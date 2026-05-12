# GPT-PESQUISA

Pesquisa orientada para aumentar a precisao e a confiabilidade da fase M1 do motor de expansao da Ultra Academia, com foco em enriquecimento territorial por H3 para expansao de academias.

Data de consolidacao: 2026-04-06  
Contexto lido: `CLAUDE.md`, `projeto_lifetime_ultra_v3.docx` e `Documentacao_Fluxo_Analises_Ponto_Ultra.docx`

## 1. Leitura executiva

A principal fragilidade do M1 hoje nao e o score em si; e a granularidade espacial.

O proprio `CLAUDE.md` registra que:

- o M1 oficial fecha com fallback municipal do IBGE
- o experimento censitario 2010 mostrou ganho intraurbano muito forte
- o pipeline oficial precisa continuar simples, reproduzivel, auditavel e em Parquet

Conclusao decisoria:

1. O caminho de maior ROI para o M1 nao e trocar o score oficial agora.
2. O caminho correto e enriquecer melhor os hexagonos com camadas espaciais mais finas e manter `score_priorizacao` como contrato oficial.
3. A melhor estrategia e montar uma pilha em camadas:
   `IBGE oficial forte -> complementos abertos robustos -> fontes municipais/pilotos`.

Minha recomendacao objetiva e:

- manter `score_priorizacao` e os artefatos oficiais intactos no M1 canonico
- criar uma camada paralela de enriquecimento territorial de alta granularidade
- promover para o pipeline oficial apenas o que tiver:
  cobertura nacional aceitavel, refresh previsivel, licenca clara, custo computacional controlado e rastreabilidade por hexagono

## 2. O que o contexto Ultra muda na pesquisa

O `projeto_lifetime_ultra_v3.docx` muda bastante o jeito correto de pensar expansao.

Nota metodologica:

- quando eu conecto os achados de lifetime a variaveis territoriais, isso e inferencia analitica orientada a negocio
- nao e prova causal fechada
- a promocao dessas hipoteses para score oficial deve depender de validacao com o historico das unidades Ultra

O que ele sugere:

- frequencia de uso e o preditor mais forte de churn
- o mes 3 e a principal janela critica de cancelamento
- unidades variam bastante em churn e receita em risco
- mix de plano importa muito: GOLD concentra mais risco; ULTRA360 e GOLDPRO parecem proteger melhor
- mulheres 18-24 aparecem como segmento proporcionalmente mais sensivel

Inferencia importante:

- para expansao, nao basta buscar "mais populacao"
- precisamos buscar territorios com maior chance de gerar frequencia recorrente, habito e LTV saudavel
- isso puxa a analise territorial para variaveis de:
  acessibilidade, conveniencia, densidade residencial real, densidade de trabalho/estudo, qualidade do entorno urbano, concorrencia real e perfil demografico aderente

O documento de fluxo operacional tambem importa:

- ha analise em massa semanal
- ha urgencias fora do fluxo
- logo, a pilha de dados precisa ser precomputada, cacheada e parquetizada
- depender de API publica ao vivo durante quinta/sexta e uma ma ideia operacional

## 3. Tese central para o M1.1

Se o objetivo e "expansao exponencial e saudavel", o H3 precisa capturar 5 dimensoes:

1. Demanda residente real
2. Demanda flutuante / diurna
3. Concorrencia e saturacao
4. Acessibilidade e friccao de uso
5. Viabilidade urbana do entorno

Hoje o M1 oficial captura muito bem a parte macro de renda + populacao, mas ainda fraco em:

- heterogeneidade intraurbana
- competicao real
- polos geradores de fluxo
- walkability / transit / conveniencia
- diferenca entre area residencial consolidada vs area industrial, rural, vazia ou de baixa ativacao urbana

## 4. Recomendacao de arquitetura de dados

### 4.1 Regra de governanca

Separar as camadas em 3 niveis:

- `gold`: fonte oficial / auditavel / nacional / estavel
- `silver`: fonte aberta robusta, boa cobertura, mas nao oficial brasileira
- `bronze`: fonte fragmentada, municipal, oportunistica ou de piloto

### 4.2 Regra de promocao

Uma camada so deve entrar no score executivo se passar nestes criterios:

