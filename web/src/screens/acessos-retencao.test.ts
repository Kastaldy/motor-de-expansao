/**
 * Retenção da trilha de acesso, como a tela a DESCREVE (DEC-027, emenda 2, 20/10/2026).
 *
 * A trilha bruta passou a ser guardada SEM prazo de deleção. Os 90 dias que sobram na aba
 * Acessos são o limite da JANELA da tela (`JANELA_DIAS_MAX` no backend), não da trilha. A
 * nota de rodapé dizia "retenção de 90 dias" e ficou para trás quando o código mudou; o
 * vitest roda em node e não monta a tela, então aqui se trava o TEXTO no fonte.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

// JSX quebra a frase em várias linhas: normalizar o espaço antes de procurar.
const normalizar = (s: string) => s.replace(/\s+/g, ' ')
const ler = (rel: string) => normalizar(readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8'))

const acessos = ler('./AcessosScreen.tsx')

const RETENCAO_90 = /reten[çc][ãa]o de 90 dias/i

function fontes(dir: string): string[] {
  return readdirSync(dir).flatMap((nome) => {
    const caminho = join(dir, nome)
    if (statSync(caminho).isDirectory()) return fontes(caminho)
    return /\.tsx?$/.test(nome) && !nome.endsWith('.test.ts') ? [caminho] : []
  })
}

describe('retenção da trilha de acesso na aba Acessos', () => {
  it('não afirma mais retenção de 90 dias da trilha', () => {
    expect(acessos).not.toMatch(RETENCAO_90)
    expect(acessos).not.toContain('além dos 90 dias')
  })

  it('declara a trilha sem prazo e os 90 dias como limite da janela da tela', () => {
    expect(acessos).toContain('guardada sem prazo de deleção (DEC-027, emenda 2)')
    expect(acessos).toContain('esse é o limite da janela da tela, não da trilha')
  })

  it('nenhum fonte do front volta a afirmar retenção de 90 dias', () => {
    const raiz = fileURLToPath(new URL('..', import.meta.url))
    const culpados = fontes(raiz).filter((f) => RETENCAO_90.test(normalizar(readFileSync(f, 'utf-8'))))
    expect(culpados).toEqual([])
  })
})
