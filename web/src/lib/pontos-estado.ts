/**
 * A LISTA DE PONTOS ANALISADOS — o estado da comparação de pontos, com UM dono só.
 *
 * POR QUE SAIU DO `PontoScreen` (decisão do dono, 2026-10-14). A lista era `useState`
 * local daquela tela, e isso dava três defeitos de uma vez:
 *  - ir ao Simulador (Viabilidade) DESMONTA a tela e a análise inteira se perdia na volta;
 *  - o mapa, que é irmão dela na árvore, só enxergava UM ponto (o pin da aba aberta) e não
 *    tinha como desenhar todos os pontos da comparação, cada um na sua cor;
 *  - "Explorar uma região" e "Analisar um ponto" passaram a analisar pontos do mesmo jeito,
 *    e a lista precisa sobreviver à troca entre os dois.
 * Agora ela mora no `App` (via `lib/use-pontos`), e as regras moram AQUI, como funções
 * puras — o vitest roda em node e não monta React.
 *
 * O PIN PROVISÓRIO É UM ITEM DA LISTA, não um pin solto. Entre a busca e a resposta do
 * `/api/ponto` (alguns segundos: lê a partição do município) o operador precisa ver ONDE
 * pediu. Antes isso era um pin local do `MapScreen` — uma terceira leitura do mesmo ponto,
 * com regras próprias de limpeza, que convivia com o pin da ficha e com o cartão "Estudo
 * pontual". Aqui ele é um `pendente`: entra na lista de pins com a cor que vai ter quando
 * chegar, e vira ficha (ou some, se a leitura falhar) sem ninguém precisar limpar nada.
 *
 * A REGRA DE PRECEDÊNCIA DO PIN É UMA SÓ (`itemAtivo`): o pendente mais recente, se houver;
 * senão a ficha da aba aberta. É ele que comanda o voo da câmera e a seleção do hexágono.
 */

import { latLngToCell } from 'h3-js'

import {
  MAX_PONTOS,
  chaveDaCoordenada,
  indiceDoMesmoPonto,
  pinsDaComparacao,
  rotulosDosPontos,
  type PinDaComparacao,
} from './comparacao-pontos'
import type { PontoPayload } from './types'

/** Uma coordenada pedida ao `/api/ponto` e ainda não respondida. */
export interface PontoPendente {
  lat: number
  lng: number
}

export interface EstadoPontos {
  /** As fichas lidas, na ordem em que chegaram. É o que a comparação compara. */
  fichas: PontoPayload[]
  /** Índice da ficha aberta em detalhe (a aba). */
  aberto: number
  /** Coordenadas pedidas e ainda em leitura — o pin provisório de cada uma. */
  pendentes: PontoPendente[]
  /**
   * Contador que só cresce: cada vez que sobe, a camada da ficha se mostra.
   *
   * Existe porque o pedido agora nasce FORA da tela que mostra a ficha (a lupa do mapa, o
   * "Selecionar ponto"), e ela precisa saber que chegou resposta para abrir a janela.
   * Comparar a lista não basta: pedir de novo um ponto que já está nela não muda a lista,
   * e mesmo assim a janela tem de abrir na aba dele.
   */
  revelar: number
}

export const PONTOS_VAZIO: EstadoPontos = Object.freeze({
  fichas: [],
  aberto: 0,
  pendentes: [],
  revelar: 0,
}) as EstadoPontos

/** O que fazer com um pedido de coordenada, decidido ANTES de gastar uma leitura. */
export type DecisaoPedido =
  /** Já está na lista: abre a aba dele, sem ler de novo. */
  | { tipo: 'repetido'; indice: number }
  /** Já foi pedido e ainda está em leitura: não pede de novo. */
  | { tipo: 'esperando' }
  /** A comparação está cheia (contando os que ainda estão em leitura). */
  | { tipo: 'cheio' }
  /** Ponto novo, com vaga: ler. */
  | { tipo: 'ler' }

const mesmaCoordenada = (a: PontoPendente, b: PontoPendente) =>
  chaveDaCoordenada(a.lat, a.lng) === chaveDaCoordenada(b.lat, b.lng)

/**
 * Decide o pedido. O teto conta os PENDENTES também: com quatro fichas e um em leitura, um
 * sexto pedido seria aceito e descartado quando chegasse — uma leitura de servidor jogada
 * fora e um ponto que some sem aviso.
 */
