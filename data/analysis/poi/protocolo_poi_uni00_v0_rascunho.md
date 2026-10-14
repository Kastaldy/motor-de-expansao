# Protocolo pré-registrado: pontos de interesse (POI) explicam o resultado das academias? (BLK-UNI, UNI-00/01)

> Rascunho v0 de 2026-09-25. É congelado ANTES de cruzar qualquer POI com qualquer desfecho.
> Camada paralela e READ-ONLY sobre o M1. Nenhum resultado aqui altera score, pesos ou artefato oficial.

## 1. Pergunta
Pontos de interesse ao redor de uma academia melhoram a explicação do resultado dela **além** do modelo de faturamento já medido?
Esses pontos são polos de fluxo (empresas de escritório, varejo, shopping, estação, universidade) e academias por CNAE.
O modelo já medido é log faturamento ~ log m² + log renda (carro 10 min) + log pop (carro 10 min), com R² fora da amostra de 0,39 na mediana de 12 meses.

## 2. Dados (congelados)
- **POIs:** `data/staging/poi/base_poi_unica/`. As fontes estão em `docs/fontes_bases_poi.md`.
  - CNPJ entra só com `geo_nivel` in {`cnpj_cep_numero`, `cnpj_cep`}.
  - A sensibilidade roda só com `cnpj_cep_numero`.
- **Áreas de alcance** (isócronas v2, mesmo motor):
  - `carro_10`: 600 s de carro, a área de referência do modelo.
  - `pe_15`: 900 s a pé, o entorno imediato de fluxo a pé.
  - Ultra: `isocronas_v2/metro_*.parquet` (tipo `ultra`). Engenharia do Corpo e SkyFit: `multirede/atributos/poligonos_metro_*.parquet`.
- **Desfechos:**
  - **S1, principal (Ultra, faturamento do Financeiro):** log da mediana mensal do faturamento, usando só meses com `mes_completo`, `operacao_mes_cheio`, `origem_faturamento == financeiro` e `meses_operacao >= 6`. A regra dos 6 meses é o controle de maturidade: o estudo de inauguração mostra que o faturamento estabiliza por volta do 6º mês.
    - **Exploração:** meses de 2025-01 a 2025-12. A unidade precisa ter pelo menos 3 meses válidos.
    - **Confirmação temporal:** meses de 2026-01 a 2026-08, com a mesma regra. Guarujá, ago/26 = R$ 217.525,74 (dupla contagem corrigida).
  - **S2, replicação em unidades independentes (alunos):**
    - S2a: SkyFit, alunos reais (N ≈ 176, sem metragem).
    - S2b: Engenharia do Corpo, alunos reais (N ≈ 36, com metragem).
  - **S3, secundário:** Ultra, log da mediana de ativos na mesma janela da exploração.
- **Covariáveis base (congeladas do trabalho anterior):**
  - S1, S2b e S3: log metragem, log renda per capita (carro 10), log pop (carro 10).
  - S2a: só log renda e log pop, porque a SkyFit não tem metragem.

## 3. Famílias de POI (uma variável por família, fixada antes de rodar)
| família | variável | área | hipótese |
|---|---|---|---|
| F1 Trabalho / fluxo diurno | log(1 + CNPJ de escritório, serviços administrativos, financeiro, TI e governo) − log(1 + pop) | carro_10 | Quem trabalha perto treina perto. Densidade de empresas por habitante indica gente de fora que circula ali. |
| F2 Polo de consumo de rua | log(1 + CNPJ de comércio, alimentação e serviços pessoais) | pe_15 | Rua comercial movimentada gera visibilidade e passagem. |
| F3 Âncoras de fluxo | log(1 + shoppings + estações/terminais do OSM) | pe_15 | Shopping e estação concentram passagem. |
| F4 Universidade | log(1 + CNPJ de educação superior, CNAE 8531 a 8533) | carro_10 | Público de 18 a 24 anos. |
| F5 Academias por CNAE | log(1 + 1000 × CNPJ 9313-1 / pop) | carro_10 | Saturação medida por um censo nacional de academias, incluindo independentes fora do universo mapeado. Hipótese de sinal negativo. |

- **Robustez de fonte:** F2b é a mesma ideia de F2, mas com os endereços não residenciais do CNEFE (espécie "outras finalidades", verificados em campo pelo IBGE em 2022) no lugar do CNPJ. F2b não entra na correção de múltiplos testes. Ele só qualifica F2: se F2 e F2b discordarem de sinal, F2 não é aceita.
- **A própria unidade** conta como 1 CNPJ 9313 em F5. O efeito é desprezível na escala de carro_10 e não é corrigido.

## 4. Análise
- **Modelo:** ridge (alfa por validação interna, `RidgeCV`, variáveis padronizadas dentro de cada treino) e OLS como checagem.
- **Validação:** leave-one-out; GroupKFold por UF como sensibilidade.
- **Métrica:** R² fora da amostra (LOO). **Ganho da família** = ΔR² = R²(base + F) − R²(base), nas mesmas previsões LOO, com IC por bootstrap pareado de 2.000 reamostragens.
- **Múltiplos testes:** Holm sobre F1 a F5 com α = 0,05. O p-valor unilateral é a fração de bootstrap com ΔR² ≤ 0.
- **Modelo conjunto** (base + F1 a F5): é reportado, mas não decide nada.
- **Poder:** simulação feita antes da leitura dos resultados. Uma variável sintética com R² parcial verdadeiro de 0,03, 0,05, 0,10 e 0,20 é somada ao desfecho real de S1, em 200 repetições. Mede-se a frequência com que o critério da §5 passa. O relatório tem de dizer o tamanho de efeito que o desenho consegue ver.

## 5. Critério de decisão (congelado)
Uma família **entra** como candidata para o modelo de faturamento (UNI-02) se as quatro condições valerem:
1. ΔR² em S1-exploração > 0, com p de Holm < 0,05.
2. ΔR² em S1-confirmação > 0, com a especificação congelada. As unidades são as mesmas, então isto é estabilidade no tempo e não uma amostra independente.
3. O sinal do coeficiente se repete em S2a (SkyFit) **e** o ΔR² LOO em S2a é > 0.
4. No caso de F2, F2b concorda no sinal.

Se passar só 1 e 2, a família é "sinal só na Ultra, não replica". Se não passar 1, é "sem ganho detectável neste N", o que **não prova ausência de efeito**: o tamanho mínimo detectável é o da simulação de poder.

**Independentemente do resultado**, os POIs viram FATO DESCRITIVO do ponto (no molde da DEC-026, fato sem peso). Exemplo: "em 10 min de carro: N empresas de escritório, K shoppings, U universidades".

## 6. O que NÃO será feito
- Não trocar área, variável ou recorte depois de ver o resultado. Qualquer análise extra entra rotulada como **exploratória** e não decide.
- Não excluir outlier para ganhar métrica.
- Não somar CNPJ, CNEFE e OSM como se fossem contagens independentes.
