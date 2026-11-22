"""Slides a mais do modelo novo (BLK-MASTERS-02, rascunho): o comportamento de cada região.

Um slide por região com unidades suficientes, só dados e sem veredito: o que já se mediu andando
com o faturamento no DF (renda a pé, população perto, metragem e alunos do 3º mês), medido de novo
na região. As unidades que faturam acima da média da rede contra as abaixo, e a força da relação.

Região sem unidades suficientes fica fora (citada no rodapé); sem nenhuma, a seção não sai.
Unidades da região = todas as Ultra cuja coordenada cai nela, de qualquer operador (é o
funcionamento da região, não só do master).

Fontes: painel do BLK-UNI (`dim_unidade`, `fato_unidade_mes`); método e traços da pesquisa
"Padrões das unidades" (rodada 43, 28/10/2026). READ-ONLY sobre o M1.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from motor_expansao.masters import analise as A
from motor_expansao.masters.territorios import Master

#: Regra do estudo "Padrões das unidades": nenhuma leitura de grupo com menos de 5 unidades.
N_MIN_GRUPO = 5
#: Relação só com 15+ unidades maduras na região; abaixo disso a faixa não diz nada.
N_MIN_RELACAO = 15
MESES_JANELA = 12

#: O que a pesquisa "Padrões das unidades" (rodada 43) viu andar com o faturamento no DF e em SP:
#: (coluna do painel, rótulo, formato). A renda é a da área a pé (a da pesquisa era a de 5 min
#: de carro). O estúdio (`cad_mod_studios`, sim/não do cadastro) é o traço mais forte de SP; o
#: estudo achou erro de cadastro do estúdio em 8 unidades. Formato "sim_nao": os dois lados viram
#: a parte das unidades com o traço, não a mediana.
#: Ordem dos cartões no slide: população primeiro (Juan, 17/11).
TRACOS_COMPORTAMENTO: tuple[tuple[str, str, str], ...] = (
    ("iso_pop__carro_5", "População em 5 min de carro", "mil"),
    ("iso_renda_pc__pe_15", "Renda por pessoa em 15 min a pé", "reais"),
    ("tam_metragem_m2", "Metragem", "m2"),
    ("cad_mod_studios", "Tem estúdio", "sim_nao"),
    ("rampa_ativos_m3", "Alunos no 3º mês de vida", "int"),
)


def _numerico(v: pd.Series) -> pd.Series:
    """Coluna do painel como número; sim/não do cadastro (True/False/None) vira 1/0/NaN."""
    if v.dtype == object or v.dtype == bool:
        v = v.map({True: 1.0, False: 0.0, "True": 1.0, "False": 0.0})
    return pd.to_numeric(v, errors="coerce")


def _lado(v: pd.Series, formato: str) -> float:
    """Valor típico de um lado: mediana, ou a parte com o traço quando é sim/não."""
    v = v.dropna()
    if not len(v):
        return float("nan")
    return float(v.mean()) if formato == "sim_nao" else float(v.median())


def unidades_com_regiao(dim: pd.DataFrame, mercado: pd.DataFrame, master: Master) -> pd.DataFrame:
    """O painel com a região do master onde cada unidade está (None fora do território)."""
    u = dim.assign(municipio_ref=A.municipio_da_coordenada(dim, mercado))
    u["regiao_id"] = A.atribuir_regiao(u, master, col_uf="uf", col_mun="municipio_ref")
    return u


def janela_madura(
    fato: pd.DataFrame, data_ref: pd.Timestamp, meses: int = MESES_JANELA
) -> pd.DataFrame:
    """Uma linha por unidade com os `meses` últimos meses fechados completos (a unidade madura)."""
    f = fato[fato["mes_completo"] & ~fato["pre_inauguracao"]]
    fim = pd.Period(data_ref, freq="M")
    periodos = {str(p) for p in pd.period_range(fim - meses + 1, fim, freq="M")}
    f = f[f["competencia"].isin(periodos)]
    g = f.groupby("unidade_id").agg(
        n_meses=("competencia", "nunique"),
        fat_mes=("faturamento", "mean"),
        ativos=("ativos", "mean"),
        agregadores=("agregadores", "mean"),
    )
    g = g[g["n_meses"] == meses].copy()
    g["pct_agregador_alunos"] = (g["agregadores"] / g["ativos"].where(g["ativos"] > 0)).clip(0, 1)
    return g.reset_index()


def _razao(num: pd.Series, den: pd.Series) -> pd.Series:
    """`num / den` só onde o denominador é positivo (NaN no resto): sem `inf` entrando na mediana."""
    return num / den.where(den > 0)


def _terco(v: pd.Series) -> pd.Series:
    """O terço (0, 1, 2) de cada valor. Pela ORDEM (`rank` com desempate pela posição), e não pelo
    valor: com valores repetidos entre unidades, `qcut` pelo valor levanta "Bin edges must be
    unique" e derruba o slide (achado da revisão automática do #568). Sem repetição, os grupos são
    os mesmos do `qcut` pelo valor."""
    return pd.qcut(v.rank(method="first"), 3, labels=False)


def _mediana(v: pd.Series) -> float:
    v = v.dropna()
    return float(v.median()) if len(v) else float("nan")


def _acerto(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Comparando duas unidades com valores diferentes do traço (e do faturamento), a parte das
    vezes em que a de traço maior fatura mais. 50% = acaso; 100% = sempre; 0% = sempre ao contrário.
    Aceita lotes (última dimensão = unidades)."""
    dx = np.sign(x[..., :, None] - x[..., None, :])
    dy = np.sign(y[..., :, None] - y[..., None, :])
    prod = dx * dy
    conc = (prod > 0).sum(axis=(-1, -2))
    disc = (prod < 0).sum(axis=(-1, -2))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.asarray(conc / (conc + disc), dtype=float)


