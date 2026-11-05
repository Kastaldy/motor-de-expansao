"""Mede a régua da Síntese do Relatório Municipal na base que o PDF lê. SÓ LEITURA.

A Síntese compara a cidade com as outras cidades grandes: os tercis (p33 / mediana / p67) da
penetração e do residual por mil habitantes entre os municípios com 100 mil+ habitantes
(`_SINTESE_PENETRACAO_TERCOS` e `_SINTESE_RESIDUAL_MIL_TERCOS` em
`src/motor_expansao/dashboard/relatorio_municipal.py`). Este script refaz a conta de
`agregar_municipio` para cada município da base enriquecida
(`outputs/hexagonos_dashboard_enriquecido`, a que o PDF lê) e imprime os tercis.

A conta: penetração = consumo / (consumo + residual); residual por mil habitantes sobre a
população de setor, com recuo para a soma de `pop_total` só quando a de setor falta INTEIRA no
município. É o que `agregar_municipio` faz; não "consertar" aqui sem consertar lá.

Antes dos tercis, um PORTÃO: o município de referência (São Paulo) pela própria
`agregar_municipio` tem de bater com a conta deste script, nos MESMOS hexágonos. Sem ele, uma conta
reimplementada errada devolveria tercis plausíveis em silêncio. A base é float32 (o relatório soma
em float32 e divide em float64), então a penetração pode diferir só no arredondamento; a tolerância
é de 0,005 p.p., metade da precisão exibida. Portão reprovado = código de saída 2, e a régua não sai.

Primeira medição (emenda de 2026-10-29 da DEC-011, base da produção regenerada em 2026-10-25): 313
cidades, penetração 33,0 / 42,3 / 49,8% e residual 78 / 90 / 104 por mil habitantes.

Uso local: `MOTOR_DATA_DIR=<dados> python scripts/medir_regua_sintese.py` (ou `--base <dir>`).

Na VPS, a imagem não leva `scripts/`: o arquivo vai pelo stdin de um container AVULSO da imagem do
site (`docker run --rm -i --network none --memory 1536m --cpus 1 ... python -`), com os mounts
só-leitura do serviço `web` (`perfil.json`, o enriquecido e o `staging`, que a renda do relatório
lê) e `MOTOR_DATA_DIR=/app/data`. Nunca dentro do `motor_expansao_web`: ler a base nacional lá
disputaria a memória do site. Simulacro antes e confirmação comando a comando (CLAUDE.md §6).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

POP_MINIMA = 100_000
TOLERANCIA_PP = 0.005
REFERENCIA = ("SP", "São Paulo")
_COLUNAS = (
    "nome_municipio",
    "cidade",
    "oferta_efetiva_disponivel",
    "oferta_consumida_mercado_estimada",
    "pop_total_setor_2022",
    "pop_total",
)
_NUMERICAS = _COLUNAS[2:]


def partes_da_base(base: Path) -> list[Path]:
    """Os arquivos da base enriquecida, particionada por UF (`uf=XX/*.parquet`)."""
    return sorted(Path(base).glob("uf=*/*.parquet"))


def ler_base(partes: list[Path]) -> pd.DataFrame:
    """Só as colunas da conta, mais a UF tirada do nome da partição."""
    frames = []
    for parte in partes:
        tem = set(pq.read_schema(parte).names)
        frame = pd.read_parquet(parte, columns=[c for c in _COLUNAS if c in tem])
        frame["uf"] = parte.parent.name.split("=", 1)[1]
        frames.append(frame)
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=[*_COLUNAS, "uf"])
    for coluna in _NUMERICAS:
        if coluna not in df.columns:
            df[coluna] = float("nan")
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
    return df


def chave_municipio(nome: str) -> str:
    """A mesma normalização de `_municipio_mask`: sem espaço nas pontas e em casefold."""
    return str(nome).strip().casefold()


def agregar_por_municipio(df: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por (UF, município), com a conta de `agregar_municipio`."""
    nome = df["nome_municipio"] if "nome_municipio" in df.columns else df["cidade"]
    if "cidade" in df.columns:
        nome = nome.fillna(df["cidade"])
    grupos = df.assign(mun=nome.astype(str).str.strip().str.casefold()).groupby(["uf", "mun"])
    agg = pd.DataFrame(
        {
            "residual": grupos["oferta_efetiva_disponivel"].sum(min_count=1),
            "consumo": grupos["oferta_consumida_mercado_estimada"].sum(min_count=1),
            "pop_setor": grupos["pop_total_setor_2022"].sum(min_count=1),
            "pop_total": grupos["pop_total"].sum(min_count=1),
            "n_hex": grupos.size(),
        }
    ).astype("float64")
    agg["pop"] = agg["pop_setor"].fillna(agg["pop_total"])
    consumo = agg["consumo"].fillna(0.0)
    residual = agg["residual"].fillna(0.0)
    denominador = consumo + residual
    agg["pen"] = (100.0 * consumo / denominador).where(denominador > 0)
    agg["res_mil"] = 1000.0 * residual / agg["pop"]
    return agg


