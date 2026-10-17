import { describe, expect, it } from 'vitest'

import { CORES_IDENTIDADE, corDeIdentidadeRgb } from './comparacao'
import {
  ALFA_PAUSADO,
  ALFA_VEU_DESENHO,
  HALO_CLARO,
  HALO_ESCURO,
  HALO_EXTRA_PX,
  CINZA_ALEM_DA_PALETA,
  contornosDoCenario,
  corDoHalo,
  luminancia,
  raioComHalo,
  tracoComHalo,
  veuDoDesenho,
} from './contorno-halo'

/* Os dois verdes do desenho (--gr-verde do escuro e do claro), espelhados em `PELE`. */
const VERDE_ESCURO = [95, 208, 140] as const
const VERDE_CLARO = [15, 157, 85] as const

describe('luminancia', () => {
  it('nas pontas da escala', () => {
    expect(luminancia([0, 0, 0])).toBe(0)
    expect(luminancia([255, 255, 255])).toBeCloseTo(1, 6)
  })
})

describe('corDoHalo', () => {
  it('no tema escuro o halo é sempre escuro, qualquer que seja a cor', () => {
    for (const rgb of [VERDE_ESCURO, [255, 230, 0] as const, [20, 20, 20] as const]) {
      expect(corDoHalo('escuro', rgb)).toEqual(HALO_ESCURO)
    }
  })

  it('no claro, cor escura ganha halo branco (o verde do desenho e as cinco de identidade)', () => {
    expect(corDoHalo('claro', VERDE_CLARO)).toEqual(HALO_CLARO)
    CORES_IDENTIDADE.forEach((_, i) => {
      expect(corDoHalo('claro', corDeIdentidadeRgb(i))).toEqual(HALO_CLARO)
    })
  })

  it('no claro, cor clara (amarelo) ganha halo escuro — branco em volta de amarelo não separa', () => {
    expect(corDoHalo('claro', [255, 230, 0])).toEqual(HALO_ESCURO)
  })

  it('devolve cópia: mexer no resultado não corrompe a constante', () => {
    const h = corDoHalo('escuro', VERDE_ESCURO)
    h[3] = 0
    expect(HALO_ESCURO[3]).toBeGreaterThan(0)
  })
})

describe('tracoComHalo', () => {
  it('o halo é mais largo que o traço e o traço mantém a cor de identidade opaca', () => {
    const t = tracoComHalo('escuro', VERDE_ESCURO, 2.5)
    expect(t.halo.largura).toBe(2.5 + HALO_EXTRA_PX)
    expect(t.traco).toEqual({ cor: [95, 208, 140, 255], largura: 2.5 })
    expect(t.halo.cor).toEqual(HALO_ESCURO)
  })

  it('pausado esmaece traço e halo, sem mudar as larguras', () => {
    const t = tracoComHalo('claro', VERDE_CLARO, 3, { pausado: true })
    expect(t.traco.cor[3]).toBe(ALFA_PAUSADO)
    expect(t.halo.cor[3]).toBeLessThan(HALO_CLARO[3])
    expect(t.halo.largura).toBe(3 + HALO_EXTRA_PX)
  })
})

describe('raio e véu', () => {
  it('o disco de halo sobra metade da folga de cada lado do pin', () => {
    expect(raioComHalo(10)).toBe(10 + HALO_EXTRA_PX / 2)
  })

  it('o véu é mais transparente que o antigo (46) e ainda mais quando pausado', () => {
    expect(ALFA_VEU_DESENHO).toBeLessThan(46)
    expect(veuDoDesenho(VERDE_ESCURO)).toEqual([95, 208, 140, ALFA_VEU_DESENHO])
    expect(veuDoDesenho(VERDE_ESCURO, { pausado: true })[3]).toBeLessThan(ALFA_VEU_DESENHO)
  })
})

describe('contornos do cenario', () => {
  it('cada hexagono na cor da posicao, sem o selecionado, cinza alem da paleta', () => {
    const ids = ['a', 'b', 'c', 'd', 'e', 'f']
    const r = contornosDoCenario(ids, 'b', CORES_IDENTIDADE.length, (i) => corDeIdentidadeRgb(i))
    expect(r.map((x) => x.id)).toEqual(['a', 'c', 'd', 'e', 'f'])
    expect(r[0].rgb).toEqual(corDeIdentidadeRgb(0))
    // a posicao conta do CENARIO, nao da lista filtrada: 'c' segue com a cor 2
    expect(r[1].rgb).toEqual(corDeIdentidadeRgb(2))
    expect(r[4].rgb).toEqual(CINZA_ALEM_DA_PALETA)
  })

  it('cenario vazio nao gera contorno', () => {
    expect(contornosDoCenario([], null, 5, () => [0, 0, 0])).toEqual([])
  })
})
