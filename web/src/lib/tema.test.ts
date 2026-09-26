import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import {
  CHAVE_TEMA,
  CHAVE_TEMA_LEGADA,
  COOKIE_TEMA,
  TEMA_PADRAO,
  type DepositoDeCookie,
  type DepositoDeTema,
  dominioCompartilhado,
  ehTema,
  gravarTema,
  lerTema,
  lerTemaDoCookie,
  montarCookieDeTema,
  outroTema,
} from './tema'

/** Depósito de mentira: um objeto, e opcionalmente um que estoura como o de aba anônima. */
function deposito(inicial: Record<string, string> = {}, explode = false): DepositoDeTema {
  return {
    getItem: (c) => {
      if (explode) throw new DOMException('bloqueado', 'SecurityError')
      return inicial[c] ?? null
    },
    setItem: (c, v) => {
      if (explode) throw new DOMException('bloqueado', 'SecurityError')
      inicial[c] = v
    },
  }
}

/**
 * Pote de cookies de mentira, com a parte da semântica do navegador que importa aqui.
 *
 * O que ele precisa imitar é o DESCARTE SILENCIOSO: pedir `Domain` que o navegador não
 * aceita — sufixo público, domínio que não é sufixo do host — não levanta e não devolve
 * nada, o cookie simplesmente não existe depois. `sufixosPublicos` é o bastante para
 * exercitar esse ramo; não pretende ser a lista real.
 */
function pote(opcoes: { host: string; jar?: Record<string, string>; sufixosPublicos?: string[] }) {
  const jar = opcoes.jar ?? {}
  const publicos = opcoes.sufixosPublicos ?? ['tech', 'com', 'com.br', 'co.uk']
  return {
    jar,
    deposito: {
      ler: () =>
        Object.entries(jar)
          .map(([n, v]) => `${n}=${v}`)
          .join('; '),
      escrever: (cookie: string) => {
        const [par, ...attrs] = cookie.split(';').map((s) => s.trim())
        const corte = par.indexOf('=')
        const nome = par.slice(0, corte)
        const valor = par.slice(corte + 1)
        const dominio = attrs
          .map((a) => /^Domain=(.+)$/i.exec(a)?.[1])
          .find((d): d is string => Boolean(d))
        if (dominio) {
          const aceita =
            !publicos.includes(dominio) &&
            (opcoes.host === dominio || opcoes.host.endsWith(`.${dominio}`))
          if (!aceita) return /* descartado, sem erro — é o comportamento do navegador */
        }
        jar[nome] = valor
      },
      hospedeiro: () => opcoes.host,
    } satisfies DepositoDeCookie,
  }
}

