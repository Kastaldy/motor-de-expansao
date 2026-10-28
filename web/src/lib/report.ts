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
import type { Alcance } from './alcance'
import { coordenadaDoEstudo, ehCentroideDoHex } from './coord'
import { MINUTOS_DO_CARRO, rotuloDaIsocrona, rotuloDoRaio } from './recorte'
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
  /** Estudo da unidade Ultra (emenda da DEC-070): o PDF tira o consumo da unidade. */
  estudoUltra?: boolean
  /**
   * O ALCANCE da ficha (DEC-074, Emenda 4): o relatório completo sai nesse recorte. Ausente
   * (ou `raio_1km`) = o raio de 1 km de sempre.
   */
  alcance?: Alcance
}

/** Parametros de identificacao do ponto no `api.relatorioPontual` (contrato dele). */
export interface ParametrosRelatorioPontual {
  lat: number
  lng: number
  rotulo: string
  origemCentroideHex: boolean
  /** So' presente (e `true`) no estudo da unidade Ultra. */
  excluirUltraProxima?: true
  /** So' presente fora do raio de 1 km (DEC-074, Emenda 4): o recorte do relatorio completo. */
  alcance?: Alcance
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
  const out: ParametrosRelatorioPontual = {
    lat: alvo.lat,
    lng: alvo.lng,
    rotulo: opts.rotuloManual || ponto.rotulo,
    origemCentroideHex: ehCentroideDoHex(ponto),
  }
  /* O MODO viaja com o ponto (emenda da DEC-070): o nome que chega do estudo da unidade
     ja' diz "(unidade Ultra)", e sem a flag o PDF do Simulador calcularia o estudo de
     ponto sob esse titulo. */
  if (ponto.estudoUltra === true) out.excluirUltraProxima = true
  /* O ALCANCE viaja com o ponto (DEC-074, Emenda 4): sem ele o relatório completo saía no
     raio de 1 km de um ponto lido em 5 min de carro (relato do Vinicius, 27/10/2026). O raio
     de 1 km não vira campo: é o default do servidor, e o pedido de sempre fica byte a byte. */
  if (ponto.alcance && ponto.alcance !== 'raio_1km') out.alcance = ponto.alcance
  return out
}

/**
 * O `title` do botão "Relatório completo em PDF" da Viabilidade no raio de 1 km — o texto de
 * sempre, para a tela do raio de 1 km não mudar um caractere (decisão 5 da DEC-074).
 */
export const DICA_RELATORIO_COMPLETO =
  'Relatório Pontual Censitário 1,0 km com fotos, dados do imóvel e os números da viabilidade'

/** O recorte do relatório completo em texto de usuário: os MESMOS rótulos da ficha (`lib/recorte`). */
export function rotuloDoRecorteDoRelatorio(alcance: Alcance | undefined): string {
  if (alcance === 'carro_5min' || alcance === 'carro_10min') {
    return rotuloDaIsocrona(null, MINUTOS_DO_CARRO[alcance])
  }
  return rotuloDoRaio(alcance === 'raio_2km' ? 2 : 1)
}

const foraDoRaioPadrao = (alcance: Alcance | undefined): alcance is Exclude<Alcance, 'raio_1km'> =>
  alcance != null && alcance !== 'raio_1km'

/**
 * O `title` do botão do relatório completo (DEC-074, Emenda 4): nomeia o recorte quando o
 * ponto veio de outro alcance. Um botão que promete "1,0 km" e entrega 5 min de carro (ou o
 * contrário) é a confusão do relato do Vinicius.
 */
export function dicaDoRelatorioCompleto(alcance: Alcance | undefined): string {
  if (!foraDoRaioPadrao(alcance)) return DICA_RELATORIO_COMPLETO
  return (
    `Relatório Pontual Censitário no recorte da ficha (${rotuloDoRecorteDoRelatorio(alcance)}), ` +
    'com fotos, dados do imóvel e os números da viabilidade'
  )
}

/**
 * A linha VISÍVEL sob o botão do relatório completo, só fora do raio de 1 km (`null` nele).
 *
 * `title` não aparece no toque nem em todo navegador; o recorte que muda o PDF tem de estar
 * escrito na tela. A linha diz também o que NÃO muda com ele, cada um por razão própria: a
 * conta financeira é do imóvel; a zona morta lê a captação própria de 1,5 km em volta do
 * ponto (DEC-042); a sugestão de demanda é do modelo de praça, treinado na isócrona de 10 min
 * de carro (DEC-078) — trocá-la pelo recorte seria usar o modelo fora do que ele aprendeu.
 */
export function avisoDoRecorteDoRelatorio(alcance: Alcance | undefined): string | null {
  if (!foraDoRaioPadrao(alcance)) return null
  return (
    `O relatório completo sai no recorte da ficha do ponto: ${rotuloDoRecorteDoRelatorio(alcance)}. ` +
    'A conta financeira, a zona morta (captação própria de 1,5 km) e a sugestão de demanda ' +
    '(10 min de carro, do modelo de praça) não mudam com ele.'
  )
}
