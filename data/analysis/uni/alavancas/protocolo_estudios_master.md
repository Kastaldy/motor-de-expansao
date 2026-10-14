# BLK-UNI-05B, passo 2 — Estúdios × master (exploratório, pós-hoc)

Versão 1.0, 2026-09-29. Escrito antes de rodar. **Pós-hoc e declarado:** nasce do resultado da parte B/C de
`protocolo_alavancas.md`, em que estúdios deram +30% no treino e não se repetiram no teste. No teste, as unidades da
matriz (master ULTRA) não têm estúdio e as do DF/GO têm.

## Pergunta

1. O efeito dos estúdios sobrevive quando se compara só dentro da mesma master?
2. A master, sozinha, melhora a previsão fora da amostra?
3. Estúdios somam alguma coisa à master fora da amostra?

**A master aqui é o campo `master` do painel.** É uma sigla de região do Growth: a DEC-053 registra que uma sigla
cobre até 3 masters diferentes. Ela é um **substituto parcial** do operador, não o operador. O teste do
operador/franqueado fica no estudo paralelo de ICP.

## Dados e modelo

- Treino: as 39 maduras de 2025. Teste: as 18 do UNI-02, com a mesma metragem e o mesmo ajuste de calendário.
- Grupos de master (fixados antes, para não ter grupo de 1 unidade): **DF/GO** (referência), **ULTRA**,
  **RJ/SP 01**, **outros** (PR, ES, SP 02, SP 03).
- Modelos (MQO, faturamento em log):
  - M0;
  - M0 + estúdios;
  - M0 + master;
  - M0 + master + estúdios.
- IC 90% HC3. Estabilidade: sinal dos estúdios ao retirar cada metro.

## Leitura (fixada antes)

- **Q1, no treino:**
  - "**estúdio sobrevive**": o IC de estúdios com a master exclui zero **e** o efeito mantém ≥ 50% do tamanho sem a
    master (em log);
  - "**era a master**": o efeito cai abaixo de 50% **e** o IC cobre zero;
  - senão, "**não distingue**".
- **Q2 e Q3, no teste**, com a regra da parte C:
  - "consistente" se o erro típico cai **e** a ordenação (Spearman) não piora, com e sem Botafogo;
  - Q2 compara M0 + master com M0; Q3 compara M0 + master + estúdios com M0 + master.
- Descritivo: dentro de cada grupo de master, a mediana do erro LOO do M0 nas unidades com e sem estúdio.

## Limites

- N = 39; 4 grupos de master consomem 3 graus de liberdade.
- No teste, a master e os estúdios quase coincidem (ULTRA 0 de 6 com estúdio), então Q3 tem pouca informação.
- É exploratório: não vira entrada da v2 sem nova confirmação.

Arquivos: `alavancas/02_estudios_master.py` → `resultado_estudios_master.md`.

## Versão 1.1 (2026-09-29): master real do cadastro, no lugar da sigla regional do Growth

Pedido do Felipe: usar o nome da master do sistema. Na produção, a master de uma unidade nova é conhecida no contrato.
Fixado antes de rodar.

- **Fonte:** `master_franquia` do cadastro de unidades da VPS (92 unidades; leitura), ligada pelo `cod_cadastro`.
- **Anonimização no servidor:** rótulos M1–M7 pela quantidade de unidades. Nenhum nome é gravado
  (`alavancas/master_id_cadastro.csv`).
- **Unidades fora do cadastro** (7 do treino): recebem a master que predomina na regional do Growth delas, entre as
  unidades já ligadas. Sensibilidade: sem elas.
- **Grupos:**
  - master com ≥ 4 unidades no treino tem grupo próprio; as demais vão para "outras";
  - referência: M1.
  - Checagem só com o X, antes de rodar: M1 = todo o DF/GO, M2 = a matriz (ULTRA), M3 = RJ/SP 01. Espera-se resultado
    próximo ao da v1.0.
- **Q1 a Q3:** as mesmas regras da v1.0. Reporta-se lado a lado com a versão pela sigla regional.
- **Congelamento:** as previsões da turma de 2026 com M0 + master real + estúdios são congeladas em arquivo novo
  (`previsao_2026/previsoes_turma_2026_master_real.csv`), sem tocar no original.

Arquivos: `alavancas/07_estudios_master_real.py` → `resultado_estudios_master_real.md`.

