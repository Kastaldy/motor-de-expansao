/* Funções puras do painel de anotações de concorrente (migration 022). Ficam fora do
 * componente para o vitest (ambiente `node`, sem DOM) alcançá-las. */
import type { CamposDaObservacao, Observacao, ObservacaoCampos } from './types'

/** Campos numéricos do formulário: (chave, rótulo, mínimo, máximo). As MESMAS faixas dos CHECK
 *  da 022 e de `web/server/observacoes.py`, para o erro aparecer antes de ir ao servidor. */
export const NUMERICOS = [
  ['metragem_m2', 'Metragem', 50, 20000],
  ['vagas', 'Vagas de estacionamento', 0, 5000],
  ['alunos_estimados', 'Alunos estimados', 1, 50000],
] as const

/** As três notas de 1 a 10: (chave, rótulo curto). */
export const NOTAS = [
  ['nota_conservacao', 'Conservação'],
  ['nota_fachada', 'Fachada'],
  ['nota_atendimento', 'Atendimento'],
] as const

export type ChaveNota = (typeof NOTAS)[number][0]
type ChaveNumerica = (typeof NUMERICOS)[number][0]

/** O que o formulário guarda enquanto a pessoa digita: números como texto, como o input
 *  devolve; notas já como número (vêm de botões). */
export interface Formulario {
  id: 'nova' | number
  versao: number
  metragem_m2: string
  vagas: string
  alunos_estimados: string
  equipamentos: string
  comodidades: string
  comentario: string
  nota_conservacao: number | null
  nota_fachada: number | null
  nota_atendimento: number | null
}

const txt = (n: number | null) => (n != null ? String(n) : '')

export function formularioDe(o: Observacao | null): Formulario {
  return {
    id: o?.id ?? 'nova',
    versao: o?.versao ?? 0,
    metragem_m2: txt(o?.metragem_m2 ?? null),
    vagas: txt(o?.vagas ?? null),
    alunos_estimados: txt(o?.alunos_estimados ?? null),
    equipamentos: o?.equipamentos ?? '',
    comodidades: o?.comodidades ?? '',
    comentario: o?.comentario ?? '',
    nota_conservacao: o?.nota_conservacao ?? null,
    nota_fachada: o?.nota_fachada ?? null,
    nota_atendimento: o?.nota_atendimento ?? null,
  }
}

/** `1.500`, `1500`, `1500,5` -> número; vazio -> null; lixo -> NaN. */
export function lerNumero(texto: string): number | null {
  const limpo = texto.trim().replace(/\./g, '').replace(',', '.')
  if (!limpo) return null
  return Number(limpo)
}

/** O corpo da requisição, ou a mensagem de erro (as MESMAS regras dos CHECK da 022). */
export function camposDoFormulario(f: Formulario): ObservacaoCampos | string {
  const numeros = {} as Record<ChaveNumerica, number | null>
  for (const [chave, rotulo, min, max] of NUMERICOS) {
    const n = lerNumero(f[chave])
    if (n != null && (!Number.isFinite(n) || n < min || n > max)) {
      const faixa = `${min.toLocaleString('pt-BR')} a ${max.toLocaleString('pt-BR')}`
      return `${rotulo} fora da faixa aceita (${faixa}).`
    }
    numeros[chave] = n == null ? null : Math.round(n)
  }
  const campos: ObservacaoCampos = {
    metragem_m2: numeros.metragem_m2,
    equipamentos: f.equipamentos.trim() || null,
    vagas: numeros.vagas,
    comodidades: f.comodidades.trim() || null,
    nota_conservacao: f.nota_conservacao,
    nota_fachada: f.nota_fachada,
    nota_atendimento: f.nota_atendimento,
    alunos_estimados: numeros.alunos_estimados,
    comentario: f.comentario.trim() || null,
  }
  if (Object.values(campos).every((v) => v == null)) {
    return 'Preencha ao menos um campo da anotação.'
  }
  return campos
}

/** A anotação viva mais recente que informa metragem — o número do resumo. */
export function metragemMaisRecente(ativas: Observacao[]): Observacao | null {
  const com = ativas.filter((o) => o.metragem_m2 != null)
  if (!com.length) return null
  return [...com].sort((a, b) => (b.atualizada_em ?? '').localeCompare(a.atualizada_em ?? ''))[0]
}

/** Média de uma nota entre as anotações vivas que a deram, e quantas deram. */
export function mediaDaNota(ativas: Observacao[], chave: ChaveNota): { media: number; n: number } | null {
  const valores = ativas.map((o) => o[chave]).filter((v): v is number => v != null)
  if (!valores.length) return null
  return { media: valores.reduce((a, b) => a + b, 0) / valores.length, n: valores.length }
}

/** `"Pessoa 3"` -> 3. O avatar usa o número para a cor ficar estável por pessoa. */
export function numeroDoRotulo(rotulo: string): number {
  const n = Number(rotulo.replace(/\D/g, ''))
  return Number.isFinite(n) && n > 0 ? n : 1
}

/** As linhas do cartão de uma anotação, na ordem da tela: (rótulo, valor, destaque). */
export function linhasDaObservacao(c: CamposDaObservacao): [string, string, boolean][] {
  const fmt = (n: number) => n.toLocaleString('pt-BR')
  const linhas: [string, string, boolean][] = []
  if (c.metragem_m2 != null) linhas.push(['Metragem', `${fmt(c.metragem_m2)} m²`, true])
  if (c.vagas != null) linhas.push(['Vagas', c.vagas === 0 ? 'Sem estacionamento' : fmt(c.vagas), false])
  if (c.alunos_estimados != null) linhas.push(['Alunos est.', `~${fmt(c.alunos_estimados)}`, false])
  const notas = NOTAS.filter(([k]) => c[k] != null).map(([k, r]) => `${r} ${c[k]}/10`)
  if (notas.length) linhas.push(['Notas', notas.join(' · '), false])
  if (c.equipamentos) linhas.push(['Equipamentos', c.equipamentos, false])
  if (c.comodidades) linhas.push(['Comodidades', c.comodidades, false])
  if (c.comentario) linhas.push(['Comentário', c.comentario, false])
  return linhas
}

/** `05/11/2026 às 14:32`, no fuso de quem lê. */
export function dataHora(iso: string | null | undefined, comHora = true): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const dia = d.toLocaleDateString('pt-BR')
  if (!comHora) return dia
  return `${dia} às ${d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`
}

/** As chaves dos pinos que podem receber anotação, sem repetição — o corpo da contagem. */
export function chavesDosPinos(pinos: { chave?: string | null }[]): string[] {
  return [...new Set(pinos.map((p) => p.chave).filter((c): c is string => !!c))]
}
