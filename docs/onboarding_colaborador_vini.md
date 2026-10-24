> **[HISTORICO]** Onboarding de jun/2026: a trilha da §6 está concluída, o Vini virou segundo dono do
> portão (DEC-019) e tem acesso de deploy desde 2026-10-09 (`docs/acesso_deploy_colaborador.md`).
> Fluxo vigente: `.claude/commands/run-cycle.md` + `docs/portao_merge_orq21.md`.

# Onboarding do colaborador (Vini) — Motor de Expansão

Checklist para o Vini começar a executar blocos via `/run-cycle` em paralelo, na conta dele,
com merge + deploy feitos pelo Felipe. Complementa `docs/handoff_colaborador_run_cycle.md`
(fluxo de PR) e `tasks/backlog.md` (seção "Trilha colaborador (Vini)").

## 1. Acessos (Felipe provê)

- [ ] **Acesso de escrita ao repo** GitHub `Kastaldy/motor-de-expansao` (collaborator) — ou fork + PR.
- [x] **Acesso de deploy na VPS** pelo usuário `deploy` (aplicado em 2026-10-09 — `docs/acesso_deploy_colaborador.md`): sem `sudo`, sem `authelia/`/`secrets/`/`cadastro/`; cada comando na VPS segue o §6 do CLAUDE.md.
- [ ] Conta git própria configurada (`git config user.name` / `user.email` do Vini).

## 2. Dados locais (gitignored — Felipe envia fora-de-banda)

O código vem por `git clone`. Os dados abaixo NÃO estão no git e precisam ser copiados
para os **mesmos caminhos relativos** dentro do clone. Total essencial ≈ 1,71 GB.

**Essenciais (todas as tarefas — rodar dashboard + relatório):**
- [ ] `data/outputs/` (~1,7 GB) — parquets do M1 + camadas paralelas; inclui
  `hexagonos_dashboard_enriquecido/uf=XX/` e a base geo `setores_censitarios_2022_geo/`.
  Pode pular os `*.tmp.parquet`.
- [ ] `data/ultra/` (544 KB) — `Ultra.csv` + assets de branding do PDF
  (`logo_ultra.png`, `relatorio_capa_bg.png`, `relatorio_conteudo_bg.png`, `dados_academias.xlsx`).
- [ ] `concorrentes/` (6,3 MB) — logos + bases geocodificadas (pins/overlays e PDF).

**Adicional — só para BLK-FIX-08 (SAM) ou regenerar camadas paralelas:**
- [ ] `data/staging/` (536 MB) — principalmente `hexagonos_mercado_mapeado.parquet`,
  `concorrentes_mapeados.parquet`, `brasil_estrutural.parquet`, `brasil_priorizados.parquet`,
  `hexagonos_brasil_oportunidades.parquet`.

**NUNCA enviar (PII / segredos / fora da trilha dele):**
- `data/referencias/` (estudos reais com PII, inclui `Teste Modelo.pptx`);
  `.env`, `Caddyfile`, `authelia/`, `secrets/`; `data/validacao/` e `data/analysis/` (trilha de score).

## 3. Ambiente

- [ ] Python 3.11 (paridade com o CI). `pip install -e ".[dev,api_mvp]"` (+ `".[basemap]"` se for mexer no
  fundo de ruas do relatório censitário).
- [ ] Validar local: `python -m pytest -q` (verde), `ruff check .`, `mypy src/`.
- [ ] Rodar o app (piloto web, DEC-022): `iniciar-piloto-web.cmd` na raiz — sobe o front Vite
  (`:5000`) e o back FastAPI (`:8899`), que lê os parquets via `MOTOR_DATA_DIR`
  (ver `web/README.md`).

## 4. Fluxo de trabalho (por bloco)

1. `/run-cycle` no bloco (ex.: `BLK-FIX-07`) → cria branch `ciclo/<ID>`, commita só os paths do ciclo.
2. Abre **PR de `ciclo/<ID>` para `main`** → o PR dispara os 4 checks (`test`, `guard`, `review-gate`, `claude-review`).
3. Merge pela régua da DEC-016: Baixa/Média auto-mergeia com os 4 verdes; Alta exige `aprovado-humano`
   (humano ≠ autor); Crítica exige também `critica-aprovada` de um dono (DEC-019).
4. Push na `main` dispara `publish-web`/`publish-api` (imagens no GHCR, filtradas por caminho); o
   **deploy PULL por digest** na VPS é manual (comando a comando, §6).
5. Bugs visuais e decisões de template exigem **gate visual do Felipe** antes do merge
   (precedente dos ciclos CENSO).

## 5. Guardrails que o Vini precisa respeitar

- **READ-ONLY sobre o M1** em toda a trilha dele: nunca recalcular `score_priorizacao`, pesos
  (`renda=0.40`/`pop=0.60`) ou artefatos oficiais (`brasil_*.parquet`, `hexagonos_brasil_*`). DEC-001 vigente.
  - Exceção: **BLK-FIX-08** toca a camada **paralela** de mercado/residual (não o M1 oficial); se
    regenerar parquets paralelos, seguir a ordem canônica (hibrido → mercado → `calcular_colunas_mercado`
    → carteira → plano → dominio → residual → `fase1_bi_exports`).
- **Anti-PII:** PDFs/estudos reais nunca versionados; cartão de contato `image24.png` nunca embutido.
- **Sem dependência de API ao vivo** no dashboard (basemap online é exceção só na geração do relatório, DEC-004).
- **Commit por path** (`git add <paths>`), nunca `git add -A`; não arrastar `PRD.md` nem edições alheias.
- **Paralelismo:** desde 2026-07-10 `context/handoff.md` e `tasks/current_task.md` são LOCAIS
  (gitignored) e `tasks/completed.md` é append-only com `merge=union`; o arquivo de processo que ainda
  pode colidir é o `tasks/backlog.md` (no modo auto-merge o PR de ciclo nem o toca — BLK-ORQ-24).

## 6. Trilha inicial sugerida (ClickUp ↔ backlog)

Começar pelos urgentes, isolados e de baixo risco:
1. **BLK-FIX-07** — Overlays do mapa territorial (urgent)
2. **BLK-FIX-08** — SAM em RR/AC/AM (urgent; camada paralela)
3. **BLK-FIX-09** / **BLK-FIX-10** — BYD no PDF / tamanho da pré-visualização
4. **BLK-EST-01** — marca d'água + solicitante (LGPD; coordenar com a tarefa de logs do Felipe)
5. **BLK-EST-02** — visual/template (gate visual)
6. **BLK-UI-01** — refatoração UX/UI (só após plano aprovado; fatiar)
