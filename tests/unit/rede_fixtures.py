"""Construtores de base SINTETICA no formato da Growth API (nao e' arquivo de teste).

Sem `test_` no nome de proposito: `python_files = ["test_*.py"]` no pyproject nao coleta
este modulo, que so existe para ser importado pelos testes de `rede_*`.

A base real e' DIARIA e mistura cumulativas (que resetam no dia 1) com snapshots. Os
construtores daqui reproduzem essa forma: `mes()` recebe o valor de FECHAMENTO das
cumulativas e distribui pelos dias, e o valor dos snapshots como constante do mes.
"""

from __future__ import annotations

import calendar

import pandas as pd

from motor_expansao.dashboard.rede_metricas import COLUNAS_CUMULATIVAS, COLUNAS_SNAPSHOT

COLUNAS_NUMERICAS: tuple[str, ...] = tuple(COLUNAS_CUMULATIVAS) + tuple(COLUNAS_SNAPSHOT)


def mes(
    unidade: str,
    ano: int,
    numero_mes: int,
    *,
    uf: str = "SP",
    master: str = "ULTRA",
    inauguracao: str = "01/01/2020",
    dias: int | None = None,
    cumulativas: dict[str, float] | None = None,
    snapshots: dict[str, float] | None = None,
    trajetoria: dict[str, list[float]] | None = None,
) -> list[dict[str, object]]:
    """Linhas diarias de um unidade-mes.

    `cumulativas` sao valores de FECHAMENTO, distribuidos linearmente pelos dias (dia 1 =
    1/N do total, ultimo dia = total). `snapshots` valem igual em todos os dias.
    `trajetoria` sobrepoe uma serie explicita dia a dia numa coluna (usada para provar que
    o fechamento pega o ULTIMO valor, e nao o maximo).
    """
    total_dias = dias if dias is not None else calendar.monthrange(ano, numero_mes)[1]
    cumulativas = cumulativas or {}
    snapshots = snapshots or {}
    trajetoria = trajetoria or {}

    linhas: list[dict[str, object]] = []
    for dia in range(1, total_dias + 1):
        linha: dict[str, object] = {c: 0 for c in COLUNAS_NUMERICAS}
        linha.update(
            unidade=unidade,
            uf=uf,
            master=master,
            inauguracao=inauguracao,
            data=f"{dia:02d}/{numero_mes:02d}/{ano}",
        )
        for coluna, total in cumulativas.items():
            linha[coluna] = round(total * dia / total_dias, 4)
        for coluna, valor in snapshots.items():
            linha[coluna] = valor
        for coluna, serie in trajetoria.items():
            linha[coluna] = serie[min(dia - 1, len(serie) - 1)]
        linhas.append(linha)
    return linhas


def base(*grupos: list[dict[str, object]]) -> pd.DataFrame:
    """Junta grupos de linhas num DataFrame no formato cru da Growth."""
    linhas = [linha for grupo in grupos for linha in grupo]
    return pd.DataFrame(linhas)


# Quantis (0 / p10 / p25 / p50 / p75 / p90 / 1) medidos nas 86 unidades comparaveis de
# jul/2026 na base de PRODUCAO, em 2026-08-04. Sao numeros agregados e anonimos: servem
# para gerar uma rede sintetica com a MESMA forma da real, sem trazer nenhuma unidade
# nomeada para dentro do repositorio.
QUANTIS_PRODUCAO: dict[str, list[float]] = {
    "churn_pct": [1.1, 2.9, 4.6, 5.6, 7.2, 8.8, 22.8],
    "conversao_pct": [30.4, 36.4, 45.8, 51.8, 59.5, 70.2, 87.6],
    "nps": [-16.7, 27.1, 47.6, 68.4, 82.6, 89.2, 100.0],
    "pct_agregador_alunos": [0.0, 0.0, 20.4, 39.2, 54.2, 66.2, 91.0],
    "saldo_operacional": [-301.0, -14.0, -1.0, 22.5, 50.2, 143.5, 549.0],
    "faturamento": [26_697.0, 85_740.0, 124_668.0, 188_251.0, 291_327.0, 359_488.0, 699_985.0],
}
_PROBABILIDADES = [0.0, 0.10, 0.25, 0.50, 0.75, 0.90, 1.0]

# Metricas em que valor ALTO e' o lado ruim (as demais sao ruins quando caem).
_RUIM_QUANDO_ALTO = frozenset({"churn_pct", "pct_agregador_alunos"})

