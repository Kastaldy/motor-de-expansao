/**
 * Selecionar uma unidade Ultra leva o cabecalho ao municipio (e a' UF) dela -- pedido do
 * Vinicius, 21/10/2026. A regra pura mora em `territorio-unidade`; a fiacao no `MapScreen`
 * e' travada pelo FONTE no fim deste arquivo (o Vitest roda sem DOM).
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { unidadesDaBusca } from './ficha-unidade'
import {
  type FontesDoTerritorio,
  municipioDaUnidade,
  normalizarNomeMunicipio,
  planoDeTroca,
  resolverTerritorioDaUnidade,
  territorioDaUnidade,
  ufDaUnidade,
  viajarAoTerritorioDaUnidade,
} from './territorio-unidade'
import type { RedeUnidade } from './types'
import { criarViagemUnidade } from './viagem-unidade'

const lista = (...nomes: string[]) => nomes.map((nome) => ({ nome }))
const SP = lista('São Paulo', 'São Bernardo do Campo', 'Santa Bárbara d’Oeste', 'Mogi das Cruzes')

describe('normalizarNomeMunicipio', () => {
  it('ignora acento, caixa, hífen, apóstrofo e espaço repetido', () => {
    expect(normalizarNomeMunicipio('  SÃO  João del-Rei ')).toBe('sao joao del rei')
    expect(normalizarNomeMunicipio("Santa Bárbara d'Oeste")).toBe(normalizarNomeMunicipio('Santa Bárbara d’Oeste'))
  })
})

describe('municipioDaUnidade', () => {
  it('casa o nome do cadastro com a lista da UF e devolve a grafia DA LISTA', () => {
    expect(municipioDaUnidade({ uf: 'SP', cidade: 'SAO PAULO' }, SP)).toBe('São Paulo')
    expect(municipioDaUnidade({ uf: 'SP', cidade: "Santa Barbara d'Oeste" }, SP)).toBe('Santa Bárbara d’Oeste')
  })

  it('tira o sufixo da UF quando o cadastro o escreve junto', () => {
    expect(municipioDaUnidade({ uf: 'SP', cidade: 'São Bernardo do Campo - SP' }, SP)).toBe('São Bernardo do Campo')
    expect(municipioDaUnidade({ uf: 'SP', cidade: 'Mogi das Cruzes/SP' }, SP)).toBe('Mogi das Cruzes')
    expect(municipioDaUnidade({ uf: 'SP', cidade: 'São Paulo (SP)' }, SP)).toBe('São Paulo')
  })

  it('UF de um município só (DF): a região administrativa do cadastro vira Brasília', () => {
    expect(municipioDaUnidade({ uf: 'DF', cidade: 'Taguatinga' }, lista('Brasília'))).toBe('Brasília')
    expect(municipioDaUnidade({ uf: 'DF', cidade: null }, lista('Brasília'))).toBe('Brasília')
  })

  it('sem nome que case, usa o município do hexágono da unidade (o do M1)', () => {
    expect(municipioDaUnidade({ uf: 'SP', cidade: 'Embu' }, SP, 'MOGI DAS CRUZES')).toBe('Mogi das Cruzes')
    // sem a lista (a busca falhou), o nome do hexágono já é do mesmo domínio
    expect(municipioDaUnidade({ uf: 'SP', cidade: null }, [], 'Mogi das Cruzes')).toBe('Mogi das Cruzes')
  })

  it('o nome do cadastro vence o hexágono (o hexágono de divisa pode ser do vizinho)', () => {
    expect(municipioDaUnidade({ uf: 'SP', cidade: 'São Paulo' }, SP, 'São Bernardo do Campo')).toBe('São Paulo')
  })

  it('sem município resolvido devolve null -- nunca chuta', () => {
    expect(municipioDaUnidade({ uf: 'SP', cidade: null }, SP)).toBeNull()
    expect(municipioDaUnidade({ uf: 'SP', cidade: 'Cidade Que Não Existe' }, SP)).toBeNull()
    expect(municipioDaUnidade({ uf: 'SP', cidade: 'Embu' }, SP, 'Nome fora da lista')).toBeNull()
    expect(municipioDaUnidade({ uf: 'SP', cidade: 'São Paulo' }, [])).toBeNull()
  })

  it('só procura DENTRO da lista recebida: nome repetido entre UFs não cruza a divisa', () => {
    // "Bom Jesus" existe em várias UFs; a lista é a da UF da unidade, e é ela que decide.
    const GO = lista('Goiânia', 'Bom Jesus de Goiás')
    expect(municipioDaUnidade({ uf: 'GO', cidade: 'Bom Jesus' }, GO)).toBeNull()
    expect(municipioDaUnidade({ uf: 'PI', cidade: 'Bom Jesus' }, lista('Teresina', 'Bom Jesus'))).toBe('Bom Jesus')
  })
})

describe('territorioDaUnidade + planoDeTroca', () => {
  it('mesma UF, outro município: troca só o município', () => {
    const alvo = territorioDaUnidade({ uf: 'SP', cidade: 'Mogi das Cruzes' }, 'SP', SP)
    expect(alvo).toEqual({ uf: 'SP', municipio: 'Mogi das Cruzes' })
    expect(planoDeTroca({ uf: 'SP', municipio: '' }, alvo)).toEqual({ uf: null, municipio: 'Mogi das Cruzes' })
    expect(planoDeTroca({ uf: 'SP', municipio: 'São Paulo' }, alvo)).toEqual({ uf: null, municipio: 'Mogi das Cruzes' })
  })

  it('a unidade já está no território aberto: nada muda', () => {
    const alvo = territorioDaUnidade({ uf: 'SP', cidade: 'são paulo' }, 'SP', SP)
    expect(planoDeTroca({ uf: 'SP', municipio: 'São Paulo' }, alvo)).toEqual({ uf: null, municipio: null })
  })

  it('OUTRA UF: troca a UF e pede o município (a UF nova zera o município sozinha)', () => {
    const GO = lista('Goiânia', 'Águas Lindas de Goiás')
    const alvo = territorioDaUnidade({ uf: 'go', cidade: 'Aguas Lindas de Goias' }, 'DF', GO)
    expect(alvo).toEqual({ uf: 'GO', municipio: 'Águas Lindas de Goiás' })
    expect(planoDeTroca({ uf: 'DF', municipio: 'Brasília' }, alvo)).toEqual({
      uf: 'GO',
      municipio: 'Águas Lindas de Goiás',
    })
  })

  it('OUTRA UF sem município resolvido: só a UF (visão do estado, que contém a unidade)', () => {
    const alvo = territorioDaUnidade({ uf: 'GO', cidade: null }, 'DF', [])
    expect(alvo).toEqual({ uf: 'GO', municipio: '' })
    expect(planoDeTroca({ uf: 'DF', municipio: 'Brasília' }, alvo)).toEqual({ uf: 'GO', municipio: null })
  })

  it('mesma UF sem município resolvido: volta à visão da UF em vez de afirmar a cidade errada', () => {
    const alvo = territorioDaUnidade({ uf: 'SP', cidade: null }, 'SP', SP)
    expect(planoDeTroca({ uf: 'SP', municipio: 'São Paulo' }, alvo)).toEqual({ uf: null, municipio: '' })
    // já na visão da UF: nada muda
    expect(planoDeTroca({ uf: 'SP', municipio: '' }, alvo)).toEqual({ uf: null, municipio: null })
  })

  it('unidade sem UF no registro fica na UF aberta', () => {
    expect(ufDaUnidade({ uf: null }, 'sp')).toBe('SP')
    expect(ufDaUnidade({ uf: ' rj ' }, 'SP')).toBe('RJ')
  })
})

describe('o seletor UNIDADES leva UF e cidade até a resolução', () => {
  it('as opções da rede e do cadastro carregam uf e cidade', () => {
    const rede = [{ id: 'a', nome: 'Alfa', uf: 'SP', cidade: 'São Paulo', lat: 1, lng: 2 } as unknown as RedeUnidade]
    const cadastro = [{ id: 'b', nome: 'Beta', uf: 'SP', cidade: 'Mogi das Cruzes', lat: null, lng: null }]
    const [alfa, beta] = unidadesDaBusca(rede, cadastro, 'SP')
    expect(alfa).toMatchObject({ uf: 'SP', cidade: 'São Paulo' })
    expect(beta).toMatchObject({ uf: 'SP', cidade: 'Mogi das Cruzes' })
  })
})

const mapa = readFileSync(fileURLToPath(new URL('../screens/MapScreen.tsx', import.meta.url)), 'utf-8')
const app = readFileSync(fileURLToPath(new URL('../App.tsx', import.meta.url)), 'utf-8')

describe('a fiação no MapScreen', () => {
  it('abrirUnidade (porta do seletor E do pin) leva o mapa ao território da unidade', () => {
    const inicio = mapa.indexOf('const abrirUnidade = useCallback(')
    const corpo = mapa.slice(inicio, mapa.indexOf('[onSoltarPonto, levarAoTerritorioDaUnidade]', inicio))
    expect(corpo).toContain('const seq = viagem.iniciar()')
    expect(corpo).toContain('levarAoTerritorioDaUnidade(u, seq, unidade, pinU)')
  })

  it('a troca usa os MESMOS onUf/onMunicipio do cabeçalho, com a coordenada da unidade primeiro', () => {
    const inicio = mapa.indexOf('const levarAoTerritorioDaUnidade = useCallback(')
    const corpo = mapa.slice(inicio, mapa.indexOf('const abrirUnidade = useCallback(', inicio))
    // a ordem e o descarte moram na lib (testados por comportamento abaixo)
    expect(corpo).toContain('void viajarAoTerritorioDaUnidade({')
    expect(corpo).toContain('carga: { unidade, pin: pinU }')
    expect(corpo).toContain('coordenada: pinU ? { lat: pinU.lat, lng: pinU.lng } : null')
    expect(corpo).toContain('municipioDoPonto: (lat, lng) => api.municipioDoPonto(lat, lng)')
    expect(corpo).toContain('chave: chaveContexto')
    expect(corpo).toContain('if (plano.uf !== null) a.onUf(plano.uf)')
    expect(corpo).toContain('if (plano.municipio !== null) a.onMunicipio(plano.municipio)')
    // a lista é a da UF pedida (a da coordenada, quando veio), ou é pedida ao servidor
    expect(corpo).toContain('a.municipiosUf.toUpperCase() === ufAlvo')
    expect(corpo).toContain('.municipios(ufAlvo)')
    // o hexágono só vale se o payload aberto for da UF pedida
    expect(corpo).toContain('a.dados.uf.toUpperCase() === ufAlvo')
  })

  it('a troca de território causada pela unidade NÃO fecha a ficha dela', () => {
    const inicio = mapa.indexOf('const transito = viagem.chegar(contexto)')
    expect(inicio).toBeGreaterThan(-1)
    const corpo = mapa.slice(inicio, mapa.indexOf('}, [uf, municipio])', inicio))
    expect(corpo).toContain('if (transito) {')
    expect(corpo).toContain('setUnidadeAberta(transito.unidade)')
    expect(corpo).toContain('setPin(transito.pin)')
    // qualquer outra troca fecha a ficha (o cancelamento é do `chegar`, testado em viagem-unidade)
    expect(corpo).toContain('setUnidadeAberta(null)')
    // reabrir NÃO chama abrirUnidade (sem ciclo de seleção)
    expect(corpo).not.toContain('abrirUnidade(')
  })

  it('o pin da Ultra casa contra a rede inteira (unidade do outro lado da divisa)', () => {
    expect(mapa).toContain('const u = unidadeDoPin(p, unidadesRede ?? [])')
    expect(mapa).not.toContain('unidadesUf')
  })

  it('fechar a ficha cancela a viagem pendente', () => {
    expect(mapa).toContain('onFechar={fecharUnidade}')
    const inicio = mapa.indexOf('const fecharUnidade = useCallback(')
    const corpo = mapa.slice(inicio, mapa.indexOf('}, [viagem])', inicio))
    expect(corpo).toContain('viagem.cancelar()')
  })

  it('sair do mapa com a lista em voo cancela a viagem (nada muda o território do App depois)', () => {
    expect(mapa).toContain('useEffect(() => () => viagem.cancelar(), [viagem])')
  })

  it('todo gesto que reposiciona a atenção cancela a viagem pendente', () => {
    const corpoDe = (abre: string, fecha: string) => {
      const i = mapa.indexOf(abre)
      expect(i, abre).toBeGreaterThan(-1)
      return mapa.slice(i, mapa.indexOf(fecha, i))
    }
    // imóvel, item da lista, comparar, busca/ponto, ponto da comparação
    expect(corpoDe('const abrirImovel = useCallback(', '}, [viagem])')).toContain('viagem.cancelar()')
    expect(corpoDe('const selecionarDaLista = useCallback(', '}, [viagem])')).toContain('viagem.cancelar()')
    expect(corpoDe('const comparar = useCallback(', '}, [viagem])')).toContain('viagem.cancelar()')
    expect(corpoDe('function aplicarPonto(', 'onPontoBuscado(')).toContain('viagem.cancelar()')
    expect(corpoDe('const aoClicarPontoComparado = useCallback(', '[viagem, onPontoComparado]')).toContain(
      'viagem.cancelar()',
    )
    expect(mapa).toContain('onPontoClicado={aoClicarPontoComparado}')
    // clique num hexágono
    expect(corpoDe('onSelecionar={(h) => {', 'setSelecionado(h.id)')).toContain('viagem.cancelar()')
    // destino de lista ou ponto analisado NOVO (só quando aparece: a unidade os solta)
    expect(mapa).toContain('if (pontoAtivo || pinFixo) viagem.cancelar()')
  })

  it('o App diz de que UF é a lista de municípios', () => {
    expect(app).toContain('setMunicipiosUf(r.uf ?? uf)')
    expect(app).toContain('municipiosUf={municipiosUf}')
  })
})

// --------------------------------------------------------------------------------------
// Defeito de 21/10/2026 (Vinicius): "leva para 'Todos os municípios' na primeira tentativa".
// A carteira vem com `cidade` vazia, e de DENTRO de outro município o hexágono da unidade
// não está no payload aberto -- as três regras antigas falhavam juntas.
// --------------------------------------------------------------------------------------

const MUNS: Record<string, readonly { nome: string }[]> = {
  SP,
  GO: lista('Goiânia', 'Águas Lindas de Goiás'),
  DF: lista('Brasília'),
}

/** Fontes falsas: o servidor responde `ponto` (ou rejeita), a lista vem de MUNS. */
function fontes(
  ponto: { uf: string; municipio: string | null; no_seletor?: boolean } | Error | Promise<never>,
  extra: Partial<FontesDoTerritorio> = {},
): FontesDoTerritorio & { chamadas: string[] } {
  const chamadas: string[] = []
  return {
    chamadas,
    municipioDoPonto: (lat, lng) => {
      chamadas.push(`ponto:${lat},${lng}`)
      if (ponto instanceof Error) return Promise.reject(ponto)
      if (ponto instanceof Promise) return ponto
      return Promise.resolve(ponto)
    },
    municipiosDaUf: (uf) => {
      chamadas.push(`lista:${uf}`)
      return Promise.resolve(MUNS[uf] ?? [])
    },
    munDoHexagono: () => null,
    ...extra,
  }
}

