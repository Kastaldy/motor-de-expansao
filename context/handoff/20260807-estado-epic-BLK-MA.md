# Estado do epic BLK-MA (vulnerabilidade / M&A) — 2026-08-07

> Handoff para retomar o epic numa sessão nova. Consolida o que mudou entre 2026-08-04 e
> 2026-08-07, o que ficou aberto e o que precisa de decisão humana.
> Fonte canônica de conclusão continua sendo `tasks/completed.md`; este arquivo é mapa, não verdade.

## 1. Quadro dos blocos

| Bloco | Estado | Onde |
|---|---|---|
| MA-01 · MA-02 · MA-03 · MA-04 | ✅ concluídos | `tasks/completed.md` |
| **MA-10** | ✅ concluído 2026-08-05 — veredito **ARQUIVAR** | PR #193 (merged) |
| **MA-08** | 🟡 **código pronto + migração executada**, PR **aberto** | `VinhoAbencoado/GymScraping` PR **#6** |
| MA-02-FU1 | 🟡 **parcial** — item 1 e item 2-B feitos; item 2 diagnosticado, não corrigido; 6 menores abertos | PR #194 (merged) |
| MA-03-FU1 | ⬜ **não iniciado** (item 1 + 6 menores) | — |
| MA-04-FU1 | 🟡 **parcial** — item 1 feito; item 2 e 4 leves abertos | PR #194 (merged) |
| **MA-07** | ⬜ sem seção própria no backlog — **precisa ser criado** | decisão do MA-10 |
| MA-09 | ⬜ **destravado**: o insumo do D-A agora existe | gate humano pendente |
| MA-05 · MA-06 | ⬜ não iniciados | — |
| **NOVO — filtro de musculação** | ⬜ **sem bloco**; ver §4 | — |

## 2. A DEC foi renumerada: 023 → **024**

A decisão que autoriza o MA-08 é a **DEC-024**, não a 023. O número 023 foi ocupado pela
"Visão Executiva 2.0", criada em paralelo por outra sessão e mergeada antes. As referências no
`GymScraping` foram corrigidas em 2026-08-07 (commit `dbd8f71`). **Ao citar a autorização da nota
in-app, usar DEC-024.**

## 3. MA-08 — o que foi entregue

