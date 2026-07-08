# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-VIAB-02 — Faixa de demanda-premissa por tier de metragem (comparáveis reais)**

Derivar percentis (p10/p50/p90) de alunos por unidade para 5 tiers de metragem, combinando
Ultra (54 unidades, `data/staging/unidades_ultra_performance_hex.parquet`) e Engenharia do Corpo
(58 linhas válidas, `data/validacao/academias_engenharia_do_corpo.xlsx`), materializando
`data/staging/demanda_premissa_por_tier.parquet` como `base_calibracao_df` para o VIAB-03.

## Objetivo
Produzir um parquet determinístico com p10/p50/p90 de alunos por tier de metragem a partir
das 112 unidades reais com metragem+alunos disponíveis, sem tocar o M1 e sem prever demanda
por geografia (DEC-009).

## ACHADO CRÍTICO — Discrepância com o backlog

O backlog cita "~1.100 academias REAIS com metragem+alunos totais" como base de calibração.
**Isso é INCORRETO.** A inspeção real das fontes revelou:

| Fonte | Metragem disponível? | Alunos disponíveis? | Usável? |
|---|---|---|---|
| `unidades_ultra_performance_hex.parquet` (54 linhas) | SIM (`metragem`: 750–2800 m²) | SIM (`alunos_total`: 1206–6251) | **SIM** |
| `academias_engenharia_do_corpo.xlsx` (61 linhas, 58 válidas) | SIM (`Metragem M²`: 636–5863 m²) | SIM (`Alunos Totais`: 763–9615) | **SIM** |
| `KPIs_Smart_2025_02 (1).xlsx` | **NÃO** — colunas: Data_Ref, Sigla, Nome, Propriedade, Alunos Totais SF, Acessos SF, Frequencia | só alunos | **NÃO** |
| `Sky Fit dados.xlsx` (header=3) | **NÃO** — colunas: ID SKY, NOMENCLATURA UNIDADE, ENDERECO, CIDADE, ESTADO, Alunos EVO, Alunos Gympass, Alunos TotalPass | só alunos | **NÃO** |
| `concorrentes/Unidades/unidades_smart_fit.csv` | **NÃO** — só nome_unidade;latitude;longitude;data_coleta | NÃO | **NÃO** |
| `concorrentes/Unidades/unidades_skyfit.csv` | **NÃO** — só nome_unidade;latitude;longitude;data_coleta | NÃO | **NÃO** |

**Base real disponível: Ultra (54) + Eng Corpo (58 válidas) = 112 unidades.**
Smart Fit e Sky Fit NÃO têm coluna de metragem em nenhuma das fontes disponíveis.
O backlog deve ser atualizado para refletir N ≈ 112, não ~1.100.

## Distribuição por tier (preview — dados reais, Ultra+Eng combinados)

| Tier (m²) | N | p10 (alunos) | p50 (alunos) | p90 (alunos) |
|---|---|---|---|---|
| < 1.000 | 17 | 1.467 | 2.063 | 3.589 |
| 1.000–1.499 | 46 | 1.558 | 2.532 | 3.889 |
| 1.500–1.999 | 36 | 1.763 | 2.748 | 4.578 |
| 2.000–2.999 | 11 | 2.870 | 3.888 | 4.752 |
| >= 3.000 | 2 | 2.578 | 5.706 | 8.833 |

**Atenção:** o tier >= 3.000 m² tem apenas 2 observações (ambas Eng Corpo). O parquet deve
registrar `n=2` e o relatório de qualidade deve alertar explicitamente para extrapolação nessa faixa.

## Escopo permitido
- Criar `src/motor_expansao/dimensionamento/demanda_premissa.py` (novo módulo)
- Criar `tests/unit/dimensionamento/test_demanda_premissa.py` (testes novos)
- Materializar `data/staging/demanda_premissa_por_tier.parquet` (gitignored, NÃO commitado)
- Materializar `data/analysis/demanda_premissa_qualidade.md` (gitignored, NÃO commitado) com:
  - N por tier
  - alerta explícito para tier >= 3.000 m² (N=2, extrapolação)
  - alerta da discrepância com o backlog (esperado ~1.100, real 112)
- Atualizar `tasks/backlog.md` apenas para corrigir a referência a "~1.100 academias" -> "~112 unidades"
- Atualizar `tasks/completed.md` ao fechar o bloco
- Atualizar `context/handoff.md` e `tasks/current_task.md` ao longo do ciclo

