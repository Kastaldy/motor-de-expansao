import { describe, expect, it } from 'vitest'
import { infoImovelParaPdf, parametrosRelatorioPontual, viabilidadeParaPdf } from './report'
import { VIABILIDADE_PAYLOAD_VERSAO } from './types'
import type { SerieMensalLinha, ViabilidadeOut } from './types'

/** Linha da serie mensal como o motor entrega (campos do `_CAMPOS_LINHA`). */
function linha(over: Partial<SerieMensalLinha> = {}): SerieMensalLinha {
  return {
    mes: 1,
    mes_contrato: 5,
    fase: 'operacao',
    alunos_total: 500,
    alunos_balcao: 345,
    alunos_agregadores: 155,
    faturamento_mensal: 66_000,
    deducoes: 330,
    receita_liquida: 65_670,
    impostos: 4367,
    receita_pos_impostos: 61_303,
    custos_variaveis: 8570,
    folha: 11_220,
    outros_fixos: 38_150,
    aluguel: 30_000,
    custo_pre_operacional: 0,
    custos_op: 87_940,
    ebitda_mensal: -10_139.56,
    ir_csll: 4118.4,
    juros: 25_200,
    amortizacao: 13_148.75,
    pmt: 38_348.75,
    investimento: 0,
    fcf_mensal: -52_606.71,
    fcf_acumulado: -1_012_606.71,
    ...over,
  }
}

/** Payload v1 do caso golden (Boulevard Shopping Londrina), resumido. */
function make(over: Partial<ViabilidadeOut> = {}): ViabilidadeOut {
  return {
    versao: VIABILIDADE_PAYLOAD_VERSAO,
    premissas: {
      ticket_cheio: 147,
      ticket_agregador: 88.2,
      ticket_blended: 120.23,
      share_balcao: 0.69,
      ticket_agregador_fator: 0.6,
      // Folha FIXA desde o mes 1: `folha_pct` dimensiona pelo faturamento MADURO
      // (aqui = o proprio steady, porque a anuidade esta desligada e o reajuste so
      // comeca no mes 13) e o valor vale desde o mes 1 — nao acompanha a rampa.
      folha_pct: 0.17,
      folha_fixa_mes: 47_942.66,
      folha_base_faturamento_maduro: 282_015.62,
      folha_fixa_desde_mes_1: true,
      folha_regime: 'fixa_desde_mes_1_dimensionada_pelo_faturamento_maduro',
      deducoes_pct: 0.005,
      impostos_receita_pct: 0.0665,
      custo_variavel_pct: 0.1305,
      reajuste_ticket_aa: 0.04,
      reajuste_aluguel_aa: 0.04,
      reajuste_custos_aa: 0.04,
      taxa_desconto_aa: 0.12,
      carencia_aluguel_meses: 0,
      mes_inicio_aluguel: -4,
      custo_pre_operacional_mes: 0,
      maturacao_meses: 8,
      horizonte_meses: 60,
      // Anuidade DESLIGADA nesta fixture (`anuidade_valor: 0`), coerente com o bloco
      // `dre` abaixo, que e o snapshot sem a linha de anuidade. Com ela ligada
      // (R$ 99 UMA VEZ POR ANO por aluno de balcao que completa 12 meses) o mes de
      // referencia vira max(maturacao, anuidade_mes_inicio) = 12 — ver o teste
      // "a linha de anuidade viaja inteira ate o PDF".
      anuidade_valor: 0,
      anuidade_mes_inicio: 12,
      anuidade_apenas_balcao: true,
      // Elegibilidade DERIVADA do churn: (1-churn)^12 = 47,59%.
      anuidade_elegivel_pct: 0.4759,
      // Sem anuidade o regime pleno e a propria maturacao (8).
      mes_referencia_steady: 8,
      valor_residual_mes_60: 0,
      capex_renovacao: 0,
      fonte_base_calibracao: 'base_calibracao_unidades',
    },
    dre: {
      faturamento: 282_015.62,
      receita_anuidade: 0,
      deducoes: 1410.08,
      // Degraus intermediarios servidos PRONTOS pelo motor (a tela e o PDF nao
      // podem reconstrui-los por subtracao).
      receita_liquida: 280_605.54,
      impostos: 18_660.27,
      receita_pos_impostos: 261_945.27,
      custos_op: 152_711.68,
      custos_variaveis: 36_619.02,
      folha: 47_942.66,
      custos_fixos: 68_150,
      ebitda: 109_233.6,
      margem: 0.3873, // FRACAO — o payload nunca manda percentual
      ir_csll: 28_683.3,
      despesa_financeira: 21_600,
      resultado_apos_ir: 80_550.3,
      flag_viavel: true,
    },
    investimento: {
      obra: 600_000,
      equipamentos: 1_400_000,
      capex_total: 2_000_000,
      taxa_franquia: 160_000,
      investimento_total: 2_160_000,
      pmt: 38_348.75,
      juros_totais: 900_925.18,
      prazo_equipamentos: 60,
      juros_equipamentos_am: 0.018,
      parcelas_obra: 4,
      // Franquia PARCELADA 4x sem juros (M-4..M-1), nao a vista no M-4.
      parcelas_franquia: 4,
      franquia_parcela: 40_000,
    },
    retorno: {
      otica: 'desalavancada',
      retorno_anual_desalavancado: 0.4475,
      retorno_anual_equity: 0.3,
      tir_anual: 0.4221,
      vpl: 875_106.66,
      payback: 29,
    },
    break_even: { unidade: 'alunos_totais', ebitda: 859.6, caixa: 1366.7 },
    aluguel_teto: {
      base: 'faturamento_bruto',
      ideal: 42_302.34,
      teto: 56_403.12,
      excecao: 84_604.69,
      canonico: 84_604.69,
      teto_p10: 40_000,
    },
    faixa_alunos: { p10: 1500, p50: 2304, p90: 3034, n_comparaveis: 40 },
    serie_mensal: [linha()],
    mes_caixa_operacional_positivo: 6,
    acumulado_mes_final: 1_636_628.61,
    demanda_premissa: 2304,
    demanda_fonte: 'premissa_explicita',
    split: { balcao: 1589.76, agregadores: 714.24 },
    flag_fora_envelope: false,
    flag_zona_morta: false,
    motivo_zona_morta: null,
    grade: [],
    melhoria_payback: null,
    ...over,
  }
}

