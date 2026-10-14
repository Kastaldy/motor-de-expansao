# BLK-UNI-01 — Protocolo da exploração de hipóteses (dados até dez/2025)

Versão 1.0, 2026-09-28. Escrito **antes** de olhar qualquer associação entre atributo e desfecho. O congelamento
(SHA-256 deste arquivo, do script e dos insumos) fica em `REGISTRO_CONGELAMENTO.txt`.

## 0. O que isto é e o que não é

- É **exploração**. Produz uma lista curta de hipóteses candidatas ao pré-registro do UNI-02. Nada daqui é confirmação.
- As três variáveis da base (m², renda e população na isócrona de carro 10 min) foram escolhidas antes, em dados que se
  sobrepõem a estes (set/25–ago/26). **Elas não estão sob teste aqui**; entram como controle.
- Rodar uma vez. Se um erro de código for achado depois, corrige-se, registra-se a versão nova e **as duas saídas ficam**.

## 1. Amostras

**Primária (maduras).** Unidades da rede comparável (`excluida_rede = False`) com pelo menos **3 meses válidos** em
jan–dez/2025 com `mes_vida >= 12`. Mês válido: `faturamento` do Financeiro presente, `mes_completo`,
`operacao_mes_cheio` e `ativos > 0`. Nas 4 unidades de inauguração placeholder, `mes_vida` = `mes_vida_minimo`
(limite inferior da idade; todas são antigas). N esperado: 40.

**Sensibilidade A (maturidade ajustada, mais unidades).** No painel unidade × mês inteiro até dez/2025
(`mes_vida >= 6`) estima-se `Y = efeito da unidade + efeito do mês-calendário + faixa de maturidade` (faixas 6–8,
9–11, 12–17, 18–23 e 24+, esta a referência). As unidades maduras o período todo identificam o efeito do mês; sem ele,
a faixa absorveria o crescimento nominal do R$ e do agregador de 2022 a 2025. As 4 unidades de inauguração
placeholder entram como 24+ em todos os meses (a idade delas é só limite inferior e todas são antigas). O nível da
unidade é a média de `Y − faixa − mês` nos seus meses válidos de **2025** com `mes_vida >= 6` (pelo menos 3). Nos
testes com o % agregador como X (T06, T07, T18), a sensibilidade A usa o % agregador ajustado da mesma forma.
N esperado: ~55.

**Sensibilidade B (janela curta).** Igual à primária, só jan–set/2025. Existe porque Brasilândia e Vila Guilherme têm
um vale de receita a partir de out/25 ainda sem explicação (anomalia a conferir, não excluída).

**Nenhuma unidade é excluída por ser atípica** (regra 4 do epic). Atributo com erro de dado conhecido já vem anulado no
painel (`flag_erro_dado`); a unidade fica fora só dos testes que usam aquele atributo.

## 2. Desfechos (nível unidade, média nos meses válidos da amostra)

| id | desfecho | escala |
|---|---|---|
| Y1 | faturamento mensal do Financeiro | média de `log(faturamento)` |
| Y2 | alunos ativos no fim do mês | média de `log(ativos)` |
| Y3 | ticket = faturamento / ativos | média de `log(faturamento/ativos)`; Y1 = Y2 + Y3 por construção |
| Y4 | % agregador nos ativos | média de `pct_agregador_ativos` (fração) |
| Y5 | churn mensal (Growth, cancelados / pagantes do mês anterior) | média de `churn_pct` (pontos percentuais) |

## 3. Base e modelo

Base B = `log tam_metragem_m2 + log iso_renda_pc__carro_10 + log iso_pop__carro_10`. Cada teste compara, **nas mesmas
unidades** (casos completos da base e do atributo), o modelo B contra B + X, por MQO. X é padronizado (média 0,
desvio 1) dentro da amostra do teste, então o coeficiente é "efeito de 1 desvio-padrão de X".
Quando X já está na base (renda), o teste é B contra B sem X. Os testes de interação incluem o efeito principal do
modificador.

