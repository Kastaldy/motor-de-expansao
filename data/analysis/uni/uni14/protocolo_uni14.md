# BLK-UNI-14 — Validação ampliada (pré-registro)

Versão **1.1**, 2026-10-06. A v1.0 foi escrita antes de rodar; a v1.1 incorpora a revisão adversarial `wf_d1fc8a01-6ba` (30 achados
confirmados) e três decisões do Felipe tomadas antes da rodada (ver §Emenda v1.1, no fim). Só análise.

**Escopo aprovado pelo Felipe (06/10).** Ele respondeu ao pedido "o que você deixou de fora sem perguntar" e marcou os 4 itens;
as unidades jovens entram com aviso.
- **(a)** tudo também nos **modelos separados** (balcão + agregador), lado a lado com a v2;
- **(b)** **validar já** na turma de 2026;
- **(c)** os 4 testes de master do plano: peso reduzido (A), mercado de agregador (B), **estúdio × renda (C)** e **tier do
  Wellhub na época (D)**;
- **(d)** **antes e depois** nas unidades que ligaram ou desligaram agregador.

**Fora, por limite do dado** (dito ao Felipe antes de rodar):
- as 5 cegas da turma, que têm 1 a 2 meses de vida;
- o mês de set/2026, porque o Financeiro não fechou;
- São Carlos, que está sem cadastro (entra se o Felipe passar a master e o estúdio);
- as unidades sem metragem.

Este bloco NÃO mexe no UNI-13, que segue congelado (SHA 80d0f594…). O fator deste bloco é reestimado sem a turma de 2026,
para poder ser validado nela.

## 1. Modelos

**v2 (vigente).** log faturamento ~ log m² + log renda domiciliar + log pop + masters + estúdios; 39 maduras de 2025; nível de
2026 = + `cal['l_fat']`.

**Duas partes (UNI-09).** Balcão e agregador previstos separadamente com as variáveis da v2. O total é balcão + fator de aceite ×
agregador, mais o ajuste de nível k pelos valores ajustados.
- Calendário por parte, como no UNI-09: balcão −0,062; agregador +0,117.
- Fator de aceite: 1 / 1 − s_TP / s_TP / 0, com s_TP = 0,371 (`uni09/01_duas_partes.py`).
- LOO por reajuste explícito (deixa a unidade de fora e reajusta tudo, inclusive o k). Os números podem diferir um pouco do UNI-09
  (22,2% / 22,9%), que usou um k aproximado. Os dois são relatados.
- Teste das 18 com o aceite do cadastro, como no UNI-09. Nas demais avaliações, o aceite OBSERVADO na receita dos meses lidos
  (regra do UNI-09: aceita a fonte que tem receita em ≥ metade dos meses).

**Braços, aplicados nas duas famílias:**

| braço | na v2 | nas duas partes |
|---|---|---|
| **A** — masters com peso reduzido | ridge one-hot nas masters (M1, M2, M3, outras); λ na grade do UNI-13 por LOO, aninhado no c2 | o mesmo em cada parte, com λ por parte |
| **B** — mercado de agregador no lugar das masters | sem masters; + log parceiros de agregador por mil hab. e log(1 + independentes no agregador) | o mesmo nas duas partes |
| **C** — estúdio × renda | + estúdio × z(log renda domiciliar), z com média e desvio das 39 | só no balcão (como no plano) |
| **D** — tier do Wellhub na época | + log da receita por passagem do Wellhub na janela do desfecho | só no agregador (como no plano) |

Notas sobre o braço D:
- Receita por passagem = `fin_gympass ÷ passagens_gympass`, mediana dos meses com as duas > 0; alinhada no mesmo mês, como
  mediu a exploratória.
- Unidade sem Wellhub na janela fica com a previsão do modelo base.
- Relatada a correlação com o tier do cadastro.
- A receita por passagem pode cair quando o aluno usa mais (associação).

## 2. Amostras e desfechos (janela 2026-01..2026-08 fora do treino)

