# Contrato da tabela `eventos` — o que o motor registra, e como

> Vocabulário fechado de `tipo` e o de-para de cada ação para `entidade`/`metadados`.
> A tabela em si é do `banco-de-reservas` (`esquema-do-banco.md` §4); este documento é o
> contrato de **uso** — quem grava o quê, e com que forma.
>
> Decidido em **P20** (01/09/2026): `eventos` registra **todas as ações relevantes**.
> Responsável: Vinícius · Setembro 2026

## 1. O que entra, e o que não entra

**Entra: ação.** Algo que alguém *decidiu fazer* — entrar na plataforma, gerar um relatório,
descartar uma área, atribuir um consultor. Uma linha por decisão.

**Não entra: telemetria.** A trilha da **DEC-027** grava uma linha por requisição HTTP, incluindo as
que a SPA dispara sozinha ao abrir uma tela (`/api/me`, `/api/ufs`, a carga da UF). Ela continua em
JSONL, com retenção de 90 dias podada pelo backend.

A separação não é estética. A trilha é ordens de grandeza maior — dezenas a centenas de requisições
por sessão contra um punhado de ações — e juntar as duas afogaria as consultas de auditoria do
**D17** num volume que não é delas, além de empurrar o **P7** (particionamento de `eventos`) do
"quando o volume pesar" para o primeiro mês.

> **Teste prático para decidir onde algo vai:** se a pessoa não fez nada e o registro aparece, é
> telemetria. Se ela clicou, escolheu ou digitou para que aquilo acontecesse, é ação.

## 2. Vocabulário de `tipo`

O **D11** deixa `tipo` como texto livre e manda "padronizar na aplicação, para não fragmentar
filtros". Esta é a padronização. **Nenhum `tipo` fora desta lista deve ser gravado** — acrescentar
um valor é editar esta tabela primeiro.

### 2.1 Acesso e sessão

| `tipo` | Quando | `entidade` | `metadados` |
|---|---|---|---|
| `login` | Entrada na plataforma | — | `origem` (`web`/`bot`) |
| `logout` | Saída explícita | — | — |
| `ciencia.confidencialidade` | Clique no OK do pop-up de entrada | — | — |
| `bot.autorizado` | Senha do bot aceita | — | `chat_hash` |

> **`login` ainda não é registrável.** Enquanto o Authelia autenticar, a entrada não passa pelo
> backend — o piloto só recebe o `Remote-User` já resolvido. O registro completo depende da epic de
> autenticação decidida no **P19**. Até lá, o mais próximo é a primeira requisição da sessão, que a
> trilha da DEC-027 já tem.

### 2.2 Geração de artefato — o núcleo do D17

| `tipo` | Quando | `entidade` | `metadados` |
|---|---|---|---|
| `relatorio.gerado` | Pontual, Municipal, Comparação ou Simulador XLSX | — (ver D24) | **`report_id` (UUID, obrigatório)**, `relatorio`, `formato`, `origem`, e o alvo (`hex_id`/`imovel_id`/`unidade_id`) quando houver |
| `dossie.baixado` | `GET /api/oportunidades/{id}/dossie` | — | `imovel_id` |

**`report_id` é obrigatório em todo `relatorio.gerado`.** É o que o D17 embute no PDF e o que
permite, dado um arquivo vazado, chegar ao evento e daí a quem o gerou — o `idx_eventos_metadados_report_id`
existe para esse lookup. Um `relatorio.gerado` sem `report_id` não cumpre o D17 e não deve ser gravado.

> **`relatorio` é chave nova (10/09), e ela faltava.** A linha acima põe os QUATRO relatórios sob o
> mesmo `tipo`, e `formato` sozinho não os separa — Pontual e Municipal são ambos `pdf`. Sem uma
> chave dizendo qual é qual, o lookup do D17 devolveria "um PDF" em vez de "o Relatório Pontual de
> tal ponto". Produtor em `motor_expansao.db.eventos.registrar_relatorio`.

