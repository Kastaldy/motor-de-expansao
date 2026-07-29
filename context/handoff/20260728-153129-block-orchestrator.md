# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-RELPON-14 — Círculo azul de 1,5 km nos mapas de escala 5 km (enquadramento INTOCADO).**
Nos dois painéis de hexágono do Relatório Pontual (`socioeconomia` e `residual`, ambos gerados por
`_render_camada_residual_hex`), o círculo azul desenhado hoje herda o mesmo raio do enquadramento
(5 km) porque os dois usam a MESMA constante `RAIO_RESIDUAL_DISPLAY_KM`. O pedido é desacoplar: o
círculo passa a 1,5 km, o enquadramento (extensão do mapa) continua em 5 km.

## Objetivo
Desacoplar, em `_render_camada_residual_hex` (`censo_map.py:1008-1125`), o raio do círculo desenhado
(vira 1,5 km) do raio de enquadramento do mapa (permanece 5 km, `RAIO_RESIDUAL_DISPLAY_KM`), sem tocar
motor censitário, `config.py`, `_RESIDUAL_GRID_DISK_K` nem artefatos do M1.

## Escopo permitido
- `src/motor_expansao/dashboard/censo_map.py`: introduzir uma constante de RENDER nova para o raio do
  círculo (`censo_map.py:1048`, hoje `Point(0, 0).buffer(RAIO_RESIDUAL_DISPLAY_KM * 1000.0, ...)`),
  mantendo `frame_metric = _frame_box_metric(RAIO_RESIDUAL_DISPLAY_KM, ...)` (`censo_map.py:1047`)
  intocado.
- Resolver **D2** (rótulo do rodapé) e, se necessário em decorrência de D2, ajustar o texto de
  título/subtítulo (**D3**) das camadas `socioeconomia` (`censo_map.py:1521-1539`, título
  `"Socioeconomia - raio 5 km"`) e `residual` (`censo_map.py:1545-1556`, título default
  `"Residual Fitness - raio 5 km"`, `censo_map.py:1021`).
- `tests/unit/test_relatorio_pontual_censitario_mapa.py`: adicionar teste novo que trava
  geometricamente o raio do círculo em 1,5 km (ex.: contagem de pixel do círculo azul, no padrão do
  helper `_conta_pixels_do_circulo`, L1149-1153) e atualizar os 2 testes que hoje hardcodam
  `"Raio 5,0 km"` para as camadas de 5 km (ver Riscos).
- `docs/relatorio_pontual_censitario.md` (§6/§7): atualizar a descrição do rodapé/título das camadas
  `socioeconomia`/`residual` se o texto mudar (D2/D3), para não repetir a dívida de doc-stale que o
  BLK-RELPON-12 já teve que pagar nesta mesma família.

## Fora de escopo
- Motor censitário (`setor_censitario_intersecao_area_1p5km`, `RAIO_CENSITARIO_DEFAULT_KM = 1,5`,
  `censo_point.py:23`) — INTOCADO.
- Enquadramento de 5 km (`RAIO_RESIDUAL_DISPLAY_KM`, `frame_metric`/`frame_3857`) — INTOCADO; é o que
  alimenta o clip dos hexes (ver evidência abaixo), não pode mudar.
- `_RESIDUAL_GRID_DISK_K = 5` (disco de hexes candidatos) — INTOCADO.
- Camadas `densidade`/`renda`/`score`/`renda_domiciliar`/`concorrentes`/`entorno` — permanecem
  byte-idênticas; nenhuma delas passa por `_render_camada_residual_hex`.
- Qualquer coisa em `config.py`, `src/motor_expansao/pipelines/m1/`, scoring ou artefatos oficiais
  (READ-ONLY M1).
