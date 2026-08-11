# Contrato — Enriquecimento de Vulnerabilidade para M&A (Plano B)

> **[canônico]** contrato dos sinais de vulnerabilidade de academias independentes (funil de M&A).
> Responsável: Felipe Silva | Estratégia e Growth | Ultra Academia
> Versão: 2026-07-23 (BLK-MA-01 — design/contrato; **ZERO código de produção**;
> emenda pós-gate 2 do mesmo dia: distinção coletor-vs-ingestão, chave de snapshot `slug`, e BLK-MA-08)
> **Emenda BLK-MA-02 (gate de engenharia de 2026-07-29, Vinicius):** seção 6 — payload de 10 colunas (hoje 12, ver emenda DEC-026),
> chave própria do snapshot, origem da `semana` e **cadência real** (os dois relógios); seção 12 —
> plug do materializador no runner semanal e o cron mensal como caminho crítico. Marcadas com
> `[emenda 2026-07-29]`.
> **Emenda BLK-MA-03 (2026-07-29):** seção 8.1 — granularidade de v1 (hex, não academia), domínio efetivo e tratamento no §8.2/§8.4. Marcada com [emenda BLK-MA-03].
> **Emenda BLK-MA-04 (2026-07-30, gate humano — G-D1/G-D2/G-D3 ratificados):** §8.1 (v3 do estado `novo`), §8.2 (normalização de v4 — razão absoluta), §8.4 (universo do score, bordas de ausência e flags), §8.5 (grão da linha = academia e contrato de coluna). Marcadas com [emenda BLK-MA-04].
> Regra de manutenção: manter curto; a implementação é dos blocos sucessores BLK-MA-02..08 (ver seção 13).

Este documento fixa o contrato dos sinais de vulnerabilidade de concorrentes independentes, a
metodologia do **score de vulnerabilidade** (heurística transparente, **não** modelo preditivo) e o
registro das decisões de produto D1–D8 confirmadas no gate humano de 2026-07-23 (Vinicius). É a
especificação que os blocos sucessores (BLK-MA-02..08, seção 13) vão implementar; nenhum extrator, score, join, entregável
ou cron é escrito neste bloco.

---

## 1. Cabeçalho, status e guardrails invariantes

