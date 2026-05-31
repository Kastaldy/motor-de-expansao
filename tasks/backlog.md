# Backlog

## Priorização atual

Próximo ciclo recomendado: validar a estrutura de Skills com uma tarefa real do projeto.

> Blocos BLK-OPS-02/03/04, BLK-ARCH-01 e BLK-SCORE-01/02/03 originados do "Programa de
> Melhorias — Referência do Master Orchestrator" (PRD.md), migrados em 2026-05-29.
> Mapa de dependências e ordem recomendada do programa: ver §3 do PRD.md original.
> Ordem deste backlog: arquitetura (BLK-ARCH-01) à frente da trilha de score (BLK-SCORE-*).

---

## Tarefas pendentes

- BLK-OPS-06 (concluído 2026-05-29) — ver tasks/completed.md
- BLK-OPS-07 (concluído 2026-05-29) — ver tasks/completed.md
- BLK-PRD-01 (concluído 2026-05-29) — ver tasks/completed.md
- BLK-OPS-02 (concluído 2026-05-29) — ver tasks/completed.md
- BLK-OPS-02b (concluído 2026-05-29) — ver tasks/completed.md
- BLK-OPS-08 (concluído 2026-05-29) — ver tasks/completed.md

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

### BLK-SCORE-05 — Viabilidade de proxy exógeno de demanda (pré-requisito de modelagem)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (LEITURA/ANÁLISE + engenharia de dados; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Depende de** | **BLK-SCORE-02**, **BLK-SCORE-03 (DEC-001)**, **BLK-SCORE-04** |
| **Status** | Pendente |
| **Origem** | pergunta do usuário "dá para modelar demanda potencial por hex?" (2026-05-31) |

**Contexto / por que existe:** BLK-SCORE-02/04 mostraram que NÃO é possível, hoje, treinar um modelo
preditivo confiável de demanda. Três bloqueios estruturais: (1) **viés de seleção** — o único
desfecho (`alunos_recorrentes`) só existe onde JÁ há unidade; não há observação de demanda em hexes
vazios (sem contrafactual); (2) **alvo enviesado/ruidoso** — desfecho pós-seleção e pós-maturação,
sem `maturacao_status` real, heterogêneo entre redes; (3) **sinal exógeno ≈ nulo** — features de
mercado/competição com IC cruzando zero, OLS conjunto R²≈0.034; o sinal que sobra é endógeno (rede
própria). Conclusão: o gargalo é de DADOS, não de algoritmo. Este bloco é o **pré-requisito de
engenharia de dados ANTES de qualquer modelagem** — NÃO é um bloco de ML.

**Objetivo:** avaliar, read-only, a VIABILIDADE de obter (a) um sinal de **maturação** por unidade
(data de abertura ou proxy auditável) e (b) ao menos um **proxy de demanda EXÓGENO** — independente
da existência de academia no hex. Entregar um diagnóstico de disponibilidade/qualidade de fontes +
recomendação GO/NO-GO para um futuro bloco de modelagem, SEM construir modelo nem alterar score.

**Escopo permitido (read-only, diagnóstico):**
- Inventariar fontes candidatas de demanda exógena e checar cobertura/granularidade por hex/município:
  - **Penetração Wellhub/Gympass** (já há `sinal_wellhub`, `n_parcerias_wellhub` no dataset de
    validação — medir cobertura e se é exógeno ou colado a unidades existentes);
  - dados de **mobilidade/fluxo** ou **busca/intenção** (avaliar se há fonte acessível offline/legal,
    sem criar dependência de API ao vivo — guardrail do projeto);
  - sinais demográfico-comportamentais já no censo/IBGE não usados (faixa etária, vínculo formal,
    renda do trabalho) que correlacionem com propensão a academia.
- Avaliar viabilidade de **maturação**: existe data de abertura por unidade (Ultra real; concorrentes
  via mapeamento)? Que proxy auditável (ex.: primeira aparição em snapshot) seria aceitável?
- Estimar, com o que houver, se algum proxy exógeno tem correlação não-trivial com `alunos_recorrentes`
  CONTROLANDO maturação (reusar `analysis/score_backtest.py`/`feature_backtest_mercado.py`).
- Produzir relatório `data/analysis/viabilidade_demanda.md` (gitignored) com: matriz de fontes ×
  (cobertura, granularidade, exógena S/N, custo/risco de obtenção), achado de correlação controlada
  (se viável), e **recomendação GO/NO-GO** para um eventual `BLK-SCORE-06 — modelo de demanda`.

**Fora de escopo (invioláveis):**
- Construir/treinar qualquer modelo preditivo (isso seria o BLK-SCORE-06, só com GO + seu gate).
- Qualquer escrita/recálculo de M1 (`scoring.py`/`constants.py`/pesos/artefatos) — DEC-001 vigente.
- Criar dependência de API ao vivo no dashboard de produção (guardrail do CLAUDE.md).
- Inventar proxy de maturação/idade sem base auditável (lição do BLK-SCORE-02 §5).
- Saída fora de `data/analysis/`; qualquer PII (`nome_unidade`) no relatório.

