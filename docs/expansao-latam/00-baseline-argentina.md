# 00 — Baseline Argentina: contrato de dados, acoplamento remanescente e esforço real

- **Data:** 2026-10-16 · **Base:** `origin/main` em `a59b0e7` · **Status:** PESQUISA E PLANEJAMENTO. Nenhum código, dado ou config foi alterado.
- **Escopo:** a fotografia de partida para levar o Motor a Colômbia (CO), Paraguai (PY), México (MX) e Peru (PE).
- **Detalhe linha a linha:**
  - `anexos/fase0-a-acoplamento-e-contrato.md` traz o mapa de acoplamento com `arquivo:linha`, as contagens de grep e o contrato completo.
  - `anexos/fase0-b-receita-argentina.md` traz as fontes AR, a linha do tempo, os PRs e os 23 problemas, cada um com sua lição.
  - Este documento é a síntese. Quando ele e o anexo divergirem, vale o anexo, que traz a evidência.
- **Regra de leitura:** o `docs/plano_multipais.md` (2026-08-31) está **defasado**. Os Blocos A–E, o portal (BLK-INTL-13) e a cauda de correções de setembro e outubro já estão no código. Onde o plano e o código divergem, vale o **código**.

---

## 1. Cinco conclusões da Fase 0

1. **A arquitetura multi-país já existe e funciona.** O modelo é o da DEC-047: um binário, um container por país, país declarado em `perfil.json`.
   - O fio de alarme ("nenhum `if pais ==`") está verde. Na Fase 0 rodaram 237 testes de perfil e 65 de compose, portal e espelho.
   - O próximo país **não pede uma decisão de arquitetura nova**. Pede que a dívida que a Argentina deixou seja paga.
2. **O custo real da Argentina não foi a plataforma.**
   - A adaptação de plataforma (Blocos A–E) foi orçada em 5 semanas com 2 devs e executada em **~1,5 dia**, com Felipe e uma sessão de IA sobre uma spec executável de 913 linhas.
   - Os dois custos reais foram o **pipeline de dados** (~7 semanas, 1 pessoa: Juan) e a **cauda de correções** (11 PRs em ~4–5 semanas), quase toda do tipo *número errado que não dá erro*.
3. **O defeito dominante é semântico, não estrutural.** Alguns exemplos:
   - `pop_total` era a população do município no BR e a do hexágono na AR;
   - a renda em USD aparecia rotulada como "$" de peso;
   - um uplift brasileiro inflava a renda argentina em 63 %;
   - pisos em "alunos" estavam na escala brasileira.

   **Nenhum teste de presença ou tipo de coluna pega essa classe**, e o validador de pacote, que deveria pegar, **não existe**.
4. **A Argentina ainda tem 5 números ou vereditos errados em produção hoje**, todos conferidos no código (§3.1):
   - ficha do ponto reprovando toda praça por R$ 4.500;
   - zona morta em R$ 500 sobre renda em USD;
   - choropleth do front com faixas brasileiras;
   - renda em USD rotulada "R$";
   - metas SAM e residual na escala brasileira.

   Consertá-los custa ~3–5 dias e é **pré-requisito** de qualquer país novo, porque as mesmas peças morderiam CO, PY, MX e PE.
5. **Para um 3º país, falta um "kit de país" que hoje não existe.** São quatro peças:
   - contrato e validador de pacote **com checagens semânticas**;
   - exportador genérico com de-para declarativo (o atual é argentino, importa um módulo externo e **diverge** da cópia do Juan, que é provavelmente a que gera a produção);
   - réguas do funil completas no perfil;
   - infraestrutura parametrizada (hoje ~12–15 artefatos copiados à mão por país, metade em caminho CRÍTICO do guard).

---

## 2. Contrato de dados por camada

