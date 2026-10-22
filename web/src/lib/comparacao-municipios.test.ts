import { describe, expect, it } from 'vitest'

import {
  DIMENSOES_MUNICIPIO,
  DIMENSOES_MUNICIPIO_LEITURA,
  compararMunicipios,
  linhasLadoALado,
  montarMunicipio,
  municipiosDisponiveis,
  passosDeLeitura,
  type MunicipioComparavel,
} from './comparacao-municipios'
import { TEXTO_SEM_DADO } from './constants'
import { num, valorComUnidade } from './format'
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

/* ---------------------------------------------------------------------------------------
   MODO LEITURA — o payload COM o Top 10 (recomendação única, DEC-077). O passo 5 deixa de
   ser fila de municípios: os itens são HEXÁGONOS (bairro no `titulo`, `municipio` só para
   o drill-down) e o `valor` é o residual de um hexágono.
   --------------------------------------------------------------------------------------- */

/** Os mesmos passos de GO, com o passo 5 já no formato do Top 10 (itens de hexágono). */
function passosComTop10(): Passo[] {
  const base = passos().filter((p) => p.n !== 5)
  const top10 = {
    n: 5,
    titulo: 'Para onde crescer',
    itens: [
      { rank: 1, titulo: 'Setor Sul', municipio: 'Goiânia', valor: 9000, tipo_item: 'hex', segmento: 'mata_virgem' },
      { rank: 2, titulo: 'Jundiaí', municipio: 'Anápolis', valor: 41000, tipo_item: 'hex', segmento: 'premium' },
    ],
  } as unknown as Passo
  return [...base, top10]
}

describe('passosDeLeitura', () => {
  it('ignora o passo 5: nome de bairro do Top 10 não vira "cidade" no comparador', () => {
    const lidos = passosDeLeitura(passosComTop10())
    expect(lidos.map((p) => p.n)).toEqual([1, 2, 3, 4])
    expect(municipiosDisponiveis(lidos)).not.toContain('Setor Sul')
    expect(municipiosDisponiveis(lidos)).not.toContain('Jundiaí')
    // Contra-prova: lendo TODOS os passos, o bairro entraria como se fosse cidade.
    expect(municipiosDisponiveis(passosComTop10())).toContain('Setor Sul')
  })

  it('o residual de UM hexágono não vira o número da cidade', () => {
    const m = montarMunicipio('Goiânia', passosDeLeitura(passosComTop10()), CRES)
    expect(m.porPasso[5]).toBeUndefined()
    expect(m.porPasso[2]).toBe(85891)
  })
})

describe('DIMENSOES_MUNICIPIO_LEITURA', () => {
  it('sem a dimensão "Residual na fila", que lia o passo 5', () => {
    expect(DIMENSOES_MUNICIPIO_LEITURA.map((d) => d.chave)).toEqual([
      'residual_bruto',
      'hexes_quentes',
      'cres_vs_mediana',
    ])
    expect(DIMENSOES_MUNICIPIO_LEITURA.some((d) => d.rotulo.includes('fila'))).toBe(false)
  })

  it('o legado continua com ela, para a instância sem régua', () => {
    expect(DIMENSOES_MUNICIPIO[0].chave).toBe('residual_fila')
    expect(Object.isFrozen(DIMENSOES_MUNICIPIO_LEITURA)).toBe(true)
  })
})

describe('linhasLadoALado — números lado a lado, sem vencedor', () => {
  const lidos = passosDeLeitura(passosComTop10())
  const goiania = montarMunicipio('Goiânia', lidos, CRES)
  const anapolis = montarMunicipio('Anápolis', lidos, CRES)

  it('um valor por cidade, na ordem escolhida, formatado na unidade da dimensão', () => {
    const linhas = linhasLadoALado(DIMENSOES_MUNICIPIO_LEITURA, [goiania, anapolis])
    const demanda = linhas.find((l) => l.chave === 'residual_bruto')!
    expect(demanda.rotulo).toBe('Demanda não atendida')
    expect(demanda.valores).toEqual([num(85891), num(30120)])
    const cres = linhas.find((l) => l.chave === 'cres_vs_mediana')!
    expect(cres.valores).toEqual([valorComUnidade(8.7 - 7.6, 'p.p.'), valorComUnidade(5.0 - 7.6, 'p.p.')])
  })

  it('não declara vencedor nem perdedor: só chave, rótulo, unidade e valores', () => {
    for (const l of linhasLadoALado(DIMENSOES_MUNICIPIO_LEITURA, [goiania, anapolis])) {
      expect(Object.keys(l).sort()).toEqual(['chave', 'rotulo', 'unidade', 'valores'])
    }
  })

  it('cidade sem o número aparece como "sem dado", nunca zero', () => {
    const goianesia = montarMunicipio('Goianésia', lidos, CRES)
    const linhas = linhasLadoALado(DIMENSOES_MUNICIPIO_LEITURA, [goiania, goianesia])
    expect(linhas.find((l) => l.chave === 'residual_bruto')!.valores).toEqual([num(85891), TEXTO_SEM_DADO])
  })

  it('dimensão que nenhuma das cidades tem fica de fora', () => {
    const semNada: MunicipioComparavel = { nome: 'X', porPasso: {}, crescimento: null }
    const outro: MunicipioComparavel = { nome: 'Y', porPasso: {}, crescimento: null }
    expect(linhasLadoALado(DIMENSOES_MUNICIPIO_LEITURA, [semNada, outro])).toEqual([])
  })
})