> **O que o Pontual ainda NÃO grava: o alvo.** A rota recebe `lat`/`lng` e um rótulo de texto livre
> — não recebe `hex_id` nem `imovel_id`. Derivar o hexágono da coordenada seria possível (H3 res 7),
> mas afirmaria um alvo que o pedido não declarou. Enquanto o front não enviar a chave, o evento sai
> sem alvo: o `report_id` sozinho já cumpre o D17, e o alvo é refinamento de consulta.

> **Estado por superfície (10/09).** **Pontual** e **Comparação**: produtor ligado, com quem gerou e o
> `report_id` na marca-d'água de todas as páginas e nos metadados `/Info`. O deck da Comparação **não
> tinha marca-d'água nenhuma** até aqui — era a superfície mais exposta do piloto, e um deck vazado
> não carregava nada apontando para pessoa, só um `set_author` fixo igual para todo mundo.
> **Municipal**: produtor ligado desde 10/09 — a marca-d'água dele já existia, mas o `solicitante`
> que ela usa nunca chegava preenchido, então saía só a base. **Simulador XLSX**: ligado em 10/09 com
> um carimbo PRÓPRIO, porque planilha não tem content stream onde desenhar marca-d'água — um bloco
> **visível** no fim da aba `Afericao` e as propriedades do documento (`docProps/core.xml` +
> `docProps/custom.xml`), invisíveis, dentro do ZIP que todo `.xlsx` é. As duas camadas são
> complementares e as duas falham: a visível morre se apagarem as linhas, a invisível morre no
> copy-paste de células para uma pasta nova, no "salvar como CSV" e no Inspetor de Documento do
> Excel. **Exports da Rede** (ficha, carteira): fora do contrato de eventos.
>
> A marca-d'água compartilhada vive em `dashboard/pdf_base.py`, junto do `UltraPDF`. Os dois
> geradores legados seguem com a cópia deles, pela razão escrita no cabeçalho daquele módulo — e o
> `test_a_marca_dagua_dos_tres_parte_da_mesma_base` é o que impede a triplicação de virar
> quadruplicação em silêncio.

**`dossie.baixado` tem linha própria** porque é o único artefato que carrega **contato de corretor**
e o único que o motor não gera: vem do coletor imobiliário. É o mesmo problema do D17 com outra fonte.

### 2.3 Escrita de dado

| `tipo` | Quando | `entidade` | `metadados` |
|---|---|---|---|
| `cadastro.editado` | `PUT /api/rede/cadastro/{id}` | — | `unidade_id`, `campo`, `de`, `para` |

Hoje é a **única escrita do piloto**, e já tem auditoria própria em `cadastro_log.jsonl` (DEC-023).
Duplicar em `eventos` só se justifica quando o log em arquivo sair — não antes.

### 2.4 Gestos da aba imobiliária

O `POST /api/imobiliaria/evento/{acao}` já tem vocabulário fechado (`ACOES_IMOBILIARIA`), com 404
fora dele. **Nem todos são ação no mesmo grau**, e por isso só dois sobem para `eventos`:

| Gesto | Vai para `eventos`? | Por quê |
|---|---|---|
| `marcar-visita` / `desmarcar-visita` | **sim** — `imovel.visita_marcada` / `_desmarcada`, com `imovel_id` em `metadados` | decisão de negócio sobre um imóvel |
| `abrir-dossie` | **não** — quem grava é o `GET` do PDF (§2.2) | o gesto dispara mesmo quando não há dossiê |
| `abrir-aba`, `abrir-imovel`, `ver-no-mapa`, `filtrar` | não | uso de tela; a trilha da DEC-027 já os tem |

> **Correção de 16/09, antes de existir produtor.** Até aqui esta tabela dizia que `abrir-dossie`
> "vira `dossie.baixado`" — e a §2.2 diz que quem o produz é o `GET /api/oportunidades/{id}/dossie`.
> Seguir as duas ao pé da letra daria **dois eventos por clique** no único artefato que carrega
> contato de corretor.
>
> O desempate não é de gosto, é de fato medido na tela: o front dispara o gesto **sempre** — inclusive
> quando o imóvel não tem dossiê, caso em que ele manda `detalhe: relatorio-pontual` — e só busca o
> PDF quando `tem_dossie`. Produzir no gesto registraria "dossiê baixado" em downloads que não
> aconteceram; produzir nos dois contaria cada um duas vezes. O evento nasce onde o arquivo é
> entregue, e o gesto continua no rastro de 90 dias da DEC-027, como os outros quatro.

