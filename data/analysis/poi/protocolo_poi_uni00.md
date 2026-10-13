# Protocolo pré-registrado: pontos de interesse (POI) explicam o resultado das academias? (BLK-UNI, UNI-00/01)

> **v1, 2026-09-25.** Substitui o rascunho v0 (`protocolo_poi_uni00_v0_rascunho.md`) depois da revisão adversarial de 4 lentes: estatística, medição, confundimento e domínio.
> É congelado ANTES de cruzar qualquer POI com qualquer desfecho. O SHA-256 deste arquivo e dos scripts fica em `REGISTRO_CONGELAMENTO.txt` antes da etapa 2 e é informado ao Felipe no chat.
> Camada paralela e READ-ONLY sobre o M1.

## 1. Pergunta
POIs ao redor da academia explicam o resultado dela **além** do modelo de faturamento já medido?
- O modelo já medido é log faturamento ~ log m² + log renda (carro 10 min) + log pop (carro 10 min).
- O resultado final é "entra" ou "não entra" como candidata para o modelo de faturamento esperado (UNI-02).

## 2. Mudanças desde o v0 e por quê (resumo da revisão)
| mudança | motivo |
|---|---|
| p de decisão por **permutação Freedman–Lane** refazendo todo o leave-one-out (B = 999). O bootstrap fica só para o IC. | Um bootstrap sobre previsões fixas não é teste sob H0. |
| **OLS decide**; ridge só é reportado. | Com poucas variáveis o ridge não acrescenta nada, e deixar os dois abertos era um caminho de escolha. |
| Critério exige o **sinal da hipótese**. | ΔR² > 0 é cego ao sinal. |
| Confirmação passa a ser **replicação na Smart Fit** (unidades independentes, concorrente low-cost direta, N ≈ 460). | Medido: as 54 unidades Ultra com metragem são as mesmas em 2025 e em 2026, então não existe unidade nova para um teste para frente. A estabilidade no tempo vira só relatório. |
| **Idade** da unidade em faixas nos dois modelos. | Com filtro de 6 meses a idade ainda anda junto com a centralidade. |
| F1 e F2 em **intensidade a pé**: log(1+n) − log(1+pop a pé 15 min). | A contagem absoluta a pé media densidade residencial, porque a pop da base é de carro. |
| F1 e F2 contam só **filial** (`matriz_filial = 2`); a versão com todas as empresas é sensibilidade. | Tira MEI e PJ registrados em casa. |
| Listas **literais** de CNAE e tag. F2 inclui supermercado e farmácia, sem atacado e veículos. F1 sem condomínio, limpeza, holding, publicidade, pesquisa e veterinária. | Operacionalização estava frouxa. |
| **Estoque em 2025-01-01**: CNPJ com `data_inicio` antes de 2025. | Evita contar como causa o que abriu depois do desfecho. O viés de sobrevivência fica declarado, porque a base só tem ativos em set/26. |
| Geocodificação refeita (`03b_regeocodificar.py`): número vazio deixa de ser "exato"; CEP com mais de 2.000 endereços vira "cep_area"; CEP ausente cai no prefixo de 5 dígitos. Nas famílias a pé, o CNPJ geocodificado por CEP é **rateado** pela fração dos endereços do CEP que cai dentro da isócrona. | Antes havia precisão falsa, com erro diferente por UF. |
| F3 **binária**, com âncoras deduplicadas; o shopping onde a unidade está (a menos de 150 m) sai e vira fato descritivo. | Dupla contagem e tipo de imóvel. |
| F4 (universidade) sai do teste e vira fato descritivo. F5 é refeita como academias por CNAE **fora** do universo mapeado, com a concorrência mapeada nos dois modelos. | Poder com N = 54, e F5 repetia o teste de concorrência já feito. |
| **Portões sem desfecho** (colinearidade, suporte, poder) medidos e gravados antes da etapa 2. | Pré-registro verificável. |

