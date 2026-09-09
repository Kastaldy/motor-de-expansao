import { describe, expect, it } from 'vitest'

import { TODAS_AS_ABAS, telaLiberada, type Aba } from './acesso'
import { ITENS_DOCK } from './dock-itens'

describe('fila de destinos do Dock', () => {
  it('tem o atalho do mapa, com o mesmo destino do card "Explorar uma região"', () => {
    // Pedido do Juan (2026-09-04): o mapa volta ao Dock como atalho — um caminho só,
    // mesmo destino do card do Início; o estado do mapa mora no App e sobrevive.
    const mapa = ITENS_DOCK.find((it) => it.tela === 'mapa')
    expect(mapa).toBeDefined()
    expect(mapa?.titulo).toBe('Explorar uma região')
  })

  it('o mapa é o primeiro destino navegável — é a superfície default do piloto', () => {
    const navegaveis = ITENS_DOCK.filter((it) => it.tela !== null)
    expect(navegaveis[0]?.tela).toBe('mapa')
  })

  it('ids são identificadores sem acento e sem repetição (CLAUDE.md §2)', () => {
    const ids = ITENS_DOCK.map((it) => it.id)
    for (const id of ids) expect(id).toMatch(/^[a-z0-9-]+$/)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('todo destino navegável é conhecido pelo gate de abas', () => {
    // Com todas as abas, o gate deve liberar cada tela da fila; uma tela que o
    // ABA_DA_TELA não conheça devolveria `undefined` na aba e falharia aqui.
    const todas = new Set<Aba>(TODAS_AS_ABAS)
    for (const it of ITENS_DOCK) {
      if (it.tela === null) continue
      expect(telaLiberada(it.tela, todas)).toBe(true)
    }
  })
})
