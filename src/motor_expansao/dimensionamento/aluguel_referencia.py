"""Aluguel de referência por município e tipo de imóvel (DEC-080).

A régua sai da base de imóveis da aba Oportunidades imobiliárias (`viaveis.parquet`, o
coletor já entrega só anúncios de aluguel entre 1.200 e 3.000 m²). Medida = MEDIANA do
R$/m² (a média é puxada pelos anúncios caros: comercial 73,3 contra 53,5 de mediana).

Recorte: município × tipo; abaixo de `MIN_ANUNCIOS` cai para UF × tipo e depois Brasil ×
tipo. O corte em 5 foi medido em 29/10/2026: com 5 anúncios a mediana da cidade erra 13%
no típico, e a mediana da UF no lugar dela erra 27% — cortar em 10 mandaria 48 cidades para
a régua pior.

READ-ONLY: lê o parquet do coletor, não toca M1 nem artefato nenhum.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

#: Mínimo de anúncios para um recorte valer (DEC-080).
MIN_ANUNCIOS = 5
#: R$/m² fora desta faixa é erro de cadastro do anúncio (7 de 12.899 em 29/10/2026).
RS_M2_MIN = 3.0
RS_M2_MAX = 400.0
#: Valores BRUTOS do tipo, como o coletor os grava. A exibição vive no front.
TIPOS: tuple[str, ...] = ("galpao", "comercial", "loja")


def normalizar_nome(nome: str | None) -> str:
    """Sem acento, maiúsculo, espaço simples — a mesma regra do `_norm_nome` do piloto."""
    if not nome:
        return ""
    s = unicodedata.normalize("NFKD", str(nome)).encode("ascii", "ignore").decode("ascii")
    return " ".join(s.upper().split())


@dataclass(frozen=True)
class Referencia:
    """Uma régua resolvida. `nivel` diz de onde ela veio: municipio, uf ou brasil."""

    tipo: str
    rs_m2: float
    n_anuncios: int
    nivel: str
    uf: str | None
    municipio: str | None

    def para_dict(self) -> dict[str, object]:
        return {
            "tipo": self.tipo,
            "rs_m2": round(self.rs_m2, 2),
            "n_anuncios": self.n_anuncios,
            "nivel": self.nivel,
            "uf": self.uf,
            "municipio": self.municipio,
        }


class TabelaAluguel:
    """Medianas pré-calculadas nos três níveis, para a consulta ser um dicionário."""

    def __init__(self, anuncios: pd.DataFrame) -> None:
        df = preparar_anuncios(anuncios)
        self.n_total = len(df)
        self._mun = _medianas(df, ["uf", "mun_norm", "tipo"])
        self._uf = _medianas(df, ["uf", "tipo"])
        self._br = _medianas(df, ["tipo"])
        # Nome de EXIBIÇÃO do município: o mais frequente na base para a chave normalizada.
        self._nome_mun = (
            df.groupby(["uf", "mun_norm"])["municipio"]
            .agg(lambda s: s.mode().iat[0])
            .to_dict()
        )

    def consultar(self, tipo: str, uf: str | None, municipio: str | None) -> Referencia | None:
        """Município × tipo -> UF × tipo -> Brasil × tipo; o primeiro com `MIN_ANUNCIOS`."""
        tipo = (tipo or "").strip().lower()
        if tipo not in TIPOS:
            return None
        uf_n = (uf or "").strip().upper() or None
        mun_n = normalizar_nome(municipio) or None
        if uf_n and mun_n:
            hit = self._mun.get((uf_n, mun_n, tipo))
            if hit and hit[1] >= MIN_ANUNCIOS:
                nome = self._nome_mun.get((uf_n, mun_n), municipio)
                return Referencia(tipo, hit[0], hit[1], "municipio", uf_n, nome)
        if uf_n:
            hit = self._uf.get((uf_n, tipo))
            if hit and hit[1] >= MIN_ANUNCIOS:
                return Referencia(tipo, hit[0], hit[1], "uf", uf_n, None)
        hit = self._br.get((tipo,))
        if hit and hit[1] >= MIN_ANUNCIOS:
            return Referencia(tipo, hit[0], hit[1], "brasil", None, None)
        return None


def preparar_anuncios(df: pd.DataFrame) -> pd.DataFrame:
    """Anúncios ativos com R$/m² válido. Aluguel e área com o mesmo fallback da aba."""
    if df.empty:
        return pd.DataFrame(columns=["uf", "municipio", "mun_norm", "tipo", "rs_m2"])
    out = df.copy()
    if "status" in out.columns:
        out = out[out["status"].astype(str).str.lower() != "removido"]
    area = _col(out, "area_relevante_m2").fillna(_col(out, "area_util_m2"))
    aluguel = _col(out, "preco_aluguel").fillna(_col(out, "preco"))
    out = out.assign(
        rs_m2=aluguel / area.where(area > 0),
        tipo=out["tipo"].astype(str).str.strip().str.lower(),
        uf=out["uf"].astype(str).str.strip().str.upper(),
        municipio=out["municipio"].astype(str).str.strip(),
    )
    out = out[out["rs_m2"].between(RS_M2_MIN, RS_M2_MAX) & out["tipo"].isin(TIPOS)]
    out = out.assign(mun_norm=out["municipio"].map(normalizar_nome))
    return out[["uf", "municipio", "mun_norm", "tipo", "rs_m2"]]


def _col(df: pd.DataFrame, nome: str) -> pd.Series:
    if nome in df.columns:
        return pd.to_numeric(df[nome], errors="coerce")
    return pd.Series(float("nan"), index=df.index)


def _medianas(df: pd.DataFrame, chaves: list[str]) -> dict[tuple, tuple[float, int]]:
    if df.empty:
        return {}
    g = df.groupby(chaves)["rs_m2"].agg(["median", "size"])
    return {
        (k if isinstance(k, tuple) else (k,)): (float(m), int(n))
        for k, (m, n) in zip(g.index, g.itertuples(index=False), strict=True)
    }


def carregar_tabela(caminho: Path) -> TabelaAluguel | None:
    """Tabela a partir do parquet do coletor; `None` sem o arquivo (API e bot não o montam)."""
    if not caminho.is_file():
        return None
    colunas = [
        "tipo", "uf", "municipio", "status", "area_relevante_m2", "area_util_m2",
        "preco_aluguel", "preco",
    ]
    import pyarrow.parquet as pq

    presentes = [c for c in colunas if c in pq.read_schema(caminho).names]
    return TabelaAluguel(pd.read_parquet(caminho, columns=presentes))
