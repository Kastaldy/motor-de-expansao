import { describe, expect, it } from 'vitest'

import {
  loginConfere,
  montarConfirmacao,
  PERFIL_ADMINISTRADOR,
  relacaoEntrePerfis,
  rotuloPerfil,
} from './confirmacao-admin'

/* O pop-up de confirmação existe para a pessoa LER antes de mudar o acesso de alguém.
   O que se guarda aqui é o texto: que ele nomeia quem e o quê, que não afirma direção
   quando não há direção, e que o atrito extra aparece exatamente onde foi decidido —
   na concessão de poder de administrador, e em nenhum outro lugar. */

describe('a hierarquia da D22 e uma ordem PARCIAL', () => {
  it('reconhece a escada Expansao -> Lideres -> Growth', () => {
    expect(relacaoEntrePerfis('expansao', 'lideres')).toBe('sobe')
    expect(relacaoEntrePerfis('expansao', 'growth')).toBe('sobe')
    expect(relacaoEntrePerfis('lideres', 'growth')).toBe('sobe')
    expect(relacaoEntrePerfis('growth', 'lideres')).toBe('desce')
    expect(relacaoEntrePerfis('lideres', 'expansao')).toBe('desce')
  })

  it('Consultoria tambem esta dentro de Lideres', () => {
    expect(relacaoEntrePerfis('consultoria', 'lideres')).toBe('sobe')
    expect(relacaoEntrePerfis('lideres', 'consultoria')).toBe('desce')
  })

  it('Expansao e Consultoria sao INCOMPARAVEIS — nem sobe, nem desce', () => {
    /* Este e o caso que a contagem de capacidades erraria. Expansao tem 11 e
       Consultoria tem 2, entao comparar numeros diria "rebaixamento" — e nao e:
       Consultoria abre a Visao Executiva, que Expansao nao tem. Sao areas
       diferentes, e a frase precisa dizer isso em vez de inventar direcao. */
    expect(relacaoEntrePerfis('expansao', 'consultoria')).toBe('muda-de-area')
    expect(relacaoEntrePerfis('consultoria', 'expansao')).toBe('muda-de-area')
  })

  it('perfil igual nao e mudanca', () => {
    expect(relacaoEntrePerfis('growth', 'growth')).toBe('igual')
  })

  it('perfil que o seed nao conhece nao ganha direcao por chute', () => {
    expect(relacaoEntrePerfis('expansao', 'juridico')).toBe('desconhecida')
    expect(relacaoEntrePerfis('juridico', 'growth')).toBe('desconhecida')
  })
})

describe('rotulo de perfil', () => {
  it('usa o nome acentuado de produto', () => {
    expect(rotuloPerfil('expansao')).toBe('Expansão')
    expect(rotuloPerfil('lideres')).toBe('Líderes')
  })

  it('cai na descricao do banco antes de imprimir o slug cru', () => {
    /* CLAUDE.md §2: texto de usuario e acentuado, identificador nunca. Um quinto
       perfil sairia como `juridico` na tela sem este fallback. */
    expect(rotuloPerfil('juridico', { juridico: 'Jurídico' })).toBe('Jurídico')
    expect(rotuloPerfil('juridico')).toBe('juridico')
  })
})

describe('trocar perfil', () => {
  const base = { tipo: 'trocar-perfil' as const, nome: 'Ana Ribeiro', login: 'ana.ribeiro' }

  it('o titulo diz QUEM e o DE-PARA, nunca "confirmar alteracao"', () => {
    const c = montarConfirmacao({ ...base, de: 'expansao', para: 'lideres' })
    expect(c.titulo).toBe('Ana Ribeiro vai passar de Expansão para Líderes')
    expect(c.titulo.toLowerCase()).not.toContain('confirmar')
  })

  it('subir diz que GANHA; descer diz que PERDE', () => {
    expect(montarConfirmacao({ ...base, de: 'expansao', para: 'lideres' }).apoio.join(' ')).toContain(
      'ganha',
    )
    expect(montarConfirmacao({ ...base, de: 'growth', para: 'expansao' }).apoio.join(' ')).toContain(
      'Perde',
    )
  })

  it('mudar de AREA nao e descrito como perda', () => {
    const c = montarConfirmacao({ ...base, de: 'expansao', para: 'consultoria' })
    const texto = c.apoio.join(' ')
    expect(texto).toContain('Troca de área')
    expect(texto).toContain('não é promoção nem rebaixamento')
    expect(texto).not.toContain('Perde')
  })

  it('leva a contagem de capacidades que veio do payload, quando ela vem', () => {
    /* O numero entre parenteses ja aparece no seletor da tela e no rodape. Se o
       pop-up dissesse outro numero, seriam duas verdades sobre a mesma coisa. */
    const c = montarConfirmacao({
      ...base,
      de: 'expansao',
      para: 'growth',
      capacidadesDe: 11,
      capacidadesPara: 15,
    })
    expect(c.apoio.join(' ')).toContain('11 → 15 capacidades')
  })

  it('sem os numeros no payload, nao inventa contagem', () => {
    const c = montarConfirmacao({ ...base, de: 'expansao', para: 'lideres' })
    expect(c.apoio.join(' ')).not.toContain('capacidades')
  })
})

