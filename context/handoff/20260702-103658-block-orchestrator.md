# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (com gate humano obrigatório de produto/UX antes do Builder — ver bifurcação A/B abaixo)

## Bloco refinado
BLK-TP-03 — Vazio competitivo do concorrente low-cost (feature/overlay)

## Objetivo
Identificar e materializar a lista de hexes H3 res-7 com demanda paga observada relevante a >5 km do concorrente low-cost de referência E sem unidade dele no hex — "tese de entrada low-cost mais limpa" — como parquet reproduzível e, dependendo de decisão de produto (gate humano), como overlay no Mapa Territorial do dashboard.

## Fórmula canônica do "vazio competitivo" (nomes exatos do contrato `demanda_revelada_v1`)

Colunas usadas, lidas de `data/staging/demanda_revelada_h3.parquet` (contrato em `src/motor_expansao/demanda_revelada/contrato.py`):

| Coluna | Tipo | Papel no filtro |
|---|---|---|
| `hex_id` | string | chave de join com o Motor |
| `membros` | int64 | demanda paga total no hex (filtro de relevância mínima) |
| `membros_gt5km_concorrente_lc` | int64 | demanda paga de pessoas a >5 km do concorrente LC — sinal principal do "vazio" |
| `dist_concorrente_lc_min_m` | float64 | distância ao concorrente LC mais próximo no hex (metros) |
| `n_concorrente_lc` | int64 | unidades do concorrente LC DENTRO do hex |

**Critério candidato de "vazio competitivo" (a confirmar/calibrar no Planner):**

```python
flag_vazio_competitivo = (
    (n_concorrente_lc == 0)                        # sem concorrente LC no próprio hex
    & (dist_concorrente_lc_min_m > 5_000)          # distância mínima ao LC vizinho > 5 km
    & (membros_gt5km_concorrente_lc >= LIMIAR_MEMBROS_GT5KM)  # demanda expressiva a >5 km
)
```

`LIMIAR_MEMBROS_GT5KM` é parâmetro a calibrar no Planner — o protótipo exploratório encontrou ~231 hexes candidatos; o Planner deve confirmar o limiar que reproduz essa ordem de grandeza ou justificar outro valor.

Atenção: `dist_concorrente_lc_min_m` pode ser `NaN` para hexes onde nenhuma célula tinha distância válida ao concorrente LC. O Planner deve decidir se NaN é tratado como "muito longe" (inclui no vazio) ou "dado ausente" (exclui). Decisão a registrar no plano.

**Colunas adicionais úteis para o artefato de saída** (join por `hex_id` com `brasil_estrutural.parquet` ou `hexagonos_mercado_mapeado.parquet`):
- `uf`, `nome_municipio`, `lat`, `lng` (localização)
- `score_priorizacao` (LIDO — READ-ONLY; permite ranquear vazios por atratividade M1)
- `oferta_efetiva_disponivel` (residual fitness; contexto de mercado)

## Bifurcação de produto — gate humano obrigatório antes do Builder

O bloco exige decisão humana entre duas opções antes que o Builder possa trabalhar:

### Opção A — Somente lista/parquet reproduzível (sem overlay no dashboard)
**Entregável:** `data/staging/vazios_competitivos_lc.parquet` (gitignored) com colunas do vazio + enriquecimento mínimo (uf/cidade/score_priorizacao). Função reproduzível em `src/motor_expansao/demanda_revelada/`.

**Vantagens:**
- Escopo mínimo; zero risco de impacto no dashboard em produção.
- Pode ser marcado `loop-safe` (sem dashboard, sem deploy).
- Artefato pronto para análise exploratória (planilha, ClickUp, Telegram/API).
- Merge mais rápido; menor superfície de teste.

**Desvantagens:**
- Não visível no dashboard sem segundo bloco futuro (overlay como bloco sucessor separado).
- Operador precisa de acesso ao parquet para usar a análise.

### Opção B — Lista/parquet + overlay no Mapa Territorial do dashboard
**Entregável:** idem A + nova camada visual no dashboard (ex.: hexes destacados em cor distinta no modo M1/Residual, ou toggle "Vazio LC" na sidebar).

**Vantagens:**
- Análise imediatamente operacionalizável no dashboard.
- Integração com a UX existente (sidebar + mapa já têm layers de concorrente).

**Desvantagens:**
- Toca `src/motor_expansao/dashboard/` — exige cuidado com o guardrail §5 (overlay não pode alterar score/ranking/carteira/plano/artefatos).
- Mais complexo: precisa de decisão de UX (cor, toggle, tooltip, compatibilidade com os 4 modos do mapa — M1/Hibrido/Censitario/Residual — e com `_downsample_map_index`/`MAP_POINT_LIMIT`/`MAP_SOURCE_COLUMNS_*` em `constants.py`).
- NÃO pode ser loop-safe.
- Aumenta superfície de teste de integração.

