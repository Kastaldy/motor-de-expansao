/* ---------------------------------------------------------------------------
   Os TEXTOS da administração de usuários que dependem do login próprio.

   POR QUE ESTE ARQUIVO EXISTE. Até 24/10/2026 o `PainelUsuarios.tsx` falava como se o
   login próprio (P19, `MOTOR_AUTENTICACAO_PROPRIA`) já estivesse ligado: depois de criar
   alguém dizia "a senha inicial é a compartilhada do piloto, e a pessoa será levada a
   trocá-la no primeiro acesso", e o rodapé dizia que "Redefinir senha" obrigava a criar uma
   senha nova na entrada. Com a chave DESLIGADA — o estado de produção até o corte — quem
   confere a senha é o Authelia, e as duas frases eram falsas. Decisão do dono: os textos
   passam a dizer a verdade nos dois estados, e os gestos de senha só aparecem com a chave
   ligada.

   NO DIA DO CORTE a senha inicial do banco passa a ser a compartilhada do Authelia (o
   `db alinhar-senhas` remarca a troca de quem nunca definiu a própria). Por isso, com a
   chave ligada, a frase do recado volta a ser verdadeira — e ela está aqui, idêntica.

   MÓDULO PURO, pela razão de sempre deste projeto: o Vitest roda em `node`, sem DOM, e o
   texto é a parte que pode mentir. Mesma divisão de `confirmacao-admin.ts`.
   --------------------------------------------------------------------------------- */

/** O arquivo do Authelia onde a pessoa ainda precisa ser cadastrada. */
export const ARQUIVO_AUTHELIA = 'authelia/users_database.yml'

/**
 * O rótulo da coluna da senha. "(banco)" porque o selo descreve a senha do BANCO — a que o
 * login próprio confere —, e não a que a pessoa digita hoje no Authelia. Sem o qualificador,
 * "inicial" ao lado de quem entra todo dia com a senha da equipe leria como cadastro errado.
 */
export const COLUNA_SENHA = 'Senha (banco)'

/**
 * O login próprio está LIGADO neste deploy? Lê o `login_proprio` da listagem sem confiar nele.
 *
 * Ausente ou de outro tipo conta como DESLIGADO, o lado conservador: esconde os gestos de
 * senha (que o servidor recusaria) e mostra o recado de quem ainda depende do Authelia.
 */
export function loginProprioDoPayload(payload: unknown): boolean {
  if (typeof payload !== 'object' || payload === null) return false
  return (payload as { login_proprio?: unknown }).login_proprio === true
}

/** A dica (`title`) do selo PRÓPRIA/INICIAL: diz que a senha é a do banco, e para que ela serve hoje. */
export function tituloDoSeloDaSenha(senhaPropria: boolean, loginProprio: boolean): string {
  const estado = senhaPropria
    ? 'Já definiu uma senha própria no banco.'
    : 'Ainda está na senha inicial do banco — nunca definiu a própria.'
  return loginProprio
    ? `${estado} É a senha do banco que o piloto confere na entrada.`
    : `${estado} É a senha do banco, que ainda não é usada para entrar: hoje a entrada é pelo ` +
        'Authelia, com a senha de lá.'
}

/**
 * O recado que fica na tela depois de criar alguém. O passo do Authelia aparece nos DOIS
 * estados, por razões diferentes: desligado, sem ele a pessoa não entra; ligado, durante a
 * janela de observação do corte, ele é o que mantém o rollback possível.
 */
export function recadoDaCriacao(
  login: string,
  loginProprio: boolean,
): { titulo: string; corpo: string } {
  if (loginProprio) {
    return {
      titulo: `${login} foi criado e já pode entrar.`,
      corpo:
        'A senha inicial é a compartilhada do piloto, e a pessoa será levada a trocá-la no ' +
        `primeiro acesso. Durante a janela de observação do corte, cadastre o login ${login} ` +
        `também no ${ARQUIVO_AUTHELIA} do servidor, para o rollback continuar possível.`,
    }
  }
  return {
    titulo: `${login} foi criado no banco, mas ainda não consegue entrar.`,
    corpo:
      `Falta cadastrar o login ${login} no ${ARQUIVO_AUTHELIA} do servidor — é o Authelia ` +
      'que confere a senha na entrada hoje, com a senha de lá. A senha do banco só passa a ' +
      'valer quando o login próprio do piloto for ligado.',
  }
}

/** A frase ao lado dos botões do formulário de criação. */
export function dicaDoFormulario(loginProprio: boolean): string {
  return loginProprio
    ? 'Sem campo de senha de propósito — a pessoa recebe a senha inicial do piloto e troca no ' +
        'primeiro acesso.'
    : 'Sem campo de senha de propósito — hoje a senha que vale na entrada é a do Authelia, ' +
        'cadastrada no servidor.'
}

