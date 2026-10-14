# BLK-UNI-15 — Melhorias nos três modelos (pré-registro)

Versão 1.0, 2026-10-06. Escrito ANTES de rodar. Só análise.

**O que o Felipe pediu (06/10, marcou as 4 opções):**
- região no lugar da master;
- treino ampliado;
- fator "sem agregador";
- preço, estúdio e tier com data (vai num bloco à parte, BLK-UNI-16, quando a coleta da Growth terminar);
- previsão em dois tempos.

Regra dele: os **três modelos lado a lado** — faturamento, balcão e agregador — mais o total recombinado onde couber.

## Modelos (iguais aos da ficha técnica)

- Regressão linear (OLS) no log.
- **Faturamento (F):** log do faturamento total.
- **Balcão (B):** log de vendas_ux − Tem Saúde.
- **Agregador (A):** log de Wellhub + TotalPass, normalizado pelo aceite do cadastro (UNI-09).
- **Total recombinado:** B + fator de aceite × A + k (UNI-09).
- **Variáveis da v2:** log m², log renda domiciliar, log população (isócrona de 10 min), masters, estúdio.
- **Calendário de 2026:** F −0,0205; B −0,0622; A +0,1172 (os mesmos de antes).

## Fato do dado (checado antes)

A master M1 é exatamente o grupo DF/GO: todas as unidades M1 são de DF ou GO, e todas as de DF/GO são M1. Treino: DF/GO 17, SP 15,
outros 7. Teste: DF/GO 6, SP 5, outros 7.

## T1 — Região no lugar da master (mesmo desenho 39/18 de sempre)

**Versões** (substituem as dummies de master):
- **R1:** DF/GO × fora (uma dummy).
- **R2:** DF/GO, SP e outros (duas dummies; referência DF/GO).

**Avaliação, em F, B, A e no total:**
- deixa-um-fora (LOO) nas 39;
- teste nas 18;
- região nova, em duas leituras:
  - erro típico deixando um metrô inteiro de fora, em todas as dobras;
  - **o mesmo sem a dobra de Brasília**, que não testa "praça nova" porque deixa a referência DF/GO com 1 unidade.

**Critério:** régua da bateria contra a mesma versão com masters.
- c2: queda ≥ 2 pp no erro típico LOO, com p do bootstrap pareado no Holm (k = 2 versões por modelo, α 0,05 unilateral);
- c3: queda ≥ 2 pp no teste, cru e recentrado.

## T2 — Treino ampliado

**Base ampliada:** as 39 (desfecho 2025) + as 18 do teste + as maduras da turma B (boa-vista-ba, ceilandia-qnm33-df, bangu-rj), com
desfecho de 2026. Fica em ~60 unidades, mais uma **dummy de ano 2026**.
- Metragem: como nas fichas. Na turma B é a do time de expansão (aproximada).
- Bangu e Botafogo não têm agregador: ficam fora do modelo A.

**Especificações:** com masters, R1 e R2.

**Avaliação justa** (mesmas unidades e sempre fora da amostra): **erro típico nas 57 unidades comuns** (39 + 18).
- Treino de 39: LOO nas 39 + teste nas 18.
- Treino ampliado: LOO nas 57.

**Também:**
- largura do IC 95% dos coeficientes (39 × 60);
- região nova, nos mesmos dois recortes do T1.

**Critério:** queda ≥ 2 pp no erro típico das 57, com o IC 90% da diferença (bootstrap pareado) abaixo de zero.

**Congelamento:** as previsões ampliadas da turma de 2026 são congeladas (BLK-UNI-12).

## T3 — Decisão de abrir sem agregador (F e B)

**Variável:** `sem_agregador` = 1 se a receita de agregador aparece em menos da metade dos meses do desfecho (regra do UNI-13/14).

**Base de estimação:** a ampliada do T2 + as unidades **jovens** com desfecho ajustado pela curva do UNI-03, com uma dummy de jovem.
- Jovens = fora do treino e da lista das 5 cegas, com ≥ 3 meses válidos com mês de vida entre 6 e 11 em jan–ago/2026.
- Curvas: F pela de faturamento; B pela de **pagantes**, porque não há curva de receita de balcão (aproximação declarada).
- Assim a base tem ~5 unidades sem agregador: Botafogo e Bangu maduras; Flow, Piçarras e Bertioga jovens.
- **Precoces ficam fora** desta estimação: dizem pouco sobre o nível maduro.

