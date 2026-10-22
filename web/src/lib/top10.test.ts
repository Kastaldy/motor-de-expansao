import { describe, expect, it } from 'vitest'

import { TEXTO_SEM_DADO } from './constants'
import { alunos, num, renda } from './format'
import {
  ROTULO_SEGMENTO_TOP10,
  SEGMENTOS_TOP10,
  TEXTOS_TOP10_POR_PAIS,
  TOKEN_COR_TOP10,
  TOP_POR_LEITURA,
  cabecalhoTop10,
  corDaEtiquetaTop10,
  corTop10,
  destinoDaVaga,
  hexesComTop10,
  legendaTop10,
  leiturasDoRecorte,
  linhaSecundaria,
  mapaTop10,
  montarBlocosTop10,
  principalDaVaga,
  referenciaTecnicaDaRegua,
  rotuloDaVersaoDaRegua,
  rotuloNoMapa,
  temTop10,
  textoDaRegua,
  textoLeituraVazia,
  textosTop10,
  textoVersaoDaRegua,
  tituloTop10,
  top10Indisponivel,
  totalVagas,
  vagasPreenchidas,
  type LinhaTop10Regiao,
} from './top10'
import type {
  Passo,
  RecomendacaoTop10,
  ReguaTop10,
  SegmentoTop10,
  SegmentoTop10Payload,
  VagaTop10,
} from './types'

/* ---------------------------------------------------------------------------------------
   Fixture com a FORMA EXATA de `Recomendacao.para_payload` (nucleo.py) — a mesma do exemplo
   real de São José dos Campos do plano da Fase 4: 3 Mata Virgem preenchidas + 2 vazias e
   3 Premium preenchidas + 2 vazias (6 de 10). Floats crus, de propósito.
   --------------------------------------------------------------------------------------- */

const ROTULOS: RecomendacaoTop10['rotulos'] = {
  segmento: { mata_virgem: 'Mata Virgem', premium: 'Premium' },
  status: { completo: 'Completo', incompleto: 'Incompleto', indisponivel: 'Indisponível' },
  motivo: {
    renda_indisponivel: 'Renda indisponível: recomendação suspensa até a base ser corrigida',
    candidatos_insuficientes: 'Não há outra região que atenda à régua neste recorte',
  },
  sem_dado: {
    sem_renda: 'Sem renda domiciliar',
    sem_residual: 'Sem residual',
    residual_estimado: 'Residual estimado (não medido)',
    sem_populacao: 'Sem população do Censo',
    sem_score: 'Sem score censitário',
    abaixo_da_populacao_minima: 'Abaixo da população mínima',
    indeterminado_mv: 'Sem dado para descartar Mata Virgem',
  },
}

const REGUA_BR_V1: ReguaTop10 = {
  versao: '2026-10_v1',
  pais: 'BR',
  dec: 'DEC-077',
  aprovado_por: 'Felipe Silva (GATE 1 e GATE 2)',
  fixada_por_env: false,
  vagas_por_segmento: 5,
  mata_virgem: {
    renda_domiciliar_min: 4500.0,
    residual_min: 2000.0,
    populacao_min: null,
    exige_residual_medido: true,
  },
  premium: { score_min: 50.0, populacao_min: 10000.0, exige_residual_medido: true },
}

function preenchida(segmento: SegmentoTop10, posicao: number, extra: Partial<VagaTop10> = {}): VagaTop10 {
  return {
    segmento,
    posicao,
    vazia: false,
    motivo: null,
    rotulo_motivo: null,
    hex_id: `87a812aa${segmento === 'premium' ? 'e' : '3'}${posicao}fffff`,
    nome_regiao: `Setor Socioeconômico ${posicao}`,
    renda_domiciliar: 7624.898618347119,
    renda_municipal: false,
    populacao: 42764.7268011927,
    residual: segmento === 'premium' ? 0.0 : 4155.39111328125,
    residual_medido: true,
    score_censitario: 57.852378845214844,
    uf: 'SP',
    cod_municipio: '3549904',
    nome_municipio: 'São José dos Campos',
    lat: -23.246980667114258,
    lng: -45.89113998413086,
    ...extra,
  }
}

function vazia(
  segmento: SegmentoTop10,
  posicao: number,
  motivo: 'candidatos_insuficientes' | 'renda_indisponivel' = 'candidatos_insuficientes',
): VagaTop10 {
  return {
    segmento,
    posicao,
    vazia: true,
    motivo,
    rotulo_motivo: ROTULOS.motivo[motivo],
    hex_id: null,
    nome_regiao: null,
    renda_domiciliar: null,
    renda_municipal: false,
    populacao: null,
    residual: null,
    residual_medido: false,
    score_censitario: null,
    uf: null,
    cod_municipio: null,
    nome_municipio: null,
    lat: null,
    lng: null,
  }
}

