# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-CENSO-02 — Relatório censitário: template e visual padrão do PDF**

Dar ao PDF do Relatório Pontual Censitário (gerado por `gerar_pdf_relatorio_pontual_censitario`
em `censo_report.py`) um template e identidade visual Ultra: fundo extraído do `Teste Modelo.pptx`,
logos, cores turquesa/magenta, estrutura de seções aprovada por Felipe, painel de Big Numbers
com lookup de residual fitness/consumo pelo hex H3 do ponto, e último slide creditando o Motor
de Expansão — sem PII, sem internet na geração, sem tocar em M1/score/artefatos.

## Objetivo
Transformar o PDF leve-minimalista atual em um relatório com template padrão Ultra (fundo do
.pptx, logos, cores da marca) e estrutura de seções aprovada, mantendo geração offline e
READ-ONLY total sobre M1.

## Escopo permitido
- `src/motor_expansao/dashboard/censo_report.py` — reescrever/estender `gerar_pdf_relatorio_pontual_censitario` com template Ultra, nova estrutura de páginas e Big Numbers.
- `src/motor_expansao/dashboard/pages.py` — apenas na chamada de `render_downloads_relatorio_censitario` / `gerar_payloads_download_relatorio_censitario`, se precisar passar campos de residual/mercado novos ao writer.
- `pyproject.toml` — SOMENTE se uma nova dependência de PDF for aprovada no gate humano (decisão aberta — ver Riscos).
- `.gitignore` — apenas se for necessário ajuste adicional; a cobertura do PDF já existe (linha 103: `data/referencias/*.pdf`); o `.pptx` é intencionalmente rastreável (não gitignore-lo).
- `tests/unit/test_relatorio_pontual_censitario_export.py` — atualizar para a nova estrutura de seções + Big Numbers + template.
- `tests/integration/test_streamlit_app.py` — smoke/import limpo após mudanças.
- `docs/relatorio_pontual_censitario.md` — atualizar §7 (Export CSV e PDF) para refletir nova estrutura.
- `CLAUDE.md` §4 (linha do Relatorio Pontual Censitario) — atualizar descrição do PDF.
- `data/referencias/Teste Modelo.pptx` — LER (extrair background/identidade visual); NÃO modificar.
- `data/ultra/logo_ultra.png` — usar como asset (já existe no repo; confirmado `True`).

## Fora de escopo
- Qualquer recálculo ou escrita em artefatos M1 (`score_priorizacao`, `hex_score_estrutural`, `brasil_estrutural.parquet`, `brasil_priorizados.parquet`, carteira, plano ou qualquer outro artefato oficial).
- Mudar dados ou métricas das camadas (só apresentação e composição do PDF).
- Reintroduzir slide de endereço, micro-área ou polos de fluxo (removidos por decisão de Felipe).
- Geocodificação de endereço (escopo do BLK-PROD-05).
- Alterar o método de interseção `setor_censitario_intersecao_area_1p5km` ou o raio de 1.5 km.
- Tornar o dashboard interativo dependente de internet (DEC-004 vigente; tiles apenas na geração).
- Mudar `censo_map.py` ou as camadas de mapa (isso é escopo do BLK-CENSO-03).
- Alterar `gerar_csv_setores_censitarios` (inalterado).
- Recalcular ou reprocessar a camada de mercado/residual; apenas LEITURA do hex.

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/censo_report.py` — writer atual (entender PDF 1.4 manual, estrutura de páginas, `_build_pdf`, `_text_page`, `_map_content`, seções atuais)
- `src/motor_expansao/dashboard/censo_map.py` — entender o que as camadas retornam (dict `{densidade, renda, concorrentes}` em PNG bytes; `MAP_LAYER_TITLES`)
- `src/motor_expansao/dashboard/pages.py` — como `render_relatorio_pontual_censitario` chama o writer e quais dados já estão disponíveis no `result` (linhas 2479–2594)
- `src/motor_expansao/dashboard/censo_point.py` — campos que o `result` de `analisar_ponto_censitario_setores` retorna (fonte do Big Numbers censitário)
- `src/motor_expansao/dashboard/data.py` — helper de lookup do hex (como resolver hex_id a partir de lat/lng, e como ler os campos de mercado/residual já materializados)
- `data/referencias/Teste Modelo.pptx` — extrair paleta/cores/background Ultra para replicar no PDF
- `data/ultra/logo_ultra.png` — asset de logo para capa/cabeçalho
- `data/outputs/hexagonos_mercado_mapeado.parquet` OU `data/outputs/oportunidades_expansao_hibrido.parquet` — checar schema de colunas para `hex_id → score_oportunidade_residual / oferta_efetiva_disponivel / consumo concorrentes` (Big Numbers residual)
- `tests/unit/test_relatorio_pontual_censitario_export.py` — testes atuais a atualizar
- `CLAUDE.md` §2, §4 (Relatório Pontual Censitário; render lazy; Big Numbers — fonte dos campos)
- `docs/relatorio_pontual_censitario.md` — contrato atual §7 (Export CSV e PDF)
- `pyproject.toml` — dependências atuais (Pillow base; contextily em `[basemap]`; sem lib de PDF nova)

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/censo_report.py` — principal (template, estrutura, Big Numbers)
- `src/motor_expansao/dashboard/pages.py` — apenas chamada de download se precisar de campos extras
- `pyproject.toml` — apenas se nova lib de PDF aprovada no gate (decisão aberta)
- `tests/unit/test_relatorio_pontual_censitario_export.py`
- `tests/integration/test_streamlit_app.py`
- `docs/relatorio_pontual_censitario.md`
- `CLAUDE.md` §4