## Fora de escopo
- Modificar `viabilidade_ponto.py` (o módulo consome `base_calibracao_df` já hoje — não mudar)
- Usar `membros`/agregador como alvo de demanda (DEC-009, proibido)
- Usar lat/lng de qualquer fonte como preditor de demanda (DEC-009, proibido)
- Usar Smart Fit ou Sky Fit como base de metragem->alunos (não têm metragem disponível)
- Tentar adicionar metragem a Smart Fit/Sky Fit por join geoespacial (fora de escopo deste bloco)
- Tocar qualquer artefato oficial do M1 (`config.py`, `pipelines/m1/`, `brasil_*.parquet`, etc.)
- Deploy, VPS, alterações de dashboard, API
- Extra `[demanda]` ou dependência nova no `pyproject.toml` (o módulo usa só pandas/numpy/openpyxl já presentes)

## Arquivos que devem ser lidos
- `/repo/src/motor_expansao/dimensionamento/viabilidade_ponto.py` — entender como `base_calibracao_df` é consumida (função `faixa_alunos_por_densidade`; requer colunas `alunos_por_m2` e `metragem`)
- `/repo/src/motor_expansao/dimensionamento/config.py` — parametros canônicos do módulo
- `/repo/data/staging/unidades_ultra_performance_hex.parquet` — fonte Ultra (colunas: `metragem`, `alunos_total`)
- `/repo/data/validacao/academias_engenharia_do_corpo.xlsx` — fonte Eng Corpo (colunas: `Metragem M²`, `Alunos Totais`; 58 linhas válidas)
- `/repo/tasks/backlog.md` — seção BLK-VIAB-02 (para corrigir "~1.100" -> "~112")
- `/repo/tests/unit/dimensionamento/test_viabilidade_ponto.py` — padrão de testes do módulo irmão

## Arquivos que podem ser alterados
- `/repo/src/motor_expansao/dimensionamento/demanda_premissa.py` — CRIAR (novo)
- `/repo/tests/unit/dimensionamento/test_demanda_premissa.py` — CRIAR (novo)
- `/repo/tasks/backlog.md` — corrigir menção "~1.100 academias" na seção BLK-VIAB-02
- `/repo/tasks/completed.md` — registrar conclusão ao fechar
- `/repo/tasks/current_task.md` — atualizar status/próxima Skill
- `/repo/context/handoff.md` — próximo handoff do ciclo
- `/repo/context/handoff/` — snapshot de cada handoff

**Gitignored (materializar localmente, NÃO commitar):**
- `data/staging/demanda_premissa_por_tier.parquet`
- `data/analysis/demanda_premissa_qualidade.md`

## Contrato do parquet de saída

Colunas obrigatórias de `data/staging/demanda_premissa_por_tier.parquet`:

| Coluna | Tipo | Descrição |
|---|---|---|
| `tier` | str | Label do tier: `"<1.000"`, `"1.000-1.499"`, `"1.500-1.999"`, `"2.000-2.999"`, `">=3.000"` |
| `n` | int | Número de comparáveis no tier |
| `p10` | float | Percentil 10 de alunos por unidade |
| `p50` | float | Percentil 50 (mediana) de alunos por unidade |
| `p90` | float | Percentil 90 de alunos por unidade |
| `versao_contrato` | str | Sempre `"demanda_premissa_v1"` |

Deve haver **exatamente 5 linhas** (uma por tier), mesmo que n=0 (nesse caso p10/p50/p90 = NaN).

## Contrato do módulo demanda_premissa.py

Funções públicas mínimas:
- `carregar_ultra(path: Path | str) -> pd.DataFrame` — lê o parquet, retorna df com `metragem` e `alunos_total`
- `carregar_eng_corpo(path: Path | str) -> pd.DataFrame` — lê o xlsx, retorna df com `metragem` e `alunos`
- `calcular_demanda_premissa_por_tier(df: pd.DataFrame) -> pd.DataFrame` — recebe df com `metragem` e `alunos`, retorna parquet-ready com 5 linhas
- `main(ultra_path, eng_path, out_path, relatorio_path) -> None` — ponto de entrada CLI/batch, materializa parquet + relatório

O módulo deve ser **puro** (sem I/O interno oculto — o chamador injeta os paths), **determinístico** e sem dependências novas.

