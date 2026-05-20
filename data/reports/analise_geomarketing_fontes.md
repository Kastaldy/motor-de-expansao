# Analise de Viabilidade — Funcionalidades GeoMarketing
> Data: 2026-05-19 | Autor: Analise Claude Code | v2 — PEA composta e passantes
> Contexto: reuniao com plataforma de GeoMarketing; avaliar o que pode ser absorvido pela ferramenta

---

## Resumo Executivo

A reuniao trouxe duas ideias centrais: **mapas de calor intraurbanos** com granularidade de setor censitario e **enriquecimento por novas fontes** (Receita Federal, MTE, PNAD, POF). A discussao posterior adicionou duas perguntas criticas: granularidade do PEA por setor e viabilidade de estimar passantes.

Conclusoes principais:

- **Densidade e Renda** ja existem no repositorio em nivel de setor censitario; o trabalho e de dashboard, nao de pipeline.
- **PEA residencial por idade** e computavel agora com dados locais (grupos etarios 15-64 do arquivo `demografia`). PEA real (ocupados) exige Censo Amostra nao disponivel localmente.
- **PEA de trabalhadores nao residentes** (pendulares, o problema do centro comercial) nao existe em fonte publica intraurbana; requer modelagem por proxy.
- **Passantes** verdadeiros dependem de dado de telco/mobile (privado). Com dados publicos, o proxy mais solido e CNPJ comercial + GTFS (transporte publico).
- **CNPJ Receita Federal** continua sendo a fonte de maior valor estrategico: amplia concorrentes mapeados e e o principal insumo para o proxy de passantes.
- **PNAD e POF** nao tem granularidade espacial suficiente para mapas; uso analitico e de calibracao.

Nenhuma fonte nova deve alterar `score_priorizacao`, `hex_score_estrutural` nem os artefatos oficiais do M1.

---

## 1. O que ja temos vs o que foi apresentado

| Funcionalidade | Status atual | Fonte ja disponivel |
|---|---|---|
| Mapa de calor — Densidade | **Disponivel** | `censo2022_setores_calibrado.parquet`: `pop_total_setor_2022` |
| Mapa de calor — Renda | **Disponivel** | `censo2022_setores_calibrado.parquet`: `renda_per_capita_setor_2022_calibrada` |
| PEA por idade (proxy) | **Computavel agora** | `Agregados_por_setores_demografia_BR.csv` local: V01034–V01039 (faixas 15-64) |
| Mapa de calor — Trabalhadores | **Parcial** | RAIS municipal + interpolacao; PEA nao residente requer modelagem |
| Passantes (footfall) | **Nao disponivel direto** | Proxy publico: CNPJ comercial + GTFS |
| Concorrentes mapeados | **Disponivel** | 28 redes em `concorrentes_mapeados.parquet` |

---

## 2. Mapas de Calor — Analise por Tipo

### 2.1 Densidade Populacional

**Viabilidade: ALTA — dados prontos**

- Coluna: `pop_total_setor_2022` em `censo2022_setores_calibrado.parquet`
- Granularidade: setor censitario IBGE 2022 — cobertura 27 UFs
- Join ao H3 res7: materializado em `censo2022_setores_h3_res7.parquet`
- O que falta: layer no Streamlit com escala de cor

**Esforco**: 1-2 dias (frontend apenas)

---

### 2.2 Renda per Capita

**Viabilidade: ALTA — dados prontos**

- Coluna: `renda_per_capita_setor_2022_calibrada` em `censo2022_setores_calibrado.parquet`
- Fonte: Censo 2022 calibrado (k=1.02, validado)
- Fallback municipal para setores sem dado (AM, RR, zonas de supressao IBGE)

**Esforco**: 1-2 dias (frontend apenas)

---

### 2.3 PEA — Populacao Economicamente Ativa

**Viabilidade: MEDIA-ALTA com importante ressalva de composicao**

Esta e a camada mais complexa. O PEA de uma regiao tem tres componentes com disponibilidades diferentes:

#### Componente A — PEA residente por faixa etaria (disponivel agora)

- Fonte: `Agregados_por_setores_demografia_BR.csv` (ja no repo local)
- Variaveis: V01034+V01035+V01036+V01037+V01038+V01039 (15-64 anos, ambos os sexos)
- O que e: populacao em **idade economicamente ativa** que **mora** no setor
- O que nao e: nao diz quem de fato trabalha (isso e Censo Amostra); nao inclui quem trabalha la mas mora em outro lugar
- Granularidade: **setor censitario** — a mais fina disponivel publicamente
- Limitacao critica: em um centro comercial, esta variavel captura poucos residentes e ignora os milhares que chegam diariamente para trabalhar