> O que cada camada **precisa receber**, em que **granularidade** e qual o **mínimo aceitável**. A coluna "Se faltar" é o comportamento **real** do código hoje. A leitura de colunas é defensiva (`carregar_uf` projeta `_COLS_DESEJADAS ∩ schema`), então coluna ausente **some sem erro**. O contrato existe para impedir isso.

### 2.0 Identidade (pré-requisito de tudo)

| Campo | Tipo / grão | Mínimo aceitável | Se faltar ou vier errado | AR |
|---|---|---|---|---|
| Partição `uf=XX` | dir, nível 1 administrativo | Sigla que case com `^[A-Za-z]{2}$` (`web/server/app.py:984`) | 400. Pasta vazia vira "estado fantasma" 404 | 24 siglas **fabricadas** pelo exportador |
| `hex_id` | str H3 **res 7** | Obrigatório | **Quebra** (sem mapa, sem merge de crescimento) | Derivado de `h3_id` |
| `lat`, `lng` | float, centroide | Obrigatório | Mapa e funil sem posição | `h3.cell_to_latlng` |
| `nome_municipio`/`cidade` | str, nível 2 | Um dos dois | Sem ranking por município | `nome_departamento` |
| `cod_municipio` | str, nível 2 | Obrigatório, **formato importa** | Renda domiciliar `None`, sem crescimento, sem malha. Join do crescimento usa `str[:6]` | 5 dígitos (não casa com o `cod6`) |

### 2.1 Camada 1 — Potencial socioeconômico

| Insumo | Unidade | Grão | Mínimo aceitável | Se faltar ou vier errado |
|---|---|---|---|---|
| `score_setor_2022_calibrado` | 0–100, **régua absoluta** nas âncoras do perfil (0,60·renda linear + 0,40·pop log) | hex7 | **Recomputado pela plataforma**, nunca herdado do pipeline | Ausente: funil vazio, sem erro. **Percentil com o mesmo nome:** corte 30 com outro significado (na AR, 12,9 % de quentes contra 5,5 % recomputado) |
| População (`populacao_corte_hex` > `pop_total_setor_2022` > `pop_total`) | habitantes **do hexágono** (ou captação hex + 6 vizinhos) | hex7 | Soma por país ≈ total do censo (±2 %) | Gate `_povoado` falso. **`pop_total` é falso amigo**: no BR é a população do município repetida por hex |
| Renda (`renda_per_capita_setor_2022_calibrada` > `renda_per_capita`) | moeda declarada em `moeda.indicadores_renda`, per capita, mês | hex7 | Moeda declarada e coerente com as âncoras | A origem decide a escala: a coluna setorial é dividida pelo `k`, a municipal pelo uplift. Sem carimbo de `k`, cai em `1.0239` (BR) **em silêncio** (só WARNING), salvo se o arquivo de fatores do país (`renda/fatores/<PAIS>/`, DEC-075) declarar `artefato_k_obrigatorio`, como o BR: aí a subida em produção falha. O da AR não declara |
| `faixa_oportunidade` | enum cru (`prioridade_maxima`/`alta`/…) | hex7 | Valores crus do vocabulário | Faixa ausente na ficha |
| Perfil | `reguas.renda_abs_min/max`, `pop_abs_min/max`, `score_corte_quente`, `pop_min_acionavel` (5.000) | — | Declarados e validados no boot | Boot fail-closed |

### 2.2 Camada 2 — Demanda não atendida (residual)

