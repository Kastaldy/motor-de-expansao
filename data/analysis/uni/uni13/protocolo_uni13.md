# BLK-UNI-13 — Fator "sem agregador" e masters encolhidas (pré-registro)

Versão **1.1**, 2026-10-06. A v1.0 foi escrita antes de rodar. A v1.1 aplica os 20 achados confirmados da revisão adversarial
(workflow `wf_89f44bbb-f93`; ver §Emenda). Só análise: fase de pesquisa; produção só muda com DEC.

Pedido do Felipe (06/10), itens 1 a 3 da recomendação:
- **item 1:** fator para unidade sem agregador (etapa 4 do `uni09/plano_melhoria_duas_partes.md`);
- **item 2:** validação na turma de 2026;
- **item 3:** braços A e B da etapa 2 (masters).

## 0. O que já se sabe (e por que isto existe)

**A v2 nunca viu unidade sem agregador.** Ela é log fat ~ log m² + log renda domiciliar + log pop + masters + estúdios, treinada
em 39 maduras de 2025, e as 39 aceitam Wellhub.

**Política de abertura.** Desde Botafogo (mar/2025), a rede abre sem agregador nos primeiros meses
(`exploratoria/03_politica_sem_agregador.py`). Nas unidades sem agregador vistas até hoje, a v2 errou para baixo:
- Botafogo +178% (teste);
- Bangu +78% (turma B);
- Flow, Vicente Pires R8 e Boqueirão acima da trajetória;
- já Piçarras e Rio Claro ficaram no previsto.

**As masters da v2 carregam a composição de agregador.** No UNI-09, a M3 vale −0,39 no balcão e +0,98 no agregador. Elas também se
ajustam demais à amostra: a master sozinha leva o teste de 21,5% para 31,0% (CADERNO:565). Mas, junto com estúdios, a master acerta o
nível; sem ela, o erro vai a 25% (CADERNO:568-569). Por isso, tirar a master tende a perder o c3 cru por nível.

**Exposição.** Todas as unidades da parte I já tiveram faturamento visto em descritivos: lotes 1–5 da exploratória, UNI-02, turma B.
O θ̂_sem é **quase calculável com números já vistos**: as duas maduras do RJ estão no topo e já são conhecidas. Esta parte é
**ESTIMAÇÃO**, não teste. As 39/18 da parte II foram consultadas muitas vezes (UNI-02, UNI-05, UNI-07, bateria, UNI-09). O c3 do
braço B é um **reteste** nas 18 que deram origem à pista (`uni09/resultado_uni09.md:44`).

## PARTE I — fator para unidade sem agregador (itens 1 e 2)

### I.1 Pergunta

Quanto a v2 erra, em média, nas unidades que operam SEM agregador, em comparação às que operam com os dois? Se o desvio for estável:
- onde a unidade não aceita agregador, a previsão passa a ser `v2 × exp(θ_sem)`;
- onde aceita, continua `v2` (fator 1).

O símbolo θ fica reservado à substituição ENTRE agregadores, como no plano (agregador-2).

### I.2 Amostra de estimação (fixada antes)

Entram as unidades **fora do treino das 39** que cumprem quatro condições.

1. **Atributos da v2:** renda domiciliar, população, estúdio e master no cadastro.
2. **Metragem:**
   - as 18 do teste usam a mesma do UNI-02 (`uni02/confirmacao_por_unidade.csv`), para o erro delas ser o mesmo já publicado;
   - as demais seguem esta ordem: oficial → time de expansão (`coleta_metragem/metragem_time_expansao_2026-10-06.csv`; área total
     sem estacionamento, com mezanino) → satélite (`metragem_estimada_2026-09-29.csv`, já corrigida pelo viés 1,12).
3. **Desfecho na janela 2026-01..2026-08**, por UMA das duas regras:
   - **madura:** ≥ 3 meses válidos com mês de vida ≥ 12. Desfecho = média do log do faturamento (regra do UNI-02).
   - **jovem:** não tem 3 meses maduros, mas tem ≥ 3 meses válidos com mês de vida entre 6 e 11. Desfecho = média, nesses meses, de
     `log(faturamento) − log(curva_p50(mês de vida))`. A curva é a congelada do UNI-03 (`uni03/curva_uni03.csv`), **série
     `faturamento` para TODAS**, com e sem agregador. A série `pagantes` (contagem de alunos de balcão) entra só como sensibilidade.
     **Direção declarada:** com `pagantes`, o nível das jovens sem agregador cai ~0,10 em log e o θ̂_sem sai menor. A curva vem do regime
     com agregador; sem agregador o total sobe mais rápido, então a curva de faturamento tende a INFLAR as jovens sem agregador.
