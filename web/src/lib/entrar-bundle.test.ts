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

  it('a tela fala com o NOSSO backend, e por caminho RELATIVO', () => {
    /* Até 25/09/2026 esta guarda exigia `fetch('/api/firstfactor')` — o Authelia. A
       DEC-067 foi assinada nos quatro itens e a tela passou a usar `api.entrar()`, que
       fala com o nosso `POST /api/login`.

       A PROPRIEDADE que a guarda protege não mudou: origem RELATIVA. Uma origem absoluta
       (`https://auth...`) quebraria o que sustenta o desenho — o pedido é de mesma
       origem, e é isso que faz o cookie de sessão ser aceito sem CORS. Cravar o host
       também impediria o mesmo binário de servir outra instância (DEC-047: um país por
       processo, nenhum host no código). */
    const entrada = ler('entrar.tsx')
    expect(entrada).toMatch(/\bapi\.entrar\(/)
    expect(entrada).not.toMatch(/https?:\/\//)
  })

  it('a tela NAO fala mais com o Authelia', () => {
    /* O contrário do teste acima, e ele existe separado porque some em silêncio: uma
       reintrodução do `/api/firstfactor` — por merge da main, por reversão apressada no
       dia do corte — passaria despercebida se a única asserção fosse sobre o que a tela
       CHAMA. Depois do corte o Authelia não existe: um `fetch` para lá é 404 numa tela
       que a pessoa precisa para entrar. */
    const entrada = ler('entrar.tsx')
    expect(entrada).not.toMatch(/firstfactor/)
    expect(entrada).not.toMatch(/\bmontarPedido\b|\blerResposta\b/)
  })
})
