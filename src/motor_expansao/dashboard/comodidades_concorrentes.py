"""Comodidades das concorrentes por academia — o que cada uma OFERECE, por canal.

O coletor (repositório GymScraping, `Comodidades/comodidades_concorrentes.csv`) junta numa
tabela só duas leituras da mesma academia, e elas NÃO dizem a mesma coisa:

- canal `recorrente`: o que a rede declara no PRÓPRIO site (fonte `site`), para quem paga
  mensalidade direto a ela;
- canal `agregador`: o que a listagem do Wellhub ou do TotalPass declara (fonte `wellhub` /
  `totalpass`), para quem chega pelo benefício.

Medido na coleta de 2026-09-29: na Gaviões, luta aparece em 93% das unidades no site e em
33% no agregador. Por isso os canais saem SEPARADOS no pino, e nunca fundidos numa lista.

**O que este dado É e o que NÃO é.** Cada item (`ITENS`) só existe como "sim" ou vazio na
fonte: a academia declara o que tem, ninguém declara o que falta. Vazio é "não declarado",
jamais "não oferece" — e é por isso que o item sai `True` ou `None`, nunca `False`.

Camada visual e READ-ONLY sobre o M1: nenhum score, ranking ou artefato oficial é tocado.
Funções puras; quem lê e grava arquivo é o script de ingestão e o piloto.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from motor_expansao.dashboard import planos_agregador

#: Nome do artefato no staging.
ARQUIVO_STAGING = "comodidades_concorrentes.parquet"

#: Canais do coletor, na ordem em que a ficha os mostra.
CANAIS: tuple[str, ...] = ("recorrente", "agregador")

#: Itens que o coletor resume em coluna própria ("sim" ou vazio).
ITENS: tuple[str, ...] = (
    "musculacao",
    "luta",
    "armario",
    "chuveiro",
    "vestiario",
    "massagem",
    "cadeira_massagem",
)

#: Camada de LABEL dos itens (CLAUDE.md §2): o valor bruto não tem acento, o rótulo tem.
#: Espelha `ROTULO_COMODIDADE` do front (`web/src/lib/ficha-unidade.ts`); é o que o PDF imprime.
ROTULO_ITEM: dict[str, str] = {
    "musculacao": "Musculação",
    "luta": "Lutas",
    "armario": "Armário",
    "chuveiro": "Chuveiro",
    "vestiario": "Vestiário",
    "massagem": "Massagem",
    "cadeira_massagem": "Cadeira de massagem",
}

COLUNAS_OBRIGATORIAS: tuple[str, ...] = (
    "canal",
    "fonte",
    "marca",
    "nome",
    "latitude",
    "longitude",
    *ITENS,
    "comodidades",
    "data_coleta",
)

#: Pino casa com a linha do coletor a até esta distância — a mesma régua de
#: `planos_agregador.CASAR_PINO_M`.
CASAR_PINO_M = 60.0
#: Quando a REDE do pino e a marca da linha são a mesma, o raio alarga: o agregador publica
#: outro pino para o mesmo endereço, e só o raio curto leria "esta unidade não foi coletada".
#: É o raio ampliado de mesma rede da DEC-062.
CASAR_MESMA_REDE_M = 300.0


def _chave(texto: object) -> str:
    """Slug de comparação: sem acento, minúsculo e só com letras e dígitos."""
    if texto is None or (isinstance(texto, float) and np.isnan(texto)):
        return ""
    bruto = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in bruto if c.isalnum() and not unicodedata.combining(c)).lower()


def _distancias_m(lat: float, lng: float, lats: np.ndarray, lngs: np.ndarray) -> np.ndarray:
    raio_terra = 6_371_008.8
    p1, p2 = np.radians(lat), np.radians(lats)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lngs - lng) / 2) ** 2
    return 2 * raio_terra * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def _texto(coluna: pd.Series) -> pd.Series:
    return coluna.fillna("").astype(str).str.strip()


def _lista(texto: object) -> list[str]:
    return [parte.strip() for parte in str(texto or "").split(",") if parte.strip()]


def normalizar(bruto: pd.DataFrame) -> pd.DataFrame:
    """CSV cru do coletor -> quadro do staging. Levanta `ValueError` se faltar coluna do contrato.

    Sai uma linha por academia e canal, com coordenada numérica. Linha marcada `pendente` na
    coluna `csv` fica de fora: é coordenada REPROVADA na auditoria do coletor, e o casamento
    aqui é por distância.
    """
    faltam = [c for c in COLUNAS_OBRIGATORIAS if c not in bruto.columns]
    if faltam:
        raise ValueError(f"CSV de comodidades sem as colunas {faltam}")
    canal = _texto(bruto["canal"]).str.lower()
    fora = sorted(set(canal) - set(CANAIS))
    if fora:
        raise ValueError(f"CSV de comodidades com canal desconhecido: {fora} (esperado: {list(CANAIS)})")

    def opcional(coluna: str) -> pd.Series:
        return _texto(bruto[coluna]) if coluna in bruto.columns else pd.Series("", index=bruto.index)

    saida = pd.DataFrame(
        {
            "canal": canal,
            "fonte": _texto(bruto["fonte"]).str.lower(),
            "marca": _texto(bruto["marca"]),
            "nome": _texto(bruto["nome"]),
            "lat": pd.to_numeric(bruto["latitude"], errors="coerce"),
            "lng": pd.to_numeric(bruto["longitude"], errors="coerce"),
            "uf": opcional("uf").str.upper(),
            **{item: _texto(bruto[item]).str.lower().eq("sim") for item in ITENS},
            "comodidades": _texto(bruto["comodidades"]),
            "atividades": opcional("atividades"),
            "slug": opcional("slug"),
            "data_coleta": _texto(bruto["data_coleta"]),
        }
    )
    if "csv" in bruto.columns:
        saida = saida[_texto(bruto["csv"]).str.lower() != "pendente"]
    return saida.dropna(subset=["lat", "lng"]).reset_index(drop=True)


def _canal_do_pino(linha: pd.Series) -> dict[str, Any]:
    return {
        "fonte": str(linha["fonte"]),
        "nome": str(linha["nome"]),
        # `True` ou `None`: a fonte declara o que tem, nunca o que falta.
        "itens": {item: (True if bool(linha[item]) else None) for item in ITENS},
        "lista": _lista(linha["comodidades"]),
        "atividades": _lista(linha["atividades"]),
        "data_coleta": str(linha["data_coleta"]) or None,
    }


def anexar_comodidades(
    pinos: list[dict[str, Any]],
    comodidades: pd.DataFrame | None,
    *,
    casar_m: float = CASAR_PINO_M,
    mesma_rede_m: float = CASAR_MESMA_REDE_M,
) -> list[dict[str, Any]]:
    """Anexa a cada pino do mapa o que a academia oferece, um bloco por canal.

    `pino["comodidades"]` sai em três estados que a tela distingue:

    - `None`: a base não foi ingerida — "indisponível";
    - `{"recorrente": None, "agregador": None}`: base presente, academia não coletada;
    - um bloco por canal casado (`fonte`, `nome`, `itens`, `lista`, `atividades`, `data_coleta`).

    Casa pela linha mais próxima do canal, a até `casar_m`. Quando a rede do pino é a marca
    da linha, vale `mesma_rede_m`; quando as duas existem e DIFEREM, a linha nunca casa — duas
    academias no mesmo shopping não emprestam comodidade uma à outra.
    """
    base = comodidades if comodidades is not None and len(comodidades) else None
    for pino in pinos:
        pino["comodidades"] = None if base is None else dict.fromkeys(CANAIS)
    if base is None:
        return pinos

    casador = _Casador(base, casar_m=casar_m, mesma_rede_m=mesma_rede_m)
    for pino in pinos:
        for canal in CANAIS:
            i = casador.mais_proxima(pino, casador.canais == canal)
            if i is not None:
                pino["comodidades"][canal] = _canal_do_pino(base.iloc[i])
    return pinos


class _Casador:
    """A régua de casamento pino -> linha do coletor, uma só para comodidade e para plano."""

    def __init__(self, base: pd.DataFrame, *, casar_m: float, mesma_rede_m: float) -> None:
        self.lats = base["lat"].to_numpy(dtype=float)
        self.lngs = base["lng"].to_numpy(dtype=float)
        self.marcas = base["marca"].map(_chave).to_numpy()
        self.canais = base["canal"].to_numpy()
        self.fontes = base["fonte"].to_numpy()
        self.casar_m = casar_m
        self.mesma_rede_m = mesma_rede_m

    def mais_proxima(self, pino: dict[str, Any], recorte: np.ndarray) -> int | None:
        """Índice da linha aceita mais próxima do pino dentro do `recorte`, ou `None`."""
        if pino.get("lat") is None or pino.get("lng") is None:
            return None
        rede = _chave(pino.get("rede"))
        d = _distancias_m(float(pino["lat"]), float(pino["lng"]), self.lats, self.lngs)
        mesma_rede = (self.marcas == rede) & (rede != "")
        outra_rede = (self.marcas != "") & (rede != "") & ~mesma_rede
        aceita = ~outra_rede & (d <= np.where(mesma_rede, self.mesma_rede_m, self.casar_m))
        candidatas = np.flatnonzero(aceita & recorte)
        return int(candidatas[np.argmin(d[candidatas])]) if len(candidatas) else None


def anexar_agregadores(
    pinos: list[dict[str, Any]],
    comodidades: pd.DataFrame | None,
    planos: Mapping[str, pd.DataFrame | None],
    *,
    casar_m: float = CASAR_PINO_M,
    mesma_rede_m: float = CASAR_MESMA_REDE_M,
) -> list[dict[str, Any]]:
    """Diz em que agregadores a academia está, com o plano exigido e o preço dele.

    `pino["agregadores"]` sai `{"wellhub": bloco | None, "totalpass": bloco | None}`, com
    `bloco = {"plano", "preco", "casado_por"}`. Roda DEPOIS de `planos_agregador.anexar_planos`
    e não mexe nas chaves que ele gravou:

    - `casado_por = "ponto"`: o plano que `anexar_planos` já achou a até 60 m do pino;
    - `casado_por = "rede"`: o pino não tinha par a 60 m, mas a linha de comodidades da MESMA
      rede (raio de `mesma_rede_m`) carrega o `slug` da listagem, e o plano sai dele.

    O segundo caminho existe porque o agregador publica outro pino para o mesmo endereço.
    Medido em 2026-10-01 nos 455 pinos de cadeia a 2 km das unidades Ultra (cadastro de
    11/06, coletas de setembro): com plano em algum agregador, 202 só pelo ponto e 266 com os
    dois caminhos — 50 planos do Wellhub e 34 do TotalPass vêm da rede. `None` continua sendo
    "não identificado", nunca "não aceita".
    """
    base = comodidades if comodidades is not None and len(comodidades) else None
    casador = _Casador(base, casar_m=casar_m, mesma_rede_m=mesma_rede_m) if base is not None else None
    por_slug = {
        fonte: quadro.drop_duplicates("slug").set_index("slug")
        for fonte, quadro in planos.items()
        if quadro is not None and len(quadro)
    }
    for pino in pinos:
        blocos: dict[str, dict[str, Any] | None] = {}
        for fonte in planos_agregador.FONTES:
            sufixo = "" if fonte == "totalpass" else f"_{fonte}"
            if pino.get(f"plano{sufixo}"):
                blocos[fonte] = {
                    "plano": pino[f"plano{sufixo}"],
                    "preco": pino.get(f"preco_plano{sufixo}"),
                    "casado_por": "ponto",
                }
                continue
            blocos[fonte] = None
            if casador is None or base is None or fonte not in por_slug:
                continue
            i = casador.mais_proxima(pino, casador.fontes == fonte)
            slug = str(base["slug"].iloc[i]) if i is not None else ""
            if slug and slug in por_slug[fonte].index:
                linha = por_slug[fonte].loc[slug]
                preco = pd.to_numeric(linha["preco"], errors="coerce")
                blocos[fonte] = {
                    "plano": str(linha["plano"]),
                    "preco": round(float(preco), 2) if pd.notna(preco) else None,
                    "casado_por": "rede",
                }
        pino["agregadores"] = blocos
    return pinos
