# Dossiê de dados — Paraguai (PY) para o Motor de Expansão

> **Leia junto com `01-consolidacao-auditoria.md`.** Este dossiê é a versão de campo, de 2026-10-16. A auditoria cruzada corrigiu alguns números e vereditos depois dele, e a versão corrigida vale sobre esta.

- Data de acesso de todas as fontes: **2026-10-16**. Pesquisa somente leitura; nada no repositório foi alterado.
- Amostras baixadas (dado não confiável, lido com `python -I`): `C:\Users\Pichau\AppData\Local\Temp\claude\C--Users-Pichau-Documents-motor-de-expansao\d45e86bf-d899-46b1-bd74-dd25828a14cf\scratchpad\amostras\PY\`. Scripts de leitura (fora da pasta de amostras): `...\scratchpad\scripts_py\`.
- Convenção: **[verificado]** = abri a página ou baixei a amostra e li o dado; **[secundário]** = número lido em imprensa/escritório de advocacia/terceiro, não na fonte primária; **[não verificado]** = não confirmado; **[estimativa]** = cálculo meu.

## Veredito em 5 linhas

1. **A malha é ótima e a população por área pequena é o gargalo.** O INE publica a cartografia censal 2022 em GeoJSON/SHP/KML com **manzanas, barrios/localidades e distritos**, em **EPSG:4674** (o mesmo SIRGAS do IBGE) [verificado]. Mas a contagem pública do censo para no **distrito (263)**. A única exceção são os **68 barrios de Asunción** [verificado]. Não há setor censitário com população.
2. **Renda não é medida e terá de ser modelada, como na AR.** A EPHC 2024 traz `ipcm` (renda per capita mensal, ₲) com dpto + urbano/rural, mas sem geografia fina [verificado]. Os censos de covariáveis só são públicos por distrito (REDATAM). A variação **intraurbana** precisa de proxy: Meta RWI (2,4 km) [verificado], prédios e luz noturna.
3. **O mercado é pequeno e concentrado.** São 6,11 M habitantes (Censo 2022) [verificado]. Com WorldPop 2022 agregado em H3 res 7, saem **742 hexágonos com ≥ 1.000 hab** e **1.094 com captação (hex + 6 vizinhos) ≥ 5.000** [estimativa], contra 15.186 exportados na AR. Gran Asunción e Ciudad del Este concentram ~70% desse universo.
4. **A concorrência low-cost está madura num único player.** A Smart Fit tem **19 unidades** (contador do site oficial) [verificado], com Smart de ₲169-229 mil/mês (US$ 29-40). **WellHub não opera no PY**: não há locale `es_py` nos sitemaps [verificado]. TotalPass não foi encontrado. Isso tira a "espinha dorsal" que a AR usou para mapear independentes.
5. **O veredito por camada:** a 1 sai *parcial com proxy*, a 2 e a 3 *parciais*, a 4 *parcial fraca* (só demografia), a 5 é *derivada*, o Pontual sai *parcial* (barrio/pseudossetor) e a viabilidade fica *completa em parâmetros, parcial em premissas*. Recomendação de escopo: **Gran Asunción (Asunción + Central) + área metropolitana de CDE + Encarnación**. O país inteiro não compensa o custo de pipeline.

---

## A. Dados por camada do funil

### A.1 Tabela de fontes (regra de evidência)

| # | Fonte | URL | Licença / termos | Formato | Granularidade espacial | Ano ref. | Status | Observação |
|---|---|---|---|---|---|---|---|---|
| 1 | INE — Cartografía Censal 2022 | https://www.ine.gov.py/microdatos/cartografia-digital-2022.php (arquivos em `https://www.ine.gov.py/microdatos/register/CARTOGRAFIA%20CENSAL%202022/CARTOGRAFIA%20CENSAL_{GeoJSON,SHP,KML}/<NN DEPTO>.rar`) | Licencia de Uso de la Información Pública (Decreto 4064 / Ley 5282/2014): uso livre, transformação e redistribuição; **atribuição obrigatória**; proibido simular uso oficial. Limites "meramente referenciais" | RAR com GeoJSON/SHP/KML por departamento + total país (SHP total = 81,9 MB) | Departamento, distrito, **barrio/localidad**, **manzana**, cidades, vias | 2022 | **verificado** (baixei Asunción GeoJSON, 2,4 MB) | CRS `EPSG:4674`. Em Asunción: 1 distrito, 68 barrios, **6.095 manzanas**. Chaves: `DPTO`(2) `DISTRITO`(2) `AREA`(1) `BAR_LOC`(3) `MANZANA`(5), `CLAVE` concatenada. **As manzanas não têm atributo de população**. Texto em latin-1 dentro do GeoJSON (acentos quebram em UTF-8) |
| 2 | INE — Códigos geográficos 2022 | https://www.ine.gov.py/microdatos/codigo-geografico-2022.php | Mesma licença | XLSX (3 tabelas) | Departamento (18), **distrito (263)**, barrio/localidad (**7.994**) | 2022 | **verificado** (baixados) | Código do distrito = 4 caracteres `DDdd` (ex.: Asunción `0000`, Luque `1109`, CDE `1001`, Encarnación `0701`) |
| 3 | INE — Censo 2022, Resultados finales: estructura de la población | https://www.ine.gov.py/censo2022/documentos/Resultados%20finales_Estructura%20de%20la%20poblacion%20por%20edad%20y%20sexo_2022.xlsx | Mesma licença | XLSX, 40 abas | País, departamento, **distrito**, urbano/rural × faixa etária por distrito; **barrio só para Asunción** (aba C1.1) | 2022 (nov) | **verificado** (baixado) | Total **6.109.903**. Asunción 462.241, Central 1.883.927, Alto Paraná 763.702, Itapúa 449.642 |
| 4 | INE — Censo 2022, Caracterización de viviendas y hogares | https://www.ine.gov.py/censo2022/documentos/Resultados%20finales_Caracterizacion%20de%20viviendas%20y%20hogar_2022.xlsx | Mesma licença | XLSX | Departamento/distrito (**não verificado** o nível exato) | 2022 | não verificado (link listado na página do censo) | Insumo de domicílios e moradores/domicílio |
| 5 | INE — REDATAM CPV2022 | https://prod.redatam.org/binpry/RpWebEngine.exe/Portal?BASE=CPV2022 | Consulta web; sem download de microdado | Tabelas on-line | **Só `DEPTO` e `DISTRITO`** (dicionário geográfico `DICGEO`, distrito 0-1705) | 2022 | **verificado** (dicionário lido) | Variáveis de vivenda/hogar/pessoa (NBI, educação, bens, TIC) **por distrito**; sem barrio/manzana público |
| 6 | INE — Estratificación socioeconómica del Marco Muestral 2022 | https://www.ine.gov.py/Publicaciones/Biblioteca/documento/297/ (tríptico + documento) | Mesma licença (documento) | PDF | **Segmento de 100-120 vivendas** (UPM), 36 domínios (dpto × urbano/rural) | 2022 | **verificado** (tríptico lido) | O INE **tem** o NSE por segmento (2-4 estratos, k-médias + ACP). Os estratos **não são comparáveis entre domínios**. A camada de segmentos **não é publicada** (não encontrei). É o melhor alvo de pedido formal ao INE |
| 7 | INE — EPHC anual (microdados) | https://www.ine.gov.py/microdato/encuesta-permanente-de-hogares-continua-ephc-2022-2023-2024-2025-anual-factor-revision-2025 (ex.: `.../documento/microdato/EPHC-ANUAL/2024/INGREFAM_EPHC_ANUAL_2024.csv`) | Mesma licença | CSV `;` decimal `,` / SAV | `dpto` (0-15; **sem Boquerón e Alto Paraguay**), `area` (1 urbano / 6 rural); `upm` sem georreferência | 2022-2025 (fator Rev. 2025) | **verificado** (INGREFAM 2024, 3,8 MB, 17.242 domicílios) | `ipcm` = renda per capita mensal ₲. Ponderado por pessoa: nacional p10/p50/p90 = **541 mil / 1,43 M / 3,83 M ₲**; urbano 0,73 M / 1,74 M / 4,40 M; Asunción p50 **2,37 M** p90 6,74 M; Central p50 1,75 M; Alto Paraná p50 1,54 M; Itapúa p50 1,12 M. O ano anual 2025 está listado e não foi baixado (27 MB o REG02) |
| 8 | INE — Proyecciones distritales Rev. 2025 | https://www.ine.gov.py/Publicaciones/Biblioteca/documento/284/Estimaciones%20y%20proyecciones%20Distrital.%20Revisi%C3%B3n%202025.xlsx | Mesma licença | XLSX | **Distrito (263)**, anual 2000-2035 | 2025 (rev.) | **verificado** (baixado, 84 KB) | Total 2022 = 6.284.020 (≈ +2,9% sobre o censo: correção de omissão). Projeção 2022→2030: Asunción **−5,1%**, Limpio +15,6%, Capiatá +12,1%, Minga Guazú +12,5%, Ñemby +10,7%, Pdte. Franco +10,7%, CDE +9,5%, Luque +8,4%, San Lorenzo +3,1%, Fernando de la Mora +1,1% |
| 9 | WorldPop R2025A, 2022, constrained 100 m | https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2022/PRY/v1/100m/constrained/pry_pop_2022_CN_100m_R2025A_v1.tif | CC BY 4.0 (padrão WorldPop; **não verificado** na página do arquivo) | GeoTIFF 19 MB, EPSG:4326 | Grade de 100 m | 2022 | **verificado** (baixado e agregado em H3) | Soma **6,72 M** (≈ 10% acima do censo, porque é ancorado em projeção da ONU) → **precisa de raking para os totais distritais do censo** |
| 10 | Meta/Facebook Relative Wealth Index | https://data.humdata.org/dataset/relative-wealth-index (recurso `pry_relative_wealth_index.csv`) | HDX "Other" (termos Data for Good; **não verificado** o texto) | CSV (lat, lng, rwi, error) | Tiles de ~2,4 km (quadkey z14) | 2021 (abr) | **verificado** (403 KB, 10.987 tiles) | Escala relativa, sem moeda. Gran Asunción: 229 tiles, rwi p05/p50/p95 = −0,02 / 0,82 / 1,46. Erro médio 0,45. Serve para ordenar dentro do distrito, não para dar nível |
| 11 | Kontur Population (H3 400 m) | https://data.humdata.org/dataset/kontur-population-dataset | CC BY | GPKG global (2,4 GB) | H3 res 8 | 2023 | não verificado (não baixado; arquivo global grande) | Alternativa ao WorldPop já em H3 |
| 12 | World Bank — PPP consumo privado e urbanização | https://api.worldbank.org/v2/country/PRY/indicator/PA.NUS.PRVT.PP ; `SP.URB.TOTL.IN.ZS` | CC BY 4.0 | JSON API | País | 2025 | **verificado** | PPP PY **2.874,56 ₲/intl$** (2025); BR 2,5815 R$/intl$ → PPP implícita **1.113,5 ₲/R$**. Urbanização 70,4% (2025) |
| 13 | BCP — cotização de referência | https://www.bcp.gov.py/webapps/web/cotizacion/monedas | Página pública; sem API formal (não encontrei) | HTML | País | 16/10/2026 | **verificado** | **USD = ₲5.770,91**; **BRL = ₲1.136,45** (BRL/USD 5,0780) |
| 14 | Smart Fit Paraguai — site oficial | https://www.smartfit.com.py/gimnasios | Termos não lidos | HTML com JSON embutido (Next) | Ponto (lat/lng) por unidade | 16/10/2026 | **verificado** | `locationsCount: 19`. A página carrega 8 unidades com preço e coordenada (7 Gran Asunción + Luque); as demais vêm por JS |
| 15 | WellHub — sitemaps de parceiros | https://wellhub.com/sitemap_partners.xml | robots `Allow: /` | XML | Ponto | 16/10/2026 | **verificado** | Locales existentes: pt_br, en_us, es_mx, es_cl, es_ar, es_es… **sem `es_py`** (nem es_co, es_pe). O sitemap es_ar não contém Asunción/CDE |
| 16 | OSM (Geofabrik PBF / Overpass) | https://download.geofabrik.de/south-america/paraguay-latest.osm.pbf | ODbL | PBF 154,5 MB (15/10/2026) | Ponto/polígono | 2026 | **não verificado** (Overpass deu timeout/500 em 3 espelhos; o PBF é grande demais para amostra) | Contagem de `leisure=fitness_centre` no PY desconhecida |
| 17 | Imprensa setorial — concorrentes | GestiónFit 08/12/2025: https://www.gestionfit.com/industria/smart-fit-abre-el-gimnasio-mas-grande-en-paraguay?elem=372385 ; Mercado Fitness (EXEN, Premier, Ark Gym); InfoNegocios (BIGG 2021, Aerofisic/Fosque 2017) | Leitura | HTML | — | 2017-2025 | **secundário** | Smart Fit com 13 em operação + 4 em obra (dez/2025). BIGG com 4 sedes (2021). EXEN Gym+ com 4 (2024). Premier Fitness Club com 2. ">500 gimnasios" no país (declaração de franqueado Vivafit, sem fonte) |
| 18 | InfoCasas PY — aluguel de locais comerciais | https://www.infocasas.com.py/alquiler/locales-comerciales/asuncion | robots.txt sem `Disallow` geral para `*` (só /fbapps, /superadmin, /wsdl); **termos de uso não lidos** | HTML Next com JSON (preço, moeda, m²) | Ponto/bairro | 16/10/2026 | **verificado** (página lida) | **1.522 anúncios** de locais em Asunción. Amostra (pareamento pela ordem no JSON, indicativo): 400 m² ₲15 M; **1.000 m² ₲22 M (≈ US$ 3,8/m²/mês)**; **1.335 m² ₲35 M (≈ US$ 4,5/m²)**. Moedas Gs. (33) e U$S (3) |
| 19 | Clasipar / ABC Clasificados | https://www.clasipar.paraguay.com ; https://www.abc.com.py | Não lidos | — | — | — | não verificado | O robots do Clasipar voltou vazio. O robots da ABC bloqueia `/buscador`, `/buscar`, `/pf/*` |
| 20 | DNIT — listado RUC | https://www.dnit.gov.py/web/portal-institucional/listado-de-ruc-con-sus-equivalencias | Não verificado | ZIP txt (`ruc0..9.zip`) [secundário] | **Sem endereço** (RUC, nome, DV, estado) [secundário] | mensal | não verificado | **Inútil para momentum territorial**: não geolocaliza |
| 21 | INE — DIRGE (Directorio General de Empresas) | ANDA: https://anda.ine.gov.py/anda/index.php/catalog/179 | Microdado `data_na` (não disponível) | — | Não verificado | 2018-2022 | **verificado** que existe e que o microdado não é público | Possível tabela publicada por departamento/distrito: não verificada |
| 22 | IPS — cotizantes | Sem portal de dados; MTESS cita 753.777 cotizantes (set/2024) e "mais de 842 mil" (manchete de jun/2026) | — | — | **Só nacional** | 2024-2026 | **secundário** | Não há série por distrito/empregador pública encontrada |
| 23 | Licenças de construção (Asunción) | — | — | — | — | — | não verificado | Não encontrei série aberta; só uma nota de imprensa de 2013 (800 mil m²) |
| 24 | INE — Censo 2022 no ANDA | https://anda.ine.gov.py/anda/index.php/api/catalog/search?sk=censo | — | — | — | — | **verificado** | O catálogo traz o CNPV **2002** (acesso remoto) e **não** o CNPV 2022. O microdado do censo 2022 não está público |
| 25 | INE — STEPwise 2022 (fatores de risco/atividade física) | ANDA id 202 (`PRY-INE-DEEA-STEPS-2022-v01`, `public`) | Mesma licença | Microdado | Nacional | 2022 | listado, **não baixado** | Proxy de prevalência de atividade física (não de academia) |

