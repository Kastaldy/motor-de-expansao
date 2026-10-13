# Termômetro de praça pela Smart Fit — o volume das Smart Fit vizinhas melhora a previsão das unidades Ultra?

Versão 1.0, 2026-09-30. Protocolo escrito **antes de rodar**. Só análise.

## 1. Pergunta e origem

**Origem:** no caso de Manaus, a única variável que mexeu na estimativa foi o volume de alunos da Smart Fit na mesma
praça (`manaus_volume/resultado_smartfit_formal.md`).

**Pergunta:** o volume das Smart Fit **vizinhas** de cada unidade Ultra, tomado como demanda revelada do concorrente
low-cost direto, **reduz o erro fora da amostra** da v2 adotada?

## 2. Dados

**Smart Fit**
- Painel `data/validacao/KPIs_Smart_*.xlsx`, aba Base.
- Por unidade: **mediana mensal de "Alunos Totais SF" em 2025**, com ≥ 6 meses com valor.
- Amostra principal: unidades **maduras**, no painel até **2024-07**. Evita o pico de abertura visto em Manaus.
- Sensibilidade: no painel até 2024-12.

**Coordenadas da Smart Fit**
- Base de concorrentes **atual da VPS** (27/09/2026, `insumos_vps/concorrentes_mapeados_2026-09-27.parquet`),
  `rede == smart_fit`, `status_registro == valido`.
- A cópia local de 10/09 tinha o teto antigo de 1.000 unidades do coletor e não é usada.
- **Casamento:**
  - nome normalizado (sem acento, minúsculas, sem "smart fit", só letras e números);
  - o nome do painel é o do último mês de cada Sigla;
  - nome duplicado em qualquer dos lados fica de fora;
  - a taxa de casamento é reportada.

**Ultra**
- Treino: as mesmas 39 unidades maduras de 2025 da v2, com os mesmos atributos (`manaus_volume/02_evidencias.base_treino`).
- Teste: as 18 do UNI-02 (2026), com a metragem do UNI-02 e a calibração de calendário. É a mesma construção de
  `simulacoes/manaus_diagnostico.py`.

## 3. Variável

**T5 (principal):** média do log dos alunos das Smart Fit maduras a **até 5 km** (haversine) da unidade Ultra. O raio
equivale à área da isócrona típica de 10 min. Unidade sem Smart Fit madura a até 5 km fica sem termômetro.

**Sensibilidades:**
- **T10:** o mesmo, até 10 km;
- **T3:** média do log das **3 mais próximas** a até 15 km;
- **T5 incluindo as abertas até 2024-12.**

## 4. Comparação justa

A v2 e a v2 + T são ajustadas **nas mesmas unidades**: as que têm termômetro. Reportam-se a cobertura (quantas das 39 e
das 18 têm T) e o desempenho da v2 nas unidades sem termômetro.

## 5. Desfechos e métricas

- **Desfecho principal:** log do faturamento (a v2 adotada). **Secundário:** log dos ativos.
- **Treino:**
  - erro típico LOO (mediana de |exp(e_LOO) − 1|);
  - R² LOO;
  - coeficiente de T com IC 90% (HC3).
- **Teste (18, fora do tempo):** erro típico, viés e Spearman, com v2 e v2 + T ajustados nas unidades de treino com T.
- **Estreitamento da faixa:** a largura da faixa de 80% (quantis dos resíduos LOO) com v2 + T sobre a largura com v2.

## 6. Critério (fixado antes)

**"Melhora a precisão"** exige as três condições, na versão principal (T5, faturamento):
1. coeficiente de T > 0, com IC 90% excluindo zero;
2. erro típico LOO cai **≥ 2 pp**;
3. erro típico no teste **cai**.

**Outras leituras:**
- **"Candidata"**, se só a condição 1 valer, ou se valerem 1 e mais uma;
- **"Não melhora"**, nos demais casos.

As sensibilidades e o desfecho em ativos são reportados, mas não mudam o veredito.

## 7. Aplicação a Manaus (descritiva, sem critério)

- T5 do pino e previsão da v2 + T (master M3 e master média) em faturamento e em ativos.
- Com a base nova, o casamento das Smart Fit de Manaus é refeito. A diferença para o teste formal de Manaus
  (crosswalk pelo TotalPass) é reportada.

## 8. Limites

- **N pequeno:** 39 de treino e 18 de teste. O ganho em LOO pode ser ruído.
- **Cobertura desigual:** a Smart Fit está nas cidades maiores, então T falta em cidades menores. A comparação justa do
  §4 não resolve a generalização para essas cidades.
- **Dupla leitura do sinal:** a Smart Fit ao lado de uma Ultra compete com ela. Volume alto pode ser demanda (sinal +)
  ou disputa (sinal −). O teste mede o efeito líquido.
- **O que o total da Smart Fit inclui e não inclui:** o total inclui agregador (TotalPass, do mesmo grupo); a Smart
  Fit não tem metragem.
