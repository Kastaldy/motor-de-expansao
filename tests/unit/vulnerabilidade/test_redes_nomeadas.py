"""BLK-MA-17 metade 1 / DEC-035: o artefato NOMEADO das unidades de REDE.

O que estes testes protegem, em ordem de gravidade do modo de falha:

  1. **Score vazando para o artefato de redes.** É a decisão central da DEC-035 e a mais fácil de
     desfazer por acidente: um join descuidado no futuro reintroduz `score_vulnerabilidade` em
     silêncio, e o artefato passa a afirmar sobre redes o que S1 e S3 não sabem — a negociação com o
     agregador é centralizada, e o S3 é correlacionado (top 5 = 48,4% das unidades, máx 440 numa
     rede: a Panobianco saindo do WellHub viraria 440 alvos no mesmo dia).
  2. **Universo do sinal 1 afrouxado.** O filtro de exibição é PRÓPRIO. Se alguém o unificar com
     `_filtrar_universo_sinal_1`, as colunas `n_academias_independentes_*` passam a contar redes com
     o nome dizendo o contrário.
  3. **Independente vazando para a lista de redes** (e o inverso: rede na lista de alvos de M&A).
  4. **Precedência de pin.** `tem_pin_proprio` tem de sair da dedup da DEC-034, e nunca ser `True`
     numa linha sem coordenada.
  5. **Ausência afirmada como zero.** Sem pressão, a auditoria e o `pressao_grao` saem NULOS — nunca
     `0` nem a constante, que seriam afirmações.

READ-ONLY sobre o M1.
"""

from __future__ import annotations

import pandas as pd
import pytest

from motor_expansao.vulnerabilidade import contrato as c
from motor_expansao.vulnerabilidade.redes_nomeadas import (
    _assert_schema_redes,
    chaves_com_pin_proprio,
    filtrar_universo_exibicao_redes,
    materializar_redes_nomeadas,
    montar_redes_nomeadas,
)

_LAT, _LNG = -23.5500, -46.6300
_GRAU_LAT_M = 111_320.0


def _norte(metros: float) -> float:
    return _LAT + metros / _GRAU_LAT_M


def _churn(linhas: list[tuple[str, str, str]]) -> pd.DataFrame:
    """`(fonte, chave, rede)` -> frame de churn com as colunas que o artefato consome."""
    n = len(linhas)
    return pd.DataFrame(
        {
            "fonte": [f for f, _, _ in linhas],
            "chave_snapshot": [k for _, k, _ in linhas],
            "rede": [r for _, _, r in linhas],
            "hex_id_res7": ["87a8a0000ffffff"] * n,
            "status_churn": ["presente"] * n,
            "nota_wellhub": [4.5] * n,
            "qtd_avaliacoes_wellhub": [120] * n,
        }
    )


def _coordenadas(linhas: list[tuple[str, str, str, float]]) -> pd.DataFrame:
    """`(fonte, chave, nome, metros ao norte)`."""
    return pd.DataFrame(
        {
            "fonte": [f for f, _, _, _ in linhas],
            "chave_snapshot": [k for _, k, _, _ in linhas],
            "nome": [nome for _, _, nome, _ in linhas],
            "lat": [_norte(m) for _, _, _, m in linhas],
            "lng": [_LNG] * len(linhas),
        }
    )


def _pressao(linhas: list[tuple[str, str, float]]) -> pd.DataFrame:
    """`(fonte, chave, pressao)` -> frame de pressão com auditoria completa."""
    n = len(linhas)
    return pd.DataFrame(
        {
            "fonte": [f for f, _, _ in linhas],
            "chave_snapshot": [k for _, k, _ in linhas],
            "pressao_competitiva": [p for _, _, p in linhas],
            "universo_oferta": [c.UNIVERSO_OFERTA_COM_INDEPENDENTES] * n,
            "n_concorrentes_no_raio": [3] * n,
            "n_independentes_no_raio": [2] * n,
            "n_cadeias_do_feed_no_raio": [1] * n,
            "oferta_ponderada": [0.8] * n,
            "dist_concorrente_mais_proximo_m": [420.0] * n,
        }
    )


