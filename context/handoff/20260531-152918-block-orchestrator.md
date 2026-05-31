# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (criticidade Alta ⇒ após o Planner há gate de REVISÃO HUMANA antes do Builder)

## Bloco refinado
**BLK-OPS-11 — Pinar dependências e restaurar paridade CI/local (CI vermelho nos testes)**

Com o lint do ruff destravado (commits `3b022ea`/`48d8eb7`), o passo `Testes (suite completa)` do
CI rodou pela 1ª vez em dias e falha na collection com
`AttributeError: property 'CORES' of 'Settings' object has no setter` em ~14 testes. Local passa;
CI falha. O lint vermelho vinha mascarando que os testes também quebravam no ambiente do CI — o CI
nunca esteve realmente verde. Produção NÃO é afetada (roda imagem pré-buildada do GHCR; smoke
import OK).

**Causa raiz (confirmada por leitura real):** dependências NÃO-pinadas no `pyproject.toml` (todas
com `>=` e sem teto). O CI instala o que há de mais novo (pandas 3.x, numpy 2.4.x, pydantic latest)
enquanto o dev local tem versões anteriores. O padrão `@property CORES` da classe `Settings`
(`src/motor_expansao/config.py`) deixa de ser aceito na inicialização sob a combinação nova. Há
também risco latente de break por pandas 3.0.

## Objetivo
Restaurar a paridade CI/local e deixar o gate de testes do CI verde de verdade (sem mascarar
falhas), pinando/saneando dependências, sem tocar M1/score/artefatos.

## Escopo permitido
O Planner DECIDE entre 2 abordagens (com gate humano); pinar o **ruff** (paridade de lint) entra em
qualquer das opções:
- **Opção A — Pinar dependências** no `pyproject.toml` para um conjunto conhecido-bom (faixas
  compatíveis: ex. `pandas<3`, `numpy<2.4`, `pydantic`/`pydantic-settings` em faixa que aceite o
  padrão atual, `ruff==<versão do CI>`, `mypy` pinado) + opcionalmente lockfile/constraints. Mais
  rápido/seguro; dívida adiada mas controlada.
- **Opção B — Adaptar o código**: corrigir o padrão `CORES`/`Settings` (eliminar duplicação nas
  linhas 83-95 e 152-164 e o conflito property×field do pydantic novo) e sanear incompatibilidades
  com pandas 3.0. Mais trabalho, mais robusto a longo prazo.
- Recomenda-se propor A agora (destravar) + B como follow-up; o Planner avalia custo das duas.
- Alterações permitidas apenas nos arquivos listados em "Arquivos que podem ser alterados".
- Re-medir as versões instaladas localmente (env drift desde a captura de 2026-05-31).

## Fora de escopo
- NÃO tocar M1: `score_priorizacao`, `scoring.py`, pesos, fórmula, artefatos oficiais. Só
  ambiente/CI/config.
- NÃO mascarar falha de teste (skip/xfail amplo) para "ficar verde" — bypass proibido.
- NÃO alterar lógica de negócio para acomodar versão de lib sem teste que prove equivalência.
- NÃO virar o gate de publicação (isso é BLK-SEC-01, que depende deste bloco) nem expandir para
  qualquer outro bloco.
- NÃO arrastar `PRD.md` nem edições não relacionadas; commit SÓ por path.

## Arquivos que devem ser lidos
- `prompts/block_orchestrator.md`
- `CLAUDE.md`
- `tasks/current_task.md`
- `tasks/backlog.md` (linhas 135–200 — definição do BLK-OPS-11)
- `pyproject.toml`
- `src/motor_expansao/config.py`
- `.github/workflows/ci.yml`

## Arquivos que podem ser alterados
- `pyproject.toml` (pins/faixas/extras)
- `src/motor_expansao/config.py` (CORES/Settings — apenas se Opção B)
- `.github/workflows/ci.yml` (constraints/lock, se necessário)
- eventual `requirements*.txt` / lockfile novo (se a abordagem exigir)
- `tasks/current_task.md` · `tasks/backlog.md` · `tasks/completed.md` · `context/handoff.md` ·
  `context/handoff/`

## Critérios de aceite
- CI **verde de ponta a ponta** (Lint → mypy → Testes → Smoke) no commit de fechamento —
  comprovado por run do GitHub Actions, não por suposição.
- Paridade: `ruff`/`mypy`/`pytest` reproduzíveis local == CI (mesmas versões; rodar ruff com
  `--no-cache`).
