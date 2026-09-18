"""Inteligência da rede — o que está POR TRÁS dos números da Growth.

A Visão Executiva 2.0 (DEC-023) lê a rede Ultra só pela operação: faturamento, alunos,
churn, NPS. O motor, porém, já sabe muito sobre o CHÃO de cada unidade — a praça, a
concorrência no raio, a retenção prevista, a trajetória de maturação. Este módulo junta as
duas leituras, sem recalcular nada do M1: só LÊ artefatos já materializados.

Oito leituras, uma função pura por leitura (sem IO, sem FastAPI — quem carrega os
parquets é `app.py`):

1. `quadrante_praca_execucao` — praça × desempenho. Separa "a praça limita" de "a
   execução deixa dinheiro na mesa". **Não é previsão**: a DEC-043 fechou a previsão de
   desempenho pela geografia (R² fora da amostra negativo). É leitura diagnóstica, com
   cortes RELATIVOS ao conjunto exibido, e a tela diz isso.
2. `fatos_territoriais` — a praça e a concorrência de cada unidade, pela COORDENADA.
3. `retencao_por_unidade` — risco de cancelamento e LTV (camada M2, DEC-014).
4. `concorrentes_novos` — academia que apareceu no feed há poucas semanas, perto de uma
   Ultra. Depende da série de snapshots (DEC-039); sem série, diz que não há série.
5. `curva_de_rampa` / `posicao_na_rampa` — a unidade nova contra a trajetória mediana da
   rede no MESMO mês de vida.
6. `sinais_antecedentes` — o que costuma vir ANTES do churn: cancelamento solicitado,
   cobrança, perda de recorrentes. Sem régua absoluta (não há régua validada): a leitura é
   o quartil dentro da rede, e o rótulo diz isso.
7. `mudancas_do_mes` — o que virou de um mês fechado para o outro.

READ-ONLY sobre o M1: nenhuma coluna oficial é escrita, nenhum score é recalculado.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Parâmetros (todos de LEITURA, nenhum entra em score)
# ---------------------------------------------------------------------------

RAIO_PROXIMO_M = 1_000.0
RAIO_ENTORNO_M = 2_000.0
#: Abaixo disso, dois pontos são o MESMO endereço (a própria unidade no cadastro).
DIST_MESMO_PONTO_M = 50.0
#: Outra Ultra a menos disto é canibalização — o mesmo `DIST_MIN_ULTRA_KM` do M1 (1,0 km).
DIST_CANIBALIZACAO_M = 1_000.0

#: Rampa: meses de vida exibidos e o mínimo de unidades para um ponto da curva existir.
RAMPA_MESES_MAX = 24
RAMPA_N_MINIMO = 5
#: Unidade "em rampa" = entre estes meses de operação no mês-base.
RAMPA_JANELA_NOVAS = (2, 18)

#: Desempenho só se compara entre unidades MADURAS: a coorte explica a diferença antes.
MESES_MADURA = 12

#: Concorrente "novo" = primeira aparição no feed dentro destas semanas.
SEMANAS_CONCORRENTE_NOVO = 8

#: Sinal antecedente acende no pior quartil da rede (leitura relativa, sem régua).
QUANTIL_SINAL = 0.75

#: Classes de `CONFIABILIDADE_UNIDADE` em que o modelo de retenção serve para ordenar.
CONFIABILIDADES_UTILIZAVEIS = frozenset({"Absoluto OK", "Apenas Ranking"})

ORDEM_SEVERIDADE = {"alta": 3, "media": 2, "ok": 1, "sem_base": 0}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _f(valor: Any) -> float | None:
    """Número JSON-safe: NaN/None/inf -> None."""
    try:
        x = float(valor)
    except (TypeError, ValueError):
        return None
    return x if np.isfinite(x) else None


def _r(valor: Any, casas: int = 1) -> float | None:
    x = _f(valor)
    return None if x is None else round(x, casas)


def distancias_m(lat: float, lng: float, lats: np.ndarray, lngs: np.ndarray) -> np.ndarray:
    """Haversine vetorizado, em metros."""
    raio_terra = 6_371_008.8
    p1, p2 = np.radians(lat), np.radians(lats)
    dphi = p2 - p1
    dlam = np.radians(lngs) - np.radians(lng)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlam / 2) ** 2
    return 2 * raio_terra * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def _pontos_validos(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or not len(df) or not {"lat", "lng"} <= set(df.columns):
        return pd.DataFrame(columns=["lat", "lng"])
    saida = df.copy()
    saida["lat"] = pd.to_numeric(saida["lat"], errors="coerce")
    saida["lng"] = pd.to_numeric(saida["lng"], errors="coerce")
    return saida.dropna(subset=["lat", "lng"]).reset_index(drop=True)


def _mascara_ultra(df: pd.DataFrame) -> pd.Series:
    """`True` onde a linha é uma unidade ULTRA — nossa, nunca concorrente.

    O agregador lista as unidades Ultra como qualquer academia. Sem este corte, a ficha da
    Aclimação desenhava "Ultra Academia - Aclimação" como independente a 37 m; e a lista de
    "novos no agregador" da ficha de Uberlândia trouxe TRÊS Ultras (Center Shopping a 141 m,
    Floriano Peixoto, Cesário) — relatado pelo Felipe em 18/09. A regra vale para as duas
    leituras, por isso vive aqui: cai por nome (a Ultra de outro bairro também é nossa) e
    por `rede`.
    """
    nomes = df["nome"].astype(str) if "nome" in df.columns else pd.Series("", index=df.index)
    redes = df["rede"].astype(str) if "rede" in df.columns else pd.Series("", index=df.index)
    return nomes.str.contains(r"\bultra\s+academia\b", case=False, regex=True) | redes.str.lower().eq("ultra")


# ---------------------------------------------------------------------------
# 2. Fatos territoriais
# ---------------------------------------------------------------------------


def fatos_territoriais(
    unidades: pd.DataFrame,
    concorrentes: pd.DataFrame | None,
    ultra: pd.DataFrame | None,
    hexes: pd.DataFrame | None,
    hex_da_unidade: Mapping[str, Sequence[str]] | None = None,
    pesos_hex: Mapping[str, Mapping[str, float]] | None = None,
) -> dict[str, dict[str, Any]]:
    """A praça e a concorrência de cada unidade, pela coordenada.

    `unidades`: `unidade_id`, `lat`, `lng`.
    `concorrentes`: a UNIÃO de oferta da DEC-046 (`lat`, `lng`, `classe` cadeia/
    independente, `rede`). Contar só as cadeias repetiria o defeito que a DEC-046
    corrigiu — metade do Brasil urbano lia "zero concorrente".
    `ultra`: o cadastro amplo de unidades Ultra (a própria unidade cai pelo piso de 50 m).
    `hexes`: linhas do parquet de mercado, indexadas por `hex_id`.
    `hex_da_unidade`: `unidade_id -> [hex central, vizinhos...]` (o disco k=1).

    A praça é lida no RAIO DE 1 KM, pela fração da área de cada hexágono que cai dentro do
    círculo (`pesos_hex`: `unidade_id -> {hex_id: fração}`). Sem pesos, cada hexágono do
    disco entra inteiro — era assim até 2026-09-15, e a população do "entorno" somava o
    hexágono e os 6 vizinhos (~36 km²), bem mais que um raio de 1 km (3,14 km²).
    """
    conc = _pontos_validos(concorrentes)
    ult = _pontos_validos(ultra)
    classe = (
        conc["classe"].astype(str).to_numpy()
        if "classe" in conc.columns
        else np.full(len(conc), "cadeia")
    )
    rede_col = next((c for c in ("rede", "nome_rede", "nome") if c in conc.columns), None)
    redes = conc[rede_col].astype(str).to_numpy() if rede_col else np.full(len(conc), "")
    nome_ultra = next((c for c in ("unidade", "nome") if c in ult.columns), None)

    saida: dict[str, dict[str, Any]] = {}
    for linha in _pontos_validos(unidades).itertuples(index=False):
        uid = str(linha.unidade_id)
        fatos: dict[str, Any] = {
            "lat": _r(linha.lat, 6),
            "lng": _r(linha.lng, 6),
        }

        if len(conc):
            d = distancias_m(linha.lat, linha.lng, conc["lat"].to_numpy(), conc["lng"].to_numpy())
            cadeia = classe == "cadeia"
            fatos["concorrentes_1km"] = int((d <= RAIO_PROXIMO_M).sum())
            fatos["concorrentes_2km"] = int((d <= RAIO_ENTORNO_M).sum())
            fatos["cadeias_1km"] = int(((d <= RAIO_PROXIMO_M) & cadeia).sum())
            fatos["cadeias_2km"] = int(((d <= RAIO_ENTORNO_M) & cadeia).sum())
            fatos["independentes_1km"] = fatos["concorrentes_1km"] - fatos["cadeias_1km"]
            if cadeia.any():
                i = int(np.argmin(np.where(cadeia, d, np.inf)))
                fatos["cadeia_mais_proxima_m"] = _r(d[i], 0)
                fatos["cadeia_mais_proxima_rede"] = redes[i] or None
            else:
                fatos["cadeia_mais_proxima_m"] = None
                fatos["cadeia_mais_proxima_rede"] = None
            no_entorno = (d <= RAIO_ENTORNO_M) & cadeia
            if no_entorno.any():
                contagem = pd.Series(redes[no_entorno]).value_counts()
                fatos["redes_no_entorno"] = [
                    {"rede": str(r), "n": int(n)} for r, n in contagem.head(5).items()
                ]
            else:
                fatos["redes_no_entorno"] = []
        else:
            fatos.update(
                concorrentes_1km=None, concorrentes_2km=None, cadeias_1km=None,
                cadeias_2km=None, independentes_1km=None, cadeia_mais_proxima_m=None,
                cadeia_mais_proxima_rede=None, redes_no_entorno=[],
            )

        if len(ult):
            d = distancias_m(linha.lat, linha.lng, ult["lat"].to_numpy(), ult["lng"].to_numpy())
            outras = d > DIST_MESMO_PONTO_M
            fatos["ultra_2km"] = int(((d <= RAIO_ENTORNO_M) & outras).sum())
            if outras.any():
                i = int(np.argmin(np.where(outras, d, np.inf)))
                fatos["ultra_mais_proxima_m"] = _r(d[i], 0)
                fatos["ultra_mais_proxima_nome"] = (
                    str(ult.iloc[i][nome_ultra]).strip() if nome_ultra else None
                )
            else:
                fatos["ultra_mais_proxima_m"] = None
                fatos["ultra_mais_proxima_nome"] = None
            fatos["canibalizacao"] = bool(
                fatos["ultra_mais_proxima_m"] is not None
                and fatos["ultra_mais_proxima_m"] <= DIST_CANIBALIZACAO_M
            )
        else:
            fatos.update(
                ultra_2km=None, ultra_mais_proxima_m=None, ultra_mais_proxima_nome=None,
                canibalizacao=None,
            )

        fatos.update(_praca_do_disco(uid, hexes, hex_da_unidade, (pesos_hex or {}).get(uid)))
        saida[uid] = fatos
    return saida


def _praca_do_disco(
    uid: str,
    hexes: pd.DataFrame | None,
    hex_da_unidade: Mapping[str, Sequence[str]] | None,
    pesos: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    vazio = {
        "hex_id": None, "municipio": None, "score_praca": None, "renda_per_capita": None,
        "populacao_entorno": None, "residual_entorno": None, "hexes_lidos": 0,
    }
    if hexes is None or not len(hexes) or not hex_da_unidade or uid not in hex_da_unidade:
        return vazio
    fracoes = {c: float((pesos or {}).get(c, 1.0)) for c in hex_da_unidade[uid]}
    celulas = [c for c in hex_da_unidade[uid] if c in hexes.index and fracoes[c] > 0]
    if not celulas:
        return {**vazio, "hex_id": hex_da_unidade[uid][0]}
    bloco = hexes.loc[celulas]
    fracao = pd.Series([fracoes[c] for c in celulas], index=bloco.index)
    # População e residual são VOLUMES: entram na proporção da área dentro do raio.
    pop = pd.to_numeric(bloco.get("pop_total_setor_2022"), errors="coerce") * fracao
    peso = pop.fillna(0.0)

    def media(col: str) -> float | None:
        if col not in bloco.columns:
            return None
        v = pd.to_numeric(bloco[col], errors="coerce")
        ok = v.notna() & (peso > 0)
        if ok.any():
            return float((v[ok] * peso[ok]).sum() / peso[ok].sum())
        return _f(v.mean())

    central = hex_da_unidade[uid][0]
    municipio = None
    if central in hexes.index and "nome_municipio" in hexes.columns:
        municipio = hexes.loc[central, "nome_municipio"]
    return {
        "hex_id": central,
        "municipio": None if pd.isna(municipio) else str(municipio),
        "score_praca": _r(media("score_setor_2022_calibrado"), 1),
        "renda_per_capita": _r(media("renda_per_capita_setor_2022_calibrada"), 0),
        "populacao_entorno": _r(pop.sum(min_count=1), 0),
        # Residual É ENDÓGENO para unidade existente: ele já desconta a oferta da própria
        # Ultra (o motivo que tirou a coluna do E7, DEC-043). Exibido como contexto,
        # nunca como eixo do quadrante.
        "residual_entorno": _r(
            (pd.to_numeric(bloco.get("oferta_efetiva_disponivel"), errors="coerce") * fracao).sum(min_count=1), 0
        ),
        "hexes_lidos": len(celulas),
    }


def concorrentes_no_entorno(
    lat: float,
    lng: float,
    oferta: pd.DataFrame | None,
    fatos_agregador: pd.DataFrame | None = None,
    *,
    raio_m: float = RAIO_ENTORNO_M,
    casar_m: float = DIST_MESMO_PONTO_M,
) -> list[dict[str, Any]]:
    """Cada academia a até `raio_m` da unidade, para o MAPA da ficha, da mais próxima à mais longe.

    `oferta` é a união da DEC-046 (`lat`, `lng`, `nome`, `rede`, `classe`). Os fatos do
    agregador — nota e avaliações do Wellhub e o score de vulnerabilidade, que só as
    independentes têm (DEC-035) — vêm de outra tabela e são casados pelo ponto mais
    próximo a até `casar_m`. Sem par, os campos ficam `None`: ausência nunca vira nota zero.
    """
    conc = _pontos_validos(oferta)
    if not len(conc):
        return []
    d = distancias_m(lat, lng, conc["lat"].to_numpy(), conc["lng"].to_numpy())
    # A Ultra NÃO é concorrente dela mesma. O agregador lista as unidades Ultra como qualquer
    # academia, e sem este corte a ficha da Aclimação desenhava "Ultra Academia - Aclimação"
    # como independente a 37 m. Cai por nome (a Ultra de outro bairro também é nossa) e pelo
    # piso de mesmo ponto (a própria unidade com grafia diferente no feed).
    manter = (d <= raio_m) & (d > casar_m) & ~_mascara_ultra(conc).to_numpy()
    perto = conc[manter].assign(_dist=d[manter]).sort_values("_dist", kind="stable")

    agg = _pontos_validos(fatos_agregador)
    if len(agg):
        da = distancias_m(lat, lng, agg["lat"].to_numpy(), agg["lng"].to_numpy())
        agg = agg[da <= raio_m + casar_m].reset_index(drop=True)

    saida = []
    for _, linha in perto.iterrows():
        item = {
            "lat": _r(linha["lat"], 6),
            "lng": _r(linha["lng"], 6),
            "nome": (str(linha.get("nome")).strip() or None) if pd.notna(linha.get("nome")) else None,
            "rede": (str(linha.get("rede")).strip() or None) if pd.notna(linha.get("rede")) else None,
            "classe": str(linha.get("classe") or "cadeia"),
            "distancia_m": _r(linha["_dist"], 0),
            "nota_wellhub": None,
            "avaliacoes": None,
            "vulnerabilidade": None,
        }
        if len(agg):
            dd = distancias_m(float(linha["lat"]), float(linha["lng"]), agg["lat"].to_numpy(), agg["lng"].to_numpy())
            i = int(np.argmin(dd))
            if dd[i] <= casar_m:
                par = agg.iloc[i]
                item["nota_wellhub"] = _r(par.get("nota_wellhub"), 2)
                item["avaliacoes"] = _r(par.get("qtd_avaliacoes_wellhub"), 0)
                item["vulnerabilidade"] = _r(par.get("score_vulnerabilidade"), 1)
        saida.append(item)
    return saida


# ---------------------------------------------------------------------------
# 1. Quadrante praça × execução
# ---------------------------------------------------------------------------

QUADRANTES = {
    "referencia": "Praça boa, faturamento acima da mediana",
    "execucao": "Praça boa, faturamento abaixo da mediana",
    "supera": "Praça mais fraca, faturamento acima da mediana",
    "limite": "Praça mais fraca, faturamento abaixo da mediana",
}
EXPLICACAO_QUADRANTE = {
    "referencia": "Praça forte e desempenho alto: o padrão a replicar.",
    "execucao": "Praça forte e desempenho baixo: a conversa é de gestão, não de mercado.",
    "supera": "Praça mais fraca e desempenho alto: a operação compensa o chão.",
    "limite": "Praça fraca e desempenho baixo: ação comercial tem teto; olhar custo e formato.",
}


def quadrante_praca_execucao(
    unidades: Iterable[Mapping[str, Any]],
    *,
    somente_maduras: bool = True,
) -> dict[str, Any]:
    """Pontos do gráfico praça × desempenho e o quadrante de cada unidade.

    Cada item de `unidades`: `id`, `nome`, `uf`, `coorte_rotulo`, `meses_operacao`,
    `score_praca` (eixo X, régua absoluta da DEC-040) e `faturamento` do último mês
    FECHADO (eixo Y).

    Os cortes são as MEDIANAS do conjunto exibido — é leitura relativa, não meta. E só
    maduras por padrão: comparar a unidade de 4 meses com a de 4 anos mediria a coorte.
    """
    pontos = []
    for u in unidades:
        x, y = _f(u.get("score_praca")), _f(u.get("faturamento"))
        meses = _f(u.get("meses_operacao"))
        if x is None or y is None:
            continue
        if somente_maduras and (meses is None or meses < MESES_MADURA):
            continue
        pontos.append({**u, "score_praca": x, "faturamento": y})

    if len(pontos) < 4:
        return {"pontos": pontos, "corte_praca": None, "corte_desempenho": None,
                "contagem": {q: 0 for q in QUADRANTES}, "n": len(pontos)}

    corte_x = float(np.median([p["score_praca"] for p in pontos]))
    corte_y = float(np.median([p["faturamento"] for p in pontos]))
    contagem = dict.fromkeys(QUADRANTES, 0)
    for p in pontos:
        forte = p["score_praca"] >= corte_x
        alto = p["faturamento"] >= corte_y
        chave = (
            "referencia" if forte and alto
            else "execucao" if forte
            else "supera" if alto
            else "limite"
        )
        p["quadrante"] = chave
        p["quadrante_rotulo"] = QUADRANTES[chave]
        contagem[chave] += 1
    return {
        "pontos": pontos,
        "corte_praca": round(corte_x, 1),
        "corte_desempenho": round(corte_y, 2),
        "contagem": contagem,
        "n": len(pontos),
    }


# ---------------------------------------------------------------------------
# 3. Retenção
# ---------------------------------------------------------------------------


def _cod(valor: Any) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    texto = str(valor).strip()
    texto = texto[:-2] if texto.endswith(".0") else texto
    # O artefato de retenção grava "01" e o cadastro, "1": sem isto, as unidades de código
    # de um dígito somem do join em silêncio.
    return texto.lstrip("0") or texto if texto.isdigit() else texto


def retencao_por_unidade(
    retencao: pd.DataFrame | None,
    cod_por_unidade: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Risco de cancelamento e LTV por unidade, casados pelo `cod_unidade` do cadastro.

    O artefato não traz nome de unidade (a coluna `UNIDADE` vem nula): o único join que
    existe é o código. Unidade sem código no cadastro fica sem leitura — e isso é dito.

    A probabilidade ABSOLUTA só é exibida onde o próprio modelo diz que pode
    (`USAR_PROB_ABSOLUTA == "Sim"`); fora disso, sobra a posição relativa.
    """
    if retencao is None or not len(retencao) or "cod_unidade" not in retencao.columns:
        return {}
    base = retencao.copy()
    base["_cod"] = base["cod_unidade"].map(_cod)
    base = base.drop_duplicates("_cod").set_index("_cod")
    prob = pd.to_numeric(base.get("PROB_CANCEL_90D_MEDIA"), errors="coerce")
    # O modelo classifica a PRÓPRIA confiabilidade por unidade. Onde ele se declara instável,
    # inconclusivo ou descalibrado (unidade nova, poucos alunos ou poucos cancelamentos),
    # a probabilidade não ordena nada — e sem este corte essas unidades LIDERAVAM o ranking
    # de risco da rede (Novo Gama no percentil 100 com 98 alunos modelados).
    if "CONFIABILIDADE_UNIDADE" in base.columns:
        confiavel = base["CONFIABILIDADE_UNIDADE"].astype(str).str.strip().isin(CONFIABILIDADES_UTILIZAVEIS)
    else:
        confiavel = pd.Series(True, index=base.index)
    percentil = prob.where(confiavel).rank(pct=True) * 100

    saida: dict[str, dict[str, Any]] = {}
    for uid, cod in cod_por_unidade.items():
        chave = _cod(cod)
        if not chave or chave not in base.index:
            continue
        linha = base.loc[chave]
        utilizavel = bool(confiavel.get(chave, False))
        absoluta = utilizavel and str(linha.get("USAR_PROB_ABSOLUTA", "")).strip().lower() == "sim"
        p12 = _f(linha.get("P_CANCEL_12M_MEDIA"))
        # O ticket do artefato e' de TABELA (tres valores em toda a rede: 117/147/197). Fica como
        # fato, mas a receita em risco e' calculada fora daqui, sobre a receita por recorrente
        # REAL da operacao (`receita_recorrente_em_risco`) — decisao do Felipe, 17/09.
        ticket = _f(linha.get("TICKET_MEDIO_UNIDADE"))
        saida[str(uid)] = {
            "utilizavel": utilizavel,
            "alunos_modelados": _r(linha.get("N_ALUNOS"), 0),
            "prob_cancel_90d_pct": _r(100 * _f(linha.get("PROB_CANCEL_90D_MEDIA")), 1)
            if absoluta and _f(linha.get("PROB_CANCEL_90D_MEDIA")) is not None
            else None,
            "risco_percentil": _r(percentil.get(chave), 0) if utilizavel else None,
            "p_cancel_12m_pct": _r(100 * p12, 1) if absoluta and p12 is not None else None,
            "ticket_medio": _r(ticket, 0),
            "ltv_12m_mediano": _r(linha.get("LTV_PROSPECTIVO_12M_MEDIANO"), 0),
            "meses_ativos_12m": _r(linha.get("E_MESES_ATIVOS_12M_MEDIANO"), 1),
            "ltv_fragil_pct": _r(100 * (_f(linha.get("PCT_LTV_FRAGIL")) or 0), 1),
            "ltv_em_risco_pct": _r(100 * (_f(linha.get("PCT_LTV_EM_RISCO")) or 0), 1),
            "ltv_duravel_pct": _r(100 * (_f(linha.get("PCT_LTV_DURAVEL")) or 0), 1),
            "ltv_alta_durabilidade_pct": _r(
                100 * (_f(linha.get("PCT_LTV_ALTA_DURABILIDADE")) or 0), 1
            ),
            "confiabilidade": str(linha.get("CONFIABILIDADE_UNIDADE") or "") or None,
            "probabilidade_absoluta_valida": absoluta,
        }
    return saida


