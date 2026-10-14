# BLK-UNI-05C — O que explica a fatia do agregador (recorrente × agregador)

Versão 1.0, 2026-09-29. Escrito antes de rodar e revisado por um revisor adversarial antes de rodar (§8). Só análise.
Sugestão do Felipe.

## 1. Pergunta

Alguma característica **conhecida antes de abrir** explica quanto da receita de uma unidade vem de agregador
(Wellhub + TotalPass)? Se sim, a v2 pode ajustar o mix por praça em vez de usar o mix padrão, e o operador sabe o
que esperar antes de decidir aceitar agregador.

**Já feito antes (UNI-01):** T02 (renda → fatia de alunos de agregador) e T04 (tier Wellhub → fatia de alunos), os
dois inconclusivos. Ambos usavam a **contagem** de alunos do UX, que não é limpa. Aqui o desfecho principal é a
**receita**, do Financeiro.

## 2. Desfecho

- **Principal:** fatia do agregador na receita bruta: `pct_agregador_receita_fin` = (Wellhub + TotalPass) ÷ (vendas
  + Wellhub + TotalPass), do Financeiro. É a média dos meses válidos.
- **Secundário, só descritivo:** fatia nos alunos (`pct_agregador_ativos`, UX), com a ressalva da contagem.

## 3. Amostras

- **Exploração:** unidades com ≥ 3 meses válidos em jan–dez/2025, com `mes_vida` ≥ 12.
- **Confirmação:** unidades com ≥ 3 meses válidos em jan–ago/2026, com `mes_vida` ≥ 12, que **não** estão na exploração
  **e** eram novas: `mes_vida` < 12 em dez/2025, ou ainda não abertas. Ela é definida primeiro, e nenhuma unidade dela
  entra em sensibilidade da exploração.
- **Aceitação, medida no Financeiro em cada janela:**
  - "aceita Wellhub" = receita de Wellhub > 0 em ≥ 50% dos meses usados;
  - o mesmo para o TotalPass.

  Aceitar um ou os dois é política do operador ou da regional e mexe mecanicamente na fatia. Por isso:
  - **a amostra principal é a das unidades que aceitam os dois;**
  - a **sensibilidade S** usa todas as que aceitam pelo menos um, com "aceita Wellhub" e "aceita TotalPass" como
    controles.
- **Fora:** unidade que não aceita nenhum (política; fatia zero por construção).

## 4. Candidatas (uma por vez, com renda e população da isócrona de 10 min de carro como controle)

| id | X | variável | natureza | sinal esperado | por quê |
|---|---|---|---|---|---|
| X1 | renda da praça | log `iso_renda_pc__carro_10` (controle só população) | **antes de abrir** | ± | benefício corporativo × poder de pagar o plano |
| X2 | escritórios a pé | `poi_F1` | **antes de abrir** | + | Wellhub/TotalPass vêm como benefício do empregador |
| X3 | demanda revelada de TotalPass | log(1 + `tpd_membros_por_mil_hab_c10`), fonte só local | foto atual | + | mais usuário de agregador por perto |
| X4 | tier do Wellhub | `wh_ord_ultra_cadastro` | decisão do operador | ± | tier alto: menos planos dão acesso, mas cada visita paga mais |
| X5 | independentes no agregador | log(1 + `iso_n_independente_agregador__carro_10`) | foto atual (feed set/26) | ± | disputa pelo usuário × mercado acostumado ao agregador |
| X6 | preço do plano Gold | `cad_preco_gold` | decisão do operador | ± | plano caro empurra para o agregador, mas também sobe a receita de balcão (o denominador) |
| X7 | em shopping | `poi_em_shopping` | **antes de abrir** | ± | fluxo de passagem |

**Só X1, X2 e X7 podem alimentar um ajuste de mix na v2.** X3 a X6 são fotos atuais ou decisões do operador e servem
para ler o mecanismo.

- **Ajuste:** MQO; ΔR² LOO contra só os controles; retirada de cada metro; `h_max` reportado.
  - X contínuo é padronizado: efeito em pontos de fração por 1 desvio-padrão.
  - **X7 (binário) não é padronizado:** efeito = diferença bruta, shopping × não. Exige ≥ 5 unidades em cada classe,
    senão "sem amostra".
- **Inferência:** IC 90% HC3 e também **IC agrupado por metro** (CR1, G − 1 graus de liberdade), porque a política
  comercial se agrupa por região.
