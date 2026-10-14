# Relatório BLK-UNI — Inteligência de Unidade

Gráficos do estudo para a apresentação executiva à diretoria. Cada gráfico tem três arquivos:
`graficos/<id>.png` (16:9, 12 × 6,75 pol., 200 dpi), `dados/<id>.csv` (os números plotados, `sep=";"`, `utf-8-sig`)
e `scripts/<id>.py` (reproduzível, com o estilo único de `scripts/_estilo.py`). Roteiro detalhado por seção em
`ROTEIRO.md`.

Para regenerar um gráfico, a partir da raiz do repositório (um script por vez):

```
PYTHONIOENCODING=utf-8 PYTHONPATH=src .venv/Scripts/python.exe data/analysis/uni/relatorio/scripts/<id>.py
```

Cada script confere o que plota contra a fonte e imprime `OK` ou `AVISO`. Na rodada de 30/09, os 27 scripts saíram
com zero avisos e nenhum CSV tem a coluna `aviso_divergencia`.

## A história em um parágrafo

A regra de viabilidade de hoje lê só a metragem: dá quase o mesmo faturamento a toda unidade e, nas 18 abertas em
2025, o real ficou, na mediana, 17% abaixo do previsto. Montamos uma base única da rede (98 unidades, 2.088 meses de
faturamento, ~240 características, 46 milhões de pontos de interesse) e testamos cada ideia com regra escrita antes e
conferência em unidades que o modelo nunca viu. Três coisas se confirmaram. A primeira é o **modelo da praça**
(metragem, renda e população a 10 min de carro): acerta o faturamento sem viés, ordena melhor e erra ~22%. A segunda
é a rampa real, bem mais rápida que a do simulador. A terceira é o alerta do 3º mês, que projeta os alunos maduros com
erro de 5–9%. No simulador de produção, o modelo da praça leva o erro de faturamento de 33% para 22% e o de payback de
20 para 14 meses, e empata com a regra atual na decisão de aprovar. Entorno, crescimento, concorrência, estado e
modelos mais complexos não melhoraram a previsão. O erro que sobra é quase todo volume de alunos, e nenhuma
característica das bases o explica. Das alavancas do operador, o estúdio é o sinal mais forte. Com a master
controlada, porém, ele já não se distingue de zero. Mesmo assim, estúdios e master entram na **v2 de trabalho**, que
ordena melhor com a mesma precisão e ainda não passou pelo simulador. A fachada segue em avaliação. O próximo ganho
depende de dado novo e da turma de 2026, já congelada. Nenhum "não" deste estudo é definitivo: o dicionário de
variáveis e os testes podem ser revisitados.

## Três nomes fixos para os modelos

| nome no deck | o que é |
|---|---|
| **regra atual** | a viabilidade de hoje: alunos pela densidade da metragem × receita por aluno |
| **modelo da praça** | metragem + renda + população da isócrona de 10 min (é a "v2" do UNI-05 e o M0 do UNI-02) |
| **v2 de trabalho** | modelo da praça + estúdios + master real (anonimizada M1–M7); decisão do dono |

## Gráficos, na ordem da apresentação

Status: **confirmado** = passou na régua escrita antes, em unidades que o modelo nunca viu; **exploratório** = achado
depois de ver o dado ou ainda sem conferência; **referência / descritivo / ilustração / em avaliação / preliminar**
conforme o selo do gráfico.