### 2.5 Análise pedida

| `tipo` | Quando | `entidade` | `metadados` |
|---|---|---|---|
| `viabilidade.calculada` | `POST /api/viabilidade` | — | `m2`, `aluguel`, `demanda`, `origem` |

O usuário digita premissas e recebe break-even — é decisão de análise, não leitura passiva.

> **Correção de 16/09: o alvo saiu, porque ele nunca existiu no pedido.** Esta linha pedia
> `hex_id` e/ou `imovel_id`, e **nenhum dos dois chega à rota**: `ViabilidadeIn` carrega
> `lat`/`lng` e as premissas financeiras, e as duas telas que a chamam — o bloco da tela de Ponto
> e a tela de Viabilidade — só têm a coordenada (medido nas duas chamadas do front). O backend
> também não deriva alvo: usa `lat`/`lng` apenas para escolher a malha do catchment.
>
> As duas saídas aparentes estão fechadas pelo próprio contrato. Derivar o hexágono da coordenada
> (H3 res 7) é o que a §2.2 já recusou para o Pontual — *"afirmaria um alvo que o pedido não
> declarou"*. E gravar a coordenada esbarra na §4: `lat`/`lng` são exatamente o que a regra de PII
> mantém fora de `metadados`. Especificar um alvo que o produtor não pode preencher só garantiria
> que ele nascesse mentindo ou vazio.
>
> Ficam as PREMISSAS, que são o conteúdo real do ato: metragem (`m2`), aluguel pedido (`aluguel`) e
> a demanda — que a DEC-009 define como premissa explícita do operador, nunca prevista, e é ela que
> governa o cálculo inteiro. O evento responde *"fulano rodou viabilidade com estas premissas, e
> quando"*, que é a pergunta de auditoria que esta seção existe para responder.
>
> **Sem alvo, o evento continua valendo — e isso é o oposto da §2.4, de propósito.** Lá, um
> `imovel.visita_marcada` sem `imovel_id` não responde nada: o alvo é o conteúdo inteiro. Aqui o
> conteúdo é a premissa, e o ato é a análise.

### 2.6 Áreas de estudo e contratos (domínio da F5.4, ainda não construído)

| `tipo` | `entidade` | `metadados` |
|---|---|---|
| `area_estudo.criada` | `area_estudo` | `metodo`, `parametros` |
| `area_estudo.editada` | `area_estudo` | `campo`, `de`, `para` |
| `area_estudo.status_alterado` | `area_estudo` | `de`, `para`, `motivo` |
| `contrato.criado` | `contrato` | `metodo`, `parametros` |
| `contrato.promovido` | `contrato` | `id_area_estudo`, `contrato_anterior` |
| `contrato.editado` | `contrato` | `campo`, `de`, `para` |
| `contrato.status_alterado` | `contrato` | `de`, `para` |

### 2.7 Gestão de acesso

| `tipo` | `entidade` | `entidade_id` | `metadados` | grava? |
|---|---|---|---|---|
| `usuario.perfil_alterado` | `usuario` | id do alvo | `de`, `para` | **sim** |
| `usuario.desativado` / `usuario.reativado` | `usuario` | id do alvo | — | **sim** |
| `usuario.criado` | `usuario` | id do **criado** | `perfil` | **sim** (desde a D26) |
| `usuario.senha_definida` | `usuario` | id de quem trocou | `primeira_vez` | **sim** (desde a D26) |
| `usuario.senha_redefinida` | `usuario` | id de quem **teve a senha redefinida** | `tinha_senha_propria` | **sim** (desde 15/09) |
| `usuario.troca_exigida` | `usuario` | id de quem **vai ter de trocar** | — | **sim** (desde 15/09) |

**Aqui são duas pessoas por linha, e elas não podem se confundir.** `id_usuario` é **quem fez** —
chega por `app.id_usuario`, como em todo evento. `entidade_id` é **quem sofreu**. Foi para isso que a
D24 pôs `usuario` no `CHECK`: é a única das entidades novas cujo id é `BIGSERIAL` deste banco, então
o par funciona como projetado, e `idx_eventos_entidade_entidade_id` passa a responder *"tudo que já
fizeram com esta pessoa"* — a pergunta de auditoria da tela de administração.

