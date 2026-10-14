# Aproveitamento v2 — fechamento do Financeiro, Engenharia do Corpo e crescimento (2026-09-25)

> Modelo declarado (política, não previsão). READ-ONLY sobre o M1. Script `14_aproveitamento_v2.py`; tabelas em `aproveitamento_v2/`.

## O que mudou

- **Faturamento:** fechamento do Financeiro (`faturamento_financeiro.parquet` da VPS), agosto/2026 e mediana de set/25–ago/26. Antes: série da API Growth.
- **Área de alcance:** mistura de carro 5 min, carro 10 min e a pé 15 min, com pesos sorteados no estresse. Usar só uma delas muda pouco a ordem (rho 0,83–0,96 contra o peso igual).
- **Engenharia do Corpo** entra numa versão em alunos (Ultra + EdC, N = 89).
- **Crescimento** (hexágono e 6 dimensões municipais) testado em três bases, com correlação parcial controlando DF e renda.

## Resultados

**Ultra, faturamento do Financeiro (N = 54):**
- 19 unidades acima da rede para o potencial, 18 abaixo e 17 dependem das premissas.
- Agosto e a mediana de 12 meses concordam (rho 0,98; mesma leitura em 96%).
- Esperado x real: rho +0,31 (antes +0,22 com a Growth).
- Acima: Botanic Mall, Lago Norte, Jardim Botânico, Botafogo, Santa Maria, Guarujá, Valparaíso, Arapoanga.
- Abaixo: Brasilândia, Campo Limpo, Vila Guilherme, Setor Oeste, Aclimação, Carapicuíba, Vila Matilde, Jardim Apurá.
- **Guarujá corrigido:** o Financeiro de agosto contava a unidade duas vezes (R$ 548 mil); usado o valor real informado por Felipe, R$ 217.525,74. Os outros 11 meses estavam corretos (R$ 211–246 mil).

**Hipótese do diretor (metragem rende mais com concorrência menor):**

| base | concorrência baixa | concorrência alta | diferença |
|---|---|---|---|
| Ultra, faturamento (N = 54) | +0,67 | +0,41 | +0,26 [−0,18; +0,67] |
| Ultra + EdC, alunos, dentro da rede (N = 89) | +0,73 | +0,19 | **+0,54 [+0,16; +0,88]** |

O recorte "praça boa" não se sustenta (−0,01 na Ultra; −0,28 no conjunto).

**Crescimento:**

| base | variável | rho | parcial (DF e renda) |
|---|---|---|---|
| Ultra, aproveitamento em faturamento (N = 47) | população municipal | +0,48 [+0,22; +0,67] | +0,50 (p < 0,001) |
| | prédios | +0,42 | +0,46 (p = 0,001) |
| | média das dimensões | +0,41 | +0,47 (p = 0,002) |
| | empresas por mil hab. | −0,36 | −0,38 (p = 0,008) |
| Ultra + EdC, aproveitamento em alunos (N = 81) | média das dimensões | +0,11 | +0,12 (p = 0,27) |
| SkyFit, alunos (N = 154) | média das dimensões | +0,14 | +0,14 (p = 0,07) |
| | emprego | +0,11 | +0,11 (p = 0,19) |

Leitura:
- O sinal de crescimento é forte e sobrevive ao controle por DF e renda no faturamento da Ultra.
- Nas outras bases a direção se repete (positiva), mas fraca. Isso sugere que o crescimento age mais no **faturamento por aluno** (ticket, mix) do que no número de alunos.
- A relação com empresas por mil habitantes é negativa na Ultra. Ou seja, crescimento em população e construção, não em densidade de empresas.

## Conclusão

1. O índice de aproveitamento funciona como régua de diagnóstico estável (agosto x 12 m 0,98; 37 de 54 unidades com leitura robusta ao estresse).
2. A hipótese do diretor se confirma no recorte de concorrência, com significância no conjunto Ultra + EdC: metragem vale mais onde há menos concorrência per capita. Isso justifica usar a interação metragem x concorrência na conta.
3. O crescimento municipal é o sinal novo mais forte para faturamento da Ultra e deve entrar na conta. A replicação fraca em alunos e na SkyFit pede cuidado com o peso e um teste pré-registrado quando houver mais meses.