4. **Fora, sempre:**
   - as 5 cegas da turma de 2026 (belford-roxo-rj, novo-gama-df, paulinia-sp, domingos-ferreira-pe, bonsucesso-rj);
   - **icarai-rj**, que fica fora desta rodada mesmo que a metragem chegue depois (está sem metragem hoje).

As elegíveis excluídas, com o motivo, são listadas no resultado.

**Previsão de cada unidade:** a v2 travada, com os coeficientes das 39 e o nível de 2026 = + `cal['l_fat']` (igual ao UNI-02 e à
turma B). Erro: `e = log real − log previsto`.

### I.3 Aceite observado (nos mesmos meses do desfecho)

Receita de agregador = `fin_gympass + fin_totalpass`.
- **nenhum:** receita de agregador > 0 em menos da metade dos meses.
- **os dois:** Wellhub > 0 e TotalPass > 0, cada um em pelo menos metade dos meses.
- **um só:** o resto. É só descritivo: são 3 unidades, e a substituição entre agregadores (θ do plano) fica para depois.

### I.4 Estimativa, estratos e portões

**Estimativa.** **θ̂_sem = mediana(e | nenhum) − mediana(e | os dois)**, nas unidades da §I.2. A diferença tira o viés geral da v2
nas unidades novas (calendário, coorte), que não é efeito do agregador.

**Incerteza.** Com 5 unidades "nenhum", o bootstrap estratificado (B = 9.999, semente 20261006) é só a **amplitude**. Ele é
reportado com o intervalo de ordem [x(1), x(5)] das "nenhum" menos a mediana das "os dois", e é **descritivo**.

**Estratos obrigatórios:**
- θ_sem só de **maduras:** nenhum maduras contra os dois maduras;
- θ_sem só de **jovens:** nenhum jovens contra os dois jovens, pela mesma curva.

**Sensibilidades relatadas (sem portão):**
- curva `pagantes` nas jovens sem agregador;
- sem RJ (que tira junto M3, estúdio e maturidade);
- calendário do BALCÃO nas "nenhum": `cal_balcão` = mediana de (média do log do balcão em 2026 − em 2025) nas do treino presentes
  nas duas janelas. Com ele, θ̂_sem soma `cal['l_fat'] − cal_balcão`.

**Portões para CONGELAR o fator** (todos precisam passar; senão θ̂_sem é reportado e NÃO congelado):
1. pelo menos 4 unidades "nenhum";
2. sinal estável ao tirar cada unidade "nenhum";
3. estratos maduras e jovens com o mesmo sinal;
4. a sensibilidade com a curva `pagantes` com o mesmo sinal.

**Checagem interna (não é teste).** Em cada unidade "nenhum", compara-se a previsão `v2 × exp(θ̂_sem sem ela)` com a v2 e se calcula
o erro típico dos dois no grupo.

**Leitura estrutural (σ como fração de ALUNOS).** O aluno de agregador rende 0,60 do de balcão (premissa; CADERNO:515,522).
- σ̂ = `0,60 × (exp(θ̂_sem) − 1 + a) / a`, com **teto 1** (σ = 1: todo aluno de agregador perdido vira balcão).
- Fator de substituição total: `1 + a × (1/0,60 − 1)`.
- Relatado numa grade de `a` (p25, p50 e p75 da fatia de agregador na receita das "os dois") × premissa {0,47; 0,60}.
- Se σ̂ > 1, a substituição sozinha não explica o desvio: há outra causa (pré-venda, demanda do RJ, foco no balcão).

### I.5 Validação (item 2): a turma de 2026

**O que se congela hoje, sem ver o desfecho:**
- para as 14 unidades com previsão (a turma tem 16; jardim-das-americas e vila-izabel não têm master), a v2 já congelada em 30/09
  (`previsao_2026/previsoes_turma_2026_v2_domiciliar.csv`, coluna `prev_v2dom_cal2026`, SHA 999bd027…);
