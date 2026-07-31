# Sonda — a nota in-app existe nos agregadores? (WellHub e TotalPass)

> Evidência de suporte aos blocos **BLK-MA-08**, **BLK-MA-09** e **BLK-MA-10**.
> Medido em 2026-07-30 e 2026-07-31 por Claude, a pedido de Vinicius.
> Camada **PARALELA e READ-ONLY sobre o M1**. Nenhum dado coletado foi persistido além dos
> agregados numéricos desta página; nenhuma PII.

## 1. Pergunta

O sinal 2 do score de vulnerabilidade (rating in-app) está `n/d` desde o gate 2 (2026-07-23), com a
justificativa registrada no contrato de que **nenhum coletor emite nota** e de que
*"WellHub = mesmo schema do TotalPass → também sem nota"*
(`docs/vulnerabilidade_ma_contrato.md`, §1 `:60-62`, §7 `:220-225`, §13 `:509`). Essa premissa foi
registrada com a ressalva honesta de que **só havia amostra de TotalPass versionada no repo**.

A pergunta desta sonda: a nota está disponível em alguma superfície pública que os coletores já
alcançam?

## 2. Método

Requisições `GET` às páginas públicas de unidade, com a **mesma sessão e os mesmos headers do coletor
de produção** (`gymscraping/core/http.py` + `BROWSER_HEADERS` dos respectivos `pipeline.py`),
espaçadas por 1,2 a 2,0 s. Duas rodadas:

- **Rodada dirigida** (2026-07-30) — 2 slugs por agregador, mais inspeção do JSON-LD e varredura de
  tokens de rating no HTML bruto.
- **Rodada estratificada** (2026-07-31) — amostra aleatória de **2 slugs por UF nas 27 UFs**
  (`seed=42`) a partir dos CSVs já coletados, medindo cobertura e distribuição.

URLs: `https://wellhub.com/pt-br/search/partners/{slug}/` e
`https://totalpass.com/br/academias/{slug}/`.

## 3. Resultado — WellHub: a nota ESTÁ no HTML que o coletor já baixa

O payload RSC (`self.__next_f.push`, Next.js App Router) traz, no mesmo HTML de ~380 KB que o coletor
já baixa e já parseia para `address` e `activities`:

```
\"partnerRating\":{\"value\":4.81,\"label\":\"(105 Avaliações)\"}
```

Objeto plano, sem aninhamento, **1 ocorrência por página** — diferente de `activities`, que aparece
7× (1 do parceiro-alvo + 6 da sidebar) e por isso exigiu âncora especial. O JSON-LD
(`SportsActivityLocation`) **não** traz `aggregateRating`: o RSC é a única fonte.

**Cobertura: 53 de 54 unidades (98,1%).**

| Métrica | Valor |
|---|---|
| Notas obtidas | 53 (de 54 sorteadas) |
| Faixa | 4,26 – 4,98 (amplitude 0,72) |
| Média / mediana | 4,782 / 4,79 |
| Desvio-padrão | 0,127 |
| Decis | 4,62 · 4,72 · 4,73 · 4,76 · 4,79 · 4,83 · 4,87 · 4,89 · 4,92 |
| Avaliações por unidade | 25 – 816 (mediana 156); só 2/53 abaixo de 30 |

Histograma (bin 0,1): `4,2-4,3` 1 · `4,5-4,6` 2 · `4,6-4,7` 4 · `4,7-4,8` **21** · `4,8-4,9` 15 ·
`4,9-5,0` 10.

### 3.1 O caso sem avaliações — forma DIFERENTE no payload

A unidade `salus-estudio-personal-trainer-vila-nova` (a 1 de 54) devolve HTTP 200 e 372 KB, mas o
campo vem como **`\"partnerRating\":null`** — o objeto inteiro nulo, **não** `{"value":null,...}` —
imediatamente após `\"newPartner\":{\"label\":\"Novo no Wellhub\",\"isNew\":false}`.

**Consequência de projeto:** um parser que só procure a forma preenchida reporta "campo ausente"
tanto para *sem avaliações* (estado legítimo) quanto para *layout mudou* (quebra do scraper). As duas
condições precisam ser distinguíveis, senão uma quebra silenciosa entra no score como `n/d` e
ninguém percebe. Ver o critério de aceite do BLK-MA-08.

### 3.2 Impacto da régua linear do §8.1

Aplicando a fórmula que o §8.1 dá como exemplo (`v2 = 1 − (rating − 1) / (5 − 1)`) às 53 notas:

