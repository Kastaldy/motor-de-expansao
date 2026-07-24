"""Motor property-first de viabilidade do imovel (BLK-DIM-11).

Dado um imovel real (`lat,lng` + `m2` + `aluguel pedido` + `demanda_premissa`),
devolve: contexto do entorno (catchment), faixa de alunos por densidade (curva
tamanho->densidade, NAO geografica), flag de zona morta, viabilidade financeira no
cenario pedido (margem/payback/ROIC), aluguel-teto, break-even e grade de
sensibilidade demanda x aluguel.

GUARDRAIL CENTRAL (4 NO-GOs):
    - A demanda NUNCA e derivada de lat/lng. `demanda_premissa` e entrada EXPLICITA
      do operador; `demanda_fonte` e sempre "premissa_explicita".
    - `lat/lng` so alimentam o catchment (contexto pop/renda) e a flag de zona morta.
    - A faixa de alunos por densidade depende SO de `m2` + base de comparaveis — nao de geo.
    - Sem I/O de parquet interno: todos os DataFrames sao injetados pelo chamador.

READ-ONLY sobre o M1: nao recalcula `score_priorizacao`, `hex_score_estrutural`,
pesos, carteira, plano nem artefatos oficiais (DEC-001/DEC-008). Funcao pura, sem UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from typing import Any

import numpy as np
import pandas as pd

from motor_expansao.dimensionamento.catchment_batch import calcular_catchment_unidade
from motor_expansao.dimensionamento.config import (
    RAIO_CATCHMENT_KM,
    SIM_MENSALIDADE_BALCAO,
    SIM_PARCELAS_OBRA_DEFAULT,
    SIM_SHARE_BALCAO,
    SIM_TAXA_FRANQUIA,
)
from motor_expansao.dimensionamento.simulador import (
    Premissas,
    ViabilidadeResult,
    aluguel_teto_clusters,
    alunos_para_margem,
    simular,
)

# --- Thresholds de zona morta (exogenos; NAO preveem alunos) -----------------
POP_ZONA_MORTA_MIN: float = 5_000.0       # alinhado com POP_MIN_ACIONAVEL do dashboard
RENDA_ZONA_MORTA_MIN: float = 1_600.0     # renda per capita minima do entorno

# --- Faixa de comparaveis por densidade (curva tamanho->densidade) -----------
FAIXA_M2_TOLERANCIA: float = 0.20         # +/-20% do m2 do imovel
FAIXA_M2_TOLERANCIA_ALARGADA: float = 0.50  # +/-50% se N < N_MIN_COMPARAVEIS na janela estreita
N_MIN_COMPARAVEIS: int = 3                # minimo de comparaveis para nao alargar

# --- Grade de sensibilidade (defaults) ---------------------------------------
ALUNOS_RANGE_DEFAULT: tuple[float, ...] = (200.0, 400.0, 600.0, 800.0, 1000.0, 1200.0)
ALUGUEL_RANGE_FATOR: tuple[float, ...] = (0.6, 0.8, 1.0, 1.2, 1.5)  # x aluguel_pedido

# --- Guardrail explicito -----------------------------------------------------
DEMANDA_FONTE_PREMISSA: str = "premissa_explicita"

# --- Mapeamento marca -> formato de operacao (BLK-VIAB-07) -------------------
# Rotula comparaveis por formato para permitir filtrar a curva tamanho->densidade
# aos pares do MESMO formato (low_cost_massa nao mistura com boutique_premium).
# NAO vai para config.py (fonte canonica do M1, intocavel). READ-ONLY sobre o M1.
FORMATO_LOW_COST_MASSA: str = "low_cost_massa"
FORMATO_BOUTIQUE_PREMIUM: str = "boutique_premium"
FORMATO_POR_MARCA: dict[str, str] = {
    "ultra": FORMATO_LOW_COST_MASSA,          # posicionamento explicito §1 (low-cost/massa)
    "skyfit": FORMATO_LOW_COST_MASSA,          # concorrente low-cost direto (§1); metragem nula -> nao entra na curva
    "engenharia_do_corpo": FORMATO_BOUTIQUE_PREMIUM,  # premium/personal; densidade e porte distintos
}

# --- Composicao balcao/agregadores (estudo §5; Ultra ~69% balcao / ~31% agregadores) ---
# A demanda_premissa representa alunos TOTAIS; o split alimenta o DRE com 2 tickets
# (balcao a ticket cheio + agregadores = fracao do ticket cheio).
# FIN-VIAB-01: REEXPORTA `config.SIM_SHARE_BALCAO` — o 0.69 tem UM dono (o config.py).
# Antes este literal era copiado tambem em web/server/app.py::_serie_motor, e mudar um
# sem o outro fazia a tela divergir do proprio grafico.
SHARE_BALCAO_DEFAULT: float = SIM_SHARE_BALCAO

# --- Guardrail de envelope de metragem (BLK-VIAB-06) -------------------------
ENVELOPE_MIN: float = 600.0   # m2 mínimo da base de calibração Ultra (636 m2 - folga)
ENVELOPE_MAX: float = 3000.0  # m2 máximo (base calibrada até 2800 m2 + folga; MAPE 85% além)


@dataclass
class ViabilidadePontoResult:
    """Resultado consolidado do motor de viabilidade property-first (BLK-DIM-11).

    GUARDRAIL: `demanda_premissa` e entrada do operador; NUNCA derivada de lat/lng.
    `demanda_fonte` e sempre "premissa_explicita".
    """

    # --- Contexto do imovel (inputs ecoados) ---
    lat: float
    lng: float
    m2: float
    aluguel_pedido: float
    demanda_premissa: float

    # --- Faixa de alunos por densidade (None se base_calibracao_df ausente) ---
    faixa_alunos_p10: float | None
    faixa_alunos_p50: float | None
    faixa_alunos_p90: float | None
    n_comparaveis: int | None

    # --- Flag de zona morta (None se setores_df ausente -> catchment nao rodado) ---
    flag_zona_morta: bool | None
    motivo_zona_morta: str | None

    # --- Contexto do entorno (catchment; None se setores_df ausente) ---
    pop_captacao: float | None
    renda_per_capita_captacao: float | None

    # --- Viabilidade no cenario pedido (demanda = premissa explicita) ---
    # FIN-VIAB-01: `viabilidade` e a saida de `simular()` — traz a serie mensal
    # completa (M-4..M+60) e TODOS os KPIs ja calculados. Ninguem recalcula nada.
    viabilidade: ViabilidadeResult
    # Aluguel-teto CANONICO (excecao, 30% do faturamento bruto steady). Vem de
    # `aluguel_teto_clusters` — NAO mais da inversao por margem EBITDA-alvo, que
    # devolvia R$105.813,13 onde a tela mostrava R$55.535,18 no mesmo cenario.
    aluguel_teto_calculado: float
    # Break-even de EBITDA em alunos TOTAIS (mix balcao/agregadores escalando junto).
    # Antes era em alunos de BALCAO e a tela comparava com a demanda TOTAL.
    alunos_breakeven: float

    # --- Grade de sensibilidade ---
    grade_sensibilidade: pd.DataFrame

    # --- Split da premissa (auditabilidade; derivados de demanda_premissa * share) ---
    alunos_balcao_premissa: float = 0.0
    alunos_agregadores_premissa: float = 0.0

    # --- Alunos para a margem-alvo (FIN-VIAB-01: unidade corrigida) ---
    # Antes vinha de `alunos_minimos_viaveis(margem_alvo=X)`, que variava SO o balcao
    # mantendo os agregadores congelados — numero nao comparavel com a demanda total.
    # Agora sai de `alunos_para_margem()`, em forma fechada e em alunos TOTAIS, na
    # MESMA regua de `alunos_breakeven`. `inf` quando a margem-alvo e inatingivel.
    alunos_para_margem_alvo: float = float("nan")

    # --- Guardrail: demanda NUNCA derivada de geo ---
    demanda_fonte: str = DEMANDA_FONTE_PREMISSA

    # --- Guardrail de envelope de metragem (BLK-VIAB-06) ---
    flag_fora_envelope: bool = False

    # --- Aluguel-teto: as 3 faixas + o teto sobre o p10 da faixa (FIN-VIAB-01) ---
    # `aluguel_teto_faixas` = {"ideal": 15%, "teto": 20%, "excecao": 30%, "canonico"}.
    aluguel_teto_faixas: dict[str, float] = field(default_factory=dict)
    # Teto CANONICO (30%) sobre o faturamento do cenario p10 da faixa de alunos. E o
    # unico teto NAO circular: o teto sobre a demanda assumida so devolve a premissa
    # que o operador digitou. None quando nao ha p10 (base de comparaveis ausente).
    aluguel_teto_p10: float | None = None

    # --- Break-even de CAIXA (EBITDA - IR cobrindo tambem a PMT), em alunos TOTAIS ---
    alunos_breakeven_caixa: float = 0.0


def faixa_alunos_por_densidade(
    m2: float,
    base_calibracao_df: pd.DataFrame,
    *,
    tolerancia: float = FAIXA_M2_TOLERANCIA,
    tolerancia_alargada: float = FAIXA_M2_TOLERANCIA_ALARGADA,
    n_min: int = N_MIN_COMPARAVEIS,
    formato: str | None = None,
) -> dict:
    """Faixa de alunos plausivel derivada da curva tamanho->densidade (NAO geografica).

    Usa `alunos_por_m2` dos comparaveis Ultra numa janela de m2 em torno do imovel.
    Retorna percentis (p10/p50/p90) de `alunos_por_m2` x m2 -> faixa de ALUNOS.

    GUARDRAIL: nao recebe lat/lng. A faixa depende SO de `m2` + base de comparaveis.

    Janela:
      1. +/-`tolerancia` (20%) do m2 do imovel.
      2. Se N < `n_min`: alarga para +/-`tolerancia_alargada` (50%).
      3. Se ainda N < `n_min`: usa a base inteira valida.

    formato (opcional): quando != None, restringe os comparaveis ao mesmo formato
    de operacao (via coluna 'formato' ou 'marca'->FORMATO_POR_MARCA). Se o filtro
    deixar < n_min linhas, faz fallback para a base completa. formato=None mantem
    o comportamento historico byte-a-byte.

    Retorna dict:
      {"faixa_alunos_p10": float, "faixa_alunos_p50": float, "faixa_alunos_p90": float,
       "n_comparaveis": int}
    ou, se a base nao tiver as colunas exigidas ou ficar vazia apos limpeza:
      {"faixa_alunos_p10": None, ..., "n_comparaveis": 0}
    """
    vazio = {
        "faixa_alunos_p10": None,
        "faixa_alunos_p50": None,
        "faixa_alunos_p90": None,
        "n_comparaveis": 0,
    }
    if base_calibracao_df is None or len(base_calibracao_df) == 0:
        return vazio
    if "alunos_por_m2" not in base_calibracao_df.columns:
        return vazio

    df = base_calibracao_df.copy()

    # Filtro OPCIONAL por formato (BLK-VIAB-07): mantem so comparaveis do mesmo
    # formato de operacao. formato=None => byte-identico ao comportamento antigo.
    # Coluna 'formato' e derivada de 'marca' via FORMATO_POR_MARCA quando ausente.
    # Fallback gracioso: se apos o filtro sobrarem < n_min linhas (ou a coluna nao
    # for derivavel), usa a base completa (nao filtrada) — evita degradar a faixa.
    if formato is not None:
        col_formato: pd.Series | None = None
        if "formato" in df.columns:
            col_formato = df["formato"].astype("string")
        elif "marca" in df.columns:
            col_formato = df["marca"].astype("string").map(FORMATO_POR_MARCA)
        if col_formato is not None:
            df_filtrado = df[col_formato == formato]
            if len(df_filtrado) >= n_min:
                df = df_filtrado
            # else: fallback silencioso para a base completa (df inalterado)

    df["__apm"] = pd.to_numeric(df["alunos_por_m2"], errors="coerce")
    df = df[np.isfinite(df["__apm"]) & (df["__apm"] > 0)]
    if df.empty:
        return vazio

    tem_metragem = "metragem" in df.columns
    if tem_metragem:
        df["__metr"] = pd.to_numeric(df["metragem"], errors="coerce")

    def _janela(tol: float) -> pd.DataFrame:
        if not tem_metragem:
            return df
        lo = m2 * (1.0 - tol)
        hi = m2 * (1.0 + tol)
        return df[df["__metr"].between(lo, hi)]

    sub = _janela(tolerancia)
    if len(sub) < n_min:
        sub = _janela(tolerancia_alargada)
    if len(sub) < n_min:
        sub = df

    if sub.empty:
        return vazio

    apm_sub = sub["__apm"].to_numpy(dtype=float)
    p10, p50, p90 = (float(v) for v in np.percentile(apm_sub, [10, 50, 90]))
    return {
        "faixa_alunos_p10": float(p10 * m2),
        "faixa_alunos_p50": float(p50 * m2),
        "faixa_alunos_p90": float(p90 * m2),
        "n_comparaveis": int(len(sub)),
    }


def flag_zona_morta(
    catchment_result: dict | None,
    *,
    pop_min: float = POP_ZONA_MORTA_MIN,
    renda_min: float = RENDA_ZONA_MORTA_MIN,
) -> dict:
    """Sinaliza risco de contexto (zona morta) a partir do catchment — NAO preve alunos.

    Le `pop_captacao` e `renda_per_capita_captacao` do dict de catchment.
    Dispara True se pop < pop_min OU renda < renda_min.

    Retorna {"flag_zona_morta": Optional[bool], "motivo_zona_morta": Optional[str]}.
    Se catchment_result is None (sem setores) ou pop/renda forem NaN -> retorna
    {"flag_zona_morta": None, "motivo_zona_morta": "catchment_indisponivel"}.

    GUARDRAIL: esta funcao NAO preve demanda — so compara pop/renda do entorno com
    thresholds exogenos. A flag e de exclusao de contexto, nao estimativa de alunos.
    """
    indisponivel = {"flag_zona_morta": None, "motivo_zona_morta": "catchment_indisponivel"}
    if catchment_result is None:
        return indisponivel

    pop_raw = catchment_result.get("pop_captacao")
    renda_raw = catchment_result.get("renda_per_capita_captacao")
    pop = float(pop_raw) if pop_raw is not None and np.isfinite(pop_raw) else None
    renda = float(renda_raw) if renda_raw is not None and np.isfinite(renda_raw) else None
    if pop is None and renda is None:
        return indisponivel

    motivos: list[str] = []
    if pop is not None and pop < pop_min:
        motivos.append(f"pop<{int(pop_min)}")
    if renda is not None and renda < renda_min:
        motivos.append(f"renda<{int(renda_min)}")

    flag = bool(motivos)
    motivo = "; ".join(motivos) if motivos else "ok"
    return {"flag_zona_morta": flag, "motivo_zona_morta": motivo}


# ---------------------------------------------------------------------------
# Ponte para o nucleo (Premissas + simular) — FIN-VIAB-01
#
# Este modulo NAO tem coeficiente financeiro proprio: tudo vem de `Premissas`
# (defaults do config.py). Aqui so se traduz a assinatura property-first
# (m2/aluguel pedido/demanda) para o contrato do nucleo.
# ---------------------------------------------------------------------------

_CAMPOS_PREMISSAS = frozenset(f.name for f in fields(Premissas))
_CHAVES_PROPRIAS = frozenset({"ticket_cheio", "share_balcao", "aluguel_mes"})


def _premissas_do_ponto(
    ticket_medio: float,
    aluguel_mes: float,
    share_balcao: float,
    premissas: Premissas | None,
    kwargs: dict[str, Any],
) -> Premissas:
    """Monta as `Premissas` do cenario. `premissas` explicito manda em tudo.

    Sem `premissas`, qualquer kwarg cujo nome seja campo de `Premissas`
    (maturacao_meses, carencia_aluguel_meses, folha_pct, ...) e repassado — e o
    que mantem vivas as chamadas historicas do dashboard/backtest/batch.
    """
    if premissas is not None:
        # O aluguel PEDIDO e o do cenario; nunca deixa os dois divergirem.
        return replace(premissas, aluguel_mes=float(aluguel_mes))
    extras = {
        k: v for k, v in kwargs.items() if k in _CAMPOS_PREMISSAS and k not in _CHAVES_PROPRIAS
    }
    return Premissas(
        ticket_cheio=float(ticket_medio),
        share_balcao=float(share_balcao),
        aluguel_mes=float(aluguel_mes),
        **extras,  # type: ignore[arg-type]
    )


def _investimento_do_ponto(
    *,
    obra: float | None,
    parcelas_obra: int | None,
    equipamentos: float | None,
    prazo_equipamentos: int | None,
    juros_equipamentos_am: float | None,
    taxa_franquia: float | None,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Kwargs de investimento de `simular()`, com adaptacao do CAPEX legado.

    Legado (`capex` + `capex_financiado_pct` + `prazo_financiamento_meses` +
    `juros_financiamento_am`): a fracao financiada vira EQUIPAMENTOS e o resto vira
    OBRA (equity). Chamadas novas passam obra/equipamentos diretamente.
    """
    if obra is None and equipamentos is None and kwargs.get("capex") is not None:
        capex = float(kwargs["capex"])
        pct = float(kwargs.get("capex_financiado_pct") or 0.0)
        equipamentos = capex * pct
        obra = capex - equipamentos
    if prazo_equipamentos is None:
        prazo_equipamentos = kwargs.get("prazo_financiamento_meses")  # type: ignore[assignment]
    if juros_equipamentos_am is None:
        juros_equipamentos_am = kwargs.get("juros_financiamento_am")  # type: ignore[assignment]

    equip = float(equipamentos or 0.0)
    return {
        "obra": float(obra or 0.0),
        "parcelas_obra": int(parcelas_obra or SIM_PARCELAS_OBRA_DEFAULT),
        "equipamentos": equip,
        "prazo_equipamentos": int(prazo_equipamentos or 0) if equip > 0 else 0,
        "juros_equipamentos_am": float(juros_equipamentos_am or 0.0),
        "taxa_franquia": float(SIM_TAXA_FRANQUIA if taxa_franquia is None else taxa_franquia),
    }