- `pages.py`/`api/service.py`: não chamam `_render_camada_residual_hex` nem `RAIO_RESIDUAL_DISPLAY_KM`
  (confirmado por grep em todo `src/`) — não há alcance fora de `censo_map.py`.

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/censo_map.py` (arquivo grande; focos: L40-145 constantes de RENDER,
  L676-882 `_render_camada`, L898-1126 `_render_camada_residual_hex`+helpers, L1200-1260
  `render_mapas_censitarios_combinados` docstring, L1506-1559 montagem do dict `mapas`).
- `tests/unit/test_relatorio_pontual_censitario_mapa.py` (focos: L700-1020 camadas residual/
  socioeconomia + travas de raio de exibição, L922-949 e L826-858 — os 2 testes que quebram, L1149-1225
  helpers de pixel do círculo e testes do `entorno`).
- `docs/relatorio_pontual_censitario.md` (§6, "Mapa do relatório" — contrato canônico da camada,
  parágrafos sobre `RAIO_RESIDUAL_DISPLAY_KM`, `_render_camada_residual_hex`, rodapé "no raio").
- `src/motor_expansao/dashboard/censo_point.py:23` (`RAIO_CENSITARIO_DEFAULT_KM = 1.5`, para decidir D1
  com o valor real à vista, não de memória).
- `tasks/backlog.md` (seção `### BLK-RELPON-14`, linhas 239-322) — diagnóstico original, já em grande
  parte confirmado nesta rodada (ver Riscos/evidência).

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/censo_map.py`
- `tests/unit/test_relatorio_pontual_censitario_mapa.py`
- `docs/relatorio_pontual_censitario.md` (se D2/D3 mudarem texto renderizado)

## Critérios de aceite
- Nos dois painéis de hexágono (`socioeconomia` e `residual`), o círculo azul tem 1,5 km e o
  enquadramento continua cobrindo 5 km — verificado por teste geométrico (pixel/raio), não a olho.
- `censo_map.RAIO_RESIDUAL_DISPLAY_KM == 5.0` preservado; `_frame_box_metric` recebe-o inalterado —
  `tests/unit/test_relatorio_pontual_censitario_mapa.py:1004,1016` não podem quebrar.
- Teste novo amarrando o raio do círculo desenhado à constante nova (1,5 km), para a regressão não
  voltar em silêncio.
- Rótulo do rodapé coerente com o que está desenhado, conforme a decisão de D2 (Vinicius).
- `/Count` do PDF e as demais páginas inalterados; nenhuma constante de motor tocada
  (padrão `assert not hasattr(config, ...)` das linhas 1017/1216 do mesmo teste).
- `ruff`/`mypy` limpos; suíte relevante verde (rodar SERIAL — `pytest -n auto` está quebrado nesta
  máquina, BLK-QA-XDIST-01).
- Gate visual humano de Vinicius antes do merge (comparar PDF antes/depois no mesmo ponto).

## Criticidade classificada
Média — **confirmada**, não Alta. Justificativa: é mudança puramente de RENDER, sem introduzir
geometria nova no caminho (h3 já é usado por `censo_map.py` desde o BLK-RELPON-10/13) e sem reverter
nenhuma decisão de produto já aprovada — ao contrário do BLK-RELPON-10 (Alta: introduziu h3 pela
primeira vez no render + revertia o BLK-CENSO-02) e do BLK-RELPON-13 (Alta: mudança visual equivalente
ao 10). O precedente mais próximo em natureza é o **BLK-RELPON-09** (Média: "display local nos dois
PDFs; sem rede, sem dado novo, sem DEC"), que se encaixa melhor neste bloco: aqui não há rede nova, não
há dado novo, não há DEC. READ-ONLY M1 mantido (só leitura de `oferta_efetiva_disponivel`/
`score_setor_2022_calibrado`, já lidas hoje).

## Esteira recomendada
Block Orchestrator → Planner → Builder (resolve D1 sozinho com a recomendação abaixo; D2/D3 precisam de
decisão de Vinicius antes ou durante o Builder — não decidir sozinho) → QA → **Gate visual humano de
Vinicius antes do merge** (critério de aceite #7 do backlog). Não loop-safe (confirmado): a validação
final é visual, o loop não julga aparência — mesmo que o RAIO em si seja testável geometricamente.

## Riscos identificados
- **Dois testes existentes vão quebrar por construção, não por acidente**, e o Planner precisa prever
  a atualização deles como parte do trabalho (não é regressão a evitar, é edição esperada, condicionada
  à decisão de D2):
  - `test_rodape_do_png_deriva_do_raio_km_1p5_identico_e_5p0_novo`
    (`tests/unit/test_relatorio_pontual_censitario_mapa.py:922-949`) — hoje afirma
    `"Raio 5,0 km - EPSG:3857 - fundo de ruas offline" in textos` para as camadas de 5 km.
  - `test_socioeconomia_e_hexagono_nao_setor_a_5km`
    (`tests/unit/test_relatorio_pontual_censitario_mapa.py:826-858`) — mesma asserção na linha 856.
- **Testes que NÃO podem quebrar** (travam o enquadramento, que fica intocado):
  `test_frame_box_metric_puro_reproduz_o_calculo_do_caller` (L992-1006) e
  `test_raio_de_exibicao_nao_toca_o_raio_do_motor` (L1009-1018, também trava
  `_RESIDUAL_GRID_DISK_K == 5`).
- **Doc desatualiza junto:** `docs/relatorio_pontual_censitario.md` §6/§7 cita "Raio 5,0 km" como
  comportamento das camadas `socioeconomia`/`residual` em pelo menos 2 parágrafos — se o texto mudar,
  a doc precisa acompanhar no mesmo PR (a família RELPON já pagou essa dívida uma vez no BLK-RELPON-12,
  não repetir).
- **D2 sem decisão trava o Builder**: as 3 alternativas de rótulo têm textos exatos diferentes — ver
  seção de evidência abaixo. Preparar a pergunta para Vinicius, não escolher por ele.
- Risco baixo de regressão colateral: `n_setores=len(hex_records)` (`censo_map.py:1113`) conta hexes
  recortados pelo FRAME (5 km), não pelo círculo — não muda com este bloco, mas vale confirmar no PR
  que nenhum teste presume que `n_setores` reflete o círculo.

## Guardrails ativos
- READ-ONLY sobre o M1: nenhuma edição em `config.py`, `src/motor_expansao/pipelines/m1/`, scoring ou
  artefatos oficiais (`score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano
  domínio).
