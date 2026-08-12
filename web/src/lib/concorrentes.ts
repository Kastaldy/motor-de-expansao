/**
 * A régua de concorrentes por DISTÂNCIA: onde cada um cai entre o imóvel e a borda do raio.
 *
 * POR QUE ISTO EXISTE. A ficha dizia "4 concorrentes no raio" — número que não separa dois
 * territórios completamente diferentes: quatro academias coladas na esquina do imóvel, ou
 * quatro espalhadas na borda de 1 km. A lista com as distâncias já vinha no payload
 * (`concorrencia.lista`), em texto; faltava a leitura espacial.
 *
 * Aqui só mora o que é DECISÃO: quem entra, onde cai, e como dois pontos que se encostam
 * são separados para não virarem um borrão. O componente desenha o resultado.
 */

/**
 * O nome da rede em texto de GENTE.
 *
 * O payload devolve o IDENTIFICADOR (`smart_fit`, `bluefit`) — chave de junção com a base
 * de concorrentes, não rótulo. Mostrá-lo cru na ficha vaza identificador para a tela, o
 * que a regra de acentuação da casa proíbe: identificador fica intacto no dado, e a
 * exibição passa por uma camada de LABEL. É o que esta função é.
 *
 * Não há tabela de nomes oficiais no payload, então a conversão é mecânica (underscore
 * vira espaço, iniciais em maiúscula). "smart_fit" -> "Smart Fit". Se algum dia a API
 * publicar o nome comercial, ele passa a valer e esta função vira o fallback.
 */
export function rotuloDaRede(bruto: string | null | undefined): string {
  const s = bruto?.trim()
  if (!s) return 'Concorrente'
  return s
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((parte) => parte.charAt(0).toUpperCase() + parte.slice(1))
    .join(' ')
}

export interface PontoRegua {
  rede: string
  /** Distância em km, como veio do servidor. */
  dist: number
  /** Onde cai entre 0 e o raio, de 0 a 1. */
  fracao: number
}

/**
 * Ordena os concorrentes por distância.
 *
 * SEM EMPILHAMENTO de rótulos, e isso é uma correção: a primeira versão punha todos num
 * eixo só, com o nome centrado sob cada ponto, e vizinhos próximos grudavam o texto —
 * ilegível justamente no caso que mais importa, o de concorrentes concentrados (relato do
 * Juan, 2026-08-12). Escapar disso por regra de separação é administrar a colisão; uma
 * LINHA POR CONCORRENTE a torna impossível. A ordem daqui é a ordem das linhas.
 *
 * FORA quem não tem distância: um concorrente sem `dist_km` não pode ser posicionado, e
 * plantá-lo no zero o poria colado no imóvel — a leitura mais alarmante possível, tirada
 * de um dado que não existe. Ele continua contado no "concorrentes no raio", que é uma
 * contagem e não depende de posição.
 *
 * Distância ACIMA do raio é presa na borda em vez de sair da régua: o servidor filtra por
 * raio, mas arredondamento de projeção pode devolver 1,004 km num raio de 1,0 — e um ponto
 * fora do eixo lê-se como defeito de desenho.
 */
export function reguaDeConcorrentes(
  lista: readonly { rede: string | null; dist_km: number | null }[] | null | undefined,
  raioKm: number,
): PontoRegua[] {
  if (!lista?.length || !(raioKm > 0)) return []
  const ordenados = lista
    .filter((c): c is { rede: string | null; dist_km: number } => typeof c.dist_km === 'number')
    .map((c) => ({
      rede: rotuloDaRede(c.rede),
      dist: c.dist_km,
      fracao: Math.max(0, Math.min(1, c.dist_km / raioKm)),
    }))
    .sort((a, b) => a.fracao - b.fracao)

  return ordenados
}

/**
 * Quantos ficaram de fora do desenho por não terem distância.
 *
 * Publicado para a tela DECLARAR a diferença: "4 concorrentes" no KPI e 3 pontos na régua,
 * sem explicação, lê-se como bug.
 */
export function semDistancia(
  lista: readonly { rede: string | null; dist_km: number | null }[] | null | undefined,
): number {
  if (!lista?.length) return 0
  return lista.filter((c) => typeof c.dist_km !== 'number').length
}
