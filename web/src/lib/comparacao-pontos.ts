/**
 * Comparacao entre PONTOS colados no modo de imovel.
 *
 * Terceiro consumidor do mesmo nucleo (`compararDimensoesComFrase`), depois de
 * hexagonos e municipios: as regras que importam — dois limiares, no maximo 3
 * dimensoes na frase, "porem" separando vantagem de desvantagem — existem UMA vez.
 *
 * O QUE ENTRA NA COMPARACAO. So' o que o `/api/ponto` devolve para os DOIS lados. A
 * viabilidade fica de fora de proposito: por DEC-009 a demanda e' premissa digitada, e
 * dois imoveis com a mesma metragem e o mesmo aluguel produzem DRE identico — duas
 * colunas com os mesmos numeros, que o operador leria como defeito. O que muda entre
 * pontos e' o contexto (quem mora em volta, quanto sobra de mercado, quem ja disputa),
 * e e' isso que a tabela compara.
 */

import {
  compararDimensoesComFrase,
  corDeIdentidadeRgb,
  rotulosPartidos,
  rotulosUnicos,
  type Comparacao,
  type Dimensao,
  type RotuloPartido,
} from './comparacao'
import { UNIDADE_MOEDA, num } from './format'
import type { PontoPayload } from './types'

/**
 * Ordem de PRIORIDADE, a mesma dos hexagonos: residual primeiro (a pergunta do
 * produto), contexto socioeconomico depois.
 */
export const DIMENSOES_PONTO: readonly Dimensao<PontoPayload>[] = Object.freeze([
  Object.freeze({
    chave: 'residual',
    rotulo: 'Residual disponível',
    ler: (p: PontoPayload) => p.mercado?.residual ?? null,
    unidade: 'alunos',
    maiorEhMelhor: true,
    limiarRelativo: 0.1,
    limiarAbsoluto: 100,
  }),
  Object.freeze({
    chave: 'populacao',
    /* "População", sem "no raio": desde a DEC-071 a comparação pode ter uma ÁREA DESENHADA
       ao lado dos pontos, e o rótulo vale para os dois recortes. O recorte de cada item é
       dito no rodapé do comparativo; a frase do veredito fica "menos população que B". */
    rotulo: 'População',
    ler: (p: PontoPayload) => p.censo?.populacao ?? null,
    unidade: 'pessoas',
    maiorEhMelhor: true,
    limiarRelativo: 0.1,
    limiarAbsoluto: 500,
  }),
  Object.freeze({
    chave: 'concorrentes',
    rotulo: 'Concorrentes',
    ler: (p: PontoPayload) => p.concorrencia?.n_concorrentes ?? null,
    unidade: '',
    // Unica invertida: menos concorrente e' melhor.
    maiorEhMelhor: false,
    limiarRelativo: 0.1,
    /* Aqui o limiar pode ser 1, e nao 2 como nos hexagonos: no modo de ponto o numero
       e' CONTAGEM REAL de pins dentro de 1,0 km (`_points_in_radius`), nao a oferta
       ponderada por distancia que o mapa estima. Um concorrente a mais e' um
       concorrente a mais. */
    limiarAbsoluto: 1,
  }),
  Object.freeze({
    chave: 'renda_domiciliar',
    rotulo: 'Renda domiciliar',
    ler: (p: PontoPayload) => p.censo?.renda_media_domiciliar ?? null,
    unidade: UNIDADE_MOEDA,
    maiorEhMelhor: true,
    limiarRelativo: 0.1,
    limiarAbsoluto: 300,
  }),
  Object.freeze({
    chave: 'score',
    rotulo: 'Potencial socioeconômico',
    ler: (p: PontoPayload) => p.censo?.score_socioeconomico ?? null,
    unidade: 'score',
    maiorEhMelhor: true,
    limiarRelativo: 0.1,
    limiarAbsoluto: 5,
  }),
  Object.freeze({
    chave: 'densidade',
    rotulo: 'Densidade',
    ler: (p: PontoPayload) => p.censo?.densidade_hab_km2 ?? null,
    unidade: 'hab/km²',
    maiorEhMelhor: true,
    limiarRelativo: 0.1,
    limiarAbsoluto: 500,
  }),
])

