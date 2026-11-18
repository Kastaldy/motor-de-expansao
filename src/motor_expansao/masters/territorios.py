"""Territórios dos masters: config JSON (fora do git) -> região de cada município.

O contrato de cada master define o território em texto livre (planilha de levantamento).
Aqui ele vira dado: cada master tem uma lista de REGIÕES, e cada região é um conjunto de
UFs inteiras (com exceções) e/ou de municípios explícitos. A comparação "onde abrir mais"
é sempre ENTRE AS REGIÕES DO PRÓPRIO MASTER, nunca contra o Brasil.

O arquivo real fica em `data/ultra/masters/territorios.json` (gitignored: o levantamento é
confidencial). Formato:

    {"masters": [{
        "id": "gempro",
        "nome_planilha": "Litoral/ABC — GEMPRO",      # como aparece na planilha
        "nome_exibicao": "Litoral/ABC - GEMPRO",      # como vai no PDF
        "regioes": [
            {"id": "abcd", "nome": "ABCD Paulista", "tipo": "exclusividade",
             "municipios": {"SP": ["Santo André", "..."]}},
            {"id": "go", "nome": "Goiás", "tipo": "exclusividade", "ufs": ["GO"],
             "excluir": {"GO": ["..."]}, "nota": "texto livre"}
        ]}]}
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TIPOS_REGIAO: dict[str, str] = {
    "exclusividade": "Exclusividade",
    "preferencia": "Preferência",
    "a_definir": "A definir",
    "agrupamento": "Agrupamento",
}


def normalizar(texto: Any) -> str:
    """Chave de comparação: sem acento, minúscula, pontuação vira espaço.

    Pontuação vira espaço para "Ponta da Praia (Santos)" citar "Santos" e para
    "Santa Bárbara d'Oeste" casar com qualquer grafia do apóstrofo.
    """
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", " ", s.lower())
    return " ".join(s.split())


def _pares(bloco: Mapping[str, Iterable[str]] | None) -> frozenset[tuple[str, str]]:
    if not bloco:
        return frozenset()
    return frozenset((uf.upper(), normalizar(m)) for uf, nomes in bloco.items() for m in nomes)


@dataclass(frozen=True)
class Regiao:
    id: str
    nome: str
    tipo: str
    ufs: frozenset[str] = field(default_factory=frozenset)
    municipios: frozenset[tuple[str, str]] = field(default_factory=frozenset)
    excluir: frozenset[tuple[str, str]] = field(default_factory=frozenset)
    nota: str = ""

    @property
    def tipo_label(self) -> str:
        return TIPOS_REGIAO.get(self.tipo, self.tipo)

    @property
    def ufs_envolvidas(self) -> frozenset[str]:
        return self.ufs | {uf for uf, _ in self.municipios}

    def contem(self, uf: str, municipio: str) -> bool:
        chave = (str(uf).upper(), normalizar(municipio))
        if chave in self.excluir:
            return False
        return chave[0] in self.ufs or chave in self.municipios

    def mencionada_em(self, texto: str, uf: str | None = None) -> bool:
        """True se `texto` (nome de unidade do pipeline) cita um município desta região.

        Para região de UF inteira, basta a UF bater e o texto não citar um município excluído.
        """
        t = f" {normalizar(texto)} "
        if uf and str(uf).upper() in self.ufs:
            return not any(f" {m} " in t for u, m in self.excluir if u == str(uf).upper())
        return any(f" {m} " in t for u, m in self.municipios if uf is None or u == str(uf).upper())


@dataclass(frozen=True)
class MetaAberturas:
    """Compromisso de aberturas do contrato do master (o que a planilha traz só em texto).

    `quantidade` None = meta não informada na config. `conta_tambem`: unidades que o contrato conta
    para a meta mesmo com outra atribuição na planilha (ex.: Santos, 1ª unidade do GEMPRO).
    """

    quantidade: int | None = None
    #: Aberturas por ano (17/11, Juan: "a meta é a cada ano"); None = não informada.
    por_ano: int | None = None
    prazo: str | None = None  # AAAA-MM-DD
    conta_tambem: tuple[str, ...] = ()
    fonte: str = ""


@dataclass(frozen=True)
class Master:
    id: str
    nome_planilha: str
    nome_exibicao: str
    regioes: tuple[Regiao, ...]
    nota: str = ""
    meta: MetaAberturas = field(default_factory=MetaAberturas)

    @property
    def ufs_envolvidas(self) -> frozenset[str]:
        out: set[str] = set()
        for r in self.regioes:
            out |= r.ufs_envolvidas
        return frozenset(out)

    def regiao_de(self, uf: str, municipio: str) -> Regiao | None:
        for r in self.regioes:
            if r.contem(uf, municipio):
                return r
        return None

    def regiao_do_pipeline(self, texto: str, uf: str | None) -> Regiao | None:
        """Região citada no nome da unidade do pipeline; o município mais longo vence."""
        candidatas = [r for r in self.regioes if r.mencionada_em(texto, uf)]
        if len(candidatas) <= 1:
            return candidatas[0] if candidatas else None
        t = f" {normalizar(texto)} "

        def maior_citacao(r: Regiao) -> int:
            return max((len(m) for _, m in r.municipios if f" {m} " in t), default=0)

        return max(candidatas, key=maior_citacao)


def _regiao(d: Mapping[str, Any]) -> Regiao:
    return Regiao(
        id=str(d["id"]),
        nome=str(d["nome"]),
        tipo=str(d.get("tipo", "exclusividade")),
        ufs=frozenset(u.upper() for u in d.get("ufs", [])),
        municipios=_pares(d.get("municipios")),
        excluir=_pares(d.get("excluir")),
        nota=str(d.get("nota", "")),
    )


def _meta(d: Mapping[str, Any] | None) -> MetaAberturas:
    if not d:
        return MetaAberturas()
    q = d.get("quantidade")
    ano = d.get("por_ano")
    return MetaAberturas(
        quantidade=int(q) if q is not None else None,
        por_ano=int(ano) if ano is not None else None,
        prazo=str(d["prazo"]) if d.get("prazo") else None,
        conta_tambem=tuple(str(u) for u in d.get("conta_tambem", [])),
        fonte=str(d.get("fonte", "")),
    )


def carregar_territorios(caminho: str | Path) -> dict[str, Master]:
    """Lê o JSON de territórios e devolve {id_master: Master}."""
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    return masters_de_dict(dados)


def masters_de_dict(dados: Mapping[str, Any]) -> dict[str, Master]:
    out: dict[str, Master] = {}
    for m in dados["masters"]:
        master = Master(
            id=str(m["id"]),
            nome_planilha=str(m["nome_planilha"]),
            nome_exibicao=str(m.get("nome_exibicao", m["nome_planilha"])),
            regioes=tuple(_regiao(r) for r in m.get("regioes", [])),
            nota=str(m.get("nota", "")),
            meta=_meta(m.get("meta_aberturas")),
        )
        if master.id in out:
            raise ValueError(f"master duplicado no territorios.json: {master.id}")
        out[master.id] = master
    return out


def municipios_sem_match(
    master: Master, nomes_por_uf: Mapping[str, Iterable[str]]
) -> list[tuple[str, str, str]]:
    """Municípios citados na config que não existem na base (erro de grafia na config)."""
    conhecidos = {(uf.upper(), normalizar(n)) for uf, ns in nomes_por_uf.items() for n in ns}
    faltando = []
    for r in master.regioes:
        for par in sorted(r.municipios | r.excluir):
            if par[0] in nomes_por_uf and par not in conhecidos:
                faltando.append((r.id, par[0], par[1]))
    return faltando
