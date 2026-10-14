# Manaus — o volume de ~2.900 alunos se sustenta ou pode ser maior?

Versão 1.0, 2026-09-30. Protocolo escrito **antes de rodar**. Só análise.

## 1. Pergunta

A v2 ajustada em alunos ativos prevê ~2.880 ativos maduros para a unidade de Manaus (pino NOVA CIDADE; 2.000 m²,
1 estúdio, master de RJ/SP). O Felipe foi questionado por que "só 2.900/3.000". Esta análise quer:

- (a) um jeito **confiável** de elevar o número; ou
- (b) dado que defenda que ele não deve ser maior.

Não é teste de hipótese para mudar o modelo, e sim um pacote de evidências com critério fixado antes.

## 2. Passo 0 — o que fica congelado (em `REGISTRO_CONGELAMENTO.txt`)

**Previsão atual:** v2 em ativos, com a praça aproximada por círculo de 5 km (`simulacoes/resultado_manaus_volume.md`):

| master | ativos | faixa de 80% |
|---|---|---|
| M3 | 2.884 | 1.918 a 4.517 |
| "outras" | 2.739 | — |

O faturamento correspondente é de R$ 421 mil a R$ 167, com o plano de estúdio.

**Passo 0b — isócrona real do pino.** O grafo de Manaus (`metro_44`) já existe, então a isócrona de 10 min de carro
do pino é gerada com a **mesma função** do pipeline das unidades (`03_isocronas.processar_lote`, ISO_VERSAO=_v2), e os
atributos com `04_atributos.atributos_poligono`.

- **Regra fixada antes:** se a isócrona **não** estiver truncada, os atributos dela **substituem** os do círculo na
  previsão central; se estiver truncada, fica o círculo e a isócrona é só reportada.
- A master central continua M3, como no número já apresentado. "outras" e a média da rede são reportadas ao lado.

## 3. Passo 1 — teto de balcão na rede

Esta é a evidência principal a favor de um teto.

- **Universo:** unidades maduras de 2025–2026 (mês de vida ≥ 12, ≥ 3 meses válidos entre 2025-01 e 2026-08). Por
  unidade, a média mensal de `ativos`, `pagantes` (balcão) e `agregadores`.
- **Pré-checagem:** mediana de |ativos − (pagantes + agregadores)| / ativos. Se passar de 5%, isso é declarado, e o
  balcão continua sendo medido por `pagantes`.
- **Praça de renda baixa:** renda domiciliar da isócrona de 10 min de carro no **terço inferior** do universo. A régua
  é a domiciliar, padrão do produto.
- **Balcão necessário para 3.500 ativos**, com a fatia de agregador "outros" da regra por estado (43%):
  B = 3.500 × 0,57 = **1.995**.
- **Critério:**
  - **Sustenta teto** se o maior `pagantes` entre as praças de renda baixa for menor que B.
  - **Sustenta número maior** se ao menos 2 praças de renda baixa tiverem `pagantes` ≥ B.
  - Qualquer outro resultado é **inconclusivo**.
- **Descritivo:** as 10 maiores unidades em ativos, com a composição balcão × agregador, e a distribuição de `pagantes`
  no universo todo.

## 4. Passo 2 — efeito praça medido pela Smart Fit (a única marca com dado em Manaus)

- **Amostra:** unidades da Smart Fit maduras (no painel desde jul/2024 ou antes), casadas ao crosswalk com isócrona.
  É a mesma função `amostra_S2()` do teste de POI.
- **Desfecho:** log da **mediana mensal de "Alunos Totais SF" em 2025**, exigindo ≥ 6 meses em 2025.
- **Portão:** ≥ 3 unidades no metrô de Manaus (id 44). Se não houver, o passo sai **inconclusivo**.
- **Modelo:** efeito fixo por metrô.
  - (i) sem controles;
  - (ii) com log renda e log população da isócrona de 10 min, franquia e idade 12–23 meses.
