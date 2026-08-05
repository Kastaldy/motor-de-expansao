/* ---------------------------------------------------------------------------
   Ponte Viabilidade -> PDF do Relatorio Pontual.

   FIN-VIAB-01: o PDF passa a consumir EXATAMENTE o mesmo objeto que a tela —
   o `viabilidade_payload_v1` inteiro, sem remapear chave e sem recalcular nada.
   Era justamente a traducao de chaves/unidades aqui (e a segunda implementacao
   do lado Python) que fazia tela e PDF divergirem no MESMO cenario: payback 35
   vs 33, aluguel-teto R$55,5 mil vs R$105,8 mil.

   A funcao continua existindo como a UNICA costura entre os dois consumidores:
   se um dia o PDF precisar de algo, entra no payload do motor — nao numa conta
   feita aqui.
   --------------------------------------------------------------------------- */
import { coordenadaDoEstudo, ehCentroideDoHex } from './coord'
import type { InfoImovel, ViabilidadeOut } from './types'

/**
 * Passa o payload adiante como esta (copia rasa, para nao vazar a referencia do
 * estado da tela). NENHUMA derivacao: `versao` viaja junto para o gerador poder
 * recusar um contrato que nao conhece.
 */
export function viabilidadeParaPdf(res: ViabilidadeOut): Record<string, unknown> {
  return { ...res } as unknown as Record<string, unknown>
}

/**
 * Mapeia os inputs do imóvel para o CONTRATO de `censo_report._info_imovel_page`, que
 * lê CHAVES ESPECÍFICAS: `metragem_m2`, `aluguel_pedido`, `valor_venda`, `pe_direito_m`,
 * `vagas`, `tipo_imovel`, além de `endereco` e `observacoes`.
 *
 * BUG que isto corrige: a metragem e o aluguel vivem no **Cenário** (não em "Dados para o
 * relatório") e nunca eram enviados; e o front mandava `pe_direito`/`tipo`, mas o PDF lê
 * `pe_direito_m`/`tipo_imovel`. Resultado: o imóvel saía com "n/d" mesmo tudo preenchido.
 * Mesmo padrão testado do `viabilidadeParaPdf`: chave errada → slide vazio, sem erro.
 *
 * `metragem_m2`/`aluguel_pedido` vêm como número (formatação `num`/`brl` do gerador); os
 * campos de texto são convertidos para número no formato pt-BR (ponto=milhar, vírgula=decimal)
 * quando possível, senão seguem como texto (o gerador degrada gracioso). Chaves vazias saem.
 */
export function infoImovelParaPdf(
  info: InfoImovel,
  cenario: { m2: number; aluguel: number },
): Record<string, unknown> {
  const numOpt = (s?: string): number | string | undefined => {
    const t = (s ?? '').trim()
    if (!t) return undefined
    // pt-BR: ponto separa milhar, vírgula é decimal. Só remove o ponto quando ele
    // separa milhar (seguido de exatamente 3 dígitos), preservando "4.5" como 4.5.
    const cleaned = t
      .replace(/[^\d.,-]/g, '')
      .replace(/\.(?=\d{3}(\D|$))/g, '')
      .replace(',', '.')
    const n = Number(cleaned)
    return cleaned !== '' && Number.isFinite(n) ? n : t
  }
  const out: Record<string, unknown> = {
    metragem_m2: cenario.m2,
    aluguel_pedido: cenario.aluguel,
    valor_venda: numOpt(info.valor_venda),
    pe_direito_m: numOpt(info.pe_direito),
    vagas: numOpt(info.vagas),
    tipo_imovel: info.tipo?.trim() || undefined,
    endereco: info.nome?.trim() || undefined,
    observacoes: info.observacoes?.trim() || undefined,
  }
  for (const k of Object.keys(out)) if (out[k] === undefined) delete out[k]
  return out
}

/**
 * O ponto escolhido, visto pelo relatorio. Subconjunto estrutural de `PontoEscolhido`
 * (App.tsx): so o que decide a coordenada e o rotulo. Fica aqui — e nao no `.tsx` —
 * para que a decisao seja testavel sem montar a tela.
 */
export interface PontoDoRelatorio {
  /** Centroide do hexagono res-7. Sempre existe; a ate ~1,5 km do endereco. */
  hex: { lat: number; lng: number }
  /** Rotulo herdado do hexagono/municipio quando o operador nao digita um nome. */
  rotulo: string
  /** Coordenada EXATA do imovel (busca por endereco/lat,lng). Ausente = clique no ranking. */
  lat?: number
  lng?: number
}

/** Parametros de identificacao do ponto no `api.relatorioPontual` (contrato dele). */
export interface ParametrosRelatorioPontual {
  lat: number
  lng: number
  rotulo: string
  origemCentroideHex: boolean
}

/**
 * Decide COM QUE COORDENADA o Relatorio Pontual e tirado e se o PDF precisa AVISAR
 * que ela e uma aproximacao.
 *
 * Vivia dentro do `ViabilityScreen.tsx`, onde nenhum teste alcanca: trocar o flag por
 * `false` mantinha tsc, vitest e a suite Python verdes e o PDF voltava a sair com cara
 * de laudo de endereco embora o raio tivesse sido tracado de um centroide a ate ~1,5 km.
 *
 * As duas respostas saem da MESMA regra de `lib/coord.ts` (`coordenadaDoEstudo` e
 * `ehCentroideDoHex`), nunca de uma copia: o aviso so e honesto se ele for verdadeiro
 * exatamente quando a coordenada devolvida for a do hexagono. Cuidado permanente:
 * `lat: 0`/`lng: 0` sao coordenadas VALIDAS (falsy em JS) e nao contam como ausentes.
 *
 * `rotuloManual` e o nome que o operador digitou em "Dados para o relatorio"; ele viaja
 * INTACTO (texto livre — endereco com parenteses, complemento, esquina) e, vazio, cede
 * lugar ao rotulo do proprio ponto.
 */
export function parametrosRelatorioPontual(
  ponto: PontoDoRelatorio,
  opts: { rotuloManual?: string } = {},
): ParametrosRelatorioPontual {
  const alvo = coordenadaDoEstudo(ponto)
  return {
    lat: alvo.lat,
    lng: alvo.lng,
    rotulo: opts.rotuloManual || ponto.rotulo,
    origemCentroideHex: ehCentroideDoHex(ponto),
  }
}
