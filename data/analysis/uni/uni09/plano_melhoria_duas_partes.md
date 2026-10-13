# Plano para melhorar os modelos de balcão e agregador (BLK-UNI-09, 06/10/2026)

Levantamento de 3 frentes (balcão, agregador, estrutura) + crítico, só leitura. **É insumo, não decisão:** a
ordem de execução e a adoção são do Felipe, e nenhuma etapa de modelo roda antes da exploratória revisada por ele.

Conferido no dado em 06/10 (antes de gravar): `passagens_gympass/totalpass`, `novos_alunos`, `cancelados` e `visitas`
com 2.275/2.275 linhas no painel; `precos/` só tem o script (o parquet de vendas nunca foi gerado); 16 unidades
abertas até abr/2026 sem m² em nenhuma fonte; bangu, icarai, flow e picarras sem receita de agregador em nenhum mês
(boa-vista com Wellhub em 6 de 25); estúdio × renda, ridge e efeito aleatório nunca rodados (grep sem ocorrência).
As demais citações vêm dos agentes e precisam ser conferidas antes de usar como fato.

## Ordem proposta

### Etapa 1: exploratória por parte com as séries que nunca entraram no estudo (balcão da abertura, captação × retenção, passagens e idade do credenciamento)

Propostas: balcao-4, balcao-5, agregador-6, agregador-7

**Por quê.** É o próximo passo que o Felipe fixou em 06/10 ("análise exploratória antes de qualquer modelo novo", tasks/backlog.md:5802-5804). É também o mais barato, porque tudo já está no painel.
- O balcão, 74% da receita, já está em 91% do maduro no mês 0 e em 89% no mês 3; o agregador, em 53% e 64% (uni03/resultado_uni03.md:12,15). Mas o alerta do mês k só foi medido em ativos totais (uni03/resultado_uni03.md:57-61).
- `passagens_gympass` e `passagens_totalpass` têm 2275/2275 linhas (DICIONARIO_UNI00.md:23-24) e, no grep, só aparecem em 05_cobertura_dicionario.py:66. A receita por passagem data as trocas de tier, que é a razão nova que falta à pista do tier: hoje ela é foto de 06/08/2026 (DICIONARIO_UNI00.md:244-247) e piora o recentrado em 1,0 pp (uni09/resultado_uni09.md:45).
- Visitas, novos alunos, cancelados e churn (DICIONARIO_UNI00.md:18-22,48) nunca foram decompostos.

Ganho direto: nenhum. O que a etapa dá: mostra onde está o volume que falta, decide qual dado novo coletar (pré-venda × ponto × retenção) e libera o braço D da Etapa 2.

**Como testar.** Só descritivo: sem ajustar regressão de faturamento e sem cruzar variável candidata com o resíduo da v2 (isso viraria forking da Etapa 2). Molde de saída: exploratoria/01_balcao_agregador.py (gráficos + planilha, sem Base Consolidada nem LOCAL_). Quatro peças:
- (a) Persistência: desvio do balcão nos meses 0 e 1 contra a previsão da parte balcão do UNI-09, comparado ao desvio do balcão maduro. Unidades: 30 das 39 com mês 0 observado + 18 do teste.
- (b) Captação × retenção do balcão nas maduras de 2025: pagantes ≈ novos_alunos ÷ churn. Antes, confirmar com a Growth se novos_alunos e vendas incluem reativação.
- (c) Série mensal de fin_gympass ÷ passagens_gympass e de fin_totalpass ÷ passagens_totalpass por unidade, com os degraus datados. Validar contra as 10 unidades com tier TotalPass divergente entre cadastro e feed (tasks/backlog.md:6207-6209).
- (d) Data do credenciamento = 1º mês com passagens > 0, por fonte.

Temporada de inauguração: NÃO cruzar aqui; fica como candidata para a turma.

**Critério.** Regras de leitura escritas antes de rodar (não é teste de precisão):
- (a) Spearman entre o desvio do balcão no mês 1 e o desvio maduro ≥ 0,5 → "balcão fixado na abertura" → prioridade ao dado de pré-venda (BLK-UNI-PEND-01) e ao plano de pré-venda como coleta nova.
- (b) Se a captação responder por ≥ 2/3 da variância do log de pagantes entre as maduras → ponto/pré-venda; se o churn responder → Lifetime.
- (c) O histórico de tier só vai para a Etapa 2 se os degraus da receita por passagem casarem com a troca de tier em ≥ 7 das 10 unidades divergentes. Se não casarem, o braço do tier é descartado (não se refaz com a foto).
- (d) A idade do credenciamento vira coluna do painel.

**Dependências.** Nenhum dado novo; só o painel local. Uma pergunta à Growth: a definição de novos_alunos e vendas. Um script por vez. Já decidido pelo Felipe (backlog:5802).

### Etapa 2: uma família pré-registrada sem dado novo — encolher as masters, trocar masters por mercado de agregador, estúdio × renda no balcão e tier vigente no agregador

Propostas: estrutura-9, estrutura-3, agregador-4, balcao-1, agregador-1

**Por quê.** São os candidatos de ganho direto mais baratos.
- (A) As masters se ajustam demais à amostra:
  - a master real sozinha leva o teste de 21,5% a 31,0% (CADERNO_ESTUDO_UNI.md:565);
  - o mr_M3 vem só de SP (uni09/resultado_uni09.md:32);
  - na parte agregador, as masters valem +0,76 a +0,98 em log (resultado_uni09.md:27-29);
  - tirar uma unidade do treino move o teste de 22% para 27% (CADERNO:1183-1187).
  Ridge ou efeito aleatório nunca foram usados (grep sem ocorrência). O Huber não encolhe coeficientes (CADERNO:472-474).
- (B) A única sensibilidade do agregador que melhorou também o recentrado foi a de parceiros na isócrona: teste +1,8 pp, recentrado +1,0 pp (resultado_uni09.md:44).
- (C) Estúdio × renda é a hipótese principal do BLK-UNI-08 e nunca foi rodada (tasks/backlog.md:5739-5742). As 4 unidades acima do teto da faixa têm estúdio (CADERNO:821-822). Mas o treino não tem desvio por estúdio (−6% × −4%, backlog:5730), então é improvável que passe no c2.
- (D) O tier ganha 2,7 pp no LOO e 2,1 pp no teste, mas piora o recentrado em 1,0 pp (resultado_uni09.md:45). Refazer com a foto daria a mesma resposta; ele só volta com o tier vigente da Etapa 1.

A régua de hoje não enxerga 1–2 pp: o IC da queda no teste vai de −9,8 a +2,9 pp (resultado_uni09.md:8). Por isso a métrica com mais poder (estrutura-9) entra aqui, pré-registrada como secundária.

**Como testar.** Um protocolo, revisado de forma adversarial e congelado com SHA antes de rodar. Braços:
- A) v2 e duas partes com efeito aleatório de master (partial pooling) e com ridge, λ escolhido por LOO aninhado.
- B) Na parte agregador, as masters saem e entram: log de parceiros Wellhub + TotalPass por mil hab. e log(1 + independentes no agregador) (DICIONARIO_UNI00.md:221,235,138). Avaliado também deixando um metrô inteiro de fora.
- C) studios × z(log renda domiciliar) só no balcão, numa forma única. A interação com coorte fica de fora, porque surgiu de olhar o teste.
- D) Tier Wellhub vigente na janela, na parte agregador. Só roda se a Etapa 1 aprovar o histórico.

Amostra: LOO nas 39 + teste nas 18, com calibração de calendário por parte. Secundárias: erro quadrático médio em log e deixando um metrô de fora.

Turma de 2026: congelar com SHA as previsões de cada braço. A leitura cega vale só para as 5 abertas a partir de jun/2026 (uni09/protocolo_uni09.md:151-154).

**Critério.** Por braço, a régua do §4.1 (bateria/protocolo_bateria.md:78-91, 284-286):
- c2: o erro típico LOO das 39 cai ≥ 2 pp;
- c3: o erro típico nas 18 cai ≥ 2 pp, cru e recentrado.

Travas extras:
- com vários braços, a queda do c2 também precisa de IC 90% (bootstrap pareado) abaixo de zero depois de Holm, com k = nº de braços que rodarem;
- o braço B não pode piorar o erro deixando um metrô de fora.

Se nada passar, a v2 fica. A métrica secundária só informa. A adoção é do Felipe.

**Dependências.** - A Etapa 1, só para o braço D.
- Decisão do Felipe antes de rodar: os braços A e B mudam a forma como a master entra na v2 adotada (CADERNO:577-580), e ele precisa aceitar a métrica secundária.
- Parceiros e independentes são foto de set/2026, então a leitura é de associação (protocolo_uni09.md:189-190).
- Sem Base Consolidada.

### Etapa 3: ampliar o N e ganhar um juiz antes de 2027 — metragem das 16 sem m², auditoria cega, desfecho de painel e reajuste nas 57+

Propostas: estrutura-6, balcao-9, estrutura-7, estrutura-2, estrutura-1

**Por quê.** O gargalo é a amostra, não a variável.
- 16 unidades abertas até abr/2026 estão fora de todo modelo por falta de m² (conferido: 12 com ≥ 5 meses de mês de vida ≥ 6; meses maduros: boa-vista-ba 13, ceilandia-qnm33 4, bangu 3). É o item 4 do BLK-DADOS-UNI-01 (tasks/backlog.md:6191-6193).
- Quatro delas não tiveram receita de agregador em nenhum mês (conferido em fin_gympass e fin_totalpass: bangu-rj 15 meses, icarai-rj 13, flow-pr 11, picarras-sc 11). boa-vista-ba teve Wellhub em só 6 de 25 meses. Hoje o treino não tem nenhuma unidade sem agregador (protocolo_uni09.md:32), então são elas que permitem a Etapa 4.
- A metragem por satélite erra 20%, sobretudo na contagem de andares (CADERNO:362-364). Butantã (+90%) usa satélite (uni02/resultado_uni02.md:50). Cotia tem 750 m² na planilha e ~1.050 medidos (CADERNO:367).
- O desfecho de painel já existe como Sensibilidade A (55 unidades; uni01/resultado_uni01.md:8), mas nunca foi desfecho de treino.
- A v2 nunca foi reajustada nas 57. O UNI-07 e a bateria só juntam resíduos, e a regra do epic pede rolling-origin (tasks/backlog.md:5283-5284).

Ganho direto pela variância dos coeficientes: ~0,5–0,7 pp. O ganho real é um juiz de ~12 unidades quase cegas meses antes da turma de 2026.

**Como testar.** 1. Pedir já a área útil e o nº de pavimentos ocupados das 16 + Cotia, com a definição escrita antes.
2. Re-medir às cegas, por planta ou contrato, TODAS as unidades do teste e da turma, sem o desfecho à vista.
3. Aplicar a todos os alvos (inclusive os que o modelo acerta) um checklist fixado antes: m², pino, isócrona < 31 km², meses com R$ 0 e Guarujá. Corrigir só erro provado (regra 4, tasks/backlog.md:5287).
4. Quando a metragem chegar, congelar com SHA as previsões da v2 e dos braços da Etapa 2 para a "turma B", ANTES de abrir o desfecho delas.
5. Desfecho de painel: log fat = α_i + mês-calendário + faixa de maturidade. α_i entra pesado pela incerteza; turma B e turma de 2026 lidas com mês de vida ≥ 6.
6. Reajuste nas 57 + turma B com efeito fixo de ano, validado deixando de fora uma turma de abertura (várias origens) e um metrô.

**Critério.** Dado: definição de área útil fixada antes e correção só de erro provado.

Modelo: o reajuste substitui a v2 só se:
- deixando uma turma de abertura de fora (pré-registrado), o erro em log não piorar;
- na turma B congelada (n ≥ 10), o erro típico cair ≥ 2 pp, cru e recentrado.

A régua das 39/18 continua sendo reportada, mas deixa de ser o juiz, porque as 18 entram no treino.

**Dependências.** - Terceiros (franqueado/operação) para metragem e plantas. Em shopping, a área pode vir como ABL; registrar.
- Se a fonte for a Base Consolidada: só leitura local pelo Felipe, sem subagentes, derivados LOCAL_.
- Decisão do Felipe, antes de rodar o reajuste: trocar o juiz (18 → turma B + turma de 2026).
- A turma de 2026 fica congelada e intocada.
- O pedido de metragem sai já, em paralelo às Etapas 1 e 2: é o caminho crítico.

### Etapa 4: aceite de agregador como alavanca medida — estimar a substituição pelo balcão (σ) em vez de supor zero

Propostas: balcao-3, agregador-2, estrutura-4