export function decidirPedido(e: EstadoPontos, lat: number, lng: number): DecisaoPedido {
  const repetido = indiceDoMesmoPonto(e.fichas, lat, lng)
  if (repetido >= 0) return { tipo: 'repetido', indice: repetido }
  if (e.pendentes.some((p) => mesmaCoordenada(p, { lat, lng }))) return { tipo: 'esperando' }
  if (e.fichas.length + e.pendentes.length >= MAX_PONTOS) return { tipo: 'cheio' }
  return { tipo: 'ler' }
}

/** Aplica um pedido ao estado. `cheio` e `esperando` não mudam nada. */
export function pedir(e: EstadoPontos, lat: number, lng: number): EstadoPontos {
  const d = decidirPedido(e, lat, lng)
  if (d.tipo === 'repetido') return { ...e, aberto: d.indice, revelar: e.revelar + 1 }
  if (d.tipo === 'ler') return { ...e, pendentes: [...e.pendentes, { lat, lng }] }
  return e
}

/**
 * A leitura de `pedido` chegou.
 *
 * Só entra se o pedido AINDA estiver pendente: depois de "Limpar tudo", uma resposta que
 * chega atrasada não pode ressuscitar um ponto que o operador acabou de tirar da tela.
 * A ficha nova entra no fim e vira a aberta — quem acabou de pedir quer ver ela.
 */
export function chegou(e: EstadoPontos, pedido: PontoPendente, ficha: PontoPayload): EstadoPontos {
  const i = e.pendentes.findIndex((p) => mesmaCoordenada(p, pedido))
  if (i < 0) return e
  const pendentes = e.pendentes.filter((_, k) => k !== i)
  /* O servidor devolve a coordenada com 6 casas e o pedido pode ter mais; a chave de 5
     casas absorve isso, mas se mesmo assim a ficha já existir (dois caminhos chegaram ao
     mesmo imóvel), abre a que existe em vez de duplicar. */
  const repetido = indiceDoMesmoPonto(e.fichas, ficha.lat, ficha.lng)
  if (repetido >= 0) return { ...e, pendentes, aberto: repetido, revelar: e.revelar + 1 }
  const fichas = [...e.fichas, ficha]
  return { ...e, fichas, pendentes, aberto: fichas.length - 1, revelar: e.revelar + 1 }
}

/** A leitura de `pedido` falhou: o pin provisório sai, as fichas já lidas ficam. */
export function falhou(e: EstadoPontos, pedido: PontoPendente): EstadoPontos {
  const pendentes = e.pendentes.filter((p) => !mesmaCoordenada(p, pedido))
  return pendentes.length === e.pendentes.length ? e : { ...e, pendentes }
}

/** Abre a aba `i` (presa ao intervalo válido). */
export function abrir(e: EstadoPontos, i: number): EstadoPontos {
  if (!e.fichas.length) return e
  const aberto = Math.max(0, Math.min(i, e.fichas.length - 1))
  return aberto === e.aberto ? e : { ...e, aberto }
}

/**
 * Tira a ficha `i` da comparação.
 *
 * MANTÉM ABERTO O MESMO PONTO quando o removido vem antes dele: só prender o índice ao
 * tamanho novo trocava a aba aberta em silêncio (tirar a 1a de três, com a 3a aberta,
 * abria a que era a 2a) — e o mapa voava para outro ponto sem o operador pedir.
 */
export function remover(e: EstadoPontos, i: number): EstadoPontos {
  if (i < 0 || i >= e.fichas.length) return e
  const fichas = e.fichas.filter((_, k) => k !== i)
  const seguinte = i < e.aberto ? e.aberto - 1 : e.aberto
  const aberto = Math.max(0, Math.min(seguinte, fichas.length - 1))
  return { ...e, fichas, aberto }
}

/**
 * Tira TUDO: fichas e pins provisórios. O `revelar` não volta a zero de propósito — ele
 * é um contador de eventos, e voltar a um valor já visto faria a tela confundir um evento
 * novo com um antigo.
 */
export function limpar(e: EstadoPontos): EstadoPontos {
  return { ...PONTOS_VAZIO, revelar: e.revelar }
}