**Arquivos a ler:** `data/analysis/relatorio_backtest.md`, `data/analysis/relatorio_backtest_mercado.md`,
`data/analysis/dataset_validacao.parquet` (colunas `sinal_wellhub`/`n_parcerias_wellhub`/`maturacao_status`),
`CLAUDE.md` §8 (DEC-001) e §4 (camadas), `analysis/feature_backtest_mercado.py` (reuso).
**Arquivos a alterar (read-only sobre M1):** novo script de diagnóstico em `analysis/` + testes
sintéticos; relatório em `data/analysis/` (gitignored). NENHUM artefato M1.

**Critérios de aceite:**
- Relatório `data/analysis/viabilidade_demanda.md` com matriz de fontes + veredito GO/NO-GO fundamentado.
- Diagnóstico explícito de maturação (disponível? proxy aceitável?) e de pelo menos 1 proxy exógeno.
- Se houver correlação controlada, reportada com incerteza (IC, N, confounds); sem forçar significância.
- ZERO escrita em M1/artefatos oficiais; ZERO PII; reprodutível (seed fixo; script versionado).

**Guardrails específicos:** READ-ONLY sobre M1; diagnóstico de viabilidade, NÃO modelagem; sem
dependência de API ao vivo; alimenta a decisão sobre os gates G1/G2/+contrafactual da DEC-001.

**Risco:** baixo (read-only). O valor é evitar investir em ML sobre dados que não identificam demanda;
o entregável é um GO/NO-GO honesto, não um modelo.

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

**Causa raiz (diagnóstico já feito):** dependências **não-pinadas** no `pyproject.toml` (ex.:
`ruff>=0.4.0`, sem teto para pandas/numpy/pydantic). O CI instala o que há de mais novo —
**pandas 3.0.3, numpy 2.4.6, pydantic latest** — enquanto o dev local tem **pandas 2.3.3, numpy
2.3.4, pydantic 2.12.5**. A versão nova do pydantic não aceita mais o padrão `@property CORES` da
classe `Settings` (`src/motor_expansao/config.py`, linhas 84 e 153 — `CORES` aparece definido 2x)
na inicialização. Também há risco latente de breaks por pandas 3.0.

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

### BLK-SEC-02 — Varredura de vulnerabilidades (deps + imagem) e gitleaks como gate de CI

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (supply-chain; não toca M1/score) |
| **Prioridade** | **Média-Alta** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Depende de** | **BLK-OPS-11** (deps pinadas) e idealmente **BLK-SEC-01** |
| **Status** | Pendente |
| **Origem** | revisão de robustez 2026-05-31 |

**Contexto / gap:** não há varredura automatizada de vulnerabilidades de dependências nem da imagem
de produção; o `gitleaks` (com `.gitleaks.toml`/`.gitleaksignore` do BLK-OPS-01) existe mas **não roda
como gate no CI**. Combinado com deps não-pinadas (BLK-OPS-11), o risco de supply-chain é real.

**Objetivo:** detectar dependências/imagens vulneráveis e segredos vazados ANTES do merge/deploy.

**Escopo permitido:**
- `pip-audit` (ou Dependabot/`safety`) sobre as deps pinadas, como step do CI.
- Scan da imagem GHCR (Trivy/Grype) no pipeline de publish.
- `gitleaks` como **step bloqueante** do CI (reusa a config existente do BLK-OPS-01).
- Definir política de severidade (o que bloqueia vs. o que só alerta) para evitar CI ruidoso.

**Fora de escopo:** remediar toda CVE histórica de uma vez (priorizar por severidade); assinatura de
imagem (cosign) — follow-up.

**Arquivos prováveis:** `.github/workflows/ci.yml`, `.github/workflows/docker-publish.yml`,
`pyproject.toml`/lock, `.gitleaks.toml`.

**Critérios de aceite:**
- CI roda `pip-audit` + `gitleaks` (bloqueantes por severidade definida) e scan de imagem no publish.
- Um segredo de teste plantado é pego pelo gitleaks (prova do gate); removido depois.
- Política de severidade documentada; zero mudança em M1/artefatos.

**Risco:** baixo-médio (ferramental/CI). Cuidado para não tornar o CI instável por CVEs de baixa
severidade — calibrar o gate.

---

### BLK-SEC-03 — Hardening do VPS (firewall, fail2ban, updates, SSH, 2FA)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (exposição do servidor de produção) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Origem** | revisão de robustez 2026-05-31 (acesso root SSH; sem hardening documentado) |

**Contexto / gap:** o `docs/infra_producao.md` mostra acesso como `root` via SSH e atualização de
sistema **manual mensal**; não há menção a firewall (ufw), fail2ban, `unattended-upgrades`, política de
SSH (desabilitar login por senha / limitar root) nem 2FA obrigatório no Authelia (hoje "opcional").

**Objetivo:** reduzir a superfície de ataque do VPS de produção sem quebrar o deploy atual.

