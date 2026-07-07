# Handoff: BLK-PROD-02 — Limpar leftovers de staging
## Timestamp: 2026-07-07 (Block Orchestrator, ciclo/loop-20260707-123809)

**Gerador:** Block Orchestrator (delimitação)
**Próxima Skill:** Builder
**Status:** Ready for Builder

---

## Bloco delimitado
| Campo | Valor |
|---|---|
| **ID** | BLK-PROD-02 |
| **Nome** | Limpar leftovers de staging |
| **Criticidade** | Baixa (manutenção; **READ-ONLY M1**) |
| **Autonomia** | loop-safe (paths PRÉ-APROVADOS no backlog) |
| **Esteira** | Block Orchestrator → Builder (sem Planner, sem QA) |
| **Branch** | ciclo/loop-20260707-123809 |

---

## Decisão de produto / PRÉ-APROVAÇÃO
**Nenhuma decisão de produto necessária.** Os 2 globs estão **PRÉ-FIXADOS no backlog § BLK-PROD-02** e substituem a "confirmação explícita" — este é o opt-in do loop:

1. Remover o diretório completo: `/repo/tmp_codex_runtime/`
2. Remover arquivos: `/repo/data/outputs/*.tmp.parquet` (APENAS com sufixo `.tmp`)

**Nenhum outro caminho alterado.**

---

## Verificação de estado (Block Orchestrator)

### Paths a deletar
- `/repo/tmp_codex_runtime/` → EXISTS
  - Contém: `manual_pytest/`, `pytest/`, `pytest_alt/`, `qa_pytest_full.log`, `write_test.txt`
- `/repo/data/outputs/monitoramento_expansao_hibrido_base.tmp.parquet` → EXISTS
- `/repo/data/outputs/oportunidades_expansao_hibrido.tmp.parquet` → EXISTS

### Paths a preservar
- Artefatos oficiais M1 em `data/outputs/`:
  - `brasil_estrutural.parquet` (mtime: inalterado)
  - `brasil_priorizados.parquet` (mtime: inalterado)
  - `hexagonos_brasil_oportunidades.parquet` (mtime: inalterado)
  - `hexagonos_brasil_dashboard.parquet` (mtime: inalterado)
  - NENHUM outro `.parquet` sem sufixo `.tmp` será tocado

---

## Guardrails
- **§5 READ-ONLY M1:** nenhuma escrita em `config.py`, `src/motor_expansao/pipelines/m1/`, artefatos oficiais M1.
- **Deleção restrita:** só os 2 globs pré-aprovados. `loop_guard.py` aborta se diff tocar `config.py`/`pipelines/m1`/artefatos M1.
- **Sem rede, sem VPS, sem commit ao vivo.**
- **Paths de commit:** `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md`

---

## Entregáveis do Builder
1. ✓ Deletar `/repo/tmp_codex_runtime/` (inteiro, `shutil.rmtree`)
2. ✓ Deletar `/repo/data/outputs/monitoramento_expansao_hibrido_base.tmp.parquet`
3. ✓ Deletar `/repo/data/outputs/oportunidades_expansao_hibrido.tmp.parquet`
4. ✓ Verificar artefatos oficiais M1: mtime INALTERADO
5. ✓ Smoke test: `python -c "import sys; sys.path.insert(0, 'src'); from motor_expansao.streamlit_app import main"`
6. ✓ Commit pelo caminho: `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md`

---

## Critérios de aceite
- ✓ Só os 2 globs removidos; nenhum outro caminho alterado
- ✓ Artefatos oficiais M1 em `data/outputs/` intactos (mtime inalterado, zero diff em ruff)
- ✓ Nenhuma escrita em `config.py` / `pipelines/m1` / `artefatos M1`
- ✓ `loop_guard` limpo (commit diff não toca caminhos sensíveis)
- ✓ Smoke test verde

---

## Próxima Skill
**Builder** (implementação + validação)
