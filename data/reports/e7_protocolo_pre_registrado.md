# E7 — Protocolo pré-registrado: sobra sinal territorial em faturamento por m²?

> **Escrito em 2026-08-29, ANTES de medir qualquer relação.** Só o esquema e a cobertura
> dos dados foram inspecionados para dimensionar o teste. Nenhuma correlação, gráfico ou
> ajuste foi olhado antes de este arquivo existir.
>
> A razão de existir deste arquivo: nesta mesma reforma, uma correlação de **+0,32 com
> N=23** virou **−0,006 com N=85**. Critério escrito depois do resultado não é critério.

## Pergunta única

**Controlando maturidade, sobra sinal territorial em faturamento por m²?**

Nada além disso. CNAE fica **fora** — só entra se este teste der GO, e como bloco próprio.

## Por que a pergunta pode ser reaberta agora

Os 13 estudos anteriores (DEC-001, BLK-DIM-08, E3) foram **corte transversal sem data de
abertura**: comparavam unidades em maturidades diferentes como se fossem comparáveis. Uma
unidade de 8 meses e uma de 4 anos entravam na mesma regressão.

O `growth_api_historico.parquet` mudou isso: **102 unidades × dia, 2022-04-01 a
2026-08-03, com `inauguracao` preenchida em 100%**. Pela primeira vez dá para fixar a
maturidade antes de perguntar sobre território.

## Dados e N

| fonte | o que traz | N que casa com o painel |
|---|---|---|
| `growth_api_historico.parquet` | série diária, `inauguracao` | 102 unidades |
| `base_calibracao_maduras.parquet` | `metragem`, catchment 1,5 km (pop/renda) | **54** |
| `unidades_ultra_performance_hex.parquet` | `hex_id_res7`, lat/lng | 54 |

**N alvo = 54**, antes dos filtros de maturidade abaixo. O join é por nome normalizado
(ASCII, maiúsculas, sufixo ` / UF` e ` - UF` removidos) — sem essa normalização o
cruzamento cai para 19, e a primeira medição desta sessão caiu nessa armadilha.

## Desfecho

`faturamento_mensal / m²` no **regime maduro**, por unidade:

1. agrega o diário em meses-calendário completos;
2. mantém só meses com **maturidade ≥ 12 meses** desde a inauguração;
3. o desfecho é a **mediana** desses meses (robusta a mês atípico);
4. a unidade entra apenas se tiver **≥ 6 meses** observados no regime maduro.

Mediana e não média porque a série tem meses de ruptura (fechamento, reforma) que a média
puxaria.

## Preditores territoriais

Exatamente o que o motor serve hoje — testar features que o produto não tem seria testar
outra coisa:

1. `score_setor_2022_calibrado` (régua absoluta, DEC-040)
2. `renda_per_capita_setor_2022_calibrada`
3. `pop_total_setor_2022`
4. `oferta_efetiva_disponivel` (residual fitness)
5. `pop_captacao` (catchment 1,5 km)
6. `renda_per_capita_captacao` (catchment 1,5 km)

## Baselines

- **B0** — só o intercepto (a média da rede). É o piso: qualquer R² OOF ≤ 0 significa "pior
  que chutar a média".
- **B1** — só `metragem`. É o baseline HONESTO: se território só reproduz o efeito de
  tamanho, não acrescenta nada ao que a viabilidade já sabe.

## Método

- **Leave-One-Out CV** (N pequeno) **e** GroupKFold por UF (unidades da mesma UF caem no
  mesmo fold, para vizinhança não vazar entre treino e teste).
- Métrica: **R² out-of-fold**. In-sample é proibido — é o vício que a metodologia do
  BLK-DIM já rejeitou.
- Dois modelos, e **reporta-se o MELHOR** (favorece deliberadamente o GO): Ridge sobre
  features padronizadas e gradient boosting raso.
- IC de 95% por **bootstrap**, 2.000 reamostragens, `seed=42`.

## CRITÉRIO DE PARADA (escrito antes de rodar)

**GO** — só se as DUAS condições valerem:
1. o melhor R² out-of-fold for **> 0** com IC de 95% **excluindo zero**; **e**
2. o ganho sobre **B1** (metragem) for **positivo** com IC excluindo zero.

**NO-GO** — se o melhor R² OOF for ≤ 0, **ou** se qualquer um dos dois IC cruzar zero.

Consequência do NO-GO, aceita antes de medir: **a pergunta se fecha.** O motor assume em
definitivo o papel de **triagem territorial** — ranqueia praça, não prevê desempenho de
unidade — e isso passa a ser afirmado na tela em vez de reaberto a cada ciclo. CNAE não é
aberto.

## Limitação declarada ANTES do resultado

A amostra é **restrita às praças onde a Ultra decidiu abrir**. Isso é restrição de
amplitude: as praças ruins que o motor rejeitaria não estão na base, então a variação
territorial observada é uma fatia estreita da variação possível. **Restrição de amplitude
ATENUA correlação** — ou seja, o desenho é enviesado a favor do NO-GO.

Portanto:

- um **GO** aqui seria forte (achou sinal apesar do viés contrário);
- um **NO-GO** significa **"não há sinal utilizável dentro do universo em que a Ultra
  opera"**, e NÃO "território é irrelevante em geral".

A segunda leitura é a honesta, e é suficiente para a decisão de produto: o motor escolhe
onde a Ultra vai operar, então o universo relevante é exatamente esse.
