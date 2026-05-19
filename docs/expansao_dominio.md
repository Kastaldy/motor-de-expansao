# Expansao de Dominio — Contrato Tecnico
> Versao: 2026-05-18 | Ciclo: Expansao de Dominio
> Feature paralela ao M1: nao substitui score_priorizacao, carteira nem plano curto prazo.

## 1. Posicionamento

A Expansao de Dominio converte o ranking individual de hexes em um **plano sequencial de ocupacao territorial** por cidade. Ela opera sobre os outputs do modelo de mercado por hexagono e nunca recalcula nem sobrescreve artefatos oficiais do M1.

Hierarquia de decisao:
- M1 (`score_priorizacao`): aprovacao de municipios e ranking executivo → inalterado.
- Carteira e plano curto prazo: referencia operacional → inalterados.
- Expansao de Dominio: sequencia de abertura dentro de cidades ja elegidas ou candidatas.

## 2. Semantica de conceitos

| Conceito | Definicao |
| --- | --- |
| **Cidade/regiao** | Agrupamento por `cod_municipio` (IBGE). |
| **Cluster** | Conjunto contíguo de hexes H3 res7 dentro do mesmo `cod_municipio`, com score residual mínimo e sem flag de canibalizacao Ultra. Adjacencia via `h3.k_ring(hex, 1)`. |
| **Hex ancora** | Hex selecionado pelo algoritmo greedy como candidato prioritario de abertura. Maximiza residual incremental capturado no cluster. |
| **Residual capturado** | Fracao de `oferta_efetiva_disponivel` que uma unidade aberta no hex ancora consegue servir, usando decaimento linear ate 2 km. |
| **Sobreposicao** | Interseccao do raio de captura (2 km) de uma nova ancora com raio de ancora ja selecionada; penaliza a escolha greedy. |
| **Protecao de marca** | Gate que bloqueia ancoras em hexes a menos de `DIST_MIN_ULTRA_AINDA_KM` de unidade Ultra existente, evitando canibalizacao. |
| **Fase de abertura** | Ordem sequencial (`ordem_expansao_cidade`) dentro da cidade; fase 1 = hex com maior ganho incremental. |

## 3. Parametros iniciais

```python
# Resolucao H3 (alinhado ao M1)
H3_RESOLUTION = 7

# Raio de captura residual por unidade aberta (km)
RAIO_CAPTURA_KM = 2.0

# Distancia minima entre novas ancoras (km)
DIST_MIN_NOVAS_ULTRAS_KM = 1.5

# Distancia minima de unidade Ultra ja existente (km) — alinhado ao M1
DIST_MIN_ULTRA_EXISTENTE_KM = 1.0

# Maximo de ancoras sugeridas por cidade (default)
MAX_ANCORAS_POR_CIDADE = 10

# Score residual minimo para candidato
MIN_SCORE_OPORTUNIDADE_RESIDUAL = 20.0

# Capacidade proxy por unidade concorrente (alunos) — alinhado ao modelo de mercado
CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS = 2500
```

## 4. Gates de elegibilidade de candidato

Um hex entra na base de candidatos apenas se:
1. `flag_sam_fitness == True`
2. `oferta_efetiva_disponivel > 0`
3. `score_oportunidade_residual >= MIN_SCORE_OPORTUNIDADE_RESIDUAL`
4. `lat` e `lng` nao nulos
5. `flag_canibalizacao_ultra_1km == False`
6. Coordenadas geograficamente validas (lat em [-90,90], lng em [-180,180])

## 5. Schema de `plano_expansao_dominio.parquet`

