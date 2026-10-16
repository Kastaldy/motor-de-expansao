import { describe, expect, it } from 'vitest'

import { Z_CABECALHO_MAPA, Z_CORPO_MAPA, Z_JANELA_FICHA } from './camadas-mapa'

describe('camadas do mapa', () => {
  it('a lista aberta de um seletor do cabecalho fica acima do painel da camada', () => {
    expect(Z_CABECALHO_MAPA).toBeGreaterThan(Z_CORPO_MAPA)
  })

  it('as janelas de ficha continuam acima do cabecalho', () => {
    expect(Z_JANELA_FICHA).toBeGreaterThan(Z_CABECALHO_MAPA)
  })
})
