"""Regras do cadastro das unidades Ultra (`unidades_ultra_mapeadas.parquet`), numa fonte só.

Dois caminhos põem unidade no cadastro, e os dois usam ESTAS regras:

* a conta `deploy`, à mão, com `scripts/incluir_unidade_ultra.py` (roteiro em
  `docs/infra_producao.md`): regrava o parquet na VPS. Fica para mover unidade e para o caso
  forçado (unidade a menos de 200 m de outra que não é a mesma);
* o site (DEC-085): growth e líderes incluem pelo Mapa. A unidade fica no banco
  (`unidades_ultra_site`, migration 024), aparece na hora no pino e na busca, pode ser
  alterada ou removida por `PRAZO_ALTERACAO` e, no primeiro domingo depois do prazo, o cron
  de mercado a acrescenta ao parquet (`compor_cadastro`) — e daí ela chega ao mercado
  residual e ao PDF da API, pelo caminho que já existia.

Duas cópias destas regras divergiriam em silêncio (a distância mínima, o que conta como nome
repetido): por isso o script e o site importam daqui. Nada aqui toca o M1: os pins e a rede
própria são camada de apoio.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

ARQ_CADASTRO = "unidades_ultra_mapeadas.parquet"
COLUNAS_CADASTRO: tuple[str, ...] = (
    "ultra_id",
    "unidade",
    "uf",
    "cidade",
    "lat",
    "lng",
    "flag_coord_valida",
    "hex_id_res7",
)
H3_RES = 7
#: Abaixo disto a unidade nova provavelmente É a que já está no cadastro (mesmo prédio,
#: geocodificação diferente). O script aceita `--forcar-perto`; o site não força.
DIST_MIN_M = 200.0
#: Quanto tempo o site deixa alterar ou remover a unidade que incluiu. Depois disso a linha
#: congela (a trigger da 024 recusa), e é a partir daí que o cron de domingo a leva ao parquet:
#: o mercado nunca recebe uma unidade que ainda pode ser apagada.
PRAZO_ALTERACAO = timedelta(hours=24)
#: `ultra_id` das unidades que vieram do site: `site-<id da linha no banco>`. É a chave que
#: impede a mesma unidade de aparecer duas vezes quando ela já foi levada ao parquet.
PREFIXO_SITE = "site-"
TAMANHO_MAX_NOME = 120
TAMANHO_MAX_UF = 40
TAMANHO_MAX_CIDADE = 120


class Recusa(Exception):
    """Entrada que não entra no cadastro: nada é gravado."""


class Conflito(Recusa):
    """A entrada é válida, mas bate com uma unidade que já está no cadastro (nome ou ponto)."""


def distancia_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distância em metros pela fórmula do haversine (raio médio da Terra)."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def mesmo_nome(a: object, b: object) -> bool:
    """Dois nomes são a mesma unidade quando batem sem espaço nas pontas e sem caixa."""
    return str(a or "").strip().casefold() == str(b or "").strip().casefold()


def nome_ja_existe(nome: str, nomes: Iterable[object]) -> bool:
    alvo = str(nome or "").strip().casefold()
    return any(str(n or "").strip().casefold() == alvo for n in nomes)


def ultra_id_do_site(id_unidade_site: int) -> str:
    return f"{PREFIXO_SITE}{int(id_unidade_site)}"


def hexagono(lat: float, lng: float) -> str:
    import h3

    return str(h3.latlng_to_cell(float(lat), float(lng), H3_RES))


def _lado(bbox: Any, chave: str) -> float:
    return float(bbox[chave]) if isinstance(bbox, Mapping) else float(getattr(bbox, chave))


def dentro_da_caixa(lat: float, lng: float, bbox: Any) -> bool:
    """A coordenada cai na caixa do país do deploy (`perfil.json`, chave `bbox`)?

    Aceita o `Bbox` do perfil carregado (`PERFIL.bbox`) ou o dicionário cru do `perfil.json`.
    """
    return (
        _lado(bbox, "lat_min") <= lat <= _lado(bbox, "lat_max")
        and _lado(bbox, "lng_min") <= lng <= _lado(bbox, "lng_max")
    )


@dataclass(frozen=True)
class MaisPerto:
    unidade: str
    cidade: str
    uf: str
    distancia_m: float


def mais_perto(lat: float, lng: float, cadastro: pd.DataFrame) -> MaisPerto | None:
    """A unidade do cadastro mais perto do ponto (colunas `unidade`, `cidade`, `uf`, `lat`, `lng`)."""
    if cadastro is None or not len(cadastro):
        return None
    validos = cadastro.dropna(subset=["lat", "lng"])
    if not len(validos):
        return None
    dist = validos.apply(lambda r: distancia_m(lat, lng, float(r["lat"]), float(r["lng"])), axis=1)
    i = dist.idxmin()
    linha = validos.loc[i]
    return MaisPerto(
        unidade=str(linha["unidade"]),
        cidade=str(linha.get("cidade") or ""),
        uf=str(linha.get("uf") or ""),
        distancia_m=float(dist.loc[i]),
    )


def _texto(valor: object, rotulo: str, maximo: int, minimo: int = 1) -> str:
    texto = " ".join(str(valor or "").split())
    if len(texto) < minimo:
        raise Recusa(f"Preencha {rotulo}.")
    if len(texto) > maximo:
        raise Recusa(f"{rotulo[0].upper()}{rotulo[1:]} passa de {maximo} caracteres.")
    return texto


@dataclass(frozen=True)
class Inclusao:
    """O que a pessoa digitou, já limpo e conferido, e o que a tela de confirmação mostra."""

    unidade: str
    uf: str
    cidade: str
    lat: float
    lng: float
    hex_id_res7: str
    mais_perto: MaisPerto | None


def conferir_inclusao(
    *,
    unidade: object,
    uf: object,
    cidade: object,
    lat: object,
    lng: object,
    cadastro: pd.DataFrame,
    bbox: Any,
    ignorar_ultra_id: str | None = None,
) -> Inclusao:
    """Limpa e confere uma unidade nova (ou a alteração de uma do site). Recusa com `Recusa`.

    `cadastro` é o cadastro inteiro que o site vê (parquet + unidades do site ainda vivas),
    com `ultra_id`; `ignorar_ultra_id` tira dele a própria unidade numa alteração, senão ela
    seria recusada por estar a 0 m de si mesma.
    """
    # Ordem das recusas: nome, coordenada, e só então UF e cidade -- no site, as duas vêm do
    # ponto, então uma coordenada ruim tem de ser dita como coordenada, e não como "falta a UF".
    nome = _texto(unidade, "o nome da unidade", TAMANHO_MAX_NOME, minimo=2)
    try:
        la, ln = float(lat), float(lng)  # type: ignore[arg-type]
    except (TypeError, ValueError) as erro:
        raise Recusa("Coordenada inválida: use latitude e longitude em graus decimais.") from erro
    if not (math.isfinite(la) and math.isfinite(ln)):
        raise Recusa("Coordenada inválida: use latitude e longitude em graus decimais.")
    if not dentro_da_caixa(la, ln, bbox):
        raise Recusa(
            f"A coordenada {la:.6f}, {ln:.6f} fica fora do país deste site. Confira se a "
            "latitude e a longitude não estão trocadas."
        )
    sigla = _texto(uf, "a UF", TAMANHO_MAX_UF).upper()
    municipio = _texto(cidade, "a cidade", TAMANHO_MAX_CIDADE)

    outros = cadastro
    if outros is not None and len(outros) and ignorar_ultra_id is not None and "ultra_id" in outros:
        outros = outros[outros["ultra_id"].astype(str) != ignorar_ultra_id]
    if outros is not None and len(outros) and nome_ja_existe(nome, outros["unidade"]):
        raise Conflito(f"Já existe uma unidade chamada {nome!r} no cadastro.")
    perto = mais_perto(la, ln, outros) if outros is not None else None
    if perto is not None and perto.distancia_m < DIST_MIN_M:
        raise Conflito(
            f"Há uma unidade a {perto.distancia_m:.0f} m deste ponto ({perto.unidade}): pode ser a "
            f"mesma. Se não for, a inclusão a menos de {DIST_MIN_M:.0f} m é feita pelo time de "
            "tecnologia."
        )
    return Inclusao(
        unidade=nome,
        uf=sigla,
        cidade=municipio,
        lat=la,
        lng=ln,
        hex_id_res7=hexagono(la, ln),
        mais_perto=perto,
    )


@dataclass(frozen=True)
class UnidadeDoSite:
    """Uma linha de `unidades_ultra_site` (migration 024)."""

    id_unidade_site: int
    pais: str
    unidade: str
    uf: str
    cidade: str
    lat: float
    lng: float
    hex_id_res7: str
    criada_em: datetime
    id_usuario_criou: int
    nome_quem_criou: str | None = None
    alterada_em: datetime | None = None
    removida_em: datetime | None = None

    @property
    def ultra_id(self) -> str:
        return ultra_id_do_site(self.id_unidade_site)

    @property
    def prazo_ate(self) -> datetime:
        return self.criada_em + PRAZO_ALTERACAO

    def no_prazo(self, agora: datetime) -> bool:
        """Ainda dá para alterar ou remover pelo site?"""
        return self.removida_em is None and agora < self.prazo_ate

    def consolidada(self, agora: datetime) -> bool:
        """Viva e fora do prazo: é a que o cron de domingo leva ao parquet."""
        return self.removida_em is None and agora >= self.prazo_ate


def cadastro_do_site(unidades: Sequence[UnidadeDoSite]) -> pd.DataFrame:
    """As unidades VIVAS do site no formato do parquet (para unir ao cadastro na leitura)."""
    linhas = [
        {
            "ultra_id": u.ultra_id,
            "unidade": u.unidade,
            "uf": u.uf,
            "cidade": u.cidade,
            "lat": float(u.lat),
            "lng": float(u.lng),
            "flag_coord_valida": True,
            "hex_id_res7": u.hex_id_res7,
        }
        for u in sorted(unidades, key=lambda x: x.id_unidade_site)
        if u.removida_em is None
    ]
    return pd.DataFrame(linhas, columns=list(COLUNAS_CADASTRO))


def unir_ao_cadastro(base: pd.DataFrame | None, unidades: Sequence[UnidadeDoSite]) -> pd.DataFrame | None:
    """O cadastro que o site mostra: o parquet + as unidades vivas do site que ainda não estão nele.

    Depois do domingo a unidade do site está nos dois lugares, com o mesmo `ultra_id`: a cópia
    do banco sai, e vale a do parquet (que é a que o mercado e a API leem).
    """
    extra = cadastro_do_site(unidades)
    if base is None:
        return extra if len(extra) else None
    if not len(extra):
        return base
    if "ultra_id" in base.columns:
        extra = extra[~extra["ultra_id"].isin(set(base["ultra_id"].astype(str)))]
    if not len(extra):
        return base
    extra = extra[[c for c in base.columns if c in extra.columns]]
    return pd.concat([base, extra], ignore_index=True)


def compor_cadastro(
    base: pd.DataFrame,
    unidades: Sequence[UnidadeDoSite],
    *,
    pais: str,
    agora: datetime,
) -> tuple[pd.DataFrame, list[UnidadeDoSite]]:
    """O cadastro de domingo: a base INTOCADA + as unidades do site já consolidadas.

    Entram só as do país do deploy, vivas, fora do prazo de alteração e ainda ausentes do
    parquet (pelo `ultra_id`). As linhas da base não mudam e os tipos das colunas também não:
    o mesmo contrato que o `scripts/incluir_unidade_ultra.py` confere ao gravar.
    """
    if list(base.columns) != list(COLUNAS_CADASTRO):
        raise Recusa(f"colunas inesperadas no {ARQ_CADASTRO}: {list(base.columns)}")
    presentes = set(base["ultra_id"].astype(str))
    novas = sorted(
        (
            u
            for u in unidades
            if u.pais == pais and u.consolidada(agora) and u.ultra_id not in presentes
        ),
        key=lambda u: u.id_unidade_site,
    )
    if not novas:
        return base, []
    linhas = cadastro_do_site(novas)
    novo = pd.concat([base, linhas], ignore_index=True).astype(base.dtypes.to_dict())
    return novo, novas