function segmento(
  seg: SegmentoTop10,
  vagas: VagaTop10[],
  extra: Partial<SegmentoTop10Payload> = {},
): SegmentoTop10Payload {
  return {
    segmento: seg,
    rotulo: ROTULOS.segmento[seg],
    status: vagas.every((v) => !v.vazia) ? 'completo' : 'incompleto',
    rotulo_status: vagas.every((v) => !v.vazia) ? 'Completo' : 'Incompleto',
    n_elegiveis: vagas.filter((v) => !v.vazia).length,
    sem_dado: {},
    vagas,
    ...extra,
  }
}

function bloco(extra: Partial<RecomendacaoTop10> = {}): RecomendacaoTop10 {
  return {
    versao_payload: 1,
    regra: REGUA_BR_V1,
    recorte: { nivel: 'municipio', uf: 'SP', cod_municipio: '3549904', nome: 'São José dos Campos' },
    n_hexes_recorte: 205,
    renda: {
      disponivel: true,
      k: 1.2334632196696071,
      carimbo: 'multiplicativo_global_k=1.2334632196696071',
      fatores_versao: '2026-10_pnad2025_v1',
      pais: 'BR',
    },
    mata_virgem: segmento(
      'mata_virgem',
      [
        preenchida('mata_virgem', 1, { residual: 4155.39111328125 }),
        preenchida('mata_virgem', 2, { residual: 3100.5 }),
        preenchida('mata_virgem', 3, { residual: 2050.25 }),
        vazia('mata_virgem', 4),
        vazia('mata_virgem', 5),
      ],
      { n_elegiveis: 3 },
    ),
    premium: segmento(
      'premium',
      [
        preenchida('premium', 1, { populacao: 38685.10797239564, score_censitario: 68.28221893310547 }),
        preenchida('premium', 2, { populacao: 30120.0 }),
        preenchida('premium', 3, { populacao: 12000.0 }),
        vazia('premium', 4),
        vazia('premium', 5),
      ],
      { n_elegiveis: 3 },
    ),
    rotulos: ROTULOS,
    ...extra,
  }
}

/** Staging sem o carimbo k: os dois segmentos indisponíveis, todas as vagas vazias. */
function blocoSemK(): RecomendacaoTop10 {
  const seg = (s: SegmentoTop10): SegmentoTop10Payload => ({
    segmento: s,
    rotulo: ROTULOS.segmento[s],
    status: 'indisponivel',
    rotulo_status: 'Indisponível',
    n_elegiveis: 0,
    sem_dado: {},
    vagas: [1, 2, 3, 4, 5].map((p) => vazia(s, p, 'renda_indisponivel')),
  })
  return bloco({
    renda: { disponivel: false, k: null, carimbo: null, fatores_versao: null, pais: null },
    mata_virgem: seg('mata_virgem'),
    premium: seg('premium'),
  })
}

const regioes = (linhas: { tipo: string }[]) =>
  linhas.filter((l): l is LinhaTop10Regiao => l.tipo === 'regiao')

describe('temTop10 — o discriminador', () => {
  it('com o bloco, é Top 10; sem ele (AR, ranking legado), é o caminho de sempre', () => {
    expect(temTop10({ recomendacao: bloco() })).toBe(true)
    expect(temTop10({ nivel: 'uf', passos: [] })).toBe(false)
    expect(temTop10({ reguas: {}, cobertura: {}, itens: [] })).toBe(false)
    expect(temTop10(null)).toBe(false)
    expect(temTop10(undefined)).toBe(false)
  })

  it('a chave presente com valor nulo NÃO liga o modo Top 10', () => {
    expect(temTop10({ recomendacao: null })).toBe(false)
  })
})

