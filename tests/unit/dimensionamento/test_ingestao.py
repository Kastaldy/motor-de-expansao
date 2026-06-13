"""Testes das funcoes puras de ingestao (sem rede; mock do cliente)."""

from __future__ import annotations

import pandas as pd

from motor_expansao.dimensionamento.ingestao import (
    auditar_historico,
    concatenar_e_dedup,
    gerar_janelas_mensais,
    iter_janelas,
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