| Insumo | Unidade | Grão | Mínimo aceitável | Se faltar |
|---|---|---|---|---|
| `oferta_efetiva_disponivel` | **alunos** = max(SAM − oferta consumida, 0) | hex7 | Na escala da `capacidade_concorrente` do país | Camadas 2–5 vazias, sem erro |
| `sam_fitness_potencial` | alunos (pop × taxa de penetração) | hex7 | Taxa **embutida** no pacote (o `reguas.taxa_fitness` do perfil não é lido) | Card SAM "Não disponível" |
| `oferta_consumida_mercado_estimada` | alunos | hex7 | Obrigatório se a camada 3 for ligada | **"Não mapeado" vira "livre"**: camada 3 verdadeira para todos |
| `oferta_consumida_ultra_real` e afins | alunos/contagem | hex7 | 0 em país sem Ultra (greenfield) | NaN no hex saturado |
| `staging/hexagonos_mercado_mapeado.parquet` | `hex_id` + 4 colunas | hex7 | Presente se o Relatório Pontual for ligado | Relatório perde a página de residual, sem erro |
| Perfil | `oferta_destaque_min` (AR = 0,75 × 1.070 = 802,5) | — | Derivado da capacidade do país | Piso inalcançável: na AR, 398 de 434 municípios ficaram com as camadas vazias até o #323 |

### 2.3 Camada 3 — Pressão competitiva

| Insumo | Unidade | Grão | Mínimo aceitável | Se faltar |
|---|---|---|---|---|
| `staging/concorrentes_mapeados.parquet` (`rede, nome_unidade, lat, lng, hex_id_res7, status_registro, flag_coord_valida, foto`) | ponto | ponto | Lista geocodificada com `status_registro` e dedup entre fontes | Sem pins. Sem `status_registro`, a rota de 1 km dá 500 |
| `capacidade_default_concorrente_alunos` | alunos/academia | hex7 | **Calibrada no país** (AR 1.070 contra BR 2.500) | Cai no perfil e, em `pressao_1km`, no **2.500 literal** |
| `n_concorrentes_influencia_1km` | contagem | hex7 | Opcional (modelo de 1 km) | Ramo antigo `consumo/capacidade`. Depende de um arquivo com nome brasileiro (`hexagonos_brasil_dashboard.parquet`) |
| Literais | `CONC_ADENSAR_MAX = 2`, `CONSUMO_1KM_CORTES = [625, 1250, 2500, 5000]` | — | Hoje **não** estão no perfil | Legendas e cortes em escala BR |

### 2.4 Camada 4 — Momentum

| Insumo | Unidade | Grão | Mínimo aceitável | Se faltar |
|---|---|---|---|---|
| `staging/crescimento_municipal.parquet` (`cod6`, `cres_tendencia`, `cres_emp_pct`, `cres_saldo_empresas`, `cres_confiab`, …) | misto | município | **Chave casável**: hoje `cod_municipio.str[:6]` contra `cod6.zfill(6)` | Passo 4 vazio, sem erro. **Código de 5 dígitos (DANE, INEGI) nunca casa.** UBIGEO (6) casa por acaso |
| `staging/crescimento_hex.parquet` (`hex_id`, `cres_hex_taxa`, `cres_hex_classe`) | taxa e classe | hex7 | Opcional | Passo 4 sem cor |
| Camadas de leitura próprias | — | nível 2 | Opcional | Exigem editar `app.py` (`_CAMADAS_AR` é schema de **um** país compilado na plataforma) |

**Na AR:** nenhum dos dois artefatos-padrão foi entregue. As 12 colunas de leitura (OEDE, IGJ, permisos, SUBE) ficaram **fora do score**.

### 2.5 Camada 5 — Fila de prioridade

Desde a DEC-077, esta é a fila da instância SEM régua da recomendação única (`_passo5_legado` em `web/server/app.py`, travado para a AR por `tests/unit/test_piloto_web_recomendacao_legado_ar.py`). Com régua (`src/motor_expansao/recomendacao/regra/<PAIS>/`, hoje só o BR), o passo 5 é o Top 10 único (5 Mata Virgem + 5 Premium), com réguas próprias na escala BR (renda domiciliar ≥ R$ 4.500, residual ≥ 2.000 alunos, score ≥ 50, população ≥ 10 mil).

