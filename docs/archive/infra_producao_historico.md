# Infraestrutura de produção — histórico

> Registro: trechos de história tirados do `docs/infra_producao.md` em 03/11/2026, palavra por palavra, na
> quinta rodada da leiguificação (lista aprovada por Vinicius, responsável pela documentação). O que vale hoje
> está no documento principal; aqui fica como a operação chegou lá. Este arquivo só recebe acréscimo.
> Os números de linha são os da versão anterior ao corte (main `07dd4c34`).

## Integração com gymscraping (repo separado)

*Trecho da linha 200:*

>  (2026-06)

*Trecho da linha 201:*

> > (a antiga "Opção B" foi implementada)

## Arquitetura (o que roda toda semana)

*Trecho da linha 224:*

>  — no lote de 13/09 havia 3 linhas de `Resultado: falha` para ~56 redes defasadas,
>      porque o lote morreu no #28 e as demais nunca rodaram

*Trecho da linha 232:*

>  (2026-10-21)

*Trecho da linha 233:*

>  (o `streamlit` saiu da lista com a DEC-022)

## Integração ao motor (regen mercado/residual — READ-ONLY M1)

*Trecho da linha 242:*

>  — desde a DEC-022; antes
> rodava na imagem do `streamlit` —

*Trecho da linha 244:*

>  (até 2026-09-17 o lote montava `/opt/motor-expansao/app`
> por cima da imagem, e o checkout congelado gravou pins vazios por três semanas)

*Trecho da linha 254:*

>  Antes dele a cadeia começava no
> > `calcular_colunas_mercado`: a academia coletada no domingo entrava no cadastro e **não pressionava
> > ninguém**, porque a oferta espacial de 1 km continuava a da última vez que alguém rodou o Bloco 3 à
> > mão. Custo medido do atraso (DEC-048): nove domingos sem propagar moveram **5.105 hexágonos (60,46%)**
> > e tiraram o white space de **808** — mais que o efeito da própria DEC-048.

## Regeneração semanal da camada de mercado (DEC-059 — o wrapper que assume a etapa 4)

*Trecho da linha 276:*

>  A etapa 4 escrevia **direto no staging vivo**, com `||` tolerante entre
>    os passos: um passo que morria no meio deixava a camada em estado **misto** (mercado novo + carteira
>    velha) e o lote seguia com `exit 0`. Ligar o Bloco 3 — que reescreve a oferta de 1,5 milhão de
>    hexágonos — nesse regime seria irresponsável.

## Sync do diretório de concorrentes dos apps (BLK-CONC-SYNC-01)

*Trecho da linha 404:*

> Antes dele, nenhum passo do ciclo o tocava: medido em 2026-07-29, estava congelado desde 2026-05-28 com 39 CSVs
> > e 39 logos, enquanto o parquet já tinha 106 redes. O registro completo, com o efeito no Streamlit
> > (aposentado pela DEC-022), está em `tasks/completed.md`, BLK-CONC-SYNC-01. 

## Operação manual / troubleshooting

*Trecho da linha 458:*

> ; se os pipelines da cadeia mudarem, re-sincronizar o checkout manualmente

*Trecho da linha 461:*

>  *(O cron **semanal** dos agregadores saiu desta lista
> > no BLK-MA-21 — tem script versionado e seção própria abaixo.)*

## Snapshot semanal de concorrentes (BLK-MA-06 — insumo de churn/staleness)

*Trecho da linha 536:*

>  Quando esta nota foi escrita, os agregadores ainda não tinham cron e valiam ~8 meses; o
> > BLK-MA-21 deu cron próprio a eles, na terça, e a maturação caiu para ~8 **semanas** — que era
> > justamente o caminho com retorno real, em vez de afrouxar o critério.

## Coleta semanal dos agregadores (BLK-MA-21 / DEC-039 — o relógio dos independentes)

*Trecho da linha 569:*

> *(emenda de 2026-08-25)*

*Linha 594:*

> **E o TotalPass agora também roda `--no-resume`.** Sem ele, `TotalPass/pipeline.py` filtra
> `pending = [s for s in slugs if not checkpoint.already_processed(s)]` e retorna cedo com
> `if not pending` — com o checkpoint cheio (34.982 slugs medidos nesta estação: 15.986 completed +
> 50 failed + 18.946 filtered), **praticamente nada era recoletado**. E o `main()` **não parava ali**:
> `split_by_state` rodava em seguida e reescrevia os 27 CSVs por UF em modo `"w"`, com conteúdo
> idêntico e **mtime de agora**. O coletor saía com **sucesso**, então o `|| echo "coletor falhou"` do
> wrapper nunca disparava.

*Trecho da linha 610:*