- Motor censitário (`setor_censitario_intersecao_area_1p5km`, `RAIO_CENSITARIO_DEFAULT_KM`) INTOCADO —
  camada READ-ONLY sobre o M1.
- Acentuação correta em texto de usuário (rótulo do rodapé/título), exceto pela exceção de RENDER já
  documentada em `censo_map.py:137-139`: o font embutido do Pillow usado no PNG não tem glifo
  acentuado — textos desses mapas são ASCII puro por construção (não regredir essa exceção, mas também
  não confundi-la com a regra geral de acentuação).
- Guardrail permanente do CLAUDE.md §5: visualizações/render não podem recalcular ou alterar
  `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano domínio ou artefatos
  oficiais do M1 sem aprovação explícita — este bloco não toca nenhum desses.

---

## Evidência levantada nesta rodada (para o Planner não precisar re-medir)

### 1) O `circle_metric` de 5 km participa de recorte de DADO? NÃO — confirmado, não hipótese.
Em `_render_camada_residual_hex` (`censo_map.py:1008-1125`):
- `frame_metric = _frame_box_metric(RAIO_RESIDUAL_DISPLAY_KM, width, height)` (L1047) →
  `frame_3857 = _project_geometry(frame_metric, to_3857_local)` (L1058) → passado a
  `_hex_polygons_3857(lat, lng, hexes_df, frame_3857, to_3857_wgs, value_col=value_col)` (L1062-1064),
  que faz `Polygon(coords).intersection(frame_3857)` (L963) para recortar cada hex — **o clip de dado é
  pelo FRAME (retângulo)**, não pelo círculo.
- `circle_metric = Point(0, 0).buffer(RAIO_RESIDUAL_DISPLAY_KM * 1000.0, quad_segs=96)` (L1048) →
  `circle_3857 = _project_geometry(circle_metric, to_3857_local)` (L1059) → passado como
  `circle_3857=circle_3857` a `_render_camada` (L1098). Dentro de `_render_camada`, `circle_3857` só é
  lido em UM lugar: `censo_map.py:824-831`, para desenhar a linha azul (`draw.line(...)`). Não entra em
  `bounds` (que vem separadamente de `bounds=frame_3857.bounds`, L1109) nem em nenhum filtro de
  `sector_records_3857`/`source_values`. Confirmado por grep: as únicas ocorrências de `circle_3857` no
  arquivo são declaração de tipo (L683), o desenho (L824-827), e as 3 construções/passagens
  (L1059/1098, L1181/L1310/L1412 nos outros caminhos). Nenhuma altera dado.
- Conclusão: o desacoplamento é seguro — mudar só `circle_metric` (L1048) para uma constante nova de
  1,5 km, mantendo `frame_metric`/`RAIO_RESIDUAL_DISPLAY_KM` (L1047) como está, não risca nenhum dado
  exibido (hexes, valor central, contagem).

### 2) Alcance real: confirmado DOIS painéis, nenhum outro chamador.
`_render_camada_residual_hex` é chamada em exatamente 2 lugares em todo `src/` (grep confirmou): a
`socioeconomia_png` (`censo_map.py:1521`, `value_col="score_setor_2022_calibrado"`) e a `residual_png`
(`censo_map.py:1545`, default `value_col="oferta_efetiva_disponivel"`), ambas dentro de
`render_mapas_censitarios_combinados` no mesmo arquivo. Nem `pages.py` nem `api/service.py` a chamam ou
referenciam `RAIO_RESIDUAL_DISPLAY_KM`. A correção vale para as duas automaticamente, por construção
(mesma função).

### 3) D1 — recomendação: constante de RENDER NOVA, não reuso de `RAIO_CENSITARIO_DEFAULT_KM`.
O padrão já estabelecido no arquivo (comentários L115-134) é: todo raio de EXIBIÇÃO ganha sua PRÓPRIA
constante em `censo_map.py`, explicitamente fora de `config.py`/§3 do CLAUDE.md, mesmo quando o valor
coincide numericamente com um parâmetro de motor —
`RAIO_RESIDUAL_DISPLAY_KM = 5.0` (L120, comentário "NÃO é parâmetro de motor... não entra em
config.py") e `RAIO_ENTORNO_DISPLAY_KM = 0.14` (L135, mesmo padrão) já seguem essa regra. Reusar
`RAIO_CENSITARIO_DEFAULT_KM` (import de `censo_point.py:23`) importaria um símbolo do MOTOR para dentro
da composição de RENDER — quebra a separação que o próprio arquivo pratica, mesmo que hoje o valor seja
igual (1,5 km == 1,5 km, coincidência, não garantia futura). **Recomendação: constante nova**, por
exemplo `RAIO_CIRCULO_DISPLAY_KM = 1.5` (nome sugestivo do backlog), com um teste-espelho no padrão de
`test_raio_de_exibicao_nao_toca_o_raio_do_motor` (`==` contra `RAIO_CENSITARIO_DEFAULT_KM`, só para
rastreabilidade/documentação, SEM criar dependência de import em runtime).

### 4) D2 — alternativas com texto EXATO (decisão de produto, não decidida aqui).
Rodapé hoje (offline): `f"{prefixo} - EPSG:3857 - fundo de ruas offline"` — online troca o fim por
`_ATRIBUICAO_TILES = "(c) OpenStreetMap, (c) CARTO"`. `prefixo` hoje = `f"Raio {raio_txt} km"` com
`raio_txt` de `RAIO_RESIDUAL_DISPLAY_KM` → **hoje**: `"Raio 5,0 km - EPSG:3857 - fundo de ruas
offline"` (47 caracteres).
- **(a)** `prefixo = "Raio 1,5 km"` → `"Raio 1,5 km - EPSG:3857 - fundo de ruas offline"`
  (47 caracteres, MESMO tamanho de hoje). Descreve o círculo; perde a informação de que o mapa cobre
  5 km.