| Insumo | Fórmula | Mínimo aceitável | Se faltar ou vier fora de escala |
|---|---|---|---|
| Nota socio (`score_setor_2022_calibrado`) + nota demanda (`oferta_efetiva_disponivel`) + `n_concorrentes_est` | `0,70·socio + 0,30·nota_dem`, com `nota_dem` em log entre **2.000 e 20.000 alunos** (`praca_indice.py:45-58`) | Âncoras de demanda **na escala do país** (hoje literais) | Índice NaN e fila vazia. Com residual em escala ~0,4× (AR), `nota_dem = 0` entre 802 e 2.000 alunos e a fila vira "só socio", **em silêncio** |

### 2.6 Módulos laterais

| Módulo | Insumo mínimo | Grão | Ponto crítico |
|---|---|---|---|
| **Ficha do ponto + Relatório Pontual** | Malha nível 2 em GeoJSON. Setores com `geometry_wkb`, `pop_total_setor_2022`, `domicilios_particulares_ocupados_setor_2022`, `renda_per_capita_setor_2022_calibrada`, `avg_moradores_domicilio_setor_2022`, **`renda_responsavel_media_setor_2022`**, `bbox_*`, `nome_bairro` | **Unidade censitária com geometria** | A renda domiciliar é `V06004 × uplift × fator temporal`, o contrato **mais brasileiro** do sistema. A AR o imitou fabricando `renda × moradores` com uplift 1,0. **Hoje ainda reprova por `RENDA_MIN` R$ 4.500 e pela zona morta em R$ 500** |
| **Relatório Municipal** | Mesmos setores + bairro/distrito | setor | "Censo 2022" e "CAGED/RAIS" fixos no texto |
| **Viabilidade** | `base_calibracao_maduras` (curva m² → alunos da rede **Ultra BR**) + câmbios + aviso; desde a DEC-078, também o "modelo de praça" (`dimensionamento/v2_coeficientes.json`, OLS do faturamento de unidades **Ultra BR** sobre a isócrona de 10 min do Valhalla) e a rampa padrão pela curva observada da rede **Ultra BR** | ponto | **O motor não lê o perfil.** A sugestão do modelo de praça só existe com `MOTOR_ROTAS_URL` (ausente no compose AR) e não tem gate de país. Lucro Presumido, PIS/COFINS/ISS, folha, CAPEX e réguas de veredito são BR. Golden de Londrina sem eixo de país |
| **Oportunidades imobiliárias** | `oportunidades/viaveis.parquet` (31 colunas, coletor externo de portais BR) | ponto | Coletor só para o BR. R$ e IPTU no front |
| **M&A / vulnerabilidade** | Snapshots semanais de agregadores (WellHub/TotalPass) | ponto | Vocabulário fechado de fontes. Não existe fora do BR |

### 2.7 O que o `perfil.json` precisa declarar

**Já lido pelo loader (schema v1):**

| Bloco | Campos |
|---|---|
| Identificação | `pais`, `nome`, `locale` |
| `moeda` | `codigo`, `simbolo`, `indicadores_renda`, `cambio_base`, `cambio_viabilidade`, `base_monetaria` |
| `bbox` | os quatro limites |
| `vista_padrao` | `lat`, `lng`, `zoom` |
| `geocode` | `countrycodes`, `idioma`, `regex_cp` |
| `fontes` | `censo`, `crescimento` |
| `reguas` | âncoras, corte quente, piso de população, `oferta_destaque_min`, capacidades, uplift, moradores, 7 metas, faixas de renda e densidade, `pin_margem_m` |
| `superficies` | lista de abas ligadas |
| `malha_municipal_disponivel` | bool |
| `avisos` | avisos carimbados |
| `operacao.pdf_concorrencia_max` | teto de PDFs simultâneos |

**Campos MORTOS** (declarados e sem leitor, que enganam quem edita o perfil): `score_pesos`, `taxa_fitness`, `separador_milhar`/`separador_decimal`, `capacidade_concorrente_unidade`, `faixas_mapa_*`, `mem_limit_alvo`, `basemap_labels_url_obrigatoria`.