**Avaliação, em F e B** (LOO na base): com × sem a variável.
- erro típico nas unidades sem agregador;
- erro típico geral.

**Critério (plano:152-154):** o erro nas sem agregador cai ≥ 10 pp e o erro geral não piora mais que 0,5 pp.

**Congelamento:** F e B com a variável para as 5 cegas da turma (conferência em 2027).

**Exposição:** todas as unidades sem agregador da base já foram vistas (UNI-13/14). Isto é estimação; o juiz é a turma cega.

## T4 — Previsão em dois tempos (F, B, A)

**Unidades:** abertas dentro do painel que estão nas 39 ou nas 18, com:
- ≥ 2 meses válidos nos meses de vida 1–3 (**abertura**);
- ≥ 3 meses válidos nos meses de vida 12–18 (**maduro**).

**Medidas:** média do log de cada parte (F, B, A). A só com as unidades que tiveram agregador nas duas janelas (pela política de
abertura sem agregador, várias não têm).

**Especificações** (todas com dummy do ano em que a unidade amadureceu):
1. só a v2: o erro LOO/teste da v2 nessas unidades (referência);
2. só a abertura: log maduro ~ log abertura;
3. abertura + v2: log maduro ~ log abertura + previsão da v2 (em log).

**Avaliação:** erro típico LOO nas mesmas unidades.

**Critério:** (3) melhora sobre (1) se cai ≥ 2 pp com o IC 90% da diferença abaixo de zero. A especificação (2) é leitura.

**Uso:** só depois de abrir (alerta do mês 3), não na aprovação.

## Gerais

- **IC das diferenças:** bootstrap pareado sobre os erros já calculados, descritivo e sem reajuste.
- **Exposição:** as 39/18 foram muito consultadas.
- **Adoção:** nada é adotado sem o Felipe.
- **Fluxo:** checagem seca → revisão adversarial (workflow) → ensaio com ruído (todos os desfechos) → REGISTRO_PRE com SHA → rodada →
  verificação independente.
- **Saída:**
  - OneDrive `09 - Melhorias nos três modelos`;
  - `uni15/resultado_uni15.md`, em linguagem simples, com uma tabela por teste e os três modelos lado a lado.

## Emenda v1.1 (revisão adversarial `wf_80675178-156`, 22 achados confirmados; antes de rodar)

**Correções de fato.**
- Treino: DF/GO 17, **SP 16, outros 6** (a v1.0 dizia 15 e 7).
- O item "preço, estúdio e tier com data" foi aprovado e está em andamento como BLK-UNI-16. A coleta da Growth parou num 429 depois
  de 9 meses (jan–set/2023); retoma com uma tentativa só, mais tarde.

**T1.**
- Como M1 = DF/GO, a R1 é a v2 com M2, M3 e outras **fundidas numa só**: mede "precisamos de tantas masters?", não "região explica
  melhor que master". O texto diz isso.
- O efeito estimado de cada região (com faixa robusta HC3) sai nos três modelos.
- Sai a lista de quem muda de grupo, no teste e nas cegas.
- "Região nova não piora" é **mostrada, não é trava**.

**T2.**
- Entra o **total recombinado** (balcão + fator × agregador + k refeito em cada rodada). O total também é congelado.
- Comparação nas 57 também **recentrada por ano** e separada (39 / 18).
- Coeficiente da dummy de 2026 ao lado da calibração de calendário. A dummy mistura ano, coorte e janela.
- Região nova medida **nas mesmas 39 unidades** nos dois treinos, com e sem Brasília.
- Faixa robusta (HC3) dos coeficientes principais, 39 × 60. R² nas mesmas 57.
- Holm por modelo, k = 3.
- Leitura descritiva sem Botafogo e Bangu, e com a variável "sem agregador": coeficientes de M3/região e previsão de Belford Roxo e
  Bonsucesso.

