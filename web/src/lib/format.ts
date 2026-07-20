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

/** Reais. `compacto` usa mil/mi para caber em card estreito. */
export function brl(v: number | null | undefined, compacto = false): string {
  if (v === null || v === undefined || Number.isNaN(v)) return 'n/d'
  if (compacto) {
    const abs = Math.abs(v)
    if (abs >= 1_000_000) return `R$ ${nf(1).format(v / 1_000_000)} mi`
    if (abs >= 1_000) return `R$ ${nf(0).format(v / 1_000)} mil`
  }
  return `R$ ${nf(0).format(v)}`
}

export function pct(v: number | null | undefined, casas = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return 'n/d'
  return `${nf(casas).format(v)}%`
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
