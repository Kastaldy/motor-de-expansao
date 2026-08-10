/**
 * Período de análise da Visão Executiva — aritmética de data, presets e rótulos.
 *
 * O seletor da tela era de COMPETÊNCIA (um mês fechado). O time de campo precisa
 * analisar também recortes que não coincidem com o mês (a virada de uma campanha, os
 * 30 dias que antecedem a reunião), então o que a tela passa a manipular é um
 * intervalo com as duas pontas — sempre INCLUSIVO: `2026-08-01..2026-08-31` é agosto
 * inteiro, e não 30 dias.
 *
 * DUAS REGRAS MANDAM AQUI, e as duas são cicatriz e não estilo:
 *
 * 1. **Toda conta em UTC** (`Date.UTC`, `getUTCDate`). `new Date('2026-08-01')` já é
 *    UTC, mas `new Date(2026, 7, 1)` é meia-noite LOCAL; misturar os dois num fuso
 *    negativo (o Brasil inteiro) faz `toISOString()` devolver `2026-07-31` para o dia
 *    1º — o backend receberia um período começando no mês anterior e ninguém
 *    desconfiaria, porque a tela mostraria "agosto". Somar dias em milissegundos só é
 *    seguro em UTC: no fuso local, um dia de horário de verão tem 23h e a soma erra.
 *
 * 2. **Nada aqui lê o relógio.** `hoje` entra como parâmetro `'AAAA-MM-DD'`. Função
 *    que chama `new Date()` por dentro não tem teste determinístico — passaria em
 *    agosto e quebraria na virada do ano, exatamente quando ninguém está olhando.
 *    Quem lê o relógio é o componente (`PeriodoPicker`), num lugar só.
 *
 * Data ilegível NUNCA estoura: as funções devolvem valor neutro (`false`, `0`,
 * `'Período inválido'`, o próprio período) e quem reprova com mensagem é
 * `periodoValido`. O `<input type="date">` passa por estados incompletos a cada
 * tecla, e um throw ali derruba a tela inteira.
 */

/** Intervalo de análise. `'AAAA-MM-DD'`, INCLUSIVO nas duas pontas. */
export interface Periodo {
  inicio: string
  fim: string
}

/** Primeira e última data COM DADO na base. Vem do payload da carteira e amarra o
 *  `min`/`max` dos campos de data: o calendário não oferece dia que a base não responde. */
export interface LimitePeriodo {
  min: string
  max: string
}

const RE_ISO = /^(\d{4})-(\d{2})-(\d{2})$/
const RE_COMPETENCIA = /^(\d{4})-(\d{2})$/
const DIA_MS = 86_400_000

interface PartesData {
  ano: number
  mes: number
  dia: number
  /** meia-noite UTC do dia — a única unidade em que se faz conta neste arquivo */
  ms: number
}

const dois = (n: number): string => String(n).padStart(2, '0')

/** `(2026, 8, 1)` -> `'2026-08-01'`. */
function montarIso(ano: number, mes: number, dia: number): string {
  return `${String(ano).padStart(4, '0')}-${dois(mes)}-${dois(dia)}`
}

/**
 * Interpreta `'AAAA-MM-DD'` em UTC, ou `null` se a data não existe.
 *
 * A conferência de ida-e-volta (`getUTCFullYear` etc.) não é paranoia: `Date.UTC`
 * NORMALIZA em silêncio, então `2026-02-30` viraria 2 de março e `2025-13-01` viraria
 * janeiro de 2026. Um período que "existe" mas aponta para outro mês é pior que um
 * período recusado. Ela também derruba `'0026-01-01'`, que `Date.UTC` mapeia para 1926.
 */
function partes(iso: string): PartesData | null {
  const m = RE_ISO.exec(String(iso ?? '').trim())
  if (!m) return null
  const ano = Number(m[1])
  const mes = Number(m[2])
  const dia = Number(m[3])
  const ms = Date.UTC(ano, mes - 1, dia)
  const d = new Date(ms)
  if (d.getUTCFullYear() !== ano || d.getUTCMonth() !== mes - 1 || d.getUTCDate() !== dia) {
    return null
  }
  return { ano, mes, dia, ms }
}

