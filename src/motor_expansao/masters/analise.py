"""Análises do relatório dos masters (funções puras sobre DataFrames).

Três perguntas, uma por seção do PDF:

1. **Onde abrir mais?** — compara as regiões do território do master entre si pelo espaço
   livre (mercado fitness menos o que concorrentes e Ultra já consomem). É ordenação
   relativa, que é o que o motor faz bem; o número de "unidades que cabem" é teto teórico,
   não previsão de alunos (DEC-009).
2. **Como estão as unidades dele?** — cada unidade contra a rede inteira na MESMA idade
   (mês de vida), porque unidade nova e madura não se comparam.
3. **O que uma Ultra nova perto fez com a unidade antiga?** — antes e depois da abertura
   da vizinha, descontada a variação da rede madura nos mesmos meses.

Nada aqui lê ou grava `score_priorizacao`, pesos ou artefatos oficiais do M1.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

import h3
import numpy as np
import pandas as pd

from motor_expansao.masters.meta import meta_do_ano
from motor_expansao.masters.territorios import Master, normalizar

# Mesma régua do residual (`pipelines.calcular_colunas_mercado.CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS`;
# a igualdade é travada por `test_a_capacidade_da_unidade_e_a_regua_do_residual_do_motor`, em
# `tests/unit/test_relatorio_masters.py`, para as duas não divergirem em silêncio).
CAPACIDADE_UNIDADE_ALUNOS = 2_500.0

MES_MADURA = 24  # a partir daqui a unidade é comparada com as maduras do mesmo mês-calendário
MES_RAMPA = 3  # antes disso não há veredito: o patamar ainda está se formando
POOL_MINIMO = 8  # menos unidades que isso na comparação -> sem percentil

VEREDITOS: dict[str, str] = {
    "acima": "Acima da rede",
    "media": "Na média da rede",
    "abaixo": "Abaixo da rede",
    "rampa": "Em rampa",
    "sem_dados": "Sem dados",
}

FORA_DO_TERRITORIO = "Fora do território"


# --------------------------------------------------------------------------- regiões


def atribuir_regiao(
    df: pd.DataFrame, master: Master, col_uf: str = "uf", col_mun: str = "nome_municipio"
) -> pd.Series:
    """`regiao_id` de cada linha (None fora do território), resolvido por par único UF×município."""
    pares = df[[col_uf, col_mun]].drop_duplicates()
    mapa: dict[tuple[object, object], str | None] = {}
    for uf, mun in pares.itertuples(index=False):
        r = master.regiao_de(str(uf), str(mun))
        mapa[(uf, mun)] = r.id if r else None
    return pd.Series(
        [mapa[(u, m)] for u, m in zip(df[col_uf], df[col_mun], strict=True)], index=df.index
    )


def comparar_regioes(
    mercado: pd.DataFrame,
    master: Master,
    concorrentes: pd.DataFrame | None = None,
    unidades_ultra: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Uma linha por região do master, na ordem de `posicao` (1 = mais espaço livre)."""
    if not master.regioes:
        return pd.DataFrame(
            columns=[
                "regiao_id",
                "regiao_nome",
                "tipo",
                "nota",
                "populacao",
                "mercado_alunos",
                "consumo_concorrentes",
                "consumo_ultra",
                "espaco_livre_alunos",
                "n_municipios",
                "n_concorrentes",
                "n_ultra",
                "pct_ocupado",
                "unidades_teoricas",
                "posicao",
            ]
        )
    m = mercado.assign(regiao_id=atribuir_regiao(mercado, master))
    m = m[m["regiao_id"].notna()]
    g = m.groupby("regiao_id").agg(
        populacao=("pop_hex_base", "sum"),
        mercado_alunos=("sam_fitness_potencial", "sum"),
        consumo_concorrentes=("oferta_consumida_mercado_estimada", "sum"),
        consumo_ultra=("oferta_consumida_ultra_estimada", "sum"),
        espaco_livre_alunos=("oferta_efetiva_disponivel", "sum"),
        n_municipios=("nome_municipio", "nunique"),
    )
    hex_regiao = m.set_index("hex_id")["regiao_id"]

    linhas = []
    for r in master.regioes:
        lin = g.loc[r.id].to_dict() if r.id in g.index else dict.fromkeys(g.columns, 0.0)
        lin.update(regiao_id=r.id, regiao_nome=r.nome, tipo=r.tipo_label, nota=r.nota)
        if concorrentes is not None:
            lin["n_concorrentes"] = int(concorrentes["hex_id_res7"].map(hex_regiao).eq(r.id).sum())
        if unidades_ultra is not None:
            lin["n_ultra"] = int(hex_das_unidades(unidades_ultra).map(hex_regiao).eq(r.id).sum())
        linhas.append(lin)
    out = pd.DataFrame(linhas)
    consumo = out["consumo_concorrentes"] + out["consumo_ultra"]
    out["pct_ocupado"] = np.where(
        out["mercado_alunos"] > 0,
        consumo / out["mercado_alunos"].where(out["mercado_alunos"] > 0),
        np.nan,
    )
    out["unidades_teoricas"] = out["espaco_livre_alunos"] / CAPACIDADE_UNIDADE_ALUNOS
    out["posicao"] = out["espaco_livre_alunos"].rank(ascending=False, method="first").astype(int)
    return out.sort_values("posicao").reset_index(drop=True)


