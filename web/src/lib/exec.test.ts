import { describe, expect, it } from 'vitest'

import { TEXTO_SEM_DADO } from './constants'
import {
  COR_SEVERIDADE,
  corComAlfa,
  destaquesDoRecorte,
  deveReenquadrar,
  enquadrar,
  filtrarUnidades,
  formatarMetrica,
  lerDelta,
  narrativaDoRecorte,
  normalizar,
  ordenarUnidades,
  queryDaCarteira,
  rotuloMesCompetencia,
  rotuloRanking,
  rotuloVsMedia,
  tituloDaCelula,
} from './exec'
import type { RedeCarteira, RedeMetrica, RedeUnidade } from './types'

function metrica(p: Partial<RedeMetrica> = {}): RedeMetrica {
  return { atual: null, m1: null, delta_pct: null, rank: null, rank_total: null, vs_media_pct: null, ...p }
}

function unidade(nome: string, p: Partial<RedeUnidade> = {}): RedeUnidade {
  return {
    id: nome.toLowerCase(),
    nome,
    uf: 'SP',
    master: 'ULTRA',
    cidade: null,
    consultor: null,
    consultor_2: null,
    master_franquia: null,
    franqueado: null,
    coorte: '24_47',
    coorte_rotulo: '2 a 4 anos',
    meses_operacao: 30,
    inauguracao: '01/01/2020',
    lat: null,
    lng: null,
    comparavel: true,
    severidade: 'ok',
    severidade_rotulo: 'Sem alerta',
    prioridade: 0,
    resumo: '',
    faixa_faturamento: 'bom',
    faixa_faturamento_rotulo: 'Bom',
    alertas: [],
    metricas: {},
    sparkline: [],
    ...p,
  }
}

describe('formatarMetrica', () => {
  it('mostra churn em PERCENTUAL, não em fração', () => {
    // A armadilha: nesta API a taxa vem em %, e na Viabilidade vem em fração.
    // Um `pctFrac` aqui mostraria "0,1%" de churn e ninguém desconfiaria.
    expect(formatarMetrica(5.93, 'pct')).toBe('5,9%')
  })

  it('usa centavos só quando o centavo importa', () => {
    expect(formatarMetrica(156.68, 'brl')).toBe('R$ 156,68')
    expect(formatarMetrica(412_000, 'brl')).toBe('R$ 412.000')
  })

  it('nulo vira travessão, nunca zero', () => {
    expect(formatarMetrica(null, 'brl')).toBe('—')
    expect(formatarMetrica(undefined, 'int')).toBe('—')
    expect(formatarMetrica(NaN, 'pct')).toBe('—')
  })

  it('NPS negativo é valor legítimo', () => {
    expect(formatarMetrica(-16.7, 'nota')).toBe('-17')
  })
})

describe('quarteto de contexto', () => {
  it('diz a posição e a distância da média em texto', () => {
    const m = metrica({ atual: 100, m1: 90, rank: 79, rank_total: 89, vs_media_pct: -64.2 })
    expect(rotuloRanking(m)).toBe('79º de 89')
    expect(rotuloVsMedia(m)).toBe('64,2% abaixo da média da rede')
    expect(tituloDaCelula('Faturamento', m, 'int')).toContain('79º de 89')
  })

  it('unidade nova não recebe posição inventada', () => {
    const m = metrica({ atual: 8000 })
    expect(rotuloRanking(m)).toBe('sem posição (unidade nova)')
    expect(rotuloVsMedia(m)).toBe('sem comparação com a rede')
  })

  it('na média não vira "0,0% acima"', () => {
    expect(rotuloVsMedia(metrica({ vs_media_pct: 0.01 }))).toBe('na média da rede')
  })
})

