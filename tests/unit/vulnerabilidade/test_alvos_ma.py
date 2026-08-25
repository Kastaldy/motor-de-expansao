"""BLK-MA-05: testes da lista priorizada de alvos de M&A (D5 hex quente + D6 entregável).

Todas as fixtures são SINTÉTICAS — a carteira é forjada campo a campo e o score vem dos helpers
injetados do `test_score.py`. **Nenhum teste lê `data/`**: a carteira real é artefato de produção e
os CSVs de origem são gitignored e carregam PII (DEC-012).

Os testes que mais importam:

  * **`test_join_falharia_se_alterasse_o_m1`** — o assert de invariância não é decorativo: o teste
    simula o join corrompendo `score_priorizacao` e prova que a função LEVANTA. Sem ele, o
    "READ-ONLY" seria prosa.
  * **`test_agregacao_nao_atravessa_regimes`** — a obrigação DURA do `BLK-MA-04-FU1` aplicada à
    AGREGAÇÃO, que é onde ela é mais fácil de violar em silêncio: um `{s3}` e um `{s1,s3,s4}` no
    MESMO hex não podem virar uma média só.
  * **`test_regime_de_dois_sinais_nao_se_mistura_pelo_contador`** — segmentar pelo CONTADOR não
    basta. `{s1,s3}` e `{s3,s4}` têm ambos `n = 2` e renormalizações diferentes.
  * **`test_csv_nao_carrega_identidade`** — D1 Opção A / DEC-012, provado RELENDO o arquivo.
"""

from __future__ import annotations

from pathlib import Path

import h3
import pandas as pd
import pytest

from motor_expansao.vulnerabilidade import alvos_ma as m
from motor_expansao.vulnerabilidade import contrato as c
from motor_expansao.vulnerabilidade.alvos_ma import (
    academias_com_hotness,
    agregar_alvos_por_hex,
    marcar_hex_quente,
    materializar_alvos_ma,
)
from motor_expansao.vulnerabilidade.score import calcular_score_vulnerabilidade

from .test_score import (
    HEX_A,
    HEX_B,
    _churn,
    _linha_churn,
    _linha_presenca,
    _presenca,
    _tokens,
)

# Vizinhança REAL (não inventada): o anel k=1 de cada centro.
HEX_Q = HEX_A
HEX_VIZ = sorted(set(h3.grid_disk(HEX_Q, 1)) - {HEX_Q})[0]
HEX_FRIO = HEX_B
_FILLERS = sorted(set(h3.grid_disk(HEX_FRIO, 1)) - {HEX_FRIO})[:5]
HEX_FORA = sorted(set(h3.grid_disk(HEX_FRIO, 2)) - set(h3.grid_disk(HEX_FRIO, 1)))[0]


# --------------------------------------------------------------------------- #
# Fixtures sintéticas
# --------------------------------------------------------------------------- #
def _linha_carteira(
    hex_id: str, *, sam: float, residual: float, uf: str = "SP"
) -> dict[str, object]:
    """Uma linha da carteira com as 5 colunas do §9 e as 5 invariantes do molde."""
    return {
        "hex_id": hex_id,
        "uf": uf,
        "sam_fitness_potencial": sam,
        "score_oportunidade_residual": residual,
        "oferta_efetiva_disponivel": 1000.0,
        "tese_entrada": "descartar",
        "score_priorizacao": 55.5,
        "rank_brasil": 1,
        "rank_uf": 2,
        "rank_carteira_brasil": 3,
        "rank_carteira_uf": 4,
    }


def _carteira() -> pd.DataFrame:
    """8 hexes. O `q75` cai em 25,0, então só `HEX_Q` satisfaz a conjunção do D5.

    `HEX_VIZ` tem SAM alto mas residual 90 (não saturado) — ele existe para provar que a
    adjacência k=1 é o que o torna relevante, não o seu próprio calor.
    """
    linhas = [
        _linha_carteira(HEX_Q, sam=100.0, residual=10.0),
        _linha_carteira(HEX_VIZ, sam=100.0, residual=90.0),
        _linha_carteira(HEX_FRIO, sam=0.0, residual=0.0, uf="RJ"),
        *[_linha_carteira(h, sam=0.0, residual=0.0, uf="RJ") for h in _FILLERS],
    ]
    return pd.DataFrame(linhas)


