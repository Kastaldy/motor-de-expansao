# Motor de Expansao Ultra Academia - CLAUDE.md
> Fonte canonica e resumida do projeto. Ler antes de qualquer tarefa.
> Responsavel: Felipe Silva | Estrategia e Growth | Ultra Academia
> Versao: Abril 2026

## 1. Visao do projeto
Sistema de expansao ativa continua da Ultra Academia.

Perguntas do produto:
1. Onde vale expandir? -> inteligencia territorial
2. Quem ja atua ali? -> radar competitivo
3. Quais imoveis estao disponiveis? -> pipeline imobiliario
4. Qual ponto tem maior chance de sucesso? -> score preditivo

Estado atual:
- Fase 1 / M1 nacional e a frente ativa e canonica.
- M2, M3, frontend e ML nao devem contaminar o fechamento do M1.
- O contrato atual fecha com base territorial reproduzivel, auditavel e staging em Parquet.

## 2. Contexto de negocio
- Rede brasileira operando desde 2020.
- 79 unidades ativas + 80 planejadas.
- Publico-alvo: 18-45 anos.
- Renda domiciliar alvo do entorno: >= R$ 4.500/mes.
- Perfil ideal de unidade: minimo 1.200 m2, ideal 1.500-2.000 m2, pe-direito >= 3,5 m.
- Distancia minima entre unidades Ultra: 1 km.

## 3. Estrutura real do repositorio
Estrutura atual e flat:

```text
.
|- CLAUDE.md
|- config.py
|- base_h3_brasil.py
|- ibge_censo.py
|- hex_enrichment.py
|- fase1_bi_exports.py
|- poi_enrichment.py
|- score_consolidado.py
|- models.py
|- main.py
|- data/
|- docs/
`- test_*.py
```

## 4. Stack e convencoes
- Python 3.11+, pandas, pyarrow, shapely, h3, requests
- staging sempre em Parquet antes de qualquer persistencia posterior
- CSV sempre com `sep=";"` e `encoding="utf-8-sig"`
- commits em conventional commits

## 5. Parametros canonicos atuais
Manter coerencia entre codigo, CI, testes e docs:

```python
H3_RESOLUTION = 7
DIST_MIN_ULTRA_KM = 1.0
RENDA_MIN = 4500.0
AREA_MIN_M2 = 1200.0
M1_SCORE_OFICIAL = "score_priorizacao"
M1_PRIORIZACAO_TOP_PCT_POR_UF = 0.20
M1_OSM_ENABLED = False
M1_SETOR_CENSITARIO_OBRIGATORIO = False
```
## 6. Escopo canonico do M1 nacional
Fluxo oficial da Fase 1:
1. `base_h3_brasil.py` -> gera base H3 nacional por UF em `data/staging/brasil/uf=XX/hexagonos.parquet`
2. `hex_enrichment.py` -> enriquecimento estrutural nacional com IBGE e saida `data/staging/brasil_estrutural.parquet`
3. priorizacao nacional -> corte padrao top 20% por UF e saida `data/staging/brasil_priorizados.parquet`
4. camada de oportunidade -> ranking Brasil, UF e municipio em `data/staging/hexagonos_brasil_oportunidades.parquet`
5. `fase1_bi_exports.py` -> artefatos executivos/BI estaveis
## 7. Regra oficial de score do M1
Separar sempre:
- `hex_score_estrutural`: base estrutural oficial
- `ajuste_executivo`: bonus/penalidade de priorizacao
- `score_priorizacao`: score oficial para ranking executivo
Inputs oficiais:
- `renda_per_capita`
- `populacao_proxy`
- `pop_18_45` como fonte preferida
- `pop_total` como fallback
Regra canonica:

```python
renda_pct_nacional = percentil_nacional(renda_per_capita)
pop_pct_nacional = percentil_nacional(populacao_proxy)

hex_score_estrutural = 100 * (
    0.60 * renda_pct_nacional +
    0.40 * pop_pct_nacional
)

ajuste_executivo =
    +5 se renda_pct_nacional >= 0.75 e pop_pct_nacional >= 0.75
    +2 se renda_pct_nacional >= 0.75 e pop_pct_nacional < 0.75
    +1 se pop_pct_nacional >= 0.75 e renda_pct_nacional < 0.75
    -5 se renda_pct_nacional < 0.25
    -3 se pop_pct_nacional < 0.25