/** O ponto que comanda o mapa: posição, hexágono e (quando já lido) o território. */
export interface PontoAtivo {
  lat: number
  lng: number
  hexId: string
  /**
   * UF e município do ponto, para o mapa ir até eles. `null` enquanto o ponto ainda está
   * em leitura: só o `/api/ponto` sabe em que município ele caiu.
   */
  territorio: { uf: string; municipio: string } | null
}

/**
 * A REGRA DE PRECEDÊNCIA: o pendente mais recente vence; sem pendente, a aba aberta.
 *
 * O pendente vence porque é o último gesto do operador — ele acabou de pedir aquele lugar,
 * e o mapa ficar parado no ponto anterior até a resposta chegar é o "não reagiu" que leva
 * a pessoa a clicar de novo.
 */
export function itemAtivo(e: EstadoPontos): PontoAtivo | null {
  const p = e.pendentes[e.pendentes.length - 1]
  if (p) return { lat: p.lat, lng: p.lng, hexId: latLngToCell(p.lat, p.lng, 7), territorio: null }
  const f = e.fichas[e.aberto]
  if (!f) return null
  return {
    lat: f.lat,
    lng: f.lng,
    hexId: f.hex_id,
    territorio: { uf: f.local.uf ?? '', municipio: f.local.municipio ?? '' },
  }
}

/**
 * Identidade do ativo para decidir se o mapa precisa se mexer: a coordenada E se o
 * território já é conhecido. É a segunda metade que faz o mapa trocar de município quando
 * o pendente vira ficha — a coordenada é a mesma nos dois momentos.
 */
export function chaveDoAtivo(a: PontoAtivo | null): string | null {
  if (!a) return null
  const terr = a.territorio ? `${a.territorio.uf}/${a.territorio.municipio}` : '?'
  return `${chaveDaCoordenada(a.lat, a.lng)}|${terr}`
}

/** O pin que o mapa recebe, no formato do `SearchPin` do `HexMap`. */
export interface PinDoMapa {
  lat: number
  lng: number
  hexId: string
}

/**
 * O pin do ponto ativo, REAPROVEITANDO o objeto atual quando nada mudou para o mapa.
 *
 * O `HexMap` voa sempre que muda a IDENTIDADE do pin. Quando o pendente vira ficha no
 * mesmo lugar e no mesmo município, um objeto novo faria um segundo voo para onde a câmera
 * já está — e, se o operador tiver arrastado o mapa enquanto esperava, o puxaria de volta.
 *
 * Mas quando o TERRITÓRIO muda o objeto PRECISA ser novo, mesmo com a coordenada igual: o
 * `MapScreen` zera a seleção ao trocar de município, e é o efeito do pin (que só roda
 * quando o pin muda de identidade) que devolve o contorno ao hexágono do ponto.
 */
export function pinParaAtivo(
  atual: PinDoMapa | null,
  ativo: PontoAtivo,
  territorioMuda: boolean,
): PinDoMapa {
  if (
    atual &&
    !territorioMuda &&
    chaveDaCoordenada(atual.lat, atual.lng) === chaveDaCoordenada(ativo.lat, ativo.lng)
  ) {
    return atual
  }
  return { lat: ativo.lat, lng: ativo.lng, hexId: ativo.hexId }
}

/** Um pin da comparação, com a marca de "ainda em leitura". */
export interface PinDoPonto extends PinDaComparacao {
  carregando: boolean
}

/**
 * TODOS os pontos da comparação como pins, cada um na sua cor de identidade — fichas
 * primeiro, pendentes depois, na ordem em que entraram.
 *
 * O pendente já sai com a cor que VAI TER quando chegar (a do índice seguinte às fichas):
 * trocar de cor no momento em que a leitura chega seria um segundo sinal visual para o
 * mesmo ponto. Rótulo do pendente é a coordenada (o fallback de `pinsDaComparacao`): o
 * bairro ainda não é conhecido.
 */
export function pinsDoEstado(e: EstadoPontos): PinDoPonto[] {
  const itens = [...e.fichas, ...e.pendentes]
  const ativo = e.pendentes.length ? itens.length - 1 : e.fichas.length ? e.aberto : null
  return pinsDaComparacao(itens, ativo, rotulosDosPontos(e.fichas)).map((p) => ({
    ...p,
    carregando: p.indice >= e.fichas.length,
  }))
}
