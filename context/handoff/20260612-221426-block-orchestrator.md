# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Builder (esteira Baixa: Block Orchestrator → Builder direto, sem Planner)

## Bloco refinado
BLK-EST-04 — Trocar a imagem de capa do Relatório Pontual Censitário (dashboard + API)

## Objetivo
Substituir o asset `data/ultra/relatorio_capa_bg.png` no VPS pela nova versão de Felipe, confirmar que título/subtítulo/raio ficam legíveis sem colisão na capa do PDF, e ajustar `_cover_page` SOMENTE SE o render mostrar colisão ou ilegibilidade.

## Escopo permitido
- Verificação VISUAL do PDF gerado com o novo asset (renderizar a capa com `gerar_pdf_relatorio_pontual_censitario` ou script ad-hoc que instancie `_cover_page` diretamente).
- Ajuste de constantes de posição/tamanho em `_cover_page` (`block_x`, `block_w`, `title_y` e derivados) SOMENTE se o render mostrar colisão com o logo "GRUPO ultra" ou com a faixa branca de parceiros, ou ilegibilidade do texto branco.
- Ajuste de `pdf.set_text_color` em `_cover_page` para outra cor (ex.: turquesa escuro ou cinza) SOMENTE se o texto branco ficar ilegível sobre o fundo da nova capa.
- Atualização de `tasks/current_task.md`, `tasks/backlog.md` e `tasks/completed.md` no fechamento do bloco.
- Atualização de `context/handoff.md` e snapshot em `context/handoff/`.
- Deploy via `scp` do arquivo `relatorio_capa_bg.png` para `/opt/motor-expansao/data/ultra/` no VPS (com confirmação humana por comando individual, conforme guardrail §6).

## Fora de escopo
- `score_priorizacao`, `hex_score_estrutural`, pesos `renda=0.40`/`pop=0.60`, artefatos oficiais do M1 (READ-ONLY, intocados).
- Método de interseção `setor_censitario_intersecao_area_1p5km` e raio 1.5 km (intocados).
- Estrutura de 7 páginas, ordem das páginas, `/Count 7`, `PDF_SECTION_HEADERS` (intocados).
- Grid 4×2 de Big Numbers, `set_compression(False)`, versão PDF 1.4 (intocados).
- Qualquer outra função além de `_cover_page` (e constantes de posição usadas somente por ela).
- Rebuild de imagem Docker — o asset é gitignored e lido em runtime do volume montado; não exige rebuild.
- Versionamento do asset no git — `data/ultra/relatorio_capa_bg.png` é gitignored e NUNCA entra em commit.
- `image24.png` (PII) — nunca embutir, seguir guardrail existente.
- Modificações no caminho da API além do que é herdado pelo asset compartilhado (ambos os caminhos usam o mesmo `_cover_page` e o mesmo volume `data/ultra`).

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/censo_report.py` — inteiro (foco nas linhas 55-80 para constantes e 297-355 para `_cover_page` e `_draw_full_page_background`).
- `CLAUDE.md` — §4 (Relatório Pontual Censitário e BLK-EST-02), §2 (guardrails), §6 (guardrails VPS), DEC-004, DEC-005 emenda.
- `tasks/current_task.md` — estado atual do bloco.
- `tasks/backlog.md` — entrada BLK-EST-04 (linhas ~266-288).

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/censo_report.py` — SOMENTE `_cover_page` (constantes de posição `block_x`/`block_w`/`title_y` ou cor do texto), e SOMENTE se o render confirmar colisão ou ilegibilidade. Se não houver colisão, este arquivo NÃO é tocado.
- `tasks/current_task.md`
- `tasks/completed.md`
- `tasks/backlog.md`
- `context/handoff.md`
- `context/handoff/` (snapshot append-only)

## Critérios de aceite
1. **VISUAL (critério central):** renderizar o PDF com o novo asset e confirmar que "Relatorio Pontual Censitario" (30 pt bold branco), subtítulo (13 pt) e "Raio de analise: X km" (13 pt) ficam LEGÍVEIS e SEM colidir com o logo "GRUPO ultra" (centro-direita da imagem) e a faixa branca de parceiros (Ultra/Spider Kick/The Flame, parte inferior). O bloco de texto fica em `block_x=478`, `title_y=330` (título em y=330), subtítulo em y=400, raio em y=422 — verificar empiricamente se a faixa branca começa antes de y≈440 na escala de página 960×540 pt.
2. **Ambos os caminhos cobertos:** o asset é compartilhado (um `scp` atualiza dashboard e API simultaneamente via volume montado); confirmar que ambos usam o mesmo `_cover_page` e o mesmo asset (não requer teste separado por caminho se o código for o mesmo).
3. **Zero mudança de código se não houver colisão:** se o render mostrar que o texto cabe na zona limpa, o commit de código não existe — só o deploy VPS.
4. **Se houver colisão:** ajuste cirúrgico de `block_x`/`block_w`/`title_y` (ou cor) em `_cover_page`; suite de testes existentes não pode quebrar; `ruff` e `mypy` limpos; smoke `import streamlit_app` ok.
5. **Deploy VPS executado com confirmação humana:** `scp <path_local>/relatorio_capa_bg.png root@2.25.137.241:/opt/motor-expansao/data/ultra/` com confirmação explícita do usuário antes de cada comando no servidor.
6. **Sem PII versionada:** asset gitignored; nenhum PNG/PPTX de branding entra em commit.