- **Métrica:** r = exp(EF_Manaus − média dos EF dos metrôs das 39 unidades Ultra de treino, ponderada pelo número de
  unidades Ultra em cada metrô).
  - Os metrôs Ultra sem Smart Fit na amostra saem, e os pesos são renormalizados. A cobertura é reportada.
  - IC90 por bootstrap de unidades estratificado por metrô, com 2.000 repetições.
- **Critério, na versão (ii)**, que é a relevante porque a v2 já controla renda e população:
  - **sustenta número maior** se o IC90 inteiro ficar acima de 1,10;
  - **sustenta teto** se o IC90 inteiro ficar abaixo de 1,00;
  - entre os dois, **neutro**.
- **Uso:** se o passo sustentar número maior, reporta-se "v2 com a master média da rede × r(ii)" como número
  alternativo. Ele não substitui o central sem decisão do Felipe.

## 5. Passo 3 — mercado de agregador na praça (escolhe o cenário de mix, não mexe em coeficiente)

- **Métrica:** academias de musculação parceiras do Wellhub por mil habitantes na isócrona de 10 min, sem a Ultra e
  sem estúdios boutique. É a mesma regra de `03_dim_unidade.planos`.
- **Comparação:** Manaus (isócrona real do Passo 0b) contra `wh_n_conc_c10 / iso_pop__carro_10` das unidades do
  universo. O TotalPass é reportado à parte, sem somar.
- **Critério pelo percentil de Manaus:**
  - ≤ p50 → cenário de mix de **30%** (padrão DF/GO);
  - ≥ p75 → **55%** (padrão SP);
  - entre os dois → **43%**.
- **Limite declarado:** no estudo do mix, a presença de agregador não previu a fatia fora da amostra (X5). Por isso é
  seletor de **cenário**, não previsão.

## 6. Passo 4 — hipótese do diretor (tamanho × concorrência de estrutura menor), só como sensibilidade

- **Fração de independentes** de Manaus na isócrona real (`n_independente_agregador / n_academias`).
- Se ficar **fora** do p10–p90 do treino, é extrapolação: não se reporta número.
- Se ficar **dentro**, ajusta-se a v2 em ativos + frac_indep + z(log m²) × z(frac_indep) nas 39 de treino e reporta-se
  a previsão de Manaus **ao lado** do central, sem substituí-lo. O M0d não passou no UNI-02.

## 7. Passo 5 — compromisso depois de abrir

- **Nível maduro projetado** = ativos do mês k completo ÷ p50 da curva do UNI-03 (`uni03/curva_uni03.csv`).
- **Gatilhos para o mês 3:**
  - revisa para **cima** se a projeção for ≥ 3.500;
  - revisa para **baixo** se for ≤ 2.300.
  - Os valores de ativos no mês 3 correspondentes são impressos.
- O mês 1 é só alerta: a cobertura foi de 59%.

## 8. Regra de síntese (fixada antes)

- **"Os dados sustentam número maior"** se:
  - o Passo 2 der "maior"; **ou**
  - o Passo 1 der "maior" **e** o Passo 3 der ≥ p75.
- **"Os dados sustentam teto de ~3.000"** se o Passo 1 der "teto", o Passo 2 **não** der "maior" e o Passo 3 der
  < p75.
- **Qualquer outra combinação:** mantém-se o central com a faixa e o gatilho do mês 3.

**Ressalva que vai junto em qualquer desfecho:** nas unidades novas com estúdio, o teto da faixa furou em 4 de 18
(BLK-UNI-08). O risco de subestimar existe e não é previsível antes de abrir.

## 9. Limites

- **Amostra condicionada no desfecho:** o p90 da rede é o teto nas praças que a Ultra escolheu. Unidades encerradas
  ou excluídas não estão nas maduras, então a distribuição sai otimista.
