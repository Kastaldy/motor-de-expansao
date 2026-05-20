# Contrato: Visao Executiva Ultra e Analise Pontual de Entorno

> Contrato de UX, metricas de raio e limites tecnicos para o ciclo Visao Executiva Ultra e Analise Pontual.
> Versao: 2026-05-20

---

## 0. Evolucao planejada - hardening (Blocos 8-13)

O ciclo ativo transforma a Analise Pontual em leitura executiva completa e padroniza a regua visual de scores. Prioridades:

- **Regua visual canonica** (Bloco 9): todos os modos quantitativos (M1, Censitario, Hibrido, Residual) usam faixas de 10 pontos (`0-10`, ..., `90-100`) reaproveitando `RESIDUAL_SCORE_BANDS`.
- **Populacao e renda no raio** (Bloco 10): mostrar `pop_total_raio` e `renda_per_capita_media_raio`, preferindo dados censitarios/setoriais quando disponiveis.
- **Pins de concorrentes e Ultra no mapa pontual** (Bloco 11 concluido): exibir unidades dentro do raio com tooltips equivalentes aos mapas principais, filtradas por distancia haversine ao ponto central.
- **Clique exato** (Bloco 12 concluido): decisao tecnica tomada — manter `st.pydeck_chart` com centroide do hex; `streamlit-folium` e componente customizado descartados. Nota visual exibida quando clique ativo; fallback por `lat,lng` na sidebar.

**Nota de area:** raio `1.6 km` gera area circular de `pi * 1.6^2 = 8.04 km2`, nao `~5 km2`. Se o produto precisar manter `~5 km2`, propor ajuste do raio para `~1.26 km` com aprovacao explicita antes de implementar.

Qualquer caminho do clique deve preservar o fallback manual por `lat,lng` e nao pode alterar M1, carteira, plano ou artefatos oficiais.

## 1. Visao Executiva — novo desenho

### Proposta
A aba `Visao Executiva` deixa de ser uma visualizacao generica do M1 e passa a ser a **leitura institucional da rede Ultra**: presenca propria no territorio, indicadores de mercado agregados e oportunidades estrategicas.

### Mapa da Visao Executiva
- Renderiza **apenas pins das unidades Ultra** (`data/ultra/Ultra.csv`).
- Sem hexagonos H3, sem heatmap, sem camadas M1/hibrido/censitario.
- Tooltip de cada pin: nome da unidade, cidade, UF, coordenadas.
- Filtros globais (UF/cidade) filtram quais pins sao exibidos.
- Estado vazio quando o arquivo Ultra.csv estiver ausente ou vazio: exibir mensagem informativa, nao travar o app.
- Zoom inicial: Brasil completo; centraliza no centroide das unidades filtradas quando ha recorte ativo.

### KPIs executivos (topo da aba)
| KPI | fonte | fallback |
| --- | --- | --- |
| Unidades Ultra no recorte | `Ultra.csv` filtrado | 0 |
| Cidades com presenca Ultra | `Ultra.csv` filtrado | 0 |
| Oportunidades sem Ultra proxima (<1 km) | `hexagonos_brasil_dashboard` + `Ultra.csv` | n/a |
| Residual potencial total no recorte (alunos) | `oportunidades_expansao_hibrido` | n/a |
| Score M1 medio no recorte | `hexagonos_brasil_dashboard` | n/a |
| Ancoras de dominio no recorte | `plano_expansao_dominio` | n/a |

### Graficos executivos (abaixo dos KPIs)
1. **Presenca Ultra por UF** — barras: unidades por UF no recorte.
2. **Residual potencial por UF/cidade** — barras: `oferta_efetiva_disponivel` agregada.
3. **Distribuicao de `score_oportunidade_residual`** — histograma das oportunidades no recorte.
4. **Oportunidades por distancia ate Ultra mais proxima** — barras agrupadas por faixa: 0-1 km, 1-3 km, 3-5 km, >5 km.
5. **Top cidades: alto residual e baixa presenca Ultra** — tabela ou grafico de dispersao.

---

## 2. Analise Pontual de Entorno — definicao

### Conceito
Analise de tudo que existe dentro de um raio fixo ao redor de um ponto geografico de interesse (potencial locacao, espaco comercial, endereco).

### Parametros fixos
| parametro | valor | observacao |
| --- | --- | --- |
| Raio default | 1.6 km | ~8.04 km2 de area circular |
| Area aproximada | pi * 1.6^2 = 8.04 km2 | calculado por formula; nao por poligono real |
| Unidade de distancia | haversine entre centroides | sem shapefile de geometria fina |
| Resolucao H3 | 7 | consistente com o M1 |