**Campos AUSENTES** (deveriam existir):
- `renda_min_ficha` (hoje `RENDA_MIN` R$ 4.500);
- `renda_zona_morta_min` e `pop_zona_morta_min`;
- `demanda_min_alunos`/`demanda_max_alunos`, `peso_socio`/`peso_demanda`;
- `conc_adensar_max`, `crit_ponto_score_min`/`crit_ponto_conc_max`;
- cortes de consumo de 1 km;
- `ano_censo` e sigla do instituto;
- vocabulário do nível 1/2, bandeira e regime tributário.

---

## 3. Acoplamento ao país que ainda existe no código

### 3.1 Já morde a Argentina em produção (consertar antes de qualquer país novo)

| # | Defeito | Onde | Esforço |
|---|---|---|---|
| S1 | Critério de renda da ficha do ponto em **R$ 4.500** e rótulo "R$" sobre renda em USD: reprova toda praça | `web/server/app.py:6478-6481`, `:6808`; `config.py:62` | P |
| S2 | Zona morta: `RENDA_ZONA_MORTA_MIN = 500` R$ sobre renda per capita em USD (mediana ~US$ 478). Alimenta o selo DEMOGRÁFICO do PDF. **Inferido, não medido na base AR** | `dimensionamento/viabilidade_ponto.py:72`, `:542` | P–M |
| S3 | Choropleth de setores no front com faixas BR. O backend serve em `/api/me` as faixas de densidade e as de renda PER CAPITA do perfil, e ninguém as lê; desde o #473 (E1 da DEC-075) o calor de renda pinta a renda DOMICILIAR, cujas faixas do perfil o `/api/me` não serve | `web/src/lib/colors.ts:358-377` | M |
| S4 | Renda USD rotulada "R$" (ponto, detalhe da região, recomendação) e "$" de peso sobre USD | `PontoScreen.tsx:645`, `DetalheRegiao.tsx:67`, `format.ts:169`, … | M |
| S8 | Metas SAM/residual da AR = 2.000 (escala BR de alunos): cards vermelhos por construção | `data/perfis/AR/perfil.json` | P (dado) |

### 3.2 Quebra ou degrada em silêncio num 3º país

| # | Ponto | Afeta | Esforço |
|---|---|---|---|
| Q1 | **Validador e contrato de pacote inexistentes** (o plano diz "inaceitável rodar o segundo país sem ele") | todos | G (3–5 d) |
| Q2 | Exportador por país, com `import nacional_academia` externo e siglas fabricadas. **Duas cópias divergentes** (a da plataforma não tem as 14 colunas de camadas da do Juan) | todos | G |
| Q3 | `_UF_RE = ^[A-Za-z]{2}$`: códigos DANE, INEGI e UBIGEO são numéricos | todos | P–M (CRÍTICO: é sink anti-traversal) |
| Q4 | Infra copiada à mão (compose, Caddy, Authelia, portal com `$br/$ar`, healthcheck com `EDGE_URL` escalar, teste de compose literal; matchers N² no portal) | cada país | M por país, ou G uma vez |
| Q5 | **Tetos** de memória declarados já somam ~16 GB na VPS. É teto, não consumo: o RSS medido da AR foi 108 MiB contra 2 GB de teto | 3º país | decisão de infra |
| Q6 | API GeoEspacial e bot só BR (`api/geo.py` com `region:"br"`, `_UFS` do bot com 27 UFs) | se pedido | G |
| Q7 | Banco de usuários (DEC-067/069) sem dimensão de país; a AR segue no Authelia, com **dois cadastros** | cada país | decisão |
| S5 | `mascara.ts` com gramática pt-BR fixa: em es-MX e es-PE (`1,500.00`) o valor digitado sai **errado sem erro** | **MX, PE** | M |
| S6 | Join do crescimento por `cod6` IBGE | CO, MX (5 dígitos) | P |
| S7 | Âncoras e pesos da camada 5, `CONC_ADENSAR_MAX`, `CRIT_PONTO_*` literais | quando `oportunidades` ligar | P–M |
| S10 | Fallbacks BR escondidos: `k = 1.0239`, `fillna(2_500)`, `TAXA_FITNESS_FALLBACK = 0,10` (o `FATOR_TEMPORAL = 1,0` rotulado "julho/2022 (Censo IBGE)" deixou de ser fallback com a DEC-075: país sem `renda/fatores/<PAIS>/` não sobe; na AR, fator e rótulo estão declarados no arquivo dela) | pacote incompleto | P cada |
| S12 | **Viabilidade inteira em regime e moeda BR.** Furos fora de `Premissas` (`aluguel_teto_clusters`, `flag_viavel`, payload, XLSX). Trocar alíquota é parâmetro; **trocar regime (IVA/IGV/ICA/ISR/PTU) é código** | todos | GG: 2–4 semanas de eng. uma vez + 3–6 semanas humanas por país |
| C1–C9 | Cosméticos: "IBGE/Censo 2022/CAGED" em PDFs e metodologia; vocabulário "estado/UF"; bandeira só BR+AR; sem i18n (1,5–2,5 mil strings no front + 453 nos PDFs); mapas sem rótulo de rua fora do BR | todos | P a GG (i18n) |