- **Camada PARALELA, READ-ONLY sobre o M1 (§5).** O `score_vulnerabilidade` é um score de negócio para
  o funil de aquisição (M&A); **não** é `score_priorizacao` nem `hex_score_estrutural`. Este trabalho
  **não** recalcula nem altera pesos do M1 (`renda=0.40`/`pop=0.60`), `score_priorizacao`,
  `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou qualquer artefato oficial do
  M1. Imposto por código (`scripts/loop_guard.py` + `.github/workflows/guard.yml`).
- **Anti-PII por construção (DEC-012).** Só agregados por `hex_id` (H3 res-7); geometria deriva do
  `hex_id`, nunca da coordenada GPS bruta; a fonte real nunca é versionada (gitignored); os testes usam
  fixtures **sintéticas**. Detalhe na seção 11.
- **Extensão do lote de scrapers (DEC-013), não pipeline novo.** O enriquecimento consome o histórico de
  snapshots dos 90 coletores já automatizados na VPS; o recompute do score entra como **passo** do
  runner semanal já pré-aprovado (`run_weekly_90.sh`), não como cron novo. Detalhe na seção 12.
- **Sem API externa ao vivo (§2).** O Plano B usa **apenas** fontes internas já coletadas + o diff dos
  snapshots semanais. **Não há dependência de API externa** e, portanto, **este bloco NÃO cria DEC**. O
  dashboard segue offline sobre Parquets locais. Qualquer rota de reputação pública externa (Google
  Places) fica no sucessor opcional **BLK-MA-07**, com gate e DEC próprios — único ponto onde o desvio
  do §2 pode reaparecer.
- **Acentuação (§2).** Prosa em português acentuado; **identificadores, valores de enum e nomes de
  coluna em ASCII** (ex.: `score_oportunidade_residual`, `oferta_efetiva_disponivel`,
  `sam_fitness_potencial`, `hex_id_res7`, `concorrente_id`, `abrir_agora`, `independente`,
  `flag_serie_imatura`). CSV do projeto sempre `sep=";"` / `encoding="utf-8-sig"`.

### Insumo real conferido (2026-07-23) — o que os coletores REALMENTE emitem

Conferência contra amostra real do coletor **TotalPass** (`unidades_totalpass_ac.csv`, **gitignored**,
fora do versionamento — DEC-012). Colunas emitidas: `slug`, `nome`, `latitude`, `longitude`, `cidade`,
`uf`, `cep`, `endereco_formatado`, `modalidades`, `data_coleta`. **NÃO há coluna de nota/rating**
— afirmação **válida só para o TotalPass, e verificada até hoje** `[emenda DEC-026]`: o **WellHub
passou a emitir `nota_wellhub` e `qtd_avaliacoes_wellhub`** (BLK-MA-08 / DEC-024), e o CSV dele tem
**12 colunas**, não 10. Para o TotalPass a frase segue verdadeira e é **definitiva**: o BLK-MA-10
provou que a nota não existe no produto. Os
coletores de cadeia em `concorrentes/` (`unidades_*.csv`) emitem `nome_unidade`, `latitude`,
`longitude`, `data_coleta` — também sem nota. Consequências canônicas que orientam as decisões abaixo:

- **Rating (sinal 2) NÃO é coletado por coletor nenhum hoje** → habilitá-lo é **ajuste de COLETOR
  (scraper), não de ingestão**: exige raspar a nota no app TP/WH. Planejado no **BLK-MA-08** (seção 13).
- **`nome`/`slug`/endereço JÁ são coletados** → a lista NOMEADA (Opção B do D1) é **só ingestão**
  (`_ler_csv_tp_wh` parar de dropar), **sem** ajuste de coletor.
- **`slug` (ID nativo do provedor) + `data_coleta` JÁ são coletados** → churn/staleness (sinais 3/4) são
  coletáveis **hoje**, zero mudança de coletor (seção 6).
- **WellHub = mesmo schema do TotalPass (confirmado por Vinicius, 2026-07-23):** logo o WellHub **também
  não traz nota** → o BLK-MA-08 ajusta os **dois** coletores (TP e WH); não há atalho "só-WellHub" mais
  barato. (Só há amostra de TotalPass versionada no repo, mas o padrão de colunas é o mesmo.)

---

## 2. Objetivo do epic + a INVERSÃO da tese de M&A

**Objetivo.** Produzir uma lista priorizada de alvos de **aquisição (M&A)**: academias independentes
**vulneráveis** (candidatas a fechar ou a serem compradas) situadas em **mercado quente** (onde a Ultra
tem demanda e interesse de presença). É um funil comercial, não uma decisão de score do M1.

> ### INVERSÃO da tese (registrar em destaque — load-bearing para o BLK-MA-05)
> **Comprar (M&A) NÃO é o mesmo que abrir.** Abrir uma unidade nova quer **residual ALTO** (mercado com
> capacidade não atendida). Comprar quer o **OPOSTO**: **demanda ALTA + residual BAIXO (mercado
> saturado)** — é justamente onde já não cabe abrir, mas cabe adquirir quem já opera. Logo o BLK-MA-05
> **NÃO** deve reutilizar a lógica de `tese_entrada = "abrir_agora"` (que exige `flag_white_space`
> e residual alto). O cruzamento com o "hexágono quente" da seção 9 é deliberadamente invertido.

---

## 3. D1 — Universo de "academia independente" e a fonte que retém identidade

**Decisão do gate (D1 = FASEADO).**

- **MVP = hex-level agregado (Opção A, 100% anti-PII).** O entregável do MVP é agregado por hexágono:
  "hexes com concentração de independentes vulneráveis perto de mercado quente" — só categorias,
  contagens e flags, sem identidade de estabelecimento. **Entra já** em BLK-MA-02/04/05, sem bloqueio.
- **Nomeação por-academia (Opção B) = DEFERIDA** atrás de confirmação (BLK-MA-03).
- **Nuance factual (a registrar).** O **nome** do estabelecimento **EXISTE** nos CSVs brutos TP/WH: em
  `src/motor_expansao/demanda_revelada/concorrentes_densos.py`, a função `_ler_csv_tp_wh` (linha 127) lê
  a coluna `nome` (linhas 130–138), usa-a **só em memória** para classificar a rede e a **descarta na
  fronteira** — a saída (linhas 139–141) é apenas `hex_id_res7` / `rede_normalizada` / `fonte`. Portanto
  a lista NOMEADA é **VIÁVEL no futuro** via extensão de ingestão que **retenha**
  `nome_estabelecimento` + `hex_id_res7`. O nome/endereço de um estabelecimento comercial é **dado de
  NEGÓCIO público**, distinto da PII de reviewer/funcionário que a DEC-012 protege. O artefato nomeado é
  então **gitignored** (fonte real fora do versionamento).
- **Definição de "independente".** Academia do universo raspado que **NÃO** é uma das 28 cadeias de
  `concorrentes_mapeados` (classificação `independente` do classificador, **ou** marca com contagem de
  unidades `== 1`). **Reconciliar "28 scrapers legados vs 90 coletores da DEC-013"** quando o BLK-MA-02
  materializar o universo (os independentes de bairro vivem nos agregadores WellHub/TotalPass; a camada
  anti-PII colapsa tudo `< 3 filiais` em `independente`, categoria sem identidade — daí a Opção B exigir
  a extensão de ingestão).
- **Há um gate de universo ANTES deste, no coletor `[emenda BLK-MA-11 / DEC-025, 2026-08-07]`.** A
  definição acima separa *independente* de *cadeia* — mas ela só se aplica ao que o coletor já
  gravou. Quem decide o que é "academia" em primeiro lugar é o filtro de atividades do WellHub
  (`tem_musculacao`, `Wellhub/split_by_state.py`), a montante deste contrato. Esse filtro **quebrou**
  quando o WellHub renomeou a taxonomia, e a DEC-025 o redefiniu para o vocabulário
  `{musculacao, treino de forca, fisiculturismo, levantamento de peso, treino hibrido}` ("V2":
  22.174 das 45.527 linhas, 48,7%, com 99,5% de recall sobre a base de maio). Registrado aqui porque
  o §3 descrevia o universo como se o único corte fosse rede-vs-independente — não é, e o corte de
  cima é o que mais mexe no N.

---

## 4. Contrato dos 6 sinais

Sinais 1–4 são obrigatórios; 5 e 6 são opcionais (fora do MVP). Ressalva: o sinal 2, embora do núcleo,
entra CONDICIONAL/inativo no Plano B até o BLK-MA-08 (seção 7). Direção `↑vuln` = quanto maior o valor
bruto do sinal, maior a vulnerabilidade. Todo componente normalizado `vi ∈ [0,1]` tem `1 = máxima
vulnerabilidade` (seção 8).

| # | Sinal | Direção ↑vuln | Fonte real | Coluna / artefato | Maturidade | Tratamento n/d / imaturo | Condicional? |
|---|---|---|---|---|---|---|---|
| 1 | Presença/ausência em agregadores WellHub/TotalPass | menos agregadores → mais vuln (canal do público low-cost) | ingestão TP/WH (reuso via `fonte`) | derivada da `fonte` do universo raspado | madura (cadência mensal do agregador) | ausência **é** o sinal (0 agregadores) `[ver emenda BLK-MA-03 no §8.1: inalcançável no grão hex]`; staleness do ativo mensal marcada | Não (obrigatório) |
| 2 | Rating in-app WellHub/TotalPass | nota mais baixa → mais vuln | **COLETADO no WellHub** (`nota_wellhub`, `qtd_avaliacoes_wellhub`, BLK-MA-08); **inexistente no TotalPass** (BLK-MA-10) `[emenda DEC-026]` | **nenhum** — não vira componente; propaga como **coluna-fato** | **INATIVO por decisão**, não por falta de dado | não entra em `Σ(wi·vi)`; nada a renormalizar | **Sim** — `SINAIS_INATIVOS = ("s2",)`; ligar o peso exige gate próprio (ver §7, emenda DEC-026) |
| 3 | Churn/permanência (diff de snapshots) | sumiu recente / "piscando" → mais vuln | histórico de snapshots (seção 6) | derivada do `slug`/`concorrente_id` entre semanas | imatura até `MIN_SEMANAS=8` | série imatura → `flag_serie_imatura`, renormaliza (não penaliza) | Não (obrigatório, gated por maturidade) |
| 4 | Staleness (diff de snapshots) | mais semanas sem mudança → mais vuln | histórico de snapshots (`hash_campos_raspados`) | `semanas_sem_mudanca` | só interpretável após série `>= STALE_SEMANAS=12` | série imatura → renormaliza (não penaliza) | Não (obrigatório, gated por maturidade) |
| 5 | Tendência de popularidade no agregador | inclinação negativa de membros → mais vuln | série do agregador / Demanda Revelada | `membros` / `alunos_parceiras` | precisa de série; fora do MVP | fora do MVP → renormaliza | **Sim** (opcional) |
| 6 | Pressão competitiva (independente espremida) | pressão maior → mais vuln | camada de mercado | `pressao_concorrencial_score_2km` (`hexagonos_mercado_mapeado.parquet`) | madura | fora do MVP → renormaliza | **Sim** (opcional) |

---

## 5. Mapa "4 sinais originais → Plano B"

Os quatro sinais concebidos originalmente (a partir da ideia de agregadores + reviews) mapeiam para os
sinais do Plano B assim:

| Sinal original | Sinal(is) do Plano B |
|---|---|
| Avaliação média (nota in-app) | **(2)** rating in-app |
| Δ de reviews em 3 meses | **(3)** churn/permanência + **(5)** tendência de popularidade |
| Presença em agregadores | **(1)** presença/ausência em agregadores |
| Última atualização do cadastro | **(4)** staleness |

Consequência: com o **D3 = Não** (seção 7), o sinal 2 fica `n/d` no Plano B (até o BLK-MA-08 ajustar o coletor), e o "Δ de
reviews" é aproximado pelos sinais internos (3) e (5), sem depender de nota externa.

---

## 6. D2 — Snapshots semanais (churn + staleness)

**Decisão do gate (D2 = default do Planner).**

- **Chave (refino do insumo real).** Snapshot semanal chaveado pelo **`slug` nativo do provedor**
  (ex.: `smart-fit-isaura-parente`), que **já vem no coletor** e é estável a jitter de lat/lng —
  preferível ao `concorrente_id` (sha1 de `rede|nome|lat|lng`), que fica como **fallback** quando o
  `slug` faltar. **Caveat:** alguns slugs carregam UUID (`academia-top-fitness-b8491478-...`) → o
  BLK-MA-02 deve **validar a estabilidade do `slug` entre semanas** antes de confiar nele para churn.
- **Chave efetivamente implementada `[emenda 2026-07-29]`.** O `concorrente_id` de produção
  (`sha1(rede|nome|lat|lng)`, `normalizar_concorrentes.py:29`) foi **descartado como chave de
  churn**: a coordenada entra com `:.6f` (~**11 cm**), então qualquer re-geocodificação produziria
  1 falso `sumiu_recente` + 1 falso `novo` no sinal de maior peso. A chave passa a ser
  `sha1("hash_estavel|<fonte>|<rede>|<nome_normalizado>|<hex_id_res7>")` e, quando o `slug` é
  confiável, `sha1("slug|<fonte>|<slug_normalizado>")` — **sempre sha1 hex de 40** nos dois casos,
  com o valor de `chave_origem` registrando qual foi usada (`slug` | `hash_estavel`). Colisões de
  chave são **COLAPSADAS**, nunca desambiguadas por ordinal (ordinal depende da ordem de leitura do
  CSV e geraria churn sintético toda semana). O `concorrente_id` continua no payload apenas como
  rastreabilidade, com a fórmula **replicada** (nunca importada) e o limite honesto de que só casa
  com `concorrentes_mapeados.parquet` para `fonte == "unidades"`.
- **Data do snapshot.** `snapshot_date = data_coleta` **por linha** (já emitido pelo coletor).
- **Origem da partição `semana` `[emenda 2026-07-29]`.** A `semana=AAAA-SS` é a semana ISO
  (`isocalendar().iso_year`, jamais `date.year`) da **data de referência da EXECUÇÃO**, NUNCA do
  `data_coleta` da linha. Motivo: coletor que falha **mantém o CSV anterior**
  (`docs/infra_producao.md:181-182`); derivar a partição da linha faria uma execução de hoje
  reescrever uma semana passada e, com `existing_data_behavior="delete_matching"`, **apagá-la**.
  Com a partição vindo da execução, o `snapshot_date` por linha passa a servir de **medidor de
  frescor** (é o único detector de "o CSV é o da semana passada").
- **Payload por linha (sem crus além do hash) `[emenda 2026-07-29; 12 colunas desde a DEC-026]`.** 12 colunas, nesta ordem:
  `{snapshot_date, slug, concorrente_id, chave_snapshot, chave_origem, hex_id_res7, rede, fonte,
  hash_campos_raspados, nota_wellhub, qtd_avaliacoes_wellhub, versao_contrato}` — as duas de rating
  entraram pela DEC-026 como FATO sem peso, entre o hash e o carimbo de versão; são nuláveis
  (`Float64`/`Int64`) e só o WellHub as preenche — **sem** nome/coordenadas brutas; a única "impressão
  digital" dos campos raspados é o `hash_campos_raspados` (que **não** inclui `data_coleta`, `slug`
  nem a taxonomia — ver a emenda BLK-MA-11 abaixo). `fonte` não é opcional: o sinal 1 da seção 4 é derivado dela, e sem ela a regra de "gap
  de feed não vira churn" é impossível de implementar. `semana` **não** é coluna do arquivo — vive
  no caminho, como chave de partição hive.

> **[emenda BLK-MA-09, 2026-08-10] Domínio da nota e normalização do par: degradar, nunca abortar.**
> O domínio de `nota_wellhub` é **`[1,0 ; 5,0]`** (`NOTA_WELLHUB_MIN`/`NOTA_WELLHUB_MAX` em
> `contrato.py`), não `[0 ; 5]`. Motivo: a nota é média de avaliações de 1 a 5 estrelas, logo `0.0`
> é aritmeticamente inalcançável — "sem avaliação" tem forma própria (`NA`/`0`). A DEC-026 mediu
> `min = 1,0` em 34.035 independentes com nota. O piso importa mais que o teto porque `0.0` é o
> retorno NATURAL de um extrator quebrado: um piso em `0.0` aceitaria em silêncio justamente o valor
> mais provável de um bug.
>
> **Toda violação DEGRADA a célula para "não lido" e é CONTADA em `rating_ilegivel`; nenhuma
> levanta.** Vale para: nota fora do domínio, contagem negativa, contagem não-inteira (`1.262`, a UI
> pt-BR) e qualquer **par** fora dos três estados da DEC-024 — `NA`/`105`, `4.81`/`0` e `4.81`/`NA`
> viram `NA`/`NA`. A razão é a mesma do item 1 do `_coagir_rating`: `montar_snapshot` roda ANTES de
> gravar e o `run_weekly_90.sh` sobrescreve os CSVs crus a cada coleta, então uma exceção não perde
> uma linha — perde **a semana inteira, para sempre**, por causa de uma célula.
>
> A **ordem** é normativa: domínio por coluna primeiro, par depois. É ela que faz `0.0`/`0` — extrator
> quebrado sobre unidade sem avaliações — cair em "sem avaliações" (`NA`/`0`) em vez de "não lido".
>
> `_assert_schema_snapshot` mantém as checagens como **rede para frames montados à mão** (metade dos
> testes desta camada constrói o insumo assim). Pelo caminho público elas são inalcançáveis — é
> justamente esse o invariante.
- **Limpeza de ruído (BLK-MA-02, obrigatória antes de derivar churn).** O feed cru traz linhas que
  **não** são academias reais e distorceriam churn/universo: coords `0;0` e rótulos de teste (ex.:
  "Teste Raised"); **entradas de tecnologia/onboarding do TotalPass** ("Zon Tecnologia", "SAGAZ
  Sistemas", "TSITECH Soluções", "DATAFITNESS - TTP" e variações "Batatão Jeans - <fornecedor>"); e
  coords geograficamente inconsistentes com `cidade`/`uf`. Filtrar essas linhas é passo do BLK-MA-02.
- **Local / retenção.** `data/staging/snapshots_concorrentes/semana=AAAA-SS/parte-*.parquet`
  (**gitignored**, vive na VPS). Retenção rolante **26 semanas** (6 meses).
- **Derivação dos sinais.**
  - Churn (sinal 3): o `slug` (fallback `concorrente_id`) aparece / some / reaparece ("piscando") entre semanas.
  - Staleness (sinal 4): nº de semanas desde a última mudança de `hash_campos_raspados`.
- **A TAXONOMIA sai do hash `[emenda BLK-MA-11 / DEC-025, 2026-08-07]` — e o contrato de snapshot
  vai para `v2`.** `atividades` (WellHub) e `modalidades` (TotalPass) **saíram** de
  `CAMPOS_HASH_POR_FONTE` e entraram em `CAMPOS_NUNCA_HASHEADOS`, ao lado de `data_coleta` e `slug`.
  Razão categórica: taxonomia é vocabulário da **FONTE**, não cadastro da academia — renomear rótulo
  não é "o negócio mudou". Razão medida: entre maio e agosto de 2026 o WellHub renomeou "Musculação"
  para "Treino de força"/"Fisiculturismo"/"Treino Híbrido", e `atividades` mudou em **12.314 dos
  12.420** slugs comuns (**99,1%**) — contra `endereco_formatado` em 63 e `nome` em 33 — sem que uma
  única academia mudasse de fato. Com a taxonomia dentro do hash, a primeira coleta pós-renomeação
  leria a base inteira como "cadastro atualizado agora", `semanas_sem_mudanca` nunca cresceria e **o
  sinal 4 morreria** — o mesmo modo de falha que já excluía `data_coleta`. O TotalPass entra por
  **simetria preventiva**, não por medição: só existe uma coleta dele (01/06/2026), logo não há
  segunda observação para medir volatilidade, e ele **ainda usa** a taxonomia antiga ("Musculação"
  em 15.970 de 15.986 unidades, 99,9%). `VERSAO_CONTRATO_SNAPSHOT` passa de `snapshots_concorrentes_v1`
  para `..._v2`; a migração foi **gratuita** porque a série estava com zero semanas no momento da
  mudança. Guardrail executável: `test_renomear_taxonomia_nao_mexe_no_hash` (`test_contrato.py`) e
  `test_hash_ignora_a_taxonomia_inteira` (`test_snapshots.py`).
- **Consequência de comparabilidade da mesma emenda, que o BLK-MA-06 precisa respeitar.** O critério
  de universo do coletor WellHub também mudou (vocabulário "V2" da DEC-025, parte 1): o universo passa
  de **12.769** (maio) para **22.174** unidades, e **9.816** desses slugs nunca estiveram na base de
  maio. Como a coleta de maio **só gravava o que passava no filtro**, o negativo de maio não existe
  como dado e é impossível separar "parceiro novo" de "existia e foi corretamente excluído". Portanto
  a **primeira janela** de série após a mudança tem churn (sinal 3) **inutilizável**, e o cron deve
  tratá-la como marco zero, não como semana comparável.
- **Ramp-up / maturidade.** `flag_serie_imatura = True` até `MIN_SEMANAS = 8` snapshots; enquanto
  imatura, os sinais 3/4 **NÃO penalizam** (são renormalizados para fora do score — seção 8). Staleness
  só é interpretável após a série atingir `STALE_SEMANAS = 12`. Mitiga falso churn no início da série.
- **Cadência real e os DOIS relógios `[emenda 2026-07-29]` — corrige afirmação factualmente falsa.**
  A versão anterior desta seção afirmava que "o cron acumula snapshots desde ~26/06/2026". **Isso é
  falso e foi removido:** nenhum passo do `run_weekly_90.sh` arquiva o feed por estabelecimento
  (`docs/infra_producao.md:136-143`; o único histórico existente é `historico_contagem.csv`, **por
  rede**), e os CSVs crus são **sobrescritos** a cada coleta. Em 2026-07-29 havia **ZERO** semanas
  de série por estabelecimento, e o produtor do insumo nasceu no **BLK-MA-02**. Os dois relógios:
  - o cron **semanal** atualiza só `Unidades/unidades_<rede>.csv` (**cadeias**, `infra_producao.md:149`);
  - o cron dos agregadores WellHub/TotalPass — onde vivem os **independentes**, o universo-alvo
    desta epic — é **MENSAL e ainda pendente** (`infra_producao.md:186`, DEC-013 §7.3).

  **Consequência de cronograma, load-bearing para o BLK-MA-04/05:** `MIN_SEMANAS` e `STALE_SEMANAS`
  contam **semanas OBSERVADAS**, não semanas de calendário. Na cadência real do feed dos
  independentes, **8 snapshots = ~8 MESES** e **12 snapshots = ~12 MESES** — ou seja, o
  `score_vulnerabilidade` sai com `flag_score_provisorio` por cerca de um ano após o cron mensal
  entrar no ar. Os valores `MIN_SEMANAS = 8` / `STALE_SEMANAS = 12` **não** foram alterados
  (decisão do gate de 2026-07-23; revisitar no BLK-MA-06, com a cadência real medida).

---

## 7. D3 — Rating de agregador (sinal 2)

> **[emenda DEC-026, 2026-08-10 — gate do BLK-MA-09] A premissa do D3 caiu, e o desfecho NÃO foi
> ligar o sinal 2.** Tudo o que esta seção afirma abaixo repousa em *"nenhum coletor emite nota"*.
> O **BLK-MA-08** falsificou isso **para o WellHub** (`partnerRating` no mesmo payload RSC que o
> coletor já baixava; 36.940 unidades com nota no consolidado). O **BLK-MA-10** provou que o
> **TotalPass não tem nota como produto** — não é dado escondido, a funcionalidade não existe —,
> logo a partição do universo é **PERMANENTE**.
>
> **Decisão (DEC-026, D-B = opção 0):** a nota e a contagem são propagadas como **COLUNA-FATO, sem
> peso, fora de `Σ(wi · vi)`**, no molde do G-D2 (o mesmo que já se aplica ao `status_churn`).
> `SINAIS_INATIVOS` continua `("s2",)` e os pesos efetivos do Plano B seguem
> `S1≈0,20 / S3≈0,467 / S4≈0,333`. **O sinal 2 permanece INATIVO** — o que muda é que o dado passa
> a existir e a chegar ao consumidor.
>
> **Por quê, em uma linha:** com peso, o `v2` inverteria o ranking. Vale a identidade
> `score_com_s2 = 0,75 · score_sem_s2 + 25 · v2`, então ter nota cobra um corte de 25% nos outros
> três sinais; com a nota mediana medida (4,93), **99,97% das 34.035 linhas com nota seriam
> penalizadas**, e a academia `sumiu_recente` + stale — o alvo de maior prioridade pela INVERSÃO do
> §2 — cairia de 90,00 para 67,94. Racional completo, alternativas medidas e riscos assumidos na
> DEC-026.
>
> **Correção de fato desta seção:** onde se lê que o rating exige "ajuste de COLETOR", isso está
> **feito** para o WellHub (BLK-MA-08) e é **impossível** para o TotalPass (BLK-MA-10).

**Decisão do gate (D3 = NÃO carregam a nota) — SUPERSEDED em parte pela emenda acima.**

- **Fato de dado (corrigido com o insumo real, 2026-07-23).** A nota **não é dropada na ingestão — ela
  não é COLETADA.** Nenhum CSV de coletor tem coluna de rating (ver "Insumo real conferido", seção 1);
  a ingestão `_ler_csv_tp_wh` (`concorrentes_densos.py:127`) por cima ainda dropa `nome`/coords e emite
  só `hex_id_res7` / `rede_normalizada` / `fonte`. Logo habilitar o rating é **ajuste de COLETOR
  (scraper), não de ingestão.**
- **Consequência.** O **sinal 2 fica `n/d`** enquanto o coletor não for ajustado. O framework o mantém
  **DEFINIDO** (por completude do contrato), porém **INATIVO** — o score do Plano B roda em
  **S1 / S3 / S4** renormalizados (seção 8). O `n/d` do sinal 2 **NÃO trava** BLK-MA-03/04.
- **Como o sinal 2 é reativado (decisão do gate 2, 2026-07-23).** Via **BLK-MA-08** (bloco near-term,
  seção 13): **ajustar os coletores TP/WH (GymScraping) para raspar a nota in-app**, persistindo só o
  agregado numérico (anti-PII). BLK-MA-08 é pré-requisito EXPLÍCITO do sinal 2. A **reputação EXTERNA**
  (Google Places, público geral) — essa sim — fica no **BLK-MA-07** (opcional/futuro, com gate + DEC
  próprios), único ponto onde o desvio do §2 reaparece. **WellHub = mesmo schema do TotalPass
  (confirmado 2026-07-23) → também sem nota:** o BLK-MA-08 cobre os DOIS coletores; sem atalho só-WellHub.

---

## 8. D4 — Score de vulnerabilidade (metodologia)

**Decisão do gate (D4).** Heurística ponderada, normalizada e **AUDITÁVEL**. **NÃO é modelo preditivo**
(sem treino em desfecho; validar que o score "prevê" aquisição/fechamento seria bloco próprio sob a
DEC-008, com LOO/k-fold vs baseline, sem R² in-sample).

### 8.1 Componentes `vi ∈ [0,1]` (`1 = máxima vulnerabilidade`)

- `v1` — presença em agregador: `0` agregadores → `1.0`; `1` → `0.5`; `2` → `0.0`.

> **[emenda BLK-MA-03, 2026-07-29] Granularidade e domínio efetivo de `v1`.** O texto acima descreve
> `v1` **por academia**. Com o universo NOMEADO (Opção B / D1-B) **deferido** (decisão S1), não existe
> identidade cross-provider: a chave do snapshot embute a `fonte` (`chave_do_slug` e
> `chave_hash_estavel`, `vulnerabilidade/contrato.py:395-413`) e o `nome` não é persistido (anti-PII,
> §11), logo a MESMA academia em TotalPass e WellHub é sempre DUAS chaves distintas e "quantos
> agregadores cobrem esta linha" seria constante `1` — sinal sem variância. **`v1` passa a ser medido
> por `hex_id_res7`** (quantos agregadores cobrem o hex) e propagado às academias do hex pelo
> BLK-MA-04 via join `validate="many_to_one"` (molde do §9/D5).
> **Viés registrado, não é o mesmo caso do §9/D5:** ali a grandeza propagada (hotness) é intrínseca ao
> hex; aqui "estar em agregador" é intrínseco à ACADEMIA. Num hex denso em que o TotalPass cobre a
> academia A e o WellHub cobre a B, o hex lê "2 agregadores" e ambas recebem `v1 = 0.0`, embora cada
> uma esteja em um só. O erro é sistemático nos hexes densos (que são os hexes-alvo, pela INVERSÃO do
> §2), mas a sua direção é a segura para um funil de aquisição: **falso negativo** (alvo bom que não
> sobe no ranking), nunca falso alvo.
> **O ramo `0` agregadores → `1.0` é inalcançável e VACUOSO nesta granularidade.** TotalPass e WellHub
> são fontes **só-positivas**: a ausência de linha nunca prova ausência real, só não-observação. E um
> hex sem nenhuma academia independente observada não tem alvo de M&A para pontuar. O caso
> informativo — "estava no agregador e saiu" — já é capturado pelo **S3**
> (`status_churn == "sumiu_recente"`, peso efetivo ≈ 0,467), não por este sinal.
> **Domínio efetivo de `v1` no Plano B: `{0.0, 0.5}`.** Com peso efetivo `S1 ≈ 0,20`, S1 contribui no
> máximo **10 dos 100 pontos** do `score_vulnerabilidade`, não 20.
> **§8.2 — `v1` é CATEGÓRICO:** entra como flag graduado, **NUNCA** por normalização percentil.
> Percentilizar um binário reescalaria "presente em 1 agregador" para ~1,0 e destruiria a calibração.
> **§8.4 — `v1` NÃO é renormalizado para fora:** ele não é ausente nem imaturo. **Restrição de produto
> herdada pelo BLK-MA-04:** enquanto S3/S4 estiverem imaturos (~8–12 meses na cadência real, §6/§12),
> o §8.4 os renormaliza para fora e **S1 fica sendo o único sinal do score** — sozinho, com peso
> renormalizado 1,00 e domínio `{0.0, 0.5}`, ele produz `score_vulnerabilidade ∈ {0, 50}`. Um score de
> dois valores não ordena carteira: o BLK-MA-04 precisa decidir como apresentar isso (banda/flag em vez
> de ranking) ou o BLK-MA-05 precisa esperar a maturidade de S3.
> O insumo bruto hex-level é entregue pelo BLK-MA-03 no contrato de coluna `presenca_agregador_v1`
> (`vulnerabilidade/presenca_agregador.py`), com os sufixos `_no_hex` carregando esta ressalva.

- `v2` — rating in-app. **`[emenda DEC-026]` NÃO EXISTE como componente.** A fórmula
  `1 − normaliza(rating)` (ex.: `1 − (rating − 1) / (5 − 1)`) fica **RESERVADA**, sem escolha de
  régua: o gate do BLK-MA-09 decidiu que o rating entra como **coluna-fato sem peso**, então não há
  `v2` em `Σ(wi · vi)` e não há normalização a definir. O bloco que quiser ligar o peso **precisa
  escolher a régua num gate próprio** — e a medição de 2026-08-10 mostra que a linear é
  inadequada: ela comprime a nota mediana a 0,44 ponto de 100 e coloca no top-100 **58 unidades com
  menos de 10 avaliações** (mediana de 8). O texto original está preservado acima só como ponto de
  partida para esse gate futuro.
- `v3` — churn/permanência: sumiu recente → `1.0`; "piscando" (some/reaparece) → `0.7`; estável →
  `0.0`.

> **[emenda BLK-MA-04, 2026-07-30] `STATUS_CHURN_VALIDOS` tem QUATRO estados, e o texto acima mapeia
> três.** O quarto é `novo` (`churn_staleness.py`: presente, zero desaparecimentos e série ainda
> imatura), e ele mapeia para **AUSENTE** — renormaliza S3 para fora —, **nunca para `0.0`**: ler
> "série curta demais para julgar" como "estável" inverteria o sinal em silêncio, e um `dict` sem a
> chave `novo` estouraria `KeyError` ou, com `.get(..., 0.0)`, faria exatamente essa leitura errada.
> O mapa é `V3_POR_STATUS_CHURN` (`vulnerabilidade/contrato.py`), e as suas chaves são **exatamente**
> os 4 estados de `STATUS_CHURN_VALIDOS` — um 5º estado futuro quebra o teste do contrato em vez de
> cair num default silencioso. Corolário implementado: "sinal disponível" equivale a "componente não
> nulo", de modo que `novo` sai do regime em vez de pontuar `0`.

- `v4` — staleness: `min(semanas_sem_mudanca / STALE_SEMANAS, 1)`; série imatura → renormaliza para fora.
- `v5` (opcional) — tendência de popularidade: inclinação negativa de `membros` / `alunos_parceiras`
  normalizada; entra só quando a série permitir.
- `v6` (opcional) — pressão competitiva: `pressao_concorrencial_score_2km / 100` (independente
  espremida); coluna já materializada em `hexagonos_mercado_mapeado.parquet`.

### 8.2 Normalização

**Percentil por universo** (robusto a outliers) para os sinais contínuos (rating, staleness,
popularidade, pressão); flags graduados para os categóricos (S1/S3). Tudo em `[0,1]`, com `↑ = ↑vuln`.

> **[emenda DEC-026, 2026-08-10] O `rating` sai desta frase.** Ele não é mais um "sinal contínuo a
> normalizar", porque não é sinal: entra como **coluna-fato sem peso** (§7, emenda DEC-026). Esta é
> a reabertura do §8.2 que o BLK-MA-09 devia fazer — e o gatilho era **este parágrafo**, que
> nomeava o `rating`, não o item 4 da emenda G-D3 (aquele fala de quem **reativar** a percentil, e o
> MA-09 não a reativou). Com o `v4` já convertido em razão absoluta pela emenda BLK-MA-04 e o
> `rating` fora, **nenhum componente do score usa percentil por universo hoje** — a percentil segue
> RESERVADA, como o G-D3 deixou.

> **[emenda BLK-MA-04, 2026-07-30 — G-D3 ratificado no gate] `v4` é RAZÃO ABSOLUTA, não percentil.**
> O §8.1 e este §8.2 se contradiziam sobre o `v4` (`min(semanas_sem_mudanca / STALE_SEMANAS, 1)` vs
> "percentil por universo"). Vale o **§8.1, literalmente**. Motivos, em ordem de peso:
> 1. **Não-monotonicidade (decisivo).** Percentil-por-universo faria o score deixar de ser monótono
>    no sinal que ele diz medir: acrescentar ao lote uma academia muito parada **BAIXA** o `v4` de
>    todas as outras, sem que nada tenha mudado nelas. Um score de vulnerabilidade em que ficar
>    parado pode reduzir a vulnerabilidade medida de terceiros é indefensável perante o comercial —
>    e mata a exigência-título do D4 ("**AUDITÁVEL**").
> 2. **Não-reprodutibilidade.** A régua mudaria a cada execução conforme o universo raspado variasse
>    (e o universo do percentil seria o subconjunto `flag_staleness_interpretavel`, que muda toda
>    semana).
> 3. **Degeneração no ramp-up.** Com poucas observações, `semanas_sem_mudanca` empata quase
>    totalmente e o percentil vira ruído.
> 4. **Não há consumidor.** No Plano B, S2 é `n/d` (D3) e S5/S6 estão fora do MVP: `v4` é o único
>    "contínuo" ativo. A normalização percentil fica **RESERVADA** para quando S1..S6 estiverem todos
>    ativos, e o bloco que a reativar terá de reabrir esta seção.
>
> `v1` e `v3` seguem **CATEGÓRICOS** (flags graduados), como este §8.2 já dizia e a emenda G1
> reforçou para o `v1`: percentilizar um categórico reescalaria "presente em 1 agregador" para ~1,0 e
> destruiria a calibração dos pesos.

### 8.3 Pesos

Pesos-alvo dos 4 obrigatórios (somam `1,00`):

| Sinal | Peso-alvo |
|---|---|
| S1 (presença) | 0,15 |
| S2 (rating) | 0,25 |
| S3 (churn) | 0,35 |
| S4 (staleness) | 0,25 |

**Churn (S3) domina** — é o proxy mais forte de fechamento/venda.

**Pesos EFETIVOS no Plano B** (S2 fora por D3 → **RENORMALIZAÇÃO** dos 3 restantes, dividindo pela soma
`0,15 + 0,35 + 0,25 = 0,75`):

| Sinal | Aritmética | Peso efetivo |
|---|---|---|
| S1 | 0,15 / 0,75 | ≈ 0,20 |
| S3 | 0,35 / 0,75 | ≈ 0,467 |
| S4 | 0,25 / 0,75 | ≈ 0,333 |

Conjunto maduro de 6 sinais (ilustrativo, soma `1,00`): `S1=0,12 · S2=0,20 · S3=0,28 · S4=0,20 ·
S5=0,10 · S6=0,10`.

### 8.4 Sinal ausente / imaturo

> **[emenda DEC-026, 2026-08-10] O rating NÃO cria regime novo.** Como ele entra como coluna-fato
> sem peso (§7), o `sinais_disponiveis` **não** ganha `"s2"`, o regime `{s1,s2}` **não passa a
> existir** e a `flag_score_provisorio` fica **intocada** — o universo inteiro segue numa régua só,
> `{s1,s3,s4}`, com ou sem nota. Foi o que dissolveu o **D-C** do gate.
>
> Registre-se, para quem reabrir o assunto, uma **correção ao enunciado do D-C** que circulou no
> backlog: dizia-se que o parêntese *"(e S2 quando ativo)"* desta seção era um caso "que a
> implementação não contempla". Não é. O parêntese **ESTENDE** a condição de provisório ao caso em
> que o score repousa sobre S1+S2 — ou seja, afirma que `{s1,s2}` **é** provisório, exatamente como
> `score.py` calcula. Tratar `{s1,s2}` como ordenável seria **emendar** este §8.4 e a decisão G-D1,
> não corrigir um bug.

**RENORMALIZAR** (dropar o peso do sinal ausente/imaturo e reescalar os restantes para somar `1`) — mais
auditável que imputar um neutro `0,5`. Flags de qualidade obrigatórias:

- `n_sinais_disponiveis` — quantos sinais entraram no score da linha;
- `flag_serie_imatura` — a série de snapshots ainda não atingiu `MIN_SEMANAS`;
- `flag_score_provisorio` — quando S3 **e** S4 estão imaturos e o score depende só de S1 (e S2 quando
  ativo).

> **[emenda BLK-MA-04, 2026-07-30] Universo do score, bordas de ausência e leitura honesta do `0`.**
>
> **(i) UNIVERSO DO SCORE — `fonte ∈ FONTES_AGREGADORES` E `rede == independente`.** O frame de churn
> é um extrator **genérico** e traz o feed `unidades` (CADEIAS, um CSV por rede) e também marcas
> conhecidas listadas dentro do TotalPass/WellHub. **Sem este filtro o score pontuaria a Smart Fit
> como alvo de aquisição** (medido em 2026-07-30 sobre fixtures sintéticas). O filtro vive no
> **score**, não no extrator — o §12 já ratificou plugar o extrator no runner semanal justamente para
> o feed de cadeias, cujo valor é de engenharia/mercado —, e reusa o predicado do sinal 1
> (`_filtrar_universo_sinal_1`), porque pelo §3/D1 o universo do sinal 1 e o universo de M&A são o
> **mesmo conjunto por definição**. É travado duas vezes: no filtro de entrada e no schema de saída.
>
> **(ii) `n_sinais_disponiveis == 0` → score NULO, jamais `0`.** `0` significa "não vulnerável" e
> seria uma afirmação de solidez que ninguém mediu; ausência de evidência é nulo.
>
> **(iii) `v1` ausente → renormaliza S1 para fora, nunca imputa.** Uma academia cujo `hex_id_res7` não
> tem par no sinal 1 recebe `v1` **ausente**. Imputar `0.0` leria "2 agregadores" (falso negativo
> injetado); `0.5` ou `1.0` inventariam observação. O caso não levanta exceção: é borda prevista, e
> fica auditável pelo biconditional `v1` nulo ⟺ `n_agregadores_no_hex` nulo ⟺ `"s1"` fora de
> `sinais_disponiveis`.
>
> **(iv) `sinais_disponiveis`** (string com os sinais que entraram, na ordem canônica) passa a
> acompanhar `n_sinais_disponiveis`: ela torna a renormalização **reconstituível a partir da própria
> saída**, sem reler o insumo.
>
> **(v) No regime só-S1, `score == 0` NÃO significa "não vulnerável"** — significa "o hex tem os dois
> agregadores". Durante o ramp-up (~8–12 meses, §6/§12) a maior parte do universo terá `0` sem
> nenhuma evidência de solidez. Daí a coluna de ordenação nula do §8.5.
>
> **NÃO foi aberta exceção para `sumiu_recente` com série imatura** (decisão do gate, G-D2): a
> maturidade é o amortecedor contra **coleta parcial** — um scrape que devolve 30% das páginas
> marcaria 70% do universo como `sumiu_recente` de uma vez, no sinal de maior peso e sem
> amortecimento algum no ramp-up. A informação que a exceção queria injetar é entregue como **FATO**:
> `status_churn` é propagado na saída **sem peso**, fora de `Σ(wi · vi)` e sem mudar regime, para o
> BLK-MA-05 **segmentar** por "sumiço observado" em vez de ordenar por um score de dois valores.

### 8.5 Saída

`score_vulnerabilidade ∈ [0,100] = 100 · Σ(wi · vi)` com os pesos **renormalizados**, acompanhado dos
componentes `vi` por sinal (para auditoria) e das flags de qualidade.

> **[emenda DEC-026, 2026-08-10] A saída ganha DOIS FATOS, não um componente.** `nota_wellhub` e
> `qtd_avaliacoes_wellhub` são propagados na saída **fora de `Σ(wi · vi)`**, no mesmo molde do
> `status_churn` (G-D2). Não têm peso, não entram em `sinais_disponiveis`, não mudam regime e não
> afetam `score_vulnerabilidade`.
>
> **As duas colunas andam juntas — a contagem não é opcional.** Medido em 2026-08-10 sobre as
> 34.035 independentes com nota: **38,4% têm menos de 30 avaliações** (mediana geral: 46), e a
> cauda que mais interessa ao M&A é a **menos** confiável — das 158 unidades abaixo de nota 4,0, a
> mediana é de **10,5 avaliações** e **47% têm menos de 10**. Uma leitura de nota sem a contagem ao
> lado coloca no topo da shortlist academias cujo sinal são três avaliações.
>
> **Obrigação transferida ao BLK-MA-05.** Como a decisão de ranking sobre o rating sai do contrato
> versionado, o entregável **deve documentar por escrito** qualquer corte que faça sobre nota ou
> contagem. Esse corte é candidato natural a virar sinal com peso num bloco futuro, quando houver
> desfecho observado contra o qual calibrá-lo.

> **[emenda BLK-MA-04, 2026-07-30] Grão da linha, contrato de coluna e a coluna de ordenação.**
> A saída do score é o contrato **`score_vulnerabilidade_v2`, de 22 colunas** (`v1`/20 até a DEC-026)
> (`CONTRATO_COLUNAS_SCORE` em `vulnerabilidade/contrato.py`; implementação em
> `vulnerabilidade/score.py`, módulo **PURO, sem I/O**), com **uma linha por ACADEMIA** =
> `(fonte, chave_snapshot)`. "Academia" aqui é uma **chave de snapshot**, não um estabelecimento
> nomeado (universo NOMEADO / D1-B deferido): a mesma academia em TotalPass e WellHub são **duas
> linhas** — intencional, e é a razão de o `v1` ser medido por hex (emenda BLK-MA-03).
> **Duas colunas de score (G-D1 ratificado no gate):** `score_vulnerabilidade` é o número auditável
> do D4 e está **sempre preenchido** quando há ≥ 1 sinal; `score_vulnerabilidade_ordenavel` é
> **NULA enquanto `flag_score_provisorio`** estiver ligada, e igual à primeira quando não estiver.
> A proibição de ordenar carteira por um score de dois valores deixa de ser prosa e vira o **tipo da
> saída**: um `sort_values` sobre frame provisório devolve NaN em todas as linhas. Reversível de
> graça — a flag desliga sozinha quando o S3 amadurece.
> **Linhas de regimes diferentes não são comparáveis entre si** (uma linha `{S1}` e uma `{S1,S3,S4}`
> não estão na mesma régua): `sinais_disponiveis` + `n_sinais_disponiveis` existem na saída
> exatamente para o BLK-MA-05 segmentar antes de ordenar.
> O CSV **hex-level** do exemplo do §10/D6 é o entregável do **BLK-MA-05**, derivado por agregação
> deste frame — não é a saída deste contrato.

---

## 9. D5 — Hexágono quente + cruzamento de M&A

**Decisão do gate (D5).**

- **Métrica de "hexágono quente para M&A" (com a INVERSÃO da seção 2):**
  `sam_fitness_potencial` **alto** (top quartil do universo) **AND** `score_oportunidade_residual < 25`
  (**saturado** — residual ≈ `< ~625` alunos, sendo `2500` alunos = 1 unidade grande proxy). É demanda
  **ALTA + residual BAIXO**, o OPOSTO de `abrir_agora`.
- **Distância academia ↔ hex = k=1.** A academia está "próxima de hex quente" se o seu `hex_id_res7`
  **ou** qualquer vizinho em `h3.grid_disk(k=1)` for quente (adjacência ~2–3 km, sem geometria pesada).
- **Colunas verificadas** em `carteira_expansao_acionavel.parquet`: `score_oportunidade_residual`,
  `oferta_efetiva_disponivel`, `sam_fitness_potencial`, `tese_entrada`, `score_priorizacao`.
- **Join READ-ONLY (molde `enriquecer_outputs_residual_mercado.py:68-82`).** Left-join do "hotness"
  (carteira/mercado) **na** lista de academias por `academia.hex_id_res7 == carteira.hex_id`, com
  asserts de invariância: `len` inalterado (`validate="many_to_one"`), e `score_priorizacao` +
  ranks (`rank_brasil` / `rank_uf` / `rank_carteira_brasil` / `rank_carteira_uf`) idênticos (`.equals`)
  antes/depois. **A camada M&A LÊ essas colunas; NUNCA escreve de volta** em carteira, mercado ou
  artefatos do M1.
- **Prioridade de M&A** = `f(score_vulnerabilidade da academia, demanda do hex, saturação do hex)`,
  ordenada de forma descendente para o comercial.

---

## 10. D6 — Entregável

**Decisão do gate (D6 = default do Planner).**

- **Camada scored:** `data/staging/vulnerabilidade_ma_academias.parquet` (**gitignored** se carregar
  identidade — Opção B do D1).
- **Lista curada para o comercial:** `data/outputs/alvos_ma_priorizados.csv`, `sep=";"`,
  `encoding="utf-8-sig"`. Exemplo de cabeçalho (hex-level do MVP, sem identidade):

  ```csv
  hex_id_res7;uf;n_independentes_vulneraveis;score_vulnerabilidade_medio;sam_fitness_potencial;score_oportunidade_residual;hex_quente;n_sinais_disponiveis;flag_serie_imatura
  ```

- **Sem overlay de dashboard no MVP** (opcional/futuro). Se por-academia (nomeado), o artefato é
  **gitignored** (fonte real fora do versionamento, DEC-012).

---

## 11. D7 — Anti-PII

**Decisão do gate (D7 = default do Planner).**

- **Persistir SÓ agregados** (contagens, médias, flags de churn/staleness, `hash_campos_raspados`).
  **NUNCA** texto/autor de review nem coordenada GPS bruta — a geometria deriva do `hex_id` (DEC-012).
- **Nome/endereço de estabelecimento** (dado de negócio) é permitido **apenas** no artefato NOMEADO da
  Opção B, que então é **gitignored**.
- **Fixtures sintéticas** nos testes; a fonte real (CSVs brutos TP/WH, snapshots) fica **fora do
  versionamento** e vive na VPS. Reafirma a DEC-012.

---

## 12. D8 — Integração ao cron

**Decisão do gate (D8 = default do Planner).**

- **Dois relógios.** Churn/staleness (S3/S4) saem do snapshot semanal dos 90 coletores →
  `run_weekly_90.sh` (DEC-013). Presença/rating de agregador (S1/S2) dependem do cron **mensal** dos
  agregadores WellHub/TotalPass, que ainda é **FUTURO/pendente** (`infra_producao.md`, § Pendentes).
- **O materializador de snapshots é plugado JÁ no runner semanal `[emenda 2026-07-29]`.** Decisão de
  produto antecipada no gate: o **BLK-MA-06** anexa
  `python -m motor_expansao.vulnerabilidade.snapshots` ao `run_weekly_90.sh`, **depois** do passo de
  coleta, para o feed `unidades`. O snapshot **tem** de ser tirado dentro da execução do runner
  porque os CSVs crus são sobrescritos a cada coleta. Custo ~zero, risco ~zero (READ-ONLY sobre o
  M1), e valida o caminho em produção enquanto a série começa a acumular. **Ressalva honesta
  registrada:** isso produz série de **CADEIAS**, que **não** é o universo-alvo do funil de M&A
  (independentes) — o valor é de engenharia e de mercado/residual, não do epic.
- **O cron MENSAL dos agregadores é CAMINHO CRÍTICO do BLK-MA-04/05 `[emenda 2026-07-29]`.** Ele
  aparece em `infra_producao.md` apenas como "pendente futuro" e **não** como dependência de bloco.
  Sem ele, S1/S3/S4 sobre os **independentes** não existem e o epic não entrega o que promete:
  registrá-lo como `Depende de` explícito do BLK-MA-04 é ação de backlog (fora do escopo do
  BLK-MA-02, que só sinaliza).
- **Passo semanal.** Anexar o recompute do `score_vulnerabilidade` como **passo** do runner semanal
  **APÓS** a regen da camada mercado/residual (para o hotness estar fresco), estritamente **READ-ONLY**
  sobre o M1. Os sinais de agregador são consumidos do **ativo mensal mais recente**, marcados com flag
  de **staleness** quando desatualizados.
- **DEC-013 cobre** a extensão do lote — **não é pipeline novo**. Runbook detalhado em BLK-MA-06.

---

## 13. Decomposição BLK-MA-02..08

Ajustada pelo **D3 = Não** (rating não é coletado → sinal 2 depende de ajuste de coletor no
**BLK-MA-08** near-term; reputação **externa** fica no BLK-MA-07):

| Bloco | Escopo | D amarradas |
|---|---|---|
| **BLK-MA-02** | Extrator de churn+staleness do histórico de snapshots (100% interno) + **limpeza de ruído** (linhas `0;0`/teste, entradas de tecnologia/onboarding, coords inconsistentes) + flags de série imatura (ramp-up); chave `slug` + `data_coleta`. É o núcleo 100%-reuso do Plano B. | D2 (S3/S4) |
| **BLK-MA-03** | Presença em agregador (**sinal 1**, reuso via `fonte`) + (opcional/deferido) extensão de **ingestão** para o universo NOMEADO (D1-B, retém `slug`/`nome_estabelecimento`; **só ingestão, SEM ajuste de coletor**); anti-PII por construção; fixtures sintéticas. **Rating (sinal 2) NÃO entra aqui** — depende do BLK-MA-08. Entregue como insumo BRUTO hex-level (contrato `presenca_agregador_v1`); `v1`/pesos são BLK-MA-04. | sinal 1 + D1 |
| **BLK-MA-04** | Score de vulnerabilidade (D4) sobre S1/S3/S4 (Plano B) + normalização + flags de qualidade. Entregue como contrato de coluna `score_vulnerabilidade_v1` (20 colunas na época; hoje `v2`/22 pela DEC-026; módulo PURO sem I/O), uma linha por academia, com o **universo de M&A filtrado aqui**; os artefatos do D6 são BLK-MA-05. | D4 + D7 |
| **BLK-MA-05** | Lista priorizada de M&A (cruzamento com o hex quente, D5, **COM a INVERSÃO**) + entregável. | D5 + D6 |
| **BLK-MA-06** | Integração ao cron semanal da VPS + runbook. | D8 |
| **BLK-MA-07** | (Opcional/futuro, **gate + DEC próprios**) reputação **EXTERNA** (Google Places ou outra, público geral). Único ponto que reabre o §2. | — |
| **BLK-MA-08** | **CONCLUÍDO (2026-08-06).** Ajuste do coletor **WellHub** para raspar a nota in-app; persiste **só os dois agregados numéricos** (anti-PII, DEC-024). `[emenda DEC-026]` A frase original — *"vale para os DOIS coletores (WellHub segue o mesmo schema do TotalPass — sem nota)"* — era **falsa nas duas metades**: o WellHub **tem** nota, e o TotalPass **nunca terá** (BLK-MA-10). | nota in-app do WellHub |
| **BLK-MA-09** | Ingerir a nota até a saída do score **como coluna-fato sem peso** (DEC-026); snapshot de 10 para 12 colunas com bump de versão. **NÃO reativa o `v2`.** | coluna-fato de rating |
| **BLK-MA-10** | **CONCLUÍDO (2026-08-05), veredito ARQUIVAR.** Spike do TotalPass: a nota não existe como produto. | — |
| **BLK-MA-11** | **CONCLUÍDO (2026-08-10).** Vocabulário "V2" do filtro de musculação + taxonomia fora do hash de staleness (DEC-025). | — |

D7 (anti-PII) é transversal a BLK-MA-02..05 e BLK-MA-08.

---

## 14. Guardrails e referências

**Guardrails ativos.**

- **§5 — READ-ONLY sobre o M1:** o `score_vulnerabilidade` é PARALELO; joins/análises não recalculam
  nem alteram `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de
  domínio ou artefatos oficiais. Pesos `renda=0.40` / `pop=0.60` INTOCADOS.