## Critérios de aceite
1. PDF sai com template/identidade Ultra: fundo extraído do `Teste Modelo.pptx`, logo Ultra (`data/ultra/logo_ultra.png`), cores turquesa/magenta nos cabeçalhos e rodapés.
2. Estrutura de seções aprovada (nesta ordem):
   - Página de **Capa** com logo + título + coordenada + município.
   - Página de **População** (mapa/choropleth `densidade` do BLK-CENSO-01).
   - Página de **Renda** (mapa/choropleth `renda` do BLK-CENSO-01).
   - Página de **Score censitário** (mapa `concorrentes` — score de contexto do BLK-CENSO-01).
   - Página de **Big Numbers** com as 6 métricas: pop total, renda média, score censitário médio/máximo, residual fitness (`score_oportunidade_residual`), qtd de concorrentes, consumo de concorrentes — ou "n/d" auditável quando a fonte não existir offline.
   - Página de **Concorrentes** (mapa + lista das redes no raio).
   - Último página de **Realização/Crédito**: "Relatório gerado pelo Motor de Expansão Ultra Academia" — SEM PII de pessoas.
3. **REMOVIDOS**: slide de endereço, slide de micro-área, slides de polos de fluxo.
4. **Big Numbers — fonte auditável**: pop/renda/scores do `result` de `analisar_ponto_censitario_setores`; residual fitness e consumo de concorrentes por lookup do hex H3 (res. 7) que contém a coordenada na camada de mercado/residual materializada — sem recalcular M1 nem residual; "n/d" com nota quando o hex não existir ou o campo estiver ausente.
5. Geração do PDF **offline-segura**: nenhuma chamada de rede no writer do PDF; sem dependência nova de internet.
6. **Nenhuma PII** de pessoas no template (sem nome/telefone/e-mail de terceiros).
7. PDF de referência (`data/referencias/*.pdf`) **gitignored** — JA COBERTO na linha 103 do `.gitignore` atual; confirmar antes de qualquer commit. O `.pptx` NÃO deve ser gitignored (é o fundo aprovado, rastreável).
8. Suite verde: `pytest -n auto` sem falhas, `ruff` limpo, `mypy` limpo.
9. `docs/relatorio_pontual_censitario.md` §7 atualizado com a nova estrutura.
10. **ZERO mudança** em artefatos M1 (score, pesos, carteira, plano, parquets oficiais).

## Criticidade classificada
**Média** (apresentação/diagramação; READ-ONLY sobre M1; não toca score/pesos/artefatos)

Não é Crítica: nenhuma alteração em `score_priorizacao`, `hex_score_estrutural`, `PESOS_HEX_SCORE_ESTRUTURAL`, carteira, plano ou artefatos oficiais do M1. Inclui `[REVISÃO HUMANA]` das decisões visuais (branding, lib de PDF, estrutura de Big Numbers) antes do Builder — conforme a esteira registrada em `tasks/current_task.md`.

## Esteira recomendada
Block Orchestrator (este handoff) → **Planner** → `[REVISÃO HUMANA das decisões visuais]` → Builder → QA

Nota de tiering (já registrado em `tasks/current_task.md`):
- Planner: Opus (override +1; extrair sistema de design do .pptx + decidir lib de PDF + cross-layer Big Numbers é atipicamente complexo para Média)
- Builder: Opus (override +1; template novo + assets de branding + Big Numbers via hex H3 + offline-safe; risco de regressão visual)
- QA: Opus 4.8 (sempre)

