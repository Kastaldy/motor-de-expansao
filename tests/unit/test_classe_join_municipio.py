"""Nota de cobertura censitaria por MUNICIPIO (BLK-JOINUF-01): promocao-so.

O defeito que estes testes travam: `qualidade_join_uf` e' UM VALOR POR ESTADO
(`fase_a_nacional_completo.py:322-325` grava um escalar em `df_uf` inteiro), derivado de
uma diferenca de CONTAGEM DE LINHAS entre dois CSVs do IBGE
(`validar_fase_a_censo2022.py:215-217`). Com isso, AM (deficit de 10,50%) e RR (9,59%)
sao as duas unicas UFs classe C do pais e perdem 100% dos hexagonos para o fallback
municipal -- Manaus inclusa, com 2.038 dos 2.139 tendo dado de setor real.

DUAS ARMADILHAS QUE ESTE ARQUIVO EXISTE PARA EVITAR, as duas encontradas por revisao
adversarial numa versao anterior dele:

1. ORACULO INDEPENDENTE. A primeira versao comparava `derive_confianca_geografica` COM a
   coluna nova contra ela mesma SEM a coluna. Isso e' vacuo: um mutante que TROCASSE a
   nota de UF pela municipal (em vez de somar) quebrava os dois lados junto e passava
   40/40. Aqui o "antes" e' `_confianca_pre_bloco`, copia LITERAL da funcao como ela era
   antes do bloco, escrita neste arquivo -- um oraculo que nao se move quando a
   implementacao se move.

2. FIACAO. O invariante pode estar perfeito e a promocao nunca acontecer em producao, se
   o produtor nao passar a nota. Mutantes que matavam os tres pontos de fiacao passavam
   516/556 testes. Por isso os `test_fiacao_*`.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
import pytest

from motor_expansao.dashboard.data import enrich_dashboard_data
from motor_expansao.pipelines.classe_join_municipio import (
    FONTE_AUSENTE,
    FONTE_CALCULADA,
    FONTE_PRESERVADA,
    anexar_nota_municipal,
    calcular_notas,
    classificar_taxa,
)
from motor_expansao.pipelines.pop_corte import (
    derive_confianca_geografica,
    has_censo_signal,
    normalized_join_quality,
)


def _confianca_pre_bloco(df: pd.DataFrame) -> pd.Series:
    """Copia LITERAL de `derive_confianca_geografica` como era ANTES do BLK-JOINUF-01.

    Oraculo independente de proposito: se um refactor futuro trocar a disjuncao por uma
    substituicao, esta funcao continua dizendo o que o comportamento antigo dizia e o
    teste falha. Nao delegue daqui para o modulo real -- isso reintroduz a vacuidade.
    """
    if "confianca_geografica" in df.columns:
        base = (
            df["confianca_geografica"]
            .astype(object)
            .where(df["confianca_geografica"].notna(), "municipal")
            .astype(str)
            .str.lower()
        )
        base = base.where(base.isin(["granular", "municipal"]), "municipal")
    else:
        base = pd.Series("municipal", index=df.index, dtype="object")
    mask = normalized_join_quality(df).isin(["A", "B"]) & has_censo_signal(df)
    return pd.Series(np.where(mask, "granular", base), index=df.index, dtype="object")


def _notas(cod: str = "1302603", classe: str = "A", taxa: float = 0.975) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cod_municipio": [cod],
            "classe_join_municipio": [classe],
            "taxa_match_municipio": [taxa],
            "n_setores_municipio": [3281],
        }
    )


# ---------------------------------------------------------------------------
# Classificacao
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("taxa", "esperado"),
    [
        (1.00, "A"),
        (0.9750, "A"),  # Manaus real
        (0.95, "A"),  # borda inclusiva
        (0.9499, "B"),
        (0.9319, "B"),  # Boa Vista real
        (0.90, "B"),  # borda inclusiva
        (0.8999, "C"),
        (0.0, "C"),
    ],
)
def test_classificar_taxa_respeita_os_cortes_do_artefato_geo(taxa: float, esperado: str) -> None:
    """Mesmos cortes de `materializar_setores_censitarios_geo.py:641` (0,95 / 0,90)."""
    assert classificar_taxa(taxa) == esperado


# ---------------------------------------------------------------------------
# O invariante, contra oraculo independente
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("classe_uf", "classe_mun", "persistida"),
    list(
        itertools.product(
            ["A", "B", "C", "Nao informado", None],
            ["A", "B", "C", "Nao informado", None],
            [None, "granular", "municipal"],
        )
    ),
)
def test_promocao_nunca_rebaixa(classe_uf, classe_mun, persistida) -> None:
    """Para QUALQUER (nota de UF, nota municipal, confianca persistida): antes ⊆ depois.

    75 combinacoes, comparadas contra `_confianca_pre_bloco` sobre o MESMO DataFrame --
    sem o truque de "omitir a coluna", que era o que tornava a versao anterior vacua.
    """
    dados = {
        "hex_id": ["a"],
        "qualidade_join_uf": [classe_uf],
        "classe_join_municipio": [classe_mun],
        "flag_censo_disponivel": [True],
    }
    if persistida is not None:
        dados["confianca_geografica"] = [persistida]
    df = pd.DataFrame(dados)

    antes = _confianca_pre_bloco(df).eq("granular")
    depois = derive_confianca_geografica(df).eq("granular")

    assert not (antes & ~depois).any(), (
        f"uf={classe_uf!r} mun={classe_mun!r} persistida={persistida!r} REBAIXOU"
    )


def test_mutante_de_substituicao_seria_pego() -> None:
    """Prova que o oraculo NAO e' vacuo: a substituicao ingenua e' detectavel aqui.

    Trocar a nota de UF pela municipal (em vez de somar) rebaixaria hexagono com UF classe
    A e municipio sem nota. Este teste fixa esse caso concreto -- e' a regressao de 231.891
    hexagonos que a medicao nacional mostrou, reduzida a uma linha.
    """
    df = pd.DataFrame(
        {
            "hex_id": ["a"],
            "qualidade_join_uf": ["A"],
            "classe_join_municipio": [None],
            "flag_censo_disponivel": [True],
        }
    )
    assert _confianca_pre_bloco(df).iloc[0] == "granular"
    assert derive_confianca_geografica(df).iloc[0] == "granular"


def test_municipio_bom_promove_hexagono_preso_em_estado_ruim() -> None:
    """O caso Manaus: UF classe C, municipio classe A -> granular."""
    df = pd.DataFrame(
        {
            "hex_id": ["a", "b", "c"],
            "qualidade_join_uf": ["C", "C", "C"],
            "classe_join_municipio": ["A", "B", "C"],
            "flag_censo_disponivel": [True, True, True],
        }
    )
    assert list(derive_confianca_geografica(df)) == ["granular", "granular", "municipal"]


def test_sem_sinal_censitario_a_nota_municipal_nao_promove() -> None:
    """A nota afrouxa o gate de JOIN, nao o de EXISTENCIA de dado."""
    df = pd.DataFrame(
        {
            "hex_id": ["a"],
            "qualidade_join_uf": ["C"],
            "classe_join_municipio": ["A"],
            "flag_censo_disponivel": [False],
        }
    )
    assert list(derive_confianca_geografica(df)) == ["municipal"]


# ---------------------------------------------------------------------------
# Calculo da nota
# ---------------------------------------------------------------------------


def test_calcular_notas_agrega_por_municipio(tmp_path) -> None:
    part = tmp_path / "uf=AM" / "cod_municipio=1302603"
    part.mkdir(parents=True)
    pd.DataFrame(
        {
            "cod_setor": ["1", "2", "3", "4"],
            "cod_municipio": ["1302603"] * 4,
            "flag_renda_disponivel": [True, True, True, False],  # 0,75 -> C
        }
    ).to_parquet(part / "part-000.parquet")

    notas = calcular_notas(tmp_path)
    linha = notas.iloc[0]
    assert linha["cod_municipio"] == "1302603"
    assert linha["taxa_match_municipio"] == pytest.approx(0.75)
    assert linha["n_setores_municipio"] == 4
    assert linha["classe_join_municipio"] == "C"


def test_calcular_notas_normaliza_chave_vinda_como_float(tmp_path) -> None:
    """FORMA: cod_municipio float (1302603.0) nao pode virar chave diferente.

    Sem a normalizacao, `astype(str)` produziria "1302603.0" e o casamento cairia a ZERO
    -- um no-op silencioso, que e' exatamente o defeito que este bloco conserta.
    """
    part = tmp_path / "uf=AM" / "cod_municipio=1302603"
    part.mkdir(parents=True)
    pd.DataFrame(
        {"cod_municipio": [1302603.0, 1302603.0], "flag_renda_disponivel": [True, True]}
    ).to_parquet(part / "part-000.parquet")

    notas = calcular_notas(tmp_path)
    assert list(notas["cod_municipio"]) == ["1302603"]


def test_calcular_notas_sem_artefato_devolve_frame_vazio(tmp_path) -> None:
    notas = calcular_notas(tmp_path / "nao-existe")
    assert notas.empty
    assert list(notas.columns) == [
        "cod_municipio",
        "classe_join_municipio",
        "taxa_match_municipio",
        "n_setores_municipio",
    ]


# ---------------------------------------------------------------------------
# Anexacao: forma da chave, procedencia e preservacao
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("chave", ["1302603", 1302603, 1302603.0, " 1302603 "])
def test_anexar_casa_a_chave_em_qualquer_formato(chave) -> None:
    """TRIPWIRE DE FORMA: int, float e string com espaco tem de casar igual.

    Cada um destes formatos aparece em algum artefato do repo. Um deles nao casando faz a
    promocao virar zero SEM erro nenhum.
    """
    df = pd.DataFrame({"hex_id": ["a"], "cod_municipio": [chave]})
    out = anexar_nota_municipal(df, _notas())
    assert out["classe_join_municipio"].iloc[0] == "A", f"formato {chave!r} nao casou"
    assert out["fonte_classe_join_municipio"].iloc[0] == FONTE_CALCULADA


def test_anexar_carimba_a_procedencia() -> None:
    """"Sem nota" e "nota C" precisam ser distinguiveis no artefato."""
    df = pd.DataFrame({"hex_id": ["a", "b"], "cod_municipio": ["1302603", "9999999"]})
    out = anexar_nota_municipal(df, _notas())
    assert out["classe_join_municipio"].iloc[0] == "A"
    assert pd.isna(out["classe_join_municipio"].iloc[1])
    assert list(out["fonte_classe_join_municipio"]) == [FONTE_CALCULADA, FONTE_AUSENTE]


def test_anexar_com_notas_malformadas_nao_estoura() -> None:
    """Frame sem as colunas do contrato e' tratado como ausencia, nao como KeyError.

    Estourar aqui derrubaria um pipeline inteiro por causa de um insumo parcial.
    """
    df = pd.DataFrame({"hex_id": ["a"], "cod_municipio": ["1302603"]})
    out = anexar_nota_municipal(df, pd.DataFrame({"cod_municipio": ["1302603"]}))
    assert out["fonte_classe_join_municipio"].iloc[0] == FONTE_AUSENTE
    assert pd.isna(out["classe_join_municipio"].iloc[0])


def test_reexecucao_sem_a_malha_preserva_a_nota_ja_gravada() -> None:
    """`calcular_colunas_mercado` LE O PROPRIO OUTPUT: sobrescrever apagaria a auditoria.

    Sem isto, rodar de novo numa maquina sem os 1,17 GB da malha deixaria o artefato com
    hexagono `granular` (preservado pelo termo `base`) e NENHUMA coluna explicando por que.
    """
    df = pd.DataFrame({"hex_id": ["a"], "cod_municipio": ["1302603"]})
    primeira = anexar_nota_municipal(df, _notas())
    assert primeira["classe_join_municipio"].iloc[0] == "A"

    segunda = anexar_nota_municipal(primeira, pd.DataFrame())
    assert segunda["classe_join_municipio"].iloc[0] == "A", "a nota anterior foi apagada"
    assert segunda["fonte_classe_join_municipio"].iloc[0] == FONTE_PRESERVADA


# ---------------------------------------------------------------------------
# FIACAO: a promocao chega mesmo ao produtor?
# ---------------------------------------------------------------------------


def _base_para_enriquecer() -> pd.DataFrame:
    """Linha minima do dataset oficial M1 (mesma forma de `test_enrich_dashboard_data`)."""
    return pd.DataFrame(
        [
            {
                "hex_id": "a",
                "lat": -3.1,
                "lng": -60.0,
                "uf": "AM",
                "cidade": "Manaus",
                "regiao": "N",
                "score_priorizacao": 50.0,
                "hex_score_estrutural": 45.0,
                "ajuste_executivo": 5.0,
                "faixa_oportunidade": "media",
                "flag_viavel": True,
                "flag_prioridade": False,
                "rank_brasil": 1,
                "rank_uf": 1,
                "rank_cidade": 1,
                "renda_per_capita": 1200.0,
                "populacao_proxy": 1000.0,
                # O que faz este hexagono ser o caso Manaus: estado classe C, mas com
                # sinal censitario e populacao de setor real disponivel.
                "cod_municipio": "1302603",
                "qualidade_join_uf": "C",
                "flag_censo_disponivel": True,
                "pop_total_setor_2022": 51.0,
                "pop_total": 2063689.0,
            }
        ]
    )


def test_fiacao_enrich_dashboard_data_promove_com_a_nota() -> None:
    """Ponto 1 da fiacao: o parametro `notas_municipio` e' de fato usado."""
    com = enrich_dashboard_data(_base_para_enriquecer(), notas_municipio=_notas())
    assert com["confianca_geografica"].iloc[0] == "granular"


