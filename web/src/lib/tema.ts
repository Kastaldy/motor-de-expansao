/**
 * Tema visual da Visão Executiva — o valor, a persistência e nada mais.
 *
 * A aba nasceu só no escuro, e o escuro continua sendo o padrão do produto inteiro. O
 * claro existe porque a Executiva é a única tela que sai do monitor: ela é projetada em
 * reunião e impressa em PDF, e num projetor o fundo escuro come o contraste que os
 * gráficos precisam ter. Por isso o atributo `data-tema` vive no CONTAINER da tela, e
 * não no `<html>`: o Mapa Territorial e a Viabilidade não pediram tema claro e não vão
 * ganhar um por tabela (ver o bloco `[data-tema='claro']` em `styles/tokens.css`).
 *
 * Nada aqui toca React nem lê `window` por conta própria — o depósito entra por
 * parâmetro. É o mesmo motivo de `lib/periodo.ts` não ler o relógio: função que alcança
 * o ambiente sozinha não tem teste determinístico.
 */

export type Tema = 'escuro' | 'claro'

/** O tema do produto. Quem nunca escolheu nada entra por aqui. */
export const TEMA_PADRAO: Tema = 'escuro'

/** Chave no `localStorage`. Namespaced: o domínio é compartilhado com outras telas. */
export const CHAVE_TEMA = 'motor.exec.tema'

/** Subconjunto do `Storage` que este módulo usa — o bastante para um duble em teste. */
export interface DepositoDeTema {
  getItem(chave: string): string | null
  setItem(chave: string, valor: string): void
}

export function ehTema(valor: unknown): valor is Tema {
  return valor === 'escuro' || valor === 'claro'
}

/** O outro tema. Existe para o botão não repetir a condicional em cada lugar. */
export function outroTema(tema: Tema): Tema {
  return tema === 'claro' ? 'escuro' : 'claro'
}

/**
 * Tema guardado, ou o padrão.
 *
 * Valor irreconhecível cai no padrão em vez de virar `data-tema="lixo"`: o seletor não
 * casaria, a tela ficaria escura, e o botão passaria a alternar a partir de um estado
 * que ninguém escolheu. Depósito ausente ou que ESTOURA também cai no padrão — em janela
 * anônima e com cookies de terceiros bloqueados, o simples acesso a `localStorage`
 * levanta `SecurityError`, e perder a preferência é aceitável; derrubar a aba não é.
 */
export function lerTema(deposito: DepositoDeTema | null | undefined): Tema {
  try {
    const bruto = deposito?.getItem(CHAVE_TEMA)
    return ehTema(bruto) ? bruto : TEMA_PADRAO
  } catch {
    return TEMA_PADRAO
  }
}

/** Guarda a escolha. Falha em silêncio: preferência de tema não vale uma tela quebrada. */
export function gravarTema(tema: Tema, deposito: DepositoDeTema | null | undefined): void {
  try {
    deposito?.setItem(CHAVE_TEMA, tema)
  } catch {
    /* sem persistência; a sessão corrente continua no tema escolhido */
  }
}

/** O `localStorage`, quando existe. Fora do navegador (SSR, teste) devolve `null`. */
export function depositoDoNavegador(): DepositoDeTema | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage
  } catch {
    return null
  }
}