- para as 5 cegas, `v2 × exp(θ̂_sem)` (se os portões passarem) e a referência σ = 0, `v2 × (1 − a)`.

Exposição declarada: os meses 0–2 de passagens e pagantes das cegas apareceram num listado de conferência em 06/10. O faturamento e o
nível maduro delas nunca foram olhados.

**Leitura.** Cada unidade da turma é lida quando tiver ≥ 3 meses válidos com mês de vida ≥ 12 (previsto para jun–set/2027):
- o aceite é o observado na janela de leitura (§I.3);
- unidade que **mudou de aceite** dentro da janela é marcada e lida à parte, como em `uni09/protocolo_uni09.md:136`;
- o calendário é recalibrado para o ano lido, como em `termometro/01_termometro.py:146-147`.

**Métrica principal (contraste dentro da turma, mesmo nível):**
- Δ_turma = mediana(erro da v2 | "nenhum") − mediana(erro da v2 | "os dois"), entre as unidades da turma de 2026 com previsão.
- Exige ≥ 3 "nenhum" e ≥ 3 "os dois" maduras.
- **Confirma** se Δ_turma ≥ θ̂_sem/2 (com θ̂_sem > 0); **refuta** se Δ_turma ≤ 0; no meio, **inconclusivo**.
- O erro típico absoluto de `v2 × fator` contra a v2 e contra `v2 × (1 − a)` (critério de 10 pp do plano:152-154) fica só como
  métrica de comunicação.

**Expectativa declarada:** a leitura de 2027 **provavelmente será inconclusiva**. A política é sem agregador só nos primeiros meses:
Caxias, São Gonçalo Centro, Laranjeiras e Vicente Pires R8 ligaram Wellhub em set/2026, e duas cegas são do RJ.

**Ampliação (dono: o estudo BLK-UNI, a cada conferência do BLK-UNI-12):** toda unidade nova sem agregador com metragem e cadastro
recebe `v2` e `v2 × exp(θ̂_sem)` **congelados antes de ter 6 meses de vida**. O conjunto é lido junto, com data-limite em
**2027-12-31**.

A adoção é do Felipe.

**Desvios declarados do plano (etapa 4):**
- o fator é empírico (θ_sem, um parâmetro) e não σ estrutural com IC em [0; 1/0,60]: com tão poucas unidades, σ não se separa de
  demanda local, pré-venda e política;
- o braço de EVENTOS com placebo (boa-vista, campo-largo, Suzano, RJ) fica para depois; o plano já o previa por volta de mar/2027,
  quando houver meses do RJ com Wellhub;
- a substituição entre agregadores (θ do plano) fica de fora, porque só há 3 "um só";
- o desfecho de painel da etapa 3 virou a regra madura/jovem acima.

## PARTE II — masters encolhidas e mercado de agregador (item 3)

### II.1 Braços (uma especificação cada, sobre a v2 total)

**A — masters encolhidas.**
- Ridge nos coeficientes das masters com **one-hot completo** (M1, M2, M3, outras), intercepto e demais variáveis sem penalidade.
  Assim cada master encolhe em direção à média da rede, e não ao contraste com a M1.
- λ na grade {0; 0,25; 0,5; 1; 2; 4; 8; 16; 32; 64; 1.000}, escolhido pela soma dos quadrados dos erros LOO em log **dentro** do
  treino de cada dobra (LOO aninhado para o c2; LOO nas 39 para a previsão das 18).
- Ponto com alavancagem 1 conta como erro infinito.

**B — mercado de agregador no lugar das masters.** É a v2 sem as dummies de master e com duas variáveis novas:
- `x1 = log((wh_n_conc_c10 + tp_n_conc_c10 + 1) / (iso_pop__carro_10 / 1.000))`;
- `x2 = log(1 + iso_n_independente_agregador__carro_10)`.

Com log pop no modelo, x1 equivale à contagem de parceiros; o coeficiente de log pop deixa de ser comparável ao da v2. É foto de
set/2026 (associação).

**Referência (não é braço):** v2 sem masters, para ler a trava do metrô.

**Desvios declarados do plano (etapa 2):**
- saem o efeito aleatório (partial pooling) e a versão em duas partes: o ridge one-hot é o equivalente fechado, e as duas partes não
  ganharam no UNI-09;
- o braço B passa da parte agregador para o TOTAL, porque o modelo vigente é a v2 total.

### II.2 Critério (bateria §4.1, sem c1)

