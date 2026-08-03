# PRD — Motor de Expansao Ultra Academia

> Versao: 2026-07-19 (rev. de reconciliacao; conteudo subordinado ao CLAUDE.md)
> Responsavel: Felipe Silva | Estrategia e Growth | Ultra Academia

## 0. Cabecalho e subordinacao ao CLAUDE.md

Este documento e o PRD (Product Requirements Document) do Motor de Expansao Ultra
Academia. Ele descreve a visao de produto, publico, escopo, camadas, requisitos,
metricas de sucesso, roadmap e restricoes.

Fonte de verdade: `CLAUDE.md`. Este PRD e SUBORDINADO ao `CLAUDE.md`; em qualquer
conflito, `CLAUDE.md` prevalece. Os parametros canonicos do projeto (score oficial,
pesos, parametros de filtragem, guardrails permanentes) vivem somente no `CLAUDE.md`
§3 e §5 e NAO sao redefinidos aqui — este PRD apenas os referencia, para evitar
deriva. O roadmap detalhado por bloco vive em `tasks/backlog.md` (pendentes) e
`tasks/completed.md` (historico), e NAO e copiado neste PRD.

Documentos de apoio referenciados ao longo deste PRD:

- `CLAUDE.md` — fonte canonica curta do projeto (parametros e guardrails).
- `tasks/backlog.md` — roadmap por bloco (escopo, criterios de aceite, dependencias).
- `tasks/completed.md` — historico de ciclos concluidos.
- `docs/streamlit_dashboard_m1.md` — governanca e uso do dashboard.
- `docs/modelo_mercado_hexagonos.md` — contrato tecnico de mercado/residual.
- `docs/m1_outputs_oficiais.md` — contrato curto dos outputs do M1.
- `docs/relatorio_pontual_censitario.md` — contrato do relatorio censitario.
- `docs/api_geoespacial_contrato.md` — contrato da API GeoEspacial on-demand (G1/BLK-API-01; DEC-005, CLAUDE.md §8); esboco em `docs/api_geoespacial_openapi.yaml`. So contrato; sem codigo de API.
- `docs/infra_producao.md` — manutencao e deploy.
- `docs/backup_restore.md` — backup e regeneracao (DR).
- `data/reports/perf_baseline_dashboard.md` — baseline de performance do dashboard.

## 1. Visao e objetivo do produto

O Motor de Expansao Ultra Academia responde, de forma defensavel, a quatro perguntas
centrais de expansao da rede: onde expandir, quem ja atua na regiao, qual mercado
residual existe e como ocupar regioes com uma sequencia controlada.

O produto e organizado em duas trilhas complementares (espelhando `CLAUDE.md` §1):

- M1 oficial territorial: decide onde expandir no nivel executivo — quais municipios
  e qual o ranking oficial de carteira.
- Mercado por hexagono: camada paralela para ler demanda, oferta mapeada, fitness
  residual e a restricao imposta pela propria rede Ultra.

O score oficial do projeto e o `score_priorizacao`. Ele e a referencia executiva para
priorizacao territorial. Nenhuma trilha paralela pode alterar o M1 sem aprovacao
explicita.

## 2. Publico-alvo e contextos de uso

Publico prioritario do negocio: faixa de 18 a 45 anos (contexto de produto, nao
parametro de score).

Usuarios e contextos de uso do produto:

- Estrategia e Growth: decisao executiva de carteira e priorizacao de municipios via
  ranking oficial M1.
- Analise territorial: leitura intraurbana refinada via camada censitaria e modelo
  hibrido.
- Operacao de mercado: leitura de mercado residual e Expansao de Dominio como apoio
  estrategico-operacional.

O consumo principal e feito por um dashboard que funciona offline, sem dependencia de
API ao vivo em producao.

## 3. Escopo do produto / fora de escopo

Dentro do escopo:

- Motor M1 oficial territorial (decisao de municipios e ranking de carteira).
- Camadas paralelas: censitaria, hibrida, mercado/residual e Expansao de Dominio.
- Dashboard offline com quatro abas (ver §6).
- Analises pontuais: Analise Pontual de Entorno (H3) e Relatorio Pontual Censitario
  1.0 km.
- Multi-hex (composicao de cenarios a partir de varios hexagonos).
- Backup e plano de regeneracao (DR) de segredos e dados.

Fora do escopo (espelhando `CLAUDE.md` §4):

- API/FastAPI ao vivo no dashboard de producao.
- PostGIS, Prefect, pipelines pesados ao vivo.
- M2/M3.
- Pesquisas e Power BI.

Estes itens estao explicitamente fora do deploy inicial.

