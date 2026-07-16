# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-RELPON-08 — Big Numbers (página 5) do Relatório Pontual Censitário: trocar métrica
("Score censitário máximo" → "Número de domicílios" no raio), reordenar a linha 1 e pintar
o fundo de cada card em verde/vermelho/neutro por meta (semáforo).

## Objetivo
Ajustar `_big_numbers_page` (grid 4x2) para exibir "Número de domicílios" no raio em vez de
"Score censitário máximo", reordenar a linha 1 conforme D2, e colorir o fundo de cada card
conforme a meta (D3) — tudo READ-ONLY sobre o M1.

## Contexto técnico (já medido — não re-medir)
- `_big_numbers_page` vive em `src/motor_expansao/dashboard/censo_report.py` (linhas ~513-591
  na leitura atual). Grid 4x2, 8 cards, ordem hoje = `index % cols`/`index // cols` sobre a
  lista `cards` construída nas linhas ~532-541:
  - L1 (índices 0-3): `pop_total_raio`, `renda_per_capita_media_raio`, `score_setor_medio`,
    `score_setor_max`.
  - L2 (índices 4-7): `sam_fitness_potencial` (via `residual`), `oferta_efetiva_disponivel`
    (via `residual`), `n_concorrentes`, `oferta_consumida_mercado_estimada` (via `residual`).
    L2 fica INALTERADA nesta ordem (D2 só mexe na L1).
- `domicilios_total_raio` NÃO existe hoje em `analisar_ponto_censitario_setores`
  (`src/motor_expansao/dashboard/censo_point.py`). O padrão EXATO a replicar é o de
  `pop_total_raio` (linhas ~283-284 e ~354-357 na leitura atual):
  - `intersectados` (o DataFrame local, ANTES do corte para `display_cols`/
    `result["setores_intersectados"]`) já carrega TODAS as colunas originais de
    `setores_df` via `record = row.to_dict()` (linha ~270) — inclusive
    `domicilios_particulares_ocupados_setor_2022`, que NÃO está em
    `_empty_setores_frame()` mas está no parquet de setores (já lida em
    `agregar_perfil_bairro_distrito`, linha ~472, para o BLK-RELPON-07). Logo o novo campo
    deve ser calculado sobre `intersectados` (full columns), não sobre o frame recortado.
  - Peso: `dom_setor = _numeric(intersectados, "domicilios_particulares_ocupados_setor_2022").clip(lower=0)`;
    `dom_estimado_intersecao = dom_setor * intersectados["peso_area_setor"]` — MESMO padrão de
    `pop_estimada_intersecao = pop_setor * intersectados["peso_area_setor"]` (linha ~284).
  - Agregação: seguir o guard de `pop_weights.notna().any()` (linha ~354) — se
    `dom_weights.notna().any()`, `result["domicilios_total_raio"] = round(float(dom_weights.fillna(0).sum()), 2)`;
    caso contrário, `None` ("n/d"). Adicionar a chave `"domicilios_total_raio": None,` ao dict
    default do `result` (linha ~204, junto de `pop_total_raio`), para o campo existir mesmo em
    early-return (setores_df vazio, sem geometria, sem candidatos, etc.).
  - NÃO reusar `domicilios_total` de `agregar_perfil_bairro_distrito` (BLK-RELPON-07) — esse é
    o total do BAIRRO/DISTRITO inteiro (página 4), escopo diferente do raio de 1,5 km (página 5).
- `_format_number(value, decimals)` já existe em `censo_report.py` (linha ~175) — reusar com
  `decimals=0` para o novo card, igual aos demais campos de contagem (pop, concorrentes).

## Decisões de produto JÁ TOMADAS (Vinicius, 2026-07-15 — NÃO reabrir sem novo gate)
- **D1** — "Score censitário máximo" (`score_setor_max`) SAI da grid; ENTRA "Número de
  domicílios" (`domicilios_total_raio`, novo, no RAIO — não no bairro). `score_setor_max`
  PODE permanecer no `result`/CSV para auditoria (só deixa de ser exibido no PDF), mesmo
  padrão que o BLK-RELPON-05 aplicou a `*_setor_ponto`.
- **D2** — Reordenar L1: "Número de domicílios" vai para **L1C3** (índice 2); "Score
  censitário médio" vai para **L1C4** (índice 3) — trocam de posição. L1 final = [População
  total no raio, Renda per capita média, Número de domicílios, Score censitário médio]. L2
  INALTERADA.
