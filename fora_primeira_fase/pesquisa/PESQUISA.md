# Pesquisa: Fontes de Dados e APIs para Enriquecimento Territorial
> Motor de Expansao Ultra Academia - Fase 1 / M1
> Data: 2026-04-06
> Responsavel: Felipe Silva | Estrategia e Growth

---

## Sumario Executivo

Esta pesquisa mapeia **22 fontes de dados publicas e gratuitas** que podem enriquecer os hexagonos H3 do Motor de Expansao com maior precisao e confiabilidade. O objetivo e aumentar a qualidade decisoria da inteligencia territorial para acelerar a expansao de forma saudavel.

**Descoberta principal:** O IBGE ja liberou os agregados por setores censitarios do Censo 2022 (468.097 setores com renda, populacao e faixas etarias). Isso resolve o principal bloqueador do modelo atual, que opera com fallback municipal e gera scores uniformes dentro de cidades.

**Top 3 acoes de maior impacto imediato:**
1. Migrar para Censo 2022 por setor censitario (granularidade 100x maior)
2. Mapear concorrentes reais via CNPJ/CNAE 9313-1/00 (Receita Federal)
3. Validar populacao com Kontur Population (dataset H3-nativo gratuito)

---

## 1. Contexto do Mercado Fitness Brasileiro

Antes de detalhar as fontes de dados, e fundamental entender o mercado:

| Indicador | Valor | Fonte |
|-----------|-------|-------|
| Posicao global em n. de academias | 2o no mundo (atras dos EUA) | ACAD Brasil |
| Total de academias registradas | ~33.000+ unidades | ACAD Brasil |
| Alunos frequentando academias | ~15 milhoes (2024) | Panorama Setorial FB |
| Penetracao de mercado | ~7% da populacao | ACAD/IHRSA |
| Penetracao EUA (referencia) | ~25% da populacao | IHRSA |
| Penetracao Europa (referencia) | ~15% da populacao | IHRSA |
| Crescimento 2019-2024 | +50% em alunos | Panorama Setorial FB |
| Previsao crescimento 2025 | +22% adicional | Panorama Setorial FB |

**Implicacao estrategica:** Com penetracao de apenas 7% vs 25% nos EUA, o Brasil tem espaco para triplicar o numero de frequentadores. A expansao territorial precisa ser cirurgica para capturar essa demanda latente nos microterritorios certos.

### Variaveis Criticas para Site Selection de Academias

Pesquisas da IHRSA (Health & Fitness Association) e estudos de location intelligence indicam:

- **80% dos membros** vem de ate **12 minutos de deslocamento** da academia
- **Densidade populacional ideal** no entorno: **60.000-100.000+ pessoas**
- **Renda domiciliar** e o fator #1 de correlacao com adesao a academias
- **Penetracao por renda:** ~30% em faixas altas vs ~10% em faixas medianas
- **Faixa etaria predominante:** 60% dos membros ganham entre R$5.000-R$15.000/mes
- **Saturacao competitiva:** areas com 5+ academias no raio de 1.5km criam pressao de receita
- **White space analysis:** ZIP codes com alta demanda residencial + baixa oferta de academias = oportunidade greenfield

---

## 2. Fontes de Dados - Catalogo Completo

### 2.1 IBGE Censo 2022 - Setores Censitarios (PRIORIDADE MAXIMA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | DISPONIVEL PARA DOWNLOAD |
| **Granularidade** | Setor censitario (~468.097 setores no Brasil) |
| **Custo** | Gratuito |
| **Relevancia** | CRITICA - resolve o principal gap do modelo atual |
| **Atualizacao** | Dados do Censo 2022, corrigidos em 17/04/2025 |

**O que contem:**
- `V002` (bloco Basico): populacao total residente por setor
- `V003` (bloco DomicilioRenda): renda total do setor censitario
- Faixas etarias por setor (permite calcular pop 18-45 real)
- Numero de domicilios por setor
- Caracteristicas dos domicilios
- **246 variaveis** do questionario do universo

**Como acessar:**
- FTP IBGE: `ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/`
- Dicionario de dados de renda: `ftp.ibge.gov.br/.../dicionario_de_dados_renda_responsavel.xlsx`
- Malha de setores (shapefile): `ibge.gov.br/geociencias/.../26565-malhas-de-setores-censitarios-divisoes-intramunicipais.html`
- Alternativa via R: pacote `censobr` do IPEA
- Alternativa via SQL: Base dos Dados (basedosdados.org)

**Impacto no modelo:**
- O experimento com setores 2010 provou amplitude de 54-74 pontos (p95-p05) vs ~0 pontos com municipal
- Censo 2022 tem dados 12 anos mais recentes que o Censo 2010
- Permite calcular `renda_per_capita` real por setor (V003/V002)
- Permite calcular `pop_18_45` real por setor (nao mais proxy)

**Acao recomendada:** Substituir o fallback municipal SIDRA pelo enriquecimento direto via setores censitarios 2022. Isso e a maior alavanca de precisao disponivel.

---