**Por quê.** Aqui estão os maiores erros de uma vez.
- Nas 3 unidades do teste que não aceitam algum agregador, a soma sem substituição erra 82,5%, contra 68,0% da v2, por prever de menos (uni09/resultado_uni09.md:17-18; CADERNO:1326-1331).
- Botafogo fatura R$ 697 mil, contra R$ 245 mil previstos (uni02/resultado_uni02.md:52). Laranjeiras está +134% na leitura precoce (previsao_2026/leitura_precoce.md:17).
- Hoje "sem agregador" entra na v2 só como faixa de −25% a +27% (CADERNO:537-538).

O UNI-09 mostrou que separar as partes não ganha do total onde a unidade aceita os dois. Por isso a estrutura certa é total = v2 × [(1 − a) + σ·a/0,60]: idêntica à v2 onde aceita os dois, diferente só onde não aceita.

Razões novas:
- a Etapa 3 traz 4 unidades sem receita de agregador em 11–15 meses e boa-vista com saída do Wellhub;
- o RJ passou a aceitar Wellhub em set/2026 (CADERNO:540-541).

A tentativa anterior deu σ degenerado (9,79 [−22; +27]) porque media a entrada de um 2º agregador (alavancas/resultado_alavancas.md:107-109). A substituição entre agregadores (θ) nunca foi estimada.

**Como testar.** Pré-registro antes de abrir as unidades novas.

Aceite pelo que aparece na receita: a unidade aceita uma fonte se tem receita dela em ≥ metade dos meses (protocolo_uni09.md:135-137).

σ por dois braços:
- (a) Transversal: unidades sem agregador observado e com mês de vida ≥ 6 (Botafogo + bangu, icarai, flow e picarras + boa-vista; desfecho de painel da Etapa 3), contra a v2 sem fator.
- (b) Eventos na mesma unidade, lidos no balcão (receita e pagantes), contra as outras unidades no mesmo mês, com placebo 6 meses antes:
  - boa-vista-ba, saída do Wellhub em 2025-03;
  - campo-largo-pr, saída do TotalPass em 2026-05 (alavancas/resultado_alavancas.md:116-118);
  - Suzano, agregadores de 2.964 para 919 (tasks/backlog.md:6213-6215); antes, conferir se é saída;
  - RJ com Wellhub desde set/2026.

θ só é estimado se houver ≥ 3 unidades que aceitam só um agregador e têm mês de vida ≥ 6 (mix/resultado_universo_cv.md:5).

A turma já tem congeladas as duas pontas, σ = 0 e σ = 1 (protocolo_uni09.md:142-144).

**Critério.** A régua 39/18 é cega para isto: o aceite quase não varia nessas unidades (protocolo_uni09.md:156-158). Ela é reportada só como trava: não pode piorar mais que 0,5 pp.

Critério de subgrupo, pré-registrado e a aprovar pelo Felipe, no grupo "sem algum agregador observado" (turma B + turma de 2026; lido só com n ≥ 4, protocolo_uni09.md:147-148):
- o erro típico de v2 × fator(σ̂) cai ≥ 10 pp contra a v2 e contra σ = 0;
- o IC 90% de σ̂ fica dentro de [0; 1/0,60].

O braço de eventos só confirma a direção: o sinal tem de ficar estável ao retirar cada evento, e o placebo tem de cobrir zero.

**Dependências.** - Etapa 3: metragem de bangu, icarai, flow, picarras e boa-vista, e o desfecho de painel.
- Tempo: ~6 meses de Wellhub no RJ (≈ mar/2027).
- Decisões do Felipe: o critério de subgrupo e a premissa de 60% (CADERNO:515,522; a conta Financeiro ÷ UX dá 47%).
- O Financeiro registra o agregador com atraso (alavancas/resultado_alavancas.md:85).
- Base Consolidada opcional, para aceite e credenciamento, só local.

### Etapa 5: alavancas do operador com data — histórico de preço e de estúdio (Growth) e tier/credenciamento declarado (Base Consolidada, local)

Propostas: balcao-2, agregador-8

**Por quê.** Hoje estúdio, preço e tier são fotos de 06/08/2026, posteriores ao desfecho de 2025 (DICIONARIO_UNI00.md:109-113; CADERNO:573-574). As três alavancas ficam presas a associação.
- Preço: na foto, plano mais caro tem +11% de alunos, porque o operador sobe o preço onde a demanda é forte; "preço não se mede comparando unidades" (CADERNO:518,545-546).
- O script de coleta está pronto e nunca rodou: precos/ só tem 01_coletar_vendas.py, sem o parquet de saída. Ele já conta as vendas de STUDIO e GOLDPRO por mês (linhas 43-44), o que dá a data real de início do estúdio e o torna variável conhecida antes de abrir.
- O tier declarado já era insumo listado do UNI-09 e não foi usado (tasks/backlog.md:5767).

É a cadeia que o caso Manaus pediu: prever o volume e aplicar o ticket declarado pelo operador (CADERNO:1032-1033).

**Como testar.** 1. Coleta de 2023-01 a 2026-08: ~44 chamadas, sem retry em 429, descartando nome e cod_aluno no ato (script, linhas 4-7). Antes, conferir a faixa de preço cheio, R$ 80–200 (linha 20).
2. Elasticidade do balcão: trocas de preço do Gold na mesma unidade, em diferença em diferenças contra as outras unidades no mesmo mês, janela de ±3 meses e placebo antes da troca.
3. Data do estúdio = 1º mês com venda STUDIO. Refazer o braço C da Etapa 2 com o estúdio datado, pré-registrado para a turma B e para as 5 cegas da turma.
4. Base Consolidada por script local: tier e aceite declarados por fase (operação, assinada, implantação), gravando só agregados.

**Critério.** - Preço: a elasticidade do volume de balcão precisa ter IC 90% que exclua zero e sinal estável ao retirar cada unidade. Aí vira entrada medida da v2, no lugar da aritmética com aviso; senão, fica como está.
- Estúdio datado e tier declarado: a mesma régua da Etapa 2 (c2 + c3 cru e recentrado, Holm), mais a conferência na turma B e na turma congeladas.

**Dependências.** - Login da Growth devolvendo 429 por credencial (tasks/backlog.md:6044-6046,5960-5962; BUG-GROWTH-DIA1): confirmar com a TI se outra integração usa a mesma credencial.
- A resposta da Growth traz PII: descartar no ato, sem cache em disco.
- Base Consolidada: só scripts locais do Felipe, sem subagentes, derivados LOCAL_.
- A tabela de repasse por tier pode ser confidencial (Financeiro/Operações).
- O re-teste do estúdio depende do braço C da Etapa 2.

### Etapa 6: forma da população — limitar à faixa do treino e testar a isócrona de 5 min só no balcão

Propostas: estrutura-5, balcao-7

**Por quê.** A população tem sinal negativo, com IC fora de zero, no total (−0,149) e no balcão (−0,178), e fica em ~0 no agregador (uni09/resultado_uni09.md:26). É uma forma suspeita do próprio modelo base, e não uma variável nova.

As unidades abaixo do mínimo do treino (68.231 hab., conferido) erram para cima: Mococa, 59.472 hab. (−53%), e Unaí, 66.871 (−21%) (uni02/resultado_uni02.md:7,35,39). Na turma, Buritis tem 46.177 e Bertioga 32.956.

Mas o limite à faixa move pouco: log(68.231/59.472) × 0,149 ≈ 2% em Mococa, ~6% em Buritis e ~11% em Bertioga. É bem menos que o "+0,28 em log" da proposta, que compara com a mediana.

A isócrona de 5 min nunca foi testada só no balcão. O prior é fraco: 22 variáveis de território deram nulo (CADERNO:44-47,296-299), e a população a pé (T15) também (uni01/resultado_uni01.md:32). Por isso fica por último.

**Como testar.** Uma especificação de cada, fixada antes:
- (a) limitar as covariáveis à faixa vista no treino, sem nenhum parâmetro novo;
- (b) na parte balcão, população e renda da isócrona de 5 min de carro (iso_pop__carro_5, iso_renda_pc__carro_5; DICIONARIO_UNI00.md:117-118), com o agregador mantido em 10 min.

Sem 15 min a pé e sem distribuição de renda (forking). Avaliação: LOO nas 39 + teste nas 18. Congelar a previsão da turma, em que Buritis e Bertioga são o teste direto.

**Critério.** c2 + c3 cru e recentrado, queda ≥ 2 pp, com Holm k = 2. O limite (a) pode ser adotado como regra de prudência mesmo sem ganho, desde que não piore nada (decisão do Felipe).

**Dependências.** Nenhum dado novo. Decisão do Felipe sobre usar o limite como regra de produto.

## Descartadas

- **estrutura-8:** Não é conhecido antes de abrir e não é diagnóstico: é uma revisão do nível maduro depois da abertura (meses 0–3). Pertence ao alerta do mês 3 / UNI-06 (CADERNO:173-175; uni03/resultado_uni03.md:57-63). Registrar no BLK-UNI-06, fora desta régua.

- **agregador-3:** - É colinear com o tier: o gap é o tier menos a mediana dos vizinhos.
  - A cobertura é de 59/98 (DICIONARIO_UNI00.md:242), só 14/18 no teste e 4/16 na turma, então não há conferência limpa.
  - O T05 já deu inconclusivo e instável (uni01/resultado_uni01.md:22).
  No máximo, entra como gráfico descritivo na Etapa 1.

- **agregador-5:** - A fonte é LOCAL_, e a DEC-012 proíbe "membros" como insumo de regressão.
  - Já falhou duas vezes: o T14 cai para +2,9% na sensibilidade A (uni01/resultado_uni01.md:31), e o X3 piorou nas unidades novas, de 7,1 para 8,9 (mix/resultado_mix_alunos.md:32).
  - Escritórios na parte agregador pioraram a previsão (uni09/resultado_uni09.md:43).
  - O teto é de ~1 pp, porque o TotalPass é 8% da receita (uni09/protocolo_uni09.md:27).

- **balcao-6:** Concorrência é armadilha já testada (CADERNO:1142-1150):
  - saturação nula (T10/T11, uni01/resultado_uni01.md:27-28);
  - termômetro Smart Fit piorou a previsão (CADERNO:1100-1104);
  - qualidade da concorrência, nulo informativo (CADERNO:1191-1198);
  - hipótese do diretor "não testável com 57" (CADERNO:1201-1202).
  A novidade ("medir no balcão") não cabe no laboratório, cujo desfecho é o total da Smart Fit, e só a Smart Fit tem data de abertura.

- **balcao-8:** É pista pós-hoc já vista (balcão +17%, p = 0,066; bateria/protocolo_bateria.md:145-147; CADERNO:1173-1175) nas mesmas 39/18. A turma só enxerga efeitos de ~+40% (CADERNO:1168-1169), e a variável está confundida com estúdio (6 de 9). Sem etapa própria: no máximo, congelar a peça de balcão com soc_exp dentro do BLK-UNI-12, por script local.

## Riscos gerais

**Expectativa honesta:** ganho direto plausível de 0 a 2 pp por etapa no erro típico. Os ganhos grandes possíveis estão em dois lugares:
- no subgrupo sem agregador, onde o erro hoje é de 68–83% (Etapa 4);
- na previsão para estado novo, onde as masters não se transferem (Etapa 2, braço B).

**Amostra pequena:** são 39 de treino e 18 de teste, e o erro típico do teste é a mediana de 18 unidades. O IC da queda no teste vai de −9,8 a +2,9 pp (uni09/resultado_uni09.md:8), e tirar uma unidade move o teste de 22% para 27% (CADERNO:1183-1187). A régua de −2 pp está dentro do ruído. Por isso a Etapa 3 (mais N e um juiz novo) é o caminho crítico, e o pedido de metragem sai já.

**Exposição das 18:** já foram consultadas no UNI-02, UNI-05, UNI-05B, UNI-07, termômetro, nos 6 itens da bateria e nas 8 sensibilidades do UNI-09. Não são mais teste limpo, e cada braço novo nelas aumenta a chance de um falso "passou": a variante M3 passou por 0,003 (CADERNO:335).

**Exposição da turma de 2026:** a leitura precoce já mostrou 11 das 16 unidades. Só 5 são cegas (belford-roxo, novo-gama, paulinia, domingos-ferreira e bonsucesso; uni09/protocolo_uni09.md:151-154), o que só detecta efeitos grandes.

**Múltiplos testes:** cada etapa é uma família com Holm. Braços que passarem não se somam sem um novo pré-registro. O recentrado é obrigatório, e um ganho só de nível não conta (bateria/protocolo_bateria.md:286).

**Forking paths:**
- na Etapa 1, só mecanismo; nunca cruzar candidata com o resíduo;
- uma especificação por braço;
- definições (temporada, área útil, faixa de preço, régua de leitura dos degraus) escritas antes;
- a "coorte" do estúdio surgiu de olhar o teste e só vale para a turma.

**Fotos posteriores:** estúdio, tier, preço e parceiros são de ago–set/2026, contra o desfecho de 2025. Há risco de causalidade reversa até as datas da Etapa 5.

