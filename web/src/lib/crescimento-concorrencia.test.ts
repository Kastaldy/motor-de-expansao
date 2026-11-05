import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  AVISO_NACIONAL,
  avisosDaContagem,
  celulaCadastro,
  celulaVariacao,
  comArtigo,
  diaMes,
  diasEntre,
  hojeLocal,
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
import type { RedeContagemSemanal, RedeCrescimento, RedeCrescimentoRede, RedeMovimentoPeriodo } from './types'

// Datas de propósito DIFERENTES das do pacote real (02/08 a 06/09, Wellhub 31/08 a 12/09): se
// alguma voltar a ser escrita à mão no código, o teste mostra o texto com a data errada.
const PERIODOS: RedeMovimentoPeriodo[] = [
  { fonte: 'cadastro', confianca: 'alta', de: '2026-08-09', ate: '2026-09-13', n: 10 },
  { fonte: 'cadastro', confianca: 'cautela', de: '2026-06-01', ate: '2026-08-09', n: 5 },
  { fonte: 'em_breve', confianca: 'alta', de: '2026-07-01', ate: '2026-09-13', n: 2 },
  { fonte: 'wellhub', confianca: 'alta', de: '2026-09-01', ate: '2026-09-20', n: 7 },
]

const HOJE = '2026-11-03'

function contagem(over: Partial<RedeContagemSemanal> = {}): RedeContagemSemanal {
  return {
    erro: null,
    data: '2026-11-01',
    data_anterior: '2026-10-25',
    execucao_mais_recente: '2026-11-01',
    linhas_sem_data: 0,
    recusadas: [],
    seguradas: [],
    confirmadas: [],
    nao_recoletadas: [],
    ausentes: [],
    removidas: [],
    total_confirmado: false,
    ...over,
  }
}

function card(over: Partial<RedeCrescimento> = {}, c: Partial<RedeContagemSemanal> = {}): RedeCrescimento {
  return {
    disponivel: true,
    tem_cadastro: true,
    periodos: PERIODOS,
    data_contagem: '2026-11-01',
    contagem_origem: 'semanal',
    contagem: contagem(c),
    redes: [],
    redes_mapeadas: 98,
    unidades_mapeadas: 4436,
    variacao_total: 5,
    agregadores: [],
    ...over,
  }
}

function linha(over: Partial<RedeCrescimentoRede> = {}): RedeCrescimentoRede {
  return {
    rede: 'selfit',
    aberturas: 2,
    aberturas_conferidas: 2,
    fechamentos: 1,
    fechamentos_conferidos: 1,
    em_breve: 0,
    saldo: 1,
    unidades: 233,
    ...over,
  }
}

const queda = { rede: 'selfit', antes: 233, agora: 119, direcao: 'queda' as const, desde: '2026-11-01' }

