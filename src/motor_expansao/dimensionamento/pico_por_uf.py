"""Pico de maturação PADRÃO por estado (emenda de 2026-10-29 da DEC-078). SÓ LEITURA da rede.

O padrão nacional continua `SIM_MES_PICO_RAMPA_PADRAO` (10 meses): a curva do UNI-03, medida
nas 33 unidades da exploração e congelada em 2026-09-28. Este módulo NÃO mexe nele. O que ele
faz, uma vez por mês, é dar a cada estado com pelo menos `MINIMO_UNIDADES` unidades maduras
um padrão próprio:

    padrão do estado = 10 + arredondar(peso x (pico do estado - pico da rede))
    peso = n / (n + PESO_K)

O pico do estado e o da rede são medidos no MESMO grupo (toda unidade com a subida inteira no
dado e o nível maduro medido), descontando a época do ano. Somar a DIFERENÇA aos 10, em vez de
usar o número do estado, é a lição de 28/10/2026: o 10 vem de outro grupo (as 33), e pôr o
número de um grupo ao lado do de outro fabricou um "DF mais rápido" que não existia. O número
publicado anda no máximo `FREIO_MESES` por atualização. Sem teste de acaso, por decisão do
Vinicius em 2026-10-29 (Opção 2): o corte de 5, o peso e o freio são a proteção.

A régua é a do UNI-03 (`data/analysis/uni/uni03/protocolo_uni03.md`), portada do estudo de
28/10/2026:
- unidade ELEGÍVEL: inauguração real a partir de abr/2022 (antes disso os primeiros meses não
  estão no dado; as 4 com a data provisória de 23/08/2021 ficam fora);
- nível maduro `L`: média dos ativos dos meses de vida 11, 12 e 13 COMPLETOS (pelo menos 2);
- mês completo: 25+ dias com dado e o último dia com dado no fim do mês;
- pico: 1º mês de vida (do 1 em diante) em que a mediana de ativos/L, arredondada a 1%, chega
  a 100% (13 = não chegou no 1º ano);
- época do ano: fator A do estudo (mediana da variação mensal das maduras por mês do
  calendário, sem tendência).

Antes de publicar, um PORTÃO: o grupo da exploração (elegível, com `L` e primeiro ano fechado
até dez/2025) tem de reproduzir o pico do motor (10), pela conta BRUTA, a mesma do UNI-03.
Reprovou, nada é publicado e o arquivo anterior fica.

A base é o fechamento mensal da Visão Executiva (`rede_metricas.fechamento_mensal` sobre a
Growth): o mesmo dado que a tela mostra. READ-ONLY sobre o M1 e sobre a Growth.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
import threading
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

#: Unidades maduras que um estado precisa para ter padrão próprio (decisão de 2026-10-29).
MINIMO_UNIDADES = 5
#: `peso = n / (n + PESO_K)`: com PESO_K unidades o estado vale metade (decisão de 2026-10-29).
PESO_K = 10
#: Quanto o número publicado pode andar por atualização, em meses.
FREIO_MESES = 1
#: Primeiro mês de inauguração cuja subida inteira está no dado da Growth.
PRIMEIRA_COMPETENCIA = pd.Period("2022-04", "M")
#: Data PROVISÓRIA do cadastro (4 unidades da matriz de SP): não é a inauguração real.
INAUGURACAO_PROVISORIA = pd.Timestamp("2021-08-23")
#: O grupo do portão: primeiro ano fechado até este mês (as 33 da exploração do UNI-03).
FIM_EXPLORACAO = pd.Period("2025-12", "M")
MESES_NIVEL_MADURO = (11, 12, 13)
MINIMO_MESES_NIVEL = 2
DIAS_MES_COMPLETO = 25
#: Meses de vida a partir dos quais a unidade entra no fator da época do ano (já madura).
MES_VIDA_FATOR = 14
KMAX = 24

ARQUIVO = "pico_rampa_por_uf.json"
ESQUEMA = "pico_rampa_por_uf_v1"
ORIGEM_ESTADO = "estado"
ORIGEM_REDE = "rede"
ORIGEM_PADRAO = "padrao"


def _pico_do_motor() -> int:
    from motor_expansao.dimensionamento.config import SIM_MES_PICO_RAMPA_PADRAO

    return int(SIM_MES_PICO_RAMPA_PADRAO)


def _limites() -> tuple[int, int]:
    from motor_expansao.dimensionamento.config import (
        SIM_MES_PICO_RAMPA_MAX,
        SIM_MES_PICO_RAMPA_MIN,
    )

    return int(SIM_MES_PICO_RAMPA_MIN), int(SIM_MES_PICO_RAMPA_MAX)


# ---------------------------------------------------------------------------------------------
# A régua (portada de `verifica-pico-uf/v01_base.py` e de `pico-minimo-5/p01_minimo5.py`)
# ---------------------------------------------------------------------------------------------


def preparar(fechamento: pd.DataFrame) -> pd.DataFrame:
    """Mês de vida e mês completo refeitos das colunas CRUAS do fechamento mensal."""
    f = fechamento.copy()
    comp = pd.PeriodIndex(f["competencia"].astype(str), freq="M")
    f["_comp"] = comp
    ina = pd.to_datetime(f["inauguracao"], errors="coerce")
    f["_ina"] = ina
    ina_p = ina.dt.to_period("M")
    mv = np.full(len(f), np.nan)
    ok = ina.notna().to_numpy()
    mv[ok] = [(c - i).n for c, i in zip(comp[ok], ina_p[ok], strict=True)]
    f["_mv"] = mv
    fim_mes = comp.to_timestamp(how="end").normalize()
    dia_ref = pd.to_datetime(f["dia_ref"], errors="coerce")
    f["_completo"] = (
        pd.to_numeric(f["dias_com_dado"], errors="coerce").to_numpy() >= DIAS_MES_COMPLETO
    ) & (dia_ref.to_numpy() >= (fim_mes - pd.Timedelta(days=1)).to_numpy())
    f["ativos"] = pd.to_numeric(f["ativos"], errors="coerce")
    return f


def unidades(f: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por unidade: inauguração, UF (a mais frequente) e se a data é provisória."""
    g = f.groupby("unidade_id")
    u = pd.DataFrame(
        {
            "ina": g["_ina"].first(),
            "uf": g["uf"].agg(lambda s: s.mode().iat[0] if s.notna().any() else None),
        }
    )
    u["provisoria"] = u["ina"].eq(INAUGURACAO_PROVISORIA)
    u["ina_comp"] = u["ina"].dt.to_period("M")
    return u


