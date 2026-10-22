/**
 * Top 10 da recomendação única (DEC-077) — a MONTAGEM DE EXIBIÇÃO, pura e testada.
 *
 * O QUE ESTE MÓDULO NÃO FAZ, e isso é o contrato: ele não calcula, não reordena e não
 * filtra nada da regra. Quem decide quais hexágonos entram, em que segmento e em que
 * posição é UMA função do servidor (`montar_recomendacao`), e o bloco `recomendacao`
 * chega pronto em `/api/municipio`, `/api/uf` e `/api/hexagonos`. Aqui só se transforma o
 * bloco em linhas de tela: rótulo da vaga (MV1..MV5 / P1..P5), nome da região, número
 * principal do segmento, linha secundária, vaga vazia com o motivo do servidor e o texto
 * da régua montado com os NÚMEROS DO PAYLOAD (nunca literal: trocar a régua troca o texto).
 *
 * Por que mora em `lib/` e não no `.tsx`: o vitest do piloto roda em ambiente `node` e só
 * casa `src/**\/*.test.ts` — regra em `lib/` é regra testável (mesmo motivo de
 * `lib/inicio.ts`). O componente `Top10Regioes.tsx` fica deliberadamente burro.
 *
 * Identificadores sem acento (`mata_virgem`, `premium`); o que vai à tela passa pela
 * camada de rótulo — de preferência a que o próprio payload traz (`rotulos.segmento`),
 * com `ROTULO_SEGMENTO_TOP10` só como reserva (CLAUDE.md §2).
 *
 * Moeda: nenhum símbolo cravado aqui (`test_sem_moeda_hardcoded_no_front`). A renda sai
 * pelo `renda()` de `lib/format`, que escreve o símbolo do país da instância.
 */

import type { RGBA } from './colors'
import { TEXTO_SEM_DADO } from './constants'
import { alunos, num, renda } from './format'
import { destinoDoHex, type DestinoHex } from './oportunidades'
import { perfilDoCliente } from './perfil'
import type {
  Passo,
  RankItem,
  RecomendacaoTop10,
  ReguaTop10,
  SegmentoTop10,
  SegmentoTop10Payload,
  VagaTop10,
} from './types'

/** Os dois segmentos, na ordem FIXA de exibição: Mata Virgem primeiro, Premium depois. */
export const SEGMENTOS_TOP10: readonly SegmentoTop10[] = Object.freeze(['mata_virgem', 'premium'])

/** Reserva de exibição. Preferir `bloco.rotulos.segmento`, que vem do módulo da regra. */
export const ROTULO_SEGMENTO_TOP10: Readonly<Record<SegmentoTop10, string>> = Object.freeze({
  mata_virgem: 'Mata Virgem',
  premium: 'Premium',
})

/** Prefixo do rótulo da vaga no mapa e na lista: MV1..MV5 / P1..P5. */
const PREFIXO_DA_VAGA: Readonly<Record<SegmentoTop10, string>> = Object.freeze({
  mata_virgem: 'MV',
  premium: 'P',
})

/**
 * Cor de cada segmento por TOKEN de tema (`styles/tokens.css`, nos dois temas). O DOM lê
 * `var()` sozinho; o deck.gl, que não lê CSS, tem o espelho RGBA na `PELE` do `HexMap`.
 */
export const TOKEN_COR_TOP10: Readonly<Record<SegmentoTop10 | 'fora', string>> = Object.freeze({
  mata_virgem: 'var(--top10-mv)',
  premium: 'var(--top10-premium)',
  fora: 'var(--top10-fora)',
})

/**
 * O DISCRIMINADOR: o payload traz o bloco `recomendacao`?
 *
 * Ausente = instância sem régua (a Argentina hoje) e o front segue o caminho legado byte a
 * byte. Recebe `object` e não um tipo com `recomendacao?` opcional de propósito: assim ele
 * serve também à união de `/api/hexagonos` (bloco OU ranking legado), cujo membro legado
 * não tem a chave.
 */
