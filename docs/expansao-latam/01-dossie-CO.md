# Dossiê de dados — COLÔMBIA (CO) para o Motor de Expansão

> **Leia junto com `01-consolidacao-auditoria.md`.** Este dossiê é a versão de campo, de 2026-10-16. A auditoria cruzada corrigiu alguns números e vereditos depois dele, e a versão corrigida vale sobre esta.

- **Data de acesso de todas as fontes:** 2026-10-16. Somente pesquisa: nada foi alterado no repositório.
- **Amostras baixadas** (dado não confiável, lido só com `python -I`, nada executado): `C:\Users\Pichau\AppData\Local\Temp\claude\C--Users-Pichau-Documents-motor-de-expansao\d45e86bf-d899-46b1-bd74-dd25828a14cf\scratchpad\amostras\CO\` (9,8 MB no total). Os scripts de leitura ficam em `...\scratchpad\scripts_co\`, fora da pasta das amostras.
- **Convenção:** `verificado` = abri a página ou baixei amostra e li o dado. `não verificado` = só vi citação em busca ou em imprensa. **[estimativa]** = conta minha sobre números verificados.
- **Bloqueio de rede (registrar):** deste ambiente, três hosts governamentais **recusaram conexão TCP**: `geoportal.dane.gov.co`, `serviciosgis.catastrobogota.gov.co` e `datosabiertos.bogota.gov.co`. O motivo provável é geobloqueio ou firewall. O pipeline precisa rodar de onde esses hosts respondem, ou usar os espelhos que funcionaram (`microdatos.dane.gov.co`, `www.dane.gov.co`, `www.datos.gov.co`).

---

## Resumo executivo (5 linhas)

1. **A Colômbia tem a melhor base censitária geográfica dos quatro países candidatos para o grão do motor.** O MGN 2018 integrado ao CNPV vem com **504.996 manzanas** em shapefile WGS84 e 80 variáveis cada: pessoas, domicílios, viviendas e **viviendas por ESTRATO 1-6**. Foi baixado e lido.
2. **O censo é velho:** população de 2018, sem censo nem conteo previsto antes de 2030 (o conteo de 2025 foi **cancelado**). Os 44,16 M recenseados precisam ser escalados para 53,40 M (projeção DANE 2026), um fator nacional de **×1,209** que **não é uniforme no espaço**.
3. **Não existe renda no censo.** A renda tem de ser **modelada** a partir da GEIH/Pobreza Monetária (microdados públicos, `ingpcug` verificado) usando o **estrato**, que existe nas duas bases. É um proxy melhor que o argentino, porque o estrato é observado por manzana.
4. **A concorrência é o elo fraco.** O WellHub **não tem sitemap para a Colômbia** (é a espinha dorsal da AR); o TotalPass não tem operação confirmada; o OSM tem só ~1.167 feições de fitness, contra 7.940 instalações segundo a HFA. Há duas fontes boas: o sitemap da Smart Fit (245 sedes, com `geo.position` na página) e o RUES (8.076 matrículas ativas no CIIU 9311, mas sem endereço geocodificado).
5. **No macro, o que pesa é o COP volátil e o custo de pessoal.** O COP valorizou ~23 % contra o USD em 12 meses; o salário mínimo subiu ~23 % em 2026; a inflação está em 6,29 % e a taxa do Banrep em 12,25 %. O **IVA sobre a mensalidade** (se for 19 %) **não foi verificado** e muda o DRE em dois dígitos.

---

## A. Dados por camada do funil

### A.1 Tabela de fontes (regra de evidência)

| # | Camada | Fonte / produto | URL | Licença / termos | Formato | Granularidade | Ano ref. | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | Identidade, malha, censo | **MGN 2018 integrado ao CNPV — nível MANZANA** (`MGN_ANM_MANZANA`) | https://microdatos.dane.gov.co/index.php/catalog/643/download/14045 (ZIP de 321.232.430 bytes) | Público, uso livre com citação ao DANE. Anonimizado por reserva estatística (Lei 79/1993). **Termo formal de licença não lido** | Shapefile (`.shp/.dbf/.prj/.shx`), **WGS84 (EPSG:4326)** | **504.996 manzanas** (clase 1 = 407.851; clase 2 = 97.145). Chave `COD_DANE_A` com 22 caracteres | 2018 | **verificado**: central directory do ZIP lido por range request. O `.prj` é GCS_WGS_1984. O `.dbf` tem **109 campos e 504.996 registros**; 2 registros lidos (Abejorral, 05002) |
| 2 | Identidade, malha | MGN integrado: níveis município, setor urbano, seção urbana, zona urbana, seção/setor rural, departamento | catálogo 643, downloads 14037-14046 | idem | Shapefile | Município (64,6 MB), setor urbano (223 MB), seção urbana (228 MB) etc. | 2018 | **verificado**: listagem do catálogo; *range* 206 OK em 14037 e 14044. Conteúdo interno de 14037/14044 **não lido** |
| 3 | Censo, dicionário | Dicionário `CNPV2018_DIC_ANDA2_MGN_MZA_20200129.xlsx` e instrutivo do MGN integrado (set/2020) | https://microdatos.dane.gov.co/index.php/catalog/643/download/12620 e /14036 | idem | XLSX, PDF | — | 2018 | **verificado** (baixados e lidos). O instrutivo documenta a anonimização (manzana com 1-3 viviendas ocupadas é unida à vizinha ou sobe de nível) |
| 4 | Censo, microdados | Microdados CNPV 2018 por departamento (33 ZIPs: viviendas, hogares, personas, com `U_MZA`) | https://microdatos.dane.gov.co/index.php/catalog/643/get-microdata | Página não mostra termos | ZIP (conteúdo não inspecionado) | Registro de vivienda/pessoa com código de manzana; contém `VA1_ESTRATO` | 2018 | **parcial**: a lista de arquivos foi vista e o dicionário (variável `VA1_ESTRATO` = "Estrato de la vivienda según servicio de energía") foi lido; **os ZIPs não foram baixados** |
| 5 | População atual | **Projeções municipais por área** (cabecera / centros poblados e rural disperso / total), 2018-2042, atualizadas em 30/07/2025 | https://www.dane.gov.co/files/censo2018/proyecciones-de-poblacion/Municipal/PPED-AreaMun-2018-2042_VP.xlsx | Público DANE | XLSX (3,9 MB) | Município (**1.123 códigos DIVIPOLA de 5 dígitos**) × área × ano | 2018-2042 | **verificado** (baixado e lido). Totais nacionais: 2018 = 48.258.494; 2025 = 53.057.212; **2026 = 53.399.171**. Bogotá 2026 = 7.945.996; Medellín 2.526.795; Cali 2.269.983. Em 2026, 60 municípios com cabecera ≥ 100 mil e 100 com cabecera ≥ 50 mil |
| 6 | População atual | Projeções por área, sexo e idade simples (2018-2042) | .../PPED-AreaSexoEdadMun-2018-2042_VP.xlsx | idem | XLSX | Município | 2018-2042 | **não verificado** (só listado na página) |
| 7 | População intraurbana | Projeções de Bogotá por localidad (2018-2035) e UPZ (2018-2024) | página "proyecciones-de-poblacion-bogota" | — | — | Localidad / UPZ | — | **não verificado** |
| 8 | Renda (camada 1) | **Medição de Pobreza Monetária e Desigualdade 2024** (microdados): `ingpcug` (renda per capita da unidade de gasto), `ingtotug`, `lp`, `li`, `pobre`, `npersug`, `dominio`, `clase`, `dpto`, `fex_c` | https://microdatos.dane.gov.co/index.php/catalog/874 (DDI: /metadata/export/874/ddi) | Microdados públicos DANE (condição de acesso **não lida**) | ZIP (Hogares: 275.057 casos, 23 variáveis; Personas: 784.910 casos, 133 variáveis) | Domínios: 13 cidades/áreas metropolitanas + 23 capitais + resto. **Sem município fora dos domínios** | 2024 (há 2025, catálogo 908) | **verificado** (DDI baixado; as variáveis citadas existem nos arquivos F4/F5) |
| 9 | Renda (covariáveis) | **GEIH 2025** (mercado de trabalho e renda), mensal | https://microdatos.dane.gov.co/index.php/catalog/853 | idem | 12 ZIPs mensais (jan-dez/2025, publicados de 11/09/2025 a 12/02/2026) | Variáveis `AREA`, `CLASE`, `DPTO` e **`P4030S1A1` = "Estrato para tarifa"** | 2025 | **verificado** (DDI lido; o estrato existe na GEIH) |
| 10 | Renda (contexto) | Linhas de pobreza 2025: nacional COP 482.041 per capita/mês; extrema COP 236.580. Incidência 28 % nacional, 24,6 % em cabeceras | https://www.dane.gov.co/files/operaciones/PM/bol-PM-2025.pdf | Público | PDF | Nacional / domínio | 2025 | **não verificado** (citação em busca; PDF não aberto) |
| 11 | Renda (proxy alternativo) | IPM de fonte censal **por manzana** (só cabeceras) | http://geoportal.dane.gov.co/visipm/ | — | Geovisor (download não confirmado); Barranquilla republica a camada | Manzana urbana | 2018 | **não verificado** (host do geoportal inacessível daqui) |
| 12 | Renda (proxy local) | Estratificação oficial por manzana dos municípios (Decreto 2220/1993: unidade ≤ manzana). Ex.: Bogotá (SDP), Cali (Datos Abiertos Cali, 2015) | datosabiertos.bogota.gov.co; https://datos.cali.gov.co/dataset/estratificacion-socioeconomica-urbana-en-cali-ano-2015 | Varia por município (Bogotá declara CC BY 4.0 em outros conjuntos) | SHP/CSV, varia | Manzana / lado de manzana | Varia | **não verificado** (portal de Bogotá inacessível daqui; o de Cali só por busca) |
| 13 | Imobiliário (proxy) | Catastro Bogotá — **mediana do valor comercial do m² de terreno por manzana** (valor de referência, 2016-2025) | https://serviciosgis.catastrobogota.gov.co/arcgis/rest/services/catastro/valorreferencia/MapServer | Portal de Bogotá declara CC BY 4.0 | ArcGIS REST / SHP | Manzana (só Bogotá) | 2016-2025 | **não verificado** (host recusou conexão) |
| 14 | Concorrência | **Smart Fit Colômbia — sitemap e páginas de sede** | https://www.smartfit.com.co/sitemap.xml; ex. https://www.smartfit.com.co/sedes/el-castillo | `robots.txt` permite `/sedes` (bloqueia `/api`, `/search` etc.). Termos de uso **não lidos** | XML + HTML com `<meta name="geo.position" content="lat;lng">` | Ponto (sede) | 2026-10-15 (lastmod) | **verificado**: 253 URLs, das quais **245 páginas de sede**; uma sede amostrada tem `geo.position` = 10.425311;-75.540879 (Cartagena). Algumas páginas dizem "preventa" (sede a abrir) |
| 15 | Concorrência | **RUES — "Establecimientos - Agencias - Sucursales"** (Confecámaras), filtro CIIU 9311 | https://www.datos.gov.co/resource/nb3d-v3n7.json | **CC BY-SA 4.0**. **Contém dado pessoal** (cédula de pessoa natural): ver C.1 | API Socrata (JSON/CSV) | **Câmara de comércio** (57 jurisdições). **Sem endereço nem coordenada** nos campos | Atualizado em 2026-10-02 | **verificado** (consulta agregada): 6.391.836 registros no total; CIIU 9311 = 21.616, dos quais **8.076 ACTIVA**. Por câmara: Bogotá 1.161, Cali 511, Ibagué 424, Medellín 408, Bucaramanga 323, Barranquilla 319 |
| 16 | Concorrência | OpenStreetMap (`leisure=fitness_centre` ∪ `amenity=gym` ∪ `sport=fitness`) | Overpass (espelho maps.mail.ru); PBF https://download.geofabrik.de/south-america/colombia.html (316 MB, dados até 2026-10-15) | ODbL 1.0 | PBF / JSON | Ponto/polígono | 2026-10-16 | **verificado**: `fitness_centre` = 740 feições; a união das três tags = **1.167**. A contagem de Smart Fit no OSM deu timeout (**não verificado**) |
| 17 | Concorrência | WellHub (sitemap de parceiros por país) | https://wellhub.com/sitemap_partners.xml | `robots.txt` permite `/` para `*` | XML | — | 2026-10-16 | **verificado (resultado negativo)**: há sitemaps de 17 locales (br, us, mx, cl, ar, es, de, it, uk, ie, ca, pt, ro, lu, be, nl, fr); **não há `es_co`**. `wellhub.com/es-co/` responde **403**, enquanto `/es-ar/` e `/es-mx/` respondem 200 |
| 18 | Concorrência | Conjuntos locais de "gimnasios" (Pereira `s248-74ea`; Risaralda `ccxh-f4jd`) | datos.gov.co | Abertos (licença por conjunto não lida) | Socrata | Endereço / comuna, sem coordenada | 2025 | **verificado** (metadados). Cobertura só local |
| 19 | Momentum | **ELIC — Licenças de construção** (boletim mensal; cobertura ampliada para **1.102 municípios**; séries históricas 302/88/77) | https://www.dane.gov.co/files/operaciones/ELIC/bol-ELIC-jul2026.pdf | Público | PDF + anexos XLSX | Município, por destino (habitação, comércio…) e estrato | jul/2026 | **verificado** o boletim (HTTP 200, 701 KB, modificado em 15/09/2026). Anexos e microdados **não abertos** |
| 20 | Momentum | **CEED — Censo de Edificaciones** (trimestral, 23 áreas) | https://microdatos.dane.gov.co/index.php/catalog/873; boletim https://www.dane.gov.co/files/operaciones/CEED/bol-CEED-IItrim2026.pdf | Público | ZIP microdados + PDF | Obra × **município (`DPTO_MPIO`)** × `ESTRATO` × `DESTINO2`. **Sem manzana nem coordenada** | 2007-II trim/2026 | **verificado** (DDI lido; boletim com HTTP 200 em 14/08/2026) |
| 21 | Momentum | RUES pessoas naturais/jurídicas (`c82u-588k`): matrículas e cancelamentos por data e CIIU | https://www.datos.gov.co/resource/c82u-588k.json | CC BY-SA 4.0 (contém dado pessoal) | Socrata | Câmara de comércio | 2026-10-02 | **verificado** (esquema lido; amostra **apagada** por conter cédula) |
| 22 | Momentum | Emprego formal: PILA/UGPP, FILCO (MinTrabajo), RELAB (DANE) | — | — | — | Município: **não confirmado** | — | **não verificado** (não achei série municipal aberta; a UGPP revisa os dados mensais em até 3,2 p.p., segundo seminário do Banrep) |
| 23 | Momentum / concorrência | **CENU 2024 — Censo Econômico Nacional Urbano** (2.005.613 unidades econômicas preliminares; microdados anonimizados previstos para mai-jun/2026) | https://difusioncensoeconomiconacionalurbano.dane.gov.co/ | — | — | Potencialmente manzana × CIIU | 2024 | **não verificado** (não achei no catálogo de microdados; seria a melhor fonte de academias independentes **se** sair com CIIU 9311 e manzana) |
| 24 | Imobiliário | Portais: Finca Raíz, Metrocuadrado, Ciencuadras | fincaraiz.com.co / metrocuadrado.com / ciencuadras.com | Ver C.2 | HTML | Imóvel | 2026 | **verificado** `robots.txt` dos três e os termos da Ciencuadras. Termos de Finca Raíz e Metrocuadrado **não lidos** (as URLs testadas deram 404 ou vieram sem o texto) |
| 25 | Imobiliário | Preço de aluguel comercial por m² (Colliers, Camacol, La Galería Inmobiliaria) | — | — | — | — | — | **não verificado**: só achei números antigos ou sem data (ex.: Camacol, norte de Bogotá ≈ COP 144.131/m²/mês, ano desconhecido). **Não usar** |
| 26 | Macro | TRM diária (Superfinanciera) | https://www.datos.gov.co/resource/32sa-8pi3.json | Aberto | Socrata | Nacional, diária | 2026-10-16 | **verificado**: TRM de 16/10/2026 = **3.170,46**; média de set/2026 = **3.184,33**; média de mai/2026 = 3.718,86; média de set/2025 = 3.914,83; média de set/2024 = 4.195,18 |
| 27 | Macro | PPA do Banco Mundial (`PA.NUS.PRVT.PP`, consumo das famílias; `PA.NUS.PPP`, PIB) | https://api.worldbank.org/v2/country/COL/indicator/PA.NUS.PRVT.PP | CC BY 4.0 | JSON | Nacional | 2025 | **verificado**: consumo 2025 = **1.665,59 COP/Int$**; PIB 2025 = 1.532,72 |
| 28 | Macro | SUAMECA / Banrep (séries, SDMX web services) | https://suameca.banrep.gov.co/estadisticas-economicas/ | Público | Web / SDMX | — | — | **não verificado** (endpoint SDMX não testado) |

### A.2 Leitura por camada

**Identidade e divisão administrativa**
- **Nível 1:** 32 departamentos + Bogotá D.C. = **33 polígonos**, verificado no instrutivo. O piloto exige partição `uf=XX` com 2 letras (`^[A-Za-z]{2}$`). A Colômbia não tem sigla oficial de 2 letras: a ISO 3166-2:CO usa 3 (CO-ANT, CO-DC…), e o DANE usa código numérico de 2 dígitos. Será preciso **fabricar 33 siglas**, como na AR. Há colisões óbvias com UFs brasileiras: Amazonas = **AM** (já colide), Bolívar/Boyacá ≈ BA/BO, Santander/Sucre/San Andrés ≈ SA/SU/SN, Caquetá/Casanare/Cauca/Cesar/Chocó/Córdoba/Cundinamarca (7 com "C"). O piloto roda um país por processo (DEC-047), então a colisão só morde nas **tabelas TS de rótulo por sigla** (achado da AR).
- **Nível 2:** município, `MPIO_CDPMP` / DIVIPOLA de **5 dígitos** (2 do departamento + 3 do município, ex. `05001` Medellín, `11001` Bogotá). O arquivo de projeções verificado tem 1.123 códigos. O CENU fala em 1.102 municípios + San Andrés/Providencia + 18 áreas não municipalizadas.
- **Hierarquia censitária:** município → classe (1 cabecera, 2 centro poblado, 3 rural disperso) → setor → seção → **manzana** (urbano), ou seção rural (46.032 polígonos). `COD_DANE_A` (22 caracteres) concatena tudo. Há também `COD_RDTM` (24 caracteres, para REDATAM).

**Base censitária e unidade mínima**
- A unidade mínima publicável é a **manzana censal**, com geometria e 80 variáveis.
- **Variáveis relevantes no `.dbf`** (nomes reais lidos):
  - `TP27_PERSO`: pessoas; `PERSONAS_S`: em hogares particulares; `PERSONAS_L`: em LEA.
  - `TVIVIENDA`: viviendas; `TP15_1_OCU`: ocupadas com pessoas presentes; `TP16_HOG`: hogares.
  - `TP19_EE_E1..E6`: viviendas por **estrato 1-6**; `TP19_EE_E9`: sem estrato / não sabe.
  - `TP34_1..9_EDA`: idade em faixas de 10 anos (0-9 … 80+).
  - `TP51*`: escolaridade.
  - `AREA`: m² em MAGNA_Colombia_Bogota; `LATITUD`/`LONGITUD`: centroide; `DENSIDAD`.
  - `CD_LC_CM`/`NMB_LC_CM`: localidad/comuna. `VERSION` = 2018.
- **Anonimização:** manzana com 1-3 viviendas ocupadas é fundida com outra da mesma seção ou sobe de nível. O resultado: 201.477 pessoas da classe 1 subiram ao nível de classe, de um total de 34.107.027 nas cabeceras (0,6 %). Na base de manzanas e seções rurais estão 43.804.646 pessoas, contra **44.164.417 recenseadas**.
- **Omissão censitária:** a população-base de 2018 nas projeções é 48.258.494, contra 44.164.417 recenseados. Isso dá um **fator de cobertura de ×1,093 em 2018** e de **×1,209 até 2026** [estimativa]. O fator varia por município, porque a omissão e a migração venezuelana não são uniformes.
- **Atenção à faixa etária:** as faixas de 10 anos não recortam 18-45. Há duas saídas: (a) usar 20-49, ou (b) interpolar com a projeção municipal por idade simples (#6, não verificada).

**Renda / consumo — o melhor proxy**
- O CNPV 2018 **não pergunta renda**. A renda tem de ser modelada.
- **Receita proposta** (análoga à EPH + raking da AR, mas com um elo observado por manzana):
  1. Na GEIH/Pobreza (#8/#9), estimar `ingpcug` por **domínio × estrato × composição educacional/idade**. O estrato está em `P4030S1A1`; os domínios são as 23 cidades e as áreas metropolitanas.
  2. Aplicar à manzana usando a distribuição observada de viviendas por estrato (`TP19_EE_E1..E6`) e a escolaridade (`TP51*`).
  3. Fazer raking aos totais oficiais por domínio de 2025.
  4. Agregar ao hex.
- **Por que é melhor que a AR:** o estrato é um atributo físico/administrativo **observado por vivienda** (não imputado). É a principal variável de focalização de subsídio do país. Fortemente correlacionado com renda, mas **não é renda** (ver F).
- **Fora dos 23 domínios urbanos** (cidades médias/pequenas), a GEIH só dá "resto" por departamento. O erro da renda modelada cresce justamente nas cidades médias onde a Smart Fit diz que vai crescer (62 municípios hoje).

**População diurna/noturna, densidade, urbanização**
- Noturna: censo + projeção (#1, #5).
- Densidade: calculável (`AREA` por manzana; o campo `DENSIDAD` existe, mas a unidade **não foi confirmada**).
- Urbanização: classe 1/2/3.
- **População diurna: nada nacional.** Bogotá tem a Encuesta de Movilidad (origem-destino), **não verificada**.

**Academias e concorrência** (detalhe em B)
- Pontos geocodificados da maior rede (Smart Fit) por sitemap: **verificado**.
- Universo de independentes: **sem fonte geocodificada**. O RUES dá contagem por câmara sem endereço; o OSM cobre ~15 % do universo HFA (1.167 contra 7.940) [estimativa]; o CENU 2024 é promessa.
- Sem WellHub CO, **a receita argentina (WellHub como espinha dorsal, 68 % da camada web) não se transporta.**

**Momentum urbano**
- Licenças de construção (ELIC, 1.102 municípios) e CEED (23 áreas, obra × estrato × destino): bons substitutos para "obras".
- Empresas: RUES por câmara (não por município: Bogotá e Cundinamarca têm câmaras próprias, mas várias câmaras cobrem um departamento inteiro).
- Emprego formal municipal: **não verificado**.
- Nada disso tem grão de hex; o grão útil é município ou câmara.

**Imobiliário / aluguel comercial**
- Portais existem e têm volume, mas há bloqueio explícito (ver C.2).
- Em Bogotá, o valor de referência do m² de terreno por manzana (Catastro) é proxy de preço de solo, não de aluguel (não verificado).
- **Não achei série pública confiável de aluguel comercial por m² em 2026.**

---

## B. Mercado fitness

| Indicador | Valor | Fonte / data | Status |
|---|---|---|---|
| Penetração (sócios/população) | **6,9 %**; 7.940 instalações; 3,6 M consumidores (ref. 2024) | *2026 HFA Global Report*, via Mercado Fitness (pub. 15-21/09/2026) — https://mercadofitness.com/los-ingresos-industria-fitness-mundial-crecieron-107-2025/ | **verificado** (artigo lido; relatório HFA original **não lido**) |
| Penetração (estimativa local divergente) | **3 %**; **2.800** academias (ref. 2024) | Mercado Fitness, *Radiografía del sector… Colombia 2024* (artigo de 05/12/2024) | **verificado** (artigo lido). Diverge da HFA em ~2,3× nas pessoas e ~2,8× nas instalações: definição de "instalação" diferente. **Escolher uma é decisão, não transcrição** |
| "Mais de 2 milhões vão à academia" | ~3,7 % de 53,4 M [estimativa] | HFA citada pela La República | **não verificado** |
| Tamanho do mercado | ~US$ 400 M/ano | Entrevista com o gerente da Spinning Center, La República, 13/01/2025 | **verificado** (artigo); número de fonte interessada |
| Smart Fit — sócios/população | **1,3 %** (o maior entre os 5 mercados: BR 1,1 %, MX 0,8 %, CL 1,7 %, PE 0,8 %) | Apresentação Institucional Smart Fit, set/2026, p. 34 ("As of Jun 30th, 2026") | **verificado** (PDF lido) |
| Sócios por clube Smart Fit CO | ~2.990 (0,013 × 53,4 M ÷ 232) | — | **[estimativa]**: compatível com a régua BR de 2.500 e longe da AR (1.070). A média de **mercado** HFA (3,6 M ÷ 7.940) dá **~453 por instalação**. A régua `capacidade_concorrente` tem de ser calibrada como na AR, não copiada |
| Ticket Smart Fit (lista em 2026-10-16; "pode variar por sede") | Black **COP 119.900** (12 meses) = **US$ 37,65** = **Int$ 71,99 PPA**. Smart **COP 89.900** (sem fidelidade) = US$ 28,23 = Int$ 53,97. Fit **COP 69.900** (12 meses) = US$ 21,95 = Int$ 41,97. Black sem permanência COP 149.900. 1º mês "$0" | https://www.smartfit.com.co/planes; câmbio = TRM média set/2026 (3.184,33); PPA = consumo 2025 (1.665,59) | **verificado** (página lida). As conversões são [estimativa] com fatores verificados. Não achei taxa de matrícula/manutenção anual |
| Maturidade do low-cost | **Madura e dominada por um player.** A Smart Fit tem **232 clubes em 30/06/2026** (3º mercado da rede, entrada em 2016); fechou 2025 com 224-225 sedes em 62 municípios e planeja +15 a 25 em 2026 nas cidades intermediárias. Tem aliança de franquia com a Action Black (marca colombiana de ~21 sedes antes da aliança) e comprou ~5 sedes da Spinning Center em 2020 | Apresentação Smart Fit set/2026 (**verificado**); Forbes 14/01/2026 (**verificado**); Pulzo/Portafolio (**não verificado**); site da Action Black (**não verificado**) | misto |
| Bodytech (mid/premium) + Athletic (low-cost da Bodytech) | Último total confiável: **~88-90 sedes na Colômbia (2022)**; Athletic 9-10 sedes (2022). +2 Bodytech e +1 Athletic anunciadas em jan/2026 | La República 2022 e 20/01/2026 | Total de 2026 **não verificado** (bodytech.com.co responde 403) |
| Spinning Center | 18 sedes; ~47.000 afiliados (jan/2025) | La República 13/01/2025 | **verificado** (artigo) |
| Stark Smart Gym | 7 sedes em Bogotá (site oficial) | https://www.starksmartgym.com.co/sedes/ (via busca) | **não verificado** (página não aberta; `robots.txt` aberto e com sitemap) |
| Agregadores | WellHub: **sem sitemap CO** e `/es-co/` com 403 → provável ausência. TotalPass: **sem operação confirmada**. Fitpass (origem mexicana): ~400 centros após "um ano" (texto de ~2020-21) | ver A.1 #17; El Tiempo | WellHub **verificado (negativo)**; TotalPass e Fitpass **não verificados** |
| Hábitos, Fitness 24 Seven, outros | Não encontrados | — | **não verificado** |

**Leitura para o motor:** a Colômbia está a ~4 anos da Ultra BR em formato (low-cost com fidelidade de 12 meses e preço de lista na casa de US$ 30-38). O espaço "livre" de low-cost é menor que na AR: a Smart Fit já tem 232 clubes e penetração própria de 1,3 %, a maior entre os cinco mercados. A camada 3 (pressão) vai saturar nas capitais. A tese da Ultra tende a ser **cidade média com cabecera de 100-500 mil**, exatamente onde a Smart Fit declarou que vai crescer.

---

## C. Regulação

### C.1 Proteção de dados
- **Lei Estatutária 1581 de 2012** (Habeas Data), regulamentada pelo Decreto 1377/2013 (compilado no Decreto 1074/2015); autoridade: **SIC**.
- **Sanções:** multas de até 2.000 SMMLV, suspensão por até 6 meses e fechamento da operação de tratamento (caso World/Tools for Humanity, Resolução 45710 de 18/06/2026). Um projeto de reforma (ago/2025) propõe até 10.000 SMMLV ou 5 % da receita. Status: **não verificado** (fonte: imprensa jurídica).
- **Implicação prática:**
  - O RUES aberto (CC BY-SA) traz **cédula e nome de pessoa natural** (proprietário único). O motor deve consumir **só agregados** (contagem por CIIU/câmara/data) e **nunca persistir** razão social nem cédula de pessoa natural. Por isso as amostras do RUES foram **apagadas** nesta pesquisa.
  - Coletar nome/endereço de academia de **pessoa jurídica** é baixo risco. Academia de "propietario único" é dado pessoal.
- **Transferência internacional para o Brasil** (se o pipeline rodar na VPS BR): depende de o Brasil constar da lista de países com nível adequado da SIC. **Não verificado.**

### C.2 Scraping e termos de uso das fontes
| Fonte | O que vale | Status |
|---|---|---|
| Smart Fit CO | `robots.txt` permite `/sedes`; bloqueia `/api`, `/search`, `/people`, `/client_space` etc. | **verificado** (robots); termos **não lidos** |
| Stark Smart Gym | `robots.txt` aberto (Yoast), com sitemap | **verificado** |
| WellHub | `robots.txt` aberto, mas **sem conteúdo CO** | **verificado** |
| **Finca Raíz** | `robots.txt` com **1.771 `Disallow:/` por user-agent**, incluindo explicitamente **`Scrapy`, `RedesScrapy` e `PyCurl`**; para `*`, bloqueia `/arriendo/*-y-*`, `/venta/*-y-*` etc. Sinal claro de oposição a coleta automatizada | **verificado** (robots); termos **não lidos** (404 nas URLs testadas) |
| Metrocuadrado | `robots.txt` bloqueia `/preciosm2/`, `/valorizacion/`, `/metrocuadrado-results/`, `/_Incapsula_Resource?` (usa **Imperva/Incapsula**, anti-bot) | **verificado** (robots); termos **não lidos** |
| **Ciencuadras** | Termos Gerais, seção 7, numerais 10-12, 14 e 18: **proíbem web scraping, robôs, criar base de dados** e coletar dados pessoais dos usuários | **verificado** (termos lidos) |
| DANE / datos.gov.co | Dados públicos; datos.gov.co declara CC BY-SA 4.0 nos conjuntos do RUES | **verificado** (metadados) |

**Conclusão:** a superfície `imobiliaria` na CO **exige parceria ou licença com o portal**, ou coleta manual. O padrão BR (coletor do Vini) colide com termos explícitos (Ciencuadras) e com bloqueio técnico (Finca Raíz, Metrocuadrado).

### C.3 Franquias
- **Não existe lei específica de franquia.** O contrato é atípico/inominado e segue as regras gerais do Código de Comércio, os usos mercantis e o pactuado (conceito SIC de 2010).
- Normas incidentes:
  - Lei 256/1996 (concorrência desleal).
  - Decreto 2153/1992 e Lei 1340/2009 (livre concorrência).
  - Circular Única da SIC (Circular 10/2001).
  - **Decisão 291 da CAN** (cláusulas restritivas em contratos de transferência de tecnologia/marca).
- Exigência prática: **o franqueador tem de ser o titular registrado da marca na Colômbia** (posição da SIC, 2017). Antes de franquear, registrar "Ultra" na SIC.
- Status: **verificado** por fontes acadêmicas e de imprensa jurídica. Não há confirmação de projeto de lei aprovado desde então.

### C.4 Investimento estrangeiro
- Regime geral: **Decreto 1068/2015**, modificado pelo **Decreto 119/2017**. A inversão estrangeira é **registrada no Banco de la República** por declaração (o Decreto 119 eliminou prazos e sanções do registro inicial). Uma alteração em 2026 (**Decreto 1044 de 05/08/2026**) aparece no site do Banrep; o conteúdo **não foi verificado**.
- Restrições setoriais (defesa e resíduos tóxicos): **não verificado**. Academia não está em setor restrito, pelo meu conhecimento; confirmar com advogado local.

---

## D. Macro e tributos — efeito no DRE e no payback

| Item | Valor | Fonte | Status |
|---|---|---|---|
| Moeda | Peso colombiano (COP). Separador de milhar "." e decimal "," (igual ao BR; **não** é o problema R10 de MX/PE) | — | conhecimento geral |
| TRM (COP/USD) | 3.170,46 em 16/10/2026; média de set/2026 **3.184,33**; set/2025 3.914,83; set/2024 4.195,18 → **COP valorizou ~23 % contra o USD em 12 meses** | datos.gov.co `32sa-8pi3` | **verificado** |
| PPA (consumo, 2025) | 1.665,59 COP por Int$ (a TRM é ~1,9× a PPA) | Banco Mundial | **verificado** |
| Inflação (IPC 12 meses) | **6,29 %** em set/2026 (5,18 % em set/2025); fora da meta de 3 % ± 1 há mais de 5 anos | Imprensa citando o DANE | **não verificado** no boletim original |
| Taxa de política monetária | **12,25 %** (alta de 25 p.b. em 30/09/2026) | Busca (site do Banrep) | **não verificado** diretamente (a URL testada deu 404) |
| Salário mínimo 2026 | **COP 1.750.905** + auxílio-transporte COP 249.095 (Decreto 1469/2025; reforço provisório Decreto 0159/2026; suspensão revogada pelo Consejo de Estado em 17/07/2026). Alta de ~23 % | Cafam, Vanguardia, Blu Radio | **parcial** (valores consistentes entre fontes; decreto não lido) |
| Imposto de renda PJ | **35 %** (art. 240 do ET, Lei 2277/2022) + **Tributação Mínima de 15 %** sobre lucro contábil depurado | Actualícese, PwC | **não verificado** no ET |
| IVA | Geral **19 %**. **Sobre a mensalidade de academia: não verificado.** Não achei conceito da DIAN sobre "acondicionamiento físico" | — | **não verificado: risco #1 do DRE** |
| ICA (municipal, sobre receita bruta) | Bogotá hoje: 4,14-13,8 por mil (Acordo 065/2002). Reforma aprovada no Concejo (Proj. 709/724 de 2026) passa a 9 tarifas de 4 a 20 por mil a partir de 01/01/2027. **Tarifa do CIIU 9311 não verificada** | Crowe, Pérez-Llorca (out/2026) | **não verificado** |
| Remessas ao franqueador no exterior (royalty) | Retenção na fonte **20 %** (salvo convênio de dupla tributação; o Brasil tem acordo com a Colômbia? **não verificado**) + IVA 19 % sobre serviço importado (autorretenção) | siemprealdia.co (2026), investincolombia | **não verificado** no ET |
| Dividendos a não residente | **20 %** | siemprealdia.co (tabela de 2026) | **não verificado** no ET |
| GMF ("4 por mil" sobre movimentação financeira) | 0,4 % | conhecimento geral | **não verificado** |
| Encargos trabalhistas sobre a folha (prestaciones, parafiscales, seguridade social) | — | — | **não verificado** (não pesquisado; tipicamente relevante) |

**Efeito no DRE/payback (qualitativo, sem número inventado):**
1. **Receita líquida:** se o IVA de 19 % incidir sobre a mensalidade cobrada do aluno com preço "cheio", a receita líquida cai ~16 % (1 − 1/1,19) contra um DRE BR em que o tributo indireto sobre serviço é bem menor. Somam-se ICA (0,4-2 %) e GMF. **É o item que mais move o payback e é o que não consegui verificar.**
2. **Custo de pessoal:** o mínimo +23 % em 2026, com inflação de 6 %, pressiona a folha. Os planos com fidelidade de 12 meses travam o reajuste de preço por um ano.
3. **Câmbio:** o motor da AR lê renda em USD. Na CO, com o COP valorizando ~23 % em 12 meses, **uma âncora de renda em USD moveria o score sem nenhuma mudança real de renda**. Recomendo `indicadores_renda` em **COP constante** (mês-base declarado, deflator IPC) ou em PPA, e câmbio só na viabilidade. Pela PTAX usada na AR em mai/2026 (BRL/USD 4,9837) e pela TRM média de mai/2026 (3.718,86), dá ≈ **746 COP por BRL** [estimativa]. É preciso declarar o `cambio_viabilidade` COP/BRL ou COP/USD no perfil.
4. **Custo de capital:** juro de política de 12,25 % encarece o capex financiado e aumenta o custo de oportunidade. Payback e TIR exigida devem ser recalibrados, não copiados do BR.

---

## E. Veredito de dados por camada e mapeamento para o contrato

| Camada | Veredito | Impacto na confiabilidade do ranking | Mapeamento para o contrato |
|---|---|---|---|
| **Identidade** | **Completa** | Baixo risco | `hex_id`/`lat`/`lng`: derivados do H3 sobre manzanas. `cidade`/`nome_municipio` ← nome do município (do MGN municipal ou das projeções). **`cod_municipio` = DIVIPOLA `MPIO_CDPMP`, string de 5 dígitos com zero à esquerda (`"05001"`)**. Partição `uf=XX`: 33 siglas fabricadas (ex.: Bogotá D.C. = `DC`; Amazonas **não pode** ser `AM` sem conferir as tabelas TS de rótulo) |
| **1 Potencial** | **Parcial com proxy** (população completa; renda modelada) | População: alta, mas com base 2018 escalada ×1,209 e erro espacial em periferias novas e bairros de migrantes. Renda: modelada por estrato. Melhor que a AR **dentro** das 23 cidades e pior fora delas | `pop_total_setor_2022` ← `TP27_PERSO` da manzana (ou `PERSONAS_S`), **escalado** pela projeção municipal 2026 (cabecera ou resto, conforme `CLAS_CCDGO`) e agregado ao hex por área ou centroide. `populacao_corte_hex` ← hex + 6 vizinhos (molde AR). **Não emitir `pop_total`** (falso amigo). `renda_per_capita` ← `ingpcug` modelado, **em COP constante de um mês-base** (recomendado) ou USD se a plataforma exigir. Manter `renda_confianca` (dentro × fora dos domínios GEIH). `score_setor_2022_calibrado` ← **recomputado** com âncoras CO (decisão: âncoras em COP/PPA, não em USD corrente). O nome da coluna diz "2022", mas o dado é de 2018: **carimbar o ano no perfil**, senão a UI mente |
| **2 Residual** | **Parcial com proxy** | Médio-alto. A taxa de penetração tem duas fontes divergentes (3 % contra 6,9 %); a capacidade por academia vai de 453 (média HFA) a ~3.000 (Smart Fit); a oferta é incompleta. Erro de escala, não de ordem, **se** a cobertura de concorrentes for homogênea, e ela não é (capitais × cidades médias) | `sam_fitness_potencial` ← pop do hex × `taxa_fitness` declarada (escolher HFA 6,9 % ou local 3 %, por decisão). `oferta_consumida_mercado_estimada` ← concorrentes × capacidade **calibrada** (molde AR: real × fator de cobertura). `oferta_efetiva_disponivel` em **alunos**. Ultra = 0 (greenfield) |
| **3 Pressão** | **Parcial com proxy** | Alto. Sem WellHub, a camada fica "Smart Fit + OSM": as redes aparecem e os independentes somem. Pela regra do contrato, **"não mapeado" vira "livre"** em silêncio, e isso favorece justamente bairros de independentes | `concorrentes_mapeados` ← Smart Fit (sitemap + `geo.position`), Bodytech/Athletic/Stark/Spinning Center (sites; Bodytech dá 403), OSM e, se sair, CENU 2024 (CIIU 9311 por manzana). `status_registro` derivado como na AR. `capacidade_default_concorrente_alunos` calibrada |
| **4 Momentum** | **Parcial com proxy** (grão municipal) | Baixo-médio: a camada não entra no score na AR e pode ficar só como leitura | ELIC (licenças por destino comércio/habitação, mensal, 1.102 municípios), CEED (área em obra por estrato, 23 áreas), RUES (aberturas e cancelamentos por câmara), projeção de população 2018→2026 por município (taxa de crescimento). **Chave:** o join do crescimento usa `cod_municipio[:6]` contra `cod6.zfill(6)`, e **5 dígitos nunca casam** (`"05001"` contra `"005001"`). Corrigir a chave na plataforma ou usar `cres_chave_nome = "<UF>\|<NOME NORMALIZADO>"` |
| **5 Fila** | **Parcial** (herda 1 e 2) | Depende das âncoras em alunos (2.000-20.000). Com capacidade de concorrente mal calibrada, `nota_dem` achata (o mesmo defeito da AR) | `indice_praca` sem mudança de fórmula. **Exige** `DEMANDA_MIN/MAX_ALUNOS` na escala CO (lacuna do perfil) |
| **Relatório Pontual** | **Parcial com proxy** (geometria e população completas; renda modelada) | Melhor que a AR na geometria: a manzana (~5-10 mil m²) é muito mais fina que o radio censal | `setores_censitarios_2022_geo`: `cod_setor` ← `COD_DANE_A` (22 caracteres); `geometry_wkb` ← polígono da manzana (**WGS84/EPSG:4326, não EPSG:4674**: declarar ou reprojetar); `area_setor_m2` ← `AREA`; `pop_total_setor_2022` ← `TP27_PERSO` escalado; `domicilios_particulares_ocupados_setor_2022` ← `TP16_HOG` (hogares) ou `TP15_1_OCU` (viviendas ocupadas): **decidir o denominador** (lição 7 da AR); `avg_moradores_domicilio_setor_2022` ← `PERSONAS_S / TP16_HOG`; `renda_per_capita_setor_2022_calibrada` ← renda modelada por estrato; `nome_bairro`/`nome_distrito` ← `NMB_LC_CM` (localidad/comuna; **bairro oficial não existe no MGN**; vazio fora das capitais). `uplift_composicao` = 1,0 (molde AR). `RENDA_MIN` R$ 4.500 e zona morta em R$ **reprovam errado** (lacuna já conhecida) |
| **Viabilidade** | **Parcial** | Alto: IVA da mensalidade, ICA por município, encargos trabalhistas e aluguel comercial **não verificados** | `cambio_base`/`cambio_viabilidade` declarados (TRM verificada; PTAX de fora). Ticket de referência: Smart Fit Black COP 119.900. Premissas tributárias são **BLK-INTL-11** (não copiar BR) |
| **Oportunidades imobiliárias** | **Inviável sem parceria** | — | Portais com bloqueio técnico ou termos contrários (C.2) |
| **M&A / agregadores** | **Inviável hoje** | — | Sem WellHub CO; TotalPass não confirmado |

---

## F. Premissas frágeis, onde a analogia BR/AR quebra, e lista do que ficou não verificado

### F.1 Onde a analogia quebra
1. **Idade do censo.** BR (2022) e AR (2022) usam base de ~4 anos; a CO usa **2018 (8 anos)**, sem censo antes de 2030 (conteo de 2025 cancelado por falta de recursos). Bairros novos de 2018-2026 (VIS periférico, expansão de Soacha, Mosquera, Funza, Rionegro…) **não existem na base de manzanas**. O fator ×1,209 aplicado proporcionalmente **sub-representa a periferia que cresceu** e superestima centros que perderam gente. Sugestão: redistribuir o delta municipal com ELIC/CEED (área licenciada para habitação) ou com uma grade externa (GHSL/WorldPop, **não pesquisada**).
2. **Migração venezuelana** (~2,8 M segundo o conhecimento geral; **não verificado**): concentrada em Bogotá, Cúcuta, Barranquilla e Medellín, e parcialmente capturada pelas projeções pós-COVID de jul/2025. Afeta a população por hex e a renda (pessoas de renda baixa em estratos médios).
3. **Estrato ≠ renda.** O estrato classifica o **imóvel/entorno** para tarifa de serviço público e é atualizado pelo município em ciclos irregulares. Há famílias de renda alta em estrato 3 e o inverso; em cidades pequenas, quase tudo é estrato 1-2, com pouca variância. O estrato do censo é **autodeclarado pela conta de luz** (`TP19_EE_*` só conta viviendas com energia). É o melhor proxy disponível, mas a régua 0-100 vai **comprimir** fora das capitais (lição 3 da AR).
4. **Escala de renda e câmbio.** A AR ancorou em USD; na CO o COP oscilou ~23 % em 12 meses. Uma âncora em USD corrente faria o score "andar" com o câmbio. **Decisão necessária:** âncoras em COP constante ou PPA.
5. **Capacidade e penetração.** Três réguas incompatíveis: HFA (6,9 %; ~453 sócios por instalação), Radiografía local (3 %; 2.800 academias) e Smart Fit (1,3 % só dela; ~3.000 por clube). Nenhuma é "a certa"; cada uma muda o residual em ordem de grandeza.
6. **Concorrência sem agregador.** Na AR o WellHub deu 68 % da camada web; na CO **não há WellHub**. Os independentes ficam quase invisíveis, e a regra do contrato transforma "não mapeado" em "livre". O CENU 2024 pode resolver isso **se** publicar microdados com CIIU e manzana; não confirmei.
7. **Chave municipal.** O DIVIPOLA de 5 dígitos quebra o join `cod6` do crescimento, exatamente como na AR. O nível 1 tem 33 unidades sem sigla de 2 letras, com colisão `AM`.
8. **Malha:** o MGN vem em **WGS84**, e o contrato assume EPSG:4674 (SIRGAS 2000). A diferença é pequena, mas tem de ser declarada ou reprojetada. Áreas oficiais em MAGNA_Colombia_Bogota.
9. **Tributo:** a AR rodou com tributo BR (provisório). Na CO o IVA potencial de 19 % sobre a mensalidade, o ICA municipal e a retenção de 20 % sobre royalty mudam o payback em dois dígitos. **Não é aceitável como provisório silencioso.**
10. **Imobiliário:** o coletor BR não se transporta; a Ciencuadras proíbe scraping por escrito e a Finca Raíz bloqueia Scrapy/PyCurl por nome.
11. **Rede de hosts:** três hosts do governo colombiano recusaram conexão deste ambiente; o pipeline pode ter de rodar de outra rede.

### F.2 Lista explícita do que ficou NÃO VERIFICADO
- Formato e conteúdo dos 33 ZIPs de microdados do CNPV 2018 por departamento e suas condições de acesso.
- Termos formais de licença do MGN/microdados DANE (verifiquei só a nota de anonimização).
- Unidade do campo `DENSIDAD` do MGN.
- Projeção por área, sexo e idade simples e projeções de Bogotá por localidad/UPZ.
- Linhas de pobreza 2025 e incidência (vistas em busca, PDF não aberto); média de `ingpcug` por domínio.
- Nota do DANE sobre estimação em áreas pequenas municipal (dez/2025): existência citada em busca, não achada.
- IPM por manzana (geovisor inacessível).
- Estratificação por manzana dos portais de Bogotá e Cali.
- Valor de referência do m² por manzana (Catastro Bogotá).
- Emprego formal municipal (PILA/FILCO/RELAB).
- CENU 2024: publicação de microdados, CIIU e grão.
- Anexos e microdados do ELIC.
- População diurna (Encuesta de Movilidad Bogotá).
- Contagem de Smart Fit no OSM (timeout); total atual de sedes da Bodytech/Athletic (site 403); página de sedes da Stark; Hábitos, Fitness 24 Seven.
- TotalPass e Fitpass na Colômbia.
- Relatório HFA 2026 original (lido via Mercado Fitness).
- Termos de uso de Smart Fit, Finca Raíz e Metrocuadrado.
- Aluguel comercial por m² em 2026 (nenhuma fonte com data).
- IPC de set/2026 no boletim DANE original; taxa de 12,25 % na página do Banrep; texto do decreto do salário mínimo.
- IVA sobre mensalidade de academia; tarifa de ICA do CIIU 9311 por município; IR 35 % e TMT 15 % no texto do ET; retenção de 20 % sobre royalty e dividendos; GMF; encargos trabalhistas; acordo de dupla tributação Brasil-Colômbia.
- Lista de países adequados da SIC para transferência internacional de dados (Brasil).
- Restrições setoriais a investimento estrangeiro e o conteúdo do Decreto 1044/2026.
- Migração venezuelana (~2,8 M).

### F.3 Fontes consultadas (lidas nesta tarefa)
- DANE microdatos CNPV 2018, catálogo 643: https://microdatos.dane.gov.co/index.php/catalog/643/related-materials
- DANE, CNPV "Dónde estamos": https://www.dane.gov.co/index.php/estadisticas-por-tema/demografia-y-poblacion/censo-nacional-de-poblacion-y-vivenda-2018/donde-estamos
- DANE, projeções de população: https://www.dane.gov.co/index.php/estadisticas-por-tema/demografia-y-poblacion/proyecciones-de-poblacion
- DANE, Pobreza Monetária 2024 (catálogo 874) e GEIH 2025 (catálogo 853): exportação DDI
- DANE, CEED (catálogo 873); boletins ELIC jul/2026 e CEED II trim/2026
- El País (08/07/2023), censo 2030 / conteo 2025: https://www.elpais.com.co/economia/habra-nuevo-censo-de-poblacion-el-dane-confirmo-las-fechas-para-esta-labor-0829.html
- El Tiempo e Semana sobre o cancelamento do conteo de 2025 (via busca): https://www.eltiempo.com/economia/sectores/el-dane-cancelo-la-realizacion-del-conteo-intercensal-del-2025-por-falta-de-recursos-3462408
- datos.gov.co (Socrata): RUES `nb3d-v3n7`, `c82u-588k`; TRM `32sa-8pi3`; catálogo de "gimnasio"
- Smart Fit: https://www.smartfit.com.co/planes, sitemap e página de sede; Apresentação Institucional set/2026 (https://investidor10.com.br/acoes/link_comunicado/SMFT3/49409/)
- Forbes Colômbia (14/01/2026): https://forbes.co/negocios/smart-fit-abrio-su-sede-numero-2-000-en-el-mundo-y-colombia-es-su-tercer-pais-mas-importante
- La República: Spinning Center (13/01/2025), Bodytech (20/01/2026)
- Mercado Fitness (05/12/2024 e set/2026)
- WellHub: robots.txt e sitemap_partners.xml
- OSM via Overpass (maps.mail.ru); Geofabrik
- Banco Mundial API (PPA)
- robots.txt de Finca Raíz, Metrocuadrado, Ciencuadras, Smart Fit e Stark; termos da Ciencuadras
- Imprensa jurídica e tributária (Asuntos Legales, siemprealdia, Actualícese, Crowe, Pérez-Llorca) — **só via busca, marcadas como não verificadas** na tabela D