def _acerto_com_faixa(
    x: np.ndarray, y: np.ndarray, rng: np.random.Generator, n_boot: int
) -> tuple[float, float, float]:
    """O acerto e a faixa de 90% por reamostragem das unidades (a faixa decide a leitura)."""
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
    bs = _acerto(x[idx], y[idx])
    bs = bs[~np.isnan(bs)]
    if not len(bs):
        return float(_acerto(x, y)), float("nan"), float("nan")
    lo, hi = np.quantile(bs, [0.05, 0.95])
    return float(_acerto(x, y)), float(lo), float(hi)


def _do_lado_do_selo(v: pd.Series, acima: pd.Series, formato: str, leitura: str) -> int | None:
    """Quantas das que faturam acima estão do lado do selo (o número real que o leitor lê).

    Número: acima (anda junto) ou abaixo (ao contrário) da típica (mediana) da região inteira;
    sim/não: com o traço (junto) ou sem (ao contrário). None quando não há selo de relação.
    """
    if leitura not in ("anda junto", "anda ao contrário"):
        return None
    junto = leitura == "anda junto"
    va = v[acima].dropna()
    if formato == "sim_nao":
        return int((va == (1.0 if junto else 0.0)).sum())
    ref = v.dropna().median()
    return int((va > ref).sum() if junto else (va < ref).sum())


def _leitura(lo: float, hi: float) -> str:
    """Faixa toda acima de 50%: anda junto; toda abaixo: ao contrário; senão, pode ser acaso."""
    return "anda junto" if lo > 0.5 else "anda ao contrário" if hi < 0.5 else "sem relação clara"


#: Pesquisa "Padrões das unidades", rodada 43 (28/10/2026): valor típico de cada traço nas unidades
#: acima x abaixo da média da rede, por grupo, na janela set/25 a ago/26 (`por_regiao_descricao.csv`).
#: Referência do slide "Veracidade dos dados": pelo mesmo método, o de hoje ainda bate com o da pesquisa?
PESQUISA_RODADA_43: dict[str, dict[str, tuple[float, float]]] = {
    "DF": {
        "iso_renda_pc__carro_5": (5780.0, 1831.0),
        "iso_pop__carro_5": (29037.0, 124270.0),
        "tam_metragem_m2": (1700.0, 1500.0),
        "cad_mod_studios": (0.889, 0.571),
    },
    "SP": {
        "iso_renda_pc__carro_5": (3248.0, 1903.0),
        "iso_pop__carro_5": (93918.0, 107953.0),
        "tam_metragem_m2": (1500.0, 1200.0),
        "cad_mod_studios": (0.667, 0.125),
    },
}
#: Os traços conferidos, com a medida da pesquisa (renda em 5 min de carro, não a pé).
CONFERENCIA: tuple[tuple[str, str, str], ...] = (
    ("iso_renda_pc__carro_5", "Renda em 5 min de carro", "reais"),
    ("iso_pop__carro_5", "População em 5 min de carro", "mil"),
    ("tam_metragem_m2", "Metragem", "m2"),
    ("cad_mod_studios", "Tem estúdio", "sim_nao"),
)
#: "Bate com a pesquisa": a razão acima / abaixo de hoje fica a até 25% da razão da pesquisa.
TOLERANCIA_CONFERE = 1.25


