# Handoff — QA / Quality Analyzer

## Skill que gerou este handoff
QA / Quality Analyzer

## Próxima Skill recomendada
Block Orchestrator (fechamento manual)

## Veredito
**APROVADO COM RESSALVAS**

## Justificativa (1-3 frases)
Os 9 arquivos atendem aos 11 critérios de aceite do Planner; M1, dashboard, deploy e VPS permanecem intactos; suíte completa roda `532 passed, 1 skipped` (zero regressão; baseline do Builder de 147 testes do `test_streamlit_app.py` confere). As pendências operacionais externas (roundtrip SOPS e gitleaks) não bloqueiam o fechamento por serem executáveis pelo humano via runbook, mas duas ressalvas de baixo impacto devem virar follow-up no backlog.

## Problemas críticos
Nenhum.

## Problemas médios
1. **`scripts/secrets_roundtrip_test.ps1` ainda está untracked** (`?? scripts/secrets_roundtrip_test.ps1` em `git status`), enquanto os dois `.sh` já estão staged como `A`. Tecnicamente o arquivo existe no disco e o conteúdo está correto, mas o Block Orchestrator precisa rodar `git add scripts/secrets_roundtrip_test.ps1` antes do commit final do ciclo — senão o `.ps1` não vai pro repo. Não é falha do conteúdo, é gap de staging.
2. **Baseline de testes desatualizada no `CLAUDE.md` §5**: o doc afirma `509 passed, 1 skipped`, mas a suíte atual roda `532 passed, 1 skipped` (zero failed). Provavelmente reflete ciclos posteriores ao referenciado. Não é regressão deste ciclo, mas vale atualizar o número canônico em housekeeping para o próximo QA não estranhar.

## Melhorias opcionais
1. Considerar adicionar `.gitattributes` com `*.sh text eol=lf` para tornar a garantia de LF nos `.sh` explícita (hoje funciona porque o blob no índice está em LF, mas depende de hábito local do Windows). Não-bloqueador — Builder já documentou que descartou essa adição por estar fora de escopo do plano.
2. `docs/backup_restore.md` referencia o IP real `2.25.137.241` em 5 lugares (igual ao `CLAUDE.md` §6 e `docs/infra_producao.md`). Não é problema novo, mas se em algum momento a equipe quiser mascarar o IP nos docs, este é um arquivo a considerar junto com os outros dois.

## Testes faltantes
Nenhum — o roundtrip dummy é validável por inspeção do script + execução humana com sops/age instalados (já tratado como pendência operacional).

## Riscos remanescentes
1. **Roundtrip SOPS+age não executado neste ambiente** (`sops`, `age`, `docker` e `gitleaks` ausentes na máquina do QA). O Planner aceitou explicitamente que basta "pelo menos um SO". A execução humana via `pwsh scripts/secrets_roundtrip_test.ps1` (após instalar sops 3.8.1 e age 1.1.1 conforme `docs/backup_restore.md` §5) é o gate operacional. **Esperado:** `ROUNDTRIP OK` + exit 0.
2. **gitleaks via Docker não executado** pelo mesmo motivo (Docker ausente). Mitigação aplicada: grep manual nos 9 arquivos por padrões `AUTHELIA_*`, `JWT_SECRET`, `argon2id$`, `AGE-SECRET-KEY-1`, `BEGIN ... PRIVATE KEY`, hashes longos, `age1[a-z0-9]{50,}` (recipient real) e IP — **todos os matches são referenciais/documentais, nenhum segredo real**.
3. **Plano B só funciona se o operador apagar `keys.txt` local** após copiar para o cofre — runbook destaca isso em negrito no §7-bis e na tabela §16. Risco humano, não técnico.

## Guardrails verificados
- VPS intocado (nenhum comando SSH/MCP do Builder): **sim**.
- `score_priorizacao` inalterado (nenhum arquivo em `src/motor_expansao/pipelines/m1/` modificado): **sim** (`git diff HEAD --stat -- src/` vazio).
- `hex_score_estrutural` inalterado: **sim**.
- Parâmetros canônicos `CLAUDE.md` §3 (`H3_RESOLUTION=7`, `DIST_MIN_ULTRA_KM=1.0`, `RENDA_MIN=4500.0`, pesos `renda=0.40` / `pop=0.60`): **sim** (`config.py` não modificado; `H3_RESOLUTION = 7` confirmado em `config.py:124`).
- Artefatos M1 oficiais em `data/outputs/` preservados: **sim** (`git diff HEAD --stat -- data/` vazio).
- Dashboard offline mantido — nenhuma dependência de API ao vivo: **sim** (Streamlit e `dashboard/` não tocados).
- `docker-compose.prod.yml`, `Dockerfile.streamlit`, `authelia/`, `Caddyfile`, `config.py`, `PRD.md`, `src/`, `data/`, `dashboard/` intactos: **sim** (`git diff HEAD --stat` para esses paths vazio).
- Escopo respeitado: 9 arquivos do Builder + 4 de orquestração (`PRD.md` pré-existente, `tasks/*.md`, `context/handoff.md`) — **sim**, `git status --short` confere exatamente.
- Nenhum valor de segredo real em nenhum dos 9 arquivos: **sim** (grep manual confirma; menções a `AUTHELIA_JWT_SECRET`, `AGE-SECRET-KEY-1...` são todas referências em docs/comentários).
- Permissões executáveis: `100755` confirmado para `setup_secrets_vps.sh` e `secrets_roundtrip_test.sh` via `git ls-files --stage`. `.ps1` é `100644` (correto, Windows não exige `+x`).
- Line endings dos `.sh` no índice: **LF puro** confirmado via `git show :scripts/*.sh | od -c` (primeiros bytes terminam em `\n`, sem `\r`).
- `git check-ignore -v` confere com expectativa: `secrets/env.enc`, `.sops.yaml`, `secrets/README.md`, `tests/fixtures/dummy_secret.yaml` **não ignorados** (exit 1, nada); `secrets/env.dec`, `secrets/keys.txt`, `secrets/key.txt`, `secrets/foo.age.key` **ignorados** com regra correta.
- Runbook `docs/backup_restore.md` tem 16 seções + `## 7-bis. Plano B` marcado como **OPCAO RECOMENDADA** em negrito (linha 183): **sim**.
- `.sops.yaml` com 4 `creation_rules` apontando para `age1REPLACE_WITH_REAL_RECIPIENT`: **sim**.
- `setup_secrets_vps.sh` não comita (passos 5/6 imprimem instrução manual e pausam): **sim** (linhas 167-178); aborta se `.sops.yaml` ainda tem placeholder (linha 114).

