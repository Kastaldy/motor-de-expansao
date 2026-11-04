# Handoff de ciclo com colaborador (run-cycle)

Fluxo para um membro da equipe rodar `/run-cycle` na conta dele; o merge segue o portão da
DEC-016 e o deploy é manual por digest (Felipe, ou colaborador com o usuário `deploy` na VPS —
`docs/acesso_deploy_colaborador.md`). A separação "agente comita em branch / humano faz
merge e deploy" já é o desenho do orquestrador (`run-cycle.md` Passo 0 e 6.b).

## Fluxo

1. **Colaborador** roda `/run-cycle`: branch isolada `ciclo/<ID>`, commit só dos
   paths do ciclo (nunca `git add -A`), e **abre PR para `main`**.
2. O PR dispara os 4 checks obrigatórios (`test`: ruff + mypy + pytest + gitleaks + pip-audit;
   `guard`; `review-gate`; `claude-review` — DEC-016).
3. Merge pela régua da DEC-016 (o merge já dá push na `main`): Baixa/Média auto-mergeia com os 4
   verdes; Alta exige `aprovado-humano` (humano ≠ autor); Crítica exige também `critica-aprovada` de
   um dono (`Kastaldy` ou `VinhoAbencoado`, DEC-019).
4. Push na `main` roda o CI de novo e dispara os jobs `publish-web`/`publish-api`
   (filtrados por caminho) → buildam e publicam as imagens no GHCR (`type=sha` + `latest`).
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
- **Assets de branding e segredos são domínio do Felipe** e ficam fora do git (`data/ultra/`, `.env`,
  `authelia/*`). Para gerar PDF na máquina, o colaborador recebe uma cópia de `data/ultra/` (lista em
  `docs/artefatos_dados.md` §4) e não a altera; `.env`, `Caddyfile`, `authelia/` e `secrets/` não se repassam.
