/**
 * Tema visual do app — o valor, a persistência e nada mais.
 *
 * O claro nasceu na Visão Executiva, a única tela que sai do monitor: ela é projetada
 * em reunião e impressa em PDF, e num projetor o fundo escuro come o contraste que os
 * gráficos precisam ter. Por isso o `data-tema` morava no CONTAINER daquela aba.
 *
 * Desde 2026-08-25 ele vive no `<html>` e vale para as cinco telas (pedido do Juan). O
 * motivo de subir é o mesmo que fez o claro existir, agora dito para o produto todo:
 * a tela é apresentada, e metade dela clarear enquanto a outra metade continua preta
 * era o pior dos dois mundos. O escuro segue sendo o PADRÃO — ninguém é movido de tema
 * sem pedir.
 *
 * Nada aqui toca React nem lê `window` por conta própria — o depósito entra por
 * parâmetro, e quem escreve o atributo no DOM é o `App`. É o mesmo motivo de
 * `lib/periodo.ts` não ler o relógio: função que alcança o ambiente sozinha não tem
 * teste determinístico.
 */

export type Tema = 'escuro' | 'claro'

/** O tema do produto. Quem nunca escolheu nada entra por aqui. */
export const TEMA_PADRAO: Tema = 'escuro'

/** Chave no `localStorage`. Namespaced: o domínio é compartilhado com outras telas. */
export const CHAVE_TEMA = 'motor.tema'

/**
 * Onde a preferência morava enquanto o tema era só da Executiva.
 *
 * Lida como SEGUNDA opção por `lerTema`, e nunca escrita. Sem isto, quem já tinha
 * escolhido o claro na Executiva voltaria ao escuro no dia do deploy — e leria como
 * "o botão parou de funcionar", não como "a chave mudou de nome". A migração acontece
 * sozinha na primeira gravação, que já sai na chave nova.
 */
export const CHAVE_TEMA_LEGADA = 'motor.exec.tema'

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
    if (ehTema(bruto)) return bruto
    // Só chega aqui quem nunca gravou na chave nova. A antiga é lida uma vez e não é
    // apagada: remover exigiria `removeItem` no `DepositoDeTema`, e ampliar a interface
    // por causa de uma chave órfã de poucos bytes não se paga.
    const legado = deposito?.getItem(CHAVE_TEMA_LEGADA)
    return ehTema(legado) ? legado : TEMA_PADRAO
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
