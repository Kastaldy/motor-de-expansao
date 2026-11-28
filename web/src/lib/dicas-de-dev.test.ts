import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

/* B5 do pentest (11/2026): as mensagens de erro que o OPERADOR vê não podem citar detalhe
   de dev (a porta 8899, o `iniciar-piloto-web.cmd`, o nome do parquet) — vaza infra e, em
   produção, faz a tela parecer "sistema caiu". Olha o FONTE SEM COMENTÁRIOS: a explicação de
   por que a frase foi neutralizada cita a porta de propósito e não pode acusar a guarda. */

const SRC = resolve(import.meta.dirname, '..') // src/lib/ -> src/

const semComentarios = (p: string) =>
  readFileSync(resolve(SRC, p), 'utf-8')
    .replace(/\/\*[\s\S]*?\*\//g, '') // bloco /* ... */ e JSX {/* ... */}
    .replace(/^\s*\/\/.*$/gm, '')

const TELAS = ['screens/MapScreen.tsx', 'screens/OportunidadesImobiliariasScreen.tsx']
const PROIBIDOS = ['8899', 'iniciar-piloto-web', 'viaveis.parquet', 'própria máquina']

describe('mensagens de erro não vazam detalhe de dev (B5)', () => {
  for (const tela of TELAS) {
    it(`${tela}: sem porta/arquivo/host interno no texto ao usuário`, () => {
      const fonte = semComentarios(tela)
      for (const token of PROIBIDOS) {
        expect(fonte, `${tela}: ainda cita "${token}" fora de comentário`).not.toContain(token)
      }
    })
  }
})