### A.2 Leitura por tema

**Identidade / divisão administrativa e malha.** Nível 1 = 17 departamentos + Asunción (distrito capital) = **18 partições**. Nível 2 = **263 distritos** (inclui Asunción, que é distrito e "departamento" ao mesmo tempo). Nível 3 = 7.994 barrios/localidades. A malha distrital e de barrios sai da cartografia censal 2022 [verificado]. Ela substitui o `ibge/municipios_<UF>.geojson` com conversão direta (`DPTO`+`DISTRITO` → `CD_MUN` de 4 caracteres). O CRS é EPSG:4674, idêntico ao contrato BR (`geometry_wkb` EPSG:4674): **zero reprojeção**. Atenção ao encoding latin-1 dos atributos.

**Base censitária e unidade mínima.** A unidade geométrica mínima é a **manzana**, sem dado. A unidade mínima **com população pública** é o **distrito**, exceto em Asunción, onde é o **barrio** (68). O INE tem o segmento (100-120 vivendas) estratificado por NSE, mas não o publica. O censo teve **cobertura declarada de 94%** pelo próprio INE [secundário: ABC Color, 01/09/2023]. Ficou **6,1% abaixo do censo de 2012**, considerado inválido, e **18% abaixo** da projeção anterior (7,45 M). A imprensa relata cobertura pior em Asunción, Central e CDE, sem número por área [secundário: Última Hora]. A projeção distrital Rev. 2025 já embute um ajuste de **+2,9%** no total de 2022 (6.284.020 contra 6.109.903) [verificado]. **Não encontrei avaliação de omissão por distrito** [não verificado].