- cobertura nacional suficiente
- atualizacao previsivel
- licenca clara
- reproducao em lote
- latencia operacional baixa
- rastreabilidade por linha
- coerencia com o contrato do M1

### 4.3 Regra espacial

Recomendacao forte:

- manter o output oficial em `H3_RESOLUTION = 7`
- calcular camadas brutas em granularidade mais fina quando existir dado melhor
- depois agregar para H3-r7 com metadados de cobertura e qualidade

Exemplo:

- setor censitario 2022 -> cruza com H3
- grade estatistica 200m -> agrega para H3
- building footprints / Open Buildings -> agrega para H3
- CNEFE / pontos de endereco -> agrega para H3

Isso preserva o contrato do M1 e aumenta muito a qualidade da informacao intraurbana.

## 5. Fontes e APIs pesquisadas

### 5.1 Tier A - prioridade maxima para o M1.1

| Fonte | Tipo | Granularidade util | Como ajuda o H3 | Confiabilidade | Recomendacao |
| --- | --- | --- | --- | --- | --- |
| IBGE Setor Censitario 2022 + malhas | dado oficial | setor / hex | renda, populacao, domicilios, idade, densidade real | muito alta | entrar primeiro |
| IBGE Grade Estatistica 2022 | dado oficial | 200m urbano / 1km rural | redistribuir populacao e domicilios com estabilidade espacial | muito alta | entrar primeiro |
| IBGE CNEFE + coordenadas dos enderecos | dado oficial | ponto / grade / hex | densidade residencial e nao residencial muito superior ao municipio | muito alta | entrar primeiro |
| IBGE Entorno dos domicilios | dado oficial | setor / microarea | walkability, iluminacao, calcada, pavimentacao, ponto de onibus, arborizacao | muito alta | entrar primeiro |
| Receita Federal - CNPJ dados abertos | dado oficial | estabelecimento | concorrencia real por CNAE, densidade comercial, mix economico | alta | entrar primeiro |
| OSM / Overpass | API aberta | ponto / hex | academias, anchors, vias, estacionamento, transporte, retail | media-alta | usar como complementar, nao como unica verdade |
| INEP - Censo Escolar / Educacao Superior | dado oficial | estabelecimento / municipio | polos de publico jovem e fluxo recorrente | alta | entrar primeiro |

### 5.2 Tier B - complementos muito fortes

| Fonte | Tipo | Granularidade util | Como ajuda o H3 | Confiabilidade | Recomendacao |
| --- | --- | --- | --- | --- | --- |
| MapBiomas | dado aberto nacional | raster / poligono / hex | urbanizacao, uso do solo, consolidacao urbana, filtros de inviabilidade | alta | entrar em seguida |
| Overture Maps Places + Buildings | dado aberto global | ponto / poligono / hex | places, edificios, built form, melhoria da leitura urbana | media-alta | piloto forte |
| Google Open Buildings | dado aberto global | building footprint | densidade construida e area edificada | media-alta | usar como proxy de forma urbana |
| WorldPop | raster aberto | 100m / hex | redistribuicao espacial de populacao | media | usar como auxiliar, nao como score oficial bruto |
| GHSL | raster aberto | grid / hex | built-up, settlement intensity, urbanicity | media-alta | bom para filtros e priors |
| VIIRS Nighttime Lights | raster aberto | grid / hex | atividade noturna/comercial como proxy complementar | media | usar como suporte |

### 5.3 Tier C - usar em piloto ou por cidade

| Fonte | Tipo | Granularidade util | Como ajuda o H3 | Risco operacional | Recomendacao |
| --- | --- | --- | --- | --- | --- |
| GTFS municipais | feed aberto fragmentado | parada / linha / isocrona | acessibilidade por transporte publico | alto | piloto por cidade |
| Zoneamento / IPTU / alvara municipal | dado aberto local | lote / zona / quadra | viabilidade imobiliaria e regulatoria | alto | piloto por capital |
| RAIS / Novo CAGED | microdado oficial | estabelecimento ou municipio, depende do recorte | proxy de emprego e fluxo diurno | medio | usar primeiro em nivel municipal / cidade piloto |
| Bases municipais de seguranca, enchente, uso do solo fino | dado aberto local | bairro / setor / lote | risco local e filtros de viabilidade | alto | apenas onde houver padrao minimo |

## 6. Detalhamento das fontes mais importantes