## Criticidade classificada
**Baixa** — troca de asset de branding gitignored; sem toque em score, M1, fórmula, pesos, artefatos oficiais, raio ou método de interseção. O único risco relevante é colisão de layout (verificável antes do deploy), e o ajuste, se necessário, é cirúrgico e restrito a constantes de posição em uma única função.

## Esteira recomendada
Block Orchestrator → **Builder** (sem Planner — criticidade baixa)

Tiering de modelo:
- Block Orchestrator: sonnet
- Builder: sonnet
- (sem QA de ciclo completo — criticidade baixa; smoke da suite pode rodar após o commit de ajuste, se houver)

## Riscos identificados
1. **Colisão de texto com a faixa branca de parceiros:** a faixa branca começa na parte inferior da imagem (1360×763 px); mapeada para a página 960×540 pt, a faixa começa estimada em y_pt≈455 pt (y_px/763×540, onde y_px≈643 se a faixa ocupa os últimos ~120 px). O texto mais baixo fica em title_y+92=422 pt, borda inferior ≈440 pt. Margem estimada ~15 pt — estreita. O render confirma ou invalida; se colidir, reduzir `title_y` ou deslocar o bloco para cima.
2. **Texto branco sobre área clara:** a zona entre o logo "GRUPO ultra" e a faixa branca pode ter fundo turquesa claro ou gradiente claro da foto — o texto branco pode ficar ilegível. Mitigação: verificar no render; se necessário, mudar cor para turquesa escuro/cinza ou adicionar retângulo semitransparente de fundo.
3. **Asset não encontrado em produção:** se o `scp` falhar ou o path no VPS estiver incorreto, o fallback é turquesa sólido (comportamento existente — não é regressão). Mitigação: confirmar path antes do `scp`.
4. **GUARDRAIL §6 VPS:** qualquer comando no servidor exige confirmação humana individual — não encadear comandos sem aprovação intermediária.

## Guardrails ativos
- **§2:** Sem dependência de API ao vivo no dashboard de produção. Toda mudança relevante entra com teste; nenhum PR deve subir com CI quebrado.
- **§4 guardrail permanente:** visualizações e interações de mapa não podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano ou artefatos oficiais do M1 sem aprovação explícita. Este bloco é READ-ONLY sobre o M1.
- **§6 GUARDRAIL ABSOLUTO:** nunca executar qualquer comando no servidor via MCP (ou qualquer tool SSH) sem confirmação explícita do usuário para cada comando individual. Isso inclui `scp`, `git pull`, `docker compose`, `chmod`, `rm` e qualquer outro. Não encadear múltiplos comandos sem aprovação intermediária.
- **DEC-004:** tiles online restritos ao caminho de geração do relatório; fallback offline gracioso.
- **DEC-005 emenda (2026-06-12):** a API pode estender `censo_report.py` com parâmetros opcionais de render; o núcleo (raio, método de interseção, score) permanece intocado.
- **Anti-PII:** `.pptx`/PDF nunca versionados; `image24.png` nunca embutido; `data/ultra/relatorio_capa_bg.png` gitignored.

## Contexto técnico adicional para o Builder
- Página PDF: 960×540 pt (16:9). Asset lido como bytes e passado em `assets["capa"]`.
- `_draw_full_page_background`: coloca o PNG em `x=0, y=0, w=960, h=540` (estica para preencher a página inteira).
- `_cover_page` com `has_bg=True`: `block_x=478.0`, `block_w=446.0`, `align="L"`, `title_y=330.0`.
  - Título: `set_xy(478, 330)`, `multi_cell(446, 32, ...)`, 30 pt bold, branco.
  - Subtítulo: `set_xy(478, 400)`, `cell(446, 18, ...)`, 13 pt, branco.
  - Raio: `set_xy(478, 422)`, `cell(446, 18, ...)`, 13 pt, branco.
  - Borda inferior do bloco de texto: y≈440 pt.
- Nova imagem (1360×763 px): mapeada linearmente para 960×540 pt. Faixa branca inferior — localização exata deve ser confirmada pelo render do PDF.
- Fallback sem asset: `block_x=40.0, block_w=880.0, align="C", title_y=230.0` — texto centralizado sobre turquesa sólido (não afetado por esta tarefa).
- Dashboard e API usam o mesmo `gerar_pdf_relatorio_pontual_censitario` → `_cover_page` → asset `relatorio_capa_bg.png` do volume montado em `/opt/motor-expansao/data/ultra/`. Um `scp` atualiza os dois.