- **Timing:** o termômetro é contemporâneo ao desfecho (2025). Numa praça nova, usa-se o dado corrente da Smart Fit,
  disponível na decisão.

## 9. Arquivos

`termometro/01_termometro.py` → `resultado_termometro.md`. Congelamento em `REGISTRO_CONGELAMENTO.txt`.

## 10. Emenda v1.1 (2026-09-30), depois da revisão adversarial e ANTES de rodar

Cada item substitui o texto correspondente acima.

**1. Casamento por nome + UF**
- Chave: nome normalizado + UF.
  - No painel, a UF vem de `Sigla[3:5]`. Trava: todo o painel tem prefixo `SBR`.
  - Na base da VPS, a UF vem do `hex_id_res7`, pelas partições `data/staging/brasil/uf=XX/hexagonos.parquet`.
- Duplicata é avaliada dentro de nome + UF.
- **Trava contra o crosswalk do TotalPass:** nas Siglas casadas pelos dois, se mais de 2% ficarem a mais de 1 km de
  distância, o script para.
- A taxa de casamento é reportada sobre o painel e sobre as unidades com desfecho.

**2. Sem dado posterior à decisão, e termômetro relativo**
- **Nível de cada Smart Fit:** mediana dos alunos nos meses da janela em que a unidade tem **≥ 12 meses de idade**
  (idade contada da primeira aparição no painel; a que já estava lá no início conta como antiga), com ≥ 6 meses.
  Substitui o corte "no painel até 2024-07".
- **Termômetro relativo:** log do nível local menos log da mediana nacional da Smart Fit na **mesma janela**.
- **Janelas:**
  - **Treino:** 2025. É contemporâneo ao desfecho, e isso fica declarado.
  - **Teste (as 18):** os 12 meses **antes da inauguração** da unidade Ultra. Inauguração com placeholder fica sem
    termômetro.

**3. Modelo principal: um só nas 39, com indicador de ausência**
- Sem T, preenche-se com a média do treino, e entra a dummy `sem_T`.
- Compara-se com a **v2 nas 39**, em LOO nas 39 e no teste nas 18. É a decisão real: v2 + T onde houver, v2 onde não
  houver.
- A comparação só no subconjunto com T vira descritiva. Nela, master com menos de 3 unidades vai para `mr_outras`.
- Trava: nenhuma alavancagem igual a 1.
- Reportam-se o desempenho da v2 nas unidades sem T, no LOO e no teste, e quantas unidades têm coordenada de baixa
  confiança.
- **Reprodução:** a v2 nas 39 tem de dar R² LOO de 0,264 ± 0,005 e erro no teste de 22,1% ± 0,3 pp. Senão, o script
  para.

**4. Critério (substitui o §6)**
- **c1:** coeficiente de T > 0, com IC 90% t (gl = n − p) excluindo zero.
- **c2:** erro típico LOO cai ≥ 2 pp. Reporta-se também o IC 90% bootstrap pareado da diferença.
- **c3:** erro típico no teste cai **≥ 2 pp**. Reporta-se também quantas das 18 têm |erro| menor.
- **"Melhora a precisão"** = c1, c2 e c3.
- **"Candidata"** = c1, com o erro LOO sem piorar.
- **"Não melhora"** = os demais casos.
- Um coeficiente negativo significativo ("disputa") é reportado à parte.

**5. Relatado sem critério**
- Erro por **leave-one-metro-out** (`iso_metro`) dos dois modelos.
- A largura da faixa de 80%, calculada como exp(q90) − exp(q10), dos dois modelos.

**6. Sensibilidades (descritivas, sem IC para escolher)**
- T10 e T3;
- **T5_pre**, só com Smart Fit anteriores à Ultra. A antiga conta como anterior só se a Ultra abriu depois de 2023-01;
- controle log(1 + nº de Smart Fit da base a até 5 km);
- **cobertura:** unidade Ultra com menos de 50% das Smart Fit da base a até 5 km casadas fica sem T;
- desfecho em ativos.

**7. Manaus**
- O número principal é só o T5 (janela 2025).
- São reportados:
  - o percentil de Manaus no treino, com aviso de extrapolação se passar do máximo;
  - a versão sem a leva de 2024;
  - o nível de 2025 e o de 2026 (calibrado).

**8. As 18 de teste já foram consultadas antes** (UNI-02, UNI-07 e a troca para renda domiciliar), então não são teste
virgem. Por isso, **congelam-se agora** as previsões da v2 + T da turma de 2026 (`previsao_2026`, 16 unidades, com T
de antes da abertura), com SHA-256, como teste limpo futuro.

**9. Congelamento:** SHA-256 do protocolo, do script, do xlsx do painel e do parquet da VPS em
`REGISTRO_CONGELAMENTO.txt`, antes de rodar. Trava: existe um só arquivo `KPIs_Smart_*.xlsx`.
- **Detalhe de implementação (antes de rodar):** a dummy `sem_T` só entra se ≥ 3 unidades de treino não tiverem T. Com menos, elas ficam com T = média, sem dummy, para evitar alavancagem igual a 1.