## 3. Dados (congelados)
- **POIs:** `data/staging/poi/` com `cnpj_ativos_<UF>` (geocodificação v2), `cnefe_cep_numero_<UF>` (para o rateio), `base_poi_unica` (OSM e CNEFE). As fontes estão em `docs/fontes_bases_poi.md`.
- **Isócronas:** v2, do mesmo motor, nas áreas `pe_15` (900 s a pé) e `carro_10` (600 s de carro).
  - Ultra: `isocronas_v2`, tipo `ultra`.
  - Smart Fit: `isocronas_v2`, tipo `academia`, com `ponto_id` casado por `alunos_reais_por_unidade` (VPS).
  - Engenharia do Corpo e SkyFit: `multirede/atributos`.
- **População e renda das isócronas:** `testes_v2/base_ultra.parquet` (Ultra), `atributos_v2` (Smart Fit) e `multirede/perfil.parquet` (EdC e SkyFit).

### 3.1 Amostras e desfechos
- **S1, decide (Ultra, faturamento do Financeiro):** base `base_ultra` com metragem, `confianca != baixa` e pop disponível. Medido: N = 54.
  - Desfecho: log da mediana mensal de 2025-01 a 2025-12, usando só meses com `mes_completo`, `operacao_mes_cheio`, `origem_faturamento == financeiro` e `meses_operacao >= 6`. A unidade precisa de pelo menos 3 meses válidos; medido, as 54 têm.
  - Idade: meses desde a inauguração em 2025-07-01, nas faixas 6–11, 12–23 e ≥ 24 (referência).
- **S2, decide (Smart Fit, alunos):** alunos do painel `KPIs_Smart` (jan/23 a jan/26), casado por nome e UF com os `ponto_id` que têm isócrona (593 casam).
  - Desfecho: log da mediana de `Alunos Totais SF` de 2025-01 a 2025-12, com pelo menos 3 meses.
  - Maturidade: a unidade tem de estar no painel desde 2024-07 no máximo (medido: 460). Idade em faixas: 12–23 e ≥ 24, com primeira aparição em jan/23 contando como ≥ 24.
  - Covariável extra: `Propriedade` (Própria ou Franquia).
  - Nomes duplicados no painel são descartados.
- **Descritivas (não decidem):**
  - S1-estabilidade: mesmas 54 unidades, mediana de 2026-01 a 2026-08.
  - S3: Ultra, ativos 2025, para ler o mecanismo (volume ou ticket).
  - SkyFit (alunos, N ≈ 176) e Engenharia do Corpo (alunos, N ≈ 36).

### 3.2 Covariáveis base
- **S1:** log metragem, log renda per capita (carro_10, piso de 300), log(1 + pop carro_10) e as faixas de idade.
- **S2:** log renda, log pop (carro_10), faixas de idade e franquia. A Smart Fit não tem metragem.
- **F5 nos dois:** entra também `conc = log(1 + 1000 × oferta_ponderada_carro_10 / pop_carro_10)`, a concorrência mapeada, na base **e** no modelo com F5.

## 4. Famílias (4 testadas; sinal esperado declarado)
Em todas as famílias de CNPJ, conta só `data_inicio < 2025-01-01`.

