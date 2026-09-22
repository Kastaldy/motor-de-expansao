import { describe, expect, it } from 'vitest'

import {
  DIMENSOES_RECORTE,
  MODOS,
  ORDEM_TRILHAS,
  PASSO_MAX,
  PASSO_MIN,
  SUBTITULO_AMBAS,
  TRILHAS,
  dimensaoPorId,
  entradaDaExecutiva,
  entradaValida,
  modoPorId,
  modosDaTrilha,
  passoAlvoDoModo,
  trilhaInicial,
  trilhasDisponiveis,
  type ModoInicio,
} from './inicio'

describe('MODOS', () => {
  it('declara as duas trilhas, na ordem do menu', () => {
    expect(MODOS.map((m) => m.id)).toEqual([
      'oportunidades',
      'regiao',
      'ponto',
      'panorama',
      'recorte',
      'unidade',
    ])
  })

  it('nao repete id', () => {
    expect(new Set(MODOS.map((m) => m.id)).size).toBe(MODOS.length)
  })

  it('so aponta para telas que existem hoje', () => {
    for (const m of MODOS) {
      expect(['mapa', 'ponto', 'oportunidades', 'executiva']).toContain(m.destino)
    }
  })

  it('cada modo de expansao abre a SUA tela dedicada', () => {
    expect(modoPorId('ponto')?.destino).toBe('ponto')
    expect(modoPorId('oportunidades')?.destino).toBe('oportunidades')
    // Regiao continua no mapa DE PROPOSITO: o funil e' a tela dele.
    expect(modoPorId('regiao')?.destino).toBe('mapa')
  })

  it('os tres modos de operacoes levam a MESMA tela, mudando so o recorte', () => {
    // Nao e' preguica: a Executiva ja' e' carteira + mapa + ficha num scroller so'.
    // Card que prometesse tela nova aqui estaria mentindo.
    const ops = modosDaTrilha('operacoes')
    expect(ops.map((m) => m.destino)).toEqual(['executiva', 'executiva', 'executiva'])
    expect(ops.map((m) => m.segundoPasso)).toEqual([null, 'recorte', 'unidade'])
  })

  it('o segundo passo vale nas DUAS trilhas, com o passo de cada card', () => {
    /* Em 2026-09-22 (2a rodada) a expansao ganhou passo tambem: o card pergunta o que a
       tela de destino perguntaria no primeiro gesto. Os DOIS `null` sao deliberados — o
       panorama e' a rede inteira por definicao, e a fila nacional promete no proprio
       texto "sem escolher estado antes". */
    expect(MODOS.map((m) => [m.id, m.segundoPasso])).toEqual([
      ['oportunidades', null],
      ['regiao', 'uf'],
      ['ponto', 'endereco'],
      ['panorama', null],
      ['recorte', 'recorte'],
      ['unidade', 'unidade'],
    ])
  })

  it('card com passo continua apontando para a tela que o atende', () => {
    // O passo PRE-RESPONDE a pergunta da tela; ele nao troca o destino dela.
    expect(modoPorId('regiao')?.destino).toBe('mapa')
    expect(modoPorId('ponto')?.destino).toBe('ponto')
  })

  it('todo card tem texto de usuario preenchido e uma arte', () => {
    for (const m of MODOS) {
      expect(m.eyebrow.trim()).not.toBe('')
      expect(m.titulo.trim()).not.toBe('')
      expect(m.linha.trim()).not.toBe('')
      expect(['brasil', 'estado', 'ponto', 'painel', 'rede', 'ficha']).toContain(m.arte)
    }
  })

  it('nao reaproveita a mesma arte em dois cards', () => {
    expect(new Set(MODOS.map((m) => m.arte)).size).toBe(MODOS.length)
  })

  it('mantem os identificadores SEM acento (regra do CLAUDE.md §2)', () => {
    // O texto de usuario e' acentuado de proposito; o `id` nunca.
    for (const m of MODOS) expect(m.id).toMatch(/^[a-z]+$/)
  })

  it('e congelado: o menu nao pode ser mutado em runtime', () => {
    expect(Object.isFrozen(MODOS)).toBe(true)
    for (const m of MODOS) expect(Object.isFrozen(m)).toBe(true)
  })
})

