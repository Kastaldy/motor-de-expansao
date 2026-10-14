# Relatório BLK-UNI — Inteligência de Unidade: roteiro da apresentação

Roteiro dos gráficos do estudo para a apresentação executiva à diretoria. Cada gráfico tem o título igual à
**mensagem** que ele sustenta, um subtítulo curto com o que se mede e um rodapé com a fonte e o N.

- Gráficos: `graficos/<id>.png` (16:9, 12 × 6,75 pol., 200 dpi).
- Números plotados: `dados/<id>.csv` (`sep=";"`, `utf-8-sig`).
- Scripts reproduzíveis: `scripts/<id>.py`, todos com o estilo único de `scripts/_estilo.py` (alias `estilo.py`).
  Para regenerar: a partir da raiz do repositório,
  `PYTHONIOENCODING=utf-8 PYTHONPATH=src .venv/Scripts/python.exe data/analysis/uni/relatorio/scripts/<id>.py`.
- Cada script lê o arquivo-fonte, recalcula o que plota e confere contra os valores deste roteiro; se divergir,
  imprime `AVISO`, usa o valor calculado e grava a divergência na coluna `aviso_divergencia` do CSV.

## A história em um parágrafo

A regra de viabilidade de hoje lê só a metragem: dá quase o mesmo faturamento a toda unidade e, nas 18 abertas em
2025, o real ficou 17% abaixo do que ela previa (24% no cálculo exato do simulador de produção). Para corrigir isso,
montamos uma base única da rede (98 unidades, 2.088 meses de faturamento, ~240 características e 46 milhões de pontos
de interesse) e testamos cada ideia com regra escrita antes e conferência em unidades que o modelo nunca viu.
Confirmaram-se três coisas: o modelo da praça (metragem, renda e população a 10 min de carro), que acerta o
faturamento sem viés e ordena melhor as praças, com erro típico de ~22%; a rampa real, bem mais rápida que a do
simulador e corrigível com uma reta simples; e o alerta do 3º mês, que projeta os alunos maduros com erro de 5–9%.
Com a amostra e as medidas de hoje, não melhoraram a previsão: empresas no entorno, crescimento, quantidade de
concorrência, estado, modelos mais complexos e renda × churn nas unidades novas; a hipótese do diretor segue a favor,
sem prova, e o erro que sobra é quase todo volume de alunos, que nenhuma variável de território explica. As alavancas
do operador entram como cenário: o agregador troca ticket por volume com saldo pequeno (premissa de 60% mantida),
estúdios + master real formam a v2 de trabalho (ordenam melhor sem ganhar precisão), a fachada segue em avaliação e o
mix por estado muda a divisão dos alunos, não o faturamento. No simulador de produção, o modelo da praça (a v2 do
UNI-05) reduz o erro de faturamento de 33% para 22%, elimina o viés e corta o erro de payback de 20 para 14 meses, mas
empata com a regra atual na decisão de aprovar; o objetivo declarado é prever melhor, e isso ele comprovou (a v2 de
trabalho erra o mesmo no faturamento, mas ainda não foi rodada no simulador contra a regra atual). O próximo salto depende de
dado novo (operador, fachada das unidades restantes, preço no tempo, custos reais e a turma de 2026 já congelada, cujas
primeiras leituras vão para os dois lados), e nenhum "não" deste estudo é definitivo: o dicionário de variáveis e os
testes podem ser revisitados.

## Como ler os selos

| selo | significado |
|---|---|
| **CONFIRMADO** (chip azul) | passou na régua escrita antes, em unidades que o modelo nunca viu |
| **EXPLORATÓRIO** (âmbar) | achado em 2025 ou depois de ver o dado; ainda sem conferência |
| **EM AVALIAÇÃO** (âmbar) | teste em andamento, com dado sendo coletado (fachada) |
| **PRELIMINAR** (âmbar) | etapa em andamento, com decisões do dono pendentes (UNI-07) |
| **ILUSTRAÇÃO** (âmbar) | conta com premissas-padrão, fora do protocolo de teste |
| **DESCRITIVO** (âmbar) | retrato do que já se vê, sem teste (turma de 2026) |

Regras de privacidade: nenhum nome de pessoa em imagem, dado ou rodapé (avaliadores = "avaliador A/B" ou "avaliador
independente"); master só como M1–M7; nenhum dado `LOCAL_*` aparece em gráfico ou CSV (a função `carregar()` do
UNI-01, reusada pelo `s4_renda_churn`, lê o `LOCAL_demanda_totalpass` como coluna auxiliar, sem nada plotado).

## Três nomes fixos para os modelos

