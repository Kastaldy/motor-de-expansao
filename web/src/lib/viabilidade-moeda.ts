/* ---------------------------------------------------------------------------
   Viabilidade: a moeda em que o operador digita e le, e o mix recorrente x agregador.

   A conta da viabilidade e' feita em REAIS (decisao 0.6 do plano multipais): os custos
   fixos e as faixas de imposto do motor sao em reais. Mas o imovel argentino vem cotado
   em pesos ou em dolares. Onde o perfil do pais declara os dois cambios, a tela oferece
   um seletor (moeda do pais | dolares): o operador digita ticket, aluguel e investimento
   na moeda do imovel e le os resultados nessa mesma moeda. A conversao acontece por
   tras, nas duas pontas — entrada -> reais antes de chamar o motor, reais -> moeda
   escolhida na exibicao (`definirExibicaoMonetaria` em `format.ts`).

   Os cambios sao os do perfil, servidos pelo `/api/me` com o mes-base. Nao ha' campo
   de cambio na tela (decisao de Juan, 2026-10-05).

   Modulo PURO: nenhum simbolo de moeda escrito aqui (`test_sem_moeda_hardcoded_no_front`).
   --------------------------------------------------------------------------- */

/** O que o `/api/me` serve em `viabilidade_moeda`. Ausente onde o perfil nao declara. */
export interface MoedaDeViabilidade {
  /** Codigo ISO da moeda do pais ("ARS"). */
  codigo: string
  /** Simbolo da moeda do pais ("$"). */
  simbolo: string
  /** Unidades da moeda do pais por dolar. */
  local_por_usd: number
  /** Reais por dolar. */
  brl_por_usd: number
  /** Mes "AAAA-MM" dos dois cambios, ou `null` se o perfil nao declara. */
  base: string | null
}

/** Moeda em que o operador digita e le: a do pais, ou dolares. */
export type MoedaDeEntrada = 'local' | 'usd'

let moedaAtual: MoedaDeViabilidade | null = null

/** Cambios desta instancia; `null` = sem seletor, tudo em reais como sempre. */
export function moedaDeViabilidade(): MoedaDeViabilidade | null {
  return moedaAtual
}

function positivo(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v) && v > 0
}

/**
 * Instala o que veio do `/api/me`. Chamado UMA vez, pelo `main.tsx`. Payload ausente
 * ou malformado nao instala nada: a tela cai no comportamento de sempre (reais) em vez
 * de converter por um cambio invalido.
 */
export function definirMoedaDeViabilidade(p: unknown): void {
  moedaAtual = null
  if (!p || typeof p !== 'object') return
  const c = p as Partial<MoedaDeViabilidade>
  if (typeof c.codigo !== 'string' || !c.codigo.trim()) return
  if (typeof c.simbolo !== 'string' || !c.simbolo.trim()) return
  if (!positivo(c.local_por_usd) || !positivo(c.brl_por_usd)) return
  moedaAtual = {
    codigo: c.codigo,
    simbolo: c.simbolo,
    local_por_usd: c.local_por_usd,
    brl_por_usd: c.brl_por_usd,
    base: typeof c.base === 'string' && c.base.trim() ? c.base : null,
  }
}

/** SO para teste: devolve o modulo ao estado de import. */
export function _resetarMoedaParaTeste(): void {
  moedaAtual = null
}

/**
 * Quantos REAIS vale UMA unidade da moeda de entrada. Dolar: o proprio cambio do real;
 * moeda do pais: passa pelo dolar (local -> dolar -> real).
 */
export function reaisPorUnidade(m: MoedaDeViabilidade, entrada: MoedaDeEntrada): number {
  return entrada === 'usd' ? m.brl_por_usd : m.brl_por_usd / m.local_por_usd
}

/**
 * Valor digitado -> reais, arredondado ao centavo (e' o numero que vai ao motor).
 * `undefined`/nao finito/negativo devolve `undefined`: campo vazio continua vazio, e a
 * chave some do JSON para o motor aplicar o padrao dele. ZERO e' valor legitimo (taxa
 * de franquia zero, aluguel zero) e atravessa como 0.
 */
export function paraReais(v: number | undefined, reaisPorUn: number): number | undefined {
  if (v === undefined || !Number.isFinite(v) || v < 0) return undefined
  if (!positivo(reaisPorUn)) return undefined
  return Math.round(v * reaisPorUn * 100) / 100
}

/**
 * Reescreve um valor ja' digitado quando o operador troca a moeda do seletor, para o
 * CENARIO continuar o mesmo (US$ 25 vira os pesos equivalentes, nao "25 pesos").
 * `casas` e' a precisao do campo na moeda de destino.
 */
export function trocarDeMoeda(
  v: number | undefined,
  reaisPorUnDe: number,
  reaisPorUnPara: number,
  casas = 0,
): number | undefined {
  if (v === undefined || !Number.isFinite(v)) return undefined
  if (!positivo(reaisPorUnDe) || !positivo(reaisPorUnPara)) return undefined
  const p = 10 ** casas
  return Math.round(((v * reaisPorUnDe) / reaisPorUnPara) * p) / p
}

/**
 * Percentual digitado (0–100) -> FRACAO (0–1), o contrato do payload. `undefined`
 * atravessa intacto para a chave sumir do JSON e o motor aplicar o padrao dele; valor
 * fora de 0–100 tambem vira `undefined` — nunca uma fracao maior que 1.
 */
export function fracaoDoPercentual(pct: number | undefined): number | undefined {
  if (pct === undefined || !Number.isFinite(pct) || pct < 0 || pct > 100) return undefined
  return pct / 100
}
