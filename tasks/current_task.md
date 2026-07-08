# Current Task

## Bloco atual

ID: BLK-RELMUN-05
Nome: Cores otimistas (verde) para aprovados na Visão Geral do Município
Status: APROVADO (QA, veredito final — suíte completa 1536 passed / 2 skipped; única falha ambiental/M2 alheia)
Tipo: manutenção (visual de relatório)
Criticidade: média
Esteira: Block Orchestrator → Planner → [confirmação humana — produto: D1 tons de verde (pré-aprovada)] → Builder → QA
Skill atual: run-cycle
Próxima Skill: Block Orchestrator

## Objetivo
Trocar as cores dos hexágonos APROVADOS na página "Visão Geral do Município" (camada cobertura) e no
Resumo (camada resumo) do relatório municipal de amarelo/laranja para tons de VERDE (otimismo),
mantendo Reprovado em cinza; e atualizar o TEXTO visível que diz "amarelo(s)" para wording neutro
("destacados"), SEM tocar os identificadores (n_hex_amarelos, soma_oferta_amarelos, parcelas_amarelos,
chaves de result). READ-ONLY sobre o M1.

## Gate humano (produto) — D1 PRÉ-APROVADO por Vinicius em 2026-07-08
Verdes: aprovado próprio _COR_APROVADO_PROPRIO = (20,170,80); aprovado fallback municipal
_COR_APROVADO_MUNICIPAL = (90,190,120). _COR_REPROVADO (cinza) inalterado. O Planner só reconfirma;
o orquestrador apresenta ao humano para confirmação rápida antes do Builder.

## Fluxo de branch (integração — decisão de Vinicius 2026-07-08)
- Branch do ciclo: ciclo/BLK-RELMUN-05, ramificada da SECUNDÁRIA integracao/map02-relmun05-06.
- Ao fechar (QA aprovado + commit por path), o orquestrador MERGEIA ciclo/BLK-RELMUN-05 -> integracao/map02-relmun05-06.
- PR para main só após os 3 ciclos (MAP-02 feito; RELMUN-05, RELMUN-06) aprovados e mergeados.

## Tiering de modelo (Passo 4) — Média
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: opus (override +1: armadilha "amarelo" identificador-vs-texto + relatório auditável)
- QA: opus 4.8 (sempre)

## Paths do ciclo (commit por path — NUNCA git add -A)
- src/motor_expansao/dashboard/relatorio_municipal.py
- tests/unit/test_relatorio_municipal.py
- CLAUDE.md (emenda de terminologia na DEC-011: cor verde ≠ critério "destacado")
- tasks/current_task.md, tasks/completed.md, tasks/backlog.md (fechamento)
- context/handoff.md, context/handoff/

## Guardrails
- §5 READ-ONLY M1: zero recálculo/alteração de score/pesos/carteira/plano/artefatos.
- NÃO tocar identificadores com "amarelo" (n_hex_amarelos, soma_oferta_amarelos, parcelas_amarelos,
  chaves de result consumidas por render/testes) — só cores + TEXTO visível mudam.
- NÃO tocar cores de ZONA da página Domínio (:155-160), critério de destaque DEC-011
  (oferta_efetiva_disponivel >= 2000), flag_sam, score.
- Núcleo censo_* / estrutura de páginas / marca d'água / set_compression: intocados.
- §2 acentuação: manter; não acentuar identificadores.