export function temTop10(
  p: object | null | undefined,
): p is { recomendacao: RecomendacaoTop10 } {
  if (p == null || !('recomendacao' in p)) return false
  return (p as { recomendacao?: unknown }).recomendacao != null
}

/** Total de vagas do Top: segmentos × vagas por segmento (10 na régua BR v1). */
export function totalVagas(b: Pick<RecomendacaoTop10, 'regra'>): number {
  return SEGMENTOS_TOP10.length * b.regra.vagas_por_segmento
}

/**
 * Nada foi calculado? Os dois segmentos `indisponivel` (staging sem o carimbo k da malha).
 * É "recomendação suspensa", não "nenhuma região passou na régua" — e a tela não pode
 * confundir os dois (nem "0 candidatos", nem "fora do Top 10" pintado no mapa inteiro).
 */
export function top10Indisponivel(b: Pick<RecomendacaoTop10, 'mata_virgem' | 'premium'>): boolean {
  return SEGMENTOS_TOP10.every((seg) => b[seg].status === 'indisponivel')
}

/** Quantas vagas têm região, somando os dois segmentos. */
export function vagasPreenchidas(b: RecomendacaoTop10): number {
  return SEGMENTOS_TOP10.reduce((n, seg) => n + b[seg].vagas.filter((v) => !v.vazia).length, 0)
}

/** Rótulo de exibição do segmento: o do payload, senão a reserva. */
export function rotuloDoSegmento(
  rotulos: RecomendacaoTop10['rotulos'] | null | undefined,
  seg: SegmentoTop10,
): string {
  return rotulos?.segmento?.[seg] || ROTULO_SEGMENTO_TOP10[seg]
}

/** MV1..MV5 / P1..P5 — o mesmo rótulo no mapa e na lista. */
export function rotuloNoMapa(v: Pick<VagaTop10, 'segmento' | 'posicao'>): string {
  return `${PREFIXO_DA_VAGA[v.segmento]}${v.posicao}`
}

/** "hex 87a812aa3…" — o mesmo corte que as outras listas de hexágono usam. */
export function hexCurto(hexId: string): string {
  return `hex ${hexId.slice(0, 9)}…`
}

/** Score com uma casa só quando fracionário (50 → "50"; 52,5 → "52,5"). */
function numScore(v: number): string {
  return Number.isInteger(v) ? num(v) : num(v, 1)
}

/** "a e b" / "a, b e c". */
function juntarComE(partes: readonly string[]): string {
  if (partes.length <= 1) return partes.join('')
  return `${partes.slice(0, -1).join(', ')} e ${partes[partes.length - 1]}`
}

function plural(n: number, um: string, varios: string): string {
  return `${num(n)} ${n === 1 ? um : varios}`
}

/** "13 candidatos" / "1 candidato" — candidatos do segmento no recorte (`n_elegiveis`). */
export function textoCandidatos(n: number): string {
  return plural(n, 'candidato', 'candidatos')
}

/**
 * Linha secundária de uma vaga preenchida: renda domiciliar, população, residual (ou "não
 * medido") e score censitário com uma casa. Os quatro sempre, nos dois segmentos — a
 * linha é a mesma para o operador comparar Mata Virgem e Premium sem trocar de leitura.
 * "Score censitário" por extenso: o tooltip do mesmo hexágono mostra também o Score M1,
 * com outro valor, e "score" sozinho não diz qual dos dois é.
 */
export function linhaSecundaria(v: VagaTop10): string {
  const partes: string[] = []
  partes.push(
    v.renda_domiciliar == null
      ? 'Renda domiciliar não disponível'
      : `Renda domiciliar ${renda(v.renda_domiciliar)}${v.renda_municipal ? ' (municipal)' : ''}`,
  )
  partes.push(v.populacao == null ? 'População não disponível' : `${num(v.populacao)} hab.`)
  if (!v.residual_medido) partes.push('residual não medido')
  else if (v.residual == null) partes.push('residual não disponível')
  else partes.push(`${alunos(v.residual)} alunos de residual`)
  partes.push(
    v.score_censitario == null
      ? 'score censitário não disponível'
      : `score censitário ${num(v.score_censitario, 1)}`,
  )
  return partes.join(' · ')
}

