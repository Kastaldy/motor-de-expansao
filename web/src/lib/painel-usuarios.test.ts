import { describe, expect, it } from 'vitest'

import {
  alternarMaster,
  chaveMaster,
  COLUNA_SENHA,
  DICA_CAMPO_MASTER,
  dicaDoFormulario,
  faltaMaster,
  mastersDaCriacao,
  recadoDaAlteracao,
  ROTULO_CAMPO_MASTER,
  SEM_MASTERS_NO_CADASTRO,
  selecaoInicialDeMasters,
  TITULO_MASTER_FORA_DO_CADASTRO,
  loginProprioDoPayload,
  mensagemDeErroDoPainel,
  recadoDaCriacao,
  rodapeDoPainel,
  textoCorrido,
  tituloDoBotaoCriar,
  tituloDoSeloDaSenha,
} from './painel-usuarios'

/* Os textos da administração de usuários que dependem do login próprio (decisão do dono,
   24/10/2026). Até essa data a tela falava como se a chave já estivesse ligada; com ela
   DESLIGADA — o estado de produção até o corte do P19 — o recado de criação, o rodapé e o
   recado de 503 diziam coisas falsas. Cada bloco abaixo guarda uma delas nos DOIS estados.

   DESDE 16/11/2026 (Estágio 3 da DEC-081) o Authelia não existe mais, e nenhum texto pode
   mandar cadastrar alguém nele — nem como caminho de volta do corte. */

const TODOS_OS_TEXTOS = (ligado: boolean): string[] => [
  tituloDoSeloDaSenha(true, ligado),
  tituloDoSeloDaSenha(false, ligado),
  recadoDaCriacao('ana', ligado).titulo,
  recadoDaCriacao('ana', ligado).corpo,
  dicaDoFormulario(ligado),
  tituloDoBotaoCriar(ligado),
  textoCorrido(rodapeDoPainel(ligado)),
]

describe('nenhum texto cita o Authelia aposentado', () => {
  it('nos dois estados da chave', () => {
    for (const ligado of [true, false]) {
      for (const texto of TODOS_OS_TEXTOS(ligado)) {
        expect(texto).not.toMatch(/authelia|users_database|rollback/i)
      }
    }
  })
})

describe('ler a chave do payload', () => {
  it('só `true` de verdade liga; o resto conta como desligado, o lado conservador', () => {
    expect(loginProprioDoPayload({ login_proprio: true })).toBe(true)
    const ruins = [
      null,
      undefined,
      1,
      'sim',
      {},
      { login_proprio: 'true' },
      { login_proprio: 1 },
      { login_proprio: false },
    ]
    for (const ruim of ruins) expect(loginProprioDoPayload(ruim)).toBe(false)
  })
})

describe('a coluna e o selo falam da senha do BANCO', () => {
  it('a coluna se chama "Senha (banco)"', () => {
    expect(COLUNA_SENHA).toBe('Senha (banco)')
  })

  it('a dica diz que é a senha do banco nos quatro casos', () => {
    for (const propria of [true, false]) {
      for (const ligado of [true, false]) {
        expect(tituloDoSeloDaSenha(propria, ligado)).toContain('senha do banco')
      }
    }
  })

  it('desligado, a dica avisa que ela ainda não é usada para entrar', () => {
    const dica = tituloDoSeloDaSenha(false, false)
    expect(dica).toContain('ainda não é usada para entrar')
    expect(dica).toContain('desligado neste servidor')
  })

  it('ligado, a dica diz que é ela que o piloto confere', () => {
    const dica = tituloDoSeloDaSenha(true, true)
    expect(dica).toContain('confere na entrada')
    expect(dica).not.toContain('Authelia')
  })

  it('a dica distingue quem já definiu de quem está na inicial', () => {
    expect(tituloDoSeloDaSenha(true, true)).toContain('Já definiu')
    expect(tituloDoSeloDaSenha(false, true)).toContain('senha inicial do banco')
  })
})

describe('o recado depois de criar', () => {
  it('desligado: a pessoa ainda não entra, até o login próprio ser ligado', () => {
    const r = recadoDaCriacao('ana', false)
    expect(r.titulo).toBe('ana foi criado no banco, mas ainda não consegue entrar.')
    expect(r.corpo).toContain('login próprio está desligado')
    // A frase que era falsa com a chave desligada não pode voltar.
    expect(r.corpo).not.toContain('levada a trocá-la')
  })

  it('ligado: a frase da senha inicial volta a valer, IDÊNTICA à da decisão do dono', () => {
    const r = recadoDaCriacao('ana', true)
    expect(r.titulo).toBe('ana foi criado e já pode entrar.')
    expect(r.corpo).toContain(
      'A senha inicial é a compartilhada do piloto, e a pessoa será levada a trocá-la no ' +
        'primeiro acesso.',
    )
    // Até 16/11/2026 o recado pedia também o cadastro no Authelia, pelo rollback; saiu.
    expect(r.corpo).toBe(
      'A senha inicial é a compartilhada do piloto, e a pessoa será levada a trocá-la no ' +
        'primeiro acesso.',
    )
  })
})

