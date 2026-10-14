# BLK-UNI-09 — Faturamento em duas partes: balcão + agregador (pré-registro)

Versão 1.0, 2026-10-05. Escrito **antes de ajustar qualquer modelo por parte**. Só análise; READ-ONLY sobre o M1.

## 1. Pergunta e decisão do dono

Somar um modelo de faturamento de **balcão** e um de **agregador** prevê o faturamento total melhor que a v2?

- **Decisão do Felipe (05/10):** o alvo é o faturamento por tipo, não o volume. São duas partes, balcão e agregador,
  com Wellhub e TotalPass juntos.
- **Motivo:**
  - a soma das partes é o próprio alvo da viabilidade;
  - o Financeiro é a fonte limpa;
  - prever volume obrigaria a modelar o ticket, e a divisão alunos × ticket de 28/09 piorou o modelo;
  - a contagem de aluno de agregador é ruidosa: R$ 46 a R$ 89 por "aluno" Wellhub (p10–p90).

A v2 é: log faturamento ~ log m² + log renda domiciliar (isócrona de 10 min) + log pop + masters + estúdios. Nas 39
maduras de 2025 dá R² LOO de 0,264 e erro de 22,1% nas 18 do teste (UNI-02, já consultadas).

## 2. Dados (conferidos sem ajustar modelo por parte)

- **Financeiro**, fechamento mensal: faturamento = vendas_ux + gympass + totalpass − tem_saude. Bate com o faturamento
  da v2 em **100% dos meses** (408 no treino, 115 no teste; |dif| ≤ 1%).
- **B (balcão)** = vendas_ux − tem_saude. **A (agregador)** = gympass + totalpass.
- **Mesmas unidades, meses e filtros da v2:** meses válidos com ≥ 12 meses de vida e ≥ 3 meses; 2025 no treino
  (39) e jan–ago/2026 no teste (18). O desfecho de cada parte é a média mensal do log, como o da v2.
- Na receita bruta das maduras de 2025 (mediana): **balcão 74%, Wellhub 16%, TotalPass 8%**.
- **Aceite** (cadastro da VPS, foto de ago/2026; `wh_tem_agregador_cadastro`, `tp_tem_agregador_cadastro`):

  | conjunto | sem Wellhub | sem TotalPass | ausente |
  |---|---|---|---|
  | treino (39) | 0 | 2 | 0 |
  | teste (18) | 1 | 3 | 0 |
  | turma de 2026 (16) | 9 | 11 | 2 |

  O cadastro bate com a receita em 39 de 39 no treino. No teste há uma divergência: uma unidade "sem TotalPass" no
  cadastro teve receita de TotalPass na janela. Nenhuma unidade do treino deixa de ter receita de agregador; no teste,
  uma.

## 3. Modelos (OLS em log, nas 39)

- **Balcão:** Y_B ~ as covariáveis da v2.
- **Agregador:** Y_A* ~ as covariáveis da v2, em que A* é a receita **normalizada para "aceita os dois"**:
  - nas unidades sem TotalPass, A* = A / (1 − s_TP);
  - s_TP = mediana da participação do TotalPass na receita de agregador, entre as unidades do treino que aceitam os
    dois.
- **Previsão do total:** exp(p_B) + fator × exp(p_A*), com o fator pelo aceite no cadastro:
  - 1 se aceita os dois; 1 − s_TP se só Wellhub; s_TP se só TotalPass; 0 se nenhum;
  - aceite ausente no cadastro = aceita os dois (o padrão da rede), sinalizado.
- **Agregação:** p_total = log(soma) + k, em que k = média no treino de [Y_total − log(exp(Y_B) + exp(Y_A))]. O k
  corrige a diferença entre "média do log das partes" e "log do total" e é calculado sem modelo; no LOO, sem a própria
  unidade.
- **Teste (18):** as partes ajustadas nas 39 recebem a **calibração de calendário de cada parte**: a mediana de
  Y_2026 − Y_2025 nas maduras presentes nos dois anos, a mesma regra da v2.

