import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

/**
 * Guardas do BUNDLE da tela de entrar.
 *
 * Ela é servida na raiz de `auth.ultra-expansao.tech`, um host que ela DIVIDE com o
 * portal do Authelia: o Caddy manda para o nosso container só a página e o prefixo
 * `entrar-assets/`; todo o resto daquele host vai para o Authelia.
 *
 * Isso cria duas formas de quebrar que **não aparecem em desenvolvimento** — no piloto
 * tudo é servido pelo mesmo backend, então qualquer caminho funciona lá. Só em produção,
 * e só naquele host, o erro aparece. Estes testes olham o FONTE, que é onde o defeito
 * seria introduzido.
 */

const RAIZ = resolve(import.meta.dirname, '..')

/* Lê o fonte SEM comentários. Sem isto, a própria explicação de por que o caminho
   absoluto é proibido — que cita `src="/logo-ultra.png"` — faria a guarda reprovar o
   arquivo que ela protege. Documentar o defeito não pode acusar o defeito. */
const ler = (p: string) =>
  readFileSync(resolve(RAIZ, p), 'utf-8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '')

describe('tela de entrar: caminhos de asset', () => {
  it('nao referencia asset por caminho ABSOLUTO', () => {
    /* `src="/logo-ultra.png"` funciona no piloto e cai no Authelia em `auth.` — o logo
       sumiria em produção sem nada quebrar antes. Resolvido por import, o caminho não
       tem como estar errado no ar sem primeiro quebrar o build. */
    const fontes = [
      'screens/LoginScreen.tsx',
      'components/login/MalhaBrasil.tsx',
      'entrar.tsx',
    ]
    for (const f of fontes) {
      const texto = ler(f)
      expect(texto, `${f}: asset por caminho absoluto`).not.toMatch(/(?:src|href)=["']\//)
      expect(texto, `${f}: url() absoluta no CSS em linha`).not.toMatch(/url\(\s*["']?\//)
    }
  })

  it('a entrada da tela NAO arrasta o app do piloto', () => {
    /* Importar `App` (ou o `main`) traria a SPA inteira para o bundle servido ANTES do
       login — as rotas internas da API viajam nela. O bundle tem de ser só a tela. */
    const entrada = ler('entrar.tsx')
    expect(entrada).not.toMatch(/from\s+["']\.\/App["']/)
    expect(entrada).not.toMatch(/from\s+["']\.\/main["']/)
  })

  it('a tela fala com o Authelia por caminho RELATIVO', () => {
    /* Origem absoluta (`https://auth...`) quebraria a propriedade que sustenta o
       desenho: o `fetch` é de mesma origem, e é isso que faz o cookie ser aceito sem
       CORS. Cravar o host também impediria o mesmo binário de servir outra instância. */
    const entrada = ler('entrar.tsx')
    expect(entrada).toMatch(/fetch\(\s*'\/api\/firstfactor'/)
    expect(entrada).not.toMatch(/fetch\(\s*['"`]https?:/)
  })

  it('o aviso de autofill existe no CSS com o nome que o TS compara', () => {
    /* Relato do Vinicius (2026-09-24): com os campos autopreenchidos, o botao de
       entrar nascia desabilitado — o navegador escreve no DOM sem disparar o evento
       que o React escuta, entao o estado ficava vazio.

       A correcao depende de um acoplamento POR NOME entre dois arquivos: a animacao
       `aviso-autofill` no `global.css` e a comparacao `e.animationName === '...'` no
       `LoginScreen`. Renomear de um lado so' devolve o defeito EM SILENCIO — nada
       quebra, nada fica vermelho, o botao so' volta a mentir. Este teste e' o que
       torna essa quebra visivel. */
    const css = readFileSync(resolve(RAIZ, 'styles/global.css'), 'utf8')
    const tela = ler('screens/LoginScreen.tsx')

    expect(css).toMatch(/@keyframes\s+aviso-autofill\b/)
    expect(css).toMatch(/input:-webkit-autofill\s*\{[^}]*animation-name:\s*aviso-autofill/)
    expect(tela).toMatch(/animationName\s*!==\s*'aviso-autofill'/)
    // E os dois campos precisam ESCUTAR o evento — sem o handler, a animacao dispara
    // para ninguem.
    expect(tela.match(/onAnimationStart=\{aoAutoPreencher\}/g)).toHaveLength(2)
  })
})
