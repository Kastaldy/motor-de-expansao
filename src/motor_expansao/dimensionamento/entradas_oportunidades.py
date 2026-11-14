"""Entradas do modelo de praca por IMOVEL da aba de oportunidades, em lote (DEC-086).

O modelo de praca (DEC-078) precisa de 3 entradas do PONTO -- `pop_c10`, `dom_c10` e
`renda_pc_c10` --, tiradas da isocrona de 10 min de carro (Valhalla) e da malha de setores.
Na abertura da lista isso custaria ~0,5 s por imovel (medido em 13/11/2026 na VPS: 11.947
imoveis vivos, 8.010 coordenadas unicas, 0,54 s em media, ~1,2 h num processo, pico de
651 MB). Por isso o calculo roda a NOITE, num processo a parte (`scripts/cron/
run_entradas_oportunidades.sh`), e grava UM arquivo ao lado do `viaveis.parquet`. O site so'
aplica a formula na leitura (~8 us por imovel) e, sem a entrada do imovel, cai na curva de
densidade de sempre.

Mesmo caminho da sugestao da Viabilidade (`_entradas_c10_do_ponto` em `web/server/app.py`):
`isocrona_carro` -> `_resolver_e_carregar(geometria=isocrona)` -> `agregar_entradas_c10`.

INCREMENTAL. A chave e' a coordenada em 5 casas (~1 m), a mesma do cache da isocrona e do
token da v2; so' a coordenada que ainda nao esta no arquivo e' calculada. Linha antiga nunca
sai (anuncio que some e volta reaproveita a conta; o arquivo cresce devagar): para refazer
tudo, por exemplo depois de tiles novos do Valhalla, `--recalcular-tudo`.

Falha PERMANENTE do ponto (sem via a 300 m, area grande demais, coordenada fora da malha,
sem setor, populacao ou renda) fica gravada com o motivo e nao se repete. Falha do SERVICO
(Valhalla fora, timeout), do INSUMO (malha municipal ausente, particao de setores ausente ou
ilegivel) ou erro inesperado NAO grava nada: o ponto volta na noite seguinte. Com
`--max-falhas-seguidas` dessas falhas em sequencia o lote para (codigo 3), e o que ja foi
calculado fica salvo -- o arquivo e' regravado a cada `GRAVAR_A_CADA` pontos novos, sempre
por temporario + rename.

READ-ONLY sobre o M1 e sobre o `viaveis.parquet`; escreve SO' o arquivo de saida.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

# Casas da coordenada na chave: as mesmas do cache da isocrona e do token da v2.
CASAS_CHAVE = 5
ARQUIVO_SAIDA = "entradas_c10.parquet"
ENV_OPORTUNIDADES = "MOTOR_OPORTUNIDADES_PATH"
ENV_SAIDA = "MOTOR_OPORTUNIDADES_ENTRADAS_PATH"

STATUS_OK = "ok"
STATUS_SEM_ISOCRONA = "sem_isocrona"  # sem via a 300 m, area ou diagonal grandes demais
STATUS_SEM_MALHA = "sem_malha"  # coordenada fora da malha do IBGE / municipio sem particao
STATUS_SEM_ENTRADAS = "sem_entradas"  # sem setor, populacao ou renda na area
STATUS_COORDENADA_INVALIDA = "coordenada_invalida"
STATUS_PERMANENTES = (
    STATUS_SEM_ISOCRONA,
    STATUS_SEM_MALHA,
    STATUS_SEM_ENTRADAS,
    STATUS_COORDENADA_INVALIDA,
)

COLUNAS = (
    "lat5",
    "lng5",
    "status",
    "motivo",
    "pop_c10",
    "dom_c10",
    "renda_pc_c10",
    "n_setores",
    "renda_fonte",
    "area_km2",
    "versao_rotas",
    "calculado_em",
)

GRAVAR_A_CADA = 500
MAX_FALHAS_SEGUIDAS = 20
CODIGO_OK = 0
CODIGO_ENTRADA_INVALIDA = 2
CODIGO_SERVICO_FORA = 3


class FalhaPermanente(Exception):
    """O ponto nao tem entradas, e tentar de novo nao muda isso. `status` vai ao arquivo."""

    def __init__(self, status: str, motivo: str) -> None:
        super().__init__(motivo)
        self.status = status
        self.motivo = motivo


class FalhaDoServico(Exception):
    """O servico de rotas nao respondeu, ou um insumo do calculo (malha municipal, particao
    de setores) esta ausente ou ilegivel: nada e' gravado e o ponto volta na proxima rodada."""


