# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-RELMUN-05 — Cores otimistas (verde) para aprovados na "Visão Geral do Município" (Relatório
Municipal). Troca de paleta de cor (amarelo/laranja → verde) dos hexágonos APROVADOS nas camadas
`cobertura` e `resumo` do relatório municipal, com atualização pontual do texto visível que hoje diz
"amarelo(s)" para wording neutro, sem tocar nos identificadores internos homônimos.

## Objetivo
Recolorir de amarelo/laranja para verde os hexágonos aprovados (2 tons distinguíveis) nas camadas
`cobertura`/`resumo` do PDF do Relatório Municipal, mantendo "Reprovado" em cinza, e atualizar só o
texto visível "amarelo(s)" para um wording neutro — sem alterar critério de destaque, identificadores,
score ou qualquer artefato do M1.

## Escopo permitido
- `src/motor_expansao/dashboard/relatorio_municipal.py:89-91`: trocar os valores RGB de
  `_COR_APROVADO_PROPRIO` (hoje `(255,210,28)` dourado) → verde forte `(20,170,80)` e
  `_COR_APROVADO_MUNICIPAL` (hoje `(245,140,30)` laranja) → verde médio `(90,190,120)` — decisão de
  produto D1, já pré-aprovada por Vinicius em 2026-07-08. Os NOMES das constantes não mudam.
- Propagação automática (sem edição direta necessária, pois derivam das constantes acima; apenas
  conferir/testar): `_HEX_DESTAQUE_RGBA` (:94), `_HEX_DESTAQUE_MUNICIPAL_RGBA` (:95),
  `_HEX_APROVADO_RGBA` (:102), `_HEX_APROVADO_MUNICIPAL_RGBA` (:103), `_COBERTURA_LEGENDA` (:105-109),
  `_RESUMO_LEGENDA` (:111-114) e o choropleth das camadas `cobertura`/`resumo` (uso em :1038, :1044,
  :1100-1101). `_COR_REPROVADO` (:91, cinza `(150,156,170)`) e `_HEX_REPROVADO_RGBA` (:104):
  INALTERADOS.
- Atualizar SOMENTE o TEXTO VISÍVEL (string exibida no PDF) que hoje diz "amarelo(s)" e ficaria
  inconsistente com a nova cor verde:
  - `relatorio_municipal.py:1656` — `"Soma dos hexágonos amarelos / 2.500"` → wording neutro (ex.:
    "hexágonos destacados").
  - `relatorio_municipal.py:2070` — `"Espaço = soma dos hexágonos amarelos / 2.500. "` → idem.
- `tests/unit/test_relatorio_municipal.py`: atualizar asserts de tuplas de cor (RGB) e de texto/labels
  afetados pela troca.
- `CLAUDE.md` — emenda de terminologia na DEC-011 (registrar que a cor visual dos hexágonos aprovados
  passou de amarelo/laranja para verde; o critério de "destacado"
  `oferta_efetiva_disponivel >= 2000` da DEC-011/emenda BLK-RELMUN-03 permanece o mesmo — cor ≠
  critério).
- Fechamento de ciclo: `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md`,
  `context/handoff.md`, `context/handoff/`.

## Fora de escopo
- Qualquer IDENTIFICADOR com "amarelo": `n_hex_amarelos` (:617, :670, :672, :1661),
  `soma_oferta_amarelos` (:616, :673, :1657, :1658), `parcelas_amarelos` (:675, :1657) e as chaves
  homônimas de `result` consumidas por `render`/testes — nomes NÃO mudam, só os valores de cor e o
  texto exibido.
- Ocorrências de "amarelo" em COMENTÁRIOS/docstrings internos (não são texto visível no PDF): linhas
  ~10, ~879, ~882, ~883, ~1070, ~1072, ~1202. Não fazem parte do critério de aceite do backlog (que
  cita só :1656 e :2070); decisão de tocá-los ou não (para evitar drift de documentação interna) fica
  a critério do Planner/Builder, mas NÃO é obrigatório para o fechamento do bloco.
- Cores das 3 ZONAS de domínio (`_ZONA_CORES_PDF`/`_ZONA_CORES_RGBA`, `relatorio_municipal.py:155-161`,
  turquesa/magenta/laranja) — semântica distinta (zonas geométricas de domínio), não mexer.
- Critério de "hexágono destacado" (DEC-011 + emenda BLK-RELMUN-03:
  `oferta_efetiva_disponivel >= 2000`), `flag_sam`, `score_priorizacao`, `hex_score_estrutural`,
  carteira, plano, qualquer artefato oficial do M1.
- Núcleo `censo_*` (`censo_point.py`/`censo_map.py`/`censo_report.py`), estrutura de páginas do PDF
  (ordem/contagem), marca d'água, `set_compression`/`pdf_version`: intocados.
