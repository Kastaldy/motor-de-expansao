# Handoff — Block Orchestrator → Planner

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco
BLK-DIM-22 — UI: exportar simulador de viabilidade como Excel

## Criticidade
**Média** — novo entregável UI; READ-ONLY sobre M1. Esteira: BO → Planner → [REVISÃO HUMANA] → Builder → QA.

---

## Contexto do bloco

### Por que existe
O operador precisa levar o resultado do simulador de viabilidade para reuniões/decisões fora do dashboard. Felipe quer o export no template padrão Ultra (cores turquesa/branco/cinza-escuro), equivalente ao "ULTRA padrão - Simulador Financeiro.xlsx" mas preenchido automaticamente com os dados do ponto analisado.

### Dependências confirmadas (todas em completed.md em 2026-06-22)
- **BLK-DIM-19**: flag de viável e payback real corretos (`flag_viavel`, `payback_meses` sem "Nunca")
- **BLK-DIM-20**: parâmetros de fluxo de caixa editáveis (capex parcelado — equipamentos e tecnologia)
- **BLK-DIM-21**: `gerar_serie_mensal()` disponível em `simulador.py` (retorna `list[dict]` com 60 elementos: `mes/alunos_balcao/faturamento_mensal/ebitda_mensal/fcf_acumulado`)

### Estado da suite (pós-BLK-DIM-21, QA aprovado)
`1046 passed, 4 skipped, 18 warnings` — baseline para este ciclo.

---

## Escopo do BLK-DIM-22

### Novo arquivo
`src/motor_expansao/dimensionamento/excel_export.py`

Função principal:
```python
def gerar_excel_viabilidade(result: ViabilidadePontoResult, *, nome_ponto: str = "") -> bytes:
```

4 abas com `openpyxl`:

1. **"Resumo"**: cabeçalho com nome Ultra (texto), ponto analisado (lat/lng/m²/aluguel/demanda), KPIs (break-even, aluguel-teto, margem EBITDA, payback, ROIC, faturamento, EBITDA, flag viável). Fundo de cabeçalho turquesa `#00BFB3`, texto branco; linhas de dado em branco/cinza-claro alternados.

2. **"DRE"**: tabela linha-a-linha do DRE no steady-state (faturamento bruto → deduções → receita líquida → impostos → custos variáveis → custos fixos → EBITDA → IR/CSLL → lucro líquido). Formatação monetária `R$ #.##0,00`. Fonte dos valores: campos do `ViabilidadeResult`.

3. **"Sensibilidade"**: grade alunos × aluguel com `margem_liq` — células coloridas (verde ≥ 10%, amarelo 0–10%, vermelho negativo). Reproduz a tabela já exibida no dashboard.

4. **"Curva"**: série mensal meses 1–60 com colunas `Mês`, `Alunos Balcão`, `Faturamento`, `EBITDA`, `FCF Acumulado`. Dados de `gerar_serie_mensal()` (BLK-DIM-21). Se a série não estiver disponível, omitir a aba com nota.

Retorna `bytes` via `BytesIO` — **NUNCA** escreve em disco no servidor (anti-PII/LGPD).

### Alteração em arquivo existente
`src/motor_expansao/dashboard/pages.py` — após os gráficos da seção de viabilidade:
```python
st.download_button(
    "⬇ Exportar Excel",
    data=excel_bytes,
    file_name=f"viabilidade_{lat:.4f}_{lng:.4f}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
```
Import lazy de `gerar_excel_viabilidade` (evitar import desnecessário se o usuário não estiver na aba de viabilidade).

### Testes
`tests/` — ao menos 1 teste de smoke: `len(gerar_excel_viabilidade(result)) > 0`; sugerido também: verificar que as 4 abas estão presentes (`wb.sheetnames`); verificar que a aba "Sensibilidade" tem os valores corretos; verificar que `BytesIO` é usado (sem escrita em disco).

---

## Fora de escopo (invioláveis)
- `config.py` raiz (M1) — ZERO toque
- `dimensionamento/config.py` — ZERO toque
- Score/pesos/artefatos M1 — ZERO
- Escrever em disco no servidor (`to_excel(path)` proibido — usar `BytesIO`)
- PII de alunos reais
- Dependência de API ao vivo no dashboard

---

## Arquivos prováveis
- `src/motor_expansao/dimensionamento/excel_export.py` (NOVO)
- `src/motor_expansao/dashboard/pages.py` (adicionar botão de download)
- `tests/dimensionamento/test_excel_export.py` ou `tests/test_excel_export.py` (NOVO ou extensão de existente)

---

## Riscos e mitigações
- **openpyxl já disponível** (`openpyxl>=3.1.0` em `pyproject.toml`) — sem dep nova
- **Risco de formatação complexa** (colorir células condicional na aba Sensibilidade): mitigação — começar com formatação simples e refinar após validação visual de Felipe; o critério de aceite é funcional (abrível + valores corretos), não estético no QA automático
- **BytesIO obrigatório**: garantir que não há nenhum `to_excel(path_str)` no código gerado

---

## Critérios de aceite
1. Download gera arquivo `.xlsx` válido abrível no Excel/LibreOffice
2. 4 abas presentes: Resumo, DRE, Sensibilidade, Curva
3. Cores Ultra aplicadas no cabeçalho (turquesa `#00BFB3`)
4. Valor da grade de sensibilidade idêntico ao exibido no dashboard
5. Suite verde (`pytest -q`)
6. Lint limpo (`ruff check .`)
7. Mypy limpo nos arquivos tocados
8. ZERO escrita em artefatos M1; ZERO disco no servidor

---

## Guardrails do loop
Este bloco é **loop-safe**: READ-ONLY sobre M1; toca só `pages.py` + novo módulo `dimensionamento/excel_export.py`; usa `openpyxl` já dep; sem VPS/deploy/segredos/PII/ingestão ao vivo. O `loop_guard.py` não deve disparar.