**Confusões:**
- estúdio × master M2 × sócio experiente;
- RJ × sem agregador × demanda excepcional (Botafogo);
- calibração de calendário por parte × mudança de repasse do agregador.

**Régua cega ao aceite:** nas 39/18 o aceite quase não varia, então o critério de subgrupo tem de ser aprovado pelo Felipe antes.

**Dados sensíveis:**
- Base Consolidada: só scripts locais do Felipe, sem subagentes, derivados LOCAL_;
- Growth: PII descartada no ato, e o 429 por credencial bloqueia a coleta;
- um script pesado por vez.

**Governança:** a adoção é decisão do Felipe. A produção só muda com DEC (CADERNO:487-488).

**Citações das propostas:** algumas linhas estavam deslocadas (por exemplo, o 429 está em backlog.md:6044-6046 e o balcão da rampa em uni03/resultado_uni03.md:12,15) e foram recitadas acima. A conta do limite de população da estrutura-5 estava superestimada (≈ 2% em Mococa, não +0,28 em log).

## As 26 propostas (texto integral dos agentes)

### balcao-1 (balcao, esforço medio) — Estúdio × renda da praça (e × coorte) só na equação do balcão, com a data real de início do estúdio

**Hipótese.** O estúdio rende mais balcão onde a praça é de renda baixa ou média: a unidade completa vira líder numa concorrência de academias pequenas. A v2 trata o estúdio como um +23% constante e por isso subestima justamente as maiores surpresas de volume do teste. Noroeste (+66%), Cariacica (+67%), Butantã (+62%), Valparaíso (+48%) e Botafogo (+178%) têm estúdio; Mococa (−52%) não (uni07/erros_fora_da_amostra.csv). Termo primário a pré-registrar: studios × z(log renda domiciliar), só no balcão. Secundário: studios × coorte (abertura ≥ 2025).

**Dado.** `cad_mod_studios` (DICIONARIO_UNI00.md:113, cadastro VPS, foto 06/08/2026): 39/39 no treino, 18/18 no teste, 14/16 na turma (5 com estúdio, 9 sem, 2 sem dado). Renda domiciliar da v2. A foto é POSTERIOR ao desfecho de 2025 (CADERNO:573-574), então hoje o estúdio não é conhecido antes de abrir. A data real de início sai do histórico de vendas, produto STUDIO (`precos/01_coletar_vendas.py:43`, nunca coletado); com ela o estúdio vira variável ex ante (decisão do operador). Comparáveis: 7 unidades de renda baixa com estúdio faturam R$ 272–349 mil, contra mediana de R$ 136 mil sem estúdio (CADERNO:936-938).

**Já testado.** Efeito principal, sim: +30% no treino [+7%; +59%], que não se repetiu no teste (CADERNO:517); +28% com a master controlada (CADERNO:550); já está na v2. No UNI-09, balcão +0,233 [+0,01; +0,46] (uni09/resultado_uni09.md:30). Desvio pós-hoc no teste: com estúdio +55% (7 de 8 acima) contra −21% sem, Fisher ≈ 0,008; não aparece no treino (−6% × −4%) e está confundido com a matriz (backlog.md:5728-5731; CADERNO:838-843). A interação estúdio × renda, que é a hipótese principal do BLK-UNI-08, e a interação estúdio × coorte NUNCA foram rodadas (conferido em backlog.md:5739-5744, onde aparecem como 'Próximo'; o CADERNO não tem etapa do UNI-08).

**Ganho esperado.** É o padrão mais nítido entre os maiores erros de volume. Se o desvio do teste for real, um termo que capture metade dele tira alguns pontos do erro no teste, porque o grupo com estúdio está +55%. No LOO das 39 o ganho é ~0 por construção, já que o treino não tem desvio. Só se decide de verdade na turma de 2026 (5 com estúdio), com a previsão congelada antes.

**Riscos.** Interação com N = 39 tem pouco poder: é o mesmo problema do T08/T09, testados 4 vezes. Três confusões: com a master M2 (matriz sem estúdio), com a experiência do sócio (6 de 9 grupos experientes têm estúdio, CADERNO:1171-1172) e com a foto de ago/26 (causalidade reversa: a unidade que vai bem abre estúdio), esta última até haver a data pelas vendas. A ideia de 'coorte' veio depois de ver o teste, então só vale como pré-registro para a turma.

### balcao-2 (balcao, esforço medio) — Preço de tabela na abertura e trocas de preço na mesma unidade (histórico de vendas Growth)

**Hipótese.** O preço do Gold é decisão do operador e age no balcão por dois canais: o ticket (direto) e o volume (elasticidade negativa). Na foto de ago/26 o preço alto aparece com MAIS alunos, porque o operador sobe o preço onde a demanda é forte. Duas medidas resolvem isso: o preço na abertura (ex ante) e as trocas de preço dentro da mesma unidade (diferença em diferenças contra as outras unidades no mesmo mês). Com elas se mede a elasticidade do volume de balcão, e o balcão passa a ser 'volume previsto pela praça × preço declarado', a cadeia que o caso Manaus pediu (CADERNO:1032-1033). O mesmo histórico dá a fração de vendas promocionais na abertura (agressividade da pré-venda) e o mês em que o STUDIO/GOLDPRO começou a ser vendido.

**Dado.** Growth `/relatorio-vendas-operacoes`. O script está pronto: `precos/01_coletar_vendas.py`, que agrega por unidade × mês a moda e a mediana do preço do Gold cheio, o nº de promoções, de STUDIO e de GOLDPRO, e descarta nome e cod_aluno no ato (linhas 1-7, 40-43). A saída `precos/vendas_unidade_mes.parquet` NÃO existe: o script nunca rodou. A janela 2023-01 a 2026-08 cobre a abertura de todo o teste e da turma. Nas 39 maduras, só as abertas a partir de 2023 têm preço de abertura; nas demais, só as trocas. A foto atual `cad_preco_gold` (DICIONARIO_UNI00.md:109, 06/08/2026) tem 39/39, 18/18 e 9/16. O preço de tabela é conhecido antes de abrir.

**Já testado.** Pela foto, quatro vezes:
- anatomia: Spearman +0,47 com o erro de alunos (uni01/anatomia_erros.md:35; CADERNO:293-295);
- duas partes alunos × ticket: ficou fora (CADERNO:339);
- alavancas: +9,7% no faturamento por R$ 10, inconclusivo; +11% de alunos com o ticket parado (alavancas/resultado_alavancas.md:128; CADERNO:518);
- leitura registrada: 'preço não se mede comparando unidades' (CADERNO:545-546).
O preço relativo à concorrência (T05) deu nulo (CADERNO:42). O HISTÓRICO nunca foi coletado: `precos/` só tem o script (CADERNO:1139, 'a coleta da Growth está pronta'; backlog.md:5624).

**Ganho esperado.** Pouco no erro central entre unidades, porque na foto o preço explica pouco do volume. O ganho certo é estrutural: a alavanca 'preço do plano' deixa de ser aritmética com aviso (CADERNO:518) e vira entrada medida, que é o que decide casos como Manaus (R$ 167 em praça de renda baixa). Destrava também a data do estúdio para o balcao-1.

**Riscos.** O login da Growth está devolvendo 429 (backlog.md:6037-6039, BUG-GROWTH-DIA1): são ~44 chamadas mês a mês com limite de 10 a cada 5 min. A resposta traz PII, que o script descarta antes de gravar; manter assim. As trocas de preço podem ser endógenas (o preço sobe quando a unidade enche): usar janelas curtas e controles do mesmo mês. A faixa de 'preço cheio' (R$ 80–200, fixada na linha 20 do script) precisa ser conferida antes de rodar.

### balcao-3 (balcao, esforço medio) — Substituição: o balcão recupera alunos quando a unidade não aceita ou perde agregador

**Hipótese.** Sem agregador, parte da demanda migra para o plano recorrente. Botafogo fatura R$ 697 mil com ~4.000 alunos de balcão e nenhum agregador (CADERNO:391-393); Laranjeiras está +134% na leitura precoce (previsao_2026/leitura_precoce.md:17). O balcão precisa de um termo s × (receita de agregador que a praça daria). Hoje o UNI-09 supõe s = 0 e erra 83% nas 3 unidades do teste sem algum agregador (uni09/resultado_uni09.md:18). Dois braços:
(a) corte transversal: trocar as masters, na equação do balcão, pela intensidade do mercado de agregador da praça. O −0,39 do M3 no balcão vem só de SP, onde todas aceitam agregador (resultado_uni09.md:28,32);
(b) eventos na mesma unidade: o RJ passou a aceitar Wellhub em set/2026, e Suzano perdeu agregador (2.964 → 919 alunos em abr–ago/26).

**Dado.** Aceite pelo cadastro, `wh_/tp_tem_agregador_cadastro` (DICIONARIO_UNI00.md:245,247; foto 06/08/2026):
- treino: 39/39 aceitam Wellhub e 37 aceitam TotalPass;
- teste: 17/18 Wellhub e 15/18 TotalPass;
- turma: Wellhub sim 5, não 9, sem dado 2. Na turma, a foto mede credenciamento em andamento (uni09/protocolo_uni09.md:129-137).
Mercado de agregador: `wh_n_conc_c10` e `tp_n_conc_c10` (DICIONARIO_UNI00.md:221,235; coleta de 10–15/09/2026), com 39/18/16. Série mensal de `fin_vendas_ux`, `pagantes`, `fin_gympass` e `fin_totalpass` em fato_unidade_mes, até 2026-09. A Base Consolidada também tem os tiers e o aceite: é sensível, então aqui só é citada (roda local). O aceite é decisão conhecida antes de abrir.

**Já testado.** - Entrada do TotalPass (3 eventos): balcão +17,9% [+1,7%; +36,7%], mas o placebo também deu positivo, e o s saiu degenerado: 9,79 [−22; +27] (alavancas/resultado_alavancas.md:52,107; CADERNO:513-516).
- 'Sem agregador' ficou só na aritmética, de −25% a +27% (CADERNO:537-541).
- No cadastro, a substituição não é estimável no treino (uni09/protocolo_uni09.md:110-111).
- No UNI-09, indício com n = 3 (CADERNO:1326-1331).
- Os eventos RJ-Wellhub e Suzano, lidos no balcão, NUNCA foram testados: o RJ começou em set/2026 (CADERNO:540-541), e Suzano só aparece como anomalia (backlog.md:6207-6208).

**Ganho esperado.** Grande no subgrupo que mais erra: dezenas de pontos de erro nas unidades sem agregador, que pelo cadastro são 9 das 16 da turma. Nas unidades que aceitam os dois, ~0. É o que permite à v2 receber 'não aceita agregador' como alavanca medida, e não como a faixa de −25% a +27%.

**Riscos.** O RJ tem só ~1 mês depois do evento; a leitura útil vem em ~6 meses (mar/2027). Suzano é unidade do treino e pode ter outra causa (repasse do agregador, gestão). O mercado de agregador da isócrona é foto de set/26, então a leitura é de associação. Poucos eventos dão inferência fraca, como no TotalPass. A contagem de alunos de agregador do UX não é limpa: medir em receita.

### balcao-4 (balcao, esforço baixo) — O balcão maduro é fixado na abertura: persistência da pré-venda e momento de inaugurar

**Hipótese.** O balcão já está em 91% do nível maduro no mês da inauguração e em 89% no mês 3 (uni03/resultado_uni03.md:14,17): o volume de balcão é fixado na pré-venda, e quem rampa é o agregador. Se o desvio do balcão nos meses 0 e 1, contra o previsto pela praça, persistir até o maduro, o volume que a v2 não explica é execução da abertura. Nesse caso as variáveis certas são de pré-venda: duração, verba e meta. Uma delas já está disponível: o mês de inauguração (alta temporada jan–mar × resto). Ordem: primeiro o diagnóstico de persistência, depois a variável ex ante.

**Dado.** - `pagantes` no `mes_vida` 0 e 1 (fato_unidade_mes, DICIONARIO_UNI00.md:25) e `rampa_recorrentes_m1`, `rampa_vendas_m0` e `rampa_novos_alunos_m0` (DICIONARIO_UNI00.md:275,297): 30/39 no treino (as outras 9 abriram antes de abr/2022), 18/18 no teste e 16/16 na turma.
- `inauguracao`: 98/98, com meses espalhados (10 em jan, 14 em jun).
- Pré-venda propriamente dita (`rampa_n_alunos_prevenda`): 0/98, pendente do export do Lifetime (DICIONARIO_UNI00.md:320; backlog.md:6213-6231).
- Verba e duração da pré-venda: não existem; é dado novo (CADERNO:1137).
Os meses 0 e 1 não são ex ante (vêm depois da aprovação). O mês de inauguração e o plano de pré-venda são.