- **Contagem de agregador:** a do UX não é limpa (premissa de 60% mantida). O balcão por `pagantes` é a medida menos
  contaminada.
- **Smart Fit:**
  - não tem metragem;
  - o total inclui agregador, e a marca é do grupo do TotalPass;
  - mede a praça para **outra** marca.
- **Anacronismo:** as listagens de agregador e de concorrência são fotos de set/2026, e o desfecho é de 2025–2026.
- **Nulos de baixo poder:** saturação e residual não mostraram efeito, mas com efeito mínimo detectável de ~30%. Isso
  **não** prova teto.
- **Circularidade:** a isócrona do pino usa o mesmo grafo/snap do pipeline, mas o ponto não é unidade em operação.

## 10. Arquivos

- `manaus_volume/01_isocrona_pino.py` → `isocrona_pino.parquet`, `atributos_pino.json`
- `manaus_volume/02_evidencias.py` → `resultado_manaus_volume_evidencias.md`
- Congelamento em `REGISTRO_CONGELAMENTO.txt`, com SHA-256 do protocolo e dos scripts.

## 11. Emenda v1.1 (2026-09-30), depois da revisão adversarial e ANTES de rodar o 02

A revisão teve duas lentes, método e código, e achou 6 bloqueadores. Cada item abaixo substitui o texto correspondente
acima.

**Passo 0 — número central e reprodução.**
- O central direto é a v2 em ativos com M3 e a praça pela isócrona real, porque ela não está truncada.
- Conferência de reprodução: o M3 no círculo precisa dar 2.884 ± 1.

**Passo 0c (novo) — o central pode estar carregando agregador de SP.**
- O coeficiente de M3 é +0,315 em ativos, contra ~0 em faturamento.
- Para separar isso, ajusta-se a v2 em log(`pagantes`) nas mesmas unidades de treino, com o desfecho definido como em
  `desfechos`. Com o balcão previsto para Manaus (M3), o **central por componentes** = balcão ÷ (1 − mix):
  - mix de 43% ("outros" da regra por estado) como padrão;
  - 30% e 55% como cenários.
- Reporta-se a mediana de agregador das unidades M3.
- O central direto e o por componentes aparecem lado a lado.

**Passo 1 — refeito em ATIVOS, ajustado ao porte.**
- **Ajuste ao porte:** ativos_aj = ativos × (2.000 / m² oficial)^b_m2, com o b_m2 da própria v2 em ativos. Unidades sem
  metragem oficial ficam de fora, e o n é reportado.
- **Portão:** Manaus precisa estar no terço inferior da renda domiciliar. Se não estiver, o passo é inconclusivo.
- **Critério, nas praças de renda baixa:**
  - **"maior"** se ≥ 2 unidades tiverem ativos_aj ≥ 3.500;
  - **"teto"** se nenhuma tiver;
  - senão, **inconclusivo**.
- **Controle negativo:** a mesma regra no terço superior. Se ele também der "teto", o rótulo passa a ser **"teto geral
  da rede"**, isto é, 3.500 ajustado ao porte é raro em qualquer praça. Isso continua valendo contra "a unidade deveria
  passar de 3.500", mas não é efeito de renda.
- **Descritivo:** o balcão (`pagantes`), sem critério.
- **Sensibilidade:** o terço de renda pela renda per capita.

**Passo 2.**
- **Controle de renda:** a renda passa a ser a **domiciliar**, proxy da v2 (renda_pc × pop / domicílios da isócrona
  carro_10min em `atributos_v2`), junto com o log da população, franquia e idade.
- **Unidades com isócrona carro_10min truncada saem**, em todos os metrôs. O n de Manaus é reportado antes e depois.
- **Portão:** ≥ **5** unidades em Manaus depois do filtro.
- **Meses válidos:** ≥ 6 meses com valor (`count`) em 2025.
- **Identificação:** posto completo checado no ajuste e em cada reamostra; as reamostras descartadas são contadas.
- **Critério aplicado ao NÚMERO:** alt = v2 com master média × r(ii).
  - "maior" se média × lo_r > CENTRAL;
  - "menor" se média × hi_r < CENTRAL;
  - senão, neutro.
  - O alt é reportado em qualquer desfecho.