describe('o formulário de criação', () => {
  it('desligado, não promete troca no primeiro acesso', () => {
    expect(dicaDoFormulario(false)).not.toContain('primeiro acesso')
    expect(dicaDoFormulario(false)).toContain('login próprio desligado')
    expect(tituloDoBotaoCriar(false)).toContain('login próprio precisa estar ligado')
  })

  it('ligado, diz que a pessoa troca a inicial no primeiro acesso', () => {
    expect(dicaDoFormulario(true)).toContain('primeiro acesso')
    expect(tituloDoBotaoCriar(true)).toContain('senha inicial')
  })
})

describe('o rodapé', () => {
  const desligado = textoCorrido(rodapeDoPainel(false))
  const ligado = textoCorrido(rodapeDoPainel(true))

  it('nunca diz que Redefinir OBRIGA a criar senha nova — a troca é oferecida', () => {
    /* A frase antiga ("obriga a criar uma senha nova na entrada") era falsa nos dois
       estados: desde 25/09/2026 a troca é recomendada, não obrigatória. */
    for (const texto of [desligado, ligado]) expect(texto).not.toContain('obriga a criar')
    expect(ligado).toContain('oferece, não obriga')
  })

  it('desligado: explica por que os gestos de senha não aparecem', () => {
    expect(desligado).toContain('só aparecem com o login próprio ligado')
    expect(desligado).toContain('desligado neste servidor')
    expect(desligado).not.toContain('gera uma senha temporária')
  })

  it('ligado: descreve o Redefinir', () => {
    expect(ligado).toContain('gera uma senha temporária')
  })

  it('a coluna aparece com o mesmo nome do cabeçalho, em destaque', () => {
    for (const estado of [false, true]) {
      expect(rodapeDoPainel(estado)).toContainEqual({ forte: COLUNA_SENHA })
    }
  })
})

describe('o recado de erro do painel', () => {
  it('503 NUNCA afirma que nada foi alterado', () => {
    for (const escrita of [false, true]) {
      for (const texto of ['Banco indisponível: PoolTimeout', '503', '']) {
        expect(mensagemDeErroDoPainel(503, texto, { escrita })).not.toContain('nada foi alterado')
      }
    }
  })

  it('503 numa escrita manda conferir a lista antes de repetir', () => {
    const m = mensagemDeErroDoPainel(503, 'Banco indisponível: PoolTimeout', { escrita: true })
    expect(m).toContain('Banco indisponível: PoolTimeout.')
    expect(m).toContain('recarregue a lista')
  })

  it('503 numa leitura é o texto do servidor, com ponto final', () => {
    expect(mensagemDeErroDoPainel(503, 'Banco indisponível: X')).toBe('Banco indisponível: X.')
    expect(mensagemDeErroDoPainel(503, 'Sem banco configurado.')).toBe('Sem banco configurado.')
    expect(mensagemDeErroDoPainel(503, '503')).toBe('O cadastro de usuários está indisponível agora.')
  })

  it('404 com o "Not Found" cru é a allowlist do painel', () => {
    expect(mensagemDeErroDoPainel(404, 'Not Found')).toBe(
      'O painel de acessos não está habilitado para este usuário.',
    )
  })

  it('404 com texto do servidor é OUTRA recusa, e o texto dele vale', () => {
    /* O login próprio desligado nos gestos de senha, ou gente que não existe. Até 24/10/2026
       todo 404 virava "painel não habilitado" — dito a quem administra o painel. */
    const recusa =
      'Redefinir senha e exigir troca só funcionam com o login próprio do piloto ligado.'
    expect(mensagemDeErroDoPainel(404, recusa)).toBe(recusa)
    expect(mensagemDeErroDoPainel(404, 'usuário 9 não existe')).toBe('usuário 9 não existe')
  })

  it('outros status: o texto do servidor, ou o status quando não há texto', () => {
    expect(mensagemDeErroDoPainel(409, 'Login em uso.')).toBe('Login em uso.')
    expect(mensagemDeErroDoPainel(500, '500')).toBe('O servidor recusou o pedido (500).')
  })
})

