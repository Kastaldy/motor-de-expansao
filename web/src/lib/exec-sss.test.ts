/**
 * SSS com maturação mínima no ano-base (DEC-088): os textos que separam "não existia há
 * um ano" de "estava em rampa", o aviso de base pequena e o rótulo da unidade em rampa no
 * "quem puxa e quem segura".
 *
 * Arquivo próprio, e não `exec.test.ts`, para a frente do SSS não disputar a mesma
 * fixture com quem mexe em churn e ranking no mesmo ciclo.
 */
import { describe, expect, it } from 'vitest'

import {
  destaquesDoRecorte,
  foraDaBaseSss,
  motivoSemBase,
  narrativaDoRecorte,
} from './exec'
import type { RedeCarteira, RedeSss, RedeUnidade } from './types'

function sss(p: Partial<RedeSss> = {}): RedeSss {
  return {
    disponivel: true,
    competencia_base: '2025-10',
    unidades: 60,
    unidades_recorte: 100,
    unidades_fora: 31,
    unidades_rampa: 9,
    unidades_base_zero: 0,
    maturacao_min_meses: 3,
    metricas: { faturamento: { atual: 16_195_471, ano_anterior: 16_696_362, var_pct: -3 } },
    serie: { meses: [], var_pct: [], unidades: [] },
    ...p,
  }
}

function carteira(s: RedeSss): RedeCarteira {
  return {
    mes: '2026-10',
    meses: ['2026-10'],
    periodo: { inicio: '2026-10-01', fim: '2026-10-31', dias: 31, mes_inteiro: true },
    periodo_anterior: { inicio: '2026-09-01', fim: '2026-09-30' },
    limites: { min: '2022-04-01', max: '2026-11-16' },
    referencia: '31/10/2026',
    referencia_m1: '30/09/2026',
    mes_completo: true,
    competencia_diagnostico: '2026-10',
    totais: { rede: 100, no_recorte: s.unidades_recorte, com_coordenada: 0 },
    kpis: {},
    split: { recorrentes: null, agregadores: null, pct_recorrentes: null, pct_agregadores: null },
    semaforo: { alta: 0, media: 0, ok: 0, sem_base: 0 },
    sss: s,
    centro: { lat: null, lng: null },
    bbox: null,
    ultra_icon: null,
    reguas: {},
    meta_nps: 75,
    serie_meses: [],
    serie_rede: [],
    series: {},
    funil: { visitas: null, convertidos: null, vendas: null, novos_alunos: null, conversao_pct: null, aviso: null },
    faixas: { competencia: '2026-10', faixas: [] },
    coortes: [],
    unidades: [],
    notas: [],
  } as RedeCarteira
}

function unidade(nome: string, p: Partial<RedeUnidade> = {}): RedeUnidade {
  return {
    id: nome.toLowerCase(),
    nome,
    uf: 'RJ',
    master: 'ULTRA',
    cidade: null,
    consultor: null,
    consultor_2: null,
    master_franquia: null,
    franqueado: null,
    coorte: '12_23',
    coorte_rotulo: '1 a 2 anos',
    meses_operacao: 14,
    inauguracao: '14/08/2025',
    lat: null,
    lng: null,
    comparavel: true,
    severidade: 'ok',
    severidade_rotulo: 'Sem alerta',
    prioridade: 0,
    resumo: '',
    faixa_faturamento: 'bom',
    faixa_faturamento_rotulo: 'Bom',
    alertas: [],
    metricas: {},
    sparkline: [],
    ...p,
  }
}