### 2.2 Kontur Population (PRIORIDADE ALTA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | DISPONIVEL PARA DOWNLOAD |
| **Granularidade** | Hexagonos H3 resolucao 8 (~400m) |
| **Custo** | Gratuito (CC BY) |
| **Relevancia** | ALTA - dataset ja nativo em H3, validacao cruzada de populacao |
| **Atualizacao** | Periodica (ultima versao 2023/2024) |

**O que contem:**
- Estimativa de populacao por hexagono H3 (resolucao 8)
- Baseado em imagens de satelite + dados censitarios
- Cobertura global, subset Brasil disponivel separadamente

**Como acessar:**
- HDX Brasil: `data.humdata.org/dataset/kontur-population-brazil`
- HDX Global: `data.humdata.org/dataset/kontur-population-dataset`
- Formato: GeoParquet / GeoJSON
- Tamanho: ~400MB (Brasil) / ~6.6GB (global 400m)

**Impacto no modelo:**
- Ja esta em formato H3 - integracao direta sem conversao geometrica
- Resolucao 8 (~400m) e mais fina que a resolucao 7 (~1.2km) usada no projeto
- Pode ser agregado para H3-r7 com `h3.h3_to_parent()`
- Serve como camada de validacao cruzada contra dados IBGE
- Permite estimar populacao em hexagonos onde setor censitario nao tem match

**Acao recomendada:** Baixar subset Brasil, agregar para H3-r7, e usar como:
1. Validacao cruzada do `populacao_proxy` do IBGE
2. Fallback para hexagonos sem match de setor censitario
3. Proxy de densidade real (vs densidade administrativa do IBGE)

---

### 2.3 CNPJ / Receita Federal - Concorrentes Reais (PRIORIDADE ALTA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | DISPONIVEL |
| **Granularidade** | Estabelecimento individual (CNPJ com endereco) |
| **Custo** | Gratuito (dados abertos RFB) |
| **Relevancia** | ALTA - mapeamento real de concorrentes vs proxy OSM |
| **Atualizacao** | Trimestral pela Receita Federal |

**O que contem:**
- Base completa de empresas ativas no Brasil
- CNAE primario e secundarios por estabelecimento
- Endereco completo (logradouro, municipio, UF, CEP)
- Razao social, nome fantasia
- Porte (MEI, ME, EPP, demais)
- Data de abertura e situacao cadastral

**CNAEs relevantes para academias:**
- `9313-1/00` - Atividades de condicionamento fisico (PRINCIPAL)
- `9312-3/00` - Clubes sociais, esportivos e similares
- `9319-1/01` - Producao e promocao de eventos esportivos
- `4774-1/00` - Comercio varejista de artigos esportivos (complementar)

**Como acessar:**
- **Base dos Dados (BigQuery):** `basedosdados.org` - consulta SQL gratuita (1TB/mes)
  ```sql
  SELECT cnpj, razao_social, nome_fantasia, cnae_fiscal,
         logradouro, municipio, uf, cep
  FROM `basedosdados.br_me_cnpj.estabelecimentos`
  WHERE cnae_fiscal = '9313100'
    AND situacao_cadastral = '02'  -- ativa
  ```
- **Download direto RFB:** `dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj`
- **APIs gratuitas:** CNPJa (`cnpja.com/api/open`), CNPJ.ws (`cnpj.ws`)
- **Mapa de Empresas:** `gov.br/empresas-e-negocios/pt-br/mapa-de-empresas` (paineis visuais)

**Impacto no modelo:**
- Substitui contagem OSM (que depende de contribuicoes voluntarias) por registro oficial
- Permite classificar concorrentes por porte: MEI (micro academias), ME/EPP (redes medias), demais (redes grandes como SmartFit)
- Permite calcular `n_concorrentes_reais` por hexagono com geocoding do CEP
- Permite identificar taxa de abertura/fechamento de academias por regiao (proxy de viabilidade)

**Acao recomendada:** Extrair via Base dos Dados todos os CNPJs com CNAE 9313-1/00 ativos, geocodificar, e atribuir a hexagonos H3. Substituir ou complementar `n_academias_osm`.

---

### 2.4 CNES - Estabelecimentos de Saude (PRIORIDADE MEDIA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | DISPONIVEL com API |
| **Granularidade** | Estabelecimento individual (com coordenadas) |
| **Custo** | Gratuito |
| **Relevancia** | MEDIA - proxy de infraestrutura urbana e poder aquisitivo do entorno |
| **Atualizacao** | Mensal |

**O que contem:**
- Localizacao de todos os estabelecimentos de saude do Brasil
- Tipo (hospital, clinica, laboratorio, consultorio)
- Natureza juridica (publico, privado, filantr6opico)
- Capacidade instalada e profissionais

**Como acessar:**
- OpenDataSUS: `opendatasus.saude.gov.br/dataset/cnes-cadastro-nacional-de-estabelecimentos-de-saude`
- API Ministerio da Saude: `apidadosabertos.saude.gov.br`
- Portal dados.gov.br: `dados.gov.br/dados/conjuntos-dados/cnes`
- Base dos Dados: `basedosdados.org` (tabela tratada)
- Formatos: CSV, JSON, XML, API REST

