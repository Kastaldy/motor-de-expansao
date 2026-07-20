/* ---------------------------------------------------------------------------
   Cores dos hexagonos — porte fiel do dashboard Streamlit.

   Fonte da verdade: src/motor_expansao/dashboard/
     - constants.RESIDUAL_SCORE_BANDS      (10 faixas de 10 pontos, vermelho->verde)
     - utils.score_band_to_color(score, alpha=170)
     - components._DISCARDED_FILL / _NAN_SCORE_FILL / _DISCARDED_LINE

   Regra canonica (CLAUDE.md §5): faixas de 10 pontos via RESIDUAL_SCORE_BANDS.
   M1 colore por score_priorizacao, censo por score_setor_2022_calibrado,
   hibrido por score_expansao_hibrido, residual por score_oportunidade_residual.
   --------------------------------------------------------------------------- */

export type RGBA = [number, number, number, number]

/** RESIDUAL_SCORE_BANDS, na ordem 0-10 .. 90-100. */
export const SCORE_BANDS_HEX = [
  '#941212',
  '#B92323',
  '#DC4141',
  '#DC6914',
  '#F0941E',
  '#EEC828',
  '#96D250',
  '#50C33C',
  '#19A832',
  '#0A8226',
] as const

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ]
}

const BANDS_RGB: [number, number, number][] = SCORE_BANDS_HEX.map(hexToRgb)

/**
 * Alpha do preenchimento dos hexes. O dashboard usa 170; aqui e mais baixo para
 * o basemap (ruas/nomes) respirar por baixo da cor — pedido do Felipe. A rampa
 * de cor (hue) segue identica; muda so a opacidade.
 */
export const HEX_FILL_ALPHA = 115
const CUT_ALPHA = 95

/** Fill de score NaN, igual a utils.score_band_to_color (RGB do dashboard). */
export const NA_FILL: RGBA = [120, 120, 140, 70]
/** Hex descartado pelo corte de <5k hab (components._DISCARDED_FILL, alpha rebaixado). */
export const DISCARDED_FILL: RGBA = [150, 150, 170, CUT_ALPHA]
export const DISCARDED_LINE: RGBA = [170, 170, 190, 160]
/** Hex valido do M1 sem score na camada ativa (components._NAN_SCORE_FILL). */
export const NAN_SCORE_FILL: RGBA = [110, 116, 140, CUT_ALPHA]

/** Regua operacional do dashboard (POP_MIN_ACIONAVEL). */
export const POP_MIN_ACIONAVEL = 5000

/**
 * Porte 1:1 de `score_band_to_color`: mapeia score 0-100 para a faixa de 10 pts.
 * `alpha` default 170, exatamente como o dashboard.
 */
export function scoreBandToColor(
  score: number | null | undefined,
  alpha = 170,
): RGBA {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return [...NA_FILL]
  }
  const idx = Math.min(9, Math.max(0, Math.floor(score / 10)))
  const [r, g, b] = BANDS_RGB[idx]
  return [r, g, b, alpha]
}

/** Só a cor sólida da faixa (para a legenda), sem alpha. */
export function bandSolid(i: number): string {
  return SCORE_BANDS_HEX[i]
}
