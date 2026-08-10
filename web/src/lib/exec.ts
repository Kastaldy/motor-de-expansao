/**
 * Lógica pura da Visão Executiva — extraída da tela SÓ para ser testável sem DOM.
 *
 * O projeto não tem `@testing-library/react`, e o precedente da casa (`lib/select-filter.ts`,
 * extraído de `Select.tsx`) é este: o que dá para testar sem montar componente sai do
 * componente. Nada aqui toca React.
 */

import { rotuloDoPeriodo } from './periodo'
import type { RedeCarteira, RedeMetrica, RedeSeveridade, RedeUnidade } from './types'
import { brl, brlCurto, num, pct } from './format'

/** Cor de cada nível do semáforo. Uma definição só, usada na tabela, no mapa e nos chips. */
export const COR_SEVERIDADE: Record<RedeSeveridade, string> = {
  alta: '#ff5a6e',
  media: '#e0b25a',
  ok: '#3cc878',
  sem_base: '#7c8798',
}

export const ORDEM_SEVERIDADE: RedeSeveridade[] = ['alta', 'media', 'ok', 'sem_base']

/**
 * Formata uma métrica pela sua natureza.
 *
 * O pega-ratão que isto blinda: **churn e conversão chegam em PERCENTUAL** desta API
 * (5,93 = 5,93%), enquanto na Viabilidade as taxas chegam em FRAÇÃO (0,0593). Um `pctFrac`
 * aqui mostraria "0,1%" de churn e ninguém desconfiaria.
 */
export function formatarMetrica(valor: number | null | undefined, formato: string): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return '—'
  switch (formato) {
    case 'brl':
      return brl(valor, false, valor < 1000 ? 2 : 0)
    // Faturamento por extenso, com centavo. O time de campo leva o número para a conversa
    // com o franqueado e precisa do valor de verdade: "R$ 141k" é bom para comparar duas
    // unidades de relance e inútil para conferir contra o extrato. A forma curta continua
    // nos gráficos, onde doze rótulos disputam a mesma linha (pedido do Felipe, 2026-08-10).
    case 'brl_pleno':
      return brl(valor, false, 2)
    case 'brl_curto':
      return brlCurto(valor)
    case 'pct':
      return pct(valor, 1)
    case 'nota':
      return num(valor, 0)
    default:
      return num(valor, 0)
  }
}

/** `12` -> `"12º de 86"`; sem posição, texto honesto em vez de um traço mudo. */
export function rotuloRanking(metrica: RedeMetrica | undefined): string {
  if (!metrica?.rank || !metrica.rank_total) return 'sem posição (unidade nova)'
  return `${metrica.rank}º de ${metrica.rank_total}`
}

/** `-64,2` -> `"64,2% abaixo da média da rede"`. */
export function rotuloVsMedia(metrica: RedeMetrica | undefined): string {
  const v = metrica?.vs_media_pct
  if (v === null || v === undefined) return 'sem comparação com a rede'
  if (Math.abs(v) < 0.05) return 'na média da rede'
  return `${pct(Math.abs(v), 1)} ${v > 0 ? 'acima' : 'abaixo'} da média da rede`
}

/** Título de acessibilidade da célula: o quarteto inteiro em texto. */
export function tituloDaCelula(rotulo: string, metrica: RedeMetrica | undefined, formato: string): string {
  if (!metrica) return rotulo
  return [
    `${rotulo}: ${formatarMetrica(metrica.atual, formato)}`,
    `M-1: ${formatarMetrica(metrica.m1, formato)}`,
    rotuloRanking(metrica),
    rotuloVsMedia(metrica),
  ].join(' · ')
}

export interface LeituraDelta {
  /** variação a exibir, já em módulo */
  valor: number
  /** 'pct' = variação relativa; 'pontos' = diferença absoluta (churn, NPS) */
  modo: 'pct' | 'pontos'
  subiu: boolean
  /** true quando a variação é boa PARA ESTA MÉTRICA (churn subindo é ruim) */
  bom: boolean
  /** abaixo do limiar de ruído: mostra travessão, não seta */
  estavel: boolean
}

const RUIDO = 0.05

/**
 * Lê a variação de uma métrica com a direção CERTA.
 *
 * Dois defeitos do dashboard que o time usa hoje, que isto impede de herdar:
 * 1. churn subindo 40% aparecia com seta verde — o delta usava a mesma direção para
 *    todas as métricas;
 * 2. churn e NPS variavam em "%" relativo, o que confunde: NPS de 2 para 4 vira "+100%".
 *    Aqui essas duas variam em PONTOS.
 */