def grade_sensibilidade(
    m2: float,
    aluguel_ref: float,
    demanda_premissa: float,
    *,
    ticket_medio: float = SIM_MENSALIDADE_BALCAO,
    n_alunos_range: tuple[float, ...] = ALUNOS_RANGE_DEFAULT,
    n_aluguel_range: tuple[float, ...] = ALUGUEL_RANGE_FATOR,
    margem_alvo: float = 0.10,
    share_balcao: float = SHARE_BALCAO_DEFAULT,
    premissas: Premissas | None = None,
    obra: float | None = None,
    parcelas_obra: int | None = None,
    equipamentos: float | None = None,
    prazo_equipamentos: int | None = None,
    juros_equipamentos_am: float | None = None,
    taxa_franquia: float | None = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Varredura cartesiana alunos x aluguel -> `simular()` por par.

    FIN-VIAB-01: cada celula roda o MESMO motor do cenario principal, com as MESMAS
    premissas e o MESMO investimento — so o aluguel e a demanda mudam. Antes a grade
    chamava o adaptador legado (folha absoluta, IR efetivo, sem pre-abertura), entao a
    celula do aluguel pedido nao reproduzia o KPI exibido ao lado dela.

    `n_alunos_range` e uma grade ABSOLUTA de alunos TOTAIS (o mix balcao/agregadores
    escala junto, dentro do nucleo). `n_aluguel_range` sao FATORES sobre `aluguel_ref`.
    `m2`, `demanda_premissa` e `margem_alvo` ficam na assinatura por compatibilidade;
    nao entram na varredura.

    Retorna DataFrame com colunas:
      ['alunos', 'aluguel', 'fator_aluguel', 'margem_liq', 'viavel', 'payback'].
    `margem_liq` e a margem EBITDA do DRE; `payback` pode ser `inf` (nunca se paga) —
    quem serializa para JSON precisa sanear.
    """
    _ = (m2, demanda_premissa, margem_alvo)  # referencia explicita; nao varridos
    p_base = _premissas_do_ponto(ticket_medio, aluguel_ref, share_balcao, premissas, kwargs)
    inv = _investimento_do_ponto(
        obra=obra,
        parcelas_obra=parcelas_obra,
        equipamentos=equipamentos,
        prazo_equipamentos=prazo_equipamentos,
        juros_equipamentos_am=juros_equipamentos_am,
        taxa_franquia=taxa_franquia,
        kwargs=kwargs,
    )

    linhas: list[dict] = []
    for alunos in n_alunos_range:
        for fator in n_aluguel_range:
            aluguel = float(aluguel_ref) * float(fator)
            r = simular(float(alunos), replace(p_base, aluguel_mes=aluguel), **inv)
            linhas.append(
                {
                    "alunos": float(alunos),
                    "aluguel": aluguel,
                    "fator_aluguel": float(fator),
                    "margem_liq": r.margem_ebitda_pct,
                    "viavel": r.flag_viavel,
                    "payback": r.payback_meses,
                }
            )
    return pd.DataFrame(
        linhas,
        columns=["alunos", "aluguel", "fator_aluguel", "margem_liq", "viavel", "payback"],
    )


def analisar_viabilidade_ponto(
    lat: float,
    lng: float,
    m2: float,
    aluguel_pedido: float,
    demanda_premissa: float,
    *,
    ticket_medio: float = SIM_MENSALIDADE_BALCAO,
    margem_alvo: float = 0.10,
    share_balcao: float = SHARE_BALCAO_DEFAULT,
    raio_km: float = RAIO_CATCHMENT_KM,
    base_calibracao_df: pd.DataFrame | None = None,
    setores_df: pd.DataFrame | None = None,
    alunos_range: tuple[float, ...] = ALUNOS_RANGE_DEFAULT,
    aluguel_range_fator: tuple[float, ...] = ALUGUEL_RANGE_FATOR,
    formato: str | None = None,
    premissas: Premissas | None = None,
    obra: float | None = None,
    parcelas_obra: int | None = None,
    equipamentos: float | None = None,
    prazo_equipamentos: int | None = None,
    juros_equipamentos_am: float | None = None,
    taxa_franquia: float | None = None,
    **kwargs: Any,
) -> ViabilidadePontoResult:
    """Orquestrador property-first — roda o nucleo (`Premissas` + `simular`) UMA vez.

    GUARDRAIL: `demanda_premissa` e entrada do operador; NUNCA derivada de lat/lng.
    lat/lng entram SO no catchment (contexto pop/renda) e na flag de zona morta.

    FIN-VIAB-01: `viabilidade` passa a ser o `ViabilidadeResult` de `simular()`, que
    ja traz a serie mensal M-4..M+60 e todos os KPIs (payback, TIR, VPL, retorno,
    break-even, aluguel-teto, acumulado). Backend, tela e PDF apenas LEEM esse objeto.
    `margem_alvo` fica na assinatura por compatibilidade — nao dirige mais nada
    (o aluguel-teto agora e % do faturamento, nao inversao por margem EBITDA).

    Modos degradados:
      - setores_df is None  -> catchment NAO roda; flag_zona_morta=None,
        pop_captacao/renda_per_capita_captacao=None.
      - base_calibracao_df is None -> faixa_alunos_p10/p50/p90=None, n_comparaveis=None,
        aluguel_teto_p10=None.

    formato (opcional, BLK-VIAB-07): quando != None, restringe a curva
    tamanho->densidade aos comparaveis do mesmo formato de operacao (fallback
    gracioso p/ base completa se < n_min).
    """
    # 1. Catchment (contexto) — so roda se setores_df foi injetado.
    catch: dict | None
    pop: float | None
    renda: float | None
    if setores_df is None:
        catch = None
        pop = None
        renda = None
    else:
        catch = calcular_catchment_unidade(lat, lng, setores_df, raio_km=raio_km)
        pop = float(catch["pop_captacao"])
        renda = float(catch["renda_per_capita_captacao"])

    # 2. Flag de zona morta.
    zm = flag_zona_morta(catch, pop_min=POP_ZONA_MORTA_MIN, renda_min=RENDA_ZONA_MORTA_MIN)

    # 2b. Flag de envelope de metragem (BLK-VIAB-06).
    # Sinaliza extrapolação quando m2 cai fora de [ENVELOPE_MIN, ENVELOPE_MAX].
    # Apenas informativa: NÃO recusa o cálculo nem altera DRE/faixa/grade.
    flag_envelope = not (ENVELOPE_MIN <= m2 <= ENVELOPE_MAX)

    # 3. Faixa de alunos por densidade (curva tamanho->densidade; NAO geografica).
    if base_calibracao_df is None:
        faixa: dict = {
            "faixa_alunos_p10": None,
            "faixa_alunos_p50": None,
            "faixa_alunos_p90": None,
            "n_comparaveis": None,
        }
    else:
        faixa = faixa_alunos_por_densidade(m2, base_calibracao_df, formato=formato)

    # 3b. Split da premissa em balcao + agregadores (composicao; estudo §5).
    # A demanda_premissa e SEMPRE alunos TOTAIS; o DRE roda com 2 tickets. Aqui o split
    # e so EXIBICAO/auditabilidade — quem aplica o mix no DRE e o proprio nucleo.
    alunos_balcao = float(demanda_premissa) * share_balcao
    alunos_agregadores = float(demanda_premissa) * (1.0 - share_balcao)

    # 4. Viabilidade no cenario pedido (demanda = premissa explicita). UMA chamada ao
    # nucleo; tudo o que vem depois e LEITURA do resultado.
    p = _premissas_do_ponto(ticket_medio, aluguel_pedido, share_balcao, premissas, kwargs)
    inv = _investimento_do_ponto(
        obra=obra,
        parcelas_obra=parcelas_obra,
        equipamentos=equipamentos,
        prazo_equipamentos=prazo_equipamentos,
        juros_equipamentos_am=juros_equipamentos_am,
        taxa_franquia=taxa_franquia,
        kwargs=kwargs,
    )
    viab = simular(float(demanda_premissa), p, **inv)

    # 5. Aluguel-teto (% do faturamento bruto steady) e break-even (alunos TOTAIS):
    # ambos ja vem calculados pelo nucleo, do MESMO cenario.
    teto_faixas = dict(viab.aluguel_teto)
    teto_canonico = float(teto_faixas.get("canonico", 0.0))

    # 5b. Teto sobre o p10 da faixa de alunos (informativo). O teto sobre a demanda
    # ASSUMIDA e circular — ele so devolve a premissa que o operador digitou; o teto
    # sobre o p10 responde "e se a unidade ocupar como a pior comparavel do porte?".
    # `p.faturamento(alunos)` e a MESMA funcao que gera o faturamento steady da serie.
    # `com_anuidade=True` NAO e opcional: o teto canonico acima vem do faturamento de
    # steady-state, que e do mes de REGIME PLENO (anuidade ja em cobranca). Como
    # `Premissas.faturamento()` tem `com_anuidade=False` por default, omitir o
    # argumento colocaria dois aluguel-teto de REGUAS DIFERENTES lado a lado na mesma
    # tela (divergencia medida no golden: R$966,36/mes, 2,2%) — exatamente a classe de
    # defeito que o FIN-VIAB-01 existe para eliminar.
    p10 = faixa["faixa_alunos_p10"]
    teto_p10 = (
        float(aluguel_teto_clusters(p.faturamento(float(p10), com_anuidade=True))["canonico"])
        if p10 is not None
        else None
    )

    # 6. Grade de sensibilidade (mesmas premissas, mesmo investimento).
    grade = grade_sensibilidade(
        m2,
        aluguel_pedido,
        demanda_premissa,
        n_alunos_range=alunos_range,
        n_aluguel_range=aluguel_range_fator,
        premissas=p,
        **inv,
    )

    # 7. Montar resultado.
    return ViabilidadePontoResult(
        lat=float(lat),
        lng=float(lng),
        m2=float(m2),
        aluguel_pedido=float(aluguel_pedido),
        demanda_premissa=float(demanda_premissa),
        faixa_alunos_p10=faixa["faixa_alunos_p10"],
        faixa_alunos_p50=faixa["faixa_alunos_p50"],
        faixa_alunos_p90=faixa["faixa_alunos_p90"],
        n_comparaveis=faixa["n_comparaveis"],
        flag_zona_morta=zm["flag_zona_morta"],
        motivo_zona_morta=zm["motivo_zona_morta"],
        pop_captacao=None if catch is None else pop,
        renda_per_capita_captacao=None if catch is None else renda,
        viabilidade=viab,
        aluguel_teto_calculado=teto_canonico,
        alunos_breakeven=float(viab.alunos_break_even_total),
        grade_sensibilidade=grade,
        alunos_balcao_premissa=float(alunos_balcao),
        alunos_agregadores_premissa=float(alunos_agregadores),
        demanda_fonte=DEMANDA_FONTE_PREMISSA,
        flag_fora_envelope=flag_envelope,
        aluguel_teto_faixas=teto_faixas,
        aluguel_teto_p10=teto_p10,
        alunos_breakeven_caixa=float(viab.alunos_break_even_caixa_total),
        alunos_para_margem_alvo=float(alunos_para_margem(p, margem_alvo)),
    )


__all__ = [
    "ViabilidadePontoResult",
    "analisar_viabilidade_ponto",
    "faixa_alunos_por_densidade",
    "flag_zona_morta",
    "grade_sensibilidade",
    "POP_ZONA_MORTA_MIN",
    "RENDA_ZONA_MORTA_MIN",
    "FAIXA_M2_TOLERANCIA",
    "FAIXA_M2_TOLERANCIA_ALARGADA",
    "N_MIN_COMPARAVEIS",
    "ALUNOS_RANGE_DEFAULT",
    "ALUGUEL_RANGE_FATOR",
    "DEMANDA_FONTE_PREMISSA",
    "FORMATO_POR_MARCA",
    "FORMATO_LOW_COST_MASSA",
    "FORMATO_BOUTIQUE_PREMIUM",
    "SHARE_BALCAO_DEFAULT",
    "ENVELOPE_MIN",
    "ENVELOPE_MAX",
    "Premissas",
]
