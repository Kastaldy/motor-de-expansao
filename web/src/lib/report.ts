/* ---------------------------------------------------------------------------
   Ponte Viabilidade -> PDF do Relatorio Pontual.

   FIN-VIAB-01: o PDF passa a consumir EXATAMENTE o mesmo objeto que a tela —
   o `viabilidade_payload_v1` inteiro, sem remapear chave e sem recalcular nada.
   Era justamente a traducao de chaves/unidades aqui (e a segunda implementacao
   do lado Python) que fazia tela e PDF divergirem no MESMO cenario: payback 35
   vs 33, aluguel-teto R$55,5 mil vs R$105,8 mil.

   A funcao continua existindo como a UNICA costura entre os dois consumidores:
   se um dia o PDF precisar de algo, entra no payload do motor — nao numa conta
   feita aqui.
   --------------------------------------------------------------------------- */
import type { InfoImovel, ViabilidadeOut } from './types'

/**
 * Passa o payload adiante como esta (copia rasa, para nao vazar a referencia do
 * estado da tela). NENHUMA derivacao: `versao` viaja junto para o gerador poder
 * recusar um contrato que nao conhece.
 */
export function viabilidadeParaPdf(res: ViabilidadeOut): Record<string, unknown> {
  return { ...res } as unknown as Record<string, unknown>
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
