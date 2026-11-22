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

   NO DIA DO CORTE a senha inicial do banco passou a ser a compartilhada do Authelia (o
   `db alinhar-senhas` remarcou a troca de quem nunca definiu a própria). Por isso, com a
   chave ligada, a frase do recado volta a ser verdadeira — e ela está aqui, idêntica.

   DESDE 16/11/2026 O AUTHELIA NÃO EXISTE MAIS (Estágio 3 da DEC-081): saiu o passo de
   cadastrar a pessoa no `users_database.yml`, que até ali era o caminho de volta do corte. Com a
   chave desligada não há outra porta de entrada: a senha do banco só passa a valer quando
   o login próprio for ligado neste servidor.

   MÓDULO PURO, pela razão de sempre deste projeto: o Vitest roda em `node`, sem DOM, e o
   texto é a parte que pode mentir. Mesma divisão de `confirmacao-admin.ts`.
   --------------------------------------------------------------------------------- */

import { PERFIL_MASTER } from './confirmacao-admin'

/**
 * O rótulo da coluna da senha. "(banco)" porque o selo descreve a senha do BANCO — a que o
 * login próprio confere. Era ela que separava a senha do banco da do Authelia, enquanto ele
 * existiu, e ficou: diz de onde vem o selo PRÓPRIA/INICIAL ao lado.
 */
export const COLUNA_SENHA = 'Senha (banco)'

/**
 * O login próprio está LIGADO neste deploy? Lê o `login_proprio` da listagem sem confiar nele.
 *
 * Ausente ou de outro tipo conta como DESLIGADO, o lado conservador: esconde os gestos de
 * senha (que o servidor recusaria) e avisa que a senha do banco ainda não vale na entrada.
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
    : `${estado} É a senha do banco, que ainda não é usada para entrar: o login próprio está ` +
        'desligado neste servidor.'
}

/**
 * O recado que fica na tela depois de criar alguém. Até 16/11/2026 ele pedia, nos dois estados,
 * o cadastro no Authelia; com o Authelia aposentado, sobra dizer se a pessoa já entra.
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
        'primeiro acesso.',
    }
  }
  return {
    titulo: `${login} foi criado no banco, mas ainda não consegue entrar.`,
    corpo:
      'O login próprio está desligado neste servidor, e sem ele ninguém entra pela tela de ' +
      'login. A senha do banco só passa a valer quando ele for ligado.',
  }
}

/** A frase ao lado dos botões do formulário de criação. */
export function dicaDoFormulario(loginProprio: boolean): string {
  return loginProprio
    ? 'Sem campo de senha de propósito — a pessoa recebe a senha inicial do piloto e troca no ' +
        'primeiro acesso.'
    : 'Sem campo de senha de propósito — com o login próprio desligado neste servidor, a ' +
        'senha do banco ainda não vale na entrada.'
}

