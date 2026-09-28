# Cobrança de dado de origem — Inteligência de Unidade (BLK-DADOS-UNI-01)

> Lista para enviar a cada dono. **Nada aqui é estimativa**: cada linha traz o número medido, a
> data da medição e o arquivo onde ele está. O que não foi medido está escrito como não medido.
>
> Levantada em **2026-09-28** sobre a base de produção (Growth de 25/09, Financeiro ingerido em
> 08/09, cadastro de 06/08, feeds de agregador de 10 e 15/09). Fonte da apuração:
> `data/analysis/uni/COBERTURA_UNI00.md` e `depara_divergencias.md`.
>
> **Itens já resolvidos em código e fora desta lista:** o Financeiro casando por código
> (São Carlos), a musculação do agregador pelo V2, os pinos da Plaza Sul e da Sagrada Família, a
> reingestão do Financeiro e o contraste das fichas no tema claro.

---

## 1 · Financeiro

### 1.1 — A aba `Unidades_UX` manda o código 91 para o nome errado

| | |
|---|---|
| **O que está errado** | A aba de de-para diz `91 → "SÃO CARLOS - SP"`. A Growth e o Lifetime escrevem `"SAO CARLOS - CENTRO - SP"`, também com o código 91. |
| **Efeito medido** | Era o **único** nome sem par na Growth com faturamento > 0, entre 96 nomes de join. R$ 664.726 de abr–ago/2026 ficavam fora da Visão Executiva, que mostrava a receita da Growth (~19% abaixo). |
| **O que pedimos** | Corrigir o texto da célula `UNIDADE_UX` do código 91 para `SAO CARLOS - CENTRO - SP`. |
| **Urgência** | Baixa — o motor já contorna por código. A correção na origem é o que torna o contorno desnecessário. |

### 1.2 — Nove unidades sem `COD_UNIDADE` na aba `Unidades_UX`

`BONSUCESSO - RJ`, `CEILANDIA QNN 32 - DF`, `DOMINGOS FERREIRA - PE`, `FREGUESIA - RJ`,
`LIMEIRA - SP`, `NUCLEO BANDEIRANTE - DF`, `PAULÍNIA - SP`, `SÃO GONÇALO CENTRO - RJ` — e uma
nona que o aviso da ingestão trunca da lista.

Elas casam **só por nome**. Enquanto isso valer, qualquer divergência de grafia entre a
planilha e a Growth repete o caso de São Carlos, e o caminho por código não tem como salvar.

**O que pedimos:** preencher o `COD_UNIDADE` das nove na aba `Unidades_UX`.
**Urgência:** média — é a prevenção do item 1.1.

### 1.3 — Dezesseis unidade-mês com R$ 0 e a academia operando

O painel trata como "mês sem lançamento", não como faturamento zero. Precisamos saber qual dos
dois é.

```
andre-de-barros-pr      2026-05
arapoanga-planaltina-df 2023-10
brasilandia-sp          2022-06
campo-largo-pr          2024-04
jardim-botanico-df      2022-11
lago-norte-df           2024-02
noroeste-df             2024-12
samambaia-df            2024-02
sao-goncalo-shopping-rj 2025-09
serra-es                2024-04
sobradinho-df           2023-07
sorriso-mt              2023-12
taguatinga-df           2024-04, 2024-05, 2024-06
vila-guanabara-sc       2025-02
```

**O que pedimos:** para cada linha, dizer se o mês teve faturamento zero de verdade ou se o
lançamento ficou pendente. **Urgência:** média — afeta a amostra das hipóteses de rampa.

### 1.4 — A ingestão logo depois da virada pega célula ainda em edição

**Medido:** a ingestão de 08/09 gravou o Guarujá de ago/2026 como R$ 547.745,05. A planilha de
28/09 traz **R$ 217.525,74**. Foi a **única** célula divergente entre as 6.528 comparáveis — e
ficou 20 dias na tela de produção.

**O que pedimos:** nada da planilha. É **lição nossa**: reingerir ~10 dias depois da virada,
não no dia seguinte. Fica registrado aqui porque a causa mora na cadência da fonte.

---

## 2 · Growth

### 2.1 — Inauguração placeholder 23/08/2021 em quatro unidades

`Aclimação`, `Mooca`, `Plaza Sul`, `Vila Mariana`.

O primeiro faturamento do Financeiro sugere abertura por volta de **set/2021**, mas isso é
inferência nossa, não dado. Hoje a **idade** dessas quatro sai `NaN`, e elas ficam fora de toda
leitura por maturidade (rampa, coorte, aproveitamento).

**O que pedimos:** a data real de inauguração das quatro. **Urgência:** alta — é o insumo que
mais amplia a amostra das análises por maturidade.

### 2.2 — Três anomalias de série para confirmar (não excluir sem prova)

