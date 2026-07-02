# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-TP-08 — Ingestão anti-PII das academias menores (WellHub/TotalPass) na camada de oferta.**
Ingerir a planilha `NAO_ABRA/03_Competidores.xlsx` (24.045 academias não-rede, com `Alunos_Academia`)
como uma camada de OFERTA agregada por `hex_id` (H3 res-7), descartando toda PII na fronteira de entrada
(Latitude/Longitude individuais e `Nome_Academia`), materializando um parquet de staging NÃO oficial
(`data/staging/oferta_academias_menores_h3.parquet`, gitignored) + um **relatório de qualidade e DEDUP**
vs `data/staging/concorrentes_mapeados.parquet` (para não contar oferta em dobro). É o 1º passo da
DEC-013 (parte 3): armazenar os agregadores WellHub/TotalPass como ativo de oferta ANTES de qualquer
integração ao residual. **NÃO** recompõe `score_oportunidade_residual` nem regenera parquets de mercado
(follow-up). READ-ONLY sobre o M1.

## Objetivo
Materializar um parquet de staging anti-PII com a oferta de academias menores agregada por hex res-7,
acompanhado de um relatório de qualidade+DEDUP vs `concorrentes_mapeados.parquet`, sem tocar no M1 nem no residual.

## Inventário do `03_Competidores.xlsx` (anti-PII)
Inspeção via pandas lendo SÓ metadados de coluna (nomes/dtype/contagens/distribuições categóricas e estatísticas
agregadas de coordenada) — **nenhuma linha individual, nome de estabelecimento ou coordenada individual foi
impressa/persistida**. Schema real (1 aba `Competidores`, **24.045 linhas × 9 colunas**):

| coluna | dtype | notna | nunique | classificação | tratamento na fronteira |
|---|---|---|---|---|---|
| `Latitude` | float64 | 24045 | 1199 | **PII (coordenada)** | usar SÓ para derivar `hex_id`, depois DROPAR |
| `Longitude` | float64 | 24045 | 1047 | **PII (coordenada)** | usar SÓ para derivar `hex_id`, depois DROPAR |
| `Cluster_ID` | float64 | **0** | **0** | vazia (100% null) | IGNORAR (inutilizável) |
| `Total_Academias` | int64 | 24045 | 8 | atributo de cluster (1..8) | não-PII; usar só se o Planner definir agregação |
| `Total_Alunos_Cluster` | int64 | 24045 | 1248 | atributo de cluster | não-PII; **cautela de dupla-contagem** (é soma por cluster, não por linha) |
| `Nome_Academia` | object | 24045 | 22097 | **PII (nome do estabelecimento)** | usar SÓ em memória p/ DEDUP por token; NUNCA persistir/logar |
| `Plano` | object | 24045 | 11 | categórico (tp0..tp7, `_plus`) | não-PII; proxy de tipo/capacidade se o Planner quiser |
| `Alunos_Academia` | int64 | 24045 | 1026 | **capacidade/oferta** (alunos por academia) | não-PII; **coluna de OFERTA a agregar por hex** |
| `Município` | object | 24045 | 212 | categórico (cabeçalho vem corrompido `Munic�pio`) | não-PII; fallback grosseiro / cross-check |

**Coordenada vs só-município — resolvido:** a planilha **TEM coordenada** (`Latitude`/`Longitude`), então
`hex_id` res-7 é derivável na fronteira via `h3.latlng_to_cell` — **NÃO** é o caso "só município". **PORÉM
as coordenadas estão arredondadas a ~2 casas decimais** (mediana e máximo = 2 casas → ~1,1 km de precisão),
o mesmo caveat do BLK-TP-01 (coords ~1 km) → introduz ruído no join res-7 (múltiplas academias caem no
mesmo hex por arredondamento; borda de hex incerta). Todas as 24.045 linhas caem dentro do bbox do Brasil
(lat −33,5..2,9 / lng −72,7..−34,8). `Alunos_Academia`: mediana 19, média 79,9, máx 5.276, min 0 (há zeros).

