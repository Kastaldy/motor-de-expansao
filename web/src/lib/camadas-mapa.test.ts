import { describe, expect, it } from 'vitest'

import {
  Z_CABECALHO_MAPA,
  Z_CORPO_MAPA,
  Z_FLUTUANTE_PONTO,
  Z_GAVETA_METODOLOGIA,
  Z_JANELA_FICHA,
  Z_JANELA_FICHA_TOPO,
} from './camadas-mapa'

describe('camadas do mapa', () => {
  it('a lista aberta de um seletor do cabecalho fica acima do painel da camada', () => {
    expect(Z_CABECALHO_MAPA).toBeGreaterThan(Z_CORPO_MAPA)
  })

  /* Pedido do Vinicius (21/10/2026): "as outras abas acabam ficando por cima dele,
     dificultando pra trocar estado / municipio". */
  it('o cabecalho fica ACIMA das janelas de ficha, inclusive a do topo da pilha', () => {
    expect(Z_CABECALHO_MAPA).toBeGreaterThan(Z_JANELA_FICHA)
    expect(Z_CABECALHO_MAPA).toBeGreaterThan(Z_JANELA_FICHA_TOPO)
  })

  it('e acima das pecas soltas do ponto (caixa de colar, espera, erro, "Ver a ficha")', () => {
    expect(Z_CABECALHO_MAPA).toBeGreaterThan(Z_FLUTUANTE_PONTO)
  })

  it('e ABAIXO da gaveta da Metodologia, que cobre o chrome do mapa de proposito', () => {
    expect(Z_GAVETA_METODOLOGIA).toBeGreaterThan(Z_CABECALHO_MAPA)
    expect(Z_GAVETA_METODOLOGIA).toBe(30)
  })

  it('corpo < janela < janela do topo < pecas soltas do ponto < cabecalho < Metodologia', () => {
    const ordem = [
      Z_CORPO_MAPA,
      Z_JANELA_FICHA,
      Z_JANELA_FICHA_TOPO,
      Z_FLUTUANTE_PONTO,
      Z_CABECALHO_MAPA,
      Z_GAVETA_METODOLOGIA,
    ]
    for (let i = 1; i < ordem.length; i++) expect(ordem[i]).toBeGreaterThan(ordem[i - 1])
  })
})
