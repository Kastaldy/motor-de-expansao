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

/** Rotulo curto de um ponto: bairro, senao municipio, senao a coordenada. */
export function rotuloDoPonto(p: PontoPayload): string {
  return (
    p.local?.bairro ??
    p.local?.municipio ??
    `${p.lat.toFixed(4)}, ${p.lng.toFixed(4)}`
  )
}

export function compararPontos(
  a: PontoPayload,
  b: PontoPayload,
): Comparacao<PontoPayload> {
  return compararDimensoesComFrase(DIMENSOES_PONTO, a, b, rotuloDoPonto(a), rotuloDoPonto(b))
}

/**
 * Teto de pontos na comparacao.
 *
 * Quatro porque a tabela e' de DUAS colunas: acima disso o operador escolhe pares num
 * seletor que ja e' mais trabalho do que colar de novo. E cada ponto custa uma leitura
 * de particao de municipio no servidor.
 */
export const MAX_PONTOS = 4
