# Caderno do estudo — Inteligência de Unidade (epic BLK-UNI)

Registro corrido, em linguagem de negócio, para virar a apresentação executiva. Cada etapa diz o que se perguntou, o
que foi feito, o que se achou e com que grau de certeza. Atualizado a cada etapa. Detalhe técnico nos arquivos citados.

Última atualização: 2026-10-13. Passagem do estudo para o Juan: ver `README_PASSAGEM.md` (mapa das pastas, como rodar,
regras e agenda).

---

## Mensagens-chave (atualizadas em 13/10; candidatas a slide)

1. **O modelo novo se confirmou em unidades que ele nunca viu.** Ele usa tamanho, renda e população da área de 10 min
   de carro. Ajustado com dado até 2025 e testado em 18 unidades abertas em 2025:
   - acerta o faturamento maduro **sem viés** (+1%) e ordena melhor as praças;
   - a regra atual, que lê só a metragem, **superestima em ~17%** o faturamento das unidades novas;
   - o erro típico do modelo é ~22%; para a diretoria, **22% a 27%** (o número muda com uma unidade a mais ou a menos
     no treino).

   **No simulador, a decisão de aprovar ou não empatou com a regra atual** (72% × 67% de acerto em 18 unidades, com
   custos-padrão). O ganho comprovado é **prever o faturamento e o payback** (o erro do payback cai de 20 para 14 meses),
   e é esse o objetivo (Felipe, 29/09). Modelo de trabalho (v2): praça com renda **domiciliar** + estúdio + master real.
2. **O 3º mês diz quase tudo, e a previsão em dois tempos é a única melhoria clara.** Antes de abrir, a projeção erra
   ~22% o nível maduro; com os alunos do mês 3, o erro cai para 5–9%. Somando os meses 1 a 3 à v2 (UNI-15), o erro do
   nível maduro cai de 22% para 13,5% no balcão e de 39% para 17% no agregador; no faturamento cai 3,5 pontos, sem se
   distinguir do acaso. Só vale depois de abrir, e foi medido em quem abriu **com** agregador.
3. **A rampa real é bem mais rápida que a do simulador.** A unidade abre com ~70–80% do nível maduro (efeito da
   pré-venda) e chega a ~90% no 6º mês. O simulador supõe 500 alunos no mês 1 (~37%) e subestima o 1º ano em ~15% dos
   alunos e ~7% do faturamento. Numa unidade típica, isso vale R$ 225–340 mil de faturamento no 1º ano e 1 a 2 meses
   de payback. É uma correção do 1º ano: o que decide a viabilidade continua sendo o nível maduro.
4. **Balcão e agregador respondem a coisas diferentes.** Master e região mexem só no agregador (+61% a +166% contra o
   DF/GO), e o agregador responde mais à praça (quando a renda dobra, o agregador sobe ~58% e o balcão ~32%). Prever as
   partes e somar não erra menos que a v2. Erro típico nas 57 unidades: faturamento 25%, balcão 22%, agregador 30%,
   total recombinado 23%.
5. **Quem abre sem agregador fatura bem acima do que o modelo prevê:** +35% a +103%, conforme a medida (sem o RJ,
   ~+30%). Não é só o aluno de app passando a pagar balcão. **Congelado, não adotado:** o juiz são as 5 unidades de 2026
   que abriram sem agregador.
6. **Masters ajudam onde a rede já está e atrapalham em região nova.** Prevendo um metrô inteiro que não viu, a v2 erra
   45%; sem masters, 24–27%. Para estado sem unidade (Manaus, MG), a versão sem masters é mais segura.
7. **O agregador troca ticket por volume.** Mais Wellhub/TotalPass dá +18% de alunos e −10% de ticket, com saldo de
   ≈ +6% no faturamento e um pouco mais de cancelamento. A premissa do simulador (o aluno de agregador rende 60% do
   recorrente) **fica**: a contagem de alunos de agregador do UX não é limpa, e a medição manual dá ~60% (Felipe, 29/09).
   A fatia de agregador se separa por estado (SP ~56%, DF/GO ~32%).
8. **A renda da região pesa no ticket e, na rede madura, no cancelamento.** Praça mais rica paga ~8% a mais e, nas
   maduras de 2025, cancela ~1,3 ponto a menos sobre 7% ao mês. **Não se confirmou nas 17 unidades que amadureceram em
   2026.** Não entra na viabilidade.
9. **A régua dos testes foi trocada.** "Cair 2 pontos nas 39 e no teste" detectava um efeito moderado em só 1–4% das
   vezes. Agora o teste é o tamanho do efeito com faixa, e os 2 pontos são só o portão para levar à aba. Relidos assim,
   o **tier do Wellhub** dá +21% de faturamento por nível (faixa de +7% a +36%), mas as unidades de 2026 abriram sem
   Wellhub: conferir quando ligarem.
10. **O que não fez diferença** (cada um com régua escrita antes): empresas e comércio no entorno (POIs), quantidade e
    qualidade da concorrência, crescimento da cidade, faculdade a até 500 m, frente para avenida, idade da população ao
    redor, experiência do sócio, modalidades além do estúdio, fachada (não se repetiu com avaliador independente), Smart
    Fit vizinha e **preço do plano** (com a tabela do 1º ano, o erro piora nos três modelos; preço 10% maior só dá ticket
    de balcão ~5% maior). A hipótese do diretor apareceu em 2025 e numa rede independente, mas não se distinguiu nas
    unidades novas; com 57 unidades, não é testável.
11. **A geografia já deu o que tinha a dar.** O modelo erra sobretudo o volume de alunos, e nenhuma característica de
    território, concorrência ou preço explica esse erro de forma confiável. O próximo ganho exige **dado novo** sobre o
    ponto, a gestão e a pré-venda. O checklist do ponto (BLK-UNI-17) é a próxima tentativa.
12. **A base de dados tinha erros que afetavam a tela de produção**, achados e corrigidos no caminho (ver etapa 1).
13. **O público é de todas as idades:** a idade mediana dos alunos é 37 anos, e um terço tem 45 ou mais. O "18 a 45"
    nunca foi medido.

---

## Etapa 0 — Base de POIs e teste de "polos de fluxo" (2026-09-25)

**Pergunta:** empresas, escritórios, shoppings e estações perto da unidade aumentam o faturamento?

**O que foi feito:**
- Montada uma base única de 46 milhões de pontos (Receita/CNPJ, IBGE/CNEFE e OpenStreetMap).
- Teste com regras escritas antes de olhar o resultado, na Ultra e replicado na Smart Fit (454 unidades).

**Resultado:** nenhum ganho. Escritórios a pé (ΔR² −0,031) e âncora de fluxo (−0,028) não ajudam; na Smart Fit,
tudo nulo. Uma pista isolada (população a pé na mesma cidade, só na Smart Fit) foi testada depois na Ultra e não
se repetiu.

**Decisão:** POI vira informação descritiva da praça, sem peso em modelo.

Arquivos: `data/analysis/poi/relatorio_teste_poi_2026-09-25.md`, `docs/fontes_bases_poi.md`.

---

## Etapa 1 — Painel da rede (UNI-00, 2026-09-26/28)

**O que é:** uma base única com cada unidade, mês a mês, de abr/2022 a set/2026, e ~240 características por
unidade: tamanho, praça, concorrência, crescimento, planos de agregador, retenção e curva de abertura.
- 98 unidades comparáveis.
- 2.088 meses de faturamento fechado pelo Financeiro.

**Validação:** a curva de abertura reproduz o estudo de inauguração da Growth:
- alunos nos meses 1, 3, 6 e 12: 1.310, 1.775, 2.122 e 2.228;
- estabiliza em ~6 meses.

**Erros de dado achados no caminho (vários já afetavam a produção):**
- **Pinos errados:**
  - Plaza Sul: o pino estava a 1,3 km da academia;
  - Sagrada Família: o pino estava em outra cidade.
  - Ambos corrigidos no painel; na produção, foram passados a outro agente.
- **Guarujá ago/26:** a Visão Executiva mostrava R$ 547,7 mil contra R$ 217,5 mil reais. A cópia do Financeiro na VPS
  foi carregada com a célula ainda em edição; é preciso recarregá-la.
- **São Carlos:** o faturamento não aparecia na Visão Executiva (nome diferente entre sistemas).
- **Filtro de musculação do Wellhub:** perdia 13% das academias.
- **Meses com faturamento zero** com a academia operando: 16 casos.
- **Metragem:** falta para 44 unidades, quase todas as abertas a partir de 2025.

Arquivos: `data/analysis/uni/COBERTURA_UNI00.md`, `DICIONARIO_UNI00.md`; dívidas no backlog (BLK-DADOS-UNI-01).

---

## Etapa 2 — Exploração de hipóteses (UNI-01, 2026-09-28)

**Pergunta:** além de tamanho, renda e população, o que faz uma unidade faturar e reter mais?

**Como foi feito (para dar confiança ao resultado):**
- **Dois tempos.** Só dados até dez/2025 para levantar ideias; jan–ago/2026 fica guardado para confirmar (UNI-02).
  É o que separa achado de coincidência.
- **19 ideias escritas antes de olhar os números**, cada uma com a forma de medir e a régua de "passou". As regras
  foram revisadas por um revisor independente, que achou 7 falhas, corrigidas antes de rodar.
- **Amostra:** 40 unidades maduras (12 meses ou mais de operação em 2025), a maioria em SP e DF. As demais eram novas
  demais.
- **Régua de "passou":**
  - o efeito tem a direção esperada e não é zero;
  - melhora a previsão fora da amostra;
  - se mantém ao retirar qualquer cidade;
  - se repete em dois recortes alternativos.

**Resultados, em três grupos:**

| grupo | o que se achou | certeza |
|---|---|---|
| Prever faturamento de ponto novo | **Hipótese do diretor:** o tamanho rende mais onde a concorrência é de academias pequenas e independentes | fraca — passou por pouco; confirmar |
| | Concorrência (quantidade), crescimento da cidade/bairro, preço frente à concorrência, população a pé | sem efeito grande (amostra pequena não descarta efeito pequeno) |
| Como a renda age | Ticket ~8% maior em praça mais rica | boa |
| | Churn ~1,3 ponto menor em praça mais rica (média 7%/mês); o efeito mais forte do estudo | boa nos dados, mas contradiz a DEC-014 → refazer |
| | Renda **não** muda o % de agregador | — |
| Operação | Mais agregador: +18% alunos, −10% ticket, ≈ +6% faturamento, +0,6 ponto de churn | boa |
| | Alunos no mês 3 definem o nível maduro | forte |
| | Demanda TotalPass na região: +14% de faturamento (fonte só local) | média |

**Descritivos:** % agregador SP 55%, DF 29%, RJ 0%; o tier do Wellhub é mais alto nas praças mais ricas.

**Limites a dizer na apresentação:**
- 40 unidades é pouco: só efeitos grandes aparecem. "Sem efeito" quer dizer "sem efeito grande".
- Planos, concorrência e retenção do Lifetime são fotos de 2026, comparadas com o faturamento de 2025.
- Para confirmar em unidades novas, faltam as metragens: só 12 das 21 unidades que amadurecem em 2026 têm esse dado.

Arquivos: `data/analysis/uni/uni01/protocolo_uni01.md`, `resultado_uni01.md`, `02_posthoc_t09.py`.

---

## Etapa 3 — Curva de rampa observada (UNI-03, 2026-09-28)

**Pergunta:** como uma unidade nova ganha alunos e faturamento no 1º ano, e isso bate com o simulador de viabilidade
(que supõe 500 alunos no mês 1, subindo em linha reta até o mês 8)?

**Como foi feito:**
- Curva montada com 33 unidades abertas até nov/2024 e testada em 22 unidades abertas entre dez/2024 e ago/2025.
  Estas não entraram na curva.
- Regras escritas antes; revisor independente achou 11 falhas, corrigidas antes de rodar.
- Justiça com o simulador:
  - ele foi avaliado com o mesmo tempo de operação (unidades abrem no meio do mês);
  - também foi testada uma versão dele "recalibrada" (mesma reta, com os parâmetros ajustados aos dados).

**Resultados:**

| mês de vida | alunos (% do nível maduro) | faixa normal (p10–p90) | faturamento (% do maduro) | simulador hoje |
|---|---|---|---|---|
| 0 (inauguração) | 80% | 42–102% | – | – |
| 1 | 68% | 50–90% | 52% | 37% |
| 3 | 84% | 68–105% | 75% | 57% |
| 6 | 92% | 83–105% | 85% | 86% |
| 12 | 101% | 96–103% | 102% | 100% |

- **A unidade abre alta, cai no 1º mês e volta a subir.** No mês da inauguração, a pré-venda já dá ~80% do nível
  maduro (quase tudo balcão). No 1º mês completo cai para ~68%, e recupera até o mês 8–10. A queda do mês 1 merece
  conversa com a operação: parece pré-venda que não renova. A confirmar com o export do Lifetime.
- **O faturamento anda mais devagar que os alunos** (52% no mês 1 contra 68% dos alunos): o ticket começa mais baixo.
- **O agregador entra devagar:** 18% dos alunos no mês 1 e 26% no mês 12. O balcão está perto do maduro já no mês 3.
- **Maturidade no mês 12:** do mês 12 ao 24 o nível médio fica estável (101%), mas a dispersão abre. Algumas unidades
  caem e outras crescem.
- **Nas 22 unidades novas, a curva erra metade do simulador:**
  - erro mensal de 10% contra 21% nos alunos, e 12% contra 17% no faturamento;
  - acerta melhor em 21 de 22 unidades;
  - o simulador subestima a soma do 1º ano em 15% dos alunos e 7% do faturamento.
- **O conserto do simulador é simples:** uma reta recalibrada (começar em ~62% do nível maduro e chegar a 100% no
  mês 8) empata com a curva nos alunos. No faturamento, a curva ainda é um pouco melhor.
- **Alerta do mês 3:** a projeção do nível maduro erra ~22% antes de abrir (pela metragem, a regra da viabilidade de
  hoje), ~20% no mês 1, **~5–9% no mês 3** e ~9% no mês 6.
  - Faixa normal do mês 3: o maduro fica entre −20% e +23% da projeção.
  - Na confirmação, a faixa cobriu 77% das unidades, dentro do esperado.