**T3.**
- Rótulo: **"conferência interna (não é teste); quem julga são as 5 cegas em 2027"**.
- O critério difere do plano:152-154: o plano lia o subgrupo na turma B + turma 2026 e pedia IC de σ.
- Duas leituras:
  - sem precoces (como a v1.0);
  - **com as precoces, com aviso** (decisão do Felipe para as unidades jovens).
- Leituras de robustez: sem RJ, só maduras, só jovens, sinal tirando cada uma, e faturamento das jovens sem agregador pela curva de
  pagantes.
- Efeito com faixa por reamostragem com reajuste. Paralelo com o +35% / +115% do UNI-14.
- Lista "fora da conta" com o motivo. Icaraí fica travada por nome.

**T4.**
- Regra do TotalPass no Financeiro: meses com passagens de TotalPass e sem a linha de TotalPass não entram no faturamento nem no
  agregador.
- Duas referências:
  - "v2 como está" (erro direto);
  - "v2 ajustada ao maduro" (é a régua do critério).
- No agregador, a previsão da v2 das 39 recebe o fator de aceite.
- **Aviso escrito:** medido em unidades que abriram COM agregador (45 de 47). Não vale ainda para quem abre sem agregador.
- Mínimo de 10 unidades por modelo; n por modelo. A dummy de 2026 coincide com as 18 do teste. Vazamento de segunda ordem declarado.

**Textos.**
- O resultado começa por "como ler", aviso de exposição e "nada adotado", e traz uma frase por teste com os três modelos e o total.
- Rótulo "passa / não passa na checagem do estudo", com a régua de cada teste por escrito.
- R² e n nas tabelas; aba RESSALVAS; por que 90%.

**Execução.**
- O ensaio põe ruído só onde o valor é > 0 (preserva zeros).
- Travas do --rodar nos n do T2, T3 e T4.
- Gráficos e planilha antes do congelamento.
- Colunas congeladas sem espaço, na escala declarada, com k, fator e s_tp.

### Detalhes de execução (v1.1, fixados antes do REGISTRO_PRE)

- **Faixas:** todas de 90% (a pergunta é de um lado só: "o novo erra menos?"). Coeficientes: faixa robusta (HC3). Efeito no total e no T3:
  2.000 reamostragens das unidades com reajuste.
- **T1, efeito no total:** média nas 39 de (total previsto com o grupo − total previsto como DF/GO).
- **T2, checagem:** queda ≥ 2 pontos nas 57 e Holm (k = 3 por modelo, 5% de um lado). Sem o nível do ano é leitura: se o ganho sumir nela, o
  texto avisa. Total refeito em cada rodada com fator do cadastro (Botafogo e Bangu têm fator 0 no cadastro).
- **T3:**
  - Candidatas = fora do treino, do teste, da turma B e das cegas.
  - Idade:
    - jovem = ≥ 3 meses válidos com mês de vida 6–11 em jan–ago/2026;
    - precoce = senão, ≥ 2 meses válidos com mês de vida ≥ 3 (os 3 últimos).
  - Saem com o motivo escrito:
    - balcão ≤ 0 na janela;
    - falta de master, renda, população, estúdio ou metragem;
    - Icaraí, travada por nome.
  - Recortes:
    - sem RJ;
    - só maduras;
    - só jovens/precoces (tira Botafogo e Bangu);
    - faturamento das novas sem agregador pela curva de pagantes;
    - tirando cada uma.
- **T4:**
  - Regra do TotalPass (faturamento e agregador): sai o mês com passagens ou alunos de TotalPass > 0 e receita de TotalPass vazia ou zero.
  - Ano do maduro = mediana dos meses 12–18. Ano com menos de 3 unidades se junta ao seguinte (o último, ao anterior).
  - Checagem: queda ≥ 2 pontos e p ≤ 5% (1 comparação por modelo).
  - Leitura extra: sem as unidades que tiveram agregador em menos da metade dos meses 1–3.
- **Contagens da seca (travas do --rodar):**
  - T2: 60 / 60 / 58.
  - T3 sem precoces, sem agregador: Botafogo, Bangu, Flow, Piçarras, Bertioga.
  - T4: faturamento 42, balcão 47, agregador 40.