describe('tema', () => {
  it('sem escolha guardada, entra no tema do produto', () => {
    expect(lerTema(deposito())).toBe(TEMA_PADRAO)
    expect(TEMA_PADRAO).toBe('escuro')
  })

  it('lê de volta o que gravou', () => {
    const d = deposito()
    gravarTema('claro', d)
    expect(lerTema(d)).toBe('claro')
    gravarTema('escuro', d)
    expect(lerTema(d)).toBe('escuro')
  })

  it('quem escolheu o claro na Executiva não volta ao escuro quando a chave muda de nome', () => {
    // A preferência morava em `motor.exec.tema` enquanto o tema era só daquela aba. Sem a
    // leitura da chave antiga, o dia do deploy leria como "o botão parou de funcionar".
    expect(lerTema(deposito({ [CHAVE_TEMA_LEGADA]: 'claro' }))).toBe('claro')
    expect(lerTema(deposito({ [CHAVE_TEMA_LEGADA]: 'escuro' }))).toBe('escuro')
  })

  it('a chave nova VENCE a antiga, e é a única em que se grava', () => {
    // Senão a escolha migrada seria imutável: gravar 'escuro' na chave nova não teria
    // efeito nenhum enquanto a antiga continuasse dizendo 'claro'.
    const d = deposito({ [CHAVE_TEMA_LEGADA]: 'claro' })
    gravarTema('escuro', d)
    expect(lerTema(d)).toBe('escuro')
  })

  it('lixo na chave antiga também cai no padrão', () => {
    expect(lerTema(deposito({ [CHAVE_TEMA_LEGADA]: 'light' }))).toBe(TEMA_PADRAO)
  })

  it('valor estragado cai no padrão, não vira data-tema inválido', () => {
    // `data-tema="dark"` não casa com nenhum seletor: a tela ficaria escura e o botão
    // passaria a alternar a partir de um estado que ninguém escolheu.
    expect(lerTema(deposito({ [CHAVE_TEMA]: 'dark' }))).toBe(TEMA_PADRAO)
    expect(lerTema(deposito({ [CHAVE_TEMA]: '' }))).toBe(TEMA_PADRAO)
  })

  it('depósito ausente ou bloqueado não derruba a aba', () => {
    // Em janela anônima com cookies de terceiros bloqueados, TOCAR no localStorage já
    // levanta SecurityError. Perder a preferência é aceitável; perder a tela não é.
    expect(lerTema(null)).toBe(TEMA_PADRAO)
    expect(lerTema(undefined)).toBe(TEMA_PADRAO)
    expect(lerTema(deposito({}, true))).toBe(TEMA_PADRAO)
    expect(() => gravarTema('claro', deposito({}, true))).not.toThrow()
    expect(() => gravarTema('claro', null)).not.toThrow()
  })

  it('outroTema é involução: ida e volta devolve o mesmo', () => {
    expect(outroTema('escuro')).toBe('claro')
    expect(outroTema('claro')).toBe('escuro')
    expect(outroTema(outroTema('claro'))).toBe('claro')
  })

  it('ehTema só reconhece os dois nomes do projeto', () => {
    expect(ehTema('claro')).toBe(true)
    expect(ehTema('escuro')).toBe(true)
    expect(ehTema('light')).toBe(false)
    expect(ehTema(null)).toBe(false)
    expect(ehTema(undefined)).toBe(false)
  })
})

describe('o tema atravessa subdomínios (tela de entrar)', () => {
  it('o claro escolhido no piloto chega na tela de entrar, que é OUTRA ORIGEM', () => {
    /* O defeito de 2026-09-25, encenado. Duas origens do mesmo domínio: cada uma com o SEU
       `localStorage` e as duas com UM pote de cookies — que é como o navegador se comporta.
       Antes da correção a tela de entrar lia apenas o `localStorage` de `auth.`, sempre
       vazio, e nascia escura para quem havia pedido claro no piloto. */
    const jar: Record<string, string> = {}
    const piloto = pote({ host: 'piloto.ultra-expansao.tech', jar })
    const entrar = pote({ host: 'auth.ultra-expansao.tech', jar })
    const lsPiloto = deposito()
    const lsEntrar = deposito() // origem diferente: NUNCA vê o que o piloto gravou

    gravarTema('claro', lsPiloto, piloto.deposito)

    expect(lerTema(lsEntrar, entrar.deposito)).toBe('claro')
    // E a volta também: trocar para escuro no piloto tem de alcançar a tela de entrar.
    gravarTema('escuro', lsPiloto, piloto.deposito)
    expect(lerTema(lsEntrar, entrar.deposito)).toBe('escuro')
  })

  it('sem cookie, a tela de entrar cai no padrão — que era o sintoma relatado', () => {
    const entrar = pote({ host: 'auth.ultra-expansao.tech' })
    expect(lerTema(deposito(), entrar.deposito)).toBe(TEMA_PADRAO)
  })

  it('Domain recusado não perde o tema: a releitura detecta e grava host-only', () => {
    /* `document.cookie = ...` com `Domain` inaceitável não levanta e não devolve nada — o
       cookie só não existe depois. Sem reler, o mecanismo morreria CALADO em qualquer
       domínio cuja forma `dominioCompartilhado` não previsse. Encenado com um host cujo
       pai é sufixo público, que é exatamente essa forma. */
    const p = pote({ host: 'piloto.com.br', sufixosPublicos: ['com.br'] })
    gravarTema('claro', deposito(), p.deposito)
    expect(p.jar[COOKIE_TEMA]).toBe('claro')
  })

  it('na MESMA origem o localStorage vence o cookie', () => {
    // Quem acabou de trocar aqui não pode ver um cookie mais velho vencer.
    const p = pote({ host: 'piloto.ultra-expansao.tech', jar: { [COOKIE_TEMA]: 'escuro' } })
    expect(lerTema(deposito({ [CHAVE_TEMA]: 'claro' }), p.deposito)).toBe('claro')
  })

  it('o cookie vence a chave legada', () => {
    const p = pote({ host: 'auth.ultra-expansao.tech', jar: { [COOKIE_TEMA]: 'claro' } })
    expect(lerTema(deposito({ [CHAVE_TEMA_LEGADA]: 'escuro' }), p.deposito)).toBe('claro')
  })

  it('localStorage que ESTOURA não impede a leitura do cookie', () => {
    /* Um `try` só ao redor das três fontes fazia a primeira que estoura cancelar as outras
       — e em aba anônima quem estoura é justamente o `localStorage`. */
    const p = pote({ host: 'auth.ultra-expansao.tech', jar: { [COOKIE_TEMA]: 'claro' } })
    expect(lerTema(deposito({}, true), p.deposito)).toBe('claro')
  })

  it('cookie estragado, ausente ou de outro nome cai no padrão', () => {
    expect(lerTemaDoCookie(null)).toBeNull()
    expect(lerTemaDoCookie('')).toBeNull()
    expect(lerTemaDoCookie('outro=claro')).toBeNull()
    expect(lerTemaDoCookie(`${COOKIE_TEMA}=light`)).toBeNull()
    expect(lerTemaDoCookie(`${COOKIE_TEMA}=`)).toBeNull()
    // Nome que CONTÉM o nosso não pode casar.
    expect(lerTemaDoCookie(`x${COOKIE_TEMA}=claro`)).toBeNull()
    expect(lerTemaDoCookie(`a=1; ${COOKIE_TEMA}=claro; b=2`)).toBe('claro')
  })

  it('pote ausente ou que estoura não derruba a gravação', () => {
    const explosivo: DepositoDeCookie = {
      ler: () => {
        throw new DOMException('bloqueado', 'SecurityError')
      },
      escrever: () => {
        throw new DOMException('bloqueado', 'SecurityError')
      },
      hospedeiro: () => 'piloto.ultra-expansao.tech',
    }
    const d = deposito()
    expect(() => gravarTema('claro', d, explosivo)).not.toThrow()
    expect(() => gravarTema('claro', deposito(), null)).not.toThrow()
    expect(lerTema(d, explosivo)).toBe('claro') // o localStorage guardou
  })
})