describe('foraDaBaseSss (card "Crescemos ou só abrimos loja?")', () => {
  it('separa quem não existia de quem estava em rampa — o texto da decisão de 17/11', () => {
    expect(foraDaBaseSss(sss())).toBe(
      '31 não existiam há um ano (ou não operaram o mês inteiro) e 9 ainda estavam nos 3 ' +
        'primeiros meses de operação no ano-base, a rampa de abertura, e ficam fora da conta.',
    )
  })

  it('sem rampa, é o texto de sempre', () => {
    expect(foraDaBaseSss(sss({ unidades_rampa: 0 }))).toBe(
      'As outras 31 não existiam há um ano, ou não operaram o mês inteiro nos dois períodos, ' +
        'e por isso ficam fora da conta.',
    )
    // No singular o verbo concorda ("operou"): a versão anterior dizia "operaram".
    expect(foraDaBaseSss(sss({ unidades_fora: 1, unidades_rampa: 0 }))).toBe(
      'A outra não existia há um ano, ou não operou o mês inteiro nos dois períodos, e por ' +
        'isso fica fora da conta.',
    )
  })

  it('payload anterior à DEC-088 (sem os campos novos) sai como antes', () => {
    const antigo = sss({ unidades_rampa: undefined, unidades_base_zero: undefined, maturacao_min_meses: undefined })
    expect(foraDaBaseSss(antigo)).toContain('As outras 31 não existiam há um ano')
  })

  it('só rampa: "as outras N", no singular quando é uma', () => {
    expect(foraDaBaseSss(sss({ unidades_fora: 0, unidades_rampa: 9 }))).toBe(
      'As outras 9 ainda estavam nos 3 primeiros meses de operação no ano-base, a rampa de ' +
        'abertura, e ficam fora da conta.',
    )
    expect(foraDaBaseSss(sss({ unidades_fora: 0, unidades_rampa: 1 }))).toBe(
      'A outra ainda estava nos 3 primeiros meses de operação no ano-base, a rampa de ' +
        'abertura, e fica fora da conta.',
    )
  })

  it('a maturação vem do servidor, não do texto', () => {
    expect(foraDaBaseSss(sss({ maturacao_min_meses: 6 }))).toContain('nos 6 primeiros meses')
  })

  it('base zero não é chamada de rampa', () => {
    const frase = foraDaBaseSss(sss({ unidades_rampa: 10, unidades_base_zero: 1 })) ?? ''
    expect(frase).toContain('e 9 ainda estavam nos 3 primeiros meses')
    expect(frase).toContain('Outra não faturou no ano-base e também fica fora.')
    expect(foraDaBaseSss(sss({ unidades_fora: 0, unidades_rampa: 2, unidades_base_zero: 2 }))).toBe(
      'As outras 2 não faturaram no ano-base e ficam fora da conta.',
    )
  })

  it('"as outras N" só com UM motivo: com dois, cada motivo leva o seu número', () => {
    // fora=31, rampa=1 (que é a base zero), zero=1: "As outras 31" diria que as de fora são
    // 31, e são 32.
    expect(foraDaBaseSss(sss({ unidades_fora: 31, unidades_rampa: 1, unidades_base_zero: 1 }))).toBe(
      '31 não existiam há um ano, ou não operaram o mês inteiro nos dois períodos, e por isso ' +
        'ficam fora da conta. Outra não faturou no ano-base e também fica fora.',
    )
    // fora=0, rampa=10 (9 em rampa + 1 base zero): "As outras 9" diria 9 de 10.
    expect(foraDaBaseSss(sss({ unidades_fora: 0, unidades_rampa: 10, unidades_base_zero: 1 }))).toBe(
      '9 ainda estavam nos 3 primeiros meses de operação no ano-base, a rampa de abertura, e ' +
        'ficam fora da conta. Outra não faturou no ano-base e também fica fora.',
    )
  })

  it('sem ninguém na base (SSS indisponível), não fala em "as outras"', () => {
    const vazio = sss({ disponivel: false, unidades: 0, unidades_recorte: 2, unidades_fora: 0, unidades_rampa: 2 })
    expect(foraDaBaseSss(vazio)).toBe(
      '2 ainda estavam nos 3 primeiros meses de operação no ano-base, a rampa de abertura, e ' +
        'ficam fora da conta.',
    )
  })

  it('ninguém de fora, nenhuma frase', () => {
    expect(foraDaBaseSss(sss({ unidades: 100, unidades_fora: 0, unidades_rampa: 0 }))).toBeNull()
  })
})

