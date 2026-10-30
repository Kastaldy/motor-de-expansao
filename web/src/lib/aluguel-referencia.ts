/**
 * Régua de aluguel da Viabilidade (DEC-080): R$/m² mediano dos anúncios da base imobiliária
 * por município × tipo de imóvel, com fallback para a UF e o Brasil quando o recorte tem
 * menos de 5 anúncios.
 *
 * Decisões de Felipe (29/10/2026) que este módulo trava:
 *  - sem selo de confiança: a base aparece como FATO NEUTRO ("Base: 7 anúncios de
 *    comercial em Vitória/ES"), sem adjetivo e sem fonte/data;
 *  - os três tipos entram, cada um com a sua mediana; o seletor abre em Comercial (valor bruto
 *    `loja`). Nomes de exibição (Felipe, 29/10): `loja` = Comercial, `comercial` = Laje Corporativa;
 *  - com o aluguel vazio, o número cinza É o aluguel que vai para a conta (regra da DEC-079).
 */

/** Valores BRUTOS do tipo, como o servidor os recebe. Nunca acentuar (CLAUDE.md §2). */
export type TipoImovelAluguel = 'galpao' | 'comercial' | 'loja'

export const TIPOS_IMOVEL_ALUGUEL: readonly TipoImovelAluguel[] = ['galpao', 'loja', 'comercial']

/** Tipo marcado ao abrir o simulador (decisão de Felipe, 29/10/2026). */
export const TIPO_IMOVEL_PADRAO: TipoImovelAluguel = 'loja'

/** Rótulo de EXIBIÇÃO do seletor. */
export const ROTULO_TIPO_IMOVEL: Readonly<Record<TipoImovelAluguel, string>> = Object.freeze({
  galpao: 'Galpão',
  comercial: 'Laje Corporativa',
  loja: 'Comercial',
})

/** O tipo no meio de uma frase ("anúncios de galpão"). */
const TIPO_NA_FRASE: Readonly<Record<TipoImovelAluguel, string>> = Object.freeze({
  galpao: 'galpão',
  comercial: 'laje corporativa',
  loja: 'comercial',
})

export const ROTULO_SELETOR_TIPO_IMOVEL = 'Tipo do imóvel'

export interface AluguelReferencia {
  tipo: TipoImovelAluguel
  rs_m2: number
  n_anuncios: number
  nivel: 'municipio' | 'uf' | 'brasil'
  uf: string | null
  municipio: string | null
}

/** Aluguel de referência para a metragem, em reais, arredondado à centena. */
export function aluguelDeReferencia(ref: AluguelReferencia | null, m2: number): number | null {
  if (!ref || !(m2 > 0) || !(ref.rs_m2 > 0)) return null
  return Math.round((ref.rs_m2 * m2) / 100) * 100
}

/** A linha da base, em fato neutro: quantos anúncios e de onde. Nunca qualifica. */
export function textoDaBase(ref: AluguelReferencia): string {
  const n = ref.n_anuncios.toLocaleString('pt-BR')
  const anuncios = `${n} ${ref.n_anuncios === 1 ? 'anúncio' : 'anúncios'} de ${TIPO_NA_FRASE[ref.tipo]}`
  if (ref.nivel === 'municipio') return `Base: ${anuncios} em ${ref.municipio}/${ref.uf}`
  if (ref.nivel === 'uf') return `Base: ${anuncios} no estado (${ref.uf})`
  return `Base: ${anuncios} no Brasil`
}

/**
 * Comparação do aluguel digitado com a referência, em % arredondado. `null` sem as duas
 * pontas. 0 = igual à referência.
 */
export function diferencaPct(aluguel: number | null | undefined, referencia: number | null): number | null {
  if (aluguel == null || referencia == null || referencia <= 0) return null
  return Math.round((aluguel / referencia - 1) * 100)
}

/** A frase da comparação ("28% acima da referência"). */
export function textoDaDiferenca(pct: number): string {
  if (pct === 0) return 'igual à referência'
  return `${Math.abs(pct)}% ${pct > 0 ? 'acima' : 'abaixo'} da referência`
}
