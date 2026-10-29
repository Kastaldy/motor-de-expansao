# Dossiê transversal — Motor de Expansão em CO, PY, MX e PE

> **Leia junto com `01-consolidacao-auditoria.md`.** Este dossiê é a versão de campo, de 2026-10-16. A auditoria cruzada corrigiu alguns números e vereditos depois dele, e a versão corrigida vale sobre esta.

- Data: 2026-10-16 | Escopo: fontes multi-país, escala H3, arquitetura/moeda/calibração | Repositório consultado só para leitura (`docs/plano_multipais.md`, `docs/decisions/DEC-047.md`, `data/perfis/AR/perfil.json`, `src/motor_expansao/pipelines/exportar_piloto_ar.py`, `docs/expansao-latam/`).
- Convenção: **medido** = número que eu calculei nesta sessão sobre dado baixado; **verificado** = abri a página/API e confirmei; **não verificado** = vem de busca, notícia ou memória e precisa de checagem antes de virar premissa.
- Amostras baixadas (dados não confiáveis, lidos com Python isolado de diretório): `scratchpad/amostras/transversal/` — Kontur PY/CO/PE/MX/AR (GeoPackage H3 r8), RWI PY (CSV), WorldPop R2025A PY 25-29 anos 2025 (GeoTIFF), Natural Earth admin-0 10m, metadados CKAN do HDX. Scripts em `scratchpad/scripts_transv/`.

---

## 0. Recomendações em uma página

1. **A combinação global homogênea que cobre as 5 camadas nos 4 países é: WorldPop R2025A (população por idade, 100 m, 2015-2030) + GHSL (urbanização/área construída) para a camada 1-população e 4; OSM + Overture Places (+ Foursquare OS Places, que já entra no Overture) para a camada 3 e para a oferta da camada 2; câmbio/PPC/inflação por APIs do Banco Mundial e FMI + banco central de cada país.** Ela **não** cobre renda de forma utilizável comercialmente: o único proxy global fino de riqueza (Relative Wealth Index da Meta) é **CC BY-NC 4.0 — proibido para uso comercial** (verificado no HDX). Luz noturna (VIIRS) é aberta mas é proxy fraco de renda intraurbana. **Renda continua exigindo o pacote nacional (censo + pesquisa domiciliar), como na Argentina.** Para concorrência, o **Overture é a melhor camada global medida** (academias com categoria `gym`: MX 31.044, CO 4.660, PE 3.415, PY 1.219 — 5 a 11× o OSM), mas não substitui a coleta direta (sem porte, preço ou data).
2. **Kontur Population é o atalho mais barato para o esqueleto H3 dos 4 países** (H3 nativo resolução 8, CC BY, um GeoPackage por país de 7 a 35 MB comprimido) — medi que ele **reproduz a ordem de grandeza do universo argentino** e serve para dimensionar e para um "mapa dia zero", mas **não substitui o censo**: no Paraguai ele soma **7,07 M** habitantes contra **6,1 M** do censo 2022 (+16%), porque herda totais da ONU anteriores ao censo.
3. **Universo H3: copiar a Argentina, não o Brasil.** Servir só "habitáveis + anel de 1 vizinho" (o padrão do `exportar_piloto_ar.py`). Estimativa calibrada na AR: **CO ≈ 13 mil, MX ≈ 41 mil, PE ≈ 12 mil, PY ≈ 2,5 mil hexágonos servidos** — contra 1,30 M do Brasil e 15.186 da Argentina. O universo territorial completo (critério de sobreposição do BR) seria CO 215 mil, MX 333 mil, PE 221 mil, PY 86 mil.
4. **Cabe na mesma VPS por RAM e disco com folga; o gargalo é CPU**, como o plano já previu. RSS medido da AR foi 108 MiB; os quatro novos países juntos devem ficar abaixo de ~1,5 GB residentes. O que precisa de regra antes do 3º país é o **teto de PDF por host** (hoje BR 3 + AR 1; com mais quatro instâncias a 1 cada, seriam 8 jobs em 4 vCPU) e as **janelas de coleta semanal** que não podem colidir.
5. **Arquitetura: a DEC-047 (instância por país) é o padrão "silo" da literatura de SaaS e está correta para este caso** — não reabrir. O que o mercado faz de diferente (modelo único "pool") só compensa com comparação entre países, que o dono recusou (decisão 0.1).
6. **Moeda: guardar renda em moeda local nominal num mês-base declarado + USD do banco central no mesmo mês + fator PPC de consumo privado do Banco Mundial como metadado**; nunca converter em tempo de requisição. APIs verificadas hoje: Banrep/TRM (datos.gov.co), BCRP, Banco Mundial, FMI DataMapper; Banxico exige token (verificado); BCP do Paraguai fora do ar no teste (522).
7. **Calibração sem unidade Ultra: validar TRIAGEM, não previsão (DEC-041).** O teste certo é de **falso-veto**: onde a Smart Fit (concorrente low-cost comparável, presente nos 4 países: MX >500, CO 224, PE ~90, PY ≥5 — não verificado em fonte primária) já abriu, o motor não pode marcar o hexágono como frio. Mais análise de sensibilidade de âncoras (a mesma da AR: top-30 estável) e ranking cego com o time local. Nada de R² de faturamento.

