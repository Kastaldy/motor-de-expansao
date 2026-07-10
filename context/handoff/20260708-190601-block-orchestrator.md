# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco
BLK-VIAB-06 — Guardrail de envelope de metragem no motor de viabilidade

## Criticidade confirmada
Média

## Escopo confirmado (READ-ONLY M1)
O que NÃO será tocado:
- `config.py` — nenhum parâmetro canônico do §3 alterado
- `src/motor_expansao/pipelines/m1/` — pipeline M1 intocado
- Artefatos oficiais: `brasil_estrutural.parquet`, `brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet`, etc.
- `score_priorizacao`, `hex_score_estrutural`, pesos `renda=0.40`/`pop=0.60`
- Carteira, plano curto prazo, plano domínio
- VPS / rede / PII — zero acesso externo

## Arquivos-alvo
- **Principal:** `/repo/src/motor_expansao/dimensionamento/viabilidade_ponto.py`
- **Testes (regressão):** `/repo/tests/unit/dimensionamento/test_viabilidade_ponto.py`
- **Testes de referência (não alterar):**
  - `/repo/tests/unit/dimensionamento/test_batch_viabilidade.py` (BLK-VIAB-03)
  - `/repo/tests/unit/dimensionamento/test_backtest_viabilidade.py` (BLK-VIAB-04)

## Análise

### O que precisa mudar em `viabilidade_ponto.py`

**1. Novas constantes de módulo** (após a constante `SHARE_BALCAO_DEFAULT`, antes do dataclass):
```python
# --- Guardrail de envelope de metragem (BLK-VIAB-06) -------------------------
ENVELOPE_MIN: float = 600.0   # m2 mínimo da base de calibração Ultra (636 m2 - folga)
ENVELOPE_MAX: float = 3000.0  # m2 máximo (base calibrada até 2800 m2 + folga; MAPE 85% além)
```

**2. Campo novo no dataclass `ViabilidadePontoResult`** (após `demanda_fonte`):
```python
# --- Guardrail de envelope de metragem (BLK-VIAB-06) ---
flag_fora_envelope: bool = False
```
Tipo: `bool` com default `False` (não quebra instanciações existentes por ser campo com default após campos com default — verificar posição no dataclass; todos os campos sem default vêm antes).

**3. Cálculo da flag no orquestrador `analisar_viabilidade_ponto`** (após o passo 2 "Flag de zona morta", antes do passo 3 "Faixa de alunos"):
```python
# 2b. Flag de envelope de metragem (BLK-VIAB-06).
flag_envelope = not (ENVELOPE_MIN <= m2 <= ENVELOPE_MAX)
```

**4. Passar a flag na construção do `ViabilidadePontoResult`** no passo 7 "Montar resultado":
```python
flag_fora_envelope=flag_envelope,
```

**5. Exportar no `__all__`** (adicionar):
```python
"ENVELOPE_MIN",
"ENVELOPE_MAX",
```

### Estado atual vs. esperado

| Item | Atual | Esperado (BLK-VIAB-06) |
|---|---|---|
| `flag_fora_envelope` no dataclass | Ausente | `bool = False` |
| Constantes `ENVELOPE_MIN`/`MAX` | Ausentes | `600.0` / `3000.0` |
| Cálculo no orquestrador | Ausente | `not (600 <= m2 <= 3000)` |
| `__all__` | Sem as constantes | Com `ENVELOPE_MIN`/`ENVELOPE_MAX` |
| Comportamento para m2 dentro do envelope | — | Byte-idêntico ao atual (`flag_fora_envelope=False`) |
| Comportamento para m2 fora do envelope | Silencioso | `flag_fora_envelope=True`; DRE/faixa/grade inalterados |

### Regras de negócio (pré-fixadas no backlog)
- Envelope = **[600, 3000] m²** (inclusivo em ambos os extremos, espelhando o padrão de `flag_zona_morta` já no código que usa `<` para disparar).
- **Só FLAG, NÃO recusa**: a função não rejeita o cálculo nem altera DRE/faixa/grade — apenas adiciona o campo informativo.
- Comportamento existente **byte-idêntico** exceto a flag nova.
- A **UI** (BLK-VIAB-09 futuro) decide o que exibir/bloquear com base na flag.

### Posição do campo no dataclass
O dataclass tem campos com default (`alunos_balcao_premissa`, `alunos_agregadores_premissa`, `alunos_para_margem_alvo`, `demanda_fonte`) e campos sem default (os primeiros). O novo campo `flag_fora_envelope: bool = False` deve ser adicionado **após** `demanda_fonte: str = DEMANDA_FONTE_PREMISSA` para não quebrar a ordem Python (campos sem default antes de campos com default).