## Riscos identificados

1. **PII no template (bloqueador de commit — GUARDRAIL ATIVO)**: o PDF `Av. Wesley Dias Rodrigues, 1385 - Hortolândia, SP.pdf` em `data/referencias/` contém nome/telefone/e-mail reais. A regra `data/referencias/*.pdf` JÁ está no `.gitignore` (linha 103 confirmada). O Builder DEVE verificar esta cobertura ANTES de qualquer `git add`/`git commit`. Jamais reproduzir PII no template.

2. **Decisão aberta — lib de PDF (principal decisão técnica do bloco)**: o writer atual é manual (PDF 1.4 em Python puro + Pillow). Funcional, mas limitado para backgrounds de alta fidelidade, fontes TTF embutidas e layouts ricos. Trocar por lib mais capaz (`reportlab`, `fpdf2`, `weasyprint`) é PERMITIDO APENAS SE aprovado no gate `[REVISÃO HUMANA]`. O Planner deve avaliar: (a) a lib roda 100% offline?; (b) custo de dependência no `pyproject.toml` e na imagem Docker?; (c) complexidade de migração vs. benefício visual?. Se não aprovada, o Builder estende o writer atual.

3. **Extração do fundo do .pptx**: `data/referencias/Teste Modelo.pptx` é o fundo aprovado. O Planner deve avaliar se usa `python-pptx` (verificar se já é dependência antes de propor adicionar) ou extrai o background como imagem PNG/JPEG manualmente (mais simples, sem dep nova).

4. **Lookup do hex para Big Numbers residual**: a coordenada `lat/lng` deve ser convertida em `hex_id` H3 (resolução 7 — `H3_RESOLUTION = 7` em `config.py`) para lookup nos parquets de mercado. Verificar qual parquet já está em `data/outputs/` e tem `score_oportunidade_residual` / `oferta_efetiva_disponivel` / consumo de concorrentes — candidatos: `hexagonos_mercado_mapeado.parquet` ou `oportunidades_expansao_hibrido.parquet`. O lookup é LEITURA simples; se o hex não existir ou o campo for NaN, exibir "n/d" sem inventar valor.

5. **Peso de assets de branding no repo**: logos e background extraído do .pptx (PNG/JPEG) podem pesar no repo. Preferir PNGs otimizados; evitar embutir assets binários grandes sem necessidade.

6. **Não regredir BLK-CENSO-01**: o template novo consome as 3 camadas de mapa como imagens (PNG bytes do dict `{densidade, renda, concorrentes}`); não deve removê-las nem alterar `censo_map.py`.

7. **Deploy**: BLK-CENSO-02 é puramente Python/geração de PDF em memória; não exige rebuild de imagem se não adicionar dependência nova. Se nova lib de PDF for aprovada, rebuild de imagem + redeploy por digest na VPS será necessário (confirmar com Felipe antes de executar — guardrail VPS §6).

## Guardrails ativos
- `CLAUDE.md §5` guardrail permanente: "visualizacoes, analise radial e interacoes de mapa nao podem recalcular ou alterar score_priorizacao, hex_score_estrutural, carteira, plano curto prazo, plano dominio ou artefatos oficiais do M1 sem aprovacao explicita."
- `CLAUDE.md §2`: "Nao criar dependencia de API ao vivo no dashboard de producao."
- `CLAUDE.md §2`: Interpretação de criticidade — LEITURA/ANÁLISE sem escrita em M1 = Alta; ALTERAÇÃO de fórmula/pesos/artefatos = Crítica. Este bloco é Média (camada de apresentação, nem leitura de score nem alteração de M1).
- `DEC-004`: fundo de ruas por tiles online permitido SOMENTE no caminho de geração do Relatório Pontual Censitário; dashboard interativo NÃO depende de internet. BLK-CENSO-02 herda este contexto — a geração do PDF não introduz novos fetches de tiles.
- `DEC-001`: pesos `renda=0.40`/`pop=0.60` e fórmula do `score_priorizacao` INALTERADOS — este bloco não os toca.
- Guardrail de PII: `data/referencias/*.pdf` gitignored (linha 103 do `.gitignore`); jamais reproduzir PII no template; `Teste Modelo.pptx` é o único arquivo rastreável em `data/referencias/`.
- Guardrail de infra VPS (`CLAUDE.md §6`): nenhum comando SSH sem confirmação explícita individual. Se rebuild de imagem for necessário (nova dep aprovada), reportar ao usuário antes de executar.
