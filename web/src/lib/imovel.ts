import { brl, brlCurto } from './format'
import type { Oportunidade } from './types'
import { AVISO_EXTRAPOLACAO_V2 } from './viabilidade-demanda-v2'

/* ---------------------------------------------------------------------------
   Identidade visual e derivacoes da camada IMOBILIARIA (oferta de imoveis).

   Extraido de `screens/OportunidadesImobiliariasScreen.tsx` quando a camada
   passou a aparecer TAMBEM no Mapa Territorial (pontinhos + secao da ficha do
   hexagono + janela de detalhe): duas copias de paleta/label/custo divergiriam
   no primeiro ajuste, e a cor do tipo e' exatamente o que liga as duas telas.
   --------------------------------------------------------------------------- */

/* --- Paleta CATEGORICA por tipo (identidade do imovel) -----------------------
   Matizes originais do design (rosa/peri/laranja). Valores HEX (telas so'-escuras;
   SVG fill e alpha-composicao nao resolvem var() em atributo). Cada uso categorico
   carrega ROTULO/ICONE junto; a cor de SCORE segue a rampa canonica, nao o tipo. */
export const COR_TIPO: Record<string, string> = {
  galpao: '#f2597f',
  comercial: '#7b9cf0',
  loja: '#7b9cf0',
  terreno: '#f2913a',
}
export const COR_TIPO_FALLBACK = '#8b97a5'
export const corTipo = (t: string): string => COR_TIPO[t] ?? COR_TIPO_FALLBACK

/** A mesma cor do tipo, em RGB 0-255 — o deck.gl nao le hex CSS em accessor. */
export function corTipoRgb(t: string): [number, number, number] {
  const hex = corTipo(t)
  return [
    parseInt(hex.slice(1, 3), 16),
    parseInt(hex.slice(3, 5), 16),
    parseInt(hex.slice(5, 7), 16),
  ]
}

/** Rotulo de EXIBICAO do tipo (CLAUDE.md §2: valor bruto de enum nunca vai a tela). */
export const LABEL_TIPO: Record<string, string> = {
  galpao: 'Galpão',
  comercial: 'Comercial',
  loja: 'Loja',
  terreno: 'Terreno',
}
export const labelTipo = (t: string): string => {
  if (!t) return 'Imóvel'
  /* "Imovel" e' o DEFAULT BRUTO do backend (app.py) para tipo ausente — sem o desvio,
     o capitalize genérico o deixava passar sem acento para a tela. */
  if (t.toLowerCase() === 'imovel') return 'Imóvel'
  return LABEL_TIPO[t] ?? t.charAt(0).toUpperCase() + t.slice(1)
}

/** Rotulo de EXIBICAO da faixa M1 do payload de oportunidades (valores CRUS como
 *  `prioridade_maxima` — dominio diferente do `Hex.faixa` do mapa, que ja chega
 *  com o nome de exibicao). Fallback capitaliza em vez de vazar o underscore. */
export const FAIXA_LABEL: Record<string, string> = {
  prioridade_maxima: 'Prioridade máxima',
  alta: 'Alta',
  media: 'Média',
  baixa: 'Baixa',
  minima: 'Mínima',
}
export const labelFaixa = (v: string | null): string | null =>
  v == null ? null : (FAIXA_LABEL[v] ?? v.charAt(0).toUpperCase() + v.slice(1))

/** Custo de ocupacao mensal = aluguel + IPTU + condominio (0 quando ausente). */
export const custoOcup = (o: Oportunidade): number =>
  [o.aluguel, o.iptu, o.condominio].reduce<number>((s, v) => s + (v ?? 0), 0)

/** R$/m² de aluguel: o do backend quando veio, senao derivado de aluguel/area. */
export const rsM2 = (o: Oportunidade): number | null =>
  o.rs_m2 != null ? o.rs_m2 : o.aluguel != null && o.area ? o.aluguel / o.area : null

/* --- Regua PUBLICADA do modelo de viabilidade: aluguel como % do faturamento --
   Os clusters sao os MESMOS do simulador (tela de Viabilidade / `aluguel_teto`
   do backend): ideal 15%, teto 20%, excecao 30%. E' a unica regua aprovada que
   compara custo com retorno — nada de limiar inventado (o design de referencia
   trazia "18%", que nao existe no modelo). Rotulos/tons espelham a classificacao
   da tela de Viabilidade (`tetoCls`), para as duas superficies falarem igual. */
export const ALUGUEL_PCT_IDEAL = 15
export const ALUGUEL_PCT_TETO = 20
export const ALUGUEL_PCT_EXCECAO = 30

/* --- Projecao de faturamento: o MODELO DE PRACA do simulador, ou nenhuma -----
   DEC-086. O backend serve o p50 pronto em `fat_proj` e diz a fonte em
   `fat_fonte`: "praca" quando o lote noturno tem as entradas da isocrona do
   imovel (o mesmo modelo da Viabilidade, com a faixa p10-p90); "sem_projecao"
   quando o modelo nao estima o ponto (emenda 1, abaixo); "densidade" so' com o
   modelo desligado no servidor (a curva de alunos por m2 de antes, com os textos
   de antes). O padrao de exibicao e' o do simulador: o p50 e' o numero, a faixa
   vai na nota com o MESMO rotulo ("Faixa do modelo"), e o aviso de extrapolacao
   e' o MESMO texto. Nada aqui recalcula: so' escolhe o texto pela fonte. */

