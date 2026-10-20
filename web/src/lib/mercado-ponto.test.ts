import { describe, expect, it } from 'vitest'

import { contaFecha, leituraDoMercado, recorteDoMercado } from './mercado-ponto'
import type { PontoMercado } from './types'

/**
 * O caso que originou a DEC-070: o ponto da Ultra Santana/SP (-23,4852 / -46,6177).
 * Valores medidos no lote do backend: SAM 6.418, concorrentes 4.865 (8 academias),
 * Ultra 2.486 (1 unidade), residual 0.
 */
function santana(over: Partial<PontoMercado> = {}): PontoMercado {
  return {
    disponivel: true,
    motivo: null,
    grao: 'raio',
    raio_km: 1,
    area_km2: 3.14,
    sam: 6418,
    consumo_concorrentes: 4865,
    consumo_ultra: 2486,
    consumo_total: 7351,
    residual: 0,
    score_residual: 0,
    taxa_fitness: 0.176257,
    n_concorrentes_alcancam: 8,
    n_ultra_alcancam: 1,
    motivo_parcial: null,
    gate: {
      passa: true,
      faixa_m1: 'alta',
      faixa_elegivel: true,
      pop_ok: true,
      pop_minima: 5000,
      motivo: null,
    },
    ...over,
  }
}

describe('leituraDoMercado', () => {
  it('a conta tem as quatro linhas, na ordem em que se lê', () => {
    const l = leituraDoMercado(santana())
    expect(l.linhas.map((x) => x.chave)).toEqual([
      'sam',
      'consumo_concorrentes',
      'consumo_ultra',
      'residual',
    ])
    expect(l.linhas.map((x) => x.sinal)).toEqual(['', '-', '-', '='])
    expect(l.linhas.map((x) => x.valor)).toEqual([6418, 4865, 2486, 0])
  })

  it('a parcela da Ultra aparece — é ela que fecha a conta de Santana', () => {
    const ultra = leituraDoMercado(santana()).linhas.find((x) => x.chave === 'consumo_ultra')!
    expect(ultra.rotulo).toBe('Consumo da Ultra')
    expect(ultra.detalhe).toBe('1 unidade Ultra alcança o raio')
  })

  it('declara quantas academias alcançam o recorte (plural e singular)', () => {
    const l = leituraDoMercado(santana())
    expect(l.linhas[1].detalhe).toBe('8 academias de rede alcançam o raio')
    const um = leituraDoMercado(santana({ n_concorrentes_alcancam: 1 }))
    expect(um.linhas[1].detalhe).toBe('1 academia de rede alcança o raio')
  })

  it('parcela ausente fica ausente (null) com o motivo do servidor, nunca zero', () => {
    const motivo = 'Sem cadastro de unidades Ultra: consumo da rede própria não calculado.'
    const l = leituraDoMercado(
      santana({ consumo_ultra: null, consumo_total: null, residual: null, n_ultra_alcancam: null, motivo_parcial: motivo }),
    )
    expect(l.linhas[2].valor).toBeNull()
    expect(l.linhas[2].detalhe).toBeNull()
    expect(l.linhas[3].valor).toBeNull()
    expect(l.motivoParcial).toBe(motivo)
  })

  it('payload antigo, sem as parcelas, não quebra: elas saem ausentes', () => {
    const antigo: PontoMercado = { disponivel: true, motivo: null, sam: 12000, residual: 4000, score_residual: 100 }
    const l = leituraDoMercado(antigo)
    expect(l.linhas[1].valor).toBeNull()
    expect(l.linhas[2].valor).toBeNull()
    expect(l.recorte).toBe('raio de 1 km')
    expect(l.avisoGate).toBeNull()
  })

  it('gate reprovado explica o SAM zerado, com o motivo do servidor', () => {
    const l = leituraDoMercado(
      santana({
        sam: 0,
        residual: 0,
        gate: {
          passa: false,
          faixa_m1: 'baixa',
          faixa_elegivel: false,
          pop_ok: true,
          pop_minima: 5000,
          motivo: 'faixa M1 do hexágono não elegível',
        },
      }),
    )
    expect(l.avisoGate).toBe(
      'O SAM sai zerado porque o gate do mercado não passa: faixa M1 do hexágono não elegível',
    )
  })

  it('gate aprovado ou desconhecido não gera aviso', () => {
    expect(leituraDoMercado(santana()).avisoGate).toBeNull()
    expect(leituraDoMercado(santana({ gate: undefined })).avisoGate).toBeNull()
  })

  it('área desenhada troca o texto do recorte e o alvo do detalhe', () => {
    const l = leituraDoMercado(santana({ grao: 'geometria', raio_km: null, area_km2: 2.43 }))
    expect(l.recorte).toBe('área desenhada de 2,43 km²')
    expect(l.linhas[1].detalhe).toBe('8 academias de rede alcançam a área')
  })
})

