# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-TP-02 — Validação: Demanda Revelada × Residual Fitness (relatório)**

Script de análise Python que faz o join `demanda_revelada_h3.parquet` × `hexagonos_mercado_mapeado.parquet`
por `hex_id`, calcula Spearman entre `membros` e `score_oportunidade_residual`, gera mapa de quatro
quadrantes e avalia divergências vs. o recorte top-20%/UF do M1. Entregável: relatório Markdown em
`data/reports/` + parquet opcional de quadrantes em `data/staging/` (gitignored, sem PII).

## Objetivo
Reproduzir e documentar a correlação demanda × `score_oportunidade_residual` (Spearman alvo ~+0,52),
o mapa de quadrantes (residual+ & demanda+), e as divergências vs. o recorte top-20%/UF do M1 — sem
alterar nenhum score, artefato ou pipeline oficial.

## Escopo permitido
- Criar módulo de análise em `src/motor_expansao/demanda_revelada/validacao.py` (isolado no pacote disjunto já existente; alternativa `scripts/analise_demanda_vs_residual.py` — Planner decide o local mais limpo).
- Ler (somente leitura) `data/staging/demanda_revelada_h3.parquet` (join principal) e `data/staging/hexagonos_mercado_mapeado.parquet` (alvo da correlação).
- Ler (somente leitura) `data/staging/brasil_priorizados.parquet` para o recorte top-20%/UF.
- Calcular Spearman `membros` × `score_oportunidade_residual` com IC 95% (scipy bootstrap ou normal).
- Calcular Spearman secundário `membros` × `oferta_efetiva_disponivel` (confirmação do sinal já reportado ~+0,75 vs. alunos capturados).
- Gerar mapa de quadrantes: Q1 (residual+ & demanda+), Q2 (residual+ & demanda-), Q3 (residual- & demanda+), Q4 (residual- & demanda-) — mediana como limiar de corte padrão, documentado no relatório.
- Calcular divergências: hexes Q1 (residual+ & demanda+) fora do recorte top-20%/UF; hexes top-20%/UF que caem em Q2–Q4.
- Escrever relatório Markdown reproduzível em `data/reports/demanda_revelada_validacao.md` (versionado — `data/reports/` não é gitignored; apenas `data/reports/scratch/` é ignorado).
- Salvar opcionalmente `data/staging/quadrantes_demanda_residual.parquet` (gitignored por `data/staging/*`; zero PII).
- Adicionar testes unitários para o módulo de análise (fixture sintética, sem dado real).
- Confirmar e marcar loop-safe no backlog ao concluir (critério satisfeito: consome só `data/staging`, sem PII, sem VPS, sem toque no M1).

## Fora de escopo
- Alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou quaisquer artefatos oficiais do M1.
- Recalibrar pesos do M1 (DEC-001 intacta — `renda=0.40`/`pop=0.60` inalterados).
- Usar `membros` ou qualquer coluna da camada de demanda como preditor geográfico de magnitude (DEC-009 intacta).
- Escrever em `pipelines/m1/`, `censo_*` ou `dashboard/`.
- Ingestão ao vivo na carga do dashboard.
- Deploy ao VPS.
- Persistir PII (o parquet de saída herda as garantias anti-PII do BLK-TP-01; só `hex_id` e métricas agregadas).
- Blocos sucessores BLK-TP-03..05.
- Versão res-8 da demanda revelada (adiada por DEC-012).
- Modificar o contrato do `demanda_revelada_h3.parquet` (schema BLK-TP-01 é fixo).

## Arquivos que devem ser lidos
- `src/motor_expansao/demanda_revelada/contrato.py` — 9 colunas canônicas, `VERSAO_CONTRATO`, `COLUNAS_PII_PROIBIDAS`.
- `src/motor_expansao/demanda_revelada/ingestao.py` — estrutura do parquet de saída e lógica de agregação H3.
- `src/motor_expansao/demanda_revelada/__init__.py` — imports públicos do módulo.
- `docs/modelo_mercado_hexagonos.md` — definição exata de `score_oportunidade_residual` (linha ~316: `clip(100 * oferta_efetiva_disponivel / 2500, 0, 100)`) e `oferta_efetiva_disponivel` (linha ~313); localização de `hexagonos_mercado_mapeado.parquet`.
- `tests/unit/test_demanda_revelada_ingestao.py` — padrão de teste existente + fixture sintética.
- `tests/fixtures/demanda_revelada_fake.html` — fixture sintética sem PII (modelo para os novos testes).
- `CLAUDE.md` — §1 (posicionamento low-cost), §4 (camada de mercado/residual, parâmetros), §5 (guardrail permanente), §8 DEC-001/DEC-009/DEC-012.
- `tasks/current_task.md` — estado do ciclo.

