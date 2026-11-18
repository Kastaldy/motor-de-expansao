/**
 * Tela Masters (DEC-089): o contrato do payload de `/api/masters` e as regras de
 * EXIBIÇÃO, puras — no padrão de `lib/acesso.ts` e `lib/dock-itens.ts`: o vitest do
 * piloto roda em ambiente `node`, então o que vira texto ou altura de barra vive aqui,
 * testável sem DOM, e `MastersScreen.tsx` só desenha.
 *
 * As regras de NEGÓCIO (o que é "em operação", quem conta para a meta) não moram aqui:
 * são do servidor (`motor_expansao.masters.painel`), e a tela recebe o resultado.
 */

export interface MasterResumo {
  em_operacao: number
  em_inauguracao: number
  assinados: number
  ano: number
  abertas_no_ano: number
}

export interface MasterMetaCard {
  ano: number
  n_ano: number
  por_ano: number | null
  n_contam: number
  quantidade: number | null
  prazo: string | null
  meses_ate_prazo: number | null
}

export interface MasterCard {
  id: string
  /** O nome do MASTER (o titular, sem o território); 18/11/2026, Juan. */
  nome: string
  /** O território dele, como a Ultra o chama ("DF/GO", "RJ/SP 01"). */
  territorio: string | null
  tipo_area: string | null
  regioes: string[]
  resumo: MasterResumo
  meta: MasterMetaCard
}

export interface FontesMasters {
  planilha_de: string | null
  ingerido_em: string | null
  growth_ate: string | null
}

export interface MastersPayload {
  masters: MasterCard[]
  hoje: string
  fontes: FontesMasters
}

export interface TrimestreMeta {
  trimestre: number
  novas: number
  acumulado: number
  pct: number | null
  futuro: boolean
  atual: boolean
}

export interface MetaMaster extends MasterMetaCard {
  pct_ano: number | null
  trimestres: TrimestreMeta[]
  pct_contrato: number | null
  sem_data: string[]
}

export interface UnidadeEmOperacao {
  unidade: string
  uf: string | null
  inauguracao: string | null
  sem_data: boolean
  conta_para_meta: boolean
  operacao_de: string | null
  meta_de: string | null
}

export interface UnidadeEmInauguracao {
  unidade: string
  uf: string | null
  cidade: string | null
  previsao: string | null
  fase: string | null
  conta_para_meta: boolean | null
  operacao_de: string | null
  meta_de: string | null
}

export interface UnidadeAssinada {
  unidade: string
  cidade: string | null
  uf: string | null
  dentro_territorio: boolean | null
}

export interface FaseAssinada {
  fase: string
  unidades: UnidadeAssinada[]
}

export interface MasterPainel {
  id: string
  nome: string
  territorio: string | null
  tipo_area: string | null
  regioes: { nome: string; tipo: string }[]
  nota: string | null
  resumo: MasterResumo
  meta: MetaMaster
  em_operacao: UnidadeEmOperacao[]
  em_inauguracao: UnidadeEmInauguracao[]
  assinados: FaseAssinada[]
  hoje: string
  fontes: FontesMasters
}

/** `2026-03-01` -> `01/03/2026`; vazio -> `—`. */
export function dataBr(iso: string | null | undefined): string {
  if (!iso) return '—'
  const [a, m, d] = iso.slice(0, 10).split('-')
  return d && m && a ? `${d}/${m}/${a}` : '—'
}

/** 0,25 -> `25%`; vazio -> `—`. */
export function pct(v: number | null | undefined): string {
  return v == null || !Number.isFinite(v) ? '—' : `${Math.round(v * 100)}%`
}

/** `Asa Norte (DF)`; sem UF, só o nome. */
export function rotuloUnidade(nome: string, uf: string | null | undefined): string {
  return uf ? `${nome} (${uf})` : nome
}

/** "faltam 4 meses", "vence este mês", "venceu em 31/12/2026" ou "não informado". */
export function textoPrazo(
  meta: Pick<MasterMetaCard, 'prazo' | 'meses_ate_prazo'>,
  hoje: string,
): string {
  if (!meta.prazo) return 'não informado'
  const data = dataBr(meta.prazo)
  if (meta.prazo < hoje.slice(0, 10)) return `venceu em ${data}`
  const n = meta.meses_ate_prazo ?? 0
  if (n <= 0) return `${data} (vence este mês)`
  return `${data} (falta${n === 1 ? '' : 'm'} ${n} ${n === 1 ? 'mês' : 'meses'})`
}