**Renda / consumo.** O censo 2022 **não pergunta renda**: as variáveis do REDATAM são NBI, educação, bens e TIC [verificado no índice]. Logo, a renda tem de ser **modelada**, como na AR (EPH → radio). A diferença crítica é que **a AR tinha covariáveis censitárias por radio, e o PY só as tem por distrito**. Receita viável:
1. Modelo `log(ipcm) ~ educação do chefe + bens + NBI + tamanho do domicílio + dpto × área` na EPHC 2024-2025.
2. Aplicação às tabelas distritais do censo (REDATAM) → renda média por distrito × área.
3. Raking ao total EPHC por domínio.
4. Desagregação intradistrital por um índice de prosperidade (RWI 2,4 km + densidade de prédios + VIIRS), com **o nível vindo do distrito e só a ordem vindo do proxy**.

O erro será maior que o ±15% da AR **dentro** de Asunción e de CDE, que é justamente onde o ranking importa [estimativa]. O pedido formal ao INE do NSE por segmento (fonte 6) ou de tabulação especial por barrio/segmento reduziria o erro e é a ação de maior retorno.

**População diurna/noturna, densidade, urbanização.**
- Não há fonte de população diurna.
- CDE tem forte fluxo de compristas brasileiros, sem medida encontrada [não verificado].
- Densidade: WorldPop 100 m (ou Kontur H3) recalibrado aos totais distritais do censo.
- Urbanização: 70,4% (WB 2025) [verificado]; a tabela CA1 do censo traz urbano/rural por distrito [verificado].