## 4. Critério (régua do §4.1 da bateria)

- **c2:** o erro típico LOO do total nas 39 cai **≥ 2 pp** contra a v2.
- **c3:** o erro típico nas 18 do teste cai **≥ 2 pp**, **cru e recentrado**.
- **Rótulos:**
  - "MELHORA A PRECISÃO" = c2 + c3 cru + c3 recentrado;
  - "CANDIDATA (o c3 só passa por nível)" = c2 + c3 cru;
  - "CANDIDATA" = c2 sem o c3, ou c3 (cru e recentrado) com o LOO sem piorar;
  - "NÃO MELHORA" = os demais.
- Erro típico = mediana de |exp(e) − 1|. Bootstrap pareado (2.000) para o IC 90% das quedas.
- **Expectativa declarada antes de rodar:** nas 39 todas aceitam agregador (37 aceitam os dois), então as duas partes
  devem ficar perto da v2 no LOO. **O valor estrutural do modelo está no aceite**, que a v2 ignora, e ele só é testado
  de verdade na **turma de 2026** (9 sem Wellhub). No teste, só 1 unidade não tem agregador.
- **A adoção é decisão do Felipe**, com o resultado na mão.

## 5. Diagnósticos (descritivos, não decidem)

- Coeficientes de cada parte, com IC 90% HC3: masters, estúdios, renda, m² e população. Principal pergunta: **a
  master de RJ/SP tem sinais opostos no balcão e no agregador?**
- R² LOO de cada parte.
- **Volume** (mecanismo): as mesmas especificações em log de pagantes (balcão) e log de alunos de agregador (contagem
  da Growth, ruidosa).
- Erro do teste separado entre as unidades que aceitam os dois e as demais.

## 6. Sensibilidades (descritivas)

- Agregador + escritórios a pé (`poi_F1`), o único candidato que chegou perto na Etapa 11.
- Agregador + oferta de parceiros na isócrona: log(1 + Wellhub) e log(1 + TotalPass) (`wh_n_conc_c10`,
  `tp_n_conc_c10`).
- **Sem o aceite** (fator 1 para todos), para isolar quanto vem do aceite.
- Correção de Duan por parte no lugar do k.
- Tem Saúde descontado do agregador, em vez do balcão.

## 7. Turma de 2026 (a palavra final)

São congeladas, com SHA-256 no REGISTRO e sem sobrescrever:
- a previsão das duas partes **com o aceite**;
- a previsão das duas partes **sem o aceite**;
- a v2 domiciliar já congelada (SHA 999bd027…).

**Conferência:** junto com o BLK-UNI-12, quando ≥ 10 das 16 tiverem 12 meses de vida e ≥ 3 meses válidos. Métrica: erro
típico das duas partes contra a v2, **no total e nas unidades sem agregador**.

## 8. Exposição anterior (conferida no caderno)

- **Etapa 7 (28/09):** "duas partes" = **alunos × ticket**, uma divisão diferente; piorou o R² de 0,30 para 0,27.
- **Etapa 11 (29/09):** a **proporção** de agregador, na receita e no volume, foi cruzada com variáveis da praça.
  Nenhuma se confirmou nas novas; a proporção se separa por estado.
- **Caso Manaus (30/09):** efeito da master de RJ/SP em ativos (+0,315) e em pagantes (−0,466), em volume.
- As 18 do teste já foram consultadas (UNI-02).
- **Nunca foi ajustado:** modelos de receita de balcão e de agregador separados, nem a soma deles com o aceite.

## 9. Limites

- **Substituição:** se a unidade não aceita agregador, parte desses alunos pode entrar pelo balcão. No treino todas
  aceitam, então isso **não é estimável**. O modelo supõe que não há substituição, e a turma decide.