**Impacto no modelo:**
- Densidade de clinicas privadas = proxy de poder aquisitivo do bairro
- Hospitais e UBSs = proxy de infraestrutura urbana consolidada
- Laboratorios de analises clinicas = indicador de fluxo de pessoas preocupadas com saude
- Pode gerar variavel `score_infraestrutura_saude` por hexagono

**Acao recomendada:** Usar como variavel complementar. Contar estabelecimentos privados de saude por hexagono como proxy de maturidade urbana e perfil de renda.

---

### 2.5 ANS - Beneficiarios de Plano de Saude (PRIORIDADE MEDIA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | DISPONIVEL |
| **Granularidade** | Municipio |
| **Custo** | Gratuito |
| **Relevancia** | MEDIA - excelente proxy de poder aquisitivo |
| **Atualizacao** | Trimestral (defasagem de 3 meses) |

**O que contem:**
- Numero de beneficiarios de planos de saude por municipio
- Segmentacao por tipo de plano (medico-hospitalar, odontologico)
- Dados historicos permitindo analise de tendencia

**Como acessar:**
- Portal ANS: `gov.br/ans/pt-br/acesso-a-informacao/perfil-do-setor/dados-abertos-1`
- Portal dados.gov.br: `dados.gov.br/dados/conjuntos-dados/dados-de-beneficiarios-por-regiao-geografica`
- Base dos Dados: `basedosdados.org` (tabela tratada)
- ANS TabNet: consulta interativa

**Impacto no modelo:**
- `% populacao com plano de saude` = forte proxy de renda disponivel para servicos de saude/fitness
- Correlacao direta: quem paga plano de saude tem perfil de renda compativel com mensalidade de academia
- No Brasil, ~25% da populacao tem plano de saude - essa proporcao varia enormemente entre municipios
- Pode gerar variavel `penetracao_plano_saude` por hexagono (via municipio)

**Acao recomendada:** Calcular `beneficiarios_ans / populacao_total` por municipio e usar como fator multiplicador do score de renda.

---

### 2.6 RAIS/CAGED - Emprego Formal (PRIORIDADE MEDIA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | DISPONIVEL |
| **Granularidade** | Municipio (por CNAE) |
| **Custo** | Gratuito |
| **Relevancia** | MEDIA - emprego formal indica estabilidade economica e perfil de consumo |
| **Atualizacao** | RAIS anual, CAGED mensal |

**O que contem:**
- RAIS: estoque de empregos formais por municipio, CNAE, faixa salarial, idade, escolaridade
- CAGED: movimentacao mensal (admissoes e desligamentos)
- Permite filtrar por CNAE do setor fitness (9313-1/00) para ver empregados de academias

**Como acessar:**
- Microdados MTE: `gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho/microdados-rais-e-caged`
- Base dos Dados: `basedosdados.org` (tabelas tratadas, consulta SQL)
- PDET Online: `acesso.mte.gov.br/portal-pdet/`

**Impacto no modelo:**
- `empregados_formais / populacao` = taxa de formalizacao do trabalho (proxy de renda estavel)
- Empregados na CNAE 9313 por municipio = tamanho do mercado de trabalho fitness local
- Massa salarial media por municipio = proxy de poder de compra
- Permite identificar regioes com crescimento acelerado de emprego (sinal de expansao economica)

**Acao recomendada:** Usar como variavel complementar para refinar estimativa de renda e identificar mercados em crescimento.

---

### 2.7 INEP - Censo Escolar (PRIORIDADE MEDIA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | DISPONIVEL |
| **Granularidade** | Escola individual (com coordenadas) |
| **Custo** | Gratuito |
| **Relevancia** | MEDIA - universidades sao concentradoras de publico 18-25 |
| **Atualizacao** | Anual |

**O que contem:**
- Localizacao de 226.000+ escolas brasileiras com endereco e geolocalizacao
- Tipo (publica/privada, infantil/fundamental/medio/superior)
- Numero de matriculas por escola
- Infraestrutura da escola

**Como acessar:**
- Microdados INEP: `gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar`
- Catalogo de Escolas INEP: interface web com busca por cidade
- Base dos Dados: `basedosdados.org` (tabela tratada com SQL)
- API INEP (GitHub): `github.com/inepdadosabertos/api`

**Impacto no modelo:**
- **Universidades** = concentracao de jovens 18-25 (publico-alvo primario)
- **Escolas privadas** = proxy de renda do bairro
- **Densidade de matriculas** = proxy de fluxo de pessoas jovens na regiao
- Pode gerar variaveis: `n_universidades_raio`, `n_matriculas_superior`, `n_escolas_privadas`

**Acao recomendada:** Geocodificar universidades e escolas privadas, contar por hexagono. Universidades sao particularmente valiosas como geradoras de demanda para academias.

---

