"""
Bloco 3 - Enriquecimento espacial por hexagono.

Calcula distancias e contagens entre hexes, concorrentes e unidades Ultra.
Saida: data/staging/hexagonos_mercado_mapeado.parquet (base para o Bloco 4)

Nao altera nenhum artefato oficial do M1.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from motor_expansao.pipelines.pressao_concorrencial_1km import anexar_pressao_1km_area

ROOT = Path(__file__).resolve().parents[3]

HIBRIDO_PATH = ROOT / "data" / "outputs" / "oportunidades_expansao_hibrido.parquet"
ESTRUTURAL_PATH = ROOT / "data" / "staging" / "brasil_estrutural.parquet"
CONCORRENTES_PATH = ROOT / "data" / "staging" / "concorrentes_mapeados.parquet"
# DEC-048: unidades de REDE vistas pelo agregador. OPCIONAL — ausente, o universo de cadeia
# fica so' com o cadastro e o artefato sai IDENTICO ao de antes.
REDES_AGREGADOR_PATH = ROOT / "data" / "staging" / "vulnerabilidade_ma_redes.parquet"
# BLK-CAPACIDADE-01: alunos REAIS por unidade. OPCIONAL -- ausente, toda academia cai no
# proxy de 2.500 e o artefato sai identico ao de antes.
ALUNOS_REAIS_PATH = ROOT / "data" / "staging" / "alunos_reais_por_unidade.parquet"
ULTRA_PATH = ROOT / "data" / "staging" / "unidades_ultra_mapeadas.parquet"
OUT_PATH = ROOT / "data" / "staging" / "hexagonos_mercado_mapeado.parquet"

EARTH_RADIUS_M = 6_371_000.0
RADIUS_1KM_RAD = 1_000.0 / EARTH_RADIUS_M
RADIUS_2KM_RAD = 2_000.0 / EARTH_RADIUS_M
CHUNK_SIZE = 100_000

#: Redes de ESTUDIO BOUTIQUE, fora do universo de oferta (BLK-ESTUDIO-01).
#:
#: Elas nao disputam o mesmo aluno de uma academia full-service low-cost (§1): sao aula em
#: horario marcado, turma pequena, ticket e proposta diferentes. Contadas como concorrente,
#: cada uma consumia os MESMOS 2.500 alunos de um Smart Fit -- e a Ultra lia como saturada
#: uma praca onde ha' tres estudios de pilates e nenhuma academia.
#:
#: A LISTA E' DO DONO, nao minha. Classificar academia x estudio e' juizo de mercado, e o
#: custo de errar e' assimetrico: excluir uma academia de verdade faz a Ultra ver mercado
#: livre onde ha' concorrente, que e' o erro caro. Por isso as 11 redes ambiguas que ele
#: nao reconheceu (Allp Fit, 26Fit, Contorno do Corpo, Corpo e Saude, Usina do Corpo,
#: Wellness Club, Evolve, Motion Fit, Marra Fit, Match Fit, Uplay) ficaram DENTRO.
REDES_ESTUDIO_BOUTIQUE = frozenset(
    {
        "velocity",
        "my_box",
        "vidya_studio",
        "tonus_gym",
        "aera_pilates",
        "race_bootcamp",
        "kore",
        "nadarte",
        "jab_house",
    }
)


def _knn_dist_m(
    hex_coords_rad: np.ndarray,
    ref_coords_rad: np.ndarray,
    chunk: int = 200_000,
) -> np.ndarray:
    """Distance (metres) from each hex centroid to the nearest point in ref_coords_rad."""
    tree = BallTree(ref_coords_rad, metric="haversine")
    n = len(hex_coords_rad)
    result = np.empty(n, dtype=np.float64)
    for start in range(0, n, chunk):
        end = min(start + chunk, n)
        dists_rad, _ = tree.query(hex_coords_rad[start:end], k=1)
        result[start:end] = dists_rad[:, 0] * EARTH_RADIUS_M
    return result


def unir_cadeias(df_comp: pd.DataFrame, df_redes: pd.DataFrame | None) -> pd.DataFrame:
    """Universo de CADEIA = mapeadas validas + as do agregador que ainda nao estao la'.

    O feed do agregador lista 2.844 unidades de REDE. Medido contra `concorrentes_mapeados`:
    1.673 sao a MESMA academia ja' contada e 1.171 NAO estao no cadastro -- Panobianco (130),
    Selfit (130), SkyFit (96), Bluefit (49) e outras. Elas existem, disputam o mesmo aluno e
    nao pressionavam ninguem: a oferta instalada de cadeia estava **26,7% subestimada**.

    Elas entram no MESMO universo, e nao num termo paralelo, porque sao a mesma coisa: unidade
    de rede, com a mesma capacidade de clube. Fosse um termo separado, `flag_white_space_2km`,
    `gap_competitivo_2km` e a contagem exibida continuariam mentindo -- so' o residual ficaria
    certo.

    A ULTIMA FRASE DESTE PARAGRAFO CAIU no BLK-CAPACIDADE-01. Ela dizia: "como a capacidade
    e' identica, `oferta_consumida_mercado_estimada / 2500` segue devolvendo a CONTAGEM
    correta". Deixou de ser verdade no dia em que a capacidade passou a ser a REAL de cada
    unidade -- um Smart Fit de 5.000 alunos daria "2 concorrentes" nessa divisao. Quem
    precisa contar academia le `n_concorrentes_influencia_1km`, que e' contagem de verdade.

    A DEDUP REUSA `tem_pin_proprio`, ja' calculada em `redes_nomeadas.py` via
    `dedup_cadeias_do_feed` (pressao_competitiva.py) -- a MESMA funcao que serve o sinal 6 e o
    consumo de `_oferta_unida` no DEC-046 (api/service.py), com as TRES regras da DEC-034/
    BLK-MA-17-FU4: `(mesma rede E d <= 150 m)` OU `(d <= 50 m)` OU casamento por NOME (ate' 1200
    m, quando as duas fontes geocodificam o mesmo endereco com desvio maior que os limiares de
    distancia). Uma versao anterior desta funcao reimplementava so' as duas primeiras regras
    diretamente aqui -- sem o 3o ramo, ~400 duplicatas por NOME (revisao de codigo em
    2026-09-08 mediu 407 na mesma comparacao) entravam como "nova", inflando a oferta e
    reduzindo o white space alem do que os numeros medidos acima afirmam. `tem_pin_proprio`
    ausente na coluna (artefato antigo, pre-BLK-MA-17) e' tratado como "sem dedup pronta" --
    entra tudo, mesmo comportamento conservador de `_oferta_unida`.

    `df_redes=None` (artefato ausente) devolve so' as mapeadas -- comportamento anterior,
    bit a bit.
    """
    comp_ok = df_comp[df_comp["status_registro"] == "valido"].copy()
    for col in ("lat", "lng"):
        comp_ok[col] = pd.to_numeric(comp_ok[col], errors="coerce")
    comp_ok = comp_ok.dropna(subset=["lat", "lng"]).reset_index(drop=True)
    if df_redes is None or df_redes.empty:
        return comp_ok

    redes = df_redes.copy()
    if "tem_pin_proprio" in redes.columns:
        redes = redes[redes["tem_pin_proprio"].fillna(False).astype(bool)]
    for col in ("lat", "lng"):
        redes[col] = pd.to_numeric(redes[col], errors="coerce")
    redes = redes.dropna(subset=["lat", "lng"])
    if redes.empty:
        return comp_ok

    novas = redes.copy()
    novas["status_registro"] = "valido"
    # `concorrente_id` viaja junto (NULO nas do agregador, que nao o tem) porque e' a
    # chave do crosswalk de alunos reais -- ver `anexar_capacidade_real`. Sem ele aqui, a
    # capacidade por unidade nao teria por onde casar: depois desta funcao so' existem
    # agregados por hexagono.
    colunas = ["rede", "lat", "lng", "status_registro"]
    if "concorrente_id" in comp_ok.columns:
        comp_ok = comp_ok.copy()
        novas = novas.copy()
        novas["concorrente_id"] = pd.NA
        colunas = [*colunas, "concorrente_id"]
    unido = pd.concat([comp_ok[colunas], novas[colunas]], ignore_index=True)
    # float64 PURO na saida, e nao `Float64` nullable. O cadastro guarda float64 e o feed do
    # agregador guarda nullable; o `concat` dos dois promove a coluna para nullable, e
    # `calc_comp_metrics` -- que consome este frame -- faz `.values` direto sobre as duas
    # colunas, o que sobre nullable devolve `object` e derruba o `np.radians`.
    # Sanear na FRONTEIRA de saida, e nao no consumidor: quem recebe este frame tem direito
    # de assumir coordenada numerica de verdade. (Encontrado ao rodar o pipeline real: os
    # testes passavam porque exercitavam `unir_cadeias` isolada, sem a funcao a jusante.)
    for col in ("lat", "lng"):
        unido[col] = unido[col].astype("float64")
    return unido.reset_index(drop=True)


def excluir_estudios_boutique(
    cadeias: pd.DataFrame, *, redes: frozenset[str] = REDES_ESTUDIO_BOUTIQUE
) -> pd.DataFrame:
    """Tira os estudios boutique do universo de OFERTA (BLK-ESTUDIO-01).

    Funcao SEPARADA de `unir_cadeias` de proposito, no molde de
    `admitir_orfaos_da_malha` x `sobrepor_renda_da_malha` (DEC-055): aquela responde
    "quem existe", esta responde "quem CONTA como concorrente". Sao duas perguntas, e
    juntar as duas numa funcao so' faria a segunda mudar de resposta sempre que a
    primeira mudasse de fonte.

    APLICADA UMA VEZ, ANTES dos dois modelos. Nao e' economia de linhas: o comentario
    do passo 5b ja' exigia que o modelo de 2 km e o de 1 km concordassem sobre QUEM e'
    concorrente. Filtrar so' o de 1 km (a oferta do residual) deixaria os estudios
    INFLANDO o mercado por `calibrar_taxa_fitness_mercado`, que le
    `n_concorrentes_mapeados_2km` para estimar a penetracao -- o residual subiria pelas
    duas pontas, e nao por uma. Um universo, uma resposta.

    O QUE ESTA FUNCAO NAO ALCANCA, e e' por desenho: os pins do mapa e a contagem do
    Relatorio Pontual (DEC-046) leem `concorrentes_mapeados.parquet` direto, na camada
    web/relatorio, sem passar por aqui. O operador continua VENDO o estudio no mapa.

    O QUE ELA ALCANCA E O DONO ACEITOU: o rotulo Livre/Adensar/Disputa (DEC-041) e a
    camada 3 do funil derivam de `n_concorrentes_est`, que desde a DEC-051 e' a oferta
    do residual dividida pela capacidade (`web/server/app.py`) -- nao uma contagem de
    cabecas. Medido: 135 hexagonos mudam de rotulo (73 Adensar->Livre, 62
    Disputa->Adensar). Decisao dele em 2026-09-10: uma regua so' na tela.
    """
    if "rede" not in cadeias.columns or cadeias.empty:
        return cadeias

    slug = cadeias["rede"].astype(str)
    fora = slug.isin(redes)

    # TRIPWIRE. O slug de `rede` nao vem de cadastro nenhum: `normalizar_concorrentes`
    # o deriva do NOME DO ARQUIVO CSV coletado. Renomear um arquivo la' na coleta apaga
    # esta exclusao em SILENCIO -- o pipeline seguiria verde com o estudio de volta na
    # oferta. Um slug declarado que nao casa NADA e' sinal disso, e tem de falar.
    vazios = sorted(r for r in redes if not slug.eq(r).any())
    if vazios:
        print(f"   AVISO: rede(s) de estudio sem nenhuma unidade no universo: {', '.join(vazios)}")
        print("          o slug vem do nome do CSV da coleta -- conferir se foi renomeado.")

    return cadeias[~fora].reset_index(drop=True)


def anexar_capacidade_real(
    cadeias: pd.DataFrame, *, crosswalk_path: Path = ALUNOS_REAIS_PATH
) -> pd.DataFrame:
    """Anexa `capacidade_alunos` por unidade a partir dos alunos REAIS (BLK-CAPACIDADE-01).

    Ate' aqui toda academia do pais consumia os mesmos 2.500 alunos -- um proxy, e o
    proprio nome da constante dizia isso (`CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS`). O
    crosswalk do BLK-ALUNOS-01 casou 1.202 unidades com o numero que a propria rede
    informou; onde ele existe, deixa de haver motivo para usar o proxy.

    QUEM NAO TEM CONTINUA COM O PROXY, e a coluna sai NULA para essas linhas em vez de
    2.500 -- quem consome decide o default. Preencher aqui esconderia do artefato quantas
    unidades sao medidas e quantas sao estimadas, que e' a pergunta que a auditoria faz.

    So' entra `confianca_match == "alta"`, a mesma regua que o tooltip usa: a rota de
    contencao e' inferencia, e um numero inferido virando CAPACIDADE mexe no residual de
    todo mundo em volta, nao so' na linha dele.

    Ausencia do crosswalk e' caminho NORMAL (o parquet nao e' versionado): devolve o
    frame sem a coluna, e o modelo cai inteiro no proxy -- exatamente o de hoje.
    """
    if not crosswalk_path.is_file() or "concorrente_id" not in cadeias.columns:
        print("   capacidade real: crosswalk ausente - todo mundo no proxy de 2.500")
        return cadeias

    cw = pd.read_parquet(crosswalk_path, columns=["concorrente_id", "alunos_total", "confianca_match"])
    cw = cw[
        cw["concorrente_id"].notna()
        & cw["confianca_match"].astype(str).eq("alta")
        & (pd.to_numeric(cw["alunos_total"], errors="coerce") > 0)
    ]
    mapa = cw.set_index(cw["concorrente_id"].astype(str))["alunos_total"].astype(float)

    out = cadeias.copy()
    out["capacidade_alunos"] = out["concorrente_id"].astype(str).map(mapa)
    n = int(out["capacidade_alunos"].notna().sum())
    print(f"   capacidade real: {n:,} de {len(out):,} unidades ({n/max(len(out),1):.1%}); resto no proxy")
    return out


def calc_comp_metrics(
    hex_coords_rad: np.ndarray,
    df_comp: pd.DataFrame,
) -> dict:
    comp_valid = df_comp[df_comp["status_registro"] == "valido"].reset_index(drop=True)
    comp_coords_rad = np.radians(comp_valid[["lat", "lng"]].values)

    is_smart = (comp_valid["rede"] == "smart_fit").values
    is_blue = (comp_valid["rede"] == "bluefit").values
    is_pano = (comp_valid["rede"] == "panobianco").values

    n = len(hex_coords_rad)
    tree = BallTree(comp_coords_rad, metric="haversine")

    n_1km = np.zeros(n, dtype=np.int32)
    n_2km = np.zeros(n, dtype=np.int32)
    n_smart = np.zeros(n, dtype=np.int32)
    n_blue = np.zeros(n, dtype=np.int32)
    n_pano = np.zeros(n, dtype=np.int32)
    oferta_1km = np.zeros(n, dtype=np.float64)
    oferta_2km = np.zeros(n, dtype=np.float64)

    n_chunks = (n - 1) // CHUNK_SIZE + 1
    print(f"  Contagens e pesos ({n:,} hexes, {n_chunks} chunks)...")
    for ci, start in enumerate(range(0, n, CHUNK_SIZE)):
        end = min(start + CHUNK_SIZE, n)
        indices, dists_rad = tree.query_radius(
            hex_coords_rad[start:end],
            r=RADIUS_2KM_RAD,
            return_distance=True,
            sort_results=False,
        )
        for i, (idxs, dr) in enumerate(zip(indices, dists_rad, strict=False)):
            if len(idxs) == 0:
                continue
            gi = start + i
            dm = dr * EARTH_RADIUS_M

            n_2km[gi] = len(idxs)
            mask_1 = dm <= 1000.0
            n_1km[gi] = int(mask_1.sum())

            sm = is_smart[idxs]
            bm = is_blue[idxs]
            pm = is_pano[idxs]
            n_smart[gi] = int(sm.sum())
            n_blue[gi] = int(bm.sum())
            n_pano[gi] = int(pm.sum())

            w2 = np.maximum(0.0, 1.0 - dm / 2000.0)
            oferta_2km[gi] = w2.sum()
            if mask_1.any():
                oferta_1km[gi] = np.maximum(0.0, 1.0 - dm[mask_1] / 1000.0).sum()

        if ci % 5 == 0:
            print(f"    chunk {ci + 1}/{n_chunks}")

    # Distancias minimas globais via k=1
    print("  Distancias minimas (k=1)...")
    dist_comp_min = _knn_dist_m(hex_coords_rad, comp_coords_rad)
    dist_smart_min = _knn_dist_m(
        hex_coords_rad,
        np.radians(comp_valid.loc[is_smart, ["lat", "lng"]].values),
    ) if is_smart.any() else np.full(n, np.nan)
    dist_blue_min = _knn_dist_m(
        hex_coords_rad,
        np.radians(comp_valid.loc[is_blue, ["lat", "lng"]].values),
    ) if is_blue.any() else np.full(n, np.nan)
    dist_pano_min = _knn_dist_m(
        hex_coords_rad,
        np.radians(comp_valid.loc[is_pano, ["lat", "lng"]].values),
    ) if is_pano.any() else np.full(n, np.nan)

    # Metricas derivadas (divisao apenas onde denominador > 0)
    mask_has = n_2km > 0
    share_smart = np.zeros(n, dtype=np.float64)
    share_blue  = np.zeros(n, dtype=np.float64)
    share_pano  = np.zeros(n, dtype=np.float64)
    n_2km_f = n_2km[mask_has].astype(np.float64)
    share_smart[mask_has] = n_smart[mask_has] / n_2km_f
    share_blue[mask_has]  = n_blue[mask_has]  / n_2km_f
    share_pano[mask_has]  = n_pano[mask_has]  / n_2km_f

    # Rede dominante com tie-break alfabetico: bluefit < panobianco < smart_fit
    counts_abc = np.column_stack([n_blue, n_pano, n_smart])
    redes_abc = np.array(["bluefit", "panobianco", "smart_fit"])
    rede_dom = np.where(  # type: ignore[call-overload]
        n_2km > 0,
        redes_abc[np.argmax(counts_abc, axis=1)],
        None,
    )

    flag_white = n_2km == 0
    gap_comp = 1.0 / (1.0 + oferta_2km)
    pressao = 100.0 * (1.0 - gap_comp)

    return {
        "n_concorrentes_mapeados_1km": n_1km,
        "n_concorrentes_mapeados_2km": n_2km,
        "n_smart_fit_2km": n_smart,
        "n_bluefit_2km": n_blue,
        "n_panobianco_2km": n_pano,
        "dist_concorrente_mais_proximo_m": dist_comp_min,
        "dist_smart_fit_mais_proximo_m": dist_smart_min,
        "dist_bluefit_mais_proximo_m": dist_blue_min,
        "dist_panobianco_mais_proximo_m": dist_pano_min,
        "oferta_efetiva_mapeada_1km": oferta_1km,
        "oferta_efetiva_mapeada_2km": oferta_2km,
        "share_smart_fit_2km": share_smart,
        "share_bluefit_2km": share_blue,
        "share_panobianco_2km": share_pano,
        "rede_dominante_2km": rede_dom,
        "flag_white_space_2km": flag_white,
        "gap_competitivo_2km": gap_comp,
        "pressao_concorrencial_score_2km": pressao,
    }


def calc_ultra_metrics(
    hex_coords_rad: np.ndarray,
    df_ultra: pd.DataFrame,
) -> dict:
    ultra_valid = df_ultra[df_ultra["flag_coord_valida"]].reset_index(drop=True)
    ultra_coords_rad = np.radians(ultra_valid[["lat", "lng"]].values)

    n = len(hex_coords_rad)
    tree = BallTree(ultra_coords_rad, metric="haversine")

    n_ultra_1km = np.zeros(n, dtype=np.int32)
    n_ultra_2km = np.zeros(n, dtype=np.int32)

    n_chunks = (n - 1) // CHUNK_SIZE + 1
    print(f"  Contagens Ultra ({len(ultra_valid)} unidades, {n_chunks} chunks)...")
    for ci, start in enumerate(range(0, n, CHUNK_SIZE)):
        end = min(start + CHUNK_SIZE, n)
        indices, dists_rad = tree.query_radius(
            hex_coords_rad[start:end],
            r=RADIUS_2KM_RAD,
            return_distance=True,
            sort_results=False,
        )
        for i, (idxs, dr) in enumerate(zip(indices, dists_rad, strict=False)):
            if len(idxs) == 0:
                continue
            gi = start + i
            dm = dr * EARTH_RADIUS_M
            n_ultra_2km[gi] = len(idxs)
            n_ultra_1km[gi] = int((dm <= 1000.0).sum())

        if ci % 5 == 0:
            print(f"    chunk {ci + 1}/{n_chunks}")

    print("  Distancia minima Ultra (k=1)...")
    dist_ultra_min = _knn_dist_m(hex_coords_rad, ultra_coords_rad)

    flag_canibal = dist_ultra_min < 1000.0
    gap_rede = 1.0 / (1.0 + n_ultra_1km.astype(float))

    return {
        "n_unidades_ultra_1km": n_ultra_1km,
        "n_unidades_ultra_2km": n_ultra_2km,
        "dist_ultra_mais_proxima_m": dist_ultra_min,
        "flag_canibalizacao_ultra_1km": flag_canibal,
        "gap_rede_propria_1km": gap_rede,
    }


def validar(df: pd.DataFrame, n_orig: int) -> None:
    print("\n=== Validacao: hexagonos_mercado_mapeado (Bloco 3) ===")

    assert len(df) == n_orig, f"Cardinalidade alterada: {len(df)} != {n_orig}"
    print(f"Linhas: {len(df):,} (preservada OK)")

    required = {
        "n_concorrentes_mapeados_1km", "n_concorrentes_mapeados_2km",
        "n_smart_fit_2km", "n_bluefit_2km", "n_panobianco_2km",
        "dist_concorrente_mais_proximo_m",
        "n_unidades_ultra_1km", "n_unidades_ultra_2km",
        "dist_ultra_mais_proxima_m", "flag_canibalizacao_ultra_1km",
        "oferta_efetiva_1km_area", "gap_competitivo_1km_area",
        "consumo_concorrentes_1km_area", "n_concorrentes_influencia_1km",
    }
    faltam = required - set(df.columns)
    assert not faltam, f"Colunas faltando: {faltam}"
    print("Schema minimo OK")

    for col in ["n_concorrentes_mapeados_1km", "n_concorrentes_mapeados_2km",
                "n_unidades_ultra_1km", "n_unidades_ultra_2km"]:
        n_nulos = df[col].isna().sum()
        assert n_nulos == 0, f"Nulos inesperados em {col}: {n_nulos}"
    print("Sem nulos em colunas de contagem")

    n_canibal = int(df["flag_canibalizacao_ultra_1km"].sum())
    n_white = int(df["flag_white_space_2km"].sum())
    total = len(df)
    print(f"flag_canibalizacao_ultra_1km=True: {n_canibal:,} ({100*n_canibal/total:.1f}%)")
    print(f"flag_white_space_2km=True:         {n_white:,} ({100*n_white/total:.1f}%)")
    n_tocados_1km = int((df["oferta_efetiva_1km_area"] > 0).sum())
    print(f"oferta_efetiva_1km_area>0 (hexes tocados): {n_tocados_1km:,} ({100*n_tocados_1km/total:.1f}%)")

    print("\nAmostra manual (3 hexes com concorrentes):")
    sample_cols = [
        "hex_id", "uf", "n_concorrentes_mapeados_2km",
        "dist_concorrente_mais_proximo_m", "rede_dominante_2km",
        "n_unidades_ultra_2km", "dist_ultra_mais_proxima_m",
        "flag_canibalizacao_ultra_1km",
    ]
    com_comp = df[df["n_concorrentes_mapeados_2km"] > 0][sample_cols].head(3)
    if not com_comp.empty:
        print(com_comp.to_string(index=False))

    assert df["dist_concorrente_mais_proximo_m"].isna().sum() == 0, (
        "dist_concorrente_mais_proximo_m tem nulos inesperados"
    )
    assert df["dist_ultra_mais_proxima_m"].isna().sum() == 0, (
        "dist_ultra_mais_proxima_m tem nulos inesperados"
    )
    print("\nValidacao OK")


def main():
    print("Bloco 3 - Enriquecimento espacial por hexagono")
    print("=" * 50)

    print("\n1. Carregando bases...")
    df_hibrido = pd.read_parquet(HIBRIDO_PATH)
    df_est = pd.read_parquet(ESTRUTURAL_PATH, columns=["hex_id", "lat", "lng", "pop_total"])
    df_comp = pd.read_parquet(CONCORRENTES_PATH)
    df_ultra = pd.read_parquet(ULTRA_PATH)
    print(f"   hibrido: {len(df_hibrido):,}")
    print(f"   estrutural (lat/lng/pop_total): {len(df_est):,}")
    print(f"   concorrentes validos: {(df_comp.status_registro == 'valido').sum()}")
    print(f"   ultra validas: {df_ultra.flag_coord_valida.sum()}")

    print("\n2. Montando base com coordenadas...")
    n_orig = len(df_hibrido)
    df_base = df_hibrido.merge(df_est, on="hex_id", how="left", suffixes=("", "_est"))
    assert len(df_base) == n_orig, "Join alterou cardinalidade"
    assert df_base["lat"].isna().sum() == 0, "lat nulo apos join com estrutural"

    hex_coords_rad = np.radians(df_base[["lat", "lng"]].values)
    print(f"   Base: {len(df_base):,} linhas")

    print("\n3. Metricas de concorrentes...")
    # DEC-048: o universo de CADEIA passa a incluir as unidades de rede que o agregador ve'
    # e o cadastro nao tem. O ramo ausente FALA: um artefato com a oferta subestimada em
    # mais de um terco nao pode passar despercebido.
    if REDES_AGREGADOR_PATH.is_file():
        df_redes_wh = pd.read_parquet(REDES_AGREGADOR_PATH)
        cadeias = unir_cadeias(df_comp, df_redes_wh)
        n_base = int((df_comp.status_registro == 'valido').sum())
        print(f"   cadeias: {n_base:,} do cadastro + {len(cadeias) - n_base:,} do agregador = {len(cadeias):,}")
    else:
        print(f"   AUSENTE: {REDES_AGREGADOR_PATH.name} - so' o cadastro; a oferta de cadeia segue subestimada.")
        cadeias = unir_cadeias(df_comp, None)

    # BLK-ESTUDIO-01: os estudios boutique saem do universo de OFERTA aqui, UMA vez,
    # antes dos dois modelos -- ver `excluir_estudios_boutique`. Pins e Relatorio
    # Pontual leem o parquet direto e seguem enxergando todo mundo.
    n_antes = len(cadeias)
    cadeias = excluir_estudios_boutique(cadeias)
    print(f"   estudios boutique fora da oferta: {n_antes - len(cadeias):,} de {n_antes:,}")

    # BLK-CAPACIDADE-01: quem tem aluno real medido para de valer o proxy de 2.500.
    cadeias = anexar_capacidade_real(cadeias)

    comp_metrics = calc_comp_metrics(hex_coords_rad, cadeias)

    print("\n4. Metricas Ultra...")
    ultra_metrics = calc_ultra_metrics(hex_coords_rad, df_ultra)

    print("\n5. Montando DataFrame final...")
    for col, vals in {**comp_metrics, **ultra_metrics}.items():
        df_base[col] = vals

    print("\n5b. Modelo de area de influencia (1 km por concorrente, DEC-051)...")
    # Mesmo universo `cadeias` do passo 3 (cadastro + agregador, deduplicado e JA' SEM os
    # estudios boutique) -- os dois modelos (2km centroide e 1km area) tem de concordar
    # sobre QUEM e' concorrente. A "exclusao futura" que este comentario previa chegou no
    # BLK-ESTUDIO-01, e entrou onde ele mandava: uma vez, acima dos dois.
    df_base = anexar_pressao_1km_area(df_base, cadeias, coluna_capacidade="capacidade_alunos")

    validar(df_base, n_orig)

    print(f"\n6. Salvando em {OUT_PATH}...")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_base.to_parquet(OUT_PATH, index=False)
    size_mb = OUT_PATH.stat().st_size / 1e6
    print(f"   Salvo: {size_mb:.1f} MB")
    print("\nBloco 3 concluido.")


if __name__ == "__main__":
    main()
