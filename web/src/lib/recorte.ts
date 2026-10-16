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
  p: Partial<Pick<PontoPayload, 'geometria' | 'mercado'>> | null | undefined,
): boolean {
  return !!p?.geometria?.length || p?.mercado?.grao === 'geometria'
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

/** "área desenhada de 2,40 km²" (duas casas abaixo de 10 km², uma acima); sem área, só o nome. */
export function rotuloDaAreaDesenhada(areaKm2: number | null | undefined): string {
  if (areaKm2 == null || Number.isNaN(areaKm2)) return 'área desenhada'
  return `área desenhada de ${areaKm2.toFixed(areaKm2 < 10 ? 2 : 1).replace('.', ',')} km²`
}
