import { describe, expect, it } from 'vitest'

import {
  MARGEM_MEDIANA_PP,
  UFS_COM_SATELITE,
  destinoDoHex,
  filtrarPorCrescimento,
  lerCrescimento,
  leituraDoItem,
  ordenarComDesempate,
  temCoberturaSatelite,
  type CrescimentoMunicipio,
  type ItemFila,
} from './oportunidades'

/** Valores da ordem de grandeza do payload real de GO (Goiânia: emp 8.7, mediana 7.6). */
const GOIANIA: CrescimentoMunicipio = { emp: 8.7, uf_mediana: 7.6, tend: 'Estável' }

describe('lerCrescimento', () => {
  it('acima da mediana quando passa da margem', () => {
    const r = lerCrescimento(GOIANIA)
    expect(r.classe).toBe('acima')
    expect(r.delta).toBeCloseTo(1.1, 5)
    expect(r.rotulo).toMatch(/acima/i)
  })

  it('abaixo da mediana', () => {
    const r = lerCrescimento({ emp: 4.0, uf_mediana: 7.6 })
    expect(r.classe).toBe('abaixo')
    expect(r.delta).toBeCloseTo(-3.6, 5)
  })

  it('diferenca menor que a margem NAO vira sinal', () => {
    // 7,61 contra 7,60 nao sustenta decisao — seria falsa precisao numa etiqueta.
    const r = lerCrescimento({ emp: 7.61, uf_mediana: 7.6 })
    expect(Math.abs(r.delta as number)).toBeLessThan(MARGEM_MEDIANA_PP)
    expect(r.classe).toBe('na-mediana')
  })

  it('sem medicao devolve sem-dado, nao zero', () => {
    for (const c of [null, undefined, {}, { emp: null }] as (CrescimentoMunicipio | null)[]) {
      const r = lerCrescimento(c)
      expect(r.classe).toBe('sem-dado') // sem medicao != sem referencia
      expect(r.valor).toBeNull()
    }
  })

  it('numero SEM mediana estadual nao vira leitura — e nem mostra o valor', () => {
    // Regra do Juan (2026-08-07): o CAGED so' vale contra margem estadual ou
    // municipal. "12,3%" solto convida a comparar municipios de UFs diferentes,
    // que e' a leitura nacional proibida.
    const r = lerCrescimento({ emp: 12.3 })
    expect(r.classe).toBe('sem-referencia')
    expect(r.delta).toBeNull()
    expect(r.rotulo).not.toContain('12,3')
    expect(r.rotulo).toMatch(/mediana estadual/i)
    // O valor segue no objeto para auditoria; quem desenha e' que nao o exibe.
    expect(r.valor).toBe(12.3)
  })

  it('sem mediana NAO passa no filtro de "cresce acima"', () => {
    const itens = [{ rank: 1, titulo: 'X', valor: 10 }]
    const cres = { X: { emp: 99 } } // numero altissimo, mas sem referencia
    expect(filtrarPorCrescimento(itens, cres, true)).toHaveLength(0)
  })
})

describe('ordenarComDesempate — crescimento NUNCA vira peso', () => {
  const cres: Record<string, CrescimentoMunicipio> = {
    Cresce: { emp: 20, uf_mediana: 7 },
    Estagna: { emp: 1, uf_mediana: 7 },
  }

  it('residual manda: cidade que cresce menos, mas tem mais residual, fica na frente', () => {
    const itens: ItemFila[] = [
      { rank: 1, titulo: 'Estagna', valor: 50000 },
      { rank: 2, titulo: 'Cresce', valor: 10000 },
    ]
    expect(ordenarComDesempate(itens, cres).map((i) => i.titulo)).toEqual([
      'Estagna', 'Cresce',
    ])
  })

  it('crescimento so decide em EMPATE de residual', () => {
    const itens: ItemFila[] = [
      { rank: 1, titulo: 'Estagna', valor: 10000 },
      { rank: 2, titulo: 'Cresce', valor: 10000 },
    ]
    expect(ordenarComDesempate(itens, cres).map((i) => i.titulo)).toEqual([
      'Cresce', 'Estagna',
    ])
  })

  it('empate total preserva a ordem do servidor (pelo rank)', () => {
    const itens: ItemFila[] = [
      { rank: 1, titulo: 'A', valor: 100 },
      { rank: 2, titulo: 'B', valor: 100 },
    ]
    expect(ordenarComDesempate(itens, {}).map((i) => i.rank)).toEqual([1, 2])
  })

  it('nao muta a lista recebida', () => {
    const itens: ItemFila[] = [
      { rank: 1, titulo: 'A', valor: 1 },
      { rank: 2, titulo: 'B', valor: 9 },
    ]
    const copia = [...itens]
    ordenarComDesempate(itens, {})
    expect(itens).toEqual(copia)
  })
})