/** As aberturas do ano: "8", ou "3 de 10 (30%)" quando há meta do ano. */
export function textoAnoDaMeta(meta: Pick<MasterMetaCard, 'n_ano' | 'por_ano'>): string {
  if (!meta.por_ano) return String(meta.n_ano)
  return `${meta.n_ano} de ${meta.por_ano} (${pct(meta.n_ano / meta.por_ano)})`
}

/** O contrato: "5 de 5 (100%)" quando há quantidade; `null` sem ela. */
export function textoContrato(
  meta: Pick<MasterMetaCard, 'n_contam' | 'quantidade'>,
): string | null {
  if (!meta.quantidade) return null
  return `${meta.n_contam} de ${meta.quantidade} (${pct(meta.n_contam / meta.quantidade)})`
}

/** O topo do gráfico da meta: a meta do ano, ou a maior barra (nunca zero). */
export function topoDoGrafico(trimestres: TrimestreMeta[], porAno: number | null): number {
  const maior = Math.max(0, ...trimestres.map((t) => t.acumulado))
  return Math.max(1, maior, porAno ?? 0)
}

/** O rótulo de cima da barra: "6 (+3)" no trimestre com abertura, "6" sem. */
export function rotuloDaBarra(t: TrimestreMeta): string {
  if (t.futuro) return ''
  return t.novas > 0 ? `${t.acumulado} (+${t.novas})` : String(t.acumulado)
}

/* ---- A barra da meta do ano (18/11/2026, Juan: "uma barra que vai até 100%, quanto % eles
   estão e quanto falta; como não temos esse dado, pode fazer randomização com a diferença de
   2, seja pra cima ou pra baixo") ---- */

/** A diferença da meta simulada para as aberturas do ano. */
export const DIFERENCA_DA_SIMULACAO = 2

export interface MetaDoAno {
  meta: number
  /** `true` = a config não traz a meta do ano e esta é a SIMULADA (a tela avisa). */
  simulada: boolean
  abertas: number
  pct: number
  faltam: number
  acima: number
}

/** Sorteio estável (FNV-1a de 32 bits): o mesmo master no mesmo ano cai sempre do mesmo lado,
 *  para a barra não mudar a cada clique. */
