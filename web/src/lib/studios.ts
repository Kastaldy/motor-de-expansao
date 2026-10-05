/**
 * Studios da aba Viabilidade (2026-10-05) — funções PURAS do estado da tela.
 *
 * Cada studio (0..3) atende uma fatia própria da demanda assumida e cobra um ticket
 * próprio; o split balcão/agregador vale só sobre a demanda restante. A conta é do
 * motor (`dimensionamento/simulador.py`): aqui só se guarda e se recorta o que o
 * operador digitou.
 *
 * A tela guarda SEMPRE as três posições e só recorta as `n` ativas na hora de mandar.
 * Assim, baixar de 3 para 1 studio e voltar devolve os tickets que o operador já tinha
 * digitado, em vez de ressuscitar o padrão.
 */

/** Teto de studios aceito pelo backend (`n_studios` com `le=3`). */
export const STUDIOS_MAX = 3

/**
 * Ticket padrão de cada studio, em reais por mês, na ordem (escada 157/167/177).
 * ESPELHO de `SIM_TICKETS_STUDIO_PADRAO` em `src/motor_expansao/dimensionamento/config.py`:
 * é o valor INICIAL das caixas; o motor só usa o que a tela manda em `tickets_studios`.
 */
export const TICKETS_STUDIO_PADRAO: readonly number[] = [157, 167, 177]

/** Normaliza o número de studios digitado: inteiro em 0..STUDIOS_MAX (lixo vira 0). */
export function clampNStudios(valor: unknown): number {
  const n = Math.round(Number(valor))
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(STUDIOS_MAX, n))
}

/** Os tickets que vão no payload: as `n` primeiras posições (n normalizado). Posição
 *  AUSENTE (ou NaN) cai no padrão daquela posição. Um valor digitado, mesmo 0, segue
 *  como está: o backend recusa ticket <= 0 com 422, e trocar em silêncio por outro
 *  número faria a caixa mostrar uma coisa e o cálculo usar outra. */
export function ticketsAtivos(tickets: readonly number[], n: number): number[] {
  const k = clampNStudios(n)
  const out: number[] = []
  for (let i = 0; i < k; i++) {
    const t = tickets[i]
    out.push(typeof t === 'number' && Number.isFinite(t) ? t : TICKETS_STUDIO_PADRAO[i])
  }
  return out
}

/** Troca o ticket de UM studio, preservando as outras posições (inclusive as
 *  inativas). Índice fora de 0..STUDIOS_MAX-1 devolve a lista intacta. */
export function definirTicketStudio(
  tickets: readonly number[],
  indice: number,
  valor: number,
): number[] {
  const base = Array.from({ length: STUDIOS_MAX }, (_, i) => tickets[i] ?? TICKETS_STUDIO_PADRAO[i])
  if (!Number.isInteger(indice) || indice < 0 || indice >= STUDIOS_MAX) return base
  base[indice] = valor
  return base
}
