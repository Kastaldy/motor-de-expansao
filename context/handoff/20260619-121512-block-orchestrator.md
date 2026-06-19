# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (criticidade Alta → gate humano obrigatório antes do Builder)

## Bloco refinado
BLK-UI-09 — Busca por link do Google Maps na barra de pesquisa do dashboard

Adicionar suporte ao terceiro formato de entrada na `render_coord_search_sidebar`: um link
do Google Maps (URL longa `maps.google.com/maps/place/...` com `!3d`/`!4d` ou `@lat,lng`)
é extraído por regex pura (`extract_any_coord`, já existente em `maps_geocoder.py`) SEM rede,
e o caminho de coordenada e endereço existentes ficam INTOCADOS.

## Objetivo
Fazer a barra de busca do dashboard aceitar link do Google Maps (URL longa) como terceiro
formato, resolvendo-o para coordenada offline via regex, sem regressão nos caminhos de
coordenada numérica e endereço já funcionais.

## Escopo permitido
- `src/motor_expansao/dashboard/pages.py` — apenas `render_coord_search_sidebar` (e helpers
  de UI imediatos: `_render_endereco_fallback_link` e a string descritiva da caption).
- `tests/unit/test_coord_search.py` — adicionar casos de teste para o novo caminho de link.
- Atualizar a caption/placeholder do campo `coord_search_input` para mencionar "link do Maps".
- Usar `extract_any_coord` de `motor_expansao.api.maps_geocoder` (já é import lazy, padrão
  idêntico ao da aba de viabilidade em `pages.py:3058-3064`). Não alterar `maps_geocoder.py`.
- Aplicar `_validate_brazil_bbox` ao resultado de `extract_any_coord` (mesmo padrão da aba
  de viabilidade) para rejeitar links de lugares fora do Brasil.

## Fora de escopo
- Links CURTOS (`maps.app.goo.gl`, `goo.gl/maps`): NÃO seguir redirect HTTP. Ver "Ponto
  sensível / decisão de gate" abaixo.
- Caminho numérico (`parse_coordinate_input`): INTOCADO.
- Caminho de endereço (`resolve_endereco_http` / Nominatim): INTOCADO.
- Qualquer escrita em score, pesos, artefatos M1, carteira, plano.
- Alterações em `maps_geocoder.py`, `components.py`, `utils.py`, `constants.py`.
- Alterações nas otimizações de performance: carga lazy por UF, render lazy de abas, fonte
  de mapa enxuta (Blocos 4–6).
- Páginas, builders de mapa, camadas paralelas de mercado/residual.

## Ponto sensível — decisão obrigatória no gate humano

**Links curtos do Maps (`maps.app.goo.gl`, `goo.gl/maps`) NÃO contêm a coordenada na
própria string.** Para resolvê-los seria preciso seguir o redirect HTTP e obter a URL final
com `!3d`/`!4d` — o que exigiria rede no caminho de link, da mesma forma que o endereço
exigiu na DEC-010.

Opções (o gate humano escolhe):

A. **APENAS URL longa (MVP, sem rede adicional):** `extract_any_coord` por regex pura.
   Links curtos exibem mensagem clara pedindo para usar a URL longa ou a coordenada.
   Sem nova emenda de DEC — o desvio de rede não se expande.

B. **URL longa + follow-do-redirect para links curtos:** exige uma nova emenda à DEC-010
   (ou DEC nova) cobrindo o redirect de links curtos como terceiro sub-caminho de rede,
   com cache local, timeout curto, fallback gracioso e texto anti-PII. Mesmas mitigações
   da DEC-010 (a)–(f). Tecnicamente trivial (um `urllib.request.urlopen` com
   `allow_redirects` e extração da URL final), mas exige aprovação humana explícita.

**Recomendação técnica:** Opção A no MVP (mínimo de risco, sem nova DEC); Opção B como
follow-up se o usuário confirmar. O Planner deve deixar a decisão explícita no plano para
que o gate humano escolha ANTES de qualquer código.

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/pages.py` (linhas 701–748: `render_coord_search_sidebar`;
  linhas 3040–3070: `_resolve_viab_ponto` — padrão de uso do `extract_any_coord` a replicar)
- `src/motor_expansao/api/maps_geocoder.py` (linhas 56–79: `extract_place_pin` /
  `extract_any_coord`; linha 82–85: `build_search_url`)
- `tests/unit/test_coord_search.py` (testes existentes a preservar)
- `CLAUDE.md` §2, §4, §5, DEC-004, DEC-010 (emenda 2026-06-17 incluída)
- `tasks/current_task.md`

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/pages.py` — **apenas** `render_coord_search_sidebar`
  (cascata de parsing: numérico → link Maps → endereço) e a caption/placeholder do campo.