score_priorizacao = clip(hex_score_estrutural + ajuste_executivo, 0, 100)
score_oficial = score_priorizacao
score_oficial_nome = "score_priorizacao"
```
Campos auditaveis esperados:
- `renda_pct_nacional`
- `pop_pct_nacional`
- `hex_score_estrutural`
- `ajuste_executivo`
- `score_priorizacao`
- `score_oficial`
- `score_oficial_nome`
- `score_percentil_nacional`
Regra de governanca:
- nao misturar score estrutural com regra executiva
- usar `hex_score_estrutural` para leitura estrutural
- usar `score_priorizacao` para ranking e priorizacao executiva
## 8. Papel do OSM no estado atual
OSM nao e dependencia operacional do fechamento nacional da Fase 1.
- OSM segue suportado para fluxos locais, validacoes pontuais e retomada futura.
- `hex_score_final` com concorrencia esta adiado.
- nos outputs oficiais do M1, `osm_status` deve indicar `nao_aplicado_mvp_nacional`.
## 9. IBGE e fallback oficial
Fonte oficial do M1 nacional: IBGE.
Fontes ativas:
- malha do Brasil por UF
- malha municipal por UF
- SIDRA tabela 10295 variavel 13431 para renda municipal
- SIDRA tabela 9514 para proxy de populacao 18-45
Quando setor censitario nao estiver disponivel:
1. atribuir municipio por malha municipal oficial do IBGE
2. carregar renda e populacao no nivel municipal via SIDRA
3. registrar fallback de forma explicita e auditavel
Colunas esperadas de rastreabilidade:
- `fonte_demografica`
- `fonte_renda`
- `fonte_populacao`
- `nivel_geografico_ibge`
- `fallback_setor_censitario`
- `motivo_fallback_setor`
- `fonte_geometria_ibge`
- `metodo_atribuicao_municipio`
- `data_referencia_ibge`
## 10. Saidas oficiais da Fase 1
- `data/staging/brasil_estrutural.parquet`
- `data/staging/brasil_priorizados.parquet`
- `data/staging/hexagonos_brasil_oportunidades.parquet`
- `data/outputs/hexagonos_brasil_dashboard.parquet`
- `data/outputs/hexagonos_mapa_sample.parquet`
- `data/outputs/top_oportunidades_resumo.csv`
- `data/outputs/resumo_por_uf.csv`
- `data/reports/camada_oportunidade_fase1.md`
- `data/reports/resumo_executivo_fase1.md`

Dicionario curto do contrato oficial:
- `brasil_estrutural.parquet` -> base estrutural auditavel com `hex_score_estrutural`
- `brasil_priorizados.parquet` -> recorte oficial top 20% por UF com `score_priorizacao`
- `hexagonos_brasil_oportunidades.parquet` -> camada canonica de oportunidade e ranking
- `hexagonos_brasil_dashboard.parquet` -> dataset oficial exportado para BI
- `hexagonos_mapa_sample.parquet` -> amostra oficial do dashboard para visualizacao no Streamlit
- documento curto de apoio: `docs/m1_outputs_oficiais.md`

Campos executivos estaveis esperados:
- `hex_score_estrutural`
- `ajuste_executivo`
- `score_priorizacao`
- `score_oficial`
- `score_oficial_nome`
- `score_percentil_nacional`
- `faixa_oportunidade`
- `flag_viavel`
- `flag_prioridade`
- `rank_brasil`, `rank_uf`, `rank_cidade`
- `osm_status`
- colunas de rastreabilidade IBGE

## 11. Testes e qualidade
Regra de ouro:
- toda mudanca relevante entra com teste
- nenhum PR deve subir com CI quebrado

Testes mais importantes para o M1:
- `test_base_h3_brasil.py`
- `test_hex_enrichment_brasil.py`
- `test_fase1_bi_exports.py`
- `test_fontes_gratuitas.py`

Gate padrao atual:
- `pytest` roda por padrao apenas a suite canonica do M1 acima
- cobertura padrao mede apenas `base_h3_brasil.py`, `hex_enrichment.py`, `fase1_bi_exports.py`, `ibge_censo.py` e `poi_enrichment.py`
- testes legados fora do M1 nao entram no gate padrao deste fechamento

## 12. Prioridades para agentes
Ao trabalhar neste projeto:
- tratar `CLAUDE.md` como fonte canonica
- inspecionar o repositorio real antes de editar
- manter o M1 simples, reproduzivel, auditavel e coerente
- preservar staging em Parquet
- alinhar codigo, config, CI, testes e docs
- nao aumentar escopo sem necessidade

Evitar no contexto do M1:
- concorrencia como dependencia obrigatoria
- frontend
- ML
- expansao para M2/M3 sem pedido explicito

## 13. Experimento paralelo 2010
Foi criado um experimento paralelo de granularidade com setor censitario IBGE 2010 para teste de precisao espacial.
- nao faz parte do pipeline oficial da Fase 1
- nao substitui `hex_score_estrutural`, `score_priorizacao` nem os artefatos oficiais do M1
- serve apenas para validacao metodologica em ambiente isolado

Decisao de design registrada:
- teste de granularidade censitaria 2010 deve ser executado em ambiente paralelo antes de qualquer eventual incorporacao ao pipeline principal

## 14. Referencias rapidas
- `README.md` -> resumo operacional do estado atual
- `docs/fontes_dados_gratuitas.md` -> fontes ativas do M1
- `data/reports/` -> validacoes e relatorios executivos

## 15. Registro de validacao rapida M1
Validacao end-to-end executada em 2026-04-05 para prontidao executiva do fechamento nacional.

Decisao registrada:
- status da validacao: `ERRO`
- recomendacao operacional: `NO-GO` ate corrigir contrato do dashboard (`populacao_proxy`), garantir corte top 20% exato por UF e restaurar lookup amigavel de municipios para o BI

## 16. Registro tecnico de correcao M1
Correcao executada em 2026-04-05 para liberar o uso executivo do fechamento nacional sem alterar a logica do modelo.

Decisoes tecnicas registradas:
- `nome_municipio` passa a ser restaurado de forma canonica via `data/ibge/municipios_nomes_ibge.parquet`
- o lookup local de municipios deve ser construido a partir de fonte oficial IBGE ja usada no projeto, priorizando SIDRA tabela `10295` (`D1C` -> codigo, `D1N` -> nome) e reutilizado localmente nos exports
- `hexagonos_brasil_dashboard.parquet` deve expor `populacao_proxy` como coluna canonica, preservando `proxy_populacao` apenas por compatibilidade
- o corte top 20% por UF do M1 deve usar ordenacao deterministica por rank e cutoff `floor(total_uf * 0.20)` para eliminar excesso por arredondamento
- observacao matematica canonica: com selecao binaria por linha, a proporcao aritmetica de `0.20` por UF so e exatamente representavel quando `total_uf` e multiplo de 5; fora disso, o contrato oficial e bater exatamente o cutoff deterministico sem estouro

Status atualizado:
- status da validacao: `GO`
- recomendacao operacional: `GO` para uso executivo

## 17. Registro do dashboard executivo Power BI
Pacote executivo do M1 preparado em 2026-04-06 a partir do dataset oficial validado, sem alterar pipeline ou artefatos Parquet.

Decisoes de dashboard e modelagem registradas:
- fonte unica do dashboard: `data/outputs/hexagonos_brasil_dashboard.parquet`
- aliases de exibicao no modelo Power BI: `UF` sobre `uf` e `nome_municipio` sobre `cidade`
- score oficial do dashboard permanece `score_priorizacao`; `hex_score_estrutural` e `ajuste_executivo` ficam expostos apenas para leitura complementar
- limite executivo mantido em 4 paginas: `Visao Executiva`, `Analise Territorial`, `Ranking e Priorizacao` e `Comparacao por UF`
- filtros executivos padrao: `UF`, `nome_municipio` e `faixa_oportunidade`
- pacote tecnico do dashboard salvo em `powerbi/m1_dashboard_executivo/` com tema, query M, medidas DAX e especificacao das paginas
- screenshots executivas salvas em `export/` por limitacao do ambiente atual, que nao possui Power BI Desktop para gerar `.pbix`

Status operacional do dashboard:
- status da entrega: `PARCIALMENTE AUTOMATIZADA`
- recomendacao operacional: `GO` para montagem final no Power BI usando o pacote salvo em `powerbi/m1_dashboard_executivo/`

## 18. Registro do dashboard executivo Streamlit local
Camada local do dashboard executivo M1 preparada em 2026-04-06 para leitura em navegador via Streamlit, sem publicar nem alterar pipeline, VPS ou artefatos oficiais.

Decisoes registradas:
- app local usa somente `data/outputs/hexagonos_brasil_dashboard.parquet` como fonte oficial
- estrutura executiva mantida em 4 abas: `Visao Executiva`, `Analise Territorial`, `Ranking e Priorizacao` e `Comparacao por UF`
- filtros globais mantidos em `UF`, `nome_municipio` e `faixa_oportunidade`
- score oficial do app permanece `score_priorizacao`; `hex_score_estrutural` fica apenas como apoio visual no hover do mapa
- padrao visual do Streamlit reaproveita a paleta e a hierarquia do pacote salvo em `powerbi/m1_dashboard_executivo/`
- leitura local prioriza KPI, ranking e mapa, com limites de renderizacao para manter fluidez sem alterar o parquet oficial

Status operacional:
- status da entrega: `GO_LOCAL`
- recomendacao operacional: `GO` para execucao local via `streamlit run streamlit_app.py`
