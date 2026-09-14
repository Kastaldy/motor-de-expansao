import { describe, expect, it } from 'vitest'

import { leiturasDoContexto } from './contexto'
import type { ContextoMunicipio } from './types'

/**
 * A tradução das camadas argentinas em cartões da ficha.
 *
 * O que estes testes existem para impedir é o mesmo que o produtor do dado travou do lado
 * dele, porque a mentira atravessa a fronteira intacta: ausência virando zero, número sem
 * período, e uso de transporte ATRIBUÍDO sendo lido como gente contada na esquina.
 *
 * O quarto caso é o Brasil, e é o que roda no outro container hoje: sem `ctx`, a lista sai
 * vazia e a seção inteira some — sem nenhum `if (país)` no caminho (DEC-047).
 */
describe('leiturasDoContexto', () => {
  const cheio: ContextoMunicipio = {
    obras_m2: 34900,
    obras_var: 12.4,
    obras_periodo: '2025-07..2026-06',
    soc_n: 1485,
    soc_var: 8.1,
    soc_janela: '2023..2025',
    emp_estoque: 52300,
    emp_salario: 1180,
    emp_constr: 7.4,
    emp_periodo: '2019-11..2025-11',
    fluxo_dia: 61200,
    fluxo_periodo: '2026-01-01..2026-09-08',
  }

  it('sem contexto não há seção — é assim que o Brasil não ganha cartão nenhum', () => {
    expect(leiturasDoContexto(null)).toEqual([])
    expect(leiturasDoContexto(undefined)).toEqual([])
    expect(leiturasDoContexto({})).toEqual([])
  })

  it('campo ausente não vira cartão com zero', () => {
    /* O caso COMUM fora da RMBA: o OEDE é nacional, o INDEC pesquisa parte dos
       municípios e o recorrido do SUBE só existe na região metropolitana. */
    const so_oede: ContextoMunicipio = { emp_estoque: 9820, emp_periodo: '2019-11..2025-11' }
    const chaves = leiturasDoContexto(so_oede).map((l) => l.chave)
    expect(chaves).toEqual(['emp'])
    expect(leiturasDoContexto(so_oede).some((l) => l.valor.includes('0 m²'))).toBe(false)
  })

  it('zero MEDIDO continua sendo um cartão', () => {
    /* La Paz (Mendoza) autorizou 84 m² em 2022 e 0 em 2025. O zero é o dado: é ele que
       diz "a obra parou aqui". Uma guarda escrita como `if (v)` o apagaria. */
    const [obra] = leiturasDoContexto({ obras_m2: 0, obras_periodo: '2025-07..2026-06' })
    expect(obra.chave).toBe('obras')
    expect(obra.valor).toBe('0 m²')
  })

  it('todo número sai com o seu período', () => {
    const leituras = leiturasDoContexto(cheio)
    expect(leituras).toHaveLength(6)
    for (const l of leituras) expect(l.nota).toBeTruthy()
    expect(leituras.find((l) => l.chave === 'obras')?.nota).toContain('2025-07..2026-06')
    expect(leituras.find((l) => l.chave === 'soc')?.nota).toContain('2023..2025')
    expect(leituras.find((l) => l.chave === 'fluxo')?.nota).toContain('2026-01-01')
  })

  it('a variação anda GRUDADA no valor absoluto que a gerou', () => {
    /* "+37%" sozinho não tem tamanho — pode ser 84 m² virando 115. A regra é a mesma do
       CAGED em `lerCrescimento`: percentual só aparece com escala ao lado. */
    const [obra] = leiturasDoContexto(cheio)
    expect(obra.valor).toContain('34.900')
    expect(obra.nota).toContain('%')
  })

  it('variação sem o absoluto não produz cartão nenhum', () => {
    expect(leiturasDoContexto({ obras_var: 12.4, obras_periodo: '2025-07..2026-06' })).toEqual([])
  })

  it('o fluxo do SUBE se declara ATRIBUÍDO no próprio rótulo', () => {
    /* Não numa nota de rodapé: quem lê o número tem de ler a ressalva junto. O uso da
       linha foi repartido entre os hexágonos pelo comprimento do trajeto dentro de cada
       um — serve para comparar corredores, não para dizer quanta gente passa na esquina. */
    const fluxo = leiturasDoContexto(cheio).find((l) => l.chave === 'fluxo')
    expect(fluxo?.rotulo.toLowerCase()).toContain('atribuídos')
  })

  it('o salário sai na moeda do PACOTE, não na moeda oficial do país', () => {
    /* `oede_sal_medio_usd` são dólares e a moeda oficial argentina é o peso: `brl()`
       imprimiria "$ 1.180" para um número que são 1.180 DÓLARES. Por isso `renda()`. */
    const salario = leiturasDoContexto(cheio).find((l) => l.chave === 'salario')
    expect(salario?.valor).toMatch(/^[A-Z$]/)
    expect(salario?.valor).toContain('1.180')
  })

  it('a ordem é estável — a ficha não embaralha cartão entre um hexágono e outro', () => {
    expect(leiturasDoContexto(cheio).map((l) => l.chave)).toEqual([
      'obras',
      'soc',
      'emp',
      'salario',
      'constr',
      'fluxo',
    ])
  })
})