export function lerDelta(
  metrica: RedeMetrica | undefined,
  bomSubindo: boolean,
  emPontos = false,
): LeituraDelta | null {
  if (!metrica) return null
  if (emPontos) {
    if (metrica.atual === null || metrica.m1 === null) return null
    const d = metrica.atual - metrica.m1
    return {
      valor: Math.abs(d),
      modo: 'pontos',
      subiu: d > 0,
      bom: d > 0 === bomSubindo,
      estavel: Math.abs(d) < RUIDO,
    }
  }
  const d = metrica.delta_pct
  if (d === null || d === undefined) return null
  return {
    valor: Math.abs(d),
    modo: 'pct',
    subiu: d > 0,
    bom: d > 0 === bomSubindo,
    estavel: Math.abs(d) < RUIDO,
  }
}

/** Métricas cuja variação se lê em PONTOS, não em percentual do percentual. */
export const METRICAS_EM_PONTOS = new Set(['churn_pct', 'nps', 'conversao_pct', 'pct_agregador_alunos'])

/**
 * Ordena a carteira no cliente. Nulos SEMPRE por último, **nas duas direções**.
 *
 * O `?? -Infinity` da v1 só funcionava em `desc`: em `asc`, quem não tinha o número subia
 * para o topo da lista de trabalho — o pior lugar possível para um dado ausente.
 */
export function ordenarUnidades(
  unidades: RedeUnidade[],
  chave: string,
  direcao: 'asc' | 'desc',
): RedeUnidade[] {
  const sinal = direcao === 'asc' ? 1 : -1
  const valorDe = (u: RedeUnidade): number | null => {
    if (chave === 'prioridade') return u.prioridade
    if (chave === 'nome') return null
    return u.metricas[chave]?.atual ?? null
  }
  return [...unidades].sort((a, b) => {
    if (chave === 'nome') return sinal * a.nome.localeCompare(b.nome, 'pt-BR')
    const va = valorDe(a)
    const vb = valorDe(b)
    if (va === null && vb === null) return a.nome.localeCompare(b.nome, 'pt-BR')
    if (va === null) return 1
    if (vb === null) return -1
    if (va === vb) return a.nome.localeCompare(b.nome, 'pt-BR')
    return sinal * (va - vb)
  })
}

/**
 * Busca local por nome/cidade/consultor, sem acento e sem caixa.
 *
 * Existe além do filtro do servidor porque digitar não pode custar um round-trip: o
 * payload inteiro já está no cliente.
 */
export function filtrarUnidades(unidades: RedeUnidade[], termo: string): RedeUnidade[] {
  const alvo = normalizar(termo)
  if (!alvo) return unidades
  return unidades.filter((u) =>
    [u.nome, u.cidade, u.consultor, u.uf, u.master_franquia]
      .filter(Boolean)
      .some((campo) => normalizar(String(campo)).includes(alvo)),
  )
}

export function normalizar(texto: string): string {
  return texto
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .trim()
}

const MESES_PT = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']

/** `"2026-06"` -> `"Jun/2026"`. O que não for competência volta como veio.
 *
 *  A tolerância não é zelo excessivo: desde o calendário de período livre, a base do SSS
 *  chega como `"2026-06"` quando o intervalo é um mês inteiro e como
 *  `"15/07/2025 a 03/08/2025"` quando não é. A versão antiga fazia `split('-')` e caía num
 *  `charAt` de `undefined`, derrubando a aba INTEIRA para tela preta — não o rótulo, a aba.
 */
export function rotuloMesCompetencia(m: string): string {
  const [ano, mes] = String(m ?? '').split('-')
  const nome = MESES_PT[Number(mes) - 1]
  if (!nome || !ano) return String(m ?? '')
  return `${nome.charAt(0).toUpperCase()}${nome.slice(1)}/${ano}`
}

/** `"2026-06"` -> `"jun"` (eixo de gráfico, onde o ano é redundante). */
export function rotuloMesCurto(m: string): string {
  const [, mes] = m.split('-')
  return MESES_PT[Number(mes) - 1] ?? mes
}

