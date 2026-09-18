/**
 * A senha temporária que o administrador repassa (D31, 18/09/2026).
 *
 * Módulo PURO: sem React, sem `fetch`, sem `localStorage`. O que mora aqui é o que precisa de
 * teste — os textos que a pessoa lê e as duas regras que impedem o gesto de virar armadilha.
 *
 * POR QUE ELA APARECE UMA VEZ SÓ. Até 18/09 a redefinição entregava a senha inicial
 * COMPARTILHADA, a mesma para todo mundo: quem conhecesse aquele valor entrava na conta de
 * qualquer um recém-redefinido. Agora é aleatória por pessoa e vale poucas horas. O pedido
 * original era poder REVER a senha durante a validade; isso exigiria guardá-la de forma
 * recuperável, e o banco hoje só tem hashes — um dump não entrega senha de ninguém. A saída foi
 * "rever" virar "gerar outra", que resolve o caso real (a ligação caiu, ele não anotou) sem
 * guardar nada.
 *
 * NUNCA PERSISTIR. Esta senha não pode ir para `localStorage`, `sessionStorage`, URL nem log:
 * ela é uma credencial viva. Ela vive no estado do componente e morre quando o painel fecha.
 */

/** Rótulo do botão que emite outra senha. Não é "rever" de propósito: o gesto INVALIDA a
 *  anterior, e um rótulo que sugira consulta faria o administrador clicar achando que só olha. */
export const ROTULO_GERAR_OUTRA = 'Gerar outra senha'

export const AJUDA_GERAR_OUTRA =
  'Emite uma senha nova e invalida esta. Use se você perdeu a senha antes de repassar.'

/** O que o administrador lê junto da senha. Diz as três coisas que ele precisa saber para não
 *  errar o repasse: que é temporária, por quanto tempo vale, e que não dá para consultar depois. */
export function avisoDaSenha(validadeHoras: number): string {
  const horas = validadeHoras === 1 ? '1 hora' : `${validadeHoras} horas`
  return `Anote ou copie agora: esta senha aparece uma única vez e vale por ${horas}. Quem recebê-la terá de criar a própria senha ao entrar.`
}

/** O recado depois de redefinir. Distingue os dois casos porque eles são eventos diferentes para
 *  quem administra: arrumar o acesso de quem nunca entrou, ou derrubar a senha de alguém. */
export function recadoDaRedefinicao(login: string, tinhaSenhaPropria: boolean): string {
  return tinhaSenhaPropria
    ? `${login}: a senha escolhida foi apagada e uma senha temporária foi gerada.`
    : `${login}: uma senha temporária foi gerada.`
}

/**
 * Pode fechar o painel da senha?
 *
 * Só depois de o administrador ter copiado ou confirmado que anotou. Fechar por engano com um
 * clique fora perderia a senha para sempre — e o sintoma seria a pessoa do outro lado da linha
 * sem conseguir entrar, sem ninguém entender por quê.
 */
export function podeFechar(copiou: boolean, confirmou: boolean): boolean {
  return copiou || confirmou
}

/**
 * A senha, fatiada para LEITURA EM VOZ ALTA.
 *
 * Ela nasce em grupos separados por hífen justamente porque vai ser ditada por telefone. Esta
 * função devolve os grupos para a tela poder espaçá-los; juntar tudo num bloco só é o que faz
 * quem dita perder a conta no meio.
 */
export function gruposDaSenha(senha: string): string[] {
  return senha.split('-').filter((g) => g.length > 0)
}
