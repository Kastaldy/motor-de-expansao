/* ---------------------------------------------------------------------------
   Troca da PRÓPRIA senha (D26 / migration 016) — a metade pura e testável.

   POR QUE ESTE ARQUIVO EXISTE SEPARADO DO COMPONENTE. O projeto testa com Vitest
   em ambiente `node`, sem DOM: componente não é testável aqui, texto e regra são.
   Mesma divisão de `confirmacao-admin.ts`, pelo mesmo motivo — o que pode mentir
   fica do lado que tem teste.

   A POLÍTICA É ESPELHO, NÃO DONA. Quem decide é `db/senhas.py::validar`, no
   servidor; isto aqui existe para a pessoa saber o que falta ANTES de gastar uma
   ida ao servidor e um Argon2 de 64 MB. Se os dois divergirem, o servidor vence e
   a tela mostra o recado dele — por isso `mensagemDoErro` existe.
   --------------------------------------------------------------------------- */

/** Espelham `MINIMO_DE_CARACTERES` / `MAXIMO_DE_CARACTERES` de `db/senhas.py`. */
export const MINIMO_DE_CARACTERES = 12
export const MAXIMO_DE_CARACTERES = 128

/** O que `/api/me` passou a devolver em 11/09. Ausente = não dá para saber. */
export interface EstadoDaSenha {
  /** A pessoa ainda deve trocar (coluna `deve_trocar_senha_usuario`). */
  deveTrocar: boolean
  /** Ela já definiu senha própria alguma vez (`senha_definida_em_usuario`). */
  propria: boolean
}

/**
 * Lê o campo `senha` do payload de `/api/me` sem confiar nele.
 *
 * Defensivo no mesmo espírito de `abasDoPayload`: um backend anterior a 11/09 não
 * manda o campo, e a SPA tem de abrir igual. `null` significa **não sei** — que é
 * diferente de "não precisa trocar", e é por isso que a ausência não vira `false`.
 */
export function estadoDaSenhaDoPayload(payload: unknown): EstadoDaSenha | null {
  if (typeof payload !== 'object' || payload === null) return null
  const bruto = (payload as { senha?: unknown }).senha
  if (typeof bruto !== 'object' || bruto === null) return null
  const s = bruto as { deve_trocar?: unknown; propria?: unknown }
  if (typeof s.deve_trocar !== 'boolean') return null
  return { deveTrocar: s.deve_trocar, propria: typeof s.propria === 'boolean' ? s.propria : false }
}

/**
 * O que ainda falta na senha nova. Lista VAZIA = pode enviar.
 *
 * Devolve todos os problemas de uma vez, e não o primeiro: corrigir um por vez,
 * descobrindo o seguinte só depois de tentar, é o que faz formulário de senha ser
 * odiado. A ordem é a da política do servidor, para os recados baterem.
 */
export function problemasDaSenha(nova: string, senhaAtual = ''): string[] {
  const problemas: string[] = []
  if (nova.length < MINIMO_DE_CARACTERES) {
    problemas.push(
      `Precisa de pelo menos ${MINIMO_DE_CARACTERES} caracteres — faltam ${MINIMO_DE_CARACTERES - nova.length}.`,
    )
  }
  if (nova.length > MAXIMO_DE_CARACTERES) {
    problemas.push(`Não pode passar de ${MAXIMO_DE_CARACTERES} caracteres.`)
  }
  if (nova.length > 0 && nova.trim() !== nova) {
    problemas.push('Não pode começar nem terminar com espaço.')
  }
  // A regra que o servidor NÃO tem: lá ele não sabe se a nova é igual à atual, porque
  // compara hash. Aqui as duas estão na mão, e avisar antes evita a troca que não troca.
  if (nova.length > 0 && senhaAtual.length > 0 && nova === senhaAtual) {
    problemas.push('A senha nova é igual à atual.')
  }
  return problemas
}

/** Um passo antes do envio: os dois campos preenchidos e a política satisfeita. */
export function podeEnviar(senhaAtual: string, nova: string, repetida: string): boolean {
  if (!senhaAtual || !nova) return false
  if (nova !== repetida) return false
  return problemasDaSenha(nova, senhaAtual).length === 0
}

/**
 * O recado da tela a partir da resposta do servidor.
 *
 * O texto do servidor tem PRECEDÊNCIA quando existe: as mensagens de `senhas.py` são
 * escritas para quem lê ("Essa é a senha inicial, que é a mesma para todo mundo...").
 * Repetir uma versão nossa aqui criaria duas verdades sobre a mesma recusa. O mapa
 * abaixo é o que se diz quando o servidor não mandou texto nenhum.
 */
export function mensagemDoErro(status: number, doServidor?: string | null): string {
  const texto = (doServidor ?? '').trim()
  // Quando a resposta nao tem corpo JSON, `pedir` poe o NUMERO do status na mensagem
  // (`detalhe = String(r.status)`, api.ts:73). Mostrar "403" a quem trocou a senha nao
  // e' recado, e' ruido -- entao texto puramente numerico conta como ausente.
  if (texto && !/^\d+$/.test(texto)) return texto
  switch (status) {
    case 403:
      return 'A senha atual não confere.'
    case 422:
      return 'A senha nova não atende à política.'
    case 409:
      return 'Você não tem cadastro no banco, então não há senha sua para trocar.'
    case 503:
      return 'O sistema de senhas está indisponível agora. Tente de novo em instantes.'
    default:
      return 'Não foi possível trocar a senha agora.'
  }
}

/**
 * Título e chamada do pop-up. Os DOIS campos do estado importam, e é aqui que se vê
 * por quê: `deveTrocar` é a intenção e `propria` é o fato. Quando o admin forçar a
 * troca de quem já tinha senha própria, os dois vêm `true` — e aí a frase não pode
 * ser "defina a sua primeira senha", que seria mentira sobre o que já aconteceu.
 */
export function textoDaTroca(estado: EstadoDaSenha): { titulo: string; chamada: string } {
  if (!estado.propria) {
    return {
      titulo: 'Defina a sua senha',
      chamada:
        'Você ainda está com a senha inicial, que é a mesma para todo mundo da equipe. ' +
        'Escolha uma que só você saiba.',
    }
  }
  return {
    titulo: 'Troque a sua senha',
    chamada: 'Foi pedido que você defina uma senha nova. A atual continua valendo até você trocar.',
  }
}

/**
 * A tela deve OFERECER a troca agora?
 *
 * Só quando o banco respondeu (`estado` não é nulo) e a coluna diz que sim. E só se a
 * pessoa não dispensou nesta sessão.
 *
 * OFERECE, NÃO OBRIGA — e isto é decisão, não esquecimento. Enquanto o P19 não
 * acontecer, quem autentica é o Authelia: a senha do banco não abre nem fecha porta
 * nenhuma. Trancar o piloto atrás dela hoje tiraria o acesso de todo mundo (os seis
 * cadastros estão com `deve_trocar = true`) em troca de zero segurança. No dia da
 * virada do P19 esta função é o único lugar a mudar.
 */
export function deveOferecerTroca(estado: EstadoDaSenha | null, dispensado: boolean): boolean {
  if (estado === null) return false
  if (dispensado) return false
  return estado.deveTrocar
}