describe('o atrito extra so aparece onde foi decidido', () => {
  const base = { tipo: 'trocar-perfil' as const, nome: 'Ana Ribeiro', login: 'ana.ribeiro' }

  it('PROMOVER a Growth exige digitar o login', () => {
    const c = montarConfirmacao({ ...base, de: 'expansao', para: PERFIL_ADMINISTRADOR })
    expect(c.loginParaDigitar).toBe('ana.ribeiro')
    expect(c.gravidade).toBe('alta')
    expect(c.eyebrow).toBe('Conceder poder de administrador')
  })

  it('CRIAR alguem ja como Growth exige o mesmo — e a mesma porta', () => {
    /* Nascer Growth concede exatamente o poder que promover a Growth concede.
       Exigir atrito num caminho e nao no outro deixaria a porta aberta do lado
       que ninguem olha. */
    const c = montarConfirmacao({
      tipo: 'criar',
      nome: 'Ana Ribeiro',
      login: 'ana.ribeiro',
      email: 'ana@ultraacademia.com.br',
      perfil: PERFIL_ADMINISTRADOR,
    })
    expect(c.loginParaDigitar).toBe('ana.ribeiro')
    expect(c.gravidade).toBe('alta')
  })

  it('REBAIXAR de Growth NAO exige digitar', () => {
    /* O modo de falha e o oposto: tirar acesso e reversivel na mesma tela, e o
       atrito ali so' atrapalharia quem esta consertando um engano. */
    const c = montarConfirmacao({ ...base, de: PERFIL_ADMINISTRADOR, para: 'expansao' })
    expect(c.loginParaDigitar).toBeNull()
  })

  it('nenhuma outra troca exige digitar', () => {
    for (const [de, para] of [
      ['expansao', 'lideres'],
      ['consultoria', 'lideres'],
      ['lideres', 'expansao'],
      ['expansao', 'consultoria'],
    ]) {
      expect(montarConfirmacao({ ...base, de, para }).loginParaDigitar).toBeNull()
    }
  })

  it('desativar e reativar nao exigem digitar', () => {
    const alvo = { nome: 'Ana Ribeiro', login: 'ana.ribeiro', perfil: 'expansao' }
    expect(
      montarConfirmacao({ tipo: 'definir-ativo', ...alvo, ativo: false }).loginParaDigitar,
    ).toBeNull()
    expect(
      montarConfirmacao({ tipo: 'definir-ativo', ...alvo, ativo: true }).loginParaDigitar,
    ).toBeNull()
  })
})

describe('a conferencia do login digitado', () => {
  it('aceita o login exato, e apara so as bordas', () => {
    expect(loginConfere('ana.ribeiro', 'ana.ribeiro')).toBe(true)
    expect(loginConfere('  ana.ribeiro  ', 'ana.ribeiro')).toBe(true)
  })

  it('recusa caixa diferente — o atrito existe para exigir atencao', () => {
    expect(loginConfere('ANA.RIBEIRO', 'ana.ribeiro')).toBe(false)
    expect(loginConfere('Ana.Ribeiro', 'ana.ribeiro')).toBe(false)
  })

  it('recusa parcial, vazio e parecido', () => {
    expect(loginConfere('', 'ana.ribeiro')).toBe(false)
    expect(loginConfere('ana', 'ana.ribeiro')).toBe(false)
    expect(loginConfere('ana.ribeir', 'ana.ribeiro')).toBe(false)
    expect(loginConfere('ana ribeiro', 'ana.ribeiro')).toBe(false)
  })
})

describe('desativar e reativar', () => {
  const alvo = { tipo: 'definir-ativo' as const, nome: 'Carla Teste', login: 'carla.teste', perfil: 'lideres' }

  it('desativar diz que NADA e apagado, porque e soft delete (D9/D23)', () => {
    const c = montarConfirmacao({ ...alvo, ativo: false })
    expect(c.titulo).toBe('Carla Teste perde o acesso ao piloto agora')
    const texto = c.apoio.join(' ')
    expect(texto).toContain('Nada é apagado')
    expect(texto).toContain('reativa aqui mesmo')
    expect(c.gravidade).toBe('alta')
  })

  it('desativar avisa que o login volta a ficar livre', () => {
    /* O indice unico e PARCIAL (`WHERE ativo`), entao desativar libera o login
       para outro cadastro — consequencia real que a tela nao dizia. */
    expect(montarConfirmacao({ ...alvo, ativo: false }).apoio.join(' ')).toContain(
      'volta a ficar livre',
    )
  })

  it('reativar e o caminho leve, e diz com que perfil a pessoa volta', () => {
    const c = montarConfirmacao({ ...alvo, ativo: true })
    expect(c.titulo).toBe('Carla Teste volta a entrar no piloto')
    expect(c.gravidade).toBe('media')
    expect(c.apoio.join(' ')).toContain('Líderes')
  })
})

