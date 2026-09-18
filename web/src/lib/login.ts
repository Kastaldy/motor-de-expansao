/* ---------------------------------------------------------------------------
   Entrada na plataforma (epic do P19) — a metade PURA e testável.

   POR QUE SEPARADO DO COMPONENTE. Mesma divisão de `troca-de-senha.ts` e
   `confirmacao-admin.ts`, e pela mesma razão: o `vitest.config.ts` roda com
   `environment: 'node'` e `include: ['src/**\/*.test.ts']` — sem DOM, e só `.ts`.
   Componente não é testável aqui; texto e regra são. O que pode mentir fica do
   lado que tem teste.

   O QUE ESTE ARQUIVO NÃO FAZ. Não valida FORÇA de senha. A política (mínimo de
   caracteres, etc.) vale na CRIAÇÃO e mora em `db/senhas.py::validar`; aplicá-la
   na entrada ensinaria o formato da senha a quem tenta adivinhar e recusaria, com
   recado diferente, uma senha legítima antiga. Aqui só se pergunta se há o que
   enviar.
   --------------------------------------------------------------------------- */

/** O que o servidor devolve quando a entrada dá certo. */
export interface EntradaAceita {
  /** A pessoa ainda está na senha inicial compartilhada e deve trocá-la agora. */
  deveTrocarSenha: boolean
}

/**
 * Lê a resposta de `POST /api/login` sem confiar nela.
 *
 * Defensivo no mesmo espírito de `estadoDaSenhaDoPayload`: campo ausente ou de
 * tipo errado vira `false` — "não sei" aqui não pode virar "abra a tela de troca",
 * porque abrir a troca sem necessidade trava a pessoa logo depois de entrar.
 */
export function entradaDoPayload(payload: unknown): EntradaAceita {
  if (typeof payload !== 'object' || payload === null) return { deveTrocarSenha: false }
  const bruto = (payload as { deve_trocar_senha?: unknown }).deve_trocar_senha
  return { deveTrocarSenha: bruto === true }
}

/**
 * Pode enviar o formulário?
 *
 * Só exige que haja conteúdo nos dois campos. Espaço em volta não conta: o
 * servidor normaliza o login com `strip()` antes de consultar, e deixar o botão
 * ativo com um campo só de espaços faria a pessoa gastar uma tentativa à toa.
 */
export function podeEntrar(login: string, senha: string): boolean {
  return login.trim().length > 0 && senha.length > 0
}

/** Rótulos da tela. Ficam aqui para poderem ser conferidos por teste. */
export const TITULO_LOGIN = 'Entrar'
export const ROTULO_LOGIN = 'Usuário'
export const ROTULO_SENHA = 'Senha'
export const ROTULO_LEMBRAR = 'Lembrar de mim neste computador'
export const ROTULO_BOTAO = 'Entrar'

/**
 * O que a caixinha "lembrar de mim" realmente faz, em uma linha, para a tela poder
 * dizer em vez de deixar a pessoa adivinhar.
 *
 * É FIEL ao que o Authelia já fazia (decisão 2, opção (a)): mantém a entrada ao
 * fechar e reabrir o navegador, e **não** estica o prazo — a sessão dura as mesmas
 * 8 horas nos dois casos. Prometer "continue conectado" sem o limite seria mentira
 * de interface, e quem fechasse o navegador confiando nisso voltaria deslogado no
 * dia seguinte sem entender por quê.
 */
export const AJUDA_LEMBRAR =
  'Mantém você conectado ao fechar o navegador. O acesso continua valendo por 8 horas.'

/**
 * A mensagem que a pessoa lê quando a entrada falha.
 *
 * Recebe `status` e `detalhe` em vez do objeto de erro de propósito: `ApiError`
 * mora em `lib/api.ts`, e `api.ts` precisa importar ESTE módulo — tipar pelo objeto
 * fecharia um ciclo entre os dois.
 *
 * O 401 NUNCA distingue "usuário não existe" de "senha errada", e isso não é
 * descuido de texto: o servidor devolve a mesma resposta nos dois casos justamente
 * para não entregar a lista de quem trabalha aqui. Repetir a distinção na tela
 * desfaria a defesa do lado de cá.
 */
export function mensagemDaFalha(status: number, detalhe?: string): string {
  if (status === 401) return 'Login ou senha incorretos.'
  if (status === 404) {
    // O portão nasce dormente (`MOTOR_AUTENTICACAO_PROPRIA`): enquanto o Authelia
    // autentica, a rota responde 404 porque neste ambiente ela não existe mesmo.
    return 'A entrada própria não está ativada neste ambiente.'
  }
  if (status === 503) {
    return 'O sistema de acesso está indisponível no momento. Tente de novo em instantes.'
  }
  if (status === 408) return 'A resposta demorou demais. Tente de novo.'
  if (status === 0) return 'Não foi possível falar com o servidor. Ele pode estar fora do ar.'
  // Qualquer outro: mostra o recado do servidor, se houver. Ele é escrito para a
  // pessoa (é a mesma política de `mensagemDoErro` da troca de senha).
  return detalhe?.trim() || 'Não foi possível entrar. Tente de novo.'
}

/**
 * Um 401 vindo do LOGIN é sessão caída?
 *
 * **Não** — e esta função existe para que a resposta fique escrita e testada, em vez
 * de depender de alguém lembrar.
 *
 * O `lib/api.ts` anuncia queda de sessão em todo 401, porque atrás do Authelia isso
 * só acontece quando a sessão vence. Mas a rota de login devolve 401 para SENHA
 * ERRADA — e o anúncio de queda é de mão única (`jaAnunciado` em `lib/sessao.ts`
 * nunca volta atrás): uma senha digitada errada abriria "Sessão encerrada", travaria
 * a trava para o resto da carga e ofereceria como única saída recarregar a página.
 * A pessoa entraria num vaivém sem entender a causa.
 */
export function ehQuedaDeSessao(url: string): boolean {
  return !url.startsWith('/api/login')
}
