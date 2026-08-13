/**
 * Controle TEMPORÁRIO de acesso por aba — a metade do FRONT (2026-08-13).
 *
 * O backend (`web/server/acesso.py`) é quem BARRA de verdade, rota a rota, pelo
 * `Remote-User` do Authelia. Este módulo só decide o que a interface mostra: quais
 * cards do Início existem, quais ícones do Dock aparecem e para onde o app leva o
 * usuário na abertura. Os nomes de aba são os MESMOS valores brutos do backend
 * (identificadores sem acento, regra do CLAUDE.md §2) — mudou lá, muda aqui junto.
 *
 * PURO e sem React de propósito, no padrão de `lib/inicio.ts`: o vitest roda em
 * ambiente node e este módulo precisa ser testável sem DOM. Por isso `TelaControlada`
 * é uma união local, e não um import do `App.tsx`.
 *
 * `abas === null` = o `/api/me` ainda não respondeu (ou falhou) -> tudo liberado,
 * espelhando o fail-open do backend: um backend antigo sem a rota não pode apagar
 * as abas de ninguém.
 */

import { MODOS, type ModoDefinicao } from './inicio'

/** Valores brutos de aba — devem bater 1:1 com ABAS_VALIDAS do backend. */
export type Aba = 'mapa' | 'oportunidades' | 'executiva' | 'viabilidade'

export const TODAS_AS_ABAS: readonly Aba[] = Object.freeze([
  'mapa',
  'oportunidades',
  'executiva',
  'viabilidade',
])

/** Telas do App que o controle conhece (subconjunto local do `Tela` do App.tsx). */
export type TelaControlada =
  | 'inicio'
  | 'ponto'
  | 'oportunidades'
  | 'mapa'
  | 'viabilidade'
  | 'executiva'

/** Que aba libera cada tela. O modo de ponto é o Explorar com a ficha por cima
 *  (pedido do Juan, 2026-08-11), então ele pertence à aba `mapa`. */
const ABA_DA_TELA: Record<Exclude<TelaControlada, 'inicio'>, Aba> = {
  ponto: 'mapa',
  mapa: 'mapa',
  oportunidades: 'oportunidades',
  executiva: 'executiva',
  viabilidade: 'viabilidade',
}

/**
 * Payload do /api/me -> conjunto de abas, defensivo: payload inesperado (backend
 * antigo, erro de proxy) devolve `null` = sem controle, nunca um conjunto vazio —
 * vazio trancaria o app inteiro por um contrato quebrado.
 */
export function abasDoPayload(payload: unknown): Set<Aba> | null {
  if (!payload || typeof payload !== 'object') return null
  const abas = (payload as { abas?: unknown }).abas
  if (!Array.isArray(abas)) return null
  return new Set(
    abas.filter((a): a is Aba => (TODAS_AS_ABAS as readonly string[]).includes(String(a))),
  )
}

/** O Início é sempre alcançável — é a porta, não uma aba. */
export function telaLiberada(tela: TelaControlada, abas: Set<Aba> | null): boolean {
  if (abas === null || tela === 'inicio') return true
  return abas.has(ABA_DA_TELA[tela])
}

/** Cards do Início que este usuário pode ver (cada card leva a uma tela). */
export function modosLiberados(abas: Set<Aba> | null): readonly ModoDefinicao[] {
  if (abas === null) return MODOS
  return MODOS.filter((m) => telaLiberada(m.destino, abas))
}

/**
 * Onde o app deve pousar na abertura (ou quando a tela atual deixa de ser permitida).
 * Quem tem algum card no Início pousa no Início; quem não tem nenhum (ex.: acesso só
 * à Executiva) vai direto para a única área que pode usar.
 */
export function telaInicial(abas: Set<Aba> | null): TelaControlada {
  if (abas === null || modosLiberados(abas).length > 0) return 'inicio'
  if (abas.has('executiva')) return 'executiva'
  if (abas.has('viabilidade')) return 'viabilidade'
  return 'inicio'
}