**Nunca o login nem o e-mail do alvo em `metadados`** — é PII, e a §4 vale aqui como em todo lugar.
O id basta: quem tem acesso a `eventos` resolve o nome em `usuarios`.

**`usuario.criado` é o único caso em que o alvo não existia antes da ação**, e por isso o
`entidade_id` só pode ser preenchido depois do `RETURNING id_usuario` do próprio `INSERT`. Trocar as
duas pessoas de lugar aqui produziria um evento afirmando que **o admin** foi criado — a inversão
mais fácil de cometer e a mais difícil de notar depois.

**`usuario.senha_definida` é o único caso em que autor e alvo coincidem de propósito.** Em todo o
resto desta seção eles são pessoas diferentes, e `_recusar_auto_alvo` existe justamente para impedir
que alguém mude o próprio acesso pela tela. Trocar a própria senha é o oposto: é a única coisa que
**só** a própria pessoa deveria poder fazer. `metadados` leva apenas `primeira_vez` (booleano) —
nunca a senha, nunca o hash, nunca parte de nenhum dos dois.

> **O que a criação NÃO resolve, e continua valendo.** Criar linha em `usuarios` **não** cria a
> pessoa no `authelia/users_database.yml`, que é quem autentica até o **P19** ser executado. A tela
> avisa isso em voz alta depois de criar, com o login a cadastrar; sem esse aviso a criação seria uma
> armadilha silenciosa — a pessoa apareceria na lista e não entraria, sem pista do porquê.
>
> `senha_hash` deixou de ser coluna sem consumidor: desde a D26 ela guarda um PHC Argon2id de
> verdade, produzido só por `motor_expansao.db.senhas.gerar`. O que ela ainda **não** faz é
> autenticar — a senha existe, é verificável e tem ciclo de vida, mas o caminho do login segue no
> Authelia. É preparação para o corte do P19, não o corte.

**Os dois gestos sobre a senha DE OUTRA PESSOA (15/09/2026).** Até aqui, mexer na credencial de
alguém que não é você não tinha tipo nenhum — era a dívida aberta em 14/09, quando as quatro linhas
semeadas (`hash_de_teste_1..4`, que não são PHC e não autenticavam nada) receberam hash de verdade por
reparo de manutenção sem deixar evento. A tela de administração passou a ter os dois gestos, e cada
um ganhou o seu tipo:

- **`usuario.senha_redefinida`** — o admin devolve a pessoa à senha inicial compartilhada e liga a
  marca de troca. É o caminho de quem esqueceu a senha. `metadados.tinha_senha_propria` diz se o
  gesto **apagou** uma senha que a pessoa escolheu: a diferença entre arrumar o acesso de quem nunca
  entrou e derrubar a senha de alguém. Registra **sempre**, mesmo quando a pessoa já estava na
  inicial — "já estava assim" não é verificável pelo hash, que pode guardar qualquer coisa.
- **`usuario.troca_exigida`** — liga `deve_trocar_senha_usuario` sem mexer na senha, depois de uma
  suspeita de vazamento. A migration `016` previa o gesto, e a coluna só andava numa direção. Aqui
  "já estava assim" é verificável (é um booleano), então vale a regra da tela: sem mudança, sem
  evento.

Nos dois, autor e alvo são pessoas **diferentes**, e `_recusar_auto_alvo` vale: quem sabe a própria
senha a troca por `usuario.senha_definida`. É por isso que nenhum dos dois reaproveita aquele tipo —
ele é o único em que autor e alvo coincidem de propósito, e seu `primeira_vez` deriva de
`senha_definida_em_usuario IS NOT NULL`, coluna que a redefinição deixa **nula**. O evento afirmaria,
na mesma transação, o que a coluna nega.