/** O faturamento projetado deste imóvel veio do modelo de praça? */
export const projecaoPeloModelo = (o: Oportunidade): boolean => o.fat_fonte === 'praca'

/* --- Sem projeção (emenda 1 da DEC-086) --------------------------------------
   "Não podemos projetar faturamento em um ponto que não conseguimos estimar"
   (Felipe, 17/11/2026). Fora do domínio do modelo (isócrona presa numa via interna,
   zona morta), sem cálculo ou ainda não calculado, o imóvel fica SEM número: nem o
   do modelo, nem o da curva de densidade. A frase vem pronta do servidor (ela cita
   os limiares, que vivem lá); a tabela abaixo é só a reserva, por motivo. */

/** O modelo não estima este imóvel: sem faturamento e sem alunos. */
export const semProjecao = (o: Oportunidade): boolean => o.fat_fonte === 'sem_projecao'

const TEXTO_SEM_PROJECAO: Record<string, string> = {
  area_pequena:
    'Sem projeção: a área de 10 min de carro não pôde ser medida a partir do imóvel (ele fica numa via interna, como de condomínio ou área industrial).',
  zona_morta: 'Sem projeção: zona morta (poucos moradores em volta).',
  sem_area: 'Sem projeção: o anúncio não traz a área.',
  aguardando: 'Sem projeção ainda: o cálculo deste imóvel roda na próxima madrugada.',
  sem_calculo: 'Sem projeção: o modelo de praça não pôde ser calculado para este ponto.',
}

/** A frase do motivo de o imóvel estar sem projeção, ou null quando ele tem número. */
export function textoSemProjecao(o: Oportunidade): string | null {
  if (!semProjecao(o)) return null
  return o.fat_motivo_texto ?? TEXTO_SEM_PROJECAO[o.fat_motivo ?? ''] ?? TEXTO_SEM_PROJECAO.sem_calculo
}

/** "Faixa do modelo: R$ 180 mil–R$ 430 mil" (como o simulador), ou null fora do modelo. */
export function faixaDoModelo(o: Oportunidade): string | null {
  if (!projecaoPeloModelo(o) || o.fat_p10 == null || o.fat_p90 == null) return null
  return `Faixa do modelo: ${brl(o.fat_p10, true)}–${brl(o.fat_p90, true)}`
}

/** Faixa curta para a nota de "Projeção fat." do card lateral da vista Mapa
 *  ("R$ 180k–430k"), ou null fora do modelo. */
export function faixaDoModeloCurta(o: Oportunidade): string | null {
  if (!projecaoPeloModelo(o) || o.fat_p10 == null || o.fat_p90 == null) return null
  return `${brlCurto(o.fat_p10)}–${brlCurto(o.fat_p90).replace(/^\S+\s/, '')}`
}

/** O MESMO aviso do simulador (`avisosV2`) quando o ponto sai do intervalo do ajuste. */
export const avisoDaProjecao = (o: Oportunidade): string | null =>
  projecaoPeloModelo(o) && o.fat_extrapolacao ? AVISO_EXTRAPOLACAO_V2 : null

/** O teto do modelo cortou a metragem do anúncio (DEC-086)? Lê o booleano do MODELO, e não
 *  `m2_modelo < area`: comparar números arredondados de lados diferentes dava falso corte. */
export const modeloCortouAArea = (o: Oportunidade): boolean =>
  projecaoPeloModelo(o) && o.teto_m2_aplicado === true && o.m2_modelo != null

/** % do faturamento projetado que o ALUGUEL toma; null sem as duas pontas. */
export const pctAluguelFat = (o: Oportunidade): number | null =>
  o.aluguel != null && o.fat_proj != null && o.fat_proj > 0
    ? (o.aluguel / o.fat_proj) * 100
    : null

/** Classificacao do % na regua 15/20/30 — mesmos rotulos/tons da Viabilidade. */
export function classeAluguelFat(pct: number | null): { rotulo: string; tom: string } | null {
  if (pct == null || Number.isNaN(pct)) return null
  if (pct <= ALUGUEL_PCT_IDEAL) return { rotulo: 'dentro do ideal', tom: 'var(--pos-text)' }
  if (pct <= ALUGUEL_PCT_TETO) return { rotulo: 'no teto', tom: 'var(--warn-text)' }
  if (pct <= ALUGUEL_PCT_EXCECAO) return { rotulo: 'exceção', tom: 'var(--warn-text)' }
  return { rotulo: 'acima do máximo', tom: 'var(--neg)' }
}

/* --- Acento da camada imobiliaria = ROSA MAGENTA (pedido do Felipe) ----------
   Colore selecao/realces e o botao de acao da camada, na aba e no mapa. Hex
   direto pelo mesmo motivo da paleta acima. */
export const ACC = '#dd3d97'
export const ACC_TX = '#f06fb6'
export const ACC_08 = 'rgba(221,61,151,.08)'
export const ACC_10 = 'rgba(221,61,151,.10)'
export const ACC_12 = 'rgba(221,61,151,.12)'
export const ACC_24 = 'rgba(221,61,151,.24)'
export const ACC_30 = 'rgba(221,61,151,.30)'
export const ACC_50 = 'rgba(221,61,151,.50)'
export const ACC_GLOW = '0 6px 16px -4px rgba(221,61,151,.45)'
export const ACC_ON = '#2a0714' // texto escuro sobre o magenta (botao primario)
