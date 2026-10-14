# Pontos de interesse explicam o resultado das academias? Teste pré-registrado (BLK-UNI, UNI-00/01)

> 2026-09-25. Camada paralela e READ-ONLY sobre o M1.
> - Protocolo: `protocolo_poi_uni00.md` (v1.1, congelado com SHA-256 em `REGISTRO_CONGELAMENTO.txt`).
> - Resultado decisório: `saidas/resultado_teste_poi.md`.
> - Exploratório: `saidas/exploratorio_poi.md`.

## Conclusão
**POI não entra no modelo de faturamento agora.** As três variáveis testadas ficaram **sem ganho detectável**, na Ultra e na Smart Fit:
- densidade de escritórios a pé;
- âncora de fluxo a pé (shopping, estação, atacarejo);
- academias fora do universo mapeado.

Os POIs viram **fato descritivo** do ponto, sem peso.

O nulo tem limite, e ele precisa ir junto:
- **Ultra (N = 53):** o teste era subpotenciado. Um efeito de ~13% no faturamento por desvio-padrão de POI tinha ~50% de chance de passar despercebido.
- **Smart Fit (N = 454):** o teste exclui efeito homogêneo sobre alunos acima de ~2% de R² parcial.
- O nulo vale para **estas variáveis como foram medidas**, não para "POI em geral".

## O que foi testado
| família | medida | área | sinal esperado | status |
|---|---|---|---|---|
| F1 Emprego de escritório | filiais de CNPJ (TI, financeiro, jurídico, consultoria, governo, hospital) por habitante | 15 min a pé | + | testada |
| F2 Consumo de rua | filiais de CNPJ de varejo, alimentação e serviços pessoais por habitante | 15 min a pé | + | fundida em F1 (r = 0,90) |
| F3 Âncora de fluxo | ≥ 1 shopping, estação ou atacarejo, fora o shopping da própria unidade | 15 min a pé | + | testada |
| F5 Academias fora do mapeado | CNPJ 9313 a > 150 m de qualquer academia mapeada, por mil habitantes | 10 min de carro | − | só na Smart Fit (poder 0,07 na Ultra) |
| F4 Universidade | — | — | — | só descritiva |

- **Ultra:** a base é log faturamento do Financeiro em 2025 (mediana mensal, meses com 6+ meses de operação) contra log m², log renda, log pop e faixa de idade.
- **Smart Fit:** a base é log alunos em 2025 (painel mensal) contra log renda, log pop, idade e franquia.

## Resultado decisório (run 2)
| família | Ultra ΔR² (LOO) | p | Smart Fit ΔR² (GroupKFold por metrô) | p | veredito |
|---|---|---|---|---|---|
| F1 | −0,031 | 0,71 | −0,043 (sinal trocado) | 0,99 | sem ganho detectável |
| F3 | −0,028 | 0,66 | −0,002 | 0,42 | sem ganho detectável |
| F5 | não avaliável (poder) | — | −0,014 | 0,21 | sem ganho detectável |

O ΔR² negativo quer dizer que acrescentar a variável **equivale a acrescentar ruído** fora da amostra, não que o POI piora a unidade.

O sinal bruto existe, mas é absorvido pela base. A correlação de F1 com o faturamento é +0,28 (+0,38 na versão de carro) e cai para +0,07 contra o resíduo do modelo base. F1 anda junto com a renda (r = 0,46), e a parte de F1 que não é renda não explica o faturamento.

## Robustez
Todas as checagens abaixo dão nulo (ΔR² ≤ 0) e não mudam o veredito:
- **Com e sem as relações do OSM:** veredito idêntico nas duas rodadas (ver Desvio declarado).
- **Contagem:** todas as empresas (não só filiais); área de carro em vez de a pé; CNEFE no lugar do CNPJ (F2b).
- **Estoque:** F5 contando só o que existia antes da inauguração.
- **Composição da amostra:** dummy de DF; sem DF (N = 34); sem a isócrona degenerada de Lago Sul.
- **Validação e janela:** GroupKFold por UF; ridge; estabilidade em jan–ago/2026.
- **Outros desfechos e redes:** Ultra ativos, SkyFit (N = 175) e Engenharia do Corpo (N = 35).
- **Tudo junto:** o modelo com todas as famílias.

