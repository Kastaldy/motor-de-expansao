# Auditoria — mercado, tributos e regulação (CO, MX, PE, PY)

- Data de acesso de todas as fontes: **2026-10-16**. Nada foi alterado no repositório.
- Escopo: seções B, C, D e F dos dossiês `../01-dossie-CO.md`, `../01-dossie-MX.md`, `../01-dossie-PE.md`, `../01-dossie-PY.md` e `../01-dossie-transversal.md`.
- Status: **verificado** = abri a fonte primária (RI, lei/decreto, jurisprudência, autoridade tributária, banco central/instituto, site oficial); **secundário** = imprensa, escritório, compilação ou trecho de busca de página oficial que não abriu; **não verificado** = sem fonte confiável.
- Amostras (dado não confiável) em `scratchpad/amostras/auditoria/`; scripts em `scratchpad/scripts_aud/` (rodados com `python -P -E`, fora do diretório das amostras).

---

## (a) Contradições → valor canônico

### a.1 Smart Fit por país (item 1)

| País | Dossiês / transversal | **Canônico (RI, 30/06/2026)** | Contador do site oficial (16/10/2026) | Fonte | Status |
|---|---|---|---|---|---|
| CO | 232 (jun/26) × 224 (transversal, fim de 2025) | **232** | 245 | Apresentação Institucional set/2026, p. 34 (PT) e p. 97 (EN), "Data: 30 de Junho de 2026": https://investidor10.com.br/acoes/link_comunicado/SMFT3/49409/ · site: https://www.smartfit.com.co/gimnasios (`locationsCount`) | **verificado** |
| MX | 488 (2T26) × ">500" (transversal) | **488** | 526 | Mesma p. 34; release 2T26 (05/08/2026), p. 7: Brasil 1.025 · México 488 · Outros 657 · total 2.170: https://api.mziq.com/mzfilemanager/v2/d/757d3905-6a2d-496a-bbb0-32ddd17de6a0/1d71f14f-0745-4f1a-aef4-ba889799d97f?origin=2 | **verificado** |
| PE | ~91 (set/2025) × ~90 (transversal) | **95** | 101 | p. 34 da apresentação (entrada em 2016, 0,8 % membros/população) | **verificado** — o dossiê PE estava defasado |
| PY | 19 (site) × "≥5" (transversal) | **19** (site; o RI não abre o PY, ele fica em "Outros Países") | 19 | https://www.smartfit.com.py/gimnasios (`locationsCount":19`) | **verificado** (site) |

Notas:
- O contador do site inclui unidades em **pré-venda** (a página do PE tem marcadores `presale`/`coming_soon`/"Pre-Venta"). Use o **RI como denominador** (unidade aberta) e o site como **teto/pipeline**: CO +13, MX +38, PE +6 em 3,5 meses.
- "Brasil 986" na p. 34 é só a marca Smart Fit; o release dá 1.025 (todas as marcas). Não afeta os 4 países.

**Clientes por país:**

| País | Valor | Fonte | Status |
|---|---|---|---|
| MX | **1.255 mil** clientes em academias (2T26); 1.110 mil no 2T25 → ~2.570 por unidade | Release 2T26, p. 8. As séries fecham com o total de 5.582 mil em todos os trimestres. A atribuição da série à legenda segue a ordem (Brasil ~2,25 M, México ~1,25 M, Outros ~2,08 M) | **verificado** (a atribuição é inferida, mas consistente) |
| CO | 1,3 % de membros/população → ~0,69 M (sobre 53,4 M) → ~2.990 por unidade | Apresentação, p. 34 | % **verificado**; absoluto = [estimativa] |
| PE | 0,8 % → ~0,27 M (sobre ~34 M) → ~2.900 por unidade | idem | % **verificado**; absoluto = [estimativa] |
| PY | não divulgado | — | **não verificado** |

**Ressalva:** no MX, 1.255 mil ÷ 130,9 M = **0,96 %**, mas a p. 34 diz 0,8 %. O "% membros/população" da apresentação é arredondado e usa base populacional não declarada. Para calibrar capacidade, prefira o **absoluto** quando existir. Em CO e PE, trate os absolutos derivados com ±20 %.

### a.2 Agregadores (item 2)

