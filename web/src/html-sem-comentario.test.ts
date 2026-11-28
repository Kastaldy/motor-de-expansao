import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

/* B4 do pentest (11/2026): comentário HTML viaja no corpo servido ao anônimo. Os três shells
   traziam blocos que descreviam a infra (Authelia, host `auth.`, roteamento do Caddy, "o nome
   de cada rota interna da API"). A documentação útil do bootstrap de tema foi para
   `src/lib/tema.ts`; o corpo servido não leva mais nenhum `<!-- -->`. */

const WEB = resolve(import.meta.dirname, '..') // src/ -> web/

describe('HTML servido sem comentários (B4)', () => {
  for (const nome of ['index.html', 'entrar.html', 'portal.html']) {
    it(`${nome} não tem <!-- comentário -->`, () => {
      const html = readFileSync(resolve(WEB, nome), 'utf-8')
      expect(html, `${nome}: comentário HTML vaza no corpo servido`).not.toContain('<!--')
    })
  }
})
