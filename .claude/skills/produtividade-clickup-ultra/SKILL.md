---
name: produtividade-clickup-ultra
description: "Padroniza a gestão de produtividade da equipe no ClickUp (workspace PROJETOS - DEG)   via MCP, usando ETIQUETAS (tags) para Frente e Complexidade. Cada FRENTE é pontuada   e lida separadamente — NUNCA se soma um total entre frentes. Use ao CRIAR, CLASSIFICAR   ou ATUALIZAR tarefas, ATRIBUIR/REBALANCEAR responsáveis, ou GERAR o painel mensal de   produtividade por frente para leitura gerencial/estratégica. Aciona com \"criar tarefa\",   \"classificar tarefa\", \"atribuir\", \"fechar o mês\", \"relatório/painel de produtividade\"."
---

# Produtividade ClickUp — Ultra (PROJETOS - DEG) — versão por Frente

## PRINCÍPIO CENTRAL (inegociável)
Frentes são unidades diferentes — comparar pontos entre elas é comparar manga com uva.
- NUNCA some pontos entre frentes. NUNCA monte um "pontos totais" por pessoa nem um ranking geral.
- Cada frente tem sua própria pontuação e é lida isoladamente.
- O painel serve à visão gerencial/estratégica (capacidade, gargalos, concentração de carga,
  tendência) e ao 1:1 — nunca como nota de desempenho ou pódio entre papéis diferentes.
- O Claude apenas LÊ as etiquetas e calcula via código; nunca inventa ou estima números.

## Três frentes, três leituras (cada uma na sua unidade)
- OPERACIONAL (repetitivo, ex.: scraping, estudos de ponto): unidade = itens. Métrica = itens concluídos ÷ dias disponíveis.
- PROJETO (dev/eng./deploy/feature): unidade = pontos de sizing. Métrica = pontos entregues ÷ dias disponíveis.
- ANÁLISE (estudo/análise/relatório aprofundado): unidade = pontos de sizing. Métrica = pontos entregues ÷ dias disponíveis.
Operacional NÃO usa a escala de pontos de complexidade; é volume.

## Vocabulário de etiquetas (criar uma vez no Space; nomes exatos, com acento)
- Frente: `Operacional` · `Projeto` · `Análise`
- Complexidade (só Projeto/Análise): `Baixa` · `Média` · `Alta`

Regras das etiquetas:
- Toda tarefa recebe EXATAMENTE UMA etiqueta de Frente.
- Projeto/Análise recebe UMA etiqueta de Complexidade. Operacional NÃO recebe.
- Subtarefas / micro-passos NÃO recebem Complexidade (logo, valem 0 ponto). Pontue no nível do entregável.

## Calibragem do sizing (importante para não inflar)
- Baixa = unidade com significado (~meia diária pra cima). NÃO use Baixa para micro-passos de 15-30 min.
- Micro-passos (ex.: "transferir código", "registrar domínio") são SUBTAREFAS do entregável-pai, não tarefas de topo.
- Escala de pontos (apenas DENTRO de Projeto e DENTRO de Análise): Baixa = 1, Média = 3, Alta = 8.

## Regras de classificação da Frente (objetiva)
scraping/coleta repetitiva → Operacional; desenvolvimento/eng./deploy/feature → Projeto;
estudo/análise/relatório aprofundado → Análise. Em dúvida, não chute: deixe sem etiqueta e liste para revisão.
**Scraping/coleta de concorrentes:** cada coletor/academia coletada = 1 item operacional (contagem por unidade,
igual a estudo de ponto). Um lote de 30 academias raspadas = 30 itens, não 1.

### Exceção importante — "estudos de ponto" são OPERACIONAL, não Análise
Estudos curtos e repetitivos de ponto para expansão (~30–40 min cada, em lote/rotina) são VOLUME OPERACIONAL,
apesar da palavra "estudo". Cada estudo = 1 item operacional. NÃO recebem Complexidade nem pontos.
Só vai para Análise o estudo/relatório aprofundado e não repetitivo (sizing por pontos). Regra prática:
se é tarefa de minutos, repetível e contável em lote → Operacional (volume); se é entregável analítico
único que leva horas/dias → Análise (pontos).

