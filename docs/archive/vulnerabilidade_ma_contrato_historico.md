# Contrato de vulnerabilidade para M&A — histórico

> Registro: trechos de história tirados do `docs/vulnerabilidade_ma_contrato.md` em 03/11/2026, palavra por
> palavra, na sexta rodada da leiguificação (lista aprovada por Vinicius, responsável pela documentação). O que
> vale hoje está no documento principal; aqui fica como o contrato chegou lá. Este arquivo só recebe acréscimo.
> Os números de linha são os da versão anterior ao corte (main `327a3a12`).

## Cabeçalho

*Linha 10:*

> > Versão: 2026-07-23 (BLK-MA-01 — design/contrato; **ZERO código de produção**;
> > emenda pós-gate 2 do mesmo dia: distinção coletor-vs-ingestão, chave de snapshot `slug`, e BLK-MA-08)

*Linha 12:*

> > **Emenda BLK-MA-02 (gate de engenharia de 2026-07-29, Vinicius):** seção 6 — payload de 10 colunas (hoje 12, ver emenda DEC-026),
> > chave própria do snapshot, origem da `semana` e **cadência real** (os dois relógios); seção 12 —
> > plug do materializador no runner semanal e o cron dos agregadores como caminho crítico. Marcadas com
> > `[emenda 2026-07-29]`.
> > **Emenda BLK-MA-03 (2026-07-29):** seção 8.1 — granularidade de v1 (hex, não academia), domínio efetivo e tratamento no §8.2/§8.4. Marcada com [emenda BLK-MA-03].
> > **Emenda BLK-MA-04 (2026-07-30, gate humano — G-D1/G-D2/G-D3 ratificados):** §8.1 (v3 do estado `novo`), §8.2 (normalização de v4 — razão absoluta), §8.4 (universo do score, bordas de ausência e flags), §8.5 (grão da linha = academia e contrato de coluna). Marcadas com [emenda BLK-MA-04].
> > **Emenda BLK-MA-04-FU1 (2026-08-12):** §8.5 — alcance da coluna `score_vulnerabilidade_ordenavel`: ela não cobre regime de 1 sinal quando esse sinal é o S3, e o BLK-MA-05 deve segmentar por `n_sinais_disponiveis` antes de ordenar. Marcada com [emenda BLK-MA-04-FU1].
> > **Emenda BLK-MA-19 (2026-08-24):** §3 — `redes_ma_nomeadas_v1` -> **`v2`** e correção do split de
> > precedência de pin (`1.171/1.673` era pré-FU4; hoje é **851/1.993**); §13 — registro dos blocos
> > BLK-MA-12..19 que a decomposição original não conhecia, tabela das **versões de contrato vigentes**
> > e o **critério escrito de "epic concluído"**, que não existia. Marcadas com `[2026-08-24]`.

## Abertura (antes da seção 1)

*Trecho da linha 27:*

>  É a
> especificação que os blocos sucessores (BLK-MA-02..08, seção 13) vão implementar; nenhum extrator, score, join, entregável
> ou cron é escrito neste bloco.

## 1. Cabeçalho, status e guardrails invariantes

*Trecho da linha 47:*

>  e, portanto, **este bloco NÃO cria DEC**

## Insumo real conferido (2026-07-23) — o que os coletores REALMENTE emitem

*Linha 68:*

> - **Rating (sinal 2) NÃO é coletado por coletor nenhum hoje** → habilitá-lo é **ajuste de COLETOR
>   (scraper), não de ingestão**: exige raspar a nota no app TP/WH. Planejado no **BLK-MA-08** (seção 13).

*Linha 74:*

> - **WellHub = mesmo schema do TotalPass (confirmado por Vinicius, 2026-07-23):** logo o WellHub **também
>   não traz nota** → o BLK-MA-08 ajusta os **dois** coletores (TP e WH); não há atalho "só-WellHub" mais
>   barato. (Só há amostra de TotalPass versionada no repo, mas o padrão de colunas é o mesmo.)

## 3. D1 — Universo de "academia independente" e a fonte que retém identidade

*Trecho da linha 127:*

>  Até aqui o §3 falava de um universo só — "TotalPass/WellHub × independente" —, e a camada
>   de exibição herdava esse recorte por não ter outro.

*Linha 154:*

>   > **[correção 2026-08-24 / BLK-MA-19] O split desta linha era `1.171 / 1.673` e envelheceu.** Os
>   > números da DEC-034 foram medidos **antes** do BLK-MA-17-FU4, que introduziu o casamento por nome
>   > (`identidade.py`) e colapsou **mais 320** duplicatas. No artefato materializado hoje
>   > (`redes_ma_nomeadas_v2`) o split é **851 com pin próprio / 1.993 já cobertas** — conferível em
>   > `tem_pin_proprio`, das 2.844 linhas. É esse `851` que o backend desenha (`carregar_redes` filtra
>   > por `tem_pin_proprio`), e é ele que a auditoria do pin tem de usar como expectativa.
>   >

## 4. Contrato dos 6 sinais

*Trecho da linha 170:*

>  até o BLK-MA-08

