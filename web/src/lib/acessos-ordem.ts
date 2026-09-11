import type { AcessosUsuarioLinha } from './types'

/* ---------------------------------------------------------------------------
   Ordenação da tabela de usuários da aba Acessos (pedido do Felipe, 2026-09-10).

   PURO e sem React de propósito, no padrão de `lib/exec.ts` e `lib/acesso.ts`: o
   vitest roda em ambiente node e a regra de ordem precisa ser testável sem DOM.

   Três estados por coluna, e é isso que atende o "ativar/desativar" do pedido:

       sem ordem  ->  1º clique  ->  2º clique (inverte)  ->  3º clique = sem ordem

   "Sem ordem" NÃO é uma ordenação nossa: é a ordem em que o backend entregou o
   payload (`_linhas_usuarios` ordena por ações desc, depois nome asc). Por isso a
   tela continua abrindo exatamente como abre hoje, e o 3º clique devolve isso.

   Ordenar aqui é VISUAL: nada disto refaz fetch nem muda o que o backend devolve.
   --------------------------------------------------------------------------- */

export type DirecaoOrdem = 'asc' | 'desc'

export interface OrdemAcessos {
  /** Chave da coluna (identificador sem acento, regra do CLAUDE.md §2). */
  chave: string
  direcao: DirecaoOrdem
}

/** Colunas que a tabela de usuários sabe ordenar — 1:1 com as chaves de `colunas`. */
export const CHAVES_ORDENAVEIS: readonly string[] = Object.freeze([
  'nome',
  'serie14',
  'ultimo',
  'dias_ativos',
  'acoes',
  'abas',
  'ips',
])

/**
 * Direção do PRIMEIRO clique, por natureza da coluna: nome abre A->Z, e todo o
 * resto abre do maior para o menor (mais recente, mais ações, mais dias) — que é
 * o que o operador procura quando clica. Mesmo critério do `aoOrdenar` da Executiva.
 */
const PRIMEIRA_DIRECAO: Record<string, DirecaoOrdem> = { nome: 'asc' }

function primeiraDirecao(chave: string): DirecaoOrdem {
  return PRIMEIRA_DIRECAO[chave] ?? 'desc'
}

/**
 * Próximo estado do ciclo de 3 posições. Devolve `null` quando a ordenação sai de
 * cena (o 3º clique na mesma coluna), e é esse `null` que a tela usa para voltar à
 * ordem do payload.
 */
export function proximaOrdem(atual: OrdemAcessos | null, chave: string): OrdemAcessos | null {
  if (!CHAVES_ORDENAVEIS.includes(chave)) return atual
  if (!atual || atual.chave !== chave) return { chave, direcao: primeiraDirecao(chave) }
  if (atual.direcao === primeiraDirecao(chave)) {
    return { chave, direcao: atual.direcao === 'asc' ? 'desc' : 'asc' }
  }
  return null
}

/**
 * Escalar de "Ritmo diário" = MÉDIA de ações por dia da série exibida na sparkline.
 *
 * A coluna mostra uma LISTA, e lista não se ordena sozinha; escolhemos a média
 * porque é literalmente o que o rótulo promete ("ritmo diário") e porque é a única
 * leitura que não muda de significado quando a janela muda: `acoes` conta a janela
 * inteira (7, 30 ou 90 dias) e a série tem no máximo 14 pontos. A soma daria a MESMA
 * ordem — o backend monta o mesmo eixo de dias para todos os usuários do payload —,
 * mas a média é o número que dá para dizer em voz alta no cabeçalho.
 *
 * Série ausente ou vazia devolve `null` e cai no mesmo tratamento dos demais nulos.
 */
export function ritmoDiario(serie: readonly number[] | null | undefined): number | null {
  if (!serie || serie.length === 0) return null
  let soma = 0
  for (const v of serie) soma += Number.isFinite(v) ? v : 0
  return soma / serie.length
}

/**
 * Instante real do último acesso, em milissegundos, para ordenar pelo MOMENTO e não
 * pela string exibida — senão `9:05` viria depois de `10:12` na comparação de texto.
 *
 * Devolve `null` para quem não tem dia registrado (nunca acessou na janela). Dia sem
 * hora vale meia-noite: é o começo do dia, o mais antigo que aquele dia pode ser.
 */
export function instanteUltimoAcesso(
  linha: Pick<AcessosUsuarioLinha, 'ultimo_dia' | 'ultimo_hora'>,
): number | null {
  if (!linha.ultimo_dia) return null
  const [ano, mes, dia] = linha.ultimo_dia.split('-').map(Number)
  if (!Number.isFinite(ano) || !Number.isFinite(mes) || !Number.isFinite(dia)) return null
  const [h, min] = String(linha.ultimo_hora ?? '').split(':').map(Number)
  const hora = Number.isFinite(h) ? h : 0
  const minuto = Number.isFinite(min) ? min : 0
  return Date.UTC(ano, mes - 1, dia, hora, minuto)
}

/** Valor numérico comparável de cada coluna. `null` = sem dado. */
function escalar(u: AcessosUsuarioLinha, chave: string): number | null {
  switch (chave) {
    case 'serie14':
      return ritmoDiario(u.serie14)
    case 'ultimo':
      return instanteUltimoAcesso(u)
    case 'dias_ativos':
      return Number.isFinite(u.dias_ativos) ? u.dias_ativos : null
    case 'acoes':
      return Number.isFinite(u.acoes) ? u.acoes : null
    case 'abas':
      // A coluna desenha bolinhas; o que se ordena é QUANTAS abas a pessoa tocou.
      return u.abas ? u.abas.length : null
    case 'ips':
      return Number.isFinite(u.ips) ? u.ips : null
    default:
      return null
  }
}

const porNome = (a: AcessosUsuarioLinha, b: AcessosUsuarioLinha): number =>
  a.nome.localeCompare(b.nome, 'pt-BR')

/**
 * Aplica a ordem escolhida. Sempre devolve um array NOVO — a lista de origem é o
 * payload memoizado no estado da tela e não pode ser mutada no lugar.
 *
 * NULO SEMPRE NO FIM, nas duas direções (mesma convenção do `ordenarUnidades` da
 * Executiva): "nunca acessou" não é um extremo de recência, é ausência de dado, e
 * jogá-lo para o topo no `asc` empurraria a informação útil para fora da tela.
 * Empate cai no nome, para a ordem não dançar entre renders.
 */
export function ordenarUsuariosAcessos(
  linhas: readonly AcessosUsuarioLinha[],
  ordem: OrdemAcessos | null,
): AcessosUsuarioLinha[] {
  if (!ordem || !CHAVES_ORDENAVEIS.includes(ordem.chave)) return [...linhas]
  const sinal = ordem.direcao === 'asc' ? 1 : -1
  return [...linhas].sort((a, b) => {
    if (ordem.chave === 'nome') return sinal * porNome(a, b)
    const va = escalar(a, ordem.chave)
    const vb = escalar(b, ordem.chave)
    if (va === null && vb === null) return porNome(a, b)
    if (va === null) return 1
    if (vb === null) return -1
    if (va === vb) return porNome(a, b)
    return sinal * (va - vb)
  })
}