#: "Cidade grande" na régua da ocupação: mercado fitness de 20 mil alunos ou mais (279 municípios
#: na base de 14/07/2026). Abaixo disso a ocupação oscila com uma academia a mais ou a menos.
MERCADO_CIDADE_GRANDE = 20_000.0


def referencia_ocupacao(
    mercado_brasil: pd.DataFrame, minimo: float = MERCADO_CIDADE_GRANDE
) -> dict[str, Any]:
    """Régua do país para a ocupação do mercado (redes + Ultra sobre o mercado fitness), por município.

    Devolve a mediana e a cidade mais ocupada entre as de mercado >= `minimo`, e o Brasil inteiro.
    """
    m = mercado_brasil
    g = m.groupby(["uf", "nome_municipio"])[
        [
            "sam_fitness_potencial",
            "oferta_consumida_mercado_estimada",
            "oferta_consumida_ultra_estimada",
        ]
    ].sum()
    g = g[g["sam_fitness_potencial"] >= minimo]
    oc = (g["oferta_consumida_mercado_estimada"] + g["oferta_consumida_ultra_estimada"]) / g[
        "sam_fitness_potencial"
    ]
    total = m["sam_fitness_potencial"].sum()
    brasil = (
        (m["oferta_consumida_mercado_estimada"].sum() + m["oferta_consumida_ultra_estimada"].sum())
        / total
        if total > 0
        else float("nan")
    )
    if oc.empty:
        return {
            "brasil": brasil,
            "mediana": float("nan"),
            "mais_ocupada": "-",
            "mais_ocupada_pct": float("nan"),
            "n_cidades": 0,
        }
    uf, nome = oc.idxmax()
    return {
        "brasil": float(brasil),
        "mediana": float(oc.median()),
        "mais_ocupada": str(nome),
        "mais_ocupada_pct": float(oc.max()),
        "n_cidades": int(len(oc)),
    }


def top_municipios(mercado: pd.DataFrame, master: Master, n: int = 5) -> pd.DataFrame:
    """Os `n` municípios com mais espaço livre em cada região."""
    m = mercado.assign(regiao_id=atribuir_regiao(mercado, master))
    m = m[m["regiao_id"].notna()]
    g = (
        m.groupby(["regiao_id", "nome_municipio"])
        .agg(
            mercado_alunos=("sam_fitness_potencial", "sum"),
            consumo=("oferta_consumida_mercado_estimada", "sum"),
            consumo_ultra=("oferta_consumida_ultra_estimada", "sum"),
            espaco_livre_alunos=("oferta_efetiva_disponivel", "sum"),
        )
        .reset_index()
    )
    g["pct_ocupado"] = (g["consumo"] + g["consumo_ultra"]) / g["mercado_alunos"].where(
        g["mercado_alunos"] > 0
    )
    g["unidades_teoricas"] = g["espaco_livre_alunos"] / CAPACIDADE_UNIDADE_ALUNOS
    g = g.sort_values(["regiao_id", "espaco_livre_alunos"], ascending=[True, False])
    return g.groupby("regiao_id", sort=False).head(n).reset_index(drop=True)


