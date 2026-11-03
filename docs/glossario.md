# Glossário do Motor de Expansão

> **Em poucas palavras**
> - **Do que trata:** as palavras que aparecem nos documentos, nas telas e nos relatórios do Motor, explicadas sem jargão.
> - **Quando ler:** quando um documento usar um termo que você não conhece, ou antes de ler os documentos técnicos pela primeira vez.
> - **Atenção:** aqui está o sentido de cada termo; a regra exata e os números ficam no documento ou na decisão indicada em "Mais".

O Motor de Expansão é o sistema da Ultra Academia (rede de academias low-cost, para o público de massa) que
ajuda a decidir onde abrir unidades novas. Os termos estão agrupados por assunto. "Decisão nº N" é o arquivo
`docs/decisions/` com o número em três dígitos (a decisão nº 7 é a `DEC-007.md`; a nº 77, a `DEC-077.md`).

## O mapa e as notas

- **Site do Motor (piloto web)** — o site de produção, com as telas Início, Mapa, Oportunidades, Ponto,
  Viabilidade, Executiva, Oportunidades imobiliárias e Acessos. "Piloto" é o nome histórico: é o app em uso.
  *Mais:* `docs/arquitetura_app_atual.md`.
- **UF** — a unidade da federação, isto é, o estado (SP, RJ, DF...). Muitos arquivos e telas são lidos um estado
  por vez.
- **Hexágono** — a célula do mapa: um hexágono de uns 5 km² (grade H3, resolução 7). O Brasil tem 1.542.531
  deles na base. Quase toda nota do Motor é dada por hexágono. *Mais:* `docs/m1_outputs_oficiais.md`.
- **Setor censitário** — a menor área do Censo 2022 do IBGE, do tamanho de alguns quarteirões; o Brasil tem
  468.099. É dele que vêm a população e a renda. *Mais:* `docs/relatorio_pontual_censitario.md`.
- **M1 (ranking oficial)** — a nota oficial de 0 a 100 de cada hexágono para decidir onde expandir: a
  população pesa 60% e a renda 40%, as duas comparadas com o país inteiro. É a camada executiva: dela saem os
  municípios aprovados e o ranking oficial da carteira, e ela só muda por decisão registrada. *Mais:* `CLAUDE.md` §3 e `docs/m1_outputs_oficiais.md`.
- **Camada paralela** — qualquer análise complementar ao M1 (a censitária, a de mercado, a de domínio, a
  Viabilidade). Ela ajuda a decidir, mas não altera o ranking oficial. *Mais:* `CLAUDE.md` §4.
- **Score censitário** — a nota de 0 a 100 calculada com os dados das áreas do Censo (por área e, levada ao mapa,
  por hexágono), a mais usada no dia a dia: 60% vem da renda
  por pessoa (R$ 300 vale 0 e R$ 4.000 vale 100) e 40% da população (1.000 pessoas vale 0 e 100.000 vale
  100). É uma régua fixa: a nota de um lugar não muda quando o resto do país muda. *Mais:* decisão nº 40.
- **Híbrido** — a combinação dos dois: o M1 aprova os municípios e o score censitário ordena os hexágonos
  dentro deles. *Mais:* `CLAUDE.md` §4.
- **Renda exibida** — a renda que aparece nas telas e nos PDFs: a do Censo 2022 atualizada para hoje com a
  PNAD Contínua 2025, com fator próprio por estado. Serve só para leitura; as notas usam outra conta.
  *Mais:* decisão nº 75 e `docs/relatorio_pontual_censitario.md`.
- **Faixa** — a cor do hexágono no mapa, em faixas de 10 pontos (de 0-10 a 90-100). *Mais:* `CLAUDE.md` §5.

## Mercado e concorrência

- **Taxa de penetração** — a parcela da população que frequenta academia. Multiplicada pela população, ela
  dá o tamanho do mercado; o Motor usa uma taxa calibrada (decisão nº 60). *Mais:*
  `docs/modelo_mercado_hexagonos.md`.
- **Mercado endereçável (SAM)** — as pessoas que poderiam ser alunas numa região: população × taxa de
  penetração. No mapa, conta só onde o hexágono está numa faixa elegível do M1 e tem 5.000 habitantes ou mais; no relatório de
  um endereço, conta quem mora no alcance escolhido. *Mais:* decisões nº 7 e nº 70.
