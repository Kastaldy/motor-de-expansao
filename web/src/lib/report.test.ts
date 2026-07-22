import { describe, expect, it } from 'vitest'
import { viabilidadeParaPdf } from './report'
import type { ViabilidadeOut } from './types'

function make(over: Partial<ViabilidadeOut> = {}): ViabilidadeOut {
  return {
    demanda_premissa: 1600,
    demanda_fonte: 'premissa',
    faixa_alunos: { p10: 900, p50: 1600, p90: 2200, n_comparaveis: 40 },
    alunos_breakeven: 1200,
    alunos_para_margem_alvo: 1400,
    aluguel_teto: { ideal: 45000, teto: 60000, excecao: 90000 },
    flag_fora_envelope: false,
    flag_zona_morta: false,
    motivo_zona_morta: null,
    split: { balcao: 1000, agregadores: 600 },
    dre: {
      faturamento: 300000,
      deducoes: 10000,
      impostos: 20000,
      custos: 170000,
      ebitda: 100000,
      lucro_liquido: 80000,
      margem: 34.57, // PERCENTUAL (como o backend manda)
      payback: 28,
      roic: 0.18, // FRAÇÃO
      flag_viavel: true,
    },
    fcf_serie: [],
    fco_serie: [],
    mes_operacao_positiva: 10,
    carencia_aluguel_meses: 0,
    melhoria_payback: null,
    grade: [],
    ...over,
  }
}

describe('viabilidadeParaPdf', () => {
  it('emite EXATAMENTE as chaves do contrato do gerador (censo_report._viabilidade_page)', () => {
    const chaves = Object.keys(viabilidadeParaPdf(make())).sort()
    const esperadas = [
      'alunos_breakeven',
      'aluguel_teto',
      'ebitda_mensal',
      'faixa_p10',
      'faixa_p90',
      'faturamento_mensal',
      'flag_fora_envelope',
      'flag_viavel',
      'margem_ebitda_pct',
      'payback_meses',
      'roic_anual',
    ].sort()
    expect(chaves).toEqual(esperadas)
  })

  it('margem vem em PERCENTUAL do backend e sai em FRAÇÃO (o gerador faz *100)', () => {
    expect(viabilidadeParaPdf(make()).margem_ebitda_pct).toBeCloseTo(0.3457, 6)
  })

  it('roic já é fração -> envia direto', () => {
    expect(viabilidadeParaPdf(make()).roic_anual).toBe(0.18)
  })

  it('aluguel_teto usa o cluster "Teto" (20%), não ideal/exceção', () => {
    expect(viabilidadeParaPdf(make()).aluguel_teto).toBe(60000)
  })

  it('R$ e alunos passam sem conversão; flags idem', () => {
    const d = viabilidadeParaPdf(make())
    expect(d.faturamento_mensal).toBe(300000)
    expect(d.ebitda_mensal).toBe(100000)
    expect(d.faixa_p10).toBe(900)
    expect(d.faixa_p90).toBe(2200)
    expect(d.payback_meses).toBe(28)
    expect(d.alunos_breakeven).toBe(1200)
    expect(d.flag_viavel).toBe(true)
    expect(d.flag_fora_envelope).toBe(false)
  })

  it('nulos degradam sem quebrar (margem/teto ausentes -> null)', () => {
    const d = viabilidadeParaPdf(
      make({ aluguel_teto: null, dre: { ...make().dre, margem: null } }),
    )
    expect(d.aluguel_teto).toBeNull()
    expect(d.margem_ebitda_pct).toBeNull()
  })
})