**Já testado.** A curva de rampa e o alerta foram medidos em alunos TOTAIS: a projeção erra 17–21% a partir do mês 1 e 5–9% a partir do mês 3 (uni03/resultado_uni03.md:57-63; CADERNO:173-175). T16, 'rampa prevê o maduro': ΔR² LOO +0,63 (backlog.md:5356). Idade da unidade × erro: nulo (uni01/anatomia_erros.md:55). Nunca testados: a projeção pelo BALCÃO dos meses 0 e 1, a persistência do resíduo do balcão (o P3 começa no mês 1 e usa ativos) e o mês ou temporada de inauguração (sem ocorrência no CADERNO nem nos protocolos).

**Ganho esperado.** (a) Alerta para 74% da receita já nos meses 0–1, antes do mês 3. (b) Se o resíduo persistir, aponta com evidência o dado que falta coletar (o plano de pré-venda), em vez de mais uma variável geográfica. (c) Temporada de inauguração: efeito pequeno a médio, barato de testar e conhecido antes de abrir.

**Riscos.** O mês 0 é parcial (f0 mediano 0,53, uni03/resultado_uni03.md:6), e a foto do fim do mês depende do dia de abertura. 9 das 39 maduras não têm o mês 0 observado. A pré-venda que não renova (queda do mês 0 para o mês 1, CADERNO:160-163) mistura a leitura. A temporada se confunde com o ano de abertura e com a calibração 2025→2026. Risco de forking: fixar uma única definição de temporada antes de rodar.

### balcao-5 (estrutura, esforço baixo) — Captação × retenção: decompor o volume de balcão em entrada de alunos e cancelamento

**Hipótese.** Em regime, pagantes ≈ novos alunos por mês ÷ churn. O erro de volume do balcão pode ser de CAPTAÇÃO (visitas, conversão, novos alunos: ponto, marketing, pré-venda) ou de RETENÇÃO (churn: operação, renda). Separando as duas, cada parte recebe as suas covariáveis: captação ~ m², população local e pré-venda; churn ~ renda (o UNI-04 achou −1,29 pp por desvio-padrão nas maduras). Mesmo sem ganho direto de precisão, mostra onde está o volume que falta.

**Dado.** `visitas`, `convertidos`, `novos_alunos`, `vendas`, `cancelados` e `churn_pct` (fato_unidade_mes, Growth, valor cumulativo do mês; DICIONARIO_UNI00.md:18-25,48). O churn é só de balcão (CADERNO:253-254). Em 2025 os meses têm valor > 0 em mais de 99% dos casos (conferido: visitas 100%, novos alunos 100%, cancelados 99,9%). Cobertura 39/39 e 18/18; a turma ainda está imatura. Não é variável ex ante: é estrutura do modelo, e as covariáveis de cada parte é que precisam ser ex ante.

**Já testado.** Já rodados: a divisão alunos × ticket, que piorou (CADERNO:332); a anatomia, que pôs 87–92% do erro no volume (CADERNO:281-282); e renda × churn (UNI-04), forte em 2025 e não confirmado nas 17 novas (CADERNO:243-248). A decomposição captação × retenção do balcão NUNCA foi feita: visitas, captação e conversão não aparecem como análise no CADERNO nem nos protocolos.

**Ganho esperado.** Diagnóstico: diz onde está o erro. Se ele se concentrar na captação, reforça o balcao-4 e a coleta de pré-venda e de ponto; se na retenção, liga ao Lifetime (BLK-UNI-PEND-01). Só ganha precisão se o churn por renda se sustentar, e ele não se confirmou nas unidades novas.

**Riscos.** A identidade de estoque só vale em regime. `novos_alunos` e `vendas` podem incluir renovações ou reativações: conferir a definição com a Growth. O churn mensal é ruidoso. O efeito da renda no churn não se confirmou nas novas (CADERNO:248).

### balcao-6 (balcao, esforço medio) — Concorrência low-cost direta (Smart Fit e redes de preço baixo) aberta antes da Ultra, medida no balcão

**Hipótese.** Quem compra o plano recorrente da Ultra é o mesmo público de Smart Fit, Selfit, Bluefit e SkyFit; para o usuário de agregador, tanto faz. Uma rede low-cost a poucos minutos, aberta antes da Ultra, deve tirar balcão, e não agregador. A contagem total de academias e a saturação misturam independentes com redes premium, o que pode explicar por que deram nulo.

**Dado.** - `insumos_vps/concorrentes_mapeados_2026-09-27.parquet`: 4.795 academias com rede e lat/lng (conferido: smart_fit 1.065, panobianco 542, skyfit 456, bluefit 234, selfit 232, pratique 185). Não tem data de abertura (foto de set/26).
- Data de abertura só da Smart Fit: painel `data/validacao/KPIs_Smart_2025_02 (1).xlsx`, de jan/2023 a jan/2026, 961 unidades, 363 com o 1º mês depois de jan/2023 (conferido).
- Isócronas de carro 5 e 10 min: prontas para 39/18/16.
- Laboratório Smart Fit pronto (`bateria/item2_comodidades.py`, amostra_lab e lab; backlog.md:5906-5907).
É ex ante para a Smart Fit datada; as outras redes entram só como foto.

**Já testado.** - Saturação (T10, alunos de concorrentes por mil hab.): nulo (uni01/protocolo_uni01.md:66; CADERNO:118).
- Nº de academias c10: −0,01 (uni01/anatomia_erros.md:56).
- Termômetro Smart Fit (volume da vizinha): NÃO MELHORA; o sinal negativo vem de causalidade reversa (CADERNO:1100-1110). O nº de Smart Fit a 5 km entrou só como controle (termometro/resultado_termometro.md:29).
- Qualidade da concorrência: nulo informativo no laboratório (CADERNO:1191-1198).
- Hipótese do diretor por frac_indep: testada 4 vezes (CADERNO:1149).
Nunca testado: presença ou distância de rede low-cost aberta antes da Ultra, medida no BALCÃO.

**Ganho esperado.** Provavelmente pequeno, porque as medidas vizinhas de concorrência já deram nulo. O valor está em fechar a pergunta 'Smart Fit perto' com poder: no laboratório (~578 Smart Fit), o efeito detectável fica em poucos %, enquanto a Ultra sozinha não detecta nada.

**Riscos.** A Smart Fit escolhe pontos fortes, o que gera associação positiva espúria. No laboratório o desfecho é o total da Smart Fit (inclui TotalPass), não o balcão. As outras redes não têm data. 'Concorrência' é armadilha conhecida (lista de nulos, CADERNO:1142-1150): pré-registrar uma única medida principal, por exemplo o nº de unidades low-cost a até 5 min de carro abertas antes da Ultra.

### balcao-7 (balcao, esforço medio) — Praça própria do balcão: área de captação local e renda-alvo do low-cost

**Hipótese.** O balcão é demanda de vizinhança, e a isócrona de 10 min é larga demais para ele. Isso explicaria duas coisas:
- a população com sinal NEGATIVO só no balcão: −0,178 [−0,28; −0,08] na receita e −0,154 em pagantes, contra ~0 no agregador (uni09/resultado_uni09.md:26);
- o caso Lago Sul, em que a área alcança o Plano Piloto (CADERNO:300-301).
Primário: população e renda da isócrona de carro de 5 min na equação do balcão; o agregador fica em 10 min. Secundário: no lugar da renda média, a fração da população em setores com renda domiciliar na faixa do low-cost, porque uma área de média alta pode ser bimodal.

**Dado.** `iso_pop__carro_5`, `iso_renda_pc__carro_5` e `iso_domicilios__carro_5` (DICIONARIO_UNI00.md:117-119; Censo 2022 + isócronas v2): 39/39, 18/18, 16/16. `iso_*__pe_15`: 38/39 (Lago Sul anulada), 18/18, 16/16. O Censo 2022 não tem faixa de renda por setor (docs/relatorio_pontual_censitario.md:233); por isso, usar a distribuição da V06004 dos setores dentro da isócrona, com a infraestrutura setor × isócrona do item 3 (`bateria/item3_prep_idade_setor.py`). Tudo é conhecido antes de abrir.

**Já testado.** - População a pé (T15): nulo no faturamento total (uni01/protocolo_uni01.md:71; CADERNO:42,60).
- Renda e densidade versus o erro: nulos (uni01/anatomia_erros.md:40,49).
- Renda per capita × domiciliar: iguais, 22,1% (CADERNO:920-921).
- Leitura geral: 'a geografia já deu o que tinha a dar' (CADERNO:44-47).
Nunca testados: a escala da área SÓ na equação do balcão e a distribuição de renda dentro da área.

**Ganho esperado.** Baixo a moderado: 0 a 2 pp no total. Corrige uma forma suspeita (população negativa) e casos de área inflada como Lago Sul. O prior é fraco, porque 22 variáveis de território já falharam.

**Riscos.** Forking (3 escalas × 2 variáveis): fixar a escala antes de rodar. A isócrona de 5 min tem pouca população em praças ralas, o que traz mais ruído. O sinal negativo da população pode ser composição de SP e agregador, e não escala. Botafogo tem demanda local excepcional que nenhuma escala de Censo capta.

### balcao-8 (balcao, esforço baixo) — Experiência do sócio no balcão: conferir a pista de +17% só na turma de 2026

**Hipótese.** Um grupo que já operava outra Ultra vende melhor a pré-venda e o plano recorrente. O efeito aparece no balcão (+17%, p = 0,066), e não no total (+11%, p = 0,155) nem no volume total (+1%): é mix, não volume (CADERNO:1173-1175). Se for real, entra na equação do balcão, e não no total.

**Dado.** Base Consolidada (`Downloads/BASE UNIDADES_CONSOLIDADA.xlsx`, MUITO sensível): só scripts locais do Felipe, derivados LOCAL_*; não foi aberta aqui. Variável `soc_exp` por unidade, foto de 01/10/2026, conhecida antes de abrir (o sócio é definido na aprovação). A peça do balcão da turma já está congelada no UNI-09 (SHA 38593c1d…, uni09/resultado_uni09.md:49). A mesma base tem o 'tempo do contrato à inauguração', nunca testado (CADERNO:1121-1122).

**Já testado.** Item 1 da bateria: total +11% [−7%; +31%], p = 0,155, e a variável piora a previsão (CADERNO:1166-1175; backlog.md:5881-5887). O +17% no balcão foi um secundário descritivo (bateria/protocolo_bateria.md:145-147). As 39/18 já foram expostas a esse resultado: testar de novo nelas seria pós-hoc. Confundido com estúdio: 6 de 9 grupos experientes têm estúdio.

**Ganho esperado.** Se for real, ~+17% no balcão das unidades de grupo experiente, ou ~+12% no total. Só dá para conferir na turma (≈14 unidades), que só detecta efeitos grandes (~+40%).

**Riscos.** Exposição (a pista já foi vista) e pouco poder. Confusão com estúdio e com a master. Homônimos e troca de dono (Carapicuíba já saiu do teste). Sensibilidade da base.

### balcao-9 (dado, esforço baixo) — Metragem efetiva das unidades de teste e da turma (área útil, conferida às cegas)

**Hipótese.** Parte dos erros de volume pode ser metragem errada.
- A turma inteira e 3 unidades do teste usam metragem por satélite: erro típico de 20%, viés de 12% já corrigido, e a contagem de andares é a maior fonte de erro.
- A oficial também erra: Cotia tem 750 m² na planilha e ~1.050 m² medidos.
- Butantã, um dos 4 maiores erros do teste (+62%), tem metragem por satélite.
Com elasticidade do balcão ao m² de 0,51 (0,35 em pagantes), um erro de 20–40% na metragem vira um erro de previsão de ~10–19% nessas unidades.

**Dado.** `tam_metragem_m2` (DICIONARIO_UNI00.md:104, dados_academias.xlsx): 39/39, 15/18, 0/16. `coleta_metragem/metragem_estimada*.csv` para as demais. A metragem é conhecida no projeto (ex ante). Fonte nova: planta ou contrato de locação de cada unidade (área útil e nº de pavimentos ocupados).

**Já testado.** Já feitas: a coleta por satélite e a calibração com gabarito (CADERNO:359-367), e a confirmação do modelo com metragem oficial × satélite (com só a oficial, erro igual: 22% × 22%; CADERNO:383-385). Nunca feitas: a re-medição por planta e a conferência da metragem oficial (Cotia segue pendente, CADERNO:367).

**Ganho esperado.** Pequeno no total, mas tira ruído justamente da turma de 2026, que é o teste limpo de todas as outras propostas. É barato.

**Riscos.** Re-medir só as unidades que mais erram enviesa o resultado (corrige para o lado do erro): re-medir todas da turma e do teste, às cegas e sem o desfecho. A definição de 'área útil' precisa ser fixada antes.

### agregador-1 (agregador, esforço baixo) — Tier da Ultra no agregador (Wellhub e TotalPass) na parte agregador, com teste próprio pré-registrado