- **O aceite é a foto do cadastro de ago/2026**, não a data de abertura. Há 1 divergência no teste.
- A receita de agregador depende do tier e do repasse por visita, que mudam com o tempo.
- N = 39 com ~9 parâmetros por parte: a soma de dois modelos tem mais variância que um.

## 10. Arquivos e congelamento

- Script: `uni09/01_duas_partes.py` (`--seco`, `--ensaio`, real).
- Resultado: `uni09/resultado_uni09.md`.
- Turma: `uni09/previsoes_turma_2026_duas_partes.csv`.
- REGISTRO: `uni09/REGISTRO_CONGELAMENTO.txt`, com o SHA-256 do protocolo, do script e dos insumos, antes de rodar.
- Revisão adversarial antes de rodar; as correções entram como emenda versionada.

## 11. Emenda v1.1 (2026-10-05): revisão adversarial e decisão do dono, ANTES de rodar

Revisão de 3 lentes (estatística, dados, protocolo), cada uma com um cético; só leitura e sem ajustar o modelo por
parte. Ficaram 3 graves e cerca de 20 menores. Tudo abaixo foi decidido sem nenhum resultado das duas partes.

**1. Aceite da turma (grave): decisão do Felipe, "misto / não sei".**
- A foto do cadastro (06/08/2026) mede, na maior parte, **credenciamento em andamento**:
  - 8 das 9 unidades da turma "sem agregador" tinham aberto 10 dias a 4 meses antes da foto;
  - 60 de 61 unidades abertas até ago/2025 aceitam Wellhub;
  - o RJ começou a aceitar Wellhub em set/2026.
- **Regra principal da conferência:** o fator usa o **aceite observado na receita da janela de avaliação**, por fonte.
  Aceita uma fonte quem tem receita dela em ≥ metade dos meses da janela.
  - Unidade que muda de aceite dentro da janela é sinalizada e lida à parte.
  - A foto do cadastro vira **leitura secundária**.
- Para isso, a turma congela **as peças por unidade**: log do balcão e do agregador ("aceita os dois") no nível de 2025,
  log da v2 em 2025, k, s_TP, calibrações de 2026 e o fator do cadastro.
- **A conferência recombina** com o aceite observado e o calendário **do ano conferido, por parte** (mediana Y_ano −
  Y_2025 nas maduras com aceite estável), como manda o protocolo da previsão de 2026.
- Congeladas também, como referência: a versão neutra (fator 1), a do cadastro **sem substituição** (limite inferior) e
  a do cadastro **com substituição total**. Na substituição total, o aluno perdido do agregador vira balcão; um aluno de
  agregador rende ~60% de um de balcão (premissa do BLK-UNI-09/simulador), então a receita perdida volta ÷ 0,60.
- **Conferência:** junto com o BLK-UNI-12, quando ≥ 10 das 14 com covariáveis tiverem 12 meses de vida e ≥ 3 meses
  válidos.
  - Decide o erro típico do total (duas partes com o aceite observado contra a v2 congelada; queda ≥ 2 pp).
  - O viés no grupo "sem agregador observado" é descritivo e só é lido com n ≥ 4.
  - Com ~14 unidades, a conferência só pega diferenças grandes de erro.

**2. Exposição da turma.** A turma **não é cega**: a leitura precoce de 29/09 (`previsao_2026/leitura_precoce.md`) já
projetou o nível maduro de 11 das 16 unidades. As de fator 0 no cadastro ficaram **acima** da previsão; as que aceitam os
dois, abaixo. Leitura confirmatória "cega": só as 5 unidades abertas a partir de jun/2026 (belford-roxo, novo-gama,
paulinia, domingos-ferreira e bonsucesso). As 14 entram como leitura com exposição parcial.

**3. O que o c2/c3 testam.** Nas 39 e nas 18 o aceite quase não varia: no treino só 2 unidades com fator 0,629, e no
teste 3 de 18 com fator ≠ 1. Portanto **c2/c3 testam a decomposição** (duas formas log-lineares e o calendário por
parte), não o aceite. O rótulo diz isso. A tabela por grupo de aceite no teste é descritiva, com o n.

