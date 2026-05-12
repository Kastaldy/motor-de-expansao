# Experimento Setor Censitario 2010 - Consolidacao Metodologica

> Relatorio consolidado pos-validacao multicidade (GO + SP + Campinas + RJ).
> Data: 2026-04-06 | Responsavel: Felipe Silva | Ambiente: experimento paralelo isolado
> Nao substitui artefatos oficiais do M1. Pipeline oficial preservado.

---

## 1. Status geral

| item | status |
| --- | --- |
| experimento paralelo ativo | sim |
| pipeline oficial M1 alterado | nao |
| artefatos M1 alterados | nao |
| bloqueadores criticos resolvidos | parcialmente (ver secao 5) |
| recomendacao de promocao ao M1 | NAO PROMOVER AINDA |
| proxima etapa recomendada | piloto controlado com fonte de renda canonizada |

---

## 2. Resultados por cidade (resumo consolidado)

| cidade | uf | cod_ibge | hex_total | hex_com_setor | cobertura_pct | score_mun_distintos | score_setor_distintos | score_setor_std | amplitude_p95_p05 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Goiania | GO | 5208707 | 128 | 128 | 100.00% | 1 | 80 | 19.31 | 71.47 |
| Sao Paulo | SP | 3550308 | 293 | 293 | 100.00% | 1 | 246 | 22.81 | 69.06 |
| Campinas | SP | 3509502 | 149 | 149 | 100.00% | 1 | 92 | 17.17 | 54.61 |
| Rio de Janeiro | RJ | 3304557 | 185 | 185 | 100.00% | 1 | 146 | 22.89 | 74.31 |
| **Total** | | | **755** | **755** | **100.00%** | — | — | — | — |

Notas:
- Cobertura espacial de 100% em todas as cidades (hex urbanos).
- Modelo municipal atual: score quase uniforme em todas as cidades (std=0.0 em GO e RJ; std=0.06 em SP/Campinas).
- Modelo censitario 2010: diferenciacao intraurbana expressiva e consistente em todas as cidades.

---

## 3. Impacto de negocio - mudancas de ranking intraurbano

### 3.1 Goiania/GO

**Modelo municipal (M1 atual):** todos os 128 hexagonos com score=99.77 — sem diferenciacao intraurbana possivel.

**Modelo censitario 2010:** scores entre 5.67 e 96.85, amplitude p95-p05=71.47.

Interpretacao executiva:
- O modelo atual indica que toda Goiania e igualmente prioritaria (score ~100).
- O modelo censitario separa bairros nobres (Setor Bueno, Jardim Goias) com scores acima de 90 de periferias com scores abaixo de 20.
- Diferenca de prioridade entre topo e base: ~91 pontos.
- Implicacao: sem setor censitario, qualquer ponto em Goiania parece equivalente para expansao.

### 3.2 Sao Paulo/SP

**Modelo municipal (M1 atual):** score ~99.89 uniforme (std=0.06), praticamente sem diferenciacao.

**Modelo censitario 2010:** Sao Paulo com 246 valores distintos, amplitude p95-p05=69.06.

Interpretacao executiva:
- O top do ranking censitario em SP (score >90) corresponde a regioes como Itaim Bibi, Vila Olimpia, Moema — bairros classicos de alta renda com perfil Ultra.
- Hexagonos em regioes perifericas caem para scores abaixo de 10.
- Diferenca entre top-1 e mediana: ~41 pontos.

### 3.3 Campinas/SP

**Modelo municipal (M1 atual):** score ~99.76 uniforme.

**Modelo censitario 2010:** 92 valores distintos, amplitude p95-p05=54.61.

Interpretacao executiva:
- Menor amplitude que SP e RJ, o que e esperado dada a menor heterogeneidade intraurbana de Campinas.
- Ainda assim, top-1 censitario (98.41) vs. base (0.91) representa diferenca operacional significativa.

### 3.4 Rio de Janeiro/RJ

**Modelo municipal (M1 atual):** score=99.81 uniforme (std=0.0) para todos os 189 hexagonos.