/** O número que ORDENA o segmento: residual em alunos (Mata Virgem) ou população (Premium). */
export function principalDaVaga(v: VagaTop10): { valor: string; unidade: string } {
  if (v.segmento === 'premium') {
    return { valor: num(v.populacao), unidade: 'habitantes (Censo)' }
  }
  if (!v.residual_medido) return { valor: 'não medido', unidade: 'residual' }
  return { valor: alunos(v.residual), unidade: 'alunos de residual' }
}

/** Destino no mapa de uma vaga preenchida (`null` = sem coordenada/UF/município). */
export function destinoDaVaga(v: VagaTop10): DestinoHex | null {
  if (v.vazia || !v.hex_id) return null
  return destinoDoHex({
    uf: v.uf,
    municipio: v.nome_municipio,
    lat: v.lat,
    lng: v.lng,
    hex_id: v.hex_id,
  })
}

export interface LinhaTop10Regiao {
  tipo: 'regiao'
  /** Chave React = hex_id (vizinhos do mesmo bairro viram linhas distintas). */
  chave: string
  posicao: number
  /** MV1..MV5 / P1..P5. */
  rotulo: string
  /** Bairro dominante, senão o município, senão o texto de "sem dado". */
  nome: string
  hexCurto: string
  /** "São José dos Campos · SP" fora do nível município; `null` dentro dele. */
  municipioUf: string | null
  principal: { valor: string; unidade: string }
  secundaria: string
  destino: DestinoHex | null
  vaga: VagaTop10
}

export interface LinhaTop10Vazia {
  tipo: 'vazia'
  chave: string
  posicao: number
  rotulo: string
  /** "Vaga vazia — {motivo do servidor}". */
  texto: string
}

export type LinhaTop10 = LinhaTop10Regiao | LinhaTop10Vazia

export interface BlocoTop10 {
  segmento: SegmentoTop10
  titulo: string
  nElegiveis: number
  /** "13 candidatos" / "1 candidato". `null` no segmento indisponível: ali nada foi
   *  calculado, e "0 candidatos" leria como "ninguém passou na régua". */
  textoCandidatos: string | null
  /** Segmento sem cálculo (ex.: renda sem o carimbo k): UMA mensagem no lugar das linhas. */
  indisponivel: { titulo: string; motivo: string } | null
  /** Segmento CALCULADO sem nenhum candidato: UMA frase no lugar de N linhas "vaga vazia"
   *  iguais (o caso mais comum fora das cidades grandes). `null` quando há candidato. */
  semCandidato: string | null
  /** Uma linha por vaga, NA ORDEM DO SERVIDOR — sem sort, sem filtro. */
  linhas: LinhaTop10[]
}

function motivoDaVaga(v: VagaTop10, rotulos: RecomendacaoTop10['rotulos'] | undefined): string | null {
  return v.rotulo_motivo || (v.motivo ? rotulos?.motivo?.[v.motivo] || null : null)
}