def receita_recorrente_em_risco(
    recorrentes: float | None,
    p_cancel_12m_pct: float | None,
    receita_por_recorrente: float | None,
) -> float | None:
    """Mensalidade que o modelo espera perder em 12 meses, por mes.

    RECORRENTES (pagantes de balcao) x chance de cancelar em 12 meses x receita por
    recorrente REAL — nao `ativos`, porque aluno de agregador nao cancela contrato com a
    unidade, e nao o ticket de TABELA do artefato, que so' tem tres valores na rede toda
    enquanto o real vai de R$ 109 a R$ 276 (medido em 17/09).

    Devolve `None` quando a probabilidade nao esta' disponivel: onde o proprio modelo diz
    que o numero absoluto nao vale, a conta viraria reais com falsa precisao.
    """
    if recorrentes is None or p_cancel_12m_pct is None or receita_por_recorrente is None:
        return None
    return _r(recorrentes * (p_cancel_12m_pct / 100.0) * receita_por_recorrente, 0)


# ---------------------------------------------------------------------------
# 4. Concorrentes novos
# ---------------------------------------------------------------------------


def concorrentes_novos(
    snapshots: pd.DataFrame | None,
    coordenadas: pd.DataFrame | None,
    unidades: pd.DataFrame,
    *,
    semanas: int = SEMANAS_CONCORRENTE_NOVO,
    raio_m: float = RAIO_ENTORNO_M,
) -> dict[str, Any]:
    """Academias que ENTRARAM no feed recentemente, perto de cada unidade.

    O snapshot semanal não guarda coordenada (DEC-029, rota B: lida e descartada); ela vem
    das tabelas de vulnerabilidade, pela chave `(fonte, chave_snapshot)`.

    "Nova" = a primeira semana em que a chave aparece é posterior à PRIMEIRA semana da
    série e cai nas últimas `semanas`. A exclusão da primeira semana não é detalhe: sem
    ela, no começo da série TODO o universo pareceria ter acabado de abrir.

    Entrar no feed não é inaugurar — pode ser credenciamento no agregador. A tela diz.
    """
    vazio = {"disponivel": False, "semanas_na_serie": 0, "ultima_semana": None, "por_unidade": {}}
    if snapshots is None or not len(snapshots) or coordenadas is None or not len(coordenadas):
        return vazio
    semanas_serie = sorted(snapshots["semana"].astype(str).unique())
    if len(semanas_serie) < 2:
        return {**vazio, "semanas_na_serie": len(semanas_serie),
                "ultima_semana": semanas_serie[-1] if semanas_serie else None}

    serie = snapshots.assign(semana=snapshots["semana"].astype(str))
    primeira = (
        serie.groupby(["fonte", "chave_snapshot"], observed=True)["semana"]
        .min()
        .reset_index(name="primeira_semana")
    )
    # A primeira semana descartada é a DA PRÓPRIA FONTE, não a da série inteira. Cada feed
    # começa a ser fotografado num domingo diferente: em 18/09 a série tinha `unidades` desde
    # a semana 2026-31 e `wellhub` só a partir de 2026-36 — contra a primeira semana GLOBAL,
    # as 22.550 chaves do WellHub passavam como recém-chegadas, e a ficha de Uberlândia
    # listava o bairro inteiro "no agregador desde 2026-36" (Felipe, 18/09). Por fonte,
    # sobram 142.
    estreia = primeira.groupby("fonte", observed=True)["primeira_semana"].transform("min")
    recentes = set(semanas_serie[-semanas:])
    novos = primeira[
        (primeira["primeira_semana"] != estreia)
        & primeira["primeira_semana"].isin(recentes)
    ]
    coords = _pontos_validos(coordenadas)
    if "fonte" not in coords.columns or "chave_snapshot" not in coords.columns:
        return {**vazio, "semanas_na_serie": len(semanas_serie)}
    novos = novos.merge(
        coords.drop_duplicates(["fonte", "chave_snapshot"]),
        on=["fonte", "chave_snapshot"],
        how="inner",
    )
    # A Ultra entra no feed do agregador como qualquer academia — e não é concorrente nova.
    novos = novos[~_mascara_ultra(novos).to_numpy()].reset_index(drop=True)
    por_unidade: dict[str, list[dict[str, Any]]] = {}
    if len(novos):
        lats, lngs = novos["lat"].to_numpy(), novos["lng"].to_numpy()
        for linha in _pontos_validos(unidades).itertuples(index=False):
            d = distancias_m(linha.lat, linha.lng, lats, lngs)
            perto = np.where(d <= raio_m)[0]
            if not len(perto):
                continue
            itens = [
                {
                    "nome": str(novos.iloc[i].get("nome") or "").strip() or None,
                    "rede": (str(novos.iloc[i].get("rede")).strip() or None)
                    if "rede" in novos.columns and pd.notna(novos.iloc[i].get("rede"))
                    else None,
                    "fonte": str(novos.iloc[i]["fonte"]),
                    "primeira_semana": str(novos.iloc[i]["primeira_semana"]),
                    "distancia_m": _r(d[i], 0),
                }
                for i in perto
            ]
            por_unidade[str(linha.unidade_id)] = sorted(itens, key=lambda x: x["distancia_m"] or 0)
    return {
        "disponivel": True,
        "semanas_na_serie": len(semanas_serie),
        "ultima_semana": semanas_serie[-1],
        "por_unidade": por_unidade,
    }


