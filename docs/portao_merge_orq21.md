# Portão de merge por checks de CI — runbook (BLK-ORQ-21 / DEC-016)

> Como a `main` é protegida hoje, o que cada check faz, como destravar um PR e como
> **desligar tudo em um comando** se der errado. Registro do bootstrap executado em
> **2026-07-14**. Contrato canônico: **DEC-016** (`CLAUDE.md` §8).

## 1. O que mudou

A `main` não é mais protegida por "1 aprovação humana". Ela é protegida por **4 checks de CI**
— código versionado, auditável e que ninguém contorna:

| check | quem é | o que reprova |
|---|---|---|
| `test` | `ci.yml` | suíte full, `ruff`, `mypy`, `gitleaks`, `pip-audit`. Gate sem bypass. |
| `guard` | `guard.yml` → `scripts/loop_guard.py` | o PR toca caminho **crítico** (M1, `config.py`, `deploy/`, `secrets/`, `Dockerfile.*`, CI) ou de **governança** (`.github/`, `CLAUDE.md`, `REVIEW.md`, `tasks/backlog.md`, o próprio guard) **sem a label humana validada**. |
| `review-gate` | `guard.yml` | a label `criticidade:*` do PR **não bate** com o campo Criticidade do bloco em `tasks/backlog.md` **da base** (criticidade não é auto-declarada), ou falta a label humana em bloco Alta/Crítica. |
| `claude-review` | `claude-review.yml` | achado de **severidade ALTA** pela régua do `REVIEW.md` (defeito técnico). |

**Régua de autonomia por criticidade do bloco:**

- **Baixa / Média** → mergeia **sozinho** (auto-merge nativo), sem humano, com os 4 verdes.
- **Alta** → exige a label `aprovado-humano`, aplicada por um humano **não-bot**, **diferente do
  autor do PR**, com `write`/`admin` — tudo validado **via API**, não na confiança.
- **Crítica** → exige `critica-aprovada` aplicada pelo **próprio dono** (`Kastaldy`).

**O deploy NUNCA é automático.** Auto-merge não deploya: um push na `main` só publica a imagem
no GHCR. Subir a imagem na VPS continua sendo passo manual, por digest (`CLAUDE.md` §6).

## 2. Estado aplicado na `main`

```
required_status_checks: strict=true, checks=[test, guard, review-gate, claude-review] (app_id 15368)
required_approving_review_count: 0
require_code_owner_reviews: true          <-- defesa N0 (ver §4)
dismiss_stale_reviews: true
required_conversation_resolution: true
enforce_admins: true
allow_force_pushes: false / allow_deletions: false
```

Os 4 contextos são pinados por `app_id: 15368` (GitHub Actions). Sem o pin, **qualquer** GitHub
App poderia reportar um check chamado `guard` e satisfazer o portão.

## 3. Como destravar um PR

1. **`guard` vermelho** — leia o veredito no log: ele diz o caminho, a classe e a label que falta.
   - classe `governanca` → alguém **que não seja você** aplica `aprovado-humano`.
   - classe `critico` → o **dono** (`Kastaldy`) aplica `critica-aprovada`.
2. **`review-gate` vermelho** — aplique a label `criticidade:<nivel>` **igual** ao campo
   Criticidade do bloco no `backlog.md`. Divergir = reprovado (é o ponto: o agente não
   se auto-classifica como Baixa).
3. **`claude-review` vermelho** — corrija o achado ALTA e dê push (a revisão roda de novo).
   Falso positivo → conduza o merge com humano.
4. **PR sem bloco no backlog** (hotfix, follow-up) → só passa com `aprovado-humano`.

> **Um push novo APAGA as labels de aprovação.** É proposital: a aprovação vale para o diff que
> o humano viu, não para o commit seguinte. Rotule **depois** do último push.

## 4. As armadilhas que este bootstrap encontrou (não repita)

