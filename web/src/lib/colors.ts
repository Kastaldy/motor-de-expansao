/* ---------------------------------------------------------------------------
   Cores dos hexagonos — porte fiel do dashboard Streamlit.

   Fonte da verdade: src/motor_expansao/dashboard/
     - constants.RESIDUAL_SCORE_BANDS      (10 faixas de 10 pontos, vermelho->verde)
     - utils.score_band_to_color(score, alpha=170)
     - components._DISCARDED_FILL / _NAN_SCORE_FILL / _DISCARDED_LINE

   Regra canonica (CLAUDE.md §5): faixas de 10 pontos via RESIDUAL_SCORE_BANDS.
   M1 colore por score_priorizacao, censo por score_setor_2022_calibrado,
   hibrido por score_expansao_hibrido, residual por score_oportunidade_residual.

   EXCECAO (BLK-MAPA-FAIXAS-01): a camada 5 do funil do piloto NAO segue a rampa —
   ela colore por `faixa_oportunidade` (categorica), porque essa faixa nao e' um
   corte de `score_priorizacao`: o M1 a define cortando `score_percentil_nacional`
   em [35, 50, 65, 80]. Pintar a rampa e rotular com os nomes do M1 afirmaria uma
   correspondencia que nao existe (score 70 nao e' necessariamente "Alta"). Ver o
   bloco FAIXA_M1_ORDEM adiante. As camadas 1/2/3 seguem a rampa normalmente.
   --------------------------------------------------------------------------- */

export type RGBA = [number, number, number, number]

/** RESIDUAL_SCORE_BANDS, na ordem 0-10 .. 90-100. */
export const SCORE_BANDS_HEX = [
  '#941212',
  '#B92323',
  '#DC4141',
  '#DC6914',
  '#F0941E',
  '#EEC828',
  '#96D250',
  '#50C33C',
  '#19A832',
  '#0A8226',
] as const

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ]
}

const BANDS_RGB: [number, number, number][] = SCORE_BANDS_HEX.map(hexToRgb)

/**
 * Alpha do preenchimento dos hexes. O dashboard usa 170; aqui e mais baixo para
 * o basemap (ruas/nomes) respirar por baixo da cor — pedido do Felipe. A rampa
 * de cor (hue) segue identica; muda so a opacidade.
 */
export const HEX_FILL_ALPHA = 115
const CUT_ALPHA = 95

/** Fill de score NaN, igual a utils.score_band_to_color (RGB do dashboard). */
export const NA_FILL: RGBA = [120, 120, 140, 70]
/** Hex descartado pelo corte de <5k hab (components._DISCARDED_FILL, alpha rebaixado). */
export const DISCARDED_FILL: RGBA = [150, 150, 170, CUT_ALPHA]
export const DISCARDED_LINE: RGBA = [170, 170, 190, 160]
/** Hex valido do M1 sem score na camada ativa (components._NAN_SCORE_FILL). */
export const NAN_SCORE_FILL: RGBA = [110, 116, 140, CUT_ALPHA]

/** Regua operacional do dashboard (POP_MIN_ACIONAVEL). */
export const POP_MIN_ACIONAVEL = 5000

/**
 * Porte 1:1 de `score_band_to_color`: mapeia score 0-100 para a faixa de 10 pts.
 * `alpha` default 170, exatamente como o dashboard.
 */
export function scoreBandToColor(
  score: number | null | undefined,
  alpha = 170,
): RGBA {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return [...NA_FILL]
  }
  const idx = Math.min(9, Math.max(0, Math.floor(score / 10)))
  const [r, g, b] = BANDS_RGB[idx]
  return [r, g, b, alpha]
}

/** Só a cor sólida da faixa (para a legenda), sem alpha. */
export function bandSolid(i: number): string {
  return SCORE_BANDS_HEX[i]
}