#### Componente B — Trabalhadores formais no local de trabalho (RAIS)

- Fonte: RAIS 2022 por estabelecimento (endereço do local de trabalho, nao do trabalhador)
- Cobre: CLT, servidor publico, estagiario (vinculo tipo 80), temporario
- Granularidade: **municipal** — sem coordenada por estabelecimento no arquivo publico
- Interpolacao necessaria: distribuir os vinculos municipais pelo hexagono proporcional a densidade de estabelecimentos (via CNPJ ou domicilios)
- Esta e a chave para resolver o problema do centro comercial: o saldo positivo de trabalhadores que entram no municipio / regiao aparece aqui

#### Componente C — Inativos com renda (aposentados e pensionistas)

- Fonte: INSS Dados Abertos — beneficiarios ativos por municipio
- URL: `https://www.gov.br/previdencia/pt-br/acesso-a-informacao/dados-abertos/`
- Inclui: aposentadorias por tempo e idade, pensoes por morte, beneficios assistenciais (BPC)
- Granularidade: **municipal** — interpolacao proporcional a populacao 60+ por setor
- Relevancia: em regioes de classe media-alta com populacao mais velha, este componente pode representar 15-25% do PEA ampliado

#### Componente D — Informais (mais dificil)

- Sem fonte publica direta com granularidade intraurbana
- Aproximacao: diferença entre PEA estimada por grupos etarios (componente A) e vinculos RAIS (componente B) por municipio; a sobra e proxy de informalidade
- PNAD Continua publica taxa de informalidade por UF — pode ser usada como coeficiente de ajuste

#### Formula PEA composta proposta

```
PEA_hex_estimada = 
  pop_idade_ativa_residente_hex           # componente A — censo demografia
  + vinculos_formais_hex_interpolado      # componente B — RAIS por estabelecimento
  + inativos_renda_hex_interpolado        # componente C — INSS
  + ajuste_informalidade_uf               # componente D — coeficiente PNAD por UF
  - pop_residente_que_trabalha_fora       # correcao pendular saida (Censo fluxo pendular)
```

**Resposta objetiva sobre granularidade:**
- **Setor censitario real**: apenas o componente A (residentes por idade). Os demais chegam ate o municipio e precisam de interpolacao para o hexagono.
- A interpolacao e defensavel e documentavel, mas precisa ser registrada como `nivel_geografico=municipal_interpolado` nas colunas de auditoria, seguindo o padrao ja adotado no M1.

**Esforco total**: 10-15 dias (pipeline RAIS + INSS + interpolacao + camada Streamlit)

---

### 2.4 Mapa de Calor de Passantes (Fluxo de Pessoas)

**Viabilidade: MEDIA com proxy publico funcional**

Esta e a camada que mais se diferencia de tudo que temos hoje e tambem a que exige mais clareza sobre o que e possivel com dados abertos.

#### O problema central

O **fluxo de passantes** (quantas pessoas transitam por um ponto em determinado periodo) e capturado com precisao por **dados de telco** (sinal de celular anonimizado). Plataformas como GeoFusion quase certamente compram esses dados de operadoras de telefonia. No Brasil, os principais provedores privados sao Serasa Experian, InLoco (agora parte da Foursquare) e dados das proprias operadoras.

Esse dado **nao e publico**.

#### O que o fluxo pendular do Censo captura (e nao captura)

O Censo 2022 publicou dados de "Deslocamento para trabalho e estudo" (fluxo pendular):
- Nivel: **municipal** — sabe-se que X pessoas saem de municipio A para trabalhar em municipio B
- Nao informa: para qual bairro, rua ou hex dentro do municipio B essas pessoas vao
- Util para: estimar o saldo liquido de trabalhadores que um municipio recebe (insumo do componente B do PEA)
- Nao util para: criar mapa de calor intraurbano de passantes

#### Proxy publico mais solido para passantes intraurbanos

Combinando tres fontes abertas, e possivel criar um **indice de atividade e fluxo** por hexagono que se aproxima do conceito de passantes:

**Camada 1 — Densidade de estabelecimentos comerciais (CNPJ)**
- Onde ha mais CNPJs ativos de varejo, alimentacao, servicos → mais pessoas transitam
- CNAEs relevantes: comercio varejista (47xx), alimentacao (56xx), servicos pessoais (96xx)
- Granularidade: CEP → geocodificavel para hexagono
- Limitacao: captura onde as pessoas *vao*, nao quem *passa*

