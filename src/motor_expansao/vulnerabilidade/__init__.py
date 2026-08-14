"""Camada paralela de Vulnerabilidade para M&A (snapshots semanais + churn/staleness).

Pacote DISJUNTO (BLK-MA-02 / DEC-012): nunca importa **diretamente** de `pipelines/m1/`,
`censo_*`, `dashboard/`, `api` nem `config.py` raiz; é **READ-ONLY sobre o M1**.
`pipelines/normalizar_concorrentes.py` e `pipelines/calcular_colunas_mercado.py` são
`_DENY_CRITICO` do `loop_guard`: molde de leitura apenas — a fórmula do `concorrente_id` está
REPLICADA em `contrato.py`, nunca importada.

**Isolamento TRANSITIVO, fechado no BLK-MA-02-FU1 item 2 (2026-08-10).** A frase acima vale para
imports DIRETOS, que é o que o `test_isolamento_imports` prova por AST. A garantia transitiva é
outra, e por um tempo não existia: `import motor_expansao.vulnerabilidade` carregava `sklearn`,
`scipy`, `shapely`, `requests`, `pyproj` e 5 módulos de `dashboard/`, em ~18 s. Causa:
`snapshots.py` importa `classificar_rede` de `demanda_revelada.classificacao_rede_menor` — módulo
que só precisa de `re`/`unicodedata`/`pathlib` —, mas o `__init__.py` daquele pacote reexportava
seus 9 submódulos de forma **eager**, e importar qualquer coisa do pacote executa o `__init__` do
pai primeiro. Nunca foi regressão de READ-ONLY (nada do M1, `config.py` ou
`normalizar_concorrentes` entrava); era **bloqueante para o BLK-MA-06**, porque este é o módulo que
a D6 ratificou plugar no `run_weekly_90.sh` e sem `sklearn`/`scipy` no host do coletor o passo do
cron quebraria já no import.

Correção: o `__init__` de `demanda_revelada` passou a reexportar por `__getattr__` (PEP 562), sem
mudar o contrato público. Resultado medido: **~3 s, zero deps pesadas, zero `dashboard/`**. Travado
por `test_pacote_nao_carrega_dependencia_pesada`, que mede por `sys.modules` num subprocesso e
**assere a procedência** do que mediu — sem isso ele resolveria o pacote pela instalação editável
em vez deste checkout, que foi como o defeito se escondeu durante o desenvolvimento.

Fronteira dos módulos: `snapshots.py` transforma o CSV cru de UMA execução em UMA partição
`semana=AAAA-SS`; `churn_staleness.py` lê a série dessas partições e devolve o estado de churn
(sinais 3 e 4); `presenca_agregador.py` lê a mesma série e devolve, por `hex_id_res7`, o insumo
bruto do sinal 1 (presença em TotalPass/WellHub). Os extratores **param** no insumo; `score.py`
(BLK-MA-04) compõe `v1`/`v3`/`v4` e o `score_vulnerabilidade` a partir deles, sem I/O, e é onde o
universo de M&A é fechado. `alvos_ma.py` (BLK-MA-05) fecha a cadeia: cruza esse score com o
hexágono quente da carteira (join READ-ONLY, `many_to_one`) e materializa os artefatos do D6 —
a camada scored por academia, a lista curada por (hex, regime) e, desde o BLK-MA-13/DEC-028, a
mesma lista COLAPSADA para uma linha por hex, que é o grão que o overlay do piloto web consegue
pintar. É o único módulo do pacote que escreve fora de `data/staging/snapshots_concorrentes/`, e o
único cuja saída sai do repositório.

`pressao_competitiva.py` (BLK-MA-12) é ortogonal aos três acima: não lê a série de snapshots, e sim
o parquet de PONTOS de concorrentes, devolvendo por hex a concorrência efetiva ponderada por
distância — o insumo do `s6`, que a DEC-027 tornou componente do score **condicionado à presença
desse insumo na chamada**.

Contrato canônico do epic: `docs/vulnerabilidade_ma_contrato.md`.
"""

from __future__ import annotations

from .alvos_ma import (
    ALVOS_HEX_PATH_DEFAULT,
    academias_com_hotness,
    agregar_alvos_por_hex,
    colapsar_regimes_por_hex,
    marcar_hex_quente,
    materializar_alvos_ma,
)
from .churn_staleness import extrair_churn_staleness
from .contrato import (
    ADJACENCIA_HEX_QUENTE_K,
    CATEGORIA_INDEPENDENTE,
    COLUNAS_PII_PROIBIDAS,
    CONTRATO_COLUNAS_ACADEMIAS_MA,
    CONTRATO_COLUNAS_ALVOS_MA,
    CONTRATO_COLUNAS_CHURN,
    CONTRATO_COLUNAS_PRESENCA_AGREGADOR,
    CONTRATO_COLUNAS_PRESSAO,
    CONTRATO_COLUNAS_SCORE,
    CONTRATO_COLUNAS_SNAPSHOT,
    FONTES_AGREGADORES,
    KERNEIS_PRESSAO,
    LIMIAR_RESIDUAL_SATURADO,
    MIN_SEMANAS,
    PESOS_ALVO_SINAIS,
    PRESSAO_KERNEL_DEFAULT,
    PRESSAO_RAIO_M,
    QUANTIL_SAM_QUENTE,
    RETENCAO_SEMANAS,
    SINAIS_INATIVOS,
    SINAIS_ORDEM,
    STALE_SEMANAS,
    V3_POR_STATUS_CHURN,
    VERSAO_CONTRATO_ALVOS_MA,
    VERSAO_CONTRATO_CHURN,
    VERSAO_CONTRATO_PRESENCA_AGREGADOR,
    VERSAO_CONTRATO_PRESSAO,
    VERSAO_CONTRATO_SCORE,
    VERSAO_CONTRATO_SNAPSHOT,
    renormalizar_pesos,
)
from .presenca_agregador import extrair_presenca_agregador
from .pressao_competitiva import (
    calcular_pressao_por_hex,
    ler_concorrentes,
    peso_por_distancia,
)
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
    # Sinal 6 - pressao competitiva com decaimento (fato sem peso)
    "calcular_pressao_por_hex",
    "peso_por_distancia",
    "ler_concorrentes",
    "CONTRATO_COLUNAS_PRESSAO",
    "VERSAO_CONTRATO_PRESSAO",
    "PRESSAO_RAIO_M",
    "PRESSAO_KERNEL_DEFAULT",
    "KERNEIS_PRESSAO",
    # Lista priorizada de M&A (D5/D6)
    "marcar_hex_quente",
    "academias_com_hotness",
    "agregar_alvos_por_hex",
    "colapsar_regimes_por_hex",
    "materializar_alvos_ma",
    "ALVOS_HEX_PATH_DEFAULT",
    "CONTRATO_COLUNAS_ACADEMIAS_MA",
    "CONTRATO_COLUNAS_ALVOS_MA",
    "VERSAO_CONTRATO_ALVOS_MA",
    "QUANTIL_SAM_QUENTE",
    "LIMIAR_RESIDUAL_SATURADO",
    "ADJACENCIA_HEX_QUENTE_K",
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