describe('viabilidadeParaPdf', () => {
  it('entrega o payload INTEIRO ao PDF — mesmo objeto da tela, sem remapear chave', () => {
    const payload = make()
    expect(viabilidadeParaPdf(payload)).toEqual({ ...payload })
  })

  it('carrega a versao do contrato (o gerador precisa poder recusar um desconhecido)', () => {
    expect(viabilidadeParaPdf(make()).versao).toBe('viabilidade_payload_v1')
  })

  it('NAO inventa chave derivada: nada de margem_ebitda_pct/roic_anual/lucro_liquido', () => {
    const chaves = Object.keys(viabilidadeParaPdf(make()))
    for (const proibida of [
      'margem_ebitda_pct',
      'roic_anual',
      'payback_meses',
      'alunos_breakeven',
      'lucro_liquido',
      'faixa_p10',
      'faixa_p90',
    ]) {
      expect(chaves).not.toContain(proibida)
    }
  })

  it('e copia rasa: mexer no retorno nao contamina o estado da tela', () => {
    const payload = make()
    const enviado = viabilidadeParaPdf(payload)
    enviado.demanda_premissa = 99
    expect(payload.demanda_premissa).toBe(2304)
  })

  it('a serie mensal viaja junto (o PDF desenha os graficos da MESMA serie)', () => {
    const enviado = viabilidadeParaPdf(make())
    expect((enviado.serie_mensal as SerieMensalLinha[]).length).toBe(1)
  })

  it('a linha de anuidade viaja inteira ate o PDF (nao pode sumir no caminho)', () => {
    const base = make()
    const payload = make({
      premissas: {
        ...base.premissas,
        anuidade_valor: 99,
        anuidade_mes_inicio: 12,
        anuidade_apenas_balcao: true,
        anuidade_elegivel_pct: 0.4759,
        // Regime pleno = max(maturacao 8, anuidade_mes_inicio 12).
        mes_referencia_steady: 12,
      },
      dre: { ...base.dre, faturamento: 288_257.57, receita_anuidade: 6241.94 },
    })
    const enviado = viabilidadeParaPdf(payload) as unknown as ViabilidadeOut
    expect(enviado.dre.receita_anuidade).toBe(6241.94)
    expect(enviado.premissas.anuidade_valor).toBe(99)
    expect(enviado.premissas.anuidade_elegivel_pct).toBe(0.4759)
    expect(enviado.premissas.anuidade_apenas_balcao).toBe(true)
    // O mes de referencia do steady vem SERVIDO — o PDF nao o recalcula de maturacao.
    expect(enviado.premissas.mes_referencia_steady).toBe(12)
    expect(enviado.premissas.maturacao_meses).toBe(8)
  })

  it('a folha FIXA e o parcelamento da franquia viajam ate o PDF (nao podem sumir)', () => {
    // Regressao do defeito "a folha esta escalando junto com a unidade": o PDF nao
    // pode reconstruir a folha multiplicando `folha_pct` pelo faturamento DO MES.
    // Ele le `folha_fixa_mes` (dimensionada pelo faturamento MADURO, paga desde o
    // mes 1) e o cronograma da franquia parcelada — ambos servidos pelo motor.
    const enviado = viabilidadeParaPdf(make()) as unknown as ViabilidadeOut
    expect(enviado.premissas.folha_fixa_mes).toBe(47_942.66)
    expect(enviado.premissas.folha_base_faturamento_maduro).toBe(282_015.62)
    expect(enviado.premissas.folha_fixa_desde_mes_1).toBe(true)
    expect(enviado.investimento.parcelas_franquia).toBe(4)
    expect(enviado.investimento.franquia_parcela).toBe(40_000)
  })

  it('os degraus intermediarios chegam prontos (sem subtracao no cliente)', () => {
    const enviado = viabilidadeParaPdf(make()) as unknown as ViabilidadeOut
    expect(enviado.dre.receita_liquida).toBe(280_605.54)
    expect(enviado.dre.receita_pos_impostos).toBe(261_945.27)
  })

  it('nao normaliza unidade: margem segue em FRACAO como o motor entrega', () => {
    const enviado = viabilidadeParaPdf(make()) as unknown as ViabilidadeOut
    expect(enviado.dre.margem).toBe(0.3873)
  })

  it('nulos degradam sem quebrar (payback/TIR infinitos viram null no backend)', () => {
    const payload = make({
      retorno: {
        otica: 'desalavancada',
        retorno_anual_desalavancado: null,
        retorno_anual_equity: null,
        tir_anual: null,
        vpl: null,
        payback: null,
      },
      aluguel_teto: null,
    })
    const enviado = viabilidadeParaPdf(payload) as unknown as ViabilidadeOut
    expect(enviado.retorno.payback).toBeNull()
    expect(enviado.aluguel_teto).toBeNull()
  })
})

