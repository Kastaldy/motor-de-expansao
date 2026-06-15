# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
**Planner** — o bloco é executável AGORA, mas somente na **trilha da API** (recorte A).
A trilha do dashboard permanece bloqueada (nenhuma fonte de identidade existe no Streamlit); o Planner deve detalhar o plano para o recorte executável e registrar a trilha do dashboard como dependência pendente (Authelia ou equivalente).

## Bloco refinado
**BLK-EST-03 — Fonte real do solicitante (token→consumidor da API) para a marca d'água do PDF**

Recorte executável (Fase 1): ligar o `consumidor` já resolvido pela camada de autenticação da API ao parâmetro `solicitante` na geração do PDF. A lacuna é pontual e cirúrgica: `service.py::gerar_pdf_ponto` chama `gerar_pdf_relatorio_pontual_censitario(result, mapas, residual=residual, ultra_dir=ultra_dir, rotulo=rotulo)` **sem passar `solicitante=consumidor`**, mesmo que o `consumidor` já esteja disponível no escopo da função. Uma única linha é a correção; o restante do escopo é testes + lint.

Recorte bloqueado (Fase 2 — trilha do dashboard): `pages.py` linha 2656 chama `render_downloads_relatorio_censitario(...)` sem `solicitante=`. Nenhuma fonte de identidade existe no dashboard hoje: zero hits em `src/` para `authelia`, `X-Remote-User`, `usuario_logado`, `st.user`, `st.experimental_user`, `st.session_state` com identidade real. Bloqueado até Authelia ou equivalente ser configurado.

## Objetivo
Passar o `consumidor` já autenticado (token→consumidor, `auth.py`) ao parâmetro `solicitante` do PDF gerado pela API, de modo que todo PDF emitido via `POST /analisar?formato=pdf` carregue o nome real do consumidor na marca d'água, mantendo o fallback `None` para geração sem sessão.

## Escopo permitido
- Alteração de `src/motor_expansao/api/service.py`: adicionar `solicitante=consumidor` na chamada a `gerar_pdf_relatorio_pontual_censitario` dentro de `gerar_pdf_ponto` (linha ~307).
- Testes unitários/integração cobrindo: (a) PDF via API com token válido → `consumidor` no watermark; (b) fallback seguro quando `consumidor=None`; (c) fixtures com nome fictício, sem PII real.
- Lint (ruff) e type-check (mypy) no escopo alterado.
- Documentação inline mínima (comentário na chamada, se necessário).
- Padronização com os logs de rastreio LGPD do Felipe (ClickUp `86e1rtezm`): verificar se o campo `consumidor` já presente no JSON de resposta (`AnalisarResponseJSON.consumidor`) é suficiente para os logs, ou se é necessário algo adicional no serviço — decisão a registrar no plano.

## Fora de escopo
- Trilha do dashboard (`pages.py` / `render_downloads_relatorio_censitario`): bloqueada, não tocar neste ciclo.
- Authelia, Authelia proxy headers, `X-Remote-User`, JWT externo: inexistentes no código, não introduzir.
- Redefinir template/marca d'água (entregue no BLK-EST-01, INTOCADO).
- Alterar `censo_report.py` além do absolutamente necessário (assinatura `solicitante` já pronta — não alterar).
- Score, pesos, artefatos M1 (READ-ONLY absoluto; DEC-001).
- Versionar PDFs reais ou fixtures com PII real.
- Introduzir dependência de API ao vivo no dashboard de produção.
- BLK-API-05 e fases posteriores da API.

## Arquivos que devem ser lidos
- `src/motor_expansao/api/service.py` — ponto exato da lacuna (`gerar_pdf_ponto`, linha ~241–308)
- `src/motor_expansao/api/routes/analisar.py` — confirma que `consumidor` chega à rota e é passado para `gerar_pdf_ponto`
- `src/motor_expansao/api/auth.py` — confirma que `resolver_consumidor` retorna `str` (não `str | None`)
- `src/motor_expansao/dashboard/censo_report.py` — assinatura de `gerar_pdf_relatorio_pontual_censitario` (linha ~624–667) e `_watermark_text` (linha ~144–151); confirmar que `solicitante: str | None = None` já existe e o fallback é seguro
- `src/motor_expansao/dashboard/pages.py` — linha 2656: confirmar que a chamada dashboard não passa `solicitante` (bloqueada, não alterar neste ciclo)
- `src/motor_expansao/api/settings.py` — confirma mapa estático `token → consumidor` (campo `tokens`)
- `tests/` — localizar testes existentes de `gerar_pdf_ponto` / `gerar_pdf_relatorio_pontual_censitario` para entender cobertura atual e onde adicionar os novos

## Arquivos que podem ser alterados
- `src/motor_expansao/api/service.py` — adicionar `solicitante=consumidor` na chamada a `gerar_pdf_relatorio_pontual_censitario` em `gerar_pdf_ponto`
- Arquivos de teste pertinentes (novos ou existentes) cobrindo o comportamento descrito no escopo
- `context/handoff.md` (este arquivo, nos próximos handoffs da esteira)
- `tasks/current_task.md` (housekeeping de esteira)