> Nota (2026-07): a **API GeoEspacial existe como servico STANDALONE on-demand** (DEC-005; `api.ultra-expansao.tech`), fora do dashboard — o dashboard de producao segue **offline**, sem API ao vivo. A **Frente C (BLK-SCORE-\*) de validacao de score foi ENCERRADA pela DEC-009** (previsao de magnitude de demanda pela geografia = NO-GO honesto; pivo para viabilidade property-first).

## 4. Camadas e trilhas

Os papeis das camadas seguem `CLAUDE.md` §1 e §4 (sem redefinir valores numericos):

- M1 oficial territorial: decide municipios e o ranking oficial de carteira. E a
  camada de decisao executiva.
- Censitario e hibrido: refinam a leitura intraurbana. No modelo hibrido, o M1 aprova
  municipios e o censitario ranqueia hexagonos dentro dos municipios aprovados; o
  resultado hibrido e operacional.
- Mercado/residual e Expansao de Dominio: apoiam a estrategia operacional combinando
  demanda, oferta mapeada e a restricao da rede propria Ultra. NAO substituem o M1.

Guardrail de camadas: nenhuma trilha paralela altera o M1, a carteira, o plano ou os
artefatos oficiais sem aprovacao explicita do usuario. Ao tocar em camadas paralelas,
preservar 100% das linhas e colunas oficiais do M1.

## 5. Score oficial e guardrails (REFERENCIA — `CLAUDE.md` §3/§5)

O score oficial do projeto e o `score_priorizacao`. A formula do score, os pesos
(componentes de renda e populacao), os parametros canonicos de filtragem e dimensao
(`H3_RESOLUTION`, `DIST_MIN_ULTRA_KM`, `RENDA_MIN`, `AREA_MIN_M2`, `AREA_IDEAL_MIN_M2`,
`AREA_IDEAL_MAX_M2`, `PE_DIREITO_MIN`, `M1_PRIORIZACAO_TOP_PCT_POR_UF` e demais) e os
campos e artefatos oficiais minimos estao definidos em `CLAUDE.md` §3 (Nucleo oficial
M1).

Os valores canonicos vivem somente no `CLAUDE.md` §3; este PRD nao os duplica para
evitar deriva. Para o valor exato de qualquer parametro, pesos ou formula, consultar
`CLAUDE.md` §3; para a lista de campos minimos e artefatos oficiais, consultar tambem
`CLAUDE.md` §3 e `docs/m1_outputs_oficiais.md`.

Guardrail permanente (`CLAUDE.md` §5): visualizacoes, analise radial, interacoes de
mapa e qualquer camada paralela NAO podem recalcular ou alterar `score_priorizacao`,
`hex_score_estrutural`, a carteira, o plano de curto prazo, o plano de dominio ou os
artefatos oficiais do M1 sem aprovacao explicita do usuario. Pins e logos de
concorrentes e Ultra no dashboard sao camada visual de apoio e nao alteram score,
ranking, carteira nem artefatos oficiais.

## 6. Requisitos funcionais e nao-funcionais

### 6.1 Requisitos funcionais

- Dashboard com quatro abas: `Visao Executiva`, `Mapa Territorial`, `Expansao de
  Dominio` e `Carteira e Plano`.
- `Visao Executiva`: mapa Ultra-only, KPIs de rede e graficos de residual por UF e
  cidade.
- `Mapa Territorial`: leitura territorial com colorizacao por faixa de score, captura
  por clique (com centroide do hex como aproximacao) e fallback por coordenada na
  sidebar.
- `Expansao de Dominio` e `Carteira e Plano`: leitura operacional de dominio hibrido,
  carteira por M1 e plano de expansao.
- Analise Pontual de Entorno (H3): analise radial de entorno (raio descritivo de
  1.6 km como feature) que retorna populacao, renda, consumo de concorrentes e consumo
  Ultra no raio, sem mutar inputs nem recalcular o score.
- Relatorio Pontual Censitario 1.0 km: cruza setor censitario real (geometria IBGE
  2022) com circulo de raio fixo 1.0 km, com export de PDF/CSV em memoria e mapa
  censitario offline.
- Multi-hex: composicao de cenarios a partir de varios hexagonos, com hex_id copiavel
  e parsing flexivel de identificadores.

Detalhe funcional, governanca e uso do dashboard estao em
`docs/streamlit_dashboard_m1.md`; o contrato do relatorio censitario esta em
`docs/relatorio_pontual_censitario.md`.

### 6.2 Requisitos nao-funcionais

- Operacao offline: o dashboard funciona com Parquets locais em `data/outputs/`, SEM
  API ao vivo em producao.
