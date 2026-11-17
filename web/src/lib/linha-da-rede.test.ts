import { describe, expect, it } from 'vitest'

import { chaveDaQuery, linhaDaRede, temTotalDaRede } from './exec'
import type { RedeLinhaRede } from './types'

const REDE: RedeLinhaRede = {
  media: {
    faturamento: { atual: 180_000, m1: 175_000, delta_pct: 2.9 },
    churn_pct: { atual: 5.2, m1: 5.0, delta_pct: 4 },
  },
  total: {
    faturamento: { atual: 16_200_000, m1: 15_900_000, delta_pct: 1.9 },
    churn_pct: { atual: 4.8, m1: 4.9, delta_pct: -2 },
  },
  n_unidades: 92,
  n_comparaveis: 90,
}

describe('linhaDaRede — média e total da rede na Carteira', () => {
  it('a média é por unidade e diz quantas comparáveis entram', () => {
    const l = linhaDaRede(REDE, 'media')
    expect(l?.rotulo).toBe('Média da rede')
    expect(l?.detalhe).toBe('por unidade · 90 comparáveis')
    expect(l?.metricas.faturamento.atual).toBe(180_000)
  })

  it('o total é a rede inteira, com churn e NPS ponderados', () => {
    const l = linhaDaRede(REDE, 'total')
    expect(l?.rotulo).toBe('Total da rede')
    expect(l?.detalhe).toBe('92 unidades · churn e NPS ponderados')
    expect(l?.metricas.faturamento.atual).toBe(16_200_000)
    expect(l?.metricas.churn_pct.delta_pct).toBe(-2)
  })

  it('com mês fechado no período, o total diz que o churn é o Churn Médio (DEC-088)', () => {
    // O churn do total passa a ser a média dos pontos mensais da rede: dizer "churn
    // ponderado" seria mentir. O NPS continua ponderado.
    const l = linhaDaRede(REDE, 'total', true)
    expect(l?.detalhe).toBe('92 unidades · Churn Médio dos meses fechados, NPS ponderado')
    expect(linhaDaRede(REDE, 'total', false)?.detalhe).toBe('92 unidades · churn e NPS ponderados')
    // A média por unidade não muda de detalhe.
    expect(linhaDaRede(REDE, 'media', true)?.detalhe).toBe('por unidade · 90 comparáveis')
  })

  it('ranking e % vs média não existem para a própria rede', () => {
    const m = linhaDaRede(REDE, 'media')?.metricas.churn_pct
    expect(m).toMatchObject({ rank: null, rank_total: null, vs_media_pct: null })
  })

  it('servidor sem o campo: sem linha (não inventa a média no cliente)', () => {
    expect(linhaDaRede(undefined, 'media')).toBeNull()
  })
})

describe('linhaDaRede — perfil master (DEC-087): o payload vem sem o total', () => {
  const SEM_TOTAL: RedeLinhaRede = { media: REDE.media, n_unidades: 92, n_comparaveis: 90 }

  it('sem a chave `total`, a opção Total não existe', () => {
    expect(temTotalDaRede(SEM_TOTAL)).toBe(false)
    expect(temTotalDaRede({ ...SEM_TOTAL, total: null })).toBe(false)
    expect(temTotalDaRede(REDE)).toBe(true)
    expect(temTotalDaRede(undefined)).toBe(false)
  })

  it('pedir "total" sem o total no payload cai na média, nunca numa linha "Total da rede"', () => {
    const l = linhaDaRede(SEM_TOTAL, 'total')
    expect(l?.rotulo).toBe('Média da rede')
    expect(l?.metricas.faturamento.atual).toBe(180_000)
  })
})

describe('chaveDaQuery — o mesmo recorte vira a mesma chave', () => {
  it('ignora campo vazio e a ordem das chaves', () => {
    expect(chaveDaQuery({ uf: 'SP', inicio: '2026-10-01', master: undefined, coorte: '' })).toBe(
      chaveDaQuery({ inicio: '2026-10-01', uf: 'SP' }),
    )
  })

  it('período ou filtro diferente vira chave diferente', () => {
    const base = { inicio: '2026-10-01', fim: '2026-10-31' }
    expect(chaveDaQuery(base)).not.toBe(chaveDaQuery({ ...base, fim: '2026-10-30' }))
    expect(chaveDaQuery(base)).not.toBe(chaveDaQuery({ ...base, uf: 'RJ' }))
  })
})