**Modelo censitario 2010:** amplitude p95-p05=74.31 — o maior ganho de diferenciacao dos 4 estados testados.

Interpretacao executiva:
- RJ tem das maiores desigualdades intraurbanas do Brasil: Zona Sul vs. Baixada vs. Zona Norte.
- O modelo censitario captura isso com amplitude de 74 pontos.
- Hexagonos no top-10 censitario (scores 85-98) correspondem a Zona Sul/Barra.
- Hexagonos com score <10 correspondem a areas de baixa renda.

### 3.5 Sintese executiva de impacto

O modelo municipal atual coloca TODOS os hexagonos de TODAS as cidades no mesmo patamar de prioridade (~100).
O modelo censitario produz uma hierarquia intraurbana clara e plausivel em 100% das cidades testadas.

Para uma decisao de expansao intraurbana (escolher entre dois pontos na mesma cidade), o modelo atual e inutil.
O modelo censitario 2010 e operacionalmente util mesmo com os bloqueadores atuais.

---

## 4. Metodologia adotada - decisoes registradas

### 4.1 Variavel de renda

**Variavel atual:** Basico V005 = "Valor do rendimento nominal medio mensal das pessoas responsaveis por domicilios particulares permanentes"

**O que V005 mede:** media do rendimento do chefe de domicilio por setor censitario.

**O que V005 NAO mede:** renda per capita domiciliar (total de rendimentos / numero de moradores).

**Por que ainda e um proxy util:**
- Correlacao alta com renda do entorno: setores com chefes de alta renda tendem a ter domicilios de alta renda.
- Disponivel em todos os setores com domicilios particulares permanentes.
- Semanticamente proxima ao perfil-alvo da Ultra (renda domiciliar >= R$ 4.500/mes).

**Proxy melhorado disponivel (implementado):**
`renda_per_capita_setor_2010 = V005 / V002 (pop_total_setor_2010)`
Disponivel quando ambos os campos estao presentes no arquivo Basico do setor.
Vantagem: mais rigoroso conceptualmente. Desvantagem: divide a renda do chefe pela populacao total, o que pode subestimar setores com muitos dependentes.

**Decisao para producao:**
Definir fonte canonica. Opcoes em ordem de preferencia:
1. Censo 2022 por setor (quando disponibilizado pelo IBGE com renda domiciliar per capita)
2. V005/V002 como proxy derivado (disponivel agora, documentado como proxy)
3. V005 direto com limitacao documentada (estado atual)

### 4.2 Calculo de percentis e comparabilidade nacional

**Problema:** `_calcular_percentil_nacional()` aplicada ao subconjunto local produz percentis relativos a esse subconjunto, nao ao universo nacional. Um setor no p75 de Goiania pode ser p50 nacional.

**Solucoes avaliadas:**

| abordagem | descricao | vantagem | limitacao |
| --- | --- | --- | --- |
| percentil local (atual) | rank dentro da cidade testada | simples, mensura separacao intraurbana | nao comparavel entre cidades |
| score ancorado (implementado) | 60% * hex_score_estrutural + 40% * hex_score_setor_local | comparavel entre cidades, preserva posicao nacional | usa combinacao linear, nao recalcula percentil real |
| percentil nacional simulado | rank do setor dentro da distribuicao nacional do M1 | totalmente comparavel | mistura escalas: renda de setor vs renda municipal media |

**Decisao adotada (implementada):** `score_setor_ancorado = 0.60 * hex_score_estrutural + 0.40 * hex_score_setor_2010`

Racional:
- `hex_score_estrutural` ja foi calculado com percentis nacionais no M1 — preserva posicao do municipio no ranking nacional.
- `hex_score_setor_2010` adiciona diferenciacao intraurbana via percentil local.
- Pesos 60/40 replicam a proporcao renda/populacao do M1 para consistencia metodologica.
- Score resultante e comparavel entre cidades diferentes.
- Nao substitui `score_priorizacao` oficial.