**Academias e concorrência.**
- Smart Fit: 19 unidades [verificado].
- Redes menores: BIGG (≥ 4), EXEN Gym+ (≥ 4), Premier (2), Aerofisic/Fosque, boutiques [secundário, datas de 2017 a 2025].
- Sem WellHub [verificado] e sem TotalPass [não encontrado].
- A coleta terá de ser **site de rede + OSM + Google Places**. O Places é pago e tem termos restritivos, o que pede decisão.

Sem agregador, a cobertura de independentes será baixa. O "fator de cobertura" da AR (2,675) não é transferível e terá de ser recalibrado. Uma referência é a declaração de ">500 gimnasios" [secundário].

**Momentum urbano.** Não existe CAGED/RAIS: o IPS só publica o agregado nacional e o RUC não tem endereço. O que existe e é aproveitável:
- (a) projeção distrital 2022-2035 do INE (crescimento demográfico) [verificado];
- (b) crescimento intercensitário 2002→2022 por distrito, pulando 2012, que é inválido;
- (c) VIIRS e mudança de footprint de prédios (a AR reprovou o VIIRS no backtest);
- (d) DIRGE do INE, se houver tabela publicada por distrito [não verificado].

**Imobiliário / aluguel comercial.** O InfoCasas tem 1.522 locais comerciais para alugar em Asunción, com preço em ₲ e m² no JSON da página [verificado]. Na amostra, ~US$ 3,8-4,5/m²/mês para 1.000-1.335 m². Clasipar e ABC Clasificados não foram verificados. Os termos de uso do InfoCasas **não foram lidos**.