def matriz_ativos(f: pd.DataFrame, ids: list[str], kmax: int = KMAX) -> pd.DataFrame:
    """Unidades x mês de vida (0..kmax) com os ativos dos meses COMPLETOS (NaN nos outros)."""
    sub = f[f["unidade_id"].isin(ids) & f["_mv"].notna() & (f["_mv"] >= 0) & (f["_mv"] <= kmax)]
    sub = sub[sub["_completo"]]
    if sub.duplicated(["unidade_id", "_mv"]).any():
        raise ValueError("duplicata unidade x mês de vida no fechamento mensal")
    m = sub.pivot(index="unidade_id", columns="_mv", values="ativos").astype(float)
    m.columns = [int(c) for c in m.columns]
    return m.reindex(index=list(ids), columns=range(0, kmax + 1))


def nivel_maduro(m: pd.DataFrame) -> pd.Series:
    v = m[list(MESES_NIVEL_MADURO)]
    return v.mean(axis=1).where(v.notna().sum(axis=1) >= MINIMO_MESES_NIVEL)


def fator_epoca_do_ano(f: pd.DataFrame) -> pd.Series:
    """Fator A do estudo: mediana da variação log mensal das maduras por mês do calendário."""
    g = f[f["_completo"]].sort_values(["unidade_id", "_comp"]).copy()
    ant = g[["unidade_id", "_comp", "ativos"]].copy()
    ant["_comp"] = ant["_comp"] + 1
    g = g.merge(ant.rename(columns={"ativos": "ant"}), on=["unidade_id", "_comp"], how="left")
    g = g[(g["_mv"] >= MES_VIDA_FATOR) & (g["ant"] > 0) & (g["ativos"] > 0)]
    if g.empty:
        return pd.Series(1.0, index=range(1, 13))
    g["dl"] = np.log(g["ativos"] / g["ant"])
    g["mes"] = g["_comp"].dt.month
    d = g.groupby("mes")["dl"].median().reindex(range(1, 13)).fillna(0.0)
    d = d - d.mean()  # tira a tendência
    s = np.cumsum(d.to_numpy())
    s = s - s.mean()
    return pd.Series(np.exp(s), index=range(1, 13))


