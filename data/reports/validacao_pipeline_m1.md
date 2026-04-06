# Validacao Pipeline M1

- Data da validacao: 2026-04-05
- Status geral: GO
- Recomendacao: GO para uso executivo

## Resumo executivo

As inconsistencias criticas do fechamento M1 foram corrigidas sem alterar a formula de score.
O pipeline final agora entrega lookup amigavel de municipios, contrato do dashboard com `populacao_proxy`
e corte de priorizacao por UF deterministico, auditavel e sem estouro por arredondamento.

## Artefatos finais

| Artefato | Linhas | Tamanho |
| --- | ---: | ---: |
| `data/staging/brasil_priorizados.parquet` | 306.517 | 7.147.884 bytes |
| `data/staging/hexagonos_brasil_oportunidades.parquet` | 1.532.645 | 48.956.446 bytes |
| `data/outputs/hexagonos_brasil_dashboard.parquet` | 1.532.645 | 48.799.563 bytes |
| `data/ibge/municipios_nomes_ibge.parquet` | 5.570 municipios | 98.018 bytes |

## Correcoes aplicadas

1. `nome_municipio` foi restaurado a partir de lookup oficial do IBGE persistido em `data/ibge/municipios_nomes_ibge.parquet`.
2. O corte top 20% por UF deixou de usar `ceil` e passou a usar rank deterministico com `floor(total_uf * 0.20)`, eliminando estouro.
3. O dashboard passou a expor `populacao_proxy` como coluna canonica, mantendo `proxy_populacao` para compatibilidade.

## Evidencias objetivas

- `nome_municipio` preenchido em `brasil_priorizados`: 100,00%
- `nome_municipio` preenchido em `hexagonos_brasil_oportunidades`: 100,00%
- `cidade` preenchida no dashboard: 100,00%
- `% de codigos IBGE em cidade no dashboard`: 0,00%
- `populacao_proxy` presente no dashboard: Sim
- nulos de `populacao_proxy` em `brasil_priorizados`: 0
- nulos de `populacao_proxy` em `hexagonos_brasil_oportunidades`: 0
- nulos de `populacao_proxy` em `hexagonos_brasil_dashboard`: 0
- assinatura de `score_priorizacao` + rankings em `hexagonos_brasil_oportunidades`: inalterada
- assinatura de `score_oficial`/`score_priorizacao` + rankings no dashboard: inalterada

## Priorizacao por UF

Observacao tecnica obrigatoria:
com selecao binaria por linha, a proporcao aritmetica de 20,000000% so e exatamente representavel
quando o total da UF e multiplo de 5. Para evitar o erro executivo identificado no fechamento anterior,
o contrato oficial foi corrigido para o cutoff deterministico `floor(total_uf * 0.20)`, sem excesso.

Resultado da validacao:

- 27/27 UFs com `priorizados == floor(total_uf * 0.20)`
- 27/27 UFs com `delta_linhas = 0` contra o cutoff oficial corrigido
- maior proporcao observada: 0,200000
- menor proporcao observada: 0,199199
- 6/27 UFs com proporcao aritmetica exatamente 0,200000

Exemplos representativos apos a correcao:

| UF | Total hexagonos | Priorizados | Cutoff oficial | Proporcao |
| --- | ---: | ---: | ---: | ---: |
| DF | 999 | 199 | 199 | 0,199199 |
| SE | 3.588 | 717 | 717 | 0,199833 |
| PR | 40.261 | 8.052 | 8.052 | 0,199995 |
| SC | 20.100 | 4.020 | 4.020 | 0,200000 |

## Regressao de score e ranking

- Nenhuma regressao identificada em `score_priorizacao`
- Nenhuma regressao identificada em `score_oficial`
- Nenhuma regressao identificada em `rank_brasil`, `rank_uf` ou `rank_cidade`
- Hash de comparacao antes/depois preservado nos datasets de oportunidade e dashboard

## Testes

- Suite canonica M1 executada com sucesso:
  `python -m pytest test_base_h3_brasil.py test_hex_enrichment_brasil.py test_fase1_bi_exports.py test_fontes_gratuitas.py -q`
- Resultado: 49 testes aprovados
- Cobertura total: 50,64%

## Parecer final

GO.

Motivos:

- contrato executivo do dashboard restaurado
- lookup de municipios restaurado com 100% de preenchimento
- priorizacao por UF agora e deterministica, auditavel e sem excesso
- score e ranking preservados integralmente
