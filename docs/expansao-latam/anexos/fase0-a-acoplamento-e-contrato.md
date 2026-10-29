# Fase 0 (parte A) — Acoplamento a país no código atual e contrato de dados por camada

- **Data:** 2026-10-16 · **Base:** worktree `trabalho-main` em `a59b0e7` (sincronizada com `origin/main`) · **Modo:** somente leitura, nenhum arquivo do repositório alterado.
- **Escopo:** levar o Motor de Expansão para Colômbia, Paraguai, México e Peru. Brasil e Argentina já estão no ar.
- **Método:** leitura direta do código, mais quatro varreduras paralelas (viabilidade, ingestão/normalização, deploy/acesso/API/bot, front). Cada `arquivo:linha` foi conferido na data. O que não foi conferido está marcado **não verificado**. O grafo (`graphify` MCP) não conectou nesta sessão; usei grep e leitura.
- **Regra de leitura:** o `docs/plano_multipais.md` (2026-08-31) está defasado. Os Blocos A a E, o BLK-INTL-13 (portal) e as correções de setembro e outubro já estão no código. Onde o plano e o código divergem, este documento segue o **código**.

---

## 0. Sumário executivo

### 0.1 O que já é neutro de país

- **Arquitetura (DEC-047).** Uma imagem, um container por país, país declarado em `perfil.json` dentro do `MOTOR_DATA_DIR`.
  - O loader é fail-closed e congelado (`src/motor_expansao/perfil.py:803-913`).
  - O fio de alarme passa. Rodei `tests/contracts/test_fio_de_alarme_pais.py` e mais 6 suítes de perfil: **237 testes verdes**. Também passaram 65 testes de compose, portal e espelho front↔python.
  - Um grep independente por comparação com sigla de país (`== "BR"`, `PERFIL.pais ==`, `in ("BR"`) devolve **zero ramos de execução**. Os únicos achados são as docstrings e comentários que proíbem o padrão.
- **Dirigido pelo perfil:** bbox, geocoder (`countrycodes`, `Accept-Language`, regex de CEP), símbolo e locale do front, as quatro âncoras da régua absoluta, `score_corte_quente`, `pop_min_acionavel`, `capacidade_concorrente`, `oferta_destaque_min`, `capacidade_unidade_alunos`, uplift e moradores (fallback), metas do semáforo, faixas de renda e densidade do **PDF**, `pin_margem_m`, superfícies, malha municipal, avisos carimbados e o teto de PDF.

### 0.2 O que ainda é brasileiro e produz número ou veredito errado em silêncio na Argentina hoje

Defeitos novos, conferidos no código:

1. **Ficha do ponto ("Serve este imóvel?").** O critério de renda compara a renda domiciliar do raio com `settings.RENDA_MIN = 4500` (R$) e rotula "R$" (`web/server/app.py:6478-6481`, `src/motor_expansao/config.py:62`).
   - Na AR a renda chega em USD, com mediana de cerca de US$ 1.068 pela meta do perfil.
   - Logo, todo ponto argentino **reprova** o critério de renda.
2. **Gate de zona morta da viabilidade e do Relatório Pontual.** `RENDA_ZONA_MORTA_MIN = 500.0` é um literal em reais (`src/motor_expansao/dimensionamento/viabilidade_ponto.py:72`, aplicado em `:542`). Ele é comparado com a renda per capita do catchment, que na AR está em USD (p50 de cerca de US$ 478 por hexágono).
   - Inferido do código, **não medido**: a maioria dos pontos argentinos sai com `flag_zona_morta=True` e motivo `renda<500`.
   - Esse flag também alimenta o selo DEMOGRÁFICO (gate E4) da Conclusão do PDF.
