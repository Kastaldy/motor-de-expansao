import { describe, expect, it } from 'vitest'

import {
  avisosDaContagem,
  celulaVariacao,
  diaMes,
  janela,
  janelaDoCadastro,
  legendaDoEntorno,
  motivoSemCadastro,
  rodapeCrescimento,
  rotuloCadastro,
  rotuloContagem,
  temVariacao,
  textoJanela,
} from './crescimento-concorrencia'
import type { RedeContagemSemanal, RedeCrescimento, RedeMovimentoPeriodo } from './types'

// Datas de propósito DIFERENTES das do pacote real (02/08 a 06/09, Wellhub 31/08 a 12/09): se
// alguma voltar a ser escrita à mão no código, o teste mostra o texto com a data errada.
const PERIODOS: RedeMovimentoPeriodo[] = [
  { fonte: 'cadastro', confianca: 'alta', de: '2026-08-09', ate: '2026-09-13', n: 10 },
  { fonte: 'cadastro', confianca: 'cautela', de: '2026-06-01', ate: '2026-08-09', n: 5 },
  { fonte: 'em_breve', confianca: 'alta', de: '2026-07-01', ate: '2026-09-13', n: 2 },
  { fonte: 'wellhub', confianca: 'alta', de: '2026-09-01', ate: '2026-09-20', n: 7 },
]

function card(over: Partial<RedeCrescimento> = {}, contagem: Partial<RedeContagemSemanal> = {}): RedeCrescimento {
  return {
    disponivel: true,
    tem_cadastro: true,
    periodos: PERIODOS,
    data_contagem: '2026-11-01',
    contagem_origem: 'semanal',
    contagem: {
      erro: null,
      data: '2026-11-01',
      data_anterior: '2026-10-25',
      execucao_mais_recente: '2026-11-01',
      confirmada: false,
      quedas_confirmadas: [],
      queda_total_confirmada_pct: null,
      recusadas: [],
      ...contagem,
    },
    redes: [],
    redes_mapeadas: 98,
    unidades_mapeadas: 4436,
    variacao_total: 5,
    agregadores: [],
    ...over,
  }
}

const selfitCaiu = { rede: 'selfit', antes: 233, agora: 119, coleta_defasada: true }

describe('datas tiradas do dado', () => {
  it('formata dia/mês e recusa o que não é data', () => {
    expect(diaMes('2026-11-01')).toBe('01/11')
    expect(diaMes(null)).toBe('—')
    expect(diaMes('ontem')).toBe('—')
  })

  it('a janela de uma fonte junta as fotos dela', () => {
    expect(textoJanela(janela(PERIODOS, 'cadastro', 'alta'))).toBe('09/08 a 13/09')
    expect(textoJanela(janela(PERIODOS, 'cadastro'))).toBe('01/06 a 13/09')
    expect(textoJanela(janela(PERIODOS, 'wellhub'))).toBe('01/09 a 20/09')
    expect(janela(PERIODOS, 'totalpass')).toBeNull()
    expect(textoJanela({ de: null, ate: '2026-09-13' })).toBe('até 13/09')
  })

  it('o cabeçalho de cada grupo de colunas diz a data da sua fonte', () => {
    expect(rotuloContagem(card())).toBe('Contagem de 01/11')
    expect(rotuloCadastro(card(), false)).toBe('Cadastro de 09/08 a 13/09')
    // com o botão ligado, o grupo passa a somar também a foto não validada
    expect(rotuloCadastro(card(), true)).toBe('Cadastro de 01/06 a 13/09')
    expect(textoJanela(janelaDoCadastro(PERIODOS, true))).toBe('01/06 a 13/09')
  })
})

describe('coluna de variação', () => {
  it('só existe com duas contagens semanais aceitas', () => {
    expect(temVariacao(card())).toBe(true)
    expect(temVariacao(card({}, { data_anterior: null }))).toBe(false)
    expect(temVariacao(card({ contagem_origem: 'pacote' }))).toBe(false)
  })

  it('escreve o sinal e separa cobertura nova de crescimento', () => {
    expect(celulaVariacao({ variacao: 3, variacao_status: 'variou' }, '2026-10-25')).toEqual({ texto: '+3', tom: 'mais' })
    const queda = celulaVariacao({ variacao: -2, variacao_status: 'variou' }, '2026-10-25')
    expect(queda.tom).toBe('menos')
    expect(queda.texto).toMatch(/^[-−]2$/)
    expect(celulaVariacao({ variacao: 0, variacao_status: 'estavel' }, '2026-10-25')).toEqual({ texto: '0', tom: 'zero' })
    // `novo` é a rede que entrou na cobertura do coletor: nunca "+12"
    const nova = celulaVariacao({ variacao: null, variacao_status: 'novo' }, '2026-10-25')
    expect(nova.texto).toBe('nova')
    expect(nova.titulo).toBe('Rede que entrou na contagem do coletor desde 25/10: é cobertura nova, não abertura.')
    expect(celulaVariacao({ variacao: null, variacao_status: null }, null)).toEqual({ texto: '—', tom: 'vazio' })
  })
})

