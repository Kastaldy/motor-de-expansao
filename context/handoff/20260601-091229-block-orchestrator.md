# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (esteira com gate de REVISÃO HUMANA após o Planner, antes do Builder).

## Bloco refinado
**BLK-SEC-01 — Gate de publicação no CI (publish só com CI verde) + pin de imagem e rollback**

Estado verificado do repositório (HEAD de `ciclo/BLK-SEC-01`, a partir de `main` @719b2ae):

- `.github/workflows/docker-publish.yml` (workflow `Docker Publish (GHCR)`): dispara em
  `push: branches:[main]` + `workflow_dispatch`. Job único `build-push`. JÁ taggeia por
  `type=sha` (gera `sha-<7chars>`) e `latest` (só em default branch). NÃO tem `needs:` nem
  `workflow_run` — **publica independentemente do resultado do CI**. Este é o gap central.
  Usa `docker/metadata-action@v5` (que já injeta o label OCI `org.opencontainers.image.revision`
  com o SHA) e `docker/build-push-action@v6` (que expõe `steps.<id>.outputs.digest` — o digest
  imutável `sha256:...` da imagem publicada).
- `.github/workflows/ci.yml` (workflow `CI`, **separado**): job `test` em `ubuntu-latest`,
  Python 3.11, passos bloqueantes ruff → mypy `src/` → `pytest -q` → smoke import. Dispara em
  push `main`/`codex-dashboard-m1-streamlit` + PR para `main` + `workflow_dispatch`.
- `docker-compose.prod.yml`: serviço `streamlit` usa
  `image: ${STREAMLIT_IMAGE:-ghcr.io/kastaldy/motor-de-expansao/motor-expansao-streamlit:latest}`.
  JÁ suporta override por env `STREAMLIT_IMAGE`. O **default** é `:latest` (tag móvel, sem pin).
- `docs/deploy.md`: runbook modo PULL já documentado, com seção **Rollback (por SHA)** — porém o
  rollback hoje é por **tag móvel** `sha-<commit>` (mutável), não por **digest imutável**.
- `docs/infra_producao.md`: a seção "Atualizar o código do dashboard" (linhas 33-47) ainda
  descreve o modelo ANTIGO `git pull` + `docker compose ... up -d --build streamlit` (build no
  servidor), que **contradiz** o modelo PULL de `deploy.md` e `docker-compose.prod.yml`. Não há
  seção de rollback em `infra_producao.md`.

## Objetivo
Garantir que SÓ imagens de um commit com CI verde sejam publicadas no GHCR, e tornar o deploy
de produção reproduzível e reversível: imagem identificada por SHA do commit, compose de prod
fixando um digest/SHA conhecido (não `:latest` cego) e runbook de rollback testável (voltar para
a imagem anterior sem rebuild). **Nada disso toca M1, score, carteira, plano ou artefatos
oficiais — é exclusivamente CI/CD e infra de publicação.**

## Escopo permitido
1. **Acoplar o publish ao sucesso do CI.** Escolher e implementar UMA das duas opções abaixo
   (decisão técnica recomendada na seção "Esteira recomendada"; escolha final é do Planner +
   aprovação humana):
   - **Opção A — `workflow_run`:** manter dois workflows; `docker-publish.yml` deixa de disparar
     em `push` e passa a disparar em `workflow_run` do workflow `CI` com filtro
     `workflows: ["CI"]`, `types: [completed]`, `branches: [main]`, e um guard de job
     `if: ${{ github.event.workflow_run.conclusion == 'success' }}`. O checkout/tag passa a usar
     o SHA de `github.event.workflow_run.head_sha` (não `github.sha`, que em `workflow_run` aponta
     para o default branch — ponto de atenção crítico para taguear o commit certo).
   - **Opção B — workflow único com `needs`:** fundir publish dentro de `ci.yml` (ou um único
     arquivo) com job `publish` que declara `needs: [test]` e roda só em
     `if: github.ref == 'refs/heads/main' && github.event_name == 'push'`. `needs` já garante que
     `publish` só roda se `test` passou; o SHA correto é `github.sha`.
2. **Tag por SHA do commit** (além de `:latest`): já existe via `type=sha`; confirmar formato e
   manter (avaliar `type=sha,format=long` para SHA completo se o Planner preferir mais legível no
   compose — opcional).
3. **Pin do `docker-compose.prod.yml` por digest/SHA** (não `:latest` cego) + atualizar o runbook
   de rollback em `docs/infra_producao.md` (e, por consistência, alinhar com `docs/deploy.md`).
   Decisão a registrar pelo Planner: **digest imutável** (`...@sha256:<digest>`, recomendado para
   reprodutibilidade real e o critério de aceite "fixa um digest conhecido") **vs** tag `sha-<commit>`
   (rastreável mas móvel). O default do compose pode passar de `:latest` para um SHA/digest
   conhecido, preservando o override por `STREAMLIT_IMAGE`.