describe('dominioCompartilhado', () => {
  it('sobe UM nível, e os dois subdomínios do produto caem no MESMO escopo', () => {
    expect(dominioCompartilhado('piloto.ultra-expansao.tech')).toBe('ultra-expansao.tech')
    expect(dominioCompartilhado('auth.ultra-expansao.tech')).toBe('ultra-expansao.tech')
    // É esta igualdade que faz o mecanismo existir.
    expect(dominioCompartilhado('piloto.ultra-expansao.tech')).toBe(
      dominioCompartilhado('auth.ultra-expansao.tech'),
    )
    // Outra instância (DEC-047: um país por processo) entra no mesmo escopo.
    expect(dominioCompartilhado('piloto-ar.ultra-expansao.tech')).toBe('ultra-expansao.tech')
  })

  it('não sobe além de um nível — o pai do pai é sufixo público e o cookie morreria', () => {
    expect(dominioCompartilhado('a.b.ultra-expansao.tech')).toBe('b.ultra-expansao.tech')
  })

  it('domínio de dois rótulos serve a si mesmo', () => {
    expect(dominioCompartilhado('ultra-expansao.tech')).toBe('ultra-expansao.tech')
  })

  it('host sem Domain possível devolve null: host-only é o certo ali', () => {
    expect(dominioCompartilhado('localhost')).toBeNull()
    expect(dominioCompartilhado('127.0.0.1')).toBeNull()
    expect(dominioCompartilhado('2.25.137.241')).toBeNull()
    expect(dominioCompartilhado('[::1]')).toBeNull()
    expect(dominioCompartilhado('')).toBeNull()
    expect(dominioCompartilhado(null)).toBeNull()
    expect(dominioCompartilhado(undefined)).toBeNull()
  })

  it('normaliza caixa e o ponto final do FQDN', () => {
    expect(dominioCompartilhado('PILOTO.Ultra-Expansao.TECH.')).toBe('ultra-expansao.tech')
  })
})