function linhaDaVaga(
  v: VagaTop10,
  nivelMunicipio: boolean,
  rotulos: RecomendacaoTop10['rotulos'] | undefined,
): LinhaTop10 {
  const rotulo = rotuloNoMapa(v)
  if (v.vazia || !v.hex_id) {
    const motivo = motivoDaVaga(v, rotulos)
    return {
      tipo: 'vazia',
      chave: `${v.segmento}-${v.posicao}`,
      posicao: v.posicao,
      rotulo,
      texto: motivo ? `Vaga vazia — ${motivo}` : 'Vaga vazia',
    }
  }
  /* Sem nome de região, o título JÁ é o município: a linha de baixo fica só com a UF,
     senão o mesmo nome apareceria duas vezes seguidas. */
  const municipioUf = nivelMunicipio
    ? null
    : v.nome_regiao
      ? [v.nome_municipio, v.uf].filter(Boolean).join(' · ') || null
      : v.uf || null
  return {
    tipo: 'regiao',
    chave: v.hex_id,
    posicao: v.posicao,
    rotulo,
    nome: v.nome_regiao || v.nome_municipio || TEXTO_SEM_DADO,
    hexCurto: hexCurto(v.hex_id),
    municipioUf,
    principal: principalDaVaga(v),
    secundaria: linhaSecundaria(v),
    destino: destinoDaVaga(v),
    vaga: v,
  }
}

function motivoDoSegmento(s: SegmentoTop10Payload, b: RecomendacaoTop10): string {
  for (const v of s.vagas) {
    const m = motivoDaVaga(v, b.rotulos)
    if (m) return m
  }
  return b.rotulos?.motivo?.renda_indisponivel ?? ''
}

/** "deste município" / "deste estado" / "do Brasil" — onde a régua procurou candidatos. */
function ondeDoRecorte(b: Pick<RecomendacaoTop10, 'recorte'>): string {
  if (b.recorte.nivel === 'municipio') return 'deste município'
  if (b.recorte.nivel === 'uf') return 'deste estado'
  return `do ${b.recorte.nome || 'país'}`
}

/**
 * A frase ÚNICA de um segmento calculado que não teve nenhum candidato no recorte. Montada
 * do payload (rótulo do segmento, nível do recorte, vagas da régua) — e sem o "Não há
 * OUTRA região" do motivo de vaga vazia, que só é verdade quando alguma vaga foi preenchida.
 */
function fraseSemCandidato(b: RecomendacaoTop10, s: SegmentoTop10Payload, titulo: string): string {
  const n = s.vagas.length
  const vagas = n === 1 ? 'a vaga fica vazia' : `as ${num(n)} vagas ficam vazias`
  return `Nenhuma região ${ondeDoRecorte(b)} atende à régua de ${titulo} — ${vagas}.`
}

/**
 * Os DOIS blocos fixos — [Mata Virgem, Premium] — com uma linha por vaga, na ordem do
 * servidor. Segmento indisponível leva `indisponivel` preenchido, e segmento calculado sem
 * nenhum candidato leva `semCandidato`: nos dois casos o componente mostra UMA mensagem, sem
 * cinco linhas repetidas. As linhas continuam lá, vazias, para quem quiser auditar.
 */
export function montarBlocosTop10(b: RecomendacaoTop10): BlocoTop10[] {
  const nivelMunicipio = b.recorte.nivel === 'municipio'
  return SEGMENTOS_TOP10.map((seg) => {
    const s = b[seg]
    const titulo = rotuloDoSegmento(b.rotulos, seg)
    const indisponivel = s.status === 'indisponivel'
    const nenhuma = !indisponivel && s.n_elegiveis === 0 && s.vagas.every((v) => v.vazia)
    return {
      segmento: seg,
      titulo,
      nElegiveis: s.n_elegiveis,
      textoCandidatos: indisponivel ? null : textoCandidatos(s.n_elegiveis),
      indisponivel: indisponivel
        ? {
            titulo: s.rotulo_status || b.rotulos?.status?.[s.status] || 'Indisponível',
            motivo: motivoDoSegmento(s, b),
          }
        : null,
      semCandidato: nenhuma ? fraseSemCandidato(b, s, titulo) : null,
      linhas: s.vagas.map((v) => linhaDaVaga(v, nivelMunicipio, b.rotulos)),
    }
  })
}

/**
 * Cabeçalho: "6 de 10 vagas preenchidas" + candidatos por segmento. Sem nada calculado
 * (staging sem o carimbo k), "Top 10 indisponível" e nenhum candidato — "0 de 10 vagas
 * preenchidas" afirmaria que a régua rodou e ninguém passou.
 */