describe('lerDelta', () => {
  it('churn subindo é RUIM (o defeito da seta verde)', () => {
    const d = lerDelta(metrica({ atual: 9, m1: 6, delta_pct: 50 }), false, true)
    expect(d).toMatchObject({ subiu: true, bom: false, modo: 'pontos' })
    expect(d?.valor).toBeCloseTo(3)
  })

  it('faturamento subindo é BOM', () => {
    expect(lerDelta(metrica({ delta_pct: 12 }), true)).toMatchObject({ subiu: true, bom: true })
  })

  it('faturamento caindo é ruim', () => {
    expect(lerDelta(metrica({ delta_pct: -12 }), true)).toMatchObject({ subiu: false, bom: false })
  })

  it('variação irrelevante é marcada como estável', () => {
    expect(lerDelta(metrica({ delta_pct: 0.01 }), true)?.estavel).toBe(true)
  })

  it('sem M-1 não inventa variação', () => {
    expect(lerDelta(metrica({ atual: 10 }), true, true)).toBeNull()
    expect(lerDelta(undefined, true)).toBeNull()
  })
})

describe('ordenarUnidades', () => {
  const lista = [
    unidade('A', { metricas: { nps: metrica({ atual: 50 }) } }),
    unidade('B', { metricas: { nps: metrica({ atual: null }) } }),
    unidade('C', { metricas: { nps: metrica({ atual: 90 }) } }),
  ]

  it('nulos ficam por último nas DUAS direções', () => {
    // O `?? -Infinity` da v1 só funcionava em `desc`; em `asc` o dado ausente
    // subia para o topo da lista de trabalho.
    expect(ordenarUnidades(lista, 'nps', 'desc').map((u) => u.nome)).toEqual(['C', 'A', 'B'])
    expect(ordenarUnidades(lista, 'nps', 'asc').map((u) => u.nome)).toEqual(['A', 'C', 'B'])
  })

  it('empate desempata por nome, para a ordem não pular entre renders', () => {
    const empate = [
      unidade('Zulu', { metricas: { nps: metrica({ atual: 10 }) } }),
      unidade('Alfa', { metricas: { nps: metrica({ atual: 10 }) } }),
    ]
    expect(ordenarUnidades(empate, 'nps', 'desc').map((u) => u.nome)).toEqual(['Alfa', 'Zulu'])
  })

  it('ordena por prioridade e por nome', () => {
    const porPrioridade = [unidade('X', { prioridade: 1 }), unidade('Y', { prioridade: 5 })]
    expect(ordenarUnidades(porPrioridade, 'prioridade', 'desc')[0].nome).toBe('Y')
    expect(ordenarUnidades(porPrioridade, 'nome', 'asc')[0].nome).toBe('X')
  })

  it('não muta a lista recebida', () => {
    const original = [...lista]
    ordenarUnidades(lista, 'nps', 'asc')
    expect(lista).toEqual(original)
  })
})

describe('filtrarUnidades', () => {
  const lista = [
    unidade('BOTAFOGO', { cidade: 'Rio de Janeiro', consultor: 'MARISE' }),
    unidade('PÁTIO BRASIL', { cidade: 'Brasília', consultor: 'ANDERSON' }),
  ]

  it('busca sem acento e sem caixa', () => {
    expect(filtrarUnidades(lista, 'patio').map((u) => u.nome)).toEqual(['PÁTIO BRASIL'])
    expect(filtrarUnidades(lista, 'BRASILIA').map((u) => u.nome)).toEqual(['PÁTIO BRASIL'])
  })

  it('busca por consultor e por cidade', () => {
    expect(filtrarUnidades(lista, 'marise')).toHaveLength(1)
    expect(filtrarUnidades(lista, 'rio')).toHaveLength(1)
  })

  it('termo vazio devolve tudo', () => {
    expect(filtrarUnidades(lista, '  ')).toHaveLength(2)
  })

  it('normalizar tira acento', () => {
    expect(normalizar('Piçarras / SC')).toBe('picarras / sc')
  })
})

