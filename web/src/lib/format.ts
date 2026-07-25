/** Formatacao pt-BR. Todo numero exibido passa por aqui. */

const nf = (casas: number) =>
  new Intl.NumberFormat('pt-BR', {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  })

/** Numero inteiro com separador de milhar. `null` vira "n/d", nunca "0". */
export function num(v: number | null | undefined, casas = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return 'n/d'
  return nf(casas).format(v)
}

/**
 * Reais. `compacto` usa mil/mi para caber em card estreito; `casas` serve para
 * valores em que o centavo importa (ticket: R$ 88,20 e nao R$ 88).
 */
export function brl(v: number | null | undefined, compacto = false, casas = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return 'n/d'
  if (compacto) {
    const abs = Math.abs(v)
    if (abs >= 1_000_000) return `R$ ${nf(1).format(v / 1_000_000)} mi`
    if (abs >= 1_000) return `R$ ${nf(0).format(v / 1_000)} mil`
  }
  return `R$ ${nf(casas).format(v)}`
}

/**
 * Reais em notacao CURTA: "R$ 38k", "R$ 2,2M". Para readout de sidebar, onde o valor
 * tem de caber numa linha so — mais enxuto que `brl(v, true)`, que escreve "mil"/"mi"
 * por extenso e quebrava a linha no bloco de investimento.
 */
export function brlCurto(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return 'n/d'
  const abs = Math.abs(v)
  if (abs >= 1_000_000) return `R$ ${nf(abs >= 10_000_000 ? 0 : 1).format(v / 1_000_000)}M`
  if (abs >= 1_000) return `R$ ${nf(0).format(v / 1_000)}k`
  return `R$ ${nf(0).format(v)}`
}

export function pct(v: number | null | undefined, casas = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return 'n/d'
  return `${nf(casas).format(v)}%`
}

/**
 * Percentual a partir de uma FRACAO — a unidade em que o motor entrega TODA taxa
 * (margem, retorno, TIR, reajuste, share). O x100 e RENDER, nao calculo: a tela
 * nao pode derivar numero financeiro (FIN-VIAB-01).
 */
export function pctFrac(v: number | null | undefined, casas = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return 'n/d'
  return pct(v * 100, casas)
}

/**
 * Rotulo de um mes da linha do tempo do motor (M-4..M+60). Mes negativo e
 * pre-abertura (obra); a partir de 1 e operacao. Nao existe mes 0.
 */
export function rotuloMes(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return 'n/d'
  const m = Math.round(v)
  return m < 0 ? `M${m} (obra)` : `mês ${m}`
}

/** Coordenada no padrao pt-BR (virgula decimal), como o template mostra. */
export function coord(lat: number, lng: number): string {
  const f = nf(5)
  return `${f.format(lat)}, ${f.format(lng)}`
}

/** Alunos — a unidade de conta do residual e da demanda. */
export function alunos(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return 'n/d'
  return nf(0).format(Math.round(v))
}
