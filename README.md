# Motor de Expansao Ultra Academia

Base territorial do MVP nacional do `motor-de-expansao`.

O contrato canonico do projeto esta em `CLAUDE.md`. Para a Fase 1 / M1, o pipeline nacional oficial usa:

- base estrutural oficial: `hex_score_estrutural`
- score oficial de priorizacao executiva: `score_priorizacao`
- replica executiva estavel: `score_oficial = score_priorizacao`
- staging sempre em Parquet
- IBGE como fonte oficial
- OSM como opcional/futuro, fora do fechamento executivo nacional

## Escopo atual do M1

Fluxo oficial:

1. `base_h3_brasil.py`
   Gera a base H3 nacional particionada por UF em `data/staging/brasil/uf=XX/hexagonos.parquet`.
2. `hex_enrichment.py`
   Enriquece a base estrutural nacional, calcula score estrutural, ajuste executivo, score de priorizacao, corte top 20% por UF e camada de oportunidade.
3. `fase1_bi_exports.py`
   Gera os artefatos executivos/BI estaveis a partir de `data/staging/hexagonos_brasil_oportunidades.parquet`.

## Regra canonica de score do M1

Inputs estruturais:

- `renda_per_capita`
- `populacao_proxy`
- `pop_18_45` como fonte preferida da proxy populacional
- `pop_total` como fallback

Calculo oficial:

```python
renda_pct_nacional = percentil_nacional(renda_per_capita)
pop_pct_nacional = percentil_nacional(populacao_proxy)

hex_score_estrutural = 100 * (
    0.60 * renda_pct_nacional +
    0.40 * pop_pct_nacional
)

ajuste_executivo = bonus_penalidade_por_quartil(
    renda_pct_nacional,
    pop_pct_nacional,
)

score_priorizacao = clip(hex_score_estrutural + ajuste_executivo, 0, 100)
```

Campos oficiais esperados:

- `renda_pct_nacional`
- `pop_pct_nacional`
- `hex_score_estrutural`
- `ajuste_executivo`
- `score_priorizacao`
- `score_oficial`
- `score_oficial_nome`
- `score_percentil_nacional`

## Artefatos oficiais da Fase 1

- `data/staging/brasil_estrutural.parquet`
- `data/staging/brasil_priorizados.parquet`
- `data/staging/hexagonos_brasil_oportunidades.parquet`
- `data/outputs/hexagonos_brasil_dashboard.parquet`
- `data/outputs/top_oportunidades_resumo.csv`
- `data/outputs/resumo_por_uf.csv`
- `data/reports/camada_oportunidade_fase1.md`
- `data/reports/resumo_executivo_fase1.md`

## Contrato oficial dos outputs do M1

O contrato curto e estavel dos outputs oficiais do M1 esta em `docs/m1_outputs_oficiais.md`.

Resumo pratico:

- `brasil_estrutural.parquet`: base estrutural auditavel com IBGE e `hex_score_estrutural`
- `brasil_priorizados.parquet`: recorte oficial top 20% por UF para priorizacao executiva
- `hexagonos_brasil_oportunidades.parquet`: camada canonica com ranking Brasil, UF e cidade
- `hexagonos_brasil_dashboard.parquet`: dataset oficial exportado para BI

Colunas oficiais exportadas para BI:

- `hex_id`, `lat`, `lng`, `uf`, `cidade`, `regiao`
- `hex_score_estrutural`, `ajuste_executivo`, `score_priorizacao`
- `score_oficial`, `score_oficial_nome`, `score_percentil_nacional`
- `faixa_oportunidade`, `flag_viavel`, `flag_prioridade`
- `rank_brasil`, `rank_uf`, `rank_cidade`
- `criterio_prioridade`, `threshold_prioridade_uf`, `osm_status`
- `fonte_demografica`, `fonte_renda`, `fonte_populacao`, `nivel_geografico_ibge`
- `fallback_setor_censitario`, `motivo_fallback_setor`
- `fonte_geometria_ibge`, `metodo_atribuicao_municipio`, `data_referencia_ibge`

## Parametros canonicos do M1

- `H3_RESOLUTION=7`
- `DIST_MIN_ULTRA_KM=1.0`
- `RENDA_MIN=4500`
- `M1_SCORE_OFICIAL=score_priorizacao`
- `M1_PRIORIZACAO_TOP_PCT_POR_UF=0.20`
- `M1_OSM_ENABLED=false`
- `M1_SETOR_CENSITARIO_OBRIGATORIO=false`

## Rastreabilidade IBGE

O pipeline estrutural nacional deve carregar por hexagono:

- `fonte_demografica`
- `fonte_renda`
- `fonte_populacao`
- `nivel_geografico_ibge`
- `fallback_setor_censitario`
- `motivo_fallback_setor`
- `fonte_geometria_ibge`
- `metodo_atribuicao_municipio`
- `data_referencia_ibge`

## Execucao rapida do M1

```bash
pip install -e ".[dev]"
copy .env.example .env
python base_h3_brasil.py
python hex_enrichment.py --brasil
python fase1_bi_exports.py
```

## Testes relevantes do M1

```bash
python -m pytest test_base_h3_brasil.py test_hex_enrichment_brasil.py test_fase1_bi_exports.py test_fontes_gratuitas.py -v
```

## Fora do escopo deste fechamento

- M2 competitivo
- M3 imobiliario
- frontend
- ML
