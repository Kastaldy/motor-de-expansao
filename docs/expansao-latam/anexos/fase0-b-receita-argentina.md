# Fase 0 (parte B) — A receita da Argentina e o esforço real, como base de estimativa para CO, PY, MX e PE

- Data: 2026-10-16 · Somente leitura · Repositório da plataforma: `Kastaldy/motor-de-expansao` (worktree sincronizada com `origin/main`, último commit `a59b0e7`).
- Repositório do pipeline argentino: **`juancalu/motor-argentina` (privado, ACESSÍVEL e lido nesta tarefa via `gh api`)** — criado em 2026-07-14, último push em 2026-10-07, 95 commits, 29 PRs.
- **Não verificado:** `HANDOFF.md` e `docs/dicionario_dados.md` do "pacote" — o `HANDOFF.md` **não está versionado** no repositório do Juan (não aparece na árvore `git/trees/main?recursive=1`; o exportador cita `felipe/HANDOFF.md`, fora do git). O `dicionario_dados.md` existe (`docs/dicionario_dados.md`, 56 KB), mas não foi lido inteiro; os números dele aqui vêm das citações na plataforma. Estado **em produção** (VPS) não foi conferido: tudo que segue é o estado do código na `main` e o que os commits/DECs dizem que foi aplicado.
- Convenção: **[medido]** = conferido em arquivo, commit ou API nesta tarefa; **[declarado]** = afirmado em doc/commit, não reconferido; **[estimativa]** = inferência minha.

---

## 0. Resumo em cinco linhas

1. A Argentina custou **duas metades muito desiguais**: um **pipeline de dados** de ~7 semanas de uma pessoa (Juan, 2026-07-07 → 2026-08-24, repositório próprio) e uma **adaptação de plataforma** que o plano orçou em **5 semanas com 2 devs** e que foi **executada em ~1,5 dia de calendário** (2026-09-02 13:59 → 2026-09-03 19:30, Felipe + uma única sessão de Claude, 29 commits).
2. Antes da execução houve **~3 dias de planejamento escrito** (DEC-047, plano de 814 linhas, spec do Bloco A de 913 linhas, spec do portal de 995 linhas, dois `perfil.json`) e, depois da subida, uma **cauda de ~5 semanas** de correções (11 PRs, 2026-09-08 → 2026-10-06), quase todas do tipo "número errado que não dá erro".
3. Total multi-país rastreável na plataforma: **41 PRs, +20.842 / −1.416 linhas, 285 arquivos-alteração**, 2 autores de PR (Felipe/`Kastaldy`, Juan/`juancalu`) e Vinicius como coautor/revisor.
4. A plataforma ficou **quase toda reaproveitável** (perfil, gate de superfície, aviso carimbado, réguas e faixas por perfil, compose por país, portal). O que **não** ficou: o **contrato/validador de pacote** (não existe), o **exportador** (é argentino e já divergiu da cópia do Juan), o `_UF_RE` de 2 letras, a autenticação da AR (presa ao Authelia) e as **premissas financeiras** (a AR roda com tributo brasileiro).
5. Para o próximo país, o gargalo **não é código de plataforma**: é o **pipeline de dados** (renda modelada, concorrentes, malha) e a **calibração das réguas** — e o padrão de defeito dominante é **semântico** (mesmo nome de coluna, unidade diferente; mesma régua, moeda diferente), que nenhum teste de presença/tipo pega.

---

## 1. Fontes argentinas que substituíram as brasileiras, camada a camada

