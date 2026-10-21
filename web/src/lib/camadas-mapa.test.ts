import { describe, expect, it } from 'vitest'

import {
  Z_CABECALHO_MAPA,
  Z_CORPO_MAPA,
  Z_FLUTUANTE_PONTO,
  Z_JANELA_FICHA,
  Z_JANELA_FICHA_TOPO,
} from './camadas-mapa'

describe('camadas do mapa', () => {
  it('a lista aberta de um seletor do cabecalho fica acima do painel da camada', () => {
    expect(Z_CABECALHO_MAPA).toBeGreaterThan(Z_CORPO_MAPA)
  })

  it('as janelas de ficha continuam acima do cabecalho', () => {
    expect(Z_JANELA_FICHA).toBeGreaterThan(Z_CABECALHO_MAPA)
  })

  it('corpo < cabecalho < janela < janela do topo < pecas soltas do ponto < 30 (Metodologia, tooltips)', () => {
    const ordem = [Z_CORPO_MAPA, Z_CABECALHO_MAPA, Z_JANELA_FICHA, Z_JANELA_FICHA_TOPO, Z_FLUTUANTE_PONTO, 30]
    for (let i = 1; i < ordem.length; i++) expect(ordem[i]).toBeGreaterThan(ordem[i - 1])
  })
})