# ---------------------------------------------------------------------------
# 5. Rampa
# ---------------------------------------------------------------------------


def _base_rampa(cheio: pd.DataFrame) -> pd.DataFrame:
    if not len(cheio):
        return cheio
    ok = (
        cheio["mes_completo"].fillna(False).astype(bool)
        & cheio["operacao_mes_cheio"].fillna(False).astype(bool)
    )
    base = cheio[ok].copy()
    base["meses_operacao"] = pd.to_numeric(base["meses_operacao"], errors="coerce")
    return base[base["meses_operacao"].between(1, RAMPA_MESES_MAX)]


def curva_de_rampa(cheio: pd.DataFrame, metrica: str = "faturamento") -> list[dict[str, Any]]:
    """p25/p50/p75 da métrica por mês de vida, só com meses FECHADOS e operação cheia.

    O mês 0 (inauguração) fica fora: mistura quem abriu no dia 2 com quem abriu no 29.
    Ponto com menos de `RAMPA_N_MINIMO` unidades não é desenhado — mediana de três é
    anedota.
    """
    base = _base_rampa(cheio)
    if not len(base) or metrica not in base.columns:
        return []
    saida = []
    for mes, grupo in base.groupby("meses_operacao"):
        valores = pd.to_numeric(grupo[metrica], errors="coerce").dropna()
        if len(valores) < RAMPA_N_MINIMO:
            continue
        saida.append({
            "mes": int(mes),
            "p25": _r(valores.quantile(0.25), 0),
            "p50": _r(valores.median(), 0),
            "p75": _r(valores.quantile(0.75), 0),
            "n": int(len(valores)),
        })
    return saida


