# BLK-UNI-16 — Preço de tabela do plano como entrada antes de abrir (pré-registro)

Versão 1.1, 2026-10-07. Escrito ANTES de ligar o preço ao desempenho. Só análise.

## Pergunta (Felipe, 06–07/10)

O preço do plano que o operador informa na aba de viabilidade ("Ticket cheio do plano") melhora a previsão dos três
modelos (faturamento, balcão e agregador) e do total recombinado?

**Escopo (decisões do Felipe em 07/10):**
- Só o preço de tabela. Lançamento/desconto, pré-venda e estúdio vendido na abertura ficam fora.
- A medida é a "tabela observada" (abaixo).

## O que a coleta mostrou (e mudou a v1.0)

- **A venda registra a primeira cobrança, não a mensalidade.**
  - Na unidade típica, metade das vendas de Gold no 1º ano sai abaixo de R$ 80, quase sempre a R$ 9,90 (primeiro mês
    promocional).
  - Em várias unidades do DF isso dura o ano inteiro.
- **O preço do plano só aparece nos meses sem essa promoção.**
- **Duas aberturas diferentes:**
  - 18 unidades venderam a preço cheio já no mês 1 (99% das vendas de Gold);
  - outras abriram só com a promoção.
- **A v1.0 media o degrau de lançamento.** Ela usava o primeiro mês com preço cheio, e a revisão de 07/10 achou que, em 26 de
  32 unidades, esse preço fica abaixo do que a própria unidade cobra depois. A v1.0 foi descartada antes de qualquer
  rodada.
- **Variação pequena:** o preço relativo vai de cerca de −17% a +9% da rede, em degraus de R$ 10. "10% acima" é mais ou
  menos um degrau.

## Dado

- **Vendas da Growth** (`precos/vendas_unidade_mes.parquet`):
  - jan/2023 a ago/2026, só agregados;
  - "preço cheio" = moda das vendas de Gold entre R$ 80 e R$ 200 (`precos/01_coletar_vendas.py`, função `agregar`).
- **Nomes casados** pela `depara_unidade`. "AGUAS CLARAS" é ambíguo (DEC-043) e fica sem dado.
- **Mês de vida:** o mês da inauguração é o mês 0, como no `fato_unidade_mes`.

## Variável

- `l_preco_rel` = **mediana**, nos meses de vida 1 a 12 com ≥ 10 vendas a preço cheio, de log(preço cheio da unidade ÷
  referência).
  - **Referência:** mediana do preço cheio das unidades **maduras** (mês de vida ≥ 12, ≥ 10 vendas cheias) na janela de 3
    meses em volta do mês.
  - A mediana entre meses fica com o preço que mais se repete, e não com o degrau de lançamento.
  - Exige ≥ 3 meses com preço cheio.
- **Sem a variável, duas marcas diferentes**, nos dois lados da comparação:
  - `sem_dado_venda`: menos de 3 meses de venda registrada nos meses de vida 1–12 (abriu antes da coleta, nome ambíguo
    ou fora da Growth);
  - `sem_preco_cheio`: tem venda, mas menos de 3 meses com preço cheio (promoção o ano todo, só plano multimês ou outro
    produto).
- Quem não tem a variável recebe a média das que têm.

## Teste

**Unidades:**
- as 57 do modelo juntas (39 maduras de 2025 + 18 de 2026), com o ajuste de nível de 2026 e o mesmo desfecho de cada
  modelo do UNI-15;
- o modelo é treinado nestas 57 (não nas ~60 do T2 do UNI-15), então os erros não batem com os de lá.

**Principal — o efeito, em cada modelo:**
- coeficiente de `l_preco_rel` no faturamento (v2), no balcão e no agregador (alvo "como se aceitasse os dois apps"),
  somado à v2 + ajuste de 2026 + as duas marcas;