| unidade | o que a série mostra | período |
|---|---|---|
| Brasilândia | vale de receita de **−45%** com ativos estáveis | out/25 → mai/26 |
| Vila Guilherme | vale de receita de **−45%** com ativos estáveis | out/25 → mai/26 |
| Suzano | **−52%** de ativos, com agregadores caindo de **2.964 para 919** | abr → ago/26 |

Receita caindo com aluno estável (ou o contrário) é sinal de troca de regime de lançamento, não
de operação — mas pode ser operação de verdade. **Não vamos excluir nenhuma delas da amostra sem
resposta.**

**O que pedimos:** confirmar se houve evento real (reforma, mudança de contrato de agregador,
migração de sistema). **Urgência:** média.

---

## 3 · Cadastro (planilha do time de campo)

### 3.1 — A semeadura é de 06/08 e cobre 92 das 98 unidades

**Medido em 2026-09-28** contra o `cadastro_unidades.json` da VPS: seis unidades da rede não têm
registro nenhum.

```
freguesia-rj            nucleo-bandeirante-df   via-brasil-shopping-rj
jardim-das-americas-mt  sao-carlos-centro-sp    vila-izabel-pr
```

Elas ficam sem `cod_unidade`, sem consultor, sem master, sem tier de agregador e sem retenção —
e é **exatamente por isso** que o Financeiro de São Carlos precisou de uma tabela declarada em
código: a Growth não carrega código, e o único artefato de produção que carrega é o cadastro.

**O que pedimos:** a planilha `ANALISE DIARIA DASHBOARD.xlsx` atualizada, para rodar
`scripts/semear_cadastro_unidades.py`. **Urgência: alta** — é o item que destrava mais coisas de
uma vez.

### 3.2 — Tier TotalPass divergente entre cadastro e feed, em dez unidades

O cadastro (ago) diz **TP1+**; o feed do agregador (set) diz **TP 2**.

```
cruzeiro-df    lago-sul-df   santa-maria-df   valparaiso-go   centro-comendador-pr
poa-barra-sul-rs   aclimacao-sp   cotia-sp   jundiai-sp   mooca-sp
```

**O que pedimos:** confirmar se houve troca de tier e atualizar o cadastro. **Urgência:** média
— o tier é régua de posicionamento de preço, e dez unidades erradas deslocam a leitura.

### 3.3 — Quatro pinos de confiança baixa, geocodificados pelo Nominatim

`Boa Vista - BA`, `Vicente Pires Rua 8 - DF`, `Domingos Ferreira - PE`, `Boqueirão - SP`.

Não são pinos comprovadamente errados: são pinos **sem confirmação**. Vieram de consulta a
endereço, não de coordenada informada — e o caso da Plaza Sul mostrou o que um pino a 1,3 km faz
com isócrona, concorrência e sobreposição.

**O que pedimos:** a coordenada conferida das quatro (como foi feito para a Plaza Sul e a Sagrada
Família). **Urgência:** média.

### 3.4 — Duas linhas de cadastro para a mesma academia do Plaza

**Medido:** `unidades_ultra_mapeadas.parquet` tem `Plaza / SP` (−23,619857, −46,626529) e
`Plaza Sul` (−23,607786, −46,627038), a **1.340,7 m** uma da outra. É **uma** academia.

A camada de mercado conta as duas como oferta Ultra instalada.

**O que pedimos:** decidir qual linha fica e apagar a outra no cadastro de pinos. **Urgência:**
média. **Atenção:** corrigir isso mexe em `oferta_consumida_ultra_real` e portanto no residual —
é regeneração com as guardas da DEC-059, não edição de mão.

---

## 4 · Levantamento de metragem

### 4.1 — Metragem ausente em 44 das 98 unidades

`data/ultra/dados_academias.xlsx` cobre as unidades maduras em abr/2026. A falta **não é
aleatória**: é justamente a rede aberta depois disso.

É o item que mais aumenta a amostra das hipóteses de tamanho — tamanho × concorrência e
patamar por m² são, as duas, razões que têm m² no denominador. Sem metragem, a unidade não entra
em nenhuma das duas.

**O que pedimos:** metragem das 44 restantes e, se possível, o número de **vagas**.
**Urgência: alta** — junto com o 2.1, é o que mais dá poder às etapas seguintes.

---

## Fora desta lista, de propósito

- **Isócrona a pé degenerada em Lago Sul** (0,16 km² e 20 habitantes, contra mediana de 1,9 km²):
  não é dado de origem, é provável *snap* do ponto de partida num trecho sem malha de pedestre.
  Conserto nosso, na camada de isócronas.
- **Export do Projeto Lifetime** (retenção da coorte de abertura e pré-venda): insumo externo com
  bloco próprio, `BLK-UNI-PEND-01`.
