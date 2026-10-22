/**
 * A VIAGEM da unidade ate' o territorio dela (`MapScreen.abrirUnidade`, pedido do Vinicius
 * de 21/10/2026): escolher uma unidade troca UF/municipio pelos mesmos `onUf`/`onMunicipio`
 * do cabecalho. Quando a lista de municipios da UF dela ainda nao esta' em maos, a troca
 * espera uma resposta do servidor -- e, numa UF fria, essa espera e' longa.
 *
 * Esta maquina e' o que decide se a resposta, ao chegar, AINDA vale. Regra: so' vale se,
 * desde a escolha, o operador nao fez nada que mude para onde ele esta' olhando. Qualquer
 * gesto (outra unidade, clique num hexagono, ponto da comparacao, imovel, busca, cenario,
 * destino de lista, troca manual de territorio, fechar a ficha) e a DESMONTAGEM do mapa
 * cancelam -- senao a resposta atrasada mudaria de cidade por baixo do gesto novo, ou
 * mudaria o territorio do App com o operador ja' em outra tela (revisao de 21/10/2026).
 *
 * Duas fases:
 * - `iniciar()` .. `embarcar()`: a escolha esta' viva enquanto `vale(seq)`.
 * - `embarcar()` .. `chegar()`: a troca foi PEDIDA ao App; o efeito de contexto do mapa
 *   chama `chegar(contexto)` e, se o contexto novo e' o que a unidade pediu, recebe a carga
 *   (a ficha da unidade, que entao NAO e' fechada). Qualquer outro contexto cancela.
 *
 * Pura e sem React, para ser testada por comportamento (o Vitest roda sem DOM).
 */
export interface ViagemUnidade<T> {
  /** Uma escolha nova: invalida a anterior (e a carga dela) e devolve o numero desta. */
  iniciar(): number
  /** A escolha `seq` ainda e' a vigente? */
  vale(seq: number): boolean
  /** Marca a troca de territorio pedida pela escolha `seq`. `false` se ela ja' caducou. */
  embarcar(seq: number, chave: string, carga: T): boolean
  /** Um gesto do operador, ou a desmontagem: nada pendente vale mais. */
  cancelar(): void
  /**
   * O contexto do mapa mudou para `contexto`. Devolve a carga se foi a viagem que causou
   * a troca; senao cancela o que estiver pendente e devolve `null`.
   */
  chegar(contexto: string): T | null
}

export function criarViagemUnidade<T>(): ViagemUnidade<T> {
  let seq = 0
  let transito: { chave: string; carga: T } | null = null
  return {
    iniciar() {
      transito = null
      return ++seq
    },
    vale(s) {
      return s === seq
    },
    embarcar(s, chave, carga) {
      if (s !== seq) return false
      transito = { chave, carga }
      return true
    },
    cancelar() {
      seq++
      transito = null
    },
    chegar(contexto) {
      const t = transito
      transito = null
      if (t && t.chave === contexto) return t.carga
      seq++
      return null
    },
  }
}
