/* ---------------------------------------------------------------------------
   Mapeia o resultado da Viabilidade (ViabilidadeOut) para o CONTRATO do gerador
   de PDF do Relatorio Pontual — `censo_report._viabilidade_page` (Python).

   Puro e TESTADO de proposito: o gerador le CHAVES e UNIDADES especificas; mandar
   a chave errada (ou a unidade errada) faz o slide de viabilidade vir vazio ("n/d")
   sem erro nenhum — foi exatamente o bug corrigido em 2026-07-22 (o front mandava
   `margem`/`ebitda`/`faturamento`, o gerador le `margem_ebitda_pct`/`ebitda_mensal`/
   `faturamento_mensal`, alem de nem enviar payback/roic/faixa).
   --------------------------------------------------------------------------- */
import type { ViabilidadeOut } from './types'

/**
 * Dict serializavel esperado por `_viabilidade_page`:
 *   alunos_breakeven, aluguel_teto (R$), margem_ebitda_pct (FRACAO), payback_meses,
 *   roic_anual (FRACAO), faturamento_mensal (R$), ebitda_mensal (R$), faixa_p10/p90,
 *   flag_viavel, flag_fora_envelope.
 *
 * UNIDADES (atencao): `dre.margem` vem em PERCENTUAL do backend, mas o gerador faz
 * `frac * 100` -> aqui divide por 100. `dre.roic` ja e fracao (envia direto).
 */
export function viabilidadeParaPdf(res: ViabilidadeOut): Record<string, unknown> {
  const pctToFrac = (v: number | null) => (v == null ? null : v / 100)
  return {
    alunos_breakeven: res.alunos_breakeven,
    aluguel_teto: res.aluguel_teto?.teto ?? null, // cluster "Teto" (20% do faturamento)
    margem_ebitda_pct: pctToFrac(res.dre.margem),
    payback_meses: res.dre.payback,
    roic_anual: res.dre.roic,
    faturamento_mensal: res.dre.faturamento,
    ebitda_mensal: res.dre.ebitda,
    faixa_p10: res.faixa_alunos?.p10 ?? null,
    faixa_p90: res.faixa_alunos?.p90 ?? null,
    flag_viavel: res.dre.flag_viavel ?? false,
    flag_fora_envelope: res.flag_fora_envelope,
  }
}
