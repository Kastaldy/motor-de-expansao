import { describe, expect, it } from 'vitest'

import {
  TOP_POR_CAMADA,
  consolidar,
  fraseConsolidada,
  topPorCamada,
} from './consolidado'
import type { Passo } from './types'

/** Passos com a forma real do payload de UF: um `valor` por cidade, por camada. */
function passo(n: number, titulo: string, cidades: string[]): Passo {
  return {
    n,
    titulo,
    metrica: 'residual',
    itens: cidades.map((c, i) => ({
      rank: i + 1,
      titulo: c,
      municipio: c,
      valor: 1000 - i,
      label: 'residual',
    })),
  } as unknown as Passo
}

/** GO simplificado: Goiânia forte em tudo, Jataí só numa camada. */
function funil(): Passo[] {
  return [
    passo(1, 'Potencial socioeconômico', ['Goiânia', 'Anápolis', 'Rio Verde', 'A', 'B']),
    passo(2, 'Demanda não atendida', ['Goiânia', 'Anápolis', 'C', 'D', 'E']),
    passo(3, 'Pressão concorrencial', ['Goiânia', 'Rio Verde', 'F', 'G', 'H']),
    passo(4, 'Como as cidades estão indo', ['Jataí', 'Goiânia', 'I', 'J', 'K']),
    passo(5, 'Para onde crescer', ['Goiânia', 'Anápolis', 'Rio Verde', 'L', 'M']),
  ]
}

describe('topPorCamada', () => {
  it('corta cada camada no top 5, sem reordenar', () => {
    const ps = [passo(1, 'X', ['a', 'b', 'c', 'd', 'e', 'f', 'g'])]
    const t = topPorCamada(ps)
    expect(t[0].itens).toHaveLength(TOP_POR_CAMADA)
    expect(t[0].itens.map((i) => i.titulo)).toEqual(['a', 'b', 'c', 'd', 'e'])
  })
})

describe('consolidar — CONTAGEM, nunca score novo', () => {
  it('quem aparece em mais camadas vem primeiro', () => {
    const c = consolidar(funil())
    expect(c[0].nome).toBe('Goiânia')
    expect(c[0].presencas).toHaveLength(5)
  })

  it('guarda QUAIS camadas, para a leitura ter lastro', () => {
    const g = consolidar(funil())[0]
    expect(g.presencas.map((p) => p.n)).toEqual([1, 2, 3, 4, 5])
    expect(g.presencas[3].titulo).toBe('Como as cidades estão indo')
    expect(g.presencas[3].posicao).toBe(2) // 2º no passo 4
  })

  it('cidade de uma camada so NAO entra na leitura consolidada', () => {
    // Jatai aparece so no passo 4 — e um destaque pontual, ja visivel no cartao dele.
    const c = consolidar(funil())
    expect(c.some((x) => x.nome === 'Jataí')).toBe(false)
  })

  it('minPresencas=1 deixa entrar o destaque pontual', () => {
    const c = consolidar(funil(), 1)
    expect(c.some((x) => x.nome === 'Jataí')).toBe(true)
  })

  it('desempata pela FILA OFICIAL, nao por media inventada', () => {
    const c = consolidar(funil())
    const anapolis = c.find((x) => x.nome === 'Anápolis')!
    const rioVerde = c.find((x) => x.nome === 'Rio Verde')!
    // Ambas em 3 camadas; Anapolis e 2ª da fila e Rio Verde 3ª.
    expect(anapolis.presencas).toHaveLength(3)
    expect(rioVerde.presencas).toHaveLength(3)
    expect(c.indexOf(anapolis)).toBeLessThan(c.indexOf(rioVerde))
  })

  it('a posicao da fila vem da fila INTEIRA, nao so do top 5', () => {
    const ps = funil()
    // Cidade na 7ª posicao da fila, presente em 2 camadas do top 5.
    ps[4] = passo(5, 'Para onde crescer', ['a', 'b', 'c', 'd', 'e', 'f', 'Anápolis'])
    const anapolis = consolidar(ps).find((x) => x.nome === 'Anápolis')!
    expect(anapolis.posicaoFila).toBe(7)
  })

  it('cidade fora da fila fica com posicaoFila null e vai para tras', () => {
    const ps = funil()
    ps[4] = passo(5, 'Para onde crescer', ['Zzz'])
    const c = consolidar(ps)
    const g = c.find((x) => x.nome === 'Goiânia')!
    expect(g.posicaoFila).toBeNull()
  })

  it('funil vazio nao quebra', () => {
    expect(consolidar([])).toEqual([])
  })
})

describe('fraseConsolidada', () => {
  it('diz em quantas e QUAIS camadas, e a posicao na fila', () => {
    const g = consolidar(funil())[0]
    const f = fraseConsolidada(g, 5)
    expect(f).toContain('5 das 5 camadas')
    expect(f).toContain('potencial socioeconômico')
    expect(f).toContain('como as cidades estão indo')
    expect(f).toContain('1ª da fila de recomendação')
  })

  it('fora da fila diz isso, em vez de omitir — e sem inventar o motivo', () => {
    const ps = funil()
    ps[4] = passo(5, 'Para onde crescer', ['Zzz'])
    const g = consolidar(ps)[0]
    const f = fraseConsolidada(g, 5)
    expect(f).toContain('Não entra na fila de recomendação')
    // A frase AFIRMAVA a causa ("há concorrente mapeado no recorte"), e desde a
    // DEC-041 isso e' falso: ter concorrente nao tira ninguem da fila (so' saturacao
    // acima de `CONC_ADENSAR_MAX` tira), e um hexagono pode ficar de fora por
    // qualquer uma das camadas anteriores. Diagnosticar a causa aqui exigiria um dado
    // que esta funcao nao recebe — entao ela declara o fato e para.
    expect(f).not.toContain('concorrente mapeado')
  })

  it('e deterministica', () => {
    const g = consolidar(funil())[0]
    expect(fraseConsolidada(g, 5)).toBe(fraseConsolidada(g, 5))
  })
})
