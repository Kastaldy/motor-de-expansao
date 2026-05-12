# Motor de Expansao Ultra Academia - CLAUDE.md
> Fonte canonica curta do projeto. Ler antes de qualquer tarefa.
> Responsavel: Felipe Silva | Estrategia e Growth | Ultra Academia
> Versao: Abril 2026
> Regra de manutencao: manter curto; historico detalhado fica em `docs/` e `data/reports/`.

## 1. Norte
- O repo agora tem 2 trilhas simultaneas:
  - `M1 oficial territorial`: decide onde expandir no nivel executivo.
  - `mercado por hexagono`: camada paralela e experimental para ler demanda, oferta mapeada e restricao da rede Ultra.
- Perguntas centrais: onde expandir, quem ja atua ali, quais imoveis estao disponiveis e qual ponto tem maior chance de sucesso.
- Publico-alvo prioritario: 18-45 anos.
- `score_priorizacao` continua sendo o score oficial do projeto.
- Nenhuma trilha paralela pode alterar o M1 sem aprovacao explicita.
- **Decisao arquitetural (2026-04-24):** cada camada tem papel distinto e complementar:
  - Visao executiva (mapa): exibe hexagonos do **setor censitario** para granularidade geografica real (elimina agua/rural visualmente).
  - Carteira e recomendacao de expansao: usa **M1 (`score_priorizacao`)** como ranking oficial — validado com rho=0.42 (p=0.007) contra faturamento real das unidades Ultra.
  - Nunca substituir um pelo outro; papeis sao complementares, nao concorrentes.

## 2. Regras operacionais
- Ler o repositorio real antes de editar; este arquivo resume contexto, nao substitui o codigo.
- Tratar `config.py` e este arquivo como fontes canonicas de parametros e guardrails.
- Staging sempre em Parquet; para CSVs locais gerados pelo projeto usar `sep=";"` e `encoding="utf-8-sig"`.
- Excecao de legado confirmada no piloto: `data/ultra/Ultra.csv` usa `sep=";"`, `encoding="latin-1"` e 1 linha inicial de metadado antes do cabecalho.
- Ao tocar em camadas paralelas, preservar 100% das linhas e colunas oficiais do M1.
- Nao criar dependencia de API ao vivo no fechamento nacional nem no piloto de mercado.
- Toda mudanca relevante entra com teste; nenhum PR deve subir com CI quebrado.
- No piloto de mercado, `prioridade_mercado_mapeado` usa regua absoluta de `som_indice_mapeado`; quartis ficam apenas como apoio de ranking relativo em analises auxiliares.
- O guia operacional do ciclo ativo fica em `PRD.md`; o contrato tecnico detalhado da trilha de mercado fica em `docs/modelo_mercado_hexagonos.md`.

## 3. Nucleo oficial M1

### Parametros canonicos
```python
H3_RESOLUTION = 7
DIST_MIN_ULTRA_KM = 1.0
RENDA_MIN = 4500.0  # renda domiciliar minima (nao per capita)
AREA_MIN_M2 = 1200.0
AREA_IDEAL_MIN_M2 = 1500.0
AREA_IDEAL_MAX_M2 = 2000.0
PE_DIREITO_MIN = 3.5
M1_SCORE_OFICIAL = "score_priorizacao"
M1_PRIORIZACAO_TOP_PCT_POR_UF = 0.20
M1_OSM_ENABLED = False
M1_SETOR_CENSITARIO_OBRIGATORIO = False
M1_POP_MINIMA_PROXY = 1  # populacao minima para hexagono entrar no ranking (evita agua/rural)
```

### Fluxo oficial
1. `base_h3_brasil.py` -> `data/staging/brasil/uf=XX/hexagonos.parquet`
2. `hex_enrichment.py` -> `data/staging/brasil_estrutural.parquet`, `data/staging/brasil_priorizados.parquet`, `data/staging/hexagonos_brasil_oportunidades.parquet`
3. `fase1_bi_exports.py` -> artefatos executivos e BI estaveis

### Regras oficiais
- Fonte oficial do M1: IBGE.
- Fallback padrao: atribuicao municipal IBGE + SIDRA com rastreabilidade explicita quando setor censitario nao estiver disponivel.
- OSM nao e dependencia operacional do fechamento nacional; nos outputs oficiais `osm_status` deve ser `nao_aplicado_mvp_nacional`.
- Inputs oficiais do score: `renda_per_capita`, `populacao_proxy`, `pop_18_45` como preferencia e `pop_total` como fallback.

```python
renda_pct_nacional = percentil_nacional(renda_per_capita)
pop_pct_nacional = percentil_nacional(populacao_proxy)
hex_score_estrutural = 100 * (0.40 * renda_pct_nacional + 0.60 * pop_pct_nacional)
score_priorizacao = clip(hex_score_estrutural + ajuste_executivo, 0, 100)
score_oficial = score_priorizacao
```
- ATENCAO: artefatos Parquet existentes (`brasil_estrutural.parquet`, `brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet`) foram gerados com os pesos antigos (renda=0.60, pop=0.40). Re-executar `hex_enrichment.py` para refletir os novos pesos (renda=0.40, pop=0.60; aprovado diretoria 2026-04-24).

- Campos auditaveis minimos: `renda_pct_nacional`, `pop_pct_nacional`, `hex_score_estrutural`, `ajuste_executivo`, `score_priorizacao`, `score_oficial`, `score_oficial_nome`, `score_percentil_nacional`.
- Artefatos oficiais: `brasil_estrutural.parquet`, `brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet`, `hexagonos_brasil_dashboard.parquet`, `hexagonos_mapa_sample.parquet`, `top_oportunidades_resumo.csv`, `resumo_por_uf.csv`.
- Suite principal do fechamento M1: `test_base_h3_brasil.py`, `test_hex_enrichment_brasil.py`, `test_fase1_bi_exports.py`, `test_fontes_gratuitas.py`.