- Performance: carga lazy por UF, render lazy das abas e fonte de mapa enxuta (ver
  `CLAUDE.md` §4 e `data/reports/perf_baseline_dashboard.md`).
- Staging sempre em Parquet; CSVs locais usam `sep=";"` e `encoding="utf-8-sig"`, com
  a excecao de legado de `data/ultra/Ultra.csv` (`sep=";"`, `encoding="latin-1"`, 1
  linha inicial de metadado), conforme `CLAUDE.md` §2.
- Qualidade: toda mudanca relevante entra com teste; nenhum PR sobe com CI quebrado
  (CI verde como gate). Baseline de testes em `CLAUDE.md` §5.
- Integridade do M1: ao tocar camadas paralelas, preservar 100% das linhas e colunas
  oficiais do M1.

## 7. Metricas de sucesso

- Aderencia do score ao desfecho real: validada pela trilha `BLK-SCORE-*` no backlog
  (dataset rotulado, poder preditivo e eventual recalibracao com DEC). Esse e o
  mecanismo formal de validacao do `score_priorizacao` contra resultado observado.
- Cobertura territorial: leitura consistente do territorio relevante (M1 nacional mais
  refino intraurbano onde a base geo existe).
- Suite de testes verde: a baseline de testes (`CLAUDE.md` §5) deve permanecer verde a
  cada ciclo.
- Dashboard utilizavel offline: o produto deve ser operavel sem dependencia de API ao
  vivo, com tempos de carga aceitaveis (referencia em
  `data/reports/perf_baseline_dashboard.md`).

Onde nao ha numero canonico no repositorio, a metrica e mantida qualitativa; este PRD
nao inventa metas numericas nao suportadas pelo projeto.

## 8. Roadmap e fases (REFERENCIA — `tasks/backlog.md`)

O roadmap e organizado por frentes, identificadas por prefixo de bloco. Uma linha de
intencao por frente:

- Frente A — `BLK-OPS-*`: robustez operacional (backup/DR, CI completo, manifesto de
  proveniencia, validacao de schema, hardening da orquestracao e sincronizacao de
  infra).
- Frente B — `BLK-ARCH-*`: arquitetura (concluir migracao para `src/` e remover
  legado, sem alterar comportamento de scoring).
- Frente C — `BLK-SCORE-*`: **(ENCERRADA — DEC-009)** validacao de scores contra desfecho real (dataset
  rotulado, poder preditivo e proposta de recalibracao com DEC).
- Produto — `BLK-PROD-*`: evolucoes de produto e performance (geocodificacao,
  relatorio concorrencial, cenarios salvos, manutencao e refatoracao).
- Orquestracao — `BLK-ORQ-*`: evolucao da propria esteira de ciclos.

Detalhe, escopo, criterios de aceite e mapa de dependencias de cada bloco vivem em
`tasks/backlog.md`. Os ciclos concluidos ficam registrados em `tasks/completed.md` e
resumidos em `CLAUDE.md` §5. Este PRD nao copia blocos do backlog.

## 9. Dependencias e restricoes (infra/VPS)

- Producao roda em VPS, com deploy baseado em checkout git (`git pull`) e Docker.
  Manutencao e deploy detalhados em `docs/infra_producao.md`.
- GUARDRAIL ABSOLUTO (`CLAUDE.md` §6): nunca executar qualquer comando no servidor via
  qualquer tool SSH sem confirmacao explicita do usuario, comando a comando. Nao
  encadear multiplos comandos no servidor sem aprovacao intermediaria.
- Fora do deploy inicial (espelha `CLAUDE.md` §4): API/FastAPI, PostGIS, Prefect,
  pipelines pesados ao vivo, M2/M3, pesquisas e Power BI.
- Backup e regeneracao (DR): procedimento de encriptacao de segredos, restore ponta a
  ponta de servidor zerado e regeneracao dos Parquets estao em `docs/backup_restore.md`.

## 10. Referencias canonicas

Hierarquia de documentos (da fonte de verdade ao subordinado):

1. `CLAUDE.md` — fonte de verdade. Parametros canonicos, score, guardrails. Prevalece
   em qualquer conflito.
2. `tasks/backlog.md` — roadmap por bloco (pendentes); `tasks/completed.md` —
   historico de ciclos concluidos.
3. `docs/` — contratos tecnicos detalhados (dashboard, mercado/residual, outputs M1,
   relatorio censitario, infra, backup/DR).
4. `PRD.md` (este documento) — visao de produto, subordinado ao `CLAUDE.md`.

Este PRD descreve o produto e referencia as fontes acima; ele nao redefine parametros
canonicos nem duplica o roadmap. Em caso de divergencia entre este PRD e o `CLAUDE.md`,
o `CLAUDE.md` prevalece.
