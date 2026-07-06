# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (esteira do bloco: Planner → [confirmação humana — produto: D1/D2/D3] → Builder → QA)

## Bloco refinado
BLK-RELPON-04 — Relatório Pontual em lote (fila de endereços pesquisados). Nova função de UI no
Streamlit que acumula endereços/coordenadas pesquisados numa fila (`session_state`) e permite gerar
N Relatórios Pontuais Censitários (raio 1,5 km) sob demanda, com progresso i/N e dois modos de
download, replicando nos dois pontos existentes da página (topo e inferior) o padrão de lote já
usado no BLK-RELMUN-04 para o Relatório Municipal.

## Objetivo
Permitir gerar em lote o Relatório Pontual Censitário a partir de uma fila de endereços pesquisados,
sem alterar o núcleo `censo_*` nem qualquer artefato do M1.

## Escopo permitido
- Fila de endereços/coordenadas em `session_state` (chave dedicada, distinta de `multihex_cenario` e
  de `relmun_lote_topo_payloads`): cada item guarda `(rotulo_endereco, lat, lng)`; sobrevive a rerun.
- Controles de fila espelhando o padrão do multihex (`btn_multihex_add`/`_remove`/`_clear`, linhas
  ~2595-2650 de `pages.py`): adicionar o ponto pesquisado atual (`search_pin` de
  `render_coord_search_sidebar`), remover item específico, limpar tudo.
- Botão "Gerar Relatorios Pontuais (N)" reusando o padrão de lote já implementado em
  `render_relatorio_municipal_download_topo` (bloco `> 1 municipio`, linhas ~3191-3233 de `pages.py`):
  loop pela fila chamando `gerar_payloads_relatorio_pontual_para_pin` (linha ~2932, sem alterá-la),
  `st.progress` com texto i/N, cache dos payloads em `session_state` por ponto.
- Dois pontos de renderização na página: junto de `render_pdf_download_topo` (topo, ~linha 2989) e
  dentro/próximo de `render_relatorio_pontual_censitario` (inferior, ~linha 3236), reusando a MESMA
  fila (session_state compartilhado) conforme D3.
- Dois modos de download: (a) lote — um `st.download_button` por endereço da fila, rotulado
  "Baixar PDF — <endereço>", `key` único (padrão de `dl_relmun_lote_topo_*`); (b) atalho "Baixar
  apenas o último solicitado" (o ponto mais recentemente adicionado à fila).
  Formato exato do modo lote definido por D1.
- Passar o texto do endereço pesquisado como `rotulo` (parâmetro opcional já existente na cadeia de
  geração do PDF pontual, emenda DEC-005) para cada item do lote sair identificado na capa.
- Adicionar as novas `st-key` dos botões de lote/fila à regra CSS de 260px existente em
  `inject_styles` (~linhas 441-448), no MESMO padrão de `.st-key-btn_gerar_relmun_lote_topo` /
  `.st-key-btn_gerar_relmun_lote_expander`. Proibido usar `use_container_width`.
- Testes novos/ajustados cobrindo: fila vazia (fluxo atual preservado), fila com 1 item, fila com
  N>1 (progresso, N downloads + atalho "último"), remoção/limpeza da fila, largura CSS, anti-PII
  (fila nunca escrita em disco/log).

## Fora de escopo
- Núcleo `censo_*` (`censo_point.py`/`censo_map.py`/`censo_report.py`): método de intersecção
  `setor_censitario_intersecao_area_1p5km`, raio 1,5 km, `RAIO_CENSITARIO_DEFAULT_KM`, estrutura das
  páginas do PDF, marca d'água anti-PII (BLK-EST-03), `set_compression(False)` — SÓ CONSUMIR.
- `score_priorizacao`, `hex_score_estrutural`, qualquer artefato oficial do M1, `flag_sam`.
- Relatório Municipal (`render_relatorio_municipal_download_topo` e afins) — já resolvido no
  BLK-RELMUN-04/-04-FU1; serve só de PRECEDENTE de padrão, não deve ser alterado por este bloco.
- Qualquer dependência de rede nova (geocoding via Nominatim/DEC-010 e tiles/DEC-004 já existem e
  não devem ganhar novo caminho de rede).