describe('montarBlocosTop10 — a resposta é o bloco do servidor, na ordem dele', () => {
  it('sempre dois blocos fixos, Mata Virgem e depois Premium, com cinco linhas cada', () => {
    const blocos = montarBlocosTop10(bloco())
    expect(blocos.map((b) => b.segmento)).toEqual(['mata_virgem', 'premium'])
    expect(blocos.map((b) => b.titulo)).toEqual(['Mata Virgem', 'Premium'])
    for (const b of blocos) expect(b.linhas).toHaveLength(5)
  })

  it('preserva a ORDEM DO SERVIDOR mesmo com o número principal fora de ordem', () => {
    /* O front não reordena: a ordem e o desempate são do servidor. Aqui o residual da
       posição 1 é MENOR que o da 2 — uma lista que ordenasse por valor trocaria as duas. */
    const b = bloco()
    b.mata_virgem.vagas[0] = preenchida('mata_virgem', 1, { residual: 2100 })
    b.mata_virgem.vagas[1] = preenchida('mata_virgem', 2, { residual: 9000 })
    const [mv] = montarBlocosTop10(b)
    expect(mv.linhas.map((l) => l.posicao)).toEqual([1, 2, 3, 4, 5])
    expect(regioes(mv.linhas).map((l) => l.chave)).toEqual(
      b.mata_virgem.vagas.filter((v) => !v.vazia).map((v) => v.hex_id),
    )
    expect(regioes(mv.linhas).map((l) => l.principal.valor)).toEqual([
      alunos(2100),
      alunos(9000),
      alunos(2050.25),
    ])
  })

  it('não filtra nada: as vagas vazias continuam como linha, na posição delas', () => {
    const [mv, pr] = montarBlocosTop10(bloco())
    expect(mv.linhas.map((l) => l.tipo)).toEqual(['regiao', 'regiao', 'regiao', 'vazia', 'vazia'])
    expect(pr.linhas.map((l) => l.tipo)).toEqual(['regiao', 'regiao', 'regiao', 'vazia', 'vazia'])
  })

  it('vaga vazia diz o motivo do servidor, e a chave é segmento-posição', () => {
    const [, pr] = montarBlocosTop10(bloco())
    const v = pr.linhas[3]
    expect(v).toEqual({
      tipo: 'vazia',
      chave: 'premium-4',
      posicao: 4,
      rotulo: 'P4',
      texto: 'Vaga vazia — Não há outra região que atenda à régua neste recorte',
    })
  })

  it('vizinhos do mesmo bairro viram linhas distintas: a chave é o hex_id, não o nome', () => {
    const b = bloco()
    b.mata_virgem.vagas[0] = preenchida('mata_virgem', 1, { nome_regiao: 'Centro' })
    b.mata_virgem.vagas[1] = preenchida('mata_virgem', 2, { nome_regiao: 'Centro' })
    const [mv] = montarBlocosTop10(b)
    const [a, c] = regioes(mv.linhas)
    expect(a.nome).toBe('Centro')
    expect(c.nome).toBe('Centro')
    expect(a.chave).not.toBe(c.chave)
  })

  it('o número principal é a CHAVE do segmento: residual (Mata Virgem) e população (Premium)', () => {
    const [mv, pr] = montarBlocosTop10(bloco())
    expect(regioes(mv.linhas)[0].principal).toEqual({
      valor: alunos(4155.39111328125),
      unidade: 'alunos de residual',
    })
    expect(regioes(pr.linhas)[0].principal).toEqual({
      valor: num(38685.10797239564),
      unidade: 'habitantes (Censo)',
    })
  })

  it('nome = bairro, senão o município, senão o texto de "sem dado"', () => {
    const b = bloco()
    b.mata_virgem.vagas[1] = preenchida('mata_virgem', 2, { nome_regiao: null })
    b.mata_virgem.vagas[2] = preenchida('mata_virgem', 3, { nome_regiao: null, nome_municipio: null })
    const nomes = regioes(montarBlocosTop10(b)[0].linhas).map((l) => l.nome)
    expect(nomes).toEqual(['Setor Socioeconômico 1', 'São José dos Campos', TEXTO_SEM_DADO])
  })

  it('o município aparece abaixo do nome fora do nível município, sem repetir o nome', () => {
    const noMunicipio = montarBlocosTop10(bloco())
    expect(regioes(noMunicipio[0].linhas)[0].municipioUf).toBeNull()

    const b = bloco({ recorte: { nivel: 'uf', uf: 'SP', cod_municipio: null, nome: 'SP' } })
    b.premium.vagas[0] = preenchida('premium', 1, { nome_regiao: null })
    const [mv, pr] = montarBlocosTop10(b)
    expect(regioes(mv.linhas)[0].municipioUf).toBe('São José dos Campos · SP')
    // Sem bairro o título JÁ é o município: abaixo dele sobra só a UF.
    expect(regioes(pr.linhas)[0].nome).toBe('São José dos Campos')
    expect(regioes(pr.linhas)[0].municipioUf).toBe('SP')
  })

  it('o hex aparece curto, como nas outras listas', () => {
    const [mv] = montarBlocosTop10(bloco())
    expect(regioes(mv.linhas)[0].hexCurto).toBe('hex 87a812aa3…')
  })
})

