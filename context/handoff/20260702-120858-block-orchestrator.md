# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-RELMUN-03 — Validar hexágono só por Residual Fitness (remover o filtro de SAM Fitness) no
Relatório Municipal.

## Objetivo
Remover o termo de SAM Fitness (`sam_fitness_potencial >= 3000`) de `_hex_destacado_mask` em
`src/motor_expansao/dashboard/relatorio_municipal.py`, deixando o critério de hexágono
destacado/válido como somente `oferta_efetiva_disponivel >= 2000` (OFERTA_DESTAQUE_MIN),
propagando a mudança para todos os textos/legendas/testes que citam o critério e registrando
emenda à DEC-011.

## Escopo permitido
- Editar `_hex_destacado_mask` (linha ~258-264) em `relatorio_municipal.py`: remover o termo
  `(sam >= SAM_DESTAQUE_MIN) &`, mantendo só `oferta >= OFERTA_DESTAQUE_MIN`.
- Decidir (no gate humano) se `SAM_DESTAQUE_MIN` é removida do módulo ou mantida como constante
  inerte/não usada; ambas as opções ficam disponíveis ao Planner para levar ao gate — não decidir
  sozinho.
- Atualizar TODOS os textos que citam o critério antigo (achados nesta leitura, todos em
  `relatorio_municipal.py`):
  - Docstring do módulo, bloco "Decisoes do gate humano ... D1" (linhas ~9-12).
  - Comentário acima das constantes (linhas ~46-51).
  - Docstring/comentário de `_hex_destacado_mask` (linha ~259) e de `_zonas_geometricas`
    (linhas ~463-464, cita "sam_fitness_potencial>=3000 E oferta_efetiva_disponivel>=2000").
  - Nota de rodapé da página "Potencial de Entrada" (linhas ~1610-1614): "As paginas seguintes
    consideram apenas as N regioes aprovadas (SAM Fitness >= 3.000 e Residual Fitness >= 2.000)."
  - Nota de rodapé/legenda da página "Resumo da Regiao" (linhas ~1666-1671): "Hexagono
    considerado quando SAM Fitness >= 3.000 e Residual Fitness >= 2.000 (alunos)."
  - Qualquer outra ocorrência textual de "SAM Fitness" ligada ao critério de destaque (buscar por
    `SAM_DESTAQUE_MIN`/"SAM Fitness" no arquivo inteiro antes de fechar — a varredura desta sessão
    cobriu as ocorrências citadas acima, mas o Builder deve confirmar exaustividade com grep).
- Atualizar `tests/unit/test_relatorio_municipal.py`:
  - `test_pdf_municipal_8_paginas_e_secoes` (linhas ~325-327): as asserções literais
    `b"SAM Fitness >= 3.000"` / `b"Residual Fitness >= 2.000"` precisam refletir o novo texto
    (só Residual Fitness).
  - Docstring/comentário de `_sample_df` (linha 47: "2 destacados (sam>=3000 & oferta>=2000)")
    e de `test_agregar_municipio_formula_espaco_d1` (linha ~121: mesmo texto) — atualizar para
    "oferta>=2000" apenas.
  - **Nota de risco de dados:** na fixture `_sample_df` atual, os 2 hexes destacados têm
    `sam_fitness_potencial=4000` E `oferta_efetiva_disponivel=4451` (ambos acima dos limiares) e
    os 2 não-destacados têm `sam=1000` E `oferta=500` (ambos abaixo) — os dois limiares se movem
    juntos nessa fixture, então `n_hex_amarelos`/`espaco_para_academias` provavelmente NÃO mudam
    de valor numérico com a remoção do termo SAM. Se o Planner/Builder quiser um teste que prove
    de fato que o filtro de SAM foi removido (ex.: hex com `sam<3000` mas `oferta>=2000` agora
    conta como destacado), precisa adicionar um caso novo à fixture ou um teste dedicado — decidir
    explicitamente se isso entra no escopo (recomendado, para não deixar a mudança sem cobertura
    que a distinga do comportamento antigo).
  - Verificar as demais funções que dependem de `_hex_destacado_mask`
    (`_zonas_geometricas`, `_focus_bounds_mercator`, `agregar_municipio`,
    `_render_camada_mapa`/render de hexes amarelos) por efeito cascata nos testes existentes
    (todas centralizadas nessa única função — baixo risco de divergência, mas conferir).