---

## 1. Fontes multi-país reaproveitáveis

### 1.1 Tabela de fontes

| Fonte | Cobertura CO / PY / MX / PE | URL | Acesso | Licença | Formato | Granularidade | Ano de referência | Status |
|---|---|---|---|---|---|---|---|---|
| **Kontur Population** | Sim / Sim / Sim / Sim (um arquivo por país) | https://data.humdata.org/dataset/kontur-population-dataset · ex.: https://geodata-eu-central-1-kontur-public.s3.amazonaws.com/kontur_datasets/kontur_population_PY_20231101.gpkg.gz | Download direto, sem login | CC BY 4.0 (campo `license_title` do HDX) | GeoPackage, colunas `h3`, `population`, `geom` | **H3 resolução 8** (~0,74 km²), agrega exato para r7 | Versão 2023-11-01 (fusão GHSL + Meta HRSL + Microsoft Buildings + Copernicus + OSM) | **verificado + medido** (baixados PY, CO, PE, MX, AR) |
| **WorldPop Global2 R2025A — idade e sexo** | Sim / Sim / Sim / Sim | https://hub.worldpop.org/rest/data/age_structures/G2_CN_Age_R25A_100m?iso3=PRY · arquivos em https://data.worldpop.org/GIS/AgeSex_structures/Global_2015_2030/R2025A/ | Download direto | CC BY 4.0 (https://hub.worldpop.org/data/licence.txt) | GeoTIFF por sexo × faixa etária (00, 01, 05…90), `t` = ambos os sexos | 3″ (~100 m), "constrained" (só onde há edificação) | **2015 a 2030, anual** (2025 é projeção) | **verificado + medido** (PY, 25-29 anos, 2025: 597 mil pessoas; ~20 MB por faixa) |
| WorldPop 2020 (série antiga, constrained) | Sim nos 4 | https://hub.worldpop.org/geodata/listing?id=88 | Download direto | CC BY 4.0 | GeoTIFF | 100 m | 2020 | não verificado (substituída pela R2025A) |
| **GHSL GHS-POP R2023A** | Global | https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_POP_GLOBE_R2023A/ | FTP/HTTP aberto, também em AWS `s3://jrc-ghsl` | CC BY 4.0 (copyright.txt da JRC) | GeoTIFF/ZIP por bloco | 100 m (Mollweide) e 3″/30″ (WGS84) | 1975-2030 a cada 5 anos | **verificado** (listagem e licença) |
| **GHSL GHS-SMOD R2023A** (grau de urbanização) | Global | https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_SMOD_GLOBE_R2023A/ | Aberto | CC BY 4.0 | GeoTIFF + GPKG de assentamentos | 1 km | 1975-2030 | **verificado** (diretório) |
| GHSL GHS-BUILT-S/V R2023A | Global | https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/ | Aberto | CC BY 4.0 | GeoTIFF | 10 m (S, 2018) / 100 m | 1975-2030 | **verificado** (diretório) |
| GHSL GHS-AGE R2025A | Global | https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_AGE_GLOBE_R2025A/V1-0/ | Aberto (ZIPs de 580-661 MB a 100 m) | CC BY 4.0 | GeoTIFF | 100 m e 1 km | até 2020 | existência **verificada**; faixas etárias **não verificadas** |
| GHSL WUP R2025A (urbanização mundial) | Global | https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_WUP_POP_GLOBE_R2025A/ | Aberto | CC BY 4.0 | GeoTIFF | 1 km / 30″ | 1975-2030 | existência **verificada** |
| **Meta High Resolution Population Density (HRSL)** | Sim / Sim / Sim / Sim | ex.: https://data.humdata.org/dataset/colombia-high-resolution-population-density-maps-demographic-estimates | Download direto | CC BY 4.0 (HDX) | CSV e GeoTIFF zipados (PY 19-21 MB; MX 70-133 MB) | 30 m (1″) | **CO, PE, PY: 2020; MX: 2018-2019** — congelado desde 2022 | **verificado** (metadados CKAN dos 4) |
| **Relative Wealth Index (Meta)** | Sim / Sim / Sim / Sim | https://data.humdata.org/dataset/relative-wealth-index | Download direto | **CC BY-NC 4.0 — uso comercial proibido** | CSV `latitude, longitude, rwi, error` | Grade de ~2,4 km (tile Bing nível 14) | Publicado 2021, atualizado até 2023 | **verificado + medido** (PY: 10.987 células) |
| VIIRS VNL V2.2 anual (EOG/Colorado School of Mines) | Global | https://eogdata.mines.edu/products/vnl/ | Download (registro não confirmado) | Página diz "muitos produtos sob CC BY 4.0"; Earth Engine diz domínio público — **conflito** | GeoTIFF | 15″ (~500 m) | 2012-2024 | não verificado (licença ambígua) |
| NASA Black Marble VNP46A4 | Global | https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/VNP46A4 | Earthdata Login | Política de dados abertos da NASA | HDF5 (tiles) | 15″ (~500 m) | anual desde 2012 | não verificado (login e última safra) |
| **OpenStreetMap** (extratos Geofabrik + taginfo regional) | Sim / Sim / Sim / Sim | https://download.geofabrik.de/ · https://taginfo.geofabrik.de/south-america:paraguay/ | Aberto | ODbL 1.0 (compartilhamento pela mesma licença se a base derivada for distribuída) | PBF / API | Ponto/polígono | Diário (dados de 2026-10-15) | **verificado + medido** (contagens abaixo) |
| **Overture Maps Places** | Global | https://docs.overturemaps.org/ · `s3://overturemaps-us-west-2/release/2026-09-23.1/theme=places/` | S3 público anônimo (16 Parquets, ~11 GB) | CDLA-Permissive 2.0 (Meta, Microsoft e outros), **Apache 2.0 (Foursquare)**, CC0 (AllThePlaces) | GeoParquet; categorias em `taxonomy.primary` / `basic_category` (schema 2026, não mais `categories`) | Ponto | Mensal (release 2026-09-23.1) | **verificado** (schema e licenças); contagem — ver §1.3 |
| Foursquare OS Places | Global | https://docs.foursquare.com/data-products/docs/access-fsq-os-places | Portal com token / Hugging Face com aprovação | Apache 2.0 | Parquet/Iceberg | Ponto | Mensal | não verificado (acesso mudou em 2025; já entra no Overture) |
| **Google Places API (New)** | Global | https://developers.google.com/maps/billing-and-pricing/pricing · https://developers.google.com/maps/documentation/places/web-service/policies | Chave paga | Termos do Google Maps Platform: **proibido pré-buscar, cachear ou armazenar conteúdo**, exceto `place_id` (indefinido); resultado em mapa tem de ser **mapa Google** | JSON | Ponto | tempo real | **verificado** (preços e política) |
| LandScan Global (população ambiente 24 h) | Global | https://landscan.ornl.gov/ | Download com cadastro | CC BY 4.0 desde 2022 | GeoTIFF | 30″ (~1 km) | anual (2023 confirmado; 2024 incerto) | não verificado |
| Meta Movement / Colocation maps | Restrito | https://dataforgood.facebook.com/ | Só parceiros (acordo) | Termos de parceria | CSV | variado | — | não verificado |
| Google Community Mobility Reports | — | — | Descontinuado | — | — | — | parou em 2022 | não verificado nesta sessão |
| **Banco Mundial — API de indicadores** | Sim nos 4 | https://api.worldbank.org/v2/country/COL;MEX;PER;PRY/indicator/PA.NUS.PRVT.PP?format=json | Aberto, sem chave | CC BY 4.0 | JSON | País-ano | `lastupdated` 2026-10-08; valores 2024-2025 | **verificado** |
| **FMI — WEO DataMapper API** | Sim nos 4 | https://www.imf.org/external/datamapper/api/v1/PCPIPCH | Aberto | Termos do FMI (uso livre com citação) | JSON | País-ano (com projeção) | até 2031 | **verificado** |
| **Banrep — TRM (via datos.gov.co)** | CO | https://www.datos.gov.co/resource/32sa-8pi3.json | Aberto (Socrata) | Dados abertos CO | JSON | Diário | 2026-10-16: 3.170,46 COP/USD | **verificado** |
| **BCRP — API de séries** | PE | https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PD04638PD/json/2026-09-25/2026-10-15 | Aberto | Dados públicos BCRP | JSON | Diário | interbancário venda, out/2026 ~3,43 PEN/USD | **verificado** |
| **Banxico — SIE API** | MX | https://www.banxico.org.mx/SieAPIRest/service/v1/series/SF43718/datos/oportuno | **Token gratuito obrigatório** | Termos Banxico | JSON | Diário (FIX = SF43718) | — | **verificado** (resposta "Token inválido" sem token) |
| BCP — cotização de referência | PY | https://www.bcp.gov.py/webapps/web/cotizacion/monedas | Site; sem API oficial encontrada | Dados públicos | HTML/planilha | Diário | — | **não verificado** (HTTP 522 no teste); alternativa: Banco Mundial `PA.NUS.FCRF` (PY 2025 = 7.545 PYG/USD, verificado) |
| HFA Global Report (penetração fitness) | MX, CO, PE (prováveis); PY incerto | https://www.healthandfitness.org/ | Relatório (parte paga) | Proprietário | PDF | País | 2025 | não verificado |