describe('segmento indisponível (staging sem o carimbo k)', () => {
  it('uma mensagem por bloco — status e motivo —, e as linhas continuam vazias', () => {
    const blocos = montarBlocosTop10(blocoSemK())
    for (const b of blocos) {
      expect(b.indisponivel).toEqual({
        titulo: 'Indisponível',
        motivo: 'Renda indisponível: recomendação suspensa até a base ser corrigida',
      })
      expect(b.linhas.every((l) => l.tipo === 'vazia')).toBe(true)
      expect(b.nElegiveis).toBe(0)
    }
  })

  it('sem cálculo não há "0 candidatos": o texto de candidatos some do bloco', () => {
    /* "Mata Virgem · 0 candidatos" ao lado de "Indisponível" leria como "ninguém passou na
       régua" — e a régua nem rodou. */
    for (const b of montarBlocosTop10(blocoSemK())) {
      expect(b.textoCandidatos).toBeNull()
      expect(b.semCandidato).toBeNull()
    }
  })

  it('o cabeçalho diz "Top 10 indisponível", e não "0 de 10 vagas preenchidas"', () => {
    expect(top10Indisponivel(blocoSemK())).toBe(true)
    expect(cabecalhoTop10(blocoSemK())).toEqual({ vagas: 'Top 10 indisponível', candidatos: null })
    // O total segue a régua, como em todo o resto.
    const oito = blocoSemK()
    oito.regra = { ...REGUA_BR_V1, vagas_por_segmento: 4 }
    expect(cabecalhoTop10(oito).vagas).toBe('Top 8 indisponível')
  })

  it('um segmento só indisponível: o cabeçalho conta o outro e diz o status deste', () => {
    const b = bloco()
    b.premium = { ...b.premium, status: 'indisponivel', rotulo_status: 'Indisponível', n_elegiveis: 0 }
    expect(top10Indisponivel(b)).toBe(false)
    expect(cabecalhoTop10(b).candidatos).toBe('3 candidatos Mata Virgem · Premium indisponível')
  })

  it('segmento calculado não leva a mensagem', () => {
    for (const b of montarBlocosTop10(bloco())) expect(b.indisponivel).toBeNull()
    expect(top10Indisponivel(bloco())).toBe(false)
  })
})

describe('segmento calculado sem nenhum candidato — uma frase, não cinco linhas iguais', () => {
  /** O caso mais comum fora das cidades grandes: a régua rodou e ninguém passou. */
  function semPremium(recorte?: RecomendacaoTop10['recorte']): RecomendacaoTop10 {
    const b = bloco(recorte ? { recorte } : {})
    b.premium = segmento(
      'premium',
      [1, 2, 3, 4, 5].map((p) => vazia('premium', p)),
      { n_elegiveis: 0, status: 'incompleto', rotulo_status: 'Incompleto' },
    )
    return b
  }

  it('a frase sai do payload: rótulo do segmento, nível do recorte e vagas da régua', () => {
    const [mv, pr] = montarBlocosTop10(semPremium())
    expect(pr.semCandidato).toBe(
      'Nenhuma região deste município atende à régua de Premium — as 5 vagas ficam vazias.',
    )
    expect(pr.textoCandidatos).toBe('0 candidatos')
    // Sem o "Não há OUTRA região" do motivo da vaga vazia: aqui não há nenhuma.
    expect(pr.semCandidato).not.toContain('outra')
    // O segmento que tem candidato segue com as linhas, sem a frase.
    expect(mv.semCandidato).toBeNull()
    // As linhas continuam no bloco, para quem quiser auditar.
    expect(pr.linhas).toHaveLength(5)
  })

  it('o lugar acompanha o recorte (estado, país)', () => {
    const uf = semPremium({ nivel: 'uf', uf: 'TO', cod_municipio: null, nome: 'TO' })
    expect(montarBlocosTop10(uf)[1].semCandidato).toContain('Nenhuma região deste estado')
    const br = semPremium({ nivel: 'brasil', uf: null, cod_municipio: null, nome: 'Brasil' })
    expect(montarBlocosTop10(br)[1].semCandidato).toContain('Nenhuma região do Brasil')
  })

  it('com uma vaga por segmento, a frase concorda no singular', () => {
    const b = bloco({ regra: { ...REGUA_BR_V1, vagas_por_segmento: 1 } })
    b.premium = segmento('premium', [vazia('premium', 1)], {
      n_elegiveis: 0,
      status: 'incompleto',
      rotulo_status: 'Incompleto',
    })
    expect(montarBlocosTop10(b)[1].semCandidato).toContain('— a vaga fica vazia.')
  })

  it('candidato insuficiente (algumas vagas preenchidas) segue linha a linha', () => {
    const [, pr] = montarBlocosTop10(bloco())
    expect(pr.semCandidato).toBeNull()
    expect(pr.linhas.map((l) => l.tipo)).toEqual(['regiao', 'regiao', 'regiao', 'vazia', 'vazia'])
  })
})