def _arred_pct(curva: np.ndarray) -> np.ndarray:
    """Arredonda a 1% como o `resultado_uni03.md` (`f"{100*v:.0f}%"`) e devolve fração."""
    return np.array([np.nan if not np.isfinite(v) else int(f"{100 * v:.0f}") / 100 for v in curva])


def pico_da_curva(curva: np.ndarray) -> int:
    """1º mês de vida de 1 a 12 em que a curva arredondada chega a 100%; 13 se não chega."""
    c = _arred_pct(np.asarray(curva, float))
    for i, v in enumerate(c[1:13], start=1):
        if np.isfinite(v) and v >= 1.0 - 1e-12:
            return i
    return 13


def pico_do_grupo(m: pd.DataFrame, L: pd.Series, ids: list[str]) -> int:
    razoes = m.loc[ids, list(range(0, 13))].div(L.loc[ids], axis=0)
    return pico_da_curva(razoes.median(axis=0, skipna=True).to_numpy())


@dataclass(frozen=True)
class Medicao:
    """O que o mês mediu. `por_uf` só tem os estados com unidade madura."""

    n_exploracao: int
    pico_exploracao: int
    n_grupo: int
    pico_rede: int
    por_uf: dict[str, tuple[int, int]]  # uf -> (unidades maduras, pico do estado)
    competencia_corte: str
    fator_epoca: tuple[float, ...]


def medir(fechamento: pd.DataFrame) -> Medicao:
    """A régua inteira sobre o fechamento mensal da rede."""
    f = preparar(fechamento)
    u = unidades(f)
    base = u[~u["provisoria"] & u["ina"].notna() & (u["ina_comp"] >= PRIMEIRA_COMPETENCIA)]
    ids = list(base.index)
    if not ids:
        raise ValueError("nenhuma unidade elegível no fechamento mensal")
    m_bruto = matriz_ativos(f, ids)
    L_bruto = nivel_maduro(m_bruto)
    com_L = [i for i in ids if pd.notna(L_bruto.get(i))]
    exploracao = [i for i in com_L if base.at[i, "ina_comp"] + 13 <= FIM_EXPLORACAO]

    # Portão: a conta BRUTA do grupo da exploração, a do UNI-03.
    pico_exp = pico_do_grupo(m_bruto, L_bruto, exploracao) if exploracao else 13

    # Medição: o grupo inteiro, descontando a época do ano.
    fator = fator_epoca_do_ano(f)
    sem_epoca = f.copy()
    sem_epoca["ativos"] = sem_epoca["ativos"] / sem_epoca["_comp"].dt.month.map(fator).to_numpy()
    m = matriz_ativos(sem_epoca, com_L)
    L = nivel_maduro(m)
    grupo = [i for i in com_L if pd.notna(L.get(i))]
    pico_rede = pico_do_grupo(m, L, grupo) if grupo else _pico_do_motor()

    por_uf: dict[str, tuple[int, int]] = {}
    ufs = base.loc[grupo, "uf"]
    for uf in sorted({str(x) for x in ufs.dropna()}):
        do_estado = [i for i in grupo if base.at[i, "uf"] == uf]
        por_uf[uf] = (len(do_estado), pico_do_grupo(m, L, do_estado))

    completos = f.loc[f["_completo"], "_comp"]
    corte = str(completos.max()) if len(completos) else ""
    return Medicao(
        n_exploracao=len(exploracao),
        pico_exploracao=int(pico_exp),
        n_grupo=len(grupo),
        pico_rede=int(pico_rede),
        por_uf=por_uf,
        competencia_corte=corte,
        fator_epoca=tuple(float(v) for v in fator.reindex(range(1, 13))),
    )


# ---------------------------------------------------------------------------------------------
# A decisão: corte de 5, peso e freio
# ---------------------------------------------------------------------------------------------


def peso(n: int) -> float:
    return n / (n + PESO_K)


def _arredondar(x: float) -> int:
    """Meio para longe do zero (0,5 -> 1; -0,5 -> -1): o `round` do Python arredonda ao par."""
    return int(math.copysign(math.floor(abs(x) + 0.5), x))