**Regras de desfecho, nesta ordem:**
1. **madura:** ≥ 3 meses válidos com mês de vida ≥ 12 → média do log do faturamento;
2. **jovem:** ≥ 3 meses válidos com mês de vida 6–11 → média de log(fat) − log(curva_p50), com a curva de faturamento do UNI-03;
3. **precoce (AVISO):** ≥ 2 meses válidos com mês de vida ≥ 3 → os últimos até 3 desses meses, ajustados pela mesma curva (com
   mês de vida > 12, fator 1).

O ajuste pela curva vem do regime com agregador. Por isso tende a inflar as unidades sem agregador, que sobem mais rápido.

**Conjuntos:**
- **Treino:** as 39.
- **Teste:** as 18 (UNI-02).
- **E (estimação do fator):** unidades fora do treino e **fora da turma de 2026**, com atributos e metragem. Metragem: a do
  UNI-02 nas 18; nas demais, oficial → time de expansão → satélite. Inclui a turma B e, com aviso, Rio Claro, Vicente Pires R8 e
  Boqueirão. Icaraí fica travada fora (UNI-13).
- **V (validação já, AVISO de leitura precoce):** turma de 2026 com previsão congelada em 30/09 (14 unidades), menos as 5 cegas,
  com desfecho por alguma das regras acima. A previsão da v2 é a congelada; a das duas partes e a dos braços usam a mesma
  metragem da turma (`previsao_2026/previsoes_turma_2026.csv`).
- **Turma B (exposta):** as 9 com metragem do time. Usada como validação dos braços e das duas partes; no fator, ela é estimação.

## 3. Perguntas e leituras

### P1 — fator sem agregador nos dois modelos (estimado em E)

- **v2:** θ_v2 = mediana(e_v2 | nenhum) − mediana(e_v2 | os dois).
- **Duas partes:** θ_2p é a mesma conta com e_2p. Na unidade "nenhum", a previsão das duas partes é só o balcão (fator 0), então
  θ_2p mede quanto o balcão real passa do balcão previsto.
- **σ por unidade "nenhum"** = 0,60 × (receita real − balcão previsto) ÷ agregador previsto: a fração de alunos de agregador que
  "voltou" pelo balcão. Teto 1 se fosse só substituição.
- Estratos e portões são os do UNI-13 (≥ 4 "nenhum", sinal estável, maduras/jovens com o mesmo sinal, curva `pagantes`), mais o
  estrato "sem as precoces".

### P2 — validação já, na turma de 2026 (V)

Erro de cada unidade e erro típico de cada modelo em V. Modelos comparados:
- v2;
- v2 × fator (θ_v2 nas "nenhum");
- duas partes (aceite observado);
- duas partes × fator (θ_2p nas "nenhum");
- os braços A–D das duas famílias.

Tabela por grupo de aceite. **Contraste dentro da turma:** Δ = mediana(e_v2 | nenhum) − mediana(e_v2 | os dois), com ≥ 3 em cada
grupo:
- confirma o fator se Δ ≥ θ_v2/2;
- refuta se Δ ≤ 0;
- no meio, inconclusivo.

É leitura **precoce e exposta** (a leitura de 29/09 já mostrou parte da turma), não confirmação. O erro da projeção pela curva é de
~9–21%.

### P3 — masters nos dois modelos

Para cada um dos 8 braços (A–D × duas famílias), contra a **v2**:
- **c2:** queda ≥ 2 pp no erro típico LOO das 39, com Holm de **k = 8** sobre o p do bootstrap pareado, α de família 0,05
  unilateral;
- **c3:** queda ≥ 2 pp no teste das 18, cru e recentrado;
- trava do metrô para os braços B (deixando um metrô de fora: não piora).

Relatados também, sem decidir:
- erro deixando um metrô de fora (por dobra);
- erro na turma B;
- erro em V;
- IC 90% das quedas;
- viés.

