/* ---------------------------------------------------------------------------
   Faixas NOMEADAS por camada do funil (BLK-MAPA-FAIXAS-01)

   Ate aqui a legenda do mapa era uma barra 0->100 sem nome: o usuario via a cor
   mas nao sabia se "62" era bom. Cada camada ganha nomes proprios porque o EIXO
   de cada uma e' diferente — o mesmo "alto" nao quer dizer a mesma coisa em
   potencial socioeconomico e em demanda nao atendida.

   READ-ONLY sobre o M1: isto e' camada de EXIBICAO. Nenhum corte aqui redefine
   score, faixa_oportunidade ou qualquer artefato — sao rotulos sobre a rampa de
   cor que ja existia (`SCORE_BANDS_HEX`, faixas de 10 pontos).

   Camada 3 (Pressao concorrencial) NAO esta aqui de proposito: ela pinta pelo
   MESMO `score_oportunidade_residual` da camada 2 (a concorrencia entra so no
   filtro de quais hexes acendem, nao na cor), entao herda os nomes da 2 ate a
   mudanca de comportamento que o Juan ja encaminhou por outro caminho.
   --------------------------------------------------------------------------- */

export interface FaixaNomeada {
  /** Limite inferior do score, inclusivo. */
  de: number
  /** Limite superior do score, exclusivo (o ultimo bloco fecha em 100). */
  ate: number
  nome: string
  /** Cor solida da faixa, tirada do meio do intervalo na rampa de 10 pontos. */
  cor: string
}

/* Camada 1 — Potencial socioeconomico (score_setor_2022_calibrado).
   Vocabulario de TEMPERATURA porque o app ja chama esses hexes de "quentes" na
   narrativa do passo 1 ("o censo 2022 acende N hexagonos quentes"). */
export const FAIXAS_POTENCIAL: FaixaNomeada[] = [
  { de: 0, ate: 20, nome: 'Frio', cor: '#B92323' },
  { de: 20, ate: 40, nome: 'Morno', cor: '#DC6914' },
  { de: 40, ate: 60, nome: 'Aquecido', cor: '#EEC828' },
  { de: 60, ate: 80, nome: 'Quente', cor: '#50C33C' },
  { de: 80, ate: 100, nome: 'Muito quente', cor: '#0A8226' },
]

/* Camada 2 — Demanda nao atendida (score_oportunidade_residual).
   Aqui o score NAO e' abstrato: `calcular_colunas_mercado` define
   `score_oportunidade_residual = 100 * oferta_efetiva_disponivel / 2.500`,
   e 2.500 alunos e' a capacidade de UMA unidade. Entao 100 = uma unidade cheia,
   50 = meia. Nomear em temperatura jogaria fora essa leitura, que e' a mais util
   para quem decide abertura. Os alunos de cada faixa vao no `sub` da legenda.

   ATENCAO: o score e' CLIPADO em 100 (`.clip(upper=100)`), entao um hex com
   10.000 alunos residuais marca o mesmo 100 que um com 2.500. Por isso a ultima
   faixa e' "Unidade cheia" e NAO "Mais de uma" — o dado nao distingue. */
export const FAIXAS_DEMANDA: FaixaNomeada[] = [
  { de: 0, ate: 20, nome: 'Marginal', cor: '#B92323' },
  { de: 20, ate: 40, nome: 'Pouco espaço', cor: '#DC6914' },
  { de: 40, ate: 60, nome: 'Meia unidade', cor: '#EEC828' },
  { de: 60, ate: 80, nome: 'Quase cheia', cor: '#50C33C' },
  { de: 80, ate: 100, nome: 'Unidade cheia', cor: '#0A8226' },
]

/** Alunos equivalentes de um score residual (a ancora dos 2.500). */
export const CAPACIDADE_UNIDADE_ALUNOS = 2500

export function alunosDaFaixa(f: FaixaNomeada): string {
  const de = Math.round((f.de / 100) * CAPACIDADE_UNIDADE_ALUNOS)
  const ate = Math.round((f.ate / 100) * CAPACIDADE_UNIDADE_ALUNOS)
  return f.ate >= 100 ? `${de}+ alunos` : `${de}–${ate}`
}

/** Faixas nomeadas da camada, ou `null` quando a camada nao usa rampa de score
 *  (camada 4 colore pela faixa do M1 — ver `FAIXA_M1_ORDEM` em `colors.ts`). */
export function faixasDoPasso(passoN: number): FaixaNomeada[] | null {
  if (passoN === 1) return FAIXAS_POTENCIAL
  if (passoN === 2 || passoN === 3) return FAIXAS_DEMANDA
  return null
}

/** Titulo da legenda por camada. */
export function tituloDaLegenda(passoN: number): string {
  if (passoN === 1) return 'Potencial socioeconômico'
  if (passoN === 2 || passoN === 3) return 'Demanda não atendida'
  return 'Faixa de oportunidade M1'
}