- **DEC-012 — anti-PII:** camada H3 res-7 sem PII; geometria do `hex_id`; só agregados; fonte real
  gitignored; fixtures sintéticas.
- **DEC-013 — coleta recorrente na VPS:** BLK-MA é **extensão** desse lote, não pipeline novo.
- **§2 — sem API ao vivo:** Plano B sem dependência de API externa; dashboard offline sobre Parquets;
  acentuação correta em texto de usuário, nunca em identificadores; CSV `sep=";"` / `utf-8-sig`.
- **Sem DEC neste bloco:** a rota Google Places/§2 foi descartada no Plano B → BLK-MA-01 **não** cria
  DEC (reputação externa e seu eventual DEC ficam no BLK-MA-07).

**Referências.**

- `docs/decisions/DEC-012.md` (anti-PII / Demanda Revelada), `docs/decisions/DEC-013.md` (coleta
  recorrente na VPS).
- `docs/modelo_mercado_hexagonos.md` (colunas de mercado/residual: `pressao_concorrencial_score_2km`,
  `sam_fitness_potencial`, `oferta_efetiva_disponivel`, `score_oportunidade_residual`, `tese_entrada`).
- `src/motor_expansao/pipelines/enriquecer_outputs_residual_mercado.py:68-82` (molde defensivo de join
  READ-ONLY).