export function cabecalhoTop10(b: RecomendacaoTop10): { vagas: string; candidatos: string | null } {
  if (top10Indisponivel(b)) return { vagas: `Top ${totalVagas(b)} indisponível`, candidatos: null }
  const vagas = `${num(vagasPreenchidas(b))} de ${num(totalVagas(b))} vagas preenchidas`
  const candidatos = SEGMENTOS_TOP10.map((seg) =>
    b[seg].status === 'indisponivel'
      ? `${rotuloDoSegmento(b.rotulos, seg)} indisponível`
      : `${textoCandidatos(b[seg].n_elegiveis)} ${rotuloDoSegmento(b.rotulos, seg)}`,
  ).join(' · ')
  return { vagas, candidatos }
}

/**
 * O texto da RÉGUA, montado só com os números do payload.
 *
 * Cláusulas condicionais seguem a régua: população mínima nula some; `exige_residual_medido`
 * decide se a frase diz "medido". Nenhum número aqui é literal — o teste troca a régua e
 * confere que o texto muda junto.
 */
export function textoDaRegua(
  regra: ReguaTop10,
  rotulos?: RecomendacaoTop10['rotulos'] | null,
): string {
  const mv = rotuloDoSegmento(rotulos, 'mata_virgem')
  const pr = rotuloDoSegmento(rotulos, 'premium')
  const m = regra.mata_virgem
  const p = regra.premium

  const criteriosMv = [
    `renda domiciliar a partir de ${renda(m.renda_domiciliar_min)}`,
    `${m.exige_residual_medido ? 'residual medido' : 'residual'} a partir de ${num(m.residual_min)} alunos`,
  ]
  if (m.populacao_min != null) {
    criteriosMv.push(`população a partir de ${num(m.populacao_min)} habitantes`)
  }

  const criteriosPr = [`score censitário a partir de ${numScore(p.score_min)}`]
  if (p.populacao_min != null) {
    criteriosPr.push(`população a partir de ${num(p.populacao_min)} habitantes`)
  }
  const condicoesPr = [`fora da ${mv}`]
  if (p.exige_residual_medido) condicoesPr.push('com residual medido')

  const vagas = plural(regra.vagas_por_segmento, 'região', 'regiões')
  return [
    `${mv}: ${juntarComE(criteriosMv)}, na ordem do residual.`,
    `${pr}: ${juntarComE(criteriosPr)}, ${juntarComE(condicoesPr)}, na ordem da população.`,
    `Até ${vagas} por segmento; vaga sem candidato fica vazia — um segmento nunca completa o outro.`,
    'Concorrência, viabilidade, aluguel e proximidade da Ultra não entram nesta conta.',
  ].join(' ')
}

const MESES_DA_REGUA: readonly string[] = Object.freeze([
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
])

/**
 * Rótulo de NEGÓCIO da versão da régua: "2026-10_v1" → "outubro de 2026, versão 1".
 *
 * O nome do arquivo e o número da decisão são detalhe técnico; quem lê a lista precisa
 * saber DE QUANDO é a régua. Fora do padrão `<ano>-<mês>_v<n>` (o carregador aceita outros
 * nomes) devolve `null` — sem inventar data. Espelho de `_rotulo_versao_regua` do servidor.
 */
export function rotuloDaVersaoDaRegua(versao: string): string | null {
  const m = /^(\d{4})-(\d{2})_v(\d+)$/.exec(versao)
  if (!m) return null
  const mes = Number(m[2])
  if (mes < 1 || mes > 12) return null
  return `${MESES_DA_REGUA[mes - 1]} de ${m[1]}, versão ${Number(m[3])}`
}