def chave_coordenada(lat: Any, lng: Any) -> tuple[float, float] | None:
    """(lat, lng) em 5 casas, ou `None` se a coordenada nao for um numero finito."""
    try:
        a, b = float(lat), float(lng)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(a) and math.isfinite(b)):
        return None
    return round(a, CASAS_CHAVE), round(b, CASAS_CHAVE)


def coordenadas_da_lista(caminho: Path) -> tuple[int, list[tuple[float, float]]]:
    """(imoveis vivos, coordenadas UNICAS em 5 casas) do `viaveis.parquet`.

    Mesmo recorte da aba (`_carregar_oportunidades`): `status == "removido"` fica de fora.
    """
    import pyarrow.parquet as pq

    nomes = set(pq.read_schema(caminho).names)
    faltam = {"latitude", "longitude"} - nomes
    if faltam:
        raise ValueError(f"{caminho.name} sem as colunas {sorted(faltam)}")
    cols = [c for c in ("latitude", "longitude", "status") if c in nomes]
    df = pd.read_parquet(caminho, columns=cols)
    if "status" in df.columns:
        df = df[df["status"].astype(str).str.lower() != "removido"]
    chaves: dict[tuple[float, float], None] = {}
    for lat, lng in zip(df["latitude"], df["longitude"], strict=True):
        k = chave_coordenada(lat, lng)
        if k is not None:
            chaves.setdefault(k, None)
    return int(len(df)), list(chaves)


def ler_anterior(caminho: Path) -> pd.DataFrame:
    """O arquivo da rodada anterior (vazio se nao existir). Linha sem chave valida sai."""
    if not caminho.exists():
        return pd.DataFrame(columns=list(COLUNAS))
    df = pd.read_parquet(caminho)
    for c in COLUNAS:
        if c not in df.columns:
            df[c] = None
    df = df[list(COLUNAS)]
    return df[df["lat5"].notna() & df["lng5"].notna()].drop_duplicates(["lat5", "lng5"], keep="last")


def _tipar(df: pd.DataFrame) -> pd.DataFrame:
    """As colunas do contrato, nos tipos do contrato (o arquivo e a concatenacao)."""
    out = df.reindex(columns=list(COLUNAS)).copy()
    for c in ("lat5", "lng5", "pop_c10", "dom_c10", "renda_pc_c10", "area_km2"):
        out[c] = pd.to_numeric(out[c], errors="coerce").astype("float64")
    out["n_setores"] = pd.to_numeric(out["n_setores"], errors="coerce").astype("Int64")
    for c in ("status", "motivo", "renda_fonte", "versao_rotas", "calculado_em"):
        out[c] = out[c].astype("string")
    return out


