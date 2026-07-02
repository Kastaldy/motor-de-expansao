# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-RELMUN-04 — Relatório Municipal em lote: quando mais de um município está selecionado, os
dois pontos de geração do Relatório Municipal (`render_relatorio_municipal_download_topo` no topo
e `render_relatorio_municipal_expander` no Mapa Territorial) devem passar a gerar, sob demanda por
botão, um PDF por município selecionado, com progresso, e oferecer um `st.download_button` por
município (rotulado com o nome do município) após a geração. O caso de exatamente 1 município
permanece com o comportamento atual, byte-a-byte.

## Objetivo
Estender os 2 pontos de geração do Relatório Municipal em `src/motor_expansao/dashboard/pages.py`
para suportar `len(selected_cities) > 1`, gerando um PDF por município via botão único
("Gerar Relatórios (N)") com indicador de progresso, e oferecendo download individual por
município — sem alterar o comportamento de 1 município nem o motor do PDF.

## Escopo permitido
- Alterar `render_relatorio_municipal_download_topo` (pages.py ~linha 3044) e
  `render_relatorio_municipal_expander` (pages.py ~linha 3898) para ramificar por
  `len(selected_cities)`:
  - `== 1`: fluxo atual PRESERVADO byte-a-byte (mesmos `key`s de widget, mesma cache key
    `relmun_topo_payload::<nome>`, mesmo texto de botão/spinner/warning).
  - `> 1`: novo ramo — botão único "Gerar Relatórios (N)" → loop por município reusando
    `_resolve_bairros_por_hex_municipio` + `agregar_municipio` + `render_mapas_municipio` +
    `gerar_payloads_download_relatorio_municipal` (as MESMAS chamadas já usadas no fluxo de 1
    município, mesmos kwargs) → indicador de progresso (`st.progress`/`st.spinner` com contador
    "gerando i/N") → cache dos payloads por município em `session_state` (chave nova, distinta de
    `relmun_topo_payload::<nome>` para não colidir) → um `st.download_button` por município,
    rotulado com o nome do município (ex. "Baixar PDF — <Município>"), `key` único por município
    (ex. incluindo UF+nome+índice para evitar colisão entre municípios homônimos de UFs
    diferentes).
  - `== 0`: preservar o comportamento atual de cada função (topo: `return` silencioso;
    expander: `st.info` pedindo para selecionar 1 município — decidir se o texto deve mencionar
    "1 ou mais" — ver Riscos).
- Tratar por município, dentro do loop, o caso `municipio_result["n_hex_total"] == 0`: aviso
  individual (ex. `st.warning` citando o nome do município) e seguir para o próximo, sem abortar
  o lote nem quebrar a geração dos demais.
- Escolher e documentar no plano: se o modo `> 1` reaproveita literalmente as mesmas 4 chamadas
  (`_resolve_bairros_por_hex_municipio`, `agregar_municipio`, `render_mapas_municipio`,
  `gerar_payloads_download_relatorio_municipal`) dentro de um loop, ou se extrai um helper privado
  comum a `== 1` e `> 1` para reduzir duplicação — decisão do Planner, desde que o resultado para
  `== 1` seja idêntico ao atual.
- Escolher o design de `session_state` para o lote (ex. dict `{"relmun_lote_payloads::<contexto>":
  {nome_municipio: {"pdf_bytes":..., "pdf_filename":...}}}` ou chaves individuais por município) —
  decisão do Planner; deve sobreviver ao rerun do clique em qualquer `download_button` individual
  (mesmo padrão do fluxo de 1 município: gerar não deve refazer o trabalho a cada rerun de
  download).
- Adicionar/editar testes em `tests/integration/test_streamlit_app.py` (mesmo arquivo dos testes
  existentes de `render_relatorio_municipal_download_topo`/`render_relatorio_municipal_expander`,
  ver linhas 4856-4909) cobrindo: gate `> 1` aparece com o rótulo "Gerar Relatórios (N)"; N
  municípios geram N `download_button` rotulados; município com `n_hex_total == 0` no lote gera
  aviso individual e não aborta os demais; fluxo de 1 município permanece idêntico (testes
  existentes `test_render_relatorio_municipal_topo_sem_municipio_unico_nao_renderiza` e
  `test_render_relatorio_municipal_topo_clique_gera_e_oferece_download` devem continuar passando
  sem modificação de asserção, só ajuste se a assinatura/comportamento do caso `== 1` mudar
  incidentalmente — o que NÃO deveria acontecer).
- Atualizar docstrings das duas funções para refletir o novo comportamento multi-município.

