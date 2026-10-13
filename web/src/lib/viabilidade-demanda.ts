/* ---------------------------------------------------------------------------
   Viabilidade: de onde nasce a demanda da tela, e o aviso que o perfil manda exibir.

   A demanda e' PREMISSA do operador (DEC-009) — nunca prevista. O unico padrao que a
   tela pode oferecer e' o p50 da faixa de comparaveis (`/api/faixa-alunos`). Ate'
   2026-10-05 havia um segundo padrao, mudo: `useState(800)`. Numa instancia sem base
   de comparaveis (a Argentina: a base e' de unidades brasileiras) o p50 vem `null`, o
   800 sobrava e a tela calculava sozinha com ele — um "reprovado" com cara de
   resultado, saido de um numero que ninguem escolheu.

   Modulo PURO de proposito: `ViabilityScreen.tsx` nao tem teste, entao a regra mora
   aqui, onde o Vitest alcanca sem servidor.
   --------------------------------------------------------------------------- */

/**
 * Demanda com que a tela abre num ponto: o p50 da faixa quando ele existe; senao a
 * demanda que o operador ja' tinha; senao NADA (`null`) — e ai' a tela pede a premissa
 * em vez de calcular.
 */
export function sementeDaDemanda(
  p50: number | null | undefined,
  atual: number | null,
): number | null {
  if (p50 != null && Number.isFinite(p50) && p50 > 0) return Math.round(p50)
  return atual
}

/** Aviso que o perfil do pais declara para a TELA de viabilidade (`avisos.*.onde`). */
export interface AvisoDeViabilidade {
  titulo: string
  texto: string
}

/** Estado do modulo, no molde de `perfil.ts`: nasce ausente (o Brasil nao declara). */
let aviso: AvisoDeViabilidade | null = null

/** Aviso vigente, ou `null` quando o perfil da instancia nao declara nenhum. */
export function avisoDeViabilidade(): AvisoDeViabilidade | null {
  return aviso
}

/**
 * Instala o aviso vindo do `/api/me` (`aviso_viabilidade`). Chamado UMA vez, pelo
 * `main.tsx`, junto do `definirPerfil`. Payload ausente ou malformado nao instala nada
 * e nao derruba o app: backend anterior nao manda a chave, e o Brasil nunca manda.
 */
export function definirAvisoDeViabilidade(p: unknown): void {
  aviso = null
  if (!p || typeof p !== 'object') return
  const c = p as Partial<AvisoDeViabilidade>
  if (typeof c.titulo !== 'string' || typeof c.texto !== 'string') return
  if (!c.titulo.trim() || !c.texto.trim()) return
  aviso = { titulo: c.titulo, texto: c.texto }
}

/** SO para teste: devolve o modulo ao estado de import. */
export function _resetarAvisoParaTeste(): void {
  aviso = null
}
