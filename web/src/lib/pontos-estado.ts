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
  ROTULO_AREA_DESENHADA,
  chaveDaArea,
  chaveDaCoordenada,
  indiceDaMesmaArea,
  indiceDoMesmoPonto,
  pinsDaComparacao,
  rotulosDosPontos,
  type PinDaComparacao,
  type PosicaoGeoJson,
} from './comparacao-pontos'
import { indiceDaMesmaUnidade } from './estudo-ultra'
import type { PontoPayload } from './types'

/**
 * Um pedido ainda não respondido: uma coordenada ao `/api/ponto` ou uma ÁREA DESENHADA ao
 * `/api/ponto/geometria` (DEC-071).
 *
 * Na área, `lat`/`lng` é um ponto DENTRO do polígono calculado na tela (`pontoInterno`):
 * é onde o pin provisório aparece até o servidor devolver o `representative_point` dele.
 */
export interface PontoPendente {
  lat: number
  lng: number
  /** Os anéis do polígono (`[lng, lat]`) — só no pedido de área desenhada. */
  geometria?: PosicaoGeoJson[][] | null
  /**
   * O pedido nasceu de um CLIQUE NO PRÓPRIO MAPA ("Selecionar ponto"): o lugar já está
   * na tela, sob o cursor. O pin dele não voa nem aproxima a câmera — a ferramenta fica
   * ligada para marcar vários pontos em sequência, e um voo com zoom 13 a cada clique
   * tirava da tela o bairro do próximo. Só aparece quando `true`.
   */
  doMapa?: boolean
  /**
   * Pedido de ESTUDO DA UNIDADE ULTRA (emenda da DEC-070): o consumo da unidade a até 150 m
   * sai do mercado. Não entra na identidade do pedido — o mesmo lugar nos dois modos é o
   * MESMO ponto, e trocar de modo substitui a ficha (`substituir`). Só aparece quando `true`.
   */
  estudoUltra?: boolean
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
  /**
   * Contador que só cresce: cada vez que sobe, o operador ESCOLHEU um item (aba, pin
   * colorido, nome num bloco, pedido repetido) e o mapa tem de ir até ele — mesmo que
   * seja o item que já estava aberto.
   *
   * Existe porque a chave do ativo (`chaveDoAtivo`) não muda quando se clica de novo no
   * ponto aberto, e era só ela que movia o mapa: depois de trocar de município à mão (o
   * ponto perde o comando da câmera) ou de arrastar o mapa, clicar no ponto aberto não o
   * trazia de volta. Ver `movimentoDoMapa`.
   */
  foco: number
  /**
   * O operador escolheu uma aba DEPOIS do último pedido ainda em leitura.
   *
   * Sem isto o pedido em voo vencia o clique: com um pendente, trocar de aba não movia o
   * mapa (o pendente seguia sendo o ativo), e quando a leitura chegava a aba aberta era
   * trocada à força pela ficha nova. A escolha explícita vale mais que um pedido anterior
   * a ela. Um pedido NOVO devolve a precedência ao pendente (é o gesto mais recente).
   */
  abaFixada: boolean
}

