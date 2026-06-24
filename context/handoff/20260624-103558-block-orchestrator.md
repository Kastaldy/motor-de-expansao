# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (esteira Alta; gate humano obrigatório antes do Builder)

## Bloco refinado
**BLK-RELMUN-02 — "Bairros por Zona" com nomes reais de bairro**

Resolve a decisão temporária D9 do BLK-RELMUN-01 (DEC-011): a página "Bairros por Zona"
(página 7 das 9 do Relatório Municipal) está simplificada porque a malha geo IBGE 2022
materializada (`data/outputs/setores_censitarios_2022_geo/uf=XX/cod_municipio=N/part-000.parquet`)
não contém `NM_BAIRRO` — a coluna não é selecionada no shapefile nem consta em `COLUNAS_ARTEFATO`
de `materializar_setores_censitarios_geo.py`. O shapefile IBGE 2022 (`BR_setores_CD2022.shp`) tem
as colunas `CD_SETOR, CD_UF, CD_MUN, NM_MUN, SITUACAO, AREA_KM2, geometry` — `NM_BAIRRO` não é
uma coluna padrão desse shapefile. Nenhuma fonte de bairro existe hoje no repositório.

## Objetivo
Dar à página "Bairros por Zona" do Relatório Municipal a lista de bairros reais agrupados por
zona (Âncora central / Flancos laterais / Cerco), com fallback gracioso quando o município não
tiver bairro mapeado, sem regredir o Relatório Pontual Censitário nem tocar o M1.

## Criticidade classificada
**Alta**

Justificativa: o bloco é READ-ONLY sobre o M1 (não toca `score_priorizacao`, `hex_score_estrutural`,
carteira, plano curto prazo, plano de domínio nem qualquer artefato oficial M1 — guardrail §5/§8).
Envolve, entretanto, enriquecimento/re-materialização de uma base geo derivada (~1,17 GB / 5.571
municípios) e alteração de uma página do Relatório Municipal existente — ambos exigem gate humano
(esteira Alta). Não Crítica porque não toca artefatos M1. Nenhuma sub-decisão neste bloco deve ser
tomada pelo Builder antes do gate humano, em particular a escolha da direção candidata (ver abaixo).

---

## QUESTÕES ABERTAS PARA O GATE HUMANO DECIDIR

As três direções abaixo são MUTUAMENTE EXCLUSIVAS na forma de implementação e têm impactos muito
diferentes. O Planner deve apresentá-las com prós/contras ao humano; NÃO pré-fixar a direção.

### Direção A — Re-materializar a malha geo IBGE 2022 incluindo NM_BAIRRO (ou equivalente)
- O shapefile `BR_setores_CD2022.shp` (setor censitário IBGE 2022) **não tem `NM_BAIRRO`** como
  campo padrão. IBGE disponibiliza bairro/subdistrito apenas em Malha de Bairros separada
  (`Malha_Bairros_2022` ou `Malha_Subdistritos_2022`), não no shapefile de setores.
- Viável se o Planner confirmar a existência da Malha de Bairros IBGE 2022 e um join setor→bairro
  por containment espacial. Offline, robusto, mas é um job pesado: ~1,17 GB de geometrias
  re-processadas para todos os 5.571 municípios.
- **Impacto em `materializar_setores_censitarios_geo.py`:** adicionar coluna `nome_bairro` em
  `COLUNAS_ARTEFATO`; re-materializar os parquets de toda a malha geo.
- **Risco maior:** a Malha de Bairros IBGE não cobre todos os municípios (só capitais e alguns
  municípios grandes têm bairro IBGE oficial). Para os demais, o campo ficaria nulo → fallback
  obrigatório mesmo nessa direção.

### Direção B — Cruzar com camada externa de bairros (OSM / admin) sem re-materializar a malha
- Carregar polígonos de bairro de uma fonte externa (OSM `admin_level=10` via `osmnx` ou arquivo
  local pré-baixado) e fazer join espacial setor×bairro na hora da geração do relatório, só para
  o município solicitado.
- Não re-materializa a malha global (~1,17 GB). O join ocorre on-demand durante `agregar_municipio`
  ou `gerar_pdf_relatorio_municipal`.
- **Impacto:** novo helper em `relatorio_municipal.py` (ou módulo auxiliar); `agregar_municipio`
  recebe `bairros_gdf` opcional; a página "Bairros por Zona" usa o resultado com fallback gracioso.
