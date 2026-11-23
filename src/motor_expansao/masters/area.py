"""Estudo de área do território do master: municípios e bairros (as "microáreas").

No molde do estudo de área do time de Expansão (RJ, abr/2026), que o Relatório Municipal do
motor já reproduz: visão geral por município, bairros por população e por renda, e quais
bairros já têm Ultra (ocupados) ou não (disponíveis).

As contas são as do motor, sem fórmula nova:
* renda média DOMICILIAR do setor pela redação canônica (`renda.setor`), agregada pela média
  ponderada pelos domicílios do setor;
* bairro pelo CNEFE com a malha do IBGE como reserva (`aplicar_bairro_cnefe`, DEC-076) e a mesma
  cascata bairro -> subdistrito -> distrito do Relatório Municipal (`_localidade_do_setor`);
* população e área do Censo 2022 (artefato GEO setorial).

READ-ONLY sobre o M1.
"""

from __future__ import annotations

from pathlib import Path

import h3
import numpy as np
import pandas as pd

from motor_expansao.dashboard.bairro_cnefe import aplicar_bairro_cnefe
from motor_expansao.dashboard.relatorio_municipal import _localidade_do_setor
from motor_expansao.masters.analise import atribuir_regiao
from motor_expansao.masters.territorios import Master
from motor_expansao.pipelines.materializar_setores_censitarios_geo import ler_particao_setores
from motor_expansao.renda.setor import renda_domiciliar_setor

H3_RES = 7

#: Mesma régua de população do motor (gate do SAM, DEC-006/007): bairro com menos gente que isso
#: não entra no "maior renda", senão um condomínio de 300 moradores lidera a lista.
POP_MIN_BAIRRO = 5_000

COLUNAS_SETOR: tuple[str, ...] = (
    "cod_setor",
    "cod_municipio",
    "nome_municipio",
    "nome_bairro",
    "nome_subdistrito",
    "nome_distrito",
    "area_setor_km2_ibge",
    "pop_total_setor_2022",
    "domicilios_particulares_ocupados_setor_2022",
    "avg_moradores_domicilio_setor_2022",
    "renda_responsavel_media_setor_2022",
    "renda_per_capita_setor_2022",
    "bbox_minx",
    "bbox_miny",
    "bbox_maxx",
    "bbox_maxy",
)


def municipios_do_territorio(mercado: pd.DataFrame, master: Master) -> pd.DataFrame:
    """(uf, cod_municipio, nome_municipio, regiao_id) dos municípios das regiões do master."""
    cols = ["uf", "cod_municipio", "nome_municipio"]
    m = mercado[cols].dropna().drop_duplicates()
    m["cod_municipio"] = m["cod_municipio"].astype(str).str.removesuffix(".0")
    m["regiao_id"] = atribuir_regiao(m, master)
    return m[m["regiao_id"].notna()].drop_duplicates(["uf", "cod_municipio"]).reset_index(drop=True)


def ler_setores(
    municipios: pd.DataFrame,
    censo_geo_dir: str | Path,
    staging_dir: str | Path | None = None,
) -> pd.DataFrame:
    """Setores dos municípios do território, com bairro, renda domiciliar, centro e hexágono."""
    partes = []
    for uf, grupo in municipios.groupby("uf"):
        lidos = []
        for cod in grupo["cod_municipio"]:
            s = ler_particao_setores(
                Path(censo_geo_dir), uf=str(uf), cod_municipio=str(cod), columns=list(COLUNAS_SETOR)
            )
            if len(s):
                lidos.append(s)
        if not lidos:
            continue
        s = pd.concat(lidos, ignore_index=True)
        s = aplicar_bairro_cnefe(
            s, censo_geo_dir=censo_geo_dir, uf=str(uf), staging_dir=staging_dir
        )
        s["uf"] = str(uf)
        partes.append(s)
    if not partes:
        return pd.DataFrame(columns=[*COLUNAS_SETOR, "uf", "localidade", "renda_dom", "lat", "lng"])
    s = pd.concat(partes, ignore_index=True)
    s["cod_municipio"] = s["cod_municipio"].astype(str).str.removesuffix(".0")
    s = s.merge(municipios[["uf", "cod_municipio", "regiao_id"]], on=["uf", "cod_municipio"])
    s["localidade"] = [_localidade_do_setor(r) for _, r in s.iterrows()]
    s["renda_dom"] = [
        renda_domiciliar_setor(v, pc, mo, cs, uf, cm)
        for v, pc, mo, cs, uf, cm in zip(
            s["renda_responsavel_media_setor_2022"],
            s["renda_per_capita_setor_2022"],
            s["avg_moradores_domicilio_setor_2022"],
            s["cod_setor"],
            s["uf"],
            s["cod_municipio"],
            strict=True,
        )
    ]
    s["renda_dom"] = pd.to_numeric(s["renda_dom"], errors="coerce")
    s["lat"] = (s["bbox_miny"] + s["bbox_maxy"]) / 2
    s["lng"] = (s["bbox_minx"] + s["bbox_maxx"]) / 2
    return s