- Persistência da fila em disco/log/cache — deve viver só em `session_state` (efêmera, anti-PII).
- Introdução de `.zip` como MODO ÚNICO de download em lote sem decisão humana (ver D1) — se incluído,
  deve ser ADICIONAL aos N botões rotulados, nunca substituí-los sem aprovação explícita.

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/pages.py` (arquivo inteiro relevante às âncoras abaixo):
  - `inject_styles` (~linha 154; regra CSS 260px em ~441-448)
  - `render_coord_search_sidebar` (~linha 769) — devolve `search_pin: tuple[float, float] | None`
  - `_render_multihex_controls` (~linha 2595) — precedente de fila em `session_state` (add/remove/clear)
  - `gerar_payloads_relatorio_pontual_para_pin` (~linha 2932) — NÃO alterar assinatura/núcleo
  - `render_pdf_download_topo` (~linha 2989) — ponto de geração superior (fluxo de 1 ponto)
  - `render_relatorio_municipal_download_topo` (~linha 3107, bloco `> 1 municipio` em ~3191-3233) —
    PADRÃO DE LOTE A REPLICAR (progresso i/N, cache em `session_state`, N `download_button`s)
  - `render_relatorio_pontual_censitario` (~linha 3236) — ponto de geração inferior
- `tasks/backlog.md` linhas ~1259-1340 (especificação completa do bloco, já lida por este
  Block Orchestrator)
- `CLAUDE.md` §2 (sem API ao vivo no dashboard), §4 (Relatório Pontual Censitário 1.5 km), §5
  (guardrail permanente READ-ONLY M1), DEC-004/DEC-010 (tiles/geocoding já aprovados, não reabrir)
- `tests/` — localizar suíte existente de `render_pdf_download_topo` /
  `render_relatorio_municipal_download_topo` / multihex para seguir o mesmo padrão de teste

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/pages.py` (fila de endereços, botões de lote, CSS de largura —
  SEM tocar `censo_point.py`/`censo_map.py`/`censo_report.py`)
- `tests/` (testes novos/ajustados da fila e do lote de UI)
- `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md` (fechamento do bloco)
- `context/handoff.md`, `context/handoff/`

## Critérios de aceite
- Com a fila contendo >1 endereço, um botão gera N Relatórios Pontuais sob demanda (com progresso
  i/N visível) e oferece download em lote (1 por endereço, rotulado com o endereço) E um atalho
  "baixar apenas o último solicitado".
- Com fila vazia ou 1 ponto, o fluxo atual de 1 ponto (`render_pdf_download_topo` / fluxo inferior)
  é preservado byte-a-byte.
- Botões novos têm a mesma largura (260px) dos demais, via CSS `st-key` (sem `use_container_width`).
- A opção de fila/lote aparece nos DOIS pontos da página (topo, perto do menu; inferior, no Mapa
  Territorial), compartilhando a mesma fila (conforme D3).
- Cada PDF do lote sai com o endereço pesquisado como rótulo/identificação da capa.
- Fila NUNCA é persistida em disco/log (só `session_state`).
- Suíte de testes verde; ruff+mypy limpos; revisão visual humana aprovada.
- Zero alteração em `score_priorizacao`, artefatos oficiais do M1 ou núcleo `censo_*`.

## Criticidade classificada
Média — confirmada. Justificativa: é uma feature de UI (mecanismo de fila + geração/download em
lote) que reusa integralmente funções de geração e busca já existentes e aprovadas
(`gerar_payloads_relatorio_pontual_para_pin`, `render_coord_search_sidebar`, DEC-010/DEC-004); não
introduz DEC nova, não toca `score_priorizacao`/`hex_score_estrutural`/pesos/carteira/plano/
artefatos oficiais do M1, não altera o núcleo `censo_*`, e não abre caminho de rede novo. O único
motivo de não ser "Baixa" é que envolve 3 decisões de produto (D1/D2/D3) que mudam a UX observável
e por isso exigem confirmação humana antes do Builder — mesmo padrão de criticidade já usado no
BLK-RELMUN-04 precedente.

