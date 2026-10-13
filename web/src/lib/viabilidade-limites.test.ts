import { describe, expect, it } from 'vitest'

import { LIMITES_DO_MOTOR, faixaEmTexto, foraDaFaixa } from './viabilidade-limites'

/**
 * `CampoNumero` documenta que `min`/`max` nativos NUNCA impediram digitação. Então
 * `min={1}` em "Parcelas franquia" não impede digitar `0`, e o motor recusa com 422.
 * Esta guarda barra antes, dizendo o campo e a faixa.
 */
describe('a faixa que o motor aceita', () => {
  it('o 0 digitado em "Parcelas franquia" é barrado, com nome e faixa', () => {
    const m = foraDaFaixa(0, LIMITES_DO_MOTOR.parcelas_franquia)
    expect(m).toBeTruthy()
    expect(m).toContain('Parcelas franquia')
    expect(m).toContain('entre 1 e 12')
  })

  it('vazio é DENTRO — campo vazio usa o padrão do motor', () => {
    for (const l of Object.values(LIMITES_DO_MOTOR)) {
      expect(foraDaFaixa(undefined, l), l.rotulo).toBeNull()
    }
  })

  it('zero NÃO é tratado como vazio', () => {
    /* Reinterpretar `0` como "não informado" faria a tela mandar o padrão do motor
       calado, com o operador vendo 0 na caixa. Valor legítimo no lugar errado — a
       família de defeito que mais se repete neste repo. */
    expect(foraDaFaixa(0, LIMITES_DO_MOTOR.parcelas_obra)).toBeTruthy()
  })

  it('as bordas da faixa PASSAM (1 e 12 são válidos)', () => {
    expect(foraDaFaixa(1, LIMITES_DO_MOTOR.parcelas_franquia)).toBeNull()
    expect(foraDaFaixa(12, LIMITES_DO_MOTOR.parcelas_franquia)).toBeNull()
    expect(foraDaFaixa(13, LIMITES_DO_MOTOR.parcelas_franquia)).toBeTruthy()
  })

  it('a metragem só exige > 0 — a guarda NÃO inventa o piso de 200 da caixa', () => {
    /* `min={200}` no `CampoNumero` vale para as setas; o motor aceita qualquer m² > 0,
       e hoje dá para digitar 150. Uma guarda mais severa que o motor REPROVARIA valor
       que o motor aceita — regra nova disfarçada de conserto. */
    expect(foraDaFaixa(150, LIMITES_DO_MOTOR.m2)).toBeNull()
    expect(foraDaFaixa(0, LIMITES_DO_MOTOR.m2)).toBeTruthy()
  })

  it('não-finito é barrado (o motor tem allow_inf_nan=False)', () => {
    expect(foraDaFaixa(Number.NaN, LIMITES_DO_MOTOR.m2)).toBeTruthy()
    expect(foraDaFaixa(Number.POSITIVE_INFINITY, LIMITES_DO_MOTOR.m2)).toBeTruthy()
  })

  it('demanda 0 é barrada — `demandaUsar == null` nunca pegou o zero', () => {
    /* Na instância sem faixa de comparáveis (o caso argentino) o operador DIGITA a
       demanda, e `min={1}` não impede digitar 0. A guarda da tela testa `== null`, e
       `0 == null` é falso: o zero atravessava inteiro até o motor. */
    expect(foraDaFaixa(0, LIMITES_DO_MOTOR.demanda)).toBeTruthy()
    expect(foraDaFaixa(1, LIMITES_DO_MOTOR.demanda)).toBeNull()
    expect(foraDaFaixa(1500, LIMITES_DO_MOTOR.demanda)).toBeNull()
  })

  it('o prazo de financiamento respeita 1..60', () => {
    expect(foraDaFaixa(0, LIMITES_DO_MOTOR.prazo_equipamentos)).toBeTruthy()
    expect(foraDaFaixa(60, LIMITES_DO_MOTOR.prazo_equipamentos)).toBeNull()
    expect(foraDaFaixa(72, LIMITES_DO_MOTOR.prazo_equipamentos)).toBeTruthy()
  })

  it('a faixa em texto usa o PISO INTEIRO de um `gt` exclusivo', () => {
    // `gt: 0` num campo de meses significa "1 ou mais" para quem lê, não "maior que 0".
    expect(faixaEmTexto({ gt: 0, le: 12, rotulo: 'x' })).toBe('entre 1 e 12')
    expect(faixaEmTexto({ gt: 0, rotulo: 'x' })).toBe('1 ou mais')
    expect(faixaEmTexto({ le: 60, rotulo: 'x' })).toBe('no máximo 60')
  })

  it('todo limite tem rótulo não vazio — a mensagem nomeia o campo', () => {
    for (const [chave, l] of Object.entries(LIMITES_DO_MOTOR)) {
      expect(l.rotulo.trim(), chave).not.toBe('')
    }
  })
})
