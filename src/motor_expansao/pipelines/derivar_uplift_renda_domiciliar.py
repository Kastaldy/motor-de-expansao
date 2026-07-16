"""Deriva o UPLIFT de renda (responsavel -> domicilio inteiro) usando SO dados do IBGE.

Por que este pipeline existe
----------------------------
O Censo 2022 por setor publica apenas a renda da pessoa RESPONSAVEL pelo domicilio (V06004).
Nao existe, no agregado setorial, a renda de todos os moradores. Para chegar a renda domiciliar
e preciso um fator de uplift.

A primeira calibracao desse fator foi feita contra a GeoFusion (SP 2.02 / RJ 2.38 / DF 2.15).
Isso era circular — ajustava um modelo contra outro modelo — e herdava o vies dela: medido
contra o Censo 2022 (contagem completa), a GeoFusion superestima a populacao em +10.4% em media
(30/30 pontos acima; ver data/reports/uplift_renda_domiciliar.md).

Aqui o fator e derivado SO do IBGE, fechando a conta com duas fontes oficiais:

    renda_domiciliar_total = rendimento_domiciliar_per_capita (SIDRA t.10295 v.13431)
                             x moradores_por_domicilio        (Censo, v0005)
    uplift_municipio       = renda_domiciliar_total / renda_media_do_responsavel (V06004)

Resultado: mediana nacional ~1.63 — o responsavel responde por ~61% da renda do domicilio.

IMPORTANTE — valores sao de JULHO/2022 (data de referencia do Censo). A atualizacao para valores
correntes e um fator SEPARADO e explicito (`FATOR_TEMPORAL_RENDA` em dashboard/constants.py).
Nao embuta inflacao aqui: foi exatamente essa mistura que fez o fator antigo (2.15) envelhecer
escondido — ele carregava composicao familiar E deriva temporal no mesmo numero.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_SETORES_ROOT = Path("data/outputs/setores_censitarios_2022_geo")
DEFAULT_M1_PATH = Path("data/staging/brasil_estrutural.parquet")
DEFAULT_OUTPUT_PATH = Path("data/staging/uplift_renda_domiciliar_municipio.parquet")
DEFAULT_REPORT_PATH = Path("data/reports/uplift_renda_domiciliar.md")

# Um uplift fora desta faixa e implausivel (o responsavel nao pode responder por menos de ~1/4
# nem por mais que 100% da renda do domicilio) e denuncia dado ruim no municipio.
UPLIFT_MIN = 1.0
UPLIFT_MAX = 4.0


def agregar_setores_por_municipio(setores_root: Path = DEFAULT_SETORES_ROOT) -> pd.DataFrame:
    """Renda do responsavel e moradores/domicilio por municipio (ponderados por domicilios)."""
    partes: list[pd.DataFrame] = []
    for uf_dir in sorted(setores_root.glob("uf=*")):
        for mun_dir in uf_dir.glob("cod_municipio=*"):
            try:
                partes.append(
                    pd.read_parquet(
                        mun_dir,
                        columns=[
                            "cod_municipio",
                            "uf",
                            "renda_responsavel_media_setor_2022",
                            "avg_moradores_domicilio_setor_2022",
                            "domicilios_particulares_ocupados_setor_2022",
                        ],
                    )
                )
            except (KeyError, OSError, ValueError):
                continue
    if not partes:
        raise FileNotFoundError(f"Nenhum setor lido em {setores_root}")

    setor = pd.concat(partes, ignore_index=True)
    setor["dom"] = pd.to_numeric(
        setor["domicilios_particulares_ocupados_setor_2022"], errors="coerce"
    )
    setor["resp"] = pd.to_numeric(setor["renda_responsavel_media_setor_2022"], errors="coerce")
    setor["mor"] = pd.to_numeric(setor["avg_moradores_domicilio_setor_2022"], errors="coerce")
    setor = setor[setor["dom"].gt(0) & setor["resp"].notna() & setor["mor"].notna()]

    def _pond(grupo: pd.DataFrame) -> pd.Series:
        peso = grupo["dom"].to_numpy(dtype=float)
        return pd.Series(
            {
                "renda_responsavel_municipio": float(
                    np.average(grupo["resp"].to_numpy(dtype=float), weights=peso)
                ),
                "moradores_por_domicilio_municipio": float(
                    np.average(grupo["mor"].to_numpy(dtype=float), weights=peso)
                ),
                "domicilios_municipio": float(peso.sum()),
                "setores_municipio": int(len(grupo)),
            }
        )

    mun = (
        setor.groupby(["uf", "cod_municipio"])
        .apply(_pond, include_groups=False)
        .reset_index()
    )
    mun["cod_municipio"] = mun["cod_municipio"].astype(str)
    return mun


def derivar_uplift(
    setores_root: Path = DEFAULT_SETORES_ROOT,
    m1_path: Path = DEFAULT_M1_PATH,
) -> pd.DataFrame:
    mun = agregar_setores_por_municipio(setores_root)

    # SIDRA t.10295 v.13431 — rendimento nominal medio mensal domiciliar PER CAPITA, por municipio.
    # Chega ao motor como `renda_per_capita` na base M1 (ver pipelines/m1/ibge_censo.py).
    m1 = pd.read_parquet(m1_path, columns=["cod_municipio", "renda_per_capita"])
    m1["cod_municipio"] = m1["cod_municipio"].astype(str)
    m1 = (
        m1[pd.to_numeric(m1["renda_per_capita"], errors="coerce").gt(0)]
        .groupby("cod_municipio")["renda_per_capita"]
        .median()
        .reset_index()
        .rename(columns={"renda_per_capita": "renda_domiciliar_per_capita_ibge"})
    )

    df = mun.merge(m1, on="cod_municipio", how="left")
    # per capita DOMICILIAR x moradores = renda TOTAL do domicilio (fecha a conta do IBGE)
    df["renda_domiciliar_total_ibge"] = (
        df["renda_domiciliar_per_capita_ibge"] * df["moradores_por_domicilio_municipio"]
    )
    df["uplift_composicao"] = (
        df["renda_domiciliar_total_ibge"] / df["renda_responsavel_municipio"]
    )

    plausivel = df["uplift_composicao"].between(UPLIFT_MIN, UPLIFT_MAX)
    df["uplift_confiavel"] = plausivel & df["renda_domiciliar_per_capita_ibge"].notna()

    # Municipio sem dado confiavel herda a mediana da UF; sem UF, a nacional.
    mediana_nacional = float(df.loc[df["uplift_confiavel"], "uplift_composicao"].median())
    mediana_uf = (
        df[df["uplift_confiavel"]].groupby("uf")["uplift_composicao"].median().to_dict()
    )
    df["uplift_composicao_final"] = np.where(
        df["uplift_confiavel"],
        df["uplift_composicao"],
        df["uf"].map(mediana_uf).fillna(mediana_nacional),
    )
    df["fonte_uplift"] = np.where(
        df["uplift_confiavel"], "ibge_municipio", "mediana_uf_ou_nacional"
    )
    df.attrs["mediana_nacional"] = mediana_nacional
    return df


def gerar_relatorio(df: pd.DataFrame) -> str:
    ok = df[df["uplift_confiavel"]]
    med = float(ok["uplift_composicao"].median())
    por_uf = ok.groupby("uf")["uplift_composicao"].agg(["count", "median"]).round(3)

    linhas = [
        "# Uplift de renda domiciliar — derivado do IBGE",
        "",
        "`uplift = renda_domiciliar_total_IBGE / renda_media_do_responsavel`, onde",
        "`renda_domiciliar_total_IBGE = rendimento domiciliar per capita (SIDRA t.10295 v.13431)"
        " x moradores/domicilio (Censo v0005)`.",
        "",
        "Converte a renda do RESPONSAVEL (unica publicada no agregado setorial) em renda do",
        "domicilio inteiro. **Sem GeoFusion na conta** — as duas pontas sao IBGE.",
        "",
        f"- Municipios com uplift proprio: **{len(ok):,}** de {len(df):,}",
        f"- Mediana nacional: **{med:.3f}** (o responsavel traz ~{100/med:.0f}% da renda do domicilio)",
        f"- Desvio padrao: {float(ok['uplift_composicao'].std()):.3f}",
        f"- Faixa (p05-p95): {float(ok['uplift_composicao'].quantile(0.05)):.2f}"
        f" a {float(ok['uplift_composicao'].quantile(0.95)):.2f}",
        "",
        "## Valores em JULHO/2022",
        "",
        "Esta e a data de referencia do Censo. A atualizacao para valores correntes e um fator",
        "SEPARADO (`FATOR_TEMPORAL_RENDA`, em dashboard/constants.py) — de proposito: o fator",
        "antigo, ajustado contra a GeoFusion (2.15), misturava composicao familiar com deriva",
        "temporal no mesmo numero e envelhecia sem ninguem perceber.",
        "",
        "## Por que nao calibrar pela GeoFusion",
        "",
        "Medida contra o Censo 2022 (contagem completa, nao amostra), a GeoFusion superestima a",
        "populacao em **+10.4%** na media — e em **30 de 30** pontos testados, o que caracteriza",
        "vies sistematico, nao ruido. Calibrar por ela importaria esse vies para dentro do motor.",
        "",
        "## Uplift por UF",
        "",
        "| UF | Municipios | Uplift (mediana) |",
        "| --- | ---: | ---: |",
    ]
    for uf, row in por_uf.sort_index().iterrows():
        linhas.append(f"| {uf} | {int(row['count'])} | {row['median']:.3f} |")
    return "\n".join(linhas) + "\n"


def executar(
    setores_root: Path = DEFAULT_SETORES_ROOT,
    m1_path: Path = DEFAULT_M1_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> pd.DataFrame:
    df = derivar_uplift(setores_root, m1_path)
    cols = [
        "uf",
        "cod_municipio",
        "renda_responsavel_municipio",
        "moradores_por_domicilio_municipio",
        "renda_domiciliar_per_capita_ibge",
        "renda_domiciliar_total_ibge",
        "uplift_composicao",
        "uplift_composicao_final",
        "uplift_confiavel",
        "fonte_uplift",
        "domicilios_municipio",
        "setores_municipio",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df[cols].to_parquet(output_path, index=False)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(gerar_relatorio(df), encoding="utf-8")

    ok = df[df["uplift_confiavel"]]
    print(f"[uplift] municipios: {len(df):,} | com uplift proprio: {len(ok):,}")
    print(f"[uplift] mediana nacional: {float(ok['uplift_composicao'].median()):.3f}")
    print(f"[uplift] artefato: {output_path}")
    print(f"[uplift] relatorio: {report_path}")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setores-root", default=str(DEFAULT_SETORES_ROOT))
    parser.add_argument("--m1-path", default=str(DEFAULT_M1_PATH))
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()
    executar(
        Path(args.setores_root),
        Path(args.m1_path),
        Path(args.output_path),
        Path(args.report_path),
    )


if __name__ == "__main__":
    main()
