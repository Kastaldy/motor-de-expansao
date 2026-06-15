# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Sumário do bloco
**BLK-DIM-05 — Features exógenas na aderência (perfil etário, densidade urbana, vínculo formal)**

Criticidade: **Alta** (loop-safe; guard substitui gate humano).

Contexto imediato: o BLK-DIM-01R concluiu com NO-GO esperado (`r2_loo_log = -0.0134`) usando
apenas `log(pop_captacao)` e `log(renda_per_capita_captacao)` como features. O módulo
`src/motor_expansao/dimensionamento/aderencia.py` está estável e é READ-ONLY neste bloco.
O spec §4 do motor de dimensionamento pede features demográfico-comportamentais EXÓGENAS
(não derivadas de pop/renda do catchment) para testar se existe sinal real de aderência.
O BLK-DIM-05 adiciona essas features e mede o delta de R²_LOO honesto.

---

## Features exógenas viáveis — inventário dos dados disponíveis

### O que EXISTE e é derivável sem ingestão ao vivo

#### 1. `n_concorrentes_raio_1_5km` — feature de saturação de mercado
- **Fonte:** `data/staging/concorrentes_mapeados.parquet` (3.296 concorrentes, 3.179 únicos
  e válidos; 39 redes; colunas `lat`, `lng`, `flag_coord_valida`, `flag_duplicado_rede_coord`)
- **Cálculo:** Haversine batch entre as 54 unidades (lat/lng de
  `data/staging/unidades_ultra_catchment.parquet`) e os concorrentes válidos. Contagem
  dos que caem em raio ≤ 1,5 km.
- **Status:** 100% viável. Testado pontualmente: PRAIA GRANDE → 7 concorrentes no raio 1,5 km.
- **Hipótese:** maior saturação → menor aderência (captura compartilhada). Sinal potencialmente
  mais discriminante que pop/renda pois é exógeno à demanda.
- **Nota técnica:** o merge maduras↔catchment funciona por `unidade` (53/54 com lat/lng;
  1 lacuna identificável). Raio 1,5 km é consistente com o raio do catchment existente.

#### 2. `densidade_pop_catchment_hab_km2` — densidade urbana ponderada no catchment
- **Fonte:** `data/outputs/setores_censitarios_2022_geo/uf=XX/cod_municipio=N/part-000.parquet`
  — coluna `densidade_pop_setor_hab_km2` calculada com `area_setor_km2_ibge` (IBGE oficial).
  Geometria WKB em EPSG:4674 disponível para cruzamento geométrico.
- **Cálculo:** somar `pop_total_setor_2022 * área_setor` dos setores que intersectam o raio
  1,5 km de cada unidade, depois dividir pela área total dos setores capturados. Alternativamente
  (mais simples): média ponderada de `densidade_pop_setor_hab_km2` por `pop_total_setor_2022`.
- **Status:** viável via `analisar_ponto_censitario_setores` (já faz o cruzamento geométrico
  e devolve os setores intersectados). O batch de 54 unidades pode reutilizar o helper existente
  ou reimplementar a lógica de intersecção bbox+área sem a UI.
- **Hipótese:** maior densidade → mais potencial de tráfego de pé → maior aderência.

#### 3. `renda_responsavel_media_catchment` — renda do responsável pelo domicílio
- **Fonte:** mesmos geo parquets — coluna `renda_responsavel_media_setor_2022` (disponível em SP,
  confirmado; varia por UF de acordo com a qualidade do join censitário).
- **Cálculo:** média ponderada por `pop_total_setor_2022` dos setores no catchment.
- **Nota:** esta é DIFERENTE de `renda_per_capita_captacao` (já no modelo): aquela é renda per
  capita estimada via proxy M1; esta é a renda do responsável diretamente do Censo 2022, sem
  o fator de calibração do M1. Pode ser colinear com a feature existente — testar correlação.
- **Status:** viável via mesmos geo parquets.