describe('rotuloNoMapa', () => {
  it('MV1..MV5 e P1..P5', () => {
    const b = bloco()
    expect(b.mata_virgem.vagas.map(rotuloNoMapa)).toEqual(['MV1', 'MV2', 'MV3', 'MV4', 'MV5'])
    expect(b.premium.vagas.map(rotuloNoMapa)).toEqual(['P1', 'P2', 'P3', 'P4', 'P5'])
  })
})

describe('cabecalhoTop10', () => {
  it('"6 de 10 vagas preenchidas" e os candidatos por segmento', () => {
    const b = bloco()
    b.mata_virgem.n_elegiveis = 11
    b.premium.n_elegiveis = 5
    expect(cabecalhoTop10(b)).toEqual({
      vagas: '6 de 10 vagas preenchidas',
      candidatos: '11 candidatos Mata Virgem · 5 candidatos Premium',
    })
  })

  it('singular quando há um candidato', () => {
    const b = bloco()
    b.mata_virgem.n_elegiveis = 1
    expect(cabecalhoTop10(b).candidatos).toBe('1 candidato Mata Virgem · 3 candidatos Premium')
  })

  it('o total de vagas sai da régua, não de um 10 cravado', () => {
    const b = bloco({ regra: { ...REGUA_BR_V1, vagas_por_segmento: 4 } })
    expect(totalVagas(b)).toBe(8)
    expect(vagasPreenchidas(b)).toBe(6)
    expect(cabecalhoTop10(b).vagas).toBe('6 de 8 vagas preenchidas')
  })
})

describe('textoDaRegua — montado só com os números do payload', () => {
  it('a régua BR v1 vira o texto esperado', () => {
    expect(textoDaRegua(REGUA_BR_V1, ROTULOS)).toBe(
      `Mata Virgem: renda domiciliar a partir de ${renda(4500)} e residual medido a partir de ` +
        `${num(2000)} alunos, na ordem do residual. Premium: score censitário a partir de 50 e ` +
        `população a partir de ${num(10000)} habitantes, fora da Mata Virgem e com residual ` +
        'medido, na ordem da população. Até 5 regiões por segmento; vaga sem candidato fica ' +
        'vazia — um segmento nunca completa o outro. Concorrência, viabilidade, aluguel e ' +
        'proximidade da Ultra não entram nesta conta.',
    )
  })

  it('trocar a régua troca o texto (nenhum número é literal)', () => {
    const outra: ReguaTop10 = {
      ...REGUA_BR_V1,
      vagas_por_segmento: 4,
      mata_virgem: {
        renda_domiciliar_min: 6000,
        residual_min: 3000,
        populacao_min: 8000,
        exige_residual_medido: false,
      },
      premium: { score_min: 55.5, populacao_min: null, exige_residual_medido: false },
    }
    const t = textoDaRegua(outra, ROTULOS)
    expect(t).toContain(`renda domiciliar a partir de ${renda(6000)}`)
    expect(t).toContain(`residual a partir de ${num(3000)} alunos`)
    expect(t).not.toContain('residual medido a partir')
    expect(t).toContain(`população a partir de ${num(8000)} habitantes, na ordem do residual`)
    expect(t).toContain(`score censitário a partir de ${num(55.5, 1)}, fora da Mata Virgem, na ordem`)
    expect(t).not.toContain('com residual medido')
    expect(t).toContain('Até 4 regiões por segmento')
    expect(t).not.toContain(renda(4500))
  })

  it('os rótulos dos segmentos saem do payload', () => {
    const rotulos = { ...ROTULOS, segmento: { mata_virgem: 'Território livre', premium: 'Alta renda' } }
    const t = textoDaRegua(REGUA_BR_V1, rotulos)
    expect(t.startsWith('Território livre: ')).toBe(true)
    expect(t).toContain('Alta renda: score')
    expect(t).toContain('fora da Território livre')
  })

  it('sem rótulos no payload, cai na reserva de exibição', () => {
    expect(textoDaRegua(REGUA_BR_V1).startsWith(`${ROTULO_SEGMENTO_TOP10.mata_virgem}: `)).toBe(true)
  })
})

