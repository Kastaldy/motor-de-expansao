# 01 — Consolidação e auditoria dos dossiês

- **Data:** 2026-10-16 · **Base:**
  - os 5 dossiês de campo (`01-dossie-CO.md`, `-MX`, `-PE`, `-PY`, `-transversal`);
  - duas auditorias cruzadas, com detalhe e URLs em `anexos/auditoria-mercado-tributos.md` e `anexos/auditoria-dados.md`.
- **Regra:** onde um dossiê e a auditoria divergem, vale este documento. Status: **verificado** (fonte primária aberta), **secundário** (imprensa, escritório ou compilação), **não verificado**, **medido** (calculado nesta pesquisa).

---

## 1. Valores canônicos, depois da auditoria

### 1.1 Mercado

| Item | CO | MX | PE | PY | Status / fonte |
|---|---|---|---|---|---|
| **Smart Fit, unidades abertas** (30/06/2026) | **232** | **488** | **95** (o dossiê dizia ~91) | **19** (site; o RI não abre o PY) | verificado: Apresentação Institucional Smart Fit set/2026, p. 34; release 2T26 |
| Smart Fit, contador do site (out/2026, com pré-venda) | 245 | 526 | 101 | 19 | verificado; serve de **pipeline futuro** (§5 da matriz) |
| Smart Fit por milhão de habitantes | 4,3 | 3,7 | 2,8 | 3,1 | medido |
| Clientes Smart Fit por unidade | ~2.990 (est.) | **~2.570** | ~2.900 (est.) | — | MX verificado; CO/PE ±20 % |
| **WellHub / TotalPass** | **não operam** | **operam os dois** | não operam | não operam | verificado nos sites oficiais |
| **Agregador local** | **Fitpass CO (400+ centros) e Fitpal (600+, 23 cidades)**, que o dossiê CO não viu | Fitpass MX | nenhum (Fitness Pass extinto) | TuPase (corporativo; secundário) | verificado (sites); termos **não lidos** |
| **Penetração** (série única HFA = Radiografía Mercado Fitness) | **6,9 %** (sensibilidade obrigatória em 3 %) | **5,6 %** (faixa 4–6 %) | **6 %** (faixa 4–6 %) | **3–5 %: decisão, não dado** | HFA e Mercado Fitness **são a mesma série**, não duas fontes |
| Sócios por instalação (régua de mercado) | ~453 | ~349 | ~522 | ? | contra BR 2.500 e AR 1.070 calibrado; **capacidade é parâmetro de país** |
| Ticket low-cost de referência (Smart Fit, plano básico/Smart) | COP 89.900 ≈ US$ 28 ≈ Int$ 54 | MXN 399 ≈ US$ 21,7 ≈ Int$ 35 | S/ 89,90 ≈ US$ 26,6 ≈ Int$ 47 | ₲ 169–229 mil ≈ US$ 29–40 | verificado (sites) |

### 1.2 Tributos e acordos

| Item | CO | MX | PE | PY | Status |
|---|---|---|---|---|---|
| **Imposto indireto sobre a mensalidade** | **IVA 19 %** (Consejo de Estado, 07/05/2020; isenção só para CAPF com encaminhamento de saúde) | IVA 16 %, sem isenção | IGV 18 % (2026: 15,5 % + IPM 2,5 %, Lei 32387) | IVA 10 % | CO **verificado**; demais secundário |
| Receita líquida / preço de lista | 84,0 % | 86,2 % | 84,7 % | 90,9 % | medido |
| Renda das empresas | 35 % + tributação mínima de 15 % | ISR 30 % + PTU 10 % (≈ 37 %) | 29,5 % (RMT 10 % no 1º tramo) | IRE 10 % + IDU 8/15 % | secundário |
| **Acordo de bitributação com o Brasil** | assinado em 2022, aprovado pelo Congresso BR (DL 193/2025), **sem promulgação**: tratar como não vigente → retenção **20 %** + IVA 19 % autorretido | **em vigor**, teto de 15 % (serviço técnico = royalty) | **em vigor**, teto de 15 % | **não há** (INR 15 % × % presumido: usar 15 %) | MX e PE **verificados** (Planalto) |
| Macro (set–out/2026) | IPC 6,29 %; juro 12,25 %; TRM 3.170 | IPC 3,45 %; juro 6,50 %; 18,38/USD | IPC Lima 4,55 %; juro 4,25 %; 3,379/USD | IPC 1,7 %; juro 5,50 %; ₲ 5.771/USD | CO, MX e PE verificados; PY: câmbio verificado, resto secundário |