def trajetoria_da_unidade(
    cheio: pd.DataFrame, unidade_id: str, metrica: str = "faturamento"
) -> list[dict[str, Any]]:
    base = _base_rampa(cheio)
    if not len(base):
        return []
    serie = base[base["unidade_id"] == unidade_id].sort_values("meses_operacao")
    return [
        {"mes": int(m), "valor": _r(v, 0), "competencia": str(c)}
        for m, v, c in zip(
            serie["meses_operacao"], pd.to_numeric(serie[metrica], errors="coerce"),
            serie["competencia"], strict=False,
        )
        if _f(v) is not None
    ]


def posicao_na_rampa(
    cheio: pd.DataFrame,
    competencia: str | None,
    ids: Iterable[str] | None = None,
    metrica: str = "faturamento",
) -> list[dict[str, Any]]:
    """Unidades em rampa no mês-base e o desvio contra a mediana da rede na MESMA idade.

    `desvio_pct` = valor / p50 da idade − 1. A faixa (abaixo do p25, entre, acima do p75)
    é a leitura; o desvio é o tamanho.
    """
    if not competencia or not len(cheio):
        return []
    curva = {p["mes"]: p for p in curva_de_rampa(cheio, metrica)}
    base = _base_rampa(cheio)
    base = base[base["competencia"].astype(str) == str(competencia)]
    lo, hi = RAMPA_JANELA_NOVAS
    base = base[base["meses_operacao"].between(lo, hi)]
    if ids is not None:
        base = base[base["unidade_id"].isin(set(ids))]
    saida = []
    for linha in base.itertuples(index=False):
        ref = curva.get(int(linha.meses_operacao))
        valor = _f(getattr(linha, metrica))
        if ref is None or valor is None or not ref["p50"]:
            continue
        faixa = (
            "abaixo" if valor < (ref["p25"] or 0)
            else "acima" if valor > (ref["p75"] or float("inf"))
            else "na_curva"
        )
        saida.append({
            "id": str(linha.unidade_id),
            "nome": str(getattr(linha, "unidade_cru", "") or "").strip(),
            "uf": str(getattr(linha, "uf", "") or ""),
            "meses_operacao": int(linha.meses_operacao),
            "valor": _r(valor, 0),
            "p25": ref["p25"],
            "p50": ref["p50"],
            "p75": ref["p75"],
            "desvio_pct": _r(100 * (valor / ref["p50"] - 1), 1),
            "faixa": faixa,
        })
    return sorted(saida, key=lambda x: x["desvio_pct"] if x["desvio_pct"] is not None else 0)


