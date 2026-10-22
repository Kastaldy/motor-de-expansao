/**
 * O registro do cabeçalho do mapa, por COMPORTAMENTO (revisão de 21/10/2026). Os leitores
 * (janela e camada do ponto) achavam o cabeçalho uma vez só, na montagem; o registro tem de
 * avisá-los quando ele aparece DEPOIS, some, ou é trocado por um elemento novo.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { afterEach, describe, expect, it } from 'vitest'

import { assinarCabecalhoMapa, cabecalhoMapaAtual, registrarCabecalhoMapa } from './registro-cabecalho'

const el = (nome: string) => ({ nome }) as unknown as HTMLElement

afterEach(() => registrarCabecalhoMapa(null))

describe('o registro do cabeçalho do mapa', () => {
  it('o cabeçalho que aparece DEPOIS do leitor avisa o leitor (Explorar sem UF -> com UF)', () => {
    const vistos: (HTMLElement | null)[] = []
    const cancelar = assinarCabecalhoMapa(() => vistos.push(cabecalhoMapaAtual()))
    expect(cabecalhoMapaAtual()).toBeNull()
    const cab = el('cabeçalho')
    registrarCabecalhoMapa(cab)
    expect(vistos).toEqual([cab])
    cancelar()
  })

  it('remontagem (Landing <-> mapa): o leitor passa a ver o elemento NOVO, não o desligado', () => {
    const vistos: (HTMLElement | null)[] = []
    const cancelar = assinarCabecalhoMapa(() => vistos.push(cabecalhoMapaAtual()))
    const velho = el('velho')
    const novo = el('novo')
    registrarCabecalhoMapa(velho)
    registrarCabecalhoMapa(null) // desmontagem
    registrarCabecalhoMapa(novo) // montagem
    expect(vistos).toEqual([velho, null, novo])
    expect(cabecalhoMapaAtual()).toBe(novo)
    cancelar()
  })

  it('o mesmo elemento de novo não re-avisa ninguém', () => {
    let avisos = 0
    const cancelar = assinarCabecalhoMapa(() => avisos++)
    const cab = el('cab')
    registrarCabecalhoMapa(cab)
    registrarCabecalhoMapa(cab)
    expect(avisos).toBe(1)
    cancelar()
  })

  it('assinatura cancelada não é mais avisada', () => {
    let avisos = 0
    const cancelar = assinarCabecalhoMapa(() => avisos++)
    cancelar()
    registrarCabecalhoMapa(el('cab'))
    expect(avisos).toBe(0)
  })

  it('o cabeçalho do mapa se publica, e os dois leitores leem o registro', () => {
    const fonte = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')
    const mapa = fonte('../screens/MapScreen.tsx')
    const abre = mapa.indexOf('className="barra-ultra"')
    expect(mapa.slice(abre, mapa.indexOf('style={{', abre))).toContain('ref={registrarCabecalhoMapa}')
    expect(fonte('../components/JanelaFicha.tsx')).toContain('useCabecalhoMapa()')
    expect(fonte('../screens/PontoScreen.tsx')).toContain('useCabecalhoMapa()')
  })
})
