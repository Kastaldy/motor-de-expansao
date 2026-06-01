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