/**
 * O ponto passa em TODOS os criterios do estudo que foi possivel avaliar?
 *
 * `null` quando nenhum criterio foi avaliado — e' "nao sei", nao "reprovou". Criterio com
 * `passa: null` (sem dado) fica FORA da conta pelo mesmo motivo: o servidor declara que
 * ausencia nunca deve ser lida como reprovacao.
 *
 * Binario de proposito. Nao conta quantos criterios o ponto cumpre nem os soma: contar
 * seria inventar um "score de aprovacao do imovel", que e' definicao nova de viabilidade
 * e exige DEC (ver `_criterios_do_ponto` no servidor). Aqui e' a mesma pergunta de
 * sim-ou-nao que o deck ja' imprime ao lado do nome de cada ponto.
 */
export function passaNoEstudo(p: PontoPayload): boolean | null {
  const r = resumoDoEstudo(p)
  return r && r.avaliados > 0 ? r.cumpridos === r.avaliados : null
}

/** Quantos criterios o ponto cumpre, de quantos foi possivel avaliar. */
export interface ResumoEstudo {
  cumpridos: number
  avaliados: number
}

/**
 * A leitura ABSOLUTA do ponto: quantos pisos do produto ele cumpre.
 *
 * Complementa o "lidera em X de N", que e' RELATIVO ao conjunto comparado — trocar de
 * concorrente na comparacao muda aquele numero e nao muda este. As duas respondem
 * perguntas diferentes e a decisao precisa das duas: um imovel pode ganhar a comparacao
 * porque os outros sao piores, e ainda assim nao alcancar a regua do estudo.
 *
 * `null` quando nenhum criterio foi avaliado. Criterio com `passa: null` (sem dado) fica
 * de fora da conta — do numerador E do denominador —, porque o servidor declara que
 * ausencia nunca se le como reprovacao.
 */
export function resumoDoEstudo(p: PontoPayload): ResumoEstudo | null {
  const avaliados = (p.criterios ?? []).filter((c) => c.passa != null)
  if (!avaliados.length) return null
  return { cumpridos: avaliados.filter((c) => c.passa === true).length, avaliados: avaliados.length }
}

/**
 * Casas decimais que definem "a mesma coordenada". 5 casas ≈ 1 metro.
 *
 * Nao e' igualdade exata de ponto flutuante de proposito: o mesmo endereco pode voltar
 * do servidor com o ultimo digito diferente conforme o caminho (coordenada colada, link
 * curto expandido, geocodificacao), e duas leituras a 30 cm uma da outra sao o mesmo
 * imovel para qualquer pergunta que este produto faz — o raio de analise e' de 1.000 m.
 */
export const CASAS_COORD = 5

/**
 * Onde este ponto JA ESTA na lista, ou -1.
 *
 * Existe porque dar Enter duas vezes na mesma coordenada acrescentava um segundo ponto
 * identico: duas abas com o mesmo nome, e uma comparacao de um ponto contra ele mesmo,
 * em que toda dimensao empata (relato do Juan, 2026-08-12). Repetir a busca e' um gesto
 * normal — quem nao viu a tela reagir tenta de novo —, entao a tela e' que precisa
 * absorver a repeticao, em vez de transformar cada Enter num item novo.
 */
/**
 * A identidade de um ponto: a coordenada arredondada em `CASAS_COORD`.
 *
 * Publicada porque DOIS lugares precisam da mesma nocao de "e' o mesmo ponto": esta
 * funcao, que evita duplicar a ficha, e a tela, que decide se leva o mapa ate' ele. A
 * tela usava o `hex_id` para isso e errava — um hexagono res-7 tem ~5 km2, entao dois
 * enderecos a mais de 1 km um do outro cabem no mesmo, e o mapa ficava parado no primeiro
 * enquanto a janela ja' mostrava o segundo (relato do Juan, 2026-08-14).
 */
export function chaveDaCoordenada(lat: number, lng: number): string {
  return `${lat.toFixed(CASAS_COORD)},${lng.toFixed(CASAS_COORD)}`
}