# ---------------------------------------------------------------------------
# 6. Sinais antecedentes
# ---------------------------------------------------------------------------

SINAIS = {
    "cancelamento_solicitado_pct": {
        "rotulo": "Cancelamento solicitado",
        "detalhe": "pedidos de cancelamento em aberto no fim do mês, sobre os recorrentes",
        "pior": "alto",
    },
    "em_cobranca_pct": {
        "rotulo": "Em cobrança",
        "detalhe": "recorrentes com cobrança em aberto no fim do mês",
        "pior": "alto",
    },
    "recorrentes_3m_pct": {
        "rotulo": "Recorrentes em 3 meses",
        "detalhe": "variação da base de recorrentes contra três meses fechados antes",
        "pior": "baixo",
    },
}


def sinais_antecedentes(
    cheio: pd.DataFrame,
    base_diaria: pd.DataFrame,
    competencia: str | None,
) -> dict[str, dict[str, Any]]:
    """Os três sinais que costumam vir ANTES do churn, com a posição de cada unidade.

    Não existe régua validada para nenhum deles, então não há alerta absoluto: o sinal
    acende quando a unidade está no pior quartil da rede NAQUELE mês (`QUANTIL_SINAL`).
    Só unidades com operação cheia entram na distribuição.

    `cancelamento_solicitado` é a foto do fim do mês (último dia com dado), como os
    demais snapshots da Growth.
    """
    if not competencia or not len(cheio):
        return {}
    mes = cheio[
        (cheio["competencia"].astype(str) == str(competencia))
        & cheio["operacao_mes_cheio"].fillna(False).astype(bool)
    ].set_index("unidade_id")
    if not len(mes):
        return {}

    quadro = pd.DataFrame(index=mes.index)
    pagantes = pd.to_numeric(mes["pagantes"], errors="coerce")
    quadro["em_cobranca_pct"] = pd.to_numeric(mes.get("em_cobranca_pct"), errors="coerce")

    solicitado = pd.Series(np.nan, index=mes.index)
    if len(base_diaria) and "cancelamento_solicitado" in base_diaria.columns:
        periodo = base_diaria["_data"].dt.to_period("M").astype(str)
        doMes = base_diaria[periodo == str(competencia)].sort_values("_data", kind="stable")
        ultimo = doMes.groupby("unidade_id")["cancelamento_solicitado"].last()
        solicitado = pd.to_numeric(ultimo, errors="coerce").reindex(mes.index)
    quadro["cancelamento_solicitado"] = solicitado
    quadro["cancelamento_solicitado_pct"] = 100 * solicitado / pagantes.where(pagantes > 0)

    tres_antes = str(pd.Period(str(competencia), freq="M") - 3)
    antes = cheio[cheio["competencia"].astype(str) == tres_antes].set_index("unidade_id")
    pag_antes = pd.to_numeric(antes.get("pagantes"), errors="coerce").reindex(mes.index)
    quadro["recorrentes_3m_pct"] = 100 * (pagantes / pag_antes.where(pag_antes > 0) - 1)

    limiares: dict[str, float | None] = {}
    for chave, spec in SINAIS.items():
        serie = quadro[chave].dropna()
        if len(serie) < 8:
            limiares[chave] = None
            continue
        q = QUANTIL_SINAL if spec["pior"] == "alto" else 1 - QUANTIL_SINAL
        limiares[chave] = float(serie.quantile(q))

    saida: dict[str, dict[str, Any]] = {}
    for uid, linha in quadro.iterrows():
        itens = []
        for chave, spec in SINAIS.items():
            valor = _f(linha[chave])
            limiar = limiares[chave]
            aceso = (
                valor is not None and limiar is not None
                and (valor >= limiar if spec["pior"] == "alto" else valor <= limiar)
                # Quartil degenerado não acende: "0% em cobrança" no pior quartil, ou
                # "recorrentes estáveis" no quartil de queda, não é sinal de nada.
                and (valor > 0 if spec["pior"] == "alto" else valor < 0)
            )
            itens.append({
                "chave": chave,
                "rotulo": spec["rotulo"],
                "detalhe": spec["detalhe"],
                "valor": _r(valor, 1),
                "limiar_quartil": _r(limiar, 1),
                "aceso": bool(aceso),
            })
        saida[str(uid)] = {
            "cancelamento_solicitado": _r(linha["cancelamento_solicitado"], 0),
            "sinais": itens,
            "acesos": sum(1 for i in itens if i["aceso"]),
        }
    return saida