function deMs(ms: number): string {
  const d = new Date(ms)
  return montarIso(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate())
}

/** A data existe no calendário? (`'2026-02-30'` e `'2026-13-01'` não existem.) */
export function ehData(iso: string): boolean {
  return partes(iso) !== null
}

/** Soma (ou subtrai) dias corridos. Em UTC o dia tem sempre 86.400.000 ms. */
export function somarDias(iso: string, dias: number): string {
  const p = partes(iso)
  return p ? deMs(p.ms + dias * DIA_MS) : iso
}

/**
 * Último dia do mês. Dia 0 do mês SEGUINTE é o último deste — a própria biblioteca de
 * data resolve 28/29/30/31 e o ano bissexto, sem tabela nossa para envelhecer.
 */
function ultimoDiaDoMes(ano: number, mes: number): number {
  return new Date(Date.UTC(ano, mes, 0)).getUTCDate()
}

/** `'2026-07'` (ou `'2026-07-15'`) -> o mês INTEIRO como período. Ponte com o seletor
 *  de competência antigo, que entregava só `'AAAA-MM'`. */
export function periodoDoMes(competencia: string): Periodo {
  const texto = String(competencia ?? '').trim().slice(0, 7)
  const m = RE_COMPETENCIA.exec(texto)
  if (!m) return { inicio: '', fim: '' }
  const ano = Number(m[1])
  const mes = Number(m[2])
  if (mes < 1 || mes > 12) return { inicio: '', fim: '' }
  return { inicio: montarIso(ano, mes, 1), fim: montarIso(ano, mes, ultimoDiaDoMes(ano, mes)) }
}

/** `'2026-08-10'` -> `'10/08/2026'`. Data ilegível volta como veio (não inventa). */
export function dataBr(iso: string): string {
  const p = partes(iso)
  return p ? `${dois(p.dia)}/${dois(p.mes)}/${p.ano}` : String(iso ?? '')
}

/** O período é exatamente um mês civil, do dia 1º ao último? */
export function ehMesInteiro(p: Periodo): boolean {
  const a = partes(p.inicio)
  const b = partes(p.fim)
  if (!a || !b) return false
  return a.ano === b.ano && a.mes === b.mes && a.dia === 1 && b.dia === ultimoDiaDoMes(b.ano, b.mes)
}

const MESES_LONGO = [
  'janeiro',
  'fevereiro',
  'março',
  'abril',
  'maio',
  'junho',
  'julho',
  'agosto',
  'setembro',
  'outubro',
  'novembro',
  'dezembro',
]

function maiusculaInicial(texto: string): string {
  return `${texto.charAt(0).toUpperCase()}${texto.slice(1)}`
}

/**
 * Rótulo do período em quatro formatos, do mais curto ao mais explícito.
 *
 * A escolha é por INFORMAÇÃO REDUNDANTE, não por gosto: repetir "agosto/2026" nas duas
 * pontas de um recorte dentro do mesmo mês faz o olho procurar a diferença onde não
 * há. Cada formato só carrega o que muda:
 *
 *   mês inteiro          -> `Julho/2026`
 *   dentro do mesmo mês  -> `1 a 10 de agosto/2026`
 *   atravessando meses   -> `15/07 a 10/08/2026`
 *   atravessando anos    -> `15/12/2025 a 10/01/2026`
 *
 * O mês vem por extenso quando dá, porque `01/07 a 31/07` lê como etiqueta de eixo, e
 * este rótulo aparece no meio do cabeçalho, ao lado de prosa.
 */