describe('enquadrar', () => {
  it('enquadra pelo bbox, não pela média das coordenadas', () => {
    // A média jogava o centro num ponto sem nenhuma unidade quando a rede é nacional.
    const v = enquadrar(
      { min_lat: -30, min_lng: -55, max_lat: -5, max_lng: -35 },
      { lat: null, lng: null },
    )
    expect(v.latitude).toBeCloseTo(-17.5)
    expect(v.longitude).toBeCloseTo(-45)
    expect(v.zoom).toBeGreaterThan(3)
    expect(v.zoom).toBeLessThan(6)
  })

  it('bbox degenerado (uma unidade só) não estoura o zoom', () => {
    const v = enquadrar(
      { min_lat: -23.5, min_lng: -46.6, max_lat: -23.5, max_lng: -46.6 },
      { lat: null, lng: null },
    )
    expect(Number.isFinite(v.zoom)).toBe(true)
    expect(v.zoom).toBeLessThanOrEqual(11)
  })

  it('sem bbox cai no Brasil inteiro', () => {
    expect(enquadrar(null, { lat: null, lng: null }).zoom).toBeLessThan(4)
  })

  const REDE_NACIONAL = { min_lat: -29, min_lng: -55, max_lat: 3, max_lng: -35 }

  it('card estreito afasta o zoom, senão as unidades das pontas ficam fora', () => {
    // O defeito real: com o mapa de volta ao lado da carteira, o card caiu para ~420x300
    // e a conta antiga — que embutia uma viewport de 512x512 — deixava Boa Vista e o
    // Nordeste fora do quadro.
    const largo = enquadrar(REDE_NACIONAL, { lat: null, lng: null }, { largura: 900, altura: 700 })
    const estreito = enquadrar(REDE_NACIONAL, { lat: null, lng: null }, { largura: 420, altura: 300 })
    expect(estreito.zoom).toBeLessThan(largo.zoom)
  })

  it('cabe nas DUAS dimensões: quem manda é a mais apertada', () => {
    // Card baixo e largo: é a ALTURA que corta. Ignorar isso era o erro da conta antiga,
    // que só olhava o span de longitude.
    const baixo = enquadrar(REDE_NACIONAL, { lat: null, lng: null }, { largura: 900, altura: 200 })
    const quadrado = enquadrar(REDE_NACIONAL, { lat: null, lng: null }, { largura: 900, altura: 900 })
    expect(baixo.zoom).toBeLessThan(quadrado.zoom)
  })

  it('a rede nacional inteira cabe no card estreito, com folga para a bolha', () => {
    const { zoom, latitude, longitude } = enquadrar(
      REDE_NACIONAL,
      { lat: null, lng: null },
      { largura: 420, altura: 300 },
    )
    // Graus de longitude que o card comporta neste zoom (512 px = 360 graus no zoom 0).
    const grausNaLargura = (420 / (512 * 2 ** zoom)) * 360
    expect(grausNaLargura).toBeGreaterThan(REDE_NACIONAL.max_lng - REDE_NACIONAL.min_lng)
    expect(latitude).toBeCloseTo(-13)
    expect(longitude).toBeCloseTo(-45)
  })

  it('viewport absurda (0x0, antes do primeiro layout) não zera o zoom', () => {
    const v = enquadrar(REDE_NACIONAL, { lat: null, lng: null }, { largura: 0, altura: 0 })
    expect(v.zoom).toBeGreaterThanOrEqual(2)
    expect(Number.isFinite(v.zoom)).toBe(true)
  })
})

describe('deveReenquadrar', () => {
  it('recorte novo reenquadra mesmo com ajuste manual — o pan velho aponta para outra rede', () => {
    expect(deveReenquadrar('recorte', true)).toBe(true)
    expect(deveReenquadrar('recorte', false)).toBe(true)
  })

  it('card só mudando de tamanho NÃO desfaz o zoom da pessoa', () => {
    // O caso real: digitar na busca encolhe a tabela, o trilho acompanha, o mapa
    // redimensiona — e o zoom que a pessoa deu numa unidade voltava para a rede inteira.
    expect(deveReenquadrar('tamanho', true)).toBe(false)
  })

  it('sem ajuste manual, mudar de tamanho reenquadra — é como o primeiro layout acerta', () => {
    expect(deveReenquadrar('tamanho', false)).toBe(true)
  })
})

