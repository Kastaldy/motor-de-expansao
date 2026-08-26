"""BLK-MA-21 / DEC-039: contrato TEXTUAL dos dois scripts de shell do cron semanal.

Não há precedente de teste de shell neste repo, e um teste que EXECUTASSE os wrappers precisaria de
Docker, do clone do coletor e de ~21h de coleta — inviável em suíte. O que dá para travar de graça,
e é o que mais importa, são as propriedades que um `bash -n` não vê e que uma edição futura pode
apagar sem ninguém perceber:

  * o wrapper dos agregadores tem `flock`, `set -euo pipefail` e o `tr -d '\\r'` do `.env` (a
    armadilha do CRLF que já matou um `docker run` com "invalid reference format") — e o log
    começa ANTES do lock, senão uma colisão pula em silêncio;
  * ele invoca o snapshot com os diretórios CURADOS, e não com o clone do coletor;
  * **nenhum comando executável dele toca a VPS de outra máquina** — nada de sessão remota, cópia
    entre hosts, atualização do clone ou `compose up`. Isso é guardrail da CLAUDE.md §6, e a
    aplicação é manual, comando a comando, do Felipe;
  * o healthcheck expõe o subcomando novo nos TRÊS lugares (função, `case` e string de uso) — que
    é exatamente o tipo de trio que se atualiza pela metade.

A checagem de comandos proibidos ignora LINHAS DE COMENTÁRIO de propósito: o cabeçalho do wrapper
precisa poder dizer, em prosa, que ele nunca faz essas coisas. Comentário não executa.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "scripts" / "cron" / "run_snapshot_agregadores.sh"
WRAPPER_SEMANAL = ROOT / "scripts" / "cron" / "run_snapshot_concorrentes.sh"
HEALTHCHECK = ROOT / "scripts" / "healthcheck_vps.sh"

# Comandos que NENHUM wrapper de cron deste repo pode executar. O espaço no fim é deliberado:
# casa a invocação, não a palavra dentro de um caminho (`/opt/gymscraping` contém "scp"? não —
# mas `sshd`, `sshpass` e nomes de arquivo com "ssh" existiriam sem o espaço).
COMANDOS_PROIBIDOS: tuple[str, ...] = ("ssh ", "scp ", "git pull", "docker compose up", "rsync ")


def _linhas_executaveis(caminho: Path) -> list[str]:
    """Linhas do script sem os comentários (linha cujo 1º caractere não-branco é `#`)."""
    texto = caminho.read_text(encoding="utf-8")
    return [linha for linha in texto.splitlines() if not linha.lstrip().startswith("#")]


def test_wrapper_agregadores_existe_e_e_bash() -> None:
    assert WRAPPER.is_file(), f"o wrapper do cron dos agregadores deveria existir em {WRAPPER}"
    texto = WRAPPER.read_text(encoding="utf-8")
    assert texto.startswith("#!/usr/bin/env bash"), "shebang ausente ou fora da 1a linha"
    # LF, sempre: CRLF quebra o shebang na VPS. O `.gitattributes` força `*.sh text eol=lf`, e
    # este teste é a rede para o caso de o arquivo chegar por outro caminho que não o git.
    assert "\r" not in texto, "o wrapper tem CRLF; o shebang quebraria na VPS"


@pytest.mark.parametrize(
    "trecho",
    [
        "set -euo pipefail",
        "flock -n",  # a janela é de ~21h45: sem lock, duas execuções duplicam a coleta
        "DRY_RUN",  # modo seco é passo OBRIGATÓRIO antes de agendar
        "PULAR_COLETA",
        "MAX_IDADE_DIAS",  # a guarda de frescor é configurável pelo operador
        "tr -d '\\r'",  # o `.env` da VPS pode ter CRLF
        "curadoria_agregadores",
        "fontes_publicadas=",  # o contrato de UMA LINHA entre o módulo e o shell
        "--fontes",
        "--dir-wellhub concorrentes/wellhub/csvs",
        "--dir-totalpass concorrentes/totalpass/csvs",
    ],
)
def test_wrapper_agregadores_tem_guardrails(trecho: str) -> None:
    assert trecho in WRAPPER.read_text(encoding="utf-8"), f"trecho ausente do wrapper: {trecho!r}"


@pytest.mark.parametrize("proibido", COMANDOS_PROIBIDOS)
def test_wrapper_agregadores_nao_executa_comando_na_vps(proibido: str) -> None:
    """CLAUDE.md §6: a aplicação na VPS é manual, comando a comando, do Felipe."""
    executaveis = "\n".join(_linhas_executaveis(WRAPPER))
    assert proibido not in executaveis, (
        f"o wrapper EXECUTA um comando proibido ({proibido!r}); em comentário seria aceitável"
    )


def test_wrapper_agregadores_falha_quando_nada_e_publicado() -> None:
    """Nada fresco para fotografar é FALHA, não sucesso silencioso.

    Se o wrapper saísse `0` aqui, a única coisa a perceber seria o alerta de idade da partição —
    9 dias depois, com a observação da semana perdida e irrecuperável.
    """
    executaveis = "\n".join(_linhas_executaveis(WRAPPER))
    assert 'if [ -z "$FONTES_CSV" ]; then' in executaveis
    assert "exit 3" in executaveis


# --------------------------------------------------------------------------- #
# Emenda de 2026-08-25 à DEC-039 — os dois críticos que vivem na fronteira com
# o repo irmão do coletor
# --------------------------------------------------------------------------- #
def test_wrapper_rotaciona_o_consolidado_de_cada_coletor() -> None:
    """CRÍTICO 1: `--no-resume` apaga o CHECKPOINT, não o consolidado.

    O consolidado é escrito por `csv_writer.append_rows` em modo `"a"`, e `ensure_header` retorna
    cedo quando o arquivo já existe com conteúdo — **nada o trunca**. Na 2ª semana as duas safras
    coexistem, `split_by_state` (modo `"w"`) propaga as duas para os 27 CSVs por UF, e o desempate
    de `montar_snapshot` (menor `hash_campos_raspados`) mantém a linha VELHA de quem mudou: o S4
    lê "parado" exatamente em quem se mexeu, e `sumiu_recente` nunca dispara.
    """
    executaveis = "\n".join(_linhas_executaveis(WRAPPER))

    assert "rotacionar_consolidado()" in executaveis, "a função de rotação sumiu do wrapper"
    for consolidado in ("TotalPass/unidades_totalpass.csv", "Wellhub/unidades_wellhub.csv"):
        assert consolidado in executaveis, f"o consolidado {consolidado} não é rotacionado"
    # ROTACIONA, não apaga: o histórico tem de continuar no disco. (`--rm` do `docker run` é
    # outra coisa — o que não pode existir é um comando `rm` de verdade.)
    assert 'mv "$arq" "$destino"' in executaveis
    apagam = [
        linha
        for linha in _linhas_executaveis(WRAPPER)
        if linha.lstrip().split(" ")[0] in {"rm", "unlink", "truncate"}
    ]
    assert apagam == [], f"o wrapper APAGA arquivo; a decisão foi rotacionar: {apagam}"
    # Sufixo sem `.csv`: nenhum glob de curadoria ou de `split_by_state` pode voltar a casá-lo.
    assert "${arq%.csv}.${TS}.bak" in executaveis


def test_rotacao_nao_roda_em_modo_seco_nem_com_coleta_pulada() -> None:
    """Rotacionar sem coletar destruiria justamente o feed que se quer reaproveitar.

    As duas chamadas têm de estar DENTRO do ramo `else` do guard de `DRY_RUN`/`PULAR_COLETA`.
    """
    linhas = _linhas_executaveis(WRAPPER)
    guard = next(
        i
        for i, linha in enumerate(linhas)
        if 'if [ "$DRY_RUN" = "1" ] || [ "$PULAR_COLETA"' in linha
    )
    senao = next(i for i, linha in enumerate(linhas) if i > guard and linha.strip() == "else")
    fim = next(i for i, linha in enumerate(linhas) if i > senao and linha.strip() == "fi")
    ramo_de_coleta = "\n".join(linhas[senao:fim])

    chamadas = [
        i for i, linha in enumerate(linhas) if linha.strip().startswith('rotacionar_consolidado "')
    ]
    assert len(chamadas) == 2, "esperadas duas chamadas de rotação (uma por coletor)"
    assert all(senao < i < fim for i in chamadas), "rotação fora do ramo de coleta"
    assert "coletor_totalpass" in ramo_de_coleta and "coletor_wellhub" in ramo_de_coleta


def test_os_dois_coletores_rodam_com_no_resume() -> None:
    """CRÍTICO 2a: sem `--no-resume`, o TotalPass NUNCA recoleta — e sai com SUCESSO.

    `TotalPass/pipeline.py` filtra `pending = [s for s in slugs if not
    checkpoint.already_processed(s)]` e retorna cedo com `if not pending`. Com o checkpoint cheio
    (34.982 slugs medidos nesta estação) nada é recoletado — mas o `main()` segue para
    `split_by_state`, que reescreve os 27 CSVs por UF em modo `"w"` com **mtime de agora**. O
    `|| echo "coletor falhou"` do wrapper nunca dispara, porque o coletor não falha.
    """
    executaveis = _linhas_executaveis(WRAPPER)
    for modulo in ("TotalPass.coletor_totalpass", "Wellhub.coletor_wellhub"):
        invocacao = next(linha for linha in executaveis if modulo in linha)
        assert "--no-resume" in invocacao, f"{modulo} roda sem `--no-resume`"


def test_wrapper_passa_o_piso_e_o_teto_das_duas_fontes() -> None:
    """`--max-linhas-totalpass` era código morto: existia na CLI e o wrapper nunca o passava."""
    executaveis = "\n".join(_linhas_executaveis(WRAPPER))
    assert "--max-linhas-totalpass" in executaveis
    assert "MAX_LINHAS_TOTALPASS" in executaveis
    # E o PISO relativo, que a curadoria não tinha: teto pega universo que infla, piso pega
    # coleta que morreu na metade.
    assert "--piso-relativo" in executaveis
    assert 'PISO_RELATIVO="${PISO_RELATIVO:-0.5}"' in executaveis


def test_cabecalho_nao_manda_ler_zero_como_caminho_errado_na_primeira_vez() -> None:
    """Em `DRY_RUN=1` na 1ª instalação, `linhas_snapshot=0` é o ESPERADO por construção.

    A curadoria em modo seco não copia nada, então não há o que o snapshot leia. A instrução
    antiga mandava ler zero como "caminho errado", que é o diagnóstico oposto.
    """
    texto = WRAPPER.read_text(encoding="utf-8")
    assert "PRIMEIRA instalacao" in texto
    assert "regua_idade" in texto, "o modo seco não manda conferir qual régua decidiu a idade"


def test_wrapper_semanal_nao_manda_rodar_a_cadencia_dos_agregadores_por_ele() -> None:
    """O wrapper de DOMINGO é o arquivo copiado para a VPS, e ele mandava pular a curadoria.

    Até 2026-08-25 o cabeçalho dizia que a cadência dos agregadores invocaria "este mesmo script
    com `--fontes totalpass wellhub`". Seguir aquilo pularia a escolha de diretório do WellHub
    (dois universos que diferem por 2-3×) e a guarda de frescor — que são a razão do bloco
    existir.
    """
    texto = WRAPPER_SEMANAL.read_text(encoding="utf-8")
    assert "run_snapshot_agregadores.sh" in texto, "não aponta para o wrapper dos agregadores"
    assert "NAO** PASSA POR AQUI" in texto or "**NAO** PASSA POR AQUI" in texto
    # E o layout documentado é o de DUAS chaves, não o de uma.
    assert "semana=AAAA-SS/fonte=<fonte>/parte-*.parquet" in texto
    assert "snapshots_concorrentes_v4" in texto, "não avisa do risco da imagem antiga"


def test_wrapper_agregadores_le_do_destino_curado_nao_do_clone() -> None:
    """O snapshot lê `HOST_AGREGADORES` (curado), não `HOST_GYMSCRAPING` (o clone cru).

    Ler o clone direto puliria a curadoria inteira — e com ela a escolha de diretório (D3) e a
    guarda de frescor (D4), que são a razão de o bloco existir.
    """
    executaveis = _linhas_executaveis(WRAPPER)
    montagens_snapshot = [linha for linha in executaveis if "/app/concorrentes:ro" in linha]
    assert montagens_snapshot, "o passo do snapshot não monta o destino curado como :ro"
    assert all("HOST_AGREGADORES" in linha for linha in montagens_snapshot)


def test_healthcheck_expoe_subcomando_agregadores() -> None:
    """Função + `case` + string de uso: o trio que costuma ser atualizado pela metade."""
    texto = HEALTHCHECK.read_text(encoding="utf-8")
    assert "check_agregadores()" in texto, "a função do subcomando não existe"
    assert "agregadores) check_agregadores ;;" in texto, "o `case` não roteia o subcomando"
    assert "{containers|host|authelia|coleta|agregadores|test}" in texto, (
        "a string de uso não lista o subcomando: ele existiria sem ser descobrível"
    )


def test_healthcheck_agregadores_tem_limiar_configuravel() -> None:
    """O limiar é de PRODUTO (cadência do cron), não de código: tem de sair por env."""
    texto = HEALTHCHECK.read_text(encoding="utf-8")
    assert 'AGREGADOR_MAX_DIAS="${MONITOR_AGREGADOR_MAX_DIAS:-9}"' in texto
    assert 'SNAPSHOTS_DIR="${MONITOR_SNAPSHOTS_DIR:-' in texto
    assert "AGREGADORES=(wellhub totalpass)" in texto
    # Uma chave de estado POR FONTE: a falha de um agregador não pode silenciar o alerta do outro.
    assert 'report "agregador_$f" FAIL' in texto
    assert 'report "agregador_$f" OK ""' in texto


def test_healthcheck_agregadores_falha_quando_nunca_existiu() -> None:
    """Partição que NUNCA existiu é o estado real hoje — e é o que mais precisa alertar.

    Um check que só medisse idade ficaria eternamente verde enquanto o cron não fosse agendado:
    sem partição, não há idade, e "sem alarme" leria como "está tudo bem".
    """
    texto = HEALTHCHECK.read_text(encoding="utf-8")
    assert "NUNCA foi fotografado" in texto


def test_healthcheck_agregadores_olha_por_fonte_nao_a_serie_inteira() -> None:
    """`find ... -name "fonte=$f"`: o cron de domingo escreve toda semana e mascararia o da terça."""
    texto = HEALTHCHECK.read_text(encoding="utf-8")
    assert '-name "fonte=$f"' in texto
    assert "-mindepth 2 -maxdepth 2" in texto


def test_healthcheck_deriva_a_idade_da_chave_semana_e_nao_do_mtime() -> None:
    """M1: o mtime do diretório `fonte=` MENTE, e mente onde dói.

    O passo 2 **obrigatório** da ordem de aplicação roda `--migrar-layout`, que **cria** a folha
    `fonte=` com mtime de agora. Medido sobre cópia da partição viva: dado de `2026-08-05`
    (20 dias) reportado como `0d` — com o limiar herdado de 45, o `FAIL` atrasaria ~20 dias. E a
    distância é
    arbitrária para qualquer `rsync`/restore do volume.
    """
    texto = HEALTHCHECK.read_text(encoding="utf-8")

    assert "epoch_da_semana_iso()" in texto, "a conversão ISO-week sumiu"
    # `date -d` não parseia data ISO-week em nenhum coreutils: a conversão é pela definição da
    # ISO-8601 (4 de janeiro cai sempre na semana 1).
    assert "${ano}-01-04" in texto
    # `10#`: sem isso, `08` e `09` seriam lidos como octal e a aritmética falharia em 2 semanas
    # por ano — o mesmo tipo de armadilha já vista na guarda de dia do mês da linha de crontab.
    assert "10#${BASH_REMATCH[2]}" in texto
    # Fallback declarado, e ele DIZ que é fallback no texto do alerta.
    assert "mtime (fallback" in texto
    assert "régua ${regua}" in texto


def test_healthcheck_ordena_particoes_pela_chave_semana() -> None:
    """A "última partição" tem de ser a de maior `semana=`, não a de mtime mais novo.

    O zero-padding da chave ISO torna a ordem lexicográfica igual à cronológica.
    """
    texto = HEALTHCHECK.read_text(encoding="utf-8")
    assert "s#.*/semana=\\([0-9]\\{4\\}-[0-9]\\{2\\}\\)/fonte=.*#\\1#p" in texto


# --------------------------------------------------------------------------- #
# Emenda de 2026-08-26 à DEC-039 — a cadência é SEMANAL, e as três correções da
# rede de segurança (log antes do lock, limiar 9, check na quinta) só fecham o
# buraco juntas
# --------------------------------------------------------------------------- #
def test_crontab_do_cabecalho_e_semanal_sem_guarda_de_dia_do_mes() -> None:
    """A guarda `[ "$(date +\\%d)" -le 07 ]` existia só para emular "1ª terça do mês".

    Ela some com a cadência semanal — e com ela some o `%` escapado, que era exigência do crontab
    e uma armadilha de cópia por si só. O operador instala a linha COPIANDO do cabeçalho: se ela
    envelhecer aqui, ele agenda a grade errada e ninguém percebe.
    """
    texto = WRAPPER.read_text(encoding="utf-8")

    assert "0 2 * * 2 /opt/motor-expansao-infra/run_snapshot_agregadores.sh" in texto, (
        "a linha de crontab semanal não está no cabeçalho"
    )
    assert "date +\\%d" not in texto, "a guarda de dia do mês sobreviveu à cadência semanal"
    assert "primeira terca do mes" not in texto.lower()


def test_wrapper_agregadores_loga_antes_do_flock() -> None:
    """Uma rodada TRAVADA segura o lock, e toda semana seguinte sairia `exit 0` SEM LOG.

    Com o `exec > >(tee -a "$LOG")` depois do `flock`, a colisão não deixava arquivo nenhum em
    `$LOG_DIR`: o único destino do aviso era o stdout do cron (mail do root, que pode nem estar
    configurado), e o symlink `_latest.log` continuava apontando para a última rodada COMPLETA. Sob
    cadência mensal isso custava caro uma vez por ano; sob a semanal, toda semana.
    """
    executaveis = _linhas_executaveis(WRAPPER)
    i_tee = next(i for i, linha in enumerate(executaveis) if "tee -a" in linha)
    i_flock = next(i for i, linha in enumerate(executaveis) if linha.startswith("flock -n 9"))
    assert i_tee < i_flock, (
        "o `tee` do log começa DEPOIS do `flock`: uma colisão de lock pularia em silêncio"
    )
    # E o `mkdir -p "$LOG_DIR"` tem de vir antes do `tee`, senão o redirecionamento morre.
    i_mkdir = next(i for i, linha in enumerate(executaveis) if 'mkdir -p "$LOG_DIR"' in linha)
    assert i_mkdir < i_tee


def test_wrapper_e_runbook_citam_a_mesma_retencao() -> None:
    """Trava contra a INVERSÃO DE SENTIDO: o checklist mandava NÃO agendar se o DRY_RUN desse 26.

    O `26` passou a ser o valor CERTO. Se a constante mudar e estes dois textos não mudarem junto,
    o próprio runbook barra a imagem correta — e o operador (que aplica na VPS comando a comando)
    não tem como saber que a instrução envelheceu.
    """
    from motor_expansao.vulnerabilidade import contrato as c

    esperado = str(c.RETENCAO_SEMANAS)
    wrapper = WRAPPER.read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "infra_producao.md").read_text(encoding="utf-8")

    assert f"retencao_semanas={esperado}" in wrapper, (
        "o echo do DRY-RUN do wrapper não cita a retenção vigente"
    )
    assert f"tem de ser {esperado}" in wrapper, (
        "o checklist do cabeçalho não manda conferir a retenção vigente"
    )
    assert f"`{esperado}`" in runbook and "retencao_semanas" in runbook, (
        "o checklist do runbook não cita a retenção vigente"
    )
    # E nenhum dos dois pode continuar mandando NÃO agendar por causa do valor certo.
    assert f"`{esperado}` é o valor antigo" not in runbook
    assert f"Com {esperado} (valor antigo)" not in wrapper


def test_healthcheck_limiar_separa_rodada_da_semana_de_uma_rodada_perdida() -> None:
    """O limiar tem de separar 3 dias (rodada da terça) de 10 (rodada perdida).

    A régua real do `healthcheck_vps.sh` deriva a idade da SEGUNDA da semana ISO da partição
    (`epoch_da_semana_iso`) e compara `idade_dias > AGREGADOR_MAX_DIAS`. Com o check na quinta
    12:00 UTC: partição da própria semana -> 3 dias; uma rodada perdida -> 10. A faixa que separa
    é [3, 9] inteira, e 9 é o TETO — o mais tolerante a uma rodada que escorregue dentro da semana.
    O `45` herdado deixava passar até 6 rodadas perdidas antes do primeiro FAIL.
    """
    import re

    texto = HEALTHCHECK.read_text(encoding="utf-8")
    achado = re.search(r'AGREGADOR_MAX_DIAS="\$\{MONITOR_AGREGADOR_MAX_DIAS:-(\d+)\}"', texto)
    assert achado is not None, "o default do limiar sumiu do healthcheck"
    limiar = int(achado.group(1))

    idade_com_a_rodada_da_semana = 3
    idade_com_uma_rodada_perdida = 10
    assert idade_com_a_rodada_da_semana <= limiar, "o limiar acusaria FAIL na semana em que rodou"
    assert idade_com_uma_rodada_perdida > limiar, "o limiar não acusa uma rodada perdida"
    assert limiar == 9, "9 é o teto da faixa que separa; mudar exige nova decisão"


def test_healthcheck_dos_agregadores_e_agendado_na_quinta() -> None:
    """`0 12 * * 4`: alerta 2 dias depois da terça e deixa sexta livre para a retentativa.

    Com o check na segunda (`0 12 * * 1`, a grade da premissa mensal), a falha da terça só seria
    vista na segunda seguinte — 6 dias depois, já fora da semana ISO em que a observação podia ser
    salva.
    """
    runbook = (ROOT / "docs" / "infra_producao.md").read_text(encoding="utf-8")
    assert "0 12 * * 4" in runbook, "o runbook não agenda o healthcheck dos agregadores na quinta"
    assert "0 12 * * 1" not in runbook, "a grade de segunda (premissa mensal) sobreviveu"
