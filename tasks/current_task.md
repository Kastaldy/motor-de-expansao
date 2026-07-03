# Current Task

## Bloco atual

ID: BLK-TP-06-FU2
Nome: Candidato C do residual — decay 2 km nas academias de bairro + capacidade de CLUBE real por rede
Status: aprovado
Tipo: modelagem (validação/seleção de candidato — READ-ONLY sobre o M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA — modelagem + anti-PII data/validacao] → Builder → QA
Skill atual: QA concluído (APROVADO)
Próxima Skill: Fechamento manual (orquestrador: completed.md + commit por path; decidir TP-09 conforme materialidade)

## Veredito do QA (2026-07-03) — APROVADO
Medição HONESTA e REPRODUZÍVEL. Reproduzi byte-a-byte sobre os parquets + data/validacao REAIS:
baseline R²_oof=+0.3119 (rho +0.4615, n=16411); C1 Δ pareado completo +0.0019 [+0.0015,+0.0023] /
fora +0.0013 [+0.0007,+0.0019] → APLICAR_C1 (passa (D)); C2 Δ −0.0312 / −0.0120 → NAO_APLICAR_C2;
A Δ −0.0427 / −0.0193 → NAO_APLICAR. Leitor anti-PII REAL = {'smart_fit':2363.0,'engenharia_do_corpo':3106.5},
Sky 944.5. Suíte full: 1316 passed, 1 skipped, 0 failed. ruff+mypy limpos; import ok; isolamento AST ok;
mtime dos 4 oficiais M1 + hexagonos_mercado_mapeado.parquet INALTERADO; calcular_colunas_mercado.py intocado;
relatório gitignored sem PII; k-ring conserva massa (1000, não 4000); decay 2 km correto; DEC-008 sem
campo in-sample. MATERIALIDADE DO C1 = ruído-significante-por-N-grande (C1==baseline em 97.3% dos hexes;
ganho +0.002 na 2ª casa) → recomendação ao BLK-TP-09: NÃO aplicar C1; C2 NO-GO; residual segue como está.
Detalhes em context/handoff.md e context/handoff/20260703-141528-qa.md.

## Resultado do Builder (2026-07-03)
Baseline reproduzido byte-a-byte (R²_oof=+0,3119, rho_oof=+0,4615, n=16.411). VEREDITO REAL
out-of-fold: **C1 = APLICAR_C1** (Δ pareado completo +0,0019 IC95[+0,0015,+0,0023]; fora +0,0013
IC95[+0,0007,+0,0019] — vence os 2, mas ganho DESPREZÍVEL ~+0,002 de R²; recomendação honesta ao
BLK-TP-09 = NÃO aplicar). **C2 = NAO_APLICAR_C2** (Δ completo −0,0312; fora −0,0120 — piora, repete
o padrão do A). Veredito consolidado: `NAO_APLICAR_A; APLICAR_C1; NAO_APLICAR_C2`. Capacidade real
(anti-PII, só `{rede:float}`): smart_fit=2363,0 / engenharia_do_corpo=3106,5; Sky âncora ~944,5;
fallback 2.500 nas 26 redes restantes. Validação: 304 passed / 0 failed / 0 skipped (demanda_revelada
+ streamlit); ruff+mypy limpos; import ok; mtime dos 4 oficiais M1 + hexagonos_mercado_mapeado
INALTERADO. READ-ONLY M1. Detalhes em context/handoff.md e context/handoff/20260703-120223-builder.md.
Gate: DECISÃO AUTÔNOMA do orquestrador em 2026-07-02 (usuário delegou explicitamente os gates desta sessão) — A–E = recomendações do Planner: (A) capacidade real Smart ~2.370 / Engenharia ~3.106, fallback 2.500 p/ ~26 redes, Sky só âncora; (B) decay bairro k=1 ponderado por anel (1,0/0,5) com normalização Σ=4,0 (conserva massa); (C) rodar C1 e C2; (D) vence = IC95 Δ pareado sem cruzar zero no completo E fora de SP/MG/RJ; (E) leitor validacao anti-PII em módulo irmão. Se C1/C2 = GO → encadear BLK-TP-09 (DEC + regen mercado/residual, M1 oficial intocado).