**Funcao de ancoragem nacional futura (implementada no script):**
`_percentil_em_distribuicao_referencia(serie, referencia)` permite calcular percentil de setores contra distribuicao nacional do M1 sem reprocessar toda a base. Disponivel para uso futuro quando for necessario comparabilidade rigorosa por percentil.

### 4.3 Bug reset_index

Bug identificado em execucao anterior (indice incorreto apos merge) ja esta corrigido no script atual. A linha `reset_index(drop=True)` esta presente em todos os pontos criticos do pipeline.

---

## 5. Bloqueadores - status atualizado

| # | bloqueador | status | acao tomada |
| --- | --- | --- | --- |
| 1 | Fonte de renda (V005 != renda per capita) | **PARCIALMENTE RESOLVIDO** | proxy `renda_per_capita_setor_2010 = V005/pop_total` implementado; fonte canonica para producao ainda nao definida |
| 2 | Percentis locais incompativeis com ranking nacional | **MITIGADO** | `score_setor_ancorado` implementado (60% mun + 40% setor); `_percentil_em_distribuicao_referencia()` disponivel para ancoragem futura |
| 3 | Custo computacional nacional nao avaliado | **ESTIMADO** | estimativa analitica: ~215k hex nacionais, throughput medido no experimento projetado para escala nacional (ver secao 6) |
| 4 | Bug de indice (reset_index) | **CORRIGIDO** | ja corrigido no script atual |

Bloqueador remanescente critico antes de qualquer promocao ao M1:
- **Fonte canonica de renda por setor**: V005/pop_total e um proxy funcional mas nao e a fonte ideal. Para producao, idealmente usar renda domiciliar per capita por setor (Censo 2022 ou tabela especifica do Censo 2010).

---

## 6. Custo computacional - estimativa

### Base de calculo
- Spatial join testado: ~762 hexagonos (GO + SP + Campinas + RJ combinados nos experimentos).
- Estrutura do spatial join: STRtree + centroide within + fallback intersects maior area.

### Projecao nacional
- Hexagonos H3 res-7 estimados no Brasil com populacao: ~215.000.
- Fator de escala: ~282x o tamanho dos experimentos realizados.
- Estimativa de tempo sequencial: **30-90 minutos por execucao nacional** (depende da densidade de setores por UF).
- Picos: UFs com maior densidade de setores (SP, MG, RJ) serao mais lentas.

### Otimizacoes recomendadas antes de producao nacional
1. **Paralelismo por UF:** processar cada UF de forma independente (trivialmente paralelizavel).
2. **Cache de STRtree:** construir a arvore de setores uma vez por UF, reutilizar para multiplos hexagonos.
3. **Filtragem previa por bounding box:** reduzir candidatos antes do spatial join fino.
4. **Execucao incremental:** rodar UF por UF e salvar Parquet intermediario.

Com paralelismo por UF (27 UFs independentes), o tempo efetivo pode cair para **2-5 minutos** em maquina com 8+ cores.

---

## 7. Score ancorado - exemplo de uso

O `score_setor_ancorado` resolve o problema de comparabilidade:

Exemplo hipotetico com dados das cidades testadas:
- Hex A (Goiania, bairro nobre): hex_score_estrutural=99.77, hex_score_setor_2010=96.85 → score_setor_ancorado = 0.6*99.77 + 0.4*96.85 = **98.60**
- Hex B (Goiania, periferia): hex_score_estrutural=99.77, hex_score_setor_2010=5.67 → score_setor_ancorado = 0.6*99.77 + 0.4*5.67 = **62.13**
- Hex C (Rio de Janeiro, Zona Sul): hex_score_estrutural=99.81, hex_score_setor_2010=98.80 → score_setor_ancorado = 0.6*99.81 + 0.4*98.80 = **99.41**
- Hex D (Rio de Janeiro, periferia): hex_score_estrutural=99.81, hex_score_setor_2010=2.39 → score_setor_ancorado = 0.6*99.81 + 0.4*2.39 = **60.84**