---

## B. Mercado fitness

| Item | Valor | Fonte / status |
|---|---|---|
| Penetração (% da população em academia) | **Desconhecida.** Não há relatório IHRSA/Mercado Fitness com número para o PY. Declarações de mercado: "2% fazem exercício constante" e ">500 academias" | InfoNegocios (franqueado Vivafit) — **secundário, sem método** |
| Ticket low-cost (Smart Fit, out/2026) | Plano Smart **₲169.000-229.000/mês**; Black **₲199.000**; Fit ₲119.000-189.000 (8 sedes amostradas) | smartfit.com.py — **verificado** |
| Em USD (BCP 5.770,91) | Smart US$ 29-40; Black **US$ 34,5** | cálculo |
| Em PPP (2.874,56 ₲/intl$) | Black ≈ **intl$ 69** | cálculo (WB PPP consumo privado 2025) |
| Em BRL (BCP 1.136,45) | Black ≈ **R$ 175**; Smart R$ 149-202 | cálculo. A PPP implícita (1.113,5 ₲/R$) quase coincide com o câmbio de mercado hoje |
| Outros tickets | EXEN Gym+ ₲199.000 (US$ 27 na época); Premier US$ 35; Ark Gym ₲350.000 (US$ 48, independente) | Mercado Fitness — **secundário**, 2023-2024 |
| Maturidade do low-cost | Smart Fit desde dez/2019 (Multiplaza). Saiu de 3 (2020) para 5 (2022), 9 (2024), 13 + 4 em obra (dez/2025) e **19 (out/2026)**. Expansão de Gran Asunción para CDE, Pdte. Franco, Encarnación (não verificado), Coronel Oviedo (anunciada) e PJC (planejada) | **verificado** (19) + secundário (série) |
| Agregadores | **WellHub ausente** (sem locale); **TotalPass não encontrado** | verificado / não verificado |
| Densidade de low-cost hoje | Smart Fit 19 ÷ 4,3 M urbanos ≈ **4,4 unidades por milhão de urbanos** | [estimativa] |

**Leitura:** o low-cost no PY é um **quase monopólio da Smart Fit**, com preço em US$ maior que no BR, em termos nominais e de PPP. A Smart Fit é o comparável direto citado no CLAUDE.md, e é ela que já ocupou os melhores pontos de Gran Asunción, com 8 das unidades amostradas em shoppings e eixos de Asunción/Central.

---

## C. Regulação

| Tema | Situação | Status |
|---|---|---|
| Proteção de dados pessoais | **Lei 7593/2025** (lei geral), promulgada em **27/11/2025**. Alcança setores público e privado e cria a Agencia Nacional de Protección de Datos Personales (no MITIC). **Vigência plena após transição de ~24 meses (≈ nov/2027)**. Regulamentação pendente | Ferrere / IAPP / EY — **secundário** (texto da lei não lido) |
| Dados de crédito | Lei 6534/2020 (dados creditícios) | **não verificado** |
| Raspagem / termos | Sem lei específica de scraping encontrada. INE: licença aberta com atribuição [verificado]. InfoCasas: robots permite `/` para `*` [verificado], termos **não lidos**. Smart Fit: termos não lidos. WellHub não se aplica no PY | parcial |
| Franquias | **Não há lei específica de franquia** (não encontrei). Risco: a **Lei 194/93** (rescisão de representantes/distribuidores de empresas estrangeiras, modelada no Dealers Act de Porto Rico) impõe justa causa e indenização. Não confirmei se a jurisprudência a aplica a franquias | **secundário / não verificado** — exige parecer local |
| Investimento estrangeiro | **Lei 117/91**: igualdade de tratamento nacional × estrangeiro; livre câmbio e livre remessa de dividendos, juros e royalties | UNCTAD / ICEX — **secundário** |

---

## D. Macro e tributos (efeito no DRE)

