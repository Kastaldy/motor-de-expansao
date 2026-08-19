import { describe, expect, it } from 'vitest'
import { alunos, brl, coord, distanciaCurta, num, pct, pctFrac, pctVar, rotuloMes } from './format'
import { TEXTO_SEM_DADO } from './constants'

describe('num', () => {
  it('formata inteiro com separador de milhar pt-BR', () => {
    expect(num(1234567)).toBe('1.234.567')
  })
  it('respeita casas decimais', () => {
    expect(num(1234.5, 2)).toBe('1.234,50')
  })
  it('zero e um numero valido (nao vira sem-dado)', () => {
    expect(num(0)).toBe('0')
  })
  it.each([null, undefined, NaN])('null/undefined/NaN -> sem-dado (nunca "0")', (v) => {
    expect(num(v)).toBe(TEXTO_SEM_DADO)
  })
})

describe('brl', () => {
  it('reais com milhar', () => {
    expect(brl(1500)).toBe('R$ 1.500')
  })
  it('compacto usa "mi" acima de 1 milhao', () => {
    expect(brl(1_500_000, true)).toBe('R$ 1,5 mi')
  })
  it('compacto usa "mil" acima de 1 mil', () => {
    expect(brl(2400, true)).toBe('R$ 2 mil')
  })
  it('compacto abaixo de 1 mil nao encurta', () => {
    expect(brl(999, true)).toBe('R$ 999')
  })
  it('casas exibe o centavo (ticket do agregador)', () => {
    expect(brl(88.2, false, 2)).toBe('R$ 88,20')
  })
  it('null -> sem-dado', () => {
    expect(brl(null)).toBe(TEXTO_SEM_DADO)
  })
})

describe('pct', () => {
  it('uma casa por padrao com sinal de %', () => {
    expect(pct(12.34)).toBe('12,3%')
  })
  it('zero formata (nao vira sem-dado)', () => {
    expect(pct(0)).toBe('0,0%')
  })
  it('null -> sem-dado', () => {
    expect(pct(null)).toBe(TEXTO_SEM_DADO)
  })
})

describe('pctFrac', () => {
  it('fracao do motor vira percentual na tela (0,3873 -> 38,7%)', () => {
    expect(pctFrac(0.3873)).toBe('38,7%')
  })
  it('sem casas para rotular mix (0,69 -> 69%)', () => {
    expect(pctFrac(0.69, 0)).toBe('69%')
  })
  it('negativo mantem o sinal', () => {
    expect(pctFrac(-0.05)).toBe('-5,0%')
  })
  it.each([null, undefined, NaN, Infinity])('null/NaN/Infinity -> sem-dado', (v) => {
    expect(pctFrac(v)).toBe(TEXTO_SEM_DADO)
  })
})

describe('pctVar', () => {
  it('positivo ganha o + que faltava (8,8 -> +8,8%)', () => {
    expect(pctVar(8.8)).toBe('+8,8%')
  })
  it('negativo mantem o sinal do Intl, sem duplicar', () => {
    expect(pctVar(-3.1)).toBe('-3,1%')
  })
  it('zero NAO recebe sinal: +0,0% afirmaria crescimento que nao houve', () => {
    expect(pctVar(0)).toBe('0,0%')
  })
  it('respeita as casas pedidas', () => {
    expect(pctVar(211.4, 0)).toBe('+211%')
  })
  it.each([null, undefined, NaN, Infinity])('null/NaN/Infinity -> sem-dado', (v) => {
    expect(pctVar(v)).toBe(TEXTO_SEM_DADO)
  })
  it('participacao segue sem sinal: o + fica so na variacao', () => {
    expect(pct(18)).toBe('18,0%')
  })
})

describe('rotuloMes', () => {
  it('mes negativo e pre-abertura (obra)', () => {
    expect(rotuloMes(-4)).toBe('M-4 (obra)')
  })
  it('mes positivo e operacao', () => {
    expect(rotuloMes(1)).toBe('mês 1')
  })
  it('null -> sem-dado', () => {
    expect(rotuloMes(null)).toBe(TEXTO_SEM_DADO)
  })
})

describe('coord', () => {
  it('5 casas, decimal com virgula, separado por virgula-espaco', () => {
    const s = coord(-15.7942, -47.8822)
    expect(s).toContain('15,79420')
    expect(s).toContain('47,88220')
    expect(s).toContain(', ')
  })
})

describe('alunos', () => {
  it('arredonda e formata inteiro', () => {
    expect(alunos(1234.6)).toBe('1.235')
  })
  it('null -> sem-dado', () => {
    expect(alunos(null)).toBe(TEXTO_SEM_DADO)
  })
})

describe('distanciaCurta — a unidade que o leitor usaria', () => {
  it('abaixo de 1 km sai em metros arredondados', () => {
    expect(distanciaCurta(0)).toBe('0 m')
    expect(distanciaCurta(847.4)).toBe('847 m')
    expect(distanciaCurta(999)).toBe('999 m')
  })

  it('de 1 km em diante sai em km com 2 casas', () => {
    expect(distanciaCurta(1000)).toBe('1,00 km')
    expect(distanciaCurta(1051)).toBe('1,05 km')
    expect(distanciaCurta(2000)).toBe('2,00 km')
  })

  it('ausencia continua ausencia, nunca "0 m"', () => {
    // `0 m` afirmaria "colado na porta" — a leitura mais alarmante possivel para um dado que
    // simplesmente nao foi medido.
    expect(distanciaCurta(null)).toBe(TEXTO_SEM_DADO)
    expect(distanciaCurta(undefined)).toBe(TEXTO_SEM_DADO)
    expect(distanciaCurta(Number.NaN)).toBe(TEXTO_SEM_DADO)
  })
})
