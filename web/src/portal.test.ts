import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'

import SelecaoPais, { PAISES } from './screens/SelecaoPais'

/**
 * Guardas do PORTAL DO APEX (`ultra-expansao.tech`), que substitui o portal estatico.
 *
 * O Vitest daqui roda sem DOM, mas `renderToStaticMarkup` e' render de string (sem DOM):
 * da' para RENDERIZAR `SelecaoPais` e provar o comportamento da selecao — a tabela, a
 * sigla desconhecida ignorada, os dois hosts, os cartoes como <a>. O orquestrador
 * `portal.tsx` tem efeito de montagem no topo (`createRoot`), entao ele e' guardado pelo
 * TEXTO-FONTE, como em `entrar-bundle.test.ts`.
 */

const ler = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')

/* Fonte SEM comentarios: a propria explicacao de "nunca um ramo por pais" nao pode fazer
   a guarda do fio de alarme acusar o arquivo que ela protege (mesma licao de
   `entrar-bundle.test.ts`). */
const semComentarios = (t: string) =>
  t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')

const portal = ler('./portal.tsx')
const selecao = ler('./screens/SelecaoPais.tsx')
const html = ler('../portal.html')

const HOST_BR = 'piloto.ultra-expansao.tech'
const HOST_AR = 'piloto-ar.ultra-expansao.tech'

describe('portal do apex: a selecao e dirigida por TABELA, nao por pais no codigo', () => {
  afterEach(() => vi.restoreAllMocks())

  it('renderiza um cartao <a> por pais, com o host de cada um', () => {
    const markup = renderToStaticMarkup(createElement(SelecaoPais, { paises: ['BR', 'AR'] }))
    // Links de verdade (<a href>), nunca <div onClick>.
    expect(markup).toMatch(/<a[^>]+href="https:\/\/piloto\.ultra-expansao\.tech\/"/)
    expect(markup).toMatch(/<a[^>]+href="https:\/\/piloto-ar\.ultra-expansao\.tech\/"/)
    expect(markup).toContain('Brasil')
    expect(markup).toContain('Argentina')
    expect(markup).not.toContain('onclick')
  })

  it('respeita a ORDEM da lista recebida', () => {
    const markup = renderToStaticMarkup(createElement(SelecaoPais, { paises: ['AR', 'BR'] }))
    expect(markup.indexOf(HOST_AR)).toBeLessThan(markup.indexOf(HOST_BR))
  })

  it('IGNORA uma sigla que nao esta na tabela (com aviso discreto), sem quebrar', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const markup = renderToStaticMarkup(createElement(SelecaoPais, { paises: ['XX', 'BR'] }))
    expect(markup).toContain(HOST_BR)
    // A sigla desconhecida nao desenha cartao nenhum e nao arrasta o outro host.
    expect(markup).not.toContain('piloto-ar')
    expect(markup).not.toContain('XX')
    expect(warn).toHaveBeenCalledOnce()
  })

  it('lista vazia nao desenha cartao nenhum', () => {
    const markup = renderToStaticMarkup(createElement(SelecaoPais, { paises: [] }))
    expect(markup).not.toContain('<a')
  })

  it('lista so com sigla SEM cartao mostra o aviso, nunca uma <ul> vazia', () => {
    // Cenario real do rollout (baixo 2 da revisao): /api/me devolve ['CO'] (nao-vazia) antes de
    // CO ter cartao. O portal.tsx entra em 'selecao' (lista nao-vazia), e SelecaoPais ignora CO
    // -> tem de mostrar o AVISO, nao uma <ul>/<a> vazia (pagina em branco).
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const markup = renderToStaticMarkup(createElement(SelecaoPais, { paises: ['CO'] }))
    expect(markup).not.toContain('<a')
    expect(markup).not.toContain('<ul')
    expect(markup).toContain('ainda não estão disponíveis')
    expect(warn).toHaveBeenCalledOnce()
  })

  it('a tabela PAISES e indexada por sigla e carrega nome + host de cada pais', () => {
    expect(Object.keys(PAISES)).toEqual(['BR', 'AR'])
    expect(PAISES.BR).toMatchObject({ nome: 'Brasil', host: HOST_BR })
    expect(PAISES.AR).toMatchObject({ nome: 'Argentina', host: HOST_AR })
  })
})

describe('portal do apex: o fio de alarme da DEC-047', () => {
  it('nenhum ramo de codigo condiciona por SIGLA de pais (tabela, nunca ternario)', () => {
    const codigo = semComentarios(portal) + '\n' + semComentarios(selecao)
    const literalEmCondicional = /(===|!==)\s*['"](BR|AR)['"]|['"](BR|AR)['"]\s*(===|!==)/
    expect(codigo).not.toMatch(literalEmCondicional)
  })

  it('nenhum arquivo do apex menciona o autenticador aposentado', () => {
    for (const [nome, texto] of [
      ['portal.tsx', portal],
      ['SelecaoPais.tsx', selecao],
      ['portal.html', html],
    ] as const) {
      expect(texto, `${nome} cita o autenticador aposentado`).not.toMatch(/authelia/i)
    }
  })
})

describe('portal do apex: o orquestrador em portal.tsx', () => {
  const codigo = semComentarios(portal)

  it('le o /api/me e ramifica nas tres fases + erro', () => {
    expect(codigo).toMatch(/api\.me\(\)/)
    // 401 -> login; qualquer outra falha -> erro.
    expect(codigo).toMatch(/status === 401/)
    // paises ausente (null) -> erro; vazio -> sem-acesso; com itens -> selecao.
    expect(codigo).toMatch(/paises === null/)
    expect(codigo).toMatch(/paises\.length === 0/)
  })

  it('a fase de login reusa o MESMO LoginScreen da tela de entrar', () => {
    expect(codigo).toMatch(/import LoginScreen from '\.\/screens\/LoginScreen'/)
    expect(codigo).toMatch(/<LoginScreen onEntrar=\{aoEntrar\}/)
  })

  it('a fase de selecao desenha os cartoes por SelecaoPais', () => {
    expect(codigo).toMatch(/import SelecaoPais from '\.\/screens\/SelecaoPais'/)
    expect(codigo).toMatch(/<SelecaoPais paises=\{fase\.paises\}/)
  })

  it('tem a tela "sem acesso" e a de erro com nova tentativa', () => {
    expect(portal).toContain('Você ainda não tem acesso a nenhum país')
    expect(portal).toContain('Tentar de novo')
  })

  it('no sucesso do login NAO navega para destinoSeguro — re-consulta o /api/me', () => {
    /* O apex fica no apex (a tarefa da DEC-081): entrar nao leva a `destinoSeguro` nem
       navega a lugar nenhum; so' re-chama `carregar`, que le' o /api/me de novo. */
    expect(codigo).not.toMatch(/destinoSeguro/)
    expect(codigo).not.toMatch(/location\.assign/)
    expect(codigo).not.toMatch(/location\.href\s*=/)
    expect(codigo).toMatch(/await api\.entrar\(/)
    expect(codigo).toMatch(/void carregar\(\)/)
  })

  it('o bundle do apex NAO arrasta a SPA do piloto', () => {
    expect(codigo).not.toMatch(/from\s+['"]\.\/App['"]/)
    expect(codigo).not.toMatch(/from\s+['"]\.\/main['"]/)
  })
})

describe('portal do apex: a pagina (portal.html)', () => {
  it('carrega o entry proprio do portal', () => {
    expect(html).toContain('src="/src/portal.tsx"')
    expect(html).toContain('<div id="root"></div>')
  })
})
