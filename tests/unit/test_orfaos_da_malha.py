"""Hexágonos órfãos da Fase A (BLK-JOINUF-01, mecanismo 2).

O DEFEITO. A Fase A rodou em 2026-05-15 e nunca mais. A base H3 cresceu DEPOIS, em três
eventos de critério geométrico de borda: +5.305 (centroide, 2026-05-26), +474 (DEC-002) e
+4.107 (DEC-003) = **exatamente 9.886**, batendo por UF em 27/27. Esses hexágonos não têm
LINHA nenhuma no traço censitário — não é join ruim, é ausência — e nenhuma regra de
reclassificação alcança linha ausente.

Duas consequências, e cada uma tem um teste aqui:

1. Sem linha no traço, eles não recebem `cod_municipio` (que só flui por ali). São as
   ÚNICAS 9.886 linhas do artefato sem código, contra ZERO nulos nas outras 1.532.645 —
   e por isso ficavam fora de qualquer regra municipal, inclusive a nota do mecanismo 1.
   O parquet estrutural sempre teve o código para os 1.542.531.
2. Sem dado censitário, não há sinal — e sem sinal não há promoção possível. A malha da
   DEC-045 já cobre 5.612 deles (6,25 milhões de habitantes), incluindo 11 de 11 em
   Fortaleza e 345 de 391 no Rio, que são os casos que o operador reportou.
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import pandas as pd

from motor_expansao.dashboard.data import enrich_dashboard_data
from motor_expansao.pipelines.agregar_censo_hex_da_malha import (
    COL_CARIMBO,
    COL_MOTIVO_SEM_CENSO,
    COL_RENDA,
    COL_SCORE,
    FONTE_ORFAO_ADMITIDO,
    MOTIVO_SEM_SETOR_POVOADO,
    MOTIVO_SETOR_SEM_RENDA,
    MOTIVOS_SEM_CENSO,
    admitir_orfaos_da_malha,
    rotular_orfaos_sem_censo,
)

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)


def _malha(tmp_path, linhas: list[dict]):
    caminho = tmp_path / "malha.parquet"
    pd.DataFrame(linhas).to_parquet(caminho)
    return caminho


# ---------------------------------------------------------------------------
# Admissão do órfão
# ---------------------------------------------------------------------------


def test_admite_hexagono_que_a_malha_cobre_e_o_traco_nao_tem(tmp_path) -> None:
    caminho = _malha(
        tmp_path,
        [
            {"hex_id": "ja_existe", "uf": "CE", "pop_malha": 10.0, "renda_malha": 900.0, "score_malha": 30.0},
            {"hex_id": "orfao", "uf": "CE", "pop_malha": 75342.0, "renda_malha": 1500.0, "score_malha": 55.0},
        ],
    )
    censo = pd.DataFrame({"hex_id": ["ja_existe"], COL_SCORE: [10.0]})

    out = admitir_orfaos_da_malha(censo, malha_path=caminho)

    assert len(out) == 2
    novo = out[out["hex_id"].eq("orfao")].iloc[0]
    assert novo[COL_SCORE] == 55.0
    assert novo[COL_RENDA] == 1500.0
    assert novo["pop_total_setor_2022"] == 75342.0
    assert novo["fonte_renda_censo_hex"] == FONTE_ORFAO_ADMITIDO
    # A linha que ja existia nao pode ser tocada -- esta funcao SO acrescenta.
    assert out[out["hex_id"].eq("ja_existe")].iloc[0][COL_SCORE] == 10.0


def test_nao_admite_hexagono_sem_score_na_malha(tmp_path) -> None:
    """Admitir linha vazia trocaria "sem dado" por "dado nulo" -- pior, some do radar."""
    caminho = _malha(
        tmp_path,
        [{"hex_id": "vazio", "uf": "AM", "pop_malha": 0.0, "renda_malha": None, "score_malha": None}],
    )
    out = admitir_orfaos_da_malha(pd.DataFrame({"hex_id": ["outro"]}), malha_path=caminho)
    assert list(out["hex_id"]) == ["outro"]


def test_admitido_nao_recebe_qualidade_join_uf(tmp_path) -> None:
    """Eles genuinamente NAO tem medida de join -- inventar uma seria mentir no artefato.

    Quem os promove e a nota de MUNICIPIO, pela mesma regra de todo mundo.
    """
    caminho = _malha(
        tmp_path,
        [{"hex_id": "orfao", "uf": "RJ", "pop_malha": 5.0, "renda_malha": 800.0, "score_malha": 12.0}],
    )
    censo = pd.DataFrame({"hex_id": ["x"], "qualidade_join_uf": ["A"]})
    out = admitir_orfaos_da_malha(censo, malha_path=caminho)
    assert pd.isna(out[out["hex_id"].eq("orfao")].iloc[0]["qualidade_join_uf"])


def test_admitido_herda_o_carimbo_de_calibracao(tmp_path) -> None:
    """Sem o carimbo do `k`, a renda do admitido ficaria em escala indefinida."""
    caminho = _malha(
        tmp_path,
        [{"hex_id": "orfao", "uf": "SP", "pop_malha": 5.0, "renda_malha": 800.0, "score_malha": 12.0}],
    )
    censo = pd.DataFrame({"hex_id": ["x"], COL_CARIMBO: ["multiplicativo_global_k=1.2334632197"]})
    out = admitir_orfaos_da_malha(censo, malha_path=caminho)
    assert out[out["hex_id"].eq("orfao")].iloc[0][COL_CARIMBO] == "multiplicativo_global_k=1.2334632197"


def test_sem_malha_no_disco_e_no_op() -> None:
    censo = pd.DataFrame({"hex_id": ["a", "b"]})
    out = admitir_orfaos_da_malha(censo, malha_path="nao/existe.parquet")
    assert len(out) == 2


# ---------------------------------------------------------------------------
# cod_municipio pelo estrutural
# ---------------------------------------------------------------------------


def _base(hex_id: str) -> dict:
    return {
        "hex_id": hex_id,
        "lat": -22.9,
        "lng": -43.2,
        "uf": "RJ",
        "cidade": "Rio de Janeiro",
        "regiao": "SE",
        "score_priorizacao": 60.0,
        "hex_score_estrutural": 55.0,
        "ajuste_executivo": 5.0,
        "faixa_oportunidade": "alta",
        "flag_viavel": True,
        "flag_prioridade": False,
        "rank_brasil": 1,
        "rank_uf": 1,
        "rank_cidade": 1,
        "renda_per_capita": 3000.0,
        "populacao_proxy": 5000.0,
    }


def test_orfao_ganha_cod_municipio_do_estrutural() -> None:
    """O código sempre existiu no estrutural; o artefato é que só o lia do censo."""
    enriquecido = enrich_dashboard_data(
        pd.DataFrame([_base("orfao")]),
        estrutural_pop_df=pd.DataFrame(
            {"hex_id": ["orfao"], "pop_total": [6748000.0], "cod_municipio": ["3304557"]}
        ),
    )
    assert enriquecido["cod_municipio"].iloc[0] == "3304557"


def test_estrutural_nao_sobrescreve_o_codigo_que_o_censo_ja_trouxe() -> None:
    """Preenche LACUNA. O censo segue sendo a fonte primária das 1.532.645 já preenchidas."""
    enriquecido = enrich_dashboard_data(
        pd.DataFrame([_base("normal")]),
        censo_df=pd.DataFrame({"hex_id": ["normal"], "cod_municipio": ["3304557"]}),
        estrutural_pop_df=pd.DataFrame(
            {"hex_id": ["normal"], "pop_total": [1.0], "cod_municipio": ["9999999"]}
        ),
    )
    assert enriquecido["cod_municipio"].iloc[0] == "3304557"


def test_populacao_do_censo_preenche_lacuna_do_hibrido() -> None:
    """`pop_total_setor_2022` FALTAVA na lista de coalescência do merge censitário.

    O merge do híbrido traz a coluna primeiro, então a do censo chegava como
    `pop_total_setor_2022_censo` por sufixo e era DESCARTADA. Nas 1.532.645 linhas
    normais isso nunca apareceu (o híbrido tem o valor); no órfão ADMITIDO pela malha o
    híbrido traz NaN, e a população morria ali — o hexágono virava `granular` (o score
    coalescia, estava na lista) e mesmo assim exibia o total do MUNICÍPIO.

    Fortaleza mostrava 2.428.708 nos 11 hexágonos costeiros mesmo depois de promovidos.
    """
    enriquecido = enrich_dashboard_data(
        pd.DataFrame([_base("orfao")]),
        hybrid_df=pd.DataFrame({"hex_id": ["orfao"], "pop_total_setor_2022": [None]}),
        censo_df=pd.DataFrame({"hex_id": ["orfao"], "pop_total_setor_2022": [75342.0]}),
    )
    assert enriquecido["pop_total_setor_2022"].iloc[0] == 75342.0


def test_coalescencia_nao_sobrescreve_a_populacao_do_hibrido() -> None:
    """Coalescer PRESERVA o híbrido onde ele tem valor — é preenchimento de lacuna."""
    enriquecido = enrich_dashboard_data(
        pd.DataFrame([_base("normal")]),
        hybrid_df=pd.DataFrame({"hex_id": ["normal"], "pop_total_setor_2022": [1234.0]}),
        censo_df=pd.DataFrame({"hex_id": ["normal"], "pop_total_setor_2022": [99999.0]}),
    )
    assert enriquecido["pop_total_setor_2022"].iloc[0] == 1234.0


def test_orfao_com_municipio_bom_vira_granular_de_ponta_a_ponta() -> None:
    """O caso Fortaleza: sem linha no traço, mas o município é classe A.

    Fecha a cadeia inteira do mecanismo 2 -- código pelo estrutural, sinal pela malha e
    promoção pela nota municipal do mecanismo 1, sem régua especial para órfão.
    """
    enriquecido = enrich_dashboard_data(
        pd.DataFrame([_base("orfao")]),
        # o que `admitir_orfaos_da_malha` teria criado no traço
        censo_df=pd.DataFrame(
            {"hex_id": ["orfao"], "score_setor_2022_calibrado": [40.0], "pop_total_setor_2022": [75342.0]}
        ),
        estrutural_pop_df=pd.DataFrame(
            {"hex_id": ["orfao"], "pop_total": [2428708.0], "cod_municipio": ["2304400"]}
        ),
        notas_municipio=pd.DataFrame(
            {
                "cod_municipio": ["2304400"],
                "classe_join_municipio": ["A"],
                "taxa_match_municipio": [0.971],
                "n_setores_municipio": [4408],
            }
        ),
    )
    assert enriquecido["confianca_geografica"].iloc[0] == "granular"
    # E a população exibida deixa de ser a do município inteiro.
    assert enriquecido["populacao_corte_hex"].iloc[0] == 75342.0


# ---------------------------------------------------------------------------
# Rótulo do órfão que a malha NÃO admite (BLK-ORFAOS-01)
#
# O resíduo tem TRÊS partes, não duas: 9.886 = 4.970 admitidos (de 5.600 linhas
# criadas no traço, 630 morrem no merge com a base M1) + 642 na malha sem
# `score_malha` + 4.274 fora da malha. O resíduo VISÍVEL é 4.916, e o grupo de 642
# nunca tinha sido contado por ninguém.
#
# O veredito medido é NÃO PROMOVER: teto de 6.532 habitantes no país inteiro, p50 de
# 0,02 hab por hexágono, ZERO entrariam na fila do funil. Estes testes travam o que
# entrou no lugar — um RÓTULO, que não escreve score, renda nem população.
# ---------------------------------------------------------------------------


def _malha_dois_motivos(tmp_path):
    """Uma linha de cada grupo do resíduo, mais uma que a malha MEDE."""
    return _malha(
        tmp_path,
        [
            # a malha mede: caso de ADMISSÃO, não de rótulo
            {"hex_id": "medido", "uf": "SP", "pop_malha": 900.0, "renda_malha": 1200.0, "score_malha": 40.0},
            # na malha, sem renda publicada pelo IBGE -> `score_malha` nulo
            {"hex_id": "sem_renda", "uf": "SP", "pop_malha": 12.0, "renda_malha": None, "score_malha": None},
        ],
    )


def test_vocabulario_de_motivo_e_fechado_e_sem_acento(tmp_path) -> None:
    """Dois valores, e nada além deles. E sem acento por serem IDENTIFICADORES.

    Eles viajam no parquet e no payload e são comparados por literal; o texto acentuado
    é camada de LABEL, do lado da tela (CLAUDE.md §2). Acentuar aqui é o defeito que
    pintou o mapa inteiro de cinza no BLK-TRAJ-01.
    """
    assert MOTIVOS_SEM_CENSO == ("setor_sem_renda_publicada", "sem_setor_povoado_no_hex")
    for valor in MOTIVOS_SEM_CENSO:
        assert valor == unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode()
        assert valor == valor.lower()

    out = rotular_orfaos_sem_censo(
        pd.DataFrame({"hex_id": ["ja_tem"]}),
        universo=["ja_tem", "sem_renda", "fora_da_malha"],
        malha_path=_malha_dois_motivos(tmp_path),
    )
    rotulos = out.set_index("hex_id")[COL_MOTIVO_SEM_CENSO]
    # cada motivo no seu grupo, e o universo de valores emitidos é o fechado
    assert rotulos["sem_renda"] == MOTIVO_SETOR_SEM_RENDA
    assert rotulos["fora_da_malha"] == MOTIVO_SEM_SETOR_POVOADO
    assert set(rotulos.dropna()) <= set(MOTIVOS_SEM_CENSO)
    # quem já tem linha no traço não recebe rótulo nenhum
    assert pd.isna(rotulos["ja_tem"])


def test_hexagono_que_a_malha_mede_nao_recebe_rotulo(tmp_path) -> None:
    """Ele é caso de ADMISSÃO. Carimbá-lo de "sem setor" afirmaria o oposto da malha.

    O vocabulário é fechado e não tem valor para "não sei" — então a resposta certa é
    ficar de fora, não inventar um terceiro motivo.
    """
    out = rotular_orfaos_sem_censo(
        pd.DataFrame({"hex_id": ["x"]}),
        universo=["x", "medido"],
        malha_path=_malha_dois_motivos(tmp_path),
    )
    assert list(out["hex_id"]) == ["x"]


def test_rotulo_e_puro_e_nao_muta_o_frame_recebido(tmp_path) -> None:
    """Molde de `admitir_orfaos_da_malha` x `sobrepor_renda_da_malha`: função pura.

    `_read_censo_trace_frame` encadeia as três sobre o MESMO frame; uma delas mutando o
    argumento faria a ordem das chamadas virar um acoplamento invisível.
    """
    censo = pd.DataFrame({"hex_id": ["ja_tem"], COL_SCORE: [55.0]})
    antes = censo.copy(deep=True)

    out = rotular_orfaos_sem_censo(
        censo,
        universo=["ja_tem", "fora_da_malha"],
        malha_path=_malha_dois_motivos(tmp_path),
    )

    pd.testing.assert_frame_equal(censo, antes)
    assert COL_MOTIVO_SEM_CENSO not in censo.columns
    assert len(out) == 2
    # e a linha que já existia continua intacta no resultado
    assert out[out["hex_id"].eq("ja_tem")].iloc[0][COL_SCORE] == 55.0


def test_rotulo_nao_escreve_score_renda_nem_populacao(tmp_path) -> None:
    """A terceira função carimba PROCEDÊNCIA e só. Escrever número aqui seria promover."""
    out = rotular_orfaos_sem_censo(
        pd.DataFrame({"hex_id": ["x"], COL_SCORE: [55.0]}),
        universo=["x", "fora_da_malha"],
        malha_path=_malha_dois_motivos(tmp_path),
    )
    novo = out[out["hex_id"].eq("fora_da_malha")].iloc[0]
    assert pd.isna(novo[COL_SCORE])
    for coluna in (COL_RENDA, "pop_total_setor_2022"):
        assert coluna not in out.columns or pd.isna(novo[coluna])


def test_rotulo_e_idempotente_e_no_op_sem_universo_ou_sem_malha(tmp_path) -> None:
    """Sem a malha não dá para distinguir os dois motivos — e inventar um seria o
    defeito que este rótulo existe para consertar."""
    caminho = _malha_dois_motivos(tmp_path)
    censo = pd.DataFrame({"hex_id": ["x"]})

    uma = rotular_orfaos_sem_censo(censo, universo=["x", "fora_da_malha"], malha_path=caminho)
    duas = rotular_orfaos_sem_censo(uma, universo=["x", "fora_da_malha"], malha_path=caminho)
    pd.testing.assert_frame_equal(uma, duas)

    assert len(rotular_orfaos_sem_censo(censo, universo=None, malha_path=caminho)) == 1
    assert len(rotular_orfaos_sem_censo(censo, universo=["x", "y"], malha_path=tmp_path / "nao_ha.parquet")) == 1


def test_procedencia_e_motivo_chegam_ao_artefato_que_o_piloto_serve() -> None:
    """`censo_extra_cols` é o funil: coluna fora da lista é DESCARTADA no merge.

    É a família de defeito DEC-038 na forma mais pura — o carimbo existe no traço, o
    pipeline roda verde, e o artefato que o piloto lê sai sem ele. Sem `fonte_renda_censo_hex`
    lá, o guardrail de procedência que a DEC-055 declara obrigatório não existe onde importa.
    """
    enriquecido = enrich_dashboard_data(
        pd.DataFrame([_base("admitido"), _base("orfao")]),
        censo_df=pd.DataFrame(
            {
                "hex_id": ["admitido", "orfao"],
                "fonte_renda_censo_hex": [FONTE_ORFAO_ADMITIDO, None],
                COL_MOTIVO_SEM_CENSO: [None, MOTIVO_SEM_SETOR_POVOADO],
            }
        ),
    )
    por_hex = enriquecido.set_index("hex_id")
    assert por_hex.loc["admitido", "fonte_renda_censo_hex"] == FONTE_ORFAO_ADMITIDO
    assert por_hex.loc["orfao", COL_MOTIVO_SEM_CENSO] == MOTIVO_SEM_SETOR_POVOADO


def test_payload_do_hexagono_devolve_None_e_nunca_string_vazia() -> None:
    """`""` seria lido pelo front como VALOR e desenharia um aviso em branco.

    São 99,7% dos hexágonos do país sem motivo nenhum — a ausência precisa ser `None`.
    """
    linha = pd.Series({"hex_id": "orfao", "lat": -22.9, "lng": -43.2})
    assert pilot._hex_dict(linha, None)["motivo_sem_censo"] is None

    vazio = pd.Series({"hex_id": "orfao", "lat": -22.9, "lng": -43.2, "motivo_sem_censo": "   "})
    assert pilot._hex_dict(vazio, None)["motivo_sem_censo"] is None

    com = pd.Series(
        {"hex_id": "orfao", "lat": -22.9, "lng": -43.2, "motivo_sem_censo": MOTIVO_SETOR_SEM_RENDA}
    )
    assert pilot._hex_dict(com, None)["motivo_sem_censo"] == MOTIVO_SETOR_SEM_RENDA