- **Sensibilidades:**
  - A = meses com `mes_vida` ≥ 6 em 2025, sem as unidades da confirmação;
  - B = jan–set/2025;
  - S = todas as que aceitam pelo menos um agregador, com a aceitação como controle;
  - C = sem as unidades com `anomalia_conferir`.

  Só A e B entram na classificação; S e C são reportadas. Também se reporta a retirada de cada UF.
- **Classificação:** regras do UNI-01 (§6), com a faixa de irrelevância mantida explicitamente em ±5 pontos de fração
  (por desvio-padrão; no X7, na diferença bruta). O desvio-padrão da fatia entre unidades é reportado, para leitura da
  faixa.
  - **Candidata passa a exigir também o IC agrupado por metro excluindo zero.** Se só esse falhar, vira "fraca".
- São 7 testes a 10%: espera-se ~0,7 falso positivo. Reportam-se também as correlações entre os X: X2, X3 e X5 podem
  ser o mesmo sinal de "SP denso".
- A fonte do X3 é só local: a saída carrega apenas o coeficiente, nenhum valor por unidade.

## 5. Confirmação

Para cada candidata, ajusta-se controles + X na exploração e prevê-se a fatia na confirmação. Compara-se com só os
controles, nas mesmas unidades:
- erro médio absoluto (pontos de fração) e Spearman;
- diferença com IC 90% por bootstrap (2.000 reamostras).

"**Consistente**" exige três coisas: o erro cai, o Spearman não piora **e** o limite superior do IC 90% da diferença
de erro fica abaixo de zero. Reporta-se também o erro com o intercepto reajustado na confirmação, que tira o efeito de
nível de 2026. Reporta-se para todas as X, mas só as candidatas contam como achado.

## 6. Descritivo

Fatia (receita e alunos) por UF e por regional do Growth. A coluna `master` é a sigla regional, que cobre até 3
masters (DEC-053). A diferença entre estados pode ser política comercial, e não característica da praça. O descritivo
serve para ler isso.

## 7. Limites

- N ≈ 40 na exploração e ≈ 20 na confirmação.
- Os estados se confundem com as variáveis: SP tem mais escritório e mais agregador. A retirada de cada metro é a
  defesa parcial.
- Tier, preço e agregador são decisões do operador: associação, não causa.
- **X3:** a fonte é metropolitana, com ~66% em SP. Fora de SP, "pouca demanda" pode ser só pouca cobertura, e ainda
  falta confirmar o que a fonte conta.
- **Faixa de irrelevância:** foi calibrada no UNI-01 para a fatia de alunos. A fatia de receita varia menos, então ±5
  p.f. é uma faixa relativamente larga.

## 8. Revisão antes de rodar (2026-09-29)

Um revisor adversarial leu a 1ª redação sem rodar. O que mudou:
- aceitação medida no Financeiro por janela, com a amostra principal "aceita os dois" e a sensibilidade S;
- confirmação só com unidades novas, sem sobreposição com a sensibilidade A;
- sinais de X4 e X6 passam a ±;
- natureza de cada X explícita, e só X1, X2 e X7 elegíveis para a v2;
- IC agrupado por metro exigido para "candidata", e retirada de cada UF reportada;
- X7 sem padronizar, com mínimo de 5 unidades por classe;
- "consistente" com o IC abaixo de zero e erro com intercepto reajustado;
- sensibilidade C, sem anomalias;
- correlações entre os X;
- R² base na amostra comum;
- `01_exploracao.py` no congelamento.

## 9. Versão 1.1 (2026-09-29): desfecho principal passa a ser o volume

Correção do Felipe depois da v1.0: a pergunta é o **volume**, ou seja, a proporção de alunos ativos recorrentes ×
agregadores, e não a receita.
- **Desfecho principal da v1.1:** `pct_agregador_ativos` = agregadores ÷ ativos (contagem do UX), média dos meses
  válidos.
  - **Ressalva:** a contagem de agregadores do UX não é 100% limpa (decisão do Felipe sobre a premissa de 60%).
  - Na v1.0, a fatia na receita e a fatia nos alunos tiveram Spearman +0,96: ordenam as unidades quase igual.
- **Não muda:** amostras, aceitação (medida no Financeiro), candidatas, regras, sensibilidades, confirmação.
- **Faixa de irrelevância:** ±5 p.f. por desvio-padrão. É a do UNI-01, calibrada para a fatia de alunos.
- **A v1.0 (receita) foi rodada antes da correção.** Fica como secundária, em `resultado_mix_receita.md` e
  `mix_testes_receita.csv`.

Arquivos: `mix/01_mix.py alunos` → `resultado_mix_alunos.md`, `mix_testes_alunos.csv`. `mix/01_mix.py receita`
reproduz a v1.0. Congelamento em `REGISTRO_CONGELAMENTO.txt`.