### 1.2 O que cada fonte entrega, por camada do funil

| Camada | Precisa de | Melhor fonte global homogênea | Perda contra o dado nacional |
|---|---|---|---|
| **1. Potencial socioeconômico — população** | pop por hexágono (idealmente 18-45) | **WorldPop R2025A** (tem faixa etária: soma 20-44 + 2/5 de 15-19, ou 18-45 aproximado por 20-44) ou Kontur (só total, mas H3 nativo) | Pequena no total urbano; grande no rural e em país com censo recente que a ONU errou (PY: +16% no Kontur). Os grids globais são modelagem dasimétrica: **ordem intraurbana boa, contagem absoluta herdada de projeção** |
| **1. Potencial socioeconômico — renda** | renda per capita por hexágono, em moeda | **Não há fonte global aberta e comercial.** RWI é NC; VIIRS é proxy fraco (satura no centro, mede iluminação e não renda) | **Perda total.** Renda tem de vir do pacote nacional (censo com escolaridade/moradia + pesquisa domiciliar: GEIH/CO, ENIGH/MX, ENAHO/PE, EPHC/PY), exatamente como a AR fez com a EPH |
| **2. Demanda não atendida** | TAM (pop × penetração) − oferta (concorrentes × capacidade) | Pop: WorldPop/Kontur; oferta: OSM + Overture | Penetração e capacidade **não existem em fonte global aberta** — são parâmetros de país (a AR mediu 400/1.070 alunos por academia contra 2.500 do BR). Contagem de oferta global é **subcobertura sistemática** (§1.3) |
| **3. Pressão competitiva** | pontos de academia com data | OSM + Overture (com dedup) | Subcobertura de independentes; viés para redes com marca. Nacional (DENUE no MX, RUES/CO, SUNAT/PE) + coleta direta dos sites resolve melhor |
| **4. Momentum** | crescimento populacional | WorldPop R2025A anual 2015-2030 (mesma metodologia ano a ano) ou GHS-POP 2020→2025 | Projeção, não observação. Para MX/CO/PE/PY a série é coerente entre países, o que é a vantagem; é modelada, o que é a fraqueza |
| **5. Fila** | combinação 0,70·socio + 0,30·demanda | Derivada | Herdada das anteriores |

