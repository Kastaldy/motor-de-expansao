# Isócronas OSM como catchment por unidade — relatório (2026-09-25)

> Camada paralela, READ-ONLY sobre o M1. Nada alterou score, pesos, DEC-021 (raio de 1 km) ou DEC-041 (funil).
> Protocolo pré-registrado: `protocolo_isocronas.md` + `protocolo_isocronas_v2_adendo.md` (escritos antes de medir).
> Resultados finais = v2 (`testes_v2/resultados_08.md`), que corrige os defeitos achados pela verificação adversarial da v1.

## Resposta curta

1. **Reproduzir com OSM: sim, e funciona.** Grafo viário de 46 regiões metropolitanas (Geofabrik, 2,1 GB), isócronas de carro (5/10/15 min, com mão única) e a pé (10/15 min) para 97 unidades Ultra, ~10 mil academias, ~24 mil pontos de controle e 175 hexágonos da carteira. O tempo de carro bate com o OSRM (razão mediana 1,05; IQR 0,94–1,25; N = 32 rotas), ou seja, é tempo **sem trânsito**.
2. **Previsão de desempenho: não.** NO-GO nos 5 desfechos (ativos/m², faturamento/m², pagantes/m², % agregador, churn), N = 54. Mesma conclusão do E7/DEC-043.
3. **O que a isócrona muda é o TAMANHO do catchment, não a forma.** Um círculo de área igual à isócrona reproduz população, renda e oferta com rho 0,94–0,99 e dá o mesmo resultado em todos os testes (T6). A "forma da rede" (barreiras, vias) não acrescenta informação mensurável.
4. **Onde agrega de verdade: produto, como fato descritivo.** Dimensiona a área de influência real (5 min de carro = 3,9x a população do círculo de 1 km, variando de 2,1x a 7,3x por unidade), mostra canibalização que o raio euclidiano não vê e dá um mapa defensável para locador e franqueado.

## Resultados v2

| teste | resultado | critério |
|---|---|---|
| T2 preferência revelada (onde academias existem, academia x esquina aleatória) | AUC 0,756 → 0,778 (+0,022, IC95 por metro [+0,013; +0,031]); pré-registrado sem truncamento +0,033 | atendido (cadeias: +0,019, no limite) |
| T3 previsão (E8) | R² OOF −0,15 a +0,08; ganho sobre o círculo nunca exclui zero | NO-GO |
| T6a forma x tamanho (preferência revelada) | isócrona − círculo de área igual = −0,002 [−0,006; +0,002] | forma não acrescenta |
| T6b concordância isócrona x círculo de área igual (Ultra) | rho pop 0,98, renda 0,99, oferta 0,94–0,96 | só tamanho muda |
| T4 funil (rótulo Livre/Adensar/Disputa, 161 hexágonos) | troca 9,9% (carro 5 min, cadeias), 49% (15 min a pé); na cascata real (N = 25) 24%, e 13 passariam a camada 3 contra 8 hoje | descritivo |
| T5 canibalização | 66 de 97 unidades têm outra Ultra a 10 min de carro (sobreposição mediana 100%); no círculo de 1 km, 6 de 97 | descritivo |
| T7 velocidade | nosso ≈ OSRM sem trânsito (1,05) | "5 min" = 5 min de rua livre |

Leitura do T2: a acessibilidade mede algo real sobre onde o setor se instala, mas o ganho vem de olhar uma área MAIOR e a pé, não do desenho da rede — um raio adaptado por densidade faria o mesmo.

## Recomendação

- **Não** usar isócrona como gate, peso ou régua (M1, funil, índice de praça). Não há sinal preditivo e a forma não acrescenta ao tamanho.
- **Sim** como fato no produto, com o rótulo "tempo sem trânsito":
  1. Relatório Pontual: bloco "quem chega em 5 min de carro e 15 min a pé" (pop, renda, academias, unidades Ultra), ao lado do raio de 1 km.
  2. Visão Executiva: canibalização por tempo (Ultras a 10 min, % de sobreposição).
  3. Funil: contagem de concorrentes na isócrona como leitura ao lado do chip, sem mudar o gate (mudaria 24% dos rótulos na cascata real — decisão que exigiria DEC).
- Para análise de desempenho, trocar hexágono/1 km por raio **adaptativo por tamanho** é mais barato que isócrona e dá o mesmo.

## Correções da v1 para a v2 (verificação adversarial)

Malha a pé partida por cidade (Niterói, Guarujá, Águas Lindas); caixa curta truncando carro 15 min; academia contando a si mesma na oferta; estúdios boutique (DEC-056) e a própria Ultra no feed do agregador contados como oferta; snap curto para centroide de hexágono; perda da metragem de Samambaia. Carro 15 min segue truncado em 37% das Ultra e foi excluído dos testes principais.

## Limitações

Velocidade sem trânsito (pico não medido); N = 54 para previsão só detecta sinal forte; coordenadas de 5 unidades com confiança baixa; recorte do funil = 175 hexágonos nas 46 regiões.

## Arquivos

Scripts `01`–`09`, bases `testes_v2/`, polígonos `poligonos_v2/`, atributos `atributos_v2/`, calibração `testes_v2/calibracao_osrm.csv`. Grafos em `data/osm_cache/grafo/`.