## Arquivos que podem ser alterados
- `data/reports/demanda_revelada_validacao.md` — NOVO: relatório principal (versionado).
- `src/motor_expansao/demanda_revelada/validacao.py` — NOVO: módulo de análise (ou `scripts/analise_demanda_vs_residual.py` — Planner decide).
- `data/staging/quadrantes_demanda_residual.parquet` — NOVO opcional (gitignored, zero PII).
- `tests/unit/test_demanda_revelada_validacao.py` — NOVO: testes do módulo de análise.
- `tasks/backlog.md` — atualizar `| **Autonomia** |` de "candidato a loop-safe" para `loop-safe` e marcar status "Concluído" ao fechar.
- `tasks/completed.md` — registrar BLK-TP-02 ao fechar (via `scripts/housekeeping_move_block.py`).
- `tasks/current_task.md` — atualizar estado conforme a esteira avança.
- `context/handoff.md` — sobrescrito por cada skill.
- `context/handoff/` — snapshot append-only por skill.

**NUNCA alterar:**
- `config.py`, `src/motor_expansao/pipelines/m1/`, qualquer artefato oficial do M1.
- `src/motor_expansao/demanda_revelada/contrato.py` e `ingestao.py` (contrato BLK-TP-01 congelado).
- `data/staging/demanda_revelada_h3.parquet`, `hexagonos_mercado_mapeado.parquet`, `brasil_priorizados.parquet` (leitura apenas).

## Critérios de aceite
1. **Spearman reproduzido:** `membros` × `score_oportunidade_residual` calculado com IC 95% e documentado no relatório (valor esperado ~+0,52; tolerância ±0,05 dado arredondamento de coords ~1 km).
2. **Spearman secundário:** `membros` × `oferta_efetiva_disponivel` calculado e documentado (valor esperado ~+0,75).
3. **Quadrantes definidos:** 4 quadrantes com limiar explícito (mediana documentada), contagem de hexes por quadrante, e lista dos hexes Q1 mais relevantes (top-N por `membros`).
4. **Divergências vs M1:** tabela ou contagem de hexes Q1 fora do top-20%/UF e vice-versa; pelo menos uma hipótese de causa registrada (ex.: concentração em SP, hexes costeiros de baixa pop).
5. **Caveats documentados:** cobertura ~1% do universo (~16.575 hexes), concentração em SP, arredondamento de coords ~1 km, join parcial (left join — universo de mercado muito maior que o de demanda revelada).
6. **READ-ONLY M1 verificado:** nenhuma linha escreve em artefato oficial; `score_priorizacao` é lido apenas para filtrar top-20%/UF, nunca recalculado.
7. **Anti-PII:** parquet de quadrantes (se gerado) contém apenas `hex_id` e métricas agregadas; zero coluna de `COLUNAS_PII_PROIBIDAS`.
8. **Loop-safe confirmado:** linha `| **Autonomia** |` em `tasks/backlog.md` atualizada para `loop-safe`.
9. **Suíte verde:** `pytest -q` sem novas falhas; `ruff check` e `mypy src/` limpos.

## Criticidade classificada
**Média** (relatório/análise READ-ONLY sobre o M1; sem gate humano obrigatório).

## Esteira recomendada
Block Orchestrator → **Planner** → Builder → QA (opus 4.8)

Tiering de modelo (Média, conforme `tasks/current_task.md`):
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre, sem exceção)

## Riscos identificados
1. **Cobertura parcial (risco principal):** `demanda_revelada_h3.parquet` cobre ~16.575 hexes (~1% do universo de 1.542.531); o join é massivamente assimétrico. A correlação é válida apenas sobre o subconjunto coberto — registrar explicitamente no relatório.
2. **Arredondamento de coords:** células da fonte têm resolução ~1 km → ruído no join H3 res-7. Citar como caveat; não corrigir no BLK-TP-02.
3. **`hexagonos_mercado_mapeado.parquet` pode não existir localmente** (gitignored — `data/staging/*`). O Builder deve verificar antes de rodar; se ausente, documentar e emitir instrução de regeneração (ordem canônica: `híbrido → mercado → calcular_colunas_mercado → ...`).
4. **Limiar dos quadrantes:** escolha de mediana vs. outro percentil afeta volume de Q1. Documentar e justificar a escolha no relatório.
5. **Escorregamento de escopo:** não usar `membros` como ajuste do `score_priorizacao` — viola DEC-009. Registrar a proibição no relatório.
6. **Dependência de scipy:** verificar se `scipy` já está nas dependências antes de importar. Se ausente, adicionar ao `[dev]` (nunca ao extra de deploy).

## Guardrails ativos
- **§5 guardrail permanente (CLAUDE.md):** análises NÃO podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou artefatos oficiais do M1.
- **DEC-001:** pesos `renda=0.40`/`pop=0.60` INALTERADOS. Não recalibrar M1.
- **DEC-009 (intacta):** a demanda entra como insumo OBSERVADO, NUNCA como preditor geográfico de magnitude. Proibido usar `membros` em regressão geográfica de demanda ou como ajuste do `score_priorizacao`.
- **DEC-012:** camada paralela READ-ONLY sobre o M1; `src/motor_expansao/demanda_revelada/` é pacote disjunto — NUNCA importa de `pipelines/m1/`, `censo_*` ou `dashboard/`.
- **Anti-PII por construção:** `COLUNAS_PII_PROIBIDAS` não pode aparecer em nenhum artefato de saída.
- **Loop-safe (confirmar ao concluir):** BLK-TP-02 é candidato a loop-safe — consome só `data/staging`, sem PII, sem VPS, sem toque no M1. Builder confirma e marca no backlog.