#### 4. `domicilios_captacao` — proxy de urbanização/adensamento domiciliar
- **Fonte:** geo parquets — coluna `domicilios_particulares_ocupados_setor_2022`.
- **Cálculo:** soma dos setores no catchment.
- **Hipótese:** domicílios no catchment como proxy de pares adultos e capacidade de consumo.
- **Status:** viável. Derivável junto com as features 2 e 3 no mesmo loop de leitura.

### O que NÃO existe nos dados disponíveis (lacunas)

| Feature | Status | Razão |
|---|---|---|
| % faixa etária 18-45 por setor | **AUSENTE** | O Censo 2022 Básico (tabulação por setor) não traz pirâmide etária granular. Microdados teriam, mas são 10+ GB e requerem decodificação — fora do escopo loop-safe. |
| Vínculo formal de emprego (CLT) | **AUSENTE** | Não tabulado no Censo 2022 por setor. Fonte seria RAIS/eSocial (sigiloso) ou microdados. |
| % de ocupados por setor | **AUSENTE** | Mesmo motivo — não está no censo básico por setor disponível. |

**Alternativa documentada no backlog mas inviável neste ciclo:** microdados IBGE (~10 GB,
fora do escopo `data/staging` sem ingestão ao vivo). O bloco deve documentar essa lacuna
no relatório e trabalhar com as 3 features deriváveis listadas acima.

---

## Arquivos-alvo (commit por path)

| Arquivo | Ação | Notas |
|---|---|---|
| `src/motor_expansao/dimensionamento/features_exogenas.py` | **CRIAR** | Módulo de derivação de features batch para as 54 unidades |
| `tests/unit/dimensionamento/test_features_exogenas.py` | **CRIAR** | Testes offline com fixtures sintéticas; sem I/O real nos testes |
| `data/analysis/features_aderencia.md` | **CRIAR** (gitignored) | Relatório de comparação R²_LOO com/sem features exógenas |
| `tasks/current_task.md` | **ATUALIZAR** | Skill atual → Builder |
| `tasks/completed.md` | **ATUALIZAR** | Registrar BLK-DIM-05 ao fechar |
| `tasks/backlog.md` | **ATUALIZAR** | Marcar BLK-DIM-05 como concluído |
| `context/handoff.md` + `context/handoff/TIMESTAMP-*.md` | **ATUALIZAR** | Handoffs de Planner, Builder e QA |
| `src/motor_expansao/dimensionamento/aderencia.py` | **READ-ONLY** | NÃO alterar — BLK-DIM-01R está congelado |

---

## Análise de risco

| Risco | Nível | Mitigação |
|---|---|---|
| Colinearidade entre `renda_responsavel_media` e `renda_per_capita_captacao` já existente | Médio | Medir correlação antes de incluir; se ρ > 0,85, usar só uma das duas |
| Batch geométrico de 54 unidades × 468.099 setores (geo parquets) | Médio | Filtrar por bbox antes do cruzamento exato (já é o padrão do helper censitário); usar apenas as UFs das 54 unidades |
| `n_concorrentes_raio` depende de cobertura OSM (pode subestimar em cidades menores) | Baixo | Documentar no relatório como limitação; incluir flag `n_conc_confianca_uf` |
| Coluna `lat/lng` ausente em 1 das 54 unidades no merge maduras↔catchment | Baixo | Excluir via `dropna()` + documentar; N efetivo = 53, dentro do N_MIN_CALIBRACAO=5 |
| R²_LOO ainda NO-GO mesmo com features exógenas | Aceito | Resultado científico válido; N=53 é estruturalmente pequeno. Documentar e propagar para BLK-DIM-06. |
| Guard de M1: qualquer escrita em `config.py`, `pipelines/m1/`, artefatos oficiais aborta o loop | Proteção | Os arquivos-alvo são exclusivamente novos (criar) em `dimensionamento/` + `tests/`; zero interseção com guard. |

---

