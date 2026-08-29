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

import { compararDimensoesComFrase, type Comparacao, type Dimensao } from './comparacao'
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
    rotulo: 'População no raio',
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
    unidade: 'R$',
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
  pontos: readonly PontoPayload[],
  lat: number,
  lng: number,
): number {
  const chave = (a: number, b: number) => chaveDaCoordenada(a, b)
  const alvo = chave(lat, lng)
  return pontos.findIndex((p) => chave(p.lat, p.lng) === alvo)
}

/* A paleta de identidade MUDOU DE CASA em 2026-08-13: virou `CORES_IDENTIDADE` /
   `corDeIdentidade` em `lib/comparacao`, porque deixou de ser "cor do ponto" — os
   hexagonos em comparacao passaram a usar a MESMA paleta, e manter a fonte da verdade
   dentro do modulo de pontos faria a segunda tela importar de um lugar que nao a
   descreve. `corDoPonto` continua existindo aqui como o nome que a tela de pontos usa. */
export { CORES_IDENTIDADE as CORES_PONTO, corDeIdentidade as corDoPonto } from './comparacao'

/** Rotulo curto de um ponto: bairro, senao municipio, senao a coordenada. */
export function rotuloDoPonto(p: PontoPayload): string {
  return (
    p.local?.bairro ??
    p.local?.municipio ??
    `${p.lat.toFixed(4)}, ${p.lng.toFixed(4)}`
  )
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
 * A DESAMBIGUACAO E' POSICIONAL, e so' entra quando ha' empate: um numero na frente, o
 * MESMO que a aba mostra e o mapa usa para marcar o ponto. Numerar sempre seria ruido
 * para quem comparou dois bairros de nomes distintos, que e' o caso comum.
 *
 * Nao inventa nome: nao ha' de onde tirar "Setor Bueno" quando o servidor devolveu
 * bairro nulo. O que se pode garantir e' que duas linhas nunca digam a mesma coisa.
 */
export function rotulosDosPontos(pontos: PontoPayload[]): string[] {
  const bases = pontos.map(rotuloDoPonto)
  const vezes = new Map<string, number>()
  for (const b of bases) vezes.set(b, (vezes.get(b) ?? 0) + 1)
  return bases.map((b, i) => ((vezes.get(b) ?? 0) > 1 ? `${i + 1} · ${b}` : b))
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