def tercos(agg: pd.DataFrame, pop_minima: float = POP_MINIMA) -> dict[str, Any]:
    """Os tercis entre as cidades com `pop_minima`+ habitantes."""
    grandes = agg[agg["pop"] >= pop_minima]
    q = [1 / 3, 0.5, 2 / 3]
    return {
        "n": int(len(grandes)),
        "penetracao": tuple(float(v) for v in grandes["pen"].quantile(q)),
        "residual_mil": tuple(float(v) for v in grandes["res_mil"].quantile(q)),
        "grandes": grandes,
    }


def portao(
    partes: list[Path], agg: pd.DataFrame, uf: str = REFERENCIA[0], nome: str = REFERENCIA[1]
) -> dict[str, Any]:
    """A conta deste script contra a FUNÇÃO do relatório, no município de referência."""
    from motor_expansao.dashboard.relatorio_municipal import _municipio_mask, agregar_municipio

    chave = (uf, chave_municipio(nome))
    if chave not in agg.index:
        return {"bate": False, "motivo": f"{nome} ({uf}) não está na base"}
    da_uf = pd.concat(
        [pd.read_parquet(p) for p in partes if p.parent.name == f"uf={uf}"], ignore_index=True
    )
    mascara = _municipio_mask(da_uf, nome)
    recorte = da_uf.loc[mascara].copy()
    oficial = float(
        agregar_municipio(recorte, nome_municipio=nome, uf=uf, df_pre_filtrado=recorte)[
            "penetracao_fitness_pct"
        ]
    )
    script = float(agg.loc[chave, "pen"])
    n_relatorio, n_script = int(mascara.sum()), int(agg.loc[chave, "n_hex"])
    bate = n_relatorio == n_script and abs(oficial - script) < TOLERANCIA_PP
    return {
        "bate": bate,
        "oficial": oficial,
        "script": script,
        "n_relatorio": n_relatorio,
        "n_script": n_script,
    }


def _br(valor: float, casas: int = 1) -> str:
    return f"{float(valor):.{casas}f}".replace(".", ",")


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--base",
        type=Path,
        default=None,
        help="diretório do enriquecido; sem ele, <raiz do perfil>/outputs/hexagonos_dashboard_enriquecido",
    )
    args = parser.parse_args(argv)
    base = args.base
    if base is None:
        from motor_expansao.perfil import resolver_perfil

        base = resolver_perfil().raiz / "outputs" / "hexagonos_dashboard_enriquecido"

    partes = partes_da_base(base)
    if not partes:
        print(f"nenhuma partição em {base}")
        return 1
    df = ler_base(partes)
    agg = agregar_por_municipio(df)
    mais_nova = time.strftime(
        "%Y-%m-%d %H:%M UTC", time.gmtime(max(p.stat().st_mtime for p in partes))
    )
    n_hex = f"{len(df):,}".replace(",", ".")
    print(
        f"base: {len(partes)} arquivos de {df['uf'].nunique()} UFs, {n_hex} hexágonos; o mais novo é de {mais_nova}"
    )

    p = portao(partes, agg)
    if not p["bate"]:
        detalhe = p.get("motivo") or (
            f"função do relatório {_br(p['oficial'], 2)}% em {p['n_relatorio']} hexágonos, "
            f"este script {_br(p['script'], 2)}% em {p['n_script']}"
        )
        print(f"portão (São Paulo): NÃO BATE ({detalhe}). A régua não sai.")
        return 2
    print(
        f"portão (São Paulo): função do relatório {_br(p['oficial'], 2)}% em {p['n_relatorio']} "
        f"hexágonos | este script {_br(p['script'], 2)}% em {p['n_script']} -> BATEM"
    )

    t = tercos(agg)
    print(f"cidades com 100 mil+ hab.: {t['n']}")
    print(f"  penetração p33 / mediana / p67: {' / '.join(_br(v) for v in t['penetracao'])}%")
    print(
        f"  residual por mil p33 / mediana / p67: {' / '.join(_br(v, 0) for v in t['residual_mil'])}"
    )

    from motor_expansao.dashboard.relatorio_municipal import (
        _SINTESE_PENETRACAO_TERCOS,
        _SINTESE_RESIDUAL_MIL_TERCOS,
    )

    grandes = t["grandes"]
    pen_p33, _, pen_p67 = _SINTESE_PENETRACAO_TERCOS
    res_p33, _, res_p67 = _SINTESE_RESIDUAL_MIL_TERCOS
    print(
        f"  com a régua em uso ({' / '.join(_br(v) for v in _SINTESE_PENETRACAO_TERCOS)}%): "
        f"'com espaço' {int((grandes['pen'] < pen_p33).sum())}, 'em desenvolvimento' "
        f"{int(((grandes['pen'] >= pen_p33) & (grandes['pen'] <= pen_p67)).sum())}, "
        f"'maduro' {int((grandes['pen'] > pen_p67).sum())}"
    )
    print(
        f"  com a régua em uso ({' / '.join(_br(v, 0) for v in _SINTESE_RESIDUAL_MIL_TERCOS)}): "
        f"'abaixo da maioria' {int((grandes['res_mil'] < res_p33).sum())}, 'na faixa típica' "
        f"{int(((grandes['res_mil'] >= res_p33) & (grandes['res_mil'] <= res_p67)).sum())}, "
        f"'acima da maioria' {int((grandes['res_mil'] > res_p67).sum())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
