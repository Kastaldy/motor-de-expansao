# Handoff — Orquestrador (sprint multi-track SEC-02 + FIX-07-B)

## Skill que gerou este handoff
Orquestração multi-agente **direta** (worktrees git isolados em paralelo), aprovada por Felipe em lote —
**não** a esteira `/run-cycle`. Por isso não há snapshots `context/handoff/20260602-*` desta sprint
(decisão do usuário em 2026-06-02: atualizar só este handoff corrente). Data: 2026-06-02.

## Próxima Skill recomendada
Nenhum bloco em execução. Próximo risco real de produção = **BLK-SEC-03 (hardening do VPS)** > BLK-SEC-05
(observabilidade) > BLK-SEC-04 (backup de dados). Follow-ups de higiene registrados (ver abaixo).
A critério do usuário abrir o próximo ciclo (via `/run-cycle` ou orquestração direta).

## VEREDITO
**CONCLUÍDO E DEPLOYADO** — ambos os tracks mergeados na `main`, CI verde, imagem em produção e saudável.

## Resumo dos tracks (QA independente APROVADO em cada um)

### Track A — BLK-FIX-07-B — clustering server-side por recorte (Fase B)
Gate puro `competitor_cluster_mode` (UF inteira/Brasil sem filtro ⇒ clusters H3 res-4 via
`ScatterplotLayer`, cap 2000, payload ~1,8 KB p/ 40k, sem cortar; município/filtro ⇒ pins individuais
com logo, caminho Fase A intocado com `cluster_competitors=False` default). +5 testes. Zero
M1/score/regra de cor. Arquivos: `src/motor_expansao/dashboard/{components,constants,pages}.py`,
`tests/integration/test_streamlit_app.py`. Commit `5d00163` → merge `adcc1db`.

### Track B — BLK-SEC-02 — gate de segurança no CI (Alta)
Actions pinadas por SHA; `docker/*` em Node 24 (`using: node24` verificado) → aviso de descontinuação
eliminado. gitleaks bloqueante (imagem por digest) — o gate revelou 2 defeitos reais do BLK-OPS-01
(fingerprints stale + invocação `--source /repo` divergente), corrigidos robusto a drift (`--source .` +
`[allowlist].regexes` no `.gitleaks.toml`); catch-proof: AWS key fake plantada bloqueou o run, depois
removida. pip-audit bloqueante (`--skip-editable`, sem `--strict`) — allowlist justificada de
`GHSA-6w46-j5rx-g56g` (pytest, DoS local dev-only). Trivy HIGH/CRITICAL (`ignore-unfixed`) no publish
(build→scan→push) e build-sanity — `.trivyignore` para 2 CVEs de build-tools sem runtime. Política de
severidade inline no `ci.yml`. Arquivos: `.github/workflows/ci.yml`, `.gitleaks.toml`, `.gitleaksignore`,
`.trivyignore`. Commit (squash) `c8bba9e` → merge `779698a`.

## Validação
- main pós-merge (dados reais): **651 passed, 1 skipped, 0 falhas**; ruff + mypy limpos.
- CI verde na `main` (push): `test` ✓ + `publish` ✓ (build→Trivy→push). Zero deprecation Node 20/16.
- Baseline no worktree (sem dados gitignored): 574 passed, 73 skipped (não comparar com a contagem da main).

## Deploy (2026-06-02, comando-a-comando, guardrail §6)
Pin `.env` `STREAMLIT_IMAGE` → `@sha256:6a80d5278acdd213d0f5d0a43ec628c7c577646d2d59cb69cc48eee17712b7c4`
(commit `779698a`). `pull` + `up -d streamlit`; container `Up (healthy)`, `/_stcore/health → ok`
(via `docker exec`; porta 8501 não publicada no host). Rollback de 1 passo:
`@sha256:2e9ac6c...04f36` (commit `058fd39`, também em `.env.bak`). Ver memória `project_deploy_pin_digest_prod`.

## Guardrails verificados
Zero M1/score/artefatos/regra de cor (conferido nos diffs); `git add` só por path; sem `pip install` nos
worktrees; arquivos disjuntos entre tracks; cada comando no VPS confirmado individualmente; FIX-06 segue
bloqueado (DEC).

## Follow-ups registrados (revisar até 2026-09; ver tasks/completed.md)
- **pytest 9**: subir `[dev]` p/ `pytest>=9` e remover o `--ignore-vuln GHSA-6w46-j5rx-g56g` do `ci.yml`.
- **Imagem multi-stage** sem build-tools no runtime: zera os 2 CVEs do `.trivyignore` (deletável depois).
- (Opcional) atualizar a linha "Baseline pytest atual" do CLAUDE.md (532 → 651).
- (Opcional) abrir os 2 follow-ups como blocos no backlog (ex.: BLK-SEC-06 / BLK-SEC-07).

## Decisão recomendada
Sprint encerrada e em produção. Recomendo priorizar **BLK-SEC-03 (hardening do VPS)** como próximo ciclo —
é o risco real de produção remanescente (root-SSH, sem firewall/fail2ban documentados, 2FA opcional),
ordens de magnitude acima dos CVEs de build-tool já allowlistados.