describe('criar', () => {
  const novo = {
    tipo: 'criar' as const,
    nome: 'Ana Ribeiro',
    login: 'ana.ribeiro',
    email: 'ana@ultraacademia.com.br',
    perfil: 'expansao',
  }

  it('mostra os quatro campos que vao para o banco', () => {
    const c = montarConfirmacao(novo)
    expect(c.titulo).toBe('Criar Ana Ribeiro como Expansão')
    const texto = c.apoio.join(' ')
    expect(texto).toContain('ana.ribeiro')
    expect(texto).toContain('ana@ultraacademia.com.br')
  })

  it('avisa da senha inicial e do passo do Authelia', () => {
    /* Sao as duas coisas que a pessoa nao adivinha: que a senha nasce
       compartilhada, e que criar aqui NAO deixa ninguem entrar. */
    const texto = montarConfirmacao(novo).apoio.join(' ')
    expect(texto).toContain('senha inicial compartilhada')
    expect(texto).toContain('Authelia')
  })

  it('avisa que criar nao se desfaz por esta tela', () => {
    expect(montarConfirmacao(novo).apoio.join(' ')).toContain('desativar')
  })
})

describe('o botao nunca diz so "Confirmar"', () => {
  it('todo rotulo de confirmacao repete a acao e o nome', () => {
    const casos = [
      montarConfirmacao({
        tipo: 'criar',
        nome: 'Ana',
        login: 'ana',
        email: 'a@u.com',
        perfil: 'expansao',
      }),
      montarConfirmacao({
        tipo: 'trocar-perfil',
        nome: 'Ana',
        login: 'ana',
        de: 'expansao',
        para: 'lideres',
      }),
      montarConfirmacao({
        tipo: 'definir-ativo',
        nome: 'Ana',
        login: 'ana',
        perfil: 'expansao',
        ativo: false,
      }),
      montarConfirmacao({ tipo: 'redefinir-senha', nome: 'Ana', login: 'ana', senhaPropria: true }),
      montarConfirmacao({ tipo: 'exigir-troca', nome: 'Ana', login: 'ana' }),
    ]
    for (const c of casos) {
      expect(c.rotuloConfirmar).toContain('Ana')
      expect(c.rotuloConfirmar).not.toBe('Confirmar')
      expect(c.titulo.length).toBeGreaterThan(12)
      expect(c.apoio.length).toBeGreaterThan(0)
    }
  })
})

describe('redefinir a senha de alguem (15/09)', () => {
  const alvo = { tipo: 'redefinir-senha' as const, nome: 'Bruno Teste', login: 'bruno.teste' }

  it('quando apaga uma senha escolhida, diz isso e pinta de perigo', () => {
    const c = montarConfirmacao({ ...alvo, senhaPropria: true })
    expect(c.titulo).toBe('Bruno Teste volta para a senha inicial')
    expect(c.apoio.join(' ')).toContain('deixa de valer agora')
    expect(c.gravidade).toBe('alta')
  })

  it('quando a pessoa nunca definiu senha, e o caminho leve', () => {
    const c = montarConfirmacao({ ...alvo, senhaPropria: false })
    expect(c.apoio.join(' ')).toContain('ainda não tinha definido')
    expect(c.gravidade).toBe('media')
  })

  it('deixa claro que o admin nao passa a conhecer a senha de ninguem', () => {
    const texto = montarConfirmacao({ ...alvo, senhaPropria: true }).apoio.join(' ')
    expect(texto).toContain('não passa a conhecer a senha de ninguém')
    expect(texto).toContain('senha inicial')
  })

  it('nao promete o que ainda nao vale: o Authelia segue autenticando', () => {
    expect(montarConfirmacao({ ...alvo, senhaPropria: true }).apoio.join(' ')).toContain(
      'Authelia',
    )
  })

  it('nao exige digitar o login — esse atrito e so para conceder poder de administrador', () => {
    expect(montarConfirmacao({ ...alvo, senhaPropria: true }).loginParaDigitar).toBeNull()
  })
})

describe('exigir nova senha (15/09)', () => {
  const alvo = { tipo: 'exigir-troca' as const, nome: 'Bruno Teste', login: 'bruno.teste' }

  it('diz que a senha atual continua valendo ate a troca', () => {
    const c = montarConfirmacao(alvo)
    expect(c.titulo).toBe('Bruno Teste vai ter de trocar a senha')
    expect(c.apoio.join(' ')).toContain('continua valendo')
    expect(c.gravidade).toBe('media')
    expect(c.loginParaDigitar).toBeNull()
  })
})