## Nota sobre compatibilidade com viabilidade_ponto.py

A função `faixa_alunos_por_densidade` em `viabilidade_ponto.py` recebe `base_calibracao_df`
com colunas `alunos_por_m2` (densidade) e `metragem`, e usa janela de +-20%/50% em torno do
m² do imóvel. O parquet de tier deste bloco **não** tem o formato de linhas brutas — é um
agregado por tier (p10/p50/p90). O VIAB-03 será responsável por converter o parquet de tier
em `base_calibracao_df` no formato que `faixa_alunos_por_densidade` espera, **ou** criar uma
função alternativa de lookup por tier. O Builder deste bloco **não deve alterar**
`viabilidade_ponto.py` — o contrato de consumo fica para o VIAB-03.

## Critérios de aceite
- `data/staging/demanda_premissa_por_tier.parquet` existe com 5 linhas e colunas `tier`, `n`, `p10`, `p50`, `p90`, `versao_contrato`
- `n` por tier bate com os valores inspecionados: 17, 46, 36, 11, 2 (total 112)
- Nenhuma coluna de PII (nome de unidade, lat, lng, endereço) no parquet de saída — só contagens agregadas
- `data/analysis/demanda_premissa_qualidade.md` existe e documenta: N por tier, alerta de N=2 no tier >= 3.000, discrepância com o backlog (~1.100 vs 112 real)
- Testes em `tests/unit/dimensionamento/test_demanda_premissa.py` passam (fixtures sintéticas, sem ler dados reais)
- `pytest -q` limpo (sem regressão na suíte completa)
- `ruff check src/ tests/` limpo
- `loop_guard.py` limpo (nenhum arquivo M1 tocado no diff)
- `viabilidade_ponto.py` inalterado (`git diff` vazio nesse arquivo)
- Módulo `demanda_premissa.py` determinístico (mesma entrada -> mesmo resultado; sem aleatoriedade)

## Criticidade classificada
**Média** (insumo de premissa do motor; READ-ONLY sobre o M1; nenhum artefato oficial tocado)

## Esteira recomendada
Block Orchestrator (este) -> **Planner** -> Builder -> QA

## Riscos identificados
- **Tier >= 3.000 m² com N=2:** percentis instáveis; o relatório de qualidade DEVE alertar explicitamente e o parquet DEVE expor `n=2` para que o consumidor (VIAB-03) possa aplicar `flag_extrapolacao`
- **Discrepância backlog vs real:** o backlog menciona "~1.100 academias" — isso pode confundir o Builder; o handoff corrige explicitamente (Smart Fit e Sky Fit não têm metragem)
- **Eng Corpo inclui academias acima de 3.500 m²:** porte muito diferente da Ultra; o relatório de qualidade deve notar isso (sem filtrar, apenas documentar)
- **Fonte Ultra inclui `alunos_total` = ativos + agregadores:** a DEC-009 permite usar `alunos_total` (alunos REAIS); é o alvo correto; não confundir com `membros` do dump de demanda revelada

## Guardrails ativos
- **§5 READ-ONLY M1:** nenhuma escrita em `config.py`, `pipelines/m1/`, `brasil_*.parquet`, `hexagonos_brasil_*.parquet`, `top_oportunidades_resumo.csv`, `resumo_por_uf.csv` nem qualquer artefato oficial. `loop_guard.py` verifica automaticamente.
- **DEC-009 (crítico):** a demanda NUNCA é derivada de lat/lng do ponto candidato. O alvo de calibração = `alunos_total` (Ultra) / `Alunos Totais` (Eng Corpo) — alunos REAIS observados. PROIBIDO usar `membros`/agregadores corporativos como alvo. PROIBIDO usar qualquer coluna geográfica como preditor de demanda.
- **DEC-001 (vigente):** `score_priorizacao`, `hex_score_estrutural`, pesos `renda=0.40`/`pop=0.60` INALTERADOS.
- **§6.1 loop-safe:** sem rede, sem VPS, sem segredos; saída em `data/staging/` e `data/analysis/` (gitignored); sem ingestão ao vivo; sem UI.
- **Anti-PII:** o parquet de saída contém APENAS contagens agregadas (tier, n, p10, p50, p90). Nenhuma linha individual de unidade, nenhum identificador, nenhuma coordenada.