**NÃO alterar:**
- `src/motor_expansao/dashboard/censo_report.py` (a assinatura já existe; não tocar além do mínimo)
- `src/motor_expansao/dashboard/pages.py` (trilha dashboard bloqueada)
- Qualquer arquivo da pipeline M1 / artefatos oficiais
- `config.py` raiz (parâmetros canônicos do §3)

## Critérios de aceite
- `gerar_pdf_ponto(lat, lng, consumidor="bot-telegram", ...)` gera PDF com watermark contendo "Ultra Academia | bot-telegram".
- `gerar_pdf_ponto(lat, lng, consumidor=None, ...)` gera PDF com watermark contendo apenas "Ultra Academia" (fallback seguro, retrocompatibilidade preservada).
- Testes passam com nome fictício nas fixtures (nenhum PII real em disco).
- Suite completa verde (`pytest -n auto`), sem regressão de contagem.
- `ruff check` e `mypy` limpos no escopo alterado.
- READ-ONLY M1: `score_priorizacao`, `hex_score_estrutural`, pesos, carteira, plano, artefatos oficiais INALTERADOS.
- Nenhum PDF real ou fixture com PII versionado.
- O campo `consumidor` no JSON de resposta (`AnalisarResponseJSON`) permanece inalterado (já rastreia o consumidor para logs LGPD).

## Criticidade classificada
**Alta** (rastreabilidade/LGPD — passa a gravar identidade real no documento; READ-ONLY sobre M1).
Esteira Alta: BO → Planner → [REVISÃO HUMANA] → Builder → QA.

## Esteira recomendada
Block Orchestrator (concluído) → **Planner** → [REVISÃO HUMANA obrigatória por Felipe] → Builder (opus) → QA (opus 4.8)

## Riscos identificados

### R1 — Lacuna confirmada na trilha da API (bloqueador imediato, mas corrigível)
`service.py::gerar_pdf_ponto` já recebe `consumidor: str | None` como parâmetro (linha ~244) mas não o repassa para `gerar_pdf_relatorio_pontual_censitario` (linha ~306-308). O fix é uma linha. Risco de omissão: BLK-API-04 foi entregue sem ligar o `consumidor` ao `solicitante`, portanto todos os PDFs emitidos pela API até agora têm watermark sem identidade ("Ultra Academia" sem o nome do bot/consumidor). Severidade: **média** (funcional, não quebra nada; mas é a razão do bloco existir).

### R2 — Trilha do dashboard permanece bloqueada (Authelia ausente)
Zero infraestrutura de autenticação no Streamlit (`src/` inteiro): nenhuma referência a `authelia`, `X-Remote-User`, `usuario_logado`, `st.user`, `st.experimental_user` ou identidade em `st.session_state`. A trilha do dashboard não pode ser desbloqueada neste ciclo. O Planner deve deixar explícito no plano que a Fase 2 (dashboard) só pode ser executada após Authelia (ou equivalente) estar operacional — e que o `solicitante=None` / fallback "Ultra Academia" deve ser preservado indefinidamente como comportamento seguro.

### R3 — Padronização com logs LGPD (ClickUp 86e1rtezm)
O campo `consumidor` já aparece no JSON de resposta da API (`AnalisarResponseJSON.consumidor`). A questão é se os logs LGPD do Felipe (ClickUp `86e1rtezm`) consomem esse campo diretamente do JSON ou se precisam de algo adicional (ex.: log structured no servidor, header de resposta, campo extra no PDF). O Planner deve confirmar com Felipe ou registrar a premissa no plano: **se os logs LGPD já leem `consumidor` do JSON de resposta, nenhuma mudança adicional é necessária além do `solicitante=consumidor` no PDF**. Se precisar de mais, isso pode ampliar o escopo — e deve ser aprovado no gate humano.

### R4 — Cobertura de teste existente para `gerar_pdf_ponto`
Não foi possível confirmar se já existem testes de `gerar_pdf_ponto` exercitando a geração do PDF com `consumidor` preenchido. O Planner deve mapear os testes existentes antes de propor novos, para não duplicar nem omitir.

### R5 — `consumidor` é `str` (não `str | None`) em `auth.py`
`resolver_consumidor` retorna `str` (nunca `None`; levanta 401 se token ausente/inválido). Portanto, no caminho da API, `consumidor` é sempre uma string quando a rota `POST /analisar` é atingida. O parâmetro de `gerar_pdf_ponto` é `consumidor: str | None` (por flexibilidade de testes), o que é correto — o Builder não deve estreitar a assinatura.

## Guardrails ativos
- READ-ONLY sobre M1: `score_priorizacao`, `hex_score_estrutural`, pesos (`renda=0.40`/`pop=0.60`), carteira, plano, artefatos oficiais INALTERADOS (DEC-001).
- Anti-PII (§2/§4 CLAUDE.md): nenhum PDF real ou fixture com PII real versionado; fixtures usam nomes fictícios.
- Sem dependência de API ao vivo no dashboard de produção (§2 CLAUDE.md); a geração do PDF pela API já é on-demand conforme DEC-005.
- `censo_report.py` NÃO deve ser alterado além do estritamente necessário (assinatura `solicitante` já pronta).
- Sem regressão de suite: baseline corrente 780 passed, 4 skipped (último QA do BLK-DIM-00).
- Esteira Alta: gate humano obrigatório entre Planner e Builder.
- Nenhuma alteração em `config.py` raiz (parâmetros canônicos do §3).