| Métrica | Valor |
|---|---|
| `v2` resultante | 0,0050 – 0,1850 |
| Domínio ocupado | **18,0%** do `[0,1]` disponível |
| Contribuição ao score (peso 0,25) | máximo **4,63** de 100 pontos; amplitude de **4,50** entre a pior e a melhor nota |

A distribuição **tem** variância real (desvio 0,127; decis espalhados de 4,62 a 4,92) — é a régua
linear sobre o intervalo teórico 1–5 que a desperdiça, porque notas de app não ocupam a metade
inferior da escala. A escolha de régua é decisão de gate do **BLK-MA-09** (D-A).

> **Ressalva de universo.** Esta amostra saiu do universo WellHub inteiro, **não** do universo-alvo da
> epic (`independente`). A distribuição precisa ser re-medida restrita a independentes antes de fixar
> qualquer limite de régua.

## 4. Resultado — TotalPass: nenhuma superfície de nota

**7 de 7 unidades sem qualquer sinal de nota.** O JSON-LD é idêntico em todas as amostras — 9 chaves
(`@context`, `@type`, `address`, `geo`, `image`, `name`, `openingHours`, `telephone`, `url`), **sem**
`aggregateRating`. No HTML inteiro (54–63 KB): zero ocorrência de `aggregateRating`, `ratingValue`,
`reviewCount`, `avalia`, `review`, `estrela` ou `nota`.

A página é Next.js **App Router** (payload RSC; `__NEXT_DATA__` ausente). Hosts citados no HTML,
medidos ao vivo em 2026-07-31 nos slugs `fit-academia` e `id-datafitness-ttp`:

`ajuda.totalpass.com.br` · `assets.totalpass.com` · **`booking.totalpass.com`** ·
`cloud.info.totalpass.com.br` · **`cms.totalpass.com`** · `hr.totalpass.com` ·
`images.totalpass.com` · `maps.googleapis.com` · `play.google.com` · `www.googletagmanager.com` ·
`vempratotalpass.pandape.infojobs.com.br`

**Leitura:** o produto web do TotalPass não tem interface de avaliação de unidade — não é uma nota
escondida atrás de uma API web. `booking.` e `cms.` são superfícies do próprio TotalPass **ainda não
sondadas** e são o alvo natural de qualquer investigação seguinte (BLK-MA-10), antes da hipótese mais
cara (app mobile autenticado). A presença de `maps.googleapis.com` é o mapa da página.

> **Nota de reprodutibilidade.** As fixtures versionadas em
> `GymScraping/TotalPass/tests/fixtures/` são de coleta anterior e **não** contêm
> `maps.googleapis.com`; a lista acima é da medição ao vivo de 2026-07-31. O que é reproduzível pelas
> fixtures: as 9 chaves do JSON-LD, a ausência total de tokens de rating, o tamanho (57–58 KB) e o
> App Router.

## 5. Conclusão

A premissa *"WellHub = mesmo schema do TotalPass → também sem nota"* está **falsificada**. A
equivalência de schema vale para o CSV de **saída**, não para o HTML de **origem**:

| | Nota disponível? | Onde | Custo | Universo |
|---|---|---|---|---|
| **WellHub** | **Sim**, 98,1% | payload RSC do HTML já baixado | +1 regex, +1 coluna; zero request extra, zero auth | 12.769 unidades |
| **TotalPass** | **Não** | nenhuma superfície pública identificada | superfícies não sondadas (`booking.`/`cms.`), depois app mobile autenticado | 15.986 unidades |

Consequência para a epic: o sinal 2 passa a ser possível **para um subconjunto do universo** — cenário
que o contrato nunca contemplou e que é o objeto do **BLK-MA-09** (régua assimétrica por fonte).

## 6. Reprodução

Scripts da sonda não foram versionados (uso único, sem valor de manutenção). A reprodução é direta:
`GET` na URL de parceiro com os headers do coletor e busca pela regex
`\\"partnerRating\\":\{[^{}]*\}` no HTML (WellHub) ou pelos tokens de rating no HTML e no JSON-LD
(TotalPass). As 4 fixtures em `GymScraping/Wellhub/tests/fixtures/` já contêm `partnerRating`
(`partner_norpra` 4,81 · `partner_gabi_marie` 4,71 · `partner_ctf_londrina` 5 ·
`partner_max_trainer` 5), o que permite verificar o parsing **sem rede**.