# --------------------------------------------------------------------------- #
# 1. A decisão central: FATO SIM, SCORE NÃO                                    #
# --------------------------------------------------------------------------- #
def test_o_artefato_nao_tem_NENHUMA_coluna_de_score() -> None:
    """A trava da DEC-035. `score_*` e `v6` estão proibidos, por decisão medida."""
    out = montar_redes_nomeadas(
        _churn([("wellhub", "a", "bluefit")]),
        _coordenadas([("wellhub", "a", "Bluefit Centro", 0.0)]),
    )
    proibidas = [x for x in out.columns if x.startswith("score_") or x == "v6"]
    assert proibidas == [], f"score vazou para o artefato de redes: {proibidas}"


def test_o_guard_derruba_score_injetado_a_mao() -> None:
    """Não basta não emitir: o guard tem de PEGAR quem injetar depois."""
    out = montar_redes_nomeadas(
        _churn([("wellhub", "a", "bluefit")]),
        _coordenadas([("wellhub", "a", "Bluefit Centro", 0.0)]),
    )
    com_score = out.assign(score_vulnerabilidade=50.0)
    with pytest.raises(AssertionError, match="DEC-035"):
        _assert_schema_redes(com_score)


def test_os_tres_fatos_sem_peso_chegam_ao_artefato() -> None:
    """`status_churn`, `nota_wellhub` e `qtd_avaliacoes_wellhub` — o que a DEC-035 autoriza."""
    out = montar_redes_nomeadas(
        _churn([("wellhub", "a", "bluefit")]),
        _coordenadas([("wellhub", "a", "Bluefit Centro", 0.0)]),
    )
    linha = out.iloc[0]
    assert linha["status_churn"] == "presente"
    assert float(linha["nota_wellhub"]) == 4.5
    assert int(linha["qtd_avaliacoes_wellhub"]) == 120
    assert linha["rede"] == "bluefit"
    assert linha["nome"] == "Bluefit Centro"
    assert linha["versao_contrato"] == c.VERSAO_CONTRATO_REDES_NOMEADAS


# --------------------------------------------------------------------------- #
# 2 e 3. O universo de exibição é PRÓPRIO, e não vaza nos dois sentidos        #
# --------------------------------------------------------------------------- #
def test_o_universo_de_exibicao_e_o_complemento_do_sinal_1() -> None:
    """Redes dos agregadores entram; independentes e a fonte `unidades` ficam fora."""
    frame = _churn(
        [
            ("wellhub", "rede1", "bluefit"),
            ("totalpass", "rede2", "smart_fit"),
            ("wellhub", "ind1", c.CATEGORIA_INDEPENDENTE),
            ("unidades", "mapeada", "bluefit"),
        ]
    )
    universo = filtrar_universo_exibicao_redes(frame)

    assert set(universo["chave_snapshot"]) == {"rede1", "rede2"}
    assert c.CATEGORIA_INDEPENDENTE not in set(universo["rede"].astype(str))
    assert "unidades" not in set(universo["fonte"].astype(str)), (
        "a fonte `unidades` e' o insumo mapeado, que ja' tem pin no funil"
    )


def test_independente_nunca_entra_no_artefato_de_redes() -> None:
    """Trava de vazamento. Se o filtro afrouxar, o guard derruba."""
    out = montar_redes_nomeadas(
        _churn(
            [("wellhub", "a", "bluefit"), ("wellhub", "i", c.CATEGORIA_INDEPENDENTE)]
        ),
        _coordenadas(
            [("wellhub", "a", "Bluefit", 0.0), ("wellhub", "i", "Academia do Ze", 100.0)]
        ),
    )
    assert list(out["chave_snapshot"]) == ["a"]

    vazado = out.copy()
    vazado.loc[0, "rede"] = c.CATEGORIA_INDEPENDENTE
    with pytest.raises(AssertionError, match="independente"):
        _assert_schema_redes(vazado)