/** O carimbo de exibição: "Régua de outubro de 2026, versão 1" (fora do padrão, a versão crua). */
export function textoVersaoDaRegua(regra: Pick<ReguaTop10, 'versao'>): string {
  const rotulo = rotuloDaVersaoDaRegua(regra.versao)
  return rotulo ? `Régua de ${rotulo}` : `Régua ${regra.versao}`
}

/** O detalhe técnico (dica ao passar o mouse): a versão crua e a decisão que a aprovou. */
export function referenciaTecnicaDaRegua(regra: Pick<ReguaTop10, 'versao' | 'dec'>): string {
  return `${regra.versao} · ${regra.dec}`
}

/** "Top 10 do Brasil" / "Top 10 de SP" / "Top 10 de São José dos Campos". */
export function tituloTop10(b: Pick<RecomendacaoTop10, 'regra' | 'recorte'>): string {
  const t = totalVagas(b)
  if (b.recorte.nivel === 'brasil') return `Top ${t} do ${b.recorte.nome || 'país'}`
  if (b.recorte.nivel === 'uf') return `Top ${t} de ${b.recorte.uf || b.recorte.nome || 'estado'}`
  return `Top ${t} de ${b.recorte.nome || 'município'}`
}

/* --- Leituras do recorte (Oportunidades) ---------------------------------------------- */

/** Quantos itens cada camada de LEITURA mostra em Oportunidades. */
export const TOP_POR_LEITURA = 5

/**
 * As camadas 1 a 4 do recorte, com o topo de cada uma — as LEITURAS, que não entram na
 * recomendação. A camada 5 (o Top 10) fica de fora de propósito: ela é o hero da tela, e
 * repeti-la aqui duplicaria a resposta — com o agravante de que um corte de 5 itens sobre
 * os 10 do Top 10 apagaria o bloco Premium inteiro.
 */
export function leiturasDoRecorte(passos: readonly Passo[]): { passo: Passo; itens: RankItem[] }[] {
  return passos
    .filter((p) => p.n <= 4)
    .map((p) => ({ passo: p, itens: p.itens.slice(0, TOP_POR_LEITURA) }))
}

/**
 * Estado vazio de uma camada de LEITURA (1 a 4) do painel, onde há o Top 10.
 *
 * Sem linguagem de funil: com a recomendação única essas camadas não filtram nada para a
 * seguinte, e mandar "escolher outro município" seria o mesmo "Avalie outro município" que
 * saiu da tela — o Top 10 lê o recorte inteiro, com régua própria. No estado os itens das
 * leituras são cidades; no município, regiões (hexágonos).
 */
export function textoLeituraVazia(
  nivel: 'uf' | 'municipio' | undefined,
  b: Pick<RecomendacaoTop10, 'regra'>,
): string {
  const noEstado = nivel === 'uf'
  return (
    `${noEstado ? 'Nenhuma cidade' : 'Nenhuma região'} aparece nesta leitura. ` +
    `O Top ${totalVagas(b)}, na camada 5, lê o ${noEstado ? 'estado' : 'município'} inteiro ` +
    'com régua própria.'
  )
}

/* --- Mapa ---------------------------------------------------------------------------- */

/** O que o mapa sabe de um hexágono do Top 10: rótulo, segmento e a chave que o ordenou. */
export interface MarcaTop10 {
  segmento: SegmentoTop10
  posicao: number
  /** MV1..MV5 / P1..P5. */
  rotulo: string
  rotuloSegmento: string
  chaveRotulo: string
  chaveValor: string
}

export interface MapaTop10 {
  porHex: Readonly<Record<string, MarcaTop10>>
  /** Os hexágonos do Top 10, na ordem MV1..MVn, P1..Pn. */
  ids: readonly string[]
  /** Muda quando o Top 10 muda — vai nos `updateTriggers` do deck.gl. */
  chave: string
  /** "Top 10" — o total sai da régua (rótulo da linha do tooltip). */
  titulo: string
}

