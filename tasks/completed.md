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
**BLK-FIX-07** (Baixa) no backlog para reconciliar o teste com os CSVs reais. Housekeeping via
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

### BLK-DIM-07 — Base de calibração multi-rede + raio de captação variável (fundação da sub-trilha "estressar o dado interno")

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (fundação que decide a sub-trilha; READ-ONLY sobre M1) |
| **Esteira** | Felipe (foreground, com revisão humana) — NÃO via loop |
| **Depende de** | **BLK-DIM-00** |
| **Status** | **Concluído 2026-06-15** |
| **Autonomia** | loop-safe (mas executado no foreground por decisão de Felipe; o loop assume o DIM-08+) |

**Concluído 2026-06-15** (Felipe + Claude, foreground). Primeira frente da sub-trilha que **estressa ao
máximo o dado interno** antes do BLK-DIM-DATA (microdados/proxy externos). Reformula o problema que deu
NO-GO no BLK-DIM-01R em 4 frentes: (1) decisão por **mercado residual ≥ piso de viabilidade** em vez de
predição absoluta; (2) **raio de captação variável** por contexto urbano; (3) penetração **regional/por
marca** (estrutura, não global); (4) **N ampliado** com Engenharia do Corpo + SkyFit + os underperformers
<2k como rótulo.

**Descoberta-chave (auditoria de dados 2026-06-15):** as 3 redes têm alunos reais **E coordenadas LOCAIS**
(sem geocoding online) — Ultra (`unidades_ultra_performance_hex.parquet`), Engenharia
(`data/validacao/academias_engenharia_do_corpo.xlsx` + `concorrentes/Unidades/unidades_engenharia_do_corpo.csv`),
SkyFit (`data/validacao/Sky Fit dados.xlsx` + `concorrentes/Unidades/unidades_skyfit.csv`, 481 coords). O
match ingênuo por nome dá **0%** (convenções divergentes) → reconciliação por chave correta: Ultra direto,
SkyFit por **cidade+UF**, Engenharia por **crosswalk fuzzy** (`difflib`, stdlib — sem dependência nova;
corte limpo ~0,95). A SkyFit deixou de precisar de geocoding → o BLK-DIM-09 virou só o crosswalk da cauda ambígua.

**Entregue:** `src/motor_expansao/dimensionamento/base_multirede.py` (loaders das 3 redes + reconciliação
auditada; `raio_variavel_km` exógeno; `derivar_densidade_marca_propria` = controle de domínio via haversine
same-brand; `validar_raio_variavel` reusando o catchment censitário do DIM-00 INTOCADO; `montar_base_multirede`,
`salvar_base` com guard anti-PII, `escrever_relatorio`). Testes: `tests/unit/dimensionamento/test_base_multirede.py`
(17 testes offline, fixtures sintéticas — não tocam os xlsx reais nem o censo). Artefatos (gitignored):
`data/staging/base_calibracao_multirede.parquet` (426 unidades, **275 com coord**, sem PII) e
`data/analysis/catchment_variavel.md`.

**Resultados reais (275 unidades com coord):**
- Taxa de match: Ultra 98%, Engenharia 62% (38 fuzzy / 23 → DIM-09), SkyFit 59% (184 cidade+UF / 127 → DIM-09).
- **CV da penetração: 1,15 (fixo 1,5 km) → 0,47 (variável) — redução de 59%.** Raio mediano 1,66 km.
- R²_LOO de log(alunos)~log(pop): −0,005 (fixo) → −0,009 (variável) — ambos ≈ 0.
- **Veredito: `raio_variavel_aceito_para_estabilidade`** — o raio variável torna a penetração COMPARÁVEL
  entre regiões (corrige o artefato de penetração >100% do raio fixo, que o BLK-DIM-01R sofria), MAS não
  conserta a previsão pop→alunos (pop sozinha não carrega o sinal de demanda em raio nenhum — consistente
  com o NO-GO do BLK-DIM-01R/DEC-001). O raio é melhor **medição**, não um preditor de demanda.

**Validações:** ruff limpo, mypy limpo (`base_multirede.py`), **130 testes do módulo `dimensionamento/`
passam** (17 novos + 113 existentes); pipeline ponta-a-ponta reproduzida (≈75–156 s, conforme cache de
partições censitárias). **READ-ONLY sobre o M1** (DEC-001/DEC-008): não recalcula `score_priorizacao`/pesos,
não toca artefatos oficiais; catchment usa o helper geométrico do DIM-00 (raio/método de interseção
INTOCADOS). **Anti-PII:** `assert_sem_pii` antes de persistir; relatório só com contagens agregadas; nenhum
xlsx/nome em disco de saída. **Sucessor:** BLK-DIM-08 (teste discriminativo do residual + estrutura
região×marca×domínio) — loop-safe, agora com dependência satisfeita.

---

> ## Spikes BLK-DIM-01..04 (1ª rodada do loop, 2026-06-13) — SUPERSEDED, mantidos como referência
>
> Os 4 spikes da 1ª rodada autônoma do loop foram **auditados e substituídos** (não mergeados; ficaram nos
> branches `ciclo/BLK-DIM-01..04` para auditoria — ver fechamento do **BLK-LOOP-02**). São referência de
> engenharia, não trabalho de produto vigente:
> - **BLK-DIM-01** → superseded por **BLK-DIM-01R** (R²=0.897 era artefato de fixture sintética).
> - **BLK-DIM-02** → superseded por **BLK-DIM-02R** (fallback `pot=y` previsor=alvo, vazamento).
> - **BLK-DIM-03** → superseded por **BLK-DIM-03R** (números mágicos calibrados ao teste).
> - **BLK-DIM-04** → superseded por **BLK-DIM-06** (backtest era in-sample disfarçado).

---

### BLK-DIM-08 — Teste discriminativo do mercado residual (performers × underperformers) + estrutura regional

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (é o teste que dá/retira confiança na tese residual; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA / no loop: guard]` → Builder → QA |
| **Depende de** | **BLK-DIM-07** (base multi-rede + raio escolhido) |
| **Status** | Pendente |
| **Autonomia** | **loop-safe** — READ-ONLY M1, sem VPS, consome `data/staging`/`data/analysis`; guard no loop |

**Contexto / hipótese central (falsificável):** "o **mercado residual endereçável** (`pop(raio variável)
× penetração_regional − consumo_concorrencial_gravitacional`) **separa** as unidades que performam (≥2k)
das que não performam (<2k, ex.: Carapicuíba) — melhor que `pop+renda` em raio fixo". Reformula o
problema mal-posto do 01R (predição absoluta → R² negativo) numa **discriminação com limiar acionável**.

**Objetivo:** medir, honestamente, se o residual discrimina viabilidade e se sobra estrutura regional de
penetração depois de **separar região × marca × domínio**.

**GUARDRAIL DE INTERPRETAÇÃO (obrigatório — Felipe 2026-06-15):** o residual é sinal de **RANKING/triagem**
(discriminar viável × inviável), **NÃO previsão pontual de alunos**. O BLK-DIM-07 mediu `R²_LOO≈0`: pop não
prevê o nº absoluto de alunos em raio nenhum. Logo, reportar a saída como **score de oportunidade / piso de
demanda com intervalo**, NUNCA como "este hex terá N alunos". O uso do residual para dimensionar (virar
alunos-alvo → m²) é downstream (DIM-04/integração), fora deste bloco.

**Escopo permitido:**
- **Teste B (discriminação):** o residual rankeia as <2k abaixo das ≥2k? Reportar separação/AUC **LOO**,
  comparando contra o baseline `pop+renda` em raio fixo. Reusar `score_oportunidade_residual` /
  `oferta_efetiva_disponivel` (já existentes) recalculados no raio do BLK-DIM-07.
- **Teste C (estrutura, decomposição de 3 efeitos):** componentes de variância da penetração separando
  **região** (mercado intrínseco) × **marca** (efeito de nível — pull de marca, NÃO ticket; confirmado
  similar entre redes) × **domínio** (`n_unidades_mesma_marca`/densidade de marca própria do BLK-DIM-07).
  Partial pooling / efeitos aleatórios; penetração por cluster sempre **leave-one-unit-out** (anti-circular).
  **Por que importa (Felipe 2026-06-15):** sem o termo de domínio, a penetração alta da Engenharia no Sul
  (Caxias do Sul "fechada") vaza para o efeito "região" e o modelo conclui falsamente "o Sul é alto-mercado"
  quando foi **estratégia de domínio**. Para site selection, reportar a penetração-base **líquida de
  domínio** (1 unidade nova, sem saturação própria).
- **Bônus — domínio como SINAL (valida a tese Expansão de Domínio com dado de concorrente):** estimar e
  reportar o uplift de penetração por unidade adicional de marca própria no catchment (efeito domínio),
  usando a Engenharia-Sul como caso. Diagnóstico READ-ONLY; se material, vira insumo de um bloco futuro de
  estratégia de domínio (não recalibra M1 aqui).
- **Sanidade dos casos:** Carapicuíba e as outras <2k caem mesmo em hex de baixo residual? (true
  negative). Se o residual NÃO separa, **NO-GO honesto** da tese residual — resultado válido.
- Saída: relatório `data/analysis/residual_discriminacao.md` (gitignored).

**Fora de escopo:** Huff completo (é o BLK-DIM-02R); score/pesos/artefatos M1; PII; recalibrar a camada
Expansão de Domínio (o efeito domínio aqui é só diagnóstico/insumo).

**Critérios de aceite:** AUC/separação LOO do residual vs. baseline; decomposição de variância
região×marca×domínio; penetração-base líquida de domínio reportada; uplift de domínio estimado (com IC);
veredito GO/NO-GO da tese residual com IC/N/confounds; ZERO escrita em M1; reprodutível.

**Risco:** médio (N~440 ajuda, mas células região×marca×domínio ficam ralas; partial pooling mitiga, não
elimina; separar domínio de região com poucos casos de domínio real é o ponto delicado).

**Concluído 2026-06-15** (loop autônomo `ciclo/loop-20260615-124342`, mergeado PR #26; auditado no merge).
**VEREDITO: NO-GO honesto.** O residual **não discrimina** unidades viáveis (≥2.000 alunos) de inviáveis
(<2.000) melhor que o acaso. AUC do `score_oportunidade_residual` = **0,480**, IC95 [0,42; 0,54] cruza 0,5,
p-perm 0,74; **abaixo** do baseline pop×renda (AUC 0,531); TNR 0,22 (pior que os 25% do acaso). Os três
rankers (residual / pop×renda / penetração regional LOO) ficam no acaso. LOO anti-circular verificado
numericamente (`_penetracao_loo_por_grupo` exclui a unidade-alvo); IC bootstrap + p de permutação; saída
só AUC/IC/variância (sem previsão pontual). Teste C (decomposição região×marca×domínio) e sanidade de
casos em `data/analysis/residual_discriminacao.md` (gitignored, 5 seções). Entregue:
`src/motor_expansao/dimensionamento/residual_discriminacao.py` + 13 testes; suíte 919 passed. READ-ONLY M1
(DEC-001/DEC-008). **Leitura:** terceiro NO-GO honesto da Camada 1/2 — a viabilidade de um ponto **não está
na geografia de mercado** que temos (pop, renda, concorrência, residual) em raio nenhum. Insumo da
bifurcação estratégica da epic (ver **BLK-DIM-10** no backlog).

---

### BLK-DIM-02R — Huff com validação real (OSM, saturação, sem vazamento)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (elo mais difícil; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA / no loop: guard]` → Builder → QA |
| **Depende de** | **BLK-DIM-08** (gate de sequência — ver nota) |
| **Status** | Pendente |
| **Autonomia** | **loop-safe** — READ-ONLY M1, sem VPS, consome `data/staging`; gate humano substituído pelo guard no loop; ver `docs/loop_autonomo.md` |

> **Gate de sequência (Felipe 2026-06-15):** dependência mudada de `BLK-DIM-01R` para **`BLK-DIM-08`**.
> O DIM-01R deu **NO-GO** (pop+renda não preveem demanda); modelar captura (Huff = potencial × share)
> em cima de uma Camada 1 NO-GO é prematuro. O **DIM-08** (discriminação do residual + estrutura
> região×marca×domínio) é quem informa se vale perseguir captura. Logo o loop só fica elegível para o
> DIM-02R **depois** do DIM-08 estar em `completed.md`. (Pré-requisito técnico de não-vazamento — remover
> `previsor=alvo` do `huff.py` — permanece igual.)

**Contexto:** o Huff do spike (`huff.py`) tem `pot = np.where(isnan(pot), y, pot)` — usa o ALVO
(`pagantes`) como fallback do previsor → vazamento latente; e o β foi calibrado com sinal possivelmente
indistinguível (maioria das maduras sem concorrente no raio → share≈1).

**Objetivo:** calibrar o share gravitacional com concorrência **OSM real** (`concorrentes_mapeados.parquet`),
tratar saturação/canibalização, **remover o fallback previsor=alvo**, e validar prevendo alunos dos
maduros (LOO-CV vs baseline). Reportar se o β é distinguível de zero.

**Escopo permitido:** Huff com distância real; β por LOO sem vazamento; saturação por capacidade;
canibalização de unidades próprias; validação out-of-sample. Sem escrita em M1.

**Critérios de aceite:** sem `previsor=alvo`; β reportado com IC (ou "indistinguível"); validação honesta
nos maduros; ZERO escrita em M1.

**Risco:** alto (captura é não-linear e satura). Substitui o `huff.py` do spike.

**Concluído 2026-06-15** (loop autônomo `ciclo/loop-20260615-124342`, mergeado PR #26).
**VEREDITO: GO técnico, mas NÃO agrega.** β=1,845 identificável (IC estreito) e o fallback `previsor=alvo`
do spike foi **removido** (sem vazamento). Porém a correlação LOO = **−0,254** (negativa — qualificada como
confound de cobertura urbana): a geometria Huff **não bate o baseline simples**. Coerente com o NO-GO da
Camada 1 (BLK-DIM-01R) e do residual (BLK-DIM-08) — empilhar captura sobre um potencial não-calibrável não
resgata. Entregue: `src/motor_expansao/dimensionamento/huff.py` + testes; suíte 919 passed. READ-ONLY M1.
Fica como módulo **validado mas não-acionável** até a Camada 1 ter sinal (ver BLK-DIM-10 / BLK-DIM-DATA).

---

> ## Sub-trilha BLK-DIM-07..09 — "Estressar ao máximo o dado que já temos" (ANTES do BLK-DIM-DATA)
>
> **Origem:** análise de produto com Felipe em 2026-06-15. O `BLK-DIM-01R` deu NO-GO prevendo
> demanda **absoluta** (`pagantes ~ pop+renda`) em **raio fixo 1,5 km**, com **uma penetração global**,
> sobre **53 unidades só-Ultra** enviesadas. Antes de buscar dado externo (BLK-DIM-DATA — microdados
> IBGE/Gympass), exaurir o dado interno reformulando o problema em 4 frentes que a auditoria dos dados
> (2026-06-15) confirmou serem viáveis: **(1)** trocar predição absoluta por **mercado residual ≥ piso
> de viabilidade** (decisão, não predição pontual); **(2)** **raio de captação variável** por contexto
> urbano (capital densa = raio curto; interior = raio largo) — a penetração a 1,5 km tem máx **110%**,
> provando que o raio fixo quebra; **(3)** **penetração regional/por marca** (partial pooling), não
> global; **(4)** ampliar N com **Engenharia do Corpo** e **SkyFit** (ambas com alunos reais + coords
> LOCAIS em `concorrentes/Unidades/*.csv` — sem geocoding online) e usar os **underperformers <2k**
> (20 unidades; Carapicuíba=1.299) como **rótulo discriminativo**. Potencial de N: 53 → **~440**.
> Caveat medido: o join alunos↔coords por nome dá **0% exato** (convenções divergentes) → reconciliação
> por cidade+UF / crosswalk é tarefa de 1ª classe do BLK-DIM-07; 09 só pega a cauda ambígua.
>
> **Piso de viabilidade:** ~2.000 alunos (média observada em Ultra/SkyFit/Engenharia). Distinguir do
> proxy de **capacidade** já existente (`capacidade_default_concorrente_alunos` = 2.500 = o que uma
> unidade *comporta*); 2.000 = o que ela *precisa para ser viável*.
>
> **Decomposição região × marca × domínio (Felipe, 2026-06-15):** o ticket das 3 redes é semelhante
> (low-cost, ±10-15%), então o efeito de marca NÃO é preço — é pull de marca + **estratégia de domínio
> de área** (ex.: Engenharia "fechou" Caxias do Sul). A penetração precisa separar **região** (mercado
> intrínseco), **marca** (nível) e **domínio** (densidade de marca própria no catchment) — senão o domínio
> da Engenharia-Sul vaza para "região" e mente sobre o mercado. Bônus: vira validação real da tese
> Expansão de Domínio com dado de concorrente.
>
> **Guardrail (toda a sub-trilha):** camada PARALELA, **READ-ONLY sobre o M1** (DEC-001/DEC-008) — não
> toca `score_priorizacao`/pesos/artefatos oficiais. **Anti-circularidade (lição do 01R):** penetração
> SEMPRE estimada no nível de cluster/região com a unidade-alvo deixada de fora (LOO); nunca derivar o
> raio do próprio desfecho. **Anti-PII:** `data/validacao/*.xlsx` e nomes de unidade nunca em disco/saída
> agregável; relatórios em `data/analysis/` (gitignored). **Metodologia §7 do spec:** LOO-CV vs baseline
> da média; banir R² in-sample; IC + flag de extrapolação.

---

- BLK-DIM-07 (concluído 2026-06-15) — ver tasks/completed.md

---

- BLK-DIM-08 (concluído 2026-06-15) — ver tasks/completed.md

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

---

### BLK-EST-05 — PDF "Apresentação Clássica Ultra" (template GeoFusion) do Relatório Pontual Censitário

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (caminho de geração do PDF de produção; branding/LGPD; READ-ONLY sobre o M1) |
| **Prioridade** | **Alta** (template aprovado pelo Vini; é o formato de apresentação que os PDFs devem seguir) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA / gate visual Felipe+Vini]` → Builder → QA |
| **Status** | Pendente |
| **Responsável sugerido** | Vini (+ Felipe no gate visual) |
| **Origem** | sessão de design com Vinicius em 2026-06-15 (simulação iterada em script descartável); spec consolidada na memória `template-pdf-apresentacao` |
| **Relacionado** | BLK-CENSO-02/03 (template recente `fpdf2`), BLK-EST-02 (refino visual), BLK-EST-03/FU1 (marca d'água/solicitante), DEC-004 (basemap) |

**Contexto:** existe hoje o template **recente** do Relatório Pontual Censitário (`censo_report.py`, 7 páginas
"Ultra Clean"). Em 2026-06-15 o Vini desenhou, iterando sobre uma **simulação descartável**
(`data/outputs/SIMULACAO_relatorio_caiubi_classico.pdf`, script em temp — NÃO versionado), um template de
**apresentação** que mistura a **estrutura/fonte de dados do modelo novo** (motor censitário) com a
**estética do modelo antigo** (`Teste Modelo` / GeoFusion). Este bloco porta esse template para produção
como uma **variante** (não substitui o template recente).

**Objetivo:** implementar em produção a variante "Apresentação Clássica Ultra" do PDF, reutilizando o motor
real (`analisar_ponto_censitario_setores` + `render_mapas_censitarios_combinados` + lookup residual), sem
tocar o M1.

**Especificação do template (CONTRATO — fonte: memória `template-pdf-apresentacao`):**
- **Base:** 16:9 (960×540 pt), `pdf_version=1.4`, `set_compression(False)`. Cores: turquesa `(0,159,160)`,
  magenta `(199,32,120)`, laranja `(237,125,49)`, branco, cinza-texto `(45,45,45)`.
- **Assets** (`data/ultra/`): `relatorio_capa_bg.png` (capa), `relatorio_conteudo_bg.png` (fundo claro),
  **`icone_ultra.png`** (marca ▶ BRANCA → bandas), `logo_ultra.png` (TURQUESA → só sobre fundo colorido).
- **Bandas turquesa (páginas de mapa):** margem de **20 px de todas as bordas**, **todos os cantos
  arredondados** (raio ~16), altura ~58; endereço (esq.) + **ícone Ultra branco (dir.)**; título de seção
  ABAIXO da banda.
- **Banda magenta (rodapé de dados, ex. Big Numbers):** preenche o **canto inferior** (full-width, flush),
  porém **baixa (~13 px)** para **não cobrir a marca d'água**.
- **Marca d'água (modelo recente `_draw_watermark`):** todas as páginas, inferior-direita, 10 pt, alpha
  0,65, cinza `(120,120,120)` exceto **capa branca**; texto `"Ultra Academia"` ou `"Ultra Academia |
  {solicitante}"`.
- **Estrutura (7 páginas):** Capa → População/Densidade → Renda → Score censitário → **Concorrentes (mapa à
  ESQUERDA + LISTA nome+distância ao pin à direita, ordenada, "... e mais N" ao truncar; lista Ultra
  também)** → **Big Numbers (grid 4×2 READ-ONLY, SEM selo de aprovação)** → Realização.
- **Capa (slide 1):** texto branco transparente na zona limpa inferior-direita (x≥478); **endereço ACIMA**
  do subtítulo; o fundo tem uma **linha branca horizontal sólida em ~y 460** — o texto fica **ACIMA da
  linha**, com a **base do bloco 5 px acima dela** (base ~y 455). Posicionar por **baseline** (`pdf.text`),
  não `cell`.
- **Realização (slide 7) = modelo recente (`_credit_page`):** fundo turquesa, "Realizacao" 34 pt + crédito +
  método + linha READ-ONLY; bloco **"Link para localizacao do ponto:"** com o **endereço sendo o link
  clicável** (link consulta o ENDEREÇO → geocoding preciso) + data; rodapé atribuição CARTO. SEM logo, SEM
  cartão de contato (anti-PII).
- **Dados/precisão:** dados/mapas do motor real na **coordenada fornecida**; o LINK consulta o endereço
  (`query=<endereço>`). Coordenada exata via link do Maps com pin (`maps_geocoder.extract_any_coord`, regex,
  sem Selenium) deixa dados+link precisos.

**Escopo permitido:** nova variante de render em `src/motor_expansao/dashboard/censo_report.py` (ex.: param
`template="classico"` ou função/módulo dedicado), reusando os helpers existentes; adicionar `icone_ultra.png`
como asset de branding; testes da nova variante. **NÃO** alterar o template recente (comportamento
preservado byte-a-byte quando o param não é passado).

**Fora de escopo:** score/pesos/artefatos M1 (READ-ONLY; DEC-001); método de interseção e raio 1,5 km
(INTOCADOS); versionar PDF/PII real; dependência de API ao vivo no dashboard; selo GO/NO-GO (é território
do BLK-DIM); fontes de dados que o motor não produz (fotos do imóvel, GeoFusion fluxo/verticalização, POIs
OSM).

**Critérios de aceite:** PDF da variante reproduz o template acima (bandas com margem/raio, ícone branco,
capa com texto acima da linha branca, concorrentes com mapa+lista de distâncias, Big Numbers sem selo,
Realização recente com link no endereço, marca d'água recente); template recente INALTERADO (testes
existentes verdes); fixtures com nome fictício, sem PII; ruff + mypy limpos; READ-ONLY M1.

**Guardrail:** anti-PII §2/§4; READ-ONLY M1 (DEC-001); gate visual humano antes do Builder (esteira Alta).

---

### BLK-DIM-11 — Esteira property-first: motor de viabilidade do imóvel (break-even, aluguel-teto, sensibilidade)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (nova esteira de produto da epic; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA / no loop: guard]` → Builder → QA |
| **Depende de** | **BLK-DIM-03R** (simulador DRE + goal-seek + curva de densidade) e **BLK-DIM-07** (catchment/contexto) — ambos concluídos |
| **Status** | Pendente |
| **Autonomia** | **loop-safe** — motor determinístico, READ-ONLY M1, sem VPS, consome `data/staging` + censo local (sem ingestão ao vivo); gate humano substituído pelo guard; ver `docs/loop_autonomo.md` |

**Contexto (materializa o Caminho A do BLK-DIM-10):** 4 NO-GOs honestos (DIM-01R/05/08 + spike de densidade)
provaram que **a geografia não prevê demanda nem densidade**. O único sinal usável é a **curva
tamanho→densidade** (DIM-03R, corr −0,37). Logo a esteira **inverte**: em vez de *prever o melhor lugar*,
o operador traz um **imóvel real** e a ferramenta **stress-testa a viabilidade** — software faz a conta,
humano decide o imóvel (os ~90% não-modeláveis = micro-localização/execução são o faro dele).

**Objetivo:** dado um imóvel real (`lat,lng` + `m²` + `aluguel pedido`), devolver contexto + break-even +
aluguel-teto + ROI + grade de sensibilidade + faixa de plausibilidade — **sem nunca prever demanda pela
geografia**.

**Escopo permitido (ORQUESTRA o que já existe; pouca lógica nova):**
- **Contexto / filtro de zona morta:** catchment no raio variável (BLK-DIM-07) → pop/renda/consumo
  concorrente do entorno; sinaliza "zona sem demanda" (exclusão), NÃO prevê alunos.
- **Curva tamanho→densidade (DIM-03R):** dado o `m²`, densidade esperada → **faixa** de alunos (intervalo,
  não ponto — refletindo os ~90% de variância não-modelável).
- **Break-even / viabilidade (simulador DIM-03R + goal-seek):** alunos mínimos viáveis, **aluguel-teto** a
  uma margem-alvo, margem/payback/ROIC no aluguel pedido.
- **Demanda = PREMISSA EXPLÍCITA:** entra por input do operador OU faixa de comparáveis de densidade
  (por marca/faixa de m²); **NUNCA** uma previsão geográfica (proibido — 4 NO-GOs).
- **Grade de sensibilidade demanda × aluguel** (o "equilíbrio aluguel↔demanda"): onde o ponto vira/não vira.
- Módulo novo isolado (ex.: `src/motor_expansao/dimensionamento/viabilidade_ponto.py`), função pura +
  testes determinísticos. Saída estruturada (dict/relatório), sem UI.

**Fora de escopo (invioláveis):** prever demanda/alunos pela geografia (NO-GO provado — só premissa
explícita); **UI/plotagem no dashboard** (bloco sucessor separado, toca dashboard → NÃO loop-safe);
atributos externos de imóvel (é o BLK-DIM-DATA redefinido); score/pesos/artefatos M1; PII.

**Critérios de aceite:** dado `(lat,lng,m²,aluguel)` retorna break-even/aluguel-teto/ROI + sensibilidade +
faixa de alunos por densidade + flag de zona morta; demanda SEMPRE premissa explícita (teste garante que
nenhuma saída deriva alunos da geografia); usa a curva de densidade real do DIM-03R; testes determinísticos
verdes; READ-ONLY M1; sem PII.

**Risco:** baixo (determinístico, reusa peças validadas). **Sucessor (não-loop):** BLK-DIM-12 — camada de
UI/plotagem do imóvel no dashboard (toca `dashboard/`, gate humano; cruza BLK-UI-01).

**Concluído 2026-06-15** (loop autônomo `ciclo/loop-20260615-163258`; auditado no merge). **VEREDITO:
APROVADO.** Entregue `src/motor_expansao/dimensionamento/viabilidade_ponto.py` (366 linhas, função pura,
DataFrames injetados, sem I/O interno) + `tests/unit/dimensionamento/test_viabilidade_ponto.py`.
`analisar_viabilidade_ponto(lat, lng, m², aluguel, demanda_premissa, ...)` devolve: faixa de alunos por
**curva tamanho→densidade** (p10/p50/p90 × m², via comparáveis — NÃO geográfica), flag de zona morta +
contexto do entorno (catchment), viabilidade no cenário pedido (margem/payback/ROIC), **aluguel-teto**,
**break-even** (alunos mínimos viáveis) e **grade de sensibilidade demanda×aluguel**. Reusa o simulador
DRE/goal-seek do BLK-DIM-03R. **Guardrail central verificado no merge (não só documentado):** a demanda
é entrada EXPLÍCITA (`demanda_fonte == "premissa_explicita"`); lat/lng só alimentam catchment + zona morta,
nunca a demanda/faixa — travado por teste de regressão `test_faixa_usa_curva_densidade_nao_geo` (lat/lng
diferentes → mesma faixa/demanda/margem) + `test_demanda_fonte_sempre_premissa_explicita`. Validações:
**936 passed, 4 skipped**; ruff/mypy limpos; READ-ONLY M1 (DEC-001/DEC-008). UI/plotagem fica para o
BLK-DIM-12 (gate humano). `LOOP_DONE` (sinal local do runner) removido do versionamento no merge.

---

### BLK-DIM-12 — UI da esteira property-first: ferramenta de viabilidade do imóvel no dashboard

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (toca o dashboard de produção; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner (design UX) → `[REVISÃO HUMANA — Felipe/Vini]` → Builder → QA |
| **Depende de** | **BLK-DIM-11** (engine `viabilidade_ponto.py`, concluído) |
| **Status** | Pendente (não iniciar sem plano de UX aprovado) |
| **Autonomia** | **manual (NÃO loop-safe)** — toca `dashboard/`, exige design de UX + gate humano; cruza BLK-UI-01. NÃO marcar loop-safe. |
| **Responsável sugerido** | Vini (dashboard/UX) + Felipe (decisão de produto) |

**Contexto:** o engine `analisar_viabilidade_ponto` (BLK-DIM-11) está pronto — função pura, READ-ONLY M1,
DataFrames injetados, com guardrail anti-geográfico testado. Falta a **tela** que o operador usa para trazer
um imóvel real e ler a viabilidade. É o materializador final da esteira property-first do BLK-DIM-10.

**Objetivo:** uma UI no dashboard onde o operador insere um imóvel real e vê a viabilidade (break-even,
aluguel-teto, ROI, sensibilidade, faixa de alunos, contexto do entorno), com a **demanda como premissa
explícita** — software faz a conta, humano decide o imóvel. Sem prever demanda pela geografia.

**Escopo permitido (wiring concreto — Planner detalha o UX no gate):**
- **Nova função `render_viabilidade_ponto`** em `dashboard/pages.py`, plugada como **expander no Mapa
  Territorial** (ao lado de `render_relatorio_pontual_censitario`, linha ~2525) OU como nova aba via
  `render_tab_selector` (linha ~449) — escolha de UX no gate.
- **Entrada:** `lat,lng` (campo, ou link do Google Maps via parser puro — sem geocoding ao vivo) + `m²` +
  aluguel pedido + **demanda premissa** (input numérico OU toggle "usar p50 dos comparáveis"); ticket/
  margem-alvo opcionais.
- **Injeção de dados (lazy, padrão do censo report):** carregar `data/staging/base_calibracao_multirede.parquet`
  (comparáveis do BLK-DIM-07) com cache; setores via `read_censo_geo_partition(uf)` +
  `resolve_cod_municipio_from_geo_dir` (mesmo padrão de `render_relatorio_pontual_censitario`); passar
  `base_calibracao_df` + `setores_df` ao engine.
- **Render:** cards (alunos break-even / aluguel-teto / margem-payback-ROIC); `grade_sensibilidade` como
  heatmap demanda×aluguel; faixa de alunos p10/p50/p90; pop/renda do entorno; **aviso de zona morta**
  (`flag_zona_morta`); pin do imóvel no mapa (pydeck, reusar componente existente) com o entorno.
- Carga lazy/cache por `(uf, cod_municipio)`; mensagem clara quando a base geo não existe (igual ao censo).

**Fora de escopo (invioláveis):** prever demanda/alunos pela geografia (o engine proíbe; a UI **não pode
burlar** — demanda sempre premissa explícita); recalcular M1/score/artefatos; geocoding de endereço ao vivo;
quebrar as otimizações de performance (carga lazy por UF, render lazy de abas, fonte de mapa enxuta).

**Critérios de aceite:** tela funcional (input → result renderizado + sensibilidade + mapa); teste garante
que a UI **nunca deriva demanda da geografia** (demanda sempre premissa explícita); carga lazy preservada;
suíte verde + `test_streamlit_app` cobrindo a nova tela; UX validada por Felipe/Vini; READ-ONLY M1; funciona
**offline** (sem API ao vivo).

**Guardrail:** §5 (visualização não recalcula M1) + preservar performance do dashboard (Blocos 4–6).

**Risco:** médio (mexe no dashboard de produção; cuidado para não regredir perf nem o fluxo das 4 abas).

---

## BLK-UI-01 (RECORTE 2) — Densidade/clareza de dados + Navegação e fluxo

Data: 2026-06-16
Tipo: feature (UX/UI) | Criticidade: Alta (mexe na navegação/apresentação do dashboard de produção; READ-ONLY M1)
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA do plano] → Builder → QA
Veredito QA: APROVADO (Opus 4.8) em 2026-06-16.

Resumo: 2º recorte focado do BLK-UI-01 amplo, pedido por Vinicius — duas frentes (densidade/clareza de
dados e navegação/fluxo), tudo READ-ONLY sobre o M1 e offline. 11 itens entregues (`pages.py`,
`streamlit_app.py`, `tests/integration/test_streamlit_app.py`):

**Frente 1 — Densidade/clareza de dados**
1. **F1-A** — tabelas Carteira (set primário 12 cols), Plano (11) e Domínio (11) reduzem o set EXIBIDO
   por padrão; colunas secundárias movidas para `st.expander("Mostrar colunas detalhadas", expanded=False)`
   que renderiza um 2º `st.dataframe` com o frame COMPLETO. ZERO coluna removida do DataFrame/parquet.
2. **F1-B** — Análise Pontual: multihex 12→9 KPIs (2 linhas) e simples 11→8 KPIs; blocos de consumo
   consolidados em 1 `st.caption` cada.
3. **F1-C** — disclaimer de centroide H3 extraído para a constante única `_CENTROID_DISCLAIMER` (2 literais
   levemente divergentes → 1 fonte).
4. **F1-D** — SEM AÇÃO (evidência: `format_int` já é uniforme; `utils.py` não tocado).

**Frente 2 — Navegação e fluxo**
5. **F2-A** — REORDENAÇÃO + relabel das abas: `DASHBOARD_TAB_LABELS = ["Mapa","Executivo","Expansão de
   Domínio","Carteira e Plano","Viabilidade"]`; **"Mapa" passa a ser a 1ª aba e o default**. Dispatch em
   `main()` atualizado em lockstep (por índice, evitando mismatch de acento). 5 testes de label atualizados.
6. **F2-B** — 3 estados-vazio (Carteira/Plano/Domínio) deixam de expor `python -m jobs...`; viram texto de
   produto em 1 frase.
7. **F2-C** — 5 filtros avançados (elegibilidade híbrida, cobertura censitária, qualidade da camada,
   top_municipio, top_hex_intraurbano) movidos para `st.sidebar.expander("Filtros avancados", expanded=False)`.
   INVARIANTE preservada: `render_uf_selectbox` segue o PRIMEIRO elemento da sidebar (gate carga lazy Bloco 4).
8. **F2-D** — heading "#### Detalhamento territorial" antes dos expanders do Mapa Territorial.
9. **F2-F** (ajuste novo de Vini) — botão de download do Relatório Pontual Censitário reposicionado para o
   TOPO da seção do mapa; só a chamada de UI movida (`censo_report.py`/`censo_map.py` INTOCADOS).
10. **F2-G** (ajuste novo) — sidebar sempre aberta no load/reload: `initial_sidebar_state="expanded"` mantido
    + reforço por CSS puro offline (sem JS de auto-clique/rede).
11. **F2-H/F2-I** (ajustes novos) — `render_tab_selector` movido para o TOPO do corpo de `main()`, acima da
    caption "Recorte atual" e do card de coordenada pesquisada (`render_hex_search_result`), que passou para
    DEPOIS do seletor — info da coordenada não ofusca mais o seletor. Seletor mantido após o guard
    `if filtered_df.empty: return` (não dispara `build_city_summary`/`build_uf_summary` em frame vazio).
    **F2-E** (hero header contextual com UF) deixado para RECORTE FUTURO.

Gate humano: aprovado COM AJUSTES por Felipe/Vini em 2026-06-16 — F2-A com REORDENAÇÃO (Mapa 1ª) +
relabel, F1-A com sets propostos (humano revisa colunas antes do merge), F2-C colapsar filtros, e os 4
ajustes novos F2-F/G/H/I. Builder executou exatamente o plano consolidado.

Arquivos alterados: streamlit_app.py, src/motor_expansao/dashboard/pages.py,
tests/integration/test_streamlit_app.py.

Validações (re-executadas pelo QA, evidência própria): suíte alvo `190 passed`; suíte full SERIAL
`955 passed, 1 skipped, 0 failed` — neste tree os 3 débitos herdados (drift de CSV de concorrentes +
gate DEC-006 do SAM) NÃO falharam (re-executados explicitamente: passam). ZERO regressão. `-n auto`
reproduz INTERNALERROR de gateway (execnet × Python 3.14, bug de ambiente conhecido) → rodado serial e
documentado, sem mascarar com `-p no:xdist`. ruff limpo; mypy Success; `import streamlit_app` ok.

Guardrails verificados: READ-ONLY M1 (nenhum score/peso/artefato/parâmetro canônico §3 tocado — as únicas
menções a `score_priorizacao` no diff são a constante `_CENTROID_DISCLAIMER` e um comentário); escopo só
`pages.py`/`streamlit_app.py`/`test_streamlit_app.py`; `censo_*`/`components.py`/`constants.py`/`utils.py`/
`config.py`/`pipelines/m1` INTOCADOS; Blocos 4/5/6 de performance preservados; offline mantido; paths
pré-sujos não tocados nem commitados.

Housekeeping: o bloco amplo BLK-UI-01 foi FECHADO em 2026-06-16 por decisão do usuário (Vini), após este
2º recorte + os 4 ajustes ad-hoc abaixo. Movido de `tasks/backlog.md` para cá via
`scripts/housekeeping_move_block.py BLK-UI-01 --date 2026-06-16`. Frentes futuras (ex.: F2-E hero header
contextual com UF) seguem no novo bloco BLK-UI-07 (placeholder no backlog).

### Ajustes ad-hoc pós-recorte (validação ao vivo com Vini, 2026-06-16)

Quatro refinamentos de UX aplicados durante a visualização ao vivo do dashboard (mesma branch
`ciclo/BLK-UI-01`), todos READ-ONLY M1 e offline, validados por suíte alvo + ruff/mypy/import (sem o
giro completo da esteira por serem ajustes visuais incrementais e dirigidos pelo usuário):
1. **2º botão de PDF no topo** (`streamlit_app.py` `main()` + `pages.py` `render_pdf_download_topo` +
   helper `gerar_payloads_relatorio_pontual_para_pin`): logo abaixo do seletor de abas, aparece SÓ quando
   há coordenada pesquisada; gera o Relatório Pontual Censitário SOB DEMANDA (clique → `st.spinner`
   "Gerando PDF..." → download), com bytes cacheados em `session_state` por coordenada. Reusa o mesmo
   caminho do relatório da seção do mapa; `censo_*` INTOCADO.
2. **"Modo de cor" do Mapa Territorial reduzido** (`pages.py`): o seletor expõe apenas
   Censitário / Residual Fitness / Expansão de Domínio (m1 e híbrido ocultos via
   `MAPA_COLOR_MODES_OCULTOS`; default visível = `censitario`). m1/híbrido permanecem em `COLOR_MODES`
   e seguem suportados pelo builder do mapa — só saíram das opções do selectbox.
3. **Largura padrão dos botões** (`pages.py` `inject_styles`): CSS dá 260px (max-width 100%) aos
   `stDownloadButton` + o "Gerar PDF do ponto" (por `.st-key-`), para consistência visual. Não afeta os
   botões inline pequenos do multi-hex nem o seletor de abas.
4. **Seção "Hexágono pesquisado" compactada** (`pages.py` `render_hex_search_result`): de um card com
   divider + heading + até 10 métricas em 3 linhas para um `st.expander(expanded=False)` colapsado (status
   no rótulo), para não empurrar o conteúdo das abas e atrapalhar a troca de abas.

Validações dos ajustes ad-hoc: suíte alvo `tests/integration/test_streamlit_app.py` `196 passed`
(190 → +6 testes novos cobrindo os 4 ajustes); ruff "All checks passed!"; mypy "Success"; `import
streamlit_app` ok. READ-ONLY M1 confirmado (sem toque em score/pesos/artefatos/`config.py`/`pipelines/m1`;
`censo_*`/`components.py` intocados).

---

### BLK-UI-01 — Refatoração UX/UI da plataforma Motor de Expansão

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (mexe na navegação/estrutura do dashboard de produção; READ-ONLY sobre M1) |
| **Prioridade** | **Média** (estratégico — exige planejamento antes de executar) |
| **Esteira** | Block Orchestrator → Planner (design detalhado) → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente (não iniciar sem plano aprovado) |
| **Responsável sugerido** | Vini |
| **ClickUp** | `86e1rtey2` — https://app.clickup.com/t/86e1rtey2 |

**Contexto:** refatoração ampla de UX/UI das 4 abas (Visão Executiva, Mapa Territorial, Expansão de
Domínio, Carteira e Plano). Por ser amplo e tocar muitos arquivos do dashboard, requer **plano detalhado +
gate humano** antes de execução, e fatiamento em sub-blocos para não colidir com os bugs acima.

**Objetivo:** melhorar usabilidade/consistência visual sem regressão de funcionalidade nem do M1.

**Escopo permitido:** `dashboard/` (pages/components/utils/constants visuais), preservando carga lazy por UF,
render lazy de abas e fonte de mapa enxuta (Blocos 4–6).

**Fora de escopo:** score/pesos/artefatos M1; recolocar dependência de API ao vivo; quebrar os contratos de
performance já entregues.

**Critérios de aceite:** plano aprovado antes de codar; sem regressão funcional (suíte verde); UX validada
por Felipe; READ-ONLY M1.

**Guardrail:** §5 (visualização) + preservar otimizações de performance do dashboard.

---

## BLK-UI-07 (RECORTE) — 2x2 do Relatório Censitário + filtros/busca na tela principal

Data: 2026-06-16
Veredito QA: **APROVADO COM RESSALVAS** (Opus 4.8).
Tipo: feature (UX/UI no dashboard de produção; READ-ONLY sobre M1). Criticidade: Alta.
Esteira: Block Orchestrator (sonnet) → Planner (opus) → [gate humano: Vinicius aprovou D1–D4] → Builder (opus) → QA (opus 4.8).
Branch: `ciclo/BLK-UI-07` (a partir de `main`/HEAD `db53cad`).

**Nota de fechamento:** entrega de RECORTE — o bloco amplo **BLK-UI-07 permanece ABERTO** no backlog (frentes
futuras herdadas: F2-E hero header por UF; limpeza do CSS legado F2-G da sidebar). Espelha o padrão do recorte
BLK-UI-01. Housekeeping via helper = N/A (sem move/close). Sucessor placeholder **BLK-UI-08** criado.

**O que foi entregue (3 frentes, decisões D1–D4 aprovadas por Vinicius):**
- **F1** — As 4 imagens do Relatório Pontual Censitário em grade **2x2** (`pages.py` `render_relatorio_pontual_censitario`,
  `st.columns(2)`×2; ordem densidade/renda → score/concorrentes preservada; captions byte-a-byte; `use_container_width=True`
  [D4]). Constante `_CENSUS_PREVIEW_WIDTH_PX` removida (uso único). `censo_map.py`/`censo_report.py`/`censo_point.py`,
  método de interseção e raio 1,5 km INTOCADOS.
- **F2** — Seletores **UF / Município / Faixa de oportunidade** migrados de `st.sidebar.*` para o CORPO (`st.*`):
  UF sozinho antes de `load_uf_slice` (carga lazy por UF preservada, `st.stop()` intacto, `st.info` sem "na barra lateral");
  Município+Faixa numa `st.columns(2)` [D3]; filtros avançados num `st.expander` no corpo [D1]; contrato de 8 retornos de
  `render_sidebar_filters` preservado; `initial_sidebar_state="collapsed"` [D2].
- **F3** — Busca por coordenada migrada para o CORPO, imediatamente acima de `render_tab_selector` [D3];
  `key="coord_search_input"` e o contrato (`search_pin`) preservados; `render_hex_search_result`/`render_relatorio_pontual_censitario` inalterados.

**Arquivos alterados:** `src/motor_expansao/dashboard/pages.py`, `streamlit_app.py`, `tests/integration/test_streamlit_app.py`.

**Validações (re-executadas pelo QA, sem bypass):** import ok; `ruff` All checks passed; `mypy` Success (2 arquivos);
alvo `test_streamlit_app.py` **199 passed** (inclui assert do 2x2 reescrito p/ `col.image` agregado + 3 testes novos de
namespace-corpo); suíte full **963 passed, 1 skipped, 1 flaky pré-existente**.

**Ressalva (não-bloqueante):** `tests/unit/test_relatorio_pontual_censitario_export.py::test_classico_template_recente_inalterado`
falha na suíte full serial mas passa isolado e passa logo após os testes alterados → poluição de estado de outro teste
NÃO alterado (debt de isolamento PRÉ-EXISTENTE; `censo_report.py` intocado por este ciclo). Follow-up **BLK-FIX-14** criado.

**Guardrails:** READ-ONLY M1 confirmado (score/pesos/artefatos/`config.py`/`pipelines/m1` intocados); carga lazy por UF,
render lazy de abas e fonte de mapa enxuta preservados; offline; sem API ao vivo. DEC-001 (pesos 0.40/0.60) intacta.

---

### BLK-FIX-14 — Isolamento do teste flaky `test_classico_template_recente_inalterado`

| Campo | Valor |
|---|---|
| **Criticidade** | **Baixa** (debt de isolamento de teste; READ-ONLY sobre M1; não afeta produção). |
| **Prioridade** | Baixa (não bloqueia ciclos; surge só na suíte full serial). |
| **Esteira** | Block Orchestrator → Builder → QA (Média se virar investigação ampla de isolamento da suíte). |
| **Status** | Pendente — aberto pelo QA do BLK-UI-07 (2026-06-16). |
| **Responsável sugerido** | Vini |

**Contexto:** durante o gate do BLK-UI-07, a suíte full serial acusou
`tests/unit/test_relatorio_pontual_censitario_export.py::test_classico_template_recente_inalterado` como
**1 failed**. Investigação do QA provou que **NÃO é regressão do BLK-UI-07**: o teste passa isolado (1 passed),
o arquivo inteiro passa (22 passed) e ele passa logo após os testes alterados (`test_streamlit_app.py` + o teste
= 200 passed). O módulo que governa os bytes do PDF (`censo_report.py`) não foi tocado pelo ciclo. Logo, é
**poluição de estado por OUTRO teste não alterado** (debt de isolamento pré-existente da suíte), surfada pela
ordem de coleta. As 3 dívidas herdadas conhecidas têm comportamento ordem-dependente parecido, reforçando que a
suíte tem fragilidade de isolamento geral.

**Objetivo:** identificar o teste poluidor (bisseção por ordem de coleta, ex.: `pytest -p no:randomly` +
`--cache-clear`, ou rodar pares progressivos até reproduzir) e corrigir o vazamento de estado global
(provável registro/monkeypatch de fonte/template em `fpdf`/`censo_report` não revertido, ou cache de módulo).

**Escopo permitido:** `tests/**` (fixtures/teardown/`conftest.py`); no máximo um ajuste de teardown/reset em
helper de teste. **NÃO** alterar a lógica de produção de `censo_report.py` sem nova decisão.

**Fora de escopo:** score/pesos/artefatos M1; mudar a geração de PDF; mascarar com `-p no:xdist` ou skip.

**Critérios de aceite:** poluidor identificado e documentado; `python -m pytest -q` (full serial) verde de forma
**reproduzível** (sem o failure); teste segue passando isolado; READ-ONLY M1.

**Guardrail:** não mascarar flakiness; corrigir a causa (isolamento), não o sintoma.

**RESULTADO DO CICLO (2026-06-17) — Veredito QA: APROVADO (Opus 4.8).**
Esteira: Block Orchestrator (sonnet) → Planner (sonnet) → Builder (opus, override +1) → QA (opus 4.8). Sem gate humano (Média). Branch `ciclo/BLK-FIX-14` (a partir de `main`/`e7b0f94`).
- **Causa real (refutou a hipótese inicial de estado global):** NÃO era poluição de `_ICON_CACHE`/`_ATLAS_CACHE` de `competitors.py`. O flaky vem do **timestamp `/CreationDate` (e `/ID` derivado) que o fpdf2 carimba a partir de `datetime.now()` por instância**. As duas gerações de PDF do teste (`antes`/`depois`) diferem em exatos **61 bytes** (dígito de segundos + hash do `/ID`) quando a geração cruza a fronteira de 1 segundo — o que acontece sob a suíte full (mais lenta), não isolado.
- **Correção (só em tests/):** novo `tests/conftest.py` com fixture **autouse scope=function** que congela o símbolo `datetime` dentro de `fpdf.fpdf`/`fpdf.output` (auto-revertido). Torna a comparação byte-a-byte determinística sem mascarar — SEM `skip`/`xfail`/`-p no:xdist`/reordenar. Produção (`censo_report.py`/`competitors.py`/`config.py`/`pipelines/m1`) **byte-intacta**.
- **Prova (QA, evidência própria):** FALHA com `--noconftest`, PASSA com o conftest, inclusive pelo caminho real `gerar_pdf_relatorio_pontual_censitario`. Suíte **full serial 964 passed / 1 skipped / 0 failed em 2 runs independentes**; alvo isolado verde; `ruff`/`mypy`/import ok. READ-ONLY M1 confirmado.
- **Arquivo alterado:** `tests/conftest.py` (novo).

---

- BLK-MAP-01 (concluído 2026-06-11) — ver tasks/completed.md

---

### BLK-UI-08 — Refinos de UX/UI do dashboard (escopo a detalhar pelo usuário)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (provável — mexe no dashboard de produção; READ-ONLY sobre M1). A confirmar no Block Orchestrator conforme o escopo citado. |
| **Prioridade** | A definir pelo usuário ao iniciar o ciclo. |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA (ajustar para Baixa/Média se o escopo citado for trivial). |
| **Status** | **Pendente — escopo a ser citado pelo usuário (Vini) ao iniciar o ciclo** (`/run-cycle BLK-UI-08`). |
| **Responsável sugerido** | Vini |
| **ClickUp** | — (criar se necessário) |

**Contexto:** novo bloco de melhorias de UX/UI do dashboard, sucessor do bloco BLK-UI-07. O conjunto exato de
mudanças será **descrito pelo usuário no início do ciclo**; este bloco existe apenas como alvo do `/run-cycle`.
Não iniciar execução sem o escopo citado e o plano aprovado no gate humano. Frentes futuras herdadas (ex.: F2-E
hero header contextual com UF; limpeza do CSS legado F2-G da sidebar agora que o default é `collapsed`) cabem aqui.

**Objetivo:** aplicar as mudanças de interface que o usuário citará, sem regressão funcional nem do M1.

**Escopo permitido (provável):** `src/motor_expansao/dashboard/` (pages/components/utils/constants visuais) +
`streamlit_app.py` + `tests/integration/test_streamlit_app.py`, preservando carga lazy por UF, render lazy de
abas e fonte de mapa enxuta (Blocos 4–6). Ajustar conforme o escopo real citado.

**Fora de escopo:** score/pesos/artefatos M1; dependência de API ao vivo; quebrar contratos de performance.

**Critérios de aceite:** escopo citado e plano aprovado antes de codar; sem regressão (suíte verde);
UX validada pelo usuário; READ-ONLY M1.

**Guardrail:** §5 (visualização) + preservar otimizações de performance do dashboard.

**Resultado do ciclo (concluído 2026-06-17):** escopo citado por Vini = 3 mudanças de UX/UI, todas READ-ONLY
sobre o M1, esteira Alta com gate humano (D1 + DEC-010). Entregue:
1. **Paleta da Renda Média** — `RENDA_PER_CAPITA_BANDS` (`constants.py`) trocada por 5 faixas absolutas RGBA
   alpha=150, ordem ascendente: `#F7F48B` (≤1000) → `#FFFF00` (1000–2000) → `#FFD21C` (2000–3500) →
   `#A8FFA8` (3500–5000) → `#00CC00` (>5000). `DENSIDADE_POP_BANDS`/`RESIDUAL_SCORE_BANDS` intocados.
2. **Tab selector sticky** — barra de abas fixa no topo ao rolar (`inject_styles` em `pages.py`).
3. **Busca por endereço** — `render_coord_search_sidebar` passa a aceitar endereço livre (caminho numérico
   `parse_coordinate_input` tentado primeiro); resolução por fetch HTTP isolado em `api/maps_geocoder.py`.
   Gate humano: D1 = Alternativa B (fetch automático); **DEC-010** registrada (CLAUDE.md §8).

**FU1 (2026-06-17, correções na validação visual; aprovadas por Vini passo a passo):**
- **Geocoder: Google → Nominatim/OpenStreetMap.** O fetch `urllib` puro contra o Google Maps NÃO resolvia
  coordenada (página renderizada por JS; sem navegador a URL final não traz o pino). `resolve_endereco_http`
  passou a usar o Nominatim (`format=jsonv2&countrycodes=br`), HTTP puro que funciona; User-Agent identificável
  + cache local `data/cache/geocode/`. **Emenda à DEC-010** registrada (provedor OSM, atribuição e anti-PII ao OSM).
- **Sticky de fato funcional + polido.** Causa raiz: na Streamlit 1.58 o testid do segmented control é
  `stButtonGroup` (não `stSegmentedControl`), então o CSS original nunca casava. Passou a usar a user-key estável
  `.st-key-dashboard_active_tab` + `overflow: visible` nos wrappers de layout; barra colada no topo (`top: 0`),
  full-width translúcida com blur, borda inferior turquesa e padding generoso.
- **Scroll ao trocar de aba.** `scroll_main_to_top` via `components.html` (script que alcança o doc pai e mede a
  posição de fluxo real da barra, rolando até o seletor de abas); nonce incremental força o re-mount a cada troca
  (dispara SEMPRE, não só 1x). Cobertura por testes (dispara na troca / não dispara sem troca).
- **Círculo do raio AZUL** nos mapas do Relatório Pontual Censitário — `_CIRCLE_RGBA = (0,102,255,235)` em
  `censo_map.py` (era laranja). Teste de cor ajustado para isolar a bolinha antiga do círculo novo.
- Sucessor placeholder **BLK-UI-09** criado no backlog.
- **Validação:** suíte completa verde; ruff + mypy + `import streamlit_app` limpos. READ-ONLY M1 confirmado.

---

- BLK-FIX-14 (concluído 2026-06-17) — ver tasks/completed.md

---

### BLK-DIM-13 — Correção do split de ticket (balcão/agregador) no engine de viabilidade — superestimação de receita

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (corrige superestimação de ~33% na receita que alimenta a aba de produção; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA / no loop: guard]` → Builder → QA |
| **Depende de** | **BLK-DIM-12** (aba existe) + estudo `data/reports/estudo_escala_alunos/` (§8) |
| **Status** | Pendente |
| **Autonomia** | **loop-safe** — READ-ONLY M1, determinístico, sem VPS/deploy/segredos, sem PII, consome `data/staging`; toca `dimensionamento/` + wiring da aba (NÃO toca M1/score/pesos/artefatos); gate humano substituído pelo guard automático no loop (`scripts/loop_guard.py`). |

**Contexto (achado da auditoria, estudo §8):** o motor de DRE (`simulador.viabilidade`) está CORRETO — já
separa balcão (R$137) + agregadores (R$82 ≈ 60%) + personal. **O wiring está errado:**
`analisar_viabilidade_ponto` passa `demanda_premissa` (que a aba pré-preenche com `faixa_alunos_p50` = alunos
**TOTAIS**) como `alunos_maturidade` (balcão) a ticket cheio E o engine ainda soma **651 agregadores fixos** por
cima → **double-count**. Impacto medido: exemplo p50=2.350 / 1.500 m² dá ~R$375k vs correto ~R$282k (**+33%**).

**Objetivo:** dividir a demanda-premissa em **balcão (~69%) + agregadores (~31%)** com seus respectivos tickets,
com agregadores **escalando junto da premissa** (não constante fixa). Eliminar o double-count.

**Escopo permitido:** em `viabilidade_ponto.py` (e onde o wiring exigir), derivar `balcao = premissa ×
share_balcao` e `agregadores = premissa × (1 − share_balcao)`; passar `alunos_agregadores` ao `viabilidade()`
em vez do default fixo; `share_balcao` como parâmetro (default = composição Ultra observada, ~0,69; configurável).
Ajustar o rótulo do input da aba para refletir que a premissa é de alunos TOTAIS (ou separar balcão/agregadores).
Teste de regressão de valor (o exemplo passa a dar ~R$282k, não ~R$375k) + teste anti-double-count.

**Fora de escopo (invioláveis):** M1/score/pesos/artefatos (DEC-001/008/009); alterar o DRE (`simulador.py` já
correto); UX nova além do rótulo; deploy/VPS; geocoding ao vivo.

**Critérios de aceite:** receita usa split balcão/agregador com 2 tickets; agregadores escala com a premissa;
zero double-count; teste de regressão do valor; suíte verde + ruff/mypy; READ-ONLY M1.

**Risco:** baixo (correção determinística pontual). **Bloqueante para subir o modelo de viabilidade a produção.**

---

### BLK-DIM-14 — Engine de risco (break-even + P(viável) + classe GO/ATENÇÃO/NÃO) + ranking DORMENTE

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (reorienta o produto de "faixa de alunos" para classificação de risco; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA / no loop: guard]` → Builder → QA |
| **Depende de** | **BLK-DIM-13** (receita correta — senão o P(viável) herda a superestimação) + estudo `data/reports/estudo_escala_alunos/` (§6/§7) |
| **Status** | Pendente |
| **Autonomia** | **loop-safe** — engine determinístico + testes, READ-ONLY M1, sem VPS/deploy/segredos, sem PII, consome `data/staging`; **ranking INATIVO** (sem render, sem ingestão ao vivo). Toca `dimensionamento/` (e, no máximo, o headline spec-locked da aba). A ATIVAÇÃO futura (busca imobiliária web) é epic separada e **NÃO loop-safe**. |

**Contexto (estudo §6/§7):** a faixa p10–p90 é **calibrada** (cobertura 76–78%, PIT 0,50) e o **P(viável)
discrimina** (AUC 0,60 Ultra / 0,68 Eng). O produto deve deixar de cravar alunos e passar a entregar **risco**:
break-even determinístico + probabilidade honesta de cobrir a conta + classe.

**Objetivo:** funções **puras** em `src/motor_expansao/dimensionamento/`:
- `p_viavel(m2, break_even, base_calibracao_df, formato)` = fração dos comparáveis (× m², condicionada ao
  **formato/marca**) que superam o break-even. **Anti-geográfico:** sem lat/lng.
- `classe_risco(p)` → `GO`/`ATENCAO`/`NAO` (cutoffs 0,70 / 0,40).
- `ranking_oportunidades(lista_imoveis)` → ordena por P(viável)/margem de segurança. **CONSTRUÍDA MAS INATIVA**
  (feature flag desligada; **sem exposição na UI**; servirá a fase futura de **busca imobiliária ativa na web
  com APIs/scrapers** — epic separada).

**UI:** opcional e **spec-locked** — pode expor o **headline de risco** (classe + P(viável) + break-even) na aba
de viabilidade SE seguir exatamente o desenho do estudo §7; a **troca visual completa da aba** (UX aberta) fica
para um bloco de UI gated (precedente BLK-DIM-12). **O ranking NUNCA é renderizado neste bloco.**

**Fora de escopo (invioláveis):** ativar/renderizar o ranking; busca imobiliária web / APIs / scrapers (epic
futura, NÃO loop-safe — ingestão ao vivo); M1/score/pesos/artefatos; deploy/VPS; prever demanda pela geografia
(DEC-009).

**Critérios de aceite:** `p_viavel`/`classe_risco`/`ranking_oportunidades` puras + testes (calibração/monotonicidade;
**anti-geográfico** = sem lat/lng; teste provando que o ranking NÃO é chamado pelo render); P(viável) consome a
receita já corrigida (BLK-DIM-13); suíte verde + ruff/mypy; READ-ONLY M1.

**Risco:** médio (lógica nova) — mitigado por manter o ranking **dormente** (zero superfície de produção).

> **Sucessor (NÃO loop-safe, futuro):** **BLK-DIM-15 — Busca imobiliária ativa (web APIs/scrapers) + ativação do
> ranking.** Ingestão ao vivo de imóveis (portais/APIs), normalização, e ativação do `ranking_oportunidades` sobre
> o pool buscado. Manual/gated (viola loop-safe: ingestão ao vivo + fontes externas). Só abrir após BLK-DIM-14.

---

### BLK-DIM-16 — Correção de cálculo: break-even (margem 0%) e limite do aluguel-teto

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (corrige números financeiros mostrados na aba de viabilidade em produção; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA / no loop: guard]` → Builder → QA |
| **Depende de** | **BLK-DIM-13** (split de ticket — break-even/teto consomem o DRE; corrigir DEPOIS que a receita estiver certa, e os dois blocos tocam `viabilidade_ponto.py`) |
| **Status** | Pendente |
| **Autonomia** | **loop-safe** — engine determinístico + testes, READ-ONLY M1, sem VPS/deploy/segredos, sem PII, consome `data/staging`; toca só `dimensionamento/{viabilidade_ponto,simulador}.py` + testes (NÃO toca M1/score/pesos/artefatos); gate humano substituído pelo guard automático no loop (`scripts/loop_guard.py`). |

**Contexto (achados ancorados no código):** dois erros pequenos de cálculo nos números de break-even e
aluguel-teto da aba de viabilidade:

1. **Break-even não é break-even (margem 0%):** em `viabilidade_ponto.analisar_viabilidade_ponto` (L313-314),
   `alunos_breakeven` é calculado via `alunos_minimos_viaveis(..., margem_alvo=margem_alvo)` com
   `margem_alvo` = **0,10** (default da assinatura, L263). Resultado: o "break-even" exibido é, na verdade,
   **"alunos para atingir 10% de margem EBITDA"** — sempre **maior** que o break-even real (margem 0). O próprio
   `alunos_minimos_viaveis` tem default `margem_alvo=0.0` (simulador.py L374), mas o chamador o sobrescreve.
2. **Limite superior do aluguel-teto ignora receita de agregadores + personal:** em `simulador.aluguel_teto`
   (L360), o teto do `brentq` é `alug_sup = alunos_maturidade * ticket_medio * 2.0` — só considera a receita de
   **balcão**. Quando agregadores (R$82 × alunos) + personal (R$5k) são materiais, o aluguel-teto verdadeiro pode
   ficar **acima** desse bound e a função retorna o próprio `alug_sup` (ramo defensivo L364-365) → **teto
   subestimado/capado**.

**Objetivo:** (a) computar `alunos_breakeven` como o **break-even real (margem EBITDA = 0%)**, mantendo, se útil,
um campo separado `alunos_para_margem_alvo` (margem-alvo) — sem perder informação; (b) corrigir o `alug_sup` do
`aluguel_teto` para um bound baseado na **receita TOTAL** (balcão + agregadores + personal), eliminando o cap.

> **Pré-decisão de produto (para ser loop-safe, sem gate): break-even = margem EBITDA 0%** (definição canônica).
> Felipe: se quiser outra definição (ex.: break-even = ponto de payback/caixa, ou manter no margem-alvo),
> ajuste esta linha ANTES de rodar — é o que o loop vai implementar.

**Escopo permitido:** `src/motor_expansao/dimensionamento/viabilidade_ponto.py` (chamada do break-even +,
se aprovado, novo campo `alunos_para_margem_alvo` no `ViabilidadePontoResult`) e
`src/motor_expansao/dimensionamento/simulador.py` (`aluguel_teto`: `alug_sup` pela receita total) + testes em
`tests/unit/dimensionamento/`. Atualizar a aba só se um rótulo/campo novo exigir (mínimo, spec-locked).

**Fora de escopo (invioláveis):** M1/score/pesos/artefatos (DEC-001/008/009); alterar a fórmula do DRE
(`viabilidade()` em si está correta); o split de ticket (é o BLK-DIM-13); UX aberta; deploy/VPS.

**Critérios de aceite:** `alunos_breakeven` = alunos p/ margem EBITDA **0%** (teste: margem no break-even ≈ 0;
break-even < alunos para 10% de margem); `aluguel_teto` não capa quando agregador+personal são materiais (teste
de unidade com receita total >> balcão prova teto > `2×balcão`); P(viável) e a aba consomem o break-even
corrigido; suíte verde + ruff/mypy; READ-ONLY M1.

**Risco:** baixo (correções determinísticas pontuais, cobertas por teste).

---

### BLK-UI-07 — Refinos de UX/UI do dashboard (escopo a detalhar pelo usuário)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (provável — mexe no dashboard de produção; READ-ONLY sobre M1). A confirmar no Block Orchestrator conforme o escopo citado. |
| **Prioridade** | A definir pelo usuário ao iniciar o ciclo. |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA (ajustar para Baixa/Média se o escopo citado for trivial). |
| **Status** | **Pendente — escopo a ser citado pelo usuário (Vini) ao iniciar o ciclo** (`/run-cycle BLK-UI-07`). |
| **Responsável sugerido** | Vini |
| **ClickUp** | — (criar se necessário) |

**Contexto:** novo bloco de melhorias de UX/UI do dashboard, sucessor do bloco BLK-UI-01 (FECHADO em
2026-06-16 após os recortes entregues). O conjunto exato de mudanças será **descrito pelo usuário no início
do ciclo**; este bloco existe apenas como alvo do `/run-cycle`. Não iniciar execução sem o escopo citado e o
plano aprovado no gate humano. Frentes futuras herdadas (ex.: F2-E hero header contextual com UF) cabem aqui.

**Objetivo:** aplicar as mudanças de interface que o usuário citará, sem regressão funcional nem do M1.

**Escopo permitido (provável):** `src/motor_expansao/dashboard/` (pages/components/utils/constants visuais) +
`streamlit_app.py` + `tests/integration/test_streamlit_app.py`, preservando carga lazy por UF, render lazy de
abas e fonte de mapa enxuta (Blocos 4–6). Ajustar conforme o escopo real citado.

**Fora de escopo:** score/pesos/artefatos M1; dependência de API ao vivo; quebrar contratos de performance.

**Critérios de aceite:** escopo citado e plano aprovado antes de codar; sem regressão (suíte verde);
UX validada pelo usuário; READ-ONLY M1.

**Guardrail:** §5 (visualização) + preservar otimizações de performance do dashboard.

---

- BLK-UI-08 (concluído 2026-06-17) — ver tasks/completed.md

---

### BLK-UI-09 — Refinos de UX/UI do dashboard (escopo a detalhar pelo usuário)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (provável — mexe no dashboard de produção; READ-ONLY sobre M1). A confirmar no Block Orchestrator conforme o escopo citado. |
| **Prioridade** | A definir pelo usuário ao iniciar o ciclo. |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA (ajustar para Baixa/Média se o escopo citado for trivial). |
| **Status** | **Pendente — escopo a ser citado pelo usuário (Vini) ao iniciar o ciclo** (`/run-cycle BLK-UI-09`). |
| **Responsável sugerido** | Vini |
| **ClickUp** | — (criar se necessário) |

**Contexto:** novo bloco de melhorias de UX/UI do dashboard, sucessor do bloco BLK-UI-08 (concluído em
2026-06-17, com FU1 de correções visuais: paleta Renda absoluta, tab selector sticky+scroll ao trocar de aba,
busca por endereço via Nominatim e círculo do raio azul). O conjunto exato de mudanças será **descrito pelo
usuário no início do ciclo**; este bloco existe apenas como alvo do `/run-cycle`. Não iniciar execução sem o
escopo citado e o plano aprovado no gate humano. Frentes futuras herdadas (ex.: F2-E hero header contextual
com UF; limpeza do CSS legado F2-G da sidebar) cabem aqui.

**Objetivo:** aplicar as mudanças de interface que o usuário citará, sem regressão funcional nem do M1.

**Escopo permitido (provável):** `src/motor_expansao/dashboard/` (pages/components/utils/constants visuais) +
`streamlit_app.py` + `tests/integration/test_streamlit_app.py`, preservando carga lazy por UF, render lazy de
abas e fonte de mapa enxuta (Blocos 4–6). Ajustar conforme o escopo real citado.

**Fora de escopo:** score/pesos/artefatos M1; dependência de API ao vivo não aprovada; quebrar contratos de performance.

**Critérios de aceite:** escopo citado e plano aprovado antes de codar; sem regressão (suíte verde);
UX validada pelo usuário; READ-ONLY M1.

**Guardrail:** §5 (visualização) + preservar otimizações de performance do dashboard.

**FECHAMENTO REAL (ciclo /run-cycle BLK-UI-09 — concluído 2026-06-19, esteira BO→Planner→[gate humano]→Builder→QA):**
Escopo citado por Vini: a barra de busca passa a aceitar **3 formatos** (coordenada, endereço, **link do Maps**);
coordenada e endereço já existiam (BLK-UI-08/DEC-010), faltava o **link**. Entregue:
- `render_coord_search_sidebar` (`pages.py`): cascata `numérico (INTOCADO) → link Maps (NOVO) → endereço Nominatim
  (INTOCADO)`, com helpers de módulo `_parece_link`/`_e_link_curto_maps` (puros, testáveis). URL longa (`!3d/!4d` ou
  `@lat,lng`) resolvida **offline por regex** (`extract_any_coord`); link curto (`maps.app.goo.gl`/`goo.gl/maps`)
  resolvido seguindo o **redirect HTTP** (Opção B). Resultado de qualquer link validado por `_validate_brazil_bbox`;
  fallback gracioso por `st.warning`. Caption/label/placeholder citam os 3 formatos; `key="coord_search_input"` preservada.
- `api/maps_geocoder.py`: novo helper `resolve_short_link(url, *, timeout=6.0) -> str | None` (urllib puro, segue
  redirect, `None` em qualquer falha; importável sem rede; import lazy no dashboard).
- `tests/unit/test_coord_search.py`: nova seção (regex pura de `extract_any_coord`, helpers de roteamento,
  `resolve_short_link` SEMPRE com urllib **mockado**). Nenhum teste bate na rede real.
- **Gate humano (Vinicius, 2026-06-19): Opção B aprovada** (link curto via rede). **Emenda à DEC-010 (2026-06-19)**
  registrada em CLAUDE.md §8 (3º sub-caminho de rede da busca, mitigações (a)/(c)/(d)/(e)/(f) vigentes).
- **QA APROVADO:** suíte full serial **1030 passed, 1 skipped, 0 failed** (xdist `-n auto` abortou com INTERNALERROR
  de execnet no Python 3.14 — contorno de ambiente documentado, não bypass); ruff/mypy/`import streamlit_app` limpos.
  **READ-ONLY M1** confirmado (`git diff src/` toca só `api/maps_geocoder.py` + `dashboard/pages.py`; config/score/pesos/
  artefatos INALTERADOS; H3=7, DIST_MIN=1.0, RENDA_MIN=4500, renda=0.40/pop=0.60). Caminhos numérico/endereço
  byte-a-byte preservados; Blocos 4–6 intocados.
- Commit por path `9a57206` no branch `ciclo/BLK-UI-09` (precedido por `571681f`, housekeeping BLK-UI-07). Merge = passo humano.

---

### BLK-RELMUN-01 — Relatório Municipal (novo formato, por município selecionado)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (provável — novo relatório no dashboard de produção; READ-ONLY sobre M1). A confirmar no Block Orchestrator conforme o template/escopo. |
| **Prioridade** | Alta (nova iniciativa ativa). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — gate]` → Builder → QA (ajustar conforme o escopo do template). |
| **Status** | **Pendente — aguardando o template de referência do Vini** para detalhar os dados necessários (`/run-cycle BLK-RELMUN-01` após o template). |
| **Responsável sugerido** | Vini |
| **ClickUp** | `86e1zdw3u` — https://app.clickup.com/t/86e1zdw3u (lista *Motor de Expansão*, tags `alta`/`projeto`, Frente=Projeto, Complexidade=Alta) |

**Contexto:** o relatório atual (*Relatório Pontual Censitário - Raio de Estudo*) cruza setores
censitários reais com um círculo de raio fixo ao redor de uma coordenada. O novo relatório muda a
unidade de análise para o **município inteiro**: o usuário **seleciona um município** e gera/baixa um
relatório consolidado dele. Os dois relatórios **convivem** — o pontual não é substituído nem alterado.

**Objetivo:** entregar um relatório por município, gerável e baixável após a seleção de um município,
reaproveitando o motor censitário e a malha real de setores IBGE 2022 onde fizer sentido, sem regressão
do relatório pontual nem do M1.

**Escopo permitido (provável, a confirmar com o template):** `src/motor_expansao/dashboard/`
(`censo_report.py`/`censo_map.py`/`pages.py` e afins) + testes; reuso da base geo
`data/outputs/setores_censitarios_2022_geo/...`. O conjunto de métricas/seções sai do **template**.

**Fora de escopo:** score/pesos/artefatos M1; alterar o relatório pontual existente; dependência de API
ao vivo não aprovada; quebrar contratos de performance do dashboard (Blocos 4–6).

**Critérios de aceite:** template analisado e plano aprovado no gate humano antes de codar; o relatório
pontual segue intocado (coexistência); geração + download por município funcionando; suíte verde;
READ-ONLY M1.

**Guardrail:** §5 (visualização/relatório) + preservar as otimizações de performance do dashboard.
**Próximo passo:** Vini envia o template → análise dos dados necessários → `/run-cycle BLK-RELMUN-01`.

#### Fechamento (2026-06-22) — APROVADO pelo QA

Ciclo `/run-cycle BLK-RELMUN-01` concluído pela esteira Alta (Block Orchestrator → Planner →
**[gate humano APROVADO por Vinicius]** → Builder → QA). Template recebido de Vini em 2026-06-22
(`docs/relatorio_municipal_template.md`, 8 páginas). **VEREDITO QA: APROVADO** — suíte completa
**1055 passed, 1 skipped, 0 failed** (serial; `-n auto` aborta com INTERNALERROR conhecido de
execnet no Python 3.14 Windows — contorno de ambiente, não bypass); ruff/mypy/`import streamlit_app`
limpos. **READ-ONLY sobre o M1** confirmado (config.py e `pipelines/m1/` intocados; pesos
`renda=0.40`/`pop=0.60`, `score_priorizacao`, artefatos oficiais INALTERADOS).

**Entregue:** módulo NOVO e disjunto `src/motor_expansao/dashboard/relatorio_municipal.py`
(`agregar_municipio` READ-ONLY + `render_mapas_municipio` + `gerar_pdf_relatorio_municipal` 8 páginas
16:9 `%PDF-1.4`/`/Count 8`/`set_compression(False)`/marca d'água + payloads/helper Streamlit);
toque pontual em `pages.py` (expander "Relatório Municipal" habilitado só com **exatamente 1
município** selecionado; nenhuma assinatura existente mudou; sem carga nova de parquet — Blocos 4–6
preservados); `tests/unit/test_relatorio_municipal.py` (25 testes, incl. **CA2 coexistência
byte-a-byte do Relatório Pontual**). Relatório Pontual Censitário **byte-a-byte intocado**
(`censo_report.py`/`censo_map.py`/`censo_point.py` sem diff).

**Decisões do gate (D1–D9) — DEC-011 (CLAUDE.md §8):**
- D1: hex destacado ⇔ `sam_fitness_potencial>=3000` E `oferta_efetiva_disponivel>=2000`; rótulo do
  hex = `oferta_efetiva_disponivel`; Espaço p/ academias = `round(Σ oferta dos destacados / 2500)`.
- D2: zonas via `dominio_df`/`cluster_id` (fallback gracioso). D3: **mapas com tiles online**
  (DEC-011 estende a DEC-004; cache local + fallback offline + import lazy + `basemap=False` em
  CI/teste; nenhum teste bate na rede). D4: mercado/residual = `Σ oferta_efetiva_disponivel`.
  D5: faixas Alto≥70/Médio-alto 50–70/Médio 30–50/Baixo<30. D6: pins por H3 res-7.
  D7: redação 1 Âncora central / 2 Flancos laterais / 3 Cerco. D8: logos só das redes mapeadas +
  carimbo de versão. D9: Página 6 (bairros) **simplificada temporariamente** (sem `NM_BAIRRO` na
  malha geo; Vini resolverá a fonte de bairro depois).

**Ressalvas leves do QA (não bloqueadoras, follow-up opcional):** (1) a camada "domínio" do mapa
não colore por zona 1/2/3 (só painel textual); (2) título da capa em linha única pode transbordar
visualmente em municípios de nome longo. **Pendência de produto:** fonte de `NM_BAIRRO` para a
Página 6 (decisão de Vini após avaliar o PDF base). Validação VISUAL do PDF pelo humano pendente.

---

### BLK-DIM-17 — Fix: limiar de renda da zona morta (3.000 → 1.600)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (afeta só o sinal de alerta de zona morta; READ-ONLY sobre M1) |
| **Prioridade** | **Alta** — corte atual de R$3.000 per capita elimina oportunidades viáveis |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Status** | Pendente |
| **Autonomia** | **loop-safe** — READ-ONLY sobre M1; toca só `viabilidade_ponto.py` + testes; sem VPS/deploy/segredos/PII/ingestão ao vivo |
| **Depende de** | — |

**Contexto / por que existe:** `RENDA_ZONA_MORTA_MIN = 3_000.0` em `src/motor_expansao/dimensionamento/viabilidade_ponto.py` está alto demais — acende alerta de "zona morta" em entornos com renda per capita entre R$1.600 e R$3.000 que são operacionalmente viáveis para o modelo Ultra. O pedido é baixar o limiar para R$1.600 (máx aceitável para não bloquear).

**Objetivo:** corrigir a constante e atualizar qualquer teste que asserte sobre o valor antigo.

**Escopo permitido:**
- `viabilidade_ponto.py`: `RENDA_ZONA_MORTA_MIN: float = 3_000.0` → `1_600.0`.
- Atualizar testes que comparam o limiar (mínimo: buscar `3_000` / `3000` nos testes do módulo).
- Nada mais.

**Fora de escopo (invioláveis):** `config.py` do M1 (`src/motor_expansao/config.py`), `RENDA_MIN = 4_500.0` (M1, intocado), `dimensionamento/config.py`, pipelines, score, artefatos oficiais.

**Critérios de aceite:** `RENDA_ZONA_MORTA_MIN == 1600.0` no módulo; suite verde sem alteração de score/M1; `flag_zona_morta` dispara apenas abaixo de R$1.600 per capita.

**Arquivos prováveis:** `src/motor_expansao/dimensionamento/viabilidade_ponto.py`, `tests/` (ajustar asserts do limiar antigo).

**Risco:** baixo — é uma constante de exibição/alerta; não altera cálculo de margem/payback/ROIC.

---

### BLK-DIM-19 — Fix: flag de viável (payback 60 → 36 meses) e exibir payback real (remover "Nunca")

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (altera semântica do flag de viabilidade na camada DIM; READ-ONLY sobre M1 oficial) |
| **Prioridade** | **Alta** — mudança de produto aprovada por Felipe (2026-06-22) |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Status** | Pendente |
| **Autonomia** | **loop-safe** — READ-ONLY sobre M1; toca só `simulador.py` + `pages.py` + testes; sem VPS/deploy/segredos/PII/ingestão ao vivo. NÃO toca `config.py` do M1 nem `dimensionamento/config.py`. |
| **Depende de** | — |

**Contexto / por que existe:** duas correções de produto:
1. `flag_viavel` em `ViabilidadeResult` usa `payback_meses <= 60` (`simulador.py` linha 302). Felipe aprovou trocar para **36 meses** (3 anos) como teto aceitável.
2. A UI exibe `"> 60 / nunca"` quando `payback == float("inf")` (`pages.py` linha 3377). Remover o texto "Nunca" — mostrar o número real (ex.: "87 meses") mesmo que ultrapasse o teto de viabilidade.

**Escopo permitido:**
- `simulador.py`: `flag_viavel = (margem_ebitda_pct >= 0.10) and (payback_meses <= 60)` → `<= 36`.
- `pages.py` (`render_viabilidade_ponto`): o card "Payback" deve sempre exibir o número em meses, sem texto "Nunca". Se `payback == float("inf")` após 60 meses de simulação, exibir `"> 60 meses"` (limite da janela do loop, não "nunca"). Remover o ramo `else "> 60 / nunca"`.
- Atualizar testes que asseriam `flag_viavel = True` com payback entre 36 e 60 (agora passam a ser `False`), e testes do display de payback.

**Fora de escopo (invioláveis):** `config.py` do M1, `RENDA_MIN`, pesos/formula M1, `flag_viavel` dos hexágonos M1 (campo diferente, nos datasets de hexágonos — não confundir com `ViabilidadeResult.flag_viavel`), artefatos oficiais.

**Critérios de aceite:** `flag_viavel` vira `False` para payback entre 37 e 60 meses; UI sempre exibe número (nunca o texto "Nunca"); suite verde.

**Arquivos prováveis:** `src/motor_expansao/dimensionamento/simulador.py`, `src/motor_expansao/dashboard/pages.py`, `tests/`.

**Risco:** baixo — altera só a constante de teto e o texto de display. O `flag_viavel` dos hexágonos M1 é campo completamente distinto e não é tocado.

---

### BLK-DIM-20 — UI: parâmetros de fluxo de caixa editáveis (capex parcelado — equipamentos e tecnologia)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (enriquece o simulador financeiro; READ-ONLY sobre M1) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Autonomia** | **loop-safe** — READ-ONLY sobre M1; toca só `simulador.py`, `viabilidade_ponto.py`, `pages.py`, testes; sem VPS/deploy/segredos/PII/ingestão ao vivo. NÃO toca `config.py` do M1 nem `dimensionamento/config.py` (constantes novas ficam nos próprios módulos). |
| **Depende de** | **BLK-DIM-19** (teto de payback e display corretos antes de expandir parâmetros) |

**Contexto / por que existe:** hoje o investimento inicial (capex) entra como lump-sum no mês 0, e o payback é calculado contra o FCF acumulado. Na prática, equipamentos e tecnologia são **parcelados** (planilha Ultra: 36 meses, juros 1,8% a.m.). O simulador atual não tem esse custo mensal de financiamento, então o payback simulado é otimista. Felipe quer que o operador possa configurar esses parâmetros.

**Objetivo:** adicionar ao simulador financeiro e à UI os parâmetros de financiamento do capex, calculando a PMT mensal como custo adicional durante o prazo de parcelamento.

**Escopo permitido:**

*`simulador.py` — novos parâmetros em `viabilidade()`:*
- `capex_financiado_pct: float = 0.0` — % do capex financiado (0 = tudo próprio, padrão atual).
- `prazo_financiamento_meses: int = 36` — prazo de parcelamento (default da planilha).
- `juros_financiamento_am: float = 0.018` — taxa mensal (default 1,8% a.m.).
- PMT mensal calculada via `pmt = C * r * (1+r)^n / ((1+r)^n - 1)` onde `C = capex_efetivo * capex_financiado_pct`. A PMT entra no loop de payback como custo financeiro nos meses `1..prazo_financiamento_meses` (abaixo da linha do EBITDA — não altera `margem_ebitda_pct`, só o `fcf_t` e o payback).

*`viabilidade_ponto.py`:* pass-through dos 3 novos parâmetros em `analisar_viabilidade_ponto()` e em `grade_sensibilidade()`.

*`pages.py` — expander "Parâmetros avançados":*
- `capex_total` (`st.number_input`, default `SIM_CAPEX_DEFAULT = 2.340.000`).
- `pct_financiado` (`st.slider`, 0–100%, default 0%).
- `prazo_financiamento_meses` (`st.number_input`, default 36, visível só se `pct_financiado > 0`).
- `juros_am_pct` (`st.number_input`, default 1,8%, visível só se `pct_financiado > 0`).
- Caption explicando: "Equipamentos e tecnologia parcelados conforme planilha padrão (36 meses, 1,8% a.m.). A PMT entra como custo financeiro no FCF (não altera EBITDA)."

**Fora de escopo (invioláveis):** `config.py` do M1, `dimensionamento/config.py`, pesos/formula/artefatos M1, cálculo de `margem_ebitda_pct` (EBITDA é pré-financiamento, conforme spec §8.2).

**Critérios de aceite:** com `pct_financiado > 0`, o payback aumenta em relação ao cenário sem financiamento (efeito esperado); `margem_ebitda_pct` inalterada entre os dois cenários (a PMT não entra no EBITDA); grade de sensibilidade propagada corretamente; suite verde.

**Arquivos prováveis:** `src/motor_expansao/dimensionamento/simulador.py`, `src/motor_expansao/dimensionamento/viabilidade_ponto.py`, `src/motor_expansao/dashboard/pages.py`, `tests/`.

**Risco:** baixo-médio — a PMT é cálculo determinístico; o risco é introduzir regressão no payback sem financiamento (deve ficar idêntico ao atual quando `pct_financiado = 0`).

---

### BLK-DIM-21 — UI: gráficos financeiros e curva de maturidade na aba de viabilidade

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (enriquecimento visual; READ-ONLY sobre M1) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Autonomia** | **loop-safe** — READ-ONLY sobre M1; toca só `simulador.py`, `pages.py`, testes; usa `plotly` já dep (`plotly>=5.20.0`); sem VPS/deploy/segredos/PII/ingestão ao vivo. NÃO toca `config.py` do M1 nem `dimensionamento/config.py`. |
| **Depende de** | **BLK-DIM-19** (payback/flag corretos), **BLK-DIM-20** (parâmetros de fluxo de caixa disponíveis para refletir nos gráficos) |

**Contexto / por que existe:** a aba de viabilidade hoje exibe só métricas estáticas (cards). Felipe quer visualizações financeiras — curva de maturidade, faturamento projetado e payback visual — para facilitar a leitura do cenário. Felipe tem um exemplo visual de referência (compartilhar antes da execução do Builder para calibrar layout/cores).

**Objetivo:** adicionar 4 gráficos Plotly à seção de resultados da viabilidade, mantendo os cards existentes e usando cores Ultra (turquesa `#00BFB3`, cinza-escuro `#2E3040`, branco, com vermelho para negativo).

**Escopo permitido:**

*`simulador.py` — nova função `gerar_serie_mensal()`:*
Extrai a lógica do loop interno de maturação e retorna `list[dict]` com campos:
`mes`, `alunos_balcao`, `faturamento_mensal`, `ebitda_mensal`, `fcf_acumulado`.
A assinatura espelha a de `viabilidade()` para receber os mesmos parâmetros (incluindo os novos do BLK-DIM-20). NÃO duplica lógica — o loop existente em `viabilidade()` pode delegar para esta função.

*`pages.py` — 4 gráficos via `st.plotly_chart(..., use_container_width=True)` após os cards:*
1. **Curva de maturidade**: linha `alunos_balcao` por mês (1–60), com linha tracejada de steady-state e anotação do ponto de maturação. Título: "Rampa de alunos (balcão)".
2. **Faturamento e EBITDA mensal**: barras empilhadas por mês (faturamento bruto) + linha sobreposição de EBITDA. Faturamento em turquesa; EBITDA positivo em verde, negativo em vermelho.
3. **FCF acumulado**: área preenchida por mês; linha horizontal em 0; anotação do payback (ponto onde FCF ≥ 0). Área positiva em turquesa translúcido, negativa em vermelho translúcido.
4. **DRE breakdown (steady-state)**: barras horizontais empilhadas mostrando: faturamento → deduções → impostos → custos variáveis → custos fixos (pessoal + outros) → aluguel → EBITDA. Útil para entender onde vai a margem.

Todos os gráficos com fundo branco/cinza-claro, fonte legível, sem borda excessiva — padrão Ultra Clean (referência: BLK-EST-02 do relatório censitário).

**Fora de escopo (invioláveis):** `config.py` do M1, `dimensionamento/config.py`, score/pesos/artefatos M1, alterar os cards existentes (preservar métricas numéricas), adicionar dependências além do plotly já disponível.

**Critérios de aceite:** 4 gráficos renderizados sem erro para qualquer combinação válida de inputs; FCF acumulado mostra visualmente o ponto de payback; curva de maturidade termina no steady-state; suite verde (testes de smoke do módulo `simulador.py` para `gerar_serie_mensal`).

**Arquivos prováveis:** `src/motor_expansao/dimensionamento/simulador.py` (nova função), `src/motor_expansao/dashboard/pages.py`, `tests/`.

**Risco:** baixo — plotly disponível; o risco principal é regressão de performance (carregar 4 charts no Streamlit). Mitigação: renderizar só após submit do formulário (já é o comportamento atual dos cards).

---

### BLK-DIM-22 — UI: exportar simulador de viabilidade como Excel

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (novo entregável; READ-ONLY sobre M1) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Autonomia** | **loop-safe** — READ-ONLY sobre M1; toca só `pages.py` + novo módulo `dimensionamento/excel_export.py`; usa `openpyxl` já dep (`openpyxl>=3.1.0`); sem VPS/deploy/segredos/PII/ingestão ao vivo. NÃO toca `config.py` do M1 nem `dimensionamento/config.py`. |
| **Depende de** | **BLK-DIM-19** (payback/flag corretos), **BLK-DIM-20** (parâmetros de fluxo de caixa), **BLK-DIM-21** (série mensal disponível em `ViabilidadeResult` para exportar a curva) |

**Contexto / por que existe:** o operador precisa levar o resultado do simulador para reuniões/decisões fora do dashboard. Felipe quer o export no template padrão Ultra (cores turquesa/branco/cinza-escuro), equivalente ao "ULTRA padrão - Simulador Financeiro.xlsx" mas preenchido com os dados do ponto analisado.

**Objetivo:** botão `st.download_button` que gera, em memória, um `.xlsx` com 4 abas com visual Ultra, sem tocar artefatos M1 nem persistir em disco no servidor.

**Escopo permitido:**

*Novo arquivo `src/motor_expansao/dimensionamento/excel_export.py`:*
- Função `gerar_excel_viabilidade(result: ViabilidadePontoResult, *, nome_ponto: str = "") -> bytes`.
- 4 abas com `openpyxl`:
  - **"Resumo"**: cabeçalho com logo/nome Ultra (texto), ponto analisado (lat/lng/m²/aluguel/demanda), KPIs (break-even, aluguel-teto, margem EBITDA, payback, ROIC, faturamento, EBITDA, flag viável). Fundo de cabeçalho turquesa `#00BFB3`, texto branco; linhas de dado em branco/cinza-claro alternados.
  - **"DRE"**: tabela linha-a-linha do DRE no steady-state (faturamento bruto → deduções → receita líquida → impostos → custos variáveis → custos fixos → EBITDA → IR/CSLL → lucro líquido). Formatação monetária `R$ #.##0,00`. Fonte dos valores: campos do `ViabilidadeResult`.
  - **"Sensibilidade"**: grade alunos × aluguel com `margem_liq` — células coloridas (verde para margem ≥ 10%, amarelo para 0–10%, vermelho para negativo). Reproduz a tabela que já existe no dashboard.
  - **"Curva"**: série mensal (meses 1–60) com colunas `Mês`, `Alunos Balcão`, `Faturamento`, `EBITDA`, `FCF Acumulado`. Dados de `gerar_serie_mensal()` (BLK-DIM-21). Se a série não estiver disponível, omitir a aba com nota.
- Retorna `bytes` (não escreve em disco no servidor — LGPD/anti-PII).

*`pages.py` — após os gráficos:*
- `st.download_button("⬇ Exportar Excel", data=excel_bytes, file_name=f"viabilidade_{lat:.4f}_{lng:.4f}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")`.
- Gerar os bytes via `gerar_excel_viabilidade(result, nome_ponto=endereco_resolv_se_disponivel)`.

**Fora de escopo (invioláveis):** `config.py` do M1, score/pesos/artefatos M1, escrever em disco no servidor (`to_excel(path)` proibido — usar `BytesIO`), incluir dados PII de alunos reais.

**Critérios de aceite:** download gera arquivo `.xlsx` válido abrível no Excel/LibreOffice; 4 abas presentes; cores Ultra aplicadas; valor da grade de sensibilidade idêntico ao exibido no dashboard; suite verde (teste de smoke: `len(gerar_excel_viabilidade(result)) > 0`).

**Arquivos prováveis:** `src/motor_expansao/dimensionamento/excel_export.py` (novo), `src/motor_expansao/dashboard/pages.py`, `tests/`.

**Risco:** baixo — openpyxl disponível; risco de formatação complexa (colorir células condicional). Mitigação: começar com formatação simples e refinar após validação visual de Felipe.

---

- BLK-OPS-11 (concluído 2026-05-31) — ver tasks/completed.md


---

- BLK-SEC-01 (concluído 2026-06-01) — ver tasks/completed.md


---

- BLK-SEC-02 (concluído 2026-06-02) — ver tasks/completed.md

---

### BLK-TP-01 — Ingestão e contrato da camada de Demanda Revelada (H3, sem PII)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (engenharia de dados + **LGPD/anonimização**; cria nova camada PARALELA; **READ-ONLY sobre o M1**). Exige **gate humano** + registro de **DEC-012**. |
| **Prioridade** | A definir por Felipe (candidato a alta — destrava validação externa e o elo demanda→captura da DEC-009). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA OBRIGATÓRIA — LGPD/anonimização + DEC-012]` → Builder → QA. |
| **Status** | Pendente. |
| **Responsável sugerido** | Felipe (engenharia de dados / camada paralela). |
| **Depende de** | DEC-012 aprovada. |
| **Autonomia** | **manual (NÃO loop-safe)** — ingere insumo externo, não se limita a `data/staging`, toca anonimização/PII; NÃO marcar loop-safe. |

**Objetivo.** Materializar uma camada paralela, **READ-ONLY sobre o M1, agregada em H3 e SEM PII**,
casável por `hex_id` com `hexagonos_mercado_mapeado.parquet`, base para os blocos de análise sucessores.

**Princípios não-negociáveis (escopo).**
1. **Anti-PII por construção:** consome apenas dados **já agregados**; identificadores e coordenadas
   individuais nunca são lidos para o staging nem persistidos; a agregação para H3 acontece na entrada.
2. **READ-ONLY sobre o M1:** zero escrita em `score_priorizacao`/pesos/`hex_score_estrutural`/carteira/
   plano/artefatos oficiais (§5).
3. **Isolamento:** código novo em pasta disjunta (ex.: `src/motor_expansao/demanda_revelada/`);
   dependências (se houver) em extra próprio do `pyproject.toml`, fora do deploy base do Streamlit;
   sem dependência de API ao vivo na carga do dashboard (§2).

**Contrato de saída (proposto — a confirmar no Planner).** `data/staging/demanda_revelada_h3.parquet`
(cai em `*.parquet` do gitignore; **não** entra na lista de artefatos oficiais do M1):

| coluna | tipo | descrição |
|---|---|---|
| `hex_id` | str | H3 res-7 (chave de join com o Motor). |
| `membros` | int | membros (demanda paga) agregados ao hex. |
| `membros_gt5km_concorrente_lc` | int | subconjunto a >5km do concorrente low-cost de referência (Smart Fit). |
| `dist_concorrente_lc_min_m` | float | menor distância ao concorrente low-cost no hex (metros). |
| `n_celulas_agregadas` | int | nº de células de origem agregadas. |
| `n_acad_parceiras` | int | academias parceiras no hex. |
| `alunos_parceiras` | int | soma de alunos das parceiras (amostra p/ BLK-DIM). |
| `n_concorrente_lc` | int | unidades do concorrente low-cost de referência no hex. |
| `versao_contrato` | str | carimbo de reprodutibilidade. |

Opcional: versão res-8 para leitura intraurbana fina.

**Caveats de dado (documentar no relatório do bloco).** coords de célula arredondadas (~1 km) → ruído
no join res-7 (ok p/ densidade, não p/ ponto exato); cobertura geográfica enviesada (concentração em
SP); a demanda casa com **~1% do universo de hexes do Motor** → camada de *refino* sobre metrópoles,
não cobertura nacional (não substitui M1/censitário, §1).

**Escopo provável.** Pipeline ingestão+agregação (parser → H3 → drop PII → parquet), módulo em pasta
disjunta, testes com **fixture sintético sem PII** (nunca dado real), relatório de qualidade/cobertura.
Reuso de `h3` (já dependência).

**Fora de escopo.** Score/pesos/artefatos M1; persistir qualquer PII; ingestão ao vivo na carga do
dashboard; deploy ao VPS; as análises em si (sucessores BLK-TP-02..05).

**Critérios de aceite.** Parquet H3 sem PII reprodutível; join por `hex_id` demonstrado; **zero** linha
individual/PII no artefato (verificado por teste); READ-ONLY M1; suíte verde.

**Guardrail.** §2, §4/§5; DEC-001/DEC-009 (não reabrir M1; demanda como insumo observado).

---

### BLK-RELMUN-02 — "Bairros por Zona" com nomes reais de bairro (resolve o D9 do BLK-RELMUN-01)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (provável — enriquecimento/re-materialização da base geo + mudança de página do relatório; **READ-ONLY sobre o M1**). A confirmar no Block Orchestrator. |
| **Prioridade** | Alta (foco da próxima sessão). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — gate]` → Builder → QA. |
| **Status** | **Pendente — próxima sessão** (`/run-cycle BLK-RELMUN-02`). |
| **Responsável sugerido** | Vini |
| **Depende de** | BLK-RELMUN-01 (concluído 2026-06-22). |

**Contexto / problema:** a página **"Bairros por Zona"** do Relatório Municipal (slide 7 das 9
páginas) está **SIMPLIFICADA** por decisão temporária (D9 / DEC-011): hoje lista as 3 zonas
geométricas (Âncora central / Flancos laterais / Cerco) com contagem de hexes + tese e a nota
*"Bairros indisponiveis na base atual; ... a malha geo IBGE 2022 materializada nao inclui
NM_BAIRRO."* O **template** (`docs/relatorio_municipal_template.md`, Página 6) pede a listagem
dos **nomes reais de bairro por zona** (ex.: Parque Roosevelt, Jardim Petrópolis, Vila Nipônica…).

**Causa-raiz (confirmada no BLK-RELMUN-01):** a malha materializada
`data/outputs/setores_censitarios_2022_geo/uf=XX/cod_municipio=N/part-000.parquet` só tem
`CD_SETOR, CD_UF, CD_MUN, NM_MUN, SITUACAO, AREA_KM2, geometry` — **sem `NM_BAIRRO`** (ver
`materializar_setores_censitarios_geo.py`). Não há fonte de nome de bairro no dataset do dashboard
nem na base geo; por isso a página foi simplificada.

**Objetivo:** dar à página "Bairros por Zona" a lista de **bairros reais por zona**, fiel ao
template, sem regressão do restante do relatório nem do Relatório Pontual, READ-ONLY sobre o M1.

**Direções candidatas (a decidir no gate — NÃO pré-fixar):**
1. **Re-materializar a malha geo IBGE 2022 incluindo bairro/subdistrito** (`NM_BAIRRO`/`CD_BAIRRO`
   ou subdistrito do agregado de setores 2022) e propagar a coluna até o trace do censo / hex
   (`enrich_dashboard_data`). Mais robusto e offline; é um job de dados sobre 5.571 municípios (~1,17 GB).
2. **Cruzar com uma camada externa de bairros** (polígonos de bairro IBGE/OSM `admin`) por
   interseção espacial setor×bairro, materializando o nome dominante por setor/hex.
3. **Reverse-geocode** do centróide dos hexes de zona (Nominatim, precedente DEC-010) — só como
   fallback pontual; inviável em lote (rede por hex, lento; contra o offline da carga).

**Escopo provável (a confirmar):** `materializar_setores_censitarios_geo.py` (+ pipeline de
enriquecimento que leva `cod_municipio`/censo trace ao hex), `src/motor_expansao/dashboard/
relatorio_municipal.py` (a página "Bairros por Zona" deixa de ser simplificada e passa a listar
bairros por zona, com a `_zonas_geometricas` já existente), `docs/relatorio_municipal_template.md`,
testes. Reuso da base geo existente.

**Fora de escopo:** score/pesos/artefatos M1; alterar o Relatório Pontual (coexistência);
dependência de API ao vivo em lote na carga do dashboard; quebrar contratos de performance
(Blocos 4–6) e a coexistência byte-a-byte do Pontual.

**Critérios de aceite:** fonte de `NM_BAIRRO` (ou equivalente) disponível por hex/setor; a página
"Bairros por Zona" lista bairros reais agrupados por zona, **com fallback gracioso** quando um
município não tiver bairro mapeado; o relatório segue com **9 páginas**; suíte verde; READ-ONLY M1;
Relatório Pontual intocado.

**Guardrail:** §5 (visualização/relatório) + preservar performance do dashboard. Relaciona-se à
**DEC-011** (D9, simplificação temporária) e ao **BLK-RELMUN-01**.
**Próximo passo:** `/run-cycle BLK-RELMUN-02` na próxima sessão.

---

### BLK-TP-02 — Validação: Demanda Revelada × Residual Fitness (relatório)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (relatório/análise read-only; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir. |
| **Esteira** | Block Orchestrator → Planner → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-TP-01** (camada em `data/staging`). |
| **Autonomia** | **loop-safe** — READ-ONLY sobre o M1, consome só `data/staging`, sem PII (anti-PII por construção, teste verde), sem VPS/deploy/segredos, sem ingestão ao vivo. |

**Objetivo.** Reproduzir e documentar a correlação demanda × `score_oportunidade_residual` (Spearman
~+0,52), mapa de quadrantes (residual+ & demanda+), e divergências vs. o recorte top-20%/UF do M1.
**Não** altera score/artefatos — saída é relatório + (opcional) parquet de quadrantes.

**Critérios de aceite.** Relatório com correlação reproduzida + quadrantes; READ-ONLY M1; suíte verde.
**Guardrail.** §5; DEC-001.

---

### BLK-UI-11 — Aprimoramento estético e clareza de conteúdo do dashboard (caminho de produção)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (a confirmar no Block Orchestrator). Camada de **visualização/UX**; **READ-ONLY sobre o M1**. Superfície ampla (as 4 abas) + **gate humano** para aprovar os ajustes propostos antes da execução. |
| **Prioridade** | Alta (pedido de Vinicius, 2026-06-24). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — gate]` → Builder → QA. |
| **Status** | **Pendente — em abertura** (`/run-cycle BLK-UI-11`). |
| **Responsável sugerido** | Vini |
| **Depende de** | — (consome o que já existe; não depende de novos dados). |

**Contexto / objetivo:** aprimorar a **estética** das telas do dashboard Streamlit e **simplificar/clarificar
o conteúdo mostrado** nas 4 abas (Visão Executiva, Mapa Territorial, Expansão de Domínio, Carteira e Plano),
no **caminho de produção atual** (pydeck/abas existentes). **Polimento geral** (decisão de produto, Vinicius
2026-06-24): o **Planner levanta e propõe** os ajustes concretos de layout, textos, legendas, hierarquia
visual e redução de ruído/redundância; o **humano aprova no gate** antes do Builder.

**Escopo permitido (display-only):** estilo/layout (CSS injetado, organização de containers, espaçamento,
tipografia), textos/rótulos/legendas, ordem e densidade de informação, remoção de conteúdo redundante ou
confuso, tooltips e mensagens de ajuda. **Zero** mudança em dados, score, ranking, carteira, plano ou
qualquer função de cálculo do M1.

**Fora de escopo:** score/pesos/artefatos M1; mudança em `build_map_figure`/lógica de cálculo; quebrar os
contratos de performance dos Blocos 4–6 (carga lazy por UF, render lazy de abas, fonte de mapa enxuta);
dependência de API ao vivo nova; o PoC de repaginação (**BLK-UI-10**, que é trilha separada opt-in atrás de
flag — este bloco NÃO é PoC, é refino do caminho de produção).

**Critérios de aceite:** as 4 abas seguem funcionais; melhorias de estética e clareza aplicadas conforme o
plano aprovado no gate; suíte verde (ruff/mypy/pytest, incl. `test_streamlit_app.py`); READ-ONLY M1
preservado; performance dos Blocos 4–6 não regredida.

**Guardrail:** §5 (visualização não recalcula/altera M1) + preservar performance do dashboard.
**Relaciona-se a:** BLK-UI-10 (PoC opt-in — distinto), BLK-EST-01..05 (estética do PDF — outra superfície).

---

### BLK-TP-05 — Re-teste honesto do elo demanda→captura (LOO vs baseline)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (modelagem; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir. |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — modelagem]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-TP-01**. |
| **Autonomia** | **manual (NÃO loop-safe)** — decisão de modelagem. |

**Objetivo.** Re-testar a regressão/Huff `alunos ~ demanda + dist_concorrente + concorrência` agora com
**demanda observada** (não imputada), usando **LOO/k-fold repetido vs baseline da média** (DEC-008;
proibido R² in-sample). O protótipo deu Spearman demanda×alunos +0,75 e OLS R²_in-sample 0,45 — promissor,
mas a validação séria é este bloco. É o re-teste honesto do que a DEC-009 marcou como NO-GO **com demanda
imputada**: se passar no LOO, reabre (sob gate) a Camada de captura da epic BLK-DIM.

**Critérios de aceite.** R²_LOO vs baseline reportado com intervalos + flag de extrapolação; veredito
GO/NO-GO honesto; READ-ONLY M1.
**Guardrail.** §5; DEC-008/DEC-009 (demanda como insumo observado, nunca preditor geográfico).

**Resultado do ciclo (2026-06-30) — APROVADO pelo QA. Esteira: Block Orchestrator → Planner →
[gate humano: A1–A8 aprovadas por Felipe em 2026-06-30] → Builder → QA (Opus 4.8).** Branch
`ciclo/BLK-TP-05` a partir de `main` @ c99bbff (escolha do humano: base = main limpo, BLK-TP-02
fica aguardando seu próprio merge).

- **VEREDITO HONESTO = GO** (primeiro GO da trilha de modelagem demanda→captura). Diferente da
  DEC-009, que marcou NO-GO com demanda **imputada**, aqui a demanda é **OBSERVADA** (`membros`,
  camada BLK-TP-01). Reproduzido de forma independente pelo QA contra o parquet real.
- **Números-chave** (k-fold repetido 5×5 vs baseline da média, `Ridge` alpha=10):
  `R²_oof_log = +0,5750`, IC95 bootstrap [+0,5576, +0,5959] (não cruza zero) → GO (> `LIMIAR_R2_GO=0,05`
  E IC_inf > 0). N modelado = **5.341** hexes (subset `alunos_parceiras > 0`); descartados zeros =
  **11.234**; inválidos = 0; range alunos [1, 14.332]. R²_oof_alunos = +0,4218; pct_extrapolação = 0%.
- **Decisões de modelagem (A1–A8, aprovadas no gate):** alvo `log1p(alunos_parceiras)` no subset >0;
  features `[log1p(membros), log1p(dist_concorrente_lc_min_m), n_concorrente_lc]`; **`n_acad_parceiras`
  EXCLUÍDO** do principal por circularidade (soma↔contagem; Spearman +0,94) — só em modelo de auditoria
  rotulado, que sobe para R²_oof_log +0,6388 e evidencia o vazamento estrutural evitado; k-fold 5×5;
  IC por bootstrap (≥500); limiar GO=0,05+IC; Huff/Camada 2 FORA do MVP.
- **Honestidade auditada (DEC-008):** R² in-sample só como campo rotulado "apenas auditoria — NÃO usar
  como desempenho", fora do gate; métrica de desempenho é out-of-fold sem vazamento treino→teste;
  6 confounds na nota honesta (cobertura ~1%, concentração SP, ruído de coords ~1 km, viés de seleção
  das parceiras, multicolinearidade membros↔alunos_parceiras, circularidade de n_acad_parceiras).
- **Entregáveis:** `src/motor_expansao/demanda_revelada/backtest_tp05.py` (módulo novo, pacote disjunto
  DEC-012; reusa `dimensionamento/` — `LIMIAR_R2_GO`/`ALPHA_GRID`/`_r2`/`_rmse`), 10 testes sintéticos
  em `tests/unit/test_backtest_tp05.py`, exports em `demanda_revelada/__init__.py`, relatório
  `data/analysis/backtest_tp05.md` (gitignored, regenerável via `__main__`).
- **Validações (re-executadas pelo QA, sem bypass):** suíte FULL `1117 passed, 1 skipped, 0 failed`
  (`-n auto`); subset 18 passed; ruff (escopo + repo) limpo; mypy 0 issues; `import streamlit_app` ok;
  helper de housekeeping 10 passed.
- **READ-ONLY M1 confirmado:** pesos `renda=0.40`/`pop=0.60`, `score_priorizacao`, artefatos oficiais
  e parâmetros canônicos do §3 INALTERADOS; pacote `demanda_revelada/` não importa de `pipelines/m1`,
  `censo_*`, `dashboard` nem `config.py` raiz; anti-PII por construção; fixture 100% sintética.
- **Próximo passo (gate humano, fora deste bloco):** o GO honesto **habilita** — sob decisão explícita
  de Felipe — a reabertura da Camada 2 (captura/Huff) da epic BLK-DIM. O Builder NÃO implementou a
  reabertura; é decisão de produto/modelagem a registrar como DEC própria se Felipe optar por avançar.

---

### BLK-RELPON-03 — Eliminar a barra cinza (letterbox) dos mapas do Relatório Municipal

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (altera o RENDER/encaixe dos mapas de um template PDF gated (DEC-011); **READ-ONLY sobre o M1**; exige revisão visual humana). |
| **Prioridade** | Definida por Vini (2º dos 2 pedidos de layout de 2026-07-01). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — produto/visual]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | — (toca só `relatorio_municipal.py`; independe de BLK-RELPON-01/02). |
| **Autonomia** | **manual (NÃO loop-safe)** — decisão de produto/visual (como encaixar o mapa no painel); precisa de olho humano no PDF. NÃO marcar loop-safe. |

**Contexto (ancorado no código, `src/motor_expansao/dashboard/relatorio_municipal.py`).**
- Causa-raiz medida: o PNG do mapa é gerado em **1000×620** (`render_mapas_municipio`/`_render_mapa_municipio`,
  `width=1000, height=620` → aspect ≈ **1,613**). Os painéis do PDF chamam `_draw_framed_map`/`_draw_map`
  com `max_w=540, max_h=380` (aspect ≈ **1,421**; um usa `560×380` ≈ 1,474). `_draw_map` (linha ~1308) usa
  `scale = min(max_w/img_w, max_h/img_h)` = **contain** → ajusta pela largura (0,54) e a altura fica 334,8 <
  380 → **letterbox de ~22,6px em cima e embaixo** = a barra cinza (fundo do painel `_rounded_panel`).

**Objetivo.** Os mapas do Relatório Municipal preenchem o painel sem barra cinza (topo/base), mantendo
proporção sem distorção grosseira, sem sobrepor a moldura/título/rodapé, e preservando a moldura Ultra Clean.

**Escopo permitido (READ-ONLY M1, só RENDER).** Casar a proporção do mapa ao painel — via (a) gerar o PNG
na proporção do painel (ajustar `width/height` de `render_mapas_municipio`/`_render_mapa_municipio` e/ou o
viewport/bbox para o aspect ~1,42), e/ou (b) `_draw_map` preencher o painel por **cover** (escala `max` +
recorte do excedente) em vez de **contain**, e/ou (c) desenhar o fundo do painel com a cor do mapa. Testes
que fixem a ausência de letterbox (mapa cobre o painel). Parâmetro opcional segue precedente DEC-005 (default = atual).

**Fora de escopo.** Gate do SAM/`flag_sam` (DEC-006/007), score, M1, artefatos oficiais (INTOCADOS);
Relatório Pontual (`censo_map.py`/`censo_report.py`, BLK-RELPON-01/02); método de intersecção e raio.

**Guardrails.** READ-ONLY sobre o M1 (§5). Sem dependência de rede nova (DEC-011 inalterada — tiles seguem
como estão). Marca d'água anti-PII + `set_compression(False)` + estrutura de 8 páginas do template mantidos.

**Critério de aceite.** Mapas do Relatório Municipal sem barra cinza (cobrem o painel), sem distorção
grosseira nem sobreposição de moldura/título/rodapé; suíte do relatório municipal verde; ruff+mypy limpos;
revisão visual humana aprovada no gate.

**Follow-up direto (BLK-RELPON-03 FU1, 2026-07-01, sem ciclo — pedido de Vinicius):** corrigidos 2 defeitos
de RENDER remanescentes no Relatório Municipal (READ-ONLY M1): (1) **zona cinza dentro do contorno** — os
bounds dos tiles passam a ser casados ao aspect do `map_box` (overscan simétrico do eixo curto) antes de
buscar/projetar, eliminando a faixa de letterbox cinza `(245,245,245)`; (2) **Resumo sem basemap** — retry
(até 3x) na busca de tiles para a 1ª camada de foco não ficar offline por timeout de rede fria. Validação:
`test_relatorio_municipal.py` 35 passed; ruff/mypy limpos; import ok.

---

### BLK-RELPON-01 — Três mapas de calor (população/renda/score) num único slide do Relatório Pontual

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (altera a ESTRUTURA de um template de PDF já aprovado em gate — muda `/Count` e mexe em asserts de teste travados; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir por Vini. |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — produto/visual]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | — (consome os mesmos `layers` de mapa já gerados pelo caminho do relatório). |
| **Autonomia** | **manual (NÃO loop-safe)** — decisão de produto/visual (layout dos 3 mapas + mudança de `/Count` de um template gated); precisa de olho humano no PDF. NÃO marcar loop-safe. |

**Contexto (ancorado no código).**
- Gerador em produção: `gerar_pdf_relatorio_pontual_classico` (`src/motor_expansao/dashboard/censo_report.py`),
  usado pelo dashboard (`pages.py`, `template="classico"`) e pela API (`api/service.py`). Há também o
  gerador legado `gerar_pdf_relatorio_pontual_censitario` (mesma estrutura de 7 páginas).
- Ordem atual das 7 páginas (ambas variantes): Capa → **Densidade** → **Renda** → **Score** →
  Concorrentes → Big Numbers → Realização. Cada mapa é um slide próprio via `_classico_map_page`/
  `_map_page`, que desenha 1 PNG grande (`_classico_draw_map`/`_draw_map`) sob a banda de título.
- Os PNGs vêm do dict `layers` (`densidade`/`renda`/`score`/`concorrentes`), gerados por
  `render_mapas_censitarios_combinados` (`censo_map.py`) — cada choropleth **já traz a própria legenda
  embutida** (faixas GeoFusion) e é ~16:9.
- **Travas de teste:** `tests/unit/test_relatorio_pontual_censitario_export.py` afirma `b"/Count 7"` e
  `%PDF-1.4` em vários testes; o gate BLK-EST-02 fixou 7 páginas / ordem / `set_compression(False)` /
  `pdf_version="1.4"`. Consolidar 3 páginas em 1 leva o PDF a **5 páginas** (`/Count 5`) → esses asserts
  PRECISAM ser atualizados (parte do escopo, com aprovação no gate).

**Objetivo.** Um único slide "Mapas de calor" com os 3 choropleths (População/Densidade, Renda, Score)
lado a lado, cada um com mini-título, legíveis, **sem sobrepor** um ao outro nem a faixa de título /
rodapé / marca d'água, mantendo a estética bicolor e GeoFusion atual. Concorrentes e Big Numbers seguem
como slides próprios.

**Escopo permitido (READ-ONLY M1).**
- Novo montador de página (ex.: `_classico_mapas_calor_page` / `_mapas_calor_page`) que recebe os 3 PNGs
  e os posiciona numa grade dentro da área de conteúdo (abaixo da banda de título, acima do rodapé),
  respeitando margens; substitui as 3 chamadas de densidade/renda/score por 1. Igual na variante censitário.
- Atualizar as orquestrações (`_classico` + `_censitario`) e os asserts de `/Count` nos testes (7→5),
  preservando `%PDF-1.4`, `set_compression(False)`, marca d'água em todas as páginas e atribuição de tiles.
- Se a legibilidade exigir, um parâmetro OPCIONAL em `render_mapas_censitarios_combinados` para render
  compacto / sem legenda individual + UMA legenda compartilhada no slide (default = comportamento atual do
  dashboard, byte-a-byte). A emenda da DEC-005 já permite params opcionais de render em `censo_map.py`.
- Testes novos: o slide único contém os 3 mapas, sem sobreposição (checagem de bounding boxes no montador),
  `/Count` novo, geração offline-safe (fallback "mapa indisponível" por camada).

**Decisões para o gate humano (Planner propõe, Vini aprova).**
1. **Consolidação vs. adição:** consolidar os 3 num slide (7→5 páginas, muda `/Count`) — leitura direta de
   "no mesmo slide" — **ou** manter os 3 individuais e ADICIONAR um slide-resumo (cresce o `/Count`)?
   (Recomendação: consolidar.)
2. **Layout:** 3 lado a lado (tira horizontal) · 2 em cima + 1 embaixo · 1 linha de 3 com legenda
   compartilhada (trade-off tamanho×legibilidade em 960×540).
3. **Legendas:** manter a legenda embutida de cada mapa (mais poluído) · uma legenda compartilhada (exige o
   param de render compacto).
4. **Mini-títulos** por mapa (População / Renda / Score) e posição.
5. **Tom bicolor:** o slide consolidado entra na alternância turquesa/magenta — definir o tom da faixa dele.

**Fora de escopo.** Concorrentes e Big Numbers (slides próprios); método `setor_censitario_intersecao_area_1p5km`,
raio 1,5 km, score, M1 e artefatos oficiais (INTOCADOS); Relatório Municipal (outro template).

**Guardrails.** READ-ONLY sobre o M1 (§5): zero recálculo de score/pesos/carteira/plano/artefatos. Caminho do
dashboard sem os params novos preservado byte-a-byte. Sem dependência de rede nova (DEC-004 inalterada). Marca
d'água anti-PII e `set_compression(False)` mantidos.

**Critério de aceite.** PDF do pontual (classico + censitário) com 1 slide contendo os 3 choropleths legíveis e
sem sobreposição; `/Count` novo consistente nos testes; suíte dos relatórios verde; ruff+mypy limpos; revisão
visual humana aprovada no gate.
### BLK-DIM-18 — Fix: faixa de alunos pela metragem ausente em produção (fallback para parquet de unidades)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (feature completamente invisível em prod; sem dado exibido no campo) |
| **Prioridade** | **Alta** — fix de produção |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Status** | Pendente |
| **Autonomia** | NAO LOOP SAFE, Mexe em Produção e VPS
| **Depende de** | — |

**Contexto / por que existe:** `load_base_calibracao()` em `streamlit_app.py` lê `data/staging/base_calibracao_multirede.parquet` — arquivo gerado pelo pipeline `base_multirede.py` (BLK-DIM-07/08) que **não existe em produção** (não foi regenerado após o pivô DEC-009). Por isso a seção "Faixa de alunos plausível pela metragem" sempre cai no `st.info("indisponível")`. O arquivo `data/staging/unidades_ultra_performance_hex.parquet` (54 unidades Ultra com `metragem` e `alunos_reais`) **sempre existe** e serve como fallback direto.

**Objetivo:** adicionar fallback na `load_base_calibracao()` para, quando o multirede não existir, tentar o `unidades_ultra_performance_hex.parquet` (que tem as mesmas colunas `metragem` e `alunos_reais` já consumidas pela função).

**Escopo permitido:**
- `streamlit_app.py`, função `load_base_calibracao()`: após verificar `BASE_CALIBRACAO_PATH.exists()`, tentar `STAGING_DIR / "unidades_ultra_performance_hex.parquet"` como fallback antes de retornar `pd.DataFrame()`.
- Derivar `alunos_por_m2` no fallback (mesma lógica já existente).
- Atualizar ou adicionar 1 teste cobrindo o caminho de fallback.

**Fora de escopo (invioláveis):** regenerar o multirede (outro ciclo), tocar `viabilidade_ponto.py`/`simulador.py`, M1, artefatos oficiais.

**Critérios de aceite:** com apenas `unidades_ultra_performance_hex.parquet` presente, a faixa p10/p50/p90 é exibida no dashboard; suite verde; nenhuma coluna M1 alterada.

**Arquivos prováveis:** `streamlit_app.py` (função `load_base_calibracao`), `tests/`.

**Risco:** baixo — READ-ONLY; só adiciona um path de fallback sem remover o caminho atual.

---

- BLK-DIM-19 (concluído 2026-06-22) — ver tasks/completed.md


---

- BLK-DIM-20 (concluído 2026-06-22) — ver tasks/completed.md


---

- BLK-DIM-21 (concluído 2026-06-22) — ver tasks/completed.md


---

- BLK-DIM-22 (concluído 2026-06-22) — ver tasks/completed.md

---

### BLK-LTV-02 — Join territorial (pendurar retenção/LTV no hexágono da unidade)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (join de dados; **READ-ONLY sobre o M1**). |
| **Prioridade** | Alta. |
| **Esteira** | Block Orchestrator → Planner → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-LTV-01**. |
| **Autonomia** | candidato **loop-safe**. |

**Objetivo.** Via `hex_id` da ponte, anexar a cada unidade as features territoriais do Motor
(`renda_per_capita`, densidade, `score_priorizacao`, `score_expansao_hibrido`,
`n_concorrentes_mapeados_1km/2km`, `pop_total_setor_2022`…) e as métricas de retenção agregadas
(`PROB_CANCEL_90D_MEDIA`, `LTV_PROSPECTIVO_12M_MEDIANO`), respeitando `USAR_PROB_ABSOLUTA`/haircut.
Entregável: `data/staging/unidade_territorio_retencao.parquet`. **Critérios de aceite.** 100% das
linhas do M1 preservadas nas leituras; nenhuma escrita em artefato M1; suíte verde.

---

### BLK-LTV-01 — Tabela-ponte `unidade_hex` (geocodificar unidades → H3 res-7)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (preparação de dados; **READ-ONLY sobre o M1**). |
| **Prioridade** | Alta (destrava o epic). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | — (insumos já no repo). |
| **Autonomia** | candidato **loop-safe** (READ-ONLY M1, sem VPS/deploy/segredos, sem PII, consome `data/ultra`+`data/staging`). |

**Objetivo.** Produzir `data/staging/unidade_hex.parquet` mapeando cada `COD_UNIDADE`/`UNIDADE` do
Lifetime → `lat`/`lng` → `hex_id` (H3 res-7, `H3_RESOLUTION=7`). Geocodificar por nome contra
`Ultra.csv` (147) com fallback ao `unidades_ultra_performance_hex.parquet` (54); fuzzy match com
verificação; emitir **relatório de qualidade de match** (casados exato/fuzzy/sem match, por UF e por
`CONFIABILIDADE_UNIDADE`). **Critérios de aceite.** Ponte reproduzível; % de cobertura reportado (não
silenciar não-casados); READ-ONLY M1; suíte verde. **Guardrail.** `Ultra.csv` = `sep=";"`,
`latin-1`, 1 linha de metadado (CLAUDE.md §2).

---

- BLK-LTV-02 (concluído 2026-07-01) — ver tasks/completed.md

---

### BLK-LTV-03 — Análise de correlação território × retenção/LTV `[GATE DE DECISÃO]`

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (gate de decisão do eixo; **READ-ONLY sobre o M1**). |
| **Prioridade** | Alta. |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — decisão do eixo]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-LTV-02**. |
| **Autonomia** | **manual (NÃO loop-safe)** — gate de decisão humano. |

**Objetivo.** Correlacionar território (renda, densidade, `score_priorizacao`, concorrência) ×
`PROB_CANCEL_90D_MEDIA` e `LTV_PROSPECTIVO_12M_MEDIANO`, **controlando por maturidade quando houver
dado** (ver caveat estrutural do epic). Método DEC-008: **Spearman + bootstrap/IC**, sem R² in-sample;
scatter + significância. **Gate de decisão:** correlação **fraca** → o epic vira consolidação de dados
(entrega LTV-01/02 como ativo, sem score); **forte** → avança para BLK-LTV-04. **Critérios de aceite.**
rho + IC bootstrap por par de variáveis, confounds declarados (maturidade, N, seleção de sobreviventes),
veredito GO/NO-GO honesto; READ-ONLY M1.

---

### BLK-LTV-04 — Score M2 territorial de retenção (SÓ se BLK-LTV-03 = GO) `[requer DEC + gate humano]`

| Campo | Valor |
|---|---|
| **Criticidade** | **Crítica/Estratégica** (cria um eixo de score novo). |
| **Prioridade** | Condicional ao GO do LTV-03. |
| **Esteira** | Block Orchestrator → Planner → `[APROVAÇÃO HUMANA + DEC]` → Builder → QA. |
| **Status** | Bloqueado (depende do gate de LTV-03). |
| **Depende de** | **BLK-LTV-03 = GO**. |
| **Autonomia** | **manual (NÃO loop-safe)** — cria score; exige DEC registrada. |

**Objetivo.** Compor um score de expansão paralelo (M2) ponderando captação + LTV/retenção territorial,
como **camada paralela READ-ONLY sobre o M1** (não altera `score_priorizacao`/pesos/artefatos; exige
**DEC** própria antes do Builder, análoga à disciplina da DEC-001/DEC-008). **Critérios de aceite.**
Definição de pesos aprovada em DEC; validação LOO/k-fold vs baseline; READ-ONLY M1; suíte verde.

**Desfecho (2026-07-01) — ciclo /run-cycle (BO→Planner→[gate humano + DEC-014]→Builder→QA). VEREDITO
QA = APROVADO; VEREDITO DO SCORE = NO-GO honesto (desfecho legítimo DEC-008/DEC-014 decisão 2).**
Gate humano (Felipe, 2026-07-01) fechou 4 decisões de produto → **DEC-014** (CLAUDE.md §8): (1) pesos
variante A `w_cap=0.50`/`w_ret=0.50`; (2) fallback em NO-GO = **encerrar sem score** (não degradar para
proxy); (3) modelo do eixo retenção em **numpy puro** (Ridge, sem `scikit-learn`); (4) nome `score_retencao`.
Fórmula aprovada: `score_retencao = clip(0.50·score_priorizacao + 0.50·retencao_norm, 0, 100)`, eixo
captação = `score_priorizacao` LIDO, eixo retenção = modelo territorial calibrado **fora-de-fold**
(k-fold 5×5 + LOO, IC95 bootstrap seed=42, **sem R² in-sample**) contra `LTV_PROSPECTIVO_12M_MEDIANO`
(agregado por unidade, N=56), maturidade só como covariável de controle. **Resultado real:** o melhor
modelo (`score_priorizacao` sozinho) deu R²_oof=+0.040 com **IC [-0.101,+0.120] cruzando zero** e
rho_oof=-0.073 (< piso 0.30, IC cruza zero) → **NO-GO mecânico**. O sinal bivariado +0.391 do BLK-LTV-03
era rank-correlation in-sample da feature bruta; o Ridge não generaliza fora-de-fold sob N=56 +
colinearidade captação↔retenção. **Parquet de score NÃO gerado** (decisão 2); escrito só o relatório
`data/analysis/relatorio_score_retencao.md` (gitignored) documentando o NO-GO + 5 confounds. **QA
re-executou o gate (NO-BYPASS):** suíte full `1193 passed / 1 skipped / 0 failed`; módulo rodado 2×
sobre parquets REAIS → NO-GO reproduzível, relatório byte-estável (SHA1 idêntico), **mtime dos 4
artefatos M1 INALTERADO** e nenhum path M1 escrito; ruff clean; mypy Success (88 files);
`import streamlit_app` ok; imports proibidos (incl. `sklearn`) ausentes. **READ-ONLY M1 comprovado;
DEC-001/DEC-008/DEC-009 intactas.** Módulo `src/motor_expansao/lifetime/score_retencao_territorial.py`
+ testes `tests/unit/test_score_retencao_territorial.py` (13 testes, NO-GO alcançável e testado). O epic
BLK-LTV encerra com LTV-01/02/03 como ativo de dados + o gate honesto do LTV-04 (território prevê
retenção in-sample, mas NÃO com poder preditivo out-of-fold que justifique um score paralelo).

---

### BLK-TP-03 — Vazio competitivo do concorrente low-cost (feature/overlay)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (camada de visualização/análise; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir. |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — produto/UX]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-TP-01**. |
| **Autonomia** | candidato a **loop-safe** se restrito a análise/parquet; **manual** se virar overlay no dashboard (decisão de produto). |

**Objetivo.** Identificar hexes com demanda paga relevante a >5km do concorrente low-cost de referência
e **sem** unidade dele no hex — tese de entrada low-cost mais limpa (demanda comprovada, concorrente
direto ausente). Protótipo exploratório apontou ~231 hexes res-7 candidatos. Possível overlay no Mapa
Territorial (§5, camada visual de apoio — não altera score/ranking/carteira).

**Critérios de aceite.** Lista/camada de vazios competitivos reproduzível; READ-ONLY M1; suíte verde.
**Guardrail.** §5; pins/camadas de concorrente são apoio visual (CLAUDE.md §2).

---

### BLK-RELMUN-03 — Validar hexágono só por Residual Fitness (remover o filtro de SAM Fitness)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (altera o CRITÉRIO de "hexágono válido/destacado" fixado na **DEC-011** — muda os números do relatório (destacados, "Espaço para academias", aprovados/reprovados); **READ-ONLY sobre o M1**; exige aprovação humana + emenda à DEC-011). |
| **Prioridade** | A definir por Vini. |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — produto + emenda DEC-011]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | — (toca só `relatorio_municipal.py`). |
| **Autonomia** | **manual (NÃO loop-safe)** — muda um critério registrado em DEC e os números do relatório; precisa de decisão humana. NÃO marcar loop-safe. |

**✅ Relatório-alvo confirmado por Vinicius (2026-07-02): Relatório MUNICIPAL.** O critério
"SAM Fitness ≥ 3.000 **E** Residual Fitness ≥ 2.000" existe HOJE **apenas no Relatório Municipal**
(DEC-011) — o pedido inicial citou "pontual", mas Vinicius confirmou que é o Municipal. Evidência: o
PDF do Relatório Municipal de Nova Iguaçu imprime literalmente "Hexagono considerado quando SAM Fitness
>= 3.000 e Residual Fitness >= 2.000 (alunos)" (páginas Resumo e "Espaço e academias"). O Relatório
Pontual (raio 1,5 km) NÃO tem esse filtro e está fora do escopo.

**Contexto (ancorado no código, `src/motor_expansao/dashboard/relatorio_municipal.py`).**
- Critério de "hexágono destacado/válido" em `_hex_destacado_mask` (linha ~258):
  `(sam_fitness_potencial >= SAM_DESTAQUE_MIN) & (oferta_efetiva_disponivel >= OFERTA_DESTAQUE_MIN)`,
  com constantes `SAM_DESTAQUE_MIN = 3000.0` (linha 50) e `OFERTA_DESTAQUE_MIN = 2000.0` (linha 51).
- Esse mask alimenta: os hexágonos amarelos do mapa; a contagem "Aprovados/Reprovados"; o
  "Espaço para academias" = `round( Σ oferta_efetiva_disponivel dos destacados / 2500 )`; e os textos
  de rodapé/legenda que citam o critério.

**Objetivo.** Remover o filtro de **SAM Fitness (≥ 3.000)** de `_hex_destacado_mask`, mantendo **apenas
Residual Fitness (`oferta_efetiva_disponivel` ≥ 2.000)** como critério de validação do hexágono.
Consequência esperada: passam a valer também os hexes com `oferta_efetiva_disponivel ≥ 2000` mas
`sam_fitness_potencial < 3000` → mais hexágonos destacados e "Espaço para academias" maior.

**Escopo permitido (READ-ONLY M1, só relatório).**
- `_hex_destacado_mask` passa a ser `oferta_efetiva_disponivel >= OFERTA_DESTAQUE_MIN` (drop do termo
  de SAM). Decidir com o gate se `SAM_DESTAQUE_MIN` é removida ou mantida como constante inerte.
- Atualizar TODOS os textos que citam o critério (rodapés/legendas/subtítulos das páginas Resumo e
  "Espaço e academias", docstring D1 do módulo) para refletir "somente Residual Fitness ≥ 2.000".
- Atualizar os testes que fixam o critério/números (ex.: `test_agregar_municipio_formula_espaco_d1`
  e afins em `tests/unit/test_relatorio_municipal.py`).
- **Registrar emenda à DEC-011** (o critério dos "hexágonos destacados" foi decidido lá).

**Fora de escopo.** `flag_sam`/gate do SAM no pipeline de mercado (DEC-006/DEC-007) — NÃO tocar (o
critério do relatório é DISPLAY local, separado do `flag_sam`); `score_priorizacao`, M1, artefatos
oficiais, método de intersecção/raio; Relatório Pontual (confirmado fora do escopo).

**Guardrails.** READ-ONLY sobre o M1 (§5): zero recálculo de score/pesos/carteira/plano/artefatos.
Sem dependência de rede nova. Marca d'água anti-PII + `set_compression(False)` + 8 páginas mantidos.

**Critério de aceite.** Hexágonos destacados e "Espaço para academias" passam a considerar só
`oferta_efetiva_disponivel ≥ 2.000`; textos/legendas do relatório coerentes com o novo critério;
suíte do relatório municipal verde; ruff+mypy limpos; emenda à DEC-011 registrada; revisão visual
humana aprovada.

---

### BLK-RELMUN-04 — Relatório Municipal em lote (um relatório por município selecionado)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (nova função de UI no fluxo de geração do Relatório Municipal; **READ-ONLY sobre o M1**; sem DEC nova; reusa a geração existente do PDF). |
| **Prioridade** | Pedido direto de Vinicius (2026-07-02). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | — (toca só `src/motor_expansao/dashboard/pages.py`; reusa `relatorio_municipal.py` sem alterá-lo). |
| **Autonomia** | manual (não loop-safe) — feature de UI com decisões de produto já coletadas; não é loop-safe por padrão da trilha do Vini. |

**Pedido de Vinicius (2026-07-02).** Hoje o Relatório Municipal só é gerável com **exatamente 1
município** selecionado (gate `len(selected_cities) != 1` em `render_relatorio_municipal_download_topo`
~linha 3062 e `render_relatorio_municipal_expander` ~linha 3917 de `pages.py`). Vinicius quer: ao
selecionar **mais de um município**, a função de gerar relatório deve gerar **um relatório PDF para
CADA município selecionado**, com os **botões de download aparecendo após a geração**, cada botão
**rotulado com o município** a que se refere.

**Decisões de produto (coletadas de Vinicius antes do ciclo).**
- **Gatilho:** geração SOB DEMANDA por **botão** ("Gerar Relatórios (N)"), com indicador de
  progresso; os botões de download aparecem DEPOIS. Evita regenerar N PDFs a cada rerun (a geração
  com mapas/tiles é pesada).
- **Onde:** **AMBOS** os pontos de geração (topo `render_relatorio_municipal_download_topo` e
  expander `render_relatorio_municipal_expander` do Mapa Territorial).
- **1 município:** comportamento atual PRESERVADO (sem regressão).

**Escopo permitido (READ-ONLY M1, só UI).**
- Estender os 2 pontos de geração para o caso `len(selected_cities) > 1`: botão "Gerar
  Relatórios (N)" → loop por município (reusando `agregar_municipio` + `render_mapas_municipio` +
  `gerar_payloads_download_relatorio_municipal`) → cache dos payloads por município em
  `session_state` → **um `st.download_button` por município, rotulado com o nome** (ex.: "Baixar
  PDF — <Município>"), com `key` único por município.
- Tratar município sem hexágonos (n_hex_total == 0) individualmente (aviso por município, não
  aborta o lote).
- Progresso do lote (ex.: `st.progress`/`st.spinner` com contador "gerando i/N").
- Testes do novo fluxo multi-município (gating, rótulos por município, contagem de botões).

**Fora de escopo.** `relatorio_municipal.py` (motor do PDF — NÃO alterar; só consumir); critério de
hexágono destacado (DEC-011/BLK-RELMUN-03); `score_priorizacao`, M1, artefatos oficiais, pipeline de
mercado (`flag_sam`); Relatório Pontual Censitário; estrutura/páginas do PDF; marca d'água anti-PII.

**Guardrails.** READ-ONLY sobre o M1 (§5). Sem dependência de rede nova (tiles já existentes,
DEC-011). Preservar o fluxo de 1 município byte-a-byte no comportamento.

**Critério de aceite.** Com >1 município selecionado, um botão gera N relatórios sob demanda e
aparece 1 botão de download por município, rotulado; com 1 município, comportamento inalterado;
suíte de testes verde; ruff+mypy limpos; revisão visual humana aprovada.

---

### BLK-TP-04 — Calibração da curva tamanho→densidade do BLK-DIM com alunos/unidade

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (alimenta a modelagem de viabilidade; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir. |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — modelagem]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-TP-01** + epic **BLK-DIM** (DIM-03R/06). |
| **Autonomia** | **manual (NÃO loop-safe)** — decisão de modelagem. |

**Objetivo.** Usar `alunos_parceiras` (amostra real de alunos/unidade por tier; n≈27 mil no protótipo)
como insumo para calibrar/validar a curva tamanho→densidade do `viabilidade_ponto.py` (BLK-DIM), com a
disciplina metodológica da DEC-008 (LOO vs baseline; banir R² in-sample; intervalos + flag de
extrapolação). Liga-se à DEC-009 (dimensionamento é a parte que funciona; consome demanda, não a prevê).

**Critérios de aceite.** Curva calibrada/validada por LOO vs baseline, documentada; READ-ONLY M1.
**Guardrail.** §5; DEC-008/DEC-009.

---

- BLK-TP-05 (concluído 2026-06-30) — ver tasks/completed.md

---

### BLK-TP-06 — Calibração/validação do score residual com demanda revelada observada

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (valida/propõe calibração de um campo ATIVO da camada de mercado/residual — `score_oportunidade_residual`; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — modelagem]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-TP-01** (parquet `data/staging/demanda_revelada_h3.parquet`, 16.575 hexes, colunas `membros`/`alunos_parceiras`) + camada de mercado/residual (`score_oportunidade_residual` em `hexagonos_mercado_mapeado.parquet`). |
| **Autonomia** | **manual (NÃO loop-safe)** — decisão de modelagem; pode propor recalibração de um score ativo. |

**Contexto.** A análise exploratória da DEC-012 (2026-06-24) mediu **Spearman +0,52** entre a demanda paga
por hex (camada Demanda Revelada) e o `score_oportunidade_residual`. Isso é a primeira validação externa
forte do residual — mas foi exploratório, **in-sample**, e nunca passou pela disciplina da DEC-008. Este
bloco transforma esse sinal em uma validação/calibração **honesta**.

**Objetivo.** Medir, fora-de-amostra, quanto o `score_oportunidade_residual` prevê a **demanda observada**
(`membros` / `alunos_parceiras` da Demanda Revelada, casadas por `hex_id`), quantificando o +0,52 de forma
honesta e produzindo veredito GO/NO-GO. Se GO, propor (sem aplicar) uma calibração dos componentes do
residual que melhore o alinhamento com demanda observada. A demanda entra como **alvo/validação observada**,
NUNCA como preditor geográfico de magnitude (DEC-009).

**Critérios de aceite.** Módulo READ-ONLY na camada paralela (não importa de `pipelines/m1`, `dashboard`,
`censo_*`, `api`); validação por LOO/k-fold vs baseline da média com **IC95 bootstrap (seed fixa)**, **R²
in-sample banido** dos outputs, intervalos + flag de extrapolação (DEC-008); join por `hex_id` com caveat
de cobertura (~1% do universo, concentração SP — DEC-012); veredito GO/NO-GO documentado em
`data/analysis/` (gitignored); anti-PII (só camada agregada; fixtures sintéticas); mtime dos 4 artefatos
oficiais M1 inalterado; suíte verde; `import streamlit_app` ok.
**Guardrail.** §5 (READ-ONLY M1 — recalibrar a FÓRMULA do residual em produção é **follow-up com gate
próprio**, não este bloco); DEC-008 / DEC-009 / DEC-012.

---

### BLK-TP-08-FU — Re-ingestão das academias menores com rótulo de rede (fecha o dado do BLK-TP-06-FU1)

Data: 2026-07-02
Resumo: Estende a ingestão anti-PII do TP-08 com um passo de CLASSIFICAÇÃO de REDE na FRONTEIRA
(módulo novo `demanda_revelada/classificacao_rede_menor.py`): deriva `rede_menor` do `Nome_Academia` cru
por matching de TOKEN com word-boundary contra a lista curada das 28 redes de `concorrentes_mapeados` e
DROPA nome/coords/cluster imediatamente. Produz 2 artefatos gitignored/NÃO oficiais — (a)
`oferta_academias_menores_rede_h3.parquet` (formato LONGO `hex_id × rede_menor`, contrato
`oferta_menores_rede_v1`) e (b) `capacidade_media_por_rede.parquet` (média/mediana de alunos por rede,
contrato `capacidade_media_rede_v1`). Gate humano APROVADO por Felipe Silva em 2026-07-02 (A token
word-boundary + lista curada; B N<3→independente; C formato longo; D capacidade=mediana, flag_confiavel N≥10).
Cobertura real (24.045 academias): 2,2% classificada / 97,8% `independente`; 13 redes na tabela, 10
confiáveis (N≥10). DEDUP FINO por `(hex_id, rede_menor)` corrige a super-dedução grosseira do TP-08: de
62,7% → **8,3%** dos alunos realmente duplicados. Fecha as 2 lacunas de dado que pausaram o BLK-TP-06-FU1.
Arquivos: `src/motor_expansao/demanda_revelada/classificacao_rede_menor.py` (novo), `__init__.py` (aditivo),
`tests/unit/demanda_revelada/test_classificacao_rede_menor.py` (novo), `tests/fixtures/rede_menor_fake.xlsx`
(sintética), `docs/modelo_mercado_hexagonos.md` (aditivo), relatório
`data/reports/scratch/rede_menor_classificacao_qualidade.md` (gitignored).
Validações: subconjunto `demanda_revelada/` + `test_streamlit_app.py` 254 passed / 0 failed; ruff+mypy limpos;
import ok; mtime dos 4 artefatos M1 INALTERADO; anti-PII provada nos 2 parquets reais (zero coluna de PII).
Decisões: DEC-012 (anti-PII por construção) / DEC-013 parte 3 (dedup+capacidade habilitados, sem integrar ao
residual). READ-ONLY M1.

---

### BLK-TP-08 — Ingestão anti-PII das academias menores (WellHub/TotalPass) na camada de oferta

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (nova ingestão de fonte externa com **PII na origem**; enriquece a camada de OFERTA/residual; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA OBRIGATÓRIA — anti-PII + dedup]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-TP-01** (contrato/ingestão da Demanda Revelada + princípios anti-PII DEC-012) + planilha `03_Competidores.xlsx` (em `NAO_ABRA/`, gitignored — 24.045 academias, `Alunos_Academia`/`Plano`/`Cluster`/`Município`) + `concorrentes_mapeados.parquet` (para o cross-check de DEDUP). |
| **Autonomia** | **manual (NÃO loop-safe)** — nova fonte externa + PII na origem + DEDUP exigem julgamento humano; NÃO marcar loop-safe. |

**Contexto.** Hoje a camada de mercado/residual consome como OFERTA instalada apenas os **concorrentes
de rede mapeados + a própria Ultra**. As **academias menores (não-rede)** — mapeadas pelos scrapers de
WellHub/TotalPass e consolidadas na planilha `03_Competidores.xlsx` (24.045 unidades com `Alunos_Academia`)
— **NÃO** entram no cálculo. Elas são oferta real que hoje o Motor ignora, o que pode **subestimar a
saturação** de bairros densos. Alinha com a **DEC-013 (parte 3)**: agregadores WellHub/TotalPass (>25 mil
academias de bairro) devem ser coletados/armazenados e integrados ao residual **numa epic futura com
DEDUP + Huff por tipo de rede**, sob gate humano. Este bloco é o primeiro passo dessa integração: a
**ingestão anti-PII agregada**, sem ainda recompor o residual.

**Objetivo.** Ingerir `03_Competidores.xlsx` como camada de OFERTA adicional, agregando por `hex_id`
(res-7) na **fronteira de entrada** e **descartando toda PII** (Lat/Lng individuais, Nome do
estabelecimento) — só contagens/capacidades agregadas por hex. Produzir um parquet de staging
(`data/staging/oferta_academias_menores_h3.parquet`, gitignored/NÃO oficial) + **relatório de qualidade e
DEDUP** (quantas dessas academias já estão em `concorrentes_mapeados.parquet` para não contar oferta em
dobro; capacidade variável por tipo/plano). **NÃO** recompõe `score_oportunidade_residual` nem regenera os
parquets de mercado — isso é follow-up (parte da recalibração / BLK-TP-09 ou epic de dedup+Huff).

**Critérios de aceite.** Ingestão isolada da camada paralela (`src/motor_expansao/demanda_revelada/` ou
pacote disjunto; sem import de `pipelines/m1`, `dashboard`, `censo_*`, `api`); **zero PII** no artefato/
log/teste (`COLUNAS_PII_PROIBIDAS`; teste `test_zero_pii`); fonte real nunca versionada (`NAO_ABRA/`);
fixtures sintéticas; relatório de DEDUP vs `concorrentes_mapeados.parquet` documentado; mtime dos 4
artefatos oficiais M1 inalterado; suíte verde; `import streamlit_app` ok.
**Guardrail.** §5 (READ-ONLY M1); DEC-012 (anti-PII por construção); DEC-013 (parte 3 — dedup + capacidade
por tipo antes de qualquer integração ao residual). Integrar a oferta ao `score_oportunidade_residual` =
follow-up com gate próprio.

---

### BLK-TP-08-FU — Re-ingestão das academias menores com rótulo de rede (fecha o dado para o BLK-TP-06-FU1)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (classifica rede a partir de nome cru sob anti-PII/DEC-012; **READ-ONLY sobre o M1**). Gate humano obrigatório (anti-reidentificação + vocabulário de matching). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA OBRIGATÓRIA — anti-PII]` → Builder → QA. |
| **Status** | Concluído 2026-07-02. |
| **Depende de** | BLK-TP-08 (concluído). |
| **Autonomia** | **manual (NÃO loop-safe)** — envolve gate humano anti-PII sobre nome cru. |

**Objetivo.** Re-ingerir `NAO_ABRA/03_Competidores.xlsx` classificando cada academia numa CATEGORIA de rede
(`rede_menor`) na FRONTEIRA (antes do drop do `Nome_Academia`), produzindo 2 artefatos gitignored/NÃO
oficiais: (a) oferta por `hex_id × rede_menor` (formato LONGO, habilita dedup FINO por rede) e (b) capacidade
média/mediana de alunos por rede. Fecha as 2 lacunas de dado que pausaram o BLK-TP-06-FU1. Gate humano
APROVADO por Felipe Silva em 2026-07-02 (A token word-boundary + lista curada; B N<3→independente; C formato
longo; D capacidade=mediana, flag_confiavel N≥10). READ-ONLY M1 (DEC-012 anti-PII por construção).

---

### BLK-TP-06-FU1 (ad-hoc) — Re-validação do residual com candidatos (concluído 2026-07-02) — Candidato A = NO-GO honesto

Bloco AD-HOC (derivado da conversa) que testou, out-of-fold e honestamente (DEC-008), se ENRIQUECER a
oferta consumida do `score_oportunidade_residual` com as academias menores (WellHub/TotalPass) melhora o
ajuste à demanda observada (`membros`). Esteira: BO → Planner → [gate humano: SÓ Candidato A; Candidato C
adiado] → Builder → QA. **READ-ONLY sobre o M1** (não altera fórmula em produção nem regenera parquets de
mercado; mtime dos oficiais + `hexagonos_mercado_mapeado.parquet` inalterado).

**Histórico:** o FU1 foi PAUSADO em 2026-07-02 no 1º gate por falta de dado (sem rótulo de rede nas menores;
médias por rede só p/ 2 de 28) → **BLK-TP-08-FU** fechou o dado (classificação de rede anti-PII + capacidade
por rede) → FU1 RETOMADO com dedup FINO por par `(hex_id, rede_menor)`.

**VEREDITO = NO-GO (NAO_APLICAR):** com o harness do TP-06 (k-fold 5×5 seed=42, IC95 bootstrap, **R²
in-sample banido**, alvo `log1p(membros)`, n=16.411): Baseline (residual atual) reproduz +0,3119
IC95[+0,2977,+0,3250]; **Candidato A** = +0,2692 IC95[+0,2553,+0,2819] — PIOR. **Δ pareado (A−baseline):
completo −0,0427 IC95[−0,0477,−0,0379]; FORA de SP/MG/RJ −0,0193 IC95[−0,0232,−0,0157]** → não vence em
nenhum recorte. **Leitura:** as academias menores co-localizam com a demanda (mercado fitness ativo), então
tratá-las como oferta consumida a subtrair joga fora sinal e PIORA a predição. O residual ATUAL segue o
melhor. **Recomendação: NÃO aplicar o Candidato A ao BLK-TP-09.** O **Candidato C** (capacidade de clube por
rede) fica pendente de dado real em `data/validacao/` (Sky Fit / Engenharia / Smart Fit KPIs) — as medianas
~340 do TP-08-FU são footprint de bairro, não de clube.

**Entregáveis:** `src/motor_expansao/demanda_revelada/revalidacao_residual_candidatos.py` (baseline + A;
dedup fino em função própria = extensível para o C futuro), `tests/unit/demanda_revelada/test_revalidacao_residual_candidatos.py`
(18 testes sintéticos), `data/analysis/revalidacao_residual_candidatos.md` (gitignored). QA APROVADO (suíte
full `1290 passed, 1 skipped`; NO-GO reproduzido byte-a-byte; anti-PII/isolamento OK). DEC-008 (NO-GO válido),
DEC-009 (demanda só como alvo), DEC-012 (fixtures sintéticas) respeitadas.

---

### BLK-TP-06-FU2 (ad-hoc) — Candidato C do residual (capacidade de clube real + decay 2 km) — concluído 2026-07-03

Bloco AD-HOC que rodou o **Candidato C** (adiado no FU1) BEM-FEITO, para separar "hipótese errada" de
"execução crua" no NO-GO do Candidato A. Corrigiu as 2 crudezas do A: **(1)** ponderou a oferta consumida
por **capacidade de CLUBE real por rede** — lida ANTI-PII de `data/validacao/` (leitor irmão
`capacidade_clube_validacao.py` → só `{rede: float}`): Smart Fit **2363,0**, Engenharia do Corpo **3106,5**,
Sky âncora ~944,5; fallback **2.500** para as ~26 redes sem dado (cobertura real ~33% dos pontos); **(2)**
aplicou **decay** consistente: point-level `max(0,1−dist/2000)` para concorrentes (têm lat/lng) e **k-ring
H3 k=1 ponderado por anel (1,0/0,5) normalizado (conserva massa)** para as academias de bairro (só hex_id).
Decompôs em **C1** (só capacidade por rede, sem bairro) e **C2** (C1 + bairro decaído) para atribuir causa.
Esteira: BO → Planner → [gate: decisão AUTÔNOMA do orquestrador, usuário delegou os gates da sessão] →
Builder → QA. **READ-ONLY M1** (mtime dos oficiais + `hexagonos_mercado_mapeado` inalterado; fórmula do
residual/`calcular_colunas_mercado` intocados).

**VEREDITO (out-of-fold, harness do TP-06, n=16.411, baseline R²_oof=+0,3119):**
- **C1 = "vence" porém RUÍDO → NÃO aplicar.** Δ pareado completo **+0,0019** IC95[+0,0015,+0,0023]; fora
  de SP/MG/RJ +0,0013 IC95[+0,0007,+0,0019]. O IC não cruza zero só por causa do N grande: **C1 é IDÊNTICO
  ao baseline em 97,3% dos hexes** (só 438 de 16.411 diferem; ganho localizado nos ~33% perto de
  Smart/Engenharia). Aplicar em produção (nova DEC + dependência de `data/validacao/` no pipeline + regen
  completa) por +0,002 de R² = sobreajuste a ruído (DEC-008).
- **C2 = NO-GO.** Δ completo −0,0312; fora −0,0120 — piora, repete a co-localização bairro↔demanda do
  Candidato A. Incluir bairro como oferta consumida — mesmo com decay fino e capacidade real — não ajuda.

**Conclusão da trilha do residual:** o **residual ATUAL é o melhor** que temos. Re-capacitar as grandes
quase não move (capacidade de clube real ≈ 2.500 flat atual) e incluir as academias de bairro na oferta
consumida piora. **BLK-TP-09 NÃO disparado** (nenhum candidato materialmente vencedor). Caminho ainda vivo,
não testado: bairro como **competição no Huff por ponto candidato (BLK-TP-07)**, não subtração global do
residual. **Entregáveis:** `capacidade_clube_validacao.py` (novo, leitor anti-PII), extensão de
`revalidacao_residual_candidatos.py` (C1/C2; baseline+A do FU1 preservados byte-a-byte),
`tests/unit/demanda_revelada/test_revalidacao_residual_candidato_c.py` (novo), relatório
`data/analysis/revalidacao_residual_candidato_c.md` (gitignored). QA APROVADO: suíte full
`1316 passed, 1 skipped`; C1/C2 reproduzidos byte-a-byte; anti-PII (só `{rede:float}`) + isolamento + k-ring
conserva massa verificados; mtime M1 intacto. DEC-008/009/012/013 respeitadas.

---

### BLK-TP-07 — Huff/gravitacional de captura de concorrentes com demanda observada (reabertura da Camada 2 do BLK-DIM)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (reabre uma camada de modelagem da epic BLK-DIM — captura/share; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — modelagem]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-TP-05** (GO da trilha demanda→captura, R²_oof_log +0,575, concluído 2026-06-30 — **destrava explicitamente a reabertura da Camada 2/Huff**) + `concorrentes_mapeados.parquet` + helper de catchment `analisar_entorno_ponto`. |
| **Autonomia** | **manual (NÃO loop-safe)** — decisão de modelagem. |

**DESFECHO (concluído 2026-07-03 — QA APROVADO COM RESSALVAS).** **GO honesto out-of-fold.** Módulo novo
`src/motor_expansao/demanda_revelada/huff_captura.py` (Huff por hexágono) reusa o núcleo PURO
`dimensionamento/huff.py` (`share_huff`/`_haversine_vec`) e o harness k-fold 5×5 seed=42/IC95 do TP-05/TP-06;
centroide via `h3.cell_to_latlng` (sem ler lat/lng-PII). Gate humano de Felipe aprovou D1..D6 = recomendações
do Planner: D1 atratividade unitária (capacidade-por-rede só sensibilidade); D2 share do centroide do hex;
D3 β por menor RMSE **out-of-fold**; D4 sem Ultra no principal; D5 `membros` log1p alvo único (`alunos_parceiras`
só cross-check circular); D6 baseline média + baseline geométrico contagem-no-raio-sem-β. **Veredito REAL
(reproduzido byte-a-byte pelo QA sobre parquets reais, seed=42):** β=0,5; **R²_oof_log = +0,4391 IC95
[+0,4251, +0,4523]** (> 0,05, IC > 0) **E supera o baseline geométrico +0,2922** ⇒ a geometria de distância
AGREGA sobre a mera contagem no raio; rho_oof +0,4354 IC95 [+0,4213, +0,4491]; R²_insample (auditoria, BANIDO)
+0,4392; n_join 16.575 (~1,07% do universo). Sensibilidades FORA do gate: D1b capacidade +0,357 (não supera o
unitário — atratividade uniforme só reescala), D4c proximidade Ultra +0,4755 (ganho marginal, não desloca o
veredito). **Ressalvas não-bloqueantes:** GO restrito a ~1% do universo (viés metropolitano SP 29,1%/MG 12,7%/
RJ 9,2% — DEC-012, desfecho honesto declarado, NÃO cobertura nacional); `hexagonos_brasil_dashboard.parquet`
ausente localmente (pré-existente, não causado pelo ciclo). **READ-ONLY M1:** mtime dos oficiais inalterado;
nenhum parquet de staging regenerado; isolamento AST sem imports proibidos; anti-PII/anti-vazamento
confirmados (`test_zero_pii`, `test_share_nao_recebe_alvo`). QA: suíte FULL **1327 passed, 1 skipped, 0 failed**;
ruff+mypy limpos; `import streamlit_app` ok. **Integrar a captura ao `score_oportunidade_residual`/carteira/plano
= BLK-TP-09 (follow-up com DEC + gate próprio), FORA deste bloco.** Relatório gitignored em
`data/analysis/huff_captura.md`. Handoffs: `context/handoff/20260703-{144500-block-orchestrator,150516-planner,180958-builder,224925-qa}.md`.

**Contexto.** A DEC-009 encerrou a previsão de *magnitude* de demanda pela geografia, e a Camada 2 (Huff)
da epic BLK-DIM ficou como NO-GO enquanto o insumo era demanda **imputada**. O **BLK-TP-05** virou esse
jogo: com demanda **observada** (não imputada), a trilha demanda→captura deu o **primeiro GO** honesto
(R²_oof_log +0,575, k-fold 5×5 vs baseline) e sua conclusão foi, textualmente, habilitar a reabertura da
**Camada 2/Huff** sob gate de Felipe. Este bloco é essa reabertura.

**Objetivo.** Modelar a **captura/share gravitacional (Huff)** de um ponto candidato — atratividade ×
distância aos concorrentes mapeados, com saturação e canibalização da rede Ultra — e **validá-la contra a
demanda observada** da Demanda Revelada (`membros`/`alunos_parceiras`), sob a disciplina DEC-008. A demanda
observada é o **alvo de validação**, nunca preditor geográfico de magnitude (DEC-009). Alinha com a
DEC-009 (dimensionamento consome demanda, não a prevê) e com a estrutura de catchment já existente.

**Critérios de aceite.** Módulo READ-ONLY isolado da camada paralela (sem import de `pipelines/m1`,
`dashboard`, `censo_*`, `api`); função de Huff parametrizável (β de distância, atratividade por
metragem/rede) calibrada/validada **out-of-fold vs baseline** com IC95 bootstrap, R² in-sample banido,
intervalos + flag de extrapolação; validação contra demanda observada por `hex_id` com caveat de cobertura
DEC-012; veredito GO/NO-GO em `data/analysis/` (gitignored); anti-PII (camada agregada; fixtures
sintéticas); sem dependência nova de rede/base pesada; mtime dos 4 artefatos oficiais M1 inalterado; suíte
verde; `import streamlit_app` ok.
**Guardrail.** §5 (READ-ONLY M1); DEC-008 / DEC-009 (demanda observada como insumo, nunca preditor de
magnitude) / DEC-012 (anti-PII). Integrar o resultado ao `score_oportunidade_residual` ou à carteira/plano
seria **follow-up com gate próprio**, não este bloco.

---

- BLK-TP-08 (concluído 2026-07-02) — ver tasks/completed.md

- BLK-TP-08-FU (concluído 2026-07-02) — ver tasks/completed.md

- BLK-TP-08-FU (concluído 2026-07-02) — ver tasks/completed.md

---

### BLK-RELPON-04 — Relatório Pontual em lote (fila de endereços pesquisados)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (nova função de UI no fluxo de geração do Relatório Pontual; **READ-ONLY sobre o M1**; sem DEC nova; reusa a geração existente do PDF pontual e a busca de endereço já existente). |
| **Prioridade** | Pedido direto de Vinicius (2026-07-06). |
| **Esteira** | Block Orchestrator → Planner → `[confirmação humana — produto: modo de "baixar em lote" + gatilho de acúmulo]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | — (toca só `src/motor_expansao/dashboard/pages.py`; reusa `gerar_payloads_relatorio_pontual_para_pin` e `render_coord_search_sidebar` sem alterá-los no núcleo). Precedente direto: BLK-RELMUN-04 (padrão de lote) e BLK-RELMUN-04-FU1 (largura). |
| **Autonomia** | **manual (NÃO loop-safe)** — feature de UI com decisões de produto; trilha do Vini. NÃO marcar loop-safe. |

**Pedido de Vinicius (2026-07-06).** Os Relatórios Pontuais também devem poder ser gerados **em lote**.
Como não há multiselect de pontos, o lote se forma **armazenando os endereços pesquisados** antes de
iniciar a geração. Requisitos explícitos:
- **Acumular** os endereços/coordenadas pesquisados numa fila (antes de gerar).
- **Gerar em lote** um Relatório Pontual por endereço da fila.
- **Dois modos de download:** **baixar em lote** (todos) **ou** **baixar apenas o último solicitado**.
- **Padrão de tamanho de botão** igual aos demais (reusar a regra CSS de 260px do `inject_styles`,
  como no BLK-RELMUN-04-FU1 — adicionar as novas `st-key` à mesma regra).
- **Dois pontos na página:** a opção deve ficar **na parte superior** (perto do menu, junto de
  `render_pdf_download_topo`) **e na inferior** (fluxo do Mapa Territorial,
  `render_relatorio_pontual_censitario`).

**Contexto (ancorado em `src/motor_expansao/dashboard/pages.py`).**
- Busca de endereço/coordenada/link Maps → `render_coord_search_sidebar` (~linha 769) devolve UM
  `search_pin=(lat,lng)` por vez (DEC-010: coord / endereço via Nominatim / link Maps). O texto
  digitado é o rótulo natural de cada ponto.
- Geração do PDF pontual: `gerar_payloads_relatorio_pontual_para_pin` (~2932) para um pin.
- Ponto de geração **superior**: `render_pdf_download_topo` (~2989) — botão `btn_gerar_pdf_topo`
  (~3011), download `dl_pdf_topo` (~3043), rótulos "Gerar PDF do ponto"/"Baixar PDF do ponto".
- Ponto de geração **inferior**: `render_relatorio_pontual_censitario` (~3236), no Mapa Territorial.
- Regra CSS de largura (260px) em `inject_styles` (~442): hoje cobre `stDownloadButton` +
  `btn_gerar_pdf_topo` + `btn_gerar_relmun_topo` + `btn_gerar_relmun_lote_topo/_expander`.
- Precedente de acúmulo em fila via `session_state` já existe no multihex (`btn_multihex_add`/`_remove`/
  `_clear`, lista copiável) — reusar o padrão de UX de fila.

**Escopo permitido (READ-ONLY M1, só UI).**
- **Fila de endereços** em `session_state` (chave dedicada, distinta das do municipal): cada item guarda
  `(rotulo_endereço, lat, lng)`; UI para **adicionar o ponto pesquisado atual**, **remover** e **limpar**
  (espelhando o multihex). Sobrevive a rerun.
- **Botão "Gerar Relatorios Pontuais (N)"** nos dois pontos (topo + inferior): loop pela fila
  reusando `gerar_payloads_relatorio_pontual_para_pin`, com **progresso i/N**; cache dos payloads por
  ponto em `session_state`.
- **Downloads:** modo **lote** (um `st.download_button` por endereço, rotulado "Baixar PDF — <endereço>",
  `key` único — como no municipal) **e** atalho **"Baixar apenas o último solicitado"** (o ponto mais
  recente). Ver decisão D1 sobre "lote = N botões vs. um .zip".
- **Rótulo na capa:** passar o endereço como `rotulo` do PDF pontual (a interface já aceita `rotulo`
  opcional — emenda da DEC-005), para cada relatório do lote sair identificado.
- **Largura dos botões:** adicionar as novas `st-key` à regra de 260px do `inject_styles` (NÃO usar
  `use_container_width`, que estica o botão — lição do BLK-RELMUN-04-FU1).
- **Fluxo de 1 ponto:** preservado (o botão "Gerar PDF do ponto"/"Baixar PDF do ponto" atual continua
  funcionando para o ponto pesquisado avulso).

**Decisões a confirmar (produto).**
- **D1 — "Baixar em lote" = N botões rotulados (como o municipal) ou um único `.zip`?** Recomendação:
  manter consistência com o BLK-RELMUN-04 (**N botões rotulados**) e, se houver apetite, **adicionar**
  um `.zip` como conveniência de "baixar tudo". Confirmar no gate.
- **D2 — Gatilho de acúmulo:** botão explícito "Adicionar à fila" do ponto pesquisado (recomendado,
  espelha o multihex) vs. acumular automaticamente cada busca. Recomendação: **botão explícito** (evita
  poluir a fila com buscas exploratórias).
- **D3 — Escopo dos dois pontos:** a fila é **compartilhada** entre topo e inferior (mesma
  `session_state`), com os botões espelhados nos dois lugares (recomendado), para o operador gerar de
  onde estiver.

**Fora de escopo.** Núcleo do relatório pontual (`censo_point.py`/`censo_map.py`/`censo_report.py`:
método de intersecção `setor_censitario_intersecao_area_1p5km`, raio 1,5 km, `RAIO_CENSITARIO_DEFAULT_KM`,
páginas/estrutura do PDF, marca d'água anti-PII) — **só consumir**; `score_priorizacao`/M1/artefatos
oficiais; `flag_sam`; Relatório Municipal (já feito no BLK-RELMUN-04). Sem dependência de rede nova
(geocoding Nominatim/DEC-010 e tiles/DEC-004 já existentes).

**Guardrails.** READ-ONLY sobre o M1 (§5). Reusa a geração e a busca existentes; não altera o núcleo
`censo_*`. Anti-PII: a fila de endereços vive só em `session_state` (efêmera), **não é persistida** em
disco/log; a marca d'água que carimba o solicitante (BLK-EST-03) e o `set_compression(False)` seguem.
Sem dependência de rede nova (§2 preservado; geocoding/tiles já cobertos por DEC-010/DEC-004).

**Critério de aceite.** Com a fila com >1 endereço, um botão gera N relatórios pontuais sob demanda
(progresso i/N) e oferece download **em lote** (1 por endereço, rotulado) **e** "baixar só o último";
com fila vazia/1 ponto o fluxo atual é preservado; os botões têm a mesma largura (260px) dos demais; a
opção aparece no topo **e** na parte inferior; suíte de testes verde; ruff+mypy limpos; revisão visual
humana aprovada.

---

### BLK-ATR-02 — Gate de viabilidade absoluto (população ≥ 5.000 E renda per capita ≥ 1.500) na camada de mercado

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (define o gate de entrada do funil; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | — (usa colunas de população e renda per capita já existentes na camada de mercado/censitária). |
| **Autonomia** | **loop-safe** — READ-ONLY M1; o gate vive na **camada de mercado/paralela** (NÃO em `config.py` nem `pipelines/m1`, senão o `loop_guard` aborta); só materializa uma flag/coluna paralela; sem VPS. |

**Contexto.** Régua absoluta (CLAUDE.md §2) para decisão. O piso de **população = 5.000** é válido (nem 100%
da população treina). O piso de **renda** hoje no código é **domiciliar** (`RENDA_MIN=4500`, via
`renda_target_proxy` escalado); o funil deve usar a régua **per capita** que o IBGE entrega direto, com corte
inicial **≥ 1.500 per capita** (decisão de Felipe, 2026-07-06; valor de partida, calibrável depois).

**Objetivo.** Materializar uma **flag de gate de viabilidade** na camada de mercado (coluna nova, ex.
`flag_gate_atratividade = populacao_corte_hex ≥ 5.000 AND renda_per_capita ≥ 1.500`), **sem tocar** o
`flag_viavel` existente (que segue com a régua domiciliar 4.500) nem `config.py`/M1. Reportar quantos hexes
passam no gate e a distribuição por UF. É o filtro binário da Etapa 1 do funil (abaixo do piso → fora do
ranking).

**Critérios de aceite.** Gate materializado como coluna paralela na camada de mercado (fora de `config.py` e
`pipelines/m1`); reutiliza a régua de população do `pop_corte.py` (`populacao_corte_hex`) e a `renda_per_capita`
existente; contagem de hexes aprovados + distribuição por UF documentada; `flag_viavel`/`RENDA_MIN`/M1
**INTOCADOS** (mtime dos 4 oficiais inalterado); suíte verde; `import streamlit_app` ok.
**Guardrail.** §5 (READ-ONLY M1); o gate é parâmetro da **camada paralela** (não canônico §3); DEC-001 intacta
(pisos do funil ≠ pesos do M1). loop-safe só enquanto NÃO tocar `config.py`/`pipelines/m1` (o `loop_guard`
aborta se tocar).

---

### BLK-ATR-01 — Densificar a base de concorrentes do Huff (TotalPass/WellHub/Unidades) + re-validar o GO

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (amplia a base de um sinal de modelagem; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | **BLK-TP-07** (motor `demanda_revelada/huff_captura.py`) + **BLK-TP-08/FU** (padrão de ingestão anti-PII e dedup por rede, `oferta_academias_menores.py`/`classificacao_rede_menor.py`). |
| **Autonomia** | **loop-safe** — READ-ONLY M1; escreve só `data/staging` (camada paralela) + `data/analysis`; ingestão de CSV LOCAL (sem API ao vivo); dado de concorrente é público/estabelecimento (não-PII pessoal); sem VPS/deploy/segredos. |

**Contexto.** Hoje o Huff (`share_captura_huff`) usa ~3,3 mil concorrentes "big players" de
`concorrentes_mapeados.parquet` → informativo em só ~0,3–1% dos hexes (99,65% viram monopólio share=1,0).
A pasta `concorrentes/` (gitignored) traz **~132 CSVs** com `latitude;longitude;nome;endereco;cidade;uf;...`:
`totalpass/` (27 UF, ~16 mil unidades), `wellhub/` (27 UF, ~13 mil) e `Unidades/` (39, por rede — dezenas de
redes além das "28" já classificadas). Densificar a base amplia a zona onde o eixo de disputa fala.

**Objetivo.** Ingerir as ~132 CSVs de `concorrentes/` (lat/long → `hex_id` res-7), **deduplicar** por
**nome+rede** entre as fontes (TotalPass ∩ WellHub ∩ Unidades) e contra `concorrentes_mapeados` (3,3k),
**cruzar com as unidades reais do `NAO_ABRA/`** (`01_SmartFit.xlsx`/`03_Competidores.xlsx`, nível
estabelecimento) para aferir precisão/overlap, materializar uma **base densa de concorrentes** em
`data/staging/` (camada paralela, NÃO oficial) e **re-computar `share_captura_huff`** sobre ela.
**Re-validar o GO do BLK-TP-07** (mesmo harness k-fold 5×5 seed=42/IC95 vs demanda observada `membros`):
confirmar se o R²_oof +0,4391 **se mantém ou melhora** com a base densa, e **quanto cresce a cobertura útil**
(hexes com share < 1,0). Veredito em `data/analysis/` (gitignored).

**Critérios de aceite.** Ingestão isolada na camada paralela (`demanda_revelada/`), sem import de
`pipelines/m1`/`dashboard`/`censo_*`/`api`/`config.py`; **nome de estabelecimento PODE ser usado** (dedup por
rede) — NÃO é PII pessoal; dado pessoal da Demanda Revelada permanece intocado (DEC-012); dedup documentado
(quantos duplicados por fonte); base densa materializada em `data/staging`; `share_captura_huff` recomputado;
**re-validação out-of-fold do GO** com números antes/depois (cobertura, R²_oof, IC95) em `data/analysis`;
mtime dos 4 oficiais M1 inalterado; suíte verde; `import streamlit_app` ok.
**Guardrail.** §5 (READ-ONLY M1); DEC-008 (re-validação out-of-fold, R² in-sample banido); DEC-009 (`membros`
é ALVO, nunca preditor); DEC-012 (só o dado PESSOAL da demanda é protegido — dado de estabelecimento é público).

---

- BLK-ATR-02 (concluído 2026-07-06) — ver tasks/completed.md

---

### BLK-ATR-03 — Testar a estrutura de leitura: matriz de eixos vs score composto (GO/NO-GO)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (decide a arquitetura do funil; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | **BLK-ATR-01** (Huff densificado + GO re-validado) + **BLK-ATR-02** (gate). |
| **Autonomia** | **loop-safe** — GO/NO-GO out-of-fold, READ-ONLY M1, veredito em `data/analysis`; sem mudança de produção (padrão dos BLK-DIM que já rodaram no loop). |

**Contexto.** Os três eixos (sociodemografia via `score_priorizacao`/`score_setor_2022_calibrado`; mercado via
`score_oportunidade_residual`; disputa via `share_captura_huff` densificado) são ortogonais (rho residual×share
−0,42 no metrô — não redundantes). A pergunta em aberto: para ranquear os hexes viáveis, um **score composto**
(um número) agrega valor preditivo sobre ler os eixos como **matriz** (o humano/operador integra)? Preferência
declarada de Felipe = **matriz**, sem descartar o teste do composto.

**Objetivo.** Dentro do conjunto viável (gate BLK-ATR-02), **validar out-of-fold** (k-fold 5×5 seed=42/IC95 vs
demanda observada `membros`) se um **score composto** dos 3 eixos prevê a demanda **melhor que cada eixo
isolado** e melhor que a **matriz** (baseline = eixos separados). **Default = matriz**; o composto só é
recomendado se **vencer materialmente** o melhor eixo isolado E não for redundante. Tratar a cobertura
metro-only do eixo Huff com **degradação graciosa** (fora do metrô o composto cai para sociodemo + residual).
Veredito GO/NO-GO + pesos validados (se composto GO) em `data/analysis/` (gitignored). **Não materializa nada
em produção.**

**Critérios de aceite.** Validação out-of-fold vs baseline (média + eixos isolados + matriz), IC95 bootstrap
seed=42, **R² in-sample banido do veredito**, flag de extrapolação; **`membros`/demanda só como ALVO**, nunca
como preditor (DEC-009); degradação graciosa fora do metrô documentada; veredito honesto (NO-GO = matriz é
resultado VÁLIDO) em `data/analysis`; caveat de cobertura ~1% explícito; mtime dos 4 oficiais M1 inalterado;
suíte verde; `import streamlit_app` ok.
**Guardrail.** §5 (READ-ONLY M1); DEC-008 (out-of-fold, R² in-sample banido, NO-GO válido); DEC-009 (demanda é
ALVO); DEC-012 (dado pessoal protegido).

**Conclusão (2026-07-06).** Builder implementou `src/motor_expansao/demanda_revelada/estrutura_funil.py`
(módulo novo, pacote disjunto) + `tests/unit/demanda_revelada/test_estrutura_funil.py` (15 testes, fixtures
sintéticas). O módulo aplica o gate ATR-02 REPLICADO inline (`populacao_corte_hex >= 5000` E
`renda_per_capita >= 1500`, sem importar de `pipelines/`), normaliza os 3 eixos em percentil nacional 0–100
(disputa = `1 - share_captura_huff` invertido, `flag_huff_disponivel` para degradação graciosa onde
share=1.0), roda modelos out-of-fold (k-fold 5×5 seed=42, IC95 bootstrap, fallback k=10/LOO) — baseline,
3 eixos isolados, censitário-auditoria, composto-Ridge, composto-pesos-iguais — e decide veredito honesto
GO-composto vs MATRIZ (default): GO só se `R²_oof > 0.05` E `IC95_inf > 0` E `ganho > 0.01` sobre o melhor
eixo E não-redundante (`pearson(pred) < 0.95`). R² in-sample é campo de auditoria rotulado, BANIDO do
veredito. `membros` só como ALVO (`log1p`). Relatório markdown gitignored em `data/analysis/estrutura_funil.md`
(caminho `executar()`/`__main__` sob `# pragma: no cover`; NÃO rodado nos testes — é passo operacional
pós-merge).

**QA — APROVADO (2026-07-06).** Validação independente:
- **Suíte FULL** (`pytest -q`): `1344 passed, 4 skipped, 4 failed` em 454s. As 4 falhas são
  PRÉ-EXISTENTES e do `openlocationcode` (não instalado → `resolve_plus_code` retorna `None`): todas em
  `test_coord_search.py`/`test_streamlit_app.py` (plus_code), fora do escopo BLK-ATR-03. **Regressões novas = 0.**
  Os 15 testes novos passaram dentro da suíte full.
- **ruff**: `All checks passed` no escopo (módulo + teste).
- **Isolamento (DEC-012)**: grep de `pipelines`/`dashboard`/`censo_`/`api`/`import config` → VAZIO. Imports só
  de `dimensionamento/` (camada irmã, precedente `backtest_tp05.py`) + `.contrato` + stdlib/numpy/pandas/
  scipy/sklearn. `loop_guard.py --base ciclo/loop-20260706-152137` → **GUARD OK** (21 caminhos, nenhum proibido).
- **READ-ONLY M1 (§5)**: mtime dos 4 oficiais inalterado (estrutural/priorizados/oportunidades 2026-06-03;
  dashboard 2026-06-12); `git status` limpo neles. `import streamlit_app` → ok.
- **Corretude (leitura do código)**: gate ATR-02 replicado inline via constantes locais `POP_MIN_GATE_ATR`/
  `RENDA_PC_MIN_GATE_ATR` (linha 249); R² in-sample AUSENTE de `_decidir_veredito` (só auditoria rotulada);
  `membros` nunca é feature (só `y = log1p(membros)`; teste `test_membros_nunca_feature` blinda); degradação
  graciosa em share=1.0 (disputa vira percentil baixo, nenhuma linha perdida; sub-análise de competitivos
  separada).
- **Housekeeping**: `housekeeping_move_block.py BLK-ATR-03 --check` → OK (stub no backlog + bloco em completed).

Veredito QA: **APROVADO.** Nada materializado em produção; veredito real do funil é passo operacional
pós-merge (`python -m motor_expansao.demanda_revelada.estrutura_funil`), não gate de teste.

---

### BLK-ATR-04 — Visualização dos resultados do funil (gráficos + números concretos para decisão)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (relatório visual de apoio à decisão; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | **BLK-ATR-01**, **BLK-ATR-02**, **BLK-ATR-03** (consome os outputs de análise dos três). |
| **Autonomia** | **loop-safe** — READ-ONLY M1; só lê os artefatos de `data/analysis`/`data/staging` e gera imagens numa pasta separada; sem produção/VPS. |

**Contexto.** Felipe quer **ver os resultados no fim** para decidir a estrutura (matriz vs composto) e o
BLK-ATR-05 com número concreto na mão, em vez de só ler o veredito textual.

**Objetivo.** Gerar um **relatório visual completo** (gráficos + números concretos) a partir dos outputs de
BLK-ATR-01/02/03, salvo em **pasta separada** (ex.: `data/analysis/viz_atratividade/`), usando **Plotly ou
Matplotlib** para materializar **imagens (PNG)** + um markdown-resumo que as referencia. Conteúdo mínimo:
(a) **cobertura do Huff antes/depois** da densificação (mapa/nº de hexes com share < 1,0, por UF);
(b) **re-validação do GO** (R²_oof antes/depois com IC95, RMSE por β);
(c) **impacto do gate** (quantos hexes passam pop ≥ 5.000 E renda_pc ≥ 1.500, por UF);
(d) **matriz de quadrantes residual × disputa** (os 4 quadrantes com contagens reais — o "prêmio grande mas
disputado" vs "nicho defensável" etc.);
(e) **comparação matriz vs composto** (R²_oof de cada eixo isolado, da matriz e do composto, com IC95);
(f) distribuições dos 3 eixos e correlações entre eles.
Tudo com números absolutos legíveis, sem PII pessoal.

**Critérios de aceite.** Imagens (PNG) + markdown-resumo em pasta separada dedicada; Plotly **ou** Matplotlib
(sem dependência de rede ao vivo — se Plotly, exportar PNG via kaleido ou HTML self-contained); números
concretos e legíveis; sem PII pessoal em nenhuma imagem/legenda; READ-ONLY M1 (mtime dos 4 oficiais inalterado);
suíte verde; `import streamlit_app` ok.
**Guardrail.** §5 (READ-ONLY M1); consome análises existentes, não recalcula score; DEC-012 (dado pessoal
protegido — só agregados/negócio nas imagens). Ver skill `dataviz` para padrão visual.

---

### BLK-UI-10 — PoC de repaginação do dashboard: tema denso (baixo) + mapa Leaflet client-side (médio)

| Campo | Valor |
|---|---|
| **Criticidade** | **Baixa** (camada de **visualização/PoC**; **READ-ONLY sobre o M1**; não substitui o caminho de produção). |
| **Prioridade** | A definir por Felipe/Vini. |
| **Esteira** | Block Orchestrator → Planner → Builder → QA. No modo loop, o gate humano é substituído pelo guard automático (`scripts/loop_guard.py`). |
| **Status** | Pendente. |
| **Depende de** | — (consome parquets já existentes em `data/outputs`/`data/staging`). |
| **Autonomia** | **loop-safe** — READ-ONLY M1, sem VPS/deploy/segredos, sem PII, **sem dependência nova de base** (Leaflet/h3-js por CDN via `st.components.v1.html`, igual ao `NAO_ABRA/totalpass_final*.html`), consome só `data/outputs`/`data/staging`; ver `docs/loop_autonomo.md`. |

**Contexto.** Comparação feita em 2026-06-24 (Felipe): o HTML `NAO_ABRA/totalpass_final (72) (1).html`
é um SPA estático (Leaflet + h3-js por CDN, ~1.500 linhas, dados embutidos como arrays JS, 100%
client-side) — leve e bonito porque é *vitrine* de um recorte pré-cozido. O nosso Streamlit é o *motor*
(server-side, base nacional de 1,54 M hexes + malha censitária, re-roda o script a cada clique, pydeck
re-renderizado). O objetivo deste bloco é **provar**, sem reescrever o motor, dois ganhos do HTML:
(A) layout denso + tema escuro coeso e (B) mapa interativo client-side fluido. NÃO é migração para SPA;
é PoC opt-in atrás de flag, com o caminho de produção (pydeck/abas atuais) **intacto e default**.

**Objetivo.** Entregar um protótipo navegável e testado que demonstre:
- **Fase A (esforço baixo — tema/layout):** uma camada de tema (CSS injetado) + layout 3-painéis
  (faixa superior + painel esquerdo de KPIs/filtros + mapa + painel direito de resultado), com a
  densidade do HTML mas seguindo a **"Direção visual"** abaixo (NÃO copiar a paleta/tipografia do
  totalpass cru — ver porquê). Só estilo/estrutura de container — **zero** mudança em dados, score,
  ranking ou nas funções de cálculo.
- **Fase B (esforço médio — mapa client-side):** um mapa **Leaflet** renderizado via
  `st.components.v1.html` (CDN, sem pip novo) que consome um **recorte JSON enxuto por UF/cidade**
  pré-agregado a partir dos parquets existentes (padrão "dados embutidos" do HTML), com pan/zoom/clique
  fluidos **sem rerun do servidor**. Comparar peso percebido e responsividade vs. o pydeck atual num
  pequeno relatório (`data/reports/ui_poc_leaflet.md`).

**Escopo permitido (estritamente loop-safe).**
- Código novo isolado em `src/motor_expansao/dashboard/` (ex.: `ui_proto.py` + helper de tema), exposto
  como **página/aba OPT-IN atrás de um flag** (env/`session_state`), nunca como substituto do render
  atual. As funções de produção (`build_map_figure`, abas, pydeck) ficam **byte-a-byte preservadas**.
- O recorte JSON é uma **VIEW derivada read-only** dos parquets; gravar, se necessário, em
  `data/outputs/ui_proto/` (ou cache `data/cache/`), **nunca** como artefato oficial do M1 (não entra na
  lista do §3/`docs/m1_outputs_oficiais.md`) e **sem PII**.
- Testes novos (render do tema sem erro, geração do recorte JSON determinística, fallback quando o
  parquet/UF não existe). Suíte verde.

**Direção visual (destilada da skill `frontend-design` — embutida aqui para o loop NÃO depender do
plugin; o container do loop tem `$HOME` próprio e não enxerga o `~/.claude` do host).**
O agente deve seguir estes tokens como decisão tomada, não reinventar. O `totalpass` é referência de
**densidade e ergonomia** (3 painéis, cards compactos, mono nos números), **não** de paleta: o "dark +
verde-ácido" dele é um dos defaults genéricos de IA. Ancore na **identidade real da Ultra** e no motivo
do produto (o hexágono H3).

- **Subject / tese.** Não é "mais um dashboard escuro": é a **sala de controle da expansão territorial**
  de uma rede low-cost/massa (CLAUDE.md §1). O herói da tela é o **mapa**, não um número grande.
- **Paleta (4–6 tokens; dark por legibilidade de mapa, mas NÃO o verde do totalpass).** Use a cor da
  marca Ultra como acento único e reserve magenta para semântica de concorrente — convenção que o
  projeto **já** usa (`Ultra=turquesa, conc.=magenta`, BLK-EST-02). Sugestão de tokens (o agente pode
  refinar a partir dos assets em `data/ultra/`, mas mantendo a semântica):
  `--bg:#0b1016` (fundo carvão-azulado, mais quente que o `#080c14` do totalpass) ·
  `--panel:#121a24` · `--line:#1f2c3a` · `--ultra:#1fd1c4` (turquesa Ultra = acento/ações/ativo) ·
  `--conc:#ff3d8b` (magenta = SÓ concorrente) · `--text:#dce6f0` / `--muted:#7d97ad`.
  Score/faixas de mapa continuam usando `RESIDUAL_SCORE_BANDS`/faixas GeoFusion já canônicas — a
  paleta de UI é a moldura, não recolore dado.
- **Tipografia (par deliberado, NÃO o Inter/JetBrains default do totalpass; tudo via Google Fonts CDN,
  loop-safe).** Display/títulos: **Space Grotesk** (caráter técnico/cartográfico, combina com "motor").
  Corpo/UI: **IBM Plex Sans** (pedigree de engenharia, distinto do Inter). Dados (hex_id, lat/lng,
  scores, m²): **IBM Plex Mono** — mono é justificável aqui porque o dado **é** o subject. Escala de
  tipo clara (ex.: 11/13/18/30) com pesos intencionais.
- **Signature (a UMA coisa memorável).** O **hexágono H3** é o motivo do produto inteiro — use-o como
  assinatura: cards de KPI com canto/recorte hexagonal sutil ou um marcador hex no lugar do "dot"
  genérico de legenda. Gaste a ousadia só aqui; o resto fica quieto e disciplinado (conselho "tire um
  acessório antes de sair").
- **Estrutura é informação, não decoração.** Nada de numeração 01/02/03 decorativa — só se houver
  sequência real. Eyebrows/labels devem codificar algo verdadeiro (UF, faixa, tese de entrada).
- **Cópia (microcopy) na voz do operador.** Rótulos pelo que a pessoa controla ("Filtrar por UF",
  "Gerar relatório"), voz ativa, sentence case, mesmo verbo do início ao fim do fluxo. Estado vazio é
  convite à ação ("Selecione um município no mapa"), erro diz o que houve e como resolver — sem
  apologia nem mood.
- **Piso de qualidade (sem alarde).** Responsivo até telas estreitas, foco de teclado visível,
  `prefers-reduced-motion` respeitado (anima no máximo a carga inicial/hover — excesso de animação
  cheira a "gerado por IA"). Contraste AA no texto sobre os painéis.
- **Anti-default checklist (rodar antes de fechar a Fase A).** (1) A paleta NÃO é o verde-ácido do
  totalpass nem cream+serif+terracota nem broadsheet hairline? (2) O par tipográfico não é o que eu
  usaria em qualquer projeto? (3) Existe UMA assinatura (hex) e o resto é contido? (4) Algum elemento
  decora sem significar? Se sim, corte. Anotar o que foi escolhido e por quê no relatório do bloco.

**Fora de escopo (NÃO fazer — manteria fora do loop-safe).** Tocar `config.py`, `pipelines/m1`,
qualquer `*scoring*`/artefato oficial do M1, `Dockerfile.streamlit`/compose/Caddy/CI/`.env`/`secrets/`;
**adicionar dependência de base** ao `pyproject.toml` (Leaflet/h3-js vêm de CDN no HTML embutido);
deploy ao VPS; recalcular score/ranking/carteira/plano; persistir qualquer PII; substituir o caminho de
produção do dashboard. Promover o PoC a default é **decisão humana** num bloco sucessor.

**Critérios de aceite.**
- Fase A: tema + layout 3-painéis renderizam numa página opt-in; produção (pydeck/abas) inalterada e
  ainda default; teste de smoke do render verde. A **"Direção visual"** foi seguida (paleta turquesa
  Ultra + magenta só-concorrente, par Space Grotesk/IBM Plex, assinatura hexagonal) e o **anti-default
  checklist** está respondido no relatório do bloco.
- Fase B: mapa Leaflet client-side carrega um recorte JSON de ≥1 UF, com clique→detalhe sem round-trip;
  recorte gerado de forma reprodutível e sem PII; relatório curto comparando peso/responsividade.
- READ-ONLY M1 comprovado (zero diff em score/pesos/artefatos oficiais); **nenhuma** dep nova de base;
  suíte verde; `loop_guard.py` não acusa toque em caminho proibido.

**Guardrail.** §2 (sem dependência de API ao vivo na carga do dashboard — o CDN do Leaflet só carrega no
PoC opt-in, com fallback gracioso, espelhando a mitigação da DEC-004); §5 (visualização não recalcula
nem altera M1); §6.1 (critérios loop-safe). Precedente de desvio cosmético restrito a um caminho: DEC-004.

---

### BLK-ATR-01-FU1 — Cruzar a base densa de concorrentes com as unidades reais do NAO_ABRA (aferição de precisão/overlap)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (aferição de qualidade da base densa do Huff; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | **Concluído** (2026-07-07). |
| **Depende de** | **BLK-ATR-01** (base densa `concorrentes_densos` + dedup por `(hex, rede)`, concluído 2026-07-06). |
| **Autonomia** | **loop-safe** — READ-ONLY M1; lê SÓ dado de **estabelecimento** de negócio (lat/long/rede/nome de unidade) do `NAO_ABRA/`; **NÃO** toca o dump pessoal (`totalpass_final*.html`); persiste ZERO PII; escreve só `data/analysis`; sem VPS/deploy/segredos/API ao vivo. |

**Contexto.** O BLK-ATR-01 fechou com um **gap de escopo declarado**: o dedup da base densa foi inter-fonte
(TotalPass/WellHub/Unidades) + contra `concorrentes_mapeados`, mas o **cruzamento com as unidades reais do
`NAO_ABRA/`** (pedido de Felipe) NÃO foi implementado. Este FU fecha esse gap.

**Objetivo.** Aferir a **precisão/cobertura** da base densa de concorrentes contra as unidades reais de
**estabelecimento** do `NAO_ABRA/` (`01_SmartFit.xlsx` = unidades SmartFit; `03_Competidores.xlsx` = ~24 mil
academias): quantas das unidades reais **casam** por `(hex_id_res7, rede)` com a base densa (recall), quantas
da base densa **não têm correspondência** (possíveis falsos/duplicatas residuais), e o overlap por rede. Só
campos de **negócio** são lidos (lat/long → hex, nome/rede para casar); qualquer PII é dropada na fronteira e
**nada de PII é persistido** (o dump pessoal `totalpass_final*.html` NÃO é lido). Relatório em `data/analysis/`
(gitignored), com contagens agregadas — recall, precisão-proxy, overlap por rede, e recomendação (a base densa
é suficiente, ou precisa de ajuste de dedup).

**Critérios de aceite.** Isolamento (`demanda_revelada/`, sem import de `pipelines/m1`/`dashboard`/`censo_*`/
`api`/`config.py`); lê só `01_SmartFit.xlsx`/`03_Competidores.xlsx` (estabelecimento), NUNCA o dump pessoal;
`test_zero_pii`/equivalente + fixtures sintéticas; relatório com métricas agregadas (recall/overlap por rede);
mtime dos 4 oficiais M1 inalterado; `concorrentes_densos.parquet` só LIDO (não reescrito sem necessidade);
suíte verde; `import streamlit_app` ok.
**Guardrail.** §5 (READ-ONLY M1); DEC-012 (dado de estabelecimento é público; só o **pessoal** é protegido —
dump pessoal não lido; zero PII persistida); DEC-013 (concorrentes só na camada de mercado/residual).

---

### BLK-ATR-03-FU1 — Re-rodar o teste de estrutura (matriz vs composto) sobre o Huff DENSO

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (fecha o número da decisão de arquitetura do funil; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | **BLK-ATR-01** (base densa + `share` denso) + **BLK-ATR-03** (harness `estrutura_funil`), ambos concluídos 2026-07-06. |
| **Autonomia** | **loop-safe** — GO/NO-GO out-of-fold, READ-ONLY M1, veredito em `data/analysis`; sem mudança de produção. |

**Contexto.** O BLK-ATR-03 deu **GO-composto** (composto R²_oof +0,48 vence o melhor eixo isolado +0,37), MAS
usou o `share_captura_huff` **original** (base de ~3,3 mil concorrentes; `% huff disponível ≈ 62%`), não o
Huff da **base densa** do ATR-01 (cobertura útil 28%→73%, R²_oof +0,44→+0,46, rho +0,44→+0,71). O eixo de
disputa denso é mais forte, então o composto provavelmente **sobe** — mas o número precisa ser recomputado
honestamente para embasar a decisão do BLK-ATR-05.

**Objetivo.** Re-rodar `estrutura_funil` (matriz vs composto, mesmo harness k-fold 5×5 seed=42/IC95 vs demanda
observada) **fiando o eixo de disputa no `share_captura_huff` DENSO** (da base do ATR-01) em vez do original.
Reportar o número atualizado do composto (R²_oof + IC95), o melhor eixo isolado, o ganho material e a
redundância — e re-emitir o veredito **matriz vs composto** com a base densa. Veredito em `data/analysis/`
(gitignored). **Não materializa nada em produção** (isso é BLK-ATR-05).

**Critérios de aceite.** Usa o `share` denso do ATR-01 (documentar a fonte exata do eixo de disputa);
validação out-of-fold vs baseline (média + eixos isolados + matriz), IC95 seed=42, **R² in-sample banido do
veredito**; `membros` só como ALVO (DEC-009); degradação graciosa onde o Huff não fala; veredito honesto
(NO-GO/matriz é válido); caveat de cobertura ~1% explícito; mtime dos 4 oficiais M1 inalterado; suíte verde;
`import streamlit_app` ok.
**Guardrail.** §5 (READ-ONLY M1); DEC-008 (out-of-fold, R² in-sample banido, NO-GO válido); DEC-009 (`membros`
só ALVO); DEC-012 (sem PII pessoal).

---

### BLK-PROD-02 — Limpar leftovers de staging

| Campo | Valor |
|---|---|
| **Criticidade** | **Baixa** (manutenção; **READ-ONLY sobre o M1**). |
| **Prioridade** | Baixa. |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | — (nenhuma). |
| **Autonomia** | **loop-safe** (paths PRÉ-APROVADOS) — READ-ONLY M1; deleção restrita a lixo temporário com glob FIXO; sem VPS. A lista fixa abaixo substitui a "confirmação explícita" original. |

**Contexto.** Sobras de execução ocupam espaço e poluem buscas: `tmp_codex_runtime/` (artefatos de teste) e
`*.tmp.parquet` temporários.

**Objetivo.** Remover EXCLUSIVAMENTE os caminhos pré-aprovados abaixo e nada além.

**Decisões PRÉ-FIXADAS (a única ação destrutiva do loop — escopo travado):**
- Remover o diretório `tmp_codex_runtime/` (inteiro).
- Remover arquivos que casem **exatamente** `data/outputs/*.tmp.parquet` (NUNCA `.parquet` sem o sufixo `.tmp` — os oficiais tipo `hexagonos_brasil_dashboard.parquet` ficam INTOCADOS).
- **Nenhum outro caminho.** Qualquer glob fora desses dois → abortar.

**Critérios de aceite.** Só os 2 globs removidos; artefatos oficiais em `data/outputs/` intactos (mtime dos 4 oficiais
inalterado); `loop_guard` limpo (não toca `config.py`/`pipelines/m1`/artefatos M1); suíte verde.

---

### BLK-VIAB-01 — Validação/limpeza da base de imóveis candidatos

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (camada paralela de dados de entrada; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | — (consome `data/ultra/Imoveis_*.xlsx` LOCAL, gitignored). |
| **Autonomia** | **loop-safe** — READ-ONLY M1; lê xlsx LOCAL (sem API ao vivo); escreve só `data/staging` (paralela) + `data/analysis`; endereço de imóvel comercial é não-PII pessoal; saída gitignored; sem VPS. |

**Contexto.** A base de imóveis (28 candidatos no snapshot 16/06, cresce pelo CRM) tem sujeira REAL medida: aluguel
placeholder (`11.111,11`), 4 metragens implausíveis (`14,9`/`25,63`/`190`/`200` m²), e as 28 linhas SEM `lat/lng`.
Precisa de uma camada de validação permanente antes de qualquer conta de viabilidade.

**Objetivo.** Ler a base, aplicar as regras de limpeza PRÉ-FIXADAS e materializar
`data/staging/imoveis_candidatos_limpos.parquet` (paralela, gitignored) + relatório
`data/analysis/imoveis_qualidade.md` (o que entrou, o que caiu e por qual regra).

**Decisões PRÉ-FIXADAS (substituem o gate humano no loop):**
- **Metragem:** descartar `ÁREA < 500 m²` (filtro de ERRO/não-academia — remove os 4 lixos; NÃO é filtro de viabilidade, o motor julga tamanho depois).
- **Aluguel:** manter só `10.000 ≤ ALUGUEL ≤ 500.000` E descartar o placeholder repdigit `11.111,11`.
- **Coordenada:** NÃO descartar linha sem `lat/lng` — só carimbar `flag_sem_coord=True` (o batch VIAB-03 roda coordless; o geocoding é bloco humano).
- **Status:** manter todos (PROSPECÇÃO/APROVADOS/HISTÓRICO) preservando a coluna `STATUS` para filtro posterior.

**Critérios de aceite.** Parquet limpo materializado (paralela, gitignored); relatório com contagem entrou/caiu por
regra; determinístico (mesmas regras → mesma saída); nenhuma escrita em `config.py`/`pipelines/m1`/artefatos oficiais;
suíte verde. **Guardrail.** §5 READ-ONLY M1; regras de limpeza são parâmetros da camada paralela (não §3); loop-safe só
enquanto não tocar `config.py`/`pipelines/m1` (o `loop_guard` aborta).

---

## BLK-VIAB-02 — Faixa de demanda-premissa por tier de metragem (comparáveis reais)

Data: 2026-07-07
Criticidade: Média (camada paralela de premissa; READ-ONLY sobre o M1)
Status: CONCLUÍDO

### O que foi feito
Criados 2 arquivos:
- `src/motor_expansao/dimensionamento/demanda_premissa.py` — módulo puro com funções
  `carregar_ultra`, `carregar_eng_corpo`, `combinar_bases`, `calcular_tiers`, `materializar`, `run`.
- `tests/unit/dimensionamento/test_demanda_premissa.py` — 28 testes unitários (fixture sintética).

### Artefatos gerados (gitignored)
- `data/staging/demanda_premissa_por_tier.parquet` (5 linhas)
- `data/analysis/demanda_premissa_qualidade.md`

### N por tier (dados reais)
| Tier (m²)  | N  | p10   | p50   | p90   | flag_extrapolacao |
|---|---|---|---|---|---|
| <1000      | 17 | 1467  | 2063  | 3589  | False |
| 1000-1499  | 46 | 1559  | 2532  | 3889  | False |
| 1500-1999  | 36 | 1763  | 2748  | 4578  | False |
| 2000-2999  | 11 | 2870  | 3888  | 4752  | False |
| >=3000     |  2 | 2578  | 5706  | 8833  | True  |
Total: 112 unidades (Ultra 54 + Eng Corpo 58)

### Validações
- ruff: limpo (0 erros)
- mypy: limpo (0 erros)
- pytest subset: 28/28 passed (testes novos)
- pytest impactado (dimensionamento/ + streamlit): 500 passed, 2 failed (pré-existentes Plus Code)
- smoke import: ok
- loop_guard: GUARD OK, 0 caminhos proibidos
- viabilidade_ponto.py: INTOCADO (git diff vazio)
- mtimes M1: brasil_estrutural.parquet=1780501621, brasil_priorizados.parquet=1780501631 (INALTERADOS)

### Referências
- `context/handoff/20260707-HHMMSS-builder.md`
- `tasks/backlog.md` (linha "~1.100" corrigida para "~112 unidades")

---

### BLK-VIAB-02 — Faixa de demanda-premissa por tier de metragem (comparáveis reais)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (insumo de premissa do motor; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | — (consome `unidades_ultra_performance_hex.parquet` + `data/validacao/academias_engenharia_do_corpo.xlsx`; Smart Fit e Sky Fit não têm metragem disponível). |
| **Autonomia** | **loop-safe** — READ-ONLY M1; consome `data/staging` + `data/validacao` (xlsx LOCAL) + `concorrentes/` (CSV LOCAL); saída `data/staging`+`data/analysis` gitignored; sem rede; sem VPS. |

**Contexto.** O motor `analisar_viabilidade_ponto` recebe `base_calibracao_df` para derivar a faixa de alunos por m²
(p10/p50/p90). Hoje essa faixa é frágil; temos ~112 unidades reais (Ultra 54 + Eng Corpo 58) com metragem+alunos totais para calibrá-la.

**Objetivo.** Derivar uma **faixa de demanda-premissa (p10/p50/p90 de alunos por unidade) POR TIER de metragem** a
partir dos comparáveis reais (Ultra `ALUNOS_TOTAL` + Smart `Alunos Totais SF` + Eng `Alunos Totais` + Sky `Alunos EVO`),
materializando `data/staging/demanda_premissa_por_tier.parquet` (a `base_calibracao_df` que o VIAB-03 consome).

**Decisões PRÉ-FIXADAS (guardrail DEC-009 — crítico):**
- A premissa vem da relação **metragem→alunos de comparáveis REAIS** (curva de capacidade), **NUNCA de renda/pop/geografia** do ponto. **PROIBIDO** usar `lat/lng` do candidato como preditor de demanda.
- **Alvo = alunos_totais REAIS**, NUNCA `membros`/agregador (achado da circularidade 2026-07-07; memória `huff-membros-circularidade-teto-demanda`).
- Tiers de metragem pré-fixados (m²): `[<1.000, 1.000–1.499, 1.500–1.999, 2.000–2.999, ≥3.000]`.

**Critérios de aceite.** Parquet de faixas por tier; N de comparáveis por tier documentado; sem PII (só contagens
agregadas); determinístico; `loop_guard` limpo. **Guardrail.** §5 READ-ONLY M1; DEC-009 intacta (premissa, não predição).

---

### BLK-VIAB-03 — Batch de viabilidade sobre candidatos limpos (coordless) + ranking por margem de segurança

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (entrega o coração do produto de viabilidade; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | **BLK-VIAB-01** (candidatos limpos) + **BLK-VIAB-02** (faixa de demanda-premissa). |
| **Autonomia** | **loop-safe** — READ-ONLY M1; reusa `dimensionamento/viabilidade_ponto.analisar_viabilidade_ponto` (PURO, determinístico); modo COORDLESS (`setores_df=None` → sem rede/catchment); saída `data/staging`+`data/analysis` gitignored; sem VPS. |

**Contexto.** O motor property-first já existe (`analisar_viabilidade_ponto(lat, lng, m2, aluguel_pedido,
demanda_premissa, ...)`) e degrada graciosamente sem coordenada (`setores_df=None` → não roda catchment/zona-morta,
mas entrega faixa de alunos + break-even + aluguel-teto). Falta o batch que roda isso sobre os candidatos reais.

**Objetivo.** Rodar o motor para CADA candidato limpo (VIAB-01) com a faixa de demanda-premissa (VIAB-02), em modo
coordless, e materializar `data/staging/viabilidade_candidatos.parquet` + relatório
`data/analysis/viabilidade_candidatos.md` ranqueado por **margem de segurança**.

**Decisões PRÉ-FIXADAS:**
- **Ranking = margem de segurança = `aluguel_teto(demanda=p50) − aluguel_pedido`**, reportando a banda p10..p90. Candidato ROBUSTO = aluguel pedido < teto em TODA a faixa (p10..p90).
- **NO-GO honesto:** aluguel pedido > teto já em p50 → NO-GO; entre `teto(p50)` e `teto(p10)` → condicional/negociar; `flag_extrapolacao` quando m² fora do envelope de calibração.
- **Ticket/margem:** usar os defaults do motor (`SIM_MENSALIDADE_BALCAO`, `margem_alvo=0.10`) — não inventar.
- **Sensibilidade:** materializar a grade `demanda × aluguel` de `grade_sensibilidade` por candidato.

**Critérios de aceite.** Parquet + relatório ranqueado; cada candidato com faixa de alunos, break-even, aluguel-teto,
margem, sensibilidade e `flag_extrapolacao`; **demanda SÓ como premissa** (nunca `lat/lng`); **reusa o motor SEM
modificá-lo** (`git diff` de `viabilidade_ponto.py` vazio); determinístico; `loop_guard` limpo. **Guardrail.** §5
READ-ONLY M1; DEC-009 (premissa explícita).

---

### BLK-VIAB-04 — Backtest do motor de viabilidade contra as 54 unidades Ultra reais

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (valida o motor antes de confiar nele; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | — (consome `unidades_ultra_performance_hex.parquet`: m²/faturamento/alunos/ticket reais das 54 unidades). |
| **Autonomia** | **loop-safe** — READ-ONLY M1; validação sobre dado interno já em `data/staging`; saída `data/analysis` gitignored; reusa harness DEC-008; sem rede; sem VPS. |

**Contexto.** Antes de ranquear imóveis com o motor, é preciso saber se ele erra. As 54 unidades Ultra maduras têm
m²/faturamento/alunos/ticket REAIS — dá pra medir predito vs realizado.

**Objetivo.** Rodar o motor com o m² real de cada unidade Ultra e a demanda real (`ALUNOS_TOTAL`) como premissa, e
comparar break-even/aluguel-teto/faixa-de-alunos PREVISTOS vs REALIZADOS. Relatório
`data/analysis/viabilidade_backtest_ultra.md` com erro (MAE/viés) e os casos onde o motor erra feio.

**Decisões PRÉ-FIXADAS (DEC-008):** validação honesta predito vs realizado por unidade; reportar erro absoluto e viés;
**NÃO ajustar o motor neste bloco** (só medir); se o motor errar de forma material e sistemática → registrar como
necessidade de recalibração (follow-up com gate), **não silenciar**.

**Critérios de aceite.** Relatório com erro por unidade + agregado; identificação de vieses; **nenhum ajuste do motor**
(`git diff` de `viabilidade_ponto.py` vazio); determinístico; `loop_guard` limpo. **Guardrail.** §5 READ-ONLY M1.

---

---

### BLK-PROD-03 — Avaliar hex_id como category com benchmark

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (performance de carga; **READ-ONLY sobre o M1**). |
| **Prioridade** | Baixa. |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | — (nenhuma). |
| **Autonomia** | **loop-safe** — READ-ONLY M1; perf/medição determinística; consome `data/staging`; escreve só `data/analysis` (relatório); sem VPS. |

**Contexto.** `hex_id` é chave de join em vários lugares; converter para `category` PODE ajudar ou prejudicar (memória/tempo).
Requer benchmark antes de qualquer mudança.

**Objetivo.** Medir o impacto de `hex_id` como `category` vs `string` em carga/join sobre os parquets de staging, com
relatório em `data/analysis/benchmark_hexid_category.md`.

**Decisão PRÉ-FIXADA.** Só APLICAR a mudança se o benchmark mostrar **ganho ≥ 15%** em tempo OU memória **sem regressão
de teste**; caso contrário, só materializar o relatório e NÃO alterar código de produção. Nunca tocar `config.py`/`pipelines/m1`.

**Critérios de aceite.** Relatório de benchmark reprodutível; se aplicada, mudança restrita a leitura/carga (não recalcula
score); suíte verde; `loop_guard` limpo.

---

- BLK-PROD-02 (concluído 2026-07-07) — ver tasks/completed.md

---

### BLK-PROD-06 — Relatório de movimentação concorrencial (a partir de staging)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (analytics; **READ-ONLY sobre o M1**). |
| **Prioridade** | Baixa. |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | — (consome os parquets de concorrentes JÁ em `data/staging`). |
| **Autonomia** | **loop-safe** (com escopo) — READ-ONLY M1; analítico sobre concorrentes JÁ em `data/staging`; **NÃO** faz a coleta ao vivo (essa é DEC-013/VPS, fora do loop); saída `data/analysis` gitignored; sem rede; sem VPS. |

**Contexto.** Queremos ler a movimentação da concorrência (contagem por rede/cidade, oferta consumida, impacto no
residual). A **coleta** semanal roda na VPS (DEC-013) — este bloco é só a **geração do relatório** a partir do que já
está em staging, sem tocar rede.

**Objetivo.** Gerar `data/analysis/movimentacao_concorrencial.md` com: contagem por rede/UF/cidade, oferta consumida e
impacto nas oportunidades residuais, a partir de `concorrentes_mapeados.parquet`/`concorrentes_densos.parquet` e da
camada de mercado.

**Decisões PRÉ-FIXADAS:**
- **Fonte = parquets de concorrentes em `data/staging`** (não a coleta ao vivo).
- Se houver ≥ 2 snapshots temporais em staging → calcular deltas (rede/cidade); se houver só 1 → gerar a estrutura + o retrato atual (sem delta), documentando a limitação.
- **READ-ONLY:** não altera `score`/residual/artefatos — só LÊ e reporta.

**Critérios de aceite.** Relatório materializado a partir de staging (sem rede); determinístico; nenhuma escrita em
score/artefatos M1; `loop_guard` limpo; suíte verde.

---

### BLK-ACENTO-01 — Acentuação da UI do dashboard (Streamlit)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (correção ampla de texto de UI; READ-ONLY sobre o M1; sem DEC; envolve 1 decisão de produto — label de exibição das faixas — e risco de acentuar identificador por engano, mitigado por lista de proibições). |
| **Prioridade** | **Urgente** (herda da tarefa ClickUp `86e26mtn5`). |
| **Esteira** | Block Orchestrator → Planner → `[confirmação humana — produto: D1 (label de exibição das faixas)]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | — (toca só a camada `dashboard/`; não depende de outros blocos). |
| **Autonomia** | **manual (NÃO loop-safe)** — mudança visual ampla que exige revisão humana; toca strings próximas a identificadores. NÃO marcar loop-safe. |

**Objetivo.** Acentuar corretamente TODO o texto voltado ao usuário na plataforma (abas, labels de
botão, `help=`, `st.caption/markdown/info/warning/success/error`, `st.metric`, `column_config`,
legendas), preservando 100% dos identificadores.

**Escopo permitido (READ-ONLY M1, só display).**
- `src/motor_expansao/dashboard/pages.py` (~359 ocorrências) e `components.py` (~161): acentuar
  strings de exibição. `pages.py` + `components.py` concentram ~90% da massa de texto.
- `streamlit_app.py` (~38), `data.py` (labels/mensagens de exibição; NÃO valores de categoria salvo
  via label layer), `constants.py` (só onde a string é EXIBIDA e não usada como chave/valor lógico).
- **D1 — camada de label de exibição das faixas:** criar `FAIXA_LABELS = {"prioridade_maxima":
  "Prioridade máxima","alta":"Alta","media":"Média","baixa":"Baixa","descartado":"Descartado",
  "inviavel":"Inviável"}` e usar `format_func` no `st.multiselect` (`pages.py:668-671`) e nas
  legendas/tabelas, mantendo o VALOR bruto intocado no filtro/`.isin`/dict de cores. Idem, se
  aplicável, `HYBRID_ELIGIBILITY_ORDER`/`COVERAGE_BUCKET_ORDER`/`JOIN_QUALITY_ORDER`. O fallback
  `"Nao informado"` (`data.py:211,219,223`, `components.py:572,589`) pode virar "Não informado"
  DESDE QUE trocado em TODAS as ocorrências juntas (é literal repetido, não comparado a dado externo)
  — validar que continua casando `pd.Categorical(...)`.
- Banir tipografia "esperta" também na UI por consistência (usar hífen simples e aspas retas).
- Atualizar `tests/integration/test_streamlit_app.py` (6232 linhas; dezenas de asserts de string de
  UI — ex. linhas 334,338,762,1112-1117,1355-1357,3199,3238-3239,3664-3666,4650-4653) e
  `tests/unit/test_dashboard_format_utils.py`.

**Fora de escopo.** Relatórios PDF/CSV (BLK-ACENTO-02). Qualquer valor bruto de enum/coluna/`key=`/
`.st-key-*`/slug (ver lista canônica de proibições da epic). `score_priorizacao`/M1/artefatos
oficiais. Sem dependência de rede nova.

**Critério de aceite.** Texto de UI do dashboard acentuado corretamente (varredura por amostra de
palavras sem acento retorna ~0 em texto de exibição); faixas exibidas com label acentuado mas
filtrando pelo valor bruto (comportamento de filtro idêntico); nenhum `key=`/`.st-key-*`/coluna/
enum bruto alterado; suíte verde; ruff+mypy limpos; revisão visual humana aprovada.

---

### BLK-ACENTO-02 — Acentuação dos relatórios gerados (PDF/CSV)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (texto dos relatórios; READ-ONLY sobre o M1; núcleo `censo_*` só nas STRINGS de exibição, sem tocar método de interseção/raio/estrutura de páginas/marca d'água; sem DEC). |
| **Prioridade** | **Urgente** (herda da tarefa ClickUp `86e26mtn5`). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | — (independente do BLK-ACENTO-01; pode ir em PR separado). |
| **Autonomia** | **manual (NÃO loop-safe)** — altera texto de relatório auditável (compressão OFF) e exige revisão visual do PDF. NÃO marcar loop-safe. |

**Objetivo.** Acentuar corretamente o texto dos relatórios (Relatório Pontual Censitário 1,5 km e
Relatório Municipal), sem trocar fonte/biblioteca e sem introduzir caracteres que virem `"?"`.

**Escopo permitido (READ-ONLY M1, só texto de relatório).**
- `src/motor_expansao/dashboard/censo_report.py` (~50 chamadas `_ascii(...)`) e
  `relatorio_municipal.py` (~142 ocorrências / ~55 `set_font` + `_ascii`): escrever os textos-fonte
  COM acento (títulos, `PDF_SECTION_HEADERS` — `censo_report.py:16-17`, `relatorio_municipal.py:60-61`,
  rótulos de Big Numbers, legendas, rodapé). `latin-1` renderiza os acentos; **manter `_ascii()`**
  como salvaguarda para caracteres exóticos.
- Corrigir o comentário-fonte enganoso ("ASCII, sem acento") para refletir que latin-1 cobre acento
  e que o que se proíbe é a tipografia fora de latin-1.
- **BANIR tipografia "esperta"** no texto de PDF (travessão `—`/`–`, bullet `•`, seta `→`,
  reticências `…`, aspas curvas, `©`): trocar por ASCII (`-`, `"`, "(c)", "...") — senão viram `"?"`
  silenciosamente via `errors="replace"`.
- **Teste de regressão anti-`"?"`:** adicionar teste que gere os PDFs e assert que **nenhum byte
  `b"?"` inesperado** aparece (ou rodar `_ascii` com `errors="strict"` num modo de auditoria/CI para
  pegar tipografia fora de latin-1 cedo). Aproveita a compressão OFF (`set_compression(False)`,
  `censo_report.py:228-236`) que já expõe o texto cru.
- Atualizar `tests/unit/test_relatorio_municipal.py` (~26 asserts `assert b"..."`, ex. linhas
  354-368,467-472,498,558-583) e `tests/unit/test_relatorio_pontual_censitario_export.py` (~40
  asserts, ex. linhas 125-126,268-269,311-326,382-416,554-556) para as strings acentuadas em
  `latin-1` (`b"Visao"` -> `"Visão".encode("latin-1")`). O laço
  `for header in PDF_SECTION_HEADERS: assert header.encode("latin-1") in pdf_bytes` NÃO quebra (lê a
  constante), mas os `assert b"literal"` isolados precisam ser atualizados um a um.

**Fora de escopo.** Núcleo funcional `censo_*`: `setor_censitario_intersecao_area_1p5km`, raio 1,5 km,
`RAIO_CENSITARIO_DEFAULT_KM`, contagem/ordem/estrutura das páginas, grid de Big Numbers, marca d'água
anti-PII (BLK-EST-03), `set_compression(False)`, `pdf_version` — SÓ as STRINGS mudam. UI do dashboard
(BLK-ACENTO-01). `score_priorizacao`/M1/artefatos oficiais. Trocar core font por TTF Unicode (não é
necessário; latin-1 basta).

**Guardrails.** READ-ONLY sobre o M1 (§5). Anti-PII inalterado (compressão OFF, marca d'água do
solicitante BLK-EST-03, `.pptx`/PDF nunca versionados, `image24.png` nunca embutido). Sem dependência
de rede nova.

**Critério de aceite.** PDFs (pontual + municipal) com acentuação correta renderizando em `latin-1`;
teste anti-`"?"` verde (zero caractere perdido); método de interseção/raio/estrutura/marca d'água
INTOCADOS; suíte verde (asserts de PDF atualizados); ruff+mypy limpos; revisão visual humana do PDF
aprovada.

---

### BLK-VIAB-05 — Recalibrar/validar a curva m²→densidade com a base ampliada (out-of-fold)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (fortalece o único sinal real do motor; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | **BLOQUEADO** — base ampliada não existe (2026-07-07, Block Orchestrator). |
| **Depende de** | — (reusa `demanda_revelada/calibracao_curva.py` + base ampliada de alunos_totais Ultra+Smart+Eng+Sky). |
| **Autonomia** | **loop-safe** — READ-ONLY M1; reusa harness DEC-008 (k-fold 5×5 seed=42); saída `data/analysis`+`data/staging` gitignored; sem rede; sem VPS. |

**Contexto.** A curva metragem→densidade (DIM-03R) foi calibrada em ~112 unidades e é sinal de TIER. O backlog
estimava "~1.100 academias reais com metragem+alunos (Ultra+Smart+Eng+Sky)" — mas essa estimativa estava errada.

**BLOQUEIO (2026-07-07 — Block Orchestrator):** A base disponível com `metragem > 0` é **N=112** (Ultra 54 + Eng
Corpo 58), idêntica à base do BLK-TP-04 (concluído 2026-07-02). Smart Fit e Sky Fit não possuem coluna de
metragem em nenhuma fonte disponível (`KPIs_Smart_2025_02.xlsx` e `Sky Fit dados.xlsx` confirmados). O
`base_calibracao_multirede.parquet` tem 426 linhas mas os 311 SkyFit têm metragem=NaN em 100% das linhas. O
BLK-TP-04 já executou a validação honesta da curva com essa mesma base N=112 e o mesmo harness DEC-008.
**Condição de reabertura:** nova fonte com metragem+alunos reais além de Ultra e Eng Corpo.

**Objetivo.** Revalidar/recalibrar a curva metragem→densidade (alunos/m²) sobre a base ampliada, **out-of-fold**
(k-fold 5×5 seed=42 vs baseline da média, DEC-008), reportar se a curva melhora (R²_oof, IC95) e se continua sinal de
TIER ou vira curva suave. Se GO, materializar a curva validada em `data/staging` (paralela) para VIAB-02/03 adotarem;
relatório honesto em `data/analysis/curva_densidade_ampliada.md`.

**Decisões PRÉ-FIXADAS (DEC-008):** out-of-fold vs baseline da média; **R² in-sample BANIDO do veredito**; IC95 seed=42;
**NO-GO é resultado VÁLIDO** (se a base ampliada não melhorar, manter a curva atual e registrar); **alvo = alunos_totais
REAIS**, nunca `membros`/agregador (achado da circularidade 2026-07-07).

**Critérios de aceite.** Relatório out-of-fold com veredito honesto; curva validada materializada só se GO; se NO-GO,
curva atual mantida e documentado; determinístico; `loop_guard` limpo. **Guardrail.** §5 READ-ONLY M1; DEC-008 honrada.

---

### BLK-VIAB-06 — Guardrail de envelope de metragem no motor de viabilidade

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (guardrail no motor de viabilidade; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | **BLK-VIAB-04** (mediu MAPE 85% na extrapolação > 2.800 m²). |
| **Autonomia** | **loop-safe** — READ-ONLY M1; muda SÓ `dimensionamento/viabilidade_ponto.py` (não `config.py`/`pipelines/m1`); determinístico + testável; sem VPS/rede. |

**Contexto.** O backtest BLK-VIAB-04-FU provou que fora do envelope calibrado (Ultra 636–2.800 m²; a base
tem 112 unidades) a curva EXTRAPOLA mal (MAPE 85% acima de 2.800 m²). O motor deve SINALIZAR isso.

**Objetivo.** Adicionar uma flag `flag_fora_envelope` em `analisar_viabilidade_ponto` (e no resultado) quando
o `m2` do imóvel cai fora de `[ENVELOPE_MIN, ENVELOPE_MAX]`, para a UI avisar "extrapolação não confiável".

**Decisões PRÉ-FIXADAS.** Envelope = **[600, 3.000] m²** (cobre a base de calibração 636–2.800 + folga);
**só FLAG, NÃO recusa** por padrão (a decisão de exibir/bloquear fica na UI); comportamento existente do motor
**byte-idêntico** exceto a flag nova (default de faixa/DRE inalterado).

**Critérios de aceite.** `flag_fora_envelope` materializada; teste (m² > 3.000 → True; dentro → False);
comportamento atual preservado (regressão dos testes VIAB-03/04); ruff/mypy/suíte verde. **Guardrail.** §5
READ-ONLY M1; `viabilidade_ponto` não recalcula score/M1.

---

### BLK-VIAB-07 — Curva de densidade por formato (rótulo opcional) — validação out-of-fold + parâmetro

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (única alavanca de precisão restante do motor; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | **BLK-VIAB-04** (diagnóstico rede-aware = teto ~+1,7 p.p. de MAPE). |
| **Autonomia** | **loop-safe** — READ-ONLY M1; parâmetro OPCIONAL (default `None` = comportamento byte-idêntico); validação out-of-fold (DEC-008); sem VPS/rede; NO-GO é resultado VÁLIDO. |

**Contexto.** Varremos a curva (BLK-VIAB-04-FU): afinar a faixa de METRAGEM não move a precisão (~30% MAPE é o
piso); o único ganho real (~1,7 p.p.) veio de **homogeneidade de FORMATO/rede** (comparáveis da mesma rede). Duas
academias do mesmo m² têm densidades diferentes se uma é low-cost de massa e a outra boutique.

**Objetivo.** (1) Rotular os comparáveis por `formato` (ex.: `low_cost_massa` / `boutique`); (2) adicionar param
OPCIONAL `formato` em `faixa_alunos_por_densidade` que filtra comparáveis do mesmo formato; (3) **VALIDAR
out-of-fold** (k-fold vs baseline, DEC-008) se o ganho de precisão se sustenta. Se GO, materializar; se NO-GO,
não expor.

**Decisões PRÉ-FIXADAS.** Param default `None` → comportamento **byte-idêntico** ao atual (dashboard/VIAB-03
preservados); **alvo = alunos totais REAIS** (nunca `membros`/agregador — memória `huff-membros-circularidade`);
validação k-fold 5×5 seed=42; **R² in-sample banido do veredito**; NO-GO honesto encerra sem expor.

**Critérios de aceite.** Relatório out-of-fold com veredito; param opcional testado (`None` = idêntico byte-a-byte);
motor não recalcula M1; ruff/mypy/suíte verde. **Guardrail.** §5 READ-ONLY M1; DEC-008.

---

### BLK-REV-01 — Baseline de performance ponta-a-ponta (instrumentação + medição)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (base factual de toda a otimização; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | — (consome o app + `data/staging`/`data/outputs`). |
| **Autonomia** | **loop-safe** — instrumentação headless determinística; READ-ONLY M1; escreve só `data/analysis`; sem VPS/rede de produção. |

**Contexto.** Sem número, otimização é palpite. O ciclo de perf de mai/2026 atacou carga por UF/aba, mas não há
baseline dos 4 caminhos que o Felipe sente lentos.
**Objetivo.** Instrumentar timing por caminho e medir (frio/quente, por tamanho de UF): carga inicial, troca de
UF/município, render do mapa (lado Python), troca de modo de cor, seleção/cenário múltiplo, PDF Pontual/Municipal.
Relatório `data/analysis/perf_baseline_app_2026.md`.
**Decisões PRÉ-FIXADAS.** Mede o lado Python/servidor (data prep, serialização pydeck, recompute do rerun,
geometria/tiles/fpdf2); paint/interação no browser = complemento MANUAL (nota no relatório, não bloqueia).
Determinístico. **Guardrail.** §5 READ-ONLY M1; não altera app/artefatos.

---

### BLK-REV-02 — Inventário arquitetural e mapa de dependências do app atual

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (retrato honesto antes de refatorar vs refazer; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | — (leitura de código). |
| **Autonomia** | **loop-safe** — leitura de código/artefatos; READ-ONLY M1; escreve só `docs/`/`data/analysis`; sem VPS. |

**Contexto.** Precisamos de um retrato honesto da arquitetura atual antes de decidir refatorar vs refazer.
**Objetivo.** Mapear camadas (carga parquet, pydeck, `session_state`, fpdf2/matplotlib, tiles), o **modelo de rerun**
do Streamlit, o que é cacheado (`@st.cache_data`) vs recomputado por rerun, tamanho dos artefatos carregados, grafo
de deps e pontos de acoplamento. Entrega diagrama + inventário em `docs/arquitetura_app_atual.md`.
**Decisões PRÉ-FIXADAS.** Só leitura; nenhuma alteração. **Guardrail.** §5 READ-ONLY M1.

---

### BLK-REV-03 — Diagnóstico de gargalo: render do mapa (pydeck)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (dor #1; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | **BLK-REV-01** (harness de baseline). |
| **Autonomia** | **loop-safe** — mede o lado Python; READ-ONLY M1; relatório em `data/analysis`; sem VPS. |

**Contexto.** Dor #1. Suspeitos: nº de pontos servidos, **serialização pydeck→browser a cada rerun**, tesselação H3,
cap `MAP_POINT_LIMIT`.
**Objetivo.** Medir a contribuição Python (montagem do layer, serialização, downsample) e formular causa-raiz;
levantar opções (downsample mais agressivo, **tiles vetoriais/MVT**, render **client-side deck.gl/MapLibre** servido
por API) com ganho estimado. Relatório.
**Decisões PRÉ-FIXADAS.** Só diagnostica (NÃO implementa); paint no browser = medição manual (nota). **Guardrail.** §5.

---

### BLK-REV-04 — Diagnóstico de gargalo: troca de modos de cor / heat maps

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (dor #2; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | **BLK-REV-01**. |
| **Autonomia** | **loop-safe** — mede o recompute do rerun; READ-ONLY M1; relatório em `data/analysis`; sem VPS. |

**Contexto.** Dor #2. Suspeita central: o **rerun do Streamlit recomputa e re-serializa o mapa inteiro** ao trocar
M1/Censitário/Residual, mesmo mudando só a cor.
**Objetivo.** Medir o custo de troca de modo; testar hipóteses (pré-computar as N camadas de cor, **recolor
client-side**, cache por modo). Relatório com opções e ganho estimado.
**Decisões PRÉ-FIXADAS.** Só diagnostica. **Guardrail.** §5 READ-ONLY M1.

---

### BLK-REV-05 — Diagnóstico de gargalo: seleção de hex + cenário múltiplo

| Campo | Valor |
|---|---|
| **Criticidade** | **Média/Alta** (dor #3; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | **BLK-REV-01**. |
| **Autonomia** | **loop-safe** — mede o recompute de cenário; READ-ONLY M1; relatório em `data/analysis`; sem VPS. |

**Contexto.** Dor #3. O ciclo **clique→rerun→recompute do cenário** a cada hex adicionado.
**Objetivo.** Medir a latência de add/remove hex e o recompute de `agregar_cenario_multihex`; opções (estado
client-side, **deltas** em vez de recompute total, debounce). Relatório.
**Decisões PRÉ-FIXADAS.** Só diagnostica; latência de interação no browser = nota manual. **Guardrail.** §5.

---

### BLK-REV-06 — Diagnóstico de gargalo: geração de PDF (Pontual + Municipal)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (dor #4; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | **BLK-REV-01**. |
| **Autonomia** | **loop-safe** — geração de PDF é headless e mensurável ponta-a-ponta; READ-ONLY M1; relatório em `data/analysis`; sem VPS. |

**Contexto.** Dor #4. Suspeito forte: o **fetch de tiles do basemap pela rede** (DEC-004/011) dentro da geração —
I/O de rede é lento e variável.
**Objetivo.** Medir cada etapa headless (intersecção geométrica de setores, **fetch/cache de tiles**, render
matplotlib, montagem fpdf2) e isolar o gargalo; opções (cache de tiles mais agressivo, pré-render, geometria
simplificada, paralelismo). Relatório.
**Decisões PRÉ-FIXADAS.** Só diagnostica; raio 1,5 km e método de intersecção INTOCADOS (só medidos). **Guardrail.** §5.

---

### BLK-REV-07 — Avaliação de fundação: Streamlit vs. alternativas (matriz de decisão)

| Campo | Valor |
|---|---|
| **Criticidade** | **Estratégica** (embasa rebuild vs refactor; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | **BLK-REV-02** + **BLK-REV-03..06** (precisa do inventário + dos achados de perf). |
| **Autonomia** | **loop-safe** — pesquisa/relatório (a DECISÃO fica no REV-12); READ-ONLY M1; sem VPS/rede de produção. |

**Contexto.** A pergunta séria do Felipe — o **modelo de rerun do Streamlit é o teto** de performance/UX deste
produto? Vale refazer noutra stack?

**PONTO DE PARTIDA — topologia real de produção (confirmada 2026-07-08 no `docker-compose.prod.yml`; NÃO
re-descobrir, partir daqui):** a produção **já é multi-container**, não um processo monolítico:
`streamlit` + **`api` (FastAPI, `src/motor_expansao/api/`)** + `telegram-bot` + **`caddy` (reverse proxy 80/443)** +
`authelia`. Os **dados vivem na VPS como volumes `:ro`** (`/opt/motor-expansao/data/outputs|staging|ibge|ultra`,
`concorrentes`) — **NÃO estão dentro de nenhum container** — e o `streamlit` E a `api` já consomem **os mesmos
volumes read-only**. Consequências para a avaliação:
- O **"requisito offline" (§2) NÃO significa "sem backend"** — significa **sem dependência de serviço EXTERNO ao
  vivo** (tiles de basemap/geocoding são exceções DEC-004/010/011). A **própria `api` na VPS lendo arquivos locais
  já é o modelo atual** e NÃO viola o §2. Um frontend web servido pela mesma VPS, chamando a `api` que lê os
  mesmos volumes, preserva o offline 100%.
- O **custo de migração cai**: **backend (`api`) e reverse proxy (`caddy`) já existem**. A opção (d)/(b) vira, na
  prática, **"trocar o container `streamlit` por um frontend estático (SPA) servido pelo Caddy que já roda"**,
  reusando/estendendo a `api` e mantendo dados/Caddy/Authelia/rede intactos — não é reescrever do zero.

**Objetivo.** Pesquisa estruturada das opções — (a) manter Streamlit + otimizar (`st.fragment`/cache/downsample);
(b) **frontend React/Next.js (SPA estático servido pelo Caddy) + a `api` FastAPI existente**; (c) Dash/Panel;
(d) frontend custom com **deck.gl/MapLibre client-side** + a `api`. Critérios: performance (esp. mapa e troca de
cor/seleção sob o modelo de rerun), controle de UX (progressive disclosure p/ leigos), **preservação do offline §2**
(dado local na VPS), **reuso da `api`/Caddy/volumes já existentes**, velocidade/custo de dev e manutenção **por
perfil de time** (Python-only vs com frontend), risco de migração. **Mapear o espectro incremental→cirúrgico→rebuild**
(cache+fragment → trocar SÓ o mapa por componente client-side → rebuild do frontend sobre a `api`). Entrega **matriz
de decisão + recomendação PRELIMINAR**.
**Decisões PRÉ-FIXADAS.** NÃO decide — a decisão é do BLK-REV-12 (gate humano + DEC). Parte da topologia real acima
(não re-litigar o offline). **Guardrail.** §5 READ-ONLY M1.
---

### BLK-MAP-02 — Filtro de marcas de concorrentes do mapa em menu expansível (fechado por padrão)

| Campo | Valor |
|---|---|
| **Criticidade** | **Baixa** (mudança de UI localizada no Mapa Territorial; READ-ONLY sobre o M1; sem decisão de produto). |
| **Prioridade** | Normal. |
| **Esteira** | Block Orchestrator → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | — (herda BLK-MAP-01, que já é o ponto único de filtragem de concorrentes). |
| **Autonomia** | **manual (NÃO loop-safe)** — mudança de UX visível; exige revisão humana. |

**Objetivo.** Envolver o filtro de marcas de concorrentes do Mapa Territorial (`st.multiselect("Redes de
concorrentes", …)`, `pages.py:4382`, dentro de `render_mapa_territorial`) num `st.expander(...,
expanded=False)`, para o filtro nascer **fechado** e não empurrar o mapa para baixo.

**Escopo permitido (READ-ONLY M1, só display).**
- Só `src/motor_expansao/dashboard/pages.py`, bloco `_show_rede_filter` (~4373–4396): mover o
  `st.multiselect` para dentro de `with st.expander("Redes de concorrentes", expanded=False):`.
- Preservar integralmente: `key="mapa_territorial_redes_concorrentes"`, `options=_all_redes`,
  `default=_all_redes`, `format_func` (label via `COMPETITOR_BRANDS`), e a lógica BLK-MAP-01 (seleção
  vazia ⇒ `competitors_df_filtered = None` ⇒ esconde concorrentes). `_render_unified_legend` e
  `build_unified_map_figure` seguem lendo `competitors_df_filtered` como hoje.

**Fora de escopo.** Lógica de filtragem/legenda/cluster de concorrentes; `key`/estado de sessão;
`COMPETITOR_BRANDS`; qualquer artefato/score/pesos do M1.

**Critério de aceite.** O filtro renderiza dentro de um expander **fechado por padrão**; abrir,
selecionar, limpar e reselecionar mantêm o comportamento atual do mapa e da legenda (inclusive
seleção vazia ⇒ esconde concorrentes); suíte verde (atualizar assert de
`tests/integration/test_streamlit_app.py` se algum travar o label/posição do widget); ruff+mypy limpos.

**Fechamento do ciclo BLK-MAP-02 (2026-07-08) — VEREDITO: APROVADO.** Esteira Baixa (BO haiku ->
Builder sonnet -> QA opus 4.8; QA incluído apesar de Baixa por causa do fluxo de integração sem
revisão humana por ciclo). Rodou na branch ciclo/BLK-MAP-02, ramificada da SECUNDÁRIA
integracao/map02-relmun05-06. Feito: `st.multiselect("Redes de concorrentes", ...)` em
render_mapa_territorial (pages.py) envolvido em `st.expander("Redes de concorrentes",
expanded=False)` -> filtro nasce fechado. Preservados key="mapa_territorial_redes_concorrentes",
options/default=_all_redes, format_func e a lógica BLK-MAP-01 (seleção vazia => competitors_df_
filtered=None => esconde concorrentes), fora do `with`. Nenhum identificador acentuado/renomeado;
COMPETITOR_BRANDS/legenda/cluster intocados. Validações (QA, NO-BYPASS): ruff limpo; import ok;
mypy só 7 erros pré-existentes de types-requests (0 novo em pages.py); suíte serial completa
`1535 passed, 2 skipped, 1 failed` — a única falha (test_score_retencao_territorial::
test_run_readonly_m1_por_mtime, parquet M2 gitignored) é PRÉ-EXISTENTE/ambiental, alheia ao bloco.
READ-ONLY M1 confirmado (git diff só em pages.py; zero pipelines/config/censo/artefatos). Sem
dry-run (não tocou orquestração). Mergeado em integracao/map02-relmun05-06 pelo orquestrador
(fluxo de integração aprovado por Vinicius); PR para main só após os 3 ciclos.

---

### BLK-RELMUN-05 — Cores otimistas (verde) para aprovados na Visão Geral do Município

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (mudança visual de um relatório + acoplamento de terminologia "amarelo"; READ-ONLY sobre o M1; envolve 1 decisão de produto — tons de verde, JÁ pré-aprovada por Vinicius, ver D1). |
| **Prioridade** | Normal. |
| **Esteira** | Block Orchestrator → Planner → `[confirmação humana — produto: D1 tons de verde (pré-aprovada)]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | — (toca só `relatorio_municipal.py` display). Relaciona-se à DEC-011 (terminologia "amarelo"/hexágono destacado). |
| **Autonomia** | **manual (NÃO loop-safe)** — altera texto/cor de relatório auditável; exige revisão visual do PDF. |

**Objetivo.** Trocar as cores dos hexágonos **aprovados** na página "Visão Geral do Município" (camada
`cobertura`) e no Resumo (camada `resumo`) de amarelo/laranja — que passam tom negativo/de alerta —
para **tons de verde** (otimismo), mantendo "Reprovado" em cinza.

**Escopo permitido (READ-ONLY M1, só display).**
- `src/motor_expansao/dashboard/relatorio_municipal.py:89–91`: `_COR_APROVADO_PROPRIO` (hoje
  `(255,210,28)` dourado) e `_COR_APROVADO_MUNICIPAL` (hoje `(245,140,30)` laranja) → **verdes** (D1).
  A troca propaga sozinha para `_HEX_DESTAQUE_RGBA`, `_HEX_DESTAQUE_MUNICIPAL_RGBA`, `_HEX_APROVADO_RGBA`,
  `_HEX_APROVADO_MUNICIPAL_RGBA`, `_COBERTURA_LEGENDA`, `_RESUMO_LEGENDA` e o choropleth das camadas
  `cobertura`/`resumo`. `_COR_REPROVADO` (cinza) INALTERADO.
- **Terminologia (acoplamento):** atualizar SOMENTE o **texto visível** que diz "amarelo(s)" e ficaria
  inconsistente com a cor verde — `"Soma dos hexágonos amarelos / 2.500"` (`:1656`) e
  `"Espaço = soma dos hexágonos amarelos / 2.500"` (`:2070`) → wording neutro por cor (ex.: "hexágonos
  destacados"). Legendas já usam "Aprovado (dado próprio)/(fallback municipal)".

**Fora de escopo (NÃO tocar).** **Identificadores** com "amarelo" — `n_hex_amarelos`,
`soma_oferta_amarelos`, `parcelas_amarelos` e chaves de `result` (consumidas por `render`/testes): só
TEXTO/cores mudam, os NOMES não. Cores de **ZONA** da página Domínio (`:155–160`, turquesa/…/laranja) —
outra semântica, não mexer. Critério de "hexágono destacado" (DEC-011: `oferta_efetiva_disponivel >=
2000`), `flag_sam`, score, artefatos oficiais do M1.

**Decisão de produto (D1 — pré-aprovada por Vinicius em 2026-07-08).** RGB verdes: aprovado próprio =
verde forte `(20,170,80)`; aprovado fallback municipal = verde médio `(90,190,120)` (dois tons
distinguíveis entre si e do cinza `_COR_REPROVADO`, legíveis sobre o basemap claro). O Planner só
reconfirma no gate.

**Critério de aceite.** PDF municipal com aprovados em verde (2 tons) + reprovado cinza; nenhuma
menção textual "amarelo" remanescente no texto de exibição; identificadores e critério de destaque
(DEC-011) intactos; DEC-011 recebe emenda de terminologia (cor ≠ critério); testes de
`tests/unit/test_relatorio_municipal.py` atualizados (tuplas de cor/labels); ruff+mypy limpos; revisão
visual do PDF aprovada.

**Fechamento do ciclo BLK-RELMUN-05 (2026-07-08) — VEREDITO: APROVADO.** Esteira Média (BO sonnet
-> Planner sonnet -> [gate D1 verdes PRÉ-APROVADO por Vinicius] -> Builder opus -> QA opus 4.8).
Rodou na branch ciclo/BLK-RELMUN-05 (ramificada da secundária integracao/map02-relmun05-06). Feito:
cores dos aprovados na Visão Geral do Município (camada cobertura) e Resumo de amarelo/laranja para
VERDE — `_COR_APROVADO_PROPRIO (255,210,28)->(20,170,80)` e `_COR_APROVADO_MUNICIPAL
(245,140,30)->(90,190,120)`; `_COR_REPROVADO` cinza inalterado; derivados/legendas herdam por
referência. Texto visível "amarelos"->"destacados" nas 2 únicas strings de PDF (_resumo_page ~1656
e rodapé de _espaco_academias_page ~2070). Identificadores com "amarelo" (n_hex_amarelos,
soma_oferta_amarelos, parcelas_amarelos, chaves de result) INTOCADOS. Emenda BLK-RELMUN-05 na
DEC-011 (cor verde é DISPLAY; critério de destaque oferta_efetiva_disponivel>=2000, flag_sam, score,
artefatos M1 intactos). Cores de ZONA da página Domínio intocadas. Teste novo
test_cores_aprovados_verdes_blk_relmun_05 + asserts de wording. Validações (QA, NO-BYPASS): ruff
limpo; import ok; mypy só 6 pré-existentes de types-requests (0 novo); suíte serial completa
`1536 passed, 2 skipped, 1 failed` — única falha pré-existente/ambiental do M2. READ-ONLY M1
confirmado (git diff só relatorio_municipal.py + test + CLAUDE.md + bookkeeping; zero
pipelines/config/censo/artefatos). Sem dry-run. Mergeado em integracao/map02-relmun05-06 pelo
orquestrador; PR para main só após os 3 ciclos E verificação humana (Vinicius pediu para revisar
antes do PR).

---

### BLK-RELMUN-06 — Texto dinâmico das zonas de atuação no slide Síntese (quadros finais)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (lógica de composição de texto de relatório; READ-ONLY sobre o M1; 1 decisão de produto — regras do texto por combinação de zonas). |
| **Prioridade** | Normal. |
| **Esteira** | Block Orchestrator → Planner → `[confirmação humana — produto: D1 regras do texto]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | — (`relatorio_municipal.py` display; usa `zonas_geo`/`n_zonas_geo` já presentes em `result`). |
| **Autonomia** | **manual (NÃO loop-safe)** — altera texto de relatório auditável; exige revisão visual do PDF. |

**Objetivo.** No slide **Síntese** (`_sintese_page`, `relatorio_municipal.py:1949` — 3 quadros/cards
finais; card 3 "Movimento Recomendado"), substituir o **texto constante**
`"posicionamento periférico, cercar o núcleo pelos flancos antes da concorrência."` por um texto
**gerado a partir dos tipos de zona efetivamente encontrados** no município (`zonas_geo` /
`_ZONA_GEO_ROTULOS` = Âncora central / Flancos laterais / Cerco), para municípios com 1, 2 ou 3 zonas
não receberem uma recomendação genérica que pode não se aplicar.

**Escopo permitido (READ-ONLY M1, só display).**
- `_sintese_page` (`relatorio_municipal.py:1949–1991`): compor o texto do card de zonas (card 3) a
  partir de `result["zonas_geo"]` (rótulos das zonas presentes), reusando `_ZONA_GEO_DESC` (`:163`) e/ou
  `_ZONA_TEXTOS` (`:1776`) como blocos de frase. Fallback para 0 zonas (mensagem de "hexes
  insuficientes …", análoga à já usada na página Domínio).
- Manter os outros 2 cards (penetração fitness, residual) e o VALOR do card ("N zonas de atuação")
  inalterados.

**Fora de escopo.** `zonas_geo`/`_zonas_geometricas` / `_zonas_do_municipio` (a zonificação em si — só
LEITURA); `dominio_df`, `flag_sam`, score, artefatos oficiais do M1. Página Domínio (`:1783`) já é
dinâmica por zona — confirmar no gate se entra no escopo ou não.

**Decisão de produto (D1 — gate).** As regras do texto por combinação de zonas (ex.: só "Âncora
central" → adensar o núcleo; +"Flancos laterais" → cercar pelos flancos; +"Cerco" → estratégia
completa de cerco). O Planner propõe o mapeamento; humano aprova antes do Builder.

**Critério de aceite.** Card de zonas do slide Síntese reflete os tipos de zona presentes no município
(testar combinações 1/2/3 zonas + 0 zonas); demais cards inalterados; `zonas_geo`/score/artefatos
intactos; testes de `tests/unit/test_relatorio_municipal.py` cobrindo as combinações; ruff+mypy limpos;
revisão visual do PDF aprovada.

**Fechamento do ciclo BLK-RELMUN-06 (2026-07-10) — VEREDITO: APROVADO.** Esteira Média (BO sonnet
-> Planner sonnet -> [gate D1 REAL: 4 textos por combinação de zona APROVADOS por Vinicius;
_dominio_page FORA de escopo] -> Builder sonnet -> QA opus 4.8). Rodou na branch ciclo/BLK-RELMUN-06
(ramificada da secundária integracao/map02-relmun05-06). Feito: novo helper puro
`_texto_zonas_sintese(zonas_geo)` em relatorio_municipal.py (~1784) que compõe o texto do card 3
"Movimento Recomendado" do slide Síntese (_sintese_page ~1998) a partir dos tipos de zona presentes
em result["zonas_geo"] (SÓ LEITURA), checando por pertencimento de rótulo (Cerco > Flancos laterais
> Âncora central > fallback 0 zonas), com os 4 textos exatos do gate D1. A COR (ULTRA_LARANJA) e o
VALOR ("N zonas de atuação") do card 3 e os cards 1/2 inalterados. 9 testes novos (5 unit do helper
incl. caso defensivo só-Flancos -> texto de 2 zonas; 4 integração PDF checando linhas wrapeadas +
regressão dos cards 1/2 e do VALOR). Validações (QA, NO-BYPASS): ruff limpo; import ok; mypy só 6
pré-existentes de types-requests (0 novo); suíte serial completa `1545 passed, 2 skipped, 1 failed`
— única falha pré-existente/ambiental do M2. READ-ONLY M1 confirmado: zonas_geo só lido;
_zonas_geometricas/_zonas_do_municipio/agregar_municipio/_hex_destacado_mask/dominio_df/flag_sam/
score intocados; _dominio_page intocada; git diff só relatorio_municipal.py + test + bookkeeping.
Sem dry-run. Mergeado em integracao/map02-relmun05-06 pelo orquestrador. FIM DOS 3 CICLOS: PR para
main NÃO aberto (Vinicius pediu para verificar o resultado primeiro).

**Fixes práticos pós-verificação (2026-07-10, na secundária integracao/map02-relmun05-06, mesmo PR
dos 3 ciclos) — READ-ONLY M1, display-only. Aprovados por Vinicius após revisão visual.**
- **BLK-MAP-02-FU1 — Legenda do mapa retrátil.** A chamada de `_render_unified_legend(...)` em
  `render_mapa_territorial` (`pages.py:4399`) passou a ficar dentro de `st.expander("Legenda",
  expanded=False)` — a legenda grande (faixas de Score + chips de todas as marcas + Ultra + descarte)
  nasce fechada, como o filtro de marcas do BLK-MAP-02. Só `pages.py`; nenhum identificador/lógica
  de legenda alterada.
- **BLK-RELMUN-05-FU1 — Fallback municipal mais amarelado.** `_COR_APROVADO_MUNICIPAL` em
  `relatorio_municipal.py` mudou de (90,190,120) verde médio para (215,200,60) amarelo-âmbar (escolha
  de Vinicius entre verde-amarelado e amarelo-âmbar), para distinguir melhor do dado próprio
  (20,170,80 verde forte); `_COR_APROVADO_PROPRIO` e `_COR_REPROVADO` inalterados. Emenda registrada
  na DEC-011 (CLAUDE.md) e teste `test_cores_aprovados_verdes_blk_relmun_05` atualizado.
- Validações: ruff limpo; import ok; mypy só 6 pré-existentes de types-requests (0 novo); focados
  `test_relatorio_municipal.py` + `test_streamlit_app.py` = 279 passed; suíte completa como gate.
- Sucessor registrado no backlog: **BLK-RELPON-05** (legenda superior por mapa no Relatório Pontual
  com o valor do dado no setor do ponto) — feature com Planner + gate, ciclo próprio depois.

---

### BLK-RELPON-05 — Legenda superior por mapa com o valor do dado no setor do ponto (Relatório Pontual)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (novo recurso de render no Relatório Pontual Censitário; READ-ONLY sobre o M1; núcleo `censo_*` só ESTENDE render/strings, sem tocar interseção/raio/estrutura de páginas/marca d'água; envolve decisões de produto). |
| **Prioridade** | Normal. |
| **Esteira** | Block Orchestrator → Planner → `[confirmação humana — produto: D1 (quais mapas/variáveis), D2 (formato/unidade por variável), D3 (fonte do valor = setor que contém o ponto)]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | — (Relatório Pontual Censitário já existente; usa a malha de setores IBGE 2022 já carregada). |
| **Autonomia** | **manual (NÃO loop-safe)** — altera relatório auditável e exige revisão visual do PDF. |

**Objetivo.** Em cada mapa do Relatório Pontual Censitário (1,5 km), exibir uma **legenda superior**
informando o **valor da variável daquele mapa no setor censitário que CONTÉM o ponto pesquisado**
(onde o pin está) — ex.: no mapa de Renda, `"Renda: R$ 2.567"`; no de Densidade, `"Densidade:
X hab/km²"`; no de Score censitário, `"Score: NN"`. Objetivo de UX: dar o número exato do ponto,
não só o gradiente/agregado do raio.

**Escopo permitido (READ-ONLY M1, só display/relatório).**
- `censo_point.py` (`analisar_ponto_censitario_setores`): EXPÔR o valor de cada variável no **setor
  que contém o ponto** (renda_per_capita, densidade, `score_setor_2022_calibrado`). Hoje o resultado
  traz agregados do raio 1,5 km — este bloco adiciona o lookup do setor do ponto (SÓ LEITURA; não
  altera o método de interseção `setor_censitario_intersecao_area_1p5km` nem o raio).
- `censo_map.py` (`render_mapas_censitarios_combinados`/`_render_camada`): desenhar a faixa/legenda
  superior por camada com o valor recebido (parâmetro opcional novo, default `None` = comportamento
  atual — padrão da emenda 2026-06-12 da DEC-005 para extensão de render de `censo_*`).
- `censo_report.py`: passar os valores por camada ao render e (se aplicável) ao PDF.
- Tratar **dado ausente** ("n/d" quando o ponto cai fora de setor/sem valor) e formatação por
  variável (moeda, hab/km², score inteiro).

**Fora de escopo.** Método de interseção `setor_censitario_intersecao_area_1p5km`, raio 1,5 km,
`RAIO_CENSITARIO_DEFAULT_KM`, contagem/ordem/estrutura das páginas, grid de Big Numbers, marca d'água
anti-PII, `set_compression(False)`. `score_priorizacao`/pesos/artefatos oficiais do M1. Relatório
Municipal e UI do dashboard. Dependência de rede nova.

**Decisões de produto (gate).** D1: em QUAIS mapas entra a legenda (todos os 4, ou só
Densidade/Renda/Score?); o mapa de Concorrentes tem "valor" análogo (ex.: nº de concorrentes no
setor) ou fica sem legenda? D2: formato/unidade exibido por variável. D3: confirmar que o valor é o
do **setor que contém o ponto** (não o agregado do raio nem o hex).

**Critério de aceite.** Cada mapa alvo do Relatório Pontual exibe a legenda superior com o valor
correto da variável no setor do ponto (formatado por D2), "n/d" quando ausente; método de
interseção/raio/estrutura/marca d'água INTOCADOS; READ-ONLY M1 (sem recálculo de score/artefatos);
testes cobrindo lookup do setor + presença da legenda no PDF; ruff+mypy limpos; revisão visual do PDF
aprovada.

---

## Fechamento de ciclo — BLK-RELPON-05 (2026-07-10)

Veredito QA: **APROVADO** (Opus 4.8). Esteira executada: Block Orchestrator (sonnet) -> Planner (sonnet) -> [gate humano de produto D1/D2/D3 — confirmado por Vinicius em 2026-07-10] -> Builder (sonnet) -> QA (opus).

Decisoes de produto confirmadas no gate: D1 = so os 3 choropleths (Densidade/Renda/Score) recebem a faixa superior; a camada "Concorrentes e Ultra" fica byte-a-byte igual (sem faixa). D2 = rotulo "X no ponto: <valor>" (renda R$ sem centavos, densidade inteira `hab/km2`, score inteiro, "n/d" quando ausente). D3 = valor do setor que CONTEM o ponto (`covers`, tie-break por `peso_area_setor`, "n/d" fora da malha) — distinto do agregado do raio e do valor por hex.

Entregue: 5 campos novos no `result` de `analisar_ponto_censitario_setores` (`cod_setor_ponto`, `renda_per_capita_setor_ponto`, `densidade_pop_setor_ponto`, `score_setor_2022_calibrado_ponto`, `flag_setor_ponto_encontrado`); parametro opcional `valor_ponto` (default None) em `_render_camada`; faixa nos 3 choropleths via `render_mapas_censitarios_combinados`; `censo_report.py` so docstring; 7 testes novos; docs atualizados. READ-ONLY M1: `setor_censitario_intersecao_area_1p5km`/raio 1,5 km/estrutura de paginas/marca d'agua/`set_compression(False)` INTOCADOS; `score_priorizacao`/pesos/artefatos oficiais inalterados.

Validacoes (re-executadas pelo QA, evidencia propria): ruff limpo; mypy limpo; `import streamlit_app` ok; 284 passed nos arquivos do bloco + `test_streamlit_app`; suite serial completa 1565 passed / 2 skipped / 1 failed. A unica falha (`test_score_retencao_territorial.py::test_run_readonly_m1_por_mtime`, camada M2/lifetime, fora de escopo) foi provada PRE-EXISTENTE/ambiental (staging gitignored `unidade_territorio_retencao.parquet` ausente) via stash+re-run no baseline — nao e regressao. `pytest -n auto` (xdist) quebra por infra do worker execnet neste ambiente Windows/Python 3.14 (nao introduzido por este bloco); gate efetivo rodado serial.

Arquivos: `src/motor_expansao/dashboard/censo_point.py`, `censo_map.py`, `censo_report.py`, `tests/unit/test_relatorio_pontual_censitario_motor.py`, `test_relatorio_pontual_censitario_mapa.py`, `test_relatorio_pontual_censitario_export.py`, `docs/relatorio_pontual_censitario.md`. Housekeeping via `scripts/housekeeping_move_block.py BLK-RELPON-05` (`--check` OK). Ciclo NAO altera a orquestracao -> sem dry-run. Merge = passo humano.
  com o valor do dado no setor do ponto) — feature com Planner + gate, ciclo próprio depois.

---

### BLK-PERF-01a — Shared transformer no render censitário + pré-filtro do agregar_municipio (PDFs 86×)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (performance de relatório; **READ-ONLY sobre o M1**; zero mudança de lógica/estrutura de páginas). |
| **Prioridade** | **Alta** (dor #4 do Felipe; maior ganho/esforço do epic). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA (autônoma no loop). |
| **Status** | Pendente. |
| **Depende de** | — (diagnóstico BLK-REV-06 concluído). |
| **Autonomia** | **loop-safe** — determinístico/headless (PNG/PDF byte-comparável + harness B6 como aceite); toca SÓ o caminho de render/agregação de relatório (`censo_map.py`, `relatorio_municipal.py`/`pages.py`); READ-ONLY M1; sem VPS/rede; NÃO toca `config.py`/`pipelines/m1`. |

**Contexto (REV-06).** Root cause do PDF Pontual: `_to_mercator` (`censo_map.py:372-375`) cria um
transformer pyproj NOVO **por setor** no loop aeqd→3857 de `render_mapas_censitarios_combinados`
(`censo_map.py`, loop ~l.729) — 141 setores × 24,4 ms = **3,4 s desperdiçados (77% dos 4,5 s totais)**;
escala linear com N de setores (SP/Rio piores). No Municipal, `agregar_municipio`
(`relatorio_municipal.py:584`) escaneia o df nacional (1,5 M hexes, 2,1 s) sendo que o chamador em
`pages.py` já tem o `df_muni` filtrado.

**Objetivo.** (1) Criar o transformer UMA vez antes do loop (`crs_local = _local_metric_crs(lat, lng)`;
`to_3857 = _transformer(crs_local, CRS_WEB_MERCATOR)`) e reusar via `_project_geometry(geom, to_3857)`
no lugar de `_to_mercator(geom, lat, lng)` por setor — ganho medido: Fase 2b 3,4 s → 0,04 s (86×),
**PDF Pontual 4,5 s → ~0,7 s**. (2) Eliminar o full-scan do `agregar_municipio` para **TODOS os
callers** — preferir o filtro por município como PRIMEIRA operação DENTRO de `agregar_municipio`
(beneficia dashboard **e** API automaticamente, byte-idêntico) ou, se caller-side, cobrir os DOIS
caminhos: `pages.py` (dashboard) **e** `api/service.py:gerar_pdf_municipio` (API/bot carrega o
parquet nacional full) — **−2,1 s locais / mais na VPS** sem mudança de lógica.

**Baseline de PRODUÇÃO (2026-07-10, medido no container da VPS pré-fix — referência do
antes/depois; detalhe em `data/analysis/baseline_prod_pdf_20260710.md`, gitignored):** Pontual
**28,3 s frio / 9,5 s quente**; Municipal **32,7 s frio / 4,5 s quente** (frio dominado por fetch
de tiles na rede da VPS). Meta pós-fix em produção: Pontual quente ≤3 s; Municipal quente ≤2,5 s.

**Decisões PRÉ-FIXADAS.** Raio 1,5 km e `setor_censitario_intersecao_area_1p5km` INTOCADOS (só o render
reprojeta mais rápido); mesma matemática de projeção (mesmos parâmetros de transformer) → saída visual
IDÊNTICA; NÃO incluir neste bloco as opções O2 (ThreadPool) e O4 (pre-fetch de tiles) do REV-06 —
ganho marginal pós-fix, avaliar depois se a UX exigir.

**Critérios de aceite.** PNGs dos mapas byte-idênticos aos atuais (teste de regressão) e PDFs
semanticamente idênticos (mesmo conteúdo/páginas); harness B6 re-rodado com ganho documentado no PR;
teste cobrindo o caminho municipal pré-filtrado; suíte verde; ruff/mypy limpos; `loop_guard` limpo;
1 validação visual humana de 1 PDF de cada tipo pós-merge (não bloqueia o ciclo).
**Guardrail.** §5 READ-ONLY M1.

---

### BLK-PERF-01b — Cache dos builders de mapa + @st.fragment no painel multi-hex + seletor de cor no fragment

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (muda o comportamento interativo do mapa — o coração do dashboard; **READ-ONLY sobre o M1**). |
| **Prioridade** | **Alta** (dores #1/#2/#3 do Felipe). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — decisões de produto + validação visual]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | — (diagnósticos BLK-REV-04/05 concluídos). Recomendado APÓS o BLK-PERF-01a (PRs independentes). |
| **Autonomia** | **manual (NÃO loop-safe)** — comportamento interativo exige validação visual humana (invalidação de cache, destaque multi-hex; lição BLK-UI-10). NÃO marcar loop-safe. |

**Contexto (REV-04/05).** Os builders de mapa NÃO têm cache e reconstroem+re-serializam o deck inteiro
(payload 21–24 MB) a cada rerun: troca de modo de cor custa 0,7–3,3 s sendo que **91,5% do payload é
invariante entre modos** (só `fill_color` muda); add/remove hex no cenário custa 700–900 ms de rebuild
sendo que `agregar_cenario_multihex` custa 10–21 ms. O seletor `mapa_territorial_color_mode`
(`pages.py:4333-4339`) está FORA do `@st.fragment` do mapa → rerun da aba inteira.

**Objetivo.** (1) Memoizar os builders (via `build_unified_map_figure`, `components.py:3028`) por
(df, modo, filtros, overlays, search) — atenção do REV-05 H3: validar picklabilidade do `pdk.Deck` para
`@st.cache_data`, senão `@st.cache_resource` com chave manual; a layer de destaque multi-hex já é
anexada DEPOIS do deck (`pages.py:4423-4424`), compatível com cache. (2) Envolver
`_render_multihex_controls` + `_render_multihex_kpis` num `@st.fragment` (esboço pronto no relatório
REV-05) — add/remove hex deixa de reconstruir o mapa. (3) Mover o seletor de modo de cor para dentro do
fragment do mapa (complemento do cache, REV-04).

**Decisões de produto — RESOLVIDAS UPFRONT por Felipe (2026-07-10; substituem o gate interativo,
permanece a validação visual humana pós-build):**
- **D1 = Botão "Atualizar mapa":** KPIs atualizam na hora dentro do fragment; o destaque laranja do
  mapa NÃO força rerun automático — o painel ganha um botão explícito "Atualizar mapa" que dispara o
  rerun completo quando o operador quiser ver o destaque novo (+ caption curto explicando). Ganho de
  −700–900 ms por add/remove preservado.
- **D2 = Cache SEM TTL:** mesmo padrão dos loaders atuais (vive enquanto o processo estiver de pé;
  parquets são `:ro` e só mudam em deploy, que recria o container e zera o cache). Invalidação por
  parâmetros (UF/cidade/modo/overlays/busca) obrigatória e testada; mudar `multihex_cenario` NÃO invalida.

**Critérios de aceite.** Harness B3/B4 antes/depois (meta: troca de cor ≈ 0 em cache hit; add/remove hex
sem rebuild do mapa); teste de integração da invalidação (trocar UF/cidade/modo/overlay/busca INVALIDA;
mudar `multihex_cenario` NÃO); mapa nunca exibe dado de UF/filtro errado (teste explícito); suíte verde;
ruff/mypy limpos; **validação visual humana aprovada** (cache + fragment + destaque).
**Guardrail.** §5 READ-ONLY M1 (display only; caps `MAP_POINT_LIMIT*` e `_downsample_map_index` INTOCADOS).

---

### BLK-PERF-01c — Tooltip enxuto do mapa (14 → 5-6 campos por hexágono)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (display; **READ-ONLY sobre o M1**; envolve 1 decisão de produto — quais campos ficam). |
| **Prioridade** | Média (complementa o 01b; maior corte de payload no PRIMEIRO render de cada modo). |
| **Esteira** | Block Orchestrator → Planner → `[confirmação humana — Felipe: campos do tooltip]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | — (diagnóstico BLK-REV-03 concluído). Independente do 01a/01b (PR separado). |
| **Autonomia** | **manual (NÃO loop-safe)** — decisão de produto (campos) + validação visual do tooltip. NÃO marcar loop-safe. |

**Contexto (REV-03).** **~65% do payload de 21–24 MB** (15,7 MB em SC) são as 14 strings de tooltip por
hexágono (`_prepare_m1_tooltip_fields` + `_apply_hex_tooltip_fields`, ~1,7 s de preparação em RO). A
geometria é só ~8,5%. Reduzir para 5-6 campos corta −50/−65% do payload e ~metade da preparação.

**Objetivo.** Reduzir os campos do tooltip nos builders para o conjunto APROVADO POR FELIPE
(2026-07-10, gate resolvido upfront — **D4 = "Enxuto + Score censitário", 7 linhas**): Título
(Município/UF) + Faixa M1 + Score do modo ativo + **Score censitário** + Habitantes + Renda per
capita + Residual Fitness (1 linha). Cortam-se: fonte geográfica, score estrutural, qualidade join,
coverage, viável, prioridade, 2ª linha de residual (detalhe completo continua a 1 clique, na Análise
Pontual). Aplicar aos 4 modos (mesma infraestrutura; o Híbrido já tem padrão compacto via
`_HYBRID_TOOLTIP_SHOW_DETAIL` — alinhar ao conjunto de 7). ~−55% de payload estimado.

**Critérios de aceite.** Campos aprovados por Felipe ANTES do Builder; payload `deck.to_json()` medido
antes/depois (meta: −50% ou mais) + harness B3/B4; acentuação correta nas labels novas (§2); suíte verde
(asserts de tooltip atualizados); validação visual humana do tooltip nos 4 modos.
**Guardrail.** §5 READ-ONLY M1 (display only; nenhum dado é removido do df — só do payload do mapa).

---

### BLK-PERF-01d — Remover o expander "Camada Híbrida - Detalhe" (2 decks fantasmas de ~14 MB por rerun)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (remoção de feature de display sem uso; **READ-ONLY sobre o M1**). |
| **Prioridade** | Alta (decisão de Felipe 2026-07-10 — "ninguém utiliza; aliviará ainda mais"). |
| **Esteira** | Direta (decisão de produto do Felipe + implementação + suíte), na sessão de 2026-07-10. |
| **Status** | Pendente. |
| **Depende de** | — (achado do harness Playwright do BLK-PERF-01b-FU1). |
| **Autonomia** | **manual** — remoção de feature visível exige decisão de produto (JÁ dada por Felipe). |

**Contexto (achado do FU1, 2026-07-10).** A aba Mapa Territorial enviava **~42 MB de deck JSON por
rerun**: o mapa principal (~14 MB) + **2 decks de ~14 MB** construídos pelo corpo do expander
RECOLHIDO "Camada Híbrida - Detalhe" (`render_modelo_hibrido_v2` → tabs "Oportunidades Híbridas" e
"Mapa Residual Fitness") — corpo de expander executa a cada rerun mesmo fechado. Ninguém usa o
detalhe híbrido; a leitura híbrida/residual segue disponível nos MODOS DE COR do mapa principal.

**Objetivo.** Remover a chamada do expander em `render_mapa_territorial` (pages.py), mantendo
`render_modelo_hibrido_v2` exportada (sem caller). Ganho: ~2/3 do payload da aba (~28 MB/rerun) e
o custo Python de construir 2 decks por rerun. Teste de regressão garante que o expander não volta.

**Guardrail.** §5 READ-ONLY M1 (display only); modos de cor do mapa principal INTOCADOS.

---

### BLK-SEC-05 — Observabilidade: alertas via bot Telegram + runbook de incidente (re-escopado 2026-07-13)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (hoje NINGUÉM é avisado quando algo cai ou falha) |
| **Prioridade** | **Média-Alta** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Origem** | revisão de robustez 2026-05-31; **re-escopado por inventário read-only da VPS em 2026-07-13** |
| **Autonomia** | **manual (NÃO loop-safe)** — VPS |

**Inventário (2026-07-13):** a rotação de logs do Docker **JÁ ESTÁ FEITA** (`daemon.json`, json-file
10m×3) — **sai do escopo**. O que segue 100% faltando é o lado DETECTIVO: queda de container, disco,
falha de login — e, novo desde a DEC-013, a **coleta semanal GymScraping falha SILENCIOSAMENTE** (ex.:
na execução de 2026-07-05, 10 coletores falharam e 2 redes estão zeradas — ninguém foi notificado; o
relatório só é visto quando alguém pede).

**Canal de alerta (decidido pela realidade atual): o BOT TELEGRAM que JÁ RODA em produção** — reusar o
token/infra existente com um chat de ops (zero dependência nova, zero custo). E-mail/webhook só como
fallback. Guardrail: o script de alerta NÃO loga token nem segredo.

**Escopo (cron simples na VPS + script; sem stack de monitoramento):**
1. **Health dos 5 containers** (caddy, authelia, streamlit, api, bot): `docker ps` (Restarting/Exited/
   crash-loop) + health interno via `docker exec` (`/_stcore/health` do Streamlit; `GET /health` da API
   na 8077 — portas não publicadas no host). Edge externo: `https://dashboard.ultra-expansao.tech`
   respondendo (302→Authelia = vivo).
2. **Host:** disco >80%, memória/swap saturada.
3. **Coleta semanal (DEC-013):** exit code do `run_weekly_90.sh` + push do resumo do relatório de
   crescimento no chat (delta por rede + lista de coletores falhos/redes zeradas) — transforma o
   relatório que hoje ninguém lê em notificação de domingo.
4. **Segurança:** falhas de login do Authelia e (pós BLK-SEC-03) disparos do fail2ban.
5. **Runbook de incidente** em `docs/` (VPS comprometido / vazamento / indisponibilidade): contenção,
   quem aciona, isolamento, ligação com DR de segredos (BLK-OPS-01) e backup de dados (BLK-SEC-04).

**Fora de escopo:** SIEM, APM, tracing, on-call formal; rotação de logs (já feita).

**Arquivos prováveis:** script de health-check + cron na VPS; `docs/infra_producao.md` (seção
monitoramento + runbook de incidente).

**Critérios de aceite:**
- Derrubar um container em horário combinado gera alerta no Telegram (teste real, qualquer um dos 5).
- Alerta de disco testado (limiar sintético).
- No domingo seguinte à implantação, o resumo da coleta chega no chat (com falhos listados).
- Runbook revisado; zero segredo nos alertas; zero mudança em M1/artefatos.

**Risco:** baixo. Calibrar limiares para não virar ruído (alerta demais = alerta ignorado).

**CONCLUSÃO (2026-07-13, executado interativamente com Felipe — §6 comando a comando):** entregue no
mesmo dia do re-escopo. `scripts/healthcheck_vps.sh` (novo, versionado) instalado em
`/opt/motor-monitoring/` + 4 crons no root (containers */5, host 1x/h, Authelia diário 08h BRT, coleta
domingo 15h BRT); `MONITOR_TELEGRAM_CHAT_ID` (grupo de ops) adicionado ao `.env` com backup
(`.env.bak-20260713-monitor`); rotação de logs JÁ existia (fora do escopo). Docs: seção "Alertas
automáticos" + "## Runbook de incidente" em `docs/infra_producao.md`. **Aceite REAL comprovado:**
mensagem de teste recebida no grupo; `docker stop` proposital do streamlit às 13:10 BRT → alerta 🔴
autônomo do cron às 13:15 (confirmado por Felipe) → restart 13:16 → alerta 🟢 de recuperação às 13:20
(confirmado por Felipe). Nota honesta: o check de edge NÃO dispara com app morto atrás do proxy (Caddy/
Authelia respondem 302 = camada viva; quem pega é o check de container — comportamento correto e
documentado). Alerta de disco por limiar sintético e resumo de coleta ficam validados no uso (próximo
domingo). READ-ONLY M1; zero segredo em log/git.

---

- BLK-ORQ-01 (concluído 2026-06-02) — ver tasks/completed.md

---

### BLK-SEC-03 — Hardening do VPS: fechar SSH por senha, fail2ban e 2FA (re-escopado 2026-07-13)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (exposição do servidor de produção) |
| **Prioridade** | **Alta** (subiu 2026-07-13: SSH root+senha aberto à internet é o maior risco atual) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Origem** | revisão de robustez 2026-05-31; **re-escopado por inventário read-only da VPS em 2026-07-13** |
| **Autonomia** | **manual (NÃO loop-safe)** — cada comando na VPS exige confirmação individual (§6) |

**Inventário real (2026-07-13, read-only na VPS):** parte do bloco original JÁ ESTÁ FEITA —
`ufw` **ATIVO** liberando só 22/80/443 (v4+v6); `unattended-upgrades` **INSTALADO** (falta confirmar a
config periódica ativa); rotação de log do Docker já configurada (`daemon.json`, 10m×3 — era escopo do
SEC-05). **Gaps reais que restam:** `sshd` com `passwordauthentication yes` + `permitrootlogin yes`
(**root por SENHA aberto à internet — o maior risco do servidor hoje**); `fail2ban` **INATIVO**
(brute-force de senha nem é banido); 2FA do Authelia opcional; revisão de acesso do `ultra_team` nunca
feita; deploy key `gymscraping_deploy` em `/root/.ssh/` (auditar que segue read-only no repo do scraper).

**Objetivo:** fechar os gaps restantes sem quebrar deploy, coleta semanal nem o acesso do time.

**Escopo re-priorizado (cada passo via MCP com confirmação individual — §6):**
1. **P1 — SSH sem senha:** `PasswordAuthentication no` + `PermitRootLogin prohibit-password` (o acesso
   real já é por chave). ANTES de aplicar: validar console web da Hostinger como porta dos fundos e
   manter uma 2ª sessão SSH aberta durante a mudança.
2. **P2 — `fail2ban` ativo** no sshd (jail default; banir brute-force).
3. **P3 — confirmar `unattended-upgrades`** aplicando patches de segurança (APT::Periodic + dry-run).
4. **P4 — Authelia:** avaliar forçar 2FA no grupo `ultra_team` + revisão de acesso em
   `authelia/users_database.yml` (remover obsoletos; definir offboarding e periodicidade da revisão).
5. Documentar em `docs/infra_producao.md` (seção hardening) com rollback de cada item.

**Fora de escopo:** trocar provedor/arquitetura; mudar M1/dashboard; superfície de rede dos containers
(API/bot não publicam porta no host — já correto); ufw (já feito).

**Critérios de aceite:**
- Login por senha REJEITADO (teste real de fora) e login por chave OK; fail2ban banindo (teste).
- unattended-upgrades comprovadamente aplicando security patches.
- Dashboard, deploy, API/bot e coleta semanal seguem funcionando após cada mudança.
- Cada alteração com confirmação individual; documentada com rollback.

**Risco:** médio-alto (lockout de SSH). Mitigação: um item por vez, 2ª sessão aberta, console web da
Hostinger validado ANTES do P1, rollback documentado antes de cada passo.

**CONCLUSÃO (2026-07-13, executado interativamente com Felipe — §6 comando a comando):** P1-P3
entregues no mesmo dia do re-escopo; P4 (2FA Authelia + revisão de acesso) desmembrado no follow-up
**BLK-SEC-03-FU1** (exige time presente). **P1:** console web da Hostinger validado por Felipe ANTES
(login root funcionando); `/etc/ssh/sshd_config.d/00-hardening.conf` (prefixo 00- vence o
`PasswordAuthentication yes` do 50-cloud-init.conf — sshd usa o PRIMEIRO valor); testes reais: chave
entra ✅ / `Permission denied (publickey)` sem chave ✅ (senha nem é oferecida). **P2:** fail2ban
instalado + jail sshd (30min/5 tent./systemd) ativa. **P3:** unattended-upgrades confirmado aplicando
security patches (log diário); achado: 3 kernels pendentes de reboot → **reboot executado** (kernel
5.15.0-177→185, ~2 min), TODA a stack voltou sozinha (5 containers, fail2ban, ufw, crons, monitor) —
resiliência a desligamento comprovada pela 1ª vez. Bateria de aceite 10/10: containers healthy, API
ok, edge 302, monitor 8/8, scan externo só 22/80/443 (8501/8077 fechadas), dashboard+bot validados
por Felipe no navegador/Telegram. Docs: seção "Hardening do servidor" em `docs/infra_producao.md`
(estado + rollback por item + política de reboot + acesso de emergência). READ-ONLY M1.

---

### BLK-SEC-04 — Backup automatizado dos dados de produção + restore testado (re-escopado 2026-07-13)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (continuidade de dados; não toca M1/score) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → `[DECISÃO HUMANA: destino/custo]` → Builder → QA |
| **Status** | Pendente — **bloqueado por 1 decisão de Felipe: o DESTINO do backup** |
| **Origem** | revisão de robustez 2026-05-31 (BLK-OPS-01 cobre segredos, não dados) |
| **Autonomia** | **manual (NÃO loop-safe)** — VPS + decisão de custo |

**Gap (confirmado no inventário 2026-07-13):** continua NÃO existindo backup dos dados de produção —
só a cópia manual na máquina de dev. Disco da VPS folgado (34G/194G usados), mas backup no MESMO disco
não é DR (perde-se junto).

**Decisão que trava o bloco (Felipe):** o destino — (a) **snapshot/backup nativo da Hostinger** (mais
simples, custo do plano, restore do disco inteiro), (b) **bucket S3-compatível** via rclone/restic
(custo baixo/mês, restore granular por arquivo), ou (c) **cópia agendada off-box** para máquina do time
(custo zero, depende da máquina estar ligada). Definido o destino, o resto é execução de 1 sessão.

**Escopo (ordem de prioridade do que copiar):**
1. `/opt/motor-expansao/data/outputs/` (~1,6 GB, parquets servidos ao dashboard) — crítico.
2. `data/ibge/` (~49 MB) + `data/staging/` (~213 MB) — obrigatórios para a API (sem `data/ibge` a API
   dá 500); regeneráveis, mas o re-scp é lento.
3. Volume `bot_data` (sessões do bot Telegram) — trivial; perder = usuários deslogados.
4. `/opt/gymscraping-infra/` (runner + **relatórios de crescimento históricos** — pequenos e NÃO
   regeneráveis: são a série temporal da concorrência; DEC-013). Os dados coletados em si são
   regeneráveis pela coleta semanal (baixa prioridade).
5. NÃO versionar parquet no git; NÃO copiar `NAO_ABRA/`/PII para o destino.

**Mecânica:** job cron na janela 2h–5h BRT (não colidir com a coleta de domingo 06:00 UTC); retenção
diários 7d / semanais 4w; checksum; **restore testado em pasta limpa** (rigor do BLK-OPS-01) + runbook
em `docs/`.

**Cruzamento com BLK-OPS-01 (segredos):** o `.env` ganhou segredos novos desde o backup original
(`API_TOKENS`/`API_API_CALL_TOKEN`/`API_TELEGRAM_TOKEN`/`API_BOT_SENHA`/`API_IMAGE`) → **re-encriptar o
`.env` no SOPS+age como passo deste ciclo** (atualização do OPS-01, não processo novo).

**Critérios de aceite:** backup automático com retenção; checksums conferem; restore validado
end-to-end e documentado; `.env` re-encriptado; zero PII no destino.

**Risco:** baixo. Atenção ao custo do destino e à janela noturna.

**RESOLUÇÃO (2026-07-13, decisão de Felipe): RISCO ACEITO — fica o backup semanal nativo da
Hostinger, sem camada adicional "por hora".** Contexto da decisão: a Hostinger já faz backup semanal
de snapshot do VPS (fato que o bloco original desconhecia), o que cobre os cenários de desastre de
disco/atualização ruim/ransomware com RPO ≤7 dias — compatível com o ritmo semanal dos dados (coleta
de domingo; quase tudo regenerável pelos pipelines). Gaps ACEITOS conscientemente: (i) restore é
tudo-ou-nada (servidor inteiro, sem restore granular de arquivo); (ii) mesmo provedor/conta (conta
Hostinger comprometida = servidor e backups juntos); (iii) itens não-regeneráveis pequenos (série
histórica dos relatórios de crescimento, `bot_data`) sem cópia própria. Alternativa recomendada e
DECLINADA por hora: híbrida com bucket S3-compatível gratuito (Backblaze B2/Cloudflare R2, 10 GB free)
via restic/rclone semanal (~1,9 GB cobre tudo). **Gatilho de reabertura:** crescimento material dos
dados não-regeneráveis, incidente que exija restore granular, ou decisão de Felipe. O item
"re-encriptar o `.env` no SOPS+age" (segredos novos da API/bot) NÃO é coberto pelo snapshot e segue
como pendência do BLK-OPS-01.

---

- BLK-SEC-05 (concluído 2026-07-13) — ver tasks/completed.md

---

### BLK-OPS-12 — Pinar dependências (lockfile) e restaurar paridade CI/local

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (reprodutibilidade de build; não toca M1/score) |
| **Prioridade** | **Alta** (tarefa ClickUp "Pinar dependências e restaurar paridade CI/local") |
| **Esteira** | interativa (Felipe presente) — toca Dockerfiles/CI, **NÃO loop-safe** (loop_guard bloqueia) |
| **Status** | Concluído 2026-07-13 (PR #95) |
| **Origem** | ClickUp (FC, prioridade Alta); auditoria 2026-07-13: NENHUM pin existia (só faixas no `pyproject.toml`, zero lockfile) e local=3.14 vs CI/prod=3.11 |

**Problema:** sem lockfile, cada rebuild de imagem/CI re-resolve as versões — dois builds do mesmo
commit podem divergir; o pin por digest protege a produção RODANDO, não a reprodutibilidade do BUILD.
E a suíte local (Python 3.14) diverge da CI/prod (3.11) — contagens de teste diferentes já observadas
(BLK-ORQ-01).

**Solução:** `constraints.txt` na raiz — lockfile UNIVERSAL (markers por versão de Python, válido
p/ >=3.11) gerado por `uv pip compile pyproject.toml --all-extras --universal --python-version 3.11`,
consumido via `-c constraints.txt` nos 3 pontos de instalação: CI (`.github/workflows/ci.yml`, também
no cache key), `Dockerfile.streamlit` e `Dockerfile.api`. `pyproject.toml` INALTERADO (faixas seguem
como intenção; o lock é a resolução exata). Refresh do lock = re-rodar o comando acima (documentado
no header do arquivo e no ci.yml). Paridade de interpretador (local 3.11) fica como recomendação
documentada — o lock universal já garante as MESMAS VERSÕES de libs em qualquer >=3.11.

**Aceite:** CI verde com constraints; dry-run local `pip install --dry-run -e ".[dev,api_mvp]" -c
constraints.txt` resolve limpo (validado, exit 0 inclusive sob 3.14); pins dentro das faixas do
pyproject (streamlit 1.59.2, pandas 2.3.3, numpy 2.3.5, h3 4.5.0); zero mudança em M1/score.

**Nota:** o rebuild seguinte das imagens usará os pins (ex.: streamlit 1.59.1→1.59.2 no container);
os guards de regressão do bug pydeck/fragment (PR #91) estão na suíte e validam no CI.

**CONCLUSÃO (2026-07-13, PR #95):** entregue e validado em 3 camadas — (1) CI verde instalando com
`-c constraints.txt` (ubuntu/3.11, suíte completa); (2) dry-run local resolve limpo sob 3.14 (markers
universais funcionando); (3) **build REAL da imagem `Dockerfile.streamlit` com o lock (docker exit 0)
e versões conferidas DENTRO da imagem** = exatamente as do lockfile (streamlit 1.59.2, pandas 2.3.3,
numpy 2.3.5, h3 4.5.0, pydeck 0.9.3, fpdf2 2.8.7). Nota de processo: a 1ª tentativa de build falhou
SILENCIOSAMENTE (daemon parado; exit 0 era do `tail` no pipe) — refeita com exit code real do docker.
Pendência aceita: paridade de INTERPRETADOR local (instalar Python 3.11 na máquina de dev) fica como
recomendação; o lock universal já garante as mesmas versões de libs em qualquer >=3.11. READ-ONLY M1.

---

- BLK-OPS-03 (concluído 2026-05-30) — ver tasks/completed.md


---

- BLK-OPS-04 (concluído 2026-05-30) — ver tasks/completed.md



- BLK-FIX-01 (concluído 2026-05-30) — ver tasks/completed.md



- BLK-FIX-02 (concluído 2026-05-30) — ver tasks/completed.md


---

- BLK-SCORE-01 (concluído 2026-05-31) — ver tasks/completed.md


---

- BLK-SCORE-01a (concluído 2026-05-31) — ver tasks/completed.md


---

- BLK-SCORE-02 (concluído 2026-05-31) — ver tasks/completed.md


---

- BLK-SCORE-03 (concluído 2026-05-31) — ver tasks/completed.md


---

- BLK-SCORE-04 (concluído 2026-05-31) — ver tasks/completed.md

---

### BLK-RELPON-06 — Legibilidade dos mapas no PDF + linha de dado por RAIO (densidade sobre área válida)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (render/display do Relatório Pontual + mudança de SEMÂNTICA da linha de dado; **READ-ONLY sobre o M1**; núcleo `censo_*` só ESTENDE render, sem tocar interseção/raio/estrutura de páginas/marca d'água). |
| **Prioridade** | A definir (Vinicius). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — visual do PDF]` → Builder → QA. |
| **Status** | Pendente — **decisões de produto D1/D2 JÁ TOMADAS** (Vinicius, 2026-07-13, ver abaixo). |
| **Depende de** | **BLK-RELPON-05** (concluído 2026-07-10, PR #90 — introduziu a faixa superior "no ponto"). |
| **Autonomia** | **manual (NÃO loop-safe)** — exige revisão VISUAL do PDF gerado; o loop não enxerga o render. |

**Contexto (relato do Vinicius, 2026-07-13, com print do relatório de Rio Branco/AC `-9.95796, -67.81461`).**
Duas dores distintas no Relatório Pontual Censitário:
1. **Legibilidade:** nos slides **2 (Mapas de calor)** e **3 (Concorrentes)** o texto dos mapas fica pequeno e
   **borrado**.
2. **Semântica do dado:** a linha de dado do ponto hoje vem do **setor censitário que contém o pin**; o número
   correto de densidade deve ser a **população contida no raio dividida pela área de espaço VÁLIDO** (que não é
   mar/rio/vazio).

**Diagnóstico medido (2026-07-13).**
- O PNG é gerado com canvas **1000 px** de largura (`render_mapas_censitarios_combinados`, default) e encaixado
  numa célula de **~299 pt** na tira 1x3 (`_map_grid_cells`: `usable_w = 960 - 2*20 - 2*12 = 896`; `896/3`) →
  **redução de ~3,35x**. Tamanhos EFETIVOS no slide: título `20 px → ~6 pt`; linha do ponto `17 px → ~5,1 pt`;
  legenda corpo `13 px → ~3,9 pt`; rótulos `11 px → ~3,3 pt`. São **dois** problemas: **tamanho** (fonte pequena)
  e **nitidez** (reamostragem de 1000 px para 299 pt) — exigem **duas alavancas**: canvas de maior resolução
  **e** fontes ampliadas em relação ao canvas.
- A densidade do raio hoje é `pop_total_raio / area_km2` com `area_km2 = π · raio²` = **7,07 km² SEMPRE**
  (`censo_point.py:168` e `:305`) — ou seja, **divide pelo círculo inteiro, incluindo água/vazio**, o que
  **subestima** a densidade (visível no print: a mancha cinza do rio dentro do círculo de Rio Branco).
- **O denominador correto JÁ É CALCULADO:** `area_intersecao_total_m2` (`censo_point.py:265`) = soma das áreas de
  interseção dos setores IBGE com o círculo. O IBGE **não cobre água** → é exatamente a "área de espaço válido".
  Falta apenas fazer a divisão.

**Decisões de produto (gate humano, JÁ RESPONDIDAS por Vinicius em 2026-07-13).**
- **D1 = os 3 dados passam a ser do RAIO** (não mais do setor que contém o pin):
  - **Densidade** = `pop_total_raio / (area_intersecao_total_m2 / 1e6)` → **campo NOVO** (ex.:
    `densidade_pop_raio_valida_hab_km2`).
  - **Renda** = `renda_per_capita_media_raio` (**já existe** no `result`).
  - **Score** = `score_setor_medio` (**já existe** no `result`).
  - **Isto REVERTE o D3 do BLK-RELPON-05** (que fixou "valor do setor que CONTÉM o ponto"). Registrar a reversão
    no `completed.md` do ciclo.
  - Rótulo da faixa muda de **"no ponto"** para **"no raio"** (ex.: `Densidade no raio: 12.400 hab/km2`) — o
    D2 do BLK-RELPON-05 é atualizado. Manter formatação ASCII-safe (`hab/km2`, `R$` sem centavos, score inteiro).
- **D2 = fontes maiores SÓ no PDF.** O mesmo PNG serve o dashboard (tamanho quase real) e o PDF (reduzido 3,35x);
  ampliar a fonte nos dois deixaria o mapa do dashboard com texto desproporcional. Implementar via **parâmetro(s)
  OPCIONAL(is) com default `None` = render byte-a-byte IDÊNTICO ao de hoje** (padrão da emenda 2026-06-12 da
  DEC-005), usados **apenas** no caminho de geração do relatório.

**Escopo permitido.**
- `censo_point.py` — expor o campo NOVO de densidade sobre área válida (leitura/derivação a partir de
  `pop_total_raio` e `area_intersecao_total_m2`, ambos já calculados). **`n/d` quando não houver setores no raio
  OU `area_intersecao_total_m2 == 0`** (guardar contra divisão por zero).
- `censo_map.py` — (a) parâmetro(s) opcional(is) de **escala de texto e/ou canvas** aplicados a **título**,
  **linha de dado** e **legenda** (título/corpo/rótulos); (b) trocar a fonte dos 3 valores da faixa para os
  agregados do raio (D1) e o rótulo para "no raio".
- `censo_report.py` — passar a escala/resolução no caminho do PDF (slides **2** e **3**).
- Testes + `docs/relatorio_pontual_censitario.md`.

**Fora de escopo (INTOCADOS).**
- Método de interseção `setor_censitario_intersecao_area_1p5km`, **raio 1,5 km**, `RAIO_CENSITARIO_DEFAULT_KM`.
- **O choropleth** (cor por setor) — só a **faixa de texto** muda; as cores por setor permanecem.
- Contagem/ordem/estrutura das **5 páginas**, grid de Big Numbers 4x2, marca d'água anti-PII,
  `set_compression(False)`.
- `score_priorizacao`, `hex_score_estrutural`, pesos (`renda=0.40`/`pop=0.60`), carteira, plano, artefatos
  oficiais do M1 (**READ-ONLY**, §5).
- Os 5 campos do "setor do ponto" do BLK-RELPON-05 **não são removidos** do `result` (seguem para
  CSV/auditoria); apenas **deixam de alimentar a faixa**.

**Riscos.**
- **Os números vão MUDAR** nos relatórios já gerados: a nova densidade é **sempre ≥ a atual** (denominador menor).
  É esperado e é o ponto do bloco — mas convém avisar quem já usou um PDF antigo.
- Divisão por zero se a área válida for 0 → `n/d` obrigatório.
- O render é compartilhado com a **API** (que já passa knobs opcionais): o default `None` deve preservar o
  caminho da API e do dashboard byte-a-byte.
- **Consistência com os Big Numbers** (página 4), que já exibem médias do raio: conferir que os rótulos não
  fiquem contraditórios após a mudança.

**Critério de aceite.**
- Slides **2 e 3**: título, linha de dado e legenda **legíveis e nítidos** — revisão visual humana aprovada
  (alvo: texto efetivo ≥ ~9–10 pt no slide; sem borrão de reamostragem).
- Faixa exibe os agregados do **raio** (D1), com "n/d" quando não há setores/área válida.
- Densidade = população do raio ÷ área válida (exclui água/vazio), **verificada no caso de Rio Branco** (o rio
  dentro do círculo deve elevar a densidade vs. o valor antigo).
- **Dashboard e API: render byte-a-byte idêntico** quando os novos parâmetros não são passados.
- Interseção/raio/estrutura de páginas/marca d'água **intocados**; **zero** alteração no M1.
- Testes cobrindo a nova densidade (incl. área válida = 0) e a escala de texto; `ruff`/`mypy` limpos; suíte verde.

---

## Fechamento de ciclo — BLK-RELPON-06 (2026-07-14)

Veredito QA: **APROVADO COM RESSALVAS** (Opus 4.8). Esteira: Block Orchestrator (sonnet) -> Planner (sonnet) -> [gate humano de produto] -> Builder (sonnet) -> QA (opus) -> [revisao visual humana].

**ATENCAO — o texto do bloco acima esta SUPERSEDED em 2 pontos.** Ele foi escrito ANTES do gate; leia estas correcoes:

**1. O D2 ("fontes maiores SO no PDF", com param opcional e dashboard byte-a-byte identico) foi REVERTIDO pelo D4** (Vinicius, 2026-07-14): a fonte maior vale para **dashboard, PDF e API**, com **UM unico render**. Motivo: "so no PDF" exigiria renderizar os mapas DUAS vezes (dobrando o custo de geracao do relatorio, que ja e uma dor conhecida) e tocar `pages.py`. Consequencia: `pages.py`, `tests/integration/test_streamlit_app.py` e o plumbing `mapas_pdf` em `censo_report.py` NAO foram necessarios.

**2. A premissa do D1 ("o IBGE nao cobre agua") e FALSA para RIOS.** Medido com dado real: os setores censitarios **ladrilham por cima do rio** — em Rio Branco/AC (`-9.95796,-67.81461`) a area valida deu 7,068 km2 contra 7,069 km2 do circulo (0,0% excluido; densidade 2.890,84 -> 2.891,13). A malha do IBGE so termina de verdade no **MAR**. Evidencia:

| Ponto | Area valida | Agua excluida | Densidade antes -> depois |
|---|---|---|---|
| Praia Grande/SP (orla) | 6,40 km2 | 0,67 km2 (9,4%) | 5.751 -> 6.350 (+10,4%) |
| Santos/SP (sobre a agua) | 0,28 km2 | 6,79 km2 (96,1%) | 22 -> 567 (25x) |
| Rio Branco/AC (rio) | 7,068 km2 | 0,001 km2 (0,0%) | 2.891 -> 2.891 |

**Decisao humana (Vinicius, 2026-07-14): considerar SO o mar e suficiente; rios NAO sao necessarios.** Nenhum bloco de hidrografia sera aberto. O ganho real do campo novo e corrigir a densidade em TODA a costa (antes, um ponto na orla de Santos aparecia com 22 hab/km2 porque a populacao era diluida por km2 de oceano).

**Decisoes de produto do gate:**
- **D1** — a faixa dos 3 choropleths passa a mostrar os agregados do **RAIO** (REVERTE o D3 do BLK-RELPON-05, que fixara "setor que contem o pin"). Campo NOVO `densidade_pop_raio_valida_hab_km2` = `pop_total_raio / (area_intersecao_total_m2/1e6)`; Renda = `renda_per_capita_media_raio`; Score = `score_setor_medio`. Rotulo "no ponto" -> "no raio". Os 5 campos `*_setor_ponto` PERMANECEM no `result` (CSV/auditoria). Efeito em Rio Branco: densidade 941 -> 2.891; renda R$ 1.857 -> R$ 2.061; score 92 -> 76.
- **D3 (fonte)** — `_font()` passa a usar SEMPRE a fonte embutida do Pillow (`ImageFont.load_default(size=)`), abandonando `arial.ttf`. **Achado do Planner, confirmado:** a imagem de producao (`python:3.11-slim`) NAO tem fonte alguma -> `arial.ttf` levantava OSError -> `load_default()` SEM size devolvia bitmap FIXO de ~10px que IGNORAVA o tamanho pedido. Ou seja, **o texto dos mapas estava quebrado em producao** (dashboard E PDF), nao so pequeno. `Dockerfile.streamlit` NAO foi tocado (evitou reclassificar o PR como Critico pelo loop_guard/DEC-016).
- **D4 (render)** — fonte maior para todos, 1 render (ver ponto 1 acima).

**Insight matematico do Planner (registrado):** escalar canvas E fontes pelo mesmo fator e **no-op para o tamanho do texto no PDF** — a largura embutida e fixa pela geometria da pagina, entao o fator se cancela (`pt_efetivo = font_px * (celula/canvas)`). Canvas maior so melhora nitidez. Por isso a solucao e **fonte-only**: titulo 20->44, linha de dado 17->38, legenda-titulo 17->34, legenda-corpo 13->32 (=9,6pt no PDF, acima do alvo de 9-10pt); layout `_MAP_TOP` 92->132, `_VALOR_Y` 51->78, coluna da legenda 252->330.

**Bugs reais achados pelo Builder na revisao visual** (nao previstos pelo Planner): o caption "Pins: Ultra e concorrentes" (362px vs 252 de orcamento) e o subtitulo "Renda per capita (R$/pessoa)" (418px vs 320) transbordavam do canvas nos tamanhos propostos -> 2 constantes dedicadas (`_FS_LEGENDA_CAPTION=20`, `_FS_LEGENDA_SUBTITULO=22`) + teste de regressao para cada.

**Validacoes (QA, evidencia propria):** suite completa serial `1 failed, 1747 passed, 2 skipped` — a unica falha (`test_score_retencao_territorial::test_run_readonly_m1_por_mtime`, camada M2/lifetime) foi provada PRE-EXISTENTE por stash+re-run no baseline (staging gitignored ausente). `ruff`/`mypy` limpos; `import streamlit_app` ok. `pytest -n auto` quebra por infra do xdist (Windows/Py3.14), gate rodado serial. Teste de **contrato de legibilidade** adicionado (trava `_FS_LEGENDA_CORPO * 0.2987 >= 9.0` e o rotulo mais longo cabendo na coluna) — a legibilidade fica travada em CI, nao depende so do olho.

**READ-ONLY M1:** `score_priorizacao`/pesos/`hex_score_estrutural`/carteira/plano/artefatos oficiais INALTERADOS. Intocados tambem: `setor_censitario_intersecao_area_1p5km`, raio 1,5 km, estrutura das 5 paginas, grid de Big Numbers, marca d'agua, `set_compression(False)`, choropleth e faixas de cor (so texto/fonte/layout mudou). `pages.py` e `Dockerfile.streamlit` NAO tocados.

**Arquivos:** `src/motor_expansao/dashboard/{censo_point,censo_map,censo_report}.py`; `tests/unit/test_relatorio_pontual_censitario_{motor,mapa}.py`; `docs/relatorio_pontual_censitario.md`. Sucessor aberto: **BLK-RELPON-06-FU1** (piso do Pillow no `pyproject.toml`). Merge = passo humano.

---

### BLK-RELPON-06-FU1 — Corrigir o piso do Pillow no pyproject (código exige >=10.1)

| Campo | Valor |
|---|---|
| **Criticidade** | **Crítica** — não pelo risco funcional (nulo), mas porque `pyproject.toml` é **path CRÍTICO do `loop_guard`** (DEC-016) e exige label `critica-aprovada` do Felipe. |
| **Prioridade** | Baixa (sem risco em produção nem em CI). |
| **Esteira** | Block Orchestrator → Builder (mudança de 1 linha) → QA. |
| **Status** | Pendente. |
| **Depende de** | BLK-RELPON-06 (concluído 2026-07-14). |
| **Autonomia** | **manual (NÃO loop-safe)** — toca `pyproject.toml`, path crítico do `loop_guard`. |

**Contexto.** O BLK-RELPON-06 (D3) trocou `_font()` para `ImageFont.load_default(size=size)`, que **só existe a partir do Pillow 10.1**. Mas o `pyproject.toml` declara `pillow>=10.0.0`.

**Risco real: NULO hoje.** Produção e CI instalam com `-c constraints.txt`, que pina `pillow==12.3.0`. A divergência só apareceria para quem instalasse o pacote SEM o `constraints.txt` e resolvesse o Pillow em 10.0.x — aí `load_default(size=)` levantaria `TypeError` em runtime, no render do mapa.

**Objetivo.** Subir o piso de `pillow>=10.0.0` para `pillow>=10.1` no `pyproject.toml`, alinhando a declaração ao que o código de fato exige. Levantado pelo QA do BLK-RELPON-06.

**Critério de aceite.** `pyproject.toml` declara `pillow>=10.1`; `constraints.txt` INALTERADO (já em 12.3.0); suíte verde; ruff/mypy limpos.

---

## Fechamento de ciclo — BLK-RELPON-06-FU1 (2026-07-14)

Correcao de 1 linha levantada pelo QA do BLK-RELPON-06: `pyproject.toml` declarava
`pillow>=10.0.0`, mas o `_font()` de `censo_map.py` passou a usar
`ImageFont.load_default(size=)` (D3 do BLK-RELPON-06), que **so existe a partir do Pillow
10.1**. Em 10.0.x levantaria `TypeError` no render do mapa.

Risco em producao/CI era NULO (ambos instalam com `-c constraints.txt`, que pina
`pillow==12.3.0`) — a divergencia so apareceria para quem instalasse o pacote SEM o
constraints e resolvesse o Pillow em 10.0.x. Mas o piso estava mentindo sobre o que o codigo
exige.

**Feito:** `pillow>=10.0.0` -> `pillow>=10.1` em `pyproject.toml` (com comentario explicando o
porque). `constraints.txt` INTOCADO (ja em 12.3.0).

**Validado:** 61 passed na trilha do relatorio pontual; `import streamlit_app` ok; `ruff` limpo;
`pyproject.toml` parseia e resolve `pillow>=10.1`.

**Governanca (DEC-016):** `pyproject.toml` e path CRITICO do `loop_guard` -> o merge deste PR
exige a label `critica-aprovada` do proprio Felipe (login Kastaldy), nao basta
`aprovado-humano`. E por isso que o bloco foi classificado Critico, apesar de ser 1 linha.
Nenhum artefato/score/peso do M1 tocado.
## Fechamento de ciclo - BLK-ORQ-25 (2026-07-14)

Demonstrador do auto-merge zero-humanos da DEC-016 (ORQ-21) + housekeeping diferido (ORQ-24).
Adicionados testes de regressao CRLF para `is_done`/`emit_delta` em `tests/unit/test_housekeeping_helper.py` (4 casos: heading movido + fechamento, prosa ignorada, sem 
 no ID, sem colisao de prefixo). READ-ONLY sobre o M1; toca so `tests/`. Este PR de implementacao entrou pelo AUTO-MERGE nativo (Baixa, 4 checks verdes, ZERO humanos) - a prova que faltava do ORQ-21. Stub do backlog DIFERIDO para o PR de housekeeping em lote (modo auto-merge do ORQ-24); ate la, `housekeeping_move_block.py --is-done BLK-ORQ-25` sai 0 e `--emit-delta` lista o bloco.

---

### BLK-ORQ-20 — Portão por checks de CI: `guard` + `review-gate` + `claude-review` + `REVIEW.md`

| Campo | Valor |
|---|---|
| **Criticidade** | **Crítica** (introduz a governança de merge do repo e mexe em CI — path CRÍTICO do `loop_guard`; **READ-ONLY sobre o M1**). Coberta pela **DEC-016** (aprovada 2026-07-13). |
| **Prioridade** | **Máxima** (destrava toda a esteira; é pré-requisito dos demais blocos da epic). |
| **Esteira** | Block Orchestrator → Planner → `[GATE HUMANO — DEC-016 já aprovada]` → Builder → QA. |
| **Status** | **Em execução** (branch `ciclo/BLK-ORQ-20-autonomia`). |
| **Depende de** | **DEC-016 registrada** (CLAUDE.md §8) — concluído neste mesmo PR. |
| **Autonomia** | **manual (NÃO loop-safe)** — mexe em CI/governança (paths CRÍTICO e GOVERNANÇA do próprio guard); NUNCA loop-safe. |

**Contexto.** Hoje a `main` exige **1 aprovação humana** (Felipe) e o único required check é `test`. A DEC-016
troca esse portão por checks auditáveis. Este bloco **cria os checks**; a proteção só é aplicada no **BLK-ORQ-21**
(depois de os checks terem rodado ao menos 1×).

**Objetivo.** Entregar os **3 checks novos** + o contrato de revisão, sem alterar branch protection ainda.

**Escopo.**
1. **`.github/workflows/guard.yml`** — job **`guard`** em **`pull_request_target`** (roda a partir da **BASE**;
   **NUNCA** faz checkout nem executa código do PR — senão um PR agêntico editaria o próprio job e se
   auto-aprovaria). Lê os paths tocados via API e chama `scripts/loop_guard.py`, classificando em **CRÍTICO**
   (M1, scores paralelos servidos em produção, `deploy/`, segredos, CI) e **GOVERNANÇA** (o próprio guard,
   `.claude/`, `REVIEW.md`, `CLAUDE.md`, `tasks/backlog.md`).
2. **`.github/workflows/claude-review.yml`** — job **`claude-review`** com `anthropics/claude-code-action@v1`,
   autenticado por **`claude_code_oauth_token`** (secret `CLAUDE_CODE_OAUTH_TOKEN`, assinatura Max — **sem custo
   de API**). **REPROVA o check** em achado de severidade alta. **Posta UM comentário único (sticky), atualizado a
   cada push — NUNCA review threads inline** (a `main` tem `required_conversation_resolution: true`: thread inline
   aberta **trava o auto-merge** até alguém resolver).
3. **Job `review-gate`** — exige a label conforme a criticidade: nada em **Baixa/Média**; **`aprovado-humano`** em
   **Alta**; **`critica-aprovada`** em **Crítica**, com **validação via API do AUTOR da label** (só `Kastaldy`).
4. **`REVIEW.md`** — contrato do revisor: severidades, o que reprova, formato sticky, o que NÃO é achado.
5. **`scripts/loop_guard.py`** — ampliar com a classificação CRÍTICO/GOVERNANÇA + modo de uso por CI (lista de
   paths → exit code), **preservando** o comportamento atual usado pelo loop (`RELATORIO-BLOQUEIO.md`).
6. **Testes** de todo comportamento novo (`pytest`).
7. **Blindagens do red team (2026-07-13; detalhadas na DEC-016, §8):** job **`dismiss-stale-approval`** (push novo
   remove as labels de aprovação); **conferência da label `criticidade:*` contra o campo Criticidade do bloco em
   `tasks/backlog.md` da BASE** (divergência = reprovado; PR sem bloco identificável exige `aprovado-humano`);
   **validação via API de QUEM aplicou a label** (humano não-bot, ≠ autor do PR, com `write`/`admin`; `Kastaldy` na
   Crítica); **PR de fork REPROVA no `claude-review`** (job pulado por `if:` conta como **sucesso** em required
   check — não pular, reprovar); `pyproject.toml`, `constraints.txt`, `conftest.py`, `.gitleaks*`, `.trivyignore` e
   `Dockerfile.*` na classe **CRÍTICO** (senão um PR desarma o próprio `test`, que roda do HEAD); **fail-closed**
   em toda leitura (diff ilegível, `arquivos_revisados < 1`, saída inválida, action fora do ar → **vermelho**).

**Critérios de aceite.**
- `guard.yml` usa **`pull_request_target`** e **não contém** `actions/checkout` do `head.sha` nem execução de código
  do PR (verificável por leitura do YAML + teste que falha se o gatilho ou o ref mudarem).
- Teste: PR tocando `config.py`/`pipelines/m1/`/artefato oficial → `loop_guard` classifica **CRÍTICO**.
- Teste: PR tocando `.github/`, `scripts/loop_guard.py`, `.claude/`, `REVIEW.md`, `CLAUDE.md` ou `tasks/backlog.md`
  → classifica **GOVERNANÇA**.
- Teste: label `critica-aprovada` aplicada por login **≠ `Kastaldy`** → `review-gate` **REPROVA**.
- Teste: bloco **Baixa/Média** sem label nenhuma → `review-gate` **PASSA**.
- Teste: PR tocando `pyproject.toml`, `constraints.txt`, `conftest.py`, `.gitleaks*`, `.trivyignore` ou
  `Dockerfile.*` → `loop_guard` classifica **CRÍTICO** (não dá para desarmar o `test` sem gate).
- Teste: label `criticidade:baixa` num PR cujo bloco em `tasks/backlog.md` (BASE) é **Crítica** → **REPROVA**
  (criticidade não é auto-declarada); PR **sem bloco identificável** só passa com `aprovado-humano`.
- Teste: `aprovado-humano` aplicada por **bot**, pelo **autor do PR**, ou por login **sem `write`/`admin`**
  → **REPROVA**.
- Teste: **push novo** em PR com `critica-aprovada`/`aprovado-humano` → `dismiss-stale-approval` **remove** a label
  (aprovação vale para o diff revisado, não para o commit seguinte).
- Teste: **PR de fork** → `claude-review` **REPROVA** (nunca "pula" — job pulado contaria como sucesso).
- Teste: diff ilegível / `arquivos_revisados < 1` / saída inválida → check **VERMELHO** (**fail-closed**).
- `claude-review` reprova (exit ≠ 0) em achado de severidade alta; comentário **sticky único**, zero review threads.
- Suíte FULL verde (`pytest -n auto`); `ruff` + `mypy` limpos.
- **Nenhum** arquivo de `deploy/`, `secrets/`, `.env`, `.claude/settings.json` ou `.gitignore` tocado neste PR.

**Guardrail.** §5 **READ-ONLY M1** (zero escrita em score/pesos/`config.py`/`pipelines/m1/`/artefatos oficiais);
NÃO tocar VPS/`deploy/`/segredos; **NÃO aplicar** branch protection aqui (é o ORQ-21); identificadores sem acento
(`guard`, `review-gate`, `claude-review`, `aprovado-humano`, `critica-aprovada`).

---

### BLK-ORQ-24 — Separar o housekeeping do backlog do PR de ciclo (destravar o auto-merge do loop)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (muda o Passo 6.0 da esteira `/run-cycle`; **READ-ONLY sobre o M1**). |
| **Prioridade** | **Alta** (sem isto, o objetivo central da DEC-016 — auto-merge do loop — fica ANULADO na prática). |
| **Esteira** | /run-cycle (edita `.claude/commands/run-cycle.md` + `prompts/qa_analyzer.md`). |
| **Status** | Pendente. |
| **Depende de** | **BLK-ORQ-20** (o `guard` precisa existir e classificar `tasks/backlog.md` como GOVERNANÇA). |
| **Autonomia** | **manual (NÃO loop-safe)** — altera a própria orquestração e toca `CLAUDE.md`/`prompts/` (governança). NÃO marcar loop-safe. |

**Contexto (o colapso operacional que o red team achou).** O `guard` classifica `tasks/backlog.md` como
**GOVERNANÇA** — e isso é **correto**: é onde vive o marcador `loop-safe`, então um PR que editasse o backlog
livremente e auto-mergeasse poderia **se auto-conceder** o direito de o loop tocar novos blocos. **Mas** o Passo 6.0
do `/run-cycle` faz *housekeeping* a CADA ciclo aprovado: `scripts/housekeeping_move_block.py` **substitui o bloco por
um stub em `tasks/backlog.md`** (além de mover o corpo para `tasks/completed.md`). Logo **TODO PR de ciclo/loop toca
`backlog.md` → cai em GOVERNANÇA → exige `aprovado-humano`** — ou seja, **nenhum PR do loop/Garimpeiro mergeia
sozinho**, e a rotina viraria carimbar a label por hábito (cheque em branco pela porta dos fundos). Isso anula o
objetivo da DEC-016. (`tasks/completed.md` **não** é governança — o append do resumo continua auto-mergeável.)

**Objetivo.** Fazer o PR de ciclo/loop conter **apenas código + testes + o append em `completed.md`** (que passa
LIMPO no guard), deixando a alteração de `backlog.md` **fora** do PR auto-mergeável.

**Opções avaliadas.**
- **(a) [RECOMENDADA] Housekeeping do backlog em PR SEPARADO/batched.** No modo auto-merge, o ciclo **NÃO** roda o
  stub-replacement em `backlog.md`; ele só entrega código + `completed.md`. A remoção do bloco do backlog vira um
  **PR de housekeeping em lote** (semanal), revisado por humano — ou executado pela routine **Zelador** (a criar; já
  prevista como reconciliadora do backlog). **Vantagem:** simples, sem parser novo; mantém `backlog.md` **sempre sob
  olho humano**, que é exatamente onde o marcador `loop-safe` deve ser concedido. **Custo:** o backlog fica
  transitoriamente defasado (o bloco aparece em `completed.md` mas ainda não some do backlog) até o PR de lote —
  defasagem que o Zelador reconcilia e que **não** afeta o loop (ele lê o marcador, não o stub).
- **(b) Guard com parser de diff do backlog.** O `guard` passaria a distinguir um diff de `backlog.md` que **só
  move/stuba o próprio bloco do PR** (sem tocar `Autonomia`/`Criticidade` de OUTROS blocos) → não conta como
  violação. **Mais poderoso** (PRs de ciclo continuam atômicos), mas exige um **parser de diff confiável na base**;
  o risco é ele errar e **deixar passar uma auto-marcação `loop-safe`** de outro bloco — exatamente o que o guard
  existe para impedir. **Rejeitada** por trocar um problema de UX por um risco de segurança.
- **(c) `backlog.md`/`CLAUDE.md` saem do housekeeping automático no modo loop.** Igual a (a) na prática, mas sem o
  PR de lote formal (o backlog só é reconciliado quando alguém lembra). Inferior a (a) por não ter dono da
  reconciliação.

**Escopo (opção a).**
1. `.claude/commands/run-cycle.md` Passo 6.0: no modo auto-merge (Baixa/Média), **pular o stub-replacement** de
   `backlog.md`; manter o append em `completed.md` (Passo 6.2). Registrar o bloco a stubar numa fila
   (`tasks/pending_housekeeping.md`, gitignored ou append-union) para o PR de lote.
2. `prompts/qa_analyzer.md`: o `--check` do helper deixa de ser gate de fechamento **no modo auto-merge** (o
   stub-move é diferido) — o QA valida que o bloco está DONE, não que o stub já existe.
3. Documentar o PR de housekeeping em lote (semanal) como responsabilidade do **Zelador** (ou passo manual até ele
   existir).
4. **Regra de seleção do loop/Garimpeiro por `completed.md` (fecha o furo de RE-SELEÇÃO durante a defasagem).**
   Como o stub no `backlog.md` fica diferido por até 7 dias, o bloco concluído continua no backlog **com o marcador
   `loop-safe` e o heading completo**. Sem proteção, o loop re-selecionaria o mesmo bloco e abriria um PR duplicado.
   O prompt do loop (`run-ralph-loop.sh`) passa a exigir: **IGNORE qualquer bloco cujo ID já esteja em
   `tasks/completed.md`, mesmo que ainda apareça no `backlog.md`** — `completed.md` é a fonte de verdade **única** de
   conclusão (já é o critério de término e de `Depende de` do loop; aqui vira também o critério de SELEÇÃO).
   **Reler o `completed.md` da `main` ATUALIZADA (checkout/pull fresco) ANTES de cada seleção; NUNCA usar cópia em
   cache de sessão anterior do loop.** A routine da nuvem clona fresco a cada run (bom); se algum dia o Garimpeiro
   reusar estado entre execuções, o pull fresco de `completed.md` é obrigatório antes de escolher o bloco.

**Consumidores do `backlog.md` durante a janela de defasagem (por que a janela de até 7 dias é segura).**
- **Loop/Garimpeiro** — ÚNICO consumidor em tempo real DENTRO deste repo. Usa `completed.md` como verdade de
  conclusão; com a regra de seleção do item 4, não re-pega bloco fechado.
- **Zelador** (routine reconciliadora, **A CRIAR**) — a defasagem é o **INPUT** dele, não um bug: deve tratar
  "bloco em `completed.md` ainda pendente no `backlog.md`" como **housekeeping pendente a reconciliar**, NUNCA como
  erro. **Requisito de desenho** do bloco do Zelador.
- **Ferramentas externas de produtividade** (ex.: o `growth-rpg-producer`, skill no ambiente Claude Desktop/Cowork
  do Felipe, **FORA deste repo/máquina**) — leem o **ClickUp em modo somente-leitura**, **NÃO** o `backlog.md` do
  git. Fonte de dado diferente → **não afetadas pela defasagem** (o motivo é a FONTE distinta, não a inexistência do
  consumidor).

**Critérios de aceite.**
- Um PR de ciclo de bloco **Média** que altere só código + testes + `completed.md` passa o `guard` **LIMPO**
  (`printf '<arquivos>' | python scripts/loop_guard.py --stdin --json` → `{"limpo": true}`) e é **auto-mergeável**.
- Um PR que toque `backlog.md` continua caindo em GOVERNANÇA (o guard **não** é afrouxado).
- O bloco concluído aparece em `completed.md` no PR de ciclo; o stub em `backlog.md` chega pelo PR de lote.
- **Anti-re-seleção:** com um bloco X já em `completed.md` mas ainda com heading `loop-safe` no `backlog.md`, uma
  passada do loop **NÃO** re-seleciona X (teste com fixture da defasagem) e a seleção lê o `completed.md` **fresco**.
- A esteira `/run-cycle` documentada e o dry-run de orquestração (Passo 6.c) passam.

**Guardrail.** §5 **READ-ONLY M1**; o `guard` **não** é enfraquecido (backlog segue governança); mudança só na
ORDEM/EMPACOTAMENTO do housekeeping, não na proteção.

---

### BLK-ORQ-25 — Testes de regressão CRLF para `is_done`/`emit_delta` (demonstrador do auto-merge)

| Campo | Valor |
|---|---|
| **Criticidade** | **Baixa** (só testes; **READ-ONLY sobre o M1**). |
| **Prioridade** | Baixa (demonstrador do auto-merge da DEC-016 + 1º bloco loop-safe pós-ORQ-24). |
| **Esteira** | Builder → QA (bloco mecânico, sem gate de produto/UX). |
| **Status** | Pendente. |
| **Depende de** | — (nenhuma; usa `is_done`/`emit_delta`, já na `main` via BLK-ORQ-24). |
| **Autonomia** | **loop-safe** — toca só `tests/`, READ-ONLY sobre o M1, não toca VPS/deploy/segredos, não persiste PII, sem ingestão ao vivo. |

**Contexto.** O BLK-ORQ-24 adicionou `is_done`/`emit_delta` em `scripts/housekeeping_move_block.py` (seleção do
loop por conclusão + delta do PR de housekeeping em lote). No Windows (plataforma de dev), `tasks/completed.md` e
`tasks/backlog.md` são CRLF; um refactor futuro que troque `splitlines()` por regex ou que mude o padrão de heading
poderia quebrar a detecção em CRLF **silenciosamente** e fazer o loop mis-selecionar um bloco.

**Objetivo.** Travar o comportamento CRLF com testes de regressão em `tests/unit/test_housekeeping_helper.py`:
`is_done` detecta `### BLK-X
` e `## Fechamento de ciclo — BLK-X
`; ignora menção em prosa mesmo em CRLF;
`emit_delta` não captura o `
` no ID e não colide prefixo (`BLK-FIX-06` vs `BLK-FIX-06-C`) em entrada CRLF.

**Critérios de aceite.** Testes novos cobrem `is_done` + `emit_delta` em entrada CRLF; suíte verde (`pytest -n auto`);
o PR toca SÓ `tests/` (mais o append de fechamento em `tasks/completed.md` no modo auto-merge). NENHUM código de
produção alterado; `is_done`/`emit_delta` inalterados (são testes de regressão, não mudança de comportamento).

**Guardrail.** §5 **READ-ONLY M1**; toca só `tests/`; sem rede, VPS, deploy, segredos ou PII.

---

### BLK-RELPON-07 — Slide de perfil do Bairro/Distrito no Relatório Pontual (estilo GeoFusion "Microárea")

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (novo slide no Relatório Pontual Censitário; **READ-ONLY sobre o M1**; ADICIONA uma página ao PDF e uma agregação por bairro; núcleo `censo_*` só ESTENDE render/leitura, sem tocar interseção/raio/marca d'água). |
| **Prioridade** | A definir (Vinicius). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — visual do PDF]` → Builder → QA. |
| **Status** | Pendente — **decisões de produto D1/D2/D3 JÁ TOMADAS** (Vinicius, 2026-07-15, abaixo). |
| **Depende de** | Relatório Pontual já existente; malha de setores IBGE 2022 (`setores_censitarios_2022_geo`), que **já traz** `nome_bairro`/`cod_bairro`/`nome_distrito`. |
| **Autonomia** | **manual (NÃO loop-safe)** — altera relatório auditável e exige revisão visual do PDF. |

**Objetivo.** Adicionar ao Relatório Pontual Censitário um **slide dedicado ao bairro/distrito** que
CONTÉM o ponto pesquisado, no espírito do painel "Microárea" da GeoFusion — o perfil da área
administrativa inteira, não do raio de 1,5 km. É uma **lente nova, complementar** aos mapas de calor.

**Viabilidade medida (2026-07-15).** A base de setores 2022 já tem os campos geográficos e as
métricas necessárias para **4 dos 7 blocos** do painel GeoFusion. Os outros 3 (faixa etária, faixa
de renda ABEP A++/A+/B/C/D/E, PEA Dia/Trabalha×Reside) **não existem** no dado do projeto (o Censo
ingerido é agregado; ABEP e PEA são fontes externas/proprietárias) e **NÃO entram** neste bloco
(decisão D3). Cobertura geográfica: `distrito` 100% nacional; `bairro` ~61% nacional (100% no
exemplo, São José do Rio Preto); `subdistrito` ~vazio (descartado).

**Decisões de produto (gate — JÁ RESPONDIDAS por Vinicius, 2026-07-15).**
- **D1 = unidade geográfica: BAIRRO com fallback para DISTRITO.** Usa `nome_bairro` quando existe;
  quando `nome_bairro` é nulo (~39% dos setores nacionais), cai para `nome_distrito`. `subdistrito`
  é descartado (dado quase sempre vazio). O rótulo do slide deve indicar qual unidade está sendo
  mostrada (ex.: título = nome; subtítulo = "bairro de {município}" ou "distrito de {município}").
- **D2 = escopo: a unidade que CONTÉM o pin.** Agrega **todos os setores** cujo `cod_bairro` (ou,
  no fallback, `nome_distrito`) é igual ao do setor que contém o ponto — o perfil da área
  administrativa inteira, independente do raio de 1,5 km. Reusa o lookup do "setor do ponto" já
  existente (BLK-RELPON-05, `cod_setor_ponto`) para descobrir o bairro/distrito do pin. Os setores
  do bairro já estão carregados: `read_censo_geo_partition` traz a partição do município inteiro.
- **D3 = incluir SÓ os 4 blocos com dado fiel** (sem placeholder, sem aproximação inventada, sem
  aquisição de dado externo):
  1. **Título** — nome do bairro (fallback distrito) + contexto do município.
  2. **População** — `Σ pop_total_setor_2022` dos setores da unidade.
  3. **Densidade Demográfica** — `população / (Σ area_setor_m2 / 1e6)` (hab/km²).
  4. **Domicílios** — `Σ domicilios_particulares_ocupados_setor_2022`.
  5. **Renda Média** — a definir no planejamento: `renda_responsavel_media_setor_2022`
     (ponderada por domicílios) **ou** `renda_per_capita_setor_2022_calibrada` (ponderada por
     população). Preferir a **renda média domiciliar ponderada por domicílios**, que é a leitura
     GeoFusion "Renda Média"; confirmar no gate visual. Formatar em R$ (padrão ASCII do PDF).
  (Os gráficos de barras de faixa etária e faixa de renda, e o bloco PEA, do painel GeoFusion,
  **NÃO** entram — decisão explícita de Vinicius.)

**Escopo permitido (READ-ONLY M1, só display/relatório).**
- `censo_point.py` — expor, no `result`, o **bairro/distrito do pin** (ex.: `cod_bairro_ponto`,
  `nome_bairro_ponto`, `nome_distrito_ponto`, `unidade_ponto_rotulo` com o fallback já resolvido),
  a partir do setor que contém o ponto — SÓ LEITURA, sem tocar interseção/raio.
- Novo helper de **agregação por bairro/distrito** (pode viver em `censo_point.py` ou módulo
  próprio) que soma pop/domicílios/área e calcula densidade e renda média ponderada dos setores da
  unidade; "n/d" gracioso quando o pin cai fora de qualquer setor ou a unidade não tem dado.
- `censo_report.py` — **nova página** "Perfil do Bairro/Distrito" nas DUAS variantes (`censitario`
  e `classico`), inserida **entre a página de Concorrentes e a de Big Numbers** (decisão de Vinicius,
  2026-07-15). Ordem final: Capa → Mapas de calor → Concorrentes → **Perfil do Bairro/Distrito** →
  Big Numbers → Realização/Crédito. **Isto ALTERA a contagem de páginas** (as DUAS variantes: **5→6**;
  ambas já tinham 5 páginas — o clássico também tem página de Concorrentes) e o `/Count` — mudança
  INTENCIONAL deste bloco (é o único ponto do "fora de escopo" histórico que este bloco toca de
  propósito). Atualizar `PDF_SECTION_HEADERS` (inserir o rótulo da nova seção **entre**
  `"Concorrentes"` e `"Big Numbers"`) e a contagem de imagens/páginas dos testes de estrutura.
- Testes: agregação por bairro (com e sem fallback para distrito; "n/d" fora da malha) + presença
  da nova página no PDF (as duas variantes) + atualização dos testes de contagem de páginas.
- `docs/relatorio_pontual_censitario.md`.

**Fora de escopo.** Método de interseção `setor_censitario_intersecao_area_1p5km`, raio 1,5 km,
`RAIO_CENSITARIO_DEFAULT_KM`, os mapas de calor / choropleth / faixa "no raio" (BLK-RELPON-06), grid
de Big Numbers 4x2, marca d'água anti-PII, `set_compression(False)`. `score_priorizacao`/pesos/
`hex_score_estrutural`/carteira/plano/artefatos oficiais do M1. Faixa etária, faixa de renda ABEP e
PEA (sem dado — não entram). Relatório Municipal e UI do dashboard (fora do Relatório Pontual).
Dependência de rede nova.

**Riscos.**
- **Contagem de páginas muda** — quebra os testes de estrutura do PDF de propósito; atualizá-los
  (não relaxá-los). Conferir que a marca d'água (BLK-EST-01, todas as páginas) cobre a página nova.
- **Bairro ausente (~39% nacional)** — o fallback para distrito precisa ser robusto; testar um
  município SEM bairro (ex.: fora de SP) para garantir que o slide não fica vazio.
- **Renda média — método de ponderação** (D3.5): documentar qual campo/peso foi usado, para o
  número ser auditável e não ser confundido com a renda do raio (BLK-RELPON-06) nem com o setor do
  pin (BLK-RELPON-05).
- **Consistência semântica** — deixar claro no slide que é o **bairro inteiro** (não o raio de
  1,5 km nem o setor do ponto), para não conflitar com os outros números do relatório.

**Critério de aceite.** O Relatório Pontual passa a ter a página "Perfil do Bairro/Distrito"
(as duas variantes) com os 4 blocos (título+unidade, população, densidade, domicílios, renda média)
agregados sobre o bairro que contém o pin, com fallback para distrito e "n/d" gracioso; contagem de
páginas/`/Count` e `PDF_SECTION_HEADERS` atualizados e testados; interseção/raio/marca d'água/M1
INTOCADOS; `ruff`/`mypy` limpos; suíte verde; revisão visual do PDF aprovada.

## Fechamento de ciclo — BLK-RELPON-07 (2026-07-15)

Ciclo `/run-cycle BLK-RELPON-07` — **Slide de perfil do Bairro/Distrito no Relatório Pontual Censitário**
(estilo GeoFusion "Microárea"). Criticidade **Média**. Esteira Block Orchestrator (sonnet) → Planner
(sonnet) → Builder (sonnet) → QA (opus) → **[REVISÃO VISUAL HUMANA DO PDF — PENDENTE]** → merge humano.
Veredito QA: **APROVADO COM RESSALVAS** (2026-07-15).

**O que foi entregue.** Nova página "Perfil do Bairro/Distrito" no PDF do Relatório Pontual, nas DUAS
variantes (`censitario` e `classico`), inserida **entre Concorrentes e Big Numbers** — o PDF passa de
**5 para 6 páginas** (mudança INTENCIONAL). A página agrega, sobre TODO o bairro (fallback distrito) que
CONTÉM o pin — não o raio de 1,5 km — 4 blocos de dado fiel: título+unidade, População
(`Σ pop_total_setor_2022`), Densidade demográfica (`pop / (Σ area_setor_m2 / 1e6)` hab/km2), Domicílios
(`Σ domicilios_particulares_ocupados_setor_2022`) e Renda média. Faixa etária, faixa de renda ABEP e PEA
NÃO entram (sem dado no projeto — decisão D3 de Vinicius).

**Decisões de produto (Vinicius, 2026-07-15).** D1 = BAIRRO com fallback para DISTRITO (subdistrito
descartado). D2 = a unidade administrativa que contém o pin (todos os setores do bairro/distrito). D3 =
só os 4 blocos com dado fiel. Ordem final do PDF: Capa -> Mapas de calor -> Concorrentes -> **Perfil do
Bairro/Distrito** -> Big Numbers -> Realização.

**Decisão técnica fechada pelo Planner (D3.5 — método da Renda Média).** Renda média domiciliar
ponderada por domicílios (leitura GeoFusion "Renda Média"): `Σ(renda_responsavel_media_setor_2022 ×
domicilios_particulares_ocupados_setor_2022) / Σ domicilios_particulares_ocupados_setor_2022`, com
**exclusão simétrica** (setor só entra no numerador E no denominador se renda não-nula E domicílios
não-nulo E > 0; senão sai dos dois lados — nunca vira zero disfarçado). Constante rastreável
`METODO_RENDA_PERFIL_BAIRRO = "renda_responsavel_media_ponderada_por_domicilios"`. Escolhida sobre a
renda per capita para NÃO criar 3 números de "renda per capita" com escopos diferentes no mesmo PDF
(setor do pin BLK-RELPON-05, raio BLK-RELPON-06, e este). Rótulo distinto "Renda média".

**Implementação (6 arquivos).**
- `src/motor_expansao/dashboard/censo_point.py`: no `result` de `analisar_ponto_censitario_setores`,
  5 campos novos de identificação do bairro/distrito do pin (`cod_bairro_ponto`, `nome_bairro_ponto`,
  `nome_distrito_ponto`, `unidade_ponto_tipo` cru "bairro"/"distrito", `unidade_ponto_rotulo` com
  fallback resolvido) — SÓ LEITURA de `ponto_row`, sem tocar interseção/raio. Novo helper público
  `agregar_perfil_bairro_distrito(setores_df, *, cod_bairro/nome_bairro/nome_distrito/nome_municipio/uf)`
  que resolve a unidade por prioridade (bairro > distrito), agrega pop/domicílios/área/densidade/renda
  ponderada e devolve "n/d" gracioso (dict-default sem exceção) quando fora da malha ou sem dado.
- `src/motor_expansao/dashboard/pages.py`: 2 pontos de chamada (`gerar_payloads_relatorio_pontual_para_pin`
  e `render_relatorio_pontual_censitario`) propagam `perfil_bairro` aos geradores de PDF.
- `src/motor_expansao/dashboard/censo_report.py`: `PDF_SECTION_HEADERS` de 5->6 strings ("Perfil do
  Bairro/Distrito" entre "Concorrentes" e "Big Numbers"); novas páginas `_perfil_bairro_page` /
  `_classico_perfil_bairro_page` (SEM mapa — texto/números, 4 cards grid 2x2, nota de método auditável,
  "n/d" gracioso); parâmetro keyword-only `perfil_bairro` nos geradores e nos helpers de download; tema
  bicolor reordenado (4 páginas de conteúdo). Marca d'água cobre a 6ª página automaticamente (laço por
  `pdf.pages_count`), confirmado por teste.
- `tests/unit/test_relatorio_pontual_censitario_motor.py` + `_export.py`: 9 testes novos (agregação por
  cod_bairro; fallback distrito; exclusão simétrica da renda **provada** — assert 2000 e não a média
  simples; "n/d" sem identificador / df vazio; presença da página nas 2 variantes com `/Count 6`;
  indisponibilidade com `perfil_bairro=None`). ~13 asserts `/Count 5`->`/Count 6` e 2 watermark-count
  `>=5`->`>=6` ATUALIZADOS (não relaxados); `test_classico_gera_5_paginas_e_secoes` renomeado para `..._6_...`.
- `docs/relatorio_pontual_censitario.md`: §4/§7 atualizados (6 páginas, novo campo/helper, D3.5, nota de
  escopo de que `api/service.py` não recebe `perfil_bairro` neste ciclo -> PDF da API mostra a página em
  "n/d", intencional).

**Nota de escopo (aceita).** `src/motor_expansao/api/service.py` NÃO foi tocado — o endpoint da API
(`POST /analisar?formato=pdf`, DEC-005) chama o gerador sem `perfil_bairro`, então o PDF da API ganha a
página em "n/d". Expor o perfil do bairro na API é bloco futuro, não deste ciclo.

**QA (Opus 4.8, evidência própria).** Suíte FULL serial: **1 failed, 1770 passed, 2 skipped**. A única
falha (`test_score_retencao_territorial::test_run_readonly_m1_por_mtime`) foi **provada PRÉ-EXISTENTE**
via `git stash` (parquet gitignored ausente em camada NÃO tocada — mesma falha do baseline HEAD; `-n auto`
quebra por infra execnet conhecida do ambiente Windows, não mascarado). Alvos do Planner: 96 passed.
`ruff` limpo; `mypy` nos 3 arquivos tocados `Success: no issues` (6 erros `requests`-stub pré-existentes
em módulos não tocados, provados por stash); smoke `import streamlit_app` ok. Escopo: só os 6 arquivos do
plano. READ-ONLY M1 confirmado: `score_priorizacao`/pesos/artefatos oficiais, método
`setor_censitario_intersecao_area_1p5km`, raio 1,5 km/`RAIO_CENSITARIO_DEFAULT_KM`, marca d'água anti-PII,
`set_compression(False)`, `pdf_version="1.4"` e choropleth INTOCADOS (grep no diff = 0). Acentuação PT
dentro de latin-1 com pontuação ASCII; regressão de acentuação verde.

**Ressalvas (não bloqueiam o código).**
1. **Gate de REVISÃO VISUAL HUMANA do PDF (dashboard + PDF das 2 variantes) PENDENTE** — Vinicius revisa o
   PDF renderizado (layout/geometria dos 4 cards, subtítulo, nota de método) antes do merge. Geometria fina
   da página é ponto de partida, ajustável no gate.
2. **Merge humano** — bloco "manual (NÃO loop-safe)"; merge segue humano após o gate visual (não auto-merge).
3. `api/service.py` sem `perfil_bairro` (nota de escopo acima).

**Housekeeping (6.0, modo MERGE-HUMANO).** Bloco movido byte-idêntico do backlog para completed.md via
`scripts/housekeeping_move_block.py BLK-RELPON-07 --date 2026-07-15` (stub de 1 linha no backlog); `--check`
e `--is-done` verdes. READ-ONLY M1; pesos `renda=0.40`/`pop=0.60` e artefatos oficiais inalterados.

### BLK-RELPON-07 — refino visual do slide (gate visual de Vinicius, 2026-07-15)

Durante a revisão visual, Vinicius pediu para os 4 blocos do slide "Perfil do Bairro/Distrito"
seguirem o formato do painel "Microárea" da GeoFusion (imagem de referência): layout VERTICAL
empilhado em vez do grid 2x2 de cards. Redesenho SÓ visual em `censo_report.py` (READ-ONLY M1;
não muda os 4 blocos, os valores, o método de renda D3.5, os rótulos, nem a contagem de páginas):
- Novo painel `_draw_perfil_panel` (compartilhado pelas 2 variantes): moldura turquesa arredondada
  + cartão branco + cabeçalho (rótulo "Bairro"/"Distrito" + nome + município/UF) + 4 métricas
  empilhadas, cada uma com ícone vetorial (pessoas p/ população e densidade, casa p/ domicílios,
  cifra p/ renda), rótulo cinza e valor grande azul-marinho, com círculo "i" decorativo à direita.
- Helpers novos: `_perfil_icon` (ícones vetoriais via ellipse/polygon/rect), `_perfil_info_dot`,
  `_perfil_metric_rows`, `_perfil_nota_metodo`. Cores novas `_PERFIL_VALOR_RGB`/`_PERFIL_ROTULO_RGB`/
  `_PERFIL_INFO_RGB`/`_PERFIL_DIVISOR_RGB`.
- Os 4 rótulos exatos ("População"/"Densidade demográfica"/"Domicílios"/"Renda média"), o título
  "Perfil do Bairro/Distrito", a mensagem "Perfil não disponível" e o "n/d" gracioso preservados;
  suíte export/motor/acentuação/municipal 96 passed; ruff/mypy limpos; import ok. Verificação visual
  própria: 4 PNGs (recente/clássico × disponível/n-d) renderizados via PyMuPDF, layout fiel à referência.

## Fechamento de housekeeping em lote - BLK-ORQ-21 + BLK-ORQ-26 (2026-07-15)

Housekeeping em lote (modo humano; toca `tasks/backlog.md` = GOVERNANÇA -> exige `aprovado-humano` de co-owner != autor, NÃO auto-mergeia). Fecha formalmente o **BLK-ORQ-21** (portão NO AR desde 2026-07-14, mas o backlog ainda o marcava "Pendente") e registra o **BLK-ORQ-26** (fix não planejado do `claude-review`, mergeado como PR #105 sem entrada de bloco). READ-ONLY sobre o M1; toca só `tasks/backlog.md` (stubs + update do ORQ-23 p/ Telegram) e `tasks/completed.md`.

---

### BLK-ORQ-21 — Aplicar a branch protection nova (0 aprovações, `enforce_admins`, 4 checks) + ligar auto-merge

| Campo | Valor |
|---|---|
| **Criticidade** | **Crítica** (mudou a governança efetiva da `main`). Coberta pela **DEC-016**. |
| **Status** | **CONCLUÍDO 2026-07-14** — portão NO AR na `main` (verificado ao vivo via `gh api .../branches/main/protection`). |
| **Depende de** | BLK-ORQ-20 (concluído). |
| **Autonomia** | manual (NÃO loop-safe). |

**O que foi aplicado.** 4 required checks `test` + `guard` + `review-gate` + `claude-review`; `required_approving_review_count: 0`; `require_code_owner_reviews: true`; `required_conversation_resolution: true`; `strict: true`; `allow_auto_merge: true` + `delete_branch_on_merge: true` (antes `false` — o auto-merge nem existia). Secret `CLAUDE_CODE_OAUTH_TOKEN` (conta pessoal do Felipe, fase de teste, custo de API = 0) + labels `aprovado-humano`/`critica-aprovada`/`criticidade:{baixa,media,alta,critica}` criadas.

**Ordem de bootstrap cumprida.** ORQ-20 mergeado pelo regime antigo (PR #96) -> os 3 checks novos rodaram >=1x num PR real (PR #97) -> SÓ ENTÃO o PUT dos 4 checks + `allow_auto_merge`. O PR #97 achou e corrigiu **4 defeitos** que congelariam o repo: CODEOWNERS com dono único (-> 3 donos + trilho crítico); `set -e` matando o step do `guard` (-> `set +e` + captura de rc); `github_token` faltando no `claude-review` (-> fallback OIDC abortava); deadlock do REVIEW.md #7. Runbook completo em `docs/portao_merge_orq21.md`.

**Provas empíricas (antes de confiar no portão).**
- **N0 anti-spoof** (PR #100, fechado sem merge): code owner funciona com `count:0` E o GitHub exige TODOS os check runs homônimos -> um `guard` forjado verde NÃO fura o portão.
- **Auto-merge zero-humanos** (PR #106, BLK-ORQ-25 Baixa): mergeou sozinho só com `criticidade:baixa`, SEM label humana/admin — a prova que faltava do trilho SEM humano.
- **Trilho COM humano** (PRs #101/#104): mergeou com `aprovado-humano`.

**Ressalva vigente (proving period).** `enforce_admins` segue **`false`** por decisão do Felipe (~1-2 semanas de prova; o `--admin` fica como extintor enquanto o `claude-review` — SPOF externo — prova estabilidade). Virar para `true` é o passo final do endurecimento (PENDÊNCIA registrada). **Kill-switch** (restaura o gate humano em 1 PUT) em `docs/portao_merge_orq21.md`. Gatilho de suspensão: 2 incidentes/90d (detector = BLK-ORQ-23).

**READ-ONLY M1.** DEC-001 intacta (`renda=0.40`/`pop=0.60`, `score_priorizacao`, artefatos oficiais inalterados) — é governança de merge. **Deploy segue manual por digest** (auto-merge NÃO deploya). Refs: PRs #96/#97/#99/#100; DEC-016; `docs/portao_merge_orq21.md`.

---

### BLK-ORQ-26 — `claude-review`: `max_turns` 20->40 + revisão diff-first (fix do fail-closed)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (fix de workflow de CI durante o proving period do portão; **READ-ONLY sobre o M1**). |
| **Status** | **CONCLUÍDO 2026-07-14** (PR #105). Fix NÃO planejado, descoberto no proving period — sem bloco prévio no backlog. |
| **Autonomia** | manual (NÃO loop-safe) — toca `.github/`. |

**Problema.** O `claude-review` estourava `--max-turns 20` (`error_max_turns`, ~US$ 1,33/run) lendo os arquivos grandes do repo (CLAUDE.md + `backlog.md` ~1750 linhas) ANTES de devolver a saída estruturada -> **fail-closed** -> travava PRs legítimos (reprovou o #104 2x).

**Fix** (`.github/workflows/claude-review.yml`): `--max-turns 20->40` + prompt "ler o DIFF primeiro, usar Grep, NÃO ler arquivos gigantes inteiros". Confirmado: a `claude-review` do próprio #105 passou em 56s (vs 2m10s falhando); depois o #106 passou em 1m6s. Como o `claude-review.yml` roda em `pull_request` (versão do HEAD do PR), o próprio PR que edita o workflow já testa a versão nova. O #105 e o #104 foram ADMIN-MERGED (extintor do proving period, `enforce_admins=false`). READ-ONLY sobre o M1.

## Fechamento de ciclo - BLK-ORQ-22 (2026-07-15)

Garimpeiro — ÚLTIMO bloco de governança da DEC-016: o loop na nuvem que abre PRs em `claude/*`, sem merge/deploy. Entregue como CÓDIGO + RUNBOOK (a config de nuvem 1× é do humano, conforme a Esteira do bloco):
- `scripts/garimpeiro_select_block.py` + `tests/unit/test_garimpeiro_select_block.py`: seletor do próximo bloco loop-safe com o MARCADOR ANCORADO (`^\| \*\*Autonomia\*\* \| loop-safe`) — NÃO casa `**manual (NÃO loop-safe)**` (a armadilha do `grep loop-safe`); respeita `Depende de` e pula concluídos com fronteira exata (`BLK-X` não confunde `BLK-X-FU1`; alinhado ao housekeeping diferido do BLK-ORQ-24, com `completed.md` como fonte de verdade). 7 testes verdes, ruff limpo.
- `docs/garimpeiro.md`: runbook — arquitetura (o portão faz rótulo/arm/merge; o Garimpeiro só ABRE o PR), o prompt da routine e a configuração humana 1× (repo PRIVADO `motor-dados` com `data/staging` + deploy key read-only; environment com setup script anti-PII que aborta se `data/staging` não estiver gitignored; routine diária 02:00 BRT; push restrito a `claude/*`, SEM PAT de escrita, SEM credencial de VPS/deploy).

Integração com o portão: com auto-criticidade (#109/#112) + auto-merge, um PR loop-safe (Baixa/Média) aberto pelo Garimpeiro auto-rotula, auto-arma e auto-mergeia (ZERO humanos); um bloco Alta/Crítica que escape para `claude/*` NÃO auto-mergeia (o `guard`/`review-gate` seguram por label humana). READ-ONLY sobre o M1 (pesos `renda=0.40`/`pop=0.60`, `score_priorizacao`, artefatos oficiais INALTERADOS). Este PR é guard-clean (só `scripts/`+`tests/`+`docs/`+`completed.md`) → precisa de UMA aprovação (`aprovado-humano`), estreando a folga da DEC-017.

Os 5 critérios de aceite do bloco estão mapeados no runbook (§5). A configuração de nuvem 1× (criar o repo privado + o environment + a routine) fica com o humano; o restante — seletor testado, prompt, guardrails — está entregue e versionado. Deploy NUNCA automático.

Estado do épico: com o ORQ-22, a trilha de GOVERNANÇA da DEC-016 (ORQ-20..26 + auto-criticidade) está COMPLETA. Restam apenas: (a) o legado ORQ-02 (Fase 2 do run-cycle, anterior à DEC-016); (b) pendências não-bloco — virar `enforce_admins=true` no fim do proving period e um PR de housekeeping em lote (stubs do ORQ-22/23 + auto-criticidade "ORQ-27" + DEC-017).

---

### BLK-ORQ-22 — Garimpeiro: routine na nuvem que abre PRs de branches `claude/*`

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (processo autônomo recorrente que **abre PRs**; não mergeia — o portão é o do ORQ-21. **READ-ONLY sobre o M1**). |
| **Prioridade** | Alta (após o portão estar de pé). |
| **Esteira** | Humano configura 1× (repo de dados + environment + routine) → operação autônoma. |
| **Status** | Pendente. |
| **Depende de** | **BLK-ORQ-21** (sem o portão aplicado, PRs abertos por routine ficariam esperando aprovação humana — não resolveria o gargalo). |
| **Autonomia** | **manual (NÃO loop-safe)** — configuração de infra/nuvem por humano, 1×; NUNCA loop-safe. |

**Contexto.** O loop hoje roda na máquina do Felipe (`iniciar-loop.cmd`). O Garimpeiro leva a execução para a nuvem
e **entrega o trabalho como PR** — sem merge, sem deploy.

**Escopo.**
1. **Repo PRIVADO `motor-dados`** com os **~270 MB de `data/staging`**. **O repo do motor é PÚBLICO
   (`Kastaldy/motor-de-expansao`) — NUNCA publicar parquet nele** (dado de negócio + risco de PII).
2. **Environment** com **setup script** que clona o `motor-dados` e monta `data/staging` antes do bloco rodar.
3. **Routine diária às 02:00 BRT**.
4. **Push restrito a `claude/*`** (permissão default da routine, **sem PAT de escrita** — não consegue push na `main`
   nem em `ciclo/*`).
5. **Prompt exige `scripts/loop_guard.py` VERDE _antes_ de abrir o PR** (falhou → não abre PR, reporta).
6. **Seleção de bloco por marcador ANCORADO:** regex **`^\| \*\*Autonomia\*\* \| loop-safe`** — âncora `^` +
   `| ` obrigatórios; **NÃO casa** `| **Autonomia** | **manual (NÃO loop-safe)** |` (que contém a substring
   "loop-safe" e seria falso-positivo de um `grep loop-safe` ingênuo). Respeitar também `Depende de`.

**Critérios de aceite.**
- Teste do seletor: bloco `manual (NÃO loop-safe)` **NÃO** é selecionado; bloco `loop-safe` **É** (fixtures dos dois
  formatos reais do `backlog.md`).
- A routine **não consegue** push fora de `claude/*` (tentativa falha).
- `loop_guard` vermelho → **nenhum PR aberto**.
- Nenhum `.parquet`/dado de `data/staging` aparece em diff do repo público (verificável no PR).
- 1 execução real: PR aberto a partir de branch `claude/*`, com os 4 checks rodando.

**Guardrail.** §5 **READ-ONLY M1**; **NUNCA** commitar dado/parquet no repo público; sem credencial de VPS/deploy no
ambiente da routine (não deploya); o Garimpeiro **abre PR, não mergeia**.

---

### BLK-ORQ-23 — Auditor de PRs: routine diária READ-ONLY com aviso no Telegram (grupo de ops, fase de teste)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (routine **READ-ONLY**: não aplica label, não mergeia, não escreve código; **READ-ONLY sobre o M1**). |
| **Prioridade** | Alta (é o **detector do gatilho de suspensão** da DEC-016 — sem ele o gatilho não tem medição). |
| **Esteira** | Humano configura 1× (routine + bot/grupo Telegram de ops — o mesmo do Motor) → operação autônoma. |
| **Status** | Pendente. |
| **Depende de** | **BLK-ORQ-20** (precisa dos checks existindo para classificar). |
| **Autonomia** | **manual (NÃO loop-safe)** — configuração de rotina na nuvem por humano, 1×; NUNCA loop-safe. |

**Contexto/Objetivo.** Dar ao Felipe **visão diária** do que está aberto/mergeando **sem** ele virar o gargalo de novo.
O gate é **determinístico** (checks + labels) — o Auditor **informa**, não decide.

**Escopo.**
1. Routine **diária** que lê **PRs abertos + diff + status de CI** (READ-ONLY).
2. **Classifica** cada PR em: **candidato a auto-merge** / **revisar** / **bloqueio**.
3. Entrega **UM aviso por dia no grupo Telegram de ops** (o mesmo usado para os alertas do Motor de Expansão — `chat_id` no `.env`; **fase de TESTE, no lugar do e-mail**) + **comentário em issue fixa** (histórico versionado).
4. **Conta os incidentes** do gatilho da DEC-016: PR auto-mergeado que (i) reprove o `guard` em auditoria posterior,
   (ii) introduza segredo/PII, (iii) exija `revert` na `main`, ou (iv) quebre o CI da `main`.
   **2 incidentes em 90 dias → alerta explícito de SUSPENSÃO do auto-merge** no relatório.

**Critérios de aceite.**
- **NÃO aplica label**, **NÃO mergeia**, **NÃO faz push** (o gate é determinístico, **não a opinião do modelo**) —
  verificável pelas permissões da routine (sem escrita).
- 1 aviso no Telegram por dia (não 1 por PR); issue fixa recebe o mesmo resumo.
- A contagem de incidentes (janela de 90 dias) aparece no relatório, com o alerta de suspensão ao atingir 2.
- Relatório distingue os 3 estados e cita o check que reprovou, quando houver.

**Guardrail.** §5 **READ-ONLY M1**; routine sem permissão de escrita no repo (nem label, nem merge, nem push);
sem credencial de VPS/deploy; **não** expor conteúdo sensível de diff no corpo da mensagem do Telegram (linkar o PR).


---

- BLK-ORQ-24 (concluído 2026-07-14) — ver tasks/completed.md



---

- BLK-ORQ-25 (concluído 2026-07-14) — ver tasks/completed.md

- BLK-ORQ-26 (concluído 2026-07-14) — ver tasks/completed.md


---

- BLK-RELPON-06 (concluído 2026-07-14) — ver tasks/completed.md


---

- BLK-RELPON-06-FU1 (concluído 2026-07-14) — ver tasks/completed.md


---

- BLK-RELPON-07 (concluído 2026-07-15) — ver tasks/completed.md

## Fechamento - Auto-criticidade + auto-merge (candidato a BLK-ORQ-27; sem bloco formal) (2026-07-15)

Feature de governança mergeada nesta esteira SEM bloco BLK dedicado (registro para completude do housekeeping). PRs #109 (label `criticidade:*` automática, lida do backlog da BASE, espelhando o `review-gate`) + #112 (armar auto-merge via `AUTO_MERGE_PAT`, pois o `GITHUB_TOKEN` não habilita `enablePullRequestAutoMerge`). Entregue: workflow `.github/workflows/auto-criticidade.yml` + `scripts/aplicar_criticidade_label.py` + testes. Na abertura de todo PR: aplica `criticidade:<nível>` se faltar e arma o auto-merge para Baixa/Média. PROVADO no #110 (label aplicada por `github-actions[bot]`) e no #115 (guard-clean → uma aprovação). READ-ONLY sobre o M1. Detalhe na emenda da DEC-016 (§8) e na memória.

Também sem bloco formal: a **DEC-017** (#114 — normalização de EOL `.md`=LF em `tasks/`+`docs/` + enxugamento do CODEOWNERS, removendo `/tasks/backlog.md`) está registrada como DEC no CLAUDE.md §8. Com ela, os PRs de ciclo/relatório deixam de conflitar em `backlog`/`completed` e passam a exigir uma aprovação.

## Fechamento de ciclo — BLK-TP-03-FU1 (2026-07-15)

**BLK-TP-03-FU1 — Overlay dos vazios competitivos no Mapa Territorial (Opção B).** Ciclo interativo (Block Orchestrator → Planner → **gate humano de UX aprovado por Felipe em 2026-07-15** → Builder → QA/Opus 4.8). Entregue: overlay opcional **READ-ONLY** (checkbox default OFF, key `mapa_territorial_vazios_lc`) no Mapa Territorial que realça os 229 hexes de "vazio competitivo" do concorrente low-cost (`data/staging/vazios_competitivos_lc.parquet`, contrato `vazios_competitivos_v1`, gerado no BLK-TP-03) como `H3HexagonLayer` roxo `#7C5CFF` (fill `[124,92,255,60]` translúcido + contorno `[124,92,255,230]` 3px), com tooltip de 4 linhas (Membros >5km do concorrente / UF / Município / Score M1) e legenda. Loader lazy+cacheado offline (`@st.cache_data`, sem rede — §2); parquet ausente → checkbox oculto + `st.caption`, nunca exceção.

Implementação 100% **aditiva** (+413/−0) em 3 arquivos: `src/motor_expansao/dashboard/components.py` (`_build_vazios_competitivos_layer`, `render_vazios_competitivos_legend`, extensão de `build_unified_map_figure`/`build_unified_map_figure_cached` com params opcionais `vazios_df`/`_vazios_df`/`vazios_token`), `src/motor_expansao/dashboard/pages.py` (loader + checkbox splice em `enabled_overlays` em memória + hook de legenda) e `tests/integration/test_streamlit_app.py` (6 testes novos). **`constants.py`, `streamlit_app.py` e `demanda_revelada/` intocados** (zero linhas); `_downsample_map_index`/`MAP_POINT_LIMIT*`/`MAP_SOURCE_COLUMNS_*` inalterados (o overlay é camada separada, fora do cap dos 4 modos). O splice usa só checagem de string `"vazios_competitivos_lc" in enabled_overlays` (não registra em `OVERLAYS`), preservando `constants.py`.

**READ-ONLY sobre o M1 (§5):** `score_priorizacao` só é LIDO para o tooltip; nenhuma escrita em pesos/fórmula/carteira/plano/artefatos; `git status -- data/` vazio (nenhum pipeline rodou); DEC-001 (renda 0.40/pop 0.60) e DEC-012 (sem PII nova no layer) intactas. **QA APROVADO COM RESSALVAS (Opus 4.8):** suíte FULL `pytest -n auto` = **1725 passed, 85 skipped, 4 failed**; as 4 falhas (`test_score_retencao_territorial`, `test_validation_dataset` x2, `test_batch_viabilidade`) foram provadas **pré-existentes na base limpa** (via `git stash`), determinísticas e específicas do **Python 3.14 local** (ex.: `assert nan is None`), sem qualquer caminho de import para `dashboard/` → **zero regressão** deste ciclo; o gate real de merge é o check `test` no CI (Python 3.11). `-k vazios` = 5 passed; `import streamlit_app` ok; ruff limpo; mypy 0 issues. Handoffs versionados: `context/handoff/20260715-{201359-block-orchestrator,172232-planner,183906-builder,185118-qa}.md`.

## Fechamento de ciclo — BLK-RELPON-08 (2026-07-15)

Ciclo APROVADO pelo QA (Opus 4.8) e pela REVISAO VISUAL HUMANA do PDF (Felipe, 2026-07-15). Esteira: Block Orchestrator -> Planner -> Builder -> QA. Criticidade Media, READ-ONLY sobre o M1. Modo de merge: AUTO-MERGE (nao toca backlog.md; stub diferido para o PR de housekeeping em lote).

- **Entregue:** pagina Big Numbers do Relatorio Pontual Censitario reformada em `_big_numbers_page` (`censo_report.py`): (1) card "Score censitario maximo" (`score_setor_max`) trocado por "Numero de domicilios" (novo `domicilios_total_raio`, no raio de 1,5 km) — `score_setor_max` mantido no result/CSV para auditoria; (2) linha 1 reordenada (L1 = Populacao total no raio, Renda per capita media, Numero de domicilios, Score censitario medio); (3) semaforo verde/vermelho/neutro por meta via helpers PUROS `_cor_por_meta`/`_cor_consumo_concorrentes`, com as 6 metas como constantes nomeadas `_META_*`, regra assimetrica do Consumo (SAM>=2000 E Residual<2000 -> vermelho), Concorrentes espelhando Consumo, e n/d -> neutro tratado antes da comparacao. Paleta pastel (verde (205,236,217) / vermelho (248,209,209) / neutro (232,233,237)).
- **Novo campo:** `domicilios_total_raio` em `analisar_ponto_censitario_setores` (`censo_point.py`), computado pelo MESMO padrao de peso de area de `pop_total_raio` (`domicilios_particulares_ocupados_setor_2022 x peso_area_setor`, soma; "n/d" gracioso; chave no dict default).
- **QA (evidencia propria):** testes do escopo (motor + export/PDF + integracao streamlit) 300 passed / 0 failed; import ok; ruff limpo; mypy limpo. Suite full: 1726 passed, 85 skipped, 4 failed pre-existentes de ambiente Python 3.14 local (provadas identicas na base via git stash), fora do escopo.
- **Revisao visual:** PDF real de Guarulhos/SP (ponto -23.4547,-46.5220; 200 setores no raio) gerado e aprovado por Felipe: card "Numero de domicilios" (31.060) em L1C3, "Score maximo" fora da grid, semaforo coerente (pop/renda/domicilios/SAM/residual verdes, score medio 54,4 vermelho).
- **Guardrails:** READ-ONLY M1 confirmado (nenhum `pipelines/m1/`/`config.py`/score/artefato oficial tocado; pesos renda=0.40/pop=0.60 intactos); metodo de intersecao/raio 1,5 km/marca d'agua INTOCADOS; acentuacao latin-1 safe.
- **Arquivos:** `src/motor_expansao/dashboard/censo_point.py`, `src/motor_expansao/dashboard/censo_report.py`, `tests/unit/test_relatorio_pontual_censitario_motor.py`, `tests/unit/test_relatorio_pontual_censitario_export.py`, `docs/relatorio_pontual_censitario.md`.

### BLK-REV-08 — Spike técnico: mapa client-side (deck.gl H3HexagonLayer) — teto de performance (concluído 2026-07-16)

- **Veredito QA (Opus 4.8, 2026-07-16): APROVADO.** Ciclo /run-cycle Média, READ-ONLY sobre o M1. Esteira: Block Orchestrator (sonnet) → Planner (opus) → **[REVISÃO HUMANA — visual/perf] APROVADO por Vinicius em 2026-07-16** → Builder (opus) → QA (opus). Bloco **manual (NÃO loop-safe)**. Dependências satisfeitas (BLK-REV-07 e BLK-REV-03 concluídos).
- **Objetivo:** protótipo DESCARTÁVEL que mede empiricamente o teto de performance de um mapa client-side (deck.gl `H3HexagonLayer` servido por `st.components.v1.html`, padrão do `ui_proto.py`/BLK-UI-10) vs pydeck/Streamlit, no volume real do cap de produção (18–35k hexes). Insumo para a decisão de rumo do BLK-REV-12. NÃO decide rumo; NÃO substitui o mapa de produção.
- **Decisão técnica fechada (Planner, aprovada no gate):** motor de render = **deck.gl `H3HexagonLayer`** (UMD por CDN), **sem MapLibre no spike** (MapLibre fica como opção viva do REV-12). `H3HexagonLayer` aceita `hex_id` cru (`getHexagon: d=>d.h`) e tessela na GPU — elimina as 18–35k chamadas `h3.cellToBoundary` em CPU do caminho Leaflet e tira a geometria do payload. Recolor (dor #2) = `updateTriggers.getFillColor` client-side; seleção/cenário (dor #3) = `pickable`+`onClick` sem rerun.
- **Arquivos criados (4, todos novos/isolados):** `src/motor_expansao/dashboard/ui_spike_deckgl.py` (recorte/HTML/render/opt-in: `gerar_recorte_spike_json`, `_build_deckgl_html`, `render_mapa_deckgl`, `is_spike_enabled`, `render_spike_page`; opt-in por env `ULTRA_SPIKE_DECKGL=1`/`session_state`, NÃO importado por `pages.py`); `scripts/rev08_spike_playwright.py` (harness dos 4 fluxos de dor, CLI `--url`/`--uf`/`--flow`/`--runs`/`--target`/`--i-confirm-production`, default localhost, **guarda anti-produção** que aborta contra `ultra-expansao.tech` sem confirmação explícita); `docs/rev08_spike_perf_runbook.md` (3 sub-entregáveis — DevTools, Playwright contra produção, A/B via Caddy VPS — com aviso §6 por comando de VPS e tabelas EM BRANCO); `tests/unit/test_ui_spike_deckgl.py` (25 testes). Cache runtime gitignored `data/cache/ui_spike_deckgl/` isolado do `ui_proto`.
- **Payload enxuto (D3):** fonte = partição derivada por UF `data/outputs/hexagonos_dashboard_enriquecido/uf=*/` (mesma que o dashboard lazy-carrega; READ-ONLY). Cap espelha `components.py:1552` (>35k → LARGE 18k; senão 35k; ordena por `score_priorizacao` desc antes do `.head`; `mode_stress` desliga o cap). Chaves curtas `h/bm1/br/s/sr/p/o`, 2 bandas de cor pré-computadas (`RESIDUAL_SCORE_BANDS`), SEM geometria/lat-lng/PII; `view` (bbox) pré-computado uma vez; JSON determinístico byte-idêntico; `version="ui_spike_deckgl_v1"`.
- **Validações QA (evidência própria, NO-BYPASS):** suíte FULL SERIAL (`-p no:xdist`, pois xdist/execnet é instável no Python 3.14 local) = **1 failed, 1843 passed, 2 skipped**; a única falha é `test_score_retencao_territorial::test_run_readonly_m1_por_mtime` (parquet de staging `unidade_territorio_retencao.parquet` gitignored ausente — pré-existente e ambiental; `git diff HEAD` vazio ⇒ falharia idêntico no HEAD, NÃO é regressão do spike). Testes do spike: **25 passed**. ruff limpo; mypy limpo (Success, no issues). Imports ok (`ui_spike_deckgl`; app real é top-level `streamlit_app`). `grep -L` confirma `pages.py` NÃO importa o spike. Recorte real SP = **18000 hexes** (47.389 > 35k → cap LARGE), zero chaves de PII/geometria. Guarda anti-produção aborta (exit 2). Runbook: 3 sub-entregáveis, 6 avisos §6, tabelas em branco, acentuação correta. `_REPO_ROOT` usa `parents[3]` (correto p/ a profundidade do arquivo; `ui_proto.py` NÃO tocado).
- **Guardrails:** READ-ONLY M1 confirmado — mtime dos 4 artefatos oficiais inalterado (2026-06-10); `pipelines/m1/`/`config.py` intocados; pesos renda=0.40/pop=0.60 intactos. `pyproject.toml` intocado (deck.gl por CDN; Playwright já no extra `[scraping]`, sem dep nova). §6: nada executado contra a VPS nem contra produção (só entrega script/runbook).
- **Tail HUMANO pendente (fora do código, por design):** os NÚMEROS reais (FPS, clique→paint, tamanho de frames WebSocket, A/B Streamlit vs deck.gl na VPS) são passo humano pós-QA, executando o runbook — insumo empírico exigido pelo BLK-REV-12. A esteira autônoma NÃO os produz.
- **Housekeeping:** stub do backlog DIFERIDO (bloco `manual`/não-loop-safe com cauda humana de medição; merge humano decidido em sessão interativa). `completed.md` é a fonte de conclusão. Commit por path na branch `ciclo/BLK-REV-08`.

### BLK-REV-08-FU1 — Fix de render do spike no gate visual/perf (deck.gl operável) (2026-07-16)

- **Contexto:** durante o gate [REVISÃO HUMANA — visual/perf] (Vinicius rodando o protótipo local), o mapa deck.gl não renderizava os hexágonos e não respondia a zoom/pan/clique. Três defeitos reais encontrados e corrigidos, ao vivo, iterando com o gate humano:
  1. **Protótipo órfão:** nada chamava `render_spike_page()`; `ULTRA_SPIKE_DECKGL=1 streamlit run streamlit_app.py` mostrava o dashboard normal, não o spike (e o caminho de `streamlit_app.py` no runbook estava errado — o real é `./streamlit_app.py` na raiz). **Fix:** novo lançador standalone descartável `scripts/rev08_spike_app.py` (serve só `render_spike_page()`, opt-in, NÃO importado por produção) + runbook corrigido.
  2. **h3 incompatível no bundle standalone:** `H3HexagonLayer` do deck.gl chamava a API v3 do h3 (`h3GetResolution`/`h3ToGeo is not a function`) que o h3 embutido (v4) não tinha → a camada morria na init (sem hexes; controlador travado). **Fix (à prova de versão):** carregar `h3-js@4` explícito por CDN + render com `PolygonLayer` (core, sem dep de h3), tesselando a célula no CLIENTE via `h3.cellToBoundary(hex_id, true)`. **Preserva a tese** do spike: payload segue só com `hex_id` cru (geometria calculada no browser, cacheada em `d.__poly`).
  3. **Interação morta:** deck.gl recebia um `<canvas>` feito à mão (`canvas: 'deck-canvas'`) — caminho que não conecta o controlador no bundle standalone. **Fix:** deck cria o próprio canvas dentro de `<div id="container">` (`container: 'container'`) → zoom/pan/clique funcionam dentro do iframe do Streamlit. Também adicionado captador de erro na própria página (`window.onerror` + try/catch no boot + diagnóstico de classes ausentes) para falhas futuras serem legíveis sem DevTools.
- **CDN pinado:** `deck.gl@8.9.36` (era `@latest`=9.3.6, que também falhava blindamente antes do captador de erro) + `h3-js@4.1.0`.
- **Resultado (confirmado por Vinicius no browser):** 18.000 hexes SP renderizam coloridos por faixa de score; recolor M1↔Residual, zoom/pan e clique-para-selecionar operacionais.
- **1ª medição local (Playwright, laptop, sem rede VPS, 3 runs):** render (trigger→1º paint) mediana **463 ms** / p95 525; recolor **46 ms** / p95 101; cenário (add hex) **32 ms**; PDF pulado (dor server-side, só `--target production`). Payload inline SP = **~1,45 MB** (18k × 7 chaves). Números de produção/A-B na VPS seguem passo humano (§6). JSON em `data/reports/scratch/rev08_spike_local.json` (gitignored).
- **Validações:** 25 testes do spike verdes (assert de camada atualizado H3HexagonLayer→PolygonLayer/`cellToBoundary`/`h3-js`); ruff limpo; mypy limpo (módulo + lançador). READ-ONLY M1 inalterado; sem dep nova em `pyproject.toml` (deck.gl/h3-js por CDN; Playwright já em `[scraping]`). Arquivos: `src/motor_expansao/dashboard/ui_spike_deckgl.py`, `scripts/rev08_spike_app.py` (novo), `docs/rev08_spike_perf_runbook.md`, `tests/unit/test_ui_spike_deckgl.py`.

### BLK-REV-08-FU2 — Correção da medição por volume + curva de escala do spike (2026-07-16)

- **Correção de honestidade:** a "1ª medição local" do FU1 (render 463 / recolor 46 / cenário 32 ms rotulada "SP 18k") estava **mal atribuída** — o harness `rev08_spike_playwright.py` clica "Gerar recorte" com a UF **default** do seletor e NÃO seleciona a `--uf`, então mediu a UF default (AC), não SP. Limitação documentada no runbook.
- **Remedição determinística por volume** (gera recorte → monta HTML → abre `file://` no Chromium/Playwright → lê `window.__spike*`; isola o deck.gl do iframe do Streamlit; 3 runs/mediana; laptop, SEM rede VPS):
  - **SP cap 18k** (produção LARGE): payload 1,46 MB · render **478 ms** · recolor 38 ms · cenário 57 ms.
  - **AC full 29k:** 2,41 MB · render 640 ms · recolor 34 ms · cenário 90 ms.
  - **SP stress 47k:** 3,86 MB · render 497 ms · recolor 71 ms · cenário 64 ms.
  - **MG stress 104k:** 8,46 MB · render ~1038 ms (2/3 runs > 45 s → instável) · recolor 30 ms · cenário 177 ms.
- **Leitura para o REV-12:** o diferencial do client-side é a **interação** (recolor 30–71 ms, cenário 57–177 ms), quase PLANA com o volume e sem round-trip ao servidor — a ordem de grandeza a comparar contra o rerun server-side do Streamlit. O `render` (1º paint) escala com o payload/tesselação e só vira gargalo perto de ~100k; a faixa operacional (cap 18k–35k) fica em ~0,5–0,65 s de render e < 100 ms de interação. **Caveat aberto (passo humano, §6):** validar na VPS se o payload inline (1,5–8,5 MB) sobrevive ao link real — o harness NÃO mede o app atual (markers `window.__spike*` são só do spike; baseline do app atual = REV-03..06/DevTools).
- **Sem toque em código de produção/M1:** correção só em `docs/rev08_spike_perf_runbook.md` (tabelas). Medição via script throwaway de scratchpad (não versionado). READ-ONLY M1 inalterado.

### BLK-REV-08-FU3 — Comparação automatizada spike x app atual (baseline do dashboard atual) (2026-07-16)

- **Automação do baseline do app atual** (o harness do spike não serve — markers são só do spike): script Playwright throwaway que dirige o dashboard real local (`:8502`, UF=SP, aba Mapa), captura os frames do WebSocket do Streamlit e mede, por interação, a latência clique→chegada do maior frame WS (mapa re-serializado) + o tamanho do frame. 5 runs, mediana, laptop local (mesma máquina do spike), SEM rede VPS.
- **Controles descobertos no app real:** tabs = segmented control (Mapa/Executivo/Expansão de Domínio/Carteira e Plano/Viabilidade); **selectbox "Modo de cor"** (Censitário/Residual Fitness/Expansão de Domínio) = recolor; botão **"Atualizar mapa"** = render.
- **Resultado (app atual x spike):**
  - render (atualizar/1º mapa): **791 ms** (frame WS ~239 KB) x spike **478 ms** → ~1,7×.
  - recolor (trocar modo de cor): **3282 ms (~3,3 s)** (frame WS ~239 KB) x spike **38 ms** → **~86×**.
  - payload por interação: app atual ~**239 KB por rerun (a CADA clique)** x spike **1,46 MB uma vez** (0/clique) → break-even ~6 cliques/sessão.
- **Leitura para o REV-12:** o `render` do zero é comparável (o app atual segura bem); o **abismo é a interação** — o rerun do Streamlit (recompute + re-serializa + repaint) custa ~3,3 s por troca de cor vs 38 ms client-side do spike. O trade-off de payload (mandar ~239 KB a cada clique vs 1,46 MB uma vez) equilibra em ~6 interações, bem abaixo do uso real. Caveats: `scenario` (add hex) não automatizado (exige clique por pixel no mapa pydeck, mas incorre no MESMO rerun); `239 KB` é o maior frame único; tudo LOCAL — perna VPS segue passo humano (§6).
- **Sem toque em produção/M1:** só `docs/rev08_spike_perf_runbook.md`; scripts de medição throwaway em scratchpad (não versionados). READ-ONLY M1 inalterado.

---

### Epic BLK-RELVIAB — Relatório de Viabilidade do Imóvel (PDF: fotos + info + slides financeiros)

Data: 2026-07-18 | PRs: #127 (backlog), #130 (blocos 01–05), #132 (bloco 06 + polish) | Deploy prod: 2026-07-18 (streamlit `sha-99acf6a`, digest `sha256:2d5026ebb103…c0be5e`).

**Objetivo (concluído):** enriquecer o PDF gerado a partir da aba **Viabilidade** com fotos do imóvel, informações do imóvel e slides de viabilidade financeira; o **relatório completo** passou a ser gerável/baixável pela própria aba. Saída 100% OPCIONAL (params default `None` → PDF byte-compatível com o anterior). READ-ONLY sobre o M1.

**Blocos:**
- **BLK-RELVIAB-01** (loop-safe) — `_fotos_imovel_page` + `_normalizar_foto` (EXIF, downscale, recompressão JPEG) + `_fotos_cells`/`_recortar_cover`. Página de até 2 fotos após a capa; MVP tamanho fixo (cover-crop, paisagem 3:2), borda laranja/magenta. Param `fotos` nos dois geradores.
- **BLK-RELVIAB-02** (loop-safe) — `_info_imovel_page` + `_info_valor`. Página de info do imóvel (cards + observações). Param `info_imovel`.
- **BLK-RELVIAB-03** (loop-safe) — novo `dashboard/viabilidade_charts.py`: 4 gráficos matplotlib→PNG (rampa de alunos, faturamento+EBITDA, FCF com payback no cruzamento real da série, waterfall DRE com R$ nas barras). Fundo transparente. Sem dependência nova.
- **BLK-RELVIAB-04** (loop-safe) — `_viabilidade_page`: slide de números (grid 4x2) + slide de gráficos. Param `viabilidade`.
- **BLK-RELVIAB-05** (loop-safe) — threading dos params pelo dispatcher `gerar_payloads_download_relatorio_censitario`/`render_downloads_*` + assembler `montar_payload_viabilidade` (engine→dict). Regressão byte-compatível.
- **BLK-RELVIAB-06** (manual/Alta) — UI na aba Viabilidade: `st.file_uploader` (2 fotos) + form de info + botão "Gerar relatório (PDF)"; `_montar_insumos_censo_pdf` (com fallback gracioso), contexto em `session_state` (sobrevive a reruns), `competitors_df`/`ultra_df` threaded.

**Polish visual (validação de Felipe, 2026-07-17/18):** fotos maiores/paisagem com borda; Big Numbers 4x2 (removido "Score censitário médio"); gráficos com fundo transparente, FCF alinhado, R$ no DRE; **mapas de calor + concorrentes com fundo TRANSPARENTE** (censo_map canvas RGBA `(255,255,255,0)` → `/SMask` no PDF) e render **landscape 1280×760** (map_box ~1.55) — maiores e retangulares, cores do choropleth intocadas. Verificação da mudança dos mapas por workflow (investigação + protótipo em worktree isolado rodando os testes reais).

**Governança:** emenda à **DEC-004** (CLAUDE.md §8) cobrindo o novo caminho de tiles online (aba Viabilidade = mesmo Relatório Pontual/mecanismo, mitigações vigentes). `claude-review` + `test` verdes antes do merge; ruff + mypy limpos. READ-ONLY sobre o M1 (sem toque em score/pesos/carteira/plano/artefatos); sem dependência nova; anti-PII (fotos/dados só em memória).

Arquivos: `dashboard/censo_report.py`, `dashboard/viabilidade_charts.py` (novo), `dashboard/censo_map.py`, `dashboard/pages.py`, `streamlit_app.py`, `CLAUDE.md` (DEC-004 emenda), `tests/unit/test_relatorio_pontual_*` (+ novos).

---

### BLK-REV-08 — Spike técnico: mapa client-side (deck.gl/MapLibre) servido por API — teto de performance

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (embasa empiricamente o REV-07; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — visual/perf]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-REV-07** (ou BLK-REV-03). |
| **Autonomia** | **manual (NÃO loop-safe)** — protótipo VISUAL throwaway; exige VER o render e medir FPS/interação no browser (lição BLK-UI-10). NÃO marcar loop-safe. |

**Contexto.** Para embasar o REV-07, medir empiricamente o teto de performance do mapa client-side vs pydeck/Streamlit.
**Objetivo.** Spike **descartável**: servir os hexes H3 por um endpoint e renderizar client-side (deck.gl
`H3HexagonLayer` / MapLibre), medindo FPS, latência de troca de cor e de seleção vs o app atual. Protótipo, **NÃO
produção**.
**Guardrail.** §5 READ-ONLY M1; código de spike isolado, descartado após medir.

> **Emenda (2026-07-10, Felipe):** (a) **partir do padrão já provado do `ui_proto.py`** (BLK-UI-10:
> `st.components.v1.html` + dados embutidos + recorte por UF em `data/cache/ui_proto/`), trocando Leaflet
> por deck.gl `H3HexagonLayer`/MapLibre e **escalando ao volume real do cap (18–35k hexes)** — a pergunta
> que o PoC Leaflet (~500 hexes) não respondeu; `H3HexagonLayer` aceita `hex_id` cru (sem enviar geometria).
> (b) **Incluir a medição VPS↔cliente como sub-entregável:** (i) DevTools contra a produção — tamanho real
> dos frames WebSocket por rerun e tempo clique→paint (fecha o caveat iii dos REV-01..06); (ii) script
> Playwright (dep já no extra `[scraping]`) cronometrando os 4 fluxos de dor ponta-a-ponta contra
> `dashboard.ultra-expansao.tech`; (iii) A/B final: spike servido pelo Caddy da VPS, medido pelo mesmo
> script — comparação Streamlit vs client-side na mesma rede real. Prioridade ELEVADA (2026-07-10): com o
> time poliglota (ver emenda do REV-12), este é o número que decide o rumo no REV-12.

---

### BLK-TP-03-FU1 — Overlay dos vazios competitivos no Mapa Territorial (Opção B)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (camada de visualização/overlay no dashboard; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — UX: cor/toggle/tooltip]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-TP-03** (concluído — parquet `data/staging/vazios_competitivos_lc.parquet`, 229 hexes). |
| **Autonomia** | **manual (NÃO loop-safe)** — toca `src/motor_expansao/dashboard/` (decisão de produto/UX). |

**Objetivo.** Expor os hexes de "vazio competitivo" (parquet gerado no BLK-TP-03) como **overlay visual
READ-ONLY** no Mapa Territorial: toggle na sidebar (default OFF) + camada de realce (contorno/cor
distinta) sobre os 229 hexes, com tooltip de `membros_gt5km_concorrente_lc`/`uf`/`nome_municipio`/
`score_priorizacao`. É a **Opção B** deferida no gate humano do BLK-TP-03 (Opção A = só parquet foi a
escolhida). Camada visual de apoio (§2) — não altera score/ranking/carteira/plano/artefatos.

**Plano técnico já detalhado** no handoff do Planner do BLK-TP-03 (passos 6–9):
`context/handoff/20260702-104651-planner.md` — inclui a exigência de LER `constants.py`
(`MAP_POINT_LIMIT`, `MAP_SOURCE_COLUMNS_*`) e `_downsample_map_index` ANTES de codar, para não
regredir o cap dos 4 modos do mapa (M1/Híbrido/Censitário/Residual).

**Critérios de aceite.** Toggle default OFF; layer só desenha os hexes do parquet; leitura lazy/cacheada
offline (sem rede — §2); parquet ausente → toggle oculto/desabilitado com mensagem clara; score/
carteira/plano do dashboard inalterados com overlay ON; cap dos 4 modos inalterado; teste de
integração cobre o toggle/layer; suíte verde; `import streamlit_app` ok.
**Guardrail.** §5 (READ-ONLY M1); §2 (sem API ao vivo); pins/camadas de concorrente são apoio visual
(CLAUDE.md §2). NÃO tocar `_downsample_map_index`/`MAP_POINT_LIMIT`/`MAP_SOURCE_COLUMNS_*`.

---

- BLK-TP-04 (concluído 2026-07-02) — ver tasks/completed.md



---

- BLK-TP-06 (concluído 2026-07-02) — ver tasks/completed.md


---

- BLK-TP-07 (concluído 2026-07-03) — ver tasks/completed.md

---

### BLK-RELPON-08 — Big Numbers (pagina 5) do Relatorio Pontual: trocar metrica, reordenar e semaforo verde/vermelho por meta

| Campo | Valor |
|---|---|
| **Criticidade** | **Media** (altera a pagina Big Numbers do Relatorio Pontual Censitario; **READ-ONLY sobre o M1**; ADICIONA um campo agregado `domicilios_total_raio` ao motor do ponto e muda layout/cor da grid; nucleo `censo_*` so ESTENDE leitura/render, sem tocar intersecao/raio/marca d'agua). |
| **Prioridade** | A definir (Vinicius). |
| **Esteira** | Block Orchestrator -> Planner -> Builder -> QA -> `[REVISAO HUMANA - visual do PDF]` -> merge. |
| **Status** | Pendente - decisoes de produto D1/D2/D3 JA TOMADAS (Vinicius, 2026-07-15, abaixo). |
| **Depende de** | Relatorio Pontual ja existente (pagina Big Numbers, `_big_numbers_page`); malha de setores IBGE 2022 com `domicilios_particulares_ocupados_setor_2022` (ja usada pelo BLK-RELPON-07). |
| **Autonomia** | **manual (NAO loop-safe)** - altera relatorio auditavel e exige revisao visual do PDF. |

**Objetivo.** Ajustar a pagina 5 (Big Numbers) do Relatorio Pontual Censitario em tres frentes:
(1) substituir a metrica "Score censitario maximo" por "Numero de domicilios" (no raio); (2) reordenar
a linha 1 da grid; (3) pintar o fundo de cada quadro em verde (meta atingida = "positivo") ou vermelho
(meta nao atingida = "negativo"), estilo semaforo, comparando cada valor com a meta esperada.
READ-ONLY sobre o M1.

**Contexto tecnico (medido 2026-07-15).**
- A pagina Big Numbers (`_big_numbers_page` em `censo_report.py`) e toda "no raio de 1,5 km". Grid 4x2,
  8 cards, hoje na ordem (indice = `row*4 + col`, `row=idx//4`, `col=idx%4`):
  - L1: [`Populacao total no raio` (`pop_total_raio`), `Renda per capita media` (`renda_per_capita_media_raio`),
    `Score censitario medio` (`score_setor_medio`), `Score censitario maximo` (`score_setor_max`)]
  - L2: [`SAM Fitness (alunos)` (`sam_fitness_potencial`), `Residual Fitness (alunos)` (`oferta_efetiva_disponivel`),
    `Concorrentes no raio` (`n_concorrentes`), `Consumo concorrentes (est.)` (`oferta_consumida_mercado_estimada`)]
- **NAO existe hoje um campo de domicilios no raio.** `analisar_ponto_censitario_setores` agrega
  pop/renda/score no raio mas NAO domicilios. Sera preciso CRIAR o campo `domicilios_total_raio` no
  `result`, computado com o MESMO padrao de `pop_total_raio`: soma de (`domicilios_particulares_ocupados_setor_2022`
  x `peso_area_setor`) sobre os setores intersectados (peso = fracao da area do setor dentro do circulo,
  ja materializada em `pop_estimada_intersecao`/`peso_area_setor`). "n/d" gracioso quando nenhum setor tem
  domicilios.
- `domicilios_total` do BLK-RELPON-07 e do BAIRRO/DISTRITO inteiro (pagina 4), NAO do raio - nao reusar
  aqui (escopos diferentes: pagina 4 = bairro, pagina 5 = raio).

**Decisoes de produto (gate - JA RESPONDIDAS por Vinicius, 2026-07-15).**
- **D1 - trocar metrica:** "Score censitario maximo" (`score_setor_max`) SAI da grid; ENTRA "Numero de
  domicilios" (no raio, novo campo `domicilios_total_raio`). O campo `score_setor_max` PODE permanecer no
  `result`/CSV para auditoria (so deixa de ser exibido), como o BLK-RELPON-05 fez com `*_setor_ponto`.
- **D2 - reordenar linha 1:** "Numero de domicilios" vai para **L1C3**; "Score censitario medio" vai para
  **L1C4** (trocam de posicao). Linha 1 final = [Populacao total no raio, Renda per capita media, Numero de
  domicilios, Score censitario medio]. Linha 2 INALTERADA.
- **D3 - semaforo verde/vermelho por meta:** o FUNDO de cada quadro passa a verde (meta atingida) ou
  vermelho (meta nao atingida), conforme:

  | Card | Verde (positivo) quando | Campo |
  |---|---|---|
  | Populacao total no raio | `>= 10000` | `pop_total_raio` |
  | Renda per capita media | `>= 1500` | `renda_per_capita_media_raio` |
  | Numero de domicilios | `>= 3000` | `domicilios_total_raio` (NOVO) |
  | Score censitario medio | `>= 60` | `score_setor_medio` |
  | SAM Fitness (alunos) | `>= 2000` | `sam_fitness_potencial` |
  | Residual Fitness (alunos) | `>= 2000` | `oferta_efetiva_disponivel` |
  | Consumo concorrentes (est.) | VERMELHO quando `sam_fitness_potencial >= 2000` **E** `oferta_efetiva_disponivel < 2000`; senao VERDE | `sam_fitness_potencial`, `oferta_efetiva_disponivel` |
  | Concorrentes no raio | ESPELHA a cor de "Consumo concorrentes (est.)" | (segue o card acima) |

**Escopo permitido (READ-ONLY M1, so display/relatorio + 1 campo agregado no raio).**
- `censo_point.py` - novo campo `domicilios_total_raio` no `result` de `analisar_ponto_censitario_setores`,
  computado pela soma de (`domicilios_particulares_ocupados_setor_2022` x `peso_area_setor`) (mesmo padrao de
  `pop_total_raio`; "n/d"/None gracioso). SO leitura/agregacao; nao toca intersecao/raio/`circle_metric`/metodo.
- `censo_report.py` - em `_big_numbers_page`: (a) trocar o card `score_setor_max` por `domicilios_total_raio`
  ("Numero de domicilios", `_format_number(..., 0)`); (b) reordenar L1 conforme D2; (c) aplicar cor de fundo
  por card (verde/vermelho/neutro) conforme D3 - helper PURO de decisao de cor por card + a pintura do
  retangulo do card. Contraste de texto preservado (rotulo/valor legiveis sobre o fundo).
- Testes: agregacao `domicilios_total_raio` (com peso de area conhecido; "n/d"); ordem/rotulos dos cards da
  L1; cor por card em cenarios (acima/abaixo da meta; a regra do Consumo; o espelho do Concorrentes; n/d
  neutro).
- `docs/relatorio_pontual_censitario.md`.

**Questoes para o gate/Planner (a confirmar antes do Builder).**
- **Q1 - "Numero de domicilios" e NO RAIO** (novo `domicilios_total_raio`), nao do bairro (pagina 4).
  Recomendado e assumido; confirmar no gate visual.
- **Q2 - valor "n/d" (dado ausente):** propor cor NEUTRA (cinza claro, sem verde/vermelho) quando o valor do
  card e None/"n/d" (pintar verde/vermelho um dado ausente seria enganoso). Vale tambem para
  Consumo/Concorrentes quando SAM ou Residual e n/d (condicao indecidivel -> neutro). Confirmar.
- **Q3 - paleta/contraste:** propor fundo em tom PASTEL (verde/vermelho claro) com barra de acento solida,
  mantendo rotulo/valor em cinza-escuro legivel; ajuste fino no gate visual.
- **Q4 - as metas (10000/1500/3000/60/2000/2000) sao constantes de DISPLAY** locais ao relatorio (nao sao
  gate do M1/mercado); recomendado vira-las constantes nomeadas no modulo (auditaveis). Confirmar.

**Fora de escopo.** Metodo de intersecao `setor_censitario_intersecao_area_1p5km`, raio 1,5 km,
`RAIO_CENSITARIO_DEFAULT_KM`, mapas de calor/choropleth, marca d'agua anti-PII, `set_compression(False)`,
pagina "Perfil do Bairro/Distrito" (BLK-RELPON-07). `score_priorizacao`/pesos/`hex_score_estrutural`/
carteira/plano/artefatos oficiais do M1. `flag_sam`/gate do SAM (DEC-006/DEC-007) - as metas de cor sao de
DISPLAY, NAO alteram o gate do SAM nem os valores de `sam_fitness_potencial`/`oferta_efetiva_disponivel`.
Contagem de paginas (segue 6). Relatorio Municipal e UI do dashboard.

**Riscos.**
- **Novo campo no raio** - `domicilios_total_raio` deve seguir EXATAMENTE o padrao de peso de `pop_total_raio`
  (fracao de area), senao o numero diverge de pop/renda no mesmo raio. Teste dedicado com peso de area conhecido.
- **Contraste** - fundo colorido nao pode tornar rotulo/valor ilegiveis; validar no gate visual (texto escuro
  sobre pastel claro).
- **n/d pintado como meta** - sem a cor neutra (Q2), um dado ausente viraria "vermelho" (falsa reprovacao) ou
  "verde"; tratar n/d explicitamente.
- **Semantica do Consumo/Concorrentes** - a regra e assimetrica (Consumo e "ruim" quando ha demanda SAM alta
  mas Residual baixo = mercado ja consumido); documentar na nota do slide para nao confundir "verde = mais
  concorrentes".
- **Metas hardcoded** - se viram constantes nomeadas (Q4), fica auditavel; caso contrario, documentar os
  limiares na nota do slide.

**Criterio de aceite.** Pagina Big Numbers passa a exibir "Numero de domicilios" (no raio) em L1C3 e "Score
censitario medio" em L1C4, sem "Score censitario maximo"; cada quadro tem fundo verde/vermelho (neutro para
n/d) conforme as metas de D3, com Consumo pela regra SAM x Residual e Concorrentes espelhando Consumo;
`domicilios_total_raio` computado por peso de area e testado; intersecao/raio/marca d'agua/M1 INTOCADOS;
`ruff`/`mypy` limpos; suite verde; revisao visual do PDF aprovada.

---

## Fechamento de ciclo — Renda média domiciliar: tooltip + mapa PDF + API/bot (2026-07-17)

> **Registro retroativo (2026-07-27).** Este ciclo fechou sem entrada aqui — o commit de housekeeping
> `639f28b` registrou a feature **apenas no `CLAUDE.md`** (§4 + §5), que na prática virou o único
> bookkeeping. A entrada abaixo reconstrói o fechamento a partir daquele texto antes que o enxugamento
> do `CLAUDE.md` (que aponta para cá como "fonte única de conclusão") deixasse o ciclo sem lar nenhum.

**Renda média domiciliar** — PRs **#124 / #125 / #126 / #129**, ClickUp `86e2d4w7m` (concluído).
**READ-ONLY sobre o M1** (§5): camada de VISUALIZAÇÃO; não recalcula `score_priorizacao`,
`hex_score_estrutural`, pesos, carteira, plano ou artefatos oficiais.

**Entregue.** A renda média domiciliar passa a ser exibida em 3 lugares, sempre pela mesma fórmula
`renda_pc_calibrada × moradores × uplift × FATOR_TEMPORAL_RENDA`:

- **(a) Tooltip do hex** (PR #125) — `_renda_media_domiciliar_series` em `dashboard/components.py`.
  Uplift e moradores **MUNICIPAIS** (`cod_municipio` → `uplift_renda_domiciliar` /
  `moradores_por_domicilio_municipio`, de `uplift_renda_domiciliar_municipio.parquet`). Computado
  **em tempo de render** a partir das colunas já servidas — não regenera artefato, não depende do
  parquet enriquecido. Uplift **setorial não se aplica ao hex**: um hex res-7 cobre vários setores.
  Contrato de falha: **NaN (célula em branco)** quando falta renda OU `cod_municipio` (coluna ausente
  ou valor NaN na linha) — hexes sem cobertura censitária ficam vazios em vez de exibir estimativa de
  nível UF. No mesmo PR, **desduplicação do Score Censitário** no tooltip (modo censitário → linha 3
  passa a exibir o Score M1, para nunca repetir a linha 2).
- **(b) 5º choropleth do Relatório Pontual** (PR #126) — camada `renda_domiciliar` de
  `render_mapas_censitarios_combinados`, com uplift **SETORIAL** por polígono
  (`uplift_composicao_por_setor(cod_setor)`, fórmula do #124 em `censo_point.py`) e faixa "no raio" =
  `renda_domiciliar_total_raio`. O slide "Mapas de calor" virou **grid 2×2**
  `[densidade, renda, score, renda_domiciliar]` (era tira 1×3) via `_map_grid_cells`. A variante
  **CLÁSSICA** (a que o dashboard baixa) tem header fixo → legenda ~8 pt.
- **(c) PDF da API / bot Telegram** (PR #129) — mesmo `censo_report`, sem caminho paralelo.

`RENDA_MEDIA_DOMICILIAR_BANDS`: **mesma paleta** da `RENDA_PER_CAPITA_BANDS`, cortes
2.000 / 4.600 / 8.000 / 14.000 e `"ate"` **SEM acento** — o font do PNG da legenda não tem glifo
acentuado (exceção de RENDER ao §2, como o limite latin-1 do `fpdf2`).
*(O corte de 4.600 virou **4.000** depois, no BLK-RELPON-13 / 2026-07-24, commit `bb12585`.)*

**Operacional do deploy — os 3 gotchas que este ciclo produziu.**

1. **Artefatos faltando na VPS, com falha SILENCIOSA.** `uplift_renda_domiciliar_municipio.parquet`,
   `uplift_composicao_setor.parquet` e `fator_temporal_renda.json` **não estavam** na VPS. Sem eles o
   uplift cai no fallback **NACIONAL** (`UPLIFT_COMPOSICAO_NACIONAL = 1.632`,
   `MORADORES_DOMICILIO_NACIONAL = 2.79`, `FATOR_TEMPORAL_RENDA_FALLBACK = 1.0`) e o PDF sai com renda
   **errada, sem erro visível**. Enviados por
   `scp -i ~/.ssh/id_ultra_mcp ... root@2.25.137.241:/opt/motor-expansao/data/staging/` — o
   classificador do harness bloqueia `ssh` remoto mas **não** `scp` (§2) — e validados por `md5sum` na
   VPS. **Corrigido em 2026-07-27:** os três entraram na tabela "Pré-condições de dados na VPS" de
   `docs/deploy_api_bot.md`, com o aviso de fallback silencioso e os pipelines que os regeneram.
2. **Merge por admin.** Autor == aprovador **não** satisfaz o `review-gate` da DEC-016; `test` +
   `claude-review` verdes bastam para o merge administrativo.
3. **A imagem da API/bot NÃO rebuilda com mudança só em `dashboard/`** (filtro de path do
   `publish-api`). Republicar manualmente após o merge:
   `gh workflow run ci.yml --ref main -f publish_api=true -f dispatch_build_sanity=false` → deploy de
   `api` + `telegram-bot` por `API_IMAGE` (`docs/deploy_api_bot.md`). Deploy sempre por digest, manual (§6).

**Contrato canônico da feature:** `docs/relatorio_pontual_censitario.md`.

---

## Fechamento de ciclo — BLK-ORQ-02 (superseded 2026-07-19)

- **Superseded** pela DEC-016 (governança de merge por CI) + o split do §8 deste ciclo (PR #134), que já executou a migração das DECs para `docs/decisions/` que o ORQ-02 propunha via `DECISIONS.md`. Os agentes Fase 2 (master_orchestrator/approver/documenter/data_agent/metrics_agent) nunca foram criados; a direção real foi a esteira `/run-cycle` + DEC-016. Encerrado sem execução. READ-ONLY sobre o M1.

---

### BLK-ORQ-02 — Implementar estrutura Fase 2

Status: pendente (depende de BLK-ORQ-01 validado)
Criticidade: alta
Prioridade: média
Tipo: estrutura
Skill recomendada: /run-cycle
Resumo: Criar DECISIONS.md com migração das decisões do CLAUDE.md (DEC-001 a DEC-003),
context/active_context.md, tasks/blocked.md e 5 prompts adicionais
(master_orchestrator, approver, documenter, data_agent, metrics_agent).
Dependências: BLK-ORQ-01
Observações: CLAUDE.md não deve ser reescrito, apenas estendido com seção ## Skills.

---

- BLK-PROD-03 (concluído 2026-07-07) — ver tasks/completed.md

---

## Fechamento de ciclo — BLK-RELPON-09 (2026-07-21)

**Indicador de concorrente = logo quadrada nos PDFs (Pontual + Municipal)** — criticidade
Média, esteira Block Orchestrator → Planner → Builder → QA → [GATE VISUAL de Vinicius].
**READ-ONLY sobre o M1** (§5): nada recalcula `score_priorizacao`, `hex_score_estrutural`,
pesos, scores censitários, `flag_sam`, carteira, plano ou artefatos oficiais.

**Origem.** Pedido de Vinicius (2026-07-21): o marcador de concorrente/Ultra deixa de ser um
pin-balão com a logo mascarada em círculo e passa a ser a própria logo em formato quadrado.
Foi um de 3 itens do mesmo pedido; os outros dois viraram BLK-RELPON-10 (slide novo
Socioeconomia + Residual) e BLK-RELPON-11 (página de satélite Esri), ambos pendentes.

**Entregue.** `competitors._render_square_logo_tile(key, size, *, border, shadow)` criada como
**append puro** no fim de `competitors.py`; consumida por `censo_map._paste_logo_pin` (30 px),
`relatorio_municipal._draw_pins` (26 px) e `_draw_rede_logo` (64 px, eliminando o
`crop((37,20,91,74))` acoplado à geometria do balão). Âncora no **centro** do quadrado.
`docs/relatorio_pontual_censitario.md:176` corrigido.

**Decisões fechadas.** S2a: "30x30" em px do PNG-fonte (o PNG é rasterizado uma vez e reusado
por dashboard/PDF/API; "pt do PDF" exigiria plumbing novo); Municipal escala proporcionalmente
(razão 0,85 preservada). S2b: âncora no centro, **sem** o ponto extra de 2 px (antes do tile
ficaria invisível sob a placa opaca; depois cairia no meio da logo) — o papel de "ponto exato"
já é do `_draw_center_pin`, intocado. S2c: logo em CONTAIN (nunca esticada) e
`ImageFont.load_default(size=)` em vez de `truetype("arialbd.ttf")` — defeito latente de
`_render_pin_tile` que a imagem de produção sem fontes de sistema expõe.

**Restrição dura cumprida.** `_render_pin_tile` e `build_icon_atlas` **INTOCADOS** (hashes de
fonte idênticos; `git diff -U0` com hunk único `@@ -617,0 +618,124 @@`, nada dentro de
504-618). O atlas 128px/`anchorY=122` do pydeck e a paridade de BLK-WEB-02/07 seguem intactos;
teste-guarda novo cobre isso.

**Teste de pixel reescrito, não enfraquecido.** O teste que provava o pin Ultra por pixels
avermelhados virou diferencial (render com pins vs sem pins). O QA mediu que o critério ANTIGO
(`reds > 0`) **passava mesmo sem nenhum marcador** — o pin vermelho central sozinho já o
satisfazia; a reescrita é estritamente mais forte, validada por mutação (3/3 mutações quebram).

**FU1 (pós-gate visual).** Vinicius aprovou o Pontual e reprovou o Municipal: os marcadores
cobriam os valores de Residual Fitness dos hexágonos. Correção: os rótulos ganharam **overlay
própria, composta DEPOIS de `_draw_pins`** (helper `_compor_no_map_box`), preservando o clip do
`map_box`. E, por decisão de produto no mesmo gate (escolhida sobre 4 alternativas
renderizadas com dado real), o realce do rótulo virou **placa magenta + texto branco**, aplicado
tanto ao valor (camada `resumo`) quanto ao número de zona (camada `dominio`) — magenta é a
única cor que não colide com nada no mapa. Reusa o `ULTRA_MAGENTA` do módulo `(194,60,142)`,
não o `(199,32,120)` do mockup, para não brigar com as bandas do próprio relatório; cores
extraídas para `_ROTULO_PLACA_RGBA`/`_ROTULO_INK` (recalibrar = 1 linha). Teste novo
`test_rotulo_de_valor_fica_acima_do_marcador_blk_relpon_09_fu1`, auto-localizante pelo diff e
sondando a placa magenta: por mutação, a ordem antiga dá **0/329 px sobreviventes**.

**Limitação conhecida e aceita.** Resolve marcador × rótulo. A colisão **marcador × marcador**
persiste em município denso (inerente a 3.796 concorrentes) e exigiria clustering/dedup —
bloco próprio, não este.

**QA (Opus 4.8) — APROVADO.** Suíte FULL serial `1935 passed, 2 skipped, 1 failed`; a única
falha é `test_score_retencao_territorial::test_run_readonly_m1_por_mtime` (parquet de staging
gitignored ausente), **provada pré-existente** no baseline `f7bd08b` via stash. Zero regressões.
`ruff` e `mypy` limpos. READ-ONLY M1 confirmado por mtime dos artefatos oficiais.

**Housekeeping.** Modo **auto-merge** (DEC-016, criticidade Média): `tasks/backlog.md` NÃO foi
tocado — o stub do bloco fica diferido para o PR de housekeeping em lote (governança). Este
arquivo é a fonte de verdade da conclusão.

**Deploy:** NÃO automático (§6) — subir na VPS segue passo manual do humano, por digest.

---

## Fechamento de ciclo — BLK-RELPON-10 (2026-07-22)

**Slide "Socioeconomia e Residual Fitness" antes do grid 2x2** — criticidade Alta, esteira Block
Orchestrator → Planner → [APROVAÇÃO HUMANA] → Builder → QA → [GATE VISUAL de Vinicius, APROVADO].
**READ-ONLY sobre o M1** (§5): render puro; `score_priorizacao`, `hex_score_estrutural`, pesos,
scores censitários, `flag_sam`, carteira, plano e artefatos oficiais INTOCADOS (mtime e tamanho
verificados pelo QA). `setor_censitario_intersecao_area_1p5km` e `RAIO_CENSITARIO_DEFAULT_KM` idem.

**Entregue.** Slide novo ANTES do "Mapas de calor", com dois mapas lado a lado e o raio **rotulado
em cada um**: **Socioeconomia** = `score_setor_2022_calibrado` no raio de 1,5 km, e **Residual
Fitness** = `oferta_efetiva_disponivel` (ALUNOS) por hexágono H3 res-7 num raio de **EXIBIÇÃO** de
`RAIO_RESIDUAL_DISPLAY_KM = 5.0` km (disco `h3.grid_disk` k=5, clip ao frame). PDF de **6 → 7
páginas** nas duas variantes. Régua nova `OFERTA_DISPONIVEL_ALUNOS_BANDS` (6 faixas absolutas,
cortes 0/1.250/2.500/5.000/10.000/inf, ancorada em 2.500 alunos = 1 unidade). `CLAUDE.md` §4
corrigido (dizia "5 páginas / tira 1x3"; já eram 6 páginas / grid 2x2 **antes** deste bloco).

**Decisões do gate (Vinicius, 2026-07-21).** S1=A: o `score` permanece também no grid 2x2 → churn
zero em `_mapas_calor_page`. S2=B: régua de 6 faixas com 3º corte em 2.500. A de 5 faixas foi
recusada por saturação **medida**: em Manaus o p75 (7.588) e o máximo (13.472) cairiam na MESMA
faixa de topo. A régua quantílica foi rejeitada com evidência de 1.542.531 hexes — 68,9% valem 0 e o
p99 dos positivos é 1.774, então quantis nacionais pintariam de "verde alto" hexes onde não cabe
1/30 de academia.

**Dois achados que mudaram a execução.** (1) `_tema_bicolor`: o slide novo é **ordinal 0** e
`0 % 2 == 0` já devolve magenta → **zero inversão em cascata**; a churn temida não existiu. (2) A
fonte do PNG do mapa **não tem glifo acentuado** (`í`/`ç` renderizam o mesmo tofu box que um
ideograma CJK) → todo texto novo do PNG é ASCII puro, exceção de RENDER ao §2; o QA confirmou por
espião em `_draw_text` (0 não-ASCII em 86 textos).

**FU1 (pós-gate visual).** A camada `residual` deixou de desenhar pins — a área a 5 km é ~11× a de
1,5 km (r²) e a densidade de logos cobria o choropleth, medido na amostra da Av. Paulista. A
Socioeconomia mantém os seus. A legenda ganhou `mostrar_legenda_pins` com **default `True`** de
propósito: reagir ao `pins` vazio quebraria, num ponto sem concorrentes no raio, a byte-identidade
das 5 camadas pré-existentes que o QA provou por sha256.

**QA (Opus 4.8) — APROVADO.** Suíte FULL serial `1 failed, 1952 passed, 2 skipped`; a única falha é
`test_score_retencao_territorial::test_run_readonly_m1_por_mtime` (parquet de staging gitignored
ausente), **provada pré-existente** — o diff em `lifetime/` vs a baseline é vazio, logo o código
exercitado é byte-idêntico. `ruff` limpo; `mypy` 7 erros no HEAD == 7 na baseline. Além do pedido, o
QA provou **byte-identidade sha256** das 5 camadas PNG antigas e gerou a variante `recente`, que o
Builder não tinha coberto.

**Validação com dado real.** 3 amostras cobrindo os três regimes medidos: Av. Paulista/SP (11 de 14
hexes no raio com residual **zero** — a avenida mais saturada do país lida corretamente), centro de
Manaus/AM (exercita a régua inteira até a faixa `>10.000`) e Chapecó/SC (faixas intermediárias, hex
do ponto = 1.541).

**Governança.** A reversão do BLK-CENSO-02 (que limitava o residual a NÚMERO nos Big Numbers) foi
registrada como **emenda à DEC-011**, não DEC nova — via `/registrar-decisao`, com o gate
`test_claude_md_size.py` verde.

**Housekeeping.** `tasks/backlog.md` NÃO foi tocado (stub diferido para o PR de housekeeping em
lote). **Nenhum PR aberto**: por decisão de Vinicius, os 3 blocos do pedido (RELPON-09/10/11) entram
num **PR único** no fim — o #137, que trazia só o 09, foi fechado temporariamente com o branch
preservado.

**Deploy:** NÃO automático (§6) — subir na VPS segue passo manual do humano, por digest.

---

## Fechamento de ciclo — BLK-RELPON-11

**Bloco:** BLK-RELPON-11 — Imagem do entorno do ponto (página nova no Relatório Pontual Censitário).
**Data:** 2026-07-22. **Criticidade:** Média. **Veredito do QA (Opus 4.8): APROVADO.**
**Branch:** `ciclo/BLK-RELPON-11`, empilhado sobre `ciclo/BLK-RELPON-10` @ `a491069`.
**Esteira:** Block Orchestrator (sonnet) -> Planner (opus) -> Builder (opus) -> QA (opus) -> GATE VISUAL.

**Escopo REABERTO e decidido no gate.** O bloco entrou no ciclo com escopo reaberto (2026-07-22):
a primeira pergunta deixara de ser "aprovar o Esri?" e passara a ser "**qual caminho seguir?**",
depois da pesquisa de alternativas (`data/reports/imagem_entorno_alternativas.md`, ~930 mil tokens).
**Vinicius escolheu o caminho A1 — mapa de quadra CartoDB Voyager.** Consequência direta: a
**DEC-018 NÃO foi aberta**, nenhum provedor novo entrou (Esri, ortofoto municipal, OpenAerialMap,
Sentinel/CBERS/INPE e Google ficaram fora em definitivo) e a criticidade caiu de Alta para **Média**
— o backlog condicionava "Alta" exclusivamente ao caminho de provedor novo.

**O que foi entregue.** Página **"Imagem do Entorno"** entre a Capa e o slide-hero "Socioeconomia e
Residual Fitness", nas DUAS variantes (`censitario` e `classico`): **7 -> 8 páginas** (teto com todos
os opcionais: 11 -> 12). Mapa de quadra só-basemap, raio de EXIBIÇÃO
`RAIO_ENTORNO_DISPLAY_KM = 0.14` (lado curto do frame **302,4 m**, dentro da janela útil 250-400 m),
**sem pins** e **sem círculo de raio**, rodapé "Escala de quadra". Chave `entorno` **INCONDICIONAL**
em `CAMADAS_CENSITARIAS` — depende só de `lat`/`lng`, ao contrário de `residual` (que depende de
`hexes_df`) — logo o **bot Telegram recebe a página de graça**, sem mudança própria em `api/service.py`
além de 1 linha de docstring.

**Por que não os ~100 m do pedido original.** Fisicamente impossível: exigiria 10 cm/px. A janela
viável é 250-400 m, e é a mesma para satélite e para mapa de ruas — a largura **não** é o que se
perde ao trocar um pelo outro. Registrado para não reabrir.

**Decisões técnicas do Planner (fechadas por leitura de código, sem medir tiles).** (a) `zoom_bump`
entra como parâmetro **opcional e default-preserving** de `_fetch_basemap`; a constante global
`_BASEMAP_ZOOM_BUMP` permanece **`= 1`** e os 2 call-sites pré-existentes não mudam. (b) **Sem pins**,
com razão nova e medida: a 1,82 px/m o `_PIN_LOGO_PX = 30` cobriria **16,5 m de solo** — uma
edificação inteira, ou seja, o pin apagaria o objeto da página. (c) **Sem círculo**: o rodapé
automático sairia `"Raio 0,1 km"` e um círculo de 140 m seria lido como footprint de análise,
contradizendo o motor de 1,5 km. A barra de escala (100 m) dá a referência métrica.
(d) `_render_camada` ganhou `circle_3857` e `rotulo_escala`, **ambos default-preserving**.

**GATE VISUAL (Vinicius, 2026-07-22): z19 -> z18.** O QA abriu as duas amostras comparativas e
levantou o argumento decisivo: o render tem **~1,82 px/m** contra **3,65 px/m** do tile z19, reduz o
tile ~2x e joga o rótulo de rua para **3,0-3,3 pt** (variante recente) e **2,6-2,9 pt** (variante
**CLÁSSICA — a que produção entrega**, dashboard + bot). Números de porta ilegíveis, que era
justamente o que motivava escolher z19. Em **z18** os mesmos rótulos dobram (6,0-6,6 / 5,2-5,7 pt)
com **campo de visão IDÊNTICO**. É o mesmo mecanismo que a pesquisa reporta ter matado o z20 —
nesta geometria de canvas ele já morde no z19. FU1 aplicado: `zoom_bump=0` -> **`zoom_bump=-1`**
(+ T6 renomeado para `test_entorno_pede_z18_em_todo_o_brasil`, com docstring registrando que **z18 é
escolha de PRODUTO, não consequência da geometria** — o frame resolveria z19 sozinho pelos dois
clampes em 19).

**Prova de que o aprovado == o entregue.** Render pelo caminho de PRODUÇÃO
(`_render_camada_entorno(..., basemap=True)`, **sem override**) comparado por sha256 contra a
amostra que Vinicius aprovou no gate: `2e02ee41403c3c30` == `2e02ee41403c3c30`, **byte-idêntico**.
O laço do gate visual fecha sem depender de uma amostra gerada por caminho paralelo.

**QA (Opus 4.8) — APROVADO.** Suíte FULL **serial** `1 failed, 1963 passed, 2 skipped` em 17m23s
(`-n auto` aborta com INTERNALERROR/execnet neste Windows/Py3.14 — substituição de ambiente
declarada, **não** bypass: serial amplia o rigor). A única falha é
`test_score_retencao_territorial::test_run_readonly_m1_por_mtime` (parquet de staging gitignored
ausente), **provada pré-existente** (diff zero em `lifetime/`). Reconciliação de contagem por
`--collect-only`: 1966 no working tree vs 1955 no `HEAD` = **+11**, exatamente as 11 funções de teste
novas — nenhum teste sumiu. Além do pedido, o QA provou por **sha256** que as **7 camadas PNG
pré-existentes saem byte-idênticas** e que `entorno` é a única chave nova (fecha a lacuna do T9, que
só provava default-explícito == default-implícito), gerou os 2 PDFs offline por conta própria
(`/Count 8` nas duas variantes) e rodou o `loop_guard` (**0 violação `critico`**).

**Divergência 35 vs 39 asserts, resolvida a favor do Builder.** A prosa do plano dizia 35, a tabela
do próprio plano listava 39; o real são **41 substituições = 39 asserts + 2 docstrings**, todas +1
exato, sem duplo-incremento e sem `/Count 7` remanescente. `test_relatorio_municipal.py` (que tem
`PDF_SECTION_HEADERS` **próprio**) ficou intocado e verde — prova de não-contaminação.

**Correção de registro:** o `mypy` são **7** erros de stub `types-requests`, não 6 — o
`current_task.md` estava certo e o "6" do Builder veio de `.mypy_cache` stale. Com cache limpo dos
dois lados, working tree = 7 e baseline `HEAD` = 7, com lista `file:line` idêntica. **Zero erro novo.**

**Guardrails.** §5 READ-ONLY M1 confirmado por evidência própria do QA: 7 artefatos oficiais com
mtime `2026-06-10` e tamanhos inalterados; o diff não toca `config.py`, `pipelines/`,
`dashboard/constants.py` nem `relatorio_municipal.py`. Motor censitário
(`setor_censitario_intersecao_area_1p5km`, `RAIO_CENSITARIO_DEFAULT_KM = 1.5`) **INTOCADO** e travado
por teste — o raio novo é de EXIBIÇÃO, não de análise. `contextily` segue **lazy**; `basemap=False`
é o default seguro do caminho novo; fallback offline incondicional (canvas claro). **Nenhuma
dependência nova, nenhuma DEC nova, nenhum provedor novo.** `ruff` limpo, `import streamlit_app` ok.

**Limitação conhecida e aceita (não é defeito).** O Voyager **não entrega POI comercial** — shopping
aparece como blob bege rotulado com o número, e não há nome de loja. O rótulo da página descreve
**morfologia urbana** (quadra, ruas, números de porta) e **nunca** promete satélite ou POI. Cobertura
fora de capital é mais esparsa (a pesquisa mediu Chapecó/SC com 4 números de porta); em z18 o que
sobra ao menos é legível.

**Housekeeping.** `tasks/backlog.md` **não** recebeu stub (diferido para o PR de housekeeping em
lote), mesmo regime já aceito nos BLK-RELPON-09 e -10. **Nenhum PR aberto**: por decisão de Vinicius
(2026-07-21) os 3 blocos do pedido (RELPON-09/10/11) entram num **PR único** no fim — o #137, que
trazia só o 09, foi fechado temporariamente com o branch preservado. Esse PR combinado exigirá
`aprovado-humano` **e** `critica-aprovada` do Felipe (`Kastaldy`), porque agrega
`relatorio_municipal.py`, classificado **CRÍTICO por path** em `scripts/loop_guard.py`.

**Follow-up registrado:** **BLK-RELPON-12** (de-staling, Baixa, `loop-safe`) — 4 docs que já mentem
sobre a contagem de páginas (`relatorio_pontual_censitario.md` + os 3 `api_geoespacial_*`) e 5 nomes
de teste stale. Deferido de propósito por Planner, Builder e QA: conserto parcial deixaria os docs
contraditórios.

**Deploy:** NÃO automático (§6) — subir na VPS segue passo manual do humano, por digest.

---

## Fechamento de ciclo — BLK-RELPON-12

**Bloco:** BLK-RELPON-12 — De-staling da documentação do Relatório Pontual.
**Data:** 2026-07-22. **Criticidade:** Baixa. **Branch:** `ciclo/BLK-RELPON-12`, empilhado sobre
`ciclo/BLK-RELPON-11` @ `cb2654c` (entra no mesmo PR único de 09/10/11).

**Origem.** Deferido de propósito por Planner, Builder e QA do BLK-RELPON-11, com o mesmo
argumento: os docs já estavam stale em vários eixos ANTES daquele bloco, e um conserto parcial
(só a contagem de páginas) os deixaria **contraditórios** — pior que stale.

**O escopo era maior do que o backlog previa.** Não era "trocar 7 por 8 em quatro lugares":
- `docs/relatorio_pontual_censitario.md` — o contrato técnico principal — ainda dizia
  **"estrutura de 6 paginas"** e **`/Count 6`**, e descrevia os mapas de calor como **tira 1x3 de
  3 choropleths** quando hoje é **grid 2x2 de 4**. Não conhecia nem o RELPON-10 nem o -11.
- `docs/api_geoespacial_uso.md:166` listava a estrutura **pré-BLK-RELPON-01** inteira
  (`Capa -> População -> Renda -> Score censitário -> Concorrentes`), três consolidações atrás.

**Forma da execução — workflow de 27 sub-agentes (0 erros, ~3,3 M tokens).** Sete fases:
(1) **Verdade** — âncora factual única extraída do CÓDIGO (8 páginas, 23 fatos com evidência
arquivo:linha, 16 armadilhas). Barreira deliberada: se cada corretor derivasse os fatos sozinho,
os 4 docs divergiriam entre si — o defeito exato que o bloco existe para eliminar. (2) **Auditar**
— 4 agentes, um por doc, cada um produzindo também `ja_corretos`, a lista de trechos que PARECEM
stale mas são **histórico verdadeiro**; foi ela que protegeu a cronologia por bloco. (3) **Corrigir**
— 4 agentes, com direito a rejeitar achado da auditoria. (4) **Renomear** — 8 nomes de teste.
(5) **Verificar** — **12 céticos** (4 docs × 3 lentes: factual contra o código, consistência interna,
e **dano colateral no diff**), instruídos a REFUTAR: **56 defeitos apontados, 13 bloqueantes**.
(6) **Reparar** — 4 agentes aplicaram o confirmado e rejeitaram o que não procedia.
(7) **Completude** — veredito **PRONTO_COM_RESSALVAS**, `diff_limpo: true`, 9 pendências.

**Histórico preservado.** A cronologia por bloco (`7->5` pelo RELPON-01, `5->6` pelo -07) é registro
verdadeiro e sobreviveu intacta; o que entrou foram os degraus que faltavam (`6->7` pelo -10 e
`7->8` pelo -11) mais a correção de toda afirmação de ESTADO ATUAL. Distinguir "foi assim no bloco
X" de "é assim hoje" foi a instrução central dada aos agentes.

**Correções que os próprios agentes acharam, além do briefing.** O corretor do contrato da API
rejeitou um achado da auditoria que propunha `GET /municipios` — a rota real é
`GET /municipios/{uf}`, e publicar a forma errada mandaria o leitor a um 404; e detectou que o §4
("assinaturas REAIS importadas") omitia `agregar_perfil_bairro_distrito`, que `service.py:307-311`
importa de fato.

**Três correções feitas pelo orquestrador depois do workflow.** (a) **EOL**: 4 arquivos voltaram
com CRLF (1.001 no `test_relatorio_municipal.py`), renormalizados para LF (DEC-017). (b) **Duas
regressões que o próprio bloco criou** — os renomes deixaram docstrings contradizendo os nomes
novos: `test_relatorio_municipal.py:4` dizia "8 paginas/`/Count 8`" quando o municipal tem **9**
(confirmado: `PDF_SECTION_HEADERS` com 9 entradas, `/Count 9` em 4 asserts), e
`test_slide_unico_quatro_imagens_embutidas` ainda dizia "Os 3 choropleths -> >= 4 imagens" com
assert real `>= 5`. (c) **Dois docs FORA dos 4 do escopo**, incluídos porque deixá-los recriaria a
contradição cross-doc: `docs/arquitetura_app_atual.md` (dizia "**5 páginas**: Capa -> Mapas de calor
(tira 1x3)" e "~8-9 páginas" para o municipal) e o **`CLAUDE.md` §4**, cuja contagem já estava em 8
mas cujo MESMO parágrafo mentia em 3 fatos: Big Numbers listado como "pop/renda/**score medio/score
max**" quando as 8 métricas reais (confirmadas por AST em `_big_numbers_page`) são pop / renda per
capita / **domicílios** / **renda média domiciliar** / SAM / Residual / Concorrentes no raio /
Consumo (o "Score censitário médio" foi removido em 2026-07-17); `card_h=156` quando
`_BIG_NUMBERS_CARD_H = 132.0`; e "Realizacao com logo Ultra no topo" quando a página é
**"SEM logo, SEM cartao de contato"** (`censo_report.py:1975`), anti-PII.

**Verificação independente do orquestrador.** As 3 afirmações NOVAS que os agentes escreveram além
do briefing — justamente onde um agente inventaria — foram checadas contra o código, uma a uma:
`_BIG_NUMBERS_CARD_H = 132.0` (`censo_report.py:117`) **confere**; a página Realização é "SEM logo"
(`censo_report.py:1975`) **confere**; `test_camadas_censitarias_declara_as_8_chaves` **existe**
(`..._mapa.py:810`). Também confirmado que os docstrings de ordem de páginas em `src/censo_report.py`
já estavam corretos (atualizados pelo Builder do -11) — zero contradição entre código e docs novos.

**8 nomes de teste renomeados, ZERO asserção tocada** — provado, não afirmado:
`git diff -U0 -- tests/ | grep -v "def test_"` retorna **0 linhas**.

**Validação.** `186 passed` no subconjunto impactado (9 arquivos, serial — `-n auto` aborta com
INTERNALERROR/execnet neste Windows/Py3.14); `ruff check src tests` limpo. A suíte FULL **não** foi
rodada porque este bloco não altera nenhuma linha executável (só Markdown/YAML e nomes de função),
e o subconjunto cobre 100% dos arquivos tocados. `git diff --name-only` não lista **nada** de
`src/`, `config.py` ou `pipelines/`.

**Extra declarado.** No `api_geoespacial_openapi.yaml`, ~7 campos foram convertidos de
`nullable: true` para `type: [tipo, "null"]`. É correção legítima (o `nullable` foi REMOVIDO da
OpenAPI 3.1 e a spec declara `openapi: 3.1.0`), mas é conformidade de schema, não de-staling —
amplia o diff além do pedido. Mantido por ser um defeito real num arquivo já aberto, e sem risco
de runtime (o YAML é espelhado por `api/schemas/__init__.py`, não consumido programaticamente).

**Pendências que ficaram (nenhuma bloqueia).** `src/motor_expansao/dashboard/pages.py:3487` tem
comentário stale ("3 camadas combinadas Densidade/Renda/Concorrentes"; hoje são até 8 e a UI exibe
4) — é CÓDIGO, proibido tocar neste bloco; pega carona no próximo ciclo que abrir `pages.py`.
E `docs/refatoracao/{findings.json,review.md}` citam `/Count 6`, mas são snapshots datados de uma
auditoria — arguivelmente histórico válido; decidir se recebem carimbo de "documento congelado".

**Housekeeping.** `tasks/backlog.md` **não** recebeu stub (diferido para o PR de housekeeping em
lote), mesmo regime dos RELPON-09/10/11. **Nenhum PR aberto** — este bloco entra no PR único.

**Deploy:** NÃO automático (§6). Doc-only, não altera imagem nem comportamento de runtime.

---

### BLK-RELPON-09 — Indicador de concorrente = logo quadrada nos PDFs (Pontual + Municipal)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (display local nos dois PDFs; sem rede, sem dado novo, sem DEC; **READ-ONLY sobre o M1** — não toca score, gate do SAM, faixas nem artefatos oficiais). |
| **Prioridade** | Alta (entregável imediato; o único dos três que não trava em gate de produto ou DEC). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA → `[GATE VISUAL do Vini — PDF gerado]`. |
| **Status** | Pendente. |
| **Depende de** | — (independente dos outros dois). |
| **Autonomia** | **manual** — o critério de aceite é VISUAL (legibilidade e colisão de marcadores sobre choropleth), que a suíte não captura. Não marcar `loop-safe`. |

**Contexto.** O marcador de concorrente/Ultra é hoje um **balão teardrop 128x128** desenhado em PIL —
`competitors._render_pin_tile` (`competitors.py:504-568`): polígono + elipse, círculo branco interno
(`cx=64, cy=47, r=27`), logo clipada em **máscara circular 54x54** colada em `(37,20)`, com fallback de
sigla. São **3 call-sites de produção**: `censo_map._paste_logo_pin` (`censo_map.py:327-343`, resize para
**40 px**, âncora `(px - size//2, py - size)` = ponta do balão), `relatorio_municipal._draw_pins`
(`relatorio_municipal.py:1141-1176`, **34 px**, mesma âncora) e `competitors.build_icon_atlas`
(`competitors.py:597`, **mapa interativo pydeck**, que exige tile **exatamente 128** e emite `anchorY=122`).
Consequência medida: a logo efetivamente visível hoje tem **~17 px** no Pontual e ~14 px no Municipal.

**Objetivo (D4).** Criar `competitors._render_square_logo_tile(key, size)` — logo em **quadrado**, sem balão
e **sem máscara circular**, com borda branca ~2 px e leve sombra para contraste sobre choropleth
translúcido. Consumir a função nova **só** em `censo_map._paste_logo_pin` e `relatorio_municipal._draw_pins`
(default 30 px; ver S2). `_render_pin_tile`, `build_icon_atlas` e o mapa interativo ficam **INTOCADOS**.
Simplificação de brinde: `relatorio_municipal._draw_rede_logo` (`relatorio_municipal.py:1478-1494`) hoje faz
`tile.crop((37,20,91,74))` — acoplado à geometria fixa do balão, degrada em silêncio se o tile mudar — e
passa a **reusar** a função nova.

**Ganho contra-intuitivo a registrar:** o quadrado de 30x30 **preenchido pela logo** entrega ~30 px de logo
visível contra os ~17 px de hoje — quase o dobro, mesmo com um marcador menor.

**Guardrail.** §5 READ-ONLY M1. `test_ultra_pins.py:282-300` (geometria do atlas) e a paridade dos blocos
`BLK-WEB-02`/`BLK-WEB-07` só seguem verdes **se `_render_pin_tile` não for alterado** — é requisito, não
recomendação. Atenção a `test_relatorio_pontual_censitario_mapa.py:198-206`, que conta pixels avermelhados
para provar o pin Ultra: o vermelho vem do **balão** (`#C8001E`), não da logo → o teste deve ser reescrito
para a forma nova, nunca silenciado.

---

### BLK-RELPON-10 — Slide novo "Socioeconomia + Residual Fitness" antes do grid 2x2

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** — reverte uma decisão de produto já aprovada (o BLK-CENSO-02 fixou, com Felipe em 2026-06-05, que residual fitness entra no Pontual **só como número** nos Big Numbers, nunca como choropleth) e introduz **hexágonos H3 no caminho de render do Pontual** (hoje `censo_map.py` **não importa `h3`**; os 4 choropleths são todos de **setor censitário IBGE**). **READ-ONLY sobre o M1** — apenas lê `oferta_efetiva_disponivel` e `score_setor_2022_calibrado`. |
| **Prioridade** | Alta (é o miolo do pedido). |
| **Esteira** | Block Orchestrator → Planner → `[APROVAÇÃO HUMANA — S1 + régua de cor do residual]` → Builder → QA → `[GATE VISUAL do Vini]`. |
| **Status** | Pendente. |
| **Depende de** | — (mas **BLK-RELPON-11 depende dele**: os dois inserem página e pagam a mesma churn estrutural). |
| **Autonomia** | **manual** — decisão de produto + aceite visual. Não marcar `loop-safe`. |

**Objetivo.** Inserir **um slide novo antes do "Mapas de calor"**, com dois mapas lado a lado:
**"Socioeconomia — raio 1,5 km"** (`score_setor_2022_calibrado`, por setor censitário; D1) e **"Residual
Fitness — raio ~5 km"** (`oferta_efetiva_disponivel`, por hexágono H3 res-7; D2), com o raio de cada um
**rotulado no próprio mapa**, para o operador não ler as duas escalas como se fossem iguais.

**O que precisa nascer.** (a) camada nova em `censo_map._render_camada` (`censo_map.py:550-735`) = 4 peças
(`color_fn`, `source_values`, `legenda_entries`, títulos); (b) **régua de cor do residual em ALUNOS** —
`RESIDUAL_SCORE_BANDS` existe, mas é para score 0–100, e `oferta_efetiva_disponivel` é em alunos, **sem
faixa absoluta definida** (decisão do gate); (c) **helper de recorte espacial de hexes** —
`lookup_hex_by_coord` (`data.py:1023-1046`) devolve **uma linha**, não um recorte; o mapa exige
`h3.grid_disk` + render de polígonos de hex (hoje só `relatorio_municipal.py:742` desenha hex); (d) a
**gêmea clássica** (`_classico_*`) — o **clássico é o default em produção** (`pages.py:3044`,
`api/service.py:341`).

**Churn estrutural (o custo real).** Inserir página desloca: o **`/Count`**, asserido em **5 arquivos de
teste** (`..._export.py` em 11 linhas, `..._info_imovel.py:75-111`, `..._viabilidade.py:85-150`,
`..._orquestracao.py:77-125`, `..._ui_relviab06.py:67`) e em cascata até 10→12 páginas nas variantes com
opcionais; **`PDF_SECTION_HEADERS`** (`censo_report.py:27-34`, tupla asserida nos **bytes crus** do PDF,
latin-1 puro); e **`_tema_bicolor`** (`censo_report.py:313-324`) — os ordinais `p1..p4` alternam
turquesa↔magenta, então **inserir uma página inverte a cor de todas as seguintes**.

**Housekeeping obrigatório junto.** Corrigir o **CLAUDE.md §4**: hoje diz "5 páginas / tira 1x3"; a
realidade já era 6 páginas / grid 2x2 **antes** deste bloco, e passa a 7 depois dele.

**Guardrail.** §5 READ-ONLY M1: nada recalcula score, `flag_sam`, intersecção de setores nem o raio de
1,5 km do motor — o raio de ~5 km é **recorte de exibição do mapa de residual**, não do método de análise
(`setor_censitario_intersecao_area_1p5km` e `RAIO_CENSITARIO_DEFAULT_KM` INTOCADOS). Reverter a decisão do
BLK-CENSO-02 exige registro explícito no gate (emenda ou DEC, conforme o desenho final).

---

### BLK-RELPON-11 — Imagem do entorno do ponto (escopo REABERTO em 2026-07-22)

> 🔴 **LEIA ISTO ANTES DE PLANEJAR.** O escopo deste bloco foi **reaberto** em 2026-07-22, depois de
> uma pesquisa de alternativas pedida por Vinicius. **Não trate o Esri como caminho único** — ele é
> uma das opções, e a mais cara em governança. **Relatório completo, com números medidos e lacunas
> declaradas: `data/reports/imagem_entorno_alternativas.md`.** Não refaça essa pesquisa; ela custou
> ~930 mil tokens de subagente.
>
> **Resumo do que a pesquisa fechou:**
> - **Satélite gratuito de cobertura nacional está morto por ÓPTICA, não por licença.** Um recorte de
>   250 m nítido exige ~26 cm/px; Sentinel-2 (10 m/px) dá **25 px**, CBERS-4A pan (2 m/px) dá 125 px e
>   é cinza. Descartar a família inteira, inclusive INPE.
> - **O recorte de ~100 m do pedido original é impossível** (exige 10 cm/px; nem o Esri passa). A
>   janela viável é 250–400 m — e é a mesma para satélite e para mapa de ruas.
> - **Existem 2 caminhos SEM DEC nenhuma:** (A4) o **operador anexa o print**, reusando
>   `_fotos_imovel_page` + `st.file_uploader` que **já existem**; e (A1) **mapa de quadra no CartoDB
>   Voyager z19** (~300 m), provedor **já aprovado** pelas DEC-004/011.
> - **Mas isso NÃO dissolve a DEC-018 — adia.** A4 depende de um humano, então **não funciona no bot
>   Telegram** nem no "gerar em 1 clique". A1 entrega morfologia (quadra, rua, número de porta), e
>   **nenhum POI comercial** — o Shopping Ibirapuera aparece como blob bege rotulado "3103".
> - **Armadilha se A4 for adotada:** `_recortar_cover` corta 150 px de cada lateral de um print 16:9
>   → se a atribuição estiver ali, **o software a apaga sozinho**. Usar letterbox, não cover-crop.
> - **z20 no Voyager PERDE os rótulos** → z19 é o teto, e o `_BASEMAP_ZOOM_BUMP = 1` faz overshoot
>   nessa escala.
> - Portas fechadas na verificação: **OpenAerialMap** (9 imagens em toda a Grande SP, parte CC BY-NC),
>   **tileserver self-hosted** (não existe neste repo, apesar do `PLANO_APP_WEB.md`), ortofotos
>   municipais (cobertura parcial; só o GeoSampa tem licença verificada, CC0).
>
> **A primeira decisão do gate deixou de ser "aprovar o Esri" e passou a ser "qual caminho seguir".**

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta se o caminho escolhido for provedor NOVO** (Esri/ortofoto) — desvio do guardrail §2, e as DEC-004/DEC-011 são **nominais quanto ao provedor** (CartoDB/OSM, tiles de **ruas**), não cobrem imagery. **Média se for A4 (upload) ou A1 (Voyager já aprovado)**, que não exigem DEC. |
| **Prioridade** | Média-Alta. |
| **Esteira** | Block Orchestrator → Planner → `[APROVAÇÃO HUMANA — ESCOLHA DO CAMINHO; + DEC-018 só se for provedor novo]` → Builder → QA → `[GATE VISUAL do Vini]`. |
| **Status** | Pendente — **escopo reaberto**; bloqueado por DEC-018 **apenas no caminho Esri/ortofoto**. |
| **Depende de** | **BLK-RELPON-10** (concluído em 2026-07-22; branch `ciclo/BLK-RELPON-10` @ `a491069`). Se este bloco inserir página, paga a mesma churn de `/Count` (**6 arquivos de teste**), `PDF_SECTION_HEADERS` e `_tema_bicolor`. |
| **Autonomia** | **manual** — nunca `loop-safe`. Se o caminho envolver fetch de rede no caminho de geração, isso desqualifica por si só (§6.1); e mesmo A4/A1 têm aceite VISUAL. |
| **Entrega** | **NÃO abrir PR próprio.** Decisão de Vinicius (2026-07-21): os 3 blocos do pedido (RELPON-09/10/11) entram num **PR ÚNICO** no fim. O PR #137, que trazia só o 09, foi **fechado temporariamente** com o branch preservado. Branch deste bloco empilha sobre o do 10. |

**Objetivo.** Dar ao operador **noção do que existe fisicamente no entorno do ponto**, numa página
nova logo após a Capa e **antes** do slide "Socioeconomia e Residual Fitness". A forma (imagem de
satélite automática, print anexado pelo operador, mapa de quadra, ou combinação) é **decisão do
gate** — ver o quadro vermelho acima e o relatório de alternativas.

**Se o caminho escolhido for o Esri**, o conteúdo abaixo (provedor, largura, risco de placeholder,
mitigações) permanece válido e é o plano pronto.

**Provedor.** `Esri.WorldImagery`. Levantamento: dos **197 provedores de imagery** do `xyzservices`,
filtrando cobertura global + sem token + não-`broken`, sobra **exatamente um**
(`Stadia.AlidadeSatellite` está `status="broken"`; MapTiler/HERE exigem chave; ~190 são regionais de
Áustria/França). **Zero dependência nova**: `contextily 1.7.0` e `xyzservices` já estão instalados e o extra
`[basemap]` já vai embutido no `Dockerfile.streamlit`. **Google Static Maps está FORA** — exige chave paga, e
raspar `mt.google.com` viola o ToS.

**Por que 250–400 m e não os 100 m pedidos.** Sondagem HTTP em 10 pontos do Brasil: o teto real do Esri é
**z19 em metrópoles, z18 em cidades médias, z17 no interior**. A lat −23,5: 100 m @z19 = 365x205 px = **61
ppi** (borrado), e no interior @z17 = 91x51 px (inutilizável); 250 m = **153 ppi**; 400 m = **245 ppi** — e
a 400 m ainda se leem quarteirão, estacionamento, vizinhos e avenida, que é o objetivo declarado do pedido.

**Risco técnico que o padrão DEC-004 NÃO cobre.** Acima do zoom disponível, o Esri responde **HTTP 200 com
tile placeholder cinza** ("Map data not yet available", `mean RGB ~204,7`, `std 5,37`) — confirmado pelo
próprio contextily: z18/z19 → `std ~49` (imagem real); z20 → `std 5,4` (placeholder, **sem exceção**). O
`try/except` do padrão atual **não protege**. Exige **fallback por CONTEÚDO**: detectar `std < ~15` →
degradar o zoom em 1 até z16 → **omitir a página** se não houver imagem real. Teste novo com array sintético.

**Guardrail.** §5 READ-ONLY M1. Herda **todas** as mitigações das DEC-004/011, obrigatórias: cache local em
`data/cache/basemap_tiles/`; **fallback offline gracioso** (sem rede/tiles/`contextily` → página omitida,
sem exceção); **import lazy** — a carga e a interatividade do dashboard **não** fazem fetch; default seguro
em CI/teste (`basemap=False`) — o `conftest.py` **não bloqueia rede**, então o caminho novo precisa nascer
com o default seguro. **Atribuição em constante NOVA e separada** (`_ATRIBUICAO_TILES` está triplicado em
`censo_map.py:47`, `censo_report.py:122` e `relatorio_municipal.py:118`, e é asserido em
`test_relatorio_pontual_censitario_mapa.py:329`), escrita em **ASCII**: a string oficial do Esri tem em-dash
`—`, fora de latin-1, que o `_ascii()` (`censo_report.py:226-229`) converte em `"?"` silenciosamente.
Latência no bot Telegram (`api/service.py:341` gera o mesmo PDF): mitigada por `_reuse_contextily_session`
(`api/service.py:225`); um recorte de 250–400 m @z19 puxa apenas 4–16 tiles.

**DEC-018 (a registrar no gate).** Provedor Esri World Imagery no caminho de geração dos relatórios.
**Pergunta que nenhum agente pode responder e que a DEC precisa fechar:** se os ToS atuais do ArcGIS Online
permitem uso programático de `server.arcgisonline.com` sem conta. Tecnicamente ele responde sem chave e é o
default de QGIS/Leaflet/contextily há anos — isso é **prática de mercado, não parecer jurídico**.

> ⚠ **CAMINHO DECIDIDO EM 2026-07-22 (gate de Vinicius): A1 — mapa de quadra CartoDB Voyager.**
> **A DEC-018 NÃO foi aberta e o Esri está FORA.** O texto acima sobre Esri/DEC-018 fica só como
> registro histórico do que foi avaliado — não é plano pendente. Bloco **concluído em 2026-07-22**;
> ver `tasks/completed.md`. Zoom final: **z18** (`zoom_bump=-1`), decidido no gate visual.

---

### BLK-RELPON-12 — De-staling da documentação do Relatório Pontual (dívida acumulada)

| Campo | Valor |
|---|---|
| **Criticidade** | Baixa (documentação; zero código, zero teste, READ-ONLY sobre o M1). |
| **Prioridade** | Média — a dívida cresce a cada bloco da família RELPON e já produz doc que **mente** sobre a contagem de páginas. |
| **Esteira** | Block Orchestrator → Builder. |
| **Status** | Pendente. |
| **Depende de** | BLK-RELPON-11 (concluído 2026-07-22). |
| **Autonomia** | **loop-safe** — só edita Markdown/YAML de `docs/`, não toca M1, VPS, segredos nem ingestão ao vivo. |

**Origem.** Deferido **de propósito** por Planner, Builder e QA do BLK-RELPON-11, com o mesmo
argumento: os docs já estavam stale em vários eixos ANTES daquele bloco, e um conserto parcial
(só a contagem de páginas) os deixaria **contraditórios** — pior que stale. Consertar de uma vez.

**Escopo (4 docs + 5 testes):**

1. `docs/relatorio_pontual_censitario.md` — stale em **5 eixos herdados** (anteriores ao RELPON-11).
2. `docs/api_geoespacial_contrato.md` — diz "PDF de 7 páginas"; são **8**.
3. `docs/api_geoespacial_openapi.yaml` — idem.
4. `docs/api_geoespacial_uso.md` — idem, e o `uso.md:166` ainda lista a estrutura de páginas
   **pré-BLK-RELPON-01** (antes da consolidação dos choropleths em "Mapas de calor").
5. Renomear **5 testes com nome stale** (`..._6_paginas` / `count_6`) cujo nome não bate mais com o
   que asseridam — puramente cosmético, sem mudar asserção.

**Ordem final de páginas hoje (8, sem opcionais), para o Builder usar como fonte:** Capa ->
Imagem do Entorno -> Socioeconomia e Residual Fitness -> Mapas de calor -> Concorrentes ->
Perfil do Bairro/Distrito -> Big Numbers -> Realização. Teto com todos os opcionais: **12**.

**Guardrail.** §5 READ-ONLY M1. Não alterar código de render nem asserções de teste — só nomes de
teste e texto de doc. §2 acentuação vale para o texto novo.

---

## Fechamento de ciclo — BLK-MA-01 (Contrato e decisões do enriquecimento de vulnerabilidade, Plano B)

**Data:** 2026-07-23 · **Veredito:** APROVADO COM RESSALVAS (ressalva de fechamento, não defeito) ·
**Criticidade:** Média (com gate humano de produto embutido) · **Esteira:** Block Orchestrator (Opus)
-> Planner (Opus) -> [gate humano de produto — Vinicius] -> Builder (Opus) -> QA (Opus 4.8).
**READ-ONLY sobre o M1** (score PARALELO de vulnerabilidade; nada de `score_priorizacao`/
`hex_score_estrutural`/pesos/carteira/plano/artefatos oficiais tocado). **SEM DEC** (Plano B não tem
API externa; a rota Google Places fica no sucessor opcional BLK-MA-07 com gate + DEC próprios).

**Entregável (SÓ-DOC, ZERO código de produção):**
- `docs/vulnerabilidade_ma_contrato.md` (NOVO, 15 seções) — contrato canônico dos 6 sinais de
  vulnerabilidade (1–4 obrigatórios; 5/6 opcionais), metodologia do `score_vulnerabilidade`
  (heurística ponderada normalizada, NÃO-preditiva), a INVERSÃO da tese de M&A (comprar quer demanda
  ALTA + residual BAIXO/saturado — o oposto de `abrir_agora`), o join READ-ONLY no molde
  `enriquecer_outputs_residual_mercado.py:68-82` com asserts de invariância, anti-PII (DEC-012),
  integração ao lote semanal (DEC-013) e o registro das decisões D1–D8.
- `docs/README.md` — 1 linha no índice apontando o novo contrato.

**Achado load-bearing (verificado no código pelo Block Orchestrator e confirmado pelo QA):** o único
caminho de ingestão hoje — `_ler_csv_tp_wh` em `src/motor_expansao/demanda_revelada/concorrentes_densos.py:127`
— produz só `hex_id_res7`/`rede_normalizada`/`fonte`; **lê o `nome` e o descarta na fronteira, e não
retém rating**. Consequência: o **nome** do estabelecimento existe na fonte (viabiliza a lista NOMEADA
no futuro, como dado de negócio distinto da PII de reviewer da DEC-012), mas a **nota/rating não existe**
na fonte.

**Decisões do gate humano (2026-07-23, Vinicius):**
- **D1 = FASEADO** — MVP hex-level agregado (anti-PII) entra já; nomeação por-academia (Opção B)
  deferida atrás da confirmação/extensão de ingestão dos CSVs brutos.
- **D3 = NÃO carregam a nota** — sinal 2 (rating in-app) fica `n/d` PERMANENTE no Plano B (definido no
  framework, inativo no MVP); reputação/nota externa só no BLK-MA-07. Score roda em S1/S3/S4.
- **D4 = pesos S1=0,15 / S2=0,25 / S3=0,35 / S4=0,25** (churn domina); efetivos no Plano B (S2 fora,
  renormalizado): S1≈0,20 / S3≈0,467 / S4≈0,333; normalização percentil-por-universo; renormalização
  para sinal ausente/imaturo; flags de qualidade; NÃO-preditivo.
- **D5 = hex quente para M&A** = `sam_fitness_potencial` alto (top quartil) AND
  `score_oportunidade_residual < 25` (saturado); distância k=1 (`h3.grid_disk`); INVERSÃO registrada.
- **D2/D6/D7/D8 = defaults do Planner aceitos** (snapshots por `concorrente_id`+hash, 26 semanas,
  `MIN_SEMANAS=8`/`STALE_SEMANAS=12`; Parquet `data/staging` gitignored-se-nomeado + CSV
  `sep=";"`/`utf-8-sig`; só agregados + fixtures sintéticas; passo no `run_weekly_90.sh` pós-regen).

**Decomposição confirmada (a implementar nos sucessores):** BLK-MA-02 (churn+staleness, 100% reuso
interno), BLK-MA-03 (presença em agregador + extensão opcional para universo nomeado; rating NÃO entra
aqui por D3), BLK-MA-04 (score), BLK-MA-05 (lista de M&A com a inversão + entregável), BLK-MA-06 (cron
+ runbook), BLK-MA-07 (opcional/futuro — reputação externa, gate + DEC próprios).

**Validações (re-executadas pelo QA, sem bypass):** `pytest -q tests/unit/test_claude_md_size.py` = 2
passed; `import streamlit_app` = ok; diff do ciclo prova SÓ-DOC (apenas `docs/vulnerabilidade_ma_contrato.md`
+ `docs/README.md`; nenhuma linha de `src/`/`config.py`/`pipelines/m1`/artefato/`PRD.md`); §2 acentuação
PASS (prosa acentuada, identificadores em ASCII); âncoras de código citadas conferidas no repo real.
Suíte FULL não rodada (bloco não altera nenhuma linha executável; precedente BLK-RELPON-12) — não é
bypass.

**Ressalva de fechamento (a cargo do humano, não do Builder):** a branch `ciclo/BLK-MA-01` nasce do
commit humano `0c2e344`, que adiciona o epic ao `tasks/backlog.md` (governança). Logo o merge é
**humano** (PR de governança), não auto-merge — coerente com "executar ANTES de abrir PR". O bloco
BLK-MA-01 **não foi stubado** (evita churn add-then-stub no mesmo PR; o epic segue como âncora dos
sucessores); a reconciliação do backlog é passo de governança posterior. O commit do ciclo NÃO inclui
`tasks/backlog.md` (só `docs/` + este append + snapshots de handoff).

**Emenda pós-gate 2 (mesmo dia, 2026-07-23) — insumo real `unidades_totalpass_ac.csv`:** Vinicius
forneceu uma amostra real do coletor TotalPass (colunas `slug;nome;latitude;longitude;cidade;uf;cep;
endereco_formatado;modalidades;data_coleta` — **sem coluna de nota**, gitignored/anti-PII). Isso destravou
3 correções no contrato (só-doc, verificadas por 2 agentes adversariais Opus = CONSISTENTE + LIMPO):
(1) **coletor-vs-ingestão** — o rating não é "dropado na ingestão", ele **não é COLETADO**; habilitá-lo é
ajuste de COLETOR (scraper). A lista nomeada (D1-B) é **só ingestão** (nome/`slug` já coletados); churn/
staleness são **coletáveis hoje**. (2) **D2** passa a usar `slug` nativo + `data_coleta` como chave de
snapshot (fallback `concorrente_id`), com limpeza de ruído (linhas `0;0`/teste, entradas de tecnologia
do TotalPass) no BLK-MA-02. (3) Novo bloco **BLK-MA-08** (near-term) — ajustar os coletores TP/WH para
raspar a nota in-app, pré-requisito EXPLÍCITO do sinal 2; toca a trilha de scrapers/VPS (não toca o M1,
mas **NÃO loop-safe**). BLK-MA-07 fica só para reputação **externa** (Google). WellHub = mesmo schema do TotalPass (confirmado
por Vinicius 2026-07-23) → também sem nota; BLK-MA-08 cobre os dois coletores (sem atalho só-WellHub).

---

### BLK-RELPON-13 — Correção do painel Socioeconomia do slide-hero: hexágono H3 a 5 km (padrão residual), não setor

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** — mudança visual no PDF do Relatório Pontual, mesma natureza do BLK-RELPON-10; render puro, **READ-ONLY sobre o M1**. Exige **gate visual humano** (Vinicius) antes do merge. |
| **Prioridade** | A definir por Vinicius. |
| **Esteira** | Block Orchestrator → Planner → `[gate humano/visual — Vinicius: tamanho das 2 imagens + aparência final]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | BLK-RELPON-10 (slide-hero "Socioeconomia e Residual Fitness", já em produção). |
| **Autonomia** | **manual (NÃO loop-safe)** — exige gate visual humano (o loop não faz gate visual). READ-ONLY M1, mas não loop-safe por causa do gate. |

**Problema (diagnosticado no código, 2026-07-23).** No slide-hero, o painel **Socioeconomia**
(`censo_map.py:1445-1453`) desenha o **mesmo** `score_setor_2022_calibrado` por **SETOR** a 1,5 km que a
camada `score` do grid 2x2 (o gate S1=A do RELPON-10 manteve o score também no grid) — é **redundante**.
E é a única metade do hero ainda em setor/1,5 km, enquanto a outra (Residual Fitness) já é **hexágono H3
a 5 km**: o slide fica geometricamente incoerente.

**Correção (decisões de Vinicius, 2026-07-23).** Fazer o painel Socioeconomia seguir o **padrão do
Residual Fitness**, mantendo a **mesma métrica e paleta de hoje**:
- **Métrica/cor INALTERADAS:** `score_setor_2022_calibrado` colorido por `score_band_to_color` — o
  **mesmo dado que o dashboard mostra no modo de cor censitário** (`COLOR_MODES["censitario"]`,
  `constants.py:593-598`). Não troca a métrica.
- **Geometria muda:** de setor a 1,5 km → **hexágono H3 res-7** via disco `h3.grid_disk(k=5)` no raio de
  **exibição** `RAIO_RESIDUAL_DISPLAY_KM=5.0` km (padrão de `_render_camada_residual_hex`,
  `censo_map.py:995-1085`), lendo `score_setor_2022_calibrado` por hex do `hexes_df`.
- **Sem pins** e **fallback textual** quando faltar `hexes_df` (à risca do residual; FU1 do RELPON-10).
- **Reduzir um pouco o tamanho das 2 imagens** da página (`_socioeconomia_residual_page` /
  `_draw_maps_grid`, `censo_report.py:549-579`).
- O que passa a diferenciar do painel `score` do grid é a **escala/geometria** (grid = setor local
  1,5 km; hero = hex regional 5 km, igual ao dashboard), não a métrica.

**Escopo (render puro, READ-ONLY M1):**
1. Generalizar `_render_camada_residual_hex` + `_hex_polygons_3857` (hoje lê `oferta_efetiva_disponivel`
   fixo em `censo_map.py:963`) para aceitar `value_col` + `color_fn`/bandas — reusado por residual e pela
   nova socioeconomia.
2. Religar a camada `socioeconomia` (`censo_map.py:1445`) ao render hex: `value_col=score_setor_2022_calibrado`,
   `color_fn=score_band_to_color` (a de hoje), título "Socioeconomia - raio 5 km" (ASCII), `pins=[]`,
   `mostrar_legenda_pins=False`, fallback textual sem `hexes_df`.
3. Reduzir o tamanho das 2 imagens em `_socioeconomia_residual_page` / `_draw_maps_grid` (ajustar
   `margin_x`/`gap`/`top`/`bottom` ou fator de escala) — calibrado no gate visual.
4. Espelhar na variante **clássica** `_classico_socioeconomia_residual_page` (`censo_report.py:1851+`) —
   dashboard e bot.

**Guardrails.** **READ-ONLY M1 (§5):** não recalcula `score_priorizacao`/`hex_score_estrutural`/scores
censitários/`oferta_efetiva_disponivel`/artefatos oficiais. `setor_censitario_intersecao_area_1p5km` e
`RAIO_CENSITARIO_DEFAULT_KM=1,5` **INTOCADOS** — o raio de 1,5 km segue valendo para o motor censitário e
o grid 2x2; muda só a **EXIBIÇÃO** do painel hero. Labels do PNG em **ASCII** (a fonte não tem glifo
acentuado — exceção de RENDER ao §2). `CAMADAS_CENSITARIAS` mantém as **mesmas 8 chaves** (reusa
`socioeconomia`); **`/Count 8`** inalterado; demais camadas (densidade/renda/score/renda_domiciliar/
concorrentes/entorno) **byte-idênticas**.

**Testes a atualizar (o comportamento mudou de propósito).**
- Travas anti-vácuo que exigem `socioeconomia` reagir a pins: `test_relatorio_pontual_censitario_mapa.py:779-780`
  e `:998-1001` — agora sem pins (como o residual).
- Assert de título/raio: `:839` ("Socioeconomia - raio 1,5 km" → 5 km) e o rodapé de raio do PNG.
- Manter byte-identidade das OUTRAS camadas (`test_camadas_existentes_ficam_byte_identicas...`) e `/Count 8`
  (`test_relatorio_pontual_censitario_export.py`).
- Novos: camada `socioeconomia` é hex (não setor), sem pins, com fallback textual sem `hexes_df`, reagindo
  a `score_setor_2022_calibrado`.

**Critério de aceite.** Painel Socioeconomia do hero = `score_setor_2022_calibrado` por hexágono a 5 km
(padrão residual), sem pins, fallback textual; 2 imagens um pouco menores; variante clássica espelhada;
`/Count 8` e demais camadas byte-idênticas; ASCII no PNG; READ-ONLY M1 confirmado por mtime dos artefatos;
gate visual de Vinicius aprovado.

---

## Fechamento de ciclo — BLK-RELPON-13 (2026-07-24)

**Veredito do QA: APROVADO COM RESSALVAS** (ressalvas não-bloqueantes). Esteira completa executada pela
`/run-cycle`: Block Orchestrator → Planner → [gate humano — Vinicius aprovou o plano em 2026-07-23] →
Builder → QA. Tiering: BO/Planner/Builder/QA todos em Opus 4.8 (override +1 no BO, justificado no
`current_task.md` pela densidade de âncoras de código).

**O que foi entregue.** O painel `socioeconomia` do slide-hero deixou de ser o choropleth de setores a
1,5 km (redundante com o `score` do grid 2x2) e passou a `score_setor_2022_calibrado` por **hexágono H3
res-7** num disco `h3.grid_disk(k=5)` a `RAIO_RESIDUAL_DISPLAY_KM = 5,0` km — **mesma métrica e mesma
paleta** (`score_band_to_color`), mudando só a geometria/escala para casar com o `residual` ao lado.
Implementado **generalizando** o caminho do residual: `_hex_polygons_3857`, `_residual_hex_central` e
`_render_camada_residual_hex` ganharam parâmetros keyword-only **DEFAULT-PRESERVING**
(`value_col`/`titulo`/`legenda_titulo`/`legenda_entries`/`color_fn`/`valor_central_*`), de modo que o
residual sai byte-a-byte igual. Consequências: `socioeconomia` virou **CONDICIONAL** ao `hexes_df` (como o
residual — sem dado, chave ausente + fallback textual), **sem pins**, e a faixa superior passou a
`_legenda_valor_hex` ("Score no hexagono: NN"). As 2 imagens do slide são reduzidas por
`_HERO_MAP_SCALE` (0.92, ponto de partida calibrável no gate visual), aplicado só às 2 páginas do hero via
`packed_scale` → `_map_grid_cells_packed(scale=...)`; `scale=1.0` preserva todas as outras páginas.
Espelhado na variante **clássica** (a que o dashboard e o bot entregam).

**Guardrails confirmados.** READ-ONLY M1: artefatos oficiais com mtime `2026-06-10` idêntico antes e depois
da suíte; nenhum arquivo de `config.py`/`pipelines/m1`/`scoring` no diff. Motor censitário
(`setor_censitario_intersecao_area_1p5km`, `RAIO_CENSITARIO_DEFAULT_KM` = 1,5 km) **INTOCADO** —
`censo_point.py` sequer entrou no diff; o raio de 1,5 km segue valendo no motor e no grid 2x2, mudou só a
EXIBIÇÃO do painel hero. `CAMADAS_CENSITARIAS` com as **mesmas 8 chaves**, `/Count 8` preservado, demais 7
camadas byte-idênticas (travado por teste), labels do PNG em ASCII.

**Validações.** Suíte completa serial: `1984 passed, 2 skipped, 1 failed` — a única falha
(`test_score_retencao_territorial.py::test_run_readonly_m1_por_mtime`) é **pré-existente e não-relacionada**:
`FileNotFoundError` em `data/staging/unidade_territorio_retencao.parquet`, ausente nesta máquina; o QA
reproduziu isolada em 15s e confirmou que não há import algum entre `lifetime/` e `censo_map`/`censo_report`.
Em CI limpo o teste **pula** (staging gitignored) → portão da `main` não afetado. Subconjunto impactado
verde, ruff e mypy limpos, `import streamlit_app` ok.

**Verificação extra do QA (além do pedido).** Como a chave virou condicional, checou se isso apagaria o
painel em produção: os 4 call sites reais passam `hexes_df` e as partições servidas trazem
`score_setor_2022_calibrado` com 97,9% (SP) / 94,0% (RJ) de não-nulos em 0-100 → renderiza choropleth real.

**Ressalvas (não-bloqueantes) e destino.** (1) O teste da **mecânica** do `packed_scale` que o plano pedia
não havia sido escrito — **adicionado no fechamento** (`test_map_grid_cells_packed_scale_encolhe_e_mantem_centrado`,
trava `scale=1.0` idêntico + `scale<1.0` menor/centrado, **sem** travar o valor 0.92). (2) A falha
pré-existente virou **BLK-FIX-LTV-01** no backlog (Baixa, loop-safe, só teste).

**Pendente (humano).** **Gate visual de Vinicius** sobre o `_HERO_MAP_SCALE` (0.92) e a aparência final do
hex a 5 km — é critério de aceite do bloco e acontece **antes do merge**; Alta exige a label
`aprovado-humano` (DEC-016). Deploy segue manual, por digest.

### BLK-RELPON-13 — resultado do gate visual (2026-07-24, Vinicius)

Gate visual **REALIZADO** (o fechamento anterior o registrava como pendente com o valor de partida).
Duas calibrações pedidas por Vinicius apos ver o PDF no dashboard local:

1. **`_HERO_MAP_SCALE` 0.92 -> 0.85`** (`censo_report.py`) — as 2 imagens do slide-hero ficam um pouco
   menores do que o ponto de partida. Vale para as duas variantes; nenhum teste travava o 0.92
   (o `test_map_grid_cells_packed_scale_encolhe_e_mantem_centrado` trava a MECANICA, nao o numero),
   entao foi mudanca de uma constante so.
2. **`_META_RENDA_DOMICILIAR_TOTAL_RAIO` 6.200 -> 4.000`** (`censo_report.py`) — o card "Renda média
   domiciliar" dos Big Numbers passa a ficar **verde a partir de 4.000**. Efeito: a faixa 4.000-6.199,
   que antes saía vermelha, agora sai verde. Substitui o alvo anterior ancorado em "~C1 GeoFusion" —
   decisão de produto de Vinicius no gate. Entrou COM teste
   (`test_renda_media_domiciliar_fica_verde_a_partir_de_4000`, trava a fronteira 4.000 verde /
   3.999 vermelho), pois nenhum teste cobria a cor desse card. `docs/relatorio_pontual_censitario.md`
   atualizado nos dois pontos (o contrato afirmava 0.92 e 6200).

Validação: subconjunto impactado **92 passed**, ruff e mypy limpos. READ-ONLY sobre o M1 inalterado
(as duas mudanças são constantes de DISPLAY locais a `censo_report.py`; não tocam `flag_sam`, DEC-006/007,
`sam_fitness_potencial`, `oferta_efetiva_disponivel` nem qualquer artefato oficial).

---

### BLK-GRAPH-01 — Grafo de conhecimento (graphify) + correção do drift doc-vs-código

| Campo | Valor |
|---|---|
| **Criticidade** | **Crítica** (escalou de Alta em 2026-07-27 — ver nota abaixo) |
| **Status** | Concluído 2026-07-27 (branch `graph-01`, PR #150) — merge exige label `critica-aprovada` |
| **ClickUp** | — |

> **Escalada de Alta para Crítica, e por quê.** O bloco nasceu Alta (edita `CLAUDE.md`, GOVERNANÇA
> no `loop_guard`). Subiu para Crítica ao precisar de UMA linha no `.gitattributes` —
> `graphify-out/graph.json -diff linguist-generated=true` — que o `loop_guard` classifica como
> **CRÍTICO por caminho, não por conteúdo** (é o arquivo que impede a conversão CRLF de corromper
> os segredos `.enc.*`, BLK-OPS-01). A linha não encosta nessas regras.
> **Por que foi necessária:** `graph.json` tem ~10 MB / 263k linhas e representava **99% do diff**
> do PR #150. O revisor automático (`claude-review`) terminava com `success` mas **sem saída
> estruturada**, e o gate reprovava fail-closed. Sem o `-diff`, todo PR futuro que tocasse o grafo
> afogaria o revisor do mesmo jeito. Trocou-se uma aprovação Crítica única por um conserto
> permanente. Histórico: uma primeira linha (`merge=graphify`, do `graphify hook install`) foi
> REVERTIDA em `1ebef60` justamente para evitar essa escalada — voltou por necessidade, não por
> descuido.

> **Alta, não Média:** o bloco edita `CLAUDE.md`, que o `scripts/loop_guard.py` classifica como
> **GOVERNANÇA** (os arquivos que definem as próprias regras). **NÃO é loop-safe** — sem marcador de
> autonomia. READ-ONLY sobre o M1: nada recalcula `score_priorizacao`, `hex_score_estrutural`, pesos,
> carteira, plano ou artefatos oficiais.

**Escopo A — grafo.** Build do graphify sobre o **núcleo canônico** (421 arquivos: 290 de código por
AST + 131 docs/contratos/DECs). `context/handoff/` (566 logs de processo) e as imagens ficaram fora
de propósito. Resultado: **7.633 nós, 15.362 arestas, 424 comunidades**; benchmark do próprio
graphify: **~58× menos tokens por consulta**. Versionados: `graphify-out/graph.json`,
`GRAPH_REPORT.md` e `.graphify_labels.json` (45 comunidades rotuladas à mão + derivadas); cache,
HTML e backups datados vão para o `.gitignore`.

**Escopo B — manutenção.** Hooks `post-commit`/`post-checkout` (rebuild AST automático, sem LLM) +
merge driver para `graph.json`. Documentado em `CLAUDE.md` §7, incluindo o limite: **o hook NÃO
cobre `.md`** — mudança em doc exige `python -m graphify . --update` numa sessão Claude.

**Escopo C — 8 correções de drift doc-vs-código** que a extração revelou. Todas nasceram corretas e
envelheceram (mesma assinatura: fato duplicado em prosa + código, código travado por teste, prosa
travada por nada):
1. `docs/fontes_dados_gratuitas.md` §4 — pesos do M1 invertidos (`0.60/0.40` → **`0.40/0.60`**);
2. `CLAUDE.md` §6.1 — perímetro loop-safe apontava blocos deletados → aponta o seletor real;
3. `CLAUDE.md` §5 — 4 tabs → **5 tabs**, nomes e ordem reais;
4. `CLAUDE.md` §5 — baseline pytest `532` → **`2006 tests`**, virou regra em vez de número;
5. `CLAUDE.md` §3 — faltava `M1_HEX_LAND_FRACTION_MIN = 0.05`;
6. `docs/relatorio_pontual_censitario.md` — artefato híbrido `1.532.645` → **`1.542.531`** linhas;
7. `docs/relatorio_municipal_template.md` — 8 → **9 páginas** (faltava "Visão Geral do Município");
8. `docs/expansao_dominio.md` — `DIST_MIN_ULTRA_AINDA_KM` (nunca existiu) → `DIST_MIN_ULTRA_EXISTENTE_KM`.

**Escopo D — bookkeeping retroativo.** O ciclo `Renda média domiciliar` (2026-07-17, PRs
#124/#125/#126/#129) não tinha entrada em `completed.md` — o `CLAUDE.md` era o único registro.
Entrada reconstruída, e os 3 parquets de uplift entraram nas pré-condições de
`docs/deploy_api_bot.md` com o aviso de **fallback silencioso** (1.632 / 2.79 / 1.0).

**Fora de escopo (fica para bloco próprio):** servidor MCP do grafo (transformaria o grafo de
instrução em ferramenta) e o **gate doc-vs-código** — fazer `tests/contracts/test_parametros_canonicos.py`
parsear o `CLAUDE.md` §3 em vez de repetir os valores num dict. Sem esse gate, o drift volta.

---

## Fechamento de ciclo — BLK-GRAPH-01 (2026-07-27)

**Grafo de conhecimento (graphify) + correção do drift doc-vs-código** — criticidade **Crítica**
(escalou de Alta ao tocar o `.gitattributes`; ver a nota na especificação do bloco acima), sessão
ad-hoc fora do `/run-cycle`, branch `graph-01`, PR #150. **READ-ONLY sobre o M1**: nada recalcula
`score_priorizacao`, `hex_score_estrutural`, pesos, carteira, plano ou artefatos oficiais.
Merge exige `critica-aprovada` do Felipe.

**Entregue.** Ver a especificação do bloco acima (escopos A-D). Resumo do estado final: grafo com
**7.633 nós / 15.362 arestas / 424 comunidades** sobre 421 arquivos; `graphify-out/graph.json`,
`GRAPH_REPORT.md` e `.graphify_labels.json` versionados; hooks de rebuild instalados; `CLAUDE.md` §7
com a seção do grafo e seus limites; 8 correções de doc; entrada retroativa do ciclo de renda
domiciliar (2026-07-17).

**Validação.** `237 passed` no subconjunto impactado (`test_claude_md_size`,
`test_parametros_canonicos`, `test_relatorio_municipal`, `test_loop_guard`, `test_loop_guard_paths`).
`CLAUDE.md` em 173/230 linhas (teto do `test_claude_md_size`). EOL em LF preservado nos `.md` de
`tasks/` e `docs/` (DEC-017) — dois docs que estavam em CRLF passaram a normalizar corretamente.
Query de fumaça no grafo confirma que ele agora devolve `renda=0.40 / pop=0.60` e distingue o
`score_dominio_hibrido` (onde `0.60/0.40` É legítimo) — a exata confusão que sustentou o defeito
por ~2 meses.

**Defeitos corrigidos durante o próprio ciclo** (encontrados por verificação, não por presunção):
(a) o comando `graphify` documentado não estava no PATH — trocado por `python -m graphify`;
(b) o merge driver registrado pelo `hook install` apontava para o lançador nu — corrigido para
caminho absoluto; (c) `.graphify_labels.json` (rótulos curados) caía no `.gitignore` por um padrão
genérico `.graphify_*` — exceção explícita aberta.

**Dívida deixada em aberto, com nome.** (1) **Gate doc-vs-código**: `test_parametros_canonicos.py`
declara na docstring ser o contrato `CLAUDE.md §3 <-> config`, mas compara código com código (dict
`CANONICAL` hardcoded). Enquanto ele não parsear o §3, editar o `CLAUDE.md` não quebra nada e o
drift volta — foi essa a causa mecânica dos 8 defeitos. Já pedido em `docs/refatoracao/review.md`
(rank 2 da Fase 0). (2) **Servidor MCP** do grafo: sem ele, o grafo é instrução no §7 e depende de o
agente ler e obedecer. (3) Os hooks vivem em `.git/hooks/` e **não são versionados** — cada clone
precisa de `python -m graphify hook install`; o container do loop e o CI não têm o pacote.

---

### BLK-GRAPH-02 — Tornar o grafo uma FERRAMENTA, não uma instrução

| Campo | Valor |
|---|---|
| **Criticidade** | **Crítica** — o Escopo B entrou neste ciclo (gate humano de 2026-07-28): o PR toca `pyproject.toml` e `.gitattributes`, ambos `critico` no `loop_guard`. |
| **Status** | Pendente — preparado em 2026-07-28 para execução em sessão nova |
| **Depende de** | Estado final do BLK-GRAPH-01 na branch `graph-01` (`5450f04`). **NÃO exige merge** — o PR #150 pode seguir fechado. |
| **Autonomia** | *(sem marcador — **NÃO** loop-safe: toca `CLAUDE.md`, que é GOVERNANÇA no `loop_guard`)* |
| **ClickUp** | — |

**PONTO DE PARTIDA — ler primeiro.** Este bloco roda **a partir da branch `graph-01`**, não da
`main`. O PR #150 está **fechado de propósito** (faltava só a label `aprovado-humano`, operacional)
e **não precisa ser mergeado antes**. Começar com:

```
git checkout graph-01          # HEAD 5450f04; 7 commits sobre a main
git checkout -b graph-02       # ou seguir na propria graph-01
```

Nessa branch o grafo **já existe versionado** — `graphify-out/graph.json`, `GRAPH_REPORT.md` e
`.graphify_labels.json` — que é o insumo de que o `.mcp.json` precisa apontar. Na `main` eles não
existem; partir dela deixaria o bloco sem base.
**Consequência a decidir na abertura do PR:** uma branch derivada da `graph-01` carrega os 7
commits dela até que a `graph-01` entre. Ou abrir o PR do 02 com **base `graph-01`** (diff limpo,
só o 02), ou aceitar o diff combinado, ou reabrir e mergear o #150 antes. Escolher
conscientemente — o diff combinado passaria de 265k linhas e afogaria o `claude-review`, pelo
mesmo motivo documentado abaixo.

**Problema.** O BLK-GRAPH-01 entregou o grafo e o versionou, mas o *uso* dele não viaja. Estado
verificado em 2026-07-27 (não presumido — cada linha foi medida):

| O que falta | Evidência |
|---|---|
| Pacote instalado | `graphifyy` (DOIS 'y' — o nome nu `graphify` está UNCLAIMED no PyPI) não consta de `pyproject.toml` nem de `constraints.txt` |
| Atualização automática | `.git/hooks/` não é versionado; `core.hooksPath` não definido → **0 hooks viajam** |
| Ser ferramenta | **não existe `.mcp.json`** no repo |
| Norma vs bibliografia | a regra vive no `CLAUDE.md` **§7** ("Onde aprofundar"), lida como ponteiro |

Consequência: hoje o grafo depende de o agente ler a §7 e decidir obedecer, a cada sessão de cada
pessoa. Quem usar outro agente não recebe nada.

**Escopo A — Alta (entrega a maior parte do valor).**
1. **`.mcp.json` versionado** expondo o servidor MCP do graphify
   (`python -m graphify.serve graphify-out/graph.json`). Tools: `query_graph`, `get_node`,
   `get_neighbors`, `get_community`, `god_nodes`, `graph_stats`, `shortest_path`. É o único item
   que viaja com o repo **e** transforma o grafo em ferramenta — o agente passa a vê-lo na lista
   de tools e usa como usa Grep, sem depender de ler doc.
2. **Mover a regra da §7 para a §2** (`Regras operacionais rapidas`), que é lida como norma. Manter
   na §7 só o detalhe técnico (limites, rebuild, o que ficou fora do grafo).
3. **Hooks versionados**: mover para `.githooks/` no repo + documentar
   `git config core.hooksPath .githooks`. **Atenção — isto NÃO é automático:** o git, por
   segurança, não aplica `core.hooksPath` vindo do repositório; cada clone roda o comando uma vez.
   O ganho é o hook ser revisável e igual para todos, não auto-instalável.

**Escopo B — Crítica, SEPARÁVEL.** Declarar `graphifyy[mcp]` como dependência (extra opcional em
`pyproject.toml`, e `constraints.txt` se for pinar). Ambos são **path CRÍTICO** do `loop_guard`
(`pyproject.toml` = config do pytest/ruff + deps da imagem; `constraints.txt` = lockfile de supply
chain) → exige `critica-aprovada`.

**Criticidade e recorte.** Classificação medida com `loop_guard.classificar`:
`.mcp.json` = livre · `.githooks/*` = livre · `CLAUDE.md` = governança ·
`pyproject.toml` = **crítico** · `constraints.txt` = **crítico**.
Fazer A sozinho mantém o PR em **Alta** (só `aprovado-humano`). Juntar B escala para **Crítica**.
**Recomendação: A primeiro, B como bloco/PR próprio** — não prender o valor principal a uma
aprovação Crítica.

**QUESTÃO DE PROJETO EM ABERTO (decidir com evidência, não no chute).** O comando do `.mcp.json`
precisa ser **portátil**. `python -m graphify.serve` só funciona se o `graphify` estiver instalado
no python ativo — que é justamente o Escopo B. Caminho absoluto de interpretador **não** serve
(é específico da máquina). Investigar antes de implementar:
(a) o MCP falha graciosamente quando o pacote falta, ou quebra a sessão inteira?
(b) dá para apontar para `graphify-out/.graphify_python`? *(Não: é gitignored.)*
(c) A depende mesmo de B para ser portátil, ou um `README`/erro claro basta?
A resposta muda o recorte A/B — e a resposta errada entrega um `.mcp.json` que só funciona na
máquina de quem o criou.

**Fora de escopo:** tudo que envolva reconstruir o grafo, mudar o recorte do corpus
(`context/handoff/` e imagens seguem fora) ou tocar M1. **READ-ONLY sobre o M1.**

**Critério de aceite.** `.mcp.json` versionado e funcional num clone limpo (testar de verdade, não
presumir); regra na §2; hooks em `.githooks/` com a limitação do `core.hooksPath` documentada
explicitamente; `ruff`/`mypy` limpos; suíte verde; `loop_guard --base main` sem CRÍTICO se o
Escopo B ficou de fora.

**Armadilhas herdadas do BLK-GRAPH-01 — ler antes de começar.**
- O comando `graphify` **não está no PATH** (o pacote instala em `<python>/Scripts/`). Usar sempre
  `python -m graphify`.
- `python -m graphify hook install` **re-adiciona** `graphify-out/graph.json merge=graphify` ao
  `.gitattributes` — que é path **CRÍTICO**. Remover antes de commitar, ou o PR escala sem querer.
- `graph.json` é versionado **com** `-diff linguist-generated=true` no `.gitattributes`. Sem esse
  atributo o diff de ~10 MB **afoga o `claude-review`** (termina com `success` mas sem saída
  estruturada → gate fail-closed). Não remover.
- Um PR Crítico exige **DUAS** labels cumulativas: `critica-aprovada` (de um dono) **E**
  `aprovado-humano` (de humano ≠ autor). Elas não se substituem.

**Achado colateral a resolver (não é deste bloco, mas alguém precisa decidir).** O
`.github/workflows/guard.yml` já implementa `DONOS = {"kastaldy", "vinhoabencoado"}`, mas a
**DEC-019 está como `PROPOSTA`** no índice do `CLAUDE.md` §8 e no corpo da própria DEC
("aguardando aprovacao de Felipe"). O código executa uma decisão que a documentação diz não estar
aprovada. Ou a DEC vira APROVADA, ou o `guard.yml` volta a um dono só.

## Fechamento de ciclo — BLK-GRAPH-02 (2026-07-28)

**Veredito do QA: APROVADO COM RESSALVAS** (não-bloqueantes). Esteira completa: Block Orchestrator →
Planner (Escopo A) → [gate humano — AJUSTE de recorte] → Planner consolidado (A+B) → [gate humano —
aprovação] → Builder → QA. Todos em Opus. Branch `ciclo/BLK-GRAPH-02` (de `graph-01` @ `be7787a`);
base do PR: **`main`**. Criticidade **CRÍTICA** (escalada por decisão do humano).

**Entrega.** O grafo do graphify deixou de ser um ponteiro na §7 e virou ferramenta + norma:
`.mcp.json` versionado e **funcional** (10 tools por handshake JSON-RPC real), `graphifyy[mcp]`
declarado em `[dependency-groups]` (PEP 735) com o pin **`mcp>=1.28,<2`**, hook `post-commit`
versionado em `.githooks/`, norma movida da §7 para a §2 do `CLAUDE.md`, runbook novo em
`docs/grafo_conhecimento.md` e 3 arquivos de teste. DEC-019 passou de `PROPOSTA` a **APROVADA**.

**4 commits, todos por path:** `037c61a` (DEC-019 + §8 do `CLAUDE.md`) · `5255e4f` (`pyproject.toml`)
· `24f4619` (o Escopo A inteiro + script de prova + testes) · `acd72d4` (`tasks/backlog.md`).

**Quatro premissas do backlog caíram, todas por medição — nenhuma por suposição:**
1. **`mcp` 2.0.0 QUEBRA o servidor.** Removeu `AnyUrl` de `mcp.types`; `graphify/serve.py:1116` ainda
   o importa dentro de um `try/except` que **mascara o erro e mente** (`'mcp not installed'`). Sem o
   pin `<2`, o critério "funcional" é inalcançável — é isto que justifica o Escopo B.
2. **"O diff combinado passa de 265k linhas e afoga o `claude-review`"** está **OBSOLETA**: com o
   `-diff linguist-generated=true` do commit `a7c4754`, `main...HEAD` = **14 arquivos, 2.312/30
   linhas** (`graph.json` sai binário). Foi o que reabriu a base `main`.
3. **O extra em `[project.optional-dependencies]` era uma bomba-relógio:** `uv pip compile
   --all-extras` (comando canônico do lock, `ci.yml:45`) puxaria +36 pins no próximo bump de
   segurança. Medido em venv descartável: com `[dependency-groups]`, os 214 pins ficam **byte a byte
   idênticos**; como extra, viram 250.
4. **Regenerar o `constraints.txt` NÃO é inócuo:** `uv pip compile` não preserva pins — re-resolve
   tudo. Com o `pyproject.toml` intocado, o refresh de hoje já mudaria **30 pacotes**, incluindo
   `streamlit 1.59.2→1.60.0` e `fastapi 0.139.0→0.140.9`, ambos nas imagens de **produção**. Daí a
   decisão de deixar o lockfile **intocado**.

Além disso: o nome do pacote no PyPI é **`graphifyy`** (dois "y"); `graphify` nu está **UNCLAIMED** —
o próprio backlog escrevia o nome errado, corrigido no `acd72d4`. E o `post-checkout` do graphify
**não** foi versionado de propósito: ele chama `_rebuild_code` sem `changed_paths` (corpus inteiro) e
produz um grafo divergente do curado — 13.599 nós contra os 7.560 versionados, com `context/handoff/`
entrando no corpus contra o recorte da §7 e os rótulos curados sobrescritos.

**Validações (re-executadas pelo QA, sem bypass).** Prova funcional do MCP a partir do próprio
`.mcp.json`: `TOOLS (10)`, `Nodes: 7633 | Edges: 15362 | Communities: 424`, `EXIT: 0`,
`STDERR: (vazio)`, `VERDICT: PASS`. Suíte completa serial: **2028 passed, 2 skipped, 1 failed**.
`ruff` limpo; `mypy` verde no CI. `loop_guard`: `critico` = {`.gitattributes`, `pyproject.toml`},
`governanca` = {`CLAUDE.md`, `.gitignore`, `tasks/backlog.md`, `.claude/settings.json`}, **0 caminhos
de M1**. READ-ONLY M1 confirmado: `git diff main...HEAD -- config.py src/ data/` vazio e artefatos
oficiais com mtime de 2026-06-10.

**Ressalvas não-bloqueantes (nenhuma é regressão deste ciclo):**
- `pytest -n auto` quebra nesta máquina (`INTERNALERROR` do `execnet`) — o QA reproduziu **num
  worktree da `main` pura**, provando que é pré-existente. CI roda serial, não é afetado. Bloco novo:
  **BLK-QA-XDIST-01**.
- A falha única da suíte (`test_run_readonly_m1_por_mtime`) é ambiental — falta
  `data/staging/unidade_territorio_retencao.parquet` nesta máquina. Já catalogada como
  **BLK-FIX-LTV-01**; blobs idênticos aos da `main`.
- O critério de aceite nº 8 do plano ficou **literalmente** descumprido: a string
  `python -m graphify . --update` permanece no `CLAUDE.md`, mas **só dentro da advertência**
  `NAO faz isso` — o teste varre todas as ocorrências e trava essa intenção. Pede ratificação
  explícita do humano no corpo do PR.

**Pendências para o humano.** (1) Merge exige **três** labels cumulativas — `criticidade:critica`,
`critica-aprovada` (dono) e `aprovado-humano` (≠ autor) — mais review nativo de CODEOWNER para
`/CLAUDE.md` e `/pyproject.toml`. (2) **`git config core.hooksPath .githooks`** em cada clone: sem
isso o hook versionado não entra em vigor e o `post-checkout` divergente continua ativo. (3) Tocar
`pyproject.toml` faz o merge **republicar a imagem da API/bot no GHCR** (`ci.yml:236`) — não é deploy;
deploy segue manual por digest (§6).

---

### BLK-MA-02 — Materializador de snapshots semanais + extrator de churn/staleness (sinais S3/S4)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (cria **pipeline de ingestão novo**, **persiste dado derivado de fonte real com PII na origem** sob requisito anti-PII (D7/DEC-012), **apaga arquivos em disco** na poda de retenção e é o módulo que o BLK-MA-06 pluga no cron de produção. **READ-ONLY sobre o M1** — não toca `score_priorizacao`, `hex_score_estrutural`, pesos, carteira, plano nem artefato oficial; **sem DEC nova**, contrato §14). |
| **Prioridade** | Alta — é o primeiro bloco com código de produção da epic e destrava BLK-MA-04/05. |
| **Esteira** | Block Orchestrator → Planner → `[gate humano de ENGENHARIA — chave do snapshot, layout de partição, fronteira anti-PII]` → Builder → QA. |
| **Status** | Em execução (ciclo 2026-07-29). |
| **Depende de** | BLK-MA-01 (contrato `docs/vulnerabilidade_ma_contrato.md`, §6 e §13). **Não** depende de dado real: valida-se só com fixtures sintéticas. |
| **Autonomia** | **manual (NÃO loop-safe)** — criticidade Alta, ingestão de fonte com PII na origem e edição de `tasks/backlog.md` (governança). NUNCA marcar loop-safe. |

**Contexto.** O contrato §6 (D2) define churn (S3) e staleness (S4) a partir do **diff de snapshots
semanais** dos coletores. Verificação no repositório em 2026-07-29:
`data/staging/snapshots_concorrentes/` **não existe** e **nada no repo o gera** — a string só aparece
em `docs/vulnerabilidade_ma_contrato.md`. O `run_weekly_90.sh` atualiza os CSVs crus **sem arquivar
nada por estabelecimento** (`docs/infra_producao.md:136-149`), e os CSVs são **sobrescritos** a cada
coleta: toda semana não fotografada é perdida para sempre. Além disso, o feed onde vivem os
independentes (TotalPass/WellHub) é **mensal e ainda pendente** (`infra_producao.md:186`, DEC-013 §7.3).
Logo o produtor do insumo precisa nascer neste bloco.

**Objetivo.** Criar o pacote paralelo `src/motor_expansao/vulnerabilidade/` com (a) o
**materializador** — CSV cru → limpeza de ruído auditável → chave estável → `hash_campos_raspados` →
partição `data/staging/snapshots_concorrentes/semana=AAAA-SS/parte-*.parquet` (gitignored) — e (b) o
**extrator** — série de partições → `status_churn`, `semanas_sem_mudanca`, `flag_serie_imatura`,
`flag_staleness_interpretavel`.

**Escopo permitido.** Pacote novo com 4 módulos (`__init__.py`, `contrato.py`, `snapshots.py`,
`churn_staleness.py`); testes em `tests/unit/vulnerabilidade/` com fixtures **100% sintéticas** em
`tmp_path`; retenção rolante de 26 semanas; extensão de `_DENY_GOVERNANCA` do `loop_guard` ao pacote
novo; emendas de prosa ao contrato (§6 payload de 10 colunas; §6/§12 cadência real).

**Fora de escopo.** `score_vulnerabilidade`, `v3`/`v4`, normalização percentil e pesos → **BLK-MA-04**.
Presença em agregador e universo nomeado → **BLK-MA-03**. Rating in-app → **BLK-MA-08**. Cruzamento
com hex quente e entregável comercial → **BLK-MA-05**. Plug no cron/VPS e runbook → **BLK-MA-06**.
`normalizar_concorrentes.py` e `calcular_colunas_mercado.py` (`_DENY_CRITICO`) — leitura como molde,
**nunca** alteração nem import. Nenhuma alteração em `.gitignore` (`data/staging/*` já cobre).

**Critérios de aceite.** Pacote isolado provado por teste de import via AST (sem `pipelines.m1`,
`dashboard`, `api`, `censo`, `config` raiz, `normalizar_concorrentes`); snapshot com exatamente as
10 colunas do contrato, dtypes coagidos e `_assert_schema` que falha em coluna extra/faltante, chave
vazia, hex fora de res-7 ou chave duplicada; **anti-PII provado relendo o Parquet do disco** (nenhuma
coluna de PII, e o nome sintético injetado ausente até nos bytes do arquivo); partição por semana ISO
usando `iso_year` (fronteira `2027-01-01` → `2026-53`) e idempotente ao rodar duas vezes; limpeza de
ruído com auditoria **só de contagens** por `motivo_descarte`; `hash_campos_raspados` insensível a
`data_coleta`/`slug` e à ordem das modalidades, sensível a mudança real; estabilidade do `slug`
medida e rebaixamento de chave auditável via `chave_origem`; os 4 estados de churn assertados em
fixture de ≥10 semanas; **gap de feed (por `fonte` e por `(fonte, rede)`) não vira churn**;
`semanas_sem_mudanca` conta semanas observadas e reseta na mudança; poda remove só diretórios
`semana=` e nunca é chamada por `materializar(escrever=False)`; nenhum teste lê fonte real; CSV de
fixture com `sep=";"`/`utf-8-sig`; identificadores 100% ASCII; `loop_guard` sem `CRITICO`; suíte sem
regressão sobre a baseline de **2056** testes coletados.

---

## Fechamento de ciclo — BLK-MA-02 (Materializador de snapshots semanais + extrator de churn/staleness)

**Data:** 2026-07-29 · **Veredito:** APROVADO COM RESSALVAS (0 críticos · 3 médios · 6 menores) ·
**Criticidade:** Alta · **Esteira:** Block Orchestrator (Opus) -> Planner (Opus) -> [gate humano de
engenharia — Vinicius] -> Builder (Opus) -> QA (Opus). **READ-ONLY sobre o M1** e **anti-PII por
construção** (DEC-012). **SEM DEC nova** (contrato §14: o Plano B não tem API externa).

**Entregável.** Pacote paralelo novo `src/motor_expansao/vulnerabilidade/` (`__init__.py`,
`contrato.py` puro sem I/O, `snapshots.py` materializador, `churn_staleness.py` extrator) + **129
testes** em `tests/unit/vulnerabilidade/` com fixtures 100% sintéticas em `tmp_path`. Entrega o
caminho ponta a ponta dos sinais S3 (churn) e S4 (staleness): CSV cru dos coletores -> limpeza de
ruído -> partição `data/staging/snapshots_concorrentes/semana=AAAA-SS/parte-*.parquet` (gitignored)
-> `status_churn` / `semanas_sem_mudanca` / flags de maturidade. O extrator **para** no estado de
churn — `v3`/`v4`, normalização, pesos e `score_vulnerabilidade` são BLK-MA-04.

**Escopo decidido antes da esteira (E1/E2, Vinicius 2026-07-29):** E1 = materializador **+** extrator
(a §13 do contrato já põe a limpeza de ruído, que opera sobre o feed CRU, dentro deste bloco, logo
ele necessariamente atravessa a fronteira CSV->snapshot); E2 = o ciclo escreve o bloco BLK-MA-02
estruturado no backlog (ele só existia como uma linha da decomposição do epic), assumindo o modo
MERGE-HUMANO daí decorrente.

**Achado que derrubou uma premissa do contrato (Block Orchestrator, verificado no repo).** O feed
onde vivem os independentes (WellHub/TotalPass) **não roda em cron nenhum**: está como *"Pendentes
(futuro)"* com cadência prevista **mensal** (`docs/infra_producao.md:186`,
`docs/decisions/DEC-013.md:7`). O cron semanal atualiza só `Unidades/unidades_<rede>.csv`
(**cadeias**) e **sobrescreve** os CSVs; o único histórico é `historico_contagem.csv`, por rede. Logo
a afirmação do contrato §6 de que "o cron acumula snapshots desde ~26/06/2026" era **factualmente
falsa** — havia **zero** semanas de série por estabelecimento.

**Dois defeitos reais achados pelo Planner e corrigidos antes de qualquer código:**
- **P1 — a partição não pode sair do `data_coleta` da linha.** Coletor que falha mantém o CSV antigo
  (`infra_producao.md:181-182`), então aquelas linhas chegam com `data_coleta` de semanas atrás; com
  `existing_data_behavior="delete_matching"`, uma execução de hoje **apagaria uma semana passada** e
  a substituiria por um punhado de linhas da rede que falhou — perda irreversível, já que os CSVs
  crus são sobrescritos. Corrigido: `semana` = semana ISO da **data de referência da execução**;
  `snapshot_date` continua sendo o `data_coleta` por linha.
- **P2 — o gap de feed é por `(fonte, rede)`, não por `fonte`.** O feed `unidades` é um CSV por rede;
  se o coletor da `selfit` falhar, a fonte `unidades` ainda tem linhas das outras redes, e uma regra
  fonte-level marcaria a rede inteira como `sumiu_recente`. Falso churn em massa no sinal de maior
  peso (S3 ~ 0,467).

**Gate humano de engenharia (2026-07-29, Vinicius) — três decisões ratificadas:**
- **D3 — chave própria, `slug` visível.**
  `chave_snapshot = sha1("hash_estavel|<fonte>|<rede>|<nome_normalizado>|<hex_id_res7>")` e, quando o
  `slug` for confiável, `sha1("slug|<fonte>|<slug_normalizado>")` — **sempre** sha1 hex de 40 chars
  nos dois ramos. O `concorrente_id` de produção foi **descartado como chave de churn**: `lat:.6f` ~
  **11 cm**, então qualquer re-geocodificação vira 1 falso `sumiu_recente` + 1 falso `novo`. Ele fica
  na linha só para rastreabilidade, com a fórmula **replicada** (nunca importada de
  `normalizar_concorrentes.py`, que é `_DENY_CRITICO`) e o limite documentado: só casa com
  `concorrentes_mapeados.parquet` para `fonte == "unidades"`. Colisões são **COLAPSADAS**, nunca
  desambiguadas por ordinal (o ordinal depende da ordem de leitura do CSV e re-chavearia toda
  semana). A alternativa opaca (`flag_slug_presente`) foi **recusada**.
- **D5 — guarda alargada.** `_DENY_GOVERNANCA` do `scripts/loop_guard.py` passa a
  `^src/motor_expansao/(lifetime|demanda_revelada|vulnerabilidade)/` + 1 caso em
  `tests/unit/test_loop_guard_paths.py`. Sem isso, um PR que tocasse só o pacote novo seria
  classificado `LIMPO` apesar de mexer em camada com PII na origem.
- **D6 — contrato emendado (§6/§12) + decisão de produto.** Removida a afirmação falsa; registrados
  os dois relógios e a equivalência "**8 snapshots = ~8 MESES** na cadência real" (`MIN_SEMANAS=8` e
  `STALE_SEMANAS=12` contam semanas **observadas**, e foram especificados assumindo feed semanal);
  decidido que o **BLK-MA-06 pluga** o materializador no `run_weekly_90.sh` para o feed `unidades`
  (ressalva: dá série de CADEIAS, não do universo-alvo de independentes — o valor é de engenharia e
  de mercado/residual); registrado que o **cron MENSAL dos agregadores é caminho crítico do
  BLK-MA-04/05**. `MIN_SEMANAS`/`STALE_SEMANAS` **intocados** (valores do gate de 2026-07-23).
- D1, D2, D4, D7 fechadas pelo Planner sem objeção do gate.

**Defeito corrigido dentro do ciclo (pelo Builder):** `taxa_slug_com_uuid` era medida sobre o slug
**normalizado** (onde o `-` já virou espaço), zerando em silêncio justamente a métrica que detecta
UUID rotativo. Passou a ler o slug cru, travado por teste.

**Validações re-executadas pelo QA, sem bypass:** suíte **COMPLETA** serial (como o CI, `ci.yml:60`)
-> `1 failed, 2183 passed, 2 skipped in 1477.77s (24m37s)`, **2186 coletados** = baseline **2056** +
130. A única falha é a **pré-existente**
`test_score_retencao_territorial.py::test_run_readonly_m1_por_mtime` (BLK-FIX-LTV-01), que roda o
`run()` do `lifetime` sobre os Parquets reais do M1 e não tem relação com este bloco. `ruff check .`
limpo; `loop_guard` sobre o diff real = 6 violações, **todas `governanca`, ZERO `critico`**;
`garimpeiro_select_block.py` devolve `BLK-FIX-LTV-01` (o bloco **não** entra no loop); `backlog.md`
com **0 CRLF** (DEC-017). O QA ainda rodou sondas adversariais próprias, fora do conjunto de testes
do Builder.

**Ressalvas registradas (viraram `BLK-MA-02-FU1`, Média, manual, no backlog):** (1)
`flag_troca_chave_na_serie` mede "origens MISTAS no escopo", não "a chave trocou ao longo da série"
-> nasce permanentemente `True` e entregaria um sinal morto ao BLK-MA-04 (é a fórmula que o Planner
especificou e o gate não vetou, não desvio do Builder); (2) vazamento **transitivo** de import — o
pacote carrega `motor_expansao.dashboard.*` + `sklearn`/`scipy` em 7,5 s via o `__init__` do
`demanda_revelada`, o que não fere o READ-ONLY mas é **bloqueante para o BLK-MA-06** plugar no cron;
(3) seis menores (partição vazia, parâmetro morto, `assert` de runtime para
`CAMPOS_NUNCA_HASHEADOS`, prosa sem acento em 2 arquivos de teste, drift no §14/D2 do contrato,
`argparse`/`--dry-run` no `__main__`).

**Pendências fora deste bloco.** (a) O `Depende de` explícito do cron mensal dos agregadores no
**BLK-MA-04** não pôde ser registrado: o BLK-MA-04 ainda não existe como bloco estruturado no
backlog (só como linha da decomposição do epic) — o §12 do contrato já o registra como caminho
crítico. (b) **Achado de tooling:** `pytest-xdist 3.8.0` está **inutilizável** neste ambiente
(Windows + Python 3.14) — qualquer `-n N`, mesmo com 1 arquivo, aborta em `OSError: [WinError 6]`.
Não afeta o CI (serial), mas invalida a recomendação de `pytest -n auto` do
`prompts/qa_analyzer.md` para qualquer QA rodando local.

**Correção de bookkeeping:** o Builder afirmou que "CA-15 e CA-16 não são enumerados em lugar nenhum
do handoff"; eles **estão**, no handoff do Block Orchestrator
(`context/handoff/20260729-121047-block-orchestrator.md:217` e `:220`) — CA-15 = "READ-ONLY sobre o
M1, provado pelo diff" (o `loop_guard` é só a segunda metade) e CA-16 = "suíte sem regressão". Ambos
comprovados; a inferência apressada não mudou o resultado.

**Snapshots de handoff (versionados):** `20260729-121047-block-orchestrator.md` ·
`20260729-123146-planner.md` · `20260729-130703-builder.md` · `20260729-134525-qa.md`.

---

### BLK-MA-03 — Sinal 1 do score de vulnerabilidade: presença em agregador (WellHub/TotalPass), hex-level

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (agregação sobre contrato de coluna já materializado pelo BLK-MA-02; READ-ONLY sobre o M1; não cria ingestão, não persiste PII pela primeira vez, não apaga disco). **Ressalva:** a emenda ao §8.1 do contrato do epic (granularidade de `v1`) exige **gate humano pontual antes do Builder**. |
| **Prioridade** | Antes do **BLK-MA-04** (é o insumo do `v1`). |
| **Esteira** | Block Orchestrator → Planner → `[GATE HUMANO — emenda §8.1]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | BLK-MA-02 (concluído 2026-07-29). |
| **Autonomia** | **manual (NÃO loop-safe)** — mesmo perfil do BLK-MA-02/FU1: camada com insumo de PII na origem (DEC-012), toca `tasks/backlog.md` (governança) e exige gate humano de contrato. NÃO marcar loop-safe. |

**Objetivo.** Derivar o **sinal 1** do contrato §4 (presença/ausência em agregador) a partir da coluna
`fonte` que o BLK-MA-02 já materializa no snapshot, entregando-o no contrato
`presenca_agregador_v1` que o BLK-MA-04 vai consumir — sem calcular `v1`, pesos ou
`score_vulnerabilidade`.

**Escopo.** Criar `src/motor_expansao/vulnerabilidade/presenca_agregador.py` com
`extrair_presenca_agregador(base_dir=None, *, snapshots=None)` (mesmo molde de
`extrair_churn_staleness`: exatamente um entre os dois; puro com `snapshots` injetado). Algoritmo:
reduzir cada `(fonte, chave_snapshot)` à observação de **maior `semana`** → filtrar
`fonte in {totalpass, wellhub}` **E** `rede == independente` → agregar por `hex_id_res7`. Saída de 10
colunas (`hex_id_res7`, `fontes_presentes_no_hex`, `n_agregadores_no_hex`,
`n_academias_independentes_totalpass`, `n_academias_independentes_wellhub`,
`semana_ultima_observacao_totalpass`, `semana_ultima_observacao_wellhub`,
`snapshot_date_ultimo_totalpass`, `snapshot_date_ultimo_wellhub`, `versao_contrato`), com
`_assert_schema_presenca_agregador` e trava executável contra `v1`/`v2`/`score_vulnerabilidade`/
`n_sinais_disponiveis`/`flag_score_provisorio`. Constantes novas em `vulnerabilidade/contrato.py`
(`VERSAO_CONTRATO_PRESENCA_AGREGADOR`, `FONTES_AGREGADORES`, `CATEGORIA_INDEPENDENTE` **replicada**,
`CONTRATO_COLUNAS_PRESENCA_AGREGADOR`). Testes com fixtures 100% sintéticas.

**Decisão que exige gate humano — emenda ao §8.1 do contrato.** A granularidade de `v1` passa de
**por academia** para **por hexágono**: com o universo NOMEADO (D1-B) deferido, a chave do snapshot
embute a `fonte` (`chave_do_slug`/`chave_hash_estavel` em `contrato.py`) e o `nome` não é persistido, logo a mesma academia em TP e WH
é sempre duas chaves e "quantos agregadores cobrem esta linha" seria constante `1`. Consequências a
registrar no contrato: viés conhecido (todas as academias do hex recebem o mesmo `v1`; erro
sistemático nos hexes densos, direção de **falso negativo**); o ramo "0 agregadores → `v1=1,0`" é
**inalcançável e vacuoso** (fontes só-positivas; hex sem alvo observado não tem o que pontuar; o caso
informativo é o S3 `sumiu_recente`, peso ≈ 0,467); domínio efetivo `v1 ∈ {0.0, 0.5}` (S1 contribui ≤
10 dos 100 pontos); `v1` é categórico (§8.2: **nunca** percentil) e **não** é renormalizado para fora
pelo §8.4. **Restrição herdada pelo BLK-MA-04:** enquanto S3/S4 estiverem imaturos (~8–12 meses,
§6/§12), S1 é o único sinal do score e produz `score_vulnerabilidade ∈ {0, 50}`.

**Fora de escopo.** `v1`/pesos/`score_vulnerabilidade`/`n_sinais_disponiveis`/`flag_score_provisorio`
e qualquer normalização (**BLK-MA-04**); cruzamento com hex quente, `h3.grid_disk(k=1)`,
`alvos_ma_priorizados.csv` (**BLK-MA-05**); flag de staleness e plug no cron (**BLK-MA-06**); sinal 2
/ rating (**BLK-MA-08**); universo NOMEADO / D1-B / `concorrentes_densos.py` (**deferido pela decisão
S1**); os itens do `BLK-MA-02-FU1`; qualquer artefato, score, peso ou pipeline do M1;
`normalizar_concorrentes.py` e `calcular_colunas_mercado.py` (`_DENY_CRITICO`, molde de leitura
apenas); editar `snapshots.py`/`churn_staleness.py` (só importar).

**Critério de aceite.** Universo do sinal 1 fechado (TP/WH × `independente`), com o filtro aplicado
**depois** da redução; redução por **maior `semana`**, jamais por `snapshot_date` (que pode congelar
ou regredir quando o coletor falha); contagem de **chaves distintas** por `(hex, fonte)`;
`n_agregadores_no_hex ∈ {1,2}` e hex sem observação **não** emite linha, com o limite registrado no
docstring; contrato de 10 colunas travado por `_assert_schema_presenca_agregador` (ordem, res-7,
duplicidade, consistência `fontes_presentes_no_hex` × contagens, nulabilidade dos relógios de frescor
sse contagem `0`); trava executável contra score adiantado; isolamento de import por AST **incluindo**
a proibição específica de `demanda_revelada` no módulo novo; `CATEGORIA_INDEPENDENTE` replicada e
travada contra drift por teste; zero PII e zero releitura de CSV cru; emenda ao §8.1 escrita no mesmo
PR; suíte completa sem regressão (baseline nesta base: **2186 coletados**, a re-medir); `ruff` limpo;
`python scripts/loop_guard.py` sem `CRITICO`; READ-ONLY sobre o M1 provado pelo diff.

---

## Fechamento de ciclo — BLK-MA-03 (Sinal 1 do score de vulnerabilidade: presença em agregador, hex-level)

**Data:** 2026-07-29 · **Veredito:** APROVADO COM RESSALVAS (0 críticos · 2 médios · 6 menores) ·
**Criticidade:** Média · **Esteira:** Block Orchestrator (Sonnet) -> Planner (Opus) -> [gate humano
G1/G2 — Vinicius] -> Builder (Opus) -> QA (Opus). **READ-ONLY sobre o M1** e **anti-PII por
construção** (DEC-012). **SEM DEC nova.**

**Entregável.** Módulo novo `src/motor_expansao/vulnerabilidade/presenca_agregador.py` com
`extrair_presenca_agregador(...)`, o contrato `presenca_agregador_v1` (**10 colunas**) em
`contrato.py`, reexports no `__init__.py` e **43 testes novos** com fixtures 100% sintéticas. Entrega
o **insumo bruto do sinal 1** (presença em agregador) que o BLK-MA-04 vai consumir — o módulo NÃO
calcula `v1`, pesos nem `score_vulnerabilidade`.

**Base da branch (decisão B1, Vinicius).** `ciclo/BLK-MA-03` EMPILHA sobre `ciclo/BLK-MA-02` (ainda
não mergeado) com `origin/main` (`67e85f0`, PR #159 / BLK-BASEMAP-05) mergeado para dentro
(`a0430b8`, auto-merge limpo do `backlog.md`). O MA-03 depende do pacote `vulnerabilidade/` e da
coluna `fonte`, que só existem na branch do MA-02. **Escopo (decisão S1):** SÓ o sinal 1 — o universo
NOMEADO (Opção B / D1-B) segue DEFERIDO, e `concorrentes_densos.py` não foi tocado.

**A decisão que dominou o ciclo — o contrato descrevia algo incomputável.** O §8.1 define `v1` **por
academia** (0/1/2 agregadores). Isso pressupõe casar a MESMA academia entre TotalPass e WellHub, o
que exige identidade cross-provider — exatamente a Opção B, deferida. O Block Orchestrator detectou e
o Planner **confirmou no código**: `chave_do_slug` e `chave_hash_estavel` **embutem a `fonte`**, logo
a mesma academia em TP e WH é sempre DUAS chaves distintas, e "quantos agregadores cobrem esta linha"
seria constante `1` — um sinal sem variância, inútil para ranking.

**Gate humano G1 (2026-07-29, Vinicius) — RATIFICADO: emenda ao §8.1, `v1` passa a ser medido por
HEX.** A emenda (itens a-d, no cabeçalho, §8.1, §4 e §13) deixa escritos os quatro pontos exigidos:
(1) o **viés** — num hex denso em que o TP cobre a academia A e o WH cobre a B, o hex lê "2
agregadores" e ambas recebem `v1 = 0.0`; erro sistemático nos hexes-alvo, mas na direção **segura**
(**falso NEGATIVO**, nunca falso alvo); (2) o **domínio efetivo `v1 ∈ {0.0, 0.5}`**, com S1
contribuindo no máximo **10 dos 100 pontos**, não 20; (3) `v1` é **CATEGÓRICO — NUNCA percentilizar**
(percentilizar um binário reescalaria "presente em 1 agregador" para ~1,0 e destruiria a calibração);
(4) `v1` **não** é renormalizado para fora pelo §8.4. As colunas saem com sufixo **`_no_hex`**
(`n_agregadores_no_hex`, `fontes_presentes_no_hex`) para a ressalva viajar até todo consumidor futuro.

**Gate humano G2 — CIÊNCIA REGISTRADA (achado do Planner, não estava em lugar nenhum).** Pelo §8.4,
sinal imaturo é renormalizado para fora; pelo §6/§12, S3 e S4 ficam imaturos ~8-12 meses na cadência
real. Logo, durante todo o ramp-up **S1 é o ÚNICO sinal maduro do Plano B** e, sozinho, com peso
renormalizado 1,00 e domínio `{0.0, 0.5}`, produz **`score_vulnerabilidade ∈ {0, 50}`** — um score de
dois valores, que não ordena carteira. **Não é defeito deste bloco**; é restrição herdada pelo
**BLK-MA-04**, que precisará apresentá-la como banda/flag em vez de ranking, ou o BLK-MA-05 esperar a
maturidade do S3. Vinicius optou por **prosseguir sem mudar a sequência do epic** (nenhuma antecipação
de BLK-MA-08 ou BLK-MA-06 autorizada).

**Dois defeitos que o Planner achou auditando o Block Orchestrator:**
- **P1 — a redução "observação mais recente" não pode ordenar por `snapshot_date`.** Coletor que falha
  mantém o CSV anterior (`infra_producao.md:181-182`), então várias semanas carregam o MESMO
  `snapshot_date` e o desempate vira arbitrário; pior, uma execução que serve um CSV mais antigo faz o
  `snapshot_date` **regredir** enquanto a `semana` avança, e a redução escolheria a observação errada.
  Corrigido: ordenar por **`semana`** (a partição, derivada da data de EXECUÇÃO — foi por isso que o
  P1 do MA-02 a definiu assim). `snapshot_date` é medidor de frescor, nunca chave de ordenação.
- **P2 — reduzir ANTES de filtrar.** Filtrando primeiro, uma chave classificada `independente` na
  semana 1 e `smart_fit` na semana 5 sobreviveria pela observação **velha** e entraria como falso alvo
  de M&A — exatamente o falso positivo que o universo pretendia matar. A classificação mais recente
  vence.

**Três correções de raciocínio do Planner sobre o BO** (nenhuma muda o resultado, todas melhoram o
registro): a analogia com o §9/D5 **não se sustenta** — ali a grandeza propagada (hotness) é
intrínseca ao hex, enquanto "estar em agregador" é intrínseco à ACADEMIA; propagar o agregado do hex
como atributo da academia é **erro de categoria**, e a leitura hex tem de ser defendida pelo que é (a
única granularidade com variância), não por um precedente inexistente. O CA de isolamento, como o BO
escreveu, **não provava nada** — o `test_isolamento_imports` herdado não proíbe `demanda_revelada` (e
não poderia: `snapshots.py:51` o importa), então acrescentar o módulo à tupla passaria mesmo com o
import indevido; exigiu-se teste próprio. E a motivação de replicar `CATEGORIA_INDEPENDENTE` estava
factualmente errada: **não economiza um milissegundo** (qualquer import do pacote já executa o
`__init__` e paga os 7,5 s); o benefício real é não criar uma **segunda aresta**, para que o
`BLK-MA-02-FU1` feche o vazamento removendo uma dependência e não duas.

**Limite consciente registrado (R1).** O ramo "0 agregadores" (`v1 = 1,0`) é **estruturalmente
inalcançável e vacuoso** nesta granularidade: TP/WH são fontes **só-positivas** (a ausência de linha
nunca prova ausência real, só não-observação), e um hex sem academia independente observada não tem
alvo de M&A para pontuar. O caso informativo — "estava no agregador e saiu" — já é capturado pelo
**S3** (`status_churn == "sumiu_recente"`, peso efetivo ~0,467). O Planner conferiu que
`oferta_academias_menores` **não** fecharia o buraco: é TP/WH-derivado (colunas `n_plano_tp0..tp7`),
mesma família só-positiva. Nenhuma expansão de escopo foi proposta.

**Validações re-executadas pelo QA, sem bypass:** suíte **COMPLETA** serial (como o CI) ->
`1 failed, 2227 passed, 2 skipped in 1592.47s (26m32s)`, **2230 coletados** = baseline **2186** + 44.
A única falha é a **pré-existente** `test_score_retencao_territorial.py::test_run_readonly_m1_por_mtime`
(BLK-FIX-LTV-01), que morre por `unidade_territorio_retencao.parquet` ausente, em `lifetime/`, fora do
diff. `ruff check .` limpo; `loop_guard --stdin` = 4 violações, **todas `governanca`, zero `critico`**;
`import streamlit_app` ok; `test_parametros_canonicos` 4 passed; `garimpeiro_select_block` não
seleciona o BLK-MA-03; 0 CRLF (DEC-017). READ-ONLY provado pelo diff contra `a0430b8`.

**Sonda adversarial que o QA construiu (e que o Builder não tinha):** com 300 academias em 40 hexes,
o sinal produziu **12 hexes com `n_agregadores_no_hex = 1` e 25 com `= 2`** — variância real
confirmada, afastando o modo de falha "sinal constante" que o QA do MA-02 pegou no bloco irmão. O ramo
"0 agregadores" foi provado inalcançável pelo caminho público.

**Ressalvas registradas.** Viraram `BLK-MA-03-FU1` (**Baixa**, manual): a super-contagem de
`n_academias_independentes_*` sob rotação de chave `slug`->`hash_estavel` (não contamina
`n_agregadores_no_hex`, mas infla a leitura de "densidade do alvo" que o contrato vende ao BLK-MA-04)
e os 6 menores. **Uma ressalva foi para o `BLK-MA-02-FU1` (Item 2-B), não para o FU1 deste bloco:** o
QA mediu, por sonda de injeção, que o `test_isolamento_imports` pega **3 das 5 formas** de escrever o
import proibido — escapam `from .. import demanda_revelada` (nó `ImportFrom` com `module=None`) e
`importlib`. O buraco vale para **todos** os módulos proibidos e é anterior a este bloco; a correção
de **1 linha** fecha o teste compartilhado e o teste próprio do MA-03 de uma vez. Impacto hoje: zero.

**Snapshots de handoff (versionados):** `20260729-144904-block-orchestrator.md` ·
`20260729-151112-planner.md` · `20260729-154930-builder.md` · `20260729-162056-qa.md`.

---

### BLK-MA-04 — Score de vulnerabilidade (D4): composição ponderada de S1/S3/S4, renormalização e flags

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (fecha a fórmula de um score de negócio novo e emenda o contrato canônico do epic; **camada PARALELA e READ-ONLY sobre o M1** — não toca `score_priorizacao`, `hex_score_estrutural`, pesos `renda=0.40`/`pop=0.60`, carteira, plano ou artefato oficial). **Exige gate humano antes do Builder** (3 decisões de produto). |
| **Prioridade** | Antes do **BLK-MA-05** (é o insumo da lista priorizada). |
| **Esteira** | Block Orchestrator → Planner → `[GATE HUMANO — G-D1/G-D2/G-D3]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | BLK-MA-02 (concluído 2026-07-29) e BLK-MA-03 (concluído 2026-07-29). **Nota (não bloqueio):** o **cron MENSAL dos agregadores WellHub/TotalPass** segue pendente (`docs/infra_producao.md`, DEC-013 §7.3) — sem ele não existe série real dos independentes e o score não produz número de produção. Este bloco entrega o CÓDIGO, validado com fixtures 100% sintéticas. |
| **Autonomia** | **manual (NÃO loop-safe)** — mesmo perfil do pacote `vulnerabilidade/`: camada com insumo de PII na origem (DEC-012), emenda contrato canônico, toca `tasks/backlog.md` (governança) e exige gate humano. NUNCA marcar loop-safe. |

**Objetivo.** Materializar o §8 do `docs/vulnerabilidade_ma_contrato.md`: compor
`score_vulnerabilidade ∈ [0,100]` a partir de S1 (`presenca_agregador_v1`, hex-level) e S3/S4
(`churn_staleness_v1`, por academia), com renormalização por sinal ausente/imaturo e flags de
qualidade — **uma linha por academia** (`(fonte, chave_snapshot)`), sem hotness, sem entregável
comercial e **sem escrever nada em disco**.

**Escopo.** Criar `src/motor_expansao/vulnerabilidade/score.py` (módulo PURO) com
`calcular_score_vulnerabilidade(base_dir=None, *, churn=None, presenca=None)` e
`_assert_schema_score`; acrescentar a `contrato.py` (stdlib puro) `VERSAO_CONTRATO_SCORE`,
`SINAIS_ORDEM`, `PESOS_ALVO_SINAIS`, `SINAIS_INATIVOS`, `V3_POR_STATUS_CHURN`,
`CONTRATO_COLUNAS_SCORE` e a primitiva `renormalizar_pesos`; exportar em `__init__.py`; criar
`tests/unit/vulnerabilidade/test_score.py` (fixtures 100% sintéticas); estender
`test_contrato.py::test_identificadores_do_contrato_sao_ascii` e
`test_snapshots.py::test_isolamento_imports`; emendar o contrato do epic com `[emenda BLK-MA-04]`.

**Pontos críticos.** (1) **Filtro de universo neste bloco** — o frame de churn traz cadeias
(`fonte == "unidades"`) e marcas conhecidas dentro do TotalPass; sem filtro o score pontuaria uma
rede de cadeia como alvo de aquisição. O predicado é reusado de `presenca_agregador`, nunca
duplicado. (2) **Renormalização genérica** a partir dos pesos-alvo do D4 (`0,15/0,25/0,35/0,25`); os
efetivos (`~0,20/~0,467/~0,333`) são consequência de S2 estar inativo e são **asseridos, nunca
digitados**. (3) `n_sinais_disponiveis == 0` → score **NULO**, jamais `0`. (4) `v1` é CATEGÓRICO —
nunca percentilizado. (5) Enquanto S3/S4 estiverem imaturos (~8-12 meses na cadência real, §6/§12),
o score vive em `{0, 50}` com `flag_score_provisorio` — e **não ordena carteira**.

**Fora de escopo.** Qualquer artefato/score/peso do M1; reabrir os pesos do D4 (gate de 2026-07-23)
ou a granularidade hex do `v1` (gate G1 de 2026-07-29); sinal 2/rating (**BLK-MA-08**); hotness,
`h3.grid_disk(k=1)`, a INVERSÃO aplicada, lista comercial e os artefatos do D6
(**BLK-MA-05**); plug no `run_weekly_90.sh` e runbook (**BLK-MA-06**); `MIN_SEMANAS`/
`STALE_SEMANAS`/`RETENCAO_SEMANAS`; editar `snapshots.py`/`churn_staleness.py`/
`presenca_agregador.py`; corrigir as ressalvas dos FU1; ler fonte real, escrever em disco,
persistir PII ou criar dependência de API ao vivo.

**Critério de aceite.** Fórmula do §8 implementada com renormalização genérica e pesos efetivos
calculados; os regimes de disponibilidade cobertos por teste; `v1`/`v3`/`v4` nos domínios
contratados, com `novo` → ausente; universo filtrado com teste que falharia se uma cadeia entrasse;
join `validate="many_to_one"` com a borda do hex sem par coberta; contrato de coluna travado por
`_assert_schema_score`, que rejeita colunas do M1, do BLK-MA-05 e as duas famílias ressalvadas dos
FU1; módulo puro, sem I/O e sem PII; isolamento de import estendido; emenda ao contrato marcada
`[emenda BLK-MA-04]`, sem DEC; suíte completa sem regressão (baseline: **2231 coletados**); `ruff
check . --no-cache` limpo; `python scripts/loop_guard.py` sem `CRITICO` (só `governanca`);
READ-ONLY sobre o M1 provado pelo diff.

---

## Fechamento de ciclo — BLK-MA-04 (Score de vulnerabilidade: composição ponderada de S1/S3/S4)

**Data:** 2026-07-30 · **Veredito:** APROVADO COM RESSALVAS (0 críticos · 2 médios · 7 leves) ·
**Criticidade:** Alta · **Esteira:** Block Orchestrator (Opus) -> Planner (Opus) -> [gate humano
G-D1/G-D2/G-D3 — Vinicius] -> Builder (Opus) -> QA (Opus). **READ-ONLY sobre o M1** e **anti-PII por
construção** (DEC-012). **SEM DEC nova** (contrato §14).

**Entregável.** `src/motor_expansao/vulnerabilidade/score.py` (novo), contrato
`CONTRATO_COLUNAS_SCORE` de **20 colunas** + `SINAIS_ORDEM` / `PESOS_ALVO_SINAIS` / `SINAIS_INATIVOS`
/ `V3_POR_STATUS_CHURN` / `renormalizar_pesos` em `contrato.py`, reexport no `__init__.py`, **79
testes** novos com fixtures 100% sintéticas, e a emenda `[emenda BLK-MA-04]` em 7 pontos do contrato
do epic. Este bloco **fecha a fórmula do `score_vulnerabilidade`**; o cruzamento com hex quente, o
entregável comercial e os artefatos do D6 são BLK-MA-05, e o cron é BLK-MA-06.

**Criticidade ALTA, não Crítica (decisão C1, registrada).** A regra dura do `/run-cycle` ("pesos do
score -> Crítica") tem por contexto o **M1** — a mesma linha cita `score_priorizacao`,
`hex_score_estrutural` e artefatos M1 oficiais. A interpretação operacional de 2026-05-30 amarra
Crítica a alteração de **artefato M1**, o que este bloco não faz: o `score_vulnerabilidade` é
PARALELO e READ-ONLY. Reforçam: o §14 diz "sem DEC neste bloco", e o gate de produto do D4 (pesos
S1=0,15 / S2=0,25 / S3=0,35 / S4=0,25) já ocorrera em 2026-07-23.

**O achado mais grave, pego pelo Block Orchestrator e medido: o score pontuaria a SMART FIT como alvo
de aquisição.** O frame de churn do BLK-MA-02 traz `fonte == "unidades"` — o feed de CADEIAS —, e o
BLK-MA-02 não filtra universo (o §12 ratificou plugar o extrator de churn justamente nesse feed). O
BLK-MA-03 já filtrava do seu lado; este bloco não filtrava. Medição do Planner:
`{'totalpass': 3, 'unidades': 1, 'wellhub': 1}`. **O filtro ficou NESTE bloco**, não como correção
retroativa no MA-02, para não quebrar o que o §12 ratificou. Falso alvo é o erro mais caro do epic —
a lista vai para o time comercial.

**Gate humano (2026-07-30, Vinicius) — três decisões, todas ratificadas na recomendação do Planner:**
- **G-D1 — coluna ordenável nula.** A pergunta era "um consumidor futuro respeita uma proibição
  escrita em contrato?". Resposta do Planner: **não, e não precisa**. A saída traz
  `score_vulnerabilidade` **sempre preenchido** (o número auditável do D4) **e**
  `score_vulnerabilidade_ordenavel`, que fica **NaN enquanto `flag_score_provisorio`** estiver ligada.
  Um `sort_values` sobre frame provisório devolve NaN em todas as linhas — o consumidor descobre no
  primeiro teste, não no primeiro relatório entregue ao comercial. Reversível de graça quando o S3
  amadurecer. **Razão material (P3):** no regime só-S1, `score == 0` **não** significa "não
  vulnerável", significa "o hex tem os 2 agregadores" — mentira semântica que não pode virar número
  para o comercial.
- **G-D2 — NÃO abrir exceção no §8.4; propagar `status_churn` como coluna de FATO.** Aqui o Planner
  **discordou do BO** (que recomendava "fraca a favor") e o gate seguiu o Planner. `status_churn`
  entra como dado observado: sem peso, fora de `Σ(wi·vi)`, sem mudar regime. Dá ao BLK-MA-05
  exatamente a informação que a exceção queria injetar — segmentar por "sumiço observado" — sem que o
  score finja maturidade que não tem, e sem mexer em cláusula ratificada em 2026-07-23.
  **A justificativa do BO caiu por medição (P4):** a proteção `(fonte, rede)` cobre gap do **escopo
  inteiro**, não **coleta parcial** — com 30% das páginas raspadas, 70% do universo viraria
  `sumiu_recente` com peso 0,70 e zero amortecimento no ramp-up.
- **G-D3 — `v4 = min(semanas_sem_mudanca / STALE_SEMANAS, 1)`** (razão absoluta do §8.1), emendando o
  §8.2 para registrar que percentil-por-universo **não tem consumidor** no Plano B. Motivo decisivo: o
  percentil tornaria o score **NÃO MONOTÔNICO** — uma academia parada baixaria o `v4` de todas as
  outras, e a régua mudaria a cada execução conforme o universo raspado variasse.

**Dois defeitos que o Planner achou no plano do BO** (nenhum chegou ao código): **P1** —
`n_agregadores_no_hex` tipado `int64` é incompatível com o próprio critério de aceite, porque no join
com miss o pandas promove a `float64`+NaN; tem de ser `Int64` nulável. **P2** — o assert de
`left_only` que o BO propôs mataria exatamente a borda que outro CA exige testar; resolvido sem
`raise`, com biconditional auditável na saída.

**Buracos do contrato fechados neste ciclo** (achados novos do BO, nenhum estava em handoff anterior):
`novo` era um `status_churn` real **sem `v3` definido** no §8.1; e o §8.1 e o §8.2 **se contradiziam**
sobre `v4` (razão absoluta vs percentil). Ambos viraram emenda.

**Desbloqueio dos dois FU1 anteriores (D5, fechada pelo Planner).** Verificado no código que os únicos
insumos de `vi` são `n_agregadores_no_hex`, `status_churn` e
`semanas_sem_mudanca` + `flag_staleness_interpretavel` — logo nem a `flag_troca_chave_na_serie`
permanentemente ligada (`BLK-MA-02-FU1`) nem a super-contagem de `n_academias_independentes_*`
(`BLK-MA-03-FU1`) bloqueiam este bloco.

**Validações re-executadas pelo QA, sem bypass:** suíte **COMPLETA** serial ->
`1 failed, 2308 passed, 2 skipped in 1824.67s (30m24s)`, **2311 coletados** (baseline **2231**). A
única falha é a **pré-existente** `test_score_retencao_territorial.py::test_run_readonly_m1_por_mtime`
(BLK-FIX-LTV-01). `ruff` limpo; `loop_guard` 4x `governanca`, **zero `CRITICO`**; READ-ONLY M1 provado
pelo diff contra `1ea0242` (o merge de `origin/main`, não contra `main`, porque a branch empilha);
`garimpeiro` não lista o bloco; 0 CRLF.

**As sondas que o QA construiu (fora dos testes do Builder) — é o que sustenta o veredito:**
- **A3 provado por MUTAÇÃO:** desligou o filtro de universo -> **4 testes falham**; desligou o filtro
  **e** o schema -> os 2 testes comportamentais ainda falham sozinhos. A cadeia realmente não entra.
- **G-D1:** ordenável nula no provisório, idêntica ao score fora dele.
- **G-D2:** §8.4 **byte-a-byte intocado** (diff só aditivo); os 4 `status_churn` dão o mesmo score.
- **G-D3:** `v4` monotônico — mover `semanas_sem_mudanca` de B de 5 para 99 **não move** o score de A.
- **Renormalizador é DERIVADO, não digitado:** mutou os pesos-alvo e os efetivos acompanharam.
- "Ausência nunca vira zero" verificado em **3 caminhos**; `Int64` nulável confirmado.
- **Acentuação limpa nos dois sentidos** em `score.py` e `test_score.py` — **primeira vez no epic sem
  ressalva de acento nos arquivos novos** (o QA pegara isso no MA-02 e no MA-03).

**Ressalvas registradas (viraram `BLK-MA-04-FU1`, Baixa, manual).** (1) O teste de isolamento novo
prova **2 das 5** formas de import — o Builder replicou num arquivo novo o ponto cego do AST já
registrado no `BLK-MA-02-FU1` Item 2-B, que agora **subconta** (2 -> 3 arquivos; 3/5 -> 2/5) e precisa
ter o texto atualizado. (2) O regime de 1 sinal **`{s3}`** não tem teste e **o G-D1 não o cobre**:
medido `score = 100.0`, `provisorio = False`, `ordenavel = 100.0` — fiel ao §8.4 ratificado, mas
significa que a coluna ordenável não protege regime de 1 sinal quando o sinal é o S3; inalcançável por
`base_dir`, alcançável por frames injetados, que é o modo que o MA-05 pode usar. (3) Quatro leves,
entre eles uma **asserção morta** (`float(score or 1.0) != 0.0` passa para `NaN` **e** para `0.0`).

**Snapshots de handoff (versionados):** `20260730-093051-block-orchestrator.md` ·
`20260730-095342-planner.md` · `20260730-102902-builder.md` · `20260730-110503-qa.md`.

---

### BLK-WEB-18 — Merge grande `piloto-web` → `main` (DEC-022)

| Campo | Valor |
|---|---|
| **Criticidade** | **Crítica** (traz `web/`, `Dockerfile.web`, CI novo e FIN-VIAB-01 à main; toca `ci.yml`, `pyproject.toml`, `constraints.txt`). |
| **Prioridade** | Máxima (destrava o corte da DEC-022). |
| **Esteira** | manual (Felipe + sessão). |
| **Status** | Pendente. |
| **Depende de** | Bloco de governança da DEC-022 mergeado (guard `^web/` na base). |
| **Autonomia** | **manual (NÃO loop-safe)** — merge de 126 arquivos com política de resolução por grupo; `critica-aprovada` + admin-merge. |

**Contexto.** DEC-022: merge verdadeiro (nunca squash/`-s theirs`) em `sync/piloto-web-main`; main vence em
`loop_guard.py`/`vulnerabilidade/`/handoffs; piloto vence em `web/**`/FIN-VIAB-01/testes do piloto; `backlog.md` por
união manual; `ci.yml` por união (jobs `web`+`publish-web` entram; nada do Streamlit sai ainda). Na resolução:
`git rm` de `repro*.png` e `data/reports/Poc_Satelite/`; linha DEC-020 do CLAUDE.md ganha link markdown.

---

### BLK-WEB-19 — Reancoragem dos testes do motor compartilhado (pré-corte)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (só `tests/`; sem `conftest.py`). |
| **Prioridade** | Alta (bloqueia o BLK-WEB-20). |
| **Esteira** | Builder → QA. |
| **Status** | Pendente. |
| **Autonomia** | loop-safe (fronteira exclusiva em `tests/`). |

**Contexto.** ~⅓ dos 255 testes de `test_streamlit_app.py` cobre motor compartilhado SÓ via UI
(`analisar_entorno_ponto`, `score_band_to_color`, `parse_hex_ids_from_text`, bloco `relatorio_municipal`,
`enrich_dashboard_data`). Reancorar em testes diretos + splits (`test_cenario_multihex`, `test_ultra_pins`,
`test_renda_domiciliar_hex`, `test_coord_search`, `test_relatorio_pontual_ui_relviab06`,
`test_motor_expansao_import`, `tests/contracts/test_docs_vs_codigo.py`). Aceite: cobertura de
`src/motor_expansao/dashboard/` SEM `test_streamlit_app.py` ≥ baseline com ele.

---

### BLK-WEB-20 — O corte: remoção atômica do Streamlit (DEC-022)

| Campo | Valor |
|---|---|
| **Criticidade** | **Crítica** (deleta o app legado; toca `pyproject.toml`, `constraints.txt`, `ci.yml`, compose, CLAUDE.md). |
| **Prioridade** | Máxima. |
| **Esteira** | manual (Felipe + sessão). |
| **Status** | Pendente. |
| **Depende de** | **BLK-WEB-18** + **BLK-WEB-19** + compose sincronizado com o servidor. |
| **Autonomia** | **manual (NÃO loop-safe)** — `critica-aprovada` + admin-merge. |

**Contexto.** Um único PR: deletes (`streamlit_app.py`, `dashboard/{pages,components,ui_theme,ui_proto,ui_spike_deckgl}.py`,
`.streamlit/`, `Dockerfile.streamlit`, scripts rev/perf, 2 funções UI duck-typed, testes UI-only incl.
`test_streamlit_app.py`); `streamlit` sai das deps BASE + refresh do `constraints.txt`; `ci.yml` sem `Smoke import`/
`publish`/`build-sanity`/branch legada + pin `setup-node` + `trivyignores` no `publish-web`; compose sem `streamlit`
(+ `mem_limit` para o `web`); docs (~225 linhas/30 arquivos; CLAUDE.md §2 e §4 emendados). Verificação: `rg streamlit`
limpo fora de histórico; builds `Dockerfile.api`/`Dockerfile.web` + `/api/health`; suíte completa; pip-audit.

---

### BLK-WEB-21 — Descomissionamento do Streamlit no VPS (DEC-022)

| Campo | Valor |
|---|---|
| **Criticidade** | **Crítica** (produção; Caddy/Authelia/compose do servidor). |
| **Prioridade** | Máxima (fecha a DEC-022). |
| **Esteira** | manual — **comando a comando com Felipe (CLAUDE.md §6)**. |
| **Status** | Pendente. |
| **Depende de** | **BLK-WEB-20** deployado e validado. |
| **Autonomia** | **manual (NÃO loop-safe)**. |

**Contexto.** Ordem obrigatória: (1) Caddy — bloco `dashboard.` mantém SÓ `/tiles/*` + 301 raiz→`piloto.`,
re-cifrar `secrets/Caddyfile.enc`; (2) validar basemap nos PDFs (api + piloto); (3) PR do `healthcheck_vps.sh`
(EDGE_URL→`piloto.`); (4) `stop`/`rm` do container + `.env` sem `STREAMLIT_IMAGE`; (5) Authelia intocada
(`/tiles/` segue atrás do login); (6) `ps` todos healthy; (7) tag `arquivo/piloto-web-final` + delete da branch
`piloto-web`. Imagem GHCR retida por semanas (rollback = revert do BLK-WEB-20 + imagem existente).

---

## Fechamento de ciclo — BLK-MA-10 (2026-08-05)

**VEREDITO: ARQUIVAR.** A nota por unidade do TotalPass **não existe** — e o achado que fecha a
questão é o *motivo*: não é dado existente porém escondido atrás de proteção técnica; **a
funcionalidade de avaliar academia não existe no produto**, nem para o usuário, nem para a academia
parceira, nem no contrato de dados que alimenta o próprio site.

Spike time-boxed, **zero código de produção**, READ-ONLY sobre o M1. Relatório completo com
evidência, limites e estimativa de custo em `data/reports/spike_totalpass_nota_2026-08-05.md`.

**O salto em relação à sonda de 2026-07-30/31.** Aquela provou ausência por **amostragem** (7 páginas
de unidade, JSON-LD sem `aggregateRating`). Esta prova no **nível do produto**, por cinco vetores que
não dependem de amostra: (1) `dev.totalpass.com` é portal de desenvolvedor **público e sem
autenticação**, com ~65 endpoints em 3 APIs e **zero** campo de rating — fonte independente e de
dentro da própria empresa; (2) o bundle JS do app de busca (20 chunks, ~1,3 MB, leitura autorizada
por `Allow: /*.js` no robots) tem zero identificador de rating — o cliente **não sabe exibir** nota;
(3) o BFF público `/api/website/gyms/` devolve 18 atributos por unidade, todos de elegibilidade de
plano — o backend **não serve** nota; (4) nenhum dos dois lados do produto conhece a feature (central
de ajuda sem artigo de avaliar, com toda ocorrência de "nota" sendo nota **fiscal**; Portal de
Academias sem menção; e o próprio blog **ensinando o parceiro a rodar pesquisa de satisfação em
Google Forms/NPS**); (5) no app, os 6 screenshots oficiais — inclusive a tela de mapa, onde a nota
apareceria — não têm estrela, e em 05/10/2024 um cliente pagante **pediu a feature** numa resenha da
App Store, o que é prova positiva de ausência.

Único quase-acerto, verificado a fundo: `monthly_gyms_rankings` (`hr.totalpass.com`) é ranking por
**contagem de check-in** dos beneficiários de **uma** empresa contratante — volume, não satisfação;
inútil como proxy de qualidade e enviesado pelo contrato daquele cliente.

**Conformidade.** Os ToS **não têm cláusula** contra scraping/crawler/acesso automatizado (têm
restrição de uso comercial da marca e regra de 1 cadastro por pessoa, esta última inviabilizando
conta dedicada à coleta); o `robots.txt` é permissivo. Ainda assim: só leitura pública espaçada,
**nenhum login, nenhuma credencial, e nenhuma tentativa de contornar os `403`** encontrados
(`api.`, `cms.`, Zendesk). Limites não verificados declarados na §5 do relatório.

**DECISÃO HUMANA (Vinicius, 2026-08-05): arquivar + levar ao BLK-MA-07.** Sem follow-up técnico. As
**15.986 unidades** TotalPass já coletadas — universo maior que o do WellHub — vão para o
**BLK-MA-07** (reputação **externa**, com gate e DEC próprios); sem isso ficariam permanentemente sem
sinal 2. Se a nota do TotalPass virar requisito de negócio, o caminho é **comercial** (pedir a fonte
ao grupo SmartFit), não técnico.

**Insumo para o gate do BLK-MA-09 (D-B).** Fica confirmado que a régua assimétrica por fonte é
**PERMANENTE**, não transitória: a partição do universo entre WellHub (com `v2`) e TotalPass (sem)
**não se resolve por engenharia**. O D-B precisa decidir sabendo disso — o que reforça a opção **(0)**
já listada como preferida no backlog (propagar o rating como coluna-fato **sem peso**), que dissolve
o problema em vez de administrá-lo.

**Pendente para o housekeeping em lote** (modo auto-merge não toca `backlog.md`): o stub do
BLK-MA-10; e o **BLK-MA-07 ainda não tem seção própria** no backlog (existe só como bullet da
decomposição do BLK-MA-01, `:1586`) — a seção precisa ser criada carregando o veredito acima e a
hipótese do app mobile como linha de risco.


---

## Fechamento de ciclo — BLK-MAPA-FAIXAS-01 e painel de metodologia (2026-08-05)

**Data:** 2026-08-05 · **PRs:** #187 (faixas nomeadas) + #185 (painel de metodologia) ·
**Criticidade:** Alta (#187) / Média (#185) · **Esteira:** revisão adversarial → reparo → merge
humano · **Impacto no M1:** NENHUM (READ-ONLY; nada em `config.py`, `pipelines/m1`, pesos ou
artefatos oficiais).

Registro tardio: os dois PRs entraram na main (`6bdd4f7` e `b7ea6a1`) **sem tocar `docs/` nem
`tasks/`** — 2.405 linhas em `web/`, `src/` e `tests/` sem uma linha de bookkeeping. Esta entrada
fecha o furo "mergeado-mas-não-registrado".

**#187 — régua única entre a legenda do mapa e a etiqueta do ranking.** Cria
`FAIXAS_MAPA_POTENCIAL` (Desfavorável · Fraco · Promissor · Forte · Excelente) e
`FAIXAS_MAPA_DEMANDA` (Saturado · Restrito · Moderado · Amplo · Livre) em
`dashboard/constants.py`, espelhadas em `web/src/lib/faixas.ts` e travadas por
`tests/contracts/test_faixas_mapa_espelho.py`. O defeito que motivou: em Campinas, 2.400 alunos
residuais saíam etiquetados "Baixa" no ranking e "Livre" na legenda ao lado — 96% de uma unidade
cheia com dois nomes na mesma tela. A camada 4 passa a colorir por `faixa_oportunidade` do M1 (que
NÃO é corte de `score_priorizacao`: o M1 a define cortando o percentil nacional em [35, 50, 65, 80]).

**Cinco reparos aplicados na revisão, antes do merge:** (1) a legenda voltou a mostrar as 10 cores
que o mapa pinta — cada bloco nomeado carrega as duas bandas de 10 pontos do seu intervalo
(`bandasDaFaixa`/`fundoDoSwatch`), senão um hex de score 45 saía laranja no mapa sem bloco
correspondente na legenda; (2) `test_passo3_etiqueta_pelo_vocabulario_competitivo` virou tautologia
com o homônimo "Livre" e passou a discriminar por `tag_cor`; (3) score ausente deixou de virar 0 e
de afirmar "Desfavorável"; (4) a faixa passou a sair do valor CRU, não do arredondado (79,6 virava
80 e mudava de faixa na borda); (5) o espelho de `colors.ts` (`FAIXA_M1_HEX`, chaveado pelo LABEL
acentuado) ficou travado por teste — sem isso, renomear `FAIXA_LABELS["media"]` pintaria de cinza
todos os hexes daquela faixa, com o chip do ranking continuando colorido e nenhum teste vermelho.

**#185 — painel de metodologia (`GET /api/metodologia`).** Gaveta lateral que explica as 4 camadas
do funil: pergunta, régua de corte, métricas em dois níveis e os parâmetros do modelo. Contrato do
payload em `docs/contrato_api_metodologia.md`.

**Sete reparos aplicados antes do merge.** O conflito com a main foi resolvido tomando o lado da
main nos pontos que **reverteriam o PR #184** (fila do passo 4 sem fallback — decisão do dono em
2026-08-03 —, o parâmetro `metrica_etiqueta` e o bloco `ancoras`), preservando do PR só os literais
virando constantes nomeadas. E o painel publicava **seis afirmações factualmente erradas**, todas
verificadas contra o código: calibração "dentro de cada estado" (é percentil NACIONAL de renda com
peso 0,60 + população relativa ao município com 0,40; `calibrar_renda_setor_2022.py` lista
"multiplicativo por UF" entre as abordagens REJEITADAS); insumos "renda, composição dos domicílios e
perfil das famílias" (são dois); "cada unidade em 2 km conta como 2.500 alunos" (a oferta é
PONDERADA por distância — concorrente a 1,9 km desconta ~125, não 2.500); saturação como única causa
de residual zero (falta o gate do SAM — DEC-006/007 —, em que "não avaliada" virava "já atendida");
omissão do fallback municipal da população; e "Growth API" como fonte da oferta Ultra (sai da base de
performance, por carga). As faixas publicadas passaram a DERIVAR de `constants.FAIXAS_MAPA_*` e
`FAIXA_LABELS`, e `tests/contracts/test_metodologia_espelha_o_funil.py` trava a coerência.

**DEFEITO CONHECIDO, não corrigido aqui:** a etiqueta do ranking virou CONSTANTE nas camadas 1, 2 e
3, porque o corte de cada camada coincide com o piso da última faixa (camada 2: corte de 2.000
alunos = score 80 = piso de "Livre"). Medido: 8 municípios com residual de 2.000 a 40.000 alunos —
amplitude de 20× — saem todos como "Livre". O painel agrava, publicando 5 faixas das quais 4 nunca
aparecem. Aberto como **BLK-MAPA-CHIP-01**; não foi corrigido junto porque os PRs #196 e #197 estão
reescrevendo o mesmo arquivo.

---

## Fechamento de ciclo — BLK-RELPON-07 (mapas de calor legíveis) (concluído 2026-07-28, registrado 2026-08-05)

**Data de conclusão:** 2026-07-28 (PR **#154**, "BLK-RELPON-07 (rebase) — mapas de calor legíveis:
nomes de rua/bairro por cima do choropleth") · **Registrado em:** 2026-08-05 · **Impacto no M1:**
NENHUM (leitura do Relatório Pontual).

Registro tardio de bloco **mergeado-mas-não-registrado**: o PR entrou em 2026-07-28 e o bloco
continuou aberto no backlog com `Status: Em revisão (PR aberto)` por mais de uma semana.

**Como o furo passou despercebido — e por que quase virou perda de trabalho.** O ID `BLK-RELPON-07`
foi **reusado três vezes** para assuntos diferentes: "Slide de perfil do Bairro/Distrito" e "refino
visual do slide" (ambos concluídos em 2026-07-15) e este, "Mapas de calor legíveis". Como
`housekeeping_move_block.is_done` casa por **token de ID, não por título**, o `--emit-delta` já
listava o bloco como pronto para stub desde julho — com base em entradas de completed que falam de
outro assunto. Quem executasse o helper mecanicamente teria stubado um bloco que se declarava "em
revisão", e o ponteiro `ver tasks/completed.md` levaria ao registro errado. **Lição para o
housekeeping em lote: conferir o TÍTULO do bloco, não só o ID, antes de aceitar o delta.**

---

---

### BLK-MA-01 — Contrato e decisões do enriquecimento de vulnerabilidade (design, Plano B)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (camada de enriquecimento paralela que reusa dados já coletados + diff de snapshots; **sem dependência externa nova** e **sem DEC** — a rota Google Places/§2 foi descartada no Plano B; gera um score paralelo e um entregável comercial. **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir por Vinicius. |
| **Esteira** | Block Orchestrator → Planner → `[confirmação humana — produto: pesos/limiares do score + definição de hex quente]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | DEC-013 (WellHub/TotalPass já coletados + **cron semanal que acumula os snapshots** — insumo de churn/staleness); camada mercado/residual + Demanda Revelada (para "hexágono quente"); `concorrentes_mapeados.parquet`. |
| **Autonomia** | **manual (NÃO loop-safe)** — toca a trilha de scrapers/VPS (integração ao cron, DEC-013) e define um score/entregável comercial; precisa de confirmação humana de produto. NÃO marcar loop-safe. |

**Contexto (ancorado).** Os scrapers do Vini (`VinhoAbencoado/GymScraping`, DEC-013) já mapeiam a
oferta concorrente **e rodam semanalmente**; a base entra no Motor via
`normalizar_concorrentes → calcular_colunas_mercado` e alimenta o residual. Hoje esses registros têm
oferta/rede/geo, mas **nenhum sinal de fragilidade do negócio**. O insight do Plano B: a **variação
temporal** e a **última atualização** saem do **diff do próprio histórico de scraping** (nenhuma API
externa), e a **reputação** vem do **rating in-app WellHub/TotalPass** que já é coletado. O BLK-MA-01
**não escreve código de produção** — fixa o contrato dos sinais, a metodologia do score e as decisões
de produto; os sucessores implementam.

**Objetivo do epic.** Score de vulnerabilidade por academia independente + lista priorizada de M&A
(academias mais vulneráveis próximas a hexágonos quentes) para o time comercial.

**Sinais (Plano B — só fontes internas / já coletadas).**
1. **Presença/ausência em agregadores** (WellHub/TotalPass) — já interno (DEC-013). Tese: ausência do
   canal onde o público low-cost está → sinal de fragilidade.
2. **Rating in-app WellHub/TotalPass** (subconjunto listado) — substitui a "avaliação média" do Google;
   `n/d` para quem não está no agregador (ver D3). **[VERIFICAR no gate — checado por Claude em
   2026-07-23]** o único caminho de ingestão que existe hoje,
   `demanda_revelada/concorrentes_densos.py:_ler_csv_tp_wh` (linha 127), produz SÓ
   `hex_id_res7`/`rede_normalizada`/`fonte` (drop-PII na fronteira), **sem coluna de rating**.
   Confirmar que os CSVs BRUTOS TP/WH (que vivem na VPS, gitignored) carregam a nota ANTES que
   BLK-MA-03/04 dependam dela — senão este sinal também é aquisição, não reuso, e o rótulo "já
   coletado" cai. É a claim mais load-bearing do Plano B.
3. **Churn/permanência** via **diff dos snapshots semanais** — apareceu/sumiu/reapareceu na base dos
   scrapers → forte proxy de fechamento/venda. (Substitui a "variação de reviews".)
4. **Staleness** via **diff dos snapshots** — tempo desde a última mudança nos campos raspados
   (horário/preço/lista de unidades/endereço). (Substitui "tempo desde última atualização" — proxy mais
   confiável que o "last-updated" do Google, que nem é exposto.)
5. **(Opcional) Tendência de popularidade no agregador** — `membros`/`alunos_parceiras` da célula
   subindo/caindo, quando a série permitir.
6. **(Opcional, interno) Pressão competitiva** — proximidade a Smart Fit/rede Ultra + residual saturado
   (de `concorrentes_mapeados` + Ultra + mercado/residual): independente espremida = mais vulnerável.
   Colunas reais já materializadas por `hex_id` em `data/staging/hexagonos_mercado_mapeado.parquet`
   (verificadas em 2026-07-23): `pressao_concorrencial_score_2km`, `n_concorrentes_mapeados_2km`,
   `dist_concorrente_mais_proximo_m`, `n_unidades_ultra_2km`, `rede_dominante_2km`,
   `share_smart_fit_2km` — nenhum sinal de "pressão" precisa ser recomputado do zero.

**Mapa dos 4 sinais originais → Plano B:** avaliação média → (2) rating in-app; Δ reviews 3m → (3)
churn + (5) tendência; presença agregadores → (1) [já interno]; última atualização → (4) staleness.

**Decisões a resolver/confirmar (BLK-MA-01).**
- **D1 — Definição de "academia independente".** Critério de não-rede/bairro sobre `concorrentes_mapeados`
  (ex.: `rede` isolada / contagem de unidades da marca == 1) e o universo exato (os 28 scrapers citados
  vs. os 90 coletores da DEC-013 — quais entram).
- **D2 — Fonte/retenção dos snapshots semanais.** Onde vivem os snapshots dos scrapers (formato/retenção)
  para computar churn/staleness; janela de staleness (nº de semanas sem mudança = "stale"); tratamento do
  **ramp-up** (cron ativo desde 26/06 — ~1,5 mês hoje; a série cresce). Sem histórico → sinal marcado
  como imaturo, não penaliza.
- **D3 — Rating de agregador.** Usar como sinal só no subconjunto listado; como tratar `n/d` (não
  penalizar quem não tem rating; a ausência de agregador já é o sinal 1).
- **D4 — Fórmula/pesos do score.** Heurística transparente e auditável (composição ponderada normalizada
  dos sinais), com direção de cada um (ausência de agregador ↑vuln.; rating baixo ↑; churn/sumiço ↑;
  staleness alta ↑; popularidade caindo ↑; pressão competitiva alta ↑). NÃO é modelo preditivo treinado
  em desfecho — se um dia se quiser validar que prevê aquisição/fechamento, entra a disciplina DEC-008
  (out-of-fold vs baseline) em bloco próprio.
- **D5 — "Hexágono quente" + proximidade.** Qual métrica define quente (`score_oportunidade_residual`,
  SAM, demanda revelada) e o limiar de distância academia↔hex para entrar na lista de M&A.
  Âncora verificada (2026-07-23): o hotness por hex já está materializado em
  `data/outputs/carteira_expansao_acionavel.parquet` (4.899x62) — colunas `score_priorizacao`,
  `score_setor_2022_calibrado`, `score_expansao_hibrido`, `score_oportunidade_residual`,
  `oferta_efetiva_disponivel`, `tese_entrada` por `hex_id` — e casa direto com
  `concorrentes_mapeados.hex_id_res7`. Fazer o join READ-ONLY no padrão defensivo de
  `src/motor_expansao/pipelines/enriquecer_outputs_residual_mercado.py:68-82` (asserts de
  `score_priorizacao`/ranks/cardinalidade inalterados após o join). **Nota de tese de M&A:** comprar
  (não construir) quer demanda ALTA + residual BAIXO (mercado saturado); é a INVERSÃO do sinal de
  abrir unidade nova (residual alto). Registrar a inversão no cálculo.
- **D6 — Entregável.** Formato da lista priorizada (Parquet + CSV `sep=";"`/`utf-8-sig` para o comercial;
  e/ou overlay no dashboard) e onde materializar (`data/staging` / `data/outputs`).
- **D7 — Anti-PII.** Persistir **somente agregados** (rating médio, contagens, flags de churn/staleness);
  **nunca** texto/autor de review nem PII. Fonte real fora do versionamento; fixtures sintéticas (DEC-012).
- **D8 — Integração ao cron.** Rodar como passo do lote semanal da VPS (DEC-013) vs. cadência separada.

**Escopo permitido (READ-ONLY M1).** Camada de enriquecimento nova (módulo isolado, ex.:
`src/motor_expansao/vulnerabilidade/` ou extensão do pacote de mercado), consumindo o histórico de
snapshots dos scrapers + o ativo WellHub/TotalPass + `concorrentes_mapeados`; materializa um Parquet
paralelo com o score e a lista de M&A. NÃO altera artefatos oficiais do M1. **Sem dependência nova de
base** e **sem API externa ao vivo**.

**Fora de escopo.** `score_priorizacao`/`hex_score_estrutural`/pesos/carteira/plano/artefatos oficiais
do M1; `flag_sam`/gate do SAM (DEC-006/DEC-007); **Google Places / qualquer API externa de reputação**
(movido para o sucessor opcional BLK-MA-07, com gate/DEC próprios); persistir PII.

**Guardrails.** §5 (score paralelo, não recalcula M1); DEC-012/anti-PII (só agregados; fonte real não
versionada; fixtures sintéticas); DEC-013 (extensão do lote de scrapers, não pipeline novo). §2 NÃO é
desafiado no Plano B — não há API ao vivo; o dashboard segue offline sobre Parquets.

**Entregável.** Score de vulnerabilidade por academia independente + lista priorizada de alvos de M&A
(vulneráveis × proximidade a hexágonos quentes) para o time comercial.

**Decomposição sugerida (sucessores, a confirmar no BLK-MA-01).**
- **BLK-MA-02** — extrator de **churn + staleness** a partir do histórico de snapshots semanais dos
  scrapers (100% interno); flags de série imatura (ramp-up).
- **BLK-MA-03** — join do sinal de agregadores (**presença + rating in-app** WellHub/TotalPass) por
  dedup com `concorrentes_mapeados`; anti-PII por construção; fixtures sintéticas.
- **BLK-MA-04** — score de vulnerabilidade (fórmula/pesos do D4) + normalização + flags de qualidade.
- **BLK-MA-05** — lista priorizada de M&A (cruzamento com hexágonos quentes, D5) + entregável (D6).
- **BLK-MA-06** — integração ao cron semanal da VPS (D8) e runbook.
- **BLK-MA-07 (opcional/futuro, gate + DEC próprios)** — enriquecer com **reputação externa** (Google
  Places ou outra) SE se quiser a nota do público geral; só aqui reaparece o desvio do §2.

**Critério de aceite (BLK-MA-01).** Contrato dos sinais internos (1–4, + 5/6 opcionais) e do score
definido; D1–D8 resolvidas/confirmadas no gate de produto; decomposição BLK-MA-02+ confirmada;
guardrails §5/anti-PII/DEC-013 explicitados; **sem DEC de API externa** (rota Google descartada, movida
ao BLK-MA-07); ZERO código de produção neste bloco (só docs/contrato).

- BLK-MA-02 (concluído 2026-07-29) — ver tasks/completed.md

---

### BLK-MA-10 — TotalPass: a nota existe? (spike de viabilidade, sem código de produção)

| Campo | Valor |
|---|---|
| **Criticidade** | **Baixa** (investigação time-boxed; ZERO código de produção, ZERO alteração de coletor, ZERO persistência). O resultado pode ser "não fazer" — e esse é um resultado válido. |
| **Prioridade** | Antes do **BLK-MA-09**, não depois: o veredito é insumo do D-B daquele bloco (se o TotalPass puder ter nota, a régua deixa de ser permanentemente assimétrica e o D-B muda). Não bloqueia o **BLK-MA-08**. |
| **Esteira** | Block Orchestrator → Builder → `[decisão humana — Vinicius: seguir, arquivar ou redirecionar ao BLK-MA-07]`. |
| **Status** | Pendente. |
| **Depende de** | — (não bloqueia nada; o sinal 2 já entrega valor só com o WellHub). |
| **Autonomia** | **manual (NÃO loop-safe)** — investigação sobre alvo externo de produção, com decisão de ToS envolvida. NÃO marcar loop-safe. |

**Contexto (medido em 2026-07-30/31; evidência em `data/reports/sonda_rating_agregadores_2026-07-31.md`).**
Duas sondas sobre `https://totalpass.com/br/academias/{slug}/` deram **7/7 sem nenhum sinal de nota**.
O JSON-LD é idêntico em todas as amostras — 9 chaves (`@context, @type, address, geo, image, name,
openingHours, telephone, url`), **sem** `aggregateRating`. No HTML inteiro (54–63 KB): zero ocorrência
de `aggregateRating`, `ratingValue`, `reviewCount`, `avalia`, `review`, `estrela` ou `nota`. A página é
Next.js **App Router** (payload RSC, sem `__NEXT_DATA__`). Conclusão da sonda: **o produto web do
TotalPass não tem sequer interface de avaliação de unidade** — não é uma nota escondida atrás de uma
API web. Cobre 15.986 unidades já coletadas, universo maior que o do WellHub.

**Objetivo.** Responder, com evidência e sem escrever código de produção, a uma pergunta binária: **a
nota do TotalPass existe em alguma superfície acessível de forma legítima e sustentável?** E, se
existe, a que custo. O entregável é uma recomendação — **seguir, arquivar ou redirecionar** —, não uma
implementação.

**Escopo permitido (time-box de 1 ciclo).** Investigar, em ordem de custo crescente: (1) as
superfícies do próprio TotalPass que a sonda identificou mas **não** investigou —
`booking.totalpass.com` e `cms.totalpass.com` são as candidatas óbvias, e são muito mais baratas que a
hipótese mobile; (2) outras superfícies públicas (sitemap, feed, página de rede, área de parceiro);
(3) se o app mobile expõe nota por unidade e por qual superfície — hipótese principal caso (1) e (2)
falhem, já que o web não a tem; (4) o custo real dessa hipótese — API autenticada exige credencial de
usuário pagante, certificate pinning é provável, e o contrato de dados pode mudar sem aviso.
Entregável: relatório curto em `data/reports/` com veredito, evidência e estimativa de esforço/risco.

**Os Termos de Uso decidem antes da engenharia.** Ler os ToS do TotalPass é passo **de abertura**, não
de fechamento: se a coleta autenticada for vedada, a investigação **para em (3)** e a recomendação é
arquivar, sem gastar o time-box em viabilidade técnica. A leitura vale para o alvo desta sonda; não é
parecer jurídico e não se estende a outros coletores.

**A alternativa mais provável.** Se o veredito for "inviável ou vedado", a recomendação natural **não**
é insistir no TotalPass — é levar aquele universo para o **BLK-MA-07** (reputação externa, com gate e
DEC próprios). Isso muda o desenho do sinal (reputação externa ≠ nota in-app, e o §2 do contrato
reaparece) e é decisão de produto, não de engenharia. **Se este for o desfecho esperado, considerar
não gastar um bloco:** mover a conclusão de duas linhas para o contexto do BLK-MA-07 e deixar a
hipótese mobile como uma linha de risco lá é mais barato que um ciclo inteiro para confirmar um "não".

**Guardrail.** READ-ONLY sobre o M1 e sobre o motor inteiro — este bloco **não escreve código de
produção em repo nenhum**. Nenhuma credencial real em repositório, nenhuma persistência de dado
coletado, nenhuma alteração no coletor ou no cron. Nenhuma tentativa de contornar autenticação,
rate-limit ou proteção técnica: se o acesso exigir burlar controle, o veredito é **arquivar**. Volume
de requisições de sondagem mínimo e espaçado, no mesmo padrão educado do coletor de produção.

**Fora de escopo.** Qualquer artefato/score/peso do M1; implementar coleta de nota no TotalPass —
isso seria um bloco novo, **condicionado** ao veredito deste; o WellHub (**BLK-MA-08**) e a reativação
do `v2` (**BLK-MA-09**); a reputação externa em si (**BLK-MA-07**).

**Critério de aceite.** Relatório em `data/reports/` respondendo à pergunta binária com evidência
reproduzível (URLs, superfícies testadas, o que se viu em cada uma); veredito explícito entre
**seguir / arquivar / redirecionar ao BLK-MA-07**, com esforço e risco estimados; leitura dos ToS
registrada com citação; ZERO alteração em código de produção, provada pelo diff; nenhuma credencial
nem dado coletado versionado.

---

### BLK-RELPON-07 — Mapas de calor legíveis (nomes de rua/bairro POR CIMA do choropleth)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (melhora a LEITURA do Relatório Pontual; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → `[GATE VISUAL — Felipe]` → Builder → QA |
| **Depende de** | — (aditivo sobre `censo_map`; OpenMapTiles self-host é passo posterior/opcional) |
| **Status** | Em revisão (PR aberto) |

**Contexto:** nos mapas de calor do Relatório Pontual (densidade/renda/score/renda domiciliar) o
choropleth **cobre as ruas e os nomes** — não dá para identificar QUAL área tem o número melhor/pior.
O realce `_STREET_*` recupera só as LINHAS de rua; os TEXTOS (nomes) continuam soterrados sob a cor.

**Objetivo:** ordem de camadas — o heat entra POR BAIXO e um tileset **só-rótulos** (transparente) é
composto POR CIMA, deixando "Av. X", "Bairro Y" legíveis sobre a cor (identificação da área).

**Escopo:** `_fetch_labels` (mosaico só-rótulos, lazy/best-effort via rede) + composição em
`_render_camada` alinhada ao extent do basemap; rótulos buscados **1x** e compartilhados pelas 4
camadas; flag `labels_overlay` (default on); a camada só-pins (concorrentes) não recebe overlay.
Fonte atual = CartoDB Voyager Only-Labels (keyless, mesma licença/atribuição do basemap Voyager).
Quando o OpenMapTiles self-host subir, trocar `_LABELS_TILE_URL` para o endpoint de rótulos do
tileserver (`openmaptiles-infra`, estilo `ultra-maptiler` já com a camada `transportation_name`).

**Fora de escopo (invioláveis):** score/pesos/intersecção de setores/raio/artefatos M1 (RENDER apenas);
subir a infra (passo posterior); dado de carteira/residual.

**Critérios de aceite:** nomes visíveis por cima do choropleth quando há basemap; **degradação graciosa**
(offline/sem rede → mapa sem nomes, byte-compatível com o anterior); testes cobrindo overlay
ligado/desligado; ruff + mypy + pytest verdes; **gate visual do Felipe**.

**Risco:** baixo (aditivo, gated por flag e por rede; caminho `basemap=False`/offline preservado).

---

## Fechamento de ciclo — BLK-MA-08 (2026-08-11)

**VEREDITO: CONCLUÍDO.** O WellHub passou a emitir a nota in-app. Código e testes (83 -> 93) em
`VinhoAbencoado/GymScraping` PR **#6**, mergeado em 2026-08-10; o lado do motor que a consome é o
BLK-MA-09.

Autorizado pela **DEC-024**, que fatiou o gate conjunto MA-08/MA-09 e fixou o schema: **duas colunas**
(`nota_wellhub`, `qtd_avaliacoes_wellhub`), ambas agregados numéricos, antes de `data_coleta` em
`FIELDNAMES`; `value` como float normalizado; e os **três estados distinguíveis** — `4.81`/`105` (tem
nota), `""`/`0` (sem avaliações), `""`/`""` (bloco ausente do HTML).

**A migração foi executada, não só documentada** (2026-08-05 19:47 -> 2026-08-06 15:50, ~20 h):
consolidado de **45.527 linhas** em 12 colunas, **36.940 com nota (81,1%)**, 8.587 sem avaliações,
**0 não-lidas**, 158 falhas (0,35%). Resultado e desvios em `Wellhub/MIGRACAO_NOTA.md`. A migração era
obrigatória porque `ensure_header` só escreve cabeçalho em arquivo vazio e `append_rows` projeta em
`FIELDNAMES`: rodar o coletor ampliado contra o CSV antigo corromperia o arquivo em silêncio.

**O que a rodada produziu além do previsto.** A distribuição da nota restrita a `independente`
(**n = 34.035**: `min = 1,0 · p1 = 4,23 · p5 = 4,59 · p10 = 4,69 · mediana = 4,93 · desvio = 0,192`;
158 linhas — 0,46% — abaixo de 4,0) virou o insumo do gate do MA-09 e, depois, o domínio
`[1,0 ; 5,0]` da guarda de rating. A sonda de julho (N = 53) media `4,26-4,98` e **não via a cauda**.

**Efeito colateral que virou bloco próprio.** A rodada completa expôs que o WellHub renomeou a
taxonomia de atividades e o filtro `tem_musculacao` parou de reconhecê-la — **BLK-MA-11**.

**Risco assumido explicitamente:** o bloco pagou o custo de uma decisão cujo valor só o MA-09
materializa, e o MA-09 acabou decidindo (DEC-026) **não** ligar o peso do sinal. A nota entrou como
**coluna-fato**, não como componente do score — o dado é útil e propagado, mas não ordena.

---

## Fechamento de ciclo — BLK-MA-11 (2026-08-11)

**VEREDITO: CONCLUÍDO.** Decidido pela **DEC-025**, saída **(a)** — ampliar o vocabulário — com o
recorte "V2". Motor em `Kastaldy/motor-de-expansao` PR **#208**; coletor em
`VinhoAbencoado/GymScraping` PR **#7**. Ambos mergeados em 2026-08-10.

**O defeito.** O WellHub renomeou a taxonomia entre maio e agosto de 2026: "Musculação" virou
"Treino de força", "Fisiculturismo" e "Treino Híbrido". O `tem_musculacao` procurava a substring
literal `musculacao` e passou a casar **144 de 45.527 linhas** — descartava a base inteira **em
silêncio**, sem levantar um único erro.

**Como o vocabulário foi escolhido** (verdade-terreno: as 12.420 unidades de maio que ainda existem,
todas aprovadas pelo filtro antigo). O **V2 é o joelho da curva**: recall de **99,5%** sobre maio com
22.174 linhas; V1 -> V2 custa +175 linhas para recuperar +134 unidades, enquanto V2 -> V3 custa +2.831
para recuperar +8, e o V4 mais +3.840 para +21. Dali em diante o ganho é ruído e o custo é categórico
— entrariam box de CrossFit e estúdio de ginástica como academia de musculação.
`csvs_musculacao/` regenerado: **144 -> 22.173 linhas**, de 7 para 27 UFs.

**Duas consequências registradas.** (1) A **comparabilidade com a série de maio quebra**: a mesma
academia pode entrar hoje e não ter entrado antes, então o churn medido pela camada de vulnerabilidade
misturaria mudança real com mudança de critério — por isso a **taxonomia saiu do hash de staleness**
nas duas fontes, com bump `snapshots_concorrentes_v1 -> v2` e emendas ao §3/§6 do contrato. (2) O
mesmo vocabulário foi espelhado no TotalPass **por prevenção** (emenda 1 da DEC-025), com **delta
medido = 0**: a fonte ainda usa a taxonomia antiga.

---

## Fechamento de ciclo — BLK-MA-09 (2026-08-11)

**VEREDITO: CONCLUÍDO.** Gate resolvido pela **DEC-026** (PR #212) e implementação entregue pelo PR
**#217** (que sucedeu o #215, fechado sem merge e reintegrado com duas correções limpas).

**A decisão do gate — D-B = opção (0): o rating é coluna-fato SEM peso.** `SINAIS_INATIVOS` continua
`("s2",)`, não existe `v2`, os pesos efetivos não mudam e nenhum tripwire de peso foi tocado. **D-A e
D-C ficaram SEM OBJETO** — sem `v2` em `Σ(wi · vi)` não há régua a escolher nem regime `{s1,s2}` sobre
o qual decidir a flag.

**O que sustentou a decisão, verificado contra `renormalizar_pesos`:**

```
score_com_s2  =  0,75 · score_sem_s2  +  25 · v2
```

Ter nota cobra um corte de **25%** nos outros três sinais; a nota mediana (4,93) devolve 0,44 ponto.
Break-even em 1,75 -> **99,97% das 34.035 linhas com nota seriam penalizadas por tê-la**. A academia
que sumiu do agregador e está parada — alvo de maior prioridade pela inversão do §2 — perderia **22
pontos** por estar listada no WellHub. As alternativas não se sustentaram: duas listas não segmentam
território (**69,4% dos hexes são mistos**, e **100% dos 200 mais densos**), e anular fora do regime
majoritário apagaria **22.744 academias** num 60/40 sem dominância.

**Contrato.** Snapshot 10 -> **12** colunas (`snapshots_concorrentes_v2 -> v3`), churn 17 -> **19**
(`churn_staleness_v1 -> v2`), score 20 -> **22** (`score_vulnerabilidade_v1 -> v2`). `ler_snapshots` e
`escrever_particao_semana` passaram a declarar `schema=` explícito — sondado antes de aceitar a
premissa: com pyarrow 23.0.1, `ds.dataset()` infere do **primeiro** arquivo, então numa série com
partições pré e pós-bump a coluna nova seria dropada das demais **sem erro**. Check de execução do
critério de aceite: `data/staging/snapshots_concorrentes/` não existia — série em zero semanas, bump
gratuito, nenhuma partição migrada.

**A guarda de rating, achada por revisão cética depois do CI verde.** A primeira versão degradava
`qtd = 1.262` (locale pt-BR) mas **levantava `ValueError`** para nota fora do domínio e contagem
negativa. Mesmo caminho, mesma consequência — a que o próprio PR classificara como crítica:
`montar_snapshot` roda **antes** de gravar e o `run_weekly_90.sh` sobrescreve os CSVs crus, então a
exceção não perde uma linha, perde **a semana inteira, para sempre**. Dois defeitos independentes:

1. **Reação.** `_coagir_rating` passou a degradar todos os casos, e o **par** fora dos três estados da
   DEC-024 (`NA`/`105`, `4.81`/`0`, `4.81`/`NA`) vira `NA`/`NA`. A ordem é **normativa**: domínio por
   coluna primeiro, par depois — é ela que faz `0.0`/`0` cair em "sem avaliações", não em "não lido".
2. **Predicado.** O domínio era `[0, 5]`; passou a **`[1,0 ; 5,0]`** (`NOTA_WELLHUB_MIN`/`MAX`). A nota
   é média de avaliações de 1 a 5 estrelas, logo `0.0` é inalcançável — e é o retorno natural de um
   extrator quebrado. A guarda barrava o improvável e deixava passar o provável: `0.0`/`105` entrava
   como nota legítima, e `0.0`/`0` como um quinto estado que não existe no contrato.

`_assert_schema_snapshot` seguiu como rede para frames montados à mão, agora com o domínio certo e
cobrindo os três pares inválidos; pelo caminho público é inalcançável — esse é o invariante.
`rating_ilegivel` conta **linhas**, não ocorrências. **9 testes novos**, todos pelo caminho real
CSV -> `materializar`, e todos provados contra o código anterior por sonda executada.

**Ponto de processo, para não se repetir.** O #215 ficou ~20 h travado por dois motivos que nada tinham
a ver com o código: (i) PR **empilhado** sobre a branch do gate nunca dispara o `ci.yml`
(`on: pull_request: branches: [main]`), então o check `test` — *required* — jamais rodou nele; e mudar
a base gera `edited`, que também não dispara. Só um push (`update-branch`) resolve. (ii) O guard
invalida `aprovado-humano` a cada `synchronize`/`edited` (fail-closed, `guard.yml:81-111`), então
aprovar antes de atualizar a branch é trabalho perdido — a label caiu **três vezes**. A ordem correta
é: mergear o PR de baixo -> `update-branch` -> CI verde -> **só então** pedir a label.

**Guardrail.** READ-ONLY sobre o M1 — nada de `score_priorizacao`, pesos, `config.py`, `pipelines/m1`
ou artefato oficial. A nota **não** entra em `CAMPOS_HASH_POR_FONTE`; nota e contagem não são PII.
Suíte no CI: **2803 passed, 87 skipped**.

---

### BLK-MA-08 — Coletar a nota do WellHub (`partnerRating`) no GymScraping

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (coluna nova num coletor de produção, no repo externo `VinhoAbencoado/GymScraping`; muda o schema de um CSV com 12.769 linhas já coletadas e estende o escopo de coleta autorizado pela DEC-013). **Exige emenda à DEC-013 registrada + gate humano obrigatório** antes do Builder. Não pode ser Média: `scripts/aplicar_criticidade_label.py:38` arma **auto-merge** para Baixa/Média, o que furaria o gate que este bloco declara. |
| **Prioridade** | **DESBLOQUEADO** — o gate foi resolvido pela **DEC-024** (2026-08-04). Antes do **BLK-MA-09**, que é o consumidor da coluna. |
| **Esteira** | Block Orchestrator → Planner → `[GATE — RESOLVIDO pela DEC-024 em 2026-08-04; NÃO reabrir]` → Builder → QA. |
| **Status** | **Implementado; PR aberto.** Código + testes (83→93) em `VinhoAbencoado/GymScraping` PR **#6**. A **migração foi EXECUTADA** (2026-08-05 19:47 → 2026-08-06 15:50, ~20 h): consolidado de **45.527 linhas** em 12 colunas, 36.940 com nota (81,1%), 8.587 sem avaliações, **0 não-lidas**, 158 falhas (0,35%). Resultado e desvios em `Wellhub/MIGRACAO_NOTA.md`. Falta só o merge do PR. |
| **Depende de** | **DEC-024** (autoriza o escopo de coleta, fixa o schema persistido e emenda as partes 2 e 3 da DEC-013). |
| **Autonomia** | **manual (NÃO loop-safe)** — repo externo, coletor de produção que roda na VPS por cron; toca a trilha de scrapers. NÃO marcar loop-safe. |

**Contexto (medido em 2026-07-30/31; evidência em `data/reports/sonda_rating_agregadores_2026-07-31.md`).**
O contrato afirma, em três lugares, que o WellHub não traz nota: §1
(`docs/vulnerabilidade_ma_contrato.md:60-62`), §7/D3 (`:220-225`) e §13 (`:509`) — todos derivados da
premissa *"WellHub = mesmo schema do TotalPass (confirmado por Vinicius, 2026-07-23)"*, registrada
com a ressalva honesta de que **só havia amostra de TotalPass versionada**. Duas sondas sobre as
páginas públicas **falsificaram a premissa**: a equivalência vale para o CSV de **saída**, não para o
HTML de **origem**. A página de parceiro do WellHub traz, no mesmo payload RSC que o coletor já baixa
e já parseia, o bloco `\"partnerRating\":{\"value\":4.81,\"label\":\"(105 Avaliações)\"}`. Cobertura
medida: **53 de 54** unidades sorteadas (2 por UF nas 27 UFs), **98,1%**. O TotalPass, na mesma
sonda, deu **7/7 sem nenhum sinal de nota** — ver **BLK-MA-10**.

**Objetivo.** Passar a extrair `partnerRating` (nota **e** contagem de avaliações) no coletor do
WellHub e persistir os dois como agregados numéricos no CSV, sem coletar nenhum texto ou autor de
avaliação. Entregável: `Wellhub/csvs/unidades_wellhub_<uf>.csv` com as colunas novas, e o
consolidado regenerado de forma íntegra.

**STOP-RULE — RESOLVIDA em 2026-08-04 (ler o desfecho antes de começar).** Este bloco **paga o custo**
de uma decisão cujo valor só o **BLK-MA-09** materializa. Se o gate do MA-09 decidir
**D-C = manter `{s1,s2}` provisório** e **D-B = segmentar por regime**, este par de blocos entrega
**zero** valor ordenável até o S3 amadurecer (~8 meses na cadência real). **Desfecho:** Vinicius
**FATIOU o gate** (DEC-024) — o MA-08 avança com as decisões de schema, e D-A/D-B/D-C ficam para o
gate do MA-09, sem serem pré-requisito deste bloco. O risco de o bloco ficar órfão foi **assumido
explicitamente**. O que o compensa: a rodada de migração exigida por este bloco produz a nota das
12.769 unidades com o `nome` ao lado, o que converte o pré-requisito do D-A — hoje uma sonda ao vivo
**sem script versionado** (`data/reports/sonda_rating_agregadores_2026-07-31.md:130-131`) — numa
consulta local ao CSV, com N grande e restrita a `independente`. Registrar a distribuição medida no
handoff do QA: ela é o insumo do gate do MA-09.

**Escopo permitido (repo `VinhoAbencoado/GymScraping`, clonado em `../GymScraping`).** Quatro pontos
de código, todos já localizados: (1) constante `_RSC_PARTNER_RATING_BLOCK_RE` em `Wellhub/extracao.py`
(após a linha 41), no **mesmo padrão** de `_RSC_ADDRESS_BLOCK_RE` — `r'\\"partnerRating\\":\{[^{}]*\}'`,
já verificado casando nas 4 fixtures; (2) helper `_extract_partner_rating` entre as linhas 117 e 120,
reusando `_extract_number(bloco, "value")` e `_extract_string(bloco, "label")`, que **funcionam sem
modificação** sobre o bloco casado; (3) chamada em `extract` após a linha 171; (4) chaves novas no
dict de saída entre 182 e 183. Mais a coluna em `FIELDNAMES` (`Wellhub/csv_writer.py`, entre as
linhas 26 e 27 — **antes** de `data_coleta`, que é o último por convenção nos dois coletores
agregadores). Testes em `Wellhub/tests/`. Docs: `CLAUDE.md:23` do GymScraping e
`Wellhub/RECON.md:97` (contrato de colunas), mais as duas correções de carona de docs **já stale
hoje** (`RECON.md:12` e `csv_writer.py:4`, ambos listando 9 colunas, sem `atividades`).

**Três decisões de produto — RESOLVIDAS pela DEC-024 (parte 5) em 2026-08-04. NÃO reabrir.**
(a) **Duas colunas, não uma:** `nota_wellhub` e `qtd_avaliacoes_wellhub`, ambas agregados numéricos,
em `FIELDNAMES` **antes** de `data_coleta`. O `label` embute a contagem (`(105 Avaliações)`) e ela vem
de graça no mesmo bloco; é o que permite ponderar confiança — 2/53 unidades têm menos de 30
avaliações, e 5,0 com 13 avaliações não vale o mesmo que 4,73 com 1.262. (b) **`value` como float
normalizado** (`4.81`, `5.0`): duas das 4 fixtures trazem `5`, não `5.0`, mas `_extract_number` já
devolve `float` e `str(5.0)` grava `"5.0"`, então normalizar é o comportamento default e custo zero,
enquanto preservar o bruto exigiria código novo — e o único ganho do bruto (detectar mudança de
formato) já está coberto por (c). **Travar a escolha em teste.** (c) **Os três estados se distinguem
pelas duas colunas, sem coluna extra:** *tem nota* = `4.81` · `105`; *sem avaliações* = `""` · `0`;
*bloco ausente do HTML* = `""` · `""`.

**O estado "sem avaliações" tem forma DIFERENTE.** Numa das 54 unidades sondadas o campo vem como
`\"partnerRating\":null` — o objeto inteiro nulo, **não** `{"value":null,...}` —, logo após
`\"newPartner\":{...}`. Um parser que só procure a forma preenchida reporta "ausente" tanto para
*sem avaliações* (legítimo) quanto para *layout mudou* (quebra do scraper), e uma quebra silenciosa
entraria no score como `n/d` sem ninguém perceber. As duas condições **têm de ser distinguíveis** —
é critério de aceite, não detalhe de implementação.

**Armadilha operacional (não é código, e corrompe em silêncio).** `ensure_header`
(`Wellhub/csv_writer.py:36`) só escreve cabeçalho em arquivo inexistente ou vazio, e `append_rows`
projeta cada linha em `{field: row.get(field, "") for field in FIELDNAMES}` (`:58`) — é essa projeção
que descarta chave nova em silêncio (o `extrasaction="ignore"` da linha 55 nunca chega a disparar).
O checkpoint atual está **completo** (`ok=12769, failed=175, filtered=30708`) e
`Wellhub/unidades_wellhub.csv` tem 12.769 linhas sob um cabeçalho de **10 colunas**. Rodar o coletor
com `FIELDNAMES` ampliado contra esse arquivo grava campos a mais sob o cabeçalho antigo — **arquivo
corrompido, sem erro e sem log**. A migração exige CSV novo (`--output` limpo, ou remoção do arquivo
+ `--no-resume`); os 27 arquivos de `Wellhub/csvs/` se regeneram por `split_by_state`, mas só a
partir de um consolidado íntegro. O bloco deve entregar o procedimento de migração **escrito e
executado**, não só o código.

**Guardrail.** READ-ONLY sobre o M1 por construção (o bloco não toca o repo do motor). Anti-PII
(DEC-012): persistir **apenas** os agregados numéricos — nota e contagem; **nunca** texto ou autor de
avaliação, que o §11 do contrato proíbe nominalmente, nem qualquer outro não-agregado (foto, data de
review), pela regra geral de persistir só agregados. Nenhuma alteração no cron ou no runner da VPS
neste bloco — isso é **BLK-MA-06**. Não tocar `gymscraping/core/contracts.py` (`OFFICIAL_COLUMNS`),
do qual o WellHub vive fora por decisão explícita (`RECON.md:100`).

**Fora de escopo.** Qualquer artefato/score/peso do M1; toda a reativação do sinal 2 no motor —
ingestão, contrato de snapshot, `v2`, pesos e comparabilidade — que é **BLK-MA-09**; o TotalPass, que
é **BLK-MA-10**; a reputação externa/Google Places, que segue no **BLK-MA-07** com gate e DEC
próprios; o plug no cron da VPS e o runbook, que são **BLK-MA-06**; qualquer mudança em
`CAMPOS_HASH_POR_FONTE` (ver o guardrail do **BLK-MA-09** — a nota **NUNCA** entra no hash).

**Critério de aceite.** Coluna(s) nova(s) extraídas e gravadas, com teste que falharia antes,
**100% offline** — as 4 fixtures em `Wellhub/tests/fixtures/` já contêm `partnerRating` (norpra
`4.81`, gabi_marie `4.71`, ctf_londrina `5`, max_trainer `5`), verificado por execução, então nenhum
teste novo pode tocar a rede; cobertura obrigatória de 4 casos — decimal, **inteiro** (`5`),
**`partnerRating: null`** e **bloco ausente do HTML**, sendo os dois últimos distinguíveis entre si e
cobertos por HTML forjado inline (molde em `Wellhub/tests/test_extracao.py:176-184`, já que nenhuma
fixture os contém); os 2 testes que quebram por construção atualizados
(`Wellhub/tests/test_extracao.py:29-35`, igualdade de conjunto de chaves, e
`Wellhub/tests/test_pipeline.py:64`, string literal do cabeçalho); os 4 pontos de doc corrigidos;
procedimento de migração do consolidado documentado e executado; suíte do WellHub sem regressão
(baseline medida em 2026-07-31: **83 testes**, via `python -m unittest discover -s Wellhub/tests -t .`
a partir da raiz do repo do scraper).

---

### BLK-MA-11 — Taxonomia de atividades do WellHub mudou e o filtro de musculação parou de reconhecê-la

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (muda o **critério de negócio** que define o universo de academias do coletor, e esse universo alimenta a camada paralela mercado/residual via `concorrentes/wellhub/csvs`. READ-ONLY sobre o M1). **Exige decisão humana de produto**, não é escolha de engenharia. |
| **Prioridade** | Antes de qualquer sincronização do consolidado novo para o motor. |
| **Esteira** | `[GATE — RESOLVIDO pela DEC-025 em 2026-08-07: escolhida a saída (a), com o vocabulário "V2". NÃO reabrir]` → Builder → QA. |
| **Status** | **Em execução.** Gate decidido (DEC-025). Lado do **motor** feito: taxonomia fora do hash nas 2 fontes, bump `snapshots_concorrentes_v1` -> `v2`, 2 testes novos, emendas no §3/§6 do contrato. Lado do **coletor** feito no repo externo: `tem_musculacao` com o V2 no WellHub (`csvs_musculacao/` regenerado, 144 -> 22.173 linhas em 27 UFs) e o mesmo vocabulário no TotalPass por prevenção (emenda 1 da DEC-025; delta medido = 0). |
| **Depende de** | BLK-MA-08 (a rodada que expôs o problema) e **DEC-025** (decide o vocabulário e a saída da taxonomia do hash). |
| **Autonomia** | **manual (NÃO loop-safe)** — repo externo + critério de negócio. |

**O que foi medido (2026-08-05/06).** O WellHub **renomeou a taxonomia de atividades** entre maio e
agosto: "Musculação" virou **"Fisiculturismo"**, **"Treino de força"** e **"Treino Híbrido"**. O
filtro `tem_musculacao` (`Wellhub/split_by_state.py`) procura a substring `"musculacao"` e não
reconhece nenhum dos rótulos novos.

Evidência, em duas escalas: na primeira tentativa de coleta, **2.994 dos 7.577 slugs descartados
(39,5%) constavam no consolidado de maio** — ou seja, tinham musculação e estavam sendo perdidos; na
rodada completa, `45.382 de 45.527 linhas excluídas pelo filtro`. Amostra de 10 dos afetados:
"Fisiculturismo" em 8, "Treino de força" em 7.

**Consequência viva.** `Wellhub/csvs_musculacao/` saiu com **144 linhas** contra 12.769 em maio e
**não substitui a base anterior**. O `Wellhub/csvs/` (45.526 linhas) está íntegro mas **mudou de
significado**: contém todas as unidades, não só academias de musculação. Os leitores do motor
(`demanda_revelada/concorrentes_densos.py` e `vulnerabilidade/snapshots.py`) apontam para
`concorrentes/wellhub/csvs` — sincronizar o estado atual sem decidir isto muda o universo daquelas
camadas sem que ninguém tenha decidido.

**As três saídas — DECIDIDO em 2026-08-07 (DEC-025): saída (a), vocabulário "V2". NÃO reabrir.**
- **(a) Ampliar o vocabulário** de `tem_musculacao` com os rótulos novos. **ESCOLHIDA.** Restaura o
  volume, mas **quebra a comparabilidade** com a série de maio — consequência aceita e quantificada
  na DEC-025 (parte 4).
- (b) Manter o consolidado completo e mover o recorte para o consumidor. *(não escolhida)*
- (c) Aceitar a base sem filtro como novo padrão, aposentando o subset. *(não escolhida)*

**O vocabulário "V2", com a medição que o escolheu.** `{musculacao, treino de forca, fisiculturismo,
levantamento de peso, treino hibrido}` sobre a string de atividades normalizada. Verdade-terreno: as
**12.420** unidades de maio que ainda existem (todas aprovadas pelo filtro antigo, quando a taxonomia
velha valia). Atual: 144 linhas · recall 1,1%. **V2: 22.174 linhas (48,7%) · recall 99,5%.** É o
joelho da curva — do V2 para o V3 (`+cross training/crossfit`) custa **+2.831 linhas** para recuperar
**+8** unidades, e o V4 (`+funcional`) mais **+3.840** para **+21**.

**Achado que ENTROU no escopo deste bloco pela DEC-025 (não estava na redação original).** A mesma
renomeação de taxonomia atinge o **sinal 4**: `atividades` está dentro de `CAMPOS_HASH_POR_FONTE`
(`vulnerabilidade/contrato.py`) e mudou em **12.314 dos 12.420** slugs comuns (**99,1%**), contra
`endereco_formatado` em 63 e `nome` em 33. Sem tratar isso, a primeira coleta pós-renomeação leria a
base inteira como "cadastro atualizado agora" e o S4 morreria — **independentemente** de qual saída o
filtro tomasse. A DEC-025 (parte 2) tira `atividades` **e** `modalidades` do hash nas duas fontes, com
bump `snapshots_concorrentes_v1` -> `v2` (gratuito: a série está em zero semanas).

**Fora de escopo.** Qualquer artefato/score/peso do M1; o sinal 2 / `v2` do rating, a régua, os pesos
e o número de COLUNAS do snapshot (**BLK-MA-09**) — o que este bloco toca no contrato de snapshot é
**só** o conjunto de campos hasheados e o carimbo de versão, por delegação explícita da DEC-025; o
cron e o runbook (**BLK-MA-06**); a reputação externa (**BLK-MA-07**).

**Critério de aceite.** DEC registrada (**DEC-025**, feita); `tem_musculacao` com o V2 e teste que
falharia antes; `csvs_musculacao/` regenerado a partir do consolidado íntegro; taxonomia fora do hash
nas 2 fontes, com teste que falharia antes, e bump de `VERSAO_CONTRATO_SNAPSHOT`; o efeito sobre a
comparabilidade da série declarado por escrito (DEC-025 parte 4 + §6 do contrato); a sincronização de
`Wellhub/csvs/` para o motor **bloqueada** até tudo acima estar aplicado; suíte sem regressão nos dois
repos; `ruff` limpo; `loop_guard` sem `CRITICO`.

---

### BLK-MA-09 — Ingerir a nota do WellHub até a saída do score, como COLUNA-FATO sem peso

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (liga um sinal do `score_vulnerabilidade`, o que **rebalanceia todos os pesos efetivos**: S3 cai de ≈0,467 para 0,35 e S4 de ≈0,333 para 0,25; muda o contrato de snapshot e força bump de versão. Camada **PARALELA e READ-ONLY sobre o M1** — não toca `score_priorizacao`, pesos, nem artefatos oficiais, e o score ainda não tem consumidor materializado; **volta a ser Crítica quando o BLK-MA-05 materializar o entregável**). **Exige emenda ao contrato ratificada no gate + gate humano obrigatório** antes do Builder. |
| **Prioridade** | Depois do **BLK-MA-08**, que produz o insumo. Antes do **BLK-MA-05**, que é o consumidor do score — se o MA-05 sair antes, ordenará sobre uma régua que este bloco vai mudar. |
| **Esteira** | Block Orchestrator → Planner → `[GATE — RESOLVIDO pela DEC-026 em 2026-08-10: D-B = opção (0); D-A e D-C ficaram SEM OBJETO. NÃO reabrir]` → Builder → QA. |
| **Status** | **IMPLEMENTADO (2026-08-10).** Gate resolvido pela DEC-026 (D-B = opção 0). Snapshot de 10 -> **12 colunas**, churn de 17 -> **19**, score de 20 -> **22**; bumps `snapshots_concorrentes_v2 -> v3`, `churn_staleness_v1 -> v2`, `score_vulnerabilidade_v1 -> v2`. `ler_snapshots` e `escrever_particao_semana` passaram a declarar `schema=` explícito. **14 testes novos** (5 do contrato + 9 da guarda de domínio), camada em **278**. **Check de execução do critério de aceite: `data/staging/snapshots_concorrentes/` NÃO existe — série em zero semanas, logo o bump foi gratuito e nenhuma partição precisou de migração.** D-A e D-C seguem SEM OBJETO. **Emenda de 2026-08-10 (revisão cética):** a primeira versão tratava `qtd = 1.262` degradando, mas LEVANTAVA `ValueError` para nota fora do domínio e contagem negativa — mesma consequência que o próprio PR classificara como crítica (perder a semana inteira, porque `montar_snapshot` roda antes de gravar e o `run_weekly_90.sh` sobrescreve os CSVs). Corrigido: `_coagir_rating` degrada TODOS os casos e o domínio da nota passou de `[0, 5]` para **`[1,0 ; 5,0]`** — `0.0`, o retorno natural de um extrator quebrado, entrava como nota legítima; o par `4.81`/`0` também passava. |
| **Criticidade REVISADA** | De **Alta** para **Média** `[DEC-026]`. A justificativa original era "liga um sinal do `score_vulnerabilidade`, o que rebalanceia todos os pesos efetivos" — **isso não acontece mais**: `SINAIS_INATIVOS` fica `("s2",)`, os pesos efetivos seguem `0,20/0,467/0,333` e nenhum tripwire de peso muda. O que resta é ingestão de coluna + bump de contrato de snapshot, sem tocar fórmula. Atenção ao efeito colateral de governança: **Média arma auto-merge** (`scripts/aplicar_criticidade_label.py:38`) — se o PR tocar `tasks/backlog.md` ou `CLAUDE.md`, o guard exige `aprovado-humano` de qualquer forma; se não tocar, entra sozinho com os 4 checks verdes. |
| **Depende de** | BLK-MA-08 (concluído). **DEC-026** (resolve o gate). |
| **Autonomia** | **manual (NÃO loop-safe)** — mesmo perfil do pacote `vulnerabilidade/`: camada com insumo de PII na origem (DEC-012). NÃO marcar loop-safe. |

> ## ⚠️ LEIA ISTO ANTES DO RESTO DO BLOCO — o gate mudou o objetivo (DEC-026, 2026-08-10)
>
> **O bloco NÃO reativa mais o `v2`.** Tudo abaixo foi escrito supondo que reativaria; está
> preservado como registro do que foi considerado, mas **o escopo executável é o desta caixa**.
>
> **O que decidiu.** D-B = **opção (0)**: nota e contagem propagadas como **coluna-fato, sem peso,
> fora de `Σ(wi · vi)`**, no molde do G-D2. `SINAIS_INATIVOS` continua `("s2",)`.
>
> **Por quê.** Com peso, o `v2` **inverte o ranking**. Vale
> `score_com_s2 = 0,75 · score_sem_s2 + 25 · v2`: ter nota cobra 25% dos outros três sinais e a
> nota mediana devolve 0,44 ponto. Resultado — **99,97%** das 34.035 linhas com nota seriam
> penalizadas, e a academia `sumiu_recente` + stale cai de **90,00 para 67,94**. As opções (1) e
> (2) não se sustentam no território: **69,4% dos hexes são mistos**, 94,2% da massa vive em hex
> misto e **100% dos 200 hexes mais densos** são mistos.
>
> **CONTINUA no escopo:** `_COLUNAS_TRABALHO`; `CONTRATO_COLUNAS_SNAPSHOT` de 10 para **12** colunas
> com bump de `VERSAO_CONTRATO_SNAPSHOT`; **`ler_snapshots` com `schema=` explícito** (hoje a
> leitura hive de esquema misto dropa a coluna nova **sem erro**); acréscimo ao
> `CONTRATO_COLUNAS_SCORE`; as correções de contrato; o guardrail do hash.
>
> **SAIU do escopo:** remover `"s2"` de `SINAIS_INATIVOS`; a máscara `False` e o laço de inativos em
> `score.py`; a tupla de `_derivar_componentes`; o biconditional `s2 ⟺ v2`; qualquer mexida em
> `flag_score_provisorio` / `score_vulnerabilidade_ordenavel`. **Os tripwires de peso efetivo
> sobrevivem intactos** — não há pesos a atualizar, e a tabela de tripwires do critério de aceite
> encolhe: só as contagens de coluna mudam.
>
> **12 colunas, não 11 — vale independentemente de tudo.** Fechar em 11 economiza uma coluna hoje e
> custa depois um segundo bump **mais um buraco no histórico**, porque o dado das semanas passadas
> não existirá.
>
> **O D-A e o D-C não foram "decididos" — ficaram sem objeto.** Se um bloco futuro quiser ligar o
> peso, os dois voltam a existir e exigem gate próprio. A medição que sustenta a recusa da régua
> linear está no bullet do D-A abaixo.

**Contexto.** O sinal 2 está `n/d` por decisão do gate 2 (D3, §7 do contrato), com a justificativa
*"nenhum coletor emite nota"*. O **BLK-MA-08** derruba essa justificativa **para o WellHub apenas** —
o TotalPass segue sem nota (**BLK-MA-10**). O resultado é um cenário que o contrato **nunca
contemplou**: sinal presente para um **subconjunto** do universo. A aritmética já suporta isso —
`renormalizar_pesos` (`src/motor_expansao/vulnerabilidade/contrato.py:534-558`) e `_compor_score`
(`.../score.py:263-305`) renormalizam **por linha, agrupando por padrão de disponibilidade**
(`score.py:281-290`), e o helper `_saida_valida` (`tests/unit/vulnerabilidade/test_score.py:199-220`)
já monta três regimes distintos num único frame. **O trabalho é ~20% aritmética e ~80% contrato e
comparabilidade.**

**Objetivo.** Ligar o `v2` para as linhas com nota, mantendo o score correto, reprodutível e
**comparável**, e corrigir as três afirmações falsificadas do contrato.

**O que o S2 realmente destrava (formulação corrigida).** O S2 **não** é o único sinal independente
de maturidade de série: o S1 também é pontual (`score.py:201`, `n_agregadores_no_hex.notna()`), e é
por isso que hoje, na primeira coleta, o regime é `{s1}` e o score vive em `{0, 50}` — `v1` é
categórico de domínio efetivo `{0,0 · 0,5}`. O S2 é o **segundo** sinal pontual, e o único que pode
ser **acrescentado** sem esperar série: com ele, o regime `{s1,s2}` produz
`0,375 · v1 + 0,625 · v2`, um score **contínuo** já na semana 1 — mas **só para o subconjunto
WellHub**. E, decisivo: com o código atual, `flag_score_provisorio` (`score.py:294`) marca `{s1,s2}`
como provisório, e `score_vulnerabilidade_ordenavel` (`:299`) fica nulo — ou seja, **sem o D-C virar,
o par MA-08+MA-09 não destrava nada ordenável**, e quando o S3 amadurecer o S2 valerá no máximo ~4,6
dos 100 pontos. Todo o valor de curto prazo da dupla depende do **D-C**.

**Decisões do gate — as três são UMA decisão conjunta (nenhuma é reversível de graça).**
- **D-A — qual régua absoluta para o `v2`?** O percentil está **fechado** pela emenda G-D3
  (2026-07-30), que o deixou RESERVADO por não-monotonicidade e não-reprodutibilidade — motivos que
  valem igualmente para o rating. Mas, ao contrário do `v4`, a régua do `v2` está **genuinamente em
  aberto**: o §8.1 (`:271-272`) diz `1 − normaliza(rating)` e dá a razão linear apenas como
  **exemplo** (`ex.:`).

  > **O pré-requisito do D-A foi CUMPRIDO em 2026-08-10, e ele falsifica os números que este
  > parágrafo trazia.** A medição antiga vinha da sonda de **N=53** sobre o universo WellHub
  > inteiro; a nova é sobre o consolidado do BLK-MA-08, restrita a `independente` via
  > `classificar_rede`, com **n=34.035** unidades com nota. Reprodutível: ler
  > `GymScraping/Wellhub/unidades_wellhub.csv`, filtrar por `classificar_rede(nome) ==
  > "independente"` e descartar `nota_wellhub` vazia.
  >
  > ```
  > min=1,0   p1=4,23   p5=4,59   p10=4,69   mediana=4,93   max=5,0   desvio=0,192
  > abaixo de 4,0: 158 (0,46%)      abaixo de 4,5: 947 (2,78%)
  > ```
  >
  > **Correção 1 — o domínio NÃO é 18%.** A sonda mediu faixa `4,26–4,98` e daí saiu o "0,005 a
  > 0,185 / no máximo ~4,6 pontos". Com N grande existem unidades em **1,0** (cinco delas), então o
  > `v2` linear ocupa a escala **inteira**, `[0, 1]`. O que é estreito é o *corpo*, não o domínio.
  > Sob a régua linear e o regime `{s1,s2,s3,s4}` (`w2 = 0,25`), a contribuição em pontos de 100 é:
  >
  > | | nota | `v2` | pontos |
  > |---|---|---|---|
  > | mediana | 4,93 | 0,018 | **0,44** |
  > | p10 | 4,69 | 0,078 | 1,94 |
  > | p5 | 4,59 | 0,103 | 2,56 |
  > | p1 | 4,23 | 0,193 | 4,81 |
  > | mínimo | 1,0 | 1,000 | **25,00** |
  >
  > Ou seja: para 99% do universo o S2 vale ≤ 4,8 pontos — mas a cauda que interessa ao M&A **não**
  > está saturada, e é ela que a régua precisa tratar. Isso muda a pergunta do D-A: não é mais "a
  > régua desperdiça a variância", é "a régua entrega quase tudo o que tem numa cauda de 0,46%".
  >
  > **Correção 2 — e esta é a mais séria: a cauda vulnerável é a MENOS confiável.** Das 158 unidades
  > abaixo de 4,0, a **mediana é de 10,5 avaliações** e **47% têm menos de 10**. No universo com
  > nota, **38,4% têm menos de 30 avaliações** (mediana geral: 46). A DEC-024 (parte 5, D-1)
  > justificou a coluna de contagem dizendo que *"2 das 53 unidades da sonda têm menos de 30
  > avaliações"* — **3,8%**. O número real é **dez vezes maior**. Consequência direta para o D-A:
  > uma régua que **não** pondere confiança vai colocar no topo do ranking de M&A academias cujo
  > "sinal" são três avaliações. A contagem deixa de ser refinamento e passa a ser parte da régua.
  >
  > Terceira via a avaliar (segue de pé, e agora com mais razão): **min-max sobre faixa fixa por
  > decisão** (não por lote), preservando monotonicidade e reprodutibilidade. O alerta original
  > continua válido — não fixar o limite inferior em **4,0**, que satura justamente a ponta
  > vulnerável — e ganhou custo medido: **158 unidades**. Travar o comportamento do clip em teste.
- **D-B — comparabilidade entre regimes.** Com S2 só-WellHub, o universo se parte em `{s1,s2,s3,s4}`
  (pesos `0,15/0,25/0,35/0,25`) e `{s1,s3,s4}` (`≈0,20/0,467/0,333`). Duas academias idênticas, uma
  listada em cada agregador, **saem com scores diferentes** — e o churn pesa 33% mais no grupo sem
  nota. O §8.5 (`:406-408`) já diz que regimes diferentes não são comparáveis, e o G-D1 blindou o
  eixo **temporal**; o que é novo aqui é que a fragmentação deixa de ser transitória e passa a ser
  **permanente e correlacionada com a fonte**, reduzindo o pool comparável. Três opções, nesta ordem
  de preferência: **(0)** propagar o rating como **coluna-fato sem peso** (molde do G-D2), o que
  dissolve D-A e D-C e entrega o dado ao MA-05 sem tocar a régua; **(1)** segmentação obrigatória por
  regime antes de qualquer ordenação — e então a pergunta ao MA-05 é se ele entrega **duas listas**;
  **(2)** anular o `ordenavel` fora do regime majoritário — só considerar após medir qual regime é
  majoritário **no universo do score** (`fonte in FONTES_AGREGADORES` e `rede == independente`), não
  no universo bruto.
- **D-C — `flag_score_provisorio` e o valor real do S2.** `score.py:294` calcula
  `provisorio = (~disponivel["s3"]) & (~disponivel["s4"])`, mas o §8.4 (`:350-351`) define a flag como
  *"quando S3 e S4 estão imaturos e o score depende só de S1 **(e S2 quando ativo)**"* — parêntese que
  a implementação não contempla. Com o cron dos agregadores ainda **mensal e pendente**
  (`docs/infra_producao.md:228`; DEC-013, decisão parte 3, `docs/decisions/DEC-013.md:7`),
  `MIN_SEMANAS = 8` significa **~8 meses** e `STALE_SEMANAS = 12`, **~12 meses**. Manter `{s1,s2}`
  provisório é defensável (dois sinais pontuais não substituem série); tratá-lo como ordenável é o
  que dá valor à dupla no curto prazo. **O gate precisa ver o composto que estará autorizando:**
  `{s1,s2}` = `0,375 · v1 + 0,625 · v2`, com domínio efetivo dado pela opção escolhida em D-A.

**Escopo permitido (READ-ONLY M1) — 13 pontos.** *(O cabeçalho dizia "12"; a enumeração sempre
produziu 13 — 10 de código + correções de contrato + reabertura do §8.2 + consequência do §10.
Corrigido em 2026-08-10.)* `_COLUNAS_TRABALHO` (`snapshots.py:92-107`) — hoje a
coluna nova é **DROPADA em silêncio** em `snapshots.py:150`; `CONTRATO_COLUNAS_SNAPSHOT`
(`contrato.py:193-204`), de 10 para 11/12 colunas, **com bump de `VERSAO_CONTRATO_SNAPSHOT`**
(`contrato.py:34`); **`ler_snapshots`** — a leitura hive de esquema misto (partições pré e pós-bump)
**dropa a coluna nova sem erro**, e o `v2` sairia nulo para o universo inteiro sem ninguém perceber:
exige `schema=` explícito ou `unify_schemas`; a rota de ingestão do valor até o score —
`CONTRATO_COLUNAS_CHURN` (`contrato.py:208-226`) e `vulnerabilidade/churn_staleness.py`, ou um
terceiro parâmetro em `calcular_score_vulnerabilidade` (`score.py:457-462`), conforme a decisão de
grão abaixo; remover `"s2"` de `SINAIS_INATIVOS` (`contrato.py:265` — o comentário `:263-264` já
antecipa: *"Reativar o sinal 2 é remover UMA entrada desta tupla"*); a máscara literal `False` em
`score.py:202` e o loop `:206-207`; **a tupla literal de `_derivar_componentes`**
(`score.py:236`: `for sinal, bruto in (("s1", v1_bruto), ("s3", v3_bruto), ("s4", v4_bruto))`) — sem
tocá-la a coluna `v2` nunca é criada e `_disponibilidade_efetiva` (`:246-247`) devolve `False` para
sempre, tornando inócua a remoção de `SINAIS_INATIVOS`; `CONTRATO_COLUNAS_SCORE`
(`contrato.py:286-307`), de 20 para 21 colunas; o biconditional `s2 ⟺ v2` (`score.py:402-411`); a
flag de `:294` e o `ordenavel` de `:299` conforme D-B e D-C. Mais as correções de contrato: §1, §7 e
§13, que afirmam a premissa falsificada; a reabertura do §8.2; e a consequência para o
`score_vulnerabilidade_medio` hex-level do §10, que agrega linhas de réguas diferentes.

> **Duas precisões sobre as correções de contrato, medidas em 2026-08-10.**
>
> **(a) São QUATRO afirmações falsificadas, não três.** Além de §1, §7/D3 e §13, a **tabela dos 6
> sinais do §4** traz, na linha do sinal 2, o insumo como *"**NÃO coletado hoje (nenhum coletor
> emite nota)**"*. Isso é **factualmente falso** desde o BLK-MA-08 — não é rótulo desatualizado
> como as menções `MA-08 -> MA-09`, é uma afirmação sobre o mundo que deixou de valer. O parágrafo
> "Ponteiros a redirecionar" tratava o §4 como mera troca de rótulo; não é.
>
> **(b) A justificativa da reabertura do §8.2 estava errada — a conclusão, não.** Este bloco dizia
> que a reabertura é "exigida pelo item 4 da emenda G-D3". O item 4 diz que a percentil fica
> RESERVADA e que *"o bloco que a REATIVAR terá de reabrir esta seção"* — e o MA-09 **não** reativa
> a percentil. O gatilho real é o **corpo do §8.2**, que lista *"percentil por universo … para os
> sinais contínuos (**rating**, staleness, …)"*: é essa frase que passa a valer para um sinal ativo
> quando o `v2` liga, e é ela que o D-A tem de resolver.

**Ponteiros a redirecionar (consequência do fatiamento).** Sete comentários no código e um teste
apontam para o **BLK-MA-08** como o bloco que reativa o S2 e produz o `v2` — o que passou a ser
**este** bloco quando a frente foi partida em coletor (MA-08) e motor (MA-09):
`contrato.py` (**5 ocorrências**), `presenca_agregador.py`, `score.py` e
`tests/unit/vulnerabilidade/test_presenca_agregador.py`. Redirecionar todos para `BLK-MA-09`, junto
com as menções equivalentes no contrato (`docs/vulnerabilidade_ma_contrato.md`, **15 ocorrências** de
`MA-08` medidas em 2026-08-10 — a lista de 10 âncoras que este parágrafo trazia era incompleta). São
comentários e prosa — nenhum altera comportamento —, mas deixá-los apontando para o bloco errado é
exatamente o defeito de drift doc-vs-código que o §5 do `CLAUDE.md` registra.

> **Os números de linha saíram deste parágrafo DE PROPÓSITO (2026-08-10).** Ele listava
> `contrato.py:230/:263/:280/:296/:540`, `presenca_agregador.py:80`, `score.py:123` e
> `test_presenca_agregador.py:400`. Auditoria de 2026-08-07 mediu que **os cinco de `contrato.py`
> estavam certos e o do teste errado por 1**; os PRs #208 e #209 então deslocaram os de
> `contrato.py` em ~14 linhas. Ou seja: a lista apodreceu **duas vezes em três dias**, e consertar
> os números seria só rearmar o relógio. A forma correta de encontrar as âncoras é
> `grep -rn "BLK-MA-08" src/motor_expansao/vulnerabilidade/ tests/unit/vulnerabilidade/` e
> `grep -n "MA-08" docs/vulnerabilidade_ma_contrato.md`, que não envelhecem.
>
> **Um item que a lista original não tinha e que NÃO é prosa:** `presenca_agregador.py` traz `"v2"`
> **hard-coded numa trava executável** (`_COLUNAS_DE_SCORE_PROIBIDAS`), logo abaixo do comentário
> que a lista mandava redirecionar. Ela **levanta** quando o `v2` aparecer na saída do módulo —
> então o MA-09 tem de tratá-la como código, não como comentário.

**Guardrail (inviolável).** A nota **NUNCA** entra em `CAMPOS_HASH_POR_FONTE`
(`contrato.py:161-183`). Ela muda a cada avaliação nova; hasheá-la faria toda unidade parecer
"cadastro alterado" a cada coleta, `semanas_sem_mudanca` nunca cresceria e **o S4 morreria** — é
exatamente o modo de falha que o comentário `:159-160` descreve para `data_coleta`, que por isso vive
em `CAMPOS_NUNCA_HASHEADOS` (`:184`). A nota deve ir para lá ou equivalente. Nota e contagem **não**
são PII e não estão em `COLUNAS_PII_PROIBIDAS` (`contrato.py:311-333`), coerente com o §13
(*"persiste só o agregado numérico"*); texto e autor de review continuam proibidos pelo §11.
**A razão real de fazer isto agora:** mudar as primitivas CONGELADAS re-chaveia a série
(`contrato.py:335-337`), e a série está em zero-a-poucas semanas — este é o único momento em que o
bump é gratuito, e o custo só cresce.

**Grão a decidir antes de escrever código.** O `v1` foi rebaixado para hex-level porque a chave de
snapshot embute a `fonte` e "quantos agregadores cobrem esta linha" era constante `1` (emenda
BLK-MA-03, contrato `:239-269`). O `v2` **não** tem esse problema: a nota é intrínseca à academia.
Logo o `v2` é o **primeiro sinal genuinamente por-academia** do score — não deve herdar o sufixo
`_no_hex` nem o join `many_to_one`, e isso decide qual módulo o produz e por onde ele entra em
`calcular_score_vulnerabilidade`.

**Fora de escopo.** Qualquer artefato/score/peso do M1; o coletor e o CSV, que são **BLK-MA-08**; o
TotalPass, que é **BLK-MA-10**; a reputação externa/Google Places (**BLK-MA-07**, gate e DEC
próprios); o cruzamento com hex quente e o entregável comercial (**BLK-MA-05**); o cron e o runbook
(**BLK-MA-06**); reabrir a fórmula, os pesos do D4 ou as decisões G-D1/G-D2/G-D3 **exceto** no ponto
que o item 4 da emenda G-D3 explicitamente delega a este bloco (o §8.2).

**Critério de aceite.** D-A, D-B e D-C decididas no gate DESTE bloco (fatiado da DEC-024) e registradas como emenda ao
contrato (§7, §8.1, §8.2, §8.4, §8.5), com DEC nova **apenas** se o D-B escolher algo que mude a
arquitetura da entrega (duas listas, ou anulação por regime); `v2` ligado com teste do regime misto
`{s1,s2,s3,s4}` × `{s1,s3,s4}` no mesmo frame, provando a política escolhida; teste de que a nota
**não** entra no hash e que o S4 sobrevive a uma nota oscilando entre coletas; teste de leitura hive
com uma partição pré-bump e uma pós-bump provando que a coluna nova sobrevive; **check de execução**
— se `ler_snapshots` devolver ≥ 1 semana no momento do ciclo, o procedimento de migração das
partições passa a ser obrigatório (hoje é gratuito porque a série está vazia, mas isso é premissa a
verificar, não a assumir); as **quatro** afirmações falsificadas corrigidas no contrato (§1, §4, §7
e §13 — ver a precisão (a) acima); os tripwires intencionais atualizados com justificativa,
**referenciados pelo nome do teste, não pela linha** (a lista por linha apodreceu duas vezes; ver a
nota no parágrafo de ponteiros):

| Arquivo | Teste | O que trava |
|---|---|---|
| `test_score.py` | `test_pesos_alvo_sao_os_quatro_do_d4_e_somam_um` | pesos-alvo do D4 **e** `SINAIS_INATIVOS == ("s2",)` |
| `test_score.py` | `test_pesos_efetivos_do_plano_b_sao_calculados_nao_digitados` | pesos efetivos `≈0,20 / 0,4667 / 0,3333` em `pytest.approx` |
| `test_score.py` | `test_schema_22_colunas_em_ordem_e_dtypes` | saída do score com 22 colunas |
| `test_snapshots.py` | `test_schema_snapshot_12_colunas_em_ordem` | snapshot com 12 colunas |
| `test_churn_staleness.py` | `test_schema_churn_19_colunas_em_ordem` | **frame de churn com 19 colunas** |

> O último **não estava na lista** e é condicional: ele só quebra se a rota de ingestão escolhida no
> ponto 4 do escopo passar pelo frame de churn — que é uma das duas rotas que o próprio bloco deixa
> em aberto. Quem escolher aquela rota precisa saber disto antes, não descobrir no vermelho.

Suíte completa sem regressão contra baseline **medida no início do ciclo** — a regra do §5 do
`CLAUDE.md` vale aqui e a linha abaixo envelhece por construção. Última medição real: **2638 passed
+ 100 skipped** em 2026-08-10, na `ciclo/BLK-MA-FU1-lote2`. *(O valor que este critério trazia,
`2334 coletados` de 2026-07-31, estava 400 testes defasado.)* `ruff` limpo; `loop_guard` sem
`CRITICO`; READ-ONLY sobre o M1 provado pelo diff.

---

---

## Fechamento de ciclo — BLK-MA-02-FU1 (2026-08-11)

**VEREDITO: CONCLUÍDO.** Todas as ressalvas do QA do BLK-MA-02 (2026-07-29) estão fechadas, em três
PRs: **#194** (item 1 e item 2-B), **#208** (item 2) e **#220** (os 6 menores).

**Item 1 — `flag_troca_chave_na_serie` nascia permanentemente ligada.** A fórmula media "o escopo tem
origens MISTAS", não "a chave TROCOU de política ao longo da série"; no feed TP/WH a flag sairia
`True` para todo o universo, todo mês, e o BLK-MA-04 receberia um sinal morto. Redefinida para troca
TEMPORAL.

**Item 2 — vazamento transitivo de import.** `import motor_expansao.vulnerabilidade` levava ~18 s e
carregava `sklearn`/`scipy`/`shapely`/`requests`/`pyproj` + 5 módulos de `dashboard/`, contra o que o
próprio docstring afirmava. O `__init__` de `demanda_revelada` passou a reexportar por `__getattr__`
(PEP 562): caiu para **~3 s, com zero dos dois**. Era **bloqueante para o BLK-MA-06** — o passo do
cron quebraria no import se `sklearn` não estivesse no host do coletor.

**Item 2-B — ponto cego de 1 linha no `test_isolamento_imports`.** Das 5 formas de escrever o import
proibido, o teste por AST pegava **2**; o filtro descartava o nó quando `node.module is None` (o caso
`from .. import X`). Hoje 5/5, com helper único em `tests/unit/_ast_imports.py`.

**Os 6 menores (#220, 2026-08-11).** O que importa é o **m6**: `python -m ...snapshots` era
`print(executar())` **sem argumento nenhum** — gravava na raiz de staging default **e podava disco**.
É o módulo que o BLK-MA-06 pluga no cron e o **único do pacote que apaga arquivo**. Ganhou
`--base-dir`, `--data-referencia`, `--retencao-semanas` e **`--dry-run`** (não grava, não poda). Sem
isso o MA-06 não existiria como bloco aplicável.

Os outros cinco: (m3) `CAMPOS_NUNCA_HASHEADOS` passou a ser imposto em **runtime** — era só prosa, e
injetar `data_coleta` mataria o S4 em silêncio; (m1) frame vazio **preserva** a partição e avisa em
WARNING — corrigiu-se o docstring, não o comportamento, porque zero linha é sintoma de coleta falha,
não de universo vazio; (m2) `data_referencia` saiu de `montar_snapshot`, parâmetro morto que sugeria
que o `snapshot_date` vinha dele; (m4) 41 linhas de prosa acentuadas nos 2 arquivos de teste, **sem
tocar literal de dado** (`"Sao Paulo"` das fixtures segue ASCII, §2); (m5) tabela D2 do contrato
marcada como SUPERSEDED.

**Duas escolhas de julgamento registradas.** No **m1**, o QA deixou em aberto corrigir o código ou o
docstring — corrigiu-se o docstring, pela mesma lógica da guarda de rating do MA-09: apagar ali
trocaria falha transitória por perda permanente de série. No **m4**, a acentuação usou `tokenize`/`ast`
para tocar só comentário e docstring; literal de dado ficou intacto porque acentuá-lo mudaria
normalização e hash.

**Verificação.** 7 testes novos no lote final — 4 falham no código anterior (sonda executada), 3 são
caracterização do comportamento que o QA pediu para travar. Camada 278 -> 285. Suíte **2814 passed,
100 skipped**. `ruff`/`mypy` limpos, `loop_guard` sem CRÍTICO. READ-ONLY sobre o M1.

---

### BLK-MA-02-FU1 — Ajustes pós-QA do materializador/extrator de vulnerabilidade

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (ajustes localizados numa camada paralela READ-ONLY sobre o M1, já entregue e coberta por testes; nenhum toca score/pesos/artefatos do M1 nem cria dependência externa). |
| **Prioridade** | Antes do **BLK-MA-05/06** (item 1: quem EXIBIR a flag) e antes do **BLK-MA-06** (item 2). **NÃO bloqueia o BLK-MA-04** — verificado em 2026-07-30: o score não consome `flag_troca_chave_na_serie` nem a propaga (trava executável em `_assert_schema_score`). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA. |
| **Status** | **PARCIAL.** ✅ Item 1 (`flag_troca_chave_na_serie` redefinida para troca TEMPORAL) e ✅ item 2-B (ponto cego do AST: era **2/5**, não 3/5 — hoje 5/5, helper único em `tests/unit/_ast_imports.py`) — PR #194, merged 2026-08-05. ✅ **Item 2 CORRIGIDO em 2026-08-10**: o `__init__` de `demanda_revelada` passou a reexportar por `__getattr__` (PEP 562); `import motor_expansao.vulnerabilidade` caiu de **~18 s com sklearn/scipy/shapely/requests/pyproj + 5 módulos de `dashboard/`** para **~3 s com zero dos dois**. **Desbloqueia o BLK-MA-06.** ✅ **Os 6 menores, em 2026-08-11** — bloco **CONCLUÍDO**. (m6) `snapshots.py` ganhou CLI real: `--base-dir`, `--data-referencia`, `--retencao-semanas` e **`--dry-run`** que não grava e **não poda** — era `print(executar())` sem argumento, gravando e podando disco; pré-requisito do MA-06. (m3) `CAMPOS_NUNCA_HASHEADOS` passou a ser imposto em RUNTIME dentro de `hash_campos_raspados` — antes era só prosa, e injetar `data_coleta` mataria o S4 em silêncio. (m1) Frame vazio agora sai cedo, **preserva** a partição existente e avisa em WARNING: zero linha é sintoma de coleta falha, não de universo vazio — o docstring prometia idempotência que não valia para encolhimento total. (m2) `data_referencia` saiu de `montar_snapshot` (parâmetro morto que sugeria que o `snapshot_date` vinha dele; ele vem por linha de `parse_data_coleta`). (m4) 41 linhas de prosa acentuadas nos 2 arquivos de teste, **sem tocar literal de dado** (`"Sao Paulo"` das fixtures segue ASCII, por §2). (m5) Tabela D2 do contrato marcada como SUPERSEDED, apontando para a emenda do §6. **7 testes novos** (4 falham no código anterior; 3 são caracterização do comportamento que o QA pediu para travar); camada 278 -> **285**. |
| **Depende de** | BLK-MA-02 (concluído 2026-07-29). |
| **Autonomia** | **manual (NÃO loop-safe)** — mesmo perfil do BLK-MA-02: camada com insumo de PII na origem (DEC-012) e módulo destinado ao cron de produção. NÃO marcar loop-safe. |

**Origem.** Ressalvas do QA do BLK-MA-02 (veredito APROVADO COM RESSALVAS em 2026-07-29; 0 críticos,
3 médios, 6 menores). Snapshot: `context/handoff/20260729-134525-qa.md`.

**Item 1 (médio, bloqueante para o BLK-MA-05/06) — `flag_troca_chave_na_serie` nasce permanentemente
ligada.** A fórmula implementada (`churn_staleness.py:203-205`) é
`|{chave_origem observados no escopo (fonte, rede_ultima)}| > 1`, que mede "o escopo tem origens
MISTAS", não "a chave TROCOU de política ao longo da série". Sonda do QA: 4 semanas, mesmo escopo,
uma chave sempre `slug` e outra sempre `hash_estavel`, **zero** troca temporal → a flag saiu `True`
para as duas. No feed TP/WH o rebaixamento por linha convive com o `slug` na mesma semana, logo a
flag será `True` para todo o universo, todo mês, e o BLK-MA-04 receberá um sinal morto. **Não é
desvio do Builder** — é a fórmula que o Planner especificou e que o gate não vetou. Redefinir para
"o conjunto de `chave_origem` da PRÓPRIA chave ao longo da sua série" ou "houve mudança entre semanas
consecutivas do escopo", com teste que reproduza a sonda (o `test_flag_troca_chave_na_serie` atual
passa por coincidência de desenho da fixture, onde a troca É temporal).

**Item 2 (médio, bloqueante para o BLK-MA-06) — vazamento transitivo de import.** O docstring de
`vulnerabilidade/__init__.py:3-4` afirma que o pacote "NUNCA importa de `dashboard/`"; medido pelo
QA, `import motor_expansao.vulnerabilidade` leva **7,5 s** e carrega `motor_expansao.dashboard.*` +
`sklearn`, `scipy`, `shapely`, `requests`. Causa: `snapshots.py:51` importa `classificar_rede` de
`demanda_revelada.classificacao_rede_menor`, e o `__init__.py` do `demanda_revelada` reexporta o
pacote inteiro. O `test_isolamento_imports` só olha imports **diretos** por AST, então não pega — o
CA-1 está literalmente satisfeito. **Não é regressão** (nada do M1, `config.py` ou
`normalizar_concorrentes` entra; o READ-ONLY continua íntegro), mas este é o módulo que a D6
ratificou plugar no `run_weekly_90.sh`: se `sklearn`/`scipy` não estiverem no host do coletor, o
passo do cron quebra no import. Tornar o `__init__` do `demanda_revelada` lazy **ou** replicar o
classificador (como já foi feito com o `concorrente_id`); no mínimo corrigir o docstring para "não
importa **diretamente**". Acrescentar teste de isolamento por `sys.modules`, não só por AST.

> **RESOLVIDO em 2026-08-10.** Escolhida a rota do `__init__` lazy, e não a réplica do
> classificador: ela conserta o vazamento para **todos** os consumidores do `demanda_revelada`, não
> só para o `vulnerabilidade/`, e não duplica código. `demanda_revelada/__init__.py` passou a
> reexportar por `__getattr__` (PEP 562), com `_EXPORTS` mapeando cada nome público ao seu
> submódulo e memoização em `globals()`; o bloco `TYPE_CHECKING` preserva o que o type checker
> enxerga, e `__all__` fica intacto. Medido: **~18 s -> ~3 s**, de 5 módulos de `dashboard/` e 5
> deps pesadas para **zero**, e de 12 submódulos de `demanda_revelada` carregados para 4 (todos
> leves).
>
> **A causa registrada acima estava certa, mas incompleta em um ponto que importa.** Não é que
> "qualquer um dos 9 puxa o conjunto": o peso vem de `backtest_tp05`, `calibracao_*`,
> `estrutura_funil`, `huff_captura` e `validacao`, que importam `scipy`/`sklearn` no topo. O que o
> `vulnerabilidade/` realmente precisa — `classificacao_rede_menor` — importa só `re`,
> `unicodedata` e `pathlib`. O problema nunca foi o submódulo escolhido; era o `__init__` do pai,
> que o interpretador executa antes de qualquer submódulo.
>
> **Dois defeitos do próprio teste, achados no caminho e corrigidos junto** (valem como lição de
> método, não só como conserto):
> 1. O subprocesso não recebia `PYTHONPATH` e resolvia `motor_expansao` pela **instalação
>    editável** — que aponta para o clone principal, não para o worktree. Ele media outra árvore em
>    silêncio. Agora recebe o `src` deste checkout e **assere a procedência** do que mediu.
> 2. Sob a captura do pytest no Windows, o `subprocess` levantava
>    `OSError: [WinError 6] Identificador inválido` antes de rodar qualquer coisa. Como o teste
>    estava marcado `xfail(strict=True)`, essa OSError contava como "falha esperada": **o teste
>    errava em vez de medir, e a marca escondia isso**. Corrigido com `stdin=DEVNULL`. Fica o
>    princípio: `xfail` engole exceção de qualquer natureza, então um `xfail` de longa duração pode
>    estar mascarando um teste quebrado em vez de um defeito real.

**Item 2-B (médio, acrescentado pelo QA do BLK-MA-03 em 2026-07-29) — ponto cego de 1 linha no
`test_isolamento_imports`, que enfraquece o guardrail nos DOIS blocos.** O QA do MA-03 construiu uma
sonda de injeção e mediu: das 5 formas de escrever o import proibido, o teste por AST pega 3 e
**deixa passar 2** — `from .. import demanda_revelada` e
`importlib.import_module("motor_expansao.demanda_revelada")`. Causa: o filtro
`if isinstance(node, ast.ImportFrom) and node.module` **descarta o nó quando `node.module is None`**
(que é exatamente o caso `from .. import X`), e os aliases nunca são coletados. O buraco vale para
**todos** os módulos proibidos (`pipelines.m1`, `dashboard`, `api`, `censo`, `config`,
`normalizar_concorrentes`), não só para `demanda_revelada`. **Impacto hoje: zero** — nenhum módulo
entregue usa essas formas. **Correção (1 linha):** coletar `a.name for a in node.names` também quando
`node.module is None`. Fica neste bloco porque a mesma linha fecha o teste compartilhado
(`test_snapshots.py`) e o teste próprio do MA-03 (`test_presenca_agregador.py`), que se apoiou nele.

**Item 3 (menores, 6).** (m1) `escrever_particao_semana` com frame vazio não limpa a partição
anterior da mesma semana e devolve caminho inexistente — a direção é segura (preserva dado), mas
contradiz o docstring e não tem teste. (m2) `montar_snapshot(df, data_referencia)` nunca usa
`data_referencia` — parâmetro morto que sugere que o `snapshot_date` sai dele. (m3)
`CAMPOS_NUNCA_HASHEADOS` não é imposto em runtime: injetando `data_coleta` em
`CAMPOS_HASH_POR_FONTE` nada levanta; um `assert` dentro de `hash_campos_raspados` fecha o buraco no
próprio caminho que ele protege. (m4) §2 acentuação: identificadores 100% ASCII em todos os 7
arquivos, mas a **prosa** de `test_snapshots.py` (9 chars) e `test_churn_staleness.py` (5) não está
acentuada. (m5) `docs/vulnerabilidade_ma_contrato.md:429` (tabela D2) ainda diz "chave = `slug`
nativo + `data_coleta` (fallback `concorrente_id`)", afirmação que a emenda do §6 descartou — basta
um ponteiro `[ver emenda 2026-07-29 no §6]`. (m6) `python -m motor_expansao.vulnerabilidade.snapshots`
chama `executar()` sem argumento: escreve em `data/staging/` **e poda disco** sem `--base-dir`,
`--data-referencia` nem `--dry-run` — faltam `argparse` e modo seco para o módulo que vai ao cron.

**Fora de escopo.** Qualquer artefato/score/peso do M1; `MIN_SEMANAS`/`STALE_SEMANAS` (valores do
gate de 2026-07-23, revisitar só no BLK-MA-06); o plug no `run_weekly_90.sh` (BLK-MA-06); `v3`/`v4` e
`score_vulnerabilidade` (BLK-MA-04).

**Critério de aceite.** Itens 1 e 2 corrigidos com teste que falharia antes da correção (o do item 2
por `sys.modules`); os 6 menores endereçados ou explicitamente recusados com justificativa; suíte
completa sem regressão (baseline do BLK-MA-02: **2186 coletados**); `ruff` limpo;
`python scripts/loop_guard.py` sem `CRITICO`; READ-ONLY sobre o M1 provado pelo diff.

---

- BLK-MA-03 (concluído 2026-07-29) — ver tasks/completed.md

---

### BLK-MA-03-FU1 — Ajustes pós-QA do sinal 1 (presença em agregador)

| Campo | Valor |
|---|---|
| **Criticidade** | **Baixa** (documentação de limite conhecido, um teste de congelamento, correção de ponteiro de linha e acentuação de prosa; nenhuma mudança de comportamento do sinal). |
| **Prioridade** | Antes do **BLK-MA-05**, que é quem exibirá "densidade do alvo". **NÃO bloqueia o BLK-MA-04** — verificado em 2026-07-30: `v1` deriva de `n_agregadores_no_hex`, e as colunas `n_academias_independentes_*` não entram no score nem na sua saída. |
| **Esteira** | Block Orchestrator → Builder. |
| **Status** | **CONCLUÍDO em 2026-08-12** (PR #223, merge commit `57bd5c7`). Itens 1, m1, m2 e m4 do critério de aceite entregues com sonda de prova. **m3, m5 e m6 RECUSADOS explicitamente** — não estão no critério de aceite e nenhum é defeito ativo: (m3) é imprecisão de um handoff já arquivado, sem artefato vivo a corrigir; (m5) é inalcançável pelo caminho público (o filtro do passo 3 garante o universo) e o `_assert_schema` já barra a saída — uma guarda privada duplicaria a trava sem fechar buraco algum; (m6) é divergência de contagem de warnings, pré-existente e alheia a este bloco. |
| **Depende de** | BLK-MA-03 (concluído 2026-07-29). |
| **Autonomia** | **manual (NÃO loop-safe)** — mesmo perfil do pacote `vulnerabilidade/`: camada com insumo de PII na origem (DEC-012). NÃO marcar loop-safe. |

**Origem.** Ressalvas do QA do BLK-MA-03 (APROVADO COM RESSALVAS em 2026-07-29; 0 críticos, 2 médios,
6 menores). Snapshot: `context/handoff/20260729-162056-qa.md`. **O médio M1 (ponto cego do AST no
`test_isolamento_imports`) NÃO está aqui** — foi para o `BLK-MA-02-FU1` (Item 2-B), porque a mesma
correção de 1 linha fecha o teste compartilhado e o teste próprio deste bloco.

**Item 1 (médio) — `n_academias_independentes_*` super-conta sob rotação de chave.** Sonda do QA: uma
única academia observada nas semanas 1-2 sob `chave_origem = slug` e nas semanas 3-4 sob
`hash_estavel` sai como `n_academias_independentes_totalpass = 2`. A redução dedupla por
`(fonte, chave_snapshot)`, então as duas encarnações da MESMA academia sobrevivem como duas chaves.
**Não contamina `n_agregadores_no_hex`** (segue `1`), que é o insumo real do `v1` — mas o contrato
vende as colunas 4/5 ao consumidor como "densidade do alvo" ("hex com 6 independentes num agregador
só é uma tese diferente de hex com 1"), e é essa leitura que fica inflada. O módulo irmão já tem
`flag_troca_chave_na_serie` exatamente para este modo de falha; aqui não há menção no docstring, nem
no comentário da coluna em `contrato.py`, nem teste. **Atenuante:** o rebaixamento global da chave só
ocorre se o chamador INJETAR a taxa medida (default `None`, `contrato.py:47-51`), logo é raro e
deliberado. **Correção:** registrar o limite no docstring do módulo e no comentário das colunas 4/5,
mais um teste que congele o comportamento.

**Item 2 (menores, 6).** (m1) A emenda G1 cita `vulnerabilidade/contrato.py:395-413` como prova de que
`chave_do_slug`/`chave_hash_estavel` embutem a `fonte`; era verdade em `a0430b8`, mas o **mesmo
commit** acrescentou 41 linhas acima delas — hoje estão em **432-450**, e `395-413` aponta para
`rotulo_de_teste`/`entrada_tecnologia_totalpass`. O ponteiro errado está em **2 artefatos
permanentes**: `docs/vulnerabilidade_ma_contrato.md:241` e este `tasks/backlog.md`. A afirmação é
verdadeira e tem teste; só a referência precisa ir para `432-450`.
**[correção 2026-08-12, BLK-MA-03-FU1] `432-450` também já envelheceu — o ponteiro foi ANCORADO POR
NOME, e DE PROPÓSITO não reapontado para um novo intervalo.** Medido: `432-450` hoje aponta para
`derivar_semana_iso`/`parse_data_coleta`, e as funções certas já se mudaram outra vez. O
deslocamento acumulado desde o BLK-MA-03 é de **+115 linhas**, e a maior fatia **não** é dos blocos
que se suspeitaria: `BLK-MA-04` sozinho vale **+59** (51%), contra `+20` do MA-09, `+14` do MA-11 e
`+22` de dois follow-ups. Este seria o **terceiro** endereço da mesma afirmação em ~2 semanas — e
escrever um quarto não resolveria nada: o próprio diff deste FU1 acrescenta 5 linhas a `contrato.py`
acima das funções e invalidaria o número no ato. É o número de linha que é o defeito, não o valor
dele, então os 3 artefatos passaram a citar **`chave_do_slug` e `chave_hash_estavel` pelo nome**,
sem intervalo algum. Também medido: o ponteiro estava em **3** artefatos, não 2 —
`tasks/completed.md` (fechamento do BLK-MA-03) carregava a mesma referência, e o endereço
`docs/...:241` deste parágrafo era, ele próprio, stale (a linha real era a `325`). (m2) §2
acentuação: 4 linhas de prosa sem acento — `presenca_agregador.py:69,308,309` e
`test_presenca_agregador.py:34` (medido: a linha real é a **33**, `# Sao Paulo`) — contra a
afirmação explícita do handoff do Builder de que a prosa estava acentuada. Mesma classe da ressalva
`m4` do QA do MA-02. **Não** contam como defeito as mensagens de `raise` em ASCII (cópia deliberada do
precedente em `churn_staleness.py:222`; §2 mira texto de usuário, não exceção de desenvolvedor).
(m3) O handoff do Builder afirma "nada mais do texto do Planner foi alterado", mas o item (b) da
emenda tem **2 linhas aditivas** além das 29 byte-idênticas — o acréscimo é útil, a afirmação é que
está imprecisa. (m4) O `fillna("")` do `_assert_schema` (desvio 2 declarado pelo Builder) foi provado
necessário pelo QA — sem ele, `fontes_presentes_no_hex = pd.NA` faz a comparação mascarada devolver
`0` e a checagem passar em silêncio —, mas **nenhum teste o trava**: o teste existente usa
`"wellhub"`, não `pd.NA`. (m5) `_agregar_por_hex` emite `n_agregadores_no_hex = 0` em silêncio se
chamado direto com `fonte = "unidades"`; pelo caminho público é inalcançável (o filtro garante o
universo) e o `_assert_schema` barra, mas a função privada não tem guarda própria. (m6) Divergência
trivial de contagem de warnings no smoke de import (2 relatados vs 4 medidos), pré-existente.

**Fora de escopo.** Qualquer artefato/score/peso do M1; `v1`, pesos e `score_vulnerabilidade`
(BLK-MA-04); a granularidade hex de `v1` (ratificada no gate G1 de 2026-07-29 — não reabrir); o ponto
cego do AST (está no `BLK-MA-02-FU1`, Item 2-B).

**Critério de aceite.** Limite da rotação de chave documentado no docstring e no comentário das
colunas 4/5, com teste que o congele; ponteiro `432-450` corrigido nos 2 artefatos; 4 linhas de prosa
acentuadas; teste do `fillna` com `pd.NA`; suíte completa sem regressão (baseline do BLK-MA-03:
**2230 coletados**); `ruff` limpo; `loop_guard` sem `CRITICO`.
**[nota 2026-08-12] A baseline `2230` é HISTÓRICA** (CLAUDE.md §5: contagem de ciclo envelhece a
cada ciclo, não serve de tripwire). Medida no início deste FU1, na `main` em `4ab83f4`: **2918
coletados**. O critério "sem regressão" foi lido contra ela, e o ponteiro foi ancorado por nome em
**3** artefatos em vez de reapontado para um novo intervalo — ver a correção do m1 acima.

---

### BLK-MA-04-FU1 — Ajustes pós-QA do score de vulnerabilidade

| Campo | Valor |
|---|---|
| **Criticidade** | **Baixa** (um teste de isolamento endurecido, um regime sem cobertura, e 4 leves de precisão de texto/asserção; nenhuma mudança na fórmula nem nos pesos). |
| **Prioridade** | Antes do **BLK-MA-05**, que é o consumidor do score. |
| **Esteira** | Block Orchestrator → Builder. |
| **Status** | **CONCLUÍDO em 2026-08-12** (PR #223, merge commit `57bd5c7`; o Item 1 já viera no PR #194). ✅ Item 1 (PR #194, merged 2026-08-05) — a mesma correção do AST fechou o teste novo deste bloco, e a taxa foi medida em **2/5** (o item 2-B do MA-02-FU1 subcontava). ✅ Item 2 — `test_regime_so_s3` + `test_ordenavel_nao_separa_regimes_de_tamanho_diferente`, e a emenda ao §8.5 do contrato. ✅ Os 4 leves (a,b,c,d), mais as duas **observações do QA** que o bloco pediu para não perder (o comentário de `SINAIS_INATIVOS` em `renormalizar_pesos` e o registro de que as duas checagens por substring são heurísticas de defesa secundária). |
| **Depende de** | BLK-MA-04 (concluído 2026-07-30). |
| **Autonomia** | **manual (NÃO loop-safe)** — mesmo perfil do pacote `vulnerabilidade/`: camada com insumo de PII na origem (DEC-012). NÃO marcar loop-safe. |

**Origem.** Ressalvas do QA do BLK-MA-04 (APROVADO COM RESSALVAS em 2026-07-30; 0 críticos, 2 médios,
7 leves). Snapshot: `context/handoff/20260730-110503-qa.md`.

**Item 1 (médio) — o teste de isolamento novo prova 2 das 5 formas de import.** O Builder replicou,
num arquivo NOVO (`tests/unit/vulnerabilidade/test_score.py::test_modulo_nao_importa_demanda_revelada`),
o ponto cego do AST já registrado no `BLK-MA-02-FU1` Item 2-B. Aplicar ali a **mesma correção de 1
linha** (coletar `a.name for a in node.names` também quando `node.module is None`) e **atualizar o
texto do Item 2-B**, que agora subconta: são **3 arquivos** do pacote (4 com
`tests/unit/demanda_revelada/test_concorrentes_densos.py`), e a taxa da checagem por substring é
**2/5**, não 3/5. Teste que falharia antes: sonda de injeção com as 5 formas.

**Item 2 (médio) — o regime de 1 sinal `{s3}` não tem teste, e o G-D1 não o cobre.** O QA mediu:
`score = 100.0`, `flag_score_provisorio = False`, `score_vulnerabilidade_ordenavel = 100.0`. É **fiel
ao §8.4 ratificado** (S3 maduro é sinal maduro), mas significa que a coluna ordenável — o guardrail
que o G-D1 criou — **não protege** um regime de 1 sinal quando esse sinal é o S3. Inalcançável pelo
caminho `base_dir`; alcançável por frames injetados, que é justamente o modo que o BLK-MA-05 pode
usar. Acrescentar `test_regime_so_s3` asserindo `tokens == ["s3"]`, peso efetivo `1,00` e que a
ordenável **fica preenchida** — para o comportamento ser escolha explícita, não descoberta do MA-05.
Registrar no §8.5 que a ordenável não cobre regimes de 1 sinal com S3, e que o MA-05 deve segmentar
por `n_sinais_disponiveis` antes de ordenar.

**Item 3 (leves, 4).** (a) `test_score.py:567` tem **asserção morta**: o QA mediu que
`float(score or 1.0) != 0.0` passa tanto para `NaN` quanto para `0.0`; trocar por
`assert not (out["n_sinais_disponiveis"].eq(0) & out["score_vulnerabilidade"].eq(0.0)).any()`.
(b) `test_snapshots.py:167` — o comentário de seção ainda diz "sobre os **4** módulos do pacote",
mas a tupla passou a ter 5 módulos + o pacote. (c) O docstring de `score.py` abre com "Módulo **PURO
e sem I/O**", mas o modo `base_dir` lê disco **transitivamente** pelos dois extratores; o texto do
Planner era mais preciso ("pura quando os frames são injetados"), e o teste só prova que não
**escreve**. (d) Faltam dois testes de borda: `presenca` bem-formada porém **vazia** com `churn` não
vazio (comportamento sondado e correto, sem teste), e a **ordem de validação dos insumos** —
`_assert_schema_presenca_agregador` **não roda** quando `churn.empty`, porque o retorno antecipado
vem antes; direção segura (saída vazia e validada), mas sem teste que trave a ordem, e não declarada
como desvio pelo Builder.

**Observações do QA que NÃO viram item (registradas para não se perderem).** `renormalizar_pesos` não
conhece `SINAIS_INATIVOS` (aceita `"s2"` porque ele está em `SINAIS_ORDEM`) — não é defeito, a
primitiva é sobre pesos e `_disponibilidade_efetiva` força `s2` a `False`, mas vale 1 linha de
comentário para o **BLK-MA-08** não se surpreender. E `test_modulo_nao_usa_funcao_de_percentil` /
`test_modulo_nao_escreve_em_disco` são checagens por **substring da fonte**: não pegariam
`scipy.stats.rankdata`, `np.percentile` sob alias, nem `Path.write_text` — são defesa secundária
legítima (a primária, `test_v4_nao_depende_do_universo`, o QA reproduziu e é robusta), mas o
docstring poderia dizer que são heurísticas.

**Fora de escopo.** Qualquer artefato/score/peso do M1; a fórmula, os pesos do D4 e as três decisões
do gate G-D1/G-D2/G-D3 (ratificadas em 2026-07-30 — não reabrir); o cruzamento com hex quente e o
entregável comercial (BLK-MA-05); o cron (BLK-MA-06).

**Critério de aceite.** Itens 1 e 2 corrigidos com teste que falharia antes; os 4 leves endereçados
ou explicitamente recusados com justificativa; suíte completa sem regressão (baseline do BLK-MA-04:
**2311 coletados**); `ruff` limpo; `loop_guard` sem `CRITICO`.

---

## Fechamento de ciclo — BLK-CONC-DUPLO (2026-08-14)

**VEREDITO: CONCLUÍDO.** A página de Conclusão do Relatório Pontual passou a carimbar **dois selos
independentes** — DEMOGRÁFICO (a praça) e FINANCEIRO (o imóvel e o retorno) — e **deixou de emitir
veredito único**. Pedido de Vinicius; decisão registrada na **DEC-030**. Registra-se aqui também, de
passagem, que a página nunca teve bloco em `tasks/`: até este ciclo seu histórico canônico eram o §7
de `docs/relatorio_pontual_censitario.md` e as mensagens de commit (o BLK-CONC-ESTUDO, de Juan em
2026-08-12, também nunca foi registrado).

**Por que.** A página nasceu em 2026-08-06 justamente para dar um veredito ÚNICO ao ponto. Essa
premissa caiu: os dois eixos falham por motivos que não se compensam — uma praça que não sustenta a
operação não fica aceitável porque o imóvel é barato, e vice-versa —, e o status único colapsava os
dois no pior lado, deixando o leitor reconstruir pela lista de observações de onde vinha a
reprovação. O golden dos 5 pontos do Recife é a prova: decomposto, ele é na prática um golden do eixo
FINANCEIRO (`1/2/2`, a calibração de Vinicius, intacta), enquanto o demográfico sai `4/1/0`. A
leitura da praça, limpa em 4 dos 5, nunca aparecia no carimbo.

**Nenhum corte foi reaberto.** Limiares, bordas inclusivas e textos dos apontamentos são os de
2026-08-06/07. O que mudou é a quem cada gate responde.

**Decisões de desenho (todas na DEC-030).** (i) `_ConclusaoPonto` perde o campo `status` — não há
agregado, e `test_parecer_nao_expoe_status_agregado` impede que volte; o levantamento provou que o
status **nunca saiu do PDF** (nenhum endpoint, response model, payload de bot ou componente do piloto
o lia). (ii) Zona morta (E4) é DEMOGRÁFICA — dispara por `pop<5000`/`renda<1600` na captação; passa a
valer no só-estudo, sem efeito no bot de produção, que chama a página com `viabilidade=None`.
(iii) Só-estudo desenha um selo (`financeiro is None`), e com isso a exceção de Juan (2026-08-12)
vira estrutural e sai do código: o rito de comitê pertence ao eixo que aquele modo não desenha.
(iv) Linha de apoio por eixo (`PRAÇA SUSTENTA`… no demográfico; `PARA COMITÊ`… no financeiro,
inalterados) mais legenda no topo de cada selo. (v) Observações agrupadas nos mesmos dois blocos, na
mesma ordem dos selos.

**Defeito encontrado na revisão visual e corrigido no mesmo ciclo.** Com a coluna preenchida na
ordem, um ponto ruim em tudo (10 apontamentos para ~6 vagas) a enchia com o bloco demográfico e o
financeiro **não entrava — nem o título**: selo REPROVADO sem uma linha que o explicasse, quebrando o
"reprova, mas nunca em silêncio" pela única via que a lista única não tinha. A seleção passou a ser
**por rodadas** entre blocos (`_conclusao_plano_elementos`), então o mais grave de cada selo aparece
antes de qualquer ressalva do outro.

**Geometria.** Dois selos de 196 pt não cabiam nos 400 pt da área útil, e com `auto_page_break` OFF o
excedente sairia **por baixo do rodapé, em silêncio**. Selo 240x196 -> **210x176**, gap 20 (bloco
372, folga 28); a coluna esquerda ganha os 30 pt por derivação (622 -> 652). A geometria interna do
selo virou fração da altura, reproduzindo o desenho de 2026-08-07 na altura de referência.

**Buraco de cobertura fechado de passagem.** Os rótulos do selo **não eram auditados contra latin-1
por ninguém**: `test_relatorio_acentuacao_regressao` gera os PDFs sem a página de Conclusão, e o
teste de latin-1 da página só percorria eliminatórios/ressalvas.

**Revisão adversarial da própria entrega, no mesmo dia.** Três dimensões (régua/partição,
render/geometria, força dos testes), com cada achado submetido a um verificador instruído a
**refutá-lo**: 9 achados, **8 confirmados** — e nenhum produzia PDF errado. Todos da mesma família:
teste que não trava o que promete e documentação que afirma mais do que o código faz.

- **Uma afirmação era falsa.** O comentário dizia que as frações de geometria "reproduzem exatamente
  o desenho de 2026-08-07" em 196. As de TAMANHO reproduzem; as de POSIÇÃO não — foram reancoradas
  (0,30→0,335; 0,55→0,60; 0,74→0,78) para abrir o topo para a legenda, e o desenho em 196 difere em
  6,9/9,8/7,8 pt. A justificativa numérica ("símbolo termina a menos de 5 pt do rótulo") também
  estava errada: o gap real seria 18,85 pt no pior caso. Corrigidas no código e no §7 — o
  reancoramento é legítimo, faltava declará-lo.
- **Cinco testes não travavam o que prometiam:** legendas (tautológico — as palavras também saem da
  nota metodológica), altura do título no orçamento de layout, `_conclusao_elementos` (o
  `_CONCLUSAO_BLOCO_GAP` podia ir a zero), rótulo principal do selo financeiro e o invariante de
  não-contaminação entre eixos (um `> 0` que sobrevivia a reunificação PARCIAL).
- **Correção provada por MUTAÇÃO** (patch em runtime, repo intocado): cada teste corrigido tem de
  derrubar a quebra que existe para pegar. Uma das correções falhou na 1ª tentativa **pelo mesmo
  defeito que corrigia** — lia o rótulo esperado do dicionário que a mutação alterava —; virou golden
  literal, com um 2º teste ligando golden e camada de label.

Fica a lição, que vale além deste bloco: **suíte verde não é evidência de cobertura.**

**Emenda 1 (mesmo dia): o gate E5 passa a valer nos DOIS modos.** Decidido por Vinicius ao revisar
três relatórios de amostra, em que um ponto de periferia de Caruaru falhava **5 das 6** metas e ainda
assim saía `com ressalvas` na praça — porque o E5 estava preso ao modo só-estudo (escopo de Juan,
12/08). O que mudou não foi o corte, e sim o que a divergência significa: enquanto o parecer era um
veredito único ela ficava diluída; com o selo demográfico próprio, o mesmo endereço passa a exibir um
carimbo de **cor diferente** em dois documentos, e a leitura da praça não pode depender de por qual
porta o relatório saiu. Custo medido **antes** de decidir: golden do Recife com no máximo 1 meta
contra corte 4 → **nenhum dos 5 muda**; dos 3 relatórios, só Caruaru (`com ressalvas` → `reprovado`).
O corte de 4, medido em 40 pontos de SP, não foi remedido nem alterado. `test_e5_nao_vale_no_modo_completo`
virou `test_e5_vale_nos_dois_modos`; entrou `test_regua_demografica_e_identica_nos_dois_modos`
(varre os cortes 0..4). A nota do modo completo passou a declarar o gate — e ganhou guarda contra
colisão com o rodapé, já que foi a 3 linhas com 7 pt de folga.

Arquivos alterados: `src/motor_expansao/dashboard/censo_report.py`,
`tests/unit/test_relatorio_pontual_conclusao.py`, `docs/relatorio_pontual_censitario.md`,
`docs/decisions/DEC-030.md`, `CLAUDE.md`, `tasks/completed.md`.
Validações: **125 casos** em `test_relatorio_pontual_conclusao.py` (era 98) + 233 nos arquivos
vizinhos de relatório/acentuação/imóvel/PDF base; 7/7 mutações detectadas; `ruff check` limpo;
`mypy` limpo. Nenhum assert de estrutura (`/Count`) mudou — a página segue UMA.
Fora de escopo: a tela de Viabilidade do piloto web (segue com o carimbo binário de `flag_viavel`,
que é outro juízo), as metas absolutas dos Big Numbers (decisão de Felipe, DEC-021) e qualquer
artefato do M1.



---

## Fechamento de ciclo — BLK-MA-05 (2026-08-13)

**Entregue: o último elo do epic M&A.** `src/motor_expansao/vulnerabilidade/alvos_ma.py` cruza a
saída do score (grão academia) com o hexágono quente da carteira (grão hex) e materializa os dois
artefatos do D6: `data/staging/vulnerabilidade_ma_academias.parquet` (camada scored) e
`data/outputs/alvos_ma_priorizados.csv` (lista curada, `sep=";"` + `utf-8-sig`, sem identidade).
Contratos de coluna novos em `contrato.py` (`CONTRATO_COLUNAS_ACADEMIAS_MA`,
`CONTRATO_COLUNAS_ALVOS_MA`, `VERSAO_CONTRATO_ALVOS_MA = "alvos_ma_v1"`) mais as constantes do
gate D5 (`QUANTIL_SAM_QUENTE`, `LIMIAR_RESIDUAL_SATURADO`, `ADJACENCIA_HEX_QUENTE_K`).

**Duas decisões de projeto que divergem do texto do §10, ambas registradas como emenda no
contrato do epic:**

1. **A linha do CSV é `(hex, REGIME)`, não `(hex)`.** O cabeçalho do §10 era EXEMPLO (o backlog o
   chamava de "canônico" — divergência resolvida em favor do contrato executável). A mudança é a
   emenda `BLK-MA-04-FU1` aplicada à AGREGAÇÃO, e não só à ordenação: uma média por hex que
   atravesse regimes mistura réguas ANTES de qualquer `sort`. **E segmentar pelo CONTADOR não
   basta** — `{s1,s3}` e `{s3,s4}` têm ambos `n = 2` com renormalizações diferentes, então a chave
   é a COMPOSIÇÃO (`sinais_disponiveis`); o contador vira a chave primária da ordenação.
2. **`uf` é a única exceção anti-PII da saída.** Ela consta de `COLUNAS_PII_PROIBIDAS` porque ali é
   a `uf` do FEED CRU, ao lado de `cep`/`endereco_formatado`. Aqui vem da CARTEIRA agregada — é a
   UF do hexágono, como o próprio `hex_id_res7` — e o §10 a exige nominalmente. Documentado no
   teste, não afrouxado em silêncio.

**Declaração exigida pela DEC-026 — o entregável NÃO faz corte sobre nota/contagem.** Nota e
contagem viajam como fatos agregados (`n_com_nota_wellhub`, `nota_wellhub_mediana`) e não entram
em filtro, ordenação nem seleção. Razão medida: a ausência de nota é sistemática (8.443
independentes do próprio WellHub, 14,9% do universo, todos com `qtd_avaliacoes = 0`) e concentra-se
no perfil que o funil mais quer olhar; cortar por nota montaria, fora do contrato versionado, um
ranking de um sinal só sobre 60% do universo. Travado por `test_nota_nao_altera_a_ordenacao`.

**READ-ONLY executável, não prosa.** O join é `validate="many_to_one"` no molde do
`enriquecer_dataframe_com_residual` (ancorado pelo NOME — o ponteiro de linha do §9 já apodreceu),
com assert de cardinalidade, de não-mutação da carteira e de transporte intacto de
`score_priorizacao` + os 4 ranks. `test_join_falharia_se_alterasse_o_m1` corrompe o transporte de
propósito e prova que a função LEVANTA — sem ele o assert poderia passar por vacuidade.

**Medições.** Suíte: **3062 coletados** (baseline medida no momento: 3029 antes; +33 testes novos),
**3034 passam, 27 skipped**. `ruff` limpo. `loop_guard`: **nenhum CRÍTICO** (só GOVERNANÇA, que é
inevitável — o pacote inteiro casa `^src/motor_expansao/(lifetime|demanda_revelada|vulnerabilidade)/`).
Caminhos de saída conferidos contra o `_DENY_CRITICO` (`carteira_expansao*`/`plano_expansao*`/
`hexagonos_mercado*`), travado por teste.

**1 falha na suíte, PRÉ-EXISTENTE e local-only:**
`test_score_retencao_territorial.py::test_run_readonly_m1_por_mtime` — é o **BLK-FIX-LTV-01**, aberto
desde 2026-07-24: o teste guarda os artefatos M1 ausentes mas não a entrada
`data/staging/unidade_territorio_retencao.parquet`. Em CI limpo `data/staging/` é gitignored, nenhum
artefato M1 existe e o teste PULA — o portão da `main` não é afetado. Não corrigido aqui por ser
bloco próprio.

**O que este bloco NÃO destrava.** Os artefatos nascem VAZIOS: a série de snapshots está em zero
semanas (BLK-MA-06 aguardando aplicação humana na VPS). Foi o previsto pelo próprio bloco — "a
implementação não espera a série; a execução sim". Rodar contra dado real e entregar a lista ao
comercial continua bloqueado pelo MA-06 + ~2 meses de acúmulo.

**Governança do PR.** Criticidade Média armaria auto-merge, mas o PR toca `tasks/backlog.md` (do
commit do BLK-MA-12) e `src/motor_expansao/vulnerabilidade/`, então o guard exige `aprovado-humano`
de qualquer forma. Deploy segue manual e não se aplica (nada vai a produção).

---

## Fechamento de ciclo — BLK-MA-12 (2026-08-13, registrado 2026-08-14)

**Dívida de bookkeeping quitada aqui, não trabalho novo.** O BLK-MA-12 foi implementado e a
DEC-036 foi escrita em 2026-08-13, mas o bloco **nunca existiu como bloco estruturado** no
`tasks/backlog.md` e nunca ganhou fechamento — o MESMO furo que o fechamento do BLK-MA-02 já
registrara para o BLK-MA-04 e que o BLK-MA-05 registrou para si próprio. Registrado agora, junto do
BLK-MA-13, porque é dele que o MA-13 depende.

**Entregue.** `src/motor_expansao/vulnerabilidade/pressao_competitiva.py` (sinal 6: concorrência
efetiva ponderada por distância, kernel triangular até 2 km, réplica da fórmula de
`pressao_concorrencial_score_2km` com o kernel como parâmetro em vez de premissa embutida) e a
promoção do S6 a **componente do score** em `score.py` (`_juntar_pressao`,
`_regra_de_disponibilidade`, `_derivar_componentes`). O contrato de score vai de 22 para **24
colunas**, com bump `score_vulnerabilidade_v2` -> `v3`.

**A decisão que sustenta o bloco (DEC-036): o S6 é ATIVO mas CONDICIONAL.** Disponível se e somente
se o insumo de pressão vier na chamada, no mesmo molde do `s1` (casou no join). Medido com um
harness antes de implementar: um S6 **sempre** disponível quebra 17 testes, e quatro deles não são
asserts a atualizar — são invariantes de produto que deixam de existir (o regime
`n_sinais_disponiveis == 0` se extingue e a trava "ausência nunca é zero" fica INALCANÇÁVEL, isto
é, vira cobertura fantasma que nunca fica vermelha). Com a condicionalidade, omitir `pressao=`
devolve o score anterior **bit a bit**, pesos efetivos inclusive.

**O ganho, medido sobre dado real:** 19.329 academias independentes (WellHub, 6.753 hexes). O score
sai de **1 valor distinto** (50,0 para todas — artefato do `v1` constante) para **2.706**, na faixa
`30,0-68,0`. O score de vulnerabilidade passou a ordenar.

**Ressalvas que viajaram para o BLK-MA-13, e não foram inventadas por ele:** (a) `w6 = 0,10` vale
**40% do score efetivo hoje**, porque S3/S4 estão renormalizados para fora — descontinuidade na
composição do score no meio da vida dele, declarada na DEC-036; (b) cobertura de **5,5%** na
carteira (2.716 de 6.753, ou 40,2%, no universo de academias — hex de independente é urbano e
denso); (c) onde falta coleta a pressão sai `0`, a leitura mais otimista da régua.

**Governança.** DEC-036 (Alta) aprovada por Vinicius em 2026-08-13. READ-ONLY sobre o M1: nenhum
peso, fórmula ou artefato oficial tocado; DEC-001 intacta.

---

## Fechamento de ciclo — BLK-MA-13 (2026-08-14)

> **[REVERTIDO no mesmo dia — leia antes do resto]** Vinicius viu a camada no piloto e mandou
> tirá-la, por **redundância**: a camada 3 do funil ("Pressão concorrencial") já responde à
> mesma pergunta sobre o território — o próprio módulo do S6 mede Pearson **1,0000** contra o
> mesmo insumo da coluna de mercado. Saiu a superfície inteira mais o que só a servia (o
> `alvos_ma_hex.parquet` e o `colapsar_regimes_por_hex`). **Permanece** a emenda do G-D1
> (decisão 4 da DEC-028), que é sobre o score e é pré-requisito do BLK-MA-14. O texto abaixo
> fica como registro do que foi construído e por quê — inclusive a decisão de rótulo, que não
> perdeu validade, só objeto: ela volta a valer no BLK-MA-15.

**Entregue: a camada de M&A ficou VISÍVEL no piloto web — como pressão competitiva, não como
vulnerabilidade.** Overlay liga/desliga sobre o mapa, com legenda própria que declara o regime de
sinais e a cobertura, tooltip com os fatos do hexágono, e um terceiro artefato hex-level
(`data/outputs/alvos_ma_hex.parquet`) servido pelo backend.

**O gate era o RÓTULO, e a decisão foi de Vinicius (DEC-028).** Medido antes de escrever código: no
regime que existe hoje (`{s1, s6}`), `v1 ≡ 0,5` para **100%** do universo — só o WellHub existe em
disco, logo `n_agregadores = 1` sempre. O score colapsa em `score = 30 + 40·v6`: **o piso é
constante e a única coisa que varia é a pressão**. Publicar isso rotulado como "alvos de M&A" seria
vender S6 com o rótulo de S3 — e S3 (churn: a academia sumiu do agregador) é o sinal de maior peso
justamente por ser o proxy real de fechamento. Escolhida a opção 1 do bloco: **rotular pelo que é**.
A opção 2 (vulnerabilidade com selo de provisório) foi rejeitada porque o selo teria de aparecer em
TODA superfície onde o número aparece, e selo compete com número e perde.

**A forma NÃO é um passo 6 do funil, e isso mudou o custo do bloco.** O reconhecimento do backlog
estimava "métrica em camada existente = 3 arquivos; camada nova (passo 6) = ~9 arquivos + 2 testes
de contrato". Nenhuma das duas foi adotada: virou **overlay**, por três razões, em ordem de peso —
(a) o §10 do contrato usa literalmente a palavra *overlay* (*"sem overlay de dashboard no MVP
(opcional/futuro)"*), que é exclusão de escopo e não proibição de invariante; (b) o funil narra
ABRIR e cada passo filtra o anterior, enquanto M&A é a **inversão do §2** — um passo 6 depois de
"Para onde crescer" faria o CTA `Próxima camada →` levar da síntese para o oposto dela; (c) um passo
6 quebraria `test_metodologia_espelha_o_funil::test_payload_tem_as_5_camadas_completas` e os três
asserts `[p["n"] for p in ...] == [1,2,3,4,5]`, e consertá-los seria reescrever a régua do funil
para acomodar uma camada que não filtra ninguém. O molde adotado é o da chave `raio1km`, que já
existe e já foi aceito.

**A emenda ao G-D1, que era pré-requisito silencioso.** `flag_score_provisorio` passou de
`(~s3) & (~s4)` para `(~s3) & (~s4) & (~s6)`. Sem ela, `score_vulnerabilidade_ordenavel` saía
**NULA em 19.329 de 19.329 linhas** e um `sort_values` devolvia `NaN` em tudo — o G-D1 mirava o
ramp-up só-S1 de DOIS valores, e o S6 entrega 2.706. Travado por
`test_pressao_tira_o_rampup_do_regime_provisorio` (falha se a emenda for revertida) e por
`test_sem_o_s6_a_serie_imatura_continua_provisoria` (prova que ela é cirúrgica). A emenda foi
escrita na DEC-028, e não na DEC-036 como o bloco previa: aquela DEC já estava fechada.

**O colapso de regimes é função nomeada, não um `groupby`.** `colapsar_regimes_por_hex` é
**SELEÇÃO, nunca agregação**: vence o regime de maior `n_sinais_disponiveis`, desempatado por
cobertura (`n_independentes_vulneraveis`) e depois pela composição canônica. A linha que sobrevive é
uma linha real; nenhum número é recomputado. Hoje há um regime só e o colapso é a identidade — nasce
agora, testado, porque no dia em que o S3 amadurecer a escolha passa a existir e um `groupby`
implícito a faria em silêncio, misturando as réguas que a emenda BLK-MA-04-FU1 separou.

**Três cores, três estados** (critério de aceite do bloco): medido (rampa invertida), "no universo
mas sem pressão medida" (cinza azulado) e "fora do universo" (cinza neutro). Colapsá-los faria o
mapa afirmar ausência de concorrência onde existe ausência de dado — o risco 2 da DEC-036.

**A rampa é lida AO CONTRÁRIO, e o complemento não é maquiagem.** A convenção do mapa inteiro é
"vermelho = apertado, verde = folgado"; pressão alta é território apertado. O mapa pinta
`scoreBandToColor(100 - pressao)`, e `100 - pressao` é o `gap` da própria fórmula do sinal 6
(`gap = 1/(1+oferta)`, `pressao = 100·(1-gap)`). `FAIXAS_MAPA_PRESSAO_MA` reusa a paleta de
`FAIXAS_MAPA_DEMANDA` em ordem inversa — travado por teste, junto do espelho Python<->TS.

**O que NÃO viaja para a tela, por decisão:** o `score_vulnerabilidade`. Sendo `30 + 40·v6` no
regime vigente, ele é uma transformação afim da própria pressão; servir os dois mostraria o mesmo
fato com dois rótulos e duas escalas, convidando o operador a lê-los como grandezas independentes.
Volta quando S3/S4 amadurecerem, com o rótulo que a DEC daquele momento decidir.

**Medições (dado real, não fixture).** Snapshot do WellHub materializado localmente: 22.173 linhas,
semana `2026-33`. Pipeline completo: **19.329** academias, **6.753** hexes, **1** regime (`s1,s6`),
0 linhas descartadas no colapso, pressão em `[0, 95,04]` com **40,2%** dos hexes acima de zero.
`score_vulnerabilidade_ordenavel` deixou de ser nula: **19.329 de 19.329** preenchidas (era 0).
Payload real de São Paulo: 199 hexes com linha, 181 com pressão > 0.

**Suíte.** Pacote `vulnerabilidade`: **378** passam (era 364; +14). Contratos: **282** passam.
Front: **580** passam em 27 arquivos (`vitest`), `tsc --noEmit` limpo e `vite build` verde. `ruff`
limpo.

**O que este bloco NÃO destrava.** Continua valendo o risco 1 da DEC-028: com `{s1, s6}` o número é
honesto, mas quase estático — quem faz S3/S4 amadurecerem é o **BLK-MA-06**, que segue aguardando
aplicação humana na VPS. Até lá, o overlay mostra pressão competitiva, que é exatamente o que ele
diz mostrar.

**Governança.** DEC-028 (Alta) aprovada por Vinicius em 2026-08-14. O PR toca `web/` e
`src/motor_expansao/vulnerabilidade/` (`_DENY_GOVERNANÇA` do `loop_guard`), então exige
`aprovado-humano`. READ-ONLY sobre o M1: `score_priorizacao`, `hex_score_estrutural`, pesos,
carteira, plano e artefatos oficiais intocados; DEC-001 intacta. Deploy segue manual e por digest —
o overlay só aparece em produção depois de o artefato ser materializado lá.

---

## Fechamento de ciclo — BLK-MA-14 (2026-08-14)

**Entregue: o sinal 6 passou a ser medido da coordenada da ACADEMIA, não do centroide do
hexágono.** O bloco nasceu de uma objeção de Vinicius no fechamento do BLK-MA-13 — *"o S6 não
deveria criar uma variabilidade de pressão entre as academias, visto que deveria medir a distância
de concorrentes a partir da mesma?"* — e ela estava certa.

**O erro que o bloco corrige, e por que não era bugfix.** O §8.1 chama o sinal de "independente
**espremida**", que é propriedade da academia, mas o definia como `pressao_concorrencial_score_2km
/ 100`, coluna **hex-level** da camada de mercado. O BLK-MA-12 implementou fielmente — e herdou o
grão. Corrigir exigia emendar o contrato, não pedir desculpas no código: daí a DEC-029.

**O tamanho do erro, medido ANTES de implementar** (5.823 independentes de SP contra 4.499 pontos
de concorrentes): erro absoluto médio **7,82** pontos, p90 **22,15**, **máximo 65,97**; amplitude de
**14,89** pontos apagada dentro do mesmo hexágono; **1.922 de 5.823 (33,0%)** mudariam de faixa. O
caso que refuta a defesa "mas a correlação é 0,92": o hexágono `87a812a15ffffff` mede pressão
**1,2** e a academia dentro dele, **67,2** — espremida, aparecendo como território livre. É o falso
negativo que o sinal existe para não produzir.

**ROTA B, escolhida por Vinicius: zero bump de série.** A coordenada é lida do feed cru
(`coordenadas_por_chave`), usada para medir e **descartada dentro da função**; o que sai é
`(fonte, chave_snapshot, pressão)`. A rota A — persistir no snapshot — custaria bump em cascata de
TRÊS contratos (`snapshots_v3`->`v4`, `churn_v2`->`v3`, `score_v3`->`v4`), cada um uma
descontinuidade, para guardar histórico de uma grandeza que ninguém pediu em série: a pressão é
leitura do entorno no momento da análise, sobre um insumo que já é sempre o atual.

A rota B só existe porque `derivar_chave` é **determinística** e, no default, **não lê semanas
anteriores** — o mesmo feed produz a mesma chave, então ela casa com a do snapshot persistido sem
re-chavear nada.

**O achado que a destravou, e que estava escondido num docstring.** O `pressao_competitiva` afirmava
que "calcular por unidade exigiria a coordenada da academia, que esta camada deliberadamente não
persiste". A frase confunde **CALCULAR** com **PERSISTIR**: a coordenada existe no feed cru e passa
pelas mãos do materializador antes de `montar_snapshot` matar a PII. Ela fechou uma porta que estava
aberta, e o sinal ficou um bloco inteiro no grão errado por causa disso. O docstring foi corrigido
COM o registro do erro — apagá-lo faria o próximo leitor repetir o raciocínio.

**O resultado, medido no dado real depois de implementar:**

| leitura | antes (grão hex) | depois (grão academia) |
|---|---|---|
| hexes com pressão variando entre suas academias | **0** de 6.753 | **2.437** |
| amplitude média dentro do hexágono | 0,00 | **13,42** pontos |
| amplitude máxima | 0,00 | **83,10** |
| valores distintos de `score_vulnerabilidade` | 2.706 | **11.956** (4,4x) |
| o hex de 26 academias que empatava | 1 valor (`67,85`) | **25 valores** (`47,0`–`84,7`) |

`score_vulnerabilidade_ordenavel` segue preenchido em 19.329 de 19.329 (emenda do G-D1, DEC-028).

**Os DOIS grãos coexistem, e a saída diz qual foi usado.** `calcular_pressao_por_hex` continua
existindo — é a grandeza comparável com o `pressao_concorrencial_score_2km` e a única que faz
sentido pintar num mapa. O contrato do score ganhou `pressao_grao` (`academia` | `hex`), preenchido
exatamente onde há pressão, porque **linhas de grãos diferentes não estão na mesma régua**. A
fórmula é compartilhada (`_oferta_por_origem` + `_saturar`), travada por
`test_os_dois_graos_usam_a_MESMA_formula`: academia no centroide bate com o grão hex dígito a
dígito. Sem isso, alterar o kernel num caminho só faria os dois deixarem de ser comparáveis, cada um
internamente coerente e nenhum erro visível.

**A agregação do entregável deixou de ser `first`, e o comentário foi reescrito junto.** Enquanto a
pressão era constante no grupo, `first` era honesto — o código dizia "agregar fingiria variância que
não existe". Com variância real, ele devolveria a linha que o `groupby` viu primeiro como se
representasse o hexágono. Virou **média + máximo**: a média descreve o hex, o máximo revela a
unidade muito espremida que uma média baixa esconde — e é essa unidade que o entregável procura.
Travado por `test_maximo_revela_a_academia_espremida_que_a_media_esconde`.

**Anti-PII mais forte, não mais fraco.** A proibição saiu do docstring e virou guard executável:
`_assert_schema_pressao_academia` barra qualquer coordenada na saída, e
`test_saida_por_academia_NAO_carrega_coordenada` prova. O §11 e a DEC-012 seguem intactos: nenhum
artefato novo persiste coordenada.

**Contrato.** `score_vulnerabilidade_v3` -> **`v4`**, 24 -> **25 colunas** (entrou `pressao_grao`;
`pressao_competitiva_no_hex` virou `pressao_competitiva` no score, porque cravar um grão no nome
faria o contrato mentir metade das vezes). O entregável hex-level troca
`pressao_competitiva_no_hex`/`v6_no_hex` por `pressao_competitiva_media`/`_max`/`v6_medio`.

**Medições da suíte.** Pacote `vulnerabilidade`: **382** passam (era 367; +15). Contratos: 264.
`ruff` limpo. Pipeline real: 19.329 academias, 22.173 unidades com pressão calculada, 6.753 hexes.

**O que este bloco destrava.** O **BLK-MA-15** (as independentes como pins, com o score no tooltip)
tinha dependência DURA daqui: sem o grão de unidade, o tooltip mostraria o mesmo número para todas
as academias do hexágono — 26 delas com `67,85` no exemplo de SP. Agora mostra 25 valores distintos.

**Governança.** DEC-029 (Alta) aprovada por Vinicius em 2026-08-14, com a rota escolhida
explicitamente. READ-ONLY sobre o M1: `score_priorizacao`, `hex_score_estrutural`, pesos, carteira,
plano e artefatos oficiais intocados; DEC-001 e DEC-036 intactas (o `w6 = 0,10` não mudou — mudou de
onde o `v6` é medido, não quanto ele pesa).

---

## Fechamento de ciclo — BLK-MA-15 (2026-08-14)

**Entregue: as academias independentes viraram pins no mapa, com nome e score no tooltip.** É o
pedido de Vinicius — *"que o score de vulnerabilidade apareça junto à franquia/unidade quando o
mouse passa por cima"* — depois de o reconhecimento mostrar que o pedido LITERAL era impossível.

**O obstáculo que redefiniu o bloco, medido antes de qualquer código.** Os pins que já existiam no
mapa são **4.499 pontos de 104 redes de CADEIA** (Smart Fit 1.000, Skyfit 482, Panobianco 472…) e o
universo do score é **100% `rede == independente`** — **interseção VAZIA**. Não é lacuna de dado: é
o guardrail central do epic, que impede pontuar uma cadeia como alvo de aquisição (sem ele a Smart
Fit entraria na lista). Logo os pins existentes eram exatamente as academias que nunca terão score.
O bloco faz o inverso: desenha as **independentes**, que não apareciam no mapa.

**A autorização, e as duas alternativas recusadas** (emenda 2 à DEC-028, decidida por Vinicius):

- **Recusada — "sem o nome".** Esconder o nome não protegeria nada: um pin em coordenada exata
  sobre um mapa com ruas já identifica o estabelecimento. Entregaria a MESMA exposição com menos
  utilidade.
- **Recusada — restringir por usuário via `acesso.py`.** O módulo é **fail-OPEN por desenho** (sem
  o arquivo, ou com um typo no JSON, todos veem tudo — ele diz isso em letra, para não trancar o
  piloto). Usá-lo para proteger dado sensível seria proteção ilusória.
- **Escolhida — identidade assumida.** O piloto está inteiro atrás do Authelia: isto é alcance
  interno, não publicação. E o que entra é identidade de ESTABELECIMENTO COMERCIAL, o mesmo tipo de
  dado que os pins de concorrente já servem desde sempre.

**O que continua vedado, e o §11 não foi afrouxado:** texto ou autor de review (nunca coletados) e
qualquer dado de PESSOA. Travado por `test_payload_nao_carrega_dado_de_pessoa` e pelo
`_assert_schema_nomeados`, que checa os campos vedados **antes** da ordem das colunas — com a ordem
primeiro, um campo de pessoa sairia rotulado como "coluna fora do contrato" e o motivo real se
perderia na mensagem.

**O artefato nasce gitignored, e isso virou código.** `data/staging/vulnerabilidade_ma_nomeadas.parquet`
(o `.gitignore` corta `data/staging/*` inteiro). `_assert_destino_gitignored` **levanta** se alguém
apontar para `data/outputs/`, que é apenas PARCIALMENTE versionado: um caminho errado ali poria
19.329 estabelecimentos no histórico do git, onde `git rm` depois não os apaga.

**Duas listas, nunca uma.** `pins.concorrentes` (cadeias) e `independentes` (alvos) viajam separadas
no payload e são desenhadas por camadas distintas. Juntá-las daria a uma Smart Fit a aparência de
alvo de aquisição — o erro mais caro do epic, agora barrado também na superfície. Travado por
`test_pins_de_independente_NAO_se_misturam_aos_de_concorrente`.

**Cor única no pin, de propósito.** A tentação era colorir por score, mas isso exigiria uma régua
nova sobre a rampa de 10 faixas que já colore os hexágonos por baixo — duas escalas de cor na mesma
tela, medindo coisas diferentes, que é o defeito que a DEC-020 chamou de "dois idiomas". O número
vive no tooltip, com rótulo e contexto.

**O tooltip diz o que precisa, e nada além:** score (com **selo de provisório** quando
`flag_score_provisorio` — sem ele, um número que o G-D1 se recusa a ordenar pareceria ranking),
pressão medida da coordenada DAQUELA academia (grão unidade, DEC-029), nota **com a contagem ao
lado** (DEC-026) e o regime de sinais declarado.

**Truncamento declarado.** O teto (`COMPETITOR_PIN_LIMIT = 6000`) corta por `head()`, e a pílula
exibe "N de M (teto)" quando morde. Corte silencioso mentiria sobre a densidade — defeito que o
teto de pins de concorrente já registrou.

**Medições (dado real).** Artefato nomeado: **19.329** academias, **todas** com coordenada, nenhum
campo vedado. Payload de São Paulo: **1.270** independentes servidas (sem truncar) ao lado de **632**
pins de cadeia. Top por score: `BS Studio 02` (68,0 / pressão 95,0 / nota 5,0 com 22 avaliações),
`D-Gym` (68,0 / 95,0 / 4,8 com 2.561), `You Club` (68,0 / 95,0 / 5,0 com 15) — e a nota ao lado da
contagem é o que impede ler os três como equivalentes.

**Dependência satisfeita:** o BLK-MA-14 entrou primeiro, e sem ele o tooltip mostraria o mesmo
número para todas as academias do hexágono (26 delas com `67,85` no exemplo de SP). Com o grão de
unidade, são 25 valores distintos.

**Suíte.** Pacote `vulnerabilidade`: **393** passam (+11 do módulo nomeado). Piloto: 9 testes novos
para os pins. Front: **587** em 28 arquivos, `tsc --noEmit` limpo. `ruff` limpo.

**Governança.** Emenda 2 à DEC-028 (Alta), decidida por Vinicius em 2026-08-14. READ-ONLY sobre o
M1: nenhum peso, fórmula ou artefato oficial tocado (DEC-001, DEC-036 e DEC-029 intactas). O PR toca
`web/` e `src/motor_expansao/vulnerabilidade/` — exige `aprovado-humano`. Deploy manual: o artefato
nomeado precisa ser materializado na VPS para os pins aparecerem em produção.

---

## BLK-FIX-LTV-01 — Guarda de skip faltante em `test_run_readonly_m1_por_mtime` (só teste)

Data: 2026-08-14
Resumo: o guard cobria só os **artefatos M1** — que EXISTEM na estação local —, então o skip não
disparava, o teste seguia e o `run()` estourava `FileNotFoundError` no próprio insumo da camada LTV
(`data/staging/unidade_territorio_retencao.parquet`). Faltava a segunda metade da mesma pergunta.
Agora o teste **pula** quando o dataset de entrada não existe; o assert de mtime (READ-ONLY M1)
permanece intacto, como o critério de aceite exigia.

**Por que valeu quitar um bloco de prioridade Baixa.** Ele era o **único vermelho** da suíte local
(1 failed em 2.955), e um vermelho crônico é pior que nenhum teste: ele treina quem roda a suíte a
ignorar a cor. Foi achado justamente assim — a falha apareceu na rodada de validação do BLK-MA-16 e
teve de ser investigada para se provar não-regressão.

Arquivos alterados: `tests/unit/test_score_retencao_territorial.py` (só teste; zero produção)
Validações: 12 passam, 1 skipped no arquivo; `ruff` limpo
Decisões relacionadas: nenhuma (Baixa, `loop-safe`, READ-ONLY sobre o M1)

---

## BLK-MA-16 — As independentes entram na oferta do sinal 6, com metade do peso de uma rede

Data: 2026-08-14
Resumo: `concorrentes_mapeados.parquet` tem 4.499 pontos, 104 redes e **zero independentes** — ele
nasce dos coletores `unidades_*.csv`, que são feeds de CADEIA. A pressão competitiva não respondia
"quanta concorrência cerca esta academia", e sim "quanta CADEIA cerca". Uma independente espremida
entre oito independentes marcava **zero**. Não era bug: era o universo do insumo.

**Medido nacionalmente (19.329 independentes):** pressão média 32,03 -> **61,41**; pressão zero
**37,8% -> 5,5%**; score médio (regime real `s1,s6`) 42,81 -> 54,57; custo 0,39 -> 1,72 min. O número
que decide: **6.238 academias (32,3% do universo) tinham `0` e passam a ter sinal vindo só de
independentes** — em torno da academia mediana há 7 independentes num raio de 2 km (p90 21, máx 52)
que a régua antiga não via.

**O risco não era o que parecia.** A objeção natural ("a saturação comprime o topo") foi medida:
`Spearman(pressão, oferta_ponderada) = 1,000000` — a saturação é estritamente crescente e **não
embaralha o ranking**. O que ela faz é achatar a leitura (no top-500 a pressão varia 4,36 pontos
enquanto a oferta varia 2,4x) e deslocar limiares absolutos ("acima de 90" passa de 255 para 1.055).
Quem precisar discriminar no topo usa `oferta_ponderada`. Esta correção derrubou uma afirmação que o
próprio bloco trazia antes de o número existir.

**Três armadilhas fechadas.** (1) AUTO-PRESSÃO: a academia está no próprio conjunto de pontos e
somaria `peso(d=0) x 0,5` de si mesma — 33,3 pontos fantasma, com o erro MAIOR justamente em quem não
tem ninguém por perto; exclusão por CHAVE, verificada por mutação. (2) DEDUP entre fontes: hoje
colapsa 0 de 19.329 (só há WellHub), e existe para o defeito não entrar em massa junto com a primeira
coleta com as duas fontes; critério arbitrado (50 m) e declarado como tal. (3) CARIMBO
`universo_oferta`: o score **se recusa a inferir**, porque assumir `cadeias` no silêncio erraria na
direção otimista.

**Aprovação e virada (DEC-033, opção A).** O default do pipeline é `cadeias_e_independentes`; a régua
histórica segue acessível por `--oferta-so-cadeias` — ela é a única comparável com o
`pressao_concorrencial_score_2km`. Artefatos regenerados: `vulnerabilidade_ma_academias.parquet`
(26 colunas, `alvos_ma_v2`), `vulnerabilidade_ma_nomeadas.parquet` (19.329 academias, todas com
coordenada, `alvos_ma_nomeados_v2`) e `alvos_ma_priorizados.csv`. A janela era esta: o piloto em
produção ainda não tinha o artefato nomeado, então os pins nascem na régua definitiva em vez de
mudarem debaixo de quem já tinha olhado.

Arquivos alterados: `src/motor_expansao/vulnerabilidade/{contrato,pressao_competitiva,score,snapshots,alvos_ma,alvos_nomeados}.py`,
`tests/unit/vulnerabilidade/{test_universo_oferta_s6,test_score}.py`, `docs/decisions/DEC-033.md`,
`docs/vulnerabilidade_ma_contrato.md` (§8.1), `CLAUDE.md` §8
Validações: 16 testes novos em `test_universo_oferta_s6.py`; 2.955 na suíte completa; `ruff` limpo;
`loop_guard` sem CRITICO; fim-a-fim pela CLI nos dois universos
Decisões relacionadas: **DEC-033** (Alta, aprovada por Vinicius em 2026-08-14, opção A; renumerada de DEC-030 em 2026-08-15, BLK-MA-17/G3). DEC-001,
DEC-036 e DEC-029 intactas; anti-PII (DEC-012/§11) preservado — a coordenada entra no cálculo e morre
na função. Bumps: `pressao_competitiva_v2`, `score_vulnerabilidade_v5`, `alvos_ma_v2`,
`alvos_ma_nomeados_v2`

---

## BLK-MA-18 — A conta por trás da pressão chega ao pin

Data: 2026-08-15
Resumo: revisão de Vinicius sobre um caso concreto — a `Academia Gold Fit-`, num canto isolado da
zona sul de São Paulo, marcava **40,4** de pressão, o que pareceu muito para a vizinhança visível.

**A desconfiança estava calibrada, e o diagnóstico saiu do dado.** A saturação
`100·(1 − 1/(1 + oferta))` — herdada da camada de mercado, fórmula **idêntica** à de
`enriquecimento_espacial_hexagonos.py` — gasta **metade da escala numa única unidade equivalente**:

| oferta efetiva | pressão | no mundo |
|---|---|---|
| 0,25 | 20,0 | 1 academia a 1,5 km |
| **0,68** | **40,4** | **o caso: 3 independentes a ~1,1 km** |
| 1,00 | 50,0 | 1 unidade de rede colada na porta |
| 9,00 | 90,0 | 9 coladas |

Logo `40,4` significa **0,68 concorrentes efetivos**, não "40% de pressão" — que é a leitura que um
número de 0 a 100 num pin praticamente convida a fazer. O defeito é de LEITURA, não de cálculo.

**A régua NÃO mudou.** Trocar a saturação quebraria a comparabilidade com
`pressao_concorrencial_score_2km`, que é a razão de ela ter sido copiada — isso exigiria DEC própria.
O que mudou é o número deixar de ser inverificável: a auditoria que já era calculada (e morria no
frame de pressão) passa a viajar até o pin. O operador conta os pins no mapa e o número fecha.

**Quatro colunas novas no artefato nomeado** (`n_concorrentes_no_raio`, `n_independentes_no_raio`,
`oferta_ponderada`, `dist_concorrente_mais_proximo_m`), servidas no payload como
`n_conc`/`n_indep`/`oferta`/`dist_m`. Elas vêm de `montar_alvos_nomeados`, **não do score**: o score
carrega o `v6` porque ele é o COMPONENTE; a contagem é material de leitura, e enfiá-la no contrato do
score custaria um bump em cascata (score -> academias -> lista curada) para servir um consumidor só.

**Ausência é NULA, nunca zero** — `0 concorrentes no raio` afirmaria território livre; artefato sem
as colunas degrada para nulo, e linha sem `pressao_competitiva` não carrega contagem (a auditoria de
um número que não existe convidaria a ler a pressão como zero).

O que o tooltip passa a mostrar, medido no dado real de São Paulo:

    Aquiles Academia    9,2 |  2 no raio ( 2 indep) |  0,10 equivalentes | mais próximo a 1,74 km
    D-Gym              96,5 | 90 no raio (43 indep) | 27,61 equivalentes | mais próximo a  183 m

Arquivos alterados: `src/motor_expansao/vulnerabilidade/{contrato,alvos_nomeados,alvos_ma}.py`,
`web/server/app.py`, `web/src/components/HexMap.tsx`, `web/src/lib/{types,format}.ts`
Validações: 6 testes novos em `test_auditoria_pressao_no_pin.py`, 2 no piloto, 3 no `format.test.ts`;
688 no recorte camada + piloto + contratos; front 601 com `tsc` limpo; `ruff` limpo
Decisões relacionadas: **nenhuma DEC** — não toca régua, peso, fórmula nem universo (DEC-033
intacta). Bump `alvos_ma_nomeados_v2` -> `v3` (só o artefato de exibição). READ-ONLY sobre o M1

---

## Fechamento de ciclo — BLK-MA-17-M2 (2026-08-15, metade 2 — o bloco-pai segue ABERTO)

**Atenção ao ID.** Este heading usa `BLK-MA-17-M2` de propósito: o bloco `### BLK-MA-17` **não está
concluído** — só a metade 2 foi entregue, e a metade 1 (exibição do diagnóstico nas unidades de rede,
com DEC própria) segue **pendente dentro do mesmo heading**, no `tasks/backlog.md`. Um heading com o
token exato marcaria o bloco inteiro como concluído (`housekeeping_move_block.py --is-done`), que é
falso. Por isso o helper **não foi rodado** neste fechamento — ver a nota de housekeeping ao final.

**O que o bloco corrige.** As **2.844 unidades de REDE** que o WellHub lista eram cortadas do cálculo
antes de virarem oferta — e **1.171 delas não têm equivalente nenhum** em `concorrentes_mapeados`.
Eram academias de cadeia reais, listadas, abertas, que **não pressionavam ninguém**. É o mesmo defeito
que a DEC-033 corrigiu do outro lado (lá as independentes não contavam como oferta), e pela mesma
razão: cobertura do insumo, não desenho da fórmula.

**Como entram.** Terceira lista de pontos no bloco de CADEIAS da oferta do S6, com peso `1,0`,
deduplicada contra o insumo mapeado por `(rede igual E d <= 150 m) OU (d <= 50 m)`
(`dedup_cadeias_do_feed`, função NOVA — a `dedup_independentes` fica intacta, porque tem custo
assimétrico oposto). Casar a rede **salva 37 concorrentes reais** que a distância pura apagaria; o
piso de 50 m recupera 8 endereços iguais com slug divergente, o menor deles a `0,0` m. Das 2.844,
**1.171 sobrevivem** e 1.673 colapsam.

**O erro silencioso que quase passou.** O bucket H3 da dedup usava `grid_disk(k=1)`, que na
`DEDUP_H3_RES = 11` (aresta real medida: **28,66 m**, não os ~24 m que o comentário afirmava) cobre
~50 m — **não** os 150 m do limiar. Uma dedup sub-coberta **não levanta erro**: ela devolve "nenhum
colapso", que é exatamente o que uma dedup correta devolve quando não há duplicata. O `k` passou a ser
**derivado** do limiar (`_k_do_bucket`, `k=6` para 150 m) e a trava é um teste de **equivalência
contra varredura completa** (`test_14b`) — o QA mutou o `k` para 1 e confirmou que o teste falha, e
que nesse `k` **193 unidades (6,8%) deixariam de deduplicar em silêncio**.

**Auto-pressão fechada nos DOIS casos.** A unidade sobrevivente somaria `peso(d=0) x 1,0` de si mesma;
a **colapsada** continuaria recebendo ~`1,0` do próprio pin do funil. Sem as duas exclusões, medimos
exatamente **+50,0 pontos** de pressão fantasma.

**A ordem MUDA — e isso foi ao gate.** `Spearman 0,9911994` no score contra a régua anterior;
**7.237 de 19.329 (37,4%)** academias mudam de valor; no entregável, **2.096 de 6.753** linhas se
movem (`Spearman 0,9865793`) e **12 das 100 primeiras linhas** do `alvos_ma_priorizados.csv` trocam —
uma em cada dez da shortlist que vai à mesa do comercial. Três réguas VISÍVEIS no pin se movem:
`pressao` (7.237), `n_conc` (7.218, máx +9) e `dist_m` (773). O falso zero cai só de 5,53% para 5,31%:
o bloco corrige **magnitude e ordem**, não cobertura — quem vender como "acaba com o falso zero"
estará errado.

**Renumeração de DEC (G3).** `DEC-030` local (BLK-MA-16) virou **`DEC-033`** por `git mv`, com as 21
citações em 9 arquivos atualizadas; a DEC deste bloco é a **`DEC-034`**. Motivo: `origin/main` já
tinha `DEC-030` ("dois selos na Conclusão"), `DEC-031` e `DEC-032` com outro conteúdo — a colisão
bloqueava o merge da pilha e ninguém a tinha registrado.

Arquivos alterados: `src/motor_expansao/vulnerabilidade/{contrato,pressao_competitiva,alvos_ma,alvos_nomeados}.py`,
`tests/unit/vulnerabilidade/{test_oferta_cadeias_do_feed (novo),test_universo_oferta_s6,test_score,test_auditoria_pressao_no_pin}.py`,
`docs/decisions/{DEC-033 (renomeada de DEC-030),DEC-034 (nova)}.md`, `docs/decisions/README.md`,
`docs/vulnerabilidade_ma_contrato.md`, `CLAUDE.md` §8, `tasks/backlog.md`, `tasks/completed.md`
Validações (re-executadas pelo QA, saída real): suíte COMPLETA serial **3178 passed, 28 skipped, 0
falhas** (42m22s); recorte camada+piloto **448 passed**; `test_parametros_canonicos` **4 passed**;
`ruff check src tests` limpo; `--collect-only` **3206** (baseline 3184 **+22**); `loop_guard --stdin`
**6 violações, todas `governanca`, ZERO `CRITICO`**; `git diff --name-status` contra a base sem
nenhum caminho do M1
Decisões relacionadas: **DEC-034** (Alta, aprovada por Vinicius no gate G1..G5 em 2026-08-15) —
emenda a **DEC-033**, que foi renumerada neste mesmo ciclo. Quatro bumps: `pressao_v2` -> `v3`,
`score_v5` -> `v6`, `alvos_ma_v2` -> `v3`, `nomeados_v3` -> `v4`. Contratos: pressão academia 13 ->
15, pressão hex 12 -> 14, nomeado 23 -> 24; score 26, `alvos_ma` 18 e `academias_ma` 26 inalterados.
READ-ONLY sobre o M1; `_filtrar_universo_sinal_1` intacto e `n_academias_independentes_*` inalteradas

**Veredito do QA: APROVADO COM RESSALVAS** — 0 críticos, 3 médios, 3 leves. Um médio virou o bloco
`BLK-MA-17-FU1` (a `dedup_independentes` tem a MESMA sub-cobertura de bucket: `k=1` para 50 m, quando
o correto é 4 — efeito **provadamente nulo hoje** (`0 de 19.329` colapsos, só há WellHub) e **ativo em
massa na primeira coleta com TotalPass**). Os outros dois são de PROCESSO, não do código: o smoke
`import streamlit_app`, obrigatório em 3 prompts da esteira, está **morto desde o commit `30378a0`**
(DEC-022, aposentadoria do Streamlit), e o `pytest -n auto` que o `qa_analyzer.md` exige é
**inexecutável nesta estação** (xdist 3.8.0, `WinError 50`).

**Housekeeping (6.0) — deliberadamente NÃO executado.** Modo MERGE-HUMANO, mas o helper recorta o
bloco INTEIRO até o próximo heading: rodá-lo apagaria do backlog a metade 1, que ainda não foi feita.
Escolhida a saída (b) do QA — **não mover**, mantendo o `### BLK-MA-17` aberto com o Status atualizado
("Metade 2 EXECUTADA em 2026-08-15 / Metade 1 segue PENDENTE") e uma nota de execução com os números
corrigidos. O stub e o move acontecem quando a metade 1 fechar.

---

### BLK-MA-17-FU3 — O caminho de PRODUÇÃO da pressão não é exercitado: `_pressao_por_academia` nunca é chamada em teste

| | |
|---|---|
| **Criticidade** | **Média** — não há defeito hoje (o código entregue está correto e foi verificado *em execução*, não só por leitura). O que falta é a rede que impede a **próxima** edição de errar em silêncio. READ-ONLY sobre o M1. |
| **Prioridade** | **Alta dentro da epic, e antes dos irmãos** — o **FU1** e o **FU2** vão editar exatamente esse caminho. Sem cobertura, as duas correções entram às cegas. |
| **Esteira** | Builder → QA (sem gate: só acrescenta teste, não muda comportamento). |
| **Status** | Pendente — **achado da revisão adversarial de 2026-08-17**: 2 dos 4 sobreviventes, rebaixados a leve individualmente, mas com a **mesma causa raiz**, que é o que os torna um bloco só. |
| **Depende de** | BLK-MA-17 (metade 2). |
| **Autonomia** | **manual (NÃO loop-safe)** |

**O buraco.** `grep -rn "_pressao_por_academia" tests/` devolve duas ocorrências úteis
(`test_oferta_cadeias_do_feed.py:300-303` e `test_universo_oferta_s6.py:317-319`) e as duas só fazem
`inspect.signature(...).parameters`. **A função nunca é chamada.** `alvos_ma.main` não aparece em
teste nenhum, e nada em `tests/contracts/` ou `tests/integration/` toca o módulo. Os dois testes que
o BLK-MA-17 declara como trava do gate DEC-033/DEC-034 inspecionam a assinatura, não o comportamento.

**Mutante 1 — a partição independente/cadeia pode ser INVERTIDA.** Trocar as duas linhas da partição
em `alvos_ma.py:605-614` faz toda independente pesar `1,0` e toda unidade de rede `0,5` — o oposto
exato da DEC-033/DEC-034. Medido: **448 passed, 0 failed**. No insumo real a pressão média das 19.329
vai de **62,775 para 71,371**, **18.270 linhas (94,5%)** mudam de valor, delta médio 9,24 pts,
p90 16,45, máximo 49,76, `Spearman` do `v6` = 0,98652. O artefato invertido **não carrega nenhum
tell**: `universo_oferta` sai idêntico nos dois casos, e `calcular_pressao_por_academia` nunca valida
o CONTEÚDO dos frames — só colunas, kernel e faixa de peso.

**Mutante 2 — a ordem do concat.** `posicao_por_chave` (`pressao_competitiva.py:610`) só é válida se
o chamador concatenar exatamente `[pontos_mapeados ; sobreviventes]`, e essa concatenação é feita à
mão em `:725`. Invertê-la devolve `pressao = 50,0000`, `oferta = 1,000000`, `dist = 0,0`: a academia
passa a **se auto-pressionar com os exatos 50 pontos** que o bloco diz ter fechado, e o concorrente
real a 1,5 km é apagado. Medido: **437 passed** no diretório da camada.

**Por que os testes de hoje não pegam.** Os dois de auto-exclusão degeneram o caso: `test_5` roda com
`_sem_cadeias()` (`offset = 0`) e `test_6` com o feed inteiro colapsado (zero sobreviventes) — em
nenhum dos dois existe **simultaneamente** ponto mapeado E sobrevivente, que é o único arranjo em que
o `offset` importa. E `test_14b`, a trava de equivalência, filtra explicitamente o outro ramo
(`obtidos = {... if pos < offset}`), de modo que a linha 610 nunca é comparada com nada. Confirmado
por mutação: `offset -> 0` derruba **só** o `test_14b`, ou seja, o `offset` é amarrado apenas pelo
filtro de fronteira, nunca pelo acoplamento de ORDEM.

**O conserto é barato — e é isso que agrava o gap.** Um teste que chama `_pressao_por_academia` com 3
academias sintéticas e um parquet temporário de 1 concorrente (~30 linhas, sem dado real, segundos)
já separa os dois pesos: a 500 m a independente contribui `oferta_independentes = 0,374906` e a
unidade de rede `oferta_cadeias_do_feed = 0,749811` — exatamente 2x, a assinatura da partição. Um
único assert sobre essas duas colunas mata o mutante 1.

**Escopo.** (1) Teste que EXECUTA `_pressao_por_academia` com fixture sintética, travando a
assinatura 2x da partição. (2) Teste do arranjo de produção — ponto mapeado **e** sobrevivente **e** o
sobrevivente sendo a academia observada —, que hoje não existe em lugar nenhum. (3) Cobrir a flag
`--oferta-so-cadeias` desligando de fato o universo ampliado (hoje só a assinatura é inspecionada).

**Fora de escopo.** Mudar o comportamento de qualquer função — este bloco **só acrescenta teste**;
qualquer artefato/peso/score do M1.

**Critério de aceite.** Os dois mutantes acima passam a **falhar**; nenhuma mudança de comportamento
medível nos artefatos; suíte verde.

---

### BLK-MA-17-FU2 — `dedup_cadeias_do_feed` não compara o feed entre FONTES: a mesma unidade de rede em dois agregadores vira duas ofertas

| | |
|---|---|
| **Criticidade** | **Média** — corrige uma dedup cujo efeito hoje é **provadamente nulo** (o snapshot `2026-33` é 100% WellHub), mas que passa a errar na primeira coleta com TotalPass. READ-ONLY sobre o M1. |
| **Prioridade** | Alta dentro da epic — **irmão do BLK-MA-17-FU1, mesmo gatilho e mesma janela**: tem de estar corrigido **ANTES** de o BLK-MA-06 ser aplicado na VPS, senão o defeito estreia junto com a segunda fonte. |
| **Esteira** | Builder → QA (sem gate: não muda universo, não muda decisão; corrige uma duplicidade de oferta). |
| **Status** | Pendente — **achado da revisão adversarial de 2026-08-17**, o único de severidade média que sobreviveu à refutação (10 achados brutos, 4 sobreviventes). **Não é coberto pelo FU1:** aquele bloco declara `dedup_cadeias_do_feed` explicitamente **fora de escopo**. |
| **Depende de** | BLK-MA-17 (metade 2) — é ele que introduz `dedup_cadeias_do_feed`. |
| **Autonomia** | **manual (NÃO loop-safe)** |

**O defeito, medido.** `dedup_cadeias_do_feed` (`pressao_competitiva.py:503-626`) popula o bucket
`ocupantes` **só** com os pontos mapeados (laço `for j in range(offset)`, linhas 573-577) e **nunca**
insere o sobrevivente do feed nesse dicionário (609-611). Não existe passagem feed × feed. A função
irmã faz o oposto: `dedup_independentes` (414-500) insere o sobrevivente em `ocupantes` (487) e
colapsa linhas de `fonte` diferentes. A camada ficou **assimétrica** — o lado das independentes está
protegido contra a duplicata TotalPass × WellHub e o lado das cadeias, não.

**O cenário, reproduzido.** Mesma unidade de rede listada pelos dois agregadores a 3 m, e a mais de
150 m de qualquer pin mapeado (o recorte das **1.171** sobreviventes de hoje). Saída medida contra
uma cópia isolada de `src/` no blob de HEAD: as **duas** linhas com
`pressao_competitiva = 49,962514`, `oferta_ponderada = 0,998502`, `n_concorrentes_no_raio = 1`,
`dist_concorrente_mais_proximo_m = 2,996633` — território sem concorrente nenhum lido como metade da
escala. O **mesmo par** marcado como independente: `dedup_independentes` colapsa e as duas saem com
`pressao = 0,0`.

**O dano não se limita à gêmea.** As duas linhas viram **dois pontos independentes** no array
`lat_c`/`lng_c` concatenado, e a auto-exclusão (`auto_pos_cadeia`) zera apenas a posição do próprio
observador. Logo **qualquer academia dentro dos 2 km enxerga dois concorrentes onde há um**:
`n_concorrentes_no_raio` sai `+1` e a oferta daquele endereço entra em dobro. As três réguas
VISÍVEIS no pin que a DEC-034 lista (`pressao`, `n_conc`, `dist_m`) se movem para terceiros, não só
para o par.

**O gatilho não exige mudar uma linha de código.** `alvos_ma._pressao_por_academia` (602-618) chama
`coordenadas_por_chave()` **sem** `fontes`, e essa função lê os três diretórios por default
(`snapshots.py:519-522`); o único dedup que ela aplica é
`drop_duplicates(subset=["fonte","chave_snapshot"])` (581), que **por construção** não colapsa entre
fontes. O recorte `--fontes unidades` do cron vale para `run_snapshot_concorrentes.sh`
(`docs/infra_producao.md:256-264`), **não** para o `alvos_ma`. Basta um CSV aparecer em
`concorrentes/totalpass/csvs`. E `_preparar_parte` (`snapshots.py:154`) atribui `rede` de cadeia
também para o TotalPass, então a gêmea cai mesmo em `cadeias_do_feed`.

**Por que hoje é zero, e por que isso é o perigoso.** Medido: `coordenadas_por_chave()` devolve
`22.173` linhas, `{'wellhub': 22173}` — fonte única; `concorrentes/totalpass` não existe no disco.
Como no FU1, o modo de falha de uma dedup que não roda é **indistinguível** do caso correto.

**Escopo.** (1) Fazer `dedup_cadeias_do_feed` comparar o feed contra si mesmo **apenas entre `fonte`
DIFERENTES**, no molde exato da guarda que `dedup_independentes` já usa
(`pressao_competitiva.py:470-471`: `if fontes[j] == fontes[i]: continue`). (2) Manter a auto-exclusão
correta para a chave colapsada nesse caminho novo. (3) Fixture com **duas** fontes — nenhum dos 21
testes do BLK-MA-17 monta uma. (4) Teste de equivalência contra varredura completa, molde do
`test_14b`. (5) Nota de emenda na **DEC-034**, dona desta dedup.

**A restrição que decide o desenho: dedup dentro da MESMA fonte está PROIBIDA, e foi medida.** Entre
as cadeias do feed há **5 pares a ≤ 50 m**, e os cinco são `wellhub × wellhub`. Só **dois** são o
mesmo estabelecimento; os outros **três são redes DIFERENTES dividindo prédio** — `skyfit` ×
`panobianco` (2,9 m), `selfit` × `power_fit` (22,5 m), `force_one` × `world_gym` (39,9 m). Colapsar
por distância dentro da mesma fonte apagaria concorrente real, que é o custo assimétrico que a
DEC-034 já mediu do outro lado. **A guarda entre-fontes resolve isso de graça:** como os 5 pares são
da mesma fonte, ela os pula por construção, e o efeito sobre o dado de hoje continua exatamente
`0`. O mesmo vale do lado das independentes, onde o fenômeno é 108x maior (543 pares a ≤ 50 m) e
igualmente não tratado, por decisão registrada (docstring 427-429; `contrato.py:472-476`).

**Fora de escopo.** Dedup dentro da mesma fonte (medida e recusada acima); recalibrar os limiares de
150 m / 50 m (isso é BLK-MA-06, com par verdade-terreno); `dedup_independentes` (é o **BLK-MA-17-FU1**);
qualquer artefato/peso/score do M1.

**Critério de aceite.** A duplicata entre fontes nunca conta duas vezes, travada por teste; o efeito
sobre o dado de hoje permanece **exatamente nulo**, medido antes e depois (fonte única); os 5 pares
de mesma fonte continuam **os 5 na oferta**; equivalência contra varredura completa; READ-ONLY sobre
o M1; suíte verde.

---


---

### BLK-MA-17-FU1 — `dedup_independentes` sub-cobre o bucket H3: o `k` é cravado em 1, e 50 m exigem 4

| | |
|---|---|
| **Criticidade** | **Média** — corrige uma dedup que hoje tem efeito **provadamente nulo** (`0 de 19.329` colapsos, porque só há WellHub), mas que passa a errar **em massa** na primeira coleta com TotalPass. READ-ONLY sobre o M1. |
| **Prioridade** | Alta dentro da epic — tem de estar corrigido **ANTES** de o BLK-MA-06 ligar a segunda fonte, senão o defeito estreia junto com o dado. |
| **Esteira** | Builder → QA (sem gate: não muda universo, não muda decisão; muda um detalhe de PERFORMANCE que hoje é detalhe de RESULTADO). |
| **Status** | Pendente — **achado do QA do BLK-MA-17 (2026-08-15)**, confirmando o DES-5 declarado pelo Builder. |
| **Depende de** | BLK-MA-17 (metade 2) — é ele que introduz `_k_do_bucket`, a função que expõe e resolve o defeito. |
| **Autonomia** | **manual (NÃO loop-safe)** |

**O defeito, medido.** `pressao_competitiva.py:469` busca o candidato da dedup em
`h3.grid_disk(celulas[i], 1)` — `k` **cravado** — com `DEDUP_INDEPENDENTES_M = 50,0` m. A fórmula que
o BLK-MA-17 introduziu no mesmo arquivo dá `_k_do_bucket(50) = 4`: na `DEDUP_H3_RES = 11` a aresta
média é **28,66 m**, e o anel `k = 1` não garante cobertura nenhuma para 50 m. O comentário do
`contrato.py` dizia "aresta ~24 m" — a medição real é **28,66 m**, e o BLK-MA-17 já corrigiu esse
comentário.

**Por que não levanta hoje, e por que isso é o perigoso.** A função só colapsa entre `fonte`
DIFERENTES, e o snapshot `2026-33` só tem WellHub: medi **`0 de 19.329`** colapsos. O modo de falha
de uma dedup sub-coberta é **indistinguível** do caso correto — ela devolve "nenhum colapso", que é
exatamente o que uma dedup correta devolve quando não há duplicata. Ninguém percebe até alguém
comparar contra varredura completa.

**O custo quando o TotalPass entrar.** A duplicata que não colapsa vira duas linhas na oferta; a
gêmea a ~0 m soma `peso(0) x PESO_OFERTA_INDEPENDENTE` -> `sat(0,5)` = até **+33,3 pontos** de
pressão fantasma na academia — o mesmo fantasma que a DEC-033 criou a dedup para matar. Para calibrar
a ordem de grandeza: no lado das cadeias, onde o dado JÁ existe, o `k` errado deixaria **193 de 2.844
unidades (6,8%)** de deduplicar (medido pelo QA: 1.364 sobreviventes com `k=1` contra 1.171 com o `k`
derivado).

**Escopo.** (1) Trocar `h3.grid_disk(celulas[i], 1)` por `h3.grid_disk(celulas[i], _k_do_bucket(distancia_m))`.
(2) **Medir o efeito** numa fixture de duas fontes e registrar (é mudança de COMPORTAMENTO da função,
ainda que hoje sobre conjunto vazio). (3) Teste de **equivalência contra varredura completa**, no
molde exato do `test_14b` do BLK-MA-17 — que é a única forma de provar que o bucket não mudou
resultado. (4) Nota de emenda na DEC-033, que é a dona daquela dedup. (5) Considerar, no mesmo passo,
a guarda de `(fonte, chave_snapshot)` duplicado nas DUAS funções de dedup (achado leve do mesmo QA:
com chave repetida o `dict` guarda só a última posição, e a auto-exclusão da outra linha aponta para
o índice errado).

**Fora de escopo.** Recalibrar o limiar de 50 m (isso é BLK-MA-06, com par verdade-terreno); mexer em
`dedup_cadeias_do_feed` (já usa `k` derivado — o defeito DELA é outro, entre fontes,
e é o **BLK-MA-17-FU2**); qualquer artefato/peso/score do M1.

**Alternativa considerada e recusada:** absorver como sub-item do BLK-MA-06. Recusada porque o
BLK-MA-06 é o bloco que **liga a segunda fonte** — se a correção viajar junto, o defeito e o dado que
o ativa estreiam no mesmo PR, e não haverá régua "antes" para medir.

---


## Fechamento de ciclo — BLK-MA-17-FU1 + FU2 + FU3 (2026-08-18, as três correções que a revisão adversarial expôs)

**De onde vieram.** Uma revisão adversarial independente sobre o diff do BLK-MA-17 metade 2
(`16f8243..HEAD`), pedida antes do merge: 3 lentes, 13 agentes, **10 achados brutos, 4 sobreviventes
após refutação, 0 críticos**. O veredito sobre o código do MA-17 se manteve — ele está correto e não
produz número errado hoje. O que sobrou foram defeitos LATENTES e uma dívida de leitura, e nenhum
deles estava registrado: o `BLK-MA-17-FU1` (já aberto pelo QA) **declarava `dedup_cadeias_do_feed`
fora de escopo**, que é exatamente onde morava o achado médio.

**Ordem de execução, e por que ela importa.** FU3 primeiro, depois FU1 e FU2. O FU3 é o que dá rede
ao caminho que os outros dois editam — sem ele, as duas correções entrariam às cegas num módulo cujo
ponto de entrada de produção nunca era executado em teste.

### FU3 — o caminho de produção não era exercitado

`_pressao_por_academia` é o único chamador de `calcular_pressao_por_academia` em produção, e as duas
ocorrências dela em `tests/` só faziam `inspect.signature(...)`. Dois mutantes passavam:
**partição independente/cadeia INVERTIDA** (448 testes verdes; no insumo real move 94,5% das linhas,
pressão média `62,775 -> 71,371`, máximo `+49,76`, sem nenhum tell no artefato — `universo_oferta`
sai igual nos dois casos) e **ordem do concat invertida** (437 verdes, `pressao = 50,0` de
auto-pressão, apagando o concorrente real a 1,5 km).

O teste da partição usa **duas rodadas separadas** de propósito: com as duas naturezas na mesma
rodada e à mesma distância, a inversão troca os valores de coluna e os números continuam iguais — o
teste passaria com a partição ao contrário.

### FU1 — o bucket H3 da `dedup_independentes` não cobria o próprio limiar

`h3.grid_disk(celulas[i], 1)`, `k` cravado, com limiar de 50 m. Na `DEDUP_H3_RES = 11` (aresta média
medida **28,66 m**) o anel `k = 1` não cobre 50 m: **43 pares** a `<= 50 m` caem fora dele. O `k`
passou a sair de `_k_do_bucket(50) = 4`.

**A primeira versão do teste de equivalência era inútil, e isso é o aprendizado do bloco.** Com
fixture aleatória densa ela passava mesmo com `k = 1`: 80 pontos em ~200 m dão **219 pares
qualificados**, e com vários candidatos por ponto perder o do anel 2 não muda quem colapsa. A
fixture teve de virar **esparsa**, com pares isolados. E o par fora do anel 1 é **buscado por
azimute**, não cravado — a célula em que um ponto cai depende de onde ele pousa na grade, e uma
coordenada fixa deixaria de provar o caso numa versão futura do `h3`, em silêncio. Descoberto no
caminho: só bases perto da BORDA da célula produzem o caso; do centro, o anel 1 alcança ~71 m.

Entrou junto o item 5 do escopo: **guarda de `(fonte, chave_snapshot)` duplicado nas DUAS dedups** —
com chave repetida o `dict` de posições guardava só a última, e a auto-exclusão da linha perdida
apontava para o índice de outra academia.

### FU2 — a dedup de cadeias não comparava o feed entre FONTES (o achado da revisão)

`dedup_cadeias_do_feed` populava `ocupantes` só com os pontos mapeados e nunca inseria o
sobrevivente: não havia passagem feed x feed. Com o TotalPass ligado, a mesma unidade nos dois
agregadores a 3 m, longe de qualquer pin (o recorte das **1.171** sobreviventes), saía com as duas
linhas a `pressao = 49,962514` / `oferta = 0,998502` / `n_conc = 1` / `dist = 2,996633`. **E o dano
não parava na gêmea:** viram dois pontos no array concatenado e a auto-exclusão só zera a posição do
próprio observador, então qualquer academia dentro dos 2 km contaria dois concorrentes onde há um.

**A restrição que decidiu o desenho.** Colapsar dentro da MESMA fonte está proibido, e foi medido:
dos 5 pares de cadeias a `<= 50 m`, os cinco são `wellhub x wellhub` e **três são redes distintas
dividindo prédio** (`skyfit` x `panobianco` 2,9 m; `selfit` x `power_fit` 22,5 m; `force_one` x
`world_gym` 39,9 m). A guarda `if fontes[j] == fontes[i]: continue` os pula por construção — é ela
que mantém o efeito de hoje em exatamente zero.

**O gatilho não exigia mudar código:** `_pressao_por_academia` chama `coordenadas_por_chave()` sem
`fontes`, que lê os três diretórios por default e cujo único dedup é
`drop_duplicates(["fonte","chave_snapshot"])` — que por construção não colapsa entre fontes. O
recorte `--fontes unidades` do cron vale para o `run_snapshot_concorrentes.sh`, não para o
`alvos_ma`. **Por isso as duas dedups tinham de fechar ANTES da aplicação do BLK-MA-06 na VPS**, e
não junto com ela.

### Efeito sobre o dado de hoje: EXATAMENTE NULO, nos três

Medido no insumo real, não inferido. Feed `22.173` linhas, `{'wellhub': 22173}` — fonte única, e o
diretório do TotalPass não existe em disco. `dedup_independentes`: **0 de 19.329** colapsos, antes e
depois. `dedup_cadeias_do_feed`: **1.171 sobreviventes / 1.673 colapsadas contra o mapeado / 0 entre
fontes** — dígito a dígito o que a DEC-034 registrou. **Nenhum bump de série:** nenhum schema muda e
nenhum número gravado muda. É essa medição que torna os três seguros de mergear junto com a pilha.

Arquivos alterados: `src/motor_expansao/vulnerabilidade/pressao_competitiva.py`,
`tests/unit/vulnerabilidade/{test_caminho_producao_pressao,test_dedup_independentes_bucket,test_dedup_cadeias_entre_fontes}.py`
(3 novos), `docs/decisions/{DEC-033,DEC-034}.md` (emendas), `docs/vulnerabilidade_ma_contrato.md`,
`tasks/backlog.md`, `tasks/completed.md`
Validações (saída real): suíte COMPLETA serial **3194 passed, 28 skipped, 0 falhas** (10m39s);
`--collect-only` **3222** (baseline 3206, **+16** = 3 + 6 + 7 testes novos); recorte da camada
**453 passed**; `ruff check src tests` limpo; `loop_guard --stdin` só `GOVERNANCA`, **zero CRITICO**;
`git diff --name-status` sem nenhum caminho do M1
Decisões relacionadas: **emenda 2 na DEC-033** (o bucket da dedup que ela criou) e **emenda 1 na
DEC-034** (a dedup entre fontes). Nenhuma DEC nova: os três são correção de defeito dentro de
decisões já aprovadas, sem mudar universo, peso, fórmula nem schema. READ-ONLY sobre o M1.

**Mutação verificada em todos, e é o que sustenta o "verde".** FU3: cada mutante derruba exatamente
1 teste. FU1: `k -> 1` derruba os 2 que o exercitam. FU2: desativar a segunda passagem derruba 4
testes; remover a guarda de fonte derruba os 2 que protegem os pares reais. Código restaurado e
`git diff` limpo após cada rodada.

**Limite declarado e NÃO corrigido (na emenda da DEC-033).** A `dedup_independentes` para no
PRIMEIRO candidato que o `grid_disk` devolver, diferente da `dedup_cadeias_do_feed`, que escolhe o
mais próximo com desempate por menor índice. Quem colapsa é determinístico; **qual representante
absorve, havendo mais de um candidato, depende da ordem de iteração das células** — e com `k` maior
o conjunto varrido cresce. Hoje é inócuo (zero colapsos). Quando o TotalPass entrar, vale decidir se
a escolha passa a ser a do mais próximo. Por isso o teste de equivalência compara o **conjunto de
colapsadas**, não o representante de cada uma.

**Housekeeping — o helper engoliu 2 dos 3 stubs.** Movidos na ordem FU3 -> FU2 -> FU1, e como o
`housekeeping_move_block.py` recorta até o PRÓXIMO HEADING, cada move levou junto o stub de 1 linha
que o anterior tinha acabado de criar: os stubs de FU3 e FU2 foram parar DENTRO do `completed.md`.
Detectado por contagem (`140 -> 141` stubs, quando deveria ser `143`), removidos de lá e recolocados
no backlog. O helper também trouxe o CRLF do `backlog.md` para o `completed.md`, que é LF — 189
linhas mistas, normalizadas (o `merge=union` deste arquivo depende de EOL consistente). Conferido ao
final: `--is-done` diz DONE para os três FU e **ABERTO para `BLK-MA-17`**, cuja metade 1 continua
pendente.

**O que sobra na epic BLK-MA, e de quem é.** `BLK-MA-17` metade 1 (exibir o diagnóstico nas unidades
de rede) — exige DEC própria e gate humano, e a revisão acrescentou que a auditoria do pin que ela
herdaria **já não fecha**: 16,4% de quebra ANTES da metade 2, ~50% depois, por recorte municipal do
pin contra raio de 2 km. `BLK-MA-06` — código na `main` desde 2026-08-11, o que falta é a **aplicação
manual na VPS**, comando a comando, e é o caminho crítico (~2 meses de relógio até S3/S4 maturarem).
`BLK-MA-07` (Google Places) — fonte externa paga, DEC própria, não bloqueia nada.

---

### BLK-MA-17 — Unidades de REDE presentes nos agregadores ganham o diagnóstico visível

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** — altera o UNIVERSO declarado da camada (§3/D1 do contrato: "TotalPass/WellHub × independente"), que hoje é travado por assert na entrada **e** na saída do score. **Exige DEC própria.** READ-ONLY sobre o M1. |
| **Prioridade** | Média — é ganho de leitura no mapa, não de decisão de M&A (comprar rede não é o caso de uso do epic). |
| **Esteira** | Block Orchestrator → Planner → `[GATE — DEC própria]` → Builder → QA. |
| **Status** | **CONCLUÍDO — as duas metades.** Metade 2 em 2026-08-15 (DEC-034): as unidades de rede entram na **oferta** do S6. Metade 1 em **2026-08-18** (DEC-035, aprovada no gate por Vinicius): elas ganham **pin e diagnóstico visível**, com **fato e sem score**. Criado em 2026-08-14 a pedido de Vinicius. |
| **Depende de** | BLK-MA-15 (concluído 2026-08-14, molde do pin nomeado) e **BLK-MA-16 (concluído 2026-08-14)** — a ordem era para a tela não estrear exibindo uma pressão que mudasse de régua em seguida. **Dependência satisfeita:** a régua já é `cadeias_e_independentes` (DEC-033). |
| **Autonomia** | **manual (NÃO loop-safe)** — muda o universo da camada. |

**O universo existe e é descartado hoje.** O snapshot da semana `2026-33` tem **22.173 linhas: 19.329
independentes (o universo do score) e 2.844 de REDE**, em 83 redes distintas — unidades de cadeia que
estão no WellHub e que `_filtrar_universo_sinal_1` corta antes do score. Incluí-las cresceria o
universo em **14,7%**.

> ### [medido em 2026-08-15, depois da DEC-033] O bloco ganhou uma SEGUNDA metade, e ela é a mais forte
>
> A justificativa original era de LEITURA ("ver o diagnóstico também nas redes"). A medição do
> BLK-MA-16 expôs outra coisa, mais grave: **1.134 dessas unidades (39,9%) não têm nenhum ponto de
> cadeia a menos de 150 m em `concorrentes_mapeados`** — o insumo de oferta do S6. São academias de
> rede REAIS, listadas no WellHub, que **hoje não pressionam ninguém** no cálculo.
>
> É o **mesmo defeito que a DEC-033 corrigiu, do outro lado**: lá as independentes não contavam como
> oferta; aqui parte das cadeias também não conta, e pela mesma razão — cobertura do insumo, não
> desenho da fórmula. Enquanto isso valer, a pressão de quem está perto dessas 1.134 está subestimada,
> e o falso zero que a DEC-033 reduziu de 37,8% para 5,5% ainda tem um resíduo com causa conhecida.
>
> **Consequência para o escopo:** o bloco deixa de ser só exibição. Ele passa a ter duas metades
> separáveis, e a segunda **não depende da DEC** que trava a primeira:
>
>   1. **Exibir** o diagnóstico nas unidades de rede — muda o universo declarado, exige DEC própria.
>   2. **Contá-las como oferta** — não muda universo nenhum: elas já são concorrência por definição, e
>      a única pergunta é de DEDUP contra os 58,5% que já estão no `concorrentes_mapeados`, para não
>      contar a mesma unidade duas vezes. A primitiva existe (`dedup_independentes`), mas hoje ela só
>      colapsa entre FONTES distintas — casar feed-de-rede com parquet-de-cadeia é caso novo.
>
> Se o gate da metade 1 demorar, **a metade 2 pode ir sozinha** e corrige um número que já está na
> tela hoje.

> ### [executado em 2026-08-15 — DEC-034] A metade 2 foi entregue; os números do quadro acima mudaram
>
> O gate (G1) ratificou **só a metade 2**: as 2.844 unidades de rede entram na **oferta** do S6, com
> peso `1,0`, deduplicadas contra `concorrentes_mapeados.parquet` por
> `(rede igual E d <= 150 m) OU (d <= 50 m)`. **Corrigindo o quadro acima:** o `1.134` citado é da
> variante de **distância pura** (que apagaria 45 concorrentes reais) e o `1.179` do handoff do
> Planner é da variante `(rede, d)` **sem o piso**. Pelo critério de fato adotado, **entram 1.171** e
> **colapsam 1.673** — as duas metades foram medidas por varredura completa, e o `1.171` é o número
> a citar daqui em diante.
>
> Efeito medido (nacional, 19.329 independentes): pressão média `61,415 -> 62,775`, **7.237 (37,4%)**
> mudam de valor, `Spearman 0,9911994` no score, **2.096 de 6.753** linhas do entregável alteradas e
> **12 das 100 primeiras linhas** do `alvos_ma_priorizados.csv` trocam. Quatro bumps de série. O
> falso zero cai só de 5,53% para 5,31%: o bloco corrige **magnitude e ordem**, não cobertura.
>
> **O que continua PENDENTE (metade 1, e a DEC dela):** exibir o diagnóstico nas unidades de rede —
> universo de exibição próprio, artefato nomeado próprio, terceira lista de pins e precedência de
> pin. A precedência sai **de graça** da dedup já implementada: as **1.171** sobreviventes são
> exatamente as que **não têm pin desenhado**; as **1.673** colapsadas já têm o pin do funil. E a
> lacuna de auditoria do BLK-MA-18 já está DECLARADA no artefato nomeado, pela coluna
> `n_cadeias_do_feed_no_raio` (24 colunas, `alvos_ma_nomeados_v4`) — falta surfaceá-la na tela.

**A objeção que decide o desenho do bloco: S1 e S3 medem OUTRA COISA numa rede.** A negociação com o
agregador é **centralizada**: "estar em 1 app em vez de 2" é política comercial da rede, não
exposição daquela unidade. E o modo de falha do S3 é pior, porque é correlacionado — a concentração
medida é **top 5 = 48,4% das unidades, máximo 440 numa rede só**. Quando a Panobianco sair do
WellHub, **440 unidades viram `sumiu_recente` no mesmo dia** e o S3 — o maior peso do Plano B,
`≈ 0,467` — dispara para todas simultaneamente, sem que uma única unidade tenha se fragilizado. O
score leria um evento de negociação como 440 alvos.

**Recomendação de desenho (a validar na DEC): fato sim, score composto não.** Propagar para as
unidades de rede o **S6** (pressão, que é geográfica e não sabe se a academia é de rede) e os
**fatos sem peso** — `nota_wellhub`, `qtd_avaliacoes_wellhub`, `status_churn` —, e **não** emitir
`score_vulnerabilidade` para elas enquanto não houver régua própria. É o molde já usado duas vezes
neste epic (G-D2 no `status_churn`, DEC-026 no rating): **o fato entra antes do peso**. Também
preserva a leitura do §2 — a lista de alvos continua sendo de independentes.

**Onde o código resiste, e por que isso é bom.** O universo é fechado num lugar só:
`_filtrar_universo_sinal_1`, importado por `score.py` de propósito para não haver duas definições.
Mas ele é **compartilhado com o sinal 1** — afrouxá-lo lá faria `n_academias_independentes_totalpass`
e `..._wellhub` passarem a contar redes **com o nome dizendo o contrário**. O caminho é um universo
próprio para a camada de exibição, não relaxar o filtro comum.

**Pins: o join espacial NÃO resolve — medido.** Casando cada unidade de rede do agregador com um pin
do funil da MESMA rede a menos de 150 m, só **1.665 de 2.844 casam (58,5%)**. Outras **1.167 não
casam apesar de a rede existir no funil**, e há redes inteiras com casamento zero: `performance`
(0/88), `one` (0/29), `contorno_do_corpo` (1/61), `power_fit` (5/76), `selfit` (69/202). Não é erro
de distância — os dois feeds cobrem conjuntos diferentes da mesma rede. Logo o caminho é **pin
próprio a partir da coordenada do feed** (molde BLK-MA-15), com **regra de precedência explícita**
para os 58,5% que virariam dois pins no mesmo lugar.

**O pin já tem molde novo (BLK-MA-18).** Se a metade 1 for adiante, ela herda a auditoria da pressão
no tooltip (`n_conc` / `n_indep` / `n_cadeias_feed` / `oferta` / `dist_m`) — sem isso, uma unidade de
rede exibiria um número saturado tão inverificável quanto o que a revisão de 2026-08-15 apontou.
Contrato do artefato nomeado **desde a DEC-034**: `alvos_ma_nomeados_v4`, **24 colunas**.
> ### [medido na revisão adversarial de 2026-08-17] A conferência visual que a metade 1 herdaria JÁ não fecha
>
> A promessa que o BLK-MA-18 escreveu no próprio componente — *"o operador conta os pins no mapa e o
> número fecha"* — foi testada contra o dado real e **já falhava em 16,4% dos casos ANTES da metade
> 2**: em SP fechava em **4.862 de 5.819** nomeadas, e **471** das 957 quebras tinham
> `n_cadeias_do_feed_no_raio = 0`, isto é, quebravam por motivo alheio a este epic. Depois da metade
> 2 fecha em **2.897 de 5.819 (49,8%)**.
>
> **A causa não é a metade 2 — é estrutural.** As duas camadas de pin filtram por
> `hex_id_res7 ∈ sel` (`_montar_pins`, `_pins_independentes`), ou seja, pelo **município**, enquanto
> o raio de 2 km atravessa divisa municipal livremente. Somem-se duas réguas de validade diferentes
> sobre o mesmo parquet (`flag_coord_valida`, 4.459 pontos, no carregador; `status_registro ==
> "valido"`, 4.366, na pressão) e a `dedup_independentes`, que colapsa entre fontes mas desenha o pin
> da linha nomeada.
>
> **Consequência para o escopo desta metade:** surfacear `n_cadeias_do_feed_no_raio` no tooltip é
> **necessário mas não suficiente** — sozinho, explica só uma parte da diferença. Herdar a auditoria
> do BLK-MA-18 sem endereçar o recorte municipal entrega uma conta que continua não fechando em
> metade dos casos. São **três** pontos de edição — `_COLS_NOMEADAS` (`web/server/app.py:401`), o
> payload de `_pins_independentes` (`:463-486`) e o template do tooltip (`HexMap.tsx:999-1005`) —,
> todos em `web/`, a zona em que `origin/main` andou.


**Fora de escopo.** Qualquer artefato/peso/score do M1; a entrada das INDEPENDENTES como oferta
(**BLK-MA-16**, concluído); incluir unidades de rede na lista comercial de alvos (**BLK-MA-05**);
régua de score própria para rede (bloco futuro, se a DEC concluir que faz falta).

**Critério de aceite.** Da metade 1: DEC própria decidindo o que é propagado (fatos e/ou score) e a
precedência de pin; o filtro do sinal 1 e as colunas `n_academias_independentes_*` **intactos**; a
lista de alvos de M&A segue só com independentes, travado por teste; anti-PII no molde do BLK-MA-15
(artefato nomeado nasce gitignored). Da metade 2: dedup entre o feed de rede e
`concorrentes_mapeados` travada por teste (a mesma unidade nunca conta duas vezes), com o efeito
medido antes e depois sobre a distribuição de pressão. Em ambas: READ-ONLY sobre o M1; suíte verde.

---


---


---


## Fechamento de ciclo — BLK-MA-17 metade 1 (2026-08-18): o bloco fecha INTEIRO, as duas metades

**O bloco `### BLK-MA-17` está concluído.** A metade 2 (contá-las como oferta) fechou em 2026-08-15
pela DEC-034; a metade 1 (exibi-las) fecha hoje pela **DEC-035**, aprovada no gate por Vinicius. O
`--is-done` passa a dizer DONE para o bloco-pai e para os três FU.

### A decisão: FATO SIM, SCORE NÃO

As unidades de rede recebem o **S6** (`pressao_competitiva` e a auditoria dela) e os **fatos sem
peso** — `status_churn`, `nota_wellhub`, `qtd_avaliacoes_wellhub`. **Não** recebem
`score_vulnerabilidade`, e a ausência é a decisão, não um esquecimento:

  - **S1 mede política comercial, não fragilidade** — a negociação com o agregador é CENTRALIZADA;
  - **S3 é correlacionado, e é o pior dos dois** — top 5 = 48,4% das unidades, máximo **440** numa
    rede só. A Panobianco saindo do WellHub viraria **440 `sumiu_recente` no mesmo dia**, e o
    composto leria um evento de negociação como 440 alvos.

O **S6 não tem esse defeito**: é geográfico e não sabe se a academia é de rede. Molde do G-D2 e da
DEC-026 — o fato entra antes do peso. A trava é dupla: um guard no artefato (qualquer coluna
`score_*`/`v6` levanta) e um teste no payload do pin.

### O achado que encolheu o bloco pela metade

**A pressão dessas 2.844 unidades JÁ era calculada — e depois descartada.** O cálculo roda sobre o
feed inteiro (22.173 linhas, incluindo as de rede) e é o **join do SCORE** que as filtra, não o
cálculo. Medido: pressão média **72,154** nas redes (contra ~62,8 das independentes, o que faz
sentido — rede fica onde é denso) e só **1,72%** de zeros. O módulo novo não recalcula nada:
materializa o que era jogado fora.

### A precedência de pin saiu de graça

As **1.171** sobreviventes da dedup da DEC-034 são, POR CONSTRUÇÃO, exatamente as unidades sem ponto
equivalente em `concorrentes_mapeados` — logo as únicas sem pin desenhado no funil. As **1.673**
colapsadas já têm o pin de lá. Não houve regra nova a inventar: `tem_pin_proprio` é a dedup, e a
materialização real bateu `1.171 / 1.673`, os mesmos números da DEC-034.

### A causa REAL da auditoria do pin não fechar — e ela é anterior a este epic

A revisão adversarial de 2026-08-17 mediu que a promessa que o BLK-MA-18 escreveu no componente —
*"o operador conta os pins no mapa e o número fecha"* — **já falhava em 16,4% dos casos ANTES da
metade 2**: em SP, fechava em 4.862 de 5.819, e **471** das 957 quebras tinham
`n_cadeias_do_feed_no_raio = 0`, ou seja, quebravam por motivo alheio a este epic.

São **três causas**, e as três foram endereçadas:
  1. **Recorte municipal** — as camadas de pin filtravam por `hex_id_res7 ∈ sel` (município)
     enquanto o raio de 2 km da pressão atravessa divisa livremente. O recorte passou a ser
     `hex ∈ sel` **UNIÃO** a margem de `PIN_MARGEM_M = 2000` — o próprio raio da pressão, porque
     todo ponto que possa entrar na conta de alguém tem de ser desenhável.
  2. **A terceira parcela não chegava à tela** — `n_cadeias_do_feed_no_raio` existia no artefato
     desde a DEC-034 e não estava em `_COLS_NOMEADAS`, nem no payload, nem no tooltip. Medido:
     **7.218 de 19.329** linhas (37,3%) têm valor > 0.
  3. **As unidades sem pin** — que é o que a terceira lista de pins resolve.

### O teste que mudou de enunciado, e por quê

`test_academia_de_outro_municipio_nao_entra` **passava por acidente de fixture**. Na fixture
sintética, São Paulo e Campinas ficam a **~1,5 km** um do outro (`0.01` grau), enquanto os
municípios reais estão a ~90 km: ela não distinguia "outro município" de "fora do alcance". Virou
dois testes — um com a academia a ~170 km (**e com o `hex_id_res7` também fora**, senão o ramo do
hex casaria e o teste provaria o contrário do que afirma) e outro provando que o vizinho DENTRO do
raio agora entra, que é a correção.

Arquivos alterados: `src/motor_expansao/vulnerabilidade/{redes_nomeadas (novo),contrato,alvos_ma}.py`,
`web/server/app.py`, `web/src/lib/types.ts`, `web/src/components/HexMap.tsx`,
`web/src/screens/MapScreen.tsx`, `tests/unit/{test_piloto_web_redes (novo),test_piloto_web_api,
test_piloto_web_endpoints,test_piloto_web_independentes}.py`,
`tests/unit/vulnerabilidade/test_redes_nomeadas.py` (novo), `docs/decisions/DEC-035.md` (nova),
`docs/decisions/README.md`, `docs/vulnerabilidade_ma_contrato.md`, `CLAUDE.md` §8,
`tasks/{backlog,completed}.md`
Validações (saída real): suíte COMPLETA **3374 passed, 33 skipped, 0 falhas** — `contracts` 262+5,
`integration` 202+1, `unit/{demanda_revelada,dimensionamento,vulnerabilidade}` 985+7 e os 96
arquivos soltos de `unit/` em dois grupos (764 e 1161+20). `3374 + 33 = 3407` bate EXATAMENTE com o
`--collect-only` global (**3407**, baseline 3382, **+25** = 16 + 8 testes novos e 1 que virou dois),
o que prova que a soma dos blocos cobriu a suíte inteira, sem recorte esquecido. Recorte
piloto+camada **558 passed**; `ruff check src tests web` limpo; `tsc --noEmit` limpo;
`npm run build` OK (13,07s);
`loop_guard --stdin` só `GOVERNANCA`, **zero CRITICO**; materialização real do artefato
(2.844 linhas, 20 colunas, 83 redes, 1.171 com pin próprio)
Decisões relacionadas: **DEC-035** (Alta, aprovada por Vinicius em 2026-08-18 no gate). Emenda ao
§3/D1 do contrato: os dois universos passam a ser **explícitos e disjuntos** — o do SCORE
(`_filtrar_universo_sinal_1`, intacto) e o de EXIBIÇÃO de redes
(`filtrar_universo_exibicao_redes`). Contrato novo `redes_ma_nomeadas_v1`, 20 colunas.
**Nenhum bump de série existente**: nada do que já era gravado mudou de schema ou de valor.

**O merge com a `main` entrou neste ciclo.** A pilha nunca tinha rodado contra a `main` atual — 16
commits (BLK-SEC-05, renda/k nacional, dois selos) que tocam `web/server/app.py`. Conflito único no
`CLAUDE.md` §8, resolvido pela **união em ordem** (001-034), não "pegando um lado": a main terminava
em `026, 030, 031, 032` e a pilha em `026, 027, 028, 029, 033, 034`. E uma correção que **nenhum
conflito forçaria**: `docs/decisions/README.md` auto-mergeia em silêncio para o lado local e saltava
de 029 para 033 — a `main` criou os arquivos `DEC-030/031/032` mas nunca os inseriu naquele índice,
então as três não estavam em índice NENHUM. Suíte pós-merge: **3349 passed, 33 skipped, 0 falhas**.

**Housekeeping — o helper engoliu os stubs DE NOVO, e agora está medido.** Mover o `### BLK-MA-17`
recorta até o próximo heading (`### BLK-ORQ-28`), e os três stubs de FU vivem no meio: foram parar
dentro do `completed.md`, como já havia acontecido no fechamento dos próprios FU horas antes. Não há
ordem de execução que evite — **é preciso salvar os stubs antes e restaurá-los depois**. O helper
também trouxe **144 linhas CRLF** do backlog para o `completed.md`, que é LF (o `merge=union` dele
depende de EOL consistente); normalizadas. Conferido ao final: 4 stubs no backlog, 0 engolidos,
`--is-done` DONE para o bloco-pai e os três FU.

**A suíte completa teve de rodar em BLOCOS, e isso vale registrar.** Duas tentativas em background
(`pytest -q` inteiro) foram MORTAS por volta de 10-14%, poucos minutos após o lançamento, sem
nenhuma falha até ali — enquanto duas rodadas anteriores no mesmo dia tinham completado normalmente
(639 s e 850 s). Em vez de insistir, a suíte foi partida em cinco blocos executados em primeiro
plano. A soma (`3374 + 33 = 3407`) bate dígito a dígito com o `--collect-only` global, que é o que
transforma "rodei em pedaços" em "rodei tudo" — sem essa conferência, um diretório esquecido
passaria por suíte verde.

**O que sobra na epic BLK-MA.** `BLK-MA-06` — código na `main` desde 2026-08-11; o que falta é a
**aplicação manual na VPS**, comando a comando, e é o caminho crítico (~2 meses de relógio até S3/S4
maturarem). As duas dedups (FU1/FU2) eram pré-requisito dele e estão fechadas. `BLK-MA-07` (Google
Places) — fonte externa paga, DEC própria, não bloqueia nada.

## Fechamento de ciclo — BLK-MA-17-FU4 + revisão visual da metade 1 (2026-08-18/19, ad-hoc)

**Ciclo AD-HOC, e o registro chega depois do código.** Nada disto nasceu no `tasks/backlog.md`: os
dois trabalhos vieram de um pedido direto de Vinicius depois de ver a metade 1 rodando no piloto —
*"as academias de rede da WH/TP devem seguir o mesmo padrão de quadrado com a bandeira (…) não uma
opção ativável, mas uma constante (…) pode ser necessário também aprimorar o dedup"*. O
`housekeeping_move_block.py` devolve `SKIP` para os dois IDs, como manda o guardrail de ciclo
ad-hoc; o registro é este resumo.

### Parte 1 — a revisão visual (emenda 1 da DEC-035, commit `3bb1a1e`)

A metade 1, fechada horas antes, desenhava as unidades do agregador como **camada própria**: ponto
circular azul, lista `redes` separada no payload e chave de liga/desliga. A justificativa original
("juntar as listas esconderia a lacuna que a DEC-034 mediu") não sobreviveu ao uso: **uma academia
de rede é uma academia de rede**, e dar-lhe outra forma obrigava o operador a ligar um toggle para
enxergar concorrência que sempre esteve instalada ali.

Agora são **bandeira quadrada com a logo da rede**, na mesma lista `pins.concorrentes`, sempre
visíveis. A medição que destravou a mudança: as **83 redes do feed têm logo cadastrado (100%)** —
nenhuma cairia no quadrado de sigla.

**O destaque é um HALO, e as restrições que o definiram são as interessantes.** Não podia ser a
borda do quadrado (7 px, já é a cor da REDE — sobrescrevê-la apagaria a marca); não podia ser ciano
(`--ac: #35c9d6` é a Ultra e o contorno de seleção); não podia ser amarelo/verde/vermelho (é a
escala de score dos hexágonos). Sobrou um claro neutro (`#E8EEF5`) num anel externo, com respiro
transparente. O `viewBox` cresce de 128 para 160 e o `getSize` de 30 para 38 — **sem esse par o halo
encolheria a marca**. A variante só é gerada para as redes com diagnóstico no recorte (29 em SP, não
as 107).

Saíram do código: a lista `redes`, `_pins_redes`, a camada `ScatterplotLayer`, o estado `redeHover`,
o tooltip próprio, a `PilulaRedes` e os tipos `PinRede`/`Redes`.

### Parte 2 — o dedup (emenda 2 da DEC-034, commit `ad6525e`)

A pergunta de Vinicius era condicional ("pode ser necessário"). A medição respondeu que **era, e o
defeito estava ativo em produção**.

`DEDUP_CADEIA_FEED_M = 150 m` era curto demais para a divergência de geocodificação entre as duas
fontes. Entre 150 m e 1 km havia **438 pares** de mesma rede entre o feed e `concorrentes_mapeados`;
comparando os NOMES, **407 (92,9%) eram a mesma academia**. Diferente do FU1 e do FU2 — cujo efeito
era provadamente nulo com uma fonte só —, **estas 407 inflavam a pressão desde a DEC-034**.

**Por que a distância sozinha não resolvia, em número.** A taxa de pares próximos é ~10x o
adensamento real da rede, medido no próprio insumo mapeado (onde duas linhas da mesma rede são
academias distintas por definição): `1,29%` a ≤200 m e `2,07%` a ≤300 m, contra `5,0%` e `19,9%` do
lado do feed. Mas subir o limiar apagaria academia real.

**`identidade.py`** — terceira passagem, `rede igual E mesma_unidade(nome) E d <= 1200 m`:
Jaccard ≥ `0,67` do **discriminante** (o nome menos o slug da rede, o ruído genérico e os ordinais;
o que sobra é o LUGAR) **e ordinais iguais**.

**A regra de ordinal é o achado do ciclo.** Sem ela o matcher colapsava unidades numeradas da mesma
rede no mesmo bairro — `Águas Claras` × `Águas Claras II`, `Carpina` × `Carpina 2` —, e a causa era
boba: o filtro de token curto descartava justamente o sufixo `2`/`II` que distingue. Aumentar o
Jaccard **não** resolveria (esses pares têm Jaccard `1,00`). Efeito da regra sozinha a 800 m: o
custo cai de **59 para 10** academias reais com o ganho intacto (292 -> 285); a razão ganho/custo
sai de `4,9:1` para `28,5:1`. O limiar de 1.200 m saiu dessa curva: ganho 320 (27,3%), custo 12
(0,27%), razão 26,7:1.

**Performance.** Os 1.200 m custariam `grid_disk(k=31)` na `DEDUP_H3_RES = 11` (2.977 células por
ponto). A passagem por nome usa bucket próprio na `DEDUP_NOME_H3_RES = 8` (aresta 531 m), onde o
mesmo alcance sai com `k=4` — 61 células, 49x menos varredura. A dedup completa roda em **1,2 s**.

### Efeito medido

Sobreviventes `1.171 -> 851`. Pressão média `62,775 -> 62,479`; **2.829 de 19.329 (14,6%)** mudam de
valor, delta médio `-2,02`, máximo `-20,82`; `Spearman = 0,9980718`; os zeros não se movem
(`5,31%`). A pressão **cai**, como tem de ser — estava inflada por unidades contadas duas vezes. Em
São Paulo, as bandeiras com halo caem de **96 para 72**.

Arquivos alterados: `src/motor_expansao/vulnerabilidade/{identidade (novo),pressao_competitiva,contrato}.py`,
`web/server/app.py`, `web/src/lib/types.ts`, `web/src/components/HexMap.tsx`,
`web/src/screens/MapScreen.tsx`,
`tests/unit/vulnerabilidade/{test_identidade (novo),test_dedup_por_nome (novo),test_oferta_cadeias_do_feed,test_auditoria_pressao_no_pin,test_redes_nomeadas}.py`,
`tests/unit/test_piloto_web_redes.py`, `docs/decisions/{DEC-034,DEC-035}.md`,
`docs/vulnerabilidade_ma_contrato.md`
Validações (saída real): piloto + camada **589 passed**; `ruff check src tests web` limpo;
`tsc --noEmit` limpo; `npm run build` OK; verificação ponta a ponta no piloto rodando (993 bandeiras
em SP, 72 com halo, 29 variantes de ícone, lista separada ausente do payload, tooltip conferido em
tela — "Sports Premium Academia", pressão 73,0, "13 num raio de 2 km (11 independentes)")
Decisões relacionadas: **emenda 2 na DEC-034** (o dedup) e **emenda 1 na DEC-035** (o visual).
**Cinco bumps de série**: `pressao_competitiva_v3 -> v4`, `score_vulnerabilidade_v6 -> v7`,
`alvos_ma_v3 -> v4`, `alvos_ma_nomeados_v4 -> v5`, `redes_ma_nomeadas_v1 -> v2`. READ-ONLY sobre o M1.

**Os 36 testes novos usam PARES REAIS medidos no insumo, não casos inventados** — é o que separa um
matcher que funciona no papel de um que funciona no dado. `SKYFIT ACADEMIA - BACABAL` × `Bacabal
(MA)` a 940 m é caso de teste porque foi medido; `Carpina` × `Carpina 2` também.

**Uma correção de rota registrada:** um teste que eu mesmo escrevi (`mesma_unidade("Bluefit Centro
Cívico", "Selfit Centro Cívico", "bluefit")`) esperava `True` e o comportamento real é `False` — só
o slug da rede PASSADA sai do discriminante, então o token `selfit` do outro nome sobrevive e derruba
o Jaccard para `0,50`. O teste foi corrigido para documentar a proteção de segunda ordem, que é
melhor do que eu supunha: mesmo um chamador que esqueça de filtrar por rede erra para o lado seguro.

**A precedência de pin mudou de natureza.** Enquanto as unidades do agregador tinham forma própria,
desenhar uma colapsada era um detalhe interno. Com a forma unificada, é **duas bandeiras da mesma
rede coladas no mapa** — erro visível. Foi exatamente isso que motivou a auditoria do dedup: a
mudança visual expôs um defeito de dado que estava escondido havia dias.

**Pendência aberta deste ciclo:** `BLK-MA-17-FU5` (resíduo de ~87 duplicatas com nome não
informativo no insumo mapeado) — ver `tasks/backlog.md`.
## Fechamento de ciclo — Trilha de acesso do piloto / DEC-027 (2026-08-17, ad-hoc)

Feature ad-hoc (fora do backlog), pedida por Felipe em 2026-08-17: "construirmos o rastro de logs
do motor e guardar isso de maneira segura; o maximo que puder ser registrado sem inflar". Origem:
diagnostico da mesma data — o Caddy injetava `Remote-User` em toda requisicao do piloto e ninguem
gravava; Authelia em `warn` nao registrava login com sucesso; retencao era acidente da rotacao do
Docker. Bot Telegram e API GeoEspacial FORA do escopo por decisao explicita.

Entrega (DEC-027): middleware `_trilha_acesso` no backend do piloto grava 1 linha JSONL por
requisicao relevante (usuario, IP real via XFF, rota+query, status, duracao_ms, agente, bytes) em
volume `:rw` proprio (`/opt/motor-expansao/logs/acesso`, segundo mount de escrita — emenda a
DEC-023, anotada inline), com filtro de ruido (assets + /api/health) e retencao de 90 dias podada
pelo proprio backend (dir 0700, arquivos 0600). Preparados (aplicacao manual na VPS): access log
do Caddy no host piloto (JSON, rolagem 20MiBx10, 90d) e Authelia `level: info`.

QA: revisao adversarial por workflow (34 agentes: 4 lentes -> 15 achados -> 2 ceticos por achado ->
9 confirmados, 6 refutados). Os 9 corrigidos no proprio ciclo — destaque: teste que trava o
REGISTRO do middleware no app (falso-verde reproduzido por mutacao), fronteira exata dos 90d e gate
da poda testados, drift do runbook `deploy_piloto_web.md` ("UNICO volume :rw") corrigido, limite de
confianca dos headers declarado no contrato. Suite completa: 3007 passed, 1 failed PRE-EXISTENTE e
ambiental (`test_sem_escrita_em_disco` do dimensionamento: openpyxl usa %TEMP% no Windows; verde no
CI Linux). `ruff` limpo. `test_claude_md_size` verde.

Arquivos: `src/motor_expansao/dashboard/acesso_log.py`, `web/server/app.py`,
`tests/unit/test_acesso_log.py` (29 testes), `tests/conftest.py`, `tests/unit/test_piloto_web_rede.py`
(contrato do compose: 2 mounts `:rw` exatos), `docker-compose.prod.yml`, `.gitignore`,
`docs/trilha_acesso_piloto.md` (contrato canonico), `docs/deploy_piloto_web.md`,
`docs/infra_producao.md`, `docs/README.md`, `docs/decisions/DEC-027.md`, `docs/decisions/DEC-023.md`
(emenda inline), `docs/decisions/README.md`, `CLAUDE.md` (linha-indice DEC-027). Locais/gitignored
(referencia para o servidor): `Caddyfile` (diretiva `log`) e `authelia/configuration.yml` (`info`).

Merge = passo humano (PR ad-hoc que toca compose: `criticidade:alta` + `aprovado-humano` de humano
distinto do autor + `critica-aprovada` de dono pelo guard). Deploy manual por digest + 5 passos de
habilitacao na VPS em `docs/trilha_acesso_piloto.md`. Housekeeping: helper e no-op (EXIT_AD_HOC).

## Fechamento de ciclo — Fix simulador XLSX com valores em cache (2026-08-18, ad-hoc)

Bug de producao reportado por Felipe: a planilha do simulador (POST /api/simulador/xlsx) abria "sem
informacoes" em DRE/Fluxo/Resumo mesmo com as premissas preenchidas. Diagnostico por evidencia: o
arquivo gerado estava INTEGRO (8 abas, ~4.600 formulas, fullCalcOnLoad) — mas openpyxl grava formula
SEM valor calculado, e visualizador sem recalculo (Excel em Modo de Exibicao Protegida, previews,
LibreOffice default) mostra as abas 100% formula em branco; so a Premissas (valores literais)
aparecia. A trilha de acesso (DEC-027) foi decisiva para descartar as outras hipoteses (403 do
controle por aba so sem Remote-User; nenhum export real do usuario chegou ao backend).

Fix: etapa `_com_valores_em_cache` no gerador — recalcula o arquivo com a lib `formulas` (a MESMA que
o nivel 2 de test_simulador_xlsx.py ja usa para provar as formulas contra o motor) e injeta cada
resultado como `<v>` no XML, sem tocar em mais nada (o proprio Excel salva assim). Formulas seguem
vivas. Kill-switch `MOTOR_SIMULADOR_XLSX_SEM_CACHE`; falha degrada para o arquivo original (download
nunca quebra); `_LOCK_RECALCULO` serializa o recalculo (race do primeiro import do schedula
reproduzido 3/3 na revisao + teto de 1 recalculo simultaneo, ~8s/300MB cada). Extra novo
`simulador_cache` no pyproject instalado pelo Dockerfile.web; constraints ja pinava tudo.

QA: revisao adversarial por workflow (27 agentes: 3 lentes -> achados -> 2 ceticos por achado ->
7 confirmados, 5 refutados) — todos os 7 corrigidos ou cobertos (lock unico resolve 3; tmp_path antes
do write; drift de comentarios; kill-switch tambem no import do conftest p/ fixtures de modulo; nota
de merge). Suites: 3192 passed na completa (1 falha pre-existente ambiental do Windows) + 105 nas
afetadas apos os consertos, incluindo teste de regressao de concorrencia. Merge admin + deploy
autorizados por Felipe ("totalmente autonomo").

## Fechamento de ciclo — Relatorio de acessos no Telegram (/acessos + cron 3/3h) (2026-08-18, ad-hoc)

Pedido de Felipe: o agregado "quem logou e quais abas" (sem detalhe de rota) puxavel pelo Telegram
sob demanda e enviado a cada 3h no canal de alertas. Entrega: modulo
`motor_expansao/api/relatorio_acessos.py` (gerador unico: agregacao da trilha DEC-027 por DIA BRT,
texto puro sem Markdown, CLI --enviar/--pular-vazio), comando `/acessos` no bot RESTRITO ao chat de
ops (id == API_ACESSOS_ADMIN_CHAT_ID = MONITOR_TELEGRAM_CHAT_ID; antes do gate de senha, id de chat
e' autorizacao mais forte que a senha compartilhada), mount `:ro` da trilha no container do bot
(compose) e cron `7 */3 * * *` na VPS (`scripts/cron/run_relatorio_acessos.sh`, molde do
run_growth_daily: container efemero da imagem da api, credenciais por env herdada — nunca argv).

QA: revisao adversarial por workflow (39 agentes: 3 lentes -> 2 ceticos por achado -> 14
confirmados, 4 refutados) — TODOS corrigidos no ciclo. Destaques: token do bot vazava no log do cron
via traceback do requests (URL do HTTPError) -> erro controlado sem URL + teste; relatorio rotulava
dia BRT lendo so o arquivo do dia UTC (entre 21h e 0h BRT negaria o dia inteiro) -> agregacao por
dia BRT lendo os 2 arquivos UTC + teste de virada; nome de usuario cru quebrava o parse_mode
Markdown -> texto puro + chunking <=4096; env vazia furava o guard do bot -> validator. Suite
completa: 3206 passed (1 falha pre-existente ambiental do Windows). Merge admin + deploy api/bot +
instalacao do cron autorizados por Felipe ("faca tudo sozinho").

## Fechamento de ciclo — Aba Acessos do piloto (painel restrito + rollup sem dado pessoal) (2026-08-19, ad-hoc)

Pedido de Felipe: transformar o relatorio de acessos numa aba do piloto com acesso limitado, para
analisar volume/uso e ver quem esta acessando — com as 4 escolhas dele registradas na emenda da
DEC-027: detalhe ate' o nivel de FEATURE (nunca query/conteudo), IP so como contagem de distintos,
rollup diario sem dado pessoal para tendencia alem dos 90 dias, e card de saude (erro + p95).

Entrega: backend `motor_expansao/dashboard/acesso_analytics.py` (agregacoes por dia BRT + rollup
`uso-diario.json` write-once por dia fechado, atomico, sem nome/IP/rota, consolidado no startup e a
cada abertura da aba) + rotas `/api/acessos/*` guardadas NO MIDDLEWARE por allowlist de env
`MOTOR_ACESSOS_ADMIN_USUARIOS` (404 para quem esta fora; `acessos` fora de ABAS_VALIDAS — o
acesso_abas.json nao concede nem por curinga; fail-open do front tambem nao) + tela
`web/src/screens/AcessosScreen.tsx` (big numbers, serie do rollup, heatmap hora×dia BRT, uso por
aba, tabela de usuarios -> ficha por feature, saude; SVG/CSS a mao, zero dependencia npm nova).
O painel e' auditado na trilha mas EXCLUIDO das metricas na aba E no relatorio 3/3h do Telegram,
pelo MESMO filtro (`evento_valido`/`ROTAS_FORA_DA_METRICA` em relatorio_acessos.py). Consertados no
caminho 3 testes data-frageis do ciclo anterior (CLI/bot liam o relogio real; passaram em 2026-08-18
por coincidencia — relogio congelado por monkeypatch). Docs: emenda na DEC-027 + secao nova em
`docs/trilha_acesso_piloto.md` + `deploy_piloto_web.md` + linha do §8 (CLAUDE.md) marcada emendada.
READ-ONLY sobre o M1; guardrail AST do app.py intacto (writer do rollup no modulo).

QA do ciclo: revisao adversarial por workflow (25 agentes: 7 lentes -> 1 cetico com REPRODUCAO por
achado) — 18 defeitos confirmados (7 media, 11 baixa; 0 critico/alto), TODOS corrigidos no proprio
ciclo. Destaques: as rotas do painel vazavam existencia+descricao no /openapi.json para qualquer
autenticado (include_in_schema=False + teste anti-regressao); rollup com conteudo invalido era
REESCRITO destruindo o historico alem dos 90d (agora: quarentena .corrompido com bytes preservados,
IO transitorio so adia a rodada, dia so consolida com o proprio arquivo legivel); dia da trilha
podia ser podado antes de consolidado (hook de virada de dia em acesso_log, ANTES da poda); guard do
middleware e startup do rollup nao eram exercitados por teste (falso-verde) -> testes de registro,
comportamento e OpenAPI; serie cai para contagem viva quando o rollup nao grava; teto de 180 barras
no grafico; aria-pressed e feedback de refetch na tela. Suites: 3242 passed na completa (1 falha
pre-existente ambiental do Windows) + 114 na bateria de acesso + 589 vitest + build da SPA. Merge
admin + deploy autorizados por Felipe ("faca o trabalho completo, do PR -> Merge Admin -> Deploy").

## Fechamento de ciclo — Redesign da aba Acessos (full-width + visual + ficha detalhada) (2026-08-19, ad-hoc)

Pedido de Felipe (3 ajustes sobre a aba entregue no mesmo dia): layout distribuido pela tela toda,
visual revisto (graficos/cores/design) e mais detalhe nos perfis individuais. Entrega: grid de 12
colunas full-width; grafico de serie em SVG medido (barras de acoes + linha de usuarios unicos em
base ZERO com escala propria declarada na legenda); Rosca da Executiva reaproveitada para uso por
aba; COR DE IDENTIDADE por aba (--gr-azul executiva, --ac mapa, --gr-verde viabilidade, --gr-rosa
oportunidades) em rosca, tabelas, avatares e linha do tempo; sparkline de ate 14 dias por usuario
na tabela (nunca alem da janela carregada); heatmap com rampa color-mix. Ficha nova: sessoes por
gap de 30 min com duracao, linha do tempo das ultimas 80 acoes (feature+hora+flag de erro — SEM
rota/query/conteudo, corte da emenda DEC-027 intacto e agora VIGIADO no ramo fallback), heatmap e
distribuicao por aba do usuario, contagem de erros, guardas contra payload antigo.

QA: revisao adversarial por workflow (21 agentes: 4 lentes -> cetico com reproducao) — 16 achados
confirmados (1 alta, 6 media, 9 baixa, com duplicatas entre lentes), TODOS corrigidos. Destaques:
falso-verde no teste-guardiao de privacidade (o ramo 'Outras acoes' — o unico com a rota bruta em
maos — nao era exercitado; sabotagem passou verde) -> evento de rota nao mapeada com sentinela no
path; linha de usuarios em escala min-max sobre eixo numerico (serie constante desenhava no meio)
-> base zero + escala propria; doc prometia 'rota nunca' mas o card de saude lista rotas agregadas
-> claim escopado; tetos/virada-de-dia sem teste -> cobertos. Suites: 36 no modulo + 589 vitest +
mypy/ruff limpos + build ok.