function sorteio(semente: string): number {
  let h = 2166136261
  for (const c of semente) {
    h ^= c.charCodeAt(0)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

/** A meta do ano para a barra: a da config; sem ela e com `simular`, a SIMULADA = as aberturas
 *  do ano ± 2, o lado sorteado pelo id do master e pelo ano, nunca abaixo de 1 (com menos de 3
 *  aberturas, só para cima); sem ela e sem `simular`, `null` ("meta do ano não informada").
 *
 *  `simular` é só da prévia local (18/11/2026, Juan: "simulação só na prévia"): a tela passa o
 *  `import.meta.env.DEV` do Vite, falso no build que vai para produção. */
export function metaDoAno(
  id: string,
  ano: number,
  abertas: number,
  porAno: number | null,
  simular = false,
): MetaDoAno | null {
  let meta = porAno ?? 0
  const simulada = !porAno || porAno <= 0
  if (simulada && !simular) return null
  if (simulada) {
    const paraCima = sorteio(`${id}:${ano}`) % 2 === 0
    const abaixo = abertas - DIFERENCA_DA_SIMULACAO
    meta = paraCima || abaixo < 1 ? abertas + DIFERENCA_DA_SIMULACAO : abaixo
  }
  return {
    meta,
    simulada,
    abertas,
    pct: abertas / meta,
    faltam: Math.max(0, meta - abertas),
    acima: Math.max(0, abertas - meta),
  }
}

/** A escala da barra, em UNIDADES (18/11/2026, Juan: "deixe ela indo de 0 à meta do ano"; depois,
 *  "só mostre o 0 e onde está a meta, com uma linha rosa e o número"): de 0 até a meta, ou até as
 *  aberturas quando elas passaram da meta. Devolve o fim da escala e onde a linha da meta cai
 *  (fração de 0 a 1), para a barra mostrar quando passou da meta. */
export function escalaDaBarra(md: Pick<MetaDoAno, 'meta' | 'abertas'>): {
  fim: number
  posicaoDaMeta: number
  posicaoDasAbertas: number
} {
  const fim = Math.max(md.meta, md.abertas, 1)
  return { fim, posicaoDaMeta: md.meta / fim, posicaoDasAbertas: md.abertas / fim }
}

/** "80% da meta · faltam 2 aberturas", ou "meta batida · 2 aberturas acima (133%)". */
export function textoProgressoDaMeta(m: MetaDoAno): string {
  const aberturas = (n: number) => `${n} ${n === 1 ? 'abertura' : 'aberturas'}`
  if (m.faltam > 0)
    return `${pct(m.pct)} da meta · falta${m.faltam === 1 ? '' : 'm'} ${aberturas(m.faltam)}`
  if (m.acima > 0) return `meta batida · ${aberturas(m.acima)} acima (${pct(m.pct)})`
  return 'meta batida (100%)'
}

/* ---- Um gráfico por grupo, no fim do painel (18/11/2026, Juan: "um gráfico para cada
   grupo e coloque no fim") ---- */

export interface Barra {
  rotulo: string
  n: number
  destaque?: boolean
}

const MESES_CURTOS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']

/** Em operação: quantas inauguraram em cada ano, do primeiro com abertura até o atual (anos
 *  sem abertura entram com zero); o ano atual em destaque. As sem data ficam à parte. */
export function barrasPorAno(
  unidades: UnidadeEmOperacao[],
  anoAtual: number,
): { barras: Barra[]; semData: number } {
  const anos = unidades
    .map((u) => (u.inauguracao ? Number(u.inauguracao.slice(0, 4)) : NaN))
    .filter((a) => Number.isFinite(a))
  const semData = unidades.length - anos.length
  if (!anos.length) return { barras: [], semData }
  const primeiro = Math.min(...anos)
  const ultimo = Math.max(anoAtual, ...anos)
  const barras: Barra[] = []
  for (let a = primeiro; a <= ultimo; a++) {
    barras.push({ rotulo: String(a), n: anos.filter((x) => x === a).length, destaque: a === anoAtual })
  }
  return { barras, semData }
}

/** Em inauguração: quantas abrem em cada mês previsto (na ordem do calendário) e, por
 *  último, as que estão em pré-venda sem data. */
export function barrasPorPrevisao(unidades: UnidadeEmInauguracao[]): Barra[] {
  const porMes = new Map<string, number>()
  let preVenda = 0
  for (const u of unidades) {
    if (u.previsao) {
      const chave = u.previsao.slice(0, 7)
      porMes.set(chave, (porMes.get(chave) ?? 0) + 1)
    } else {
      preVenda += 1
    }
  }
  const barras: Barra[] = [...porMes.keys()].sort().map((chave) => {
    const [a, m] = chave.split('-')
    return { rotulo: `${MESES_CURTOS[Number(m) - 1]}/${a.slice(2)}`, n: porMes.get(chave) ?? 0 }
  })
  if (preVenda) barras.push({ rotulo: 'pré-venda', n: preVenda })
  return barras
}

/** Contratos assinados: um por fase, na ordem em que o servidor as entrega (a mais perto
 *  de abrir primeiro). */
export function barrasPorFase(fases: FaseAssinada[]): Barra[] {
  return fases.map((f) => ({ rotulo: f.fase, n: f.unidades.length }))
}

/** As etiquetas de uma unidade em operação: só as EXCEÇÕES (quase todas contam para a meta
 *  do próprio master, e repetir "conta para a meta" em cada linha virava ruído). */
export function etiquetasDaUnidade(u: UnidadeEmOperacao): string[] {
  const out: string[] = []
  if (u.sem_data) out.push('sem data no Growth')
  if (!u.conta_para_meta) out.push(u.meta_de ? `fora da meta (meta: ${u.meta_de})` : 'fora da meta')
  if (u.operacao_de) out.push(`operação: ${u.operacao_de}`)
  return out
}