**Conclusão da §1.** A combinação homogênea viável é **WorldPop R2025A (pop e idade) + GHSL (urbanização) + OSM/Overture (oferta) + Banco Mundial/FMI (moeda)**. Ela cobre 4 das 5 camadas de forma comparável entre países; **a camada de renda não tem substituto global comercial** e continua dependendo do pacote nacional. O Kontur entra como **esqueleto H3 e régua de dimensionamento**, não como população oficial.

### 1.3 Cobertura de academias — medido hoje

Contagens do taginfo da Geofabrik (dados de 2026-10-15), Kontur para a população:

| País | `leisure=fitness_centre` | `sport=fitness` | por 100 mil hab. (fitness_centre) | `brand=Smart Fit` no OSM | Smart Fit real (não verificado, notícia) | Cobertura OSM da Smart Fit |
|---|---|---|---|---|---|---|
| Colômbia | 742 | 467 | 1,4 | 65 | 224 (fim de 2025, Forbes CO) | ~29% |
| México | 2.734 | 984 | 2,1 | 80 | >500 (1º sem. 2026, Emprendedor) | ~16% |
| Peru | 346 | 128 | 1,0 | 16 | ~90 (abr. 2025, Gestión) | ~18% |
| Paraguai | 241 | 67 | 3,4 | 0 | ≥5 em Assunção (2022, La Nación) | 0% |
| Argentina (referência) | 1.766 | 1.889 | 3,9 | 0 | — | — |
| Brasil (referência) | 5.867 | 5.423 | ~2,8 | 273 | ~1.000+ | — |

`amenity=gym` retornou 0 nos seis (tag em desuso). **Régua de calibração da AR:** o perfil argentino estima um parque de **8.662** academias; o OSM tem **1.766** `fitness_centre` → **~20% de cobertura**. Aplicar a mesma razão é a estimativa mais honesta que existe para a ordem de grandeza do parque real, e mostra que **OSM sozinho não serve para a camada 3** — ele serve como uma das duas camadas do D4 do contrato (OSM + coleta direta), que é o desenho que a AR já usa.

**Overture Places (release 2026-09-23.1) — medido hoje**, lendo só os *row groups* cujo `bbox` cruza cada país e filtrando pelo país do 1º endereço, `operating_status` aberto:

| País | Places com endereço no país | `taxonomy.primary = gym` | + `fitness_trainer`, `boxing_class`, `pilates_studio`, `yoga_studio` | `gym` por 100 mil hab. | Razão `gym` Overture / `fitness_centre` OSM |
|---|---|---|---|---|---|
| México | 3.060.620 | **31.044** | 6.942 | 24,1 | 11,4× |
| Colômbia | 642.719 | **4.660** | 736 | 8,9 | 6,3× |
| Peru | 436.892 | **3.415** | 457 | 10,3 | 9,9× |
| Paraguai | 112.455 | **1.219** | 186 | 17,2 | 5,1× |

Leituras: (i) o Overture traz **5 a 11 vezes** mais academias que o OSM e é a melhor camada global para a concorrência — na mesma ordem de grandeza do parque argentino estimado (18,9 por 100 mil); (ii) **CO, PE e PY são piso**: o filtro por país do endereço descarta lugar sem endereço, e a razão places/habitante do México (2,4 por 100 hab.) é 2 a 2,5 vezes a dos outros três, o que indica preenchimento de endereço desigual — na versão de produção o recorte tem de ser **geométrico** (ponto no polígono do país), não pelo campo de endereço; (iii) a categoria guarda-chuva `sport_or_fitness_facility` (MX 5.920, CO 1.729, PE 1.375, PY 511) mistura quadras e clubes e **não** deve entrar na contagem; (iv) o Overture **não traz porte, preço nem data de abertura** — serve para a camada 3 e para a oferta da camada 2 como contagem, não para capacidade.