## Registro de volume operacional em LOTE (estudos de ponto e afins)
Trabalho operacional repetitivo NÃO vira uma tarefa por unidade. Registre em LOTE: uma tarefa por pessoa
por mês, com a quantidade embutida de forma legível para o relatório.
- Lista de destino: **"Rotina de Estudos"** (pasta "Estudos - Expansão") — `list_id = 901713566217`.
- Etiqueta `operacional` + campo **Frente = Operacional**. SEM Complexidade. Status `concluído` quando fechado.
- Nome no padrão: `Estudos de ponto p/ expansão — <Mês>/<Ano> (<N> estudos)`.
- Na descrição, inclua um marcador legível por código: `[VOL_OPERACIONAL: <N>]`.
  (Se o campo numérico "Quantidade" existir um dia, prefira gravar nele; enquanto não existir, use o marcador.)
- IDs úteis deste workspace:
  - Campo **Frente** `7adab26a-ff95-408e-b8b0-14f8a249e96e` → Operacional `3c64ee76-ff6a-448f-8888-1817591988de`.
  - Pessoas: Juan `101182134` · Vinícius `101182135` · Felipe `296609800`.
- Exemplo de criação:
```
clickup_create_task(
  list_id="901713566217",
  name="Estudos de ponto p/ expansão — Maio/2026 (29 estudos)",
  assignees=["101182134"],
  tags=["operacional"],
  status="concluído",
  due_date="2026-05-30",
  custom_fields=[{"id":"7adab26a-ff95-408e-b8b0-14f8a249e96e","value":"3c64ee76-ff6a-448f-8888-1817591988de"}],
  markdown_description="... [VOL_OPERACIONAL: 29] ..."
)
```

## FLUXO 1 — Criar tarefa nova (uso recorrente da equipe)
1. Lista de destino: pergunte ou use `clickup_get_list`.
2. Responsável: `clickup_resolve_assignees` (aceita "me", nome ou e-mail).
3. Decida a Frente; se Projeto/Análise, confirme a Complexidade na CRIAÇÃO.
4. Crie com `clickup_create_task` passando as etiquetas em `tags` (devem já existir no Space).
```
clickup_create_task(list_id="<LISTA>", name="<NOME>", assignees=["<USER_ID>"], tags=["Projeto","Média"])
clickup_create_task(list_id="<LISTA>", name="<NOME>", assignees=["<USER_ID>"], tags=["Operacional"])
```

## FLUXO 2 — Classificar / backfill de tarefa existente
`clickup_add_tag_to_task(task_id, tag_name)` / `clickup_remove_tag_from_task`. Idempotente.
Nunca adicione Complexidade em Operacional nem em subtarefa.

## CRITÉRIO TEMPORAL — a que mês uma entrega pertence (LEIA ANTES DE QUALQUER FECHAMENTO)
Esta é a regra que evita a maior fonte de erro (contar a mesma entrega no mês errado, inflar ou
esvaziar um mês). Vale para TODO fechamento e comparação.

**Regra base — vale a data de CONCLUSÃO (`date_closed`), não a de criação.**
Uma entrega pertence ao mês em que foi *concluída*. NUNCA use `created_date` para medir entrega
(uma tarefa criada em maio e concluída em junho é entrega de JUNHO).

**Grace period de virada (3 dias corridos).**
Colaboradores às vezes esquecem de marcar como concluído na virada do mês. Por isso:
- Tarefa com `due_date` no mês X, concluída **até o 3º dia corrido** do mês X+1 -> conta em **X**.
- O corte é 3 dias CORRIDOS (não úteis): dias 01, 02 e 03 do mês seguinte.
- Só se aplica a tarefas COM `due_date` no mês X. Tarefa sem `due_date` NÃO entra no grace.

**Tarefas sem `due_date` (ex.: coletores de scraping, itens soltos).**
Seguem `date_closed` puro, sem grace period. Fecharam no mês Y -> contam em Y, ponto.

**Espelho nas duas pontas.** Ao fechar o mês X, o grace traz para X o que tinha prazo em X e fechou
no começo de X+1; e RETIRA de X o que tinha prazo em X-1 e só foi fechado nos primeiros dias de X.
Sempre verifique as DUAS pontas (início e fim do mês).

**Implementação:** puxe por `clickup_filter_tasks` com `date_closed_from`/`date_closed_to` cobrindo
o mês X **mais os 3 primeiros dias de X+1**; depois, no código, reclassifique cada tarefa da janela
extra: se tem `due_date` em X -> fica em X; senão -> é de X+1 e sai. Converta timestamps em fuso BRT
(UTC-3) para não errar a virada do dia. `include_closed=true`, `subtasks=true`, paginando `page` até
`count < 100`.

## COMPROMETIDO vs BÔNUS (taxa de conclusão honesta — substitui o falso "100%")
NUNCA apresente "X pts disponíveis / X entregues = 100%" copiando o realizado para o disponível — isso
é 100% por construção e não significa nada. Em vez disso, separe o backlog do mês em dois baldes:

