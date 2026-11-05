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
 *  - com o aluguel vazio, o número cinza É o aluguel que vai para a conta (regra da DEC-079);
 *  - o quadro mostra a FAIXA p25–p75 da região, e a comparação é contra a faixa (pedido do
 *    time imobiliário, decidido por Felipe em 04/11/2026). A mediana segue sendo o número cinza;
 *  - a comparação diz as DUAS réguas ("42% acima da mediana · 10% acima da faixa"). Cor
 *    (Felipe, 05/11/2026): vermelho acima da faixa, amarelo acima da mediana, verde no resto.
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
  /** p25 e p75 do R$/m² no mesmo recorte: a faixa do quadro. */
  rs_m2_p25: number
  rs_m2_p75: number
}

export interface FaixaAluguel {
  min: number
  max: number
}

/** Aluguel de referência para a metragem, em reais, arredondado à centena. */
export function aluguelDeReferencia(ref: AluguelReferencia | null, m2: number): number | null {
  if (!ref || !(m2 > 0) || !(ref.rs_m2 > 0)) return null
  return naCentena(ref.rs_m2 * m2)
}

const naCentena = (reais: number) => Math.round(reais / 100) * 100

/** Faixa do aluguel do mês para a metragem (p25 e p75 × m²), na centena. */
export function faixaDoAluguel(ref: AluguelReferencia | null, m2: number): FaixaAluguel | null {
  if (!ref || !(m2 > 0) || !(ref.rs_m2_p25 > 0) || !(ref.rs_m2_p75 > 0)) return null
  return { min: naCentena(ref.rs_m2_p25 * m2), max: naCentena(ref.rs_m2_p75 * m2) }
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
 * Distância do aluguel digitado até a ponta mais próxima da faixa, em % dessa ponta. 0 =
 * dentro da faixa; fora dela nunca devolve 0. `null` sem as duas pontas. Espelho de
 * `diferenca_da_faixa_pct` no servidor (o PDF).
 */
export function diferencaDaFaixaPct(
  aluguel: number | null | undefined,
  faixa: FaixaAluguel | null,
): number | null {
  if (aluguel == null || faixa == null) return null
  if (faixa.max > 0 && aluguel > faixa.max) {
    return Math.max(1, Math.round((aluguel / faixa.max - 1) * 100))
  }
  if (faixa.min > 0 && aluguel < faixa.min) {
    return Math.min(-1, Math.round((aluguel / faixa.min - 1) * 100))
  }
  return 0
}

/** A frase da comparação ("12% acima da faixa"). */
export function textoDaDiferenca(pct: number): string {
  if (pct === 0) return 'dentro da faixa'
  return `${Math.abs(pct)}% ${pct > 0 ? 'acima' : 'abaixo'} da faixa`
}

/** Diferença do aluguel para a mediana do mês, em % dela. Espelho de `diferenca_da_mediana_pct`. */
export function diferencaDaMedianaPct(
  aluguel: number | null | undefined,
  mediana: number | null,
): number | null {
  if (aluguel == null || mediana == null || !(mediana > 0)) return null
  return Math.round((aluguel / mediana - 1) * 100)
}

/** Tom da comparação: `faixa` acima da faixa, `mediana` acima só da mediana, `ok` no resto. */
export type TomDaComparacao = 'faixa' | 'mediana' | 'ok'

export function tomDaComparacao(pctFaixa: number, pctMediana: number | null): TomDaComparacao {
  if (pctFaixa > 0) return 'faixa'
  if (pctMediana != null && pctMediana > 0) return 'mediana'
  return 'ok'
}

/** A frase contra a mediana ("42% acima da mediana"). */
export function textoDaDiferencaMediana(pct: number): string {
  if (pct === 0) return 'na mediana'
  return `${Math.abs(pct)}% ${pct > 0 ? 'acima' : 'abaixo'} da mediana`
}