## Objetivo
Rodar o Candidato C (adiado no FU1) BEM-FEITO, corrigindo as 2 crudezas do Candidato A (que deu NO-GO):
1. aplicar o **decay de ~2 km** também às academias de bairro (consistente com a oferta consumida mapeada),
   não somar contagem crua flat por hex;
2. ponderar a oferta consumida por **capacidade de CLUBE real por rede**, lida de `data/validacao/`
   (`KPIs_Smart_2025_02 (1).xlsx` = Smart Fit, `Sky Fit dados.xlsx` = SkyFit, `academias_engenharia_do_corpo.xlsx`
   = Engenharia), NÃO as medianas ~340 de footprint de bairro do BLK-TP-08-FU.
Validar out-of-fold vs baseline (mesmo harness do TP-06/FU1: k-fold 5×5 seed=42, IC95 bootstrap, R²
in-sample banido, Δ pareado, 3 recortes). Decide honestamente se o Candidato C VENCE o baseline (+0,3119) e
sobrevive fora de SP/MG/RJ. READ-ONLY sobre o M1. Distingue "hipótese errada" de "execução crua".

## Contexto (do FU1, mergeado)
- Candidato A (FU1) = NO-GO: somar as bairro cru como oferta consumida PIORA (Δ pareado completo −0,0427;
  fora −0,0193). Causas: (a) co-localização bairro↔demanda; (b) crudeza (contagem crua, sem decay, sem
  capacidade por rede). O FU2 ataca (b) para separar de (a).
- Módulo a ESTENDER: `src/motor_expansao/demanda_revelada/revalidacao_residual_candidatos.py` (baseline +
  Candidato A; dedup fino isolado em `alunos_menores_add_por_hex`; estrutura já deixada extensível para C).
- Baseline (residual atual): rho_oof +0,4615, R²_oof +0,3119 (n=16.411) — sinal sólido; o alvo é superá-lo.

## RESTRIÇÃO DE DADO a resolver no gate (o BO/Planner devem medir)
- As academias de bairro estão AGREGADAS por hex (coords dropadas no anti-PII do TP-08) → um decay de 2 km
  POINT-level exato não é possível para elas. Avaliar aproximação por VIZINHANÇA DE HEXES (H3 k-ring; res-7
  ≈ 1,2 km/hex, k=1 ≈ ~2,5 km) como proxy do raio de 2 km. Os concorrentes mapeados TÊM coords/hex.
- `data/validacao/` dá capacidade de clube real para ~3 redes (Smart/Sky/Engenharia); as demais ~25 redes de
  `concorrentes_mapeados` precisam de fallback declarado (2.500 atual, ou medianas de bairro só p/ as pequenas).

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: opus (override +1: forense anti-PII de data/validacao real + viabilidade do decay em dado hex-agregado)
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-TP-06-FU2 (criada a partir de main @ HEAD 33e5160).

## Bloco ad-hoc
Derivado da conversa. Fechamento: Passo 6.0 no-op (ad-hoc) → resumo a completed.md via 6.2; atualizar o
BLK-TP-09 no backlog conforme o veredito do C.

## Guardrails
- §5 (READ-ONLY M1): zero recálculo de score/pesos/carteira/plano/artefatos oficiais; NÃO alterar a fórmula
  do residual em produção nem regenerar `hexagonos_mercado_mapeado.parquet`. Candidato C só EM MEMÓRIA/relatório.
- DEC-008: out-of-fold vs baseline; R² in-sample BANIDO; IC95 seed=42; Δ pareado; NO-GO é válido.
- DEC-009: demanda (`membros`) é ALVO OBSERVADO; nunca preditor geográfico de magnitude.
- DEC-012 (anti-PII): `data/validacao/` são DADOS REAIS (gitignored) — agregar a capacidade POR REDE na
  fronteira e DESCARTAR qualquer PII (nome de unidade/endereço/coord); zero PII em artefato/log/teste;
  fixtures sintéticas; nunca versionar a fonte real.
- Isolamento: módulo NÃO importa de pipelines/m1, dashboard, censo_*, api.