- Registrar **emenda à DEC-011** em `CLAUDE.md` §8 (seguir o padrão das emendas já existentes na
  DEC-010/DEC-014: bloco "Emenda AAAA-MM-DD (BLK-RELMUN-03, APROVADA por ...)" dentro da própria
  DEC-011, documentando: critério antigo → novo, motivo, e que é mudança de DISPLAY local ao
  Relatório Municipal, sem tocar `flag_sam`/M1).
- Atualizar `tasks/backlog.md` (status do bloco BLK-RELMUN-03), `tasks/current_task.md` e
  `tasks/completed.md` ao fechar o ciclo (fluxo padrão da esteira).

## Fora de escopo
- `flag_sam` / gate do SAM no pipeline de mercado (`calcular_colunas_mercado.py`, DEC-006/DEC-007)
  — o critério do relatório é DISPLAY local e NÃO deve tocar o pipeline de mercado.
- `score_priorizacao`, `hex_score_estrutural`, pesos, carteira, plano curto prazo, plano de
  domínio, artefatos oficiais do M1 (§5 guardrail permanente).
- Relatório Pontual Censitário (raio 1,5 km) — não tem esse filtro; fora de escopo confirmado por
  Vinicius.
- Método de intersecção/raio, tiles/basemap (D3 da DEC-011), páginas/estrutura do PDF além do
  texto do critério, marca d'água anti-PII, `set_compression(False)`.
