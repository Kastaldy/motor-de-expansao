# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Builder

## Bloco refinado
**BLK-OPS-08 — Atualizar actions do CI para Node 24 (fim do Node 20)**

Os runs do `CI` (`.github/workflows/ci.yml`) e do `Docker Publish (GHCR)` (`.github/workflows/docker-publish.yml`) emitem aviso de descontinuação porque `actions/checkout@v4` e `actions/setup-python@v5` ainda rodam no runtime Node 20. O GitHub força a migração para Node 24 a partir de 16-jun-2026 e remove o Node 20 do runner em 16-set-2026. Este bloco apenas sobe a tag dessas actions para as versões que rodam em Node 24 e revisa as versões dos `docker/*-action`. Não muda nenhum step de teste, build, scoring nem artefato M1.

## Objetivo
Eliminar o aviso de descontinuação do Node 20 atualizando as tags das actions para versões que rodam em Node 24, sem alterar o comportamento de testes/build, scoring ou artefatos M1.

## Escopo permitido
- Atualizar as tags das actions baseadas em JS/Node nos dois workflows para as versões que rodam em Node 24 (lista exata abaixo).
- Revisar as versões dos `docker/*-action` no `docker-publish.yml` (login/metadata/setup-buildx/build-push) e confirmar que já estão na última estável; manter como estão se já forem.
- Commit por path (apenas os arquivos de workflow listados + arquivos de controle/handoff).

## Fora de escopo
- Mudar lógica de CI, ordem ou comportamento de qualquer step (instalar deps, ruff, mypy, pytest, smoke import, login GHCR, metadata, buildx, build/push).
- Alterar gatilhos (`on:`), permissões, matrizes, versão de Python (`3.11`) ou parâmetros de cache.
- Alterar scoring (`score_priorizacao`, `hex_score_estrutural`, `ajuste_executivo`), carteira, plano ou qualquer artefato oficial do M1.
- Executar qualquer comando no VPS (CLAUDE.md §6).
- Resolver outros blocos do backlog. Um bloco por vez.

## Arquivos que devem ser lidos
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\.github\workflows\ci.yml`
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\.github\workflows\docker-publish.yml`
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\tasks\backlog.md` (seção `### BLK-OPS-08`, linhas ~243-268 — escopo/aceite/risco canônicos)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\tasks\current_task.md`
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\CLAUDE.md` (§2 regras operacionais; §6 VPS)

## Arquivos que podem ser alterados
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\.github\workflows\ci.yml`
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\.github\workflows\docker-publish.yml`
- Controle (no fechamento): `tasks\current_task.md`, `tasks\completed.md`, `tasks\backlog.md` (marcar BLK-OPS-08), `context\handoff.md`, `context\handoff\`.
- NÃO arrastar `PRD.md` nem edições pré-existentes não relacionadas em `tasks\backlog.md`.

## Actions a atualizar — lista explícita (versão atual → versão alvo)

### `.github/workflows/ci.yml`
| Action | Linha | Runtime atual | Versão atual | Versão alvo | Muda? |
|---|---|---|---|---|---|
| `actions/checkout` | 14 | Node 20 | `@v4` | `@v5` | SIM |
| `actions/setup-python` | 16 | Node 20 | `@v5` | `@v6` | SIM |

(2 ocorrências; ambas no job `test`. O `actions/setup-python@v6` mantém `python-version: "3.11"` e `cache: pip` / `cache-dependency-path` inalterados — só sobe o runtime para Node 24.)

### `.github/workflows/docker-publish.yml`
| Action | Linha | Versão atual | Versão alvo | Muda? |
|---|---|---|---|---|
| `actions/checkout` | 25 | `@v4` | `@v5` | SIM |
| `docker/login-action` | 28 | `@v3` | `@v3` | NÃO (já é a última estável; não usa runtime Node 20) |
| `docker/metadata-action` | 36 | `@v5` | `@v5` | NÃO (já é a última estável) |
| `docker/setup-buildx-action` | 44 | `@v3` | `@v3` | NÃO (já é a última estável) |
| `docker/build-push-action` | 47 | `@v6` | `@v6` | NÃO (já é a última estável) |

Observação: os `docker/*-action` não aparecem no aviso de descontinuação do Node 20 (não rodam no runtime JS/Node do runner). A única mudança no `docker-publish.yml` é o `actions/checkout@v4 → @v5`. As demais ficam como estão. (Builder: confirme na execução, via marketplace/release notes, que `@v5`/`@v6` continuam as últimas estáveis para `checkout`/`setup-python`; se houver tag maior estável publicada, usar a mais recente e registrar no commit.)

## Critérios de aceite
- Run do workflow `CI` verde no GitHub Actions **sem** o aviso de descontinuação do Node 20.
- Run do workflow `Docker Publish (GHCR)` verde **sem** o aviso de descontinuação do Node 20.
- Nenhum step de teste/build alterado em comportamento (mesmos comandos: `pip install -e ".[dev]"`, `ruff check .` continue-on-error, `mypy src/` continue-on-error, `python -m pytest -q`, smoke import; mesmo login/metadata/buildx/build-push no Docker Publish).
- Diff contém exclusivamente mudanças de tag de action (`@vX` → `@vY`) nos dois arquivos de workflow — nenhuma outra linha alterada.
- Commit por path (somente os workflows + controle/handoff).

## Criticidade classificada
**Baixa.** Atualização de versão de tags de actions; reversível por revert. Não toca scoring, carteira, plano nem artefatos oficiais do M1 → sem ALERTA M1.

## Esteira recomendada
Block Orchestrator → Builder (sem Planner, sem gate humano).

## Riscos identificados
- **Mudança de comportamento entre majors de action (baixo):** `actions/checkout@v5` e `setup-python@v6` são saltos de major; em tese podem mudar defaults. Mitigação: manter explícitos os `with:` já presentes (`python-version`, `cache`, `cache-dependency-path`) e validar via run verde.
- **Cache de pip do `setup-python@v6` (baixo):** a chave de cache pode invalidar uma vez (cache miss no primeiro run pós-upgrade); não é falha, só latência. Esperado e aceitável.
- **Verificação externa depende de push/PR (baixo):** o sumiço do aviso só é comprovável num run real do GitHub Actions; o QA/validação deve observar os logs do run em branch de ciclo / PR. Sem acesso a runner local equivalente.
- **Tag "mais recente estável" pode mudar (baixo):** se entre a delimitação e a execução o GitHub publicar major maior, o Builder deve usar a mais recente estável conhecida e registrar a escolha no commit.

## Guardrails ativos
- **CLAUDE.md §2:** toda mudança relevante entra com teste; nenhum PR sobe com CI quebrado. Tratar `config.py`, `CLAUDE.md` e `PRD.md` como fontes canônicas. (Aqui a "prova" é o próprio run verde dos workflows.)
- **CLAUDE.md §5 (guardrail permanente):** CI/visualizações não podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou artefatos oficiais do M1. Este bloco não toca nenhum desses.
- **CLAUDE.md §6:** GUARDRAIL ABSOLUTO — nenhum comando no VPS via MCP/SSH. Este bloco não toca no servidor.
- **Escopo travado:** apenas tags de action nos dois workflows; nenhum step, gatilho, permissão ou versão de Python alterada.
