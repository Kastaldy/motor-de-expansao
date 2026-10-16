import { describe, expect, it } from 'vitest'

import {
  FOLGA_ABAIXO_DO_CABECALHO,
  TOPO_BOTAO_PADRAO,
  topoDoBotaoVerFicha,
} from './botao-ver-ficha'

describe('topoDoBotaoVerFicha', () => {
  it('sem medida vale o topo padrão da janela', () => {
    expect(topoDoBotaoVerFicha(null, 0)).toBe(TOPO_BOTAO_PADRAO)
    expect(topoDoBotaoVerFicha(67, null)).toBe(TOPO_BOTAO_PADRAO)
    expect(topoDoBotaoVerFicha(Number.NaN, 0)).toBe(TOPO_BOTAO_PADRAO)
  })

  it('fica logo abaixo do cabeçalho, com a folga', () => {
    expect(topoDoBotaoVerFicha(67, 0)).toBe(67 + FOLGA_ABAIXO_DO_CABECALHO)
  })

  it('acompanha o cabeçalho que quebra em duas linhas', () => {
    // ~1100 px: o cabeçalho desce para ~103 px, e o botão desce junto.
    expect(topoDoBotaoVerFicha(103, 0)).toBeGreaterThan(103)
  })

  it('é relativo ao contêiner, não à tela', () => {
    expect(topoDoBotaoVerFicha(67, -13)).toBe(67 + 13 + FOLGA_ABAIXO_DO_CABECALHO)
  })

  it('desfaz a escala do app: a medida está em px de tela, o top em px de layout', () => {
    // #root encolhido a 0,85: 68 px de tela = 80 px de layout.
    expect(topoDoBotaoVerFicha(68, 0, 0.85)).toBe(80 + FOLGA_ABAIXO_DO_CABECALHO)
    expect(topoDoBotaoVerFicha(68, 0, 0)).toBe(68 + FOLGA_ABAIXO_DO_CABECALHO)
  })

  it('nunca devolve negativo', () => {
    expect(topoDoBotaoVerFicha(0, 500)).toBe(0)
  })
})
