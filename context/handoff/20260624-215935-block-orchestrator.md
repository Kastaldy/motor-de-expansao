# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

---

## Bloco refinado

**BLK-TP-01 — Ingestão e contrato da camada de Demanda Revelada (H3, sem PII)**

Criação de um pipeline de ingestão que consome dados de demanda paga (membros) já agregados
externamente, descarta qualquer identificador ou coordenada individual na fronteira de entrada,
e materializa `data/staging/demanda_revelada_h3.parquet` — casável por `hex_id` (H3 res-7)
com `hexagonos_mercado_mapeado.parquet`. Nova camada PARALELA, READ-ONLY sobre o M1.

---

## Objetivo

Materializar `data/staging/demanda_revelada_h3.parquet` a partir de dados de demanda já
agregados, com anti-PII por construção, conforme o contrato de colunas proposto no backlog
(BLK-TP-01), de modo a destravar os blocos de análise sucessores (BLK-TP-02..05).

---

## Escopo permitido

- Novo módulo/pasta `src/motor_expansao/demanda_revelada/` (disjunto de todos os módulos
  existentes; nenhuma importação de dentro de `pipelines/m1/`, `censo_*`, `dashboard/`).
- Pipeline de ingestão: parser de formato de entrada → agregação em H3 res-7 → drop imediato
  de PII (identificadores, coordenadas individuais) → escrita de
  `data/staging/demanda_revelada_h3.parquet`.
- Contrato de saída (a confirmar/refinar no Planner): colunas `hex_id`, `membros`,
  `membros_gt5km_concorrente_lc`, `dist_concorrente_lc_min_m`, `n_celulas_agregadas`,
  `n_acad_parceiras`, `alunos_parceiras`, `n_concorrente_lc`, `versao_contrato`.
  Opcional: versão res-8 para leitura intraurbana fina (decisão do Planner).
- Dependências novas (se necessárias) declaradas **exclusivamente** em extra próprio do
  `pyproject.toml` (ex.: `[demanda]`), fora do extra base do Streamlit e do `[dev]`.
  A biblioteca `h3` já é dependência existente e deve ser reutilizada.
- Testes **exclusivamente com fixture sintética sem PII** (nunca dado real nos testes);
  cobrir: ausência de qualquer coluna PII no parquet de saída; join por `hex_id` com o
  dataset de mercado; reprodutibilidade (mesma entrada → mesmo parquet).
- Relatório de qualidade/cobertura (Markdown, gitignored ou em `data/reports/`): distribuição
  de hexes cobertos, concentração geográfica, caveats de dado documentados (ver lista abaixo).
- Registro de **DEC-012** (adoção da camada de Demanda Revelada): redigir texto da DEC para
  aprovação humana no gate; a DEC DEVE ser aprovada pelo humano antes do Builder executar
  qualquer escrita em staging.

---

## Fora de escopo

- Qualquer alteração em `score_priorizacao`, `hex_score_estrutural`, pesos do M1, carteira,
  plano de curto prazo, plano de domínio ou artefatos oficiais (`brasil_estrutural.parquet`,
  `brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet`,
  `hexagonos_brasil_dashboard.parquet`, `hexagonos_mapa_sample.parquet`,
  `top_oportunidades_resumo.csv`, `resumo_por_uf.csv`).
- Persistir qualquer identificador individual, nome de pessoa, CPF, e-mail, telefone,
  coordenada individual de membro ou qualquer dado pessoal (PII) em arquivo, log ou cache.
- Leitura de dados individuais (dados brutos de membros individuais) fora do pré-processamento
  de ingestão; o pipeline só enxerga o dado já pré-agregado na fronteira de entrada.
- Ingestão ao vivo na carga do dashboard: o parquet de staging é gerado offline; o dashboard
  o lê passivamente se/quando exposto (BLK-TP-02..05 decidirão a exposição).
- Deploy ao VPS, alteração de Dockerfile, docker-compose, CI ou `config.py`.
- Alteração de `censo_report.py`, `censo_map.py`, `censo_point.py`, `streamlit_app.py`,
  `pages.py`, `components.py` ou qualquer módulo de dashboard existente.
- As análises em si: correlação demanda × residual (BLK-TP-02), vazio competitivo (BLK-TP-03),
  layer de demanda no dashboard (BLK-TP-04), dimensionamento + DIM (BLK-TP-05).
- Configuração de API ao vivo, scraping ou qualquer fetch em runtime durante carga do dashboard.

---

## Arquivos que devem ser lidos