describe('linha sem leitura de cadastro', () => {
  it('diz por que a Smart Fit e a rede nova mostram "—"', () => {
    expect(motivoSemCadastro({ rede: 'smart_fit', sem_cadastro: 'teto_coletor' })).toBe(
      'No cadastro de setembro, a Smart Fit estava travada no teto de 1.000 unidades do coletor; ' +
        'as aberturas e os fechamentos dela ficaram de fora.',
    )
    expect(motivoSemCadastro({ rede: 'nova', sem_cadastro: 'fora_da_cobertura' })).toBe(
      'O coletor ainda não cobria esta rede no período do cadastro.',
    )
    expect(motivoSemCadastro({ rede: 'selfit', sem_cadastro: null })).toBeNull()
  })
})

describe('avisos da contagem', () => {
  it('semana normal não avisa nada', () => {
    expect(avisosDaContagem(card())).toEqual([])
  })

  it('a contagem mais recente recusada diz qual rede caiu e em que semana o card ficou', () => {
    const avisos = avisosDaContagem(
      card({}, { execucao_mais_recente: '2026-11-08', recusadas: [{ execucao: '2026-11-08', motivo: 'queda', redes: [selfitCaiu], queda_total_pct: null }] }),
    )
    expect(avisos).toEqual([
      {
        tom: 'alerta',
        texto:
          'A contagem de 08/11 ficou de fora: a Selfit caiu de 233 para 119 unidades, sinal de coleta incompleta. ' +
          'O card segue na de 01/11, a última aceita.',
      },
    ])
  })

  it('recusa pelo total e por duplicidade têm texto próprio', () => {
    const pelo_total = avisosDaContagem(
      card({}, { recusadas: [{ execucao: '2026-11-08', motivo: 'queda', redes: [], queda_total_pct: 12.5 }] }),
    )
    expect(pelo_total[0].texto).toContain('o total caiu 12,5%, sinal de coleta incompleta')
    const duplicada = avisosDaContagem(
      card({}, { recusadas: [{ execucao: '2026-11-08', motivo: 'duplicada', redes: [], queda_total_pct: null }] }),
    )
    expect(duplicada[0].texto).toBe(
      'A contagem de 08/11 ficou de fora: ela aparece duas vezes no histórico. O card segue na de 01/11, a última aceita.',
    )
  })

  it('várias recusadas seguidas: lista as datas e explica a última', () => {
    const avisos = avisosDaContagem(
      card({}, {
        recusadas: [
          { execucao: '2026-11-08', motivo: 'queda', redes: [selfitCaiu], queda_total_pct: null },
          {
            execucao: '2026-11-15',
            motivo: 'queda',
            redes: [selfitCaiu, { rede: 'panobianco', antes: 150, agora: 60 }],
            queda_total_pct: null,
          },
        ],
      }),
    )
    expect(avisos[0].texto).toBe(
      'As contagens de 08/11 e 15/11 ficaram de fora (na de 15/11, a Selfit caiu de 233 para 119 unidades ' +
        'e a Panobianco, de 150 para 60, sinal de coleta incompleta). O card segue na de 01/11, a última aceita.',
    )
  })

  it('variação que cobre mais de uma semana diz por quê', () => {
    const avisos = avisosDaContagem(
      card({}, {
        data_anterior: '2026-10-18',
        recusadas: [{ execucao: '2026-10-25', motivo: 'queda', redes: [selfitCaiu], queda_total_pct: null }],
      }),
    )
    expect(avisos).toEqual([{ tom: 'info', texto: 'A variação compara com 18/10 porque a contagem de 25/10 ficou de fora.' }])
  })

  it('queda aceita por confirmação é nomeada, e o aviso de intervalo não se repete', () => {
    const avisos = avisosDaContagem(
      card({}, {
        data: '2026-10-18',
        data_anterior: '2026-10-04',
        confirmada: true,
        quedas_confirmadas: [{ rede: 'pequena', antes: 6, agora: 4 }],
        recusadas: [{ execucao: '2026-10-11', motivo: 'queda', redes: [{ rede: 'pequena', antes: 6, agora: 4 }], queda_total_pct: null }],
      }),
    )
    expect(avisos).toEqual([
      {
        tom: 'info',
        texto:
          'A queda da Pequena (de 6 para 4 unidades) apareceu em duas contagens seguidas e foi aceita como real; ' +
          'por isso a variação compara com 04/10.',
      },
    ])
  })

  it('sem histórico semanal, diz de que data são as unidades', () => {
    const ausente = avisosDaContagem(card({ contagem_origem: 'pacote', data_contagem: '2026-09-06' }, { erro: 'ausente', data: null }))
    expect(ausente).toEqual([
      {
        tom: 'alerta',
        texto:
          'O histórico semanal de contagem não está neste ambiente: as unidades são da contagem de 06/09, ' +
          'e a variação fica de fora.',
      },
    ])
    const ilegivel = avisosDaContagem(card({ contagem_origem: 'pacote', data_contagem: '2026-09-06' }, { erro: 'ilegivel', data: null }))
    expect(ilegivel[0].texto.startsWith('O histórico semanal de contagem está ilegível neste ambiente')).toBe(true)
  })

  it('com uma contagem aceita só, avisa que a variação vem depois', () => {
    expect(avisosDaContagem(card({}, { data_anterior: null }))).toEqual([
      { tom: 'info', texto: 'A variação aparece a partir da segunda contagem semanal aceita.' },
    ])
  })
})