---

## 2. H3 em larga escala

### 2.1 Método

- Área: Natural Earth admin-0 1:10m, projetada em Mollweide (ESRI:54009).
- Contagem territorial: `h3.h3shape_to_cells` resolução 7 (centro dentro) e `h3shape_to_cells_experimental(..., contain='overlap')` (qualquer sobreposição, que é o critério de candidatos do Brasil na DEC-003). **Controle:** o Brasil por sobreposição deu **1.542.346** contra **1.542.531** do repositório (−0,01%) — o método reproduz o número oficial.
- Universo povoado: Kontur r8 agregado a r7 (`cell_to_parent`). O limiar de "habitável" foi **calibrado na Argentina** para reproduzir os **6.956** habitáveis medidos no exportador (`exportar_piloto_ar.py:1026`): sai `pop_r7 ≥ 740`, que dá 6.959 na AR. Mesmo limiar + anel de 1 aplicado aos demais.
- Fator de correção Kontur→pacote nacional, medido na AR: habitáveis+anel **20.981 (Kontur) → 15.186 (pacote)** = ×0,724; corte ≥ 3 hab/km² **81.910 (Kontur ≥ 16 hab/hex) → 42.388 (pacote)** = ×0,517. A diferença vem de o pacote do Juan alocar radio censal por área (o Kontur espalha população rural fina por mais células).
- **Observação:** área / 5,161 km² **não** é uma boa estimativa — a área da célula H3 varia com a latitude (perto do equador as células são maiores; CO e PE dão menos células que a divisão simples, AR e PY dão mais).

### 2.2 Tabela de estimativa H3 (resolução 7)

| País | Área (km²) | Células — centro | Células — sobreposição (critério BR) | Kontur r7 com pop > 0 | Kontur ≥ 16 hab (~3 hab/km²) | **Universo ≥ 3 hab/km² estimado** (×0,517) | Habitáveis (≥ 740 hab) | Habitáveis + anel (Kontur) | **Servidos estimados** (×0,724) | Hexes com pop ≥ 5.000 |
|---|---|---|---|---|---|---|---|---|---|---|
| **Brasil** (ref.) | 8.523.997 | 1.534.656 | **1.542.346** (repo: 1.542.531) | — | — | — | — | — | **1.303.414** servidos (medido no repo) | — |
| **Argentina** (ref.) | 2.789.349 | 660.076 | 664.228 | 177.957 | 81.910 | **42.388** (medido no pacote) | 6.959 (pacote: 6.956) | 20.981 | **15.186** (medido) | 1.997 |
| **Colômbia** | 1.142.648 | 212.995 | 215.258 | 84.266 | 55.694 | ~28.800 | 4.941 (88% da pop.) | 18.330 | **~13.300** | 1.367 |
| **México** | 1.966.640 | 328.279 | 332.845 | 147.447 | 97.604 | ~50.500 | 18.777 (89%) | 57.223 | **~41.400** | 4.355 |
| **Peru** | 1.298.027 | 219.233 | 221.264 | 72.185 | 47.908 | ~24.800 | 4.874 (79%) | 16.291 | **~11.800** | 810 |
| **Paraguai** | 401.756 | 85.444 | 86.384 | 31.134 | 17.880 | ~9.300 | 1.073 (70%) | 3.399 | **~2.500** | 253 |

População Kontur (r8 somado): AR 45,8 M · CO 52,2 M · MX 128,6 M · PE 33,1 M · PY 7,07 M.

Leitura: **o México é o único país novo maior que a Argentina** (≈2,7× os servidos argentinos). CO e PE ficam no tamanho da AR; PY é um sexto dela. **Nenhum dos quatro chega perto do Brasil** — o maior (MX servido) é 3% do Brasil servido.

### 2.3 Armazenamento

Proporções medidas no repositório (`docs/plano_multipais.md` §4 e `exportar_piloto_ar.py`): enriquecido BR **265 MB / 1.303.414 hex ≈ 0,2 KB/hex** (sem geometria); pacote AR `hexagonos_h3` **42 MB / 42.388 hex ≈ 1,0 KB/hex** (86 colunas, com `geometry_wkb`); `censo_radios` AR **93 MB / 66.502 radios ≈ 1,4 KB/unidade**; geo setorial BR **1,2 GB / 468.099 setores ≈ 2,6 KB/unidade**.

| País | Pacote hexagonal (universo ≥ 3 hab/km², ~1 KB/hex) | Se fosse universo territorial completo | Malha fina para a superfície `ponto` (1,4-2,6 KB × nº de unidades) | Tiles `.mbtiles` (decisão 0.9 do plano) |
|---|---|---|---|---|
| CO | ~30 MB | ~215 MB | depende de manzana × sección — **nº de unidades não verificado aqui** | 3-6 GB |
| MX | ~50 MB | ~330 MB | se AGEB: ordem de 100-200 MB; **se manzana (milhões de unidades), ordem de GB** | 3-6 GB |
| PE | ~25 MB | ~220 MB | não verificado (cartografia de manzana do INEI sai por solicitação — §6.5 do plano) | 3-6 GB |
| PY | ~9 MB | ~85 MB | não verificado | 3-6 GB |