/** A dica do botão "Criar usuário". */
export function tituloDoBotaoCriar(loginProprio: boolean): string {
  return loginProprio
    ? 'Cria a pessoa com a senha inicial do piloto, marcada para troca.'
    : 'Cria a pessoa no banco. Para entrar, ela ainda precisa do cadastro no Authelia.'
}

/** Um pedaço do rodapé: texto corrido, ou um trecho em destaque. */
export type Segmento = string | { forte: string }

/**
 * O miolo do rodapé da tabela — a parte que depende da chave. O começo (a trilha) e o fim (o
 * número ao lado de cada perfil) valem nos dois estados e ficam no componente.
 */
export function rodapeDoPainel(loginProprio: boolean): Segmento[] {
  if (loginProprio) {
    return [
      { forte: 'Criar usuário' },
      ' dá à pessoa a senha inicial compartilhada do piloto, e ela é levada a trocá-la no ' +
        'primeiro acesso; durante a janela de observação do corte, cadastre-a também no ' +
        'Authelia, no servidor, para o rollback continuar possível. A coluna ',
      { forte: COLUNA_SENHA },
      ' diz quem já definiu a própria senha — é a que o piloto confere na entrada; nenhum hash ' +
        'sai do banco para esta tela. ',
      { forte: 'Redefinir senha' },
      ' gera uma senha temporária só daquela pessoa e mostra a você uma única vez, para ' +
        'repassar; ela vale poucas horas e derruba as sessões abertas dela. Na entrada, o ' +
        'piloto convida a pessoa a criar uma senha nova — oferece, não obriga —, e depois do ' +
        'prazo a temporária para de funcionar. Se você perder a senha antes de repassar, gere ' +
        'outra — a anterior deixa de valer.',
    ]
  }
  return [
    { forte: 'Criar usuário grava só no banco:' },
    ' a pessoa também precisa ser cadastrada no Authelia, no servidor — é ele que confere a ' +
      'senha na entrada hoje —, senão ela aparece nesta lista e não consegue entrar. A coluna ',
    { forte: COLUNA_SENHA },
    ' diz quem já definiu a própria senha no banco: é a que o login próprio do piloto vai ' +
      'conferir quando for ligado, e hoje ela não é usada para entrar; nenhum hash sai do ' +
      'banco para esta tela. ',
    { forte: 'Redefinir senha' },
    ' e ',
    { forte: 'Exigir troca' },
    ' só aparecem com o login próprio ligado: até lá, a senha que vale na entrada é a do ' +
      'Authelia, e mexer na do banco não mudaria nada.',
  ]
}

/** O rodapé como texto corrido — para teste e leitura, sem a marcação de destaque. */
export function textoCorrido(segmentos: Segmento[]): string {
  return segmentos.map((s) => (typeof s === 'string' ? s : s.forte)).join('')
}

/**
 * O recado de erro da tela, a partir do status e do texto que o servidor mandou.
 *
 * 404 TEM DOIS SENTIDOS AQUI, e o que os separa é o texto. O "Not Found" CRU é a allowlist
 * do painel: para quem está fora dela a rota "não existe" (emenda da DEC-027). Um 404 com
 * texto PRÓPRIO é outra recusa — o login próprio desligado nos gestos de senha, ou gente que
 * não existe —, e a frase do servidor é a verdadeira. Até 24/10/2026 todo 404 virava "painel
 * não habilitado", o que mandaria quem administra procurar uma allowlist em que ele está.
 *
 * 503 NÃO AFIRMA MAIS "nada foi alterado" (#463, follow-up B). Na ESCRITA isso não é
 * garantia: o banco pode cair no meio de uma gravação, e a resposta de um COMMIT interrompido
 * é ambígua. A troca conjunta de perfil e status virou uma transação só, mas nem isso torna
 * a frase verdadeira — então o recado manda conferir, que é o que dá para afirmar.
 */
export function mensagemDeErroDoPainel(
  status: number,
  mensagem: string,
  { escrita = false }: { escrita?: boolean } = {},
): string {
  const texto = mensagem.trim()
  const semTexto = texto === '' || texto === 'Not Found' || /^\d+$/.test(texto)
  if (status === 404 && semTexto) {
    return 'O painel de acessos não está habilitado para este usuário.'
  }
  if (status === 503) {
    const base = semTexto ? 'O cadastro de usuários está indisponível agora' : texto
    const frase = /[.!?]$/.test(base) ? base : `${base}.`
    return escrita
      ? `${frase} Não dá para garantir que nada foi gravado: recarregue a lista para ` +
          'conferir antes de tentar de novo.'
      : frase
  }
  return semTexto ? `O servidor recusou o pedido (${status}).` : texto
}
