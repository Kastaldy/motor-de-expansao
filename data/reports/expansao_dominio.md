# Relatorio executivo — Expansao de Dominio Ultra Academia

**Gerado em:** 2026-05-18  
**Fonte:** `data/outputs/plano_expansao_dominio.parquet`  
**Ancoras materializadas:** 300  
**Ciclo:** Expansao de Dominio (paralelo ao M1 oficial)  

## Sumario executivo

- **Ancoras recomendadas:** 300
- **Cidades cobertas:** 30 em 18 UFs
- **Residual incremental total capturado:** 2.357.881 alunos/mes potencial

**Distribuicao por tese:**

- Adensar cluster: 160 ancoras (53.3%)
- Dominar white space: 116 ancoras (38.7%)
- Abrir com disputa: 19 ancoras (6.3%)
- Proteger corredor Ultra: 5 ancoras (1.7%)

## Top 15 cidades por residual capturado

| # | UF | Cidade | Ancoras | Clusters | Residual capturado | Score max | Tese principal |
|---|----|----|---|---|---|---|---|
| 1 | SP | São Paulo | 10 | 1 | 179.587 | 100.0 | Adensar cluster |
| 2 | BA | Salvador | 10 | 1 | 154.107 | 100.0 | Adensar cluster |
| 3 | CE | Fortaleza | 10 | 1 | 141.717 | 100.0 | Adensar cluster |
| 4 | RJ | Rio de Janeiro | 10 | 1 | 138.282 | 100.0 | Adensar cluster |
| 5 | PE | Recife | 10 | 1 | 133.921 | 100.0 | Adensar cluster |
| 6 | PA | Belém | 10 | 1 | 117.334 | 100.0 | Adensar cluster |
| 7 | SP | Osasco | 10 | 1 | 93.465 | 100.0 | Adensar cluster |
| 8 | SP | Guarulhos | 10 | 1 | 86.955 | 100.0 | Adensar cluster |
| 9 | AL | Maceió | 10 | 1 | 85.766 | 100.0 | Adensar cluster |
| 10 | SP | Santo André | 10 | 2 | 82.945 | 100.0 | Adensar cluster |
| 11 | MG | Belo Horizonte | 10 | 1 | 82.893 | 100.0 | Adensar cluster |
| 12 | SP | São Bernardo do Campo | 10 | 1 | 81.575 | 100.0 | Adensar cluster |
| 13 | MA | São Luís | 10 | 1 | 76.812 | 100.0 | Adensar cluster |
| 14 | PB | João Pessoa | 10 | 1 | 74.031 | 100.0 | Adensar cluster |
| 15 | RN | Natal | 10 | 2 | 70.410 | 100.0 | Adensar cluster |

## Top 10 clusters por residual capturado

| # | UF | Cidade | Cluster | Hexes total | Ancoras | Residual cluster | Dist Ultra min (m) | Tese |
|---|----|----|---|---|---|---|---|---|
| 1 | SP | São Paulo | 3550308_001 | 173 | 10 | 179.587 | 1.480 | Adensar cluster |
| 2 | BA | Salvador | 2927408_001 | 90 | 10 | 154.107 | 326.445 | Adensar cluster |
| 3 | CE | Fortaleza | 2304400_001 | 43 | 10 | 141.717 | 198.672 | Adensar cluster |
| 4 | RJ | Rio de Janeiro | 3304557_001 | 135 | 10 | 138.282 | 1.826 | Adensar cluster |
| 5 | PE | Recife | 2611606_001 | 26 | 10 | 133.921 | 5.025 | Adensar cluster |
| 6 | PA | Belém | 1501402_001 | 92 | 10 | 117.334 | 483.851 | Adensar cluster |
| 7 | SP | Osasco | 3534401_001 | 10 | 10 | 93.465 | 2.483 | Adensar cluster |
| 8 | SP | Guarulhos | 3518800_001 | 39 | 10 | 86.955 | 6.966 | Adensar cluster |
| 9 | AL | Maceió | 2704302_001 | 25 | 10 | 85.766 | 2.544 | Adensar cluster |
| 10 | MG | Belo Horizonte | 3106200_001 | 52 | 10 | 82.893 | 6.582 | Adensar cluster |

## Resumo por UF

| UF | Cidades | Ancoras | Residual capturado |
|----|----|---|---|
| SP | 9 | 90 | 720.147 |
| MG | 3 | 30 | 184.903 |
| BA | 1 | 10 | 154.107 |
| CE | 1 | 10 | 141.717 |
| RJ | 1 | 10 | 138.282 |
| PE | 1 | 10 | 133.921 |
| PA | 1 | 10 | 117.334 |
| PR | 2 | 20 | 95.627 |
| GO | 2 | 20 | 92.978 |
| AL | 1 | 10 | 85.766 |
| MA | 1 | 10 | 76.812 |
| PB | 1 | 10 | 74.031 |
| RN | 1 | 10 | 70.410 |
| RS | 1 | 10 | 62.548 |
| PI | 1 | 10 | 60.014 |
| DF | 1 | 10 | 59.507 |
| MS | 1 | 10 | 47.151 |
| SC | 1 | 10 | 42.626 |

## Comparativo com artefatos M1

> Nenhum artefato M1 foi alterado. Esta secao e leitura comparativa apenas.

- Cidades no plano Expansao de Dominio: **30**
- Ja presentes na carteira acionavel: **30** de 30
- Ja presentes no plano curto prazo: **27** de 30
- Cidades exclusivas do Dominio (nao na carteira nem no CP): **0**

## Parametros utilizados

| Parametro | Valor |
|---|---|
| H3 resolucao | 7 |
| Raio de captura residual | 2,0 km |
| Distancia minima entre novas ancoras | 1,5 km |
| Distancia minima de Ultra existente | 1,0 km |
| Score residual minimo (gate) | 20,0 |
| Maximo de ancoras por cidade (default) | 10 |
| Capacidade proxy concorrente | 2.500 alunos |
| Cidades materializadas (--top-cidades 30) | 30 |

## Limitacoes e cautelas

- **Concorrentes mapeados:** apenas grandes redes nacionais (Smartfit, Bluefit, etc.);
  academias independentes, estudiosboutique e concorrentes regionais nao estao na base.
  O residual pode estar superestimado em regioes com alta densidade de independentes.
- **Capacidade proxy:** 2.500 alunos/unidade para todos os concorrentes, independente
  de formato. Unidades menores ou maiores distorcem o calculo de oferta consumida.
- **Populacao:** usa `pop_total_setor_2022` quando disponivel; fallback por proporcao
  municipal quando o setor censitario nao esta mapeado no hex.
- **Score residual:** depende de `sam_fitness_potencial`, que usa penetracao de 8% sobre
  populacao adulta com renda >= R$ 4.500. Nao reflete ciclo economico atual.
- **Distancia Ultra:** usa `dist_ultra_mais_proxima_m` da base de mercado; novos pontos
  Ultra abertos apos o ultimo snapshot nao estao refletidos.
- **Esta feature nao substitui o M1**, a carteira acionavel nem o plano curto prazo.
  `score_priorizacao` e `hex_score_estrutural` nao foram alterados.