describe('datas tiradas do dado', () => {
  it('formata dia/mês, conta dias e recusa o que não é data', () => {
    expect(diaMes('2026-11-01')).toBe('01/11')
    expect(diaMes(null)).toBe('—')
    expect(diaMes('ontem')).toBe('—')
    expect(diasEntre('2026-10-25', '2026-11-01')).toBe(7)
    expect(diasEntre('2026-12-28', '2027-01-04')).toBe(7)
    expect(diasEntre(null, '2026-11-01')).toBeNull()
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
  it('só existe com duas contagens semanais', () => {
    expect(temVariacao(card())).toBe(true)
    expect(temVariacao(card({}, { data_anterior: null }))).toBe(false)
    expect(temVariacao(card({ contagem_origem: 'pacote' }))).toBe(false)
  })

  it('escreve o sinal e separa cobertura nova de crescimento', () => {
    expect(celulaVariacao({ variacao: 3, variacao_status: 'variou' }, '2026-10-25')).toEqual({ texto: '+3', tom: 'mais' })
    const menos = celulaVariacao({ variacao: -2, variacao_status: 'variou' }, '2026-10-25')
    expect(menos.tom).toBe('menos')
    expect(menos.texto).toMatch(/^[-−]2$/)
    expect(celulaVariacao({ variacao: 0, variacao_status: 'estavel' }, '2026-10-25')).toEqual({ texto: '0', tom: 'zero' })
    const nova = celulaVariacao({ variacao: null, variacao_status: 'novo' }, '2026-10-25')
    expect([nova.texto, nova.tom]).toEqual(['nova', 'info'])
    expect(nova.titulo).toBe('Rede que entrou na contagem do coletor desde 25/10: é cobertura nova, não abertura.')
  })

  it('o que ficou na contagem anterior aparece ESCRITO na célula, não só na dica', () => {
    const segurada = celulaVariacao({ variacao: null, variacao_status: 'segurada', lido: 119 }, '2026-10-25')
    expect([segurada.texto, segurada.tom]).toEqual(['segurada', 'info'])
    expect(segurada.titulo).toContain('O coletor leu 119 unidades')
    expect(celulaVariacao({ variacao: null, variacao_status: 'nao_recoletada' }, null).texto).toBe('sem coleta')
    expect(celulaVariacao({ variacao: null, variacao_status: 'ausente' }, null).texto).toBe('ausente')
    const confirmada = celulaVariacao({ variacao: -70, variacao_status: 'confirmada' }, '2026-10-25')
    expect(confirmada.tom).toBe('menos')
    expect(confirmada.titulo).toContain('se manteve numa coleta mais nova')
    expect(celulaVariacao({ variacao: null, variacao_status: null }, null)).toEqual({ texto: '—', tom: 'vazio' })
  })
})

describe('células do cadastro', () => {
  it('a Smart Fit mostra "—" em aberturas, fechamentos e saldo, e mantém o "Em breve"', () => {
    const smart = linha({ rede: 'smart_fit', aberturas: 0, fechamentos: 0, saldo: 0, em_breve: 3, sem_cadastro: 'teto_coletor' })
    for (const coluna of ['aberturas', 'fechamentos', 'saldo'] as const) {
      const c = celulaCadastro(smart, coluna)
      expect(c.tipo).toBe('sem_leitura')
      expect(c.titulo).toContain('travada no teto de 1.000 unidades do coletor')
    }
    expect(celulaCadastro(smart, 'em_breve')).toEqual({ tipo: 'numero', valor: 3 })
  })

  it('a rede fora da cobertura perde o número até no "Em breve"; a rede comum mostra 0', () => {
    const nova = linha({ rede: 'nova', aberturas: 0, fechamentos: 0, saldo: 0, sem_cadastro: 'fora_da_cobertura' })
    expect(celulaCadastro(nova, 'em_breve').tipo).toBe('sem_leitura')
    const parada = linha({ aberturas: 0, fechamentos: 0, saldo: 0 })
    expect(celulaCadastro(parada, 'aberturas')).toEqual({ tipo: 'zero', valor: 0 })
    expect(celulaCadastro(linha(), 'aberturas')).toEqual({ tipo: 'numero', valor: 2 })
  })

  it('diz por que a linha mostra "—"', () => {
    expect(motivoSemCadastro({ rede: 'nova', sem_cadastro: 'fora_da_cobertura' })).toBe(
      'O coletor ainda não cobria esta rede no período do cadastro.',
    )
    expect(motivoSemCadastro({ rede: 'selfit', sem_cadastro: null })).toBeNull()
  })
})

describe('avisos da contagem', () => {
  it('semana normal não avisa nada', () => {
    expect(avisosDaContagem(card(), HOJE)).toEqual([])
  })

  it('a rede segurada diz quem caiu, de quanto para quanto, e que ela ficou na contagem anterior', () => {
    expect(avisosDaContagem(card({}, { seguradas: [queda] }), HOJE)).toEqual([
      {
        tom: 'alerta',
        texto:
          'A Selfit caiu de 233 para 119 unidades na contagem de 01/11, sinal de coleta incompleta: ' +
          'ela fica com a última contagem boa até a próxima coleta confirmar.',
      },
    ])
  })

  it('o salto para cima não é chamado de coleta incompleta', () => {
    const subida = { rede: 'bluefit', antes: 100, agora: 200, direcao: 'subida' as const, desde: '2026-10-25' }
    const [aviso] = avisosDaContagem(card({}, { seguradas: [subida] }), HOJE)
    expect(aviso.texto).toBe(
      'A Bluefit subiu de 100 para 200 unidades na contagem de 01/11 (segurada desde 25/10), um salto que ' +
        'costuma ser ajuste do coletor, e não abertura: ela fica com a última contagem boa até a próxima coleta confirmar.',
    )
  })

  it('várias redes seguradas são listadas com o salto de cada uma', () => {
    const [aviso] = avisosDaContagem(
      card({}, { seguradas: [queda, { rede: 'panobianco', antes: 150, agora: 60, direcao: 'queda', desde: '2026-11-01' }] }),
      HOJE,
    )
    expect(aviso.texto).toBe(
      '2 redes tiveram salto brusco na contagem de 01/11 e cada uma fica com a última contagem boa até a próxima ' +
        'coleta confirmar. São elas: Selfit (de 233 para 119) e Panobianco (de 150 para 60).',
    )
  })

  it('o salto confirmado diz que se manteve numa coleta mais nova', () => {
    const avisos = avisosDaContagem(
      card({}, { confirmadas: [{ rede: 'pequena', antes: 6, agora: 4, direcao: 'queda', desde: '2026-10-25' }] }),
      HOJE,
    )
    expect(avisos).toEqual([
      { tom: 'info', texto: 'A queda da Pequena (de 6 para 4 unidades) se manteve numa coleta mais nova e entrou nesta contagem.' },
    ])
  })

  it('as redes não recoletadas viram aviso com a contagem e os nomes', () => {
    const uma = avisosDaContagem(card({}, { nao_recoletadas: ['selfit'] }), HOJE)
    expect(uma[0].texto).toBe('A Selfit não foi recoletada nesta semana: fica com a última contagem, sem variação.')
    const varias = avisosDaContagem(card({}, { nao_recoletadas: ['a', 'b', 'c', 'd', 'e'] }), HOJE)
    expect(varias[0].texto).toBe(
      '5 redes não foram recoletadas nesta semana e ficam com a última contagem, sem variação: A, B, C e mais 2.',
    )
  })

  it('rede ausente e rede removida', () => {
    const avisos = avisosDaContagem(card({}, { ausentes: ['extinta'], removidas: ['velha', 'outra'] }), HOJE)
    expect(avisos.map((a) => a.texto)).toEqual([
      'A Extinta não veio na contagem de 01/11: fica com a última contagem por uma semana.',
      'Velha e Outra saíram da contagem do coletor (não vieram duas semanas seguidas).',
    ])
  })

  it('execução inteira de fora: pelo total ou por duplicidade, depois e antes da contagem atual', () => {
    const total = avisosDaContagem(card({}, { recusadas: [{ execucao: '2026-11-08', motivo: 'total', queda_total_pct: 12.5 }] }), HOJE)
    expect(total[0].texto).toBe(
      'A contagem de 08/11 ficou de fora: a soma das redes recoletadas caiu 12,5%, sinal de coleta incompleta. ' +
        'O card segue na de 01/11.',
    )
    const duplicada = avisosDaContagem(card({}, { recusadas: [{ execucao: '2026-11-08', motivo: 'duplicada', queda_total_pct: null }] }), HOJE)
    expect(duplicada[0].texto).toBe(
      'A contagem de 08/11 ficou de fora: ela aparece duas vezes no histórico. O card segue na de 01/11.',
    )
    const entre = avisosDaContagem(
      card({}, { data_anterior: '2026-10-18', recusadas: [{ execucao: '2026-10-25', motivo: 'total', queda_total_pct: 11 }] }),
      HOJE,
    )
    expect(entre).toEqual([{ tom: 'info', texto: 'A variação compara com 18/10 porque a contagem de 25/10 ficou de fora.' }])
  })

  it('contagem velha vira alerta: o histórico pode ter parado de chegar', () => {
    const avisos = avisosDaContagem(card(), '2026-11-20')
    expect(avisos[0]).toEqual({
      tom: 'alerta',
      texto: 'A execução mais recente do histórico semanal é de 01/11/2026, de 19 dias atrás: o histórico pode ter parado de chegar ao site.',
    })
    expect(avisosDaContagem(card(), '2026-11-08')).toEqual([])
  })

  it('sem histórico semanal, diz de que data são as unidades', () => {
    const ausente = avisosDaContagem(card({ contagem_origem: 'pacote', data_contagem: '2026-09-06' }, { erro: 'ausente', data: null }), HOJE)
    expect(ausente).toEqual([
      {
        tom: 'alerta',
        texto:
          'O histórico semanal de contagem não está neste ambiente: as unidades são da contagem de 06/09, ' +
          'e a variação fica de fora.',
      },
    ])
    const ilegivel = avisosDaContagem(card({ contagem_origem: 'pacote', data_contagem: '2026-09-06' }, { erro: 'ilegivel', data: null }), HOJE)
    expect(ilegivel[0].texto.startsWith('O histórico semanal de contagem está ilegível neste ambiente')).toBe(true)
  })

  it('sem o pacote, diz que o cadastro não está no ambiente', () => {
    expect(avisosDaContagem(card({ tem_cadastro: false, periodos: [] }), HOJE)).toEqual([
      {
        tom: 'info',
        texto: 'O cadastro de aberturas e fechamentos (pacote de setembro) não está neste ambiente: o card mostra só a contagem semanal.',
      },
    ])
  })

  it('uma contagem só, e linhas sem data', () => {
    expect(avisosDaContagem(card({}, { data_anterior: null }), HOJE)).toEqual([
      { tom: 'info', texto: 'A variação aparece a partir da segunda contagem semanal.' },
    ])
    expect(avisosDaContagem(card({}, { linhas_sem_data: 3 }), HOJE)[0].texto).toBe(
      '3 linhas do histórico vieram fora do formato (sem data ou com campos a mais) e ficaram de fora.',
    )
  })
})

describe('rodapé', () => {
  it('cada fonte com a sua data, todas tiradas do payload', () => {
    const t = rodapeCrescimento(card(), false)
    expect(t).toContain('Mercado mapeado: 4.436 unidades em 98 redes (+5 desde 25/10, entre as redes das duas contagens).')
    expect(t).toContain('Unidades: contagem semanal do coletor de 01/11, a mesma do relatório de domingo no Telegram')
    expect(t).toContain('já inclui as unidades anunciadas ("Em breve")')
    expect(t).toContain('A variação mistura aberturas, anúncios e ajustes do coletor.')
    expect(t).toContain('fotos do cadastro de 09/08 a 13/09, validadas contra a contagem oficial (a foto de 01/06 a 09/08 entra só pelo botão)')
    expect(t).toContain('"Em breve": anúncios que ainda não tinham inaugurado em 13/09.')
    expect(t).toContain('Estúdios boutique ficam fora (DEC-056).')
    // nenhuma das datas do pacote real escrita à mão
    for (const literal of ['02/08', '06/09', '28/05', '31/08', '12/09']) expect(t).not.toContain(literal)
    // a nota de setembro sobre a Smart Fit só aparece quando a linha dela está na tabela
    expect(t).not.toContain('Smart Fit')
  })

  it('a nota da Smart Fit vale para o cadastro, não para a contagem', () => {
    const t = rodapeCrescimento(card({ redes: [linha({ rede: 'smart_fit', unidades: 1061, sem_cadastro: 'teto_coletor' })] }), false)
    expect(t).toContain('A Smart Fit fica fora de aberturas e fechamentos: no cadastro, ela estava travada no teto de 1.000 unidades do coletor.')
    expect(t).not.toContain('PISO')
  })

  it('"nova" ganha explicação visível quando aparece na tabela', () => {
    expect(rodapeCrescimento(card({ redes: [linha({ variacao_status: 'novo' })] }), false)).toContain(
      '"nova": rede que o coletor passou a contar; não é abertura.',
    )
  })

  it('com o botão ligado, diz que a foto não validada entrou na soma', () => {
    expect(rodapeCrescimento(card(), true)).toContain('mais a foto de 01/06 a 09/08, que não foi validada')
  })

  it('sem histórico semanal, as unidades dizem que são do pacote', () => {
    const t = rodapeCrescimento(card({ contagem_origem: 'pacote', data_contagem: '2026-09-06', variacao_total: null }, { data: null, data_anterior: null }), false)
    expect(t).toContain('Unidades: contagem oficial de 06/09, do pacote de setembro.')
    expect(t).toContain('Mercado mapeado: 4.436 unidades em 98 redes.')
  })
})

describe('ficha da unidade', () => {
  it('a legenda diz até quando vai cada foto do pacote', () => {
    expect(legendaDoEntorno(PERIODOS)).toBe('Fotos do cadastro até 13/09 e do Wellhub até 20/09.')
    expect(legendaDoEntorno([])).toBe('')
  })
})

// --------------------------------------------------------------------------- //
// O FONTE da tela usa as funções testadas acima (o vitest roda sem DOM)
// --------------------------------------------------------------------------- //
const inteligencia = readFileSync(fileURLToPath(new URL('../components/exec/Inteligencia.tsx', import.meta.url)), 'utf-8')
const ficha = readFileSync(fileURLToPath(new URL('../components/exec/FichaInteligencia.tsx', import.meta.url)), 'utf-8')

/** O corpo de uma função do componente, sem os comentários (que podem citar datas). */
function corpo(fonte: string, inicio: string, fim: string): string {
  const i = fonte.indexOf(inicio)
  const j = fonte.indexOf(fim, i)
  expect(i).toBeGreaterThan(-1)
  expect(j).toBeGreaterThan(i)
  return fonte
    .slice(i, j)
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, '')
    .replace(/\/\/.*$/gm, '')
}

describe('o card na tela', () => {
  const fonteCard = corpo(inteligencia, 'function MovimentacaoConcorrencia(', '/* ================================ TABELA')

  it('nenhuma data escrita à mão no código do card', () => {
    expect(fonteCard).not.toMatch(/\d{2}\/\d{2}/)
  })

  it('o aviso de card nacional, o cabeçalho datado e as células saem da lib', () => {
    expect(AVISO_NACIONAL).toBe('Visão nacional das redes concorrentes: este card não muda com os filtros do topo da página.')
    for (const uso of ['{AVISO_NACIONAL}', 'rotuloContagem(m)', 'rotuloCadastro(m, comCautela)', 'celulaCadastro(r, coluna)', 'celulaVariacao(r, dataAnterior)', 'rodapeCrescimento(m, comCautela)']) {
      expect(fonteCard).toContain(uso)
    }
    // A expressão EXATA: um `new Date().toLocaleDateString()` compilaria, passaria num regex frouxo e
    // desligaria o aviso de contagem velha (`diasEntre` só lê ISO). E `toISOString` daria o dia em UTC.
    expect(fonteCard).toContain('avisosDaContagem(m, hojeLocal())')
    expect(fonteCard).not.toContain('toISOString')
  })

  it('o cabeçalho de duas linhas associa cada grupo às suas colunas', () => {
    expect(fonteCard).not.toContain('aria-hidden')
    expect(fonteCard.match(/scope="colgroup"/g)?.length).toBe(2)
    // sem <colgroup>, o scope="colgroup" não liga o grupo às colunas; e cada linha tem cabeçalho
    expect(fonteCard.match(/<colgroup/g)?.length).toBe(3)
    expect(fonteCard).toContain('<th scope="row"')
  })

  it('a ficha tira as datas da movimentação do dado', () => {
    expect(ficha).toContain('legendaDoEntorno(mov.periodos)')
    expect(ficha).not.toContain('Foto não validada (28/05 a 02/08)')
  })
})

// --------------------------------------------------------------------------- //
// Revisão de 05/11 (2ª rodada): a idade do histórico, a execução sem coleta nova, plurais
// --------------------------------------------------------------------------- //
describe('avisos: a idade do histórico e a execução sem coleta nova', () => {
  it('o histórico que chegou e foi recusado não é "parou de chegar"', () => {
    const avisos = avisosDaContagem(
      card({}, { execucao_mais_recente: '2026-11-08', recusadas: [{ execucao: '2026-11-08', motivo: 'total', queda_total_pct: 14.9 }] }),
      '2026-11-12',
    )
    expect(avisos).toEqual([
      {
        tom: 'alerta',
        texto: 'Nenhuma contagem nova entra no card desde 01/11/2026, há 11 dias: o histórico chega, mas as execuções seguintes ficaram de fora.',
      },
      {
        tom: 'alerta',
        texto: 'A contagem de 08/11 ficou de fora: a soma das redes recoletadas caiu 14,9%, sinal de coleta incompleta. O card segue na de 01/11.',
      },
    ])
  })

  it('a fronteira da contagem velha é de 9 dias: no 10º, alerta', () => {
    expect(avisosDaContagem(card(), '2026-11-10')).toEqual([])
    const [aviso] = avisosDaContagem(card(), '2026-11-11')
    expect(aviso.texto).toContain('de 10 dias atrás: o histórico pode ter parado de chegar ao site.')
  })

  it('a execução sem coleta nova não troca a data do card e é dita', () => {
    const uma = avisosDaContagem(card({}, { execucao_mais_recente: '2026-11-04', sem_coleta_nova: ['2026-11-04'] }), HOJE)
    expect(uma).toEqual([
      {
        tom: 'alerta',
        texto: 'A execução de 04/11 não trouxe coleta nova: nenhuma rede foi recoletada. O card segue na contagem de 01/11.',
      },
    ])
    const duas = avisosDaContagem(
      card({}, { execucao_mais_recente: '2026-11-15', sem_coleta_nova: ['2026-11-08', '2026-11-15'] }),
      '2026-11-16',
    )
    expect(duas.map((a) => a.texto)).toEqual([
      'Nenhuma contagem nova entra no card desde 01/11/2026, há 15 dias: o histórico chega, mas as execuções seguintes ficaram de fora.',
      'As execuções de 08/11 e 15/11 não trouxeram coleta nova: nenhuma rede foi recoletada. O card segue na contagem de 01/11.',
    ])
  })

  it('a queda do total que se repetiu e entrou', () => {
    expect(avisosDaContagem(card({}, { total_confirmado: true }), HOJE)).toEqual([
      { tom: 'info', texto: 'A queda do total se manteve por duas contagens seguidas, e esta entrou.' },
    ])
  })

  it('plurais: várias confirmadas e várias recusadas depois da contagem', () => {
    const confirmadas = avisosDaContagem(
      card(
        {},
        {
          confirmadas: [
            { rede: 'selfit', antes: 233, agora: 119, direcao: 'queda', desde: '2026-10-25' },
            { rede: 'bluefit', antes: 100, agora: 160, direcao: 'subida', desde: '2026-10-25' },
          ],
        },
      ),
      HOJE,
    )
    expect(confirmadas[0].texto).toBe('2 saltos bruscos se mantiveram numa coleta mais nova e entraram nesta contagem: Selfit e Bluefit.')
    const recusadas = avisosDaContagem(
      card(
        {},
        {
          execucao_mais_recente: '2026-11-15',
          recusadas: [
            { execucao: '2026-11-08', motivo: 'total', queda_total_pct: 12 },
            { execucao: '2026-11-15', motivo: 'duplicada', queda_total_pct: null },
          ],
        },
      ),
      '2026-11-16',
    )
    expect(recusadas.map((a) => a.texto)).toContain(
      'As contagens de 08/11 e 15/11 ficaram de fora (na de 15/11, ela aparece duas vezes no histórico). O card segue na de 01/11.',
    )
  })

  it('o nome que já começa por "A " não ganha outro artigo', () => {
    expect(comArtigo('selfit')).toBe('A Selfit')
    expect(comArtigo('a_fitness')).toBe('A Fitness')
    const [aviso] = avisosDaContagem(card({}, { nao_recoletadas: ['a_melhor_academia'] }), HOJE)
    expect(aviso.texto).toBe('A Melhor Academia não foi recoletada nesta semana: fica com a última contagem, sem variação.')
  })

  it('"hoje" é a data local de quem abre a página, não a de UTC', () => {
    expect(hojeLocal(new Date(2026, 10, 10, 21, 30))).toBe('2026-11-10')
    expect(hojeLocal(new Date(2026, 0, 5, 0, 5))).toBe('2026-01-05')
  })
})