| País | WellHub | TotalPass | Outro agregador ativo | Status |
|---|---|---|---|---|
| CO | **Não opera.** O seletor de país do site lista US, BR, MX, AR, CL, ES, PT, IT, FR, LU, BE, UK, IE, CA, DE; `/es-co/` dá 403 | **Não opera.** `totalpass.com/co/` dá 404; a apresentação da Smart Fit mostra TotalPass só em BR e MX | **Sim, dois.** **Fitpass Colômbia**: "+400 centros e gimnasios del país" (https://www.fitpass.com/co). **Fitpal**: "+600 centros", 23 cidades, só CO (https://fitpal.co/) | **verificado** (sites oficiais, 16/10/2026) |
| MX | **Opera** (`/es-mx/` 200) | **Opera** (`/mx/` 200; líder em usuários, segundo a Sensor Tower na apresentação da Smart Fit) | Fitpass MX (origem) | **verificado** |
| PE | **Não opera** (`/es-pe/` 403; fora do seletor) | **Não opera** (`/pe/` 404) | **Nenhum ativo encontrado.** O Fitness Pass (Lima, 2018, 171 centros) redireciona para `4ventsgroup.com`, ou seja, está extinto ou foi vendido; `fitpass.com/pe` redireciona para `/mx` | **verificado** (negativo para WellHub/TotalPass/Fitpass); Fitness Pass = **secundário** |
| PY | **Não opera** (`/es-py/` 403) | **Não opera** (`/py/` 404) | **TuPase** (origem uruguaia, benefício corporativo, "+600 centros" em UY/PY/BO), segundo a imprensa. O domínio não respondeu deste ambiente | WellHub/TotalPass **verificado**; TuPase **secundário** |

**Conclusão:** o molde argentino (agregador = espinha dorsal da camada web) é **replicável no MX** (WellHub + TotalPass) e **na CO, trocando WellHub por Fitpass CO/Fitpal** (termos e robots **não lidos**). Não é replicável no **PE** nem no **PY**, onde, no máximo, o TuPase cobre uma fatia corporativa a investigar. O dossiê CO, que dizia "sem agregador", **muda**.

### a.3 Penetração fitness (item 3)

**Achado de método:** os números por país do *2026 HFA Global Report* (ref. 2024, divulgado via Mercado Fitness em 15-21/09/2026) **são os mesmos das Radiografías da Mercado Fitness**:
- **MX:** a Radiografía 2024 (PDF lido) traz ">20.000 instalações", **7,2 M** de sócios e **5,64 %**, calculados como contagem de instalações na internet × distribuição de usuários da pesquisa. O HFA traz 20.642 / 7,2 M / 5,6 %.
- **PE:** a Radiografía 2024 traz 4.026 / 2,1 M / 6 %; o HFA traz os mesmos números.
- **AR:** 8.662 é exatamente o parque do perfil AR do repositório.

Logo, HFA e Mercado Fitness **não são duas fontes independentes**: é uma série só, e comparável entre AR, MX, CO e PE. Isso inverte a leitura do dossiê CO: o *outlier* é o "3 %", não o HFA.

| País | Valores em disputa | **Recomendação** | Fonte | Status |
|---|---|---|---|---|
| MX | 3-6 % sem método; piso de 1,26 % | **5,6 % central; faixa 4-6 %** (piso duro de 1,26 % = só as redes listadas) | Radiografía MX 2024: https://mercadofitness.com/pdf/radiografia-mexico-2024-mercado-fitness.pdf · HFA via https://mercadofitness.com/los-ingresos-industria-fitness-mundial-crecieron-107-2025/ | **verificado** (Radiografía lida; HFA original pago, não lido) |
| CO | 6,9 % (HFA) × 3 % (artigo MF dez/2024) × 2-3 % (executivos, imprensa antiga) | **6,9 % central para comparabilidade com AR/MX/PE; sensibilidade obrigatória em 3 %**. A divergência é de definição de instalação (7.940 × 2.800) | HFA via Mercado Fitness | 6,9 % **secundário** (relatório original não lido); 3 % **não verificado** nesta auditoria |
| PE | 6 % × 4-5 % (Smart Fit) | **6 % central; faixa 4-6 %** | Radiografía PE 2024 = HFA | **secundário** (artigo MF; o PDF da Radiografía PE não está no padrão de URL do MX, que dá 404) |
| PY | desconhecida | **Decisão, não dado: faixa 3-5 %** (abaixo de AR 7,8 % e de CO/PE 6-7 %; acima do "2 % treina constante", declaração sem método de franqueado). Nem HFA nem MF publicam o PY (só houve evento MF em Assunção, 26-27/06/2026) | — | **não verificado** |

**Régua de capacidade implícita (sócios ÷ instalação, HFA/MF 2024):** MX ~349, AR ~416, CO ~453, PE ~522, contra BR 2.500 no motor. Confirma que a `capacidade_concorrente` tem de ser **por país** (e, se possível, por estrato de porte). A Smart Fit sozinha fica em ~2.600-3.000 por unidade nos três países com dado.

### a.4 Imposto indireto sobre a mensalidade (item 4)

| País | Dossiê | **Canônico** | Fonte | Status |
|---|---|---|---|---|
| **CO — IVA** | "não verificado; risco #1" | **IVA 19 % sobre a mensalidade de academia.** Não há exclusão para academia comum. A única via é o **CAPF** (Lei 729/2001, art. 6, + ET art. 476, num. 1, "serviços médicos"), e só para quem chega **remetido por profissional de saúde externo**, com CAPF autorizado pelo ente esportivo municipal e equipe de saúde. Histórico: excluídos pela Lei 633/2000 → 7 % pela Lei 788/2002 → tarifa geral pela Lei 1111/2006 | Consejo de Estado, Sección Cuarta, exp. 68001-23-33-000-2016-00681-01 (23572), sentença de 07/05/2020 (caso Progym), no normograma da DIAN: https://normograma.dian.gov.co/dian/compilacion/docs/68001-23-33-000-2016-00681-01(23572).htm | **verificado** (jurisprudência). Receita líquida = preço ÷ 1,19 (−16,0 %) |
| CO — ICA Bogotá CIIU 9311 | não verificado | Tarifa específica **não confirmada**. Regime atual: Acordo 65/2002 (4,14-13,8 ‰). Reforma aprovada no Concejo em 28/09/2026 (PA 709/724), com 9 tarifas de 4 a 20 ‰ a partir de 01/01/2027, **pendente de sanção** | Pérez-Llorca, boletim out/2026; Crowe | **secundário / não verificado** (a página da Hacienda Distrital não entregou a tabela) |
| **PE — IGV** | "18 % (16 + 2)", não verificado | **18 % total, mas a composição mudou: em 2026 é IGV 15,5 % + IPM 2,5 %** (Lei 32387, publicada em 16/06/2025). Cronograma: 2027 15 + 3; 2028 14,5 + 3,5; 2029 14 + 4. **A carga total não muda** (receita líquida = preço ÷ 1,18; −15,3 %). A academia não está nas exonerações; a alíquota especial de 8 % + IPM vale só para restaurantes/hotéis MYPE | RSM Peru: https://www.rsm.global/peru/es/node/1494 ; tabela da SUNAT vista em busca (emprender.sunat.gob.pe deu 403); páginas antigas da SUNAT (RG/RMT) ainda dizem "16 % + 2 %" | **secundário** (consistente entre SUNAT via busca e RSM) |
| PE — RMT | 10 % até 15 UIT, 29,5 % acima, teto de 1.700 UIT | **Mantido** | SUNAT renta (via busca; a página deu 403). **Atenção:** a página legada `ww1.sunat.gob.pe/ol-ti-itmoddatruc/RMT.html` traz 10/15/35 % e IGV 16 + 2 %. É um regime antigo (RTMPYME): não usar | **secundário** |
| **MX — IVA** | 16 %, declarado | **IVA 16 % sobre a mensalidade, sem isenção.** O art. 15 da LIVA não isenta academia. A única menção a esporte (fr. XII, e) **exclui** da isenção associações com instalações esportivas > 25 % do ativo. Zona fronteiriça norte: 8 % com estímulo | LIVA art. 15 (compilação mLey): https://mley.mx/LIVA/articulo/15/ | **secundário** (compilação; texto da Câmara/DOF não aberto: diputados.gob.mx recusou conexão). Receita líquida = preço ÷ 1,16 (−13,8 %) |
| MX — ISR / PTU | 30 % / 10 % | **Mantidos** (carga ≈ 37 % do lucro antes de PTU e ISR) | LISR art. 9; LFT art. 117 | **não verificado** nesta auditoria (conhecimento consolidado) |
| **PY — IVA / IRE / IDU** | 10 % / 10 % / 8-15 % | **Mantidos** | Lei 6380/2019 (Ferrere, PwC 2019) | **secundário** (texto da lei não aberto) |
| PY — INR sobre royalty | 15 % sobre renda presumida de 30-100 % | **15 % × % presumido; o % para royalty de marca/franquia continua não verificado** → efetivo entre 4,5 % e 15 %. Para o DRE, usar **15 % (pior caso)** até parecer local | PwC 2019 (PDF lido: só confirma INR 15 % e IDU 8/15 %) | **secundário / não verificado** |

### a.5 Acordos de dupla tributação com o Brasil e retenção sobre royalties (item 5)

| País | Acordo com o Brasil | Teto do tratado sobre royalty | Retenção interna (sem tratado) | Fonte | Status |
|---|---|---|---|---|---|
| **MX** | **Em vigor** desde 30/11/2006 (Decreto 6.000/2006) | **15 %**. O Protocolo, item 6, aplica o art. 12 também a **assistência técnica e serviços técnicos**; cláusula de nação mais favorecida com piso de 10 % | LISR art. 167: 25 % para assistência técnica e demais royalties; para patente/marca, a tarifa máxima do art. 152 (~35 %) | https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/decreto/d6000.htm ; https://mley.mx/LISR/articulo/167/ | tratado **verificado**; interna **secundário** |
| **PE** | **Em vigor** (Decreto 7.020/2009; Portaria MF 553/2010) | **15 %**. O Protocolo inclui **serviços técnicos, assistência técnica, digitais e consultoria** como royalty | 30 % (LIR) | https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2009/decreto/d7020.htm | tratado **verificado**; interna **não verificado** |
| **CO** | **Assinado em 05/08/2022; aprovado pelo Congresso brasileiro (Decreto Legislativo 193, de 02/09/2025)**. Decreto presidencial de promulgação e troca de notas **não encontrados**; a Receita não o lista. Tratar como **não vigente** | (texto não lido) | **20 %** (ET art. 408) + IVA de 19 % por autorretenção sobre serviço importado | DL 193/2025: https://www2.camara.leg.br/legin/fed/decleg/2025/decretolegislativo-193-2-setembro-2025-797919-convencao-176284-pl.html ; lista da Receita: https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/legislacao/acordos-internacionais/acordos-para-evitar-a-dupla-tributacao/acordos-para-evitar-a-dupla-tributacao-e-prevenir-a-evasao-fiscal | tramitação **verificado**; vigência **não verificado**; 20 % **secundário** |
| **PY** | **Não há acordo vigente.** Convenção assinada em 2000 e aprovada no Senado em 2003, mas **ausente da lista da Receita** | — | INR 15 % × % presumido (ver a.4) | lista da Receita (acima); Senado: https://www25.senado.leg.br/web/atividade/materias/-/materia/62967 | ausência na lista **verificado** |

### a.6 Franquias (item 6)

| País | Canônico | Status |
|---|---|---|
| MX | LFPPI art. 245 mantém a **COF ≥ 30 dias antes** do contrato, com nulidade + perdas e danos em 1 ano. A reforma DOF de **03/04/2026** existe (transferência de tecnologia, patentes e marcas, em vigor em 04/04/2026; houve também um decreto de linguagem inclusiva no mesmo dia). O texto vigente usa "persona franquiciataria", e o **parágrafo da COF (2º) não tem marca de reforma**. O conteúdo da COF (investimento, retorno) está no art. 124 do Reglamento, que não foi reaberto. A conclusão do dossiê MX (a viabilidade vira insumo da COF) **se mantém** | **secundário** (mLey + Forvis Mazars/EY; DOF e Câmara inacessíveis daqui) |
| PY | Sem lei de franquia (confirmado também pela Câmara Paraguaia de Franquias via imprensa). **Lei 194/93:** o texto fala em representantes/distribuidores de **produtos** de firmas estrangeiras. Há fallback da Corte Suprema estendendo a lei a subsidiária controlada (levantamento do véu), mas **não achei decisão aplicando-a a franquia de serviço**. Risco real, não confirmado: exige parecer | **secundário / não verificado** |
| CO | Sem lei específica (contrato atípico; marca registrada na SIC; Decisão 291/486 da CAN) | **secundário** (dossiê; não reaberto) |
| PE | Sem lei específica | **secundário** (dossiê; não reaberto) |

### a.7 Proteção de dados (item 7)

| País | Canônico | Status |
|---|---|---|
| MX | Nova **LFPDPPP** publicada no DOF em 20/03/2025, **vigente desde 21/03/2025**; abrogou a de 2010; o INAI foi extinto e a autoridade passou à Secretaría Anticorrupción y Buen Gobierno | **secundário** (EY, Basham, síntese do DOF da SCJN; texto do DOF não aberto) |
| PY | **Lei 7593/2025**, promulgada em 27/11/2025. **Plena em ~nov/2027** (24 meses); regulamentação **ainda pendente** (o MITIC admitiu em mar/2026). Há divergência doutrinária sobre se já vige: tratar como **não exigível até a regulamentação** | **secundário** (Ferrere, ABC 20/03/2026, Última Hora 17/09/2026) |
| PE | **DS 016-2024-JUS**, publicado em 30/11/2024. Vigência geral de **29 a 31/03/2025** conforme a contagem (CMS: 120 dias corridos = 29/03; nota do MINJUSDH: 31/03); prazos escalonados para o Oficial de Dados | **secundário** |
| CO | **Lei 1581/2012** vigente. **Reforma não aprovada:** PL 214/2025 e 274/2025 acumulados na Câmara; novo PL Estatutário 282/2026 Câmara (ago/2026). Multas propostas de até 4.000-10.000 SMMLV ou 5 % da receita | **secundário** (MinCIT, Asuntos Legales 03/08/2026) |
| Regra específica de *scraping* / dado público de estabelecimento | **Não encontrada em nenhum dos 4 países.** As quatro leis protegem pessoa **natural/física**; dado de pessoa jurídica fica fora. O risco está na academia de **pessoa natural comerciante** (CO RUES; PE persona natural con negocio) e nos termos de uso de cada site | **não verificado** (nenhuma resolução da SIC/ANPD/autoridade MX/PY sobre *scraping* localizada) |

### a.8 Macro (item 8)

| País | Câmbio | Inflação 12 m | Juro de política | Status |
|---|---|---|---|---|
| CO | TRM **3.170,46** COP/USD (16/10/2026) | **6,29 %** (set/2026; 5,18 % em set/2025) — DANE, boletim de 07/10/2026: https://www.dane.gov.co/files/operaciones/IPC/sep2026/press-IPC-sep2026.pdf | **12,25 %** (alta de 25 pb em 30/09/2026, vigente desde 01/10/2026): https://www.banrep.gov.co/es/noticias | **verificado** (TRM via datos.gov.co `32sa-8pi3`) |
| MX | 18,3835 MXN/USD (BCE, 16/10/2026; o FIX do Banxico exige *token*) | **3,45 %** (set/2026; núcleo 3,75 %) — INEGI, boletim 619/26 de 08/10/2026: https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/inpc/inpc_2q2026_10.pdf | **6,50 %** (mantida em 24/09/2026, após cortes em 26/03 e 07/05; era 7,00 % em 05/02): https://www.banxico.org.mx/publicaciones-y-prensa/anuncios-de-las-decisiones-de-politica-monetaria/anuncios-politica-monetaria-t.html | **verificado** (câmbio = BCE, não Banxico) |
| PE | **3,379** PEN/USD (média interbancária de set/2026) | **4,55 %** IPC Lima (set/2026) | **4,25 %** (jun-out/2026) | **verificado** — API do BCRP `PN01273PM-PD04722MM-PN01207PM` |
| PY | **₲5.770,91/USD** e **₲1.136,45/BRL** (cruzado BRL/USD 5,0780), planilha de 16/10/2026: https://www.bcp.gov.py/webapps/web/cotizacion/monedas | 1,7 % (set/2026) | 5,50 % (sem mudança desde o corte de fev/2026) | câmbio **verificado**; IPC e TPM **secundário** (a home do BCP dá 403) |

---

## (b) Achados novos que mudam conclusões dos dossiês

1. **CO tem agregadores locais com escala (Fitpass CO 400+, Fitpal 600+ em 23 cidades).** Isso derruba a premissa F.1.6 do dossiê CO ("concorrência sem agregador → independentes invisíveis") e a recomendação transversal de que só OSM + site cobririam a camada 3. Próximo passo: ler robots e termos dos dois antes de coletar.
2. **No PE e no PY a ausência de agregador fica confirmada** (WellHub e TotalPass fora; Fitness Pass PE extinto). A camada 3 nesses países depende de OSM/Overture + sites de rede + cadastro tributário. O fator de cobertura tem de ser declarado, e o residual vai inflar ("não mapeado = livre").
3. **IVA de 19 % sobre a mensalidade na CO está confirmado** (Consejo de Estado 2020). Era o "risco #1 do DRE"; agora é premissa: receita líquida = 84,0 % do preço de lista, contra 86,2 % no MX, 84,7 % no PE e 90,9 % no PY.
4. **PE: o IGV de 2026 é 15,5 % + IPM 2,5 %** (Lei 32387). O total de 18 % não muda o DRE, mas qualquer rotina que separe IGV de IPM, ou que cite "16 %", está desatualizada.
5. **Tratados com o Brasil:** MX e PE **vigentes, com teto de 15 % e serviços técnicos tratados como royalty** (impede reclassificar a taxa de franquia como serviço para fugir da retenção). CO **aprovado no Congresso BR em set/2025, mas sem promulgação nem vigência confirmadas** (usar 20 % interno + IVA de 19 % autorretido). PY **sem tratado**.
6. **HFA e Mercado Fitness são a mesma série** para os países latinos. A penetração de CO (6,9 %), MX (5,6 %), PE (6 %) e AR (7,8 %) é comparável entre si. O "3 %" da CO é o ponto fora da série e deve virar só sensibilidade.
7. **Smart Fit PE = 95** em 30/06/2026 (não ~90-91). Os contadores dos sites mostram o *pipeline* até out/2026: CO 245, MX 526, PE 101, PY 19 (com pré-venda).
8. **Inconsistência interna da Smart Fit no MX:** 1.255 mil clientes ÷ população = ~0,96 %, contra 0,8 % na p. 34. Os "% membros/população" da apresentação não servem para derivar absolutos com precisão melhor que ±20 %.
9. **Colômbia, macro:** Banrep **subindo** (12,25 %) com IPC de 6,29 %. É o custo de capital mais alto dos quatro, e o único país com juro real de ~6 %.

---

## (c) Continua não verificado

- Relatório **HFA 2026** original (pago): metodologia por país e se a CO usa a mesma regra de contagem que MX/PE.
- **Mercado Fitness CO**: fonte primária do "3 % / 2.800 academias"; Radiografía PE em PDF.
- **Penetração PY**: inexistente em qualquer fonte.
- Termos de uso e robots de **Fitpass CO, Fitpal e TuPase**; status atual do TuPase no PY (o domínio não respondeu).
- **ICA Bogotá** para o CIIU 9311 (tarifa atual e na reforma de 2027, pendente de sanção).
- Texto vigente do **ET art. 408** (20 %) e do art. 240 (35 % + TMT 15 %); GMF; encargos trabalhistas da CO.
- **Convênio BR-CO:** decreto de promulgação, ratificação colombiana (lei + Corte Constitucional), data de vigência e teto sobre royalty.
- **PY INR:** % de renda presumida para royalty de marca/franquia (Lei 6380 e decreto regulamentar); IVA/IRE/IDU no texto oficial.
- **PE:** retenção interna de 30 % sobre royalty; tabela oficial da SUNAT da Lei 32387 (a página deu 403); prazo exato de vigência do DS 016-2024-JUS no texto.
- **MX:** texto do DOF de 03/04/2026 (LFPPI) e art. 124 do Reglamento; DOF da LFPDPPP; PTU/ISR reconferidos na fonte; FIX do Banxico (exige *token*).
- **PY:** IPC de set/2026 (1,7 %) e TPM (5,50 %) no comunicado do BCP; texto oficial da Lei 7593/2025.
- **Lei 194/93 (PY):** decisão que a aplique a franquia de serviços.
- Regra específica de *scraping* em qualquer dos 4 países.
- Clientes da Smart Fit por país em CO, PE e PY (só % agregado).

## Fontes adicionais consultadas
- Smart Fit, Apresentação Institucional set/2026 (texto extraído em `amostras/auditoria/smft_inst/inst.txt`, p. 34/97) e release 2T26 (`amostras/auditoria/smft_rel/rel.txt`, p. 7-8).
- Sites oficiais: wellhub.com (seletor de país em `/es-mx/`), totalpass.com, fitpass.com, fitpal.co, smartfit.com.{co,mx,pe,py}/gimnasios.
- Radiografía MX 2024 (`amostras/auditoria/mf_mx/mx.txt`, p. ~10-11).
- Planalto (Decretos 6.000/2006 e 7.020/2009); Câmara (DL 193/2025); Receita Federal (lista de acordos).
- Busca (secundário): Mercado Fitness set/2026; Pérez-Llorca e Crowe (ICA); RSM Peru (Lei 32387); Ferrere, ABC e Última Hora (PY); EY e Basham (MX); CMS, Cuatrecasas e MINJUSDH (PE); MinCIT e Asuntos Legales (CO); InfoNegocios e Montevideo Portal (TuPase); Infomercado (Fitness Pass).
