/**
 * O PAINEL do trilho inferior esquerdo do mapa: "Camadas do mapa" OU "Desenhar área", nunca
 * os dois (pedido do Vinicius, 2026-10-16).
 *
 * POR QUE UM SÓ. Os dois painéis abrem no MESMO lugar — colados no trilho, à direita dele —
 * e com a mesma caixa (`PainelDoTrilho`). Antes o do desenho subia empilhado por cima do
 * trilho, com outra cara (era a caixa "não tão visualmente agradável" do pedido). Um lugar,
 * uma caixa, um painel por vez.
 *
 * O PAINEL DO DESENHO É A FERRAMENTA LIGADA. Ele está aberto exatamente quando a ferramenta
 * "Analisar geometria" está ligada — não existe um segundo booleano para divergir. Por isso
 * FECHAR o painel (o × dele, o botão do polígono de novo, abrir "Camadas", ligar a régua ou o
 * ponto) é PAUSAR o desenho: a ferramenta desliga, o clique no mapa volta a ser o de sempre,
 * e os VÉRTICES FICAM, desenhados no mapa. Reabrir (o botão do polígono no trilho, ou a linha
 * "Analisar geometria" do painel de camadas) retoma de onde parou.
 *
 * O que APAGA o desenho é declarado e curto (`rascunhoSobrevive`): Cancelar, Esc com o desenho
 * ligado, Concluir (a área virou item da comparação) e a troca de território. Antes qualquer
 * desligamento apagava — e "abrir as camadas para ligar os pins" custaria o polígono inteiro.
 *
 * Funções PURAS, sem React, para o vitest (node) testar sem montar mapa.
 */

import { alternarFerramenta, type FerramentaMapa } from './ferramenta-mapa'

export interface EstadoTrilho {
  /** O painel "Camadas do mapa" está aberto. */
  camadasAberto: boolean
  /** A ferramenta do clique (`lib/ferramenta-mapa`); 'geometria' = painel do desenho aberto. */
  ferramenta: FerramentaMapa
}

export type AcaoTrilho =
  /** O ícone de camadas do trilho (abre/fecha). */
  | { tipo: 'alternar-camadas' }
  /** O × do painel de camadas. */
  | { tipo: 'fechar-camadas' }
  /** Um botão de ferramenta (trilho ou linha do painel). */
  | { tipo: 'alternar-ferramenta'; alvo: FerramentaMapa }
  /** Desligar a ferramenta sem trocar de painel: Esc, Concluir, Cancelar, × do painel do desenho. */
  | { tipo: 'desligar-ferramenta' }

export function transicaoTrilho(e: EstadoTrilho, a: AcaoTrilho): EstadoTrilho {
  switch (a.tipo) {
    case 'alternar-camadas': {
      const abrir = !e.camadasAberto
      /* Abrir as camadas PAUSA o desenho (a ferramenta desliga, os vértices ficam): o painel
         do desenho mora no mesmo lugar e é a ferramenta ligada. As outras ferramentas (régua,
         ponto) convivem com o painel de camadas, como sempre conviveram. */
      return {
        camadasAberto: abrir,
        ferramenta: abrir && e.ferramenta === 'geometria' ? 'nenhuma' : e.ferramenta,
      }
    }
    case 'fechar-camadas':
      return { ...e, camadasAberto: false }
    case 'alternar-ferramenta': {
      const ferramenta = alternarFerramenta(e.ferramenta, a.alvo)
      /* Ligar o desenho fecha as camadas — inclusive quando o gesto veio da linha
         "Analisar geometria" de dentro do próprio painel de camadas. */
      return {
        camadasAberto: ferramenta === 'geometria' ? false : e.camadasAberto,
        ferramenta,
      }
    }
    case 'desligar-ferramenta':
      return { ...e, ferramenta: 'nenhuma' }
  }
}

/** Qual painel aparece ao lado do trilho. Nunca os dois. */
export function painelDoTrilho(e: EstadoTrilho): 'camadas' | 'desenho' | null {
  if (e.ferramenta === 'geometria') return 'desenho'
  return e.camadasAberto ? 'camadas' : null
}

/** Por que a ferramenta do desenho está desligando. */
export type MotivoFimDoDesenho =
  /** Fechou o painel do desenho, abriu as camadas, ligou outra ferramenta, tocou o botão de novo. */
  | 'pausa'
  /** O botão "Cancelar". */
  | 'cancelar'
  /** Esc com o desenho ligado — o atalho de cancelar que o título do botão promete. */
  | 'esc'
  /** "Concluir" ou clique no 1º vértice: a área virou item da comparação. */
  | 'concluir'
  /** Trocou de município/UF: o polígono é de um território. */
  | 'territorio'

/** Os vértices sobrevivem a este fim? Só a pausa os guarda. */
export function rascunhoSobrevive(motivo: MotivoFimDoDesenho): boolean {
  return motivo === 'pausa'
}

/**
 * O desenho está PAUSADO: há vértices guardados e a ferramenta não está ligada. É o estado
 * que muda o título do botão do trilho ("Retomar o desenho") e a linha do painel.
 */
export function desenhoPausado(ferramenta: FerramentaMapa, nVertices: number): boolean {
  return ferramenta !== 'geometria' && nVertices > 0
}