# Correlacao entre as metricas de uma mesma unidade. Sortear cada metrica de forma
# INDEPENDENTE nao reproduz a rede real: la, quem vai mal costuma ir mal em varias coisas
# ao mesmo tempo, o que CONCENTRA os alertas em menos unidades. Com metricas independentes
# a fatia `alta` sintetica da 44%, contra 24% medidos na producao; com 0,8 da 26%, que e' a
# forma certa. Calibrado em 2026-08-04 varrendo rho de 0,0 a 0,9.
_CORRELACAO_ENTRE_METRICAS = 0.8


def fechamento_sintetico(
    unidades: int = 90, competencias: tuple[str, ...] = ("2026-04", "2026-05", "2026-06", "2026-07")
) -> pd.DataFrame:
    """Rede sintetica com a mesma distribuicao marginal E a mesma concentracao da producao.

    Copula gaussiana de um fator: um "nivel de saude" latente por unidade puxa todas as
    metricas juntas (`rho = 0,8`), preservando os quantis medidos de cada uma. Semente
    fixa: deterministico, o teste nao pisca.
    """
    import math

    import numpy as np

    rng = np.random.default_rng(20260804)
    rho = _CORRELACAO_ENTRE_METRICAS
    saude = rng.standard_normal(unidades)
    normal_acumulada = np.vectorize(lambda z: 0.5 * (1.0 + math.erf(z / math.sqrt(2.0))))

    percentis: dict[str, object] = {}
    for metrica in QUANTIS_PRODUCAO:
        if metrica == "faturamento":
            # Porte e' independente da saude: uma flagship pode ir mal e uma unidade
            # pequena pode ir bem. Amarrar os dois inventaria uma correlacao que a base
            # nao mostra -- e o porte so entra na PRIORIDADE, nunca na severidade.
            percentis[metrica] = rng.random(unidades)
            continue
        z = rho * saude + math.sqrt(1 - rho**2) * rng.standard_normal(unidades)
        acumulada = normal_acumulada(z)
        percentis[metrica] = acumulada if metrica in _RUIM_QUANDO_ALTO else 1.0 - acumulada

    valores = {
        metrica: np.interp(percentis[metrica], _PROBABILIDADES, quantis)
        for metrica, quantis in QUANTIS_PRODUCAO.items()
    }
    # Tendencia do faturamento ao longo dos meses (-25% a +25% no total da janela): e' o
    # que faz o alerta de queda ter o que observar.
    tendencias = rng.uniform(-0.25, 0.25, unidades) / max(len(competencias) - 1, 1)

    linhas: list[dict[str, object]] = []
    for i in range(unidades):
        perfil = {metrica: float(serie[i]) for metrica, serie in valores.items()}
        tendencia = float(tendencias[i])
        for ordem, competencia in enumerate(competencias):
            linhas.append(
                {
                    "unidade_id": f"u{i:03d}",
                    "unidade_cru": f"UNIDADE {i:03d}",
                    "competencia": competencia,
                    "uf": "SP",
                    "master": "ULTRA",
                    "mes_completo": True,
                    "operacao_mes_cheio": True,
                    "meses_operacao": 30.0,
                    "faturamento": perfil["faturamento"] * (1 + tendencia * ordem),
                    "churn_pct": perfil["churn_pct"],
                    "conversao_pct": perfil["conversao_pct"],
                    "nps": perfil["nps"],
                    "pct_agregador_alunos": perfil["pct_agregador_alunos"],
                    "saldo_operacional": perfil["saldo_operacional"],
                    "inadimplente": 9_999.0,
                    "treino_ativo": 999.0,
                }
            )
    return pd.DataFrame(linhas)


def unidade_saudavel(
    nome: str, ano: int, numero_mes: int, **kwargs: object
) -> list[dict[str, object]]:
    """Unidade sem nenhum alerta nas reguas vigentes (o 'controle' dos testes)."""
    padrao: dict[str, object] = dict(
        cumulativas={
            "faturamento": 200_000.0,
            "faturamento_sem_agregador": 180_000.0,
            "cancelados": 30.0,
            "visitas": 200.0,
            "convertidos": 120.0,  # 60% de conversao
            "novos_alunos": 100.0,
            "vendas": 120.0,  # saldo +90
        },
        snapshots={
            "pagantes": 1_200.0,
            "ativos_total": 1_400.0,
            "alunos_gympass": 100.0,
            "alunos_totalpass": 100.0,
            "NPS": 75.0,
            "em_cobranca": 80.0,
            "inadimplente": 60.0,
            "treino_ativo": 55.0,
        },
    )
    padrao.update(kwargs)
    return mes(nome, ano, numero_mes, **padrao)  # type: ignore[arg-type]