- 624 passed (ou contagem ≥) verde no CI; nenhuma falha de collection.
- Zero mudança em M1/artefatos; zero teste silenciado para forjar verde.
- Validações obrigatórias:
  ```
  ruff check . --no-cache
  mypy src/
  pytest -q
  # + confirmar run verde no GitHub Actions (gh run watch)
  ```

## Achados confirmados por leitura real (insumo do Planner)
- **`pyproject.toml`**: TODAS as dependências usam `>=` sem teto. Núcleo relevante: `pandas>=2.2.0`,
  `numpy>=1.26.0` (em `dependencies`); `ruff>=0.4.0`, `mypy>=1.10.0`, `pytest>=8.2.0` (extra `dev`);
  `pydantic>=2.7.0`, `pydantic-settings>=2.2.0` (extra `api`).
- **`config.py`**: `@property CORES` aparece DUAS vezes, com corpos idênticos:
  - linhas 83-95 — dentro do ramo `if BaseSettings is not None:` (classe pydantic `BaseSettings`);
  - linhas 152-164 — dentro do ramo `else:` (classe simples fallback, sem pydantic).
  É `@property` em ambos os ramos (não há field). O fallback simples seta atributos via
  `setattr(self, name, ...)` no `__init__` apenas para nomes `isupper()` — `CORES` continua property.
- **`.github/workflows/ci.yml`**: instala `pip install -e ".[dev]"` (NÃO instala o extra `api`).
  Consequência crítica para o Planner: como `pydantic`/`pydantic-settings` estão SÓ no extra `api`,
  no CI o `import` do `pydantic_settings` falha → ramo `BaseSettings is None` (fallback simples,
  linhas 99-164) é o que roda. Ou seja, a quebra de `CORES` no CI vem do ramo fallback, não do ramo
  pydantic. O Planner deve confirmar qual versão de qual lib dispara o `has no setter` nesse ramo
  antes de escolher A/B. Steps do gate (todos bloqueantes): checkout → setup-python 3.11 (cache pip)
  → install `.[dev]` → `ruff check .` → `mypy src/` → `python -m pytest -q` → smoke
  `import streamlit_app`.
- **Versões locais agora** (re-medidas; divergem da baseline 2026-05-31 do backlog — env drift):
  pydantic 2.12.5 · pydantic-settings 2.13.1 · pandas 2.3.3 · numpy 2.3.4 · ruff 0.15.15 ·
  mypy 2.1.0. O Planner deve fixar o conjunto conhecido-bom e checar a(s) versão(ões) reais do CI.

## Criticidade classificada
**Alta** — confirmada. Afeta o gate de qualidade do CI (testes na prática desligados), mas NÃO toca
`score_priorizacao`, `hex_score_estrutural`, carteira, plano, plano de domínio nem artefatos
oficiais do M1. Por isso NÃO escala para Crítica pela regra de guardrail. Por ser Alta, a esteira
inclui gate de REVISÃO HUMANA após o Planner.

## Esteira recomendada
Block Orchestrator → Planner → [REVISÃO HUMANA] → Builder → QA

## Riscos identificados
- Pinar (Opção A) pode esconder incompatibilidades futuras (mitigar agendando a Opção B como
  follow-up).
- Adaptar (Opção B) exige cuidado para não alterar comportamento de `Settings`/`CORES` sem teste de
  equivalência.
- Divergência entre o ramo que falha no CI (fallback, sem pydantic) e a hipótese de origem
  (pydantic novo): se não confirmada, o fix pode mirar o ramo errado. Exigir reprodução real.
- Env local já driftou em relação à baseline do backlog — escolher pins sem re-medir o CI real pode
  reintroduzir a divergência.
- Cache do ruff deu falso-verde no fix anterior; rodar `ruff check . --no-cache`.
- Tentação de silenciar testes para "ficar verde" — proibido (bypass).

## Guardrails ativos (CLAUDE.md §2 e §5)
- Guardrail permanente: visualizações, análise radial e interações de mapa NÃO podem recalcular ou
  alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio
  ou artefatos oficiais do M1 sem aprovação explícita. Este bloco é ambiente/CI/config e NÃO toca M1.
- Toda mudança relevante entra com teste; nenhum PR sobe com CI quebrado (CLAUDE.md §2). O objetivo
  é justamente honrar essa regra com CI verde de verdade.
- Commit SÓ por path; nunca `git add -A`. Não arrastar `PRD.md` nem edições não relacionadas.
- GUARDRAIL ABSOLUTO de VPS: nunca executar comando no servidor sem confirmação explícita (não se
  aplica diretamente, mas permanece ativo).
