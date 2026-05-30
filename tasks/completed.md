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
