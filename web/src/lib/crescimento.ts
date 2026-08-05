/* ---------------------------------------------------------------------------
   Contrato dos campos codificados do passo 4 (BLK-TRAJ-01).

   `cres_dims` e `cres_series` viajam como UMA string cada, e nao como JSON aninhado,
   para nao abrir dez colunas novas no contrato da API pela mesma informacao. O preco
   e este parser — que estava dentro do `NarrativePanel` e por isso nao tinha teste
   nenhum, apesar de ser a unica coisa entre o payload e o grafico na tela.

   Formatos (produzidos por `data/reports/crescimento/06_encode_dims.py` e `07_series.py`):

     dims   nome:valor:unidade:posicao:periodo         blocos unidos por ';'
     series nome|unidade|rotulo_ini|rotulo_fim|v1,v2,…  blocos unidos por ';'

   NENHUM valor pode conter `:`, `|` ou `;` — verificado em 26.129 blocos de dims e
   26.140 de series. Os separadores `→` e `–` dos periodos sao seguros.

   Os dois filtram silenciosamente o bloco malformado em vez de estourar: a alternativa
   e a tela inteira do passo 4 morrer porque um municipio veio com um campo torto.
   --------------------------------------------------------------------------- */

/** Uma serie temporal de uma dimensao — o que o grafico desenha. */
export interface Serie {
  nome: string
  unidade: string
  ini: string
  fim: string
  valores: number[]
}

/** Uma dimensao: o numero, sua unidade e a posicao nacional que lhe da escala. */
export interface Linha {
  nome: string
  valor: number
  unidade: string
  pos: number
  periodo: string
}

/** `periodo` e opcional (chegou depois, no `10_periodo.py`), dai o `length >= 4`. */
export function parseDims(s: string): Linha[] {
  return s
    .split(';')
    .map((p) => p.split(':'))
    .filter((p) => p.length >= 4)
    .map(([nome, valor, unidade, pos, periodo]) => ({
      nome,
      valor: Number(valor),
      unidade,
      pos: Number(pos),
      periodo: periodo ?? '',
    }))
    .filter((l) => Number.isFinite(l.valor) && Number.isFinite(l.pos))
}

/** Exige os 5 campos e ao menos 3 pontos: com menos que isso nao ha linha a desenhar. */
export function parseSeries(s: string): Serie[] {
  return s
    .split(';')
    .map((bloco) => bloco.split('|'))
    .filter((p) => p.length === 5)
    .map(([nome, unidade, ini, fim, vs]) => ({
      nome,
      unidade,
      ini,
      fim,
      valores: vs.split(',').map(Number).filter(Number.isFinite),
    }))
    .filter((s) => s.valores.length >= 3)
}
