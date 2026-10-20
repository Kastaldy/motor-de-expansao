/**
 * O botão do Simulador na ficha do ponto sem a seta ao lado do texto (pedido do Vinicius,
 * 20/10/2026: "No botão do Simulador, quero que você remova a seta no lado do texto").
 *
 * O Vitest roda sem DOM: a trava lê o FONTE da tela, no molde de `seletor-alcance.test`.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { ROTULO_SIMULADOR } from './rodape-ponto'

const pontoScreen = readFileSync(fileURLToPath(new URL('../screens/PontoScreen.tsx', import.meta.url)), 'utf-8')

/** Setas que já apareceram (ou poderiam aparecer) coladas a um rótulo de botão. */
const SETA = /[→➜➔⟶›»]|->/

describe('botão do Simulador sem seta', () => {
  it('o rótulo do Simulador não carrega seta', () => {
    expect(ROTULO_SIMULADOR).toBe('Simulador')
    expect(ROTULO_SIMULADOR).not.toMatch(SETA)
  })

  it('o botão da ficha mostra só o rótulo', () => {
    const inicio = pontoScreen.indexOf('onClick={onSimulador}')
    expect(inicio).toBeGreaterThan(-1)
    const conteudo = pontoScreen.slice(inicio, pontoScreen.indexOf('</Botao>', inicio))
    expect(conteudo).toContain('{simulador.rotulo}')
    expect(conteudo.slice(conteudo.indexOf('{simulador.rotulo}'))).not.toMatch(SETA)
  })

  it('nenhum outro ponto da tela cola uma seta ao rótulo do Simulador', () => {
    expect(pontoScreen).not.toMatch(/\{simulador\.rotulo\}\s*(?:[→➜➔⟶›»]|->)/)
  })
})