| Item | Valor | Fonte / status |
|---|---|---|
| Moeda | Guaraní (₲, PYG), **sem casas decimais** na prática (preços inteiros; ex.: 199.000) | verificado no site da Smart Fit |
| Câmbio | **₲5.770,91/US$** e **₲1.136,45/R$** (BCP, 16/10/2026) | **verificado** |
| Tendência cambial | ~₲7.000/US$ há um ano para ~5.850 em 01/10/2026: **valorização de ~17% do guaraní em 12 meses**. Mercado projetava ₲6.300 no fim de 2026 (pesquisa BCP de julho) | Rio Times / InfoNegocios — **secundário** |
| Inflação | IPC **1,7% a/a (set/2026)**, núcleo 1,2%; meta BCP 3,5%; juro de política 5,50% | Rio Times (02/10/2026), Trading Economics — **secundário** |
| IVA | **10%** geral; aluguel não residencial 10% (residencial 5%) | Ferrere (Lei 6380/2019) — **secundário** |
| IRE (renda de empresas) | **10%** | Ferrere — **secundário** |
| IDU (dividendos) | **8%** para residentes / **15%** para não residentes (efetivo 17,2% / 23,5% com o IRE) | Ferrere — **secundário** |
| INR (royalties a não residente) | **15% sobre renda líquida presumida** (30%-100% do bruto conforme a atividade). Há limite de dedutibilidade de royalties entre partes vinculadas | Ferrere / YoFacturo — **secundário**; o % presumido para royalty de franquia **não verificado** |
| Salário mínimo | **₲3.044.000/mês** desde 01/07/2026 (+5%; Decreto 6225/26) ≈ US$ 527 ≈ R$ 2.678 | Bloomberg Línea / Infobae / ABC — **secundário** |
| Encargos | IPS: **16,5% patronal** + 9% do empregado | calculadora local — **secundário** |

**Efeito no payback [estimativa qualitativa, sem DRE rodado]:**
1. **Carga sobre o lucro muito menor que no BR.** O IRE é de 10%, contra IRPJ + CSLL de até 34% no lucro real. O IVA é de 10% "por dentro": de ₲199.000 brutos sobram ₲180.909 líquidos. Com a mesma margem operacional, isso **encurta o payback**.
2. **O ticket nominal é maior que no BR** (R$ 175 contra o low-cost brasileiro) e o **salário mínimo é maior em R$** (≈ R$ 2.678). O aluguel amostrado fica em ~R$ 19-23/m²/mês. Para receita, folha e aluguel, a premissa BR **não pode ser transcrita**; precisa do perfil próprio (BLK-INTL-11).
3. **O câmbio é um risco nas duas pontas.** O capex de equipamento importado é cotado em US$/R$, e a valorização recente do guaraní o barateia. Royalties e dividendos remetidos ao BR pagam INR/IDU de 15%, e o valor em R$ oscila ±15-20%/ano. O DRE do perfil precisa de `moeda.cambio_viabilidade` explícito e da sensibilidade ao câmbio.
4. A **Lei 194/93** é um risco de **custo de saída** de franqueado, não de operação.

---

## E. Veredito de dados por camada e mapeamento para o contrato

