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

/** Valores brutos de aba — devem bater 1:1 com o que o /api/me pode devolver
 *  (ABAS_VALIDAS do backend + a aba `acessos`, que vem da allowlist de env). */
export type Aba =
  | 'mapa'
  | 'oportunidades'
  | 'imobiliaria'
  | 'executiva'
  | 'viabilidade'
  | 'acessos'

export const TODAS_AS_ABAS: readonly Aba[] = Object.freeze([
  'mapa',
  'oportunidades',
  'imobiliaria',
  'executiva',
  'viabilidade',
  'acessos',
])

/**
 * Abas que o fail-open NÃO concede: `acessos` (emenda DEC-027) expõe atividade do
 * time, e `imobiliaria` (2026-08-24) é a camada de imóveis restrita a um subconjunto
 * do time. Ambas só existem para quem o /api/me listar EXPLICITAMENTE — um /api/me
 * fora do ar não pode fazê-las aparecer para todo mundo. O backend barra de verdade
 * (404 / 403); aqui é só o espelho visual do deny-by-default.
 *
 * Só a TELA dedicada entra aqui. A camada de imóveis DENTRO do Mapa Territorial
 * (pins + seção da ficha do hexágono) segue a aba `mapa` de propósito — decisão do
 * Felipe em 2026-08-24: quem tem o mapa vê os imóveis por lá.
 */
const ABAS_SEM_FAIL_OPEN: ReadonlySet<Aba> = new Set(['acessos', 'imobiliaria'])

/** Telas do App que o controle conhece (subconjunto local do `Tela` do App.tsx). */
export type TelaControlada =
  | 'inicio'
  | 'ponto'
  | 'oportunidades'
  | 'oportunidades-imob'
  | 'mapa'
  | 'viabilidade'
  | 'executiva'
  | 'acessos'

/** Que aba libera cada tela. O modo de ponto é o Explorar com a ficha por cima
 *  (pedido do Juan, 2026-08-11), então ele pertence à aba `mapa`. */
const ABA_DA_TELA: Record<Exclude<TelaControlada, 'inicio'>, Aba> = {
  ponto: 'mapa',
  mapa: 'mapa',
  oportunidades: 'oportunidades',
  // Camada de oferta com gate PRÓPRIO desde 2026-08-24. Antes reusava o gate de
  // `oportunidades`, o que amarrava os imóveis ao funil de expansão: não dava para
  // restringir um sem tirar o outro de quem o usa. Os pins de imóvel no Mapa
  // Territorial NÃO passam por aqui — são da aba `mapa` (ver ABAS_SEM_FAIL_OPEN).
  'oportunidades-imob': 'imobiliaria',
  executiva: 'executiva',
  viabilidade: 'viabilidade',
  acessos: 'acessos',
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
  if (tela === 'inicio') return true
  // Fail-open (sem /api/me) libera as abas de trabalho, NUNCA as deny-by-default.
  if (abas === null) return !ABAS_SEM_FAIL_OPEN.has(ABA_DA_TELA[tela])
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
