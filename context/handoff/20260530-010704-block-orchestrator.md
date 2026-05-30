# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Campos de controle
- Skill atual: Block Orchestrator
- Próxima Skill: Planner

## Cabeçalho do ciclo
- Bloco: **BLK-ARCH-01b — Tipar os 14 módulos migrados e remover o override de mypy**
- Criticidade: **Média**
- Esteira: Block Orchestrator → Planner → Builder → QA (criticidade média, SEM aprovação humana / sem gate humano)
- Dependência BLK-ARCH-01a: ✅ satisfeita (já mergeada em `main`; branch `ciclo/BLK-ARCH-01b` criado a partir do HEAD de main)
- Branch ativo: `ciclo/BLK-ARCH-01b`

## Bloco refinado
Corrigir os ~50 erros de tipo latentes (em 12 dos 14 módulos) de
`src/motor_expansao/pipelines/` atualmente silenciados pelo bloco
`[[tool.mypy.overrides]]` (`ignore_errors = true`) em `pyproject.toml`, e remover esse
override por completo — trazendo os 14 módulos ao gate real `mypy src/`. A correção é
mecânica de tipagem (anotações refletindo o tipo REAL em runtime); NÃO muda
comportamento, valores, score nem artefatos do M1.

## Objetivo
Eliminar a dívida de tipagem dos 14 módulos migrados e remover o override de mypy, com não-mutação dos artefatos M1 provada por hash sha256 idêntico pré/pós.

## Classificação confirmada e justificativa
- Criticidade classificada: **Média**.
- Por que NÃO Crítica: este bloco NÃO toca `core/scoring.py`, `score_priorizacao`,
  `hex_score_estrutural`, pesos do score, carteira, plano curto prazo, plano de domínio
  nem qualquer cálculo oficial do M1. É correção mecânica de tipos (anotações), sem
  alteração de lógica ou de valores. O guardrail do CLAUDE.md/spec que força CRÍTICA só
  dispara quando o bloco ENVOLVE esses artefatos/cálculos — não é o caso. A não-mutação é,
  ainda assim, critério de aceite duro (hash sha256 idêntico pré/pós nos 4 artefatos).
- Por que NÃO Baixa: mexe em 12-14 módulos de pipeline (incluindo os de Fase A do Censo e
  penetração Ultra), com risco de, ao "consertar tipos", introduzir mudança de
  comportamento por descuido (ex.: cast que altera valor, reordenação, troca de dtype) ou
  de mascarar um bug latente com uma anotação errada. Daí o gate de hash + pytest + ruff.

## Escopo permitido
- Adicionar/ajustar anotações de tipo nos 14 módulos listados, refletindo o tipo real em runtime.
- `# type: ignore[code]` pontual e justificado APENAS onde lib de terceiros não tem stub (não em massa).
- Remover do `pyproject.toml` cada módulo do bloco `[[tool.mypy.overrides]]` conforme fica limpo, até remover o bloco inteiro.
- Ajustes mínimos em testes SOMENTE se uma anotação correta exigir (ex.: type narrowing), preservando o comportamento testado.
- Atualizar arquivos de controle do ciclo (`tasks/*.md`, `context/handoff.md`, `context/handoff/`).

## Fora de escopo
- Qualquer alteração de comportamento, valores, dtypes de saída ou ordenação dos dados.
- Tocar em `core/scoring.py`, `score_priorizacao`, `hex_score_estrutural`, pesos do score, carteira, plano curto prazo, plano de domínio ou artefatos oficiais do M1.
- `# type: ignore` em massa / blanket ignores; relaxar configuração global de mypy.
- Refatoração arquitetural, renomeação de funções/colunas, mudança de assinaturas públicas além do necessário para tipagem.
- Avançar para outro bloco ou resolver múltiplos blocos.

## Os 14 módulos (todos em `src/motor_expansao/pipelines/`)
1. `calcular_colunas_mercado.py`
2. `calcular_penetracao_ultra_hex.py`
3. `comparar_geofusion_vs_hex.py`
4. `enriquecimento_espacial_hexagonos.py`
5. `normalizar_unidades_ultra.py`
6. `gerar_carteira_acionavel.py`
7. `modelo_hibrido_expansao.py`
8. `validar_modelo_ultra.py`
9. `validar_penetracao_ultra_hex.py`
10. `materializar_setores_censitarios_geo.py`
11. `fase_a_censo2022_setores.py`
12. `validar_fase_a_censo2022.py`
13. `fase_a_piloto_expandido.py`
14. `fase_a_nacional_completo.py`

Localização do override: `pyproject.toml`, bloco `[[tool.mypy.overrides]]` com
`ignore_errors = true` (linhas 107-124) listando EXATAMENTE estes 14 módulos.