**O que continua descoberto.** O reparo de 14/09 **não** ganha evento retroativo, e um script ou
`UPDATE` feito à mão continua sem deixar rastro em `eventos` — é a hipótese que a §3.2 já admite:
*"a aplicação esquece, o SQL manual não passa por ela"*. O único vestígio desse caminho é
`atualizado_em_usuario`, que não diz qual coluna mudou nem por quem, e nenhuma *trigger* supre o
evento (a auditoria do D19 é sobre `perfil_permissoes`). A diferença é que agora existe um caminho
com rastro para o mesmo gesto, e o manual deixou de ser o único.

## 3. O que o esquema precisa acomodar

Duas questões de modelo. A primeira está **resolvida** (D24, migration `014`); a segunda segue
aberta e depende da F5.4 existir.

### 3.1 O alvo das entidades do motor vai em `metadados` (D24 — resolvido)

O `CHECK` de `entidade` aceita só `area_estudo` e `contrato`. A saída aparente seria ampliá-lo para
`unidade`, `imovel` e `hexagono` — **e ela não funciona**. A razão não é o vocabulário, é o tipo.

`chk_evento_entidade` obriga o par a andar junto: ou `entidade` e `entidade_id` são os dois nulos, ou
os dois estão preenchidos. Não existe preencher só o rótulo. E `entidade_id` é `BIGINT`, porque
aponta para o `BIGSERIAL` de uma tabela **daquele** banco. Os três ids do motor foram conferidos no
código, e nenhum é numérico:

| Entidade | Id | Onde nasce |
|---|---|---|
| `imovel` | `im_3f2a9b` (regex `im[-_][0-9a-fA-F]+`) | `_dossie_index`, `web/server/app.py` |
| `unidade` | slug `patio-brasil-df`, `aguas-claras-df-2` | `resolver_identidade`, `dashboard/rede_metricas.py` |
| `hexagono` | índice H3, 15 caracteres | `hex_id`, `str()` em todo o motor |

Então `entidade = 'imovel'` exigiria um `entidade_id` que não existe: ampliar o `CHECK` trocaria uma
recusa por outra.

**Decidido na D24: o vínculo vive em `metadados`, com índice de expressão** — o mesmo padrão que a
tabela já usa para o `report_id` do D17. A migration `014` criou os três
(`idx_eventos_metadados_imovel_id`, `_unidade_id`, `_hex_id`), parciais por presença da chave e
compostos com `criado_em_evento`.

**O `CHECK` muda numa coisa só, e não é nenhuma das três: `usuario` entra.** É a exceção que a
regra produz — `usuarios.id_usuario` é `BIGSERIAL` daquele banco, exatamente o caso para o qual as
duas colunas foram feitas. Ver a §2.7.

O ganho é de coerência: `entidade`/`entidade_id` continuam significando uma coisa só — linha de uma
tabela daquele banco. Nas alternativas descartadas (trocar o tipo para `TEXT`, ou dar ao banco um
registro próprio de imóveis e hexágonos) o par passaria a significar às vezes isso e às vezes um
identificador externo, e nenhuma consulta poderia confiar nele sem saber de antemão qual caso está
lendo.

> **Os nomes das chaves são contrato.** `imovel_id`, `unidade_id`, `hex_id` — exatamente como o motor
> os chama. Gravar `id_imovel` ou `imovel` põe o evento fora dos índices, e o defeito é **silencioso**:
> a escrita passa, a consulta fica lenta, e ninguém descobre até a tabela crescer.

> **Emenda ao D17.** A convenção dizia que todo `relatorio.gerado` carrega `report_id` **e**
> `entidade`/`entidade_id`. A segunda metade só vale quando o alvo é linha do banco: relatório sobre
> hexágono ou imóvel põe o alvo em `metadados`. O `report_id` segue obrigatório sempre.

### 3.2 Transição de status: trigger ou aplicação?

`status_area_estudo` e `status_contrato` são colunas que **sobrescrevem**. Descartar uma área ou
encerrar um contrato apaga o estado anterior — não há como responder *"quando isto virou analisada?"*
ou *"quem descartou?"*. `eventos` passa a ser a única fonte dessa resposta.

