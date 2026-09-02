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
| `relatorio.gerado` | Pontual, Municipal, Comparação ou Simulador XLSX | — (ver D24) | **`report_id` (UUID, obrigatório)**, o alvo (`hex_id`/`imovel_id`/`unidade_id`), `formato`, `origem` |
| `dossie.baixado` | `GET /api/oportunidades/{id}/dossie` | — | `imovel_id` |

**`report_id` é obrigatório em todo `relatorio.gerado`.** É o que o D17 embute no PDF e o que
permite, dado um arquivo vazado, chegar ao evento e daí a quem o gerou — o `idx_eventos_metadados_report_id`
existe para esse lookup. Um `relatorio.gerado` sem `report_id` não cumpre o D17 e não deve ser gravado.

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
fora dele. **Nem todos são ação no mesmo grau**, e por isso só três sobem para `eventos`:

| Gesto | Vai para `eventos`? | Por quê |
|---|---|---|
| `marcar-visita` / `desmarcar-visita` | **sim** — `imovel.visita_marcada` / `_desmarcada`, com `imovel_id` em `metadados` | decisão de negócio sobre um imóvel |
| `abrir-dossie` | **sim** — vira `dossie.baixado` | é o pedido do PDF com PII |
| `abrir-aba`, `abrir-imovel`, `ver-no-mapa`, `filtrar` | não | uso de tela; a trilha da DEC-027 já os tem |

### 2.5 Análise pedida

| `tipo` | Quando | `entidade` | `metadados` |
|---|---|---|---|
| `viabilidade.calculada` | `POST /api/viabilidade` | — | `hex_id` e/ou `imovel_id`, metragem, aluguel pedido |

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

| `tipo` | `entidade` | `entidade_id` | `metadados` | grava? |
|---|---|---|---|---|
| `usuario.perfil_alterado` | `usuario` | id do alvo | `de`, `para` | **sim** |
| `usuario.desativado` / `usuario.reativado` | `usuario` | id do alvo | — | **sim** |
| `usuario.criado` | `usuario` | id do alvo | `perfil` | não — ver abaixo |

**Aqui são duas pessoas por linha, e elas não podem se confundir.** `id_usuario` é **quem fez** —
chega por `app.id_usuario`, como em todo evento. `entidade_id` é **quem sofreu**. Foi para isso que a
D24 pôs `usuario` no `CHECK`: é a única das entidades novas cujo id é `BIGSERIAL` deste banco, então
o par funciona como projetado, e `idx_eventos_entidade_entidade_id` passa a responder *"tudo que já
fizeram com esta pessoa"* — a pergunta de auditoria da tela de administração.

**Nunca o login nem o e-mail do alvo em `metadados`** — é PII, e a §4 vale aqui como em todo lugar.
O id basta: quem tem acesso a `eventos` resolve o nome em `usuarios`.

> **`usuario.criado` ainda não tem produtor**, e a razão não é preguiça: criar linha em `usuarios`
> não cria a pessoa no Authelia, que autentica até o **P19** ser executado, e `senha_hash` é
> `NOT NULL` sem consumidor. A tela de administração nasce com trocar perfil e ativar/desativar; a
> criação segue manual até a epic de autenticação fechar esse buraco.

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

**Grava (desde 02/09/2026):** os três da §2.7 — `usuario.perfil_alterado`, `usuario.desativado` e
`usuario.reativado` —, escritos pela tela de administração de usuários. São os primeiros eventos do
sistema, e cada um sai na **mesma transação** da mudança que descreve
(`motor_expansao.db.usuarios`).

**Não grava:** todo o resto. As famílias §2.1 a §2.6 são contrato para implementação futura, e as
da §2.6 dependem da F5.4 existir.

**O esquema comporta tudo isto.** A D24 fechou a última pendência de modelo e a `014` criou os
índices que faltavam; a `015` acrescentou a capacidade que separa ver o painel de mudar quem entra.
