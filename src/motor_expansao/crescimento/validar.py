"""Portao do artefato de crescimento: rejeita o parquet plausivel-e-errado.

Os modos de falhar que este validador mata sao os do README dos geradores, todos
sem erro e sem log quando acontecem:

- `03_artefato.py` rodado sozinho recria o municipal com ~15 das 33 colunas — o
  passo 4 perde veredito, dims e series (HTTP 200, tela mutilada);
- dominio fechado quebrado (`cres_hex_classe` etc.) pinta o mapa de cinza, porque
  o SPA compara o rotulo por literal;
- `10_periodo.py` pulado deixa `cres_dims` sem o 5o campo (periodo) — a dimensao
  aparece sem "de quando ate' quando".

A regua NAO e' um schema exato de 33 nomes de proposito: coluna NOVA no artefato e'
evolucao legitima (a leitura do backend e' defensiva); o que reprova e' FALTAR o que
o piloto consome ou o TOTAL cair abaixo do minimo historico. Numeros de referencia:
docs/camada_crescimento_municipal.md (33/3 colunas, 5.571/41.135 linhas em 2026-08).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

#: O que `web/server/app.py::_COLS_CRESCIMENTO` projeta, mais o `v_classe` do
#: veredito (05). Faltar QUALQUER uma degrada uma superficie do passo 4.
COLUNAS_CONSUMIDAS_MUNICIPAL = [
    "cod6",
    "cres_chave_nome",
    "cres_tendencia",
    "cres_emp_pct",
    "cres_saldo_empresas",
    "cres_confiab",
    "cres_salario",
    "cres_salario_var",
    "cres_setor",
    "cres_uf_mediana",
    "cres_dims",
    "cres_series",
    "v_frase",
    "v_classe",
]

#: Largura minima do municipal integro. A execucao parcial (so' o 03) produz ~15;
#: o artefato completo tem 33 hoje e so' pode CRESCER sem quebrar contrato.
MIN_COLUNAS_MUNICIPAL = 30

#: Linhas: todos os municipios do IBGE (5.570 + Boa Esperanca do Norte).
MIN_LINHAS_MUNICIPAL = 5_500
MIN_LINHAS_HEX = 30_000

#: Dominios FECHADOS — identificadores SEM acento por regra permanente (CLAUDE.md
#: §2); o acento e' camada de label no backend (`_ROTULO_TEND`/`_ROTULO_CLASSE`).
DOMINIO_TENDENCIA = {"Em alta", "Em queda", "Estavel"}
DOMINIO_CONFIAB = {"alta", "media", "baixa", "muito_baixa"}
DOMINIO_HEX_CLASSE = {"Em alta", "Estavel", "Sem obra nova"}

#: Cobertura minima das colunas narrativas (medida em 2026-08: ~100%).
MIN_COBERTURA = 0.90


def _fora_do_dominio(serie: pd.Series, dominio: set[str]) -> list[str]:
    valores = set(serie.dropna().astype(str).unique())
    return sorted(valores - dominio)


def validar_municipal(df: pd.DataFrame) -> list[str]:
    """Lista de defeitos do artefato municipal ([] = integro)."""
    erros: list[str] = []
    faltam = [c for c in COLUNAS_CONSUMIDAS_MUNICIPAL if c not in df.columns]
    if faltam:
        erros.append(
            f"colunas consumidas pelo piloto ausentes: {faltam} — assinatura de "
            "execucao parcial da cadeia (rode 01..10 do comeco)"
        )
    if len(df.columns) < MIN_COLUNAS_MUNICIPAL:
        erros.append(
            f"{len(df.columns)} colunas (< {MIN_COLUNAS_MUNICIPAL}): artefato mutilado"
        )
    if len(df) < MIN_LINHAS_MUNICIPAL:
        erros.append(f"{len(df)} linhas (< {MIN_LINHAS_MUNICIPAL} municipios)")
    if "cres_tendencia" in df.columns:
        fora = _fora_do_dominio(df["cres_tendencia"], DOMINIO_TENDENCIA)
        if fora:
            erros.append(f"cres_tendencia fora do dominio fechado: {fora}")
    if "cres_confiab" in df.columns:
        fora = _fora_do_dominio(df["cres_confiab"], DOMINIO_CONFIAB)
        if fora:
            erros.append(f"cres_confiab fora do dominio fechado: {fora}")
    for col in ("v_frase", "cres_dims", "cres_series"):
        if col in df.columns:
            cobertura = float(df[col].notna().mean())
            if cobertura < MIN_COBERTURA:
                erros.append(
                    f"{col} preenchida em {cobertura:.0%} (< {MIN_COBERTURA:.0%})"
                )
    if "cres_dims" in df.columns and not df["cres_dims"].dropna().empty:
        # Bloco = nome:valor:unidade:posicao:periodo. O 5o campo so' existe se o
        # `10_periodo.py` rodou; sem ele o Detalhes mostra dimensao sem periodo.
        exemplo = str(df["cres_dims"].dropna().iloc[0])
        blocos = [b for b in exemplo.split(";") if b]
        if blocos and min(len(b.split(":")) for b in blocos) < 5:
            erros.append(
                "cres_dims sem o campo de periodo (5o) — 10_periodo.py nao rodou"
            )
    return erros


def validar_hex(df: pd.DataFrame) -> list[str]:
    """Lista de defeitos do artefato por hexagono ([] = integro)."""
    erros: list[str] = []
    # As 3 colunas do contrato: o payload do mapa consome `cres_hex_taxa` alem da
    # classe — sem ela o portao passaria e a taxa sairia nula no tooltip em silencio.
    for col in ("hex_id", "cres_hex_classe", "cres_hex_taxa"):
        if col not in df.columns:
            erros.append(f"coluna ausente no hex: {col}")
    if len(df) < MIN_LINHAS_HEX:
        erros.append(f"{len(df)} hexes (< {MIN_LINHAS_HEX})")
    if "cres_hex_classe" in df.columns:
        fora = _fora_do_dominio(df["cres_hex_classe"], DOMINIO_HEX_CLASSE)
        if fora:
            erros.append(
                f"cres_hex_classe fora do dominio fechado: {fora} — o SPA compara "
                "por literal e pintaria a camada de cinza"
            )
    return erros


def validar_par(municipal: Path, hexes: Path) -> list[str]:
    erros: list[str] = []
    if not municipal.exists():
        erros.append(f"artefato municipal ausente: {municipal}")
    else:
        erros += [f"municipal: {e}" for e in validar_municipal(pd.read_parquet(municipal))]
    if not hexes.exists():
        erros.append(f"artefato hex ausente: {hexes}")
    else:
        erros += [f"hex: {e}" for e in validar_hex(pd.read_parquet(hexes))]
    return erros


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--municipal", required=True, type=Path)
    ap.add_argument("--hex", dest="hexes", required=True, type=Path)
    args = ap.parse_args(argv)
    erros = validar_par(args.municipal, args.hexes)
    if erros:
        for e in erros:
            print(f"FALHA: {e}")
        return 4
    print("artefatos integros (colunas consumidas, dominios e cobertura OK)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
