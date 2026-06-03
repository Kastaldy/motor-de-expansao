# Current Task

## Bloco atual

ID: BLK-FIX-06-B
Nome: Geração de candidatos H3 por overlap (recupera a orla povoada de verdade)
Status: aprovado (QA verde; oficiais regenerados no limiar 0.05 / DEC-003)
Tipo: bug (correção do BLK-FIX-06; toca base M1 → regenera artefatos oficiais)
Criticidade: crítica
Esteira: Fix → Medição (scratch) → [aprovação humana + DEC-003] → Regeneração → QA → Deploy
Skill atual: run-cycle (fechamento: commit por path → merge/push → CI → redeploy VPS)
Próxima Skill: commit/merge/push/CI + redeploy de parquets ao VPS
dry_run: false
Resultado: limiar 0.20→0.05 (DEC-003); universo 1.538.424→1.542.531 (+4.107 hexes costeiros, 23 UFs); impacto no score ~nulo (máx 0.02); QA 656 passed/1 skipped; ruff+mypy limpos; Mongaguá+PG-Mongaguá recuperados.

## Objetivo
Corrigir o defeito do BLK-FIX-06: a geração de candidatos usa `h3.geo_to_cells` (containment por CENTRO), que nunca produz os hexes da orla cujo centroide cai no mar — então o filtro de fração-de-terra nunca os avalia. Trocar para containment `overlap` (h3 4.4.2) para que a orla povoada (≥ M1_HEX_LAND_FRACTION_MIN de terra) seja de fato recuperada. Medir o impacto ANTES de regenerar/redeploy (DEC-003).

## Causa-raiz (provada)
- `gerar_hexagonos_validos_uf` (base_h3_brasil.py:218): `h3.geo_to_cells(UF)` = polyfill por centro → orla de centro-no-mar nunca é candidata.
- Prova: orla de Mongaguá `87a810998ffffff` tem fração_terra=0.218 (≥0.20) mas está AUSENTE; não é candidata de `geo_to_cells(SP)`; centro fora do polígono de SP/Brasil.
- Os "+474" do BLK-FIX-06 eram só casos de borda entre malhas UF/Brasil, não a orla.

## Fix
- `_gerar_candidatos_uf`: usa `h3.h3shape_to_cells_experimental(geo_to_h3shape(UF), res, "overlap")` (fallback robusto: centro + grid_disk k=1). Resto do critério (fração-de-terra ≥ limiar) inalterado.

## Paths do ciclo
- src/motor_expansao/pipelines/m1/base_h3_brasil.py (geração de candidatos)
- tests/integration/test_base_h3_brasil.py (teste do overlap)
- scripts/medir_impacto_litoral_blk_fix_06b.py (medição scratch)
- data/reports/base_h3_litoral_impacto_06b.md (relatório DEC-003)
- CLAUDE.md §8 (DEC-003) + §5 — após aprovação
- artefatos M1 oficiais — regenerados após DEC-003
- deploy: sync parquets ao VPS após regeneração

## Observação
Deploy anterior (BLK-FIX-06, +474) permanece live (correto, porém incompleto). Backup em VPS `outputs_bak_blkfix06`. Este ciclo regenera por cima e redeploya.