function marcaDaVaga(v: VagaTop10, rotulos: RecomendacaoTop10['rotulos'] | undefined): MarcaTop10 {
  const premium = v.segmento === 'premium'
  return {
    segmento: v.segmento,
    posicao: v.posicao,
    rotulo: rotuloNoMapa(v),
    rotuloSegmento: rotuloDoSegmento(rotulos, v.segmento),
    chaveRotulo: premium ? 'População do Censo' : v.residual_medido ? 'Residual medido' : 'Residual',
    chaveValor: premium
      ? v.populacao == null
        ? TEXTO_SEM_DADO
        : `${num(v.populacao)} hab.`
      : v.residual_medido && v.residual != null
        ? `${alunos(v.residual)} alunos`
        : 'não medido',
  }
}

/** Índice hex_id → marca, para pintar, rotular e explicar os 10 no mapa. */
export function mapaTop10(b: RecomendacaoTop10): MapaTop10 {
  const porHex: Record<string, MarcaTop10> = {}
  const ids: string[] = []
  for (const seg of SEGMENTOS_TOP10) {
    for (const v of b[seg].vagas) {
      if (v.vazia || !v.hex_id || Object.prototype.hasOwnProperty.call(porHex, v.hex_id)) continue
      porHex[v.hex_id] = marcaDaVaga(v, b.rotulos)
      ids.push(v.hex_id)
    }
  }
  return {
    porHex: Object.freeze(porHex),
    ids: Object.freeze(ids),
    chave: ids.map((id) => `${porHex[id].rotulo}:${id}`).join('|'),
    titulo: `Top ${totalVagas(b)}`,
  }
}

/**
 * Os hexágonos do mapa DEPOIS do filtro, com os do Top 10 que o filtro tirou de volta.
 *
 * As 10 regiões aparecem SEMPRE, mesmo com o filtro de faixa M1 ligado: um Premium de faixa
 * "Média" sumiria do mapa enquanto o painel o lista. Sem duplicar, e devolvendo o MESMO
 * array quando não há o que repor (memo estável).
 */
export function hexesComTop10<H extends { id: string }>(
  filtrados: H[],
  todos: readonly H[],
  ids: readonly string[],
): H[] {
  if (!ids.length) return filtrados
  const presentes = new Set(filtrados.map((h) => h.id))
  const faltam = new Set(ids.filter((id) => !presentes.has(id)))
  if (!faltam.size) return filtrados
  const repostos = todos.filter((h) => faltam.has(h.id))
  return repostos.length ? [...filtrados, ...repostos] : filtrados
}

export interface CoresTop10 {
  mv: RGBA
  premium: RGBA
  fora: RGBA
}

const COR_DO_SEGMENTO: Readonly<Record<SegmentoTop10, 'mv' | 'premium'>> = Object.freeze({
  mata_virgem: 'mv',
  premium: 'premium',
})

/**
 * Cor do hexágono na camada 5 com o Top 10: a do segmento (com o alpha de hexágono do tema)
 * para os 10, e o "fora do Top 10" — esmaecido, com o alpha próprio — para todo o resto.
 */
export function corTop10(
  marca: MarcaTop10 | null | undefined,
  cores: CoresTop10,
  alphaHex: number,
): RGBA {
  if (!marca) return [cores.fora[0], cores.fora[1], cores.fora[2], cores.fora[3]]
  const c = cores[COR_DO_SEGMENTO[marca.segmento]]
  return [c[0], c[1], c[2], alphaHex]
}

export interface LegendaTop10 {
  titulo: string
  itens: { nome: string; cor: string }[]
  fora: { nome: string; cor: string }
}

/**
 * Legenda da camada 5 com o Top 10: Mata Virgem / Premium / fora do Top 10. Sem nada
 * calculado (staging sem o carimbo k) o mapa não tem segmento nenhum a pintar: a legenda diz
 * "Top 10 indisponível" e o esmaecido é "recomendação suspensa" — e não "fora do Top 10",
 * que leria como "nenhuma região passou na régua".
 */
