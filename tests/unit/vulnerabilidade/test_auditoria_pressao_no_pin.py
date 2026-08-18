"""BLK-MA-18: a conta por trás da pressão viaja até o pin.

**O defeito é de LEITURA, não de cálculo** — e foi achado por revisão de Vinicius em 2026-08-15, ao
olhar uma academia isolada marcando `40,4`: parecia muito para a vizinhança que o mapa mostrava.

A desconfiança estava calibrada. A saturação `100·(1 − 1/(1+oferta))`, herdada da camada de mercado
(`enriquecimento_espacial_hexagonos.py`, fórmula idêntica), gasta **metade da escala numa única
unidade equivalente**:

    oferta 0,25  ->  20,0     (uma academia a 1,5 km)
    oferta 0,68  ->  40,4     (o caso real: 3 independentes a ~1,1 km)
    oferta 1,00  ->  50,0     (uma unidade de rede colada na porta)
    oferta 9,00  ->  90,0

Ou seja: `40,4` significa **0,68 concorrentes efetivos**, e não "40% de pressão" — que é a leitura
que um número de 0 a 100 num pin praticamente convida a fazer. A régua não muda (trocá-la quebraria
a comparabilidade com `pressao_concorrencial_score_2km`, que é a razão de ela ter sido copiada); o
que muda é o número deixar de ser inverificável: com a contagem ao lado, o operador confere olhando
o próprio mapa.

Estes testes protegem a cadeia inteira do dado — do frame de pressão até a coluna do artefato.
"""

from __future__ import annotations

import pandas as pd
import pytest

from motor_expansao.vulnerabilidade import contrato as c
from motor_expansao.vulnerabilidade.alvos_nomeados import montar_alvos_nomeados

_HEX = "87a8100acffffff"


def _score(chaves: list[str], *, com_pressao: bool = True) -> pd.DataFrame:
    linhas = []
    for k in chaves:
        linhas.append(
            {
                "chave_snapshot": k,
                "fonte": "wellhub",
                "rede": c.CATEGORIA_INDEPENDENTE,
                "hex_id_res7": _HEX,
                "status_churn": "novo",
                "nota_wellhub": None,
                "qtd_avaliacoes_wellhub": None,
                "v1": 0.5,
                "v3": None,
                "v4": None,
                "v6": 0.404 if com_pressao else None,
                "pressao_competitiva": 40.4 if com_pressao else None,
                "pressao_grao": c.PRESSAO_GRAO_ACADEMIA if com_pressao else None,
                "universo_oferta": c.UNIVERSO_OFERTA_COM_INDEPENDENTES if com_pressao else None,
                "sinais_disponiveis": "s1,s6" if com_pressao else "s1",
                "n_sinais_disponiveis": 2 if com_pressao else 1,
                "score_vulnerabilidade": 46.2 if com_pressao else 50.0,
                "score_vulnerabilidade_ordenavel": None,
                "flag_serie_imatura": True,
                "flag_staleness_interpretavel": False,
                "flag_score_provisorio": not com_pressao,
                "n_agregadores_no_hex": 1,
                "fontes_presentes_no_hex": "wellhub",
                "semana_ultima_observacao": "2026-33",
                "snapshot_date_ultimo": "2026-08-14",
                "versao_contrato": c.VERSAO_CONTRATO_SCORE,
            }
        )
    df = pd.DataFrame(linhas, columns=list(c.CONTRATO_COLUNAS_SCORE.keys()))
    for col, dtype in c.CONTRATO_COLUNAS_SCORE.items():
        df[col] = df[col].astype(dtype)
    return df


def _coords(chaves: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "fonte": ["wellhub"] * len(chaves),
            "chave_snapshot": chaves,
            "nome": [f"Academia {k}" for k in chaves],
            "lat": [-23.72] * len(chaves),
            "lng": [-46.75] * len(chaves),
            "rede": [c.CATEGORIA_INDEPENDENTE] * len(chaves),
        }
    )


def _pressao(
    chaves: list[str],
    *,
    n: int = 3,
    n_ind: int = 3,
    n_feed: int = 0,
    oferta: float = 0.678,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "fonte": ["wellhub"] * len(chaves),
            "chave_snapshot": chaves,
            "pressao_competitiva": [40.4] * len(chaves),
            "v6": [0.404] * len(chaves),
            "oferta_ponderada": [oferta] * len(chaves),
            "n_concorrentes_no_raio": [n] * len(chaves),
            "dist_concorrente_mais_proximo_m": [1051.0] * len(chaves),
            "oferta_independentes": [oferta] * len(chaves),
            "n_independentes_no_raio": [n_ind] * len(chaves),
            "oferta_cadeias_do_feed": [0.0] * len(chaves),
            "n_cadeias_do_feed_no_raio": [n_feed] * len(chaves),
            "kernel_pressao": [c.PRESSAO_KERNEL_DEFAULT] * len(chaves),
            "raio_pressao_m": [c.PRESSAO_RAIO_M] * len(chaves),
            "universo_oferta": [c.UNIVERSO_OFERTA_COM_INDEPENDENTES] * len(chaves),
            "versao_contrato": [c.VERSAO_CONTRATO_PRESSAO] * len(chaves),
        }
    )