const COORD = { lat: -23.52, lng: -46.19 }
const SEM_CIDADE = { uf: 'SP', cidade: null }

describe('a coordenada vem primeiro (resolverTerritorioDaUnidade)', () => {
  it('unidade SEM cidade, operador dentro de OUTRO município: vai ao município da coordenada', async () => {
    const f = fontes({ uf: 'SP', municipio: 'Mogi das Cruzes', no_seletor: true })
    const alvo = await resolverTerritorioDaUnidade(SEM_CIDADE, COORD, 'SP', f)
    expect(alvo).toEqual({ uf: 'SP', municipio: 'Mogi das Cruzes' })
    // o servidor é perguntado ANTES da lista
    expect(f.chamadas).toEqual(['ponto:-23.52,-46.19', 'lista:SP'])
  })

  it('o nome do servidor casa com a lista pelo nome normalizado e sai na grafia DA LISTA', async () => {
    const f = fontes({ uf: 'sp', municipio: 'SAO BERNARDO DO CAMPO', no_seletor: false })
    expect(await resolverTerritorioDaUnidade(SEM_CIDADE, COORD, 'SP', f)).toEqual({
      uf: 'SP',
      municipio: 'São Bernardo do Campo',
    })
  })

  it('a coordenada vence o cadastro (a cidade do cadastro pode estar errada)', async () => {
    const f = fontes({ uf: 'SP', municipio: 'Mogi das Cruzes', no_seletor: true })
    const alvo = await resolverTerritorioDaUnidade({ uf: 'SP', cidade: 'São Paulo' }, COORD, 'SP', f)
    expect(alvo.municipio).toBe('Mogi das Cruzes')
  })

  it('a rota falha: cai na cidade do cadastro', async () => {
    const f = fontes(new Error('503'))
    const alvo = await resolverTerritorioDaUnidade({ uf: 'SP', cidade: 'Mogi das Cruzes' }, COORD, 'SP', f)
    expect(alvo).toEqual({ uf: 'SP', municipio: 'Mogi das Cruzes' })
  })

  it('a rota falha e não há cidade: cai no hexágono, e só então na UF inteira', async () => {
    const comHex = fontes(new Error('404'), { munDoHexagono: (uf) => (uf === 'SP' ? 'MOGI DAS CRUZES' : null) })
    expect(await resolverTerritorioDaUnidade(SEM_CIDADE, COORD, 'SP', comHex)).toEqual({
      uf: 'SP',
      municipio: 'Mogi das Cruzes',
    })
    expect(await resolverTerritorioDaUnidade(SEM_CIDADE, COORD, 'SP', fontes(new Error('404')))).toEqual({
      uf: 'SP',
      municipio: '',
    })
  })

  it('UF de município único sem resposta do servidor: o DF segue indo a Brasília', async () => {
    const f = fontes(new Error('fora do ar'))
    expect(await resolverTerritorioDaUnidade({ uf: 'DF', cidade: 'Taguatinga' }, COORD, 'SP', f)).toEqual({
      uf: 'DF',
      municipio: 'Brasília',
    })
  })

  it('nome do servidor fora da lista: não chuta, segue os fallbacks', async () => {
    const f = fontes({ uf: 'SP', municipio: 'Embu', no_seletor: false })
    const alvo = await resolverTerritorioDaUnidade({ uf: 'SP', cidade: 'Mogi das Cruzes' }, COORD, 'SP', f)
    expect(alvo.municipio).toBe('Mogi das Cruzes')
  })

  it('sem lista (a busca falhou): aceita o nome só quando o servidor diz que é o do seletor', async () => {
    const semLista = { municipiosDaUf: () => Promise.reject(new Error('timeout')) }
    const doSeletor = fontes({ uf: 'SP', municipio: 'Mogi das Cruzes', no_seletor: true }, semLista)
    expect((await resolverTerritorioDaUnidade(SEM_CIDADE, COORD, 'SP', doSeletor)).municipio).toBe('Mogi das Cruzes')
    const doCenso = fontes({ uf: 'SP', municipio: 'Mogi das Cruzes', no_seletor: false }, semLista)
    expect((await resolverTerritorioDaUnidade(SEM_CIDADE, COORD, 'SP', doCenso)).municipio).toBe('')
  })

  it('ponto em OUTRA UF que a do cadastro: a coordenada manda, e a lista pedida é a dela', async () => {
    const f = fontes({ uf: 'GO', municipio: 'Águas Lindas de Goiás', no_seletor: true })
    const alvo = await resolverTerritorioDaUnidade({ uf: 'DF', cidade: 'Ceilândia' }, COORD, 'DF', f)
    expect(alvo).toEqual({ uf: 'GO', municipio: 'Águas Lindas de Goiás' })
    expect(f.chamadas).toContain('lista:GO')
    expect(f.chamadas).not.toContain('lista:DF')
  })

  it('unidade sem coordenada: o servidor nem é chamado', async () => {
    const f = fontes({ uf: 'SP', municipio: 'Mogi das Cruzes' })
    expect(await resolverTerritorioDaUnidade({ uf: 'SP', cidade: 'São Paulo' }, null, 'SP', f)).toEqual({
      uf: 'SP',
      municipio: 'São Paulo',
    })
    expect(f.chamadas).toEqual(['lista:SP'])
  })
})

