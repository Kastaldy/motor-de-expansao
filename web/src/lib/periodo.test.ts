// Fuso NEGATIVO antes de qualquer `Date`: é onde a aritmética de data quebra. Com
// hora local, `new Date('2026-08-01').getDate()` devolve 31 (de julho) em UTC-3, e um
// período que começa no dia 1º chegaria ao backend começando no mês anterior. O
// arquivo todo é UTC, então isto tem de ser indiferente — os testes de rótulo e de
// preset abaixo são justamente o que reprova se alguém trocar para hora local.
// (Onde o Node não honrar a troca em tempo de execução, o teste continua válido: ele
// vira o mesmo teste rodando no fuso da máquina.)
process.env.TZ = 'America/Sao_Paulo'

import { describe, expect, it } from 'vitest'

import {
  ajustarAoLimite,
  dataBr,
  diasDoPeriodo,
  ehData,
  ehMesInteiro,
  mesmoPeriodo,
  periodoDoMes,
  periodoValido,
  rotuloDoPeriodo,
  somarDias,
} from './periodo'

/** `hoje` fixo: nenhum teste aqui pode depender do dia em que roda. */
const HOJE = '2026-08-10'

const LIMITE = { min: '2024-01-01', max: '2026-08-10' }



describe('ehMesInteiro', () => {
  it('mês de 31 dias', () => {
    expect(ehMesInteiro({ inicio: '2026-07-01', fim: '2026-07-31' })).toBe(true)
  })
  it('fevereiro comum termina no dia 28', () => {
    expect(ehMesInteiro({ inicio: '2026-02-01', fim: '2026-02-28' })).toBe(true)
  })
  it('fevereiro BISSEXTO só é inteiro até o dia 29', () => {
    expect(ehMesInteiro({ inicio: '2024-02-01', fim: '2024-02-29' })).toBe(true)
    expect(ehMesInteiro({ inicio: '2024-02-01', fim: '2024-02-28' })).toBe(false)
  })
  it('29 de fevereiro em ano comum não existe — não é mês inteiro, é data inválida', () => {
    expect(ehData('2026-02-29')).toBe(false)
    expect(ehMesInteiro({ inicio: '2026-02-01', fim: '2026-02-29' })).toBe(false)
  })
  it('não começar no dia 1º ou não terminar no último derruba', () => {
    expect(ehMesInteiro({ inicio: '2026-07-02', fim: '2026-07-31' })).toBe(false)
    expect(ehMesInteiro({ inicio: '2026-07-01', fim: '2026-07-30' })).toBe(false)
  })
  it('meses diferentes nunca são um mês inteiro, mesmo cobrindo 1º ao último', () => {
    expect(ehMesInteiro({ inicio: '2026-07-01', fim: '2026-08-31' })).toBe(false)
  })
})

describe('rotuloDoPeriodo', () => {
  it('mês inteiro: só o mês e o ano', () => {
    expect(rotuloDoPeriodo({ inicio: '2026-07-01', fim: '2026-07-31' })).toBe('Julho/2026')
    expect(rotuloDoPeriodo({ inicio: '2024-02-01', fim: '2024-02-29' })).toBe('Fevereiro/2024')
  })
  it('dentro do mesmo mês: dias soltos, mês por extenso uma vez só', () => {
    expect(rotuloDoPeriodo({ inicio: '2026-08-01', fim: '2026-08-10' })).toBe(
      '1 a 10 de agosto/2026',
    )
  })
  it('um dia só não vira intervalo', () => {
    expect(rotuloDoPeriodo({ inicio: '2026-08-10', fim: '2026-08-10' })).toBe('10 de agosto/2026')
  })
  it('atravessando meses do mesmo ano: ano uma vez só, no fim', () => {
    expect(rotuloDoPeriodo({ inicio: '2026-07-15', fim: '2026-08-10' })).toBe(
      '15/07 a 10/08/2026',
    )
  })
  it('atravessando anos: data completa nas duas pontas', () => {
    expect(rotuloDoPeriodo({ inicio: '2025-12-15', fim: '2026-01-10' })).toBe(
      '15/12/2025 a 10/01/2026',
    )
  })
  it('período ilegível não fabrica rótulo', () => {
    expect(rotuloDoPeriodo({ inicio: '', fim: '2026-01-10' })).toBe('Período inválido')
    expect(rotuloDoPeriodo({ inicio: '2026-02-30', fim: '2026-03-10' })).toBe('Período inválido')
  })
})

describe('periodoValido', () => {
  it('período dentro do limite passa', () => {
    expect(periodoValido({ inicio: '2026-07-01', fim: '2026-07-31' }, LIMITE)).toEqual({ ok: true })
  })
  it('as pontas do limite são inclusivas', () => {
    expect(periodoValido({ inicio: LIMITE.min, fim: LIMITE.max }, LIMITE).ok).toBe(true)
  })
  it('fim antes do início reprova', () => {
    const r = periodoValido({ inicio: '2026-07-31', fim: '2026-07-01' }, LIMITE)
    expect(r.ok).toBe(false)
    expect(r.erro).toContain('anterior')
  })
  it('antes do primeiro dia com dado reprova, e a mensagem diz o que a base cobre', () => {
    const r = periodoValido({ inicio: '2023-12-31', fim: '2026-01-10' }, LIMITE)
    expect(r.ok).toBe(false)
    expect(r.erro).toContain('01/01/2024')
    expect(r.erro).toContain('10/08/2026')
  })
  it('depois do último dia com dado reprova', () => {
    expect(periodoValido({ inicio: '2026-08-01', fim: '2026-08-11' }, LIMITE).ok).toBe(false)
  })
  it('data incompleta (input pela metade) reprova sem estourar', () => {
    const r = periodoValido({ inicio: '2026-08', fim: '2026-08-10' }, LIMITE)
    expect(r.ok).toBe(false)
    expect(r.erro).toContain('Informe')
  })
  it('limite ilegível NÃO trava o operador', () => {
    expect(periodoValido({ inicio: '2026-08-01', fim: '2026-08-10' }, { min: '', max: '' }).ok).toBe(
      true,
    )
  })
})

