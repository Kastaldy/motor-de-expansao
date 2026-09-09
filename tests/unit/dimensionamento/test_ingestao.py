"""Testes das funcoes puras de ingestao (sem rede; mock do cliente)."""

from __future__ import annotations

import pandas as pd
import pytest

from motor_expansao.dimensionamento.ingestao import (
    auditar_historico,
    concatenar_e_dedup,
    gerar_janelas_mensais,
    iter_janelas,
    unidades_ausentes_do_view,
)


def test_gerar_janelas_mensais_basico():
    janelas = gerar_janelas_mensais("2022-04-01", "2022-06-15")
    assert janelas == [
        ("2022-04-01", "2022-04-30"),
        ("2022-05-01", "2022-05-31"),
        ("2022-06-01", "2022-06-15"),
    ]


def test_gerar_janelas_respeita_dia_inicial():
    janelas = gerar_janelas_mensais("2022-04-15", "2022-05-10")
    assert janelas[0] == ("2022-04-15", "2022-04-30")
    assert janelas[1] == ("2022-05-01", "2022-05-10")


def test_gerar_janelas_mesmo_mes():
    assert gerar_janelas_mensais("2022-04-05", "2022-04-20") == [
        ("2022-04-05", "2022-04-20")
    ]


def test_gerar_janelas_inicio_apos_fim():
    assert gerar_janelas_mensais("2022-06-01", "2022-04-01") == []


def test_gerar_janelas_atravessa_ano():
    janelas = gerar_janelas_mensais("2022-12-01", "2023-01-31")
    assert janelas == [
        ("2022-12-01", "2022-12-31"),
        ("2023-01-01", "2023-01-31"),
    ]


class _FakeCliente:
    def __init__(self, por_janela):
        self.por_janela = por_janela
        self.chamadas = []

    def get_historico_dash_view(self, di, dfim, force_refresh=False):
        self.chamadas.append((di, dfim, force_refresh))
        return self.por_janela.get((di, dfim), [])

    def get_historico_dash(self, di, dfim, force_refresh=False):
        self.chamadas.append(("dash", di, dfim, force_refresh))
        return self.por_janela.get((di, dfim), [])


def test_iter_janelas_chama_view_por_janela():
    cli = _FakeCliente(
        {
            ("2022-04-01", "2022-04-30"): [{"unidade": "A", "data": "2022-04-01"}],
            ("2022-05-01", "2022-05-31"): [{"unidade": "A", "data": "2022-05-01"}],
        }
    )
    janelas = [("2022-04-01", "2022-04-30"), ("2022-05-01", "2022-05-31")]
    blocos = list(iter_janelas(cli, janelas, force_refresh=True))
    assert len(blocos) == 2
    assert all(c[2] is True for c in cli.chamadas)


def test_concatenar_e_dedup_remove_duplicatas():
    blocos = [
        [{"unidade": "A", "data": "2022-04-01", "faturamento": 1}],
        [{"unidade": "A", "data": "2022-04-01", "faturamento": 99}],  # dup -> keep last
        [{"unidade": "B", "data": "2022-04-01", "faturamento": 5}],
    ]
    df = concatenar_e_dedup(blocos)
    assert len(df) == 2
    fat_a = df.loc[df["unidade"] == "A", "faturamento"].iloc[0]
    assert fat_a == 99


def test_concatenar_vazio():
    assert concatenar_e_dedup([[], []]).empty


def test_auditar_historico():
    df = pd.DataFrame(
        {
            "unidade": ["A", "A", "B"],
            "data": ["01/04/2022", "01/05/2022", "01/04/2022"],
            "faturamento": [1.0, 2.0, 3.0],
            "pagantes": [10, 11, 5],
            "ticket_medio": [100, 100, 90],
            "cancelados": [1, 2, 0],
            "churn": [0.05, 0.06, 0.04],
            "ativos_total": [10, 11, 5],
            "inadimplente": [0, 1, 0],
            "uf": ["SP", "SP", "RJ"],
            "inauguracao": ["2020-01-01", "2020-01-01", None],
        }
    )
    aud = auditar_historico(df)
    assert aud["n_linhas"] == 3
    assert aud["n_unidades"] == 2
    assert aud["data_min"] == "2022-04-01"
    assert aud["data_max"] == "2022-05-01"
    assert aud["colunas_minimas_ausentes"] == []
    # A tem inauguracao, B nao -> 50%
    assert aud["tem_pct_inauguracao"] == 50.0