export function rotuloDoPeriodo(p: Periodo): string {
  const a = partes(p.inicio)
  const b = partes(p.fim)
  if (!a || !b) return 'Período inválido'
  if (ehMesInteiro(p)) return `${maiusculaInicial(MESES_LONGO[a.mes - 1])}/${a.ano}`
  if (a.ano === b.ano && a.mes === b.mes) {
    const mesAno = `${MESES_LONGO[a.mes - 1]}/${a.ano}`
    // Um dia só não é intervalo: "10 a 10 de agosto" lê como erro de digitação.
    return a.dia === b.dia ? `${a.dia} de ${mesAno}` : `${a.dia} a ${b.dia} de ${mesAno}`
  }
  if (a.ano === b.ano) {
    return `${dois(a.dia)}/${dois(a.mes)} a ${dois(b.dia)}/${dois(b.mes)}/${b.ano}`
  }
  return `${dataBr(p.inicio)} a ${dataBr(p.fim)}`
}

/**
 * O período pode ir para o backend?
 *
 * Três reprovações, nesta ordem — a primeira que bate é a que o operador lê, porque
 * empilhar mensagens sobre o mesmo campo não ajuda ninguém a consertar nada:
 *  1. data incompleta/inexistente (o `<input type="date">` passa por isso a cada tecla);
 *  2. fim antes do início;
 *  3. fora do intervalo que a base cobre.
 *
 * Limite ilegível NÃO reprova: quem define a cobertura é a base, e travar o operador
 * por um defeito nosso de payload seria trocar um dado faltando por uma tela morta.
 */
export function periodoValido(p: Periodo, limite: LimitePeriodo): { ok: boolean; erro?: string } {
  const a = partes(p.inicio)
  const b = partes(p.fim)
  if (!a || !b) return { ok: false, erro: 'Informe as duas datas do período.' }
  if (b.ms < a.ms) return { ok: false, erro: 'A data final é anterior à data inicial.' }
  const min = partes(limite?.min ?? '')
  const max = partes(limite?.max ?? '')
  if (!min || !max) return { ok: true }
  if (a.ms < min.ms || b.ms > max.ms) {
    return {
      ok: false,
      erro: `Fora do intervalo com dado: a base vai de ${dataBr(limite.min)} a ${dataBr(limite.max)}.`,
    }
  }
  return { ok: true }
}

/**
 * Grampeia as duas pontas dentro do que a base cobre.
 *
 * Grampear ponta a ponta preserva a ordem (a função é monótona): se `inicio <= fim`
 * antes, continua depois — não há como sair daqui com um período invertido. Data
 * ilegível passa direto, para não trocar o que o operador digitou por uma data que ele
 * não escolheu; quem recusa é `periodoValido`.
 */
export function ajustarAoLimite(p: Periodo, limite: LimitePeriodo): Periodo {
  const min = partes(limite?.min ?? '')
  const max = partes(limite?.max ?? '')
  if (!min || !max || max.ms < min.ms) return p
  const grampo = (iso: string): string => {
    const d = partes(iso)
    if (!d) return iso
    if (d.ms < min.ms) return deMs(min.ms)
    if (d.ms > max.ms) return deMs(max.ms)
    return iso
  }
  return { inicio: grampo(p.inicio), fim: grampo(p.fim) }
}

/**
 * Quantos dias o período tem, contando as DUAS pontas: `01/08..01/08` é 1 dia, e não 0.
 * É a mesma contagem que o operador faz no dedo, e é a que divide faturamento por dia.
 * Período inválido ou invertido não tem dia nenhum.
 */
export function diasDoPeriodo(p: Periodo): number {
  const a = partes(p.inicio)
  const b = partes(p.fim)
  if (!a || !b || b.ms < a.ms) return 0
  return Math.round((b.ms - a.ms) / DIA_MS) + 1
}

/** Mesmo intervalo? Compara pelo DIA, então `' 2026-08-01'` e `'2026-08-01'` batem. */
export function mesmoPeriodo(a: Periodo, b: Periodo): boolean {
  const ai = partes(a.inicio)
  const af = partes(a.fim)
  const bi = partes(b.inicio)
  const bf = partes(b.fim)
  if (!ai || !af || !bi || !bf) return false
  return ai.ms === bi.ms && af.ms === bf.ms
}