**Camada 2 — Infraestrutura de transporte publico (GTFS)**
- GTFS (General Transit Feed Specification): formato padrao de dados de onibus/metro/trem publicado pelas cidades
- Disponivel para: Sao Paulo, Rio de Janeiro, Belo Horizonte, Curitiba, Porto Alegre, Recife, Fortaleza e outras capitais
- O que oferece: rotas com frequencia, pontos de parada com localizacao precisa
- Logica: hex com mais linhas de onibus + maior frequencia = mais pessoas transitando
- Agregacao: `n_linhas_passando`, `frequencia_media_veiculos_hora`, `n_paradas` por hexagono

**Camada 3 — POIs OSM (pontos de interesse)**
- Contagem de POIs comerciais, culturais, de saude e lazer por hexagono
- Proxy de atividade urbana — ja temos suporte tecnico a OSM no repositorio
- Mais denso em centros comerciais, menos denso em areas residenciais puras

**Indice composto sugerido:**
```
indice_fluxo_proxy = 
  0.5 * percentil(n_cnpj_comercial_hex) 
  + 0.3 * percentil(n_linhas_gtfs_hex) 
  + 0.2 * percentil(n_poi_osm_hex)
```

**Limitacoes do proxy:**
- Captura infraestrutura de fluxo, nao fluxo real
- Nao tem variacao horaria (dia vs noite, semana vs fim de semana)
- Centros comerciais novos podem ter baixa densidade CNPJ/GTFS no inicio
- Zonas industriais concentram trabalhadores sem POIs de varejo → subestimadas

**O que nao conseguimos replicar sem dado de telco:**
- Fluxo por hora do dia
- Perfil demografico de quem transita (idade, renda)
- Sazonalidade semanal e mensal

**Esforco estimado**: 12-18 dias (CNPJ + GTFS das principais cidades + OSM + composite index + camada Streamlit)

---

## 3. Novas Fontes de Dados

### 3.1 Receita Federal — Base CNPJ

**Valor estrategico: MUITO ALTO**

Alem de expandir o mapeamento de concorrentes, o CNPJ e o insumo central para o proxy de passantes e a interpolacao do RAIS (onde estao os estabelecimentos empregadores dentro do municipio).

- URL: `https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica-cnpj`
- Volume: ~50 GB comprimido (arquivos por entidade — empresas, socios, estabelecimentos)
- O arquivo de **estabelecimentos** e o mais util: tem CNPJ raiz + CEP + situacao + CNAE + porte
- Geocodificacao: CEP → lat/lng via tabela IBGE de CEPs ou ViaCEP; precisao suficiente para res7

**Usos no Motor:**
| Uso | Como | Impacto |
|---|---|---|
| Ampliar concorrentes | CNAEs 9312-0/00 e 9313-8/00 ativos | Melhora `oferta_efetiva_disponivel` |
| Proxy de passantes | Densidade de CNAEs comerciais por hex | Camada de fluxo intraurbano |
| Interpolacao RAIS | Distribuir vinculos municipais pelo hex via densidade de estabelecimentos empregadores | Melhora PEA nao residente |
| Vitalidade economica | Crescimento de CNPJs ativos por hex ao longo do tempo | Indicador de expansao/retracao de mercado |

**Esforco**: 10-15 dias

---

### 3.2 GTFS — Transporte Publico Municipal

**Valor estrategico: ALTO para passantes / MEDIO para mercado geral**

- Formato: arquivos CSV padrao (routes, stops, trips, stop_times, frequencies)
- Cidades com GTFS publico: SP, RJ, BH, Curitiba, Porto Alegre, Recife, Fortaleza, Brasilia e outras
- Processamento: contar linhas e frequencia por hex; leve em termos de volume
- Combinado com CNPJ forma o proxy de passantes mais solido disponivel publicamente

**Esforco**: 5-8 dias (download + parse + join hexagono para principais capitais)

---

### 3.3 Ministerio do Trabalho — RAIS

**Valor estrategico: MEDIO-ALTO para PEA nao residente**

- RAIS por estabelecimento: total de vinculos por CNPJ de estabelecimento
- O CNPJ do estabelecimento tem CEP → geocodificavel para hexagono (sinergia com CNPJ RF)
- Cobre: CLT, servico publico, estagiario
- Nao cobre: MEI, autonomo, informal