**Escopo permitido (cada passo via MCP com confirmação individual — guardrail do projeto):**
- `ufw` liberando só 22/80/443; `fail2ban` no SSH; `unattended-upgrades` para patches de segurança.
- SSH: desabilitar autenticação por senha (manter chave), avaliar usuário não-root para operação.
- Authelia: avaliar **forçar 2FA** para o grupo `ultra_team`.
- Documentar tudo em `docs/infra_producao.md` (seção de hardening) com rollback de cada item.

**Fora de escopo:** trocar provedor/arquitetura; mudar M1/dashboard.

**Critérios de aceite:**
- Firewall ativo (regras mínimas), fail2ban e unattended-upgrades rodando; SSH sem senha.
- Dashboard e deploy continuam funcionando (smoke + login OK após cada mudança).
- Cada alteração no VPS feita com confirmação individual; documentada com rollback.

**Risco:** médio-alto (mexer em SSH/firewall pode trancar o acesso). Mitigação: alterar um item por vez,
manter sessão aberta de teste, ter rollback pronto ANTES de aplicar regras de SSH/ufw.

---

### BLK-SEC-04 — Backup automatizado dos dados de produção (parquets) + restore testado

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (continuidade de dados; não toca M1/score) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Origem** | revisão de robustez 2026-05-31 (BLK-OPS-01 cobre segredos, não dados) |

**Contexto / gap:** o BLK-OPS-01 entregou backup/DR dos **segredos**, mas os **dados** de produção
(`/opt/motor-expansao/data/outputs/`, ~1.6 GB de parquets do M1) hoje só têm "manter cópia local na
máquina de dev" como backup — manual e frágil. Não há snapshot periódico nem restore testado.

**Objetivo:** garantir recuperação dos parquets de produção após perda/corrupção, com restore provado.

**Escopo permitido:**
- Definir destino de backup (snapshot do provedor, bucket S3-compatível, ou cópia versionada off-box).
- Job agendado (cron na janela 2h–5h BRT, fora do pico) que faz snapshot dos `data/outputs/`.
- Política de retenção (ex.: diários 7d / semanais 4w) e verificação de integridade (checksum).
- **Restore testado** em pasta limpa (igual ao rigor do BLK-OPS-01) + runbook em `docs/`.

**Fora de escopo:** versionar parquets no git (são grandes/gerados); recalcular M1.

**Critérios de aceite:**
- Backup automatizado rodando com retenção definida; checksums conferem.
- Restore validado end-to-end (arquivos íntegros) e documentado.
- Sem PII em logs; sem dependência de API ao vivo no dashboard.

**Risco:** baixo. Atenção a custo/espaço do destino e a não competir com usuários (janela noturna).

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

### BLK-PROD-03 — Avaliar hex_id como category com benchmark

Status: pendente
Criticidade: média
Prioridade: baixa
Tipo: performance
Skill recomendada: /run-cycle
Resumo: hex_id é chave de join; avaliar se category ajuda ou prejudica performance.
Requer benchmark antes de qualquer mudança.
Dependências: nenhuma

---

### BLK-PROD-02 — Limpar leftovers de staging

Status: pendente
Criticidade: baixa
Prioridade: baixa
Tipo: manutenção
Skill recomendada: /run-cycle
Resumo: Remover data/outputs/*.tmp.parquet e diretório tmp_codex_runtime/.
Dependências: aprovação explícita do usuário para remoção de arquivos.
Observações: não executar sem confirmação explícita. Risco de remoção indevida.

---

### BLK-PROD-01 — Refatoração completa do repositório

Status: pendente
Criticidade: estratégica
Prioridade: média
Tipo: refatoração
Skill recomendada: /run-cycle (fluxo estratégico)
Resumo: Migrado do PRD.md. Próxima etapa de planejamento estrutural do repositório.
Dependências: nenhuma bloqueadora
Observações: requer planejamento detalhado antes de execução. Não iniciar sem aprovação.

---

### BLK-PROD-05 — Geocodificação offline/online de endereço

Status: pendente
Criticidade: alta
Prioridade: baixa
Tipo: feature
Skill recomendada: /run-cycle
Resumo: Implementar geocodificação de endereço apenas se dependência externa for
aprovada ou base local viável identificada.
Dependências: aprovação de dependência externa ou base local.

---

### BLK-PROD-06 — Relatório semanal de movimentação concorrencial

Status: pendente
Criticidade: alta
Prioridade: baixa
Tipo: feature / analytics
Skill recomendada: /run-cycle
Resumo: Snapshots, deltas por rede/cidade e impacto nas oportunidades.
Dependências: definição de fonte de dados concorrencial automatizável.

---

### BLK-PROD-07 — Cenários salvos por usuário e histórico de decisão

Status: pendente
Criticidade: alta
Prioridade: baixa
Tipo: feature
Skill recomendada: /run-cycle
Resumo: Apenas se o dashboard evoluir para produto web interno com múltiplos usuários.
Dependências: decisão de produto sobre evolução para web interno.

---