def test_a_conta_chega_ao_artefato() -> None:
    """As quatro colunas de auditoria acompanham a pressão até a linha que a tela lê."""
    chaves = ["a", "b"]
    out = montar_alvos_nomeados(_score(chaves), _coords(chaves), _pressao(chaves))
    linha = out.iloc[0]
    assert int(linha["n_concorrentes_no_raio"]) == 3
    assert int(linha["n_independentes_no_raio"]) == 3
    assert float(linha["oferta_ponderada"]) == pytest.approx(0.678)
    assert float(linha["dist_concorrente_mais_proximo_m"]) == pytest.approx(1051.0)


def test_sem_o_frame_de_pressao_a_auditoria_e_NULA_nunca_zero() -> None:
    """`0 concorrentes no raio` afirma território livre; "não medi" não afirma nada.

    É a mesma regra que vale para o `v6` sem insumo, e ela importa mais aqui: o zero apareceria na
    tela como um fato sobre o entorno, do lado de um número de pressão que ninguém calculou.
    """
    chaves = ["a"]
    out = montar_alvos_nomeados(_score(chaves), _coords(chaves), None)
    for coluna in (
        "n_concorrentes_no_raio",
        "n_independentes_no_raio",
        "n_cadeias_do_feed_no_raio",
        "oferta_ponderada",
        "dist_concorrente_mais_proximo_m",
    ):
        assert out[coluna].isna().all(), f"`{coluna}` deveria ser nula sem o frame de pressao"


def test_linha_sem_pressao_nao_carrega_contagem() -> None:
    """Auditoria sem o número que ela audita seria pior que nada.

    O frame de pressão pode até trazer a linha (ele cobre um universo maior), mas se o score não
    tem `pressao_competitiva` para aquela academia, exibir "3 concorrentes no raio" ao lado de um
    campo de pressão vazio convida a leitura de que a pressão é zero.
    """
    chaves = ["a"]
    out = montar_alvos_nomeados(_score(chaves, com_pressao=False), _coords(chaves), _pressao(chaves))
    assert out["pressao_competitiva"].isna().all()
    assert out["n_concorrentes_no_raio"].isna().all()
    assert out["oferta_ponderada"].isna().all()


def test_a_contagem_crua_e_a_efetiva_sao_grandezas_DIFERENTES() -> None:
    """O ponto todo do bloco: a diferença entre as duas É a distância.

    3 concorrentes que valem 0,68 efetivos estão longe; 3 que valem 2,9 estão colados. Sem as duas,
    o operador não distingue "pouca gente" de "gente longe" — que é a distinção que o decaimento
    existe para fazer e que o número saturado apaga.
    """
    chaves = ["a"]
    out = montar_alvos_nomeados(_score(chaves), _coords(chaves), _pressao(chaves))
    n = int(out["n_concorrentes_no_raio"].iloc[0])
    efetivos = float(out["oferta_ponderada"].iloc[0])
    assert efetivos < n, "oferta efetiva nao pode superar a contagem crua com kernel em [0, 1]"
    assert efetivos == pytest.approx(0.678)


def test_frame_de_pressao_incompleto_levanta_em_vez_de_silenciar() -> None:
    """Um frame sem as colunas de auditoria é erro de programação, não caso de uso."""
    chaves = ["a"]
    incompleto = _pressao(chaves).drop(columns=["oferta_ponderada"])
    with pytest.raises(AssertionError, match="auditoria"):
        montar_alvos_nomeados(_score(chaves), _coords(chaves), incompleto)


def test_o_contrato_declara_as_colunas_de_auditoria() -> None:
    """Quatro no BLK-MA-18; a quinta entrou no BLK-MA-17 (DEC-034), com o bump que ela exige."""
    for coluna in (
        "n_concorrentes_no_raio",
        "n_independentes_no_raio",
        "n_cadeias_do_feed_no_raio",
        "oferta_ponderada",
        "dist_concorrente_mais_proximo_m",
    ):
        assert coluna in c.CONTRATO_COLUNAS_ALVOS_NOMEADOS
    assert c.VERSAO_CONTRATO_ALVOS_NOMEADOS == "alvos_ma_nomeados_v5"


def test_a_lacuna_de_pin_e_DECLARADA_na_linha_que_a_tela_le() -> None:
    """A razão de `n_cadeias_do_feed_no_raio` existir (BLK-MA-17 / DEC-034).

    A auditoria do BLK-MA-18 promete conferência visual — "conta os pins e o número fecha". As
    unidades de REDE vindas do agregador entram em `n_concorrentes_no_raio` e **não têm pin
    desenhado** (a superfície é a metade 1, fora deste ciclo). Sem esta coluna, a contagem
    simplesmente não fecharia no mapa e a explicação não estaria em lugar nenhum.
    """
    chaves = ["a"]
    out = montar_alvos_nomeados(
        _score(chaves), _coords(chaves), _pressao(chaves, n=5, n_ind=3, n_feed=2)
    )
    linha = out.iloc[0]
    assert int(linha["n_concorrentes_no_raio"]) == 5
    assert int(linha["n_cadeias_do_feed_no_raio"]) == 2, (
        "a coluna tem de declarar quantos dos `n_conc` nao estao desenhados no mapa"
    )