describe('corComAlfa', () => {
  it('mistura a cor com transparente na proporção pedida', () => {
    expect(corComAlfa('#ff5a6e', 12)).toBe('color-mix(in srgb, #ff5a6e 12%, transparent)')
  })

  it('funciona sobre um TOKEN, que é a razão de existir', () => {
    // O sufixo hexadecimal antigo (`${cor}1f`) só valia para `#rrggbb`. Com o semáforo em
    // token, `var(--sev-alta)1f` não é cor nenhuma: o navegador descarta a declaração e o
    // chip perde o fundo — sem erro, sem aviso e sem ninguém perceber.
    expect(corComAlfa(COR_SEVERIDADE.alta, 12)).toBe(
      'color-mix(in srgb, var(--sev-alta) 12%, transparent)',
    )
    expect(corComAlfa(COR_SEVERIDADE.media, 12)).toContain('var(--sev-media)')
  })

  it('as cores do semáforo são todas token, nunca hex', () => {
    // Se alguma voltar a ser hex, o tema claro deixa de alcançá-la e ela fica com o valor
    // do escuro no meio da tela branca.
    for (const cor of Object.values(COR_SEVERIDADE)) {
      expect(cor).toMatch(/^var\(--sev-[a-z-]+\)$/)
    }
  })
})

describe('auxiliares', () => {
  it('rotula a competência em pt-BR', () => {
    expect(rotuloMesCompetencia('2026-06')).toBe('Jun/2026')
  })

  it('o que NÃO é competência volta como veio, em vez de derrubar a aba', () => {
    // Com período livre, a base do SSS chega assim. A versão antiga fazia split('-') e
    // caía num charAt de undefined, pintando a Visão Executiva inteira de preto.
    expect(rotuloMesCompetencia('15/07/2025 a 03/08/2025')).toBe('15/07/2025 a 03/08/2025')
    expect(rotuloMesCompetencia('')).toBe('')
    expect(rotuloMesCompetencia('2026-99')).toBe('2026-99')
  })

  it('monta a query omitindo o que está vazio', () => {
    expect(queryDaCarteira({ mes: '2026-07', uf: '', consultor: undefined })).toBe('?mes=2026-07')
    expect(queryDaCarteira({})).toBe('')
  })
})

function carteira(p: Partial<RedeCarteira> = {}): RedeCarteira {
  return {
    mes: '2026-07',
    meses: ['2026-07', '2026-06'],
    periodo: { inicio: '2026-07-01', fim: '2026-07-31', dias: 31, mes_inteiro: true },
    periodo_anterior: { inicio: '2026-06-01', fim: '2026-06-30' },
    limites: { min: '2022-04-01', max: '2026-08-03' },
    referencia: '31/07/2026',
    referencia_m1: '30/06/2026',
    mes_completo: true,
    competencia_diagnostico: '2026-07',
    totais: { rede: 92, no_recorte: 24, com_coordenada: 21 },
    kpis: {
      faturamento: metrica({ atual: 1_400_000 }),
      ativos: metrica({ atual: 5_400 }),
    },
    split: { recorrentes: null, agregadores: null, pct_recorrentes: null, pct_agregadores: null },
    semaforo: { alta: 3, media: 5, ok: 16, sem_base: 0 },
    sss: {
      disponivel: true,
      competencia_base: '2025-07',
      unidades: 15,
      unidades_recorte: 24,
      unidades_fora: 9,
      metricas: { faturamento: { atual: 1_400_000, ano_anterior: 1_284_000, var_pct: 9 } },
      serie: { meses: [], var_pct: [], unidades: [] },
    },
    centro: { lat: null, lng: null },
    bbox: null,
    ultra_icon: null,
    reguas: {},
    meta_nps: 75,
    serie_meses: [],
    serie_rede: [],
    series: {},
    funil: { visitas: null, convertidos: null, vendas: null, novos_alunos: null, conversao_pct: null, aviso: null },
    faixas: { competencia: '2026-07', faixas: [] },
    coortes: [],
    unidades: [],
    notas: [],
    ...p,
  }
}