- faixa robusta (HC3) de 90%, com p pela t de Student (graus de liberdade = unidades − parâmetros);
- **"tem efeito"** se, depois de Holm (k = 3, 10% dos dois lados), o p fica abaixo do limite;
- o sentido não é fixado: preço maior pode trazer menos alunos e mais ticket;
- a faixa mostrada é a sem correção, e o texto avisa que o veredito desconta os 3 modelos.

**Portão de adoção** (não é teste):
- erro de cada unidade prevista sem ela, nas 57, cai ≥ 2 pontos no faturamento **e** no total recombinado (refeito em cada
  rodada);
- leitura: o mesmo só nas unidades que têm preço, que é como seria na aba.

**Leituras (sem veredito):**
- só as unidades com preço (sem as marcas), nos três modelos;
- sem Botafogo;
- o efeito separado em alunos de balcão (log de pagantes) e ticket do balcão (balcão ÷ pagantes);
- o preço de **hoje** do cadastro (`cad_preco_gold`), relativo à mediana, nas mesmas unidades e nos três modelos: é de
  depois do resultado, só para comparação;
- referência só do mesmo mês, em vez da janela de 3 meses.

**Poder:**
- Pela simulação de 07/10 com 57 unidades, a detecção vai de 39% a 98% conforme a correlação real (0,2 a 0,5).
- Aqui o efeito vem só das unidades com preço e de uma variável com pouca variação, então o poder é menor.
- **"Não se distingue de zero" não prova que o preço não importa.**

## Exposição e limites

- As 57 unidades foram muito usadas. O preço com data nunca foi ligado ao desempenho; o preço de hoje (cadastro) foi, em
  29/09 ("mais caro, mais alunos", com direção incerta).
- **Reação à demanda:** o preço dos meses 1–12 pode ter subido porque a unidade encheu. Isso favorece achar efeito
  positivo; o texto do resultado avisa.
- **Turma de 2026:** as cegas ainda não têm 3 meses de preço cheio; nada é congelado agora. Conferir em 2027.
- **Prever não é causar.**

## Tier do Wellhub (registro, fora deste teste)

- Na releitura de 07/10, o tier do cadastro deu +21% de faturamento por nível (faixa +7% a +36%).
- Felipe (07/10): o tier "geralmente é definido antes", e "a depender da região ou desempenho pode acabar subindo, mas não é
  algo tão frequente".
- **Limite:**
  - as 5 cegas abriram **sem** Wellhub ("não possui", pela política de abrir sem agregador), assim como a maior parte da
    turma B e da de 2026;
  - o efeito foi medido em unidades que abriram com Wellhub.
- **Conferência:** quando as unidades de 2026 ligarem o Wellhub, o tier delas é registrado e conferido (BLK-UNI-12).

## Fluxo

Seca (contagens e distribuição, sem desempenho) → revisão (feita na v1.0; os 12 achados aplicados nesta v1.1) → ensaio com
ruído → REGISTRO_PRE (SHA) → rodada (com marcador de início e REGISTRO_POS) → verificação independente.

Saída: `uni16/resultado_uni16.md` e OneDrive `11 - Preço de tabela na abertura`.

### Contagens da seca da v1.1 (07/10; sem desempenho)

- **Preço de tabela:** 38 das 57 (22 das 39 e 16 das 18), com 6 meses de preço cheio na mediana.
- **Preço relativo:** de −17% a +17% das maduras, mediana 0%, desvio 9,5%.
- **Sem dado de venda (10):** aclimacao, aguas-claras, asa-norte, augusta, jundiai, lago-sul, mooca, plaza-sul, santos,
  vila-mariana.
- **Sem preço cheio (9):** aguas-lindas, botanic-mall, ceilandia-sul, cotia, lago-norte, poa-barra-sul, praia-grande,
  samambaia, vicente-pires.
- **Unidades por modelo:** faturamento 57, balcão 57, agregador 56.
- A v1.1 aplicou os 12 achados da revisão da v1.0 e não passou por nova revisão. A verificação independente depois da
  rodada cobre isso.