/** A dica do botão "Criar usuário". */
export function tituloDoBotaoCriar(loginProprio: boolean): string {
  return loginProprio
    ? 'Cria a pessoa com a senha inicial do piloto, marcada para troca.'
    : 'Cria a pessoa no banco. Para entrar, o login próprio precisa estar ligado.'
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
        'primeiro acesso. A coluna ',
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
    { forte: 'O login próprio está desligado neste servidor:' },
    ' a pessoa criada aqui aparece nesta lista, mas só entra quando ele for ligado. A coluna ',
    { forte: COLUNA_SENHA },
    ' diz quem já definiu a própria senha no banco: é a que o login próprio do piloto vai ' +
      'conferir quando for ligado, e hoje ela não é usada para entrar; nenhum hash sai do ' +
      'banco para esta tela. ',
    { forte: 'Redefinir senha' },
    ' e ',
    { forte: 'Exigir troca' },
    ' só aparecem com o login próprio ligado: até lá, a senha do banco não é conferida na ' +
      'entrada, e mexer nela não mudaria nada.',
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

/* ---------------------------------------------------------------------------
   O vínculo com MASTER FRANQUIA (emenda 1 da DEC-087, 17/11/2026).

   O perfil Master vê na Visão Executiva só as unidades cujo `master_franquia` do cadastro está
   vinculado a ele. Até esta emenda o vínculo era um INSERT manual no banco; agora é um campo da
   aba Acessos, obrigatório para o perfil Master e ausente para os outros. As opções vêm do
   cadastro das unidades (`masters_disponiveis`), e o servidor recusa nome que não esteja lá.
   --------------------------------------------------------------------------- */

/** O rótulo do campo, no formulário de criação e na edição da linha. */
export const ROTULO_CAMPO_MASTER = 'Master franquia'

/** A dica abaixo das opções do campo. */
export const DICA_CAMPO_MASTER =
  'Escolha ao menos um. Na Visão Executiva, a pessoa vê só as unidades desses masters.'

/** Sem cadastro de unidades no servidor não há o que escolher (e o servidor recusaria). */
export const SEM_MASTERS_NO_CADASTRO =
  'O cadastro de unidades não está disponível neste servidor: não há master para escolher.'

/** A dica do chip de um master vinculado que o cadastro não tem mais (renomeado ou removido). */
export const TITULO_MASTER_FORA_DO_CADASTRO =
  'Este nome não está no cadastro de unidades: por ele, a pessoa não vê nenhuma unidade.'

/** A mesma chave do servidor (`_chave_master`): sem espaço nas pontas, espaços internos
 *  colapsados e sem caixa. É por ela que um vínculo antigo casa com a grafia do cadastro. */
export function chaveMaster(nome: string): string {
  return nome.trim().split(/\s+/).join(' ').toLocaleLowerCase('pt-BR')
}

/**
 * A seleção com que a edição abre: os masters de hoje trocados pela grafia do cadastro, e à
 * parte os que o cadastro não tem mais. Esses não viram opção — salvar com eles seria recusado
 * —, e a tela avisa que saem ao salvar.
 *
 * Sem cadastro no servidor (`disponiveis` vazio: AR, ou o volume fora do ar) não dá para dizer
 * que um nome SAIU dele — a mesma regra do chip da linha, que fica cinza nesse caso. Nada vai
 * para `foraDoCadastro`, e a tela não promete "sai ao salvar" (o Salvar fica travado sem opção).
 */
export function selecaoInicialDeMasters(
  atuais: string[],
  disponiveis: string[],
): { selecionados: string[]; foraDoCadastro: string[] } {
  if (disponiveis.length === 0) return { selecionados: [], foraDoCadastro: [] }
  const porChave = new Map(disponiveis.map((d) => [chaveMaster(d), d]))
  const selecionados: string[] = []
  const foraDoCadastro: string[] = []
  for (const nome of atuais) {
    const doCadastro = porChave.get(chaveMaster(nome))
    if (doCadastro === undefined) foraDoCadastro.push(nome)
    else if (!selecionados.includes(doCadastro)) selecionados.push(doCadastro)
  }
  return { selecionados, foraDoCadastro }
}

/** Marca ou desmarca um master, mantendo a ordem do cadastro. */
export function alternarMaster(
  selecionados: string[],
  nome: string,
  disponiveis: string[],
): string[] {
  const marcados = new Set(selecionados)
  if (marcados.has(nome)) marcados.delete(nome)
  else marcados.add(nome)
  return disponiveis.filter((d) => marcados.has(d))
}

/** O perfil Master ainda sem master escolhido: trava o botão de criar ou salvar. */
export function faltaMaster(perfil: string, masters: string[]): boolean {
  return perfil === PERFIL_MASTER && masters.length === 0
}

/** O que vai no corpo da criação: os masters só com o perfil Master (os outros o recusam). */
export function mastersDaCriacao(perfil: string, masters: string[]): string[] | undefined {
  return perfil === PERFIL_MASTER ? masters : undefined
}

/** O bloco de resposta do PATCH que a tela usa para o recado. */
interface Mudanca {
  mudou: boolean
}

/**
 * O recado depois de uma alteração, montado da RESPOSTA do servidor — nunca do que foi pedido:
 * `mudou: false` é "já estava assim", e a tela não pode chamar isso de alteração.
 *
 * `rotulo` é o `rotuloPerfil` de `confirmacao-admin.ts` (passado, e não importado, para este
 * módulo seguir só de textos).
 */
export function recadoDaAlteracao(
  login: string,
  r: {
    perfil?: Mudanca & { de: string; para: string }
    status?: Mudanca & { ativo: boolean }
    paises?: Mudanca & { para: string[] }
    masters?: Mudanca & { para: string[] }
    avisos?: Mudanca & { para: string[] }
  },
  rotulo: (perfil: string) => string,
  rotuloDoAviso: (aviso: string) => string = (a) => a,
): string {
  const masters = r.masters?.mudou ? r.masters.para : null
  if (r.perfil?.mudou) {
    const troca = `${login}: ${rotulo(r.perfil.de)} → ${rotulo(r.perfil.para)}`
    if (masters === null) return `${troca}.`
    return masters.length
      ? `${troca}, com master franquia ${masters.join(', ')}.`
      : `${troca}; vínculo com master franquia removido.`
  }
  if (r.status?.mudou) return `${login} foi ${r.status.ativo ? 'reativado' : 'desativado'}.`
  if (r.paises?.mudou) return `${login}: países agora ${r.paises.para.join(', ')}.`
  if (masters !== null) {
    return masters.length
      ? `${login}: master franquia agora ${masters.join(', ')}.`
      : `${login}: vínculo com master franquia removido.`
  }
  if (r.avisos?.mudou) {
    return r.avisos.para.length
      ? `${login}: avisos agora ${r.avisos.para.map(rotuloDoAviso).join(', ')}.`
      : `${login}: nenhum aviso marcado (ficam só os do perfil).`
  }
  return `${login} já estava assim — nada foi alterado.`
}