## Panorama de erros de tipo apurado
- **Contagem confiável (do QA de BLK-ARCH-01a):** removendo o override e rodando
  `mypy src/` → **`Found 50 errors in 12 files (checked 44 source files)`**. Os 12 arquivos
  com erro são TODOS subconjunto dos 14 do override (zero erro em `m1/`, dashboard, core,
  constants — esses permanecem checados e limpos). Natureza dos erros é típica de legado
  nunca-checado, NÃO de migração quebrada (zero "module not found"/import quebrado).
- **Nota metodológica para o recon:** rodar `python -m mypy <arquivo>.py ...` apontando os
  14 por caminho retornou `Success: no issues found in 14 source files`. Isso NÃO contradiz
  os 50 erros — com a override ativa (ou pela forma como o mypy resolve módulos por path +
  `ignore_missing_imports`), os erros não aparecem; a forma fidedigna de revelá-los é o que
  o QA de 01a fez: **remover o bloco de override e rodar `mypy src/`**. O Planner/Builder
  devem usar exatamente esse procedimento (backup/restore do `pyproject.toml` ou edição
  temporária) para enumerar e categorizar os 50 erros por módulo/linha.

### Amostras concretas de erro (do QA de BLK-ARCH-01a — sem override)
```
normalizar_unidades_ultra.py:158: error: Argument 1 to "float" has incompatible type "object" [arg-type]
gerar_carteira_acionavel.py:146:  error: Argument 1 to "float" has incompatible type "object" [arg-type]
validar_modelo_ultra.py:265:      error: Need type annotation for "resultados" [var-annotated]
modelo_hibrido_expansao.py:102:   error: Argument 1 to "float" has incompatible type "float | None" [arg-type]
enriquecimento_espacial_hexagonos.py:134: error: No overload variant of "where" matches [call-overload]
materializar_setores_censitarios_geo.py:29: error: Name "ajuste_executivo" already defined (possibly by an import) [no-redef]
```

### Categorias dominantes (confirmadas)
- `arg-type` — `float(object)` / `float(float | None)` sobre células de DataFrame (mais frequente).
- `var-annotated` — variável acumuladora sem anotação (ex.: `resultados`).
- `call-overload` — overloads numpy (`np.where`, etc.).
- `no-redef` — redefinição por fallback `try/except import` (ex.: `ajuste_executivo`).

## Estratégia sugerida (corrigir em grupos pequenos)
Corrigir em lotes coesos, removendo cada módulo do override assim que ficar limpo no
`mypy`, até remover o bloco `[[tool.mypy.overrides]]` inteiro. Sugestão de agrupamento por
afinidade de domínio (menor superfície de revisão e menor risco de regressão):
1. **Trio Fase A**: `fase_a_censo2022_setores`, `fase_a_piloto_expandido`, `fase_a_nacional_completo` (+ `validar_fase_a_censo2022` se compartilhar helpers).
2. **Geo censitário**: `materializar_setores_censitarios_geo` (atenção ao `no-redef` de `ajuste_executivo` por fallback import).
3. **Dupla penetração**: `calcular_penetracao_ultra_hex`, `validar_penetracao_ultra_hex`.
4. **Mercado/enriquecimento**: `calcular_colunas_mercado`, `enriquecimento_espacial_hexagonos` (`call-overload` de numpy), `comparar_geofusion_vs_hex`.
5. **Ultra/carteira/híbrido/validação**: `normalizar_unidades_ultra`, `gerar_carteira_acionavel`, `modelo_hibrido_expansao`, `validar_modelo_ultra` (concentram os `arg-type` de `float(object)`).
6. Após cada lote: rodar `mypy src/` (sem as entradas removidas), `pytest -q` e `ruff check .`; ao final remover o bloco `[[tool.mypy.overrides]]` por completo e confirmar `mypy src/` limpo + hashes M1 idênticos.

## Arquivos que devem ser lidos
- `CLAUDE.md` (seções 1, 2, 3, 5 — guardrails e fontes canônicas)
- `pyproject.toml` (bloco `[[tool.mypy.overrides]]`, linhas 107-124; e config global de mypy)
- Os 14 módulos em `src/motor_expansao/pipelines/` listados acima
- `tasks/current_task.md` e a seção `### BLK-ARCH-01b` de `tasks/backlog.md`
- Testes relacionados aos pipelines (em `tests/`) para preservar comportamento ao tipar