| Camada | Veredito | Impacto na confiabilidade do ranking | Mapeamento para colunas do contrato |
|---|---|---|---|
| **Identidade** | **Completa** | — | Partição `uf=XX`: 18 siglas de 2 letras **fabricadas** (regex `^[A-Za-z]{2}$`; o ISO 3166-2:PY é numérico, ex.: `PY-11`, `PY-ASU` — de memória, não verificado). Proposta: `AS` Asunción, `CE` Central, `AP` Alto Paraná, `IT` Itapúa, `CG` Caaguazú, `SP` San Pedro, `CR` Cordillera, `GU` Guairá, `CZ` Caazapá, `MI` Misiones, `PG` Paraguarí, `NE` Ñeembucú, `AM` Amambay, `CY` Canindeyú, `PH` Pdte. Hayes, `BQ` Boquerón, `AG` Alto Paraguay, `CN` Concepción. `SP`, `CE`, `AP` e `AM` colidem com UFs do BR; checar as tabelas TS por sigla, como na AR, ou trocar essas quatro. `cod_municipio` = código INE do distrito, **string de 4 caracteres zero-padded** (`"0000"`, `"1109"`). **Quebra o join do crescimento** (`str[:6]` contra `cod6.zfill(6)` → `"1109"` ≠ `"001109"`), mesmo defeito da AR; usar `cres_chave_nome` ou corrigir a plataforma. `nome_municipio` = `DIST_DESC` (latin-1 → normalizar). `hex_id`/`lat`/`lng` por H3 res 7 |
| **1 Potencial** | **Parcial com proxy** | **Médio-alto entre distritos, baixo dentro de Asunción/CDE**. Pop: dasimetria WorldPop raked ao distrito (e ao barrio em Asunción): erro moderado. Renda: modelada no distrito, com a ordem intradistrital por RWI (2021, 2,4 km). Num hex res 7 (~5 km²) de Asunción, o RWI vê 1-3 tiles: resolução **no limite** | `pop_total_setor_2022` = pop do hex (WorldPop raked aos totais do censo 2022). `populacao_corte_hex` = hex + 6 vizinhos. **Não emitir `pop_total`** (falso amigo). `renda_per_capita` = renda modelada `ipcm` no mês-base (₲, com coluna USD paralela), declarando `moeda.indicadores_renda`. Âncoras: R$300→R$4.000 equivalem hoje a **₲341 mil → ₲4,55 M** (mercado) ou ₲334 mil → ₲4,45 M (PPP); a EPHC urbana p10-p90 (0,73-4,40 M) cabe dentro, sem saturar. `score_setor_2022_calibrado` **recomputado na régua absoluta** (nunca percentil) |
| **2 Residual** | **Parcial com proxy** | **Baixo-médio**. A taxa de penetração é desconhecida (não há benchmark local) e a cobertura de concorrentes é baixa sem agregador. O residual pode sair inflado ("não mapeado vira livre") | `sam_fitness_potencial` = pop × taxa (a calibrar; faixa provisória 4-7% da pop urbana, entre a AR 7,8% e o relato local; **decisão**, não dado). `oferta_consumida_mercado_estimada` = Σ capacidade (Smart Fit ~2.000-2.500 por unidade de shopping de grande porte; independentes a calibrar). `oferta_efetiva_disponivel` em **alunos** |
| **3 Pressão** | **Parcial** | **Médio para a Smart Fit** (19 pontos exatos, coordenadas no site), **baixo para independentes** | `staging/concorrentes_mapeados.parquet`: Smart Fit (site), BIGG/EXEN/Premier (sites), OSM, opcionalmente Google Places. `capacidade_default_concorrente_alunos` próprio do PY. `status_registro` derivado |
| **4 Momentum** | **Parcial fraco** (só demografia) | **Baixo**: sinal único (crescimento populacional distrital projetado). Sem emprego formal nem empresas por território | `crescimento_municipal` com `cres_tendencia` derivada de Δpop 2022-2030 (Rev. 2025) e 2002→2022. `cres_emp_pct`/`cres_saldo_empresas`/`cres_salario` **nulos**. `crescimento_hex` por mudança de footprint/VIIRS: opcional e frágil (a AR reprovou o VIIRS) |
| **5 Fila** | **Derivada** (viável se 1-2 existirem) | Herda os erros de 1-2. Com residual em escala menor, `nota_dem` vai a 0 abaixo de 2.000 alunos, e a fila vira "só socio" (mesmo risco da AR) | `indice_praca` = 0,70·socio + 0,30·nota_dem; âncoras de demanda do perfil precisam de revisão |
| **Relatório Pontual** | **Parcial** | **Médio em Asunción** (barrio com pop oficial), **baixo fora** (pseudossetor) | Setor = barrio/localidad (geometria verificada) com pop dasimétrica raked ao distrito, ou a **manzana** com pop WorldPop (100 m ≈ manzana). `domicilios_particulares_ocupados_setor_2022` e `avg_moradores_domicilio_setor_2022` = valor do distrito (tabela de viviendas, não verificada). `renda_per_capita_setor_2022_calibrada` = renda modelada redistribuída. `uplift_composicao = 1,0` (como a AR). `geometry_wkb` EPSG:4674 nativo. `bbox_*` calculado. `nome_bairro` = `BARLO_DESC` |
| **Viabilidade** | **Parâmetros completos, premissas parciais** | Tributos e câmbio verificáveis; capex, ticket Ultra e curva m²→alunos precisam de premissa PY | `moeda.cambio_viabilidade` (PYG/BRL 1.136,45 em out/2026), regime IRE/IVA/IDU/INR no perfil (lacuna BLK-INTL-11), salário mínimo, IPS 16,5%, aluguel InfoCasas |
| **Imobiliário** | **Parcial** (fonte rica, termos não lidos) | — | Coletor novo (InfoCasas) em ₲/US$, sem IPTU (no PY é o "impuesto inmobiliario", municipal) |

### Hexágonos e mercado endereçável [estimativa]

- **WorldPop 2022 em H3 res 7** (soma 6,72 M, a ser reescalada para 6,11 M):
  - 35.287 hexes com pop > 0;
  - **742 com ≥ 1.000 hab** (4,88 M);
  - 249 com ≥ 5.000;
  - **1.094 com captação ≥ 5.000**: é o universo que passa o gate de 5.000 do funil.
- Por metro (bbox aproximada):

| Metro | Pop (WorldPop) | Hexes ≥ 1.000 hab | Hexes ≥ 5.000 hab |
|---|---|---|---|
| Gran Asunción | 2,52 M | 204 | 128 |
| CDE + Hernandarias/Pdte. Franco/Minga | 0,61 M | 57 | 35 |
| Encarnación | 0,17 M | 25 | 8 |
| PJC | 0,12 M | 12 | 6 |
| Coronel Oviedo | 0,10 M | 11 | 6 |

  - Fora desses cinco metros, o país quase não tem hex acionável.
- **Unidades que o mercado comporta:**
  - Benchmark de densidade: 4-6 unidades low-cost por milhão de habitantes urbanos, a faixa em que já opera a Smart Fit PY (4,4/M).
  - Aplicado a 4,3 M urbanos, dá **~17-26 unidades low-cost no país inteiro hoje**, e a Smart Fit já tem 19.
  - **Folga para a Ultra: ~3-8 unidades em 3-5 anos**, sobretudo em Central (Limpio, Capiatá, Luque, Ñemby, Itauguá: crescimento de 8-16% até 2030) e na área metropolitana de CDE (Minga Guazú, Pdte. Franco).
  - É estimativa grosseira: penetração e capacidade **não verificadas**.
