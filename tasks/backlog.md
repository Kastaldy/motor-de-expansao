# Backlog

## Priorização atual

Próximo ciclo recomendado: validar a estrutura de Skills com uma tarefa real do projeto.

---

## Tarefas pendentes

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

### BLK-PROD-04 — Avaliar st.fragment para interações do mapa

Status: concluido (2026-05-25)
Criticidade: média
Prioridade: baixa
Tipo: performance / UI
Skill recomendada: /run-cycle
Resumo: Implementado render_mapa_pydeck_fragment (@st.fragment) em pages.py. Reduz reruns da aba ao isolar st.pydeck_chart e captura de clique. QA aprovado: 532 passed, 1 skipped.
Dependências: nenhuma

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





