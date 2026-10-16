# Dossiê de dados — MÉXICO (MX) para o Motor de Expansão

> **Leia junto com `01-consolidacao-auditoria.md`.** Este dossiê é a versão de campo, de 2026-10-16. A auditoria cruzada corrigiu alguns números e vereditos depois dele, e a versão corrigida vale sobre esta.

- Data da pesquisa e de todos os acessos: **2026-10-16**. Somente leitura sobre o repositório; nada foi alterado nele.
- Insumos lidos antes de pesquisar: `fase0_acoplamento_contrato.md` §2.0-2.8 e `fase0_receita_argentina.md` §1 e §6.
- Amostras baixadas (dado não confiável, lido com `python -I`; nada baixado foi executado), em `C:\Users\Pichau\AppData\Local\Temp\claude\C--Users-Pichau-Documents-motor-de-expansao\d45e86bf-d899-46b1-bd74-dd25828a14cf\scratchpad\amostras\MX\`:
  - `ageb01.zip`: CPV 2020 por AGEB e manzana, Aguascalientes, 2,6 MB.
  - `denue_00_71_csv.zip`: DENUE 05/2026, setor 71 nacional, 6,7 MB.
  - `imu_2020.csv`: Índice de Marginación Urbana CONAPO por AGEB, 15,6 MB.
  - `mg2023\*.dbf/.prj/.txt`: tabelas do Marco Geoestadístico dez/2023, extraídas por *range request* sem baixar o shape.
  - `wellhub_*.xml`: sitemaps de parceiros do WellHub.
  - `imss_asg_2026-09-30_head.csv`: só o cabeçalho, 3 KB.
  - `fx_usd_mxn_brl.json`: câmbio.
  - `smartfit_doc1.txt`: texto do release 2T26 da Smart Fit.
  - `gsw_2T26.txt`: texto do relatório 2T26 do Grupo Sports World.
  - O ITER 2020 nacional (36,6 MB) foi baixado só para contar hexágonos e **apagado em seguida**.
- Scripts em `...\scratchpad\scripts_mx\` (fora da pasta de dados).
- Convenção:
  - **[medido]**: conferido nesta sessão em arquivo ou página.
  - **[declarado]**: afirmado por terceiro, não reconferido.
  - **[estimativa]**: inferência minha, com a conta explícita.

---

## Resumo executivo (5 linhas)

1. O México é, dos quatro países, o que tem a **melhor base pública para o motor**:
   - censo 2020 por **AGEB urbana (64 mil) e manzana (>1 milhão)**, com geometria oficial (Marco Geoestadístico) e licença de uso comercial com atribuição;
   - **Encuesta Intercensal 2025**, já publicada (22/09/2026);
   - um **diretório oficial georreferenciado de academias**: DENUE, com **30.242 "centros de acondicionamiento físico del sector privado"** com lat/lng, AGEB e manzana [medido].
2. **Renda continua MODELADA**, como na AR, mas com insumo melhor:
   - o **cuestionario ampliado do CPV 2020** traz **renda do trabalho individual medida** (`INGTRMEN`), representativa por **município** (2.469 domínios) [medido];
   - a ENIGH 2024 traz `ing_cor` com **código de município** (`ubica_geo`) [medido];
   - a distribuição intra-municipal sai de modelo sobre covariáveis da AGEB (escolaridade, bens, internet), com o NSE AMAI por AGEB (grátis) e o IMU CONAPO (CC-BY) como validação.
3. **Concorrência:** é a camada mais forte de todos os países, mas exige **calibração própria de capacidade**:
   - 86,7 % dos 30.242 estabelecimentos do DENUE têm 0-5 empregados;
   - a Smart Fit tem ~2.570 clientes por unidade no MX.
   - O estrato de pessoal ocupado do DENUE permite capacidade **por estrato**, em vez de uma constante.
4. **Pontos de quebra com o contrato:**
   - `cod_municipio` tem 5 dígitos (`CVEGEO` = 2 de entidade + 3 de município), não casa com o join de crescimento por `cod6`;
   - as 32 entidades não têm sigla oficial de 2 letras (a ISO 3166-2:MX é de 3), o que bate no `_UF_RE`;
   - o IMSS usa código de município **próprio** (`A01`…), não o INEGI;
   - o IVA de 16 % está embutido no preço ao consumidor;
   - há PTU de 10 % do lucro para os empregados.
5. **Gargalos reais:**
   - **imobiliário**: todos os portais testados (Inmuebles24, Vivanuncios, Lamudi, Propiedades.com) respondem 403/401 a HTTP simples, então é preciso anti-bot pago ou parceria;
   - **penetração fitness**: não há número primário confiável; o publicado varia de 3 % a 6 %, sem metodologia.

---

## A. Dados por camada do funil

### A.0 Identidade, divisão administrativa e malha

**Hierarquia:** entidade federativa (32) → município / *demarcación territorial* (2.475 no MG dez/2023 [medido]; 2.478 segundo a EIC 2025 [medido]; 2.469 domínios no CPV 2020 [declarado pelo INEGI]) → localidade → AGEB (urbana/rural) → manzana.

**Chave geográfica `CVEGEO` [medido nos DBF do MG 2023]:**

| Nível | Formato | Exemplo |
|---|---|---|
| Entidade | 2 dígitos | `01` |
| Município | **5 dígitos** = `CVE_ENT` + `CVE_MUN` | `01001` |
| AGEB | 13 caracteres = ent(2) + mun(3) + loc(4) + ageb(4, **alfanumérico**) | `010020011025A` |
| Manzana | 16 caracteres = AGEB + mza(3) | `0100200010122002` |

**Mudanças na malha:**
- O MG muda entre versões: 2020 (base do CPV) → dez/2023 (2.475 municípios) → EIC 2025 (2.478).
- O join do dado do CPV 2020 tem de usar o **MG 2020** (`889463807469`), não o 2023.

**Projeção** do MG [medido no `.prj`]: `MEXICO_ITRF_2008_LCC` (cônica conforme de Lambert, ITRF2008/GRS80). Precisa de reprojeção para EPSG:4326/4674-equivalente antes do H3.

**Escala (H3 res 7):**

| Medida | Valor | Origem |
|---|---|---|
| Hexágonos no território total (1.964.375 km² ÷ 5,1613 km²) | ≈ 380.600 | [estimativa] |
| Hexágonos com ≥ 1 localidade povoada (pontos do ITER 2020) | **93.214** | [medido] |
| Hexágonos povoados, somando o transbordo das áreas urbanas grandes | ~95-100 mil | [estimativa] |
| Hexágonos com ≥ 5.000 hab. (o gate) | **~4-7 mil** | [estimativa] |

Notas da escala:
- **Base de medição dos 93.214:** 189.432 localidades com coordenada e 126,0 M hab.
- **Limite inferior do gate:** pelo ponto da localidade são 2.346 hexes ≥ 5.000.
- **Teto do gate:** as 741 localidades ≥ 15 mil hab. somam 80,3 M hab. e cobririam ~2.600 hexes a 6.000 hab./km².
- **Comparação com a AR:** 42.388 hexes povoados, ou seja, **~2,3× a AR** em hexes povoados.

**Volume de arquivos:**

| Arquivo | Tamanho | Origem |
|---|---|---|
| CPV 2020 AGEB/manzana, soma dos 32 zips | **247 MB** compactado (~2,4 GB de CSV, 10× no AGS) | [medido] |
| MG 2023 "integrado", sem manzanas | **277 MB** | [medido] |
| MG por entidade, com manzanas (AGS) | 41,7 MB → nacional na ordem de **1-2 GB** compactado | [medido] / [estimativa] |
| Manzanas no MG 2023 | 23.780 no AGS → **~2,1 milhões** no país (proporção de população) | [medido] / [estimativa] |

### A.1 Tabela de fontes (regra de evidência)

**Leitura das colunas (valem para todas as tabelas de fontes):**
- **Acesso:** 2026-10-16 em todas.
- **Licença INEGI:** "Términos de Libre Uso de la Información del INEGI". Permite **uso comercial**, adaptar e redistribuir, com **atribuição** ("Fuente: INEGI, <produto>"), informando as transformações e sem sugerir endosso [medido em https://www.inegi.org.mx/inegi/terminos.html].

#### Identidade e malha

| Fonte | URL | Licença | Formato | Granularidade | Ano ref. | Status |
|---|---|---|---|---|---|---|
| Marco Geoestadístico dez/2023 Integrado | https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos/geografia/marcogeo/794551067314/mg_2023_integrado.zip (277 MB) | INEGI livre | Shapefile (LCC ITRF2008) | entidade, município (2.475), AGEB (82.030: 64.557 urb. + 17.473 rur.), localidades (4.905 urb. + 45.858 rur. polígonos; 294.163 pontos) | jul/2023 | **verificado** (diretório central lido; `00a.dbf`, `00mun.dbf`, `.prj`, metadado e `contenido.txt` extraídos) |
| MG por entidade, com manzanas (ex.: AGS) | `.../marcogeo/794551067314/01_aguascalientes.zip` (41,7 MB) | INEGI livre | Shapefile | manzana (`01m`: 23.780 no AGS, `CVEGEO` 16), AGEB, localidade, frentes de manzana | jul/2023 | **verificado** (`01m.dbf` lido) |
| MG 2020 (versão do CPV 2020) | `.../marcogeo/889463807469/mg_2020_integrado.zip` (257,5 MB) e `.../889463807469/01_aguascalientes.zip` (36,8 MB) | INEGI livre | Shapefile | igual | 2020 | **verificado** (existência e tamanho por *range request*); conteúdo não aberto |
| MG mais recente que dez/2023 (2024/2025) | https://www.inegi.org.mx/temas/mg/ | — | — | — | — | **não verificado** (página em JS; nenhuma versão 2024/2025 encontrada) |

#### Base censitária e unidade mínima

| Fonte | URL | Licença | Formato | Granularidade | Ano ref. | Status |
|---|---|---|---|---|---|---|
| **CPV 2020 — Principales resultados por AGEB y manzana urbana** | https://www.inegi.org.mx/contenidos/programas/ccpv/2020/datosabiertos/ageb_manzana/ageb_mza_urbana_01_cpv2020_csv.zip (1 zip por entidade, 32 = 247 MB) | INEGI livre | CSV UTF-8 com BOM, 230 colunas | **AGEB urbana e manzana** (só localidades urbanas) | 2020 | **verificado**: 16.376 linhas no AGS (480 AGEB, 15.843 manzanas). Colunas `POBTOT`, `VIVTOT`, `TOTHOG`, `VIVPAR_HAB`, `PROM_OCUP`, `GRAPROES`, `P_18A24`, `POB15_64`, `PEA`, `PDER_SS`, `VPH_AUTOM`, `VPH_PC`, `VPH_INTER`. Supressão `*` na manzana: `TOTHOG` 4,8 %, `VPH_INTER` 10,5 %, `P_18A24` 14,3 %, `POBTOT` 0 %; na AGEB, ≤ 1,2 %. Cobre 84 % da pop. do AGS (1.198.711 de 1.425.607): o resto é rural |
| CPV 2020 — ITER (Principales resultados por localidad) | https://www.inegi.org.mx/contenidos/programas/ccpv/2020/datosabiertos/iter/iter_00_cpv2020_csv.zip (36,6 MB; CSV de 150 MB) | INEGI livre | CSV, `LATITUD`/`LONGITUD` em graus-min-seg | localidade (pontos), incl. **rurais** | 2020 | **verificado**: 189.432 localidades com coordenada, 126.014.024 hab. |
| **Encuesta Intercensal 2025** | https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/ei/EIC2025-def_CP.pdf | INEGI livre | PDF (boletim); tabulados e microdados anunciados no portal | nacional, 32 entidades, **2.478 municípios** e localidades ≥ 50 mil | 2025 (campo 06/10-14/11/2025; publicado 22/09/2026) | **verificado** (boletim lido): 130,9 M hab.; 39,7 M viviendas particulares habitadas; 3,3 hab./vivenda; amostra de 7,3 M viviendas; crescimento de 0,7 % a.a. em 2020-2025. **Não há AGEB nem manzana.** Tabulados municipais e pergunta de renda do trabalho: **não verificados** |
| CPV 2020 — cuestionario ampliado (microdados) | https://www.inegi.org.mx/contenidos/programas/ccpv/2020/microdatos/Censo2020_CA_ags_csv.zip | INEGI livre | CSV | pessoa/vivenda; geografia `ENT`, `MUN`, `LOC50K`, `ESTRATO`, `UPM`, `FACTOR` (sem AGEB) | 2020 | **verificado** (cabeçalho de `Personas01.CSV` lido por *range*): contém **`INGTRMEN`** (renda mensal do trabalho), `MUN_TRAB`, `HORTRA`. Amostra de ~4 M viviendas, estimativas para 2.469 municípios [declarado INEGI/CEPAL] |

#### Renda, consumo e proxies

| Fonte | URL | Licença | Formato | Granularidade | Ano ref. | Status |
|---|---|---|---|---|---|---|
| **ENIGH 2024 (nueva serie)** | https://www.inegi.org.mx/contenidos/programas/enigh/nc/2024/microdatos/enigh2024_ns_concentradohogar_csv.zip (13,2 MB); base completa `.../datosabiertos/conjunto_de_datos_enigh2024_ns_csv.zip` (103 MB) | INEGI livre | CSV | domicílio, com `ubica_geo` = **município de 5 dígitos**, `est_dis`, `upm`, `factor`; representativa nacional/entidade/urbano-rural [declarado] | 2024 (campo ago-nov/2024; publicado jul/2025) | **verificado** (cabeçalho e 2 linhas lidos): `ing_cor`, `ingtrab`, `tot_integ`, `educa_jefe`, `gasto_mon`, `esparci`. Ingresso corrente médio de 77.864 MXN/trimestre por domicílio [declarado, INEGI via imprensa] |
| **NSE AMAI por AGEB** (regra 2022, modelo ENIGH 2020 aplicado ao CPV 2020) | https://www.amai.org/descargas/AMAI_NSE2022_Nota_sobre_estructura_bases_NSE.pdf | **Grátis até AGEB**; manzana fora do grátis (pago, presumivelmente). Termos de uso **não verificados** | SPSS `.SAV` e Excel | município, localidade, **AGEB**, manzana: viviendas por NSE (7 níveis A/B…E) e NSE predominante | 2020 (regra 2022; há nota 2024 com a ENIGH 2022) | **verificado** (nota lida); arquivos **não baixados** |
| **Índice de Marginación Urbana 2020** (CONAPO) | https://www.datos.gob.mx/dataset/d8f2a534-bcee-4114-853d-82982a81ce24/resource/9600f414-c1ba-408a-8dd6-7f73d76601d4/download/imu_2020.csv | **CC-BY-4.0** [medido na API CKAN] | CSV UTF-8 | **AGEB urbana** (`CVE_AGEB` de 13) | 2020 | **verificado**: 50.790 AGEBs; `IM_2020`, `GM_2020` (Bajo 14.105, Medio 13.209, Muy bajo 9.292, Alto 8.274, Muy alto 5.910), indicadores de carência. **Não contém renda.** `ENT`/`MUN` sem zero à esquerda (`1`, não `01`). Também há IMU por colônia (CSV + SHP) e IM municipal/localidade 2020 |
| Pobreza CONEVAL por AGEB urbana / localidade 2020 | https://www.coneval.org.mx/Medicion/Documents/GRS_AGEB_2020/Nota_GRS_AGEB_urbana_2020.pdf | — | — | Grau de rezago social por AGEB; pobreza por localidade urbana em faixas | 2020 | **não verificado** (não aberto). O CONEVAL foi extinto e o **INEGI assumiu a medição em 17/07/2025** [declarado, imprensa] |

#### Emprego formal e momentum

| Fonte | URL | Licença | Formato | Granularidade | Ano ref. | Status |
|---|---|---|---|---|---|---|
| **IMSS — asegurados (datos abiertos)** | http://datos.imss.gob.mx/dataset/asg-2026 → `.../sites/default/files/asg-2026-09-30.csv` (401 MB/mês) | "lic-mx" (Licencia de Datos Abiertos MX) [medido na API CKAN] | CSV sep. `\|` | **município IMSS** (`cve_municipio` = `A01`…, **não é INEGI**) × setor × porte × sexo × idade × faixa salarial; `asegurados`, `masa_sal_*` | mensal; último 30/09/2026 | **verificado** (cabeçalho por *range*; pacote atualizado em 08/10/2026) |
| DENUE (para momentum: altas e baixas entre versões) | https://www.inegi.org.mx/contenidos/masiva/denue/denue_00_71_csv.zip (e demais setores) | INEGI livre | CSV latin-1 | estabelecimento com lat/lng, AGEB, manzana | 05/2026 (semestral) | **verificado** (ver A.3) |
| Vivenda nova (CONAVI/SNIIV, RUV) | https://datamx.io/vi/dataset/registro-de-vivienda | — | CSV | município | ficha diz 2018/2019 | **não verificado** |
| Licenças de construção municipais / Estadística de la Industria de la Construcción | — | — | — | — | — | **não verificado** |

#### Concorrência

| Fonte | URL | Licença | Formato | Granularidade | Ano ref. | Status |
|---|---|---|---|---|---|---|
| **DENUE — SCIAN 713943** "Centros de acondicionamiento físico del sector privado" | https://www.inegi.org.mx/contenidos/masiva/denue/denue_00_71_csv.zip | INEGI livre | CSV latin-1 | ponto (lat/lng), AGEB, manzana, CP, estrato de pessoal ocupado | 05/2026 (publicado 20/05, corrigido 01/07/2026) | **verificado** (contagem abaixo) |
| WellHub — sitemap de parceiros `es_mx` | https://wellhub.com/sitemap_partners_1_es_mx.xml (+ `_es_mx_locations.xml`) | robots.txt `Allow: /` para `*`; ToS **não verificado** | XML | URL por parceiro (slug com bairro/cidade) | out/2026 | **verificado**: **7.489 URLs** de parceiros (inclui estúdios, yoga etc.) |
| TotalPass México | https://totalpass.com/mx/para-aliados/ | — | — | — | 2026 | **não verificado** ("7.500 gimnasios, actividades y hábitos" num PDF promocional de mai/2026 [declarado]) |
| OSM (Geofabrik) | https://download.geofabrik.de/north-america/mexico-latest.osm.pbf (647 MB, 16/10/2026) | ODbL | PBF | ponto/polígono | 2026 | existência **verificada**; contagem de `leisure=fitness_centre` **não verificada** (Overpass falhou: timeout/500) |

#### Imobiliário

| Fonte | URL | Licença | Formato | Granularidade | Ano ref. | Status |
|---|---|---|---|---|---|---|
| Inmuebles24 (portal) | https://www.inmuebles24.com/ | ToS **não verificado**; robots.txt permite caminhos gerais e publica sitemaps | HTML | anúncio | 2026 | **verificado bloqueio**: listagem e termos → **HTTP 403** a cliente HTTP simples |
| Vivanuncios | https://www.vivanuncios.com.mx/ | robots.txt bloqueia `/api/*` | HTML | anúncio | 2026 | **verificado bloqueio**: listagem de locais → **403** |
| Lamudi MX | https://www.lamudi.com.mx/ | robots → 403 | HTML | anúncio | 2026 | **verificado bloqueio**: **401/403** |
| Propiedades.com | https://propiedades.com/ | robots → 403 | HTML | anúncio | 2026 | **verificado bloqueio**: **403** |
| Mercado Libre Inmuebles | https://inmuebles.mercadolibre.com.mx/ | robots.txt **bloqueia explicitamente ClaudeBot/GPTBot** | HTML | anúncio | 2026 | **verificado** (robots); listagem não testada |
| Índice Inmuebles24 (CDMX/MTY/GDL) | https://www.inmuebles24.com/blog/wp-content/uploads/2026/05/INDEX_CDMX_REPORTE_2026-04.pdf | — | PDF | colônia/cidade, **residencial** | 2026 | **não verificado** (não serve para local comercial) |
| Aluguel comercial R$/m² de referência | — | — | — | — | — | **não encontrado** (CBRE/Solili/Datoz não localizados) |

#### Macro e mercado

| Fonte | URL | Licença | Formato | Granularidade | Ano ref. | Status |
|---|---|---|---|---|---|---|
| Banxico SIE API | https://www.banxico.org.mx/SieAPIRest/service/v1/ | **token gratuito obrigatório** | JSON | série (FIX = SF43718) | diário | **verificado** (sem token → `"Token inválido"`, com URL de cadastro) |
| Câmbio de referência BCE (via Frankfurter) | https://api.frankfurter.app/latest?from=USD&to=MXN,BRL | aberto | JSON | diário | 16/10/2026 | **verificado**: USD/MXN **18,3835**; USD/BRL **5,0828** → **3,617 MXN/BRL** |
| INPC (inflação) | https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/inpc/ | INEGI livre | PDF | nacional | set/2026 | **parcial**: 3,45 % a/a (boletim de 08/10/2026, via imprensa; PDF não aberto) |
| PPP (Banco Mundial, `PA.NUS.PRVT.PP`) | https://api.worldbank.org/v2/country/MEX/indicator/PA.NUS.PRVT.PP?format=json | CC-BY-4.0 | JSON | país | 2025 | **verificado**: MX **11,309** LCU/$int; BR 2,581 |
| Smart Fit — release 2T26 | https://api.mziq.com/mzfilemanager/v2/d/757d3905-6a2d-496a-bbb0-32ddd17de6a0/1d71f14f-0745-4f1a-aef4-ba889799d97f?origin=2 | público (RI) | PDF | país | 2T26 | **verificado** (ver B) |
| Grupo Sports World — reporte 2T26 | https://www.sportsworld.com.mx/uploads/es/documents/reports_quarterly/gsw_reporte_2T26.pdf | público (BMV) | PDF | rede | 2T26 (27/07/2026) | **verificado** |

### A.2 Base censitária: qual unidade usar

| Unidade | Nº | Pop. típica | Uso proposto |
|---|---|---|---|
| **AGEB urbana** | 64.557 (MG 2023); ~64 mil com dado no CPV 2020 [declarado] | ~2.000-2.500 (AGS: 2.237 e 1.411 nas 2 primeiras) | **análogo do setor censitário BR** para o Relatório Pontual e para a ponte AGEB→hex7. Supressão ≤ 1,2 % |
| Manzana | ~2,1 M (urb. + rur.) [estimativa]; >1 M urbanas com dado | ~50-150 | Resolução fina de **população** (`POBTOT` sem supressão); demais variáveis com 5-14 % de `*` |
| AGEB rural + localidade (ITER) | 17.473 AGEB rurais; 189 mil localidades | — | População rural por **ponto de localidade** → hex direto |

Recomendações:
- **População do hex:** `POBTOT` por manzana urbana (distribuída por área) mais as localidades rurais por ponto.
- **Domicílios e moradores:** da AGEB (`TOTHOG`, `VIVPAR_HAB`, `PROM_OCUP`).
- **Atualizar para 2025:** razão município EIC 2025 / CPV 2020 (+0,7 % a.a. nacional).

### A.3 Academias e concorrência: contagem medida no DENUE 05/2026

Setor 71 inteiro: 68.423 estabelecimentos. Códigos 7139x [medido]:

| SCIAN | Descrição | Nº |
|---|---|---|
| **713943** | Centros de acondicionamiento físico del sector **privado** | **30.242** |
| 713944 | Centros de acondicionamiento físico del sector público | 2.989 |
| 713941 | Clubes deportivos del sector privado | 439 |
| 713942 | Clubes deportivos del sector público | 125 |

> A pista "713941 = academias" está **errada**: 713941 são *clubes deportivos*. O código das academias é **713943**.

**713943, perfil:**
- **Porte (pessoal ocupado):**
  - 0-5: 26.217 (86,7 %)
  - 6-10: 3.024
  - 11-30: 857
  - 31-50: 95
  - 51-100: 45
  - 101-250: 4
- **Geografia:**
  - 100 % com lat/lng.
  - Por entidade: Estado de México 4.448, Jalisco 2.132, CDMX 2.008, Veracruz 1.723, Guanajuato 1.688, Puebla 1.581, Michoacán 1.502, Nuevo León 1.347.
- **`fecha_alta` concentrada em 2024-11 (14.678)**, carga dos Censos Económicos 2024. O metadado diz que o DENUE é atualizado "fundamentalmente en el segmento de los establecimientos grandes", então **micro-academias fechadas podem persistir**: superestima.

**Marcas por regex em `nom_estab`/`raz_social` (713943 + 713944)** [medido; nome ≠ marca, então é piso]:
- Smart Fit **329**, contra 488 no release 2T26, ou seja, **~67 % de cobertura da maior rede**.
- Outras: Sports World 54, Anytime 57, Gold's 30, Sport City 27, Total Fitness 23, Fitness 24/7 21, Curves 15, Energy Fitness 12, Planet Fitness 11, Snap 7, Orangetheory 5, "CrossFit" 561.

**Implicação:**
- O DENUE é a espinha dorsal **oficial e georreferenciada** da oferta independente, o que nem o BR (GymScraping) nem a AR (OSM + web) tiveram.
- As **redes** precisam de complemento por sites e localizadores (Smart Fit, Planet Fitness, Anytime, Sports World) e WellHub/TotalPass, com dedup.

### A.4 População diurna, densidade e urbanização

- **Noturna:** CPV 2020 por manzana/AGEB, atualizada pela EIC 2025 no município.
- **Diurna:**
  - (a) **DENUE de todos os setores** traz estrato de pessoal ocupado por estabelecimento, com lat/lng: a soma do ponto médio do estrato por hex é um proxy de **trabalhadores presentes de dia** [estimativa de método; o arquivo multissetorial não foi baixado];
  - (b) `MUN_TRAB` (CPV 2020 ampliado, **verificado** no cabeçalho) e a mobilidade da EIC 2025 dão fluxo origem-destino **municipal**.
- **Urbanização:** no AGS, 84 % da população está em AGEB urbana [medido].

### A.5 Momentum urbano

| Substituto do BR | MX | Grão | Status |
|---|---|---|---|
| CAGED/RAIS (emprego formal, salário) | **IMSS asegurados + massa salarial**, mensal | município IMSS (exige crosswalk para INEGI) | verificado |
| Receita (empresas novas) | **DENUE**: diferença entre versões semestrais e `fecha_alta` | estabelecimento → hex | verificado (1 versão) |
| Crescimento populacional | **CPV 2020 → EIC 2025** por município | município | boletim verificado; tabulado municipal não |
| Obras / vivenda nova | SNIIV/RUV; licenças municipais | município | não verificado |

---

## B. Mercado fitness

| Indicador | Valor | Fonte e data | Status |
|---|---|---|---|
| **Smart Fit — academias no MX** | **488** (2T26); 471 (1T26); 403 (2T25); 465 no fim de 2025 | Release 2T26 (05/08/2026), gráfico "Evolução do número de academias"; 465 via imprensa (Moneytimes/Suno) | **verificado** (488/471/403); 465 [declarado] |
| Smart Fit — clientes em academias no MX | **1,255 M** (2T26); 1,110 M (2T25) → **~2.570 clientes/unidade** | Release 2T26 | **verificado** (série lida no texto extraído; atribuição à legenda pela ordem e pelo total, que fecha 5.582 mil) |
| Smart Fit — plano de 2026 no MX | ~70 aberturas; investimento > 1.500 M MXN (≈ 21 M MXN/unidade); "> 500 unidades" e 1,3 M usuários | Emprendedor, 10/09/2026 | **verificado** (nota lida); números da empresa |
| Smart Fit — capex por unidade | 16 M MXN (próprias e franquias) | Forbes México (sem data) | **não verificado** |
| **Smart Fit — preço** | Fit **299**, Smart **399** (sem permanência), Black **599** MXN/mês; 1º mês grátis; "pode variar por unidade" | https://www.smartfit.com.mx/planes | **verificado** |
| Profeco (sondagem 19-20/11/2024) | Smart Fit 559/mês + 1.499 de inscrição; Anytime 1.197 + 1.500; Sports World 1.698 + 5.000 | adn40, 02/01/2025 | **não verificado** na fonte primária Profeco |
| **Grupo Sports World** (premium) | **49 clubes**; **96.930** clientes ativos (2T26); receita do 1S26 de 1.164,8 M MXN | Reporte 2T26, 27/07/2026 | **verificado** |
| **Planet Fitness MX** | **50 clubes** (25 dois anos antes); > 300 mil sócios; 15 estados; operador "Fitness para Todos" | Forbes MX, 14/09/2026 | **verificado** (nota lida) |
| **Anytime Fitness MX** | "> 110 clubes em 26 estados"; meta de 200 em ~3 anos | Emprendedor, 01/01/2026 | **verificado** (nota lida) |
| Energy Fitness | A quebra de 2026 é da rede **chilena**; no MX, "7 unidades" (dado de 2017) | The Clinic / El Financiero | **não verificado** para o MX atual |
| Fitness 24/7 MX | sem dado de unidades nem preço no MX (só documentos da Colômbia) | — | **não verificado** |
| WellHub MX | 7.489 páginas de parceiros no sitemap `es_mx`; "+800 academias em 2024" | sitemap (medido); release de dez/2024 [declarado] | parcial |
| TotalPass MX | líder entre agregadores no MX (release Smart Fit 2T26, Sensor Tower); rede +45 % no 1T26 [declarado]; "7.500 gimnasios, actividades y hábitos" | release 2T26 (verificado); PDF promocional (não verificado) | parcial |
| **Penetração** | 3 % (Emprendedor 2023), ~6 % (AgendaPro 2026, sem fonte primária), 2,5 % (Forbes), "> 4 M membros" (Forbes) | — | **não verificado**: sem fonte primária |
| Piso medido de penetração (só redes com dado) | Smart Fit 1,255 M + Sports World 0,097 M + Planet Fitness > 0,3 M ≈ **1,65 M = 1,26 % de 130,9 M** | [estimativa] sobre números verificados | piso, não estimativa central |
| Faturamento do setor | ~US$ 2,1 bi (2024), atribuído à AMEGYC | AgendaPro | **não verificado** |
| Radiografía Mercado Fitness México 2024 | https://mercadofitness.com/pdf/radiografia-mexico-2024-mercado-fitness.pdf | > 10 MB, não lido | **não verificado** |

**Ticket em três moedas (Smart Fit plano Smart, 399 MXN, com IVA):**

| Moeda | Conta | Valor |
|---|---|---|
| USD | 399 ÷ 18,3835 | **US$ 21,7** |
| PPP | 399 ÷ 11,309 | **$int 35,3** |
| BRL | 399 ÷ 3,617 | **R$ 110** |
| Líquido de IVA | 399 ÷ 1,16 | **344 MXN** (US$ 18,7) |

**Maturidade do low-cost:**
- **Alta e já ocupada pela Smart Fit:** 488 unidades, ~2.570 clientes/unidade, MX = 23 % da rede global.
- Concorrentes HVLP diretos: Planet Fitness (50) e Anytime (franquia, ticket ~2-3× maior).
- Entrante low-cost no MX compete **frontalmente** com o líder no seu 2º maior mercado. A Smart Fit diz buscar imóveis grandes via Grupo Gigante, FUNO e Danhos (Forbes MX), o que indica **competição também pelo imóvel âncora**.

---

## C. Regulação

1. **Proteção de dados:** **nova LFPDPPP**.
   - Publicada no DOF em **20/03/2025**, vigente desde 21/03/2025; abrogou a lei de 2010.
   - O **INAI foi extinto**; a competência sobre particulares passou à **Secretaría Anticorrupción y Buen Gobierno** ("Transparencia para el Pueblo").
   - Consentimento tem de ser renovado para finalidade nova, e caiu a figura de finalidade "compatível ou análoga".
   - Multas em UMA; defesa via amparo.
   - Fontes: EY Law Flash (26/03/2025, lido), Garrigues, Basham [declarado].
   - Texto do DOF **não verificado** diretamente.
   - **Impacto no motor:** é baixo, porque as camadas usam agregados sem PII. A coleta de concorrentes deve **descartar telefone e e-mail** do DENUE (os campos existem: `telefono`, `correoelec`) e não reter nome de pessoa física.
2. **Scraping e termos de uso:**
   - **INEGI, CONAPO (CC-BY) e IMSS (lic-mx):** uso comercial permitido com atribuição.
   - **WellHub:** robots `Allow: /`; ToS não lido.
   - **Portais imobiliários:** 403/401 (anti-bot ativo).
   - **Mercado Libre:** bloqueia explicitamente bots de IA no robots.txt.
   - **Direito autoral:** a LFDA protege compilações (art. 107, não os dados em si) e proíbe contornar medida tecnológica (art. 114 Bis) [declarado, UNU/UNAM]. **Contornar anti-bot de portal tem risco jurídico maior que no BR.** O caminho recomendado é parceria ou API (Inmuebles24/Navent, Spot2) ou corretor.
3. **Franquias:** **LFPPI** (2020), art. 245.
   - Franquia = licença de marca + transmissão de *know-how*.
   - O franqueador entrega a informação da empresa (a **COF**) **pelo menos 30 dias antes** do contrato.
   - Informação falsa → nulidade + perdas e danos (1 ano).
   - O art. 124 do Reglamento lista o conteúdo, incluindo **montos de investimento, tempos de retorno e nº de unidades próprias e franqueadas**.
   - Fontes: mLey, SDV (lidos). O mLey marca o parágrafo como "reformado DOF 03-04-2026": **não verificado** no DOF.
   - **Consequência para o motor:** o DRE/payback do módulo de viabilidade vira **insumo da COF**, ou seja, número com responsabilidade legal → exige premissas MX próprias, não BR.
4. **Investimento estrangeiro:** a **LIE** art. 4 permite 100 % de capital estrangeiro salvo exceções.
   - O art. 7 (limites) e o art. 5 (reservas) **não incluem academias ou serviços de esparcimento** (mLey, art. 7, lido).
   - **Não verificados:** inscrição no RNIE (Registro Nacional de Inversiones Extranjeras) e a **zona restrita** (100 km das fronteiras / 50 km do litoral) para propriedade direta de imóvel por estrangeiro. Afeta compra, não aluguel.
5. **Trabalhista:**
   - **Jornada de 40 h** aprovada (reforma constitucional publicada no DOF em mar/2026, LFT em mai/2026), **gradual: 48 h em 2026 → 46 h em 2027 → … → 40 h em 2030**, sem redução salarial [declarado, Baker McKenzie/Animal Político; DOF não verificado].
   - Academia aberta ~16 h/dia → mais turnos ou horas extras pagas a +100 %.
   - Salário mínimo de 2026: +13 % (≈ 315 MXN/dia, **não verificado**).

---

## D. Macro, tributos e efeito no DRE

| Item | Valor | Status |
|---|---|---|
| Moeda | Peso mexicano (MXN), símbolo `$`; locale `es-MX`, separador decimal `.` e de milhar `,` (o **inverso** do BR) | conhecido |
| Câmbio | USD/MXN **18,3835** (16/10/2026); **forte depreciação recente**: 17,00 em 01/09 → 18,52 em 15/10 (**+8,9 % em 6 semanas**); BRL/MXN 3,617 | **verificado** (BCE) |
| Inflação | **3,45 % a/a** (set/2026); núcleo 3,75 %; meta 3 % ± 1 | parcial (imprensa citando boletim INEGI de 08/10/2026) |
| Juros | Taxa objetivo Banxico **6,50 %** (decisão de 24/09/2026); convergência à meta só no 4T27 | [declarado, imprensa] |
| PPP | 11,309 MXN/$int (consumo privado, 2025) | **verificado** |
| **ISR** pessoa moral | **30 %** do lucro fiscal (LISR art. 9); zona fronteiriça norte com estímulo (efetivo ~20 %), decreto prorrogado em 31/12/2025 | [declarado] |
| **IVA** | **16 %** (8 % na zona fronteiriça norte com estímulo) — **embutido no preço ao consumidor** | [declarado] |
| **PTU** | **10 %** da renda tributável distribuída aos empregados (LFT art. 117; tetos da reforma de 2021) | conhecimento prévio, **não reconferido** |
| **ISN** (estadual, sobre folha) | **CDMX 4 %** desde 2025 (era 3 %; Gaceta de 27/12/2024), com redução de 1 p.p. para empresa que inicia operação; demais estados ~2-4 % com alta em 2026 (BCS 3 %, Chihuahua 4 %) | [declarado]: fontes secundárias divergem por estado |
| Encargos IMSS/INFONAVIT/SAR do empregador | não levantado | **não verificado** |
| Retenção sobre royalties ao exterior (franqueador BR → franqueado MX) | depende do tratado Brasil-México | **não verificado** |

**Efeito no DRE e no payback (mecânico, sobre a estrutura do motor):**
1. **Receita líquida = preço ÷ 1,16:** o IVA tira **13,8 %** do ticket de tabela, contra ISS/PIS/COFINS no BR, cuja alíquota depende do regime.
2. **Carga sobre o lucro antes de impostos (X):**
   - PTU = 0,10·X;
   - ISR = 0,30·(X − PTU) = 0,27·X;
   - **total ≈ 37 % de X** (lucro líquido ≈ 0,63·X).
3. **Folha:** ISN de 3-4 % mais encargos da seguridade, e a transição para 40 h até 2030 encarece a folha de uma operação de 16 h/dia.
4. **Capital:** Banxico a 6,5 % barateia financiamento contra um custo de capital alto no BR [estimativa qualitativa]. Já a **volatilidade cambial** (+9 % em 6 semanas) afeta capex importado (equipamento em USD) e qualquer conversão para BRL na viabilidade.
5. **Benchmark de capex:** ~16-21 M MXN por unidade Smart Fit (≈ US$ 0,9-1,2 M) [declarado / estimativa]. A plataforma converte para BRL (decisão 0.6): o par `MXN/USD` + `BRL/USD` precisa ser declarado no perfil com o mesmo mês-base.

---

## E. Veredito de dados por camada

| Camada | Veredito | Insumo MX → coluna do contrato | Impacto no ranking |
|---|---|---|---|
| **Identidade (§2.0)** | **Completa**, com 3 adaptações | `hex_id`/`lat`/`lng`: H3 sobre o MG reprojetado. `nome_municipio`: `NOMGEO` do `00mun`. **`cod_municipio` = `CVEGEO` de 5 dígitos como string** (`"09015"`), nunca int: o IMU traz `ENT`/`MUN` sem zero. Partição `uf=XX`: **32 siglas de 2 letras fabricadas** (a ISO 3166-2:MX é de 3: `AGU`, `BCN`, `CMX`…), com colisão provável com UFs BR (ex.: `MG`, `SP`), como aconteceu na AR | Nenhum, se a sigla for tabelada. O join de crescimento por `cod6` **não casa** com 5 dígitos (mesmo defeito da AR) |
| **1 — Potencial** | **Parcial com proxy (bom)** | `pop_total_setor_2022` ← `POBTOT` manzana/AGEB 2020 (+ rural por ITER) × fator EIC 2025. `populacao_corte_hex` ← soma do hex + 6 vizinhos. **`renda_per_capita`** ← renda modelada (abaixo), em **USD** como na AR (`moeda.indicadores_renda: "USD"`), ou em MXN com âncoras próprias. `densidade_pop_setor_hab_km2` ← `POBTOT` / área do polígono do MG | **Moderado.** População é medida (melhor que a AR, com manzana). Renda é modelada, mas sobre renda **medida** no município (CPV ampliado `INGTRMEN`, ENIGH com `ubica_geo`), com o rank intra-municipal vindo de covariáveis da AGEB (`GRAPROES`, `VPH_AUTOM`, `VPH_PC`, `VPH_INTER`, `PDER_SS`) e validação cruzada contra **NSE AMAI** e **IMU**. Erro esperado menor que os ±15 % da AR no município; desconhecido dentro do município (**não medido**). Âncoras do `nota_renda` são **decisão**, não transcrição |
| **2 — Residual** | **Parcial com proxy** | `sam_fitness_potencial` ← pop × taxa (**penetração MX sem fonte primária**: piso medido 1,26 %, publicado 3-6 %). `oferta_consumida_mercado_estimada` ← DENUE 713943 + redes × **capacidade calibrada por estrato de pessoal ocupado** (não constante: 86,7 % é 0-5 empregados; Smart Fit ~2.570/unidade). `oferta_efetiva_disponivel` em **alunos** | **Alto risco silencioso**: a taxa de penetração e a capacidade definem a escala do residual, e os pisos da camada 2 e as âncoras da camada 5 são em alunos. Calibrar com a régua `clientes_rede / unidades_rede` (Smart Fit, SW, PF) e checar o total contra 3-6 % |
| **3 — Pressão** | **Completa** (a melhor dos 4 países) | `staging/concorrentes_mapeados.parquet` ← DENUE (lat/lng, `status_registro` a derivar de `fecha_alta` e da presença em versões sucessivas) + sites das redes + WellHub, com dedup. `n_concorrentes_influencia_1km` ← contagem real em disco de 1 km. `capacidade_default_concorrente_alunos` ← calibrada | **Baixo.** Atenção: o DENUE superestima micro-academias fechadas e cobre ~67 % da Smart Fit pelo nome |
| **4 — Momentum** | **Parcial com proxy** | `crescimento_municipal`: IMSS asegurados/massa salarial (mensal; **crosswalk IMSS→INEGI**) + saldo de estabelecimentos DENUE + pop. 2020→2025 (EIC). `cres_chave_nome = "<UF>\|<NOME>"` é o fallback. `crescimento_hex`: delta de estabelecimentos DENUE por hex entre versões semestrais | **Moderado.** O join por `cod6` precisa de correção na plataforma (ou `cod6` fabricado com zfill(6) do `CVEGEO`) |
| **5 — Fila** | **Parcial** (herda 1 e 2) | `indice = 0,70·socio + 0,30·nota_dem` | A fila fica confiável **só** se o residual estiver na escala certa; senão vira "só socio" (achatamento já visto na AR) |
| **Relatório Pontual** | **Completa com proxy de renda** | Polígono = **AGEB urbana** (MG 2020) com `pop_total_setor_2022` ← `POBTOT`, `domicilios_particulares_ocupados_setor_2022` ← `TOTHOG`/`VIVPAR_HAB`, `avg_moradores_domicilio_setor_2022` ← `PROM_OCUP`, `renda_per_capita_setor_2022_calibrada` ← renda modelada por AGEB, `nome_bairro` ← **não existe no MG** (colônia vem do IMU por colônia CC-BY ou do DENUE `nomb_asent`), `geometry_wkb` reprojetado de LCC para geográficas | A AGEB (~2 mil hab.) é ~3-4× maior que o setor BR. Num raio de 1 km cabem poucas AGEBs, então a borda pesa mais. Alternativa: manzana para população |
| **Viabilidade** | **Parcial** | Câmbio `MXN/USD` + `BRL/USD`; **premissas tributárias próprias** (IVA por dentro, ISR 30 % + PTU 10 %, ISN estadual, encargos); aluguel-teto **sem fonte pública de R$/m² comercial** | Alto: rodar com tributo BR (como a AR) daria número errado **e com efeito legal** se usado na COF |
| **Oportunidades imobiliárias** | **Inviável sem custo** | Todos os portais testados bloqueiam (403/401); não há índice público de aluguel comercial | Superfície desligada até haver parceria ou anti-bot pago |
| **M&A / agregadores** | **Parcial** | WellHub (sitemap `es_mx`, 7.489 páginas) e TotalPass (líder) operam no MX: reaproveitável | — |

---

## F. Premissas frágeis, onde a analogia BR/AR quebra, e o que ficou não verificado

### Premissas frágeis

1. **"O censo mede renda."** Falso no MX também.
   - O questionário básico (AGEB/manzana) não tem renda; só o **ampliado** tem `INGTRMEN`, e só até município.
   - A renda por AGEB será **modelada**, como na AR. A diferença é que o MX tem renda **medida** no município (CPV ampliado + ENIGH com `ubica_geo`), o que permite calibrar o modelo por município, não só por região.
2. **"Unidade mínima = setor censitário."**
   - A AGEB (~2 mil hab.) é maior que o setor BR.
   - A manzana é menor, mas com 5-14 % de supressão `*` (confidencialidade < 3 unidades).
   - Tratar `*` como **ausente**, não como zero.
3. **"Capacidade de concorrente = 2.500 alunos."** Quebra mais forte que na AR:
   - 30.242 micro-academias (86,7 % com 0-5 empregados) contra uma rede (Smart Fit) com ~2.570 clientes/unidade;
   - uma constante única ou subestima o líder ou superestima os micro.
   - Usar capacidade **por estrato** de `per_ocu`.
4. **"Penetração calibrada."** Não há pesquisa primária pública de penetração no MX.
   - Os números de imprensa (3 %, 6 %) divergem 2× e não têm metodologia.
   - Só redes listadas dão piso (1,26 %).
5. **Concorrência local já ocupada.**
   - O MX é o 2º maior mercado da Smart Fit e onde ela mede a sua TotalPass;
   - a analogia "entrar como low-cost em praça desatendida" vale menos que no BR interiorano.
6. **Moeda e locale.**
   - Separador decimal invertido (R10 da AR: `mascara.ts` fixo).
   - Câmbio volátil (+8,9 % em 6 semanas) muda a conversão para BRL da viabilidade entre duas rodadas.
7. **Chaves:**
   - `CVEGEO` de 5 dígitos (o `cod6` não casa);
   - código de município **do IMSS** diferente do INEGI;
   - número de municípios muda entre versões (2.469 → 2.475 → 2.478);
   - o IMU vem sem zero à esquerda;
   - **AGEB tem caractere alfanumérico** (`025A`): nunca converter para int.
8. **Siglas de 2 letras:** a ISO é de 3 letras, então fabricar 32 siglas, com risco de colisão com UFs BR (lição da AR).
9. **Escala:** ~95-100 mil hexes povoados (~2,3× a AR), 2,1 M manzanas e ~2,4 GB de CSV de AGEB/manzana descompactado. Pipeline por entidade, como no BR.
10. **Imobiliário:**
    - O coletor BR depende de portal raspável; no MX os quatro portais testados bloqueiam;
    - a LFDA (art. 114 Bis) torna o contorno de medida técnica juridicamente mais arriscado.
11. **Franquia com responsabilidade legal:** os números de investimento e retorno entram na COF (LFPPI art. 245 + Reglamento art. 124). Viabilidade com premissa BR é risco legal, não só técnico.

### Lista explícita do que ficou NÃO VERIFICADO

- Marco Geoestadístico posterior a dez/2023 (2024/2025): não encontrado. Tamanho nacional do MG com manzanas (estimado em 1-2 GB).
- EIC 2025:
  - tabulados por município e formato dos microdados;
  - **se há pergunta de renda do trabalho**.
- NSE AMAI por AGEB: arquivos não baixados; termos de uso; o nível manzana é pago (presumido).
- CONEVAL/INEGI: rezago social e pobreza por AGEB/localidade 2020 (não abertos); medição 2025.
- Tamanho do estimador do `INGTRMEN` por município (precisão) e se a AGEB existe no microdado restrito (laboratório INEGI).
- **Tradução** IMSS município → INEGI (catálogo não localizado nesta sessão).
- SNIIV/RUV atualizado; licenças de construção municipais.
- Contagem OSM de `leisure=fitness_centre` no MX (Overpass falhou).
- Termos de uso: WellHub, Inmuebles24, Vivanuncios, Lamudi, Propiedades.com, TotalPass. Contagem de aliados TotalPass MX.
- Penetração do fitness no MX; faturamento do setor (AMEGYC); conteúdo da Radiografía Mercado Fitness 2024.
- Smart Fit: participação própria × franquia no MX; capex de 16 M MXN por unidade.
- Unidades e preço atuais de Fitness 24/7, Energy Fitness MX, Sport City (só o regex do DENUE: 27).
- Profeco: fonte primária da sondagem de nov/2024.
- Aluguel comercial por m² (CDMX, MTY, GDL): **nenhuma fonte encontrada**.
- Legislação, com o texto do DOF não aberto (só fontes secundárias):
  - LFPDPPP 2025;
  - jornada de 40 h;
  - LFPPI art. 245 (reforma de 03/04/2026).
- Valores:
  - PTU de 10 % (não reconferida);
  - ISN por estado (fontes divergem; só CDMX 4 % tem duas fontes);
  - encargos IMSS do empregador;
  - salário mínimo de 2026;
  - INPC de set/2026 na fonte primária;
  - taxa Banxico.
- LIE: RNIE e zona restrita.
- Tratado Brasil-México (retenção sobre royalties).
- DENUE multissetorial (para população diurna): não baixado.

### Fontes consultadas (além das URLs das tabelas)

- INEGI:
  - termos: https://www.inegi.org.mx/inegi/terminos.html
  - CPV 2020 AGEB/manzana: https://www.inegi.org.mx/contenidos/programas/ccpv/2020/doc/fd_agebmza_urbana_cpv2020.pdf
  - boletim EIC 2025: https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/ei/EIC2025-def_CP.pdf
- AMAI, nota NSE 2022: https://www.amai.org/descargas/AMAI_NSE2022_Nota_sobre_estructura_bases_NSE.pdf
- CONAPO, índices de marginação (CKAN): https://www.datos.gob.mx/api/3/action/package_show?id=indices_marginacion
- IMSS CKAN: http://datos.imss.gob.mx/api/3/action/package_show?id=asg-2026
- Smart Fit:
  - release 2T26 (link mziq acima);
  - planos: https://www.smartfit.com.mx/planes
  - Emprendedor: https://emprendedor.com/smart-fit-acelera-su-expansion-en-mexico-invertira-mas-de-1500-mdp-y-abrira-70-gimnasios/
- Sports World 2T26: https://www.sportsworld.com.mx/uploads/es/documents/reports_quarterly/gsw_reporte_2T26.pdf
- Planet Fitness: https://forbes.com.mx/?p=1432365
- Anytime Fitness: https://emprendedor.com/expansion-anytime-fitness-mexico-david-rascon-200-gimnasios/
- Profeco via adn40: https://www.adn40.mx/mexico/2025-01-02/profeco-anuncia-gimnasio-mas-barato-2025-cumple-propositos-ano-nuevo/
- LFPDPPP:
  - EY: https://www.ey.com/es_mx/technical/tax/boletines-fiscales/nueva-ley-federal-proteccion-datos-personal-posesion-particulares
  - Garrigues: https://www.garrigues.com/es_ES/noticia/mexico-nueva-ley-federal-proteccion-datos-personales-posesion-particulares-introduce
- LFPPI art. 245: https://mley.mx/LFPPI/articulo/245/
- LIE art. 7: https://mley.mx/LIE/articulo/7/
- Scraping e LFDA: https://law.ungovr.org/ai/mx
- Jornada de 40 h: https://www.bakermckenzie.com/en/insight/publications/2026/04/mexico-federal-labor-law-reform-shortens-work-wee
- ISN CDMX: https://facturama.mx/blog/impuesto-sobre-nominas-en-cdmx/
- Banxico (decisão de 24/09/2026): https://www.excelsior.com.mx/finanzas/banxico-mantiene-tasa-clave-6-5
- INPC set/2026: https://www.elcontribuyente.mx/2026/10/inflacion-anual-sube-a-345-reporta-inegi/
- Banco Mundial PPP: https://api.worldbank.org/v2/country/MEX/indicator/PA.NUS.PRVT.PP?format=json
- INEGI assumindo o CONEVAL: https://elceo.com/economia/inegi-asume-las-funciones-del-coneval-y-divulga-nuevo-calendario/