>  — seguindo a mensagem de erro, o operador apagou o subset filtrado em 2026-09-18 e o universo completo (2,05×) ficou como única cópia

*Trecho da linha 616:*

> > *(emenda de 2026-08-25, régua ajustada para o mínimo em 2026-08-26)*

*Trecho da linha 616:*

>  A guarda nasceu medindo
> > `p.stat().st_mtime` e isso a tornava cega ao caso que ela existe para pegar. Medido no clone real:
> > os 27 CSVs de `TotalPass/csvs/` tinham `mtime` de **hoje** e `data_coleta = 2026-06-01` em
> > **15.982 de 15.986** linhas — **85 dias** reportados como `0`.

*Trecho da linha 628:*

>  *(2026-08-26)*

*Trecho da linha 645:*

>  *(emenda de 2026-08-25)*:
> no laço único anterior, o `totalpass` (primeiro na ordem canônica) já tinha sido publicado quando a
> ambiguidade do `wellhub` levantava, e o destino ficava com meia curadoria de uma semana nova enquanto
> o wrapper abortava

*Linha 654:*

> > Texto original, para registro: **Ação humana pendente, e ela se repete toda SEMANA se não for resolvida.** O wrapper roda o WellHub
> > no modo **default** (filtro do pipeline ligado), em que só `csvs/` é regenerado —
> > `Wellhub/csvs_musculacao/` fica para trás e vira "estritamente mais antigo", que é exatamente o
> > gatilho da linha *ambiguidade* acima. Nesta estação o clone já está nesse estado
> > (`csvs/` de `2026-08-18` contra `csvs_musculacao/` de `2026-08-07`). **Antes da primeira execução
> > agendada:** confirmar de que modo o coletor rodou e **apagar `Wellhub/csvs_musculacao/` à mão**. Com
> > o filtro ligado, `csvs/` já É o subset de musculação e o diretório antigo não tem função.

*Linha 686:*

> 1. **Publicar e aplicar a imagem da API com o BLK-MA-21** (`docs/deploy_api_bot.md`, deploy por
>    digest) **antes de qualquer cron**. Uma imagem antiga escreve com **uma** chave e **apaga** a
>    folha da outra cadência.
> 2. Se o snapshot **semanal** já tiver rodado com a imagem antiga, **copiar
>    `snapshots_concorrentes/` inteiro** e só então migrar o layout **na imagem nova**:
>    `python -m motor_expansao.vulnerabilidade.snapshots --migrar-layout --dry-run` e depois sem o
>    `--dry-run`. A escrita **recusa** semana com arquivo legado solto — sem isso, legado + folha nova
>    da mesma fonte na mesma semana devolve a linha **duas vezes** na leitura, e o erro só aparece
>    dias depois, longe da causa.
>
>    > **A cópia não é zelo, é a única defesa contra a janela residual.** A
>    > migração escreve as folhas num diretório temporário **irmão** de `snapshots_concorrentes/`
>    > e as move por rename atômico. Sobra uma
>    > janela de alguns renames, entre a primeira folha movida e o `unlink` do legado, em que um crash deixa folha nova ao lado do legado — exatamente o par que faz a leitura duplicar linha; eliminá-la
>    > exigiria rename atômico de diretório sobre diretório, que nem POSIX nem Windows oferecem.
>    >
>    > O `--dry-run` **DIAGNOSTICA** em vez de levantar: imprime
>    > `{"migrar_layout": [...], "ambiguas": [...], "dry_run": True}` com **todas** as semanas ambíguas
>    > de uma vez. Se `ambiguas` não vier vazia, **não migre**:
>    > resolva à mão primeiro.
> 3. Conferir os três passos do **BLK-MA-06**, já aplicados na VPS (cópia do wrapper semanal, `DRY_RUN=1`, linha
>    no `run_weekly_90.sh`). É ele quem prova o caminho dos CSVs e o `API_IMAGE`.
> 4. Atualizar o clone `/opt/gymscraping` (traz o `GymScraping` #11 — a caixa exata de `TotalPass/`;
>    sem ele o passo 1 do wrapper aborta com mensagem própria).
> 5. Instalar o wrapper e rodar o modo seco.
> 6. Só então: a linha de crontab e a linha do healthcheck.

*Trecho da linha 754:*

> **Sem guarda de dia do mês** — ela existia só para emular "1ª terça", e com ela cai também o `%`
> escapado (`\%`) que o crontab exigia. 

*Trecho da linha 776:*

>  *(2026-08-26)*

*Trecho da linha 780:*

>  (Não é o *único* valor que separa; a justificativa de unicidade era falsa.) O
> > `45` herdado da premissa mensal deixava passar **até 6 rodadas perdidas** antes do primeiro `FAIL`.

*Trecho da linha 784:*

>  *(emenda de
> > 2026-08-25)*

