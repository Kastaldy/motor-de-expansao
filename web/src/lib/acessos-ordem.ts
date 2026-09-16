import { ordenarPorEscalar, type DirecaoOrdem } from './ordenacao'
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

export type { DirecaoOrdem }

/**
 * FONTE ÚNICA das colunas ordenáveis: `chave -> escalar comparável`.
 *
 * As mesmas 7 chaves viviam em TRÊS listas que nada amarrava — esta allowlist, o
 * array `colunas` da tela e um `switch` de escalares —, e cada par que saísse de
 * sincronia falhava em silêncio, verde no `tsc` e na suíte:
 *
 *   (i)  chave viva em `colunas` e fora da allowlist -> `proximaOrdem` devolve o
 *        próprio estado atual e o cabeçalho para de responder ao clique;
 *   (ii) chave na allowlist sem escalar -> `asc` e `desc` devolvem a MESMA ordem
 *        A-Z, que o operador lê como "ordenou errado".
 *
 * Agora as três saem daqui: `CHAVES_ORDENAVEIS` é o `Object.keys` deste mapa e
 * `ChaveAcessos` é o `keyof` dele — o tipo com que a tela declara as colunas
 * (`Record<ChaveAcessos, ...>` em `AcessosScreen`, no molde do `COLUNAS_METRICA`
 * da Executiva). Acrescentar uma coluna aqui SEM desenhá-la lá, ou o contrário,
 * passa a ser erro de compilação — não mais um defeito mudo em produção.
 *
 * A ORDEM das chaves é a ordem das colunas na tela: a tabela é montada por esta
 * lista, então mexer aqui move a coluna.
 */
const ESCALARES = {
  /**
   * `nome` ordena pelo RÓTULO (A-Z / Z-A), não por escalar: `ordenarPorEscalar`
   * desvia para a colação pt-BR antes de chamar esta função, que existe para o
   * `Object.keys` enxergar a coluna.
   */
  nome: () => null,
  serie14: (u: AcessosUsuarioLinha) => ritmoDiario(u.serie14),
  ultimo: (u: AcessosUsuarioLinha) => instanteUltimoAcesso(u),
  dias_ativos: (u: AcessosUsuarioLinha) => (Number.isFinite(u.dias_ativos) ? u.dias_ativos : null),
  acoes: (u: AcessosUsuarioLinha) => (Number.isFinite(u.acoes) ? u.acoes : null),
  // A coluna desenha bolinhas; o que se ordena é QUANTAS abas a pessoa tocou.
  abas: (u: AcessosUsuarioLinha) => (u.abas ? u.abas.length : null),
  ips: (u: AcessosUsuarioLinha) => (Number.isFinite(u.ips) ? u.ips : null),
} satisfies Record<string, (u: AcessosUsuarioLinha) => number | null>

/** Chave de coluna que a tabela de usuários sabe ordenar. */
export type ChaveAcessos = keyof typeof ESCALARES

/** Colunas ordenáveis, na ordem em que aparecem — derivadas de `ESCALARES`. */
export const CHAVES_ORDENAVEIS: readonly ChaveAcessos[] = Object.freeze(
  Object.keys(ESCALARES) as ChaveAcessos[],
)

/**
 * Guarda da fronteira NÃO tipada: `Tabela` entrega a chave clicada como `string`
 * (`Coluna<T>.chave` é `string` para toda tabela do produto), então o estreitamento
 * acontece aqui, uma vez, na entrada.
 *
 * `includes` no array e não `chave in ESCALARES`: o `in` anda pela cadeia de
 * protótipos e daria `true` para `toString`, `constructor` e companhia.
 */
export function ehChaveOrdenavel(chave: string): chave is ChaveAcessos {
  return (CHAVES_ORDENAVEIS as readonly string[]).includes(chave)
}

export interface OrdemAcessos {
  /** Chave da coluna (identificador sem acento, regra do CLAUDE.md §2). */
  chave: ChaveAcessos
  direcao: DirecaoOrdem
}

/**
 * Direção do PRIMEIRO clique, por natureza da coluna: nome abre A->Z, e todo o
 * resto abre do maior para o menor (mais recente, mais ações, mais dias) — que é
 * o que o operador procura quando clica. Mesmo critério do `aoOrdenar` da Executiva.
 */
const PRIMEIRA_DIRECAO: Partial<Record<ChaveAcessos, DirecaoOrdem>> = { nome: 'asc' }

function primeiraDirecao(chave: ChaveAcessos): DirecaoOrdem {
  return PRIMEIRA_DIRECAO[chave] ?? 'desc'
}

/**
 * Próximo estado do ciclo de 3 posições. Devolve `null` quando a ordenação sai de
 * cena (o 3º clique na mesma coluna), e é esse `null` que a tela usa para voltar à
 * ordem do payload.
 */
export function proximaOrdem(atual: OrdemAcessos | null, chave: string): OrdemAcessos | null {
  if (!ehChaveOrdenavel(chave)) return atual
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

/**
 * Aplica a ordem escolhida com a política de `lib/ordenacao.ts` — a MESMA do
 * `ordenarUnidades` da Executiva, agora escrita num lugar só: nulo sempre no fim
 * nas duas direções ("nunca acessou" é ausência de dado, não um extremo de
 * recência), empate no nome e array novo a cada chamada (a lista de origem é o
 * payload memoizado no estado da tela e não pode ser mutada no lugar).
 */
export function ordenarUsuariosAcessos(
  linhas: readonly AcessosUsuarioLinha[],
  ordem: OrdemAcessos | null,
): AcessosUsuarioLinha[] {
  if (!ordem || !ehChaveOrdenavel(ordem.chave)) return [...linhas]
  return ordenarPorEscalar(linhas, ordem.chave, ordem.direcao, {
    escalar: (u, chave) => ESCALARES[chave as ChaveAcessos](u),
    rotulo: (u) => u.nome,
  })
}