export function indiceDoMesmoPonto(
  pontos: readonly Pick<PontoPayload, 'lat' | 'lng' | 'geometria'>[],
  lat: number,
  lng: number,
): number {
  const chave = (a: number, b: number) => chaveDaCoordenada(a, b)
  const alvo = chave(lat, lng)
  /* ÁREA DESENHADA NÃO É PONTO (DEC-071). O `lat`/`lng` dela é o `representative_point`
     do polígono — um lugar que o operador nunca clicou —, e casar por ele faria buscar
     exatamente aquela coordenada abrir a ficha da ÁREA em vez de ler o ponto com raio. */
  return pontos.findIndex((p) => !p.geometria?.length && chave(p.lat, p.lng) === alvo)
}

/**
 * A identidade de uma ÁREA DESENHADA: os vértices do anel, arredondados em `CASAS_COORD`.
 *
 * Desenhar de novo o MESMO polígono (vértice a vértice) é repetição, como colar duas vezes
 * a mesma coordenada; qualquer vértice diferente é outra área.
 */
export function chaveDaArea(geometria: readonly (readonly PosicaoGeoJson[])[]): string {
  const anel = geometria[0] ?? []
  return `area:${anel.map(([x, y]) => chaveDaCoordenada(y, x)).join(';')}`
}

/** Onde esta área JÁ ESTÁ na lista, ou -1. Só casa com itens de área — nunca com ponto. */
export function indiceDaMesmaArea(
  itens: readonly Pick<PontoPayload, 'geometria'>[],
  geometria: readonly (readonly PosicaoGeoJson[])[],
): number {
  const alvo = chaveDaArea(geometria)
  return itens.findIndex((p) => !!p.geometria?.length && chaveDaArea(p.geometria) === alvo)
}

/** O item é uma ÁREA DESENHADA (DEC-071), e não um ponto com raio? */
export function ehAreaDesenhada(p: Pick<PontoPayload, 'geometria'> | null | undefined): boolean {
  return !!p?.geometria?.length
}

/**
 * Por que o PDF de comparação NÃO sai para esta lista — ou `null` quando sai.
 *
 * Fase 1 da DEC-071: área desenhada é só TELA. O deck de comparação fotografa cada item com
 * o raio de 1 km e escreve "raio" nos textos; para uma área ele afirmaria um recorte que não
 * é o dela. A recusa é dita (com o caminho para destravar), e não um botão que some.
 */
export function motivoSemPdfDeComparacao(
  fichas: readonly Pick<PontoPayload, 'geometria'>[],
): string | null {
  if (!fichas.some((f) => ehAreaDesenhada(f))) return null
  return (
    'O PDF de comparação ainda não aceita área desenhada — ele chega na próxima fase. ' +
    'Remova as áreas desenhadas da comparação para gerar o PDF dos pontos.'
  )
}

/** Rótulo da área desenhada nas abas, na legenda e no mapa ("#k" quando há mais de uma). */
export const ROTULO_AREA_DESENHADA = 'Área desenhada'

/**
 * O recorte da leitura em texto de usuário: "raio de 1.000 m" ou "área desenhada de
 * 2,40 km²". É o que substitui o "raio de X m" escrito à mão nas fichas — com uma área
 * desenhada na lista, aquele texto passaria a mentir sobre ela.
 */
export function rotuloDoRecorte(
  p: Pick<PontoPayload, 'raio_km' | 'geometria' | 'recorte' | 'mercado'>,
): string {
  if (ehAreaDesenhada(p)) {
    const area = p.recorte?.area_km2 ?? p.mercado?.area_km2 ?? null
    return area != null
      ? `área desenhada de ${area.toFixed(area < 10 ? 2 : 1).replace('.', ',')} km²`
      : 'área desenhada'
  }
  return `raio de ${num((p.raio_km ?? 1) * 1000)} m`
}

/* A paleta de identidade MUDOU DE CASA em 2026-08-13: virou `CORES_IDENTIDADE` /
   `corDeIdentidade` em `lib/comparacao`, porque deixou de ser "cor do ponto" — os
   hexagonos em comparacao passaram a usar a MESMA paleta, e manter a fonte da verdade
   dentro do modulo de pontos faria a segunda tela importar de um lugar que nao a
   descreve. `corDoPonto` continua existindo aqui como o nome que a tela de pontos usa. */