**"Melhora a precisão"** = c2 + c3 (+ trava). Os braços não se somam. As duas partes sem braço ficam como referência (UNI-09).

### P4 — antes e depois (eventos)

**Eventos.** Mudança na presença de passagens (Growth) de Wellhub ou TotalPass, com ≥ 3 meses no estado anterior. Datar pela
Growth, e não pelo Financeiro, porque o TotalPass só entra no Financeiro a partir de out/2023.

**Medidas.** Em log, relativas à mediana da rede madura no mesmo mês, sem a própria unidade:
- pagantes (Growth);
- balcão em R$ (Financeiro);
- alunos de agregador (Growth);
- faturamento total em R$ (Financeiro), só em evento com todos os meses ≥ 2023-10.

Em evento com mês de vida < 12, cada mês é ajustado pela curva do UNI-03 da série correspondente (pagantes, agregadores,
faturamento; o balcão em R$ pela de pagantes) e o evento fica marcado "na rampa".

**Antes/depois e placebo.**
- Antes = os 6 meses anteriores (≥ 3 válidos); depois = do 1º ao 6º mês seguinte (≥ 2 válidos e completos, até 2026-08). A
  diferença é depois − antes.
- Placebo: a mesma conta 6 meses antes, onde houver dado.

**Leitura por tipo de evento** (liga ou desliga × Wellhub ou TotalPass): mediana da diferença e n.
- Substituição esperada: ao **ligar** o agregador, o balcão cai; ao **desligar**, o balcão sobe.
- Descritivo, sem limiar.
- Os de set/2026 (Caxias, Vicente Pires R8, Laranjeiras) não têm "depois": só gráfico.
- Suzano não tem evento (as passagens não zeram): só gráfico.

## 4. Fluxo

Checagem seca → revisão adversarial (workflow, só leitura) → ensaio com ruído (todos os desfechos) → REGISTRO_PRE com SHA →
rodada.

**Saída.** OneDrive `07 - Validação ampliada`, com gráficos e planilha. O resultado é escrito em linguagem simples, uma resposta
por pergunta.

**Arquivos:**
- `uni14/01_validacao_ampliada.py`;
- `REGISTRO_PRE.txt`;
- `resultado_uni14.md`;
- `previsoes_turma_2026_uni14.csv`: previsões dos braços e do fator θ_v2/θ_2p para a turma, congeladas para o BLK-UNI-12.

## Emenda v1.1 (antes da rodada)

### Decisões do Felipe (06/10, perguntadas antes de rodar)

1. **Tier do Wellhub:** "os dois".
   - O **tier declarado no cadastro** (`wh_ord_ultra_cadastro`, conhecido antes de abrir) entra no critério como braço D.
   - O **R$ por passagem** do próprio período entra só como **diagnóstico** (D-diag), fora do Holm e do rótulo, porque a covariável sai
     da mesma receita que o modelo prevê.
   - Unidade sem tier declarado ("não possui") usa a previsão do modelo base, inclusive no treino.
   - O portão da Etapa 1(c) do plano (degraus de tier) fica dispensado: o tier vem do cadastro, e não datado pelos degraus.
2. **Braço B nos modelos separados:** rodam as **duas versões**.
   - **B só no agregador**, como no plano: o balcão mantém as masters.
   - **B nas duas partes.**
3. **Turma de 2026:** mostrada **sem veredito**.
   - Cada recorte recebe só a leitura "mesma direção do fator / direção contrária".
   - Recortes: todas; sem as 2 unidades de 2 meses (Laranjeiras e Ceilândia QNM24); sem quem mudou de aceite; curva de pagantes.

### Correções aplicadas (revisão adversarial)

**Ensaio.**
- No ensaio, P4 usa ruído PURO, sem valor real; o R$ por passagem também é ruído; o ensaio não imprime o resultado.
- **Registro de exposição:** o ensaio da v1.0 (06/10 15:09) usava o valor real × ruído pequeno no P4. As saídas foram **apagadas sem
  abrir**. No terminal só apareceram as primeiras 40 linhas do resultado de ensaio (P1 e P3, com ruído); o P4 nunca foi exibido.