describe('narrativaDoRecorte', () => {
  it('recorte vazio devolve UMA frase, e ela não fala de crescimento', () => {
    const frases = narrativaDoRecorte(
      carteira({ totais: { rede: 92, no_recorte: 0, com_coordenada: 0 } }),
      'MARISE · RJ',
    )
    expect(frases).toHaveLength(1)
    expect(frases[0]).toContain('MARISE · RJ')
    expect(frases[0]).toContain('nenhuma unidade')
  })

  it('mês fechado é "fechamento", mês em curso é a JANELA acumulada', () => {
    // Dizer "em agosto" com 3 dias corridos faz o leitor comparar 3 dias com 31.
    expect(narrativaDoRecorte(carteira(), 'a rede')[0]).toContain('no fechamento de julho/2026')
    const emCurso = narrativaDoRecorte(
      carteira({ mes: '2026-08', mes_completo: false, referencia: '03/08/2026' }),
      'a rede',
    )
    expect(emCurso[0]).toContain('no acumulado do mês até 03/08')
    expect(emCurso[0]).not.toContain('fechamento')
  })

  it('o sujeito entra maiúsculo sem estragar o nome do consultor', () => {
    expect(narrativaDoRecorte(carteira(), 'a rede')[0].startsWith('A rede tem 24 unidades')).toBe(true)
    expect(narrativaDoRecorte(carteira(), 'MARISE')[0].startsWith('MARISE tem 24 unidades')).toBe(true)
  })

  it('lê o recorte de referência inteiro, do jeito que vai para a tela', () => {
    // O cenário real medido em 2026-08-10: MARISE, +9,0% com 15 das 24 comparáveis.
    // O teste fixa a PROSA, não só os pedaços — é a única forma de revisar concordância
    // e pontuação sem abrir o navegador.
    expect(
      narrativaDoRecorte(
        carteira({
          funil: { visitas: 1_240, convertidos: 400, vendas: 420, novos_alunos: 300, conversao_pct: 24.2, aviso: null },
        }),
        'MARISE',
      ),
    ).toEqual([
      'MARISE tem 24 unidades, com R$ 1,4 mi de faturamento e 5.400 alunos ativos no fechamento de julho/2026.',
      'Na mesma base (15 das 24 unidades), o faturamento cresce 9,0% contra Jul/2025; as outras 9 não existiam há um ano.',
      'O diagnóstico de Jul/2026 aponta 3 unidades em prioridade alta e 5 em atenção.',
      'A conversão de visita em aluno fica em 24,2%, sobre 1.240 visitas no período.',
    ])
  })

  it('diz a base comparável ANTES do número do SSS', () => {
    const frase = narrativaDoRecorte(carteira(), 'MARISE')[1]
    expect(frase).toContain('Na mesma base (15 das 24 unidades)')
    expect(frase).toContain('cresce 9,0% contra Jul/2025')
    expect(frase).toContain('as outras 9 não existiam há um ano')
  })

  it('queda usa o VERBO certo — nunca "cresce −2,5%"', () => {
    const frase = narrativaDoRecorte(
      carteira({
        sss: {
          ...carteira().sss,
          metricas: { faturamento: { atual: 900_000, ano_anterior: 923_000, var_pct: -2.5 } },
        },
      }),
      'GUILHERME',
    )[1]
    expect(frase).toContain('cai 2,5%')
    expect(frase).not.toContain('cresce')
    expect(frase).not.toContain('-2,5')
  })

  it('variação irrelevante não vira "cresce 0,0%"', () => {
    const frase = narrativaDoRecorte(
      carteira({
        sss: {
          ...carteira().sss,
          metricas: { faturamento: { atual: 900_000, ano_anterior: 900_000, var_pct: 0.01 } },
        },
      }),
      'a rede',
    )[1]
    expect(frase).toContain('fica estável')
  })

  it('sem unidade de fora, a oração extra não aparece', () => {
    const frase = narrativaDoRecorte(
      carteira({
        sss: { ...carteira().sss, unidades: 24, unidades_recorte: 24, unidades_fora: 0 },
      }),
      'MARISE',
    )[1]
    expect(frase).toContain('Na mesma base (24 das 24 unidades)')
    expect(frase).not.toContain('há um ano')
  })

  it('SSS indisponível vira frase honesta, não um zero', () => {
    const frases = narrativaDoRecorte(
      carteira({
        sss: {
          disponivel: false,
          competencia_base: '2025-07',
          unidades: 0,
          unidades_recorte: 3,
          unidades_fora: 3,
          serie: { meses: [], var_pct: [], unidades: [] },
        },
      }),
      'uma coorte nova',
    )
    expect(frases[1]).toContain('Não há base comparável neste recorte')
    expect(frases[1]).toContain('Jul/2025')
    expect(frases[1]).not.toContain('0,0%')
  })

  it('KPI nulo derruba a cláusula — não vira travessão nem "Não disponível"', () => {
    const frases = narrativaDoRecorte(carteira({ kpis: { faturamento: metrica(), ativos: metrica() } }), 'RJ')
    expect(frases[0]).toBe('RJ tem 24 unidades no fechamento de julho/2026.')
    for (const frase of frases) {
      expect(frase).not.toContain('—')
      expect(frase).not.toContain(TEXTO_SEM_DADO)
    }
  })

  it('o diagnóstico diz de QUE competência é — ele quase nunca é a da tela', () => {
    const frase = narrativaDoRecorte(carteira({ mes: '2026-08', competencia_diagnostico: '2026-07' }), 'a rede')[2]
    expect(frase).toBe('O diagnóstico de Jul/2026 aponta 3 unidades em prioridade alta e 5 em atenção.')
  })

  it('recorte sem alerta nenhum não fica sem a frase de diagnóstico', () => {
    const frase = narrativaDoRecorte(
      carteira({ semaforo: { alta: 0, media: 0, ok: 24, sem_base: 0 } }),
      'a rede',
    )[2]
    expect(frase).toContain('não aponta nenhuma unidade')
  })

  it('só em atenção: a frase mantém o substantivo', () => {
    const frase = narrativaDoRecorte(
      carteira({ semaforo: { alta: 0, media: 1, ok: 23, sem_base: 0 } }),
      'a rede',
    )[2]
    expect(frase).toContain('1 unidade em atenção')
  })

  it('período livre fala por extenso, e não promete um mês que não foi analisado', () => {
    const frase = narrativaDoRecorte(
      carteira({
        periodo: { inicio: '2026-07-15', fim: '2026-08-03', dias: 20, mes_inteiro: false },
        mes_completo: false,
      }),
      'a rede',
    )[0]
    expect(frase).toContain('no período de')
    expect(frase).not.toContain('fechamento')
  })

  it('funil só entra quando há conversão apurada — 3 frases sem ele, 4 com ele', () => {
    expect(narrativaDoRecorte(carteira(), 'a rede')).toHaveLength(3)
    const comFunil = narrativaDoRecorte(
      carteira({
        funil: { visitas: 1_240, convertidos: 400, vendas: 420, novos_alunos: 300, conversao_pct: 24.2, aviso: null },
      }),
      'a rede',
    )
    expect(comFunil).toHaveLength(4)
    expect(comFunil[3]).toBe('A conversão de visita em aluno fica em 24,2%, sobre 1.240 visitas no período.')
  })
})