### 6.1 IBGE - espinha dorsal oficial do enriquecimento

O IBGE ja e a base oficial do M1. A pesquisa confirma que ele deve continuar sendo a espinha dorsal.

Camadas mais valiosas:

- API de Localidades
- API de Malhas
- SIDRA
- Malha de Setores Censitarios 2022
- Grade Estatistica 2022
- CNEFE 2022
- Coordenadas geograficas dos enderecos
- Caracteristicas urbanisticas do entorno dos domicilios

Por que isso e decisivo:

- e oficial
- e auditavel
- tem cobertura nacional
- conversa naturalmente com a governanca do M1

Uso recomendado:

- substituir o maximo possivel do fallback municipal por setor / grade / endereco
- usar Grade Estatistica 2022 como ponte entre o mundo oficial IBGE e a malha H3
- usar CNEFE e coordenadas para criar densidade de enderecos, intensidade residencial, intensidade nao residencial e sinais de consolidacao urbana

Observacao importante:

- a Grade Estatistica 2022 foi atualizada com dados do Censo 2022 em 12/06/2025
- nas areas urbanas, trabalha com celulas de 200m x 200m
- isso e muito aderente para redistribuicao espacial dentro do H3

Aplicacoes concretas no H3:

- `pop_residente_grade`
- `domicilios_grade`
- `dens_enderecos_residenciais_cnefe`
- `dens_enderecos_nao_residenciais_cnefe`
- `intensidade_urbana_ibge`
- `indice_entorno_urbano_ibge`

### 6.2 Receita Federal - CNPJ dados abertos

Esta e uma das melhores camadas para resolver concorrencia e vitalidade economica real.

Por que ela e forte:

- e fonte oficial
- tem atualizacao recorrente
- tem CNAE
- permite contar concorrentes reais, nao apenas POIs cadastrados em mapa

Para academias, o principal CNAE e:

- `9313-1/00` - atividades de condicionamento fisico

Mas o valor vai muito alem de contar academias.

Tambem permite:

- densidade de comercio e servicos
- presenca de anchors economicos
- mix de atividade economica do entorno
- proxy de fluxo diurno, especialmente se combinado com CNEFE, OSM e RAIS/CAGED

Risco tecnico:

- a base e bulk, nao API pronta para query espacial
- exige ETL, padronizacao e geocodificacao

Recomendacao:

- nao usar geocodificacao online em lote
- usar pipeline de geocodificacao offline / snapshot
- para M1.1, comecar com:
  CNPJ de academias + grandes anchors + densidade geral de estabelecimentos

Campos sugeridos:

- `n_academias_cnpj_1km`
- `n_academias_cnpj_2km`
- `dens_estabelecimentos_cnpj`
- `mix_servicos_cnpj`
- `anchor_comercial_score_cnpj`

### 6.3 OSM / Overpass / Nominatim

OSM continua muito util, mas precisa ser reposicionado.

Papel correto:

- complementar CNPJ
- melhorar cobertura de POIs e anchors
- enriquecer rede viaria, transporte, retail, estacionamento e concorrencia observavel

Nao deve ser:

- unica fonte de concorrencia
- dependencia online do fechamento nacional

Pontos de atencao:

- Overpass publico e bom para prototipo e lotes pequenos
- para escala nacional, o ideal e trabalhar com snapshots / extracts
- a politica publica do Nominatim nao e apropriada para batch pesado

Uso recomendado:

- manter OSM como `silver`
- usar principalmente para:
  academias, supermercados, shoppings, farmacias, restaurantes, escolas, paradas, vias estruturais, estacionamento
- consolidar com CNPJ para reduzir falso negativo e falso positivo

Campos sugeridos:

- `n_academias_osm_1km`
- `n_anchors_osm_1km`
- `score_vitalidade_osm`
- `paradas_transporte_osm`
- `estacionamento_osm`
- `road_access_osm`

### 6.4 INEP - educacao como polo gerador de demanda

Para academias, polos de estudo importam muito.

Especialmente para:

- publico 18-24
- fluxo diurno recorrente
- areas com alta rotacao e potencial de novos alunos

Recomendacao:

- usar Censo Escolar e Censo da Educacao Superior como camada estruturante de demanda jovem
- combinar com renda e walkability para evitar supervalorizar areas com publico jovem, mas baixa retencao