- **D3** — Fundo de cada card vira verde (meta atingida) ou vermelho (meta não atingida),
  conforme a tabela:

  | Card | Verde quando | Campo |
  |---|---|---|
  | População total no raio | `>= 10000` | `pop_total_raio` |
  | Renda per capita média | `>= 1500` | `renda_per_capita_media_raio` |
  | Número de domicílios | `>= 3000` | `domicilios_total_raio` (NOVO) |
  | Score censitário médio | `>= 60` | `score_setor_medio` |
  | SAM Fitness (alunos) | `>= 2000` | `sam_fitness_potencial` |
  | Residual Fitness (alunos) | `>= 2000` | `oferta_efetiva_disponivel` |
  | Consumo concorrentes (est.) | VERMELHO quando `sam_fitness_potencial >= 2000` **E** `oferta_efetiva_disponivel < 2000`; senão VERDE | `sam_fitness_potencial`, `oferta_efetiva_disponivel` |
  | Concorrentes no raio | ESPELHA a cor de "Consumo concorrentes (est.)" | (segue o card acima) |

## Questões do gate — RESOLVIDAS por esta delimitação (usar estas respostas; não reabrir)
- **Q1 — escopo do domicílio:** "Número de domicílios" é NO RAIO (`domicilios_total_raio`,
  computado em `analisar_ponto_censitario_setores`), NÃO do bairro/distrito (página 4,
  `domicilios_total` de `agregar_perfil_bairro_distrito`). Confirmado.
- **Q2 — cor para "n/d":** quando o valor do card é `None`/"n/d", a cor de fundo é NEUTRA
  (cinza claro, sem verde/vermelho). Aplica-se também ao Consumo/Concorrentes quando SAM ou
  Residual é "n/d" (condição indecidível → neutro). Confirmado.
- **Q3 — paleta:** fundo em tom PASTEL (verde/vermelho claro) com a barra de acento sólida no
  topo do card já existente (padrão D3=B do BLK-EST-02, `card_h=156`/barra 6 pt) mantida;
  rótulo/valor seguem em cinza-escuro `(45,45,45)`/`(40,40,40)` — contraste ajustado fino no
  gate visual humano do fim da esteira, se necessário. O Planner deve propor tons pastel
  concretos (RGB) para verde/vermelho/neutro como parte do plano, mas a decisão fina de
  contraste fica para a revisão visual humana do PDF.
- **Q4 — metas como constantes:** os 6 limiares (10000/1500/3000/60/2000/2000) viram
  constantes nomeadas no módulo `censo_report.py` (auditáveis, não hardcoded inline).
  Confirmado.

## Escopo permitido
- `src/motor_expansao/dashboard/censo_point.py`:
  - Adicionar `"domicilios_total_raio": None,` ao dict default do `result` em
    `analisar_ponto_censitario_setores`.
  - Computar `domicilios_total_raio` sobre `intersectados` (full columns, ANTES do corte
    `display_cols`) pelo MESMO padrão de peso de área de `pop_total_raio`
    (`domicilios_particulares_ocupados_setor_2022 × peso_area_setor`, soma, "n/d" gracioso
    quando nenhum setor tem domicílios ou `dom_weights` é todo NaN).
  - SÓ leitura/agregação nova. NÃO tocar `setor_censitario_intersecao_area_1p5km`, o raio de
    1,5 km, `circle_metric`, o método de interseção, nem qualquer outro campo já existente.
- `src/motor_expansao/dashboard/censo_report.py`, dentro de `_big_numbers_page`:
  - Trocar o card de `score_setor_max` por `domicilios_total_raio` ("Número de domicílios",
    `_format_number(..., 0)`).
  - Reordenar a lista `cards` conforme D2 (L1: pop, renda, domicílios, score médio; L2
    inalterada).
  - Adicionar um helper PURO de decisão de cor por card (ex.: `_card_cor_fundo(...)` ou
    equivalente) que recebe os valores relevantes e devolve a cor (verde/vermelho/neutro),
    aplicando a tabela de D3 — incluindo a regra assimétrica do Consumo e o espelhamento do
    card Concorrentes. Testável isoladamente, sem depender do PDF.
  - Pintar o retângulo de fundo do card (`pdf.rect(..., style="F")`) com a cor decidida ANTES
    de desenhar a barra de acento e o texto, preservando contraste do rótulo/valor.
  - Definir as 6 metas como constantes nomeadas no módulo (Q4).
  - Atualizar a nota de fonte auditável do fim do slide se necessário para mencionar o
    semáforo (opcional, mas recomendado para rastreabilidade).