describe('filtrarPorCrescimento', () => {
  const cres: Record<string, CrescimentoMunicipio> = {
    Alta: { emp: 20, uf_mediana: 7 },
    Baixa: { emp: 2, uf_mediana: 7 },
    Igual: { emp: 7.1, uf_mediana: 7 },
  }
  const itens: ItemFila[] = [
    { rank: 1, titulo: 'Alta', valor: 10 },
    { rank: 2, titulo: 'Baixa', valor: 9 },
    { rank: 3, titulo: 'Igual', valor: 8 },
    { rank: 4, titulo: 'SemDado', valor: 7 },
  ]

  it('desligado devolve tudo', () => {
    expect(filtrarPorCrescimento(itens, cres, false)).toHaveLength(4)
  })

  it('ligado guarda so quem cresce acima da mediana', () => {
    const r = filtrarPorCrescimento(itens, cres, true)
    expect(r.map((i) => i.titulo)).toEqual(['Alta'])
  })

  it('quem nao tem medicao NAO passa no filtro — nao se inventa que cresce', () => {
    const r = filtrarPorCrescimento(itens, cres, true)
    expect(r.some((i) => i.titulo === 'SemDado')).toBe(false)
  })
})

describe('leituraDoItem', () => {
  it('declara o que a fila ja garante e acrescenta o crescimento', () => {
    const t = leituraDoItem({ rank: 1, titulo: 'Goiânia', valor: 57164 }, GOIANIA)
    expect(t).toContain('57.164 alunos de residual') // milhar pt-BR
    expect(t).toContain('nenhum concorrente mapeado')
    expect(t).toContain('acima da mediana')
  })

  it('sem medicao diz isso, em vez de omitir', () => {
    const t = leituraDoItem({ rank: 2, titulo: 'X', valor: 3000 }, null)
    expect(t).toContain('Sem medição de crescimento')
  })

  it('e deterministica', () => {
    const it_ = { rank: 1, titulo: 'A', valor: 1000 }
    expect(leituraDoItem(it_, GOIANIA)).toBe(leituraDoItem(it_, GOIANIA))
  })
})

describe('cobertura de satelite', () => {
  it('sao 12 UFs', () => {
    expect(UFS_COM_SATELITE).toHaveLength(12)
  })

  it('GO e SP tem; MT, AM e PA nao', () => {
    expect(temCoberturaSatelite('GO')).toBe(true)
    expect(temCoberturaSatelite('sp')).toBe(true) // aceita minuscula
    for (const uf of ['MT', 'AM', 'PA', 'RO', 'TO']) {
      expect(temCoberturaSatelite(uf)).toBe(false)
    }
  })

  it('nulo nao quebra', () => {
    expect(temCoberturaSatelite(null)).toBe(false)
    expect(temCoberturaSatelite(undefined)).toBe(false)
  })
})


describe('destinoDoHex — o "Ver no mapa" do ranking nacional', () => {
  const COMPLETO = {
    uf: 'TO',
    municipio: 'Palmas',
    lat: -10.1849,
    lng: -48.3336,
    hex_id: '87817101bffffff',
  }

  it('leva o HEXÁGONO, não só a cidade — o pin é o que o mapa precisa', () => {
    const d = destinoDoHex(COMPLETO)
    expect(d).not.toBeNull()
    // uf + municipio escolhem o território; o pin escolhe o PONTO dentro dele.
    expect(d?.uf).toBe('TO')
    expect(d?.municipio).toBe('Palmas')
    expect(d?.pin).toEqual({ lat: -10.1849, lng: -48.3336, hexId: '87817101bffffff' })
  })

  it('sem coordenada NÃO é destino — pin sem lat/lng leva a câmera para o oceano', () => {
    expect(destinoDoHex({ ...COMPLETO, lat: null })).toBeNull()
    expect(destinoDoHex({ ...COMPLETO, lng: null })).toBeNull()
  })

  it('NaN é tratado como coordenada ausente, não propagado para o mapa', () => {
    expect(destinoDoHex({ ...COMPLETO, lat: Number.NaN })).toBeNull()
    expect(destinoDoHex({ ...COMPLETO, lng: Number.POSITIVE_INFINITY })).toBeNull()
  })

  it('sem UF ou município não é destino: o mapa abriria o lugar errado', () => {
    expect(destinoDoHex({ ...COMPLETO, uf: null })).toBeNull()
    expect(destinoDoHex({ ...COMPLETO, municipio: null })).toBeNull()
    expect(destinoDoHex({ ...COMPLETO, municipio: '' })).toBeNull()
  })

  it('coordenada ZERO é válida — `!h.lat` teria descartado o meridiano', () => {
    const d = destinoDoHex({ ...COMPLETO, lat: 0, lng: 0 })
    expect(d?.pin).toEqual({ lat: 0, lng: 0, hexId: '87817101bffffff' })
  })
})