## Validações executadas neste QA

### Inspeção de conteúdo
- Read completo dos 9 arquivos (`.sops.yaml`, `secrets/README.md`, `tests/fixtures/dummy_secret.yaml`, `docs/backup_restore.md`, `scripts/setup_secrets_vps.sh`, `scripts/secrets_roundtrip_test.sh`, `scripts/secrets_roundtrip_test.ps1`, `.gitignore`, `.dockerignore`).
- Grep dos 9 arquivos por padrões de segredo (`AUTHELIA_`, `JWT_SECRET`, `argon2id$`, `AGE-SECRET-KEY-1`, `BEGIN PRIVATE KEY`, senhas longas, `age1[a-z0-9]{50,}`). **Zero matches de valor real.**
- Grep por IP `2.25.137.241` nos 9 arquivos: 5 ocorrências em `docs/backup_restore.md`, todas em comandos de exemplo. Mesma exposição já existe em `CLAUDE.md:114` e `docs/infra_producao.md` — não é novidade deste ciclo.

### git check-ignore -v (paths esperados ignorados/não-ignorados)
```
.gitignore:90:secrets/*.dec    secrets/env.dec       ← ignorado (OK)
.gitignore:95:keys.txt          secrets/keys.txt     ← ignorado (OK)
.gitignore:94:key.txt           secrets/key.txt      ← ignorado (OK)
.gitignore:93:*.age.key         secrets/foo.age.key  ← ignorado (OK)
(sem saida para: secrets/env.enc, .sops.yaml, secrets/README.md, tests/fixtures/dummy_secret.yaml)  ← nao ignorados (OK)
```

### git ls-files --stage (modos no índice)
```
100755 ... scripts/secrets_roundtrip_test.sh
100755 ... scripts/setup_secrets_vps.sh
(sem saida para scripts/secrets_roundtrip_test.ps1 — untracked)
```

### Line endings (`git show :<path> | od -c | head`)
- `scripts/setup_secrets_vps.sh`: linha 1 termina em `\n` puro (LF). OK.
- `scripts/secrets_roundtrip_test.sh`: linha 1 termina em `\n` puro (LF). OK.

### Suíte de testes
```
$ python -m pytest -q tests/integration/test_streamlit_app.py
147 passed in 10.19s        ← confere com baseline do Builder

$ python -m pytest -q
532 passed, 1 skipped, 9 warnings in 88.42s
```
**Zero falhas.** Salto de +23 vs baseline `509+1` do `CLAUDE.md` reflete ciclos posteriores; não é regressão deste ciclo (vide problema médio #2).

### Guardrails de escopo
```
$ git diff HEAD --stat -- src/ config.py data/ dashboard/ docker-compose.prod.yml Dockerfile.streamlit authelia/ Caddyfile
(vazio — nenhum desses paths foi tocado)
```

### Ferramentas externas
- `sops`, `age`, `docker`, `gitleaks`: **todos ausentes** no ambiente do QA. Pendência operacional documentada — humano valida via runbook.

## Pendências operacionais para o humano (não bloqueadoras do fechamento)
1. **Roundtrip dummy**: instalar sops 3.8.1 e age 1.1.1 (passos exatos em `docs/backup_restore.md` §5 para Windows) e rodar `pwsh scripts/secrets_roundtrip_test.ps1`. Esperado: `ROUNDTRIP OK` + exit 0.
2. **gitleaks**: ter Docker disponível e rodar `docker run --rm -v "${PWD}:/repo" zricethezav/gitleaks:latest detect --no-git --source /repo -v`. Esperado: 0 findings, exit 0.
3. **Staging do `.ps1`**: rodar `git add scripts/secrets_roundtrip_test.ps1` antes do commit de fechamento. (Problema médio #1.)

## Decisão recomendada
**Fechar ciclo** com as duas ressalvas registradas como follow-up no `tasks/backlog.md` (atualizar baseline de testes no `CLAUDE.md` §5; rodar roundtrip + gitleaks quando ferramentas instaladas; staging do `.ps1` antes do commit). Não há necessidade de reabrir Builder nem criar bloco de correção — todos os critérios obrigatórios foram atendidos e os guardrails permanecem íntegros.