- `src/motor_expansao/demanda_revelada/concorrentes_densos.py:127` (`_ler_csv_tp_wh` — a ingestão lê
  `nome`/coords e dropa tudo; a nota **nem existe na fonte** → ajuste de coletor, não de ingestão).
- `docs/infra_producao.md` (runbook do cron semanal GymScraping — D2/D8).
- `CLAUDE.md` §1/§2/§4/§5/§6/§8.

---

## 15. Registro das decisões D1–D8 (gate de 2026-07-23, Vinicius)

| # | Questão | Opção escolhida no gate | Default do Planner |
|---|---|---|---|
| **D1** | Universo de "academia independente" e fonte que retém identidade | **FASEADO** — MVP hex-level agregado (Opção A, anti-PII) entra já; nomeação por-academia (Opção B) **deferida** atrás de confirmação dos CSVs brutos (nome existe na fonte, é dado de negócio). Independente = fora das 28 cadeias (`independente` ou marca com unidades `== 1`); reconciliar 28 scrapers vs 90 coletores no BLK-MA-02. | Entregar Opção A primeiro; Opção B atrás de confirmação. |
| **D2** | Fonte/retenção dos snapshots (churn/staleness) | **Default aceito + refino do insumo real:** chave = `slug` nativo + `data_coleta` (fallback `concorrente_id`) — **SUPERSEDED, ver a emenda de 2026-07-29 no §6**: a chave de churn passou a ser própria (`chave_do_slug`/`chave_hash_estavel`), porque o `concorrente_id` de produção embute a coordenada com `:.6f` (~11 cm) e qualquer re-geocodificação geraria falso churn no sinal de maior peso —, com limpeza de ruído (linhas `0;0`/teste/tecnologia) no BLK-MA-02; snapshots em `data/staging/snapshots_concorrentes/semana=AAAA-SS/` (gitignored, VPS); retenção 26 semanas; `MIN_SEMANAS=8`; `STALE_SEMANAS=12`; série imatura marcada e neutra. | snapshots por `concorrente_id` (Opção A). |
| **D3** | Rating de agregador (sinal 2) | **NÃO é coletado (ajuste de coletor, não de ingestão)** — sinal 2 fica `n/d` até o **BLK-MA-08** (near-term) ajustar os coletores TP/WH para raspar a nota; enquanto isso o score roda em S1/S3/S4 renormalizados. Reputação **externa** (Google) fica no BLK-MA-07. | Sinal 2 CONDICIONAL, `n/d` não penaliza, renormaliza. |
| **D4** | Fórmula/pesos do score de vulnerabilidade | **Pesos S1=0,15 / S2=0,25 / S3=0,35 / S4=0,25** (churn domina); efetivos no Plano B (S2 fora): **S1≈0,20 / S3≈0,467 / S4≈0,333** (`0,15/0,75`, `0,35/0,75`, `0,25/0,75`); normalização percentil-por-universo **[ver emenda BLK-MA-04 no §8.2: `v4` é razão absoluta; o percentil fica reservado]**; RENORMALIZAÇÃO para sinal ausente/imaturo; flags de qualidade; **NÃO-preditivo**. Saída `score_vulnerabilidade ∈ [0,100] = 100·Σ(wi·vi)` + componentes `vi` + flags. | Idem, com S5/S6 fora do MVP. |
| **D5** | Hexágono quente + distância + INVERSÃO | **Quente = `sam_fitness_potencial` alto (top quartil) AND `score_oportunidade_residual < 25` (saturado)**; distância **k=1** (`h3.grid_disk(k=1)`); **INVERSÃO** (demanda alta + residual baixo, oposto de `abrir_agora`) registrada; join READ-ONLY no molde `:68-82` com asserts de invariância. | Idem (Opção A + k=1 + join com asserts). |
| **D6** | Entregável | **Default aceito** — Parquet `data/staging/vulnerabilidade_ma_academias.parquet` (gitignored se nomeado) + CSV `data/outputs/alvos_ma_priorizados.csv` (`sep=";"`/`utf-8-sig`); sem overlay de dashboard no MVP. | Idem. |
| **D7** | Anti-PII | **Default aceito** — só agregados; nome/endereço só no artefato nomeado (gitignored); fixtures sintéticas; fonte real fora do versionamento (DEC-012). | Idem. |
| **D8** | Integração ao cron | **Default aceito** — passo no `run_weekly_90.sh` **pós-regen** mercado/residual (READ-ONLY); sinais de agregador do ativo mensal mais recente com flag de staleness; DEC-013 cobre a extensão do lote. | Idem. |