export function legendaTop10(b: RecomendacaoTop10): LegendaTop10 {
  const t = totalVagas(b)
  if (top10Indisponivel(b)) {
    return {
      titulo: `Top ${t} indisponível`,
      itens: [],
      fora: { nome: 'recomendação suspensa', cor: TOKEN_COR_TOP10.fora },
    }
  }
  return {
    titulo: `Top ${t} por hexágono`,
    itens: SEGMENTOS_TOP10.map((seg) => ({
      nome: rotuloDoSegmento(b.rotulos, seg),
      cor: TOKEN_COR_TOP10[seg],
    })),
    fora: { nome: `fora do Top ${t}`, cor: TOKEN_COR_TOP10.fora },
  }
}

/* --- Textos de front por país (DEC-047: tabela, nunca ramo por país) ---------------------
   Os textos que NÃO vêm do payload (landing do mapa, card do Início, rótulo do filtro, selo
   da faixa M1, título da metodologia) e mudam com a recomendação única. País fora da tabela
   (a Argentina hoje) recebe `null`, e quem chama usa o texto legado de sempre — nada muda lá.
   `test_fio_de_alarme_pais.py` reprova comparação com literal de país; tabela é a forma
   certa de variar por país. */

export interface TextosTop10Front {
  regiaoLinha: string
  landingMapa: string
  filtroFaixaRotulo: string
  filtroFaixaLabel: string
  seloFaixaPrefixo: string
  seloFaixaTitulo: string
  metodologiaTitulo: string
  /** Rótulo do corte das camadas 1 a 4 na metodologia: régua de LEITURA, não filtro. */
  metodologiaCorteLeitura: string
  /** Rótulo do corte da camada 5 na metodologia (a régua do Top 10). */
  metodologiaCorteTop10: string
}

export const TEXTOS_TOP10_POR_PAIS: Readonly<Record<string, TextosTop10Front>> = Object.freeze({
  BR: Object.freeze({
    regiaoLinha: 'Camadas de leitura e o Top 10 por hexágono, do estado ao município.',
    landingMapa:
      'O mapa lê o território em camadas — potencial, demanda, concorrência e crescimento — e mostra o Top 10 por hexágono do recorte.',
    filtroFaixaRotulo: 'FAIXA M1',
    filtroFaixaLabel: 'Filtrar pela faixa M1',
    seloFaixaPrefixo: 'Faixa M1 · ',
    seloFaixaTitulo:
      'Faixa do M1: percentil de renda e população. Não considera a concorrência instalada — isso é o bloco “Quanto de mercado sobra”.',
    metodologiaTitulo: 'Como o mapa lê o território e monta o Top 10',
    metodologiaCorteLeitura: 'régua da leitura',
    metodologiaCorteTop10: 'entra no Top 10',
  }),
})

/**
 * Cor por TOKEN do chip de um segmento do Top 10 numa lista de etiquetas (a da metodologia):
 * a mesma de `--top10-mv`/`--top10-premium` que pinta o mapa, o selo MV1/P1 e a legenda. O
 * servidor publica o `tom` da faixa dentro do tipo `Tom` (azul para o Premium), que é a
 * identidade de OUTRA camada; sem isto o Premium sairia azul no manual e violeta no mapa.
 * `null` para qualquer etiqueta que não seja um segmento.
 */
export function corDaEtiquetaTop10(etiqueta: string): string | null {
  for (const seg of SEGMENTOS_TOP10) {
    if (etiqueta === ROTULO_SEGMENTO_TOP10[seg]) return TOKEN_COR_TOP10[seg]
  }
  return null
}

/** Textos do país da instância; `null` = país sem régua (o chamador usa o texto legado). */
export function textosTop10(pais: string = perfilDoCliente().pais): TextosTop10Front | null {
  return Object.prototype.hasOwnProperty.call(TEXTOS_TOP10_POR_PAIS, pais)
    ? TEXTOS_TOP10_POR_PAIS[pais]
    : null
}