| # | arquivo | mensagem (título) | fonte principal | status |
|---|---|---|---|---|
| 1 | `s1_regra_achata.png` | A regra atual dá quase o mesmo número a toda unidade — e, na mediana, o real ficou 17% abaixo | `uni02/confirmacao_por_unidade.csv`, `uni02/resultado_uni02.md` | referência (o problema) |
| 2 | `s1_payback_prometido.png` | No payback, a regra atual promete demais às fracas e de menos às fortes | `uni05/comparacao_por_unidade.csv`, `uni05/resultado_uni05.md` | referência (o problema) |
| 3 | `s2_base_cobertura.png` | Uma base única: 98 unidades, 2.088 meses de faturamento e ~240 características por unidade | `COBERTURA_UNI00.md`, painéis, `docs/fontes_bases_poi.md`, `coleta_metragem/` | descritivo |
| 4 | `s2_metodo.png` | Cada ideia foi testada em dois tempos: achada em 2025, conferida em unidades que o modelo nunca viu | `CADERNO_ESTUDO_UNI.md`, protocolos e registros de congelamento | método |
| 5 | `s2_metragem_satelite.png` | A metragem por satélite é boa o bastante: erro típico de 20% (25% depois de corrigir o viés de +12%) | `coleta_metragem/qualidade_coleta_2026-09-29.md`, `uni07/resultado_uni07.md` | descritivo (N = 9 medições) |
| 6 | `s2_erros_dado.png` | No caminho, achamos erros de dado que já distorciam a tela de produção | `depara_divergencias.md`, `COBERTURA_UNI00.md`, relatório POI, PRs #418–#423 | descritivo |
| 7 | `s3_placar_modelo.png` | O modelo da praça se confirmou em unidades que nunca viu: sem viés e ordenando melhor | `uni02/resultado_uni02.md` | **confirmado** |
| 8 | `s3_previsto_real.png` | Com a praça, o erro fica equilibrado: 9 acima e 9 abaixo, contra 7 e 11 na regra atual | `uni02/confirmacao_por_unidade.csv` | **confirmado** (mesmo teste do #7) |
| 9 | `s3_curva_rampa.png` | A rampa real é bem mais rápida que a do simulador: 68% do nível maduro no 1º mês, contra 37% | `uni03/curva_uni03.csv`, `uni03/resultado_uni03.md` | exploração da curva (33 unidades) |
| 10 | `s3_rampa_confirmacao.png` | Em 22 unidades novas, a curva real erra metade do simulador nos alunos — e uma reta recalibrada já resolve | `uni03/resultado_uni03.md`, `uni03/ilustracao_payback_uni03.md` | **confirmado** (painel direito: ilustração) |
| 11 | `s3_alerta_mes3.png` | No 3º mês, a projeção dos alunos maduros erra 5–9%, contra ~22% antes de abrir | `uni03/resultado_uni03.md` (P3) | **confirmado** |
| 12 | `s4_placar_hipoteses.png` | Além do modelo da praça, nenhuma variável de território se confirmou | `uni01`, `uni02`, `uni02r`, `uni03`, `uni04`, relatório POI, alavancas | placar (vereditos por linha) |
| 13 | `s4_poi_nulo.png` | Empresas, shoppings e estações no entorno não melhoram a previsão — nem na Ultra, nem em 454 Smart Fit | `poi/saidas/resultado_teste_poi.*`, `poi/relatorio_teste_poi_2026-09-25.md` | teste pré-registrado (nulo); IC 95% |
| 14 | `s4_erro_e_volume.png` | O que o modelo erra é volume de alunos — e nenhuma das 22 características explica o erro de faturamento de forma confiável | `uni01/anatomia_erros.*` | exploratório |
| 15 | `s4_renda_churn.png` | Praça mais rica cancela menos na rede madura, mas o efeito não apareceu nas unidades novas | `uni04/resultado_uni04a.md` (+ pós-hoc marcado) | teste que decide: inconclusivo |
| 16 | `s4_diretor_replica.png` | A hipótese do diretor aparece com o mesmo tamanho em outra rede — evidência a favor, ainda sem prova | `uni02r/resultado_uni02r.md`, `uni02/resultado_uni02.md` | exploratório |
| 17 | `s5_alavancas_forest.png` | Das alavancas, só o estúdio tem efeito medido no faturamento — e, com a master controlada, ele já não se distingue de zero | `alavancas/resultado_alavancas.md`, `alavancas_corte.csv`, `resultado_estudios_master_real.md` | exploratório |
| 18 | `s5_agregador.png` | O agregador troca ticket por volume com saldo pequeno; a premissa de 60% fica | `uni01/resultado_uni01.md`, `alavancas/resultado_alavancas.md` | exploratório (premissa: decisão do dono) |
| 19 | `s5_estudio_separa.png` | Nas unidades novas, as com estúdio faturaram acima do previsto (+54%) e as sem estúdio, abaixo (−21%) | `uni02/confirmacao_por_unidade.csv`, `dim_unidade.parquet` | exploratório |
| 20 | `s5_botafogo.png` | Botafogo: as alavancas declaradas explicam parte do caso — o resto é volume excepcional | `alavancas/resultado_quanto_melhora.md` §3, `uni05/comparacao_por_unidade.csv` | ilustração (cenário mais favorável) |
| 21 | `s5_fachada.png` | Fachada: sinal a favor que enfraqueceu com o primeiro avaliador independente — ainda em avaliação | `alavancas/resultado_fachada_*.md`, `resultado_v2_fachada.md` | em avaliação |
| 22 | `s5_mix_estado.png` | A fatia de agregador se separa por estado — SP ~56%, DF/GO ~32% — mas não muda faturamento nem payback | `mix/resultado_universo_cv.md`, `mix/universo_cv.csv` | exploratório |
| 23 | `s6_escada.png` | O ganho está na demanda da praça; estúdios + master ordenam melhor com a mesma precisão | `alavancas/resultado_quanto_melhora.md`, `resultado_estudios_master_real.md`, `uni02`, `uni07` | exploratório (modelo da praça: **confirmado**; regra atual: referência) |
| 24 | `s6_viabilidade.png` | No simulador, o modelo da praça prevê melhor faturamento e payback — e empata na decisão de aprovar | `uni05/resultado_uni05.md` (v1.1), `uni05/comparacao_por_unidade.csv` | teste do simulador (modelo da praça, não a v2 de trabalho) |
| 25 | `s7_faixas_seguranca.png` | A v2 passa a entregar faixa: de −37% a +58% em torno da previsão, que cobriu 13 das 18 unidades novas | `uni07/faixas_indicadores.csv`, `uni07/resultado_uni07.md` | verificado (UNI-07 concluído e verificado; faixa adotada provisoriamente) |
| 26 | `s7_turma_2026.png` | A turma de 2026 é a prova que falta: previsões congeladas antes do resultado, com primeiras leituras para os dois lados | `previsao_2026/` (previsões congeladas, leitura precoce) | descritivo |
| 27 | `s7_roadmap.png` | O próximo ganho de precisão vem de dado novo, não de mais uma variável geográfica | `CADERNO_ESTUDO_UNI.md`, `previsao_2026/protocolo_previsao_2026.md` | próximos passos |

## O que mudou na revisão de 30/09

- **Número errado:** `s2_base_cobertura` dizia "erro típico de 20%" depois da correção; passou a "20–25%" (20% antes,
  25% depois de dividir por 1,12). Rótulos de jargão da cobertura viraram termos de negócio.
- **Nomes dos modelos:** `s6_viabilidade` passou a "modelo da praça (v2 do UNI-05)", com nota de que a v2 de trabalho
  não foi rodada no simulador. Em `s6_escada`, a regra atual ganhou o chip neutro REFERÊNCIA e só o modelo da praça
  ficou CONFIRMADO. Os dois gráficos explicam por que a regra atual erra 27% num e 33% no outro.
- **Mensagens corrigidas:**
  - `s3_previsto_real`: erro equilibrado 9/9 × 7/11 e "amplitude das previsões".
  - `s4_erro_e_volume`: erro de faturamento; os 3 de 22 no erro de alunos (Gold ρ +0,47, p = 0,003).
  - `s4_placar_hipoteses`: "estado ou escritórios" vai para o chip cinza NÃO MELHORA; o diretor "passou por 2 pontos
    nas novas".
  - `s5_estudio_separa`: a legenda do anel M2 saiu da área de dados e ganhou cor neutra.
  - `s5_botafogo`: as duas suposições aparecem sob os degraus; "nessa conta, passaria o corte".
  - `s5_fachada`: as 5 barras ficaram iguais, sem a seta da "escada"; ampliada +0,32 [−0,09; +0,66]; "N a registrar".
  - `s2_metragem_satelite`: título com 20%/25%; caixa com N = 3 contra 54; rótulos sem fundo; Cotia A/B separados.
  - `s5_alavancas_forest`: o IC com a master "cruza zero: não distingue"; título novo e selo EXPLORATÓRIO.
  - `s2_metodo`: a revisão prévia vale para UNI-01, UNI-03, UNI-04, alavancas e UNI-07 (7, 11, 10, 12 e 11); o UNI-02
    ficou sem revisão prévia registrada.
- **Clareza:**
  - `s1_regra_achata`: "na mediana" no título.
  - `s3_curva_rampa`: os 37% explicados pelo tempo de operação (k + 0,53); "nível mediano".
  - `s3_rampa_confirmacao`: as barras da direita são as retas 62%→100% (mês 8) e 64%→100% (mês 11).
  - `s3_alerta_mes3`: o erro típico (sem sinal) e a faixa p10–p90 (com sinal) ficaram em eixos separados.
  - `s4_diretor_replica`: eixo em linguagem de negócio.
  - `s2_erros_dado`: coluna STATUS com os PRs.
  - `s7_turma_2026`: faixa do modelo da praça × faixa da v2; Guarapari e Laranjeiras citadas.
  - `s7_faixas_seguranca`: "esperado 80%; adotada provisoriamente"; Paranoá com asterisco.
  - `s5_mix_estado`: "RJ: mediana 0%" com Cabo Frio; legenda escuro/claro.
- **Estilo:** EM ANDAMENTO passou a âmbar de contorno em `s7_roadmap`. O nível do IC está declarado nos subtítulos
  dos forest plots, e o POI destaca "IC 95% (os demais usam 90%)".
- `ROTEIRO.md`: nova frase de privacidade (nenhum dado `LOCAL_*` em gráfico ou CSV; o UNI-01 o lê como coluna
  auxiliar), glossário dos três nomes e títulos atualizados.

## Notas de conciliação (números que aparecem diferentes entre slides)

- **Erro típico do modelo:** 21,5% (modelo da praça nas 18 novas, alavancas), 22% (UNI-02 e UNI-07, juntos), 23% (v2
  no treino, UNI-07) e 25% (`anatomia_erros.md`; a mediana de |erro| no CSV dá 22,15%). No discurso, usar "~22%".
- **Erro da regra atual:** 27% = regra de metragem com a receita por aluno observada (UNI-02); 33% = cálculo exato do
  simulador (R$ 115 por aluno, UNI-05).
- **Faixas p10–p90:**
  - −37% a +58%: v2 de trabalho, UNI-07 (`s7_faixas`).
  - −35% a +67%: modelo da praça na turma de 2026 (`s7_turma`).
  - −35% a +54%: caderno, etapa 9.
- **Agregador no faturamento:** +6% pela conta, ≈ −5% com a maturidade ajustada e +10,2% no evento TotalPass. O +18% é
  de alunos, não de faturamento.
- **Previsões da regra atual:** R$ 183–295 mil (UNI-02, `s1`). O caderno e o UNI-05 trazem outras faixas (203–326 e
  199–319 mil). Na apresentação, usar o número do gráfico.
- **Paranoá Parque:** 34 meses de payback sem o custo do estúdio (`s1`, `s6`: "se pagou") e 37 com ele (`s7_faixas`:
  "não viável").

## Pendências

1. **Slide de abertura e slide de proposta/decisão.** Faltam dois slides:
   - Abertura: resumo com os 3–4 números que importam (viés −17% → +1%; payback 20 → 14 meses; mês 3 com erro de
     5–9%; faixa de −37% a +58%).
   - Proposta e decisão pedida, antes do roadmap: o que se propõe mudar já (modelo da praça ou v2 como base, rampa
     62%→100% no mês 8, faixa, alerta do mês 3 e revisão da receita por aluno do simulador).
2. **Exemplo concreto de ponto novo**, com p10/p50/p90, payback e chance de ser viável (unidade típica ou simulação de
   Manaus). Hoje a unidade típica aparece só na nota do `s7_faixas`.
3. **Rodar a v2 de trabalho no simulador contra a regra atual.** Sem isso, o ganho de 33% → 22% e 20 → 14 meses vale
   só para o modelo da praça.
4. **Enxugar para o executivo:**
   - candidatos a anexo: `s2_base_cobertura`, `s2_metragem_satelite`, `s4_poi_nulo`, `s4_diretor_replica` e
     `s5_mix_estado`;
   - fundir `s3_curva_rampa` com `s3_rampa_confirmacao`;
   - antecipar `s6_viabilidade` para logo depois de `s3_placar_modelo`.
5. **Títulos de 1 e 2 linhas não foram padronizados.** Os gráficos com título longo seguem em 2 linhas, e a área do
   gráfico começa em alturas diferentes.
6. **POI segue em IC 95%.** O intervalo vem do bootstrap já publicado e não foi recalculado em 90%; o gráfico avisa a
   diferença.
7. **Conferir antes de apresentar:**
   - as correções de dado estão na `main` (PRs #418, #419, #421, #422 e #423, de 28/09), mas falta conferir se já
     estão no ar (BLK-DADOS-UNI-01);
   - o `s2_erros_dado` e o `s7_roadmap` dizem "produção a conferir".
8. **Dados que faltam registrar ou fechar:**
   - o N da amostra "só lojas de rua" (`s5_fachada`);
   - o veredito da fachada, que depende das notas restantes do avaliador independente (11 de 45);
   - o UNI-07 em andamento: `s7_faixas_seguranca` lê `uni07/faixas_indicadores.csv` e se regenera quando fechar, e há
     2 decisões do dono pendentes (faixa por estado; chance como ranking).
9. **Divergência a esclarecer:** `anatomia_erros.md` publica "erro típico 25%", mas a mediana de |erro_pct| no CSV dá
   22,15%. A definição usada no .md não está registrada.
