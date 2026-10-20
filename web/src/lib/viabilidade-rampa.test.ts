import { describe, expect, it } from 'vitest'

import {
  FORMA_RAMPA_PADRAO,
  FORMAS_RAMPA,
  ROTULO_FORMA_RAMPA,
  ajudaDaRampa,
  formaDoPayload,
  mesFimDaRampa,
  notaDaRampa,
  usaMesesDeRampa,
} from './viabilidade-rampa'

describe('forma da rampa (DEC-075)', () => {
  it('o padrão é a curva observada, e os identificadores são os do motor', () => {
    expect(FORMA_RAMPA_PADRAO).toBe('curva_uni03')
    expect([...FORMAS_RAMPA]).toEqual(['curva_uni03', 'reta'])
    expect(ROTULO_FORMA_RAMPA.curva_uni03).toBe('Curva observada')
    expect(ROTULO_FORMA_RAMPA.reta).toBe('Reta')
  })

  it('o controle de meses só vale na reta', () => {
    expect(usaMesesDeRampa('reta')).toBe(true)
    expect(usaMesesDeRampa('curva_uni03')).toBe(false)
  })

  it('a ajuda da curva declara a amarra do agregador', () => {
    expect(ajudaDaRampa('curva_uni03')).toContain('agregador')
    expect(ajudaDaRampa('reta')).toContain('meses')
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
    expect(
      mesFimDaRampa({ maturacao_meses: 8, forma_rampa: 'curva_uni03', mes_maturidade_rampa: 10 }),
    ).toBe(10)
  })

  it('backend anterior à DEC-075 (sem o campo) cai na reta de maturacao_meses', () => {
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
    const t = notaDaRampa({
      maturacao_meses: 8,
      forma_rampa: 'curva_uni03',
      mes_maturidade_rampa: 10,
    })
    expect(t).toContain('mês 10')
    expect(t).toContain('não é modelado')
  })

  it('na reta, mantém o texto de antes', () => {
    expect(notaDaRampa({ maturacao_meses: 8, forma_rampa: 'reta', mes_maturidade_rampa: 8 })).toBe(
      '8 meses para a demanda sair do piso inicial e chegar ao valor assumido. Afeta o ' +
        'caixa e o payback, não a margem de steady-state.',
    )
  })
})