- **COMPROMETIDO** = tarefas criadas (`created_date`) **até o 20º dia corrido** do mês. É o que o time
  assumiu entregar naquele mês.
- **BÔNUS** = tarefas criadas do **21º dia em diante** (e concluídas no mês, pelo critério temporal acima).
  São entregas extras, além do combinado.

Duas leituras que isso gera (por frente, sempre):
- **Taxa de conclusão do comprometido** = comprometidas concluídas ÷ comprometidas totais. Uma tarefa
  comprometida NÃO concluída no mês derruba essa taxa (é dívida do mês).
- **Volume de bônus** = pontos/itens entregues que estavam fora do comprometido.

O critério temporal (fechamento + grace) e o de comprometido (por criação até dia 20) operam JUNTOS:
uma tarefa criada dia 20 com prazo no mês, concluída dia 02 do mês seguinte, é COMPROMETIDA
(criação <= dia 20) E conta no mês (grace de 3 dias). São filtros independentes aplicados à mesma tarefa.

## FLUXO 3 — Painel mensal POR FRENTE (cálculo embutido, sem total)
1. Puxe as tarefas por `clickup_filter_tasks` usando **`date_closed_from`/`date_closed_to`** (YYYY-MM-DD),
   cobrindo o mês + 3 dias de grace, `include_closed=true`, `subtasks=true`, paginando `page` até `count<100`.
   NÃO use `created_date` para o recorte de entrega (só para separar comprometido vs bônus).
2. Aplique o CRITÉRIO TEMPORAL (grace period, fuso BRT) para decidir o mês de cada tarefa da janela extra.
3. Para cada tarefa, leia etiquetas → frente, complexidade (ou vazio), concluida (status == "concluído").
   - **Multi-responsável (tarefa conjunta):** cada responsável recebe os pontos/itens INTEGRAIS. NÃO divida.
   - **Tarefa-pai/épico sem etiqueta de Complexidade:** vale 0 pts (as subtarefas pontuadas é que contam).
     Nunca some o pai + as subtarefas — seria dupla contagem.
   Para tarefas OPERACIONAIS, leia a QUANTIDADE: marcador `[VOL_OPERACIONAL: N]` na descrição (ou
   `(N estudos)` no nome). Sem marcador, quantidade = 1. **Scraping: cada coletor/academia = 1 item.**
4. Pergunte dias úteis do período e dias indisponíveis por pessoa.
5. NÃO calcule de cabeça. Preencha as variáveis e EXECUTE este código:

```python
import re
from datetime import datetime, timezone, timedelta
from collections import defaultdict
PONTOS = {"baixa":1,"media":3,"média":3,"alta":8}
BRT = timezone(timedelta(hours=-3))
def n(s): return (s or "").strip().lower()
def dt(ms): return datetime.fromtimestamp(int(ms)/1000, BRT) if ms else None

# ── CRITÉRIO TEMPORAL ────────────────────────────────────────────────
# MES_ALVO = (ano, mes) que estamos fechando. Ex.: (2026, 6)
MES_ALVO = (2026, 6)
def mes_de_entrega(t):
    """Retorna (ano,mes) ao qual a tarefa pertence, aplicando grace de 3 dias corridos.
    t precisa de: date_closed (ms), due_date (ms ou None)."""
    cl = dt(t.get("date_closed"));  du = dt(t.get("due_date"))
    if cl is None: return None
    # grace: fechada nos 3 primeiros dias do mês, com due no mês anterior -> conta no anterior
    if du is not None and cl.day <= 3:
        ant = (cl.year, cl.month-1) if cl.month>1 else (cl.year-1, 12)
        if (du.year, du.month) == ant:
            return ant
    return (cl.year, cl.month)
def eh_comprometida(t):
    """Comprometida = criada até o 20º dia corrido do mês-alvo."""
    cr = dt(t.get("created_date"))
    return cr is not None and cr.day <= 20

def qtd_operacional(t):
    """Volume de tarefa operacional: [VOL_OPERACIONAL: N], senão (N estudos), senão 1.
    Scraping/coletor solto = 1 (cai no default)."""
    txt = f"{t.get('nome','')} {t.get('descricao','')}"
    m = re.search(r"VOL_OPERACIONAL:\s*(\d+)", txt, re.I)
    if m: return int(m.group(1))
    m = re.search(r"\((\d+)\s+estudos?\)", txt, re.I)
    if m: return int(m.group(1))
    return 1

# tarefas: cada dict precisa de assignees (lista de nomes), frente, complexidade,
#   concluida, nome, descricao, date_closed, due_date, created_date
tarefas = []          # preenchido a partir do clickup_filter_tasks
disponibilidade = {}  # {"Felipe":22, "Vinícius":22, "Juan":21}

# Sub-balde comprometido/bônus por frente
def novo(): return {"p":0,"c":0}
P = defaultdict(lambda: {
    "op_c":0,"op_a":0,"prj_p":0,"prj_pa":0,"prj_c":0,"ana_p":0,"ana_pa":0,"ana_c":0,
    # comprometido vs bônus (só concluídas): compr_* e bonus_*
    "prj_compr":0,"prj_bonus":0,"ana_compr":0,"ana_bonus":0,"op_compr":0,"op_bonus":0,
    # denominador do comprometido (comprometidas totais, concluídas ou não)
    "prj_compr_tot":0,"ana_compr_tot":0,"op_compr_tot":0})
T = {"op_c":0,"prj_p":0,"prj_c":0,"ana_p":0,"ana_c":0}

for t in tarefas:
    # filtro temporal: só entra quem pertence ao MES_ALVO
    if mes_de_entrega(t) != MES_ALVO and bool(t.get("concluida")):
        # concluída fora do mês-alvo -> ignora nesta apuração
        continue
    f=n(t.get("frente")); c=bool(t.get("concluida"))
    pts=PONTOS.get(n(t.get("complexidade")),0)
    compr = eh_comprometida(t)
    # MULTI-RESPONSÁVEL: pontos/itens INTEGRAIS para cada um (não divide)
    pessoas = t.get("assignees") or ["—"]
    for p in pessoas:
        r=P[p]
        if f=="operacional":
            q=qtd_operacional(t)
            if c:
                r["op_c"]+=q; T["op_c"]+=q
                if compr: r["op_compr"]+=q
                else: r["op_bonus"]+=q
            else: r["op_a"]+=q
            if compr: r["op_compr_tot"]+=q
        elif f=="projeto":
            if c:
                r["prj_p"]+=pts; r["prj_c"]+=1; T["prj_p"]+=pts; T["prj_c"]+=1
                if compr: r["prj_compr"]+=pts
                else: r["prj_bonus"]+=pts
            else: r["prj_pa"]+=pts
            if compr: r["prj_compr_tot"]+=pts
        elif f in ("análise","analise"):
            if c:
                r["ana_p"]+=pts; r["ana_c"]+=1; T["ana_p"]+=pts; T["ana_c"]+=1
                if compr: r["ana_compr"]+=pts
                else: r["ana_bonus"]+=pts
            else: r["ana_pa"]+=pts
            if compr: r["ana_compr_tot"]+=pts

def rate(x,d): return round(x/d,2) if d else 0
def taxa(feito,tot): return f"{round(100*feito/tot)}%" if tot else "—"
print("=== POR PESSOA (cada frente na sua unidade — NÃO somar entre frentes) ===")
for p in sorted(P):
    r=P[p]; d=disponibilidade.get(p,0) or 0
    print(f"\n{p}  (dias disponíveis: {d})")
    print(f"  Operacional: {r['op_c']} itens  ->  {rate(r['op_c'],d)}/dia"
          f"  | comprometido {r['op_compr']}/{r['op_compr_tot']} ({taxa(r['op_compr'],r['op_compr_tot'])}) + bônus {r['op_bonus']}")
    print(f"  Projeto    : {r['prj_p']} pts ({r['prj_c']} tar)  ->  {rate(r['prj_p'],d)}/dia"
          f"  | comprometido {r['prj_compr']}/{r['prj_compr_tot']} ({taxa(r['prj_compr'],r['prj_compr_tot'])}) + bônus {r['prj_bonus']} | abertos {r['prj_pa']}")
    print(f"  Análise    : {r['ana_p']} pts ({r['ana_c']} tar)  ->  {rate(r['ana_p'],d)}/dia"
          f"  | comprometido {r['ana_compr']}/{r['ana_compr_tot']} ({taxa(r['ana_compr'],r['ana_compr_tot'])}) + bônus {r['ana_bonus']} | abertos {r['ana_pa']}")

print("\n=== POR FRENTE (visão de capacidade da equipe) ===")
print(f"  Operacional: {T['op_c']} itens concluídos")
print(f"  Projeto    : {T['prj_p']} pts entregues ({T['prj_c']} tarefas)")
print(f"  Análise    : {T['ana_p']} pts entregues ({T['ana_c']} tarefas)")
```
5. Apresente SEMPRE por frente. Nunca apresente um número único por pessoa.