## 4. Hipóteses e testes

| teste | hipótese | X | desfecho | sinal esperado | nota |
|---|---|---|---|---|---|
| T01 | renda × ticket | `log iso_renda_pc__carro_10` | Y3 | + | |
| T02 | renda × agregador | `log iso_renda_pc__carro_10` | Y4 | ± | |
| T03 | plano do agregador × ticket | tier Wellhub do cadastro (`wh_ord_ultra_cadastro`, ordinal) | Y3 | ± | foto ago/26 contra desfecho 2025 |
| T04 | plano do agregador × agregador | `wh_ord_ultra_cadastro` | Y4 | − | tier maior = assinatura mínima mais cara para entrar = menos assinantes elegíveis |
| T05 | preço relativo à concorrência | `wh_gap_ord_c10` (ordinal da Ultra − mediana dos concorrentes) | Y1 | ± | foto set/26 |
| T06 | agregador traz volume | média de `pct_agregador_ativos` na janela | Y2 | + | associação, não causa: o % é decisão e resultado ao mesmo tempo |
| T07 | agregador dilui ticket | idem | Y3 | − | idem |
| T08 | tamanho × praça boa (diretor) | `z(log m²) × z(log renda c10)` | Y1 | + | interação; poder baixo |
| T09 | tamanho × concorrência de estrutura menor (diretor) | `z(log m²) × z(fração de independentes na isócrona c10)`, fração = `iso_n_independente_agregador / iso_n_academias` | Y1 | + | interação; poder baixo |
| T10 | saturação da concorrência | `log conc_alunos_por_mil_hab__carro_10` | Y1 | − | premissa de alunos para cadeia sem dado (1.800) e independente (400); foto atual |
| T11 | saturação × volume | idem | Y2 | − | |
| T12 | crescimento do município | `cres_dim_media` | Y1 | + | valor do MUNICÍPIO: o DF é um só, e ~15 unidades repetem o mesmo X |
| T13 | crescimento do hexágono (satélite 2016–23) | `cres_hex_taxa` | Y1 | + | |
| T14 | demanda revelada TotalPass (**só local**) | `log(1 + tpd_membros_por_mil_hab_c10)` | Y1 | + | não pode virar variável de produção enquanto a fonte for só local |
| T15 | população a pé dentro da mesma cidade (pista do teste de POI) | `log iso_pop__pe_15`, com efeito fixo de metro | Y1 | + | metros com 1 unidade ficam fora deste teste |
| T16 | rampa prevê o nível maduro | `log rampa_ativos_m3` | Y2 | + | só operações (depois da abertura); não entra no modelo de expansão |
| T17 | renda × retenção | `log iso_renda_pc__carro_10` | Y5 | − | retenção da coorte de abertura segue pendente (BLK-UNI-PEND-01) |
| T18 | agregador × retenção | média de `pct_agregador_ativos` | Y5 | ± | |
| T19 | saturação × retenção | `log conc_alunos_por_mil_hab__carro_10` | Y5 | + | |

**Só descritivos (sem teste):** % agregador por UF (a RJ tem 1 unidade madura até dez/25, então a pergunta "RJ 0%"
não é testável aqui); correlação de Spearman entre tier do agregador e renda (o franqueado precifica pela praça?).

**Fora:** POIs (já testados com protocolo próprio em 2026-09-25, resultado nulo); retenção da coorte de abertura e
pré-venda (sem o export do Lifetime).

## 5. Estatística

Para cada teste, nas mesmas unidades:
1. **Efeito** de X com IC 90% por erro-padrão robusto HC3 e t com n − k graus de liberdade.
2. **Ganho fora da amostra:** ΔR² leave-one-out (fórmula fechada) de B + X contra B.
3. **Estabilidade geográfica:** o sinal de X quando se retira cada metro inteiro, um de cada vez (as unidades
   concentram-se em SP e DF; por isso não se usa erro-padrão por cluster com 13 clusters desbalanceados).