## Contexto técnico para o Planner

### Interface de integração com `aderencia.py` (BLK-DIM-01R)

O módulo `aderencia.py` expõe:
- `calibrar_aderencia(df, feature_cols=["log_pop_captacao", "log_renda_per_capita"])` — aceita
  lista de features customizável.
- `AderenciaModel` — dataclass de resultado (coeficientes, métricas de validação, veredito).
- `LIMIAR_R2_GO = 0.05` — gate de materialidade.

O Builder deve criar `features_exogenas.py` que:
1. Carrega `base_calibracao_maduras.parquet` + `unidades_ultra_catchment.parquet` (para lat/lng).
2. Carrega `concorrentes_mapeados.parquet` e calcula `n_concorrentes_raio_1_5km` por unidade.
3. Para cada unidade, lê os geo parquets do setor correspondente (filtrando por UF do catchment)
   e deriva `densidade_pop_catchment_hab_km2`, `renda_responsavel_media_catchment`,
   `domicilios_captacao` via cruzamento por bbox (fast-path) + confirmação por distância.
4. Monta um `df_features` com as features exógenas por unidade (54 linhas).
5. Chama `calibrar_aderencia(df, feature_cols=[...])` em 3 variantes:
   - Baseline (só pop+renda — reproduz BLK-DIM-01R)
   - Modelo A: pop + renda + n_concorrentes
   - Modelo B: pop + renda + n_concorrentes + densidade + renda_responsavel
6. Compara `r2_loo_log` dos 3 modelos e gera relatório `data/analysis/features_aderencia.md`.

### Padrão de teste (copiar de `test_aderencia.py`)
- Fixtures sintéticas: gerar `n_concorrentes` e `densidade` aleatórios sem correlação com
  `pagantes` para garantir controle negativo (NO-GO mesmo com features).
- Fixture positiva: criar `pagantes = f(n_conc, densidade)` com ruído para garantir que a
  função de derivação de features funciona e que o pipeline de LOO-CV roda.
- Não usar dados reais nos testes (sem I/O de parquet nos testes unitários).

### Colunas-chave disponíveis nos geo parquets (confirmadas)
```
cod_setor, uf, cod_municipio, area_setor_km2_ibge, pop_total_setor_2022,
domicilios_particulares_ocupados_setor_2022, renda_responsavel_media_setor_2022,
renda_per_capita_setor_2022_calibrada, densidade_pop_setor_hab_km2,
bbox_minx, bbox_miny, bbox_maxx, bbox_maxy, geometry_wkb (EPSG:4674),
flag_renda_disponivel, flag_geometria_valida
```

### Colunas-chave em `unidades_ultra_catchment.parquet` (54 linhas)
```
unidade, unidade_norm, uf, lat, lng, pop_captacao, renda_per_capita_captacao,
n_setores_captacao, raio_km
```

### Merge maduras ↔ catchment
```python
df_mad = pd.read_parquet("data/staging/base_calibracao_maduras.parquet")
df_catch = pd.read_parquet("data/staging/unidades_ultra_catchment.parquet")
df = df_mad.merge(df_catch[["unidade", "lat", "lng"]], on="unidade", how="left")
# 53/54 com lat/lng; 1 lacuna: excluir via dropna(subset=["lat","lng"])
```

---

## Guardrails ativos
- READ-ONLY sobre M1 (DEC-001): zero escrita em `score_priorizacao`, pesos, artefatos oficiais.
- `aderencia.py` é READ-ONLY neste bloco (BLK-DIM-01R congelado).
- Sem ingestão ao vivo: apenas `data/staging/` e `data/outputs/setores_censitarios_2022_geo/`.
- Sem PII em disco.
- `data/analysis/features_aderencia.md` é gitignored — não versionar.
- Guard do loop (`scripts/loop_guard.py`) bloqueia qualquer diff em `config.py`,
  `pipelines/m1/`, artefatos M1, VPS/deploy/segredos.
