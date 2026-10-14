# Previsão congelada da turma de 2026 (confirmação prospectiva)

Versão 1.0, 2026-09-29. Escrito antes de gerar as previsões. Só análise.

## Para que serve

Três resultados do estudo precisam de unidades **nunca vistas** para se confirmar:
- **estúdios** (+28–30%, pós-hoc);
- **master + estúdios** (bateu o M0 no teste, também pós-hoc);
- a **faixa de incerteza** da v2 (cobriu 67% no UNI-02).

A turma aberta de 2025-08 em diante ainda não está madura. As previsões são feitas e **congeladas hoje, com hash**,
e comparadas com o real quando cada unidade amadurecer. Não há como ajustar depois de ver.

## Previsões

**Treino:** as 39 maduras de 2025, as mesmas do UNI-02.

| modelo | variáveis |
|---|---|
| **M0** | log m², log renda e log população da isócrona de 10 min de carro |
| **M0+E** | M0 + estúdios |
| **M0+ME** | M0 + grupo de master (DF/GO, ULTRA, RJ/SP 01, outros) + estúdios |

**Unidades:**
- fora do treino e do teste do UNI-02;
- com metragem oficial ou por satélite (planilha de 29/09, corrigida pelo viés 1,12);
- com a isócrona.

M0+E e M0+ME só onde o cadastro tem estúdio e master. Master desconhecida conta como "outros".

**Nível:**
- faturamento mensal maduro no nível de 2025, e o mesmo com o ajuste de calendário de 2026 (−2%, o do UNI-02);
- na conferência, usa-se o calendário do ano conferido.

**Faixa:** p10–p90 dos erros fora da amostra do M0, juntando o LOO do treino e o teste do UNI-02. É provisória: o
BLK-UNI-07 calibra a definitiva.

## Conferência (fixada hoje)

**Quando:** cada unidade com ≥ 3 meses válidos com `mes_vida` ≥ 12. Real = média desses meses (regra do UNI-01).
Confere-se quando houver ≥ 10 unidades maduras.

**Métricas:**
- erro típico (mediana de |erro|) e viés de cada modelo;
- Spearman;
- cobertura da faixa.

**Leituras:**
- **Estúdios se confirmam** se M0+E tiver erro típico menor que o M0 **e** Spearman não pior.
- **Master + estúdios** se confirmam pela mesma regra, contra o M0.
- **Faixa:** cobertura entre 70% e 90%.

## Leitura precoce (descritiva, não é a conferência)

Para as unidades com 3 a 12 meses de vida:
- projeta-se o nível maduro pela curva de faturamento do UNI-03: faturamento do último mês válido ÷ a mediana da curva
  naquele mês;
- compara-se a projeção com as previsões.

É só um sinal antecipado, porque o erro da projeção vai de 9% a 21% conforme o mês. Não confirma nada.

Arquivos: `previsao_2026/01_congelar.py` → `previsoes_turma_2026.csv`, `leitura_precoce.md`,
`REGISTRO_CONGELAMENTO.txt`.
