# BLK-UNI-03 — Protocolo da curva de rampa observada

Versão 1.1, 2026-09-28. Escrito antes de olhar a curva. A v1.0 foi revista por um revisor adversarial antes de rodar
(11 achados, todos incorporados aqui). O congelamento (SHA-256 deste arquivo, do script e dos insumos) fica em
`REGISTRO_CONGELAMENTO.txt`. Roda uma vez; se um erro de código aparecer depois, as duas saídas ficam.

## 1. Perguntas

- **P1 — formato:** como os alunos (total, balcão e agregador) e o faturamento crescem nos meses 1 a 12 de vida, como
  fração do nível maduro da própria unidade? Mediana e faixa p10–p90.
- **P2 — curva × simulador:** a curva prevê o 1º ano de uma unidade nova melhor que a rampa do simulador?
- **P3 — alerta precoce:** com os alunos do mês 1, 3 ou 6, com que erro se projeta o nível maduro? E quanto isso é
  melhor que a projeção feita antes de abrir, pela metragem?
- **P4 — depois do mês 12:** a unidade continua subindo nos meses 13 a 24?

## 2. Definições

- **Unidade elegível:** inauguração real a partir de abr/2022 (as 4 de inauguração placeholder ficam fora; as abertas
  antes de abr/2022 não têm os primeiros meses no dado) e com nível maduro medido. O mês 1 não precisa estar completo.
- **Nível maduro `L`** de cada série: média dos meses de vida 11, 12 e 13 válidos (pelo menos 2 dos 3).
  - Justificativa (UNI-01, sensibilidade A): o faturamento nas faixas 12–17 e 18–23 fica a ±2% do de 24+ meses.
  - A P4 checa isso de novo (ver §6).
- **Séries:**
  - `ativos` (total), `pagantes` (balcão / recorrentes) e `agregadores` (Wellhub + TotalPass): válidos em mês com
    `mes_completo`;
  - `faturamento` do Financeiro: válido em mês de operação cheia com valor > 0. Não exige `mes_completo`, que é a
    completude da coleta da Growth.
- **Mês de vida `k`:** mês 0 é o da inauguração (parcial). A foto do fim do mês `k` corresponde a `t = k + f0` meses
  de operação, onde `f0` = fração do mês 0 com a unidade aberta = (dias do mês − dia da inauguração + 1) / dias do
  mês. O simulador é avaliado em `t`, para ter o mesmo tempo de operação que a foto.
- **Curva `c_s(k)`:** mediana, entre unidades, de `s(k) / L_s`, com p10 e p90.

## 3. Amostras

- **Exploração (monta a curva):** unidades elegíveis com inauguração + 13 meses ≤ dez/2025 (N ≈ 33).
- **Confirmação:** as demais unidades elegíveis com `L`, ou seja, cujo 1º ano fecha em 2026 (N ≈ 22, inauguradas de
  dez/2024 a ago/2025). Não entram na curva.
- A classificação é pela data de inauguração, não pela existência de linha no dado.

## 4. P2 — curva × simulador (critério fixado antes)

Para cada unidade da confirmação, dado o `L` realizado de `ativos`, compara-se:

| braço | previsão para o mês k |
|---|---|
| **curva** | `c_ativos(k) × L` |
| **simulador atual, modo padrão** (tela de viabilidade) | `a0 + (L − a0) × min(t/8, 1)`, com `a0 = min(500, L)` |
| **simulador atual, modo só balcão** (usado no lote e no risco) | balcão `b0 + (0,69·L − b0) × min(t/8, 1)`, com `b0 = min(500, 0,69·L)`, mais agregador `0,31·L` desde o mês 1 |
| **linear recalibrada** | a mesma reta, com `a0/L` e o mês de maturação ajustados na exploração (grade: `a0/L` de 0 a 1 em passos de 0,01; maturação de 1 a 12 meses), minimizando o erro médio dos meses 1–10 |

**Métricas por unidade** (só entra quem tem pelo menos 6 dos 12 meses válidos):
- (a) **média do erro absoluto percentual nos meses 1–10**. Os meses 11 e 12 fazem parte do próprio `L` e acertariam
  quase por construção;