É o mesmo problema que o **D19** resolveu para permissões, e vale o mesmo raciocínio: a aplicação
esquece, o SQL manual não passa por ela. **Recomendação: trigger `AFTER UPDATE ... WHEN (OLD.status
IS DISTINCT FROM NEW.status)`**, que grava o fato (de → para, quem, quando) sem depender de ninguém
lembrar.

O custo é que a trigger não conhece o **motivo**, que só a tela coleta. A saída é o mesmo mecanismo
do `app.id_usuario`: a aplicação declara `SET LOCAL app.motivo = '...'` na transação, e a trigger o
lê com `current_setting(..., true)` — nulo quando não houver, como já acontece com o autor.

Isso é decisão de modelo e pertence ao `banco-de-reservas`; fica registrada aqui como a
recomendação que este contrato pressupõe.

## 4. Regras invioláveis

- **Sem PII em `metadados`** (convenções §5): nada de nome, CPF, e-mail. Só parâmetros técnicos,
  ids e valores de campo. O `solicitante` de um relatório é **texto digitado pelo usuário** e não
  deve ser copiado para cá.
- **`ip` é PII retida por prazo indeterminado** — base legal e retenção seguem abertas no **P15**.
- **Append-only**: `eventos` não tem `atualizado_em` e nunca é atualizado (§4).
- **Todo `relatorio.gerado` carrega `report_id`.** Sem ele, o D17 não fecha.
- **`tipo` fora deste documento é defeito**, não estilo — o D11 alerta que texto livre fragmenta
  filtro, e a padronização é aqui.

## 5. O que já grava, e o que não

**Grava (desde 02/09/2026):** `usuario.perfil_alterado`, `usuario.desativado` e
`usuario.reativado`, escritos pela tela de administração de usuários. São os primeiros eventos do
sistema, e cada um sai na **mesma transação** da mudança que descreve
(`motor_expansao.db.usuarios`).

**Grava (desde a D26):** `usuario.criado` e `usuario.senha_definida`, pela mesma tela e pela mesma
regra de unidade de trabalho. **Desde 15/09**, também `usuario.senha_redefinida` e
`usuario.troca_exigida`. Com eles, os **sete** tipos da §2.7 têm produtor — a §2.7 é a única seção
deste contrato cujo vocabulário está inteiramente implementado.

**Cuidado com a frase acima:** ela diz que os sete tipos *declarados* têm produtor, não que tudo o
que acontece com `usuarios` vira evento. Um `UPDATE` feito à mão, fora da tela, continua sem deixar
rastro — ver *"O que continua descoberto"* no fim da §2.7.

**Grava (desde 16/09):** `dossie.baixado` (§2.2), pelo **`GET` do PDF** — e não pelo gesto
`abrir-dossie`, que dispara mesmo quando o imóvel não tem dossiê (ver a correção no fim da §2.4).
E `imovel.visita_marcada` / `imovel.visita_desmarcada` (§2.4), pelos dois gestos que aquela seção
manda subir; os outros cinco continuam só na trilha de 90 dias. E `viabilidade.calculada` (§2.5),
pela rota que devolve o payload — com as PREMISSAS, sem alvo, pela razão medida que está no fim
daquela seção.

> **Esta seção ficou desatualizada por um dia, e vale registrar.** A frase abaixo dizia "todo o
> resto", e ela passou a ser falsa no mesmo commit que criou o produtor do dossiê — a §2.2 ganhou
> produtor e a §5 continuou anunciando que nada fora da §2.7 gravava. Contrato e implementação
> andam juntos: quem acrescenta produtor edita as duas seções.

**Não grava:** o que resta das famílias §2.1 a §2.6 — `login`, `logout`, `ciencia.confidencialidade`
e `bot.autorizado` (§2.1), `cadastro.editado` (§2.3) — que a própria §2.3 manda **não** duplicar
enquanto o log em arquivo existir — e a família inteira da §2.6, que depende da F5.4 existir. `login` segue sem produtor por outro motivo, e não por
falta de coluna: enquanto o Authelia autenticar, a entrada não passa pelo motor — é o P19 que
destrava esse, não a D26.

**O esquema comporta tudo isto.** A D24 fechou a última pendência de modelo e a `014` criou os
índices que faltavam; a `015` acrescentou a capacidade que separa ver o painel de mudar quem entra.
