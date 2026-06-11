# Current Task

## Bloco atual

ID: BLK-EST-02
Nome: Melhorar visual e template dos estudos automatizados
Status: aprovado
Tipo: feature (template/visual)
Criticidade: média
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA das decisões visuais] → Builder → QA
Skill atual: QA (Builder concluído; gate aprovado executado exatamente — D1=B,D2=B,D3=B,D4=B,D5=C,D6=A,D7=C subset,D8=B)
Próxima Skill: QA

## Objetivo
Evoluir o template/visual dos estudos automatizados (Relatório Pontual Censitário, continuação
do BLK-CENSO-02/03): layout mais limpo/profissional mantendo as 7 páginas e o conteúdo Big
Numbers READ-ONLY sobre o M1, com decisões visuais aprovadas por Felipe em gate humano.

## Tiering de modelo (Passo 4) — Média com gate humano de decisões visuais
- Block Orchestrator: sonnet
- Planner: opus  (override +1: design de template/visual em censo_report.py/censo_map.py é
  atipicamente complexo p/ Média — precedente CENSO de muitos footguns + gate humano sobre o output)
- Builder: opus  (override +1: mesma justificativa — edição cirúrgica do template fpdf2 7 páginas)
- QA: opus 4.8 (sempre)

## Gate humano (REVISÃO HUMANA das decisões visuais) — APROVADO por Felipe/usuário em 2026-06-11
Tema recomendado "Ultra Clean / GeoFusion" aprovado EM BLOCO:
- D1=B (tipografia: capa 30pt / banda conteúdo 22pt / Realização 34·18·12; Helvetica, sem TTF)
- D2=B (valor do card em cinza-escuro 40,40,40; rótulo 45,45,45; acento só na barra do topo)
- D3=B (card_h=156, gap=16, barra acento 6pt, valor 26pt, borda fina 225,225,228)
- D4=B (bullets Ultra=turquesa/concorrente=magenta + contagem total + "... e mais N")
- D5=C (logo Ultra no topo da Realização + método em 1 frase; offline-safe c/ fallback gracioso)
- D6=A (títulos de mapa curtos sem prefixo "Relatorio Pontual Censitario -"; manter subtítulo técnico)
- D7=C SUBSET SEGURO (amostras arredondadas radius 4 + separador faixas×pins; NÃO mexer em
  _map_box/legend_x — risco G evitado por decisão explícita)
- D8=B (rodapé enxuto com atribuição CARTO quando drew_basemap=True; escala width 5 + fundo branco)
Builder executa EXATAMENTE estas letras. Troca de fonte TTF fica fora (sub-bloco futuro).

## Branch do ciclo
ciclo/BLK-EST-02 (a partir de ciclo/BLK-MAP-01 @ HEAD)

## Escopo permitido (do backlog)
- src/motor_expansao/dashboard/censo_report.py (template fpdf2, 7 páginas)
- src/motor_expansao/dashboard/censo_map.py (composição de mapa)
- assets de branding em data/ultra/ (gitignored)
- testes correspondentes

## Fora de escopo (invioláveis)
- recalcular qualquer score (score_priorizacao, score_setor_2022_calibrado, residual, SAM)
- método de interseção / raio 1.5 km (setor_censitario_intersecao_area_1p5km INTOCADO)
- PII no PDF (anti-PII §4: .pptx/PDF nunca versionados; image24.png nunca embutido)
- dependência de API ao vivo no dashboard (DEC-004: basemap só na geração do relatório)

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md

dry_run: false
