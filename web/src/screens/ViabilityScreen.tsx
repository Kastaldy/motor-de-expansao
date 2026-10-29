import { useEffect, useRef, useState } from 'react'

import type { PontoEscolhido } from '../App'
import BotaoInicio from '../components/BotaoInicio'
import CampoNumero from '../components/CampoNumero'
import {
  CascataDre,
  FluxoCaixa,
  FluxoCaixaOperacional,
  RampaAlunos,
  ReguaBreakEven,
  Veredito,
} from '../components/ViabilityCharts'
import { NotasMetodologicas } from '../components/ViabilityNotes'
import { Aviso, Botao, Eyebrow, Glass, Kpi, Spinner } from '../components/primitives'
import { api, ApiError, baixar } from '../lib/api'
import { TEXTO_SEM_DADO } from '../lib/constants'
import { coordenadaDoEstudo } from '../lib/coord'
import {
  alunos,
  brl,
  brlCurto,
  coord,
  definirExibicaoMonetaria,
  num,
  pctFrac,
  rotuloMes,
} from '../lib/format'
import {
  aluguelDeReferencia,
  diferencaPct,
  ROTULO_SELETOR_TIPO_IMOVEL,
  ROTULO_TIPO_IMOVEL,
  textoDaBase,
  textoDaDiferenca,
  TIPO_IMOVEL_PADRAO,
  TIPOS_IMOVEL_ALUGUEL,
  type AluguelReferencia,
  type TipoImovelAluguel,
} from '../lib/aluguel-referencia'
import { formatarNumero } from '../lib/mascara'
import {
  ESTILO_ROTULO_ALCANCE,
  ESTILO_TRILHO_ALCANCE,
  estiloDaOpcaoAlcance,
} from '../lib/seletor-alcance'
import {
  avisoDoRecorteDoRelatorio,
  dicaDoRelatorioCompleto,
  infoImovelParaPdf,
  parametrosRelatorioPontual,
  rotuloDoRecorteDoRelatorio,
} from '../lib/report'
import {
  clampNStudios,
  definirTicketStudio,
  TICKETS_STUDIO_PADRAO,
  ticketsAtivos,
} from '../lib/studios'
import { avisoDeViabilidade, sementeDaDemanda } from '../lib/viabilidade-demanda'
import {
  avisosV2,
  camposDeV2,
  corpoSugestaoV2,
  motivoV2,
  sementeDaDemandaV2,
  sugestaoValePara,
  v2Disponivel,
} from '../lib/viabilidade-demanda-v2'
import {
  ajudaDaRampa,
  mesFimDaRampa,
  passoPico,
  picoExibido,
  picoParaEnviar,
  rotuloPico,
  type MesPicoRampa,
} from '../lib/viabilidade-rampa'
import {
  type ChaveComLimite,
  LIMITES_DO_MOTOR,
  foraDaFaixa,
} from '../lib/viabilidade-limites'
import {
  fracaoDoPercentual,
  moedaDeViabilidade,
  paraReais,
  reaisPorUnidade,
  trocarDeMoeda,
  type MoedaDeEntrada,
} from '../lib/viabilidade-moeda'
import type {
  DemandaV2Out,
  EstadoDemandaV2,
  FaixaAlunos,
  InfoImovel,
  MunicipioPayload,
  ViabilidadeIn,
  ViabilidadeOut,
} from '../lib/types'

export interface ViabilityScreenProps {
  ponto: PontoEscolhido | null
  dados: MunicipioPayload | null
  onVoltar: () => void
  /** Volta ao menu de modos. Não limpa nada — ver `components/BotaoInicio`. */
  onInicio: () => void
  /**
   * De onde o operador veio, para o breadcrumb e o botão de volta dizerem a verdade.
   * O ponto chega aqui por dois caminhos — clique num hexágono do mapa ou "Mais
   * detalhes" na ficha do modo de ponto — e escrever "vindo do mapa" nos dois casos
   * mandaria metade dos operadores para uma tela em que eles não estavam.
   */
  origemRotulo?: string
}

const DEMANDA_PASSO = 100

/**
 * Ticket de MUSCULAÇÃO padrão (mensalidade do balcão, R$/mês). Desde 2026-10-05 ele
 * NÃO depende do número de studios — antes a tela o subia na escada 147/157/167/177 a
 * cada studio. Cada studio agora tem ticket próprio (ver `lib/studios.ts`).
 */
const TICKET_MUSCULACAO_PADRAO = 147

/**
 * FALLBACKS das réguas do veredito, usados SÓ enquanto o payload não chegou (primeiro
 * render) — os números oficiais vêm em `premissas.payback_viavel_max` e
 * `premissas.margem_viavel_min`, servidos da fonte única (`dimensionamento/config.py`).
 * Se a régua mudar lá, a tela acompanha sozinha; estes valores nunca prevalecem sobre
 * o payload. Quem dá o veredito é o motor (`dre.flag_viavel`).
 */
const PAYBACK_ALVO_MESES = 36
const MARGEM_VIAVEL_MIN_FALLBACK = 0.3

/**
 * Quanto o cheque total pode passar do aporte inicial antes de virar aviso. Acima
 * disto a diferença é dinheiro que o investidor precisa TER e que o contrato não
 * pede — o caso de referência bate 1,50x. Limiar de EXIBIÇÃO, não de cálculo.
 */
const CHEQUE_AVISO_RAZAO = 1.2

/* ---------------------------------------------------------------------------
   PLACEHOLDER DOS CAMPOS OPCIONAIS DO INVESTIMENTO.

   Regra dura: placeholder NUNCA afirma um padrão que não foi verificado no
   backend — placeholder que mente é pior que placeholder ausente (já houve uma
   reversão por causa disso).

   A fonte mais honesta é o PRÓPRIO PAYLOAD do último cálculo: `investimento.*` e
   `premissas.*` trazem o valor que o motor realmente usou, e acompanham sozinhos
   qualquer mudança no `config.py`. Antes do primeiro cálculo não há payload, e aí
   só entram os padrões PROVADOS abaixo; o resto fica no texto neutro.

   As citações abaixo são por SÍMBOLO, não por número de linha: a main andou três
   vezes durante este PR e toda linha citada derivou. Bloco que se intitula
   "conferido" com número errado é pior que bloco nenhum — afirma uma verificação
   que não vale mais.

   PADRÃO DO MOTOR (o campo vazio entrega exatamente este número):
     parcelas_obra = 4              `_investimento` em web/server/app.py, via
                                    SIM_PARCELAS_OBRA_DEFAULT (dimensionamento/config.py)
     parcelas_franquia = 4          idem, SIM_PARCELAS_FRANQUIA_DEFAULT
     taxa_franquia = 160.000        `_investimento`, via SIM_TAXA_FRANQUIA. Único que
                                    usa `is None`, então digitar 0 é honrado como zero
     carencia = 0                   entra por `opcionais` (None é filtrado) e cai no
                                    default da dataclass `Premissas`, SIM_CARENCIA_ALUGUEL_MESES
     taxa_minima_negocio = 25% a.a. mesmo caminho, SIM_TAXA_MINIMA_NEGOCIO_AA
     obra = 1.500.000               `investimento_do_body`, via SIM_OBRA_DEFAULT
     equipamentos = 1.200.000       idem, SIM_EQUIPAMENTOS_DEFAULT
     prazo_equipamentos = 36        idem, SIM_PRAZO_EQUIPAMENTOS_DEFAULT (0 se o
                                    equipamento digitado for 0)
     juros_equipamentos_am = 1,8%   idem, SIM_JUROS_EQUIPAMENTOS_AM_DEFAULT
   Os quatro últimos têm padrão PRÓPRIO desde 2026-10-28 (decisão de Felipe). Até ali
   eram só SUGESTÃO: com obra e equipamentos vazios o motor usava um CAPEX único de
   2.340.000 sem financiamento, preencher um zerava o outro e o juros vazio era 0% —
   digitar o número cinza mudava o payback (Campinas: 52 -> 39 meses só de confirmar a
   obra). Valor digitado, inclusive 0, é honrado.
   --------------------------------------------------------------------------- */
const PADRAO_PARCELAS_OBRA = '4'
const PADRAO_PARCELAS_FRANQUIA = '4'
const PADRAO_TAXA_FRANQUIA = '160.000'
const PADRAO_CARENCIA = '0'
const PADRAO_TAXA_NEGOCIO = '25'
/** % de balcão do motor (`SIM_SHARE_BALCAO` = 0,69). RESERVA até o payload chegar:
 *  depois do 1º cálculo a caixa mostra o `premissas.share_balcao` realmente usado. */
const PADRAO_PCT_BALCAO = '69'

/* Os quatro padrões do investimento abaixo TÊM de casar com o config do motor
   (SIM_OBRA_DEFAULT, SIM_EQUIPAMENTOS_DEFAULT, SIM_PRAZO_EQUIPAMENTOS_DEFAULT,
   SIM_JUROS_EQUIPAMENTOS_AM_DEFAULT): é o número que o campo vazio entrega. Ficam FIXOS
   na caixa (via `fixa`), e não pelo eco do payload: o eco anunciaria o número DIGITADO
   como se fosse o padrão. */
const PADRAO_OBRA = '1.500.000'
const PADRAO_EQUIPAMENTOS = '1.200.000'
const PADRAO_PRAZO_EQUIP = '36'
/** Os MESMOS padrões acima, em número (reais): onde o operador escolhe a moeda, a caixa
 *  mostra o valor CONVERTIDO em vez do texto em reais. */
const PADRAO_OBRA_REAIS = 1_500_000
const PADRAO_EQUIPAMENTOS_REAIS = 1_200_000
const PADRAO_TAXA_FRANQUIA_REAIS = 160_000
const PADRAO_JUROS_EQUIP = '1,8'

/**
 * Placeholder = valor usado pelo motor no último cálculo; sem cálculo ainda, o texto
 * de reserva do chamador. Formatado por `formatarNumero` (e não por `num`) de
 * propósito: é a MESMA grafia que o campo mostraria se o número fosse digitado — sem
 * zero à direita, com a mesma vírgula.
 *
 * Serve às parcelas, taxa de franquia, carência e taxa mínima. Os quatro campos do
 * investimento (obra, equipamentos, prazo, juros) usam `fixa()`.
 */
function dica(usado: number | null | undefined, reserva: string, casas = 0): string {
  return formatarNumero(usado, casas) || reserva
}

/**
 * Placeholder que NÃO ecoa o motor: o padrão fica de pé antes e depois do cálculo.
 *
 * Nos quatro campos do investimento o eco engana: com a obra digitada, o prazo vazio e
 * o equipamento em 0, o motor devolve prazo 0, e a caixa passaria a anunciar 0 como
 * padrão. O número fixo é o padrão do config (ver o bloco acima).
 */
function fixa(padrao: string): string {
  return padrao
}

/** Aluguel do vazio quando a instância não tem a base de imóveis (o padrão de antes da DEC-080). */
const ALUGUEL_SEM_BASE_REAIS = 20_000

/**
 * O SELETOR DO TIPO DO IMÓVEL (DEC-080), no mesmo visual do seletor de alcance da ficha do
 * ponto (DEC-074): controle segmentado, marcado CHEIO. Trocar o tipo troca a régua de aluguel.
 */
function SeletorTipoImovel({
  atual,
  onTrocar,
}: {
  atual: TipoImovelAluguel
  onTrocar: (tipo: TipoImovelAluguel) => void
}) {
  return (
    <div style={{ display: 'grid', gap: 6, marginBottom: 10 }}>
      <span id="rotulo-tipo-imovel" style={ESTILO_ROTULO_ALCANCE}>
        {ROTULO_SELETOR_TIPO_IMOVEL}
      </span>
      <div role="radiogroup" aria-labelledby="rotulo-tipo-imovel" style={ESTILO_TRILHO_ALCANCE}>
        {TIPOS_IMOVEL_ALUGUEL.map((t) => {
          const marcado = t === atual
          return (
            <button
              key={t}
              type="button"
              role="radio"
              aria-checked={marcado}
              onClick={() => onTrocar(t)}
              style={estiloDaOpcaoAlcance(marcado)}
            >
              {ROTULO_TIPO_IMOVEL[t]}
            </button>
          )
        })}
      </div>
    </div>
  )
}

/**
 * O QUADRO DO ALUGUEL DE REFERÊNCIA (DEC-080): o R$/m² e o aluguel para a metragem, a base
 * em fato neutro (sem selo, sem fonte, sem data) e, com o aluguel digitado, a comparação.
 */