- **Leitura:** "Manaus" aqui são as Smart Fit dentro da caixa de ±12 km em volta do pino, não a cidade inteira.

**Passo 3.**
- **Sai da regra de síntese.** Só indica qual cenário de mix é mais plausível.
- **Novo mapeamento:** ≤ p25 → 30%; ≥ p75 → 55%; o resto → 43%, comparando com os quantis literais.

**Passo 5.** Os gatilhos são recentrados no número central:
- **para cima** se a projeção do mês 3 ≥ CENTRAL × 1,25;
- **para baixo** se ≤ CENTRAL × 0,81;
- o mês 1 é só alerta, porque a cobertura foi de 59%.

**Síntese (substitui o §8):**
- "sustenta número maior" se o Passo 2 der "maior" **ou** o Passo 1 der "maior".
- "sem evidência de 3.500 ajustado ao porte; central = X" se o Passo 1 der "teto" (ou "teto geral") **e** o Passo 2 não
  der "maior".
- "os dados apontam abaixo do central" se o Passo 2 der "menor" e o Passo 1 não der "maior".
- Qualquer outra combinação: mantém o central, com a faixa e o gatilho.

**§9, limites acrescentados:**
- A v2 em ativos tem R² LOO de 0,074, e o coeficiente de população é negativo (−0,113). A troca do círculo pela
  isócrona mexe no central em parte por esse sinal.
- Os R$ 421 mil do §2 usam 69% de balcão.
- O descritivo de balcão já tinha sido visto antes da v1.0; a v1.1 muda o teste para ativos ajustados ao porte, que não
  tinham sido olhados assim.
- A "renda domiciliar" é o proxy da v2 (per capita calibrada × moradores), não a domiciliar do relatório do produto
  (V06004 × uplift).

## 12. Emenda v1.2 (2026-09-30): Passo 2 formal da Smart Fit, escrito ANTES de rodar

**Declaração do que já foi visto antes desta emenda:**
- A checagem exploratória por UF: as 10 Smart Fit de Manaus têm mediana de ~3.850 em 2025, contra 2.717 no Brasil.
- A tabela do adendo pós-verificação.
- As coordenadas da listagem do TotalPass. A Cidade Nova fica a ~0,5 km do pino. A "Assaí Grande Circular" tem
  coordenada fora de Manaus (−2,23; −58,10). Amazonas Shopping e Jardim Amazonas não aparecem na listagem.
- A base de concorrentes não tem Smart Fit em Manaus e tem 28 pontos da rede local Live.

**Por que o Passo 2 da v1.1 deu zero:** o crosswalk da Smart Fit (`alunos_reais_por_unidade`) não tem nenhuma unidade do
AM. O coletor de concorrentes não cobre a Smart Fit de Manaus.

### 12.1 Crosswalk único para o país inteiro

A regra é a mesma em todos os metrôs, não só em Manaus.
- **Casamento:** cada unidade do painel `KPIs_Smart` (Nome do último mês) é casada com a Smart Fit da listagem
  `insumos_vps/planos_totalpass.parquet` por **nome normalizado + UF**.
  - Normalização: sem acento, minúsculas, sem o prefixo "smart fit", só letras e números.
  - Nome duplicado dentro da UF, de qualquer lado, fica de fora.
- **Coordenada válida:** a unidade precisa estar a no máximo 40 km da mediana das coordenadas de todos os parceiros do
  TotalPass da mesma `cidade`. Fora disso, é descartada e contada.

### 12.2 Geometria igual para todas as unidades