3. **Mapa de setores do front pinta renda e densidade com a régua brasileira.** `RENDA_DOMICILIAR_SETOR_BANDS` e `DENSIDADE_BANDS` têm literais em `web/src/lib/colors.ts:358-380` (a de renda é domiciliar, #473, E1 da DEC-075, com os cortes BR 2.000/4.000/8.000/14.000 e rótulo por `moedaRenda()`).
   - O backend já serve `reguas.bandas_renda_setor`/`bandas_densidade_setor` em `/api/me` (`app.py:5323-5324`), mas nada em `web/src` lê esses campos (zero ocorrências de `bandas_`), e as de renda são per capita: não servem ao calor de renda, que é domiciliar (`app.py:5276-5278`).
   - O PR 2 do front, previsto em `tests/contracts/test_perfil_front_espelha_o_python.py:83-86`, não foi feito.
   - Efeito, pela nota do perfil AR: 99,88% da população cai na 1ª faixa.
4. **Renda em USD rotulada "R$" em telas que a AR alcança:**
   - `web/src/screens/PontoScreen.tsx:645-646`;
   - `web/src/components/DetalheRegiao.tsx:67`;
   - `Recomendacao.tsx:139`, via `unidade "R$"` vinda de `app.py:6480`;
   - `BlocoViabilidadePonto.tsx` (apagado no #457, em 16/10/2026, com a seção "Fecha a conta?" da ficha do ponto);
   - `format.ts:169` (`UNIDADE_MOEDA` usa `moeda()`, que é o "$" do peso, sobre renda em dólar).
5. **Duas metas do semáforo da AR estão na escala brasileira de alunos.** `sam_fitness_potencial` e `residual_fitness_disponivel` valem 2.000 em `data/perfis/AR/perfil.json`, mas o residual argentino vive numa escala de cerca de 0,4× (capacidade 1.070, taxa 0,078). Os cards saem vermelhos por construção.

### 0.3 O que quebra ou degrada em silêncio num 3º país, mesmo com o perfil certo

- `mascara.ts` tem gramática pt-BR fixa. O perfil declara `separador_milhar/decimal` e ninguém lê. No México e no Peru (es-MX/es-PE: `1,500.00`), o valor digitado é lido errado sem erro (R10 do plano, ainda aberto).
- O join do crescimento municipal usa `cod_municipio.str[:6]` (o código IBGE sem dígito verificador) (`app.py:1104-1108`).
  - Com DANE (CO) e INEGI (MX), de 5 dígitos, a camada 4 fica vazia em silêncio.
  - Com UBIGEO (PE), de 6 dígitos, casa por acaso.
- As tabelas de vocabulário do front só conhecem BR e AR: `rodape-base.ts:36-60` e `Dock.tsx:38-48`. Um país novo cai em "unidades federativas" e fica sem bandeira. É degradação controlada, não erro.
- `nota_demanda` (camada 5) tem âncoras em alunos brasileiros: `DEMANDA_MIN_ALUNOS = 2.000` e `DEMANDA_MAX_ALUNOS = 20.000` (`src/motor_expansao/dashboard/praca_indice.py:45-46`).
  - Em país com outra escala de residual, como a AR (piso do funil em 802,5), a ordenação da fila sai achatada.
  - Morde quando a superfície `oportunidades` subir.
- `_CAMADAS_AR` (`app.py:910-925`) é um schema de colunas de UM país compilado na plataforma. Não é ramo, mas um país novo com camadas próprias exige editar `app.py`.

### 0.4 Infra e acesso

- **Três peças inexistentes no repo:** o validador `scripts/validar_pacote_pais.py`, o contrato `docs/contrato_pacote_pais.md` e um exportador genérico.
  - O exportador AR (`src/motor_expansao/pipelines/exportar_piloto_ar.py`) é específico de país.
  - Ele ainda faz `import nacional_academia` (`:399`), módulo do repo do Juan que não está aqui.
- **Adicionar país = cerca de 12 a 15 artefatos copiados à mão**, metade CRÍTICOS:
  - compose, template Caddy, Caddyfile real, Authelia, portal `index.html` com `$br/$ar` fixos, healthcheck e teste de compose.
- **Capacidade.** Os tetos rígidos já somam 16 GB na VPS (`docs/deploy_piloto_web.md`, passo 10).
- **API/bot não existem para a AR**, por desenho: `api/geo.py` e o `_UFS` do bot são BR literais.
- **O banco de usuários (DEC-067/069) é só BR** e não tem dimensão de país. A AR segue no Authelia.

---

## 1. TAREFA 1 — Mapa de acoplamento a país (código atual)

Legenda: **PERFIL** = lido do `perfil.json` · **DADO** = vem do pacote no `MOTOR_DATA_DIR` (troca com o volume) · **BR** = literal brasileiro no código · **MORTO** = declarado no perfil e sem leitor.

### 1.1 Contagens de grep (código, sem `node_modules`; inclui comentários salvo indicação)

Formato: ocorrências/arquivos.

| Padrão | `src/motor_expansao` | `web/server` | `web/src` (sem `*.test.*`) | `scripts` |
|---|---|---|---|---|
| `IBGE` | 148/28 | 17/1 | 17/7 | 24/5 |
| `R$` | 231/33 | 20/2 | 107/26 (≈60 fora de comentário) | 5/3 |
| `brl(` | 26/2 | 0 | 84/16 | 0 |
| `BRL` | 12/2 | 1/1 | 3/2 | 0 |
| `setor_2022` | 577/39 | 56/2 | 4/4 | 7/4 |
| `countrycodes` | 4/2 | 4/1 | 0 | 0 |
| `_UFS_BR`/`UF_BR` | 20/6 | 2/1 | 0 | 0 |
| `Brasil`/`brasil` | 319/47 | 35/3 | 95/33 | 63/9 |
| `pt-BR`/`pt_BR` | 16/11 | 1/1 | 30/17 | 0 |
| `CAGED`/`RAIS` | 43/9 | 12/1 | 21/10 | 1/1 |
| `WellHub`/`wellhub` | 257/28 | 29/2 | 70/9 | 21/5 |
| `TotalPass` | 198/33 | 11/1 | 44/10 | 20/6 |
| `SIRGAS`/`4674`/`5880` | 14/8 | 0 | 0 | 1/1 |
| `Nominatim` | 36/5 | 6/1 | 2/2 | 13/1 |

- **Strings visíveis ao usuário com IBGE/CAGED/R$/Censo 2022 fora de comentário**, só nos geradores de texto principais:
  - `censo_report.py`: 5 (`:2428`, `:3220`, `:3551`, `:4029`, `:4127`);
  - `relatorio_municipal.py`: 8, das quais 3 já leem o instituto do perfil (`:3399`, `:3401`, `:3951`), mas com "Censo 2022" fixo;
  - `web/server/app.py`: 8 (`:2758`, `:2779`, `:3706`, `:4054`, `:5556`, `:5586`, `:5740`, `:5744`).
- **Fio de alarme** (`test_fio_de_alarme_pais.py`): **verde**. A lista de exceções é só o próprio teste (`:61-63`, travada em `:157-164`). Os únicos `pais === 'BR'` do repo estão em comentário de `rodape-base.ts:44` e de `rodape-base.test.ts:126`.
- **Anti-moeda** (`test_sem_moeda_hardcoded_no_front.py`): verde, mas só varre `web/src/lib/**` (allowlist vazia).
  - As telas e componentes ficam fora da guarda por decisão (decisão 0.6, a viabilidade em reais).
  - É por esse buraco que passam os "R$" de renda listados no §0.2 item 4.

### 1.2 Tabela por área

| Área | Dirigido por PERFIL / DADO | Ainda BR (literal) | Evidência |
|---|---|---|---|
| **Boot / caminhos** | PERFIL: `resolver_perfil()` 1×/processo; `DATA_DIR = PERFIL.raiz`; `outputs/`, `staging/`, `ibge/`, `ultra/` penduram nele | Nomes de arquivo brasileiros como contrato: `DASHBOARD_NACIONAL_PATH = outputs/hexagonos_brasil_dashboard.parquet` (`app.py:242`, usado pela camada de 1 km); o diretório se chama `ibge/` (`app.py:230`) | `perfil.py:894-913`, `app.py:137-138`, `:228-261` |
| **Ingestão: censo** | DADO: o piloto lê o que o pacote traz. A AR entra pelo exportador | Toda a cadeia de produção BR é IBGE (Fase A, `materializar_setores_censitarios_geo`, `agregar_censo_hex_da_malha`, uplift via SIDRA) e roda neste repo. Para outro país, o método mora no repo do pipeline de país (DEC-047) | §1.3; `exportar_piloto_ar.py:198-279` |
| **Ingestão: GymScraping / concorrentes** | DADO: `staging/concorrentes_mapeados.parquet` (contrato `rede, nome_unidade, lat, lng, hex_id_res7, status_registro, flag_coord_valida, foto`) | Catálogo de exibição de redes BR (`competitors.py`, cerca de 110 redes); slug de logo derivado do nome (`app.py:1905-1957`). A AR entrega logos por slug | `exportar_piloto_ar.py:330-465` |
| **Agregadores WellHub/TotalPass (M&A)** | DADO opcional: sem os parquets `vulnerabilidade_ma_*`, os pins somem | Vocabulário fechado `FONTES_VALIDAS = {"totalpass","wellhub","unidades"}` (`vulnerabilidade/contrato.py:213`); coleta e cron brasileiros; ícones `logo-wellhub`/`logo-totalpass` no front | `app.py:259-261`, `:1190-1365` |
| **Crescimento municipal** | DADO opcional: `staging/crescimento_municipal.parquet` e `crescimento_hex.parquet` | Join por `cod_municipio.str[:6]` = código IBGE sem dígito verificador (`app.py:1104-1108`). Textos "CAGED, RAIS, Receita Federal" em `app.py:2758`, `:2779`, `:3706`, `:4054`, `:5744` e `censo_report.py:4029`. Módulo `crescimento/` é CAGED puro (`crescimento/caged.py:17`, `validar.py:50`). A AR tem `crescimento_hex_ar.py` no repo do Juan, **não exportado** | `app.py:1092-1140` |
| **Renda: score (âncoras)** | PERFIL: `Perfil.ancoras()` → `calcular_score_calibrado(..., ancoras=)`. O exportador AR recomputa com as âncoras AR (`exportar_piloto_ar.py:118-136`) | Pesos 0,60/0,40 literais (`calibrar_renda_setor_2022.py:191`); `reguas.score_pesos` do perfil é **MORTO** (aceito como "tolerado", `perfil.py:396-403`) | `calibrar_renda_setor_2022.py:91-107`, `:171-191` |
| **Renda: k de calibração** | — | `_K_CALIBRACAO_FALLBACK = 1.0239` (`app.py:1617`), lido do carimbo do staging BR. Na AR, a renda do hexágono vem de `renda_per_capita` (`exportar_piloto_ar.py:261`), então o ramo do k não é exercitado. Um país que entregue `renda_per_capita_setor_2022_calibrada` no hexágono sem o carimbo cai no k brasileiro **em silêncio** (só log WARNING), salvo se o arquivo de fatores do país (`renda/fatores/<PAIS>/`, DEC-075) declarar `artefato_k_obrigatorio: true`, como o BR: aí a subida em produção falha (`InsumoRendaInvalido`). O da AR declara `false`; o fallback mora em `renda/hex.py:53`, re-exportado em `app.py:1884` | `app.py:1626-1675`, `:1677-1702` |
| **Renda: uplift e moradores** | PERFIL como fallback nacional: `UPLIFT_COMPOSICAO_NACIONAL = _REGUAS.uplift_composicao` (AR = 1,0) e `MORADORES_DOMICILIO_NACIONAL` (AR = 2,5654) (`dashboard/constants.py:553-556`). DADO: as tabelas por município e setor têm precedência se existirem | Tabelas com schema IBGE (`cod_municipio` 7 dígitos, `uplift_confiavel`), docstrings "IBGE" | `renda/insumos.py` (movidas de `constants.py` na E0 da DEC-075, #472) |
| **Renda: FATOR_TEMPORAL_RENDA** | Arquivo de fatores versionado NA IMAGEM (E0 da DEC-075, #472): `src/motor_expansao/renda/fatores/<PAIS>/<versao>.json` + `VIGENTE`, escolhido pelo país do perfil; o `staging/fator_temporal_renda.json` não é lido | Sem fallback: país sem o diretório de fatores **não sobe** (`FatoresRendaInvalidos`, também em dev). A AR tem `2026-08_sem_atualizacao_v0` (fator 1,0) com o rótulo **"julho/2022 (Censo IBGE)"** herdado do fallback brasileiro, ainda exibido como data de referência da renda. Para CO (censo 2018) e PE (2017), fator e rótulo passam a ser decisão do arquivo do país | `renda/carregador.py:287-308`; `renda/subida.py`; `app.py:2003-2013` |
| **Malha H3** | Resolução 7 é contrato implícito do piloto (todo `hex_id` é res 7; `pressao_1km` e o raio usam res 7) | `H3_RESOLUTION=7` e `M1_HEX_LAND_FRACTION_MIN=0.05` vivem no `config.py` do M1, cujo pipeline (`base_h3_brasil.py`) é BR. Na AR a malha vem pronta do pacote | §1.3 |
| **Funil: camada 1** | PERFIL: `SCORE_CORTE_QUENTE`, `POP_MIN_ACIONAVEL` (`app.py:287-296`) | Narrativa "o censo 2022 acende…" (`app.py:3152`, `:3651`) | `app.py:2907-2917` |
| **Funil: camada 2** | PERFIL: `OFERTA_DESTAQUE_MIN` (AR = 802,5) | — | `app.py:2919-2924` |
| **Funil: camada 3** | PERFIL: `CAPACIDADE_CONCORRENTE_PADRAO` como fallback de divisor | `CONC_ADENSAR_MAX = 2` literal (`app.py:339`); `pressao_1km.py:201` com `fillna(2_500.0)`; `CAPACIDADE_ULTRA_PROXY = 2_500` (`:66`); `CONSUMO_1KM_CORTES = [625,1250,2500,5000]` no front (`colors.ts:293`, BLK-INTL-14 aberto) | `app.py:2872-2964` |
| **Funil: camada 4** | DADO opcional | Join por `cod6` IBGE e textos CAGED (ver crescimento) | `app.py:3086-3092`, `:3166-3180` |
| **Funil: camada 5** | — | `PESO_SOCIO 0,70`/`PESO_DEMANDA 0,30`, `DEMANDA_MIN/MAX_ALUNOS 2.000/20.000` literais (`praca_indice.py:45-58`); `FILA_MAX = 10` | `app.py:2999-3026` |
| **Ficha do ponto (critério do imóvel)** | PERFIL: `POP_MIN_ACIONAVEL` | **`settings.RENDA_MIN = 4500` (R$) + rótulo "R$"** (`app.py:6478-6481`, `:6808`); `CRIT_PONTO_SCORE_MIN = 50`, `CRIT_PONTO_CONC_MAX = 3` (`:322-323`); `AREA_MIN_M2` etc. do `config.py` | `app.py:6436-6520` |
| **Relatório Pontual (PDF)** | PERFIL: metas (`censo_report.py:156`), faixas de renda e densidade (`constants.py:529-537`, `:748-749`), símbolo de renda (`censo_map.py:51`), aviso de rodapé | Rodapés "setores IBGE 2022" e "Censo IBGE 2022" (`censo_report.py:3220`, `:3551`, `:4127`); "CAGED, RAIS e Receita" (`:4029`); EPSG:4674 como CRS de origem (`censo_point.py:26`) — inócuo, a área é calculada em AEQD local | — |
| **Relatório Municipal** | PERFIL: instituto (`relatorio_municipal.py:1082-1090`), `OFERTA_DESTAQUE_MIN` (`:75`), símbolo de renda (`:1078`); unidade HEXAGONO já passada pelo web (`app.py:10564`) | "Censo 2022" fixo no ano (`:3399`, `:3401`, `:3765`, `:3861`, `:3951`); "CAGED, RAIS e Receita Federal" (`:4114`) | — |
| **Calibração do mercado (DEC-060)** | — | `calibrar_taxa_fitness_mercado` roda no pipeline BR (17,35%), a partir do consumo 1 km e de alunos Ultra reais; fallback 0,10 (`calcular_colunas_mercado.py:46`). `reguas.taxa_fitness` do perfil é **MORTO** (BR declara 0,1; o real é 0,1735). Na AR, a taxa (0,078 constante) e a capacidade (1.070) entram **dentro** do pacote do Juan | `calcular_colunas_mercado.py:121-208`, `:357-362` |
| **Viabilidade** | PERFIL: câmbios `cambio_base` e `cambio_viabilidade` → `_moeda_da_viabilidade` (`app.py:200-225`), servido em `/api/me`; aviso `AR-VIAB-TRIB-PROVISORIO` na tela, no PDF e no XLSX (`app.py:159-197`, `:11019`, `:11145`) | **O motor inteiro é BR**: `dimensionamento/config.py` (Lucro Presumido, PIS/COFINS/ISS `:85-87`, IRPJ/CSLL `:210-217`, folha 17%, royalty 8%, CAPEX 2,34 mi, taxa mínima 25% "Selic 14,25%" `:229-244`, aluguel-teto `:180-182`, veredito `:266/:270`). Furos fora de `Premissas`: `aluguel_teto_clusters` (`simulador.py:632-651`), `flag_viavel` (`:999`), `payload_viabilidade.py:364-367/466-467/680-681`. XLSX com encargos 68% e quadro em R$ (`simulador_xlsx.py:242-268`). Textos fiscais BR em `ViabilityNotes.tsx:135-206`. Zona morta em R$ (`viabilidade_ponto.py:72`). Golden de Londrina trava tudo (`tests/contracts/test_viabilidade_golden.py:1053-1163`). Detalhe no §1.4 | — |
| **API GeoEspacial** | PERFIL: bbox e nome (`api/coord.py:25-27`), `countrycodes`/idioma/CEP (`api/maps_geocoder.py:28-48`, `:278`, `:288`), fonte (`service.py:144`, `:163`), símbolo (`:1254`) | `api/geo.py` **não lê o perfil**: Google `region:"br", language:"pt-BR"` (`:342`, `:359`), sufixo "Brasil" (`:164`), Nominatim sem `countrycodes` (`:373-381`). Malha `municipios_*.geojson` com `CD_MUN` (`service.py:110-125`). `validar_brasil`/`BRASIL_*` (nomes legados). Sem gate de superfície. **Não sobe na AR** (`docker-compose.ar.yml:8-9`) | — |
| **Bot Telegram** | indireto (`api.coord`) | `_UFS` com as 27 UFs fixas (`api/telegram_bot.py:66-69`, `:680`); textos "Endereço + CEP", "estado (UF)"; um token só; não usa `GET /ufs`. **Não sobe na AR** | — |
| **Controle de acesso** | PERFIL: `motivo_bloqueio_pais(path, perfil)` (`web/server/acesso.py:207-229`) com `SUPERFICIE_DA_ROTA` (`:145-170`) e `ROTAS_QUE_EXIGEM_MALHA_MUNICIPAL` (`:186-193`), sem literal de país. Fail-closed por usuário (`:491-542`); um `acesso_abas.json` por instância | **Banco (DEC-067/069) só BR**: `usuarios` sem coluna de país (`db/migracoes/003-usuarios.sql:12-21`); bases de referência IBGE/4674 (`006-bases-de-referencia.sql:12-40`). A AR segue no Authelia → dois cadastros. Pertença a país só nos grupos `expansao_br`/`expansao_ar` (arquivos cifrados, **não verificado**) | — |
| **Portal (BLK-INTL-13)** | — | `portal/index.html:485-551` com `$br`/`$ar` e um cartão por país escritos à mão ("PRÓXIMO PAÍS: copie um bloco"); matchers `@so_<pais>`/`@tem_<pais>` no Caddyfile, com N² linhas de negação; regex `brasil\|argentina\|piloto-ar` em `tests/unit/test_portal_paises.py:37`, `:141` | `scripts/aceite_portal_paises.sh:112-142` |
| **Front: formatação** | PERFIL: `nf()` com `locale` (`format.ts:11-15`), `moeda()`/`moedaRenda()` (`perfil.ts:70-86`), bbox (`coord.ts:23-29`, `entrada-ponto.ts:68-78`), vista (`mapa-ponto.ts:33-37`), `POP_MIN_ACIONAVEL` (`colors.ts:70`), `CAPACIDADE_UNIDADE_ALUNOS` (`faixas.ts:86`) | `mascara.ts` com gramática pt-BR (`:81`, `:172`, `:187`, `:226`, `:248-257`); `localeCompare('pt-BR')` em 7 sítios e `toLocaleString('pt-BR')` em 4 (`oportunidades.ts:171,206,209`, `recomendacao.ts:203`); `lang="pt-BR"` em `index.html:2`/`entrar.html:2`; bandas de renda e densidade BR (`colors.ts:358-377`); `fmtBrl` com `moeda()` sobre valores em reais (`recomendacao.ts:206`); "R$ 0" fixo no eixo (`ViabilityCharts.tsx:1125`) | — |
| **Front: textos/i18n** | — | **Sem i18n**: nenhum catálogo, nenhum `t()`. De 1,5 a 2,5 mil strings PT inline. "Escolha o estado" (`Passos.tsx:113-128`), "Mediana do estado" (`HexMap.tsx:380`), "Brasil" em `inicio.ts:170`, `:268` e no desenho `MalhaBrasil` do login (`LoginScreen.tsx:207`, `:505`, `:562`). Tabelas `UNIDADE`/`CENSO`/`INSTITUTO`/`PONTOS` só BR+AR (`rodape-base.ts:36-60`); `BANDEIRAS` só BR+AR (`Dock.tsx:38-48`) | — |
| **Front: mapa base** | — | CARTO GL global (`HexMap.tsx:207`, `:217`), neutro. O aviso `mapa_sem_toponimo` do perfil AR não tem leitor no front | — |
| **PDF: basemap** | env por serviço (`API_BASEMAP_TILES_URL`/`_LABELS_URL`) | Rótulos sem fallback (`censo_map.py:864-873`); `openmaptiles-infra` só gera `brazil.mbtiles` com `name:pt`. `operacao.basemap_labels_url_obrigatoria` e `mem_limit_alvo` do perfil são **MORTOS** | — |
| **Deploy** | Mesma imagem `WEB_IMAGE` nos dois países; perfil por bind | Stacks escritas à mão: `docker-compose.prod.yml` (BR, com caminhos `/opt/motor-expansao/...`) e `docker-compose.ar.yml` (`name`, `container_name`, mounts `/opt/motor-expansao-ar/...`, `mem_limit 2g`). Testes literais por país (`tests/unit/test_compose_ar.py:89-147`). Healthcheck com array manual (`scripts/healthcheck_vps.sh:83-118`) e `EDGE_URL` escalar (`:31`). O branding AR lê do diretório BR (`docker-compose.ar.yml:85`) | — |
| **Exportador / contrato de pacote** | PERFIL: âncoras via `--perfil` (`exportar_piloto_ar.py:981-985`) | **Específico de país**: `SIGLA_PROVINCIA` e `UF_BR` (`:155-168`, o anticolisão com UF BR é resquício da era da disjunção); `import nacional_academia` (`:399`), módulo externo; `POP_MIN_PILOTO = 5_000` duplicado (`:178`). **Não existem** `scripts/validar_pacote_pais.py` nem `docs/contrato_pacote_pais.md` (conferido: `git log --all` vazio para os dois caminhos). Comentários defasados no próprio exportador: `:914-916` cita `MOTOR_PAIS`/`_censo_publica_renda_do_responsavel`, que não existem mais; `:1093-1095` diz que a renda AR sai com "$", e hoje sai "USD" | — |

### 1.3 Ingestão, normalização e malha (detalhe)

**Princípio já decidido (DEC-047, §1.1 do plano).** A ingestão de um país novo **não mora neste repositório**: ela mora no repo de pipeline do país, mantido pelo Juan. Por isso, o que segue mede o quanto o pipeline **brasileiro** é reaproveitável, não o quanto a plataforma precisa mudar.

**Correção ao enunciado:** não há scripts legados na raiz do repo; só existe `conftest.py`. A docstring `pipelines/m1/__init__.py:1` ("wrappers legados na raiz") está defasada. O `config.py` canônico é `src/motor_expansao/config.py`.

**Pipelines em `src/motor_expansao/pipelines/`**

Contagens: linhas com IBGE / setor_2022 / cod_municipio / `\buf\b`.

| Módulo | Classe | Evidência |
|---|---|---|
| `m1/base_h3_brasil.py` | **BR** (API de malhas IBGE) | `IBGE_MALHAS_UF_URL` (`:37-44`); `UF_POR_CODAREA` com 27 entradas (`:46-74`); exige **exatamente 27 features** (`:153-160`); cache `data/raw/ibge/malha_*.geojson` (`:386-387`). Res. 7 em `:379`, `:520`; land fraction em `:254`, `:508` |
| `m1/ibge_censo.py` | **BR** (FTP IBGE + SIDRA t.10295/t.4709) | `:36-48`; 18/3/51/60 |
| `m1/hex_enrichment.py` | **BR** (SIDRA, `RENDA_MIN`) | `:131`, `:628`, `:635` |
| `m1/fase1_bi_exports.py` | BR (cod_municipio/UF; grava `hexagonos_brasil_*`) | `:39-41` |
| `fase_a_censo2022_setores.py`, `fase_a_nacional_completo.py`, `fase_a_piloto_expandido.py`, `materializar_setores_censitarios_geo.py`, `validar_fase_a_censo2022.py` | **BR** (IBGE setores, v0001/V06004; listas `UFS_*` fixas) | `fase_a…:52`, `:88-90`; `materializar…:65`, `:94` |
| `agregar_censo_hex_da_malha.py` | BR (mede o k na malha) | `:305-320`, `:666-667` |
| `calibrar_renda_setor_2022.py` | BR com régua **parametrizável** (`ancoras=`) | `:91-107`, `:171-194`. O k é **calculado** (`m1_median/setor_median` em GO/SP/RJ, `:109`, `:295-305`), não literal |
| `derivar_fator_temporal_renda.py` | não existe (E0 da DEC-075, #472); o fator temporal fica em `src/motor_expansao/renda/atualizar_fatores.py` (microdados da PNAD Contínua), fora de `pipelines/` | — |
| `derivar_uplift_renda_domiciliar.py`, `derivar_uplift_composicao_setor.py` | **BR** (SIDRA, parentesco IBGE) | `:108` |
| `normalizar_concorrentes.py` | **BR** (GymScraping) | — |
| `alunos_reais.py`, `normalizar_unidades_ultra.py`, `calcular_penetracao_ultra_hex.py`, `validar_*ultra*` | BR (rede Ultra, WellHub/TotalPass) | — |
| `calcular_colunas_mercado.py` | lógica neutra, **constantes BR** | `TAXA_FITNESS_MERCADO_FALLBACK 0.10`, `CAPACIDADE_MIN_ACADEMIA_ALUNOS 2000`, `CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS 2500`, `POP_MIN_SAM_GATE 5000`, `RENDA_PER_CAPITA_MIN_ATR 1500` em R$ (`:46-53`); calibração DEC-060 em `:121-215` |
| `enriquecimento_espacial_hexagonos.py`, `pressao_concorrencial_1km.py`, `enriquecer_outputs_residual_mercado.py`, `pop_corte.py` | **neutros** (geometria/H3) | reaproveitáveis por outro pipeline |
| `modelo_hibrido_expansao.py`, `gerar_carteira_*`, `gerar_plano_*` | lógica neutra, chaves `cod_municipio`/`uf` | — |
| `exportar_piloto_ar.py` | ponte AR → contrato do piloto | §2 |

**Fora de `pipelines/`:**
- **`scripts/ingerir_*`:** Growth API, planos de agregador, comodidades, movimentação, faturamento financeiro. Mais `sync_concorrentes_dashboard.py`. Todos são **BR por fonte**.
- **Crescimento:** `src/motor_expansao/crescimento/atualizar.py` orquestra `data/reports/crescimento/01..10_*.py` (`:51-61`). Os insumos são Novo CAGED via FTP PDET (`crescimento/caged.py:40-41`), RAIS e satélite. A saída é consumida por `app.py:243`, `:247`, `:1072`, `relatorio_praca.py:446-447` (também por `cod6`) e `api/service.py:1249`.

**Normalização no serving (`dashboard/constants.py`, `_REGUAS = resolver_perfil().reguas` em `:10`)**

| Item | Linha | Origem |
|---|---|---|
| `POP_MIN_ACIONAVEL`, `CAPACIDADE_UNIDADE_ALUNOS` | `:183`, `:418` | **perfil** |
| Bandas de renda e densidade (PDF) | `:528-537`, `:747-749` | **perfil**, com fallback `_*_BANDS_BR` (`:451`, `:468`, `:738`) |
| `UPLIFT_COMPOSICAO_NACIONAL`, `MORADORES_DOMICILIO_NACIONAL` | `:553`, `:556` | **perfil** |
| Uplift e moradores por município/UF/setor | fora deste arquivo desde a E0 da DEC-075 (#472): `src/motor_expansao/renda/insumos.py` | **DADO** com schema IBGE (`cod_municipio`, `cod_setor`); caminho relativo ao CWD (`data/staging/...`), reapontado pelo web por `renda.configurar_staging(STAGING_DIR)` (`app.py:1875`). Na AR o arquivo não existe e o fallback do perfil vale |
| `FATOR_TEMPORAL_RENDA` | saiu deste arquivo na E0 da DEC-075 (#472) | arquivo de fatores versionado por país na imagem (`renda/fatores/<PAIS>/`), sem fallback; o rótulo "julho/2022 (Censo IBGE)" segue declarado no arquivo da AR (`rotulo_referencia`) |
| `FAIXAS_MAPA_POTENCIAL/DEMANDA` | `:396`, `:408` | **literal** (o perfil declara `faixas_mapa_*`, o loader não lê) |
| `BRASIL_CENTER` | `:184` | literal |

- **Semântica IBGE no serving.** Contagens: IBGE / setor_2022 / cod_municipio / V06004 / cod6.
  - pipelines: 102 / 431 / 309 / 61 / 0;
  - dashboard: 40 / 155 / 83 / 21 / 10;
  - api: 6 / 8 / 27 / 0 / 1;
  - web/server: 17 / 58 / 44 / 6 / 18.
- **V06004 (renda do responsável) é a base da renda domiciliar** em `censo_point.py:392-505`, `censo_map.py:1860-1893`, `relatorio_municipal.py:922-935` e `app.py:1681-1729`.
  - **Esse é o contrato semântico mais "brasileiro" que um país tem de imitar.** O exportador AR fabrica `renda_responsavel_media_setor_2022 = renda × moradores` (`exportar_piloto_ar.py:923`) para caber na fórmula, com `uplift = 1,0`.
- **Malha H3 em resumo.**
  - **Res. 7:** contrato implícito do serving (o mapa, o raio de 1 km e as camadas assumem res 7).
  - **`M1_HEX_LAND_FRACTION_MIN = 0.05`:** decisão do pipeline BR (DEC-003), sem leitor no serving.
  - **Geração da malha AR:** cobertura por área ponderada a partir dos radios, com corte de densidade ≥ 3 hab/km² (plano §6.1 D2, **não verificado** no código do Juan).
- **`config.py` lido no serving:** `RENDA_MIN` (`app.py:6459`, `:6480`, `:6808`) e `AREA_*` (`app.py:6808-6811`; `censo_report.py:16-20` via `core/constants.py:13-16`). Nenhum vem do perfil.

### 1.4 Viabilidade (detalhe)

**O motor de viabilidade não lê o perfil em nenhum ponto** (grep `perfil|PERFIL` em `src/motor_expansao/dimensionamento/`: só docstring). Do perfil vêm três coisas, todas na borda: os câmbios para a tela, o aviso e o locale/símbolo dos formatadores.

- **Fonte única CRÍTICA:** `src/motor_expansao/dimensionamento/config.py`.
  - **Tributos:** `SIM_PIS` 0,0065 / `SIM_COFINS` 0,03 / `SIM_ISS` 0,03 (`:85-87`); IR/CSLL presumido `:210-217` (base 32%, IRPJ 15% + 10% acima de R$ 20 mil/mês, CSLL 9%).
  - **Custos fixos e receita:** folha 17% (`:147`); outros fixos 38.150 com IPTU (`:109`); ticket 137 (`:99`; a tela usa 147, `ViabilityScreen.tsx:81`); mix 0,69 / agregador 0,60; anuidade R$ 99 (`:290`).
  - **Variáveis e investimento:** royalty 8% (`:77-82`); reajuste 4% (`:221-223`); CAPEX 2,34 mi (`:103`); franquia 160 mil (`:169`).
  - **Taxa e réguas:** taxa mínima 25% "Selic 14,25%" (`:229-244`); aluguel-teto 0,15/0,20/0,30 (`:180-182`); margem ≥ 0,30 / payback ≤ 36 (`:266`, `:270`).
- **A estrutura do imposto é fixa.** `Premissas.ir_csll` (`simulador.py:464-473`) é o regime presumido, e `impostos_receita_pct = pis+cofins+iss` (`:304-305`). Trocar alíquota é parâmetro; trocar regime (Monotributo/IVA/IGV/ICA/Ingresos Brutos) é código.
- **Furos fora de `Premissas`** (nenhum pacote por país os alcança):
  - `aluguel_teto_clusters` (`simulador.py:632-651`);
  - `flag_viavel` (`:999`);
  - `payload_viabilidade.py:185-276`, `:364-367`, `:466-467`, `:680-681`;
  - `viabilidade_ponto.py:29-35`, `:418`, `:489`;
  - XLSX `simulador_xlsx.py:142-151`, `:1035-1079`, `:1571-1581`;
  - `_ticket_proj_mensal` (`app.py:11365-11376`).
- **Moeda:** a conta é sempre em BRL (decisão 0.6).
  - A AR declara `ARS/USD` 1.397,71 e `BRL/USD` 4,9837 (base 2026-05).
  - `_moeda_da_viabilidade` só serve se os pares forem exatamente `{codigo}/USD` e `BRL/USD`.
  - O front converte a entrada (`viabilidade-moeda.ts:76-107`) e a exibição (`format.ts:52-73`).
  - O PDF e o XLSX saem em reais (`_FMT_CONTABIL` em `simulador_xlsx.py:199`, `_brl` em `viabilidade_charts.py:79` e `censo_report.py:1104`/`:2151`).
- **Contexto de commits:** a DEC-068 trata do ticket próprio por studio, não de moeda. O commit `8cc5983` (#446) levou o ticket de studio por `paraReais` (antes daria erro de cerca de 280×) e criou o teste `test_viabilidade_mix_e_cambio.py`.
- **Golden:** `tests/contracts/test_viabilidade_golden.py` (Londrina) trava o DRE com tolerância de R$ 0,01 e todo `SIM_*` com 1e-12 (`:1053-1163`). Não tem eixo de país.

---

## 2. TAREFA 2 — Contrato de dados por camada

Convenções:
- **Artefato:** caminho relativo ao `MOTOR_DATA_DIR`.
- **Leitura defensiva:** `carregar_uf` projeta `_COLS_DESEJADAS ∩ schema` (`app.py:930-1012`), ou seja, coluna ausente **não quebra**, some.
- **Grão:** "hex7" = H3 res 7.
- O piloto descobre as "UFs" por `glob("uf=*")` (`app.py:1465-1476`). A chave tem de casar `^[A-Za-z]{2}$` (`app.py:984`); fora disso a resposta é 400.

### 2.0 Identidade (pré-requisito de todas as camadas)

| Coluna | Tipo | Grão | Mínimo aceitável / se faltar | AR |
|---|---|---|---|---|
| partição `uf=XX` | dir, 2 letras | nível 1 | Fora do regex: 400. Pasta vazia vira "estado fantasma" que dá 404 | 24 siglas próprias (`exportar_piloto_ar.py:155-163`) |
| `hex_id` | str H3 res 7 | hex7 | **Quebra**: sem ele não há mapa (o `merge` do crescimento e o `_contagem_no_hexagono` exigem) | Derivado de `h3_id` |
| `lat`, `lng` | float | hex7 (centroide) | Mapa e funil sem posição | Derivado por `h3.cell_to_latlng` |
| `nome_municipio` / `cidade` | str | nível 2 | Um supre o outro (`app.py:1396-1397`). Sem os dois, não há ranking por município | `nome_departamento` |
| `cod_municipio` | str | nível 2 | Sem ele: renda domiciliar do hex vira `None` (`app.py:1712-1714`), sem crescimento, sem malha. **Formato importa**: `str[:6]` no join do crescimento | `cod_departamento` (5 dígitos) |

### 2.1 Camada 1 — Potencial socioeconômico

| Insumo | Tipo / unidade | Grão | Se faltar | AR entregou |
|---|---|---|---|---|
| `score_setor_2022_calibrado` | float 0-100, régua ABSOLUTA nas âncoras do perfil | hex7 | `_quente` devolve tudo `False` (`app.py:2907-2911`) → funil vazio, **sem erro**. Se vier um **percentil** com esse nome: corte 30 com outro significado, número errado silencioso (motivo do recompute, `exportar_piloto_ar.py:118-136`) | Sim, **recomputado** com as âncoras AR (US$ 350/1.000; pop 1.000/100.000) |
| população: precedência `populacao_corte_hex` > `pop_total_setor_2022` > `pop_total` | float, habitantes | hex7 | `pop_leitura` NaN → `_povoado` False | `populacao_corte_hex` = captação (hex + 6 vizinhos); `pop_total_setor_2022` = pop DO hex. **Não** emite `pop_total` (falso amigo: no BR é o total do município repetido) |
| renda: `renda_per_capita_setor_2022_calibrada` > `renda_per_capita` (por LINHA) | float, moeda **`moeda.indicadores_renda`** per capita/mês | hex7 | Tooltip sem renda. A origem decide a escala: a coluna de setor é dividida pelo k (`app.py:1693-1694`), a municipal pelo uplift (`:1695-1699`) | `renda_per_capita` = `renda_estimada_usd` (USD) |
| `densidade_pop_setor_hab_km2` | float hab/km² | hex7 | Camada de densidade vazia | Não entregue no hex (só no setor) — **não verificado** se o mapa a usa na AR |
| `faixa_oportunidade` | enum cru (`prioridade_maxima`/`alta`/…) | hex7 | Faixa M1 ausente na ficha | Sim (os valores crus casam com `FAIXA_ORDEM`) |
| `score_priorizacao`, `score_expansao_hibrido`, `score_oportunidade_residual` | float | hex7 | Camadas do mapa sem cor | Sim (o nativo AR, percentil; **não é** o que o funil corta) |

**Perfil:** `reguas.renda_abs_min/max`, `pop_abs_min/max` (validação: min<max, pop_min>0), `score_corte_quente`, `pop_min_acionavel`, `moeda.indicadores_renda`, `faixas_mapa_potencial` (declarada; o front usa `faixas.ts:76-82`).

### 2.2 Camada 2 — Demanda não atendida (residual)

| Insumo | Tipo / unidade | Grão | Se faltar | AR entregou |
|---|---|---|---|---|
| `oferta_efetiva_disponivel` | float, **alunos** = `max(SAM − oferta consumida, 0)` | hex7 | `_com_residual` todo False (`app.py:2919-2924`) → camadas 2-5 vazias, **sem erro**; o índice nasce NaN (`:3008-3012`) | Sim, renomeado de `residual_membros` (de-para `exportar_piloto_ar.py:477-483`, conferido em 42.388 linhas) |
| `sam_fitness_potencial` | float alunos | hex7 | Card SAM "Não disponível" | Sim (`sam_membros_potencial`) |
| `oferta_consumida_mercado_estimada` | float alunos | hex7 | Camada 3 vira `True` para todos (`app.py:2950-2951`): **"não mapeado" vira "livre"** | Sim (`oferta_consumida_mercado`) |
| `oferta_consumida_ultra_real`, `n_unidades_ultra_2km`, `n_unidades_ultra_performance_hex` | float/int | hex7 | `pressao_1km` devolve NaN no hex saturado | Cravados 0 (greenfield) |
| `staging/hexagonos_mercado_mapeado.parquet` (único, não particionado) | `hex_id` + 4 colunas | hex7 | Relatório Pontual perde a página de residual e os cards SAM/Residual, **sem erro** | Sim (`exportar_piloto_ar.py:486-532`) |

**Perfil:** `oferta_destaque_min` (piso; AR = 0,75 × 1.070 = 802,5, ancorado na régua nativa do pipeline AR) e `faixas_mapa_demanda`. O `taxa_fitness` declarado **não é lido**: a taxa precisa vir embutida no SAM do pacote. **Unidade crítica:** o residual tem de estar em **alunos**, na escala do `capacidade_concorrente` do país, porque os pisos da camada 2 e as âncoras da camada 5 são em alunos.

### 2.3 Camada 3 — Pressão competitiva

| Insumo | Tipo / unidade | Grão | Se faltar | AR entregou |
|---|---|---|---|---|
| `n_concorrentes_influencia_1km` | int (contagem real, disco de 1 km) | hex7 | Cai no ramo `consumo / capacidade` (`app.py:2894-2906`) | **Não**: o exportador não emite, e a camada de 1 km exige `outputs/hexagonos_brasil_dashboard.parquet` (`app.py:242`, `pressao_1km.py:161-163`), que o exportador não produz. A AR usa o ramo antigo (**não verificado** se a VPS AR tem esse arquivo; o BLK-INTL-14 afirma que a AR "já pinta" a camada de 1 km) |
| `capacidade_default_concorrente_alunos` | float alunos/academia | hex7 | Divisor cai em `PERFIL.reguas.capacidade_concorrente`; em `pressao_1km`, em **2.500 literal** (`:201`) | Sim (`capacidade_concorrente_calibrada` = 1.070) |
| `staging/concorrentes_mapeados.parquet` | `rede, nome_unidade, lat, lng, hex_id_res7, status_registro, flag_coord_valida, foto` | ponto | Sem pins; a rota de 1 km dá 500 se faltar `status_registro` | Sim, OSM + web deduplicados, `status_registro` derivado (`exportar_piloto_ar.py:330-465`) |
| `CONC_ADENSAR_MAX = 2` | literal | — | — | Mesmo valor (BR) |

**Perfil:** `capacidade_concorrente`, `pin_margem_m` (AR = 0). **Falta no perfil:** os cortes de consumo do mapa (`CONSUMO_1KM_CORTES`, BLK-INTL-14) e `capacidade_concorrente` no payload do front.

### 2.4 Camada 4 — Momentum / crescimento

| Insumo | Tipo | Grão | Se faltar | AR entregou |
|---|---|---|---|---|
| `staging/crescimento_municipal.parquet`: `cod6` (6 dígitos, zfill) + `cres_chave_nome` (`UF\|NOME`), `cres_tendencia`, `cres_emp_pct`, `cres_saldo_empresas`, `cres_confiab`, `cres_salario`, `cres_salario_var`, `cres_setor`, `cres_uf_mediana`, `cres_dims`, `cres_series`, `v_frase` (`app.py:265-279`) | misto | município | Retorna `None` → passo 4 vazio, **sem erro** (só aparece em `/api/acessos/saude-artefatos`) | **Não** |
| `staging/crescimento_hex.parquet`: `hex_id`, `cres_hex_taxa`, `cres_hex_classe` (+ delta) | float/enum | hex7 | Passo 4 sem cor | **Não** (o `crescimento_hex_ar.py` existe no repo do Juan e não foi exportado) |
| Camadas de leitura AR (`_CAMADAS_AR`: obras, sociedades, emprego OEDE, SUBE) | num/texto por departamento | nível 2 | Somem | Sim, mas por **lista compilada na plataforma** (`app.py:910-925`), não por contrato genérico |

**Formato da chave:** o `cod_municipio` do hex é truncado em 6 caracteres e comparado com `cod6.zfill(6)`. Um código de 5 dígitos (AR, CO, MX) **nunca casa** (`"02007"` contra `"002007"`). O fallback por nome exige `cres_chave_nome = "<UF>|<NOME NORMALIZADO>"`.

**Perfil:** `fontes.crescimento.{nome,detalhe}` (só texto). Os textos "CAGED/RAIS/Receita" no funil e na metodologia **não** vêm daí.

### 2.5 Camada 5 — Fila de prioridade (índice de praça)

| Insumo | Fórmula | Se faltar | AR |
|---|---|---|---|
| `score_setor_2022_calibrado` (nota socio) + `oferta_efetiva_disponivel` (nota demanda) + `n_concorrentes_est` (desempate) | `indice = 0,70·socio + 0,30·nota_dem`; `nota_dem = 100·log10(clip(res, 2.000, 20.000)/2.000)/1` (`praca_indice.py:45-58`, `:108-131`); fila = top 10 | Sem colunas: índice NaN e fila vazia (`app.py:3008-3012`) | A superfície `oportunidades` está **desligada**. Se ligada: com residual em escala ~0,4×, `nota_dem` = 0 para residual entre 802,5 e 2.000 → a fila vira praticamente "só socio" (número achatado, silencioso) |

**Falta no perfil:** `DEMANDA_MIN/MAX_ALUNOS`, `PESO_SOCIO/DEMANDA`, `CONC_ADENSAR_MAX`, `FILA_MAX`.

### 2.6 Módulos laterais

#### a) Ficha do ponto + Relatório Pontual censitário (superfície `mapa`, gate `malha_municipal_disponivel`)

| Insumo | Tipo | Grão | Se faltar | AR |
|---|---|---|---|---|
| `ibge/municipios_<UF>.geojson` (`CD_MUN`/`codarea`/`cod_municipio`; UF tirada do nome do arquivo) | GeoJSON | nível 2 | `/api/ponto` 500 → por isso existe o gate (`acesso.py:186-193`) | Sim (P7 fechada, `escrever_malha`) |
| `outputs/setores_censitarios_2022_geo/uf=XX/cod_municipio=N/part-000.parquet` com `cod_setor, uf, cod_municipio, nome_municipio, nome_distrito, nome_bairro, nome_subdistrito, geometry_wkb (EPSG:4674 assumido), bbox_*, area_setor_m2, area_setor_km2_ibge, pop_total_setor_2022, domicilios_particulares_ocupados_setor_2022, renda_per_capita_setor_2022_calibrada, renda_per_capita_domiciliar_setor, avg_moradores_domicilio_setor_2022, renda_responsavel_media_setor_2022, densidade_pop_setor_hab_km2, score_setor_2022_calibrado, flag_renda_disponivel, flag_geometria_valida, qualidade_join_uf` | parquet WKB | unidade censitária | 404 `base_geo_ausente`. Sem `avg_moradores`, renda `null`. Sem `bbox_*`, bairros vazios **em silêncio** | Sim, radios INDEC com renda do hex redistribuída pela ponte de área; `renda_responsavel = renda × moradores` e uplift 1,0 no perfil (`exportar_piloto_ar.py:763-940`) |
| `renda_responsavel_media_setor_2022` × `uplift` × `FATOR_TEMPORAL` | moeda/mês | setor | Renda domiciliar errada (63% acima, se o uplift BR fosse aplicado) | Neutralizado por `uplift_composicao = 1,0` |
| Metas (`reguas.metas_big_numbers`, 7) | moeda / escala do país | — | Loader recusa ≤ 0 | 4 em escala AR; **SAM/residual = 2.000 em escala BR** |
| Critério do imóvel: `RENDA_MIN` | **R$ 4.500 literal** | — | — | **Reprova sempre** (§0.2) |
| `staging/hexagonos_mercado_mapeado.parquet` | ver 2.2 | hex7 | Página de residual vazia | Sim |
| Tiles de rótulo (`API_BASEMAP_LABELS_URL`) | env | — | PDF sem nome de rua (`censo_map.py:864-873`) | Ausente, aceito por aviso `mapa_sem_toponimo` (o front não o exibe) |

#### b) Relatório Municipal

- **Insumos:** os mesmos setores geo, mais `nome_bairro`/`nome_distrito` (cascata), malha, concorrentes e mercado.
- **Unidade:** `UNIDADE_HEXAGONO` já passada pelo web (`app.py:10564`), o que evita as duas páginas de bairro IBGE.
- **API:** o `_carregar_mercado_full` da API não sobe na AR.
- **Na AR:** o instituto vem do perfil; o ano "2022" e "CAGED/RAIS" estão fixos (§1.2).

#### c) Oportunidades imobiliárias (superfície `imobiliaria`; desligada na AR)

- **Insumo:** `oportunidades/viaveis.parquet` (env `MOTOR_OPORTUNIDADES_PATH`), com 31 colunas (`app.py:11328-11336`), joinadas ao M1 **pelo coletor**, um repo externo: `uf, municipio, hex_id, preco_aluguel, iptu, condominio, m1_residual_fitness, censo_renda_per_capita_hex…`. Mais os dossiês em PDF (`MOTOR_DOSSIES_DIR`).
- **Se faltar:** lista vazia com 200 ("Nada no recorte"), visível só em `saude-artefatos`.
- **Acoplamento:** o coletor imobiliário é brasileiro (portais BR); tudo é em R$ e `IPTU`; o front tem 17 "R$" na tela (`OportunidadesImobiliariasScreen.tsx`).
- **AR:** nada.

#### d) M&A / vulnerabilidade (pins de independentes e de redes)

- **Insumos:** `staging/vulnerabilidade_ma_nomeadas.parquet` (19 colunas, `app.py:1153-1173`) e `vulnerabilidade_ma_redes.parquet` (`:1317`). Eles derivam de snapshots semanais dos agregadores (`FONTES_VALIDAS = {totalpass, wellhub, unidades}`) e de `concorrentes_mapeados`.
- **Se faltar:** os pins somem em silêncio. Isso já acontece em produção BR: os artefatos `vulnerabilidade_ma_*` nunca chegaram ao ar, segundo a memória do projeto.
- **AR:** nada.
- **Para MX** (WellHub e TotalPass operam lá): plausível reaproveitar. Para CO/PE/PY: **não verificado** se há agregador com cobertura.

#### e) Viabilidade (superfície `viabilidade`)

- **Insumos de dado:** `base_calibracao_maduras` (curva m² → alunos da rede Ultra BR, `faixa_alunos_por_densidade`) e setores geo para o catchment.
- **Perfil:** `moeda.cambio_base`, `moeda.cambio_viabilidade`, `moeda.base_monetaria`, `avisos.viabilidade_tributo_provisorio`.
- **Mínimo aceitável:** sem câmbios, o ticket é digitado em reais. Sem aviso, nada é carimbado.
- **AR:** câmbios e aviso declarados. Premissas 100% BR (decisão 0.6, aceita como provisória). A zona morta em R$ dispara errado (§0.2).

### 2.7 O que o `perfil.json` precisa declarar (schema v1 efetivo do loader)

| Bloco | Campos lidos (obrigatórios salvo nota) | Validação no boot | Lacunas: o que deveria estar e não está |
|---|---|---|---|
| raiz | `schema_versao` (=1), `pais` (ISO-2), `nome`, `locale` (BCP-47 único) | regex | — |
| `moeda` | `codigo`, `simbolo`, `indicadores_renda`; opcionais `cambio_base`, `cambio_viabilidade` (`par` XXX/YYY, `valor` > 0), `base_monetaria` (AAAA-MM) | regex, positivo | `separador_milhar`/`separador_decimal` **declarados e não lidos** (`mascara.ts` fixo) |
| `bbox` | `lat_min/max`, `lng_min/max` | faixa e não degenerada | — |
| `vista_padrao` | `lat`, `lng`, `zoom` | número | — |
| `geocode` | `countrycodes` (`br`, `ar,…`), `idioma` (Accept-Language com lista e q), `regex_cp` (string ou null; compila) | regex | `api/geo.py` (Google) ignora o bloco |
| `fontes` | `censo.{nome,detalhe}`, `crescimento.{nome,detalhe}` | não vazio | Ano do censo e instituto por sigla (hoje deduzidos do texto entre parênteses); CAGED/RAIS fixos nos textos |
| `reguas` | `renda_abs_min/max`, `pop_abs_min/max`, `score_corte_quente`, `pop_min_acionavel` (int), `oferta_destaque_min`, `capacidade_concorrente`, `capacidade_unidade_alunos` (int), `uplift_composicao` > 0, `moradores_por_domicilio` > 0, `metas_big_numbers` (7, > 0, score ≤ 100); opcionais `faixas_renda {per_capita, domiciliar}` e `faixas_densidade` (2-6 faixas, rótulo ASCII, topo `null`), `pin_margem_m` ≥ 0 | degenerescência, log, positivos | **Mortos:** `score_pesos`, `taxa_fitness`, `capacidade_concorrente_unidade`, `faixas_mapa_*`. **Ausentes:** `renda_min_ficha` (hoje `RENDA_MIN` R$ 4.500), `renda_zona_morta_min` (R$ 500), `pop_zona_morta_min`, `demanda_min/max_alunos`, `peso_socio/demanda`, `conc_adensar_max`, `crit_ponto_score_min/conc_max`, cortes de consumo 1 km |
| `superficies` | lista ⊂ {mapa, oportunidades, imobiliaria, executiva, viabilidade} | vocabulário | — |
| `malha_municipal_disponivel` | bool | — | — |
| `avisos` | `{chave: {codigo, ativo, alerta, obrigatorio, onde ⊂ {tela,pdf,xlsx}, titulo, texto_curto, [texto_longo, texto_rodape]}}` | vocabulário | `mapa_sem_toponimo` (onde=tela) sem leitor no front |
| `operacao` | `pdf_concorrencia_max` ≥ 1 | ≥ 1 | `mem_limit_alvo` e `basemap_labels_url_obrigatoria` **mortos** (o compose é a fonte real) |
| (fora do perfil hoje) | — | — | Vocabulário de nível 1/2 ("estado/província/departamento"), bandeira, instituto e "pontos" (hoje em tabelas TS por sigla); regime tributário e premissas (BLK-INTL-11) |

**Higiene do perfil AR:** `_pendencias` ainda marca **P5 (metas) e P7 (malha) como `ausente`**, mas os dois já existem (metas preenchidas; commit `a794236` "P7 fechada"). A `_nota_metas` diz "NULL…" e está defasada. O BR declara `taxa_fitness: 0.1`, mas o calibrado real é 17,35% (DEC-060); o campo é morto e engana.

### 2.8 O que a Argentina entregou, por camada (resumo)

| Camada / módulo | Entregue | Faltou ou ficou no ramo antigo |
|---|---|---|
| Identidade | `hex_id`, `lat/lng`, `cidade`, `cod_municipio`, 24 partições | — |
| 1 Potencial | Score recomputado nas âncoras AR, pop do hex + captação, renda USD | `densidade_pop_setor_hab_km2` no hex (**não verificado**) |
| 2 Residual | `oferta_efetiva_disponivel`, `sam_fitness_potencial`, `oferta_consumida_mercado_estimada`, mercado único (de-para completado no Bloco B, ao contrário do início, quando 2 e 3 não tinham linha) | Ultra = 0 por construção |
| 3 Pressão | Capacidade calibrada 1.070, concorrentes OSM+web com `status_registro`, logos e fotos | `n_concorrentes_influencia_1km` e base nacional para o modelo de 1 km |
| 4 Crescimento | Camadas de leitura AR (obras, sociedades, emprego, SUBE) | `crescimento_municipal` e `crescimento_hex` (o join por `cod6` não casaria de qualquer forma) |
| 5 Fila | — | Superfície `oportunidades` desligada |
| Ponto / Pontual | Malha adm2, radios com geometria e renda redistribuída, moradores, metas (4 de 7 calibradas), faixas de renda | Rótulos de rua; critério de renda e zona morta em R$ |
| Municipal | Instituto e unidade hexágono | Ano e crescimento |
| Imobiliária / M&A / Executiva | — | Não se aplicam (sem coletor, agregador nem rede Ultra) |
| Viabilidade | Câmbios e aviso | Premissas próprias (BLK-INTL-11) |

---

## 3. TAREFA 3 — Pontos de acoplamento remanescentes, por severidade

Esforço grosseiro para 1 dev: **P** < 0,5 dia · **M** 0,5-2 dias · **G** 3-10 dias · **GG** > 2 semanas. "Já morde" = afeta a AR em produção hoje.

### 3.1 QUEBRA (erro, 4xx/5xx, ImportError, ou impossibilidade de subir o país)

| # | Ponto | Onde | Para quem | Esforço |
|---|---|---|---|---|
| Q1 | Validador e contrato de pacote inexistentes (o plano diz "inaceitável rodar o segundo país sem ele") | `scripts/validar_pacote_pais.py`, `docs/contrato_pacote_pais.md` | todo país novo | G (3-5 d) |
| Q2 | Exportador é por país e depende de módulo externo (`import nacional_academia`), mais `SIGLA_PROVINCIA`/`UF_BR` | `exportar_piloto_ar.py:155-178`, `:399` | CO/MX/PE/PY | G: generalizar em exportador com de-para declarativo por país, ou um por país |
| Q3 | Chave de partição `^[A-Za-z]{2}$`: códigos numéricos DANE/INEGI/UBIGEO exigem uma tabela de siglas inventada por país | `app.py:984` | CO/MX/PE/PY | P-M (afrouxar para `^[A-Za-z0-9]{2,6}$` com teste de traversal) **ou** só tabela no exportador |
| Q4 | Infra por cópia manual: compose, Caddy, Authelia, portal (`$br/$ar`), healthcheck, testes de compose literais; matchers N² | `docker-compose.ar.yml`, `portal/index.html:485-551`, `scripts/healthcheck_vps.sh:83-118`, `tests/unit/test_compose_ar.py` | cada país (CRÍTICO no guard) | M por país (copiar) · G para parametrizar uma vez |
| Q5 | Capacidade da VPS: tetos já somam 16 GB | `docs/deploy_piloto_web.md` §8 passo 10 | 3º país | Decisão de infra (rever tetos ou VPS nova) |
| Q6 | API/bot não servem outro país (`api/geo.py` BR, `_UFS` do bot, defaults `ibge`) | `api/geo.py:164`, `:342-391`; `telegram_bot.py:66-76`, `:680` | Se pedirem API/bot por país | G |
| Q7 | Banco de usuários sem país; AR no Authelia (dois cadastros) | `db/migracoes/003-usuarios.sql`, `006-…sql` | Se auth própria for estendida | G (decisão: banco por país ou coluna de país) |

### 3.2 NÚMERO OU VEREDITO ERRADO EM SILÊNCIO

| # | Ponto | Onde | Já morde na AR? | Esforço |
|---|---|---|---|---|
| S1 | Critério de renda da ficha do ponto em R$ 4.500 (`settings.RENDA_MIN`) + rótulo "R$" | `app.py:6478-6481`, `:6808` | **Sim**: reprova todo ponto | P: campo `reguas.renda_min_ficha` no perfil (BR = 4.500) + teste nos dois perfis |
| S2 | Zona morta: `RENDA_ZONA_MORTA_MIN = 500` R$ e `POP_ZONA_MORTA_MIN` literais → flag e selo DEMOGRÁFICO (E4) | `viabilidade_ponto.py:54`, `:72`, `:542`; `censo_report.py:1792-1803` | **Provável** (inferido, não medido) | P-M: perfil + medir na base AR |
| S3 | Choropleth de renda e densidade do MAPA web com cortes BR; o backend já serve as bandas de densidade (as de renda que ele serve são per capita) | `web/src/lib/colors.ts:358-377` | **Sim** | M (PR 2 previsto) |
| S4 | Renda USD rotulada "R$" (PontoScreen, DetalheRegiao, Recomendacao) e "$" de peso sobre USD (`UNIDADE_MOEDA`) e sobre reais (`fmtBrl`) | `PontoScreen.tsx:645-646`, `DetalheRegiao.tsx:67`, `Recomendacao.tsx:139`, `format.ts:169`, `recomendacao.ts:206`, `ViabilityCharts.tsx:1125` (o `BlocoViabilidadePonto.tsx` foi apagado no #457) | **Sim** | M; e estender a guarda anti-moeda para `components/` e `screens/` com allowlist da viabilidade |
| S5 | `mascara.ts` pt-BR fixo; perfil declara separadores sem leitor | `mascara.ts:81`, `:172`, `:187`, `:226`, `:248-257` | Não (es-AR coincide). **MX/PE sim** | M (o módulo é puro, tem testes) |
| S6 | Join do crescimento por `cod6` IBGE | `app.py:1104-1108` | Latente (a AR não tem o artefato) | P: chave declarada no contrato ou casamento por código inteiro |
| S7 | Âncoras e pesos da camada 5 (`DEMANDA_MIN/MAX_ALUNOS`, 0,70/0,30) e `CONC_ADENSAR_MAX`, `CRIT_PONTO_*` literais | `praca_indice.py:45-58`, `app.py:322-323`, `:339` | Quando `oportunidades` ligar | P-M: perfil + derivar de `capacidade_concorrente` |
| S8 | Metas SAM/residual da AR em escala BR (2.000) | `data/perfis/AR/perfil.json` (`metas_big_numbers`) | **Sim** (cards vermelhos) | P (só dado) |
| S9 | `CONSUMO_1KM_CORTES` ancorado em 2.500 (BLK-INTL-14 aberto) | `colors.ts:293` | Sim, se a camada existir na AR (**não verificado**) | P-M |
| S10 | Fallbacks BR "escondidos": `_K_CALIBRACAO_FALLBACK 1.0239`; `pressao_1km` `fillna(2_500)`; `TAXA_FITNESS_MERCADO_FALLBACK 0,10` (o `FATOR_TEMPORAL` 1,0 não é fallback (E0 da DEC-075): país sem `renda/fatores/<PAIS>/` não sobe, e o rótulo "julho/2022 (Censo IBGE)" da AR é declarado no arquivo dela) | `renda/hex.py:53` (re-exportado em `app.py:1884`); `pressao_1km.py:201`; `calcular_colunas_mercado.py:46` | Latente: dispara com pacote incompleto | P cada (fail-closed ou campo de perfil) + o validador (Q1) pega |
| S11 | Campos de perfil mortos que parecem ter efeito (`score_pesos`, `taxa_fitness`, `mem_limit_alvo`, `basemap_labels_url_obrigatoria`, `separador_*`, `capacidade_concorrente_unidade`, `faixas_mapa_*`) | `perfil.py:396-403` (regra "tolerado") | Engana quem edita o perfil | P: ligar o leitor ou mover para `_nota` |
| S12 | Viabilidade inteira em regime e moeda BR (provisório declarado e carimbado); furos fora de `Premissas` | `dimensionamento/config.py`, `simulador.py:464-473`, `:632-651`, `:999`; `payload_viabilidade.py` | Sim, **declarado** (aviso AR-VIAB-TRIB-PROVISORIO) | GG: 2-4 semanas de engenharia uma vez + 3-6 semanas humanas por país (BLK-INTL-11); furos + separadores ≈ 1 semana |
| S13 | Camada de 1 km dependente de `hexagonos_brasil_dashboard.parquet` (nome BR); país sem ele cai no ramo `consumo/capacidade` | `app.py:242`, `pressao_1km.py:161-163` | Sim (ramo antigo) | P (renomear ou declarar no contrato) |

### 3.3 COSMÉTICO (atribuição, rótulo ou vocabulário errado; não muda número)

| # | Ponto | Onde | Esforço |
|---|---|---|---|
| C1 | "IBGE", "Censo 2022", "CAGED/RAIS/Receita" em PDFs, metodologia e funil (a metodologia AR cita "malha do IBGE" e "CAGED") | `censo_report.py:3220`, `:3551`, `:4029`, `:4127`; `relatorio_municipal.py:3399-3951`, `:4114`; `app.py:2758`, `:2779`, `:3152`, `:3651`, `:3706`, `:4054`, `:5586`, `:5740-5744` | M (ler de `fontes`, mais campo `ano_censo`) |
| C2 | Tabelas de vocabulário só BR+AR (rodapé, bandeira) | `rodape-base.ts:36-60`, `Dock.tsx:38-48` | P por país (ou mover para o perfil) |
| C3 | "Escolha o estado", "Mediana do estado/UF", "Brasil" no início e no login (`MalhaBrasil`) | `Passos.tsx:113-128`, `HexMap.tsx:380`, `FichaHex.tsx:449-450`, `inicio.ts:170`, `:268`, `LoginScreen.tsx:207-562` | M |
| C4 | `localeCompare`/`toLocaleString('pt-BR')` literais (11 sítios); `lang="pt-BR"` | ver §1.2 | P |
| C5 | Sem i18n: 1,5 a 2,5 mil strings no front + 453 nos PDFs (124 `_ascii`) | todo `web/src`, `dashboard/*` | GG (BLK-INTL-12; decisão D4 de traduzir ou não) |
| C6 | Aviso `mapa_sem_toponimo` sem leitor; rótulos de rua inexistentes fora do BR (`brazil.mbtiles`) | front; `openmaptiles-infra` | P (aviso) · G (mbtiles por país) |
| C7 | Comentários e docs defasados: exportador (`:914-916`, `:1093-1095`); `_pendencias` P5/P7 do perfil AR; refs de linha em `docker-compose.ar.yml:45-53` e `docs/acesso_abas_ar.exemplo.json`; nomes `validar_brasil`, `noBrasil`, `'fora-do-brasil'` | vários | P |
| C8 | `_CAMADAS_AR` compilado na plataforma (schema de um país em `app.py`) | `app.py:910-925` | M (lista declarada no perfil ou no contrato) |
| C9 | Branding AR lido do diretório BR; `EDGE_URL` escalar (queda da borda AR não alerta) | `docker-compose.ar.yml:85`; `scripts/healthcheck_vps.sh:31` | P |

### 3.4 Ordem sugerida (para alimentar a Fase 0 parte B)

1. **Antes de qualquer 3º país, consertar o que já morde a AR.** É barato, cerca de 3-5 dias:
   - S1, S2, S8: réguas novas no perfil;
   - S3, S4: front lendo bandas e moeda certa, com a guarda anti-moeda ampliada;
   - S11: limpar campos mortos.
2. **Contrato + validador (Q1) e exportador genérico com de-para declarativo (Q2).** Fecham a classe "pacote incompleto vira número errado" (S6, S10, S13).
3. **Réguas do funil completas no perfil (S7, S9).** Pré-requisito para ligar `oportunidades` em qualquer país.
4. **S5 (máscara), antes de abrir México e Peru.**
5. **Infra parametrizada (Q4/Q5)** a partir do 3º país. Copiar compose e portal escala mal (N² matchers).
6. **BLK-INTL-11 (S12) e i18n (C5)** como trilhas próprias, com donos humanos.

> **Não verificado nesta fase:**
> - o conteúdo real da VPS AR (se há `hexagonos_brasil_dashboard.parquet`, crescimento ou camada de 1 km lá);
> - a taxa real de disparo da zona morta e do critério de renda na base AR (inferida do código e dos quantis do perfil, não medida);
> - as regras do Authelia e do Caddyfile real (arquivos cifrados ou gitignored);
> - o corpo de `gerarPdf`/`gerarXlsx` do front;
> - `densidade_pop_setor_hab_km2` no hex da AR;
> - a cobertura de WellHub e TotalPass em CO/PE/PY.
