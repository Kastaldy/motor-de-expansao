"""Camada paralela de Vulnerabilidade para M&A (snapshots semanais + churn/staleness).

Pacote DISJUNTO (BLK-MA-02 / DEC-012): NUNCA importa de `pipelines/m1/`, `censo_*`, `dashboard/`,
`api` nem `config.py` raiz; é **READ-ONLY sobre o M1** e usa só deps da base
(pandas/pyarrow/h3 + stdlib). `pipelines/normalizar_concorrentes.py` e
`pipelines/calcular_colunas_mercado.py` são `_DENY_CRITICO` do `loop_guard`: molde de leitura
apenas — a fórmula do `concorrente_id` está REPLICADA em `contrato.py`, nunca importada.

Fronteira dos dois módulos: `snapshots.py` transforma o CSV cru de UMA execução em UMA partição
`semana=AAAA-SS`; `churn_staleness.py` lê a série dessas partições e devolve o estado de churn.
O extrator **para** no `status_churn`/`semanas_sem_mudanca` — `score_vulnerabilidade`, `v3`/`v4`,
normalização e pesos são do BLK-MA-04.

Contrato canônico do epic: `docs/vulnerabilidade_ma_contrato.md`.
"""

from __future__ import annotations

from .churn_staleness import extrair_churn_staleness
from .contrato import (
    COLUNAS_PII_PROIBIDAS,
    CONTRATO_COLUNAS_CHURN,
    CONTRATO_COLUNAS_SNAPSHOT,
    MIN_SEMANAS,
    RETENCAO_SEMANAS,
    STALE_SEMANAS,
    VERSAO_CONTRATO_CHURN,
    VERSAO_CONTRATO_SNAPSHOT,
)
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