/* ---------------------------------------------------------------------------
   Faixa de oportunidade do M1 (BLK-MAPA-FAIXAS-01)

   Porte de `constants.FAIXA_COLORS_POR_LABEL`. A camada 5 do funil ("Para onde
   crescer") passa a ser colorida POR ESTA FAIXA, nao pelo score.

   POR QUE: `faixa_oportunidade` NAO e' um corte de `score_priorizacao` — o M1 a
   define cortando `score_percentil_nacional` em [35, 50, 65, 80]
   (`m1/hex_enrichment._definir_faixa_oportunidade`). Como o mapa pintava por
   `score_priorizacao`, rotular aquela rampa com os nomes do M1 afirmaria uma
   correspondencia que nao existe: score 70 nao e' necessariamente "Alta".
   O backend ja manda a faixa pronta em `Hex.faixa`, entao colorir por ela deixa a
   legenda EXATA sem recalcular nada (READ-ONLY sobre o M1).
   --------------------------------------------------------------------------- */

/** Ordem de exibicao na legenda: da maior para a menor prioridade. */
export const FAIXA_M1_ORDEM = [
  'Prioridade máxima',
  'Alta',
  'Média',
  'Baixa',
  'Descartado',
  'Inviável',
] as const

export type FaixaM1 = (typeof FAIXA_M1_ORDEM)[number]

/** `constants.FAIXA_COLORS_POR_LABEL` — chaveado pelo rotulo acentuado que a API envia. */
export const FAIXA_M1_HEX: Record<string, string> = {
  'Prioridade máxima': '#14C850',
  Alta: '#F59E0B',
  Média: '#DC3232',
  Baixa: '#B41E1E',
  Descartado: '#78788C',
  Inviável: '#2E3040',
}

/** Cor de preenchimento do hex pela faixa M1; faixa desconhecida/ausente -> NA_FILL. */
export function faixaM1ToColor(faixa: string | null | undefined, alpha = HEX_FILL_ALPHA): RGBA {
  if (!faixa) return [...NA_FILL]
  const hex = FAIXA_M1_HEX[faixa]
  if (!hex) return [...NA_FILL]
  const [r, g, b] = hexToRgb(hex)
  return [r, g, b, alpha]
}

/* ---------------------------------------------------------------------------
   Passo 4 — taxa de crescimento da area construida do hexagono.

   NAO usa a rampa de score: aqui nao ha nota, ha tres estados. E nao usa amarelo
   — amarelo no meio de uma escala vermelho-verde le como ALERTA, e "estavel" nao
   e alerta (pedido do Juan). Em alta recebe o turquesa da identidade do piloto,
   estavel recebe verde, em queda recebe vermelho.
   --------------------------------------------------------------------------- */

export const CRESC_ALTA_HEX = '#35C9D6'
export const CRESC_ESTAVEL_HEX = '#19A832'
export const CRESC_PARADO_HEX = '#6E7686'

const CRESC_ALTA: RGBA = [53, 201, 214, 150]
const CRESC_ESTAVEL: RGBA = [25, 168, 50, 120]
/* "Sem obra nova" e cinza, nao vermelho. O vermelho fazia o leitor entender que
   os predios foram DERRUBADOS; o que a medida diz e outra coisa — a area
   construida parou de crescer e a variacao ficou ligeiramente negativa, que nessa
   escala e obra encerrada mais ruido de medicao. Ausencia de obra nao e alarme. */
const CRESC_PARADO: RGBA = [110, 118, 134, 110]
/** Sem medicao de satelite (fora das 12 UFs ou fora da mancha urbana). */
const CRESC_SEM: RGBA = [120, 120, 140, 45]

/** Cor por classe de crescimento do hexágono. Categórica, sem ordenação de nota. */
export function crescClasseToColor(classe: string | null | undefined): RGBA {
  if (classe === 'Em alta') return [...CRESC_ALTA]
  if (classe === 'Estável') return [...CRESC_ESTAVEL]
  if (classe === 'Sem obra nova') return [...CRESC_PARADO]
  return [...CRESC_SEM]
}