describe('ajustarAoLimite', () => {
  it('grampeia as duas pontas', () => {
    expect(ajustarAoLimite({ inicio: '2020-01-01', fim: '2030-12-31' }, LIMITE)).toEqual({
      inicio: '2024-01-01',
      fim: '2026-08-10',
    })
  })
  it('não mexe em quem já cabe', () => {
    const p = { inicio: '2026-07-01', fim: '2026-07-31' }
    expect(ajustarAoLimite(p, LIMITE)).toEqual(p)
  })
  it('período inteiramente fora colapsa na borda mais próxima, sem inverter', () => {
    const r = ajustarAoLimite({ inicio: '2027-01-01', fim: '2027-02-01' }, LIMITE)
    expect(r).toEqual({ inicio: '2026-08-10', fim: '2026-08-10' })
    expect(periodoValido(r, LIMITE).ok).toBe(true)
  })
  it('o resultado nunca fica com fim antes do início', () => {
    const r = ajustarAoLimite({ inicio: '2023-01-01', fim: '2030-01-01' }, LIMITE)
    expect(diasDoPeriodo(r)).toBeGreaterThan(0)
  })
  it('limite ilegível devolve o período como veio', () => {
    const p = { inicio: '2026-07-01', fim: '2026-07-31' }
    expect(ajustarAoLimite(p, { min: 'x', max: 'y' })).toEqual(p)
  })
})

describe('diasDoPeriodo', () => {
  it('conta as DUAS pontas: um dia só é 1', () => {
    expect(diasDoPeriodo({ inicio: '2026-08-10', fim: '2026-08-10' })).toBe(1)
  })
  it('mês de 31 dias dá 31', () => {
    expect(diasDoPeriodo({ inicio: '2026-08-01', fim: '2026-08-31' })).toBe(31)
  })
  it('o 29 de fevereiro entra na conta do ano bissexto', () => {
    expect(diasDoPeriodo({ inicio: '2024-02-28', fim: '2024-03-01' })).toBe(3)
    expect(diasDoPeriodo({ inicio: '2026-02-28', fim: '2026-03-01' })).toBe(2)
  })
  it('ano inteiro: 365 dias, 366 no bissexto', () => {
    expect(diasDoPeriodo({ inicio: '2026-01-01', fim: '2026-12-31' })).toBe(365)
    expect(diasDoPeriodo({ inicio: '2024-01-01', fim: '2024-12-31' })).toBe(366)
  })
  it('a virada do horário de verão não come nem inventa dia (conta em UTC)', () => {
    // 2018-11-04 foi a última virada de horário de verão no Brasil; em hora local o
    // dia tem 23h e a divisão por 86.400.000 daria 30,96 dias.
    expect(diasDoPeriodo({ inicio: '2018-10-15', fim: '2018-11-14' })).toBe(31)
    expect(somarDias('2018-11-03', 1)).toBe('2018-11-04')
  })
  it('período invertido ou ilegível não tem dia nenhum', () => {
    expect(diasDoPeriodo({ inicio: '2026-08-31', fim: '2026-08-01' })).toBe(0)
    expect(diasDoPeriodo({ inicio: '', fim: '2026-08-01' })).toBe(0)
  })
})


describe('mesmoPeriodo', () => {
  it('mesmo dia, mesmo período (espaço em volta não conta)', () => {
    expect(
      mesmoPeriodo({ inicio: ' 2026-08-01', fim: '2026-08-10 ' }, { inicio: '2026-08-01', fim: '2026-08-10' }),
    ).toBe(true)
    expect(
      mesmoPeriodo({ inicio: '2026-08-01', fim: '2026-08-10' }, { inicio: '2026-08-01', fim: '2026-08-11' }),
    ).toBe(false)
  })
  it('período ilegível não é igual a ninguém, nem a outro ilegível', () => {
    // `mesmoPeriodo` decide se o campo digitado ainda é o período do pai. Devolver
    // `true` para lixo faria o rascunho ser dado por sincronizado no meio da digitação.
    expect(mesmoPeriodo({ inicio: '', fim: '' }, { inicio: '', fim: '' })).toBe(false)
    expect(
      mesmoPeriodo({ inicio: '2026-02-30', fim: '2026-08-10' }, { inicio: '2026-02-30', fim: '2026-08-10' }),
    ).toBe(false)
  })
})

describe('periodoDoMes e dataBr', () => {
  it('a competência antiga vira o mês inteiro', () => {
    expect(periodoDoMes('2026-07')).toEqual({ inicio: '2026-07-01', fim: '2026-07-31' })
    expect(periodoDoMes('2024-02')).toEqual({ inicio: '2024-02-01', fim: '2024-02-29' })
    expect(ehMesInteiro(periodoDoMes('2026-11'))).toBe(true)
  })
  it('competência ilegível não vira período', () => {
    expect(periodoDoMes('2026-13')).toEqual({ inicio: '', fim: '' })
    expect(periodoDoMes('')).toEqual({ inicio: '', fim: '' })
  })
  it('dataBr é dd/mm/aaaa e não inventa data', () => {
    expect(dataBr('2026-08-10')).toBe('10/08/2026')
    expect(dataBr('2026-02-30')).toBe('2026-02-30')
  })
})
