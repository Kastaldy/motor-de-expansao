/* Passo 4 do funil ("Como a cidade está indo"): as três classes de crescimento da área
   construída pintam o hexágono EXATAMENTE como as camadas 1-3 pintam uma faixa de score
   (pedidos de 2026-11-10 e 2026-11-11, "tem que estar como está nas outras camadas"):

     Em alta       = verde da faixa 90-100 (SCORE_BANDS_HEX[9])
     Estável       = verde da faixa 70-80  (SCORE_BANDS_HEX[7]) -- o verde mais claro
     Sem obra nova = vermelho da faixa 10-20 (SCORE_BANDS_HEX[1])

   com UMA opacidade, a do tema (o `alphaHex` que as outras camadas usam), sem variar pela
   taxa. A tentativa anterior (intensidade pela taxa, alfa por classe) invertia a leitura: no
   tema escuro o Estável transparente saía mais escuro que o Em alta, enquanto a legenda, em
   cor cheia, mostrava o Estável como o verde mais claro.

   O teste compara com `scoreBandToColor` (o pintor das camadas 1-3) e com SCORE_BANDS_HEX por
   ÍNDICE, e não com literal novo: a cor do crescimento anda junto com a rampa, e a paridade da
   rampa com o Python já é travada por tests/unit/test_paridade_paleta_web.py. Usa só literais
   de classe — o crescimento_hex.parquet não existe no clone nem no CI. */
import { describe, expect, it } from 'vitest'
import * as cores from './colors'
import {
  CRESC_ALTA_HEX,
  CRESC_ESTAVEL_HEX,
  CRESC_PARADO_HEX,
  HEX_FILL_ALPHA,
  SCORE_BANDS_HEX,
  crescClasseToColor,
  scoreBandToColor,
} from './colors'

function rgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}

describe('camada de crescimento pintada como as outras camadas', () => {
  it('as três cores são faixas da rampa: verde 90-100, verde 70-80, vermelho 10-20', () => {
    expect(CRESC_ALTA_HEX).toBe(SCORE_BANDS_HEX[9])
    expect(CRESC_ESTAVEL_HEX).toBe(SCORE_BANDS_HEX[7])
    expect(CRESC_PARADO_HEX).toBe(SCORE_BANDS_HEX[1])
  })

  it.each([
    ['Em alta', 95],
    ['Estável', 75],
    ['Sem obra nova', 15],
  ] as const)('%s sai igual a um hexágono de score %d das camadas 1-3, nos dois temas', (classe, score) => {
    for (const alpha of [HEX_FILL_ALPHA, 170]) {
      expect(crescClasseToColor(classe, alpha)).toEqual(scoreBandToColor(score, alpha))
    }
  })

  it('a opacidade é a do tema e não depende da classe (nada de destaque próprio)', () => {
    const alfas = ['Em alta', 'Estável', 'Sem obra nova'].map((c) => crescClasseToColor(c)[3])
    expect(alfas).toEqual([HEX_FILL_ALPHA, HEX_FILL_ALPHA, HEX_FILL_ALPHA])
  })

  it('mapa e legenda contam a mesma história: o Estável é o verde mais claro nos dois', () => {
    // Luminância relativa (sRGB) da cor cheia: a mesma ordem vale no mapa, onde todas as classes
    // levam a MESMA opacidade sobre o mesmo fundo.
    const lum = (hex: string) => {
      const [r, g, b] = rgb(hex).map((c) => {
        const v = c / 255
        return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
      })
      return 0.2126 * r + 0.7152 * g + 0.0722 * b
    }
    expect(lum(CRESC_ESTAVEL_HEX)).toBeGreaterThan(lum(CRESC_ALTA_HEX))
    expect(crescClasseToColor('Estável')[3]).toBe(crescClasseToColor('Em alta')[3])
  })

  it('a calibração por taxa saiu (não há mais alfa por classe nem pontas de taxa)', () => {
    expect('CRESC_ALPHA_ESCURO' in cores).toBe(false)
    expect('CRESC_ALPHA_CLARO' in cores).toBe(false)
    expect('CRESC_TAXA_PONTAS' in cores).toBe(false)
  })

  it.each([null, undefined, '', 'Estavel', 'Em queda'])(
    'sem classe reconhecida (%s) continua no cinza de "sem medição"',
    (classe) => {
      expect(crescClasseToColor(classe)).toEqual([120, 120, 140, 45])
    },
  )
})
