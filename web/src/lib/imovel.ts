import type { Oportunidade } from './types'

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
   Os clusters sao os MESMOS do simulador (`BlocoViabilidadePonto` / `aluguel_teto`
   do backend): ideal 15%, teto 20%, excecao 30%. E' a unica regua aprovada que
   compara custo com retorno — nada de limiar inventado (o design de referencia
   trazia "18%", que nao existe no modelo). Rotulos/tons espelham a classificacao
   da tela de Viabilidade (`tetoCls`), para as duas superficies falarem igual. */
export const ALUGUEL_PCT_IDEAL = 15
export const ALUGUEL_PCT_TETO = 20
export const ALUGUEL_PCT_EXCECAO = 30

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