## 10. Versão 1.2 (2026-09-29): confirmação ampliada (volume)

Pedido do Felipe: confirmar com mais unidades, sem esperar a turma de 2026 amadurecer. Fixado antes de rodar.

**Amostra ampliada:**
- unidades fora da exploração, novas (`mes_vida` < 12 em dez/2025, ou ainda não abertas);
- que aceitam os dois agregadores (Financeiro);
- com **≥ 3 meses válidos em jan–ago/2026 e `mes_vida` ≥ 6** (antes era ≥ 12);
- desfecho: a média da proporção de agregadores nos ativos nesses meses.

**Por que a correção de nível:** checado antes, sem os X. A proporção nos meses 6–8 fica ~8 p.f. **abaixo** da
madura (mediana), mas a ordem das unidades já está definida (Spearman 0,86 com a madura, N = 54). As unidades jovens
têm, portanto, nível mais baixo, e a comparação principal é de **ordem e de erro com o nível corrigido**.

**Métricas** (modelos ajustados na exploração de 2025, como na §5):
- Spearman;
- **erro médio absoluto depois de reajustar o intercepto** na amostra ampliada;
- erro bruto, só reportado.

**Leitura:** "**consistente**" se o erro reajustado cai, o Spearman não piora **e** o limite superior do IC 90%
(bootstrap, 2.000 reamostras) da diferença do erro reajustado fica abaixo de zero.
- Vale para as 4 candidatas da v1.1 (X2, X3, X5, X6). As demais são reportadas.
- **Só X2 (escritórios a pé) é conhecida antes de abrir e pode ir à v2** (§4).

**Sensibilidade:** só as unidades com `mes_vida` ≥ 9, com a mesma regra.

Arquivos: `mix/02_confirmacao_ampliada.py` → `resultado_confirmacao_ampliada.md`.

## 11. Versão 1.3 (2026-09-29): universo inteiro com validação cruzada, para decidir o mix da v2

Pedido do Felipe:
- usar também as unidades que aceitam **só um** agregador (a política pesa pouco; na sensibilidade S da v1.1 o efeito
  de escritórios foi +7,8 × +7,9);
- avaliar se o mix entra no modelo.

Fixado antes de rodar.

**Universo:**
- todas as unidades com ≥ 3 meses válidos com `mes_vida` ≥ 6 entre jan/2025 e ago/2026 que aceitam **pelo menos um**
  agregador (Financeiro). As que não aceitam nenhum ficam fora (proporção zero por política);
- desfecho: média da proporção de agregadores nos ativos (UX) nesses meses.

**Controles (todos os modelos):**
- renda e população da isócrona de 10 min de carro;
- **"jovem"** = mês de vida médio dos meses usados < 12. A proporção ainda sobe até a maturidade (§10);
- **"só um agregador"**. A versão sem esse controle é reportada.

**Candidatas (todas conhecidas antes de abrir):**

| id | variável | origem |
|---|---|---|
| E1 | escritórios a pé (`poi_F1`) | candidata da v1.1 |
| E2 | **escritórios privados** a pé: F1 sem administração pública (CNAE 84) e sem hospitais (8610) | nova, pelo mecanismo "benefício de empresa" (`poi/05c_f1_privado.py`; F1 recalculado bate 96 de 96 com o painel) |
| E3 | grupo de estado: SP / DF-GO / outros | pós-hoc da v1.2 |
| E4 | E2 + E3 | combinação |

**Validação** (contra o modelo só com controles, nas mesmas unidades):
- **LOO:** cada unidade prevista por um modelo ajustado sem ela;
- **por metro:** cada metrópole inteira prevista por um modelo ajustado sem ela, o que testa a transferência para uma
  região nova;
- métricas: erro médio absoluto (pontos de fração) e Spearman. IC 90% da diferença de erro LOO por bootstrap pareado
  de unidades (2.000);
- coeficiente de E1/E2 com IC agrupado por metro.

**Leitura** (é checagem; a decisão de adotar é do Felipe): "**melhora a previsão**" se:
- o erro LOO cai;
- o erro por metro cai;
- o Spearman LOO não piora.

**Não é confirmação independente:** E1 e E3 foram escolhidas com parte destas unidades. E2 é nova, mas a hipótese nasce
do mesmo quadro. Para a v2, reporta-se também a regra final (coeficientes ajustados no universo todo) e o seu efeito
prático em pontos de mix.

Arquivos: `mix/03_universo_cv.py` → `resultado_universo_cv.md`, `universo_cv.csv`.
