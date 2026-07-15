# Garimpeiro — loop autônomo na nuvem que abre PRs (BLK-ORQ-22)

> Fecha o épico de governança da **DEC-016**. O loop hoje roda na máquina do Felipe
> (`iniciar-loop.cmd` → container Docker). O **Garimpeiro** leva a execução para a **nuvem** e entrega
> o trabalho como **PR** em branch `claude/*` — **sem merge, sem deploy**. O merge fica com o portão
> (4 checks + auto-criticidade/auto-merge); o Garimpeiro **só abre o PR**.

## 1. Como se encaixa no portão (por que "abrir PR" já basta)

Depois da DEC-016 + auto-criticidade (DEC-016/§8) o fluxo de um bloco **loop-safe** (Baixa/Média) é:

1. Garimpeiro seleciona o bloco, roda a esteira, **abre o PR** em `claude/<bloco>`.
2. O workflow **`auto-criticidade`** dispara na abertura → aplica `criticidade:<nível>` (lida do backlog
   da BASE) **e arma o auto-merge** (`--auto --squash`, via `AUTO_MERGE_PAT`) para Baixa/Média.
3. Os **4 checks** (`test` + `guard` + `review-gate` + `claude-review`) rodam. O `guard` só libera se o
   diff for READ-ONLY sobre o M1 e não tocar caminho crítico/governança.
4. Verdes → **auto-merge nativo do GitHub** (zero humanos). **Deploy segue manual, por digest.**

Ou seja: o Garimpeiro não precisa mergear nem aprovar nada — o portão faz o resto. Um bloco **Alta/
Crítica** que escape para `claude/*` **não** auto-mergeia (o `guard`/`review-gate` seguram por label
humana), então o pior caso é um PR parado esperando gente — nunca um merge indevido.

## 2. Seleção de bloco (marcador ANCORADO)

`scripts/garimpeiro_select_block.py` (testado em `tests/unit/test_garimpeiro_select_block.py`) escolhe
o próximo bloco **loop-safe** elegível:

```bash
python scripts/garimpeiro_select_block.py          # imprime o próximo BLK-* elegível (ou nada)
python scripts/garimpeiro_select_block.py --list   # todos os elegíveis
```

Regras (todas testadas):
- **Marcador ancorado** `^\| \*\*Autonomia\*\* \| loop-safe` — só entra bloco cuja Autonomia **começa**
  com `loop-safe`. **NÃO** casa `| **Autonomia** | **manual (NÃO loop-safe)** |` (que contém a substring
  "loop-safe" e enganaria um `grep loop-safe`).
- **`Depende de`** — só blocos cujas dependências já estão em `completed.md`.
- **Pula concluídos** — heading de conclusão em `completed.md`, com **fronteira exata** (`BLK-X` não
  casa `BLK-X-FU1`). Alinhado com o housekeeping diferido do **BLK-ORQ-24** (o stub do backlog pode
  estar atrasado; `completed.md` é a fonte de verdade de conclusão).

Saída vazia = nada a fazer nesta passada → a routine encerra sem abrir PR.

## 3. Configuração humana 1× (Esteira do bloco)

> Tudo abaixo é feito **uma vez** por um humano. Depois a routine opera sozinha.

### 3.1 Repo PRIVADO de dados `Kastaldy/motor-dados`
- Repo **privado** com os **~270 MB de `data/staging`** (parquets de negócio; risco de PII).
- **O `motor-de-expansao` é PÚBLICO — NUNCA commitar parquet nele.** `data/staging/` já é gitignored;
  o setup script (3.2) confirma isso e aborta se não estiver.
- Gerar uma **deploy key read-only** do `motor-dados` e guardá-la como segredo do environment
  (`MOTOR_DADOS_DEPLOY_KEY`).

### 3.2 Environment (setup script)
O environment da routine roda este script **antes** do agente, montando `data/staging`:

```bash
#!/usr/bin/env bash
# Setup do environment do Garimpeiro: popula data/staging a partir do motor-dados privado.
set -euo pipefail
export GIT_SSH_COMMAND="ssh -i \"$MOTOR_DADOS_DEPLOY_KEY_PATH\" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
git clone --depth 1 git@github.com:Kastaldy/motor-dados.git /tmp/motor-dados
mkdir -p data/staging
cp -a /tmp/motor-dados/data/staging/. data/staging/
# Trava anti-PII: data/staging NUNCA pode ser rastreado no repo publico.
git check-ignore -q data/staging || { echo "ABORT: data/staging nao esta gitignored"; exit 1; }
pip install -e ".[dev]" >/dev/null 2>&1 || true
echo "Garimpeiro env pronto: $(find data/staging -name '*.parquet' | wc -l) parquets."
```