### Metricas calculadas no raio
| metrica | descricao |
| --- | --- |
| `n_hexes_raio` | numero de hexes com centroide dentro do raio |
| `residual_total` | soma de `oferta_efetiva_disponivel` no raio |
| `score_residual_medio` | media de `score_oportunidade_residual` no raio |
| `score_residual_max` | maximo de `score_oportunidade_residual` no raio |
| `score_m1_medio` | media de `score_priorizacao` no raio |
| `score_m1_max` | maximo de `score_priorizacao` no raio |
| `score_hibrido_medio` | media de `score_expansao_hibrido` no raio (quando disponivel) |
| `score_hibrido_max` | maximo de `score_expansao_hibrido` no raio (quando disponivel) |
| `n_concorrentes_raio` | contagem de unidades concorrentes no raio |
| `n_ultra_raio` | contagem de unidades Ultra no raio |
| `n_ancoras_dominio_raio` | contagem de ancoras de dominio no raio |
| `pop_total_raio` | soma da populacao residente nos hexes/setores dentro do raio, preferindo `pop_total_setor_2022` |
| `fonte_pop_total_raio` | origem predominante da populacao usada: setor 2022, mercado residual, total municipal, proxy ou ausente |
| `renda_per_capita_media_raio` | renda per capita media no raio, preferencialmente ponderada por populacao |
| `metodo_renda_raio` | indica se a renda foi ponderada por populacao, media simples ou fallback |
| `hex_mais_proximo` | `hex_id` do hex mais proximo do ponto central |
| `distancia_hex_mais_proximo_km` | distancia ao centroide mais proximo |

### Tabela do entorno
- Lista hexes/oportunidades dentro do raio, ordenada por distancia crescente e `score_oportunidade_residual` decrescente.
- Colunas exibidas: `hex_id`, `municipio`, `uf`, `distancia_km`, `score_priorizacao`, `score_oportunidade_residual`, `oferta_efetiva_disponivel`, `n_concorrentes_hex`.

---

## 3. UX da Analise Pontual

### Localizacao no dashboard
- Secao dedicada dentro da aba `Mapa Territorial` (subsecao abaixo do mapa) **ou** nova subsecao na `Visao Executiva`.
- Decisao final no Bloco 5; contrato de UX permanece o mesmo.

### Entrada de coordenada
- Campo de texto: formato `lat, lng` (ex: `-23.55, -46.63`).
- Reutilizar `parse_coordinate_input` ja existente na sidebar.
- Botao "Analisar entorno" aciona o calculo.
- Mostrar coordenada formatada para copiar no formato `lat,lng` (Google Maps / GPS).

### Visualizacao no mapa
- Pin no ponto central da analise (cor distinta dos pins Ultra e concorrentes).
- Circulo/anel de raio 1.6 km ao redor do ponto (linha tracejada ou anel semitransparente via `ScatterplotLayer` com `stroked=True`).
- Hexes dentro do raio destacados ou com cor diferenciada.
- Pins de concorrentes e Ultra dentro do raio, com tooltips equivalentes aos mapas principais, renderizados acima do circulo/ponto central.

### Fallback por captura via clique
- Alvo de produto: clique esquerdo em qualquer ponto do mapa deve preencher a coordenada exata (`lat,lng`) da Analise Pontual.
- Estado atual: `st.pydeck_chart` captura selecao de objeto de camada; ao clicar em H3, a coordenada disponivel tende a ser o centroide do hex, nao o ponto exato clicado.
- Decisao tecnica pendente: comparar `st.pydeck_chart`, `streamlit-folium` e componente customizado. Documentar a escolha antes de implementar.
- Fallback obrigatorio: campo manual de coordenada na sidebar.
- Botao direito/context menu e desejavel para copiar/exibir coordenada, mas nao e requisito bloqueante enquanto o componente atual nao suportar.

---

## 4. Limitacoes tecnicas registradas

### Captura de clique no mapa — decisao tecnica (Bloco 12)

**Decisao:** manter `st.pydeck_chart` com captura por centroide de hex. Opcao customizada e folium descartadas.

| opcao | avaliacao | decisao |
| --- | --- | --- |
| `st.pydeck_chart` + centroide | sem nova dependencia; consistente com mapas principais; centroide inerente a res-7 | **adotada** |
| `streamlit-folium` | `last_clicked` daria coord exata; porém: +2 dependencias, inconsistencia visual Leaflet vs deck.gl | descartada |
| componente customizado JS/React | maximo controle; fora do escopo do ciclo e do deploy offline | descartada |

**Justificativa para manter pydeck:**
- H3 res-7 hexes tem area de ~5.16 km² e diametro ~3-4 km. O centroide de um hex esta a no maximo ~1.3 km de qualquer ponto dentro do hex.
- A analise pontual opera com raio 1.6 km e leitura por centroide de hex — a precisao do clique nao muda esse limite.
- O campo `lat,lng` na barra lateral ja oferece coordenada exata para quem precisa.
- Dashboard offline; novas dependencias de UI aumentam superficie de manutencao.