4. **Estratégia de prova do gate** (ver Critérios de aceite): provar que CI vermelho NÃO publica
   sem precisar de push malicioso real à `main`.

## Fora de escopo
- Qualquer mudança em M1, `score_priorizacao`, `hex_score_estrutural`, pesos, carteira, plano de
  curto prazo, plano de domínio ou artefatos oficiais do M1. (Este bloco não os toca.)
- Assinatura de imagem (cosign) e attestation/SBOM — **follow-up** (BLK-SEC futuro).
- Varredura de vulnerabilidades / gitleaks como gate — é o **BLK-SEC-02**, bloco separado.
- Executar qualquer comando no VPS (guardrail §6: deploy/rollback no servidor é sempre passo
  humano, comando a comando). O runbook é documentação; nada roda no servidor neste ciclo.
- Reescrever a lógica do CI (`test`) em si; o gate apenas o consome como dependência.

## Arquivos que devem ser lidos
- `CLAUDE.md` — §2 (regras operacionais; commit por path, nada de `git add -A`), §6 (guardrails
  de infra/VPS), §7 (onde aprofundar).
- `tasks/current_task.md` — escopo e contexto de abertura do ciclo.
- `tasks/backlog.md` — linhas 140-178 (definição canônica do BLK-SEC-01).
- `.github/workflows/docker-publish.yml` — workflow a acoplar ao CI.
- `.github/workflows/ci.yml` — workflow `CI` (a dependência/gate).
- `docker-compose.prod.yml` — serviço `streamlit`, linha 23 (`image:` com default `:latest`).
- `docs/deploy.md` — runbook PULL + rollback por SHA (estado atual, base do digest-pin).
- `docs/infra_producao.md` — seção "Atualizar o código" (modelo antigo a alinhar) + onde inserir
  rollback.
- (Referência) `Dockerfile.streamlit` e `.dockerignore` — confirmar que a imagem não embute
  segredos/dados (já garantido; não alterar).

## Arquivos que podem ser alterados
- `.github/workflows/docker-publish.yml` (acoplamento ao CI + tag por SHA).
- `.github/workflows/ci.yml` (somente se a Opção B — workflow único com `needs` — for escolhida).
- `docker-compose.prod.yml` (pin do default por digest/SHA; preservar override `STREAMLIT_IMAGE`).
- `docs/infra_producao.md` (runbook de rollback + alinhar seção de atualização ao modelo PULL).
- `docs/deploy.md` (opcional: alinhar rollback por digest, se o Planner adotar digest).
- Housekeeping do ciclo: `tasks/current_task.md`, `tasks/backlog.md`, `tasks/completed.md`,
  `context/handoff.md`, `context/handoff/`.

## Critérios de aceite
1. **Gate comprovado:** existe evidência de que um commit com CI vermelho NÃO publica imagem.
   Estratégia de prova viável SEM push malicioso à `main` (escolher ≥1; recomendado os três níveis):
   - **Estática (sempre):** o YAML do publish depende explicitamente do sucesso do CI — Opção A:
     `if: github.event.workflow_run.conclusion == 'success'`; Opção B: `needs: [test]`. Revisor
     confirma que não há caminho de publish sem o CI passar.
   - **Dinâmica controlada:** disparar numa branch de ciclo (não `main`) ou via `workflow_dispatch`
     um cenário com `test` falho proposital (ex.: commit temporário que quebra um teste/lint na
     branch `ciclo/BLK-SEC-01`) e mostrar nos Actions que o job `publish`/`build-push` foi
     **skipped/não executado**; depois reverter o quebra-proposital. Documentar o run id.
   - (Opcional) `act`/dry-run local se disponível — não obrigatório.
2. **Tag por SHA:** a imagem publicada recebe tag `sha-<commit>` (já existe; manter e confirmar no
   run de teste do publish numa branch/dispatch).
3. **Pin no compose:** `docker-compose.prod.yml` deixa de ter `:latest` como pin cego — o default
   referencia um digest (`@sha256:...`) ou SHA conhecido, mantendo o override `STREAMLIT_IMAGE`.
4. **Runbook de rollback testável:** `docs/infra_producao.md` tem passos para voltar à imagem
   anterior por SHA/digest, **sem rebuild** (`export STREAMLIT_IMAGE=...@sha256:<anterior>` →
   `pull` → `up -d`). "Testado" aqui = passos validados como coerentes e auto-suficientes na
   revisão (execução real no VPS é passo humano fora deste ciclo, por §6); a seção antiga de
   `--build` em `infra_producao.md` deixa de contradizer o modelo PULL.
5. **Zero mudança em M1/artefatos:** nenhum arquivo de score/pipeline/artefato oficial é tocado;
   `git diff` do ciclo contém só workflows, compose, docs e housekeeping.