def alvos(medicao: Medicao) -> dict[str, int]:
    """O padrão que a conta do mês pede para cada estado com o corte de 5."""
    base_motor = _pico_do_motor()
    minimo, maximo = _limites()
    saida: dict[str, int] = {}
    for uf, (n, pico_uf) in medicao.por_uf.items():
        if n < MINIMO_UNIDADES:
            continue
        ajuste = _arredondar(peso(n) * (pico_uf - medicao.pico_rede))
        saida[uf] = min(maximo, max(minimo, base_motor + ajuste))
    return saida


def aplicar_freio(alvo: dict[str, int], anterior: dict[str, int]) -> dict[str, int]:
    """Cada estado anda no máximo `FREIO_MESES` por atualização, partindo do publicado antes.

    Estado sem publicação anterior parte dos 10 do motor. Estado que saiu do corte volta aos
    10 também pelo freio, um mês por vez.
    """
    base_motor = _pico_do_motor()
    publicado: dict[str, int] = {}
    for uf in sorted(set(alvo) | set(anterior)):
        destino = alvo.get(uf, base_motor)
        antes = anterior.get(uf, base_motor)
        passo = max(-FREIO_MESES, min(FREIO_MESES, destino - antes))
        novo = antes + passo
        if novo != base_motor or uf in alvo:
            publicado[uf] = novo
    return publicado


def montar_artefato(
    medicao: Medicao,
    publicado: dict[str, int],
    alvo: dict[str, int],
    hoje: date | None = None,
    anterior: dict[str, int] | None = None,
) -> dict[str, Any]:
    """O arquivo publicado. `anterior` (o publicado no mês passado) entra por estado, para
    o freio ser auditável: dá para ver de onde cada número partiu."""
    base_motor = _pico_do_motor()
    antes = anterior or {}
    estados = {}
    for uf, (n, pico_uf) in sorted(medicao.por_uf.items()):
        valor = publicado.get(uf, base_motor)
        estados[uf] = {
            "unidades_maduras": n,
            "pico_medido": pico_uf,
            "diferenca_para_a_rede": pico_uf - medicao.pico_rede,
            "peso": round(peso(n), 4),
            "alvo": alvo.get(uf),
            "anterior": antes.get(uf, base_motor),
            "publicado": valor,
            # Número diferente de 10 é sempre do estado, mesmo voltando aos 10 pelo freio
            # depois de sair do corte: "padrão da rede" com 9 meses seria uma contradição.
            "origem": ORIGEM_ESTADO if (uf in alvo or valor != base_motor) else ORIGEM_REDE,
        }
    for uf in sorted(set(publicado) - set(estados)):
        estados[uf] = {
            "unidades_maduras": 0,
            "anterior": antes.get(uf, base_motor),
            "publicado": publicado[uf],
            "origem": ORIGEM_ESTADO if publicado[uf] != base_motor else ORIGEM_REDE,
        }
    return {
        "esquema": ESQUEMA,
        "medido_em": (hoje or date.today()).isoformat(),
        "competencia_corte": medicao.competencia_corte,
        "pico_motor": _pico_do_motor(),
        "regra": {
            "minimo_unidades": MINIMO_UNIDADES,
            "peso_k": PESO_K,
            "freio_meses": FREIO_MESES,
        },
        "portao": {
            "unidades_exploracao": medicao.n_exploracao,
            "pico_exploracao": medicao.pico_exploracao,
        },
        "rede": {"unidades_maduras": medicao.n_grupo, "pico_medido": medicao.pico_rede},
        "fator_epoca_do_ano": [round(v, 4) for v in medicao.fator_epoca],
        "estados": estados,
    }


def publicados_do_artefato(artefato: dict[str, Any] | None) -> dict[str, int]:
    if not artefato or artefato.get("esquema") != ESQUEMA:
        return {}
    return {
        uf: int(dados["publicado"])
        for uf, dados in (artefato.get("estados") or {}).items()
        if "publicado" in dados
    }