describe('viajarAoTerritorioDaUnidade: a troca e o descarte da resposta atrasada', () => {
  type Carga = { unidade: string }
  const chave = (uf: string, m: string) => `${uf}|${m}`

  function montar(f: FontesDoTerritorio, atual = { uf: 'SP', municipio: 'São Paulo' }) {
    const viagem = criarViagemUnidade<Carga>()
    const trocas: { uf: string | null; municipio: string | null }[] = []
    const pedido = (seq: number) => ({
      viagem,
      seq,
      carga: { unidade: 'U' },
      unidade: SEM_CIDADE,
      coordenada: COORD,
      atual: () => atual,
      fontes: f,
      chave,
      trocar: (plano: { uf: string | null; municipio: string | null }) => trocas.push(plano),
    })
    return { viagem, trocas, pedido }
  }

  it('o defeito relatado: de dentro de São Paulo, a unidade de Mogi leva a Mogi (e não a "Todos")', async () => {
    const { viagem, trocas, pedido } = montar(fontes({ uf: 'SP', municipio: 'Mogi das Cruzes', no_seletor: true }))
    const seq = viagem.iniciar()
    expect(await viajarAoTerritorioDaUnidade(pedido(seq))).toBe(true)
    expect(trocas).toEqual([{ uf: null, municipio: 'Mogi das Cruzes' }])
    // a ficha atravessa a troca: a chegada é reconhecida pela chave do município CERTO
    expect(viagem.chegar('SP|Mogi das Cruzes')).toEqual({ unidade: 'U' })
  })

  it('resposta do servidor depois de um gesto (cancelar): descartada, nada troca', async () => {
    let responder: (v: { uf: string; municipio: string; no_seletor: boolean }) => void = () => {}
    const atrasada = new Promise<{ uf: string; municipio: string; no_seletor: boolean }>((r) => {
      responder = r
    })
    const f = fontes({ uf: 'SP', municipio: null }, { municipioDoPonto: () => atrasada })
    const { viagem, trocas, pedido } = montar(f)
    const seq = viagem.iniciar()
    const voo = viajarAoTerritorioDaUnidade(pedido(seq))
    viagem.cancelar() // o operador clicou num hexágono com a resposta em voo
    responder({ uf: 'SP', municipio: 'Mogi das Cruzes', no_seletor: true })
    expect(await voo).toBe(false)
    expect(trocas).toEqual([])
  })

  it('outra unidade escolhida com a primeira em voo: só a segunda troca o território', async () => {
    let responder: (v: { uf: string; municipio: string; no_seletor: boolean }) => void = () => {}
    const lenta = new Promise<{ uf: string; municipio: string; no_seletor: boolean }>((r) => {
      responder = r
    })
    const respostas = [lenta, Promise.resolve({ uf: 'SP', municipio: 'São Bernardo do Campo', no_seletor: true })]
    const f = fontes({ uf: 'SP', municipio: null }, { municipioDoPonto: () => respostas.shift()! })
    const { viagem, trocas, pedido } = montar(f)
    const primeira = viajarAoTerritorioDaUnidade(pedido(viagem.iniciar()))
    const segunda = viajarAoTerritorioDaUnidade(pedido(viagem.iniciar()))
    expect(await segunda).toBe(true)
    responder({ uf: 'SP', municipio: 'Mogi das Cruzes', no_seletor: true })
    expect(await primeira).toBe(false)
    expect(trocas).toEqual([{ uf: null, municipio: 'São Bernardo do Campo' }])
  })

  it('a unidade já está no território aberto: nada troca e nada embarca', async () => {
    const { viagem, trocas, pedido } = montar(fontes({ uf: 'SP', municipio: 'São Paulo', no_seletor: true }))
    expect(await viajarAoTerritorioDaUnidade(pedido(viagem.iniciar()))).toBe(false)
    expect(trocas).toEqual([])
  })

  it('outra UF: pede a UF e o município juntos', async () => {
    const f = fontes({ uf: 'GO', municipio: 'Águas Lindas de Goiás', no_seletor: true })
    const { viagem, trocas, pedido } = montar(f, { uf: 'DF', municipio: 'Brasília' })
    expect(await viajarAoTerritorioDaUnidade(pedido(viagem.iniciar()))).toBe(true)
    expect(trocas).toEqual([{ uf: 'GO', municipio: 'Águas Lindas de Goiás' }])
    expect(viagem.chegar('GO|Águas Lindas de Goiás')).toEqual({ unidade: 'U' })
  })
})