describe('infoImovelParaPdf', () => {
  const cenario = { m2: 1500, aluguel: 20000 }

  it('SEMPRE inclui metragem/aluguel do Cenário como número (o bug do "n/d")', () => {
    const d = infoImovelParaPdf({}, cenario)
    expect(d.metragem_m2).toBe(1500)
    expect(d.aluguel_pedido).toBe(20000)
  })

  it('remapeia as chaves do front para o contrato do gerador (pe_direito_m, tipo_imovel, endereco)', () => {
    const d = infoImovelParaPdf(
      { nome: 'Loja Centro', pe_direito: '4,5', tipo: 'galpão', vagas: '10' },
      cenario,
    )
    expect(d.endereco).toBe('Loja Centro')
    expect(d.pe_direito_m).toBe(4.5)
    expect(d.tipo_imovel).toBe('galpão')
    expect(d.vagas).toBe(10)
    // Nunca emite as chaves ERRADAS que o front usava antes.
    expect(d).not.toHaveProperty('pe_direito')
    expect(d).not.toHaveProperty('tipo')
    expect(d).not.toHaveProperty('nome')
  })

  it('valor de venda pt-BR (ponto=milhar, vírgula=decimal) vira número', () => {
    expect(infoImovelParaPdf({ valor_venda: 'R$ 1.200.000,00' }, cenario).valor_venda).toBe(
      1200000,
    )
    // "4.5" NÃO é milhar (só 1 dígito depois do ponto) -> preserva 4.5
    expect(infoImovelParaPdf({ pe_direito: '4.5' }, cenario).pe_direito_m).toBe(4.5)
  })

  it('campos opcionais vazios são omitidos (sem chaves undefined no payload)', () => {
    const d = infoImovelParaPdf({ nome: '  ', valor_venda: '' }, cenario)
    expect(Object.keys(d).sort()).toEqual(['aluguel_pedido', 'metragem_m2'])
  })

  it('texto não numérico em campo numérico segue como texto (degrada gracioso, não vira n/d)', () => {
    expect(infoImovelParaPdf({ valor_venda: 'a combinar' }, cenario).valor_venda).toBe(
      'a combinar',
    )
  })
})