describe('recorteDoMercado', () => {
  it('raio em km, sem ",0" sobrando, e vírgula na casa decimal', () => {
    expect(recorteDoMercado({ grao: 'raio', raio_km: 1, area_km2: null })).toBe('raio de 1 km')
    expect(recorteDoMercado({ grao: 'raio', raio_km: 1.5, area_km2: null })).toBe('raio de 1,5 km')
  })

  it('área desenhada sem área conhecida não inventa número', () => {
    expect(recorteDoMercado({ grao: 'geometria', raio_km: null, area_km2: null })).toBe('área desenhada')
  })

  it('a isócrona também roda num polígono, mas não é "área desenhada" (DEC-074)', () => {
    // O servidor chama o mercado com `geometria` e devolve `grao = 'geometria'`: o tipo do
    // recorte do item é que diz o que a ficha afirma.
    const iso = { grao: 'geometria' as const, raio_km: null, area_km2: 38.24 }
    expect(recorteDoMercado(iso, 'carro_10min')).toBe('10 min de carro, sem trânsito · 38,2 km²')
    expect(recorteDoMercado(iso, 'poligono')).toBe('área desenhada de 38,2 km²')
    expect(recorteDoMercado({ grao: 'raio', raio_km: 2, area_km2: 12.57 }, 'raio_2km')).toBe('raio de 2 km')
  })
})

describe('leituraDoMercado na isócrona (DEC-074)', () => {
  it('nota e contagens falam de 10 min de carro, não de área desenhada', () => {
    const l = leituraDoMercado(santana({ grao: 'geometria', raio_km: null, area_km2: 38.24 }), 'carro_10min')
    expect(l.recorte).toBe('10 min de carro, sem trânsito · 38,2 km²')
    const conc = l.linhas.find((x) => x.chave === 'consumo_concorrentes')!
    expect(conc.detalhe).toBe('8 academias de rede alcançam a área de 10 min de carro')
    expect(JSON.stringify(l)).not.toMatch(/desenhada/)
  })

  it('nos 5 min de carro, o recorte e as contagens dizem 5 min (Emenda 1)', () => {
    const l = leituraDoMercado(santana({ grao: 'geometria', raio_km: null, area_km2: 3.17 }), 'carro_5min')
    expect(l.recorte).toBe('5 min de carro, sem trânsito · 3,17 km²')
    const conc = l.linhas.find((x) => x.chave === 'consumo_concorrentes')!
    expect(conc.detalhe).toBe('8 academias de rede alcançam a área de 5 min de carro')
    expect(JSON.stringify(l)).not.toMatch(/10 min/)
  })

  it('sem o tipo, a leitura de sempre (raio pelo grão)', () => {
    expect(leituraDoMercado(santana()).recorte).toBe('raio de 1 km')
    expect(leituraDoMercado(santana(), 'raio_1km')).toEqual(leituraDoMercado(santana()))
  })
})

describe('contaFecha', () => {
  it('Santana: SAM 6.418 - (4.865 + 2.486) satura em 0 e fecha', () => {
    expect(contaFecha(santana())).toBe(true)
  })

  it('residual positivo fecha com folga de 1 aluno de arredondamento', () => {
    expect(contaFecha(santana({ sam: 9000, residual: 1649 }))).toBe(true)
    expect(contaFecha(santana({ sam: 9000, residual: 1650 }))).toBe(true)
  })

  it('residual que ignora a parcela da Ultra (a dupla leitura antiga) não fecha', () => {
    // 9.000 - 4.865 = 4.135: o residual que se leria sem a Ultra na conta.
    expect(contaFecha(santana({ sam: 9000, residual: 4135 }))).toBe(false)
  })

  it('sem parcela não há conta para conferir', () => {
    expect(contaFecha(santana({ consumo_ultra: null }))).toBeNull()
    expect(contaFecha(santana({ residual: null }))).toBeNull()
  })
})
