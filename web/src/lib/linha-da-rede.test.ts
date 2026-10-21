import { describe, expect, it } from 'vitest'

import { linhaDaRede } from './exec'
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

  it('ranking e % vs média não existem para a própria rede', () => {
    const m = linhaDaRede(REDE, 'media')?.metricas.churn_pct
    expect(m).toMatchObject({ rank: null, rank_total: null, vs_media_pct: null })
  })

  it('servidor sem o campo: sem linha (não inventa a média no cliente)', () => {
    expect(linhaDaRede(undefined, 'media')).toBeNull()
  })
})
