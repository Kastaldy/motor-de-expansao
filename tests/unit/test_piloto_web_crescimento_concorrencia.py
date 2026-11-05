"""Card "Crescimento da concorrência" da Visão Executiva, pela ROTA (`/api/rede/inteligencia`).

O defeito de origem (diagnóstico de 04/11/2026): o card lia só o pacote garimpado da VPS em 15/09 e
ficou oito domingos parado em 06/09, enquanto o lote de domingo já copiava o histórico semanal para
o staging (passo 2.1, PR #393) sem que ninguém o lesse. Aqui se trava a LIGAÇÃO: a rota lê o
histórico do staging, relê quando o arquivo muda (sem restart), não segue o filtro da carteira
(nacional de propósito) e, sem o histórico, diz de que data são as unidades.

READ-ONLY sobre o M1.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402

from motor_expansao.dashboard import movimentacao_concorrencia as mov  # noqa: E402
from motor_expansao.dashboard import saldo_rede  # noqa: E402
from tests.unit.test_piloto_web_rede import rede  # noqa: E402,F401  (fixture)


def _historico(staging: Path, linhas: list[tuple[str, str, int]]) -> Path:
    """O CSV no formato REAL do coletor (CRLF, sem BOM), onde o passo 2.1 o deixa."""
    caminho = staging / saldo_rede.ARQUIVO_STAGING
    corpo = "data_execucao;rede;unidades;data_coleta\r\n" + "".join(
        f"{d};{r};{n};{d}\r\n" for d, r, n in linhas
    )
    caminho.write_bytes(corpo.encode("utf-8"))
    return caminho


def _pacote(staging: Path) -> None:
    """O pacote de setembro como está em produção: eventos e a contagem de 06/09."""
    eventos = pd.DataFrame(
        [
            {"fonte": "cadastro", "tipo": "abertura", "confianca": "alta", "rede": "pratique",
             "nome": "Pratique X", "lat": -23.0, "lng": -46.0, "de": "2026-08-02", "ate": "2026-09-06"},
            {"fonte": "wellhub", "tipo": "entrou_agregador", "confianca": "alta", "rede": None,
             "nome": "Academia Y", "lat": -23.1, "lng": -46.1, "de": "2026-08-31", "ate": "2026-09-12"},
        ]
    )
    eventos.to_parquet(staging / mov.ARQUIVO_STAGING)
    pd.DataFrame(
        {"rede": ["pratique", "selfit"], "unidades": [184, 231], "data": ["2026-09-06", "2026-09-06"]}
    ).to_parquet(staging / mov.ARQUIVO_CONTAGEM_STAGING)


def _semanas(*datas: str, selfit: int = 231, velocity: int = 130) -> list[tuple[str, str, int]]:
    """Domingos com 30 redes estáveis (a proporção do caso real), a Pratique, a Selfit e um estúdio."""
    linhas: list[tuple[str, str, int]] = []
    for d in datas:
        linhas += [(d, f"rede_{i}", 40) for i in range(30)]
        linhas += [(d, "pratique", 190), (d, "selfit", selfit), (d, "velocity", velocity)]
    return linhas


def test_card_le_a_contagem_semanal_do_staging(rede: Path) -> None:  # noqa: F811
    _pacote(pilot.STAGING_DIR)
    _historico(pilot.STAGING_DIR, _semanas("2026-10-25", "2026-11-01"))

    m = pilot.rede_inteligencia_recorte()["movimentacao"]
    assert (m["contagem_origem"], m["data_contagem"]) == ("semanal", "2026-11-01")
    assert m["contagem"]["data_anterior"] == "2026-10-25"
    linhas = {r["rede"]: r for r in m["redes"]}
    assert (linhas["pratique"]["unidades"], linhas["pratique"]["aberturas"]) == (190, 1)
    assert "velocity" not in linhas, "estúdio boutique fora (DEC-056), também na contagem"
    assert {a["agregador"] for a in m["agregadores"]} == {"wellhub"}


def test_card_rele_o_historico_quando_o_arquivo_muda_sem_restart(rede: Path) -> None:  # noqa: F811
    """O defeito que um `lru_cache` sem chave esconderia: o domingo troca o arquivo, e o restart só
    vem quando o regen publica, então a tela ficaria na semana velha."""
    _pacote(pilot.STAGING_DIR)
    caminho = _historico(pilot.STAGING_DIR, _semanas("2026-10-25", "2026-11-01"))
    assert pilot._rede_movimentacao_redes()["data_contagem"] == "2026-11-01"

    _historico(pilot.STAGING_DIR, _semanas("2026-10-25", "2026-11-01", "2026-11-08"))
    # mtime explicitamente mais novo: duas escritas no mesmo tique do relógio do disco empatariam
    st = caminho.stat()
    os.utime(caminho, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    assert pilot._rede_movimentacao_redes()["data_contagem"] == "2026-11-08"


def test_card_e_nacional_e_nao_segue_o_filtro_da_carteira(rede: Path) -> None:  # noqa: F811
    """Decisão de 05/11/2026: a pergunta é da rede concorrente, não da unidade Ultra do recorte."""
    _pacote(pilot.STAGING_DIR)
    _historico(pilot.STAGING_DIR, _semanas("2026-10-25", "2026-11-01"))
    nacional = pilot.rede_inteligencia_recorte()["movimentacao"]
    assert pilot.rede_inteligencia_recorte(uf="RJ")["movimentacao"] == nacional


def test_sem_historico_cai_para_o_pacote_e_diz(rede: Path) -> None:  # noqa: F811
    _pacote(pilot.STAGING_DIR)
    m = pilot.rede_inteligencia_recorte()["movimentacao"]
    assert (m["contagem_origem"], m["data_contagem"], m["contagem"]["erro"]) == ("pacote", "2026-09-06", "ausente")


def test_historico_ilegivel_nao_derruba_a_rota(rede: Path) -> None:  # noqa: F811
    _pacote(pilot.STAGING_DIR)
    (pilot.STAGING_DIR / saldo_rede.ARQUIVO_STAGING).write_bytes(b"outra;coisa\r\n1;2\r\n")
    m = pilot.rede_inteligencia_recorte()["movimentacao"]
    assert (m["contagem_origem"], m["contagem"]["erro"]) == ("pacote", "ilegivel")


def test_coleta_quebrada_de_uma_rede_segura_so_ela_e_e_dita(rede: Path) -> None:  # noqa: F811
    """A Selfit cai de 231 para 119 com coleta nova: ela fica na última contagem boa, e as outras
    redes andam (julgar a semana inteira prenderia todas por causa de uma)."""
    _pacote(pilot.STAGING_DIR)
    _historico(
        pilot.STAGING_DIR, _semanas("2026-10-25", "2026-11-01") + _semanas("2026-11-08", selfit=119)
    )
    m = pilot.rede_inteligencia_recorte()["movimentacao"]
    assert m["data_contagem"] == "2026-11-08"
    selfit = {r["rede"]: r for r in m["redes"]}["selfit"]
    assert (selfit["unidades"], selfit["variacao_status"], selfit["lido"]) == (231, "segurada", 119)
    assert [s["rede"] for s in m["contagem"]["seguradas"]] == ["selfit"]


def test_a_rota_tira_os_estudios_antes_da_guarda(rede: Path) -> None:  # noqa: F811
    """A mutação que a revisão de 05/11 achou viva: sem `excluir` na chamada da rota, o tombo de um
    estúdio entrava na guarda e no aviso, e nenhum teste falhava (o filtro da tabela escondia)."""
    _pacote(pilot.STAGING_DIR)
    _historico(
        pilot.STAGING_DIR, _semanas("2026-10-25", "2026-11-01") + _semanas("2026-11-08", velocity=10)
    )
    m = pilot.rede_inteligencia_recorte()["movimentacao"]
    assert m["data_contagem"] == "2026-11-08"
    assert m["contagem"]["seguradas"] == [], "o estúdio não entra na guarda do card"


def test_rota_com_domingo_duplicado_e_linha_cortada(rede: Path) -> None:  # noqa: F811
    """O lote que rodou duas vezes no domingo, mais uma linha cortada no meio da cópia: a rota lê
    pela leitura TOLERANTE (a estrita levantaria e o card voltaria ao pacote de setembro) e passa os
    dois descartes para a tela avisar."""
    _pacote(pilot.STAGING_DIR)
    linhas = _semanas("2026-10-25") + _semanas("2026-11-01") + _semanas("2026-11-01")
    corpo = "data_execucao;rede;unidades;data_coleta\r\n" + "".join(f"{d};{r};{n};{d}\r\n" for d, r, n in linhas)
    corpo += "2026-11-0;rede_1;4\r\n"
    (pilot.STAGING_DIR / saldo_rede.ARQUIVO_STAGING).write_bytes(corpo.encode("utf-8"))

    m = pilot.rede_inteligencia_recorte()["movimentacao"]
    assert (m["contagem_origem"], m["data_contagem"]) == ("semanal", "2026-10-25")
    assert m["contagem"]["linhas_sem_data"] == 1
    assert m["contagem"]["recusadas"] == [{"execucao": "2026-11-01", "motivo": "duplicada", "queda_total_pct": None}]
    assert m["contagem"]["execucao_mais_recente"] == "2026-11-01"
