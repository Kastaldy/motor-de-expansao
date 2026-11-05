"""Aluguel de referência por município e tipo de imóvel (DEC-080).

A régua sai da base de imóveis da aba Oportunidades imobiliárias (`viaveis.parquet`, o
coletor já entrega só anúncios de aluguel entre 1.200 e 3.000 m²). Medida = MEDIANA do
R$/m² (a média é puxada pelos anúncios caros: comercial 73,3 contra 53,5 de mediana).

Faixa (pedido do time imobiliário, 04/11/2026): além da mediana, o p25 e o p75 do R$/m² do
mesmo recorte. A tela e o PDF mostram a FAIXA; a mediana segue sendo o aluguel que entra na
conta quando o campo fica vazio (regra da DEC-079).

Recorte: município × tipo; abaixo de `MIN_ANUNCIOS` cai para UF × tipo e depois Brasil ×
tipo. O corte em 5 foi medido em 29/10/2026: com 5 anúncios a mediana da cidade erra 13%
no típico, e a mediana da UF no lugar dela erra 27% — cortar em 10 mandaria 48 cidades para
a régua pior.

READ-ONLY: lê o parquet do coletor, não toca M1 nem artefato nenhum.
"""

from __future__ import annotations

import math
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
    rs_m2_p25: float
    rs_m2_p75: float

    def para_dict(self) -> dict[str, object]:
        return {
            "tipo": self.tipo,
            "rs_m2": round(self.rs_m2, 2),
            "rs_m2_p25": round(self.rs_m2_p25, 2),
            "rs_m2_p75": round(self.rs_m2_p75, 2),
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
                return Referencia(tipo, hit[0], hit[1], "municipio", uf_n, nome, *hit[2:])
        if uf_n:
            hit = self._uf.get((uf_n, tipo))
            if hit and hit[1] >= MIN_ANUNCIOS:
                return Referencia(tipo, hit[0], hit[1], "uf", uf_n, None, *hit[2:])
        hit = self._br.get((tipo,))
        if hit and hit[1] >= MIN_ANUNCIOS:
            return Referencia(tipo, hit[0], hit[1], "brasil", None, None, *hit[2:])
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


def _medianas(
    df: pd.DataFrame, chaves: list[str]
) -> dict[tuple, tuple[float, int, float, float]]:
    """(mediana, n, p25, p75) por recorte."""
    if df.empty:
        return {}
    g = df.groupby(chaves)["rs_m2"].agg(
        mediana="median",
        n="size",
        p25=lambda s: s.quantile(0.25),
        p75=lambda s: s.quantile(0.75),
    )
    return {
        (k if isinstance(k, tuple) else (k,)): (float(m), int(n), float(a), float(b))
        for k, (m, n, a, b) in zip(g.index, g.itertuples(index=False), strict=True)
    }


def _arredondar(x: float) -> int:
    """Meio para cima, como o `Math.round` do front (o `round` do Python vai ao par)."""
    return math.floor(x + 0.5)


def aluguel_na_centena(rs_m2: float, m2: float) -> int:
    """R$/m² x metragem, arredondado à centena (a mesma conta da tela)."""
    return _arredondar(rs_m2 * m2 / 100.0) * 100


def faixa_mensal(ref: Referencia, m2: float) -> tuple[int, int] | None:
    """Faixa do aluguel do mês para a metragem (p25 e p75 x m²). `None` sem metragem."""
    if not (m2 and m2 > 0):
        return None
    # Do R$/m² JÁ arredondado a 2 casas, o mesmo número que a tela recebe de `para_dict`:
    # com o valor cru, perto da virada da centena a ponta saía R$ 100 diferente da tela e o
    # veredito ("dentro" x "1% abaixo") divergia.
    return (
        aluguel_na_centena(round(ref.rs_m2_p25, 2), m2),
        aluguel_na_centena(round(ref.rs_m2_p75, 2), m2),
    )


def diferenca_da_faixa_pct(aluguel: float, faixa: tuple[int, int]) -> int:
    """Distância do aluguel até a ponta mais próxima da faixa, em % dessa ponta.

    0 = dentro da faixa. Fora dela nunca devolve 0 (o arredondamento não pode dizer
    "dentro" de um aluguel que está fora). Espelho de `diferencaDaFaixaPct` no front.
    """
    minimo, maximo = faixa
    if aluguel > maximo > 0:
        return max(1, _arredondar((aluguel / maximo - 1) * 100))
    if 0 < minimo and aluguel < minimo:
        return min(-1, _arredondar((aluguel / minimo - 1) * 100))
    return 0


def texto_da_diferenca(pct: int) -> str:
    """A frase da comparação. Espelho de `textoDaDiferenca` no front."""
    if pct == 0:
        return "dentro da faixa"
    return f"{abs(pct)}% {'acima' if pct > 0 else 'abaixo'} da faixa"


def mediana_mensal(ref: Referencia, m2: float) -> int | None:
    """Aluguel mediano do mês para a metragem: o número cinza da tela (regra da DEC-079)."""
    if not (m2 and m2 > 0):
        return None
    return aluguel_na_centena(round(ref.rs_m2, 2), m2)


def diferenca_da_mediana_pct(aluguel: float, mediana: int) -> int:
    """Diferença do aluguel para a mediana, em % dela. Espelho de `diferencaDaMedianaPct`."""
    return _arredondar((aluguel / mediana - 1) * 100)


def texto_da_diferenca_mediana(pct: int) -> str:
    """A frase contra a mediana. Espelho de `textoDaDiferencaMediana` no front."""
    if pct == 0:
        return "na mediana"
    return f"{abs(pct)}% {'acima' if pct > 0 else 'abaixo'} da mediana"


def texto_da_comparacao(pct_mediana: int, pct_faixa: int) -> str:
    """As duas réguas numa linha: a mediana primeiro, a faixa depois.

    Sem o "Seu aluguel:" da tela: no PDF a linha vai DEBAIXO do valor do aluguel pedido.
    """
    return f"{texto_da_diferenca_mediana(pct_mediana)} · {texto_da_diferenca(pct_faixa)}"


_TIPO_NA_FRASE = {"galpao": "galpão", "comercial": "laje corporativa", "loja": "comercial"}
#: Rótulo de EXIBIÇÃO do tipo (decisão de Felipe, 29/10/2026). Espelho do front.
ROTULO_TIPO = {"galpao": "Galpão", "comercial": "Laje Corporativa", "loja": "Comercial"}


def texto_da_base(ref: Referencia) -> str:
    """A base em fato neutro, sem fonte, data nem adjetivo. Espelho de `textoDaBase`."""
    n = f"{ref.n_anuncios:,}".replace(",", ".")
    anuncios = f"{n} {'anúncio' if ref.n_anuncios == 1 else 'anúncios'} de {_TIPO_NA_FRASE[ref.tipo]}"
    if ref.nivel == "municipio":
        return f"Base: {anuncios} em {ref.municipio}/{ref.uf}"
    if ref.nivel == "uf":
        return f"Base: {anuncios} no estado ({ref.uf})"
    return f"Base: {anuncios} no Brasil"


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


def bloco_do_pdf(
    tabela: TabelaAluguel | None,
    tipo: str | None,
    uf: str | None,
    municipio: str | None,
    m2: float | None,
    aluguel_digitado: float | None,
) -> dict[str, object] | None:
    """O card "Aluguel de referência" do PDF, pronto para imprimir. `None` sem régua.

    Mesma consulta da tela (o front manda o tipo, a UF e o município que usou), para o PDF
    e a tela não divergirem. A comparação só existe com o aluguel DIGITADO: com o campo
    vazio a conta usa a mediana, e comparar a régua com ela mesma não diz nada.
    """
    if tabela is None or not tipo:
        return None
    ref = tabela.consultar(tipo, uf, municipio)
    faixa = faixa_mensal(ref, float(m2 or 0)) if ref is not None else None
    if ref is None or faixa is None:
        return None
    mediana = mediana_mensal(ref, float(m2 or 0))
    pct = pct_mediana = None
    if aluguel_digitado is not None and aluguel_digitado > 0:
        pct = diferenca_da_faixa_pct(float(aluguel_digitado), faixa)
        if mediana:
            pct_mediana = diferenca_da_mediana_pct(float(aluguel_digitado), mediana)
    if pct is None:
        comparacao = None
    elif pct_mediana is None:
        comparacao = texto_da_diferenca(pct)
    else:
        comparacao = texto_da_comparacao(pct_mediana, pct)
    return {
        "faixa_min": faixa[0],
        "faixa_max": faixa[1],
        "mediana": mediana,
        "rs_m2_p25": round(ref.rs_m2_p25, 2),
        "rs_m2_p75": round(ref.rs_m2_p75, 2),
        "base": texto_da_base(ref),
        "n_anuncios": ref.n_anuncios,
        # Cor do PDF: vermelho acima da faixa, âmbar acima da mediana, verde no resto.
        "diferenca_pct": pct,
        "diferenca_mediana_pct": pct_mediana,
        "comparacao": comparacao,
    }