describe('trilhas', () => {
  it('toda trilha declarada tem rotulo e subtitulo', () => {
    for (const t of ORDEM_TRILHAS) {
      expect(TRILHAS[t].rotulo.trim()).not.toBe('')
      expect(TRILHAS[t].subtitulo.trim()).not.toBe('')
    }
    expect(SUBTITULO_AMBAS.trim()).not.toBe('')
  })

  it('todo modo pertence a uma trilha declarada', () => {
    for (const m of MODOS) expect(ORDEM_TRILHAS).toContain(m.trilha)
  })

  it('modosDaTrilha devolve so os cards daquela pergunta', () => {
    expect(modosDaTrilha('expansao').map((m) => m.id)).toEqual([
      'oportunidades',
      'regiao',
      'ponto',
    ])
    expect(modosDaTrilha('operacoes').map((m) => m.id)).toEqual([
      'panorama',
      'recorte',
      'unidade',
    ])
  })
})

describe('trilhasDisponiveis', () => {
  it('com todos os cards, as duas trilhas existem na ordem da pilula', () => {
    expect(trilhasDisponiveis(MODOS)).toEqual(['expansao', 'operacoes'])
  })

  it('so a Executiva liberada = so a trilha de operacoes', () => {
    // E' exatamente o perfil que caia numa tela VAZIA antes de 2026-09-22.
    const so = modosDaTrilha('operacoes')
    expect(trilhasDisponiveis(so)).toEqual(['operacoes'])
    expect(trilhaInicial(so)).toBe('operacoes')
  })

  it('sem a Executiva = so a trilha de expansao', () => {
    const so = modosDaTrilha('expansao')
    expect(trilhasDisponiveis(so)).toEqual(['expansao'])
  })

  it('com as duas, a entrada abre na de expansao', () => {
    expect(trilhaInicial(MODOS)).toBe('expansao')
  })

  it('sem card nenhum nao ha trilha — a tela mostra a explicacao, nao uma pilula vazia', () => {
    expect(trilhasDisponiveis([])).toEqual([])
    expect(trilhaInicial([])).toBeNull()
  })
})

describe('modoPorId', () => {
  it('acha cada modo declarado', () => {
    for (const m of MODOS) expect(modoPorId(m.id)?.titulo).toBe(m.titulo)
  })

  it('devolve null para id desconhecido em vez de estourar', () => {
    expect(modoPorId('inexistente')).toBeNull()
    expect(modoPorId('')).toBeNull()
  })
})

describe('passoAlvoDoModo', () => {
  it('nenhum modo pede passo do mapa — todos tem tela propria ou o funil inteiro', () => {
    // `oportunidades` pedia o passo 5 enquanto reusava o mapa; com tela propria a fila
    // deixou de ser um passo do funil.
    for (const m of MODOS) expect(passoAlvoDoModo(m.id)).toBeNull()
  })

  it('o guarda de faixa continua valendo para quem voltar a usar passo', () => {
    // Protege o contrato: passo fora de 1..5 nunca deve chegar ao backend.
    expect(PASSO_MIN).toBe(1)
    expect(PASSO_MAX).toBe(5)
  })

  it('id desconhecido nao vira passo', () => {
    expect(passoAlvoDoModo('nada' as ModoInicio)).toBeNull()
  })
})