## FLUXO 4 — Painel em HTML (TEMPLATE CANÔNICO, com GRÁFICOS)
O painel mensal tem UM template visual oficial e fixo, em `template-painel.html` (nesta skill).
TODO relatório é gerado a partir dele, para que a série arquivada fique 100% consistente — é material
recorrente para apresentar ao diretor, então o visual NUNCA varia de um mês para o outro.

Como gerar o relatório do mês:
1. Calcule os números pelo código do FLUXO 3 (nada estimado de cabeça; critério temporal + grace aplicados).
2. COPIE `template-painel.html` para um novo arquivo com o nome padrão:
   `painel-produtividade-<mes>-<ano>.html` (minúsculo, mês por extenso em pt-BR; ex.: `painel-produtividade-junho-2026.html`).
3. Edite **somente o objeto `DADOS`** no topo do `<script>`. NÃO toque em CSS, layout, funções de render
   nem na configuração dos gráficos — é exatamente isso que mantém todos os relatórios idênticos.
4. Preencha `DADOS` com os números do FLUXO 3:
   - `titulo`, `periodo` (badge), `subtitulo`.
   - `pessoas[]`: por frente `{value, unit, rate, backlog}` — `backlog: null` quando não houver;
     `backlog.pct` é só a largura visual da barra (proporção do aberto vs. capacidade da frente).
   - `equipe`: totais por frente (`big` + `sub`). NUNCA um total somando entre frentes.
   - `graficos`: arrays na ordem de `labels` (pessoas). `*Max` define o teto do eixo Y de cada frente.
   - `leitura[]`: um card de análise por destaque (`cor`: op/prj/ana).
   - `rodapeHTML`: método (janela de datas, dias disponíveis, afastamentos, origem dos números).
5. Entregue o arquivo para download e arquive na pasta da série (um arquivo por mês, mesmo nome-padrão).

Regras inegociáveis do template (já embutidas — não quebrar ao editar DADOS):
- Cada frente na SUA unidade: Operacional em **itens** (volume), Projeto/Análise em **pontos** de sizing.
- Nenhum gráfico/eixo mistura itens com pontos; nenhum "ranking geral"; nenhum "pontos totais" entre frentes.
- Cores fixas: Operacional ciano, Projeto âmbar, Análise violeta. Fontes Space Grotesk + JetBrains Mono.
- Estudos de ponto entram como volume Operacional (FLUXO 3 soma a quantidade via `[VOL_OPERACIONAL: N]`);
  se ficarem fora da janela do mês, registre isso nas notas do `rodapeHTML` como volume capturado à parte.
- Os 6 gráficos do template são fixos: Projeto (entregues + vazão), Análise (entregues + vazão),
  Operacional (itens + vazão). Para histórico/tendência mês a mês, NÃO altere o template: gere um painel
  comparativo separado, mantendo as mesmas cores e a regra de não somar entre frentes.

## LEITURA GERENCIAL / ESTRATÉGICA (o que o painel deve responder)
Use os números por frente para decidir, não para ranquear pessoas. Olhe:
- Capacidade e vazão de cada frente (itens/dia, pts/dia) — a frente está dando conta da demanda?
- Backlog e bloqueados por frente — o que está travado e precisa de desbloqueio?
- Concentração de carga (bus factor) — uma frente inteira depende de uma pessoa só? É risco.
- Tendência mês a mês de cada frente e de cada pessoa contra o próprio histórico.
Decisões que isso alimenta: rebalancear carga DENTRO de uma frente, desbloquear itens,
avaliar capacidade (saturação → contratar/realocar), e reconhecer cada um no seu lane.
NUNCA: ranking de pontos totais, comparar pessoas de frentes diferentes pelo mesmo número,
ou usar como nota isolada de desempenho.

## Arquivos desta skill
- `SKILL.md` — este guia.
- `template-painel.html` — TEMPLATE CANÔNICO do relatório (FLUXO 4). Já vem com os dados de Maio/2026 como
  exemplo funcional; para o mês novo, copie o arquivo e edite só o objeto `DADOS`.

## Instalação e uso no Cowork
- Crie antes as 6 etiquetas no Space (nomes exatos acima).
- Adicione esta skill (a pasta inteira, com o `template-painel.html`) em Customize > Skills.
- Fechamento recorrente: abra uma tarefa no Cowork e digite `/schedule`
  (roda só com o computador ligado e o Desktop aberto).