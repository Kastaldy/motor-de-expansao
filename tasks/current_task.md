# Current Task

## Bloco atual

ID: BLK-UI-08
Nome: Refinos de UX/UI do dashboard (paleta Renda, tab sticky, busca por endereço)
Status: CONCLUÍDO (ciclo + FU1) — commit por path + PR nesta branch (2026-06-17)
Tipo: feature (UX/UI; READ-ONLY sobre M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [aprovação humana] → Builder → QA (concluído) + FU1 interativo (aprovado por Vini)
Skill atual: Fechamento (commit + PR)
Próxima Skill: Revisão/merge humano do PR
FU1: geocoder Nominatim, sticky funcional+polido, scroll ao trocar de aba, círculo do raio azul; DEC-010 com emenda OSM.

## Veredito do QA (2026-06-17)
APROVADO. Suíte FULL serial = 975 passed, 1 skipped, 0 failed (xdist `-n auto` abortou com INTERNALERROR do execnet no Python 3.14 — contorno serial autorizado, não bypass). ruff/mypy/import limpos. READ-ONLY M1 confirmado (git diff -- src/ não toca config/pipelines-m1/scoring/artefatos; §3 intacto). 3 mudanças + DEC-010 conforme plano. Nenhum teste bate na rede real (mock urllib legítimo, DEC-010(c)). Housekeeping --check em estado pré-move esperado (exit 1, stub ausente); move é passo do orquestrador. Paths pré-sujos NÃO staged. Sem problemas críticos/médios.
Gate humano: D1 = Alternativa B (fetch HTTP) + DEC-010 APROVADA por Vinicius em 2026-06-17.

## Objetivo
Aplicar três refinos de interface no dashboard: (1) nova paleta de cores absoluta para o mapa de
Renda Média, (2) tab selector fixo (sticky) ao rolar a página, e (3) busca por endereço na barra de
pesquisa (endereço → coordenada), sem regressão funcional nem do M1.

## Escopo citado pelo usuário (Vini, 2026-06-17)
1. **Paleta da Renda Média** — alterar a paleta do mapa gerado a partir da análise de Renda Média para
   5 faixas absolutas:
   - #00CC00  (> 5000)
   - #A8FFA8  (3500–5000)
   - #FFD21C  (2000–3500)
   - #FFFF00  (1000–2000)
   - #F7F48B  (≤ 1000)
2. **Tab selector sticky** — o seletor de abas deve fixar no topo da tela quando o scroll passar por ele.
3. **Busca por endereço** — a barra de pesquisa deve aceitar endereço, convertido para coordenada durante
   a busca. Código de referência fornecido: `endereco_para_link_maps` (limpeza textual + percent-encoding,
   sem imports/regex/urllib; produz link do Google Maps). Já existe `api/maps_geocoder` (URL Maps → coordenada).

## Classificação (Passo 2)
Alta — mexe no dashboard de produção; READ-ONLY sobre M1. Confirmado pelo Block Orchestrator.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet (concluído)
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-UI-08 (criada a partir do HEAD atual = ciclo/BLK-FIX-14, por escolha explícita do usuário).
Consequência aceita pelo usuário: carrega o commit f89fc41 (BLK-FIX-14) até este ser mergeado.

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md

## Riscos / pontos sensíveis a tratar no Planner + gate humano
- Endereço → coordenada normalmente exige chamada online → tensiona o guardrail §2 ("não criar dependência
  de API ao vivo no dashboard de produção"). Pode exigir uma DEC (precedente: DEC-004 do basemap).
- Confirmar se a "imagem do mapa de Renda Média" é o relatório censitário (PDF, `RENDA_PER_CAPITA_BANDS`) ou
  o choropleth do dashboard — pinar o(s) arquivo(s) exato(s) e a constante de faixas.

## Fora de escopo
- score/pesos/artefatos M1; quebrar contratos de performance (carga lazy por UF, render lazy de abas, fonte
  de mapa enxuta — Blocos 4–6).