Resultado: hexagonos de diferentes cidades sao agora comparaveis entre si. Goiania-nobre (98.60) vs. RJ-Zona-Sul (99.41) e uma comparacao valida. A hierarquia intraurbana e preservada dentro de cada cidade.

---

## 8. Limitacoes remanescentes

1. **Defasagem temporal:** Censo 2010 (~15 anos de defasagem). Transformacoes urbanas desde 2010 nao sao capturadas.
2. **Fonte de renda nao canonizada:** V005 e proxy, nao renda per capita ideal.
3. **Percentis intraurbanos:** `hex_score_setor_2010` usa percentil local; `score_setor_ancorado` mitiga mas nao elimina a limitacao.
4. **Cobertura rural:** setores rurais podem ter geometrias problematicas; experimento focou em areas urbanas.
5. **Sem fonte de populacao 18-45 por setor 2010:** pop_target nao foi encontrada nos arquivos Basico testados; usa pop_total como fallback.
6. **Custo nacional nao medido empiricamente:** apenas estimado a partir de amostras pequenas.

---

## 9. Artefatos gerados por este experimento

```
data/staging/teste_setor_2010/
  hexagonos_teste_setor_2010.parquet        <- hexagonos GO com score setor e ancorado
  comparativo_municipal_vs_setor_2010.parquet <- comparativo GO
  go/                                        <- subpasta GO
  sp/
    hexagonos_teste_setor_2010.parquet       <- hexagonos SP+Campinas
    comparativo_municipal_vs_setor_2010.parquet
  rj/
    hexagonos_teste_setor_2010.parquet       <- hexagonos RJ
    comparativo_municipal_vs_setor_2010.parquet

data/outputs/teste_setor_2010/
  top_hexagonos_setor_2010.csv              <- top 20 por cidade, modelo censitario (GO)
  top_comparativo_por_cidade.csv
  sp/top_hexagonos_setor_2010.csv           <- top SP+Campinas
  rj/top_hexagonos_setor_2010.csv           <- top RJ

data/reports/
  teste_setor_2010.md                       <- este relatorio consolidado (GO)
  teste_setor_2010_sp.md                    <- relatorio SP+Campinas
  teste_setor_2010_rj.md                    <- relatorio RJ
```

Todos os artefatos sao isolados do M1. Os parquets oficiais nao foram alterados.

---

## 10. Recomendacao final

**Status:** `EXPERIMENTO_VALIDADO_COM_BLOQUEADORES`

**Decisao:** Manter como experimento paralelo. Nao promover ao M1 ainda.

**Condicoes para promocao futura (M2 ou revisao M1):**

| condicao | status |
| --- | --- |
| cobertura espacial >= 95% em cidades-alvo | ATENDIDA (100% nas 4 cidades testadas) |
| diferenciacao intraurbana confirmada | ATENDIDA (amplitude p95-p05 entre 54 e 74 em todas) |
| fonte canonica de renda por setor definida | PENDENTE |
| score comparavel com ranking nacional | MITIGADO (score_setor_ancorado disponivel) |
| custo computacional nacional avaliado empiricamente | PENDENTE (apenas estimado) |
| pipeline nacional testado em >= 5 UFs | PENDENTE (testado em 3 UFs) |

**Proximos passos recomendados (em ordem):**
1. Definir fonte canonica de renda por setor 2010 (V005/pop_total como proxy, ou tabela de renda domiciliar per capita)
2. Executar experimento em mais 2 UFs (ex: MG e RS) para confirmar robustez
3. Medir custo real de spatial join em UF grande completa (ex: SP com todos os municipios)
4. Avaliar Censo 2022 por setor quando disponivel como substituto ao 2010
5. Decidir: candidato ao M1 com ancoragem nacional, ou camada complementar no M2

**Caminho recomendado de evolucao:** modulo complementar de precisao intraurbana, disponivel opcionalmente no M2, com flag `SETOR_CENSITARIO_ENABLED` — sem substituir o pipeline nacional do M1.