- `tests/` — testes novos/alterados cobrindo:
  - `domicilios_total_raio`: agregação com peso de área conhecido (setor parcialmente dentro
    do círculo) e caso "n/d" (nenhum setor com domicílios, ou setores_df vazio).
  - Ordem e rótulos dos cards da L1 (novo card presente, `score_setor_max` ausente do PDF).
  - Cor por card: cenário acima/abaixo de cada meta; a regra assimétrica do Consumo; o espelho
    de Concorrentes; caso "n/d" → neutro (para cada campo relevante, inclusive quando SAM ou
    Residual é "n/d").
- `docs/relatorio_pontual_censitario.md` — atualizar a seção "Cards Big Numbers" (linha ~244
  na leitura atual) para refletir a nova ordem, o novo campo e o semáforo de cor.

## Fora de escopo
- Método de interseção `setor_censitario_intersecao_area_1p5km`, raio 1,5 km,
  `RAIO_CENSITARIO_DEFAULT_KM`, `circle_metric`.
- Mapas de calor/choropleth, marca d'água anti-PII, `set_compression(False)`.
- Página "Perfil do Bairro/Distrito" (BLK-RELPON-07) e seu `domicilios_total` (escopo
  bairro/distrito, não raio) — NÃO reusar nem tocar.
- `score_priorizacao`, pesos, `hex_score_estrutural`, carteira, plano, artefatos oficiais do
  M1 (§5 CLAUDE.md, guardrail permanente).
- `flag_sam`/gate do SAM (DEC-006/DEC-007) — as metas de cor de D3 são de DISPLAY local ao
  PDF; NÃO alteram o gate do SAM nem os valores de `sam_fitness_potencial`/
  `oferta_efetiva_disponivel`.
- Contagem de páginas do PDF (permanece 6).
- Relatório Municipal e UI do dashboard Streamlit (fora do escopo deste bloco).

## Arquivos que devem ser lidos
- `CLAUDE.md` (§2 regras de acentuação — texto voltado ao usuário/PDF deve ter acentuação
  correta; §5 guardrail M1 READ-ONLY).
- `tasks/backlog.md` — bloco `### BLK-RELPON-08` completo (linha ~1408).
- `src/motor_expansao/dashboard/censo_point.py` — função `analisar_ponto_censitario_setores`
  completa (dict default, cálculo de `pop_total_raio`/`peso_area_setor`/
  `pop_estimada_intersecao`, guard de agregação); e `agregar_perfil_bairro_distrito` (para
  entender por que NÃO reusar `domicilios_total` do bairro).
- `src/motor_expansao/dashboard/censo_report.py` — função `_big_numbers_page` completa,
  `_format_number`, e as constantes de cor já existentes no módulo (`ULTRA_TURQUESA`,
  `ULTRA_MAGENTA`, `_BRANCO`, `_CINZA_TEXTO` etc.) para escolher paleta consistente.
- `docs/relatorio_pontual_censitario.md` — seção "Cards Big Numbers" (linha ~244) e contexto
  de página 5 (linha ~213).
