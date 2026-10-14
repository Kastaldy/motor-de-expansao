# Fachada — teste final com a planilha completa do Juan (protocolo v1.3)

Planilha: `planilha_fachada_juan_2026-09-30_completa.xlsx` (SHA-256 `7dc734990260a887…`), coluna `Notas`: 46 notas de 51 linhas (6 de controle; 40 novas; 29 novas que ninguém tinha visto). Protocolo `protocolo_fachada.md` (SHA-256 `dea15484a3234dd8…`). Botafogo fora (decisão do Felipe).
Shopping (`poi_em_shopping`): loja de rua 55, em shopping 14, sem informação 1 (ficam fora das amostras 'loja de rua').
**Concordância nas unidades de controle** (Juan × média Felipe/Vini): serra-es 4 × 4; floriano-mg 4 × 4; boa-vista-ba 3 × 5; samambaia-df 5 × 4; jundiai-sp 5 × 3; butanta-sp 3 × 5. Diferença de mais de 1 ponto em 3 de 6 (regra: 3 ou mais → réguas diferentes; a leitura principal já é dentro do avaliador).

| amostra | N | Spearman nota × faturamento acima do previsto | IC 90% | inclinação | leitura |
|---|---|---|---|---|---|
| **PRINCIPAL — novas não vistas, loja de rua** | 23 | +0.05 | [-0.37; +0.44] | +2% por ponto | **inconclusivo** |
| novas não vistas, com shopping | 29 | -0.23 | [-0.56; +0.10] | -8% por ponto | **inconclusivo** |
| todas as novas do Juan, loja de rua | 31 | -0.07 | [-0.39; +0.26] | -2% por ponto | **inconclusivo** |
| todas as novas do Juan, com shopping | 40 | -0.26 | [-0.51; +0.02] | -8% por ponto | **inconclusivo** |
| todas as notas (Felipe, Vini e Juan), loja de rua | 48 | +0.21 | [-0.05; +0.45] | +9% por ponto | **inconclusivo** |
| todas as notas (Felipe, Vini e Juan), com shopping | 61 | +0.00 | [-0.22; +0.23] | +0% por ponto | **inconclusivo** |

Faturamento acima/abaixo do previsto por nota (todas, sem Botafogo): nota 1: +16% (n=3); nota 2: +29% (n=5); nota 3: -12% (n=22); nota 4: +1% (n=21); nota 5: +12% (n=10).

| unidade (novas não vistas) | loja de rua | origem | nota | faturou vs. previsto |
|---|---|---|---|---|
| setor-oeste-go | sim | treino (LOO) | 3 | -51% |
| lago-sul-df | ? | treino (LOO) | 5 | -41% |
| campo-limpo-sp | sim | treino (LOO) | 4 | -40% |
| alexandrina-go | sim | teste UNI-02 | 3 | -36% |
| brasilandia-sp | sim | treino (LOO) | 3 | -34% |
| jardim-apura-sp | sim | teste UNI-02 | 5 | -34% |
| sobradinho-df | sim | treino (LOO) | 4 | -32% |
| poa-barra-sul-rs | não | treino (LOO) | 3 | -25% |
| aguas-lindas-go | sim | treino (LOO) | 4 | -22% |
| cpa-mt | sim | teste UNI-02 | 3 | -22% |
| unai-mg | sim | teste UNI-02 | 4 | -21% |
| ceilandia-sul-df | sim | treino (LOO) | 5 | -18% |
| taguatinga-sul-df | sim | teste UNI-02 | 4 | -14% |
| vicente-pires-df | sim | treino (LOO) | 4 | -14% |
| ceilandia-df | não | treino (LOO) | 4 | -6% |
| cabo-frio-rj | sim | treino (LOO) | 3 | -5% |
| aclimacao-sp | sim | treino (LOO) | 3 | -4% |
| paranoa-parque-df | sim | teste UNI-02 | 4 | -0% |
| campo-largo-pr | sim | treino (LOO) | 2 | +2% |
| cambui-campinas-sp | sim | teste UNI-02 | 4 | +12% |
| asa-norte-df | sim | treino (LOO) | 3 | +12% |
| arapoanga-planaltina-df | sim | treino (LOO) | 3 | +13% |
| vila-guanabara-sc | sim | teste UNI-02 | 1 | +19% |
| cidade-ocidental-go | sim | jovem, mês 7 | 4 | +32% |
| guaruja-sp | sim | treino (LOO) | 5 | +46% |
| plaza-sul-sp | não | treino (LOO) | 2 | +52% |
| praia-grande-sp | não | treino (LOO) | 1 | +62% |
| santos-sp | sim | treino (LOO) | 5 | +76% |
| cariacica-es | não | teste UNI-02 | 3 | +100% |

**Leitura principal (v1.3): INCONCLUSIVO.**