*Trecho da linha 177:*

>  (era `("s2",)`)

## 5. Mapa "4 sinais originais → Plano B"

*Trecho da linha 197:*

>  (até o BLK-MA-08 ajustar o coletor)

## 6. D2 — Snapshots semanais (churn + staleness)

*Trecho da linha 297:*

>  (*emenda de 2026-08-25*)

*Trecho da linha 310:*

>  — o divisor `4,345` do feed mensal (que sustentava o `78`) morreu
>     junto com a premissa

*Trecho da linha 358:*

>  — corrige afirmação factualmente falsa

*Trecho da linha 359:*

>   A versão anterior desta seção afirmava que "o cron acumula snapshots desde ~26/06/2026". **Isso é
>   falso e foi removido:** nenhum passo do `run_weekly_90.sh` arquiva o feed por estabelecimento
>   (`docs/infra_producao.md:136-143`; o único histórico existente é `historico_contagem.csv`, **por
>   rede**), e os CSVs crus são **sobrescritos** a cada coleta. Em 2026-07-29 havia **ZERO** semanas
>   de série por estabelecimento, e o produtor do insumo nasceu no **BLK-MA-02**.

*Trecho da linha 366:*

> ; o D1 original dizia terça 02:00 UTC

*Trecho da linha 367:*

>  *(Até 2026-08-26 este contrato
>     dizia MENSAL e pendente — as duas coisas deixaram de valer.)*

*Trecho da linha 374:*

> , não por cerca de um ano

## 7. D3 — Rating de agregador (sinal 2)

*Trecho da linha 392:*

> > `SINAIS_INATIVOS` continua `("s2",)` e os pesos efetivos do Plano B seguem
> > `S1≈0,20 / S3≈0,467 / S4≈0,333`.

## 8.1 Componentes `vi ∈ [0,1]` (`1 = máxima vulnerabilidade`)

*Trecho da linha 535:*

> , aprovada em
> > 2026-08-14

## 8.2 Normalização

*Trecho da linha 670:*

>  Esta é
> > a reabertura do §8.2 que o BLK-MA-09 devia fazer — e o gatilho era **este parágrafo**, que
> > nomeava o `rating`, não o item 4 da emenda G-D3 (aquele fala de quem **reativar** a percentil, e o
> > MA-09 não a reativou).

## 10. D6 — Entregável

*Trecho da linha 918:*

>  Junto saíram o terceiro artefato
> > (`alvos_ma_hex.parquet`) e o colapso de regimes, que só existiam para servi-lo.

## 12. D8 — Integração ao cron

*Trecho da linha 977:*

>  — que deixou de ser pendente no BLK-MA-21

*Trecho da linha 988:*

>  Quando esta emenda foi escrita ele aparecia em
>   `infra_producao.md` apenas como "pendente futuro" e **não** como dependência de bloco.

## [2026-08-24] Blocos posteriores ao BLK-MA-11, que a tabela acima não conhecia

*Trecho da linha 1050:*

> ; era terça 02:00 UTC

*Linha 1056:*

> > **[2026-08-25] O arquivamento do TotalPass foi da NOTA, não da fonte — e a distinção abre o
> > BLK-MA-20.** Como a DEC-026 tornou o rating **coluna-fato sem peso**, a ausência permanente de nota
> > no TotalPass é irrelevante para o score, e a assimetria que o §7/D3 e o spike do BLK-MA-10 tratam
> > como "fragmentação permanente do universo" afeta uma coluna de fato, **não o ranking**. Nada neste
> > contrato nem em DEC alguma proíbe o TotalPass como FONTE: o §3/D1 e `FONTES_AGREGADORES` já o
> > declaram agregador de primeira classe, e `fontes_presentes_no_hex` é definido como *subconjunto de
> > `FONTES_AGREGADORES`* — o desenho espera os dois.
> >
> > A consequência que o BLK-MA-20 tem de resolver antes de qualquer inclusão: hoje o `v1` tem
> > **variância zero** (6.753 de 6.753 hexes com um agregador), e soltá-lo no regime `{s1,s6}` — onde
> > o S1 pesa **0,600** — produz um **degrau**, não um discriminador. Detalhe, números e as três vias
> > no bloco.

## O que é "epic BLK-MA concluído" — critério escrito, que faltava

*Trecho da linha 1069:*

> , que faltava

*Trecho da linha 1071:*

> Até 2026-08-24 não havia nenhum. A ausência tem consequência prática: sem critério, "o bloco
> mergeou" foi lido como "a coisa está entregue", e foi assim que a camada passou cinco dias
> publicada e morta. 

*Trecho da linha 1084:*

>  (era `s1,s6` e `30 + 40·v6` até a DEC-066 tirar o S1 da conta)

## 14. Guardrails e referências

*Linha 1128:*

> - **Sem DEC neste bloco:** a rota Google Places/§2 foi descartada no Plano B → BLK-MA-01 **não** cria
>   DEC (reputação externa e seu eventual DEC ficam no BLK-MA-07).

*Trecho da linha 1140:*

> ; a nota **nem existe na fonte** → ajuste de coletor, não de ingestão
