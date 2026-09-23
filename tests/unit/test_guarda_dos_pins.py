"""A guarda dos pins: coerência de chave antes do `mv`, aviso de ops e monitor de idade.

As três peças são uma só e se trancam. A guarda de desenhabilidade que já existia faz o certo ao
barrar artefato ruim — foi ela que salvou os pins bons de 30/08 a 17/09 —, mas o efeito dela é
**invisível**: ela só escrevia num log que ninguém lê, e o mapa serviu dado cada vez mais velho
por três semanas sem que ninguém soubesse. Endurecer a guarda sozinha apenas **congela melhor**.
Por isso, no mesmo ciclo:

  * **coerência de chave** — desenhável não basta. A série já migrou de chave uma vez (DEC-063,
    `v4` -> `v5`) e migrará de novo; um materializador com a função de chave VELHA produz artefato
    CHEIO, com lat/lng e centenas de desenháveis, cuja identidade não existe na série. A guarda de
    desenhabilidade aprova isso sem piscar, porque ela pergunta "tem coordenada?", não "é esta
    academia?";
  * **aviso de ops** nos dois ramos que bloqueiam a promoção — bloquear passa a GRITAR;
  * **monitor de idade** no healthcheck — o relógio que faltava.

**A propriedade que dá sentido à guarda de coerência é a INDEPENDÊNCIA:** ela lê a série com
pyarrow cru (hive), nunca por `ler_snapshots`. Passar pelo mesmo caminho de código que produziu o
artefato faria a guarda herdar o defeito que procura — foi assim que o checkout congelado em 19/08
leu a série de duas chaves declarando `v3`, recebeu `fonte` nula e gravou vazio com `exit 0`.

O teste funcional **extrai e executa** o script embutido no wrapper em vez de reescrevê-lo: uma
cópia aqui passaria mesmo se o wrapper divergisse, que é o defeito que a lição da DEC-044 nomeia
(duas redações da mesma regra se desencontram em silêncio).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "scripts" / "cron" / "run_weekly_90.sh"
HEALTHCHECK = ROOT / "scripts" / "healthcheck_vps.sh"
RUNBOOK = ROOT / "docs" / "infra_producao.md"


def _linhas_executaveis(caminho: Path) -> list[str]:
    """Linhas do script sem os comentários — o que importa medir é sempre o que EXECUTA."""
    texto = caminho.read_text(encoding="utf-8")
    return [linha for linha in texto.splitlines() if not linha.lstrip().startswith("#")]


def _script_da_guarda() -> str:
    """O Python da guarda, RECORTADO do wrapper de produção (nunca uma cópia)."""
    texto = WRAPPER.read_text(encoding="utf-8")
    i = texto.index("MEDIDA=$(docker run")
    j = texto.index("python -c '", i) + len("python -c '")
    k = texto.index("\n' 2>/dev/null | tail -1)", j)
    return texto[j:k]


def _medir(tmp_path: Path, *, novo: Path | str, serie: Path | str) -> tuple[int, int]:
    """Roda o script REAL da guarda e devolve `(desenhaveis, coerencia_pct)`.

    Os caminhos vão ABSOLUTOS. A `tmp_path` deste ambiente é RELATIVA, e com `cwd=tmp_path` um
    caminho relativo passa a resolver DENTRO de si mesmo: o artefato some, a guarda lê `0` e a
    falha se disfarça de "a guarda reprovou" — ou seja, o teste da guarda mediria o próprio
    defeito do teste. Foi o que aconteceu na primeira execução, nos quatro casos de uma vez.
    """
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _script_da_guarda()],
        capture_output=True,
        text=True,
        # Ambiente HERDADO com as duas chaves sobrepostas, nunca um dict de dois itens: no
        # Windows, um `env=` sem `SYSTEMROOT` impede o próprio interpretador de subir, e a
        # falha se disfarçaria de "a guarda não imprimiu nada".
        env={
            **os.environ,
            "PINS_NOVO": str(Path(novo).resolve()),
            "PINS_SERIE": str(Path(serie).resolve()),
        },
        cwd=tmp_path,
        check=False,
    )
    saida = [linha for linha in proc.stdout.splitlines() if linha.strip()]
    assert saida, f"a guarda não imprimiu nada (stderr: {proc.stderr[-400:]})"
    draw, coer = saida[-1].split()
    return int(draw), int(coer)


def _escrever_serie(base: Path, chaves: list[str], *, semana: str = "2026-38") -> None:
    """Série no layout hive de DUAS chaves (`semana=`/`fonte=`), como em produção."""
    folha = base / f"semana={semana}" / "fonte=wellhub"
    folha.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"chave_snapshot": chaves}).to_parquet(folha / "part-0.parquet", index=False)


def _escrever_pins(caminho: Path, chaves: list[str], *, sem_coordenada: int = 0) -> None:
    lat = [(-23.5 if i >= sem_coordenada else None) for i in range(len(chaves))]
    caminho.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"chave_snapshot": chaves, "lat": lat}).to_parquet(caminho, index=False)


# --------------------------------------------------------------------------- #
# A guarda de coerência, EXECUTADA
# --------------------------------------------------------------------------- #
def test_chaves_da_serie_medem_100_por_cento(tmp_path: Path) -> None:
    """O caso normal: os pins da semana vêm da série que acabou de ser fotografada."""
    _escrever_serie(tmp_path / "serie", ["a", "b", "c"])
    _escrever_pins(tmp_path / "pins.parquet", ["a", "b", "c"])
    draw, coer = _medir(tmp_path, novo=tmp_path / "pins.parquet", serie=tmp_path / "serie")
    assert (draw, coer) == (3, 100)


def test_chave_VELHA_derruba_a_coerencia_e_a_desenhabilidade_NAO_ve(tmp_path: Path) -> None:
    """O caso que esta guarda existe para pegar, e que a guarda antiga aprovaria sem piscar.

    Artefato cheio, lat/lng em todas as linhas, bytes de sobra — e identidade que não existe na
    série, porque o materializador rodou com a função de chave anterior à migração (DEC-063).
    """
    _escrever_serie(tmp_path / "serie", ["nova-a", "nova-b", "nova-c"])
    _escrever_pins(tmp_path / "pins.parquet", ["velha-a", "velha-b", "velha-c"])
    draw, coer = _medir(tmp_path, novo=tmp_path / "pins.parquet", serie=tmp_path / "serie")
    assert draw == 3, "a desenhabilidade aprova: é exatamente por isso que ela não basta"
    assert coer == 0, "a coerência de chave tem de reprovar identidade que não está na série"


def test_serie_ILEGIVEL_abstem_em_vez_de_bloquear(tmp_path: Path) -> None:
    """Precedente EXPLÍCITO da DEC-061: série ilegível APROVA e carimba o erro.

    Uma guarda que derruba a promoção quando não consegue medir causa exatamente o dano que existe
    para evitar — pins congelados. A abstenção é `-1`, e o wrapper a deixa passar.
    """
    _escrever_pins(tmp_path / "pins.parquet", ["a", "b"])
    draw, coer = _medir(tmp_path, novo=tmp_path / "pins.parquet", serie=tmp_path / "serie-ausente")
    assert draw == 2
    assert coer == -1, "série ilegível deveria ABSTER, não reprovar"


def test_artefato_ILEGIVEL_continua_bloqueando(tmp_path: Path) -> None:
    """A assimetria é deliberada: sem artefato não há o que promover, e `0` desenháveis barra."""
    _escrever_serie(tmp_path / "serie", ["a"])
    draw, _ = _medir(tmp_path, novo=tmp_path / "nao-existe.parquet", serie=tmp_path / "serie")
    assert draw == 0, "artefato ilegível tem de bloquear a promoção"


def test_pin_sem_coordenada_nao_conta_como_desenhavel(tmp_path: Path) -> None:
    """`lat` nula é academia real sem coordenada (contrato dos nomeados): entra, mas não desenha."""
    _escrever_serie(tmp_path / "serie", ["a", "b", "c", "d"])
    _escrever_pins(tmp_path / "pins.parquet", ["a", "b", "c", "d"], sem_coordenada=3)
    draw, coer = _medir(tmp_path, novo=tmp_path / "pins.parquet", serie=tmp_path / "serie")
    assert draw == 1
    assert coer == 100, "a coerência mede IDENTIDADE, não coordenada"


# --------------------------------------------------------------------------- #
# O que o wrapper promete em TEXTO
# --------------------------------------------------------------------------- #
def test_a_coerencia_entra_na_CONDICAO_de_promocao() -> None:
    """Medir sem decidir seria só mais uma linha de log — o ponto é barrar o `mv`."""
    executaveis = "\n".join(_linhas_executaveis(WRAPPER))
    assert '"${COER:-0}" -ge 50' in executaveis, "a coerência saiu da condição de promoção"
    assert '"${COER:--1}" -lt 0' in executaveis, "a abstenção da DEC-061 sumiu da condição"
    # A guarda tem de decidir ANTES do `mv`, senão ela audita um estrago já feito.
    assert executaveis.index('"${COER:-0}" -ge 50') < executaveis.index("mv -f ")


def test_a_medicao_e_INDEPENDENTE_do_contrato() -> None:
    """A propriedade que dá sentido à guarda: ela não pode usar o caminho que produziu o artefato.

    Com `ler_snapshots`, um materializador que declara contrato velho faria a guarda ler a série
    do MESMO jeito errado e concordar consigo mesma — foi o incidente de 17/09.
    """
    script = _script_da_guarda()
    assert "pyarrow.dataset" in script, "a leitura crua da série sumiu"
    assert 'partitioning="hive"' in script, "sem o layout hive a série de duas chaves não abre"
    assert "ler_snapshots" not in script, (
        "a guarda passou a medir pelo mesmo caminho de código que produziu o artefato"
    )
    assert "motor_expansao" not in script, "a guarda passou a depender do pacote que ela audita"


def test_os_dois_ramos_que_bloqueiam_AVISAM_ops() -> None:
    """O silêncio era a outra metade do incidente: 3 semanas de pins congelados sem alerta."""
    executaveis = _linhas_executaveis(WRAPPER)
    avisos = [linha for linha in executaveis if "_avisar_ops " in linha]
    assert len(avisos) >= 5, "os avisos dos ramos de pin não foram adicionados"
    texto = "\n".join(executaveis)
    assert "os pins M&A NÃO foram promovidos" in texto, "o ramo da guarda continua mudo"
    assert "o materializador de pins M&A falhou" in texto, "o ramo da falha continua mudo"


def test_as_mensagens_novas_dos_pins_sao_ACENTUADAS() -> None:
    """`CLAUDE.md` §2: o bot Telegram é canal de usuário, e acento é o 1º detalhe que se perde."""
    texto = WRAPPER.read_text(encoding="utf-8")
    for palavra in ("desenháveis", "série", "está", "NÃO", "não"):
        assert palavra in texto, f"{palavra!r} perdeu o acento na mensagem de ops"
    assert "�" not in texto, "o arquivo tem caractere de substituição (encoding corrompido)"


def test_o_aviso_dos_pins_NAO_derruba_o_lote() -> None:
    """Aviso é efeito colateral, não etapa: o `_avisar_ops` já engole a própria falha."""
    executaveis = "\n".join(_linhas_executaveis(WRAPPER))
    assert "(o lote segue)" in executaveis
    for linha in _linhas_executaveis(WRAPPER):
        if "_avisar_ops " in linha:
            assert "exit" not in linha, "um aviso passou a poder abortar o lote"


# --------------------------------------------------------------------------- #
# O monitor — o relógio que faltava
# --------------------------------------------------------------------------- #
def test_healthcheck_expoe_subcomando_pins() -> None:
    """Função + `case` + string de uso: o trio que costuma ser atualizado pela metade."""
    texto = HEALTHCHECK.read_text(encoding="utf-8")
    assert "check_pins()" in texto, "a função do subcomando não existe"
    assert "pins) check_pins ;;" in texto, "o `case` não roteia o subcomando"
    assert "|pins|" in texto, "a string de uso não lista o subcomando"


def test_monitor_dos_pins_tem_limiares_configuraveis() -> None:
    """Limiar é de PRODUTO (cadência do lote), não de código: sai por env, como os irmãos."""
    texto = HEALTHCHECK.read_text(encoding="utf-8")
    assert 'PINS_MAX_DIAS="${MONITOR_PINS_MAX_DIAS:-9}"' in texto
    assert 'PINS_MIN_DESENHAVEIS="${MONITOR_PINS_MIN_DESENHAVEIS:-100}"' in texto
    assert 'PINS_PARQUET="${MONITOR_PINS_PARQUET:-' in texto


def test_monitor_dos_pins_falha_quando_NUNCA_existiu() -> None:
    """Sem artefato não há idade, e "sem alarme" leria como "está tudo bem" (molde dos irmãos)."""
    assert "NUNCA foram publicados" in HEALTHCHECK.read_text(encoding="utf-8")


def test_monitor_CEGO_conta_como_falha() -> None:
    """Precedente do `mercado`: não conseguir medir não pode ser lido como saúde."""
    assert "Monitor cego conta como falha" in HEALTHCHECK.read_text(encoding="utf-8")


def test_o_piso_de_desenhaveis_tem_PARIDADE_com_a_guarda_do_wrapper() -> None:
    """Dois números para a mesma régua se desencontram (DEC-044); aqui a paridade é travada."""
    healthcheck = HEALTHCHECK.read_text(encoding="utf-8")
    wrapper = "\n".join(_linhas_executaveis(WRAPPER))
    assert "MONITOR_PINS_MIN_DESENHAVEIS:-100" in healthcheck
    assert '"${DRAW:-0}" -ge 100' in wrapper


def test_o_monitor_declara_POR_QUE_o_mtime_e_confiavel_aqui() -> None:
    """Contraintuitivo contra o irmão `mercado`, onde o mtime MENTE — por isso vai por escrito.

    Lá o arquivo é reescrito toda semana; aqui só o `mv` da promoção o toca, então bloqueio faz o
    arquivo envelhecer — que é precisamente o sinal ausente entre 30/08 e 17/09.
    """
    texto = HEALTHCHECK.read_text(encoding="utf-8")
    assert "mv" in texto and "promoção" in texto
    assert "rsync" in texto, "a ressalva do mtime rejuvenescido por restore não foi declarada"


def test_runbook_agenda_o_monitor_dos_pins() -> None:
    """Monitor não agendado é monitor que não existe."""
    runbook = RUNBOOK.read_text(encoding="utf-8")
    assert "healthcheck_vps.sh pins" in runbook, "o runbook não agenda o monitor dos pins"
    assert "0 12 * * 4  /opt/motor-monitoring/healthcheck_vps.sh pins" in runbook


@pytest.mark.parametrize("proibido", ["ssh ", "scp "])
def test_nenhum_comando_novo_toca_a_VPS_de_fora(proibido: str) -> None:
    """CLAUDE.md §6: o wrapper roda DENTRO da VPS; nada aqui alcança o servidor de outra máquina."""
    script = _script_da_guarda()
    assert proibido not in script
