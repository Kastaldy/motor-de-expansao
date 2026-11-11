/* Funções puras do painel de anotações de concorrente (migration 023). Ficam fora do
 * componente para o vitest (ambiente `node`, sem DOM) alcançá-las. */
import type { CamposDaObservacao, Observacao, ObservacaoCampos } from './types'

/** Campos numéricos do formulário: (chave, rótulo, mínimo, máximo). As MESMAS faixas dos CHECK
 *  da 023 e de `web/server/observacoes.py`, para o erro aparecer antes de ir ao servidor. */
export const NUMERICOS = [
  ['metragem_m2', 'Metragem', 50, 20000],
  ['vagas', 'Vagas de estacionamento', 0, 5000],
  ['alunos_estimados', 'Alunos estimados', 1, 50000],
] as const

/** Quantos dígitos cabem nas caixas de metragem, vagas e alunos (pedido de 11/11). Trava de
 *  DIGITAÇÃO: quem decide o que vale continua sendo a faixa de `NUMERICOS`, que cabe nela. */
export const DIGITOS_MAXIMOS = 5

/** Teto de caracteres de equipamentos, comodidades e comentário (pedido de 11/11; eram 1.000,
 *  1.000 e 2.000). O MESMO `TEXTO_MAXIMO` de `web/server/observacoes.py` — um teste amarra os dois. */
export const TEXTO_MAXIMO = 250

/** Os textos livres: (chave, rótulo com a MESMA frase do servidor). */
const TEXTOS = [
  ['equipamentos', 'O campo de equipamentos'],
  ['comodidades', 'O campo de comodidades e aulas coletivas'],
  ['comentario', 'O comentário'],
] as const

/** Teto das notas: estrelas de 1 a 5 (prévia de 10/11; eram notas de 1 a 10). O MESMO teto do
 *  CHECK `chk_observacao_notas` da 023 e de `INTEIROS` em `web/server/observacoes.py`. */
export const NOTA_MAXIMA = 5

/** `3` -> `★★★☆☆`. A média arredonda para a estrela inteira (4,2 -> 4; 4,5 -> 5); o número
 *  exato fica ao lado, no resumo. */
export function estrelas(nota: number): string {
  const cheias = Math.min(NOTA_MAXIMA, Math.max(0, Math.round(nota)))
  return '★'.repeat(cheias) + '☆'.repeat(NOTA_MAXIMA - cheias)
}

/** As três notas, de 1 a 5 estrelas: (chave, rótulo curto). */
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

/** O que os campos numéricos aceitam ao digitar ou colar: só dígitos, até `DIGITOS_MAXIMOS`.
 *  Letra, ponto, vírgula e sinal somem na hora; o que passa do 5º dígito é cortado (o colar não
 *  respeita o `maxLength` do jeito que a digitação respeita). */
export function apenasDigitos(texto: string): string {
  return texto.replace(/\D/g, '').slice(0, DIGITOS_MAXIMOS)
}

/** O corpo da requisição, ou a mensagem de erro (as MESMAS regras dos CHECK da 023 e de
 *  `web/server/observacoes.py`, com a mesma frase). */
export function camposDoFormulario(f: Formulario): ObservacaoCampos | string {
  const numeros = {} as Record<ChaveNumerica, number | null>
  for (const [chave, rotulo, min, max] of NUMERICOS) {
    const n = lerNumero(f[chave])
    if (n != null && !Number.isInteger(n)) {
      return `${rotulo} precisa ser um número inteiro.`
    }
    if (n != null && (n < min || n > max)) {
      const faixa = `${min.toLocaleString('pt-BR')} a ${max.toLocaleString('pt-BR')}`
      return `${rotulo} fora da faixa aceita (${faixa}).`
    }
    numeros[chave] = n
  }
  // O maxLength trava a digitação, mas não corta o texto de uma anotação antiga que já passa do
  // teto: a edição dela tem de ouvir a mesma frase que o servidor daria.
  for (const [chave, rotulo] of TEXTOS) {
    if (f[chave].trim().length > TEXTO_MAXIMO) return `${rotulo} passa de ${TEXTO_MAXIMO} caracteres.`
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

/** `"Carla de Souza Mendes"` -> `"CM"`: 1ª letra do primeiro e do último nome, para o avatar.
 *  Só letras contam (`"(sem cadastro)"` -> `"SC"`); sem nenhuma, volta `""` e o cartão usa o
 *  número da pessoa. */
export function iniciais(nome: string | null | undefined): string {
  const palavras = (nome ?? '')
    .split(/\s+/)
    .map((p) => p.replace(/[^\p{L}]/gu, ''))
    .filter(Boolean)
  if (!palavras.length) return ''
  const letras = palavras.length > 1 ? [palavras[0], palavras[palavras.length - 1]] : [palavras[0]]
  return letras.map((p) => p[0].toLocaleUpperCase('pt-BR')).join('')
}

/** As linhas do cartão de uma anotação, na ordem da tela: (rótulo, valor, destaque). */
export function linhasDaObservacao(c: CamposDaObservacao): [string, string, boolean][] {
  const fmt = (n: number) => n.toLocaleString('pt-BR')
  const linhas: [string, string, boolean][] = []
  if (c.metragem_m2 != null) linhas.push(['Metragem', `${fmt(c.metragem_m2)} m²`, true])
  if (c.vagas != null) linhas.push(['Vagas', c.vagas === 0 ? 'Sem estacionamento' : fmt(c.vagas), false])
  if (c.alunos_estimados != null) linhas.push(['Alunos est.', `~${fmt(c.alunos_estimados)}`, false])
  const notas = NOTAS.filter(([k]) => c[k] != null).map(([k, r]) => `${r} ${estrelas(c[k] as number)}`)
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
