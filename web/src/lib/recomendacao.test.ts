import { describe, expect, it } from 'vitest'

import {
  recomendar,
  type CriterioPonto,
  type EntradaRecomendacao,
  type ReguasPonto,
} from './recomendacao'

const REGUAS: ReguasPonto = {
  pop_minima: 5000,
  score_minimo: 70,
  renda_domiciliar_minima: 4500,
  area_min_m2: 1200,
  area_ideal_min_m2: 1500,
  area_ideal_max_m2: 2000,
  conc_regiao_disputada: 3,
}

function crit(chave: string, rotulo: string, passa: boolean | null, valor = 1): CriterioPonto {
  return { chave, rotulo, valor, regua: 0, unidade: '', maior_melhor: true, passa }
}

/** Entorno que passa em tudo — cada teste reprova só o que precisa. */
function base(over: Partial<EntradaRecomendacao> = {}): EntradaRecomendacao {
  return {
    criterios: [
      crit('populacao', 'População no raio', true, 66113),
      crit('renda_domiciliar', 'Renda domiciliar', true, 11452),
      crit('score', 'Potencial socioeconômico', true, 82),
      crit('residual', 'Residual disponível', true, 5000),
      crit('concorrentes', 'Concorrentes no raio', true, 0),
    ],
    reguas: REGUAS,
    viavel: null,
    m2: 1500,
    aluguel: 20000,
    tetoAluguel: 52597,
    melhoria: null,
    gradeSemViavel: false,
    ...over,
  }
}

describe('o que NAO se negocia vem primeiro', () => {
  it('entorno reprovado bloqueia, em vez de sugerir ajuste de contrato', () => {
    const a = recomendar(
      base({
        criterios: [
          crit('populacao', 'População no raio', false, 800),
          crit('renda_domiciliar', 'Renda domiciliar', true),
          crit('score', 'Potencial socioeconômico', true),
        ],
        viavel: false,
        melhoria: { alvo_meses: 36, reduzir_capex: 500000, reduzir_aluguel: 8000 },
      }),
    )
    expect(a[0].tipo).toBe('bloqueio')
    expect(a[0].titulo).toMatch(/não se resolve por negociação/i)
    expect(a[0].detalhe).toContain('população no raio')
  })

  it('lista TODOS os estruturais reprovados, nao so o primeiro', () => {
    const a = recomendar(
      base({
        criterios: [
          crit('populacao', 'População no raio', false),
          crit('score', 'Potencial socioeconômico', false),
          crit('residual', 'Residual disponível', false),
        ],
      }),
    )
    const d = a[0].detalhe
    expect(d).toContain('população no raio')
    expect(d).toContain('potencial socioeconômico')
    expect(d).toContain('residual disponível')
  })

  it('criterio SEM DADO nao conta como reprovado', () => {
    const a = recomendar(
      base({ criterios: [crit('populacao', 'População no raio', null)] }),
    )
    expect(a.every((x) => x.tipo !== 'bloqueio')).toBe(true)
  })
})

describe('concorrencia — regra de bolso, nunca calculo de metragem', () => {
  it('avisa a partir do limiar e diz que e regra de bolso', () => {
    const a = recomendar(
      base({ criterios: [crit('concorrentes', 'Concorrentes no raio', false, 17)] }),
    )
    const aviso = a.find((x) => x.tipo === 'aviso')!
    expect(aviso.titulo).toMatch(/disputada/i)
    expect(aviso.detalhe).toContain('17 concorrentes')
    expect(aviso.detalhe).toContain('2.000 m²') // topo da faixa ideal
    // O texto PRECISA declarar que nao e calculo — derivar m2 da geografia viola a DEC-009.
    expect(aviso.detalhe).toMatch(/regra de bolso/i)
    expect(aviso.detalhe).toMatch(/não tem a metragem dos concorrentes/i)
  })

  it('abaixo do limiar nao avisa', () => {
    const a = recomendar(
      base({ criterios: [crit('concorrentes', 'Concorrentes no raio', true, 2)] }),
    )
    expect(a.some((x) => x.tipo === 'aviso')).toBe(false)
  })
})