describe('DIMENSOES_RECORTE', () => {
  it('oferece os tres eixos pedidos, com Estado primeiro', () => {
    expect(DIMENSOES_RECORTE.map((d) => d.id)).toEqual(['uf', 'master', 'consultor'])
  })

  it('todo eixo tem rotulo de chip e convite de seletor', () => {
    for (const d of DIMENSOES_RECORTE) {
      expect(d.rotulo.trim()).not.toBe('')
      expect(d.convite.trim()).not.toBe('')
    }
  })

  it('e congelado', () => {
    expect(Object.isFrozen(DIMENSOES_RECORTE)).toBe(true)
    for (const d of DIMENSOES_RECORTE) expect(Object.isFrozen(d)).toBe(true)
  })

  it('dimensaoPorId devolve null para eixo desconhecido em vez de estourar', () => {
    expect(dimensaoPorId('uf')?.rotulo).toBe('Estado')
    expect(dimensaoPorId('franqueado')).toBeNull()
    expect(dimensaoPorId('')).toBeNull()
  })
})

describe('entradaValida', () => {
  it('deixa passar recorte e unidade bem formados', () => {
    const recorte = { tipo: 'recorte', dimensao: 'master', valor: 'MARISE' } as const
    expect(entradaValida(recorte)).toBe(recorte)
    const unidade = { tipo: 'unidade', id: 'u-123' } as const
    expect(entradaValida(unidade)).toBe(unidade)
  })

  it('ausencia de entrada continua sendo panorama', () => {
    expect(entradaValida(null)).toBeNull()
  })

  it('valor em branco NAO vira recorte', () => {
    /* Sem isto a Executiva abriria filtrada por string vazia: uma carteira vazia que nao
       explica por que esta vazia, com "Limpar filtros" aceso sem filtro visivel. */
    expect(entradaValida({ tipo: 'recorte', dimensao: 'uf', valor: '' })).toBeNull()
    expect(entradaValida({ tipo: 'recorte', dimensao: 'uf', valor: '   ' })).toBeNull()
  })

  it('id de unidade em branco NAO abre ficha', () => {
    expect(entradaValida({ tipo: 'unidade', id: '' })).toBeNull()
    expect(entradaValida({ tipo: 'unidade', id: '  ' })).toBeNull()
  })

  it('deixa passar uf e endereco bem formados', () => {
    const uf = { tipo: 'uf', uf: 'PR' } as const
    expect(entradaValida(uf)).toBe(uf)
    const end = { tipo: 'endereco', texto: 'Av. Paulista 1000' } as const
    expect(entradaValida(end)).toBe(end)
  })

  it('uf ou endereco em branco NAO viram entrada', () => {
    // Sem isto o mapa abriria com `uf: ''` e o modo de ponto tentaria resolver vazio.
    expect(entradaValida({ tipo: 'uf', uf: '  ' })).toBeNull()
    expect(entradaValida({ tipo: 'endereco', texto: '   ' })).toBeNull()
  })

  it('dimensao desconhecida NAO vira recorte', () => {
    // Payload velho ou estado guardado de uma versao com outro vocabulario.
    const torta = { tipo: 'recorte', dimensao: 'regiao', valor: 'SUL' } as unknown as Parameters<
      typeof entradaValida
    >[0]
    expect(entradaValida(torta)).toBeNull()
  })
})

describe('entradaDaExecutiva', () => {
  it('deixa passar so o que a Visao Executiva sabe aplicar', () => {
    const recorte = { tipo: 'recorte', dimensao: 'uf', valor: 'PR' } as const
    expect(entradaDaExecutiva(recorte)).toBe(recorte)
    const unidade = { tipo: 'unidade', id: 'u-1' } as const
    expect(entradaDaExecutiva(unidade)).toBe(unidade)
  })

  it('entrada de EXPANSAO nunca chega a Executiva', () => {
    /* O estreitamento existe para o mesmo defeito nao ter duas portas: sem ele, um
       `{tipo:'uf'}` do card de regiao entraria no efeito de montagem da Executiva e
       cairia no ramo `else` do recorte — filtrando consultor por uma sigla de estado. */
    expect(entradaDaExecutiva({ tipo: 'uf', uf: 'PR' })).toBeNull()
    expect(entradaDaExecutiva({ tipo: 'endereco', texto: 'Av. Paulista' })).toBeNull()
    expect(entradaDaExecutiva(null)).toBeNull()
  })
})