def gravar(df: pd.DataFrame, caminho: Path) -> None:
    """Grava por temporario + rename (quem le nunca ve o arquivo pela metade)."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(f".{caminho.name}.tmp-{os.getpid()}")
    saida = _tipar(df).sort_values(["lat5", "lng5"], kind="stable").reset_index(drop=True)
    saida.to_parquet(tmp, index=False)
    try:
        # Os containers leem como usuario sem privilegio; o job roda como root (cron).
        os.chmod(tmp, 0o664)
    except OSError:
        pass
    os.replace(tmp, caminho)


def calculadora_de_producao(raiz: Path, perfil: Any) -> Callable[[float, float], dict[str, Any]]:
    """O caminho de producao (o mesmo da sugestao da Viabilidade) para um ponto."""
    from motor_expansao.api.coord import CoordenadaInvalidaError, validar_brasil
    from motor_expansao.api.errors import APIError
    from motor_expansao.api.service import Settings, _resolver_e_carregar
    from motor_expansao.dashboard.alcance_ponto import (
        AlcanceInvalido,
        RotasIndisponiveis,
        isocrona_carro,
    )
    from motor_expansao.dimensionamento.config import V2_MINUTOS_ISOCRONA
    from motor_expansao.dimensionamento.entradas_c10 import (
        EntradasC10Indisponiveis,
        agregar_entradas_c10,
    )

    cfg = Settings(
        censo_geo_dir=raiz / "outputs" / "setores_censitarios_2022_geo",
        ibge_dir=raiz / "ibge",
        ultra_dir=raiz / "ultra",
        staging_dir=raiz / "staging",
        perfil=perfil,
    )

    def calcular(lat: float, lng: float) -> dict[str, Any]:
        try:
            validar_brasil(lat, lng)
        except CoordenadaInvalidaError as exc:
            raise FalhaPermanente(STATUS_COORDENADA_INVALIDA, str(exc)) from exc
        try:
            iso = isocrona_carro(lat, lng, V2_MINUTOS_ISOCRONA)
        except RotasIndisponiveis as exc:
            raise FalhaDoServico(str(getattr(exc, "detalhe", exc))) from exc
        except AlcanceInvalido as exc:
            raise FalhaPermanente(STATUS_SEM_ISOCRONA, str(exc)) from exc
        try:
            _uf, _cod, setores = _resolver_e_carregar(lat, lng, cfg, geometria=iso.geometria)
        except APIError as exc:
            # So' o 400 depende do PONTO (coordenada fora da malha municipal). O 404
            # `base_geo_ausente` tambem sai de particao ILEGIVEL (corrompida, no meio de um
            # scp -- o incidente de Varjota/CE) e o 500 e' a malha municipal ausente: sao
            # incidentes de INSUMO, e gravar o ponto como permanente o deixaria na curva
            # de densidade ate' um `--recalcular-tudo` manual. Voltam na proxima noite.
            if int(getattr(exc, "status_code", 0)) == 400:
                raise FalhaPermanente(STATUS_SEM_MALHA, str(exc.detail)) from exc
            raise FalhaDoServico(f"{exc.codigo}: {exc.detail}") from exc
        try:
            ent = agregar_entradas_c10(setores, iso.geometria, lat, lng)
        except EntradasC10Indisponiveis as exc:
            raise FalhaPermanente(STATUS_SEM_ENTRADAS, str(exc)) from exc
        return {
            "pop_c10": float(ent.pop_c10),
            "dom_c10": float(ent.dom_c10),
            "renda_pc_c10": float(ent.renda_pc_c10),
            "n_setores": int(ent.n_setores),
            "renda_fonte": str(ent.renda_fonte),
            "area_km2": float(iso.area_km2),
            "versao_rotas": iso.versao,
        }

    return calcular


@dataclass
class Resumo:
    imoveis_vivos: int = 0
    coordenadas_unicas: int = 0
    ja_calculadas: int = 0
    pendentes: int = 0
    calculadas_agora: Counter = field(default_factory=Counter)
    falhas_do_servico: int = 0
    ultima_falha_do_servico: str | None = None
    erros_inesperados: Counter = field(default_factory=Counter)
    abortou_por_servico: bool = False
    linhas_no_arquivo: int = 0
    gravou: bool = False
    duracao_s: float = 0.0

    def como_dict(self) -> dict[str, Any]:
        return {
            "imoveis_vivos": self.imoveis_vivos,
            "coordenadas_unicas": self.coordenadas_unicas,
            "ja_calculadas": self.ja_calculadas,
            "pendentes": self.pendentes,
            "calculadas_agora": dict(self.calculadas_agora),
            "falhas_do_servico": self.falhas_do_servico,
            "ultima_falha_do_servico": self.ultima_falha_do_servico,
            "erros_inesperados": dict(self.erros_inesperados),
            "abortou_por_servico": self.abortou_por_servico,
            "linhas_no_arquivo": self.linhas_no_arquivo,
            "gravou": self.gravou,
            "duracao_s": round(self.duracao_s, 1),
        }


def _agora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def rodar(
    oportunidades: Path,
    saida: Path,
    calcular: Callable[[float, float], dict[str, Any]],
    *,
    recalcular_tudo: bool = False,
    limite: int | None = None,
    max_falhas_seguidas: int = MAX_FALHAS_SEGUIDAS,
    gravar_a_cada: int = GRAVAR_A_CADA,
    relogio: Callable[[], str] = _agora,
    log: Callable[[str], None] | None = None,
) -> Resumo:
    """Calcula as coordenadas que faltam e regrava o arquivo. Nunca apaga linha antiga."""
    inicio = time.monotonic()
    escrever = log or (lambda msg: print(msg, file=sys.stderr, flush=True))
    r = Resumo()
    r.imoveis_vivos, coords = coordenadas_da_lista(oportunidades)
    r.coordenadas_unicas = len(coords)
    # Recalcular tudo NAO comeca do zero: o arquivo antigo fica de base e cada ponto refeito
    # substitui a linha dele. Se o lote parar no meio (Valhalla fora), o que nao foi refeito
    # segue valendo, em vez de sumir da tela ate' a proxima noite.
    anterior = ler_anterior(saida)
    feitas = (
        set()
        if recalcular_tudo
        else {(float(a), float(b)) for a, b in zip(anterior["lat5"], anterior["lng5"], strict=True)}
    )
    pendentes = [k for k in coords if k not in feitas]
    r.ja_calculadas = r.coordenadas_unicas - len(pendentes)
    if limite is not None:
        pendentes = pendentes[: max(0, int(limite))]
    r.pendentes = len(pendentes)
    escrever(
        f"[entradas_oportunidades] {r.imoveis_vivos} imoveis, {r.coordenadas_unicas} "
        f"coordenadas, {r.ja_calculadas} ja calculadas, {r.pendentes} a calcular"
    )

    novas: list[dict[str, Any]] = []
    seguidas = 0

    def _gravar_parcial() -> None:
        partes = [
            d for d in (_tipar(anterior), _tipar(pd.DataFrame(novas, columns=list(COLUNAS))))
            if not d.empty
        ]
        tudo = pd.concat(partes, ignore_index=True) if partes else _tipar(anterior)
        tudo = tudo.drop_duplicates(["lat5", "lng5"], keep="last")
        gravar(tudo, saida)
        r.linhas_no_arquivo = int(len(tudo))
        r.gravou = True

    for i, (lat, lng) in enumerate(pendentes, start=1):
        linha: dict[str, Any] = {c: None for c in COLUNAS}
        linha.update({"lat5": lat, "lng5": lng, "calculado_em": relogio()})
        try:
            valores = calcular(lat, lng)
        except FalhaDoServico as exc:
            r.falhas_do_servico += 1
            r.ultima_falha_do_servico = str(exc)[:300]
            seguidas += 1
            if seguidas >= max_falhas_seguidas:
                r.abortou_por_servico = True
                escrever(f"[entradas_oportunidades] servico ou insumo fora ({exc}); parando")
                break
            continue
        except FalhaPermanente as exc:
            seguidas = 0
            linha.update({"status": exc.status, "motivo": exc.motivo[:300]})
            r.calculadas_agora[exc.status] += 1
        except Exception as exc:  # noqa: BLE001 -- lote: registra o tipo e segue
            seguidas = 0
            r.erros_inesperados[type(exc).__name__] += 1
            continue
        else:
            seguidas = 0
            linha.update(valores)
            linha["status"] = STATUS_OK
            r.calculadas_agora[STATUS_OK] += 1
        novas.append(linha)
        if gravar_a_cada and len(novas) % gravar_a_cada == 0:
            _gravar_parcial()
        if i % 200 == 0:
            gasto = time.monotonic() - inicio
            escrever(
                f"[entradas_oportunidades] {i}/{r.pendentes} em {gasto:.0f} s "
                f"(~{gasto / i:.2f} s por ponto)"
            )

    # Nada novo e o arquivo existe: nao regrava (o site so' rele quando o arquivo muda).
    if novas or not saida.exists():
        _gravar_parcial()
    else:
        r.linhas_no_arquivo = int(len(anterior))
    r.duracao_s = time.monotonic() - inicio
    return r


def _caminhos_padrao(raiz: Path) -> tuple[Path, Path]:
    oport = Path(os.environ.get(ENV_OPORTUNIDADES, str(raiz / "oportunidades" / "viaveis.parquet")))
    saida = Path(os.environ.get(ENV_SAIDA, str(oport.with_name(ARQUIVO_SAIDA))))
    return oport, saida


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m motor_expansao.dimensionamento.entradas_oportunidades",
        description="Entradas do modelo de praca por imovel da aba de oportunidades (DEC-086).",
    )
    p.add_argument("--oportunidades", type=Path, help="viaveis.parquet (padrao: o do site)")
    p.add_argument("--saida", type=Path, help=f"arquivo de saida (padrao: {ARQUIVO_SAIDA} ao lado)")
    p.add_argument("--recalcular-tudo", action="store_true", help="ignora o arquivo anterior")
    p.add_argument("--limite", type=int, default=None, help="no maximo N coordenadas novas")
    p.add_argument("--max-falhas-seguidas", type=int, default=MAX_FALHAS_SEGUIDAS)
    a = p.parse_args(list(argv) if argv is not None else None)

    from motor_expansao.perfil import resolver_perfil

    perfil = resolver_perfil()
    oport_padrao, saida_padrao = _caminhos_padrao(perfil.raiz)
    oport = a.oportunidades or oport_padrao
    saida = a.saida or (a.oportunidades.with_name(ARQUIVO_SAIDA) if a.oportunidades else saida_padrao)
    if not oport.exists():
        print(json.dumps({"erro": f"lista de imoveis ausente: {oport}"}, ensure_ascii=False))
        return CODIGO_ENTRADA_INVALIDA
    try:
        resumo = rodar(
            oport,
            saida,
            calculadora_de_producao(perfil.raiz, perfil),
            recalcular_tudo=a.recalcular_tudo,
            limite=a.limite,
            max_falhas_seguidas=a.max_falhas_seguidas,
        )
    except ValueError as exc:
        print(json.dumps({"erro": str(exc)}, ensure_ascii=False))
        return CODIGO_ENTRADA_INVALIDA
    print(json.dumps({"saida": str(saida), **resumo.como_dict()}, ensure_ascii=False))
    return CODIGO_SERVICO_FORA if resumo.abortou_por_servico else CODIGO_OK


if __name__ == "__main__":
    raise SystemExit(main())