def _conferencia(sub: pd.DataFrame, rede: pd.DataFrame, acima: pd.Series) -> dict[str, Any]:
    """Valor típico de hoje (acima x abaixo) dos traços da pesquisa ao lado do da pesquisa.

    Só compara quando a região é exatamente um grupo da pesquisa: todas as maduras de uma UF que a
    pesquisa separou (DF, SP). Recorte menor ou misto = sem referência (o grupo seria outro).
    """
    ufs = set(sub["uf"].dropna()) if "uf" in sub.columns else set()
    grupo = None
    if len(ufs) == 1:
        uf = next(iter(ufs))
        mesma_uf = set(rede.loc[rede["uf"] == uf, "unidade_id"])
        if uf in PESQUISA_RODADA_43 and set(sub["unidade_id"]) == mesma_uf:
            grupo = uf
    itens = []
    for col, rotulo, formato in CONFERENCIA:
        v = _numerico(sub[col]) if col in sub.columns else pd.Series(np.nan, index=sub.index)
        hoje = (_lado(v[acima], formato), _lado(v[~acima], formato))
        pesquisa = PESQUISA_RODADA_43[grupo].get(col) if grupo else None
        bate = None
        if pesquisa and all(pd.notna(x) and x > 0 for x in (*hoje, *pesquisa)):
            r_hoje, r_pesq = hoje[0] / hoje[1], pesquisa[0] / pesquisa[1]
            bate = bool(max(r_hoje / r_pesq, r_pesq / r_hoje) <= TOLERANCIA_CONFERE)
        itens.append(
            {
                "col": col,
                "rotulo": rotulo,
                "formato": formato,
                "hoje": hoje,
                "pesquisa": pesquisa,
                "bate": bate,
            }
        )
    return {"grupo": grupo, "itens": itens}


def comportamento(
    u: pd.DataFrame, maduras: pd.DataFrame, master: Master, n_boot: int = 2000, seed: int = 42
) -> dict[str, Any]:
    """Por região: unidades acima x abaixo da média da rede, traço por traço.

    Mesmo método da rodada 43 da pesquisa: média do faturamento mensal das maduras da rede como
    corte; valor típico de cada traço nos dois lados. A relação vira o "acerto": comparando duas
    unidades da região, quantas vezes a de traço maior fatura mais (50% = acaso), com faixa de 90%
    por reamostragem (2.000, semente 42) que decide a leitura. Relação nesta amostra, não causa.
    """
    m = maduras.merge(u, on="unidade_id", suffixes=("", "_dim"))
    media = float(m["fat_mes"].mean()) if len(m) else float("nan")
    rng = np.random.default_rng(seed)
    grupos = []
    for r in master.regioes:
        sub = m[m["regiao_id"] == r.id]
        acima = sub["fat_mes"] > media
        tracos: list[dict[str, Any]] = []
        for col, rotulo, formato in TRACOS_COMPORTAMENTO:
            # Coluna fora do painel (versão antiga) = traço sem dado, não erro do relatório inteiro.
            v = _numerico(sub[col]) if col in sub.columns else pd.Series(np.nan, index=sub.index)
            par = pd.DataFrame({"x": v, "fat": sub["fat_mes"]}).dropna()
            if len(par) >= N_MIN_RELACAO:
                acerto, lo, hi = _acerto_com_faixa(
                    par["x"].to_numpy(float), par["fat"].to_numpy(float), rng, n_boot
                )
                leitura = _leitura(lo, hi)
            else:
                acerto = lo = hi = float("nan")
                leitura = "poucas unidades"
            tracos.append(
                {
                    "col": col,
                    "rotulo": rotulo,
                    "formato": formato,
                    "n": int(len(par)),
                    "acima": _lado(v[acima], formato),
                    "n_acima": int(v[acima].notna().sum()),
                    "abaixo": _lado(v[~acima], formato),
                    "n_abaixo": int(v[~acima].notna().sum()),
                    "acerto": acerto,
                    "lo": lo,
                    "hi": hi,
                    "leitura": leitura,
                    "do_lado": _do_lado_do_selo(v, acima, formato, leitura),
                }
            )
        grupos.append(
            {
                "id": r.id,
                "rotulo": r.nome,
                "n_total": int((u["regiao_id"] == r.id).sum()),
                "n_maduras": int(len(sub)),
                "n_acima": int(acima.sum()),
                "n_abaixo": int((~acima).sum()),
                "pct_agregador_alunos": _mediana(sub["pct_agregador_alunos"]),
                "tracos": tracos,
                # Veracidade: o valor de hoje ao lado do da pesquisa.
                "conferencia": _conferencia(sub, m, acima),
            }
        )
    return {
        "media_rede": media,
        "n_rede": int(len(m)),
        "pct_agregador_alunos_outras": _mediana(
            m.loc[m["regiao_id"].isna(), "pct_agregador_alunos"]
        ),
        "grupos": grupos,
    }