Os checks do BLK-ORQ-20 **nunca tinham rodado** — `guard.yml` usa `pull_request_target`, ou seja,
roda a partir da **base**, e portanto não roda no PR que o cria. O primeiro PR real (#97) revelou
**quatro** defeitos, todos capazes de congelar o repositório:

1. **CODEOWNERS com dono único.** `@Kastaldy` era dono dos 8 caminhos **e** é o autor de quase
   todo PR. O GitHub **não deixa o autor aprovar o próprio PR** → com `require_code_owner_reviews`
   + `enforce_admins`, nenhum PR tocando esses caminhos teria revisor elegível. **Ninguém**
   mergearia — nem o dono. Corrigido com **3 donos** (`@Kastaldy @VinhoAbencoado @juancalu`).
2. **`guard.yml` matava o próprio veredito.** O shell default do Actions é `bash -e`, e
   `set -uo pipefail` **não** desliga o `-e`. O exit 1 do `loop_guard` (o caso **normal**: achou
   violação) abortava o step **antes** de cruzar violações × labels → todo PR de governança
   reprovava **mesmo com a label válida**. Corrigido com `set +e` + captura do `rc`.
3. **`claude-review` nunca rodava o Claude.** Sem o input `github_token`, a action cai no
   fallback de **OIDC** e aborta (`Unable to get ACTIONS_ID_TOKEN_REQUEST_URL`) — o check ficava
   vermelho por config, não por achado. Corrigido passando `github_token`.
4. **`REVIEW.md` ALTA #7 criava um deadlock.** Mandava reprovar toda mudança em
   `.github/`/`deploy/`/`Dockerfile.*`/`secrets/` — mas o revisor **não enxerga labels**, então
   reprovaria **mesmo com** a label humana. Sob `enforce_admins`, o CI/deploy ficaria **imutável**.
   A exigência foi movida para onde é **verificável**: o `guard` (label validada por API). O
   revisor voltou a julgar **defeito técnico**.

**Ordem de bootstrap (inegociável):** mergear os checks → deixá-los **reportar 1× num PR real** →
só então exigir os contextos. Exigir um check que nunca reportou o deixa em `expected` eterno e,
com `enforce_admins: true`, **nenhum PR mergeia — nem o que consertaria isso**.

## 5. Kill-switch (restaura o gate humano em 1 comando)

```bash
gh api --method PUT repos/Kastaldy/motor-de-expansao/branches/main/protection --input - <<'JSON'
{
  "required_status_checks": {"strict": true, "checks": [{"context": "test", "app_id": 15368}]},
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "require_last_push_approval": false
  },
  "restrictions": null,
  "required_conversation_resolution": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
```

Isso devolve **exatamente** o regime anterior (1 aprovação humana, só o check `test`). Não é
preciso reverter código nem PR. `enforce_admins: true` **não** impede um admin de **editar** a
proteção — só de **bypassá-la**. Este é o extintor.

**Gatilho de suspensão (DEC-016):** 2 incidentes em 90 dias → auto-merge de Baixa/Média suspenso.
Incidente = PR auto-mergeado que reprove o `guard` em auditoria, introduza segredo/PII, exija
`revert` na `main` ou quebre o CI da `main`. O detector é o **Auditor de PRs** (BLK-ORQ-23).

## 6. Pendências conhecidas

- **O auto-merge do loop ainda não flui.** O housekeeping do `/run-cycle` stuba
  `tasks/backlog.md` a cada ciclo → o `guard` classifica como **governança** → todo PR de ciclo
  pede `aprovado-humano`. É o que o **BLK-ORQ-24** resolve (tirar o housekeeping do PR de ciclo).
  Enquanto ele não entra, o auto-merge vale para PRs que **não** tocam o backlog.
- **`claude-review` é um SPOF externo.** Token expirado, rate-limit da assinatura ou outage da
  action = check vermelho e nada mergeia. O kill-switch da §5 é a saída.
- **`strict: true`** exige a branch atualizada com a `main`: se a `main` andar, o PR precisa de
  "Update branch" — e o update **apaga as labels de aprovação** (por desenho). Em PR Alta/Crítica,
  rotule por último.