| família | definição literal | área e forma | sinal |
|---|---|---|---|
| **F1** Emprego de escritório | CNPJ com `matriz_filial = 2` e CNAE principal na divisão 62, 63, 64, 65, 66, 69, 70, 71 ou 84, ou classe 8610-1 (hospital). Exceto 6462000 e 6470101/02/03. | pe_15: log(1+n) − log(1+pop_pe15) | + |
| **F2** Consumo de rua | CNPJ com `matriz_filial = 2` e CNAE principal na divisão 47, 56 ou 96 | pe_15: log(1+n) − log(1+pop_pe15) | + |
| **F3** Âncora de fluxo | 1 se há pelo menos 1 âncora a pé em 15 min, senão 0. Âncoras: (a) OSM `shop=mall` com nome; (b) OSM `railway=station`, `public_transport=station` ou `amenity=bus_station` (sem `subway_entrance`, `halt` e `marketplace`); (c) CNPJ 4711-3/01 (hipermercado/atacarejo) com geocodificação por ponto (`cnpj_cep_numero` ou `cnpj_cep`). Âncoras do mesmo tipo a menos de 300 m contam como uma. Shopping a menos de 150 m da unidade não conta (fato "unidade em shopping"). | pe_15, binária | + |
| **F5** Academias fora do universo mapeado | CNPJ 9313-1/00 com geocodificação por ponto (qualquer nível exceto `sem_coordenada`), a mais de 150 m de qualquer academia mapeada (`academias_pontos`, que tem cadeias e independentes do agregador) e de qualquer Ultra | carro_10: log(1 + 1000 × n / pop_carro10), com `conc` nos dois modelos | − |

- **Contagem nas famílias a pé (F1, F2):**
  - CNPJ `cnpj_cep_numero` conta como ponto.
  - CNPJ `cnpj_cep` e `cnpj_cep_area` contam pela fração dos endereços CNEFE do CEP (ponderados por `n`) que cai dentro do polígono.
  - `cnpj_cep5` e `sem_coordenada` não entram a pé.
- **Descritivo, sem teste:**
  - F2b: CNEFE "outras finalidades" com `nv_geo` de 1 a 3, a pé 15, na mesma forma de F2.
  - F4: CNPJ de educação superior (8531 a 8533) e OSM `amenity=university`, em carro_10.
  - "Unidade em shopping".
  - Fração da contagem vinda de geocodificação exata (qualidade de medida por unidade).

## 5. Portões medidos SEM desfecho (etapa 1, gravados antes da etapa 2)
- **P1 Colinearidade:** uma família com |r| ≥ 0,7 contra qualquer covariável base de S1 (incluindo log área da isócrona) é "não identificável" e sai do teste.
  - Entre famílias com |r| ≥ 0,8, fica só a primeira da ordem F1, F2, F3, F5.
- **P2 Suporte de F3:** em S1, é preciso ter pelo menos 10 unidades com F3 = 1 e pelo menos 10 com F3 = 0; senão F3 é "não testável".
- **P3 Idade:** publicar a correlação de cada F com a idade e com log m².
- **P4 Poder**, simulado com as F reais e antes de ver a relação F-desfecho:
  - y_sim = ŷ_base + π(e_base) + β·F⊥, com β calibrado para R² parcial de 0,03, 0,05, 0,10 e 0,20 em S1, e de 0,01, 0,02 e 0,05 em S2.
  - Cada cenário usa o teste da §6 (permutação com B = 199 dentro da simulação) e o limiar α/m do primeiro passo do Holm.
  - A simulação usa os resíduos do modelo base (é o desfecho real sem nenhuma F), declarado.
  - **Declaração antecipada:** se o poder em S1 for < 0,5 com R² parcial 0,10, "sem ganho detectável" é o resultado ESPERADO e não prova que POI não importa.

## 6. Teste (etapa 2)
- **Estatística:** ΔR² fora da amostra, R²(base + F) − R²(base).
  - S1: previsões leave-one-out do OLS, pela forma fechada e/(1 − h).
  - S2: GroupKFold por região metropolitana (10 dobras), porque há dependência espacial.