def so_com_dados(fn: dict[str, Any]) -> dict[str, Any]:
    """O mesmo `fn` só com as regiões que têm unidades suficientes.

    `_fora` = regiões que saíram (para a nota); `_slides` = se a seção sai (alguma região com dado).
    """
    todos = fn["comportamento"]["grupos"]
    com = [g for g in todos if g["n_maduras"] >= N_MIN_RELACAO]
    return {
        **fn,
        "comportamento": {**fn["comportamento"], "grupos": com},
        "_fora": {"comportamento": [g["rotulo"] for g in todos if g not in com]},
        "_slides": {"comportamento": bool(com)},
    }


def tem_dados(fn: dict[str, Any]) -> bool:
    """Alguma região do master tem dado para o slide a mais."""
    return bool(fn) and any(so_com_dados(fn)["_slides"].values())


#: Rampa de maturação: alunos ativos no mês de vida k sobre os do 12º mês, k = 1 a 12.
MESES_RAMPA = 12
#: Marco do slide: em que mês a mediana passa de 90% do 12º mês.
MARCO_RAMPA = 0.9


def _ja_estabilizadas(frac: pd.DataFrame, ate: int | None) -> int:
    """Quantas unidades (linhas de `frac`, mês de vida sobre o 12º) passaram de 90% até o mês `ate`.

    O número real por trás do "N meses" do slide (17/11: "é a média ou é um fato?").
    """
    if not ate or frac.empty:
        return 0
    cols = [c for c in range(1, ate + 1) if c in frac.columns]
    return int((frac[cols] >= MARCO_RAMPA).any(axis=1).sum())


def rampa(u: pd.DataFrame, fato: pd.DataFrame, master: Master) -> dict[str, Any]:
    """Curva de maturação por região e nas outras unidades: mediana, mês a mês, de ativos(k) / ativos(12).

    Só unidades com a rampa observável no painel do BLK-UNI (abertas a partir de abr/2022, sem data
    de inauguração provisória) e com o 1º e o 12º mês fechados: a mesma régua do `rampa_ativos_mK`.
    """
    obs = (
        u["rampa_observavel"].eq(True)
        if "rampa_observavel" in u.columns
        else pd.Series(True, index=u.index)
    )
    ids = set(u.loc[obs, "unidade_id"])
    f = fato[
        fato["mes_completo"]
        & fato["mes_vida"].between(1, MESES_RAMPA)
        & fato["unidade_id"].isin(ids)
    ].assign(mes=lambda x: x["mes_vida"].astype(int))
    piv = f.pivot_table(index="unidade_id", columns="mes", values="ativos", aggfunc="first")
    piv = piv.reindex(columns=range(1, MESES_RAMPA + 1))
    piv = piv[piv[1].notna() & (piv[MESES_RAMPA] > 0)]
    frac = piv.div(piv[MESES_RAMPA], axis=0)
    regiao = u.drop_duplicates("unidade_id").set_index("unidade_id")["regiao_id"]

    def grupo(ids_grupo: set[str]) -> dict[str, Any]:
        sub = frac[frac.index.isin(ids_grupo)]
        curva = [float(v) for v in sub.median().reindex(range(1, MESES_RAMPA + 1))]
        marco = next(
            (k for k, v in enumerate(curva, start=1) if pd.notna(v) and v >= MARCO_RAMPA), None
        )
        return {
            "n": int(len(sub)),
            "curva": curva,
            "mes_marco": marco,
            "ja_no_marco": _ja_estabilizadas(sub, marco),
            "alunos_m12": _mediana(piv.loc[sub.index, MESES_RAMPA]),
        }

    return {
        "grupos": {r.id: grupo(set(regiao[regiao == r.id].index)) for r in master.regioes},
        "outras": grupo(set(regiao[regiao.isna()].index)),
    }