describe('destaquesDoRecorte', () => {
  // A variação vem do bloco `sss` (ano a ano) ou do `fechado` (mês contra mês anterior),
  // NUNCA do `delta_pct` do quarteto: este compara MTD contra MTD e, no dia 3 da
  // competência em curso, uma unidade que saiu de R$ 400 para R$ 26 mil lidera com
  // +6.239%. Por isso a fábrica abaixo cravou 999 no delta_pct — se ele voltar a ser lido,
  // os testes quebram na hora.
  const comVar = (nome: string, variacao: number | null, p: Partial<RedeUnidade> = {}) =>
    unidade(nome, {
      sss: { competencia_base: '2025-07', faturamento: 100_000, ano_anterior: 90_000, var_pct: variacao },
      fechado: { competencia: '2026-07', faturamento: 100_000, variacao_pct: variacao },
      metricas: { faturamento: metrica({ atual: 100_000, delta_pct: 999 }) },
      ...p,
    })

  const nomes = (itens: { unidade: RedeUnidade }[]) => itens.map((d) => d.unidade.nome)

  it('quem PUXA cresce e quem SEGURA cai — a divisao e por sinal, nao por posicao', () => {
    // Com 4 comparaveis e `quantos = 5`, o corte por posicao jogava as quatro em "quem
    // puxa", inclusive as duas que estavam CAINDO. Aconteceu de verdade no recorte do
    // consultor GUILHERME, com VILA MARIANA (-2,2%) e ACLIMACAO (-4,0%) no topo.
    const lista = [comVar('A', 2.6), comVar('B', 2), comVar('C', -2.2), comVar('D', -4)]
    const { puxam, seguram } = destaquesDoRecorte(lista)
    expect(nomes(puxam)).toEqual(['A', 'B'])
    expect(nomes(seguram)).toEqual(['D', 'C'])
  })

  it('corta em `quantos` DENTRO de cada sinal', () => {
    const lista = [
      comVar('A', 7), comVar('B', 6), comVar('C', 5), comVar('D', 4),
      comVar('E', 3), comVar('F', 2), comVar('G', 1),
    ]
    const { puxam, seguram, todas } = destaquesDoRecorte(lista)
    expect(nomes(puxam)).toEqual(['A', 'B', 'C', 'D', 'E'])
    expect(seguram).toEqual([])
    // `todas` ignora o corte: e a lista completa que o painel expande.
    expect(nomes(todas)).toEqual(['A', 'B', 'C', 'D', 'E', 'F', 'G'])
  })

  it('recorte inteiro em queda deixa "quem puxa" vazio em vez de promover uma queda', () => {
    const { puxam, seguram } = destaquesDoRecorte([comVar('A', -3), comVar('B', -1)])
    expect(puxam).toEqual([])
    expect(nomes(seguram)).toEqual(['A', 'B'])
  })

  it('variacao exatamente zero nao e nem uma coisa nem outra', () => {
    const { puxam, seguram, todas } = destaquesDoRecorte([comVar('PARADA', 0), comVar('SOBE', 1)])
    expect(nomes(puxam)).toEqual(['SOBE'])
    expect(seguram).toEqual([])
    // ...mas continua na lista completa: zero e um resultado, nao um dado ausente.
    expect(nomes(todas)).toEqual(['SOBE', 'PARADA'])
  })

  it('quem segura vem da PIOR para a menos pior', () => {
    const lista = [comVar('A', 30), comVar('B', 10), comVar('C', -5), comVar('D', -40)]
    const { seguram } = destaquesDoRecorte(lista, 'sss', 2)
    expect(nomes(seguram)).toEqual(['D', 'C'])
  })

  it('unidade não comparável fica fora — o "+900%" dela é inauguração, não desempenho', () => {
    const lista = [comVar('NOVA', 900, { comparavel: false }), comVar('VELHA', 4)]
    const { puxam, semBase } = destaquesDoRecorte(lista)
    expect(nomes(puxam)).toEqual(['VELHA'])
    // Fica fora da CONTA, mas visível na lista completa: sumir com ela faria a lista
    // parecer completa quando não é.
    expect(semBase.map((u) => u.nome)).toEqual(['NOVA'])
  })

  it('sem base comparável apurada, a unidade vai para `semBase`', () => {
    const lista = [comVar('SEM', null), unidade('VAZIA'), comVar('COM', 2)]
    const { puxam, seguram, semBase } = destaquesDoRecorte(lista)
    expect(nomes(puxam)).toEqual(['COM'])
    expect(seguram).toEqual([])
    expect(semBase.map((u) => u.nome)).toEqual(['SEM', 'VAZIA'])
  })

  it('empate desempata por nome, para a lista não piscar entre renders', () => {
    expect(nomes(destaquesDoRecorte([comVar('Zulu', 10), comVar('Alfa', 10)]).puxam)).toEqual([
      'Alfa',
      'Zulu',
    ])
  })

  it('a base escolhida troca a ordem E a competência do rodapé', () => {
    const lista = [
      unidade('SOBE_NO_ANO', {
        sss: { competencia_base: '2025-07', faturamento: 200_000, ano_anterior: 100_000, var_pct: 100 },
        fechado: { competencia: '2026-07', faturamento: 200_000, variacao_pct: -10 },
      }),
      unidade('SOBE_NO_MES', {
        sss: { competencia_base: '2025-07', faturamento: 50_000, ano_anterior: 60_000, var_pct: -16 },
        fechado: { competencia: '2026-07', faturamento: 50_000, variacao_pct: 30 },
      }),
    ]
    const anoAno = destaquesDoRecorte(lista, 'sss')
    expect(nomes(anoAno.puxam)).toEqual(['SOBE_NO_ANO'])
    expect(nomes(anoAno.seguram)).toEqual(['SOBE_NO_MES'])
    expect(anoAno.competencia).toBe('2025-07')
    // O faturamento exibido acompanha a base: e o par do numero que ordenou a lista.
    expect(anoAno.puxam[0].faturamento).toBe(200_000)

    const mesMes = destaquesDoRecorte(lista, 'mes')
    expect(nomes(mesMes.puxam)).toEqual(['SOBE_NO_MES'])
    expect(nomes(mesMes.seguram)).toEqual(['SOBE_NO_ANO'])
    expect(mesMes.competencia).toBe('2026-07')
  })

  it('IGNORA o delta_pct do quarteto, que é MTD contra MTD', () => {
    // A ordem por `delta_pct` seria RUIDO, LENTA; pela base comparável é LENTA, RUIDO.
    const lista = [
      unidade('RUIDO', {
        sss: { competencia_base: '2025-07', faturamento: 26_000, ano_anterior: 27_000, var_pct: -3 },
        metricas: { faturamento: metrica({ atual: 26_000, delta_pct: 6_239.6 }) },
      }),
      unidade('LENTA', {
        sss: { competencia_base: '2025-07', faturamento: 95_000, ano_anterior: 91_346, var_pct: 4 },
        metricas: { faturamento: metrica({ atual: 95_000, delta_pct: 1 }) },
      }),
    ]
    const { puxam, seguram } = destaquesDoRecorte(lista)
    expect(nomes(puxam)).toEqual(['LENTA'])
    expect(nomes(seguram)).toEqual(['RUIDO'])
    expect(puxam[0].variacao_pct).toBe(4)
    expect(puxam[0].faturamento).toBe(95_000)
  })

  it('não mexe na lista recebida', () => {
    const lista = [comVar('A', 9), comVar('B', 2)]
    const original = [...lista]
    destaquesDoRecorte(lista)
    expect(lista).toEqual(original)
  })
})