### 1.3 Regulação

| Item | CO | MX | PE | PY |
|---|---|---|---|---|
| Franquia | sem lei específica; registrar a marca na SIC | **COF (LFPPI art. 245) ≥ 30 dias antes, com investimento e retorno**; a reforma de 03/04/2026 **não** tocou esse parágrafo | sem lei específica | sem lei; **Lei 194/93** (rescisão de distribuidor de produto estrangeiro) **pode** alcançar franquia: parecer necessário |
| Dados pessoais | Lei 1581/2012 (reforma não aprovada) | nova LFPDPPP, vigente desde 21/03/2025 | DS 016-2024-JUS, vigente desde mar/2025 (representante local para estrangeiro) | Lei 7593/2025, plena em ~nov/2027 |
| Regra específica de scraping | nenhuma encontrada nos 4. O risco está nos **termos de uso** e no dado de **pessoa natural** (RUES na CO) | | | |
| Imobiliário (coleta automatizada) | Ciencuadras **proíbe** por escrito; Finca Raíz bloqueia | 4 portais 403/401; LFDA art. 114 Bis (contornar medida técnica) | Cloudflare (403) | InfoCasas acessível; termos **não lidos** |

### 1.4 Dados

| Item | Resolução da auditoria |
|---|---|
| **Relative Wealth Index (Meta)** | **CC BY-NC 4.0: uso comercial proibido** (campo `license_other` do HDX). **Sai do pipeline do PY.** Substituto: Mapa de Pobreza Monetária INE + Banco Mundial (263 distritos + **67 barrios de Asunción**, a única verdade de chão intraurbana pública) + altura e área construída do Google Open Buildings 2.5D (CC BY) e GHSL BUILT-C/H, **validados nos 67 barrios** antes de ir para Central/CDE |
| **Cobertura do OSM** | **~9 %** do parque onde há denominador oficial (MX 2.734/30.242; PE 346/4.026; CO 742/7.940), **e não os 20 % da régua AR**. O fator de cobertura é por país e declarado |
| **Overture Places** (`gym`) | MX 31.044 · CO 4.660 · PE 3.415 · PY 1.219, de 5 a 11 vezes o OSM. **Sem porte, preço ou data, com duplicatas prováveis**; é piso em CO, PE e PY (filtro por endereço) |
| **Universo do gate de população** | o transversal contou população **do hexágono** ≥ 5.000. O funil corta pela **captação** (hex + 6 vizinhos). Universo acionável real: **CO ~7,4 mil · MX ~22,5 mil · PE ~4,9 mil · PY ~1,0 mil** hex. Servidos (teto exportado): CO ~13,3 mil · MX ~41,4 mil · PE ~11,8 mil · PY ~2,5 mil |
| **PE: Censo 2025** | o **REDATAM distrital 2025 existe** (o dossiê disse que não): as covariáveis do modelo de renda passam a ser de 2025. **Manzana e geometria de manzana continuam indisponíveis.** Omissão censitária de 4,25 % (1,45 M) |
| **CO: CENU 2024** | microdados **não publicados**, e o acesso futuro previsto é só para pesquisa. **Não resolve** a concorrência independente. O MGN 2018 já traz estrato em todas as 504.996 manzanas |
| **MX: IMSS → INEGI** | catálogo oficial com entidade + nome, sem `CVE_MUN`: join por nome cobre ~96 %. **Deixa de ser bloqueio** |
| **MX: DENUE** | incorporou a varredura dos Censos Económicos 2024, então o risco de "micro fechada que persiste" fica limitado a fechamentos pós-2024. Tem 11× o OSM |
| **MX: NSE AMAI** | grátis até AGEB ≠ licença comercial. **Só validação interna**; o IMU CONAPO (CC BY) cumpre a função sem risco |
| PY: câmbio | a média anual de 2025 (7.545) erra ~30 % contra o câmbio do mês (5.771): **usar a série mensal do mês-base** |

---

## 2. Veredito final de dados por camada (depois da auditoria)

Legenda: **C** = Completa · **P** = Parcial com proxy · **P−** = Parcial com proxy fraco · **I** = Inviável no curto prazo.

