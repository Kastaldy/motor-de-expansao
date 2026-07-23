/* ---------------------------------------------------------------------------
   Mapeia o resultado da Viabilidade (ViabilidadeOut) para o CONTRATO do gerador
   de PDF do Relatorio Pontual — `censo_report._viabilidade_page` (Python).

   Puro e TESTADO de proposito: o gerador le CHAVES e UNIDADES especificas; mandar
   a chave errada (ou a unidade errada) faz o slide de viabilidade vir vazio ("n/d")
   sem erro nenhum — foi exatamente o bug corrigido em 2026-07-22 (o front mandava
   `margem`/`ebitda`/`faturamento`, o gerador le `margem_ebitda_pct`/`ebitda_mensal`/
   `faturamento_mensal`, alem de nem enviar payback/roic/faixa).
   --------------------------------------------------------------------------- */
import type { InfoImovel, ViabilidadeOut } from './types'

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

/**
 * Mapeia os inputs do imóvel para o CONTRATO de `censo_report._info_imovel_page`, que
 * lê CHAVES ESPECÍFICAS: `metragem_m2`, `aluguel_pedido`, `valor_venda`, `pe_direito_m`,
 * `vagas`, `tipo_imovel`, além de `endereco` e `observacoes`.
 *
 * BUG que isto corrige: a metragem e o aluguel vivem no **Cenário** (não em "Dados para o
 * relatório") e nunca eram enviados; e o front mandava `pe_direito`/`tipo`, mas o PDF lê
 * `pe_direito_m`/`tipo_imovel`. Resultado: o imóvel saía com "n/d" mesmo tudo preenchido.
 * Mesmo padrão testado do `viabilidadeParaPdf`: chave errada → slide vazio, sem erro.
 *
 * `metragem_m2`/`aluguel_pedido` vêm como número (formatação `num`/`brl` do gerador); os
 * campos de texto são convertidos para número no formato pt-BR (ponto=milhar, vírgula=decimal)
 * quando possível, senão seguem como texto (o gerador degrada gracioso). Chaves vazias saem.
 */
export function infoImovelParaPdf(
  info: InfoImovel,
  cenario: { m2: number; aluguel: number },
): Record<string, unknown> {
  const numOpt = (s?: string): number | string | undefined => {
    const t = (s ?? '').trim()
    if (!t) return undefined
    // pt-BR: ponto separa milhar, vírgula é decimal. Só remove o ponto quando ele
    // separa milhar (seguido de exatamente 3 dígitos), preservando "4.5" como 4.5.
    const cleaned = t
      .replace(/[^\d.,-]/g, '')
      .replace(/\.(?=\d{3}(\D|$))/g, '')
      .replace(',', '.')
    const n = Number(cleaned)
    return cleaned !== '' && Number.isFinite(n) ? n : t
  }
  const out: Record<string, unknown> = {
    metragem_m2: cenario.m2,
    aluguel_pedido: cenario.aluguel,
    valor_venda: numOpt(info.valor_venda),
    pe_direito_m: numOpt(info.pe_direito),
    vagas: numOpt(info.vagas),
    tipo_imovel: info.tipo?.trim() || undefined,
    endereco: info.nome?.trim() || undefined,
    observacoes: info.observacoes?.trim() || undefined,
  }
  for (const k of Object.keys(out)) if (out[k] === undefined) delete out[k]
  return out
}