**Fator e amostra (P1).**
- O fator só é aplicado e congelado se os portões do P1 passarem (como no UNI-13).
- Unidade que muda de aceite dentro da janela é marcada e lida à parte (P1 e P2).
- "Um só" sem fonte majoritária fica com a fonte de mais meses.
- Unidade sem regra de desfecho entra na lista "fora da conta" com o motivo, por exemplo **gama-df** (1 mês válido com mês de
  vida ≥ 3).

**Antes e depois (P4).**
- Usa o mês de vida com o fallback do mínimo: as 4 unidades com inauguração provisória entram como maduras.
- As 5 cegas ficam fora.
- O evento precisa persistir ≥ 2 meses.
- A data é conferida no Financeiro: "fora" se a fonte aparece lá ≥ 2 meses antes; o TotalPass só é conferível a partir de 2024.
- "Sensível" = data duvidosa ou volta em até 6 meses; o resumo sai com e sem os sensíveis, separado em rampa × madura, com o n e o
  placebo.
- A referência exclui as unidades em evento nos ±6 meses.
- O ajuste de rampa vale só para mês de vida < 12.
- Gráfico: há painel por unidade, série dos eventos de set/2026 (só o "antes") e painel de Suzano.

**Modelos e conjuntos (P2 e P3).**
- P2 traz todos os modelos por grupo de aceite e a leitura das duas famílias.
- P3: os braços dos modelos separados são comparados também contra os separados sem braço.
- P3 traz o erro por dobra da região não vista e a referência "v2 sem masters".

**Reprodução e congelamento.**
- Travas de reprodução do UNI-09: calendários, s_TP e teste das 18 dos separados = 22,9%.
- Peças da turma salvas sem k (k em coluna).
- Máscara explícita onde falta covariável.
- A v2 da turma é conferida nas 14.

**Itens descritivos do UNI-13 de volta.** Faixa por reamostragem, intervalo da menor à maior unidade, calendário alternativo,
conferência interna, sobra do balcão com premissa 0,47 e 0,60, RMSE em log, fonte da metragem e população abaixo do treino.

**Resultado em linguagem simples.** Explica como ler, com aviso de exposição no topo e uma resposta por pedido.

### Desvios declarados (do plano e do pedido)

- **Braço A:** o efeito aleatório de master não roda à parte, porque ridge one-hot nas masters é equivalente (variância fixada
  pelo λ).
- **Métrica secundária:** entra o RMSE em log.
- **Repetição do UNI-13:** os braços A e B da v2 repetem os do UNI-13. **O veredito do UNI-13 continua valendo**; este é
  complementar.
- **Holm** sobre os 9 braços do critério (v2: A, B, C, D; separados: A, B-agregador, B-duas, C, D), α de família 0,05 unilateral.
- **Detalhes de procedimento:** o s_TP fica fixo (das 39) dentro das dobras; o "depois" do placebo tem 5 meses.
- **"Turma de 2026"** = as 16 congeladas em 30/09 (não "todas as abertas em 2026"):
  - Rio Claro, Vicente Pires R8 e Boqueirão (jan–mar) estão na estimação;
  - Laranjeiras e Ceilândia QNM24 (abril), na validação.
- **Leitura da turma de 2026:** é **releitura de números já vistos** (leitura precoce de 29/09 nas 8; UNI-13 publicou o erro da v2
  em 4). Leitura confirmatória só existe nas 5 cegas, em 2027.
- **Antes e depois:** mede quase só TotalPass; o Wellhub "liga" fica para reler por volta de mar/2027. As entradas de TotalPass já
  foram vistas na Etapa 10 (alavancas), então é reexposição.
- **Incerteza da curva:** a incerteza "~9–21%" da v1.0 era da série de alunos. No faturamento, nos meses 3–5, a faixa vai de ~−34%
  a +22%.