Aplicacoes no H3:

- `n_escolas_1km`
- `n_ies_2km`
- `matriculas_educacao_basica_prox`
- `matriculas_superior_prox`
- `indice_demanda_jovem_educacional`

### 6.5 MapBiomas

MapBiomas e provavelmente a melhor camada nacional aberta para separar:

- urbano consolidado
- urbano disperso
- area nao urbanizada
- agua
- vegetacao
- agricultura / pastagem

Isso e muito importante porque evita pontuar como oportunidade:

- hexagono urbanisticamente inviavel
- area periurbana vazia
- zona industrial pesada
- area com baixa consolidacao urbana

Aplicacoes no H3:

- `pct_urbanizado_mapbiomas`
- `classe_dominante_mapbiomas`
- `indice_consolidacao_urbana`
- `filtro_inviabilidade_uso_solo`

### 6.6 Overture / Open Buildings / GHSL / WorldPop

Essas fontes nao devem substituir o IBGE oficial.

Elas devem ser usadas como reforco espacial para responder:

- onde exatamente a massa urbana se concentra dentro do municipio?
- qual hexagono e mais construido / consolidado?
- como redistribuir populacao quando o dado oficial vier mais agregado?

Uso correto:

- como camada de apoio para dasymetric mapping
- como proxy de intensidade construtiva
- como filtro de urbanizacao real

Uso incorreto:

- substituir renda oficial do IBGE
- virar a fonte primaria do score executivo

Campos sugeridos:

- `building_count_open`
- `building_area_open`
- `built_up_pct`
- `pop_grid_aux`
- `urban_form_score`

### 6.7 VIIRS Nighttime Lights

Night lights sao uteis como proxy de:

- atividade economica
- densidade comercial
- centralidade funcional

Mas eu nao usaria isso como camada principal para academia.

Eu usaria como:

- score auxiliar
- criterio de desempate
- sinal complementar para areas com dados incompletos de comercio

## 7. O que eu colocaria primeiro no algoritmo

Se eu tivesse que escolher a ordem de implementacao para maximizar qualidade decisoria sem estourar escopo, eu faria assim:

### Fase A - ganho rapido e altamente confiavel

1. Promover setor censitario 2022 como primeira tentativa oficial antes do fallback municipal.
2. Integrar Grade Estatistica 2022 para redistribuir populacao e domicilios dentro do municipio.
3. Integrar CNEFE e coordenadas de endereco para densidade residencial / nao residencial.
4. Integrar `entorno dos domicilios` para walkability e conforto urbano.
5. Integrar CNPJ de academias e anchors economicos.
6. Manter OSM como camada complementar de concorrencia e POIs.

### Fase B - ganho espacial forte

1. Integrar MapBiomas para filtro de urbanizacao.
2. Integrar Overture / Open Buildings / GHSL para built form.
3. Integrar WorldPop como auxiliar de redistribuicao quando faltar granularidade oficial.
4. Integrar INEP para polos de estudo.

### Fase C - aprofundamento de cidade piloto

1. GTFS e acessibilidade por transporte publico.
2. Zoneamento, IPTU, alvara e risco urbano por cidade.
3. RAIS/CAGED para fluxo diurno e emprego.

## 8. Como isso conversa com o lifetime da Ultra

O lifetime interno da Ultra sugere 4 ajustes conceituais para a expansao:

### 8.1 Nao otimizar so para aquisicao

Como o churn precoce e muito forte, o territorio precisa ser bom para uso recorrente, nao apenas para gerar visitas no primeiro mes.

Inferencia:

- proximidade funcional
- facilidade de acesso
- entorno caminhavel
- presencia de rotina diaria

devem ter mais peso do que pura populacao bruta.

### 8.2 Publico jovem precisa vir com filtro de qualidade

Ha sinal de risco proporcional em mulheres 18-24.

Logo:

- areas com muito estudante / jovem adulto sao valiosas
- mas precisam ser filtradas por renda, acesso, mix urbano e capacidade de recorrencia

### 8.3 Unidade vencedora nao e so "onde vende", e "onde retém"

Recomendacao metodologica:

- usar o proprio historico de unidades Ultra para criar um perfil de catchment vencedor
- correlacionar features espaciais do entorno com:
  churn, lifetime previsto, LTV e mix de plano

