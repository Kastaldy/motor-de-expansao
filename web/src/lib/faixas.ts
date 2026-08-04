/* ---------------------------------------------------------------------------
   Faixas NOMEADAS por camada do funil (BLK-MAPA-FAIXAS-01)

   Ate aqui a legenda do mapa era uma barra 0->100 sem nome: o usuario via a cor
   mas nao sabia se "62" era bom. Cada camada ganha nomes proprios porque o EIXO
   de cada uma e' diferente — o mesmo "alto" nao quer dizer a mesma coisa em
   potencial socioeconomico e em demanda nao atendida.

   ESPELHO, NAO FONTE. A definicao canonica vive em
   `src/motor_expansao/dashboard/constants.py` (`FAIXAS_MAPA_POTENCIAL` /
   `FAIXAS_MAPA_DEMANDA`), porque o BACKEND tambem precisa dela: a etiqueta de cada
   item do ranking (`_etiqueta` em web/server/app.py) sai da MESMA regua que esta
   legenda. Se as duas divergirem, a mesma regiao aparece com dois nomes na tela —
   foi o defeito medido em 2026-08-03. `tests/contracts/test_faixas_mapa_espelho.py`
   quebra se este arquivo sair de sincronia com o Python.

   READ-ONLY sobre o M1: isto e' camada de EXIBICAO. Nenhum corte aqui redefine
   score, faixa_oportunidade ou qualquer artefato — sao rotulos sobre a rampa de
   cor que ja existia (`SCORE_BANDS_HEX`, faixas de 10 pontos).

   Camada 3 (Pressao concorrencial) NAO esta aqui de proposito: ela pinta pelo
   MESMO `score_oportunidade_residual` da camada 2 (a concorrencia entra so no
   filtro de quais hexes acendem, nao na cor), entao herda os nomes da 2 ate a
   mudanca de comportamento que o Juan ja encaminhou por outro caminho.
   --------------------------------------------------------------------------- */

import { num } from './format'

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
   VEREDITO sobre a regiao, nao medida abstrata: o mapa e' lido por quem decide
   abertura, e "Promissor" resolve na hora o que "62 pontos" nao resolve. */
export const FAIXAS_POTENCIAL: FaixaNomeada[] = [
  { de: 0, ate: 20, nome: 'Desfavorável', cor: '#B92323' },
  { de: 20, ate: 40, nome: 'Fraco', cor: '#DC6914' },
  { de: 40, ate: 60, nome: 'Promissor', cor: '#EEC828' },
  { de: 60, ate: 80, nome: 'Forte', cor: '#50C33C' },
  { de: 80, ate: 100, nome: 'Excelente', cor: '#0A8226' },
]

/* Camada 2 — Demanda nao atendida (score_oportunidade_residual).
   Aqui o score NAO e' abstrato: `calcular_colunas_mercado` define
   `score_oportunidade_residual = 100 * oferta_efetiva_disponivel / 2.500`,
   e 2.500 alunos e' a capacidade de UMA unidade. Entao 100 = uma unidade cheia,
   50 = meia. Nomear em temperatura jogaria fora essa leitura, que e' a mais util
   para quem decide abertura. Os alunos de cada faixa vao no `sub` da legenda.

   O vocabulario e' de SATURACAO (quanto o mercado local ja esta tomado), escolhido
   pelo Juan em 2026-08-03, em registro FORMAL — saiu a primeira versao coloquial
   ("Respirando"/"Folgado"). A escala anda junto com a cor: score 0 = vermelho =
   "Saturado" (nao sobra nada) e score 100 = verde = "Livre" (cabe uma unidade
   inteira). A leitura em alunos vai no `sub` de cada bloco e preserva a ancora.

   RESSALVA REGISTRADA (Claude -> Juan, 2026-08-03): "Saturado" sugere que a
   demanda foi CONSUMIDA por concorrentes, mas residual baixo tem duas causas —
   (a) muita oferta instalada (saturacao de verdade) e (b) SAM baixo, ou seja
   pouca gente/renda para comecar. No caso (b) o hex nao esta saturado, esta
   VAZIO, e o rotulo sugere a causa errada. Como o score sozinho nao distingue as
   duas, o texto foi mantido a pedido; se um dia incomodar, separar exige cruzar
   com `oferta_consumida_mercado_estimada` — dado que ja chega no payload.

   ATENCAO: o score e' CLIPADO em 100 (`.clip(upper=100)`), entao um hex com
   10.000 alunos residuais marca o mesmo 100 que um com 2.500. Por isso a ultima
   faixa e' "Livre" e nao promete "mais de uma unidade" — o dado nao distingue. */
export const FAIXAS_DEMANDA: FaixaNomeada[] = [
  { de: 0, ate: 20, nome: 'Saturado', cor: '#B92323' },
  { de: 20, ate: 40, nome: 'Restrito', cor: '#DC6914' },
  { de: 40, ate: 60, nome: 'Moderado', cor: '#EEC828' },
  { de: 60, ate: 80, nome: 'Amplo', cor: '#50C33C' },
  { de: 80, ate: 100, nome: 'Livre', cor: '#0A8226' },
]

/** Alunos equivalentes de um score residual (a ancora dos 2.500). */
export const CAPACIDADE_UNIDADE_ALUNOS = 2500

/**
 * Etiqueta de alunos sob o nome da faixa: "1.000–1.500".
 *
 * Passa pelo `num()` para herdar o separador de milhar pt-BR do resto do app — a
 * primeira versao escrevia "1000-1500" cru, destoando de todo numero da tela. A
 * UNIDADE nao entra aqui: repetir "alunos" em cinco blocos de uma legenda de
 * 8,5px so gasta largura, entao ela vai UMA vez no titulo (`tituloDaLegenda`).
 * A ultima faixa e' aberta (`2.000+`) porque o score satura em 100 — ver a
 * ressalva do bloco `FAIXAS_DEMANDA`.
 */
export function alunosDaFaixa(f: FaixaNomeada): string {
  const de = num(Math.round((f.de / 100) * CAPACIDADE_UNIDADE_ALUNOS))
  const ate = num(Math.round((f.ate / 100) * CAPACIDADE_UNIDADE_ALUNOS))
  return f.ate >= 100 ? `${de}+` : `${de}–${ate}`
}

/** Faixas nomeadas da camada, ou `null` quando a camada nao usa rampa de score
 *  (camada 4 colore pela faixa do M1 — ver `FAIXA_M1_ORDEM` em `colors.ts`). */
export function faixasDoPasso(passoN: number): FaixaNomeada[] | null {
  if (passoN === 1) return FAIXAS_POTENCIAL
  if (passoN === 2 || passoN === 3) return FAIXAS_DEMANDA
  return null
}

/** Titulo da legenda por camada. A unidade das camadas 2/3 vive AQUI, e nao
 *  repetida em cada etiqueta (ver `alunosDaFaixa`). */
export function tituloDaLegenda(passoN: number): string {
  if (passoN === 1) return 'Potencial socioeconômico'
  if (passoN === 2 || passoN === 3) return 'Demanda não atendida (alunos)'
  return 'Faixa de oportunidade M1'
}