Legenda de esforço para 1 dev: **P** < 0,5 dia · **M** 0,5–2 dias · **G** 3–10 dias · **GG** > 2 semanas.

---

## 4. A receita da Argentina

### 4.1 Fontes que substituíram as brasileiras

| Camada | Brasil | Argentina | Natureza |
|---|---|---|---|
| Censo / população | IBGE 2022 por setor | **INDEC 2022 por radio censal** (66.502 radios), via GeoParquet do pacote `censoargentino`, porque o REDATAM travava e o download do INDEC foi suspenso | medido |
| Malha H3 | `base_h3_brasil.py` (fração de terra ≥ 0,05; 1,54 M hex) | Interseção radio × hex com área ponderada, **corte ≥ 3 hab/km²** → **42.388 hex** (98,1 % da população). **15.186 exportados** ao piloto | medido |
| Renda | Censo (renda do responsável) × uplift × fator temporal | **MODELADA**: EPH 2025 → `log(IPCF) ~ educação + posse do domicílio + tamanho + aglomerado`, raking por região, aplicada ao radio. ±15 % na mediana, **85 % dos hex com confiança baixa**, distribuição comprimida (p95/p05 = 2,2 contra 6,4 no BR). Servida em **USD** | medido no repo do Juan |
| Malha adm2 | IBGE | georef/IGN, 529 departamentos (chegou por último) | medido |
| Concorrentes | GymScraping (90 coletores) + agregadores | 9 fontes web (WellHub = 68 % da camada web + 8 redes) + OSM, com dedup < 150 m. Capacidade **calibrada 1.070** alunos (fator de cobertura 2,675). Coleta semanal **no laptop do Juan** | medido |
| Penetração | `taxa_fitness` calibrada (17,35 %, DEC-060) | **0,078 constante** (Radiografía del Fitness 2024). A taxa OSM calibrada (0,35) foi descartada | medido |
| Crescimento | CAGED/RAIS/Receita | OEDE, IGJ, permisos, SUBE; VIIRS reprovada no backtest (+0,003 AUC). **Nada entra no score** | medido |
| Tiles | tileserver próprio | CARTO global, **sem rótulos de rua** (aceito por escrito) | medido |

### 4.2 O que foi adaptado na plataforma (reaproveitável)

- **Configuração do país:**
  - `perfil.json` com loader fail-closed;
  - âncoras, réguas, faixas e metas como parâmetro;
  - bbox e geocoder unificados e validados.
- **Moeda e textos:**
  - moeda do indicador de renda separada da moeda do país;
  - vazamentos de "Brasil"/"IBGE" removidos.
