import { describe, expect, it } from 'vitest'
import { FAIXA_M1_HEX, FAIXA_M1_ORDEM, faixaM1ToColor, NA_FILL } from './colors'
import {
  alunosDaFaixa,
  CAPACIDADE_UNIDADE_ALUNOS,
  FAIXAS_DEMANDA,
  FAIXAS_POTENCIAL,
  faixasDoPasso,
  tituloDaLegenda,
} from './faixas'

describe('faixas nomeadas por camada', () => {
  // Tuplas de 1 elemento: `it.each` desestrutura o array externo, entao passar
  // [A, B] entregaria os ITENS de A como argumentos, nao A inteiro.
  it.each([[FAIXAS_POTENCIAL], [FAIXAS_DEMANDA]])(
    'cobrem 0-100 sem buraco nem sobreposicao',
    (faixas) => {
      expect(faixas[0].de).toBe(0)
      expect(faixas[faixas.length - 1].ate).toBe(100)
      for (let i = 1; i < faixas.length; i++) {
        // o `ate` de uma e o `de` da seguinte: sem lacuna (score cairia sem nome)
        // e sem sobreposicao (score teria dois nomes).
        expect(faixas[i].de).toBe(faixas[i - 1].ate)
      }
    },
  )

  it('camada 1 usa temperatura; camada 2 usa unidade — vocabularios distintos', () => {
    expect(FAIXAS_POTENCIAL.map((f) => f.nome)).toEqual([
      'Frio',
      'Morno',
      'Aquecido',
      'Quente',
      'Muito quente',
    ])
    expect(FAIXAS_DEMANDA.map((f) => f.nome)).toEqual([
      'Marginal',
      'Pouco espaço',
      'Meia unidade',
      'Quase cheia',
      'Unidade cheia',
    ])
    // O pedido do Juan foi explicito: os nomes VARIAM por camada.
    expect(FAIXAS_POTENCIAL.map((f) => f.nome)).not.toEqual(FAIXAS_DEMANDA.map((f) => f.nome))
  })

  it('camada 3 herda a 2 (mesma cor, mesmo score residual)', () => {
    expect(faixasDoPasso(3)).toBe(faixasDoPasso(2))
  })

  it('camada 4 nao usa rampa de score — colore pela faixa do M1', () => {
    expect(faixasDoPasso(4)).toBeNull()
    expect(tituloDaLegenda(4)).toBe('Faixa de oportunidade M1')
  })
})

describe('leitura em alunos da camada de demanda', () => {
  it('ancora no 2.500 (capacidade de uma unidade)', () => {
    expect(CAPACIDADE_UNIDADE_ALUNOS).toBe(2500)
    // score 40-60 -> 1.000-1.500 alunos, ou seja "meia unidade" de verdade.
    expect(alunosDaFaixa(FAIXAS_DEMANDA[2])).toBe('1000–1500')
  })

  it('a ultima faixa e aberta porque o score e CLIPADO em 100', () => {
    // `score_oportunidade_residual` tem `.clip(upper=100)`: 2.500 e 10.000 alunos
    // marcam o mesmo 100. O rotulo nao pode prometer "mais de uma unidade".
    expect(alunosDaFaixa(FAIXAS_DEMANDA[4])).toBe('2000+ alunos')
  })
})

describe('cores da faixa M1', () => {
  it('todo rotulo da ordem tem cor definida', () => {
    for (const nome of FAIXA_M1_ORDEM) {
      expect(FAIXA_M1_HEX[nome]).toMatch(/^#[0-9A-F]{6}$/i)
    }
  })

  it('faixa ausente ou desconhecida cai no NA_FILL, sem inventar cor', () => {
    expect(faixaM1ToColor(null)).toEqual(NA_FILL)
    expect(faixaM1ToColor('Faixa Que Nao Existe')).toEqual(NA_FILL)
  })

  it('Prioridade máxima é o verde canonico do M1 (FAIXA_COLORS)', () => {
    expect(FAIXA_M1_HEX['Prioridade máxima']).toBe('#14C850')
    const [r, g, b, a] = faixaM1ToColor('Prioridade máxima', 115)
    expect([r, g, b]).toEqual([0x14, 0xc8, 0x50])
    expect(a).toBe(115)
  })
})