| Coluna | Tipo | Descricao |
| --- | --- | --- |
| `hex_id` | str | ID H3 res7 do hex ancora |
| `uf` | str | Sigla UF |
| `cod_municipio` | str | Codigo IBGE municipio |
| `nome_municipio` | str | Nome do municipio |
| `lat` | float | Latitude centroide |
| `lng` | float | Longitude centroide |
| `cluster_id` | str | ID do cluster intraurbano (formato `{cod_municipio}_{seq}`) |
| `n_hex_cluster` | int | Numero de hexes no cluster |
| `ordem_expansao_cidade` | int | Sequencia de abertura dentro da cidade (1=prioritaria) |
| `score_oportunidade_residual` | float | Score residual do hex ancora |
| `oferta_efetiva_disponivel` | float | Alunos residuais disponiveis no hex |
| `residual_incremental_capturado` | float | Residual adicional capturado por esta ancora |
| `residual_cluster_pos_acao` | float | Residual remanescente no cluster apos abertura |
| `sam_fitness_potencial` | float | SAM fitness do hex |
| `sam_total_cluster` | float | SAM total do cluster |
| `residual_total_cluster` | float | Residual total do cluster antes da acao |
| `score_residual_max` | float | Score residual maximo do cluster |
| `score_residual_medio` | float | Score residual medio do cluster |
| `pressao_concorrencial_media` | float | Media de `pressao_concorrencial_score_2km` no cluster |
| `dist_ultra_min_cluster` | float | Menor distancia a Ultra existente no cluster (m) |
| `dist_nova_ancora_mais_proxima_m` | float | Distancia ate a ancora mais proxima ja selecionada (m) |
| `tese_dominio` | str | Classificacao estrategica da abertura |
| `rank_dominio_brasil` | int | Ranking nacional da ancora |
| `rank_dominio_uf` | int | Ranking dentro da UF |
| `rank_dominio_cidade` | int | Ranking dentro da cidade |
| `n_concorrentes_mapeados_2km` | int | Concorrentes mapeados em 2 km |
| `dist_ultra_mais_proxima_m` | float | Distancia a Ultra existente mais proxima (m) |
| `flag_canibalizacao_ultra_1km` | bool | Flag de canibalizacao Ultra em 1 km |

## 6. Teses de dominio

| Tese | Condicao |
| --- | --- |
| `dominar_white_space` | `flag_white_space_2km == True` e score residual alto |
| `abrir_com_disputa` | Concorrentes presentes, residual > 0, Ultra ausente |
| `proteger_corredor_ultra` | Distancia a Ultra existente entre 1.0 e 2.0 km; anchor protege corredor |
| `adensar_cluster` | Cluster grande com multiplas ancoras; ordem >= 2 |
| `monitorar` | Score abaixo do limiar ou concorrencia intensa sem vantagem clara |
| `bloqueado_canibalizacao` | `flag_canibalizacao_ultra_1km == True` (excluido da base ativa) |

## 7. Guardrails

- Este modulo **nunca** altera `score_priorizacao`, `hex_score_estrutural`, `carteira_expansao_acionavel.parquet` nem `plano_expansao_curto_prazo.parquet`.
- Qualquer mudanca de parametro deve ser registrada neste documento e validada por testes antes do merge.
- O campo `hex_id` em `plano_expansao_dominio.parquet` nao pode ter duplicatas por execucao.
- Pins visuais de ancoras no dashboard sao apenas auxiliares; nao afetam scores nem rankings oficiais.

## 8. Fontes e limitacoes

- Concorrentes mapeados: grandes redes (Smart Fit, Bluefit, Panobianco); academias independentes ausentes.
- Capacidade proxy de 2500 alunos por unidade; sem ajuste por formato de loja.
- Populacao por `pop_hex_base` (censo 2022 quando disponivel, proxy M1 como fallback).
- Score residual calibrado para publico geral fitness; sem segmentacao por faixa etaria alem do publico-alvo 18-45 definido no M1.

## 9. Hardening operacional (Bloco 8)

- **Constantes centralizadas**: `DOMINIO_SCHEMA_MINIMO` e `DOMINIO_TESES_VALIDAS` em `dashboard/constants.py` (fonte canonica para testes e dashboard).
- **Smoke de schema interno**: `validate_dominio_schema(df)` em `gerar_plano_expansao_dominio.py`; chamada automaticamente por `materializar()` antes de salvar.
- `SCHEMA_DOMINIO_OBRIGATORIO` no pipeline e `DOMINIO_SCHEMA_MINIMO` em `constants.py` sao identicos por design — teste unitario valida a igualdade.
- **Guardrail M1**: testes unitarios verificam que `SAIDA_PARQUET` e `SAIDA_CSV` nao apontam para paths de artefatos M1; testes de integracao (condicionais) verificam que `carteira` e `plano_cp` contem `score_priorizacao` intacto apos execucao do pipeline.
- **Conflito de nomes pytest**: adicionados `__init__.py` a `tests/unit/`, `tests/integration/` e `tests/contracts/` para resolver colisao de modulos de mesmo nome.