Isso e extremamente valioso para a fase seguinte, porque transforma expansao em:

- `demanda potencial x capacidade de retencao esperada`

e nao apenas:

- `renda x populacao`

### 8.4 Frequencia sugere importancia de acessibilidade

Se frequencia e o principal preditor de permanencia, entao facilidade de encaixar a academia na rotina diaria tende a ser uma variavel territorial central.

Logo, vale medir:

- proximidade a eixos viarios
- walkability
- pontos de onibus / metro / trem
- presenca de anchors cotidianos
- densidade de enderecos residenciais e nao residenciais

## 9. Features novas recomendadas para o H3

### 9.1 Demanda residente

- `pop_total_setor_2022`
- `pop_18_45_setor_2022`
- `renda_per_capita_setor_2022`
- `domicilios_setor_2022`
- `pop_grade_200m`
- `domicilios_grade_200m`
- `dens_end_residenciais_cnefe`

### 9.2 Demanda diurna / fluxo

- `dens_end_nao_residenciais_cnefe`
- `dens_estabelecimentos_cnpj`
- `n_anchors_comerciais`
- `n_escolas_1km`
- `n_ies_2km`
- `night_lights_mean`

### 9.3 Concorrencia

- `n_academias_cnpj_1km`
- `n_academias_cnpj_2km`
- `n_academias_osm_1km`
- `competicao_fusionada_score`
- `share_academias_premium_proxy`

### 9.4 Acessibilidade e conveniencia

- `indice_entorno_urbano_ibge`
- `road_access_osm`
- `paradas_transporte_osm`
- `estacionamento_osm`
- `tempo_medio_ao_anchor` em piloto por cidade

### 9.5 Forma urbana / viabilidade

- `pct_urbanizado_mapbiomas`
- `classe_uso_solo_dominante`
- `building_count_open`
- `building_area_open`
- `built_up_pct`
- `indice_consolidacao_urbana`

## 10. Modelo operacional recomendado

### 10.1 Nao consultar APIs publicas ao vivo no fechamento nacional

Para a operacao da Ultra, eu recomendo fortemente:

- snapshots versionados
- staging em Parquet por fonte e data
- jobs de refresh separados do job de scoring

Formato ideal:

- `data/raw/<fonte>/ano=YYYY/mes=MM/...`
- `data/staging/<fonte>_h3_res8.parquet`
- `data/staging/<fonte>_h3_res7.parquet`
- `data/staging/brasil_territorial_enriquecido.parquet`

### 10.2 Contract-first

Cada fonte nova deve entrar com colunas de rastreabilidade como:

- `fonte_<camada>`
- `data_referencia_<camada>`
- `metodo_agregacao_<camada>`
- `coverage_pct_<camada>`
- `qualidade_<camada>`

### 10.3 Separar score oficial de score experimental

Sugestao:

- `score_priorizacao` continua oficial
- `score_territorial_expandido` nasce como experimental
- promocao apenas apos validacao de correlacao com:
  performance de unidades, taxa de conversao local, churn e LTV

## 11. O que eu evitaria agora

### 11.1 Evitar dependencia de Nominatim publico

Para lote nacional, isso e fragil e em desacordo com o uso ideal do servico publico.

### 11.2 Evitar usar so OSM para concorrencia

OSM e excelente, mas insuficiente como verdade unica.

### 11.3 Evitar score cheio de sinais fracos

Melhor poucas camadas muito boas do que vinte proxies medianas.

### 11.4 Evitar contaminar o M1 canonico cedo demais

O melhor caminho e:

- enriquecer primeiro
- validar em paralelo
- promover depois

## 12. Priorizacao final

### Top 6 camadas que eu implementaria primeiro

1. IBGE setor censitario 2022
2. IBGE Grade Estatistica 2022
3. IBGE CNEFE + coordenadas dos enderecos
4. IBGE entorno dos domicilios
5. Receita Federal CNPJ dados abertos
6. OSM complementar + INEP

### Top 3 ganhos esperados

1. Diferenciacao intraurbana real dentro do mesmo municipio
2. Melhor leitura de competicao e saturacao
3. Melhor aderencia entre territorio e uso recorrente / LTV saudavel

### Melhor postura para a fase M1