**Hipótese.** A receita de agregador é o número de visitas vezes o valor pago por visita, e o tier define as duas coisas: quais assinantes têm acesso e quanto paga cada visita (mix/protocolo_mix.md:45; uni09/protocolo_uni09.md:113). Na Etapa 11 o desfecho era a PROPORÇÃO de alunos, pela contagem do UX, que mede pessoas e não reais. Por isso o efeito de preço não aparece ali. No T03 ele se diluiu no ticket total, que é 74% balcão. Na receita de agregador do Financeiro ele aparece direto. O 'preço da Ultra no agregador' (wh_preco_ultra, tp_preco_ultra/tp_plano_ultra) NÃO é uma variável separada: é função 1:1 do plano (ordem_tiers_wellhub.csv e ordem_tiers_totalpass.csv, preco_modal com nunique=1 por plano) e é o preço do ASSINANTE, não o repasse à Ultra. Teste proposto: parte agregador da v2 + ordinal do Wellhub, com o TotalPass num braço separado. O c3 RECENTRADO é critério obrigatório, porque a regra da bateria (bateria/protocolo_bateria.md:286) não aceita ganho só de nível.

**Dado.** dim_unidade: cad_tier_wellhub e cad_tier_totalpass (DICIONARIO_UNI00.md:110-111), cobertura 39/39, 18/18 e 14/16. Ordinal wh_ord_ultra_cadastro com 39/17/5 e tp_ord_ultra_cadastro com 37/15/3 (DICIONARIO:244,246); a turma tem pouco porque 9 unidades estão como 'NÃO POSSUI' no cadastro. A foto do cadastro é de 06/08/2026. O feed (wh_ord_ultra 38/14/4, tp_ord_ultra 30/13/3) é de 10–15/09/2026. No treino há só 3 níveis: Wellhub Basic 4, Basic+ 18 e Silver 17; TotalPass TP1+ 29, TP2 7 e TP3 1. No treino, cadastro e feed concordam em 32 de 38 (Wellhub) e em só 19 de 30 (TotalPass). Conhecido antes de abrir: SIM, como decisão do operador no credenciamento (alavanca, como o estúdio). Mas o valor da foto é posterior ao desfecho de 2025.

**Já testado.** UNI-01 T03, tier × ticket total: descartada, +3,8% [−1,8; +9,7] (uni01/resultado_uni01.md:20). T04, tier × % agregador: inconclusiva (resultado_uni01.md:21). Etapa 11, X4 na proporção de alunos: inconclusiva; na confirmação o erro foi de 7,1 para 6,2 p.f. e 'não se repete' (mix/resultado_mix_alunos.md:19,33). Na proporção da receita: +3,8 p.f., inconclusiva (mix/resultado_mix_receita.md:19). Anatomia: ρ +0,21 com o erro (uni01/anatomia_erros.md:36). UNI-09, sensibilidade exploratória: LOO 23,5% → 20,8% (−2,7 pp) e teste 21,1% → 19,0% (−2,1 pp), mas o RECENTRADO PIORA 1,0 pp (uni09/resultado_uni09.md:45; CADERNO:1333-1335). O tier do TotalPass nunca foi testado contra desfecho; só se mediu ρ +0,20 com a renda (resultado_uni01.md:62).

**Ganho esperado.** A pista indica −2 a −3 pp no erro do total, mas só em nível. O que falta provar é o ganho no recentrado (hoje −1,0 pp). Expectativa honesta: de 0 a −2 pp no total. O teto é baixo, porque o agregador é 24% da receita (16% Wellhub e 8% TotalPass; uni09/protocolo_uni09.md:27).

**Riscos.** Causalidade reversa e maturidade: nas 18 de teste há 5 unidades 'Basic', contra 4 de 39 no treino. A unidade nova pode entrar num tier baixo e subir depois, e a foto mistura decisão com resultado. A correlação com a renda (ρ +0,53) pode contar duas vezes a elasticidade de renda do agregador (0,55). São só 3 níveis, e o TotalPass é quase constante (29 de 37 em TP1+). Com 5/16 de ordinal na turma, a conferência limpa quase não testa. A divergência entre cadastro e feed (TotalPass 19/30) é ruído de medida.

### agregador-2 (estrutura, esforço medio) — Substituição medida em vez de suposta: o fator de aceite entre os agregadores e do agregador para o balcão

**Hipótese.** O UNI-09 supõe que quem não aceita um agregador perde toda a receita dele: o fator é 1 − s_TP, s_TP ou 0 (uni09/protocolo_uni09.md:43-48). Três sinais indicam que isso pune demais. (1) A mesma previsão com fator 1 para todos leva o LOO das duas partes de 22,2% para 20,0%, e o s_TP de fora de SP leva a 21,3% (uni09/resultado_uni09.md:38,41). (2) As 3 unidades de teste sem algum agregador erraram 82,5%, contra 68,0% da v2, por preverem DE MENOS (resultado_uni09.md:15-18; CADERNO:1326-1331). (3) Na turma, as unidades com fator 0 ficaram acima da previsão na leitura precoce (protocolo_uni09.md:152-153; Laranjeiras +134%, previsao_2026/leitura_precoce.md:17). Proposta: estimar dois parâmetros em vez de fixá-los. θ é a fração da receita de TotalPass que o Wellhub absorve quando só ele é aceito. σ é a fração da receita de agregador perdida que volta pelo balcão, entre 0 e 1/0,60. Os dois entram no fator de aceite.

**Dado.** Aceite observado mês a mês na receita: fin_gympass com 2147/2275 linhas e fin_totalpass com 1899/2275 (DICIONARIO_UNI00.md:52-53); o Financeiro só tem TotalPass desde out/2023. Variação de aceite: no treino, 2 unidades só com Wellhub (asa-norte-df, lago-norte-df; mix/resultado_mix_alunos.md:6). No teste, 1 sem Wellhub e 3 sem TotalPass (protocolo_uni09.md:30-34). No universo de 64, 5 aceitam só um (mix/resultado_universo_cv.md:5). Saídas: boa-vista-ba sem Wellhub desde 2025-03 (586 alunos) e campo-largo-pr sem TotalPass desde 2026-05 (alavancas/resultado_alavancas.md:116-118). Experimento natural: o RJ passou a aceitar Wellhub em set/2026, o que permite comparar antes e depois dentro da mesma unidade (CADERNO:540-541, 1354). O aceite é conhecido antes de abrir (decisão do operador).

**Já testado.** Etapa 10: 'aceitar ou não' NÃO mede. A conta de substituição deu s = 9,79 [−22; +27], 'não medida' (alavancas/resultado_alavancas.md:104-110; CADERNO:516). A entrada do TotalPass deu +10,2% de faturamento, inconclusivo (resultado_alavancas.md:53). UNI-09: substituição declarada 'não estimável' no treino (protocolo_uni09.md:110-111). A turma tem as peças congeladas nas duas pontas, substituição zero e total (protocolo_uni09.md:141-144). No teste, o fator 1 NÃO melhora: 22,9% → 23,0% (resultado_uni09.md:38). θ, a substituição entre agregadores, nunca foi testado.

**Ganho esperado.** Quase nada nas 39 e nas 18, porque o aceite quase não varia ali (protocolo_uni09.md:156-158). O ganho está onde as duas partes mais erram: nas unidades sem algum agregador, o erro de 82,5% pode voltar ao nível da v2 (68%) ou ficar abaixo dele. Para a expansão (a Grande Rio não aceitava agregador até set/2026, CADERNO:342-345), é o parâmetro que mais move a previsão: de −25% a +27%, conforme a substituição (CADERNO:538).

**Riscos.** O n é minúsculo (2 + 3 + 5 que aceitam só um, com sobreposição). Botafogo e Laranjeiras misturam 'sem agregador' com demanda excepcional do RJ. Parte do ganho do fator 1 no LOO pode ser só nível, porque o k é recalculado com o fator (protocolo_uni09.md:165-167). As 3 unidades de teste já foram vistas, então estimar σ nelas é pós-hoc. O teste limpo é o RJ depois de ~6 meses (≈ mar/2027) e a turma com o aceite observado. O Financeiro registra o agregador com atraso (alavancas/resultado_alavancas.md:85).

### agregador-3 (agregador, esforço baixo) — Posição da Ultra no cardápio do agregador: tier relativo aos concorrentes da isócrona

**Hipótese.** Na parte agregador não importa só o tier absoluto, mas quantos concorrentes a mesma assinatura alcança. Se o tier da Ultra fica abaixo da mediana dos vizinhos, ela é a opção barata do cardápio e recebe mais visitas dos planos baixos; se fica acima, disputa com academias de categoria maior. É um mecanismo de VISITAS de agregador, não de faturamento total. Por isso o T05, medido contra o total, não tinha como ver. Roda como braço ALTERNATIVO ao agregador-1, não somado a ele.

**Dado.** dim_unidade: wh_gap_ord_c10 (DICIONARIO_UNI00.md:242), cobertura 38/39, 14/18 e 4/16. wh_pct_acima_ultra_c10 e wh_pct_abaixo_ultra_c10 (DICIONARIO:239,241), mesma cobertura. tp_gap_ord_c10 (DICIONARIO:228): 30/39, 13/18 e 3/16. Foto do feed de 10–15/09/2026, posterior ao desfecho de 2025. Exige a Ultra listada no feed e ≥ 3 concorrentes com preço. Conhecido antes de abrir: em parte; o tier dos vizinhos sim, o da Ultra é decisão.

**Já testado.** UNI-01 T05 (wh_gap × faturamento TOTAL): +7,7% [−5,5%; +22,7%], inconclusiva e instável ao retirar cada metrô (uni01/resultado_uni01.md:22; uni01/protocolo_uni01.md:61). 'Preço frente à concorrência' está entre as variáveis sem efeito (CADERNO:41-42). Nunca testado contra a receita de agregador nem contra as passagens: conferido por grep nos .py/.md de data/analysis/uni, onde wh_gap só aparece no UNI-01.

**Ganho esperado.** Pequeno no total (≤ 1 pp). O valor é decidir se pesa o tier absoluto (agregador-1) ou o relativo.

**Riscos.** É colinear com o tier, porque o gap é o tier menos a mediana dos vizinhos. A cobertura é ruim no teste (14/18) e quase nula na turma (4/16), então não há conferência limpa. A foto é de set/2026. O filtro de musculação do Wellhub já perdeu 13% das academias numa versão anterior (CADERNO:88).

### agregador-4 (agregador, esforço medio) — Mercado de agregador medido (parceiros por mil hab. + independentes no agregador) no lugar das masters na parte agregador, avaliado deixando um metrô inteiro de fora

**Hipótese.** Na parte agregador, as masters valem +0,76 a +0,98 em log (uni09/resultado_uni09.md:27-29). Isso é mercado e política comercial de SP e DF/GO, e não se transfere. Manaus herda o +0,98 da M3 (CADERNO:956-957) e é a praça com MENOR oferta de agregador medida na rede, no percentil ~0 (CADERNO:1050). Trocar as dummies por uma medida do mercado mantém o mecanismo e transfere para estado novo (RJ, MG e AM, onde está a expansão). Por que a RECEITA seria diferente da PROPORÇÃO da Etapa 11: a proporção cancela o volume comum às duas partes (renda e população explicam R² 0,008 dela; mix/resultado_mix_alunos.md:8), e o que sobra é o estado. Já o NÍVEL da receita de agregador responde à praça (elasticidade à renda 0,55 contra 0,25 no balcão; ao m², 0,97 contra 0,51; resultado_uni09.md:24-25) e à densidade de assinantes. Comparar 3 braços pré-registrados: masters (atual), grupo de estado SP / DF-GO / outros (regra da Etapa 11) e mercado medido. A métrica principal é o erro deixando um metrô inteiro de fora.

**Dado.** dim_unidade: wh_n_conc_c10 e tp_n_conc_c10 (DICIONARIO_UNI00.md:235,221) e iso_n_independente_agregador__carro_10 (DICIONARIO:138), todas com 39/39, 18/18 e 16/16. O denominador é iso_pop__carro_10. No treino (p10/p50/p90): parceiros Wellhub 17/68/164, TotalPass 18/43/129, independentes 16/48/134. Foto do feed de 10–15/09/2026, sem a Ultra e sem estúdios (DICIONARIO:220). Conhecido antes de abrir: sim para um ponto novo, porque o feed de hoje é o 'antes' dele. No treino é anacrônico.

**Já testado.** UNI-09, sensibilidade com log(1 + parceiros) SOMADO às masters: LOO +0,2 pp, teste +1,8 pp e recentrado +1,0 pp. É a única sensibilidade do agregador que melhorou também o recentrado (uni09/resultado_uni09.md:44). Etapa 11, X5 (independentes no agregador, na proporção): +21,3 p.f. em 2025, mas o erro DOBROU nas unidades novas, de 7,1 para 13,9 (mix/resultado_mix_alunos.md:20,34; CADERNO:625). Regra por estado na proporção: erro de 12,7 para 9,8 e, com o metrô de fora, de 14,3 para 9,5 (mix/resultado_universo_cv.md:17). A versão por mil hab. e a SUBSTITUIÇÃO das masters nunca foram testadas.