**Recomendação Block Orchestrator:** iniciar com Opção A (parquet) e tratar Opção B como bloco sucessor (BLK-TP-03-FU1), permitindo que o ciclo feche mais rápido e o gate de UX aconteça com o parquet já disponível como insumo visual.

## Escopo permitido

- Ler `data/staging/demanda_revelada_h3.parquet` (gerado pelo BLK-TP-01).
- Join por `hex_id` com `data/staging/brasil_estrutural.parquet` e/ou `hexagonos_mercado_mapeado.parquet` para enriquecimento de localização/score (READ-ONLY sobre esses parquets).
- Criar módulo em `src/motor_expansao/demanda_revelada/vazios_competitivos.py` (nome sugerido) com função que aplica o filtro e grava `data/staging/vazios_competitivos_lc.parquet` (gitignored).
- Testes com fixture sintética (zero dado real em testes); reusar ou estender `tests/fixtures/demanda_revelada_fake.html` ou criar fixture nova para o módulo de vazios.
- Se Opção B aprovada no gate humano: adicionar camada visual READ-ONLY em `src/motor_expansao/dashboard/` (sem alterar score nem artefatos oficiais).
- Atualizar housekeeping de ciclo: `tasks/backlog.md`, `tasks/completed.md`, `tasks/current_task.md`, `context/handoff.md`, `context/handoff/`.

## Fora de escopo

- Recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, pesos (`renda=0.40`/`pop=0.60`) ou qualquer artefato oficial do M1 (`brasil_estrutural.parquet`, `brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet`, `hexagonos_brasil_dashboard.parquet`, etc.).
- Alterar `flag_sam`, `oferta_efetiva_disponivel`, `sam_fitness_potencial` ou qualquer campo do pipeline de mercado (`calcular_colunas_mercado.py`).
- Tocar o pipeline de ingestão da Demanda Revelada (`ingestao.py`, `contrato.py`) — consumir o parquet já gerado, não regerar.
- Importar de `pipelines/m1/`, `censo_*` ou `dashboard/` a partir do pacote `demanda_revelada/`.
- Usar dados reais em testes (fonte em `NAO_ABRA/`, gitignored).
- Deploy ao VPS.
- Dependência de API ao vivo.
- Persistir PII em qualquer artefato, log ou teste.
- Versão res-8 da Demanda Revelada (adiada, fora deste bloco).
- Qualquer análise dos blocos BLK-TP-02/04/05 (já concluídos ou em backlog próprio).
- Overlay no dashboard SE o gate humano escolher Opção A (overlay fica para bloco sucessor).

## Arquivos que devem ser lidos

- `src/motor_expansao/demanda_revelada/contrato.py` — contrato canônico das 9 colunas (nomes exatos para o filtro)
- `src/motor_expansao/demanda_revelada/ingestao.py` — como o parquet foi gerado (contexto de origem dos dados)
- `src/motor_expansao/demanda_revelada/__init__.py` — exports existentes do pacote (para adicionar o novo módulo)
- `src/motor_expansao/demanda_revelada/backtest_tp05.py` — padrão de módulo disjunto no mesmo pacote (reusar estilo)
- `tests/unit/test_backtest_tp05.py` — padrão de teste sintético do pacote (reusar estrutura)
- `tests/fixtures/demanda_revelada_fake.html` — fixture sintética existente (verificar se serve para o novo módulo)
- `docs/modelo_mercado_hexagonos.md` — contrato de `hexagonos_mercado_mapeado.parquet` e `brasil_estrutural.parquet` (colunas de join e enriquecimento)
- `CLAUDE.md` — §1/§2/§4/§5, DEC-012 (anti-PII), DEC-014 (guardrails ativos)
- `tasks/backlog.md` — bloco BLK-TP-03 (linha ~877) para coletar critérios de aceite originais

## Arquivos que podem ser alterados

**Sempre (housekeeping de ciclo):**
- `tasks/backlog.md` — marcar BLK-TP-03 concluído
- `tasks/completed.md` — registrar resultado
- `tasks/current_task.md` — atualizar estado
- `context/handoff.md` e `context/handoff/AAAAMMDD-HHMMSS-*.md`

**Código (escopo do ciclo):**
- `src/motor_expansao/demanda_revelada/vazios_competitivos.py` (novo — módulo a criar)
- `src/motor_expansao/demanda_revelada/__init__.py` — adicionar exports do novo módulo
- `tests/unit/test_vazios_competitivos.py` (novo — testes sintéticos)
- Se Opção B aprovada no gate humano: `src/motor_expansao/dashboard/components.py` e/ou `src/motor_expansao/dashboard/pages.py` (overlay visual READ-ONLY)

**Nunca alterar (guardrail absoluto):**
- `config.py`, `src/motor_expansao/pipelines/m1/**`, qualquer artefato oficial do M1
- `src/motor_expansao/demanda_revelada/contrato.py`, `ingestao.py` (consumir, não editar)
- `src/motor_expansao/dashboard/` — exceto se Opção B aprovada no gate humano

## Critérios de aceite