/* ---------------------------------------------------------------------------
   Identidade das camadas do funil — espelho de --l1..--l5 (styles/tokens.css),
   onde esta o PORQUE da paleta. Aqui fica so' o acesso por numero de passo.

   Por que o RGB aparece de novo: o deck.gl pinta em array [r,g,b,a] e nao le
   variavel CSS, entao a borda do rotulo de rank (HexMap) precisa do numero cru —
   e' a mesma razao de SCORE_BANDS_HEX viver neste arquivo.

   O `rgb` NAO segue o tema, e os `var()` acima seguem. Isso parece divergencia e nao
   e': eles vestem superficies diferentes. Os `var()` pintam DOM (cabecalho do painel,
   bolinha do stepper) sobre o fundo do app, que troca de cor; o `rgb` pinta a borda do
   chip de rank, que pousa no MAPA e e' ESCURO nos dois temas — o chip precisa ser
   escuro porque cobre a rampa inteira, do vermelho ao verde, e e' o fundo dele que
   garante a leitura do numero. Sobre esse chip escuro valem as matizes CLARAS, que sao
   justamente as do `:root`.

   Ao mexer num --lN de tokens.css: se o valor mexido for o do `:root` (escuro), mexa no
   `rgb` do mesmo item aqui. Se for o do bloco [data-tema='claro'], NAO mexa — aquele
   valor nunca chega ao WebGL.
   --------------------------------------------------------------------------- */

export interface CamadaCor {
  /** Texto/numero da camada (var CSS). */
  fg: string
  /** Fundo do bloco do funil (10%). */
  bg: string
  /** Borda do bloco e anel da bolinha do stepper (24%). */
  borda: string
  /** Conector ja percorrido do stepper (60%). */
  conector: string
  /** Mesma matiz de `fg`, para camada WebGL (deck.gl nao le var CSS). */
  rgb: [number, number, number]
}

const CAMADA_CORES: Record<1 | 2 | 3 | 4 | 5, CamadaCor> = {
  1: {
    fg: 'var(--l1)',
    bg: 'var(--l1-a10)',
    borda: 'var(--l1-a24)',
    conector: 'var(--l1-a60)',
    rgb: [111, 164, 247],
  },
  2: {
    fg: 'var(--l2)',
    bg: 'var(--l2-a10)',
    borda: 'var(--l2-a24)',
    conector: 'var(--l2-a60)',
    rgb: [169, 140, 240],
  },
  3: {
    fg: 'var(--l3)',
    bg: 'var(--l3-a10)',
    borda: 'var(--l3-a24)',
    conector: 'var(--l3-a60)',
    rgb: [233, 192, 122],
  },
  // Camada 4 = "Como a cidade esta indo" (crescimento por satelite). Herda o
  // TURQUESA que a propria camada ja' usa no mapa para "Em alta"
  // (`CRESC_ALTA_HEX`), decidido junto com o Juan: dar-lhe outra matiz aqui faria
  // o cabecalho do painel brigar com o hexagono logo ao lado.
  4: {
    fg: 'var(--l4)',
    bg: 'var(--l4-a10)',
    borda: 'var(--l4-a24)',
    conector: 'var(--l4-a60)',
    rgb: [53, 201, 214],
  },
  // Camada 5 = "Para onde crescer", a SINTESE. Fica sem matiz, em claro neutro,
  // pela mesma razao do KPI em destaque do header: as quatro matizes livres ja'
  // estao gastas (azul, violeta, ambar, turquesa) e qualquer uma que sobrasse
  // afirmaria parentesco com a camada que ja' a usa. Ausencia de cor nao afirma
  // parentesco nenhum — e a camada da resposta e' justamente a que resume as outras.
  5: {
    fg: 'var(--l5)',
    bg: 'var(--l5-a10)',
    borda: 'var(--l5-a24)',
    conector: 'var(--l5-a60)',
    rgb: [238, 243, 248],
  },
}

/**
 * Cores da camada `n` (1..5). Numero fora da faixa cai na camada 1 em vez de
 * quebrar: o passo chega do BACKEND, e o funil ja' passou de 4 para 5 camadas uma
 * vez — a cor e' decoracao, o conteudo e' que importa.
 */
export function camadaCor(n: number): CamadaCor {
  return CAMADA_CORES[n as 1 | 2 | 3 | 4 | 5] ?? CAMADA_CORES[1]
}