- **Superfícies e acesso:**
  - gate de superfície por país (404 com motivo);
  - aviso de tributo provisório carimbado no PDF e no XLSX;
  - `pdf_concorrencia_max` por instância;
  - grupos Authelia por país.
- **Infraestrutura:** compose AR, Caddy, portal de seleção de país.
- **Guardas:** fio de alarme e guarda anti-moeda.

Detalhe no anexo B, §2.

### 4.3 O que ficou de fora ou provisório

- **Superfícies:**
  - superfícies ligadas: `mapa` e `viabilidade`;
  - **o funil municipal está no ar** via `/api/municipio`, sob a aba `mapa`, ao contrário do que o plano dizia;
  - continuam bloqueados o Modo 3, a imobiliária e a executiva.
- **Viabilidade:** usa tributo BR (BLK-INTL-11 não iniciado).
- **Mapa e idioma:**
  - mapas sem rótulo de rua;
  - interface só em português, por decisão D4 do dono.
- **Peças da plataforma ainda pendentes:**
  - contrato e validador;
  - cache orçado em bytes;
  - `_UF_RE`;
  - operação em matriz.
- **Usuários:** a AR segue no Authelia, com dois cadastros.
- **Coleta semanal de concorrentes:** **sem rastro na VPS** (provavelmente ainda no laptop do Juan; *não verificado*).

---

## 5. Esforço real: o baseline de estimativa

### 5.1 Linha do tempo

| Marco | Data | Intervalo |
|---|---|---|
| Juan começa os downloads (OSM, georef, radios, EPH) | ≤ 2026-07-07 | — |
| Pacote AR no layout do piloto | 2026-08-24 | **~7 semanas de pipeline** (1 pessoa + IA; 95 commits, ~35–45 mil linhas de Python *estimado*) |
| DEC-047 + plano + specs + perfis | 2026-08-31 → 09-02 | ~3 dias de spec |
| Blocos A → E executados | 2026-09-02 13:59 → 09-03 19:30 | **~1,5 dia** (29 commits, uma sessão de IA) |
| **Argentina no ar** | **2026-09-03** | 3 dias após a DEC-047 |
| Cauda de correções | 2026-09-08 → 10-06 | **~4 semanas, 11 PRs** |
| **Total multi-país na plataforma** | — | **41 PRs, +20.842/−1.416 linhas**, 2 autores + Vinicius como coautor |

### 5.2 Plano × real

| Item | Planejado | Real | Leitura |
|---|---|---|---|
| Plataforma (A–E) | 5 semanas, 2 devs (6–8 com 1) | ~1,5 dia | **Não transferível sem spec executável equivalente.** A velocidade veio de spec numerada + IA |
| Pipeline de país | não orçado | ~7 semanas | O custo dominante |
| Cauda pós-subida | não orçada | ~4 semanas | Custo dominante nº 2, quase tudo número errado silencioso |

### 5.3 Baseline por país (para escalar a CO, PY, MX e PE)

| Componente | Referência AR | Baseline por país (estimativa) | Natureza |
|---|---|---|---|
| Pipeline de dados (censo fino → H3 → renda modelada → concorrentes → mercado) | ~7 semanas, 1 pessoa | **5–9 semanas** × fator de complexidade do país (Fase 2) | estimativa |
| Malha adm2 na convenção | dias | 1–3 dias se pública | estimativa |
| Perfil + decisões de régua (P1–P9) + arquivo de fatores de renda do país (`src/motor_expansao/renda/fatores/<PAIS>/`, obrigatório desde a DEC-075: sem ele a instância não sobe) | ~3 dias, gargalo = decisão do dono | 2–4 dias | estimativa |
| Exportador / de-para | 1.100 linhas | 2–5 dias (cai para ~1 dia com exportador genérico) | estimativa |
| Infra (DNS, compose, Caddy, grupo, cadastro, medição) | ~1 dia | 1 dia + 24 h de observação | medido na AR |
| **Cauda de correções** | ~4 semanas | **2–4 semanas** de atenção intermitente (cai com o validador semântico) | estimativa |
| Premissas financeiras locais (viabilidade sem carimbo) | não feito | 3–6 semanas humanas (assessor fiscal) | estimativa do plano |
| Coleta recorrente de concorrentes | laptop do Juan | 1–2 semanas para montar + custo recorrente | estimativa |

