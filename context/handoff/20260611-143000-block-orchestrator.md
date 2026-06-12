# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-EST-01 — Marca d'água + nome do solicitante nos PDFs do Relatório Pontual Censitário

## Objetivo
Embutir marca d'água diagonal com texto fixo "Ultra Academia" e nome do solicitante em todas as 7 páginas do PDF gerado por `gerar_pdf_relatorio_pontual_censitario`, de forma legível e não separável do content stream, sem versionar PII e preservando compressão de stream OFF.

## Escopo permitido
- `src/motor_expansao/dashboard/censo_report.py` — único arquivo de produção a alterar
- Adicionar parâmetro `solicitante: str | None = None` em `gerar_pdf_relatorio_pontual_censitario`, `gerar_payloads_download_relatorio_censitario` e `render_downloads_relatorio_censitario` (passagem em cascata transparente, retrocompat por default)
- Nova função privada `_draw_watermark(pdf, text)` chamada em cada página após o conteúdo e antes do `output()`
- Testes correspondentes em `tests/unit/test_relatorio_pontual_censitario_export.py`

## Fora de escopo
- Qualquer alteração em `score_priorizacao`, `hex_score_estrutural`, carteira, plano ou artefatos oficiais do M1 (READ-ONLY absoluto)
- Versionar PDFs reais (PII) ou fixtures com nome de pessoa real
- Embutir `image24.png` (anti-PII, §4 CLAUDE.md)
- Implementar integração com Authelia/sessão autenticada — fora do MVP deste bloco
- Alterar `pages.py` além da propagação mínima do parâmetro (se necessário)
- Criar dependência de API ao vivo
- Alterar a API (`src/motor_expansao/api/`) — ela não existe ainda; o contrato de parâmetro deve ser compatível quando existir (DEC-005), mas não requer implementação agora
- Alterar o template visual das 7 páginas além da camada de marca d'água

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/censo_report.py` — função pública `gerar_pdf_relatorio_pontual_censitario` (linha 511), classe `_UltraPDF` (linha 171), funções de página (`_cover_page`, `_map_page`, `_big_numbers_page`, `_competitors_page`, `_credit_page`)
- `tests/unit/test_relatorio_pontual_censitario_export.py` — suite existente a preservar; `test_pdf_sem_pii_de_pessoas` (linha 195) com `_PII_FORBIDDEN` que deve continuar passando
- `src/motor_expansao/dashboard/pages.py` — chamador `render_downloads_relatorio_censitario` (linha 2619) para verificar propagação do parâmetro
- `CLAUDE.md` §2 (anti-PII), §4 (censo_report.py, compressão OFF), §5 (guardrails READ-ONLY M1)

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/censo_report.py`
- `tests/unit/test_relatorio_pontual_censitario_export.py`

## Decisões a resolver no gate humano (antes do Builder)

### D1 — Fonte do nome do solicitante
**Ambiguidade confirmada:** o backlog cita "sessão autenticada (Authelia)", mas não há nenhuma integração Authelia no código hoje. Busca por `authelia`, `solicitante`, `usuario_logado`, `X-Remote-User`, `identity` em todo `src/` retornou zero resultados. A sessão Streamlit (`st.session_state`) também não expõe identidade de usuário.

**Proposta de contrato mínimo para o Builder:** parâmetro `solicitante: str | None = None` em `gerar_pdf_relatorio_pontual_censitario`. Quando `None`, texto da marca d'água usa somente "Ultra Academia" (sem nome). Quando preenchido, exibe "Ultra Academia | {solicitante}". O chamador em `pages.py` passa `None` por ora; quando Authelia for integrada (bloco futuro), basta passar o header/session nesse parâmetro.

**Ponto de decisão para Felipe:** aceitar este contrato mínimo (valor `None` com fallback seguro), ou bloquear o bloco até a integração Authelia existir?

### D2 — Posição e conteúdo da marca d'água
**Proposta:** texto diagonal sobreposto em cada página após renderizar o conteúdo, centralizado, rotacionado ~45°, cor cinza semi-transparente (alpha baixo via `set_alpha`), fonte Helvetica tamanho ~60 pt. Texto = "Ultra Academia" quando `solicitante=None`; "Ultra Academia | {solicitante}" quando preenchido.

**Alternativas a decidir:**
- (a) Marca d'água apenas na capa — menor impacto visual, mas não cobre todas as 7 páginas
- (b) Marca d'água em todas as 7 páginas — máxima rastreabilidade LGPD (recomendado pelo backlog)
- (c) Rodapé em cada página com "Gerado para: {solicitante}" — mais discreto, porém não é marca d'água diagonal

**Ponto de decisão para Felipe:** qual opção (a/b/c) e qual texto exato?

### D3 — "Não removível trivialmente" com fpdf2
**Clarificação técnica:** com `set_compression(False)` (já ativo em `_UltraPDF.__init__`), o texto da marca d'água será embutido em claro no content stream de cada página como operadores PDF (`BT ... ET`), sem camada separada nem anotação (`/Annot`). Isso significa: (1) não é um overlay separável por ferramentas PDF padrão; (2) o texto aparece em claro nos bytes do arquivo (verificável por `assert b"Ultra Academia" in pdf_bytes`). Atende ao guardrail de auditabilidade anti-PII e ao requisito "não removível trivialmente".