- **Risco:** dependência de internet ou arquivo OSM local (conflito com guardrail de offline do
  dashboard); cobertura irregular (municípios pequenos sem polígonos de bairro no OSM).
- Se usar arquivo OSM local pré-baixado por município: é um novo artefato de dados externo
  (gitignored, peso variável); o Planner deve dimensionar.

### Direção C — Reverse-geocode pontual do centróide dos hexes de cada zona (Nominatim)
- Para cada hex de zona, chamar `resolve_endereco_http` / Nominatim e extrair o campo `suburb` ou
  `neighbourhood` da resposta JSON.
- **INVIÁVEL em lote:** um município típico tem dezenas a centenas de hexes destacados; uma
  chamada de rede por hex viola o guardrail de offline e a política de uso do Nominatim
  (máx. 1 req/s, sem uso em massa — DEC-010). Lento e não-determinístico.
- Aceitável **apenas como fallback pontual** para municípios muito pequenos (<5 hexes de zona),
  nunca como mecanismo principal.
- Esta direção NÃO deve ser a primária; mencionada para completude.

---

## Escopo permitido
- Alterar `src/motor_expansao/dashboard/relatorio_municipal.py`: a função `_bairros_page` e
  helpers de suporte (ex.: `_bairros_por_zona`); `agregar_municipio` pode receber parâmetros
  opcionais adicionais para a lista de bairros.
- Se Direção A aprovada: alterar `src/motor_expansao/pipelines/materializar_setores_censitarios_geo.py`
  (adicionar coluna `nome_bairro` a `COLUNAS_ARTEFATO` e ao pipeline de materialização); re-materializar
  parquets da malha geo (job de dados, ~1,17 GB).
- Se Direção B aprovada: criar helper de join espacial (módulo novo ou em `relatorio_municipal.py`),
  sem alterar `materializar_setores_censitarios_geo.py`.
- Testes novos para a página "Bairros por Zona" com e sem bairros mapeados (fallback gracioso).
- Atualizar `docs/relatorio_municipal_template.md` (D9 deixa de ser "simplificada").
- Fallback gracioso obrigatório em qualquer direção: quando o município não tiver bairro mapeado,
  a página exibe o que existir (zonas geométricas + tese) sem exceção e sem nota de "indisponível"
  como texto principal.

## Fora de escopo
- Qualquer alteração em `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo,
  plano de domínio ou artefatos oficiais M1 (`brasil_estrutural.parquet`, `brasil_priorizados.parquet`,
  `hexagonos_brasil_oportunidades.parquet`, `hexagonos_brasil_dashboard.parquet`, etc.).
- Alterar o Relatório Pontual Censitário (raio 1,5 km): `censo_report.py`, `censo_map.py`,
  `analisar_ponto_censitario_setores`, `setor_censitario_intersecao_area_1p5km` — byte-a-byte
  intocados.
- Quebrar os contratos de performance dos Blocos 4–6 (carga lazy por UF, render lazy de abas,
  fonte de mapa enxuta): `load_uf_slice`, `read_enriched_uf_partition`, `build_dashboard_dataset`,
  `render_tab_selector` — intocados.
- Dependência de API ao vivo em lote na CARGA do dashboard (reverse-geocode de todos os hexes
  como pipeline batch está fora de escopo; Nominatim só pode aparecer como fallback pontual, se
  aprovado pelo gate).
- Alterar o número de páginas do PDF (deve continuar com 9 páginas, ordem inalterada).
- Alterar `config.py`, `pipelines/m1/` ou qualquer parâmetro canônico do §3 do CLAUDE.md.

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/relatorio_municipal.py` — funções `_bairros_page`, `_zonas_geometricas`,
  `_zonas_do_municipio`, `agregar_municipio`, `PDF_SECTION_HEADERS`, `COLUNAS_ARTEFATO` (linha 84–117),
  constantes de cores de zona.
- `src/motor_expansao/pipelines/materializar_setores_censitarios_geo.py` — `COLUNAS_ARTEFATO`,
  `carregar_malha_uf` (col selecionadas do shapefile), `escrever_particoes`.
- `docs/relatorio_municipal_template.md` — Página 6 ("Bairros por Zona"), decisões D9.
- `tasks/backlog.md` — BLK-RELMUN-02, critérios de aceite.
- `CLAUDE.md` — §2 (guardrails offline), §4 (estrutura da malha geo), §5 (guardrail permanent),
  DEC-010 (Nominatim, limites de uso), DEC-011 (D9 simplificação temporária).