*Trecho da linha 815:*

>  O
> que ele deixou de ser, com a DEC-066, é a porta que separava o TotalPass do ranking: essa porta virou
> o `SINAIS_INATIVOS`.

## Entregável de M&A no piloto (BLK-MA-19 — os pins de academia no Mapa Territorial)

*Trecho da linha 828:*

>  Entre 2026-08-19 e 2026-08-24 o código dos pins
> esteve publicado e funcionando em produção sem que **nenhum dos dois parquets** tivesse sido
> enviado — a camada não existia para ninguém, e nada acusou. Não havia bloco de backlog, não havia
> linha de runbook, e `scripts/check_artifacts.py` imprimia "OK".

*Linha 942:*

> > **`pins.redes_disponivel` não serve de aceite enquanto a imagem no ar for anterior ao BLK-MA-19.**
> > O campo nasceu nesse bloco (`web/server/app.py`), então **ausente não é falha** — é uma imagem
> > mais velha, e o deploy pode estar perfeito. Ele só passa a valer como sinal depois do merge **e**
> > do próximo deploy de imagem, que é passo separado e manual (por digest, §6 do `CLAUDE.md`). Até
> > lá, o aceite é a contagem de `diag`.

*Trecho da linha 959:*

> **851** na DEC-035; 

## Gerenciar usuários do login (Authelia)

*Trecho da linha 1117:*

> **Com o banco ligado no BR (desde 23/10/2026) e até o corte do P19 (feito em 27/10/2026), quem
> > usava o piloto brasileiro dependia de DOIS cadastros:** o Authelia autenticava (`users_database.yml`)
> > e o banco autorizava (a linha da pessoa em `usuarios`, com o perfil). Sem a linha no banco ela
> > entrava e abria o piloto vazio; sem a entrada no Authelia ela não entrava. 

*Trecho da linha 1125:*

> até o corte, a senha
> > que valia era a do Authelia, e 

*Trecho da linha 1127:*

> > Esse comportamento e o nome da coluna chegaram com a imagem da mudança de 24/10/2026. Na que estava no ar
> > nesse dia (`d1cc438e…`), eles ainda apareciam (o cadeado, para todos) e não deviam ser usados antes do
> > corte: o cadeado pedia a senha inicial sorteada, e a temporária de "Redefinir senha" não abria a entrada.

## Revogar usuário

*Trecho da linha 1166:*

>  Até o corte do P19, quem barra a **entrada** é o Authelia:
> desativar só no banco tira o piloto da pessoa (sem linha ativa em `usuarios` o RBAC não concede
> capacidade nenhuma, e ela abre o piloto vazio), mas ela segue autenticando — e, se o banco cair com
> queda provada, as rotas não sensíveis passam sem conferir permissão (Runbook de incidente, cenário
> 4). Por isso a porta 1 não pode faltar.

*Trecho da linha 1200:*

>  Antes do corte ela já tira o
>    piloto da pessoa (com o banco ligado, o RBAC não concede nada a quem está inativo), mas não a
>    impede de autenticar no Authelia: até o corte, a porta 1 continua obrigatória.

## Hardening do servidor (BLK-SEC-03, aplicado 2026-07-13)

*Trecho da linha 1253:*

> , aplicado 2026-07-13

*Linha 1263:*

> | Kernel | reboot aplicado em 2026-07-13 (5.15.0-177 → 185) | ver política abaixo |

*Trecho da linha 1267:*

>  Validado em
> 2026-07-13.

## Reiniciar tudo

*Trecho da linha 1327:*

> antes do corte do P19, o RBAC do BR
> > responde degradado ou 503 (Runbook de incidente, cenário 4); depois do corte, 

## Alertas automáticos (BLK-SEC-05)

*Trecho da linha 1383:*

> : entre 30/08 e
> > 17/09 ela preservou os pins bons por três semanas seguidas enquanto o mapa servia dado cada vez
> > mais velho, e nada alertou

## Alerta de borda — varreduras com assinatura (2026-09-23)

*Trecho da linha 1439:*

>  (2026-09-23)

*Trecho da linha 1450:*

>  (23/09)

*Trecho da linha 1487:*

>  Espelhar o `run_relatorio_acessos.sh` sem olhar o
> > dono foi o defeito, pego no smoke de instalação em 23/09.

## Runbook de incidente

*Trecho da linha 1540:*

>  Antes do corte quem responde é o Authelia, que não usa o banco.

*Trecho da linha 1557:*

> ; nas anteriores — inclusive a que estava no ar
>   em 24/10/2026 — ele escondia as abas sensíveis (um F5 as traz de volta quando o banco responde)

## Cuidados e boas práticas

*Trecho da linha 1688:*

> ; teto herdado da função do Streamlit — DEC-022