**Ganho esperado.** No LOO das 39 (quase só SP e DF), perto de zero. O ganho que importa é com o metrô de fora e em estado novo, onde a master hoje leva o mercado de SP. O +1,8 pp do teste é o teto plausível no total.

**Riscos.** A foto é posterior, com causalidade reversa: o agregador recruta parceiros onde há assinante, e a própria Ultra puxa esse mercado. O X5 já mostrou ajuste à amostra. A colinearidade com SP é forte (demanda TotalPass × independentes no agregador, ρ +0,73; resultado_mix_alunos.md:44). Trocar 3 dummies por 2 variáveis contínuas com N = 39 pode só mudar a variância de lugar. O grupo 'outros' mistura RJ (~61%) com MT (~34%) (CADERNO:681).

### agregador-5 (agregador, esforço medio) — Demanda corporativa revelada do TotalPass contra a receita de TotalPass, e não contra o total

**Hipótese.** Um membro de TotalPass só gera receita de TotalPass. Medido contra o faturamento total (T14) e contra a proporção de alunos (X3), o sinal se dilui no balcão e no Wellhub. Contra fin_totalpass (8% da receita; uni09/protocolo_uni09.md:27) e contra a parte agregador, ele mede o mecanismo direto. É o 'benefício da empresa' que os escritórios a pé tentaram medir pela contagem de estabelecimentos.

**Dado.** LOCAL_demanda_totalpass_por_unidade.parquet: CITADO, NÃO aberto. Foi lido no UNI-01 (T14, N = 39) e no mix (N = 37 na exploração, 13 na confirmação). Deriva de data/staging/demanda_revelada_h3.parquet: 16.575 hexágonos H3 res-7, com as colunas membros, n_acad_parceiras e alunos_parceiras (DEC-012). A fonte tem ~66% em SP (mix/protocolo_mix.md:97), é foto atual e é centrada na Smart Fit (docs/decisions/DEC-012.md:4). É só local e não pode ir à produção (uni01/protocolo_uni01.md:70). Conhecido antes de abrir: sim para um ponto novo; no treino é anacrônico. Alternativa para medir o mecanismo: emprego formal privado (CAGED/RAIS), proposto e nunca medido (CADERNO:672-673; tasks/backlog.md:5668).

**Já testado.** T14 contra o total: +14,4%, candidata, mas só +2,9% na sensibilidade A (uni01/resultado_uni01.md:31). X3 contra a proporção: +11,1 p.f. em 2025, e PIOROU nas novas, de 7,1 para 8,9 (mix/resultado_mix_alunos.md:18,32). Escritórios a pé dentro da parte agregador do UNI-09: pioram (LOO −1,3 pp, teste −1,0 pp; uni09/resultado_uni09.md:43). O inventário já pedia excluir a própria Ultra e medir na turma (CADERNO:1131; tasks/backlog.md:5831). Contra a receita de TotalPass ou de agregador: nunca testado.

**Ganho esperado.** Pequeno no total: o TotalPass é 8% da receita, e o teto fica perto de 1 pp. O valor está no mecanismo e no planejamento do TotalPass por praça.

**Riscos.** Endogeneidade: se a foto inclui membros que já treinam na Ultra, a variável é o próprio desfecho, e excluí-los exige refazer a agregação na origem. A cobertura é fraca fora de SP: ausência quer dizer sem cobertura, não sem demanda. A DEC-012 proíbe usar 'membros' como insumo de regressão geográfica de demanda (DEC-012.md:9). No estudo pode-se contrariar a DEC, mas o resultado NÃO sobe à produção sem DEC. A fonte é LOCAL_ e as saídas só podem ser agregadas. A variável já falhou duas vezes em perguntas vizinhas.

### agregador-6 (agregador, esforço medio) — Agregador = passagens × receita por passagem, com as trocas de tier datadas pelo degrau na receita por passagem

**Hipótese.** A receita de agregador tem duas peças com causas diferentes. As passagens (check-ins) dependem da praça e do mercado. O valor pago por passagem depende do tier e da tabela do agregador (uni09/protocolo_uni09.md:113). Modelar as duas em separado diz se o erro do agregador é de volume ou de preço. A série mensal da receita por passagem mostra também QUANDO o tier mudou (um degrau na série), o que troca a foto de ago/2026 por um histórico. Exemplo de evento que o modelo de nível não enxerga: em Suzano, os agregadores caíram de 2.964 para 919 entre abr e ago/26 (uni01/anatomia_erros.md:13).

**Dado.** fato_unidade_mes: passagens_gympass e passagens_totalpass (DICIONARIO_UNI00.md:23-24; cumulativas, último valor do mês), fin_gympass e fin_totalpass (DICIONARIO:52-53). No treino de 2025, passagens de Wellhub > 0 em 468 de 468 meses-unidade (39 unidades); de TotalPass, em 444 de 468 (37). A série da Growth começa em 2022-04 (Wellhub) e 2022-06 (TotalPass); o Financeiro só tem TotalPass desde out/2023. Não é conhecido antes de abrir: é decomposição do mecanismo e fonte de histórico do tier.

**Já testado.** Nunca usado: passagens_* só aparece no dicionário e na cobertura (grep em data/analysis/uni). Parente próximo que falhou: alunos × ticket no total (Etapa 7, R² 0,30 → 0,27; CADERNO:332). Lá a divisão era pela contagem de alunos do UX, que não é limpa (CADERNO:522-534); aqui o divisor é a passagem, que é o que o agregador paga. Receita por aluno de agregador já medida: 47% da do recorrente (Wellhub 47%, TotalPass 50%; alavancas/resultado_alavancas.md:9), com a premissa mantida em 60%.

**Ganho esperado.** Primeiro é diagnóstico. Se a receita por passagem for quase toda tier + calendário, o agregador vira 'passagens × tabela', que é mais estável. O ganho no total é incerto (0 a −1 pp). O subproduto de mais valor é o histórico de tier por unidade, que alimenta o agregador-1 e o agregador-8.

**Riscos.** As regras de pagamento por visita (tetos por assinante, tabela por tier) não estão documentadas no repositório. A passagem pode ter o mesmo problema de limpeza da contagem de alunos: Setor Oeste recebia TotalPass 10 meses antes de o UX contar esses alunos (CADERNO:504-505). O atraso do Financeiro no agregador desalinha as competências (resultado_alavancas.md:85). Há risco de repetir a Etapa 7: separar em peças e piorar por variância.

### agregador-7 (agregador, esforço baixo) — Agregador como alvo móvel: idade do credenciamento e calibração de calendário do agregador por grupo de estado

**Hipótese.** Entre 2025 e 2026, nas MESMAS unidades maduras, a receita de agregador subiu +0,117 em log, enquanto o balcão caiu −0,062 (uni09/resultado_uni09.md:3). O agregador também entra devagar na vida da unidade: 18% dos alunos no mês 1 e 26% no mês 12 (CADERNO:164). O TotalPass chegou a SP em 2022–23 e ao DF em 2023–24 (alavancas/resultado_alavancas.md:15-42). Se o crescimento do agregador depende de há quanto tempo a unidade está credenciada e da região, uma calibração única de calendário erra por grupo. E foi justamente no teste, onde a calibração pesa, que as duas partes perderam 0,8 pp.

**Dado.** fato_unidade_mes: 1º mês com passagens_gympass / passagens_totalpass > 0 por unidade (DICIONARIO_UNI00.md:23-24). Na Growth desde 2022-04 (Wellhub) e 2022-06 (TotalPass); no Financeiro o TotalPass só aparece a partir de out/2023. Idade do credenciamento Wellhub no meio de 2025, no treino: menos de 12 meses em 2 unidades, 12–24 em 18, mais de 24 em 19. No teste (abertas em 2025), o credenciamento foi na abertura (atraso mediano de 0 mês). 4 maduras têm inauguração placeholder (DICIONARIO:59). Conhecido antes de abrir: credenciar na abertura é decisão, e a idade do credenciamento no futuro é calculável.

**Já testado.** Calendário por parte × calendário único: o único piora o teste, 22,1% → 23,8% (uni09/resultado_uni09.md:40). O controle 'jovem' entrou na proporção (mix/resultado_universo_cv.md:35). A rampa do agregador foi descrita (CADERNO:164). A idade do credenciamento como covariável e a calibração por grupo de estado nunca foram testadas.

**Ganho esperado.** O ganho fica no teste e na turma, onde o calendário pesa: pode recuperar os 0,8 pp perdidos no teste e algo mais. Nas 39 (LOO), quase nada.

**Riscos.** Calibrar por grupo, com poucas maduras em cada um (SP 16, DF 15, outros 8), acrescenta variância. Parte do efeito pode ser só nível, com o recentrado parado, e a regra da bateria não aceita isso (bateria/protocolo_bateria.md:286). A alta do agregador em 2026 pode ser de repasse ou de tabela, e não de demanda; nesse caso não se repete em 2027.

### agregador-8 (dado, esforço medio) — Coletar tier, data de credenciamento e tabela de repasse por unidade, com o tier declarado ANTES de abrir

**Hipótese.** Todas as variáveis próprias do agregador hoje são fotos de ago–set/2026 comparadas com o desfecho de 2025 (uni09/protocolo_uni09.md:112, 189-190). E o tier muda com o tempo: no TotalPass, cadastro e feed só concordam em 19 de 30 unidades do treino. Com o tier vigente em cada mês, a data de credenciamento e a tabela de repasse por tier, os testes do agregador-1, 3 e 6 deixam de ser associação e passam a usar variável conhecida antes do desfecho. O tier declarado nas fases 'assinada' e 'em implantação' é exatamente a entrada da v2 para um ponto novo.

**Dado.** Base Consolidada (Downloads/BASE UNIDADES_CONSOLIDADA.xlsx): CITADA, NÃO aberta; só scripts locais e derivados LOCAL_. Traz tiers de Wellhub/TotalPass, operador, modalidades e fase para 193 linhas: 98 em operação, 56 assinadas e 35 em implantação (memória base-consolidada-sensivel.md). Casa com 92 unidades por cod_cadastro. Complementos: o histórico do cadastro da VPS (cadastro_unidades.json, hoje só a foto de 06/08/2026; DICIONARIO_UNI00.md:109-111) e os contratos/tabelas de repasse do Wellhub e do TotalPass (Financeiro/Operações). A tabela de repasse não existe no repositório: 'repasse' só aparece em docs/ no sentido de pacote de passagem de trabalho. O snapshot semanal de concorrentes NÃO guarda plano nem preço (src/motor_expansao/vulnerabilidade/contrato.py:313-329), então não serve para reconstruir histórico.

**Já testado.** Não é teste; é coleta de dado. O backlog já listava 'aceite e tier de Wellhub/TotalPass por unidade (Base Consolidada, LOCAL)' como insumo do BLK-UNI-09 (tasks/backlog.md:5767), mas o UNI-09 usou só a foto do cadastro.

**Ganho esperado.** Habilita os testes limpos do agregador-1, 3 e 6 e dá o tier declarado da turma de 2026 e das 56 assinadas. Sem esse dado, a pista do tier continua presa a uma associação com foto posterior.

**Riscos.** A base é muito sensível: nada sai da máquina e só agregados podem ser gravados. A Base também é uma foto (01/10) e pode não ter histórico. A tabela de repasse pode ser confidencial por contrato. Credenciamento em andamento confunde 'não aceita' com 'ainda não aceita' (uni09/protocolo_uni09.md:131-134).

### estrutura-1 (estrutura, esforço baixo) — Treinar nas 57 (39 de 2025 + 18 de 2026) com calendário e coorte explícitos, e mover o teste para unidades que nenhum modelo viu

**Hipótese.** Parte do erro nas unidades novas vem da diferença entre turmas: os coeficientes estimados só nas maduras antigas não valem para as novas. No treino, quem tem estúdio não se desvia da previsão; no teste, fica +55% acima. A calibração 2025→2026 dá −6,2% no balcão e +11,7% no agregador. Outra parte vem da variância dos coeficientes: masters e estúdio foram estimados com 39 unidades, e o mr_M3 só com SP. A proposta é reestimar com as 57, trocando a mediana de calibração por efeito fixo de ano-calendário (2025/2026) e acrescentando um termo de turma de abertura (o ano de abertura é conhecido antes de abrir). Isso deve reduzir o viés na próxima turma.