- **Círculo de 4,97 km** (área da isócrona de 10 min típica da rede) em volta de cada Smart Fit.
- **Atributos:** população, domicílios e renda per capita (calibrada, ponderada pela população) dos setores cujo ponto
  representativo cai no círculo. É o mesmo método de `04_atributos.atributos_poligono` para área acima de 40 km².
- **Renda domiciliar (proxy da v2):** renda_pc × pop / domicílios.

### 12.3 Amostra e desfecho

- **Desfecho:** log da mediana mensal de "Alunos Totais SF" em 2025, com ≥ 6 meses com valor.
- **Amostra:** unidades cuja primeira aparição no painel é ≤ 2024-12.
- **Idade (dummies), pela primeira aparição:**
  - "1º ano em 2025": de 2024-08 a 2024-12;
  - "2º ano": de 2023-08 a 2024-07;
  - referência: ≤ 2023-07, incluindo o que já estava no painel antes do início.
- **Franquia:** moda de `Propriedade`.

### 12.4 Grupos

- O metrô de cada unidade vem das caixas de `metros.json`, sem recuo. Manaus é a caixa 44, que contém todas as Smart
  Fit válidas da cidade.
- Unidade fora de toda caixa entra com efeito fixo pela UF (grupo "fora_UF"). Só ajuda a estimar os controles.
- **Pesos:** unidades Ultra de treino por metrô, como na v1.1.

### 12.5 Versões

- **(i-todas)** Sem controles e sem geometria. Manaus = todas as unidades do AM no painel, inclusive as duas que não
  casaram. Os outros metrôs usam as unidades casadas.
- **(i-casadas)** Sem controles, só unidades casadas.
- **(ii-casadas), a PRINCIPAL:** controles de log da renda domiciliar e log da população (círculo), franquia e idade.
  O que muda de (i-todas) para (i-casadas) mede o efeito de deixar de fora as duas unidades não casadas. Esse viés é
  declarado.
- **(ii-casadas, sem o 1º ano):** sensibilidade só com unidades já no painel até 2024-07.

### 12.6 Número e critério

- **Número:** alt = v2 da Ultra para Manaus com a **master média** (2.532, isócrona real; Passo 0) × r.
- **IC90:** bootstrap estratificado por grupo, com 2.000 repetições, checagem de posto e reamostras descartadas
  contadas.
- **Critério, na versão (ii-casadas):**
  - **"sustenta ≥ 3.000"** se o limite inferior do alt for ≥ 3.000;
  - **"sustenta acima do modelo"** se o limite inferior do alt for > 2.532 (r > 1 com 90%);
  - **"abaixo do modelo"** se o limite superior do alt for < 2.532;
  - senão, **"neutro"**.
- **Portão:** ≥ 5 unidades de Manaus em (ii-casadas).

### 12.7 Descritivos (sem critério)

- Série mensal da Smart Fit Cidade Nova (a ~0,5 km do pino).
- Pontos da rede Live e de outras redes na isócrona de 10 min do pino, pela base de concorrentes.
- Taxa de casamento nacional.

### 12.8 Limites

- A Smart Fit não tem metragem.
- O total inclui agregador (TotalPass, do mesmo grupo).
- O r mede a praça para **outra** marca, e a Ultra entraria disputando com essas unidades e com a Live.
- O círculo não é a isócrona.
- A amostra casada de Manaus perde as duas unidades de menor volume.

## 13. Emenda v1.3 (2026-09-30), depois da revisão adversarial do §12 e ANTES de rodar o 03

**O que já rodou:** só o índice de bbox dos setores (`scratchpad/indice_setores_bbox.parquet`), que é mecânico e não
produz resultado. Nenhum número do Passo 2 formal foi visto.

Cada item abaixo substitui o texto correspondente do §12.

### Bloqueadores corrigidos