Total dos quatro, pior caso razoável (pacote + malha fina de AGEB/sección + tiles): **< 40 GB** nos 200 GB do SSD. **Disco não é restrição.** O único item que pode mudar de ordem de grandeza é a malha fina do México em nível de manzana — e ela só é necessária se a superfície `ponto` for ligada lá.

### 2.4 RAM e CPU

- Medido no repositório: **RSS da instância AR = 82 → 108 MiB** com 15.186 hexágonos (`docs/expansao-latam/anexos/fase0-b-receita-argentina.md:82`). Picos de carga a frio por partição no BR: SC 20.373 hex → 342 MB; RO 46.455 → 330 MB; AM 293.991 → 826 MB.
- Estimativa, não medido: CO, PE e PY ficam no patamar da AR (100-200 MiB residentes); MX servido (~41 mil hex em 32 entidades, a maior partição com poucos milhares de hex) deve ficar em 150-300 MiB. **Mesmo com universo territorial completo**, a maior entidade mexicana (Chihuahua, ~247 mil km² → ~48 mil hex) é do tamanho de RO (330 MB de pico). **RAM não é o limite em nenhum cenário.**
- Tetos declarados (`mem_limit`) já somam mais que 16 GB (BR 8 + API 6 + AR 2 + tiles 1,5); somar 4 × 1-2 GB piora a soma de tetos, mas **teto não é consumo** (o plano retirou essa conta, §4). Recomendo `mem_limit` provisório de **1 GB para PY, 1,5 GB para CO/PE e 2 GB para MX**, revistos depois da medição de RSS em regime.
- **CPU é o gate.** `_PDF_CONCORRENCIA_MAX` é por processo; com BR 3 + AR 1 + quatro países a 1, o host admite **8 jobs de PDF simultâneos em 4 vCPU**. A coleta semanal de concorrentes de cada país (~20 min com 4 workers, padrão AR) também disputa CPU. Recomendação compatível com a DEC-047 (que proíbe multiplexar país **dentro** do processo, não limitar recurso **no host**): (i) `cpus:` por container no compose para as instâncias novas (ex.: 1,0 cada), protegendo o BR; (ii) `pdf_concorrencia_max = 1` no perfil de cada país novo; (iii) calendário de coleta escalonado e declarado, com a data da última coleta no `/api/health` (já é regra do plano).
- **API GeoEspacial:** hoje é só BR (6 GB de teto). Os países novos sobem **sem API e sem bot**, como a AR. Se um país pedir a API, ela é o item caro (o `_carregar_mercado_full` tem "~1,9 GB" de docstring nunca medido — risco R11 do plano).

### 2.5 Recomendação de universo e particionamento

1. **Pipeline do país:** calcular sobre o universo **≥ 3 hab/km²** (método AR, cobre ~98% da população); **servir** "habitáveis + anel de 1" (padrão `exportar_piloto_ar.py`). Não replicar o universo territorial do Brasil (1,54 M existe porque o M1 brasileiro ranqueia o território inteiro; nenhum país novo tem M1).
2. **Partição por nível 1:** CO 32 departamentos + Bogotá D.C.; MX 32 entidades; PE 24 departamentos + Callao (+ Lima Metropolitana, se tratada à parte); PY 17 departamentos + Assunção. Atenção ao achado **Q3** do baseline AR: `_UF_RE = ^[A-Za-z]{2}$` recusa códigos numéricos (DANE `11`, INEGI `09`, UBIGEO `15`), e é sink anti-path-traversal — a decisão é fabricar sigla alfabética no exportador (como a AR) ou relaxar o regex com teste de segurança, **antes** do primeiro país novo.
3. **Mesma VPS:** sim, para os quatro, com as três salvaguardas de CPU acima. Gatilho de reabertura (já no plano): p95 do BR degradando com as instâncias novas no ar.

---

## 3. Arquitetura multi-país, moeda e calibração

### 3.1 Núcleo comum por país (silo) × modelo único parametrizado (pool)

