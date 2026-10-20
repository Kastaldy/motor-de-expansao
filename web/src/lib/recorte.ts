/**
 * O RECORTE de uma leitura, em texto de usuário — e a pergunta "é área desenhada?".
 *
 * Fonte ÚNICA (revisão do PR #457, 2026-10-16). Antes havia DUAS `ehAreaDesenhada` (uma em
 * `comparacao-pontos`, outra em `rodape-ponto`, com regras diferentes) e o mesmo raio saía
 * escrito de dois jeitos na mesma tela: "raio de 1.000 m" no subtítulo e no comparativo,
 * "raio de 1,0 km" na conta do mercado. Agora todo texto de raio passa por `rotuloDoRaio`
 * e todo texto de área por `rotuloDaAreaDesenhada`.
 *
 * Os números são formatados SEM depender do locale da instância (vírgula decimal fixa),
 * como a conta do mercado já fazia.
 */

import type { PontoPayload } from './types'

/** Raio padrão do produto quando o payload não traz `raio_km` (DEC-021). */
export const RAIO_PADRAO_KM = 1

/**
 * O item é uma ÁREA DESENHADA (DEC-071), e não um ponto com raio?
 *
 * Pela `geometria` do payload PRIMEIRO, e só depois pelo `grao` do mercado: quando o
 * cálculo de mercado falha no servidor, o bloco volta sem `grao` — e, lida só por ele, a
 * área desenhada destravaria o "Estudo", que geraria o PDF do RAIO em volta do ponto
 * interno dela, com o nome da área. Um PDF certo sobre o recorte errado.
 */
export function ehAreaDesenhada(
  p: Partial<Pick<PontoPayload, 'geometria' | 'mercado' | 'recorte'>> | null | undefined,
): boolean {
  /* O ALCANCE (DEC-074) também pode vir com `grao === 'geometria'` — a isócrona de 10 min
     é calculada como polígono no servidor —, mas NÃO é área desenhada: o ponto é o que o
     operador clicou, o Estudo e o Simulador falam dele. Quando o servidor diz o tipo do
     recorte, é o tipo que manda. */
  const tipo = p?.recorte?.tipo
  if (tipo && tipo !== 'poligono') return false
  return !!p?.geometria?.length || p?.mercado?.grao === 'geometria'
}

/** Os tipos de recorte que a tela conhece (identificadores crus). */
export type TipoRecorte = 'raio_1km' | 'raio_2km' | 'carro_5min' | 'carro_10min' | 'poligono'

const TIPOS_RECORTE: readonly string[] = ['raio_1km', 'raio_2km', 'carro_5min', 'carro_10min', 'poligono']

/**
 * O TEMPO de cada isócrona (DEC-074 e Emenda 1). É a única coisa que muda entre os
 * alcances de carro: os rótulos saem daqui, em vez de cada tela repetir o caso de 10 min.
 */
export const MINUTOS_DO_CARRO: Readonly<Record<'carro_5min' | 'carro_10min', number>> = Object.freeze({
  carro_5min: 5,
  carro_10min: 10,
})

/** Os minutos de carro do recorte, ou `null` quando ele não é uma isócrona. */
export function minutosDoRecorte(tipo: TipoRecorte | null | undefined): number | null {
  return tipo === 'carro_5min' || tipo === 'carro_10min' ? MINUTOS_DO_CARRO[tipo] : null
}

/**
 * O TIPO do recorte de um item (identificador cru, NÃO acentuar): `'raio_1km'`,
 * `'raio_2km'`, `'carro_5min'`/`'carro_10min'` (isócrona, DEC-074) ou `'poligono'` (área desenhada à mão,
 * DEC-071).
 *
 * Pelo `recorte.tipo` do servidor quando ele vem; payload anterior à chave cai na regra de
 * sempre — área desenhada pelo `ehAreaDesenhada`, senão o raio pelo `raio_km` (2 km é o
 * único raio além do de 1 km que a tela conhece).
 */
export function tipoDoRecorte(
  p: Partial<Pick<PontoPayload, 'raio_km' | 'geometria' | 'mercado' | 'recorte'>> | null | undefined,
): TipoRecorte {
  const tipo = p?.recorte?.tipo
  if (tipo && TIPOS_RECORTE.includes(tipo)) return tipo
  if (ehAreaDesenhada(p)) return 'poligono'
  return p?.raio_km != null && Math.abs(p.raio_km - 2) < 1e-9 ? 'raio_2km' : 'raio_1km'
}

/** Quilômetros com no máximo uma casa e sem ",0" sobrando: 1 -> "1", 1,5 -> "1,5". */
function kmCurto(v: number): string {
  const arred = Math.round(v * 10) / 10
  return Number.isInteger(arred) ? String(arred) : arred.toFixed(1).replace('.', ',')
}

/** "raio de 1 km" / "raio de 1,5 km". Sem raio conhecido, vale o raio padrão do produto. */
export function rotuloDoRaio(raioKm: number | null | undefined): string {
  return `raio de ${kmCurto(raioKm ?? RAIO_PADRAO_KM)} km`
}

/** Área em km² com duas casas abaixo de 10 km² e uma acima, vírgula fixa: "2,40" / "38,2". */
function areaCurta(areaKm2: number): string {
  return areaKm2.toFixed(areaKm2 < 10 ? 2 : 1).replace('.', ',')
}

/** "área desenhada de 2,40 km²" (duas casas abaixo de 10 km², uma acima); sem área, só o nome. */
export function rotuloDaAreaDesenhada(areaKm2: number | null | undefined): string {
  if (areaKm2 == null || Number.isNaN(areaKm2)) return 'área desenhada'
  return `área desenhada de ${areaCurta(areaKm2)} km²`
}

/**
 * "10 min de carro, sem trânsito · 38,2 km²" — a isócrona (DEC-074). O "sem trânsito" é
 * parte do recorte, não enfeite: o serviço de rotas calcula com a velocidade da via, e a
 * mesma origem na hora do rush alcançaria bem menos. Sem área, só o tempo. `minutos` é o
 * da isócrona (5 ou 10, `MINUTOS_DO_CARRO`); o default é o alcance original da DEC-074.
 */
export function rotuloDaIsocrona(areaKm2: number | null | undefined, minutos = 10): string {
  const base = `${minutos} min de carro, sem trânsito`
  if (areaKm2 == null || Number.isNaN(areaKm2)) return base
  return `${base} · ${areaCurta(areaKm2)} km²`
}