**Aplicacao no PEA composto:**
```
vinculos_formais_hex = 
  RAIS_vinculos[CNPJ_estabelecimento] JOIN CNPJ_RF[CEP] JOIN hex_id
```

Isso resolve o problema do centro comercial: os vinculos aparecem no endereco do estabelecimento, nao do trabalhador.

**Esforco**: 5-8 dias

---

### 3.4 INSS — Beneficiarios Ativos

**Valor estrategico: MEDIO para PEA ampliado**

- Publica mensalmente: total de beneficiarios por municipio e tipo de beneficio
- Tipos relevantes: aposentadoria por tempo (B41), aposentadoria por idade (B42), pensao por morte (B21), BPC (B87/B88)
- Interpolacao para hex: proporcional a populacao 60+ por setor (temos esse dado no arquivo `demografia`)
- Util em regioes de perfil mais velho: adiciona poder de compra nao capturado pelo M1 atual

**Esforco**: 3-4 dias

---

### 3.5 PNAD — Uso como Calibrador de Informalidade

**Granularidade espacial: UF apenas — nao usar para mapas**

- PNAD Continua publica taxa de informalidade por UF e Regiao Metropolitana
- Uso no Motor: coeficiente ajustador do componente D da PEA composta
- Acesso via API IBGE SIDRA ja usada no projeto

**Esforco**: 2 dias (coeficiente por UF, sem pipeline espacial)

---

### 3.6 POF — Calibrador de SAM Fitness

**Granularidade espacial: UF apenas — nao usar para mapas**

- POF 2017-2018: gasto medio com academias por quintil de renda e UF
- Defasagem de ~8 anos; estrutura relativa (quem gasta mais vs menos) ainda e valida
- Uso: calibrar `sam_fitness_potencial` — converter penetracao demografica em propensao real de consumo
- Proxima edicao (2023-2024) com publicacao parcial em 2025 pode atualizar esse coeficiente

**Esforco**: 2-3 dias (coeficientes por UF/quintil)

---

## 4. Resposta Objetiva — Perguntas da Reuniao

### Pergunta: PEA tem granularidade de setor censitario?

| Componente PEA | Granularidade real | Fonte | Temos localmente? |
|---|---|---|---|
| Populacao em idade ativa (15-64 anos) | **Setor censitario** | Censo demografia | **SIM** |
| Trabalhadores ocupados (PEA real) | Municipio (Amostra Censo por setor nao esta nos nossos arquivos locais) | Censo Amostra | NAO |
| Trabalhadores formais no local de trabalho | Municipio (interpolavel via CNPJ) | RAIS + CNPJ RF | Requer pipeline |
| Inativos com renda | Municipio (interpolavel via pop 60+) | INSS | Requer pipeline |
| Informais | Estimativa por UF | PNAD | Requer pipeline |

**Resumo**: o dado mais fino que existe publicamente para PEA real (ocupados) chega ao nivel de setor via Censo Amostra, mas nossa copia local nao tem esse arquivo. Os componentes de trabalhadores nao residentes e inativos chegam ate o municipio e precisam de interpolacao para o hexagono.

---

### Pergunta: Fluxo pendular consegue estimar passantes?

**Resposta curta: nao diretamente — e uma limitacao de granularidade e conceito.**

| Abordagem | O que captura | Granularidade | Disponibilidade |
|---|---|---|---|
| Fluxo pendular Censo | Deslocamento entre municipios para trabalho/estudo | Municipal | Publica |
| Dados de telco (GeoFusion) | Presenca real de pessoas por hora | Hexagono / quarteira | Privado (pago) |
| CNPJ comercial (proxy) | Onde ha estabelecimentos = onde ha fluxo | CEP → hexagono | Publica |
| GTFS transporte publico | Infraestrutura de deslocamento intraurbano | Parada / hexagono | Publica (por cidade) |
| OSM POIs (proxy) | Atividade urbana como correlato de fluxo | Ponto / hexagono | Publica |

O fluxo pendular e util como insumo do **PEA nao residente** (componente B): saber quantas pessoas chegam ao municipio oriundas de outros municipios para trabalhar. Para distribuir essas pessoas dentro do municipio, o CNPJ de estabelecimentos e o proxy mais preciso disponivel publicamente.

---

## 5. Matriz de Priorizacao Atualizada