4. **Sensibilidades A e B:** o sinal de X nas outras duas amostras.
5. **Efeito mínimo detectável** com 80% de poder e α = 0,10 bilateral: `(t_0,95 + t_0,80) × EP`.

## 6. Regra de classificação (fixada antes)

Aplicada nesta ordem; vale a primeira que casar.

1. **Sem amostra:** menos de 12 unidades; no T12, menos de **8 municípios distintos**. O X do T12 é do município (o
   DF inteiro é um só), então lá o IC usa erro-padrão agrupado por município (CR1, t com G − 1 graus de liberdade) em
   vez do HC3, e a estabilidade é por retirada de município. Vira descritivo.
2. **Descartada** (sem efeito relevante): o IC 90% fica inteiro dentro da faixa de irrelevância — ±10% por
   desvio-padrão nos desfechos em log (Y1–Y3); ±5 pontos de fração em Y4; ±0,5 ponto percentual em Y5; ±0,15 na
   elasticidade ao m² por desvio-padrão do modificador (interações). Um efeito "significativo" mas pequeno demais para
   importar cai aqui. **Nas interações (T08, T09), com N ≈ 40, o IC tende a ser mais largo que a faixa: elas quase
   certamente não podem sair descartadas, só candidatas ou inconclusivas.** Isso é declarado agora para não ser lido
   depois como "não testamos direito".
3. **Contrária:** o IC 90% exclui zero com o sinal **oposto** ao esperado. É registrada como achado e não sobe
   automaticamente; a forma dela para o UNI-02 é decisão explícita, com justificativa escrita.
4. **Candidata:** o IC 90% exclui zero (com o sinal esperado, ou qualquer sinal quando "±") **e** vale tudo abaixo:
   ΔR² LOO > 0; o sinal se mantém em **todas** as retiradas de metro; mesmo sinal nas sensibilidades A e B.
5. **Fraca:** o IC exclui zero, mas falha pelo menos um critério do item 4. Uma sensibilidade sem amostra conta como
   falha, e o motivo aparece na tabela (coluna "falhou").
6. **Inconclusiva:** o resto (o dado não distingue efeito relevante de zero).

Com 19 testes a α = 0,10, cerca de 2 passam o critério do IC por acaso. Por isso a confirmação é outra etapa.

**O que sobe ao UNI-02 (modelo de expansão):** só testes com desfecho **Y1** e com X **conhecido antes de abrir** a
unidade: T05, T08, T09, T10, T12, T13 e T15. No máximo **2 variáveis novas** somadas à base, pela ordem de ΔR² LOO.
Os demais testes informam outras etapas:
- **UNI-06 (operações):** T06, T07 e T18 (o % agregador é decisão e resultado da operação, não existe antes de
  abrir), T14 (fonte só local) e T16 (rampa, só depois de abrir);
- **mecanismo:** T01, T02 e T17 (a renda já está na base; dizem por onde ela age: ticket, agregador ou churn), T03,
  T04, T11 e T19.

## 7. Limites declarados

- **Composição:** das 40 maduras, a maioria é SP e DF; a RJ tem 1. Efeito de UF não se separa de efeito de metro.
- **Fotos atuais contra desfecho de 2025** (planos, concorrência, POI, Lifetime): risco de causalidade reversa — por
  exemplo, concorrente que abriu perto de uma Ultra que já ia bem. A demanda revelada TotalPass (T14) tem **data e
  procedência não confirmadas**.
- **Confirmação do UNI-02:** as mesmas unidades em jan–ago/26 não são dado independente (receita da unidade é
  persistente). O teste de verdade são as **21 unidades que amadurecem em 2026**, e só **12 delas têm metragem**. A
  metragem das unidades novas (item 4 do BLK-DADOS-UNI-01) passa a ser o gargalo do UNI-02.
- Poder baixo: com N ≈ 40, só efeitos moderados a fortes aparecem; interações quase nunca.
- `log` de valor ≤ 0 vira ausente; o N de cada teste fica na tabela. (O script conta, por atributo, quantas unidades
  caem por isso.)
