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


def payload_carteira_sintetico() -> dict[str, object]:
    """Payload da carteira no formato que `rede_export` consome, sem tocar disco.

    Exercita TODOS os textos do gerador: notas, reguas, semaforo, SSS, split e uma linha
    de unidade com alerta.
    """
    return {
        "mes": "2026-07",
        "referencia": "31/07/2026",
        "referencia_m1": "30/06/2026",
        "mes_completo": True,
        "competencia_diagnostico": "2026-07",
        "totais": {"rede": 2, "no_recorte": 2, "com_coordenada": 2},
        "kpis": {
            chave: {"atual": valor, "m1": valor, "delta_pct": 0.0}
            for chave, valor in (
                ("faturamento", 400_000.0),
                ("ativos", 2_400.0),
                ("churn_pct", 5.4),
                ("receita_por_recorrente", 152.3),
                ("nps", 61.0),
            )
        },
        "split": {
            "recorrentes": 1_800.0,
            "agregadores": 600.0,
            "pct_recorrentes": 75.0,
            "pct_agregadores": 25.0,
        },
        "semaforo": {"alta": 1, "media": 0, "ok": 1, "sem_base": 0},
        "sss": {
            "disponivel": True,
            "competencia_base": "2025-07",
            "unidades": 2,
            "metricas": {"faturamento": {"atual": 400_000.0, "ano_anterior": 360_000.0, "var_pct": 11.1}},
        },
        "serie_meses": ["2026-05", "2026-06", "2026-07"],
        "serie_rede": [380_000.0, 390_000.0, 400_000.0],
        "reguas": _REGUAS_VIGENTES(),
        "meta_nps": 60.0,
        "unidades": [
            {
                "id": "botafogo-rj",
                "nome": "BOTAFOGO",
                "uf": "RJ",
                "cidade": "Rio de Janeiro",
                "consultor": "MARISE",
                "master_franquia": "Franqueadora",
                "master": "RJ/SP 01",
                "coorte_rotulo": "2 a 4 anos",
                "meses_operacao": 40,
                "severidade": "alta",
                "severidade_rotulo": "Prioridade alta",
                "resumo": "Churn de 9,2% no mês, acima da régua de 8,0%.",
                "faixa_faturamento_rotulo": "Excelente+",
                "alertas": [{"codigo": "churn", "titulo": "Churn alto", "nivel": "grave"}],
                "metricas": {
                    "faturamento": {"atual": 250_000.0, "m1": 240_000.0, "rank": 1, "rank_total": 2, "vs_media_pct": 12.5},
                    "ativos": {"atual": 1_400.0, "m1": 1_380.0, "rank": 1, "rank_total": 2, "vs_media_pct": 8.0},
                    "churn_pct": {"atual": 9.2, "m1": 7.0, "rank": 2, "rank_total": 2, "vs_media_pct": 30.0},
                    "nps": {"atual": 55.0, "m1": 58.0, "rank": 2, "rank_total": 2, "vs_media_pct": -9.0},
                },
                "sparkline": [240_000.0, 245_000.0, 250_000.0],
            },
        ],
        "notas": ["Receita por recorrente não é o TICKET_MEDIO do PowerBI."],
    }


def payload_ficha_sintetico() -> dict[str, object]:
    """Payload da ficha no formato que `rede_export.ficha_pdf` consome."""
    return {
        "unidade": {
            "id": "botafogo-rj",
            "nome": "BOTAFOGO",
            "uf": "RJ",
            "cidade": "Rio de Janeiro",
            "consultor": "MARISE",
            "master_franquia": "Franqueadora",
            "coorte_rotulo": "2 a 4 anos",
            "inauguracao": "01/01/2021",
        },
        "mes": "2026-07",
        "meta_nps": 60.0,
        "metricas": {
            "faturamento": {"atual": 250_000.0, "m1": 240_000.0, "rank": 1, "rank_total": 2, "vs_media_pct": 12.5},
            "receita_por_recorrente": {"atual": 152.3, "m1": 150.0, "rank": 1, "rank_total": 2, "vs_media_pct": 3.0},
            "churn_pct": {"atual": 9.2, "m1": 7.0, "rank": 2, "rank_total": 2, "vs_media_pct": 30.0},
            "nps": {"atual": 55.0, "m1": 58.0, "rank": 2, "rank_total": 2, "vs_media_pct": -9.0},
        },
        "serie": {
            "meses": ["2026-05", "2026-06", "2026-07"],
            "faturamento": [240_000.0, 245_000.0, 250_000.0],
            "ativos": [1_380.0, 1_390.0, 1_400.0],
            "churn_pct": [6.1, 7.0, 9.2],
        },
        "funil": {
            "visitas": 200.0,
            "convertidos": 90.0,
            "vendas": 95.0,
            "novos_alunos": 88.0,
            "conversao_pct": 45.0,
            "aviso": None,
        },
        "coorte": {
            "chave": "24_47",
            "rotulo": "2 a 4 anos",
            "degradacao": "coorte",
            "base_rotulo": "pares da mesma maturidade",
            "n": 12,
            "metricas": {
                "faturamento": {"unidade": 250_000.0, "p25": 180_000.0, "p50": 220_000.0, "p75": 280_000.0, "percentil": 62.0},
                "receita_por_recorrente": {"unidade": 152.3, "p25": 130.0, "p50": 150.0, "p75": 170.0, "percentil": 55.0},
                "churn_pct": {"unidade": 9.2, "p25": 4.0, "p50": 5.5, "p75": 7.0, "percentil": 92.0},
            },
        },
        "diagnostico": {
            "competencia": "2026-07",
            "severidade": "alta",
            "severidade_rotulo": "Prioridade alta",
            "resumo": "Churn de 9,2% no mês, acima da régua de 8,0%.",
            "alertas": [{"codigo": "churn", "titulo": "Churn alto", "nivel": "grave"}],
            "recomendacoes": [
                {
                    "codigo": "churn",
                    "titulo": "Atacar a retenção",
                    "corpo": "Separar motivo de saída de motivo de cobrança.",
                }
            ],
        },
        "reguas": _REGUAS_VIGENTES(),
        "notas": ["Diagnóstico calculado sobre 2026-07."],
    }


def _REGUAS_VIGENTES() -> dict[str, dict[str, object]]:
    from motor_expansao.dashboard.rede_diagnostico import REGUAS_VIGENTES

    return dict(REGUAS_VIGENTES)
