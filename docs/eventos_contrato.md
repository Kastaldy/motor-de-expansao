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
| `relatorio.gerado` | Pontual, Municipal, Comparação ou Simulador XLSX | conforme o alvo | **`report_id` (UUID, obrigatório)**, `formato`, `origem` |
| `dossie.baixado` | `GET /api/oportunidades/{id}/dossie` | `imovel` | `imovel_id` |

**`report_id` é obrigatório em todo `relatorio.gerado`.** É o que o D17 embute no PDF e o que
permite, dado um arquivo vazado, chegar ao evento e daí a quem o gerou — o `idx_eventos_metadados_report_id`
existe para esse lookup. Um `relatorio.gerado` sem `report_id` não cumpre o D17 e não deve ser gravado.

**`dossie.baixado` tem linha própria** porque é o único artefato que carrega **contato de corretor**
e o único que o motor não gera: vem do coletor imobiliário. É o mesmo problema do D17 com outra fonte.

### 2.3 Escrita de dado

| `tipo` | Quando | `entidade` | `metadados` |
|---|---|---|---|
| `cadastro.editado` | `PUT /api/rede/cadastro/{id}` | `unidade` | `campo`, `de`, `para` |

Hoje é a **única escrita do piloto**, e já tem auditoria própria em `cadastro_log.jsonl` (DEC-023).
Duplicar em `eventos` só se justifica quando o log em arquivo sair — não antes.

### 2.4 Gestos da aba imobiliária

O `POST /api/imobiliaria/evento/{acao}` já tem vocabulário fechado (`ACOES_IMOBILIARIA`), com 404
fora dele. **Nem todos são ação no mesmo grau**, e por isso só três sobem para `eventos`:

| Gesto | Vai para `eventos`? | Por quê |
|---|---|---|
| `marcar-visita` / `desmarcar-visita` | **sim** — `imovel.visita_marcada` / `_desmarcada` | decisão de negócio sobre um imóvel |
| `abrir-dossie` | **sim** — vira `dossie.baixado` | é o pedido do PDF com PII |
| `abrir-aba`, `abrir-imovel`, `ver-no-mapa`, `filtrar` | não | uso de tela; a trilha da DEC-027 já os tem |

### 2.5 Análise pedida

| `tipo` | Quando | `entidade` | `metadados` |
|---|---|---|---|
| `viabilidade.calculada` | `POST /api/viabilidade` | `hexagono` ou `imovel` | metragem, aluguel pedido |

O usuário digita premissas e recebe break-even — é decisão de análise, não leitura passiva.

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

`usuario.criado`, `usuario.desativado`, `usuario.reativado`, `usuario.perfil_alterado` — todos com
`entidade` nula (usuário não é entidade do `CHECK`), e o alvo em `metadados.id_usuario_alvo`.

## 3. Duas coisas que o esquema precisa acomodar

### 3.1 O `CHECK` de `entidade` não cobre o motor

Ele aceita `area_estudo` e `contrato`, que são o domínio **futuro**. As entidades reais das ações do
piloto são **`unidade`**, **`imovel`** e **`hexagono`**. Sem ampliá-lo, essas ações só cabem com
`entidade` nula — o vínculo cai em `metadados` e o `idx_eventos_entidade_entidade_id` deixa de
servir. O **D11** já prevê o caminho: *"ao criar um novo tipo de entidade, adicionar o valor ao
CHECK"*. É migration de uma linha.

Ressalva de tipo: `entidade_id` é `BIGINT`, e o id de imóvel do coletor pode não ser numérico —
conferir antes, ou o vínculo do imóvel fica em `metadados` por necessidade, não por escolha.

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

## 5. O que ainda não existe

Nada disto está implementado: o motor **não grava evento nenhum** hoje. Este documento é o contrato
que a implementação deve seguir, e ela é trabalho novo — o esquema já comporta, exceto pelo `CHECK`
da §3.1.
