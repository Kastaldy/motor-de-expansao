/**
 * A regra da tela de entrar, PURA — sem React e sem rede.
 *
 * POR QUE VIVE AQUI. Mesmo motivo de `lib/inicio.ts` e `lib/troca-de-senha.ts`: o vitest
 * do piloto roda em ambiente `node` e so' casa `src/**\/*.test.ts`, sem testing-library.
 * Entao o que decide (o formulario esta' submissivel? o que esta mensagem quer dizer?)
 * fica aqui, testavel, e a tela fica burra.
 *
 * O QUE ESTA TELA AINDA NAO FAZ. Ela nao autentica ninguem: quem autentica hoje e' o
 * Authelia, na borda, e a decisao de onde o `submit` vai bater (API do Authelia agora,
 * ou o motor depois do corte do P19) esta' em aberto. O `enviar` chega por prop de
 * proposito — e' o unico ponto que muda quando essa decisao for tomada.
 */

/** Em que ponto do envio a tela esta'. */
export type EstadoEnvio = 'parado' | 'enviando'

/**
 * As falhas que a tela sabe nomear.
 *
 * `bloqueado` NAO e' detalhe de pintura, e por isso e' um caso proprio: o Authelia
 * bloqueia o usuario apos 4 tentativas erradas em 2 minutos, por 10 minutos
 * (`regulation` em `authelia/configuration.yml`, lido na VPS em 2026-09-22). A partir
 * da quinta tentativa a senha CERTA tambem falha — e uma tela que traduza isso como
 * "usuario ou senha invalidos" deixa a pessoa dez minutos repetindo a senha correta,
 * convencida de que errou. Esse era o defeito a evitar desde o primeiro desenho.
 */
export type FalhaLogin = 'credencial' | 'bloqueado' | 'indisponivel' | 'nao-ligado'

export const MENSAGEM_FALHA: Readonly<Record<FalhaLogin, string>> = Object.freeze({
  /* Mensagem DELIBERADAMENTE ambigua entre "usuario nao existe" e "senha errada": dizer
     qual dos dois falhou entrega a quem sonda a lista de quem tem conta. */
  credencial: 'Usuário ou senha incorretos.',
  /* A régua é do NOSSO servidor desde 25/09/2026: `MAX_TENTATIVAS` recusas numa janela
     MÓVEL de `JANELA_TENTATIVAS_MIN` minutos (`db/sessoes.py`). Antes esta frase dizia
     "bloqueado por 10 minutos", que é o `ban_time` do Authelia — e a diferença não é
     detalhe: lá havia um relógio fixo para esperar, aqui a janela DESLIZA, então o que
     destrava é a tentativa mais antiga envelhecer. Prometer "10 minutos" mandaria a
     pessoa esperar um prazo que não existe. */
  bloqueado:
    'Muitas tentativas seguidas. Por segurança, o acesso ficou bloqueado — aguarde alguns minutos antes de tentar de novo, ou peça a um administrador para redefinir a sua senha.',
  indisponivel:
    'Não foi possível falar com o servidor de autenticação. Ele pode estar reiniciando.',
  'nao-ligado':
    'Esta tela ainda está em revisão: a autenticação continua sendo feita pela tela do Authelia.',
})

/** HTTP -> falha nomeada. O que nao for reconhecido vira `indisponivel`, nunca
 *  `credencial`: afirmar que a senha esta' errada por causa de um 500 e' mentir. */
export function falhaDoStatus(status: number): FalhaLogin {
  if (status === 401 || status === 403) return 'credencial'
  // 429 e' o codigo de "regulado"; o Authelia tambem responde 403 no banimento, e por
  // isso o chamador que souber distinguir deve passar `bloqueado` explicitamente.
  if (status === 429) return 'bloqueado'
  return 'indisponivel'
}

/**
 * O formulario pode ser enviado?
 *
 * Campo vazio NAO vai ao servidor: alem de economizar a ida, evita gastar uma das
 * tentativas da trava. A regua e' a do NOSSO servidor desde 25/09/2026 --
 * `MAX_TENTATIVAS` recusas numa janela MOVEL de `JANELA_TENTATIVAS_MIN` minutos
 * (`lib/login-motor.ts`, espelhando `db/sessoes.py`). Ate' essa data este comentario
 * citava "4 tentativas / bloquear por 10 minutos", que e' o `regulation` do AUTHELIA e
 * deixa de existir no corte do P19.
 *
 * `auto` marca os campos que o navegador AUTOPREENCHEU e cujo valor ele ainda nao
 * deixa o JavaScript ler. Nao e' detalhe de implementacao, e' o coracao de um defeito
 * relatado duas vezes (Vinicius, 2026-09-24; Felipe, 2026-09-25: "o botao so' fica
 * azul depois que eu clico na tela, independente de onde seja o clique").
 *
 * O Chrome preenche usuario e senha na carga, mas SEGURA o valor da senha ate' haver
 * um GESTO do usuario — antes disso `input.value` devolve string vazia. Por isso a 1a
 * tentativa de correcao, que lia o DOM e sincronizava o estado, nao resolveu: ela lia
 * vazio e concluia "campo vazio". E por isso o botao acordava a qualquer clique — o
 * clique E' o gesto que libera a leitura.
 *
 * Com `auto`, o campo autopreenchido CONTA como preenchido para habilitar o botao. O
 * valor de verdade e' lido na hora do envio, quando o clique ja' aconteceu e o
 * navegador o entrega. A trava de "campo vazio nao vai ao servidor" fica de pe para
 * quem realmente deixou o campo vazio: sem autofill, `auto` e' falso e nada muda.
 */
export function podeEnviar(
  usuario: string,
  senha: string,
  estado: EstadoEnvio,
  auto: { usuario?: boolean; senha?: boolean } = {},
): boolean {
  if (estado === 'enviando') return false
  const temUsuario = usuario.trim().length > 0 || auto.usuario === true
  const temSenha = senha.length > 0 || auto.senha === true
  return temUsuario && temSenha
}

/**
 * O usuario, normalizado para o envio: sem espaco nas pontas e em minusculas.
 *
 * O `users_database.yml` do Authelia guarda os logins em minusculas, e o teclado do
 * celular capitaliza a primeira letra por conta propria — "Felipe.silva" viraria uma
 * tentativa desperdicada, e quatro delas bloqueiam o acesso por 10 minutos. A SENHA
 * nunca e' tocada: espaco em senha e' caractere como outro qualquer.
 */
export function normalizarUsuario(bruto: string): string {
  return bruto.trim().toLowerCase()
}
