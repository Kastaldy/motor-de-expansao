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
import { alunos, brl, brlCurto, coord, num, pctFrac, rotuloMes } from '../lib/format'
import { formatarNumero } from '../lib/mascara'
import { infoImovelParaPdf, parametrosRelatorioPontual } from '../lib/report'
import type {
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
}

const DEMANDA_PASSO = 100

/** Ticket CHEIO do plano por nº de studios — tabela da planilha (Simulador!J9). */
const TICKET_POR_STUDIO = [147, 157, 167, 177] as const

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

   SEM PADRÃO PRÓPRIO, e por isso sem número anunciado como padrão:
     juros_equipamentos_am — o backend resolve `float(juros or 0.0)`, ou seja 0% a.m.
       O "1,8% a.m." é da planilha e do adaptador LEGADO (`viabilidade()` em
       dimensionamento/simulador.py), que esta rota não percorre. Afirmar 1,8 como
       padrão seria mentir — por isso ele entra como SUGESTÃO, ver o bloco abaixo.
     prazo_equipamentos — `int(... or 36) if equip > 0 else 0`: o 36 é condicional a
       haver equipamento; sem ele o padrão é 0. A faixa validada é ge=1, le=60.
     obra / equipamentos — o CAPEX padrão (SIM_CAPEX_DEFAULT) só entra com OS DOIS
       vazios; preenchendo um, o outro vira 0,0.
   --------------------------------------------------------------------------- */
const PADRAO_PARCELAS_OBRA = '4'
const PADRAO_PARCELAS_FRANQUIA = '4'
const PADRAO_TAXA_FRANQUIA = '160.000'
const PADRAO_CARENCIA = '0'
const PADRAO_TAXA_NEGOCIO = '25'

/* SUGESTAO x PADRAO — a distincao NAO e' cosmetica ---------------------------
   Acima, "padrao" e' o numero que o motor aplica quando o campo fica vazio, cada um
   conferido no backend. Abaixo sao SUGESTOES de ponto de partida (pedido de Juan,
   2026-08-05) que o motor NAO aplica:
     Obra / Equipamentos -> nao tem padrao proprio. O CAPEX so' entra com OS DOIS
       vazios; preenchendo um, o outro vira 0,0.
     Prazo financ.       -> o padrao real e' 36, nao 60.
     Juros equip.        -> o padrao real e' 0% (`float(juros or 0.0)` em
       `_investimento`). Os 1,8% da planilha vivem no adaptador legado
       `viabilidade()` de dimensionamento/simulador.py, que a rota web nao chama.
   O placeholder mostra SO' O NUMERO: "sugestao 1.500.000" nao cabia na caixa depois
   que o adorno da unidade passou a ocupar a direita dela (Juan, 2026-08-05: "sem a
   palavra sugestao, pois nao da' pra visualizar"). O preco assumido e' que estes
   quatro ficam visualmente iguais aos que anunciam padrao de verdade — a ressalva
   vive no `title` de cada campo, que nao disputa largura com o adorno.

   O risco que sobra, e que o `title` do juros deixa explicito: deixar o campo vazio
   vendo 1,8 na tela faz o calculo rodar SEM custo de financiamento — a PMT some do
   fluxo de caixa e o payback melhora sozinho. Quem quiser a sugestao, digita. */
const SUGESTAO_OBRA = '1.500.000'
const SUGESTAO_EQUIPAMENTOS = '1.200.000'
const SUGESTAO_PRAZO_EQUIP = '60'
const SUGESTAO_JUROS_EQUIP = '1,8'

/**
 * Placeholder = valor usado pelo motor no último cálculo; sem cálculo ainda, o texto
 * de reserva do chamador. Formatado por `formatarNumero` (e não por `num`) de
 * propósito: é a MESMA grafia que o campo mostraria se o número fosse digitado — sem
 * zero à direita, com a mesma vírgula.
 *
 * Serve aos campos cujo padrão do motor É o número certo a anunciar (parcelas, taxa de
 * franquia, carência, taxa mínima). Para os quatro campos de SUGESTÃO existe `fixa()`.
 */