- manter o contrato oficial
- criar uma camada `territorial_expandida`
- validar contra historico de unidades Ultra
- promover apenas o que provar ganho real

## 13. Recomendacao decisoria final

Se o objetivo e deixar o M1 mais preciso e confiavel sem perder governanca, a direcao certa e:

1. Fortalecer o M1 com mais IBGE espacial fino antes de qualquer outra coisa.
2. Usar CNPJ para concorrencia e vitalidade economica real.
3. Usar OSM como complemento estrutural e nao como pilar unico.
4. Adicionar MapBiomas + built form para evitar falso positivo urbano.
5. Ligar tudo ao historico de lifetime / churn / LTV das unidades Ultra para calibrar o que realmente e "territorio saudavel".

Em uma frase:

o proximo salto do M1 nao depende de um score mais sofisticado; depende de um H3 muito mais bem descrito.

## 14. Proposta de proxima entrega pratica

Se eu fosse transformar esta pesquisa em execucao, a proxima sprint seria:

1. Definir o dicionario de colunas novas do H3 enriquecido.
2. Implementar ingestao de:
   setor 2022, grade 2022, CNEFE, entorno, CNPJ-academias, OSM-academias.
3. Gerar um `parquet` experimental nacional enriquecido.
4. Medir:
   cobertura, custo computacional, ganho de diferenciacao e correlacao com unidades reais Ultra.
5. So depois discutir promocao para o score executivo.

## 15. Fontes pesquisadas

### IBGE

- API Localidades: https://servicodados.ibge.gov.br/api/docs/localidades
- API Malhas: https://servicodados.ibge.gov.br/api/docs/malhas?versao=3
- API SIDRA: https://apisidra.ibge.gov.br/
- Censo Demografico 2022 - portal do produto: https://www.ibge.gov.br/estatisticas/sociais/saude/22827-censo-demografico-2022.html
- Malhas de Setores Censitarios / divisoes intramunicipais: https://www.ibge.gov.br/geociencias/organizacao-do-territorio/estrutura-territorial/26565-malhas-de-setores-censitarios-divisoes-intramunicipais.html
- Grade Estatistica 2022 - atualizacao com dados do Censo 2022: https://agenciadenoticias.ibge.gov.br/agencia-noticias/2012-agencia-de-noticias/noticias/43687-ibge-atualiza-grade-estatistica-com-dados-do-censo-demografico-2022

### Receita Federal

- Dados abertos de cadastros: https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/dados-abertos/cadastros
- Metadados do conjunto CNPJ: https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica-cnpj

### Educacao

- INEP - microdados Censo Escolar: https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar
- INEP - microdados Censo da Educacao Superior: https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-da-educacao-superior

### OSM / Overture

- Overpass API: https://wiki.openstreetmap.org/wiki/Overpass_API
- Politica de uso do Nominatim: https://operations.osmfoundation.org/policies/nominatim/
- Tag `amenity=gym`: https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dgym
- Tag `leisure=fitness_centre`: https://wiki.openstreetmap.org/wiki/Tag:leisure%3Dfitness_centre
- Overture Places: https://docs.overturemaps.org/guides/places/
- Overture Buildings: https://docs.overturemaps.org/guides/buildings/

### Uso do solo / forma urbana / grids

- MapBiomas - downloads: https://brasil.mapbiomas.org/downloads/
- MapBiomas - colecoes: https://brasil.mapbiomas.org/colecoes-mapbiomas/
- Google Open Buildings: https://sites.research.google/open-buildings/
- WorldPop Brasil 100m: https://hub.worldpop.org/geodata/summary?id=72639
- GHSL collection: https://data.jrc.ec.europa.eu/collection/ghsl
- VIIRS Nighttime Lights: https://eogdata.mines.edu/products/vnl/

### Trabalho / atividade economica

- Microdados RAIS e CAGED: https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho/microdados-rais-e-caged

## 16. Fechamento

Decisao recomendada:

- `GO` para uma trilha de enriquecimento territorial M1.1
- `NAO GO` para mexer no score oficial antes de enriquecer e validar

Melhor aposta de qualidade:

- IBGE fino + CNPJ + OSM complementar + forma urbana aberta

Melhor aposta de negocio:

- usar essas camadas para encontrar territorios que nao so compram, mas permanecem.