describe('narrativaDoRecorte com a maturação do SSS', () => {
  it('diz quantas não existiam e quantas estavam em rampa, cada uma com o seu número', () => {
    expect(narrativaDoRecorte(carteira(sss()), 'a rede')[1]).toBe(
      'Na mesma base (60 das 100 unidades), o faturamento cai 3,0% contra Out/2025; 31 não ' +
        'existiam há um ano e 9 estavam na rampa de abertura (menos de 3 meses de operação no ' +
        'ano-base).',
    )
  })

  it('base pequena sai sem aviso: o número fala por si (Felipe, 17/11/2026)', () => {
    const frase = narrativaDoRecorte(
      carteira(sss({ unidades: 3, unidades_recorte: 10, unidades_fora: 5, unidades_rampa: 2 })),
      'DALMO',
    )[1]
    expect(frase).toContain('Na mesma base (3 das 10 unidades)')
    expect(frase).not.toContain('base pequena')
    expect(frase).toContain('5 não existiam há um ano e 2 estavam na rampa de abertura')
  })

  it('SSS indisponível por rampa não diz que "nenhuma operou o mês inteiro"', () => {
    const frase = narrativaDoRecorte(
      carteira(
        sss({
          disponivel: false,
          unidades: 0,
          unidades_recorte: 3,
          unidades_fora: 2,
          unidades_rampa: 1,
          metricas: undefined,
        }),
      ),
      'uma coorte nova',
    )[1]
    expect(frase).toBe(
      'Não há base comparável neste recorte contra Out/2025: 2 não existiam há um ano e 1 estava ' +
        'na rampa de abertura (menos de 3 meses de operação no ano-base), então o crescimento ' +
        'na mesma base não é medido.',
    )
  })
})

describe('quem puxa e quem segura com a unidade em rampa', () => {
  const emRampa = unidade('ICARAI', {
    sss: { competencia_base: '2025-10', faturamento: 420_000, ano_anterior: 370_340, var_pct: null, motivo: 'em_rampa' },
  })
  const madura = unidade('BOTAFOGO', {
    sss: { competencia_base: '2025-10', faturamento: 400_000, ano_anterior: 380_000, var_pct: 5.3, motivo: null },
  })

  it('a unidade em rampa sai da conta e fica à vista em "sem base"', () => {
    const { puxam, semBase } = destaquesDoRecorte([emRampa, madura], 'sss')
    expect(puxam.map((d) => d.unidade.nome)).toEqual(['BOTAFOGO'])
    expect(semBase.map((u) => u.nome)).toEqual(['ICARAI'])
  })

  it('rótulo próprio na leitura ano a ano, separado de "não existia há um ano"', () => {
    expect(motivoSemBase(emRampa, 'sss')).toBe('fora da base (em rampa)')
    const zerada = unidade('ZERADA', {
      sss: { competencia_base: '2025-10', faturamento: 60_000, ano_anterior: 0, var_pct: null, motivo: 'base_zero' },
    })
    expect(motivoSemBase(zerada, 'sss')).toBe('fora da base (sem faturamento no ano-base)')
    const semAno = unidade('SEM ANO', {
      sss: { competencia_base: '2025-10', faturamento: 60_000, ano_anterior: null, var_pct: null, motivo: 'sem_ano_anterior' },
    })
    expect(motivoSemBase(semAno, 'sss')).toBe('não operou o período inteiro há um ano')
    expect(motivoSemBase(unidade('NOVA', { comparavel: false }), 'sss')).toBe('unidade nova')
  })

  it('na leitura mês contra mês, a rampa do ano-base não vira rótulo', () => {
    expect(motivoSemBase(emRampa, 'mes')).toBe('não operou o período inteiro há um ano')
  })
})
