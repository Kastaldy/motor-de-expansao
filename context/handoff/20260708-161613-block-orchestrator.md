# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-RELMUN-06 — Texto dinâmico das zonas de atuação no slide Síntese (card 3 "Movimento
Recomendado") do Relatório Municipal, conforme os tipos de zona geométrica efetivamente presentes
no município (Âncora central / Flancos laterais / Cerco).

## Objetivo
Substituir o texto CONSTANTE do card 3 da `_sintese_page` por um texto composto a partir de
`result["zonas_geo"]` (rótulos das zonas presentes), para que municípios com 1, 2 ou 3 zonas — ou
0 zonas — recebam uma recomendação coerente com a estratégia real, em vez de sempre a mesma frase
de "cerco pelos flancos".

## Escopo permitido
- `_sintese_page` (`src/motor_expansao/dashboard/relatorio_municipal.py:1950-1997`): alterar SOMENTE
  a string `texto` do 3º item da lista `cards` (linha 1969, hoje
  `"Movimento Recomendado: posicionamento periférico, cercar o núcleo pelos flancos antes da
  concorrência."`), compondo-a a partir de `result.get("zonas_geo")` (lista de dicts com chaves
  `zona_n`, `rotulo`, `descricao`, `n_hex`, `cor_rgb` — produzida em `_zonas_geometricas`/linhas
  459-528 e injetada no `result` em `agregar_municipio`, linha 688).
- Reusar como blocos de frase as constantes já existentes: `_ZONA_GEO_DESC` (linhas 164-168,
  paralela a `_ZONA_GEO_ROTULOS` linha 163) e/ou `_ZONA_TEXTOS` (dict por rótulo, linhas
  1777-1781). Não é obrigatório usar as duas; o Planner decide qual serve melhor ao texto do card
  (o Builder só implementa o que for aprovado no gate D1).
- Definir fallback de texto para 0 zonas (`zonas_geo` vazio/ausente) — análogo ao padrão já usado
  na Página Domínio para o caso "sem hexes aprovados" (linhas 1818/1890, mensagem de zonas
  insuficientes).
- Testes novos/atualizados em `tests/unit/test_relatorio_municipal.py` cobrindo 0, 1, 2 e 3 zonas.

## Fora de escopo
- `_zonas_geometricas`, `_zonas_do_municipio`, `hex_zona`/`hex_zona_geo`, `_hex_destacado_mask` —
  a zonificação em si é SÓ LIDA, nunca recalculada ou alterada.
- `dominio_df`, `flag_sam`, `score_priorizacao`/`score_setor_2022_calibrado`/qualquer artefato
  oficial do M1.
- Os outros 2 cards da Síntese (penetração fitness, residual) e o VALOR do card 3
  (`f"{_format_number(result.get('n_zonas_geo'), 0)} zonas de atuação"`, linha 1968) — permanecem
  exatamente como estão.
- `_dominio_page` (Página 5/6, linhas 1784+) — já é dinâmica por zona; **o backlog registra que
  o gate deve CONFIRMAR explicitamente se ela entra ou não no escopo deste bloco** (por padrão,
  fora de escopo — só a Síntese foi pedida).
- Estrutura de páginas do PDF, contagem de páginas, marca d'água, `set_compression`,
  `_draw_footer`, núcleo `censo_*`.