# ---------------------------------------------------------------------------
# 7. O que mudou
# ---------------------------------------------------------------------------


def mudancas_do_mes(
    atual: Mapping[str, Any],
    anterior: Mapping[str, Any],
    nomes: Mapping[str, str],
    *,
    competencia: str | None,
    inauguradas: Iterable[str] = (),
    rampa: Sequence[Mapping[str, Any]] = (),
    concorrencia: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    semanas_concorrencia: int = 4,
    ultima_semana: str | None = None,
) -> list[dict[str, Any]]:
    """Eventos do último mês fechado contra o anterior, do mais grave ao mais leve.

    `atual`/`anterior`: `unidade_id -> Diagnostico` (de `rede_diagnostico.diagnosticar`).
    Só entra quem está nos dois meses — unidade sem mês anterior não "piorou", ela
    começou. `tom`: `neg`, `pos` ou `neutro`, para a tela pintar.
    """
    eventos: list[dict[str, Any]] = []
    ids = set(nomes)

    for uid in sorted(ids & set(atual) & set(anterior)):
        a, b = atual[uid], anterior[uid]
        nome = nomes[uid]
        sa, sb = ORDEM_SEVERIDADE.get(a.severidade, 0), ORDEM_SEVERIDADE.get(b.severidade, 0)
        if sb and sa and sa != sb:
            piorou = sa > sb
            eventos.append({
                "tipo": "severidade", "unidade_id": uid, "nome": nome,
                "tom": "neg" if piorou else "pos", "peso": 30 + 5 * abs(sa - sb),
                "de": _rotulo_sev(b.severidade), "para": _rotulo_sev(a.severidade),
                # O "por quê" da linha: quem piorou mostra os alertas de AGORA; quem melhorou,
                # os alertas que deixaram de existir.
                "motivos": (
                    [x.titulo for x in a.alertas]
                    if piorou
                    else [x.titulo for x in b.alertas if x.codigo not in {y.codigo for y in a.alertas}]
                ),
                "texto": (
                    f"{nome} {'piorou' if piorou else 'melhorou'}: "
                    f"{_rotulo_sev(b.severidade)} → {_rotulo_sev(a.severidade)}."
                ),
            })
        novos = {x.codigo for x in a.alertas} - {x.codigo for x in b.alertas}
        for alerta in a.alertas:
            if alerta.codigo in novos:
                eventos.append({
                    "tipo": "alerta_novo", "unidade_id": uid, "nome": nome, "tom": "neg",
                    "peso": 20 if alerta.nivel == "grave" else 12,
                    "alerta": alerta.titulo,
                    "texto": f"Alerta novo em {nome}: {alerta.titulo.lower()}.",
                })
        if (
            getattr(a, "faixa_faturamento", None) and getattr(b, "faixa_faturamento", None)
            and a.faixa_faturamento != b.faixa_faturamento
            and "sem_dado" not in (a.faixa_faturamento, b.faixa_faturamento)
        ):
            eventos.append({
                "tipo": "faixa", "unidade_id": uid, "nome": nome, "tom": "neutro", "peso": 8,
                "de": b.faixa_faturamento_rotulo, "para": a.faixa_faturamento_rotulo,
                "texto": (
                    f"{nome} mudou de faixa de faturamento: {b.faixa_faturamento_rotulo} → "
                    f"{a.faixa_faturamento_rotulo}."
                ),
            })

    for uid in inauguradas:
        if uid in ids:
            eventos.append({
                "tipo": "inauguracao", "unidade_id": uid, "nome": nomes[uid], "tom": "pos",
                "peso": 10, "texto": f"{nomes[uid]} completou o primeiro mês de operação.",
            })

    for r in rampa:
        if r.get("id") in ids and r.get("faixa") == "abaixo":
            eventos.append({
                "tipo": "rampa", "unidade_id": r["id"], "nome": r.get("nome") or nomes[r["id"]],
                "tom": "neg", "peso": 15,
                "texto": (
                    f"{r.get('nome') or nomes[r['id']]} está abaixo do quartil inferior da rampa "
                    f"no mês {r['meses_operacao']} ({_pct(r.get('desvio_pct'))} vs mediana da rede)."
                ),
            })

    if concorrencia and ultima_semana:
        corte = _semana_menos(ultima_semana, semanas_concorrencia)
        for uid, itens in concorrencia.items():
            if uid not in ids:
                continue
            recentes = [i for i in itens if str(i.get("primeira_semana", "")) > corte]
            if not recentes:
                continue
            mais_perto = recentes[0]
            quem = mais_perto.get("rede") or mais_perto.get("nome") or "academia"
            eventos.append({
                "tipo": "concorrente", "unidade_id": uid, "nome": nomes[uid], "tom": "neg",
                "peso": 18,
                "texto": (
                    f"{len(recentes)} academia(s) nova(s) no feed a até 2 km de {nomes[uid]} — "
                    f"a mais próxima, {quem}, a {_metros(mais_perto.get('distancia_m'))}."
                ),
            })

    eventos.sort(key=lambda e: (-e["peso"], e["nome"]))
    for e in eventos:
        e["competencia"] = competencia
        e.pop("peso", None)
    return eventos


def _rotulo_sev(chave: str) -> str:
    return {"alta": "prioridade alta", "media": "atenção", "ok": "sem alerta"}.get(chave, chave)


def _pct(v: Any) -> str:
    x = _f(v)
    if x is None:
        return "—"
    return f"{'+' if x > 0 else ''}{x:.0f}%".replace(".", ",")


def _metros(v: Any) -> str:
    x = _f(v)
    if x is None:
        return "distância desconhecida"
    return f"{x / 1000:.1f} km".replace(".", ",") if x >= 1000 else f"{x:.0f} m"


def _semana_menos(semana: str, n: int) -> str:
    """`AAAA-SS` menos `n` semanas ISO, no mesmo formato."""
    try:
        ano, num = str(semana).split("-")
        data = pd.Timestamp.fromisocalendar(int(ano), int(num), 1) - pd.Timedelta(weeks=n)
        iso = data.isocalendar()
        return f"{iso.year:04d}-{iso.week:02d}"
    except (ValueError, TypeError):
        return ""
