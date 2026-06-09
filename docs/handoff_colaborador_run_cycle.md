# Handoff de ciclo com colaborador (run-cycle)

Fluxo para um membro da equipe rodar `/run-cycle` na conta dele e o Felipe
fazer merge + push + deploy. A separação "agente comita em branch / humano faz
merge e deploy" já é o desenho do orquestrador (`run-cycle.md` Passo 0 e 6.b).

## Fluxo

1. **Colaborador** roda `/run-cycle`: branch isolada `ciclo/<ID>`, commit só dos
   paths do ciclo (nunca `git add -A`), e **abre PR para `main`**.
2. O PR dispara o CI (`test`: ruff + mypy + pytest + gitleaks + pip-audit).
   **Felipe confere o CI verde no PR.**
3. **Felipe** revisa, aprova e faz **merge** (o merge já dá push na `main`).
4. Push na `main` roda o CI de novo e dispara o job `publish` → builda e publica
   a imagem no GHCR (`type=sha` + `latest`).
5. **Felipe** faz o **deploy PULL por digest** no VPS, comando a comando
   (ver `docs/deploy.md`). CLAUDE.md §6: comando no VPS é sempre humano.

CI verde é gate **antes** do merge; a imagem só publica **depois** do merge na `main`.

## Acessos

| Colaborador PRECISA | Colaborador NÃO precisa |
|---|---|
| Escrita no repo (push da branch) ou fork + PR | SSH/VPS |
| Conta git própria (autoria fica com ele) | Escrita no GHCR (o CI publica) |
| — | Segredos de produção / `.env` / SOPS |

## Atenção

- **CI não roda sozinho na `ciclo/*`** (só `main` e PRs para `main`). Por isso o
  fluxo é via PR. Alternativa manual: `gh workflow run ci.yml --ref ciclo/<ID>`.
- **Parquets/artefatos do M1 não estão no git.** Ciclo só de código → merge +
  rebuild resolve. Ciclo que **regenera artefatos oficiais** → os `.parquet`
  ficam na máquina do colaborador; Felipe regenera local ou recebe e faz `scp`
  pro VPS (`docs/infra_producao.md`). Marcar no backlog quais blocos tocam dados.
- **Assets de branding / segredos são server-only** (`data/ultra/`, `.env`,
  `authelia/*`) — domínio do Felipe; o colaborador não toca.
