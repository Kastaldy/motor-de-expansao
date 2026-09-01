/**
 * De que BASE o app está falando — disponível em qualquer ponto da árvore.
 *
 * POR QUE CONTEXTO, E NÃO PROP. O país da base é um fato GLOBAL da instância: o mesmo
 * binário serve Brasil e Argentina, e o que muda é o `MOTOR_DATA_DIR`. Quem precisa dele
 * são folhas espalhadas — a ficha do hexágono, o detalhe do raio, o rodapé de procedência,
 * o título da tela vazia. Levar `ufs` de prop em prop até `FichaHex` atravessaria três
 * componentes que não têm nada a ver com o assunto, e a próxima folha a precisar pagaria
 * o pedágio de novo.
 *
 * O QUE VIAJA É A LISTA DE UFs, e não o país já resolvido, porque as duas perguntas saem
 * dela: quantas unidades a base tem (a contagem do rodapé) e qual é o país
 * (`paisDaBase`). Guardar só o país obrigaria um segundo canal para a contagem.
 *
 * O DEFAULT É LISTA VAZIA, e isso é deliberado: sem base carregada os helpers de
 * `rodape-base` devolvem `null`/termo neutro, e a tela não afirma nada. Um componente
 * usado fora do provider (num teste, numa história isolada) degrada para "não sei" em vez
 * de estourar.
 */

import { createContext, useContext, type ReactNode } from 'react'

const UfsDaBase = createContext<readonly string[]>([])

export function BaseProvider({
  ufs,
  children,
}: {
  ufs: readonly string[]
  children: ReactNode
}) {
  return <UfsDaBase.Provider value={ufs}>{children}</UfsDaBase.Provider>
}

/** As UFs da base servida. `[]` quando ainda não carregou (ou fora do provider). */
export function useUfsDaBase(): readonly string[] {
  return useContext(UfsDaBase)
}
