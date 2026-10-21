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
  municipioDaUnidade,
  normalizarNomeMunicipio,
  planoDeTroca,
  territorioDaUnidade,
  ufDaUnidade,
} from './territorio-unidade'
import type { RedeUnidade } from './types'

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

  it('a troca usa os MESMOS onUf/onMunicipio do cabeçalho, e só quando o plano pede', () => {
    const inicio = mapa.indexOf('const levarAoTerritorioDaUnidade = useCallback(')
    const corpo = mapa.slice(inicio, mapa.indexOf('const abrirUnidade = useCallback(', inicio))
    expect(corpo).toContain('if (!viagem.vale(seq)) return')
    expect(corpo).toContain('if (plano.uf === null && plano.municipio === null) return')
    expect(corpo).toContain('if (plano.uf !== null) a.onUf(plano.uf)')
    expect(corpo).toContain('if (plano.municipio !== null) a.onMunicipio(plano.municipio)')
    // a lista é a da UF da unidade, ou é pedida
    expect(corpo).toContain('a.municipiosUf.toUpperCase() === ufAlvo')
    expect(corpo).toContain('.municipios(ufAlvo)')
    // o hexágono só vale se o payload aberto for da UF da unidade
    expect(corpo).toContain('a.dados.uf.toUpperCase() === ufAlvo')
    // a viagem é marcada ANTES de pedir a troca, e só se a escolha ainda vale
    const embarque = 'if (!viagem.embarcar(seq, chaveContexto(ufFinal, munFinal), { unidade, pin: pinU })) return'
    expect(corpo).toContain(embarque)
    expect(corpo.indexOf(embarque)).toBeLessThan(corpo.indexOf('a.onUf(plano.uf)'))
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