### 2.8 CadUnico / Bolsa Familia (PRIORIDADE MEDIA-BAIXA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | DISPONIVEL |
| **Granularidade** | Municipio |
| **Custo** | Gratuito |
| **Relevancia** | MEDIA-BAIXA - proxy inverso de renda |
| **Atualizacao** | Mensal |

**O que contem:**
- Familias cadastradas por faixa de renda per capita por municipio
- Beneficiarios do Bolsa Familia por municipio
- Dados historicos para analise de tendencia

**Como acessar:**
- Portal PBF/CadUnico: `aplicacoes.cidadania.gov.br/ri/pbfcad/`
- Portal dados.gov.br: `dados.gov.br/dados/conjuntos-dados/cadastro-unico---familiaspessoas-por-faixas-de-renda-per-capita`

**Impacto no modelo:**
- `% familias CadUnico / total familias` = proxy inverso de poder aquisitivo
- Alta proporcao de CadUnico = menor potencial para academia premium
- Util como filtro negativo: hexagonos com alta concentracao CadUnico podem ter score reduzido

**Acao recomendada:** Usar como penalizador no `ajuste_executivo`. Regioes com > 40% de familias no CadUnico recebem ajuste negativo.

---

### 2.9 IPEA - Indice de Vulnerabilidade Social (PRIORIDADE MEDIA-BAIXA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | DISPONIVEL |
| **Granularidade** | Municipio e UDH (Unidade de Desenvolvimento Humano) |
| **Custo** | Gratuito |
| **Relevancia** | MEDIA-BAIXA - indice sintetico complementar |
| **Atualizacao** | Periodica (ultima atualizacao com PNAD 2022) |

**O que contem:**
- IVS composto por 3 dimensoes: infraestrutura urbana, capital humano, trabalho e renda
- Dados para 5.565 municipios
- Dados para regioes metropolitanas ao nivel de UDH

**Como acessar:**
- Atlas IVS: `ivs.ipea.gov.br`
- Portal dados.gov.br: `dados.gov.br/dados/conjuntos-dados/ivs`

**Impacto no modelo:**
- Indice sintetico que combina multiplas dimensoes de vulnerabilidade
- Pode servir como validacao cruzada do score estrutural
- UDHs em regioes metropolitanas oferecem granularidade sub-municipal

**Acao recomendada:** Usar como variavel de validacao. Nao incluir diretamente no score para evitar redundancia com renda/populacao ja usados.

---

### 2.10 Atlas da Violencia / Seguranca Publica (PRIORIDADE MEDIA-BAIXA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | DISPONIVEL |
| **Granularidade** | Municipio |
| **Custo** | Gratuito |
| **Relevancia** | MEDIA-BAIXA - seguranca impacta decisao de localizacao |
| **Atualizacao** | Anual |

**O que contem:**
- Taxas de homicidio por municipio (SIM/DataSUS)
- Dados segmentados por sexo, raca/cor, faixa etaria
- Series historicas

**Como acessar:**
- Atlas da Violencia: `ipea.gov.br/atlasviolencia/`
- Downloads CSV: `ipea.gov.br/atlasviolencia/downloads`
- Base dos Dados: `basedosdados.org` (tabela tratada)

**Impacto no modelo:**
- Municipios com altas taxas de violencia podem ter menor atratividade para investimento
- Pode servir como fator de penalizacao no ajuste executivo
- Seguranca e fator decisorio para clientes de academias (especialmente mulheres)

**Acao recomendada:** Incluir como fator de penalizacao leve. Municipios no top 10% de violencia recebem ajuste negativo de -2 a -3 pontos.

---

### 2.11 ANATEL ERBs - Torres de Celular (PRIORIDADE BAIXA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | DISPONIVEL |
| **Granularidade** | Torre individual (com coordenadas) |
| **Custo** | Gratuito |
| **Relevancia** | BAIXA - proxy de urbanizacao |
| **Atualizacao** | Continua |

**O que contem:**
- Localizacao de todas as ERBs (Estacoes Radio Base) licenciadas no Brasil
- Operadora, tecnologia (2G/3G/4G/5G), frequencia
- Endereco e coordenadas geograficas

**Como acessar:**
- Painel ANATEL: `gov.br/anatel/pt-br` > Paineis > Outorga e Licenciamento > Estacoes do SMP
- Sistema Mosaico ANATEL

**Impacto no modelo:**
- Densidade de ERBs = proxy de urbanizacao e fluxo de pessoas
- Areas com 5G = indicador de regiao premium/desenvolvida
- Util em areas onde dados censitarios sao limitados

**Acao recomendada:** Usar como variavel de validacao secundaria. Nao incluir diretamente no score.

---

### 2.12 OpenCelliD - Torres de Celular Global (PRIORIDADE BAIXA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | DISPONIVEL |
| **Granularidade** | Torre individual (com coordenadas) |
| **Custo** | Gratuito (CC BY-SA 4.0) |
| **Relevancia** | BAIXA - alternativa global ao ANATEL |
| **Atualizacao** | Continua (contribuicao comunitaria) |