#: Padrão de faturamento: faturamento do mês de vida k sobre o do 12º mês, k = 1 a 18 (o 13º ao 18º
#: mostram se o nível se mantém depois do 1º ano).
MESES_FATURAMENTO = 18


def _ids_rampa(u: pd.DataFrame) -> set[str]:
    """Unidades com a rampa observável no painel do BLK-UNI (abertas a partir de abr/2022)."""
    if "rampa_observavel" not in u.columns:
        return set(u["unidade_id"])
    return set(u.loc[u["rampa_observavel"].eq(True), "unidade_id"])


def _pivo_mes_de_vida(
    fato: pd.DataFrame, ids: set[str], coluna: str, ate: int, mes_cheio: bool
) -> pd.DataFrame:
    """Uma linha por unidade, uma coluna por mês de vida (1 a `ate`), só meses fechados.

    `mes_cheio`: só meses de operação inteira (o faturamento do mês da abertura sai parcial).
    """
    m = fato["mes_completo"] & fato["mes_vida"].between(1, ate) & fato["unidade_id"].isin(ids)
    if mes_cheio and "operacao_mes_cheio" in fato.columns:
        m &= fato["operacao_mes_cheio"].eq(True)
    f = fato[m].assign(mes=lambda x: x["mes_vida"].astype(int))
    piv = f.pivot_table(index="unidade_id", columns="mes", values=coluna, aggfunc="first")
    return piv.reindex(columns=range(1, ate + 1))


def padrao_faturamento(u: pd.DataFrame, fato: pd.DataFrame, master: Master) -> dict[str, Any]:
    """Faturamento por mês de vida sobre o do 12º mês, por região e nas outras unidades.

    Por grupo: a curva (mediana mês a mês; mês com menos de `N_MIN_GRUPO` unidades fica vazio), o
    mês em que passa de 90%, quantas já tinham 90% no 3º mês, e a abertura do 3º mês em alunos e
    faturamento por aluno (as duas partes do faturamento). Mesma régua da rampa de alunos.
    """
    ids = _ids_rampa(u)
    fat = _pivo_mes_de_vida(fato, ids, "faturamento", MESES_FATURAMENTO, mes_cheio=True)
    fat = fat[fat[MESES_RAMPA] > 0]
    atv = _pivo_mes_de_vida(fato, ids, "ativos", MESES_RAMPA, mes_cheio=False).reindex(fat.index)
    frac = fat.div(fat[MESES_RAMPA], axis=0)
    ticket = fat[[3, MESES_RAMPA]] / atv[[3, MESES_RAMPA]].where(atv[[3, MESES_RAMPA]] > 0)
    regiao = u.drop_duplicates("unidade_id").set_index("unidade_id")["regiao_id"]

    def grupo(ids_grupo: set[str]) -> dict[str, Any]:
        idx = frac.index[frac.index.isin(ids_grupo)]
        sub = frac.loc[idx]
        n_mes = sub.notna().sum()
        mediana = sub.median().where(n_mes >= N_MIN_GRUPO)
        curva = [float(v) for v in mediana]
        marco = next(
            (
                k
                for k in range(1, MESES_RAMPA + 1)
                if pd.notna(curva[k - 1]) and curva[k - 1] >= MARCO_RAMPA
            ),
            None,
        )
        return {
            "n": int(len(idx)),
            "curva": curva,
            "n_mes": [int(v) for v in n_mes],
            "mes_marco": marco,
            "ja_no_marco": _ja_estabilizadas(sub, marco),
            "fat_m3": _mediana(fat.loc[idx, 3]),
            "fat_m12": _mediana(fat.loc[idx, MESES_RAMPA]),
            "cheias_m3": int((sub[3] >= MARCO_RAMPA).sum()),
            "n_m3": int(sub[3].notna().sum()),
            "alunos_m3": _mediana(_razao(atv.loc[idx, 3], atv.loc[idx, MESES_RAMPA])),
            "ticket_m3": _mediana(ticket.loc[idx, 3]),
            "ticket_m12": _mediana(ticket.loc[idx, MESES_RAMPA]),
            # Faturamento por aluno do 3º mês sobre o do 12º, unidade a unidade (mesma régua dos alunos).
            "ticket_rel_m3": _mediana(ticket.loc[idx, 3] / ticket.loc[idx, MESES_RAMPA]),
        }

    return {
        "grupos": {r.id: grupo(set(regiao[regiao == r.id].index)) for r in master.regioes},
        "outras": grupo(set(regiao[regiao.isna()].index)),
    }