**Sinal de DEDUP (contagem de tokens de rede em `Nome_Academia`, sem imprimir nomes):** panobianco 149,
bio ritmo 33, smart 29, selfit 1, "fit" 6532 (ruído). Confirma que **parte das academias menores JÁ está
mapeada** em `concorrentes_mapeados.parquet` → dupla-contagem de oferta é risco real.

**`concorrentes_mapeados.parquet` (chave para o DEDUP):** 3.296 linhas (3.179 `valido`), 28 redes,
colunas `[concorrente_id, rede, nome_unidade, lat, lng, data_coleta, arquivo_origem, flag_coord_valida,
flag_duplicado_rede_coord, status_registro, hex_id_res7]`; **1.659 `hex_id_res7` únicos** (3.179 notna).
→ A base de concorrentes JÁ tem `hex_id_res7`, então o DEDUP por sobreposição de hex é viável sem tocar PII.

## Escopo permitido
- Novo módulo de ingestão numa camada paralela isolada (pacote existente `src/motor_expansao/demanda_revelada/`
  ou submódulo disjunto ali) que consuma `NAO_ABRA/03_Competidores.xlsx` (fonte parametrizável, default gitignored).
- Contrato de saída anti-PII agregado por hex res-7. Colunas candidatas (o Planner define a lista exata):
  `hex_id` (res-7), `n_academias_menores` (contagem de academias no hex), `alunos_academias_menores`
  (Σ `Alunos_Academia` no hex), `versao_contrato` (carimbo, ex.: `oferta_academias_menores_v1`). Opcional
  sob decisão do Planner: n por `Plano`/tipo, ou marca de sobreposição com concorrente mapeado.
- Derivar `hex_id` na FRONTEIRA a partir de `Latitude`/`Longitude`, depois DROPAR as coordenadas.
- Materializar `data/staging/oferta_academias_menores_h3.parquet` (gitignored, NÃO oficial).
- **Relatório de qualidade + DEDUP** em `data/reports/scratch/` (gitignored) ou `data/analysis/` (gitignored):
  cobertura (nº hexes, nº que casam com o universo do Motor), caveat de coords ~1 km, e quantas academias
  menores caem em hex que já contém concorrente mapeado (oferta potencialmente duplicada) + estratégia de DEDUP.
- Rede de segurança anti-PII automatizada (reuso do padrão `_assert_sem_pii` + `COLUNAS_PII_PROIBIDAS` do
  `demanda_revelada/`) e teste `test_zero_pii` sobre fixture sintética.
- Fixture sintética nova (padrão `tests/fixtures/demanda_revelada_fake.html`) — um `.xlsx` ou CSV sintético,
  sem PII real — para os testes; a suíte NUNCA lê o `NAO_ABRA/` real.

## Fora de escopo
- Recompor/alterar `score_oportunidade_residual`, `oferta_efetiva_disponivel`, `oferta_consumida_*` ou
  qualquer coluna de `hexagonos_mercado_mapeado.parquet` / `calcular_colunas_mercado.py` (FOLLOW-UP: BLK-TP-09/epic dedup+Huff).
- Regenerar qualquer parquet de mercado/residual, carteira, plano ou os 4 artefatos oficiais do M1.
- Qualquer escrita/recálculo em `score_priorizacao`, `hex_score_estrutural`, pesos (renda 0.40/pop 0.60).
- Modelar capacidade real por tipo/plano (Huff/dedup fino) — é a epic futura da DEC-013 parte 3; aqui só se
  DOCUMENTA a variabilidade de capacidade no relatório, não se aplica.
- Import de `pipelines/m1`, `dashboard`, `censo_*` ou `api` a partir do módulo novo.
- Versionar a fonte real (`NAO_ABRA/03_Competidores.xlsx`) ou qualquer parquet/relatório com PII.
- Persistir/logar `Latitude`/`Longitude`/`Nome_Academia` individuais em qualquer artefato, log ou cache.
- Deploy, VPS, alteração de contrato do `demanda_revelada_v1` existente.

## Arquivos que devem ser lidos
- `CLAUDE.md` (§1 Ultra low-cost / WellHub-TotalPass; §4 camada mercado/residual e `oferta_efetiva_disponivel`;
  §5 guardrails; DEC-012 anti-PII por construção; DEC-013 parte 3 dedup+capacidade por tipo)