- **Oferta e capacidade** — quantos alunos as academias de uma região já atendem. Onde há dado, o Motor usa
  a capacidade real da unidade; onde não há, supõe 2.500 alunos. *Mais:* decisão nº 57.
- **Mercado residual (mercado ainda livre)** — o mercado endereçável menos o que as academias de rede e a
  própria Ultra já atendem por perto, nunca abaixo de zero. Responde à pergunta "ainda cabe uma academia
  aqui?". As academias independentes não entram na conta, então o residual não é um mercado vazio: parte dele
  pode já ser atendida por elas. *Mais:* `docs/modelo_mercado_hexagonos.md`.
- **Rede (cadeia)** — academia de bandeira, como Smart Fit e Bluefit. Entram na oferta as unidades do
  cadastro de concorrentes, as de rede achadas nos aplicativos de acesso e as da própria Ultra; os estúdios
  boutique ficam de fora. *Mais:* decisões nº 48 e nº 56.
- **Aplicativos de acesso (agregadores)** — Wellhub e TotalPass, que dão acesso a várias academias com uma
  assinatura. O Motor usa as listas deles para achar unidades e sinais dos concorrentes. *Mais:* decisões
  nº 39 e nº 66.
- **Coleta semanal de concorrentes (GymScraping)** — o robô que, todo domingo, coleta as unidades das redes
  concorrentes e atualiza o mercado. *Mais:* `docs/infra_producao.md`.
- **M&A (alvos de compra)** — a lista de academias independentes que a Ultra poderia comprar, ordenada por
  sinais medidos de fragilidade (o "Plano B" de expansão). *Mais:* `docs/vulnerabilidade_ma_contrato.md`.

## Onde abrir

- **Funil** — o filtro em etapas que escolhe os hexágonos mais promissores: corta os de nota baixa, corta
  onde a concorrência passa do limite e ordena os que sobram. *Mais:* decisões nº 41 e nº 44.
- **Top 10 (Mata Virgem e Premium)** — a recomendação única de onde expandir: 5 hexágonos "Mata Virgem"
  (renda domiciliar de R$ 4.500 ou mais e mercado livre de 2.000 pessoas ou mais) e 5 "Premium" (score
  censitário de 50 ou mais, 10.000 habitantes ou mais e mercado livre medido). A mesma lista sai no site, nos
  PDFs e no robô do Telegram. *Mais:* decisão nº 77.
- **Expansão de domínio** — o plano de "âncoras" por cidade: onde abrir unidades para ocupar uma região
  antes da concorrência, com uma tese para cada uma (ocupar espaço vazio, abrir com disputa, proteger a
  rede, adensar). *Mais:* `docs/expansao_dominio.md`.
- **Oportunidades imobiliárias** — os imóveis anunciados (galpões, lojas, salas comerciais) que servem para
  uma unidade, cada um com a sua ficha. *Mais:* decisão nº 37.

## O endereço e o imóvel

- **Relatório Pontual** — o PDF de um endereço: quem mora em volta (por padrão, num raio de 1,0 km), a renda,
  os concorrentes, o mercado livre e, se pedido, a simulação financeira. Fecha com dois selos independentes,
  um demográfico e um financeiro, sem veredito único. *Mais:* `docs/relatorio_pontual_censitario.md`.
- **Relatório Municipal** — o PDF de uma cidade: bairros, mapas de nota e de mercado livre, concorrência e a
  lista de onde expandir. *Mais:* `docs/relatorio_municipal_template.md`.
- **Alcance** — a área em volta do ponto: raio de 1 ou 2 km, ou o que se alcança em 5 ou 10 minutos de carro.
  *Mais:* decisão nº 74.
- **Zona morta** — o bloqueio do ponto onde a renda ou a população não sustentam uma unidade (renda abaixo
  de R$ 500 ou população abaixo de 5.000). *Mais:* decisão nº 42.
- **Viabilidade** — a simulação financeira de uma unidade num imóvel: investimento, aluguel, alunos mês a
  mês, receita, custos e tempo de retorno. Os números saem de um simulador só; a tela, o PDF e a planilha
  apenas os leem. *Mais:* `PREMISSAS_VIABILIDADE.md`.
- **Demanda** — quantos alunos a unidade deve ter quando estiver madura. É uma premissa que o usuário pode
  editar; o Motor sugere um valor pela metragem do imóvel ou pelo modelo de praça. *Mais:* decisão nº 78.
- **Modelo de praça** — o modelo que sugere a demanda a partir de quem mora a até 10 minutos de carro do
  imóvel. *Mais:* decisão nº 78 e `docs/estado_dos_modelos.md`.
