"""DEC-059: contrato TEXTUAL do wrapper da regeneração semanal da camada de mercado.

Mesmo molde (e mesmas limitações declaradas) de `test_wrappers_cron_agregadores.py`: um teste que
EXECUTASSE este wrapper precisaria de Docker, do clone do coletor, de ~550 MB de rascunho e da malha
de 1,17 GB — inviável em suíte. O que dá para travar de graça, e é o que mais importa, são as
propriedades que um `bash -n` não vê e que uma edição futura apagaria sem ninguém perceber:

  * o REGIME DE ESCRITA — rascunho, `&&` entre os passos, validação antes de publicar, rename
    atômico. É a razão de o bloco existir: ligar o Bloco 3 no regime antigo (escrita direta no
    staging vivo com `||` tolerante entre os passos) publicaria estado misto;
  * a ORDEM da cadeia, com `enriquecimento_espacial_hexagonos` ENTRE `normalizar_concorrentes` e
    `calcular_colunas_mercado` — tirá-lo dali devolve a dívida inteira (a academia coletada no
    domingo volta a não pressionar ninguém);
  * o que é HARDLINK e o que é CÓPIA REAL: `to_parquet` trunca o inode, então hardlink num artefato
    que a cadeia sobrescreve vazaria para o arquivo VIVO — o oposto do que o rascunho promete;
  * a malha de setores montada `:ro` — sem ela a promoção da DEC-054 vira no-op EM SILÊNCIO;
  * **nenhum comando executável toca a VPS de outra máquina** (CLAUDE.md §6);
  * o healthcheck expõe o subcomando novo nos TRÊS lugares (função, `case`, string de uso).

A checagem de comandos proibidos ignora LINHAS DE COMENTÁRIO de propósito: o cabeçalho precisa poder
dizer, em prosa, que o script nunca faz essas coisas. Comentário não executa.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "scripts" / "cron" / "run_regen_mercado.sh"
HEALTHCHECK = ROOT / "scripts" / "healthcheck_vps.sh"
RUNBOOK = ROOT / "docs" / "infra_producao.md"

# Comandos que NENHUM wrapper de cron deste repo pode executar. O espaço no fim é deliberado:
# casa a invocação, não a palavra dentro de um caminho.
COMANDOS_PROIBIDOS: tuple[str, ...] = ("ssh ", "scp ", "git pull", "docker compose up", "rsync ")

#: A cadeia, na ordem em que tem de rodar. O Bloco 3 no meio é a mudança da DEC-059.
CADEIA: tuple[str, ...] = (
    "motor_expansao.pipelines.normalizar_concorrentes",
    "motor_expansao.pipelines.enriquecimento_espacial_hexagonos",
    "motor_expansao.pipelines.calcular_colunas_mercado",
    "motor_expansao.pipelines.gerar_carteira_acionavel",
    "motor_expansao.pipelines.gerar_plano_expansao_curto_prazo",
    "motor_expansao.pipelines.gerar_plano_expansao_dominio",
    "motor_expansao.pipelines.enriquecer_outputs_residual_mercado",
    "materialize_enriched_dashboard",
)


def _linhas_executaveis(caminho: Path) -> list[str]:
    """Linhas do script sem os comentários (linha cujo 1º caractere não-branco é `#`).

    Vale também para o validador em Python embutido no heredoc: lá o comentário também começa
    com `#`, e o que se quer medir é sempre o que EXECUTA.
    """
    texto = caminho.read_text(encoding="utf-8")
    return [linha for linha in texto.splitlines() if not linha.lstrip().startswith("#")]


def _bloco_da_cadeia() -> list[str]:
    """Só as linhas do passo 3 (o `docker run` da cadeia).

    Necessário porque a PRÉ-CHECAGEM do passo 1 também cita
    `motor_expansao.pipelines.enriquecimento_espacial_hexagonos` (o `import` que prova que a
    imagem tem o módulo) — procurar no arquivo inteiro casaria com ela e mediria a ordem errada.
    """
    linhas = _linhas_executaveis(WRAPPER)
    inicio = next(i for i, linha in enumerate(linhas) if "passo 3 - cadeia no rascunho" in linha)
    fim = next(i for i, linha in enumerate(linhas) if i > inicio and "CADEIA_RC=" in linha)
    return linhas[inicio:fim]


def test_wrapper_existe_e_e_bash() -> None:
    assert WRAPPER.is_file(), f"o wrapper do regen deveria existir em {WRAPPER}"
    texto = WRAPPER.read_text(encoding="utf-8")
    assert texto.startswith("#!/usr/bin/env bash"), "shebang ausente ou fora da 1a linha"
    # LF, sempre: CRLF quebra o shebang na VPS.
    assert "\r" not in texto, "o wrapper tem CRLF; o shebang quebraria na VPS"


@pytest.mark.parametrize(
    "trecho",
    [
        "set -euo pipefail",
        "flock -n 9",  # a janela do lote é de ~2h: sem lock, duas rodadas se atropelam
        "DRY_RUN",  # modo seco é passo OBRIGATÓRIO antes de agendar
        "tr -d '\\r'",  # o `.env` da VPS pode ter CRLF
        "API_IMAGE",
        "--user 0:0",  # staging/CSVs do host são root:root
        "PYTHONPATH=/app/src",  # é o que faz `ROOT` ser `/app` e o rascunho valer
        "MOTOR_DATA_DIR=/app/data",  # perfil de país fail-closed (DEC-047)
        "--memory",
    ],
)
def test_wrapper_tem_guardrails(trecho: str) -> None:
    assert trecho in WRAPPER.read_text(encoding="utf-8"), f"trecho ausente do wrapper: {trecho!r}"


@pytest.mark.parametrize("proibido", COMANDOS_PROIBIDOS)
def test_wrapper_nao_executa_comando_na_vps(proibido: str) -> None:
    """CLAUDE.md §6: a aplicação na VPS é manual, comando a comando, do Felipe."""
    executaveis = "\n".join(_linhas_executaveis(WRAPPER))
    assert proibido not in executaveis, (
        f"o wrapper EXECUTA um comando proibido ({proibido!r}); em comentário seria aceitável"
    )


def test_wrapper_loga_antes_do_flock() -> None:
    """Uma rodada TRAVADA segura o lock, e a seguinte sairia `exit 0` SEM LOG.

    Mesmo defeito corrigido na emenda de 2026-08-26 à DEC-039: com o `tee` depois do `flock`, a
    colisão não deixa arquivo nenhum em `$LOG_DIR` e o `_latest.log` continua apontando para a
    última rodada COMPLETA — que é o log errado para quem for depurar.
    """
    executaveis = _linhas_executaveis(WRAPPER)
    i_tee = next(i for i, linha in enumerate(executaveis) if "tee -a" in linha)
    i_flock = next(i for i, linha in enumerate(executaveis) if linha.startswith("flock -n 9"))
    assert i_tee < i_flock, (
        "o `tee` do log começa DEPOIS do `flock`: uma colisão de lock pularia em silêncio"
    )
    i_mkdir = next(i for i, linha in enumerate(executaveis) if 'mkdir -p "$LOG_DIR"' in linha)
    assert i_mkdir < i_tee, "o `mkdir` do LOG_DIR tem de vir antes do `tee`"
    # E o `_latest` aponta para ESTA rodada desde o início, não só no sucesso.
    i_latest = next(i for i, linha in enumerate(executaveis) if "regen_mercado_latest.log" in linha)
    assert i_latest < i_flock


# --------------------------------------------------------------------------- #
# O que o bloco veio ligar: a cadeia, na ordem, com `&&`
# --------------------------------------------------------------------------- #
def test_a_cadeia_roda_na_ordem_com_o_bloco_3_no_meio() -> None:
    """Sem o Bloco 3 entre a normalização e o cálculo, a dívida volta inteira.

    A etapa 4 de hoje começa no `calcular_colunas_mercado`: a academia coletada no domingo entra no
    cadastro e NÃO pressiona ninguém, porque `oferta_efetiva_1km_area` /
    `n_concorrentes_influencia_1km` continuam as da última vez que alguém rodou o Bloco 3 à mão.
    """
    bloco = "\n".join(_bloco_da_cadeia())
    posicoes = []
    for passo in CADEIA:
        idx = bloco.find(passo)
        assert idx != -1, f"passo ausente da cadeia: {passo}"
        posicoes.append(idx)
    assert posicoes == sorted(posicoes), (
        "os passos da cadeia estão fora de ordem; o Bloco 3 tem de rodar DEPOIS de "
        "normalizar_concorrentes e ANTES de calcular_colunas_mercado"
    )


def test_a_cadeia_e_encadeada_com_e_nao_com_ou() -> None:
    """`&&` entre os passos: a falha de um PARA a cadeia.

    O regime antigo usava `||` tolerante — um passo que morria no meio deixava a camada em estado
    MISTO (mercado novo + carteira velha) e o lote seguia com `exit 0`.
    """
    bloco = _bloco_da_cadeia()
    for passo in CADEIA[:-1]:  # o último passo da cadeia não precisa de `&&` depois dele
        linha = next(linha for linha in bloco if passo in linha)
        assert linha.rstrip().endswith("&&"), f"o passo {passo} não encadeia com `&&`: {linha!r}"
        assert "||" not in linha, f"o passo {passo} tem `||` tolerante: {linha!r}"


def test_o_bloco_3_nao_e_editado_por_este_wrapper() -> None:
    """O rascunho é por MOUNT, e é isso que mantém `src/` com zero diff.

    `enriquecimento_espacial_hexagonos.py` é CRÍTICO no `scripts/loop_guard.py` desde a DEC-048
    (foi o furo em que ele saía LIMPO). Se algum dia alguém trocar o mount por um parâmetro de
    caminho no Python, este teste continua verde — mas o guard passa a exigir aprovação humana, que
    é o comportamento correto. O que ele trava aqui é o CONTRATO do mount.
    """
    executaveis = "\n".join(_linhas_executaveis(WRAPPER))
    assert '-v "${RASCUNHO_DATA}:/app/data"' in executaveis, (
        "o rascunho não é montado em /app/data — sem isso a cadeia escreve no staging VIVO"
    )
    assert "-w /app" in executaveis, (
        "`materialize_enriched_dashboard` usa caminhos RELATIVOS (Path('data/outputs/...')): "
        "sem WORKDIR /app ele escreveria em outro lugar"
    )


# --------------------------------------------------------------------------- #
# Rascunho: o que é hardlink e o que é cópia real
# --------------------------------------------------------------------------- #
#: Artefatos que a cadeia SOBRESCREVE — hardlink neles vazaria para o arquivo vivo.
ARTEFATOS_ESCRITOS: tuple[str, ...] = (
    "staging/concorrentes_mapeados.parquet",
    "staging/hexagonos_mercado_mapeado.parquet",
    "outputs/oportunidades_expansao_hibrido.parquet",
    "outputs/carteira_expansao_acionavel.parquet",
    "outputs/plano_expansao_curto_prazo.parquet",
    "outputs/plano_expansao_dominio.parquet",
)


@pytest.mark.parametrize("artefato", ARTEFATOS_ESCRITOS)
def test_artefato_sobrescrito_entra_na_lista_de_copia_real(artefato: str) -> None:
    """`to_parquet` abre o destino em modo binário de escrita e TRUNCA O INODE.

    Com o inode compartilhado por hardlink, escrever no rascunho vazaria para o arquivo VIVO — que
    é exatamente o que o rascunho existe para impedir. A lista também é a lista de publicação: um
    artefato fora dela seria gerado no rascunho e nunca chegaria à produção.
    """
    executaveis = "\n".join(_linhas_executaveis(WRAPPER))
    assert f'"{artefato}"' in executaveis, (
        f"{artefato} não está em ARTEFATOS_ESCRITOS: ou vazaria para o vivo por hardlink, "
        "ou seria gerado e nunca publicado"
    )


def test_o_espelho_e_hardlink_e_a_excecao_e_copia_real() -> None:
    executaveis = "\n".join(_linhas_executaveis(WRAPPER))
    assert "cp -al" in executaveis, "o espelho dos insumos só-leitura não usa hardlink"
    assert 'cp -p "${HOST_DATA}/${rel}"' in executaveis, (
        "os artefatos sobrescritos não são copiados de verdade"
    )
    assert 'rm -f "${RASCUNHO_DATA}/${rel}"' in executaveis, (
        "o hardlink do artefato sobrescrito não é desfeito antes da cópia real"
    )


def test_a_malha_de_setores_entra_por_bind_read_only() -> None:
    """Sem a malha, a promoção da DEC-054 vira no-op EM SILÊNCIO.

    `calcular_colunas_mercado` chama `calcular_notas_municipio(CENSO_GEO_ROOT)` (nota de join
    municipal, que alimenta `flag_pop_min_5k` e portanto o gate do SAM) e
    `fase1_bi_exports.build_enriched_dashboard_frame` faz o mesmo para o artefato servido ao piloto.
    O contrato dessa função é: **artefato ausente devolve frame vazio e a promoção vira no-op** —
    sem erro, sem log, sem teste vermelho. Os 13.147 hexágonos promovidos (Manaus 2.038/2.139)
    voltariam ao fallback municipal e o único sintoma seria a população errada na tela.
    """
    executaveis = "\n".join(_linhas_executaveis(WRAPPER))
    assert "setores_censitarios_2022_geo:ro" in executaveis, (
        "a malha de setores não é montada `:ro` no rascunho"
    )
    # E a ausência dela ABORTA, em vez de degradar em silêncio.
    assert "DEC-054" in WRAPPER.read_text(encoding="utf-8")
    i_check = executaveis.find('"!! malha de setores ausente')
    assert i_check != -1, "não há pré-checagem que aborte quando a malha está ausente"


@pytest.mark.parametrize(
    "insumo",
    ["vulnerabilidade_ma_redes.parquet", "alunos_reais_por_unidade.parquet", "unidades_ultra_mapeadas.parquet"],
)
def test_insumo_opcional_do_bloco_3_e_exigido_pela_pre_checagem(insumo: str) -> None:
    """São OPCIONAIS no pipeline — e é por isso que precisam ser exigidos AQUI.

    Ausentes, o Bloco 3 cai em ramos de `print` e termina com SUCESSO, publicando oferta de cadeia
    26,7% subestimada (DEC-048), 1.202 academias de volta ao proxy de 2.500 (DEC-057) ou a
    canibalização da rede própria zerada. Verde, silencioso, e servido na tela.
    """
    executaveis = "\n".join(_linhas_executaveis(WRAPPER))
    assert insumo in executaveis, f"{insumo} não é pré-checado; o Bloco 3 sairia verde sem ele"


def test_pre_checagens_abortam_antes_de_montar_o_rascunho() -> None:
    """Não se copia ~550 MB para descobrir depois que falta insumo."""
    executaveis = _linhas_executaveis(WRAPPER)
    i_precheck = next(i for i, linha in enumerate(executaveis) if "passo 1 - pre-checagens" in linha)
    i_rascunho = next(i for i, linha in enumerate(executaveis) if "passo 2 - montando o rascunho" in linha)
    assert i_precheck < i_rascunho


# --------------------------------------------------------------------------- #
# Validação e publicação
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "coluna",
    [
        "oferta_efetiva_1km_area",
        "gap_competitivo_1km_area",
        "consumo_concorrentes_1km_area",
        "n_concorrentes_influencia_1km",
        "n_concorrentes_mapeados_1km",
        "flag_white_space_2km",
        "n_redes_mapeadas",
    ],
)
def test_validacao_exige_as_colunas_do_bloco_3(coluna: str) -> None:
    """Se elas não estiverem no rascunho, o que se publicaria é a camada velha com data nova."""
    assert coluna in WRAPPER.read_text(encoding="utf-8"), (
        f"a validação de publicação não exige {coluna}"
    )


def test_validacao_tem_guarda_de_desenhabilidade() -> None:
    """Lição do incidente de 2026-08-30: o refresh semanal APAGOU os pins do mapa.

    A guarda da época olhava BYTES, e um artefato gordo e sem coordenada passou. A régua aqui é a
    contagem de concorrentes DESENHÁVEIS (status válido E coordenada presente), e ela não pode CAIR.
    """
    texto = WRAPPER.read_text(encoding="utf-8")
    assert "DESENHAVEIS" in texto or "DESENHÁVEIS" in texto
    assert "concorrentes_desenhaveis" in texto
    assert "conc_novo) < len(conc_vivo)" in texto, (
        "a guarda não compara a contagem desenhável do rascunho contra a publicada"
    )


def test_validacao_compara_cardinalidade_com_o_publicado_e_nao_com_um_literal() -> None:
    """A régua é o PUBLICADO, não `1_542_531` cravado no script.

    Cravar a base H3 aqui duplicaria, fora do `config.py`, uma constante que já mudou duas vezes
    (DEC-002 -> DEC-003) — e este repo já foi mordido mais de uma vez por constante-que-já-foi-
    verdade. O invariante que importa é "a cadeia não pode PERDER hexágono".
    """
    assert "cardinalidade mudou" in WRAPPER.read_text(encoding="utf-8")
    # Só o que EXECUTA: o comentário do validador cita o número justamente para explicar por que
    # ele não está no código.
    executaveis = "\n".join(_linhas_executaveis(WRAPPER))
    assert "1_542_531" not in executaveis and "1542531" not in executaveis, (
        "o número da base H3 foi cravado no wrapper; a régua tem de ser o artefato publicado"
    )
    assert "n_vivo" in executaveis, "a cardinalidade não é comparada contra a do artefato publicado"


def test_validacao_reprovada_nao_publica_nada() -> None:
    """Reprovar significa: nada publicado, staging vivo intacto, exit != 0."""
    executaveis = _linhas_executaveis(WRAPPER)
    texto = "\n".join(executaveis)
    i_valid = texto.find("VALID_RC")
    i_publica = texto.find("passo 5 - publicando")
    assert i_valid != -1 and i_publica != -1
    assert i_valid < i_publica, "a publicação acontece antes da validação"
    assert "exit 4" in texto, "a reprovação da validação não devolve exit != 0"


def test_publicacao_e_atomica_e_legivel() -> None:
    """Molde de `crescimento/atualizar.py:publicar` — cópias primeiro, renames depois.

    E `chmod 0644` ANTES do rename: o job roda como root e os containers leem como usuário
    non-root; um umask restritivo apagaria a camada da tela sem erro nenhum no job.
    """
    executaveis = "\n".join(_linhas_executaveis(WRAPPER))
    assert '.tmp-$$' in executaveis, "não há arquivo temporário no destino"
    assert "chmod 0644" in executaveis
    i_chmod = executaveis.find("chmod 0644")
    i_mv = executaveis.find('mv -f "${par%%|*}"')
    assert i_chmod < i_mv, "o `chmod` tem de vir ANTES do rename"


def test_restart_e_obrigatorio_e_nao_recria_os_containers() -> None:
    """`lru_cache(maxsize=1)` no `MERCADO_PARQUET` (web/server/app.py): sem restart, publicar não
    muda a tela. E `restart`, nunca `up -d --force-recreate`, que reaplicaria o compose inteiro e
    poderia trocar a VERSÃO do piloto junto com o dado.
    """
    executaveis = "\n".join(_linhas_executaveis(WRAPPER))
    assert "docker compose -f \"$COMPOSE_FILE\" restart" in executaveis
    assert "force-recreate" not in executaveis
    for servico in ("web", "api", "telegram-bot"):
        assert servico in executaveis, f"o serviço {servico} não é reiniciado"


def test_avisa_nos_dois_desfechos() -> None:
    executaveis = "\n".join(_linhas_executaveis(WRAPPER))
    assert "_avisar_falha()" in executaveis and "_avisar()" in executaveis
    # Sucesso: o texto vem do validador (que é quem tem os números).
    assert '_avisar < "${RUN_DIR}/aviso.txt"' in executaveis
    # E o token NUNCA vai no argv do docker (visível em `ps`): `-e NOME` SEM valor herda do
    # ambiente exportado. `-e NOME=$valor` seria o defeito.
    assert "-e API_TELEGRAM_TOKEN -e MONITOR_TELEGRAM_CHAT_ID" in executaveis
    vazamentos = [
        linha
        for linha in _linhas_executaveis(WRAPPER)
        if re.search(r"-e\s+(API_TELEGRAM_TOKEN|MONITOR_TELEGRAM_CHAT_ID)=", linha)
    ]
    assert vazamentos == [], f"o valor do segredo entra no argv do docker: {vazamentos}"


def test_dry_run_nao_publica_nem_reinicia_nem_manda_telegram() -> None:
    executaveis = _linhas_executaveis(WRAPPER)
    texto = "\n".join(executaveis)
    i_dry = texto.find('if [ "$DRY_RUN" = "1" ]; then\n  echo ">> DRY-RUN: nada publicado')
    i_publica = texto.find("passo 5 - publicando")
    assert i_dry != -1, "não há saída antecipada em modo seco"
    assert i_dry < i_publica, "o modo seco sai DEPOIS de publicar"
    assert "DRY_RUN=1 /opt/motor-expansao-infra/run_regen_mercado.sh" in WRAPPER.read_text(
        encoding="utf-8"
    ), "o cabeçalho não ensina o modo seco"


# --------------------------------------------------------------------------- #
# Monitor
# --------------------------------------------------------------------------- #
def test_healthcheck_expoe_subcomando_mercado() -> None:
    """Função + `case` + string de uso: o trio que costuma ser atualizado pela metade."""
    texto = HEALTHCHECK.read_text(encoding="utf-8")
    assert "check_mercado()" in texto, "a função do subcomando não existe"
    assert "mercado) check_mercado ;;" in texto, "o `case` não roteia o subcomando"
    assert "|crescimento|mercado|test}" in texto, (
        "a string de uso não lista o subcomando: ele existiria sem ser descobrível"
    )


def test_healthcheck_mede_conteudo_e_nao_mtime_do_artefato() -> None:
    """O mtime MENTE aqui, e mente onde dói.

    A etapa 4 reescreve `hexagonos_mercado_mapeado.parquet` toda semana, então ele parece sempre
    fresco — inclusive no regime antigo, em que as colunas espaciais ficavam estagnadas por nove
    domingos (DEC-048: 60,46% dos hexágonos se moveram quando alguém rodou o Bloco 3 à mão). Um
    monitor por data teria ficado VERDE o tempo todo.
    """
    texto = HEALTHCHECK.read_text(encoding="utf-8")
    assert "n_redes_mapeadas" in texto, "o monitor não lê o carimbo de auditoria da camada"
    assert 'c["status_registro"] == "valido"' in texto, (
        "o monitor não compara com o cadastro de concorrentes"
    )
    assert "DESSINCRONIZADA" in texto
    # O mtime ainda é usado — mas do LOG do wrapper (que só existe quando ele roda), nunca do
    # artefato (que a etapa 4 rejuvenesce toda semana).
    assert 'stat -c %Y "$MERCADO_LOG"' in texto
    assert 'stat -c %Y "$MERCADO_PARQUET"' not in texto


def test_healthcheck_mercado_tem_limiar_configuravel() -> None:
    """O limiar é de PRODUTO (cadência do cron), não de código: tem de sair por env."""
    texto = HEALTHCHECK.read_text(encoding="utf-8")
    achado = re.search(r'MERCADO_MAX_DIAS="\$\{MONITOR_MERCADO_MAX_DIAS:-(\d+)\}"', texto)
    assert achado is not None, "o default do limiar sumiu do healthcheck"
    limiar = int(achado.group(1))
    idade_com_a_rodada_da_semana = 7
    idade_com_um_domingo_perdido = 11
    assert idade_com_a_rodada_da_semana <= limiar, "o limiar acusaria FAIL na semana em que rodou"
    assert idade_com_um_domingo_perdido > limiar, "o limiar não acusa um domingo perdido"


def test_healthcheck_mercado_falha_quando_nunca_rodou_e_quando_nao_da_para_medir() -> None:
    """Os dois estados que um monitor ingênuo leria como "está tudo bem".

    Sem log, não há idade — e "sem alarme" leria como saudável enquanto o wrapper não fosse
    instalado. Sem conseguir medir (container fora do ar), o monitor está CEGO, que também não é
    um estado verde.
    """
    texto = HEALTHCHECK.read_text(encoding="utf-8")
    assert "NUNCA rodou" in texto
    assert "Monitor cego conta como falha" in texto


def test_runbook_documenta_a_instalacao_manual() -> None:
    """A aplicação na VPS é manual, comando a comando (CLAUDE.md §6) — o runbook é o insumo dela."""
    runbook = RUNBOOK.read_text(encoding="utf-8")
    assert "run_regen_mercado.sh" in runbook, "o runbook não cita o wrapper"
    assert "DRY_RUN=1 /opt/motor-expansao-infra/run_regen_mercado.sh" in runbook, (
        "o runbook não manda rodar o modo seco antes de agendar"
    )
    assert "healthcheck_vps.sh mercado" in runbook, "o runbook não agenda o monitor novo"