function QuadroAluguelReferencia({
  referencia,
  m2,
  aluguelDigitado,
}: {
  referencia: AluguelReferencia | null
  m2: number
  aluguelDigitado: number | null
}) {
  const valor = aluguelDeReferencia(referencia, m2)
  if (!referencia || valor == null) return null
  const pct = diferencaPct(aluguelDigitado, valor)
  return (
    <div
      style={{
        marginTop: 10,
        padding: '10px 12px',
        borderRadius: 10,
        border: '1px solid var(--line-soft)',
        background: 'var(--surf-chip)',
        display: 'grid',
        gap: 4,
      }}
    >
      <span style={{ font: '600 11px/1.3 var(--f-ui)', color: 'var(--tx-sub)' }}>
        Aluguel de referência
      </span>
      <span style={{ font: '700 14px/1.3 var(--f-ui)', color: 'var(--tx-strong)' }}>
        {brl(referencia.rs_m2, false, 2)}/m² · {brl(valor)}/mês para {num(m2)} m²
      </span>
      <span style={{ font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>
        {textoDaBase(referencia)}
      </span>
      {pct != null && aluguelDigitado != null && (
        <span
          style={{
            font: `${pct > 0 ? 700 : 600} 12.5px/1.4 var(--f-ui)`,
            color: pct > 0 ? 'var(--neg-forte)' : 'var(--pos-text)',
            whiteSpace: 'nowrap',
          }}
        >
          Seu aluguel: {textoDaDiferenca(pct)}
        </span>
      )}
    </div>
  )
}

export default function ViabilityScreen({
  ponto,
  onVoltar,
  onInicio,
  origemRotulo = 'mapa',
}: ViabilityScreenProps) {
  // --- Cenário -------------------------------------------------------------
  const [m2, setM2] = useState(1500)
  // Instância cujo perfil declara os dois câmbios (hoje a AR): o operador escolhe a
  // moeda do imóvel — a do país ou dólares —, digita e lê tudo nela. A conta segue em
  // REAIS: a conversão acontece por trás (lib/viabilidade-moeda.ts). Sem câmbio no
  // perfil (Brasil), `moedaLocal` é null e a tela é a de sempre, em reais.
  const moedaLocal = moedaDeViabilidade()
  const [moedaEntrada, setMoedaEntrada] = useState<MoedaDeEntrada>('local')
  /** Reais por unidade da moeda em que o operador digita (1 = reais). */
  const reaisPorUn = moedaLocal ? reaisPorUnidade(moedaLocal, moedaEntrada) : 1
  /** Símbolo da moeda de entrada — o mesmo dos resultados. */
  const simbolo = !moedaLocal ? 'R$' : moedaEntrada === 'usd' ? 'US$' : moedaLocal.simbolo
  const nomeMoeda = !moedaLocal ? 'reais' : moedaEntrada === 'usd' ? 'dólares' : moedaLocal.codigo
  // Os valores do motor chegam em reais; `brl`/`brlCurto` os mostram na moeda
  // escolhida. Definido DURANTE o render (e não em efeito) para os componentes filhos
  // já pintarem certo na mesma passada; o efeito mais abaixo desliga ao sair da tela.
  definirExibicaoMonetaria(moedaLocal ? { simbolo, porReal: 1 / reaisPorUn } : null)
  // Com seletor de moeda o aluguel abre VAZIO: R$ 20.000 lido como US$ 20.000 seria
  // um número que ninguém escolheu (a mesma família do 800 da demanda).
  //
  // DEC-080: no Brasil o aluguel também abre VAZIO, e o vazio vale o ALUGUEL DE REFERÊNCIA
  // (metragem × R$/m² mediano dos anúncios do município e do tipo do imóvel) — o mesmo
  // número que a caixa mostra em cinza e o que vai para a conta (regra da DEC-079). Sem a
  // base de imóveis na instância, o vazio segue valendo os R$ 20.000 de antes.
  const [aluguel, setAluguel] = useState<number | undefined>(undefined)
  const [tipoImovel, setTipoImovel] = useState<TipoImovelAluguel>(TIPO_IMOVEL_PADRAO)
  const [refAluguel, setRefAluguel] = useState<AluguelReferencia | null>(null)
  /** A referência mais recente, lida por `calcular` logo após a busca (o estado só chega
   *  no próximo render, e a conta da chegada ao ponto sairia com a referência velha). */
  const refAluguelAgora = useRef<AluguelReferencia | null>(null)
  const aluguelDigitadoReais = paraReais(aluguel, reaisPorUn)
  const aluguelRefReais = moedaLocal ? null : aluguelDeReferencia(refAluguel, m2)
  /** O aluguel que entra na conta: o digitado; vazio, a referência (só no Brasil). */
  function aluguelDaConta(): number | null {
    if (aluguelDigitadoReais != null) return aluguelDigitadoReais
    if (moedaLocal) return null
    return aluguelDeReferencia(refAluguelAgora.current, m2) ?? ALUGUEL_SEM_BASE_REAIS
  }
  const aluguelReais = aluguelDaConta()
  /** Valor em reais escrito na moeda escolhida, para o texto de uma caixa vazia. */
  const naMoeda = (reais: number) => formatarNumero(Math.round(reais / reaisPorUn), 0)
  // Ticket de MUSCULAÇÃO = mensalidade R$/mês do plano de balcão (P2-12). O ticket
  // médio (blended, com o mix de agregadores e studios) é somente-leitura e vem do
  // motor, e INDEPENDE do número de studios desde a DEC-068.
  //
  // ESTA LINHA ERA `useState(TICKET_POR_STUDIO[0])`, de uma escada
  // `[147, 157, 167, 177]` que a DEC-068 (#442) revogou — e o `onChange` de Studios
  // reescrevia o ticket com ela quando `!moedaLocal`, ou seja NO BRASIL. Trazer este PR
  // sem desfazer isso reverteria a decisão na instância BR, em silêncio.
  const [ticket, setTicket] = useState<number>(TICKET_MUSCULACAO_PADRAO)
  // Com seletor de moeda o ticket é digitado na moeda escolhida e abre VAZIO: converter
  // o ticket brasileiro e chamar de padrão seria repetir o erro do 800.
  const [ticketLocal, setTicketLocal] = useState<number | undefined>(undefined)
  const ticketLocalReais = paraReais(ticketLocal, reaisPorUn)
  /** Ticket em REAIS que entra na conta. */
  const ticketDaConta = moedaLocal ? ticketLocalReais : ticket
  /** Falta alguma premissa em dinheiro sem a qual não há conta (ticket ou aluguel). */
  const faltaTicket =
    moedaLocal != null && (!ticketLocalReais || ticketLocalReais <= 0 || aluguelReais == null)
  // Mix recorrente × agregador, em % de balcão. Vazio = padrão do motor. Só é editável
  // onde o perfil declara as premissas como provisórias (o aviso); no Brasil o mix tem
  // dono e segue somente-leitura.
  const mixEditavel = avisoDeViabilidade() != null
  const [pctBalcao, setPctBalcao] = useState<number | undefined>(undefined)
  // `null` = ainda sem premissa. Nascia em 800, e numa instância sem faixa de
  // comparáveis o 800 sobrava e a tela calculava sozinha com ele. Agora, sem p50, a
  // tela pede o número ao operador (regra em lib/viabilidade-demanda.ts).
  const [demanda, setDemanda] = useState<number | null>(null)
  // A demanda vem padronizada no p50 da metragem e re-escala quando a metragem
  // muda — até o operador mexer no ±, aí a mão dele prevalece (DEC-009: premissa).
  const [demandaTocada, setDemandaTocada] = useState(false)
  const [faixa, setFaixa] = useState<FaixaAlunos | null>(null)
  // A busca da faixa já respondeu (com ou sem p50)? Só depois disso a tela pode
  // afirmar "sem comparáveis" e trocar o número pelo campo de digitação.
  const [faixaBuscada, setFaixaBuscada] = useState(false)
  // Viabilidade v2 (DEC-078 ampliada): o SERVIDOR diz se ela está disponível; só então a
  // demanda é semeada pelo p50 dela (editável, mesma `demandaTocada`). Indisponível ou
  // com erro -> o modo densidade de sempre, com o motivo discreto.
  const [estadoV2, setEstadoV2] = useState<EstadoDemandaV2 | null>(null)
  const [sugestaoV2, setSugestaoV2] = useState<DemandaV2Out | null>(null)
  const [erroV2, setErroV2] = useState<string | null>(null)
  // Rampa de maturação (DEC-078, emendas de 21 e 22/10/2026): só a curva observada, com o PICO
  // DE MATURAÇÃO escolhido pelo operador; `null` = sem escolha, e então o pedido vai sem
  // `mes_pico_rampa` e vale o pico observado (padrão do SERVIDOR). A forma não é mais
  // escolha da tela: o pedido não manda `forma_rampa`.
  const [picoRampa, setPicoRampa] = useState<MesPicoRampa | null>(null)
  // Studios (0..3): cada um atende uma fatia da demanda com ticket PRÓPRIO e soma um
  // custo fixo mensal (valores do motor). O estado dos tickets guarda SEMPRE as três
  // posições: baixar de 3 para 1 e voltar devolve o que o operador já digitou.
  const [nStudios, setNStudios] = useState(0)
  const [ticketsStudios, setTicketsStudios] = useState<number[]>(() => [
    ...TICKETS_STUDIO_PADRAO,
  ])

  // --- Investimento: Obra (equity) x Equipamentos (financiado) --------------
  // OS NOVE CAMPOS GUARDAM `number | undefined`, e nao mais texto cru: a mascara viva
  // (CampoNumero) e' quem le a digitacao, entao o estado ja' recebe o NUMERO. O que se
  // preserva palavra por palavra e' a semantica do vazio: `undefined` -> a chave nao
  // entra no payload (JSON.stringify omite `undefined`) -> Pydantic ve None -> o motor
  // aplica O PADRAO DELE. Vazio nunca pode virar 0: em taxa_franquia o backend usa
  // `is None` (app.py:1372) e um 0 digitado vale R$ 0 de verdade, e em parcelas/prazo
  // o 0 e' barrado por `gt=0`/`ge=1` e volta 422.
  // Obra = desembolso do franqueado, parcelado sem juros (base do ROIC/payback).
  const [obra, setObra] = useState<number | undefined>(undefined)
  const [parcelasObra, setParcelasObra] = useState<number | undefined>(undefined)
  // Equipamentos = financiado (prazo em meses + juros a.m.); a PMT entra abaixo do
  // EBITDA (dilui no tempo, melhora o payback).
  const [equip, setEquip] = useState<number | undefined>(undefined)
  const [prazoEquip, setPrazoEquip] = useState<number | undefined>(undefined)
  const [jurosEquip, setJurosEquip] = useState<number | undefined>(undefined)
  // Carência de aluguel: meses iniciais sem pagar aluguel (melhora payback/FCF).
  const [carencia, setCarencia] = useState<number | undefined>(undefined)
  // Taxa de franquia: R$160.000 é o padrão do motor, mas o operador pode sobrescrever
  // (decisão de Felipe, FIN-VIAB-01). Vazio = padrão; o payload devolve o valor usado.
  const [taxaFranquia, setTaxaFranquia] = useState<number | undefined>(undefined)
  // Parcelas da taxa de franquia: 4x SEM JUROS por decisão de Felipe (2026-07-24).
  // Antes a taxa saía INTEIRA do caixa no M-4. Vazio = padrão do motor (4). É só
  // timing de caixa: mexe em TIR/VPL, não em EBITDA, margem ou break-even.
  const [parcelasFranquia, setParcelasFranquia] = useState<number | undefined>(undefined)
  // Taxa mínima do NEGÓCIO (% a.a.) — a ÚNICA taxa configurável. Vazio = padrão do
  // motor (25% a.a.). A taxa mínima do SÓCIO NÃO tem campo: ela é DERIVADA dentro do
  // motor, o que torna impossível digitar uma taxa de sócio abaixo do custo da dívida.
  const [taxaNegocio, setTaxaNegocio] = useState<number | undefined>(undefined)

  // --- Dados opcionais do imóvel (entram no PDF completo) ------------------
  const [info, setInfo] = useState<InfoImovel>({})
  const [fotos, setFotos] = useState<File[]>([])

  const [res, setRes] = useState<ViabilidadeOut | null>(null)
  const [calculando, setCalculando] = useState(false)
  const [gerandoPdf, setGerandoPdf] = useState(false)
  const [gerandoXlsx, setGerandoXlsx] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const inputFoto = useRef<HTMLInputElement>(null)

  // Coordenada do estudo: a EXATA quando o ponto veio da busca; o centroide do hexágono
  // só quando ele veio do clique no ranking (aí é a única que existe). Ver PontoEscolhido.
  const alvo = ponto ? coordenadaDoEstudo(ponto) : null
  const alvoLat = alvo?.lat
  const alvoLng = alvo?.lng

  /** Tickets de studio ativos, em REAIS (a mesma conversão do pedido da viabilidade). */
  function ticketsStudiosEmReais(): number[] {
    return ticketsAtivos(ticketsStudios, nStudios).map((t) => paraReais(t, reaisPorUn) ?? t)
  }

  /** Pede a sugestão da v2 para o cenário atual. Falha -> `null` e o motivo na tela. */
  async function pedirSugestaoV2(): Promise<DemandaV2Out | null> {
    if (alvoLat == null || alvoLng == null) return null
    try {
      const s = await api.demandaV2(
        corpoSugestaoV2({
          lat: alvoLat,
          lng: alvoLng,
          m2,
          ticket: ticketDaConta,
          shareBalcao: mixEditavel ? fracaoDoPercentual(pctBalcao) : undefined,
          ticketsStudios: ticketsStudiosEmReais(),
        }),
      )
      setSugestaoV2(s)
      setErroV2(null)
      return s
    } catch (e) {
      setSugestaoV2(null)
      setErroV2(e instanceof ApiError ? e.message : 'O modelo de praça não respondeu.')
      return null
    }
  }

  /** Régua de aluguel do ponto para o tipo (DEC-080); `null` sem base ou sem resposta. */
  async function buscarReferencia(tipo: TipoImovelAluguel): Promise<AluguelReferencia | null> {
    return api.aluguelReferencia(tipo, ponto?.uf, ponto?.municipio).catch(() => null)
  }

  /** Troca o tipo do imóvel: troca a régua e, com o aluguel vazio, o aluguel da conta. */
  async function trocarTipoImovel(tipo: TipoImovelAluguel) {
    setTipoImovel(tipo)
    const r = await buscarReferencia(tipo)
    refAluguelAgora.current = r
    setRefAluguel(r)
  }

  function montarPayload(
    demandaUsar: number,
    sug: DemandaV2Out | null = sugestaoV2,
  ): ViabilidadeIn {
    return {
      // Modo v2 só com sugestão válida para a metragem e os estúdios de agora; sem ela,
      // o pedido sai como sempre (modo densidade) e nada muda.
      ...camposDeV2(sug, { lat: alvoLat, lng: alvoLng, m2, nStudios }),
      lat: alvoLat!,
      lng: alvoLng!,
      m2,
      // Tudo que é dinheiro vai ao motor em REAIS (fator 1 onde a tela já é em reais).
      aluguel: aluguelDaConta() ?? 0,
      ticket: ticketDaConta,
      // % digitado -> FRAÇÃO (o contrato). Vazio some do JSON e o motor usa o padrão.
      share_balcao: mixEditavel ? fracaoDoPercentual(pctBalcao) : undefined,
      demanda: demandaUsar,
      n_studios: nStudios,
      // Um ticket por studio ATIVO (o backend devolve 422 se o tamanho divergir), na
      // MESMA moeda dos outros campos de dinheiro. Sem `paraReais` aqui, um ticket
      // digitado em pesos entrava no motor como se fosse real.
      tickets_studios: ticketsAtivos(ticketsStudios, nStudios).map(
        (t) => paraReais(t, reaisPorUn) ?? t,
      ),
      obra: paraReais(obra, reaisPorUn),
      parcelas_obra: parcelasObra,
      equipamentos: paraReais(equip, reaisPorUn),
      prazo_equipamentos: prazoEquip,
      // % a.m. digitado -> FRAÇÃO (o contrato do payload). Conversão de UNIDADE; não é
      // derivação de número financeiro. `undefined` atravessa intacto para a chave
      // sumir do JSON — dividir `undefined` por 100 daria NaN e viraria `null`.
      juros_equipamentos_am: jurosEquip !== undefined ? jurosEquip / 100 : undefined,
      carencia_aluguel_meses: carencia,
      mes_pico_rampa: picoParaEnviar(picoRampa),
      taxa_franquia: paraReais(taxaFranquia, reaisPorUn),
      parcelas_franquia: parcelasFranquia,
      // % a.a. digitado -> FRAÇÃO, mesma conversão de unidade.
      taxa_minima_negocio_aa: taxaNegocio !== undefined ? taxaNegocio / 100 : undefined,
    }
  }

  // O backend recusa ticket de studio <= 0 (422), e o detalhe do 422 chega como lista —
  // viraria "[object Object]" na tela. Barra antes, com mensagem em português.
  function erroTicketsStudios(): string | null {
    const i = ticketsAtivos(ticketsStudios, nStudios).findIndex((t) => !(t > 0))
    return i < 0 ? null : `O ticket do studio ${i + 1} precisa ser maior que zero.`
  }

  /**
   * Campos de faixa fora do que o motor aceita.
   *
   * `CampoNumero` DOCUMENTA que `min`/`max` nativos nunca impediram digitação (eles só
   * valem para as setas), então `min={1}` em "Parcelas franquia" não impede digitar
   * `0` — e foi assim que um operador levou um 422 em 2026-10-13. Barra aqui, com o
   * nome do campo e a faixa, em vez de deixar o motor recusar.
   *
   * ZERO NÃO VIRA VAZIO de propósito: "vazio usa o padrão do modelo" e `0` é um número
   * que a pessoa digitou. Reinterpretar um pelo outro em silêncio é a família de
   * defeito que este repo mais repete.
   */
  function erroDeFaixa(demandaUsar: number | null): string | null {
    const valores: Record<ChaveComLimite, number | undefined> = {
      m2,
      // A demanda vem por ARGUMENTO porque `calcular` aceita uma diferente da do
      // estado (`montarPayload(demandaUsar)`): checar o estado deixaria passar
      // exatamente o número que vai ao motor.
      demanda: demandaUsar ?? undefined,
      parcelas_obra: parcelasObra,
      parcelas_franquia: parcelasFranquia,
      prazo_equipamentos: prazoEquip,
    }
    for (const chave of Object.keys(LIMITES_DO_MOTOR) as ChaveComLimite[]) {
      const fora = foraDaFaixa(valores[chave], LIMITES_DO_MOTOR[chave])
      if (fora) return fora
    }
    return null
  }

  async function calcular(
    demandaUsar: number | null = demanda,
    sug: DemandaV2Out | null = sugestaoV2,
  ) {
    // AS TRES guardas, e nenhuma substitui a outra: demanda ausente e ticket nao
    // convertivel sao deste PR; ticket de studio <= 0 e' da DEC-068. Escolher um lado
    // aqui compila limpo e reabre o buraco que o outro tapava.
    if (!ponto || demandaUsar == null || faltaTicket) return
    const erroStudios = erroTicketsStudios() ?? erroDeFaixa(demandaUsar)
    if (erroStudios) {
      setErro(erroStudios)
      return
    }
    setCalculando(true)
    setErro(null)
    try {
      const r = await api.viabilidade(montarPayload(demandaUsar, sug))
      setRes(r)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao calcular a viabilidade.')
    } finally {
      setCalculando(false)
    }
  }

  // Ao sair da tela, `brl`/`brlCurto` voltam ao símbolo do país para o resto do app.
  // (Religa no próprio efeito para sobreviver à montagem dupla do StrictMode.)
  useEffect(() => {
    definirExibicaoMonetaria(moedaLocal ? { simbolo, porReal: 1 / reaisPorUn } : null)
    return () => definirExibicaoMonetaria(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [simbolo, reaisPorUn])

  /** Troca a moeda do seletor reescrevendo o que já foi digitado: o cenário é o mesmo. */
  function trocarMoeda(nova: MoedaDeEntrada) {
    if (!moedaLocal || nova === moedaEntrada) return
    const de = reaisPorUn
    const para = reaisPorUnidade(moedaLocal, nova)
    const casasTicket = nova === 'usd' ? 2 : 0
    setTicketLocal((v) => trocarDeMoeda(v, de, para, casasTicket))
    // Os tickets de studio sao dinheiro como os outros: sem reescrever, trocar de
    // dólares para pesos deixaria `157` como 157 PESOS, outro cenario com o mesmo numero.
    setTicketsStudios((ts) => ts.map((v) => trocarDeMoeda(v, de, para, casasTicket) ?? v))
    setAluguel((v) => trocarDeMoeda(v, de, para))
    setObra((v) => trocarDeMoeda(v, de, para))
    setEquip((v) => trocarDeMoeda(v, de, para))
    setTaxaFranquia((v) => trocarDeMoeda(v, de, para))
    setMoedaEntrada(nova)
  }

  // Ao chegar num ponto: busca a faixa da metragem, semeia a demanda no p50 e
  // calcula. Sem p50 (instância sem base de comparáveis, ou a busca falhou) e sem
  // demanda anterior, NÃO calcula: o campo fica vazio e a tela pede a premissa.
  useEffect(() => {
    if (!ponto) return
    let vivo = true
    setDemandaTocada(false)
    // A tela NÃO é remontada ao trocar de ponto: a sugestão da v2 do ponto anterior
    // morre aqui, antes de a nova chegar, senão PDF/planilha levariam o token velho.
    setSugestaoV2(null)
    ;(async () => {
      let seed = demanda
      if (!moedaLocal) {
        const r = await buscarReferencia(tipoImovel)
        if (!vivo) return
        refAluguelAgora.current = r
        setRefAluguel(r)
      }
      try {
        const f = await api.faixaAlunos(m2)
        if (!vivo) return
        setFaixa(f)
        seed = sementeDaDemanda(f.p50, demanda)
      } catch {
        /* sem faixa: mantém a demanda atual */
      }
      // v2: o servidor decide. Disponível -> a semente é o p50 da v2 (a faixa de
      // comparáveis segue buscada, como referência e para o modo densidade).
      let sug: DemandaV2Out | null = null
      let estado = estadoV2
      if (estado == null) {
        estado = await api.demandaV2Estado().catch(() => null)
        if (!vivo) return
        setEstadoV2(estado)
      }
      if (v2Disponivel(estado)) {
        sug = await pedirSugestaoV2()
        if (!vivo) return
        seed = sementeDaDemandaV2(sug) ?? seed
      }
      if (vivo) {
        setFaixaBuscada(true)
        setDemanda(seed)
        void calcular(seed, sug)
      }
    })()
    return () => {
      vivo = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ponto?.hex.id])

  // Metragem mudou: re-busca a faixa e re-semeia a demanda no novo p50 (a menos
  // que o operador já tenha fixado um valor manual nesta metragem).
  useEffect(() => {
    let vivo = true
    const t = setTimeout(async () => {
      try {
        const f = await api.faixaAlunos(m2)
        if (!vivo) return
        setFaixa(f)
        // Com a v2 disponível quem ressemeia é o efeito da v2 (abaixo), não a faixa.
        if (!demandaTocada && f.p50 != null && !v2Disponivel(estadoV2)) {
          setDemanda(Math.round(f.p50))
        }
      } catch {
        /* ignora */
      }
    }, 350)
    return () => {
      vivo = false
      clearTimeout(t)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [m2])

  // v2: metragem, estúdios, tickets ou mix mudaram -> nova sugestão (o servidor reconverte
  // o faturamento previsto em alunos com as premissas novas). Ressemeia a demanda só
  // enquanto o operador não a tocou; tocada, a sugestão nova só atualiza a faixa e o token.
  // O PONTO exato entra na chave: trocar de endereço DENTRO do mesmo hexágono não remonta a
  // tela nem dispara o efeito da chegada (que olha o hex), e a sugestão velha ficava recusada
  // sem ninguém pedir outra.
  const chaveSugestaoV2 = [
    alvoLat,
    alvoLng,
    m2,
    nStudios,
    ticketDaConta,
    pctBalcao,
    ticketsStudiosEmReais().join(','),
  ].join('|')
  const primeiraChaveV2 = useRef<string | null>(null)
  useEffect(() => {
    if (!ponto || !v2Disponivel(estadoV2)) return
    // A sugestão da chegada ao ponto é do efeito acima; aqui só as MUDANÇAS.
    if (primeiraChaveV2.current == null) {
      primeiraChaveV2.current = chaveSugestaoV2
      return
    }
    if (primeiraChaveV2.current === chaveSugestaoV2) return
    primeiraChaveV2.current = chaveSugestaoV2
    let vivo = true
    const t = setTimeout(async () => {
      const s = await pedirSugestaoV2()
      if (!vivo) return
      // Sugestão falhou (ex.: serviço de rotas fora): volta à semente da densidade, como
      // a tela faria sem a v2 — nunca fica com a semente de uma metragem antiga.
      const semente = sementeDaDemandaV2(s) ?? (faixa?.p50 != null ? Math.round(faixa.p50) : null)
      if (!demandaTocada && semente != null) setDemanda(semente)
    }, 350)
    return () => {
      vivo = false
      clearTimeout(t)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chaveSugestaoV2, estadoV2])

  /** Sugestão da v2 que vale para o cenário de agora (`null` = modo densidade). */
  const v2Vigente = sugestaoValePara(sugestaoV2, { lat: alvoLat, lng: alvoLng, m2, nStudios })
    ? sugestaoV2
    : null
  const motivoDaV2 = motivoV2(estadoV2, erroV2)

  async function gerarPdf() {
    if (!ponto) return
    // Mesma guarda do calcular/gerarXlsx. Aqui ela importa ainda mais: o backend do PDF
    // valida os inputs dentro de um `except` e, com ticket de studio <= 0, o relatório
    // sairia SEM a seção de viabilidade e sem erro nenhum. Só vale quando o PDF leva a
    // viabilidade (`res`): sem cálculo, os tickets nem vão no pedido.
    const erroStudios = res ? (erroTicketsStudios() ?? erroDeFaixa(demanda)) : null
    if (erroStudios) {
      setErro(erroStudios)
      return
    }
    setGerandoPdf(true)
    setErro(null)
    try {
      const { blob, filename } = await api.relatorioPontual({
        // Coordenada do estudo + rótulo + AVISO DE ORIGEM (e, fora do raio de 1 km, o
        // ALCANCE da ficha — DEC-074, Emenda 4) saem prontos de
        // `parametrosRelatorioPontual` (lib/report.ts), que é onde essa decisão pode
        // ser testada. Ela responde às duas coisas pela MESMA regra de `lib/coord.ts`:
        // qual coordenada usar e se o PDF precisa avisar que ela é o CENTROIDE do
        // hexágono (a até ~1,5 km), e não um endereço. Aqui a tela só repassa.
        ...parametrosRelatorioPontual(ponto, { rotuloManual: info.nome }),
        // Metragem/aluguel vêm do Cenário e as chaves são remapeadas para o contrato
        // do PDF (senão o imóvel saía "n/d" mesmo preenchido — lib/report.ts).
        infoImovel: infoImovelParaPdf(info, { m2, aluguel: aluguelReais ?? 0 }),
        // SÓ os inputs do cenário: o backend roda o motor UMA vez e monta o payload
        // inteiro (números + gráficos) por conta própria. Não reenviamos o payload
        // calculado — ele tem 70 KB (série de 64 meses + grade) e estourava a query
        // string em HTTP 431. Ver o comentário em lib/api.ts::relatorioPontual.
        viabilidadeInputs:
          res && demanda != null && !faltaTicket ? montarPayload(demanda) : undefined,
        fotos,
      })
      baixar(blob, filename)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao gerar o relatório.')
    } finally {
      setGerandoPdf(false)
    }
  }

  /**
   * Baixa o simulador financeiro completo em Excel (fórmulas vivas). Manda os MESMOS
   * inputs do cenário — o servidor roda o motor uma vez e monta a planilha; a tela
   * não deriva nada. Mesmo padrão de carregando/erro do PDF.
   */
  async function gerarXlsx() {
    // As tres guardas, pela mesma razao do `calcular`.
    if (!ponto || demanda == null || faltaTicket) return
    const erroStudios = erroTicketsStudios() ?? erroDeFaixa(demanda)
    if (erroStudios) {
      setErro(erroStudios)
      return
    }
    setGerandoXlsx(true)
    setErro(null)
    try {
      const { blob, filename } = await api.simuladorXlsx(
        montarPayload(demanda),
        info.nome || ponto.rotulo,
      )
      baixar(blob, filename)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao gerar a planilha.')
    } finally {
      setGerandoXlsx(false)
    }
  }

  if (!ponto) {
    // Este é o estado em que o card "Analisar um ponto ou imóvel" cai HOJE: o campo de
    // colar link do Maps / coordenada é a etapa seguinte do épico. Até lá, o caminho
    // honesto é escolher o ponto pelo mapa — e daqui tem de dar para voltar ao menu,
    // senão o card vira beco sem saída.
    return (
      <Aviso
        titulo="Nenhum ponto escolhido ainda"
        corpo="A viabilidade testa um imóvel concreto. Escolha o ponto pelo mapa — chegue até a camada de recomendação e traga um hexágono para cá."
        acao={
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
            <Botao onClick={onVoltar}>Escolher pelo mapa</Botao>
            <Botao variante="ghost" onClick={onInicio}>
              Voltar ao início
            </Botao>
          </div>
        }
      />
    )
  }

  // Sem p50 a demanda é digitada: não há padrão a oferecer, só a premissa do operador.
  const semComparaveis = faixaBuscada && faixa?.p50 == null
  /** Aviso que o perfil do país declara para esta tela (ausente no Brasil). */
  const avisoPerfil = avisoDeViabilidade()
  /** Demanda que os quadros de leitura mostram: a do campo; se ele foi esvaziado
   *  depois de um cálculo, a que o motor usou. `null` = nada a comparar ainda. */
  const demandaExibida = demanda ?? res?.demanda_premissa ?? null
  /**
   * Não há resultado: NADA da área de resultado na tela.
   *
   * O `&&` que havia aqui (`!res && (demanda == null || faltaTicket)`) condicionava a
   * proteção a faltar TAMBÉM a premissa — e com premissa presente e cálculo falhado
   * acontecia exatamente o que o comentário original previa: cartões vazios dizendo
   * "não atinge" e o selo "Requer revisão de premissas" LIDOS COMO VEREDITO. Em
   * 2026-10-13 um operador recebeu um 422 e a tela afirmou "Fora da régua de
   * viabilidade" sobre um ponto onde o motor nunca rodou. Veredito sem conta é
   * resultado inventado — e um "reprovado" inventado custa mais que tela vazia.
   */
  const semResultado = !res
  /** ...e falta premissa para haver. SÓ escolhe o TEXTO do painel de espera. */
  const faltaPremissa = semResultado && (demanda == null || faltaTicket)

  // TUDO abaixo é LEITURA do viabilidade_payload_v1. A tela não deriva número
  // financeiro nenhum: o motor (dimensionamento/simulador.py) já entregou pronto.
  const premissas = res?.premissas ?? null
  // O seletor mostra o pico escolhido pelo operador ou, sem escolha, o que o servidor usou.
  const picoMostrado = picoExibido(picoRampa, premissas)
  // Studios lidos do PAYLOAD (o que o motor aplicou), não do estado da tela: o rótulo
  // descreve o último cálculo, e não o que está digitado e ainda não foi calculado.
  const temStudios = (premissas?.n_studios ?? 0) > 0
  /** Investimento REALMENTE usado pelo motor — a fonte honesta dos placeholders. */
  const inv = res?.investimento ?? null
  const dre = res?.dre ?? null
  const retorno = res?.retorno ?? null
  const serie = res?.serie_mensal ?? []
  /** margem EBITDA em FRAÇÃO (0,3873 = 38,73%) — o payload nunca manda percentual. */
  const margem = dre?.margem ?? null
  /** Break-even OPERACIONAL (EBITDA = 0), em alunos TOTAIS. */
  const beEbitda = res?.break_even.ebitda ?? null
  /** Break-even DE CAIXA (cobre também a PMT do financiamento), em alunos TOTAIS. */
  const beCaixa = res?.break_even.caixa ?? null
  /** Réguas do veredito servidas pelo motor; as constantes só cobrem o payload ausente. */
  const margemViavelMin = premissas?.margem_viavel_min ?? MARGEM_VIAVEL_MIN_FALLBACK
  const paybackViavelMax = premissas?.payback_viavel_max ?? PAYBACK_ALVO_MESES
  /** Horizonte da simulação (meses de operação), para rotular os cards sem cravar 60. */
  const horizonteMeses = premissas?.horizonte_meses ?? 60
  /**
   * Selo do veredito = o que o MOTOR decidiu (`dre.flag_viavel`: margem >=
   * margem_viavel_min E payback <= payback_viavel_max). A tela não re-deriva o
   * veredito: enquanto ela o derivava do break-even, o mesmo cenário saía "Aprovado
   * para comitê" aqui e "Viável? Não" no PDF, que lê o mesmo `flag_viavel`.
   * FALLBACK (o campo é opcional no contrato, para payload antigo): aplica a MESMA
   * régua do motor com os limiares acima — nunca o critério antigo de break-even.
   */
  const aprovado =
    dre?.flag_viavel ??
    (margem !== null &&
      margem >= margemViavelMin &&
      retorno?.payback != null &&
      retorno.payback <= paybackViavelMax)

  // Classificação do aluguel pedido frente aos clusters de teto (% do faturamento).
  const teto = res?.aluguel_teto ?? null
  const tetoCls =
    teto &&
    teto.ideal != null &&
    teto.teto != null &&
    teto.excecao != null &&
    aluguelReais != null
      ? aluguelReais <= teto.ideal
        ? { label: 'dentro do ideal', tone: 'var(--pos-text)' }
        : aluguelReais <= teto.teto
          ? { label: 'no teto', tone: 'var(--warn-text)' }
          : aluguelReais <= teto.excecao
            ? { label: 'exceção', tone: 'var(--warn-text)' }
            : { label: 'acima do máximo', tone: 'var(--neg)' }
      : null

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        background:
          'radial-gradient(120% 90% at 50% 0%, var(--bg-lift) 0%, var(--bg-base) 70%)',
      }}
    >
      {/* ---------------- Header ----------------
          `barra-ultra`: mesma barra turquesa do Mapa e da Visão Executiva. Ficou de
          fora quando as outras duas foram convertidas — era a única barra superior do
          produto ainda branca, e é o que o Felipe apontou. Sem `backdropFilter`: a
          superfície é opaca, e desfocar o que está atrás dela só custa composição. */}
      <header
        className="barra-ultra"
        style={{
          margin: '16px 16px 0',
          padding: '9px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          background: 'var(--surf-chrome)',
          border: '1px solid var(--line-soft)',
          borderRadius: 'var(--r-xl)',
          flexWrap: 'wrap',
        }}
      >
        <BotaoInicio onInicio={onInicio} />
        {/* Voz de TÍTULO da marca, como na Visão Executiva — era `--f-ui` 15px, isto é,
            um título vestido de rótulo de interface. */}
        <h1
          className="ultra-titulo"
          style={{ font: '700 20px/1 var(--f-titulo)', color: 'var(--tx-max)', margin: 0 }}
        >
          Viabilidade do ponto
        </h1>
        <span aria-hidden style={{ width: 1, height: 20, background: 'var(--line-mid)' }} />
        <button
          type="button"
          onClick={onVoltar}
          className="num"
          style={{
            font: '500 11px/1 var(--f-num)',
            color: 'var(--ac-chip)',
            background: 'var(--ac-a12)',
            border: '1px solid var(--ac-a25)',
            borderRadius: 8,
            padding: '6px 10px',
          }}
        >
          ↩ vindo {origemRotulo} · {ponto.rotulo}
          {/* O recorte que o relatório completo vai ler (DEC-074, Emenda 4), só fora do raio de 1 km. */}
          {ponto.alcance && ponto.alcance !== 'raio_1km' && ` · ${rotuloDoRecorteDoRelatorio(ponto.alcance)}`}
        </button>

        <div style={{ flex: 1 }} />

        <span
          className="num"
          style={{ font: '500 12px/1 var(--f-num)', color: 'var(--tx-narrative)' }}
        >
          {coord(alvoLat!, alvoLng!)}
        </span>
      </header>

      {/* ---------------- Corpo ---------------- */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          gap: 16,
          padding: 16,
          minHeight: 0,
          overflow: 'hidden',
        }}
      >
        {/* ---- Sidebar de premissas ---- */}
        <aside
          className="painel-marca"
          style={{
            width: 346,
            flexShrink: 0,
            overflowY: 'auto',
            padding: '18px 18px 22px',
            /* Cor CHEIA da marca no tema claro, a mesma da barra lateral: a tela
               estava com todos os fundos brancos e virava uma superfície só. Quem
               troca a cor é a classe `painel-marca` (tokens.css) — no escuro o escopo
               não existe e isto volta a ser o painel de vidro de sempre.

               Uma versão anterior usou uma LAVAGEM pálida aqui, e era o erro: o pedido
               era a cor da barra lateral, cheia. */
            background: 'var(--surf-sidebar)',
            border: '1px solid var(--line-soft)',
            borderRadius: 'var(--r-2xl)',
          }}
        >
          <Eyebrow>Cenário</Eyebrow>
          <p
            style={{
              font: '400 11.5px/1.5 var(--f-ui)',
              color: 'var(--tx-muted)',
              margin: '9px 0 16px',
            }}
          >
            Ajuste as premissas. A ferramenta testa o número que você assume — não
            prevê a demanda.
          </p>
          {moedaLocal && (
            <div style={{ marginBottom: 14 }}>
              <span
                style={{
                  display: 'block',
                  font: '500 11px/1 var(--f-ui)',
                  color: 'var(--tx-label)',
                  marginBottom: 6,
                }}
              >
                Moeda do imóvel
              </span>
              <div role="radiogroup" aria-label="Moeda do imóvel" style={{ display: 'flex', gap: 6 }}>
                {(
                  [
                    ['local', `Pesos (${moedaLocal.codigo})`],
                    ['usd', 'Dólares (USD)'],
                  ] as const
                ).map(([id, rotulo]) => {
                  const ativo = moedaEntrada === id
                  return (
                    <button
                      key={id}
                      type="button"
                      role="radio"
                      aria-checked={ativo}
                      onClick={() => trocarMoeda(id)}
                      style={{
                        flex: 1,
                        padding: '8px 10px',
                        borderRadius: 'var(--r-md)',
                        border: `1px solid ${ativo ? 'var(--ac)' : 'var(--line-soft)'}`,
                        background: ativo ? 'var(--surf-raised)' : 'transparent',
                        color: ativo ? 'var(--tx-max)' : 'var(--tx-sub)',
                        font: `${ativo ? 600 : 500} 12px/1 var(--f-ui)`,
                      }}
                    >
                      {rotulo}
                    </button>
                  )
                })}
              </div>
              <div
                style={{ font: '400 10px/1.45 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 6 }}
              >
                Valores digitados e resultados em {nomeMoeda}. Câmbio do perfil:{' '}
                {num(moedaLocal.local_por_usd, 2)} {moedaLocal.codigo} e R${' '}
                {num(moedaLocal.brl_por_usd, 4)} por dólar
                {moedaLocal.base ? ` (base ${moedaLocal.base})` : ''}. O PDF e a planilha saem
                em reais.
              </div>
            </div>
          )}

          {/* MASCARA VIVA nos campos do Cenario --------------------------------
              O ponto de milhar e a unidade aparecem DENTRO da caixa, enquanto a
              pessoa digita: "1500" ja' e' "1.500" na tecla, e o "m²"/"R$" fica
              visivel o tempo todo (adorno absoluto, `aria-hidden` — o nome
              acessivel vai no `rotulo`). O input nativo nao exibe separador
              nenhum, entao isto exige `type="text"`: em `type="number"` o
              `selectionStart` e' `null` no Chrome/Safari e o caret seria
              impossivel de preservar. Ver components/CampoNumero.tsx.

              O que se perde e' o SPINNER (os botoezinhos); o incremento volta em
              ArrowUp/ArrowDown com o mesmo step, avisado no `title`. Nao se perde
              clamp: `min`/`max` nativos nunca impediram digitacao — hoje ja' dava
              para digitar 50 em Metragem com min=200 —, eles so' valiam para as
              setas, e as setas continuam respeitando-os.

              A unidade saiu do `sufixo` do `Campo` e virou adorno DENTRO da caixa:
              ali ela nao concorre com o rotulo por espaco e fica ao lado do numero
              que esta' sendo digitado, que e' o momento em que ela importa.

              STUDIOS FICA COMO ESTA': 0..3, um digito, nunca tem separador de milhar
              para exibir e a faixa ja' esta' no rotulo. Mascarar so' custaria o clamp
              e as setas nativas, sem entregar nada. */}
          {!moedaLocal && (
            <SeletorTipoImovel atual={tipoImovel} onTrocar={(t) => void trocarTipoImovel(t)} />
          )}

          <div style={{ display: 'flex', gap: 10 }}>
            <Campo label="Metragem">
              <CampoNumero
                valor={m2}
                onValor={(n) => {
                  setM2(n)
                  // Nova metragem re-escala a demanda: solta o override manual.
                  setDemandaTocada(false)
                }}
                maxDigitos={5}
                min={200}
                step={50}
                sufixo="m²"
                rotulo="Metragem em m²"
                title="Metragem do imóvel, em m². Use ↑/↓ para variar de 50 em 50."
              />
            </Campo>
            <Campo label="Aluguel" sufixo="/mês">
              <CampoNumero
                valor={aluguel}
                onValor={setAluguel}
                onVazio={() => setAluguel(undefined)}
                maxDigitos={moedaLocal && moedaEntrada === 'local' ? 10 : 7}
                min={0}
                step={moedaLocal && moedaEntrada === 'local' ? 100000 : 1000}
                prefixo={simbolo}
                rotulo={`Aluguel em ${nomeMoeda} por mês`}
                placeholder={
                  moedaLocal ? 'Informe' : naMoeda(aluguelRefReais ?? ALUGUEL_SEM_BASE_REAIS)
                }
                title={
                  moedaLocal
                    ? `Aluguel pedido, em ${simbolo}/mês.`
                    : 'Aluguel pedido, em R$/mês. Vazio usa o aluguel de referência do município para o tipo e a metragem.'
                }
              />
            </Campo>
          </div>

          {!moedaLocal && (
            <QuadroAluguelReferencia
              referencia={refAluguel}
              m2={m2}
              aluguelDigitado={aluguelDigitadoReais ?? null}
            />
          )}

          <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
            {moedaLocal ? (
              <Campo label="Ticket de musculação" sufixo="/mês">
                <CampoNumero
                  valor={ticketLocal}
                  onValor={setTicketLocal}
                  onVazio={() => setTicketLocal(undefined)}
                  maxDigitos={moedaEntrada === 'local' ? 7 : 4}
                  casas={moedaEntrada === 'usd' ? 2 : 0}
                  min={0}
                  step={moedaEntrada === 'local' ? 500 : 1}
                  prefixo={simbolo}
                  rotulo={`Ticket de musculação, em ${nomeMoeda} por mês`}
                  placeholder="Informe"
                  title={`Mensalidade cheia do plano de balcão, em ${simbolo}/mês.`}
                />
              </Campo>
            ) : (
              <Campo label="Ticket de musculação" sufixo="/mês">
                <CampoNumero
                  valor={ticket}
                  onValor={setTicket}
                  maxDigitos={4}
                  min={0}
                  step={5}
                  prefixo="R$"
                  rotulo="Ticket de musculação, em reais por mês"
                  title="Mensalidade cheia do plano de balcão, em R$/mês. Use ↑/↓ para variar de 5 em 5."
                />
              </Campo>
            )}
            <Campo label="Studios" sufixo="0–3">
              <input
                type="number"
                value={nStudios}
                min={0}
                max={3}
                step={1}
                onChange={(e) => setNStudios(clampNStudios(e.target.value))}
              />
            </Campo>
          </div>

          {/* Um ticket por studio ativo: as caixas aparecem e somem junto com o número.
              Grade com `auto-fit`: 1 a 3 caixas dividem a largura sem estourar a coluna
              estreita da sidebar (minmax garante que o "R$" e o número caibam). */}
          {nStudios > 0 && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(92px, 1fr))',
                gap: 10,
                marginTop: 10,
              }}
            >
              {ticketsAtivos(ticketsStudios, nStudios).map((valor, i) => (
                <Campo key={i} label={`Ticket do studio ${i + 1}`} sufixo="/mês">
                  <CampoNumero
                    valor={valor}
                    onValor={(n) => setTicketsStudios((t) => definirTicketStudio(t, i, n))}
                    maxDigitos={moedaLocal && moedaEntrada === 'local' ? 7 : 4}
                    casas={moedaLocal && moedaEntrada === 'usd' ? 2 : 0}
                    min={1}
                    step={moedaLocal ? (moedaEntrada === 'local' ? 500 : 1) : 5}
                    prefixo={simbolo}
                    rotulo={`Ticket do studio ${i + 1}, em ${nomeMoeda} por mês`}
                    title={`Mensalidade do studio ${i + 1}, em ${simbolo}/mês.`}
                  />
                </Campo>
              ))}
            </div>
          )}

          {/* Ticket médio (blended) — SOMENTE-LEITURA, vem do motor. O operador digita o
              ticket de musculação (e o de cada studio); o que entra no caixa por aluno
              TOTAL é este, com os studios, o mix balcão/agregador e o ticket do agregador
              acoplado ao de musculação (P2-12). Tudo lido do payload: a tela só formata. */}
          <div
            style={{
              marginTop: 10,
              padding: '10px 12px',
              background: 'var(--surf-raised)',
              border: '1px solid var(--line-soft)',
              borderRadius: 'var(--r-md)',
            }}
          >
            <div
              style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}
            >
              <span style={{ font: '500 11px/1 var(--f-ui)', color: 'var(--tx-label)' }}>
                Ticket médio (blended)
              </span>
              <span
                className="num"
                style={{ font: '700 14px/1 var(--f-num)', color: 'var(--tx-max)' }}
              >
                {premissas ? brl(premissas.ticket_blended, false, 2) : TEXTO_SEM_DADO}
              </span>
            </div>
            <div
              style={{ font: '400 10px/1.45 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 6 }}
            >
              {premissas ? (
                <>
                  {temStudios && (
                    <>
                      {premissas.n_studios === 1 ? '1 studio' : `${premissas.n_studios} studios`}
                      {premissas.share_por_studio != null
                        ? ` × ${pctFrac(premissas.share_por_studio, 0)} da demanda`
                        : ''}{' '}
                      ({(premissas.tickets_studios ?? []).map((t) => brl(t, false, 2)).join(' · ')}
                      ).{' '}
                    </>
                  )}
                  {temStudios && premissas.share_musculacao != null
                    ? `Sobre os ${pctFrac(premissas.share_musculacao, 0)} restantes: `
                    : 'Mix '}
                  {pctFrac(premissas.share_balcao, 0)} balcão (
                  {brl(premissas.ticket_cheio, false, 2)}, ticket de musculação) ·{' '}
                  {pctFrac(1 - premissas.share_balcao, 0)} agregador (
                  {brl(premissas.ticket_agregador, false, 2)}
                  {premissas.ticket_agregador_fator != null
                    ? `, ${pctFrac(premissas.ticket_agregador_fator, 0)} da musculação`
                    : ''}
                  ). Já líquido de churn e inadimplência.
                  {/* Onde o mix é campo do operador, "a tela só exibe" seria falso. */}
                  {!mixEditavel && ' Calculado pelo motor — a tela só exibe.'}
                </>
              ) : (
                'Calcule o cenário para ver o ticket médio efetivo por aluno total.'
              )}
            </div>
          </div>

          <span
            style={{
              display: 'block',
              font: '400 10px/1.4 var(--f-ui)',
              color: 'var(--tx-sub)',
              marginTop: 6,
            }}
          >
            Ticket de musculação = mensalidade do plano de balcão.{' '}
            {premissas?.share_por_studio != null && premissas.custo_studio_mes != null
              ? `Cada studio atende ${pctFrac(premissas.share_por_studio, 0)} da demanda assumida, com ticket próprio, e custa ${brl(premissas.custo_studio_mes)}/mês; o split balcão/agregadores vale sobre o restante.`
              : 'Cada studio atende uma fatia própria da demanda assumida, com ticket próprio e custo fixo mensal; o split balcão/agregadores vale sobre o restante.'}
          </span>

          <div
            style={{
              marginTop: 14,
              padding: '13px 15px',
              background: 'var(--ac-a08)',
              border: '1px solid var(--ac-a30)',
              borderRadius: 'var(--r-lg)',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'baseline',
                marginBottom: 8,
              }}
            >
              <span style={{ font: '500 11px/1 var(--f-ui)', color: 'var(--tx-label)' }}>
                Demanda assumida
              </span>
              <span
                className="num"
                style={{
                  font: '500 9.5px/1 var(--f-num)',
                  color: demandaTocada || semComparaveis ? 'var(--warn-text)' : 'var(--ac-text)',
                }}
              >
                {demandaTocada
                  ? 'ajuste manual'
                  : v2Vigente
                    ? 'sugestão do modelo'
                    : semComparaveis
                      ? 'premissa do operador'
                      : 'padrão · p50'}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {/* O numero grande saia sem unidade nenhuma ("800"). `alunos()` ja'
                  aplica o separador de milhar; faltava a palavra. */}
              {semComparaveis && !v2Vigente ? (
                // Sem faixa de comparáveis não existe padrão: o operador DIGITA a
                // premissa. Vazio volta a `null` e a tela deixa de calcular.
                <span style={{ flex: 1, minWidth: 0 }}>
                  <CampoNumero
                    valor={demanda ?? undefined}
                    onValor={(n) => {
                      setDemandaTocada(true)
                      setDemanda(n)
                    }}
                    onVazio={() => setDemanda(null)}
                    maxDigitos={5}
                    min={1}
                    step={DEMANDA_PASSO}
                    sufixo="alunos"
                    rotulo="Demanda assumida, em alunos totais"
                    placeholder="Informe"
                  />
                </span>
              ) : (
                <span style={{ flex: 1, display: 'flex', alignItems: 'baseline', gap: 6 }}>
                  <span
                    className="num"
                    style={{ font: '700 22px/1 var(--f-num)', color: 'var(--tx-max)' }}
                  >
                    {alunos(demanda)}
                  </span>
                  <span style={{ font: '500 11px/1 var(--f-ui)', color: 'var(--tx-label)' }}>
                    alunos
                  </span>
                </span>
              )}
              <button
                type="button"
                aria-label="Diminuir demanda"
                onClick={() => {
                  setDemandaTocada(true)
                  setDemanda((d) => Math.max(100, (d ?? 0) - DEMANDA_PASSO))
                }}
                style={stepper}
              >
                −
              </button>
              <button
                type="button"
                aria-label="Aumentar demanda"
                onClick={() => {
                  setDemandaTocada(true)
                  setDemanda((d) => (d ?? 0) + DEMANDA_PASSO)
                }}
                style={stepper}
              >
                +
              </button>
            </div>
            {/* Mix recorrente × agregador: de quantos desses alunos pagam o plano de
                balcão. Vazio = padrão do motor; o agregador é o complemento. */}
            {mixEditavel && (
              <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', marginTop: 10 }}>
                <Campo label="Recorrente (balcão)">
                  <CampoNumero
                    valor={pctBalcao}
                    onValor={setPctBalcao}
                    onVazio={() => setPctBalcao(undefined)}
                    maxDigitos={3}
                    min={0}
                    max={100}
                    step={1}
                    sufixo="%"
                    rotulo="Percentual de alunos recorrentes, de balcão"
                    placeholder={
                      premissas ? num(premissas.share_balcao * 100, 0) : PADRAO_PCT_BALCAO
                    }
                    title="Percentual dos alunos que paga o plano de balcão (recorrente). O restante vem por agregador, que paga menos por aluno. Vazio usa o padrão do motor."
                  />
                </Campo>
                <div style={{ flex: 1, minWidth: 0, paddingBottom: 9 }}>
                  <span style={{ font: '500 11px/1 var(--f-ui)', color: 'var(--tx-label)' }}>
                    Agregador
                  </span>
                  <div
                    className="num"
                    style={{
                      font: '700 14px/1 var(--f-num)',
                      color: 'var(--tx-max)',
                      marginTop: 8,
                    }}
                  >
                    {/* Le a MESMA funcao que monta o payload (`fracaoDoPercentual`), e nao
                        `100 - pctBalcao`. A diferenca importa fora da faixa: o `CampoNumero`
                        deste repo documenta que `min`/`max` nativos NAO impedem digitacao,
                        entao 150 era aceito e a tela mostrava "Agregador -50%" enquanto
                        `fracaoDoPercentual` devolvia `undefined`, a chave saia do JSON e o
                        MOTOR usava o padrao de 69% — tela e conta discordando em silencio.
                        Com a mesma fonte, fora da faixa as duas caem no padrao juntas. */}
                    {(() => {
                      const frac = fracaoDoPercentual(pctBalcao)
                      if (frac !== undefined) return `${num(100 - frac * 100, 0)}%`
                      return premissas
                        ? `${num((1 - premissas.share_balcao) * 100, 0)}%`
                        : `${100 - Number(PADRAO_PCT_BALCAO)}%`
                    })()}
                  </div>
                </div>
              </div>
            )}
            <div
              style={{
                font: '400 10.5px/1.4 var(--f-ui)',
                color: 'var(--tx-sub)',
                marginTop: 8,
              }}
            >
              {v2Vigente ? (
                <>
                  Sugestão do modelo de praça (10 min de carro, metragem e estúdios),
                  editável. Faixa: {alunos(v2Vigente.alunos.p10)}–
                  {alunos(v2Vigente.alunos.p90)} alunos (p10–p90).
                  {avisosV2(v2Vigente).map((a) => (
                    <span key={a} style={{ display: 'block', color: 'var(--warn-text)' }}>
                      {a}
                    </span>
                  ))}
                  {demandaTocada && (
                    <>
                      {' '}
                      <button
                        type="button"
                        onClick={() => {
                          const s = sementeDaDemandaV2(v2Vigente)
                          setDemandaTocada(false)
                          if (s != null) setDemanda(s)
                        }}
                        style={{
                          color: 'var(--ac-text)',
                          font: '600 10.5px/1.4 var(--f-ui)',
                          padding: 0,
                          textDecoration: 'underline',
                        }}
                      >
                        voltar à sugestão do modelo
                      </button>
                    </>
                  )}
                </>
              ) : faixa && faixa.p50 != null ? (
                <>
                  {motivoDaV2 && (
                    <span style={{ display: 'block', color: 'var(--tx-muted)' }}>
                      {motivoDaV2}
                    </span>
                  )}
                  Padrão = p50 da curva tamanho→densidade para {num(m2)} m² (
                  {alunos(faixa.p10)}–{alunos(faixa.p90)}, {faixa.n_comparaveis} comparáveis).
                  {demandaTocada && (
                    <>
                      {' '}
                      <button
                        type="button"
                        onClick={() => {
                          setDemandaTocada(false)
                          if (faixa.p50 != null) setDemanda(Math.round(faixa.p50))
                        }}
                        style={{
                          color: 'var(--ac-text)',
                          font: '600 10.5px/1.4 var(--f-ui)',
                          padding: 0,
                          textDecoration: 'underline',
                        }}
                      >
                        voltar ao p50
                      </button>
                    </>
                  )}
                </>
              ) : demanda == null ? (
                'Não há faixa de comparáveis nesta base. A demanda é premissa do operador: informe o número de alunos totais e calcule.'
              ) : premissas ? (
                temStudios && premissas.share_por_studio != null ? (
                  `Premissa explícita do operador, em alunos TOTAIS. Mix: ${
                    premissas.n_studios
                  } × ${pctFrac(premissas.share_por_studio, 0)} em studios; ${pctFrac(
                    premissas.share_balcao,
                    0,
                  )} balcão + ${pctFrac(1 - premissas.share_balcao, 0)} agregadores${
                    premissas.share_musculacao != null
                      ? ` sobre os ${pctFrac(premissas.share_musculacao, 0)} restantes`
                      : ' sobre o restante'
                  }.`
                ) : (
                  `Premissa explícita do operador, em alunos TOTAIS. Mix: ${pctFrac(
                    premissas.share_balcao,
                    0,
                  )} balcão + ${pctFrac(1 - premissas.share_balcao, 0)} agregadores.`
                )
              ) : (
                'Premissa explícita do operador, em alunos TOTAIS (balcão + agregadores + studios).'
              )}
            </div>
          </div>

          {/* ---- Rampa de maturação: curva observada, com o PICO no contador "−/+" ---- */}
          <div
            style={{
              marginTop: 14,
              padding: '12px 15px',
              background: 'var(--surf-raised)',
              border: '1px solid var(--line-soft)',
              borderRadius: 'var(--r-lg)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ font: '500 11px/1 var(--f-ui)', color: 'var(--tx-label)' }}>
                Pico de maturação
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <button
                  type="button"
                  aria-label="Diminuir o pico de maturação"
                  disabled={picoMostrado == null}
                  onClick={() => picoMostrado != null && setPicoRampa(passoPico(picoMostrado, -1))}
                  style={stepper}
                >
                  −
                </button>
                <span
                  className="num"
                  aria-live="polite"
                  style={{
                    font: '700 14px/1 var(--f-num)',
                    color: 'var(--tx-max)',
                    minWidth: 58,
                    textAlign: 'center',
                  }}
                >
                  {picoMostrado != null ? rotuloPico(picoMostrado) : '—'}
                </span>
                <button
                  type="button"
                  aria-label="Aumentar o pico de maturação"
                  disabled={picoMostrado == null}
                  onClick={() => picoMostrado != null && setPicoRampa(passoPico(picoMostrado, 1))}
                  style={stepper}
                >
                  +
                </button>
              </div>
            </div>
            <div style={{ font: '400 10.5px/1.4 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 8 }}>
              {ajudaDaRampa(premissas)}
            </div>
          </div>

          {/* ---- Investimento: Obra (CAPEX) + Equipamentos (OPEX financiado) ---- */}
          <div
            style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: 16 }}
          >
            <Eyebrow>Investimento</Eyebrow>
            <span style={{ font: '400 10.5px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>opcional</span>
          </div>
          <p style={{ font: '400 10.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)', margin: '7px 0 10px' }}>
            Obra + Equipamentos = CAPEX. Com a taxa de franquia formam o investimento total,
            base do retorno do negócio e do payback. Campo vazio usa o padrão do modelo —
            exceto no par Obra/Equipamentos: preenchendo só um dos dois, o outro entra
            como R$ 0.
          </p>

          {/* MASCARA VIVA tambem aqui — o mesmo CampoNumero do Cenario ---------------
              O separador de milhar aparece na tecla e a UNIDADE (R$, meses, % a.m.,
              % a.a.) fica DENTRO da caixa o tempo todo, como adorno. Antes a unidade
              vivia no placeholder e sumia na primeira tecla: era exatamente a queixa.

              DUAS DIFERENCAS em relacao ao Cenario, ambas resolvidas por prop:
               - `onVazio`: aqui o vazio e' um VALOR ("use o padrao do motor"), entao o
                 pai precisa ouvi-lo e guardar `undefined`. Sem essa prop o componente
                 continua com a politica do Cenario, e por isso os 3 campos de la' nao
                 precisaram de nenhuma edicao.
               - `casas`: juros e taxa minima aceitam UMA virgula decimal. Nos 7 campos
                 inteiros `casas` fica em 0, o que agora torna impossivel digitar "4,5"
                 em Parcelas obra e levar um 422 do `int | None`.

              O nome do campo saiu do placeholder e virou ROTULO (`Campo`): o adorno
              come' ~60px da caixa, e "Parcelas franquia (meses)" nao caberia no que
              sobra. O placeholder ficou para o PADRAO — ver `dica` e o bloco de
              padroes verificados acima dela. */}
          <div style={{ display: 'flex', gap: 8 }}>
            <Campo label="Obra">
              <CampoNumero
                valor={obra}
                onValor={setObra}
                onVazio={() => setObra(undefined)}
                maxDigitos={moedaLocal && moedaEntrada === 'local' ? 10 : 7}
                min={0}
                step={10000}
                prefixo={simbolo}
                rotulo={`Obra, em ${nomeMoeda}`}
                placeholder={moedaLocal ? naMoeda(PADRAO_OBRA_REAIS) : fixa(PADRAO_OBRA)}
                title={
                  moedaLocal
                    ? `Obra (equity do franqueado), em ${simbolo}. O número da caixa é o padrão: vazio, o motor usa esse valor.`
                    : "Obra (equity do franqueado), em R$. O 1.500.000 da caixa é o padrão: vazio, o motor usa esse valor. Use as setas para variar de 10.000 em 10.000."
                }
              />
            </Campo>
            <Campo label="Parcelas obra">
              <CampoNumero
                valor={parcelasObra}
                onValor={setParcelasObra}
                onVazio={() => setParcelasObra(undefined)}
                maxDigitos={2}
                min={1}
                max={12}
                sufixo="meses"
                rotulo="Parcelas da obra, em meses"
                placeholder={dica(inv?.parcelas_obra, PADRAO_PARCELAS_OBRA)}
                title="Em quantos meses a obra é desembolsada (1 a 12). Vazio usa o padrão do modelo."
              />
            </Campo>
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <Campo label="Equipamentos">
              <CampoNumero
                valor={equip}
                onValor={setEquip}
                onVazio={() => setEquip(undefined)}
                maxDigitos={moedaLocal && moedaEntrada === 'local' ? 10 : 7}
                min={0}
                step={10000}
                prefixo={simbolo}
                rotulo={`Equipamentos, em ${nomeMoeda}`}
                placeholder={moedaLocal ? naMoeda(PADRAO_EQUIPAMENTOS_REAIS) : fixa(PADRAO_EQUIPAMENTOS)}
                title={
                  moedaLocal
                    ? `Equipamentos (parcela financiada), em ${simbolo}. O número da caixa é o padrão: vazio, o motor usa esse valor. Para não financiar nada, digite 0.`
                    : "Equipamentos (parcela financiada), em R$. O 1.200.000 da caixa é o padrão: vazio, o motor usa esse valor. Para não financiar nada, digite 0. Use as setas para variar de 10.000 em 10.000."
                }
              />
            </Campo>
            <Campo label="Prazo financ.">
              <CampoNumero
                valor={prazoEquip}
                onValor={setPrazoEquip}
                onVazio={() => setPrazoEquip(undefined)}
                maxDigitos={2}
                min={1}
                max={60}
                sufixo="meses"
                rotulo="Prazo do financiamento dos equipamentos, em meses"
                placeholder={fixa(PADRAO_PRAZO_EQUIP)}
                title="Prazo do financiamento dos equipamentos, em meses (1 a 60). O 36 da caixa é o padrão: vazio, o motor usa esse valor. Sem equipamentos o prazo não tem efeito."
              />
            </Campo>
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <Campo label="Juros equip.">
              <CampoNumero
                valor={jurosEquip}
                onValor={setJurosEquip}
                onVazio={() => setJurosEquip(undefined)}
                maxDigitos={3}
                casas={2}
                min={0}
                max={100}
                step={0.1}
                sufixo="% a.m."
                rotulo="Juros do financiamento dos equipamentos, em por cento ao mês"
                placeholder={fixa(PADRAO_JUROS_EQUIP)}
                title="Juros do financiamento dos equipamentos, em % ao mês (aceita vírgula). O 1,8 da caixa é o padrão: vazio, o motor usa esse valor. Use as setas para variar de 0,1 em 0,1."
              />
            </Campo>
            <Campo label="Carência aluguel">
              <CampoNumero
                valor={carencia}
                onValor={setCarencia}
                onVazio={() => setCarencia(undefined)}
                maxDigitos={2}
                min={0}
                max={60}
                sufixo="meses"
                rotulo="Carência de aluguel, em meses"
                placeholder={dica(premissas?.carencia_aluguel_meses, PADRAO_CARENCIA)}
                title="Meses iniciais sem pagar aluguel, contados da entrega (M-4). Vazio usa o padrão do modelo."
              />
            </Campo>
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <Campo label="Taxa de franquia">
              <CampoNumero
                valor={taxaFranquia}
                onValor={setTaxaFranquia}
                onVazio={() => setTaxaFranquia(undefined)}
                maxDigitos={moedaLocal && moedaEntrada === 'local' ? 10 : 7}
                min={0}
                step={10000}
                prefixo={simbolo}
                rotulo={`Taxa de franquia, em ${nomeMoeda}`}
                placeholder={
                  moedaLocal
                    ? naMoeda(inv?.taxa_franquia ?? PADRAO_TAXA_FRANQUIA_REAIS)
                    : dica(inv?.taxa_franquia, PADRAO_TAXA_FRANQUIA)
                }
                title={
                  moedaLocal
                    ? `Taxa de franquia, em ${simbolo}. Vazio usa o padrão do modelo (o número da caixa); digitar 0 é honrado como zero.`
                    : "Taxa de franquia, em R$. Vazio usa o padrão do modelo; digitar 0 é honrado como R$ 0."
                }
              />
            </Campo>
            {/* Parcelas da franquia: mesmo par que "Obra + Parcelas obra", uma linha
                abaixo — o número de parcelas fica ao lado do valor que ele divide. */}
            <Campo label="Parcelas franquia">
              <CampoNumero
                valor={parcelasFranquia}
                onValor={setParcelasFranquia}
                onVazio={() => setParcelasFranquia(undefined)}
                maxDigitos={2}
                min={1}
                max={12}
                sufixo="meses"
                rotulo="Parcelas da taxa de franquia, em meses"
                placeholder={dica(inv?.parcelas_franquia, PADRAO_PARCELAS_FRANQUIA)}
                title="Em quantas parcelas sem juros a taxa de franquia entra (1 a 12). Vazio usa o padrão do modelo."
              />
            </Campo>
          </div>
          <span style={{ display: 'block', font: '400 10px/1.4 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 8 }}>
            A taxa de franquia é editável (vazio = padrão do modelo) e entra{' '}
            <strong>parcelada sem juros</strong> (vazio = 4x), a partir do M-4, junto da obra —
            não mais à vista no M-4. Obra = equity parcelada sem juros; equipamentos
            financiados (prazo + juros a.m.) entram como PMT no caixa mês a mês. Parcelar a
            franquia é só timing de caixa: melhora TIR e VPL, e não muda EBITDA, margem nem
            break-even.
          </span>

          {/* ---- Taxas mínimas: uma é INPUT, a outra é DERIVADA -------------------
              A do NEGÓCIO é a única premissa. A do SÓCIO sai de
              Ke = Ku + (Ku − Kd) × D/E dentro do motor — o sócio é subordinado ao
              banco, então a taxa dele não pode ser menor que a do credor. Não existe
              campo para digitá-la: a incoerência ficou impossível por construção. */}
          <div
            style={{
              marginTop: 14,
              padding: '12px 15px',
              background: 'var(--surf-raised)',
              border: '1px solid var(--line-soft)',
              borderRadius: 'var(--r-lg)',
            }}
          >
            <span style={{ font: '500 11px/1 var(--f-ui)', color: 'var(--tx-label)' }}>
              Taxa mínima do negócio
            </span>
            <div style={{ marginTop: 8 }}>
              <CampoNumero
                valor={taxaNegocio}
                onValor={setTaxaNegocio}
                onVazio={() => setTaxaNegocio(undefined)}
                maxDigitos={3}
                casas={2}
                min={0}
                max={100}
                sufixo="% a.a."
                rotulo="Taxa mínima do negócio, em por cento ao ano"
                // Este campo ja' era o unico a mostrar o padrao PROVADO, lendo o valor
                // usado do proprio payload. A mudanca preserva a fonte e so' troca a
                // formatacao para a mesma do que se digita (25, e nao "25,0% a.a.").
                placeholder={dica(
                  premissas == null ? undefined : premissas.taxa_minima_negocio_aa * 100,
                  PADRAO_TAXA_NEGOCIO,
                  2,
                )}
                title="Piso de retorno que o ativo tem de entregar, ao ano, em % (aceita vírgula: 12,5). Vazio usa o padrão do modelo."
              />
            </div>
            {/* Derivada: SOMENTE-LEITURA, com a fórmula no tooltip. */}
            <div
              title="Taxa mínima do sócio = taxa do negócio + (taxa do negócio − custo da dívida) × dívida/aporte inicial. Derivada pelo motor; não é editável."
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'baseline',
                gap: 8,
                marginTop: 10,
                padding: '9px 11px',
                background: 'var(--surf-pending)',
                border: '1px dashed var(--line-strong)',
                borderRadius: 'var(--r-md)',
              }}
            >
              <span style={{ font: '500 10.5px/1.3 var(--f-ui)', color: 'var(--tx-label)' }}>
                Taxa mínima do sócio
                <span style={{ color: 'var(--tx-sub)', fontWeight: 400 }}> · derivada</span>
              </span>
              <span
                className="num"
                style={{ font: '700 13px/1 var(--f-num)', color: 'var(--tx-max)' }}
              >
                {retorno?.socio ? `${pctFrac(retorno.socio.taxa_minima_aa)} a.a.` : TEXTO_SEM_DADO}
              </span>
            </div>
            <div
              style={{ font: '400 10px/1.45 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 8 }}
            >
              {retorno ? (
                <>
                  Custo da dívida {pctFrac(retorno.custo_divida_aa)} a.a. · alavancagem{' '}
                  {num(retorno.alavancagem_divida_sobre_aporte, 2)}x o aporte inicial. O sócio
                  entra depois do banco, então exige mais que ele — a taxa dele é calculada
                  pelo motor e não pode ser digitada.
                </>
              ) : (
                'Calcule o cenário para ver a taxa mínima do sócio, derivada do custo da dívida e da alavancagem.'
              )}
            </div>
          </div>

          {/* P1-7: a carência EFETIVA que o motor aplicou e o mês em que o aluguel
              começa a ser cobrado. Antes o texto falava em "padrão do modelo", que não
              existe: o default é ZERO e a contagem parte da ENTREGA (M-4), não da abertura. */}
          {premissas && (
            <div
              style={{
                marginTop: 10,
                padding: '9px 11px',
                background: 'var(--surf-raised)',
                border: '1px solid var(--line-soft)',
                borderRadius: 'var(--r-md)',
                font: '400 10.5px/1.5 var(--f-ui)',
                color: 'var(--tx-sub)',
              }}
            >
              {premissas.carencia_aluguel_meses > 0 ? (
                <>
                  Carência efetiva:{' '}
                  <strong style={{ color: 'var(--tx-soft)' }}>
                    {premissas.carencia_aluguel_meses}{' '}
                    {premissas.carencia_aluguel_meses === 1 ? 'mês' : 'meses'}
                  </strong>
                  , contados da entrega da unidade (M-4), não da inauguração. Primeira cobrança
                  de aluguel:{' '}
                  <strong style={{ color: 'var(--tx-soft)' }}>
                    {premissas.mes_inicio_aluguel == null
                      ? 'nenhuma no horizonte'
                      : rotuloMes(premissas.mes_inicio_aluguel)}
                  </strong>
                  .
                </>
              ) : (
                <>
                  <strong style={{ color: 'var(--tx-soft)' }}>Sem carência.</strong> Primeira
                  cobrança de aluguel:{' '}
                  <strong style={{ color: 'var(--tx-soft)' }}>
                    {premissas.mes_inicio_aluguel == null
                      ? 'nenhuma no horizonte'
                      : rotuloMes(premissas.mes_inicio_aluguel)}
                  </strong>
                  {premissas.mes_inicio_aluguel != null && premissas.mes_inicio_aluguel < 0
                    ? ' — ou seja, já durante as obras.'
                    : '.'}
                </>
              )}
            </div>
          )}

          {res && (
            <div
              style={{
                display: 'flex',
                gap: 16,
                marginTop: 10,
                padding: '9px 11px',
                background: 'var(--surf-raised)',
                border: '1px solid var(--line-soft)',
                borderRadius: 'var(--r-md)',
              }}
            >
              {/* Notação curta ("R$ 2,2M", "R$ 38k/mês"): os três readouts dividem uma
                  linha estreita e o valor cheio quebrava para a linha de baixo. */}
              <ReadoutCapex
                rotulo="Investimento total"
                valor={brlCurto(res.investimento.investimento_total)}
              />
              {/* A franquia é PARCELADA: mostrar só o total esconderia o desembolso
                  real de cada mês de obra. Ambos vêm do payload (nenhuma divisão aqui). */}
              <ReadoutCapex
                rotulo={
                  res.investimento.parcelas_franquia
                    ? `Franquia (${res.investimento.parcelas_franquia}x)`
                    : 'Taxa de franquia'
                }
                valor={
                  res.investimento.franquia_parcela
                    ? `${brlCurto(res.investimento.taxa_franquia)} · ${brlCurto(
                        res.investimento.franquia_parcela,
                      )}/parc.`
                    : brlCurto(res.investimento.taxa_franquia)
                }
              />
              {/* Sem financiamento, a informacao vai para o ROTULO e o valor vira "—".
                  "sem financiamento" ocupava ~133px de 13px mono numa coluna de ~85px:
                  o texto vazava da caixa, e "financiamento" sozinho ja' nao cabia (nao
                  ha' onde quebrar dentro da palavra). No rotulo, a 9.5px, ele quebra em
                  duas linhas e cabe. */}
              <ReadoutCapex
                rotulo={res.investimento.pmt ? 'PMT' : 'PMT · sem financiamento'}
                valor={
                  res.investimento.pmt ? `${brlCurto(res.investimento.pmt)}/mês` : '—'
                }
              />
            </div>
          )}

          <div style={{ height: 1, background: 'var(--line-soft)', margin: '18px 0' }} />

          <div
            style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}
          >
            <Eyebrow>Dados para o relatório</Eyebrow>
            <span style={{ font: '400 10.5px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
              opcional
            </span>
          </div>

          {/* Fotos */}
          <button
            type="button"
            onClick={() => inputFoto.current?.click()}
            style={{
              width: '100%',
              marginTop: 12,
              padding: '16px 12px',
              border: '1.5px dashed var(--line-dashed)',
              borderRadius: 11,
              background: 'transparent',
              color: 'var(--tx-muted)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M12 16V4m0 0L8 8m4-4 4 4" />
              <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
            </svg>
            <span style={{ font: '600 12px/1 var(--f-ui)', color: 'var(--tx-soft)' }}>
              {fotos.length ? `${fotos.length} foto(s) escolhida(s)` : 'Fotos do imóvel'}
            </span>
            <span style={{ font: '400 10.5px/1 var(--f-ui)' }}>até 2 · JPG ou PNG</span>
          </button>
          <input
            ref={inputFoto}
            type="file"
            accept="image/jpeg,image/png"
            multiple
            hidden
            onChange={(e) => setFotos(Array.from(e.target.files ?? []).slice(0, 2))}
          />

          <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <input
              placeholder="Nome / endereço do imóvel"
              value={info.nome ?? ''}
              onChange={(e) => setInfo({ ...info, nome: e.target.value })}
            />
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                placeholder="Valor de venda"
                value={info.valor_venda ?? ''}
                onChange={(e) => setInfo({ ...info, valor_venda: e.target.value })}
              />
              <input
                placeholder="Pé-direito"
                style={{ maxWidth: 92 }}
                value={info.pe_direito ?? ''}
                onChange={(e) => setInfo({ ...info, pe_direito: e.target.value })}
              />
              <input
                placeholder="Vagas"
                style={{ maxWidth: 72 }}
                value={info.vagas ?? ''}
                onChange={(e) => setInfo({ ...info, vagas: e.target.value })}
              />
            </div>
            <input
              placeholder="Tipo do imóvel (loja, galpão…)"
              value={info.tipo ?? ''}
              onChange={(e) => setInfo({ ...info, tipo: e.target.value })}
            />
            <textarea
              placeholder="Observações"
              rows={2}
              value={info.observacoes ?? ''}
              onChange={(e) => setInfo({ ...info, observacoes: e.target.value })}
              style={{ resize: 'vertical' }}
            />
          </div>

          <Botao
            onClick={() => calcular()}
            disabled={calculando || demanda == null || faltaTicket}
            title={
              demanda == null
                ? 'Informe a demanda assumida para calcular'
                : faltaTicket
                  ? 'Informe o ticket e o aluguel para calcular'
                  : undefined
            }
            style={{ width: '100%', marginTop: 18, padding: 14, fontSize: 14 }}
          >
            {calculando ? 'Calculando…' : res ? 'Recalcular viabilidade' : 'Calcular viabilidade'}
          </Botao>

          <Botao
            variante="ghost"
            onClick={gerarPdf}
            disabled={gerandoPdf}
            style={{ width: '100%', marginTop: 10 }}
            title={dicaDoRelatorioCompleto(ponto.alcance)}
          >
            {gerandoPdf ? (
              <span style={carregando}>
                <Spinner /> Montando o relatório…
              </span>
            ) : (
              'Relatório completo em PDF ↓'
            )}
          </Botao>

          {/* DEC-074, Emenda 4: o recorte que muda o PDF ESCRITO na tela (o `title` não aparece
              no toque nem em todo navegador). `null` no raio de 1 km: a tela de sempre. */}
          {avisoDoRecorteDoRelatorio(ponto.alcance) && (
            <p
              style={{
                font: '400 10.5px/1.5 var(--f-ui)',
                color: 'var(--tx-sub)',
                marginTop: 8,
              }}
            >
              {avisoDoRecorteDoRelatorio(ponto.alcance)}
            </p>
          )}

          {gerandoPdf && (
            <p
              style={{
                font: '400 10.5px/1.5 var(--f-ui)',
                color: 'var(--tx-sub)',
                marginTop: 8,
              }}
            >
              Os mapas de rua são baixados na hora; em área densa isso leva alguns
              minutos.
            </p>
          )}

          <Botao
            variante="ghost"
            onClick={gerarXlsx}
            disabled={gerandoXlsx}
            style={{ width: '100%', marginTop: 10 }}
            title="Planilha do cenário com DRE, folha de pagamento e fluxo de caixa dos 60 meses, em fórmulas editáveis"
          >
            {gerandoXlsx ? (
              <span style={carregando}>
                <Spinner /> Montando a planilha…
              </span>
            ) : (
              'Baixar simulador (Excel) ↓'
            )}
          </Botao>

          <p
            style={{
              font: '400 10.5px/1.5 var(--f-ui)',
              color: 'var(--tx-sub)',
              marginTop: 8,
            }}
          >
            {gerandoXlsx
              ? 'Montando os 60 meses de DRE, folha e fluxo de caixa.'
              : 'Abre com fórmulas vivas: dá para editar aluguel, demanda e salários na frente do investidor e ver os 60 meses recalcularem no Excel.'}
          </p>
        </aside>

        {/* ---- Resultados ---- */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            gap: 14,
            minWidth: 0,
            overflowY: 'auto',
          }}
        >
          {/* Estado de carregamento da TELA, nao so' do botao. O spinner dentro do
              botao passava despercebido (relato de Felipe, 2026-07-31): o operador
              nao sabia se a tela estava processando. Fica `sticky` para continuar
              visivel com a coluna rolada, e no caso do recalculo AVISA que os
              numeros exibidos ainda sao do cenario anterior. */}
          {(calculando || gerandoPdf || gerandoXlsx) && (
            <div
              role="status"
              aria-live="polite"
              style={{
                position: 'sticky',
                top: 0,
                zIndex: 3,
                display: 'flex',
                alignItems: 'center',
                gap: 11,
                padding: '13px 16px',
                borderRadius: 'var(--r-md)',
                background: 'var(--ac-a12)',
                border: '1px solid var(--ac-a30)',
                color: 'var(--ac-text)',
                font: '600 13px/1.4 var(--f-ui)',
                backdropFilter: 'blur(14px)',
              }}
            >
              <Spinner tamanho={18} />
              {calculando
                ? 'Recalculando a viabilidade — os números abaixo ainda são do cenário anterior.'
                : gerandoPdf
                  ? 'Montando o Relatório Pontual. Os mapas de rua são baixados na hora; em área densa leva alguns minutos.'
                  : 'Montando a planilha do simulador.'}
            </div>
          )}

          {/* Rótulo do modelo em calibração vs planilha. Some onde o perfil do país já
              carrega o próprio aviso de premissas provisórias (a AR): lá esta nota,
              escrita para a calibração brasileira, só disputava espaço com ele. */}
          {!avisoPerfil && (
          <div
            style={{
              padding: '9px 13px',
              borderRadius: 'var(--r-md)',
              background: 'rgba(255,193,7,.10)',
              border: '1px solid rgba(255,193,7,.35)',
              font: '400 11px/1.45 var(--f-ui)',
              color: 'var(--warn-text)',
            }}
          >
            <strong style={{ fontWeight: 600 }}>Premissas em calibração.</strong> Tela, gráficos
            e PDF passaram a ler o MESMO motor — não há mais número recalculado fora dele. Seguem
            pendentes de gate o NÍVEL da folha
            {premissas ? ` (${pctFrac(premissas.folha_pct)} do faturamento maduro,` : ' ('}{' '}
            revisão no BLK-VIAB-11) e a taxa de desconto do VPL/TIR
            {premissas ? ` (${pctFrac(premissas.taxa_desconto_aa)} a.a.,` : ' ('} provisória). A
            ESTRUTURA da folha já está decidida: valor FIXO desde o mês 1, dimensionado pelo
            faturamento maduro — não escala com a rampa.
          </div>
          )}

          {/* O perfil do país declara, a tela obedece (DEC-047): na AR é a ressalva de
              que a conta usa premissas BRASILEIRAS. O texto é dado do perfil. */}
          {avisoPerfil && (
            <Glass style={{ padding: '13px 16px' }}>
              <Eyebrow cor="var(--warn)" dot>
                {avisoPerfil.titulo}
              </Eyebrow>
              <p
                style={{
                  font: '400 12.5px/1.5 var(--f-ui)',
                  color: 'var(--tx-narrative)',
                  margin: '8px 0 0',
                }}
              >
                {avisoPerfil.texto}
              </p>
            </Glass>
          )}

          {semResultado && !calculando && (
            <Glass style={{ padding: '13px 16px' }}>
              <Eyebrow cor="var(--warn)" dot>
                {!faltaPremissa
                  ? 'Nada calculado ainda'
                  : demanda == null && faltaTicket
                    ? 'Demanda, ticket e aluguel não informados'
                    : demanda == null
                      ? 'Demanda não informada'
                      : 'Ticket ou aluguel não informado'}
              </Eyebrow>
              <p
                style={{
                  font: '400 12.5px/1.5 var(--f-ui)',
                  color: 'var(--tx-narrative)',
                  margin: '8px 0 0',
                }}
              >
                {demanda == null &&
                  'Esta base não tem faixa de alunos de imóveis comparáveis, então a tela não sugere um número de alunos. '}
                {faltaTicket &&
                  'Ticket e aluguel não têm padrão nesta instância: informe os dois na moeda do imóvel. '}
                {!faltaPremissa &&
                  'As premissas estão preenchidas; o resultado aparece depois do cálculo. '}
                Preencha no painel ao lado e clique em Calcular viabilidade.
              </p>
            </Glass>
          )}

          {erro && (
            <div
              role="alert"
              style={{
                padding: '12px 15px',
                borderRadius: 'var(--r-md)',
                background: 'rgba(255,90,110,.12)',
                border: '1px solid rgba(255,90,110,.3)',
                color: 'var(--neg)',
                font: '500 12.5px/1.45 var(--f-ui)',
              }}
            >
              {erro}
            </div>
          )}

          {!semResultado && (
          <>
          {/* Sem demanda não há veredito: "Com 0 alunos… requer revisão" seria um
              resultado inventado. */}
          {demandaExibida != null && (
            <Veredito
              aprovado={aprovado}
              margem={margem}
              demanda={demandaExibida}
              breakEvenEbitda={beEbitda}
              breakEvenCaixa={beCaixa}
              payback={retorno?.payback ?? null}
              melhoria={res?.melhoria_payback ?? null}
            />
          )}

          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
            <Kpi
              label="Margem EBITDA"
              valor={pctFrac(margem)}
              /* O steady-state é o mês `mes_referencia_steady` do payload (regime pleno:
                 alunos maduros E anuidade em cobrança) — LEITURA, nunca recalculado. */
              sub={
                premissas
                  ? `no cenário assumido · mês ${num(premissas.mes_referencia_steady)} (regime pleno)`
                  : 'no cenário assumido'
              }
              /* MESMA régua do veredito (`margem_viavel_min`, do motor): verde só a
                 partir dela. Enquanto o corte aqui era `>= 0`, um cenário de 12% de
                 margem pintava o card de VERDE logo abaixo do selo "Requer revisão de
                 premissas" — dois sinais opostos para o mesmo número. */
              tone={
                margem === null
                  ? undefined
                  : margem >= margemViavelMin
                    ? 'var(--pos-text)'
                    : margem >= 0
                      ? 'var(--warn-text)'
                      : 'var(--neg)'
              }
            />
            {/* P2-15: "payback" é SÓ o retorno do capital. Meses de OPERAÇÃO. */}
            <Kpi
              label="Payback do investimento"
              valor={retorno?.payback == null ? 'não atinge' : `${num(retorno.payback)} meses`}
              sub="meses de operação, contados do 1º desembolso da obra"
              tone={
                retorno?.payback == null
                  ? 'var(--neg)'
                  : retorno.payback <= paybackViavelMax
                    ? 'var(--pos-text)'
                    : 'var(--warn-text)'
              }
            />
            {/* As DUAS ÓTICAS, em cards SEPARADOS e cada uma com a SUA taxa. Antes havia
                UM par de TIR/VPL sem ótica declarada (era o do sócio) ao lado de um
                retorno rotulado "desalavancado" — misturava as duas réguas no mesmo
                bloco, que é o defeito que este ciclo existe para matar. */}
            <Kpi
              label="Retorno do negócio (o ativo)"
              valor={pctFrac(retorno?.negocio?.retorno_anual ?? retorno?.retorno_anual_desalavancado)}
              sub={
                retorno?.negocio
                  ? `TIR ${pctFrac(retorno.negocio.tir_anual)} · VPL ${brl(retorno.negocio.vpl, true)} @ ${pctFrac(retorno.negocio.taxa_minima_aa)}`
                  : 'lucro anual / investimento total'
              }
              tone={
                (retorno?.negocio?.vpl ?? 0) >= 0 ? 'var(--pos-text)' : 'var(--neg)'
              }
            />
            <Kpi
              label="Retorno do sócio (com a alavancagem)"
              valor={pctFrac(retorno?.socio?.retorno_anual ?? retorno?.retorno_anual_equity)}
              sub={
                retorno?.socio
                  ? `TIR ${pctFrac(retorno.socio.tir_anual)} · VPL ${brl(retorno.socio.vpl, true)} @ ${pctFrac(retorno.socio.taxa_minima_aa)} (derivada)`
                  : 'depois da parcela do financiamento'
              }
              tone={(retorno?.socio?.vpl ?? 0) >= 0 ? 'var(--pos-text)' : 'var(--neg)'}
            />
            {/* O número que decide se o negócio é FINANCIÁVEL, e que não existia: o pior
                ponto do caixa acumulado. O aporte contratado (obra + franquia) é bem
                menor que o cheque que o investidor precisa ter disponível. */}
            <Kpi
              label="Cheque total"
              valor={brl(res?.investimento?.cheque_total, true)}
              sub={
                res?.investimento?.cheque_total && res.investimento.aporte_inicial
                  ? `pior caixa, no mês ${res.investimento.mes_cheque_total ?? '?'} · ${(
                      res.investimento.cheque_total / res.investimento.aporte_inicial
                    ).toFixed(2)}× o aporte de ${brl(res.investimento.aporte_inicial, true)}`
                  : 'pior ponto do caixa acumulado'
              }
              tone={
                res?.investimento?.cheque_total && res.investimento.aporte_inicial
                  ? res.investimento.cheque_total / res.investimento.aporte_inicial >
                    CHEQUE_AVISO_RAZAO
                    ? 'var(--warn-text)'
                    : 'var(--pos-text)'
                  : undefined
              }
            />
            {/* P2-15: este é o indicador OPERACIONAL — não é payback. */}
            <Kpi
              label="1º mês com caixa operacional positivo"
              valor={
                res?.mes_caixa_operacional_positivo == null
                  ? 'não atinge'
                  : `mês ${res.mes_caixa_operacional_positivo}`
              }
              sub={
                res?.mes_caixa_operacional_positivo == null
                  ? `a operação não fecha nenhum mês no positivo de forma permanente até o mês ${horizonteMeses}`
                  : `e assim permanece até o mês ${horizonteMeses}`
              }
              tone={
                res?.mes_caixa_operacional_positivo == null ? 'var(--neg)' : 'var(--pos-text)'
              }
            />
            <Kpi
              label="Aluguel vs teto"
              valor={brl(aluguelReais, true)}
              sub={
                teto && teto.ideal != null && teto.teto != null && teto.excecao != null
                  ? `${tetoCls?.label ?? ''} · ideal ${brl(teto.ideal, true)} · teto ${brl(teto.teto, true)} · máx ${brl(teto.excecao, true)}`
                  : 'sem base de faturamento'
              }
              tone={tetoCls?.tone}
            />
            <Kpi
              label="Faixa de alunos"
              valor={
                res?.faixa_alunos.p50 !== null && res?.faixa_alunos.p50 !== undefined
                  ? alunos(res.faixa_alunos.p50)
                  : TEXTO_SEM_DADO
              }
              sub={
                res?.faixa_alunos.p10 != null && res?.faixa_alunos.p90 != null
                  ? `p10 ${num(res.faixa_alunos.p10)} · p90 ${num(res.faixa_alunos.p90)}`
                  : 'sem comparáveis'
              }
            />
          </div>

          {demandaExibida != null && (
            <ReguaBreakEven
              demanda={demandaExibida}
              breakEvenEbitda={beEbitda}
              breakEvenCaixa={beCaixa}
              p90={res?.faixa_alunos.p90 ?? faixa?.p90 ?? null}
            />
          )}

          {/* Fluxo de caixa ao lado da rampa; a composição do resultado (agora com as
              parcelas do custo e a despesa financeira) fica embaixo, em largura total. */}
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
            <div style={{ flex: 1.5, minWidth: 320, display: 'flex' }}>
              <FluxoCaixa
                serie={serie}
                payback={retorno?.payback ?? null}
                carencia={premissas?.carencia_aluguel_meses ?? 0}
              />
            </div>
            <div style={{ flex: 1, minWidth: 240, display: 'flex' }}>
              <RampaAlunos
                serie={serie}
                maturacaoMeses={mesFimDaRampa(premissas)}
                formaRampa={premissas?.forma_rampa ?? null}
              />
            </div>
          </div>

          <FluxoCaixaOperacional
            serie={serie}
            mesPositivo={res?.mes_caixa_operacional_positivo ?? null}
          />

          {/* `premissas` entra só como ROTULAGEM: o mês de referência do regime pleno
              (`mes_referencia_steady`, lido do payload) e a regra da anuidade. */}
          <CascataDre dre={dre} premissas={premissas} />

          {/* Manual da tela, abaixo de TODOS os gráficos: o que cada KPI significa e
              como é calculado. Lê as premissas do payload, então não desatualiza. */}
          <NotasMetodologicas
            premissas={premissas}
            dre={dre}
            demanda={res?.demanda_premissa ?? null}
          />

          {(res?.flag_fora_envelope || res?.flag_zona_morta) && (
            <Glass style={{ padding: '13px 16px' }}>
              <Eyebrow cor="var(--warn)" dot>
                Guardrail
              </Eyebrow>
              <p
                style={{
                  font: '400 12.5px/1.5 var(--f-ui)',
                  color: 'var(--tx-narrative)',
                  margin: '8px 0 0',
                }}
              >
                {res.flag_fora_envelope &&
                  'A metragem está fora do envelope de imóveis comparáveis — a faixa de alunos é extrapolação, não leitura. '}
                {/* `motivo_zona_morta_texto` e nao `motivo_zona_morta`: o segundo e' o
                    TOKEN CRU (`renda<500`), identificador e nao texto de usuario. O
                    servidor traduz com a MESMA funcao do PDF (DEC-042). */}
                {res.flag_zona_morta &&
                  (res.motivo_zona_morta_texto ?? 'Ponto sinalizado como zona morta.')}
              </p>
            </Glass>
          )}
          </>
          )}
        </div>
      </div>
    </div>
  )
}

/** Rótulo + spinner na mesma linha: o `Botao` não é flex, o wrapper é que alinha. */
const carregando: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 8,
}

const stepper: React.CSSProperties = {
  width: 32,
  height: 26,
  borderRadius: 7,
  background: 'var(--surf-pending)',
  border: '1px solid var(--line-strong)',
  color: 'var(--tx-soft)',
  font: '600 15px/1 var(--f-ui)',
  display: 'grid',
  placeItems: 'center',
}

function ReadoutCapex({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ font: '400 9.5px/1 var(--f-ui)', color: 'var(--tx-sub)', marginBottom: 4 }}>
        {rotulo}
      </div>
      {/* `overflowWrap: anywhere` como rede: qualquer valor futuro mais largo que a
          coluna quebra dentro da caixa em vez de vazar por cima do vizinho. */}
      <div
        className="num"
        style={{
          font: '600 13px/1 var(--f-num)',
          color: 'var(--tx-soft)',
          overflowWrap: 'anywhere',
        }}
      >
        {valor}
      </div>
    </div>
  )
}

function Campo({
  label,
  sufixo,
  children,
}: {
  label: string
  sufixo?: string
  children: React.ReactNode
}) {
  return (
    <label style={{ flex: 1, minWidth: 0 }}>
      <span
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          font: '500 11px/1 var(--f-ui)',
          color: 'var(--tx-label)',
          marginBottom: 6,
        }}
      >
        {label}
        {sufixo && <span style={{ color: 'var(--tx-sub)' }}>{sufixo}</span>}
      </span>
      {children}
    </label>
  )
}
