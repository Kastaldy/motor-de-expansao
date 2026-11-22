"""Planilha dos masters + config dos territórios -> o que o piloto lê (DEC-089).

A planilha de levantamento (`Masters_Ultra_Territorios_e_Unidades.xlsx`) e a config
(`territorios.json`) são CONFIDENCIAIS e ficam fora do git. O piloto não as lê: lê três parquets
e um manifesto em `data/staging`, gerados aqui, que só carregam o que a tela mostra.

* `masters_contratos.parquet`: um master por linha, na ordem da config (nome do master, território,
  tipo de área, regiões, meta e prazo do contrato, unidades que o contrato manda contar).
* `masters_inauguradas.parquet`: as inauguradas da planilha (seção, meta e operação de cada uma,
  pelo id do master).
* `masters_pipeline.parquet`: as assinadas (fase, cidade, se estão dentro do território).
* `masters_manifesto.json`: de onde veio (arquivo, sha256, data), quando e quantas linhas.

O nome do master é o titular da aba "Masters" sem o território da frente ("DF/GO — Fulano de
Tal" vira "Fulano de Tal"; 18/11/2026, Juan: "precisa estar com o nome do master", e não o
do estado). A tela é restrita a Growth e Líderes (DEC-089), que já veem o nome do master franquia na
Visão Executiva. A aba "Masters" é lida só nas colunas "Master", "Titular / razão social" e "Tipo de
área"; o texto livre da área fica de fora, e o master vai pelo `id` da config.

Recusa (`IngestaoRecusada`) em vez de gravar meia verdade: aba ou coluna faltando, ou um master
da planilha que não está na config.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import openpyxl
import pandas as pd

from motor_expansao.masters.dados import ler_planilha_masters
from motor_expansao.masters.meta import fase_de_exibicao
from motor_expansao.masters.territorios import Master, carregar_territorios, normalizar

ARQ_CONTRATOS = "masters_contratos.parquet"
ARQ_INAUGURADAS = "masters_inauguradas.parquet"
ARQ_PIPELINE = "masters_pipeline.parquet"
ARQ_MANIFESTO = "masters_manifesto.json"
#: Versão do formato dos arquivos acima; o piloto recusa outra.
ESQUEMA = 1

COLUNAS_CONTRATOS: tuple[str, ...] = (
    "master_id",
    "nome",
    "territorio",
    "tipo_area",
    "regioes",
    "regioes_tipos",
    "nota",
    "meta_quantidade",
    "meta_por_ano",
    "meta_prazo",
    "conta_tambem",
    "ordem",
)
COLUNAS_INAUGURADAS: tuple[str, ...] = (
    "master_id",
    "unidade",
    "uf",
    "meta_master_id",
    "operacao_master_id",
)
COLUNAS_PIPELINE: tuple[str, ...] = (
    "master_id",
    "unidade",
    "cidade",
    "uf",
    "fase",
    "dentro_territorio",
)


class IngestaoRecusada(ValueError):
    """A planilha não tem o que o piloto precisa; nada é gravado."""


@dataclass(frozen=True)
class Tabelas:
    contratos: pd.DataFrame
    inauguradas: pd.DataFrame
    pipeline: pd.DataFrame
    manifesto: dict[str, Any]


def _sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def nome_do_master(titular: Any) -> str | None:
    """O titular sem o território da frente: "DF/GO — Fulano de Tal" -> "Fulano de Tal".

    Sem o travessão, o texto inteiro; vazio, None.
    """
    if titular is None:
        return None
    texto = " ".join(str(titular).split())
    if not texto:
        return None
    partes = re.split(r"\s+[—–-]\s+", texto, maxsplit=1)
    return partes[1].strip() if len(partes) == 2 and partes[1].strip() else texto


def _aba_masters(planilha: Path, masters: dict[str, Master]) -> dict[str, dict[str, str]]:
    """Da aba Masters, por id do master: o tipo de área e o nome do master (o titular sem o
    território). Lê SÓ as colunas Master, Titular e Tipo de área."""
    wb = openpyxl.load_workbook(planilha, read_only=True, data_only=True)
    try:
        if "Masters" not in wb.sheetnames:
            raise IngestaoRecusada('a planilha não tem a aba "Masters"')
        linhas = list(wb["Masters"].iter_rows(values_only=True))
    finally:
        wb.close()
    idx = next(
        (
            i
            for i, r in enumerate(linhas)
            if r and any(normalizar(v) == "tipo de area" for v in r if v is not None)
        ),
        None,
    )
    if idx is None:
        raise IngestaoRecusada('a aba "Masters" não tem a coluna "Tipo de área"')
    cab = [normalizar(v) if v is not None else "" for v in linhas[idx]]
    if "master" not in cab:
        raise IngestaoRecusada('a aba "Masters" não tem a coluna "Master"')
    i_master, i_tipo = cab.index("master"), cab.index("tipo de area")
    i_titular = next((i for i, c in enumerate(cab) if c.startswith("titular")), None)
    por_nome = {normalizar(m.nome_planilha): m.id for m in masters.values()}
    out: dict[str, dict[str, str]] = {}
    for r in linhas[idx + 1 :]:
        if not r or len(r) <= max(i_master, i_tipo) or r[i_master] is None:
            continue
        mid = por_nome.get(normalizar(r[i_master]))
        if not mid:
            continue
        campos: dict[str, str] = {}
        if r[i_tipo] is not None and str(r[i_tipo]).strip() not in ("", "—", "-"):
            campos["tipo_area"] = str(r[i_tipo]).strip()
        nome = (
            nome_do_master(r[i_titular]) if i_titular is not None and len(r) > i_titular else None
        )
        if nome:
            campos["nome_master"] = nome
        out[mid] = campos
    return out


def _dentro(valor: Any) -> bool | None:
    texto = normalizar(valor) if valor is not None else ""
    if texto in ("sim", "s"):
        return True
    if texto in ("nao", "n"):
        return False
    return None


def _ids(valores: pd.Series, por_nome: dict[str, str]) -> pd.Series:
    return valores.map(lambda v: por_nome.get(normalizar(v)) if v is not None else None)


def montar_tabelas(planilha: Path, territorios: Path, agora: datetime | None = None) -> Tabelas:
    """Lê planilha e config e devolve as tabelas do piloto; levanta `IngestaoRecusada`."""
    planilha, territorios = Path(planilha), Path(territorios)
    masters = carregar_territorios(territorios)
    try:
        inaug, pipe = ler_planilha_masters(planilha)
    except KeyError as erro:
        raise IngestaoRecusada(f"a planilha não tem a aba {erro}") from erro
    except StopIteration as erro:
        raise IngestaoRecusada('uma aba da planilha não tem a coluna "Unidade"') from erro
    for nome, df, cols in (
        ("Inauguradas", inaug, ("master_secao", "unidade", "uf", "meta", "operacao")),
        ("Pipeline", pipe, ("master", "unidade", "uf", "fase")),
    ):
        faltando = [c for c in cols if c not in df.columns]
        if faltando:
            raise IngestaoRecusada(f'a aba "{nome}" não tem as colunas {faltando}')

    por_nome = {normalizar(m.nome_planilha): m.id for m in masters.values()}
    secao = _ids(inaug["master_secao"], por_nome)
    dono = _ids(pipe["master"], por_nome)
    sem_config = sorted(
        {str(v) for v, m in zip(inaug["master_secao"], secao, strict=True) if m is None}
        | {str(v) for v, m in zip(pipe["master"], dono, strict=True) if m is None}
    )
    if sem_config:
        raise IngestaoRecusada(
            f"{len(sem_config)} master(s) da planilha fora do territorios.json: {sem_config}"
        )

    inauguradas = pd.DataFrame(
        {
            "master_id": secao,
            "unidade": inaug["unidade"].astype(str).str.strip(),
            "uf": inaug["uf"].fillna("").astype(str).str.strip().str.upper(),
            "meta_master_id": _ids(inaug["meta"], por_nome),
            "operacao_master_id": _ids(inaug["operacao"], por_nome),
        }
    )
    cidade = pipe["cidade"] if "cidade" in pipe.columns else pd.Series(None, index=pipe.index)
    dentro = (
        pipe["dentro_territorio"]
        if "dentro_territorio" in pipe.columns
        else pd.Series(None, index=pipe.index)
    )
    pipeline = pd.DataFrame(
        {
            "master_id": dono,
            "unidade": pipe["unidade"].astype(str).str.strip(),
            "cidade": cidade.map(lambda v: str(v).strip() if v else None),
            "uf": pipe["uf"].fillna("").astype(str).str.strip().str.upper(),
            "fase": pipe["fase"].map(fase_de_exibicao),
            "dentro_territorio": dentro.map(_dentro).astype(object),
        }
    )

    aba = _aba_masters(planilha, masters)
    contratos = pd.DataFrame(
        [
            {
                "master_id": m.id,
                # O nome do master (o titular); sem ele na planilha, o território.
                "nome": aba.get(m.id, {}).get("nome_master") or m.nome_exibicao,
                "territorio": m.nome_exibicao,
                "tipo_area": aba.get(m.id, {}).get("tipo_area", ""),
                "regioes": [r.nome for r in m.regioes],
                "regioes_tipos": [r.tipo_label for r in m.regioes],
                "nota": m.nota,
                "meta_quantidade": m.meta.quantidade,
                "meta_por_ano": m.meta.por_ano,
                "meta_prazo": m.meta.prazo,
                "conta_tambem": list(m.meta.conta_tambem),
                "ordem": i,
            }
            for i, m in enumerate(masters.values())
        ],
        columns=list(COLUNAS_CONTRATOS),
    )
    contratos["meta_quantidade"] = contratos["meta_quantidade"].astype("Int64")
    contratos["meta_por_ano"] = contratos["meta_por_ano"].astype("Int64")

    agora = agora or datetime.now(UTC)
    versao = json.loads(territorios.read_text(encoding="utf-8")).get("versao")
    manifesto = {
        "esquema": ESQUEMA,
        "gerado_em": agora.isoformat(timespec="seconds"),
        "planilha": {
            "arquivo": planilha.name,
            "sha256": _sha256(planilha),
            "modificada_em": datetime.fromtimestamp(planilha.stat().st_mtime, UTC)
            .date()
            .isoformat(),
        },
        "territorios": {
            "arquivo": territorios.name,
            "sha256": _sha256(territorios),
            "versao": versao,
        },
        "contagens": {
            "masters": len(contratos),
            "inauguradas": len(inauguradas),
            "pipeline": len(pipeline),
        },
    }
    return Tabelas(contratos, inauguradas, pipeline, manifesto)


def gravar(tabelas: Tabelas, saida: Path) -> list[Path]:
    """Grava os quatro arquivos em `saida`, cada um por arquivo temporário + rename (o piloto
    nunca lê um parquet pela metade). O manifesto vai por último: ele descreve os outros três."""
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    feitos: list[Path] = []
    for nome, df in (
        (ARQ_CONTRATOS, tabelas.contratos),
        (ARQ_INAUGURADAS, tabelas.inauguradas),
        (ARQ_PIPELINE, tabelas.pipeline),
    ):
        destino = saida / nome
        tmp = destino.with_name(destino.name + ".tmp")
        df.to_parquet(tmp, index=False)
        os.replace(tmp, destino)
        feitos.append(destino)
    destino = saida / ARQ_MANIFESTO
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.write_text(json.dumps(tabelas.manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, destino)
    feitos.append(destino)
    return feitos
