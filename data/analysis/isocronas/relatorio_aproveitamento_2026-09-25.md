# Aproveitamento do potencial por unidade Ultra (2026-09-25)

> Modelo DECLARADO (política, não previsão; DEC-043 segue valendo). Camada paralela, READ-ONLY sobre o M1.
> Script `13_aproveitamento.py`; tabela por unidade `aproveitamento/unidades.csv`; detalhes `aproveitamento/resultados.md`.

## A conta

Para cada unidade (54 com metragem e faturamento de 12 meses), em três áreas de alcance (carro 5 e 10 min, a pé 15 min):

- **Demanda** = população × taxa de penetração × ajuste de renda × ajuste de crescimento do hexágono.
- **Oferta concorrente** = alunos reais dos concorrentes dentro da isócrona (1.201 com dado real, 427 pela mediana da rede, o resto por proxy de cadeia ou de independente).
- **Canibalização** = ativos das outras Ultras dentro da isócrona.
- **Alunos esperados** = demanda × capacidade própria ÷ (capacidade própria + concorrentes + outras Ultras). A capacidade própria vem da metragem, que é a hipótese do diretor: academia maior captura mais onde a concorrência é menor.
- **Faturamento esperado** = alunos esperados × receita por aluno ajustada pela renda.
- **Aproveitamento** = faturamento real ÷ esperado, normalizado pela mediana da rede. 1,0 é a rede típica para aquele potencial.

**Estresse:** 2.000 sorteios das premissas (taxa 10–25%, peso da renda, peso do ticket, capacidade de independentes e de cadeias sem dado, alunos/m², peso do crescimento e peso de cada área de alcance).

## Resultado

- **20 unidades ficam acima da rede para o potencial em mais de 80% dos sorteios, 21 abaixo e 13 dependem das premissas.**
- **Botafogo: 2,45x** (IC80 1,53–3,86). Fatura R$ 683 mil/mês contra R$ 208 mil esperados para a praça, bem acima mesmo em praça rica e disputada.
- **Acima:** Botanic Mall, Jardim Botânico, Santa Maria, Sorriso, Cotia, Valparaíso, Lago Norte, Vila Guanabara, Arapoanga.
- **Abaixo:** Vila Guilherme, Campo Limpo, Brasilândia, Augusta, Carapicuíba, Aclimação, Setor Oeste, Águas Claras, Jundiaí, Plaza Sul.
  - Brasilândia e Vila Guilherme têm o vale de receita de out/25–mai/26, que puxa a mediana de 12 meses para baixo.
- **Premissas que mais mexem:** o peso da renda (rho 0,56 entre os extremos) e a área de alcance usada (0,83 a 0,96). Taxa de penetração, capacidade dos concorrentes e alunos/m² quase não mudam a ordem (0,95–0,99).

## Testes (honestos)

| teste | resultado |
|---|---|
| Esperado x real (faturamento) | rho +0,22 (sorteios: +0,01 a +0,37); por m²: −0,01 |
| Aproveitamento x faturamento/m² | rho +0,75 |
| Hipótese do diretor: metragem rende mais em praça boa | rho +0,51 dentro x +0,36 fora; diferença +0,15 [−0,33; +0,63] |
| Hipótese do diretor: metragem rende mais com concorrência menor | +0,53 x +0,32; diferença +0,21 [−0,27; +0,70] |
| Vagas x faturamento | +0,53 (colinear com m²); x faturamento/m²: +0,24 |
| Crescimento do município x aproveitamento | população +0,48, emprego +0,40, média das dimensões +0,42, empresas −0,41 (N = 47, 6 testes) |
| Crescimento do hexágono x aproveitamento | +0,25 |

Leitura:

1. O potencial calculado quase não se relaciona com o faturamento real. O índice é, portanto, uma régua declarada: mostra onde a unidade está contra uma praça de mesmo porte, mas o ranking é dominado pelo faturamento real por m².
2. A hipótese do diretor aparece na direção certa nos dois recortes, mas sem significância com N = 54. Não dá para afirmar nem descartar.
3. Crescimento municipal de população e emprego acompanha unidades acima do potencial. É o sinal novo mais forte desta rodada, mas vem de 6 testes, com N = 47 e concentração no DF. Fica como hipótese a pré-registrar.

## Próximos passos

- Validar o índice com o time de campo: as unidades "abaixo" são as que eles consideram mal geridas ou com ponto ruim? Se sim, o índice vira ferramenta de diagnóstico.
- Empresas (Receita): a pasta do OneDrive tem só a tabela de empresas (sem endereço e sem CNAE) e está apenas na nuvem. Para localizar empregos, é preciso a tabela de estabelecimentos.
- Pré-registrar o teste de crescimento (população e emprego municipal x desempenho) quando houver N maior.
