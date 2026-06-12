# Current Task

## Bloco atual

ID: BLK-EST-02-FU1
Nome: Remover logo Ultra atrás do texto "Realizacao" (página de crédito do PDF)
Status: Builder concluído; aguardando verificação do orquestrador (render PDF + suíte full)
Tipo: bug (UX/UI — PDF, ajuste visual)
Criticidade: baixa
Esteira: Block Orchestrator → Builder
Skill atual: Builder (concluído)
Próxima Skill: Orquestrador (verificação de render + suíte full + fechamento)

## Objetivo
Na página 7 (Realização/Crédito) do PDF, o logo Ultra é desenhado no topo e o texto "Realizacao" cai
POR CIMA da parte de baixo do logo (colidem; o logo fica "atrás do texto"). Pedido de Felipe/Vini:
REMOVER o logo Ultra dessa página. READ-ONLY M1; só `censo_report.py`; o texto "Realizacao" e o crédito
permanecem.

## Diagnóstico (render real verificado pelo orquestrador)
- `_credit_page` (censo_report.py ~529-555): desenha fundo turquesa, depois o LOGO Ultra
  (`pdf.image(BytesIO(logo), x=(_PAGE_W-160)/2, y=90, w=160)`, bloco D5=C linhas ~539-545), depois o
  título "Realizacao" (`set_xy(40,180)`, 34pt) e o crédito.
- O logo (y=90, w=160) e o "Realizacao" (y=180) se sobrepõem visualmente → logo atrás do texto.
- Nenhum teste depende do logo na página de crédito (grep confirmou).

## Correção
- Remover o bloco D5=C do logo em `_credit_page` (as linhas `logo = assets.get("logo")` + `if logo is not
  None: try: pdf.image(...) except: pass` + o comentário D5). Manter o fundo turquesa, o título "Realizacao"
  e o crédito. Atualizar o comentário/docstring se mencionar o logo.
- NÃO mexer no texto, no crédito, nem em outras páginas/assets (o logo segue sendo carregado por
  `_load_branding_assets` e pode ser usado em outro lugar — só remover o DESENHO na página de crédito).

## Verificação
- Orquestrador renderiza a página 7 e confirma que o logo Ultra sumiu e que "Realizacao" + crédito ficam
  limpos sobre o turquesa. Roda a suíte do relatório + full.

## Tiering de modelo — Baixa
- Block Orchestrator: haiku
- Builder: sonnet
- (Baixa: sem Planner/QA; orquestrador faz a verificação de render + suíte)

## Branch do ciclo
ciclo/BLK-EST-01-FU2 (MESMA branch do PR em montagem — o fix entra no mesmo PR; commit por path)

## Escopo permitido
- src/motor_expansao/dashboard/censo_report.py — só o bloco do logo em `_credit_page`

## Fora de escopo (invioláveis)
- recalcular qualquer score ou artefato M1
- mexer no texto "Realizacao"/crédito/`solicitante`/marca d'água
- remover o carregamento do asset `logo` (só o desenho na página de crédito)
- alterar outras páginas/template/mapas

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md

dry_run: false