function dica(usado: number | null | undefined, reserva: string, casas = 0): string {
  return formatarNumero(usado, casas) || reserva
}

/**
 * Placeholder que NÃO ecoa o motor: a sugestão fica de pé antes e depois do cálculo.
 *
 * Existe porque, nestes quatro campos, o valor "usado" engana. Obra e Equipamentos não
 * têm padrão próprio: com os dois vazios o motor aplica o CAPEX compartilhado
 * (2.340.000, app.py:1357) e devolve isso como `investimento.obra` — então, depois do
 * primeiro cálculo, a caixa da Obra passava a anunciar 2.340.000 como se fosse a
 * referência, apagando a sugestão e escondendo que preencher um dos dois zera o outro.
 * Prazo e juros têm o mesmo problema em menor escala (o eco vira 36 e 0).
 */
function fixa(sugestao: string): string {
  return sugestao
}

export default function ViabilityScreen({
  ponto,
  onVoltar,
  onInicio,
}: ViabilityScreenProps) {
  // --- Cenário -------------------------------------------------------------
  const [m2, setM2] = useState(1500)
  const [aluguel, setAluguel] = useState(20000)
  // Ticket CHEIO = mensalidade R$/mês do plano de balcão (P2-12). O ticket médio
  // (blended, com o mix de agregadores) é somente-leitura e vem do motor. Coerente
  // com studios=0 (planilha: 0→147); mudar Studios reajusta, dá para editar depois.
  const [ticket, setTicket] = useState<number>(TICKET_POR_STUDIO[0])
  const [demanda, setDemanda] = useState(800)
  // A demanda vem padronizada no p50 da metragem e re-escala quando a metragem
  // muda — até o operador mexer no ±, aí a mão dele prevalece (DEC-009: premissa).
  const [demandaTocada, setDemandaTocada] = useState(false)
  const [faixa, setFaixa] = useState<FaixaAlunos | null>(null)
  // Rampa de maturação (Simulador E13; padrão 8). Controlável na sidebar: alonga
  // a curva de alunos e o fluxo de caixa (afeta payback), não a margem steady.
  const [rampaMeses, setRampaMeses] = useState(8)
  // Studios extras (0..3): cada studio adiciona R$6.000/mês de folha (reduz EBITDA).
  const [nStudios, setNStudios] = useState(0)

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

  function montarPayload(demandaUsar: number): ViabilidadeIn {
    return {
      lat: alvoLat!,
      lng: alvoLng!,
      m2,
      aluguel,
      ticket,
      demanda: demandaUsar,
      n_studios: nStudios,
      obra,
      parcelas_obra: parcelasObra,
      equipamentos: equip,
      prazo_equipamentos: prazoEquip,
      // % a.m. digitado -> FRAÇÃO (o contrato do payload). Conversão de UNIDADE; não é
      // derivação de número financeiro. `undefined` atravessa intacto para a chave
      // sumir do JSON — dividir `undefined` por 100 daria NaN e viraria `null`.
      juros_equipamentos_am: jurosEquip !== undefined ? jurosEquip / 100 : undefined,
      carencia_aluguel_meses: carencia,
      rampa_meses: rampaMeses,
      taxa_franquia: taxaFranquia,
      parcelas_franquia: parcelasFranquia,
      // % a.a. digitado -> FRAÇÃO, mesma conversão de unidade.
      taxa_minima_negocio_aa: taxaNegocio !== undefined ? taxaNegocio / 100 : undefined,
    }
  }

  async function calcular(demandaUsar: number = demanda) {
    if (!ponto) return
    setCalculando(true)
    setErro(null)
    try {
      const r = await api.viabilidade(montarPayload(demandaUsar))
      setRes(r)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao calcular a viabilidade.')
    } finally {
      setCalculando(false)
    }
  }

  // Ao chegar num ponto: busca a faixa da metragem, semeia a demanda no p50 e
  // calcula — a tela nunca abre vazia nem com o 800 fixo antigo.
  useEffect(() => {
    if (!ponto) return
    let vivo = true
    setDemandaTocada(false)
    ;(async () => {
      let seed = demanda
      try {
        const f = await api.faixaAlunos(m2)
        if (!vivo) return
        setFaixa(f)
        if (f.p50 != null) seed = Math.round(f.p50)
      } catch {
        /* sem faixa: mantém a demanda atual */
      }
      if (vivo) {
        setDemanda(seed)
        void calcular(seed)
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
        if (!demandaTocada && f.p50 != null) setDemanda(Math.round(f.p50))
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

  async function gerarPdf() {
    if (!ponto) return
    setGerandoPdf(true)
    setErro(null)
    try {
      const { blob, filename } = await api.relatorioPontual({
        // Coordenada do estudo + rótulo + AVISO DE ORIGEM saem prontos de
        // `parametrosRelatorioPontual` (lib/report.ts), que é onde essa decisão pode
        // ser testada. Ela responde às duas coisas pela MESMA regra de `lib/coord.ts`:
        // qual coordenada usar e se o PDF precisa avisar que ela é o CENTROIDE do
        // hexágono (a até ~1,5 km), e não um endereço. Aqui a tela só repassa.
        ...parametrosRelatorioPontual(ponto, { rotuloManual: info.nome }),
        // Metragem/aluguel vêm do Cenário e as chaves são remapeadas para o contrato
        // do PDF (senão o imóvel saía "n/d" mesmo preenchido — lib/report.ts).
        infoImovel: infoImovelParaPdf(info, { m2, aluguel }),
        // SÓ os inputs do cenário: o backend roda o motor UMA vez e monta o payload
        // inteiro (números + gráficos) por conta própria. Não reenviamos o payload
        // calculado — ele tem 70 KB (série de 64 meses + grade) e estourava a query
        // string em HTTP 431. Ver o comentário em lib/api.ts::relatorioPontual.
        viabilidadeInputs: res ? montarPayload(demanda) : undefined,
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
    if (!ponto) return
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

  // TUDO abaixo é LEITURA do viabilidade_payload_v1. A tela não deriva número
  // financeiro nenhum: o motor (dimensionamento/simulador.py) já entregou pronto.
  const premissas = res?.premissas ?? null
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
    teto && teto.ideal != null && teto.teto != null && teto.excecao != null
      ? aluguel <= teto.ideal
        ? { label: 'dentro do ideal', tone: 'var(--pos-text)' }
        : aluguel <= teto.teto
          ? { label: 'no teto', tone: 'var(--warn-text)' }
          : aluguel <= teto.excecao
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
      {/* ---------------- Header ---------------- */}
      <header
        style={{
          margin: '16px 16px 0',
          padding: '9px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          background: 'var(--surf-chrome)',
          border: '1px solid var(--line-soft)',
          borderRadius: 'var(--r-xl)',
          backdropFilter: 'blur(14px)',
          flexWrap: 'wrap',
        }}
      >
        <BotaoInicio onInicio={onInicio} />
        <h1 style={{ font: '600 15px/1 var(--f-ui)', color: 'var(--tx-max)', margin: 0 }}>
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
          ↩ vindo do mapa · {ponto.rotulo}
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
          style={{
            width: 346,
            flexShrink: 0,
            overflowY: 'auto',
            padding: '18px 18px 22px',
            background: 'var(--surf-sidebar)',
            border: '1px solid var(--line-soft)',
            borderRadius: 'var(--r-2xl)',
            backdropFilter: 'blur(14px)',
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
                maxDigitos={7}
                min={0}
                step={1000}
                prefixo="R$"
                rotulo="Aluguel em reais por mês"
                title="Aluguel pedido, em R$/mês. Use ↑/↓ para variar de 1.000 em 1.000."
              />
            </Campo>
          </div>

          <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
            <Campo label="Ticket cheio do plano" sufixo="/mês">
              <CampoNumero
                valor={ticket}
                onValor={setTicket}
                maxDigitos={4}
                min={0}
                step={5}
                prefixo="R$"
                rotulo="Ticket cheio do plano, em reais por mês"
                title="Mensalidade cheia do plano de balcão, em R$/mês. Use ↑/↓ para variar de 5 em 5."
              />
            </Campo>
            <Campo label="Studios" sufixo="0–3">
              <input
                type="number"
                value={nStudios}
                min={0}
                max={3}
                step={1}
                onChange={(e) => {
                  const n = Math.max(0, Math.min(3, Math.round(Number(e.target.value) || 0)))
                  setNStudios(n)
                  setTicket(TICKET_POR_STUDIO[n]) // studios elevam o ticket (planilha)
                }}
              />
            </Campo>
          </div>

          {/* Ticket médio (blended) — SOMENTE-LEITURA, vem do motor. O operador digita o
              cheio; o que entra no caixa por aluno TOTAL é este, com o mix e o ticket do
              agregador acoplado ao cheio (P2-12). */}
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
                  Mix {pctFrac(premissas.share_balcao, 0)} cheio (
                  {brl(premissas.ticket_cheio, false, 2)}) ·{' '}
                  {pctFrac(1 - premissas.share_balcao, 0)} agregador (
                  {brl(premissas.ticket_agregador, false, 2)}
                  {premissas.ticket_agregador_fator != null
                    ? `, ${pctFrac(premissas.ticket_agregador_fator, 0)} do cheio`
                    : ''}
                  ). Já líquido de churn e inadimplência. Calculado pelo motor — a tela só exibe.
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
            Ticket cheio = mensalidade do plano de balcão. Studios elevam o cheio (0→147, 1→157,
            2→167, 3→177); você pode ajustar manualmente depois.
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
                  color: demandaTocada ? 'var(--warn-text)' : 'var(--ac-text)',
                }}
              >
                {demandaTocada ? 'ajuste manual' : 'padrão · p50'}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {/* O numero grande saia sem unidade nenhuma ("800"). `alunos()` ja'
                  aplica o separador de milhar; faltava a palavra. */}
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
              <button
                type="button"
                aria-label="Diminuir demanda"
                onClick={() => {
                  setDemandaTocada(true)
                  setDemanda((d) => Math.max(100, d - DEMANDA_PASSO))
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
                  setDemanda((d) => d + DEMANDA_PASSO)
                }}
                style={stepper}
              >
                +
              </button>
            </div>
            <div
              style={{
                font: '400 10.5px/1.4 var(--f-ui)',
                color: 'var(--tx-sub)',
                marginTop: 8,
              }}
            >
              {faixa && faixa.p50 != null ? (
                <>
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
              ) : premissas ? (
                `Premissa explícita do operador, em alunos TOTAIS. Mix: ${pctFrac(
                  premissas.share_balcao,
                  0,
                )} balcão + ${pctFrac(1 - premissas.share_balcao, 0)} agregadores.`
              ) : (
                'Premissa explícita do operador, em alunos TOTAIS (balcão + agregadores).'
              )}
            </div>
          </div>

          {/* ---- Rampa de maturação (meses) ---- */}
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
                Rampa de maturação
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <button
                  type="button"
                  aria-label="Diminuir meses de rampa"
                  onClick={() => setRampaMeses((m) => Math.max(1, m - 1))}
                  style={stepper}
                >
                  −
                </button>
                <span
                  className="num"
                  style={{
                    font: '700 14px/1 var(--f-num)',
                    color: 'var(--tx-max)',
                    minWidth: 58,
                    textAlign: 'center',
                  }}
                >
                  {rampaMeses} {rampaMeses === 1 ? 'mês' : 'meses'}
                </span>
                <button
                  type="button"
                  aria-label="Aumentar meses de rampa"
                  onClick={() => setRampaMeses((m) => Math.min(36, m + 1))}
                  style={stepper}
                >
                  +
                </button>
              </div>
            </div>
            <div style={{ font: '400 10.5px/1.4 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 8 }}>
              Meses até o platô de alunos (Simulador E13, padrão 8). Alonga a curva de
              maturação e o fluxo de caixa; recalcule para atualizar o payback.
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
                maxDigitos={7}
                min={0}
                step={10000}
                prefixo="R$"
                rotulo="Obra, em reais"
                placeholder={fixa(SUGESTAO_OBRA)}
                title="Obra (equity do franqueado), em R$. O 1.500.000 da caixa é SUGESTÃO, não o padrão: Obra e Equipamentos não têm padrão próprio — com os dois vazios o motor usa um CAPEX único de 2.340.000, e preencher um zera o outro. Use as setas para variar de 10.000 em 10.000."
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
                maxDigitos={7}
                min={0}
                step={10000}
                prefixo="R$"
                rotulo="Equipamentos, em reais"
                placeholder={fixa(SUGESTAO_EQUIPAMENTOS)}
                title="Equipamentos (parcela financiada), em R$. O 1.200.000 da caixa é SUGESTÃO, não o padrão: vazio com a Obra preenchida vale ZERO equipamentos. Use as setas para variar de 10.000 em 10.000."
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
                placeholder={fixa(SUGESTAO_PRAZO_EQUIP)}
                title="Prazo do financiamento dos equipamentos, em meses (1 a 60). O 60 da caixa é SUGESTÃO; deixando vazio o motor usa 36. Sem equipamentos o prazo não tem efeito."
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
                placeholder={fixa(SUGESTAO_JUROS_EQUIP)}
                title="Juros do financiamento dos equipamentos, em % ao mês (aceita vírgula). ATENÇÃO: o 1,8 da caixa é SUGESTÃO — deixando vazio o motor calcula com 0% e o financiamento sai sem custo, o que melhora o payback artificialmente. Use as setas para variar de 0,1 em 0,1."
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
                maxDigitos={7}
                min={0}
                step={10000}
                prefixo="R$"
                rotulo="Taxa de franquia, em reais"
                placeholder={dica(inv?.taxa_franquia, PADRAO_TAXA_FRANQUIA)}
                title="Taxa de franquia, em R$. Vazio usa o padrão do modelo; digitar 0 é honrado como R$ 0."
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
            disabled={calculando}
            style={{ width: '100%', marginTop: 18, padding: 14, fontSize: 14 }}
          >
            {calculando ? 'Calculando…' : 'Recalcular viabilidade'}
          </Botao>

          <Botao
            variante="ghost"
            onClick={gerarPdf}
            disabled={gerandoPdf}
            style={{ width: '100%', marginTop: 10 }}
            title="Relatório Pontual Censitário 1,0 km com fotos, dados do imóvel e os números da viabilidade"
          >
            {gerandoPdf ? (
              <span style={carregando}>
                <Spinner /> Montando o relatório…
              </span>
            ) : (
              'Relatório completo em PDF ↓'
            )}
          </Botao>

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

          {/* Rótulo permanente: o modelo de viabilidade ainda está em calibração vs planilha. */}
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

          <Veredito
            aprovado={aprovado}
            margem={margem}
            demanda={demanda}
            breakEvenEbitda={beEbitda}
            breakEvenCaixa={beCaixa}
            payback={retorno?.payback ?? null}
            melhoria={res?.melhoria_payback ?? null}
          />

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
              valor={brl(aluguel, true)}
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

          <ReguaBreakEven
            demanda={demanda}
            breakEvenEbitda={beEbitda}
            breakEvenCaixa={beCaixa}
            p90={res?.faixa_alunos.p90 ?? faixa?.p90 ?? null}
          />

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
              <RampaAlunos serie={serie} maturacaoMeses={premissas?.maturacao_meses ?? null} />
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
                {res.flag_zona_morta && (res.motivo_zona_morta ?? 'Ponto sinalizado como zona morta.')}
              </p>
            </Glass>
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
