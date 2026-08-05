import { describe, expect, it } from 'vitest'

import { parseDims, parseSeries } from './crescimento'

/* Parser dos campos codificados do passo 4. E' a unica peca entre o payload e o
   grafico na tela, e vivia dentro do `NarrativePanel` sem teste nenhum.

   O que importa aqui nao e o caminho feliz — e o comportamento diante de bloco torto:
   um municipio com um campo ruim nao pode derrubar a tela dos outros quatro. */

describe('parseDims', () => {
  it('lê o formato real do artefato, com período', () => {
    const linhas = parseDims('Renda:25.8:%:25:2020→2024;Emprego:8.8:%:59:2022→jun/2026')
    expect(linhas).toEqual([
      { nome: 'Renda', valor: 25.8, unidade: '%', pos: 25, periodo: '2020→2024' },
      { nome: 'Emprego', valor: 8.8, unidade: '%', pos: 59, periodo: '2022→jun/2026' },
    ])
  })

  it('aceita bloco SEM período — ele entrou depois (10_periodo.py)', () => {
    expect(parseDims('Renda:25.8:%:25')).toEqual([
      { nome: 'Renda', valor: 25.8, unidade: '%', pos: 25, periodo: '' },
    ])
  })

  it('descarta o bloco torto e mantém os bons', () => {
    // 2 campos (curto demais), valor nao numerico, posicao nao numerica.
    const linhas = parseDims('Renda:25.8:%:25;Quebrado:1;Ruim:abc:%:10;Pos:1:%:xyz')
    expect(linhas.map((l) => l.nome)).toEqual(['Renda'])
  })

  it('string vazia devolve lista vazia, não estoura', () => {
    expect(parseDims('')).toEqual([])
  })

  it('valor negativo é dado válido — cidade pode encolher', () => {
    const [l] = parseDims('População:-1.1:%:47:2016→2021')
    expect(l.valor).toBe(-1.1)
  })

  it('unidade não numérica (/mil) sobrevive', () => {
    const [l] = parseDims('Empresas:110:/mil:99:2020→2025')
    expect(l).toMatchObject({ unidade: '/mil', valor: 110, pos: 99 })
  })
})

describe('parseSeries', () => {
  it('lê o formato real do artefato', () => {
    expect(parseSeries('Renda|R$|2020|2024|3243,3500,3900,4200,4643')).toEqual([
      {
        nome: 'Renda',
        unidade: 'R$',
        ini: '2020',
        fim: '2024',
        valores: [3243, 3500, 3900, 4200, 4643],
      },
    ])
  })

  it('exige os 5 campos: bloco com 4 é descartado', () => {
    expect(parseSeries('Renda|R$|2020|3243,3500,3900')).toEqual([])
  })

  it('exige ao menos 3 pontos — com menos não há linha a desenhar', () => {
    expect(parseSeries('Renda|R$|2020|2024|3243,3500')).toEqual([])
    expect(parseSeries('Renda|R$|2020|2024|3243,3500,3900')).toHaveLength(1)
  })

  it('ponto não numérico some, e o bloco cai se sobrar menos de 3', () => {
    expect(parseSeries('Renda|R$|2020|2024|3243,x,3900,4200')).toEqual([
      { nome: 'Renda', unidade: 'R$', ini: '2020', fim: '2024', valores: [3243, 3900, 4200] },
    ])
    expect(parseSeries('Renda|R$|2020|2024|3243,x,y')).toEqual([])
  })

  it('um bloco torto não derruba os outros', () => {
    const s = 'Renda|R$|2020|2024|1,2,3;LIXO;Emprego|vínculos|2022|2026|10,20,30'
    expect(parseSeries(s).map((x) => x.nome)).toEqual(['Renda', 'Emprego'])
  })

  it('string vazia devolve lista vazia, não estoura', () => {
    expect(parseSeries('')).toEqual([])
  })
})
