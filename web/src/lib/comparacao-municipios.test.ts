import { describe, expect, it } from 'vitest'

import {
  DIMENSOES_MUNICIPIO,
  compararMunicipios,
  montarMunicipio,
  municipiosDisponiveis,
  type MunicipioComparavel,
} from './comparacao-municipios'
import type { Passo } from './types'

/** Passos com a forma REAL do payload de GO (um `valor` por município, por passo). */
function passos(): Passo[] {
  const p = (n: number, titulo: string, itens: [string, number][]): Passo =>
    ({
      n,
      titulo,
      itens: itens.map(([t, v], i) => ({ rank: i + 1, titulo: t, municipio: t, valor: v })),
    }) as unknown as Passo

  return [
    p(1, 'Potencial socioeconômico', [
      ['Goiânia', 34], ['Anápolis', 12], ['Águas Lindas de Goiás', 9],
    ]),
    p(2, 'Demanda não atendida', [['Goiânia', 85891], ['Anápolis', 30120]]),
    p(3, 'Pressão concorrencial', [['Goiânia', 57164], ['Anápolis', 26213]]),
    p(4, 'Como as cidades estão indo', [['Goianésia', 22]]),
    p(5, 'Para onde crescer', [['Goiânia', 57164], ['Anápolis', 26213]]),
  ]
}

const CRES = {
  'Goiânia': { emp: 8.7, uf_mediana: 7.6 },
  'Anápolis': { emp: 5.0, uf_mediana: 7.6 },
}

describe('montarMunicipio', () => {
  it('le o valor de cada passo, sem agregar nada no cliente', () => {
    const m = montarMunicipio('Goiânia', passos(), CRES)
    expect(m.porPasso[1]).toBe(34)
    expect(m.porPasso[2]).toBe(85891)
    expect(m.porPasso[5]).toBe(57164)
    expect(m.crescimento?.emp).toBe(8.7)
  })

  it('passo em que o municipio nao aparece vira null, nunca zero', () => {
    // Goiânia não está no passo 4 — dizer "0% de emprego" seria inventar dado.
    const m = montarMunicipio('Goiânia', passos(), CRES)
    expect(m.porPasso[4]).toBeNull()
  })

  it('municipio sem crescimento nao quebra', () => {
    const m = montarMunicipio('Goianésia', passos(), CRES)
    expect(m.crescimento).toBeNull()
    expect(m.porPasso[4]).toBe(22)
  })
})

describe('municipiosDisponiveis', () => {
  it('junta os municipios de todos os passos, sem repetir', () => {
    expect(new Set(municipiosDisponiveis(passos()))).toEqual(
      new Set(['Águas Lindas de Goiás', 'Anápolis', 'Goiânia', 'Goianésia']),
    )
  })

  it('ordena em pt-BR: acento nao joga o nome para o fim da lista', () => {
    /* Este e' o caso em que o `sort()` padrao erra: ele compara code-unit, e 'Á'
       (U+00C1) vem DEPOIS de todo o alfabeto maiusculo cru — entao "Águas Lindas"
       cairia atras de "Goiânia". Em pt-BR o acento e' secundario: 'Á' ordena como
       'A', e a lista sai como um humano espera. */
    const ordenado = municipiosDisponiveis(passos())
    expect(ordenado[0]).toBe('Águas Lindas de Goiás')
    expect([...ordenado].sort()[0]).not.toBe('Águas Lindas de Goiás') // o padrao erra
  })
})

describe('DIMENSOES_MUNICIPIO', () => {
  it('residual vem primeiro na prioridade', () => {
    expect(DIMENSOES_MUNICIPIO[0].chave).toBe('residual_fila')
  })

  it('crescimento le o DESVIO para a mediana, nao o numero cru', () => {
    // O CAGED só vale contra margem estadual: comparar 8,7 com 22 solto convidaria
    // a lê-lo como grandeza absoluta.
    const dim = DIMENSOES_MUNICIPIO.find((d) => d.chave === 'cres_vs_mediana')!
    const m: MunicipioComparavel = {
      nome: 'X', porPasso: {}, crescimento: { emp: 8.7, uf_mediana: 7.6 },
    }
    expect(dim.ler(m)).toBeCloseTo(1.1, 5)
    expect(dim.ler(m)).not.toBe(8.7)
  })

  it('sem mediana estadual, a dimensao de crescimento nao existe', () => {
    const dim = DIMENSOES_MUNICIPIO.find((d) => d.chave === 'cres_vs_mediana')!
    const m: MunicipioComparavel = { nome: 'X', porPasso: {}, crescimento: { emp: 99 } }
    expect(dim.ler(m)).toBeNull()
  })
})

describe('compararMunicipios', () => {
  it('usa o mesmo nucleo dos hexagonos — limiares e frase iguais', () => {
    const ps = passos()
    const a = montarMunicipio('Goiânia', ps, CRES)
    const b = montarMunicipio('Anápolis', ps, CRES)
    const c = compararMunicipios(a, b)

    expect(c.vencedor).toBe('a')
    expect(c.frase).toContain('Goiânia')
    expect(c.frase).toContain('mais residual na fila')
    expect(c.frase).toContain('Goiânia leva a comparação.')
  })

  it('no maximo 3 dimensoes na frase, como nos hexagonos', () => {
    const ps = passos()
    const c = compararMunicipios(
      montarMunicipio('Goiânia', ps, CRES),
      montarMunicipio('Anápolis', ps, CRES),
    )
    expect(c.destaques.length).toBeLessThanOrEqual(3)
  })

  it('dimensao ausente nos dois lados nao entra', () => {
    const ps = passos()
    // Nenhum dos dois está no passo 4 -> aquela dimensão fica fora.
    const c = compararMunicipios(
      montarMunicipio('Goiânia', ps, CRES),
      montarMunicipio('Anápolis', ps, CRES),
    )
    for (const d of c.destaques) expect(d.a).not.toBeNull()
  })

  it('equivalentes devolvem a frase de empate', () => {
    const ps = passos()
    const a = montarMunicipio('Goiânia', ps, CRES)
    const c = compararMunicipios(a, { ...a, nome: 'Clone' })
    expect(c.vencedor).toBe('empate')
    expect(c.frase).toContain('equivalentes')
  })
})