#: Retenção da coorte de abertura (estudo de inauguração, Etapas 7, 8 e 10; base de alunos do
#: Lifetime, retrato de 17/04/2026): fração dos alunos do mês 0 ativa após 12 meses contra a das
#: coortes dos meses 3 a 11 (mediana por unidade), a diferença mediana e quantas unidades a favor da
#: abertura. O painel não tem a coluna preenchida (`rampa_ret12_coorte_m0_vs_m3a11_pp` vazia): texto fixo.
RETENCAO_ABERTURA: dict[str, dict[str, Any]] = {
    "DF": {"abertura": 0.648, "depois": 0.595, "pontos": 7.8, "a_favor": 14, "n": 17},
    "SP": {"abertura": 0.538, "depois": 0.505, "pontos": 1.9, "a_favor": 7, "n": 13},
    "rede": {
        "abertura": 0.576,
        "depois": 0.552,
        "pontos": 4.4,
        "a_favor": 31,
        "n": 46,
        "sem_df_go": 2.4,
    },
}


def ocupacao_vizinhas(
    u: pd.DataFrame, fato: pd.DataFrame, maduras: pd.DataFrame, master: Master
) -> dict[str, Any]:
    """Alunos por m², Ultra vizinha e entradas do 1º ano com e sem vizinha, por região e nas outras.

    Alunos por m² = ativos médios dos 12 meses da janela sobre a metragem (só maduras com metragem).
    Vizinha a 5 min = outra Ultra na isócrona de 5 min de carro (`iso_n_ultra__carro_5` conta a
    própria); a 10 min = outras Ultras abertas na de 10 min no último mês fechado do painel.
    Entradas do 1º ano = novos alunos por mês do 1º ao 12º mês (unidades com a rampa observável).
    """
    m = maduras.merge(u, on="unidade_id", suffixes=("", "_dim"))
    m = m.assign(dens=m["ativos"] / m["tam_metragem_m2"].where(m["tam_metragem_m2"] > 0))
    base = u.drop_duplicates("unidade_id").set_index("unidade_id")
    viz5 = (
        base["iso_n_ultra__carro_5"] - 1
        if "iso_n_ultra__carro_5" in base.columns
        else pd.Series(np.nan, index=base.index)
    )
    col10 = "n_ultra_outras_abertas__carro_10"
    if col10 in fato.columns:
        ult = fato[fato["mes_completo"]].sort_values("competencia").groupby("unidade_id").last()
        viz10 = ult[col10].reindex(base.index)
    else:
        viz10 = pd.Series(np.nan, index=base.index)
    ids_rampa = _ids_rampa(u)
    if "novos_alunos" in fato.columns:
        f1 = fato[
            fato["mes_completo"]
            & fato["mes_vida"].between(1, MESES_RAMPA)
            & fato["unidade_id"].isin(ids_rampa)
        ]
        entradas = f1.groupby("unidade_id")["novos_alunos"].mean()
    else:
        entradas = pd.Series(dtype=float)

    def grupo(mask: pd.Series) -> dict[str, Any]:
        ids = set(base.index[mask.reindex(base.index, fill_value=False)])
        mm = m[m["unidade_id"].isin(ids)]
        v5, v10 = viz5[viz5.index.isin(ids)], viz10[viz10.index.isin(ids)]
        e = entradas[entradas.index.isin(ids)]
        com = e[viz5.reindex(e.index) >= 1]
        sem = e[viz5.reindex(e.index) < 1]
        return {
            "n": int(len(ids)),
            "densidade": _mediana(mm["dens"]),
            "n_densidade": int(mm["dens"].notna().sum()),
            "ativos": _mediana(mm.loc[mm["dens"].notna(), "ativos"]),
            "metragem": _mediana(mm.loc[mm["dens"].notna(), "tam_metragem_m2"]),
            "viz5": int((v5 >= 1).sum()),
            "n_viz5": int(v5.notna().sum()),
            "viz10": int((v10 >= 1).sum()),
            "n_viz10": int(v10.notna().sum()),
            "media_viz10": float(v10.mean()) if v10.notna().any() else float("nan"),
            "entradas_com": _mediana(com),
            "n_entradas_com": int(len(com)),
            "entradas_sem": _mediana(sem),
            "n_entradas_sem": int(len(sem)),
        }

    regiao = base["regiao_id"]
    return {
        "grupos": {r.id: grupo(regiao == r.id) for r in master.regioes},
        "outras": grupo(regiao.isna()),
    }


