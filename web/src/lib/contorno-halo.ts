/**
 * CONTORNO DUPLO ("halo") das marcas que o operador põe no mapa: os pins dos pontos da
 * comparação, o traço da área desenhada (durante e depois do desenho) e os vértices.
 *
 * O DEFEITO (Vinicius, 2026-10-16): "dependendo da cor aplicada, acaba ficando escondido
 * (ex.: um desenho de área com linhas verdes fica meio apagado num hexágono aprovado, por ser
 * verde também)". A rampa de score dos hexágonos usa verde, laranja, vermelho — e as cores de
 * identidade da comparação (`CORES_IDENTIDADE`) e o verde do desenho caem dentro dela. Uma
 * linha de 2-3 px da MESMA matiz do preenchimento embaixo some.
 *
 * A SAÍDA é a de qualquer mapa impresso: a cor de identidade POR CIMA de uma faixa mais larga
 * de contraste POR BAIXO. O halo não depende da cor do hexágono — ele separa a linha de
 * QUALQUER fundo, porque é sempre uma das pontas da escala de luminância.
 *
 * QUAL HALO. No tema escuro, sempre escuro: o basemap é preto, e um halo claro viraria uma
 * segunda linha competindo com a de identidade. No claro, decide o CONTRASTE com a própria
 * cor: cor escura (o verde #0f9d55 do desenho, as cinco de identidade) ganha halo branco;
 * uma cor clara (amarelo, por exemplo) ganharia halo escuro — branco em volta de amarelo
 * sobre o Positron não separa nada.
 *
 * Puro, sem deck.gl, para o vitest (node) testar sem montar mapa.
 */

import type { Tema } from './tema'

export type Rgba = [number, number, number, number]
type Rgb = readonly [number, number, number] | readonly [number, number, number, number]

/** Halo escuro: o `--bg-base` do escuro, quase opaco. */
export const HALO_ESCURO: Rgba = [8, 11, 16, 225]
/** Halo claro: branco quase opaco. */
export const HALO_CLARO: Rgba = [255, 255, 255, 235]

/**
 * Quanto o halo é MAIS LARGO que o traço, em px (metade de cada lado). 4 px = 2 px de folga
 * de cada lado: menos que isso some no zoom de cidade; mais vira moldura grossa.
 */
export const HALO_EXTRA_PX = 4

/**
 * Alfa do VÉU da área em desenho (0-255). Era 46: sobre um hexágono da mesma matiz, o véu
 * somava cor à cor e borrava o traço. Mais transparente, quem diz "esta é a área" é o
 * contorno com halo, e o choropleth embaixo continua legível.
 */
export const ALFA_VEU_DESENHO = 24

/** Alfa do traço quando o desenho está PAUSADO (`lib/painel-trilho`): presente, mas em espera. */
export const ALFA_PAUSADO = 150

/** Corte de luminância relativa acima do qual a cor é "clara" e pede halo escuro. */
export const LUMINANCIA_COR_CLARA = 0.5

/** Luminância relativa sRGB (WCAG), 0 = preto, 1 = branco. */
export function luminancia(rgb: Rgb): number {
  const lin = (c: number) => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2])
}

/** A cor do halo para uma cor de identidade, no tema dado. */
export function corDoHalo(tema: Tema, rgb: Rgb): Rgba {
  if (tema === 'escuro') return [...HALO_ESCURO] as Rgba
  return luminancia(rgb) > LUMINANCIA_COR_CLARA ? ([...HALO_ESCURO] as Rgba) : ([...HALO_CLARO] as Rgba)
}

export interface TracoComHalo {
  /** Desenhado PRIMEIRO (por baixo): mais largo, na cor de contraste. */
  halo: { cor: Rgba; largura: number }
  /** Desenhado DEPOIS (por cima): a cor de identidade, na largura pedida. */
  traco: { cor: Rgba; largura: number }
}

/** As duas passadas de uma linha com halo. `larguraPx` é a do traço de identidade. */
export function tracoComHalo(
  tema: Tema,
  rgb: Rgb,
  larguraPx: number,
  opcoes: { pausado?: boolean } = {},
): TracoComHalo {
  const alfa = opcoes.pausado ? ALFA_PAUSADO : 255
  const halo = corDoHalo(tema, rgb)
  return {
    halo: {
      cor: opcoes.pausado ? [halo[0], halo[1], halo[2], Math.round(halo[3] * 0.6)] : halo,
      largura: larguraPx + HALO_EXTRA_PX,
    },
    traco: { cor: [rgb[0], rgb[1], rgb[2], alfa], largura: larguraPx },
  }
}

/** Raio do disco de halo por baixo de um pin/vértice de raio `raioPx`. */
export function raioComHalo(raioPx: number): number {
  return raioPx + HALO_EXTRA_PX / 2
}

/**
 * Os contornos de CENÁRIO (multi-hex) que ganham halo: cada hexágono do cenário, na cor de
 * identidade da posição dele, MENOS o selecionado (esse veste a cor de seleção, na camada
 * `hex`). Acima de `nCores` vai o cinza neutro — a mesma regra da camada `hex`, que a
 * paleta cicla e o 6º não pode repetir a cor do 1º.
 */
export const CINZA_ALEM_DA_PALETA: Rgba = [154, 167, 181, 255]

export function contornosDoCenario(
  cenario: readonly string[],
  selecionado: string | null | undefined,
  nCores: number,
  corDe: (i: number) => Rgb,
): { id: string; rgb: Rgba }[] {
  const out: { id: string; rgb: Rgba }[] = []
  cenario.forEach((id, i) => {
    if (id === selecionado) return
    const c = i < nCores ? corDe(i) : CINZA_ALEM_DA_PALETA
    out.push({ id, rgb: [c[0], c[1], c[2], 255] })
  })
  return out
}

/** O véu (preenchimento) da área em desenho: a cor de identidade bem transparente. */
export function veuDoDesenho(rgb: Rgb, opcoes: { pausado?: boolean } = {}): Rgba {
  return [rgb[0], rgb[1], rgb[2], opcoes.pausado ? Math.round(ALFA_VEU_DESENHO / 2) : ALFA_VEU_DESENHO]
}