- `tests/unit/test_coord_search.py` — novos casos de teste para o caminho de link Maps
  (URL longa com `!3d`/`!4d`, URL com `@lat,lng`, URL inválida retorna None, URL fora do
  Brasil retorna None; NUNCA bate na rede real — nenhum mock novo de urllib é necessário
  pois `extract_any_coord` é regex pura, sem I/O).

## Critérios de aceite
1. Campo `coord_search_input` aceita os três formatos sem alterar os dois existentes:
   - Coordenada `lat,lng` (intacto, `parse_coordinate_input`).
   - Link do Maps com `!3d`/`!4d` ou `@lat,lng` → extração offline, sem rede.
   - Endereço livre (intacto, `resolve_endereco_http` / Nominatim, DEC-010).
2. O parsing de link é tentado ANTES do caminho de endereço (links são mais específicos
   e o caminho é offline — não custa nada tentar; detecção por prefixo `http`/`https`).
3. URL fora do Brasil → `None` + fallback gracioso (mesmo comportamento do endereço sem match).
4. Link curto (`maps.app.goo.gl`) → mensagem clara pedindo URL longa ou coordenada
   (a menos que o gate humano aprove Opção B com emenda à DEC-010).
5. Caption/placeholder do campo menciona "link do Google Maps" como terceiro formato aceito.
6. Suíte completa verde (`pytest -q`; baseline: 532 passed, 1 skipped).
7. Nenhum novo caso de teste bate na rede real (`extract_any_coord` é regex pura, sem I/O).
8. ruff + mypy limpos.
9. READ-ONLY M1: nenhum artefato oficial alterado, score/pesos INALTERADOS.
10. Blocos 4–6 (carga lazy, render lazy, mapa enxuto): INALTERADOS.

## Criticidade classificada
**Alta** — mexe no dashboard de produção; READ-ONLY sobre o M1. A decisão sobre links
curtos (rede adicional) poderia exigir emenda à DEC-010, mas o caminho principal (URL
longa, regex offline) não expande nenhum desvio já aprovado.

## Esteira recomendada
Block Orchestrator (este) → **Planner** → `[REVISÃO HUMANA — gate obrigatório]` (decisão
sobre Opção A ou B para links curtos; aprovação do plano técnico) → **Builder** → **QA**

Tiering de modelo (Alta):
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Riscos identificados
- **Links curtos sem rede (principal):** `maps.app.goo.gl` e similares não contêm a
  coordenada na string. Sem Opção B aprovada, o campo deve comunicar isso claramente —
  não silenciar nem deixar cair no caminho de endereço (que tentaria resolver a string
  `"maps.app.goo.gl/..."` como endereço literal no Nominatim, retornando None sem mensagem
  útil ao usuário). A detecção de URL (`http`/`https`) serve de guard para emitir a
  mensagem correta.
- **Ordem da cascata:** parsing de link ANTES do endereço é crítico. Se o link for enviado
  ao Nominatim como endereço, resulta em None silencioso. Ordem correta: numérico →
  link (regex offline) → endereço (Nominatim, rede).
- **Validação de bounding box do Brasil:** `extract_any_coord` retorna um par bruto.
  Aplicar `_validate_brazil_bbox` (padrão da aba de viabilidade em `pages.py:3062`) antes
  de retornar o resultado para o chamador.
- **Regressão nos caminhos existentes:** coordenada e endereço devem funcionar byte-a-byte
  como antes. Os testes existentes devem continuar verdes sem modificação.
- **Fallback de link inválido/incompleto:** `_render_endereco_fallback_link` só deve ser
  exibido quando NENHUM dos três caminhos resolve. Para links curtos sem Opção B, o
  fallback deve ter texto mais específico (ou uma mensagem separada antes de cair no link
  genérico do Maps).

## Guardrails ativos
- §2 CLAUDE.md: "Não criar dependência de API ao vivo no dashboard de produção." Links
  curtos via redirect = nova dependência de rede → exige emenda à DEC-010 ou DEC nova
  (Opção B). Opção A (URL longa apenas, offline) não expande o desvio já aprovado.
- §5 CLAUDE.md (guardrail permanente de visualização): visualizações não podem recalcular
  ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo,
  plano domínio ou artefatos oficiais do M1 sem aprovação explícita.
- DEC-010 (emenda 2026-06-17): rede SÓ no caminho de resolução de ENDEREÇO da barra de
  busca. Links longos do Maps são parsing offline (regex, sem nova emenda). Links curtos
  são nova expansão e requerem aprovação explícita antes do Builder.
- DEC-004: basemap e tiles online SÓ no caminho de geração do relatório pontual — não
  afetado por este bloco.
- Blocos 4–6: carga lazy por UF, render lazy de abas e fonte de mapa enxuta são contratos
  de performance — INTOCADOS.