#: Faturamento e tendência: últimos 3 meses fechados contra os mesmos 3 meses um ano antes, só com
#: as unidades que estavam nos dois períodos (e já com 12 meses no primeiro): sem efeito de unidade
#: nova entrando na conta.
MESES_COMPARA = 3
#: Unidade que aceita app: 5 ou mais alunos de app (Gympass e TotalPass) na média dos meses.
MIN_ALUNOS_APP = 5
#: Calendário de alunos novos: 24 meses até a data de referência, unidades com 13+ meses de vida.
MESES_CALENDARIO = 24


def faturamento_tendencia(
    u: pd.DataFrame,
    fato: pd.DataFrame,
    maduras: pd.DataFrame,
    master: Master,
    data_ref: pd.Timestamp,
) -> dict[str, Any]:
    """Por região e nas outras unidades: nível, tendência de 12 meses, cancelamento, faturamento por
    faixa de renda e o calendário de alunos novos."""
    m = maduras.merge(u, on="unidade_id", suffixes=("", "_dim"))
    fim = pd.Period(data_ref, freq="M")
    depois = {str(fim - k) for k in range(MESES_COMPARA)}
    antes = {str(fim - 12 - k) for k in range(MESES_COMPARA)}
    f = fato[fato["mes_completo"]]
    cols = [c for c in ("faturamento", "ativos", "pagantes", "agregadores") if c in f.columns]
    a = f[f["competencia"].isin(antes) & (f["mes_vida"] >= 12)].groupby("unidade_id")[cols].mean()
    b = f[f["competencia"].isin(depois)].groupby("unidade_id")[cols].mean()
    par = a.join(b, lsuffix="_a", rsuffix="_b", how="inner")
    churn = _pivo_mes_de_vida(fato, _ids_rampa(u), "churn_pct", MESES_RAMPA, mes_cheio=False)
    if "novos_alunos" in f.columns:
        cal = f[
            (f["mes_vida"] >= 13)
            & (f["competencia"] > str(fim - MESES_CALENDARIO))
            & (f["competencia"] <= str(fim))
        ].copy()
        cal["mes"] = cal["competencia"].str[5:7].astype(int)
        cal["indice"] = cal["novos_alunos"] / cal.groupby("unidade_id")["novos_alunos"].transform(
            "mean"
        ).where(lambda x: x > 0)
    else:
        cal = pd.DataFrame(columns=["unidade_id", "mes", "indice"])
    base = u.drop_duplicates("unidade_id").set_index("unidade_id")

    def grupo(ids: set[str]) -> dict[str, Any]:
        mm = m[m["unidade_id"].isin(ids)]
        pp = par[par.index.isin(ids)].dropna(subset=["faturamento_a", "faturamento_b"])
        var = {c: _mediana(pp[f"{c}_b"] / pp[f"{c}_a"].where(pp[f"{c}_a"] > 0) - 1) for c in cols}
        renda = mm["iso_renda_pc__pe_15"] if "iso_renda_pc__pe_15" in mm.columns else None
        tercos = []
        if renda is not None and renda.notna().sum() >= 3 * N_MIN_GRUPO:
            ok = mm[renda.notna()].assign(terco=lambda x: _terco(x["iso_renda_pc__pe_15"]))
            for k in range(3):
                t = ok[ok["terco"] == k]
                tercos.append(
                    {
                        "de": float(t["iso_renda_pc__pe_15"].min()),
                        "ate": float(t["iso_renda_pc__pe_15"].max()),
                        "fat": _mediana(t["fat_mes"]),
                        "n": int(len(t)),
                    }
                )
        c = cal[cal["unidade_id"].isin(ids)]
        n_mes = c.groupby("mes")["unidade_id"].nunique().reindex(range(1, 13), fill_value=0)
        ind = c.groupby("mes")["indice"].median().reindex(range(1, 13)).where(n_mes >= N_MIN_GRUPO)
        ch = churn[churn.index.isin(ids)]
        return {
            "n": int(len(mm)),
            "fat_med": _mediana(mm["fat_mes"]),
            "fat_aluno": _mediana(mm["fat_mes"] / mm["ativos"].where(mm["ativos"] > 0)),
            "n_var": int(len(pp)),
            "cresceram": int((pp["faturamento_b"] > pp["faturamento_a"]).sum()),
            "var": var,
            # Das unidades comparadas, quantas já aceitavam app um ano antes (o crescimento do app não
            # é de unidade que passou a aceitar; 17/11, Juan: "cresceram porque liberaram o agregador?").
            "app_ja_tinha": int((pp["agregadores_a"] >= MIN_ALUNOS_APP).sum())
            if "agregadores_a" in pp.columns
            else None,
            "churn_m3": _mediana(ch[3]),
            "churn_m12": _mediana(ch[MESES_RAMPA]),
            "n_churn": int(ch[MESES_RAMPA].notna().sum()),
            "tercos_renda": tercos,
            "calendario": [float(v - 1) if pd.notna(v) else float("nan") for v in ind],
            "n_calendario": int(c["unidade_id"].nunique()),
        }

    regiao = base["regiao_id"]
    return {
        "meses": (sorted(antes), sorted(depois)),
        "grupos": {r.id: grupo(set(regiao[regiao == r.id].index)) for r in master.regioes},
        "outras": grupo(set(regiao[regiao.isna()].index)),
    }