# --------------------------------------------------------------------------- unidades


def hex_das_unidades(unidades: pd.DataFrame) -> pd.Series:
    """Hexágono res-7 de cada unidade: a coluna `hex_id_res7` quando existe, senão o da coordenada."""
    if "hex_id_res7" in unidades.columns:
        return unidades["hex_id_res7"]
    if not {"lat", "lng"} <= set(unidades.columns):
        return pd.Series([None] * len(unidades), index=unidades.index, dtype=object)
    return pd.Series(
        [
            h3.latlng_to_cell(float(la), float(lo), 7) if pd.notna(la) and pd.notna(lo) else None
            for la, lo in zip(unidades["lat"], unidades["lng"], strict=True)
        ],
        index=unidades.index,
        dtype=object,
    )


def municipio_da_coordenada(unidades: pd.DataFrame, mercado: pd.DataFrame | None) -> pd.Series:
    """Município de cada unidade pelo hexágono da coordenada; sem ele, a cidade do cadastro.

    No cadastro, a "cidade" às vezes é o bairro (Vila Guanabara é Joinville), e a unidade caía
    "fora do território". O hexágono da coordenada, na base do motor, diz o município certo.
    """
    cadastro = unidades.get("cidade_cadastro", pd.Series(index=unidades.index, dtype=object))
    if mercado is None:
        return cadastro
    por_hex = mercado.drop_duplicates("hex_id").set_index("hex_id")["nome_municipio"]
    return hex_das_unidades(unidades).map(por_hex).fillna(cadastro)