- A literatura de SaaS (AWS Well-Architected SaaS Lens, "Silo, Pool, and Bridge Models" — https://docs.aws.amazon.com/wellarchitected/latest/saas-lens/silo-pool-and-bridge-models.html, verificado) chama de **silo** o que a DEC-047 escolheu: recurso dedicado por inquilino com identidade, onboarding e operação compartilhados. O **pool** troca isolamento por economia de escala; o **bridge** mistura.
- Por que o silo é o certo aqui, e não preferência: (a) o *noisy neighbor* que a AWS usa como argumento para silo é exatamente o risco medido no repo (CPU do PDF); (b) os 40 `lru_cache` e os 6 caches de renda sem `cache_clear` tornam o pool um **defeito de correção** (DEC-047); (c) o pool só se paga com **comparação entre países**, recusada pela decisão 0.1.
- O que a prática de mercado ensina e **ainda falta** no silo da DEC-047: a parte "compartilhada" do silo — onboarding, identidade e operação únicos. No repo isso corresponde a: validador de contrato rodado pelo produtor (BLK-INTL-07, ainda não existe — Q1 do baseline), infra gerada em vez de copiada à mão (Q4) e um painel de saúde por país (data da coleta, RSS, versão do perfil). **É aí que o 3º-6º país custa caro**, não no código do app.
- **Não propor:** instância única multi-país, export LATAM, i18n (D4 fechada em português), modelo bimonetário (D5 fora desta rodada).

### 3.2 Moeda, câmbio e inflação

Regra recomendada (consistente com o `perfil.json` da AR, que já separa `codigo`, `indicadores_renda` e `comparacao`):

1. **Armazenar a renda na moeda em que ela foi construída, num mês-base único e declarado** (a AR usa mai/2026). As âncoras do perfil ficam nessa mesma moeda e mês — **a âncora é recalibrada pela distribuição do país (receita p05/p99), não convertida** (nota `_nota_renda` do perfil AR).
2. **Guardar junto, como metadado do pacote:** câmbio USD do banco central **no mesmo mês-base** (Banrep TRM, Banxico FIX SF43718, BCRP PD04638PD, BCP referência) e o **fator PPC de consumo privado** do Banco Mundial (`PA.NUS.PRVT.PP`, melhor que o de PIB para poder de compra de serviço ao consumidor). Valores verificados hoje (LCU por dólar internacional, 2025): CO 1.665,6 · MX 11,31 · PE 1,93 · PY 2.874,6 · BR 2,58.
3. **Nunca converter em tempo de requisição.** Converter é decisão de pacote, com data; a tela mostra a data do câmbio.
4. **Inflação:** IPC nacional (DANE, INEGI, INEI, BCP) para atualizar o mês-base; FMI WEO `PCPIPCH` para projeção do DRE (verificado: 2026 — CO 6,0% · MX 3,8% · PE 3,8% · PY 3,1%). Todos os quatro são de inflação baixa/moderada — o problema argentino (32,5% em 2026 no WEO) **não se repete**, e o fator temporal de renda pode ser anual.
5. **Gramática numérica:** MX e PE usam `1,500.00`; `mascara.ts` assume pt-BR e transforma "35,000" em 35 sem erro (R10 do plano / S5 do baseline). Tem de ser corrigido **antes** do primeiro operador desses dois países.

### 3.3 Calibração sem unidades Ultra no país — respeitando a DEC-041 (a DEC-043 foi revogada pela DEC-078)

No BR, a Viabilidade sugere o faturamento de um imóvel com um modelo calibrado em unidades Ultra (DEC-078). **O funil segue triagem** (política declarada, DEC-041). Logo, nenhum país novo deve ser "validado" por acerto de faturamento, e a validação proposta mede só o que a triagem promete: **não descartar praça boa e ordenar de forma estável.**

1. **Transferência de parâmetros, sem conversão:** âncoras de renda pela mesma receita (p05 arredondado / acima do p99, saturação < 0,4%); âncoras de população **idênticas ao BR** (1.000 / 100.000 — casamento de unidade, já demonstrado na AR); `pop_min_acionavel = 5.000` (decisão 0.18); corte quente 30 (verificar a fração de quentes: BR 2,2%, AR 5,5%).
2. **Teste de falso-veto com a Smart Fit** (concorrente low-cost e comparável, presente nos 4 países): localizar as unidades (OSM `brand=Smart Fit` cobre só 16-29%; completar pelo localizador do site — o endpoint `api/locations` do MX respondeu **401**, então a coleta é por página — ou pelo Overture `brand`), e medir **que fração delas cai em hexágono "frio"** (score < 30 ou pop < 5.000). Critério pré-registrado, no molde do E6/E7: falso-veto alto reprova as âncoras. **Ressalva escrita junto (DEC-042):** a amostra é condicionada no desfecho — prova falso-veto, **não** prova acerto ao rejeitar.
3. **Backtest temporal de presença:** com o dado de população de um ano-base (WorldPop 2020) e a lista de aberturas da Smart Fit 2021-2025 (imprensa, histórico do OSM, Wayback), verificar se os hexágonos onde ela abriu depois estavam no topo da fila. É teste de **ordenação**, não de desempenho.
4. **Sensibilidade das âncoras como gate de entrada** (replicar o que a AR mediu na decisão 0.19): top-30 compartilhado entre âncoras candidatas (AR: 27-29 de 30) e Spearman (AR: 0,96-0,998). Se o top mudar muito com a âncora, a âncora vira decisão do dono, não default.
5. **Ranking cego com o time local:** 20-30 bairros/hexágonos em 2 cidades por país, ranqueados por quem conhece a praça antes de ver o mapa; Spearman contra o motor; divergência abre revisão caso a caso. Serve para achar defeito de dado (o tipo "Bariloche com renda alta e ninguém morando"), não para dar nota ao modelo.
6. **Priors só para a camada financeira:** ticket, churn, rampa e aluguel-teto com distribuição a priori derivada da rede BR (e de preços públicos da Smart Fit local), atualizada quando houver dado local; saída como faixa (P10-P90) e tornado de sensibilidade, nunca ponto. O carimbo "não calibrado" viaja no PDF/XLSX (decisão 0.7).

---

## 4. Premissas frágeis e riscos

| # | Premissa / risco | Por que é frágil | Mitigação |
|---|---|---|---|
| F1 | "Fontes globais substituem o censo" | Medido: Kontur PY = 7,07 M contra 6,1 M do censo 2022 (+16%). Grids globais herdam totais da ONU; países com censo recente que revisou para baixo (PY 2022) ficam inflados | Usar grid global só como **distribuição** (dasimetria) e reescalar ao total do censo/projeção oficial por departamento |
| F2 | "RWI resolve a renda" | **CC BY-NC 4.0** — uso comercial proibido (verificado). Grade de 2,4 km também é grossa para intraurbano | Não usar no produto. Se for usado em pesquisa interna, consultar o jurídico antes |
| F3 | "Kontur é CC BY, então está livre" | Ele funde Microsoft Buildings e OSM (ODbL, *share-alike*); a declaração CC BY do produtor não foi auditada | Usar Kontur para dimensionamento e mapa interno; para artefato distribuído, preferir WorldPop/GHSL (CC BY limpos) |
| F4 | "OSM/Overture dão a concorrência" | OSM cobre ~20% do parque (régua AR) e 16-29% da Smart Fit; o Overture traz 5-11× mais (MX 31 mil `gym`), mas sem porte/preço/data, com duplicatas prováveis e preenchimento de endereço desigual entre países | D4 do contrato (OSM + coleta direta + dedup). Declarar o fator de cobertura por país (a AR usa 2,675) e **não** aplicá-lo hexágono a hexágono |
| F5 | "Google Places completa a lista" | Termos proíbem armazenar/cachear (só `place_id`) e exigem mapa Google; US$ 32 por mil buscas Text Search Pro | Não usar como base persistida. No máximo verificação pontual manual |
| F6 | "Penetração e capacidade transferem do BR" | A AR mediu 400/1.070 alunos por academia contra 2.500 do BR e taxa fitness 4,5× do benchmark; HFA por país não verificado | Parâmetro de **perfil por país**, com fonte e dono; residual entre países é incomparável até isso estar declarado |
| F7 | "Universo servido pequeno = RAM pequena" | Verdadeiro para dado; **falso para CPU**: 8 jobs de PDF em 4 vCPU com seis instâncias | `cpus:` por container, PDF = 1 nos novos, coletas escalonadas, medir p95 do BR a cada país que entra |
| F8 | Códigos de subdivisão numéricos | `_UF_RE` só aceita duas letras (Q3); é guarda anti-traversal | Decidir sigla fabricada × regex relaxado com teste de segurança antes do 1º país |
| F9 | Smart Fit como "verdade" de praça boa | Ela escolhe ponto com lógica parecida (circularidade); amostra condicionada no desfecho | Usar só como teste de falso-veto e de ordenação, com a ressalva escrita (DEC-042) |
| F10 | WorldPop 2025 é "dado de 2025" | É projeção (série 2015-2030) ancorada em censos antigos (CO 2018, PE 2017) | Rotular o ano como projeção no perfil (`fontes.safra`) e preferir o censo quando houver |
| F11 | VIIRS como proxy de renda | Mede luz, satura em centros densos, confunde indústria/iluminação pública com renda | No máximo variável auxiliar no modelo de renda do pacote nacional, validada contra a pesquisa domiciliar |
| F12 | Banco central do Paraguai | Site respondeu 522 no teste; sem API oficial encontrada | Fallback declarado: Banco Mundial `PA.NUS.FCRF` (anual) ou planilha anual do BCP |
| F13 | Contagens de Smart Fit por país | Vêm de notícia (Forbes CO, Gestión, Emprendedor), não do release da companhia | Conferir no release de RI (anexo por país) antes de usar como denominador |
| F14 | Kontur→pacote (×0,517 e ×0,724) | Fatores medidos **só na AR**; a forma da ocupação (cordilheira no PE, selva na CO) pode mudar a razão | Tratar a tabela §2.2 como ordem de grandeza (±30%); o número real sai do pacote de cada país |

---

## 5. Rastros

- Contagem H3: `scratchpad/scripts_transv/h3_count.py` (Natural Earth 10m; BR por sobreposição = 1.542.346 contra 1.542.531 do repo).
- Universo povoado: `scratchpad/scripts_transv/kontur_res7.py` e `kontur_universo.py` (Kontur 2023-11-01, r8→r7, limiar 740 calibrado nos 6.956 habitáveis da AR).
- WorldPop: `scratchpad/scripts_transv/read_tif.py` sobre `pry_t_25_2025_CN_100m_R2025A_v1.tif` (10057×9984, nodata −99999, soma 597.003).
- OSM: API do taginfo regional da Geofabrik (`/api/4/tag/stats`), dados de 2026-10-15. O Overpass público (overpass-api.de) não respondeu deste ambiente; os espelhos kumi/private.coffee deram HTTP 500.
- Overture: `scratchpad/scripts_transv/overture_gyms.py` (leitura por *row group* filtrada pelas estatísticas de `bbox`, sem baixar os arquivos).
- Câmbio/inflação/PPC: chamadas às APIs listadas na §1.1 em 2026-10-16.