## Fora de escopo
- `src/motor_expansao/dashboard/relatorio_municipal.py` (motor do PDF: `agregar_municipio`,
  `render_mapas_municipio`, `gerar_pdf_relatorio_municipal`,
  `gerar_payloads_download_relatorio_municipal`, `render_download_relatorio_municipal`,
  `_hex_destacado_mask`, páginas do PDF, marca d'água, `CAPACIDADE_UNIDADE`) — SÓ CONSUMIR, não
  alterar.
- Critério de hexágono destacado (DEC-011 / BLK-RELMUN-03) e o gate `flag_sam` do pipeline de
  mercado.
- `score_priorizacao`, `hex_score_estrutural`, pesos, carteira, plano curto prazo, plano de
  domínio, artefatos oficiais do M1 (§5 CLAUDE.md).
- Relatório Pontual Censitário (`render_relatorio_pontual_censitario`,
  `render_pdf_download_topo`, `gerar_payloads_relatorio_pontual_para_pin`) — não tocar.
- Estrutura/páginas/formato do PDF (9 páginas), tiles/basemap (DEC-011 já cobre a rede existente;
  não introduzir dependência de rede nova).
- Qualquer outro ponto de `pages.py`/`streamlit_app.py` não relacionado aos 2 pontos de geração
  listados.

## Arquivos que devem ser lidos
- `CLAUDE.md` (§2, §4, §5, DEC-011 em §8)
- `tasks/current_task.md`
- `tasks/backlog.md` (bloco `BLK-RELMUN-04`, linhas ~125-171)
- `src/motor_expansao/dashboard/pages.py` — função `render_pdf_download_topo` (linhas 2986-3042,
  padrão irmão já existente de "gerar sob demanda + cache em session_state + download_button", do
  Relatório Pontual, útil como referência de padrão a seguir), `render_relatorio_municipal_
  download_topo` (linhas 3044-3122), `render_relatorio_municipal_expander` (linhas 3898-3966,
  chama `render_download_relatorio_municipal` de `relatorio_municipal.py` no fim)
- `src/motor_expansao/dashboard/relatorio_municipal.py` — assinaturas de `agregar_municipio`,
  `render_mapas_municipio`, `gerar_payloads_download_relatorio_municipal` (linhas 2124-2143),
  `render_download_relatorio_municipal` (linhas 2145-2166); usar SÓ como referência de contrato,
  não alterar.
- `streamlit_app.py` — linhas ~145-167 (import das funções de `pages.py`) e linhas ~561-572
  (chamada real de `render_relatorio_municipal_download_topo` no fluxo principal, com
  `selected_cities`/`selected_ufs` vindos do multiselect de cidades, definido em `pages.py`
  linha ~657) e a chamada de `render_relatorio_municipal_expander` em `pages.py` linhas 4219-4231
  (dentro do expander "Relatório Municipal" do Mapa Territorial).
- `tests/integration/test_streamlit_app.py` — linhas 4856-4909 (testes existentes do fluxo de
  1 município via `render_relatorio_municipal_download_topo`, mockam `agregar_municipio`,
  `render_mapas_municipio`, `gerar_payloads_download_relatorio_municipal`, `streamlit.button`,
  `streamlit.download_button`, `streamlit.session_state`) — usar como template dos novos testes.
- `tests/unit/test_relatorio_municipal.py` (linhas 1-80 lidas; contrato de `agregar_municipio`
  e `_sample_df`) — só para entender o formato de `municipio_result`, não para alterar.

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/pages.py` (alvo principal — as 2 funções e nada mais nesse
  arquivo, salvo imports/helpers estritamente necessários ao novo ramo)
- `tests/integration/test_streamlit_app.py` (novos testes do fluxo multi-município; testes
  existentes do fluxo de 1 município não devem precisar de alteração de asserção)
- `tasks/backlog.md` (marcar o bloco como concluído, ao final do ciclo — passo do orquestrador,
  não do Builder)
- `tasks/current_task.md`, `tasks/completed.md`
- `context/handoff.md`, `context/handoff/`

## Critérios de aceite
- Com 1 município selecionado: comportamento idêntico ao atual em ambos os pontos de geração
  (mesmos textos de botão/spinner/warning, mesmas `key`s de widget, mesma chave de cache
  `relmun_topo_payload::<nome>`); testes existentes `test_render_relatorio_municipal_topo_
  sem_municipio_unico_nao_renderiza` e `test_render_relatorio_municipal_topo_clique_gera_e_
  oferece_download` continuam verdes sem alteração de asserção.
- Com N > 1 municípios selecionados: um único botão "Gerar Relatórios (N)" aparece; ao clicar,
  gera N PDFs sob demanda (uma vez, não a cada rerun) com indicador de progresso; ao final, N
  `st.download_button` aparecem, um por município, rotulado com o nome do município, cada um
  com `key` único (sem colisão entre eles nem com o modo de 1 município).
- Município sem hexágonos (`n_hex_total == 0`) dentro do lote gera aviso individual identificando
  o município e NÃO aborta a geração dos demais municípios do lote.
- Reusa exclusivamente as funções existentes de `relatorio_municipal.py` já usadas no fluxo de 1
  município (`agregar_municipio`, `render_mapas_municipio`,
  `gerar_payloads_download_relatorio_municipal`) — nenhuma alteração em `relatorio_municipal.py`.
- Zero recálculo/alteração de `score_priorizacao`, `hex_score_estrutural`, pesos, carteira, plano,
  artefatos oficiais do M1, gate `flag_sam` ou critério de hexágono destacado (DEC-011).
- Sem dependência de rede nova (basemap/tiles seguem via `render_mapas_municipio(basemap=True)`,
  já existente, DEC-011).
- `pytest -q` (suíte completa) verde; `ruff` e `mypy` limpos no escopo alterado.
- Revisão visual humana aprovada (o bloco tem UI nova — o QA deve sinalizar quando revisão visual
  humana for necessária antes do fechamento, conforme critério de aceite do backlog).

## Criticidade classificada
Média — nova função de UI no fluxo de geração do Relatório Municipal; READ-ONLY sobre o M1; sem
DEC nova; reusa a geração existente do PDF sem alterar o motor. Já classificada assim no backlog
e em `tasks/current_task.md`; não há menção a `score_priorizacao`, `hex_score_estrutural`, pesos
ou artefatos oficiais do M1 que exigisse reclassificação para Crítica.

## Esteira recomendada
Block Orchestrator → Planner → Builder → QA (sem gate humano — decisões de produto já coletadas
de Vinicius em 2026-07-02 e registradas em `tasks/current_task.md`/`tasks/backlog.md`).

Tiering de modelo (já registrado em `tasks/current_task.md`, manter):
- Block Orchestrator: sonnet
- Planner: opus (override +1 — reestrutura o gate "1 município" em DOIS pontos de UI com
  session_state; risco de quebrar o caso de 1 município se o design do session_state for mal
  isolado)
- Builder: opus (override +1 — o expander hoje AUTO-GERA para 1 município sem botão; risco de
  regressão no fluxo de produção se o Builder não preservar essa assimetria entre os 2 pontos)
- QA: opus (sempre)

## Riscos identificados
- **Colisão de `session_state`:** a chave de cache do modo 1-município é
  `relmun_topo_payload::<nome_municipio>` (topo). O modo lote precisa de chave(s) distinta(s) que
  não colidam nem sejam sobrescritas ao alternar entre selecionar 1 e depois N municípios (ou
  vice-versa) no mesmo `session_state` da sessão Streamlit.
- **Assimetria hoje existente entre os dois pontos de geração:** `render_relatorio_municipal_
  download_topo` já é botão-triggered para 1 município; `render_relatorio_municipal_expander` hoje
  AUTO-GERA (sem botão) para 1 município. O Planner deve decidir explicitamente, e registrar no
  plano: (a) no modo `> 1`, ambos os pontos usam botão "Gerar Relatórios (N)" (recomendado, coerente
  com a decisão de gatilho do bloco), mantendo o auto-gen do expander SÓ para `== 1` — OU (b)
  também converter o expander em botão-triggered para `== 1`. A opção (b) alteraria o comportamento
  hoje em produção para 1 município (regressão potencial de UX) — se escolhida, deve ser explícita
  e justificada no plano, já que "preservar o fluxo de 1 município" é critério de aceite do
  backlog. Recomenda-se (a).
- **Custo de geração pesada em lote:** cada PDF envolve mapas com tiles (rede, DEC-011); gerar N
  sequencialmente pode ser lento — a decisão de produto já cobre isso com "indicador de progresso",
  mas o Planner deve garantir que o loop não dispare tiles/rede em paralelo de forma descontrolada
  nem quebre o fallback offline gracioso da DEC-011 (basemap=False em caso de falha por município,
  sem abortar o lote).
- **`key` de widgets Streamlit únicos:** nomes de município podem se repetir entre UFs diferentes
  (homônimos) — o `key` de cada `download_button`/estado interno do loop deve incluir UF além do
  nome para evitar colisão.
- **Duplicação de lógica entre os 2 pontos de geração:** ambos os pontos (topo e expander) vão
  precisar da mesma lógica de loop/progresso/cache multi-município; avaliar extrair um helper
  privado compartilhado dentro de `pages.py` (reduz risco de divergência entre os 2 pontos) — decisão
  de implementação do Planner, mantendo escopo restrito a `pages.py`.
- **Revisão visual humana:** o critério de aceite do backlog exige "revisão visual humana
  aprovada" — o QA deve sinalizar esse passo explicitamente antes de considerar o ciclo fechado
  (não é algo que o QA automatizado substitui).

## Guardrails ativos
- §5 CLAUDE.md (guardrail permanente): visualizações, relatórios e interações de UI não podem
  recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo,
  plano de domínio ou artefatos oficiais do M1 sem aprovação explícita. Este bloco é 100%
  READ-ONLY sobre o M1.
- §2 CLAUDE.md: não criar dependência de API ao vivo NOVA no dashboard de produção — este bloco
  não introduz rede nova, só reusa o caminho de tiles já existente e aprovado (DEC-011) via
  `render_mapas_municipio(basemap=True)`.
- §2 CLAUDE.md: toda mudança relevante entra com teste; nenhum PR sobe com CI quebrado.
- DEC-011 (§8): fundo de ruas por tiles online no Relatório Municipal já aprovado e vigente; este
  bloco não altera essa decisão, só reusa a função de mapas que já a implementa.
- Guardrail do Block Orchestrator: não expandir escopo, não resolver múltiplos blocos, não
  implementar nada nesta etapa.