**Impacto na viabilidade (ilustração, unidade típica de 2.213 alunos, premissas-padrão):**

| rampa | payback | faturamento do 1º ano |
|---|---|---|
| hoje (500 → reta até o mês 8) | 38 meses | R$ 2,37 mi |
| curva de faturamento observada | 37 meses | R$ 2,60 mi |
| curva de alunos observada | 36 meses | R$ 2,71 mi |

**Leitura para a diretoria:** o simulador é pessimista no 1º ano. Corrigir a rampa melhora payback e caixa, mas o
ganho é de 1 a 2 meses. O que decide se um ponto é viável continua sendo o nível maduro (etapas UNI-02 e réplica).

Arquivos: `data/analysis/uni/uni03/` (`protocolo_uni03.md`, `resultado_uni03.md`, `curva_uni03.png`,
`ilustracao_payback_uni03.md`).

---

## Etapa 4 — Réplica da hipótese do diretor em outras redes (reforço do UNI-02, 2026-09-28)

**Pergunta:** o padrão achado na Ultra ("o tamanho rende mais onde a concorrência é de academias pequenas e
independentes") aparece em outras redes?

**Como foi feito:**
- Mesmo modelo e mesma medida de concorrência, com regras escritas antes.
- Redes: Engenharia do Corpo (36 unidades em 27 cidades, principal) e Pacer (9 unidades em Ribeirão Preto).
- As duas só informam alunos, então a Ultra também foi medida em alunos, para comparar igual com igual.

**Resultados:**

| rede | medida | efeito* | faixa de confiança | leitura |
|---|---|---|---|---|
| Ultra | faturamento | +0,34 | +0,04 a +0,65 | achado original |
| Ultra | alunos | +0,40 | +0,12 a +0,69 | o efeito aparece também em alunos |
| Engenharia do Corpo | alunos | +0,30 | −0,40 a +1,01 | mesmo tamanho e direção; amostra pequena demais para afirmar |
| EdC + Pacer | alunos | +0,35 | −0,27 a +0,97 | idem |

\* quanto o retorno do m² (elasticidade) aumenta quando a fração de academias independentes em volta sobe um
"degrau típico" (um desvio-padrão).

**Leitura para a diretoria:**
- Numa rede independente, o efeito medido é praticamente do mesmo tamanho que na Ultra, e mantém o sinal em todas as
  27 retiradas de cidade.
- A amostra é pequena demais para "provar"; o resultado era previsto como inconclusivo antes de rodar.
- É evidência a favor da hipótese do diretor, não prova. A prova definitiva virá das unidades Ultra abertas em 2025,
  quando houver a metragem delas.

**Limites:** alunos e não faturamento nas outras redes; sem data de inauguração (maturidade não controlada); redes com
preço e posicionamento diferentes da Ultra.

Arquivos: `data/analysis/uni/uni02r/` (`protocolo_uni02r.md`, `resultado_uni02r.md`).

---

## Etapa 5 — Renda da praça × cancelamento (UNI-04, parte A, 2026-09-28)

**Pergunta:** o achado da etapa 2 (praça mais rica cancela menos) se confirma em unidades que não foram usadas para
achá-lo? E por que ele contradiz a DEC-014, que não viu efeito do território na retenção?

**Como foi feito:** regras escritas antes, revisão independente (10 falhas corrigidas antes de rodar). Quatro olhares:
1. unidades novas, que amadureceram só em 2026 (17), com a idade da unidade controlada — é o teste que decide;
2. as mesmas unidades de 2025, agora em 2026;
3. outra fonte de retenção (Lifetime) e a renda que a DEC-014 usou;
4. o que "explica" o efeito (ticket, agregador, inadimplência).

**Resultados:**

| olhar | efeito no churn mensal (por "degrau típico" de renda) | leitura |
|---|---|---|
| Rede madura 2025 (achado original) | −1,29 ponto (média 7%) | forte |
| … com a idade da unidade controlada (pós-hoc) | −1,15 ponto | não era só idade |
| Mesmas unidades em 2026 | −0,90 ponto | persiste |
| **17 unidades que amadureceram em 2026** | **−0,20 ponto (−1,10 a +0,69)** | **não confirmou** (inconclusivo) |
| Lifetime (churn de 60 dias, 56 unidades, idade controlada) | −0,38 ponto (média 8,1%) | mesma direção, pequeno |

- **Por que difere da DEC-014:** a renda que ela usou é municipal (um valor só para todo o DF). Suspeitei que isso
  explicasse a diferença, mas não se sustentou: no Lifetime, com a idade controlada, a renda municipal e a do bairro
  dão efeitos parecidos e pequenos. A diferença vem mais da medida de cancelamento (o churn mensal da Growth, só
  balcão) e da amostra (só maduras).
- **O que anda junto com a renda:** praças mais ricas têm ticket maior e bem menos alunos "em cobrança" (ρ −0,64).
  Controlando ticket e cobrança, o efeito cai de −1,29 para −0,88. Parte do "cancelar menos" é pagar em dia e ter plano
  mais caro. Isto é decomposição, não prova de causa: a inadimplência é em parte o próprio cancelamento.

**Leitura para a diretoria:**
- Na rede madura, praça mais rica retém melhor, e isso é consistente em duas fontes.
- Não serve para prometer o churn de uma unidade nova: nas que abriram em 2025, não apareceu.
- Não muda a viabilidade agora. Vale acompanhar na operação (UNI-06).

Arquivos: `data/analysis/uni/uni04/` (`protocolo_uni04a.md`, `resultado_uni04a.md`, `02_posthoc_idade.py`).

---

## Etapa 6 — Anatomia dos erros do modelo (2026-09-28)

**Pergunta:** onde o modelo atual (tamanho + renda + população da área de 10 min de carro) mais erra, e o que as
unidades com erro grande têm em comum?

**Como foi feito:** erro de cada uma das 39 unidades maduras de 2025, medido fora da amostra. Em seguida:
- o erro foi separado, de forma exata, em "erro de alunos" e "erro de ticket" (faturamento = alunos × ticket);
- a lista de 22 características a comparar foi fixada antes de olhar.

As conclusões passaram por verificação adversarial de 3 revisores independentes (estatística, explicações
alternativas, qualidade do dado), que **derrubaram a principal leitura inicial** (ver o item 2).

**Resultados:**
1. **O modelo erra sobretudo o número de alunos, não o ticket.** Cerca de 87–92% do erro vem do volume de alunos. O
   modelo explica só ~12% da diferença de alunos entre unidades.
   - "Alunos" inclui os de agregador. Parte desse erro é o mix: unidade com muito agregador tem mais alunos e ticket
     menor.
2. **Não é "efeito São Paulo".** A leitura inicial era "SP fica acima do previsto" (+21%). A verificação mostrou que:
   - o excesso vem de 3 unidades da Baixada Santista (Santos +76%, Praia Grande +62%, Guarujá +46%), mais algumas
     unidades da matriz;
   - na Grande SP o erro mediano é −4%, igual ao do DF (−5%).

   Hipóteses a testar, sem prova:
   - no litoral, o Censo subestima a demanda (população flutuante, área de 10 min cortada pelo mar);
   - a **gestão** pesa: as unidades de SP da matriz ficam +23% acima, e as do outro master de SP, −14%.
3. **O preço do plano Gold não entra no modelo.** É uma foto de ago/2026, depois do resultado, e não acrescenta
   nada. Onde o preço é mais alto há mais alunos que o previsto, mas não dá para saber a direção (o preço pode ter subido
   porque a unidade encheu). Para testar, seria preciso o histórico de preço.
4. **Nenhuma das 22 características explica o erro de faturamento de forma confiável.** Foram 66 comparações;
   esperavam-se ~3 falsos positivos, e as que apareceram são de mix de agregador. O que falta ao modelo não está nas
   bases de hoje: é gestão, qualidade do ponto, visibilidade e fachada. É a mesma conclusão do estudo multirrede de
   25/09.
5. **Caso Lago Sul** (−41%, a maior previsão da amostra): a área de 10 min de carro alcança o Plano Piloto, rico e
   denso, mas o público real é local e rarefeito. É um limite da medida de área, não erro de dado.
6. **Casos extremos sem erro de dado,** exceto Suzano: o nível de 2025 não se sustentou (−42% no faturamento em
   ago/26, com a queda dos agregadores). Brasilândia fica entre as piores com ou sem o vale de receita do fim de 2025.

**Leitura para a diretoria:**
- O modelo de território acerta a ordem de grandeza (erro típico de ~25%). A diferença que sobra entre unidades
  parecidas vem de fatores que as bases não medem: gestão, ponto e fachada.
- Para ganhar precisão, o caminho é **coletar esses dados** (operador e imóvel), não achar mais uma variável
  geográfica.

**Pedidos de dado que saem daqui:**
- identificador do operador/franqueado por unidade (anonimizado basta);
- preço na abertura, ou o histórico de preço;
- tipo de imóvel e fachada da Ultra (já pendentes).

Arquivos: `data/analysis/uni/uni01/03_anatomia_erros.py`, `04_anatomia_regiao.py`, `anatomia_erros.md`,
`anatomia_regiao.md`.

---

## Etapa 7 — Modelo em duas partes e preço (2026-09-28)

**Pergunta:** prever alunos e ticket separadamente, cada um com as suas variáveis, deixa o modelo mais preciso? E o
preço da unidade ajuda?

**Como foi feito:**
- 6 variantes fixadas antes, com a mesma régua ("supera o atual só com +0,02 de R² nas duas avaliações");
- as duas avaliações: fora da amostra e retirando a cidade inteira;
- verificação adversarial por 2 revisores (vazamento de dado e ruído).

**Resultados:**
- **Separar em duas partes, sozinho, piora** (R² fora da amostra 0,30 → 0,27). O ganho que apareceu (variante M3,
  0,30 → 0,33) veio de um termo de "política de agregador do estado", não da separação. Esse termo funciona na
  prática como "SP × DF", o mesmo efeito regional que a anatomia já tinha desmontado.
  - Passou na régua por 0,003, abaixo do nível de ruído que o próprio protocolo declarou.
- **Hipótese do diretor:** não passou fora da amostra (+0,013). O ganho ao "retirar a cidade" (0,19 → 0,31) é
  artefato: na dobra de Brasília, 15 das 16 unidades estão fora da faixa de concorrência vista no treino.
- **Juntar as duas coisas** desanda ao extrapolar para o DF (R² −0,38).
- **Preço:** fica fora do modelo. É foto de ago/2026 e não soma nada (ver etapa 6).
- **Veredito honesto: nenhuma estrutura nova confirmada.** O modelo atual (tamanho + renda + população) segue como
  referência, com erro típico de ~21–25%.
- **Achado de dado útil:** o 0% de agregador do RJ é **real**. As unidades da Grande Rio não aceitam Wellhub nem
  TotalPass (cadastro "NÃO POSSUI", zero na Growth e no Financeiro). Só Cabo Frio e São Gonçalo Shopping aceitam.
  Aceitar ou não agregador é decisão conhecida antes de abrir e mexe em volume e ticket. Mas quase todas as maduras de
  2025 aceitam; só dá para medir o efeito com as unidades do RJ que amadurecem em 2026.

**Leitura para a diretoria:**
- Com os dados de hoje, esgotamos o que a geografia consegue explicar. O modelo simples já captura isso.
- O próximo salto de precisão depende de **dado novo**:
  - metragem das unidades de 2025, para confirmar;
  - operador, preço na abertura, imóvel e fachada, para explicar o que falta.

Arquivos: `data/analysis/uni/uni01/protocolo_duas_partes.md`, `05_duas_partes.py`, `resultado_duas_partes.md`.

---

## Etapa 8 — Metragem por satélite e confirmação do modelo (UNI-02, 2026-09-28)

**Coleta de metragem** (Felipe e Vini, pelo Google Earth/Street View: área do telhado × andares):
- 34 unidades visitadas e 19 medições válidas; 9 unidades novas ganharam metragem.
- **Qualidade**, medida em 9 unidades de metragem conhecida, avaliadas sem saber o valor:
  - a medição superestima ~12%, corrigido dividindo por 1,12;
  - erro típico de 20%, bom o bastante para usar;
  - o maior erro vem de **contar andares**: em Recanto das Emas, a academia ocupa 1 dos 2 andares do prédio.
- **Tipo de imóvel pelo mapa não é confiável:** os dois avaliadores concordaram em 1 de 7 unidades. As categorias
  precisam ser redesenhadas antes de usar.
- **Cotia:** os dois mediram ~1.050 m² contra 750 m² da planilha oficial. Vale conferir a oficial.

**Confirmação do modelo (a prova principal do epic):**
- Modelo ajustado só com dado até dez/2025, previsto para **18 unidades que ele nunca viu** (abertas em 2025, maduras
  em 2026).
- Regras escritas antes de olhar.

| modelo | erro típico | viés | ordena as unidades? |
|---|---|---|---|
| regra atual da viabilidade (só metragem) | 27% | **superestima 17%** | não com segurança (ρ +0,35, IC cruza zero) |
| sem informação (média da rede) | 37% | superestima 19% | — |
| **modelo do estudo (metragem + renda + população)** | **22%** | **+1% (sem viés)** | **sim (ρ +0,50, IC +0,12 a +0,78)** |
| modelo + hipótese do diretor | 20% | +8% | sim (ρ +0,51) |

- **O modelo do estudo se confirmou** pelo critério fixado antes.
- **Ganho que se sustenta em todos os recortes:** não ter viés e ordenar melhor. A regra atual **superestima em
  15–19% o faturamento das unidades novas**, o que faz a viabilidade parecer melhor do que o real, porque ignora que
  as praças novas são mais fracas que as antigas. O erro típico dos dois é parecido quando se usa só a metragem
  oficial (22% × 22%).
- **Hipótese do diretor:** passou na regra por 2 pontos, mas empata nas sensibilidades. Não se distingue com 18
  unidades, como previsto.
- **A faixa de confiança do modelo é estreita demais:** cobriu 67% das unidades, e o esperado era 80%. Na
  viabilidade v2 ela precisa ser mais larga.
- **Maiores erros:** unidades excepcionais.
  - **Botafogo (RJ)** fatura R$ 697 mil/mês com ~4.000 alunos de balcão a ~R$ 175, **sem agregador**. É a maior
    receita da rede, e o modelo previu R$ 245 mil.
  - Laranjeiras (RJ, também sem agregador) já fatura R$ 488 mil no 4º mês.
  - O modelo nunca viu unidade sem agregador. Quando houver mais unidades do RJ maduras, "aceita agregador" deve
    entrar como variável.

**Leitura para a diretoria:**
- O modelo novo não é uma bola de cristal (erra ~22%), mas é **honesto**: acerta a média sem viés e ordena melhor as
  praças.
- A regra atual, na prática, promete ~17% a mais do que as unidades novas entregam.
- Isso justifica levar o modelo para a viabilidade como alternativa ao lado da atual (UNI-05), com faixa mais larga.

Arquivos: `data/analysis/uni/coleta_metragem/` (`qualidade_coleta.md`, `metragem_estimada.csv`) e
`data/analysis/uni/uni02/` (`protocolo_uni02.md`, `resultado_uni02.md`, `confirmacao_por_unidade.csv`).

---

## Etapa 9 — Viabilidade v2 × atual no simulador (UNI-05, 2026-09-28, só análise)

**Pergunta:** se a viabilidade v2 (modelo do estudo + rampa observada + faixa de incerteza) tivesse sido usada para
aprovar as unidades, ela teria acertado mais que a de hoje?

**Como foi feito:**
- As 18 unidades novas do UNI-02 passaram pelo simulador de produção, cada uma em três versões: "real" (com o
  faturamento que a unidade de fato teve), "atual" (como a ferramenta calcula hoje) e "v2".
- Todas com os mesmos custos-padrão (aluguel R$ 20 mil, obra R$ 2,34 mi), porque o custo real de cada unidade não
  estava disponível.
- Regras escritas antes. A verificação adversarial achou um **erro meu**: um ajuste de calendário de −2% valia só para
  a v2. A versão corrigida (v1.1) **inverteu a conclusão**. As duas versões estão guardadas.

**Resultados (versão corrigida):**

| 18 unidades novas | regra atual | v2 |
|---|---|---|
| faturamento: erro típico | 33% | **22%** |
| faturamento: viés | o real ficou **24% abaixo** do previsto | **+1% (sem viés)** |
| payback: erro nas unidades que se pagam em 60 meses | 20 meses | **14 meses** (a v2 erra menos em 6 de 10) |
| decisão "viável" igual à realidade | **72%** | 67% |
| aprovações indevidas / rejeições indevidas | 0 / 5 | 1 / 5 |

- **A v2 prevê melhor o faturamento e o payback,** mas **não acerta mais a decisão de aprovar**. As duas empatam na
  prática: a diferença é 1 unidade (Mococa, exatamente no corte de 36 meses). "Reprovar tudo" acertaria 56%.
- **Pelo critério fixado antes, a v2 não é recomendada para DEC agora.**
- **Por que a decisão não melhora:**
  - Com custo-padrão, "viável" vira "faturar mais de ~R$ 260 mil". Várias unidades ficam coladas no corte, e 2% de
    diferença no nível trocam o resultado.
  - As duas regras deixam de fora as mesmas unidades excepcionais: Botafogo, Butantã, Cariacica e Vila Guanabara.
- **A regra atual achata:** dá quase o mesmo número a todas as unidades (R$ 203–326 mil, contra um real de R$ 114–697
  mil). Promete demais às fracas (~20 meses de payback a menos) e de menos às fortes. Parte do otimismo dela vem de
  uma premissa do simulador: **a receita por aluno de ~R$ 117, contra ~R$ 108 na realidade** (~8% acima).
- **Rampa:** muda o payback em 1–2 meses e só decide quem está no corte. Trocada sozinha, sem a demanda nova,
  aumentaria as aprovações indevidas; tem de ser trocada junto.
- Nas 39 unidades antigas (amostra de desenvolvimento, só apoio), a v2 decide melhor: 72% contra 54%, com 6 contra 10
  aprovações indevidas.

**Leitura para a diretoria:**
- O modelo novo **prevê melhor o faturamento**: sem viés, e confirmado em unidades nunca vistas.
- Ainda **não há prova de que ele melhora a decisão de abrir ou não**. Com 18 unidades e custos-padrão, as duas
  regras empatam.
- Nenhuma das duas encontra as unidades excepcionais.
- Correção que vale já, independente da DEC: rever a premissa de receita por aluno do simulador.

**Decisão do Felipe (29/09):**
- O objetivo é **prever melhor**, e isso a v2 comprovou. Por isso ela vale como base de previsão da viabilidade.
- O critério de "acertar a decisão de aprovar" foi uma checagem do estudo, não a regra de adoção. A decisão de abrir
  depende de muitas outras variáveis e de alavancas que o operador define na mão.
- Não é objetivo achar unidades excepcionais "por sorte".

**Teste 1 — Botafogo com as alavancas do operador declaradas** (mesma demanda prevista pela v2):

| cenário | faturamento previsto | payback | viável? |
|---|---|---|---|
| como estava (69% balcão / 31% agregador, R$ 137) | R$ 245 mil | 40 meses | não |
| **100% recorrente (não aceita agregador)** | R$ 277 mil | 33 meses | **sim** |
| 100% recorrente + preço real do plano (R$ 177) | R$ 354 mil | 24 meses | sim |
| realidade | R$ 697 mil | 12 meses | sim |

- Duas alavancas declaradas pelo operador (sem agregador e preço do plano) levam a previsão 45% para cima e acertam a
  decisão.
- O que falta é **volume**: ~4.100 alunos reais contra ~2.100 previstos. É uma demanda local excepcional.

**Teste 2 — "suprimir" as excepcionais no ajuste do modelo** (regressão robusta, que dá menos peso às unidades fora da
curva sem excluí-las): **não melhora**. O erro vai de 22% para 23–25% e a ordenação piora; as previsões mudam menos de
4%. O modelo já não era puxado por elas.

**Conclusão:** unidade excepcional se trata com **alavancas declaradas pelo operador**, como entradas da v2, e não
abafando dados. O modelo prevê a praça; o operador declara o modelo de negócio:
- aceita agregador?
- preço do plano;
- estúdios e modalidades;
- vagas e comodidade.

**O que falta antes de uma DEC:**
1. rodar com o aluguel e a obra reais de cada unidade;
2. esperar mais unidades amadurecerem (a turma de 2026) e repetir o teste;
3. faixa de incerteza calibrada sem os erros do teste (hoje: −35% a +54% em torno da previsão);
4. na hora de ir para produção, uma DEC Estratégica que emende a DEC-043 e a DEC-009 (usar localização para prever
   demanda).

Arquivos: `data/analysis/uni/uni05/` (`protocolo_uni05.md`, `resultado_uni05.md` na v1.1, `resultado_uni05_v1_0.md`,
`comparacao_por_unidade.csv`).

---

## Etapa 10 — Alavancas do operador (BLK-UNI-05B, 2026-09-29, só análise)

**Pergunta:** a v2 prevê o faturamento da praça. Quanto mudam esse número as decisões que o operador toma antes de
abrir: aceitar agregador, preço do plano, estúdios e modalidades, vagas?

**O que foi feito:**
- Regras escritas e congeladas antes de rodar.
- Um revisor adversarial leu o plano antes da rodada e achou 2 falhas graves e 10 correções, todas feitas. Entre
  elas, dois problemas de dado:
  - o Financeiro só tem a linha de TotalPass a partir de out/2023;
  - Setor Oeste recebia TotalPass 10 meses antes de o Growth contar esses alunos.
- **Agregador:** "experimento natural". O TotalPass entrou em datas diferentes em unidades que já operavam, e cada
  unidade foi comparada com ela mesma antes e depois, contra as outras no mesmo mês.
- **Preço, estúdios, modalidades e vagas:** comparação entre as 39 unidades maduras, com a praça controlada, e
  confirmação nas 18 unidades novas.

**Resultados:**

| alavanca | o que o dado diz | como entra na v2 (proposta) |
|---|---|---|
| receita do aluno de agregador | 47% da do recorrente pela conta Financeiro ÷ UX (R$ 62 × R$ 136; 418 meses de 43 unidades). O simulador supõe 60% | **mantém 60%** (decisão do Felipe: a contagem do UX não é limpa; a medição manual dá ~60%) |
| aceitar / não aceitar agregador | **não mede**: nos eventos limpos o TotalPass trouxe só 1–8% dos alunos, e as unidades já vinham crescendo antes da entrada | aritmética do simulador, com a faixa −25% a +27% |
| **estúdios** | **+30% de faturamento** com a mesma praça (faixa +7% a +59%): +19% de alunos e +9% de ticket. **Não se repetiu** nas 18 novas (erro 21% → 25%), embora ordene melhor as unidades (0,50 → 0,73) | faixa ao lado do número, sem entrar nele |
| preço do plano | unidade com plano mais caro tem **mais** alunos (+11% por R$ 10), e o ticket médio não sobe. É o operador pondo preço alto onde a demanda é forte, não o efeito do preço | aritmética do simulador, com aviso |
| modalidades | cada modalidade a mais sobe o ticket ~5% (+2% a +8%), sem efeito claro no faturamento | aritmética |
| vagas | sem efeito: as vagas andam junto com o tamanho | não entra |

**Decisão do Felipe (29/09): a premissa do agregador fica em 60%.**
- A contagem de alunos de agregador do UX (Growth) não é 100% limpa.
- Medida à mão, com dados direto das unidades, a receita do aluno de agregador chega a ~60% da do recorrente.
- Os 47% saíram de receita do Financeiro dividida pela contagem do UX. Se o UX conta alunos de agregador a mais, a
  razão sai baixa.

**Consequência para leituras anteriores:**
- Toda conta que usa a **contagem** de alunos de agregador carrega essa ressalva:
  - a fatia de agregador por estado (SP 55%, DF 29%);
  - "agregador traz +18% de alunos";
  - a receita por aluno de ~R$ 108 da etapa 9.
- A diferença "simulador R$ 117 × real R$ 108" pode ser, em parte, efeito dessa contagem, e não otimismo do simulador.
- **O modelo de faturamento (v2) não é afetado:** ele prevê o faturamento do Financeiro direto.

**O que isso quer dizer:**
- **"Sem agregador" continua sem número medido.** Depende de quantos alunos de agregador virariam recorrentes.
  - Com a receita real por aluno: nenhum → a unidade fatura **25% menos**; todos → **27% mais**.
  - Em Botafogo, o que falta à previsão é volume, não o modelo de negócio.
  - **Como medir de verdade:** o RJ começou a aceitar Wellhub em algumas unidades em set/2026. Em ~6 meses, é o
    primeiro experimento "não aceitava → passou a aceitar".
- **O estúdio pode estar medindo o operador.**
  - Nas 18 unidades novas, as da matriz não têm estúdio e as do DF/GO têm.
  - Para separar o efeito do estúdio do efeito do operador, falta o teste do operador/franqueado (pendente).
- **Preço não se mede comparando unidades.** É preciso ver a mesma unidade mudando de preço ao longo do tempo. O
  histórico de vendas da API Growth tem isso (valor e data de cada venda).

**Aprofundamento dos estúdios (mesmo dia, pós-hoc e declarado):** estúdio × master. A master é uma sigla regional do
Growth, substituto parcial do operador.
- **O efeito dos estúdios sobrevive à master:** +28% com a master controlada (faixa +4% a +58%), contra +30% sem
  ela. Retém 93% do efeito e é estável ao retirar cada metro.
- **A master sozinha não prevê:** nas 18 unidades novas, o erro vai de 21% para 30%.
- **Master + estúdios juntos prevêem melhor que o modelo base:** erro 20,6% × 21,5% e ordenação 0,73 × 0,50.
  - Na amostra antiga, as unidades da matriz sem estúdio faturam muito acima do previsto (+49%).
  - Nas unidades novas, as da matriz estão todas sem estúdio.
  - Por isso estúdio sozinho errava, e junto com a master acerta.
- **Leitura:** é o sinal mais promissor entre as alavancas. Só não entra na v2 antes de se repetir em unidades novas,
  porque o teste foi feito depois de ver o dado. Caminho: congelar agora a previsão da turma de 2026 com e sem
  estúdios, e conferir quando ela amadurecer.

**Master real do cadastro no lugar da sigla regional (pedido do Felipe, mesmo dia):**
- A master vem do cadastro da VPS, anonimizada de M1 a M7, e é ligada pelo código da unidade.
- A verificação independente achou um erro de chave meu ("6" × "06"). Corrigido, os números não mudaram.
- **Estúdio é só sim/não** no sistema: sem quantidade de salas.
- **A master real sozinha não prevê:** o erro vai de 21,5% para 31,0%.
- **Estúdios + master real:** erro de 22,1%, igual ao da praça dentro do ruído (IC −9 a +5 pontos), e ordenação de
  0,69 contra 0,50.
- **O ganho de ordenação é dos estúdios.** A master só acerta o nível: sem ela, o modelo com estúdios erra 25%, porque
  as unidades da matriz sem estúdio vão muito bem.
- **O que é firme:** estúdio separa quem fatura acima do previsto. Fora da amostra, as unidades com estúdio ficam
  +54% contra −21% das sem estúdio (72 de 80 pares; 11 de 11 dentro da mesma master). O **tamanho** do efeito
  (+26% a +30%) é incerto.
- **Cuidado:** o estúdio é o retrato de ago/2026 contra o desfecho de 2025. Unidade que vai bem pode ter aberto
  estúdio depois.
- As diferenças de erro entre as versões (20,6%, 21,5%, 22,1%, 25,0%) são todas ruído com 18 unidades.

**Decisão do Felipe (29/09):**
- **adota como v2 de trabalho: praça + estúdios + master real;**
- sem rótulo de "não confirmada" por ora;
- vai apresentar ao diretor antes.
- A conferência na turma de 2026 continua congelada nas duas versões.

**Grau de certeza:**
- Premissa do agregador: a conta com o UX dá 47%, e a medição manual das unidades, ~60%. Vale a manual.
- **Média-baixa** para os estúdios: passou na amostra antiga, não se repetiu na nova.
- **Nenhuma** para agregador sim/não e preço: o dado de hoje não mede.

Arquivos: `data/analysis/uni/alavancas/`:
- `protocolo_alavancas.md`, com a revisão antes de rodar no §10;
- `resultado_alavancas.md`;
- `eventos_agregador.csv`, `saidas_agregador.csv`, `alavancas_corte.csv`, `confirmacao_alavancas.csv`;
- `REGISTRO_CONGELAMENTO.txt`.

---

## Etapa 11 — Base recorrente × agregador: o que explica a proporção (BLK-UNI-05C, 2026-09-29, só análise)

**Pergunta (sugestão do Felipe):** alguma característica da praça explica a **proporção de alunos ativos** que vêm
de agregador (Wellhub/TotalPass) contra os recorrentes? Se sim, a v2 pode ajustar o mix por praça em vez de usar o
padrão.

**O que foi feito:**
- **Desfecho:** a fatia de agregadores nos alunos ativos (contagem do UX, com a ressalva de que a contagem de
  agregadores não é 100% limpa).
  - A 1ª rodada usou a fatia na receita (Financeiro); depois o Felipe esclareceu que a pergunta é o **volume**.
  - As duas medidas ordenam as unidades quase igual (+0,96), e as conclusões coincidem.
- **Amostras:** 37 unidades maduras em 2025 que aceitam os dois agregadores; confirmação em 13 unidades novas,
  maduras em 2026.
- Regras escritas antes e revisadas por um revisor adversarial, que pegou um erro de desenho: aceitar um ou os dois
  agregadores é política e mexe na proporção.

**Resultados:**
- **Numa unidade típica, 41% dos alunos ativos são de agregador** (de 22% a 61%).
  - **SP ~53% contra DF ~27%**: a maior diferença é entre estados.
  - Na receita, isso vira 37% × 15%.
- **Renda e população não explicam** a proporção.
- **Na amostra de 2025**, quatro variáveis explicam bastante. Quase todas medem "mercado acostumado a agregador":
  - escritórios a pé (+8 p.f. por desvio-padrão);
  - demanda de TotalPass por perto (+11 p.f.);
  - academias independentes no agregador (+21 p.f.);
  - preço do plano Gold (+8 p.f.).
- **Nas 13 unidades novas, nenhuma se confirmou.**
  - A mais perto foi **escritórios a pé**: o erro caiu de 7,2 para 5,9 p.f. e a ordenação ficou igual ou melhor, mas
    com 13 unidades ainda cabe no acaso.
  - A mais forte em 2025, **independentes no agregador**, **errou o dobro** nas novas (7 → 14 p.f.). Era ajuste à
    amostra.

**O que isso quer dizer:**
- A proporção de agregador é sobretudo **uma questão de estado e de mercado corporativo**: praça de escritório em SP
  puxa agregador.
- Com o padrão da rede, a proporção de uma praça nova sai com erro de ~7 p.f. "Escritórios a pé" é o único candidato
  conhecido antes de abrir, e ainda não se confirmou.
- **Para a v2:** manter o mix padrão. "Escritórios a pé" fica como candidato a confirmar com a turma de 2026.

**Confirmação ampliada (pedido do Felipe, mesmo dia):** a confirmação foi estendida a 19 unidades, incluindo as de 6
meses de vida em diante. Regra escrita antes, com o erro medido depois de corrigir o nível: a proporção das unidades
jovens ainda está subindo.
- **Nenhuma das 4 candidatas se confirmou.**
- **Escritórios a pé:** o efeito não se distingue de zero. É a que mais reduz o erro bruto (10,7 → 9,0 pontos; com as
  unidades de 9+ meses, 10,1 → 7,8), mas o IC cobre zero em todos os cortes.
- **Independentes no agregador:** o erro piora de forma clara nas unidades novas. A causa pode ser ajuste à amostra
  ou uma variável que não se transfere entre praças.
- **Ressalva da verificação:** 13 das 19 unidades já estavam na 1ª confirmação. Esta não é uma prova independente; só
  ~6 unidades são de fato novas.

**Estado/regional (exploratório, fora do protocolo):**
- A proporção **se separa por estado**: SP ~53% e DF/GO ~28% em 2025; nas unidades da confirmação, 63% × 34%.
- Uma regra só por estado (SP 53%, DF/GO 28%, outros 45%):
  - **ordena melhor** as unidades novas: 0,73 contra 0,64;
  - **erra menos no nível bruto:** 8,5 contra 10,6 pontos;
  - no erro com o nível corrigido, porém, o ganho é pequeno (0,4 ponto) e não foi testado.
- Três cuidados apontados pela verificação:
  - o agrupamento foi escolhido depois de ver dados que já incluíam parte dessas unidades;
  - DF/GO é praticamente uma regional só, então pode ser **política comercial** e não mercado;
  - o grupo "outros" já falhou (55% → 42%).
- A leitura correta é "**se separa** por estado/regional", não "o estado explica".
- **RJ:** a política é de unidade/capital, não de estado. Cabo Frio aceita os dois agregadores e tem 61%; a Grande Rio
  não aceitava até set/2026.

**Universo inteiro, com validação cruzada (pedido do Felipe, mesmo dia):**
- **O que mudou:**
  - entram também as unidades que aceitam só um agregador. O Felipe avaliou que a política pesa pouco, e o dado
    confirma;
  - são 64 unidades, cada uma prevista por um modelo que não a viu, e também deixando uma metrópole inteira de fora;
  - "escritórios privados" = escritórios sem administração pública e hospitais, pelo mecanismo "benefício de empresa".
- **Regra por estado** (SP / DF-GO / outros):
  - o erro da proporção cai de 12,7 para 9,8 pontos (−23%);
  - com a metrópole de fora, cai de 14,3 para 9,5;
  - SP tem **~23 pontos a mais** de agregador que DF/GO. Medianas: SP 56%, DF/GO 32%, outros 43%.
- **Escritórios (normal ou privados):** ~1 ponto de ganho dentro das regiões conhecidas, e nada em metrópole nova.
  Somado ao estado, **piora** a transferência (9,5 → 10,4). Fica fora. A versão privada é praticamente igual à normal
  (0,99), porque conta estabelecimentos e não trabalhadores. O teste certo do mecanismo usaria o emprego formal
  privado (CAGED/RAIS).
- **Verificação independente (3 lentes, só leitura):**
  - achou 1 bug meu: 2 unidades com o polígono de pino antigo. Foi corrigido e o resultado não mudou;
  - **o fato firme é SP acima de DF/GO**, que aparece na contagem do UX, na receita do Financeiro e nas unidades
    novas.
- **Cuidados antes de usar a regra:**
  - o agrupamento foi escolhido vendo estes dados;
  - DF/GO é praticamente uma regional só (Brasília): mercado e política comercial não se separam;
  - "outros" mistura RJ (~61%) com MT (~34%), então para estado novo (RJ, MG: a expansão) a regra acerta pouco;
  - os IC saem otimistas.
- **O que o mix muda na v2:** a v2 prevê o faturamento direto, então o mix **não muda o faturamento nem o payback**.
  Muda a divisão dos alunos (quantos de agregador) e, com isso, o planejamento de Wellhub/TotalPass. O erro no número
  de alunos de agregador cai de ~±30% para ~±23% em SP e DF/GO.
- **Nível:** a contagem do UX dá 42% de agregador; o simulador usa 31% (a premissa de 60% implica que o UX conta a
  mais). Se entrar, a regra deve ser aplicada como **diferença** em torno do padrão do simulador, e não com os níveis
  do UX.

**Grau de certeza:**
- **Alto** para "renda não explica" e para SP acima de DF/GO.
- **Médio** para a regra por estado prever melhor em SP e DF/GO.
- **Baixo** para estado novo.
- **Nulo** para escritórios.

Arquivos: `data/analysis/uni/mix/`:
- `protocolo_mix.md`, com a revisão no §8 e a v1.1 no §9;
- `resultado_mix_alunos.md` (principal) e `resultado_mix_receita.md`;
- `resultado_confirmacao_ampliada.md` (v1.2);
- `resultado_universo_cv.md` (v1.3.1; v1.3.0 com o bug preservada);
- `poi/05c_f1_privado.py` (escritórios privados).

A verificação independente foi feita por 3 lentes, só de leitura.

---

## Etapa 12 — Quanto cada ajuste melhora de verdade o modelo de viabilidade (2026-09-29, exploratório)

**Pergunta do Felipe:** somando tudo (praça, rampa, alavancas do operador, mix, estado, escritórios, estúdios), quanto
melhora o modelo final? A régua é sempre a mesma: as **18 unidades que o modelo nunca viu** (abertas em 2025, maduras
em 2026).

| o que muda | faturamento: erro típico | ordenação | leitura |
|---|---|---|---|
| **regra atual (só metragem)** | 27% (superestima ~17%) | 0,35 | ponto de partida |
| **v2: demanda da praça (m², renda, população)** | **21,5%**, sem viés | **0,50** | **o ganho real e confirmado** |
| + estado | 24,9% | 0,36 | piora |
| + escritórios a pé | 24,8% | 0,51 | piora o erro |
| + estado + escritórios | 26,0% | 0,35 | piora |
| + estúdios | 25,0% | 0,73 | ordena melhor, erra mais o valor |
| + estúdios + master | 20,6% | 0,73 | melhor de todos, mas pós-hoc (a confirmar na turma de 2026) |
| + preço declarado (aritmética) | 24,3%, sem viés | 0,67 | ordena melhor, erra mais o valor |
| + agregador declarado | 21,5% | 0,56 | só muda Botafogo (245 → 277 mil; real 697 mil) |
| + preço + agregador | 24,3% | 0,68 | idem |

**Nos alunos (volume), a mesma coisa:** o modelo da praça erra 16%; somar estado e escritórios leva a 19–21%. **Estado
e escritórios mudam a divisão dos alunos (agregador × recorrente), não o total.**

**Rampa (etapa 3):** corrige o 1º ano (~7% do faturamento, 1–2 meses de payback), sem mudar o nível maduro.

**Mix do agregador:**
- **Renda + escritórios + estado juntos**, na proporção agregador × recorrente: o erro cai de 12,7 para 9,6 pontos (universo de 64, validação LOO). Quase tudo vem do estado: só ele dá 9,8. Renda não soma. Escritórios soma 0,2 dentro das regiões conhecidas e piora em metrópole nova (9,5 → 10,4).
- A regra híbrida (SP e DF/GO pelo modelo, "outros" no padrão) erra o mesmo que a regra completa por estado: 9,8
  pontos.
- Fixar "outros" no padrão não custa nada.
- O mix não muda o faturamento nem o payback da v2.

**Conclusões:**
1. **O ganho do estudo está na demanda da praça:**
   - o erro de faturamento cai de 27% para 22%;
   - o viés de +17% some;
   - o erro do payback cai de 20 para 14 meses.
2. **As alavancas do operador, aplicadas como conta**, ajudam a **ordenar** as unidades (0,50 → 0,68), mas **erram o
   tamanho**. A conta supõe os mesmos alunos com o preço novo, e na realidade o volume reage. Servem para o operador
   simular cenários, não para melhorar o número central.
3. **O erro que sobra (~22%) é quase todo volume**, e nenhuma variável de praça que temos o explica. Os candidatos
   estão fora do dado de hoje:
   - operador/gestão (estudo paralelo de ICP do franqueado);
   - ponto e fachada;
   - demanda local excepcional (Botafogo).

Arquivo: `alavancas/03_quanto_melhora.py` → `resultado_quanto_melhora.md` (exploratório).

**Fachada (mesmo dia, teste com critério escrito antes):**
- É a nota de 1 a 5 e os 6 itens avaliados por Felipe e Vini na coleta.
- Nas 4 unidades avaliadas pelos dois, as notas batem (2/2, 3/3, 1/1, 2,5/3).
- **Direção a favor, sem prova:** cada ponto de nota vale ~**+8%** de faturamento acima do previsto (Spearman +0,37),
  mas com só 14 unidades o IC vai de −0,20 a +0,86.
- A maior exceção é Botafogo: nota 2 e +185%.
- A fachada foi registrada na conferência congelada da turma de 2026 (13 das 16 unidades).
- **Para testar já:** avaliar a fachada das ~40 unidades maduras que ficaram de fora (Street View; nota + 6 itens).
  Isso leva o teste de 14 para ~50 unidades.

- **Amostra ampliada** (v1.1: + unidades jovens projetadas pela curva do mês 6–12 + 2 de shopping), 22 unidades:
  Spearman +0,32 [−0,09; +0,66], **+10% de faturamento por ponto de nota**. O IC ainda encosta em zero.
- **Por nota:**
  - nota 3: −16% contra o previsto (8 unidades);
  - nota 4: +13% (8);
  - nota 5: +39% (4).
- **Sem Botafogo** (nota 2 e +185%, a demanda excepcional): Spearman +0,50.
- **Sem Botafogo só no teste de fachada (decisão do Felipe: "fachada ridícula, o maior outlier da rede"):**
  - maduras: +0,67 [+0,27; +0,91], **~+23% de faturamento por ponto de nota**;
  - ampliada: +0,49 [+0,15; +0,76], ~+21% por ponto.
  - A exclusão foi decidida depois de ver o dado; as duas versões ficam registradas.
- **Confirmação limpa em andamento:** o Juan avalia 45 unidades que ninguém tinha avaliado, com 6 de controle
  misturadas sem aviso. A regra do teste foi escrita antes de ele preencher.
- **Leitura:** é o sinal mais coerente depois dos estúdios, com escada limpa de 3 → 4 → 5.
- **1ª leitura parcial da confirmação (Juan, 29/09, 14 notas):**
  - 11 unidades novas e 3 de controle. Concordância com Felipe/Vini: 2 iguais e 1 com 2 pontos de diferença (Boa
    Vista).
  - **Nas 11 novas, a fachada não se confirmou:** Spearman −0,25 [−0,64; +0,26].
  - Com todas as notas (32, sem Botafogo): +0,22 [−0,07; +0,48], ~+10% por ponto.
  - Unidades com nota 2 que faturam acima do previsto (Botanic Mall, Noroeste, Mooca) puxam contra. Pode ser que
    fachada em shopping ou galeria não se compare com loja de rua. É hipótese, não testada.
  - **O sinal enfraqueceu com o primeiro dado independente.** O veredito sai com as 45.
  - **"E se tirar as unidades extremas?" (pergunta do Felipe, 30/09):**
    - tirar as que contrariam (nota 2 faturando acima) daria +0,41. Isso é escolher a dedo e não vale;
    - com regras que não olham a nota, não se sustenta:
      - corte simétrico dos 10% mais extremos: +0,16;
      - só lojas de rua (fora de shopping), sem Botafogo: **+0,30** [−0,03; +0,64], a mais perto de se sustentar.
    - A hipótese "loja de rua" veio da análise, não do Felipe. Foi escrita antes das ~34 notas que faltam e é o teste
      principal quando o Juan terminar.
  - **Fachada dentro da v2 (30/09, exploratório, 24 unidades com nota, sem Botafogo):** não melhora a previsão.
    - v2 sozinha: 21,8%;
    - v2 + correção de nível: 17,5%;
    - v2 + fachada: **18,9%**, pior que só o nível;
    - ordenação: 0,58 → 0,52;
    - efeito: +6% por ponto, sem significância.
    - **Por ora, a fachada não entra na v2.** O veredito sai com as notas restantes do Juan (`alavancas/09_v2_fachada.py`).
 Com mais ~30–40 avaliações
  das unidades maduras, ele se decide.
Arquivos: `alavancas/protocolo_fachada.md`, `04_fachada.py`, `resultado_fachada.md`., `05_fachada_ampliada.py`, `resultado_fachada_ampliada.md`.

---

## Etapa 13 — Quanto o modelo pode errar e faixas de segurança (BLK-UNI-07, 2026-09-30)

**Pergunta:** quando a v2 prevê o faturamento de um ponto novo, quanto ela pode errar, e o que isso significa para a
decisão?

**O que foi feito:**
- regras escritas antes;
- revisão adversarial antes de rodar (11 correções) e verificação independente depois (2 lentes);
- erro medido em unidades que o modelo não viu: as 39 de 2025 deixando cada uma de fora, e as 18 novas de 2026.

**Resultados:**
- **Erro típico da v2: ~23%** (desvio-padrão de 0,37 em log). É o mesmo do modelo só de praça (~22%). A v2 **não
  aumenta a precisão**; o ganho dela é ordenar melhor as unidades.
- **Faixa de segurança de 80%: de −37% a +58%** em torno da previsão. Nas 18 novas, cobriu 13 (72%) e foi adotada
  **provisoriamente**, porque passou por uma unidade só.
  - O **piso segurou**: só 1 de 18 ficou abaixo (Mococa).
  - O **teto não**: 4 ficaram acima (Noroeste, Butantã, Cariacica e Botafogo), todas com estúdio.
- **Faixa de 50%:** coberta de fato (~50%). A primeira leitura de "estreita" foi retirada: duas unidades ficaram fora
  por menos de 0,1 ponto.
- **O erro é maior em SP do que no DF/GO:** 32% contra 17%, e não é efeito de 2 ou 3 unidades. Pela regra, isso abre a
  opção de faixa por estado, que é decisão do Felipe. Se adotada, seria um fator de escala, e não quantis próprios (SP
  teria só ~2 unidades por ponta).
- **Unidade típica (custos-padrão):**

  | | faturamento maduro | payback (meses) | margem (central) | chance de ser viável |
  |---|---|---|---|---|
  | sem estúdio | R$ 144 mil · 215 mil · 358 mil | >60 · 50 · 24 | 36% | 38% |
  | com estúdio (+R$ 6 mil/mês) | mesmo faturamento | >60 · 55 · 25 | 33% | 26% |

  A chance de ~38% equivale à chance de faturar ≥ ~R$ 260 mil/mês maduro, porque quem decide é o payback ≤ 36.
- **A "chance de ser viável" ordena bem** (Brier 0,175 contra 0,238 da taxa-base; AUC ~0,83), mas **não serve como
  corte**: com corte em 50%, reprovaria 5 das 7 unidades que seriam viáveis. Serve para **comparar pontos**.
- **Achado registrado (pedido do Felipe, 30/09): a v2 provavelmente SUBESTIMA unidades com estúdio.** Pós-hoc, a confirmar:
  - nas 18 novas, as com estúdio faturaram **acima** do previsto (7 de 8; mediana +55%) e as sem estúdio, **abaixo**
    (8 de 10; −21%);
  - no treino (2025) isso não acontece;
  - confundido com a matriz: 6 das 10 sem estúdio são da matriz. Pode ser que o estúdio valha mais nas unidades novas,
    ou que as unidades novas da matriz não repitam as antigas.
- **Depois de abrir:** o mês 3 dá uma referência sobre o volume de alunos com metade da largura (−20% a +23%). É outra
  grandeza (alunos, não faturamento).

**Cuidados:**
- folha de 17%: é a premissa válida. A folha de 25–26% das DREs estava inflada (decisão do Felipe, 30/09);
- a chance é da praça com custo típico, não da unidade real;
- faixa provisória até a conferência da turma de 2026.

**Decisões do Felipe pendentes:**
1. faixa única ou fator por estado (SP mais larga);
2. apresentar a chance de viabilidade como ranking, e não como corte.

Arquivos: `data/analysis/uni/uni07/`:
- `protocolo_uni07.md`, `resultado_uni07.md`;
- `erros_fora_da_amostra.csv`, `faixas_indicadores.csv`.

---

## Simulação pontual — Manaus, pino NOVA CIDADE (2026-09-30)

**Cenário do Felipe:**
- unidade com estúdio, 2.000 m²;
- aluguel R$ 80 mil, obra R$ 2,5 mi;
- equipamentos R$ 1,5 mi em 60× a 2% a.m.;
- plano cheio R$ 167.

**Praça (10 min de carro):** ~525 mil habitantes (acima da mediana da rede, 341 mil) e renda per capita de ~R$ 1.070
(bem abaixo da mediana, R$ 1.950).
- Foi aproximada por um círculo de área equivalente, porque o `osmium` não está no ambiente que funciona.
- Calibração: nas 39 de treino, o círculo muda a previsão em +3% na mediana (erro típico de 6%).

**v2:**
- faturamento maduro de **~R$ 247 mil/mês** (faixa de 80%: R$ 156–389 mil), com master desconhecida;
- como M1 ou M3, ~R$ 216 mil; como M2, ~R$ 269 mil.

**Viabilidade:** **não viável no cenário central**:
- margem de 10% (R$ 137) e 19% (R$ 167);
- payback acima de 60 meses;
- chance de viabilidade de 5%.

**Por quê:**
- o aluguel de R$ 80 mil é ~1/3 do faturamento previsto;
- **mesmo com aluguel zero**, o payback central fica em 46 meses (R$ 167), por causa dos R$ 4 mi de investimento;
- para ser viável, a demanda teria de ser ~R$ 416 mil/mês (~3.600 alunos), 68% acima da previsão central.

**Cuidados:**
- o R$ 167 é conta (mesma demanda, com o efeito do preço no volume não medido), numa praça de renda baixa;
- Manaus fica fora dos estados da amostra, embora renda e população estejam dentro da faixa da rede.

**Os 2.000 alunos (pergunta do Felipe) e a expectativa do diretor (~R$ 400 mil/mês):**
- **Unidades parecidas na rede:**
  - praças de renda baixa com estúdio: 2.100 a 3.600 alunos, com R$ 270–350 mil;
  - unidades de 1.700 m² ou mais: mediana de 3.034 alunos.
- **Os ~2.000 alunos da v2 são provavelmente conservadores.** É o achado de que a v2 subestima unidades com
  estúdio (etapa 13). Uma faixa realista é ~2.000–3.200 alunos, com centro perto de 2.600.
- **R$ 400 mil com plano a R$ 167 = ~2.840 alunos.** É plausível pela rede, mas otimista.
  - Pela faixa da v2, a chance é de ~8%. Com a correção pós-hoc do estúdio, que é só ilustrativa, ~40%.
  - Risco: R$ 167 é preço de topo numa praça de renda baixa. As unidades de renda baixa cobram R$ 117–137, e a reação
    do volume ao preço não foi medida.
  - Vagas (80) não mostraram efeito no faturamento (etapa 10).
- **Mesmo com R$ 400 mil/mês, com aluguel de R$ 80 mil e R$ 4 mi de investimento, não se paga em 36 meses:**
  - margem de 32%, payback acima de 60 meses;
  - com aluguel de R$ 40 mil, o payback vai a 39 meses;
  - com obra de R$ 1,5 mi, a 53 meses.
- **Para ser viável com os custos informados:** ~R$ 503 mil/mês (~3.580 alunos), acima de qualquer unidade de renda
  baixa da rede.
- **Payback de 36 meses é régua, não corte** (Felipe, 30/09). Reportar o payback em meses, sem "se paga / não se
  paga".
- **Por que a previsão ficou "baixa" (diagnóstico exploratório):**
  - **O modelo já põe Manaus acima da média:** R$ 247 mil contra ~R$ 215 mil da unidade típica (+15%).
  - Contribuições contra a típica:
    - metragem +17%;
    - estúdio +10%;
    - master desconhecida +12%;
    - renda −16%;
    - população −4%: mais gente na praça não soma no modelo depois que a master entra.
  - **Renda domiciliar (padrão do produto) no lugar da per capita:** o modelo acerta igual (erro 22,1%, ordenação 0,69)
    e Manaus sobe para R$ 261 mil. Manaus tem 3,27 moradores por domicílio, o maior da rede (mediana 2,66). A per
    capita penaliza um pouco, mas não é o motivo principal.
  - **R$ 400 mil é top 3 da rede**, ao lado de Botafogo, Noroeste e Butantã. Essas unidades faturam 59% a 185% acima
    do que a praça prevê: é a demanda excepcional que as variáveis de praça não enxergam.
  - **A conta que concilia com o diretor:** v2 R$ 247 mil × o desvio do estúdio visto nas unidades novas (+55%) ≈
    R$ 380 mil, e com o plano a R$ 167 (conta, mesma demanda) passa de R$ 400 mil. O número dele equivale a supor
    que o estúdio rende o que rendeu na turma de 2025 **e** que o preço de topo se sustenta numa praça de renda
    baixa.
- **Decisão do Felipe (30/09): a v2 passa a usar renda DOMICILIAR** (padrão do produto) no lugar da per capita.
  - Acerto igual: erro 22,1%, ordenação 0,69.
  - Previsões da turma de 2026 congeladas também nessa versão (`previsao_2026/previsoes_turma_2026_v2_domiciliar.csv`).
- **O "+55%" não é "o estúdio sozinho":** é quanto as 8 unidades novas com estúdio superaram a previsão, e não o efeito
  causal do estúdio.
  - O efeito medido com a praça e a master controladas é +23–26%.
  - O estúdio marca o **formato completo**: mais investimento, mais modalidades, ticket +9% e alunos +19%.
- **Base empírica para R$ 300–350 mil (comparáveis):** as 7 unidades da rede em praça de renda baixa **com estúdio**
  faturam R$ 272–349 mil (mediana R$ 329 mil, ~2.650 alunos). As sem estúdio na mesma faixa de renda: mediana R$ 136
  mil.
  - **Hipótese para testar (BLK-UNI-08):** em praça de renda baixa, o estúdio vale mais. A concorrência ali é de
    academias menores, sem estrutura, e a unidade completa vira a líder da categoria. Liga-se à hipótese do diretor
    (T09: tamanho × concorrência de estrutura menor).
- **Payback com os custos informados** (aluguel R$ 80 mil, R$ 4 mi de investimento): acima de 60 meses de R$ 260 mil a
  R$ 400 mil/mês. A margem vai de 15% a 32%.
- **Por que o payback passa de 60 meses mesmo a R$ 400 mil (conferido no fluxo mês a mês; a conta está certa):**
  - EBITDA de R$ 127 mil (32%);
  - − IR/CSLL de R$ 41,5 mil (lucro presumido, ~10% da receita);
  - − parcela do equipamento de R$ 43 mil (R$ 1,5 mi a 2% a.m. = R$ 1,09 mi de juros em 60 meses);
  - = sobram ~R$ 43 mil/mês para recuperar ~R$ 3,0 mi: obra de R$ 2,5 mi + franquia de R$ 160 mil + 4 meses de aluguel
    antes de abrir.
  - Alavancas:
    - equipamento a 1% a.m.: 60 meses;
    - sem juros: 54;
    - aluguel de R$ 50 mil: 44;
    - aluguel de R$ 50 mil + equipamento a 1%: **39 meses**;
    - obra de R$ 2,0 mi + aluguel de R$ 60 mil + equipamento a 1%: 39.
- **Master de Manaus:** a mesma que cuida de RJ/SP (grupo M3 no estudo). Com ela, a v2 dá ~R$ 230 mil, porque o
  coeficiente da M3 é ~0 e o de "outras" é +15%.
- **Leitura:** o que decide é custo × demanda. O ponto pode ser o melhor da região e, ainda assim, não pagar aluguel de
  R$ 80 mil mais R$ 4 mi de investimento em 3 anos.

Arquivos: `simulacoes/manaus_nova_cidade.py`, `resultado_manaus_nova_cidade.md`.

### Premissas corrigidas e plano de estúdio (30/09, exploratório)

- **Premissas corrigidas pelo Felipe:**
  - obra de R$ 2,3 mi;
  - **taxa de franquia zero**;
  - 100 vagas e terreno de 4.000 m² (nenhum dos dois entra no modelo);
  - 1 estúdio;
  - aluguel de R$ 80 mil, equipamentos em 60× a 2% a.m. e plano de R$ 167, sem mudança.
- **Feeling do diretor:** 5% da base em plano de estúdio, mais caro. O preço não foi informado, então foi testada uma
  sensibilidade de R$ 197 a R$ 347.
- **Efeito das correções:** o payback, na demanda do diretor (~2.840 alunos, R$ 400 mil), cai de 66 para **63 meses**.
- **Plano de estúdio:** cada R$ 50 a mais no preço tira ~2–3 meses. A R$ 297, o payback fica em **55 meses**, porque o
  plano soma só ~R$ 17 mil/mês (4%). Para chegar a 36 meses só com o plano, ele teria que custar ~R$ 800.
- **O que fecha a conta é custo:**
  - aluguel de R$ 60 mil + equipamento a 1% a.m. + plano de R$ 297: 37 meses;
  - aluguel de R$ 50 mil + equipamento a 1%: 36 meses sem o plano e 33 com ele.
- **Na demanda da v2** (master de RJ/SP, ~1.960 alunos), a unidade não se paga em 120 meses, com ou sem plano.
- **Comparáveis de renda baixa com estúdio:** ~2.820 alunos, praticamente a mesma demanda do número do diretor.

Arquivos: `simulacoes/manaus_premissas_corrigidas.py`, `resultado_manaus_premissas_corrigidas.md`.

**Faturamento e financiamento (30/09, exploratório).** O plano de estúdio foi posto em 5% da base a R$ 272, o meio da
faixa testada, só como referência.

- **Faturamento maduro com os fatores do operador:**
  - v2: R$ 288 mil;
  - comparáveis: R$ 412 mil;
  - diretor: R$ 414 mil.
  - No mês 1, com a rampa observada de 64%: R$ 192, 274 e 275 mil.
  - O plano de estúdio soma ~R$ 10–14 mil/mês. O resto da diferença para os R$ 230 mil da v2 é o preço de R$ 167,
    supondo o mesmo número de alunos.
- **Juros e prazo do equipamento** (payback na demanda do diretor, com o plano):
  - 2% em 60×: 57 meses;
  - 1,8% em 60×: 55;
  - 1,8% em 96×: 49;
  - 1% em 120×: 42.
  - Alongar o prazo encurta o payback, mas encarece a dívida: a 1,8%, os juros vão de R$ 0,97 mi em 60× para
    R$ 1,66 mi em 96×.
  - O efeito não é monotônico: em 36×, o payback é de 54 meses, porque a parcela acaba cedo.
- **Combinações que chegam perto de 36 meses:**
  - 1,8% em 96× com aluguel de R$ 60 mil: 37 meses;
  - 1% em 60× com aluguel de R$ 60 mil: 37 meses.
- **Na demanda da v2:** a unidade não se paga em 120 meses, nem com o melhor financiamento.

Arquivos: `simulacoes/manaus_financiamento.py`, `resultado_manaus_financiamento.md`.

**Achado (30/09): o "1.960 alunos" vinha do caminho da conta, não da praça.** A v2 prevê faturamento, e eu convertia
faturamento em alunos dividindo por R$ 115 por aluno (o do simulador, com plano de R$ 137). Dois efeitos puxavam para
baixo:

1. **A master de RJ/SP aparece como "média" no faturamento** (coeficiente ~0), mas é a **mais forte em volume** (+32%
   de alunos). As unidades dela têm muitos alunos e faturam pouco por aluno, porque RJ/SP têm muito agregador.
2. **A rede fatura R$ 108 por aluno ativo, não R$ 115.** A conversão contava 6% de alunos a menos.

**A v2 ajustada direto em alunos ativos, com a master de RJ/SP, dá ~2.880 para Manaus** (faixa de 80%: 1.920 a 4.520).
Com master "outras", dá 2.740. Para comparar:
- a mediana da rede é 2.340;
- as unidades com estúdio têm 2.740;
- as unidades com 1.800 m² ou mais têm 3.175 (7 unidades).

**Ressalvas:**
- O R² LOO em alunos ativos é baixo (0,07), com erro típico de 19%.
- O efeito da master de RJ/SP está misturado com o mercado de agregador de SP.

**Com 2.880 alunos a R$ 167 e o plano de estúdio:**
- faturamento maduro de ~R$ 421 mil;
- payback de 54 meses com os custos informados;
- 36 meses com aluguel de R$ 60 mil + equipamento a 1,8% em 96×.

**Implicação para o modelo:** quando o ticket é decisão do operador, a cadeia certa é prever o **volume** e aplicar o
ticket da unidade, não prever faturamento no preço médio da rede. É candidato a formalizar.

Arquivos: `simulacoes/manaus_volume.py`, `resultado_manaus_volume.md`.

**Volume: 2.900 se sustenta? (30/09, protocolo congelado v1.1 + verificação adversarial; `manaus_volume/`)**

- **Isócrona real do pino** (10 min de carro, sem truncamento): 388 mil habitantes, renda domiciliar de ~R$ 3.370.
  Central da v2 em ativos com a master de RJ/SP: 2.958.
- **Esse central carrega a composição de agregador de SP.** As unidades dessa master no treino são todas de SP, com
  ~67% de agregador, e no balcão a master sai −47%. Com a master média, o central é 2.530; por componentes, 2.150 a
  2.550. **O 2.958 é teto de cenário, não centro.**
- **O teste do teto é "maior" pela regra, mas não discrimina.**
  - A regra: ajustado a 2.000 m², 4 de 18 praças de renda baixa passam de 3.500. Só que isso acontece em qualquer faixa
    de renda.
  - As 4 que passam têm 45–68% de agregador.
  - **Com agregador ≤ 33%, nenhuma praça de renda baixa passa de ~3.200** (mediana ~2.650). A mais parecida com Manaus
    é Paranoá Parque (2.000 m², renda parecida, 25% de agregador), com 2.464.
- **Manaus tem a menor oferta de agregador medida:** Wellhub e TotalPass no percentil ~0 da rede.
- **Sinal a favor de número maior (exploratório):**
  - As 10 Smart Fit de Manaus com 12 meses em 2025 têm mediana de ~3.850 alunos, contra 2.717 no Brasil (~+40%); 8 de
    10 estão acima da mediana nacional.
  - As duas da Zona Norte, perto do pino, têm 4.493 (ViaNorte) e 3.408 (Cidade Nova), no 1º ano.
  - Ressalvas: sem metragem, sem controles, e o total inclui TotalPass.
- **Leitura:** a rede Ultra defende 2.500 a 3.000; o mercado de Manaus sugere mais, ainda sem teste formal.
- **Caminho confiável:** a v1.2 com a Smart Fit, controlando renda e população, e ampliando o recorte do metrô de
  Manaus. Depois de abrir, revisar para cima se o mês 3 fechar com 3.105 ativos ou mais.

**Teste formal da Smart Fit (30/09, protocolo §12 + §13, congelado, verificado; `manaus_volume/resultado_smartfit_formal.md`)**

- **O que foi feito:** crosswalk nacional pela listagem do TotalPass (329 unidades casadas), círculo de 5 km igual para
  todas e efeito fixo por metrô.
- **Resultado:** as Smart Fit de Manaus têm **~40% mais alunos por unidade** que as das cidades da Ultra, controlando
  renda, população e idade.
  - Na versão menos favorável, r = 1,38 (IC90 de 1,15 a 1,64). Aplicado à média do modelo (2.532), dá ~3.480 (de 2.910
    a 4.170).
  - Veredito pré-registrado: **"acima do modelo, sem chegar a 3.000 com 90%"**.
- **A queda do fim de 2025 é sazonal nacional:** Manaus caiu −6%, o Brasil −9%. No nível recente, Manaus tem 3.690 e o
  Brasil 2.457.
- **Ressalvas da verificação:**
  - o prêmio vem das 8 unidades abertas em 2024; as 2 antigas ficam no nível nacional;
  - o total inclui o TotalPass;
  - o pino tem 7 unidades da Live e 2 Smart Fit a menos de 1 km (uma aberta em dez/2025).
- **Número de trabalho: ~3.000**, faixa de 2.500 a 3.500. **O mês 3 decide.**


## Fachada — teste final com a planilha completa do Juan (30/09)

- **Resultado:** protocolo v1.3, congelado antes das notas restantes: **INCONCLUSIVO**.
  - Leitura principal (novas, não vistas, loja de rua): N 23, Spearman +0,05 [−0,37; +0,44].
  - Nenhuma amostra confirma. Com todas as notas: +0,00. Só loja de rua: +0,21 [−0,05; +0,45].
- **Não há gradiente por nota:** nota 1 = +16%, 2 = +29%, 3 = −12%, 4 = +1%, 5 = +12% contra o previsto.
- **A régua é subjetiva:** nas 6 unidades de controle, o Juan difere de Felipe/Vini em mais de 1 ponto em 3.
- **Leitura:** o sinal inicial (+0,67, Felipe/Vini, N 13) não se repetiu com um avaliador independente. A fachada fica
  fora do modelo por ora. Não é um não definitivo: se voltar, precisa de checklist objetivo.

Arquivos: `alavancas/10_fachada_final.py`, `alavancas/resultado_fachada_final.md`.

## Termômetro de praça pela Smart Fit (30/09)

**Pergunta.** O volume de alunos das Smart Fit vizinhas melhora a previsão das unidades Ultra?

**Desenho** (protocolo v1.1, congelado, com revisão antes e verificação depois; `termometro/`):
- base de concorrentes atual da VPS (27/09), com 1.065 Smart Fit;
- casamento por nome + UF, que pegou 93% do painel;
- termômetro relativo ao nacional;
- no teste, os dados da Smart Fit dos 12 meses antes da abertura da unidade Ultra.

**Resultado: NÃO MELHORA.**
- O coeficiente saiu −0,69, com IC de −1,75 a +0,37.
- O erro no teste piorou (22,1% → 25,6%), e o Spearman caiu (0,69 → 0,35).
- Nenhuma variante do teste melhora.

**Leitura:**
- **Não há sinal útil.** O sinal negativo não deve ser lido como disputa: pode ser a própria Ultra tirando aluno da
  Smart Fit vizinha.
- **Manaus fica fora do suporte do teste:** o termômetro de lá sai de uma só Smart Fit madura. Então não há base na
  rede nem para transferir o prêmio da Smart Fit de Manaus para a Ultra, nem para negá-lo.
- A v2 segue como modelo de trabalho.
- Ficou congelada a previsão da turma de 2026 com o termômetro (v2T), para um teste limpo no futuro.

**Correção de dado.** A cópia local da base de concorrentes, de 10/09, tinha o teto antigo de 1.000 Smart Fit. A base da
VPS está completa: 4.795 academias, com 16 Smart Fit em Manaus. **Daqui em diante, use a base da VPS.**

## Inventário: variáveis ainda não testadas (30/09)

Cruzamento do que está disponível com o que já foi testado. Workflow só de leitura, com crítica de completude.

**Candidatas, em ordem:**
1. **Experiência do operador na abertura:** nº de unidades que já operava, se é a 1ª, própria × franquia, tempo do
   contrato à inauguração. Fonte: cadastro + planilha de franqueados, ~92 unidades. Nunca testada.
2. **Idade da população: PREMISSA NÃO CONFIRMADA (correção do Felipe, 01/10).** O "público-alvo de 18 a 45 anos" vem do
   posicionamento escrito no CLAUDE.md, não de dado. Conferido em 01/10: **não há idade de aluno** no repositório, no painel,
   nas vendas da Growth nem na Base Consolidada. A variável só entra depois de medir a idade real dos alunos (fonte a
   definir com o Felipe, só agregada por unidade).
3. **Visibilidade objetiva** (classe da via OSM, esquina, distância do pino à rua) + **checklist objetivo do imóvel**.
   Substitui a nota de fachada.
4. **Faculdades** (CNAE 8531–8533 na base de POI): nunca testadas contra volume. O mecanismo ("público
   jovem") também depende da idade real dos alunos.
5. **Demanda corporativa do TotalPass** (VPS, `demanda_revelada_h3`): exige excluir a própria Ultra e medir contra a
   turma de 2026.
6. **Verticalização** (% de domicílios em apartamento): nunca testada.

**Dado novo que falta:**
- horário/24h;
- verba de marketing de inauguração;
- formato e investimento real;
- preço de abertura (a coleta da Growth está pronta);
- fluxo de pessoas.

**Armadilhas (já testadas e nulas):**
- escritórios;
- vagas;
- canibalização Ultra;
- saturação/concorrência total;
- famílias de POI, shopping e estação;
- preço pela foto atual;
- hipótese do diretor (já repetida 4 vezes);
- termômetro Smart Fit.

**Desenho proposto:**
- um pré-registro com correção de Holm;
- as variáveis de território passam antes pelo "laboratório Smart Fit" (~454 unidades com efeito fixo de metrô);
- teste limpo na turma de 2026, com as previsões congeladas.

## Bateria de variáveis novas — operador e modalidades (BLK-UNI-10, 01/10)

**Como foi feito:**
- um pré-registro único para 6 candidatas, com correção para múltiplos testes (Holm);
- duas revisões independentes antes de rodar;
- regras de decisão escritas antes de ver o resultado;
- a Base Consolidada foi lida só na máquina local, e o relatório só tem agregados;
- uma unidade que trocou de dono (informada pelo Felipe) saiu do teste do operador.

**Resultado 1 — experiência do sócio na abertura: não demonstrado.**
- Pergunta: unidade aberta por um grupo que já operava outra Ultra fatura mais do que o modelo prevê?
- Diferença estimada de **+11%**, mas com faixa de **−7% a +31%**: pode ser zero. Com 16 unidades nessa situação, o teste
  só enxergaria efeito acima de ~+42%. Um efeito de +10% a +30% **não está descartado**.
- **Para prever, piora:** com a variável, o erro sobe um pouco nas maduras e no teste. Não entra no modelo.
- **O sinal positivo vem só das unidades novas**, e ali a experiência anda junto com o estúdio: 6 de 9 unidades de grupo
  experiente têm estúdio, contra 2 de 9 das outras. Nas maduras, o grupo experiente fica ligeiramente abaixo (−9%).
- **O mecanismo não aparece:** grupo experiente não tem mais alunos (+1%) e não rampa mais rápido (rampa até um pouco
  mais lenta). O balcão é 17% maior (pista fraca), o que sugere diferença de mix balcão × agregador, e não de volume.
  Isso fica para o modelo em duas partes (BLK-UNI-09).

**Resultado 2 — modalidades além do estúdio (piscina, bike, pilates, lutas): não acrescentam.**
- **−5% por modalidade**, com faixa de **−14% a +6%**. Este resultado é informativo: descarta ganho acima de ~6% por
  modalidade, além do que o estúdio já explica.
- Repete o achado de 28/09 (etapa 10): as modalidades mexem no **ticket**, não no faturamento total.
- Pista solta: piscina sozinha +19%, mas só 6 unidades têm piscina.

**Achado lateral — a precisão da v2 deve ser comunicada como faixa:**
- tirar uma única unidade do treino (a repassada) muda o erro no teste das unidades novas de 22% para 27%, sobretudo
  por nível;
- o erro nas maduras fica estável (~23%);
- o "22%" é a mediana de só 18 unidades. A precisão da v2 deve ser apresentada como **22–27%**.

**Ficou congelado para conferir quando a turma de 2026 amadurecer:** a previsão com e sem as duas variáveis.

**Resultado 3 — qualidade da concorrência ao redor (comodidades do Juan): não reduz o volume.**
- Medida: entre as academias do Wellhub na área de 10 min, a fração com vestiário, chuveiro e armário. Só o Wellhub
  informa os três itens de forma comparável.
- **Laboratório Smart Fit (574 unidades em 48 áreas, comparação dentro da mesma cidade):**
  - **−0,4% de alunos para cada 10 pontos a mais** de concorrência completa;
  - o teste tinha poder para enxergar a partir de −2,8%, então o resultado é informativo: na Smart Fit, a qualidade da
    concorrência vizinha não mexe no volume;
  - não depende de quanta concorrência existe (correlação de −0,01 com o nº de academias).
- **Na Ultra (descritivo):** a associação aparece (−4,4% por 10 pontos), mas com poucos grupos independentes. Com ela, o
  erro nas 18 novas sobe de 22% para 26%. Não entra.
- **Hipótese do diretor** (tamanho rende mais onde a concorrência é fraca): zero, mas sem poder. O teste só enxergaria
  um efeito que anulasse todo o ganho de tamanho. Fica não testável com 57 unidades.
- **Correção de método:** a 1ª montagem do laboratório usava só 374 Smart Fit; a pergunta do Felipe levou a 578. O
  agrupamento por metrô (8 grupos) foi trocado por quadrículas de 15 km dentro da área, decidido só com o desenho, antes
  de ver o resultado.

**Resultado 4 — faculdade muito perto da unidade (até 500 m, ~6 min a pé): não aumenta o volume (05/10).**
- **A pergunta foi redefinida pelo Felipe antes de rodar.** A 1ª versão contava faculdades na área de 10 min, mas na
  prática isso é "estar no centro de cidade grande": 83% da variável repetia renda, população e região. A pergunta dele
  é outra: "ter uma faculdade muito próxima altera o resultado?".
- Medida: CNPJ ativo de ensino superior (graduação, pós e extensão) a até 500 m do pino, aberto antes da decisão.
  - 55% das Smart Fit e 51% das Ultra têm.
  - O teste procurou **aumento ou queda**, por decisão do Felipe.
- **Laboratório Smart Fit (578 unidades, comparação dentro da mesma cidade):**
  - **−2,8% de alunos** com faculdade a até 500 m, contra quem não tem;
  - não significativo (p = 0,19, bilateral);
  - o teste enxergaria efeitos a partir de ±7%;
  - **nenhuma das 11 versões da medida deu positivo**: 300 m, 1 km, distância contínua, só endereço exato, só
    graduação, campus do OSM, sem os casos duvidosos. Todas ficaram entre −2% e −4%.
- **Na Ultra (descritivo, poucos grupos independentes):** +14% de faturamento, faixa de −3% a +33%. O sinal é o oposto
  do laboratório, e somar a variável **piora** a previsão: o erro nas 18 novas vai de 22% para 27%. Não entra.
- **Leitura:** ter faculdade colada não traz mais alunos para uma academia low-cost de rede. Se há efeito, é pequeno e
  mais para baixo do que para cima.
- **Limites:**
  - só há CNPJ ativo hoje;
  - o CNPJ não separa campus de polo EAD;
  - campus grande com CEP exclusivo às vezes fica sem endereço preciso. Esses casos foram tratados à parte e o resultado
    não muda.

**Resultado 5 — ponto de frente para avenida (visibilidade objetiva, OSM): não muda o volume (05/10).**
- Medida: o pino da unidade a até 30 m do eixo de uma avenida (via primária, secundária ou expressa do OpenStreetMap).
  É o "checklist objetivo" que substituiu a nota de fachada.
  - 40% das Smart Fit e 30% das Ultra estão nessa situação.
  - Os pinos da Smart Fit foram conferidos com uma 2ª fonte (TotalPass): distância mediana de 19 m entre as duas.
- **Laboratório Smart Fit (513 unidades, comparação dentro da mesma cidade):**
  - **−0,9% de alunos** de frente para avenida, contra quem não está (p = 0,72);
  - o teste enxergaria a partir de +5% a +6%, e com a regra de decisão a partir de ~+8,5%;
  - todas as variações ficaram entre −3% e +1,5%: 15, 50 e 100 m; com acessos e terciárias; esquina; sem shopping;
    só pinos conferidos nas duas fontes.
- **Na Ultra (descritivo):** −1% de faturamento, com faixa de −18% a +20%, e a previsão quase não muda.
- **Leitura:** ficar de frente para avenida não traz mais alunos para uma academia low-cost de rede. A fachada já tinha
  dado inconclusivo (30/09); a régua objetiva confirma que localização "de vitrine" não é o que separa as unidades.
- **Limites:**
  - o pino tem alguns metros de erro, e a distância é até o eixo da via;
  - não há metragem da Smart Fit, então "porte da loja" não está controlado;
  - túnel e elevado não são distinguidos.

**Placar da bateria:** os cinco itens rodados dão **não demonstrado**:

| item | p |
|---|---|
| operador | 0,16 |
| modalidades | 0,69 |
| qualidade da concorrência | 0,30 |
| faculdade perto | 0,19 |
| frente para avenida | 0,72 |

Pela correção de Holm, nenhum deles entra, qualquer que seja o resultado do último.

**Resultado 6 — população na idade dos alunos ao redor: não demonstrado (05/10).**
- **Faixa definida pela idade real dos alunos da Ultra:** a regra pré-registrada (menor intervalo com ≥ 60% dos
  alunos) deu **20 a 49 anos**, com 66% dos alunos.
- **Medida:** % da população da área de 10 min com 20 a 49 anos, pelo Censo 2022 por setor (IBGE, baixado em 05/10).
  Varia pouco: de 44% a 49% entre as áreas.
- **Laboratório Smart Fit (578 unidades):** **+2,2% de alunos** por +5 pontos de população nessa faixa (p = 0,31).
  O sinal não é estável: sem São Paulo vira −9%.
- **Leitura honesta:** só pela composição etária, o esperado era um efeito de uns +4%, e o teste só conseguiria ver
  algo a partir de ~+18%. O resultado **não diz que a idade da praça não importa**; diz que, com o que dá para medir
  por área, ela não separa uma unidade boa de uma ruim.
- **Ultra (descritivo):** −5% de faturamento, com faixa de −24% a +19%; a previsão não muda.

**Placar final da bateria (fechada em 05/10, correção de Holm):** nenhuma das 6 variáveis entra no modelo.

| item | p |
|---|---|
| experiência do sócio | 0,16 |
| faculdade a até 500 m | 0,19 |
| qualidade da concorrência | 0,30 |
| idade da população ao redor | 0,31 |
| modalidades | 0,69 |
| frente para avenida | 0,72 |

**O que isso quer dizer para a apresentação:**
- a v2 (praça com renda domiciliar + estúdios + master) segue como o melhor modelo, com precisão de 22–27%;
- as seis hipóteses foram testadas com régua fixada antes e revisão independente. Elas cobrem operador, oferta da
  unidade, concorrência, faculdade, ponto de vitrine e idade, e nenhuma explica o que a v2 erra;
- o que sobra do erro deve estar no que ainda não se mede: execução da operação, pré-venda, preço de abertura e mix de
  agregador (BLK-UNI-09);
- previsões das 16 unidades de 2026 com cada variável estão congeladas para conferir quando amadurecerem
  (BLK-UNI-12).

**Primeira medição da idade real dos alunos (05/10, Growth, amostra de 1 semana de vencimentos, 97 unidades):**
- idade mediana de **37 anos**; 80% dos alunos têm entre 20 e 60;
- **18 a 44 anos: 62%** dos alunos com idade; menos de 18: 6%; 45 ou mais: 32%;
- **a Ultra atende todas as idades** (Felipe, 05/10): o "18–45" que estava escrito no CLAUDE.md e no PRD nunca foi
  posicionamento, e o dado confirma isso, porque um terço dos alunos tem 45 anos ou mais;
- entre unidades, a idade mediana vai de 28 a 51 anos;
- **ressalva:** só 40% dos cadastros têm data de nascimento, mas a falta é igual em todas as unidades (36–44%).

Para virar variável falta a idade da população por setor censitário (Censo 2022, IBGE), cujo download precisa de
autorização.

## Faturamento em duas partes: balcão + agregador (BLK-UNI-09, 05/10)

**Pergunta:** prever o faturamento de balcão e o de agregador (Wellhub + TotalPass) separadamente, e somar, erra menos
que a v2? Decisão do Felipe: faturamento por tipo, do Financeiro, e não volume.

**Como foi feito:** pré-registro, revisão adversarial de 3 lentes e teste no mesmo molde da bateria. A soma das partes é
exatamente o faturamento da v2 (100% dos meses). Nas maduras, o balcão é 74% da receita, o Wellhub 16% e o TotalPass 8%.

**Resultado: não melhora a precisão.**
- Erro típico nas 39 maduras (validação cruzada): 23,5% → 22,2% (−1,3 pp; a régua pedia −2 pp).
- Nas 18 de teste: 22,1% → 22,9% (piora 0,8 pp).
- A v2 continua.

**Mas a separação mostra o mecanismo, com clareza** (coeficientes por parte):
- **A master de RJ/SP não muda o total; muda o mix.** Ela tem **−33% no balcão e +167% no agregador** (log −0,39 e
  +0,98), com IC que não cruzam zero. O "efeito master" do total é composição de agregador.
- **DF/GO (M1) tem muito menos receita de agregador:** as outras masters faturam +114% a +167% a mais em agregador
  (log +0,76 a +0,98), sem diferença relevante no balcão.
- **O agregador responde mais à praça:** elasticidade à renda de 0,55 contra 0,25 no balcão; ao m², 0,97 contra 0,51.
- **Estúdio pesa igual nas duas partes** (+23%).
- **Cada parte é mais previsível que o total:** R² fora da amostra de 0,41 (balcão) e 0,32 (agregador), contra 0,26 da
  v2. Mesmo assim os erros das partes não se compensam na soma.

**Aceite de agregador e "substituição":**
- Nas 3 unidades de teste que não aceitam algum agregador, o modelo errou mais que a v2 (83% contra 68%) por prever
  receita baixa demais. Elas faturaram **mais** que o esperado sem agregador, assim como as novas sem agregador na leitura
  precoce.
- **Indício de substituição:** quem não aceita agregador recupera parte desses alunos pelo balcão. É indício com n = 3,
  não prova.

**Pista para seguir (exploratória, fora do critério):** acrescentar o **tier do Wellhub** da unidade ao agregador
melhorou o erro nas 39 (−2,7 pp) e no teste (−2,1 pp). A melhora some quando se corrige o nível. É candidato a teste
próprio.

**Turma de 2026:** as peças de cada unidade ficaram congeladas. Na conferência, a recombinação usa o aceite que de fato
aparecer na receita, por decisão do Felipe (a foto do cadastro de ago/2026 mostra credenciamento ainda em andamento).

## Exploratória antes de qualquer modelo novo (06/10)

Pedido do Felipe: dissecar os dados, olhar os gráficos e ajustar à mão antes de escolher variáveis. Gráficos e planilhas
estão em `OneDrive\Área de Trabalho\Análises - Motor de Expansão\Exploratória BLK-UNI\`, nas pastas 01 a 06.

**O que os números mostram:**
- **O agregador depende mais da praça que o balcão.** Quando a renda dobra, o agregador sobe ~58% e o balcão ~32%.
- **O erro da v2 se concentra em poucas unidades, mas a unidade típica ainda erra ~18%.**
  - As 5 unidades que mais erram fazem 46% do erro quadrático no treino e 79% no teste.
  - Reajustar o modelo sem elas piora o teste.
- **Agregador ganhando mercado, dentro da mesma unidade.** Nas 24 maduras de jan/25 a ago/26, comparando o mesmo mês:
  - balcão −6% em R$ e −13% em pagantes;
  - agregador +18% em R$ e +21% em alunos;
  - faturamento total estável.
- **A abertura já ordena o patamar.** Os meses 1–3 preveem a ordem das unidades maduras (correlação +0,72 no balcão e +0,83 no
  agregador).
- **Captar alunos pesa mais que retê-los.** A captação explica 66–76% da diferença de pagantes entre unidades; a retenção,
  ~12%.

**Política de abertura (informação do Felipe):** desde Botafogo (mar/2025), a rede abre só com planos de balcão. No dado:
- com agregador no 1º mês: ~100% das aberturas de 2024, 62% em 2025-S2 e 0–12% em 2026;
- quem abre sem agregador fatura mais por m² nos primeiros meses (+39% no mês 3);
- mas essa vantagem cai para +5% sem RJ, DF e GO: é sobretudo composição (RJ), ainda sem sinal limpo da política.

**Turma B — unidades sem m² que ganharam metragem do time de expansão.** A definição é área total sem estacionamento, com
mezanino. A previsão da v2 foi congelada antes de olhar o resultado.

| unidade | previsto pela v2 | real | erro |
|---|---|---|---|
| Boa Vista | R$ 291 mil | R$ 332 mil | +14% |
| QNM33 | R$ 229 mil | R$ 295 mil | +29% |
| Bangu (sem agregador) | R$ 184 mil | R$ 328 mil | +78% |

Nas jovens sem agregador, Flow, Vicente Pires R8 e Boqueirão estão bem acima do previsto; Piçarras e Rio Claro, no
previsto.

## Fator "sem agregador" e masters (BLK-UNI-13, 06/10)

**Pergunta 1:** quanto a v2 erra nas unidades que operam sem agregador?
**Pergunta 2:** a v2 melhora se a master pesar menos, ou se a master for trocada pelo tamanho do mercado de agregador da
praça?

**Como foi feito:** pré-registro, checagem seca, revisão adversarial (20 problemas corrigidos antes de rodar), ensaio com
ruído, registro com SHA e uma rodada.

**Sem agregador: a v2 erra muito para baixo, mas não é só substituição.**
- Nas 28 unidades fora do treino, as 5 sem agregador ficaram **+81%** acima do que a v2 previa, comparadas às que aceitam
  os dois (mediana).
- Quebrando: maduras (Botafogo e Bangu) +130%; jovens (Flow, Piçarras e Bertioga) +59%.
- **Sem o RJ, cai para +28%.** O RJ pesa muito: demanda carioca e "sem agregador" andam juntas.
- Se fosse só substituição (o aluno que iria pelo app passa a pagar balcão), o máximo seria ~+19%. O resto vem de outra
  coisa: pré-venda, demanda local, foco no balcão.
- O fator ficou **congelado para conferência, não adotado**. O juiz é a turma de 2026: as 5 unidades que abriram sem
  agregador e ainda não foram vistas.
- A leitura de 2027 provavelmente será inconclusiva, porque as unidades ligam o agregador depois de alguns meses. Toda
  abertura nova sem agregador passa a ter a previsão congelada antes, até dez/2027.

**Masters: nenhuma das duas mudanças melhora a precisão nas 39/18.**
- Masters encolhidas: 23,5% → 22,1% nas 39, mas 22,1% → 24,6% no teste.
- Mercado de agregador no lugar das masters: praticamente igual (23,7% e 22,5%).
- **Mas há um achado importante para expansão:**
  - quando a v2 prevê uma região inteira que ela não viu (deixando um metrô de fora), o erro vai a **45%**;
  - sem depender da master, fica em **24–27%**;
  - ou seja, as masters ajudam onde a rede já está e atrapalham em região nova.
- Para estado ou região sem unidade, a versão sem masters é mais segura.

Arquivos: `uni13/` (protocolo v1.1, resultado, previsões congeladas da turma, REGISTRO); `exploratoria/01–04`;
`previsao_turma_b/`.

## Validação ampliada (BLK-UNI-14, 06/10)

Pedido do Felipe, depois de apontar que eu tinha deixado testes de fora sem perguntar:
- tudo também nos modelos separados (balcão + agregador);
- validar já na turma de 2026;
- os 4 testes de master;
- antes e depois de ligar/desligar agregador.

Três escolhas foram dele, perguntadas antes de rodar: tier pelo cadastro (o R$ por passagem fica só como diagnóstico), mercado de
agregador nas duas versões, e a turma de 2026 mostrada sem veredito.

**O que saiu, em uma linha cada:**
- **Modelos separados × v2:** a v2 continua melhor.
  - Nas 39 maduras os separados ganham por pouco (21,8% × 23,5%), mas perdem no teste (22,9% × 22,1%), na turma B (49% × 29%) e na
    turma de 2026 (46% × 41%).
  - O motivo: para unidade sem agregador eles preveem só o balcão, e ela fatura muito mais.
- **Sem agregador:** a unidade fatura ~35% acima do que a v2 prevê, comparada às que aceitam os dois apps (~30% sem o RJ).
  - Na turma de 2026, as 3 unidades sem agregador vão na mesma direção.
  - Com o fator, o erro típico delas cai de 26% para 7%.
  - Leitura precoce e já vista: é sinal, não prova. Congelado para conferência, não adotado.
- **Masters (9 testes):** nenhum passa a régua.
  - O mais perto é o **tier do Wellhub declarado no cadastro**: 23,5% → 20,6% nas 39 e 22,1% → 18,7% no teste, mas não passa no
    teste estatístico.
  - Sem master, a previsão para região que o modelo não viu fica em ~25%, contra 45% da v2.
- **Antes e depois:**
  - Quando unidades maduras ligaram o TotalPass, o balcão caiu 25% na mediana. Mas 4 das 7 são de SP no mesmo mês (jan/2023), e as
    de DF subiram: sem conclusão.
  - Desligar o TotalPass não trouxe balcão de volta de forma clara (2 casos).
  - Ligar o Wellhub ainda não tem meses depois (RJ, set/2026).

Arquivos: `uni14/` (protocolo v1.1, resultado, previsões congeladas da turma, REGISTROs); gráficos em
`Exploratória BLK-UNI\07 - Validação ampliada`.

## Melhorias nos três modelos (BLK-UNI-15, 06/10)

Pedido do Felipe: "como melhoramos esses modelos?". Ele marcou as 4 opções. Três rodaram aqui; preço, estúdio e tier com data
esperam a coleta da Growth (BLK-UNI-16).

**O que saiu, em uma linha cada** (faturamento, balcão, agregador e total, sempre juntos):
- **Região no lugar das masters:** não melhora em nenhum dos quatro.
  - Ganhos nas 39 maduras viram perda no teste.
  - Como a master M1 é o próprio DF/GO, a pergunta respondida é "precisamos de tantas masters?". A resposta é: não se vê ganho em
    juntar.
- **Treino ampliado (~60 unidades):** não melhora o erro de forma que se distinga do acaso (faturamento −2 pontos, os outros ~0).
  - O que melhora é a firmeza dos pesos: a faixa do peso da metragem cai pela metade.
  - Cuidado: Botafogo e Bangu (RJ, sem agregador) puxam para cima a previsão das duas cegas do RJ.
- **Abrir sem agregador (conferência, não é teste):** nesta base, as 5 sem agregador faturam o dobro do que o modelo prevê (+103%).
  - Com a variável, o erro delas cai de 50% para 23%.
  - No balcão o salto é maior (+284%), porque todo aluno vira aluno de balcão.
  - O efeito é bem maior que os +35% do UNI-14, que foram medidos de outro jeito.
  - Quem julga são as 5 cegas em 2027 (previsões congeladas).
- **Previsão em dois tempos (meses 1–3 + v2):** é a única melhoria clara.
  - Contra a v2 como está, o erro do nível maduro cai 8,5 pontos no balcão (22% → 13,5%) e 22,5 no agregador (39% → 17%).
  - No faturamento cai 3,5 pontos, sem se distinguir do acaso.
  - Só vale depois de abrir e foi medido em quem abriu **com** agregador: para quem abre sem, não vale ainda.

Arquivos: `uni15/` (protocolo v1.1, resultado, previsões congeladas, REGISTROs); gráficos e planilha em
`Exploratória BLK-UNI\09 - Melhorias nos três modelos`.

## Antes de inaugurar: entradas do operador (07/10)

Pergunta do Felipe: dá para melhorar a previsão **antes de abrir** com o que o operador informa na aba de viabilidade
(estúdios, ticket, uma nota do ponto)?

**O que já se sabia (conferido nos arquivos):**
- **Estúdios:** +30% no treino, mas não se repetiu nas 18 novas.
- **Nota livre de fachada:** inconclusiva com avaliador independente.
- **Preço do cadastro:** só existe a foto de hoje, tirada depois do resultado.

**A régua dos testes antigos era fraca (simulação de 07/10):**
- "Cair 2 pontos nas 39 e no teste" detecta um efeito real moderado em só 1–4% das vezes.
- Daqui em diante, o teste é o **tamanho do efeito com faixa**, e os 2 pontos são só o portão para levar à aba.

**Releitura dos testes antigos com o efeito** (leitura; `releitura/resultado_releitura.md`):
- **Tier do Wellhub do cadastro:** +21% de faturamento por nível de tier (faixa +7% a +36%), e resiste à correção por várias
  variáveis.
  - No UNI-14 "não passou" só pela régua.
  - Cuidado: o tier é a foto de hoje do cadastro, não o da abertura.
- **Masters e região:** pesam só no agregador (+61% a +166% contra o DF/GO). No faturamento e no balcão não se distinguem de
  zero.
- **Estúdio × renda e mercado de agregador:** sem efeito.

**Checklist do ponto** (BLK-UNI-17): planilhas prontas para duas pessoas de fora preencherem. São itens de fato do imóvel
antes da abertura, e o teste limpo são as 5 cegas em 2027.

**Preço cheio (BLK-UNI-16):** a coleta da Growth terminou, mas ela mostra **o valor da primeira cobrança, não a mensalidade**.
- Na unidade típica, metade das vendas de Gold no 1º ano sai abaixo de R$ 80, quase sempre a R$ 9,90 (primeiro mês
  promocional).
- O preço do plano só aparece nos meses sem essa promoção.
- **Medida escolhida pelo Felipe:** a "tabela observada" (o preço cheio que a unidade mais praticou no 1º ano, contra as
  maduras). 38 das 57 unidades têm.
- **Resultado (pré-registrado, verificado): o preço não melhora a previsão** em nenhum dos três modelos.
  - Com o preço, o erro até piora: faturamento 25% → 27%, total 23% → 26%.
  - O que ele mostra é o esperado: preço 10% maior dá ticket de balcão ~5% maior, sem perder alunos de forma visível.
  - Na aba, o preço continua valendo na conta do ticket, mas não ajuda a prever quantos alunos a unidade terá.
- **Tier do Wellhub:** é definido antes de abrir na maioria das vezes (Felipe), mas as unidades de 2026 abrem sem Wellhub.
  O +21% foi medido em quem abriu com ele. Conferir quando as de 2026 ligarem.

## Pendências e pedidos (atualizado em 13/10)

**Esperando dado ou tempo:**
- **Checklist do ponto (BLK-UNI-17):** as planilhas A e B estão no OneDrive (`Exploratória BLK-UNI\10 - Checklist do
  ponto`), esperando duas pessoas de fora. Depois: piloto cronometrado de 5 unidades, concordância entre os dois,
  registro, rodada e verificação (`checklist_ponto/protocolo_checklist_ponto.md`).
- **Turma de 2026 (BLK-UNI-12, em 2027):** conferir todas as previsões congeladas (v2, renda domiciliar, master real,
  duas partes, termômetro, bateria e UNI-13 a UNI-15). Entram aí o fator "sem agregador" nas 5 unidades que abriram sem
  ele e a suspeita de que a v2 subestima unidades com estúdio (BLK-UNI-08).
- **Tier do Wellhub:** registrar e conferir quando as unidades de 2026 ligarem o Wellhub.
- **RJ passando a aceitar Wellhub (set/2026):** reavaliar em ~mar/2027. É o primeiro caso de "não aceitava → passou a
  aceitar".
- **Export agregado do Projeto Lifetime** (retenção da turma de abertura e pré-venda): BLK-UNI-PEND-01.

**Dado que falta:**
- metragem de 6 unidades (Icaraí, Pátio Brasil, SG Shopping, Center Shopping, Sagrada Família e Villa Branca); o Felipe
  disse em 06/10 que, por ora, não é possível;
- master e estúdio de São Carlos, que não está no cadastro;
- metragens em conflito: Boa Vista (1.600 m² do time de expansão × 960 m² medidos pelo satélite) e Cotia (750 m² da
  planilha oficial × ~1.050 m² medidos).

**Pode rodar quando quiser:**
- **Preço dentro da mesma unidade, ao longo do tempo.** É a única forma de medir quanto o preço tira de alunos. O dado já
  está coletado (`precos/vendas_unidade_mes.parquet`, jan/2023 a ago/2026, só agregados).

**Decisões do Felipe em aberto:**
- faixa de erro única, ou maior para SP (UNI-07: SP 32% × DF/GO 17%);
- "chance de ser viável" apresentada como ranking, e não como corte.

**Antes de levar a v2 à aba de viabilidade (exige DEC):**
- rodar o simulador com o aluguel e a obra reais das unidades novas;
- conferir a turma de 2026;
- DEC Estratégica que emende a DEC-043 e a DEC-009 (usar a localização para prever demanda).

**Fora do estudo, registrado:**
- a correção do "18–45" no `CLAUDE.md`, no `PRD.md` e em `docs/expansao_dominio.md` está feita no checkout do Felipe,
  ainda sem PR; sobram comentários em `dashboard/constants.py:461` e em `dimensionamento/`;
- erros de dado para corrigir na origem: BLK-DADOS-UNI-01.

**Já resolvido (registro):** metragem por satélite (etapa 8 e entregas de 29/09 e 06/10), correções na produção
(PRs #418 a #423), teste do operador (bateria, item 1), faixas de erro (UNI-07) e idade dos alunos (05/10).

## Ideias para o sistema (registradas, sem desenvolvimento nesta fase)

- **Curva de alunos e alerta do mês 3.** Cada unidade no 1º ano é comparada com a curva normal. No mês 3, projeta-se
  onde ela vai se estabilizar (erro de 5–9%), com alerta se ficar abaixo do previsto na aprovação. Depende de saber o
  "previsto" de cada unidade.
- **Estudo reverso da viabilidade.** Reconstituir a premissa de alunos usada na aprovação de cada unidade, para
  comparar previsto × realizado.
- **Rampa do simulador.** Trocar os 500 alunos iniciais com reta até o mês 8 pela curva observada.

Decisão do Felipe (28/09): o momento é de pesquisa, análise e ciência de dados para um modelo mais preciso;
desenvolvimento fica para depois.

## Próximos passos (13/10)

O estudo passa ao Juan. A ordem e as datas estão na agenda de `README_PASSAGEM.md`:
1. checklist do ponto, quando as planilhas voltarem;
2. preço dentro da mesma unidade, que pode rodar já;
3. conferência da turma de 2026, do tier e do RJ, em 2027;
4. antes de qualquer DEC, a viabilidade com custos reais.