- **(b)** `prefixo = "Raio 1,5 km - escala 5 km"` → `"Raio 1,5 km - escala 5 km - EPSG:3857 - fundo de
  ruas offline"` (61 caracteres, +14 vs hoje). Honesto nas duas dimensões, ocupa mais espaço no rodapé
  (fonte `_FS_FOOTER=22px`, linha em `(28, height-34)` — não há teste de overflow para o rodapé hoje,
  ao contrário da legenda que tem `test_rotulo_mais_longo_da_legenda_cabe_na_coluna`; se (b) for
  escolhida, vale um teste equivalente de "cabe no canvas").
- **(c)** mecanismo, não texto fixo: reusar o parâmetro `rotulo_escala=` que `_render_camada` já aceita
  (`censo_map.py:700`, hoje usado só pela camada `entorno` com `_ENTORNO_ROTULO_ESCALA = "Escala de
  quadra"`, `censo_map.py:1196`) para injetar QUALQUER string custom — poderia carregar o texto de (a),
  de (b), ou uma redação nova (ex.: `"Circulo 1,5 km (mapa 5 km)"`), sem precisar derivar de `raio_km`.
  Vantagem: não mexe no cálculo de `raio_txt`/`prefixo` para as outras camadas (1,5 km), reusa caminho
  já testado pelo `entorno`.