**O que contem:**
- 40M+ registros de torres celulares globais
- Coordenadas, operadora, tecnologia, pais

**Como acessar:**
- Download: `opencellid.org/downloads.php`
- World Bank Data Catalog: `datacatalog.worldbank.org/search/dataset/0038043`

**Impacto no modelo:**
- Similar ao ANATEL, porem com cobertura global e formato mais acessivel
- World Bank ja rasterizou a ~1km de resolucao
- Correlacao comprovada entre densidade de torres e populacao

---

### 2.13 Overture Maps - POIs Globais (PRIORIDADE MEDIA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | DISPONIVEL |
| **Granularidade** | POI individual (com coordenadas) |
| **Custo** | Gratuito (CDLA Permissive v2) |
| **Relevancia** | MEDIA - alternativa superior ao OSM para POIs |
| **Atualizacao** | Periodica (releases trimestrais) |

**O que contem:**
- 64M+ pontos de interesse globais (escolas, negocios, hospitais, etc.)
- Categorizado por tipo de estabelecimento
- Coordenadas precisas
- Mantido por Microsoft, Meta, Amazon, TomTom

**Como acessar:**
- Download: `overturemaps.org/download/`
- Formato: GeoParquet (cloud-native)
- AWS S3 e Azure Blob Storage
- Consulta via DuckDB (SQL) ou Python client
- Explorer web: sem instalacao necessaria

**Impacto no modelo:**
- Base de POIs muito maior e mais curada que OSM
- Permite contar concorrentes (gyms/fitness), comercio, servicos por hexagono
- Pode substituir ou complementar Overpass API do OSM
- Formato GeoParquet e nativo do projeto (ja usa Parquet)

**Acao recomendada:** Avaliar como substituto do OSM para contagem de POIs. Download do subset Brasil e filtro por categorias relevantes (fitness, comercio, servicos).

---

### 2.14 Meta/CIESIN High Resolution Population (PRIORIDADE MEDIA-BAIXA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | DISPONIVEL (porem descontinuado) |
| **Granularidade** | ~30 metros |
| **Custo** | Gratuito |
| **Relevancia** | MEDIA-BAIXA - alta resolucao mas sem atualizacao |

**O que contem:**
- 7 mapas para o Brasil: populacao geral, mulheres, homens, criancas (0-5), jovens (15-24), idosos (60+), mulheres em idade reprodutiva
- Baseado em AI + imagens de satelite + censo

**Como acessar:**
- HDX: `data.humdata.org/dataset/brazil-high-resolution-population-density-maps-demographic-estimates`
- AWS: `registry.opendata.aws/dataforgood-fb-hrsl/`
- Formato: GeoTIFF

**Nota:** Meta anunciou em 2024 que nao atualizara mais estes mapas. Dados refletem ~2019-2020. Ainda uteis como referencia historica e para validacao cruzada.

---

### 2.15 GHSL - Global Human Settlement Layer (PRIORIDADE BAIXA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | DISPONIVEL |
| **Granularidade** | Grid 100m-1km |
| **Custo** | Gratuito |
| **Relevancia** | BAIXA - validacao complementar |
| **Atualizacao** | Periodica (versao R2023A atual) |

**O que contem:**
- GHS-POP: populacao residencial 1975-2030 (projecoes)
- GHS-BUILT: area construida
- GHS-SMOD: grau de urbanizacao

**Como acessar:**
- Download: `human-settlement.emergency.copernicus.eu/download.php`
- Google Earth Engine: `developers.google.com/earth-engine/datasets/catalog/JRC_GHSL_P2023A_GHS_POP`

---

### 2.16 VIIRS Night Lights - Luminosidade Noturna (PRIORIDADE BAIXA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | DISPONIVEL |
| **Granularidade** | Grid ~500m |
| **Custo** | Gratuito |
| **Relevancia** | BAIXA - proxy de atividade economica |
| **Atualizacao** | Mensal (2012-presente) |

**O que contem:**
- Intensidade de luz noturna por pixel
- Proxy validado academicamente para GDP e atividade economica
- Serie historica desde 2012

**Como acessar:**
- EOG: `eogdata.mines.edu/products/vnl/`
- World Bank Light Every Night: `registry.opendata.aws/wb-light-every-night/`
- Google Earth Engine

**Impacto no modelo:**
- Luminosidade noturna = proxy de atividade economica e urbanizacao
- Permite detectar tendencias de crescimento urbano (aumento de luminosidade ao longo do tempo)
- Resolucao de ~500m e compativel com H3-r7

---

### 2.17 FipeZAP - Precos Imobiliarios (PRIORIDADE BAIXA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | PARCIALMENTE DISPONIVEL |
| **Granularidade** | Cidade (10 capitais para comercial) |
| **Custo** | Relatorios publicos gratuitos / dados detalhados pagos |
| **Relevancia** | BAIXA para M1 nacional - util para analise local |
| **Atualizacao** | Mensal |