def _agregar(s: pd.DataFrame, chaves: list[str]) -> pd.DataFrame:
    s = s.assign(
        _dom_renda=s["domicilios_particulares_ocupados_setor_2022"].where(s["renda_dom"].notna()),
    )
    s["_soma_renda"] = s["renda_dom"] * s["_dom_renda"]
    g = (
        s.groupby(chaves, dropna=False)
        .agg(
            populacao=("pop_total_setor_2022", "sum"),
            area_km2=("area_setor_km2_ibge", "sum"),
            _soma_renda=("_soma_renda", "sum"),
            _dom_renda=("_dom_renda", "sum"),
            n_setores=("cod_setor", "size"),
        )
        .reset_index()
    )
    g["renda_dom"] = g["_soma_renda"] / g["_dom_renda"].where(g["_dom_renda"] > 0)
    g["densidade"] = g["populacao"] / g["area_km2"].where(g["area_km2"] > 0)
    return g.drop(columns=["_soma_renda", "_dom_renda"])


def visao_municipios(setores: pd.DataFrame, mercado: pd.DataFrame, master: Master) -> pd.DataFrame:
    """Uma linha por município do território, em ordem de população (a tabela da Visão Geral)."""
    g = _agregar(setores, ["regiao_id", "uf", "cod_municipio", "nome_municipio"])
    m = mercado.assign(regiao_id=atribuir_regiao(mercado, master))
    m = m[m["regiao_id"].notna()].copy()
    m["cod_municipio"] = m["cod_municipio"].astype(str).str.removesuffix(".0")
    esp = (
        m.groupby(["uf", "cod_municipio"])["oferta_efetiva_disponivel"].sum().rename("espaco_livre")
    )
    g = g.merge(esp.reset_index(), on=["uf", "cod_municipio"], how="left")
    nomes = {r.id: r.nome for r in master.regioes}
    g["regiao_nome"] = g["regiao_id"].map(nomes)
    return g.sort_values("populacao", ascending=False).reset_index(drop=True)


def bairros(setores: pd.DataFrame, master: Master, hexes_com_ultra: set[str]) -> pd.DataFrame:
    """Uma linha por bairro (localidade) do território, com `ocupado` = já tem Ultra no bairro.

    Ocupado pela regra do Relatório Municipal: o hexágono da unidade ganha o nome do bairro de
    mais moradores dentro dele, e esse bairro conta como ocupado.
    """
    s = setores[setores["localidade"].notna()].copy()
    if s.empty:
        return pd.DataFrame(
            columns=[
                "regiao_id",
                "uf",
                "cod_municipio",
                "nome_municipio",
                "localidade",
                "populacao",
                "area_km2",
                "renda_dom",
                "densidade",
                "ocupado",
                "regiao_nome",
            ]
        )
    s["hex_id"] = [
        h3.latlng_to_cell(float(la), float(lo), H3_RES)
        if np.isfinite(la) and np.isfinite(lo)
        else None
        for la, lo in zip(s["lat"], s["lng"], strict=True)
    ]
    pop_hex = (
        s.groupby(["hex_id", "uf", "cod_municipio", "localidade"])["pop_total_setor_2022"]
        .sum()
        .reset_index()
    )
    dominante = pop_hex.sort_values(
        ["hex_id", "pop_total_setor_2022", "localidade"], ascending=[True, False, True]
    )
    dominante = dominante.drop_duplicates("hex_id")
    ocupados = set(
        map(
            tuple,
            dominante.loc[
                dominante["hex_id"].isin(hexes_com_ultra), ["uf", "cod_municipio", "localidade"]
            ].to_numpy(),
        )
    )
    g = _agregar(s, ["regiao_id", "uf", "cod_municipio", "nome_municipio", "localidade"])
    g["ocupado"] = [
        (u, c, b) in ocupados
        for u, c, b in zip(g["uf"], g["cod_municipio"], g["localidade"], strict=True)
    ]
    g["regiao_nome"] = g["regiao_id"].map({r.id: r.nome for r in master.regioes})
    return g.sort_values("populacao", ascending=False).reset_index(drop=True)


def top_bairros_renda(b: pd.DataFrame, n: int = 5, pop_min: int = POP_MIN_BAIRRO) -> pd.DataFrame:
    return b[b["populacao"] >= pop_min].sort_values("renda_dom", ascending=False).head(n)