- (b) **erro percentual na soma de alunos dos meses 1–12**, que é o que pesa no caixa e no payback.

As duas são resumidas pela mediana entre unidades; em (b), mediana de |b| e mediana de b (viés).

**Critério:** a curva **vence o simulador atual** (modo padrão) se tiver (a) **e** |b| menores na mediana. Também se
reporta em quantas unidades a curva erra menos em (a).

**Leitura fixada antes:**
- Se a linear recalibrada ficar a até 1 ponto de (a) da curva, a mensagem é "basta recalibrar os parâmetros 500/8"
  (troca mais simples no simulador).
- Se ficar além disso, a mensagem é "o formato da rampa importa".

**Sensibilidades:**
- simulador avaliado em `t = k`, sem `f0`;
- o mesmo teste no faturamento (secundário), com a rampa aplicada ao faturamento. Simplificação declarada: o
  simulador soma anuidade a partir do mês 12; aqui não.

**Limite:** o teste usa o `L` realizado, então mede só o formato da rampa. O erro da demanda madura é assunto do UNI-02.

## 5. P3 — alerta precoce

- **Projeção feita no mês `k`** (1, 3 e 6): `L̂_k = ativos(k) / c_ativos(k)`. Erro: `e_k = L / L̂_k − 1`.
- **Faixa de erro** (p10–p90 de `e_k`), medida na exploração com curva **leave-one-out**: cada unidade é projetada com
  a curva montada sem ela.
- **Na confirmação:** cobertura da faixa e mediana de `|e_k|`. Uma faixa p10–p90 empírica com N ≈ 33 cobre cerca de
  75% de uma unidade nova. Com 22 unidades, a cobertura é **compatível** se ficar entre 57% e 93%.
- **Antes de abrir × mês 3:** nas unidades da confirmação com metragem, `L̂_0` = p50 de
  `faixa_alunos_por_densidade(m², base)`. É a **função da viabilidade em produção**: janela de ±20% do m², ±50% se
  faltar comparável, depois a base inteira. A base são as unidades da exploração, com `alunos_por_m2 = L / m²`.
  Reporta-se a mediana de `|e|` de `L̂_0` contra `L̂_3` nas mesmas unidades. Exige pelo menos 8 unidades; senão, "sem
  amostra".

## 6. P4 — depois do mês 12, e o que ela muda

- `s(k)/L` para k = 13 a 24, com todas as unidades e dados até ago/2026 (mediana, p10, p90, N).
- **Consequência fixada antes:** a viabilidade parte da densidade das unidades maduras, e não do mês 12. Assim, se a
  mediana de `L_24 / L` (nível dos meses 22–24 sobre o dos meses 11–13, nas unidades que têm os dois) se afastar de 1
  por mais de 5%:
  - a curva também é publicada sobre o nível do mês 24, `c(k) × mediana(L / L_24)`;
  - é essa versão a recomendada para o simulador.

## 7. Descritivos

- Alunos medianos (absolutos) nos meses 0, 1, 3, 6 e 12 na exploração, contra os 500 iniciais do simulador.
- Participação do agregador em k = 1, 3, 6 e 12.

## 8. Limites declarados

- **Confirmação pequena:** 22 unidades, 7 delas no RJ e em MG, onde a exploração quase não tem unidades.
- **Viés de sobrevivência:** unidades que fecharam antes do mês 13 não entram; o script conta quantas são.
- **Fontes:** alunos vêm da Growth (foto do fim do mês); faturamento, do Financeiro.
- **Pré-registro imperfeito, declarado:**
  - o caderno do estudo já diz que "o 3º mês diz quase tudo" (achado T16 do UNI-01, feito com as maduras de 2025);
  - o painel já traz os `rampa_*` das unidades da confirmação;
  - as medianas de alunos nos meses 1/3/6/12 (1.310/1.775/2.122/2.228) já foram vistas no UNI-00, com todas as
    unidades misturadas;
  - a curva, a comparação com o simulador e a cobertura da faixa nas 22 unidades da confirmação ainda não foram vistas.