## Testes existentes relevantes

### Testes de regressão (NÃO devem quebrar):
- `test_analisar_viabilidade_ponto_completo` — chama o orquestrador com m2=1500 (dentro do envelope) → deve continuar passando; agora `r.flag_fora_envelope` será `False`
- `test_sem_staging_real` — m2=1500, deve passar com `flag_fora_envelope=False`
- `test_faixa_usa_curva_densidade_nao_geo` — m2=1500 em dois pontos geo distintos; flag deve ser igual (False) em ambos
- `test_demanda_fonte_sempre_premissa_explicita` — m2=1500; sem impacto na demanda_fonte
- `test_breakeven_menor_que_alunos_para_margem_alvo` — m2=1500; inalterado
- `test_breakeven_resulta_ebitda_zero` — m2=1500; inalterado
- `test_split_corrige_superestimacao_receita` — m2=1500; inalterado
- `test_anti_double_count_agregadores_escalam` — m2=1500; inalterado
- `test_grade_aplica_split_internamente` — m2=1500; inalterado
- `test_share_balcao_default_aplicado` — m2=1500; inalterado
- `test_alunos_para_margem_alvo_campo_presente` — m2=1500; inalterado
- `test_aluguel_teto_considera_agregadores_materiais` — testa `aluguel_teto` direto (não orquestrador); inalterado
- `test_aluguel_teto_sem_agregadores_nao_regride` — idem; inalterado
- `test_flag_zona_morta_*` (4 testes) — testam `flag_zona_morta` diretamente; inalterados
- `test_faixa_alunos_*` (2 testes) — testam `faixa_alunos_por_densidade` diretamente; inalterados
- `test_grade_sensibilidade_*` (2 testes) — testam `grade_sensibilidade` diretamente; inalterados

### Novos testes a criar em `test_viabilidade_ponto.py`:
```
# BLK-VIAB-06 — Guardrail de envelope de metragem
test_flag_fora_envelope_acima_do_max    # m2=3001  → flag_fora_envelope=True
test_flag_fora_envelope_abaixo_do_min   # m2=599   → flag_fora_envelope=True
test_flag_fora_envelope_no_limite_max   # m2=3000  → flag_fora_envelope=False (inclusivo)
test_flag_fora_envelope_no_limite_min   # m2=600   → flag_fora_envelope=False (inclusivo)
test_flag_dentro_envelope_nao_altera_dre # m2=3001 vs m2=1500 → viabilidade.margem_ebitda_pct igual (DRE inalterado)
```

### Arquivos de backtest referenciados no critério de aceite do bloco:
- `test_backtest_viabilidade.py` (BLK-VIAB-04) — não toca viabilidade_ponto diretamente; verificar regressão
- `test_batch_viabilidade.py` (BLK-VIAB-03) — usa `analisar_viabilidade_ponto`; verificar que novos campos não quebram

## Riscos / alertas

1. **Posição do campo no dataclass**: Python exige campos com default após os sem default. O novo `flag_fora_envelope: bool = False` deve ser colocado **após** todos os campos com default já existentes. Se colocado antes de um campo sem default ocorre `TypeError` em runtime. Verificar antes de gerar o diff.

2. **Semântica inclusiva do envelope**: o critério de aceite do bloco diz `m2 > 3000 → True` e `dentro → False`, o que implica que os limites exatos (600 e 3000) são **dentro** do envelope. A condição correta é `not (ENVELOPE_MIN <= m2 <= ENVELOPE_MAX)` — confirmar com o critério de aceite (`m2 > 3.000 → True`).

3. **`test_analisar_viabilidade_ponto_completo` não verifica `flag_fora_envelope`**: o teste existente não acessa o novo campo, portanto não quebrará. Mas o Builder deve adicionar `assert r.flag_fora_envelope is False` nele (ou em teste dedicado) para cobrir o caso normal.

4. **loop_guard.py**: a mudança só toca `dimensionamento/viabilidade_ponto.py` — fora do escopo guardado (`config.py`/`pipelines/m1`/`*scoring*`/artefatos M1/`deploy/`/Dockerfiles/compose/Caddy/authelia/`.env`/`secrets/`/CI). loop_guard deve passar limpo.

5. **`__all__` exporta as novas constantes**: garantir que `ENVELOPE_MIN` e `ENVELOPE_MAX` entrem no `__all__` para que os testes possam importá-las diretamente e verificar os valores.