def unidades_do_master(
    inauguradas: pd.DataFrame,
    dim: pd.DataFrame,
    master: Master,
    mercado: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Unidades que o master OPERA (coluna "Operação"), casadas com o painel por nome+UF.

    A região sai do município da coordenada (`municipio_da_coordenada`) quando há `mercado`.
    Devolve (unidades, nomes_sem_dados).
    """
    alvo = normalizar(master.nome_planilha)
    sel = inauguradas[inauguradas["operacao"].map(normalizar) == alvo]
    linhas, faltando = [], []
    for nome, uf in zip(sel["unidade"], sel["uf"], strict=True):
        hit = dim[(dim["chave_nome"] == normalizar(nome)) & (dim["uf"] == str(uf).upper())]
        if hit.empty:
            faltando.append(str(nome))
            continue
        lin = hit.iloc[0].to_dict()
        lin["nome_exibicao"] = str(nome)
        linhas.append(lin)
    un = pd.DataFrame(linhas)
    if un.empty:
        return un, faltando
    un["municipio_ref"] = municipio_da_coordenada(un, mercado)
    reg = atribuir_regiao(un, master, col_uf="uf", col_mun="municipio_ref")
    nomes = {r.id: r.nome for r in master.regioes}
    un["regiao_id"] = reg
    un["regiao_nome"] = reg.map(nomes).fillna(FORA_DO_TERRITORIO)
    return un.sort_values("inauguracao").reset_index(drop=True), faltando


def nomes_exibicao(inauguradas: pd.DataFrame, dim: pd.DataFrame) -> dict[str, str]:
    """{unidade_id: nome como está na planilha}; o painel guarda o nome em caixa alta e sem acento."""
    chave = dict(zip(inauguradas["unidade"].map(normalizar), inauguradas["unidade"], strict=False))
    return {
        uid: chave.get(k, str(nome).title())
        for uid, k, nome in zip(dim["unidade_id"], dim["chave_nome"], dim["nome"], strict=True)
    }


def base_comparavel(fato: pd.DataFrame) -> pd.DataFrame:
    """Meses fechados, depois da inauguração, com faturamento e idade conhecidos."""
    b = fato[
        fato["mes_completo"]
        & ~fato["pre_inauguracao"]
        & fato["faturamento"].notna()
        & fato["mes_vida"].notna()
        & (fato["mes_vida"] >= 1)
    ]
    return b.sort_values(["unidade_id", "competencia"])


def _pool(base: pd.DataFrame, unidade_id: str, competencia: str, mes_vida: int) -> pd.DataFrame:
    if mes_vida >= MES_MADURA:
        pool = base[(base["competencia"] == competencia) & (base["mes_vida"] >= MES_MADURA)]
    else:
        pool = base[base["mes_vida"].between(mes_vida - 1, mes_vida + 1)]
    return pool[pool["unidade_id"] != unidade_id]


def percentil_na_rede(pool: pd.Series, valor: float) -> float:
    """Percentil de `valor` dentro de `pool` (empates contam meio). NaN se o pool for pequeno."""
    pool = pool.dropna()
    if len(pool) < POOL_MINIMO or pd.isna(valor):
        return float("nan")
    return float(100.0 * ((pool < valor).mean() + 0.5 * (pool == valor).mean()))


def veredito(mes_vida: float, pct_faturamento: float) -> str:
    if pd.isna(mes_vida):
        return "sem_dados"
    if mes_vida < MES_RAMPA:
        return "rampa"
    if pd.isna(pct_faturamento):
        return "sem_dados"
    if pct_faturamento >= 75:
        return "acima"
    if pct_faturamento <= 25:
        return "abaixo"
    return "media"


def diagnostico_unidades(unidades: pd.DataFrame, fato: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por unidade: último mês fechado, médias de 3 meses e posição na rede."""
    base = base_comparavel(fato)
    linhas = []
    for u in unidades.itertuples(index=False):
        s = base[base["unidade_id"] == u.unidade_id]
        lin: dict[str, object] = {
            "unidade_id": u.unidade_id,
            "nome": u.nome_exibicao,
            "regiao_nome": u.regiao_nome,
            "inauguracao": u.inauguracao,
        }
        if s.empty:
            lin["veredito"] = "sem_dados"
            linhas.append(lin)
            continue
        ult, ult3 = s.iloc[-1], s.tail(3)
        mv = int(ult["mes_vida"])
        pool = _pool(base, u.unidade_id, ult["competencia"], mv)
        pct_fat = percentil_na_rede(pool["faturamento"], ult["faturamento"])
        lin.update(
            competencia_ref=ult["competencia"],
            mes_vida=mv,
            faturamento_ref=float(ult["faturamento"]),
            faturamento_3m=float(ult3["faturamento"].mean()),
            ativos_ref=float(ult["ativos"]),
            churn_3m=float(ult3["churn_pct"].mean()),
            nps_3m=float(ult3["nps"].mean()),
            pct_faturamento=pct_fat,
            pct_ativos=percentil_na_rede(pool["ativos"], ult["ativos"]),
            rede_faturamento_p50=float(pool["faturamento"].median()) if len(pool) else float("nan"),
            n_pool=int(pool["unidade_id"].nunique()),
            veredito=veredito(mv, pct_fat),
        )
        linhas.append(lin)
    return pd.DataFrame(linhas)


def referencia_rede(fato: pd.DataFrame, competencias: Iterable[str]) -> dict[str, float]:
    """Medianas da rede madura nos meses dados (para a régua das colunas da tabela)."""
    b = base_comparavel(fato)
    b = b[b["competencia"].isin(list(competencias)) & (b["mes_vida"] >= MES_MADURA)]
    por_unidade = b.groupby("unidade_id")[["faturamento", "ativos", "churn_pct", "nps"]].mean()
    return {c: float(por_unidade[c].median()) for c in por_unidade.columns} | {
        "n": int(len(por_unidade))
    }


# --------------------------------------------------------------------------- vizinhas


def distancia_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _serie(fato: pd.DataFrame, unidade_id: str) -> pd.DataFrame:
    s = fato[(fato["unidade_id"] == unidade_id) & fato["mes_completo"] & ~fato["pre_inauguracao"]]
    s = s.assign(periodo=pd.PeriodIndex(s["competencia"], freq="M"))
    return s.set_index("periodo").sort_index()


def efeito_vizinhas(
    unidades: pd.DataFrame,
    dim: pd.DataFrame,
    fato: pd.DataFrame,
    raio_km: float = 3.0,
    idade_min_meses: int = 12,
    meses_janela: int = 3,
    nomes: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Para cada unidade do master que já tinha `idade_min_meses` quando uma Ultra nova abriu
    a até `raio_km`: variação de alunos/faturamento entre os `meses_janela` meses antes da
    vizinha e os últimos `meses_janela` meses fechados, contra a mesma variação da rede madura.
    """
    outras = dim[dim["lat"].notna() & dim["lng"].notna() & dim["inauguracao"].notna()]
    eventos = []
    for u in unidades.itertuples(index=False):
        if pd.isna(u.lat) or pd.isna(u.inauguracao):
            continue
        for v in outras.itertuples(index=False):
            if v.unidade_id == u.unidade_id:
                continue
            if v.inauguracao <= u.inauguracao + pd.DateOffset(months=idade_min_meses):
                continue
            d = distancia_km(u.lat, u.lng, v.lat, v.lng)
            if d > raio_km:
                continue
            ev = _medir_evento(fato, u.unidade_id, v.unidade_id, v.inauguracao, meses_janela)
            if ev is None:
                continue
            nome_v = (nomes or {}).get(v.unidade_id, str(v.nome).title())
            eventos.append(
                {
                    "unidade_id": u.unidade_id,
                    "nome": u.nome_exibicao,
                    "vizinha_id": v.unidade_id,
                    "vizinha_nome": nome_v,
                    "vizinha_inauguracao": v.inauguracao,
                    "distancia_km": d,
                    **ev,
                }
            )
    return pd.DataFrame(eventos)


def _medir_evento(
    fato: pd.DataFrame, uid: str, vid: str, inaug_v: pd.Timestamp, k: int
) -> dict[str, object] | None:
    abre = pd.Period(inaug_v, freq="M")
    su = _serie(fato, uid)
    pre_p = pd.period_range(abre - k, abre - 1, freq="M")
    if su.empty or not set(pre_p).issubset(su.index):
        return None
    pos_p = su.index[-k:]
    if len(pos_p) < k or pos_p.min() < abre + k:  # vizinha precisa ter ao menos k meses de vida
        return None
    pre_u, pos_u = su.loc[pre_p], su.loc[pos_p]
    out: dict[str, object] = {
        "periodo_antes": f"{pre_p[0]}..{pre_p[-1]}",
        "periodo_depois": f"{pos_p[0]}..{pos_p[-1]}",
    }
    sv = _serie(fato, vid)
    for col in ("ativos", "faturamento"):
        a, d = pre_u[col].mean(), pos_u[col].mean()
        out[f"{col}_antes"], out[f"{col}_depois"] = float(a), float(d)
        var_u = float(d / a - 1) if a else float("nan")
        var_rede = _variacao_rede(fato, {uid, vid}, pre_p, pos_p, col)
        out[f"var_{col}"], out[f"var_{col}_rede"] = var_u, var_rede
        out[f"efeito_{col}"] = float((1 + var_u) / (1 + var_rede) - 1)
        vizinha_depois = sv.reindex(pos_p)[col].mean() if not sv.empty else float("nan")
        out[f"{col}_vizinha_depois"] = float(vizinha_depois)
        out[f"var_{col}_par"] = (
            float((d + vizinha_depois) / a - 1) if a and pd.notna(vizinha_depois) else float("nan")
        )
    return out


def _variacao_rede(
    fato: pd.DataFrame, excluir: set[str], pre_p: pd.PeriodIndex, pos_p: pd.PeriodIndex, col: str
) -> float:
    """Mediana da variação nas unidades maduras (≥12 meses no início da janela) com os dois períodos completos."""
    f = fato[fato["mes_completo"] & ~fato["pre_inauguracao"] & ~fato["unidade_id"].isin(excluir)]
    f = f.assign(periodo=pd.PeriodIndex(f["competencia"], freq="M"))
    inicio = f[(f["periodo"] == pre_p[0]) & (f["mes_vida"] >= 12)]["unidade_id"]
    f = f[f["unidade_id"].isin(inicio)]
    antes = f[f["periodo"].isin(pre_p)].groupby("unidade_id")[col].agg(["mean", "count"])
    depois = f[f["periodo"].isin(pos_p)].groupby("unidade_id")[col].agg(["mean", "count"])
    j = antes.join(depois, lsuffix="_a", rsuffix="_d", how="inner")
    j = j[(j["count_a"] == len(pre_p)) & (j["count_d"] == len(pos_p)) & (j["mean_a"] > 0)]
    return float((j["mean_d"] / j["mean_a"] - 1).median()) if len(j) else float("nan")


# --------------------------------------------------------------------------- metas


def _maiores_restos(pesos: pd.Series, total: int) -> pd.Series:
    """Divide `total` inteiros proporcionalmente a `pesos` (método dos maiores restos)."""
    pesos = pesos.clip(lower=0)
    if total <= 0 or pesos.sum() <= 0:
        return pd.Series(0, index=pesos.index)
    cota = pesos / pesos.sum() * total
    base = np.floor(cota).astype(int)
    falta = total - int(base.sum())
    ordem = (cota - base).sort_values(ascending=False).index[:falta]
    base.loc[ordem] += 1
    return base


def _datas_inauguracao(
    sel: pd.DataFrame, dim: pd.DataFrame | None
) -> tuple[list[pd.Timestamp], list[str]]:
    """Data de inauguração (painel, por nome+UF) de cada unidade de `sel`; devolve (datas, sem data).

    Sem o par nome+UF, vale o nome quando ele é único no painel: Novo Gama está em GO na planilha e
    em DF no painel (17/11).
    """
    if dim is None or dim.empty or "chave_nome" not in dim.columns:
        return [], list(sel["unidade"].astype(str))
    datas: list[pd.Timestamp] = []
    sem: list[str] = []
    for nome, uf in zip(sel["unidade"], sel.get("uf", [None] * len(sel)), strict=True):
        mesmo_nome = dim[dim["chave_nome"] == normalizar(nome)]
        hit = mesmo_nome[mesmo_nome["uf"] == str(uf).upper()]
        if hit.empty and len(mesmo_nome) == 1:
            hit = mesmo_nome
        data = pd.to_datetime(hit["inauguracao"].iloc[0]) if len(hit) else pd.NaT
        if pd.notna(data):
            datas.append(pd.Timestamp(data))
        else:
            sem.append(str(nome))
    return sorted(datas), sem


def progresso_meta(
    inauguradas: pd.DataFrame,
    pipeline: pd.DataFrame,
    master: Master,
    hoje: pd.Timestamp,
    aberturas_12m: int,
    dim: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Quanto falta para a meta do contrato.

    Contam as inauguradas que a planilha atribui à meta do master (coluna "Meta de abertura") e as
    que o contrato manda contar (`meta.conta_tambem`). O pipeline do master (aba "Pipeline", as
    assinadas) aparece à parte: ainda não abriu. Com `dim` (o painel), a meta do ano por trimestre
    (`trimestres`, de `meta_do_ano`; `n_ano` e `pct_ano` até hoje) e as sem data (`sem_data`).
    """
    meta = master.meta
    alvo = normalizar(master.nome_planilha)
    extra = {normalizar(u) for u in meta.conta_tambem}
    col_meta = inauguradas["meta"] if "meta" in inauguradas.columns else pd.Series(dtype=object)
    conta = (col_meta.map(normalizar) == alvo) | inauguradas["unidade"].map(normalizar).isin(extra)
    contam = list(inauguradas.loc[conta, "unidade"].astype(str))
    datas, sem_data = _datas_inauguracao(inauguradas.loc[conta], dim)
    n_ano = sum(1 for x in datas if x.year == hoje.year and x <= hoje)
    n_pipe = int((pipeline["master"].map(normalizar) == alvo).sum()) if len(pipeline) else 0
    prazo = pd.Timestamp(meta.prazo) if meta.prazo else None
    meses = None
    if prazo is not None:
        meses = max(0, (prazo.year - hoje.year) * 12 + prazo.month - hoje.month)
    q = meta.quantidade
    faltam = max(0, q - len(contam)) if q is not None else None
    return {
        "quantidade": q,
        "prazo": prazo,
        "fonte": meta.fonte,
        "contam": contam,
        "n_contam": len(contam),
        "n_pipeline": n_pipe,
        "pct": len(contam) / q if q else float("nan"),
        "pct_com_pipeline": (len(contam) + n_pipe) / q if q else float("nan"),
        "faltam": faltam,
        "meses_ate_prazo": meses,
        "ritmo_necessario_mes": (faltam / meses) if (faltam and meses) else 0.0,
        "ritmo_atual_mes": aberturas_12m / 12,
        "por_ano": meta.por_ano,
        "ano": hoje.year,
        "n_ano": n_ano,
        "pct_ano": n_ano / meta.por_ano if meta.por_ano else float("nan"),
        "trimestres": meta_do_ano(datas, meta.por_ano, hoje),
        "sem_data": sem_data,
    }


def proposta_metas(
    regioes: pd.DataFrame,
    unidades: pd.DataFrame,
    pipeline: pd.DataFrame,
    master: Master,
    data_ref: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Proposta de metas para 12 meses, por região.

    Regra (simples de explicar ao master): abrir o que já está assinado e iniciar novas
    buscas no mesmo ritmo de aberturas dos últimos 12 meses (mínimo 1), distribuídas pelo
    espaço livre que sobra depois do pipeline.
    """
    alvo = normalizar(master.nome_planilha)
    pipe = pipeline[pipeline["master"].map(normalizar) == alvo].copy()
    pipe["regiao_id"] = [
        (r.id if (r := master.regiao_do_pipeline(f"{un} {cid or ''}", uf)) else None)
        for un, cid, uf in zip(
            pipe["unidade"], pipe.get("cidade", [None] * len(pipe)), pipe["uf"], strict=True
        )
    ]
    inicio = data_ref - pd.DateOffset(months=12)
    aberturas_12m = (
        int(((unidades["inauguracao"] > inicio) & (unidades["inauguracao"] <= data_ref)).sum())
        if len(unidades)
        else 0
    )
    novas = max(1, aberturas_12m)

    t = regioes[
        ["regiao_id", "regiao_nome", "tipo", "espaco_livre_alunos", "unidades_teoricas"]
    ].copy()
    t["abertas"] = [
        int((unidades.get("regiao_id", pd.Series(dtype=object)) == rid).sum())
        for rid in t["regiao_id"]
    ]
    t["pipeline"] = [int((pipe["regiao_id"] == rid).sum()) for rid in t["regiao_id"]]
    t["espaco_apos_pipeline"] = (
        t["espaco_livre_alunos"] - t["pipeline"] * CAPACIDADE_UNIDADE_ALUNOS
    ).clip(lower=0)
    # Se o pipeline já cobre todo o espaço livre, distribui pelo espaço livre bruto; o resumo
    # sempre usa a soma distribuída, para o texto e a tabela nunca divergirem.
    pesos = t.set_index("regiao_id")["espaco_apos_pipeline"]
    if pesos.sum() <= 0:
        pesos = t.set_index("regiao_id")["espaco_livre_alunos"]
    t["novas_buscas"] = _maiores_restos(pesos, novas).reindex(t["regiao_id"]).to_numpy()
    resumo: dict[str, object] = {
        "aberturas_12m": aberturas_12m,
        "n_pipeline": int(len(pipe)),
        "n_pipeline_fora": int(pipe["regiao_id"].isna().sum()),
        "novas_buscas": int(t["novas_buscas"].sum()),
        "regiao_prioritaria": t.sort_values("espaco_apos_pipeline", ascending=False)[
            "regiao_nome"
        ].iloc[0]
        if len(t)
        else None,
        "pipeline": pipe[["unidade", "uf", "fase", "regiao_id"]].to_dict("records"),
    }
    return t, resumo
