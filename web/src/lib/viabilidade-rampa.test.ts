import { describe, expect, it } from 'vitest'

import * as rampa from './viabilidade-rampa'
import {
  FORMAS_RAMPA,
  ROTULO_FORMA_RAMPA,
  ajudaDaRampa,
  casaNoMes1,
  ebitdaDosPrimeirosMeses,
  formaDoPayload,
  formaExibida,
  formaParaEnviar,
  mesFimDaRampa,
  notaDaRampa,
  usaMesesDeRampa,
} from './viabilidade-rampa'

const CURVA = { maturacao_meses: 8, forma_rampa: 'curva_uni03', mes_maturidade_rampa: 10 }
const RETA = { maturacao_meses: 8, forma_rampa: 'reta', mes_maturidade_rampa: 8 }

describe('forma da rampa (DEC-077)', () => {
  it('os identificadores são os do motor e os rótulos são de usuário', () => {
    expect([...FORMAS_RAMPA]).toEqual(['curva_uni03', 'reta'])
    expect(ROTULO_FORMA_RAMPA.curva_uni03).toBe('Curva observada')
    expect(ROTULO_FORMA_RAMPA.reta).toBe('Reta')
  })

  it('a tela não crava o padrão: ele é do servidor (uma constante só reverte tudo)', () => {
    expect('FORMA_RAMPA_PADRAO' in rampa).toBe(false)
  })
})

describe('seletor Curva / Reta (lógica pura)', () => {
  it('sem escolha, o pedido vai SEM forma_rampa e vale o padrão do servidor', () => {
    expect(formaParaEnviar(null)).toBeUndefined()
    // a chave some do JSON: o corpo é o mesmo de antes da DEC-077
    expect(JSON.stringify({ forma_rampa: formaParaEnviar(null) })).toBe('{}')
  })

  it('a escolha explícita vai no pedido, nas duas formas', () => {
    expect(formaParaEnviar('curva_uni03')).toBe('curva_uni03')
    expect(formaParaEnviar('reta')).toBe('reta')
  })

  it('sem escolha, o seletor mostra a forma que o servidor usou', () => {
    expect(formaExibida(null, RETA)).toBe('reta')
    expect(formaExibida(null, CURVA)).toBe('curva_uni03')
  })

  it('antes do primeiro cálculo nenhuma forma é marcada (não adivinha o servidor)', () => {
    expect(formaExibida(null, null)).toBeNull()
  })

  it('a escolha do operador vence a forma servida', () => {
    expect(formaExibida('reta', CURVA)).toBe('reta')
    expect(formaExibida('curva_uni03', RETA)).toBe('curva_uni03')
  })

  it('os meses da rampa somem na curva e aparecem na reta e antes do cálculo', () => {
    expect(usaMesesDeRampa('reta')).toBe(true)
    expect(usaMesesDeRampa('curva_uni03')).toBe(false)
    expect(usaMesesDeRampa(null)).toBe(true)
    // composição com o que a tela mostra: payload da curva sem escolha esconde os meses
    expect(usaMesesDeRampa(formaExibida(null, CURVA))).toBe(false)
    expect(usaMesesDeRampa(formaExibida(null, RETA))).toBe(true)
  })
})

describe('ajuda do controle', () => {
  it('a ajuda da curva declara a amarra do agregador', () => {
    expect(ajudaDaRampa('curva_uni03')).toContain('agregador')
    expect(ajudaDaRampa('reta')).toContain('meses')
  })

  it('trocar a forma não recalcula sozinho, e a ajuda diz isso nas três situações', () => {
    for (const forma of ['curva_uni03', 'reta', null] as const) {
      expect(ajudaDaRampa(forma).toLowerCase()).toContain('recalcule para atualizar o payback')
    }
  })

  it('os percentuais da ajuda saem da curva servida, não de número cravado', () => {
    const curva = [0.68, 0.77, 0.84, 0.88, 0.9, 0.92, 0.97, 0.97, 0.99, 1, 1, 1]
    const t = ajudaDaRampa('curva_uni03', curva)
    expect(t).toContain('68% da demanda no mês 1')
    expect(t).toContain('100% a partir do mês 10')
    // antes do primeiro cálculo não há curva: a ajuda não inventa percentual
    expect(ajudaDaRampa('curva_uni03', null)).not.toMatch(/\d+%/)
  })
})

describe('fim da rampa lido do payload', () => {
  it('lê o mês servido pelo motor (curva fecha no 10, não no parâmetro da reta)', () => {
    expect(mesFimDaRampa(CURVA)).toBe(10)
  })

  it('backend anterior à DEC-077 (sem o campo) cai na reta de maturacao_meses', () => {
    expect(mesFimDaRampa({ maturacao_meses: 8 })).toBe(8)
    expect(formaDoPayload({ maturacao_meses: 8 })).toBe('reta')
  })

  it('sem premissas não inventa mês', () => {
    expect(mesFimDaRampa(null)).toBeNull()
  })

  it('forma desconhecida vinda do payload é lida como reta, nunca como curva', () => {
    expect(formaDoPayload({ maturacao_meses: 8, forma_rampa: 'outra' })).toBe('reta')
  })
})

describe('nota metodológica', () => {
  it('na curva, diz o mês de fechamento e o que NÃO é modelado', () => {
    const t = notaDaRampa(CURVA)
    expect(t).toContain('mês 10')
    expect(t).toContain('não é modelado')
  })

  it('na reta, mantém o texto de antes', () => {
    expect(notaDaRampa(RETA)).toBe(
      '8 meses para a demanda sair do piso inicial e chegar ao valor assumido. Afeta o ' +
        'caixa e o payback, não a margem de steady-state.',
    )
  })

  it('"casa vazia" no mês 1 só na reta: na curva o mês 1 já tem 68% da demanda', () => {
    expect(casaNoMes1(RETA)).toBe('com a casa vazia')
    expect(casaNoMes1(CURVA)).not.toContain('vazia')
  })

  it('o EBITDA dos primeiros meses só é afirmado NEGATIVO na reta', () => {
    expect(ebitdaDosPrimeirosMeses(RETA)).toBe(
      'então o EBITDA dos primeiros meses é bem NEGATIVO enquanto a casa não enche.',
    )
    expect(ebitdaDosPrimeirosMeses(CURVA)).not.toMatch(/NEGATIVO/i)
    expect(ebitdaDosPrimeirosMeses(CURVA)).toContain('positivo')
  })
})