def test_o_filtro_do_sinal_1_continua_intacto() -> None:
    """O de exibição é OUTRA função. Os dois recortes são disjuntos e cobrem os agregadores."""
    from motor_expansao.vulnerabilidade.presenca_agregador import _filtrar_universo_sinal_1

    frame = _churn(
        [
            ("wellhub", "rede1", "bluefit"),
            ("wellhub", "ind1", c.CATEGORIA_INDEPENDENTE),
            ("totalpass", "ind2", c.CATEGORIA_INDEPENDENTE),
            ("unidades", "mapeada", "bluefit"),
        ]
    )
    do_score = set(_filtrar_universo_sinal_1(frame.copy())["chave_snapshot"])
    de_exibicao = set(filtrar_universo_exibicao_redes(frame.copy())["chave_snapshot"])

    assert do_score == {"ind1", "ind2"}, "o universo do sinal 1 mudou"
    assert de_exibicao == {"rede1"}
    assert do_score & de_exibicao == set(), "os dois universos se sobrepuseram"


# --------------------------------------------------------------------------- #
# 4. Precedência de pin — herdada da dedup da DEC-034                          #
# --------------------------------------------------------------------------- #
def test_tem_pin_proprio_sai_da_dedup_e_nao_de_regra_nova() -> None:
    """Sobrevivente da dedup = sem pin no funil = pin próprio. Colapsada = já tem pin."""
    feed = pd.DataFrame(
        {
            "fonte": ["wellhub", "wellhub"],
            "chave_snapshot": ["longe", "colada"],
            "rede": ["bluefit", "bluefit"],
            "lat": [_norte(5_000.0), _norte(10.0)],
            "lng": [_LNG] * 2,
        }
    )
    # Pin do funil na origem: `colada` (10 m) colapsa contra ele; `longe` (5 km) sobrevive.
    mapeados = pd.DataFrame({"lat": [_LAT], "lng": [_LNG], "rede": ["bluefit"]})
    com_pin = chaves_com_pin_proprio(feed, mapeados)

    assert com_pin == {("wellhub", "longe")}

    out = montar_redes_nomeadas(
        _churn([("wellhub", "longe", "bluefit"), ("wellhub", "colada", "bluefit")]),
        _coordenadas(
            [("wellhub", "longe", "Bluefit Longe", 5_000.0), ("wellhub", "colada", "Bluefit Colada", 10.0)]
        ),
        None,
        com_pin,
    )
    por_chave = out.set_index("chave_snapshot")["tem_pin_proprio"]
    assert bool(por_chave["longe"]) is True
    assert bool(por_chave["colada"]) is False


def test_sem_coordenada_nunca_tem_pin_proprio() -> None:
    """A dedup pode dizer "sobreviveu"; sem coordenada não há o que desenhar."""
    coord = _coordenadas([("wellhub", "a", "Bluefit", 0.0)])
    coord.loc[0, "lat"] = None
    out = montar_redes_nomeadas(
        _churn([("wellhub", "a", "bluefit")]),
        coord,
        None,
        {("wellhub", "a")},
    )
    assert bool(out["tem_pin_proprio"].iloc[0]) is False


def test_sem_o_conjunto_da_dedup_ninguem_ganha_pin() -> None:
    """Default CONSERVADOR: sem saber quem sobreviveu, desenhar arriscaria dois pins no lugar."""
    out = montar_redes_nomeadas(
        _churn([("wellhub", "a", "bluefit")]),
        _coordenadas([("wellhub", "a", "Bluefit", 0.0)]),
    )
    assert bool(out["tem_pin_proprio"].iloc[0]) is False


# --------------------------------------------------------------------------- #
# 5. Ausência é nula, nunca zero                                               #
# --------------------------------------------------------------------------- #
def test_sem_pressao_a_auditoria_e_o_grao_saem_NULOS() -> None:
    """`0 concorrentes` é uma afirmação forte; "não medi" não é."""
    out = montar_redes_nomeadas(
        _churn([("wellhub", "a", "bluefit")]),
        _coordenadas([("wellhub", "a", "Bluefit", 0.0)]),
    )
    linha = out.iloc[0]
    assert pd.isna(linha["pressao_competitiva"])
    assert pd.isna(linha["pressao_grao"]), "carimbou de ONDE mediu algo que nao foi medido"
    assert pd.isna(linha["universo_oferta"])
    for coluna in (
        "n_concorrentes_no_raio",
        "n_independentes_no_raio",
        "n_cadeias_do_feed_no_raio",
        "oferta_ponderada",
        "dist_concorrente_mais_proximo_m",
    ):
        assert pd.isna(linha[coluna]), f"`{coluna}` afirmou valor sem pressao medida"