- Qualquer outro card/página do relatório municipal ou do relatório pontual censitário.

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/relatorio_municipal.py` (função `_sintese_page` ~1950-1997;
  constantes `_ZONA_GEO_ROTULOS` ~163, `_ZONA_GEO_DESC` ~164-168, `_ZONA_TEXTOS` ~1777-1781;
  `_zonas_geometricas` ~459-528; `agregar_municipio` — produção de `zonas_geo`/`n_zonas_geo` no
  `result`, ~657-690; `_dominio_page` ~1784+ como referência de padrão já dinâmico e de fallback
  para 0 zonas).
- `tests/unit/test_relatorio_municipal.py` (testes existentes de `_sintese_page`/Síntese e de
  zonas, para seguir o padrão de fixtures).
- `tasks/backlog.md` (bloco `### BLK-RELMUN-06`, linhas 1346-1385).
- `tasks/current_task.md` (tarefa ativa, gate D1, guardrails, paths do ciclo).
- CLAUDE.md §2 (acentuação; PDF em latin-1 via `_ascii()`, proibido travessão/bullet/seta/aspas
  curvas fora de latin-1) e §5 (READ-ONLY M1).

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/relatorio_municipal.py`
- `tests/unit/test_relatorio_municipal.py`
- `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md` (só no fechamento do ciclo)
- `context/handoff.md`, `context/handoff/`

## Critérios de aceite
- O texto do card 3 ("Movimento Recomendado") no slide Síntese reflete os tipos de zona
  efetivamente presentes em `result["zonas_geo"]` para o município (testar 1, 2 e 3 zonas — todas
  as combinações plausíveis de `_ZONA_GEO_ROTULOS`).
- Fallback definido e testado para 0 zonas (`zonas_geo` vazio/None), sem exceção.
- Os outros 2 cards e o VALOR do card 3 ("N zonas de atuação") permanecem byte-a-byte inalterados.
- `zonas_geo`, `hex_zona_geo`, `dominio_df`, `flag_sam`, score e artefatos oficiais do M1
  permanecem intocados (nenhuma escrita, só leitura de `result`).
- Texto novo com acentuação correta do português; nenhum caractere fora de latin-1 (sem
  travessão/bullet/seta/reticências/aspas curvas — só ASCII de pontuação, via `_ascii()`).
- `tests/unit/test_relatorio_municipal.py` cobre as combinações de zonas; suíte relevante,
  ruff e mypy limpos.
- Revisão visual do PDF aprovada (o card não pode transbordar com texto mais longo que o atual).

## Criticidade classificada
Média.

## Esteira recomendada
Block Orchestrator (concluído) → Planner → **[gate humano D1 — REAL, aprovação obrigatória de
Vinicius antes do Builder]** → Builder → QA.

**Gate humano D1 (REAL, não pular):** o Planner deve PROPOR o mapeamento texto↔combinação de
zonas (ex.: só "Âncora central" → adensar o núcleo; +"Flancos laterais" → cercar pelos flancos;
+"Cerco" → estratégia completa de cerco; 0 zonas → fallback) e também propor se a Página Domínio
entra ou não no escopo. O orquestrador do ciclo PARA nesse ponto e apresenta a proposta ao humano
para aprovação explícita antes de acionar o Builder. Não é gate simbólico — não prosseguir sem
resposta do humano.

## Riscos identificados
- Tocar `_zonas_geometricas`/`_zonas_do_municipio`/`hex_zona_geo` (a zonificação em si) em vez de
  só LER `result["zonas_geo"]` — violaria READ-ONLY M1/mercado e teria efeito além do display.
- Texto do card ficar longo demais ao combinar 3 zonas e transbordar o `_rounded_panel` (card_h
  fixo em 210, `multi_cell` a partir de `top + 104`) — checar visualmente com as 4 combinações.
- Acentuar IDENTIFICADORES por engano (ex.: chaves de `_ZONA_TEXTOS`, valores de `rotulo`/`zona_n`)
  — essas já vêm acentuadas como rótulo de exibição legítimo (não são enum bruto), mas nenhuma
  chave de dict/coluna deve ganhar acento novo por engano ao refatorar.
- Introduzir caractere fora de latin-1 no texto novo (travessão, bullet, seta, aspas curvas) —
  vira "?" silencioso no PDF (`_ascii()`); usar só pontuação ASCII.
- Escopo ambíguo quanto à Página Domínio (`_dominio_page`) — já dinâmica; expandir a ela sem
  aprovação do gate seria expansão de escopo não autorizada.
- Quebrar o VALOR do card ("N zonas de atuação") ao editar a tupla `cards[2]` — a edição deve
  tocar só o 3º elemento da tupla (texto), preservando os dois primeiros.

## Guardrails ativos
- §5 (CLAUDE.md): "Guardrail permanente: visualizações, análise radial e interações de mapa não
  podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto
  prazo, plano domínio ou artefatos oficiais do M1 sem aprovação explícita." — este bloco é
  puramente de DISPLAY (texto de relatório), sem qualquer escrita em score/artefatos.
- §2 (CLAUDE.md, regra de acentuação): todo texto voltado ao usuário (inclusive relatórios
  PDF/CSV) deve ter acentuação correta; NUNCA acentuar identificadores (`key=`, `session_state`,
  seletores CSS, valores brutos de enum, nomes de coluna, slugs/arquivos). No PDF (`fpdf2`
  Helvetica, `latin-1` via `_ascii()`), caracteres fora de latin-1 (travessão, bullet, seta,
  reticências, aspas curvas, ©) viram "?" silenciosamente — usar só pontuação ASCII.
- Regra de criticidade para score (CLAUDE.md, decisão 2026-05-30): leitura/análise de score sem
  escrita em artefato M1 → Alta; alteração de fórmula/pesos/artefato → Crítica. Este bloco não
  toca score algum (é texto de card lendo `zonas_geo` já calculado) — mantém-se Média conforme
  classificado no backlog/current_task, não Alta/Crítica.
- Guardrails específicos do `current_task.md`: só leitura de `zonas_geo`/`_zonas_geometricas`/
  `_zonas_do_municipio`; `dominio_df`/`flag_sam`/score intactos; núcleo `censo_*`/estrutura de
  páginas/marca d'água/`set_compression` intocados; commit por path (nunca `git add -A`), paths
  do ciclo listados em `tasks/current_task.md`.
- Fluxo de branch (decisão de Vinicius 2026-07-08): branch `ciclo/BLK-RELMUN-06` ramificada de
  `integracao/map02-relmun05-06`; ao fechar (QA aprovado + commit por path), mergear para a
  secundária; NÃO abrir PR após os 3 ciclos (Vinicius quer revisar antes).