def gravar_atomico(caminho: Path, artefato: dict[str, Any]) -> None:
    """Escreve num temporário do MESMO diretório e troca por rename: quem lê nunca vê meio
    arquivo."""
    caminho = Path(caminho)
    fd, tmp = tempfile.mkstemp(prefix=".pico_", suffix=".json", dir=caminho.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as saida:
            json.dump(artefato, saida, ensure_ascii=False, indent=2, sort_keys=True)
            saida.write("\n")
        # `mkstemp` cria o arquivo com 0600, e o job grava como root: sem isto o site e a
        # API (outro usuario) nao leriam o arquivo publicado e ficariam nos 10 em silencio.
        os.chmod(tmp, 0o644)
        os.replace(tmp, caminho)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------------------------
# A leitura (Viabilidade: site, API e planilha)
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PicoPadrao:
    """O padrão do pico para o estado do ponto, e de onde ele veio."""

    meses: int
    #: `estado` (o estado tem padrão próprio), `rede` (o estado ficou nos 10 da rede) ou
    #: `padrao` (sem medição publicada: os 10 do motor, como antes desta emenda).
    origem: str
    uf: str | None = None
    unidades_maduras: int | None = None
    competencia_corte: str | None = None

    def para_payload(self) -> dict[str, Any]:
        return {
            "meses": self.meses,
            "origem": self.origem,
            "uf": self.uf,
            "unidades_maduras": self.unidades_maduras,
            "competencia_corte": self.competencia_corte,
        }


_CACHE: dict[str, tuple[float, dict[str, Any] | None]] = {}
_TRAVA = threading.Lock()


def ler_artefato(staging_dir: Path | str) -> dict[str, Any] | None:
    """O artefato publicado, relido quando o arquivo MUDA (mtime): publicar não exige restart.

    Ausente, ilegível ou de outro esquema = `None`, e a Viabilidade segue nos 10 do motor.
    """
    caminho = Path(staging_dir) / ARQUIVO
    try:
        mtime = caminho.stat().st_mtime
    except OSError:
        return None
    chave = str(caminho)
    with _TRAVA:
        guardado = _CACHE.get(chave)
        if guardado is not None and guardado[0] == mtime:
            return guardado[1]
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        if not isinstance(dados, dict) or dados.get("esquema") != ESQUEMA:
            dados = None
    except (OSError, ValueError):
        dados = None
    with _TRAVA:
        _CACHE[chave] = (mtime, dados)
    return dados


def limpar_cache() -> None:
    with _TRAVA:
        _CACHE.clear()


def pico_padrao(uf: str | None, staging_dir: Path | str) -> PicoPadrao:
    """O padrão do pico para o estado `uf`. Sem medição publicada: os 10 do motor."""
    base_motor = _pico_do_motor()
    artefato = ler_artefato(staging_dir)
    if artefato is None:
        return PicoPadrao(meses=base_motor, origem=ORIGEM_PADRAO)
    corte = artefato.get("competencia_corte") or None
    sigla = (uf or "").strip().upper() or None
    dados = (artefato.get("estados") or {}).get(sigla) if sigla else None
    if not dados:
        return PicoPadrao(
            meses=base_motor,
            origem=ORIGEM_REDE,
            uf=sigla,
            unidades_maduras=0,
            competencia_corte=corte,
        )
    minimo, maximo = _limites()
    try:
        meses = min(maximo, max(minimo, int(dados.get("publicado", base_motor))))
    except (TypeError, ValueError):
        meses = base_motor
    origem = ORIGEM_ESTADO if dados.get("origem") == ORIGEM_ESTADO else ORIGEM_REDE
    return PicoPadrao(
        meses=meses,
        origem=origem,
        uf=sigla,
        unidades_maduras=int(dados.get("unidades_maduras") or 0),
        competencia_corte=corte,
    )


# ---------------------------------------------------------------------------------------------
# A rotina mensal
# ---------------------------------------------------------------------------------------------


def fechamento_da_growth(growth_parquet: Path | str) -> pd.DataFrame:
    """O fechamento mensal da Visão Executiva, sem o faturamento do Financeiro (irrelevante
    para ativos)."""
    from motor_expansao.dashboard import rede_metricas

    return rede_metricas.fechamento_mensal(rede_metricas.carregar_base(Path(growth_parquet)))


def rodar(
    growth_parquet: Path | str,
    saida: Path | str,
    *,
    publicar: bool = True,
    hoje: date | None = None,
) -> tuple[int, dict[str, Any] | None, Medicao]:
    """Mede, aplica corte, peso e freio e (com `publicar`) grava. Devolve (código, artefato,
    medição); código 0 = publicado (ou pronto, no modo seco), 2 = portão reprovado."""
    medicao = medir(fechamento_da_growth(growth_parquet))
    if medicao.pico_exploracao != _pico_do_motor():
        return 2, None, medicao
    saida = Path(saida)
    anterior = None
    if saida.exists():
        try:
            anterior = json.loads(saida.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            anterior = None
    alvo = alvos(medicao)
    antes = publicados_do_artefato(anterior)
    publicado = aplicar_freio(alvo, antes)
    artefato = montar_artefato(medicao, publicado, alvo, hoje=hoje, anterior=antes)
    if publicar:
        gravar_atomico(saida, artefato)
    return 0, artefato, medicao


def resumo(artefato: dict[str, Any] | None, medicao: Medicao) -> str:
    """Texto curto para o log e para o aviso de ops."""
    linhas = [
        f"Pico por estado — medição até {medicao.competencia_corte or '?'}",
        f"Portão: grupo da exploração ({medicao.n_exploracao} unidades) dá {medicao.pico_exploracao} "
        f"meses; o motor usa {_pico_do_motor()}.",
        f"Rede no grupo inteiro: {medicao.pico_rede} meses ({medicao.n_grupo} unidades maduras).",
    ]
    if artefato is None:
        linhas.append("NADA PUBLICADO: o portão reprovou e o arquivo anterior fica.")
        return "\n".join(linhas)
    proprios = 0
    for uf, dados in artefato["estados"].items():
        if dados.get("origem") == ORIGEM_ESTADO or dados.get("publicado") != _pico_do_motor():
            proprios += 1
            antes = dados.get("anterior", _pico_do_motor())
            mudou = f"antes {antes}" if antes != dados["publicado"] else "sem mudança"
            linhas.append(
                f"{uf}: {dados['publicado']} meses ({mudou}; {dados.get('unidades_maduras', 0)} "
                f"unidades maduras; a conta pede {dados.get('alvo')})"
            )
    if not proprios:
        linhas.append("Nenhum estado com 5 ou mais unidades maduras: todos seguem nos 10 meses.")
    else:
        linhas.append("Os demais estados seguem nos 10 meses da rede.")
    return "\n".join(linhas)


def texto_de_falha(etapa: str) -> str:
    return (
        f"Pico por estado — a rotina mensal falhou em: {etapa}.\n"
        "Nada foi publicado: a Viabilidade segue com o arquivo anterior (ou com os 10 meses, "
        "se nunca houve publicação)."
    )


def _enviar(texto: str, stdout: bool) -> None:
    """O mesmo transporte do aviso do crescimento (bot do chat de ops)."""
    from motor_expansao.crescimento.aviso import enviar

    enviar(texto, stdout=stdout)


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--staging", type=Path, default=None, help="diretório de staging")
    parser.add_argument("--growth", type=Path, default=None, help="growth_api_historico.parquet")
    parser.add_argument("--saida", type=Path, default=None, help=f"padrão: <staging>/{ARQUIVO}")
    parser.add_argument("--seco", action="store_true", help="mede e imprime, sem gravar")
    parser.add_argument(
        "--avisar", action="store_true", help="manda o resumo ao chat de ops (no seco, imprime)"
    )
    parser.add_argument("--falha", default=None, help="só manda ao chat de ops a etapa que falhou")
    args = parser.parse_args(argv)
    if args.falha:
        _enviar(texto_de_falha(args.falha), stdout=False)
        return 0
    staging = args.staging
    if staging is None:
        from motor_expansao.perfil import resolver_perfil

        staging = resolver_perfil().raiz / "staging"
    growth = args.growth or Path(staging) / "growth_api_historico.parquet"
    saida = args.saida or Path(staging) / ARQUIVO
    if not Path(growth).exists():
        print(f"base da Growth ausente: {growth}")
        return 1
    codigo, artefato, medicao = rodar(growth, saida, publicar=not args.seco)
    texto = resumo(artefato, medicao)
    print(texto)
    if args.avisar:
        _enviar(texto, stdout=args.seco)
    if artefato is not None and args.seco:
        print(json.dumps(artefato, ensure_ascii=False, indent=2, sort_keys=True))
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