/** Lado do tile do basemap: a escala de zoom do MapLibre/deck.gl é definida sobre ele. */
const LADO_DO_TILE = 512
/* Fração do card que o bbox ocupa. O respiro não é estética: o bbox enquadra o CENTRO
   das unidades, e a bolha tem até 40 px de raio — com pouca folga, a unidade da ponta
   aparece cortada pela borda do card. */
const RESPIRO = 0.8

/** Latitude -> fração da altura do mundo em Mercator (0 no topo, 1 embaixo). */
function fracaoMercator(lat: number): number {
  const rad = (Math.max(-85, Math.min(85, lat)) * Math.PI) / 180
  return (1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2
}

/**
 * Enquadramento do mapa a partir do bbox das unidades.
 *
 * A média das coordenadas (o que a v1 fazia) cai no meio do nada quando a rede é
 * nacional: com unidades de SC ao RN, o "centro" fica num ponto sem nenhuma unidade e o
 * zoom fixo corta metade do país.
 *
 * O `viewport` não é refinamento: sem ele, a conta embute a suposição de um card de
 * 512x512. Num card estreito — que é o do mapa desde que ele voltou para o lado da
 * carteira — a mesma conta devolve zoom alto demais e as unidades das pontas ficam
 * FORA do quadro. Como as duas dimensões cortam, o zoom é o menor dos dois: o que faz
 * a largura caber e o que faz a altura caber. A altura passa pela projeção de Mercator,
 * senão o Brasil (que vai de +5 a -33 graus) sai apertado.
 */
export function enquadrar(
  bbox: { min_lat: number; min_lng: number; max_lat: number; max_lng: number } | null,
  centro: { lat: number | null; lng: number | null },
  viewport?: { largura: number; altura: number },
): { latitude: number; longitude: number; zoom: number } {
  if (!bbox) {
    return { latitude: centro.lat ?? -15.78, longitude: centro.lng ?? -47.93, zoom: 3.4 }
  }
  const largura = viewport && viewport.largura > 40 ? viewport.largura : LADO_DO_TILE
  const altura = viewport && viewport.altura > 40 ? viewport.altura : LADO_DO_TILE
  const latitude = (bbox.min_lat + bbox.max_lat) / 2
  const longitude = (bbox.min_lng + bbox.max_lng) / 2
  // Piso em 1e-4 para o bbox degenerado (uma unidade só) não virar divisão por zero.
  const fracaoLng = Math.max((bbox.max_lng - bbox.min_lng) / 360, 1e-4)
  const fracaoLat = Math.max(
    Math.abs(fracaoMercator(bbox.min_lat) - fracaoMercator(bbox.max_lat)),
    1e-4,
  )
  const zoom = Math.min(
    Math.log2((largura * RESPIRO) / (LADO_DO_TILE * fracaoLng)),
    Math.log2((altura * RESPIRO) / (LADO_DO_TILE * fracaoLat)),
  )
  return { latitude, longitude, zoom: Math.min(11, Math.max(2, zoom)) }
}

/**
 * O mapa deve voltar ao enquadramento automático?
 *
 * Duas coisas disparam o reenquadramento e elas NÃO valem o mesmo:
 *
 * - `recorte` — mudou o conjunto de unidades (outro filtro, outra competência). Reenquadra
 *   sempre, mesmo por cima do ajuste manual: o pan antigo aponta para unidades que não
 *   estão mais na tela.
 * - `tamanho` — mudou só a caixa do mapa (janela redimensionada, trilho refluído). Aqui o
 *   ajuste manual PREVALECE. Sem essa distinção, digitar na busca desfazia o zoom da
 *   pessoa: a busca filtra só na tela, não muda o bbox, mas encolhe a tabela — e o trilho
 *   acompanha a altura da carteira.
 */
export function deveReenquadrar(motivo: 'recorte' | 'tamanho', mexeu: boolean): boolean {
  return motivo === 'recorte' || !mexeu
}

/** Query string da carteira, omitindo o que está vazio. */
export function queryDaCarteira(filtros: Record<string, string | undefined>): string {
  const q = new URLSearchParams()
  for (const [chave, valor] of Object.entries(filtros)) {
    if (valor) q.set(chave, valor)
  }
  const texto = q.toString()
  return texto ? `?${texto}` : ''
}

/* ---------------------------------------------------------------------------
   Painel do recorte — a leitura em prosa e os dois extremos da carteira.

   Ambas as funções são LEITURA: todo número que aparece aqui já veio somado do
   servidor. Foi a duplicação de contas entre tela e backend que produziu, na v1,
   dois "crescimento da rede" diferentes na mesma página.
   --------------------------------------------------------------------------- */

const MESES_PT_LONGO = [
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

/** `"2026-07"` -> `"julho/2026"`. Separado de `rotuloMesCompetencia` porque na PROSA o
 *  mês abreviado ("Jul/2026") lê como etiqueta de eixo, não como parte de uma frase. */
function mesPorExtenso(m: string): string {
  const [ano, mes] = String(m ?? '').split('-')
  const nome = MESES_PT_LONGO[Number(mes) - 1]
  return nome ? `${nome}/${ano}` : String(m ?? '')
}

/** `['a', 'b', 'c']` -> `'a, b e c'`. */
function juntarComE(partes: string[]): string {
  if (partes.length <= 1) return partes[0] ?? ''
  return `${partes.slice(0, -1).join(', ')} e ${partes[partes.length - 1]}`
}

function plural(n: number, um: string, varios: string): string {
  return n === 1 ? um : varios
}

function maiusculaInicial(texto: string): string {
  return `${texto.charAt(0).toUpperCase()}${texto.slice(1)}`
}

/** Contra quem o SSS compara. A guarda não é purismo: `rotuloMesCompetencia('')` estoura
 *  em `nome.charAt`, e a competência-base é o único campo do SSS que a frase não pode
 *  simplesmente omitir — sem ela, "cresce 9,0%" não diz contra o quê. */
function contraMesBase(competenciaBase: string | undefined): string {
  return competenciaBase
    ? `contra ${rotuloMesCompetencia(competenciaBase)}`
    : 'contra o mesmo mês do ano anterior'
}

/**
 * O período a que os números da primeira frase se referem.
 *
 * Dizer "em agosto" num mês em curso é o erro que faz o leitor comparar 3 dias com
 * 31 e concluir que a rede desabou. Com a competência aberta, a frase carrega a
 * JANELA ("de 1 a 03/08"); só o mês fechado pode ser chamado de fechamento.
 */
function periodoDoRecorte(carteira: RedeCarteira): string {
  // Com período livre, "no fechamento de julho/2026" só vale quando o intervalo É julho
  // inteiro. Recorte solto fala por extenso — dizer o mês de um recorte de 10 dias faria
  // a frase prometer trinta.
  if (carteira.periodo && !carteira.periodo.mes_inteiro) {
    return `no período de ${rotuloDoPeriodo(carteira.periodo).toLowerCase()}`
  }
  if (carteira.mes_completo) return `no fechamento de ${mesPorExtenso(carteira.mes)}`
  // "de 1 a 03/08" mistura dia solto com data completa e lê como erro de digitação. O mês
  // por extenso já está na frase inteira, então basta o dia: "no acumulado de 03/08".
  const diaMes = String(carteira.referencia ?? '').slice(0, 5)
  return /^\d{2}\/\d{2}$/.test(diaMes)
    ? `no acumulado do mês até ${diaMes}`
    : `em ${mesPorExtenso(carteira.mes)}`
}

/**
 * Frases do painel: leitura pronta do recorte, feita SÓ com números que o servidor já
 * calculou. Nenhuma conta nova aqui — formatação e concordância.
 *
 * Duas regras mandam no formato:
 *
 * 1. **Cláusula sem número não existe.** `num`/`brl` devolvem `TEXTO_SEM_DADO` para
 *    nulo, e "com Não disponível de faturamento" no meio de uma frase lê como defeito
 *    da tela, não como dado ausente. O travessão tem o mesmo problema: serve em célula
 *    de tabela, não em prosa. Então o KPI nulo derruba a oração inteira.
 * 2. **O sinal vive no VERBO.** "cresce −2,5%" é a construção que faz o olho ler alta
 *    onde houve queda; o percentual entra sempre em módulo, atrás de cresce/cai.
 *
 * `rotuloRecorte` chega pronto da tela ('a rede', 'MARISE', 'MARISE · RJ') porque é ela
 * quem sabe quais filtros estão ativos; aqui ele é só o sujeito da oração.
 */
export function narrativaDoRecorte(carteira: RedeCarteira, rotuloRecorte: string): string[] {
  const sujeito = maiusculaInicial(rotuloRecorte.trim() || 'o recorte')
  const noRecorte = carteira.totais?.no_recorte ?? 0

  // Recorte vazio: qualquer frase seguinte falaria de crescimento e de alertas de um
  // conjunto que não existe. Uma frase só, e ela diz o que fazer a seguir.
  if (noRecorte === 0) {
    return [`${sujeito} não tem nenhuma unidade no recorte selecionado; ajuste os filtros.`]
  }

  const frases: string[] = []

  const numeros: string[] = []
  const faturamento = carteira.kpis?.faturamento?.atual ?? null
  const ativos = carteira.kpis?.ativos?.atual ?? null
  if (faturamento !== null) numeros.push(`${brl(faturamento, true)} de faturamento`)
  if (ativos !== null) numeros.push(`${num(ativos)} ${plural(ativos, 'aluno ativo', 'alunos ativos')}`)
  frases.push(
    `${sujeito} tem ${num(noRecorte)} ${plural(noRecorte, 'unidade', 'unidades')}` +
      (numeros.length > 0 ? `, com ${juntarComE(numeros)}` : '') +
      ` ${periodoDoRecorte(carteira)}.`,
  )

  const sss = carteira.sss
  if (!sss?.disponivel) {
    frases.push(
      `Não há base comparável neste recorte ${contraMesBase(sss?.competencia_base)}: nenhuma ` +
        'unidade operou o mês inteiro nos dois períodos, então o crescimento na mesma base ' +
        'não é medido.',
    )
  } else {
    // A base comparável é o que separa "crescemos" de "abrimos loja" — por isso ela
    // aparece ANTES do número, e não como ressalva no fim da frase.
    const base =
      sss.unidades_recorte === 1
        ? 'na mesma base (a única unidade do recorte)'
        : `na mesma base (${sss.unidades} das ${sss.unidades_recorte} unidades)`
    const contra = contraMesBase(sss.competencia_base)
    const variacao = sss.metricas?.faturamento?.var_pct ?? null
    let miolo: string
    if (variacao === null) {
      miolo = `${maiusculaInicial(base)}, a variação de faturamento ${contra} não foi apurada`
    } else if (Math.abs(variacao) < RUIDO) {
      miolo = `${maiusculaInicial(base)}, o faturamento fica estável ${contra}`
    } else {
      const verbo = variacao > 0 ? 'cresce' : 'cai'
      miolo = `${maiusculaInicial(base)}, o faturamento ${verbo} ${pct(Math.abs(variacao), 1)} ${contra}`
    }
    const fora =
      sss.unidades_fora > 0
        ? `; ${
            sss.unidades_fora === 1
              ? 'a outra não existia há um ano'
              : `as outras ${sss.unidades_fora} não existiam há um ano`
          }`
        : ''
    frases.push(`${miolo}${fora}.`)
  }

  // O diagnóstico é de uma competência FECHADA, quase sempre diferente da que está na
  // tela. Sem dizer qual, o time cobra na reunião um alerta que já mudou de mês.
  const alta = carteira.semaforo?.alta ?? 0
  const media = carteira.semaforo?.media ?? 0
  const quando = carteira.competencia_diagnostico
    ? `O diagnóstico de ${rotuloMesCompetencia(carteira.competencia_diagnostico)}`
    : 'O diagnóstico'
  if (alta === 0 && media === 0) {
    frases.push(`${quando} não aponta nenhuma unidade em prioridade alta ou em atenção.`)
  } else {
    const partes: string[] = []
    if (alta > 0) partes.push(`${alta} ${plural(alta, 'unidade', 'unidades')} em prioridade alta`)
    if (media > 0) {
      partes.push(
        partes.length > 0 ? `${media} em atenção` : `${media} ${plural(media, 'unidade', 'unidades')} em atenção`,
      )
    }
    frases.push(`${quando} aponta ${juntarComE(partes)}.`)
  }

  const conversao = carteira.funil?.conversao_pct ?? null
  if (conversao !== null) {
    const visitas = carteira.funil?.visitas ?? null
    frases.push(
      `A conversão de visita em aluno fica em ${pct(conversao, 1)}` +
        (visitas !== null ? `, sobre ${num(visitas)} ${plural(visitas, 'visita', 'visitas')} no período` : '') +
        '.',
    )
  }

  return frases
}

/**
 * Quem puxa e quem segura o recorte, por variação de faturamento contra M-1.
 *
 * Só entra unidade COMPARÁVEL: quem inaugurou dentro da competência tem M-1 parcial (ou
 * nenhum) e ocuparia o topo por construção, com um "+900%" que não é desempenho. É a
 * mesma exclusão que o ranking do servidor já faz — os dois têm de concordar, senão a
 * unidade em destaque no painel não aparece no ranking da tabela ao lado.
 *
 * `seguram` nunca repete quem está em `puxam`: com 7 elegíveis e `quantos = 5` as duas
 * fatias se sobrepõem em 3, e a mesma unidade sairia ao mesmo tempo como quem puxa e
 * como quem segura. Nesse caso `seguram` encolhe (2 nomes) em vez de mentir.
 */
export interface DestaqueDoRecorte {
  unidade: RedeUnidade
  /** variação de faturamento na base escolhida, em % */
  variacao_pct: number
  /** faturamento do período que gerou a variação — o par do número acima, nunca o MTD */
  faturamento: number | null
}

/** Contra o que "quem puxa e quem segura" compara.
 *
 *  `sss` = o mesmo mês um ano antes, unidade a unidade — a leitura que o time pediu para
 *  poder abrir a conta do crescimento comparável da carteira.
 *  `mes` = o último mês FECHADO contra o anterior, que responde "o que mudou agora". */
export type BaseDoDestaque = 'sss' | 'mes'

export interface DestaquesDoRecorte {
  puxam: DestaqueDoRecorte[]
  seguram: DestaqueDoRecorte[]
  /** lista COMPLETA, na mesma ordem, para quando o operador quiser ver todas */
  todas: DestaqueDoRecorte[]
  /** unidades sem base comparável nesta leitura — ficam à vista, e não somem */
  semBase: RedeUnidade[]
  competencia: string | null
}

export function destaquesDoRecorte(
  unidades: RedeUnidade[],
  base: BaseDoDestaque = 'sss',
  quantos = 5,
): DestaquesDoRecorte {
  // Nenhuma das duas bases é o `delta_pct` do quarteto, e por um motivo medido: o
  // quarteto compara MTD contra MTD, então no dia 3 da competência em curso uma unidade
  // que saiu de R$ 400 para R$ 26 mil aparece com +6.239% e lidera "quem puxa".
  const leitura = (u: RedeUnidade) =>
    base === 'sss'
      ? { v: u.sss?.var_pct ?? null, fat: u.sss?.faturamento ?? null }
      : { v: u.fechado?.variacao_pct ?? null, fat: u.fechado?.faturamento ?? null }

  const elegiveis: { u: RedeUnidade; v: number; fat: number | null }[] = []
  const semBase: RedeUnidade[] = []
  for (const u of unidades) {
    const { v, fat } = leitura(u)
    if (u.comparavel && v !== null && Number.isFinite(v)) elegiveis.push({ u, v, fat })
    else semBase.push(u)
  }

  const ordenadas = elegiveis
    // Desempate por nome: sem ele, duas unidades com a mesma variação trocam de lugar
    // entre renders e a lista "pisca" a cada refetch.
    .sort((a, b) => (a.v === b.v ? a.u.nome.localeCompare(b.u.nome, 'pt-BR') : b.v - a.v))
    .map<DestaqueDoRecorte>((e) => ({ unidade: e.u, variacao_pct: e.v, faturamento: e.fat }))

  // Separado por SINAL, e não por posição na lista. Cortar as N primeiras e as N últimas
  // parece equivalente e não é: num recorte de 4 unidades comparáveis, as quatro caíam em
  // "quem puxa" — inclusive as duas que estavam CAINDO 2,2% e 4,0%. Quem puxa cresce;
  // quem segura cai. Variação exatamente zero não é nem uma coisa nem outra.
  const teto = Math.max(quantos, 0)
  const puxam = ordenadas.filter((d) => d.variacao_pct > 0).slice(0, teto)
  const caindo = ordenadas.filter((d) => d.variacao_pct < 0)
  const seguram = caindo.slice(Math.max(caindo.length - teto, 0)).reverse()
  const competencia =
    base === 'sss'
      ? (unidades.find((u) => u.sss?.competencia_base)?.sss?.competencia_base ?? null)
      : (unidades.find((u) => u.fechado?.competencia)?.fechado?.competencia ?? null)
  return { puxam, seguram, todas: ordenadas, semBase, competencia }
}