- **Recomendação de escopo:** não rodar o país inteiro. Exportar 3-5 partições, `AS` + `CE` + `AP` + `IT` (+ `AM` por PJC/Ponta Porã). Isso reduz o custo de pipeline (renda e concorrentes) a ~70% da população urbana.

---

## F. Premissas frágeis e onde a analogia BR/AR quebra

1. **Censo sem renda e sem área pequena pública.** No BR há setor com renda. Na AR, o radio sem renda vinha **com covariáveis**. No PY, as covariáveis param no **distrito**, e Asunción inteira (462 mil, 117 km²) é um distrito só, de modo que a variação intraurbana depende de proxy (RWI 2021). É a quebra mais séria.
2. **Censo 2022 com cobertura de 94% e controvérsia.** A pop caiu frente a 2012 e ficou 18% abaixo da projeção anterior; a imprensa relata omissão maior em Asunción/Central/CDE. Usar a **projeção distrital Rev. 2025** (+2,9%) como total de controle é mais defensável que o censo cru, mas é decisão.
3. **WorldPop está 10% acima do censo.** Sem raking por distrito, o gate de 5.000 passa hex demais.
4. **EPHC sem Boquerón/Alto Paraguay** (irrelevantes para o escopo) e **sem georreferência de UPM**. O raking é por dpto × área, e não há validação intraurbana possível com dado público.
5. **Âncoras de renda × câmbio volátil.** Hoje R$↔₲ por mercado (1.136) e por PPP (1.114) quase coincidem, mas o guaraní valorizou ~17% em 12 meses. A âncora em R$ convertida "ao câmbio do dia" vai deslizar; fixar o mês-base e a conversão no perfil.
6. **Sem agregador (WellHub/TotalPass).** A espinha dorsal da coleta AR (68% da camada web) não existe. A capacidade calibrada da AR (1.070) e o fator de cobertura (2,675) não se transferem.
7. **Penetração desconhecida.** `taxa_fitness` será decisão, não medida; o residual herda esse chute.
8. **Momentum sem emprego/empresas por território.** A camada 4 vira só demografia, a menos que o INE libere o DIRGE por distrito.
9. **Hierarquia: Asunción é ao mesmo tempo "UF" e "município".** Gran Asunción fica partida em duas partições (`AS` + `CE`), e o ranking "por UF" separa núcleo e periferia da mesma praça.
10. **Código do distrito com 4 dígitos** quebra o join `cod6` (mesmo defeito da AR). E as siglas de 2 letras fabricadas podem colidir com tabelas TS por sigla (ex.: `SP`, `CE`, `AP`, `AM` também são UFs do BR).
11. **Moeda sem decimais e com números grandes** (₲4,55 M como âncora). Verificar máscaras e formatação (`separador_milhar` declarado e não lido no front).
12. **Ligação com o Brasil.** Fronteira seca PJC–Ponta Porã e ponte CDE–Foz, com circulação de reais. A população diurna e a demanda de brasileiros em CDE/PJC **não são medidas** por nenhuma fonte encontrada; a demanda real pode estar subestimada pelo residencial.
13. **Risco jurídico de franquia (Lei 194/93).** Sem análogo no BR/AR no contrato; precisa de parecer.

### O que ficou `não verificado`

- O nível geográfico exato da tabela "Caracterización de viviendas y hogares 2022" (domicílios e moradores por distrito?).
- A existência de população por barrio/localidad fora de Asunción. Não encontrei nenhuma.
- A camada pública de segmentos censitários com NSE; um pedido ao INE é necessário.
- A avaliação oficial de omissão censitária por departamento/distrito e o método da pesquisa de cobertura.
- A contagem de academias no OSM (Overpass indisponível; PBF de 154 MB não baixado).
- A série completa e o endereço das 19 Smart Fit (só 8 lidas com coordenada).
- As unidades atuais de BIGG, EXEN, Premier e Aerofisic/Fosque: os dados são de 2017-2024.
- A ausência de TotalPass no PY (não encontrei, mas não provei a ausência).
- A penetração fitness e o número de sócios no PY.
- Os termos de uso de InfoCasas, Clasipar, ABC Clasificados e Smart Fit.
- O texto integral da Lei 7593/2025 (sanções, transferência internacional).
- A Lei 6534/2020 (dados creditícios).
- A aplicabilidade da Lei 194/93 a franquias.
- O % de renda presumida do INR para royalties de franquia.
- A cifra oficial de 16,5% de IPS patronal (fonte secundária).
- O salário mínimo e a inflação, lidos em fonte secundária (Bloomberg Línea/Infobae; Rio Times) e não no MTESS/BCP.
- A licença exata do WorldPop R2025A e os termos do RWI no HDX.
- A Kontur Population (não baixada).
- A tabela publicada do DIRGE por distrito.
- A série de licenças de construção de Asunción.
- Os códigos ISO 3166-2:PY (citados de memória).
- O pareamento preço × m² dos anúncios do InfoCasas (inferido pela ordem no JSON).