### 3.3 Routine (agendada)
- **Diária às 02:00 BRT** (05:00 UTC).
- **Permissões restritas (não-negociável):**
  - Push **só em `claude/*`** — a permissão default da routine na nuvem já restringe; **sem PAT de
    escrita** no environment (não consegue push na `main` nem em `ciclo/*`).
  - **Sem** credencial de VPS/deploy/`CLICKUP_WRITE`/`GROWTH_API_` no environment (a mesma rede de
    segurança 1 do `run-ralph-loop.sh`; o guard também barra deploy/segredos).
  - Autenticação do agente pela **assinatura Max** (`CLAUDE_CODE_OAUTH_TOKEN`), não API key.
- **Prompt da routine:** o de §4.

## 4. Prompt da routine (o que o Garimpeiro faz por execução)

```text
/run-cycle [MODO GARIMPEIRO — loop autônomo na nuvem, sem humano no loop]

1. SELEÇÃO: rode `python scripts/garimpeiro_select_block.py`. Se a saída for VAZIA, não há bloco
   loop-safe elegível agora — encerre SEM abrir PR. Senão, trabalhe o bloco impresso (um por execução).
2. ESTEIRA: Planner → Builder → QA sobre esse bloco. NESTE MODO o gate humano de blocos Alta é
   SUBSTITUÍDO pelo guard automático: o bloco SÓ pode ser READ-ONLY sobre o M1 e NÃO pode tocar
   VPS/deploy/segredos nem persistir PII. Se o plano exigir mexer em M1 (config.py/score/pesos/
   artefatos/pipelines/m1), VPS/SSH/deploy, .env/segredos ou gravar PII → NÃO execute: pule e registre
   o motivo em RELATORIO-BLOQUEIO.md. Consuma os parquets já montados em data/staging (sem ingestão ao
   vivo). Rode `ruff check .` e `pytest -q` (gate único, SEM bypass); não avance com teste vermelho.
3. HOUSEKEEPING (BLK-ORQ-24): NÃO edite tasks/backlog.md ao fechar o bloco (não rode o
   housekeeping_move_block.py). O PR leva SÓ código + testes + o append em tasks/completed.md.
4. GUARD antes de abrir o PR: rode `python scripts/loop_guard.py --base origin/main`. Se ele acusar
   violação (M1/CI/deploy/segredo/governança), NÃO abra o PR — encerre e reporte em RELATORIO-BLOQUEIO.md.
5. ENTREGA: commit por path na branch `claude/<BLK-ID>` (ex.: claude/BLK-DIM-01), push (SÓ claude/* é
   permitido) e `gh pr create` (título com o BLK-ID). NUNCA merge/push em main|ciclo/*, NUNCA deploy,
   NUNCA escreva no ClickUp/VPS. O portão (auto-criticidade + 4 checks + auto-merge) cuida de rótulo,
   armar e mergear — você só ABRE o PR.
```

## 5. Guardrails e critérios de aceite

| Critério de aceite (bloco) | Como é atendido |
|---|---|
| Seletor: `manual (NÃO loop-safe)` NÃO entra; `loop-safe` entra | `garimpeiro_select_block.py` + `test_garimpeiro_select_block.py` (regex ancorado, 2 formatos reais) |
| Routine não consegue push fora de `claude/*` | Permissão default da routine + **sem PAT de escrita** no environment (§3.3) |
| `loop_guard` vermelho → nenhum PR aberto | Passo 4 do prompt (§4): guard antes do `gh pr create` |
| Nenhum `.parquet`/`data/staging` no diff do repo público | `data/staging/` gitignored + trava do setup (§3.2); o guard barra artefato M1 |
| 1 execução real: PR em `claude/*` com os 4 checks | Passo 5 do prompt + o portão dispara os 4 checks na abertura |

**Guardrails permanentes:** §5 do CLAUDE.md (**READ-ONLY M1** — nada de score/pesos/`config.py`/
`pipelines/m1/`/artefatos); **NUNCA** commitar parquet no repo público; sem credencial de VPS/deploy no
environment (não deploya); o Garimpeiro **abre PR, não mergeia**. Redes de segurança herdadas do loop:
guard sem bypass, testes como gate, container/environment credential-free.
