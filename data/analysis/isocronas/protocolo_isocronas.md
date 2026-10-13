# Protocolo pré-registrado — isócronas OSM como catchment adaptativo por unidade (2026-09-24)

> Escrito ANTES de rodar qualquer teste sobre a base completa. Só foi visto até aqui: a demo de 15 unidades (área e população por cenário, sem desfecho além de correlações ilustrativas que não passaram de |rho| 0,47 com fat/m²). Molde: `data/reports/e7_protocolo_pre_registrado.md` e DEC-043.

## Pergunta

Substituir o raio fixo de 1 km / hexágono res-7 por um catchment por tempo de deslocamento (isócrona) **muda o que o motor mede** e **ajuda em algum uso**: (a) descrever a praça (produto), (b) o funil (rótulo de concorrência e residual), (c) preferência revelada do setor (onde academias existem), (d) previsão de desempenho de unidade?

## Universo

- Grafo: OSM (Geofabrik 2026-09-23), 46 caixas metropolitanas em torno das unidades Ultra (Growth + cadastro), malha de carro DIRECIONADA (oneway), velocidades default por classe com `maxspeed` quando existe (teto 80 km/h); malha a pé não direcionada, 4,5 km/h.
- Cenários: carro 5 / 10 / 15 min; a pé 10 / 15 min; comparadores: círculo de 1 km e hexágono res-7 do ponto.
- Pontos: 97 unidades Ultra (83 com coordenada de confiança alta, 9 média, 5 baixa — os de confiança baixa entram na descrição e SAEM dos testes de previsão), ~26 mil academias (cadeias mapeadas + agregador), pontos de controle aleatórios sobre a malha (2 por academia, teto 4.000 por metro), centroides dos hexágonos da carteira acionável.
- Atributos por polígono: população, domicílios e renda per capita calibrada (setores 2022, fração de área), academias por tipo, oferta ponderada (cadeia 1,0; independente 0,5 — DEC-033), unidades Ultra dentro (canibalização), nós e km de rua alcançados.

## Testes e critérios (escritos antes)

**T1 — Medição (descritivo, sem critério de GO).** Quanto a isócrona difere do círculo/hex: razão de população, renda e oferta; correlação de ranks; quais unidades/hexágonos mais mudam e por quê (barreiras). Só reporta.

**T2 — Preferência revelada (onde academias existem).** Classificador academia vs controle, GroupKFold por metro (5 folds), regressão logística padronizada. Baseline B = atributos do círculo de 1 km + hex (pop, renda, oferta). Modelo I = B + atributos das isócronas (pop/renda/oferta/km_rua/n_nos por cenário; no máximo 2 cenários por modo para não empilhar colinearidade: carro 5 min e 15 min; a pé 15 min). Métrica: AUC out-of-fold; IC95 por bootstrap (2.000) sobre as previsões OOF. **Critério: isócrona "acrescenta informação de localização" se AUC(I) − AUC(B) ≥ +0,02 com IC95 excluindo zero.** Independentes e cadeias reportadas separadamente (a cadeia escolhe ponto com critério; a independente, menos).

**T3 — Previsão de desempenho (E8, molde E7).** Unidades Ultra com metragem (54) e regime maduro (≥ 12 meses, ≥ 6 meses observados). Desfecho primário: **ativos por m² no regime maduro** (mediana); secundários: fat/m² maduro, pagantes/m², % agregador, churn 12 m. Baseline B1 = metragem; B2 = círculo/hex (pop 1 km, renda 1 km, oferta 1 km); Modelo I = B2 + isócrona (pop carro 5 min, pop a pé 15 min, oferta ponderada carro 5 min, n_ultra carro 10 min, pop/oferta carro 5 min). LOO e GroupKFold por UF; ridge padronizado; R² OOF com IC bootstrap 2.000. **GO só se R²_OOF(I) > 0 com IC excluindo zero E ganho (I − B2) > 0 com IC excluindo zero.** Efeito fixo de master declarado como sensibilidade. Expectativa declarada: NO-GO (E7), e a razão que faria diferença é a OFERTA por isócrona, não a população.

**T4 — Funil.** Para os hexágonos da carteira acionável dentro dos metros: contar academias na isócrona de carro de 5 min do centroide contra `n_concorrentes_influencia_1km`; reclassificar pelo rótulo do funil (Livre / Adensar / Disputa, `CONC_ADENSAR_MAX` = 2) e medir a taxa de troca de rótulo, a direção (mais Disputa? mais Livre?) e a concordância de ranks do residual (população − oferta ponderada × capacidade) entre 1 km e isócrona. Sem critério de GO: é medida de IMPACTO no produto. Vetos de sanidade: hexágono com `sem_rede` fica fora e é contado.

**T5 — Canibalização (descritivo).** Para pares de unidades Ultra com isócronas de 10 min sobrepostas: fração de sobreposição e relação com ativos/m² e pct agregador. Só reporta.

## O que NÃO se conclui daqui

- Nada aqui altera M1, score, pesos, raio do Relatório Pontual (DEC-021) ou artefatos: é camada paralela READ-ONLY.
- T2 diz se a rede viária/acessibilidade informa ONDE o setor se instala — não que prevê faturamento.
- Velocidades são defaults; sem tráfego real; isócrona de carro é "distância-tempo teórica".