## Arquivos que podem ser alterados (commit por path — NUNCA `git add -A`)
- `src/motor_expansao/pipelines/calcular_colunas_mercado.py`
- `src/motor_expansao/pipelines/calcular_penetracao_ultra_hex.py`
- `src/motor_expansao/pipelines/comparar_geofusion_vs_hex.py`
- `src/motor_expansao/pipelines/enriquecimento_espacial_hexagonos.py`
- `src/motor_expansao/pipelines/normalizar_unidades_ultra.py`
- `src/motor_expansao/pipelines/gerar_carteira_acionavel.py`
- `src/motor_expansao/pipelines/modelo_hibrido_expansao.py`
- `src/motor_expansao/pipelines/validar_modelo_ultra.py`
- `src/motor_expansao/pipelines/validar_penetracao_ultra_hex.py`
- `src/motor_expansao/pipelines/materializar_setores_censitarios_geo.py`
- `src/motor_expansao/pipelines/fase_a_censo2022_setores.py`
- `src/motor_expansao/pipelines/validar_fase_a_censo2022.py`
- `src/motor_expansao/pipelines/fase_a_piloto_expandido.py`
- `src/motor_expansao/pipelines/fase_a_nacional_completo.py`
- `pyproject.toml` (remover o override)
- (eventuais testes tocados) em `tests/`
- `tasks/current_task.md`, `tasks/backlog.md`, `tasks/completed.md`
- `context/handoff.md`, `context/handoff/`

## Critérios de aceite (para o QA)
- `mypy src/` limpo COM o bloco `[[tool.mypy.overrides]]` REMOVIDO (sem o override).
- `pytest -q` verde (baseline atual ~541 passed, 1 skipped).
- `ruff check .` limpo.
- Hash **sha256 idêntico pré/pós** em:
  - `data/staging/brasil_priorizados.parquet`  (esperado: `c226954945ad0757a0429c84c43f410492c0ea7d15ca1d9b6a15f68727806567`)
  - `data/staging/brasil_estrutural.parquet`   (esperado: `7baa07a2cbc0b7d8f2a8878932cae0ebf9400fce00e9c48c366c9903215f131b`)
  - `data/staging/hexagonos_brasil_oportunidades.parquet` (esperado: `805c65e28adfd800c7d5524e73fa9b0a044b992f17d617d0f2c6e40f9bbf61ca`)
  - `data/outputs/hexagonos_brasil_dashboard.parquet` (esperado: `0cfb1015fc9df8b63776eb07ae3e666766905f768a4a78a406ae4d6b7cb6f618`)
  (hashes acima são os registrados pelo QA de BLK-ARCH-01a; Builder deve recapturar no Passo 0 e comparar pré/pós deste ciclo)
- Bloco `[[tool.mypy.overrides]]` (os 14 módulos) REMOVIDO do `pyproject.toml`.

## Criticidade classificada
Média

## Esteira recomendada
Block Orchestrator → Planner → Builder → QA (sem gate humano)

## Riscos identificados
- "Consertar tipos" introduzir mudança de comportamento silenciosa (cast que altera valor,
  troca de dtype, narrowing que muda fluxo). Mitigação: gate de hash sha256 + `pytest -q`.
- Anotação errada MASCARAR um bug latente em vez de revelá-lo. Mitigação: anotação deve
  refletir o tipo REAL em runtime; manter `pytest -q` verde; revisar cada `arg-type` de
  `float(object)` entendendo de onde vem o valor.
- Tentação de `# type: ignore` em massa para fechar rápido o gate. Mitigação: só
  `# type: ignore[code]` pontual e justificado onde a lib de terceiros não tem stub.
- pandas/geopandas/numpy/pyarrow sem stubs completos → erros que exigem anotação explícita
  em vez de ignore. Lembrar da lição de paridade mypy CI vs local (instalar stubs
  necessários — ex.: `pandas-stubs`, `types-*` — antes de validar localmente, senão falso verde).
- Remover o módulo do override antes de estar 100% limpo quebraria `mypy src/`. Mitigação:
  remover entrada só após o módulo passar isolado.
- Recon: para enumerar os 50 erros é PRECISO remover/comentar temporariamente o override e
  rodar `mypy src/` (apontar arquivos por path mascara os erros). Restaurar antes de commitar parcial.

## Guardrails ativos (do CLAUDE.md)
- Visualizações, análise radial, refator e qualquer mudança paralela NÃO podem recalcular
  nem alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo,
  plano de domínio ou artefatos oficiais do M1 sem aprovação explícita.
- Ler o repositório real antes de editar; `config.py`, `CLAUDE.md` e `PRD.md` são fontes canônicas.
- Toda mudança relevante entra com teste; nenhum PR sobe com CI quebrado.
- Preservar 100% das linhas e colunas oficiais do M1 ao tocar camadas paralelas.
- Commit por path; NUNCA `git add -A`.

## Notas operacionais desta execução
- Recon executado. `python -m mypy` por caminho nos 14 arquivos retornou
  `Success: no issues found in 14 source files` (não-fidedigno com override ativo). A
  contagem confiável vem do QA de BLK-ARCH-01a (override removido + `mypy src/`):
  **50 erros em 12 dos 14 módulos**. Nenhum arquivo de código nem o `pyproject.toml` foi
  alterado pelo Block Orchestrator — único output é este handoff (2 cópias).