| Camada | CO | MX | PE | PY |
|---|---|---|---|---|
| Identidade / malha | C (DIVIPOLA 5 dígitos, 33 nível 1) | C (CVEGEO 5; AGEB alfanumérica) | C (UBIGEO 6, casa nativamente) | C (4 dígitos; EPSG:4674 nativo) |
| 1 Potencial: população | P (2018 reescalado ×1,21, não uniforme) | **C** (2020 manzana/AGEB + EIC 2025) | P (manzana 2017 → distrito 2025) | P− (distrito; barrio só em Asunción) |
| 1 Potencial: renda | P (modelada por **estrato observado** na manzana) | P (modelada, **calibrada em renda medida no município**) | P (ENAHO + REDATAM 2025 distrital; **validável** pelos Planos Estratificados) | P− (SAE distrital + proxy de prédios; validável só em Asunción) |
| 2 Residual | P (penetração 6,9 % × 3 %; capacidade ~453) | P (penetração 5,6 %; capacidade **por porte DENUE**) | P (6 %; capacidade ~522) | P− (penetração por decisão) |
| 3 Pressão | **P (melhorou: Fitpass/Fitpal + Smart Fit + OSM + Overture)** | **C** (DENUE + WellHub + TotalPass + redes) | P (sem agregador; OSM + Overture + sites) | P− (Smart Fit 19 exatos; independentes fracos) |
| 4 Momentum | P (ELIC, CEED, RUES agregado; grão municipal) | P (IMSS + DENUE + 2020→2025) | P (intercensal 2017→2025 real + RENAMU + RUC) | P− (só demografia; Open Buildings Δ como opção) |
| 5 Fila | P (herda 1 e 2) | P | P | P− |
| Relatório Pontual | **C** em geometria (manzana) / P em renda | C em geometria (AGEB) / P em renda | P (geometria de manzana sem download) | P− (barrio em Asunción; pseudossetor fora) |
| Viabilidade | P (IVA 19 % confirmado; ICA municipal aberto) | P (**COF: exige premissa MX assinada**) | P (IGV com crédito; aluguel em USD) | P (tributos simples; INR a confirmar) |
| Imobiliário | I (termos e bloqueio) | I (403/401; LFDA) | I (Cloudflare) | P (InfoCasas, se os termos permitirem) |
| M&A / agregadores | P (Fitpass/Fitpal: snapshot possível) | **C** (cadeia BR reaproveitável) | I | I |

---

## 3. O que continua NÃO verificado (consolidado)

Por impacto na decisão, do maior para o menor:

1. **Penetração no PY.** Não existe em fonte alguma: será decisão.
2. **Termos de uso e robots de Fitpass CO e Fitpal.** É deles que depende a melhora da camada 3 CO.
3. **Geometria de manzana no PE** (2017 baixável e 2025), via INEI pela Lei 27806 ou SIGRID de outra rede. Junto, o **calendário de manzana/microdados do Censo 2025** e se os totais distritais incluem os 1,45 M omitidos.
4. **PY: renda e população intraurbanas.**
   - Download e formato do **Mapa de Pobreza SAE**.
   - Resposta do INE a pedido de NSE por segmento ou de população por barrio.
   - Valores fiscais de Asunción em camada geográfica.
5. **Tributos ainda em aberto:**
   - **ICA Bogotá** para o CIIU 9311;
   - vigência do **tratado BR–CO**;
   - **% presumido do INR** sobre royalty no PY;
   - textos oficiais de ISR/PTU (MX), IR 35 % e TMT (CO) e da Lei 32387 (PE);
   - encargos trabalhistas dos 4 países.
6. **Lei 194/93 aplicada a franquia de serviço (PY).**
7. **MX:**
   - renda do trabalho na Encuesta Intercensal 2025;
   - termos do NSE AMAI;
   - significado dos 88 códigos IMSS "NA";
   - contagem 713943 nos Censos Económicos 2024.
8. **CO:**
   - campo e licença de estrato nos shapes de Bogotá e Medellín;
   - cronograma oficial do censo 2030;
   - IPM por manzana (geovisor inacessível);
   - emprego formal municipal (PILA/FILCO).
9. **Aluguel comercial por m²** em CO, MX e PE: nenhuma fonte com data. No PY há amostra do InfoCasas (~US$ 3,8–4,5/m²/mês), com pareamento inferido.
10. **Contagens de concorrentes:** Bodytech/Athletic (CO), Sportlife/b2 (PE), BIGG/EXEN (PY), Fitness 24/7 e Energy (MX), todos com dado antigo ou ausente.
11. **Licenças periféricas:**
    - VIIRS V2.2 (EOG: ambígua);
    - Kontur (declara CC BY, mas funde OSM, que é ODbL).
12. **Rede:** três hosts do governo colombiano e o Overpass público recusaram conexão deste ambiente. Os pipelines podem precisar de outra rede.