**c2.**
- O erro típico LOO das 39 cai ≥ 2 pp contra a v2.
- **E** o p do bootstrap pareado passa no Holm com k = 2 e **α de família 0,05 unilateral** (limiares 0,025 e 0,05). Isso equivale
  ao IC 90% bilateral com Holm, como pedem o plano e a bateria.
- O p é a fração das B = 9.999 reamostras das 39 em que a queda da mediana é ≤ 0.

**c3.** No teste das 18, o erro típico cai ≥ 2 pp, **cru e recentrado**. Recentrado = cada modelo menos a mediana do próprio resíduo
nas 18.

**Trava do braço B.** O erro típico deixando um metrô inteiro de fora (`iso_metro`, nas 39) não pode piorar contra a v2. Junto vêm:
- o erro por dobra (metrô 1, metrô 0, demais), porque nas dobras grandes a v2 fica ancorada numa única unidade da master;
- a comparação com a v2 sem masters.

**Relatados:** IC 90% da queda no LOO e no teste, viés mediano no teste, RMSE em log.

**Leitura final:**
- **"Melhora a precisão"** = c2 + c3 (e a trava, no B). Senão, a v2 fica.
- Braços que passarem NÃO se somam sem novo pré-registro.
- Turma de 2026: as previsões de cada braço para as 14 com previsão são congeladas com SHA, para o BLK-UNI-12.

## Fluxo

1. checagem seca (`--seca`), feita na v1.0: contagens sem desfecho de faturamento;
2. revisão adversarial (workflow, só leitura), feita: §Emenda;
3. ensaio (`--ensaio`): TODOS os desfechos, inclusive a fatia de agregador, trocados por ruído ou constante; saída só no scratchpad;
4. REGISTRO pré-rodada com SHA do protocolo, do script e dos insumos;
5. rodada real (`--rodar`): resultado, previsões congeladas da turma (REGISTRO gravado logo depois delas) e gráficos no OneDrive
   (`06 - Fator sem agregador e masters`).

Arquivos: `uni13/01_fator_e_masters.py`, `uni13/REGISTRO_PRE.txt`, `uni13/resultado_uni13.md`,
`uni13/previsoes_turma_2026_uni13.csv`, `uni13/REGISTRO_CONGELAMENTO_turma_2026.txt`.

## Emenda v1.1 (revisão adversarial `wf_89f44bbb-f93`, 20 achados confirmados e 9 refutados)

1. **Curva das jovens:** `faturamento` para todas, com `pagantes` como sensibilidade. A v1.0 usava `pagantes` (contagem) nas sem
   agregador, o que baixava o θ̂ em ~0,10.
2. **2027:** contraste dentro da turma em vez de erro absoluto. Ficaram registrados: a regra para quem muda de aceite, o processo e o
   dono da ampliação, a data-limite e a expectativa de leitura inconclusiva.
3. **Composição:** estratos maduras e jovens obrigatórios e portões de congelamento (sinal estável, estratos e curva). Declarado que o
   θ̂ é quase calculável com o já visto.
4. **σ:** uma definição só (alunos, teto 1), fator de substituição total, grade de `a` × premissa. A v1.0 misturava o teto de outra
   definição.
5. **Holm:** α de família 0,05 unilateral. A v1.0 usava 0,10, mais frouxo que o plano no 2º passo.
6. **Ridge:** one-hot completo; trava de alavancagem 1.
7. **Desvios do plano:** declarados (eventos, θ entre agregadores, painel, efeito aleatório, duas partes, B no total).
8. **Trava do metrô:** erro por dobra e referência sem masters.
9. **Calendário do balcão:** como sensibilidade.
10. **Icaraí:** travada fora; lista de excluídas com o motivo.
11. **Ensaio:** sem nenhum desfecho real. O ensaio de 06/10 14:07 (v1.0) exibiu a fatia de agregador real `a` no resultado de ensaio.
12. **Turma:** SHA das previsões de 29–30/09 conferidos; mesmo padrão de previsão faltante; tolerância de 0,5%; REGISTRO gravado antes
    dos gráficos.
13. **Textos:** "congelado para conferência (não adotado)", "checagem interna, não é teste", IC rotulado como amplitude, c3 do B como
    reteste, nota sobre x1.
14. **Rastreabilidade:** mais insumos no REGISTRO_PRE.