- `tasks/backlog.md` (bloco `### BLK-TP-08`, linhas 960–995; cabeçalho do epic `## Epic BLK-TP`, linha 851)
- `tasks/current_task.md`
- `src/motor_expansao/demanda_revelada/contrato.py` (contrato de colunas + `COLUNAS_PII_PROIBIDAS`)
- `src/motor_expansao/demanda_revelada/ingestao.py` (padrão de fronteira anti-PII: `_to_cell`, `_agregar_h3`,
  `_assert_sem_pii`, `_assert_res7`, `ingerir_*` com `escrever`/fonte parametrizável)
- `tests/unit/test_demanda_revelada_ingestao.py` e `tests/unit/test_demanda_revelada_validacao.py` (padrão de teste + fixture sintética)
- `docs/modelo_mercado_hexagonos.md` (§5.6 `oferta_efetiva_disponivel`/oferta instalada; §7 — "academias
  independentes e boutiques" estão explicitamente FORA da camada atual → é exatamente essa lacuna que o bloco stage;
  §3 dicionário de `concorrentes_mapeados` para escopar o DEDUP por `hex_id_res7`)
- `.gitignore` (confirmar `NAO_ABRA/`, `data/staging/*`, `data/analysis/`, `data/reports/scratch/`, `*.parquet`)

## Arquivos que podem ser alterados
- `src/motor_expansao/demanda_revelada/` (novos: p.ex. `oferta_academias_menores.py` [contrato+ingestão] — ou
  par contrato/ingestão análogo ao existente; sem import de M1/dashboard/censo/api)
- `tests/unit/` (novo `test_oferta_academias_menores*.py`) + `tests/fixtures/` (nova fixture sintética anti-PII)
- Gerados em runtime (NÃO commitáveis; já gitignored): `data/staging/oferta_academias_menores_h3.parquet` e o
  relatório em `data/reports/scratch/*.md` (ou `data/analysis/*.md`)
- `docs/modelo_mercado_hexagonos.md` (opcional: nota curta de que a oferta de academias menores foi STAGED
  como camada separada, ainda NÃO integrada ao residual)
- Bookkeeping: `tasks/backlog.md` (bloco BLK-TP-08), `tasks/current_task.md`, `tasks/completed.md`,
  `context/handoff.md`, `context/handoff/`
- Script opcional em `scripts/` (wrapper de execução da ingestão), se o Planner assim decidir

## Critérios de aceite
- Ingestão isolada na camada paralela; `grep` de import NÃO acusa `pipelines.m1`, `dashboard`, `censo`, `api` no módulo novo.
- Parquet `data/staging/oferta_academias_menores_h3.parquet` gerado, agregado por `hex_id` res-7 válido
  (todos os hexes passam `h3.is_valid_cell` + `get_resolution==7`), com carimbo `versao_contrato`.
- **Zero PII no artefato/relatório/teste:** nenhuma coluna de `COLUNAS_PII_PROIBIDAS` (Lat/Lng/Nome/etc.)
  no parquet nem no relatório; teste `test_zero_pii` cobre o contrato e falha se qualquer PII aparecer.
- **Relatório de qualidade + DEDUP** presente e legível: nº de academias/alunos agregados, nº de hexes, %
  que casa com o universo do Motor, caveat de coords ~1 km, e a **medição de sobreposição vs
  `concorrentes_mapeados.parquet`** (quantos hexes/quantos alunos de academias menores caem em hex que já
  tem concorrente mapeado) + a **estratégia de DEDUP candidata** registrada para o gate.
- Fonte real (`NAO_ABRA/03_Competidores.xlsx`) NÃO versionada; testes usam fixture sintética (a suíte não lê o dump real).
- **mtime dos 4 artefatos oficiais do M1 inalterado** (`brasil_estrutural.parquet`, `brasil_priorizados.parquet`,
  `hexagonos_brasil_oportunidades.parquet`, `hexagonos_brasil_dashboard.parquet`).
- `score_oportunidade_residual` e parquets de mercado NÃO regenerados/alterados (nenhuma escrita nessa cadeia).
- Suíte verde (`pytest -n auto`); `import streamlit_app` ok; ruff+mypy limpos.