## 4. Camadas paralelas e estado atual
- `M1.1` e paralelo ao M1. Nao altera `score_priorizacao`, `hex_score_estrutural` nem artefatos oficiais.
- Fase A do Censo 2022 foi validada como camada experimental; continua `NO-GO` para substituir o score oficial nacional.
- Validacao com unidades reais da Ultra manteve o M1 como modelo vencedor para ranking oficial; o censitario serve como camada editorial/local.
- Modelo hibrido:
  - regra: M1 aprova municipios; censitario ranqueia hexes dentro dos municipios aprovados;
  - score operacional: `score_expansao_hibrido`;
  - semantica: preserva `score_priorizacao` como base e adiciona bonus local minimo de desempate; por isso pode passar marginalmente de `100` sem virar novo score oficial;
  - piso operacional intraurbano: exigir densidade setorial minima de `5.000 hab/km2` para elegibilidade censitaria;
  - cobertura do censitario: 27 UFs; core `DF`, `GO`, `MG`, `RJ`, `RS`, `SP`; piloto expandido; nacional `data/staging/censo2022_setores_calibrado_nacional_completo.parquet` (21 UFs, 1.251.771 linhas, k_global=1.0213, gerado 2026-04-23);
  - UFs com `qualidade_join_uf=C` (filtradas automaticamente): AM, RR (supressao IBGE), AL, AP, CE, MA, PA, PB, PE, RO, SE (gates);
  - `modelo_hibrido_expansao.py` consome os 3 parquets; deduplicacao core > expandido > nacional por `hex_id`; hexes elegiveis: 222.619; municipios top M1 com camada local: 852;
  - `qualidade_join_uf`: A/B se todos os gates passam, C se qualquer gate falha (filtrado pelo hibrido);
  - status: `GO` para **visualizacao executiva** (mapa exibe hexagonos do setor censitario — granularidade geografica real, elimina agua/rural); M1 continua como **fonte oficial de ranking de carteira** (rho=0.42 vs faturamento real); `NO-GO` para substituir o M1 no ranking.
- Dashboard local agora separa explicitamente os papeis: mapa executivo usa geometria granular quando `qualidade_join_uf` e `A/B`, fallback municipal nas UFs `C` e renderiza todos os hexagonos validos da UF selecionada sem cap editorial; aba de carteira volta a ordenar por `rank_brasil`/`score_priorizacao` do M1 e deixa Censitario/Hibrido apenas como apoio local.
- Camada de mercado por hexagono:
  - status: ciclo anterior de mercado fechado ate o Bloco 3; staging materializado, carteira/plano nacionais regenerados e validacao integrada concluida para handoff;
  - objetivo: combinar demanda, oferta mapeada e restricao da rede propria Ultra;
  - artefatos acionaveis atuais:
    - `data/outputs/carteira_expansao_acionavel.parquet`: 5.406 linhas, 27 UFs, 1.093 municipios, 0 `hex_id` duplicado;
    - `data/outputs/plano_expansao_curto_prazo.parquet`: 269 linhas, 27 UFs, 66 municipios, 0 `hex_id` duplicado;
  - regra operacional nova: se o municipio top M1 tiver `top_hex_intraurbano=True`, a carteira usa somente os hexes granulares; se nao tiver, entra fallback municipal/M1 sem excluir a UF do output;
  - insumos ja disponiveis:
    - `concorrentes/*.csv`
    - `data/ultra/Ultra.csv`
    - `data/outputs/oportunidades_expansao_hibrido.parquet`
    - `data/staging/brasil_estrutural.parquet`
    - `data/staging/censo2022_setores_calibrado.parquet`

## 5. Ciclo ativo
- Ciclo atual do `PRD.md`: handoff do repositorio e deploy Streamlit em VPS.
- Objetivo: compartilhar codigo/docs/testes com a equipe e servir o dashboard com Parquets locais.
- Deploy inicial: somente Streamlit via `Dockerfile.streamlit`/`docker-compose.prod.yml`; API/FastAPI, PostGIS, Prefect e pipelines pesados ficam fora.
- Artefatos minimos do dashboard em `data/outputs/`: `hexagonos_brasil_dashboard.parquet`, `oportunidades_expansao_hibrido.parquet`, `carteira_expansao_acionavel.parquet`, `plano_expansao_curto_prazo.parquet`.
- Contrato de handoff: `docs/handoff_repositorio.md`.
- Guardrails permanentes: nao alterar `score_priorizacao`, `hex_score_estrutural` nem artefatos oficiais do M1 sem aprovacao explicita; dashboard de producao roda offline com dados locais e Parquet.

## 6. Onde aprofundar
- `PRD.md`: guia operacional em blocos do ciclo ativo.
- `docs/modelo_mercado_hexagonos.md`: contrato tecnico de colunas e calculos.
- `docs/m1_outputs_oficiais.md`: contrato curto dos outputs do M1.
- `docs/m1_1_arquitetura_enriquecimento.md`: design da camada M1.1.
- `docs/streamlit_dashboard_m1.md`: governanca e uso do dashboard.
- `data/reports/validacao_modelo_ultra.md`: aderencia com dados reais das unidades Ultra.
- `data/reports/modelo_hibrido_expansao.md`: regra e cobertura do modelo hibrido.

Se um detalhe historico nao estiver aqui, procurar primeiro nesses docs antes de expandir novamente este arquivo.