**Dado.** fato_unidade_mes (faturamento do Financeiro, mes_vida, competencia; DICIONARIO_UNI00.md:5-75) + dim_unidade (tam_metragem_m2 54/98 + satélite 19; iso_*__carro_10 97/98; cad_mod_studios e master do cadastro, foto de 06/08/2026). Conferido nesta leitura (só cobertura): 57 unidades têm metragem, isócrona e ≥3 meses válidos com mes_vida≥12, sendo 39 em 2025 e 18 em 2026 (jan–set). Praça e m² são conhecidos antes de abrir. Estúdio e master são foto de ago/2026: o operador os declara antes de abrir, mas o dado é posterior ao desfecho do treino.

**Já testado.** O modelo nunca foi reajustado nas 57. Elas só foram juntadas como resíduos: o UNI-07 calibra a faixa com 39 LOO + 18 fora do tempo (uni07/resultado_uni07.md:13 e :23), e o item 1 da bateria usa o 'resíduo combinado (n = 57)' (bateria/protocolo_bateria.md:123-131). Nos dois casos o modelo continua ajustado só nas 39. A regra de método do epic prevê rolling-origin (tasks/backlog.md:5283-5284), mas só uma origem foi usada (dez/2025).

**Ganho esperado.** A variância dos coeficientes, sozinha, dá pouco: com 8 parâmetros, a alavancagem média cai de ~0,21 (39) para ~0,14 (57), o que tira ~0,5–0,7 pp do erro típico (23,5% → ~22,9%). Um ganho grande (2–4 pp) só existe se a diferença entre turmas for real, e é isso que a turma de 2026 vai dizer. O ganho certo: coeficientes de master e estúdio com 46% mais unidades, incluindo as primeiras unidades novas de cada grupo.

**Riscos.** Perde-se o teste das 18 como juiz (que, de todo modo, já foi consultado). O juiz passa a ser a turma de 2026, com só 5 unidades cegas (uni09/protocolo_uni09.md:151-155) e maturidade só por volta de meados de 2027. Por isso esta proposta depende das estrutura-2 e estrutura-6 para ter teste antes. Um termo de turma com só 2–3 turmas é fraco e pode virar 'ano = DF × SP'. O calendário de 2026 é parcial (jan–set), com sazonalidade diferente entre os conjuntos. É preciso congelar com SHA as previsões da turma antes de rodar.

### estrutura-2 (estrutura, esforço medio) — Desfecho de painel ajustado por maturidade e calendário (efeito da unidade), para incluir unidades jovens e conferir a turma ~6 meses antes

**Hipótese.** O desfecho de hoje é a média do log nos meses com mes_vida≥12 de um só ano, com no mínimo 3 meses. Ele descarta as unidades jovens e mede com ruído quem tem poucos meses. A proposta é estimar, no painel inteiro, log fat_it = α_i + mês-calendário_t + faixa de maturidade(mv) e usar α_i como desfecho, com peso pela incerteza. Assim entram as unidades com mv de 6 a 11, e a turma de 2026 pode ser lida com mv≥6 em vez de mv≥12.

**Dado.** fato_unidade_mes: 1.599 unidade-mês válidos com mv≥6 em 61 unidades com metragem e isócrona (64 com mv≥3), contra 57 na regra de hoje (conferido nesta leitura, só contagem). Curva: uni03/curva_uni03.csv. Turma: 16 unidades, as últimas abertas em jun/2026 (previsao_2026/leitura_precoce.md:9-19; uni09/protocolo_uni09.md:154). É o próprio desfecho mensal do Financeiro e da Growth; não é conhecido antes de abrir.

**Já testado.** Já existe como 'Sensibilidade A' do UNI-01 (uni01/01_exploracao.py:83-108; uni01/protocolo_uni01.md:20-26): 55 unidades, com efeito da faixa f06 −0,081, f09 −0,025, f12 +0,017 e f18 −0,007 contra 24+ (uni01/resultado_uni01.md:8). Foi usada só como robustez das hipóteses da exploração (e em alavancas/01_alavancas.py:532). Nunca serviu de desfecho de treino da v2 nem das duas partes, nem na conferência da turma.

**Ganho esperado.** Em precisão, pequeno: +4 a +7 unidades com metragem hoje (+12 com a estrutura-6). O painel NÃO multiplica o N: as covariáveis são fixas por unidade, então o N efetivo continua sendo o número de unidades (~61–76), e não 1.599. O ganho real é de tempo e de ruído: (i) pela regra '≥10 maduras', a conferência da turma sai por volta de jan/2027 com mv≥6, em vez de jun/2027 com mv≥12 (estimativa pelas datas de abertura da leitura precoce); (ii) as unidades com 3 a 5 meses ganham um nível menos ruidoso, porque o efeito dos meses 6–8 (−8%) deixa de virar erro.

**Riscos.** A projeção do mês 6 erra ~8–9% (uni03/resultado_uni03.md:57-61), então a unidade jovem entra com ruído extra; pesar por 1/(σ²_modelo + σ²_projeção). Pôr unidades jovens no treino tira a turma do papel de teste: é preciso decidir antes, unidade por unidade, quem é treino e quem é teste. A faixa de maturidade é estimada com as mesmas unidades, o que dá uma circularidade leve. A leitura antecipada da turma precisa de regra escrita antes, porque a leitura precoce já mostrou o resultado de 11 das 16 (uni09/protocolo_uni09.md:151-155).

### estrutura-3 (estrutura, esforço baixo) — Encolher os efeitos de master e metrô (efeito aleatório) e aplicar ridge aos coeficientes da v2, sem acrescentar variáveis

**Hipótese.** Os termos de grupo da v2 são estimados com pouquíssimas unidades e se ajustam demais à amostra. Sinais disso: a master real sozinha piora o teste (21,5% → 31,0%); o mr_M3 é estimado só com SP; 'outras' soma +15% a uma master nova (Manaus). A proposta é puxar cada master e cada metrô para a média da rede na proporção do número de unidades (efeito aleatório), e encolher os coeficientes com um ridge cuja penalidade é escolhida por LOO aninhado. Isso reduz a variância das previsões, sobretudo para master ou estado novo. O efeito de metrô também capturaria padrões locais como a Baixada Santista (Santos +76%, Praia Grande +62%, Guarujá +46%; CADERNO_ESTUDO_UNI.md:286-289).

**Dado.** dim_unidade: master (de-para, 98/98) e master real M1–M7 do cadastro (alavancas/master_id_cadastro.csv); iso_metro (97/98; DICIONARIO_UNI00.md:165); cad_mod_studios (92/98, foto de 06/08/2026). Nas 57 há 19 metrôs: dois grandes (21 e 14 unidades) e 12 com uma unidade só (conferido nesta leitura). Master e metrô são conhecidos antes de abrir.

**Já testado.** Nunca foi testado (conferido por busca em data/analysis/uni: nenhum ridge, lasso, modelo misto ou hierárquico). O único ajuste 'robusto' foi o Huber de uni05/03_robusto.py, que dá menos peso às unidades extremas mas NÃO encolhe coeficientes: erro 22% → 23–25%, com previsões mudando menos de 4% (CADERNO_ESTUDO_UNI.md:472-474). Ridge 'com mais variáveis' NÃO é recomendado: as 22 características da anatomia (66 testes; CADERNO:296-299) e os 6 itens da bateria (bateria/protocolo_bateria.md:1171-1188) já deram nulo, e ridge sobre variáveis sem sinal empata ou piora. Prior vindo da Smart Fit também não: lá as inclinações são renda +0,019 e população +0,08, contra +0,218 e −0,113 na v2 (manaus_volume/resultado_smartfit_formal.md:17-26). Além disso, o KPI da Smart Fit só tem 'Alunos Totais SF', sem receita nem divisão balcão × agregador (data/validacao/KPIs_Smart_2025_02 (1).xlsx, aba Base), então ela não serve de laboratório para a parte de balcão.

**Ganho esperado.** De 0 a 2 pp no erro típico LOO. O ganho mais provável é nos casos extremos: previsões para master ou estado novo (expansão em MG, PR, ES, AM) e para metrôs com 1–2 unidades. Também ganha estabilidade: hoje, tirar uma unidade do treino (Carapicuíba) move o erro do teste de 22% para 27% (CADERNO:1183-1187).

**Riscos.** Com ~8 parâmetros, sobra pouco para encolher, e a escolha da penalidade com 39–57 unidades é ruidosa. O efeito de metrô só vale onde já há unidades (2 metrôs grandes) e pode reintroduzir o 'efeito SP' que a anatomia desmontou. Mudar a forma como a master entra é mudar a v2 adotada: decisão do Felipe.

### estrutura-4 (estrutura, esforço medio) — Total + proporção + aceite: v2 para o total, fatia de agregador por master/estado e um parâmetro de substituição (σ) estimado, no lugar da soma de duas partes

**Hipótese.** O UNI-09 mostrou que a master muda o MIX, e não o total (mr_M3 −0,39 no balcão e +0,98 no agregador; uni09/resultado_uni09.md:28), e que os erros das partes não se compensam (CADERNO:1324). O que sobra é um fator de volume comum às duas partes. Logo, somar as partes não tem como ganhar do total nas unidades que aceitam os dois agregadores. O valor da separação está só no aceite: total_sem_agregador = v2 × [(1 − a) + σ·a/0,60], em que a é a fatia de agregador prevista (regra de master/estado) e σ é a fração dos alunos de agregador que voltam pelo balcão.

**Dado.** fato_unidade_mes: fin_vendas_ux, fin_gympass (2147/2275), fin_totalpass (1899/2275; a linha do TotalPass só existe desde out/2023) e pagantes (DICIONARIO_UNI00.md:25, 51-53). Com eles se observa o aceite mês a mês. Aceite no cadastro (wh/tp_tem_agregador_cadastro, foto de 06/08/2026; DICIONARIO:245-247): sem algum agregador estão 2 de 39 no treino e 3 de 18 no teste (uni09/protocolo_uni09.md:28-34). Fontes para σ: (i) as unidades do RJ que não aceitavam até set/2026 — Botafogo (teste); Laranjeiras, Belford Roxo e Bonsucesso (turma); Bangu, Icaraí, Cachamorra, Caxias e São Gonçalo Centro (sem metragem; ver estrutura-6) —, com São Gonçalo Shopping, que aceita os dois, como contraste no mesmo mercado; (ii) o credenciamento do Wellhub no RJ desde set/2026, que vira um antes/depois na própria unidade em ~6 meses. O aceite é decisão do operador, conhecida antes de abrir; σ é um parâmetro de mercado.

**Já testado.** A soma de duas partes com fator de aceite e SEM substituição foi o UNI-09: LOO 23,5% → 22,2%, teste 22,1% → 22,9% (uni09/resultado_uni09.md:7-11). Nas 3 unidades do teste sem algum agregador, o erro foi de 68% para 82,5% (resultado_uni09.md:17-18), indício de substituição (CADERNO:1326-1331). A fatia por estado foi a Etapa 11 (64 unidades, LOO 12,7 → 9,8 pontos; CADERNO:666-670). σ nunca foi estimado: o protocolo diz que não é estimável no treino (uni09/protocolo_uni09.md:110-111), e só os limites σ = 0 e σ = 1 estão congelados para a turma (protocolo_uni09.md:142-144). Os eventos de entrada do TotalPass foram inconclusivos (3 limpos), e há só 1 saída de agregador analisável (alavancas/saidas_agregador.csv; CADERNO:516). Alunos × ticket (Etapa 7) piorou (0,30 → 0,27; CADERNO:331-333). Um 'modelo conjunto' tipo SUR NÃO muda a previsão central: com as mesmas covariáveis nas duas equações, SUR é idêntico a MQO equação a equação (teorema de Zellner); a covariância entre as partes só serve para a faixa.

**Ganho esperado.** Zero nas unidades que aceitam os dois agregadores: por construção, a previsão é a própria v2. Nas que não aceitam, o ganho pode ser de dezenas de pontos (hoje o erro é de 68–83%), e são justamente a expansão do RJ e 9 das 16 unidades da turma (pelo cadastro). No erro típico das 18: ~0–1 pp.

**Riscos.** σ é identificado com poucas unidades e se confunde com a demanda excepcional (Botafogo) e com o mercado do RJ. A foto do cadastro de ago/2026 mostra, na maior parte, credenciamento em andamento (uni09/protocolo_uni09.md:129-137). O RJ passou a aceitar Wellhub em set/2026, então essas unidades mudam de regime no meio da janela. Depende da metragem das unidades do RJ (estrutura-6). A premissa de 60% é decisão do Felipe (a conta Financeiro ÷ UX dá 47%).

### estrutura-5 (estrutura, esforço baixo) — Forma funcional da população e extrapolação fora da faixa do treino (cidade pequena / isócrona curta)