- **p:** permutação Freedman–Lane, com y* = ŷ_base + π(e_base), recalculando os dois modelos. B = 999 e p = (1 + #{ΔR²* ≥ ΔR²obs}) / (B + 1). Holm sobre as famílias que passarem nos portões, separadamente em S1 e em S2.
- **Sinal:** coeficiente do OLS com a amostra inteira.
- **Influência (S1):** refazer o ΔR² LOO sem a unidade de maior d_i = e²_base,i − e²_F,i.
- **IC95 do ΔR²:** bootstrap pareado com 2.000 reamostragens, só informativo.

## 7. Critério de decisão (congelado)
- **C1:** em S1, ΔR² > 0, sinal igual ao esperado e p de Holm < 0,05.
- **C1b:** em S1, ΔR² > 0 continua valendo sem a unidade mais influente.
- **C2:** em S2 (Smart Fit), ΔR² > 0, sinal igual ao esperado e p de Holm < 0,05.
  - Guarda: se |ρ(F, log m²)| ≥ 0,3 em Ultra + EdC (medido sem desfecho), C2 é "não avaliável" para aquela família, porque a Smart Fit não tem metragem.

**Veredito:**
- **ENTRA** (candidata ao UNI-02): C1, C1b e C2.
- **Candidata não confirmada:** C1 e C1b, com C2 não avaliável.
- **Sinal só na Ultra, não replica:** C1 e C1b, com C2 falhando.
- **Sinal só na Smart Fit:** C2 sem C1. Registrar como hipótese para a Ultra, sem entrar.
- **Sem ganho detectável neste N:** nenhum dos anteriores. Ler junto com o poder da §5.

## 8. Relatado, mas sem decidir
- Ridge, GroupKFold por UF (S1), S1-estabilidade, S3, SkyFit, EdC e o modelo com todas as famílias juntas.
- Sensibilidades:
  - F1 e F2 com todas as empresas (não só filial) e em carro_10;
  - idade ≥ 12 meses;
  - dummy de DF;
  - F5 com estoque anterior à inauguração da unidade;
  - F2b.
- Toda análise feita depois de ver o desfecho é rotulada como **exploratória**.

## 9. Não será feito
- Trocar área, variável ou recorte depois de ver o desfecho.
- Excluir outlier para ganhar métrica. A C1b só deixa o critério mais estrito.
- Somar CNPJ, CNEFE e OSM como contagens independentes.
- Independentemente do resultado, os POIs viram FATO DESCRITIVO do ponto (molde da DEC-026: fato sem peso).

## 10. Emenda v1.1: auditoria do código, antes de qualquer desfecho (2026-09-25)
Três revisores independentes leram o código contra o v1, só lendo. O que mudou, por quê, e com toda decisão tomada **antes** de cruzar POI com desfecho:

**Medição**
1. **Hipermercado (âncora de F3) e F4 sem corte de estoque.** Os dois passam a contar só `data_inicio < 2025-01-01`, como o §4 já mandava.
2. **Ordem da regra de F3 invertida.** A F3 agora agrupa primeiro as âncoras do mesmo tipo a menos de 300 m (ligação simples) e depois descarta o cluster de shopping que tenha **qualquer** membro a menos de 150 m da unidade. Antes, o shopping da própria unidade vazava quando aparecia duplicado no OSM (nó + way).
3. **Relações do OSM descartadas.** O extrator ignorava os multipolígonos (shopping grande, campus). O `01b_osm_relacoes.py` acrescenta 9.755 POIs, 135 deles de `shop=mall`.
4. **F5 só com CNPJ de endereço exato (`cnpj_cep_numero`).** A regra dos 150 m contra academia mapeada não funciona com centroide de CEP: a própria unidade mapeada caía fora dos 150 m e contava como "invisível". O P1 do v1 mediu uma variável contaminada (r = 0,86 com a renda). Com a correção, r = 0,23.
5. **plaza-sul-sp fora da S1.** O pino da base está na Rua Itaucama, a 1,34 km do endereço real: Shopping Plaza Sul, Praça Leonor Kaupa 100, confirmado nas listagens públicas de WellHub, TotalPass e Waze. A isócrona foi medida no lugar errado. É erro de dado, removido antes do desfecho. S1 fica com N = 53.
6. **Idade no mês mediano válido.** A idade passa a ser medida no mês mediano dos meses válidos de 2025 de cada unidade, e não em 2025-07-01. A data fixa jogava 9 unidades de 4 a 5 meses na faixa de referência (≥ 24). Há trava (`assert idade >= 6`).
7. **Ajustes na Smart Fit (S2):**
   - só `confianca_match == alta`;
   - duas unidades com o mesmo nome e UF saem (recebiam o mesmo y);
   - série, maturidade e desfecho agregados por **Sigla** (renomeação no painel não quebra);
   - o mínimo de meses conta valores não nulos;
   - N = 454.

**Estatística**

8. **Permutação restrita dentro do grupo:** UF em S1 e metrô em S2. Com dependência espacial, a permutação livre inflava o α. Em S2 o IC é por bootstrap de cluster (metrô).
9. **Veredito escrito em termos de C1r = C1 ∧ C1b.** "Sinal só na Smart Fit" = C2 sem C1r. A tabela das combinações está travada por `_trava_veredito()`.
10. **Poder:**
    - S1: B = 399, 200 réplicas.
    - S2: B = 199, 100 réplicas, com o mesmo GroupKFold por metrô e a mesma permutação restrita do teste real.
    - O erro Monte Carlo é reportado.
11. **NaN não vira zero.** Unidade sem polígono a pé fica com F3 = NaN, e sem carro_10 fica com F5 = NaN; o filtro de completos age sobre elas. A §8 filtra por família.

**Nova regra, P5, decidida com o P4 à vista e sem nenhuma relação F-desfecho**
Uma família com poder < 0,20 em S1 para R² parcial de 0,10 **não entra no Holm de S1**: ela gastaria α sem chance de detectar nada.
- Medido: F5 = 0,06 ± 0,02. F5 fica fora do Holm de S1 (C1 = "não avaliável", então o máximo possível é "sinal só na Smart Fit").
- F5 continua testada em S2, com poder 0,48 para R² parcial de 0,02.
- Holm: S1 sobre {F1, F3} (α/2); S2 sobre {F1, F3, F5}.
- F2 continua fundida em F1 (r = 0,90, P1).

### 10.1 Auditoria 2 (código reescrito, ainda sem desfecho)
12. **Unidade em shopping pelo POLÍGONO do shopping.** O `01c_osm_malls_poligono.py` extrai 3.551 polígonos de `shop=mall`, de ways e de relações. Com eles:
    - o shopping "próprio" é qualquer polígono a até 150 m da unidade, inclusive quando ela está dentro;
    - âncoras de shopping a até 150 m desse polígono saem.
    O centroide de um shopping grande ficava a mais de 150 m da academia que está dentro dele. Resultado: S1 com 11 unidades em shopping (antes 8) e S2 com 135.
13. **Simulação de poder sem vazamento.** Antes de permutar, o resíduo base perde a parte linear em [média do grupo de F⊥, F⊥ − média do grupo]. Sem isso, a permutação restrita preservaria a associação real F-desfecho entre grupos.
    - O poder de S1 foi medido com α/3 (regra anterior ao P5); o limiar real de S1 é α/2, então o número publicado é conservador.
    - P5 inalterado: F5 = 0,07 ± 0,02.
14. **Ambiguidade de nome da Smart Fit medida só no último mês do painel** (o mês que o crosswalk usou). A série inteira fica por Sigla.
    - Trava: a data do crosswalk precisa ser igual ao último mês do painel.
    - Funil publicado: 876 → 591 → 590 → 457 → 454.
15. **Na §8, dobras do GroupKFold refeitas depois da máscara**, com número de dobras limitado ao número de grupos.
16. **`fatos_poi_ultra.csv`** passa a ser gravado na etapa de portões, com os valores das famílias.
17. **A etapa 2 confere o SHA-256** do protocolo, dos scripts e do `portoes.json` contra o `REGISTRO_CONGELAMENTO.txt` antes de rodar.
