import { describe, expect, it } from 'vitest'

import {
  CHAVES_ORDENAVEIS,
  instanteUltimoAcesso,
  ordenarUsuariosAcessos,
  proximaOrdem,
  ritmoDiario,
  type OrdemAcessos,
} from './acessos-ordem'
import type { AcessosUsuarioLinha } from './types'
import { COLUNAS_ACESSOS } from '../screens/AcessosScreen'

function linha(over: Partial<AcessosUsuarioLinha> & { nome: string }): AcessosUsuarioLinha {
  return {
    ultimo_dia: '2026-09-10',
    ultimo_hora: '10:00',
    dias_ativos: 1,
    acoes: 1,
    abas: [],
    ips: 1,
    serie14: [],
    ...over,
  }
}

const nomes = (ls: AcessosUsuarioLinha[]): string[] => ls.map((l) => l.nome)

describe('ciclo de 3 estados (ativar / inverter / desativar)', () => {
  it('1o clique numa coluna numérica abre em decrescente', () => {
    expect(proximaOrdem(null, 'acoes')).toEqual({ chave: 'acoes', direcao: 'desc' })
  })

  it('1o clique no nome abre em crescente (A->Z)', () => {
    expect(proximaOrdem(null, 'nome')).toEqual({ chave: 'nome', direcao: 'asc' })
  })

  it('2o clique inverte a direção', () => {
    expect(proximaOrdem({ chave: 'acoes', direcao: 'desc' }, 'acoes')).toEqual({
      chave: 'acoes',
      direcao: 'asc',
    })
    expect(proximaOrdem({ chave: 'nome', direcao: 'asc' }, 'nome')).toEqual({
      chave: 'nome',
      direcao: 'desc',
    })
  })

  it('3o clique DESLIGA a ordenação (volta à ordem do payload)', () => {
    expect(proximaOrdem({ chave: 'acoes', direcao: 'asc' }, 'acoes')).toBeNull()
    expect(proximaOrdem({ chave: 'nome', direcao: 'desc' }, 'nome')).toBeNull()
  })

  it('o ciclo inteiro de uma coluna fecha em 3 cliques e recomeça', () => {
    let ordem: OrdemAcessos | null = null
    const visto: (OrdemAcessos | null)[] = []
    for (let i = 0; i < 4; i += 1) {
      ordem = proximaOrdem(ordem, 'dias_ativos')
      visto.push(ordem)
    }
    expect(visto).toEqual([
      { chave: 'dias_ativos', direcao: 'desc' },
      { chave: 'dias_ativos', direcao: 'asc' },
      null,
      { chave: 'dias_ativos', direcao: 'desc' },
    ])
  })

  it('clicar em OUTRA coluna reinicia o ciclo nela, sem passar pelo desligado', () => {
    expect(proximaOrdem({ chave: 'acoes', direcao: 'asc' }, 'ultimo')).toEqual({
      chave: 'ultimo',
      direcao: 'desc',
    })
  })

  it('chave desconhecida não mexe no estado', () => {
    const atual: OrdemAcessos = { chave: 'acoes', direcao: 'desc' }
    expect(proximaOrdem(atual, 'coluna_inexistente')).toBe(atual)
    expect(proximaOrdem(null, 'coluna_inexistente')).toBeNull()
  })

  it('as chaves ordenáveis são identificadores sem acento (CLAUDE.md §2)', () => {
    for (const c of CHAVES_ORDENAVEIS) expect(c).toMatch(/^[a-z0-9_]+$/)
  })
})

describe('desligado = ordem do payload, intacta', () => {
  const payload = [linha({ nome: 'zeca' }), linha({ nome: 'ana' }), linha({ nome: 'bruno' })]

  it('sem ordem, devolve a mesma sequência que o backend entregou', () => {
    expect(nomes(ordenarUsuariosAcessos(payload, null))).toEqual(['zeca', 'ana', 'bruno'])
  })

  it('nunca muta o array de origem', () => {
    const copia = [...payload]
    ordenarUsuariosAcessos(payload, { chave: 'nome', direcao: 'asc' })
    expect(payload).toEqual(copia)
  })
})

