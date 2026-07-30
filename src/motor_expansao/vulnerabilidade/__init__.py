"""Camada paralela de Vulnerabilidade para M&A (snapshots semanais + churn/staleness).

Pacote DISJUNTO (BLK-MA-02 / DEC-012): NUNCA importa de `pipelines/m1/`, `censo_*`, `dashboard/`,
`api` nem `config.py` raiz; é **READ-ONLY sobre o M1** e usa só deps da base
(pandas/pyarrow/h3 + stdlib). `pipelines/normalizar_concorrentes.py` e
`pipelines/calcular_colunas_mercado.py` são `_DENY_CRITICO` do `loop_guard`: molde de leitura
apenas — a fórmula do `concorrente_id` está REPLICADA em `contrato.py`, nunca importada.

Fronteira dos módulos: `snapshots.py` transforma o CSV cru de UMA execução em UMA partição
`semana=AAAA-SS`; `churn_staleness.py` lê a série dessas partições e devolve o estado de churn
(sinais 3 e 4); `presenca_agregador.py` lê a mesma série e devolve, por `hex_id_res7`, o insumo
bruto do sinal 1 (presença em TotalPass/WellHub). Os extratores **param** no insumo; `score.py`
(BLK-MA-04) compõe `v1`/`v3`/`v4` e o `score_vulnerabilidade` a partir deles, sem I/O, e é onde o
universo de M&A é fechado. Materializar artefato e cruzar com hexágono quente são do BLK-MA-05.

Contrato canônico do epic: `docs/vulnerabilidade_ma_contrato.md`.
"""

from __future__ import annotations

from .churn_staleness import extrair_churn_staleness
from .contrato import (
    CATEGORIA_INDEPENDENTE,
    COLUNAS_PII_PROIBIDAS,
    CONTRATO_COLUNAS_CHURN,
    CONTRATO_COLUNAS_PRESENCA_AGREGADOR,
    CONTRATO_COLUNAS_SCORE,
    CONTRATO_COLUNAS_SNAPSHOT,
    FONTES_AGREGADORES,
    MIN_SEMANAS,
    PESOS_ALVO_SINAIS,
    RETENCAO_SEMANAS,
    SINAIS_INATIVOS,
    SINAIS_ORDEM,
    STALE_SEMANAS,
    V3_POR_STATUS_CHURN,
    VERSAO_CONTRATO_CHURN,
    VERSAO_CONTRATO_PRESENCA_AGREGADOR,
    VERSAO_CONTRATO_SCORE,
    VERSAO_CONTRATO_SNAPSHOT,
    renormalizar_pesos,
)
from .presenca_agregador import extrair_presenca_agregador
from .score import calcular_score_vulnerabilidade
from .snapshots import (
    SNAPSHOTS_DIR_DEFAULT,
    avaliar_estabilidade_slug,
    calcular_hash_campos_raspados,
    derivar_chave,
    escrever_particao_semana,
    ler_feeds,
    ler_snapshots,
    limpar_ruido,
    materializar,
    montar_snapshot,
    podar_snapshots,
)

__all__ = [
    # Materializador (CSV cru -> particao semanal)
    "materializar",
    "ler_feeds",
    "limpar_ruido",
    "calcular_hash_campos_raspados",
    "derivar_chave",
    "montar_snapshot",
    "avaliar_estabilidade_slug",
    "escrever_particao_semana",
    "ler_snapshots",
    "podar_snapshots",
    "SNAPSHOTS_DIR_DEFAULT",
    # Extrator (serie -> churn/staleness)
    "extrair_churn_staleness",
    # Sinal 1 (presenca em agregador, hex-level)
    "extrair_presenca_agregador",
    "CONTRATO_COLUNAS_PRESENCA_AGREGADOR",
    "VERSAO_CONTRATO_PRESENCA_AGREGADOR",
    "FONTES_AGREGADORES",
    "CATEGORIA_INDEPENDENTE",
    # Score de vulnerabilidade (D4)
    "calcular_score_vulnerabilidade",
    "CONTRATO_COLUNAS_SCORE",
    "VERSAO_CONTRATO_SCORE",
    "PESOS_ALVO_SINAIS",
    "SINAIS_ORDEM",
    "SINAIS_INATIVOS",
    "V3_POR_STATUS_CHURN",
    "renormalizar_pesos",
    # Contrato
    "CONTRATO_COLUNAS_SNAPSHOT",
    "CONTRATO_COLUNAS_CHURN",
    "COLUNAS_PII_PROIBIDAS",
    "VERSAO_CONTRATO_SNAPSHOT",
    "VERSAO_CONTRATO_CHURN",
    "MIN_SEMANAS",
    "STALE_SEMANAS",
    "RETENCAO_SEMANAS",
]
