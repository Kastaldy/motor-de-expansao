import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError } from './api'
import {
  AJUDA_LEMBRAR,
  ehQuedaDeSessao,
  entradaDoPayload,
  mensagemDaFalha,
  podeEntrar,
} from './login'
import { assinarQuedaDeSessao, resetarEstadoDaSessao } from './sessao'

describe('podeEntrar', () => {
  it('exige conteúdo nos dois campos', () => {
    expect(podeEntrar('vinicius', 'segredo')).toBe(true)
    expect(podeEntrar('', 'segredo')).toBe(false)
    expect(podeEntrar('vinicius', '')).toBe(false)
  })

  it('login só de espaços não vale', () => {
    // O servidor normaliza com `strip()` antes de consultar: deixar o botão ativo
    // aqui gastaria uma tentativa da pessoa à toa.
    expect(podeEntrar('   ', 'segredo')).toBe(false)
  })

  it('não impõe política de senha na entrada', () => {
    // A política vale na CRIAÇÃO (`db/senhas.py::validar`). Aplicá-la aqui ensinaria o
    // formato da senha a quem tenta adivinhar, e recusaria senha legítima antiga.
    expect(podeEntrar('vinicius', 'a')).toBe(true)
  })
})

describe('entradaDoPayload', () => {
  it('lê o pedido de troca de senha', () => {
    expect(entradaDoPayload({ deve_trocar_senha: true })).toEqual({ deveTrocarSenha: true })
    expect(entradaDoPayload({ deve_trocar_senha: false })).toEqual({ deveTrocarSenha: false })
  })

  it('campo ausente ou de tipo errado NÃO abre a troca', () => {
    // "Não sei" não pode virar "abra a tela de troca": abrir sem necessidade trava a
    // pessoa logo depois de ela entrar.
    for (const bruto of [{}, null, 'sim', { deve_trocar_senha: 'true' }, { deve_trocar_senha: 1 }]) {
      expect(entradaDoPayload(bruto)).toEqual({ deveTrocarSenha: false })
    }
  })
})

describe('mensagemDaFalha', () => {
  it('401 não distingue usuário inexistente de senha errada', () => {
    // O servidor devolve a MESMA resposta nos dois casos, para não entregar a lista de
    // quem trabalha aqui. Distinguir na tela desfaria a defesa do lado de cá.
    expect(mensagemDaFalha(401)).toBe('Login ou senha incorretos.')
    expect(mensagemDaFalha(401, 'Usuário não encontrado.')).toBe('Login ou senha incorretos.')
  })

  it('404 explica que a entrada própria não está ligada', () => {
    expect(mensagemDaFalha(404)).toContain('não está ativada')
  })

  it('503 e 408 e rede têm recados próprios e acionáveis', () => {
    expect(mensagemDaFalha(503)).toContain('indisponível')
    expect(mensagemDaFalha(408)).toContain('demorou')
    expect(mensagemDaFalha(0)).toContain('servidor')
  })

  it('status desconhecido mostra o recado do servidor, quando há', () => {
    expect(mensagemDaFalha(422, 'Campo inválido.')).toBe('Campo inválido.')
    expect(mensagemDaFalha(422, '   ')).toBe('Não foi possível entrar. Tente de novo.')
    expect(mensagemDaFalha(500)).toBe('Não foi possível entrar. Tente de novo.')
  })

  it('nenhuma mensagem vaza se o usuário existe', () => {
    const todas = [401, 404, 503, 408, 0, 500].map((s) => mensagemDaFalha(s).toLowerCase())
    for (const m of todas) {
      expect(m).not.toContain('não existe')
      expect(m).not.toContain('inexistente')
      expect(m).not.toContain('não encontrado')
    }
  })
})

describe('ehQuedaDeSessao', () => {
  it('401 do LOGIN não é sessão caída', () => {
    // A armadilha que esta função existe para fechar: `lib/api.ts` anuncia queda de
    // sessão em todo 401, e o anúncio é de MÃO ÚNICA (`jaAnunciado` nunca volta atrás).
    // Sem esta exceção, errar a senha uma vez abriria "Sessão encerrada", travaria a
    // trava para o resto da carga e ofereceria como única saída recarregar a página.
    expect(ehQuedaDeSessao('/api/login')).toBe(false)
  })

  it('401 de qualquer outra rota continua sendo sessão caída', () => {
    // A exceção é CIRÚRGICA: tirar o anúncio das demais rotas devolveria o defeito que
    // o `AvisoSessao` foi criado para resolver — a pessoa via "está rodando na porta
    // 8899?" quando o que tinha acontecido era o login vencer.
    for (const url of ['/api/me', '/api/uf/SP', '/api/relatorio/pontual', '/api/logout']) {
      expect(ehQuedaDeSessao(url)).toBe(true)
    }
  })
})

/* ---------------------------------------------------------------------------
   A LIGAÇÃO, e não só a função.

   Os testes de `ehQuedaDeSessao` acima exercitam a função ISOLADA — e isso não
   prova nada sobre o comportamento real: tirar a chamada dela do `lib/api.ts`
   deixaria todos eles verdes. A garantia que importa é o caminho completo, e é
   ele que este bloco percorre, com o `fetch` falsificado.
   --------------------------------------------------------------------------- */
describe('401 do login não pode virar "Sessão encerrada"', () => {
  let avisos: number

  beforeEach(() => {
    resetarEstadoDaSessao()
    avisos = 0
    assinarQuedaDeSessao(() => {
      avisos += 1
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    resetarEstadoDaSessao()
  })

  function responder401() {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: false,
        status: 401,
        type: 'basic',
        json: async () => ({ detail: 'Login ou senha incorretos.' }),
      })),
    )
  }

  it('senha errada NÃO anuncia queda de sessão', async () => {
    responder401()
    await expect(api.entrar('vinicius', 'errada')).rejects.toBeInstanceOf(ApiError)
    expect(avisos).toBe(0)
  })

  it('e a trava de mão única NÃO é acionada — dá para tentar de novo', async () => {
    // `jaAnunciado` em `lib/sessao.ts` nunca volta atrás. Se a primeira senha errada
    // acionasse a trava, a segunda tentativa já nasceria dentro do pop-up de sessão,
    // com "recarregar a página" como única saída. É o vaivém que este teste impede.
    responder401()
    await expect(api.entrar('vinicius', 'errada')).rejects.toBeInstanceOf(ApiError)
    await expect(api.entrar('vinicius', 'errada2')).rejects.toBeInstanceOf(ApiError)
    expect(avisos).toBe(0)
  })

  it('mas 401 de OUTRA rota continua anunciando', async () => {
    // A exceção é cirúrgica. Sem esta metade, "silenciar o 401 do login" poderia virar
    // "silenciar todo 401" sem nenhum teste reclamar — e voltaria o defeito que o
    // `AvisoSessao` existe para resolver.
    responder401()
    await expect(api.me()).rejects.toBeInstanceOf(ApiError)
    expect(avisos).toBe(1)
  })
})

describe('AJUDA_LEMBRAR', () => {
  it('diz o que a caixinha faz E o que ela não faz', () => {
    // Decisão 2, opção (a) — FIEL: mantém ao fechar o navegador e NÃO estica o prazo.
    // Prometer "continue conectado" sem o limite faria quem fecha o navegador voltar
    // deslogado no dia seguinte sem entender por quê.
    expect(AJUDA_LEMBRAR).toContain('fechar o navegador')
    expect(AJUDA_LEMBRAR).toContain('8 horas')
  })
})
