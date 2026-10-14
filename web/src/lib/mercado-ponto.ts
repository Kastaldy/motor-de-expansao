/**
 * A conta do mercado na ficha de ponto: SAM - consumo (concorrentes + Ultra) = residual.
 *
 * POR QUE EXISTE (DEC-070, 2026-10-14). A ficha mostrava "Mercado potencial (SAM)" e
 * "Residual disponivel" lado a lado, e o consumo — a parcela que liga um ao outro — nao
 * aparecia. No caso de Santana/SP o SAM era maior que o consumo dos concorrentes e o
 * residual saia ZERO, sem nada na tela que explicasse: a parcela que faltava era a da
 * propria Ultra. Agora as tres parcelas aparecem, e a conta fecha na frente do operador.
 *
 * E' do RAIO, nao do hexagono. Desde a DEC-070 o servidor calcula SAM e consumo no raio
 * de 1,0 km do ponto (ou na area desenhada, DEC-071), com o modelo de area de influencia
 * que conserva massa. O hexagono do ponto continua no payload so' como AUDITORIA
 * (`mercado.hexagono`) e nao entra aqui.
 *
 * NAO RECALCULA NADA. Os valores sao os do servidor; esta funcao so' decide o que exibir
 * e com qual motivo. Parcela ausente sai como ausente (`null`, desenhada como travessao)
 * com o motivo que o servidor mandou — nunca como zero, que afirmaria mercado livre por
 * falta de dado.
 */
import type { PontoMercado } from './types'

/** Uma linha da conta, na ordem em que ela se le. */
export interface LinhaMercado {
  /** Identificador estavel da linha (chave de React e de teste) — NAO acentuar. */
  chave: 'sam' | 'consumo_concorrentes' | 'consumo_ultra' | 'residual'
  rotulo: string
  /** Operacao que a linha faz na conta: soma o SAM, subtrai consumo, iguala o residual. */
  sinal: '' | '-' | '='
  valor: number | null
  /** Complemento curto ("8 academias alcançam o raio"), quando o servidor o mandou. */
  detalhe: string | null
}

export interface LeituraMercado {
  /** "raio de 1,0 km" ou "área desenhada de 2,4 km²" — o recorte que a conta usou. */
  recorte: string
  linhas: LinhaMercado[]
  /**
   * Por que o SAM saiu zerado: o gate do SAM (faixa M1 do hexagono do ponto E populacao
   * do recorte >= 5.000) reprovou. Sem isto, "SAM 0" se leria como defeito.
   */
  avisoGate: string | null
  /** Parcela faltando (base de concorrentes ou cadastro Ultra ausente), com o motivo. */
  motivoParcial: string | null
}

/** Formata km com uma casa e virgula ("1,0"), sem depender do locale da instancia. */
function km(v: number): string {
  return v.toFixed(1).replace('.', ',')
}

/** O recorte em texto de usuario. Sem `raio_km` no payload, vale o raio padrao do produto. */
export function recorteDoMercado(m: Pick<PontoMercado, 'grao' | 'raio_km' | 'area_km2'>): string {
  if (m.grao === 'geometria') {
    return m.area_km2 != null ? `área desenhada de ${km(m.area_km2)} km²` : 'área desenhada'
  }
  return `raio de ${km(m.raio_km ?? 1)} km`
}

function contagem(n: number | null | undefined, singular: string, plural: string): string | null {
  if (n == null) return null
  return `${n} ${n === 1 ? singular : plural}`
}

/**
 * Monta a conta exibida a partir do bloco `mercado` do `/api/ponto`.
 *
 * Bloco indisponivel nao chega aqui: quem desenha a secao mostra o motivo do servidor no
 * lugar dela (`Secao` com `bloco`).
 */
export function leituraDoMercado(m: PontoMercado): LeituraMercado {
  const nConc = contagem(m.n_concorrentes_alcancam, 'academia de rede alcança', 'academias de rede alcançam')
  const nUltra = contagem(m.n_ultra_alcancam, 'unidade Ultra alcança', 'unidades Ultra alcançam')
  const alvo = m.grao === 'geometria' ? 'a área' : 'o raio'
  const linhas: LinhaMercado[] = [
    { chave: 'sam', rotulo: 'Mercado potencial (SAM)', sinal: '', valor: m.sam, detalhe: null },
    {
      chave: 'consumo_concorrentes',
      rotulo: 'Consumo dos concorrentes',
      sinal: '-',
      valor: m.consumo_concorrentes ?? null,
      detalhe: nConc ? `${nConc} ${alvo}` : null,
    },
    {
      chave: 'consumo_ultra',
      rotulo: 'Consumo da Ultra',
      sinal: '-',
      valor: m.consumo_ultra ?? null,
      detalhe: nUltra ? `${nUltra} ${alvo}` : null,
    },
    { chave: 'residual', rotulo: 'Residual disponível', sinal: '=', valor: m.residual, detalhe: null },
  ]

  const gate = m.gate
  const avisoGate =
    gate && gate.passa === false
      ? `O SAM sai zerado porque o gate do mercado não passa${gate.motivo ? `: ${gate.motivo}` : '.'}`
      : null

  return {
    recorte: recorteDoMercado(m),
    linhas,
    avisoGate,
    motivoParcial: m.motivo_parcial ?? null,
  }
}

/**
 * A conta exibida fecha? `residual == max(SAM - consumo, 0)`, com folga de 1 aluno.
 *
 * A folga e' de ARREDONDAMENTO: o servidor arredonda cada parcela para inteiro
 * separadamente, entao a soma das parcelas exibidas pode diferir em 1 do residual
 * exibido. Mais que isso e' conta errada — e e' o que o teste trava. `null` quando falta
 * parcela: sem ela nao ha conta para conferir.
 */
export function contaFecha(m: PontoMercado): boolean | null {
  const { sam, residual } = m
  const cc = m.consumo_concorrentes
  const cu = m.consumo_ultra
  if (sam == null || residual == null || cc == null || cu == null) return null
  return Math.abs(Math.max(sam - cc - cu, 0) - residual) <= 1
}