- Qualquer alteração na contagem/estrutura de páginas do PDF (ver risco abaixo sobre "8 vs 9
  páginas").

## Arquivos que devem ser lidos
- `CLAUDE.md` (§2, §4, §5, DEC-011 completa em §8)
- `tasks/current_task.md`
- `tasks/backlog.md` (seção BLK-RELMUN-03, linhas ~123-173)
- `src/motor_expansao/dashboard/relatorio_municipal.py` (arquivo inteiro; focar linhas 1-70,
  258-264, 455-480, 600-625, 740-765, 895-925, 1000-1020, 1595-1675)
- `tests/unit/test_relatorio_municipal.py` (arquivo inteiro; focar linhas 1-135, 295-335)
- `docs/relatorio_municipal_template.md` (contexto do template, se necessário)

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/relatorio_municipal.py`
- `tests/unit/test_relatorio_municipal.py`
- `CLAUDE.md` (emenda à DEC-011, §8)
- `tasks/backlog.md`, `tasks/current_task.md`, `tasks/completed.md`
- `context/handoff.md`, `context/handoff/`

## Critérios de aceite
- `_hex_destacado_mask` retorna `oferta_efetiva_disponivel >= OFERTA_DESTAQUE_MIN` apenas (sem
  termo de SAM Fitness).
- Nenhuma referência textual remanescente a "SAM Fitness >= 3.000" como critério de destaque no
  módulo `relatorio_municipal.py` nem nos testes (grep confirmando ausência).
- "Hexágonos destacados"/"Espaço para academias"/contagem "Aprovados/Reprovados" no PDF refletem
  o novo critério (mais hexágonos destacados, valor de "Espaço para academias" igual ou maior que
  antes para qualquer município com hexes de `oferta>=2000` e `sam<3000`).
- Suíte `tests/unit/test_relatorio_municipal.py` verde; suíte completa do projeto sem regressões
  (`pytest -q`); ruff + mypy limpos.
- Emenda à DEC-011 registrada em `CLAUDE.md` §8, datada e com aprovação humana citada.
- Revisão visual humana do PDF gerado (Vinicius) aprovada antes do merge.
- `score_priorizacao`, artefatos oficiais do M1 e `flag_sam` no pipeline de mercado permanecem
  byte-a-byte inalterados (nenhum diff fora dos arquivos listados acima).

## Criticidade classificada
Alta

## Esteira recomendada
Planner → [REVISÃO HUMANA — produto + emenda DEC-011] → Builder → QA

## Riscos identificados
- **Decisão pendente de produto:** manter ou remover `SAM_DESTAQUE_MIN` como constante — precisa
  ser resolvida explicitamente no gate humano (backlog já sinaliza isso como aberto), não deve
  ser decidida unilateralmente pelo Builder.
- **Cobertura de teste insuficiente para provar a mudança:** a fixture `_sample_df` atual move os
  dois limiares (SAM e oferta) em conjunto, então os testes existentes podem passar sem
  realmente exercitar o caso "sam<3000 e oferta>=2000 agora destacado" — recomenda-se que o
  Planner inclua explicitamente esse caso no plano de testes.
- **Inconsistência pré-existente de contagem de páginas** (fora do escopo deste bloco, mas pode
  confundir o Builder): o guardrail recebido do orquestrador cita "8 páginas mantidas", porém o
  código atual (`PDF_SECTION_HEADERS` tem 9 entradas, docstring do módulo diz "PDF de 9 paginas",
  e o teste `test_pdf_municipal_8_paginas_e_secoes` assere `b"/Count 9"`) já está em 9 páginas —
  provavelmente resquício textual de antes do FU1 que adicionou "Visao Geral do Municipio". Não
  corrigir essa nomenclatura como parte deste bloco (fora de escopo), mas o Builder NÃO deve
  tentar forçar 8 páginas — o invariante real e correto a preservar é "estrutura/contagem de
  páginas do PDF inalterada" (seja qual for o número atual).
- **`_hex_destacado_mask` é usada em múltiplos pontos** (mapa "resumo", `_zonas_geometricas`,
  `_focus_bounds_mercator`, cálculo de "Espaço para academias", contagem aprovados/reprovados,
  legenda). Por estar centralizada numa única função, o risco de divergência entre os
  consumidores é baixo, mas o Builder deve confirmar por grep que não há nenhuma segunda
  implementação paralela do critério (`sam_fitness_potencial >= 3000` hardcoded fora da função).
- **Efeito de produto:** mais hexágonos destacados e "Espaço para academias" maior em todos os
  relatórios já gerados/futuros — é o resultado esperado e aprovado, mas deve ser comunicado
  como mudança visível de número no PDF (não é bug).

## Guardrails ativos
- §2: nenhuma trilha paralela pode alterar o M1 sem aprovação explícita; toda mudança relevante
  entra com teste; nenhum PR sobe com CI quebrado.
- §5 (guardrail permanente): visualizações/relatórios não podem recalcular ou alterar
  `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou
  artefatos oficiais do M1 sem aprovação explícita.
- DEC-011 (§8): fixa D1 — critério original do hexágono destacado do Relatório Municipal
  (`sam_fitness_potencial>=3000` E `oferta_efetiva_disponivel>=2000`); este bloco exige emenda
  formal a essa decisão, não uma reescrita silenciosa.
- Interpretação de criticidade (topo do CLAUDE.md, decidida 2026-05-30): ALTERAÇÃO de
  fórmula/pesos/artefato M1 = Crítica; este bloco é sobre um critério de DISPLAY do relatório
  (não é fórmula/peso/artefato M1), por isso a criticidade classificada é Alta (conforme já
  fixado em `tasks/current_task.md` e no backlog), não Crítica — mas ainda assim exige aprovação
  humana e DEC por alterar um número decidido formalmente (DEC-011).