export { CORES_IDENTIDADE as CORES_PONTO, corDeIdentidade as corDoPonto } from './comparacao'

/** Rotulo curto de um ponto: bairro, senao municipio, senao a coordenada. */
export function rotuloDoPonto(p: PontoPayload): string {
  /* A área desenhada não tem bairro que a nomeie (o bairro do `representative_point` é o
     de um ponto qualquer dentro dela): ela se chama pelo que é. Duas áreas viram "Área
     desenhada #1" e "#2" pela regra comum de `rotulosUnicos`. */
  if (ehAreaDesenhada(p)) return ROTULO_AREA_DESENHADA
  return (
    p.local?.bairro ??
    p.local?.municipio ??
    `${p.lat.toFixed(4)}, ${p.lng.toFixed(4)}`
  )
}

/**
 * O subtitulo do deck de pontos: a cidade, quando ela vale para TODOS, e a contagem.
 *
 * A capa afirmava a cidade do PRIMEIRO ponto (`fichas[0].local.municipio`). No deck de
 * 10/09/2026 os quatro pontos eram dois de Posse/GO e dois de Jatai/GO, e a peca inteira
 * saiu "Posse - 4 pontos" — metade dela falando de outra cidade. E' a MESMA regra que o
 * deck de hexagonos ja' aplica (`MapScreen`, com o mesmo relato: "usar o municipio do
 * primeiro fazia a capa afirmar Sao Paulo"), agora tambem do lado dos pontos.
 *
 * Municipio nao resolvido nao concorda com ninguem: nao se sabe de onde o ponto e',
 * entao a capa se cala em vez de deixar a cidade dos outros afirmar pelo conjunto.
 */
export function subtituloDoDeckDePontos(fichas: readonly PontoPayload[]): string {
  const cidades = new Set(fichas.map((f) => f.local?.municipio ?? null))
  const unica = cidades.size === 1 ? [...cidades][0] : null
  return unica ? `${unica} - ${fichas.length} pontos` : `${fichas.length} pontos`
}

/**
 * Rotulos de uma LISTA de pontos, garantidamente distinguiveis entre si.
 *
 * POR QUE NAO BASTA O `rotuloDoPonto`. Ele olha um ponto por vez, e o nome de um ponto
 * nao e' unico: dois enderecos da mesma cidade sem bairro resolvido viram "Goiânia" e
 * "Goiânia". Nas abas, nos seletores e nos cabecalhos da tabela de comparacao, o operador
 * ficava com duas colunas de nome identico — e a frase do veredito saia "Goiânia é o
 * melhor... Goiânia é o pior" (relato do Juan, 2026-08-12).
 *
 * A regra de desambiguacao e' UMA so', a de `rotulosUnicos` ("Centro #1", "Centro #2",
 * so' quando ha' empate). Ate' 2026-10-14 esta funcao tinha a copia dela, e as duas
 * comparacoes podiam divergir em silencio — agora delega.
 *
 * Nao inventa nome: nao ha' de onde tirar "Setor Bueno" quando o servidor devolveu
 * bairro nulo. O que se pode garantir e' que duas linhas nunca digam a mesma coisa.
 */
export function rotulosDosPontos(pontos: readonly PontoPayload[]): string[] {
  return rotulosUnicos(pontos.map(rotuloDoPonto))
}

/** Os rotulos da lista partidos em nome + "#k" — para o "#k" nao sumir no ellipsis. */
export function rotulosPartidosDosPontos(pontos: readonly PontoPayload[]): RotuloPartido[] {
  return rotulosPartidos(pontos.map(rotuloDoPonto))
}

/** Um vertice de poligono no formato GeoJSON: [lng, lat]. */
export type PosicaoGeoJson = [number, number]