describe('acoes de contrato — vem do motor, nao da tela', () => {
  it('traduz reduzir_aluguel em um ALVO, nao num delta solto', () => {
    const a = recomendar(
      base({
        viavel: false,
        aluguel: 60000,
        melhoria: { alvo_meses: 36, reduzir_capex: null, reduzir_aluguel: 48631 },
      }),
    )
    const acao = a.find((x) => x.tipo === 'acao')!
    expect(acao.titulo).toContain('R$ 11.369') // 60.000 - 48.631
    expect(acao.detalhe).toContain('R$ 48.631')
    expect(acao.detalhe).toContain('36 meses')
  })

  it('oferece o corte de CAPEX como alternativa', () => {
    const a = recomendar(
      base({
        viavel: false,
        melhoria: { alvo_meses: 36, reduzir_capex: 1750703, reduzir_aluguel: 48631 },
      }),
    )
    const capex = a.find((x) => x.titulo.includes('da obra'))!
    expect(capex.titulo).toContain('R$ 1.750.703')
    expect(capex.detalhe).toMatch(/alternativa/i)
  })

  it('nunca sugere aluguel negativo', () => {
    const a = recomendar(
      base({
        viavel: false,
        aluguel: 5000,
        melhoria: { alvo_meses: 36, reduzir_capex: null, reduzir_aluguel: 48631 },
      }),
    )
    expect(a.find((x) => x.tipo === 'acao')!.titulo).toContain('R$ 0')
  })

  it('sem sugestao do motor, usa o teto como alvo', () => {
    const a = recomendar(base({ viavel: false, aluguel: 90000, tetoAluguel: 52597 }))
    const acao = a.find((x) => x.titulo.includes('acima do teto'))!
    expect(acao.detalhe).toContain('R$ 90.000')
    expect(acao.detalhe).toContain('R$ 52.597')
  })

  it('aluguel abaixo do teto nao vira acao', () => {
    const a = recomendar(base({ viavel: false, aluguel: 20000, tetoAluguel: 52597 }))
    expect(a.some((x) => x.titulo.includes('acima do teto'))).toBe(false)
  })

  it('metragem abaixo do minimo da rede', () => {
    const a = recomendar(base({ viavel: false, m2: 900 }))
    const acao = a.find((x) => x.titulo.includes('Metragem abaixo'))!
    expect(acao.titulo).toContain('1.200 m²')
    expect(acao.detalhe).toContain('900 m²')
  })

  it('grade sem nenhum cenario viavel vira BLOQUEIO, nao acao', () => {
    const a = recomendar(base({ viavel: false, gradeSemViavel: true }))
    const b = a.find((x) => x.tipo === 'bloqueio')!
    expect(b.titulo).toMatch(/Nenhum cenário testado/i)
    expect(b.detalhe).toMatch(/não é o preço do contrato/i)
  })
})

describe('nada a corrigir', () => {
  it('viavel devolve ok', () => {
    const a = recomendar(base({ viavel: true }))
    expect(a).toHaveLength(1)
    expect(a[0].tipo).toBe('ok')
    expect(a[0].titulo).toMatch(/Fecha a conta/i)
  })

  it('sem viabilidade calculada, convida a calcular em vez de opinar', () => {
    const a = recomendar(base({ viavel: null }))
    expect(a[0].tipo).toBe('ok')
    expect(a[0].detalhe).toMatch(/Calcule a viabilidade/i)
  })

  it('viabilidade NAO calculada nao gera acao de contrato', () => {
    const a = recomendar(
      base({ viavel: null, melhoria: { alvo_meses: 36, reduzir_capex: 1, reduzir_aluguel: 1 } }),
    )
    expect(a.some((x) => x.tipo === 'acao')).toBe(false)
  })
})