def _score_de(
    linhas_churn: list[dict[str, object]],
    hexes_com_s1: list[str],
    *,
    pressao: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Score real, calculado pelo módulo do MA-04 a partir de frames injetados."""
    return calcular_score_vulnerabilidade(
        churn=_churn(linhas_churn),
        presenca=_presenca([_linha_presenca(h) for h in hexes_com_s1]),
        pressao=pressao,
    )


def _score_padrao() -> pd.DataFrame:
    """Uma academia em cada situação de hotness, todas no regime completo `{s1,s3,s4}`."""
    return _score_de(
        [
            _linha_churn("k_q", hex_id=HEX_Q, n_semanas_serie=13, interpretavel=True),
            _linha_churn("k_viz", hex_id=HEX_VIZ, n_semanas_serie=13, interpretavel=True),
            _linha_churn("k_frio", hex_id=HEX_FRIO, n_semanas_serie=13, interpretavel=True),
            _linha_churn("k_fora", hex_id=HEX_FORA, n_semanas_serie=13, interpretavel=True),
        ],
        [HEX_Q, HEX_VIZ, HEX_FRIO, HEX_FORA],
    )


def _linha_por_chave(df: pd.DataFrame, chave: str) -> pd.Series:
    recorte = df[df["chave_snapshot"] == chave]
    assert len(recorte) == 1, f"a chave {chave} deveria ter exatamente 1 linha"
    return recorte.iloc[0]


# --------------------------------------------------------------------------- #
# D5 — hexágono quente
# --------------------------------------------------------------------------- #
def test_hex_quente_e_a_conjuncao_do_d5() -> None:
    """SAM no top quartil E residual saturado. Nenhuma das duas metades sozinha basta."""
    out = marcar_hex_quente(_carteira())
    quentes = set(out.loc[out["hex_quente"], "hex_id"].astype(str))
    assert quentes == {HEX_Q}, "so' o hex com SAM alto E residual baixo e' quente"


def test_sam_alto_com_residual_folgado_nao_e_quente() -> None:
    """A INVERSÃO do §2: comprar quer mercado SATURADO. Residual alto desqualifica."""
    out = marcar_hex_quente(_carteira())
    linha = out[out["hex_id"] == HEX_VIZ].iloc[0]
    assert float(linha["sam_fitness_potencial"]) == 100.0
    assert not bool(linha["hex_quente"])


def test_marcar_hex_quente_nao_muta_a_carteira() -> None:
    carteira = _carteira()
    antes = carteira.copy()
    marcar_hex_quente(carteira)
    pd.testing.assert_frame_equal(carteira, antes)


def test_limiar_residual_vem_do_contrato() -> None:
    """O corte `< 25` é do gate D5 e mora no contrato — mudá-lo é DEC, não argumento de chamada."""
    assert c.LIMIAR_RESIDUAL_SATURADO == 25.0
    assert c.QUANTIL_SAM_QUENTE == 0.75


def test_carteira_vazia_nao_quebra() -> None:
    vazia = pd.DataFrame(
        {
            c: pd.Series(dtype="float64")
            for c in ("sam_fitness_potencial", "score_oportunidade_residual")
        }
    )
    vazia["hex_id"] = pd.Series(dtype="string")
    out = marcar_hex_quente(vazia)
    assert out.empty


def test_carteira_sem_coluna_do_d5_levanta() -> None:
    carteira = _carteira().drop(columns=["sam_fitness_potencial"])
    with pytest.raises(AssertionError, match="sam_fitness_potencial"):
        marcar_hex_quente(carteira)


# --------------------------------------------------------------------------- #
# Adjacência k=1
# --------------------------------------------------------------------------- #
def test_adjacencia_k1_marca_o_vizinho_e_nao_o_centro() -> None:
    """O anel EXCLUI o centro: as duas metades da disjunção do §9 ficam auditáveis em separado."""
    out = academias_com_hotness(_score_padrao(), _carteira())

    q = _linha_por_chave(out, "k_q")
    assert bool(q["hex_quente"]) and not bool(q["hex_quente_vizinho"])
    assert bool(q["proximo_de_hex_quente"])

    viz = _linha_por_chave(out, "k_viz")
    assert not bool(viz["hex_quente"]) and bool(viz["hex_quente_vizinho"])
    assert bool(viz["proximo_de_hex_quente"])


def test_hex_distante_nao_e_proximo_de_quente() -> None:
    out = academias_com_hotness(_score_padrao(), _carteira())
    frio = _linha_por_chave(out, "k_frio")
    assert not bool(frio["proximo_de_hex_quente"])


def test_hex_invalido_na_carteira_nao_derruba_a_materializacao() -> None:
    """Dado sujo de terceiro vira aviso, não exceção: `grid_disk` LEVANTA para célula inválida."""
    carteira = _carteira()
    carteira.loc[len(carteira)] = _linha_carteira("nao-e-um-hex", sam=100.0, residual=1.0)
    out = academias_com_hotness(_score_padrao(), carteira)
    assert len(out) == 4


# --------------------------------------------------------------------------- #
# Join READ-ONLY — o coração do guardrail
# --------------------------------------------------------------------------- #
def test_join_preserva_cardinalidade() -> None:
    score = _score_padrao()
    out = academias_com_hotness(score, _carteira())
    assert len(out) == len(score)


def test_join_nao_muta_a_carteira() -> None:
    carteira = _carteira()
    antes = carteira.copy()
    academias_com_hotness(_score_padrao(), carteira)
    pd.testing.assert_frame_equal(carteira, antes)


def test_join_propaga_o_m1_sem_alterar() -> None:
    out = academias_com_hotness(_score_padrao(), _carteira())
    assert float(_linha_por_chave(out, "k_q")["score_priorizacao"]) == 55.5


def test_join_falharia_se_alterasse_o_m1(monkeypatch: pytest.MonkeyPatch) -> None:
    """O assert de invariância é EXECUTÁVEL: corrompa o transporte e a função levanta.

    Sem este teste, `_assert_invariancia_m1` poderia estar comparando uma coisa com ela mesma e
    passando por vacuidade — que é o modo de falha clássico de assert de invariância.
    """
    original = m.marcar_hex_quente

    def _corrompido(carteira: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
        out = original(carteira, **kwargs)  # type: ignore[arg-type]
        out["score_priorizacao"] = out["score_priorizacao"] + 1.0
        return out

    monkeypatch.setattr(m, "marcar_hex_quente", _corrompido)
    with pytest.raises(AssertionError, match="score_priorizacao"):
        academias_com_hotness(_score_padrao(), _carteira())


def test_carteira_com_hex_duplicado_levanta() -> None:
    """`many_to_one` seria ambíguo: o hotness do hex tem de ser único."""
    carteira = pd.concat([_carteira(), _carteira().head(1)], ignore_index=True)
    with pytest.raises(AssertionError, match="duplicado"):
        academias_com_hotness(_score_padrao(), carteira)


def test_hex_fora_da_carteira_nao_e_quente_e_nao_e_erro() -> None:
    """Ausência de evidência de calor não é calor — e não é exceção."""
    out = academias_com_hotness(_score_padrao(), _carteira())
    fora = _linha_por_chave(out, "k_fora")
    assert not bool(fora["hex_quente"])
    assert pd.isna(fora["sam_fitness_potencial"])


# --------------------------------------------------------------------------- #
# A obrigação DURA do BLK-MA-04-FU1, aplicada à agregação
# --------------------------------------------------------------------------- #
def test_agregacao_nao_atravessa_regimes() -> None:
    """Duas academias no MESMO hex, regimes diferentes -> DUAS linhas, nunca uma média só."""
    score = _score_de(
        [
            _linha_churn(
                "k_completa", hex_id=HEX_Q, status="estavel", n_semanas_serie=13, interpretavel=True
            ),
            _linha_churn("k_so_s3", hex_id=HEX_Q, status="sumiu_recente", n_semanas_serie=9),
        ],
        [HEX_Q],
    )
    # As duas casam no sinal 1 (mesmo hex), então force o regime `{s3}` removendo o par do S1.
    score.loc[score["chave_snapshot"] == "k_so_s3", ["v1", "n_agregadores_no_hex"]] = pd.NA
    score.loc[score["chave_snapshot"] == "k_so_s3", "fontes_presentes_no_hex"] = pd.NA
    score.loc[score["chave_snapshot"] == "k_so_s3", "sinais_disponiveis"] = "s3"
    score.loc[score["chave_snapshot"] == "k_so_s3", "n_sinais_disponiveis"] = 1

    alvos = agregar_alvos_por_hex(academias_com_hotness(score, _carteira()))
    do_hex = alvos[alvos["hex_id_res7"] == HEX_Q]
    assert len(do_hex) == 2, "regimes diferentes no mesmo hex nao podem colapsar numa linha"
    assert set(do_hex["sinais_disponiveis"]) == {"s1,s3,s4", "s3"}


def test_regime_de_dois_sinais_nao_se_mistura_pelo_contador() -> None:
    """`{s1,s3}` e `{s3,s4}` têm ambos `n = 2` — segmentar pelo CONTADOR seria insuficiente."""
    score = _score_padrao().head(2).copy()
    score.loc[score.index[0], "sinais_disponiveis"] = "s1,s3"
    score.loc[score.index[0], "n_sinais_disponiveis"] = 2
    score.loc[score.index[1], "sinais_disponiveis"] = "s3,s4"
    score.loc[score.index[1], "n_sinais_disponiveis"] = 2
    score.loc[score.index[1], "hex_id_res7"] = score.loc[score.index[0], "hex_id_res7"]

    alvos = agregar_alvos_por_hex(academias_com_hotness(score, _carteira()))
    assert len(alvos) == 2, "mesmo contador, reguas diferentes: nao podem virar uma linha"
    assert set(alvos["sinais_disponiveis"]) == {"s1,s3", "s3,s4"}


def test_ordenacao_usa_o_regime_como_chave_primaria() -> None:
    """Um `{s3}` de score 100 lidera o SEU bloco, nunca a lista inteira."""
    score = _score_de(
        [
            _linha_churn(
                "k_completa",
                hex_id=HEX_Q,
                status="estavel",
                n_semanas_serie=13,
                interpretavel=True,
            ),
            _linha_churn("k_so_s3", hex_id=HEX_FRIO, status="sumiu_recente", n_semanas_serie=9),
        ],
        [HEX_Q],
    )
    alvos = agregar_alvos_por_hex(academias_com_hotness(score, _carteira()))

    assert float(alvos.iloc[0]["score_vulnerabilidade_medio"]) < float(
        alvos.iloc[-1]["score_vulnerabilidade_medio"]
    ), "a linha de score 100 e' de 1 sinal e NAO pode encabecar a lista"
    assert int(alvos.iloc[0]["n_sinais_disponiveis"]) == 3


def test_linha_sem_sinal_algum_nao_entra_na_agregacao() -> None:
    """`n_sinais_disponiveis == 0` é ausência de evidência; média sobre ausência é invenção."""
    score = _score_padrao()
    score.loc[score["chave_snapshot"] == "k_q", "score_vulnerabilidade"] = pd.NA
    score.loc[score["chave_snapshot"] == "k_q", "score_vulnerabilidade_ordenavel"] = pd.NA
    score.loc[score["chave_snapshot"] == "k_q", "n_sinais_disponiveis"] = 0
    score.loc[score["chave_snapshot"] == "k_q", "sinais_disponiveis"] = ""

    alvos = agregar_alvos_por_hex(academias_com_hotness(score, _carteira()))
    assert HEX_Q not in set(alvos["hex_id_res7"].astype(str))


# --------------------------------------------------------------------------- #
# Schema e anti-PII
# --------------------------------------------------------------------------- #
def test_schema_camada_scored_em_ordem_e_dtypes() -> None:
    out = academias_com_hotness(_score_padrao(), _carteira())
    assert list(out.columns) == list(c.CONTRATO_COLUNAS_ACADEMIAS_MA.keys())
    for coluna, dtype in c.CONTRATO_COLUNAS_ACADEMIAS_MA.items():
        assert str(out[coluna].dtype) == dtype, coluna


def test_schema_lista_curada_em_ordem_e_dtypes() -> None:
    alvos = agregar_alvos_por_hex(academias_com_hotness(_score_padrao(), _carteira()))
    assert list(alvos.columns) == list(c.CONTRATO_COLUNAS_ALVOS_MA.keys())
    for coluna, dtype in c.CONTRATO_COLUNAS_ALVOS_MA.items():
        assert str(alvos[coluna].dtype) == dtype, coluna


def test_lista_curada_nao_tem_identidade() -> None:
    """D1 Opção A / DEC-012: o MVP é hex-level. Nem a chave opaca entra."""
    alvos = agregar_alvos_por_hex(academias_com_hotness(_score_padrao(), _carteira()))
    for proibida in ("chave_snapshot", "fonte", "rede", "nome", "latitude", "longitude"):
        assert proibida not in alvos.columns


def test_saida_nao_tem_coluna_de_pii() -> None:
    """Anti-PII com UMA exceção nomeada, e ela é do contrato, não conveniência.

    `uf` está em `COLUNAS_PII_PROIBIDAS` porque naquela lista ela é a `uf` do FEED CRU, que viaja
    ao lado de `cep`/`endereco_formatado` e ajuda a reidentificar. Aqui a `uf` vem da CARTEIRA —
    é a UF do hexágono, geografia agregada como o próprio `hex_id_res7` — e o §10 a exige
    nominalmente no cabeçalho do CSV. Nenhuma das outras 18 pode aparecer.
    """
    out = academias_com_hotness(_score_padrao(), _carteira())
    vazando = (set(out.columns) & c.COLUNAS_PII_PROIBIDAS) - {"uf"}
    assert not vazando, vazando
    for identificadora in ("nome", "latitude", "longitude", "cep", "endereco_formatado", "cidade"):
        assert identificadora not in out.columns


def test_score_vazio_produz_saidas_vazias_bem_formadas() -> None:
    vazio = calcular_score_vulnerabilidade(churn=_churn([]), presenca=_presenca([]))
    academias = academias_com_hotness(vazio, _carteira())
    alvos = agregar_alvos_por_hex(academias)
    assert academias.empty and alvos.empty
    assert list(academias.columns) == list(c.CONTRATO_COLUNAS_ACADEMIAS_MA.keys())
    assert list(alvos.columns) == list(c.CONTRATO_COLUNAS_ALVOS_MA.keys())


def test_nota_e_contagem_viajam_juntas_como_fato() -> None:
    """DEC-026: a nota é FATO sem peso, e nunca aparece sem a contagem ao lado."""
    alvos = agregar_alvos_por_hex(academias_com_hotness(_score_padrao(), _carteira()))
    assert "n_com_nota_wellhub" in alvos.columns
    assert "nota_wellhub_mediana" in alvos.columns


def test_nota_nao_altera_a_ordenacao() -> None:
    """O entregável não faz corte sobre nota/contagem — a declaração da DEC-026, em teste."""
    carteira = _carteira()
    base = agregar_alvos_por_hex(academias_com_hotness(_score_padrao(), carteira))

    score = _score_padrao()
    score["nota_wellhub"] = 1.0  # a pior nota possível, no universo inteiro
    score["qtd_avaliacoes_wellhub"] = 500
    com_nota = agregar_alvos_por_hex(academias_com_hotness(score, carteira))

    pd.testing.assert_series_equal(base["hex_id_res7"], com_nota["hex_id_res7"], check_names=False)


# --------------------------------------------------------------------------- #
# Materialização
# --------------------------------------------------------------------------- #
def test_materializa_os_dois_artefatos_no_formato_canonico(tmp_path: Path) -> None:
    parquet = tmp_path / "vulnerabilidade_ma_academias.parquet"
    csv = tmp_path / "alvos_ma_priorizados.csv"

    auditoria = materializar_alvos_ma(
        _score_padrao(), _carteira(), academias_path=parquet, alvos_csv_path=csv
    )
    assert parquet.exists() and csv.exists()
    assert auditoria["academias"] == 4

    relido = pd.read_csv(csv, sep=";", encoding="utf-8-sig")
    assert list(relido.columns) == list(c.CONTRATO_COLUNAS_ALVOS_MA.keys())
    assert csv.read_bytes().startswith(b"\xef\xbb\xbf"), "CSV do projeto e' utf-8-sig"


def test_csv_nao_carrega_identidade(tmp_path: Path) -> None:
    """Provado RELENDO o arquivo, não só inspecionando o frame em memória."""
    csv = tmp_path / "alvos.csv"
    materializar_alvos_ma(
        _score_padrao(),
        _carteira(),
        academias_path=tmp_path / "a.parquet",
        alvos_csv_path=csv,
    )
    texto = csv.read_text(encoding="utf-8-sig")
    assert "chave_snapshot" not in texto
    assert "k_q" not in texto


def test_dry_run_nao_grava(tmp_path: Path) -> None:
    parquet = tmp_path / "a.parquet"
    csv = tmp_path / "b.csv"
    auditoria = materializar_alvos_ma(
        _score_padrao(), _carteira(), academias_path=parquet, alvos_csv_path=csv, dry_run=True
    )
    assert not parquet.exists() and not csv.exists()
    assert auditoria["dry_run"] is True


def test_materializar_sem_fonte_levanta() -> None:
    with pytest.raises(ValueError, match="informe"):
        materializar_alvos_ma(None)


# --------------------------------------------------------------------------- #
# Regressões achadas na revisão adversarial de 2026-08-13
# --------------------------------------------------------------------------- #
def test_quartil_degenerado_nao_marca_sam_zero_como_quente() -> None:
    """D3: com >=75% de zeros, `q75 = 0` e `sam >= 0` valeria para TODO o universo.

    Medido na carteira real: acontece em 12 das 27 UFs. Em SP marcaria 354 hexes de SAM **zero**
    como "hexágono quente / demanda alta" — número errado, silencioso, na mesa do comercial.
    """
    linhas = [_linha_carteira(h, sam=0.0, residual=1.0) for h in _FILLERS]
    linhas.append(_linha_carteira(HEX_Q, sam=50.0, residual=1.0))
    carteira = pd.DataFrame(linhas)

    out = marcar_hex_quente(carteira)
    assert float(out.attrs["corte_sam"]) == 0.0, "o cenario precisa degenerar o quartil"
    quentes = set(out.loc[out["hex_quente"], "hex_id"].astype(str))
    assert quentes == {HEX_Q}, "SAM zero nunca e' demanda alta, mesmo com o quartil degenerado"


def test_guarda_de_sam_positivo_nao_muda_o_resultado_quando_o_quartil_e_saudavel() -> None:
    """A guarda do D3 não pode reabrir o D5: com quartil positivo, o conjunto é o mesmo."""
    out = marcar_hex_quente(_carteira())
    assert set(out.loc[out["hex_quente"], "hex_id"].astype(str)) == {HEX_Q}


def test_carteira_com_dtype_nulavel_nao_acusa_violacao_do_m1() -> None:
    """D2: `Series.equals` compara DTYPE. `Float64` vs `float64` acusava o M1 de ter sido alterado.

    `dtype_backend="numpy_nullable"` é opção suportada de leitura sobre o MESMO arquivo de
    produção — bastava alguém usá-la para o entregável parar de rodar com um erro que aponta para
    o lugar errado (corrupção de artefato oficial que não aconteceu).
    """
    carteira = _carteira()
    carteira["score_priorizacao"] = carteira["score_priorizacao"].astype("Float64")
    for rank in ("rank_brasil", "rank_uf", "rank_carteira_brasil", "rank_carteira_uf"):
        carteira[rank] = carteira[rank].astype("Int64")

    out = academias_com_hotness(_score_padrao(), carteira)
    assert float(_linha_por_chave(out, "k_q")["score_priorizacao"]) == 55.5


def test_hex_invalido_alem_dos_cinco_primeiros_e_barrado() -> None:
    """D4: o `[:5]` cortava a VARREDURA, não a amostra da mensagem — o guard nunca disparava.

    Com dezenas de milhares de academias, a chance de o hex sujo cair nos 5 primeiros únicos é
    ~0. Este é o único guard de geometria da camada.
    """
    score = _score_padrao()
    linhas = [score.iloc[[i % len(score)]].copy() for i in range(8)]
    for i, linha in enumerate(linhas):
        linha["chave_snapshot"] = f"k_{i}"
    inflado = pd.concat(linhas, ignore_index=True)
    inflado.loc[inflado.index[-1], "hex_id_res7"] = "LIXO_NAO_H3"

    with pytest.raises(AssertionError, match="fora de res-7"):
        academias_com_hotness(inflado, _carteira())


def test_carteira_sem_coluna_opcional_nao_quebra_o_astype() -> None:
    """D1: o ramo que tolera carteira incompleta criava `pd.NA` e o `astype("float64")` levantava.

    A defesa derrubava exatamente o caso que existia para salvar.
    """
    for coluna in ("oferta_efetiva_disponivel", "score_priorizacao", "uf", "tese_entrada"):
        carteira = _carteira().drop(columns=[coluna])
        out = academias_com_hotness(_score_padrao(), carteira)
        assert len(out) == 4, coluna
        assert out[coluna].isna().all(), coluna


# --------------------------------------------------------------------------- #
# Sinal 6 propagado como fato sem peso (BLK-MA-12)
# --------------------------------------------------------------------------- #
def _pressao_em(hexes: list[str], perto_de: str) -> pd.DataFrame:
    """Frame de pressão POR HEX com UM concorrente colado no centroide de `perto_de`.

    Continua no grão HEX de propósito: este arquivo testa a PROPAGAÇÃO até o entregável, e o grão
    hex é o caso em que todas as academias do hexágono recebem o mesmo valor — o que torna os
    asserts de propagação legíveis. O grão academia tem testes próprios em `test_score.py` e
    `test_pressao_competitiva.py`.
    """
    from motor_expansao.vulnerabilidade.pressao_competitiva import calcular_pressao_por_hex

    lat, lng = h3.cell_to_latlng(perto_de)
    conc = pd.DataFrame(
        [{"rede": "smart_fit", "lat": lat + 0.004, "lng": lng, "status_registro": "valido"}]
    )
    return calcular_pressao_por_hex(hexes, conc)


def test_sem_pressao_no_score_as_colunas_do_s6_chegam_nulas() -> None:
    """ "Não calculei" tem de continuar distinguível de "medi e não há".

    Na régua do §8.1 o `0` é a leitura mais OTIMISTA ("ninguém espremendo"); confundir ausência de
    cálculo com ausência de concorrência rebaixaria o alvo por falta de dado.
    """
    out = academias_com_hotness(_score_padrao(), _carteira())
    assert out["v6"].isna().all()
    assert out["pressao_competitiva"].isna().all()
    assert out["pressao_grao"].isna().all()


def test_s6_do_score_e_propagado_ate_o_entregavel() -> None:
    """Esta camada não recalcula a pressão — ela carrega o que o score já computou."""
    score = _score_de(
        [
            _linha_churn("k_q", hex_id=HEX_Q, n_semanas_serie=13, interpretavel=True),
            _linha_churn("k_frio", hex_id=HEX_FRIO, n_semanas_serie=13, interpretavel=True),
        ],
        [HEX_Q, HEX_FRIO],
        pressao=_pressao_em([HEX_Q, HEX_FRIO], HEX_Q),
    )
    out = academias_com_hotness(score, _carteira())
    assert float(_linha_por_chave(out, "k_q")["v6"]) > 0.0
    assert float(_linha_por_chave(out, "k_frio")["v6"]) == 0.0, "medido e zero, nao nulo"


def test_pressao_ALTERA_o_score_agora_que_o_s6_tem_peso() -> None:
    """A inversão do BLK-MA-12: o S6 deixou de ser fato e virou componente.

    Enquanto era fato sem peso, havia um teste afirmando exatamente o contrário disto. A mudança
    de arquitetura tinha de virar mudança de teste — senão o antigo passaria a proteger um
    comportamento que ninguém mais quer.
    """
    linhas = [_linha_churn("k_q", hex_id=HEX_Q, n_semanas_serie=13, interpretavel=True)]
    sem = _score_de(linhas, [HEX_Q])
    com = _score_de(linhas, [HEX_Q], pressao=_pressao_em([HEX_Q], HEX_Q))

    s_sem = float(sem.iloc[0]["score_vulnerabilidade"])
    s_com = float(com.iloc[0]["score_vulnerabilidade"])
    assert s_sem != s_com, "com peso, a pressao TEM de mover o score"
    assert _tokens(com.iloc[0]) == ["s1", "s3", "s4", "s6"]
    assert _tokens(sem.iloc[0]) == ["s1", "s3", "s4"]


# --------------------------------------------------------------------------- #
# Guardrails de pacote
# --------------------------------------------------------------------------- #
def test_modulo_nao_importa_demanda_revelada() -> None:
    from .._ast_imports import nomes_importados

    for n in nomes_importados(m):
        assert "demanda_revelada" not in n, n


def test_cli_analisa_os_argumentos() -> None:
    args = m._parse_args(["--base-dir", "x", "--dry-run"])
    assert args.dry_run is True
    assert args.carteira == m.CARTEIRA_PATH_DEFAULT


# --------------------------------------------------------------------------- #
# BLK-MA-21 / DEC-039 (D9) — a fronteira com o BLK-MA-20, imposta POR CÓDIGO
# --------------------------------------------------------------------------- #
def test_cli_aceita_recorte_de_fontes() -> None:
    """`--fontes wellhub` é o que o entregável roda enquanto o BLK-MA-20 não fecha.

    A partição do `totalpass` passa a ser GRAVADA desde o primeiro mês — para o cronômetro de
    `MIN_SEMANAS` começar a correr, já que a 8ª observação de um feed mensal está a 8 meses —, mas
    **não entra no ranking** antes de o grão do S1 ser decidido e a dedup TP × WH ser calibrada
    (ela está arbitrada, não medida: não existe par real).
    """
    args = m._parse_args(["--base-dir", "x", "--fontes", "wellhub"])
    assert args.fontes == ["wellhub"]

    with pytest.raises(SystemExit):
        m._parse_args(["--base-dir", "x", "--fontes", "gympass"])  # nome antigo do WellHub


def test_o_recorte_de_fontes_e_FAIL_CLOSED(caplog: pytest.LogCaptureFixture) -> None:
    """Emenda de 2026-08-25 à DEC-039: **omitir o flag é o comportamento SEGURO**.

    O D9 rejeitou "a DEC proíbe por escrito" com a frase *"é prosa: a cadeia roda com as duas
    fontes sem editar uma linha"*. A primeira implementação tinha `default=None` e, com isso, a
    MESMA propriedade — só que o gesto que vazava passou a ser **não digitar o flag**. E as duas
    receitas canônicas do próprio repositório o omitiam. O teste anterior travava exatamente o
    comportamento errado, assertando `default is None`.
    """
    assert m.FONTES_ENTREGAVEL_DEFAULT == ("wellhub",)

    # 1. Omissão => recorte do entregável, NUNCA a série inteira.
    assert m.resolver_fontes(m._parse_args(["--base-dir", "x"])) == ("wellhub",)
    # 2. Recorte explícito manda sobre o default.
    assert m.resolver_fontes(m._parse_args(["--base-dir", "x", "--fontes", "unidades"])) == (
        "unidades",
    )
    # 3. Série inteira exige GESTO, e ele é mutuamente exclusivo com `--fontes`.
    assert m.resolver_fontes(m._parse_args(["--base-dir", "x", "--todas-as-fontes"])) is None
    with pytest.raises(SystemExit):
        m._parse_args(["--base-dir", "x", "--todas-as-fontes", "--fontes", "wellhub"])


def test_recorte_de_fontes_e_prosa_sem_o_flag() -> None:
    """A DEC exige que o recorte seja IMPOSTO, não prometido: o parâmetro tem de existir de ponta
    a ponta — `ler_snapshots(fontes=)` e `coordenadas_por_chave(fontes=)`.

    Sem os dois, a cadeia inteira roda com as duas fontes sem editar uma linha, e "proibido por
    escrito" não impede nada.
    """
    import inspect

    from motor_expansao.vulnerabilidade import snapshots as msnap

    assert "fontes" in inspect.signature(msnap.ler_snapshots).parameters
    assert "fontes" in inspect.signature(msnap.coordenadas_por_chave).parameters


def _serie_de_duas_fontes(base: Path, *, semanas: int = 13) -> None:
    """Série SINTÉTICA em disco com `wellhub` e `totalpass`, uma academia independente cada.

    Escrita pela função de produção (`escrever_particao_semana`), para que o teste exercite o
    layout de duas chaves de verdade — e não uma aproximação dele.
    """
    from motor_expansao.vulnerabilidade import snapshots as msnap

    hexes = {"wellhub": HEX_Q, "totalpass": HEX_VIZ}
    for i in range(semanas):
        semana = f"2026-{i + 10:02d}"
        linhas = [
            {
                "snapshot_date": f"2026-03-{i + 1:02d}",
                "slug": f"academia-{fonte}",
                "concorrente_id": f"id-{fonte}",
                "chave_snapshot": f"slug:{fonte}:academia-{fonte}",
                "chave_origem": "slug",
                "hex_id_res7": hexes[fonte],
                "rede": c.CATEGORIA_INDEPENDENTE,
                "fonte": fonte,
                "hash_campos_raspados": f"h{fonte}{i:02d}",
                "nota_wellhub": pd.NA,
                "qtd_avaliacoes_wellhub": pd.NA,
                "fontes_lidas": "totalpass,wellhub",
                "versao_contrato": c.VERSAO_CONTRATO_SNAPSHOT,
            }
            for fonte in ("wellhub", "totalpass")
        ]
        frame = pd.DataFrame(linhas)
        for coluna, dtype in c.CONTRATO_COLUNAS_SNAPSHOT.items():
            frame[coluna] = frame[coluna].astype(dtype)
        msnap.escrever_particao_semana(frame, base, semana=semana)


def test_ramo_que_impoe_o_recorte_tira_o_totalpass_do_entregavel(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """O RAMO, não o `argparse`: prova que o TotalPass sai do entregável de ponta a ponta.

    Os dois testes D9 originais cobriam só `argparse` e `inspect.signature`; o ramo de `main()` que
    lê a série recortada e a **injeta** nos dois extratores (`snapshots=[serie]`) não era
    exercitado por teste nenhum. Se os extratores voltassem a ler do disco, o recorte seria
    decorativo — e nada ficaria vermelho.
    """
    base = tmp_path / "serie"
    _serie_de_duas_fontes(base)
    carteira = tmp_path / "carteira.parquet"
    _carteira().to_parquet(carteira, index=False)

    comum = [
        "--base-dir", str(base),
        "--carteira", str(carteira),
        "--sem-pressao",
        "--dry-run",
    ]  # fmt: skip

    assert m.main(comum) == 0
    fechado = capsys.readouterr().out
    assert m.main([*comum, "--todas-as-fontes"]) == 0
    aberto = capsys.readouterr().out

    assert "'academias': 1" in fechado, (
        f"a omissao do flag deixou passar mais de uma fonte: {fechado}"
    )
    assert "'academias': 2" in aberto, f"`--todas-as-fontes` nao abriu a serie: {aberto}"


def test_as_receitas_canonicas_nao_regridem_para_fail_open() -> None:
    """As duas instruções que o operador COPIA têm de ser coerentes com o código.

    Com o recorte fail-closed, a receita correta é a que **omite** o flag — e o que não pode
    aparecer nelas é `--todas-as-fontes`, que abriria a série. Até 2026-08-25 elas omitiam
    `--fontes wellhub` sobre um `default=None`, e omitir era exatamente o gesto que vazava.
    """
    import re

    raiz = Path(m.__file__).resolve().parents[3]
    runbook = (raiz / "docs" / "infra_producao.md").read_text(encoding="utf-8")
    diagnostico = (raiz / "scripts" / "check_artifacts.py").read_text(encoding="utf-8")

    # Só os blocos COPIÁVEIS: as cercas ```bash do runbook e as linhas `print(...)` do
    # diagnóstico. A prosa ao redor PODE (e deve) citar `--todas-as-fontes` para explicar a porta.
    blocos = [b for b in re.findall(r"```bash\n(.*?)```", runbook, re.S) if "alvos_ma" in b]
    # No diagnóstico a receita e a prosa saem pelo MESMO `print`: o que é comando são as linhas
    # que começam por `python -m` ou por `--`. A prosa ao redor pode citar a porta explícita.
    impressas = re.findall(r'print\("(.*?)"\)', diagnostico)
    receita_diag = "\n".join(
        linha for linha in impressas if linha.strip().startswith(("python -m", "--"))
    )
    assert blocos, "o runbook perdeu o bloco copiavel do entregavel"
    assert "alvos_ma" in receita_diag, "o diagnostico perdeu a receita impressa"

    for nome, texto in (
        ("infra_producao.md", "\n".join(blocos)),
        ("check_artifacts.py", receita_diag),
    ):
        assert "--todas-as-fontes" not in texto, f"{nome}: a receita copiavel abre a serie inteira"

    # E as duas dizem, em prosa, que a OMISSÃO já recorta — senão o operador lê "sem flag = tudo".
    assert "FAIL-CLOSED" in runbook, "o runbook nao declara que o recorte vale sem o flag"
    assert "FAIL-CLOSED" in diagnostico, "o diagnostico nao declara o recorte da omissao"
    assert "wellhub" in "\n".join(impressas), "o diagnostico nao nomeia o recorte que vale"


def test_caminhos_de_saida_nao_casam_o_deny_critico_do_loop_guard() -> None:
    """`carteira_expansao*`/`plano_expansao*`/`hexagonos_mercado*` são CRÍTICO no `loop_guard`."""
    for caminho in (m.ACADEMIAS_PATH_DEFAULT, m.ALVOS_CSV_DEFAULT):
        nome = caminho.name
        for proibido in ("carteira_expansao", "plano_expansao", "hexagonos_mercado"):
            assert not nome.startswith(proibido), nome


# --------------------------------------------------------------------------- #
# BLK-MA-14 / DEC-029 — a agregação do entregável deixou de ser `first`
# --------------------------------------------------------------------------- #
def _score_com_pressao_por_academia(pressoes: dict[str, float]) -> pd.DataFrame:
    """Score real com pressão POR ACADEMIA injetada, todas no MESMO hexágono."""
    from .test_score import _pressao_academia

    linhas = [
        _linha_churn(chave, hex_id=HEX_Q, n_semanas_serie=13, interpretavel=True)
        for chave in pressoes
    ]
    return calcular_score_vulnerabilidade(
        churn=_churn(linhas),
        presenca=_presenca([_linha_presenca(HEX_Q)]),
        pressao=_pressao_academia(pressoes),
    )


def test_agregacao_usa_media_e_maximo_nunca_o_first() -> None:
    """Com pressão por academia a variância DENTRO do hex passa a existir — e `first` mentiria.

    Enquanto a pressão vinha do centroide ela era constante no grupo e `first` era honesto. Agora
    duas academias do mesmo hexágono podem ter 90 e 10: `first` devolveria uma delas como se
    representasse o hexágono. O par média+máximo é o mínimo — a média descreve o hex, o máximo
    revela a unidade muito espremida que uma média baixa esconderia.
    """
    score = _score_com_pressao_por_academia({"k_alta": 90.0, "k_baixa": 10.0})
    alvos = agregar_alvos_por_hex(academias_com_hotness(score, _carteira()))
    linha = alvos[alvos["hex_id_res7"] == HEX_Q].iloc[0]

    assert float(linha["pressao_competitiva_media"]) == pytest.approx(50.0)
    assert float(linha["pressao_competitiva_max"]) == pytest.approx(90.0)
    assert float(linha["v6_medio"]) == pytest.approx(0.50)
    # A prova de que NÃO é `first`: com `first` a média sairia igual ao primeiro valor visto.
    assert float(linha["pressao_competitiva_media"]) != pytest.approx(90.0)
    assert float(linha["pressao_competitiva_media"]) != pytest.approx(10.0)


def test_maximo_revela_a_academia_espremida_que_a_media_esconde() -> None:
    """O caso que justifica carregar as DUAS colunas em vez de só a média."""
    score = _score_com_pressao_por_academia({"k1": 5.0, "k2": 5.0, "k3": 5.0, "k_espremida": 95.0})
    linha = agregar_alvos_por_hex(academias_com_hotness(score, _carteira())).iloc[0]
    assert float(linha["pressao_competitiva_media"]) < 30.0, "a media dilui o caso extremo"
    assert float(linha["pressao_competitiva_max"]) == pytest.approx(95.0)
