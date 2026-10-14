# UNI-02 (reforço) — Réplica da hipótese do diretor em outras redes

Versão 1.0, 2026-09-28. Escrito antes de calcular qualquer associação nas outras redes. O congelamento (SHA-256)
fica em `REGISTRO_CONGELAMENTO.txt`. Roda uma vez.

## 1. Hipótese

Vem do T09 do UNI-01, que é a hipótese do diretor: **o tamanho (m²) rende mais onde a concorrência em volta é de
estrutura menor**, medida como a fração de academias independentes na isócrona de carro 10 min.

Na Ultra (40 maduras, faturamento de 2025), a elasticidade do faturamento ao m² sobe **+0,34** por desvio-padrão dessa
fração (IC 90% de +0,04 a +0,65). O resultado é frágil: o IC cruza zero em 7 de 39 retiradas de uma unidade.

## 2. Amostras

- **Primária — Engenharia do Corpo:** unidades da base multirrede (`data/analysis/isocronas/multirede/`) com metragem,
  alunos e isócrona de carro 10 min. N esperado ≈ 35, em 29 cidades.
- **Secundária — EdC + Pacer juntas**, com efeito fixo de rede:
  - Pacer: 9 unidades de Ribeirão Preto e Bonfim Paulista, com isócronas geradas agora pelo mesmo pipeline;
  - as 2 de Sertãozinho ficam fora (fora do grafo viário).
- **Referência — Ultra com desfecho alunos:** o mesmo modelo na amostra primária do UNI-01, trocando o faturamento
  pelos alunos. É necessária porque o T09 foi medido em faturamento e as outras redes só informam alunos. Só informa;
  não decide.

## 3. Desfecho e variáveis

- **Desfecho:** `log(alunos)`.
  - EdC: ativos + Gympass (foto de mai/2026).
  - Pacer: alunos de planos (foto de jun/2026; a fonte não traz agregador).
- **Modelo:** `log alunos ~ log m² + log renda c10 + log pop c10 + frac_indep + z(log m²)·z(frac_indep)`, mais efeito
  fixo de rede na amostra conjunta.
- **`frac_indep`** = `n_independente_agregador / n_academias` na isócrona de carro 10 min. É a mesma função de
  atributos usada na Ultra (`04_atributos.atributos_poligono`), com a própria unidade excluída (< 75 m).
- **Efeito:** coeficiente da interação dividido pelo desvio-padrão de `log m²`, ou seja, a variação da elasticidade
  ao m² por 1 dp de `frac_indep`. IC 90% HC3.

## 4. Critério (fixado antes, na amostra primária)

- **Replicou:** o IC 90% exclui zero com sinal positivo.
- **Não replicou:** o IC 90% fica inteiro abaixo de +0,15 (exclui efeito positivo relevante, a mesma faixa de
  irrelevância do UNI-01).
- **Inconclusivo:** o resto.

**Também se reporta:**
- se o valor da Ultra (+0,34) cai dentro do IC da EdC;
- o sinal ao retirar cada cidade (metro);
- o efeito mínimo detectável (80% de poder, α = 0,10).

**Declarado de antemão:** com N ≈ 35, uma interação dificilmente sai significativa. "Inconclusivo" é o resultado
mais provável e **não** refuta a hipótese.

## 5. Limites

- Alunos, não faturamento. Por isso a referência da Ultra em alunos.
- Sem data de inauguração nas outras redes: a maturidade **não** é controlada.
- Redes diferentes da Ultra: posicionamento e preço não são controlados.
- Fotos de 2026 de alunos, concorrência e planos.
- A Pacer não informa agregador, e é uma só cidade.