describe('montarCookieDeTema', () => {
  it('leva Path, validade, SameSite e o Domain compartilhado', () => {
    const c = montarCookieDeTema('claro', 'ultra-expansao.tech')
    expect(c).toContain(`${COOKIE_TEMA}=claro`)
    expect(c).toContain('Path=/')
    expect(c).toContain('SameSite=Lax')
    expect(c).toMatch(/Max-Age=\d+/)
    expect(c).toContain('Domain=ultra-expansao.tech')
  })

  it('sem domínio, sai host-only', () => {
    expect(montarCookieDeTema('escuro', null)).not.toMatch(/Domain=/i)
  })

  it('NÃO leva Secure, e isso é decisão declarada', () => {
    /* `Secure` faria o navegador descartar o cookie em HTTP e desligaria o mecanismo em
       silêncio no desenvolvimento e em host interno sem TLS. O valor é uma preferência de
       cor — está na tela —, não credencial. */
    expect(montarCookieDeTema('claro', 'ultra-expansao.tech')).not.toMatch(/Secure/i)
  })
})

describe('bootstrap de tema nos dois HTML', () => {
  const RAIZ_WEB = resolve(import.meta.dirname, '../..')

  /** O `<script>` que escreve `data-tema` antes da primeira pintura. */
  function bootstrap(arquivo: string): string {
    const html = readFileSync(resolve(RAIZ_WEB, arquivo), 'utf8').replace(/\r\n/g, '\n')
    const alvo = (html.match(/<script>[\s\S]*?<\/script>/g) ?? []).filter((b) =>
      b.includes('data-tema'),
    )
    expect(alvo, `${arquivo}: esperava UM <script> escrevendo data-tema`).toHaveLength(1)
    return alvo[0]
  }

  it('é o MESMO texto nos dois arquivos', () => {
    /* A tela de entrar quebrou em 2026-09-25 justamente por DIVERGIR do `index.html` —
       ela lia uma fonte a menos. Corrigir um e esquecer o outro é o defeito, não o
       acidente; texto idêntico é a guarda mais simples que o torna vermelho. */
    expect(bootstrap('entrar.html')).toBe(bootstrap('index.html'))
  })

  it('lê as TRÊS fontes, na mesma ordem de lerTema', () => {
    for (const arquivo of ['index.html', 'entrar.html']) {
      const s = bootstrap(arquivo)
      const iLocal = s.indexOf(`'${CHAVE_TEMA}'`)
      const iCookie = s.indexOf('document.cookie')
      const iLegado = s.indexOf(`'${CHAVE_TEMA_LEGADA}'`)
      expect(iLocal, `${arquivo}: não lê ${CHAVE_TEMA}`).toBeGreaterThanOrEqual(0)
      expect(iCookie, `${arquivo}: não lê o cookie`).toBeGreaterThanOrEqual(0)
      expect(iLegado, `${arquivo}: não lê ${CHAVE_TEMA_LEGADA}`).toBeGreaterThanOrEqual(0)
      expect(iLocal, `${arquivo}: ordem diverge de lerTema`).toBeLessThan(iCookie)
      expect(iCookie, `${arquivo}: ordem diverge de lerTema`).toBeLessThan(iLegado)
    }
  })

  it('o nome do cookie no HTML é o que o TS exporta', () => {
    /* Renomear `COOKIE_TEMA` sem mexer no HTML devolve o defeito EM SILÊNCIO: nada quebra,
       a tela de entrar só volta a nascer escura. */
    const escapado = `${COOKIE_TEMA.replace(/\./g, '\\.')}=`
    for (const arquivo of ['index.html', 'entrar.html']) {
      expect(bootstrap(arquivo), `${arquivo}: cookie com outro nome`).toContain(escapado)
    }
  })

  it('cada fonte tem o seu try, senão a primeira que estoura cancela as outras', () => {
    for (const arquivo of ['index.html', 'entrar.html']) {
      const tentativas = (bootstrap(arquivo).match(/try\s*\{/g) ?? []).length
      expect(tentativas, `${arquivo}: menos de três try`).toBeGreaterThanOrEqual(3)
    }
  })

  it('o padrão do HTML é o padrão do produto', () => {
    for (const arquivo of ['index.html', 'entrar.html']) {
      expect(bootstrap(arquivo)).toContain(`'${TEMA_PADRAO}'`)
    }
  })
})
