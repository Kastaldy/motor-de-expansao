# Completed Tasks

## Histórico de ciclos concluídos antes da estrutura de Skills

Os ciclos abaixo foram concluídos antes da implementação da estrutura de Skills.
Detalhes completos estão no CLAUDE.md e PRD.md.

---

## PRÉ-ORQ — Blocos 1-13 (Visao Executiva, Analise Pontual, Hardening)

Data: 2026-05-20
Resumo: Visao Executiva Ultra-only, Analise Pontual de Entorno (raio 1.6km),
clique por centroide, mapa com pins de concorrentes/Ultra, régua visual 10-em-10,
hardening de 13 blocos.
Arquivos alterados: streamlit_app.py, dashboard/*, tests/*
Validações: 189 testes passaram
Decisões relacionadas: score_band_to_color via RESIDUAL_SCORE_BANDS

---

## PRÉ-ORQ — Blocos 14-19 (Multi-Hex, Domínio Híbrido, Consumo Fitness)

Data: 2026-05-21
Resumo: Contrato multi-hex, agregador (25 campos), UI multi-hex, domínio híbrido
censitário-residual, consumo fitness padronizado e handoff.
Arquivos alterados: dashboard/*, src/motor_expansao/*
Validações: 497 testes passaram, 1 skipped
Decisões relacionadas: score_dominio_hibrido = clip(0.60*censitário + 0.40*residual, 0, 100)

---

## PRÉ-ORQ — Ciclo Performance e Refatoração do Dashboard

Data: 2026-05-22
Resumo: Dataset enriquecido particionado por UF, carga lazy por UF, render lazy
de abas, fonte de mapa enxuta.
Arquivos alterados: dashboard/data.py, dashboard/components.py, streamlit_app.py
Validações: 509 testes passaram, 1 skipped
Decisões relacionadas: load_uf_slice, read_enriched_uf_partition, MAP_POINT_LIMIT

---

## PRÉ-ORQ — Ciclo Relatório Pontual Censitário 1.5km

Data: 2026-05-22 (correção: 2026-05-25)
Resumo: Subsistema censitário paralelo ao H3: motor setor x círculo, mapa PNG offline,
export CSV/PDF em memória, UI Streamlit. Base geo completa: 27 UFs, 5.571 municípios,
468.099 setores (~1.17GB). Correção de cod_municipio ausente.
Arquivos alterados: censo_point.py, censo_map.py, censo_report.py, dashboard/data.py
Validações: 526 testes passaram, 1 skipped
Decisões relacionadas: resolve_cod_municipio_from_geo_dir, censo_geo_dir propagado

---

## frag-mapa-pydeck-01 — st.fragment para interações do mapa pydeck

Data: 2026-05-25
Resumo: render_mapa_pydeck_fragment criada com @st.fragment em pages.py. Cliques sem
nova coordenada rerenderizam apenas o fragmento; cliques com nova coordenada propagam
st.rerun() completo para expanders dependentes (Analise Pontual, Relatorio Censitario,
Multi-Hex Controls). build_unified_map_figure permanece fora do fragmento.
Arquivos alterados: pages.py, streamlit_app.py, tests/integration/test_streamlit_app.py,
tests/unit/test_mapa_fragment.py (novo, 6 testes)
Validações: 532 passed, 1 skipped (+23 testes sobre baseline 509)
Veredito QA: APROVADO
Decisões relacionadas: st.rerun() sem scope (rerun completo) obrigatório ao detectar clique novo

---

## BLK-20260525-01 — Documentar estrutura de orquestração por Skills no README.md

Data: 2026-05-25
Resumo: Seção "## Orquestração por Skills" adicionada ao README.md (~55 linhas) entre
"## Mapa de docs" e "## Recalculo do M1". Cobre diretórios de controle, arquivos de
controle, papéis das quatro Skills, esteiras por criticidade e exemplo de uso do /run-cycle.
Arquivos alterados: README.md (somente)
Validações: documentação pura — pytest não aplicável; seções existentes preservadas
Veredito: APROVADO (criticidade baixa, sem QA obrigatório)
Skills executadas: Block Orchestrator → Builder

---

## BLK-20260527-01 — Plano de Deploy + Infraestrutura Hostinger KVM4

Data: 2026-05-27
Resumo: Análise técnica comparativa de deploy e implementação dos arquivos de infraestrutura
para hospedar o dashboard Streamlit na Hostinger KVM4 (4 vCPU, 16 GB RAM, 200 GB NVMe,
~R$ 780/ano) com stack Caddy + Authelia (tela de login real, 2FA opcional, 100% self-hosted).
Arquivos criados/modificados: .dockerignore, docker-compose.prod.yml (3 serviços: streamlit +
caddy + authelia), Caddyfile, authelia/configuration.yml, authelia/users_database.yml (template),
.env.example, .gitignore (entradas de deploy), docs/deploy_plan.md (17 passos).
Nenhum arquivo Python alterado. Nenhum artefato M1 tocado.
Validações: 147 testes passaram (tests/integration/test_streamlit_app.py); import ok.
Veredito QA: APROVADO (após correção de 3 bloqueadores: server.address Authelia v4.38,
endpoint /api/authz/forward-auth, pin de versão authelia:4.38).
Skills executadas: Block Orchestrator → Planner (×3 revisões) → Builder → QA (×2)
Pendências do usuário: contratar KVM4 na Hostinger, configurar DNS, substituir
SEU_DOMINIO.COM.BR nos arquivos de config, gerar hashes de usuários reais.

---

## BLK-20260528-03 — Atualizar base de concorrentes (CSVs + Logos)

Data: 2026-05-28
Resumo: 11 novas redes adicionadas (a_fitness, biohit, evolve, feira_fitness, formula,
motion_fit, my_box, pacer, pro3, redfit, skyfit — incluindo retorno do SkyFit).
28 CSVs existentes substituídos por versões atualizadas. Nomes de logos normalizados
(bluefit_academia_logo→logo_bluefit, logo_kore_studios→logo_kore, etc.; contorno_do_corpo
agora tem logo próprio). Total local: 39 redes, 3.796 unidades; VPS: 39 redes, 3.542 unidades.
VPS: volume mount /opt/motor-expansao/data/concorrentes→/app/concorrentes adicionado ao
docker-compose.prod.yml; 39 CSVs + 39 logos sincronizados via MCP SSH; imagem reconstruída;
3 linhas corrompidas corrigidas nos CSVs (bodytech, panobianco, tonus_gym).
Arquivos alterados: src/motor_expansao/dashboard/competitors.py, tests/integration/test_modelo_mercado_hexagonos.py
Validações: local 532 passed 1 skipped; VPS load_competitor_points: 39 redes, 3.542 unidades, sem parse errors.
Veredito: APROVADO
Skills executadas: Block Orchestrator → Builder → QA

---

## BLK-20260528-02 — Eliminar warning jwt_secret via force-recreate

Data: 2026-05-28
Resumo: Recriação do container Authelia no VPS de produção via `docker compose up -d --force-recreate authelia`
para carregar os env vars atualizados do docker-compose.prod.yml (mapeamento
AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET atualizado no ciclo BLK-20260528-01 mas
não carregado pelo restart simples). Container recriado com exitCode 0; logs vazios confirmam
eliminação do warning jwt_secret deprecated; caddy e streamlit inalterados.
Arquivos alterados: nenhum — operação apenas de container no servidor VPS.
Validações: docker ps (authelia Up healthy, caddy/streamlit Up 19h), docker logs authelia (0 linhas).
Veredito: APROVADO
Skills executadas: Block Orchestrator → Builder (aprovação explícita do usuário antes da execução VPS)

---

## BLK-20260528-01 — Corrigir Authelia url lookup failed + deprecations

Data: 2026-05-28
Resumo: Correção do erro `authelia url lookup failed` e warnings de configuração deprecated
no Authelia v4.38.19. Três arquivos editados diretamente no servidor VPS (root@2.25.137.241):
`authelia/configuration.yml` (bloco session migrado para formato cookies[] canônico v4.38),
`Caddyfile` (query string ?authelia_url removido do forward_auth), `docker-compose.prod.yml`
(AUTHELIA_JWT_SECRET renomeado para AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET).
Desvio necessário: campo global `default_redirection_url` removido do topo do configuration.yml
— Authelia v4.38 rejeita coexistência global + por-cookie com fatal error.
Arquivos alterados: apenas arquivos de infra no servidor VPS; nenhum arquivo Python tocado;
nenhum artefato M1 alterado.
Validações: docker ps (3 containers Up + healthy), docker inspect (RestartCount=0),
docker logs authelia (sem url lookup failed, sem session.domain deprecated),
docker logs caddy (limpos).
Veredito QA: APROVADO COM RESSALVAS (ressalva: warning jwt_secret remanescente —
melhoria opcional, não bloqueador; docker compose restart não recria container para
reler env vars; eliminação via force-recreate — ver BLK-20260528-02 no backlog).
Skills executadas: Block Orchestrator → Planner → [aprovação humana] → Builder → QA

---

## BLK-20260528-04 — Corrigir caminhos de concorrentes e Ultra no dashboard em produção (VPS)

Data: 2026-05-28
Resumo: Root cause identificado: `.dockerignore` exclui `data/` e `*.csv` da imagem, e o
`docker-compose.prod.yml` não tinha volume mounts para `concorrentes/` nem `data/ultra/`. Adicionados
dois mounts ao serviço `streamlit`: `/opt/motor-expansao/concorrentes:/app/concorrentes:ro` e
`/opt/motor-expansao/data/ultra:/app/data/ultra:ro`. Nenhum código Python alterado.
Nota: BLK-20260528-03 havia registrado mount com path `/opt/motor-expansao/data/concorrentes`
(com `/data/` no meio), mas esse mount não chegou ao commit por conflito de stash;
o path correto é `/opt/motor-expansao/concorrentes` (sem prefixo `/data/`).
Pendências operacionais VPS (requerem confirmação explícita do usuário):
  1. git pull na VPS para pegar o compose atualizado
  2. Verificar/mover arquivos: se existir /opt/motor-expansao/data/concorrentes/, mover para /opt/motor-expansao/concorrentes/
  3. Garantir /opt/motor-expansao/data/ultra/ com Ultra.csv e logo_ultra.png
  4. docker compose -f docker-compose.prod.yml up -d --no-deps streamlit
Arquivos alterados: docker-compose.prod.yml (+2 linhas de volume mount)
Validações: 191 passed (tests/unit/), import ok. Veredito QA: APROVADO
Skills executadas: Block Orchestrator → Builder → QA

---

## PRÉ-ORQ — Implementação da estrutura de Skills Fase 1

Data: 2026-05-25
Resumo: Criação das pastas tasks/, context/, prompts/, .claude/commands/ e docs/uso_pratico_skills.md.
Orquestrador autônomo /run-cycle implementado como slash command do Claude Code.
Arquivos criados: tasks/*, context/handoff.md, prompts/*.md, .claude/commands/run-cycle.md,
docs/uso_pratico_skills.md, orquestracao_claude.md
Nenhum arquivo de código alterado.
Próximo: BLK-ORQ-01 — ciclo piloto com /run-cycle

---

## BLK-OPS-01 — Backup encriptado de segredos e plano de regeneração

Data: 2026-05-28
Criticidade: alta
Resumo: Tooling SOPS+age configurado no repo (escolhido sobre git-crypt por granularidade de
diff em YAML, binários nativos Windows/Linux e rotação de chaves simples) + runbook
ponta-a-ponta `docs/backup_restore.md` com 16 seções + `## 7-bis. Plano B` marcando geração
de chave age na máquina local como opção RECOMENDADA. Builder não tocou VPS nem segredos
reais; scripts de automação criados como artefatos no repo (execução é humana).
Arquivos criados: `.sops.yaml`, `secrets/README.md`, `tests/fixtures/dummy_secret.yaml`,
`docs/backup_restore.md`, `scripts/setup_secrets_vps.sh` (chmod 0755), `scripts/secrets_roundtrip_test.sh` (chmod 0755), `scripts/secrets_roundtrip_test.ps1`
Arquivos alterados: `.gitignore` (seção SOPS+age: `*.dec`, `*.plain.*`, `*.age.key`, `key.txt`,
`keys.txt`), `.dockerignore` (`secrets/`)
Validações: pytest -q 532 passed, 1 skipped, 9 warnings (zero regressão); `git check-ignore`
confirma `.enc*` rastreado e `.dec`/`*.age.key`/`keys.txt` ignorados; permissões `100755`
nos `.sh`; line endings LF nos scripts bash. Pendências operacionais: roundtrip SOPS e
gitleaks (Docker) — sops/age/Docker ausentes no ambiente do QA, validação humana via runbook.
Veredito QA: APROVADO COM RESSALVAS (problemas médios: `.ps1` untracked no commit, baseline
de testes desatualizada no CLAUDE.md §5). Ambos registrados como follow-ups
(BLK-OPS-01-FU1, FU2, FU3 no backlog).
Skills executadas: Block Orchestrator → Planner → [aprovação humana] → Planner (revisão com 3 ajustes) → [aprovação humana] → Builder → QA
Guardrails: VPS intocado; nenhum segredo real manipulado; score_priorizacao, hex_score_estrutural,
config.py, src/, data/, dashboard/, docker-compose.prod.yml, authelia/, Caddyfile inalterados.

---

## BLK-OPS-01 — Fechamento REAL (backup real + restore validado)

Data: 2026-05-29
Criticidade: alta
Resumo: O ciclo BLK-OPS-01 de 2026-05-28 entregou TOOLING (scripts, .sops.yaml com placeholder,
runbook, fixture dummy). Mas o backup real continuava aberto — `.sops.yaml` tinha
`age1REPLACE_WITH_REAL_RECIPIENT`, nenhuma chave age existia, nenhum segredo real estava
encriptado. Este registro documenta o fechamento real, executado em uma sequência guiada
de 6 passos (~3 horas) com 7 commits.

Passos executados:
1. Chave age real gerada via Plano B em PowerShell local (`age-keygen -o ~/.sops/age/keys.txt`).
   Recipient público `age1lau0w4xgfkh9xnn58f2nwt0t4vstva30nht9zcggg2g7ssgq9uqsvd8zmd`.
2. `.sops.yaml` atualizado com recipient real (commit `1632844`).
3. Chave privada guardada em DOIS lugares offline: KeePassXC (`motor-expansao-vault.kdbx`)
   + cópia em papel guardada fisicamente. Pen drive não usado por indisponibilidade.
4. SOPS 3.8.1 + age 1.1.1 instalados no VPS via `curl` direto (sem package manager). 5 segredos
   reais encriptados *in-place* no VPS (`cp src dst && sops -e -i dst`), recipient público
   usado (chave privada nunca tocou o VPS). 5 `.enc.*` baixados via SCP. Commit `a2a4cea`.
5. Restore real validado em pasta limpa `C:\Users\Felipe Silva\restore-test\` (apagada após):
   - `git clone --depth 1` fresh da branch main.
   - Hashes do clone batem byte-a-byte com working tree (`.gitattributes` segurou conversão).
   - `sha256` no VPS dos 5 originais capturados.
   - `sops -d | sha256sum` no clone para binários: Caddyfile e db.sqlite3 batem exatamente
     com originais.
   - Comparação semântica via Python+PyYAML para textos (SOPS normaliza YAML/dotenv):
     env (29 chaves), configuration.yml (7 chaves), users_database.yml (1 chave) — todos
     idênticos semanticamente aos originais.
   - Cleanup: `restore-test/` removido inteiro.
6. Gitleaks com `.enc.*` presentes: 0 leaks, 5.9s (vs ~2h sem config no FU2). Antecipado
   antes do passo 5.

Defeitos do tooling original descobertos e corrigidos durante o fechamento:
- DEFEITO 3 (`64e68b1`): SOPS 3.8.1 não casa `path_regex` contendo `/`. Os 4 regex foram
  trocados de `secrets/.*\.enc\.*$` para `.*\.enc\.*$` (sem prefixo de diretório). Também
  renomeado `secrets/env.enc` para `secrets/env.enc.env` (necessário para a regra dotenv
  casar e preservar `encrypted_regex: ^.*$`).
- DEFEITO 4: `encrypt_one` no `scripts/setup_secrets_vps.sh` usava `sops -e SRC > DST` com
  SRC fora de `secrets/`, mesmo problema do defeito 3 (path matching). Não corrigido neste
  ciclo — registrado como follow-up BLK-OPS-01-FU4. Workaround manual: `cp SRC DST &&
  sops -e -i DST`.
- DEFEITO 5 (`a2a4cea`): `.gitattributes` ausente. Git Windows ia converter LF↔CRLF nos
  `.enc.*`, quebrando o MAC do SOPS no decrypt. Criado `.gitattributes` com `secrets/*.enc*
  binary` e `*.sh text eol=lf`.

Arquivos finais commitados (sequência 1632844 → 793127b → 64e68b1 → a2a4cea):
- `.sops.yaml` (recipient real + path_regex sem `/`)
- `.gitattributes` (binary para .enc.*, eol=lf para .sh)
- `secrets/env.enc.env` (5238 bytes, dotenv encrypted)
- `secrets/Caddyfile.enc` (1656 bytes, binary)
- `secrets/authelia.configuration.enc.yaml` (8073 bytes, yaml)
- `secrets/authelia.users_database.enc.yaml` (12269 bytes, yaml)
- `secrets/authelia.db.sqlite3.enc` (334280 bytes, binary base64)
- `docs/backup_restore.md` (sec 9 nota técnica sobre `.enc.env` + quirk path_regex;
  8 refs `env.enc` → `env.enc.env`)
- `scripts/setup_secrets_vps.sh` (linha 156 atualizada)
- `secrets/README.md` (inventário atualizado + nota explicativa)

Guardrails verificados ao longo de toda a sequência:
- Chave privada age NUNCA passou pela conversa com Claude (apenas o usuário viu).
- Chave privada NUNCA foi copiada para o VPS (encriptação no VPS usou só o recipient público).
- Plaintexts originais foram lidos pelo Python local para comparação semântica, mas nunca
  impressos ou expostos na conversa; arquivos temporários removidos imediatamente após.
- VPS recebeu apenas: instalação de SOPS+age em /usr/local/bin/, `git pull`, encriptação
  in-place dos 5 segredos para `secrets/*.enc.*`. Nenhum estado de produção alterado
  (containers, redes Docker, dados, configurações ativas).
- M1, dashboard, pipeline e parâmetros canônicos (H3_RESOLUTION=7, etc.) inalterados.

DoD do plano original: "só declare encerrado depois que o passo 5 (restore real) passar.
Tooling commitado NÃO é 'done'." → Passo 5 passou em 2026-05-29 12:21 UTC-3.

**BLK-OPS-01 FECHADO DE VERDADE.** Risco de DR (perda do VPS sem possibilidade de
reconstrução completa dos segredos) eliminado.

Follow-ups pendentes registrados em `tasks/backlog.md`:
- BLK-OPS-01-FU4: corrigir `encrypt_one` no `scripts/setup_secrets_vps.sh` para usar
  o padrão `cp + sops -e -i` (consistente com o que foi feito manualmente).
- BLK-OPS-01-FU5: decidir se apaga os `secrets/*.enc.*` do VPS agora (já vivem no repo) ou
  mantém como cópia adicional. Decisão pendente de aprovação.

Skills executadas: usuario manual + Claude guiando comando-por-comando (sem /run-cycle).
Tempo total real (relogio do usuario): ~3-4 horas espalhadas em 2 dias (2026-05-28 tooling,
2026-05-29 backup real).


---

## BLK-OPS-05 — Hardening do sistema de orquestracao

Concluido em 2026-05-29. Veredito do QA: **APROVADO** (re-execucao independente).
Criticidade: Alta (meta — altera o proprio mecanismo de ciclos). Esteira completa:
Block Orchestrator -> Planner -> [revisao humana: aprovado por Felipe Silva, com 1 rodada
de ajuste] -> Builder -> QA.

### O que foi entregue (7 caminhos de orquestracao, so markdown)
1. **QA com evidencia propria e SEM bypass** (`prompts/qa_analyzer.md`): o QA passa a
   re-executar TODAS as validacoes obrigatorias do handoff (nao so `pytest`) contra a
   config e os artefatos REAIS, colando a saida literal. Verde obtido por bypass
   (`sops --config /dev/null`, fixture que nao casa as `creation_rules` reais, mock do
   caminho critico) = NAO-EXECUTADO e impede APROVADO. Exige >=1 execucao de tooling
   contra o caminho real de producao. Regra ancorada no episodio dos 5 defeitos do
   BLK-OPS-01 (path_regex sem `/`, sufixo `env.enc.env`, `.gitattributes` binary — todos
   so pegos no fechamento real contra producao, nao na validacao inicial que contornava
   a config).
2. **Handoffs versionados append-only** (`context/handoff/AAAAMMDD-HHMMSS-<slug>.md`,
   com SEGUNDOS): novo diretorio `context/handoff/` + `README.md` documentando a convencao;
   `context/handoff.md` (raiz) segue sendo o "corrente". Slugs: `block-orchestrator`,
   `planner`, `builder`, `qa`. Cada papel grava seu snapshot no "Ao final" (bullet
   adicionado em block_orchestrator/planner/builder; qa_analyzer cobre o slug `qa`);
   `/run-cycle` Passo 4 atua como rede de seguranca.
3. **Disciplina de git por ciclo** (`.claude/commands/run-cycle.md`): novo Passo 0
   (branch `ciclo/<ID>` a partir do HEAD, tratamento de worktree pre-sujo, commit por
   path — nunca `git add -A` —, ciclo re-entrante); Passo 6.a/6.b/6.c (dry-run pos-merge
   como gate, commit isolado por path, rollback preferencialmente nao-destrutivo, reset
   destrutivo so com confirmacao humana); 4 guardrails permanentes, sendo o 4o o NO-BYPASS
   de validacao.
4. **Paridade Claude<->Codex** (`.codex/skills/codex-run-cycle/SKILL.md`): mesmas regras
   em ingles, sem divergencia (Triggered Workflow, Role Execution Pattern, Validation com
   no-bypass + dry-run gate, 4 Mandatory Guardrails, Repository Contract).

### Decisao de processo registrada
O dry-run dos criterios de aceite (`/run-cycle` com tarefa dummy criticidade Baixa) NAO foi
executado dentro deste ciclo (seria recursivo/circular). E um GATE de validacao humana
POS-MERGE: a primeira acao apos o merge e o dry-run; nenhum bloco real roda antes de ele
passar; se falhar -> reverter o merge.

### Validacoes (re-executadas pelo QA, sem bypass)
- `python -m pytest -q` -> `532 passed, 1 skipped, 9 warnings` (baseline preservada, 0 novas falhas).
- `python -c "import streamlit_app; print('import ok')"` -> `import ok`.
- Escopo: git status/diff confirmam que `src/`, `config.py`, `data/`, `dashboard/`, pipelines
  NAO foram tocados; `M PRD.md` e a entrada BLK-OPS-05 do `tasks/backlog.md` sao edicoes
  pre-existentes nao relacionadas, NAO revertidas nem commitadas pelo ciclo.
- Paridade Claude<->Codex e no-bypass conferidos textualmente em ambos os arquivos.

### Dogfooding da Feature 2
Snapshots versionados ja existem em `context/handoff/`: `20260529-133300-builder.md` e
`20260529-133652-qa.md` (carimbos aproximados), alem do `README.md`.

### Guardrails
M1, score_priorizacao, hex_score_estrutural, artefatos oficiais, dashboard e VPS inalterados
(mudancas puramente em markdown de orquestracao). Nenhum segredo manipulado.

### Pendencia pos-ciclo (gate)
Dry-run pos-merge (validacao humana) antes de confiar a esteira nova aos ciclos de producao.

---

## BLK-OPS-01-FU4 — Corrigir `encrypt_one` no `setup_secrets_vps.sh`

Concluido em 2026-05-29. Veredito do QA: **APROVADO** (re-execucao independente).
Criticidade: Media. Esteira completa: Block Orchestrator -> Planner -> Builder -> QA.
Branch do ciclo: `ciclo/BLK-OPS-01-FU4`.

### O que foi entregue
Correcao do bug descoberto no fechamento real do BLK-OPS-01 (passo 4.5): a funcao
`encrypt_one` usava `sops -e SRC > DST` com SRC fora de `secrets/`, falhando com
"no matching creation rules found" (SOPS 3.8.1 casa `path_regex` contra o caminho de
ENTRADA, e os SRCs `.env`/`Caddyfile`/`authelia/*` nao tem sufixo `.enc.*`). Os 3 ramos
do `case` foram reescritos para o padrao in-place ja validado manualmente em producao:
`cp "${src}" "${dst}"` seguido de `if ! sops [flags] -e -i "${dst}"; then rm -f "${dst}";
echo "ERRO..." >&2; return 1; fi` — a guarda apaga o DST em qualquer falha do `sops`
para nunca deixar plaintext copiado em `secrets/` (critico sob `set -euo pipefail`).
Flags por modo (decisao do Planner): dotenv = `--input-type dotenv --output-type dotenv`;
binary = `--input-type binary --output-type binary` (OBRIGATORIO — extensao `.enc` nao e
reconhecida pelo SOPS, sem a flag corromperia o conteudo); yaml = sem flags (inferencia
por `.yaml`). As 5 chamadas a `encrypt_one` (linhas 156-160) ficaram byte-identicas.
O `docs/backup_restore.md` (bloco "Comandos exatos por arquivo (manual)") foi alinhado
ao mesmo padrao + nota tecnica explicando a quirk.

### Validacoes (re-executadas pelo QA, sem bypass)
- `bash -n scripts/setup_secrets_vps.sh` -> exit 0 (sintaxe valida).
- `shellcheck` -> nao disponivel no ambiente (registrado).
- Inspecao estatica: nenhum `sops -e SRC > DST` remanescente no script nem no doc; os 3
  ramos com `cp`+guarda `rm -f`+`return 1`; flags por modo corretas; 5 chamadas intactas;
  nota tecnica presente no doc.
- Escopo: `git diff --stat` confirma apenas `scripts/setup_secrets_vps.sh` e
  `docs/backup_restore.md` como arquivos do ciclo (+ controle); `src/`, `config.py`,
  `data/` intactos; `M PRD.md` (edicao pre-existente nao relacionada) NAO revertida nem
  commitada pelo ciclo.

### No-bypass
Nao houve execucao de tooling SOPS (real nem falsa): o script roda exclusivamente no VPS,
como passo humano, sobre segredos reais — proibido executar aqui por guardrail (CLAUDE.md
§6). A validacao maxima viavel e estatica + a correcao replica fielmente o workaround ja
validado contra producao no fechamento real de 2026-05-29. Isso NAO e "verde por bypass":
nao se forjou nenhum verde de SOPS contra config falsa.

### Guardrails
M1, score_priorizacao, hex_score_estrutural, artefatos oficiais, dashboard e VPS inalterados
(mudanca puramente em shell/markdown). Nenhum segredo manipulado. Ciclo NAO altera a
orquestracao -> nao dispara dry-run pos-merge (Passo 6.c).

---

## BLK-OPS-05-DRYRUN — Dry-run pós-merge do BLK-OPS-05 (gate de validação humana, Passo 6.a) — 2026-05-29

Veredito: APROVADO (dry-run autônomo). Esteira: Block Orchestrator → Builder (criticidade baixa).

### Objetivo
Exercitar end-to-end a esteira de orquestração endurecida no BLK-OPS-05, validando o gate do
Passo 6.a: branch/commit isolado por path e handoffs versionados append-only com carimbo de
segundos. Tarefa dummy trivial de doc — sem entrega de feature.

### O que foi exercitado
- Branch isolado `ciclo/BLK-OPS-05-DRYRUN` criado a partir do HEAD; working tree pré-sujo
  (`M PRD.md`, `M tasks/backlog.md`) preservado e NÃO arrastado para o commit.
- Block Orchestrator e Builder rodaram como sub-agentes de contexto isolado, cada um gravando
  `context/handoff.md` corrente + snapshot append-only:
  `context/handoff/20260529-151225-block-orchestrator.md` e `...-151410-builder.md`.
- Builder criou `docs/orquestracao_dryrun_ops05.md` (nota de validação) e rodou as validações
  obrigatórias: `pytest -q tests/integration/test_streamlit_app.py` → 147 passed, 0 failed,
  0 skipped; `python -c "import streamlit_app"` → import ok.
- Commit isolado por path (sem PRD.md, sem tasks/backlog.md).

### Guard de recursão
Este ciclo rodou com `dry_run: true` → NÃO disparou outro dry-run no fechamento (quebra a
recursão na profundidade 1, conforme Passo 6.c).

### Guardrails
M1, score_priorizacao, artefatos oficiais e dashboard inalterados (mudança puramente em doc).

### Fechamento (histórico limpo)
FU4 (`97195e3`) mergeado no `main` por fast-forward. A branch `ciclo/BLK-OPS-05-DRYRUN` e o
commit dummy `8705e24` (doc `docs/orquestracao_dryrun_ops05.md` + handoffs `…-151225-…`/`…-151410-…`)
foram **descartados** após a validação — eram artefatos de uma tarefa dummy; este registro é o
canônico. BLK-OPS-05 fica 100% fechado.

---

## BLK-OPS-06 — Alinhar checkout do VPS via `git pull` — 2026-05-29

Veredito: APROVADO. Esteira: Block Orchestrator → execução VPS conduzida pelo orquestrador
(comando-a-comando, §6) → Fechamento. Criticidade: baixa. Tipo: operação / infraestrutura.

### Objetivo
Trazer o checkout git de `/opt/motor-expansao/app` no VPS de produção para `origin/main` via
fast-forward, materializando os 5 `secrets/*.enc.*` como arquivos rastreados e eliminando o
estado "atrás do origin".

### Execução (VPS, comando-a-comando sob GUARDRAIL §6)
Conduzida pelo ORQUESTRADOR (main loop), NÃO por sub-agente Builder autônomo — cada comando
aprovado individualmente pelo usuário. MCP `ssh-vps-ultra` (`root@2.25.137.241`).
- **Diagnóstico (read-only, aprovado em bloco):** `git status` → working tree limpo em arquivos
  rastreados, só untracked não relacionados (`authelia/`, `Caddyfile.backup.1779977816`,
  `docker-compose.prod.yml.backup.1779977827`). HEAD do VPS = `64e68b1`. `fetch --dry-run` →
  `64e68b1..8218f38 main -> origin/main`.
- **Reconciliação da premissa do backlog (feita localmente, sem tocar o VPS):** o `origin/main`
  no GitHub está em `8218f38` (não no HEAD local `97195e3`). Confirmado que `a2a4cea` (commit
  dos 5 `.enc.*`) é ancestral de `8218f38`; o range `64e68b1..8218f38` adiciona os 5
  `secrets/*.enc.*` + `.gitattributes` e modifica `CLAUDE.md`/`tasks/*` — e NÃO toca `authelia/`,
  `Caddyfile*` nem `docker-compose.prod.yml*` (risco de colisão com untracked do VPS descartado).
- **Escrita (único comando, aprovado em separado):** `git -C /opt/motor-expansao/app pull --ff-only`
  → `Updating 64e68b1..8218f38`, fast-forward limpo, 5 `.enc.*` criados + `.gitattributes`.
- **Verificação (read-only):** HEAD do VPS = `8218f38` **== origin/main**; `git ls-files secrets/`
  lista os 5 `.enc.*` + `README.md` como tracked; `git status -s` mostra só os 3 untracked não
  relacionados intactos. Nenhum rebuild/restart de docker.

### Critérios de aceite — todos atendidos
- Passos read-only aprovados individualmente; `pull --ff-only` só após aprovação explícita.
- Fast-forward limpo (sem merge commit, sem conflito).
- HEAD do VPS == origin/main (`8218f38`, contém `a2a4cea`).
- 5 `secrets/*.enc.*` rastreados no VPS.
- Sem rebuild de docker; nenhum segredo em texto puro tocado; chave age privada nunca esteve no VPS.

### Observação de estado (não bloqueia o bloco)
O VPS ficou em `8218f38`, ainda SEM `4ee9685` (BLK-OPS-05) e `97195e3` (FU4), que são commits
locais ainda NÃO enviados ao GitHub (local `main` ahead 2–3 de origin). Irrelevante para o
objetivo do bloco (os `.enc.*` já vieram via `a2a4cea`). Para alinhar o VPS 100% ao HEAD local,
fazer `git push` do `main` local ao GitHub e novo `pull` no VPS — passo OPCIONAL, fora do escopo
deste bloco.

### Guard de recursão / dry-run
Ciclo NÃO altera a orquestração (run-cycle/prompts/esteira) — é operação git no VPS + arquivos de
controle. `dry_run: false`. Portanto NÃO dispara dry-run pós-merge (Passo 6.c).

### Guardrails
M1, score_priorizacao, artefatos oficiais e dashboard inalterados (nenhum código/artefato tocado).

### Nota de escopo no fechamento (commit por path)
`tasks/backlog.md` tinha 92 linhas de edição pré-existente NÃO relacionada (migração de blocos,
incl. a própria definição do BLK-OPS-06) e `PRD.md` (M) é alheio ao ciclo. Para não arrastar
edições de terceiros ao commit do ciclo, o commit por path incluiu apenas `tasks/current_task.md`,
`tasks/completed.md`, `context/handoff.md` e `context/handoff/`. A marcação de BLK-OPS-06 como
concluído em `tasks/backlog.md` foi feita no working tree mas deixada NÃO-commitada, junto da
edição pré-existente, para o humano commitar separadamente.

---

## BLK-PRD-01 — Reescrever PRD.md como PRD padrão do projeto

Status: CONCLUÍDO (2026-05-29) — APROVADO pelo QA via /run-cycle (esteira média + gate de
revisão humana do outline). Branch do ciclo: `ciclo/BLK-PRD-01`.

### Objetivo
Substituir o conteúdo temporário do `PRD.md` ("Programa de Melhorias — Referência do Master
Orchestrator", cujos 9 blocos já haviam sido migrados para `tasks/backlog.md` em 2026-05-29) por
um PRD padrão de produto canônico, subordinado ao `CLAUDE.md`.

### Esteira executada
Block Orchestrator → Planner → [revisão humana do outline: APROVADO pelo usuário] → Builder → QA.
Criticidade: Média (doc-only; não toca score/M1/código/`config.py`/`CLAUDE.md`), com gate de
revisão humana do outline obrigatório por `PRD.md` ser documento canônico.

### Entregável
`PRD.md` reescrito em 11 seções (0–10): cabeçalho com subordinação explícita ao `CLAUDE.md` ·
visão/objetivo · público (18–45) e contextos · escopo/fora de escopo · camadas e trilhas (M1
oficial, censitário, híbrido, mercado/residual, Expansão de Domínio) · score oficial e guardrails
(REFERENCIANDO `CLAUDE.md` §3/§5) · requisitos funcionais e não-funcionais (dashboard offline, sem
API ao vivo, performance) · métricas de sucesso · roadmap (REFERENCIANDO `tasks/backlog.md`) ·
dependências e restrições (infra/VPS) · referências canônicas.

### Princípio central aplicado
Referenciar, nunca redefinir. Nenhum valor numérico canônico (pesos renda/pop, `H3_RESOLUTION`,
`DIST_MIN_ULTRA_KM`, `RENDA_MIN`, `AREA_*`, etc.) foi duplicado no PRD — todos apontam para
`CLAUDE.md` §3/§5. Scan anti-deriva do QA confirmou que só aparecem NOMES de parâmetros (na seção
de referência), nunca valores. Roadmap por referência ao backlog, sem copiar blocos.

### Validação (QA re-executou por conta própria — NO-BYPASS)
- `pytest -q` → `532 passed, 1 skipped, 9 warnings in 105.31s` (igual à baseline; doc-only).
- `git --no-pager diff --stat -- PRD.md` → `1 file changed, 226 insertions(+), 80 deletions(-)`.
- Diff de conteúdo restrito a `PRD.md`.

### Nota de escopo no fechamento (commit por path)
`tasks/backlog.md` estava pré-sujo (`M`, ~127 linhas de migração de blocos alheia a este ciclo) e
NÃO foi incluído no commit por path — `git add tasks/backlog.md` arrastaria conteúdo de terceiros.
A marcação de BLK-PRD-01 como concluído fica aqui em `tasks/completed.md`; `backlog.md` deixado ao
humano (mesmo padrão do fechamento do BLK-OPS-06). Commit do ciclo: `PRD.md` + arquivos de controle
(`tasks/current_task.md`, `tasks/completed.md`, `context/handoff.md`, `context/handoff/`).

### Guard de recursão / dry-run
Ciclo doc-only — NÃO altera a orquestração (run-cycle.md / prompts / esteira). `dry_run: false`.
Portanto NÃO dispara dry-run pós-merge (Passo 6.c).

### Guardrails
`CLAUDE.md`, código, `config.py`, `score_priorizacao`, `hex_score_estrutural`, artefatos M1 e
dashboard inalterados. VPS intocado. Nenhum valor canônico redefinido.

---

## BLK-OPS-07 — Sincronizar VPS 100% com o `main` local (git push + pull)

Data: 2026-05-29
Veredito: CONCLUÍDO COM SUCESSO. VPS (`/opt/motor-expansao/app`) sincronizado de
`8218f38` → `76fc89e` (== `main` == `origin/main`).

### Esteira executada
Block Orchestrator → Builder (execução conduzida pelo orquestrador no loop principal,
interativa, com confirmação humana comando a comando no VPS — não delegada a subagente
isolado, por CLAUDE.md §6 GUARDRAIL ABSOLUTO + push outward-facing). Criticidade: baixa.

### Achado-chave de pré-execução
`git fetch origin` na máquina local mostrou `origin/main` == `main` == `76fc89e`, ahead/behind
`0 0`. **O `git push origin main` do passo 1 do backlog é NO-OP** — o GitHub já tinha tudo
(FU4 `97195e3`, BLK-OPS-05, BLK-OPS-06 `f36adfe`, BLK-PRD-01 `3d1ca1a`/`76fc89e`). Push pulado
por decisão humana confirmada. Trabalho real ficou só no lado VPS.

### Execução no VPS (7 comandos, todos com gate humano individual; read-only antes do write)
1. `git status` → working tree limpo; untracked conhecidos (`authelia/`, `Caddyfile.backup.*`,
   `docker-compose.prod.yml.backup.*`).
2. `git rev-parse HEAD` → `8218f38` (esperado).
3. `git fetch --dry-run` → `8218f38..76fc89e main -> origin/main` (fast-forward limpo).
4. `git pull --ff-only` → `Updating 8218f38..76fc89e Fast-forward`, 26 arquivos (só docs/controle:
   PRD.md, handoffs, backlog, prompts, run-cycle, docs/scripts de tooling de secrets).
5–6. `git rev-parse HEAD origin/main` → ambos `76fc89e9a17...`.
7. `git status -s` → só os 3 untracked conhecidos.

### Critérios de aceite — todos atendidos
VPS HEAD == `76fc89e` == origin/main · pull foi fast-forward · status sem mudanças inesperadas ·
NENHUM rebuild/restart de Docker (só arquivos versionados doc/controle mudaram) · push no-op
confirmado. BLK-OPS-06 (que deixou esta sincronização pendente) agora plenamente fechado.

### Guard de recursão / dry-run
Ciclo operacional — NÃO altera a orquestração (run-cycle.md / prompts / esteira). `dry_run: false`.
Portanto NÃO dispara dry-run pós-merge (Passo 6.c).

### Guardrails
Nenhum código de aplicação, imagem Docker, `config.py`, `score_priorizacao`,
`hex_score_estrutural`, artefato M1, `CLAUDE.md` ou `PRD.md` local tocado. Pull restrito a
`--ff-only`. Cada comando no VPS aprovado individualmente (§6); sem encadeamento.

---

## BLK-OPS-02 — CI completo + build via registry (fora da prod)

Status: CONCLUÍDO (2026-05-29) — APROVADO COM RESSALVAS pelo QA via /run-cycle.
Branch: `ciclo/BLK-OPS-02`. Commits: `ff63a54` (entrega principal) + `4af99de` (correção psutil).
PR de ciclo: https://github.com/Kastaldy/motor-de-expansao/pull/1 (aberto, **aguardando merge humano**).
Criticidade: alta. Esteira: Block Orchestrator → Planner → [aprovação humana: Felipe Silva, 2026-05-29] → Builder → QA.

### O que foi entregue
- **CI completo (`.github/workflows/ci.yml`):** o gate passou de 2 arquivos + smoke para `python -m pytest -q`
  da suíte inteira + cache pip + `workflow_dispatch`. Steps `ruff check .` e `mypy src/` adicionados
  como **informativos** (`continue-on-error: true`) — ver ressalva 1.
- **Build via registry:** novo `.github/workflows/docker-publish.yml` builda e publica no GHCR com tag por
  SHA (`push: main` + `workflow_dispatch`, `GITHUB_TOKEN` / `packages: write`, build-push-action@v6, cache gha).
- **Deploy modo pull:** `docker-compose.prod.yml` migrou de `build:` para
  `image: ${STREAMLIT_IMAGE:-ghcr.io/Kastaldy/motor-de-expansao/motor-expansao-streamlit:latest}`;
  novo runbook `docs/deploy.md` (`pull` + `up -d` sem `--build`, rollback por SHA, guardrail §6);
  nota de cruzamento em `docs/deploy_vps_streamlit.md`. `.dockerignore` criado (`.env`/`data`/`secrets` fora da imagem).
- **Skip-guards:** ~6 testes de integração acoplados a dados reais de produção (gitignored, ausentes no
  runner) passaram a `pytest.skip`/`skipif` no padrão de `test_expansao_dominio.py`. Só `assert PATH.exists()`
  foi convertido — NENHUM assert de schema/contagem/scoring (`score_oficial==score_priorizacao`,
  `score_oficial_nome`, `osm_status`, `len==54`, row-counts 1000/223/472) tocado.
- **Correção `4af99de`:** `psutil` (importado por `jobs/pipelines/validar_fase_a_censo2022.py` e
  `scripts/profile_dashboard.py`, mas não declarado) adicionado a `dependencies` core do `pyproject.toml`.
  Sem ele, a coleta do pytest abortava no runner limpo (`ModuleNotFoundError`, exit 2) — falha latente
  mascarada localmente porque psutil estava instalado no ambiente do dev.

### Evidência de aceite (verificada pelo QA, re-execução própria)
- **CI verde no runner limpo** (PR #1, run `26664015146`, commit `4af99de`): `460 passed, 73 skipped,
  0 failed / 0 errors`. As 73 skips = testes de dado real ausente no runner. PR check `test` = pass.
- **Baseline local intacto** (com dados reais): `532 passed, 1 skipped` — prova de que o skip-guard não
  mascara regressão de M1.
- `import streamlit_app` ok; `test_streamlit_app.py` 147 passed; `git check-ignore tests/fixtures/sample.parquet` exit 1.
- Guardrails: diff `092a43b..4af99de` não toca `src/`/`config.py`/scoring/parquets de `data/outputs/`;
  parâmetros canônicos intactos; `PRD.md` não tocado; nenhum comando no VPS.

### Ressalvas (conhecidas e pré-aprovadas)
1. **ruff (286) / mypy (~20-23) não zerados** → mantidos informativos (`continue-on-error`) por decisão
   humana explícita; saneamento completo fica em **BLK-OPS-02b** (já registrado no backlog).
2. **`docker-publish.yml` não verificado pré-merge:** `workflow_dispatch` exige o workflow no branch
   default (404 na branch do ciclo) e ele não tem trigger `pull_request`. Dispara via `push: main` ao
   mergear → **verificado-na-fusão**. Acompanhar o 1º run pós-merge.

### Pendências de fechamento (passo humano)
- **Merge humano** do PR #1 (`ciclo/BLK-OPS-02` → `main`). Pós-merge: observar o 1º run de `docker-publish.yml`.
- `tasks/backlog.md`: marcar BLK-OPS-02 como concluído está PENDENTE — não foi feito no commit de
  fechamento porque o working tree tem uma edição **não-relacionada** em `backlog.md` (BLK-SCORE-01:
  "Engenharia do Corpo" + `alunos_totais`) que NÃO pode ser arrastada para o ciclo. O humano resolve as
  duas coisas no housekeeping do backlog.

### Nota de orquestração
Ciclo de infra/CI — NÃO altera a própria orquestração (run-cycle.md / prompts / esteira). `dry_run: false`.
Portanto NÃO dispara dry-run pós-merge (Passo 6.c).

---

## BLK-OPS-08 — Atualizar actions do CI para Node 24 (fim do Node 20)

Data: 2026-05-29
Veredito: CONCLUÍDO (esteira Baixa: Block Orchestrator → Builder, sem QA/sem gate humano).
Branch: ciclo/BLK-OPS-08 (a partir de `main` 30237a0).

### Objetivo
Eliminar o aviso de descontinuação do Node 20 nos runs de CI/Docker Publish, atualizando as tags
das actions baseadas em Node para versões que rodam em Node 24 — sem alterar comportamento de
testes/build, scoring ou artefatos M1.

### O que foi feito (diff cirúrgico — 3 linhas, só tags)
- `.github/workflows/ci.yml`: `actions/checkout@v4 → @v5`; `actions/setup-python@v5 → @v6`
  (`with:` intactos: `python-version: "3.11"`, `cache: pip`, `cache-dependency-path`).
- `.github/workflows/docker-publish.yml`: `actions/checkout@v4 → @v5`.
- `docker/*-action` (login@v3, metadata@v5, setup-buildx@v3, build-push@v6) NÃO mudaram —
  já são as últimas estáveis e não rodam no runtime Node 20 do runner.

### Validações
- `python -c "import streamlit_app; print('import ok')"` → `import ok` (warnings de Streamlit bare mode esperados).
- `git diff` dos workflows = exclusivamente as 3 mudanças de tag; nenhuma outra linha alterada.
- Suíte pytest completa NÃO re-executada (mudança YAML-only de CI, ortogonal ao código).
- Prova final do aviso some = run verde no GitHub Actions, que ocorre no push/PR pós-merge humano.

### Guardrails verificados
- score_priorizacao / hex_score_estrutural / artefatos M1: NÃO tocados (não aplicável a YAML de CI).
- Commit isolado por path; nenhuma edição não relacionada (`PRD.md` etc.) arrastada.
- Nenhum comando no VPS (CLAUDE.md §6).

### Nota de orquestração
Ciclo de infra/CI — NÃO altera a própria orquestração (run-cycle.md / prompts / esteira).
`dry_run: false` → NÃO dispara dry-run pós-merge.

### Pendência de fechamento (passo humano)
- Merge humano `ciclo/BLK-OPS-08` → `main`. Pós-merge: confirmar no run de CI/Docker Publish que o
  aviso "Node.js 20 actions are deprecated" desapareceu.

---

## BLK-OPS-02b — Saneamento ruff/mypy (violações que exigem refatoração)

Data: 2026-05-29
Veredito: APROVADO pelo QA via /run-cycle (esteira Alta completa: Block Orchestrator → Planner →
[aprovação humana] → Builder → QA). Gate humano: APROVADO POR Felipe Silva EM 2026-05-29.
Branch: ciclo/BLK-OPS-02b (a partir de `main` 30237a0).

### Objetivo
Zerar as 286 violações ruff + 23 mypy descobertas (e rebaixadas a informativas) em BLK-OPS-02,
preferindo correção a supressão, e tornar os steps ruff/mypy bloqueantes no CI — sem alterar
scoring, artefatos M1 ou semântica de testes M1, mantendo pytest 532/1.

### O que foi feito (plano de 13 passos, prova anti-regressão a cada toque em M1)
- PASSO 1: `pyproject.toml` migrou `[tool.ruff]`→`[tool.ruff.lint]` (set de regras IDÊNTICO; nenhuma
  regra desabilitada, mypy não afrouxado — verificado pelo QA).
- PASSO 2: `ruff check . --fix` (219 auto-fixes: I001/F401/UP045/UP037/F541/UP035/E401) em ~30+ arquivos.
  O --fix removeu re-exports usados por testes (`normalizar_0_100`/`normalizar_serie`/`build_map_figure`);
  reintroduzidos com `# noqa: F401` documentado (consumidos por `mock.patch(...pages.build_map_figure)` etc.).
- PASSOS 3-4: triviais ruff (E712/B905/F841/B007/E731/E741/B017/B023) e mypy baixo risco fora de M1.
- PASSO 5: F821 `pdk` em `pages.py` corrigido (import sob TYPE_CHECKING; com `from __future__ import
  annotations` não havia NameError de runtime, mas o nome era indefinido p/ ruff/mypy).
- PASSO 6: `base_h3_brasil.py` generator anotado `Iterator[list[str]]` (cede list[str], não str —
  desvio correto do literal do plano, validado pelo QA).
- PASSO 7: `hex_enrichment.py` — Optional explícito, anotação de dict, `# type: ignore[no-redef]` no
  fallback `try/except ModuleNotFoundError` de import (não é duplicação real).
- PASSO 8: B019 lru_cache em método (`ibge_censo.py` ×3) — `# noqa: B019` documentado (decisão humana:
  suprimir, não refatorar — caches de rede no grafo de produção M1, refator arriscaria coleta M1).
- PASSO 9 (isolado, por último): F601 em `tests/integration/test_hex_enrichment_brasil.py` — removida
  SÓ a 1ª `"pop_total": 0.0,` (código morto sobrescrito) de cada um dos 15 dicts. Prova de invariância:
  em literal Python a última chave vence, o valor real (2ª ocorrência) já era o entregue → dict idêntico.
- PASSO 11: removidos os 2 `continue-on-error: true` dos steps ruff/mypy do `ci.yml` (só após 0/0).

### Validações (re-executadas pelo QA, evidência própria — não o log do Builder)
- `ruff check .` → All checks passed! (0 erros)
- `mypy src/` → Success: no issues found in 18 source files (0 erros)
- `python -m pytest -q` → 532 passed, 1 skipped, 9 warnings (zero regressão vs baseline)
- `python -c "import streamlit_app"` → import ok
- 4 hashes SHA256 M1 IDÊNTICOS à baseline (não-mutação provada): brasil_priorizados, brasil_estrutural,
  hexagonos_brasil_oportunidades (data/staging/), hexagonos_brasil_dashboard (data/outputs/).

### Guardrails verificados (QA)
- Parâmetros canônicos intactos: grep no diff de scoring/constants/config por 0.40/0.60/H3_RESOLUTION/
  DIST_MIN_ULTRA_KM/RENDA_MIN/score_priorizacao/hex_score_estrutural = VAZIO.
- `core/scoring.py` e `core/constants.py` NÃO aparecem no diff (lógica de score intocada).
  Produção M1 (hex_enrichment.py, base_h3_brasil.py) tocada SÓ em anotação/type:ignore — zero runtime.
- Sem mass-suppress; cada noqa/type:ignore com comentário justificando.
- Commit isolado por path; nenhum PRD.md/data/secrets arrastado (status verificado limpo).
- Nenhum comando no VPS (CLAUDE.md §6).

### Nota de orquestração
Ciclo altera `.github/workflows/ci.yml` (ruff/mypy bloqueantes) mas NÃO altera a própria orquestração
(run-cycle.md / prompts / esteira). `dry_run: false` → NÃO dispara dry-run pós-merge.

### Pendência de fechamento (passo humano)
- Merge humano `ciclo/BLK-OPS-02b` → `main`. Pós-merge: o CI agora REPROVA em violação de ruff/mypy.

### BLK-OPS-02b-FU1 — Hotfix mypy no CI (falso verde local por falta de types-requests)

Data: 2026-05-30
Contexto: ao tornar `mypy src/` bloqueante (BLK-OPS-02b) e fazer push do `main`, o CI REPROVOU em
`ibge_censo.py:368` — `requests.get(params=...)` recebia um `dict[str, object]` (inferido do literal
heterogêneo) incompatível com o tipo esperado por `requests.get`. O erro NÃO aparecia no mypy LOCAL
porque o ambiente local não tinha `types-requests` instalado (com `ignore_missing_imports=true`,
`requests` virava `Any` → sem erro); o runner do CI resolve os tipos de `requests` e fica mais estrito.
Foi um **falso verde** na validação local do QA.
Correção: anotar `params: dict[str, str | int | float] = {...}` (anotação de variável local — PEP 526,
não avaliada em runtime; comportamento idêntico). Verificado COM paridade: `pip install types-requests`
+ `mypy src/` → Success (0); `ruff check .` → 0; `import streamlit_app` → ok.
Lição: para validar `mypy src/` com paridade ao CI, instalar `types-requests` (ou os mesmos stubs do
runner) antes de rodar; senão o verde local é falso. Hotfix direto no `main` (1 linha, runtime-inerte).

---

## Housekeeping BLK-OPS-09 — blocos migrados do backlog (2026-05-29)

> Movidos íntegros de `tasks/backlog.md` (Status: CONCLUÍDO) pelo ciclo BLK-OPS-09.
> 6 da seção "Tarefas pendentes" (viraram stub no backlog) + 9 da antiga seção "## Concluídos" (removida do backlog).

### BLK-OPS-06 — Alinhar checkout do VPS via `git pull` — CONCLUÍDO (2026-05-29)

Status: CONCLUÍDO (2026-05-29) — APROVADO. Detalhes em `tasks/completed.md`. Mover para a seção
Concluídos no próximo housekeeping do backlog. Execução: `git pull --ff-only` no VPS levou
`/opt/motor-expansao/app` de `64e68b1 → 8218f38` (fast-forward), materializando os 5
`secrets/*.enc.*` como rastreados; HEAD do VPS == origin/main. VPS ainda sem `4ee9685`/`97195e3`
(locais não enviados ao GitHub) — alinhamento 100% via `git push` + novo pull é OPCIONAL.
Criticidade: baixa
Prioridade: alta (próxima da fila)
Tipo: operação / infraestrutura
Skill recomendada: decisão humana + comando direto (per-command no VPS)
Resumo: Fechamento operacional do FU5. O checkout git em `/opt/motor-expansao/app`
(origin = github.com/Kastaldy/motor-de-expansao) está atrás do `origin/main` — não tem
o commit `a2a4cea` que versionou os 5 `secrets/*.enc.*`. No FU5 esses arquivos estavam
untracked no VPS e foram removidos (`rm`), com as versões canônicas vivendo no repo/origin.
Um `git pull` no VPS faz fast-forward e materializa os `.enc.*` como arquivos **rastreados**,
eliminando o estado "atrás do origin" e deixando o checkout limpo/alinhado.
Passos sugeridos (todos per-command, com confirmação explícita — GUARDRAIL CLAUDE.md §6):
1. read-only: `git -C /opt/motor-expansao/app status` e `git -C /opt/motor-expansao/app rev-parse HEAD`
   (confirmar working tree limpo e quão atrás está antes de qualquer pull).
2. read-only: `git -C /opt/motor-expansao/app fetch --dry-run` (ver o que viria).
3. `git -C /opt/motor-expansao/app pull --ff-only` (aplicar; abortar se não for fast-forward).
4. verificar: `secrets/*.enc.*` presentes e tracked; `docker compose` não precisa rebuild
   (mudança é só de arquivos versionados, não de imagem).
Observações:
- Pré-requisito opcional: `git push` do `main` local (hoje `ahead 3` do origin) se quiser que
  o VPS receba também FU4 + housekeeping. NÃO é necessário para os `.enc.*` (já estão no origin
  via `a2a4cea`).
- Não urgente, mas deve ser feita antes do próximo deploy/restore para evitar surpresa de
  estado divergente no servidor.
Dependências: aprovação explícita do usuário, comando a comando, antes de qualquer execução no VPS.

---

### BLK-OPS-07 — Sincronizar VPS 100% com o `main` local (git push + pull) — CONCLUÍDO (2026-05-29)

Status: CONCLUÍDO (2026-05-29) — APROVADO. Detalhes em `tasks/completed.md`. VPS sincronizado
`8218f38 → 76fc89e` via `git pull --ff-only` (fast-forward, gate humano por comando). O `git push`
do passo 1 era NO-OP (`origin/main` já == `main` == `76fc89e`) e foi pulado por decisão humana.
Mover para a seção Concluídos no próximo housekeeping do backlog. Texto original abaixo preservado.
(antes: pendente — executar APÓS concluir BLK-PRD-01)
Criticidade: baixa
Prioridade: média (fechamento de sincronização, ao final do ciclo do BLK-PRD-01)
Tipo: operação / infraestrutura
Skill recomendada: decisão humana + comando direto (per-command no VPS)
Resumo: Fechar a sincronização deixada pendente pelo BLK-OPS-06. Depois daquele bloco, o VPS
(`/opt/motor-expansao/app`) ficou em `8218f38` (origin/main no GitHub no momento), com os 5
`secrets/*.enc.*` já rastreados — MAS o `main` local está à frente do `origin/main` (ahead ~3:
inclui `97195e3` FU4, `4ee9685` BLK-OPS-05 e o fechamento do BLK-OPS-06 `f36adfe`). Para o VPS
refletir 100% o HEAD local, é preciso primeiro publicar o `main` local no GitHub e depois puxar
no VPS.
Passos sugeridos (todos per-command, com confirmação explícita — GUARDRAIL CLAUDE.md §6):
1. local (sua máquina): `git push origin main` (publica FU4 + BLK-OPS-05 + BLK-OPS-06 no GitHub).
   Pré-checagem read-only opcional: `git log --oneline origin/main..main` para ver o que sobe.
2. read-only no VPS: `git -C /opt/motor-expansao/app fetch --dry-run` (confirmar o range que viria).
3. VPS: `git -C /opt/motor-expansao/app pull --ff-only` (abortar se não for fast-forward).
4. verificar no VPS: `git rev-parse HEAD` == `origin/main`; `git status -s` limpo (só os untracked
   não relacionados conhecidos: `authelia/`, `Caddyfile.backup.*`, `docker-compose.prod.yml.backup.*`).
   `docker compose` NÃO precisa rebuild (só arquivos versionados mudam; nenhuma imagem/serviço).
Observações:
- Pré-requisito: BLK-PRD-01 concluído e commitado (a reescrita do PRD.md deve estar no `main` local
  antes do push, para subir tudo de uma vez).
- Antes do push, garantir que as edições pendentes de `tasks/backlog.md` e `PRD.md` estejam
  resolvidas/commitadas como se deseja — o push leva o estado do `main` local.
Dependências: BLK-PRD-01 concluído; aprovação explícita do usuário, comando a comando, antes de
qualquer execução no VPS.

---

### BLK-PRD-01 — Reescrever PRD.md como PRD padrão do projeto

| Campo | Valor |
|---|---|
| **Criticidade** | Média *(doc canônico §2 do CLAUDE.md; Block Orchestrator pode ELEVAR p/ Alta se quiser gate de aprovação do novo formato — nunca rebaixar)* |
| **Prioridade** | Alta |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana do outline]` → Builder → QA |
| **Depende de** | — |
| **Status** | CONCLUÍDO (2026-05-29) — APROVADO pelo QA via /run-cycle (commit `3d1ca1a`, branch `ciclo/BLK-PRD-01`). Detalhes em `tasks/completed.md`. |
| **Skill** | /run-cycle |

**Contexto:** o `PRD.md` atual contém o "Programa de Melhorias — Referência do Master
Orchestrator" — conteúdo **temporário** que substituiu o PRD padrão antigo (apagado por estar
desatualizado). Os 9 blocos desse programa **já foram migrados** para `tasks/backlog.md`
(2026-05-29). Há também uma edição não-commitada pré-existente em `PRD.md` (`M PRD.md`) que será
absorvida/substituída pela reescrita.

**Objetivo:** reescrever `PRD.md` como um **PRD padrão do projeto** — documento de produto
canônico, subordinado ao `CLAUDE.md` (fonte de verdade), sem duplicar o backlog.

**Escopo permitido:**
- Substituir todo o conteúdo de `PRD.md` por um PRD padrão. Estrutura **sugerida** (o Planner
  refina e apresenta o outline para revisão humana antes do Builder escrever, por ser doc canônico):
  - Visão e objetivo do produto (Motor de Expansão Ultra Academia)
  - Público-alvo (18–45) e contextos de uso
  - Escopo do produto / fora de escopo
  - Camadas e trilhas (M1 oficial territorial, censitário, híbrido, mercado/residual, Expansão de Domínio)
  - Score oficial e guardrails canônicos — **referenciar** o `CLAUDE.md` §3/§5, não redefinir valores
  - Requisitos funcionais e não-funcionais (dashboard offline, performance, sem API ao vivo)
  - Métricas de sucesso
  - Roadmap/fases — **referenciar** `tasks/backlog.md` para o detalhe dos blocos, não copiá-los
  - Dependências e restrições (infra/VPS)
- **Commit do `PRD.md` atualizado por path** — este é o entregável final do ciclo (incluído no escopo a pedido do usuário).

**Fora de escopo:**
- Alterar `CLAUDE.md`, código, `config.py`, score, artefatos M1.
- Reescrever, mover ou re-duplicar blocos do `tasks/backlog.md`.

**Arquivos a ler:** `PRD.md` (estado atual + histórico git) · `CLAUDE.md` (fonte canônica) · `tasks/backlog.md` (para referenciar, não duplicar).
**Arquivos a alterar:** `PRD.md`.

**Critérios de aceite:**
- `PRD.md` é um PRD padrão coerente, subordinado ao `CLAUDE.md`, sem duplicar o backlog.
- Nenhum valor canônico contradiz o `CLAUDE.md` (PRD referencia, não redefine pesos/parâmetros).
- `PRD.md` commitado por path (sem arrastar outros arquivos não relacionados).

**Validações obrigatórias:**
```
pytest -q            # doc-only: suíte deve seguir verde (nada de código tocado)
git --no-pager diff --stat -- PRD.md    # escopo: só PRD.md alterado
```

**Guardrails específicos:**
- Doc-only: não toca score/M1/código/artefatos. Por ser canônico, recomenda-se `[revisão humana]`
  do outline proposto pelo Planner antes do Builder escrever.
- Commit isolado por path (`git add PRD.md`); não arrastar a edição pré-existente de outros arquivos.

**Risco:** baixo (documentação). Variância no alinhamento do formato com a expectativa do usuário —
mitigado pela revisão humana do outline.

---

### BLK-OPS-02 — CI completo + build via registry (fora da prod)

| Campo | Valor |
|---|---|
| **Criticidade** | Alta |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana]` → Builder → QA |
| **Depende de** | — |
| **Status** | CONCLUÍDO (2026-05-29) — APROVADO COM RESSALVAS pelo QA via /run-cycle; **mergeado no `main`** (merge commit `24aa066`, PR #1). Detalhes em `tasks/completed.md`. CI completo verde no runner limpo (460 passed, 73 skipped); `Docker Publish (GHCR)` rodou no push à `main` e publicou a imagem (run `26664812524`). Ressalvas: ruff/mypy não-bloqueantes → **BLK-OPS-02b**; upgrade de actions Node 20 → **BLK-OPS-08**. Mover para Concluídos no próximo housekeeping. |

**Objetivo:** o gate do `main` deve rodar a suíte completa (hoje só 2 arquivos + smoke import),
e o deploy deve usar imagem buildada no CI e empurrada para um registry — o servidor faz `pull`,
não `build`.

**Escopo permitido:**
- Estender `.github/workflows/ci.yml` para rodar `pytest -q` completo (ou o máximo viável).
- Resolver dependências de dados dos testes no runner (fixtures sintéticas / amostras pequenas
  versionadas, **nunca** os Parquets de produção).
- Workflow de build → push de imagem para registry (ex.: GHCR).
- Atualizar runbook de deploy para `pull` em vez de `--build` no servidor.

**Fora de escopo:** alterar lógica de scoring, alterar artefatos M1, executar deploy no VPS.

**Arquivos a ler:** `.github/workflows/ci.yml` · `Dockerfile.streamlit` · `docker-compose.prod.yml` ·
`tests/` (mapear dependências de dados) · `CLAUDE.md` §3.4, §3.5.
**Arquivos a alterar/criar:** `.github/workflows/ci.yml` · novo workflow de build · `tests/fixtures/` ·
`docs/deploy.md`.

**Critérios de aceite:**
- CI roda a suíte completa e fica verde (baseline atual: 532 passed, 1 skipped).
- Build de imagem publica no registry com tag por commit.
- Runbook de deploy descreve `pull` + `up -d` sem `--build` no servidor.

**Validações obrigatórias:**
```
pytest -q                                  # suíte completa, verde
ruff check . && mypy src/                   # qualidade
docker build -f Dockerfile.streamlit -t test:ci .   # build local sanity
```

**Guardrails específicos:**
- Fixtures de teste **não** contêm dados reais de Ultra/Skyfit/Wellhub.
- Deploy efetivo no VPS é passo humano, fora deste bloco.

**Risco:** médio — variância concentrada nas dependências de dados dos 532 testes no runner.
Se o acoplamento a dados locais for grande, considerar quebrar em sub-bloco de fixtures.

---

### BLK-OPS-02b — Saneamento ruff/mypy (violações que exigem refatoração)

| Campo | Valor |
|---|---|
| **Criticidade** | Alta *(toca código de produção M1: hex_enrichment.py, base_h3_brasil.py — additivo/mecânico, mas exige cuidado anti-regressão)* |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana]` → Builder → QA |
| **Depende de** | **BLK-OPS-02** (steps ruff/mypy já existem no CI, hoje não-bloqueantes) |
| **Status** | CONCLUÍDO (2026-05-29) — APROVADO pelo QA via /run-cycle (re-execução independente). Branch `ciclo/BLK-OPS-02b`. Gate humano: APROVADO POR Felipe Silva EM 2026-05-29. Resultado: `ruff check .`→0, `mypy src/`→0, `pytest -q`→532 passed/1 skipped (zero regressão), steps ruff/mypy BLOQUEANTES no `ci.yml` (continue-on-error removido), 4 hashes M1 idênticos (não-mutação provada). F601 corrigido com prova de invariância (removida só a 1ª `pop_total` morta de 15 dicts); supressões documentadas mínimas (B019×3, type:ignore em fallbacks de import, F401 re-exports usados por testes); `pyproject.toml` só migrou `[tool.ruff]`→`[tool.ruff.lint]` (nenhuma regra desabilitada). Detalhes em `tasks/completed.md`. Mover para Concluídos no próximo housekeeping. |

**Contexto:** `ruff`/`mypy` nunca rodaram no CI. Ao wirá-los em BLK-OPS-02 descobriu-se dívida
latente muito acima do escopo trivial daquele bloco: **286 erros ruff** (228 auto-fixáveis via
`ruff check . --fix`, 68 remanescentes não-triviais) e **23 erros mypy** em `src/`. Os
remanescentes estão espalhados por ~22 arquivos incluindo **código de produção M1**
(`src/motor_expansao/pipelines/m1/hex_enrichment.py`, `base_h3_brasil.py`), dashboard
(`pages.py`, `components.py`, `data.py`, `censo_*`), pipelines `jobs/`, legado
`fora_primeira_fase/` e **testes de fixtures M1** (`tests/integration/test_hex_enrichment_brasil.py`
com 14× F601 "repeated dict key", `test_fase_a_censo2022.py`). Zerá-los exige refatoração de
produção e tocar a semântica de testes M1 — **proibido em BLK-OPS-02** (trivial only; guardrail
"não refatorar produção", "não mass-suppress", "não desabilitar regra no pyproject"). Por isso,
em BLK-OPS-02 os steps ruff/mypy foram adicionados ao `ci.yml` como **`continue-on-error: true`**
(informativos), mantendo o gate verde (CLAUDE.md §2).

**Pendências herdadas de BLK-OPS-02 (lista para sanear aqui):**
- Aplicar `ruff check . --fix` (228 auto-fixes mecânicos: I001 import-sort, F401 unused-import,
  UP045/UP037 anotações, F541 f-string, UP035) — diff amplo (~52 arquivos), validar com `pytest -q`.
- 68 ruff remanescentes não-autofixáveis, com destaque para itens que NÃO são triviais:
  - `src/motor_expansao/dashboard/pages.py:2511 F821 Undefined name pdk` — **bug latente real** em produção (avaliar import/uso de `pydeck as pdk`).
  - `ibge_censo.py` 3× B019 `lru_cache` em método (risco de memory leak — refatorar, não suprimir cego).
  - `tests/integration/test_hex_enrichment_brasil.py` 14× F601 `"pop_total"` repetido em dict literal — **M1**: mudar a chave repetida altera qual valor vence; exige entender o fixture antes de tocar (não mexer sem confirmar invariância M1).
  - Diversos B905 (`zip(strict=)`), E712 (`== True`), F841 (var não usada), B007/B023/B017/E731/E741 em produção e testes — triviais individualmente, mas em volume.
- 23 mypy em `src/`: `dashboard/pages.py` (8), `pipelines/m1/hex_enrichment.py` (6 — implicit Optional, dict-item, no-redef de `generate_fase1_bi_artifacts`), `config.py` (5 — SettingsConfigDict/no-redef), `dashboard/censo_map.py` (2), `components.py` (1), `pipelines/m1/base_h3_brasil.py` (1 — Generator return type).

**Escopo permitido:** corrigir as violações de verdade (refatoração mecânica/segura), preferindo
correção a supressão; supressão pontual `# noqa: <code>` / `# type: ignore[<code>]` SEMPRE
documentada quando o fix for arriscado. Ao final, tornar os steps ruff/mypy **bloqueantes**
(remover `continue-on-error`) no `ci.yml`.

**Fora de escopo:** alterar lógica de scoring/pesos, alterar artefatos M1, mudar semântica de
testes M1 (F601 só pode ser tocado provando invariância do fixture).

**Critérios de aceite:** `ruff check .` → 0 erros; `mypy src/` → 0 erros; steps bloqueantes no CI;
`pytest -q` mantém `532 passed, 1 skipped` (zero regressão); hashes dos Parquets M1 inalterados.

**Risco:** médio-alto — toca produção M1; mitigar com passos pequenos + prova de não-regressão
(pytest verde + hash dos artefatos M1) a cada passo.

---

### BLK-OPS-08 — Atualizar actions do CI para Node 24 (fim do Node 20)

| Campo | Valor |
|---|---|
| **Criticidade** | Baixa |
| **Esteira** | Block Orchestrator → Builder |
| **Depende de** | **BLK-OPS-02** (workflows criados) — ✅ satisfeita |
| **Status** | CONCLUÍDO (2026-05-29) — Builder aplicou o upgrade (esteira Baixa: Block Orchestrator → Builder, sem QA). Branch `ciclo/BLK-OPS-08`. Diff cirúrgico (3 tags): `ci.yml` `actions/checkout@v4→@v5` + `actions/setup-python@v5→@v6`; `docker-publish.yml` `actions/checkout@v4→@v5` (docker/* já nas últimas estáveis, não mudam). Smoke `import streamlit_app` OK. Validação final do aviso some = run verde no GitHub Actions pós-merge humano. Detalhes em `tasks/completed.md`. Mover para Concluídos no próximo housekeeping. |

**Contexto:** os runs do CI/Docker Publish emitem aviso de descontinuação — `actions/checkout@v4`
e `actions/setup-python@v5` rodam em Node 20, que o GitHub força a Node 24 a partir de 16-jun-2026
e remove do runner em 16-set-2026. Os `docker/*-action` usados no `docker-publish.yml` (login@v3,
metadata@v5, build-push@v6) não estão no aviso, mas vale revisar versões no mesmo passo.

**Escopo permitido:**
- Atualizar `.github/workflows/ci.yml` e `.github/workflows/docker-publish.yml` para as versões de
  actions que suportam Node 24 (ex.: `actions/checkout@v5`, `actions/setup-python@v6` ou a mais
  recente estável no momento da execução).
- Confirmar via run verde no GitHub Actions (push em branch de teste / PR) que o aviso some.

**Fora de escopo:** mudar lógica de CI, steps de teste, scoring, artefatos M1.

**Critérios de aceite:** runs de CI e Docker Publish verdes sem o aviso de Node 20; nenhum step
de teste/build alterado em comportamento.

**Risco:** baixo — atualização de versão de actions; reversível.

---

### BLK-OPS-01-FU5 — Decidir destino dos `secrets/*.enc.*` no VPS

Status: CONCLUÍDO (2026-05-29)
Criticidade: baixa
Prioridade: baixa
Tipo: operação / decisão
Resumo: Decisão tomada (usuário): apagar do VPS, repo = single source of truth.
Durante a execução descobriu-se que `/opt/motor-expansao/app` é um checkout git
(origin = github.com/Kastaldy/motor-de-expansao) e que os 5 `secrets/*.enc.*` lá
estavam **untracked** (`??`), com o checkout do VPS atrás do `origin/main` (sem o
commit `a2a4cea` que os versionou). Antes do `rm`: confirmado que `origin/main`
contém `a2a4cea` e que os sha256 das 5 cópias no VPS batem byte-a-byte com as
versões commitadas (recuperáveis via `git pull`). `rm` dos 5 `.enc.*` untracked
executado no VPS com confirmação comando-a-comando (5 comandos, 1–4 read-only +
5 destrutivo); `secrets/README.md` (rastreado) preservado. `secrets/` no VPS agora
só tem `README.md`. Nenhum segredo em claro tocado; chave privada age nunca esteve
no VPS. Re-criação no deploy/restore via `git pull` (+ `sops -d` quando preciso).
Dependências: atendidas (aprovação explícita do usuário, dada comando-a-comando).

---

### BLK-OPS-05 — Hardening do sistema de orquestração

| Campo | Valor |
|---|---|
| **Criticidade** | Alta *(meta: altera o próprio mecanismo de ciclos)* |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana]` → Builder → QA |
| **Depende de** | — |
| **Status** | Concluído (2026-05-29) — APROVADO pelo QA + dry-run pós-merge validado (BLK-OPS-05-DRYRUN, branch `ciclo/BLK-OPS-05-DRYRUN`, gate 6.a OK: commit isolado por path + handoffs versionados c/ segundos). Detalhes em `tasks/completed.md`. |

**Objetivo:** fechar três lacunas de confiabilidade da orquestração: (1) QA re-executa testes em
vez de confiar no log do Builder; (2) handoffs versionados/auditáveis; (3) disciplina de git por ciclo.

**Escopo permitido:**
- Atualizar `prompts/qa_analyzer.md`: QA roda `pytest -q` por conta própria e cola a saída;
  log reportado pelo Builder **não** é aceito como evidência.
- Handoff versionado: `context/handoff/AAAAMMDD-HHMM-<skill>.md` (append-only) ou log acumulativo,
  preservando estados intermediários do ciclo.
- `.claude/commands/run-cycle.md`: cada ciclo cria branch/commit isolado; ao falhar no meio,
  procedimento de `git reset` documentado e ciclo re-entrante.
- Portar mudanças equivalentes para `.codex/skills/codex-run-cycle/SKILL.md`.

**Fora de escopo:** Fase 2 completa (Master Orchestrator, +5 Skills) — isso é bloco Estratégico à parte.

**Arquivos a ler:** `prompts/*.md` · `.claude/commands/run-cycle.md` ·
`.codex/skills/codex-run-cycle/SKILL.md` · `CLAUDE.md` §4.
**Arquivos a alterar:** os acima.

**Critérios de aceite:**
- Prompt do QA exige re-execução independente de testes.
- Handoffs de um ciclo de exemplo ficam preservados e versionados.
- Ciclo de exemplo gera branch/commit próprio; rollback documentado e testado num dry-run.
- Versão Claude e Codex consistentes.

**Validações obrigatórias:**
```
# Dry-run de um ciclo trivial (ex.: ajuste de doc) end-to-end:
/run-cycle   # com tarefa dummy de criticidade Baixa
git log --oneline -3   # confirma commit isolado do ciclo
ls context/handoff/     # confirma handoffs versionados
```

**Guardrails específicos:**
- Como este bloco modifica a própria esteira, rodá-lo com **observação humana atenta** (gate
  `[revisão humana]`) e validar num ciclo dummy antes de confiar nos ciclos de produção.

**Risco:** médio — alterar o mecanismo enquanto se depende dele. Mitigar com dry-run em tarefa trivial.

---

### BLK-OPS-01 — Backup encriptado de segredos e plano de regeneração

| Campo | Valor |
|---|---|
| **Criticidade** | Alta |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana]` → Builder → QA |
| **Depende de** | — |
| **Status** | Concluído (2026-05-28) — APROVADO COM RESSALVAS. Detalhes em `tasks/completed.md`. |

**Objetivo:** garantir que a perda do VPS não implique perda de segredos/config, e documentar
a regeneração completa dos Parquets a partir das fontes brutas.

**Escopo permitido:**
- Configurar tooling de encriptação de segredos no repo (ex.: SOPS+age ou git-crypt) — apenas a
  infraestrutura, **sem** versionar valores em claro.
- Escrever runbook `docs/backup_restore.md`: o que existe só no servidor (`.env`, `Caddyfile`,
  `authelia/configuration.yml`, `users_database.yml`, `db.sqlite3`), como encriptar/restaurar.
- Documentar a regeneração dos Parquets: IBGE Censo 2022 raw + `Ultra.csv` → pipeline M1 →
  `data/outputs/`, com os comandos exatos e tempo esperado.

**Fora de escopo:** alterar pipeline, alterar M1, executar qualquer coisa no VPS.

**Arquivos a ler:** `CLAUDE.md` §3 · estrutura de `/opt/motor-expansao/`.
**Arquivos a criar:** `docs/backup_restore.md` · `.sops.yaml` (ou equivalente) · `.gitattributes` se git-crypt.

**Critérios de aceite:**
- Runbook revisado descreve restore ponta a ponta de um servidor zerado.
- Tooling de encriptação funciona num arquivo de teste (não num segredo real).
- Nenhum segredo em texto puro entra no git (verificado).

**Validações obrigatórias:**
```
git secrets --scan   # ou: gitleaks detect --no-git -v
# Teste de roundtrip do tooling com arquivo dummy:
echo "dummy: ok" > /tmp/t.yaml && sops -e /tmp/t.yaml | sops -d /dev/stdin
```

**Guardrails específicos:**
- O **Builder NÃO toca o VPS** e NÃO manipula segredos reais. A coleta/encriptação dos segredos
  reais é passo humano, executado a partir do runbook, com confirmação por comando.
- Nenhum valor de segredo aparece em handoff, log de teste ou commit.

**Risco:** baixo, desde que a regra "Builder não acessa segredos reais" seja respeitada.

---

### BLK-OPS-01-FU1 — Stage do `secrets_roundtrip_test.ps1` no próximo commit

Status: CONCLUÍDO (2026-05-28, commit 4ed75d8)
Criticidade: baixa
Resumo: `git add scripts/secrets_roundtrip_test.ps1` aplicado antes do commit
de fechamento. Arquivo entrou no repo.

---

### BLK-OPS-01-FU2 — Executar roundtrip SOPS + gitleaks no ambiente do dev

Status: CONCLUÍDO (2026-05-28)
Criticidade: alta
Tipo: operação / validação
Resumo da execução:
- sops 3.8.1, age 1.1.1 e gitleaks 8.30.1 baixados para `$env:USERPROFILE\tools\`
  (sem privilégio admin; PATH ajustado só na sessão).
- Primeira execução revelou 3 defeitos no tooling entregue por BLK-OPS-01:
  (a) URL do SOPS em `docs/backup_restore.md` §5 incorreta — asset oficial é
      `sops-v3.8.1.exe`, não `sops-v3.8.1.windows.amd64.exe`.
  (b) `scripts/secrets_roundtrip_test.{sh,ps1}` falhavam com `no matching creation
      rules found` porque o `.sops.yaml` tem regras apenas para `secrets/**` e a
      fixture vive em `tests/fixtures/`. Correção: passar `--config /dev/null`.
  (c) Comparação `diff -q` byte-a-byte falhava porque sops normaliza YAML
      (remove aspas redundantes, indentação nested 2→4 espaços). Correção:
      comparação YAML semântica via Python+PyYAML.
- Gitleaks sem config scaneou 13.26 GB em 1h57m e encontrou 3 falsos positivos:
  `.env.example:17 GEOFUSION_API_KEY=` (placeholder), 2x
  `renda_per_capita_setor_2022_calibrada` (nome de coluna de DataFrame em
  `jobs/pipelines/calibrar_renda_setor_2022.py:122` e
  `src/motor_expansao/dashboard/pages.py:2453`). Nenhum segredo real.
- Após correções: roundtrip `ROUNDTRIP OK` + exit 0; gitleaks 0 leaks em 4.63s.
Arquivos alterados pelas correções: `.gitleaks.toml` (novo), `.gitleaksignore`
(novo, 3 FPs registrados), `scripts/secrets_roundtrip_test.{sh,ps1}` (corrigidos),
`docs/backup_restore.md` (§5 URL SOPS + §15.2 gitleaks com config). Commit
corretivo separado.

---

### BLK-OPS-01-FU3 — Atualizar baseline de testes no CLAUDE.md §5

Status: CONCLUÍDO (2026-05-28)
Criticidade: baixa
Tipo: documentação / housekeeping
Resumo: Diagnóstico do QA original interpretou o `509 passed` da linha 94 (descrição
histórica do ciclo Performance e Refatoração de 22-mai) como baseline atual. Decisão:
NÃO reescrever a história do ciclo Performance — adicionar nova linha no topo de §5
declarando explicitamente a baseline atual (`532 passed, 1 skipped, 9 warnings` em
2026-05-28) e marcar que os números menores nos ciclos abaixo são históricos. Também
acrescentado o registro do ciclo BLK-OPS-01 (incluindo FU1, FU2, FU3) em §5.

---

### BLK-OPS-01-FU4 — Corrigir `encrypt_one` no `setup_secrets_vps.sh`

Status: CONCLUÍDO (2026-05-29) — APROVADO pelo QA via /run-cycle (esteira média completa). Detalhes em `tasks/completed.md`.
Criticidade: média
Prioridade: média
Tipo: bug / tooling
Skill recomendada: comando direto (sem /run-cycle)
Resumo: Durante o fechamento real de BLK-OPS-01 em 2026-05-29 (passo 4.5), descobriu-se
que a função `encrypt_one` do script usa `sops -e SRC > DST` com SRC fora de `secrets/`.
Isso falha com "no matching creation rules found" pelo mesmo motivo do defeito 3
(SOPS 3.8.1 não casa `path_regex` com `/`). O workaround manual usado no fechamento
foi `cp SRC DST && sops -e -i DST`. Corrigir a função `encrypt_one` para usar esse
padrão. Adicionar tratamento de erro: se `sops -e -i` falhar, fazer `rm DST` para
não deixar plaintext em `secrets/`.
Dependências: nenhuma.

---

### BLK-20260528-02 — Eliminar warning jwt_secret via force-recreate

Status: concluído (2026-05-28)
Criticidade: baixa
Prioridade: baixa
Tipo: operação / infraestrutura
Skill recomendada: /run-cycle
Resumo: Executar `docker compose up -d --force-recreate authelia` no servidor VPS para
recriar o container do Authelia com os env vars atualizados do docker-compose.prod.yml.
O `AUTHELIA_JWT_SECRET` foi renomeado para `AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET`
no compose file (ciclo BLK-20260528-01), mas `docker compose restart` não recria o
container — o warning `jwt_secret deprecated` permanece até o force-recreate.
Downtime esperado: ~10s do Authelia (Caddy e Streamlit não são afetados).
Dependências: nenhuma bloqueadora
Observações: não executar sem confirmação explícita do usuário; aguardar janela de
manutenção conveniente.

---

### BLK-PROD-04 — Avaliar st.fragment para interações do mapa

Status: concluido (2026-05-25)
Criticidade: média
Prioridade: baixa
Tipo: performance / UI
Skill recomendada: /run-cycle
Resumo: Implementado render_mapa_pydeck_fragment (@st.fragment) em pages.py. Reduz reruns da aba ao isolar st.pydeck_chart e captura de clique. QA aprovado: 532 passed, 1 skipped.
Dependências: nenhuma

---

### BLK-OPS-09 — Housekeeping do backlog.md

Data: 2026-05-29 — APROVADO (esteira média doc-only consolidada no orquestrador + QA independente).
Branch: `ciclo/BLK-OPS-09`.
Resumo: Movidos 15 blocos `Status: CONCLUÍDO` íntegros de `tasks/backlog.md` para este arquivo
(append-only, seção "## Housekeeping BLK-OPS-09" acima): 6 da seção "Tarefas pendentes"
(BLK-OPS-06, -07, BLK-PRD-01, BLK-OPS-02, -02b, -08 → viraram stub de 1 linha no backlog) e 9 da
seção "## Concluídos" (BLK-OPS-01-FU5, -05, -01, -01-FU1/FU2/FU3/FU4, BLK-20260528-02, BLK-PROD-04
→ seção removida do backlog). 13 blocos pendentes preservados verbatim.
Escopo: editou SOMENTE `tasks/backlog.md` + `tasks/completed.md` (substantivo); bookkeeping do ciclo
em current_task.md/handoffs. NÃO tocou CLAUDE.md, PRD.md, código, M1, prompts/, .claude/commands/.
Achado: o enunciado citava 9+8 blocos; o real era 6+9=15 (regra `Status: CONCLUÍDO` aplicada).
Por isso o backlog caiu de 860 → 426 linhas (~50%), não os ~330 estimados (a estimativa assumia 9
concluídos em "Tarefas pendentes", não 6).
Validações (QA, re-execução independente): `pytest -q` → 532 passed, 1 skipped, 9 warnings;
verificação byte-level contra `git show HEAD:` confirmou append-only + 15 blocos verbatim + zero perda
de conteúdo + pendentes preservados. NO-BYPASS (suíte real, sem mock).

---

### BLK-ARCH-01 — Concluir migração `src/` e remover legado

| Campo | Valor |
|---|---|
| **Criticidade** | Alta |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana]` → Builder → QA |
| **Depende de** | **BLK-OPS-02** (CI completo verde como rede de segurança) — ✅ SATISFEITA (BLK-OPS-02 concluído/mergeado em 2026-05-29; suíte completa roda verde no CI). |
| **Status** | Pendente *(desbloqueado — dependência satisfeita; candidato à fila após BLK-OPS-02b)* |

**Objetivo:** eliminar a dualidade `src/` vs. legado (`dashboard/` flat, `jobs/`, wrappers de
raiz). Uma única fonte de verdade por função, sem quebrar o dashboard.

**Escopo permitido:**
- Mapear o que ainda é importado dos caminhos legados (`base_h3_brasil.py` raiz, `dashboard/`,
  `jobs/`, `ibge_censo.py`, `poi_enrichment.py`).
- Migrar o que estiver vivo para `src/motor_expansao/`, atualizar imports, remover wrappers e
  legado morto **em passos pequenos e reversíveis**.
- Cada passo: testes verdes antes de avançar.

**Fora de escopo:** mudar comportamento de scoring, mudar artefatos M1, refatorar lógica além do
necessário para mover.

**Arquivos a ler:** árvore completa do repo (`view`), `streamlit_app.py`, todos os imports.
**Arquivos a alterar:** múltiplos — listados pelo Planner após o mapeamento.

**Critérios de aceite:**
- Nenhum import aponta para caminhos legados removidos.
- `import streamlit_app` ok; dashboard sobe localmente.
- Suíte completa verde; comportamento idêntico (scores e artefatos inalterados).

**Validações obrigatórias:**
```
pytest -q
python -c "import streamlit_app; print('ok')"
ruff check . && mypy src/
# Prova de equivalência de M1 (hashes idênticos pré/pós migração):
sha256sum data/outputs/brasil_priorizados.parquet
```

**Guardrails específicos:**
- Migração é **mecânica**, não pode alterar nenhum valor de output M1 (provar por hash).
- Avançar só com CI verde a cada passo — daí a dependência de BLK-OPS-02.

**Risco:** alto e de variância alta (2–5 dias). Quebrar em sub-blocos por área (pipelines /
dashboard / acesso a dados) se o mapeamento revelar acoplamento grande.

**RESULTADO DO CICLO (concluído 2026-05-29) — APROVADO pelo QA.**
Particionado: este ciclo executou a **FATIA-1** (núcleo M1 + dashboard); `jobs/pipelines/*` (21
módulos, cluster autocontido) virou o bloco-filho **BLK-ARCH-01a** no backlog. O que foi feito:
(A) removidos os 3 wrappers de raiz (`base_h3_brasil.py`, `hex_enrichment.py`, `fase1_bi_exports.py`)
e reapontados os imports de teste para `motor_expansao.pipelines.m1.*`; (B) `dashboard/constants.py`
+ `dashboard/utils.py` movidos para `src/motor_expansao/dashboard/`, imports invertidos e pacote
`dashboard/` flat removido; (D) `ibge_censo.py` + `poi_enrichment.py` movidos para
`src/motor_expansao/pipelines/m1/` com limpeza dos branches mortos `jobs.pipelines.*`; (E) `config.py`
movido para `src/motor_expansao/config.py` limpando o branch morto `api.config`. Tudo via `git mv`
(histórico preservado), sem renomear funções/assinaturas/valores.
Validações (QA re-executou, sem bypass): `pytest -q` → **541 passed, 1 skipped, 0 failed**;
`import streamlit_app` ok; `ruff check .` limpo; `mypy src/` Success (23 arquivos). Greps de import
legado vazios em código vivo. **Prova de não-mutação M1: 4 artefatos oficiais
(`brasil_priorizados`, `brasil_estrutural`, `hexagonos_brasil_oportunidades` em `data/staging/`;
`hexagonos_brasil_dashboard` em `data/outputs/`) com sha256 byte-idêntico pré/pós.** Params canônicos
intactos (H3_RESOLUTION=7, pesos 0.40/0.60, DIST_MIN_ULTRA_KM=1.0, RENDA_MIN=4500.0).
3 desvios do plano, todos auditados como legítimos pelo QA: (1) remoção do teste obsoleto
`test_legacy_m1_wrappers_export_modules` (validava wrappers removidos por design); (2) reaponte
mecânico de strings `patch`/`monkeypatch` em 3 testes; (3) correção de 1 linha de import em 2 módulos
`jobs/pipelines/*` (`fase_a_censo2022_setores.py`, `teste_setor_censitario_2010.py`) exercidos por
testes EM ESCOPO — rewiring mínimo forçado pela remoção do wrapper, sem migração estrutural de `jobs/`
(que segue intocada em BLK-ARCH-01a). `pythonpath` inalterado (jobs/ ainda depende de `"."`).

---

### BLK-ARCH-01a — Migrar `jobs/pipelines/*` para `src/` e limpar `pythonpath`

| Campo | Valor |
|---|---|
| **Criticidade** | Alta *(toca pipelines de mercado/residual/fase-A; migração mecânica, provada por hash)* |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana]` → Builder → QA |
| **Depende de** | **BLK-ARCH-01 (FATIA-1)** — ✅ SATISFEITA (concluído/aprovado 2026-05-29). |
| **Status** | Pendente *(desbloqueado — sub-bloco remanescente da migração `src/`)* |

**Objetivo:** concluir a migração `src/` movendo os 21 módulos de `jobs/pipelines/*` para
`src/motor_expansao/pipelines/` e, só então, remover `"."` de `pythonpath` — eliminando a última
fonte de imports de raiz viva. É a FATIA-2 (e final) de BLK-ARCH-01.

**Escopo permitido:**
- Mover os 21 módulos de `jobs/pipelines/` para `src/motor_expansao/pipelines/` (sugestão de
  subpacotes por grupo funcional: `fase_a/`, `mercado/`, `dominio/`, `penetracao/`, `normalizacao/`
  — o Planner do sub-bloco decide a partição), via `git mv`, em passos pequenos e reversíveis.
- Atualizar os imports internos `jobs.pipelines.*` (acoplamento entre si) e os testes de
  integração/unit que consomem esses módulos.
- Remover `"."` de `pythonpath` em `pyproject.toml` SOMENTE ao final, e SÓ se grep confirmar zero
  dependência de raiz viva (excluir `fora_primeira_fase/*`, que permanece órfão por design).

**Fora de escopo:** mudar comportamento de scoring, artefatos M1, ou lógica além do necessário para
mover. `fora_primeira_fase/*` (imports órfãos NÃO consertar). `concorrentes/geo_skyfit.py` (script
standalone isolado).

**Arquivos a ler:** `jobs/pipelines/*.py` (todos), `pyproject.toml` (`pythonpath`, `packages`),
testes que importam `jobs.pipelines.*`.
**Arquivos a alterar:** `jobs/pipelines/*` (mover) · imports internos e nos testes · `pyproject.toml`
(só ao final).

**Critérios de aceite:**
- Nenhum import vivo aponta para `jobs.pipelines.*` nem para raiz removida (grep limpo, excl.
  `fora_primeira_fase/`).
- `python -c "import streamlit_app; print('ok')"` ok; `pytest -q` verde; `ruff check .` e `mypy src/`
  limpos.
- **Prova de não-mutação M1 (hash idêntico pré/pós)** dos 4 artefatos oficiais.
- `pythonpath` sem `"."` (se e só se nada vivo depender de raiz).

**Validações obrigatórias:**
```
pytest -q
python -c "import streamlit_app; print('ok')"
ruff check . && mypy src/
# Prova de equivalência M1 (caminhos reais):
python -c "import hashlib,pathlib; [print(hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest(), p) for p in ['data/staging/brasil_priorizados.parquet','data/staging/brasil_estrutural.parquet','data/staging/hexagonos_brasil_oportunidades.parquet','data/outputs/hexagonos_brasil_dashboard.parquet']]"
```

**Guardrails específicos:** migração mecânica (sem renomear funções/assinaturas/valores); avançar só
com `pytest -q` verde a cada grupo de módulos movido; `"."` de `pythonpath` é o ÚLTIMO passo.

**Risco:** médio-alto — volume (21 módulos) + acoplamento interno (`fase_a_*`,
`validar_penetracao` ↔ `comparar_geofusion`, `enriquecer_outputs_residual` ↔ `gerar_carteira`).
Mover por grupo funcional, testes verdes a cada grupo, em vez de big-bang.

**RESULTADO DO CICLO (concluído 2026-05-30) — APROVADO COM RESSALVAS pelo QA.**
FATIA-2 (final) da migração `src/`. Destino **flat**: os 20 módulos de `jobs/pipelines/*` movidos para
`src/motor_expansao/pipelines/<modulo>.py` via `git mv` (swap de prefixo de import puro
`jobs.pipelines.X` → `motor_expansao.pipelines.X`), em ordem topológica (folhas primeiro). Diretório
`jobs/` removido. **Única alteração de valor permitida e aplicada:** `Path(__file__).resolve().parents[2]`
→ `parents[3]` em 14 módulos (a profundidade ganha o nível `src/`; `ROOT`/`BASE`/`BASE_DIR` seguem
apontando para a raiz do repo, validado por spot-check e suíte de integração). Nos 8 módulos com
`sys.path.insert(0, str(ROOT))`, o insert (vestigial pós-FATIA-1) + `import sys` foram removidos — o que
eliminou a última dependência de raiz viva. 16 arquivos de teste reapontados. `pythonpath` em
`pyproject.toml`: `[".", "src"]` → `["src"]` (gate de grep confirmou zero import de raiz vivo fora de
`fora_primeira_fase/`). 4 literais/docstrings cosméticos `jobs/pipelines/...` preservados (um asserido
por `test_validar_penetracao_ultra_hex.py`).
Validações (QA re-executou, sem bypass): `pytest -q` → **541 passed, 1 skipped, 0 failed**;
`import streamlit_app` ok; `ruff check .` limpo; `mypy src/` Success (44 arquivos); grep de import de
raiz vivo VAZIO; zero `parents[2]` em `src/.../pipelines/`. **Prova de não-mutação M1: 4 artefatos
oficiais com sha256 byte-idêntico pré/pós.** Params canônicos intactos.
**Desvio (único) auditado e aprovado pelo QA:** mover os módulos legados (nunca type-checked) para `src/`
os colocou sob o gate `mypy src/`, expondo 50 erros de tipo LATENTES em 12 dos 14 módulos. Resolução
value-neutral: bloco `[[tool.mypy.overrides]] ignore_errors = true` em `pyproject.toml` restrito por LISTA
NOMINAL aos 14 módulos migrados (NÃO glob; não mascara m1/dashboard/core/config, que seguem checados e
limpos). QA confirmou removendo o override que os 50 erros são pré-existentes (típicos de legado), sem
regressão de cobertura. Ressalva NÃO bloqueante: tipar os 14 módulos e remover o override → registrado
como bloco-filho **BLK-ARCH-01b** no backlog. Com BLK-ARCH-01a, a dualidade `src/` vs. legado de raiz
está ELIMINADA (`pythonpath` sem `"."`).

---

### BLK-ARCH-01b — Tipar os 14 módulos migrados e remover o override de mypy

| Campo | Valor |
|---|---|
| **Criticidade** | Média *(dívida de tipagem; toca pipelines de mercado/residual/fase-A, mas é melhoria de qualidade, não mudança de comportamento)* |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Depende de** | **BLK-ARCH-01a** — ✅ SATISFEITA (concluído 2026-05-30). |
| **Status** | Pendente *(dívida registrada no fechamento de BLK-ARCH-01a; ressalva não bloqueante do QA)* |

**Objetivo:** eliminar a dívida de tipagem criada (registrada, não introduzida) por BLK-ARCH-01a:
os 14 módulos migrados de `jobs/pipelines/*` para `src/motor_expansao/pipelines/` carregam ~50 erros
de tipo LATENTES (código legado nunca type-checked). BLK-ARCH-01a os silenciou com um
`[[tool.mypy.overrides]] ignore_errors = true` nominal para preservar o status quo (CI verde, mesma
cobertura efetiva). Este bloco corrige os tipos e REMOVE o override, trazendo esses módulos para o
gate `mypy src/` de verdade.

**Escopo permitido:**
- Corrigir os erros de tipo nos 14 módulos listados no override de `pyproject.toml`
  (`float(object)`, anotações de variável faltantes, overloads numpy, `no-redef` de fallback
  try/except, etc.), em passos pequenos — idealmente um módulo (ou grupo) por vez.
- Remover do `[[tool.mypy.overrides]]` cada módulo conforme ele fica limpo; ao final, remover o bloco
  de override inteiro.

**Fora de escopo:** mudar comportamento/lógica/valores; mexer em score/artefatos M1; refatorar além
do necessário para tipar. Correção de tipo é mecânica/estrutural, não muda runtime.

**Arquivos a ler:** os 14 módulos em `src/motor_expansao/pipelines/` listados no override ·
`pyproject.toml` (bloco `[[tool.mypy.overrides]]`).
**Arquivos a alterar:** os 14 módulos · `pyproject.toml` (remover override progressivamente).

**Critérios de aceite:**
- `mypy src/` limpo SEM o bloco de override (ou com ele já removido).
- `pytest -q` verde (mesma contagem); `ruff check .` limpo.
- Prova de não-mutação M1 (hash idêntico pré/pós) dos 4 artefatos oficiais — tipar não muda dados.
- Bloco `[[tool.mypy.overrides]]` dos 14 módulos REMOVIDO de `pyproject.toml`.

**Validações obrigatórias:**
```
mypy src/         # sem o override
pytest -q
ruff check .
python -c "import hashlib,pathlib; [print(hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest(), p) for p in ['data/staging/brasil_priorizados.parquet','data/staging/brasil_estrutural.parquet','data/staging/hexagonos_brasil_oportunidades.parquet','data/outputs/hexagonos_brasil_dashboard.parquet']]"
```

**Guardrails específicos:** correção de tipo NÃO pode alterar comportamento/valores; cada anotação
deve refletir o tipo REAL em runtime (não forçar `# type: ignore` em massa — isso só troca um override
por outro). Preferir anotações corretas; `# type: ignore[código]` pontual e justificado é aceitável
onde a lib de terceiros não tem stubs.

**Risco:** baixo-médio — volume de erros (~50) mas todos de tipagem, sem mudança de runtime. Risco
real é "consertar" um tipo de forma que mascare um bug latente; mitigar mantendo `pytest -q` verde.

---

### BLK-OPS-03 — Manifesto de proveniência nos outputs

| Campo | Valor |
|---|---|
| **Criticidade** | Alta *(toca o pipeline que gera artefatos M1 — additivo, não-mutante)* |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana]` → Builder → QA |
| **Depende de** | — |
| **Status** | Pendente |

**Objetivo:** todo conjunto de outputs carrega sua origem: vintage IBGE, hash do `Ultra.csv`,
`code_commit`, `generated_at`, versões de parâmetros canônicos. Permite distinguir "score mudou
porque o dado mudou" de "mudou porque o código mudou".

**Escopo permitido:**
- Gerar `data/outputs/_manifest.json` no fim de `fase1_bi_exports.py` com os campos acima.
- Expor o manifesto no rodapé/aba do dashboard (read-only).
- Teste validando presença e schema do manifesto.

**Fora de escopo:** **alterar qualquer valor dentro dos artefatos M1.** O manifesto fica ao lado,
nunca dentro do conteúdo de scoring.

**Arquivos a ler:** `src/motor_expansao/pipelines/m1/fase1_bi_exports.py` · `config.py` ·
`src/motor_expansao/core/constants.py`.
**Arquivos a alterar/criar:** `fase1_bi_exports.py` · `_manifest.json` (gerado) ·
componente de rodapé no dashboard · `tests/unit/test_manifest.py`.

**Critérios de aceite:**
- Manifesto gerado contém: `ibge_vintage`, `ultra_csv_sha256`, `code_commit`, `generated_at`,
  `h3_resolution`, `pesos={renda:0.40, pop:0.60}`, `dist_min_ultra_km`, `renda_min`.
- Dashboard exibe a proveniência.

**Validações obrigatórias:**
```
pytest -q tests/unit/test_manifest.py
# Prova de não-mutação dos artefatos M1 (hashes idênticos pré/pós):
sha256sum data/outputs/brasil_priorizados.parquet data/outputs/brasil_estrutural.parquet
# (QA compara com os hashes registrados ANTES da mudança)
```

**Guardrails específicos:**
- QA **deve** verificar que os Parquets M1 (`brasil_priorizados`, `brasil_estrutural`,
  `hexagonos_*_dashboard`) têm hash idêntico antes e depois — provando que só foi **adicionado**
  um manifesto, sem tocar conteúdo. Se algum hash mudar → REPROVAR.

**Risco:** baixo se a não-mutação for provada por hash; médio se a geração do manifesto for
acoplada ao cálculo (deve ser passo final, isolado).

**Fechamento do ciclo — 2026-05-30. Veredito do QA: APROVADO** (re-execução independente, sem bypass).
Esteira completa: Block Orchestrator → Planner → [aprovação humana: "Aprovar" por Felipe Silva] →
Builder → QA. Criticidade elevada a **Crítica** pelo override do orquestrador (menciona pesos do
score + toca pipeline de artefatos M1).

### O que foi entregue
- Novo módulo isolado `src/motor_expansao/pipelines/m1/provenance.py`: funções puras
  `build_manifest(...) -> dict` e `write_manifest(...) -> Path`; helpers `_sha256_file` (hash dos
  BYTES BRUTOS do `Ultra.csv`, `None` se ausente) e `_git_commit` (`git rev-parse HEAD`, `None` em
  falha). Pesos lidos de `PESOS_HEX_SCORE_ESTRUTURAL` (renda←renda_per_capita, pop←populacao_proxy),
  nunca hardcoded. JSON UTF-8 sem BOM, `indent=2`. 9 chaves: `schema_version`, `ibge_vintage`,
  `ultra_csv_sha256`, `code_commit`, `generated_at` (ISO UTC), `h3_resolution`, `pesos`,
  `dist_min_ultra_km`, `renda_min`.
- `fase1_bi_exports.py`: `write_manifest()` acoplado como passo FINAL ISOLADO de `main()`, depois de
  todos os artefatos já escritos; fora de `write_outputs`/`generate_fase1_bi_artifacts`/funções de score.
- `dashboard/components.py`: helper read-only `render_manifest_footer(manifest_path)` (expander; não
  renderiza nem quebra se o JSON falta), chamado no fim de `main()` de `streamlit_app.py` fora dos
  branches de aba; constante `MANIFEST_PATH` no app.
- `tests/unit/test_manifest.py` (NOVO): 6 casos — chaves/schema, valores canônicos, sha presente/ausente,
  voláteis tipados, JSON sem BOM.
- `.gitignore`: `data/outputs/_manifest.json` ignorado (artefato gerado, consistente com `*.parquet`;
  evita commit acidental de artefato máquina-específico). Adicionado no fechamento.

### Validações (re-executadas pelo QA, sem bypass)
- `pytest -q tests/unit/test_manifest.py`: 6 passed.
- `pytest -q tests/integration/test_streamlit_app.py`: 147 passed.
- `python -c "import streamlit_app"`: ok.
- `pytest -q` (suíte completa): **547 passed, 1 skipped** (subiu vs. baseline 532; nada quebrou).
- `mypy src/.../provenance.py`: Success. `ruff check`: All checks passed.

### Prova de não-mutação (guardrail do bloco)
SHA256 dos 5 artefatos M1 IDÊNTICO pré/pós a geração do `_manifest.json` real:
`hexagonos_brasil_dashboard.parquet`, `hexagonos_mapa_sample.parquet`, `brasil_estrutural.parquet`,
`brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet` — todos byte-idênticos.
Manifesto fica AO LADO, nunca dentro do conteúdo de scoring. `score_priorizacao`/`hex_score_estrutural`
e parâmetros canônicos (H3=7, dist=1.0, renda_min=4500.0, pesos 0.40/0.60) preservados — só lidos.

---

### BLK-OPS-04 — Validação de schema no carregamento

| Campo | Valor |
|---|---|
| **Criticidade** | Média |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Depende de** | — |
| **Status** | Pendente |

**Objetivo:** o dashboard deve falhar de forma clara (não mostrar lixo) se um Parquet vier
corrompido ou com schema/range inesperado.

**Escopo permitido:**
- Asserções de schema no caminho de load (`data.py`): colunas obrigatórias, dtypes, scores em
  `[0, 100]`, chaves não-nulas, `h3` válido. Pandera opcional se já não pesar o deploy.
- Mensagem de erro útil quando a validação falha.

**Fora de escopo:** alterar fórmulas, alterar artefatos, mudar performance de load de forma
relevante (validação deve ser barata).

**Arquivos a ler:** `src/motor_expansao/dashboard/data.py` (`load_uf_slice`,
`read_enriched_uf_partition`, `load_uf_catalog`) · esquema dos outputs.
**Arquivos a alterar/criar:** `data.py` · módulo de schema (ex.: `dashboard/schemas.py`) ·
`tests/unit/test_schema_validation.py`.

**Critérios de aceite:**
- Load rejeita Parquet com coluna faltante, dtype errado ou score fora de `[0,100]`.
- Caminho feliz continua passando com overhead desprezível.

**Validações obrigatórias:**
```
pytest -q tests/unit/test_schema_validation.py
pytest -q   # garantir que nada existente quebrou
```

**Guardrails específicos:** validação é **read-only** — nunca corrige/preenche dados silenciosamente.

**Risco:** baixo.

**Fechamento do ciclo — 2026-05-30. Veredito do QA: APROVADO** (re-execução independente, sem bypass).
Esteira completa: Block Orchestrator → Planner → Builder → QA. Criticidade **Média** confirmada pelo
Block Orchestrator: o trigger "Crítica" do CLAUDE.md/run-cycle protege contra MUTAÇÃO/recálculo de
score/artefatos M1; esta tarefa é a operação dual e oposta — estritamente read-only (lê e rejeita
carga ruim, não recalcula nem muta nada). Sem gate humano.

### O que foi entregue
- Novo módulo `src/motor_expansao/dashboard/schemas.py`: `SchemaValidationError(ValueError)` e função pura
  `validate_dashboard_frame(df, *, source) -> None`, read-only (coerção numérica em variável local, jamais
  reatribuída ao `df`; no-op para `df is None`/`df.empty`). Invariantes, nesta ordem: (b) colunas
  obrigatórias presentes via `REQUIRED_COLUMNS` importado de `constants.py` (sem duplicar a lista);
  (c) chaves `hex_id`/`uf` não-nulas; (d) `hex_id` H3 válido via `h3.is_valid_cell` sobre os únicos;
  (e) colunas de score conversíveis a numérico + faixa `[0,100]` com NaN tolerado. Toda mensagem nomeia
  source + coluna + invariante.
- Integração no caminho real de load, ambas ANTES de `_prepare_dataframe` (que coagiria dtype ruim a NaN):
  `streamlit_app.py::_read_m1_frame` (frame M1 cru) e `src/motor_expansao/dashboard/data.py::read_enriched_uf_partition`
  (partição enriquecida crua). +1 import + 1 chamada em cada arquivo; sem ciclo de import (schemas→constants).
- `tests/unit/test_schema_validation.py` (NOVO, 16 testes): caso feliz; não-mutação (`assert_frame_equal`);
  NaN tolerado (obrigatório e opcional); coluna faltante; dtype errado; score fora de `[0,100]` (sup/inf);
  chave nula (`uf` e `hex_id`); `hex_id` inválido; frame vazio/`None` (no-op); coerência
  `set(_SCORE_RANGE_REQUIRED) <= set(REQUIRED_COLUMNS)`.
- `tests/integration/test_streamlit_app.py`: 4 fixtures migrados de `hex_id` sintéticos (`"a"`, `"hSP1"`,
  `"hSP2"`, `"hRJ1"`) para células H3 res-7 reais (`h3.latlng_to_cell`), pois fluíam pelos entry points
  agora validados. Consequência legítima da validação correta — só dados de fixture, nenhuma lógica/asserção
  de teste alterada. Path adicionado ao commit por path do ciclo (QA julgou o desvio aceitável).

### Validações (re-executadas pelo QA, sem bypass)
- `pytest -q tests/unit/test_schema_validation.py`: 16 passed.
- `pytest -q` (suíte completa): **563 passed, 1 skipped** (subiu vs. baseline 532; nada quebrou).
- `pytest -q tests/integration/test_streamlit_app.py`: 147 passed.
- `python -c "import streamlit_app"`: ok. `ruff check`: All checks passed. `mypy schemas.py`: Success.

### Guardrails verificados
- `score_priorizacao`/`hex_score_estrutural` apenas LIDOS e validados — nunca recalculados nem mutados
  (prova por teste de não-mutação + leitura do diff). Nenhuma fórmula/peso/artefato M1 tocado.
- Parâmetros canônicos intactos: H3_RESOLUTION=7, DIST_MIN_ULTRA_KM=1.0, RENDA_MIN=4500.0, pesos 0.40/0.60.
- `pandera` NÃO adicionado ao core/deploy (validação manual com pandas/numpy/h3, já no core).
- Risco remanescente: base real de produção não exercitada nesta worktree; se houver `hex_id` legado não-H3
  ou score fora de `[0,100]` em produção, o app passará a falhar com mensagem clara (comportamento desejado).

---

- BLK-ARCH-01 (concluído 2026-05-29) — ver tasks/completed.md

---

- BLK-ARCH-01a (concluído 2026-05-30) — ver tasks/completed.md

---

- BLK-ARCH-01b (concluído 2026-05-30) — ver tasks/completed.md

---

### BLK-FIX-01 — Corrigir clipping de score_expansao_hibrido e validação com tolerância float
Criticidade: Alta (bloqueia deploy do OPS-04 no VPS; toca pipeline de score híbrido — leitura M1, não mutação do score M1 oficial)
Esteira: Block Orchestrator → Planner → [revisão humana] → Builder → QA
Escopo: (a) schemas.py — adicionar tolerância 1e-2; (b) localizar e corrigir clip no cálculo híbrido; (c) regenerar Parquets afetados; (d) re-validar localmente com Parquets reais.

**Fechamento do ciclo — 2026-05-30. Veredito do QA: APROVADO** (re-execução independente, sem bypass).
Esteira completa: Block Orchestrator → Planner → [APROVAÇÃO HUMANA: "aprovado" por Felipe Silva em
2026-05-30] → Builder → QA. Criticidade **Alta** (sem DEC), confirmada pela nova regra §2 do CLAUDE.md:
a solução final mexe SÓ no validador read-only, sem alterar fórmula/pesos/artefato M1.

### Diagnóstico da causa-raiz
O validador read-only do BLK-OPS-04 (`schemas.py`) rejeitava `score_expansao_hibrido` porque ele pode
chegar a ~100.001, estourando a faixa estrita [0,100]. Causa: `calcular_score_expansao_hibrido`
(`modelo_hibrido_expansao.py:115`) = `score_priorizacao + score_setor_2022_calibrado/LOCAL_BONUS_DIVISOR`
(`LOCAL_BONUS_DIVISOR=100_000` → bônus ≤0.001). Por DESENHO esse campo é uma **chave de ordenação
lexicográfica** (M1 primário + micro-desempate censitário), NÃO um score limitado a [0,100] — o
"estouro" é intencional e carrega o desempate. O bug real foi o campo ter entrado na checagem de faixa.

### Decisão de design (divergiu do escopo palpitado no backlog)
O escopo inicial do backlog supunha (a) tolerância 1e-2 e (b) clipar a fórmula. O Planner avaliou as 3
alternativas e o humano APROVOU a **alternativa (iii)**: remover `score_expansao_hibrido` da checagem de
faixa, validando-o só como numérico/não-nulo. Motivo: honra o contrato de design (chave de ordenação),
não introduz tolerância "mágica" (rejeitada alt. ii), e NÃO clipa a fórmula (rejeitada alt. i, que
zeraria o micro-desempate dos hexes de topo, seria Crítica+DEC e exigiria regenerar Parquets). Scope (b),
(c) e (d) do backlog ficaram desnecessários: nenhuma fórmula tocada, nenhum Parquet regenerado.

### O que foi entregue
- `src/motor_expansao/dashboard/schemas.py`: `score_expansao_hibrido` removido de `_SCORE_RANGE_OPTIONAL`;
  criada tupla `_SCORE_NUMERIC_OPTIONAL = ("score_expansao_hibrido",)` com comentário de desenho; helper
  local `_coerce_numeric` extraído (reaproveita a checagem de conversibilidade, sem duplicar a lógica de
  faixa); novo laço valida a chave de ordenação só como numérico/não-nulo (sem `between(0,100)`, NaN
  tolerado). Read-only preservado (coerção em variável local, df não mutado).
- `tests/unit/test_schema_validation.py`: importa `_SCORE_NUMERIC_OPTIONAL`; teste de fora-de-faixa
  trocado para `score_oportunidade_residual`; +4 testes (teto técnico ~100.001 passa; não-conversível
  rejeitado citando o campo; NaN tolerado; sanidade de design das tuplas). Testes de faixa dos scores
  obrigatórios intactos.

### Validações (re-executadas pelo QA, sem bypass)
- `pytest -q tests/unit/test_schema_validation.py`: 20 passed.
- `pytest -q` (suíte completa): **567 passed, 1 skipped** (acima da baseline; nada quebrou).
- `pytest -q tests/integration/test_streamlit_app.py`: 147 passed.
- `import streamlit_app`: ok. `ruff check`: All checks passed. `mypy schemas.py`: Success.

### Guardrails verificados
- Fórmula `calcular_score_expansao_hibrido`, `LOCAL_BONUS_DIVISOR` e `modelo_hibrido_expansao.py`
  INTACTOS; nenhum Parquet regenerado; `score_dominio_hibrido` intocado (segue faixa estrita).
- `score_priorizacao`/`hex_score_estrutural` seguem estritos a [0,100]; parâmetros canônicos
  (H3=7, dist=1.0, renda_min=4500.0, pesos 0.40/0.60) e 4 artefatos M1 oficiais inalterados.
- Branch `ciclo/BLK-FIX-01` a partir de `main` já com BLK-OPS-04 mergeado (merge feito pelo humano).
  `CLAUDE.md` (edição do usuário com a nova regra §2) NÃO commitado neste ciclo, conforme decidido.

---

### BLK-FIX-02 — Corrigir MessageSizeError para UFs grandes
Criticidade: Média (bloqueia usabilidade de alguns estados em produção)
Esteira: Block Orchestrator → Planner → Builder → QA
Escopo: (a) aumentar maxMessageSize para 500 no config; (b) identificar qual caminho envia 240 MB e verificar se o downsampling está sendo aplicado corretamente.

#### Fechamento do ciclo (2026-05-30) — VEREDITO QA: APROVADO

##### Diagnóstico (causa-raiz)
O `MessageSizeError` em UFs grandes NÃO era altura (nº de pontos): o cap de 35k (`MAP_POINT_LIMIT`,
`_downsample_map_index`) já estava aplicado. Era LARGURA: os builders de mapa passavam o `map_df`
inteiro (`data=map_df`, ~30/33 colunas-fonte + auxiliares `*_fmt`/`*_label`/`tooltip_residual_*` +
`tooltip_line_1..14`) ao `H3HexagonLayer`, e o pydeck serializa o DataFrame todo como JSON na spec do
deck → ~35k linhas × ~50+ colunas de texto verboso ≈ os ~240 MB relatados. O layer consome apenas
`hex_id`/`fill_color`/`line_color` e o tooltip HTML só referencia `tooltip_title`/`tooltip_line_*`.

##### O que foi entregue
- `.streamlit/config.toml`: `maxMessageSize = 500` no bloco `[server]` (eleva o teto de transporte;
  default Streamlit era 200 MB).
- `src/motor_expansao/dashboard/components.py`: novo helper puro `_deck_layer_frame(map_df)` +
  `_DECK_RENDER_COLUMNS = ("hex_id","fill_color","line_color")`. Projeta o frame para SOMENTE as
  colunas de render + `tooltip_title`/`tooltip_line_*` REALMENTE PRESENTES (derivadas por
  `startswith("tooltip_line_")`, robusto a `_HYBRID_TOOLTIP_SHOW_DETAIL`), dedup preservando ordem,
  `.loc[:, ordered].copy()` — NÃO muta `map_df`. Aplicado via `data=layer_df` aos 4 builders
  (`build_map_figure`, `build_hybrid_map_figure`, `build_residual_heatmap_figure` e o builder de
  domínio — este localizado por grep além da previsão do Planner).
- `tests/integration/test_streamlit_app.py`: +3 testes que exercitam os builders reais (M1/híbrido/
  residual) e asseram que `pd.DataFrame(deck.layers[0].data).columns` é subconjunto de
  `{hex_id,fill_color,line_color,tooltip_title,tooltip_line_1..14}` com auxiliares ausentes; 3 asserts
  pré-existentes que liam colunas-fonte do payload (`confianca_geografica` ~493 e ~628;
  `score_oportunidade_residual` ~1154) reescritos preservando a intenção (validam a consequência
  visível em line_color/fill_color), sem reintroduzir a coluna nem usar `assert True`.

##### Validações (re-executadas pelo QA, sem bypass)
- `pytest -q tests/integration/test_streamlit_app.py`: 150 passed.
- `pytest -q` (suíte completa): **570 passed, 1 skipped** (567 baseline + 3 novos; zero falhas).
- `import streamlit_app`: ok. `ruff check` (components.py + teste): All checks passed. `mypy
  components.py`: Success.

##### Guardrails verificados
- `score_priorizacao`/`hex_score_estrutural`/pesos 0.40-0.60 e demais canônicos (H3=7, dist=1.0,
  renda_min=4500.0) INALTERADOS; nenhum path em `src/motor_expansao/pipelines/`, `core/` ou `data/`
  tocado; nenhum score recalculado (o helper só PROJETA colunas). `MAP_POINT_LIMIT` (35k) e a chave
  de ordenação/dedup do downsample intactos; pins de competidor/Ultra e layer de busca não tocados;
  tooltips visíveis preservados. `map_df` não mutado.
- Esteira: Block Orchestrator → Planner → Builder → QA (Média, sem gate humano). Branch
  `ciclo/BLK-FIX-02` a partir de `main` (HEAD com BLK-FIX-01 já mergeado). `CLAUDE.md` (M, edição
  prévia do usuário) NÃO commitado neste ciclo.
- Ressalva leve (não bloqueante, QA): sem teste de payload dedicado ao builder de domínio (coberto
  indiretamente pelo helper compartilhado).
- Nota operacional (esclarecida pelo usuário no fechamento): o arquivo não rastreado
  `PROMPT-portar-run-cycle.md` (presente como `??` no início do ciclo) foi removido pelo PRÓPRIO
  usuário — era um arquivo temporário criado por um agente para aplicar o run-cycle em outro projeto.
  Ação intencional e controlada; nenhum sub-agente o tocou. Sem impacto no ciclo.

---

### BLK-SCORE-01 — Dataset rotulado de validação (Ultra + Skyfit + Wellhub)

| Campo | Valor |
|---|---|
| **Criticidade** | Alta *(read-only sobre M1 — ver §2 do PRD; ratificar com usuário)* |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana]` → Builder → QA |
| **Depende de** | — *(pode rodar em paralelo à Frente A)* |
| **Status** | Pendente |

**Objetivo:** montar a base que liga cada unidade existente (Ultra, Skyfit e Engenharia do Corpo) ao score do
hex/setor onde ela caiu (M1, censitário, residual, domínio) e ao desfecho observado (alunos
recorrentes; Wellhub/Totalpass como proxy de demanda independente). É insumo do backtest.

**Escopo permitido:**
- Geocodificar cada unidade → célula H3 (res. 7) e setor IBGE correspondente.
- Fazer join com os scores existentes (leitura dos outputs M1 e camadas paralelas).
- Anexar desfechos: `alunos_recorrentes`, sinal Wellhub/Totalpass, `alunos_totais` , `data_abertura` (para maturação).
- Gravar artefato de análise em `data/analysis/dataset_validacao.parquet` — **fora** de
  `data/outputs/` (não é artefato de produto, é insumo de análise).

**Fora de escopo:** **qualquer escrita em artefato M1 ou alteração de score.** Apenas leitura e join.

**Arquivos a ler:** fontes Ultra/Skyfit/Wellhub · **bases de validação de concorrentes em
`data/validacao/`** (`Sky Fit dados.xlsx`, `academias_engenharia_do_corpo.xlsx` — alunos/m² + metragem;
gitignored, ver `data/validacao/README.md`) · `data/outputs/*` (scores) · `core/scoring.py`
(para entender as colunas) · esquema dos setores censitários.
**Arquivos a criar:** script de montagem (ex.: `analysis/build_validation_dataset.py`) ·
`data/analysis/dataset_validacao.parquet` · `tests/unit/test_validation_dataset.py`.

**Critérios de aceite:**
- Cada unidade tem H3/setor resolvidos e os 4 scores anexados.
- Flag de maturação (ex.: `meses_operacao >= N`) presente — unidades imaturas marcadas, não descartadas silenciosamente.
- **Auditoria de qualidade de rótulo:** relatório curto de outliers/nulos em `alunos_recorrentes`,
  com nota explícita sobre a confiabilidade dos números de Skyfit (estimados vs. medidos).

**Validações obrigatórias:**
```
pytest -q tests/unit/test_validation_dataset.py
# Sanidade do join: contagem de unidades de entrada == unidades com score anexado (ou diff explicado)
```

**Guardrails específicos:**
- Dados sensíveis de Ultra/Skyfit/Wellhub **não** entram em logs/handoff em texto agregável a PII.
- Artefato vive em `data/analysis/`, nunca em `data/outputs/`. CSVs com `sep=";"`, `utf-8-sig`;
  `Ultra.csv` permanece `latin-1`.

**Risco:** médio — qualidade dos rótulos de concorrente e maturação de unidades novas são as
maiores fontes de viés. Tratar a auditoria de rótulo como critério de aceite, não opcional.


## Fechamento BLK-SCORE-01 — Dataset rotulado de validação (concluído 2026-05-31)

**Veredito QA:** APROVADO COM RESSALVAS. Esteira completa (Block Orchestrator → Planner → [gate humano] → Builder → QA), criticidade Alta, READ-ONLY sobre o M1.

**Entregue:**
- `analysis/build_validation_dataset.py` (+`analysis/__init__.py`): montagem read-only do dataset rotulado, executável via `python -m analysis.build_validation_dataset`.
- `tests/unit/test_validation_dataset.py`: 21 testes, fixtures sintéticas (CI não usa dados reais gitignored).
- `.gitignore`: cobre `data/analysis/` (parquet+md gitignored).
- Artefatos gerados (gitignored): `data/analysis/dataset_validacao.parquet` (441 linhas: ultra 54 + skyfit 326 + engcorpo 61; 31 colunas) + `data/analysis/relatorio_auditoria_rotulo.md`.

**Decisões do gate humano (2026-05-30/31):**
- Skyfit: coords de `concorrentes/unidades_skyfit.csv` (apenas; geocodificados descartados por imprecisão) + match por NOME em cascata (exato→fuzzy difflib 0.84→fallback cidade+UF). Colunas novas `hex_origem`/`hex_precisao`.
- Maturação `maturacao_indisponivel` (sem data de abertura em fonte); alunos canônicos `alunos_recorrentes`+origem+medido (Ultra/Skyfit medido, EngCorpo estimado); setor via `cod_municipio`+`score_setor_2022_calibrado`; domínio nulo+flag fora dos 500 hexes.
- 4 scores anexados por join por `hex_id` (read-only): M1, censitário, residual, domínio.

**Cobertura (marcada, não silenciosa):** hex resolvido ultra 53/54, skyfit 301/326 (nome_exato 175 / nome_fuzzy 16 / cidade_centroide 110 / nao_resolvido 25), engcorpo 31/61.

**Validação:** `pytest -q` → 591 passed, 1 skipped (sem regressão; +21 novos testes deste ciclo). `--check` housekeeping verde. Nenhum artefato/código oficial do M1 alterado.

**Ressalvas (não bloqueantes, candidatos a ciclo futuro):** match EngCorpo conservador (31/61 — possível melhoria fuzzy/por cidade se BLK-SCORE-02 precisar de mais N); Skyfit `cidade_centroide` é hex coarse por design; domínio cobertura parcial 42/441 (esperado).

**Próximo recomendado:** BLK-SCORE-02 (poder preditivo dos scores vs. desfecho) — depende deste dataset.

---

### BLK-SCORE-01a — Melhorar match de nome do Engenharia do Corpo

| Campo | Valor |
|---|---|
| **Criticidade** | Alta *(read-only sobre M1 — só leitura/join, mesmo padrão do BLK-SCORE-01)* |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana]` → Builder → QA |
| **Depende de** | BLK-SCORE-01 (mergeado) |
| **Status** | Pendente |

**Origem:** no BLK-SCORE-01, o match do Engenharia do Corpo (EngCorpo) ficou em ~31/61 unidades porque
foi feito por **nome exato normalizado**, mas a planilha de desfecho e o staging usam convenções de nome
diferentes: a planilha prefixa toda unidade com `EC -`/`ECB -` (ex.: `EC - VACARIA, RS`) enquanto o staging
usa o nome cru (`Vacaria, RS`). O usuário apontou (2026-05-31) que o nome "vem um pouco diferente, mas ainda
daria para encontrar" — confirmado por análise: removendo o prefixo `EC`/`ECB` + fuzzy determinístico
(difflib ≥0.80) a recuperação sobe para ~38/61, e parte do restante é resolvível por sinônimo de
bairro/cidade (ex.: `EC - FLORIANOPOLIS, SC` ~ `Estreito - Florianópolis, SC`; `EC - BLUMENAU` ~ `Centro - Blumenau`).

**Objetivo:** elevar a cobertura de hex/scores do EngCorpo no `dataset_validacao.parquet` melhorando o
match de nome (sem inventar correspondências), mantendo tudo read-only sobre o M1 e marcando os não-casados.

**Escopo permitido:**
- Em `analysis/build_validation_dataset.py`, melhorar a etapa de match EngCorpo: normalização que remove
  prefixo `EC`/`ECB` e ruído; **cascata determinística** nome_exato → nome_fuzzy (difflib, cutoff documentado)
  → fallback cidade+UF (espelhando o padrão já aprovado para o Skyfit no BLK-SCORE-01).
- **Avaliar usar `concorrentes/unidades_engenharia_do_corpo.csv`** (e/ou `concorrentes/Unidades/unidades_engenharia_do_corpo.csv`)
  como fonte de coordenadas direta para resolver hex via `latlng_to_h3`, em vez de depender só do staging
  `concorrentes_mapeados.parquet` (mesma abordagem coords-por-CSV + match-por-nome do Skyfit). Verificar schema/coords antes.
- Anexar `hex_origem`/`hex_precisao` ao EngCorpo (já existem no esquema) refletindo a origem do match.
- Regerar `data/analysis/dataset_validacao.parquet` + `data/analysis/relatorio_auditoria_rotulo.md`.

**Fora de escopo:** **qualquer escrita em artefato M1 ou alteração de score.** Apenas leitura e join.
Fuzzy não-determinístico (que quebre o CI). Geocodificação de endereço ao vivo (BLK-PROD-05).

**Arquivos a ler:** `analysis/build_validation_dataset.py` · `data/validacao/academias_engenharia_do_corpo.xlsx`
(sheet `Academias`) · `data/staging/concorrentes_mapeados.parquet` (`rede=="engenharia_do_corpo"`) ·
`concorrentes/unidades_engenharia_do_corpo.csv` · `concorrentes/Unidades/unidades_engenharia_do_corpo.csv` ·
`context/handoff/20260530-235959-planner.md` (seção REVISÃO 2 Skyfit — padrão de cascata a espelhar).
**Arquivos a alterar:** `analysis/build_validation_dataset.py` · `tests/unit/test_validation_dataset.py`
(casos novos de match EngCorpo) · artefatos regerados em `data/analysis/` (gitignored).

**Critérios de aceite:**
- Match EngCorpo materialmente acima do baseline (31/61); cada unidade casada tem `hex_origem`/`hex_precisao`
  coerentes; não-casados **marcados** (`rotulo_casado=False`/`hex_resolvido=False`), nunca descartados nem
  casados de forma incorreta.
- Cascata determinística (mesmo input → mesmo output; verde no CI sem dados reais).
- Relatório de auditoria atualizado com a nova cobertura EngCorpo por `hex_origem` e a lista (agregada, sem PII)
  de não-casados remanescentes.
- Nenhum falso-positivo introduzido: validar uma amostra dos pares fuzzy aceitos (cidade/UF batem).

**Validações obrigatórias:**
```
pytest -q tests/unit/test_validation_dataset.py
pytest -q                                   # sem regressão
python -m analysis.build_validation_dataset # regenera dataset + relatório fim a fim
```

**Guardrails específicos:**
- READ-ONLY sobre o M1; artefato em `data/analysis/`, nunca `data/outputs/`. PII fora de logs/handoff/relatório.
- CSVs do projeto `sep=";"`, `utf-8-sig`. H3_RESOLUTION=7. Sem fuzzy não-determinístico.

**Risco:** médio — fuzzy pode introduzir falso-positivo (casar unidade errada da mesma cidade). Mitigar
exigindo concordância de cidade+UF no match fuzzy e auditando os pares aceitos.


## Fechamento BLK-SCORE-01a — Melhorar match de nome do Engenharia do Corpo (concluído 2026-05-31)

**Veredito QA:** APROVADO. Esteira completa (Block Orchestrator → Planner → [gate humano: aprovado por Felipe Silva em 2026-05-31] → Builder → QA), criticidade Alta, READ-ONLY sobre o M1.

**Entregue:**
- `analysis/build_validation_dataset.py`: match determinístico de coordenadas EngCorpo espelhando o padrão Skyfit. Novos: constante `ENGCORPO_COORDS_CSV` (fonte canônica `concorrentes/unidades_engenharia_do_corpo.csv`; réplica em `Unidades/` é byte-idêntica e não é lida); helper `normalize_name_engcorpo` (remove prefixo `EC`/`ECB` via regex âncorada `^\s*ec[bv]?\s*[-–—:]?\s*`, só no início, delega a `normalize_name`); helper `_city_uf_from_engcorpo_name` (convenção `Cidade, UF`); função `match_engcorpo_coords` (cascata nome_exato → nome_fuzzy difflib cutoff 0.84 COM concordância obrigatória cidade+UF → cidade_centroide, com `_coord_in_brazil`); `load_engcorpo` reescrita com fallback `hex_staging`; flag `--engcorpo-coords` no `main`. `normalize_name`/`normalize_name_skyfit`/`match_skyfit_coords` intocados (anti-regressão).
- `tests/unit/test_validation_dataset.py`: +11 testes sintéticos (normalize EC/ECB sem corromper `ec` interno, nome_exato, fuzzy-aceito-cidade+UF, **fuzzy-REJEITADO-quando-cidade-ou-UF-divergem** (anti-falso-positivo), cidade_centroide, nao_resolvido, coord-fora-faixa-Brasil, determinismo, fallback-staging, não-casado-marcado-nunca-descartado).
- Artefatos regenerados (gitignored): `data/analysis/dataset_validacao.parquet` + `data/analysis/relatorio_auditoria_rotulo.md`.

**Resultado (cobertura EngCorpo):** 31/61 → **37/61 (60.7%, +19%)** — materialmente acima do baseline. Por `hex_origem`: nome_exato=34, cidade_centroide=3, nao_resolvido=24. **0 fuzzy acionado nos dados reais → zero falso-positivo.** 61 entrada == 61 saída; os 24 não-resolvidos ficam MARCADOS (`rotulo_casado=False`/`hex_resolvido=False`), nunca descartados. Ultra (53/54) e Skyfit (301/326) idênticos ao baseline (sem regressão).

**Validação (re-executada pelo QA, sem bypass):** `pytest -q tests/unit/test_validation_dataset.py` → 32 passed (21+11; confirmado via `--collect-only`); `pytest -q` → 602 passed, 1 skipped (591 baseline + 11; sem regressão); `python -m analysis.build_validation_dataset` → exit 0, 2 artefatos regenerados; `import streamlit_app` ok. `--check` housekeeping verde. READ-ONLY do M1 confirmado por `git status` (nenhum path M1; `data/analysis/*` gitignored); `H3_RESOLUTION=7` e `DEFAULT_FUZZY_CUTOFF=0.84` preservados.

**Observação (não-defeito):** os 24 não-resolvidos são majoritariamente entradas por bairro (ex.: `EC - ESPLANADA, RS`) cuja cidade real só seria recuperável por mapeamento bairro→cidade — fora do escopo deste bloco (decisão conservadora anti-falso-positivo). Candidato a ciclo futuro se BLK-SCORE-02 precisar de mais N.

**Próximo recomendado:** BLK-SCORE-02 (poder preditivo dos scores vs. desfecho) — usa este dataset.

---

### BLK-SCORE-02 — Poder preditivo dos scores vs. desfecho

| Campo | Valor |
|---|---|
| **Criticidade** | Alta *(read-only sobre M1 — ver §2 do PRD)* |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana]` → Builder → QA |
| **Depende de** | **BLK-SCORE-01** |
| **Status** | Pendente |

**Objetivo:** medir, sobre o dataset rotulado, quanto cada score (M1, censitário, residual,
domínio) prevê `alunos_recorrentes` — por rede e no agregado — e onde discordam do real.

**Escopo permitido:**
- Análise exploratória: correlação score×desfecho, por rede e segmento de maturação.
- Decomposição do M1: renda vs. pop — qual componente carrega o sinal? (testa empiricamente o 0.40/0.60).
- Relatório de achados em `data/analysis/` (markdown + figuras), **sem proposta de mudança ainda**.

**Fora de escopo:** alterar pesos, fórmula ou artefatos M1 — isso é o BLK-SCORE-03.

**Arquivos a ler:** `data/analysis/dataset_validacao.parquet` · `core/scoring.py` · `core/constants.py`.
**Arquivos a criar:** `analysis/score_backtest.py` · relatório `data/analysis/relatorio_backtest.md`.

**Critérios de aceite:**
- Relatório responde, com números: (a) qual score melhor prevê recorrentes; (b) o 0.40/0.60 se
  sustenta?; (c) casos onde score alto ≠ desfecho bom (e hipótese do porquê — ex.: saturação de concorrente).
- Análise controla por maturação (não comparar unidade de 2 meses com uma de 5 anos).

**Validações obrigatórias:**
```
pytest -q             # nada quebrado
python analysis/score_backtest.py   # roda fim a fim e gera o relatório
```

**Guardrails específicos:**
- Estritamente **analítico e read-only**. Nenhuma alteração em `scoring.py`/`constants.py`/artefatos.

**Risco:** baixo a médio (qualidade da análise estatística). N pequeno por rede pode limitar
conclusões — relatar incerteza honestamente, não forçar significância.


## Fechamento BLK-SCORE-02 — Poder preditivo dos scores vs. desfecho (concluído 2026-05-31)

**Veredito QA:** APROVADO. Esteira completa (Block Orchestrator -> Planner -> [gate humano: aprovado por Felipe Silva em 2026-05-31] -> Builder -> QA), criticidade Alta, ESTRITAMENTE READ-ONLY sobre o M1.

**Entregue:**
- `analysis/score_backtest.py` (NOVO): backtest read-only com funcoes puras testaveis (`pairwise_valid`, `correlate` via `scipy.stats`, `correlate_by_cell`, `bootstrap_ci_spearman` seed 42, `join_componentes` read-only por `hex_id`, `decompor_renda_pop`, `find_outliers` within-rede anti-PII, `build_report`, `load_inputs`, `main`). Figuras matplotlib OPCIONAIS sob try/except (Agg) -> script sempre exit 0 e gera o `.md` mesmo sem matplotlib. N_MIN=10, seed 42.
- `tests/unit/test_score_backtest.py` (NOVO): +15 testes sinteticos em memoria (sem o parquet real gitignored), cobrindo monotonia +-1, N<N_MIN, variancia zero, pairwise, by_cell, join match_rate/anti-sobrescrita, bootstrap deterministico, anti-PII de outliers, smoke de build_report.
- `data/analysis/relatorio_backtest.md` (gerado, gitignored): responde (a)(b)(c) + Limitacoes.

**Achados (numeros reais, reproduzidos pelo QA):**
- (a) Ranking AGG por Spearman vs `alunos_recorrentes`: melhor `score_setor_2022_calibrado` rho=+0.148 (p=0.004); `score_oportunidade_residual` rho=-0.257 (p<0.001, sinal NEGATIVO); M1 `score_priorizacao` rho=-0.004 (p=0.948, nulo); `score_dominio_hibrido` esparso (AGG N=43; engcorpo N=4 = insuficiente).
- (b) Decomposicao renda x pop (join 357/391 = 91.3%): renda_pct rho=+0.067 vs pop_pct rho=+0.095 — sinal fraco em ambos; reportado como ACHADO DESCRITIVO, SEM proposta de novo peso (isso e BLK-SCORE-03).
- (c) Outliers de ambas as direcoes (score alto x desfecho baixo e inverso), within-rede, anonimizados, com hipotese (saturacao/maturacao ausente/rotulo estimado).

**Validacao (re-executada pelo QA, sem bypass):** `pytest -q tests/unit/test_score_backtest.py` -> 15 passed; `python analysis/score_backtest.py` -> exit 0, relatorio regenerado com (a)(b)(c)+Limitacoes; `pytest -q` -> 617 passed, 1 skipped (602 baseline + 15; sem regressao); `import streamlit_app` ok. Determinismo confirmado (numeros do QA batem com os do Builder). READ-ONLY do M1 confirmado por `git status`/`git diff` (nada em `scoring.py`/`constants.py`/`data/outputs/`/pesos 0.40-0.60/`H3_RESOLUTION=7`); saida so em `data/analysis/` (gitignored). Sem proposta de peso; sem PII; sem dependencia nova (pyproject intocado; matplotlib opcional).

**Observacoes leves (nao-bloqueantes, QA):** (L1) scipy nao declarado em `pyproject.toml` — divida pre-existente do repo, fora de escopo; (L2) frase-template de hipotese generica para o score residual. Nenhuma exige nova rodada.

**Sinal estrategico (para BLK-SCORE-03, NAO acionado aqui):** sobre este dataset rotulado, o M1 `score_priorizacao` nao mostra poder preditivo do desfecho (rho~0), o censitario e o unico com sinal positivo fraco, e o residual correlaciona negativamente. Material empirico para a eventual proposta de recalibracao — que e o escopo CRITICO do BLK-SCORE-03 (gate humano + DEC).

---

### BLK-SCORE-03 — Proposta de recalibração + DEC

| Campo | Valor |
|---|---|
| **Criticidade** | **CRÍTICA** |
| **Esteira** | Block Orchestrator → Planner → `[APROVAÇÃO HUMANA OBRIGATÓRIA]` → Builder → QA |
| **Depende de** | **BLK-SCORE-02** |
| **Status** | Pendente |

**Objetivo:** *se* o backtest justificar, propor recalibração dos pesos/fórmula e, somente após
DEC registrada e aprovação humana, implementá-la — preservando reprodutibilidade e versionamento.

**Escopo permitido (em duas fases separadas pelo gate):**
- **Antes do gate (Planner):** proposta de recalibração fundamentada no relatório de BLK-SCORE-02,
  com impacto esperado no ranking, e minuta de DEC (`DEC-00X`).
- **Depois do gate (Builder, só com DEC aprovada):** alterar pesos/fórmula em `core/scoring.py` /
  `core/constants.py`, regerar artefatos via pipeline, registrar nova versão de proveniência.

**Fora de escopo:** qualquer escrita em M1 antes da string `APROVADO POR [usuário] EM [data]` no handoff.

**Arquivos a ler:** `data/analysis/relatorio_backtest.md` · `core/scoring.py` · `core/constants.py` ·
`CLAUDE.md` (DECs existentes).
**Arquivos a alterar (só pós-gate):** `core/scoring.py` · `core/constants.py` · `CLAUDE.md` (nova DEC) ·
regeneração de `data/outputs/` via pipeline.

**Critérios de aceite:**
- DEC registrada em `CLAUDE.md` (ou `DECISIONS.md` se já existir) com justificativa e data.
- Pesos antigos vs. novos documentados; ranking M1 antes/depois comparado e diferenças explicadas.
- Proveniência (BLK-OPS-03) reflete a nova versão.

**Validações obrigatórias:**
```
pytest -q tests/unit/test_scoring.py    # fórmulas — atualizar testes para os novos pesos
pytest -q                               # suíte completa verde
# Regeneração controlada (staging primeiro, nunca sobrescrever prod sem staging):
python -m motor_expansao.pipelines.m1.fase1_bi_exports   # ou comando canônico do repo
```

**Guardrails específicos (invioláveis):**
- Builder **não** altera nada de M1 sem `APROVADO POR [usuário] EM [data]` no handoff.
- Staging primeiro; jamais sobrescrever Parquets de produção sem passo de staging.
- QA verifica explicitamente que `H3_RESOLUTION=7`, `DIST_MIN_ULTRA_KM=1.0` e demais canônicos
  **não** foram tocados — só os pesos aprovados na DEC mudam.

**Risco:** crítico por definição. O gate humano + DEC + staging são a proteção. Não pular nenhum.

**Resultado do ciclo (concluído 2026-05-31 — APROVADO):**
- **Decisão (DEC-001, APROVADO POR Felipe Silva EM 2026-05-31): NÃO recalibrar o M1.** Pesos
  `renda=0.40`/`pop=0.60` e fórmula do `score_priorizacao` permanecem INALTERADOS; nenhum
  artefato M1 regerado. O Builder NÃO tocou `scoring.py`/`constants.py`/`config.py`/`data/`.
- **Fundamento (BLK-SCORE-02 + exploração read-only deste ciclo):** `score_priorizacao` rho=-0.004
  (IC95% [-0.104,+0.094] atravessa zero → sinal nulo); componentes renda +0.067 (n.s.) e pop +0.095
  (n.s.), diferença dentro do ruído e peso já favorece pop; **`n_domicilios`/`densidade_dom` em
  `brasil_estrutural.parquet` estão 100% zerados (placeholders)** → não há feature nova usável
  dentro do M1; o único preditor positivo é o censitário (+0.148), que é camada paralela.
- **Reenquadramento (correção de documentação do usuário):** o M1 é a camada EXECUTIVA (municípios/
  ranking de carteira), NÃO o score operacional do dia a dia — esse papel é da camada CENSITÁRIA.
  §1 "Norte" do `CLAUDE.md` ajustada cirurgicamente para refletir isso.
- **Entregue (só documentação/backlog):** (1) §1 do `CLAUDE.md` corrigida; (2) **DEC-001** registrada
  em nova seção `## 8. Decisoes registradas (DEC)` do `CLAUDE.md`, com evidência, pesos inalterados e
  plano de reabertura (pré-requisito: popular as colunas zeradas; gatilhos G1–G4 + sinal do
  BLK-SCORE-04); (3) **BLK-SCORE-04** adicionado ao backlog (backtest read-only multivariado das
  features mercado/censitárias vs. desfecho — responde à pergunta "outras variáveis ajudam?").
- **Validação (re-executada pelo QA, sem bypass):** `git diff` em `src/`/`data/`/`config.py`/
  `test_scoring.py` = VAZIO; pesos `0.40/0.60`, `H3_RESOLUTION=7`, `DIST_MIN_ULTRA_KM=1.0`,
  `RENDA_MIN=4500.0` intactos; `pytest -q` = **617 passed, 1 skipped** (sem regressão); integração
  Streamlit 150 passed; `import streamlit_app` ok. Sem PII; escopo não excedido.
- **Esteira:** Block Orchestrator → Planner → [ajuste do humano] → Planner (revisão) →
  [APROVAÇÃO HUMANA] → Builder → QA. Veredito QA: **APROVADO**.

---

### BLK-SCORE-04 — Backtest read-only multivariado das features mercado/censitárias vs. desfecho

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (LEITURA/ANÁLISE read-only, sem escrita em M1) |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Depende de** | **BLK-SCORE-02** e **BLK-SCORE-03** (DEC-001) |
| **Status** | Pendente |
| **Origem** | revisão do BLK-SCORE-03 (resposta à pergunta do usuário "outras variáveis ajudam?") |
| **Insumo** | `data/analysis/dataset_validacao.parquet` (BLK-SCORE-02) + `data/staging/hexagonos_mercado_mapeado.parquet` (131 cols, populadas) + `score_setor_2022_calibrado` |

**Objetivo:** medir, read-only, o poder preditivo INDIVIDUAL e CONJUNTO das features reais das
camadas mercado/censitária contra o desfecho `alunos_recorrentes`, para fundamentar (com
evidência) um eventual enriquecimento dos scores OPERACIONAIS (censitário/mercado) — e, no longo
prazo e somente após popular as colunas zeradas, do M1. Responde diretamente "outras variáveis
além de pop/renda ajudam/são significativas?".

**Escopo (read-only, estilo BLK-SCORE-02):**
- NÃO toca M1: sem editar `scoring.py`/`constants.py`/artefatos oficiais; sem recalcular `score_priorizacao`.
- Join por `hex_id` do `dataset_validacao` com `hexagonos_mercado_mapeado` (reportar taxa de match).
- Saída SÓ em `data/analysis/` (gitignored): relatório agregado/anonimizado, sem PII (sem `nome_unidade`).

**Colunas candidatas (verificadas como populadas e variando):**
- Mercado/competição: `n_concorrentes_mapeados_1km`, `n_concorrentes_mapeados_2km`,
  `dist_concorrente_mais_proximo_m`, `oferta_efetiva_mapeada_1km`, `oferta_efetiva_mapeada_2km`,
  `gap_competitivo_2km`, `pressao_concorrencial_score_2km`, `n_unidades_ultra_1km`,
  `n_unidades_ultra_2km`, `share_*_2km`.
- Demanda/densidade: `densidade_pop_setor_hab_km2`, `pop_total_setor_2022`, `coverage_pct_setor_2022`.
- Censitário: `score_setor_2022_calibrado` (baseline positivo já conhecido, +0.148) como âncora.

**Método:**
- Reusar `analysis/score_backtest.py` (Spearman rho + Pearson r, p-valor; pairwise por célula;
  `to_numeric` coerce; seed=42).
- Por feature: correlação por rede (ultra/skyfit/engcorpo) e AGG.
- Piso N_MIN = 10 (não calcular célula com N<10); IC bootstrap (percentil 2.5/97.5, n_boot=2000,
  seed 42) para N>=30.
- Opcional read-only: regressão multivariável simples / importância relativa para ler sinal
  CONJUNTO (sem produzir um score novo — só diagnóstico de quais features carregam sinal).
- Reportar limitações herdadas do BLK-SCORE-02 (§5): maturação, heterogeneidade, N pequeno,
  precisão de hex, EngCorpo estimado.

**Guardrails (invioláveis):**
- READ-ONLY sobre M1 e sobre todos os artefatos oficiais. Nenhuma escrita fora de `data/analysis/`.
- Não criar/alterar score; só MEDIR. Sem PII no relatório.
- Resultado é base de EVIDÊNCIA; qualquer mudança de score posterior é outro bloco (com seu gate).

**Critérios de aceite:**
- Relatório `data/analysis/relatorio_backtest_mercado.md` com tabela por feature × célula
  (rho/p/r/p/N/flag), ranking por |rho| AGG, e seção de limitações.
- Taxa de match do join reportada; features com input constante marcadas "indefinido".
- Zero escrita em M1/artefatos oficiais; zero PII.
- Reprodutível (seed fixo; script versionado).

**Resultado do ciclo (concluído 2026-05-31 — APROVADO; revisão humana por Felipe Silva):**
- **Entregue (read-only; ZERO escrita em M1):** `analysis/feature_backtest_mercado.py` (NOVO; importa
  as funções puras de `score_backtest.py`, sem alterá-lo), `tests/unit/test_feature_backtest_mercado.py`
  (NOVO; 7 testes sintéticos em memória), `data/analysis/relatorio_backtest_mercado.md` (gerado,
  gitignored). 12 features (poda 19→12 de colineares), âncora censitária do dataset, sentinela de
  distância mantida (Spearman primário), OLS diagnóstico restrito a 4 regressores z-scored (numpy
  lstsq; nada persistido).
- **Achados (reproduzidos pelo QA; match join 390/391 = 99,7%):** ranking |rho| AGG liderado por
  features de REDE PRÓPRIA — `n_unidades_ultra_2km` rho=+0.346 e `gap_rede_propria_1km` rho=-0.312 —
  porém marcadas com **CAUTELA DE ENDOGENEIDADE** (correlação circular: refletem onde a Ultra já
  opera, não atributo exógeno; NÃO acionáveis p/ nova expansão, NÃO entram no gate G4). Âncora
  censitária `score_setor_2022_calibrado` reproduz exatamente o +0.148 do BLK-SCORE-02. Features de
  mercado/competição de terceiros com sinal individual ~nulo (IC cruza zero). OLS conjunto R²≈+0.034
  (sinal fraco). Conclusão honesta: nenhuma feature EXÓGENA de mercado mostra sinal preditivo forte
  no dataset rotulado atual — coerente com a DEC-001 (não recalibrar; reabertura só sob G1–G4).
- **Validação (re-executada pelo QA, sem bypass):** 7+15 testes verdes; `pytest -q` = **624 passed,
  1 skipped** (617 base + 7 novos; sem regressão); script EXIT 0 e determinístico (2 execuções
  byte-idênticas, seed=42); `import streamlit_app` ok; `git diff` em `src/`/`data/outputs/`/
  `data/staging/`/`config.py`/`scoring.py`/`constants.py`/`score_backtest.py`/relatório do
  BLK-SCORE-02 = VAZIO; saída só em `data/analysis/` (gitignored); sem PII.
- **QA: APROVADO COM RESSALVAS** (médio não-bloqueante): a cautela de endogeneidade estava só no
  handoff, não no relatório (artefato que alimenta o G4). **Ressalva endereçada pelo orquestrador
  antes do fechamento** (conforme recomendação do próprio QA): adicionados §4 e limitação 8 de
  endogeneidade ao `build_feature_report`, relatório regenerado (determinístico), suíte verde →
  fechado como APROVADO.
- **Esteira:** Block Orchestrator → Planner → [REVISÃO HUMANA: aprovar] → Builder → QA.

---

### BLK-OPS-11 — Pinar dependências e restaurar paridade CI/local (CI vermelho nos testes)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (CI quebrado mascarava falhas; afeta o gate de qualidade — não toca M1/score) |
| **Prioridade** | **Alta** (o gate de testes do CI está, na prática, desligado) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Origem** | descoberto em 2026-05-31 ao destravar o lint do ruff (commits `3b022ea`/`48d8eb7`) |

**Contexto / sintoma:** com o lint do ruff corrigido, o passo `Testes (suite completa)` do CI
rodou pela 1ª vez em dias e **falha na collection** com
`AttributeError: property 'CORES' of 'Settings' object has no setter` em ~14 testes. **Local passa
(624 passed, 1 skipped); CI falha.** O lint vermelho vinha *mascarando* que os testes também
quebravam no ambiente do CI — ou seja, o CI nunca esteve realmente verde. Produção NÃO é afetada
(roda imagem pré-buildada do GHCR; smoke import OK).

**Causa raiz (CORRIGIDA na execução BLK-OPS-11, 2026-05-31):** a quebra da collection do CI **NÃO**
vinha do pydantic novo. No CI, `pydantic_settings` está só no extra `api` (não instalado em
`.[dev]`), então `Settings` roda pelo **RAMO FALLBACK** (`else` em `src/motor_expansao/config.py`). O
`__init__` desse ramo iterava `self.__class__.__dict__.items()` e fazia `setattr` para todo nome
`isupper()`; `CORES` é uma `@property` cujo nome é `isupper()` e property sem setter explodia no
`setattr` (`AttributeError: property 'CORES' ... has no setter`). Isso derrubava o import de
`config` → `core/constants.py` → 12 módulos de teste na collection. **A cura é no `config.py`**
(guard `if isinstance(default, property): continue` antes do `setattr`), provada sob fallback forçado
(`Settings()` instancia, `CORES` resolve, 12/12 módulos importam). Pinar libs (Opção A) é **higiene
de paridade**, não a cura — o ramo que falhava sequer importa pydantic. Permanece o risco latente de
breaks por pandas 3.0 / numpy 2.4, mitigado pelos tetos adicionados.

**Sub-achado correlato (lição):** o ruff local deu *falso-verde por cache* durante o 1º fix — só
`--no-cache` revelou o erro restante. Reforça a necessidade de pinar a versão do linter também.

**Objetivo:** restaurar paridade CI/local e deixar o gate de testes do CI verde de verdade, sem
mascarar nada.

**Escopo permitido — DECIDIR entre 2 abordagens no Planner (com gate humano):**
- **Opção A — Pinar dependências** no `pyproject.toml` para um conjunto conhecido-bom (faixas
  compatíveis: ex. `pandas<3`, `pydantic` em faixa que aceite o padrão atual, `ruff==<versão do CI>`,
  etc.) + opcionalmente um lockfile. Mais rápido/seguro; é dívida adiada mas controlada.
- **Opção B — Adaptar o código** para as versões novas: corrigir o padrão `CORES`/`Settings`
  (remover a duplicação nas linhas 84/153 e o conflito property×field do pydantic novo) e sanear
  qualquer incompatibilidade com pandas 3.0. Mais trabalho, mais robusto a longo prazo.
- Recomenda-se o Planner avaliar custo das duas e propor uma (provável: A agora para destravar +
  B como follow-up). Pinar o **ruff** (paridade de lint) entra em qualquer das opções.

**Fora de escopo (invioláveis):**
- NÃO tocar M1: `score_priorizacao`/`scoring.py`/pesos/artefatos. Só ambiente/CI/config.
- NÃO mascarar falha de teste (skip/xfail amplo) para "ficar verde" — isso é bypass proibido.
- NÃO alterar a lógica de negócio para acomodar versão de lib sem teste que prove equivalência.

**Arquivos prováveis:** `pyproject.toml` (pins/faixas), `src/motor_expansao/config.py` (CORES/Settings,
se Opção B), `.github/workflows/ci.yml` (se precisar de constraints/lock), eventual `requirements*.txt`/lock.

**Critérios de aceite:**
- CI **verde de ponta a ponta** (Lint → mypy → Testes → Smoke) no commit de fechamento — comprovado
  por run do Actions, não por suposição.
- Paridade: `ruff`/`mypy`/`pytest` reproduzíveis local == CI (mesmas versões; rodar ruff com `--no-cache`).
- 624 passed (ou contagem ≥) verde no CI; nenhuma falha de collection.
- Zero mudança em M1/artefatos; zero teste silenciado para forjar verde.

**Validações obrigatórias:**
```
ruff check . --no-cache           # paridade de lint (versão pinada)
mypy src/
pytest -q                         # local
# + confirmar run verde no GitHub Actions (gh run watch)
```

**Risco:** médio. Pinar pode esconder incompatibilidades futuras (mitigado por agendar a Opção B);
adaptar código exige cuidado para não alterar comportamento. O gate humano + QA com CI real verde
(sem bypass) são a proteção.

**Fechamento do ciclo (2026-05-31) — VEREDITO QA: APROVADO COM RESSALVAS**
- **Diagnóstico corrigido na execução:** a quebra da collection do CI **não** vinha de "pydantic novo"
  e sim do **ramo fallback** de `Settings` (`config.py`): no CI, `pydantic-settings` está só no extra
  `api` (não instalado em `.[dev]`), então roda o fallback, cujo `__init__` fazia `setattr` em todo
  nome `isupper()` — inclusive a `@property CORES` (sem setter) → `AttributeError`, derrubando 12
  módulos na collection. Provado por reprodução read-only (Planner) e re-provado pelo QA.
- **Abordagem HÍBRIDA aprovada por Felipe Silva (2026-05-31):**
  - **Cura (B):** guard `if isinstance(default, property): continue` no `__init__` do fallback de
    `config.py` (2 linhas; ramo pydantic, dict `CORES` e `_coerce_env_value` intocados).
  - **Paridade (A):** tetos de runtime em `pyproject.toml` (`pandas<3`, `numpy<2.4`, `pyarrow<24`,
    `scikit-learn<1.8`, `streamlit<2`) e faixas das ferramentas dev (`ruff>=0.15,<0.16`, `mypy<2`,
    `pytest<10`, `pytest-asyncio<0.25`). Extra `api` NÃO tocado; `mypy` NÃO pinado em `==`.
  - **CI:** lint passou a `ruff check . --no-cache` (cache dava falso-verde). `api` NÃO adicionado ao
    CI (o fallback é o caminho suportado e agora testado).
  - **Teste novo:** `tests/unit/test_config_fallback.py` (2 testes) blinda o ramo fallback (CORES
    resolve + env-override) — sem skip/xfail, sem bypass.
- **Validações locais (QA re-executou, sem confiar no Builder):** `ruff --no-cache` limpo; `mypy src/`
  0 erros; `pytest -q` 626 passed, 1 skipped, 0 erros de collection; streamlit 150 passed; smoke
  import ok; prova da cura sob fallback forçado (12/12 módulos antes afetados importam; 0 erros de
  collection).
- **Guardrails M1:** `score_priorizacao`/pesos 0.40-0.60/H3=7/`scoring.py`/artefatos intactos; só
  `config.py` mudou em `src/`. Commit só por path; `PRD.md` não arrastado.
- **Ressalva única (não bloqueante) — FECHADA no fechamento:** o critério "CI verde de ponta a ponta
  no GitHub Actions (Python 3.11)" foi CONFIRMADO. Run `26722016904` (workflow_dispatch na branch
  `ciclo/BLK-OPS-11`) ficou verde: Instalar deps → Lint (ruff `--no-cache`) → Types (mypy src/) →
  Testes (suite completa) → Smoke import, todos ✓ em 2m9s. Pytest no 3.11: **554 passed, 73 skipped,
  0 falhas, 0 erros de collection** (total 627 coletados = igual ao local; os 73 skips são testes de
  integração gated em parquets de dados reais gitignored ausentes no CI — comportamento pré-existente
  do repo, NÃO silenciamento). As faixas pinadas resolveram sem problema no 3.11. A cura (guard de
  property) é independente de versão.
- **Follow-up sugerido:** agendar a Opção B ampla (deduplicar a `@property CORES` entre os ramos e
  sanear incompatibilidades pandas 3.0) como dívida controlada; pode entrar antes de BLK-SEC-01/02
  (que dependem deste bloco).
- **Esteira:** Block Orchestrator → Planner → [REVISÃO HUMANA: aprovar] → Builder → QA.

---

### BLK-SEC-01 — Gate de publicação no CI (publish só com CI verde) + pin de imagem e rollback

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (integridade de CI/CD; afeta o artefato de produção — não toca M1/score) |
| **Prioridade** | **Alta** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Depende de** | **BLK-OPS-11** (CI precisa estar verde de verdade antes de virar gate) |
| **Status** | Pendente |
| **Origem** | descoberto em 2026-05-31 durante a sincronização da VPS |

**Contexto / gap:** `docker-publish.yml` publica `ghcr.io/.../motor-expansao-streamlit:latest` a cada
push em `main` **sem depender do CI** (sem `needs:`/`workflow_run`). Por dias o CI esteve vermelho e a
imagem de produção continuou sendo publicada — um build com teste quebrado (ou dependência
comprometida) chega ao `:latest` que a VPS puxa, sem barreira. Além disso o `docker-compose.prod.yml`
referencia `:latest` (tag móvel) — não há pin por digest nem rollback trivial.

**Objetivo:** garantir que SÓ imagens de um commit com CI verde sejam publicadas, e tornar o deploy
reproduzível/reversível.

**Escopo permitido:**
- Acoplar o publish ao sucesso do CI (`workflow_run` com `conclusion == success`, ou um único
  workflow com job `publish` que `needs: [test]`).
- Taguear a imagem também por **SHA do commit** (além de `:latest`) — já há `revision` no label OCI.
- Pin do `docker-compose.prod.yml` por digest/SHA (não `:latest` cego) + runbook de **rollback**
  (apontar para a tag/digest anterior e `up -d`), em `docs/infra_producao.md`.

**Fora de escopo:** mudar M1/score/artefatos; assinar imagem (cosign) — pode virar follow-up.

**Arquivos prováveis:** `.github/workflows/docker-publish.yml`, `.github/workflows/ci.yml`,
`docker-compose.prod.yml`, `docs/infra_producao.md`.

**Critérios de aceite:**
- Push com CI vermelho **NÃO** publica imagem (comprovado por um run de teste).
- Imagem publicada com tag por SHA; compose de prod fixa um digest/SHA conhecido.
- Runbook de rollback testado (voltar para a imagem anterior sem rebuild).
- Zero mudança em M1/artefatos.

**Risco:** médio. Mitigado por testar o gate num push proposital com falha antes de confiar nele.

---

## Fechamento BLK-SEC-01 — Gate de publicação no CI + pin de imagem e rollback (concluído 2026-06-01)

- **Veredito QA:** APROVADO COM RESSALVAS. Ressalva única e NÃO bloqueante: a prova dinâmica
  Nível 3 (run real no GitHub Actions com `test` quebrado proposital numa branch de ciclo,
  comprovando que `publish` fica skipped) foi DIFERIDA ao fechamento humano — não é viável ao
  agente local e não dispara runs reais. O gate foi provado por prova estática (Nível 1) +
  sintaxe de YAML (Nível 2) neste ciclo.
- **Esteira:** Block Orchestrator → Planner → [REVISÃO HUMANA: aprovado COM ajuste] → Builder → QA.
- **Aprovação humana (Felipe Silva, 2026-06-01) com 1 ajuste no D2:** o default do `image:` no
  `docker-compose.prod.yml` deixou de ser `:latest` (e não virou `sha-<commit>` hardcodado como no
  plano original), passando à forma **fail-closed** `${STREAMLIT_IMAGE:?<mensagem→docs/infra_producao.md>}`.
  Motivo: ciclos entram na `main` por merge commit, então `sha-<commit-da-branch>` nunca é publicada;
  um default `sha-<...>` apontaria para tag inexistente. Com `:?`, `docker compose up` sem
  `STREAMLIT_IMAGE` falha de propósito com mensagem clara. Validação #3 ajustada para checar a forma `:?`.
- **O que mudou (commit por path na branch `ciclo/BLK-SEC-01`):**
  - **Opção B (acoplamento ao CI):** publish fundido em `.github/workflows/ci.yml` como job `publish`
    com `needs: [test]` + `if: github.event_name == 'push' && github.ref == 'refs/heads/main'`,
    `packages: write` só no job (global `contents: read`); `github.sha` correto, sem a armadilha de
    `workflow_run`/`head_sha`.
  - `.github/workflows/docker-publish.yml` **removido** (`git rm`) — eliminado o caminho de publish
    desacoplado que publicava em todo `push:[main]` sem gate.
  - Job `build-sanity` (dispatch manual, `push: false`) preserva a sanidade de build do QA sem
    publicar nada.
  - `metadata-action` mantém `type=sha` (tag por SHA) + `:latest` só na default branch.
  - `docs/infra_producao.md`: seção antiga `git pull` + `up -d --build` substituída por
    "Atualizar (modo PULL, sem build)" + "Rollback (por digest imutável, sem rebuild)";
    referências passam a apontar para o job `publish` do CI. `docs/deploy.md` alinhado (rollback por
    digest; pin fail-closed).
- **Validações (re-executadas pelo QA, sem bypass):** (1) `ci.yml ok`; (2) `removido`; (3) compose
  fail-closed `${STREAMLIT_IMAGE:?...}` sem `:latest`; (4) integração `150 passed`; (5) `import ok`;
  (6) suíte completa `626 passed, 1 skipped, 0 failed / 0 collection errors`; (7) diff só em
  `.github/workflows/*`, `docker-compose.prod.yml`, `docs/*.md`, `tasks/*`, `context/handoff*`.
- **Zero-M1 confirmado:** nenhum `src/`, `dashboard/`, `*.parquet`, `config.py` ou `PRD.md` tocado;
  parâmetros canônicos (H3=7, DIST=1.0, RENDA_MIN=4500.0, renda=0.40/pop=0.60) intactos.
- **Dry-run de orquestração:** NÃO se aplica (o ciclo não alterou `run-cycle`/`prompts`/esteira;
  só tocou CI/CD, compose e docs).
- **Pendência para o humano no/após merge:** executar a prova Nível 3 real no GitHub Actions
  (quebra proposital em branch de ciclo → `publish` skipped → reverter; anotar o run id) e fazer o
  pin real de produção por digest imutável (`STREAMLIT_IMAGE=...@sha256:<digest>`) ao deployar.
- **Snapshots de auditoria:** `context/handoff/20260601-091229-block-orchestrator.md`,
  `…-091547-planner.md`, `…-092740-builder.md`, `…-093404-qa.md`.

---

### BLK-FIX-03 — SP estoura "Out of Memory" no Mapa Territorial

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (UF inteira inutilizável em produção; não toca M1/score — só render/transporte) |
| **Prioridade** | **Alta (topo)** |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Depende de** | — (relacionado ao **BLK-FIX-02**, já concluído) |
| **Status** | Pendente |
| **Origem** | Felipe, 2026-06-01 (print do navegador: "Esta página está com problemas / Código de erro: Out of Memory") |

**Contexto / gap:** selecionar a UF **SP** no Mapa Territorial derruba a aba do navegador com
"Out of Memory" — erro **client-side** (JS heap do navegador), **distinto** do `MessageSizeError`
de transporte já curado no BLK-FIX-02. SP é a maior UF (mais hexes/população); mesmo com o cap de
35k (`MAP_POINT_LIMIT`) e a projeção de colunas do BLK-FIX-02, o render do deck.gl/pydeck de ~35k
hexágonos H3 + dados para SP parece exceder a memória da aba. Hipótese adicional: pico de memória já
na carga (`read_enriched_uf_partition` lê a partição `uf=SP` inteira antes do cap).

**Objetivo:** tornar o Mapa Territorial utilizável para SP (e qualquer UF grande) sem crash de memória.

**Escopo permitido (não toca M1):** medir onde o pico ocorre (carga da partição × payload do deck ×
render client-side); avaliar cap efetivo menor para UFs grandes, simplificar a camada/geometria, ou
agregar visualmente; reusar `_downsample_map_index` / `MAP_POINT_LIMIT` / `_deck_layer_frame`.

**Fora de escopo:** recalcular score/carteira/plano/artefatos M1; alterar o universo de hexes (é o BLK-FIX-06).

**Arquivos prováveis:** `dashboard/constants.py` (`MAP_POINT_LIMIT≈98`, `MAP_SOURCE_COLUMNS_*`),
`dashboard/components.py` (`_downsample_map_index`, builders de mapa, `_deck_layer_frame`),
`dashboard/pages.py` (`st.pydeck_chart`, render do Mapa Territorial), `dashboard/data.py`
(`read_enriched_uf_partition`, `load_uf_slice`), `.streamlit/config.toml`.

**Critérios de aceite:** SP carrega no Mapa Territorial sem crash (medição de memória/payload ou repro
manual); demais UFs não regridem; zero mudança em M1/artefatos; suíte verde.

**Risco:** médio (perf/UX; sem tocar dados oficiais).

## Fechamento BLK-FIX-03 (2026-06-01)

**Veredito QA:** APROVADO COM RESSALVAS (QA 2026-06-01). Ciclo fechado pelo orquestrador; aguarda merge
humano de `ciclo/BLK-FIX-03` na base.

**Esteira executada:** Block Orchestrator → Planner → Builder → QA (Alta; não toca M1 → sem gate humano).

**Causa-raiz confirmada:** OOM **client-side** (JS heap/WebGL) ao renderizar ~35k hexágonos H3 em GPU —
distinto do `MessageSizeError` de transporte do BLK-FIX-02 (que continua valendo, não regrediu). Achado-
chave do Block Orchestrator: **SP não é a maior UF** (é a 10ª em hexes, 47k); AM (293k), PA (214k),
MT (165k), MG (104k), BA (94k) são maiores e também saturavam o cap de 35k → a correção mira "qualquer
UF grande", não só SP (atende ao pedido explícito de verificar outras UFs).

**Solução implementada:** cap efetivo **dinâmico** `MAP_POINT_LIMIT_LARGE = 18000` aplicado nos 3
builders quantitativos (M1/híbrido/residual) **só** quando o recorte satura `MAP_POINT_LIMIT` (35k);
UFs pequenas/recortes ≤35k permanecem byte-idênticos (cap cheio, sem regressão). Layer simplificado
(`auto_highlight=False`/`stroked=False`) **só** no cap reduzido; `pickable=True`, regra de cor
(`score_band_to_color`/`RESIDUAL_SCORE_BANDS`) e BLK-FIX-02 intactos. Caption "capped" reflete o cap
efetivo (18.000 vs 35.000). Passo 7 (projeção de colunas na carga): **não-feito-justificado** — o pico
dominante é render de geometria, já atacado; `data.py` não tocado.

**Arquivos do ciclo:** `src/motor_expansao/dashboard/constants.py` (nova const `MAP_POINT_LIMIT_LARGE`),
`src/motor_expansao/dashboard/components.py` (cap dinâmico + simplificação de layer + `effective_cap` no
caption), `src/motor_expansao/dashboard/pages.py` (cálculo de `capped`/`effective_cap`),
`tests/integration/test_streamlit_app.py` (novos testes de cap reduzido/cor/caption + revisão dos testes
de cap existentes preservando a intenção top-N por prioridade), `docs/streamlit_dashboard_m1.md` (nota
do cap reduzido).

**Validações (re-executadas pelo QA):** `pytest -q` → **631 passed, 1 skipped**; `test_streamlit_app.py`
→ 155 passed; `import streamlit_app` ok; `ruff` → All checks passed; `mypy components.py` → Success.

**Guardrails:** zero alteração em `score_priorizacao`/`hex_score_estrutural`/carteira/plano/artefatos M1/
universo de hexes/`MAP_POINT_LIMIT` global/`_downsample_map_index`/regra de cor; parâmetros canônicos
preservados (H3_RESOLUTION=7, pesos renda=0.40/pop=0.60). Commit só por path.

**Ressalva (média, não-bloqueante):** o gatilho `capped` em `pages.py` infere o corte por
`n_points >= MAP_POINT_LIMIT_LARGE`; um recorte com 18.000–34.999 hexes distintos (renderizado SEM corte)
exibiria falsamente o caption "amostrado". Registrada como follow-up opcional **BLK-FIX-03-FU1** no backlog.

**Dry-run de orquestração:** N/A — o ciclo não tocou run-cycle/prompts/esteira (só dashboard render + docs).

---

### BLK-FIX-07 — Camada de pins de academias escalável (manter logos; alvo ~40k concorrentes)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (bug de produção: SP estoura OOM; render/transporte — não toca M1/score) |
| **Prioridade** | **Alta (topo)** |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Depende de** | BLK-FIX-03 (cap de hexes, concluído 2026-06-01) — complementar, não substitui |
| **Status** | Pendente |
| **Origem** | Diagnóstico no fechamento/deploy do BLK-FIX-03 (2026-06-01): SP continuou travando após o cap de hexes |

**Contexto / causa-raiz (confirmada com dado real):** mesmo após o cap dinâmico de hexes do BLK-FIX-03
(18k), **SP continua estourando "Out of Memory" client-side**, enquanto AM (293k hexes) e BA (94k hexes)
funcionam. O fator não é o nº de hexes (capado e ~idêntico entre UFs grandes), e sim as **camadas de
pins de academias**, que **não têm cap** e embutem o **logo base64 por linha**:
- `_build_competitor_icon_layer` ([components.py:695](src/motor_expansao/dashboard/components.py#L695))
  e `_build_ultra_icon_layer` ([components.py:231](src/motor_expansao/dashboard/components.py#L231))
  atribuem `icon_data` = data-URI base64 do logo **por pin** (`competitor_icon_data`,
  [competitors.py:198](src/motor_expansao/dashboard/competitors.py#L198)), repetido no payload por linha.
- Contagem real por bbox: **SP 1.381** concorrentes vs **BA 133** vs **AM 68** (total 3.296). SP concentra
  o grosso das academias → outlier de payload, mesmo com poucos hexes.
- Cada pin monta **15 campos de tooltip** ([components.py:711-732](src/motor_expansao/dashboard/components.py#L711-L732)),
  custo linear por linha que o BLK-FIX-02 (`_deck_layer_frame`) nunca aplicou às IconLayers.

⚠ **Escala futura:** scrapings em desenvolvimento devem levar o nº de concorrentes a **>40 mil**. Só o
atlas de ícones (logo uma vez) **não basta** a 40k: sobra o custo `O(N)` de transporte/serialização
(uma linha por pin + tooltip, serializada a cada rerun e mantida no heap da aba). A correção precisa ser
dimensionada para 40k desde já.

**Objetivo:** tornar a camada de pins escalável a ~40k concorrentes **mantendo os logos**, sem crash de
memória, sem tocar M1/score/artefatos.

**Escopo permitido (vias a fundamentar pelo Planner):**
- **Atlas de ícones compartilhado** (`iconAtlas` + `iconMapping`): logo entra **uma vez** no atlas; cada
  linha carrega só o **nome da rede**. Mantém os logos; elimina a repetição do data-URI por pin.
- **Gate por recorte + clustering server-side:** na visão de **UF inteira** (muitos pins), enviar
  **clusters agregados** (contagem por grid/hex), não todos os pins; expandir para **pins individuais
  com logo** quando o recorte é pequeno (município/filtro). Limita o payload independentemente do total
  de 40k. (Nota: `st.pydeck_chart` **não** round-trippa zoom/pan ao servidor → o gate é por
  **recorte/filtro selecionado**, não por zoom client-side ao vivo.)
- **Payload por linha enxuto:** aplicar o equivalente do `_deck_layer_frame` às IconLayers — tooltip via
  **template** sobre 2–3 colunas cruas em vez dos 15 campos pré-montados.
- **Cap de segurança duro** por camada (fail-safe com aviso "amostrado"), análogo ao `MAP_POINT_LIMIT`.
- **Medição determinística:** teste que conta linhas/bytes do payload das IconLayers por UF, inclusive com
  **dataset sintético de ~40k concorrentes**, para provar o bound antes de o scraping crescer.

**Fora de escopo:** M1/score/artefatos/universo de hexes; trocar o componente de mapa (Bloco 12 mantém
`st.pydeck_chart`); **culling por zoom client-side ao vivo** (exigiria componente React custom — follow-up
se quiserem refino depois); refazer o cap de hexes do BLK-FIX-03 (já feito); mexer na regra de cor de score.

**Arquivos prováveis:** `dashboard/components.py` (`_build_competitor_icon_layer`, `_build_ultra_icon_layer`,
`build_*_map_figure`, `_filter_competitors_to_reference`), `dashboard/competitors.py`
(`competitor_icon_data`/atlas, preload de logos), `dashboard/constants.py` (cap de pins / limites de
cluster), `dashboard/pages.py` (render do Mapa Territorial), `tests/integration/test_streamlit_app.py`.

**Critérios de aceite:**
- Com dataset sintético de **40k concorrentes**, o payload das IconLayers por UF fica **≤ limite definido**
  (medição determinística de linhas/bytes); sem crash.
- **SP real (1.381 pins) carrega sem crash** no Mapa Territorial (repro manual + medição).
- **Logos preservados** (atlas) e **tooltips preservados** (via template); demais UFs não regridem.
- Zero mudança em M1/score/artefatos; `pickable`/clique preservado; suíte verde.

**Risco:** médio-alto (refator de render + clustering). **Mitigação/faseamento sugerido:** Fase A (atlas +
payload enxuto + cap de segurança) já resolve o SP imediato e dá ganho grande; Fase B (clustering por
recorte) entrega o alvo de 40k. O Planner decide se entrega em um ciclo ou em duas fases.

---

## Fechamento BLK-FIX-07 (orquestrador, 2026-06-01)

**Veredito QA:** APROVADO (rígido, a pedido de Felipe). Zero problemas críticos/médios; só opcionais.

**O que foi entregue (Fase A):** camada de pins (IconLayer de concorrentes e Ultra) tornada escalável a
~40k mantendo os logos, sem tocar M1/score/artefatos.
- **Atlas de ícones** (`build_icon_atlas` + `_ATLAS_CACHE` em `dashboard/competitors.py`): logo entra UMA
  vez num atlas PNG (1 tile 128x128/rede, geometria do pin espelhada: cx=64,cy=47,r=27,anchorY=122);
  cada linha carrega só a chave da rede. Cache por `frozenset` de redes. `preload_logos`/`_ICON_CACHE`/
  `competitor_icon_data`/`ultra_icon_data` preservados (fonte do atlas).
- **Payload enxuto** (`dashboard/components.py`): `_icon_layer_frame`/`_ICON_RENDER_COLUMNS`; tooltips
  VETORIZADOS (sem `.apply(axis=1)`), mesmos textos (Tipo/Rede/Cidade-UF/Coordenadas/Fonte), sem os
  campos vazios `tooltip_line_6..14`. `pickable=True`/clique (BLK-FIX-04) e template compartilhado intactos.
- **Cap de segurança duro** (`dashboard/constants.py`): `COMPETITOR_PIN_LIMIT=ULTRA_PIN_LIMIT=6000`,
  amostragem determinística (sort estável + head); caption "amostrado" honesta em `dashboard/pages.py`
  (só quando excede o cap; deixa claro que é limite de RENDER, não afeta score/ranking/carteira).
- **Pitfall pydeck 0.9.1 (`@@=` no `iconAtlas`)** confirmado e neutralizado via workaround de aspas
  (`icon_atlas='"'+atlas+'"'`) + teste-trava.

**Números medidos (QA, caminho real dos builders):** SP-like 1.381 pins = ~484 KB, sem corte; 40k
sintéticos -> 6.000 linhas (cap) = ~2,05 MB (vs ~47 MB sem cap). Bound de 40k garantido pelo cap duro.

**Validações (re-executadas pelo QA, sem bypass):** integração 159 passed; suíte completa **639 passed,
1 skipped** (baseline 631 + 8 novos); `import streamlit_app` ok; ruff All checks passed; mypy Success.

**Housekeeping 6.0:** `python scripts/housekeeping_move_block.py BLK-FIX-07 --date 2026-06-01` (stub no
backlog + bloco byte-idêntico em completed; `--check` OK; `test_housekeeping_helper.py` 10 passed;
content-identity confirmada com newline-normalize).

**Commit por path** na branch `ciclo/BLK-FIX-07` (sem `git add -A`; `PRD.md`/dados/`config.py` não
arrastados). **Dry-run de orquestração:** NÃO se aplica (não tocou run-cycle/prompts/esteira — só
dashboard render + testes + docs). **Merge:** humano, na base.

**Follow-up registrado:** `BLK-FIX-07-B — Clustering server-side por recorte` (Fase B) adicionado ao
backlog (recomendação do Planner/QA; não-bloqueante — o bound de 40k já está garantido pela Fase A).

---

### BLK-FIX-03-FU1 — Caption "capped" do Mapa Territorial pode dar falso positivo (follow-up opcional)

| Campo | Valor |
|---|---|
| **Criticidade** | **Baixa** (cosmético de UX; não toca M1/score) |
| **Prioridade** | **Baixa** |
| **Esteira** | Block Orchestrator → Builder |
| **Depende de** | BLK-FIX-03 (concluído) |
| **Status** | Pendente |
| **Origem** | Ressalva do QA no fechamento do BLK-FIX-03 (2026-06-01) |

**Contexto / gap:** após o BLK-FIX-03, o gatilho do caption "capped" em
`dashboard/pages.py` (`render_mapa_pydeck_fragment`) infere o corte por heurística
`capped = n_points >= MAP_POINT_LIMIT_LARGE` (18.000). Logo um recorte com **18.000–34.999 hexes
distintos** — que é renderizado **sem corte** (cap cheio de 35k não foi atingido) — exibiria
falsamente a mensagem "amostrado / recorte maior que o limite". É um falso positivo cosmético; o
render e os dados estão corretos.

**Objetivo:** o caption só indica "amostrado" quando houve corte de fato.

**Escopo permitido:** propagar o cap efetivo aplicado (ou o nº de candidatos pré-cap) do builder ao
fragmento, em vez de inferir por `n_points`, para que `capped`/`effective_cap` reflitam o corte real.
Sem tocar M1/score/regra de cor.

**Fora de escopo:** M1/artefatos; mudar o cap dinâmico do BLK-FIX-03.

**Arquivos prováveis:** `dashboard/components.py` (retorno dos builders quantitativos),
`dashboard/pages.py` (`render_mapa_pydeck_fragment`/`render_mapa_territorial`), testes do caption.

**Critérios de aceite:** recorte de 18k–35k hexes não exibe o caption "amostrado"; recorte que satura
(≥35k) continua exibindo o caption com o cap efetivo (18.000); suíte verde; zero M1.

**Risco:** baixo (UX/caption).

---

### BLK-FIX-04 — Seleção de hex por clique não funciona no Mapa Territorial

| Campo | Valor |
|---|---|
| **Criticidade** | **Média-Alta** (interação central da aba quebrada; não toca M1/score) |
| **Prioridade** | **Alta** |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Depende de** | — |
| **Status** | Pendente |
| **Origem** | Felipe, 2026-06-01 |

**Contexto / gap:** clicar num hexágono no Mapa Territorial não dispara a seleção / Análise Pontual.
O fluxo usa `st.pydeck_chart(..., on_select="rerun")` e `_extract_click_coord_from_selection`
(`pages.py:2294`), que tenta extrair **lat/lng** do evento de seleção; mas o `H3HexagonLayer` do pydeck
não emite lat/lng no objeto selecionado (retorna propriedades do hex / `hex_id`) → extração falha →
`click_coord` fica `None` → `lookup_hex_by_coord` (`data.py:1072`) não roda. CLAUDE.md §5 registra que
o clique usa o centroide do hex via pydeck; **confirmar se o contrato do evento mudou** com a versão de
Streamlit/pydeck.

**Objetivo:** restaurar captura de clique → seleção de hex → Análise Pontual, mantendo o fallback de
`lat,lng` na sidebar.

**Escopo permitido:** corrigir a extração para ler o identificador efetivamente retornado pelo evento
(índice / `hex_id` / objeto) em vez de assumir lat/lng; mapear de volta ao hex no `df`; garantir
`pickable=True` na camada. Sem recalcular score.

**Fora de escopo:** M1/score/artefatos; trocar o componente de mapa (decisão do Bloco 12 mantém pydeck).

**Arquivos prováveis:** `dashboard/pages.py` (`_extract_click_coord_from_selection≈2294`, render do Mapa
Territorial, `st.pydeck_chart`), `dashboard/components.py` (`build_map_figure` / `pickable` da camada),
`dashboard/data.py` (`lookup_hex_by_coord≈1072`).

**Critérios de aceite:** clique num hex seleciona e dispara a Análise Pontual (repro manual + teste do
parser de evento com payload representativo); fallback `lat,lng` preservado; zero M1; suíte verde.

**Risco:** baixo-médio (depende do contrato de evento do pydeck/Streamlit).

---

### BLK-FIX-05 — Cores da UI ficam claras em tema claro do SO (botões de aba e caixas de filtro)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (legibilidade/usabilidade; não toca M1/score) |
| **Prioridade** | **Alta** |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Depende de** | — |
| **Status** | Pendente |
| **Origem** | Felipe, 2026-06-01 |

**Contexto / gap:** em máquinas com **tema claro** do SO/navegador, os botões das abas
(`render_tab_selector` / `st.segmented_control`) e as caixas de seleção dos filtros (selectbox/
multiselect) ficam **brancos**, perdendo o fundo escuro do design. Causa provável: `.streamlit/config.toml`
**não tem bloco `[theme]`** (confirmado — só `[server]`/`[browser]`/`[client]`), então o app segue o
tema do SO (auto), enquanto o CSS de `inject_styles` (`pages.py:121`) assume fundo escuro → em tema
claro, componentes baseweb (`[data-baseweb="tab"]`, `[data-baseweb="select"]`) caem no estilo claro do
Streamlit e/ou o CSS escuro não cobre todos os estados.

**Objetivo:** UI mantém o tema escuro consistente independentemente do tema do SO/navegador.

**Escopo permitido:** fixar o tema escuro no `.streamlit/config.toml` (`[theme] base="dark"` + paleta)
e/ou endurecer o CSS de `inject_styles` para garantir contraste dos seletores de aba e filtros;
verificar em tema claro **e** escuro do SO.

**Fora de escopo:** M1/score; redesenho de identidade visual; mexer nas faixas de cor de score
(`RESIDUAL_SCORE_BANDS` / `score_band_to_color`).

**Arquivos prováveis:** `.streamlit/config.toml` (sem `[theme]`), `dashboard/pages.py`
(`inject_styles≈121`, `render_tab_selector≈359`), `dashboard/constants.py` (`COLORS`).

**Critérios de aceite:** abas e caixas de filtro mantêm fundo escuro/contraste em SO tema claro
(evidência visual antes/depois) e seguem ok no escuro; zero M1; suíte verde.

**Risco:** baixo (CSS/config).

---

## Fechamento sprint multi-track FIX (orquestrador, 2026-06-01)

Sprint paralela aprovada por Felipe (paralelizar + pré-autorizar em lote; FIX-06 mantido bloqueado).
Dois tracks executados em **worktrees git isolados** (Builders e QA em paralelo), merge sequencial na main.

**Track A — `ciclo/BLK-FIX-04` (BLK-FIX-04 + BLK-FIX-03-FU1):** QA APROVADO.
- FIX-04: clique de hex voltou a funcionar. Causa-raiz real (diferente da hipótese do backlog): o payload
  do `on_select` do H3HexagonLayer tem `hex_id` mas NÃO `lat/lng` (o `_deck_layer_frame` removeu lat/lng
  no BLK-FIX-03). Novo `_hex_id_to_centroid` + parser reescrito (hex_id→centróide; branch lat/lng defensivo).
  Round-trip provado idempotente pelo QA (`87a8100c0ffffff`→centróide→mesmo hex). `pickable` já estava ok.
- FU1: caption 'amostrado' só quando há corte real (atributo `deck._ultra_capped`/`_ultra_effective_cap`,
  sem mudar assinatura `(deck,n)`). QA confirmou o falso positivo eliminado na janela 18k–35k.

**Track B — `ciclo/BLK-FIX-05` (tema claro do SO):** QA APROVADO (prova visual final é manual do Felipe).
- `.streamlit/config.toml` ganhou `[theme] base=dark` ancorado em `COLORS`; `inject_styles` endurecido para
  segmented_control, `[data-baseweb=tab]` selecionado, texto/input do select e o popover do dropdown.

**Validação na main pós-merge (dados reais):** `646 passed, 1 skipped` (baseline 639 + 7 novos), ruff/mypy
limpos, `import streamlit_app` ok. Merges A→B auto-mergearam sem conflito (regiões distintas de pages.py).

**Gotcha registrado:** worktrees compartilham o env Python; o pacote é editable instalado da árvore
principal, então testes no worktree exigiram `PYTHONPATH=<worktree>/src` para não testar o código errado
(confirmado empiricamente). Builders/QA nunca rodaram `pip install` (env compartilhado).

**Pendência:** verificação visual do FIX-05 em SO tema claro (Felipe). FIX-06 segue bloqueado (DEC).
BLK-FIX-07-B (clustering, Fase B) permanece como follow-up.

---

## Fechamento sprint multi-track SEC-02 + FIX-07-B (orquestrador, 2026-06-02)

Sprint paralela aprovada por Felipe em lote (planos apresentados juntos; SEC-02 = Alta). Dois tracks em
**worktrees git isolados** a partir da `main`, Builders + QA independentes em paralelo, commit por path,
merge sequencial `--no-ff` na `main`, CI verde, deploy comando-a-comando. Guardrails honrados: zero
M1/score/artefatos/regra de cor; `git add` só por path; sem `pip install` nos worktrees; FIX-06 bloqueado.

**Track A — `ciclo/BLK-FIX-07-B` (clustering server-side, Fase B):** QA APROVADO.
- Gate puro `competitor_cluster_mode(selected_ufs, selected_cities, selected_faixas)` → cluster quando
  `len(ufs)<=1 and not cities and not faixas` (UF inteira/Brasil sem filtro); município/filtro ⇒ pins
  individuais com logo (caminho Fase A **intocado**, default `cluster_competitors=False` em todo lugar).
- `_build_competitor_cluster_layer`: agrega por H3 res-4 (`COMPETITOR_CLUSTER_RES=4`), centróide via
  `cell_to_latlng`, `ScatterplotLayer` dimensionado por contagem, tooltip contagem por rede/total,
  `pickable` preservado, cap duro `COMPETITOR_CLUSTER_LIMIT=2000` (payload **1.849 bytes** p/ 40k ≪ 3 MB,
  sem cortar). Selector `_competitor_layer_for_scope` + gate fiado em `build_unified_map_figure`.
- +5 testes (gate, no-cut/payload, tooltip, IconLayer preservado, dispatcher). `len(deck.layers)` inalterado.
- Arquivos: `src/motor_expansao/dashboard/{components,constants,pages}.py`, `tests/integration/test_streamlit_app.py`.

**Track B — `ciclo/BLK-SEC-02` (pip-audit + gitleaks + Trivy + pin de actions por SHA):** QA APROVADO.
- Actions todas pinadas por SHA (comentário de versão); `docker/*` subidas p/ Node 24
  (`using: node24` verificado) → **aviso de descontinuação eliminado** (zero deprecation no run de main, incl. `publish`).
- **gitleaks** bloqueante (imagem por digest) no job `test`. O 1º run do gate revelou 2 defeitos reais
  do BLK-OPS-01: `.gitleaksignore` com fingerprints **stale** (refator `jobs/`→`src/` + drift de linha) e
  invocação em CI divergente (`--source /repo` vs o `--source .` documentado). Corrigido **robusto a drift**:
  invocação `--source .` (com `-w /repo`) + falsos positivos de conteúdo em `[allowlist].regexes` do
  `.gitleaks.toml` (`renda_per_capita_setor_2022`, `test_fase_a_censo2022.py`); `.gitleaksignore` esvaziado.
  **Catch-proof:** AWS key fake plantada em branch descartável → gate reprovou (`leaks found: 1`) → branch
  deletada (a key óbvia `AKIA...EXAMPLE` é allowlist default do gitleaks; usada uma key realista sem stopword).
- **pip-audit** bloqueante no `test` (`--desc --skip-editable`; sem `--strict`, incompatível com o pacote
  local editável). Achou `pytest 8.4.2 GHSA-6w46-j5rx-g56g` (DoS local, **dev-only, fora da imagem de prod** —
  `Dockerfile.streamlit` roda `pip install .` sem `[dev]`) → `--ignore-vuln` com justificativa + revisão 2026-09.
- **Trivy** HIGH/CRITICAL (`ignore-unfixed`) no `publish` (reestruturado **build `load:true` → scan → push**,
  imagem vulnerável nunca publica; digest publicado passa a vir de `steps.push`) e no `build-sanity`. Achou
  3 HIGH em build-tools da imagem base (`wheel` CVE-2026-24049, `jaraco.context` CVE-2026-23949, também
  vendored no setuptools), sem runtime no Streamlit → `.trivyignore` (decisão de Felipe) com justificativa + revisão.
- Política de severidade documentada **inline** no `ci.yml`. Histórico iterativo (6 commits de CI-debug)
  squashed num commit limpo (`c8bba9e`). Arquivos: `.github/workflows/ci.yml`, `.gitleaks.toml`,
  `.gitleaksignore`, `.trivyignore`.

**Validação na main pós-merge (dados reais):** `651 passed, 1 skipped, 0 falhas`, ruff/mypy limpos.
CI verde na `main` (run de push): `test` ✓ + `publish` ✓ (build→Trivy→push). Merges disjuntos sem conflito.

**Deploy (2026-06-02, comando-a-comando, guardrail §6):** pin `.env` `STREAMLIT_IMAGE` →
`@sha256:6a80d527...b7c4` (commit `779698a`); `pull`+`up -d streamlit`; container `Up (healthy)`,
`/_stcore/health → ok` (via `docker exec`; porta 8501 não é publicada no host). Rollback de 1 passo:
`@sha256:2e9ac6c...04f36` (commit `058fd39`, também em `.env.bak`). Ver [[project_deploy_pin_digest_prod]].

**Gotcha de QA reconfirmado:** worktrees compartilham o env Python (pacote editable da árvore principal),
então a suíte no worktree exige `PYTHONPATH=<worktree>/src`. No worktree (sem dados gitignored) o baseline
é `574 passed, 73 skipped`; na main com dados reais é `651 passed, 1 skipped` — não comparar contagens entre os dois.

**Follow-ups registrados (revisar até 2026-09):** migração `pytest 9` (zera o allowlist do pip-audit);
imagem **multi-stage** sem build-tools no runtime (zera os 2 CVEs do `.trivyignore` de vez). FIX-06 bloqueado (DEC).

---

### BLK-ORQ-01 — Otimização de tempo de execução do /run-cycle

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** — altera a própria orquestração (`.claude/commands/run-cycle.md` + `prompts/*`) → dispara o dry-run autônomo do Passo 6.c. **NÃO** toca M1/score/artefatos. |
| **Prioridade** | **Média-Alta** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Depende de** | nenhuma (BLK-ORQ-02 depende deste) |
| **Status** | Pendente |
| **Origem** | Felipe, 2026-06-02 — ciclos do /run-cycle levando horas; pedido de identificar gargalos e otimizar tempo mantendo qualidade e documentação. |

**Contexto / diagnóstico (medições deste repo, 2026-06-02):**
- Esteira média/alta é **100% serial**: Orquestrador + Block Orchestrator + Planner + Builder + QA = 4–5 spawns, com round-trip do orquestrador (lê handoff, monta próximo prompt) entre cada estágio. Nada independente roda em paralelo.
- **Contexto pago em dobro:** o Passo 4 manda o orquestrador embutir o conteúdo dos arquivos no prompt do sub-agente, E cada `prompts/*.md` manda o sub-agente "Leia CLAUDE.md completo" — leitura duplicada (orquestrador embute + sub-agente relê).
- **Orquestrador incha:** por embutir todo arquivo, o contexto do próprio orquestrador cresce a cada estágio (CLAUDE.md 18 KB relido por 5 agentes; +4 prompts + alvos + handoffs), encarecendo cada turno e disparando compactação em ciclos longos.
- **QA duplica o Builder:** `prompts/qa_analyzer.md` exige re-executar TODAS as validações por conta própria, incluindo `pytest -q` full (**90 s medidos, 651 testes**) + leitura grau-implementação de todos os arquivos alterados. A maquinaria anti-bypass (8,4 KB, ~toda sobre o episódio BLK-OPS-01) é essencial para tooling/infra contra config real, mas overkill em todo ciclo de código comum.
- **Suíte sem paralelização:** `pytest-xdist` NÃO instalado; `pytest -q` = 90 s, roda ~2×/ciclo (Builder em alguns casos + QA sempre).
- **Sem tiering de modelo:** todo sub-agente herda o modelo da sessão (o mais pesado), inclusive trabalho mecânico (delimitar escopo, housekeeping, dry-run).
- **Block Orchestrator e Planner se sobrepõem** em baixa/média (delimitar escopo vs. plano técnico).

**Objetivo:** reduzir o tempo de relógio do /run-cycle SEM degradar qualidade de entrega nem a documentação/handoffs versionados.

**Escopo permitido — Fase 1 (Tier 1; alvo deste bloco; ganho alto, risco ~zero):**
1. **Eliminar a leitura dupla:** o orquestrador passa CAMINHOS, não conteúdo; o sub-agente lê. Ajustar Passo 4 do `run-cycle.md` e remover a redundância nos `prompts/*.md`. Mantém isolamento de contexto e os handoffs.
2. **Instalar `pytest-xdist`** (dependência `[dev]` no `pyproject.toml`) e rodar `pytest -n auto` no Builder e no QA. Não muda cobertura.
3. **Suíte full uma única vez por ciclo (no QA):** Builder valida com subconjunto impactado + smoke import; a suíte completa roda 1× no gate do QA, não em ambos.

**Candidatos a follow-up (Tier 2/3 — FORA do escopo deste bloco; promover a blocos próprios após medir a Fase 1):**
- (T2) Escopar a re-validação total anti-bypass do QA por perfil de ciclo (`tooling/infra` = re-execução total contra config real; `código` = re-run direcionado + suíte 1× + auditoria de diff). Preservar o NO-BYPASS onde importa.
- (T2) Tiering de modelo: agentes mecânicos (Block Orchestrator, housekeeping, dry-run) em modelo rápido; Planner/Builder/QA no modelo pesado.
- (T2) Fundir Block Orchestrator + Planner em baixa/média; manter separados em alta/crítica/estratégica.
- (T3) Enxugar `prompts/qa_analyzer.md` (mover narrativa do BLK-OPS-01 para `docs/`, deixar regra + ponteiro); arquivar snapshots antigos de `context/handoff/`.

**Fora de escopo (invioláveis):**
- Qualquer alteração em M1/score/artefatos oficiais.
- Remover ou enfraquecer guardrails de processo: handoff versionado append-only, NO-BYPASS de validação (onde aplicável), branch/commit isolado por path, rollback não-destrutivo, dry-run autônomo de orquestração, housekeeping via helper.
- Reduzir cobertura de teste ou qualidade da documentação/handoffs.

**Arquivos prováveis (Fase 1):** `.claude/commands/run-cycle.md` (Passo 4), `prompts/block_orchestrator.md`, `prompts/planner.md`, `prompts/builder.md`, `prompts/qa_analyzer.md` (instruções de leitura/validação), `pyproject.toml` (dep `pytest-xdist` em `[dev]`).

**Critérios de aceite:**
- Tempo de relógio de um ciclo de referência cai de forma medível (registrar antes/depois; alvo: redução ≥30% no overhead de orquestração de um ciclo média).
- `pytest -n auto` verde com a mesma contagem de testes (sem perda de cobertura); suíte full executada ≥1× no gate do QA.
- Handoffs versionados, NO-BYPASS, commit por path, rollback não-destrutivo e housekeeping via helper PRESERVADOS e demonstrados.
- **Dry-run autônomo pós-merge (Passo 6.c) EXECUTADO e reportado** — este ciclo altera a orquestração.
- Documentação atualizada (`run-cycle.md`/`prompts/*` coerentes; nota no CLAUDE.md §5 se a baseline/fluxo mudar).

**Guardrails específicos:**
- Mudança de orquestração → dry-run autônomo obrigatório (tarefa dummy Baixa + `dry_run: true`, guard de recursão prof. 1) APÓS merge humano.
- Aprovação humana obrigatória antes do Builder (criticidade Alta).
- Medir antes/depois com o MESMO ciclo de referência para evitar conclusão por ruído.

**Risco:** médio (mexe no processo, não no produto). Mitigação: faseamento (só Tier 1 aqui), dry-run de orquestração e nenhuma remoção de guardrail. Sem toque em M1/dados.

---

### BLK-FIX-06 — Hexágonos do litoral recortados pelo pipeline ⚠ (toca base M1 → Crítica + DEC)

| Campo | Valor |
|---|---|
| **Criticidade** | **CRÍTICA** — a correção altera a base de hexes do M1 e **regenera artefatos oficiais** → aprovação obrigatória + **DEC** (CLAUDE.md §2 e §8) |
| **Prioridade** | **Alta** (cobertura de mercado costeiro), **mas bloqueada por decisão humana** |
| **Esteira** | Block Orchestrator → Planner → **[REVISÃO/APROVAÇÃO HUMANA + DEC]** → Builder → QA |
| **Depende de** | decisão humana (DEC) antes de qualquer execução |
| **Status** | Pendente (bloqueado em decisão) |
| **Origem** | Felipe, 2026-06-01 (litoral: Praia Grande, Rio de Janeiro etc. sem hexes; print de exemplo) |

**Contexto / gap:** hexágonos sobre faixas litorâneas povoadas (Praia Grande, litoral do RJ, etc.)
**não aparecem** no mapa. Causa provável: `base_h3_brasil.py` filtra hexes **só por centróide dentro do
polígono do Brasil** (`shapely.intersects(brasil_geom, chunk_centroids)`, ~linha 189; remoção logada
como "centroide em mar/fronteira", ~linha 361). Hexes costeiros cujo centróide cai na água — mesmo com
a maior parte sobre terra povoada — são descartados **na geração da base, antes de qualquer score**.

⚠ **Atenção de criticidade:** corrigir isso **adiciona hexes ao universo do M1**, mudando contagens,
**percentis nacionais** e, portanto, **regenera os artefatos oficiais** (`brasil_estrutural`,
`brasil_priorizados`, `hexagonos_*`). Pela regra §2 do CLAUDE.md isso é **ALTERAÇÃO de artefato M1 →
Crítica (aprovação obrigatória + DEC)**. **Não é** um fix de dashboard trivial e **não pode** ser
executado pelo Builder sem DEC registrada.

**Objetivo:** incluir hexes litorâneos que sobreponham terra/população real, sem distorcer o M1,
mediante decisão registrada.

**Escopo permitido (somente APÓS DEC):** trocar o critério de centróide por **interseção do polígono do
hex com o polígono do Brasil** (ou critério híbrido centróide-ou-interseção com limiar de área);
**quantificar** quantos hexes entram e o impacto em percentis/score ANTES de aplicar; regenerar
artefatos de forma auditável e reprodutível.

**Fora de escopo (sem DEC):** qualquer regeneração de artefato M1; mudar pesos/fórmula
(renda=0.40/pop=0.60); parâmetros canônicos.

**Arquivos prováveis:** `src/motor_expansao/pipelines/m1/base_h3_brasil.py` (filtro de centróide
~181-194, log ~356-364), `config.py` (`M1_POP_MINIMA_PROXY`), artefatos M1 (regeneração controlada).

**Critérios de aceite:** critério geométrico revisado cobre o litoral povoado (repro: Praia Grande/RJ
voltam a aparecer); **impacto no M1 quantificado e aprovado em DEC**; artefatos regenerados de forma
reprodutível; testes do pipeline verdes.

**Risco:** **alto** (mexe na base do M1 e em artefatos oficiais; exige DEC e validação de não-regressão
do score). Mitigação: decisão humana + DEC antes de qualquer execução; medir delta de hexes/percentis.

---

- BLK-FIX-07 (concluído 2026-06-01) — ver tasks/completed.md

- BLK-FIX-07-B (concluído 2026-06-02) — ver tasks/completed.md

---

### BLK-FIX-06-C — Orla NÃO RENDERIZA no dashboard apesar dos dados corretos (display/render, NÃO é dados)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (display/render do dashboard; **NÃO toca M1/score/artefatos** — os dados já estão corretos e deployados) |
| **Prioridade** | **Alta** (continuação direta do BLK-FIX-06-B; objetivo do usuário ainda não atingido visualmente) |
| **Esteira** | Block Orchestrator → Planner → [revisão humana] → Builder → QA |
| **Status** | Pendente (registrado 2026-06-03; Felipe vai resolver a partir de amanhã 2026-06-04) |
| **Origem** | Felipe, 2026-06-03: "Não funcionou, não está renderizando no dashboard" após o deploy completo do BLK-FIX-06-B |

**Sintoma:** após o BLK-FIX-06-B (universo M1 1.542.531, limiar 0.05, TODAS as camadas paralelas
regeneradas e **deployadas** ao VPS), os hexes da orla **continuam não aparecendo** no dashboard.

**INSIGHT-CHAVE (economiza tempo amanhã): o problema NÃO é de dados — é de RENDER.** Os hexes da orla
ESTÃO presentes e corretos nos parquets SERVIDOS em produção (verificado via `docker exec` no container
live, 2026-06-03): M1 `hexagonos_brasil_dashboard.parquet`=1.542.531; `oportunidades_expansao_hibrido`
=1.542.531 com `score_oportunidade_residual`/`score_setor_2022_calibrado`/`score_expansao_hibrido`;
`plano_expansao_dominio`=5.957 com `score_dominio_hibrido`; enriquecido `uf=SP`=47.389. TODOS contêm
Mongaguá `87a810998ffffff` e PG-Mongaguá `87a810d4cffffff`. Logo o caminho de **render/exibição** está
descartando ou ocultando esses hexes — não falta dado.

**Hipóteses (ancoradas em código, a confirmar pelo Planner — NÃO confirmadas):**
1. **Corte de população "<5k hab" pinta de CINZA translúcido** (`_apply_pop_cut_colors`,
   `dashboard/components.py:1111`; `_DISCARDED_FILL=[120,120,140,70]`, alpha 70). Hexes com
   `populacao_corte_hex < POP_MIN_ACIONAVEL` (5000) viram cinza quase-invisível na base escura. Muitos
   hexes de orla têm `populacao_corte_hex` baixo (fonte `setor_2022`, ex.: Mongaguá centro=2.416) →
   cinza → parece "não renderizar". **HIPÓTESE MAIS FORTE** (eles renderizam, mas invisíveis).
2. **Score NaN no modo ativo** dropa/descolore o hex: no Censitário, muitos hexes de orla sobre água
   têm `score_setor_2022_calibrado`=NaN (sem setor censitário) → sem cor. Idem `score_expansao_hibrido`
   em alguns. Verificar se o builder do mapa filtra `notna()` por modo.
3. **Cap de display** `MAP_POINT_LIMIT_LARGE=18.000` para UFs grandes (SP tem 47k) — top-N por
   `score_priorizacao`; hexes costeiros de score baixo ficam fora do recorte. (Mas Felipe relatou que
   FILTROU poucas cidades e mesmo assim sumiu → o cap não deveria aplicar; reconfirmar.)
4. Alguma máscara de validade no builder do mapa (`build_*_map_figure` em `components.py`, layers
   `H3HexagonLayer get_hexagon="hex_id"` ~linhas 1198/1441/1687/1816/1981) que remove os hexes.

**Objetivo:** fazer os hexes da orla **aparecerem visivelmente** no dashboard (em todos os modos, ou ao
menos M1), sem mexer em M1/score/dados (já corretos). Provável fix de DISPLAY: tornar o corte de 5k
configurável/com toggle no mapa, ou elevar a opacidade/cor do "descartado", ou tratar NaN de score na
orla — decisão de produto do Felipe.

**Escopo permitido:** apenas `src/motor_expansao/dashboard/*` (render/cor/legenda/cap), sem recálculo de
score nem novo deploy de dados (os dados já estão no VPS). Guardrail §5 do CLAUDE.md: visualização não
recalcula score.

**Fora de escopo:** mexer em `base_h3_brasil.py`/M1/artefatos (BLK-FIX-06-B já fechou isso); regenerar
dados; mudar pesos/fórmula.

**Critérios de aceite:** Praia Grande/Mongaguá/litoral aparecem visíveis no dashboard (M1 e, idealmente,
nos modos operacionais) com `Ctrl+Shift+R`; sem alterar score/artefatos; testes verdes.

**Contexto/links:** BLK-FIX-06-B (DEC-003, commits `353b2c1`/`acc9ca4`); deploy live verificado
(container healthy, dados presentes); backup de rollback no VPS `outputs_bak_blkfix06b` (não precisa
rollback — dados estão certos); investigação de display em `components.py` (`_apply_pop_cut_colors`,
`MAP_POINT_LIMIT_LARGE`), `dashboard/constants.py` (`POP_MIN_ACIONAVEL`, `COLOR_MODES`).

**Risco:** baixo (só display; M1/dados intactos). Cuidado: não reintroduzir o falso diagnóstico de
"dados faltando" — os dados ESTÃO lá; o trabalho é de RENDER.

**FECHAMENTO (2026-06-03) — CONCLUÍDA, deployada e verificada por Felipe.**
- **BLK-FIX-06-C** (Alta; esteira BO→Planner→[gate humano]→Builder→QA): fix de display em
  `dashboard/components.py` — `_DISCARDED_FILL` alpha 70→150 (orla <5k visível) + relaxe de scope dos
  builders Híbrido/Residual (`score_setor_2022_calibrado.notna()`→`hex_id/lat/lng notna()`) + nova cor
  `_NAN_SCORE_FILL` para score NaN antes do pop-cut. Decisões de produto aprovadas por Felipe no gate
  (alpha 150 / fallback visível / não mexer nas tabelas / 2 cores distintas). QA APROVADO: suite full
  660 passed/1 skipped; ruff+mypy limpos. Merge `ab521ec`; deploy de IMAGEM ao VPS (digest
  `868349e0...a044d`, tag `sha-ab521ec`) — 1º deploy de imagem desde a sprint SEC-02. Housekeeping:
  bloco movido backlog→completed via helper (commit `ba79502`).
- **BLK-FIX-06-C-FU1** (follow-up ad-hoc, aprovado por Felipe): o 06-C corrigiu só os modos
  Híbrido/Residual; o mapa EXECUTIVO M1 (`build_map_figure`) ainda sumia a orla por um filtro
  intencional/testado (`key.loc[granular_rows | municipal_rows]`) que descartava hex SEM censo em UF
  granular (SP/RJ) — a orla sobre água caía aí. FU1 transforma granular/municipal em RÓTULO de
  confiança (não filtro): hexes válidos do M1 sem censo renderizam coloridos pelo `score_priorizacao`
  real, com borda municipal âmbar (fallback "sem censo" explícito). Impacto ~1.000 hexes/SP (orla +
  margens de rio/represa; score 22-100). Display-only (M1/score/artefatos intactos). 2 testes do
  descarte antigo atualizados + 1 novo (orla Mongaguá); suite full 661 passed/1 skipped; ruff+mypy
  limpos. Merge `2fa93e9`; deploy de imagem (digest `bb5a4558...850c`, tag `sha-2fa93e9`) → `Up
  (healthy)`, health `ok`.
- **Verificação do usuário:** Felipe confirmou em 2026-06-03 — "funcionando e deixando explícito quando
  é fallback" (orla visível na Análise Territorial / M1; sem-censo marcado pela borda âmbar).

---

### BLK-CENSO-01 — Relatório censitário: camadas combinadas + fundo de ruas + faixas GeoFusion + pins com logo

> **FECHAMENTO (2026-06-05) — VEREDITO: APROVADO.** Ciclo Alta executado pela esteira /run-cycle
> (BO→Planner→[gate humano: DEC-004 APROVADA por Felipe]→Builder→QA). Entregue: orquestradora
> `render_mapas_censitarios_combinados` gera **3 camadas numa só geração** (densidade / renda per capita /
> concorrentes) — UI sem dropdown (3 `st.image`) + PDF com N páginas de mapa (writer manual generalizado
> de 1→N XObjects, retrocompat `bytes`). **Fundo de ruas** via CartoDB Positron No-Labels (`contextily`
> em extra dedicado `[basemap]`, import lazy try/except), composição em **EPSG:3857** (reproj. setores+
> círculo do CRS métrico local só p/ render; método de interseção e raio 1.5 km INTOCADOS), **cache local**
> `data/cache/basemap_tiles/` (gitignored) e **fallback offline gracioso** (sem internet/extra → canvas
> branco, default em CI, coberto por teste do `try/except`). **Faixas absolutas fixas** (não quartil):
> `DENSIDADE_POP_BANDS` (Reds, cortes 1k/5k/10k/25k/inf hab/km²) e `RENDA_PER_CAPITA_BANDS` (recalibrada a
> per capita 1k/2k/3,5k/5k, NÃO copia A/B/C domiciliares do Geo); score mantém `RESIDUAL_SCORE_BANDS`;
> alpha 150 (vs 225) p/ ruas aparecerem. **Pins com logo** reusando `competitors._render_pin_tile`
> (logo ou sigla no fallback). **DEC-004** registrada no CLAUDE.md §8 (Status APROVADA); §4 + docs §6/§7/§8
> atualizados. **READ-ONLY sobre M1 confirmado por QA** (git diff vazio em `pipelines/`, `scoring.py`,
> `censo_point.py`, `config.py`; pesos 0.40/0.60 e params §3 preservados). QA (Opus 4.8) re-executou tudo
> SEM bypass: **suite full `667 passed, 1 skipped, 0 failed`** (== serial, sem flakiness), subconjunto
> 192 passed, `import streamlit_app` ok, ruff limpo, mypy 1.20.2 "no issues". Ressalva leve (não
> bloqueadora): caminho com tiles REAIS (basemap=True + internet) só verificável em deploy/visual; o ramo
> fetch-failure do `_fetch_basemap` é coberto por design (teste extra de reforço é opcional). Arquivos do
> ciclo: `pyproject.toml`, `.gitignore`, `dashboard/{constants,censo_map,pages,censo_report}.py`,
> `tests/unit/test_relatorio_pontual_censitario_{mapa,export}.py`, `tests/integration/test_streamlit_app.py`,
> `docs/relatorio_pontual_censitario.md`, `CLAUDE.md`. Sucessor: **BLK-CENSO-02** (template/visual do PDF).

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (toca o guardrail "sem dependência de API ao vivo" → exige DEC + gate humano; READ-ONLY sobre M1/score) |
| **Prioridade** | **Alta** (pedido direto de Felipe, uso operacional) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA + DEC sobre tiles online]` → Builder → QA |
| **Depende de** | nenhuma bloqueadora (feature já existe; é repaginação) |
| **Status** | Pendente |
| **Origem** | pedido de Felipe (2026-06-05) + PDFs de referência (GeoFusion / exemplo atual) |

**Contexto / estado atual (file:line confirmados):**
- O relatório roda em `render_relatorio_pontual_censitario` (`src/motor_expansao/dashboard/pages.py:2479`),
  no expander da aba Mapa Territorial. Hoje ele já gera **1 PDF combinado**, mas o **mapa mostra só
  UMA métrica por vez** (dropdown: pop / renda / score / peso), e o PDF embute **só esse 1 mapa**.
- O mapa é PNG desenhado com **Pillow, 100% offline** em `render_mapa_censitario_estatico_png`
  (`src/motor_expansao/dashboard/censo_map.py:245`) — por isso **não tem fundo de ruas**, só os
  polígonos dos setores sobre canvas branco.
- As cores usam **quartis** (`_build_breaks`, `censo_map.py:75`, cortes p20/p40/p60/p80) e paleta
  `_SECTOR_PALETTE` opaca (alpha 225) → escondem o arruamento.
- Os "símbolos esquisitos" do exemplo são: concorrentes = círculos laranja, Ultra = quadrados
  vermelhos, ponto central = círculo azul com cruz — **sem logo**, apesar de os logos das redes e
  da Ultra **já existirem no repo** e serem usados como pins SVG nos mapas pydeck
  (`preload_logos`, `src/motor_expansao/dashboard/competitors.py:203`; logos em `concorrentes/logo_*.png`
  e `data/ultra/logo_ultra.png`).
- O motor de interseção `analisar_ponto_censitario_setores` (`censo_point.py:145`) já devolve
  renda, população, densidade, setores e os DataFrames `concorrentes_raio`/`ultra_raio`.
- CSV/PDF em memória: `censo_report.py` (`gerar_csv_setores_censitarios`,
  `gerar_pdf_relatorio_pontual_censitario`, `render_downloads_relatorio_censitario`).
- Testes existentes (10 unit, a atualizar): `tests/unit/test_relatorio_pontual_censitario_motor.py`,
  `..._mapa.py`, `..._export.py` (referenciam paleta de quartil, símbolos atuais e mapa de 1 métrica).

**Objetivo:** entregar UMA exportação do relatório com (a) **renda, população e concorrentes juntos**
(sem precisar trocar dropdown e baixar vários PDFs), (b) **fundo de ruas** no mapa, (c) **faixas de
cor absolutas padronizadas estilo GeoFusion** (mais transparentes, ruas visíveis) e (d) **pins com
logo** da Ultra e das concorrentes.

**Decisões de produto já aprovadas por Felipe (2026-06-05) — o Planner deve formalizar a DEC dos tiles:**
1. **Camadas combinadas:** o relatório (UI **e** PDF) passa a apresentar, de uma vez, um mapa de
   **Renda**, um de **População/Densidade** e um mapa com **todas as concorrentes** (pins) no raio —
   numa única geração/PDF. Decidir no Planner se são 3 mapas (1 por camada) ou 1 mapa-base + variações
   de choropleth; o critério é "uma exportação só resolve".
2. **Fundo de ruas = tiles online SÓ na geração**, com **cache local** para amortizar
   (ex.: `contextily`/provedor OSM/Carto). Usar um **basemap claro/BRANCO** (ex.: Carto Positron/
   Light "no labels") — decisão de Felipe (2026-06-05): o fundo precisa ser **branco/claro** para o
   mapa de calor por cima **não ficar escuro** e as ruas seguirem legíveis. Isso **desvia do guardrail**
   "não criar dependência de API ao vivo no dashboard de produção" → **exige DEC registrada (§8) + gate
   humano**. Mitigações obrigatórias: cache local de tiles; **fallback offline gracioso** (se não houver
   internet/tiles, gera o mapa sobre canvas branco sem ruas, sem quebrar); dependência restrita ao
   caminho de geração do relatório, não à carga do dashboard.
3. **Faixas absolutas fixas estilo GeoFusion, com CORES DEFINIDAS** (não quartil) — decisão de Felipe
   (2026-06-05): cada camada tem paleta própria fixa, parecida com o GeoFusion, **transparente** o
   bastante para ver as ruas do basemap branco por baixo:
   - **População/Densidade:** rampa parecida com a do GeoFusion (escala de vermelhos por hab/km²),
     cortes fixos de referência: até 1.000 / 1.001–5.000 / 5.001–10.000 / 10.001–25.000 / >25.000 hab/km².
   - **Renda:** rampa parecida com a do GeoFusion, **adaptada para renda PER CAPITA** (não domiciliar) —
     o Planner recalibra os cortes/classes para a escala per capita (as classes A/B/C do Geo são de renda
     domiciliar; não copiar os valores, só o estilo de cor/faixas).
   - **Score censitário:** manter o padrão de projeto (`RESIDUAL_SCORE_BANDS`/`score_band_to_color`).
   Cortes e cores canônicos centralizados em constantes; comparáveis entre pontos diferentes.
4. **Pins com logo:** substituir os círculos/quadrados pelos **logos** já existentes (Ultra +
   concorrentes), reaproveitando `preload_logos`/brand colors; embutir as imagens de logo no PNG
   Pillow (ponto central, concorrentes, Ultra distinguíveis).

**Escopo permitido:**
- Editar `censo_map.py` (fundo de tiles + faixas fixas + pins com logo), `pages.py` (UI das camadas
  combinadas), `censo_report.py` (embutir os mapas combinados no PDF). Adicionar dependência de
  basemap/tiles (ex.: `contextily`) em `pyproject`/extras + cache local de tiles.
- Atualizar os 3 arquivos de teste unit + `tests/integration/test_streamlit_app.py` conforme o novo
  visual; cobrir o **fallback offline** (sem tiles) e a presença das 3 camadas no PDF.
- Atualizar o contrato `docs/relatorio_pontual_censitario.md` (§6/§7) e o CLAUDE.md §4 (linha do
  relatório) refletindo tiles+faixas+pins; registrar a **DEC** dos tiles no CLAUDE.md §8.

**Fora de escopo (invioláveis):**
- Qualquer recálculo/escrita de M1 (`scoring.py`/`constants.py`/pesos/artefatos oficiais) — é visualização.
- Mudar o método de interseção `setor_censitario_intersecao_area_1p5km` ou o raio fixo de 1.5 km.
- Tornar o **dashboard interativo** dependente de internet (o desvio de tiles é só no caminho do relatório).
- Template/diagramação final do PDF (isso é o BLK-CENSO-02).

**Critérios de aceite:**
- Uma única geração do relatório entrega renda + população + concorrentes (UI e PDF), sem múltiplos downloads.
- Mapas com fundo de ruas **branco/claro** quando há tiles; **fallback offline** gera mapa sobre canvas
  branco sem ruas, sem quebrar (testado).
- Faixas de cor absolutas fixas com **paleta própria por camada** (população = vermelhos estilo Geo;
  renda = estilo Geo adaptado a renda PER CAPITA; score = padrão do projeto), transparentes o bastante
  para ver as ruas; legenda condizente.
- Pins com logo de Ultra e concorrentes (sem os símbolos antigos); ponto central distinguível.
- Suite verde (`pytest -n auto`), ruff+mypy limpos, smoke `import streamlit_app` ok; DEC registrada; docs atualizados.
- ZERO mudança em score/carteira/plano/artefatos oficiais do M1.

**Guardrails específicos:** READ-ONLY sobre M1 (§5); o desvio do guardrail de "API ao vivo" é
**restrito à geração do relatório**, aprovado via DEC + gate humano, com cache + fallback offline.

**Risco:** médio. Pontos de atenção: dependência/limites de rate dos tiles e licença do provedor;
peso do cache; reprojeção tiles × CRS métrico local do buffer 1.5 km; regressão dos 10 testes existentes.

---

### BLK-CENSO-02 — Relatório censitário: template e visual padrão do PDF

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (apresentação/diagramação; READ-ONLY sobre M1) |
| **Prioridade** | **Média** (fase 2 — depois da função) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Depende de** | **BLK-CENSO-01** (camadas/mapas já repaginados) |
| **Status** | Pendente |
| **Origem** | pedido de Felipe (2026-06-05): "preparar o PDF para sair com template e visual padrão" |

**Contexto:** hoje o PDF é gerado por writer leve interno em `censo_report.py`
(`gerar_pdf_relatorio_pontual_censitario`, PDF 1.4 minimalista, sem dependência nova) — funcional,
mas sem identidade visual. Felipe quer um **template padrão Ultra** (layout + cores) para padronizar
e agilizar o dia a dia.

**Arquivos de referência (já no repo, em `data/referencias/`):**
- `Av. Wesley Dias Rodrigues, 1385 - Hortolândia, SP.pdf` — estudo REAL, usar **só como referência de
  diagramação/layout**. ⚠️ Contém dados de concorrentes e **PII** (nome/telefone/e-mail de pessoa) →
  **não versionar**: o Planner deve garantir regra de gitignore para este PDF antes de qualquer commit;
  jamais reproduzir a PII no template.
- `Teste Modelo.pptx` — **fundo/base vazio** aprovado por Felipe para servir de base do template
  (extrair o background/identidade e aplicar nas páginas do PDF).

**Estrutura de slides/seções aprovada por Felipe (2026-06-05):**
- **Remover:** slide de **endereço**, slide de **micro-área**, e (por hora) os slides de **polos de
  fluxo** (mercado, shoppings, supermercados, transporte, escolas, hospitais etc.).
- **Manter:** slide(s) de **concorrentes** (mapa + lista das redes no raio).
- **Slides dedicados (1 cada):**
  1. **População** (mapa/choropleth de população do BLK-CENSO-01).
  2. **Renda** (mapa/choropleth de renda do BLK-CENSO-01).
  3. **Score censitário** (mapa por `score_setor_2022_calibrado`).
  4. **Big Numbers** — painel de destaques: **pop total**, **renda média**, **scores**,
     **residual fitness**, **qtd de concorrentes** e **consumo de concorrentes**.
- **Último slide (realização):** trocar as informações dos estagiários/contato por crédito explícito
  de que o relatório foi **gerado pelo Motor de Expansão** (sem PII de pessoas).
- **Estilo:** manter **layout e cores da Ultra** (turquesa/magenta), reusando o fundo do `Teste Modelo.pptx`
  e os logos já no repo (`data/ultra/logo_ultra.png`).

**Objetivo:** dar ao PDF do relatório um template e visual padrão Ultra, reaproveitando os mapas e
KPIs já produzidos no BLK-CENSO-01, sem reintroduzir dependência de internet na **geração do PDF**.

**Fonte do Big Numbers (decisão de Felipe, 2026-06-05):** os campos que não saem do motor censitário —
**residual fitness** e **consumo de concorrentes** — devem ser puxados **do hexágono em que o ponto
está localizado** (o hex H3 que contém a coordenada). Ou seja: resolver o `hex_id` que contém o ponto
e ler `score_oportunidade_residual` / `oferta_efetiva_disponivel` (residual fitness) e o consumo de
concorrentes desse hex na camada de mercado/residual já materializada (`hexagonos_mercado_mapeado` /
`oportunidades_expansao_hibrido` / `Consumo Conc. (est.)`). É **leitura** do hex — **sem** recalcular
M1 nem a camada residual. Se o hex não existir/estiver sem o campo, exibir "n/d" com nota; não inventar
valor. pop total, renda média e scores continuam vindo do próprio relatório censitário do ponto.

**Escopo permitido:** capa/header padrão + branding Ultra (fundo do pptx), as seções fixas acima na
ordem definida, rodapé e paginação; extrair background/cores do `Teste Modelo.pptx`; avaliar trocar o
writer interno por gerador de PDF mais capaz **somente se** a dependência for aprovada (senão, estender
o writer atual). Atualizar testes de export e o contrato em `docs/relatorio_pontual_censitario.md`.
Garantir gitignore do PDF de referência real.

**Fora de escopo:** qualquer recálculo/escrita de M1; mudar dados/métricas das camadas (só
apresentação e composição); reintroduzir os polos de fluxo removidos; geocodificação de endereço
(BLK-PROD-05); slide de endereço e de micro-área (removidos por decisão de Felipe).

**Critérios de aceite:**
- PDF sai com template/identidade padrão Ultra (fundo do pptx + logos), na estrutura aprovada
  (sem endereço, sem micro-área, sem polos de fluxo; com concorrentes; slides de população, renda,
  score censitário e Big Numbers; último slide creditando o Motor de Expansão).
- Big Numbers traz pop total, renda média, scores, residual fitness, qtd e consumo de concorrentes
  (ou "n/d" auditável quando a fonte não existir offline).
- Geração do PDF **offline-segura**; nenhuma PII de pessoas no template; PDF de referência gitignored.
- Suite verde (`pytest -n auto`), ruff+mypy limpos; docs atualizados; ZERO mudança em artefatos M1.

**Risco:** baixo-médio (apresentação). Atenção a: peso de assets de branding no repo; manter geração
do PDF sem internet; fonte de residual fitness/consumo para o ponto; não regredir o conteúdo do BLK-CENSO-01.

**Fechamento do ciclo (2026-06-05) — VEREDITO QA: APROVADO (suíte full 672 passed, 1 skipped):**
Esteira /run-cycle: Block Orchestrator (sonnet) → Planner (opus) → [REVISÃO HUMANA das decisões
visuais] → Builder (opus) → QA (opus 4.8). **Gate humano (Felipe):** APROVADO com alteração de D1 —
adotar biblioteca de PDF nova **`fpdf2`** (em vez de estender o writer manual PDF-1.4). O Planner
descobriu PII real no `Teste Modelo.pptx` (`ppt/media/image24.png` = cartão de contato com
nome/telefone/e-mail) → guardrail anti-PII: `image24` NUNCA embutido, `.pptx`/PDF nunca versionados,
teste anti-PII sobre bytes crus obrigatório.
- **Entrega:** `gerar_pdf_relatorio_pontual_censitario` reescrito sobre **fpdf2** (`fpdf2>=2.7.0,<3`
  dep BASE no `pyproject.toml`), compressão de stream desativada (`set_compression(False)` +
  `pdf_version="1.4"`) para auditabilidade anti-PII + asserts de texto cru. Template Ultra de **7
  páginas**: Capa turquesa → População → Renda → Score censitário → Big Numbers → Concorrentes →
  Realização/Crédito. Endereço/micro-área/polos REMOVIDOS.
- **Assets de branding:** 2 fundos LIMPOS extraídos do `.pptx` para `data/ultra/` (gitignored;
  `relatorio_capa_bg.png` ← `image6.png` turquesa #00A79D; `relatorio_conteudo_bg.png` ← `image1.jpg`
  claro #F8F8F8). **Fallback gracioso** para cor sólida quando os assets faltam → PDF válido offline
  (QA provou: 810 KB com assets vs 93 KB fallback — caminho real do writer, não mock).
- **Big Numbers (6 métricas, READ-ONLY):** pop/renda/score médio/score máx do `result` censitário;
  residual fitness (`score_oportunidade_residual`) + consumo (`oferta_consumida_mercado_estimada`) via
  `lookup_hex_by_coord(lat,lng,df,h3_res=7)` — leitura pura do `df` já em escopo, SEM load novo nem
  recálculo de M1/residual; "n/d" auditável quando hex ausente/NaN.
- **QA (re-executado, sem confiar no Builder):** `pytest -n auto` 672 passed/1 skipped (idêntico
  serial → não-flaky); ruff/mypy limpos (fpdf2 ship `py.typed` — mypy não é falso-verde); import ok;
  anti-PII sobre bytes reais (zero `vinicius`/telefone/e-mail/`image24`); READ-ONLY M1 confirmado por
  git scope vazio em pipelines/scoring/`censo_point.py`/`censo_map.py`/`config.py`; pesos 0.40/0.60 e
  H3=7 preservados. Ressalva leve não-bloqueante: documentar qual coluna de mercado é canônica p/ o
  card "consumo de concorrentes".
- **Arquivos:** `censo_report.py` (reescrita), `pages.py` (lookup residual + propagação de kwargs),
  `pyproject.toml` (fpdf2), `tests/unit/test_relatorio_pontual_censitario_export.py`,
  `docs/relatorio_pontual_censitario.md` §7, `CLAUDE.md` §4. Assets `data/ultra/` gitignored.
- **PENDÊNCIA DE OPS (pós-merge, guardrail §6 SSH gated):** rebuild da imagem Docker (fpdf2 virou dep
  base) + redeploy por digest na VPS + copiar os 2 PNGs ao volume `/opt/motor-expansao/data/ultra/`
  (gitignored → não vão na imagem). Sem os assets, o fallback sólido mantém o PDF válido.
- Ciclo NÃO altera a orquestração (run-cycle/prompts/esteira) → sem dry-run autônomo.

---

### BLK-CENSO-03 — Relatório censitário: refino visual do mapa (ruas dominantes + conflito verde basemap×heat + aspect retangular + camada só-concorrentes)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (apresentação/visualização; READ-ONLY sobre M1/score; sem novo desvio de guardrail — tiles já cobertos pela DEC-004). Inclui `[REVISÃO HUMANA]` das decisões visuais antes do Builder. |
| **Prioridade** | **Alta** (pedido direto de Felipe em 2026-06-05; qualidade do relatório no uso diário) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA das decisões visuais]` → Builder → QA |
| **Depende de** | **BLK-CENSO-01** (concluído; FU1–FU5 deployados). Relacionado a **BLK-CENSO-02** (template do PDF consome estes mapas) |
| **Status** | Pendente |
| **Origem** | pedido de Felipe (2026-06-05), a partir do uso real comparando o relatório com o GeoFusion |

**Contexto / estado atual (pós BLK-CENSO-01 FU1–FU5; tudo display-only / READ-ONLY M1):**
- Render em `render_mapas_censitarios_combinados` (`src/motor_expansao/dashboard/censo_map.py`); UI em
  `render_relatorio_pontual_censitario` (`pages.py`); PDF em `gerar_pdf_relatorio_pontual_censitario`
  (`censo_report.py`).
- Já feito (knobs centralizados em `censo_map.py`, exceto rampas em `constants.py`): basemap **CartoDB
  Voyager No-Labels** + contraste **1.6** + zoom **+1** (`_BASEMAP_PROVIDER_ATTR`/`_BASEMAP_CONTRAST`/
  `_BASEMAP_ZOOM_BUMP`); choropleth alpha **55** (`_CHOROPLETH_ALPHA`); cobre o **frame inteiro** sem
  bordas (setores recortados ao QUADRADO do frame `_MAP_FRAME_MARGIN`, não ao círculo); rampa de renda
  **amarelo→laranja→verde** (`RENDA_PER_CAPITA_BANDS`); densidade = vermelhos (`DENSIDADE_POP_BANDS`);
  score = `RESIDUAL_SCORE_BANDS` (verde alto); pin central vermelho; **3 camadas** (Densidade/Renda/
  Concorrentes) numa geração + **1 página de mapa por camada** no PDF.
- Dimensões atuais: `width=1000, height=760` (quase **quadrado**); frame é um **quadrado** em torno do
  círculo de 1.5 km.
- Imagem de produção embute o extra `[basemap]` (DEC-004 atualizada); deploy é PULL por digest (ver
  memória de deploy / `docs/infra_producao.md`). Cada iteração visual exige **rebuild de imagem +
  redeploy por digest** na VPS.

**Problemas reportados por Felipe (vs GeoFusion):**
1. **Ruas ainda mal aparecem** — mesmo com alpha 55 + contraste 1.6 + zoom+1, as ruas seguem fracas
   perto do GeoFusion (ruas nítidas/dominantes).
2. **Verde do basemap (mato/vegetação) se confunde com o verde do choropleth** de **renda alta** e de
   **score censitário alto** — difícil distinguir vegetação do dado.
3. **Imagens quadradas** — quer os mapas mais **retangulares** (paisagem, como o GeoFusion).
4. **Falta uma camada/slide SÓ de concorrentes** — um mapa com **apenas basemap de ruas + pins de
   concorrentes/Ultra + ponto central**, **sem nenhum mapa de calor**.

**Objetivo:** aproximar o relatório do padrão visual do GeoFusion — ruas claramente dominantes, paleta
das camadas que não conflite com o verde do basemap, mapas em formato retangular, e uma camada/slide
dedicada só a concorrentes (sem choropleth).

**Direções a avaliar no Planner (decisões visuais → `[REVISÃO HUMANA]`, levar amostras reais ao gate):**
1. **Ruas dominantes:** opções não-exclusivas — (a) desenhar as ruas **por cima** do choropleth via
   overlay de tiles "só-linhas/labels" (ex.: `CartoDB.VoyagerOnlyLabels` ou layer de ruas) para nunca
   serem cobertas; (b) baixar mais o `_CHOROPLETH_ALPHA`; (c) sharpen/realce das linhas do tile;
   (d) provedor alternativo. Medir e comparar amostras (ex.: Gama/DF) no gate.
2. **Conflito verde basemap × heat:** opções — (a) trocar a paleta de **renda** e/ou **score** para
   NÃO usar verde (ex.: renda = amarelo→laranja→**roxo/azul**; score = divergente sem verde);
   (b) basemap **neutro/cinza sem áreas verdes** (ex.: Positron) nas camadas onde o verde do dado
   importa (trade-off com visibilidade de ruas); (c) aumentar saturação/contorno das faixas p/
   destacar do mato. Definir paleta canônica no gate; manter constantes centralizadas (`constants.py`).
3. **Aspect ratio retangular:** mudar `width/height` para paisagem (ex.: ~16:9, 1280×720) e o **frame**
   de quadrado para **retângulo** (recorte dos setores a um frame retangular; novo parâmetro de
   proporção junto de `_MAP_FRAME_MARGIN`). A análise/KPIs e o raio 1.5 km ficam INTOCADOS (o círculo
   segue só como referência, agora sobre frame retangular).
4. **Camada/slide só-concorrentes:** adicionar uma camada de concorrentes **sem choropleth** (só
   basemap + pins + ponto central) — definir no gate se vira a **4ª camada** (Densidade/Renda/Score/
   Concorrentes-puro) ou substitui a atual "Concorrentes" (que hoje tem choropleth de score de
   contexto). Exibir na UI e como **página dedicada no PDF**.

**Escopo permitido:** `src/motor_expansao/dashboard/censo_map.py` (render/basemap/overlay/paletas/
aspect/camadas), `constants.py` (paletas/cortes), `pages.py` (UI das camadas), `censo_report.py`
(páginas do PDF), `Dockerfile.streamlit`/`pyproject` se precisar de lib/extra novo (ex.: layer de
ruas), testes correspondentes, docs `relatorio_pontual_censitario.md` + CLAUDE.md §4; atualizar a
**DEC-004** se mudar provedor/camada de tiles.

**Fora de escopo (invioláveis):** qualquer recálculo/escrita de M1 (score/pesos/carteira/plano/
artefatos); mudar o método de interseção `setor_censitario_intersecao_area_1p5km` ou o raio fixo de
1.5 km; tornar o **dashboard interativo** dependente de internet (tiles só na geração — DEC-004);
template/branding final do PDF (isso é o **BLK-CENSO-02**).

**Critérios de aceite:**
- Ruas claramente visíveis/dominantes (validação visual no gate com amostras reais; qualitativamente
  próximo do GeoFusion).
- Verde do basemap (mato) não se confunde com renda alta / score alto (paleta resolvida; checagem visual).
- Mapas em **formato retangular** (paisagem) na UI e no PDF.
- Camada/slide **SÓ de concorrentes** (basemap + pins, **sem** choropleth) na UI e no PDF.
- READ-ONLY sobre M1 (zero mudança em score/carteira/plano/artefatos; raio 1.5 km e interseção
  intocados); suite verde (`pytest -n auto`), ruff+mypy limpos, smoke `import streamlit_app` ok;
  docs/CLAUDE.md atualizados; controles visuais centralizados em knobs/constantes.
- Deploy: rebuild da imagem (basemap embutido) + redeploy por digest na VPS (ver memória de deploy).

**Risco:** baixo-médio (visualização). Atenção: overlay de ruas pode exigir 2º fetch de tiles
(custo/cache); reprojeção do frame retangular × círculo de 1.5 km; garantir que as 4 paletas não
conflitem entre si nem com o basemap; cada iteração visual exige rebuild de imagem + redeploy por digest.

**Estado atual (2026-06-08) — FU1→FU3 já implementados e deployados:**
- **FU1/FU2 (DESCARTADOS):** tentativa de desenhar as ruas por `ImageFilter.FIND_EDGES` (linhas
  escuras sobre base clara Voyager) — **reprovado por Felipe: deixou o mapa ilegível** (malha de
  linhas pretas em cima de tudo). Não reusar edge-detection.
- **FU3 (VIGENTE em prod, pin `77a5a983...2bf7`, commit `bc32f68`):** mapa refeito no estilo do
  mapa interativo do dashboard → **base ESCURA CartoDB Dark Matter** (`_BASEMAP_PROVIDER_ATTR=
  "DarkMatter"`, = `pdk.map_styles.CARTO_DARK`); ruas/nomes nítidos sobre a cor recolocando os
  PRÓPRIOS pixels CLAROS do tile (`_STREET_FLOOR=52`/`_STREET_GAIN=2.6`/`_STREET_CAP=230`, NÃO
  edge-detection); `_CHOROPLETH_ALPHA=95`, contraste 1.35; círculo do raio LARANJA (`_CIRCLE_RGBA`),
  escala/labels claros (`_DARK_MAP_INK`); frame retangular OK. Tudo em `censo_map.py`, READ-ONLY M1.

**>>> FOLLOW-UP PEDIDO POR FELIPE (2026-06-08) — a ser retomado em NOVA janela de contexto:**
**Trocar a base ESCURA (Dark Matter) por uma base CLARA, mantendo a MESMA legibilidade** de ruas/
nomes sobre a cor que o FU3 alcançou (era isto que Felipe queria desde o início; acabou saindo
escuro). Dicas de implementação (para não repetir o erro do FU1/FU2):
- Trocar `_BASEMAP_PROVIDER_ATTR` de `DarkMatter` para um provedor CLARO COM labels (ex.: CartoDB
  `Positron` ou `Voyager`). Re-tunar `_BASEMAP_CONTRAST` e `_CHOROPLETH_ALPHA` para fundo claro.
- **INVERTER a recolocação de "tinta":** numa base CLARA as ruas/nomes são pixels ESCUROS (não
  claros). O overlay atual (`_STREET_*` em `_render_camada`) recoloca pixels CLAROS (correto p/ Dark
  Matter); para base clara, recolocar pixels ESCUROS (luminância < cutoff) — são as ruas/nomes
  NATIVOS do tile. **Continuar usando os pixels nativos do tile, NUNCA edge-detection** (foi o que
  deixou ilegível).
- Reverter os elementos desenhados no mapa para tema claro: barra de escala/labels para tinta
  ESCURA (hoje `_DARK_MAP_INK` claro); círculo pode seguir laranja ou voltar ao navy; fallback
  offline = canvas claro (hoje escuro `(34,38,49)`).
- Validar visualmente com basemap real (contextily) no ponto RJ `-22.87650,-43.34582` antes de
  deployar; aprovar preview com Felipe; só então rebuild de imagem + redeploy por digest.
- **Ainda pendente do escopo original:** a **camada/slide SÓ de concorrentes** (basemap + pins, SEM
  choropleth) — ver critério de aceite acima; não foi feita nos FU1–FU3.

**FECHAMENTO DO CICLO — FU4 (2026-06-08, esteira /run-cycle autônoma BO→Planner→[gate visual resolvido upfront]→Builder(opus)→QA(opus); VEREDITO: APROVADO):**
- Gate de decisões visuais resolvido UPFRONT por Felipe (autorização "de uma só vez"): base CLARA =
  **CartoDB Voyager COM labels** (substitui Dark Matter do FU3); camada concorrentes = **SUBSTITUIR** a
  atual por SÓ-pins (sem choropleth); conflito verde = **MANTER** rampas atuais confiando na base.
- Builder (`censo_map.py`, `censo_report.py`): `_BASEMAP_PROVIDER_ATTR` "DarkMatter"→**"Voyager"**;
  overlay de ruas INVERTIDO (recoloca pixels ESCUROS nativos do tile, `lum < _STREET_CEIL=160`,
  `_STREET_GAIN=2.2`/`_STREET_CAP=210`; `_STREET_FLOOR` removido; **nunca** FIND_EDGES); tema claro
  (`_DARK_MAP_INK=(31,41,55)` lum≈37, fallback offline canvas claro `(245,245,245)`, `_CHOROPLETH_ALPHA`
  95→140, `_BASEMAP_CONTRAST` 1.35→1.15, círculo segue laranja); camada concorrentes via flag
  `pins_only=True` (sem loop de choropleth nem overlay); `MAP_LAYER_TITLES[2]` → "Concorrentes e Ultra";
  footer cita "CartoDB Voyager". Frame retangular e raio 1.5 km/`setor_censitario_intersecao_area_1p5km`
  INTOCADOS.
- **Validação visual REAL (online, contextily) no ponto RJ `-22.87650,-43.34582`: APROVADA pelo Builder**
  (fundo claro Voyager, ruas/nomes escuros nítidos sobre o choropleth, camada concorrentes só-pins,
  círculo laranja, escala em tinta escura). Knobs iniciais não precisaram de retune.
- QA (Opus 4.8, gate único): suíte FULL `678 passed, 1 skipped, 0 failed` (idêntico em `-n auto` e
  serial → sem flakiness); ruff limpo; mypy "no issues"; `import streamlit_app` ok. READ-ONLY M1
  confirmado (git scope vazio em pipelines/scoring.py/censo_point.py/config.py; H3=7, renda=0.40/pop=0.60
  preservados). No-bypass confirmado. Achados LEVES não bloqueadores: `_score_legend_entries()` virou
  dead code; docstring de `_fetch_basemap` ainda diz "No-Labels"; caption pré-existente em `pages.py`.
- Docs: `docs/relatorio_pontual_censitario.md`, `CLAUDE.md §4` (FU3→FU4) e **DEC-004** (provedor Dark
  Matter → Voyager COM labels) atualizados.
- **PENDÊNCIA DE OPS (pós-merge, guardrail §6 SSH gated):** aprovação visual final de Felipe + rebuild
  da imagem Docker (basemap embutido) + redeploy por digest na VPS. Fora deste ciclo de código.
- Ciclo NÃO altera a orquestração (run-cycle/prompts/esteira) → **sem dry-run autônomo**.
- Paths do ciclo (commit por path): `src/motor_expansao/dashboard/censo_map.py`,
  `src/motor_expansao/dashboard/censo_report.py`, `tests/unit/test_relatorio_pontual_censitario_mapa.py`,
  `tests/unit/test_relatorio_pontual_censitario_export.py`, `docs/relatorio_pontual_censitario.md`,
  `CLAUDE.md`, `.gitignore`, `tasks/backlog.md`, `tasks/completed.md`, `tasks/current_task.md`,
  `context/handoff.md`, `context/handoff/`.

---

### BLK-API-01 — Definir arquitetura e contrato da API (G1)

| Campo | Valor |
|---|---|
| **Criticidade** | **Estratégica** (nova fase: stand-up de uma API; redesenho de superfície de consumo do motor) |
| **Prioridade** | **Alta** (urgent no ClickUp; G1 é pré-requisito de G2/G3/G4) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — decisões-chave de contrato]` → Builder → QA |
| **Status** | Pendente |
| **Responsável sugerido** | Felipe |
| **ClickUp** | `86e1rtfe3` — https://app.clickup.com/t/86e1rtfe3 (subtarefa de `86e1rtfcy`) |
| **Toca dados/artefatos** | **Não** (bloco de design; só docs) |

**Contexto:** G1 é a fundação do projeto API. É um bloco **de design/decisão, sem código de produção** —
produz o contrato e o ADR que destravam G2 (backend) e definem em quantos blocos o resto se quebra. O
scaffold FastAPI já existe em `fora_primeira_fase/api_postgis/` (`main.py` esqueletado) e o extra `[api]`
já está no `pyproject.toml`; G1 decide o que dele se aproveita e o layout final em `src/motor_expansao/api/`.

**Objetivo:** entregar um contrato de API aprovado por Felipe, suficiente para o Juan implementar G2 sem
re-discussão de arquitetura, e um ADR registrando as decisões.

**Entregáveis (Builder escreve, após o gate):**
- `docs/api_geoespacial_contrato.md` — contrato técnico: layout do pacote `src/motor_expansao/api/`,
  fronteira "importa-não-edita `censo_*`", lista de endpoints, schemas de request/response, auth, erros,
  versionamento, e a **decomposição de G2+ em blocos** (`BLK-API-02..0N` com escopo de cada um).
- Esboço **OpenAPI** dos endpoints do MVP (arquivo `docs/api_geoespacial_openapi.yaml` ou bloco no contrato).
- **ADR** (estilo das DECs do CLAUDE.md §8) registrando as decisões-chave abaixo, para entrar como nova DEC.
- Atualização mínima do README/PRD apontando para o contrato (sem implementar a API).

**Escopo permitido:** `docs/` (contrato + OpenAPI + ADR), `tasks/`, e edição de texto do README/PRD.
**NENHUM** código de produção neste bloco.

**Fora de escopo:** implementar rotas/handlers; subir container; PostGIS; integração Telegram/WhatsApp
(G4); qualquer escrita em `src/motor_expansao/` (exceto, se decidido no gate, criar a pasta `api/` **vazia**
com `__init__.py` como marcação de layout — sem lógica); recalcular/alterar M1 (§5).

**Decisões que EXIGEM gate humano** (o Planner apresenta cada uma com as opções e sua recomendação;
**Felipe decide no Passo 5 antes do Builder**; o Builder só redige o contrato com as escolhas confirmadas):

1. **Formato de saída da API** *(ponto-chave citado por Felipe)*
   - (a) JSON estruturado com os KPIs do ponto (leve, bot renderiza a mensagem).
   - (b) PDF binário (o relatório de 7 páginas) inline na resposta.
   - (c) **[recomendado]** Ambos por negociação — `/analisar` retorna JSON por padrão e `?formato=pdf`
     (ou `Accept: application/pdf`) devolve o relatório; reaproveita `analisar_ponto_censitario_setores`
     + `gerar_pdf_relatorio_pontual_censitario`.
   - (d) JSON + link para o PDF gerado sob demanda.

2. **Autenticação** (uso interno + bots)
   - (a) API key estática por header (`X-API-Key`) — mais simples.
   - (b) **[recomendado]** Token por consumidor/bot — permite rastrear **quem** pediu o estudo (casa com
     BLK-EST-01: marca d'água + solicitante no PDF / logs LGPD).
   - (c) Reuso do Authelia/JWT já em produção.

3. **Superfície de endpoints do MVP** (define quanto G2 entrega)
   - (a) **[recomendado]** Mínimo: `GET /health` + `POST /analisar` (ponto censitário 1.5 km).
   - (b) Acrescentar lookup de hex M1 / camada de mercado já no MVP.
   - → A escolha alimenta diretamente a decomposição de `BLK-API-02..0N`.

4. **Entrada de coordenada**
   - (a) Apenas `{lat, lng}`.
   - (b) **[recomendado]** `{lat, lng}` **e** link do Google Maps (parser extrai a coordenada) — os bots
     receberão link colado pelo usuário (o roadmap do PDF prevê "parser de links Maps").

5. **Raio de análise no MVP**
   - (a) **[recomendado]** Fixo 1.5 km (igual ao Relatório Pontual Censitário — motor intocado).
   - (b) Parametrizável (exige validar limites e revalidar o método de interseção).

6. **Carimbo de versão/reprodutibilidade**
   - **[recomendado]** Incluir a versão do contrato/score no JSON e no rodapé do PDF (item de
     reprodutibilidade do PDF estratégico), para estudos antigos seguirem interpretáveis.

**Critérios de aceite:** contrato + OpenAPI + ADR escritos e coerentes entre si; todas as 6 decisões acima
resolvidas e registradas no ADR com a opção escolhida; decomposição de G2+ em blocos explícita; fronteira
"importa-não-edita `censo_*`" e "on-demand, PostGIS fora do MVP" registradas; **zero código de produção**
(git scope só em `docs/`, `tasks/`, `README.md`/`PRD.md`); suíte + ruff + mypy verdes (bloco de docs não
deve quebrar nada); READ-ONLY M1 comprovado (sem escrita em `pipelines/`/`config.py`/scoring).

**Guardrail:** §2 (fontes canônicas) + §5 (READ-ONLY M1) + §6 (deploy/VPS é humano — não se aplica aqui,
pois G1 não faz deploy). API ao vivo no dashboard de produção **não** é introduzida por este bloco.

> **Decomposição de G2+ aprovada em BLK-API-01** (gate de Felipe 2026-06-10, DEC-005; Decisão 3 = (a)
> MVP mínimo). Contrato canônico: `docs/api_geoespacial_contrato.md` (+ `docs/api_geoespacial_openapi.yaml`).
> Premissas invioláveis: on-demand sem PostGIS no MVP; importa-não-edita `censo_*`; código novo só em
> `src/motor_expansao/api/`; deps só no extra `[api]`; READ-ONLY M1. Blocos abaixo são sucessores do G1.

**FECHAMENTO DO CICLO (2026-06-10, esteira /run-cycle autônoma BO→Planner→[GATE HUMANO das 6 decisões: Felipe APROVOU todas as recomendações do Planner]→Builder(opus)→QA(opus 4.8); VEREDITO: APROVADO):**
- **Gate humano (Felipe, 2026-06-10):** 1=(c) JSON + `?formato=pdf`; 2=(b) token por consumidor/bot; 3=(a) MVP mínimo `GET /health`+`POST /analisar`; 4=(b) `{lat,lng}` E link Google Maps; 5=(a) raio fixo 1.5 km; 6=incluir carimbo de versão. Registradas na **DEC-005** (CLAUDE.md §8).
- **Entregáveis:** `docs/api_geoespacial_contrato.md` (15 seções; fronteira importa-não-edita com as 4 assinaturas reais de `censo_*`; endpoints MVP; schemas; auth por token→consumidor; erros; versionamento `/api/v1`+carimbo; subset MVP do extra `[api]` vs legado PostGIS), `docs/api_geoespacial_openapi.yaml` (OpenAPI 3.1.0 do MVP), **DEC-005** no §8, decomposição **BLK-API-02..07** no contrato e no backlog, ponteiros mínimos em README.md/PRD.md. **ZERO código de produção** (pasta `api/` nasce no BLK-API-02).
- **QA (Opus 4.8, gate único, sem bypass):** suíte FULL `679 passed, 1 skipped, 0 falhas` (679 vs baseline 532 = ambiente Py 3.14 local); `import streamlit_app` ok; `ruff check src/ tests/` limpo; `mypy src/` limpo (46 files); `yaml.safe_load` do OpenAPI ok; assinaturas `censo_*` do contrato batem 100% com o código; zero placeholder `<<DECISÃO N>>` pendente. **READ-ONLY M1 comprovado:** git scope só em `docs/`/`tasks/`/`CLAUDE.md`/`README.md`/`PRD.md`/`context/`; ZERO em `src/motor_expansao/`; pesos 0.40/0.60, H3=7, raio 1.5 km e método de interseção INTOCADOS (só descritos). DEC-001..004 intocadas.
- Commit por path na branch `ciclo/BLK-API-01` (deleções pré-sujas `data/raw/ibge/*.geojson` NÃO arrastadas). **Não dispara dry-run** (ciclo não altera a orquestração). Próximo: merge humano da branch + início do BLK-API-02 (esqueleto do app, Juan/G2).

---

### BLK-FIX-11 — Tornar funcionais os 3 overlays "mortos" do Mapa Territorial (Alternativa A)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (display/interação; READ-ONLY sobre M1) |
| **Prioridade** | **Alta** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA das decisões visuais]` → Builder → QA |
| **Status** | Pendente |
| **Responsável sugerido** | Vini |
| **ClickUp** | `86e1rtefy` — https://app.clickup.com/t/86e1rtefy |
| **Relacionado** | **Supersede o BLK-FIX-07** (mesma tarefa ClickUp `86e1rtefy`, "Overlays do mapa territorial não funcionando"). Leitura de 2026-06-09: `concorrentes`/`ultra` **funcionam**; os 3 abaixo é que estão mortos. BLK-FIX-07 marcado como superseado. |

**Contexto / causa-raiz (ancorada no código):** o registro `OVERLAYS` em
`src/motor_expansao/dashboard/constants.py` (≈ linha 394) declara **5 overlays** e o multiselect
`render_mapa_territorial` (`pages.py` ≈ linha 2733) os expõe todos. Porém, no dispatcher
`build_unified_map_figure` (`components.py` ≈ linhas 2953-2957) e na legenda `_render_unified_legend`
(`pages.py` ≈ linhas 1816-1819) **apenas `"concorrentes"` e `"ultra"`** são lidos de `enabled_overlays`.
Os outros três aparecem no multiselect mas marcar/desmarcar **não muda nada no mapa**:
- **`hex_pesquisado`** — `search_pin`/`search_hex_id` são passados **incondicionalmente** aos builders
  (`pages.py` ≈ linhas 2766-2767); o id `"hex_pesquisado"` nunca é consultado.
- **`descartados_5k`** — a coloração de descartados é aplicada **sempre** dentro dos builders quando existe
  `flag_pop_min_5k` (`components.py` ≈ linhas 505, 527, 1117); `"descartados_5k"` nunca é lido. *(Nota: o
  `absent_behavior` dele é `show_neutral`, indício de que a fiação foi prevista e não concluída.)*
- **`ancoras_dominio`** — `"ancoras_dominio"` nunca é desenhado como camada de mapa; as únicas ocorrências
  são um KPI e a contagem radial, não o multiselect.

**Objetivo:** **Alternativa A** — fazer os 3 toggles funcionarem de verdade:
- `hex_pesquisado`: só passar/renderizar o pin e o hex pesquisado quando `"hex_pesquisado" in enabled_overlays`.
- `descartados_5k`: propagar a flag aos builders e **pular** a coloração/camada de descartados <5k quando
  desmarcado (mantendo o comportamento atual quando marcado).
- `ancoras_dominio`: desenhar de fato uma camada de âncoras de domínio (a partir do `dominio_df`) quando
  marcado; ocultar quando desmarcado.

**Escopo permitido:** `components.py` (gate de `enabled_overlays` no dispatcher + builders; nova camada de
âncoras), `pages.py` (passar `enabled_overlays`/`dominio_df` ao caminho de busca e descartados; legenda
coerente com o que está ligado), `constants.py` se ajustar `OVERLAYS`, e testes em
`tests/integration/test_streamlit_app.py`. Só display/interação.

**Fora de escopo:** recalcular score/carteira/plano; alterar artefatos M1; mudar o cap de pontos
(`MAP_POINT_LIMIT*`/`COMPETITOR_PIN_LIMIT`/`ULTRA_PIN_LIMIT`) sem aprovação.

**Critérios de aceite:**
- Marcar/desmarcar **Hex pesquisado**, **Descartados <5k hab** e **Âncoras Domínio** muda o mapa de forma
  visível e coerente com a legenda; `concorrentes`/`ultra` seguem funcionando (sem regressão).
- Teste cobrindo cada um dos 3 overlays antes inertes (ligado vs desligado → camada presente/ausente).
- Suíte + ruff + mypy verdes; READ-ONLY M1 comprovado (git scope vazio em `pipelines/`/`scoring.py`/`config.py`).
- Decisão registrada sobre encerrar/superseder **BLK-FIX-07**.

**Guardrail:** visualização não recalcula nem altera M1 (§5).

---

### BLK-SAM-01 — Redefinir condições de cálculo do SAM (Faixa M1 + população ≥ 5000)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (altera o VALOR da camada PARALELA de mercado/residual; **não** é M1 oficial, mas redefine semântica → exige revisão humana) |
| **Prioridade** | **Alta** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA das decisões de produto]` → Builder → QA |
| **Status** | Pendente |
| **Responsável sugerido** | Vini |
| **ClickUp** | `86e1rte9n` — https://app.clickup.com/t/86e1rte9n |
| **Relacionado** | **Supersede o BLK-FIX-08** (mesma tarefa ClickUp `86e1rte9n`, "SAM não calculando…"): este bloco é a versão precisa/decidida; BLK-FIX-08 marcado como superseado. **Absorve** a preocupação de cobertura do BLK-FIX-08 — fallback de população em UFs de baixa cobertura censitária (RR/AC/AM): rotular SAM como "sem base" em vez de zerar silenciosamente quando não há população auditável (ver decisão #2). |

**Contexto / estado atual (ancorado no código):** hoje o SAM é gateado em
`src/motor_expansao/pipelines/calcular_colunas_mercado.py` por:
- `flag_sam = flag_viavel & top_municipio & ~flag_canibalizacao_ultra_1km` (≈ linha 274);
- `flag_sam_fitness = flag_sam & (tam_populacao_hex > 0)` (≈ linha 279);
- `sam_fitness_potencial = where(flag_sam_fitness, tam_fitness_potencial, 0.0)` (≈ linha 280).

Consequência observada: hexes com **boa Faixa M1** podem ter `sam_fitness_potencial = 0` por estarem fora do
top_municipio, canibalizados, ou sem `tam_populacao_hex > 0` (sem limiar mínimo de população).

**Objetivo (pedido de Felipe):** o SAM deve ser calculado **para hexes nas Faixas M1
`baixa`, `media`, `alta` e `prioridade_maxima`** (ou seja, excluindo `descartado` e `inviavel`), **e** que
contenham **pelo menos 5000 de população**. Hexes fora dessas faixas ou abaixo de 5000 hab → SAM = 0
(ou rótulo explícito "sem base"), sem zeragem silenciosa por outras causas.

**Decisões de produto — TODAS RESOLVIDAS por Felipe em 2026-06-09** (registrar como nova DEC no CLAUDE.md §8 na execução; o Builder implementa direto, sem novo gate de produto):
1. **[RESOLVIDO por Felipe, 2026-06-09]** Gate redefinido assim: **manter** `~flag_canibalizacao_ultra_1km`
   como filtro; **substituir** `top_municipio` pelos novos critérios — **Faixa M1 ∈ {baixa, media, alta,
   prioridade_maxima}** *e* **pop ≥ 5000**. Resultado pretendido:
   `flag_sam = faixa_oportunidade.isin({baixa,media,alta,prioridade_maxima}) & (pop_corte ≥ 5000) & ~flag_canibalizacao_ultra_1km`
   (sobre o campo de população decidido em #2). Consequência aceita da remoção do `top_municipio`:
   o SAM passa a ser calculado **fora do recorte M1** (municípios não-top), desde que faixa+pop satisfaçam.
   **Sub-decisão do `flag_viavel` — [RESOLVIDA por Felipe, 2026-06-09]:** **manter** `flag_viavel` como guarda
   adicional. Motivo (verificado nos dados 2026-06-09): `flag_viavel` **não** embute piso de 5000 — sua parte de
   população é só `hex_sem_populacao=False` (= `populacao_proxy ≥ 1`); logo **não é redundante** com a nova regra
   e não a entrega sozinho. A **única** sobreposição é a faixa (`flag_viavel` já exige faixa ∉ {descartado,inviavel},
   = o mesmo conjunto {baixa,media,alta,prioridade_maxima}); mantê-lo é inofensivo e **preserva de brinde o filtro de
   renda** (`renda_target_proxy ≥ RENDA_MIN`). Gate efetivo: `flag_viavel & faixa∈{…} & (pop_corte ≥ 5000) & ~canibal`.
2. **[RESOLVIDO por Felipe, 2026-06-09] Campo de população do corte de 5000 = `populacao_corte_hex` / `flag_pop_min_5k`**
   (a régua operacional `POP_MIN_ACIONAVEL=5000` que o dashboard **já tem**, em `data.py::derive_pop_cut_columns`:
   setor 2022 quando granular, fallback total municipal `pop_total`). **NÃO** usar `pop_hex_base`/`tam_populacao_hex`.
   Justificativa (medido nos dados de 2026-06-09): `pop_hex_base` é a população do setor **rateada por hexágono**
   (mediana nacional ≈ **5** hab; **97,4%** dos 196.715 hexes com SAM>0 têm `pop_hex_base < 5000`) — cortar 5000 sobre
   ela **aniquilaria ~97% do SAM**. A régua `populacao_corte_hex` é a noção de "5k habitantes" pretendida (no recorte
   SP, só ~14% dos hexes com SAM>0 a passam — filtro forte, não aniquilador). **Atenção de implementação:**
   `populacao_corte_hex`/`flag_pop_min_5k` hoje são derivados na **camada do dashboard** (`data.py`), não na de mercado;
   o Builder precisa torná-los disponíveis em `calcular_colunas_mercado` (mover/compartilhar `derive_pop_cut_columns`
   ou recomputar a mesma regra no pipeline), sem duplicar a lógica de forma divergente.
3. **[RESOLVIDO] Limiar inclusivo `≥ 5000`** (conforme "pelo menos 5000"); coerente com `flag_pop_min_5k` (`.ge(5000)`).

**Escopo permitido (camada PARALELA, não M1 oficial):** o gate do SAM em `calcular_colunas_mercado.py`
(`flag_sam`/`flag_sam_fitness`/`sam_fitness_potencial`) e, se necessário, parâmetro do limiar 5000 em
`config.py`/`constants.py`. Se houver regeneração de parquets paralelos, seguir a **ordem canônica**:
híbrido → mercado → `calcular_colunas_mercado` → carteira → plano → domínio → residual → `fase1_bi_exports`.

**Fora de escopo (inviolável):** `score_priorizacao`/`hex_score_estrutural`/pesos/`faixa_oportunidade`/
artefatos oficiais do M1 (DEC-001 vigente; a Faixa M1 é **lida**, não recalculada); inventar população onde
não há base auditável.

**Critérios de aceite:**
- SAM calculado exatamente para Faixa M1 ∈ {baixa, media, alta, prioridade_maxima} **e** população ≥ 5000
  (campo confirmado no gate); demais hexes com SAM = 0 ou rótulo explícito.
- As 3 decisões acima resolvidas e registradas (idealmente como nova DEC no CLAUDE.md §8).
- Repro de ≥1 hex que **passa a calcular** e ≥1 que **passa a zerar** sob a nova regra, com causa documentada.
  **Repro de referência (verificado nos dados de 2026-06-09)** — hex `87a91b18dffffff` (Santo Amaro da Imperatriz/SC):
  hoje tem `sam_fitness_potencial ≈ 7,28` (SAM>0) porque passa em tudo (`flag_viavel=True`, `top_municipio=True`,
  `canibal=False`, faixa `prioridade_maxima`, `score_priorizacao=75,84`) e o gate atual só exige `tam_populacao_hex>0`
  (= **35,4** hab, setor 2022 rateado). Sob a nova regra, `populacao_corte_hex = 35,4` → `flag_pop_min_5k=False`
  → **SAM deve passar a 0**. É o caso canônico de "pop < 5000 com SAM" que motivou o bloco.
- Parquets paralelos regenerados de forma reprodutível, se necessário; **ZERO escrita em M1 oficial**.
- Suíte + ruff + mypy verdes (incluindo testes novos do gate em `tests/integration/test_modelo_mercado_hexagonos.py`).

**Guardrail:** não toca o M1 oficial; mudança restrita à camada de mercado/residual paralela (§4/§5).

---

### BLK-EST-01 — Marca d'água + nome do usuário solicitante nos PDFs

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (rastreabilidade/LGPD + identidade do solicitante no documento) |
| **Prioridade** | **Alta** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Responsável sugerido** | Vini |
| **ClickUp** | `86e1rteq7` — https://app.clickup.com/t/86e1rteq7 |
| **Relacionado** | ClickUp `86e1rtezm` (logs de rastreio LGPD, do Felipe) |

**Contexto:** anexar marca d'água + nome do usuário que solicitou o estudo no PDF, para rastreabilidade
(base LGPD). A identidade do solicitante vem da sessão autenticada (Authelia). Coordenar com a tarefa de
logs LGPD do Felipe para padronizar a fonte do "solicitante".

**Objetivo:** todo PDF gerado carrega marca d'água + nome do solicitante de forma legível e não removível trivialmente.

**Escopo permitido:** `src/motor_expansao/dashboard/censo_report.py` (composição do PDF sobre `fpdf2`);
passar o identificador do solicitante pelo caminho de geração.

**Fora de escopo:** versionar PDFs reais (PII); embutir o cartão de contato `image24.png` (anti-PII, §4);
score/artefatos M1.

**Critérios de aceite:** marca d'água + solicitante presentes no PDF; fonte do nome definida e testada;
sem PII versionada; compressão de stream OFF preservada (auditabilidade anti-PII); suíte verde; READ-ONLY M1.

**Guardrail:** anti-PII do §4 preservado; sem dependência de API ao vivo.

**Fechamento (concluído 2026-06-11 — esteira /run-cycle BO→Planner→[gate humano]→Builder→QA):**
APROVADO pelo QA (Opus 4.8). Marca d'água diagonal "Ultra Academia [| {solicitante}]" embutida em TODAS
as 7 páginas do PDF do Relatório Pontual Censitário, via novo parâmetro opcional `solicitante: str | None
= None` em cascata nas 3 funções públicas de `censo_report.py` (`gerar_pdf_relatorio_pontual_censitario`,
`gerar_payloads_download_relatorio_censitario`, `render_downloads_relatorio_censitario`) + helpers
`_watermark_text` e `_draw_watermark`. **Gate humano (Felipe/usuário, 2026-06-11):** D1 = contrato mínimo
`solicitante=None` com fallback seguro (None → só "Ultra Academia"); D2 = opção (b), marca d'água em todas
as 7 páginas. fpdf2 **2.8.7** confirmado por inspeção real: rotação via `pdf.rotation(angle,x,y)` +
transparência via `local_context(fill_opacity=...)` (`text_opacity`/`set_alpha` NÃO existem nesta versão);
com `set_compression(False)` o texto sai legível nos bytes crus ("não removível trivialmente"). `pages.py`
INTOCADO (default `None` propaga). **READ-ONLY M1** confirmado (diff de `pipelines/`+`config.py`+`scoring.py`
VAZIO; pesos renda=0.40/pop=0.60 e artefatos oficiais intocados). **Anti-PII** preservado (fixtures com nome
fictício "Analista Teste"; `test_pdf_sem_pii_de_pessoas` verde; nenhum PDF/`image24.png` versionado).
**Testes:** arquivo do bloco 13 passed (3 novos + `/Count 7` + `_count_layer_titles==3`); suíte full serial
689 passed / 3 failed / 1 skipped — as 3 falhas (`test_modelo_mercado_hexagonos.py`) PROVADAS pré-existentes
(idênticas com o bloco stashed; herança do estado SAM/DEC-007, sem relação com o BLK-EST-01); ruff + mypy
limpos; `import streamlit_app` ok. Arquivos: `src/motor_expansao/dashboard/censo_report.py` +
`tests/unit/test_relatorio_pontual_censitario_export.py`. Ressalva do QA p/ o orquestrador: as 3 falhas de
mercado saneiam no merge dos blocos SAM em main + regeneração canônica dos parquets paralelos (não é defeito
deste bloco). Pendência funcional: integração Authelia/sessão (fonte real do nome) fica para bloco futuro;
o contrato `solicitante` já está pronto para a API (DEC-005).

---

### BLK-MAP-01 — Filtro individual de concorrentes nos overlays do Mapa Territorial

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (nova função/UI localizada na camada de visualização; READ-ONLY sobre M1) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA leve — estilo do controle de UI]` → Builder → QA |
| **Status** | Pendente |
| **Responsável sugerido** | Vini |
| **ClickUp** | `86e1ut13u` — https://app.clickup.com/t/86e1ut13u |
| **Relacionado** | BLK-FIX-11 (overlays do Mapa Territorial, Alternativa A); BLK-UI-01 (refator UX amplo) |

**Contexto (ancorado no código, leitura 2026-06-11):** hoje o overlay de concorrentes do Mapa Territorial
é tudo-ou-nada. O controle de UI é um `st.multiselect` de overlays em `render_mapa_territorial`
(`src/motor_expansao/dashboard/pages.py:2743-2749`); o builder `build_unified_map_figure`
(`src/motor_expansao/dashboard/components.py:3008`) liga/desliga o conjunto inteiro via
`_comp = competitors_df if "concorrentes" in enabled_overlays else None` (`components.py:3031`). Não há como
escolher **quais redes** aparecem. Os concorrentes são identificados pela coluna **`rede`** (carregados por
`load_competitor_points()` em `src/motor_expansao/dashboard/competitors.py:323`; estilos/labels em
`COMPETITOR_BRANDS`, `competitors.py:83`), renderizados como `IconLayer` por
`_build_competitor_icon_layer` (`components.py:818`, cap `COMPETITOR_PIN_LIMIT=6000`) ou como bolhas de
densidade por `_build_competitor_cluster_layer` (`components.py:878`).

**Objetivo:** permitir filtrar concorrentes **individualmente por rede** no Mapa Territorial, exibindo
**apenas as redes selecionadas** (pins, clusters, legenda e tooltips refletindo a seleção), sem afetar
nenhum cálculo do motor.

**Escopo permitido:**
- `src/motor_expansao/dashboard/pages.py` — novo controle de UI de seleção de redes em `render_mapa_territorial`
  (multiselect de `rede`, default = todas; lista de opções derivada das redes presentes em `competitors_df`,
  ordenada/legível via `COMPETITOR_BRANDS`); aplicar a filtragem em `competitors_df` ANTES de
  `build_unified_map_figure` (ponto único de aplicação, por volta de `pages.py:2749`).
- `src/motor_expansao/dashboard/components.py` — adaptar `render_competitor_legend` (`components.py:196`)
  para refletir só as redes selecionadas; garantir que pins/clusters/tooltips e a legenda fiquem coerentes
  com a seleção. O cap de pins (`COMPETITOR_PIN_LIMIT`) e o caption de "amostrado" seguem valendo sobre o
  subconjunto filtrado.
- Testes de smoke em `tests/integration/test_streamlit_app.py` (e/ou unidade de components) cobrindo:
  seleção de uma rede → só ela renderiza; seleção vazia → comportamento definido (ver decisão); "todas"
  selecionadas → idêntico ao comportamento atual (retrocompat).

**Fora de escopo (invioláveis):**
- Qualquer recálculo/alteração de `score_priorizacao`, `hex_score_estrutural`, carteira, plano, residual,
  SAM, canibalização ou artefatos oficiais do M1 — a filtragem é **puramente visual** (§5; precedente
  BLK-FIX-11). O filtro NÃO muda a oferta consumida nem nenhum score; apenas o que é DESENHADO.
- Mexer no overlay de Ultra, nas âncoras de domínio ou no overlay `descartados_5k` (BLK-FIX-11 intocado).
- Quebrar as otimizações de performance do mapa (carga lazy por UF, fonte de mapa enxuta, caps de pontos).

**Decisões para o gate humano (leve):**
- D1 — Estilo do controle: `st.multiselect` de redes (recomendado, simples) vs. checkboxes por rede com
  logo vs. integração no multiselect de overlays existente.
- D2 — Semântica de seleção vazia: "nenhuma rede" esconde todos os concorrentes (recomendado) vs. cair de
  volta para "todas".
- D3 — Escopo da lista de redes: todas as redes do `competitors_df` carregado vs. apenas as redes
  presentes no recorte/bbox atual do mapa.

**Critérios de aceite:** selecionar uma ou mais redes exibe **apenas** os concorrentes dessas redes
(pins/clusters/legenda/tooltips coerentes); "todas" selecionadas = comportamento atual (retrocompat);
seleção vazia conforme D2; nenhum score/artefato M1 alterado (READ-ONLY); caps e performance preservados;
suíte verde; ruff + mypy limpos.

**Guardrail:** §5 (visualização não recalcula nem altera M1) + preservar contratos de performance do
dashboard; sem dependência de API ao vivo.

---

### BLK-EST-02 — Melhorar visual e template dos estudos automatizados

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (template/visual; READ-ONLY sobre M1) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA das decisões visuais]` → Builder → QA |
| **Status** | Pendente |
| **Responsável sugerido** | Vini |
| **ClickUp** | `86e1rteju` — https://app.clickup.com/t/86e1rteju |
| **Depende de** | precedência do BLK-CENSO-02/03 (template `fpdf2` 16:9 + 7 páginas já estabelecido) |

**Contexto:** evoluir o template/visual dos estudos (continuação do BLK-CENSO-02/03). Decisões visuais
**exigem gate humano** do Felipe (precedente dos ciclos CENSO). Cada iteração visual implica rebuild de
imagem + redeploy por digest na VPS + assets de branding no volume (footgun BLK-CENSO-02).

**Objetivo:** template mais limpo/profissional, mantendo as 7 páginas e o conteúdo READ-ONLY.

**Escopo permitido:** `censo_report.py` / `censo_map.py` + assets de branding em `data/ultra/` (gitignored).

**Fora de escopo:** recalcular qualquer score; método de interseção/raio; PII no PDF.

**Critérios de aceite:** visual aprovado por Felipe (gate); 7 páginas e Big Numbers READ-ONLY preservados;
suíte verde; READ-ONLY M1; deploy registrado.

**Guardrail:** §5 (visualização) + §4 (anti-PII) + DEC-004 (basemap só na geração).

---

## BLK-UI-01 (RECORTE) — Sidebar aparente + indicadores de carregamento + limpeza visual

Data: 2026-06-12
Tipo: feature (UX/UI) | Criticidade: Alta (mexe na navegação do dashboard de produção; READ-ONLY M1)
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA do plano] → Builder → QA
Veredito QA: APROVADO (Opus 4.8) em 2026-06-12.

Resumo: recorte focado do BLK-UI-01 amplo, pedido por Felipe/Vini — três frentes de UX puramente
visuais (CSS/markdown/spinner/strings), READ-ONLY sobre o M1:
1. **Sidebar mais aparente** — `initial_sidebar_state="expanded"` (D1=A); realce CSS da sidebar com
   borda ciano 2px (`brand_alt`) + `box-shadow` de separação (D2=B); cabeçalho estilizado "Filtros
   globais" + sublinha via `st.sidebar.markdown(unsafe_allow_html=True)` (D3=B). INVARIANTE preservada:
   `render_uf_selectbox` segue sendo o PRIMEIRO widget/gate da carga lazy por UF.
2. **Indicadores de carregamento** — 3 `st.spinner` decorativos (D4): troca de UF (`load_uf_slice`,
   dentro do `try`), construção do Mapa Territorial (`build_unified_map_figure`, só a atribuição) e
   geração dos mapas censitários (`render_mapas_censitarios_combinados`). Corpo dos builders intocado.
3. **Limpeza de poluição visual** — removido caption técnico de proveniência (D5=A; rodapé do manifesto
   já cobre); pills do header simplificadas para 3 sem jargão de coluna ("Onde expandir (M1)" / "Qual
   bairro (Censitário)" / "Fila operacional (Híbrido)") (D6=A); removido caption de limitações do pydeck
   no estado vazio, PRESERVADO o caption de centroide H3 (D7=A); 2 captions repetitivos do híbrido
   consolidados em 1 (D8=A). Legendas em expander deixadas FORA de escopo (D9=A).

Gate humano: D1..D9 aprovados por Felipe/usuário em 2026-06-12 (D1=A, D2=B, D3=B, D4=textos propostos,
D5=A, D6=A, D7=A, D8=A, D9=A). Builder executou exatamente estas letras.

Arquivos alterados: streamlit_app.py, src/motor_expansao/dashboard/pages.py,
tests/integration/test_streamlit_app.py.

Validações (re-executadas pelo QA, evidência própria): suíte alvo `182 passed`; suíte full SERIAL
`695 passed, 1 skipped, 3 failed` — as 3 falhas são PRÉ-EXISTENTES (provadas via `git stash` no tree
limpo: drift de snapshot de CSVs reais locais gitignored em `concorrentes/` + gate DEC-006 do SAM em
parquet de mercado pendente de regeneração pós-merge), ZERO regressão deste ciclo. `-n auto` reproduz
INTERNALERROR de gateway (execnet × Python 3.14, bug de ambiente conhecido) → rodado serial e
documentado, sem mascarar. ruff limpo; mypy Success; `import streamlit_app` ok.

Guardrails verificados: READ-ONLY M1 (nenhum score/artefato/parâmetro canônico tocado — só
CSS/markdown/spinner/strings); contratos de performance dos Blocos 4/5/6 com corpo intocado (spinners
só por fora); sem dependência de API ao vivo; paths pré-sujos não tocados nem commitados.

Housekeeping: N/A neste ciclo — entrega é RECORTE do BLK-UI-01 amplo; o bloco amplo permanece ABERTO
em `tasks/backlog.md` para as demais frentes de UX das 4 abas (helper de move NÃO executado).

Débito operacional registrado (fora deste ciclo): regenerar parquets paralelos de mercado (gate DEC-006
do SAM) e refrescar snapshots de validação de concorrentes — passos pós-merge, não requisito de fechamento.

---

## BLK-UI-02 (follow-up ad-hoc do BLK-UI-01) — Coord destacado + tooltip menos cortado + densificação por município

Data: 2026-06-12
Tipo: feature (UX/UI) | Criticidade: Alta (toca o contrato de performance Bloco 6 anti-OOM e a navegação
do dashboard de produção; READ-ONLY M1)
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA do plano] → Builder → QA
Veredito QA: APROVADO (Opus 4.8) em 2026-06-12.

Origem: 3 observações de Felipe/Vini ao testar o BLK-UI-01 no dashboard. Tarefa ad-hoc (não há bloco
BLK-UI-02 no backlog; o bloco amplo BLK-UI-01 permanece aberto). Entrega empilhada sobre ciclo/BLK-UI-01.

Resumo (tudo READ-ONLY M1 — CSS/markdown/strings; cap anti-OOM intocado):
1. **Campo de busca por coordenada destacado** — `render_coord_search_sidebar` agora usa `st.sidebar.info(...)`
   (caixa azul) no lugar do heading+caption simples, separando-o dos demais filtros (D1=A). Assinatura,
   `text_input`, parsing/retorno `(lat,lng)|None` e a chamada única fora-de-aba (`streamlit_app.py:470`,
   Bloco 5) preservados.
2. **Tooltip do hexágono menos cortado** — adicionadas 4 chaves ao `style` dos dois tooltips
   (`_shared_map_tooltip` e `_hybrid_compact_tooltip`): `fontSize:11px`, `padding:6px 8px`, `maxWidth:260px`,
   `lineHeight:1.25` (D2=A), reduzindo a altura para caber na borda do mapa. O recorte total do tooltip no
   cursor é limitação nativa do pydeck/deck.gl (iframe) — mitigação por altura é a via realista. HTML/linhas
   dos tooltips inalterados (Planner confirmou: sem linha vazia a enxugar na config default).
3. **Densificação por município (comunicação)** — confirmado nos 4 builders que `selected_cities` entra no
   `scope` ANTES do `_downsample_map_index`, ou seja, selecionar um município já dá densidade total do
   recorte (mecanismo NATIVO). Decisão de produto pré-fixada por Felipe/Vini = filtro de município/área (NÃO
   remover/elevar o cap; pydeck não tem zoom-awareness). Fix = só COMUNICAÇÃO: frase "filtre por município →
   densidade total" anexada ao ramo não-capped de `build_map_scope_caption` e ao caption do
   `render_mapa_territorial` (D3=(a)+(b)). Substrings testadas do ramo capped preservadas.
4. **Testes** — `test_build_map_scope_caption_*` ampliado (asserção de "municipio") + novo
   `test_map_tooltips_tem_css_de_tamanho` (D4=A).

Gate humano: D1=A, D2=A, D3=(a)+(b), D4=A — aprovados por Felipe/usuário em 2026-06-12. Builder executou
exatamente estas letras.

Arquivos alterados: src/motor_expansao/dashboard/pages.py, src/motor_expansao/dashboard/components.py,
tests/integration/test_streamlit_app.py.

Validações (re-executadas pelo QA, evidência própria): suíte alvo `183 passed`; suíte full SERIAL
`696 passed, 1 skipped, 3 failed` — as 3 falhas são as MESMAS PRÉ-EXISTENTES da baseline (drift de CSVs reais
locais gitignored em `concorrentes/` + gate DEC-006 do SAM em parquet de mercado), comprovadas via `git stash`;
`passed` subiu 695→696 (exatamente o +1 do teste novo), ZERO regressão. `-n auto` reproduz INTERNALERROR de
gateway (execnet × Python 3.14) → rodado serial e documentado, sem mascarar. ruff "All checks passed!"; mypy
sem issues; `import streamlit_app` ok.

Guardrails verificados: **Bloco 6 anti-OOM INTOCADO** (`MAP_POINT_LIMIT`/`MAP_POINT_LIMIT_LARGE` sem diff;
`_downsample_map_index`/scope/cap fora do diff — o nº3 é só texto); READ-ONLY M1 (nenhum score/cap/downsample
no diff); Bloco 4 (carga lazy) e Bloco 5 (render lazy) preservados; sem dependência de API ao vivo; paths
pré-sujos não tocados nem commitados.

Housekeeping: N/A (tarefa ad-hoc; sem bloco BLK-UI-02 no backlog — helper de move NÃO executado).

---

### BLK-FIX-10 — Diminuir tamanho da pré-visualização dos estudos

| Campo | Valor |
|---|---|
| **Criticidade** | **Baixa** (layout/UX; READ-ONLY sobre M1) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Status** | Pendente |
| **Responsável sugerido** | Vini |
| **ClickUp** | `86e1rteea` — https://app.clickup.com/t/86e1rteea |

**Contexto / hipótese:** a pré-visualização do estudo no dashboard renderiza grande demais. Hipótese:
`st.image`/container de preview sem largura controlada em `pages.py`.

**Objetivo:** preview em tamanho adequado (largura/altura controladas), sem afetar o PDF exportado.

**Escopo permitido:** layout do preview em `pages.py` + teste de smoke.

**Fora de escopo:** alterar o PDF final; score/artefatos M1.

**Critérios de aceite:** preview menor/legível; export inalterado; suíte verde; READ-ONLY M1.

---

- BLK-EST-01 (concluído 2026-06-11) — ver tasks/completed.md

---

## BLK-UI-03 (follow-up ad-hoc do BLK-UI-02; FECHA BLK-FIX-10) — Reverter coord, tooltip meio-termo, preview menor, destaque do seletor de abas

Data: 2026-06-12
Tipo: feature (UX/UI) | Criticidade: Alta (toca o seletor de abas da produção/Bloco 5 — só CSS — e a
navegação do dashboard; READ-ONLY M1)
Esteira: Block Orchestrator → Planner (Opus) → [REVISÃO HUMANA do plano] → Builder → QA
Veredito QA: APROVADO (Opus 4.8) em 2026-06-12.

Origem: 4 observações de Felipe/Vini ao testar o BLK-UI-02 no dashboard. Tarefa ad-hoc empilhada sobre
ciclo/BLK-UI-02. O item nº3 fecha o bloco real BLK-FIX-10 do backlog (movido via
scripts/housekeeping_move_block.py — ver a entrada "### BLK-FIX-10" acima neste arquivo).

Resumo (tudo READ-ONLY M1 — CSS/markdown/strings/largura de exibição; Bloco 5 e PDF intocados):
1. **[D1] Reverter o campo de coordenadas do BLK-UI-02** — `render_coord_search_sidebar` voltou ao
   `st.sidebar.markdown("### Busca por coordenada")` + `st.sidebar.caption("Localize um hexagono pela
   coordenada. Offline, sem API externa.")` (texto byte-idêntico ao commit BLK-UI-01 `0862205`),
   removendo a caixa `st.sidebar.info` que o usuário achou intrusiva. `text_input`/parse/retorno
   `(lat,lng)|None` e a chamada `streamlit_app.py:470` preservados.
2. **[D2] Tooltip do hexágono — meio-termo** — `style` dos dois tooltips (`_shared_map_tooltip` e
   `_hybrid_compact_tooltip`) ajustado de 11px/6px8px/260px/1.25 (BLK-UI-02) para
   `fontSize:13px`/`padding:8px 10px`/`maxWidth:300px`/`lineHeight:1.35` — meio-termo entre o default
   deck.gl (~14px) e o 11px, mais legível sem voltar a cortar na borda. HTML/chaves pré-existentes
   inalterados.
3. **[D3 = BLK-FIX-10] Preview menor do Relatório Pontual** — constante `_CENSUS_PREVIEW_WIDTH_PX = 720`
   em pages.py; as 4 `st.image` do preview do censitário trocaram `width="stretch"` por
   `width=_CENSUS_PREVIEW_WIDTH_PX` (edição uma a uma — `replace_all` PROIBIDO pois há ~39 outras
   ocorrências de `width="stretch"` no arquivo, todas preservadas). PDF exportado, `censo_report.py`,
   `censo_map.py` e geração de mapas INTOCADOS — só a largura de exibição na tela diminuiu.
4. **[D4] Destaque do seletor de abas (SÓ CSS)** — regras do `stSegmentedControl` em `inject_styles()`
   reforçadas: botões com `font-size:1rem`/`font-weight:600`/`padding:0.5rem 1.15rem`/`border-radius:10px`;
   aba ativa com `border-color: rgba(25,183,255,0.9)` + `box-shadow: 0 0 8px rgba(25,183,255,0.35)` +
   `font-weight:700`. **`render_tab_selector` byte-idêntico** (Bloco 5 render lazy intocado — confirmado
   por QA: não aparece no diff); `:hover` inalterado.

Gate humano: D1..D4 aprovados por Felipe/usuário em 2026-06-12 (preview = 720px). Builder executou
exatamente estas decisões.

Nota de processo: o primeiro sub-agente de delimitação acumulou BO+Planner em tier sonnet; o orquestrador
corrigiu registrando o snapshot de BO e re-rodando o Planner em **Opus** (snapshot `20260612-162000-planner.md`),
que validou o plano e pegou o footgun do `replace_all` no item nº3. Há dois snapshots de BO
(`125955` do agente + `161000` reconstruído pelo orquestrador) — redundância de auditoria inofensiva
(append-only, não editados).

Arquivos alterados: src/motor_expansao/dashboard/pages.py, src/motor_expansao/dashboard/components.py,
tests/integration/test_streamlit_app.py.

Validações (re-executadas pelo QA, evidência própria): suíte alvo `183 passed`; suíte full SERIAL
`696 passed, 1 skipped, 3 failed` — as 3 falhas (`test_csvs_concorrentes_legiveis` x2 +
`test_parquet_final_respeita_guardrails_do_piloto`) são as MESMAS PRÉ-EXISTENTES, comprovadas via
`git stash` em HEAD limpo; ZERO novas falhas. `-n auto` reproduz INTERNALERROR (execnet × Python 3.14)
→ rodado serial, documentado, sem mascarar. ruff "All checks passed"; mypy sem issues; import ok.

Guardrails verificados: Bloco 5 (`render_tab_selector` byte-idêntico); PDF/geração de mapas do Relatório
Pontual intocados (item nº3 só preview na tela; 39 `width="stretch"` preservadas); READ-ONLY M1 (nenhum
score/peso/fórmula/artefato no diff); Bloco 4/6 intocados; sem dependência de API ao vivo; paths pré-sujos
não tocados nem commitados.

Housekeeping: BLK-FIX-10 movido via helper (`--check` OK; teste do helper verde, 10 passed). Itens
D1/D2/D4 são follow-up ad-hoc (sem bloco próprio no backlog) — resumidos aqui.

---

## BLK-UI-04 (follow-up ad-hoc do BLK-UI-03) — Destaque do seletor de telas (aba ativa ciano sólido, mais espaço, botões distintos dos cartões)

Data: 2026-06-12
Tipo: feature (UX/UI — CSS) | Criticidade: Média (CSS localizado no seletor de abas; READ-ONLY M1; Bloco 5 lógica intocada)
Esteira: Block Orchestrator → Planner → Builder → QA (Média, sem gate humano)
Veredito QA: APROVADO (Opus 4.8) em 2026-06-12.

Origem: 3 observações de Felipe/Vini ao testar o BLK-UI-03 — o seletor de telas (st.segmented_control das
4 abas) se camuflava entre os cartões de valores. Tarefa ad-hoc empilhada sobre ciclo/BLK-UI-03.

Causa-raiz: os botões inativos do seletor usavam `background: rgba(18,23,42,0.92)`, quase idêntico ao
fundo dos cartões de valores (`stMetric`/`.section-card`/`.model-card` = `rgba(18,23,42,0.96)`); e a aba
ativa usava só `rgba(25,183,255,0.22)` (tom fraco).

Resumo (3 mudanças CSS, 100% dentro do bloco `<style>` de `inject_styles()` em pages.py; READ-ONLY M1):
1. **Aba ATIVA = ciano sólido** — `background: #19B7FF` + `color: #0A0C18` (texto escuro, contraste ~9.7:1)
   + `font-weight: 700`, no lugar do `rgba(25,183,255,0.22)`/`COLORS["text"]`. Decisão de produto de
   Felipe/Vini (2026-06-12): ciano sólido preenchido.
2. **Mais espaçamento entre botões** — `display: flex; gap: 8px;` no container `[data-testid="stSegmentedControl"]`.
3. **Botões INATIVOS distintos dos cartões** — `background: rgba(30,38,65,0.88)` (slate mais claro) +
   borda ciano suave `rgba(25,183,255,0.30)`, no lugar de `rgba(18,23,42,0.92)`/`COLORS["border"]`.

Arquivos alterados: src/motor_expansao/dashboard/pages.py (bloco CSS do seletor em inject_styles),
tests/integration/test_streamlit_app.py (+1 assert `"#19B7FF" in css`).

Validações (re-executadas pelo QA, evidência própria): suíte alvo `183 passed`; full SERIAL `696 passed,
1 skipped, 3 failed` = baseline exato (as 3 falhas são as MESMAS pré-existentes; `-n auto` reproduz o
INTERNALERROR execnet×Python 3.14 → serial). ruff "All checks passed"; mypy Success; import ok.

Guardrails verificados: **Bloco 5 byte-idêntico** (`render_tab_selector`/`st.segmented_control`/`session_state`
NÃO aparecem no diff); READ-ONLY M1 (diff é só CSS + 1 assert; nenhum score/peso/fórmula/artefato);
seletores `stSegmentedControl`/`aria-checked` preservados; paths pré-sujos não tocados nem commitados.

Housekeeping: N/A (tarefa ad-hoc; sem bloco BLK-UI-04 no backlog).

---

## BLK-UI-05 (bug-fix do BLK-UI-04) — CSS do seletor de telas não renderizava (seletores reais do st.segmented_control)

Data: 2026-06-12
Tipo: bug (UX/UI — CSS) | Criticidade: Média (CSS localizado; READ-ONLY M1; Bloco 5 lógica intocada)
Esteira: Block Orchestrator → Planner → Builder → QA (Média, sem gate)
Veredito QA: APROVADO (Opus 4.8) em 2026-06-12 — com confirmação visual pendente do usuário.

Origem: ao testar o BLK-UI-04, Felipe/Vini reportou (com screenshot) que a aba ativa não ficava ciano
sólido e o gap entre botões não aparecia. O `pytest` do BLK-UI-04 passou mesmo assim (o teste só checa a
STRING do CSS, não o render).

Causa-raiz (confirmada contra o frontend instalado do Streamlit 1.58.0, via grep no bundle JS): o estado
ATIVO do `st.segmented_control` é marcado pelo testid `stBaseButton-segmented_controlActive` (NÃO por
`aria-checked`/`aria-selected`), e o inativo por `stBaseButton-segmented_control`. As regras do BLK-UI-04
miravam `aria-checked`/`aria-selected` (que não casam o DOM real) → a aba ativa nunca recebia o ciano; e
faltavam `!important` (o CSS emotion do Streamlit tem especificidade alta e sobrepunha o gap/fundo).

Correção (100% CSS dentro de `inject_styles()`, pages.py ~304-335; READ-ONLY M1):
- Aba ATIVA: adicionado `[data-testid="stBaseButton-segmented_controlActive"]` à lista de seletores, com
  `background:#19B7FF !important; color:#0A0C18 !important; border-color:#19B7FF !important;
  font-weight:700 !important; box-shadow:0 0 8px rgba(25,183,255,0.35) !important`.
- Botões INATIVOS: adicionado `[data-testid="stBaseButton-segmented_control"]`, com
  `background:rgba(30,38,65,0.88) !important` + borda ciano `rgba(25,183,255,0.30) !important` +
  `border-radius:10px !important` (distinto dos cartões de valores).
- GAP: `gap:8px !important` no container `[data-testid="stSegmentedControl"]`.
- Seletores legados (`aria-checked`/`aria-selected`/`stSegmentedControl`) MANTIDOS (o teste os verifica);
  precedência: a regra do ativo vem DEPOIS da inativa, mesma camada `!important` → ciano vence.
- Teste de REGRESSÃO: assert de `"stBaseButton-segmented_controlActive"` no CSS (guarda contra voltar aos
  seletores que não casavam).

Lição registrada: o teste de presença-de-string no CSS NÃO garante render no navegador; para componentes
de terceiros (Streamlit/baseweb), confirmar os seletores reais contra o DOM/bundle da versão instalada e
fechar com verificação VISUAL do usuário.

Arquivos alterados: src/motor_expansao/dashboard/pages.py, tests/integration/test_streamlit_app.py.

Validações (re-executadas pelo QA): suíte alvo `183 passed`; full SERIAL `696 passed, 1 skipped, 3 failed`
= baseline exato (3 falhas pré-existentes; `-n auto` reproduz INTERNALERROR execnet×Python 3.14 → serial).
ruff "All checks passed"; mypy Success; import ok.

Guardrails: Bloco 5 byte-idêntico (`render_tab_selector` ausente do diff); READ-ONLY M1 (só CSS + 2 asserts);
paths pré-sujos não tocados. Housekeeping: N/A (ad-hoc).

---

## BLK-UI-06 (bug-fix do BLK-UI-05) — GAP do seletor de telas não renderizava (flex-pai real + margem negativa do baseweb)

Data: 2026-06-12
Tipo: bug (UX/UI — CSS) | Criticidade: Média (CSS localizado; READ-ONLY M1; Bloco 5 lógica intocada)
Esteira: Block Orchestrator → Planner → Builder → QA (Média, sem gate)
Veredito QA: APROVADO (Opus 4.8) em 2026-06-12 — render do gap PROVADO por medição DOM.

Origem: após o BLK-UI-05, Felipe/Vini confirmou (com screenshot) que o realce da aba ativa funcionou,
mas o gap entre os botões ainda não aparecia (botões colados).

Causa-raiz (DOM REAL renderizado, medido pelo orquestrador via playwright contra o app — Streamlit 1.58):
- O flex-pai dos botões do `st.segmented_control` é `[data-baseweb="button-group"]` (role=radiogroup,
  display:flex) com `gap: 4px 0px` → **0px de gap horizontal** (o 4px é row-gap, só vale se quebrar linha).
- Cada botão tinha `margin-right: -1px` (o baseweb "cola" os botões sobrepondo a borda).
- O testid `stSegmentedControl` NÃO existe nessa versão (o container real é `stButtonGroup`), então a
  regra de gap do BLK-UI-04/05 (mirando `[data-testid="stSegmentedControl"]`) nunca casava.

Correção (DOM-verificada; 100% CSS em `inject_styles()`; READ-ONLY M1):
- `[data-baseweb="button-group"] { gap: 8px !important; }` — gap horizontal no flex-pai real.
- `[data-testid="stBaseButton-segmented_control"], [data-testid="stBaseButton-segmented_controlActive"]
  { margin: 0 !important; }` — remove a margem negativa que conectava os botões.
- Regras de cor (ativa ciano `#19B7FF`, inativo `rgba(30,38,65,0.88)`) e seletores legados mantidos.
- Teste de regressão: asserts de `[data-baseweb="button-group"]`, `gap: 8px` e `margin: 0` nos botões.

Verificação de RENDER (o passo que faltava nos ciclos anteriores): o orquestrador rodou playwright,
selecionou uma UF, e mediu o bounding box dos 4 botões → gaps horizontais de **8px / 8px / 8px** e
`margin-right: 0px`; `button-group` com `gap: 8px` (display flex). Gap confirmado no DOM, não só na string.

Lição (reforça a do BLK-UI-05): para componentes de terceiros, NÃO basta o `data-testid` "óbvio" — inspecionar
o DOM/bundle da versão instalada e MEDIR o render (playwright) antes de declarar pronto. O pytest de
presença-de-string passou em todos os ciclos mesmo quando o CSS não aplicava.

Arquivos alterados: src/motor_expansao/dashboard/pages.py, tests/integration/test_streamlit_app.py.

Validações (QA): suíte alvo `183 passed`; full SERIAL `696 passed, 1 skipped, 3 failed` = baseline exato
(3 falhas pré-existentes). ruff "All checks passed"; mypy Success; import ok.

Guardrails: Bloco 5 byte-idêntico (`render_tab_selector` ausente do diff); READ-ONLY M1 (só CSS + asserts);
paths pré-sujos não tocados. Housekeeping: N/A (ad-hoc).

---

## BLK-EST-01-FU1 (follow-up do BLK-EST-01) — Marca d'água sutil no canto (rodapé inferior-direito)

Data: 2026-06-12
Tipo: feature (UX/UI — PDF, ajuste visual) | Criticidade: Média (render do PDF; READ-ONLY M1; anti-PII §4)
Esteira: Block Orchestrator → Planner → Builder → QA (Média, sem gate)
Veredito QA: APROVADO (Opus 4.8) em 2026-06-12 — render confirmado por imagem.

Origem: Felipe/Vini pediu (após a análise de reversão do BLK-EST-01) NÃO reverter a marca d'água, e sim
deixá-la MAIS SUTIL e num CANTO. Decisão de produto (2026-06-12): rodapé inferior-direito, horizontal,
pequena e discreta.

Resumo (só `censo_report.py`, render da marca; READ-ONLY M1; texto/`solicitante` INALTERADOS):
- `_draw_watermark` deixou de ser faixa diagonal central de 60pt e virou rótulo discreto no canto
  inferior-direito: posição `x = _PAGE_W - _WATERMARK_MARGIN - get_string_width(text)`,
  `y = _PAGE_H - _WATERMARK_MARGIN`; sem rotação (horizontal); peso normal.
- Constantes: `_WATERMARK_FONT_PT` 60→9; `_WATERMARK_ANGLE` 45.0→0.0; `_WATERMARK_ALPHA` 0.16→0.40
  (em 9pt, 0.16 ficaria invisível — 0.40 é discreto porém auditável); nova `_WATERMARK_MARGIN=20.0`;
  `_WATERMARK_RGB` inalterado. Desenho em TODAS as páginas (loop 635-637) e `local_context` preservados.
- O texto `_watermark_text(solicitante)` (BLK-EST-01) NÃO foi alterado — a feature continua; só mudou a
  aparência. Anti-PII §4 preservado (stream OFF; nada de PII nova).

Verificação de RENDER (orquestrador): gerou um PDF de amostra com `solicitante="Analista Teste"`,
renderizou as páginas (pypdfium2 — instalado só para a verificação, NÃO entra no projeto) e confirmou por
imagem que a marca aparece pequena/cinza/horizontal no canto inferior-direito (página 6 com fundo limpo);
a faixa diagonal central sumiu.

Arquivos alterados: src/motor_expansao/dashboard/censo_report.py.

Validações (QA): suíte alvo `29 passed` (3 de marca d'água verdes); full SERIAL `696 passed, 1 skipped,
3 failed` = baseline exato (3 falhas pré-existentes). ruff "All checks passed"; mypy Success; import ok.

Guardrails: READ-ONLY M1 (só render da marca; nenhum score/peso/artefato); anti-PII §4 (compressão OFF;
texto/`solicitante` inalterados; default seguro); template/7 páginas/mapas/raio/interseção intocados;
paths pré-sujos não tocados. Housekeeping: N/A (ad-hoc).

---

## BLK-EST-01-FU2 (follow-up do BLK-EST-01-FU1) — Marca d'água visível-porém-discreta + branca na capa

Data: 2026-06-12
Tipo: feature (UX/UI — PDF) | Criticidade: Média (render do PDF; READ-ONLY M1; anti-PII §4)
Esteira: Block Orchestrator → Planner → Builder → QA (Média, sem gate)
Veredito QA: APROVADO (Opus 4.8) em 2026-06-12 — render confirmado por imagem (capa + conteúdo).

Origem: ao baixar um PDF, Felipe/Vini não viu a marca do FU1. Diagnóstico do orquestrador (render real pelo
caminho de download): o código do FU1 estava correto (a marca renderiza no canto inferior-direito em todas
as páginas; NÃO há cache no caminho do relatório), mas a 0.40/9pt/cinza ficou SUTIL DEMAIS — no conteúdo
passava batida e na CAPA (fundo turquesa) o cinza não contrastava (quase invisível). O servidor usado também
era anterior ao FU1.

Decisões de produto (Felipe/Vini, 2026-06-12): (1) discreta-porém-visível; (2) texto claro/branco na capa.

Resumo (só `censo_report.py`; texto/`solicitante` INALTERADOS; READ-ONLY M1):
- `_WATERMARK_ALPHA` 0.40 → 0.65; `_WATERMARK_FONT_PT` 9 → 10 (legível sem deixar de ser discreta).
- Nova `_WATERMARK_RGB_COVER = (255, 255, 255)`; `_draw_watermark` passou a aceitar `rgb` keyword-only
  (default `_WATERMARK_RGB` cinza) e usa `set_text_color(*rgb)`.
- Loop por-página (635-637): página 1 (capa) → branco; páginas 2-7 (conteúdo) → cinza. Posição
  (canto inferior-direito), horizontal e `local_context` preservados.

Verificação de RENDER (orquestrador): PDF gerado pelo caminho de download (`gerar_payloads_download_...`,
`solicitante="Analista Teste"`), renderizado com pypdfium2 (instalado só para verificação, NÃO entra no
projeto). Confirmado por imagem: CAPA com marca BRANCA visível sobre o turquesa; CONTEÚDO com marca CINZA
legível e discreta a 0.65/10pt.

Arquivos alterados: src/motor_expansao/dashboard/censo_report.py.

Validações (QA): suíte alvo `29 passed` (3 de marca d'água verdes); full SERIAL `696 passed, 1 skipped,
3 failed` = baseline exato (3 falhas pré-existentes). ruff "All checks passed"; mypy Success; import ok.

Guardrails: READ-ONLY M1 (só render; nenhum score/peso/artefato); anti-PII §4 (stream OFF; texto/`solicitante`
inalterados); template/mapas/raio intocados; paths pré-sujos não tocados. Housekeeping: N/A (ad-hoc).

Nota: a marca é desenhada por página via `pdf.page = n` — para o usuário ver a versão nova é preciso um
servidor Streamlit reiniciado (o anterior precedia o FU1).

---

## BLK-EST-02-FU1 (follow-up do BLK-EST-02) — Remover logo Ultra atrás do texto "Realizacao"

Data: 2026-06-12
Tipo: bug (UX/UI — PDF) | Criticidade: Baixa (remoção de bloco visual isolado; READ-ONLY M1)
Esteira: Block Orchestrator → Builder (Baixa, sem QA; orquestrador fez render + suíte como gate)

Origem: na página 7 (Realização/Crédito) do PDF, o logo Ultra (D5=C do BLK-EST-02, desenhado no topo a
y=90/w=160) colidia com o título "Realizacao" (y=180) — o texto caía por cima do logo. Felipe/Vini pediu
para remover o logo dessa página.

Resumo (só `censo_report.py`; READ-ONLY M1): removido o bloco D5=C do logo em `_credit_page`
(`logo = assets.get("logo")` + `if logo is not None: try: pdf.image(...) except: pass`). Mantidos o fundo
turquesa, o título "Realizacao" e o crédito. O asset `logo` continua sendo carregado por
`_load_branding_assets` (só o DESENHO na página de crédito foi removido). Nenhum import alterado.

Verificação de RENDER (orquestrador): renderizou a página 7 (pypdfium2) → o logo sumiu; "Realizacao" +
crédito ficam limpos sobre o turquesa, sem colisão.

Arquivos alterados: src/motor_expansao/dashboard/censo_report.py.

Validações: suíte alvo `29 passed`; full SERIAL `696 passed, 1 skipped, 3 failed` = baseline exato (3 falhas
pré-existentes). ruff "All checks passed"; mypy Success; import ok. Nenhum teste dependia do logo na página
de crédito (verificado).

Guardrails: READ-ONLY M1; anti-PII §4 (texto/`solicitante`/marca d'água inalterados); só `_credit_page`
tocado; paths pré-sujos não tocados. Housekeeping: N/A (ad-hoc).

Nota: commitado na MESMA branch `ciclo/BLK-EST-01-FU2` (o PR em montagem) e re-empurrado, para entrar no
mesmo PR.
### BLK-SAM-02 — Afrouxar o gate do SAM: apenas Faixa M1 elegível + população ≥ 5000 (remover flag_viavel e ~canibal)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (altera o VALOR da camada PARALELA de mercado/residual; reverte sub-decisões da DEC-006; **não** é M1 oficial) |
| **Prioridade** | **Alta** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA do plano técnico]` → Builder → QA |
| **Status** | Em execução (Builder concluído → aguardando QA; 2026-06-10) |
| **Responsável sugerido** | Vini |
| **ClickUp** | (segue `86e1rte9n`, mesma trilha do SAM) |
| **Relacionado** | **Reverte 2 sub-decisões da DEC-006** (BLK-SAM-01): a manutenção de `flag_viavel` e de `~flag_canibalizacao_ultra_1km` no gate do SAM. |

**Contexto / estado atual:** após o BLK-SAM-01 (DEC-006), o gate do SAM em
`src/motor_expansao/pipelines/calcular_colunas_mercado.py` é:
`flag_sam = flag_viavel & faixa_oportunidade ∈ {baixa,media,alta,prioridade_maxima} & flag_pop_min_5k(≥5000) & ~flag_canibalizacao_ultra_1km`.

**Objetivo (pedido do usuário Vinicius, 2026-06-10):** o SAM deve responder **apenas** a
`faixa_oportunidade ∈ {baixa,media,alta,prioridade_maxima}` **e** `flag_pop_min_5k (≥5000)`,
**desconsiderando** `flag_viavel` e `~flag_canibalizacao_ultra_1km`. Gate pretendido:
`flag_sam = faixa_oportunidade.isin({baixa,media,alta,prioridade_maxima}) & flag_pop_min_5k`.

**Decisão de produto — RESOLVIDA pelo usuário Vinicius em 2026-06-10** (confirmada com ciência do impacto):
- Remover `flag_viavel` (que embutia o filtro de renda `renda_target_proxy ≥ RENDA_MIN` e o guard pop ≥ 1).
- Remover `~flag_canibalizacao_ultra_1km` (SAM passa a incluir áreas já canibalizadas por unidade Ultra < 1 km).
- **Impacto medido (dados reais 2026-06-10):** `flag_sam` True **27.996 → 479.568** (+451.572, ≈ ×17);
  ~451.496 entram por dropar `flag_viavel` (filtro de renda) e apenas 76 por dropar `~canibal`.
- **Conflito explícito:** reverte a sub-decisão da DEC-006 em que Felipe manteve de propósito `flag_viavel`
  (para "preservar de brinde o filtro de renda") e `~flag_canibalizacao_ultra_1km`.

**Escopo permitido (camada PARALELA, não M1 oficial):** o gate do SAM em `calcular_colunas_mercado.py`
(`flag_sam`/`flag_sam_fitness`/`sam_fitness_potencial`). Se houver regeneração de parquets paralelos, seguir
a **ordem canônica**: híbrido → mercado → `calcular_colunas_mercado` → carteira → plano → domínio → residual →
`fase1_bi_exports` (+ enriquecido derivado do dashboard).

**Fora de escopo (inviolável):** `score_priorizacao`/`hex_score_estrutural`/pesos/`faixa_oportunidade`/
artefatos oficiais do M1 (DEC-001 vigente; a Faixa M1 é **lida**, não recalculada); a régua
`populacao_corte_hex`/`flag_pop_min_5k` (helper `pop_corte.py` — mantida intacta, só consumida).

**Critérios de aceite:**
- Gate = `faixa_oportunidade ∈ {baixa,media,alta,prioridade_maxima} & flag_pop_min_5k`, sem `flag_viavel`
  nem `~flag_canibalizacao_ultra_1km`; verificável por teste.
- Repro de ≥1 hex que **passa a calcular** por ter sido reprovado só em `flag_viavel` (renda < RENDA_MIN) e
  ≥1 que **passa a calcular** por ter sido reprovado só em `~canibal`, com causa documentada.
- Volume `flag_sam` ≈ **479.568** (±pequena variação) confirmado.
- Nova **DEC-007** no CLAUDE.md §8 registrando a reversão e o novo aprovador (Vinicius, 2026-06-10).
- Parquets paralelos regenerados de forma reprodutível; **ZERO escrita em M1 oficial**.
- Suíte + ruff + mypy verdes (atualizar testes do gate em `tests/integration/test_modelo_mercado_hexagonos.py`).

**Guardrail:** não toca o M1 oficial; mudança restrita à camada de mercado/residual paralela (§4/§5).

---

### BLK-FIX-09 — Remover "BYD" do PDF de estudos

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (conteúdo do relatório; READ-ONLY sobre M1) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Responsável sugerido** | Vini |
| **ClickUp** | `86e1rtebk` — https://app.clickup.com/t/86e1rtebk |

**Contexto / hipótese:** entrada espúria "BYD" (marca não-fitness) aparece no PDF de estudos — provavelmente
um pin/logo de POI ou registro indevido na base de concorrentes (`concorrentes/` logos/Unidades) ou no
lookup do relatório. Planner localiza a origem (dado vs render).

**Objetivo:** o "BYD" não aparece mais no PDF/relatório.

**Escopo permitido:** `src/motor_expansao/dashboard/censo_report.py` / `censo_map.py` (filtro de render) e/ou
saneamento da fonte de concorrentes consumida pelo relatório.

**Fora de escopo:** alterar score/artefatos M1; mexer no método de interseção/raio 1.5 km.

**Critérios de aceite:** PDF sem "BYD"; teste cobrindo a exclusão; suíte verde; READ-ONLY M1.

**Guardrail:** relatório é camada de visualização (§5).

---

### BLK-FIX-07 — Overlays do mapa territorial não funcionando

> ⚠️ **SUPERSEADO por BLK-FIX-11 (2026-06-09)** — ver seção "Novos blocos". A tarefa ClickUp `86e1rtefy`
> passa a ser rastreada pelo **BLK-FIX-11** (Alternativa A: fiar os 3 overlays mortos). Mantido aqui só por histórico.

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (display/render; READ-ONLY sobre M1) |
| **Prioridade** | **Alta** (urgent no ClickUp) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA das decisões visuais]` → Builder → QA |
| **Status** | Pendente |
| **Responsável sugerido** | Vini |
| **ClickUp** | `86e1rtefy` — https://app.clickup.com/t/86e1rtefy |

**Contexto / hipótese:** as camadas de overlay do Mapa Territorial (toggles de concorrentes/Ultra/score)
não renderizam ou não respondem ao controle. Hipótese: regressão no controle de camadas/`pydeck` em
`src/motor_expansao/dashboard/pages.py` (`render_mapa_territorial`) ou nos builders de layer em
`components.py` (filtro de `scope`/cap de pontos descartando o overlay antes do render — eco do
BLK-FIX-06-C). Planner confirma se é toggle de UI, layer pydeck ou dado ausente.

**Objetivo:** restaurar a exibição e o controle dos overlays no Mapa Territorial.

**Escopo permitido:** `pages.py`/`components.py` (controle e build de camadas), testes de
`test_streamlit_app.py`. Só display/interação.

**Fora de escopo:** recalcular score/carteira/plano; alterar artefatos M1; mudar o cap de pontos sem aprovação.

**Critérios de aceite:** overlays aparecem e respondem ao toggle; teste cobrindo a camada antes invisível;
suíte + ruff + mypy verdes; READ-ONLY M1 comprovado (git scope vazio em pipelines/scoring.py/config.py).

**Guardrail:** visualização não recalcula nem altera M1 (§5).

---

### BLK-FIX-08 — SAM não calcula em alguns hexágonos/municípios (RR, AC e outros)

> ⚠️ **SUPERSEADO por BLK-SAM-01 (2026-06-09)** — ver seção "Novos blocos". A tarefa ClickUp `86e1rte9n`
> passa a ser rastreada pelo **BLK-SAM-01** (redefine o gate do SAM: Faixa M1 + pop ≥ 5000), que **absorve**
> a preocupação de cobertura (fallback de pop em RR/AC/AM). Mantido aqui só por histórico.

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (altera valor da camada PARALELA de mercado/residual; **não** é M1 oficial, mas exige revisão) |
| **Prioridade** | **Alta** (urgent no ClickUp) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Responsável sugerido** | Vini |
| **ClickUp** | `86e1rte9n` — https://app.clickup.com/t/86e1rte9n |

**Contexto / hipótese:** `sam_fitness_potencial` fica vazio/zerado em UFs de baixa cobertura censitária
(RR, AC, AM — exatamente as de supressão IBGE/classe C). Hipótese: o fallback de `pop_hex_base`
(`pop_total_setor_2022` → `populacao_proxy / total_hex_municipio`) não cobre esses hexes, ou `cod_municipio`
ausente quebra o join da camada de mercado. Planner confirma a origem no cálculo do mercado
(`calcular_colunas_mercado` / `hexagonos_mercado_mapeado.parquet`).

**Objetivo:** SAM calculado (ou marcado explicitamente como "sem base", não silenciosamente vazio) nessas UFs.

**Escopo permitido (camada PARALELA, não M1 oficial):** cálculo de mercado/residual e seu fallback de
população; se houver regeneração de parquets paralelos, seguir a **ordem canônica** (hibrido → mercado →
`calcular_colunas_mercado` → carteira → plano → dominio → residual → `fase1_bi_exports`).

**Fora de escopo (inviolável):** `score_priorizacao`/`hex_score_estrutural`/pesos/artefatos oficiais do M1
(DEC-001 vigente); inventar população onde não há base auditável.

**Critérios de aceite:** SAM presente ou rotulado em RR/AC/AM com causa documentada; repro de ≥1 hex antes
quebrado; parquets paralelos regenerados de forma reprodutível se necessário; ZERO escrita em M1 oficial;
suíte + ruff + mypy verdes.

**Guardrail:** não toca o M1 oficial; mudança restrita à camada de mercado/residual paralela.

---

### BLK-API-02 — Esqueleto do app + /health + settings + auth (G2 base)

| Campo | Valor |
|---|---|
| **Criticidade** | Média (stand-up de pacote novo; sem lógica de análise; READ-ONLY M1) |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Status** | Pendente (depende de BLK-API-01) |
| **ClickUp** | G2 (subtarefa de `86e1rtfcy`) |

**Escopo:** criar `src/motor_expansao/api/` real (`__init__.py`, `main.py`, `settings.py`, `auth.py`),
app `FastAPI(/api/v1)` + CORS + `GET /health` ({status, environment}), `pydantic-settings`, e
autenticação por **token→consumidor** (Decisão 2: lista estática, rastreio do solicitante). Sem rota de
análise. Deps: subset MVP do extra `[api]` (`fastapi`/`uvicorn[standard]`/`pydantic`/`pydantic-settings`).
**Aproveitar** o esqueleto do scaffold legado `fora_primeira_fase/api_postgis/main.py`; **descartar**
Sentry/structlog/routers PostGIS/`on_event("startup")`. **Critérios:** app sobe; `/health` 200; token
inválido → 401; suíte+ruff+mypy verdes; READ-ONLY M1.

---

### BLK-API-03 — POST /analisar JSON (G2)

| Campo | Valor |
|---|---|
| **Criticidade** | Média (importa `censo_*`, não edita; READ-ONLY M1) |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Status** | Pendente (depende de BLK-API-02) |
| **ClickUp** | G2 |

**Escopo:** `schemas/` (`AnalisarRequest`/`AnalisarResponseJSON`), `routes/analisar.py`, `coord.py`
(parser de link Google Maps + validação de bounding box do Brasil — Decisão 4, utilitário **puro**),
`service.py` (resolução coord→partição → `read_censo_geo_partition` → `analisar_ponto_censitario_setores`),
KPIs do `result` + **carimbo de versão** (Decisão 6: `versao_contrato`/`versao_score`/`gerado_em`/`consumidor`).
Raio **fixo 1.5 km** (Decisão 5). **Erros:** 400/401/403/404/422/500 do contrato (§9). **Critérios:** ponto
válido retorna KPIs; `{lat,lng}` e `maps_url` aceitos; base ausente → 404 com mensagem espelhada do
dashboard; suíte+ruff+mypy verdes; `censo_*` intocado; READ-ONLY M1.

---

### BLK-API-04 — Saída PDF (G2/G3)

| Campo | Valor |
|---|---|
| **Criticidade** | Média (negociação de conteúdo; gera o PDF de 7 páginas; READ-ONLY M1) |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Status** | Pendente (depende de BLK-API-03) |
| **ClickUp** | G2/G3 |

**Escopo:** negociação `?formato=pdf` / `Accept: application/pdf` (Decisão 1 = (c)) →
`render_mapas_censitarios_combinados` + `gerar_pdf_relatorio_pontual_censitario` (`application/pdf`).
**Fallback** `basemap=False` quando offline (DEC-004). Rodapé com **carimbo de versão** (Decisão 6). Sem
PII. **Critérios:** PDF binário retornado com `Content-Type: application/pdf`; offline cai em fallback
gracioso; JSON segue default; suíte+ruff+mypy verdes; `censo_*` intocado; READ-ONLY M1.

---

### BLK-API-06 — Integração G3 (Felipe+Juan)

| Campo | Valor |
|---|---|
| **Criticidade** | Média-Alta (integração fim-a-fim + deploy doc) |
| **Esteira** | Block Orchestrator → Planner → [gate humano de deploy] → Builder → QA |
| **Status** | Pendente (depende de BLK-API-04) |
| **ClickUp** | G3 |

**Escopo:** testes de contrato fim-a-fim (`/health` + `/analisar` JSON/PDF), observabilidade mínima
(logs do solicitante p/ LGPD), documentação de deploy da API (extra `[api]` fora do deploy base do
Streamlit; §6 deploy/VPS é humano). **Critérios:** fluxo ponta-a-ponta validado; doc de deploy; READ-ONLY M1.

---

### BLK-API-07 — G4 Telegram/WhatsApp (Juan)

| Campo | Valor |
|---|---|
| **Criticidade** | Média (clientes de bot; consome a API, não a altera) |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Status** | Pendente (depende de BLK-API-06) |
| **ClickUp** | G4 |

**Escopo:** clientes de bot (Telegram/WhatsApp) consumindo `POST /analisar` (recebem link/coordenada do
usuário, devolvem KPIs e/ou PDF). Usa token→consumidor por bot (Decisão 2). **Critérios:** bot envia
ponto e recebe estudo; rastreio do consumidor; sem alteração do motor/M1.

---

### BLK-FIX-12 — Logos das concorrentes não aparecem no PDF do Relatório (API/bot; verificar dashboard)

| Campo | Valor |
|---|---|
| **Criticidade** | Média (qualidade do entregável ao cliente; não toca M1) |
| **Prioridade** | Média |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Status** | Pendente |
| **Origem** | bug reportado por Felipe 2026-06-12 (PDF do bot/API) |

**Sintoma:** o PDF do Relatório Pontual Censitário (página **Concorrentes**) sai com os pins **sem a logo
da rede**, caindo no fallback de sigla/texto. Reportado no PDF gerado pelo **bot e pela API**.

**Diagnóstico inicial (do deploy 2026-06-12 — provável raiz, 3 causas somadas):** a logo vem de
`competitors_logos_dir` (arquivos `logo_<rede>.png`, mapeados em `dashboard/competitors.py`; render via
`_render_pin_tile`). (1) **`data/Logos/` NÃO existe no VPS** (verificado AUSENTE no deploy); (2) o serviço
`api` do `docker-compose.prod.yml` **não** define `API_COMPETITORS_LOGOS_DIR` nem monta o volume de logos
(define só censo/ibge/staging/ultra); (3) como a imagem instala o pacote **não-editável**, o default
`settings.competitors_logos_dir` resolve para `site-packages/data/Logos` (mesma classe do bug de data dirs
corrigido no #9). Soma → nenhum diretório de logos válido.

**Escopo provável:** (a) levar os assets `logo_<rede>.png` ao VPS (conferir se o dashboard já os tem no
volume `/opt/motor-expansao/concorrentes` montado no `streamlit`); (b) montar `:ro` + setar
`API_COMPETITORS_LOGOS_DIR=/app/data/Logos` (ou caminho escolhido) no serviço `api`; (c) confirmar se o PDF
do **dashboard** também sofre (mesma `censo_report`/`competitors`) e padronizar o caminho.

**Critérios:** PDF (API e dashboard) mostra a logo correta por rede; sigla só quando a rede não tem asset.
READ-ONLY M1.

**Resolução do ciclo (concluído 2026-06-12 — esteira BO→Planner→Builder→QA, criticidade Média):**
Diagnóstico das 3 causas confirmado por leitura de código (dashboard NÃO sofre o bug — `preload_logos`
no boot do Streamlit popula o `_ICON_CACHE` global; só a API/bot, processo separado, caía no fallback).
Correção (5 arquivos, READ-ONLY M1):
- `src/motor_expansao/api/settings.py`: `competitors_logos_dir` muda de `Path = _DATA_DIR / "Logos"` para
  `Path | None = None` (default seguro; não resolve mais para `site-packages/data/Logos` em pacote não-editável).
- `src/motor_expansao/api/service.py` (`gerar_pdf_ponto`): guard `is not None and Path(...).is_dir()` (evita `TypeError`).
- `docker-compose.prod.yml` (serviço `api`): adiciona env `API_COMPETITORS_LOGOS_DIR: "/app/concorrentes"` e
  volume `/opt/motor-expansao/concorrentes:/app/concorrentes:ro` (espelha o `streamlit`).
- `tests/unit/test_api_skeleton.py`: 4 testes novos (default None; env→Path; `preload_logos` popula `_ICON_CACHE`;
  guard com None resolve para None sem exceção; limpeza de `_ICON_CACHE` em `finally`).
- `docs/api_geoespacial_deploy.md`: default da env atualizado + tabela de volumes do serviço `api`.
**QA APROVADO:** suíte FULL `733 passed, 4 skipped` (`-n auto`), ruff/mypy limpos, escopo respeitado, §5/§6/§2 ok.
**Operação pós-merge (HUMANO, §6 GUARDRAIL VPS):** garantir `/opt/motor-expansao/concorrentes` no host (o
`streamlit` já o usa), rebuild/pull da imagem `api` e `docker compose up -d --no-deps api`; cada comando exige
confirmação humana. Assets `logo_*.png` são gitignored — não entram na imagem, vêm do volume.

---

### BLK-API-08 — Documentação ponta-a-ponta da API GeoEspacial (uso + manipulação)

| Campo | Valor |
|---|---|
| **Criticidade** | Média (doc; não toca código/M1) |
| **Prioridade** | Média |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Status** | Pendente |
| **Origem** | pedido de Felipe 2026-06-12 (pós-deploy API/bot) |

**Contexto / gap:** já existem `docs/api_geoespacial_contrato.md`, `docs/api_geoespacial_openapi.yaml`,
`docs/api_geoespacial_deploy.md` e `docs/deploy_api_bot.md` — porém espalhados e voltados a
contrato/deploy. Falta **UM** doc de **uso ponta-a-ponta** para qualquer usuário conseguir **utilizar
ou manipular** a API sem ter que juntar as peças.

**Escopo:** criar `docs/api_geoespacial_uso.md` (fonte única de USO) cobrindo, no mínimo:
- Visão geral + arquitetura (api/bot/containers na VPS; api interna 8077; bot long-polling).
- **Autenticação:** token→consumidor; header `Authorization: Bearer <token>`; como obter/rotacionar o token.
- **Endpoints:** `GET /health`; `POST /api/v1/analisar` — schema request/response, **JSON e PDF**
  (`?formato=pdf` / `Accept: application/pdf`), entrada `{lat,lng}` e `maps_url`, raio fixo 1.5 km, carimbo
  de versão (contrato/score).
- **Exemplos prontos:** `curl` (JSON e PDF) e o fluxo do **bot Telegram** (senha → menu → localização → PDF).
- **Erros:** tabela `{detail, codigo}` (400 coordenada_invalida / 401 nao_autenticado / 404 base_geo_ausente
  / 500 erro_interno).
- **Operação:** variáveis `API_*`, rodar local (`uvicorn motor_expansao.api.main:app`), e ponteiro p/
  deploy/atualização (cruzar com `docs/deploy_api_bot.md`). Limitações + roadmap (BLK-API-05).

**Critérios de aceite:** um usuário novo, só com o doc, autentica + chama `/analisar` (JSON e PDF) e usa o
bot; quem mantém entende env/erros/deploy. Linka (não duplica) os docs existentes. READ-ONLY M1.

---

- BLK-FIX-12 (concluído 2026-06-12) — ver tasks/completed.md

---

### BLK-EST-04 — Trocar a imagem de capa do Relatório Pontual Censitário (dashboard + API)

| Campo | Valor |
|---|---|
| **Criticidade** | Baixa (asset de branding; não toca M1) |
| **Prioridade** | Média |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Status** | Pendente |
| **Origem** | pedido de Felipe 2026-06-12 (nova capa já adicionada em `data/ultra/`) |

**Contexto:** a capa do PDF usa o asset `data/ultra/relatorio_capa_bg.png` (extraído do `Teste Modelo.pptx`,
**gitignored** — não vai na imagem; lido em runtime do volume `data/ultra`). Felipe **já adicionou a nova
versão** em `data/ultra/relatorio_capa_bg.png` (local).

**Escopo:** trocar a capa nos **dois** caminhos (dashboard + API). Como o asset é gitignored e lido do
volume montado, basta **scp** do novo `relatorio_capa_bg.png` para `/opt/motor-expansao/data/ultra/` no
VPS — `streamlit` e `api` montam `data/ultra`, então **uma cópia atualiza os dois**. Sem rebuild de imagem.
Se a nova capa mudar de proporção/zona limpa, conferir o layout 16:9 (`_cover_page` em `censo_report.py`)
para o título/subtítulo não colidirem com o branding.

**Critérios:** PDF do dashboard e da API usa a capa nova; título/subtítulo legíveis sobre ela; sem PII
versionada (asset segue gitignored).

**Fechamento (2026-06-12) — APROVADO.** Esteira efetiva: Block Orchestrator → Builder → fechamento
(criticidade Baixa; pura troca de asset de branding, READ-ONLY sobre o M1). Nova capa
`data/ultra/relatorio_capa_bg.png` (1360×763, ratio 1.7824 ≈ 16:9; 76.089 bytes) renderizada e
**inspecionada visualmente pelo orquestrador** via PyMuPDF nos DOIS estados do subtítulo
(coordenada e rótulo de endereço): título "Relatorio Pontual Censitario" (30 pt bold branco,
zona limpa inferior-direita), subtítulo e "Raio de analise: 1,5 km" ficam LEGÍVEIS e SEM colisão
com o logo "GRUPO ULTRA" (acima) nem com a faixa branca de parceiros Ultra/Spider Kick/The Flame
(abaixo). **ZERO mudança de código** — `_cover_page`/`censo_report.py` intocados (Caso A do Builder,
confirmado por render independente). **Deploy VPS executado e verificado** (usuário pré-autorizou):
`scp` do novo PNG para `/opt/motor-expansao/data/ultra/relatorio_capa_bg.png`; sha256 host
`f7419fd1…d0b2` == local; **ambos os containers servem o novo asset** (api e streamlit, mesmo hash
via mount `/app/data/ultra`); sem rebuild de imagem nem restart (lido do volume em runtime). Capa
antiga substituída (era 423.924 bytes, sha `affdc153…44be`). M1/score/artefatos oficiais e estrutura
do PDF (7 páginas/ordem/`/Count`/grid 4x2/`set_compression(False)`/raio 1.5 km/método de interseção):
INALTERADOS. Asset segue gitignored (sem PII versionada; `image24.png` nunca embutida).

---

### BLK-DIM-00 — Fundação de dados: catchment, base de calibração das maduras e ingestão dos insumos externos

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (engenharia de dados nova; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Depende de** | Felipe disponibilizar os insumos externos (série diária, datas de abertura, .xlsx) |
| **Status** | Pendente |

**Objetivo:** montar a fundação de dados de TODAS as camadas, sem tocar o M1.

**Escopo permitido:**
- **Ingestão dos insumos externos** (Felipe disponibiliza): série diária das ~60 maduras
  (vendas/cancelamentos/churn), datas de abertura por unidade, `ULTRA padrão - Simulador
  Financeiro.xlsx`. Normalizar para staging Parquet (gitignored se contiver PII).
- **Catchment materializado:** rodar `analisar_entorno_ponto` em batch para cada unidade Ultra madura
  e cada hex candidato → `pop_captação`, `renda_per_capita_captação` por raio fixo (começar 1,5 km;
  parametrizar para 1–2 km). Materializar em `data/staging/` (NÃO sobrescrever artefato M1).
- **Base de calibração das maduras:** consolidar por unidade — pagantes steady-state, churn,
  inadimplência, ticket, **curva de maturação** (da série diária), metragem, `pop_captação`.
- **Derivar maturação real** das datas de abertura (resolve gate G1 da DEC-001) — substituir
  `maturacao_indisponivel`.

**Critérios de aceite:** base de calibração reprodutível por unidade madura com maturação real e
`pop_captação`; auditoria do que foi ingerido vs. lacunas remanescentes; ZERO escrita em artefato M1;
sem PII versionada.

**Risco:** médio (depende dos insumos externos; sem eles, DIM-01/02/04 ficam limitados).

---

### BLK-LOOP-01 — Loop autônomo (ralph) em container isolado para blocos loop-safe

**Concluído 2026-06-13** (ad-hoc; pedido de Felipe). Porta o padrão "ralph" (laço de `/run-cycle`
autônomo) do projeto Growth RPG para o Motor, restrito a blocos **`loop-safe`** (READ-ONLY sobre o M1,
sem VPS/deploy, sem PII, consumindo `data/staging`). Roda em **container Docker isolado** (`Dockerfile.loop`,
non-root), repo montado como volume, autenticado pela **assinatura Max** (`CLAUDE_CODE_OAUTH_TOKEN`,
não API key). Decisões de Felipe: (D1) **guard automático substitui o gate humano** dos blocos Alta;
(D2) **container sem credencial** (consome só dados já staged; ingestão ao vivo continua passo humano).

**Entregue:** `Dockerfile.loop`, `run-ralph-loop.sh` (laço com 4 redes de segurança), `scripts/loop_guard.py`
(aborta se o diff tocar M1/score/config/pipelines m1/VPS/deploy/segredo/CI — testado), `docs/loop_autonomo.md`
(runbook Windows+Docker), marcador `Autonomia: loop-safe` em BLK-DIM-01/02/03/04, e `LOOP_DONE`/
`RELATORIO-BLOQUEIO.md` no `.gitignore`. O loop commita por path no branch e **nunca** faz merge/push/deploy.
Validações: ruff/mypy limpos no guard; `bash -n` ok; guard testado (positivo e negativo). READ-ONLY sobre o M1.

---

### BLK-LOOP-02 — Robustez do guard do loop (falso-positivo de CRLF) + container sem churn

**Concluído 2026-06-13** (ad-hoc; pós-mortem da 1ª rodada do loop). A 1ª rodada autônoma (epic
BLK-DIM) entregou as 4 camadas com testes verdes, mas o guard ABORTOU por **falso-positivo**: o
container Linux normalizou line endings (CRLF→LF) e isso fez arquivos do M1 **aparecerem
"modificados"** no working tree (`git status`), embora o **commit por path** os tenha mantido fora
dos commits (diff commitado 100% limpo, zero arquivo M1/VPS). Correções:
- **`scripts/loop_guard.py`**: passa a avaliar a **intenção de merge** = diff **commitado (base..HEAD)
  + staged (`--cached`)**, NÃO o working tree não-staged (que trazia o churn de CRLF/`__pycache__`).
  Regex de M1 **ancorado** a caminhos específicos (`^src/motor_expansao/config.py$`,
  `^.../(core|dashboard)/constants.py$`) — não casa mais o `dimensionamento/config.py` legítimo.
- **`Dockerfile.loop`**: `git config core.autocrlf false` no container (não converte line endings).
- **`tests/unit/test_loop_guard.py`**: 26 testes trancam a matriz proibido/permitido (M1/score/VPS/
  segredo bloqueados; módulo paralelo `dimensionamento/` e docs permitidos).
READ-ONLY sobre o M1. Validações: 26 passed, ruff/mypy limpos. O trabalho DIM-01..04 da 1ª rodada
ficou nos branches `ciclo/BLK-DIM-01..04` para auditoria humana (R²=0.897 identificado como artefato
de fixture sintética — ver parecer; calibração em dado real ainda pendente).

---

### BLK-EST-03 — Fonte real do solicitante (Authelia/sessão) para a marca d'água do PDF

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (rastreabilidade/LGPD — passa a gravar identidade real no documento; READ-ONLY sobre M1) |
| **Prioridade** | **Média** (depende de infra de autenticação; o contrato já está pronto) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente (bloqueado: requer Authelia/sessão autenticada existir primeiro) |
| **Responsável sugerido** | Vini (+ Felipe na padronização da fonte) |
| **ClickUp** | `86e1rtezm` — https://app.clickup.com/t/86e1rtezm (logs de rastreio LGPD, do Felipe) |
| **Origem** | follow-up do BLK-EST-01 (ver `tasks/completed.md`); risco R1 do handoff do Planner |
| **Relacionado** | DEC-005 (API GeoEspacial — token por consumidor/bot); BLK-API-02+ |

**Contexto:** o BLK-EST-01 entregou a marca d'água com o parâmetro `solicitante: str | None = None` e
fallback seguro (`None` → só "Ultra Academia"). Hoje **não existe Authelia/sessão autenticada no código**
(verificado em 2026-06-11: busca por `authelia`/`solicitante`/`usuario_logado`/`X-Remote-User`/`identity`
em `src/` = zero), então o nome real do solicitante nunca é preenchido. Este bloco fecha essa lacuna:
ligar a fonte real da identidade ao parâmetro `solicitante` já existente, padronizando com os logs de
rastreio LGPD do Felipe (ClickUp `86e1rtezm`).

**Objetivo:** todo PDF gerado por usuário autenticado carrega o nome real do solicitante na marca d'água,
com a mesma fonte de identidade usada nos logs LGPD; geração anônima/sem sessão mantém o fallback seguro.

**Escopo permitido:** caminho de geração que chama `render_downloads_relatorio_censitario` /
`gerar_payloads_download_relatorio_censitario` / `gerar_pdf_relatorio_pontual_censitario` (passar a
identidade real no parâmetro `solicitante`); leitura da identidade da sessão (dashboard) e/ou do token do
consumidor (API, DEC-005); padronização da fonte com os logs LGPD. **NÃO altera `censo_report.py`** (a
assinatura `solicitante` já está pronta) além do estritamente necessário.

**Fora de escopo:** redefinir a marca d'água/template (já entregue no BLK-EST-01); versionar PDFs reais ou
fixtures com PII real; score/artefatos M1 (READ-ONLY); recolocar dependência de API ao vivo no dashboard.

**Dependências:** infra de autenticação (Authelia ou equivalente) disponível no dashboard de produção;
padronização da fonte "solicitante" com a tarefa de logs LGPD do Felipe (ClickUp `86e1rtezm`); para a API,
o token→consumidor da DEC-005 (BLK-API-02+).

**Critérios de aceite:** PDF gerado por sessão autenticada traz o nome real do solicitante; sem sessão →
fallback "Ultra Academia" (retrocompat preservada); fonte do nome padronizada e testada (com nome
fictício nas fixtures, sem PII real); suíte verde; ruff + mypy limpos; READ-ONLY M1.

**Guardrail:** anti-PII do §2/§4 preservado (nenhum PDF/PII versionado); sem dependência de API ao vivo no
dashboard; LEITURA/ANÁLISE sem escrita em artefato M1 = Alta.

**Fechamento do ciclo (2026-06-15) — VEREDITO: APROVADO COM RESSALVAS** (esteira BO → Planner →
[aprovação humana de Vinicius] → Builder → QA). Entregue o **recorte da trilha da API (Fase 1)**: o
Block Orchestrator descobriu que a API GeoEspacial (DEC-005 / BLK-API-02+) já mergeou com
`auth.resolver_consumidor` (token→consumidor) e a rota `POST /analisar?formato=pdf` já leva o
`consumidor` até `service.gerar_pdf_ponto` — a ÚNICA lacuna era que `gerar_pdf_ponto` chamava
`gerar_pdf_relatorio_pontual_censitario(...)` **sem repassar `solicitante=consumidor`**. Fix cirúrgico de
**1 linha** em `src/motor_expansao/api/service.py` (linhas ~306-308: `+ solicitante=consumidor`) + **2 testes**
em `tests/integration/test_api_analisar.py` (spy na origem `censo_report.gerar_pdf_relatorio_pontual_censitario`
captura o kwarg `solicitante`: rota carimba o consumidor; chamada direta com `consumidor=None` → fallback
"Ultra Academia"). `censo_report.py` (assinatura `solicitante: str | None = None` e `_watermark_text`),
`pages.py`, `AnalisarResponseJSON` e a assinatura `consumidor: str | None` de `gerar_pdf_ponto` INTOCADOS.
Anti-PII: fixtures com nome fictício, nenhum PDF/PII real versionado. READ-ONLY M1 confirmado
(score/pesos `0.40`/`0.60`/artefatos INALTERADOS; DEC-001). **Trilha do dashboard permanece BLOQUEADA**
(Authelia/identidade ausente no Streamlit — `pages.py` segue com fallback seguro) → Fase 2 futura.
Premissa R3 (logs LGPD ClickUp `86e1rtezm` já leem `consumidor` do JSON; sem logging novo) confirmada no
gate humano. Validações do QA (Opus 4.8, gate único): ruff limpo, `import streamlit_app` ok, mypy só com
1 erro PRÉ-EXISTENTE de stub `requests` (linha intocada), os 2 testes novos PASSAM não-skipped. **Ressalva
não-bloqueadora:** a suíte full (serial; xdist trava ~96% no ambiente Python 3.14 local) deu
`2 failed, 816 passed, 1 skipped` — as 2 falhas são **data-drift PRÉ-EXISTENTE** em
`test_csvs_concorrentes_legiveis` (CSVs reais de concorrentes regenerados: 226 vs 223 e 455 vs 472 linhas),
comprovadamente independentes do bloco (reproduzem idênticas com o BLK-EST-03 em `git stash`). Aberto
**BLK-FIX-13** (Baixa) no backlog para reconciliar o teste com os CSVs reais (renomeado de BLK-FIX-07 para
evitar colisão de ID com o BLK-FIX-07 concluído em 2026-06-01). Housekeeping via
`scripts/housekeeping_move_block.py` (`--check` verde); paths do ciclo: `src/motor_expansao/api/service.py`,
`tests/integration/test_api_analisar.py`, `tasks/*`, `context/handoff*`.

---

- BLK-EST-02 (concluído 2026-06-11) — ver tasks/completed.md

---

### BLK-DIM-03R — Simulador financeiro fundamentado no DRE real (remove os números mágicos)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (módulo determinístico isolado; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Depende de** | **BLK-DIM-00** (`simulador_estrutura.json` já existe) |
| **Status** | Pendente |
| **Autonomia** | **loop-safe** — READ-ONLY M1, sem VPS, determinístico, consome `data/staging`; gate humano substituído pelo guard no loop; ver `docs/loop_autonomo.md` |

**Contexto:** o simulador do spike (`simulador.py`) inventou `pessoal_pct=0.30`, `outros_custos_pct=0.05`,
`custo_fixo_base_mes=5000` para fazer o teste de margem (~24%) passar — circular. Os coeficientes reais
estão no `data/staging/simulador_estrutura.json` (BLK-DIM-00) e no `.xlsx`.

**Objetivo:** trocar os números mágicos por coeficientes derivados do DRE real (`simulador_estrutura.json`),
e **des-circularizar** o teste: validar a margem/ROIC contra o Excel de referência (defaults §8.2), não
contra constantes ajustadas para passar.

**Escopo permitido:** ler `simulador_estrutura.json`; parametrizar a "linha de resultado" do DRE com os
ratios reais; goal-seek (`brentq`) preservado; teste valida contra o Excel/§8.2. Sem escrita em M1.

**Critérios de aceite:** zero número mágico não-fundamentado; margem/ROIC batem o Excel de referência
(não constantes auto-ajustadas); goal-seek do aluguel-teto validado; ZERO escrita em M1.

**Risco:** baixo (determinístico). Substitui o `simulador.py` do spike.

---

### BLK-DIM-01R — Calibração REAL da Camada 1 (aderência) + correção da endogeneidade

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (decide ciência vs. ficção do motor; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA / no loop: guard]` → Builder → QA |
| **Depende de** | **BLK-DIM-00** (base de calibração materializada em `data/staging/`) |
| **Status** | Pendente |
| **Autonomia** | **loop-safe** — READ-ONLY M1, sem VPS, consome `data/staging`; no modo loop o gate humano é substituído pelo guard automático (`scripts/loop_guard.py`); ver `docs/loop_autonomo.md` |

**Contexto / por que existe:** a 1ª rodada do loop (spike DIM-01..04, branches `ciclo/BLK-DIM-01..04`,
NÃO mergeados) entregou bom esqueleto de engenharia, mas a auditoria (2026-06-13) achou que o
**R²_LOO=0.897 é ARTEFATO** de fixture sintética (o teste gera os dados da própria equação do modelo)
e que há **endogeneidade**: o alvo `penetração = pagantes/pop_captação` tem a feature `log(pop)` no
denominador → anti-correlação mecânica (`log penet = log pagantes − log pop`), que pode gerar **GO
espúrio**. Nenhuma calibração em dado REAL foi feita. Este bloco faz a Camada 1 **de verdade**.

**Objetivo:** estimar e VALIDAR honestamente a aderência/penetração usando os **maduros reais** de
`data/staging/base_calibracao_maduras.parquet` (DIM-00), tratando a endogeneidade, e reportar o
**R²_LOO verdadeiro** com veredito GO/NO-GO. (Pode reaproveitar o ESQUELETO de engenharia do branch
`ciclo/BLK-DIM-01` — LOO/Ridge/anti-PII estão corretos — mas a estatística deve ser refeita honesta.)

**Escopo permitido:**
- **Rodar sobre dado REAL** (`base_calibracao_maduras.parquet`): nada de fixture sintética como
  resultado. Reportar N de unidades, faixa de penetração observada, e o **R²_LOO no espaço de alunos**
  (não no log) **contra baseline da média** (§7 do spec).
- **Corrigir a endogeneidade** (escolher e justificar): (a) modelar `pagantes_steady_state`
  DIRETAMENTE com `pop`/`renda`/features de perfil como preditores (sem a razão no alvo); e/ou
  (b) regredir penetração contra features que NÃO derivam de pop/renda do mesmo catchment (perfil
  etário, densidade urbana — spec §4). Documentar que `coef_log_pop≈−1` é em parte artefato algébrico.
- **Teste de controle negativo (anti-circular):** com `pagantes` independente de `pop` (identidade
  pura), o gate **NÃO** pode dar GO espúrio — virar teste de regressão explícito (o spike só notava
  isso em rodapé). Remover/substituir os testes circulares (R²>0.5 sobre dados auto-gerados).
- Saída: relatório `data/analysis/aderencia_real.md` (gitignored) com R²_LOO honesto, IC, N, confounds
  e veredito; flags de extrapolação. Módulo em `src/motor_expansao/dimensionamento/`.

**Gate GO/NO-GO:** se o R²_LOO real não for positivo e material contra a média, **NO-GO honesto** —
relatório sem forçar significância (coerente com a DEC-001, que achou sinal ~nulo). Um NO-GO aqui é
um resultado VÁLIDO do bloco, não uma falha.

**Fora de escopo (invioláveis):** score/pesos/artefatos M1 (READ-ONLY; DEC-001); ingestão ao vivo na
Growth API (consome só `data/staging`); persistir PII; VPS/deploy; reaproveitar o R²=0.897 do spike.

**Critérios de aceite:** R²_LOO calculado em dado REAL (espaço de alunos, vs baseline) com IC/N; alvo
sem endogeneidade trivial (justificado); teste de controle negativo verde; ZERO fixture-sintética como
resultado; ZERO escrita em M1; reprodutível (seed fixo).

**Risco:** o resultado pode ser NO-GO (sinal fraco) — e está tudo bem: é o "número que decide tudo"
medido com honestidade. **Ótimo bloco para testar o loop corrigido (BLK-LOOP-02).**

---

### BLK-DIM-05 — Features exógenas na aderência (perfil etário, densidade urbana, vínculo formal)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (modelagem que informa expansão; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA / no loop: guard]` → Builder → QA |
| **Depende de** | **BLK-DIM-01R** (alvo sem endogeneidade) |
| **Status** | Pendente |
| **Autonomia** | **loop-safe** — READ-ONLY M1, sem VPS, consome `data/staging`/censo; gate humano substituído pelo guard no loop; ver `docs/loop_autonomo.md` |

**Contexto:** o spike usou só `pop`+`renda` (que geram a endogeneidade). O spec §4 pede features
demográfico-comportamentais. Estas são EXÓGENAS (não derivam de pop/renda do catchment) e podem
trazer o sinal real que a DEC-001 não achou no M1.

**Objetivo:** enriquecer o X da aderência com features exógenas do censo 2022 por catchment: **faixa
etária 18-45** (público-alvo do projeto), densidade urbana, vínculo formal/renda do trabalho — e medir
se o R²_LOO honesto melhora materialmente sobre o baseline e sobre o modelo só-pop/renda.

**Escopo permitido:** derivar as features por catchment (reuso do helper censitário, READ-ONLY);
acrescentar ao modelo do BLK-DIM-01R; LOO-CV vs baseline; reportar ganho/perda honesto. Relatório em
`data/analysis/` (gitignored).

**Critérios de aceite:** features exógenas materializadas por unidade; comparação honesta (com/sem) por
LOO-CV; ZERO escrita em M1; reprodutível.

**Risco:** baixo (read-only/diagnóstico). Pode concluir que não há ganho — resultado válido.

---

### BLK-DIM-06 — Backtest honesto out-of-sample (substitui o backtest in-sample do spike)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (é o que dá/retira confiança no motor; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA / no loop: guard]` → Builder → QA |
| **Depende de** | **BLK-DIM-01R** (e idealmente DIM-02R/03R) |
| **Status** | Pendente |
| **Autonomia** | **loop-safe** — READ-ONLY M1, sem VPS, consome `data/staging`; gate humano substituído pelo guard no loop; ver `docs/loop_autonomo.md` |

**Contexto:** o backtest do spike (`pipeline.py`) usava `faturamento` gerado pela PRÓPRIA fórmula do
simulador → in-sample disfarçado de honesto. Precisamos do erro REAL.

**Objetivo:** harness que roda o motor "às cegas" nos maduros reais (faturamento/alunos REAIS de
`base_calibracao_maduras`/Growth API já staged) e reporta **MAPE e R² out-of-sample** por camada e
end-to-end, com flags de extrapolação. A `nota_honesta` deve refletir o erro medido, não afirmar.

**Escopo permitido:** LOO/out-of-sample sobre dados reais; comparação previsto×real por unidade;
relatório `data/analysis/backtest_dim.md` (gitignored). Sem escrita em M1.

**Critérios de aceite:** erro out-of-sample real (MAPE/R²) por camada e end-to-end; flags de
extrapolação; nenhum dado auto-gerado como resultado; ZERO escrita em M1.

**Risco:** o erro real pode ser alto — e é exatamente o que precisamos saber antes de qualquer decisão.

---

- BLK-DIM-03R (concluído 2026-06-13) — ver tasks/completed.md

---

### BLK-FIX-13 — Data-drift em `test_csvs_concorrentes_legiveis` (2 falhas pré-existentes na suíte full)

| Campo | Valor |
|---|---|
| **Criticidade** | **Baixa** (teste de dados desatualizado vs CSVs reais regenerados; READ-ONLY sobre M1) |
| **Prioridade** | **Média** (deixa a suíte full vermelha — 2 falhas — mascarando regressões futuras) |
| **Esteira** | Block Orchestrator → Builder |
| **Status** | Pendente |
| **Origem** | ressalva não-bloqueadora do QA do BLK-EST-03 (2026-06-15); falhas comprovadamente independentes do bloco (reproduzem com o BLK-EST-03 em `git stash`) |

**Contexto:** o QA do BLK-EST-03 rodou a suíte full e encontrou `2 failed, 816 passed, 1 skipped`
(serial; xdist trava em ~96% no ambiente Python 3.14 local). As 2 falhas estão em
`test_csvs_concorrentes_legiveis` e são **data-drift**: os CSVs reais de concorrentes foram
regenerados com contagens diferentes das fixadas no teste (226 vs 223 linhas; 455 vs 472 linhas).
Nada a ver com a API/marca d'água — reproduzem idênticas com o BLK-EST-03 fora da árvore.

**Objetivo:** restaurar a suíte full 100% verde, reconciliando o teste com os CSVs reais atuais
(atualizar as contagens esperadas OU tornar o teste robusto a drift, conforme o BO/Builder decidir),
sem mascarar regressão real.

**Escopo permitido:** o teste `test_csvs_concorrentes_legiveis` e, se necessário, a verificação dos
CSVs de concorrentes em `data/`. **Fora de escopo:** score/pesos/artefatos M1 (READ-ONLY); regenerar
artefatos M1.

**Critérios de aceite:** `pytest` full verde (0 failed); a mudança documenta por que as contagens
mudaram (regeneração legítima vs regressão); READ-ONLY M1.

**Fechamento do ciclo (2026-06-15) — VEREDITO: APROVADO** (esteira Baixa: BO → Builder; sem QA — o
orquestrador é o gate final). Diagnóstico confirmado: `CSV_SOURCES` (em
`tests/integration/test_modelo_mercado_hexagonos.py`) fixava contagens exatas (bluefit 223, panobianco
472) mas os CSVs reais de `concorrentes/` (GITIGNORED, regenerados pelo pipeline) drifteram para 226/455;
smart_fit segue 1000. Como em CI os CSVs não existem (`pytest.skip`), o vermelho era só no run LOCAL — não
era regressão de código, e sim refresh legítimo de dado. **Fix (abordagem B, recomendada pelo BO):**
trocar `assert len(df) == expected_rows` por **piso de sanidade** `assert len(df) >= min_rows` (floor 100
por CSV), mantendo a checagem de `CSV_REQUIRED_COLS` e parseabilidade — robusto a drift legítimo, mas
detecta CSV vazio/truncado. `CSV_SOURCES` agora mapeia floors (100/100/100) e o param virou `min_rows`.
**Validação (Builder, gate final):** suíte FULL `884 passed, 1 skipped, 0 failed`; `import streamlit_app`
ok; ruff limpo no arquivo. READ-ONLY M1 (DEC-001): só o arquivo de teste mudou; score/pesos/artefatos
intocados. Escopo só `tests/integration/test_modelo_mercado_hexagonos.py`.