- `CLAUDE.md` (§1, §2, §4, §5, §8/DEC-001/DEC-009) — fonte canônica de guardrails
- `tasks/backlog.md` linhas ~916–989 — especificação canônica do BLK-TP-01 e Epic BLK-TP
- `tasks/current_task.md` — estado atual do ciclo, paths pré-sujos
- `src/motor_expansao/__init__.py` e estrutura de `src/motor_expansao/` — para evitar colisão
  de nomes de módulo
- `pyproject.toml` — para declarar extras novos corretamente e verificar que `h3` já existe
- `data/staging/hexagonos_mercado_mapeado.parquet` — schema de colunas para confirmar que
  `hex_id` é a chave de join (leitura do schema apenas, sem carregar o dataset completo)
- `docs/modelo_mercado_hexagonos.md` — contrato da camada de mercado para garantir que o join
  é compatível
- `.gitignore` — confirmar que `*.parquet` em `data/staging/` já é gitignored
- `config.py` — LEITURA APENAS; confirmar `H3_RESOLUTION = 7` (chave de join); NÃO alterar

---

## Arquivos que podem ser alterados

- `src/motor_expansao/demanda_revelada/` — pasta NOVA; todos os arquivos dentro são novos
  (ex.: `__init__.py`, `ingestao.py`, `contrato.py`)
- `pyproject.toml` — SOMENTE para adicionar extra `[demanda]` com dependências novas
- `tests/unit/test_demanda_revelada_ingestao.py` — arquivo de teste NOVO
- `data/staging/demanda_revelada_h3.parquet` — artefato de saída (gitignored por padrão)
- `data/reports/demanda_revelada_qualidade.md` — relatório de qualidade (gitignored ou versionado
  conforme decisão do Planner; NÃO é artefato M1)
- `context/handoff.md` — atualizado a cada transição de Skill
- `context/handoff/AAAAMMDD-HHMMSS-<slug>.md` — snapshot append-only
- `tasks/current_task.md` — atualizado a cada transição de Skill
- `CLAUDE.md` §8 — SOMENTE para registrar DEC-012 (após aprovação humana no gate)
- `tasks/backlog.md` — SOMENTE o heading `### BLK-TP-01` se o housekeeping helper exigir

---

## Critérios de aceite

1. `data/staging/demanda_revelada_h3.parquet` existe e é legível via pandas/pyarrow.
2. O parquet contém as colunas do contrato (a confirmar no Planner): pelo menos `hex_id`,
   `membros`, `versao_contrato`; colunas opcionais presentes se implementadas.
3. **Zero** linha com dado individual/PII no parquet: verificado por teste automatizado
   (fixture sintética; o teste lista colunas proibidas e falha se qualquer uma existir).
4. Join `hex_id` com `hexagonos_mercado_mapeado.parquet` demonstrado por teste: pelo menos
   N hexes da fixture cruzam sem erro de tipo/formato.
5. `hex_id` em H3 resolução 7 (validado via `h3.get_resolution(hex_id) == 7` em fixture).
6. Pipeline é **reprodutível**: mesma entrada → mesmo parquet (sem side-effects de estado).
7. READ-ONLY sobre o M1: `grep -r "score_priorizacao\|hex_score_estrutural\|to_parquet" src/motor_expansao/demanda_revelada/` não aponta escrita em artefatos oficiais.
8. Suíte completa verde: `pytest -q` passa sem novos erros (contagem >= baseline anterior
   + novos testes do módulo).
9. `ruff check .` → zero erros.
10. `mypy src/motor_expansao/demanda_revelada/` → zero erros (ou baseline justificado).
11. `import motor_expansao.demanda_revelada` não importa dependências do `[basemap]`, `[api]`,
    `[api_mvp]` nem do deploy base Streamlit fora do `pyproject.toml` base.
12. DEC-012 redigida pelo Planner, aprovada pelo humano no gate, e registrada em `CLAUDE.md` §8
    antes de qualquer escrita em staging pelo Builder.

---

## Criticidade classificada

**Alta**

**Justificativa:** engenharia de dados + anonimização/LGPD; cria nova camada paralela que
consome insumo externo com PII na origem; exige gate humano + DEC-012 antes da execução do
Builder. NÃO é Crítica porque é READ-ONLY sobre o M1 (não toca `score_priorizacao`, pesos,
`hex_score_estrutural`, carteira, plano nem artefatos oficiais do M1 — §5 guardrail). A
esteira Alta exige revisão humana obrigatória entre Planner e Builder.

---

## Esteira recomendada