**4. Rótulos (desvio declarado do §4.1 da bateria):** aqui não há c1 (não é teste de variável). O caminho "CANDIDATA"
pelo c2 passa a exigir que o teste não piore (simétrico ao caminho pelo c3). Os IC de bootstrap são condicionais aos
ajustes, descritivos e sem papel de critério.

**5. Correções técnicas:**
- **k pelos valores ajustados:** k = média de [Y_total − log(exp(p̂_B) + fator × exp(p̂_A*))], sem a própria unidade no
  LOO. Zera o resíduo médio no nível, como na v2. A variante de Duan sai: mira a média, não a mediana, e vazava a unidade
  do LOO.
- **"Sem aceite"** = o mesmo ajuste, com fator 1 só na previsão (igual à turma). O ajuste sem normalizar o agregador
  vira outra sensibilidade, com outro nome.
- **Y_A** usa só os meses com receita de agregador > 0, com mínimo de 3 meses. Nas 39, nenhum mês tem A = 0; o mínimo
  de meses com A é 4.
- **Calibração por parte** só com maduras de aceite estável nos dois anos: 39 de 39 (balcão −0,062; agregador
  +0,117; total −0,020).
- **Sensibilidades novas:** calendário único (o do total) nas duas partes; s_TP fora de SP (0,270, contra 0,371 no
  país) para quem não aceita TotalPass; agregador + tier Wellhub do cadastro (ordinal, foto ago/2026).
- **Sensibilidade com escritórios a pé:** roda nas 38 unidades que têm o dado (lago-sul-df não tem), com a v2 também
  nas 38.
- **Execução:** cada sensibilidade é isolada; uma falha é registrada na tabela e não derruba a rodada.
- **Ensaio:** todo desfecho real sai antes do ruído (havia vazamento do log de pagantes). Na rodada real, o log de
  pagantes do diagnóstico é o de `partes()`, com os mesmos filtros.
- **Trava nova:** a turma remontada reproduz a v2 congelada (diferença máxima de 0,03%).
- **REGISTRO:** passa a incluir o painel de KPIs (exigido no import), `dimensionamento/config.py`, `simulador.py` e
  `viabilidade_ponto.py`. Sai o `uni03` (não é importado). A docstring declara a leitura do `LOCAL_demanda_totalpass`
  (não gravado em saída).

**6. Limites que ficam declarados:**
- **"Com aceite" do cadastro = limite inferior:** supõe substituição zero; usa a calibração do balcão (−6,2%, mais
  pessimista que a do total); usa um mr_M3 estimado só com SP, que aceita agregador; e usa um s_TP nacional.
- **Parceiros na isócrona** (`wh/tp_n_conc_c10`) são foto de set/2026, posterior ao desfecho do treino: a leitura é de
  associação.
- **Calendário por parte × total:** com 37% de agregador, a calibração por parte dá ~+2,4 pp a mais que a do total; com
  15%, ~−1,5 pp. A sensibilidade de calendário único mostra quanto do c3 vem disso.

**7. Exposição anterior que faltava no §8:**
- **Etapa 10 (29/09):** "aceitar ou não agregador" já foi discutido. Faixa −25%/+27% conforme a substituição, e o caso
  Botafogo (única unidade do teste com fator 0).
- **Etapa 7:** além da piora do M1, a variante M3 passou na régua por 0,003, atribuída depois a ruído do termo de
  política do estado.
- Renda e população nas duas partes, e a master com sinais opostos, já eram conhecidas da Etapa 11 e do caso Manaus.

**8. Escopo contra o backlog.** O BLK-UNI-09 do backlog previa **volume**, com agregador ~ mercado + aceite/tier +
mix por estado. A troca para **faturamento por tipo** é decisão do Felipe (05/10). O mercado e o tier do agregador
ficaram como sensibilidades, e o mix por estado é absorvido pelas masters. São escolhas do analista, declaradas aqui.