/* --- PROTOTIPO: pressao por numero de concorrentes no disco de 1 km -----------
   Quantas concorrentes ALCANCAM o hexagono, nao quantas estao "dentro" dele. A
   leitura pedida pelo Felipe: uma concorrente ja tinge a area em que ela atua; a
   segunda cinza mais; da terceira em diante o hexagono vai apagando ate virar
   chumbo — disputa alta, pouco espaco.

   A rampa e DIVERGENTE de proposito (verde -> ambar -> vermelho -> cinza), nao um
   gradiente de uma cor so: o operador precisa distinguir "ninguem" de "um" num
   relance, e duas amostras da mesma matiz com alpha diferente nao resolvem isso
   sobre um basemap escuro.

   `0` NAO entra aqui: hexagono sem concorrente mantem a cor da propria camada
   (residual/score), senao o mapa perderia a leitura que ja tinha. */
/* Indexado a partir de 1 concorrente. O zero NAO tem entrada: hexagono sem
   concorrente mantem a cor da propria camada, e dar uma cor a ele aqui faria a
   legenda prometer um pintado que o mapa nao faz. */
export const CONC_1KM_HEX = ['#F2C230', '#E8663C', '#B9455A', '#6E7686']

export const CONC_1KM_ROTULOS = [
  '1 concorrente',
  '2 concorrentes',
  '3 concorrentes',
  '4 ou mais',
]

/* --- Cor pelo CONSUMO rateado (alunos que o hexagono perde) -----------------
   A rampa por CONTAGEM de concorrentes nao mostrava o que o modelo faz: dois
   hexagonos com "1 concorrente" ficavam iguais mesmo quando um perdia 2.400 alunos
   (concorrente no meio dele) e o outro 100 (so' a beirada do disco encostou). O
   rateio por area SO' fica visivel quando a cor responde ao VALOR.

   Faixas em alunos, ancoradas na capacidade de 2.500 de uma unidade: ate 1/4 de
   unidade, ate 1/2, ate 1, ate 2, acima disso. */
export const CONSUMO_1KM_CORTES = [625, 1250, 2500, 5000]

export const CONSUMO_1KM_HEX = ['#F2C230', '#E8663C', '#B9455A', '#8A3550', '#6E7686']

export const CONSUMO_1KM_ROTULOS = [
  'até 625 alunos',
  '625 a 1.250',
  '1.250 a 2.500',
  '2.500 a 5.000',
  'acima de 5.000',
]

/** Cor do hexagono pelo numero de ALUNOS que ele perde para concorrentes no rateio de
 *  1 km. `<= 0` devolve `null` — o chamador mantem a cor da camada. */
export function consumo1kmToColor(
  alunos: number | null | undefined,
  alpha = HEX_FILL_ALPHA,
): RGBA | null {
  if (alunos == null || alunos <= 0) return null
  let i = CONSUMO_1KM_CORTES.length
  for (let k = 0; k < CONSUMO_1KM_CORTES.length; k++) {
    if (alunos <= CONSUMO_1KM_CORTES[k]) {
      i = k
      break
    }
  }
  const hex = CONSUMO_1KM_HEX[i]
  return [
    parseInt(hex.slice(1, 3), 16),
    parseInt(hex.slice(3, 5), 16),
    parseInt(hex.slice(5, 7), 16),
    alpha,
  ]
}

/** Cor do hexagono pelo numero de concorrentes que o alcancam (disco de 1 km).
 *  `n <= 0` devolve `null` — o chamador mantem a cor da camada. */
export function conc1kmToColor(
  n: number | null | undefined,
  alpha = HEX_FILL_ALPHA,
): RGBA | null {
  if (n == null || n <= 0) return null
  const i = Math.min(n - 1, CONC_1KM_HEX.length - 1)
  const hex = CONC_1KM_HEX[i]
  return [
    parseInt(hex.slice(1, 3), 16),
    parseInt(hex.slice(3, 5), 16),
    parseInt(hex.slice(5, 7), 16),
    alpha,
  ]
}