export const PONTOS_VAZIO: EstadoPontos = Object.freeze({
  fichas: [],
  aberto: 0,
  pendentes: [],
  revelar: 0,
  foco: 0,
  abaFixada: false,
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

/**
 * A identidade de um pedido: a coordenada, para ponto; os vértices, para área. Área e
 * ponto nunca se confundem — o `lat`/`lng` da área é um ponto interno que ninguém clicou.
 */
const chaveDoPedido = (p: PontoPendente) =>
  p.geometria?.length ? chaveDaArea(p.geometria) : `ponto:${chaveDaCoordenada(p.lat, p.lng)}`

const mesmoPedido = (a: PontoPendente, b: PontoPendente) => chaveDoPedido(a) === chaveDoPedido(b)

/**
 * Decide o pedido. O teto conta os PENDENTES também: com quatro fichas e um em leitura, um
 * sexto pedido seria aceito e descartado quando chegasse — uma leitura de servidor jogada
 * fora e um ponto que some sem aviso.
 *
 * `estudoUltra`: o pedido parte da UNIDADE Ultra (coordenada do cadastro dela). Um ponto da
 * lista a poucos metros, já ligado à mesma unidade, é o MESMO lugar — `repetido`, e quem
 * pediu troca o modo dele (`indiceDaMesmaUnidade`), em vez de abrir um segundo ponto.
 */
export function decidirPedido(
  e: EstadoPontos,
  lat: number,
  lng: number,
  geometria?: PosicaoGeoJson[][] | null,
  estudoUltra = false,
): DecisaoPedido {
  const pedido: PontoPendente = { lat, lng, geometria: geometria ?? null }
  let repetido = geometria?.length
    ? indiceDaMesmaArea(e.fichas, geometria)
    : indiceDoMesmoPonto(e.fichas, lat, lng)
  if (repetido < 0 && estudoUltra && !geometria?.length) {
    repetido = indiceDaMesmaUnidade(e.fichas, lat, lng)
  }
  if (repetido >= 0) return { tipo: 'repetido', indice: repetido }
  if (e.pendentes.some((p) => mesmoPedido(p, pedido))) return { tipo: 'esperando' }
  /* A área desenhada OCUPA UMA VAGA como qualquer ponto: ela entra na mesma comparação,
     com uma das cinco cores de identidade. */
  if (e.fichas.length + e.pendentes.length >= MAX_PONTOS) return { tipo: 'cheio' }
  return { tipo: 'ler' }
}

/**
 * Aplica um pedido ao estado. `cheio` e `esperando` não mudam nada.
 *
 * Pedir de novo o que já está na lista é ESCOLHER aquele item: abre a aba, mostra a
 * janela e sobe o `foco` (o mapa vai até ele). Pedido novo devolve a precedência ao
 * pendente (`abaFixada: false`) — ele passa a ser o gesto mais recente.
 */
export function pedir(
  e: EstadoPontos,
  lat: number,
  lng: number,
  geometria?: PosicaoGeoJson[][] | null,
  doMapa = false,
  estudoUltra = false,
): EstadoPontos {
  const d = decidirPedido(e, lat, lng, geometria, estudoUltra)
  if (d.tipo === 'repetido') {
    return { ...e, aberto: d.indice, revelar: e.revelar + 1, foco: e.foco + 1, abaFixada: true }
  }
  if (d.tipo === 'ler') {
    const novo: PontoPendente = geometria?.length ? { lat, lng, geometria } : { lat, lng }
    if (doMapa) novo.doMapa = true
    if (estudoUltra && !geometria?.length) novo.estudoUltra = true
    return { ...e, pendentes: [...e.pendentes, novo], abaFixada: false }
  }
  return e
}

/**
 * A leitura de `pedido` chegou.
 *
 * Só entra se o pedido AINDA estiver pendente: depois de "Limpar tudo", uma resposta que
 * chega atrasada não pode ressuscitar um ponto que o operador acabou de tirar da tela.
 * A ficha nova entra no fim e vira a aberta — quem acabou de pedir quer ver ela.
 *
 * EXCETO quando o operador escolheu uma aba enquanto esperava (`abaFixada`): aí a ficha
 * entra na lista (o pin dela deixa de ser provisório) mas a aba aberta continua a que ele
 * escolheu. Roubar a aba de quem acabou de clicar nela é o "a tela mudou sozinha".
 */
export function chegou(e: EstadoPontos, pedido: PontoPendente, ficha: PontoPayload): EstadoPontos {
  const i = e.pendentes.findIndex((p) => mesmoPedido(p, pedido))
  if (i < 0) return e
  const pendentes = e.pendentes.filter((_, k) => k !== i)
  /* O servidor devolve a coordenada com 6 casas e o pedido pode ter mais; a chave de 5
     casas absorve isso, mas se mesmo assim a ficha já existir (dois caminhos chegaram ao
     mesmo imóvel), abre a que existe em vez de duplicar. Área casa com área, pelos
     vértices — nunca com o ponto que por acaso esteja no `representative_point` dela. */
  const repetido = ficha.geometria?.length
    ? indiceDaMesmaArea(e.fichas, ficha.geometria)
    : indiceDoMesmoPonto(e.fichas, ficha.lat, ficha.lng)
  if (e.abaFixada) {
    return repetido >= 0 ? { ...e, pendentes } : { ...e, fichas: [...e.fichas, ficha], pendentes }
  }
  if (repetido >= 0) return { ...e, pendentes, aberto: repetido, revelar: e.revelar + 1 }
  const fichas = [...e.fichas, ficha]
  return { ...e, fichas, pendentes, aberto: fichas.length - 1, revelar: e.revelar + 1 }
}

/**
 * A ficha de um ponto JÁ NA LISTA foi relida em outro modo (estudo de ponto <-> estudo da
 * unidade Ultra, emenda da DEC-070): troca a ficha NO LUGAR, sem mexer na aba aberta, na
 * ordem nem na cor do ponto. Casa pela coordenada, e não pelo índice: se o operador tirou
 * um ponto antes enquanto a releitura voava, o índice antigo apontaria para outro. Ponto
 * que saiu da lista nesse meio-tempo não volta (a resposta é descartada). Área desenhada
 * não troca de modo.
 */
export function substituir(e: EstadoPontos, ficha: PontoPayload): EstadoPontos {
  if (ficha.geometria?.length) return e
  const i = indiceDoMesmoPonto(e.fichas, ficha.lat, ficha.lng)
  if (i < 0) return e
  const fichas = e.fichas.map((f, k) => (k === i ? ficha : f))
  return { ...e, fichas }
}

/** A leitura de `pedido` falhou: o pin provisório sai, as fichas já lidas ficam. */
export function falhou(e: EstadoPontos, pedido: PontoPendente): EstadoPontos {
  const pendentes = e.pendentes.filter((p) => !mesmoPedido(p, pedido))
  return pendentes.length === e.pendentes.length ? e : { ...e, pendentes }
}

/**
 * Abre a aba `i` (presa ao intervalo válido) — e é uma ESCOLHA do operador: sobe o `foco`
 * mesmo quando `i` já é a aberta (clicar de novo no ponto aberto o traz de volta ao mapa)
 * e fixa a aba contra um pedido ainda em leitura (`abaFixada`).
 */
export function abrir(e: EstadoPontos, i: number): EstadoPontos {
  if (!e.fichas.length) return e
  const aberto = Math.max(0, Math.min(i, e.fichas.length - 1))
  return { ...e, aberto, foco: e.foco + 1, abaFixada: true }
}

/**
 * Abre a aba `i` E mostra a janela — o clique num pin colorido do mapa.
 *
 * Antes o clique no pin pedia de novo a coordenada da ficha (`pedir` devolvia `repetido`,
 * abria a aba e subia o `revelar`). Com a ÁREA DESENHADA na lista isso deixou de servir: a
 * coordenada da área é o ponto central dela, e pedi-la de novo leria um PONTO novo ali em
 * vez de abrir a área. Abrir pelo ÍNDICE vale para os dois e não depende de coordenada.
 */
export function mostrar(e: EstadoPontos, i: number): EstadoPontos {
  if (i < 0 || i >= e.fichas.length) return e
  return { ...e, aberto: i, revelar: e.revelar + 1, foco: e.foco + 1, abaFixada: true }
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
 * Tira TUDO: fichas e pins provisórios. O `revelar` e o `foco` não voltam a zero de
 * propósito — são contadores de eventos, e voltar a um valor já visto faria a tela
 * confundir um evento novo com um antigo.
 */
export function limpar(e: EstadoPontos): EstadoPontos {
  return { ...PONTOS_VAZIO, revelar: e.revelar, foco: e.foco }
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
  /** O ativo é um pendente pedido por clique no próprio mapa (ver `PontoPendente.doMapa`). */
  doMapa: boolean
}

/** O pendente que comanda o mapa, se algum: o mais recente, a menos que uma aba tenha sido escolhida depois dele. */
function pendenteAtivo(e: EstadoPontos): PontoPendente | null {
  if (e.abaFixada) return null
  return e.pendentes[e.pendentes.length - 1] ?? null
}

/**
 * A REGRA DE PRECEDÊNCIA: o pendente mais recente vence; sem pendente, a aba aberta.
 *
 * O pendente vence porque é o último gesto do operador — ele acabou de pedir aquele lugar,
 * e o mapa ficar parado no ponto anterior até a resposta chegar é o "não reagiu" que leva
 * a pessoa a clicar de novo. Pela mesma razão, uma aba escolhida DEPOIS do pedido
 * (`abaFixada`) vence o pendente: o último gesto passou a ser ela.
 */
export function itemAtivo(e: EstadoPontos): PontoAtivo | null {
  const p = pendenteAtivo(e)
  if (p) {
    return {
      lat: p.lat,
      lng: p.lng,
      hexId: latLngToCell(p.lat, p.lng, 7),
      territorio: null,
      doMapa: p.doMapa === true,
    }
  }
  const f = e.fichas[e.aberto]
  if (!f) return null
  return {
    lat: f.lat,
    lng: f.lng,
    hexId: f.hex_id,
    territorio: { uf: f.local.uf ?? '', municipio: f.local.municipio ?? '' },
    doMapa: false,
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
  /**
   * O lugar já está na tela (clique no próprio mapa): o `HexMap` NÃO voa nem aproxima a
   * câmera para este pin. Só aparece quando `true`.
   */
  semVoo?: boolean
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
 * quando o pin muda de identidade) que devolve o contorno ao hexágono do ponto. Se o pin
 * era de um clique no mapa, o novo HERDA o `semVoo`: o ponto continua sob o cursor.
 *
 * `forcar` (o operador ESCOLHEU o item: aba, pin colorido, pedido repetido) sempre dá
 * objeto novo e com voo — é o "leve-me até ele", mesmo que ele já seja o ativo.
 */
export function pinParaAtivo(
  atual: PinDoMapa | null,
  ativo: PontoAtivo,
  territorioMuda: boolean,
  forcar = false,
): PinDoMapa {
  const novo: PinDoMapa = { lat: ativo.lat, lng: ativo.lng, hexId: ativo.hexId }
  if (forcar) return novo
  const mesmoLugar =
    atual != null &&
    chaveDaCoordenada(atual.lat, atual.lng) === chaveDaCoordenada(ativo.lat, ativo.lng)
  if (mesmoLugar && !territorioMuda) return atual
  if (ativo.doMapa || (mesmoLugar && atual.semVoo)) novo.semVoo = true
  return novo
}

/**
 * O que o mapa faz quando o ativo da lista muda (o efeito do `App`).
 *
 * - `focar`: o operador escolheu um item (`foco` subiu). Pin NOVO, com voo, e o território
 *   do item volta — mesmo que ele já fosse o ativo, mesmo que o mapa tenha sido arrastado
 *   ou que o operador tenha trocado de município à mão antes.
 * - `seguir`: o ativo mudou por outro motivo (pedido novo, leitura que chegou, remoção):
 *   o pin acompanha, reaproveitando o objeto quando nada mudou para o mapa.
 * - `nenhum`: nada a fazer — a chave é a mesma, OU o ponto perdeu o comando da câmera
 *   (`soltou`: o operador foi a outro destino à mão) e o que mudou foi só o território
 *   de um pedido que já estava em voo. Uma resposta atrasada não pode desfazer a
 *   navegação que o operador fez enquanto esperava (ranking nacional, troca de município,
 *   unidade da rede).
 */
export type MovimentoDoMapa = 'nenhum' | 'seguir' | 'focar'

export interface MarcaDoAtivo {
  /** `chaveDoAtivo` do item ativo. */
  chave: string | null
  /** `EstadoPontos.foco` no mesmo instante. */
  foco: number
}

export function movimentoDoMapa(
  antes: MarcaDoAtivo,
  agora: MarcaDoAtivo,
  soltou: boolean,
): MovimentoDoMapa {
  if (agora.chave == null) return antes.chave == null ? 'nenhum' : 'seguir'
  if (agora.foco !== antes.foco) return 'focar'
  if (agora.chave === antes.chave) return 'nenhum'
  if (soltou && antes.chave != null && coordenadaDaChave(antes.chave) === coordenadaDaChave(agora.chave)) {
    return 'nenhum'
  }
  return 'seguir'
}

/** A metade "coordenada" de uma `chaveDoAtivo` (antes do `|` do território). */
function coordenadaDaChave(chave: string): string {
  return chave.split('|')[0]
}

/**
 * A janela da ficha nasce aberta nesta montagem?
 *
 * Só na volta do Simulador aberto pela própria ficha, e só se ainda houver ponto. Qualquer
 * outra remontagem com pontos na lista (Executiva e de volta, ranking nacional, aba de
 * imóveis) nasce fechada: ali o operador foi a outro destino, e a ficha de ponto reabrindo
 * sozinha cobriria a ficha dele.
 */
export function janelaNaMontagem(voltaDoSimulador: boolean, nFichas: number): boolean {
  return voltaDoSimulador && nFichas > 0
}

/**
 * O erro da leitura de ponto precisa do aviso FLUTUANTE?
 *
 * O erro tem duas casas: a caixa de colar (o `CampoPonto` dela o mostra) e este aviso.
 * Sem ficha na tela não há caixa no Explorar; COM ficha a caixa some depois do 1o ponto,
 * e os pedidos seguintes chegam pela lupa, pelo "Selecionar ponto" e pelo "Analisar
 * geometria" — o 6o ponto, o clique no mar ou a área recusada falhavam sem nenhum sinal.
 * Durante uma leitura o aviso espera: o "Lendo os setores..." ocupa o mesmo lugar.
 */
export function erroFlutuanteVisivel(c: {
  nFichas: number
  caixaAberta: boolean
  carregando: boolean
  erro: string | null
}): boolean {
  if (!c.erro || c.carregando) return false
  // Com ficha e a caixa de colar aberta, o `CampoPonto` dela já mostra o erro.
  return !(c.caixaAberta && c.nFichas > 0)
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
  // A mesma precedência de `itemAtivo`: o pendente, salvo aba escolhida depois dele.
  const ativo = pendenteAtivo(e) ? itens.length - 1 : e.fichas.length ? e.aberto : null
  /* A área em leitura já se chama "Área desenhada" (o nome dela não depende do servidor);
     o ponto em leitura fica com a coordenada, porque o bairro ainda não é conhecido. */
  const rotulos = [
    ...rotulosDosPontos(e.fichas),
    ...e.pendentes.map((p) =>
      p.geometria?.length ? ROTULO_AREA_DESENHADA : `${p.lat.toFixed(4)}, ${p.lng.toFixed(4)}`,
    ),
  ]
  return pinsDaComparacao(itens, ativo, rotulos).map((p) => ({
    ...p,
    carregando: p.indice >= e.fichas.length,
  }))
}
