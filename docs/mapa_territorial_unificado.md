# Mapa Territorial Unificado — Contrato de UX, Camadas e Guardrails

**Ciclo:** Mapa Territorial Unificado
**Status:** Contrato aprovado (Bloco 1)

## Objetivo

Consolidar os quatro mapas repetidos do dashboard em um unico mapa principal com modo de cor selecionavel e overlays opcionais, sem perder funcionalidades existentes.

## Inventario dos mapas atuais

| mapa | aba/subtab atual | builder | coluna de cor | overlays |
|---|---|---|---|---|
| Mapa M1 | Visao Executiva | `build_map_figure` | `faixa_oportunidade` / `score_priorizacao` | concorrentes, Ultra, search |
| Mapa Hibrido | Modelo Hibrido > Oportunidades Hibridas | `build_hybrid_map_figure` | `score_oportunidade_residual` | concorrentes, Ultra, search |
| Mapa Residual Fitness | Modelo Hibrido > Mapa Residual Fitness | `build_residual_heatmap_figure` | `score_oportunidade_residual` | concorrentes, Ultra, search |
| Mapa Dominio | Expansao de Dominio | `build_dominio_map_figure` | `ordem_expansao_cidade` | concorrentes, Ultra |

Obs.: Mapa Hibrido e Mapa Residual usam a mesma coluna de cor e sao funcionalmente redundantes.

## Modos de cor (exclusivos — um por vez)

| id | label | coluna principal | parquet fonte | builder atual |
|---|---|---|---|---|
| `m1` | M1 | `faixa_oportunidade` / `score_priorizacao` | `hexagonos_brasil_dashboard.parquet` | `build_map_figure` |
| `hibrido` | Hibrido | `score_expansao_hibrido` | `oportunidades_expansao_hibrido.parquet` | `build_hybrid_map_figure` |
| `censitario` | Censitario | `score_setor_2022_calibrado` | `oportunidades_expansao_hibrido.parquet` | `build_hybrid_map_figure` (adaptado) |
| `residual` | Residual Fitness | `score_oportunidade_residual` | `oportunidades_expansao_hibrido.parquet` | `build_residual_heatmap_figure` |
| `dominio` | Expansao de Dominio | `ordem_expansao_cidade` | `plano_expansao_dominio.parquet` | `build_dominio_map_figure` |

- Modo padrao: `m1`.
- Quando a coluna do modo nao existir no Parquet do recorte, exibir aviso inline e retornar ao modo `m1`.
- Modos `hibrido`, `censitario` e `residual` requerem `oportunidades_expansao_hibrido.parquet`.
- Modo `dominio` requer `plano_expansao_dominio.parquet`.

## Overlays opcionais (independentes entre si)

| id | label | fonte | padrao | comportamento quando ausente |
|---|---|---|---|---|
| `concorrentes` | Concorrentes | `concorrentes/*.csv` | ligado | ocultado silenciosamente |
| `ultra` | Ultra | `data/ultra/Ultra.csv` | ligado | ocultado silenciosamente |
| `ancoras_dominio` | Ancoras Dominio | `plano_expansao_dominio.parquet` | desligado | ocultado silenciosamente |
| `hex_pesquisado` | Hex pesquisado | busca por coordenada | ligado | ocultado quando sem busca ativa |
| `descartados_5k` | Descartados <5k hab | coluna `flag_pop_min_5k` | ligado | hexes cinza ocultos quando desligado |

Todos os overlays sao puramente visuais: nao alteram `score_priorizacao`, `hex_score_estrutural`, ranking, carteira, plano curto prazo nem artefatos oficiais do M1.

## Funcionalidades preservadas

- Filtros globais: UF, municipio, faixa de oportunidade, elegibilidade hibrida, cobertura censitaria, qualidade de join, top_municipio, top_hex_intraurbano.
- Busca por coordenada: centraliza mapa com zoom 10, destaca hex em amarelo (mesmo fora dos filtros ou descartado), exibe card de detalhe com score, rank, renda e populacao.
- Regua 5k: hexes com `flag_pop_min_5k=False` recebem cor cinza `[120, 120, 140, 70]` quando overlay `descartados_5k` ativo.
- Pins de concorrentes e Ultra como overlays independentes.
- Dashboard funcional com apenas UF selecionada, UF+cidade ou apenas coordenada.

## Controles da aba Mapa Territorial

- Seletor de modo de cor: radio ou selectbox no topo da aba.
- Checkboxes de overlays: linha horizontal ou expander "Overlays" no topo ou sidebar.
- Legenda dinamica: renderizada abaixo dos controles, refletindo modo e overlays ativos.
- Opacidade: slider opcional (nao bloqueia entrega do Bloco 3/4).

## Guardrails

- Camadas visuais e refatoracoes de UI nao podem recalcular nem modificar: `score_priorizacao`, `hex_score_estrutural`, `carteira_expansao_acionavel`, `plano_expansao_curto_prazo`, `plano_expansao_dominio` ou qualquer artefato oficial do M1.
- Overlays e modos de cor so leem dados; nao escrevem nem transformam colunas de score.
- Fallback gracioso obrigatorio: modo sem dados no recorte deve exibir aviso e nao quebrar o mapa.
- `score_priorizacao` permanece identico ao valor lido do Parquet.

## Navegacao esperada apos ciclo (Bloco 5)

Estrutura sugerida de abas:
```
Visao Executiva | Mapa Territorial | Expansao de Dominio | Carteira e Plano
```

Absorcao planejada:
- Mapa M1 da "Visao Executiva" → Mapa Territorial (modo M1)
- Mapas de "Modelo Hibrido" → Mapa Territorial (modos Hibrido, Censitario, Residual)
- Mapa da "Expansao de Dominio" → Mapa Territorial (modo Dominio) + aba propria mantida

Funcionalidades nao-mapa preservadas fora do Mapa Territorial:
- KPIs executivos, cards de resposta, graficos de cidade/UF → Visao Executiva
- Tabelas de ranking e analise territorial → Visao Executiva
- Tabelas operacionais de carteira e plano → Carteira e Plano
- Tabela e KPIs de dominio → Expansao de Dominio