describe('parametrosRelatorioPontual', () => {
  // Primeiro elo do fio "origem da coordenada": tela -> api.ts -> rota -> PDF. Os elos
  // seguintes ja tinham teste; este vivia dentro do ViabilityScreen.tsx, fora do alcance
  // do vitest (que so ve `src/**/*.test.ts`) — fixar o flag em `false` deixava tudo verde
  // e o PDF voltava a mentir sobre a origem da coordenada. Estes casos sao o controle.
  // Centroide real do hex res-7 em Janga/Paulista-PE (o caso que quebrou em producao).
  const hex = { lat: -7.942426, lng: -34.821732 }
  const ponto = { hex, rotulo: 'Hexágono 8780...' }

  it('coordenada EXATA (busca por endereço): usa a exata e NAO avisa aproximação', () => {
    const p = parametrosRelatorioPontual({ ...ponto, lat: -7.93908, lng: -34.82566 })
    expect(p.lat).toBe(-7.93908)
    expect(p.lng).toBe(-34.82566)
    expect(p.origemCentroideHex).toBe(false)
    // Nao pode vazar o centroide para o PDF.
    expect(p.lat).not.toBe(hex.lat)
    expect(p.lng).not.toBe(hex.lng)
  })

  it('coordenada AUSENTE (clique no ranking): cai no centroide e AVISA', () => {
    const p = parametrosRelatorioPontual(ponto)
    expect(p.lat).toBe(hex.lat)
    expect(p.lng).toBe(hex.lng)
    // O aviso e o unico canal: nao existe equivalente na tela.
    expect(p.origemCentroideHex).toBe(true)
  })

  it('coordenada pela metade também é centroide (e avisa)', () => {
    expect(parametrosRelatorioPontual({ ...ponto, lat: -7.93908 })).toMatchObject({
      lat: hex.lat,
      lng: hex.lng,
      origemCentroideHex: true,
    })
    expect(parametrosRelatorioPontual({ ...ponto, lng: -34.82566 })).toMatchObject({
      lat: hex.lat,
      lng: hex.lng,
      origemCentroideHex: true,
    })
  })

  it('lat=0/lng=0 é coordenada VÁLIDA: viaja como está e NÃO vira aviso', () => {
    // Zero e falsy: um `!ponto.lat` no lugar do `== null` marcaria a Ilha Nula como
    // centroide e o PDF sairia avisando de uma aproximacao que nao houve.
    const p = parametrosRelatorioPontual({ ...ponto, lat: 0, lng: 0 })
    expect(p.lat).toBe(0)
    expect(p.lng).toBe(0)
    expect(p.origemCentroideHex).toBe(false)
  })

  it('o aviso é verdadeiro EXATAMENTE quando a coordenada é a do hexágono', () => {
    // Trava do controle negativo: com o flag fixo (em `false` ou em `true`) algum destes
    // casos quebra, porque o flag e comparado com a coordenada REALMENTE devolvida.
    const casos = [
      {},
      { lat: -7.93908, lng: -34.82566 },
      { lat: -7.93908 },
      { lng: -34.82566 },
      { lat: 0, lng: 0 },
    ]
    for (const caso of casos) {
      const p = parametrosRelatorioPontual({ ...ponto, ...caso })
      const veioDoHex = p.lat === hex.lat && p.lng === hex.lng
      expect(p.origemCentroideHex).toBe(veioDoHex)
    }
  })

  it('rótulo digitado pelo operador vence e viaja INTACTO; vazio cede ao do ponto', () => {
    expect(
      parametrosRelatorioPontual(ponto, { rotuloManual: 'Av. Brasil, 100 (esquina)' }).rotulo,
    ).toBe('Av. Brasil, 100 (esquina)')
    expect(parametrosRelatorioPontual(ponto, { rotuloManual: '' }).rotulo).toBe(ponto.rotulo)
    expect(parametrosRelatorioPontual(ponto).rotulo).toBe(ponto.rotulo)
  })

  it('devolve só o que o contrato de `api.relatorioPontual` identifica do ponto', () => {
    expect(Object.keys(parametrosRelatorioPontual(ponto)).sort()).toEqual([
      'lat',
      'lng',
      'origemCentroideHex',
      'rotulo',
    ])
  })
})