describe('rodapé', () => {
  it('cada fonte com a sua data, todas tiradas do payload', () => {
    const t = rodapeCrescimento(card(), false)
    expect(t).toContain('Mercado mapeado: 4.436 unidades em 98 redes (+5 desde 25/10, entre as redes das duas contagens).')
    expect(t).toContain('Unidades: contagem semanal do coletor de 01/11, a mesma do relatório de domingo no Telegram')
    expect(t).toContain('fotos do cadastro de 09/08 a 13/09, validadas contra a contagem oficial (a foto de 01/06 a 09/08 entra só pelo botão)')
    expect(t).toContain('"Em breve": anúncios que ainda não tinham inaugurado em 13/09.')
    expect(t).toContain('Estúdios boutique ficam fora (DEC-056).')
    // nenhuma das datas do pacote real escrita à mão
    for (const literal of ['02/08', '06/09', '28/05', '31/08', '12/09']) expect(t).not.toContain(literal)
    // a afirmação de setembro sobre a Smart Fit só aparece quando a linha dela está na tabela
    expect(t).not.toContain('Smart Fit')
  })

  it('a nota da Smart Fit vale para o cadastro, não para a contagem', () => {
    const t = rodapeCrescimento(card({ redes: [{ rede: 'smart_fit', aberturas: 0, aberturas_conferidas: 0, fechamentos: 0, fechamentos_conferidos: 0, em_breve: 0, saldo: 0, unidades: 1061, sem_cadastro: 'teto_coletor' }] }), false)
    expect(t).toContain('A Smart Fit fica fora de aberturas e fechamentos: no cadastro, ela estava travada no teto de 1.000 unidades do coletor.')
    expect(t).not.toContain('PISO')
  })

  it('com o botão ligado, diz que a foto não validada entrou na soma', () => {
    expect(rodapeCrescimento(card(), true)).toContain('mais a foto de 01/06 a 09/08, que não foi validada')
  })

  it('sem histórico semanal, as unidades dizem que são do pacote', () => {
    const t = rodapeCrescimento(card({ contagem_origem: 'pacote', data_contagem: '2026-09-06', variacao_total: null }, { data: null, data_anterior: null }), false)
    expect(t).toContain('Unidades: contagem oficial de 06/09, do pacote de setembro.')
    expect(t).toContain('Mercado mapeado: 4.436 unidades em 98 redes.')
  })

  it('sem o pacote, o rodapé não fala de cadastro', () => {
    const t = rodapeCrescimento(card({ tem_cadastro: false, periodos: [] }), false)
    expect(t).not.toContain('cadastro')
    expect(t).toContain('Unidades: contagem semanal do coletor de 01/11')
  })
})

describe('ficha da unidade', () => {
  it('a legenda diz até quando vai cada foto do pacote', () => {
    expect(legendaDoEntorno(PERIODOS)).toBe('Fotos do cadastro até 13/09 e do Wellhub até 20/09.')
    expect(legendaDoEntorno([])).toBe('')
  })
})