| Camada | Brasil (hoje) | Argentina | Onde está escrito |
|---|---|---|---|
| **Censo / população** | IBGE Censo 2022 por setor censitário (`v0001`, `v0007`, `v0005`) | **INDEC Censo 2022 por *radio censal*** — 66.502 radios, `POB_TOT_P` (pop. em domicílios particulares, 45,6 M), `VIV_TOT_P` (viviendas). Baixado do **GeoParquet do pacote `censoargentino` no Hugging Face** (`pedroorden/censoargentino`), porque o REDATAM travava e o INDEC suspendeu o download local em mai/2026. Variáveis detalhadas (NBI, educação, tenência) via `censoargentino.query` | `juancalu/motor-argentina:docs/fontes_dados_argentina.md` §"Censo 2022 por radio — RESOLVIDO" [medido]; `data/perfis/AR/perfil.json` `fontes.censo` [medido] |
| **Grade H3** | `hexagonos_dashboard_enriquecido` (H3 res 7) | **H3 res 7** por interseção radio×hex com alocação por área ponderada, corte densidade ≥ 3 hab/km² → **42.388 hexágonos, 44,77 M hab = 98,1 %** (`nacional_hexagonos.py`). Exportados ao piloto: **15.186 hexes em 24 partições** (saída do exportador) | `roadmap.md` BLK-AR-09 do Juan [medido]; commit `6b6fa58` [medido]; `docs/plano_multipais.md:645` |
| **Renda** | Censo IBGE (renda do responsável, `V06004`) × uplift × fator temporal; `k` nacional | **NÃO medida — MODELADA**: EPH 2025 (microdados INDEC, janela móvel de 4 trimestres, ~31 aglomerados) → `log(IPCF) ~ educação + tenência + tamanho + aglomerado`, clima educativo harmonizado ao `HOGAR_EDUHOG` do censo, **raking por região EPH**, aplicado ao radio e agregado ao hex. Saída em **3 unidades**: `renda_estimada_ars` (pesos constantes de **mai/2026**, deflator IPC), `renda_estimada_usd` (câmbio **BCRA 1.397,71 ARS/USD**) e `renda_estimada_canastas` (CBT GBA). Erro estrutural **±15 % na mediana, ±24 % no P90**; 85 % dos hexes com `renda_confianca = baixa`. **A plataforma lê a coluna em USD** (`renda_per_capita = renda_estimada_usd`) | `roadmap.md` BLK-AR-05 do Juan [medido]; `data/perfis/AR/perfil.json:16` (`indicadores_renda: "USD"`), `fontes._fonte_renda` [medido] |
| **Malha adm2** | `ibge/municipios_<UF>.geojson` (IBGE) | **georef/IGN** (`infra.datos.gob.ar/georef/*.geojson`): 24 províncias, **529 departamentos/partidos/comunas**, localidades. O exportador escreve 24 `ibge/municipios_<UF>.geojson` (o nome "ibge" ficou como convenção de pasta). Chegou em **2026-09-03** (P7) | `fontes_dados_argentina.md` (log de downloads) [medido]; commit `a794236` [medido]; `perfil.json:377` (`malha_municipal_disponivel: true`) |
| **Concorrentes** | GymScraping (90 coletores, cron semanal na VPS) + agregadores (WellHub/TotalPass) + `concorrentes_mapeados` | **Duas camadas complementares** (sobreposição de só ~14 %): (a) **web, 9 fontes** — WellHub (sitemap público, espinha dorsal, 68 % da camada web) + 8 sites de rede (SportClub, Smart Fit, BIGG, Megatlón, CORE, Fiter, ON FIT, Pratique), via `coletar_concorrentes_web.py`; (b) **OSM** (`leisure=fitness_centre`, `sport=fitness`, `amenity=gym`) via `classificar_concorrentes.py` sobre o PBF Geofabrik. Dedup < 150 m + nome parecido entre fontes diferentes. Orquestração: `atualizar_concorrentes.py` (8 passos, gate de 39 checagens). Cadência **semanal** (`coleta_semanal.ps1`, segunda 03:00 — **script PowerShell, máquina do Juan**). Capacidade calibrada **1.070 alunos** (400 real × fator de cobertura 2,675 = 8.662 academias estimadas / 3.238 vistas) contra 2.500 no BR | `juancalu/motor-argentina:docs/coleta_concorrentes_academias.md` §1, §2, §6 [medido]; `perfil.json:252` + `_nota_capacidade` [medido]; `docs/plano_multipais.md:32` (decisão 0.10) |
| **Crescimento** | CAGED, RAIS, Receita, satélite (camada municipal trimestral) | **Não há CAGED/RAIS.** `crescimento_hex_ar.py` (contrato BR `hex_id`, `cres_hex_taxa`, `cres_hex_classe`; corte 21,9 % no GBA contra 30 % no BR) + camadas de leitura próprias criadas depois (fases 3-17 do Juan, set/2026): OEDE (emprego/salário por departamento), RNS/IGJ (sociedades novas geocodificadas), permisos de obra INDEC/municipais, SUBE (fluxo de transporte), VIIRS (luz noturna — **reprovada** no backtest, +0,003 AUC). **Nenhuma entra no score**; 12 colunas chegam à ficha do hexágono como leitura (`_CAMADAS_AR`, `web/server/app.py:910-923`) | `docs/plano_multipais.md:33` (0.10b) [declarado]; commits do Juan 2026-09-04 → 09-14 [medido]; PR #365 [medido]; `perfil.json` `fontes.crescimento` (texto descreve a AUSÊNCIA, pendência P9) |
| **Mercado / SAM** | `taxa_fitness` calibrada em runtime (fallback 0,10) | `taxa_fitness = 0,078` **constante** (Radiografía del Fitness 2024); `sam_mercado_argentina.py`; `taxa_fitness_osm_calibrada = 0,3529` no parquet (4,5× o benchmark, gravada sem alertar — **não usar**) | `perfil.json` `_nota_taxa_fitness`, `_nota_capacidade` [medido] |
| **Âncoras monetárias** | R$ correntes + `FATOR_TEMPORAL_RENDA` | Mês-base **mai/2026**; IPC INDEC; canasta CBT GBA (485.029,58 ARS); câmbio BCRA 1.397,71; para a viabilidade, **PTAX BRL/USD 4,9837** (média mai/2026) | `perfil.json:23` (`cambio_viabilidade`), `metas_big_numbers._nota_renda_pc` [medido] |
| **Tiles / basemap** | `API_BASEMAP_TILES_URL` + `API_BASEMAP_LABELS_URL` (tileserver próprio) | **Nenhuma env de basemap no `docker-compose.ar.yml`** → fundo cai no CARTO global; **sem rótulos** (rua/bairro) nos PDFs — aceito por escrito (decisão 0.9; `.mbtiles` "de madrugada", nunca gerado) | `docker-compose.ar.yml` (bloco "O que NAO entra") [medido]; `docs/plano_multipais.md:31` |
| **Geocoder** | Nominatim `countrycodes=br`, `Accept-Language: pt-BR` | `perfil.geocode`: `countrycodes: "ar"`, `idioma: "es-AR,es"`, **validação do retorno contra `perfil.bbox`**; `regex_cp: null` (CPA argentino não honra o contrato do sítio que consome o campo — dívida declarada) | `perfil.json:116` + `_divida_regex_cp` [medido]; commit `18f3275` (#291) |
| **Divisão administrativa** | UF (27) / município | Província (24, incl. CABA) / departamento (= *partido* em BA, *comuna* em CABA). Siglas de **2 letras fabricadas** pelo exportador (`BS`, `CB`, `SF`…) porque `_UF_RE = ^[A-Za-z]{2}$` (`web/server/app.py:984`) e 5 siglas óbvias colidiam com UFs (PB, BA, RN, SC, SE) | `src/motor_expansao/pipelines/exportar_piloto_ar.py:148-193` [medido] |

---

## 2. O que foi ADAPTADO na plataforma

| Adaptação | Mecanismo | PR / commit | Reaproveitável? |
|---|---|---|---|
| **`perfil.json` por deploy** (DEC-047) | Dataclass congelada, loader **fail-closed**, resolvido **uma vez no import**; `_DEFAULT_DATA` (caminho do laptop) morto; BR com perfil próprio que reproduz as constantes | #288, #290; `src/motor_expansao/perfil.py` (913 linhas) | **Sim** |
| **Âncoras da régua absoluta como parâmetro** | `calcular_score_calibrado(..., ancoras=)` com default BR; AR: renda **US$ 350 / 1.000**, pop **1.000 / 100.000**, pesos 0,60/0,40, corte quente 30 | #289 (CRÍTICO); `perfil.json:226` | Sim (mecanismo); valores por país |
| **bbox + geocoder** | 6 cópias de bbox (eram 3 caixas distintas) + `countrycodes` unificadas no perfil; `/api/geocode` passa a validar o retorno | #291 | Sim |
| **Réguas do funil, Settings, painel de Metodologia** | `SCORE_CORTE_QUENTE`, `POP_MIN_ACIONAVEL`, fontes ("Censo 2022 (INDEC)"), frase da âncora com moeda do perfil | #292 | Sim |
| **Perfil no front** | `/api/me` serve bbox, locale, moeda, vista, réguas; fábrica de formatador | #293 | Sim |
| **Fio de alarme** | `tests/contracts/test_fio_de_alarme_pais.py`: zero `pais == "XX"` em `src/`, `web/`, `scripts/`; guarda anti-moeda (`R$` literal) | #294 | Sim |
| **Carimbo de país** | Deixa de deduzir por disjunção de siglas (`pais-da-base.ts` apagado) e lê o perfil — **a dívida nº 2 do plano foi paga já na AR**, não "antes da Colômbia" | #295 | Sim |
| **Uplift e moradores** | `reguas.uplift_composicao = 1.0` na AR (o exportador já escreve renda domiciliar; 1,632 inflaria +63 %); `moradores_por_domicilio = 2,5654` (pop/viviendas no radio) — **sem `MOTOR_PAIS`** | #297 (`3ceb999`, `8b69c6e`) | Mecanismo sim; valores por país |
| **Metas do semáforo (Relatório Pontual)** | 7 metas no perfil; AR: renda per capita = **1,2 canastas = US$ 416,42**, domiciliar US$ 1.068,28, população mantida | `8b69c6e` (#297); `perfil.json:353` | Mecanismo sim; calibração por país |
| **Exportador para dentro do repo** | `exportar_piloto_rep.py` → `src/motor_expansao/pipelines/exportar_piloto_ar.py` (1.100 linhas); score **recomputado** nas âncoras AR em vez de renomeado (12,9 % → 5,5 % de quentes; Spearman 0,615 em Córdoba) | #298 | **Não** — é argentino (siglas, colunas, caminhos) |
| **De-para de colunas** | `h3_id→hex_id`, `residual_membros→oferta_efetiva_disponivel`, `oferta_consumida_mercado→oferta_consumida_mercado_estimada`, `pop_total→pop_total_setor_2022` (ver §5, falso amigo) | #298, #299; `exportar_piloto_ar.py:203-263` | Padrão sim; tabela por país |
| **Moeda da renda ≠ moeda do país** | `Moeda.simbolo_renda()` / `moedaRenda()`: "R$" no BR, **"USD"** na AR; `brl()` intocado para viabilidade | #304 | Sim |
| **Vazamentos de nome** | `hexes_acionaveis_brasil` → `hexes_acionaveis_pais`; "Malha IBGE"/"fora do Brasil" → fonte e país do perfil | #303 | Sim |
| **Gate de superfície por país** | `SUPERFICIE_DA_ROTA` (conjunção, fail-closed, **404 com motivo**) + `ROTAS_QUE_EXIGEM_MALHA_MUNICIPAL` + `/api/me` interseccionando abas do cadastro com `perfil.superficies` | #305; `web/server/acesso.py:145-223` | Sim |
| **Aviso de tributo provisório carimbado** | `avisos.viabilidade_tributo_provisorio` (`AR-VIAB-TRIB-PROVISORIO`) em célula de alerta do XLSX e no rodapé de **todas** as páginas financeiras do PDF; `pdf_concorrencia_max` do perfil (BR 3, AR 1) | #307 | Sim |
| **Authelia / grupos** | Regra por host **com `subject`**: `group:expansao_br` (hosts BR) e `group:expansao_ar` (host AR); aplicado na VPS, backups cifrados no repo | #308 (Bloco D), #310 | Sim (um grupo por país) |
| **Compose AR** | `docker-compose.ar.yml` **novo** (o BR fica intacto), serviço único `web_ar`, mesma imagem/digest, `name:` próprio, rede externa `app_app_net`, **`MOTOR_CADASTRO_DIR` + `MOTOR_ACESSO_FAIL_CLOSED=1`** (evita o fail-open), `mem_limit 2g` | #309, #311; `tests/unit/test_compose_ar.py` | **Molde** — um arquivo por país |
| **Caddy / DNS / healthcheck** | `deploy/caddy/piloto-ar.Caddyfile.template`; `piloto-ar.ultra-expansao.tech`; container AR no array do `healthcheck_vps.sh` (o `EDGE_URL` segue escalar) | #309; `docs/deploy_piloto_web.md` §8 | Molde |
| **Malha adm2 + rotas de ponto** | `malha_municipal_disponivel: true` libera `/api/ponto`, `/api/resolver-ponto`, `/api/relatorio/pontual` e `/api/relatorio/municipal` | #312 | Mecanismo sim |
| **Portal de seleção de país** | Raiz `ultra-expansao.tech` lê `Remote-Groups`; 302 + `no-store`; `sem-acesso.html`; aplicado na VPS em 2026-09-03 (aceite 8/8) | #313, #316 | Sim |
| **Logos e fotos AR** | Mount `/opt/motor-expansao-ar/concorrentes`; logo por slug no PDF | #314, #319 | Sim |
| **Faixas de cor (renda/densidade) pelo perfil** | `reguas.faixas_renda` (6 faixas ancoradas na canasta: até US$ 340 … >US$ 850) e `faixas_densidade`; `/api/me` serve bandas já resolvidas; corrigido bug que pulava o 5º degrau no BR | #320, #353 | Sim |
| **Piso de destaque** | `oferta_destaque_min = 802,5` = 0,75 × 1.070 (prioridade "alta" do pipeline AR), em vez do 2.000 brasileiro | #323 | Mecanismo sim; valor por país |
| **Camadas de leitura AR na ficha** | `_CAMADAS_AR` (12 colunas) em `ctx_mun`; ausência apaga o cartão (no BR fica vazio) | #365 | **Parcial** — tabela com nome de país dentro de `app.py` |
| **Aba Acessos na AR** | `MOTOR_ACESSOS_ADMIN_USUARIOS_AR` própria (os dois composes leem o mesmo `.env`) | #366 | Molde |
| **Pins dentro do município** | `reguas.pin_margem_m` (BR 2.000 m; **AR 0**) — comunas de CABA são pequenas e coladas (Comuna 1: 140 pins, 76 de fora) | #370; DEC-035 emenda 2 | Sim |
| **Relatório Municipal em USD/INDEC + barrios** | `_renda` com `simbolo_renda()`, 16 citações "IBGE" lidas de `fontes.censo.nome`; exportador passa a escrever colunas de bairro nos radios | #373, #374 | Sim (PDF); exportador por país |
| **Viabilidade com moeda local de entrada** | Ticket/aluguel/obra digitados em **pesos ou dólares**, convertidos a **reais** (`cambio_base` + `cambio_viabilidade`); a conta continua em BRL com tributo BR | #446 (substitui #443/#444 do Juan) | Sim, mas é ponte até o BLK-INTL-11 |

---

## 3. O que ficou DE FORA ou provisório (estado em 2026-10-16, pela `main`)

| Item | Estado | Evidência |
|---|---|---|
| **Superfícies AR** | `["mapa","viabilidade"]`. **Bloqueadas (404 nomeado):** Modo 3 do funil (`/api/estados`, `/api/hexagonos` → `oportunidades`), dossiê imobiliário (`imobiliaria`), Visão Executiva (`executiva`). **Liberadas desde 2026-09-03:** ponto, Relatório Pontual e Municipal (malha chegou). **Atenção:** o funil **municipal** (Modo 2) mora em `/api/municipio/{uf}/{mun}` → `montar_funil` (`web/server/app.py:6906-6924`), gated por `mapa` — logo **o funil por município está no ar na AR**, ao contrário do que o plano dizia | `perfil.json:372`; `acesso.py:145-172` |
| **Tributo brasileiro na viabilidade** | **Provisório e ativo**: conta em reais, Lucro Presumido/encargos/ticket BR, aviso `AR-VIAB-TRIB-PROVISORIO` carimbado. BLK-INTL-11 (premissas por país) **não iniciado** — orçado em 2-4 semanas de engenharia (uma vez) + **3-6 semanas humanas por país** | `perfil.json:382`; `docs/plano_multipais.md:604-615` |
| **Rótulos de mapa (tiles)** | Sem `API_BASEMAP_LABELS_URL` no compose AR → PDFs pontuais/municipais AR **sem nome de rua/bairro**; `perfil.operacao.basemap_labels_url_obrigatoria: false` **não tem leitor** no `perfil.py` (campo tolerado, inerte) | `docker-compose.ar.yml`; `perfil.json:417`; `grep` em `src/` sem ocorrência |
| **i18n** | **Fechado pelo dono: português, "não se mexe até eu passar a ordem"** (D4, 2026-09-02). BLK-INTL-12 (453 strings de PDF + ~2.400 linhas de front) é o último bloco | `docs/plano_multipais.md:776-779` |
| **Contrato e validador de pacote** | **NÃO existem** (`scripts/validar_pacote_pais.py`, `docs/contrato_pacote_pais.md` — `ls` falha). O plano diz "aceitável com um país; **inaceitável rodar o segundo**" | `docs/plano_multipais.md:394`, `:792` |
| **Baseline de desempenho** | `data/reports/perf_baseline_piloto_web.md` **não existe**. Medição pontual feita no Bloco E: RSS 82→108 MiB, p95 BR sem degradação (mediana 1,7 ms) | `perfil.json` `operacao._nota_mem` |
| **`_UF_RE` / siglas fabricadas** | Continua `^[A-Za-z]{2}$` (`web/server/app.py:984`); BLK-INTL-04 não feito | — |
| **Operação em matriz** | `EDGE_URL` escalar (`scripts/healthcheck_vps.sh:31`); relatório de acessos e `/acessos` do bot leem só a trilha BR | `docs/deploy_piloto_web.md` §8 (dívida declarada) |
| **Cache em bytes (BLK-INTL-06)** | Não feito; "a partir do terceiro país deixa de ser adiável" | `docs/plano_multipais.md:392` |
| **Autenticação AR** | **Presa ao Authelia** (DEC-067, emenda 25/09): `web_ar` não tem banco; o BR tem a auth própria pronta (P19), mas o corte ainda depende do banco na VPS e, em produção, o Authelia autentica BR e AR (DEC-067, emenda de 14/10/2026). Dois cadastros de usuários (banco BR + `users_database.yml`, que hoje autentica as duas instâncias) — "quem sai da empresa tem de sair dos dois" | `docs/decisions/DEC-067.md:198-216` |
| **Cadência de concorrentes AR na VPS** | Decisão 0.10 mandava migrar a coleta semanal da máquina do Juan para a VPS e expor a data da última coleta no `/api/health`. **Nenhum rastro na plataforma** (nenhum cron/script/doc fora do plano e da DEC-047; `app.py` não expõe data de coleta no health). **Não verificado na VPS** — provável que ainda rode no Windows do Juan (`coleta_semanal.ps1`) | `grep` em `scripts/`, `docs/infra_producao.md` [medido: ausência] |
| **Agregadores / camada 4 do funil (crescimento municipal) AR** | Sem dono (D7b) | `docs/plano_multipais.md:795` |
| **`CONSUMO_1KM_CORTES`** | Literal `[625, 1250, 2500, 5000]` ainda em `web/src/lib/colors.ts:293` — legenda "até 1 unidade" mente na AR (1.070) | BLK-INTL-14 aberto |
| **CPA (código postal)** | `regex_cp: null` | `perfil.json` `_divida_regex_cp` |
| **API GeoEspacial + bot Telegram** | Só BR (fora da trilha multi-país por decisão) | plano §3 "NÃO ESTÁ" |
| **Marca de "não calibrado" por linha de premissa** | Só o aviso de país inteiro | BLK-INTL-11 item 6 |

**Drift de documentação encontrado (não é defeito de produto, mas engana o próximo país):**
- `tasks/backlog.md`: BLK-INTL-A1, B1, C1 e C2 ainda com **"Status: Pendente"** (linhas ~4226, 4335, 4416, 4464) e BLK-INTL-13 "em andamento", embora mergeados e aplicados em 2026-09-02/03; **nenhum bloco BLK-INTL em `tasks/completed.md`**.
- `data/perfis/AR/perfil.json` `_pendencias`: P5 e P7 ainda `estado: ausente`, contradizendo `metas_big_numbers` preenchido e `malha_municipal_disponivel: true`; `data/perfis/LEIA-ME.md:210` diz "9 itens (8 abertos, 1 decidido)".
- `docker-compose.ar.yml`: comentário diz `mem_limit` "PROVISÓRIO E NÃO MEDIDO" e que o PDF pontual está "bloqueado pela malha até o P7" — ambos superados em 2026-09-03.

---

## 4. Linha do tempo e esforço

### 4.1 Linha do tempo

| Data | Marco | Fonte |
|---|---|---|
| ≤ 2026-07-07 | Juan começa downloads (OSM, georef, radios, EPH) | `fontes_dados_argentina.md` (log "atualizado em 2026-07-07") |
| 2026-07-08 | Decisões de escopo do pipeline (renda via EPH, piloto CABA+GBA, idioma pt) e **expansão nacional** (42.388 hexes) | `roadmap.md` BLK-AR-00/09 |
| 2026-07-14 | 1º commit do repo `motor-argentina` (+6.149 linhas, 41 arquivos — dump do trabalho anterior) | `gh api commits/b64abc9` |
| 2026-07-20 → 07-23 | Gate de dados, coleta web de concorrentes, relatório pontual, "pacote" + HANDOFF | commits do Juan |
| 2026-08-24 | **Exportador no layout do piloto BR** — o piloto roda a AR "sem uma linha alterada" (com 12 patches fora do repo) | commit do Juan; `piloto_rep/LEIA-ME.md` |
| 2026-08-26 → 08-31 | 1º PR multi-país na plataforma (**#270**, carimbo de país) e a série de patches do Juan entrando como #281-#283 | prs.tsv |
| 2026-08-31 | **DEC-047 aprovada**; plano, specs e perfis escritos (commit `ad1aa53` só entra em 09-02 10:53) | `docs/decisions/DEC-047.md` |
| 2026-09-02 13:59 → 16:44 | **Bloco A** inteiro (9 PRs) | git log |
| 2026-09-02 17:10 → 09-03 12:04 | **Bloco B** (5 PRs) | git log |
| 2026-09-03 13:43 → 15:37 | **Blocos C e C+** | git log |
| 2026-09-03 16:23 | **Bloco D** aplicado na VPS | `d3d173a`/#308 |
| 2026-09-03 16:48 → 18:23 | **Bloco E**: compose AR, Caddy, DNS, subida, RSS medido; **P7 (malha) fecha no mesmo dia** | #309-#312 |
| **2026-09-03** | **ARGENTINA NO AR** em `piloto-ar.ultra-expansao.tech` (backlog: "Feita em 2026-09-03 — stack AR no ar") + portal na raiz (aceite 8/8) | `tasks/backlog.md` BLK-ARG-E1; commit `7c6814a` |
| 2026-09-08 | Incidente: **bot em crash loop** (DEC-049) no 1º deploy da API pós-Bloco A | #321 |
| 2026-09-08 → 10-06 | Cauda de correções AR (faixas, piso de destaque, camadas, pins, relatório municipal, moeda da viabilidade) | 11 PRs |
| 2026-09-28 | Incidente de login (P19, #425) — não é da AR, mas a AR ficou dependente do Authelia | DEC-067 |
| 2026-10-16 | Hoje: 6 semanas com a AR no ar | — |

**Intervalos:** do 1º PR multi-país (#270, 08-26) à AR no ar: **8 dias**. Da DEC-047 à AR no ar: **3 dias**. Do início do pipeline (≤ 07-07) à AR no ar: **~8,5 semanas**. Da AR no ar até hoje: **~6 semanas**, das quais ~5 com correções.

### 4.2 Esforço na plataforma, por bloco (PRs mergeados)

| Grupo | PRs | Linhas (+/−) | Arquivos | Calendário real | Autores de PR |
|---|---|---|---|---|---|
| Série de patches do Juan (pré-plano) | #270, #281-#283 | +923 / −102 | 21 | 08-26 → 08-31 | juancalu, Kastaldy |
| Plano + specs + perfis | #286, #287 | +5.579 / −7 | 15 | ~08-31 → 09-02 (≈3 dias) | Kastaldy |
| Bloco A | #288-#296 (9) | +5.542 / −414 | 106 | **~3 h** (09-02) | Kastaldy |
| Bloco B | #297-#299, #303, #304 | +2.164 / −62 | 32 | **~1 dia** (09-02 → 09-03) | Kastaldy |
| Blocos C + C+ | #305, #307 | +1.144 / −19 | 17 | **~2 h** | Kastaldy |
| Bloco D | #308 | +225 / −110 | 2 | horas (VPS) | Kastaldy |
| Bloco E (+P7, logos) | #309-#312, #314 | +580 / −143 | 16 | **~2 h** + medição | Kastaldy |
| Portal (BLK-INTL-13) | #313, #316 | +702 / −133 | 10 | ~1 h | Kastaldy |
| Cauda pós-subida | #319-#323, #353, #365, #366, #370, #373, #374, #446 | +3.983 / −426 | 66 | 09-08 → 10-06 | juancalu, Kastaldy |
| **Total** | **41** | **+20.842 / −1.416** | **285** | — | 2 (+ Vinicius coautor) |

Notas: (i) 29 dos commits de A→portal saíram de **uma única sessão de Claude** (`session_01Cgw6b5…`); (ii) `Kastaldy` = Felipe (git user "Felipe Castaldi"); (iii) linhas incluem testes e docs — o código de produção é uma fração [estimativa: ~40-50 %, não medido]; (iv) PRs fechados sem merge (#266, #443, #444) não entram na soma.

### 4.3 Esforço no pipeline do Juan (repositório externo)

| Métrica | Valor | Natureza |
|---|---|---|
| Calendário até "pacote pronto para o piloto" | ≤ 07-07 → 08-24 ≈ **7 semanas** | medido (datas de commit/log) |
| Commits / PRs (até 10-07) | 95 / 29 (71 commits só em setembro — fases 2-17 de enriquecimento, **não** necessárias para subir) | medido |
| Pessoas | 1 (Juan), com sessões de Claude (assinatura nos commits) | medido |
| Código | 104 arquivos `.py` ≈ 1,66 MB (≈ 35-45 mil linhas) + 33 `.md` ≈ 0,55 MB | medido (bytes); linhas = estimativa |
| Horas-pessoa | **não disponível** | — |

### 4.4 Plano × real

| Bloco | Estimativa do plano (§5.0.3) | Real | Razão real/plano |
|---|---|---|---|
| A | 7-11 dias · 1 dev | ~3 h | ~1/25 |
| B | 4-6 dias + 2-3 de ida-e-volta com o Juan | ~1 dia | ~1/7 |
| C | 3-4 dias | ~1,5 h | ~1/20 |
| C+ | 1 dia | ~1 h | ~1/8 |
| D | 1 dia | horas | ~1/2 |
| E | 3-4 dias + 24 h de observação | ~2 h + medição (24 h de observação **não verificada**) | ~1/10 |
| **Total** | **5 semanas com 2 devs (6-8 com 1)** | **~1,5 dia de calendário** (+ ~3 dias de spec antes, + ~5 semanas de cauda depois) | — |

**Leitura honesta:** o plano estimou em **dias-dev humanos**; a execução foi feita por um humano decidindo + agente de IA codando, sobre uma **spec executável** (37 sítios numerados, ordem de 10 commits). A velocidade de execução não é transferível sem spec equivalente. E o plano **não orçou a cauda**: 11 PRs em 4 semanas, a maioria corrigindo número errado silencioso.

### 4.5 Separação PLATAFORMA (uma vez) × POR PAÍS (repetível) — base para CO/PY/MX/PE

**Já pago, reaproveitável:** perfil + loader + fio de alarme; âncoras/faixas/metas/pin_margem/piso de destaque como campos do perfil; gate de superfície + malha; aviso carimbado; moeda da renda ≠ moeda do país; geocoder/bbox; portal; molde de compose/Caddy/Authelia; faixas de cor resolvidas no `/api/me`.

**Plataforma ainda devida ANTES do 2º país (uma vez)** — [estimativa, ritmo da AR com spec + IA]:

| Item | Por quê | Estimativa |
|---|---|---|
| `validar_pacote_pais.py` + `contrato_pacote_pais.md` **com checagem semântica** (não só nome/tipo: soma de população vs censo, moeda declarada, escala de score) | Dívida nº 8; o "falso amigo" `pop_total` passaria num validador só de tipo | 1-3 dias |
| Exportador **genérico** ou por país com contrato único — e **resolver a divergência atual** (a cópia da plataforma não tem as 14 colunas de camadas que a do Juan tem) | Hoje são dois exportadores AR divergindo | 2-5 dias |
| `_UF_RE` afrouxado (BLK-INTL-04) | DANE/INEGI/INEI/DGEEC usam códigos numéricos | 0,5-1 dia (CRÍTICO, sink de traversal) |
| `mascara.ts` com separador por locale (R10) | **Obrigatório para MX e PE** (ponto decimal): "35,000" vira 35 | 0,5 dia |
| `CONSUMO_1KM_CORTES` e outros literais TS ancorados em 2.500 | BLK-INTL-14 | 0,5 dia |
| Banco/auth própria por instância **ou** decisão de manter Authelia para não-BR | DEC-067: dois cadastros de usuário hoje | a decidir |
| Operação em matriz (healthcheck, trilha, deploy) | Com 3+ instâncias, "toda mudança de infra feita N vezes" | 3-5 dias |
| Cache em bytes + baseline de desempenho | "Inadiável a partir do 3º país"; 4 vCPU compartilhados | 3-5 dias |
| Premissas financeiras por país (BLK-INTL-11) | Sem isso, todo país novo herda tributo BR | 2-4 semanas eng. (uma vez) |

**Por país (repetível):**

| Item | Referência AR | Estimativa por país [estimativa] |
|---|---|---|
| Pipeline de dados (censo fino → H3 → renda modelada → concorrentes → mercado) | ~7 semanas, 1 pessoa + IA | 5-9 semanas conforme fonte (ver §6.5 do plano: CO ≈0,8, MX ≈1,0-1,3, PE ≈1,1, PY ≈0,7 "AR") |
| Malha adm2 em GeoJSON na convenção | georef/IGN, chegou depois do resto | 1-3 dias se pública; **PE: cartografia de manzana do INEI pode exigir solicitação** |
| `perfil.json` + decisões P1-P9 (âncoras, metas, faixas, piso, margem, moradores, uplift, moeda do indicador) | 528 linhas, decisões em ~3 dias | 2-4 dias (decisões do Felipe são o gargalo) |
| Exportador / de-para | 1.100 linhas | 2-5 dias se não houver exportador genérico |
| Infra (DNS, compose, Caddy, grupo Authelia, cadastro, scp, medição de RSS/p95) | ~1 dia | 1 dia + 24 h de observação |
| Cauda de correções pós-subida | 11 PRs / ~4 semanas | **orçar 2-4 semanas** de atenção intermitente |
| Premissas financeiras locais (se quiser viabilidade sem carimbo) | não feito | 3-6 semanas humanas (assessor fiscal) |
| Cadência de concorrentes (coleta semanal) | ainda fora da VPS [não verificado] | 1-2 semanas para montar coletores do país |

---

## 5. Problemas que apareceram, e a lição de cada um

| # | Problema | Sintoma medido | Conserto | Lição para o próximo país |
|---|---|---|---|---|
| 1 | **`pop_total` é um falso amigo** (`94bdd40`, #299) | No BR é a pop. do **município** repetida por hex (somada: 79,3 bilhões, 391× o Brasil); na AR é a pop. do **hexágono**. `/api/estados` dava **500**, KPI de pop. vinha `null` | Exportador escreve em `pop_total_setor_2022`, não emite `pop_total` | Mesmo nome ≠ mesma semântica. O contrato precisa de **asserção de agregado** (soma ≈ censo), não só presença/tipo |
| 2 | **Score percentil renomeado como absoluto** (#298) | Renomeado: 12,9 % de quentes; recomputado: 5,5 % (BR: 2,2 %); Spearman 0,615 | Recomputar com `calcular_score_calibrado` nas âncoras do país | Nunca herdar score do pipeline do país; recomputar na régua da plataforma |
| 3 | **Uplift brasileiro sobre renda já domiciliar** (`3ceb999`) | Renda do Relatório Pontual **+63 %** | `uplift_composicao = 1.0` no perfil (não `MOTOR_PAIS`) | Cada fator de renda do BR tem de ser declarado e justificado por país |
| 4 | **Renda em USD rotulada "$"** (#304) | "$ 508" lido como pesos = 1.397× menor | `simbolo_renda()` separado da moeda do país | Três moedas convivem (país, indicador, viabilidade); declarar as três no perfil |
| 5 | **Vazamentos "brasil"/"IBGE"** (#303) | Chave `hexes_acionaveis_brasil`; erro "Malha municipal IBGE … fora do Brasil" na AR | Ler do perfil | Varrer literais de país/instituto antes de subir (hoje há 16 citações IBGE só no municipal — #374) |
| 6 | **Faixas de renda em R$** (#320) | 99,88 % da pop. AR caía na 1ª faixa; legenda com 4 cores que nunca ocorriam | `reguas.faixas_renda` (canasta) | Toda régua visual absoluta é régua de país |
| 7 | **Bug do 5º degrau de cor** (#353) | No BR, 17,47 % dos setores de SP com cor errada | Atribuição por prefixo | Generalizar um literal para N países expõe bugs do caso único |
| 8 | **Piso de destaque inalcançável** (#323) | 398 de 434 municípios com camadas "Demanda não atendida"/"Pressão" vazias | 802,5 = 0,75 × capacidade AR | Pisos em alunos dependem da capacidade por concorrente do país |
| 9 | **Pins de comunas vizinhas** (#370) | Comuna 1 de CABA: 140 pins, 76 de fora | `pin_margem_m = 0` | Geografia administrativa muda o raio certo (DEC-035 emenda 2) |
| 10 | **Relatório Municipal 500** (#374) | `'numpy.float64' object has no attribute 'dropna'` — coluna ausente vira escalar; bairros vazios em silêncio | `_coluna_numerica`; exportador escreve colunas de bairro | Superfície liberada sem teste com dado real do país quebra no 1º clique |
| 11 | **Camadas AR descartadas** (#365) | 12 colunas no volume não chegavam à tela (`_COLS_DESEJADAS` descarta em silêncio) | `_CAMADAS_AR` | O filtro defensivo de colunas esconde dado novo; listar o que o país traz a mais |
| 12 | **Bot em crash loop** (DEC-049, #321) | `PerfilInvalidoError … site-packages/.../BR/perfil.json` no 1º deploy da API pós-Bloco A | `MOTOR_DATA_DIR` + bind do perfil no serviço `telegram-bot` | Loader fail-closed no import: **todo** serviço que importa o pacote precisa do perfil; testar compose por serviço |
| 13 | **Filtro de publish do CI** (#296) | `perfil.py` fora do path-filter das duas imagens | Incluído | Módulo novo de núcleo precisa entrar nos path-filters no mesmo PR |
| 14 | **Teste envenenando o cache do perfil** (`8737892`, Vinicius) | Contrato passava sozinho e falhava (`'Argentina' == 'Brasil'`) após outro arquivo; passava "por ordem alfabética" | Fixture autouse + contrato AST contra nova função cacheada que alcance `PERFIL` | "Um país por processo" vale também para a suíte; testes de país em subprocesso |
| 15 | **Moeda na viabilidade** (#443/#444 → #446) | PR com base errada (CI nunca rodou); reverteria a DEC-068 **no Brasil**; chave `obra` duplicada; ticket de studio ~280× maior | Cherry-pick sobre `main` + 10 guardas de fonte | Mudança "só para a AR" em tela compartilhada atinge o BR; exigir base `main` e CI |
| 16 | **Fail-open de acesso no compose novo** (prevenido no Bloco E) | Sem `MOTOR_CADASTRO_DIR`, `ABAS_VALIDAS` inteira para todo autenticado | `MOTOR_CADASTRO_DIR` + `MOTOR_ACESSO_FAIL_CLOSED=1` + `test_compose_ar.py` | O teste do compose BR lia caminho literal; compose novo precisa de teste próprio |
| 17 | **Aba Acessos desligada na AR** (#366) | env não propagada; `/api/acessos/*` 404 | `MOTOR_ACESSOS_ADMIN_USUARIOS_AR` | Variáveis por instância não podem reaproveitar a do BR no mesmo `.env` |
| 18 | **Login (#425, P19)** | Troca seca de autenticação derrubou o login de todos (rollback) | Authelia como reserva | Para a AR: decidiu-se mantê-la no Authelia (DEC-067) → **dois cadastros de usuário**; decidir auth antes de cada país |
| 19 | **Colisão de número de DEC** | DEC-046 → DEC-047 (5ª colisão do repo) | Renumerada | Pegar o ID no momento do commit |
| 20 | **Fork fora do repo** | 12 patches do Juan em `piloto_rep/patches`, reaplicados por script; ainda resta 1 na prévia argentina | Acordo 0.11; #281-#283 | Prévia local ≠ produção; acordar a fronteira de repositório no dia 1 |
| 21 | **Exportador duplicado** [medido nesta tarefa] | A cópia da plataforma (`exportar_piloto_ar.py`) **não tem** as 14 colunas `sube_/oede_/soc_hex/mun_permisos` que a do Juan tem; a base em produção carrega essas colunas (#365) → [inferência] **a produção é gerada pelo exportador do Juan, não pelo da plataforma** | — | O objetivo "exportador no repo" (R5) só vale se for **a única** cópia |
| 22 | **Ambiente local** | DLL do `h3` bloqueada pelo Controle de Aplicativo do Windows (`WinError 4551`) — testes com h3 só rodaram no CI | — | Garantir CI como gate; não confiar em "passou local" |
| 23 | **Coleta parada 36 dias** (pré-plano) | Motor serviu retrato velho como atual | Decidido expor data no `/api/health` — **não implementado** [medido: ausência] | Data da última coleta na tela/health por país |

---

## 6. Premissas frágeis — onde a analogia BR → AR quebrou

1. **"O funil não sobe no dia 1."** Falso na prática: o funil **municipal** é servido por `/api/municipio` (aba `mapa`); o gate só fechou o Modo 3. Foi por isso que o piso de destaque (#323) virou problema dias depois. → Mapear rota por rota o que a superfície "mapa" realmente entrega.
2. **"Ponto e municipal ficam fora."** Mudou em 24 h: Felipe corrigiu a leitura em 09-02 e a malha chegou em 09-03. O plano inteiro foi reescrito duas vezes em 3 dias (0.6, 0.14). → Escopo do dia 1 é volátil; o mecanismo (gate) é que precisa ser firme.
3. **Renda medida × renda modelada.** No BR o censo mede renda; na AR é EPH modelada (±15 %, 85 % baixa confiança) e **comprimida** (p95/p05 = 2,2 contra 6,4 no BR) — a âncora de teto teve duas leituras que discordavam 1,6×. → Nos 4 países a renda também será modelada (GEIH, ENIGH, ENAHO, EPHC); a âncora é decisão, não transcrição.
4. **Score percentil × absoluto.** O pipeline do país produz percentil com pesos invertidos (0,40/0,60); a plataforma usa régua absoluta 0,60/0,40. A escolha "absoluto × percentil" moveu o ranking **dez vezes mais** que qualquer âncora (correlação 0,46).
5. **Unidade da âncora de população.** Circulou que a âncora BR era de setor; era de hexágono — o erro inverteu uma conclusão do plano por um dia. → Conferir a unidade **da linha**, não o nome da coluna.
6. **Capacidade e penetração.** 1.070 alunos (parque de academias menores, motor vê 37 %) contra 2.500; `taxa_fitness` constante (0,078) contra calibrada no BR; taxa OSM calibrada de 0,3529 inutilizável. → Cada régua em "alunos" é de país.
7. **Domicílio.** INDEC publica `viviendas` (inclui vagas), não `hogares` por radio: moradores/domicílio 2,5654 (consistência de cadeia) em vez de 2,8623 (fidelidade à definição). → A definição censitária muda o denominador.
8. **Geografia administrativa.** Comunas de CABA minúsculas → margem de pins 0; siglas de 2 letras fabricadas (5 colidiam com UFs); `departamento` como "município". → Colômbia (departamento/município), México (estado/municipio/AGEB), Peru (departamento/provincia/distrito) e Paraguai (departamento/distrito) têm hierarquias diferentes; a "UF" da plataforma é sempre o nível 1.
9. **Concorrência.** Não existe GymScraping no país: 9 fontes + OSM, WellHub estrangula com 12 threads (perdeu 2.289 de 2.366 fichas), cadência semanal no laptop de uma pessoa. → Coleta é custo **recorrente** por país, não entrega única.
10. **Crescimento.** Sem CAGED/RAIS; o substituto (OEDE, IGJ, SUBE, permisos) virou 12 colunas de leitura **fora do score** e uma tabela `_CAMADAS_AR` com nome de país dentro de `app.py` — não viola o fio de alarme, mas é código por país na plataforma.
11. **Moeda.** Três moedas (ARS do país, USD da renda, BRL da viabilidade) e dois câmbios do mesmo mês. → No México e no Peru entra também o separador decimal invertido (R10).
12. **Memória.** O temor de RSS com `geometry_wkb` não se materializou (108 MiB contra teto de 2 GB); o risco real do host é **CPU** (4 vCPU, semáforo de PDF por processo) e operação em N vias.
13. **Estimativa de esforço.** O plano orçou 5 semanas/2 devs para A-E; a execução levou ~1,5 dia com IA sobre spec detalhada. Mas o plano **não orçou** a cauda (≈4 semanas) nem o pipeline do país (≈7 semanas), que foram os dois custos reais. → Para CO/PY/MX/PE, estimar **pipeline + decisões + cauda**, não a plataforma.

---

## Fontes consultadas

- Plataforma: `docs/plano_multipais.md` (§0, §2, §3, §4, §5.0, §6, §7, §8, §9), `docs/decisions/DEC-047.md`, `DEC-035.md` (emenda 2), `DEC-049.md`, `DEC-067.md` (emenda 25/09), `data/perfis/AR/perfil.json`, `data/perfis/LEIA-ME.md`, `docs/deploy_piloto_web.md` §8, `docs/spec_portal_selecao_pais.md`, `docker-compose.ar.yml`, `web/server/acesso.py:120-223`, `web/server/app.py` (`:910-976`, `:984`, `:6104-6924`), `src/motor_expansao/pipelines/exportar_piloto_ar.py`, `src/motor_expansao/perfil.py`, `tasks/backlog.md:4109-4700`, `tasks/completed.md` (sem BLK-INTL), `git log origin/main`, `gh pr list/view` (41 PRs + #266, #443, #444).
- Pipeline do Juan (`juancalu/motor-argentina`, leitura via API): `README.md`, `ROADMAP.md`, `docs/fontes_dados_argentina.md`, `docs/coleta_concorrentes_academias.md`, `piloto_rep/LEIA-ME.md`, histórico de commits, árvore de arquivos, `pipelines/exportar_piloto_rep.py` (grep).
- Não lidos/não verificados: `HANDOFF.md` (não versionado), `docs/dicionario_dados.md` integral, estado real da VPS, horas-pessoa.