**Comportamento atual e documentado:**
- Clique em hex: captura `(lat, lng)` do centroide do hex via `_extract_click_coord_from_selection`.
- Clique em espaco vazio: nao dispara evento (limitacao do pydeck).
- Botao direito: nao suportado.
- Nota visual: apos clique, dashboard exibe `"Ponto ativo: lat, lng (centroide do hex selecionado). Para coordenada exata, use lat,lng na barra lateral."`.
- Fallback obrigatorio: campo `lat, lng` na barra lateral permanece em todos os cenarios.
- Guardrail: clique nao altera `score_priorizacao`, filtros globais, carteira, plano ou artefatos M1.

### Precisao da analise radial
- Distancias calculadas por haversine entre centroides dos hexes e o ponto central.
- Sem geometrias finas de setor censitario, rua ou lote: a leitura e aproximada.
- Hexes grandes (H3 res 7 ≈ 5.16 km2) podem ter centroide fora da area de interesse mesmo que parte do hex esteja dentro do raio.
- Leitura adequada para decisao estrategica; nao adequada para analise de vizinhanca em escala de metros.

### Dados faltantes
- Colunas opcionais (ex: `score_oportunidade_residual`, `oferta_efetiva_disponivel`, `score_expansao_hibrido`) podem estar ausentes dependendo dos artefatos disponiveis.
- Fallback: exibir `n/a` ou omitir a metrica; nao travar a analise.

---

## 5. Guardrails fixos

- **Nenhuma interacao desta aba ou da analise pontual pode recalcular ou alterar:**
  - `score_priorizacao`
  - `hex_score_estrutural`
  - `carteira_expansao_acionavel`
  - `plano_expansao_curto_prazo`
  - `plano_expansao_dominio`
  - qualquer artefato oficial do M1 listado em `docs/m1_outputs_oficiais.md`
- Toda analise e leitura; nenhuma escrita em disco por acao do usuario.
- Pins, circulos e destaques de raio sao camada visual efemera; desaparecem ao remover o ponto de analise.

---

## 6. Mapa de implementacao (referencias aos blocos do PRD)

| bloco | entrega |
| --- | --- |
| Bloco 1 | Este documento |
| Bloco 2 | `build_ultra_presence_map` + mapa Ultra-only na Visao Executiva |
| Bloco 3 | KPIs e graficos executivos da rede e mercado |
| Bloco 4 | `analisar_entorno_ponto(lat, lng, raio_km=1.6)` — motor analitico |
| Bloco 5 | UI de analise pontual, campo de coordenada, mapa com circulo de raio |
| Bloco 6 | Investigacao e implementacao de captura por clique/botao direito |
| Bloco 7 | Hardening ciclo 1-7, validacao final e docs |
| Bloco 8 (este) | Contrato hardening, area 8.04 km2, regra visual canonica definida |
| Bloco 9 | Implementacao da regua 10-em-10 nos modos M1/Censitario/Hibrido/Residual |
| Bloco 10 | Motor de Analise Pontual com `pop_total_raio` e `renda_per_capita_media_raio` |
| Bloco 11 | Pins de concorrentes e Ultra no mapa da Analise Pontual |
| Bloco 12 | Decisao tecnica do clique exato — pydeck com centroide adotado |
| Bloco 13 | Hardening final, docs e regressao visual — ciclo concluido em 2026-05-20 |

---

## 7. Regra visual canonica de scores (0-100 em faixas de 10 pontos)

A partir do Bloco 9, todos os modos quantitativos do mapa devem usar a mesma regua visual.

### Paleta canonica

Derivada de `RESIDUAL_SCORE_BANDS` em `dashboard/constants.py`:

| faixa | cor hex |
| --- | --- |
| 0-10   | #941212 |
| 10-20  | #B92323 |
| 20-30  | #DC4141 |
| 30-40  | #DC6914 |
| 40-50  | #F0941E |
| 50-60  | #EEC828 |
| 60-70  | #96D250 |
| 70-80  | #50C33C |
| 80-90  | #19A832 |
| 90-100 | #0A8226 |

### Score-fonte por modo

| modo | score-fonte | campo |
| --- | --- | --- |
| M1 | Score de priorizacao M1 | `score_priorizacao` |
| Censitario | Score censitario calibrado 2022 | `score_setor_2022_calibrado` |
| Hibrido | Score de expansao hibrido | `score_expansao_hibrido` |
| Residual | Score de oportunidade residual | `score_oportunidade_residual` |

Observacao: `faixa_oportunidade` continua sendo util para filtros e leitura executiva no modo M1, mas **a cor do hex deve ser derivada de `score_priorizacao`**, nao da faixa categorica.

### Guardrail

A padronizacao visual nao altera `score_priorizacao`, `hex_score_estrutural`, ranking, carteira, plano de curto prazo, plano de dominio nem qualquer artefato oficial do M1. Cor e representacao visual derivada do score existente, sem recalculo.