describe('Último acesso ordena pelo INSTANTE, não pela string exibida', () => {
  // A armadilha real: "9:05" > "10:12" em comparação de texto.
  const cedo = linha({ nome: 'cedo', ultimo_dia: '2026-09-10', ultimo_hora: '09:05' })
  const tarde = linha({ nome: 'tarde', ultimo_dia: '2026-09-10', ultimo_hora: '10:12' })

  it('10:12 é MAIS RECENTE que 09:05 no mesmo dia', () => {
    expect(instanteUltimoAcesso(tarde)! > instanteUltimoAcesso(cedo)!).toBe(true)
    expect(
      nomes(ordenarUsuariosAcessos([cedo, tarde], { chave: 'ultimo', direcao: 'desc' })),
    ).toEqual(['tarde', 'cedo'])
  })

  it('sobrevive a hora sem zero à esquerda vinda do payload', () => {
    const solto = linha({ nome: 'solto', ultimo_dia: '2026-09-10', ultimo_hora: '9:05' })
    expect(instanteUltimoAcesso(solto)).toBe(instanteUltimoAcesso(cedo))
  })

  it('o dia manda sobre a hora', () => {
    const ontemTarde = linha({ nome: 'ontem', ultimo_dia: '2026-09-09', ultimo_hora: '23:59' })
    const hojeCedo = linha({ nome: 'hoje', ultimo_dia: '2026-09-10', ultimo_hora: '00:01' })
    expect(
      nomes(ordenarUsuariosAcessos([ontemTarde, hojeCedo], { chave: 'ultimo', direcao: 'desc' })),
    ).toEqual(['hoje', 'ontem'])
  })

  it('dia sem hora vale meia-noite (o começo daquele dia)', () => {
    const semHora = linha({ nome: 'x', ultimo_dia: '2026-09-10', ultimo_hora: null })
    expect(instanteUltimoAcesso(semHora)).toBe(Date.UTC(2026, 8, 10, 0, 0))
  })

  it('quem NUNCA acessou fica no fim nas DUAS direções', () => {
    const nunca = linha({ nome: 'nunca', ultimo_dia: null, ultimo_hora: null })
    const base = [nunca, cedo, tarde]
    expect(nomes(ordenarUsuariosAcessos(base, { chave: 'ultimo', direcao: 'desc' })).at(-1)).toBe(
      'nunca',
    )
    expect(nomes(ordenarUsuariosAcessos(base, { chave: 'ultimo', direcao: 'asc' })).at(-1)).toBe(
      'nunca',
    )
  })
})

describe('Ritmo diário — o escalar da sparkline é a média da série', () => {
  it('média = soma / no de dias da série', () => {
    expect(ritmoDiario([0, 0, 4, 0])).toBe(1)
    expect(ritmoDiario([2, 2])).toBe(2)
  })

  it('série vazia ou ausente não tem ritmo', () => {
    expect(ritmoDiario([])).toBeNull()
    expect(ritmoDiario(null)).toBeNull()
    expect(ritmoDiario(undefined)).toBeNull()
  })

  it('ordena pelo ritmo, e NÃO pelo total de ações da janela', () => {
    // `maratona` fez mais ações na janela inteira, mas concentradas fora da série;
    // `constante` tem o ritmo maior na série exibida.
    const maratona = linha({ nome: 'maratona', acoes: 100, serie14: [0, 0, 0, 1] })
    const constante = linha({ nome: 'constante', acoes: 12, serie14: [3, 3, 3, 3] })
    expect(
      nomes(ordenarUsuariosAcessos([maratona, constante], { chave: 'serie14', direcao: 'desc' })),
    ).toEqual(['constante', 'maratona'])
    expect(
      nomes(ordenarUsuariosAcessos([maratona, constante], { chave: 'acoes', direcao: 'desc' })),
    ).toEqual(['maratona', 'constante'])
  })

  it('sem série vai para o fim nas duas direções', () => {
    const sem = linha({ nome: 'sem', serie14: [] })
    const com = linha({ nome: 'com', serie14: [1, 1] })
    for (const direcao of ['asc', 'desc'] as const) {
      expect(nomes(ordenarUsuariosAcessos([sem, com], { chave: 'serie14', direcao })).at(-1)).toBe(
        'sem',
      )
    }
  })
})

