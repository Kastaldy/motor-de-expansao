# Perfil e clusterização multirede com isócronas (2026-09-25)

> Camada paralela, READ-ONLY sobre o M1. Tabelas completas em `multirede/cluster_resultados.md`; ficha por unidade em `multirede/perfil.parquet`; script `12_perfil_cluster.py`.

## Universo

- 273 unidades com coordenada e isócrona: SkyFit 182, Ultra 53, Engenharia do Corpo 38. Das 426 da base multirede, 151 não têm coordenada (123 SkyFit, 23 EdC); 2 ficaram sem malha.
- Metragem e vagas: Ultra 53 e EdC 37-38 (N = 90). Tipo de imóvel só na EdC (38). SkyFit sem metragem.
- Grafos novos: 91 caixas além das 46 anteriores.

## Resultados

1. **Não há regiões "naturais" estáveis.** Com 6 variáveis de região (população a 1 km, razão de alcance, km de rua em 5 min, fração a pé, renda, pressão de oferta), nenhum k entre 3 e 6 passa a estabilidade mínima (ARI mediano 0,33 a 0,56, contra 0,75). O território forma um contínuo, não grupos discretos.
2. **Os perfis de k = 5 são legíveis** e servem como vocabulário descritivo, com fronteiras instáveis:
   - alto alcance e pouca oferta (razão 5,9x, 72 unidades);
   - central de renda alta (renda 4.100, 28);
   - periferia pouco caminhável (fração a pé 0,32, 20);
   - bairro compacto de alcance baixo (87);
   - denso, renda baixa e pouca concorrência (64).
3. **Desempenho não difere entre os perfis.** Alunos relativos à mediana da própria rede: p = 0,74; só Ultra p = 0,22; só SkyFit p = 0,51; alunos/m² p = 0,69.
4. **Modelo simples com N = 263 (113 metros):** log de alunos explicado só pela rede tem R² OOF +0,03; somar o círculo de 1 km dá +0,01 e somar as isócronas dá −0,00. O ganho da isócrona é −0,016 [−0,038; +0,033]. É o N em centenas que a DEC-043 pedia, e o território segue sem explicar alunos.
5. **Imóvel:** unidades menores têm mais alunos/m² nas duas redes (escala, já conhecido). Vagas por 1.000 m² não se relacionam com alunos/m² (rho 0,00). Na EdC, centro comercial tem 2,71 alunos/m², sala de rua 2,30 e shopping 2,26 (N = 11/20/6, só descritivo).

## Leitura

A isócrona e os perfis descrevem bem a praça, mas nem região nem imóvel (metragem, vagas) explicam alunos nas três redes com os dados de hoje. O que resta sem medir é o que o campo sabe e as bases não têm: visibilidade e fachada, qualidade do ponto, gestão da unidade e tempo de maturação.

## Próximo passo possível

- Usar os perfis como etiqueta descritiva no Relatório Pontual e na escolha de comparáveis da viabilidade, sem prometer desempenho.
- Quando chegarem fachada, tipo de imóvel da Ultra e datas de inauguração das outras redes, rodar de novo o `12_perfil_cluster.py` (o pipeline já está pronto).
- Recuperar coordenadas das 151 unidades sem geolocalização aumentaria o N para ~420.
