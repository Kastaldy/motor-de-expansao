"""Contrato TEXTUAL do lote de domingo (`run_weekly_90.sh`), agora versionado.

Este wrapper passou a viver no repositório em 2026-09-17. Até então era o ÚNICO de produção sem
versionamento — e o custo disso não é hipotético: a DEC-059 tirou o mount do checkout velho da
etapa de regen em 12/09 e **deixou o passo 4.5 para trás**, porque não havia diff para ninguém
revisar. O passo seguiu montando `$MOTOR/app:/app` (checkout congelado em 19/08) por cima da
imagem; o `alvos_ma` de lá declara `snapshots_concorrentes_v3`, leu a série `v4` de duas chaves
devolvendo `fonte` NULA e gravou artefato **vazio com `exit 0`** por três semanas.

O que este teste trava é exatamente o que um `bash -n` não vê e uma edição futura apagaria sem
ninguém perceber:

  * **o mount do checkout NÃO volta** — é a regressão que já aconteceu uma vez;
  * **`PYTHONPATH=/app/src` e `-w /app` FICAM** — contraintuitivo, e por isso travado: o caminho
    da carteira é resolvido pela localização do PACOTE (`ROOT` de `__file__`), não pelo CWD, então
    remover o bloco inteiro quebra com `FileNotFoundError` em `site-packages`;
  * a **guarda de desenhabilidade** antes de promover pin (incidente 30/08);
  * a **chamada única** do snapshot com as duas fontes (`delete_matching` por semana ISO);
  * a etapa de regen **delegada** ao wrapper da DEC-059, não reinlinada.

**Por que aqui NÃO vale a proibição de `git pull`/`docker compose`.** O
`test_wrappers_cron_regen_mercado.py` proíbe esses comandos, e está certo lá: aqueles wrappers são
disparados da estação/CI e um comando desses tocaria a VPS de fora (CLAUDE.md §6). Este é o
oposto — ele É o processo que roda DENTRO da VPS, pelo cron do root. Por isso este teste **exige**
os dois em vez de proibi-los.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "scripts" / "cron" / "run_weekly_90.sh"
RUNBOOK = ROOT / "docs" / "infra_producao.md"


def _linhas_executaveis(caminho: Path) -> list[str]:
    """Linhas do script sem os comentários — o que se mede é sempre o que EXECUTA.

    O cabeçalho precisa poder DIZER, em prosa, que o mount não deve voltar; comentário não executa.
    """
    texto = caminho.read_text(encoding="utf-8")
    return [linha for linha in texto.splitlines() if not linha.lstrip().startswith("#")]


def test_wrapper_existe_e_e_bash() -> None:
    assert WRAPPER.is_file(), f"o lote de domingo deveria estar versionado em {WRAPPER}"
    texto = WRAPPER.read_text(encoding="utf-8")
    assert texto.startswith("#!/usr/bin/env bash"), "shebang ausente ou fora da 1a linha"
    assert "\r" not in texto, "o wrapper tem CRLF; o shebang quebraria na VPS"


# --------------------------------------------------------------------------- #
# A regressão que já aconteceu: o checkout congelado montado por cima da imagem
# --------------------------------------------------------------------------- #
def test_nenhum_docker_run_monta_o_checkout_do_motor() -> None:
    """`-v $MOTOR/app:/app` SUBSTITUI o `/app` da imagem por um checkout que ninguém atualiza.

    Medido em 2026-09-17: o `src/` de `/opt/motor-expansao/app` estava congelado em 19/08 (131
    arquivos `.py`, zero modificados depois, sem marcador de DEC-058/059/060). Rodando o passo 4.5
    com ele: `NOMEADAS 0 | desenháveis 0 | REDES 0`, `EXIT=0`. Sem ele, na imagem: 19.807 / 19.217
    / 2.885.
    """
    executaveis = "\n".join(_linhas_executaveis(WRAPPER))
    assert "$MOTOR/app:/app" not in executaveis, (
        "o wrapper voltou a montar o checkout do motor por cima da imagem: o passo roda código "
        "velho e grava artefato VAZIO com exit 0"
    )


@pytest.mark.parametrize("trecho", ["PYTHONPATH=/app/src", "-w /app"])
def test_o_que_NAO_pode_sair_junto_com_o_mount(trecho: str) -> None:
    """Remover o bloco inteiro quebra o passo — é a armadilha oposta, e ela é contraintuitiva.

    O caminho da carteira em `alvos_ma` vem da localização do PACOTE (`ROOT` derivado de
    `__file__`), NÃO do CWD: `-w /app` sozinho não resolve. Rodando de `site-packages` o passo
    morre com
    `FileNotFoundError: '/usr/local/lib/python3.11/data/outputs/carteira_expansao_acionavel.parquet'`.
    A imagem traz `/app/src` pelo `COPY . .`, então com `PYTHONPATH=/app/src` o pacote resolve em
    `/app/src/motor_expansao` e `ROOT` volta a ser `/app` — com o código NOVO.
    """
    assert trecho in "\n".join(_linhas_executaveis(WRAPPER)), (
        f"{trecho!r} saiu do wrapper; sem ele o passo dos pins quebra em FileNotFoundError"
    )


# --------------------------------------------------------------------------- #
# As redes de segurança que já pagaram por si
# --------------------------------------------------------------------------- #
def test_guarda_de_desenhabilidade_antes_de_promover_pin() -> None:
    """TAMANHO NÃO BASTA (incidente 2026-08-30): 42.862 linhas, ~2 MB, ZERO coordenadas.

    Foi essa guarda que impediu o artefato vazio de 02/09 a 17/09 de sobrescrever os pins bons.
    """
    executaveis = "\n".join(_linhas_executaveis(WRAPPER))
    assert "DRAW" in executaveis and '"${DRAW:-0}" -ge 100' in executaveis, (
        "a guarda de desenhabilidade sumiu: artefato sem coordenada voltaria a ser promovido"
    )
    assert '_novo.parquet' in executaveis, "a promoção deixou de passar por arquivo *_novo"


def test_snapshot_e_UMA_chamada_com_as_duas_fontes() -> None:
    """`delete_matching` é por semana ISO: duas chamadas na mesma semana apagam uma à outra."""
    executaveis = "\n".join(_linhas_executaveis(WRAPPER))
    assert 'FONTES="unidades wellhub"' in executaveis, (
        "o snapshot deixou de ser UMA chamada com as duas fontes; a segunda apagaria a primeira"
    )
    assert executaveis.count("run_snapshot_concorrentes.sh") == 1


def test_regen_e_delegado_ao_wrapper_da_dec_059() -> None:
    """A etapa 4 não pode voltar a ser bloco inline (escrita direta no staging vivo)."""
    executaveis = "\n".join(_linhas_executaveis(WRAPPER))
    assert "run_regen_mercado.sh" in executaveis, "a regen deixou de delegar ao wrapper da DEC-059"
    assert "motor_expansao.pipelines.calcular_colunas_mercado" not in executaveis, (
        "a cadeia voltou a ser inline aqui, fora do regime de rascunho/validação/rename atômico"
    )


# --------------------------------------------------------------------------- #
# A exceção declarada: este wrapper roda DENTRO da VPS
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("permitido", ["git pull", "docker compose"])
def test_os_comandos_que_aqui_sao_legitimos(permitido: str) -> None:
    """Proibidos nos outros wrappers, obrigatórios neste — e a diferença é o lugar de execução.

    Se um dia isto virar violação, o certo é declarar a exceção aqui, não apagar o comando: sem o
    `git pull` o clone do coletor congela (foi o que aconteceu, 8 commits atrás em 17/09) e sem o
    `docker compose restart` os apps seguem com `lru_cache` velho depois do regen.
    """
    assert permitido in "\n".join(_linhas_executaveis(WRAPPER))


def test_o_wrapper_declara_a_divida_do_pull_engolido() -> None:
    """`git checkout -- Unidades/` + `|| echo` tornam DESTRUTIVA a falha de um coletor.

    Não é corrigido aqui de propósito — versionar não é hora de mudar comportamento —, mas fica
    NOMEADO no arquivo: foi assim que o checkout ficou 8 commits atrás sem ninguém ver.
    """
    texto = WRAPPER.read_text(encoding="utf-8")
    assert "DIVIDA DECLARADA" in texto, "a dívida do pull engolido saiu do cabeçalho"


def test_runbook_aponta_para_o_arquivo_versionado() -> None:
    """O runbook dizia 'infra na VPS, fora do repo' — afirmação que este PR torna falsa."""
    texto = RUNBOOK.read_text(encoding="utf-8")
    assert "scripts/cron/run_weekly_90.sh" in texto, (
        "o runbook não aponta para a fonte versionada do lote de domingo"
    )
    assert "infra na VPS, fora do repo" not in texto, (
        "o runbook ainda declara o wrapper como fora do repositório"
    )