def validade(u: pd.DataFrame, fato: pd.DataFrame, master: Master) -> dict[str, Any]:
    """Até quando a análise de padrões vale, por região (18/11, Juan: "até quando essa análise vale,
    quando em 2027 ela pode ser refeita com mais amostras").

    `n` = unidades abertas da região com dado de operação; `mes_todas` = o mês dos dados em que a
    última delas fecha 12 meses (1º mês de operação + 11), a régua das maduras. Assinadas que ainda
    não abriram não entram.
    """
    primeiro = fato[~fato["pre_inauguracao"]].groupby("unidade_id")["competencia"].min()
    regiao = u.drop_duplicates("unidade_id").set_index("unidade_id")["regiao_id"]
    out: dict[str, Any] = {}
    for r in master.regioes:
        p = primeiro.reindex(regiao.index[regiao == r.id]).dropna()
        meses = [pd.Period(c, freq="M") + (MESES_JANELA - 1) for c in p]
        out[r.id] = {"n": int(len(p)), "mes_todas": str(max(meses)) if meses else None}
    return out


def montar(
    master: Master,
    dim: pd.DataFrame,
    fato: pd.DataFrame,
    mercado: pd.DataFrame,
    data_ref: pd.Timestamp,
) -> dict[str, Any]:
    u = unidades_com_regiao(dim, mercado, master)
    maduras = janela_madura(fato, data_ref)
    fim = pd.Period(data_ref, freq="M")
    return {
        "janela": f"{fim - MESES_JANELA + 1}..{fim}",
        "n_rede_maduras": int(len(maduras)),
        "comportamento": comportamento(u, maduras, master),
        "rampa": rampa(u, fato, master),
        "faturamento": padrao_faturamento(u, fato, master),
        "ocupacao": ocupacao_vizinhas(u, fato, maduras, master),
        "tendencia": faturamento_tendencia(u, fato, maduras, master, data_ref),
        "validade": validade(u, fato, master),
    }