- `tests/` existentes que cobrem `_big_numbers_page`/`analisar_ponto_censitario_setores` (o
  Planner/Builder deve localizá-los para entender o padrão de teste do módulo antes de somar
  casos novos).

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/censo_point.py`
- `src/motor_expansao/dashboard/censo_report.py`
- `tests/` (arquivos de teste do relatório pontual censitário — unit/integration existentes
  ou novos, conforme convenção do repo)
- `docs/relatorio_pontual_censitario.md`
- `context/handoff/` (snapshots versionados do próprio ciclo)

## Critérios de aceite
- Página Big Numbers exibe "Número de domicílios" (no raio) em L1C3 e "Score censitário
  médio" em L1C4; "Score censitário máximo" NÃO aparece mais na grid (pode continuar no
  `result`/CSV).
- `domicilios_total_raio` é computado em `analisar_ponto_censitario_setores` pelo mesmo padrão
  de peso de área de `pop_total_raio`, com teste dedicado usando peso de área conhecido e
  cenário "n/d".
- Cada um dos 8 cards tem fundo verde/vermelho/neutro conforme a tabela de D3, com a regra
  assimétrica do Consumo concorrentes (SAM alto + Residual baixo = vermelho) e o card
  Concorrentes espelhando a cor do Consumo; "n/d" sempre neutro.
- As 6 metas (10000/1500/3000/60/2000/2000) existem como constantes nomeadas em
  `censo_report.py`.
- Método de interseção, raio de 1,5 km, marca d'água e todo artefato/score do M1 permanecem
  INTOCADOS (nenhum arquivo de `pipelines/m1/`, `config.py` ou artefatos oficiais tocado).
- Acentuação correta do português em todo texto novo voltado ao usuário (rótulos, nota de
  fonte) — sem regressão para texto sem acento (CLAUDE.md §2).
- `ruff` e `mypy` limpos; suíte de testes verde (incluindo os casos novos acima).
- Revisão visual humana do PDF gerado aprovada (contraste rótulo/valor legível sobre o fundo
  colorido; semáforo compreensível) — gate obrigatório no fim da esteira, antes do merge.

## Criticidade classificada
Média — confirmado. O bloco é READ-ONLY sobre o M1 (não toca `score_priorizacao`,
`hex_score_estrutural`, pesos, carteira, plano ou qualquer artefato oficial do M1). Adiciona
um campo agregado (`domicilios_total_raio`) ao motor do relatório pontual e altera
layout/cor de uma página de PDF — mudança de display/relatório com uma extensão de leitura
pontual, sem redesenho de arquitetura. Não se qualifica como Alta/Crítica porque nenhum
gate de score, pipeline de mercado (DEC-006/DEC-007) ou artefato M1 é alterado.

## Esteira recomendada
Block Orchestrator -> Planner -> Builder -> QA -> [REVISÃO HUMANA visual do PDF] -> merge.

## Riscos identificados
- **Divergência de peso de área** — se `domicilios_total_raio` não seguir EXATAMENTE o mesmo
  padrão de peso (`peso_area_setor`) de `pop_total_raio`, o número fica inconsistente com
  pop/renda do mesmo raio. Mitigação: teste dedicado com peso de área conhecido, comparando
  contra um cálculo manual.
- **Contraste ilegível** — fundo colorido (mesmo pastel) pode reduzir a legibilidade do
  rótulo/valor em cinza-escuro. Mitigação: gate visual humano obrigatório no fim da esteira;
  Planner deve especificar tons pastel concretos que preservem contraste com texto
  `(45,45,45)`/`(40,40,40)`.
- **"n/d" pintado como reprovação/aprovação falsa** — sem a regra neutra (Q2), um dado
  ausente viraria "vermelho" (falsa reprovação) ou "verde" (falso positivo). Mitigação: o
  helper de cor deve tratar `None`/"n/d" explicitamente ANTES de comparar com a meta, com
  teste dedicado por campo.
- **Semântica assimétrica do Consumo/Concorrentes** — a regra não é "quanto maior, melhor"; é
  "SAM alto + Residual baixo = mercado já consumido = vermelho". Mitigação: documentar na nota
  de fonte do slide para não induzir a leitura errada de "verde = mais concorrentes é bom".
- **Metas hardcoded sem constante nomeada** — se implementadas como números soltos no meio do
  código, ficam pouco auditáveis. Mitigação: Q4 já resolve isso — exigir constantes nomeadas
  como critério de aceite.

## Guardrails ativos
- **READ-ONLY M1 (CLAUDE.md §5, guardrail permanente):** visualizações, análise radial e
  relatórios não podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`,
  carteira, plano curto prazo, plano de domínio ou artefatos oficiais do M1 sem aprovação
  explícita. Este bloco NÃO tem essa aprovação nem precisa dela — está fora de escopo tocar
  nesses artefatos.
- **Acentuação (CLAUDE.md §2, regra permanente pós BLK-ACENTO):** todo texto voltado ao
  usuário no PDF (rótulos, nota de fonte) deve ter acentuação correta do português; não
  regredir para texto sem acento. Atenção ao encoding `latin-1` do fpdf2/Helvetica via
  `_ascii()` — caracteres fora de latin-1 (travessão `—`, bullet `•`, seta `→`, reticências
  `…`, aspas curvas, `©`) viram `"?"` silenciosamente; usar pontuação ASCII (`-`, `"`, `(c)`,
  `...`) em texto novo.
- **Núcleo `censo_*` como interface estável (DEC-005 emenda 2026-06-12):** o método de
  interseção `setor_censitario_intersecao_area_1p5km`, o raio 1,5 km e a lógica de
  interseção são INTOCADOS; este bloco só ESTENDE leitura/agregação (novo campo) e render
  (cor/ordem), sem editar o núcleo geométrico.
- **flag_sam/DEC-006/DEC-007 intocados:** as metas de cor de D3 são thresholds de DISPLAY
  locais a `censo_report.py`; não alteram o gate do SAM no pipeline de mercado
  (`calcular_colunas_mercado.py`) nem os valores de `sam_fitness_potencial`/
  `oferta_efetiva_disponivel` — o card apenas LÊ esses valores já calculados.
- **Interpretação de criticidade para score (CLAUDE.md §1):** este bloco é
  LEITURA/EXTENSÃO de campo agregado sem escrita em artefato M1 → tratado como Média/Alta no
  espírito da regra, mas confirmado Média porque não há alteração de fórmula/peso/artefato
  M1 — apenas leitura adicional na camada de relatório.