**Plataforma devida uma vez, antes do 3º país** (*estimativa*, no ritmo da AR com spec + IA):
- **Correções:** S1–S4/S8 (3–5 d).
- **Kit de país:**
  - validador semântico + contrato (3–5 d);
  - exportador genérico com de-para (3–5 d);
  - `_UF_RE` (0,5–1 d);
  - `mascara.ts` (0,5 d);
  - réguas do funil no perfil (1–2 d).
- **Operação:**
  - operação em matriz e infra parametrizada (3–5 d);
  - cache em bytes + baseline de desempenho (3–5 d).
- **Viabilidade:** motor de premissas multi-regime, BLK-INTL-11 (2–4 semanas).

---

## 6. Premissas frágeis: onde a analogia BR → AR quebrou

1. **Renda medida × modelada.** Nos 4 países a renda também será **modelada** por pesquisa domiciliar (GEIH, EPHC, ENIGH, ENAHO) ou por proxy. A âncora é decisão, não transcrição.
2. **Percentil × absoluto.** Essa escolha moveu o ranking **10× mais** que qualquer âncora (correlação 0,46). Sempre recomputar na régua da plataforma.
3. **Toda régua em "alunos" é de país**: capacidade, penetração, pisos, âncoras de demanda e metas.
4. **Definição censitária muda o denominador.** Na AR, `viviendas` não equivale a `hogares` (moradores 2,5654 contra 2,8623).
5. **Geografia administrativa.**
   - Na AR, as comunas pequenas exigiram margem de pins zero e foram fabricadas siglas de 2 letras.
   - CO (departamento/município), MX (estado/municipio/AGEB), PE (departamento/provincia/distrito) e PY (departamento/distrito) têm hierarquias e códigos diferentes.
   - A "UF" da plataforma é sempre o nível 1.
6. **Concorrência é custo recorrente**, não entrega única.
   - Na AR, o WellHub estrangulou a coleta: com 12 threads, perdeu 2.289 de 2.366 fichas.
   - A coleta ficou 36 dias parada sem ninguém ver.
7. **Escopo do dia 1 é volátil.** O plano foi reescrito duas vezes em 3 dias. O que precisa ser firme é o **mecanismo** (gate de superfície + validador), não a lista.
8. **O risco de host é CPU, não RAM.** São 4 vCPU compartilhados, e o semáforo de PDF é por processo. A coleta recorrente de cada país disputa a mesma CPU.
9. **Nenhum dos 4 países tem unidade Ultra.** Na AR também não há: a camada Ultra entra zerada por construção, e a viabilidade usa a curva m² → alunos da rede **brasileira**. Isso continua sendo a premissa mais frágil de toda a viabilidade fora do BR (ver `02-matriz-viabilidade.md` §validação).

---

## 7. Não verificado nesta fase

- Conteúdo real da VPS AR:
  - se há `hexagonos_brasil_dashboard.parquet`, crescimento ou camada de 1 km lá;
  - qual exportador gerou a base no ar.
- Taxa real de disparo da zona morta e do critério de renda na base AR. Foi inferida do código e dos quantis, não medida.
- Regras reais do Authelia e do Caddyfile (arquivos cifrados ou gitignored).
- `HANDOFF.md` e `dicionario_dados.md` integrais do pacote do Juan, horas-pessoa e cadência real da coleta AR.
- Observação de 24 h de RSS/p95 após a subida da AR.