## Esteira recomendada
Block Orchestrator (concluído) → Planner → [confirmação humana — produto: D1/D2/D3] → Builder → QA
(QA sempre em Opus 4.8, conforme tiering do ciclo em `tasks/current_task.md`).

## Decisões de produto a confirmar (D1/D2/D3) — devem chegar ao gate humano SEM ambiguidade
- **D1 — Formato do "baixar em lote":** N botões de download rotulados por endereço (replicando
  exatamente o padrão do BLK-RELMUN-04: `dl_relmun_lote_topo_*`) OU um único arquivo `.zip` com
  todos os PDFs. Recomendação do backlog: manter consistência (N botões) e, se houver apetite,
  ADICIONAR um `.zip` como conveniência extra — nunca substituir os N botões sem aprovação.
- **D2 — Gatilho de acúmulo à fila:** botão explícito "Adicionar à fila" acionado pelo operador após
  pesquisar um ponto (recomendado — espelha o multihex, evita poluir a fila com buscas
  exploratórias) VS. acumular automaticamente toda busca feita em `render_coord_search_sidebar`.
- **D3 — Escopo da fila entre os dois pontos da página:** fila COMPARTILHADA (mesma chave de
  `session_state`) entre o botão do topo e o do rodapé (recomendado, permite operar de qualquer
  lugar da página) VS. duas filas independentes (uma por ponto de renderização).

## Riscos identificados
- Colisão de nomes de `session_state`/`key` com as chaves já usadas pelo multihex
  (`multihex_cenario`, `btn_multihex_*`) e pelo lote municipal (`relmun_lote_topo_payloads`,
  `btn_gerar_relmun_lote_topo`, `dl_relmun_lote_topo_*`) — usar chaves com prefixo próprio
  (ex.: `relpon_lote_*`) para não colidir nem reaproveitar estado alheio.
- Regra CSS de 260px é global por `st-key`; qualquer novo botão de lote/fila deve entrar
  explicitamente na lista de seletores em `inject_styles`, senão sai com largura padrão do Streamlit
  (regressão visual silenciosa — já ocorreu no BLK-RELMUN-04, corrigido no FU1).
- Geração de N relatórios pesados em sequência pode ser lenta (cada Relatório Pontual carrega base
  setorial + gera mapas com basemap online); o padrão de `st.progress` i/N do BLK-RELMUN-04 já
  mitiga a percepção, mas vale registrar no handoff do Builder para não prometer paralelismo.
- Se D2 = acúmulo automático, a fila pode crescer sem limite com buscas exploratórias, aumentando
  tempo/uso de memória do lote e o rótulo da capa pode ficar poluído com pontos não desejados —
  reforça a recomendação de D2 = botão explícito.
- Anti-PII: a fila fica em memória do processo Streamlit (multiusuário/multissessão); confirmar que
  `session_state` já é isolado por sessão (padrão do Streamlit) e que nenhum novo ponto de log/print
  grava endereços da fila.

## Guardrails ativos
- §2 (CLAUDE.md): "Nao criar dependencia de API ao vivo no dashboard de producao" — este bloco NÃO
  abre caminho de rede novo (geocoding/tiles já cobertos por DEC-010/DEC-004); qualquer sugestão de
  nova chamada de rede deve ser rejeitada pelo Planner/Builder.
- §4/§5 (CLAUDE.md): Relatório Pontual Censitário 1,5 km é núcleo `censo_*` — método de intersecção,
  raio, estrutura do PDF e marca d'água anti-PII (BLK-EST-03) são **INTOCADOS**, só consumidos.
  Guardrail permanente do §5: "visualizacoes, analise radial e interacoes de mapa nao podem
  recalcular ou alterar score_priorizacao, hex_score_estrutural, carteira, plano curto prazo, plano
  dominio ou artefatos oficiais do M1 sem aprovacao explicita."
- Anti-PII: a fila de endereços vive só em `session_state` (efêmera); nunca persistida em
  disco/log/cache.
- Um bloco por vez: este handoff cobre exclusivamente BLK-RELPON-04; não expandir para o Relatório
  Municipal ou qualquer outro bloco do backlog.