1. `data/staging/vazios_competitivos_lc.parquet` é gerado a partir de `demanda_revelada_h3.parquet` com `flag_vazio_competitivo` e colunas de localização/score; arquivo reproduzível (mesmo input → mesmo output, ordem determinística).
2. O filtro aplica as 3 condições com nomes exatos do contrato (`n_concorrente_lc == 0`, `dist_concorrente_lc_min_m > 5000`, `membros_gt5km_concorrente_lc >= LIMIAR`) — zero coluna inventada fora do contrato.
3. Zero PII no artefato de saída: nenhuma coluna de `COLUNAS_PII_PROIBIDAS` presente (verificado por teste automatizado).
4. Os testes rodam com fixture sintética apenas — nenhum teste acessa `NAO_ABRA/` nem o parquet real.
5. Módulo novo em `demanda_revelada/` NÃO importa de `pipelines/m1/`, `censo_*` nem `dashboard/` (verificável por `import` estático no módulo ou `grep import`).
6. `mtime` de todos os artefatos oficiais do M1 INALTERADO após o ciclo (verificado no QA).
7. Contagem de hexes candidatos reportada no `completed.md` (comparar com o protótipo ~231 hexes como sanity check; divergência aceitável com justificativa de limiar).
8. Se Opção B aprovada: overlay não altera `score_priorizacao`, `carteira`, `plano` nem qualquer campo de score; é layer visual de apoio (CLAUDE.md §2); testes de integração do dashboard cobrem o novo toggle/layer.
9. Suíte FULL (`pytest -n auto` ou serial em caso de WinError 6) passa sem falhas; ruff limpo; mypy 0 issues no escopo alterado; `import streamlit_app` ok.

## Criticidade classificada
Média (camada de visualização/análise — READ-ONLY sobre o M1; sem modelagem; sem PII nova; sem toque em score/pesos/artefatos)

## Esteira recomendada
Block Orchestrator (este handoff) → **Planner** → **[REVISÃO HUMANA — produto/UX: Opção A vs B]** → Builder → QA (Opus 4.8)

## Tiering de modelo (conforme tasks/current_task.md)
- Block Orchestrator: sonnet
- Planner: opus (override +1 justificado: gate de produto/UX overlay-vs-parquet + guardrails anti-PII DEC-012)
- Builder: sonnet
- QA: opus 4.8 (sempre, sem override para baixo)

## Riscos identificados

1. **Limiar `LIMIAR_MEMBROS_GT5KM` não fixado:** o Planner deve calibrar o limiar que reproduz os ~231 hexes do protótipo ou justificar outra escolha. Risco de zero hexes (limiar alto demais) ou lista trivialmente grande (limiar zero).
2. **Cobertura geográfica da Demanda Revelada é ~1% do universo do Motor (concentrada em SP):** os vazios competitivos também refletirão esse viés. Documentar explicitamente no relatório para não criar expectativa de cobertura nacional.
3. **Ruído de coordenadas (~1 km) na agregação H3 res-7:** um hex pode ter `n_concorrente_lc == 0` mas haver LC a ~800 m (fora do hex mas perto). A precisão é hex-a-hex (~1,2 km de lado), não de metro. Documentar no `completed.md`.
4. **`dist_concorrente_lc_min_m` pode ser `NaN`:** para hexes onde nenhuma célula tinha distância válida ao SF. O Planner deve definir o tratamento (incluir ou excluir) e registrar no plano.
5. **Se Opção B:** overlay no dashboard aumenta superfície de teste de integração; verificar compatibilidade com `_downsample_map_index`, `MAP_POINT_LIMIT` e `MAP_SOURCE_COLUMNS_*` em `constants.py` ANTES de implementar, para evitar regressão nos 4 modos do mapa.

## Guardrails ativos

- **§5 (READ-ONLY M1, guardrail permanente):** visualizações, análise e overlays NÃO recalculam nem alteram `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou artefatos oficiais do M1. Pins/camadas de concorrente são apoio visual (CLAUDE.md §2).
- **DEC-012 (anti-PII por construção):** consumir APENAS `demanda_revelada_h3.parquet` (já agregado); zero PII em artefato/log/cache/teste; fonte real em `NAO_ABRA/` (gitignored); testes com fixture sintética; `COLUNAS_PII_PROIBIDAS` do contrato como rede de segurança automatizada.
- **DEC-001 (pesos M1 inalterados):** `renda=0.40`/`pop=0.60`, `score_priorizacao`, `hex_score_estrutural` — NÃO recalibrar.
- **§2 (sem API ao vivo):** nenhuma dependência de rede na carga/interatividade do dashboard.
- **Isolamento do pacote `demanda_revelada/`:** NÃO importar de `pipelines/m1/`, `censo_*`, `dashboard/` core do M1.
- **Autonomia (CLAUDE.md §6.1):** loop-safe APENAS se Opção A aprovada E restrito a análise/parquet (sem dashboard). Se Opção B: manual, NÃO loop-safe.