describe('linhaSecundaria e principal', () => {
  it('renda domiciliar, população, residual e score censitário com uma casa', () => {
    expect(linhaSecundaria(preenchida('mata_virgem', 1))).toBe(
      `Renda domiciliar ${renda(7624.898618347119)} · ${num(42764.7268011927)} hab. · ` +
        `${alunos(4155.39111328125)} alunos de residual · score censitário ${num(57.852378845214844, 1)}`,
    )
  })

  it('o score é o CENSITÁRIO, por extenso — o tooltip também mostra o Score M1', () => {
    expect(linhaSecundaria(preenchida('premium', 1))).not.toMatch(/· score \d/)
    expect(linhaSecundaria(preenchida('premium', 1, { score_censitario: null }))).toContain(
      'score censitário não disponível',
    )
  })

  it('renda do fallback municipal é declarada', () => {
    expect(linhaSecundaria(preenchida('mata_virgem', 1, { renda_municipal: true }))).toContain(
      `Renda domiciliar ${renda(7624.898618347119)} (municipal)`,
    )
  })

  it('residual estimado aparece como "não medido", nunca como número', () => {
    const v = preenchida('premium', 1, { residual: null, residual_medido: false })
    expect(linhaSecundaria(v)).toContain('residual não medido')
    expect(principalDaVaga(preenchida('mata_virgem', 1, { residual: null, residual_medido: false }))).toEqual({
      valor: 'não medido',
      unidade: 'residual',
    })
  })

  it('o residual zero MEDIDO do Premium aparece como 0, não como "—"', () => {
    expect(linhaSecundaria(preenchida('premium', 1, { residual: 0 }))).toContain(
      `${alunos(0)} alunos de residual`,
    )
  })

  it('score com uma casa decimal', () => {
    expect(linhaSecundaria(preenchida('premium', 1, { score_censitario: 68.28221893310547 }))).toContain(
      `score censitário ${num(68.3, 1)}`,
    )
  })
})

describe('tituloTop10', () => {
  it('Brasil, UF e município', () => {
    expect(tituloTop10(bloco({ recorte: { nivel: 'brasil', uf: null, cod_municipio: null, nome: 'Brasil' } }))).toBe(
      'Top 10 do Brasil',
    )
    expect(tituloTop10(bloco({ recorte: { nivel: 'uf', uf: 'SP', cod_municipio: null, nome: 'SP' } }))).toBe(
      'Top 10 de SP',
    )
    expect(tituloTop10(bloco())).toBe('Top 10 de São José dos Campos')
  })
})

describe('destinoDaVaga', () => {
  it('vaga preenchida vira destino no mapa; vazia ou sem coordenada, não', () => {
    const v = preenchida('mata_virgem', 1)
    expect(destinoDaVaga(v)).toEqual({
      uf: 'SP',
      municipio: 'São José dos Campos',
      pin: { lat: v.lat, lng: v.lng, hexId: v.hex_id },
    })
    expect(destinoDaVaga(vazia('premium', 4))).toBeNull()
    expect(destinoDaVaga(preenchida('premium', 1, { lat: null }))).toBeNull()
    expect(destinoDaVaga(preenchida('premium', 1, { nome_municipio: null }))).toBeNull()
  })
})

describe('mapaTop10', () => {
  it('só os preenchidos, na ordem MV1..MVn, P1..Pn, com segmento e chave', () => {
    const b = bloco()
    const m = mapaTop10(b)
    const esperados = SEGMENTOS_TOP10.flatMap((s) => b[s].vagas.filter((v) => !v.vazia).map((v) => v.hex_id))
    expect(m.ids).toEqual(esperados)
    const mv1 = m.porHex[b.mata_virgem.vagas[0].hex_id!]
    expect(mv1).toEqual({
      segmento: 'mata_virgem',
      posicao: 1,
      rotulo: 'MV1',
      rotuloSegmento: 'Mata Virgem',
      chaveRotulo: 'Residual medido',
      chaveValor: `${alunos(4155.39111328125)} alunos`,
    })
    const p1 = m.porHex[b.premium.vagas[0].hex_id!]
    expect(p1.rotulo).toBe('P1')
    expect(p1.chaveRotulo).toBe('População do Censo')
    expect(p1.chaveValor).toBe(`${num(38685.10797239564)} hab.`)
    expect(m.titulo).toBe('Top 10')
    expect(mapaTop10(bloco({ regra: { ...REGUA_BR_V1, vagas_por_segmento: 4 } })).titulo).toBe('Top 8')
  })

  it('a chave muda quando o Top 10 muda (gatilho do deck.gl)', () => {
    const b = bloco()
    const outra = bloco()
    outra.premium.vagas[3] = preenchida('premium', 4)
    expect(mapaTop10(b).chave).not.toBe(mapaTop10(outra).chave)
    expect(mapaTop10(b).chave).toBe(mapaTop10(bloco()).chave)
  })

  it('sem k, o mapa não tem o que marcar', () => {
    expect(mapaTop10(blocoSemK()).ids).toEqual([])
  })
})