| nome no deck | o que é |
|---|---|
| **regra atual** | a viabilidade de hoje: alunos pela densidade da metragem × receita por aluno |
| **modelo da praça** | metragem + renda + população da isócrona de 10 min de carro (é a "v2" do UNI-05 e o M0 do UNI-02) |
| **v2 de trabalho** | modelo da praça + estúdios + master real (M1–M7); decisão do dono de 29–30/09 |

## Seções e gráficos

### 1. O problema: a viabilidade de hoje lê só a metragem

A regra atual dá quase o mesmo faturamento a toda unidade: nas 18 unidades novas, o real ficou 17% abaixo do previsto
na mediana. No payback, ela encurta o das fracas e alonga o das fortes; na decisão, não aprovou nenhuma fraca, mas
recusou 5 das 8 que se pagaram.

| id | título (mensagem) | forma | selo |
|---|---|---|---|
| `s1_regra_achata` | A regra atual dá quase o mesmo número a toda unidade — e, na mediana, o real ficou 17% abaixo | dumbbell horizontal (previsto × real) | — |
| `s1_payback_prometido` | No payback, a regra atual promete demais às fracas e de menos às fortes | dispersão com diagonal (previsto × real) | — |

### 2. O que construímos: uma base única e um método que separa achado de coincidência

Juntamos as fontes numa base única, medimos por satélite a metragem que faltava, achamos erros de dado que já
afetavam a produção e fixamos o método: regra escrita antes, exploração em 2025 e confirmação em unidades nunca
vistas. É isso que separa "confirmado" de "exploratório" neste relatório.

| id | título (mensagem) | forma | selo |
|---|---|---|---|
| `s2_base_cobertura` | Uma base única: 98 unidades, 2.088 meses de faturamento e ~240 características por unidade | KPIs + barras de cobertura | — |
| `s2_metodo` | Cada ideia foi testada em dois tempos: achada em 2025, conferida em unidades que o modelo nunca viu | diagrama de fluxo e linha do tempo | — |
| `s2_metragem_satelite` | A metragem por satélite é boa o bastante: erro típico de 20% (25% depois de corrigir o viés de +12%) | dispersão (estimada × conhecida) | — |
| `s2_erros_dado` | No caminho, achamos erros de dado que já distorciam a tela de produção | quadro | — |

### 3. O que se confirmou: modelo da praça, rampa real e alerta do 3º mês

Testado em 18 unidades que nunca viu, o modelo da praça acerta o faturamento sem viés e ordena melhor as praças (erro
típico ~22%); a rampa real é bem mais rápida que a do simulador e se corrige com uma reta simples; e o 3º mês projeta
os alunos maduros com erro de 5–9%.

| id | título (mensagem) | forma | selo |
|---|---|---|---|
| `s3_placar_modelo` | O modelo da praça se confirmou em unidades que nunca viu: sem viés e ordenando melhor | barras em 3 painéis | CONFIRMADO |
| `s3_previsto_real` | Com a praça, o erro fica equilibrado: 9 acima e 9 abaixo, contra 7 e 11 na regra atual | dumbbell com 3 marcadores (retoma `s1_regra_achata`) | — |
| `s3_curva_rampa` | A rampa real é bem mais rápida que a do simulador: 68% do nível maduro no 1º mês, contra 37% | linhas com faixa p10–p90 | — |
| `s3_rampa_confirmacao` | Em 22 unidades novas, a curva real erra metade do simulador nos alunos — e uma reta recalibrada já resolve | barras agrupadas + ilustração | ILUSTRAÇÃO (painel direito) |
| `s3_alerta_mes3` | No 3º mês, a projeção dos alunos maduros erra 5–9%, contra ~22% antes de abrir | barras + intervalos | CONFIRMADO |

### 4. O que não se confirmou — e por que isso também é resultado

Empresas no entorno, crescimento, quantidade de concorrência, estado, modelos mais complexos e renda × churn nas
unidades novas não melhoraram a previsão; a hipótese do diretor segue a favor, sem prova. O erro que sobra é quase
todo volume de alunos, e nenhuma variável de território o explica. Vale para as variáveis como foram medidas e para a
amostra de hoje: não é um "não" definitivo, e o dicionário de variáveis pode ser revisitado.