- **Pergunta pronta para Vinicius:** "O rodapé das camadas Socioeconomia/Residual (hoje 'Raio 5,0 km')
  deve virar (a) 'Raio 1,5 km' [perde a info de 5 km], (b) 'Raio 1,5 km - escala 5 km' [mais longo, mas
  honesto nas duas escalas], ou (c) outra redação livre via o mesmo mecanismo que a camada Entorno já
  usa ('Escala de quadra')?"

### 5) D3 — título/legenda da camada residual e coerência.
Os títulos são hardcoded ASCII: `"Socioeconomia - raio 5 km"` (`censo_map.py:1533`) e
`"Residual Fitness - raio 5 km"` (default em `censo_map.py:1021`). Ambos descrevem corretamente o
ENQUADRAMENTO (que fica em 5 km, INTOCADO) — nesse sentido continuam tecnicamente coerentes. Risco de
percepção: depois da mudança, um leitor pode olhar o título "raio 5 km" e o círculo azul visivelmente
menor (1,5 km) e ler como contradição, mesmo sem ser uma (o título fala do mapa, o círculo é uma
referência visual auxiliar). Não há necessidade técnica de mudar o título junto com D1, mas é a MESMA
decisão de produto de D2 — recomendo apresentar as duas juntas a Vinicius no mesmo gate, não como itens
separados.

### 6) Constantes/variáveis confirmadas (para não precisar re-grep):
- `RAIO_RESIDUAL_DISPLAY_KM = 5.0` — `censo_map.py:120`.
- `RAIO_CENSITARIO_DEFAULT_KM = 1.5` — `censo_point.py:23` (motor, INTOCADO).
- `_RESIDUAL_GRID_DISK_K = 5` — `censo_map.py:126` (INTOCADO).
- `_CIRCLE_RGBA = (0, 102, 255, 235)` — `censo_map.py:59` (cor do círculo, INTOCADA).
- Helper de teste reutilizável para travar o raio do círculo: `_conta_pixels_do_circulo`
  (`tests/unit/test_relatorio_pontual_censitario_mapa.py:1149-1153`), já usado por
  `test_camada_entorno_nao_desenha_o_circulo_do_raio` (L1156-1164) para provar ausência/presença de
  círculo por contagem de pixel azul — o mesmo padrão serve para provar TAMANHO (comparar área/raio do
  círculo azul entre a versão antiga simulada com raio 5 km e a nova com 1,5 km, ou medir o raio em
  pixels e comparar à razão esperada 1,5/5,0 do frame).