# ---------------------------------------------------------------------------
# Uniao view + dash (universo de unidades)
# ---------------------------------------------------------------------------


def _linhas(unidade, datas, pagantes=100):
    return [
        {"unidade": unidade, "data": d, "pagantes": pagantes, "faturamento": 1000.0}
        for d in datas
    ]


def _dash_de_exemplo():
    """Base pequena com os tres regimes que importam.

    `NO VIEW` esta nos dois lados; `NOVA - MT` so' no dash e operando; `ZERADA` so' no
    dash e sem pagantes ha meses (o molde do BELA CINTRA real).
    """
    dash = pd.DataFrame(
        _linhas("NO VIEW - RJ", ["01/08/2026", "08/09/2026"])
        + _linhas("NOVA - MT", ["25/02/2026", "08/09/2026"])
        + _linhas("ZERADA", ["01/03/2025"], pagantes=50)
        + _linhas("ZERADA", ["08/09/2026"], pagantes=0)
    )
    view = pd.DataFrame(_linhas("NO VIEW - RJ", ["01/08/2026", "08/09/2026"]))
    return view, dash


def test_uniao_adota_unidade_que_o_view_nao_tem():
    view, dash = _dash_de_exemplo()
    fora = unidades_ausentes_do_view(view, dash)
    assert set(fora["unidade"]) == {"NOVA - MT"}


def test_uniao_nao_adota_unidade_zerada():
    """Operar UM dia em 2025 nao qualifica: e' o caso BELA CINTRA.

    Sem a janela final, a regra "teve pagantes alguma vez" adotaria uma unidade morta e
    ela entraria na carteira com zeros, puxando toda media ponderada da aba para baixo.
    """
    view, dash = _dash_de_exemplo()
    assert "ZERADA" not in set(unidades_ausentes_do_view(view, dash)["unidade"])


def test_uniao_nao_duplica_quem_ja_esta_no_view():
    view, dash = _dash_de_exemplo()
    assert "NO VIEW - RJ" not in set(unidades_ausentes_do_view(view, dash)["unidade"])


def test_uniao_deriva_uf_do_sufixo_e_deixa_master_vazio():
    view, dash = _dash_de_exemplo()
    fora = unidades_ausentes_do_view(view, dash)
    assert set(fora["uf"]) == {"MT"}
    # `master` da Growth e' sigla de REGIAO; quem nomeia o franqueado e' o cadastro.
    assert set(fora["master"]) == {""}


def test_uniao_deriva_inauguracao_da_primeira_data_da_serie():
    view, dash = _dash_de_exemplo()
    fora = unidades_ausentes_do_view(view, dash)
    assert set(fora["inauguracao"]) == {"25/02/2026"}


def test_uniao_nao_inventa_inauguracao_de_serie_truncada():
    """Serie que comeca junto com a base foi CORTADA pelo recorte, nao inaugurada ali.

    Sem esta guarda, toda unidade antiga adotada receberia como "inauguracao" o primeiro
    dia do historico -- um numero plausivel e errado, que alimentaria coorte, maturidade
    e o gate de "inaugurada dentro da competencia".
    """
    dash = pd.DataFrame(_linhas("ANTIGA - SP", ["01/04/2022", "08/09/2026"]))
    fora = unidades_ausentes_do_view(pd.DataFrame(), dash)
    assert set(fora["unidade"]) == {"ANTIGA - SP"}
    assert set(fora["inauguracao"]) == {""}


def test_uniao_com_dash_vazio_nao_estoura():
    view, _ = _dash_de_exemplo()
    assert unidades_ausentes_do_view(view, pd.DataFrame()).empty


def test_iter_janelas_recusa_endpoint_desconhecido():
    with pytest.raises(ValueError, match="endpoint desconhecido"):
        list(iter_janelas(_FakeCliente({}), [("2026-01-01", "2026-01-31")], endpoint="x"))


def test_iter_janelas_no_dash_chama_o_outro_endpoint():
    cli = _FakeCliente({("2026-01-01", "2026-01-31"): [{"unidade": "A", "data": "01/01/2026"}]})
    list(iter_janelas(cli, [("2026-01-01", "2026-01-31")], endpoint="dash"))
    assert cli.chamadas[0][0] == "dash"