## Criticidade classificada
**Alta.** Nova ingestão de fonte externa com **PII na origem** que enriquecerá a camada de OFERTA/residual;
READ-ONLY sobre o M1 (camada paralela — não toca score/pesos/carteira/plano/artefatos oficiais). Não é
Crítica porque não altera nenhum artefato/fórmula do M1 nem do score de mercado (só STAGE a oferta); a
sensibilidade que a eleva a Alta é a PII na origem + o julgamento de DEDUP, que exigem **revisão humana obrigatória**.

## Esteira recomendada
Block Orchestrator → Planner → **[REVISÃO HUMANA OBRIGATÓRIA — anti-PII + estratégia de DEDUP]** → Builder → QA.
(O gate humano decide método: contrato exato das colunas agregadas, a estratégia de DEDUP e o tratamento do
caveat de coords ~1 km. Autonomia = **manual, NÃO loop-safe**.)

## Riscos identificados
- **PII na origem:** `Latitude`/`Longitude`/`Nome_Academia` são PII. Mitigação obrigatória (DEC-012): agregar
  na fronteira, dropar coords após derivar `hex_id`, nunca persistir/logar nome/coordenada; `COLUNAS_PII_PROIBIDAS` + `test_zero_pii`.
- **Coords arredondadas a ~2 casas (~1 km):** ruído no join res-7 (academias distintas colapsam no mesmo hex;
  hex de borda incerto). Mesmo caveat do BLK-TP-01 → registrar no relatório; a camada é refino, não verdade fina.
- **Dupla-contagem de oferta (o risco central do bloco):** tokens de rede em `Nome_Academia` (panobianco 149,
  smart 29, bio ritmo 33, ...) indicam que academias já mapeadas em `concorrentes_mapeados` reaparecem aqui.
  **Estratégia candidata de DEDUP (para o gate):** por **sobreposição de `hex_id_res7`** (a base de concorrentes
  já tem essa chave — 1.659 hexes) como cross-check primário, complementada por token de nome normalizado
  APENAS em memória (nunca persistido). Como este bloco NÃO integra ao residual, o DEDUP aqui é **de RELATÓRIO
  (quantificar a sobreposição)**, não de subtração de oferta — a subtração fica para o follow-up.
- **`Total_Alunos_Cluster` é soma por cluster, não por linha:** somá-lo ingenuamente duplica alunos; a coluna de
  oferta correta a agregar é `Alunos_Academia`. `Cluster_ID` está 100% nula (inutilizável).
- **`Alunos_Academia` com zeros/outliers (min 0, máx 5.276):** decidir no gate se filtra/clipa; documentar.
- **Cabeçalho `Município` vem corrompido (`Munic�pio`, encoding):** ler pelo índice/normalizar o nome; não é chave crítica (coord é a chave).
- **Escopo:** tentação de já recompor `oferta_efetiva_disponivel` — proibido neste bloco (follow-up com gate próprio).

## Guardrails ativos
- **§5 (READ-ONLY sobre o M1):** visualizações/camadas paralelas não podem recalcular ou alterar
  `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou artefatos
  oficiais do M1 sem aprovação explícita. Aqui: **zero** escrita nessa cadeia; mtime dos 4 oficiais inalterado.
- **DEC-012 (anti-PII por construção):** consumir só o agregado por hex; drop Lat/Lng/Nome na fronteira; zero
  PII em artefato/log/teste (`COLUNAS_PII_PROIBIDAS` + `test_zero_pii`); fonte real em `NAO_ABRA/` (gitignored,
  nunca versionada); fixtures sintéticas.
- **DEC-013 (parte 3):** agregadores WellHub/TotalPass devem ser coletados/armazenados com **DEDUP + capacidade
  por tipo ANTES** de qualquer integração ao residual. Este bloco só INGERE + relatório de DEDUP; a integração é epic futura sob gate.
- **DEC-009 (intacta):** demanda/oferta observada entra como insumo, NUNCA como preditor geográfico de magnitude.
- **Isolamento de pacote:** o módulo novo da camada paralela NÃO importa de `pipelines/m1`, `dashboard`, `censo_*`, `api`.