- **Rampa e pico de maturação** — a rampa é a curva de alunos de uma unidade nova, mês a mês, até o tamanho
  de uma unidade madura; o pico é o mês em que ela chega lá. O padrão é 10 meses, medido nas unidades da rede.
  *Mais:* `PREMISSAS_VIABILIDADE.md`.
- **Payback (tempo de retorno)** — quantos meses a unidade leva para devolver o investimento.
- **Aluguel de referência** — o aluguel estimado quando o usuário não digita um: a metragem do imóvel vezes o
  preço mediano do m² nos anúncios da cidade. *Mais:* decisão nº 80.

## A rede Ultra

- **Visão Executiva** — a tela com os números da rede própria (unidades, alunos, faturamento) e os alertas de
  cada unidade. *Mais:* decisão nº 23.
- **Growth** — o sistema interno da Ultra de onde vêm os números das unidades. *Mais:* decisão nº 53.

## Como o projeto trabalha

- **Decisão registrada (DEC)** — cada decisão de produto, de cálculo ou de governança vira um arquivo
  numerado, com data, criticidade e situação (proposta, aprovada, revogada). *Mais:*
  `docs/decisions/README.md`.
- **Arquivo de dados (Parquet)** — o formato em que ficam as bases do Motor (notas, mercado, Censo). Elas não
  ficam no git: são geradas à parte e copiadas para o servidor. *Mais:* `docs/artefatos_dados.md`.
- **PR e merge** — PR (pull request) é o pedido para juntar uma mudança ao código principal; merge é a junção,
  feita depois das verificações automáticas e, quando a criticidade pede, da aprovação humana.
- **Bloco e epic** — bloco é uma tarefa do projeto (código `BLK-...`); epic é um conjunto de blocos. A lista
  do que falta é o `tasks/backlog.md`; o registro do que foi feito é o `tasks/completed.md`.
- **Criticidade** — o grau de risco de uma mudança: Baixa, Média, Alta, Crítica ou Estratégica. Ela define
  quem aprova: Baixa e Média entram sozinhas quando as verificações automáticas passam; Alta e Crítica
  precisam de aprovação humana. *Mais:* decisão nº 16.
- **Verificações automáticas** — os testes e as regras que rodam em toda mudança antes de ela entrar; uma
  delas (o "guard") barra mudança em arquivo protegido sem a aprovação certa. *Mais:*
  `docs/portao_merge_orq21.md`.
- **Robô de tarefas (loop)** — o robô que executa sozinho, num ambiente isolado, só as tarefas marcadas como
  seguras para ele ("loop-safe", uma marca que só uma pessoa põe no bloco). Ele nunca publica versão nova no
  servidor. *Mais:* `docs/loop_autonomo.md`. O **Garimpeiro** é a variante desenhada para rodar na nuvem uma
  vez por dia e abrir um PR com o resultado (`docs/garimpeiro.md`).
- **Servidor (VPS)** — a máquina onde rodam o site, o serviço de relatórios e o robô do Telegram. Todo
  comando nele precisa da confirmação do dono, um a um. *Mais:* `docs/infra_producao.md`.
- **Publicar versão nova (deploy)** — trocar no servidor a versão do site ou do serviço pela versão exata que
  já foi testada (identificada pelo "digest"). É sempre um passo manual. *Mais:* `docs/deploy_piloto_web.md`.
- **Perfil de país** — o arquivo que diz qual país uma instância do Motor atende: moeda, mapa, textos. Cada
  país roda separado; hoje estão no ar o Brasil e a Argentina. *Mais:* `data/perfis/LEIA-ME.md` e decisão
  nº 47.
- **Login próprio (P19)** — o login do site feito pelo próprio Motor, com a senha guardada no banco de dados.
  Está no ar no Brasil desde 27/10/2026; a Argentina ainda usa o sistema de login anterior (Authelia). *Mais:*
  decisão nº 67 e `docs/infra_producao.md`.
- **Banco de dados** — guarda os usuários, as permissões e o registro de ações (por exemplo, quem gerou qual
  relatório). As notas e os mapas não vêm dele: vêm dos arquivos de dados. *Mais:* `docs/banco_conexao.md`.
- **Grafo de conhecimento** — um índice automático do código e da documentação, para achar onde está cada
  coisa e o que chama o quê. *Mais:* `docs/grafo_conhecimento.md`.