| Funcionalidade | Valor | Esforco | Dado disponivel localmente | Recomendacao |
|---|---|---|---|---|
| Mapa calor Densidade | Alto | 1-2d | **SIM** | Implementar agora |
| Mapa calor Renda | Alto | 1-2d | **SIM** | Implementar agora |
| PEA por idade (proxy) | Alto | 2-3d | **SIM** (demografía) | Implementar agora |
| CNPJ Receita Federal | Muito alto | 10-15d | NAO | Proximo ciclo prioritario |
| GTFS cidades | Alto | 5-8d | NAO | Proximo ciclo |
| RAIS + INSS (PEA completo) | Medio-alto | 8-12d | NAO | Proximo ciclo |
| Proxy passantes (CNPJ+GTFS) | Alto | 12-18d | NAO | Apos CNPJ e GTFS prontos |
| POF calibracao SAM | Medio | 2-3d | NAO | Backlog |
| PNAD informalidade | Baixo | 2d | NAO | Backlog |

---

## 6. Roadmap Sugerido

### Fase 1 — Rapida (ciclo atual, 5-7 dias total)
1. Layer mapa de calor **Densidade** no Streamlit — `pop_total_setor_2022`
2. Layer mapa de calor **Renda** — `renda_per_capita_setor_2022_calibrada`
3. Layer **PEA por idade** — soma V01034–V01039 do arquivo `demografia` local (populacao 15-64 por setor)
4. Toggle por tipo de camada no sidebar
5. Zero pipeline novo — apenas leitura de parquets/CSVs ja existentes

### Fase 2 — Pipeline CNPJ + GTFS (ciclo dedicado, ~20 dias)
1. Download e parse CNPJ Receita Federal (arquivos de estabelecimentos)
2. Filtrar e geocodificar: academias (9312/9313) + comercio (47xx, 56xx, 96xx)
3. Join ao hexagono → `data/staging/cnpj_por_hex.parquet`
4. Download GTFS das 5 capitais prioritarias; calcular linhas e frequencia por hex
5. Compor `indice_fluxo_proxy` = CNPJ (50%) + GTFS (30%) + OSM POI (20%)
6. Layer no dashboard: mapa de calor de atividade/fluxo

### Fase 3 — PEA completo (ciclo dedicado, ~15 dias)
1. RAIS 2022 por estabelecimento — vinculos formais com CNPJ
2. Join com CNPJ RF para obter CEP do estabelecimento → hexagono
3. INSS municipio → interpolacao 60+ por hex
4. Montar `pea_estimada_hex` como coluna opcional de enriquecimento
5. Layer PEA completo no dashboard; documentar limitacoes de interpolacao

### Fase 4 — Calibradores analiticos (backlog)
1. POF: coeficiente `pof_propensao_academia` por UF/quintil
2. PNAD: taxa de informalidade por UF para componente D do PEA

---

## 7. Guardrails e Riscos

| Risco | Mitigacao |
|---|---|
| PEA componente B (RAIS) sem coordenada intraurbana | Registrar como `nivel_geografico=municipal_interpolado`; documentar metodo |
| Proxy de passantes pode super-estimar centros com pouco GTFS (cidades menores) | Ponderar por cobertura GTFS disponivel; aplicar apenas onde GTFS existe |
| CNPJ 50 GB: volume alto | Processar apenas arquivo de estabelecimentos (~5 GB); filtrar por CNAE antes de persistir |
| POF desatualizada (2017-2018) | Usar como coeficiente estrutural relativo, nao absoluto; documentar defasagem |
| Novas variaveis no score | Guardrail absoluto: nenhuma nova fonte toca `score_priorizacao`, `hex_score_estrutural` ou artefatos M1; novas variaveis entram como colunas complementares |
| Dados de telco/mobile nao publicos | Deixar explicity no codigo e docs que o proxy e aproximacao; se houver interesse futuro em dados privados, tratar como decisao separada de aquisicao |

---

## Conclusao

O mapa de calor de trabalhadores/PEA e tecnicamente viavel em camadas progressivas de precisao. A parte imediata — populacao em idade ativa por setor censitario — ja temos nos dados locais. A parte que resolve o problema real citado (centros comerciais onde os residentes nao refletem o movimento) exige pipeline de CNPJ + RAIS, com o CNPJ sendo o insumo central que conecta tudo: proxy de passantes, localizacao de estabelecimentos empregadores e expansao do mapeamento competitivo.

Para passantes verdadeiros (dado de telco), a ferramenta pode criar o melhor proxy disponivel com dados publicos, sendo transparente sobre a diferenca em relacao ao dado real usado por plataformas pagas.