**O que contem:**
- Preco medio de venda e locacao de imoveis comerciais (salas/conjuntos ate 200m2)
- Indice de variacao de precos
- Cobertura: 10 cidades para comercial

**Como acessar:**
- Relatorios PDF: `downloads.fipe.org.br/indices/fipezap/`
- DataZAP+: `datazap.com.br` (dados mais detalhados, potencialmente pagos)

---

### 2.18 Strava Metro - Atividade Fitness (PRIORIDADE BAIXA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | DISPONIVEL (mediante solicitacao) |
| **Granularidade** | Rua/segmento |
| **Custo** | Gratuito para planejamento urbano |
| **Relevancia** | BAIXA - proxy de interesse em atividade fisica |

**O que contem:**
- Dados agregados e de-identificados de atividades (corrida, ciclismo)
- Heatmap de rotas populares
- Volume de atividades por regiao

**Como acessar:**
- Strava Metro: `metro.strava.com` (formulario de solicitacao)
- Heatmap publico: `strava.com/maps/global-heatmap` (visual, sem download)

**Impacto no modelo:**
- Areas com alta atividade Strava = populacao engajada em fitness = demanda potencial para academias
- Porem: viés de selecao (Strava = outdoor/corrida, nao necessariamente publico de academia)

---

### 2.19 Isochrone APIs - Catchment Area (PRIORIDADE MEDIA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | DISPONIVEL (open source) |
| **Granularidade** | Customizavel (1-30 min) |
| **Custo** | Gratuito (self-hosted) |
| **Relevancia** | MEDIA - analise de acessibilidade real |

**O que contem:**
- Poligonos de area alcancavel em X minutos a pe, carro ou transporte publico
- Baseado em dados OSM + GTFS

**Ferramentas open source:**
- **Valhalla:** `valhalla.github.io/valhalla/api/isochrone/api-reference/` - motor de routing completo
- **OpenTripPlanner (OTP):** suporta GTFS para transporte publico
- **TravelTime API:** freemium, ate 10 isocronas/segundo no plano gratuito