1. **Manaus madura na versão principal.**
   - As 2 unidades do AM que não casam (Amazonas Shopping e Jardim Amazonas) são as únicas antigas de Manaus.
   - Nova versão **(ii-todas-imputada)**: elas entram no grupo 44 com log da renda domiciliar e log da população iguais
     à média das casadas de Manaus. O desvio-padrão dessas variáveis entre as casadas é impresso.
   - Também são impressos:
     - o n de Manaus por faixa de idade;
     - a diferença entre novas e antigas dentro de Manaus, ao lado dos coeficientes nacionais de idade.
2. **Nome e fechamento.**
   - O nome passa a ser o do **último mês de cada Sigla**, não o do último mês global.
   - Homônimos são checados sobre esse conjunto completo.
   - A série de 2023 a 2026-01 das 2 unidades antigas de Manaus é impressa.
   - **Trava:** o conjunto das unidades do AM que não casam tem de estar contido em {Amazonas Shopping, Jardim
     Amazonas}. Se não estiver, o script para, e a divergência vai para uma nova emenda.

### Correções

3. **Inclinações.**
   - Os coeficientes de renda e população da Smart Fit são impressos ao lado dos da v2.
   - Nova sensibilidade **(ii-offset)**: desfecho y − b_v2·(log renda domiciliar, log população), com efeito fixo +
     franquia + idade.
4. **Incerteza.**
   - Além do bootstrap, calcula-se um IC-t com 90% e gl = n_Manaus − 1 sobre o erro-padrão HC3 do contraste (EF_44 −
     referência ponderada). A alavancagem igual a 1 conta peso zero, e isso é declarado.
   - Vale o **IC mais largo**.
   - A faixa de 80% da v2 (master média) × r também é impressa.
5. **Veredito do Passo 2** (substitui o §12.6).
   - Categorias, aplicadas ao alt = 2.532 × r:
     - **A** = limite inferior ≥ 3.000 **e** ≥ o central M3 (2.958, calculado);
     - **B** = limite inferior > 2.532;
     - **C** = limite superior < 2.532;
     - **D** = neutro.
   - O veredito é o **menos favorável** entre (ii-casadas), (ii-todas-imputada) e as duas versões (ii-offset), na ordem
     C < D < B < A.
   - Na síntese do §11, o Passo 2 conta como **"maior" só em A** e como **"menor" só em C**.
   - Portão: ≥ 5 unidades de Manaus em (ii-casadas). Se não passar, o veredito é inconclusivo.
6. **(i-todas).**
   - **Todas** as unidades do AM vão para o grupo 44.
   - Trava: toda unidade válida do AM está na caixa 44.
   - A lista do AM é impressa por situação: não casada, coordenada inválida ou válida.
7. **Coordenada válida.**
   - A cidade da listagem é normalizada (sem acento, minúsculas).
   - Limite por cidade = o maior entre 40 km e o p95 da distância dos parceiros daquela cidade à mediana dela.
   - São impressos os descartes por grupo e quantas Smart Fit ficam em cidade com 1 parceiro só.
8. **Idade em faixas de meses até 2025-07, pela primeira aparição:**
   - ≤ 8;
   - 9–11;
   - 12–17;
   - 18–23;
   - referência: ≥ 24 ou já no painel antes do início.
9. **Pesos.** Os pesos vêm de `d.iso_metro`, como na v1.1. Divergências contra a regra da caixa são impressas.
10. **Pontos de setor inválidos.** Pontos sem coordenada finita saem. População NaN vira 0. Quedas por grupo são
    reportadas.
11. **Sensibilidade sem as unidades com menos de 12 meses:** marcada como "abaixo do portão" se Manaus tiver menos de
    5 unidades.
12. **Diagnóstico:** quantas das não casadas casariam com as palavras ordenadas.

### Limite acrescentado

- O EPSG:5880 distorce a área em até ~5% no Nordeste (~0,5% em Manaus). O efeito fixo por metrô absorve quase tudo.
