import { describe, expect, it } from 'vitest'

import {
  barrasPorAno,
  barrasPorFase,
  barrasPorPrevisao,
  dataBr,
  escalaDaBarra,
  etiquetasDaUnidade,
  metaDoAno,
  pct,
  rotuloDaBarra,
  rotuloUnidade,
  textoAnoDaMeta,
  textoContrato,
  textoPrazo,
  textoProgressoDaMeta,
  topoDoGrafico,
  type TrimestreMeta,
} from './masters'

const tri = (acumulado: number, novas: number, extra: Partial<TrimestreMeta> = {}) => ({
  trimestre: 1,
  novas,
  acumulado,
  pct: null,
  futuro: false,
  atual: false,
  ...extra,
})

describe('tela Masters (DEC-089): textos', () => {
  it('datas e porcentagens no formato da tela', () => {
    expect(dataBr('2026-03-01')).toBe('01/03/2026')
    expect(dataBr(null)).toBe('—')
    expect(pct(0.25)).toBe('25%')
    expect(pct(null)).toBe('—')
    expect(rotuloUnidade('Asa Norte', 'DF')).toBe('Asa Norte (DF)')
    expect(rotuloUnidade('Jandira', null)).toBe('Jandira')
  })

  it('o prazo do contrato diz quanto falta, e diz quando já venceu', () => {
    const hoje = '2026-11-18'
    expect(textoPrazo({ prazo: '2027-03-11', meses_ate_prazo: 4 }, hoje)).toBe(
      '11/03/2027 (faltam 4 meses)',
    )
    expect(textoPrazo({ prazo: '2026-12-31', meses_ate_prazo: 1 }, hoje)).toBe(
      '31/12/2026 (falta 1 mês)',
    )
    expect(textoPrazo({ prazo: '2026-11-30', meses_ate_prazo: 0 }, hoje)).toBe(
      '30/11/2026 (vence este mês)',
    )
    expect(textoPrazo({ prazo: '2026-10-31', meses_ate_prazo: 0 }, hoje)).toBe(
      'venceu em 31/10/2026',
    )
    expect(textoPrazo({ prazo: null, meses_ate_prazo: null }, hoje)).toBe('não informado')
  })

  it('a meta do ano vira % só quando existe; o contrato, só com quantidade', () => {
    expect(textoAnoDaMeta({ n_ano: 8, por_ano: null })).toBe('8')
    expect(textoAnoDaMeta({ n_ano: 3, por_ano: 10 })).toBe('3 de 10 (30%)')
    expect(textoContrato({ n_contam: 5, quantidade: 5 })).toBe('5 de 5 (100%)')
    expect(textoContrato({ n_contam: 33, quantidade: null })).toBeNull()
  })

  it('a barra do trimestre mostra o acumulado e quantas abriram nele', () => {
    expect(rotuloDaBarra(tri(6, 3))).toBe('6 (+3)')
    expect(rotuloDaBarra(tri(8, 0))).toBe('8')
    expect(rotuloDaBarra(tri(0, 0, { futuro: true }))).toBe('')
    // O topo é a meta do ano quando ela é maior que as barras, e nunca zero.
    expect(topoDoGrafico([tri(3, 3), tri(5, 2)], 10)).toBe(10)
    expect(topoDoGrafico([tri(3, 3), tri(5, 2)], null)).toBe(5)
    expect(topoDoGrafico([tri(0, 0)], null)).toBe(1)
  })

  it('a meta do ano da barra: a da config; sem ela, simulada só na prévia', () => {
    // Com a meta na config, ela vale e nada é simulado (com ou sem prévia).
    const real = metaDoAno('dfgo', 2026, 8, 10)
    expect(real).toEqual({ meta: 10, simulada: false, abertas: 8, pct: 0.8, faltam: 2, acima: 0 })
    expect(metaDoAno('dfgo', 2026, 8, 10, true)).toEqual(real)
    expect(textoProgressoDaMeta(real!)).toBe('80% da meta · faltam 2 aberturas')
    // Sem ela e fora da prévia (produção): não informada, nada inventado.
    expect(metaDoAno('dfgo', 2026, 8, null)).toBeNull()
    // Na prévia: as aberturas ± 2, sempre o mesmo lado para o mesmo master e ano.
    const sim = (id: string, abertas = 8) => metaDoAno(id, 2026, abertas, null, true)!
    for (const id of ['dfgo', 'es', 'pr', 'camargo', 'gempro', 'franklin']) {
      const s = sim(id)
      expect(s.simulada).toBe(true)
      expect([6, 10]).toContain(s.meta)
      expect(sim(id)).toEqual(s)
    }
    // Os dois lados aparecem entre os masters (é um sorteio, não um lado fixo).
    const lados = new Set(
      ['dfgo', 'es', 'pr', 'camargo', 'gempro', 'franklin', 'ginseng', 'ceara'].map(
        (id) => sim(id).meta,
      ),
    )
    expect(lados).toEqual(new Set([6, 10]))
    // Nunca abaixo de 1: com 0 ou 1 abertura, só para cima.
    expect(sim('x', 0).meta).toBe(2)
    expect(sim('x', 1).meta).toBe(3)
    // Acima da meta: o texto diz quanto passou.
    expect(textoProgressoDaMeta(metaDoAno('x', 2026, 8, 6)!)).toBe(
      'meta batida · 2 aberturas acima (133%)',
    )
    expect(textoProgressoDaMeta(metaDoAno('x', 2026, 3, 4)!)).toBe(
      '75% da meta · falta 1 abertura',
    )
  })

  it('a escala da barra vai de 0 à meta (ou às aberturas, quando passaram) e marca a meta', () => {
    // Abaixo da meta: a escala vai até a meta, e a linha dela fica no fim.
    expect(escalaDaBarra({ meta: 9, abertas: 7 })).toEqual({
      fim: 9,
      posicaoDaMeta: 1,
      posicaoDasAbertas: 7 / 9,
    })
    // Passou da meta (8 de 6): a escala vai até 8 e a linha da meta cai antes do fim da barra.
    expect(escalaDaBarra({ meta: 6, abertas: 8 })).toEqual({
      fim: 8,
      posicaoDaMeta: 0.75,
      posicaoDasAbertas: 1,
    })
    expect(escalaDaBarra({ meta: 2, abertas: 0 }).posicaoDasAbertas).toBe(0)
  })

  it('um gráfico por grupo: aberturas por ano, inaugurações por mês e assinados por fase', () => {
    const op = (inauguracao: string | null) => ({
      unidade: 'x',
      uf: 'DF',
      inauguracao,
      sem_data: inauguracao === null,
      conta_para_meta: true,
      operacao_de: null,
      meta_de: null,
    })
    // Anos sem abertura entram com zero; o atual em destaque; as sem data à parte.
    const ano = barrasPorAno([op('2023-05-01'), op('2026-02-10'), op('2026-08-20'), op(null)], 2026)
    expect(ano.barras.map((b) => [b.rotulo, b.n])).toEqual([
      ['2023', 1],
      ['2024', 0],
      ['2025', 0],
      ['2026', 2],
    ])
    expect(ano.barras.filter((b) => b.destaque).map((b) => b.rotulo)).toEqual(['2026'])
    expect(ano.semData).toBe(1)
    expect(barrasPorAno([op(null)], 2026)).toEqual({ barras: [], semData: 1 })

    const inaug = (previsao: string | null) => ({
      unidade: 'y',
      uf: 'GO',
      cidade: null,
      previsao,
      fase: previsao ? null : 'Pré Venda',
      conta_para_meta: null,
      operacao_de: null,
      meta_de: null,
    })
    expect(
      barrasPorPrevisao([inaug('2027-01-15'), inaug(null), inaug('2026-12-10'), inaug('2026-12-20')]),
    ).toEqual([
      { rotulo: 'dez/26', n: 2 },
      { rotulo: 'jan/27', n: 1 },
      { rotulo: 'pré-venda', n: 1 },
    ])

    const u = { unidade: 'z', cidade: null, uf: 'DF', dentro_territorio: true }
    expect(
      barrasPorFase([
        { fase: 'Obras', unidades: [u, u] },
        { fase: 'Minuta', unidades: [u] },
      ]),
    ).toEqual([
      { rotulo: 'Obras', n: 2 },
      { rotulo: 'Minuta', n: 1 },
    ])
  })

  it('as etiquetas de uma unidade em operação', () => {
    const base = {
      unidade: 'Bertioga',
      uf: 'SP',
      inauguracao: '2026-01-20',
      sem_data: false,
      conta_para_meta: true,
      operacao_de: 'Litoral/ABC - GEMPRO',
      meta_de: null,
    }
    // Só as exceções: contar para a meta é o normal e não vira etiqueta.
    expect(etiquetasDaUnidade(base)).toEqual(['operação: Litoral/ABC - GEMPRO'])
    expect(etiquetasDaUnidade({ ...base, operacao_de: null })).toEqual([])
    expect(
      etiquetasDaUnidade({
        ...base,
        sem_data: true,
        conta_para_meta: false,
        meta_de: 'outra atribuição',
        operacao_de: null,
      }),
    ).toEqual(['sem data no Growth', 'fora da meta (meta: outra atribuição)'])
  })
})