describe('hexesComTop10 — as 10 regiões aparecem mesmo com o filtro ligado', () => {
  const todos = [{ id: 'a' }, { id: 'b' }, { id: 'c' }, { id: 'd' }]

  it('devolve o hexágono do Top 10 que o filtro tirou', () => {
    const filtrados = [todos[0], todos[1]]
    expect(hexesComTop10(filtrados, todos, ['b', 'd']).map((h) => h.id)).toEqual(['a', 'b', 'd'])
  })

  it('não duplica quem já estava', () => {
    const r = hexesComTop10(todos, todos, ['a', 'c'])
    expect(r.map((h) => h.id)).toEqual(['a', 'b', 'c', 'd'])
  })

  it('sem Top 10, ou sem nada a repor, devolve o MESMO array (memo estável)', () => {
    const filtrados = [todos[0]]
    expect(hexesComTop10(filtrados, todos, [])).toBe(filtrados)
    expect(hexesComTop10(filtrados, todos, ['a'])).toBe(filtrados)
    // id que nem está na base não inventa hexágono
    expect(hexesComTop10(filtrados, todos, ['zz'])).toBe(filtrados)
  })
})

describe('corTop10', () => {
  const cores = {
    mv: [10, 20, 30, 255] as [number, number, number, number],
    premium: [40, 50, 60, 255] as [number, number, number, number],
    fora: [70, 80, 90, 40] as [number, number, number, number],
  }
  const m = mapaTop10(bloco())

  it('Mata Virgem e Premium na cor do segmento, com o alpha de hexágono do tema', () => {
    expect(corTop10(m.porHex[m.ids[0]], cores, 115)).toEqual([10, 20, 30, 115])
    expect(corTop10(m.porHex[m.ids[3]], cores, 170)).toEqual([40, 50, 60, 170])
  })

  it('fora do Top 10: o esmaecido, com o alpha próprio', () => {
    expect(corTop10(null, cores, 115)).toEqual([70, 80, 90, 40])
    expect(corTop10(undefined, cores, 115)).toEqual([70, 80, 90, 40])
  })

  it('devolve cópia — quem pinta não muda a paleta', () => {
    const c = corTop10(null, cores, 115)
    c[3] = 0
    expect(cores.fora[3]).toBe(40)
  })
})

describe('legendaTop10', () => {
  it('Mata Virgem / Premium / fora do Top 10, por token de tema', () => {
    expect(legendaTop10(bloco())).toEqual({
      titulo: 'Top 10 por hexágono',
      itens: [
        { nome: 'Mata Virgem', cor: TOKEN_COR_TOP10.mata_virgem },
        { nome: 'Premium', cor: TOKEN_COR_TOP10.premium },
      ],
      fora: { nome: 'fora do Top 10', cor: TOKEN_COR_TOP10.fora },
    })
    expect(TOKEN_COR_TOP10).toEqual({
      mata_virgem: 'var(--top10-mv)',
      premium: 'var(--top10-premium)',
      fora: 'var(--top10-fora)',
    })
  })

  it('sem nada calculado, a legenda diz "Top 10 indisponível" — não "fora do Top 10"', () => {
    /* Sem o carimbo k o mapa da camada 5 fica todo esmaecido: com a legenda de sempre isso se
       leria como "nenhuma região passou na régua", e não como "recomendação suspensa". */
    expect(legendaTop10(blocoSemK())).toEqual({
      titulo: 'Top 10 indisponível',
      itens: [],
      fora: { nome: 'recomendação suspensa', cor: TOKEN_COR_TOP10.fora },
    })
  })
})

describe('textoLeituraVazia — estado vazio das camadas de leitura (1 a 4)', () => {
  it('sem linguagem de funil nem "escolha outro município"', () => {
    const municipio = textoLeituraVazia('municipio', bloco())
    expect(municipio).toBe(
      'Nenhuma região aparece nesta leitura. O Top 10, na camada 5, lê o município inteiro com régua própria.',
    )
    const uf = textoLeituraVazia('uf', bloco())
    expect(uf).toBe(
      'Nenhuma cidade aparece nesta leitura. O Top 10, na camada 5, lê o estado inteiro com régua própria.',
    )
    for (const t of [municipio, uf]) {
      expect(t).not.toMatch(/passou|filtro|outro município|Camada anterior/)
    }
  })

  it('sem nível conhecido, fala do município; o total sai da régua', () => {
    expect(textoLeituraVazia(undefined, bloco())).toContain('lê o município inteiro')
    expect(textoLeituraVazia('uf', bloco({ regra: { ...REGUA_BR_V1, vagas_por_segmento: 4 } }))).toContain(
      'O Top 8, na camada 5',
    )
  })
})