- Qualquer outro bloco do backlog (ex.: BLK-RELMUN-06) — não expandir escopo.

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/relatorio_municipal.py` (completo; focar :89-114, :1030-1105,
  :1650-1665, :2065-2075)
- `tests/unit/test_relatorio_municipal.py`
- `tasks/backlog.md` (seção `### BLK-RELMUN-05`)
- `tasks/current_task.md`
- `CLAUDE.md` §2, §5, DEC-011 (incl. emenda BLK-RELMUN-03)

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/relatorio_municipal.py`
- `tests/unit/test_relatorio_municipal.py`
- `CLAUDE.md` (emenda de terminologia na DEC-011)
- `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md`
- `context/handoff.md`, `context/handoff/`

## Critérios de aceite
- `_COR_APROVADO_PROPRIO == (20, 170, 80)` e `_COR_APROVADO_MUNICIPAL == (90, 190, 120)`;
  `_COR_REPROVADO` inalterado `(150, 156, 170)`.
- PDF municipal renderiza aprovados (camadas `cobertura` e `resumo`) em 2 tons de verde
  distinguíveis entre si e do cinza de reprovado; revisão visual do PDF aprovada.
- Nenhuma menção textual "amarelo(s)" remanescente nas strings exibidas no PDF (mínimo: linhas
  correspondentes a :1656 e :2070 do arquivo original).
- Identificadores `n_hex_amarelos`, `soma_oferta_amarelos`, `parcelas_amarelos` e chaves de `result`
  inalterados (mesmos nomes, mesma lógica de cálculo).
- Critério de destaque (DEC-011: `oferta_efetiva_disponivel >= 2000`), `flag_sam`, score e artefatos
  oficiais do M1 inalterados (nenhum arquivo de `data/staging`/`data/outputs` oficiais tocado).
- `tests/unit/test_relatorio_municipal.py` atualizado (tuplas de cor e/ou labels de texto) e passando.
- `ruff` e `mypy` limpos.
- `CLAUDE.md` recebe emenda de terminologia na DEC-011 registrando a troca de cor (verde) mantendo o
  critério de destaque intocado.
- Suite completa de testes verde (sem regressão fora do escopo).

## Criticidade classificada
Média

## Esteira recomendada
Block Orchestrator → Planner → [confirmação humana rápida — D1 tons de verde, pré-aprovada por
Vinicius em 2026-07-08; Planner só reconfirma] → Builder (model override +1, opus — armadilha
identificador-vs-texto "amarelo") → QA (opus 4.8).

## Riscos identificados
- Tocar por engano um IDENTIFICADOR com "amarelo" (`n_hex_amarelos`, `soma_oferta_amarelos`,
  `parcelas_amarelos` ou chave de `result`) em vez de só cor/texto — quebraria consumidores
  (render/testes) e violaria o guardrail de não-toque em identificadores (§2 análogo).
  Mitigação: grep completo por "amarel" antes e depois da mudança; diff revisado linha a linha.
- Esquecer uma ocorrência de texto visível "amarelo" (além de :1656/:2070) e deixar o PDF
  inconsistente (texto ainda menciona "amarelo" enquanto a cor já é verde). Mitigação: buscar todas
  as ocorrências de "amarelo" no arquivo e classificar cada uma (texto visível vs. identificador vs.
  comentário) antes de editar.
- Alterar por engano as cores de ZONA da página Domínio (`_ZONA_CORES_PDF`/`_ZONA_CORES_RGBA`,
  :155-161) — semântica e escopo diferentes; NÃO fazem parte deste bloco.
- Alterar o critério de "destacado" (DEC-011: `oferta_efetiva_disponivel >= 2000`), `flag_sam` ou
  qualquer cálculo de score ao mexer nas cores — o bloco é estritamente de DISPLAY (cor + texto),
  nunca de lógica/critério.
- Inconsistência de legibilidade: os 2 tons de verde precisam permanecer distinguíveis entre si e do
  cinza de reprovado sobre o basemap claro (revisão visual obrigatória antes de fechar QA).
- Drift de documentação: comentários/docstrings internos que mencionam "amarelo" (fora do escopo
  formal) podem gerar confusão futura se não sinalizados — registrado como nota, não bloqueante.

## Guardrails ativos
- §5 (CLAUDE.md): visualizações, relatórios e interações não podem recalcular ou alterar
  `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou
  artefatos oficiais do M1 sem aprovação explícita. Este bloco é 100% READ-ONLY sobre o M1.
- §2 (CLAUDE.md): não acentuar identificadores; texto voltado ao usuário deve ter acentuação correta
  do português (aplica-se ao novo wording que substitui "amarelo(s)").
- DEC-011 (+ emenda BLK-RELMUN-03): critério de "hexágono destacado" =
  `oferta_efetiva_disponivel >= OFERTA_DESTAQUE_MIN (2000)`; cor de exibição é camada de VISUALIZAÇÃO
  separada do critério — a emenda deste bloco deve deixar essa separação explícita no CLAUDE.md.
- Núcleo `censo_*`/estrutura de páginas/marca d'água/`set_compression`: intocados (herdado de
  DEC-011/BLK-RELMUN-01/03).