describe('o campo Master franquia (emenda 1 da DEC-087)', () => {
  const cadastro = ['Dalmo Ribeiro', 'Luana Ribeiro', 'Zé Master']

  it('a chave é a do servidor: sem caixa, sem espaço nas pontas, espaços internos colapsados', () => {
    expect(chaveMaster('  dalmo   RIBEIRO ')).toBe('dalmo ribeiro')
    expect(chaveMaster('Dalmo Ribeiro')).toBe(chaveMaster('dalmo ribeiro'))
  })

  it('a edição abre com a grafia do cadastro, e separa o que o cadastro não tem mais', () => {
    expect(selecaoInicialDeMasters(['dalmo ribeiro', 'Master Antigo'], cadastro)).toEqual({
      selecionados: ['Dalmo Ribeiro'],
      foraDoCadastro: ['Master Antigo'],
    })
    expect(selecaoInicialDeMasters([], cadastro)).toEqual({ selecionados: [], foraDoCadastro: [] })
  })

  it('sem cadastro no servidor, nenhum nome é dado como fora dele (mesma regra do chip)', () => {
    // O cadastro indisponível não é o nome que saiu: a edição não pode dizer "sai ao salvar".
    expect(selecaoInicialDeMasters(['Dalmo Ribeiro'], [])).toEqual({
      selecionados: [],
      foraDoCadastro: [],
    })
  })

  it('marcar e desmarcar mantém a ordem do cadastro', () => {
    expect(alternarMaster([], 'Zé Master', cadastro)).toEqual(['Zé Master'])
    expect(alternarMaster(['Zé Master'], 'Dalmo Ribeiro', cadastro)).toEqual([
      'Dalmo Ribeiro',
      'Zé Master',
    ])
    expect(alternarMaster(['Dalmo Ribeiro', 'Zé Master'], 'Dalmo Ribeiro', cadastro)).toEqual([
      'Zé Master',
    ])
  })

  it('só o perfil Master exige master, e só ele o manda na criação', () => {
    expect(faltaMaster('master', [])).toBe(true)
    expect(faltaMaster('master', ['Dalmo Ribeiro'])).toBe(false)
    expect(faltaMaster('consultoria', [])).toBe(false)
    expect(mastersDaCriacao('master', ['Dalmo Ribeiro'])).toEqual(['Dalmo Ribeiro'])
    expect(mastersDaCriacao('consultoria', ['Dalmo Ribeiro'])).toBeUndefined()
  })

  it('os textos do campo são curtos, em português, e citam a Visão Executiva', () => {
    expect(ROTULO_CAMPO_MASTER).toBe('Master franquia')
    expect(DICA_CAMPO_MASTER).toContain('ao menos um')
    expect(DICA_CAMPO_MASTER).toContain('Visão Executiva')
    expect(SEM_MASTERS_NO_CADASTRO).toContain('cadastro de unidades')
    expect(TITULO_MASTER_FORA_DO_CADASTRO).toContain('não vê nenhuma unidade')
  })
})

describe('o recado depois de uma alteração', () => {
  const rot = (p: string) => ({ master: 'Master', consultoria: 'Consultoria' })[p] ?? p

  it('virar Master diz o perfil e o master na mesma frase', () => {
    expect(
      recadoDaAlteracao(
        'luana',
        {
          perfil: { de: 'consultoria', para: 'master', mudou: true },
          masters: { para: ['Dalmo Ribeiro'], mudou: true },
        },
        rot,
      ),
    ).toBe('luana: Consultoria → Master, com master franquia Dalmo Ribeiro.')
  })

  it('sair de Master diz que o vínculo saiu', () => {
    expect(
      recadoDaAlteracao(
        'luana',
        {
          perfil: { de: 'master', para: 'consultoria', mudou: true },
          masters: { para: [], mudou: true },
        },
        rot,
      ),
    ).toBe('luana: Master → Consultoria; vínculo com master franquia removido.')
  })

  it('trocar só o master', () => {
    expect(
      recadoDaAlteracao('dalmo', { masters: { para: ['Dalmo Ribeiro', 'Luana Ribeiro'], mudou: true } }, rot),
    ).toBe('dalmo: master franquia agora Dalmo Ribeiro, Luana Ribeiro.')
  })

  it('os avisos (DEC-090): os marcados pelo rótulo, e nenhum quando desmarca tudo', () => {
    const rotuloDoAviso = (a: string) => (a === 'imovel_master' ? 'Imóvel pedido por um master' : a)
    expect(
      recadoDaAlteracao('priscila', { avisos: { para: ['imovel_master'], mudou: true } }, rot, rotuloDoAviso),
    ).toBe('priscila: avisos agora Imóvel pedido por um master.')
    expect(recadoDaAlteracao('priscila', { avisos: { para: [], mudou: true } }, rot)).toBe(
      'priscila: nenhum aviso marcado (ficam só os do perfil).',
    )
  })

  it('os recados de antes continuam iguais', () => {
    expect(
      recadoDaAlteracao('ana', { perfil: { de: 'consultoria', para: 'master', mudou: true } }, rot),
    ).toBe('ana: Consultoria → Master.')
    expect(recadoDaAlteracao('ana', { status: { ativo: false, mudou: true } }, rot)).toBe(
      'ana foi desativado.',
    )
    expect(recadoDaAlteracao('ana', { paises: { para: ['AR', 'BR'], mudou: true } }, rot)).toBe(
      'ana: países agora AR, BR.',
    )
  })

  it('mudou: false nunca vira alteração', () => {
    expect(recadoDaAlteracao('ana', { masters: { para: ['Dalmo Ribeiro'], mudou: false } }, rot)).toBe(
      'ana já estava assim — nada foi alterado.',
    )
  })
})