### D4 — Cascata pela API (DEC-005)
`src/motor_expansao/api/` ainda não existe (BLK-API-02+ não implementado). O parâmetro `solicitante: str | None = None` deve ser definido com default `None` já agora em `gerar_pdf_relatorio_pontual_censitario`, para que quando a API nascer ela simplesmente passe o token/identidade do consumidor nesse campo (conforme DEC-005, §6: "token por consumidor/bot"). Nenhum código de API é criado neste bloco.

### D5 — Anti-PII: nome do solicitante em fixtures de teste
O nome do solicitante (usuário interno Ultra) aparece no content stream do PDF, mas o PDF em si não é versionado (gitignored). O teste `test_pdf_sem_pii_de_pessoas` verifica `_PII_FORBIDDEN` (strings ligadas ao cartão de contato `image24.png`); esse teste deve continuar passando. O Builder deve usar string fictícia (ex.: `"Analista Teste"`) nas fixtures — NUNCA nome/e-mail real.

## Critérios de aceite
1. `gerar_pdf_relatorio_pontual_censitario(..., solicitante="Analista Teste")` produz PDF com `b"Ultra Academia"` e `b"Analista Teste"` nos bytes crus (stream OFF garante legibilidade direta).
2. `gerar_pdf_relatorio_pontual_censitario(..., solicitante=None)` produz PDF com `b"Ultra Academia"` e SEM texto de solicitante — default seguro e retrocompat.
3. Estrutura de 7 páginas preservada (`b"/Count 7"` presente).
4. `test_pdf_sem_pii_de_pessoas` continua passando — as strings `_PII_FORBIDDEN` não mudam.
5. Compressão de stream OFF preservada (`_UltraPDF.set_compression(False)` intocado).
6. Marca d'água presente nas páginas configuradas conforme decisão D2 (aguarda gate humano).
7. Suite completa verde (`pytest -q`); ruff + mypy limpos.
8. READ-ONLY M1: nenhum artefato oficial alterado; `score_priorizacao` intocado.
9. `pages.py` não quebra — passagem de `solicitante=None` implícita por default.

## Criticidade classificada
**Alta** — rastreabilidade/LGPD; camada de visualização READ-ONLY sobre o M1. NÃO é Crítica: não altera `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio nem qualquer artefato oficial do M1. Confirmado pela regra operacional CLAUDE.md §2: "LEITURA/ANÁLISE de score sem escrita em artefato M1 → Alta".

## Esteira recomendada
Block Orchestrator (concluído) → **Planner** → `[REVISÃO HUMANA — gate D1/D2]` → Builder → QA

## Riscos identificados
- **R1 — Authelia inexistente:** a fonte "sessão autenticada" citada no backlog não existe no código; entregar com `solicitante=None` é seguro, mas o nome ficará vazio até a integração. Coordenar com a tarefa de logs LGPD do Felipe (ClickUp `86e1rtezm`).
- **R2 — Marca d'água sobre fundo de imagem:** páginas com asset de branding (`_cover_page`, `_map_page`) sobrepõem PNGs como camada de fundo; a marca d'água deve ser desenhada APÓS a imagem de fundo para ficar visível sobre qualquer fundo.
- **R3 — Rotação em fpdf2:** `FPDF` pode exigir transformação de matriz via contexto `with pdf.local_context()` + `set_stretching`/`rotate`; o Builder deve confirmar a API exata da versão instalada antes de implementar.
- **R4 — PII em testes:** o Builder deve usar nome fictício nas fixtures; nunca nome/e-mail real de usuário Ultra.
- **R5 — Propagação em `pages.py`:** a chamada atual (linha 2619) usa `render_downloads_relatorio_censitario` sem `solicitante`; com default `None` isso não quebra. Se Felipe decidir por `solicitante` obrigatório, `pages.py` precisará de alteração mínima — registrar como item do plano.

## Guardrails ativos
- **§2 CLAUDE.md:** anti-PII absoluto — PDFs nunca versionados; `image24.png` nunca embutido; fixtures sem PII real.
- **§4 CLAUDE.md:** `censo_report.py` é interface estável; compressão de stream OFF preservada; assinatura pública só pode ser EXPANDIDA com parâmetros opcionais (retrocompat obrigatória).
- **§5 CLAUDE.md:** visualizações READ-ONLY sobre M1; marca d'água é camada visual, não altera score/artefatos.
- **DEC-004:** tiles online só no caminho de geração do relatório; marca d'água é offline-safe por construção (texto puro fpdf2).
- **DEC-005:** parâmetro `solicitante` deve ser compatível com a futura API; default `None` garante isso.
- **GUARDRAIL ABSOLUTO §6:** nenhum comando no VPS sem confirmação explícita do usuário.
