# Dossiê de dados — PERU (PE)

> **Leia junto com `01-consolidacao-auditoria.md`.** Este dossiê é a versão de campo, de 2026-10-16. A auditoria cruzada corrigiu alguns números e vereditos depois dele, e a versão corrigida vale sobre esta.

- Missão: pesquisa e planejamento para levar o Motor de Expansão da Ultra Academia ao Peru. Somente leitura sobre o repositório; nada foi alterado.
- Data de acesso de todas as fontes: **2026-10-16**.
- Amostras baixadas (dado não confiável, lido com `python -I`, nada executado): `C:\Users\Pichau\AppData\Local\Temp\claude\C--Users-Pichau-Documents-motor-de-expansao\d45e86bf-d899-46b1-bd74-dd25828a14cf\scratchpad\amostras\PE\`
- Convenção de status: **verificado** = abri a página/API ou baixei amostra e confirmei que o dado existe e é legível; **verificado (HEAD)** = confirmei existência, tamanho e data do arquivo por requisição HEAD, sem abrir o conteúdo (arquivo grande demais para a regra de amostra); **não verificado** = só por busca/terceiros, ou servidor fora do ar.

## Resumo em 6 linhas

1. **Censo 2025 é decisivo e está a meio caminho.** Campo de 4/ago a 31/out/2025; primeiros resultados em 29/mai/2026 (34.157.732 hab.); resultados **por província e pelos 1.892 distritos** publicados em 10/jul/2026 (verificado). **Não encontrei** microdados, REDATAM nem dado por manzana do Censo 2025 até 16/out/2026. A base intraurbana hoje é o **Censo 2017** (REDATAM até manzana).
2. **O censo peruano não pergunta renda.** A renda terá de ser **modelada**, como na AR: ENAHO 2025 (verificado: código 1031, módulo 34 "Sumaria" disponível) + covariáveis do censo + raking. Há um ativo que a AR não tinha: os **Planos Estratificados por ingreso a nivel de manzana** (INEI 2020; Lima com 50 distritos e "Grandes Ciudades" com 245), mas **só em PDF de mapas**, sem camada vetorial pública encontrada.
3. **A chave fecha de graça.** O UBIGEO do INEI tem 6 dígitos (2 depto + 2 prov + 2 distrito) e casa nativamente com o `str[:6]` / `cod6.zfill(6)` do contrato. É o primeiro país em que isso acontece. Ressalvas: zero à esquerda (Amazonas = `01xxxx`), UBIGEO do RENIEC ≠ UBIGEO do INEI, e malha HDX de 2015 com 1.873 distritos contra 1.892 no Censo 2025.
4. **Concorrência sem agregador.** WellHub e TotalPass **não operam no Peru** (verificado pela ausência no seletor de países). A oferta precisa vir de OSM + sites das redes. Mercado: 4.026 academias, ~2,1 M usuários, penetração de 6% (Mercado Fitness, 2024). Smart Fit tem ">90" unidades (91 em set/2025) e o plano Smart custa a partir de S/ 89,90.
5. **Macro: a premissa "inflação baixa" quebrou em 2026.** O IPC de Lima subiu 4,55% em 12 meses até set/2026, acima da meta (1-3%) desde mar/2026 (BCRP, verificado). O câmbio está estável em 3,36-3,45 PEN/USD. Aluguel comercial costuma ser cotado em USD + IGV 18%.
6. **Veredito:** as camadas 1 e 2 ficam **Parciais com proxy** (renda modelada, população de 2017 reescalada para 2025). A camada 3 também é **Parcial**, sem agregador e com capacidade a calibrar. A camada 4 é **Parcial com proxy razoável**: crescimento intercensal distrital real 2017-2025, RENAMU e diferenças do padrão RUC. A camada 5 é **Completa por construção**, se 1 e 2 existirem. O Relatório Pontual também é **Parcial**: falta a geometria de manzana oficial baixável.

---

## A. Dados por camada do funil

### A.0 Tabela de fontes (regra de evidência)

| # | Camada | Fonte | URL | Licença / termos | Formato | Granularidade espacial | Ano ref. | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | Identidade / malha | HDX COD-AB Peru (fonte IGN), via OCHA | https://data.humdata.org/dataset/cod-ab-per | **CC BY-IGO** (metadado da API HDX) | GDB / SHP / GeoJSON (zip 21-45 MB) + XLSX de códigos | adm1 = 25, adm2 = 196, adm3 = **1.873** distritos; `adm3_pcode` = `PE` + UBIGEO de 6 dígitos (ex.: `PE030101`) | Limites de 2015, revisados em 30/10/2025 | **verificado** (XLSX de 415 KB baixado e lido: `per_admin_boundaries.xlsx`) |
| 2 | Identidade | API do portal Censos 2025 (`/api/v1/geografia/*`) | https://censos2025.inei.gob.pe/api/v1/geografia/departamentos e `/distritos?codRegion=15&ccpp=01` | Termos não lidos (portal público do Estado) | JSON | Departamento / província / distrito. `idGeografia` = `9` + UBIGEO (ex.: `9150101` = Lima). **Lima Metropolitana aparece com `codRegion = 27`**, separada do departamento 15 | 2025 | **verificado** (`c25_departamentos.json`, `c25_dist_1501.json`: 43 distritos na província de Lima) |
| 3 | Censo / população | INEI — Censos Nacionales 2025, resultados por província e distrito | https://www.gob.pe/institucion/inei/noticias/1417313-censos-nacionales-2025-lima-metropolitana-continua-siendo-la-provincia-mas-poblada | Nota de imprensa oficial | HTML; tabulados XLSX por região e "cuadros interactivos" no portal https://censos2025.inei.gob.pe/descarga-de-datos | **Distrito** (1.892). Sem manzana | 2025 | **verificado** (nota de 10/07/2026 lida: Lima Metropolitana 9,6 M; Arequipa, Trujillo e Callao > 1 M; urbano 80,6%) |
| 4 | Censo / população | INEI — primeiro pacote do Censo 2025 (nacional) | https://www.gob.pe/institucion/inei/noticias/1399446-inei-poblacion-del-peru-totalizo-34-millones-157-mil-732-habitantes-al-2025 | Oficial | HTML | Nacional / departamento | 2025 (pub. 29/05/2026) | **não verificado** diretamente (gob.pe devolveu 418 ao WebFetch; total confirmado na nota de 10/07, que repete 34.158 mil) |
| 5 | Censo / geoportal | Geoportal do Censo 2025 (GeoServer `geoservercpv2025.inei.gob.pe`, camadas `cpv_resultados_v2:limites_administrativos_v2`) | https://censos2025.inei.gob.pe/geoportal | Exige autenticação (WMS/WFS devolvem **401**) | Vector tiles PBF | Limites administrativos | 2025 | **verificado** que existe e é **fechado** (401) |
| 6 | Censo / unidade mínima | INEI — REDATAM Censos Nacionales 2017 (até **manzana**) | https://censos2017.inei.gob.pe/redatam/ | Consulta on-line; termos não lidos | Ferramenta web REDATAM (processamento por área selecionada) | Departamento → distrito → zona censal → **manzana** (urbano); centro poblado (rural) | 2017 | **verificado** que o serviço responde (HTTP 200). Consulta por manzana **não executada** |
| 7 | Censo / unidade mínima (geometria) | CENEPRED/SIGRID — "Manzanas referenciales 2017" (fonte: INEI CPV 2017; campos pop total, homens, mulheres, viviendas) | https://sigrid.cenepred.gob.pe/arcgis/rest/services/Elementos_Expuestos/MapServer/2100300 | Termos não lidos (serviço estatal ArcGIS) | ArcGIS REST (FeatureServer/MapServer) | Manzana | 2017 | **não verificado** (servidor fora do ar em 16/10/2026: "No se puede acceder a ningún equipo del servidor") |
| 8 | Censo / geometria (terceiro) | GEO GPS PERÚ — "Manzanas urbanas de todo el Perú" | https://www.geogpsperu.com/2025/12/mapa-de-manzanas-urbanas-de-todo-el.html | **Sem licença declarada**; link de download em domínio de terceiro com aparência de anúncio | SHP | Manzana | 2017 (declarado) | **não verificado** — **não usar sem procedência** |
| 9 | Renda (proxy direto) | INEI — Planos Estratificados por ingreso a nivel de manzana de Grandes Ciudades (2020) | https://www.inei.gob.pe/media/MenuRecursivo/publicaciones_digitales/Est/Lib1747/libro.pdf ; nota: https://m.inei.gob.pe/media/MenuRecursivo/noticias/np123_2020.pdf | Publicação oficial, uso livre declarado ("cualquier usuario puede acceder") | **PDF de mapas temáticos** (sem camada vetorial pública encontrada) | **Manzana**, 5 estratos (Alto, Medio Alto, Medio, Medio Bajo, Bajo), **245 distritos** de grandes cidades | Censo 2017 + ENAHO 2017-2018 + registros administrativos | **verificado** (nota de imprensa baixada e lida: `np123_2020.pdf`) |
| 10 | Renda (proxy direto) | INEI — Planos Estratificados de Lima Metropolitana a nivel de manzana (2020) | https://www.inei.gob.pe/media/MenuRecursivo/publicaciones_digitales/Est/Lib1744/libro.pdf | Idem | PDF de 62 MB (HEAD: `Content-Length: 62069359`, `Last-Modified: 2020-07-18`) | Manzana, 50 distritos de Lima. Faixas de ingreso per capita do hogar (S/ mensais, via busca): ≥ 2.412,45; 1.449,72-2.412,44; 1.073,01-1.449,71; 863,72-1.073,00; ≤ 863,71 | 2017-2018 | **verificado (HEAD)**. As faixas são **não verificadas** (vieram de extração por busca, com ambiguidade de rótulo) |
| 11 | Renda (modelagem) | INEI — ENAHO 2025, metodologia atualizada, "Condiciones de Vida y Pobreza", anual (período 55), **código 1031**; módulo 34 "Sumaria" (ingreso/gasto do hogar) | https://proyectos.inei.gob.pe/iinei/srienaho/descarga/CSV/1031-Modulo34.zip (também SPSS/STATA) | Portal de microdados do INEI ("resguardando el secreto estadístico"); termos e condições não lidos na íntegra | ZIP CSV, **18.069.531 bytes**, `Last-Modified: 2026-05-04` | Hogar, com UBIGEO de distrito e estrato; representatividade nacional, urbano/rural e departamental (≈ 36,6 mil viviendas/ano, via busca) | 2025 | **verificado (HEAD)** + listagem de 32 módulos de 2025 lida no portal (`periodo.html`). Conteúdo do módulo **não aberto** |
| 12 | Renda (agregado de controle) | INEI — Mapa de Pobreza Monetaria Provincial y Distrital 2018 (ELL) | https://www.inei.gob.pe/media/DocumentosPublicos/pobreza/2018/Mapa-de-Pobreza-2018-Desagregacion.pdf | Oficial | PDF / tabelas | Província, distrito e subdistrito | 2018 (pub. 2020) | **não verificado** (só por busca; não encontrei edição oficial mais nova) |
| 13 | Renda (agregado nacional) | INEI — Pobreza monetaria 2025 | (notas de imprensa de 05/05/2026, ex.: https://lpderecho.pe/inei-reporta-25-7-peruanos-vivio-pobreza-monetaria-durante-ano-2025/) | Imprensa | HTML | Nacional / Lima Metropolitana | 2025 | **não verificado** na fonte primária: pobreza 25,7%; gasto per capita S/ 920/mês; linha S/ 462 |
| 14 | Renda (NSE de mercado) | APEIM — Niveles Socioeconómicos | https://apeim.com.pe/ ; boletim: https://apeim.com.pe/wp-content/uploads/2026/08/APEIM-News-Agosto-1.pdf | **Proprietário** (associação de pesquisa de mercado) | PDF | Nacional, Lima por "zonas APEIM" (agrupamentos de distritos) | 2025 (base ENAHO). **Atualização baseada no Censo 2025 marcada para 12/11/2026** | **verificado** o boletim (PDF de 2,5 MB lido: save-the-date "Niveles Socioeconómicos Perú" com atualização pelo Censo 2025) |
| 15 | Concorrência | OpenStreetMap — Geofabrik `peru-latest.osm.pbf` | https://download.geofabrik.de/south-america/peru-latest.osm.pbf | **ODbL** | PBF, 256.568.985 bytes, `Last-Modified: 2026-10-16` | Ponto / polígono | 2026 | **verificado (HEAD)**. Contagem de `leisure=fitness_centre` / `amenity=gym` **não verificada** (Overpass deu 500/504 em 3 espelhos) |
| 16 | Concorrência | Smart Fit Perú — planos e unidades | https://www.smartfit.com.pe/planes ; https://www.smartfit.com.pe/gimnasios | Termos do site não lidos; a lista de unidades carrega por API em JavaScript (não raspada) | HTML | Ponto (unidade) | out/2026 | **verificado** preço: plano "Smart" desde **S/ 89,90**, "Black" desde **S/ 129,90** (`smartfit_pe_planes.html`); a página de unidades mostra preços entre S/ 99,90 e S/ 139,90 |
| 17 | Concorrência | Gestión (02/10/2026) — Smart Fit Perú | https://gestion.pe/economia/empresas/smart-fit-mira-mas-alla-de-los-gimnasios-en-peru-que-prepara-para-su-marca-noticia/ | Imprensa | HTML | País | 2025-2026 | **verificado** (WebFetch): > 90 unidades, 91 em set/2025; avalia mais 5-10; Bio Ritmo em Surco, Miraflores e La Molina |
| 18 | Mercado fitness | Mercado Fitness — Radiografía 2024 Perú | https://mercadofitness.com/mercado-fitness-lanza-radiografia-gimnasios-en-peru/ | Página aberta; relatório completo com acesso não verificado | HTML / PDF | País | 2024 | **verificado** (WebFetch): 4.026 instalações, > 2 M usuários, penetração 6%, < 400 m², 2-5 funcionários |
| 19 | Mercado fitness | El Comercio Día1 (10/08/2024 e 14/12/2024) | https://elcomercio.pe/economia/dia-1/bodytech-se-fue-del-pais-como-se-esta-reconfigurando-el-mercado-de-gimnasios-con-esta-salida-dia-1-cadenas-de-gimnasios-smart-fit-b2-sportlife-deporte-actividad-fisica-noticia/ | Imprensa | HTML | País / Lima | 2024 | **verificado** (WebFetch): b2 com 8-9 sedes e ~20 mil sócios; Sportlife 3; KO 4; saída da Bodytech; Smart Fit com > 250 mil abonados e ~90 clubes no fim de 2024 |
| 20 | Agregadores | WellHub (seletor de países) / TotalPass | https://wellhub.com/es-mx/ ; https://totalpass.com/pe/ | — | HTML | — | out/2026 | **verificado**: o seletor do WellHub lista es-ar, es-cl, es-mx e es-es, **sem es-pe**; `totalpass.com/pe/` dá **404** |
| 21 | Momentum | Censo 2017 × Censo 2025 por distrito (crescimento intercensal) | Fontes 3 e 6 | Oficial | Tabelas | Distrito | 2017→2025 | **verificado** que o dado distrital 2025 existe (nota de 10/07/2026 cita taxas por distrito, ex.: Cerro Colorado +3,6% a.a.) |
| 22 | Momentum | INEI — RENAMU (Registro Nacional de Municipalidades), anual, inclui licenças de edificação e funcionamento | Portal de microdados (`Consulta_por_Encuesta.asp`, opção "Registro Nacional de Municipalidades - RENAMU") | Microdados INEI | Microdados por município (distrital/provincial) | Distrito | Anos até **2026** listados | **verificado** que os anos 2023-2026 constam no portal (`renamu_anios.html`). Variável de licenças **não verificada** (só por nota de imprensa de 2024) |
| 23 | Momentum | SUNAT — Padrón reducido del RUC | http://www2.sunat.gob.pe/padron_reducido_ruc.zip ; guia: https://orientacion.sunat.gob.pe/padron-reducido-del-ruc-para-descarga | Público; termos não declarados na página | ZIP (TXT delimitado), **393.798.962 bytes**, `Last-Modified: 2026-10-16` (atualização diária aparente) | **UBIGEO** do domicílio fiscal e dos locais anexos | Corrente | **verificado (HEAD)** + campos lidos na guia oficial: RUC, razão social, estado, condição, UBIGEO, domicílio. **Sem CIIU nem data de início** → momentum só por diferença entre snapshots |
| 24 | Momentum | MTPE — Planilla Electrónica / SIMEL (emprego formal) | https://elperuano.pe/noticia/293833-atencion-universitarios-mtpe-abre-sus-bases-de-datos-para-impulsar-investigaciones-sobre-empleo | Bases abertas para pesquisa (condições não lidas) | — | **Não confirmei recorte por UBIGEO** | 2026 | **não verificado** |
| 25 | Imobiliário | Urbania.pe / Adondevivir.com (mesmo grupo das brasileiras Imovelweb/QuintoAndar, segundo o rodapé) | https://urbania.pe ; https://www.adondevivir.com | `robots.txt` lido (Adondevivir: `User-agent: *` com Disallow em APIs e mapas). Termos de uso **não lidos** | HTML (anúncios) | Ponto / distrito | Corrente | **verificado** que a busca de locais comerciais devolve **403 "Just a moment" (Cloudflare)** nos dois portais |
| 26 | Imobiliário | Properati Perú | https://www.properati.com.pe | — | — | — | — | **verificado** que `robots.txt` devolve **401 Access Denied** (provável desativação ou bloqueio) |
| 27 | Imobiliário | Nexo Inmobiliario (projetos novos, sobretudo residenciais) | https://nexoinmobiliario.pe | `robots.txt`: `Disallow:` vazio | HTML | Projeto | Corrente | **verificado** (HTTP 200; pouco relevante para locais comerciais) |
| 28 | Macro | BCRP — API de séries (IPC Lima 12m `PN01273PM`; TC interbancário `PN01207PM`; BRL `PN01237PM`; taxa de referência `PD04722MM`) | https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN01273PM/json/2025-1/2026-10 | Aberto | JSON | Nacional / Lima | até set/2026 | **verificado** (JSONs baixados) |
| 29 | Macro | Banco Mundial — PPC (`PA.NUS.PRVT.PP`, `PA.NUS.PPP`) | https://api.worldbank.org/v2/country/PER/indicator/PA.NUS.PRVT.PP?format=json | CC BY 4.0 | JSON | Nacional | 2025 | **verificado** |

### A.1 Identidade, divisão administrativa e malha

- **Hierarquia:** departamento (24 + Província Constitucional do Callao = 25 no HDX) → província (196) → distrito (1.873 no HDX de 2015; **1.892** no Censo 2025). O equivalente de "município" brasileiro (ente com prefeitura) é o **distrito**: cada um tem *municipalidad distrital*. A província também tem *municipalidad provincial*.
- **Lima é um caso à parte.** A província de Lima (= Lima Metropolitana, 43 distritos, 9,6 M hab.) concentra ~28% do país. Com o Callao, passa de 10,6 M (≈ 31%). Na API do Censo 2025, "Lima Metropolitana" tem `codRegion = 27`, separada do departamento 15 (verificado). Ranquear "por município" no Peru = ranquear distritos de Lima com escala de cidade grande (San Juan de Lurigancho tem 1,125 M hab.).
- **Chave:** UBIGEO INEI, `str` de 6 dígitos com zero à esquerda (`010101` … `250401`). O pcode do HDX é `PE` + UBIGEO, então basta tirar o prefixo. **Armadilha:** o UBIGEO do RENIEC (usado no DNI e em bases administrativas) é **outro sistema**, não equivalente ao do INEI (confirmado por busca; pacotes de equivalência existem no GitHub, `jmcastagnetto/ubigeo`). Toda base externa tem de declarar qual UBIGEO usa.
- **Malha:** HDX/IGN (CC BY-IGO) serve para `ibge/municipios_<UF>.geojson`, mas é de 2015: faltam ~19 distritos criados depois. Esses distritos novos cairão no distrito-mãe, a menos que se obtenha o limite censitário de 2025, que hoje só está no geoportal fechado (401).

### A.2 Base censitária e unidade mínima

- **Censo 2025:** só há agregados até **distrito** (verificado). O portal tem "descarga de datos" com tabulados de população, hogar e vivienda em XLSX **por região** e "cuadros interactivos" com recorte por departamento, província, distrito e centro poblado (lido no código do SPA). **Não encontrei** microdados, REDATAM nem manzana. O INEI tinha prometido "resultados definitivos ... a nivel de manzana" (nota de jul/2025, via busca, **não verificado**), mas não há data.
- **Censo 2017 (base viável hoje):** o REDATAM chega a **manzana** (urbano), passando por zona censal. A geometria de manzana não tem download oficial encontrado. Caminhos: (a) a camada SIGRID/CENEPRED "Manzanas referenciais 2017", com pop por manzana (fora do ar hoje); (b) pedido formal ao INEI pela Lei de Transparência 27806 (procedimento existe; resposta não testada); (c) o shapefile de terceiro (sem procedência — evitar).
- **Recomendação de unidade mínima:** manzana 2017 (pop + viviendas) agregada ao hexágono H3 res 7 e **reescalada pelo total distrital de 2025** (raking por distrito). Assim se preserva a forma intraurbana de 2017 e o nível de 2025. Trocar pela manzana de 2025 quando o INEI publicar.
- **Domicílio:** o censo distingue *vivienda* e *hogar*. O total de 13.762.606 viviendas particulares (2025, via imprensa, **não verificado**) inclui 11,7% desocupadas e 11,6% de uso ocasional. Para `avg_moradores_domicilio` e `domicilios_particulares_ocupados`, usar *viviendas ocupadas* / *hogares*, e não o total. É a mesma armadilha que a AR teve com `viviendas` (§6 item 7 da receita).

### A.3 Renda / consumo — melhor proxy

O censo peruano **não tem pergunta de renda**. Pela busca, a cédula de 2025 tem 67 perguntas sem item de ingresso (**não verificado** na cédula oficial). Três insumos se complementam:

1. **ENAHO 2025** (verificado, código 1031). Tem ingresso e gasto do hogar no módulo 34 "Sumaria", com fator de expansão e UBIGEO. Os nomes de variável tradicionais (`inghog1d`, `gashog2d`, `mieperho`, `factor07`) são **não verificados nesta tarefa**. É o análogo da EPH argentina, com uma vantagem: é **nacional**, não só de aglomerados urbanos. Modelo: `log(ingreso pc) ~ educação do chefe + materiais da vivienda + serviços + posse de bens + tamanho do hogar + área/departamento`, aplicado à manzana do censo 2017 e com raking por departamento/domínio ENAHO. Saída em **PEN/mês**.
2. **Planos Estratificados (INEI 2020).** É o único proxy **direto por manzana**, com 5 estratos e faixas em S/, cobrindo Lima (50 distritos) e "Grandes Ciudades" (245 distritos). Como só existe em PDF, serve para **validação** (taxa de acerto do estrato previsto) ou, se o INEI liberar o vetor, como restrição de calibração. Base 2017-2018, então tem 8 anos de defasagem.
3. **Mapa de pobreza distrital 2018 (ELL)** como restrição de borda distrital. Opcional: APEIM/Ipsos NSE (proprietário) para checar a distribuição de Lima. A APEIM vai publicar a versão baseada no Censo 2025 em 12/11/2026.

- **Nível de referência:** gasto per capita nacional S/ 920/mês (2025); linha de pobreza S/ 462 (via imprensa, **não verificado** no relatório primário). Renda do trabalho média S/ 1.887/mês (EPEN 2025, via imprensa, **não verificado**).

### A.4 População diurna/noturna, densidade, urbanização

- **Urbanização:** 80,6% urbano em 2025; Lima e Callao 100% urbanos; Costa com 58,7% da população (verificado, nota de 10/07/2026).
- **Densidade:** derivável da pop da manzana sobre a área do polígono, o que exige a geometria (ver A.2).
- **População diurna:** não há fonte oficial equivalente. Proxies possíveis: o padrão RUC (estabelecimentos anexos por UBIGEO) e pesquisas de mobilidade de Lima (ATU/JICA). Nenhuma foi verificada.

### A.5 Academias e concorrência

- **Não existe GymScraping nem agregador.** Tanto WellHub quanto TotalPass estão ausentes (verificado). Logo, a "espinha dorsal" da coleta argentina (WellHub = 68% da camada web) **não existe no Peru**. Com isso também ficam **sem objeto** os módulos M&A e vulnerabilidade, que dependem dos snapshots semanais dos agregadores.
- **Fontes viáveis:**
  - OSM: PBF verificado. Contagem não verificada.
  - Sites das redes: Smart Fit (lista carregada por API JS; termos não lidos), Bio Ritmo, b2, Sportlife, KO Urban Detox, Gym Plus.
  - Google Places (pago; termos restritivos; não testado).
  - Padrão RUC: filtrar por razão social contendo "gym/gimnasio/fitness"; sem CIIU, então a precisão é baixa.
- **Capacidade por academia:** a razão bruta "2,1 M usuários / 4.026 instalações ≈ 520 usuários por instalação" é **derivada por mim**, não publicada. Ela é ainda menor que a calibração argentina (1.070, que corrige cobertura) e muito menor que os 2.500 do BR. Precisa da mesma calibração da AR: capacidade real × fator de cobertura (academias estimadas / vistas no OSM).

### A.6 Momentum urbano

- **Melhor sinal disponível:** crescimento intercensal **real** por distrito 2017→2025. Os dados existem (verificado); exemplos: Cerro Colorado +3,6% a.a.; Carabayllo +2,9%; Trujillo −0,7%; Chiclayo −0,2%. É uma vantagem sobre a AR, que não tinha série distrital recente. Limitação: é **estático** (8 anos), não trimestral como o CAGED.
- **Sinais recorrentes:**
  - **RENAMU** anual (licenças de edificação/funcionamento por município; anos até 2026 listados; variável não verificada).
  - **Padrão RUC** em diferença de snapshots: contribuintes ativos por UBIGEO, com arquivo diário de ~394 MB. Exige arquivar snapshots, porque não há data de início.
  - **Planilla/SIMEL:** recorte territorial não verificado.
  - Opcional: despacho de cimento e índices do BCRP, só nacional/departamental.

### A.7 Imobiliário / aluguel comercial

- **Portais:** Urbania e Adondevivir (grupo Navent/QuintoAndar) estão atrás de desafio Cloudflare (403 "Just a moment", verificado). É a mesma barreira anti-bot citada para o coletor brasileiro. Properati PE devolve 401. Nexo é residencial/projetos.
- **Escala de preço:** anúncios indicam ~US$ 20-30/m²/mês em San Isidro e Miraflores e ~US$ 8/m² em Ate. São **poucos anúncios** (via busca, **não verificado**, sem estudo de consultoria encontrado). Prática de mercado: cotação em **USD + IGV**, contrato mínimo de 3 anos.
- **BCRP:** publica preço de venda e aluguel de **departamentos** por distrito de Lima, em USD/m². Serve como proxy residencial; o recorte comercial não foi encontrado.

---

## B. Mercado fitness

| Indicador | Valor | Fonte / data | Status |
|---|---|---|---|
| Instalações | 4.026 | Mercado Fitness, Radiografía 2024 (pub. 27/11/2024) | verificado |
| Usuários | ~2,1 M ("más de 2 millones") | idem | verificado |
| Penetração | **6%** (contra AR 7,8% e CO 6,9% no mesmo relatório regional, via busca) | idem | verificado (PE); regional não verificado |
| Penetração segundo a Smart Fit | 4-5% no PE e no BR; "potencial de 15%" | El Comercio, 14/12/2024 | verificado |
| Perfil da academia típica | < 400 m², 2-5 funcionários | Mercado Fitness 2024 | verificado |
| Ticket low-cost (Smart Fit "Smart") | **S/ 89,90** ≈ **US$ 26,6** (3,379 PEN/USD, set/2026) ≈ **Int$ 46,7 PPC** (fator 1,927 de consumo privado, 2025) ≈ **R$ 136,8** (0,6572 S/ por R$, set/2026) | smartfit.com.pe/planes, 16/10/2026 | verificado (preço); conversões calculadas por mim |
| Ticket "Black" | S/ 129,90 ≈ US$ 38,4 ≈ Int$ 67,4 ≈ R$ 197,7 | idem | verificado (preço) |
| Disposição a pagar | 32% pagariam < S/ 100/mês; 31% entre S/ 100 e 150 | Impronta Research citada por El Comercio (10/08/2024) | não verificado na fonte primária |
| Tamanho do mercado | US$ 150-169 M (estimativas antigas) | Bodytech/IHRSA via imprensa | não verificado, antigo |

**Concorrentes (nº de unidades):**

| Rede | Segmento | Unidades | Fonte / data | Status |
|---|---|---|---|---|
| **Smart Fit** | low-cost (líder) | **> 90**; 91 em set/2025; "~90 clubes" no fim de 2024; > 250 mil abonados (2024) | Gestión 02/10/2026; El Comercio 14/12/2024 | verificado |
| Bio Ritmo (grupo Smart Fit) | premium | 3 (Surco, Miraflores, La Molina) + ~5 em avaliação | Gestión 02/10/2026 | verificado |
| b2 | full service | 8-9 em Lima; ~20 mil sócios | El Comercio 10/08/2024 | verificado (data antiga) |
| Sportlife | fitness club | 3 em Lima (outra fonte diz 7) | El Comercio 10/08/2024 | verificado / contraditório |
| KO Urban Detox | boutique | 4; > 5 mil alunos | idem | verificado |
| Gym Plus | — | não informado (recordação 29%) | idem | parcial |
| Bodytech | — | **saiu do Peru em 2024**; ~22 mil membros transferidos à Smart Fit | El Comercio | verificado |
| Gold's Gym | — | ativos vendidos à Smart Fit; master franquia antiga citada por terceiros | imprensa | não verificado (estado atual) |
| Fitness Point, Sportlife (expansão), outras regionais | — | não encontrado | — | não verificado |

**Maturidade do low-cost:** o mercado é **concentrado num único player** (Smart Fit, com 55% de recordação contra 24-46% dos demais) e muito fragmentado na cauda (4.026 instalações pequenas). Depois da saída da Bodytech, nenhum competidor anunciou aberturas (Smart Fit, dez/2024). Hoje a Smart Fit diz priorizar "calidad sobre cantidad" e o premium (Bio Ritmo). Para a Ultra (low-cost/massa, 18-45), o espaço comparável é o **low-cost fora dos distritos A/B de Lima** e as cidades intermediárias, onde a Smart Fit é mais rala. A distribuição das unidades da Smart Fit por distrito é **não verificada** (a lista é carregada por API, não raspada).

---

## C. Regulação

- **Proteção de dados:** Lei 29733 + **novo Regulamento DS 016-2024-JUS** (publicado em 30/11/2024; vigência em 29 ou 30/03/2025 conforme a fonte). Pontos:
  - consentimento prévio, livre, expresso e inequívoco;
  - Oficial de Datos Personales com cronograma por porte (grandes empresas: 1 ano a partir da publicação);
  - notificação de incidente à ANPD em 48 h (uma única fonte, **não verificado** no texto);
  - alcance extraterritorial: empresa estrangeira que trate dados de pessoas no Peru precisa de **representante local**.

  Impacto: o motor já não persiste PII (regra do projeto), mas o **cadastro de alunos** e o Relatório Pontual não podem levar dado pessoal. Coletar avaliações ou nomes de pessoas em sites cai no regime de consentimento.
- **Scraping:** não há lei específica, e não encontrei resolução da ANPD sobre scraping. Valem os termos de uso de cada site (os de Urbania, Adondevivir e Smart Fit **não foram lidos**), a Lei 30096 de Delitos Informáticos (acesso não autorizado; **não verificado** aqui) e a Lei 29733, se houver dado pessoal (ex.: nome e telefone de corretor nos anúncios, análogo ao "dossiê com contato de corretor" da DEC-037). Os portais usam desafio Cloudflare, então contorná-lo agrava o risco jurídico.
- **Franquia:** **não há lei específica de franquias** no Peru (WIPO e literatura). Aplicam-se o Código Civil (arts. 1354 e 1361, liberdade contratual), o DL 1075 e a **Decisão 486 da CAN** (marca); recomenda-se registrar a licença de uso de marca no INDECOPI. Há risco de responsabilidade solidária do franqueador pelo art. 67 do DL 1075 (segundo blog jurídico, **não verificado**). Não há obrigação de documento pré-contratual equivalente à COF brasileira (**não verificado**).
- **Investimento estrangeiro:** DL 662 e DL 757 dão **tratamento nacional e autorização automática**, com registro posterior (ProInversión). Convênios de estabilidade jurídica são opcionais (Lei 27342, DL 1011) e não dão benefício fiscal. Não encontrei restrição setorial para academias.

## D. Macro

| Item | Valor | Fonte | Status |
|---|---|---|---|
| Moeda | Sol (PEN, "S/"), separador decimal **vírgula** em sites de varejo (S/ 89,90) e ponto em fontes oficiais/BCRP (3.379) | sites; BCRP | verificado |
| Câmbio PEN/USD | 3,379 (média interbancária de set/2026); faixa 3,36-3,45 em 2026 | BCRP `PN01207PM` | verificado |
| Câmbio PEN/BRL | 0,6572 S/ por R$ (set/2026) → 1 S/ = R$ 1,522 | BCRP `PN01237PM` | verificado |
| Inflação (IPC Lima, 12 m) | **4,55% em set/2026**; 4,44% em ago; acima da meta de 1-3% desde mar/2026 | BCRP `PN01273PM`; Perú Retail 01/10/2026 | verificado |
| Taxa de referência BCRP | 4,25% (ago-set/2026) | BCRP `PD04722MM` | verificado |
| PPC (consumo privado) | 1,927 PEN por Int$ (2025) | Banco Mundial | verificado |
| UIT 2026 | S/ 5.500 (DS 301-2025-EF) | El Peruano / imprensa | verificado por múltiplas fontes de imprensa |
| IR empresarial | Regime Geral **29,5%**; **RMT** 10% até 15 UIT (S/ 82.500) de renda líquida e 29,5% acima; teto do RMT 1.700 UIT (S/ 9,35 M de receita) | imprensa e guias | parcialmente verificado (imprensa) |
| IGV | **18%** (16% IGV + 2% IPM) | conhecimento geral | **não verificado** nesta tarefa |
| Dividendos | 5% | conhecimento geral | **não verificado** |
| Salário mínimo (RMV) | S/ 1.230 desde 01/10/2026; S/ 1.300 previsto para o 1º semestre de 2027 (DS 015-2026-TR) | imprensa | verificado (imprensa) |
| Encargos trabalhistas | 2 gratificações/ano + CTS (~1 salário/ano) + EsSalud 9% | conhecimento geral | **não verificado** |

**Efeito sobre o DRE e o payback** (qualitativo; nada foi calculado contra o golden):

1. **IGV 18% embutido no preço.** O ticket de S/ 89,90 rende S/ 76,19 líquidos. Em contrapartida, aluguel, obra e equipamentos geram crédito de IGV, e no ano 1 o crédito de capex pode zerar o IGV a pagar por meses. O DRE BR (Simples/PIS-COFINS/ISS) não tem esse mecanismo de crédito → `viabilidade_tributo_provisorio` precisa de premissas peruanas próprias (BLK-INTL-11).
2. **IR de 29,5%** (ou 10% no primeiro tramo do RMT para franqueado pequeno) é menor que os 34% do Lucro Real BR, e o dividendo paga 5%.
3. **Folha mais cara por salário-base:** ~14 salários/ano + CTS + EsSalud, contra 13,33 + FGTS + INSS no BR. O nível salarial é mais baixo (RMV S/ 1.230 ≈ R$ 1.872).
4. **Aluguel em USD:** risco cambial moderado, porque o sol é estável. Mas o modelo precisa ser **bimonetário**: receita em PEN, aluguel e parte do capex em USD.
5. **Inflação de 4,5%** em 2026 reajusta aluguel e salário. Payback em termos reais fica sensível a reajuste de ticket, que a Smart Fit hoje ancora.
6. **Penetração de 6% e capacidade pequena por academia** reduzem o SAM por hexágono contra o BR. O efeito líquido sobre o payback é **não estimado**.

---

## E. Veredito de dados por camada

| Camada | Veredito | O que vira a coluna do contrato | Impacto na confiabilidade do ranking |
|---|---|---|---|
| **Identidade** | **Completa** | `cod_municipio` = **UBIGEO INEI de 6 dígitos como string** (`"150101"`); casa nativamente com `str[:6]` e `cod6.zfill(6)`. `nome_municipio` = nome do distrito. `uf=XX` = 25 partições de nível 1 com **siglas fabricadas** de 2 letras (sugestão: separar **Lima Metropolitana** do restante do departamento de Lima, como faz o INEI com `codRegion 27`). `hex_id`/`lat`/`lng` por H3 | Baixo risco. **Atenções:** zero à esquerda (Amazonas `01…`); UBIGEO RENIEC ≠ INEI em bases externas; malha de 1.873 contra 1.892 distritos |
| **1 Potencial** | **Parcial com proxy** | `pop_total_setor_2022` ← pop da manzana 2017 agregada ao hex e reescalada ao total distrital de 2025. `populacao_corte_hex` ← captação (hex + 6 vizinhos), como na AR. `renda_per_capita` ← **renda modelada ENAHO 2025 em PEN/mês** (`moeda.indicadores_renda = "PEN"`), não em USD, para evitar a terceira moeda. `score_setor_2022_calibrado` ← **recomputado** com âncoras peruanas (decisão, não transcrição) | **Médio-alto.** A população é boa (censo real, só a forma de 2017). A renda é modelo com erro provavelmente semelhante ao da AR (±15-25%; não medido). Os Planos Estratificados permitem **medir** acerto nos 245 distritos urbanos, o que a AR não pôde fazer |
| **2 Residual** | **Parcial com proxy** | `sam_fitness_potencial` = pop 18-45 (ou total) × **taxa_fitness ≈ 0,06** (Mercado Fitness 2024; calibrar por Lima × resto). `oferta_consumida_mercado_estimada` = nº de concorrentes × **capacidade calibrada** (bruto ~520 usuários/instalação, derivado; aplicar fator de cobertura). `oferta_efetiva_disponivel` = max(SAM − oferta, 0) em **alunos** | **Médio.** É sensível à capacidade e à cobertura do OSM, que não foram medidas. Com capacidade baixa, o residual por hex fica pequeno e a `nota_dem` da camada 5 tende a 0 (piso de 2.000 alunos), o mesmo achatamento visto na AR. As âncoras de demanda precisam de régua peruana |
| **3 Pressão** | **Parcial com proxy** | `staging/concorrentes_mapeados.parquet` ← OSM + sites das redes (Smart Fit, Bio Ritmo, b2, Sportlife, KO), deduplicados, com `status_registro`. `n_concorrentes_influencia_1km` ← contagem própria no disco de 1 km | **Médio.** Sem agregador, as independentes ficam sub-representadas (só OSM). A Smart Fit, que importa mais, é coletável. Os módulos M&A/vulnerabilidade **não se aplicam** |
| **4 Momentum** | **Parcial com proxy (bom)** | `crescimento_municipal.parquet`: `cod6` = UBIGEO; `cres_tendencia` ← taxa intercensal 2017-2025 do distrito; `cres_saldo_empresas` ← diferença de RUC ativos por UBIGEO (exige arquivar snapshots); licenças ← RENAMU. **Sem** `cres_emp_pct`/salário (sem CAGED/RAIS por distrito verificado) | **Médio.** O sinal estrutural (intercensal) é forte e oficial. Os sinais recorrentes exigem montar série própria. Os textos "CAGED/RAIS" fixos na plataforma ficam errados |
| **5 Fila** | **Completa por construção** (se 1 e 2 existirem) | `indice = 0,70·socio + 0,30·nota_dem` | Herda as fragilidades de 1 e 2. As âncoras `DEMANDA_MIN/MAX_ALUNOS` (2.000/20.000) em escala BR achatam o termo de demanda (ver camada 2) |
| **Relatório Pontual** | **Parcial** | `setores_censitarios_2022_geo` ← **manzanas ou zonas censais de 2017** com pop/viviendas (REDATAM), geometria (SIGRID ou pedido ao INEI) e renda modelada redistribuída. `avg_moradores_domicilio` ← pessoas / *hogares* (não viviendas totais). `uplift_composicao = 1,0` (molde AR) | **Médio-baixo** até haver geometria oficial baixável. Bairro (`nome_bairro`) não existe como nível censitário; o mais próximo é a zona censal ou a *urbanización* (não verificado) |
| **Viabilidade** | **Parcial** | `moeda.cambio_base` PEN/USD 3,379; `cambio_viabilidade` PEN/BRL 0,6572 (set/2026); regime tributário IGV + IR 29,5%/RMT; aluguel em USD | **Médio-baixo:** sem premissas peruanas, o DRE BR erra o tributo (sem crédito de IGV) e a folha |
| **Oportunidades imobiliárias** | **Inviável no curto prazo** | — | Portais atrás de Cloudflare, termos não lidos e preços em USD. Exigiria coletor novo |

**Recorte geográfico recomendado:** malha H3 **nacional** (barata, porque censo e malha são nacionais), com o uso operacional focado nas **grandes cidades**: Lima Metropolitana + Callao (≈ 31% da população), Arequipa, Trujillo, Chiclayo e Piura, mais Ica, Cusco e Huancayo como segunda onda. É exatamente o universo dos 245 distritos dos Planos Estratificados, onde a renda modelada pode ser **validada**. Fora dele, a renda fica sem validação e com confiança baixa.

---

## F. Premissas frágeis e onde a analogia BR/AR quebra

1. **"Censo novo = base pronta."** Falso por ora: o Censo 2025 tem dado distrital, mas **não manzana** nem microdado (até 16/10/2026), e o calendário não foi encontrado. Planejar em 2017 + reescala, com troca futura.
2. **"Renda vem do censo."** Falso nos dois países andinos: o Peru não pergunta renda, então ela é **modelo** (ENAHO). A âncora de renda é **decisão**. Os Planos Estratificados são a única régua externa por manzana, e ainda assim estão em PDF, com base 2017-2018.
3. **"Município" = distrito, mas Lima não é uma cidade no sentido do motor.** São 43 "municípios" numa mancha urbana contínua. Rankings "por município" vão comparar San Isidro com San Juan de Lurigancho como se fossem cidades.
4. **Chave UBIGEO "fecha de graça" — só a do INEI.** Bases do RENIEC e algumas do MTPE/SUNAT podem usar outro UBIGEO (verificar por fonte). A malha HDX é de 2015 (19 distritos a menos).
5. **"Sem agregador" muda a camada 3 e mata o M&A.** Na AR, 68% da camada web vinha do WellHub. No Peru essa fonte não existe. As independentes só aparecem via OSM, de cobertura desconhecida (contagem não obtida).
6. **Capacidade por academia:** BR 2.500, AR 1.070, PE com bruto ~520 usuários/instalação (derivado de dados de 2024). Se a régua de 2.500 for usada, a oferta consumida fica superestimada ~5× e o residual some. A régua precisa ser calibrada.
7. **Penetração:** 6% (Mercado Fitness) contra 4-5% (Smart Fit) contra 17,35% calibrado no BR (DEC-060). A diferença muda o SAM em 3×.
8. **Inflação baixa:** quebrou em 2026 (4,55% em set). Âncoras monetárias (renda, metas, ticket) precisam de mês-base declarado e deflator, como na AR (mai/2026).
9. **Moeda e formatação:** PEN com "S/", vírgula decimal no varejo e ponto nas fontes oficiais. Aluguel em USD. Viabilidade em BRL → três moedas, como na AR.
10. **Domicílio:** `viviendas` totais incluem 23% de desocupadas ou de uso ocasional (dado de 2025, via imprensa). Usar ocupadas/hogares.
11. **Imobiliário:** o mesmo grupo dos portais brasileiros, mas com anti-bot Cloudflare e cotação em USD. O coletor do Vini não é reaproveitável sem trabalho e sem leitura de termos.
12. **Regulação:** o novo regulamento de dados exige representante local para empresa estrangeira que trate dados de residentes no Peru. Para o motor (sem PII) o impacto é baixo; para o cadastro de alunos ou o bot, não.

### Lista explícita do que ficou `não verificado`

- Calendário do Censo 2025 para resultados definitivos, microdados, REDATAM e **manzana**; promessa de "dados por manzana" (nota de jul/2025).
- Ausência de pergunta de renda na cédula de 2025 (só por busca).
- Total de viviendas de 2025 (13.762.606) e as percentagens de desocupação (só imprensa).
- Faixas em S/ dos Planos Estratificados de Lima (extração por busca com ambiguidade de rótulo). Existência de camada vetorial desses planos.
- Camada SIGRID "Manzanas referenciais 2017" (servidor fora do ar). Shapefile de manzanas da GEO GPS PERÚ (sem licença ou procedência).
- Conteúdo do módulo 34 da ENAHO 2025 (nomes de variáveis); representatividade amostral exata.
- Mapa de pobreza distrital: existência de edição oficial posterior a 2018.
- Pobreza 2025 (25,7%), gasto per capita (S/ 920) e renda do trabalho (S/ 1.887): só imprensa.
- Contagem de academias no OSM (Overpass falhou em 3 espelhos).
- Lista e distribuição das unidades da Smart Fit por distrito; nº atual de unidades de Sportlife, b2, Gym Plus e Gold's Gym; existência de "Fitness Point".
- Penetração regional (AR 7,8%, CO 6,9%) e disposição a pagar (Impronta).
- Planilla Electrónica/SIMEL com recorte por UBIGEO; variável de licenças no RENAMU de 2025-2026.
- Termos de uso de Urbania, Adondevivir, Smart Fit, INEI (microdados) e SUNAT.
- Preços de aluguel comercial (US$ 20-30/m² em San Isidro/Miraflores; US$ 8/m² em Ate): poucos anúncios via busca, sem estudo de consultoria.
- IGV 18%, dividendos 5%, encargos trabalhistas (gratificações, CTS, EsSalud), prazo de 48 h de notificação de incidente, ausência de documento pré-contratual de franquia, art. 67 do DL 1075, Lei 30096.
- Data exata de vigência do DS 016-2024-JUS (29 ou 30/03/2025).