6. **CI verde:** o próprio CI da branch do ciclo permanece verde (ruff/mypy/pytest/smoke), e o
   novo encadeamento não introduz erro de sintaxe de workflow (validável por `gh workflow` /
   parser do Actions).

## Criticidade classificada
**ALTA.** NÃO é Crítica: o bloco é exclusivamente CI/CD e infra de publicação — **não toca**
`score_priorizacao`, `hex_score_estrutural`, pesos, carteira, plano de curto prazo, plano de
domínio nem nenhum artefato oficial do M1. Registrado explicitamente que **M1 não é tocado**
(guardrail M1 permanece intacto). A criticidade Alta deriva da integridade do CI/CD e do impacto
no artefato de produção (imagem que a VPS puxa), exigindo gate de **REVISÃO HUMANA** após o
Planner.

## Esteira recomendada
Block Orchestrator → Planner → **[REVISÃO HUMANA]** → Builder → QA.

**Recomendação técnica de acoplamento — Opção B (workflow único com `needs: [test]`).**
Trade-offs:
- **Opção B (recomendada):** mais simples e menos sujeita a erro. `needs: [test]` é uma garantia
  nativa e legível ("publish só roda se test passou"); o SHA correto é `github.sha` sem
  malabarismo. Evita a principal armadilha da Opção A. Custo: re-roda no mesmo workflow (pode
  reusar setup/cache) e exige condicionar `publish` a `push` na `main` (`if`), além de fundir os
  dois arquivos ou adicionar o job `publish` ao `ci.yml`.
- **Opção A (`workflow_run`):** mantém os dois workflows separados e desacoplados, e só dispara o
  build após o CI concluir. Porém é a opção mais propensa a erro sutil: em eventos `workflow_run`,
  `github.sha`/`actions/checkout` apontam para o **head do default branch**, não para o commit
  testado — é preciso usar `github.event.workflow_run.head_sha` explicitamente no checkout e na
  metadata-action, ou corre-se o risco de buildar/taguear o commit errado. Também herda a
  limitação de `workflow_run` só disparar quando o workflow base está na branch default.

Decisão final entre A e B fica para o Planner + aprovação humana; ambas satisfazem os critérios de
aceite se implementadas corretamente. Sobre o pin do compose, recomenda-se **digest imutável**
(`@sha256:<digest>`) por ser o único que satisfaz literalmente "fixa um digest conhecido" e dá
reprodutibilidade real (tag `sha-<commit>` é rastreável mas tecnicamente remarcável).

## Riscos identificados
- **(Opção A) SHA errado:** `workflow_run` taguear/buildar o commit do default branch em vez do
  commit testado. Mitigação: usar `head_sha` explicitamente — ou escolher Opção B.
- **Janela de publicação:** ao acoplar ao CI, a imagem `:latest`/`sha-<commit>` só sobe após o CI
  verde — leve aumento de latência entre merge e imagem disponível (aceitável; é o objetivo).
- **Pin por digest e atualização operacional:** com digest fixo no compose, cada deploy passa a
  exigir atualizar o digest (ou usar override `STREAMLIT_IMAGE`); documentar bem no runbook para
  não "congelar" produção por engano.
- **Prova do gate sem push à `main`:** o cenário de falha proposital precisa rodar em branch de
  ciclo / `workflow_dispatch` e ser revertido; risco de deixar resíduo de "quebra de teste" se não
  for limpo. Mitigação: commit temporário isolado + reversão documentada na branch do ciclo.
- **Inconsistência de docs:** `infra_producao.md` (modelo `--build`) vs `deploy.md` (modelo PULL);
  se o runbook de rollback for adicionado sem alinhar a seção antiga, a doc fica contraditória.
- **Permissões/registry:** GHCR privado exige `read:packages` no VPS para o `pull` por
  digest/SHA; isso é runtime do servidor (fora do escopo de execução, mas mencionar no runbook).
- **Guardrail §6:** nenhuma validação pode rodar no VPS via agente/MCP; tudo que envolve o
  servidor é passo humano documentado.

## Guardrails ativos
- **M1 intocável (permanente):** nenhuma alteração em score, pesos, fórmula, carteira, planos ou
  artefatos oficiais do M1. Este bloco não os toca.
- **§2:** commit SÓ por path; nunca `git add -A`; não arrastar `PRD.md` nem edições não
  relacionadas. Toda mudança relevante entra com teste/evidência; nenhum PR sobe com CI quebrado.
- **§6:** GUARDRAIL ABSOLUTO — nunca executar comando no VPS (MCP/SSH) sem confirmação explícita do
  usuário, comando a comando; não encadear comandos no servidor. Deploy/rollback no servidor é
  passo humano. Runbooks são documentação.
- **Esteira com gate humano:** Criticidade Alta ⇒ REVISÃO HUMANA obrigatória após o Planner, antes
  do Builder.
- **Um bloco por vez; não expandir escopo.** BLK-SEC-02 (varredura/gitleaks) e cosign são blocos/
  follow-ups separados.
