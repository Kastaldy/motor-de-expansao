#!/usr/bin/env python3
"""Guard de caminhos protegidos - ralph loop autonomo (BLK-LOOP-01) + check `guard` do CI.

O guard tem UM juiz (este arquivo) e DOIS consumidores:

1. Ralph loop (`run-ralph-loop.sh`, container local) -> `--base <ref>`:
   deriva do git os caminhos com INTENCAO DE MERGE (commitados entre <ref> e HEAD + staged/--cached).
   NAO olha o working tree nao-staged (commit-by-path nao mergeia isso; evita falso-positivo de churn
   de CRLF/__pycache__).

2. Check `guard` do CI (job em `pull_request_target`, rodando a partir do checkout da BASE) -> `--stdin`:
       gh pr diff --name-only <N> | python scripts/loop_guard.py --stdin --json
   O script que JULGA vem da base (main), nunca do PR - e por isso que um PR agentico nao consegue
   desarmar o proprio guarda. O job NUNCA faz checkout nem executa codigo do PR.

Duas classes de caminho protegido:

* CRITICO   - nucleo do M1 (score/pesos/config/pipelines/artefatos oficiais), scores PARALELOS
              servidos em producao (flag_sam/carteira/plano/relatorio municipal), producao/VPS/CI,
              o BANCO de producao (migrations, autenticacao/autorizacao, trilha de eventos e os
              crons que o operam com a senha do dono) e os arquivos que ARMAM os proprios checks
              do CI (pyproject/conftest/constraints/gitleaks/Dockerfile/scripts/ci). Sem estes
              ultimos, um PR desarma o check `test` a partir do proprio HEAD (o job `test` roda em
              `pull_request`) e auto-mergeia com tudo verde.
* GOVERNANCA - os arquivos que definem as PROPRIAS regras (este guard, CLAUDE.md, backlog, REVIEW.md,
              runner do loop, .gitignore, .claude/, .github/), as camadas de PRODUCAO que calculam
              ou exibem numeros para o comite (dashboard/data, API/bot, viabilidade, lifetime,
              demanda revelada), os instrumentos de VEREDITO sobre identidade no banco e o
              contrato da porta unica dele. Sem isso um agente poderia reescrever o guarda que o
              julga - ou mudar, num bloco "Media" auto-mergeavel, um numero que o comite le como
              verdade.

Semantica de saida (o guard REPORTA; quem DECIDE e o consumidor):

* `--stdin` (CI): exit 1 se QUALQUER classe for tocada; o job do CI resolve pela regua de labels
  (`aprovado-humano` para Alta, `critica-aprovada` para Critica) - o Felipe precisa poder alterar o
  M1 com DEC aprovada, entao o guard nao e um "nao" absoluto.
* `--base` (ralph): comportamento IDENTICO ao historico - exit 1 SO em CRITICO. GOVERNANCA vira
  AVISO nao-fatal porque o proprio loop faz housekeeping legitimo em `tasks/backlog.md`,
  `tasks/completed.md` e `CLAUDE.md`; bloquear isso mataria o loop a cada ciclo. A revisao dessas
  mudancas acontece no PR (onde o modo `--stdin` do CI as sinaliza).

Nos DOIS modos, caminho que o git cita (aspas nas pontas + octal: o nome com acento, no
`git diff --name-only` e no `gh pr diff --name-only`) e' desfeito ANTES de casar as regras --
senao toda regra ancorada era contornavel por um acento no caminho.

Uso:
    python scripts/loop_guard.py --base <ref> [--json]
    gh pr diff --name-only <N> | python scripts/loop_guard.py --stdin [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

CLASSE_CRITICO = "critico"
CLASSE_GOVERNANCA = "governanca"

# N10 (fail-closed): teto de caminhos aceitos no modo `--stdin`. `gh pr diff --name-only` pode
# TRUNCAR a lista num PR gigante (limite da API do GitHub); um caminho protegido ALEM do teto
# ficaria invisivel e o guard reportaria "limpo". Ao alcancar este limite REPROVAMOS sem tentar
# classificar - a lista ja nao e confiavel. So se aplica ao `--stdin` (CI); o `--base` do ralph
# deriva o diff do git local, sem truncamento de API.
_STDIN_TRUNCATION_LIMIT = 3000
_TRUNCATION_SENTINEL = "<lista-truncada>"

# --- Classe CRITICO: nucleo do M1, scores paralelos servidos em producao, producao/VPS/CI ---------
# Regras ANCORADAS a caminhos especificos - NAO casar nomes genericos: um `config.py`/`constants.py`
# de modulo paralelo qualquer segue LIMPO (so o caminho EXATO de `dimensionamento/config.py` cai
# aqui, e por carregar premissas financeiras + a lista anti-PII).
_DENY_CRITICO: list[tuple[str, str]] = [
    (r"^src/motor_expansao/config\.py$", "config.py raiz - parametros canonicos do M1"),
    (r"^src/motor_expansao/pipelines/m1/", "pipeline oficial do M1"),
    (r"(^|/)[^/]*scoring[^/]*\.py$", "arquivo de score (scoring)"),
    (r"^src/motor_expansao/(core|dashboard)/constants\.py$", "constants.py - pesos/constantes M1/mapa"),
    # Scores PARALELOS servidos em producao (DEC-006/DEC-007 gate do SAM, carteira, plano, residual).
    # O regex `*scoring*` acima NAO casa esses arquivos - eram o furo do guard.
    (
    # `enriquec` (e nao `enriquecer`): o prefixo antigo casava
    # `enriquecer_outputs_residual_mercado.py` e NAO casava
    # `enriquecimento_espacial_hexagonos.py` -- justamente quem materializa a oferta de
    # 1,5 milhao de hexes, o insumo do consumo e do residual. Ele saia LIMPO, entao um PR
    # "Media" auto-mergeavel podia reescrever a oferta do pais sem gate humano (DEC-048).
        r"^src/motor_expansao/pipelines/(calcular_colunas_mercado|pop_corte|gerar_carteira|gerar_plano|enriquec)",
        "camada de mercado/residual servida em producao (flag_sam/carteira/plano - DEC-006/DEC-007)",
    ),
    # Insumos/scores PARALELOS que alimentam o que e servido em producao: o censitario calibrado
    # (score PRIMARIO operacional), o hibrido, a OFERTA (concorrentes/Ultra/penetracao) e o dominio.
    # Um bloco "Media" auto-mergeavel nao pode mover esses numeros sem gate.
    (
        r"^src/motor_expansao/pipelines/(calibrar_renda_setor_2022|modelo_hibrido_expansao|normalizar_concorrentes|normalizar_unidades_ultra|calcular_penetracao_ultra_hex|gerar_relatorio_expansao_dominio)\.py$",
        "score/insumo paralelo servido em producao (censitario/hibrido/oferta)",
    ),
    # PRODUTORES da camada censitaria. A linha acima cobre quem CALIBRA o score; estes sao
    # quem MATERIALIZA a renda e a populacao por setor e por hexagono -- ou seja, o insumo
    # do score. Ate 2026-08-31 os cinco saiam LIMPOS do guard, e por isso um PR "Media"
    # auto-mergeavel podia reescrever a renda de 1,3 milhao de hexagonos sem gate humano.
    # Nao e' hipotese: foi por um defeito nesses arquivos que a renda censitaria de TODAS
    # as UFs ficou espacialmente errada, com Sao Paulo trocando 10 dos 10 primeiros da fila.
    (
        r"^src/motor_expansao/pipelines/(fase_a_[a-z0-9_]+|recalcular_score_absoluto|"
        r"materializar_setores_censitarios_geo|agregar_censo_hex_da_malha)\.py$",
        "produtor da camada censitaria (renda/populacao por setor e por hexagono)",
    ),
    (
        r"^src/motor_expansao/dashboard/relatorio_municipal\.py$",
        "limiares do 'hexagono destacado' do Relatorio Municipal (DEC-011)",
    ),
    # Ponto UNICO da renda exibida (E0 da correcao de renda): formula, fatores temporais
    # versionados (`fatores/<PAIS>/*.json` + `VIGENTE`), insumos de uplift/moradores e o
    # recalculo pela PNAD. Trocar o VIGENTE ou uma linha da formula muda a renda de TODAS as
    # telas, PDFs, API e bot de uma vez -- sem esta regra o pacote saia LIMPO e um PR "Media"
    # auto-mergeavel podia mover esse numero sem gate humano.
    (
        r"^src/motor_expansao/renda/",
        "ponto unico da renda exibida (formula + fatores versionados + VIGENTE)",
    ),
    # Recomendacao unica (Top 10 = 5 Mata Virgem + 5 Premium; DEC-077): a regua versionada
    # (`regra/<PAIS>/*.json` + `VIGENTE`) e o nucleo que ordena os hexagonos. Trocar um numero
    # da regua ou uma linha da ordenacao muda a lista que web, API, bot e PDF mostram ao comite
    # -- nao pode sair LIMPO num PR "Media" auto-mergeavel.
    (
        r"^src/motor_expansao/recomendacao/",
        "recomendacao unica (regua versionada + VIGENTE + nucleo do Top 10 - DEC-077)",
    ),
    (
        r"^src/motor_expansao/dimensionamento/config\.py$",
        "premissas financeiras + lista anti-PII do motor de viabilidade (DEC-009/DEC-012)",
    ),
    # INPUTS VERSIONADOS do M1: a malha IBGE define o universo de hexes e a fracao-de-terra
    # (DEC-002/DEC-003). Um PR "Media" auto-mergeavel que editasse a malha MOVERIA o M1 sem tocar
    # uma linha de codigo protegido -> tem de ser CRITICO junto com os artefatos.
    (r"^data/(raw/)?ibge/", "malha IBGE versionada - insumo do universo de hexes do M1 (DEC-002/003)"),
    (r"brasil_(estrutural|priorizados)", "artefato oficial M1 (brasil_*)"),
    (r"hexagonos_brasil", "artefato oficial M1 (hexagonos_brasil*)"),
    (r"top_oportunidades_resumo|resumo_por_uf", "artefato oficial M1 (resumos)"),
    (
        r"(^|/)(hexagonos_mercado|carteira_expansao|plano_expansao)[^/]*\.(parquet|csv)$",
        "artefato da camada de mercado/residual (servido em producao)",
    ),
    (r"(^|/)hexagonos_dashboard_enriquecido/", "artefato enriquecido servido ao dashboard"),
    (r"^deploy/", "deploy/ (VPS)"),
    # `^Dockerfile\.` (nao so web|api): o `Dockerfile.loop` - imagem do proprio loop autonomo -
    # ficava de fora do regex antigo.
    (r"^Dockerfile\.", "imagem Docker (web/api/loop)"),
    (r"^\.dockerignore$", "contexto de build da imagem"),
    (r"docker-compose", "compose de producao"),
    (r"(^|/)Caddyfile", "Caddy (VPS)"),
    (r"^authelia/", "Authelia (VPS)"),
    # BANCO de producao (Postgres/PostGIS). Desde 23/10/2026 ele AUTORIZA o piloto BR (RBAC por
    # `MOTOR_DATABASE_URL`) e, ligado o P19 (`MOTOR_AUTENTICACAO_PROPRIA`, DEC-067), AUTENTICA:
    # e' o sucessor do `authelia/` logo acima, por isso fica na MESMA classe. Ate' aqui o pacote
    # inteiro saia LIMPO -- um bloco "Media" auto-mergeavel podia afrouxar o `_dev_ativo` do
    # `rbac.py` (qualquer um vira qualquer usuario), aceitar senha errada no `senhas.py`,
    # conceder permissao por migration (aplicada pelo papel DONO, fora do RBAC) ou parar de
    # carimbar o autor da auditoria no `postgres.py`, sem gate humano nenhum. Nao e' hipotese:
    # o #447 mexeu em `cli.py`/`postgres.py`/`senhas.py` (o `conferir` e o `privilegios`
    # aprovavam bancos quebrados) e o guard so' o marcou pelo `.gitignore` do mesmo diff.
    # CRITICO, e nao GOVERNANCA, pelo efeito no ralph: o banco guarda dado pessoal e credencial
    # (login, e-mail, hash de senha, token de sessao, IP) e o criterio loop-safe proibe persistir
    # PII e tocar segredo -- o loop tem de ABORTAR, nao so' avisar. O pacote entra INTEIRO na
    # terceira regra (e nao como lista de arquivos): modulo novo nasce coberto, a licao das
    # regras que "nasceram fora da lista" (DEC-070/071/074). As duas primeiras so' afinam o motivo.
    (
        r"^src/motor_expansao/db/migracoes/",
        "migrations do banco de producao (DDL + seed do RBAC, aplicadas pelo papel dono)",
    ),
    (
        r"^src/motor_expansao/db/(rbac|usuarios|senhas|sessoes)\.py$",
        "autenticacao/autorizacao do piloto pelo banco (RBAC em producao + login proprio do P19 - DEC-067)",
    ),
    (
        r"^src/motor_expansao/db/",
        "pacote do banco de producao (porta unica de conexao, runner de migration como dono, trilha de eventos)",
    ),
    # Crons do banco na VPS (instalados a mao no host e rodando sozinhos todo dia): os dois de
    # hoje leem a senha do papel DONO do Postgres no `.env` de producao; o backup tambem le a
    # chave do restic/S3 e produz o dump com dado pessoal, e o expurgo executa a retencao do IP
    # das sessoes (P15), que so' vale porque roda ANTES do backup. Mesmo raciocinio dos
    # lancadores do loop (abaixo): um PR mergeado que os altere exfiltra o segredo na proxima
    # instalacao. A regra casa o NOME (`banco`/`sessoes` em qualquer ponto do caminho sob
    # `scripts/cron/`), e nao a lista dos dois de hoje: o proximo cron do banco (restore, copia
    # off-box, um ajudante que eles carreguem) nasce coberto -- a mesma licao do pacote acima.
    # Os OUTROS crons de `scripts/cron/` tambem leem o `.env` e ficam fora daqui por escopo --
    # estender a regra a eles e' decisao propria, nao efeito colateral desta.
    (
        r"^scripts/cron/.*(banco|sessoes)",
        "cron do banco na VPS - opera o Postgres de producao com a senha do papel dono (backup: chave restic/S3 + dump com dado pessoal)",
    ),
    (r"(^|/)\.env($|\.)", ".env / segredos"),
    (r"^secrets/", "secrets/"),
    # Lancadores do loop: LEEM o CLAUDE_CODE_OAUTH_TOKEN do .env do dono e o injetam no container.
    # Um PR mergeado que os altere exfiltra o token no proximo clique do dono -> CRITICO.
    (r"^iniciar-loop\.cmd$", "lancador do loop - manuseia o CLAUDE_CODE_OAUTH_TOKEN"),
    (r"^scripts/iniciar_loop\.ps1$", "lancador do loop - manuseia o CLAUDE_CODE_OAUTH_TOKEN"),
    (r"\.enc\.", "arquivo encriptado (segredo)"),
    (r"^\.gitattributes$", ".gitattributes - eol/binary dos .enc.*"),
    # `.github/workflows/` e CRITICO (nao GOVERNANCA): sao os workflows que rodam com os secrets do
    # repo e definem os proprios checks obrigatorios (`test`/`guard`/`claude-review`/`review-gate`).
    # Como o CRITICO e avaliado ANTES da GOVERNANCA, `.github/workflows/guard.yml` cai aqui; o resto
    # de `.github/` (CODEOWNERS, templates, actions auxiliares) cai em GOVERNANCA.
    (r"^\.github/workflows/", "CI (.github/workflows) - workflows com secrets e checks obrigatorios"),
    # --- Arquivos que ARMAM os checks do CI -------------------------------------------------------
    # O job `test` roda em `pull_request`, ou seja A PARTIR DO HEAD DO PR. Logo, quem controla estes
    # arquivos controla o proprio veredito: `[tool.pytest.ini_options] testpaths=[]` ou
    # `[tool.ruff] extend-exclude=["src"]` deixam o `test` VERDE sem rodar nada, e um `conftest.py`
    # pode neutralizar a suite inteira. `constraints.txt` e supply chain (entra na imagem de prod).
    (r"^pyproject\.toml$", "pyproject.toml - config do pytest/ruff + deps da imagem"),
    (r"^constraints\.txt$", "constraints.txt - lockfile universal (supply chain)"),
    (r"(^|/)conftest\.py$", "conftest - pode neutralizar a suite inteira"),
    (r"^\.gitleaks(\.toml|ignore)$", "config do gate de segredos (gitleaks)"),
    (r"^\.trivyignore$", "config do gate de imagem (Trivy)"),
    # F1 (N1) - a PRECEDENCIA de config favorece o atacante: `pytest.ini`/`tox.ini` vencem o
    # `[tool.pytest.ini_options]` do pyproject; `ruff.toml`/`.ruff.toml` vencem `[tool.ruff]`;
    # `mypy.ini`/`.mypy.ini` vencem `[tool.mypy]`; e `setup.py`/`setup.cfg`/`sitecustomize.py`
    # EXECUTAM codigo no `pip install -e .` / import do job `test`. Basta ADICIONAR um destes
    # arquivos novos na raiz e os 3 gates (ruff/mypy/pytest) ficam verdes sem rodar nada, com o
    # pyproject.toml (ja protegido) intocado. Um `.pth` em qualquer lugar injeta codigo no import.
    (
        r"^(setup\.py|setup\.cfg|pytest\.ini|tox\.ini|ruff\.toml|\.ruff\.toml|mypy\.ini|\.mypy\.ini|sitecustomize\.py)$",
        "config de ferramenta na raiz - tem precedencia sobre o pyproject.toml (desarma ruff/mypy/pytest)",
    ),
    (r"(^|/)[^/]+\.pth$", "arquivo .pth - injeta codigo no import do Python"),
    # Scripts que o job `test` EXECUTA a partir do HEAD do PR -- hoje o banco de ensaio
    # (`scripts/ci/banco_de_ensaio.sh`): sobe o PostGIS do compose, aplica a cadeia de migrations
    # do zero e exige o teste de integracao do banco SEM pular, conferindo o junit. Mesmo caso do
    # `conftest.py`: quem controla o script controla o veredito, e um `exit 0` no `verificar`
    # deixa o `test` verde sem ter migrado nada. O diretorio inteiro, para o proximo script de CI
    # nascer coberto.
    (
        r"^scripts/ci/",
        "script que o job `test` executa a partir do HEAD do PR (hoje, o banco de ensaio) - pode desarmar o check",
    ),
]

# --- Classe GOVERNANCA: as regras do jogo + as camadas de PRODUCAO que produzem os numeros --------
# Exige `aprovado-humano` no CI (Alta); no ralph e so AVISO (housekeeping legitimo em backlog/CLAUDE).
_DENY_GOVERNANCA: list[tuple[str, str]] = [
    (r"^scripts/loop_guard\.py$", "o proprio guard (auto-edicao do guarda)"),
    (r"^\.claude/", "configuracao do harness Claude (permissoes/hooks/agentes)"),
    (r"^REVIEW\.md$", "instrucoes do revisor automatico"),
    (r"^CLAUDE\.md$", "fonte canonica de regras e DECs"),
    (r"^tasks/backlog\.md$", "backlog - marcador de autonomia/criticidade dos blocos"),
    (r"^run-ralph-loop\.sh$", "runner do loop autonomo (redes de seguranca)"),
    (r"^\.gitignore$", ".gitignore - o que fica fora do versionamento"),
    (r"^\.github/", "configuracao do repositorio (.github)"),
    # Caminhos de PRODUCAO que CALCULAM ou EXIBEM os numeros que o comite ve. Nao sao o M1 (nao viram
    # CRITICO), mas tambem nao podem entrar via bloco "Media" auto-mergeavel sem olho humano.
    # `components.py`/`pages.py` ficam de FORA de proposito: sao display puro (cor, layout, widget) e
    # o auto-merge morre se todo ajuste visual virar falso-positivo.
    # `mercado_raio` (DEC-070: SAM/consumo/residual/score do ponto nas TRES superficies) e
    # `geometria_desenhada` (DEC-071: limites da area desenhada) entraram em 2026-10-14 --
    # nasceram fora da lista e um PR "Media" que mexesse so' neles passaria limpo.
    # `alcance_ponto` (DEC-074: raio de 2 km, isocrona de 10 min e o FATOR que escala as
    # reguas absolutas) entrou no MESMO PR que o criou, pela mesma razao.
    (
        r"^src/motor_expansao/dashboard/"
        r"(data|utils|censo_point|censo_map|censo_report|mercado_raio|geometria_desenhada|"
        r"alcance_ponto)\.py$",
        "camada que calcula/exibe os numeros do dashboard",
    ),
    (r"^src/motor_expansao/api/", "API/bot servidos em producao"),
    # DEC-022 — o piloto web e' o app de producao que substitui o Streamlit. O backend
    # (web/server) calcula/exibe os numeros do comite e o frontend define o que o usuario
    # ve; nenhum dos dois entra por bloco "Media" auto-mergeavel sem olho humano.
    (r"^web/", "piloto web servido em producao (frontend + backend FastAPI)"),
    # BLK-INTL-13 — as duas paginas estaticas que o Caddy serve na raiz (bind mount
    # `./portal:/srv/portal:ro`). Nao decidem roteamento nem acesso (por isso nao e'
    # CRITICO), mas sao conteudo servido em producao na porta de entrada: nao entram
    # por bloco "Media" auto-mergeavel sem olho humano (spec docs/spec_portal_selecao_pais.md §8).
    (r"^portal/", "portal de selecao de pais servido na raiz"),
    (
        r"^src/motor_expansao/dimensionamento/viabilidade_ponto\.py$",
        "motor de viabilidade (DEC-009)",
    ),
    (
        r"^src/motor_expansao/(lifetime|demanda_revelada|vulnerabilidade)/",
        "camadas paralelas com insumo de PII na origem (DEC-012)",
    ),
    # Instrumentos de VEREDITO sobre identidade no banco: o conferidor do corte (diz se quem entra
    # hoje esta' no banco com as mesmas abas; roda no host da VPS lendo o `users_database.yml` do
    # Authelia) e o rastreio de vazamento (diz QUEM gerou um PDF ou XLSX). Nao escrevem nada nem
    # leem o `.env` -- por isso nao sao CRITICO --, mas o veredito deles e' lido como verdade num
    # corte de acesso e numa acusacao, e nao pode mudar num "Media" auto-mergeavel sem olho
    # humano (o #455 criou o conferidor e o guard o via LIMPO). `scripts/extrair_migracoes.py`
    # fica de FORA de proposito: ele so' gera arquivo em `db/migracoes/`, que ja' e' CRITICO.
    (
        r"^scripts/(conferir_usuarios_banco|rastrear_arquivo)\.py$",
        "instrumento de veredito sobre identidade no banco (conferidor do corte de acesso / rastreio de vazamento)",
    ),
    # Contrato da PORTA UNICA do banco (D28): o teste varre `src/`, `web/server` e `scripts/` e
    # recusa conexao aberta fora de `db/postgres.py`/`db/cli.py` -- quem escreve fora dali
    # escreve SEM o carimbo `app.id_usuario`, e a auditoria registra autor nulo. Ele e' a unica
    # trava sobre codigo LIMPO (um modulo qualquer de `src/` sai LIMPO do guard), e o jeito
    # natural de um agente "fazer passar" e' acrescentar o proprio arquivo a `_PERMITIDOS`.
    # Precedente: `tests/unit/test_scoring.py` ja' e' protegido (CRITICO, pelo `*scoring*`) --
    # teste que E' a regra nao fica livre.
    (
        r"^tests/contracts/test_conexao_por_uma_porta_so\.py$",
        "contrato da porta unica do banco (D28) - a allowlist e' a unica trava sobre codigo LIMPO",
    ),
    # N3 - governanca da esteira e insumos/config de PRODUCAO que um bloco "Media" auto-mergeavel
    # nao deve mover sem olho humano: os PROMPTS dos agentes (definem o comportamento da esteira),
    # a config do harness Codex, o housekeeping do backlog, o cache de oferta versionado e a config
    # do dashboard de producao.
    (r"^prompts/", "prompts dos agentes da esteira"),
    (r"^\.codex/", "config do harness Codex"),
    (r"^scripts/housekeeping_move_block\.py$", "housekeeping do backlog"),
    (r"^data/osm_cache/", "cache de oferta versionado"),
]

_DENY_CRITICO_RES = [(re.compile(p), motivo) for p, motivo in _DENY_CRITICO]
_DENY_GOVERNANCA_RES = [(re.compile(p), motivo) for p, motivo in _DENY_GOVERNANCA]

# Alias legado: antes existia UMA lista `_DENY_RES` (== a classe CRITICO de hoje). Mantido para nao
# quebrar consumidores/testes existentes que importam o nome.
_DENY_RES = _DENY_CRITICO_RES


@dataclass(frozen=True)
class Violacao:
    """Um caminho tocado que cai numa classe protegida."""

    path: str
    classe: str
    motivo: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "classe": self.classe, "motivo": self.motivo}


# Citacao do git (`core.quotePath`, ligado por padrao): caminho com byte fora do ASCII, aspas,
# barra invertida ou caractere de controle chega ENTRE ASPAS e com escape em octal -- tanto no
# `git diff --name-only` do ralph quanto no `gh pr diff --name-only` do CI (medido no #136, que
# o `gh` lista como `"Motor de Expans\303\243o - Refer\303\252ncia (standalone).html"`). As regras
# ANCORADAS nao casam a aspa da ponta: ate' 2026-10-24, um modulo novo em `db/`, um script em
# `scripts/ci/` ou um `conftest.py` (que neutraliza a suite, F1) com acento em qualquer ponto do
# caminho saiam LIMPOS nos DOIS modos. Desfazer a citacao antes de casar so' ACRESCENTA acerto:
# a parte ASCII do caminho nao muda, e nenhuma regra depende de aspa ou de escape.
_ESCAPES_DO_GIT = {
    "a": 0x07,
    "b": 0x08,
    "t": 0x09,
    "n": 0x0A,
    "v": 0x0B,
    "f": 0x0C,
    "r": 0x0D,
    '"': 0x22,
    "\\": 0x5C,
}


def _desfazer_citacao_do_git(path: str) -> str:
    """`"src/motor_expansao/db/sess\\303\\243o.py"` -> o mesmo caminho, com o `a` de til.

    Caminho sem aspas nas DUAS pontas volta intacto. Escape que o git nao produz (fora da
    tabela, octal incompleto ou acima de 377) devolve o caminho so' SEM as aspas: ali nao ha'
    citacao do git, mas tirar a aspa da ponta ainda deixa as regras ancoradas casarem o
    esqueleto ASCII -- na duvida, o guard erra para o lado de PEGAR. Nunca levanta excecao:
    guard que quebra no insumo reprova o CI e aborta o loop, mas por erro, e nao pelo motivo
    certo.
    """
    if len(path) < 2 or path[0] != '"' or path[-1] != '"':
        return path
    corpo = path[1:-1]
    saida = bytearray()
    i = 0
    try:
        while i < len(corpo):
            letra = corpo[i]
            if letra != "\\":
                saida += letra.encode("utf-8", errors="surrogatepass")
                i += 1
                continue
            seguinte = corpo[i + 1 : i + 2]
            octal = corpo[i + 1 : i + 4]
            if seguinte in _ESCAPES_DO_GIT:
                saida.append(_ESCAPES_DO_GIT[seguinte])
                i += 2
            elif len(octal) == 3 and all(c in "01234567" for c in octal) and int(octal, 8) <= 0xFF:
                saida.append(int(octal, 8))
                i += 4
            else:
                return corpo
        return saida.decode("utf-8", errors="replace")
    except (UnicodeError, ValueError):
        return corpo


def classificar(paths: Iterable[str]) -> list[Violacao]:
    """Funcao PURA: classifica caminhos em CRITICO/GOVERNANCA (o que nao casa fica de fora).

    CRITICO tem precedencia sobre GOVERNANCA (um caminho gera no maximo UMA violacao). Retorna a
    lista ordenada por caminho, sem duplicatas. Caminho citado pelo git (entre aspas, com octal)
    e' desfeito ANTES de casar, e a violacao carrega o caminho desfeito, legivel na tabela do CI.
    """
    violacoes: list[Violacao] = []
    for path in sorted({_desfazer_citacao_do_git(p.strip()) for p in paths if p.strip()}):
        for rx, motivo in _DENY_CRITICO_RES:
            if rx.search(path):
                violacoes.append(Violacao(path, CLASSE_CRITICO, motivo))
                break
        else:
            for rx, motivo in _DENY_GOVERNANCA_RES:
                if rx.search(path):
                    violacoes.append(Violacao(path, CLASSE_GOVERNANCA, motivo))
                    break
    return violacoes


def _git(*args: str) -> str:
    # `stdin=DEVNULL`: o git daqui nunca le a entrada, e herda-la falha de vez em quando no
    # Windows (WinError 6/50 ao duplicar um stdin redirecionado) -- o guard quebraria por
    # erro de ambiente, e nao pelo motivo certo. No container do ralph nao muda nada.
    out = subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL
    )
    return out.stdout


def _changed_paths(base: str) -> set[str]:
    """Caminhos com INTENCAO de merge: commitados (base..HEAD) + staged (--cached).

    NAO inclui o working tree nao-staged/untracked de proposito: o loop commita POR PATH, entao
    so o que esta commitado/staged seria mergeado. Modificacoes transitorias nao-staged (ex.: churn
    de CRLF do container Linux, __pycache__, artefatos regenerados) NAO representam intencao de
    merge e davam falso-positivo. O `.gitattributes` (eol=lf) elimina o churn de line-ending.
    """
    paths: set[str] = set()
    # Commitados desde o inicio do loop.
    for line in _git("diff", "--name-only", f"{base}..HEAD").splitlines():
        if line.strip():
            paths.add(line.strip())
    # Staged (indexado para o proximo commit).
    for line in _git("diff", "--cached", "--name-only").splitlines():
        if line.strip():
            paths.add(line.strip())
    return paths


def _stdin_paths() -> set[str]:
    """Le a lista de caminhos (um por linha) do stdin (ex.: `gh pr diff --name-only <N>`)."""
    return {line.strip() for line in sys.stdin.read().splitlines() if line.strip()}


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Guard de caminhos protegidos (M1/producao + governanca): ralph loop e check `guard` do CI."
    )
    fonte = ap.add_mutually_exclusive_group(required=True)
    fonte.add_argument("--base", help="ref git do inicio do loop (HEAD inicial); deriva o diff via git")
    fonte.add_argument(
        "--stdin",
        action="store_true",
        help="le a lista de caminhos alterados (um por linha) do stdin, sem tocar no git",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help='imprime {"limpo": bool, "violacoes": [...]} em stdout (para o job do CI consumir)',
    )
    args = ap.parse_args(argv)

    modo_stdin = bool(args.stdin)
    paths = _stdin_paths() if modo_stdin else _changed_paths(args.base)

    # N10 (fail-closed): lista de caminhos truncada pela API do GitHub -> nao da para confiar que
    # todo caminho protegido esta visivel. Reprova antes de classificar, com motivo explicito. So no
    # `--stdin` (CI); o `--base` do ralph le o diff do git local e nao sofre truncamento.
    if modo_stdin and len(paths) >= _STDIN_TRUNCATION_LIMIT:
        motivo = (
            f"lista de {len(paths)} caminhos alcancou o teto de {_STDIN_TRUNCATION_LIMIT} "
            "(gh pr diff pode ter truncado o diff da API) - um caminho protegido ficaria invisivel; "
            "reprovando fail-closed"
        )
        if args.json:
            payload = {
                "limpo": False,
                "violacoes": [
                    {"path": _TRUNCATION_SENTINEL, "classe": CLASSE_CRITICO, "motivo": motivo}
                ],
            }
            print(json.dumps(payload, ensure_ascii=True))
            return 1
        print(f"GUARD: {motivo}", file=sys.stderr)
        return 1

    violacoes = classificar(paths)

    # No CI (`--stdin`), QUALQUER classe e fatal e a decisao final (label) e do job.
    # No ralph (`--base`), so CRITICO e fatal: o loop faz housekeeping legitimo em backlog/completed/
    # CLAUDE.md, e bloquear isso mataria o loop a cada ciclo.
    classes_fatais = (
        {CLASSE_CRITICO, CLASSE_GOVERNANCA} if modo_stdin else {CLASSE_CRITICO}
    )
    fatais = [v for v in violacoes if v.classe in classes_fatais]

    if args.json:
        payload = {
            "limpo": not violacoes,
            "violacoes": [v.to_dict() for v in violacoes],
        }
        print(json.dumps(payload, ensure_ascii=True))
        return 1 if fatais else 0

    if fatais:
        print("GUARD: caminho(s) PROTEGIDO(s) tocado(s):", file=sys.stderr)
        for v in fatais:
            print(f"  - [{v.classe.upper()}] {v.path}  ->  {v.motivo}", file=sys.stderr)
        return 1

    avisos = [v for v in violacoes if v.classe not in classes_fatais]
    if avisos:
        print(
            "GUARD AVISO: caminho(s) de GOVERNANCA tocado(s) (nao bloqueia o loop; revisar no PR):",
            file=sys.stderr,
        )
        for v in avisos:
            print(f"  - [{v.classe.upper()}] {v.path}  ->  {v.motivo}", file=sys.stderr)
        print(f"GUARD OK: {len(paths)} caminho(s) alterado(s), nenhum CRITICO.")
        return 0

    print(f"GUARD OK: {len(paths)} caminho(s) alterado(s), nenhum proibido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