def test_fiacao_enrich_dashboard_data_sem_nota_nao_promove() -> None:
    """Contraprova do teste acima -- sem ela, um mutante que ignora o parametro passa."""
    sem = enrich_dashboard_data(_base_para_enriquecer())
    assert sem["confianca_geografica"].iloc[0] == "municipal"


def test_fiacao_produtor_le_a_malha_e_repassa_a_nota(monkeypatch, tmp_path) -> None:
    """Ponto 2: `build_enriched_dashboard_frame` LE a malha e PASSA a nota adiante.

    Mata o mutante que remove o argumento no produtor -- que passava a suite inteira
    porque nenhum teste chamava esse caminho.
    """
    from motor_expansao.pipelines.m1 import fase1_bi_exports as bi

    part = tmp_path / "uf=AM" / "cod_municipio=1302603"
    part.mkdir(parents=True)
    pd.DataFrame(
        {"cod_municipio": ["1302603"] * 4, "flag_renda_disponivel": [True, True, True, True]}
    ).to_parquet(part / "part-000.parquet")

    capturado: dict[str, pd.DataFrame | None] = {}

    def _fake_enrich(*args, **kwargs):
        capturado["notas"] = kwargs.get("notas_municipio")
        return pd.DataFrame({"hex_id": ["a"]})

    monkeypatch.setattr(bi, "CENSO_GEO_ROOT", tmp_path)
    monkeypatch.setattr(bi, "enrich_dashboard_data", _fake_enrich)
    monkeypatch.setattr(bi, "_read_m1_dashboard_frame", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(bi, "_read_hybrid_frame", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(bi, "_read_censo_trace_frame", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(bi, "_read_estrutural_pop_frame", lambda *a, **k: pd.DataFrame())

    bi.build_enriched_dashboard_frame()

    notas = capturado.get("notas")
    assert notas is not None, "o produtor nao passou notas_municipio"
    assert not notas.empty, "o produtor passou nota VAZIA mesmo com a malha no disco"
    assert notas["classe_join_municipio"].iloc[0] == "A"


def test_fiacao_mercado_anexa_a_nota_antes_do_gate(monkeypatch, tmp_path) -> None:
    """Ponto 3: a camada de MERCADO tambem promove, senao o gate do SAM le outra regua."""
    import motor_expansao.pipelines.calcular_colunas_mercado as ccm

    part = tmp_path / "uf=AM" / "cod_municipio=1302603"
    part.mkdir(parents=True)
    pd.DataFrame(
        {"cod_municipio": ["1302603"] * 4, "flag_renda_disponivel": [True] * 4}
    ).to_parquet(part / "part-000.parquet")
    monkeypatch.setattr(ccm, "CENSO_GEO_ROOT", tmp_path)

    df = pd.DataFrame({"hex_id": ["a"], "cod_municipio": ["1302603"]})
    out = ccm.anexar_nota_municipal(df, ccm.calcular_notas_municipio(ccm.CENSO_GEO_ROOT))
    assert out["classe_join_municipio"].iloc[0] == "A"
