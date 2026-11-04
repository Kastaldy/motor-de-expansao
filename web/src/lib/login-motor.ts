/* ---------------------------------------------------------------------------
   O CONTRATO DE CLIENTE DO NOSSO `/api/login` — e só ele.

   Este arquivo já foi a metade pura de uma SEGUNDA tela de login, construída nesta
   branch (epic do P19) em paralelo à da `main`. Em 23/09/2026 o dono decidiu: **a tela
   da main fica**. A tela daqui foi removida, e com ela os rótulos, o `podeEntrar` e o
   `mensagemDaFalha` — a tela da main tem vocabulário próprio (`podeEnviar`,
   `MENSAGEM_FALHA`, `falhaDoStatus`, em `lib/login.ts`), e manter dois seria manter duas
   redações da mesma regra, que é como elas divergem em silêncio.

   O QUE SOBROU NÃO É RESTO: é a ponte para o backend que a main não tem. `api.entrar()`
   e `api.sair()` falam com as rotas desta epic — sessão em tabela, trava de tentativas,
   senha temporária —, e é para elas que a tela da main vai apontar no dia do corte. A
   DEC-067 diz, com todas as letras, que o `submit` dela "não tem para onde apontar"
   enquanto as quatro decisões do P19 não tiverem resposta; elas têm, e isto é o destino.

   VIVO DESDE O CORTE (DEC-081): o login próprio vale em todas as origens, o Authelia foi
   aposentado, e `api.entrar()`/`api.sair()` são o único caminho de entrada e saída.
   --------------------------------------------------------------------------- */

/**
 * Espelham `MAX_TENTATIVAS` / `JANELA_TENTATIVAS_MIN` de `db/sessoes.py`.
 *
 * A tela precisa deles porque o servidor **não diz** que trancou: a trava responde o
 * MESMO 401 com a MESMA mensagem de uma senha errada, de propósito — dizer "conta
 * bloqueada" avisaria a quem varre nomes que acertou um. Sem campo que os separe,
 * contar no cliente é a única forma de a tela dizer algo mais útil na enésima tentativa.
 *
 * Divergir daqui não quebra nada (o servidor manda), mas faz a tela prometer uma régua
 * que não existe — então mude os dois juntos. Até 25/09/2026 a tela falava em "4
 * tentativas" e "bloqueado por 10 minutos": eram os números do AUTHELIA (`max_retries 4`,
 * `ban_time 10m`) vazados para dentro do nosso vocabulário.
 */
export const MAX_TENTATIVAS = 5
export const JANELA_TENTATIVAS_MIN = 15

/** O que o servidor devolve quando a entrada dá certo. */
export interface EntradaAceita {
  /** A pessoa ainda está numa senha que não escolheu e deve trocá-la agora. */
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
 * Um 401 vindo do LOGIN é sessão caída?
 *
 * **Não** — e esta função existe para que a resposta fique escrita e testada, em vez
 * de depender de alguém lembrar.
 *
 * O `lib/api.ts` anuncia queda de sessão em todo 401, porque no backend isso
 * só acontece quando a sessão vence. Mas a rota de login devolve 401 para SENHA
 * ERRADA — e o anúncio de queda é de mão única (`jaAnunciado` em `lib/sessao.ts`
 * nunca volta atrás): uma senha digitada errada abriria "Sessão encerrada", travaria
 * a trava para o resto da carga e ofereceria como única saída recarregar a página.
 * A pessoa entraria num vaivém sem entender a causa.
 */
export function ehQuedaDeSessao(url: string): boolean {
  return !url.startsWith('/api/login')
}

/** Para onde levar a pessoa depois de sair, e o que ela vê se o encerramento falhar. */
export type Saida =
  | { tipo: 'ir'; destino: string }
  | { tipo: 'falhou'; recado: string }

/**
 * SAIR DE VERDADE — revoga no servidor ANTES de navegar.
 *
 * Ela chama o nosso `/api/logout`, que invalida a sessão NO SERVIDOR. Só limpar estado no
 * cliente seria pior que não ter botão: a tela pareceria deslogada e a próxima requisição
 * continuaria chegando autenticada — é o defeito que o próprio `/api/logout` declara
 * inaceitável ("limpar estado no cliente NÃO é logout").
 *
 * COM A DEC-081 o login próprio vale em todas as origens e o Authelia foi aposentado, então
 * SAIU o antigo fallback "404 -> portal do Authelia": não há mais portal para onde mandar.
 * `/api/logout` é público e idempotente (sair com a sessão já vencida não é erro), então o
 * caminho feliz é revogar e ir para a nossa tela de entrar.
 *
 * FALHA NÃO NAVEGA. Se o encerramento falhou (rede caiu, 503 por banco fora), a sessão
 * continua ABERTA — mandar a pessoa embora mostraria uma tela deslogada por cima de uma
 * sessão viva, que é a mentira que este caminho existe para não contar.
 */
export async function sair(chamarSair: () => Promise<void>): Promise<Saida> {
  try {
    await chamarSair()
  } catch {
    return {
      tipo: 'falhou',
      recado:
        'Não foi possível encerrar a sessão agora — ela continua aberta. ' +
        'Tente de novo em instantes; se persistir, avise quem administra.',
    }
  }
  // Revogada no servidor. A nossa tela de entrar é servida direto pela borda (DEC-081).
  return { tipo: 'ir', destino: '/entrar.html' }
}