/**
 * O minimo que um item da comparacao precisa para virar pin no mapa.
 *
 * Generico de proposito: alem do `PontoPayload` (ponto do raio de 1 km), a comparacao vai
 * receber uma AREA DESENHADA (DEC-071, fase 1). O pin dela e' o `representative_point` do
 * poligono — vem em `lat`/`lng` como o de qualquer ponto — e o contorno vai em
 * `geometria`, como os aneis do Polygon GeoJSON (coordenadas `[lng, lat]`).
 */
export interface ItemNoMapa {
  lat: number
  lng: number
  hex_id?: string | null
  /** Aneis do Polygon GeoJSON (`coordinates`): o 1o e' o externo. So' item de geometria. */
  geometria?: PosicaoGeoJson[][] | null
}

/** Um pin da comparacao, pronto para o deck.gl. */
export interface PinDaComparacao {
  lat: number
  lng: number
  hexId: string | null
  /** Indice do item na lista — e' por ele que aba, cor e rotulo se casam. */
  indice: number
  /** A cor de identidade do item (a mesma da aba e das barras), em `[r, g, b, a]`. */
  rgb: [number, number, number, number]
  rotulo: string
  /** O item da aba aberta. */
  ativo: boolean
  /** O contorno da area desenhada, quando o item e' de geometria. */
  geometria: PosicaoGeoJson[][] | null
}

/**
 * TODOS os itens da comparacao como pins, cada um na sua cor de identidade.
 *
 * Antes o mapa mostrava so' o ponto da aba aberta, e o operador nao via onde os outros
 * estavam em relacao a ele (decisao do dono, 2026-10-14: todos ao mesmo tempo). A cor
 * sai do INDICE, nunca da ordem de desenho, senao o pin vermelho deixaria de ser o da aba
 * vermelha quando um ponto sai da lista.
 *
 * `rotulos` e' a lista ja' desambiguada (`rotulosDosPontos`); faltando um, cai na
 * coordenada — o mesmo fallback do `rotuloDoPonto` —, para o pin nunca sair sem nome.
 */
export function pinsDaComparacao(
  fichas: readonly ItemNoMapa[],
  aberto: number | null,
  rotulos: readonly string[],
): PinDaComparacao[] {
  return fichas.map((f, i) => ({
    lat: f.lat,
    lng: f.lng,
    hexId: f.hex_id ?? null,
    indice: i,
    rgb: corDeIdentidadeRgb(i),
    rotulo: rotulos[i] ?? `${f.lat.toFixed(4)}, ${f.lng.toFixed(4)}`,
    ativo: i === aberto,
    geometria: f.geometria ?? null,
  }))
}

export function compararPontos(
  a: PontoPayload,
  b: PontoPayload,
  /* Rotulos JA DESAMBIGUADOS, vindos de `rotulosDosPontos`. Sao opcionais so' para nao
     quebrar quem compara dois pontos soltos; a tela sempre os passa, porque a frase do
     veredito nomeia os dois lados e com nomes iguais ela vira "X é o melhor, X é o pior". */
  rotuloA?: string,
  rotuloB?: string,
): Comparacao<PontoPayload> {
  return compararDimensoesComFrase(
    DIMENSOES_PONTO,
    a,
    b,
    rotuloA ?? rotuloDoPonto(a),
    rotuloB ?? rotuloDoPonto(b),
  )
}

/**
 * Teto de pontos na comparacao.
 *
 * CINCO desde 2026-08-13 (pedido do Juan). Eram quatro porque a comparacao era a tabela
 * de DUAS colunas: acima disso o operador escolhia pares num seletor que ja' dava mais
 * trabalho do que colar de novo. Com os BLOCOS POR PARAMETRO todos os pontos entram no
 * mesmo bloco e a escolha de par deixa de existir, entao o teto que a tabela impunha caiu.
 *
 * Cinco, e nao mais: e' o tamanho da paleta de identidade (`CORES_PONTO`), escolhida para
 * as cores se distinguirem entre si no fundo escuro — a sexta cor repetiria e duas abas
 * ficariam iguais. O comentario de la' ja' dizia "cinco porque MAX_PONTOS e' 5"; era o
 * codigo que estava atrasado em relacao ao proprio desenho.
 *
 * Cada ponto ainda custa uma leitura de particao de municipio no servidor.
 */
export const MAX_PONTOS = 5