def test_com_pressao_o_grao_e_academia_e_a_auditoria_chega() -> None:
    """O grão sai por CONSTRUÇÃO: o join é por `(fonte, chave_snapshot)`, que só o grão academia tem."""
    out = montar_redes_nomeadas(
        _churn([("wellhub", "a", "bluefit")]),
        _coordenadas([("wellhub", "a", "Bluefit", 0.0)]),
        _pressao([("wellhub", "a", 61.5)]),
    )
    linha = out.iloc[0]
    assert float(linha["pressao_competitiva"]) == 61.5
    assert linha["pressao_grao"] == c.PRESSAO_GRAO_ACADEMIA
    assert int(linha["n_concorrentes_no_raio"]) == 3
    assert int(linha["n_cadeias_do_feed_no_raio"]) == 1
    assert float(linha["dist_concorrente_mais_proximo_m"]) == 420.0


# --------------------------------------------------------------------------- #
# Contrato, anti-PII e materialização                                          #
# --------------------------------------------------------------------------- #
def test_o_contrato_tem_as_20_colunas_na_ordem() -> None:
    out = montar_redes_nomeadas(
        _churn([("wellhub", "a", "bluefit")]),
        _coordenadas([("wellhub", "a", "Bluefit", 0.0)]),
    )
    assert list(out.columns) == list(c.CONTRATO_COLUNAS_REDES_NOMEADAS.keys())
    assert len(out.columns) == 20
    assert c.VERSAO_CONTRATO_REDES_NOMEADAS == "redes_ma_nomeadas_v1"


def test_campo_de_PESSOA_derruba_o_guard() -> None:
    """§11: identidade de ESTABELECIMENTO é autorizada; de PESSOA, nunca."""
    out = montar_redes_nomeadas(
        _churn([("wellhub", "a", "bluefit")]),
        _coordenadas([("wellhub", "a", "Bluefit", 0.0)]),
    )
    with pytest.raises(AssertionError, match="§11"):
        _assert_schema_redes(out.assign(autor_review="alguem"))


def test_universo_vazio_devolve_frame_do_contrato() -> None:
    """Feed só com independentes: artefato válido e vazio, não exceção."""
    out = montar_redes_nomeadas(
        _churn([("wellhub", "i", c.CATEGORIA_INDEPENDENTE)]),
        _coordenadas([("wellhub", "i", "Academia do Ze", 0.0)]),
    )
    assert out.empty
    assert list(out.columns) == list(c.CONTRATO_COLUNAS_REDES_NOMEADAS.keys())


def test_materializar_fora_de_staging_e_barrado(tmp_path) -> None:
    """Mesmo guard do nomeado de independentes: o artefato carrega identidade."""
    with pytest.raises(ValueError, match="staging"):
        materializar_redes_nomeadas(
            _churn([("wellhub", "a", "bluefit")]),
            _coordenadas([("wellhub", "a", "Bluefit", 0.0)]),
            saida=tmp_path / "vazando.parquet",
        )


def test_auditoria_da_materializacao_conta_os_dois_regimes_de_pin(tmp_path) -> None:
    """A auditoria separa quem ganha pin de quem já está coberto pelo funil."""
    destino = tmp_path / "staging" / "redes.parquet"
    auditoria = materializar_redes_nomeadas(
        _churn([("wellhub", "a", "bluefit"), ("wellhub", "b", "selfit")]),
        _coordenadas([("wellhub", "a", "Bluefit", 0.0), ("wellhub", "b", "Selfit", 500.0)]),
        com_pin_proprio={("wellhub", "a")},
        saida=destino,
    )
    assert auditoria["unidades_de_rede"] == 2
    assert auditoria["com_pin_proprio"] == 1
    assert auditoria["cobertas_por_pin_do_funil"] == 1
    assert destino.exists()

    lido = pd.read_parquet(destino)
    assert list(lido.columns) == list(c.CONTRATO_COLUNAS_REDES_NOMEADAS.keys())
