"""Leitura das entradas do relatório dos masters (tudo local, nada de API ao vivo).

Entradas e de onde vêm hoje:

* planilha de levantamento dos masters (`Masters_Ultra_Territorios_e_Unidades.xlsx`, abas
  "Inauguradas" e "Pipeline"): quais unidades cada master OPERA e o que ele tem assinado;
* `hexagonos_mercado_mapeado.parquet` (staging do motor): mercado fitness, oferta já consumida
  e espaço livre por hexágono;
* `concorrentes_mapeados.parquet` (staging do motor): unidades de concorrentes por hexágono;
* `unidades_ultra_mapeadas.parquet` (staging do motor): as unidades Ultra com coordenada;
* artefato GEO de setores do Censo 2022 (`setores_censitarios_2022_geo`): população, renda e
  bairro por setor, para o estudo de área (`masters.area`);
* `dim_unidade.parquet` e `fato_unidade_mes.parquet` (painel de unidades do estudo BLK-UNI):
  cadastro, coordenadas, inauguração e a série mensal de faturamento/alunos de cada unidade.
"""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pandas as pd
import pyarrow.parquet as pq

from motor_expansao.masters.territorios import normalizar

COLUNAS_MERCADO: tuple[str, ...] = (
    "hex_id",
    "uf",
    "cod_municipio",
    "nome_municipio",
    "lat",
    "lng",
    "pop_hex_base",
    "sam_fitness_potencial",
    "oferta_consumida_mercado_estimada",
    "oferta_consumida_ultra_estimada",
    "oferta_efetiva_disponivel",
    "data_snapshot_mercado",
)

COLUNAS_FATO: tuple[str, ...] = (
    "unidade_id",
    "competencia",
    "mes_vida",
    "mes_completo",
    "pre_inauguracao",
    "faturamento",
    "faturamento_agregador",
    "ativos",
    "agregadores",
    "churn_pct",
    "nps",
    # Slides do modelo novo: mês de operação inteira (padrão de faturamento), entradas do 1º ano e
    # outras Ultras abertas a 10 min de carro (retenção, ocupação e vizinhas).
    "operacao_mes_cheio",
    "novos_alunos",
    "n_ultra_outras_abertas__carro_10",
    # Faturamento e tendência: alunos pagantes (recorrentes), para separar de agregador.
    "pagantes",
)

_CABECALHOS = {
    "master secao": "master_secao",
    "master": "master",
    "unidade": "unidade",
    "uf": "uf",
    "cidade": "cidade",
    "meta de abertura": "meta",
    "operacao": "operacao",
    "fase": "fase",
    "dentro do territorio do contrato": "dentro_territorio",
}


def _aba(wb: openpyxl.Workbook, nome: str) -> pd.DataFrame:
    linhas = list(wb[nome].iter_rows(values_only=True))
    idx = next(
        i for i, r in enumerate(linhas) if r and any(normalizar(v) == "unidade" for v in r if v)
    )
    cab = [
        _CABECALHOS.get(normalizar(v), normalizar(v)) if v else f"_c{i}"
        for i, v in enumerate(linhas[idx])
    ]
    df = pd.DataFrame(linhas[idx + 1 :], columns=cab)
    df = df[df["unidade"].notna()].copy()
    for c in df.columns:
        df[c] = df[c].map(lambda v: str(v).strip() if v is not None else None)
    return df


def ler_planilha_masters(caminho: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devolve (inauguradas, pipeline) da planilha de levantamento."""
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    try:
        inaug = _aba(wb, "Inauguradas")
        pipe = _aba(wb, "Pipeline")
    finally:
        wb.close()
    inaug = inaug[inaug["master_secao"].notna() & (inaug["unidade"] != "Unidade")]
    # Em algumas linhas a UF está na coluna "cidade"; normaliza para a coluna `uf`.
    if "cidade" in pipe.columns:
        sem_uf = pipe["uf"].isna() & pipe["cidade"].fillna("").str.fullmatch(r"[A-Z]{2}")
        pipe.loc[sem_uf, "uf"] = pipe.loc[sem_uf, "cidade"]
        pipe.loc[sem_uf, "cidade"] = None
    return inaug.reset_index(drop=True), pipe.reset_index(drop=True)


#: Concorrentes que ALCANÇAM o hexágono (disco de 1 km), a contagem do motor (DEC-057), e a
#: anterior a ela; lidas só se o artefato as tiver (17/11: o mapa de concorrentes do relatório).
COLUNAS_MERCADO_OPCIONAIS: tuple[str, ...] = (
    "n_concorrentes_influencia_1km",
    "n_concorrentes_mapeados_1km",
)


def ler_mercado(caminho: str | Path, ufs: frozenset[str] | set[str]) -> pd.DataFrame:
    tem = set(pq.read_schema(caminho).names)
    extras = [c for c in COLUNAS_MERCADO_OPCIONAIS if c in tem]
    return pd.read_parquet(
        caminho, columns=[*COLUNAS_MERCADO, *extras], filters=[("uf", "in", sorted(ufs))]
    )


def ler_mercado_brasil(caminho: str | Path) -> pd.DataFrame:
    """O mercado do país inteiro, só com o que a régua da ocupação usa (`analise.referencia_ocupacao`)."""
    return pd.read_parquet(
        caminho,
        columns=[
            "uf",
            "nome_municipio",
            "sam_fitness_potencial",
            "oferta_consumida_mercado_estimada",
            "oferta_consumida_ultra_estimada",
        ],
    )


def ler_concorrentes(caminho: str | Path) -> pd.DataFrame:
    df = pd.read_parquet(caminho)
    if "flag_coord_valida" in df.columns:
        df = df[df["flag_coord_valida"].fillna(False).astype(bool)]
    if "flag_duplicado_rede_coord" in df.columns:
        df = df[~df["flag_duplicado_rede_coord"].fillna(False).astype(bool)]
    return df[["concorrente_id", "rede", "hex_id_res7"]]


def ler_ultra(caminho: str | Path) -> pd.DataFrame:
    """Unidades Ultra do motor (`unidades_ultra_mapeadas.parquet`), só com coordenada válida."""
    df = pd.read_parquet(
        caminho,
        columns=["ultra_id", "unidade", "uf", "lat", "lng", "hex_id_res7", "flag_coord_valida"],
    )
    df = df[df["flag_coord_valida"].fillna(False).astype(bool)]
    return df.drop(columns=["flag_coord_valida"]).reset_index(drop=True)


def ler_unidades(dim_path: str | Path, fato_path: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    dim = pd.read_parquet(dim_path)
    dim = dim[~dim["excluida_rede"].fillna(False).astype(bool)].copy()
    dim["inauguracao"] = pd.to_datetime(dim["inauguracao"], errors="coerce")
    dim["chave_nome"] = dim["nome"].map(normalizar)
    fato = pd.read_parquet(fato_path, columns=list(COLUNAS_FATO))
    fato = fato[fato["unidade_id"].isin(dim["unidade_id"])].copy()
    fato["mes_completo"] = fato["mes_completo"].fillna(False).astype(bool)
    fato["pre_inauguracao"] = fato["pre_inauguracao"].fillna(False).astype(bool)
    return dim.reset_index(drop=True), fato.reset_index(drop=True)