**Código** (PR #6, aberto): parser do `partnerRating`, `FIELDNAMES` de 10 → 12 colunas
(`nota_wellhub`, `qtd_avaliacoes_wellhub`, antes de `data_coleta`), 3 estados distinguíveis, suíte
83 → **93** testes, 100% offline.

**Correção de um crítico que o próprio bloco criava:** com `FIELDNAMES` em 12 e o consolidado
versionado em 10, `append_rows` gravaria 12 campos sob o cabeçalho antigo — sem erro, sem log — e o
`DictReader` seguinte devolveria a **nota dentro de `data_coleta`**, propagando pelo `split_by_state`
para os 27 CSVs por UF. `ensure_header` passou a comparar o cabeçalho em disco com `FIELDNAMES` e
**falhar alto**.

**Migração EXECUTADA** (2026-08-05 19:47 → 2026-08-06 15:50, ~20 h):

| | maio | agora |
|---|---|---|
| linhas | 12.769 | **45.527** |
| com nota | — | 36.940 (81,1%) |
| sem avaliações | — | 8.587 (18,9%) |
| **não lidas** | — | **0** |
| falhas | 175 (0,4%) | 158 (**0,35%**) |

Zero não-lidas em 45.527 é a prova de produção da regex e da distinção
"sem avaliações" × "parser quebrou".

## 4. ⚠️ O que está ABERTO e precisa de decisão

### 4.1 Filtro de musculação quebrado (sem bloco ainda)

O WellHub **renomeou a taxonomia de atividades** entre maio e agosto: "Musculação" virou
**"Fisiculturismo" / "Treino de força" / "Treino Híbrido"**. `tem_musculacao`
(`Wellhub/split_by_state.py`) procura a substring `"musculacao"` e não reconhece os rótulos novos.

Medido: dos 7.577 descartados na primeira tentativa de coleta, **2.994 (39,5%) constavam no
consolidado de maio**. Na rodada completa, `45.382 de 45.527 linhas excluídas pelo filtro`.

**Consequência viva:** `Wellhub/csvs_musculacao/` tem **144 linhas** contra 12.769 em maio e **não
substitui a base anterior**. `Wellhub/csvs/` (45.526 linhas) está íntegro mas **mudou de
significado** — contém todas as unidades, não só academias de musculação. Isso importa porque
`demanda_revelada/concorrentes_densos.py` e `vulnerabilidade/snapshots.py` leem
`concorrentes/wellhub/csvs` (a cópia sincronizada no repo do motor).

Atualizar `tem_musculacao` é mudança de **critério de negócio** e não foi feita. Um bloco novo
precisa decidir entre: (a) ampliar o vocabulário do filtro; (b) manter o consolidado completo e
mover o recorte para o consumidor; (c) aceitar a base sem filtro.

### 4.2 Vazamento transitivo de import (MA-02-FU1, item 2)

`import motor_expansao.vulnerabilidade` carrega `sklearn`, `scipy`, `shapely`, `requests` e módulos
de `dashboard/`. **A causa medida não é a que o backlog supunha:** não é o import específico de
`classificar_rede` — o `__init__.py` de `demanda_revelada` reexporta os **9** submódulos de forma
eager, e **qualquer um dos 9** puxa o conjunto inteiro. Não há import "leve" a escolher.

Entregue: docstring corrigido + teste `test_pacote_nao_carrega_dependencia_pesada` marcado
**`xfail(strict=True)`** — quando a correção entrar, ele passa e o `strict` avisa para remover a
marca. **Segue bloqueante para o MA-06** (plug no cron).

### 4.3 Correção de texto pendente no backlog

O item 2-B do MA-02-FU1 afirma que a checagem por AST pegava **3/5** das formas de import proibido.
Medido em 2026-08-05: eram **2/5**. Já corrigido no código (agora 5/5), mas o texto do bloco não.

## 5. MA-09 — o gate está destravado

O pré-requisito do **D-A** (régua do `v2`) era "re-medir a distribuição restrita a `independente`".
Isso existe agora, do consolidado novo, recorte `independente` (**n = 34.035**):

```
min=1.0   p1=4.23   p5=4.59   p10=4.69   mediana=4.93   max=5.0   desvio=0.192
abaixo de 4,0: 158 (0,46%)     abaixo de 4,5: 947 (2,78%)
```

**A sonda de julho enganava.** Com N=53 ela mediu faixa `4,26–4,98`, mediana 4,79, desvio 0,127 —
**não via a cauda inferior**. O backlog alertava para não fixar o limite inferior da régua em 4,0,
"que satura justamente a ponta vulnerável"; o custo está medido: **158 unidades**, e são as de nota
mais baixa, ou seja, os alvos de M&A mais interessantes.

**Insumo para o D-B:** o MA-10 confirmou que o TotalPass **não tem nota como produto**, então a
régua assimétrica por fonte é **permanente**, não transitória. Isso reforça a opção **(0)** já
preferida no backlog — propagar o rating como coluna-fato **sem peso** —, que dissolve D-A e D-C.

**Lembrete de escopo:** hoje `_COLUNAS_TRABALHO` (`snapshots.py`) tem 14 colunas e **nenhuma** é
`nota_wellhub` — o materializador **dropa a coluna nova em silêncio**. E `SINAIS_INATIVOS = ("s2",)`.
São os 2 primeiros dos 12 pontos do MA-09.

## 6. PRs

| PR | Repo | Estado |
|---|---|---|
| **#6** | GymScraping | **ABERTO** — MA-08 (3 commits) |
| #188 | motor | merged (virou DEC-024) |
| #193 | motor | merged (MA-10) |
| #194 | motor | merged (lote parcial FU1) |
| #189 | motor | **CLOSED sem merge** — atualização do grafo foi rejeitada |

## 7. Onde estão os artefatos da coleta

- Consolidado novo: `GymScraping/Wellhub/unidades_wellhub.csv` (45.527 linhas, 12 colunas)
- Backup do antigo: `Wellhub/unidades_wellhub_10col_backup.csv` (12.769 linhas, 10 colunas)
- Runbook + resultado medido: `Wellhub/MIGRACAO_NOTA.md`
- Scripts da rodada e logs: `%LOCALAPPDATA%\ultra-migracao-wellhub\`
  (`retomar_wellhub_12col.ps1`, `inspecionar.ps1`, `validar.py`, `coleta_*.log`)
- A tarefa agendada `UltraWellhubMigracao12Col` segue **registrada e ociosa** (`Ready`); pode ser
  removida com `Unregister-ScheduledTask` quando não for mais útil.

## 8. Dado de rede observado de carona

**2,7% das unidades de maio sumiram** da rede WellHub em dois meses (349 de 12.769) — churn real,
que é o tipo de sinal que a camada de vulnerabilidade quer medir e que hoje ela só consegue estimar
com série longa.