## Exploratório (não decide; 26 testes sem correção, ~1,3 "p < 0,05" esperado por acaso)
- **Pista para pré-registrar:** dentro do mesmo metrô, na Smart Fit (12 metrôs, N = 418), a **população a 15 min a pé** se associa a mais alunos (ΔR² +0,010, p = 0,016).
  - Em F1, o sinal negativo vinha desse denominador.
  - A ideia é coerente com academia low-cost de bairro, mas não sobrevive à correção.
  - Candidata a hipótese pré-registrada no UNI-02: pop a pé dentro da cidade, confirmada na Ultra.
- **O metrô explica 17,5% dos alunos da Smart Fit; renda e pop, ~0.** Entre metrôs, R² LOO +0,001 sem efeito fixo e +0,175 com ele. Coerente com a DEC-043: a variação de desempenho não é territorial fora da praça.
- **"Idade ≥ 12 meses, F3"** (ΔR² +0,05, p = 0,044) é frágil:
  - vai a p = 0,13 com a troca de uma única unidade na F3 (Praia Grande, pelas relações do OSM);
  - vai a p = 0,28 com GroupKFold por UF;
  - vai a p = 0,13 sem o DF.
  Não é pista.
- **Estar em shopping** não ajuda na Ultra (p = 0,86). Na Smart Fit dá p = 0,064, também não é pista.

## Qualidade de medição (limita o que se pode afirmar)
- **Geocodificação v2:** 47% dos CNPJs com endereço exato no país, mas ~2% no DF (endereço de quadra). No DF, F1 e F2 vêm do rateio por CEP, e **F5 não é medida** (conta só endereço exato). 4 metrôs da Smart Fit estão nesse regime; tirá-los não muda nada (E7).
- **Lago Sul:** a isócrona a pé é degenerada (0,16 km² e 20 habitantes, contra mediana de 1,9 km²). O F1 dela não deve ser publicado como fato.
- **plaza-sul-sp** saiu antes do desfecho: o pino estava na Rua Itaucama, 1,34 km do endereço real (Shopping Plaza Sul). **Corrigir o pino no cadastro** e refazer a isócrona. Sobradinho foi conferida e está certa.
- **Estoque de CNPJ:** só ativos em set/26, contados como estoque em 2025. Viés de sobrevivência declarado.

## Achado colateral sobre o modelo de faturamento
Na janela de 2025 com idade, o R² LOO da base Ultra é **0,285**; sem idade, 0,304. Na janela set/25–ago/26 são **0,39**, com as mesmas 53 unidades. O número depende da janela, então o UNI-02 deve reportar sempre janela e especificação junto com o R².

## Desvio declarado
- **O que houve:** a 1ª rodada (`saidas/resultado_teste_poi_run1_sem_relacoes_osm.md`) rodou sem as relações do OSM, porque o `04` foi executado com `| head -1` e o SIGPIPE o matou após a 1ª UF.
- **O que mudou:** código e protocolo não mudaram (mesmo SHA). A base foi refeita, só os hashes de dados foram re-registrados, e a 2ª rodada é a oficial.
- **Efeito:** 1 unidade da Ultra (Praia Grande) e 1 da Smart Fit mudaram de F3; o veredito é idêntico.

## Como foi feito
1. Base única de POIs: CNPJ, CNEFE e OSM, 46 milhões de pontos (`docs/fontes_bases_poi.md`).
2. Protocolo v0, criticado por 4 lentes → v1.
3. Duas auditorias de código antes do desfecho → v1.1, com ~20 correções:
   - geocodificação refeita;
   - estoque na âncora;
   - shopping pelo polígono;
   - permutação restrita e simulação de poder sem vazamento;
   - Smart Fit por Sigla.
4. Portões sem desfecho: colinearidade, suporte, poder.
5. Congelamento com SHA-256.
6. Teste.
7. Três céticos tentaram derrubar o nulo: sem bug, com ressalvas incorporadas acima.

## Próximos passos sugeridos
1. **Fato descritivo no ponto** (Relatório Pontual / viabilidade): em 15 min a pé, nº de shoppings, estações e atacarejos e "unidade em shopping"; em 10 min de carro, escritórios e universidades. Contagem bruta, com flag de qualidade (`frac_exato`), sem semáforo, suprimindo F5 no DF.
2. **UNI-02:** pré-registrar a **pop a pé dentro da cidade** como a única candidata que saiu daqui.
3. **Cadastro:** corrigir o pino da Plaza Sul. Revisar a isócrona a pé de Lago Sul (possível snap num trecho sem malha de pedestre).