describe('versão da régua — rótulo de negócio, não o nome do arquivo', () => {
  it('"2026-10_v1" vira "outubro de 2026, versão 1"', () => {
    expect(rotuloDaVersaoDaRegua('2026-10_v1')).toBe('outubro de 2026, versão 1')
    expect(rotuloDaVersaoDaRegua('2027-03_v12')).toBe('março de 2027, versão 12')
    expect(textoVersaoDaRegua(REGUA_BR_V1)).toBe('Régua de outubro de 2026, versão 1')
  })

  it('fora do padrão `<ano>-<mês>_v<n>`, a versão crua — sem inventar data', () => {
    expect(rotuloDaVersaoDaRegua('2026-13_v1')).toBeNull()
    expect(rotuloDaVersaoDaRegua('piloto')).toBeNull()
    expect(textoVersaoDaRegua({ versao: 'piloto' })).toBe('Régua piloto')
  })

  it('a versão crua e a decisão ficam só no detalhe técnico', () => {
    expect(referenciaTecnicaDaRegua(REGUA_BR_V1)).toBe('2026-10_v1 · DEC-077')
    expect(textoVersaoDaRegua(REGUA_BR_V1)).not.toContain('DEC')
    expect(textoVersaoDaRegua(REGUA_BR_V1)).not.toContain('2026-10_v1')
  })
})

describe('corDaEtiquetaTop10 — o chip do segmento na metodologia', () => {
  it('Mata Virgem e Premium na cor do token que pinta o mapa; o resto, nada', () => {
    expect(corDaEtiquetaTop10('Mata Virgem')).toBe(TOKEN_COR_TOP10.mata_virgem)
    expect(corDaEtiquetaTop10('Premium')).toBe(TOKEN_COR_TOP10.premium)
    expect(corDaEtiquetaTop10('Vaga vazia')).toBeNull()
    expect(corDaEtiquetaTop10('Livre')).toBeNull()
  })
})

describe('leiturasDoRecorte — as camadas 1 a 4 de Oportunidades', () => {
  const passo = (n: number, itens: number): Passo =>
    ({
      n,
      titulo: `Camada ${n}`,
      itens: Array.from({ length: itens }, (_, i) => ({ rank: i + 1, hex_id: `h${n}-${i}`, titulo: `${n}-${i}` })),
    }) as unknown as Passo

  it('a camada 5 (o Top 10) não se repete: ela é o hero da tela', () => {
    const r = leiturasDoRecorte([passo(1, 3), passo(2, 3), passo(3, 3), passo(4, 3), passo(5, 10)])
    expect(r.map((x) => x.passo.n)).toEqual([1, 2, 3, 4])
  })

  it('o topo de cada leitura, na ordem do servidor, cortado em 5', () => {
    expect(TOP_POR_LEITURA).toBe(5)
    const [l1, l2] = leiturasDoRecorte([passo(1, 8), passo(2, 2)])
    expect(l1.itens.map((it) => it.rank)).toEqual([1, 2, 3, 4, 5])
    expect(l2.itens.map((it) => it.rank)).toEqual([1, 2])
  })
})

describe('textosTop10 — tabela por país, nunca ramo', () => {
  it('o Brasil tem os textos do Top 10, todos preenchidos', () => {
    const t = textosTop10('BR')
    expect(t).not.toBeNull()
    for (const v of Object.values(t!)) expect(v.trim()).not.toBe('')
    expect(t!.filtroFaixaRotulo).toBe('FAIXA M1')
  })

  it('o corte das camadas na metodologia é régua de leitura (1 a 4) e régua do Top 10 (5)', () => {
    const t = textosTop10('BR')!
    expect(t.metodologiaCorteLeitura).toBe('régua da leitura')
    expect(t.metodologiaCorteTop10).toBe('entra no Top 10')
    expect(t.metodologiaCorteLeitura).not.toContain('passa no corte')
  })

  it('país sem régua (Argentina) ou desconhecido devolve null: o texto legado vale', () => {
    expect(textosTop10('AR')).toBeNull()
    expect(textosTop10('XX')).toBeNull()
    expect(textosTop10('')).toBeNull()
  })

  it('chave herdada do protótipo não vira texto', () => {
    expect(textosTop10('constructor')).toBeNull()
    expect(textosTop10('toString')).toBeNull()
  })

  it('sem argumento, lê o país do perfil da instância (Brasil no default compilado)', () => {
    expect(textosTop10()).toBe(TEXTOS_TOP10_POR_PAIS.BR)
  })

  it('a tabela é congelada', () => {
    expect(Object.isFrozen(TEXTOS_TOP10_POR_PAIS)).toBe(true)
    expect(Object.isFrozen(TEXTOS_TOP10_POR_PAIS.BR)).toBe(true)
  })
})