describe('colunas numéricas e nome', () => {
  const a = linha({ nome: 'ana', dias_ativos: 3, acoes: 30, ips: 1, abas: ['Mapa'] })
  const b = linha({ nome: 'bruno', dias_ativos: 9, acoes: 5, ips: 4, abas: ['Mapa', 'Executiva'] })

  it('decrescente põe o maior primeiro; crescente inverte', () => {
    expect(
      nomes(ordenarUsuariosAcessos([a, b], { chave: 'dias_ativos', direcao: 'desc' })),
    ).toEqual(['bruno', 'ana'])
    expect(nomes(ordenarUsuariosAcessos([a, b], { chave: 'dias_ativos', direcao: 'asc' }))).toEqual([
      'ana',
      'bruno',
    ])
    expect(nomes(ordenarUsuariosAcessos([a, b], { chave: 'acoes', direcao: 'desc' }))).toEqual([
      'ana',
      'bruno',
    ])
    expect(nomes(ordenarUsuariosAcessos([a, b], { chave: 'ips', direcao: 'desc' }))).toEqual([
      'bruno',
      'ana',
    ])
  })

  it('a coluna Abas ordena pela QUANTIDADE de abas tocadas', () => {
    expect(nomes(ordenarUsuariosAcessos([a, b], { chave: 'abas', direcao: 'desc' }))).toEqual([
      'bruno',
      'ana',
    ])
  })

  it('nome usa a colação pt-BR (acento não vai para o fim do alfabeto)', () => {
    const ordenados = nomes(
      ordenarUsuariosAcessos(
        [linha({ nome: 'bruno' }), linha({ nome: 'ávila' }), linha({ nome: 'ana' })],
        { chave: 'nome', direcao: 'asc' },
      ),
    )
    expect(ordenados).toEqual(['ana', 'ávila', 'bruno'])
  })

  it('empate no valor cai no nome, para a ordem não dançar entre renders', () => {
    const x = linha({ nome: 'zeca', acoes: 7 })
    const y = linha({ nome: 'ana', acoes: 7 })
    for (const direcao of ['asc', 'desc'] as const) {
      expect(nomes(ordenarUsuariosAcessos([x, y], { chave: 'acoes', direcao }))).toEqual([
        'ana',
        'zeca',
      ])
    }
  })
})

/* ---------------------------------------------------------------------------------
   A FONTE ÚNICA das colunas ordenáveis.

   As mesmas 7 chaves viviam em TRÊS listas que nada amarrava — a allowlist daqui, o
   array `colunas` da tela e um `switch` de escalares — e as duas divergências possíveis
   eram MUDAS: verdes no `tsc` e na suíte inteira, visíveis só para quem clicasse.

   Hoje as três saem do mesmo mapa, então a divergência (i) — chave na tela e fora da
   allowlist — é erro de compilação. O que continua precisando de teste é a (ii), que é
   de COMPORTAMENTO: chave declarada sem escalar não quebra nada, só devolve a mesma
   ordem nas duas direções.
   --------------------------------------------------------------------------------- */
describe('as três listas de colunas viraram uma', () => {
  it('as colunas da tela são exatamente as chaves ordenáveis, na mesma ordem', () => {
    expect(COLUNAS_ACESSOS.map((c) => c.chave)).toEqual([...CHAVES_ORDENAVEIS])
  })

  it('toda coluna da tela desenha a própria célula', () => {
    for (const c of COLUNAS_ACESSOS) expect(typeof c.render, c.chave).toBe('function')
  })

  it('toda chave ordenável tem escalar: asc e desc NUNCA devolvem a mesma ordem', () => {
    // A falha (ii) do acoplamento antigo: chave na allowlist sem `case` no switch dava
    // escalar nulo em TODAS as linhas, as duas direções caíam no desempate por nome e
    // saíam A-Z nas duas — o que o operador lê como "ordenou errado".
    // O trio é construído para que TODA coluna concorde com a ordem alfabética: se uma
    // delas parar de ordenar, o `desc` volta a sair A-Z e o caso reprova nela.
    const trio = [
      linha({ nome: 'ana', ultimo_dia: '2026-09-01', dias_ativos: 1, acoes: 1, ips: 1, abas: [], serie14: [1] }),
      linha({ nome: 'bruno', ultimo_dia: '2026-09-02', dias_ativos: 2, acoes: 2, ips: 2, abas: ['Mapa'], serie14: [2] }),
      linha({ nome: 'carla', ultimo_dia: '2026-09-03', dias_ativos: 3, acoes: 3, ips: 3, abas: ['Mapa', 'Executiva'], serie14: [3] }),
    ]
    for (const chave of CHAVES_ORDENAVEIS) {
      expect(nomes(ordenarUsuariosAcessos(trio, { chave, direcao: 'asc' })), chave).toEqual([
        'ana',
        'bruno',
        'carla',
      ])
      expect(nomes(ordenarUsuariosAcessos(trio, { chave, direcao: 'desc' })), chave).toEqual([
        'carla',
        'bruno',
        'ana',
      ])
    }
  })
})