```
Block Orchestrator (este handoff)
    → Planner (opus)        — detalha o plano técnico + redige texto da DEC-012
    → [REVISÃO HUMANA OBRIGATÓRIA — LGPD/anonimização + DEC-012]
        - Humano lê o plano do Planner
        - Humano aprova (ou rejeita/modifica) a DEC-012
        - Humano confirma que o contrato de colunas está correto
        - Humano confirma que o formato de entrada (dado já agregado) está disponível
        - Humano confirma o extra [demanda] do pyproject.toml
    → Builder (opus)        — implementa SOMENTE após aprovação humana
    → QA (opus 4.8)        — valida todos os critérios de aceite acima
```

---

## Riscos identificados

- **R1 — DEC-012 não aprovada:** o bloco inteiro depende de DEC-012 aprovada. Se o humano
  rejeitar a adoção da camada no gate, o Builder NÃO deve executar e o ciclo é abortado.
  DEC-012 ainda NÃO consta em CLAUDE.md §8 (apenas DEC-001..011 registradas).

- **R2 — Formato de entrada do dado externo não especificado:** o backlog menciona "dados já
  agregados" mas não detalha o formato do arquivo de entrada (CSV, JSON, Parquet, planilha?),
  encoding, colunas disponíveis, unidade de coordenada (lat/lng? geohash?). O Planner DEVE
  obter essa informação do humano no gate antes de o Builder codificar o parser.

- **R3 — Cobertura geográfica enviesada (SP):** a demanda cobre ~1% do universo de hexes do
  Motor, concentrada em SP. O Planner e o Builder devem garantir que o relatório de
  qualidade documente claramente essa limitação para evitar uso indevido da camada como
  substituta do M1/censitário.

- **R4 — Arredondamento de coordenada de célula (~1 km):** as coordenadas de célula na origem
  podem ter precisão de ~1 km, introduzindo ruído no join res-7. Não impede o bloco, mas
  deve ser documentado como caveat no relatório de qualidade e nos testes (a fixture pode
  incluir casos de borda de arredondamento).

- **R5 — Reutilização de `h3` para aggregação:** o pipeline deve usar `h3.latlng_to_cell` ou
  equivalente em res-7 para mapear coordenadas (se disponíveis) para `hex_id`. Se a entrada
  já vem pré-agregada por algum grid próprio (ex.: H3 de resolução diferente ou grid
  proprietário), o Planner precisa definir a estratégia de reprojeção/join para res-7.

- **R6 — Coluna `dist_concorrente_lc_min_m` requer concorrentes mapeados:** calcular a menor
  distância ao concorrente low-cost (Smart Fit) dentro do hex exige o dataset
  `concorrentes_mapeados.parquet`. O Planner deve verificar disponibilidade e schema desse
  dataset. Se indisponível, a coluna é opcional ou calculada em bloco sucessor.

- **R7 — Paths pré-sujos declarados:** `.gitignore (M)`, `CLAUDE.md (M)`, `tasks/backlog.md (M)`,
  `data/raw/ibge/malha_brasil.geojson (D)`, `data/raw/ibge/malha_uf_brasil.geojson (D)`,
  `scripts/backtest_smartfit_scores.py (??)`. O Builder NÃO deve incluir esses paths no
  commit do ciclo.

---

## Guardrails ativos

- **§2 — Regras operacionais:**
  - Não criar dependência de API ao vivo no dashboard de produção (ingestão é offline).
  - Toda mudança relevante entra com teste; nenhum PR deve subir com CI quebrado.
  - Staging sempre em Parquet.

- **§4 — Camadas paralelas:** a camada de Demanda Revelada é paralela ao M1 e NÃO pode
  alterar o M1 sem aprovação explícita. `pop_hex_base` e o modelo de mercado existente
  NÃO são alterados.

- **§5 — Guardrail permanente:** visualizações, análises e interações não podem recalcular
  ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano
  de domínio ou artefatos oficiais do M1 sem aprovação explícita.

- **§8/DEC-001:** pesos `renda=0.40`/`pop=0.60` e fórmula de `score_priorizacao` INALTERADOS.

- **§8/DEC-009:** a demanda entra como **insumo OBSERVADO**, NUNCA como preditor geográfico
  de magnitude. Proibido usar `membros` ou qualquer coluna da nova camada como input em
  regressão geográfica de demanda ou como ajuste do `score_priorizacao`.

- **Anti-PII por construção:** identificadores individuais, nomes, CPFs, e-mails, telefones,
  coordenadas individuais de membros jamais são lidos para staging nem persistidos.
  A agregação para H3 ocorre na **fronteira de entrada** do pipeline (dentro do módulo
  `demanda_revelada/`), não em staging intermediário com dados individuais.

- **DEC-012 obrigatória antes do Builder:** o gate humano do Planner deve cobrir a aprovação
  da DEC-012; sem aprovação explícita do humano, o Builder NÃO executa.