| id | título (mensagem) | forma | selo |
|---|---|---|---|
| `s4_placar_hipoteses` | Além do modelo da praça, nenhuma variável de território se confirmou | placar (hipótese × veredito) | — |
| `s4_poi_nulo` | Empresas, shoppings e estações no entorno não melhoram a previsão — nem na Ultra, nem em 454 Smart Fit | forest plot (ΔR² fora da amostra) | — |
| `s4_erro_e_volume` | O que o modelo erra é volume de alunos — e nenhuma das 22 características explica o erro de faturamento de forma confiável | decomposição + correlações | EXPLORATÓRIO |
| `s4_renda_churn` | Praça mais rica cancela menos na rede madura, mas o efeito não apareceu nas unidades novas | forest plot | — (pós-hoc marcados) |
| `s4_diretor_replica` | A hipótese do diretor aparece com o mesmo tamanho em outra rede — evidência a favor, ainda sem prova | forest plot | EXPLORATÓRIO |

### 5. As alavancas do operador

O modelo prevê a praça; o operador declara o modelo de negócio. O agregador troca ticket por volume com saldo pequeno
(premissa de 60% mantida); o estúdio é o sinal mais forte e entra com a master real na v2 de trabalho; preço e "sem
agregador" não se medem com o dado de hoje; a fachada segue em avaliação; e o mix por estado muda a divisão dos
alunos, não o faturamento.

| id | título (mensagem) | forma | selo |
|---|---|---|---|
| `s5_alavancas_forest` | Das alavancas, só o estúdio tem efeito medido no faturamento — e, com a master controlada, ele já não se distingue de zero | forest plot com colunas de leitura | EXPLORATÓRIO |
| `s5_agregador` | O agregador troca ticket por volume com saldo pequeno; a premissa de 60% fica | barras com IC + comparação | EXPLORATÓRIO (painel esquerdo) |
| `s5_estudio_separa` | Nas unidades novas, as com estúdio faturaram acima do previsto (+54%) e as sem estúdio, abaixo (−21%) | strip plot por grupo | EXPLORATÓRIO |
| `s5_botafogo` | Botafogo: as alavancas declaradas explicam parte do caso — o resto é volume excepcional | cascata | ILUSTRAÇÃO |
| `s5_fachada` | Fachada: sinal a favor que enfraqueceu com o primeiro avaliador independente — ainda em avaliação | barras por nota + forest | EM AVALIAÇÃO |
| `s5_mix_estado` | A fatia de agregador se separa por estado — SP ~56%, DF/GO ~32% — mas não muda faturamento nem payback | barras (2 painéis) | EXPLORATÓRIO |

### 6. Quanto tudo isso melhora a viabilidade

O ganho real está na demanda da praça: viés eliminado, ordenação melhor e, no simulador de produção, o modelo da
praça leva o erro de faturamento de 33% para 22% e o de payback de 20 para 14 meses. Estúdios + master (v2 de trabalho)
ordenam melhor com a mesma precisão, mas ainda não passaram pelo simulador; as demais alavancas servem para simular
cenários. Na decisão de aprovar, modelo da praça e regra atual empatam.

| id | título (mensagem) | forma | selo |
|---|---|---|---|
| `s6_escada` | O ganho está na demanda da praça; estúdios + master ordenam melhor com a mesma precisão | barras pareadas (erro e ordenação) | EXPLORATÓRIO (CONFIRMADO nas 2 primeiras linhas) |
| `s6_viabilidade` | No simulador, o modelo da praça prevê melhor faturamento e payback — e empata na decisão de aprovar | barras em 4 painéis | — |

### 7. Próximos passos

Três frentes fecham as dúvidas que restam: faixas de segurança em torno de cada previsão (UNI-07, em andamento), a
conferência da turma de 2026 já congelada e a coleta de dado novo (operador, fachada, preço no tempo, custos reais, RJ
com agregador). O próximo ganho de precisão vem de dado novo, não de mais geografia, e os "nãos" de hoje podem ser
revisitados com medidas melhores.

| id | título (mensagem) | forma | selo |
|---|---|---|---|
| `s7_faixas_seguranca` | A v2 passa a entregar faixa: de −37% a +58% em torno da previsão, que cobriu 13 das 18 unidades novas | faixa p10–p90 por unidade + real | PROVISÓRIA (UNI-07 verificado; decisões do dono pendentes) |
| `s7_turma_2026` | A turma de 2026 é a prova que falta: previsões congeladas antes do resultado, com primeiras leituras para os dois lados | dot plot com faixa | DESCRITIVO |
| `s7_roadmap` | O próximo ganho de precisão vem de dado novo, não de mais uma variável geográfica | quadro | — |

## Decisões do dono que o relatório respeita

- v2 de trabalho = praça (m², renda e população da isócrona de 10 min) + estúdios + master real (anonimizada M1–M7).
- A premissa do agregador fica em 60%.
- Botafogo sai só do teste de fachada; fica em todos os testes do modelo.
- A fachada segue em avaliação: não é um "não" definitivo; faltam as notas das unidades restantes.
- O mix por estado não muda faturamento nem payback.