**Hipótese.** A v2 tem elasticidade NEGATIVA à população (−0,149 [−0,27; −0,02]; uni09/resultado_uni09.md:26). Num modelo log-linear, isso faz a previsão SUBIR quando a praça é pequena. Só que, em cidade pequena e isolada, a isócrona de 10 min cobre a cidade inteira: pouca população é mercado pequeno, e não pouca concorrência. As unidades abaixo da população mínima do treino (68.231) erram todas para cima: Mococa, com 59.472 habitantes (−53%), e Unaí, com 66.871 (−21%). Na turma, Buritis (46.177) já projeta −59% na leitura precoce, e Bertioga tem 32.956. A proposta é limitar as covariáveis à faixa vista no treino (sem nenhum parâmetro novo) ou trocar o log da população por uma forma com saturação (por exemplo, a população do município quando a isócrona cobre a cidade).

**Dado.** dim_unidade: iso_pop__carro_10 e iso_area_km2__carro_10 (97/98; DICIONARIO_UNI00.md:129, 132; Censo 2022 + isócronas v2) e tam_metragem_m2. Conferido nesta leitura, só nas covariáveis: a população do treino vai de 68.231 a 1.328.219. Fora dessa faixa, no teste: Mococa e Unaí (abaixo), Butantã (1.339.104, acima), além de Cotia e Cambuí (uni02/resultado_uni02.md:7); na turma: Buritis-MG e Bertioga. Isócronas mais curtas da rede (p25 da área = 55,5 km²): Jardim Apura 17,4 km² (erro −34%), Cidade Ocidental 20,9, Buritis 25,8, Bertioga 28,2, Boqueirão 29,0 e Carapicuíba 30,1. Tudo é conhecido antes de abrir.

**Já testado.** Nunca foi testado (conferido por busca em data/analysis/uni: nenhuma forma não linear, limite à faixa do treino ou recorte de cidade pequena). O UNI-02 só listou as 5 unidades fora da faixa (uni02/resultado_uni02.md:7). O relatório de isócronas mostrou que o desenho da isócrona não acrescenta e que o que muda é o tamanho (data/analysis/isocronas/relatorio_isocronas_2026-09-25.md:11); não é o mesmo teste.

**Ganho esperado.** Na mediana das 18, ~0–1 pp, porque atinge 2–5 unidades. Por unidade, o ganho é grande: em Mococa, a população pequena soma ~+0,28 em log à previsão, comparada a uma praça de população mediana (log(59/398) × −0,149), cerca de um terço do erro em log. Na turma, Buritis e Bertioga são um teste direto, e a regra é escrita sem conhecer o resultado delas.

**Riscos.** Com 39–57 unidades, qualquer forma não linear se ajusta demais à amostra; por isso é melhor limitar à faixa do treino, que não estima nada. O erro de Mococa pode ser da operação e não da praça. Isócronas curtas também aparecem no litoral com erro POSITIVO (Santos, Praia Grande), então 'isócrona curta' não aponta numa direção só; só a regra da população pequena é testável. Escrever a regra antes de a turma amadurecer.

### estrutura-6 (dado, esforço medio) — Metragem oficial das 16 unidades sem m² (inclusive as de shopping, que o satélite não mede), formando uma 'turma B' quase cega para teste já

**Hipótese.** O gargalo do N não é o painel, é a metragem. Dezesseis unidades abertas até abr/2026 ficam fora de TODO modelo porque não têm m²: 12 delas têm ≥5 meses válidos com mv≥6, e 3 já são maduras. Elas nunca receberam previsão da v2, então formam um teste quase cego. Esse teste fica disponível agora com o desfecho da estrutura-2, ou por volta de jan/2027 com mv≥12, em vez de esperar a turma de 2026 até meados de 2027. Duas delas, Bangu e Icaraí (RJ, sem agregador no cadastro), são justamente as que faltam para medir o aceite (estrutura-4).

**Dado.** Conferido nesta leitura, só cobertura: boa-vista-ba (13 meses com mv≥12), ceilandia-qnm33-df (4), bangu-rj (3); icarai-rj, berrini-sp, patio-brasil-df, center-shopping-mg, sagrada-familia-mt, sao-goncalo-shopping-rj, flow-pr, picarras-sc e villa-branca-sp (5–7 meses com mv≥6); e as jovens vicente-pires-rua-8-df, visconde-de-rio-claro-sp, boqueirao-sp e sao-carlos-centro-sp. A coleta por satélite marcou 6 delas como 'sem metragem' (shopping/galeria; coleta_metragem/metragem_estimada*.csv). Fontes possíveis: contrato de locação ou projeto da franquia, ou a Base Consolidada (pode ser CITADA; é muito sensível e só pode ser lida localmente). A metragem é conhecida antes de abrir.

**Já testado.** O pedido está aberto como item 4 do BLK-DADOS-UNI-01 ('o que mais aumenta a amostra'; tasks/backlog.md:6191-6193) e virou cobrança a terceiros. A coleta por satélite (Etapa 8) deu 19 medições válidas + 10, com erro de 20% e sem medir shoppings (CADERNO_ESTUDO_UNI.md:359-367). Nenhum modelo foi avaliado nessas 16 unidades.

**Ganho esperado.** N de treino de 57 para até ~69 (+21%). Sobretudo, um juiz independente de ~12 unidades meses antes da turma, que é o que falta para confirmar qualquer ganho de 1–2 pp. Junto, conferir a metragem de Cotia (750 m² na oficial × ~1.050 medidos; CADERNO:367) e a de Botafogo (1.230 m² para ~4.000 alunos de balcão).

**Riscos.** Depende de terceiros (franqueado e operação). As unidades não são 100% cegas: o faturamento delas já apareceu em descritivos (Etapa 11 e comparáveis de renda baixa). A metragem de shopping pode vir como área bruta locável e não como área útil; registrar a definição. Congelar as previsões ANTES de olhar o desfecho delas.

### estrutura-7 (dado, esforço medio) — Auditoria dirigida dos maiores erros e das covariáveis que mais pesam no ajuste, com checklist escrito antes

**Hipótese.** Parte dos maiores erros pode ser de dado (metragem, pino, isócrona, receita) e não da praça. A proposta é uma auditoria com checklist fixado antes de olhar a direção do erro: metragem real, andares, pino, isócrona degenerada e meses do Financeiro. Corrige-se o que for erro provado, e o resto fica como está (regra 4 do epic: nenhum outlier é excluído para melhorar a métrica; tasks/backlog.md:5287).

**Dado.** Alvos: os 6 maiores erros do teste — Botafogo +185%, Cariacica +100%, Butantã +90% (metragem por satélite), Noroeste +59%, Valparaíso +50% e Mococa −53% (uni02/resultado_uni02.md:34-51); as 6 isócronas abaixo de 31 km² (estrutura-5); Cotia; as anomalias do Financeiro (Suzano com −52% de ativos, Brasilândia e Vila Guilherme com vale de −45%; tasks/backlog.md:6213-6215); os 16 meses com R$ 0 e academia operando (backlog:6194-6199); e o Guarujá ago/26 desatualizado na cópia da VPS (backlog:6181-6189). Colunas: tam_metragem_m2, lat/lng, iso_area_km2__carro_10, fin_* e flag_erro_dado (5/98).

**Já testado.** A anatomia dos erros conferiu o dado só nos casos extremos e achou erro apenas em Suzano (CADERNO_ESTUDO_UNI.md:300-303). Botafogo foi conferido na RECEITA ('real e consistente'; backlog:5419-5420), não na metragem. Dar menos peso aos extremos no ajuste (Huber) não melhorou: 22% → 23–25% (CADERNO:472-474). Os pinos de Plaza Sul e Sagrada Família já foram corrigidos (backlog:6167-6180).

**Ganho esperado.** Baixo no número de cabeça: o erro típico é uma MEDIANA, que não se move ao corrigir 2–3 extremos (<0,5 pp), e o modelo já não era puxado por eles. O ganho é de exatidão nas unidades afetadas e na elasticidade ao m², porque erro de medida no m² puxa o coeficiente para zero. Vale como higiene antes de reajustar nas 57.

**Riscos.** Tentação de 'corrigir' só o que contraria o modelo; por isso o checklist vem antes e vale para todos os alvos, inclusive os que o modelo acerta. Depende de terceiros para confirmar. Não confundir unidade excepcional (Botafogo) com erro de dado.

### estrutura-8 (estrutura, esforço baixo) — Previsão em dois tempos: a v2 como ponto de partida, atualizada pela pré-venda e pelos meses 0–3 (horizonte)

**Hipótese.** O erro que sobra é um fator de volume da própria unidade, que nenhuma variável de praça mede, mas que aparece nos primeiros meses. Combinar a v2 (desvio-padrão de ~0,37 em log; uni07/resultado_uni07.md:13) com a projeção pelo mês k do UNI-03, cada uma pesada pela sua precisão, deve dar, logo depois da abertura, uma previsão do nível maduro melhor que cada uma sozinha. A pré-venda (vendas do mês 0) pode antecipar isso para o dia da inauguração.

**Dado.** dim_unidade: rampa_vendas_m0 e rampa_novos_alunos_m0 (86/98), rampa_ativos_m1 (86/98) e rampa_ativos_m3 (75/98) (DICIONARIO_UNI00.md:274-297). Conferido nesta leitura: mês 0 e mês 1 existem em 30 das 39, 18 das 18 e 16 das 16 da turma; o mês 3, em 30, 18 e 11. Os meses anteriores à inauguração não têm venda registrada no painel. rampa_n_alunos_prevenda está vazia (0/98; DICIONARIO:320), à espera do export do Lifetime (BLK-UNI-PEND-01). Nada disso é conhecido antes da decisão de abrir: serve à operação (UNI-06) e à conferência, não à escolha do ponto.

**Já testado.** O alerta do mês k foi comparado só com a regra da metragem, nunca com a v2: erro de 22% antes de abrir, 21% no mês 1 e 9% no mês 3 (uni03/resultado_uni03.md:57-63). A combinação com a v2 nunca foi feita, e o mês 0 / pré-venda nunca foi usado para prever (conferido por busca em data/analysis/uni).

**Ganho esperado.** Teórico, se os erros forem independentes: no mês 1, ~21% → ~16% em alunos; no mês 3, pouco além dos 9% do mês 3 sozinho. Não melhora a previsão antes de abrir. Melhora a revisão logo depois da abertura e dá à turma uma leitura antecipada coerente com a v2.

**Riscos.** Os erros da v2 e do mês k podem andar juntos (a praça forte já abre forte), o que reduz o ganho da combinação. A curva é de alunos, e o faturamento cresce mais devagar (52% contra 68% no mês 1; CADERNO_ESTUDO_UNI.md:162-163). Se a pré-venda seguir uma meta do operador, ela mede esforço comercial e não demanda.

### estrutura-9 (estrutura, esforço baixo) — Régua de desenvolvimento com poder: validação repetida deixando de fora uma turma de abertura ou um metrô inteiro nas 57+, com erro em log, e a mediana só para comunicar

**Hipótese.** Os ganhos que ainda existem são de 1–2 pp, e a régua atual não enxerga isso. O '−2 pp' na mediana de 18 unidades tem IC de −9,8 a +2,9 pp (uni09/resultado_uni09.md:8), e tirar uma unidade do treino move o teste de 22% para 27%. A proposta é avaliar todas as unidades fora da amostra, deixando de fora, em rodadas repetidas, uma turma de abertura inteira ou um metrô inteiro, e decidir por uma métrica que usa todos os resíduos (erro quadrático médio em log, ou log-score). Isso dá ICs bem mais estreitos e permite escolher entre estruturas sem gastar a turma.

**Dado.** As 57 (e as ~12 da estrutura-6), com mes_vida, inauguracao (turma de abertura) e iso_metro (19 metrôs nas 57). Não precisa de dado novo.

**Já testado.** Em parte: 'retirando a cidade inteira' na Etapa 7 (uni01/resultado_duas_partes.md), 'deixando um metrô de fora' na Etapa 11 (mix/resultado_universo_cv.md) e bootstrap pareado da queda no UNI-09 e na bateria (bateria/protocolo_bateria.md:275-287). Deixar uma turma de abertura de fora (rolling-origin com várias origens) nunca foi feito, e a métrica de decisão sempre foi a mediana de |erro|, com a régua de ≥2 pp em c2/c3 (bateria/protocolo_bateria.md:78-91).

**Ganho esperado.** Nenhum ganho de precisão por si só. O ganho é na decisão: com ~3 vezes mais unidades avaliadas e uma métrica mais eficiente, o IC da diferença cai a cerca de metade (estimativa). Isso torna detectáveis as melhorias de 1–2 pp das outras propostas e evita adotar ruído, como a variante M3 da Etapa 7, que passou na régua por 0,003.

**Riscos.** Trocar a métrica depois de ver resultados parece mudar a regra no meio do jogo: é preciso pré-registrar antes de rodar qualquer estrutura nova e manter a mediana como número de comunicação. A validação por turma tem poucas rodadas (3–4 turmas), e os metrôs são desbalanceados (21 e 14 unidades em dois deles). A palavra final continua sendo da turma congelada, e a adoção é decisão do Felipe.