- Testes existentes de `relatorio_municipal`: `tests/` (verificar cobertura da página "Bairros por Zona").

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/relatorio_municipal.py` — `_bairros_page` e helpers de suporte.
- **Condicional (Direção A apenas):** `src/motor_expansao/pipelines/materializar_setores_censitarios_geo.py`
  — `COLUNAS_ARTEFATO` + pipeline de materialização + re-materialização dos parquets da malha geo.
- `docs/relatorio_municipal_template.md` — atualizar D9 de "simplificada" para "implementada".
- Arquivos de teste relevantes à página de bairros.
- `tasks/backlog.md` e `tasks/completed.md` ao final do ciclo (pelo orquestrador).

## Critérios de aceite
1. A página "Bairros por Zona" (página 7/9 do PDF) lista bairros reais agrupados por zona (Âncora
   central / Flancos laterais / Cerco) para pelo menos um município coberto pela fonte escolhida.
2. Fallback gracioso verificável: para um município sem bairro mapeado, a página renderiza sem
   exceção (sem `raise`, sem nota de erro visível como texto principal).
3. O Relatório Pontual Censitário (raio 1,5 km) permanece byte-a-byte intocado: suíte censitária
   verde, `setor_censitario_intersecao_area_1p5km` e `render_mapas_censitarios_combinados` não
   alterados.
4. M1 intocado: `score_priorizacao`, pesos, artefatos oficiais, `config.py` inalterados.
5. Suíte completa verde (ruff + mypy + pytest) após a implementação; nenhum bypass de CI.
6. O PDF gerado continua com 9 páginas na mesma ordem.
7. Performance dos Blocos 4–6 não regredida (carga lazy por UF, render lazy de abas).

## Esteira recomendada
Block Orchestrator (concluído) → **Planner** (elaborar plano técnico com as 3 direções e
prós/contras para o gate humano) → `[REVISÃO HUMANA — gate: escolha da direção A/B/C]` →
Builder → QA

## Riscos identificados
- **Cobertura incompleta de bairros (todas as direções):** `NM_BAIRRO` não existe no shapefile
  padrão de setores IBGE 2022; mesmo a Malha de Bairros IBGE cobre principalmente capitais e
  municípios grandes. O fallback gracioso é mandatório, não opcional.
- **Tamanho do job de re-materialização (Direção A):** ~1,17 GB de geometrias / 5.571 municípios
  / 468.099 setores. Tempo de execução alto; o Planner deve estimar e propor estratégia
  (re-materializar só as UFs necessárias? re-materializar tudo?).
- **Dependência de internet em lote (Direção B via OSM online):** viola guardrail §2 se feito
  na carga do dashboard. Aceitável só se o join for feito na hora da geração do relatório
  (sob demanda) com fallback offline gracioso — exatamente como DEC-004/DEC-011 para tiles.
- **Direção C (Nominatim em lote):** explicitamente fora de escopo como mecanismo primário.
  Uso em lote viola a Nominatim Usage Policy (máx. 1 req/s) — DEC-010.
- **Regressão de testes do Relatório Municipal:** `_bairros_page` hoje tem comportamento fixo
  (simplificado). Qualquer mudança nela pode quebrar testes existentes; verificar antes de editar.
- **Dados ausentes em produção:** os parquets de domínio (`plano_expansao_dominio.parquet`) e a
  malha geo devem existir para o município selecionado; ambos têm fallback gracioso já implementado,
  mas o Planner deve verificar se a nova coluna de bairro propaga corretamente por esse fallback.

## Guardrails ativos
- §5 CLAUDE.md: "visualizações, análise radial e interações de mapa não podem recalcular ou
  alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano domínio
  ou artefatos oficiais do M1 sem aprovação explícita."
- §2 CLAUDE.md: "Não criar dependência de API ao vivo no dashboard de produção." (Exceção pontual
  admissível apenas via DEC, como DEC-004/DEC-010/DEC-011.)
- DEC-011 D9: simplificação temporária resolvida por este bloco; as demais decisões D1–D8 são
  intocadas.
- DEC-010: Nominatim, máx. 1 req/s, sem uso em massa — proíbe reverse-geocode em lote.
- Guardrail do loop (§6.1): este bloco NÃO é `loop-safe` (toca base geo derivada e página do
  relatório; exige gate humano).