**Impacto no modelo:**
- Permite calcular `populacao_12min` = populacao real a 12 min de cada hexagono (metrica #1 da IHRSA)
- Superior a raio fixo de 1.5km (que ignora barreiras geograficas, rios, viadutos)
- Pode substituir `DIST_MIN_ULTRA_KM` por distancia de tempo real

**Acao recomendada:** Implementar no M2 como camada de acessibilidade. Para o M1, manter raio euclidiano por simplicidade.

---

### 2.20 GTFS - Transporte Publico (PRIORIDADE BAIXA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | PARCIALMENTE DISPONIVEL |
| **Granularidade** | Rota/parada |
| **Custo** | Gratuito |
| **Relevancia** | BAIXA - cobertura limitada no Brasil |

**O que contem:**
- Rotas, paradas, horarios de transporte publico
- Formato padrao para integracao com isochrone APIs

**Disponibilidade no Brasil:**
- Sao Paulo (SPTrans): DISPONIVEL
- Belo Horizonte: DISPONIVEL
- Maioria das cidades: NAO DISPONIVEL

**Como acessar:**
- MobilityDatabase: `transitfeeds.com`
- Transitland: `transit.land`
- Ferramentas IPEA: `github.com/ipeaGIT/gtfstools`

---

### 2.21 PNAD Continua - Renda e Emprego (PRIORIDADE BAIXA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | DISPONIVEL |
| **Granularidade** | UF e regioes metropolitanas (nao municipal) |
| **Custo** | Gratuito |
| **Relevancia** | BAIXA - granularidade insuficiente para M1 |

**O que contem:**
- Renda domiciliar per capita media: R$2.069 (2024)
- Faixas etarias, educacao, ocupacao
- Atualizacao trimestral

**Como acessar:**
- IBGE SIDRA: `sidra.ibge.gov.br/tabela/3261`
- Microdados: `ibge.gov.br/estatisticas/sociais/saude/17270-pnad-continua.html`

**Nota:** Util para calibracao nacional, mas granularidade insuficiente (UF) para enriquecer hexagonos individuais.

---

### 2.22 Google Places API (PRIORIDADE MEDIA - JA INTEGRADA)

| Atributo | Detalhe |
|----------|---------|
| **Status** | DISPONIVEL (ja integrada no projeto) |
| **Granularidade** | POI individual |
| **Custo** | Freemium - US$200 credito/mes + Pro tier: 5.000 eventos gratis/mes |
| **Relevancia** | MEDIA - score de vitalidade comercial |

**Nota sobre pricing 2026:**
- Nearby Search cai no tier Pro (5.000 eventos gratuitos/mes)
- Para varredura nacional de ~1.5M hexagonos, custo seria proibitivo
- Melhor usar para validacao pontual de top hexagonos priorizados

---

## 3. Matriz de Priorizacao

### Prioridade 1 - Impacto Maximo, Custo Zero (implementar agora)

| Fonte | Variavel Gerada | Impacto Esperado | Complexidade |
|-------|-----------------|------------------|--------------|
| IBGE Censo 2022 Setores | `renda_per_capita_setor`, `pop_18_45_setor` | **TRANSFORMACIONAL** - resolve gap principal | Media |
| CNPJ/CNAE 9313 | `n_concorrentes_reais`, `porte_concorrentes` | **ALTO** - concorrencia real vs proxy | Baixa-Media |
| Kontur Population | `pop_kontur_h3`, `densidade_kontur` | **ALTO** - validacao H3-nativa | Baixa |

### Prioridade 2 - Impacto Medio, Custo Zero (implementar em sequencia)

| Fonte | Variavel Gerada | Impacto Esperado | Complexidade |
|-------|-----------------|------------------|--------------|
| ANS Beneficiarios | `penetracao_plano_saude` | MEDIO - proxy de poder aquisitivo | Baixa |
| CNES Saude | `score_infraestrutura_saude` | MEDIO - proxy de maturidade urbana | Baixa |
| INEP Escolas | `n_universidades_raio`, `n_escolas_privadas` | MEDIO - proxy de fluxo jovem | Baixa |
| Overture Maps | `n_pois_comerciais`, `score_vitalidade` | MEDIO - substitui OSM | Media |
| CadUnico | `pct_familias_vulneraveis` | MEDIO - filtro negativo | Baixa |

### Prioridade 3 - Enriquecimento Complementar (avaliar para M2)

| Fonte | Variavel Gerada | Impacto Esperado | Complexidade |
|-------|-----------------|------------------|--------------|
| RAIS/CAGED | `emprego_formal_pct`, `massa_salarial` | BAIXO-MEDIO | Media |
| Atlas Violencia | `taxa_homicidio_ajustada` | BAIXO - penalizador | Baixa |
| IPEA IVS | `ivs_score` | BAIXO - validacao | Baixa |
| Night Lights | `luminosidade_media` | BAIXO - proxy economico | Media |
| Isochrone | `populacao_12min_real` | MEDIO-ALTO (porem complexo) | Alta |
| ANATEL ERBs | `densidade_erbs` | BAIXO - proxy urbanizacao | Baixa |

---

## 4. Proposta de Modelo de Score Enriquecido

### Score Atual (M1)
```
renda_pct = percentil_nacional(renda_per_capita)         -- IBGE SIDRA municipal
pop_pct   = percentil_nacional(populacao_proxy)           -- IBGE SIDRA municipal

hex_score_estrutural = 100 * (0.60 * renda_pct + 0.40 * pop_pct)
```

### Score Proposto (M1 Enriquecido)
```
# Camada 1: Base estrutural (Censo 2022 setores censitarios)
renda_pct = percentil_nacional(renda_per_capita_setor)    -- IBGE Censo 2022 SETOR
pop_pct   = percentil_nacional(pop_18_45_setor)           -- IBGE Censo 2022 SETOR

hex_score_estrutural = 100 * (0.60 * renda_pct + 0.40 * pop_pct)

# Camada 2: Ajuste por concorrencia real (CNPJ)
n_concorrentes = count(CNPJ CNAE 9313 no raio de 1.5km)
penalidade_concorrencia =
    0   se n_concorrentes == 0
   -2   se n_concorrentes == 1-2
   -5   se n_concorrentes == 3-5
   -10  se n_concorrentes > 5

# Camada 3: Ajuste executivo (mantido + ampliado)
ajuste_executivo =
    +5 se renda_pct >= 0.75 e pop_pct >= 0.75
    +2 se renda_pct >= 0.75
    +1 se pop_pct >= 0.75
    -5 se renda_pct < 0.25
    -3 se pop_pct < 0.25
    +1 se penetracao_plano_saude >= mediana_nacional       -- NOVO: ANS
    -2 se pct_familias_cadunico >= 0.40                    -- NOVO: CadUnico

score_priorizacao = clip(hex_score_estrutural + penalidade_concorrencia + ajuste_executivo, 0, 100)
```

**Ganho esperado:**
- Score estrutural: de ~0 pontos de amplitude intra-cidade para 50-75 pontos
- Concorrencia: de proxy OSM voluntario para registro oficial Receita Federal
- Ajuste executivo: de 2 variaveis para 4 variaveis

---

## 5. Roadmap de Implementacao Sugerido

### Fase A - Quick Wins (1-2 semanas)
1. Download e processamento dos setores censitarios Censo 2022
2. Cruzamento setor censitario x hexagono H3 (spatial join)
3. Substituicao do fallback municipal por setor censitario 2022
4. Validacao: comparar scores antes/depois em cidades-teste (GO, SP, RJ)

### Fase B - Concorrencia Real (1 semana)
1. Consulta Base dos Dados para CNPJ CNAE 9313 ativos
2. Geocoding dos enderecos (CEP -> coordenada)
3. Atribuicao a hexagonos H3
4. Calculo de `n_concorrentes_reais` por hexagono

### Fase C - Validacao Populacional (1 semana)
1. Download Kontur Population Brasil
2. Agregacao H3-r8 -> H3-r7
3. Comparacao com populacao IBGE por hexagono
4. Decisao: usar Kontur como fallback ou como variavel complementar

### Fase D - Enriquecimento Complementar (2 semanas)
1. ANS: download beneficiarios, calculo de penetracao por municipio
2. CNES: download estabelecimentos, contagem por hexagono
3. INEP: download escolas/universidades, contagem por hexagono
4. CadUnico: download familias, calculo de proporcao por municipio
5. Integracao de novas variaveis no ajuste executivo

### Fase E - Modelo Avancado (M2 - futuro)
1. Isochrone analysis com Valhalla
2. Overture Maps para POIs
3. Night Lights para proxy economico
4. Score de competitividade com CNPJ detalhado

---

## 6. Riscos e Mitigacoes

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Setores censitarios 2022 com cobertura incompleta | Baixa | Alto | Manter fallback municipal como backup |
| Geocoding de CNPJ com baixa acuracia | Media | Medio | Usar CEP como proxy (resolucao ~bairro) |
| Kontur desatualizado vs Censo 2022 | Baixa | Baixo | Usar Kontur apenas como validacao, nao como fonte primaria |
| Overhead computacional com setores 2022 | Media | Medio | Processar por UF em paralelo (ja suportado) |
| Overfitting do modelo com muitas variaveis | Media | Alto | Manter score estrutural simples + ajustes modulares |

---

## 7. Conclusao

O Motor de Expansao da Ultra Academia esta bem posicionado para um salto de qualidade significativo sem custo adicional de dados. As tres acoes de maior impacto sao:

1. **Censo 2022 Setores Censitarios** - ja disponivel, resolve o gap principal de granularidade. Ganho esperado: de ~0 para 50-75 pontos de diferenciacao intra-urbana.

2. **CNPJ/CNAE 9313** - registro oficial de academias concorrentes. Substitui a contagem voluntaria do OSM por dados da Receita Federal.

3. **Kontur Population** - dataset H3-nativo gratuito. Validacao cruzada e fallback para populacao.

Com penetracao de apenas 7% no Brasil (vs 25% EUA), o mercado fitness brasileiro tem espaco para crescimento exponencial. A Ultra Academia, com 79 unidades ativas e 80 planejadas, precisa de inteligencia territorial cirurgica para capturar essa demanda nos microterritorios certos. As fontes mapeadas nesta pesquisa fornecem a materia-prima para isso.

---

## Referencias e Links de Acesso

### Fontes Primarias
- IBGE Censo 2022: `ibge.gov.br/estatisticas/sociais/trabalho/22827-censo-demografico-2022.html`
- IBGE Downloads: `downloads.ibge.gov.br`
- IBGE SIDRA: `sidra.ibge.gov.br`
- Base dos Dados: `basedosdados.org`

### Fontes Demograficas e Populacionais
- Kontur Population Brasil (HDX): `data.humdata.org/dataset/kontur-population-brazil`
- Meta HRSL Brasil (HDX): `data.humdata.org/dataset/brazil-high-resolution-population-density-maps-demographic-estimates`
- GHSL (Copernicus): `human-settlement.emergency.copernicus.eu/download.php`
- WorldPop: `data.humdata.org/dataset/worldpop-population-density-for-brazil`

### Fontes de Negocio e Concorrencia
- CNPJ Dados Abertos: `dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj`
- Mapa de Empresas: `gov.br/empresas-e-negocios/pt-br/mapa-de-empresas`
- CNAE 9313: `concla.ibge.gov.br/busca-online-cnae.html?subclasse=9313100`
- Overture Maps: `overturemaps.org/download/`

### Fontes Socioeconomicas
- ANS Dados Abertos: `gov.br/ans/pt-br/acesso-a-informacao/perfil-do-setor/dados-abertos-1`
- CNES (OpenDataSUS): `opendatasus.saude.gov.br/dataset/cnes`
- RAIS/CAGED: `gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho/microdados-rais-e-caged`
- CadUnico: `dados.gov.br/dados/conjuntos-dados/cadastro-unico---familiaspessoas-por-faixas-de-renda-per-capita`
- IPEA IVS: `ivs.ipea.gov.br`
- Atlas Violencia: `ipea.gov.br/atlasviolencia/downloads`

### Fontes Educacionais
- INEP Microdados: `gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar`

### Fontes de Infraestrutura
- ANATEL ERBs: `gov.br/anatel/pt-br/regulado/outorga/telefonia-movel/estacoes-radio-base`
- OpenCelliD: `opencellid.org/downloads.php`
- VIIRS Night Lights: `eogdata.mines.edu/products/vnl/`

### Fontes de Mobilidade
- Strava Metro: `metro.strava.com`
- GTFS Feeds: `transitfeeds.com`
- Valhalla Isochrone: `valhalla.github.io/valhalla/api/isochrone/api-reference/`

### Mercado Fitness
- ACAD Brasil: `acadbrasil.com.br`
- Fitness Brasil / IHRSA: `fitnessbrasil.com.br`
- IHRSA Global: `healthandfitness.org`
