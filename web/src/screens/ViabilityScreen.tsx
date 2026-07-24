import { useEffect, useRef, useState } from 'react'

import type { PontoEscolhido } from '../App'
import {
  CascataDre,
  FluxoCaixa,
  FluxoCaixaOperacional,
  RampaAlunos,
  ReguaBreakEven,
  Veredito,
} from '../components/ViabilityCharts'
import { Aviso, Botao, Eyebrow, Glass, Kpi } from '../components/primitives'
import { api, ApiError, baixar } from '../lib/api'
import { coordenadaDoEstudo } from '../lib/coord'
import { alunos, brl, coord, num, pctFrac, rotuloMes } from '../lib/format'
import { infoImovelParaPdf } from '../lib/report'
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
}

const DEMANDA_PASSO = 100

/** Ticket CHEIO do plano por nº de studios — tabela da planilha (Simulador!J9). */
const TICKET_POR_STUDIO = [147, 157, 167, 177] as const

/**
 * Limiar apenas VISUAL do card de payback (espelha `SIM_PAYBACK_VIAVEL_MAX` do
 * config do motor). Não entra em conta nenhuma: quem dá o veredito de viabilidade
 * é o motor (`dre.flag_viavel`); aqui só decide a cor do número.
 */
const PAYBACK_ALVO_MESES = 36

/** Texto -> numero opcional (aceita virgula decimal e separador de milhar). */
function parseNum(txt: string): number | undefined {
  const s = txt.trim().replace(/\./g, '').replace(',', '.')
  if (!s) return undefined
  const n = Number(s)
  return Number.isFinite(n) ? n : undefined
}

export default function ViabilityScreen({ ponto, onVoltar }: ViabilityScreenProps) {
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
  // Obra = desembolso do franqueado, parcelado sem juros (base do ROIC/payback).
  const [obraTxt, setObraTxt] = useState('')
  const [parcelasObraTxt, setParcelasObraTxt] = useState('')
  // Equipamentos = financiado (36–60m + juros a.m.); a PMT entra abaixo do EBITDA
  // (dilui no tempo, melhora o payback). Padrão da planilha: 1,8% a.m.
  const [equipTxt, setEquipTxt] = useState('')
  const [prazoEquipTxt, setPrazoEquipTxt] = useState('')
  const [jurosEquipTxt, setJurosEquipTxt] = useState('')
  // Carência de aluguel: meses iniciais sem pagar aluguel (melhora payback/FCF).
  const [carenciaTxt, setCarenciaTxt] = useState('')
  // Taxa de franquia: R$160.000 é o padrão do motor, mas o operador pode sobrescrever
  // (decisão de Felipe, FIN-VIAB-01). Vazio = padrão; o payload devolve o valor usado.
  const [taxaFranquiaTxt, setTaxaFranquiaTxt] = useState('')

  // --- Dados opcionais do imóvel (entram no PDF completo) ------------------
  const [info, setInfo] = useState<InfoImovel>({})
  const [fotos, setFotos] = useState<File[]>([])

  const [res, setRes] = useState<ViabilidadeOut | null>(null)
  const [calculando, setCalculando] = useState(false)
  const [gerandoPdf, setGerandoPdf] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const inputFoto = useRef<HTMLInputElement>(null)

  // Coordenada do estudo: a EXATA quando o ponto veio da busca; o centroide do hexágono
  // só quando ele veio do clique no ranking (aí é a única que existe). Ver PontoEscolhido.
  const alvo = ponto ? coordenadaDoEstudo(ponto) : null
  const alvoLat = alvo?.lat
  const alvoLng = alvo?.lng

  function montarPayload(demandaUsar: number): ViabilidadeIn {
    const jurosEquip = parseNum(jurosEquipTxt)
    return {
      lat: alvoLat!,
      lng: alvoLng!,
      m2,
      aluguel,
      ticket,
      demanda: demandaUsar,
      n_studios: nStudios,
      obra: parseNum(obraTxt),
      parcelas_obra: parseNum(parcelasObraTxt),
      equipamentos: parseNum(equipTxt),
      prazo_equipamentos: parseNum(prazoEquipTxt),
      juros_equipamentos_am: jurosEquip !== undefined ? jurosEquip / 100 : undefined,
      carencia_aluguel_meses: parseNum(carenciaTxt),
      rampa_meses: rampaMeses,
      taxa_franquia: parseNum(taxaFranquiaTxt),
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
        lat: alvoLat!,
        lng: alvoLng!,
        rotulo: info.nome || ponto.rotulo,
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

  if (!ponto) {
    return (
      <Aviso
        titulo="Nenhum ponto escolhido ainda"
        corpo="A viabilidade testa um imóvel concreto. Volte ao mapa, chegue até a camada de recomendação e escolha um hexágono para trazer para cá."
        acao={<Botao onClick={onVoltar}>Voltar ao mapa</Botao>}
      />
    )
  }

  // TUDO abaixo é LEITURA do viabilidade_payload_v1. A tela não deriva número
  // financeiro nenhum: o motor (dimensionamento/simulador.py) já entregou pronto.
  const premissas = res?.premissas ?? null
  const dre = res?.dre ?? null
  const retorno = res?.retorno ?? null
  const serie = res?.serie_mensal ?? []
  /** margem EBITDA em FRAÇÃO (0,3873 = 38,73%) — o payload nunca manda percentual. */
  const margem = dre?.margem ?? null
  /** Break-even OPERACIONAL (EBITDA = 0), em alunos TOTAIS. */
  const beEbitda = res?.break_even.ebitda ?? null
  /** Break-even DE CAIXA (cobre também a PMT do financiamento), em alunos TOTAIS. */
  const beCaixa = res?.break_even.caixa ?? null
  const aprovado = margem !== null && margem > 0 && (beEbitda === null || demanda >= beEbitda)

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

          <div style={{ display: 'flex', gap: 10 }}>
            <Campo label="Metragem" sufixo="m²">
              <input
                type="number"
                value={m2}
                min={200}
                step={50}
                onChange={(e) => {
                  setM2(Number(e.target.value))
                  // Nova metragem re-escala a demanda: solta o override manual.
                  setDemandaTocada(false)
                }}
              />
            </Campo>
            <Campo label="Aluguel" sufixo="/mês">
              <input
                type="number"
                value={aluguel}
                min={0}
                step={1000}
                onChange={(e) => setAluguel(Number(e.target.value))}
              />
            </Campo>
          </div>

          <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
            <Campo label="Ticket cheio do plano" sufixo="/mês">
              <input
                type="number"
                value={ticket}
                min={0}
                step={5}
                onChange={(e) => setTicket(Number(e.target.value))}
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
                {premissas ? brl(premissas.ticket_blended, false, 2) : 'n/d'}
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
              <span
                className="num"
                style={{ font: '700 22px/1 var(--f-num)', color: 'var(--tx-max)', flex: 1 }}
              >
                {alunos(demanda)}
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
            base do retorno desalavancado e do payback. Vazio usa o padrão do modelo.
          </p>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              inputMode="numeric"
              placeholder="Obra (R$)"
              value={obraTxt}
              onChange={(e) => setObraTxt(e.target.value)}
            />
            <input
              inputMode="numeric"
              placeholder="Parcelas obra (meses)"
              value={parcelasObraTxt}
              onChange={(e) => setParcelasObraTxt(e.target.value)}
            />
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <input
              inputMode="numeric"
              placeholder="Equipamentos (R$)"
              value={equipTxt}
              onChange={(e) => setEquipTxt(e.target.value)}
            />
            <input
              inputMode="numeric"
              placeholder="Prazo financ. (meses)"
              value={prazoEquipTxt}
              onChange={(e) => setPrazoEquipTxt(e.target.value)}
            />
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <input
              inputMode="numeric"
              placeholder="Juros equip. (% a.m.)"
              value={jurosEquipTxt}
              onChange={(e) => setJurosEquipTxt(e.target.value)}
            />
            <input
              inputMode="numeric"
              placeholder="Carência aluguel (meses)"
              value={carenciaTxt}
              onChange={(e) => setCarenciaTxt(e.target.value)}
            />
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <input
              inputMode="numeric"
              placeholder="Taxa de franquia (R$)"
              value={taxaFranquiaTxt}
              onChange={(e) => setTaxaFranquiaTxt(e.target.value)}
            />
          </div>
          <span style={{ display: 'block', font: '400 10px/1.4 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 8 }}>
            A taxa de franquia é editável (vazio = padrão do modelo) e entra à vista no M-4,
            somando ao investimento. Obra = equity parcelada sem juros; equipamentos financiados
            (prazo + juros a.m.) entram como PMT no caixa mês a mês.
          </span>

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
              <ReadoutCapex
                rotulo="Investimento total"
                valor={brl(res.investimento.investimento_total, true)}
              />
              <ReadoutCapex
                rotulo="Taxa de franquia"
                valor={brl(res.investimento.taxa_franquia, true)}
              />
              <ReadoutCapex
                rotulo="PMT"
                valor={
                  res.investimento.pmt ? `${brl(res.investimento.pmt)}/mês` : 'sem financiamento'
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
            title="Relatório Pontual Censitário 1,5 km com fotos, dados do imóvel e os números da viabilidade"
          >
            {gerandoPdf ? 'Montando o relatório…' : 'Relatório completo em PDF ↓'}
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
            pendentes de gate: o nível da folha (17% do faturamento bruto, revisão no BLK-VIAB-11)
            e a taxa de desconto do VPL/TIR (12% a.a., provisória).
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
              tone={
                margem === null
                  ? undefined
                  : margem >= 0
                    ? 'var(--pos-text)'
                    : 'var(--neg)'
              }
            />
            {/* P2-15: "payback" é SÓ o retorno do capital. P0-4: TIR e VPL ao lado dele. */}
            <Kpi
              label="Payback do investimento"
              valor={retorno?.payback == null ? 'não atinge' : `${num(retorno.payback)} meses`}
              sub={
                retorno
                  ? `TIR ${pctFrac(retorno.tir_anual)} a.a. · VPL ${brl(retorno.vpl, true)}`
                  : 'retorno do capital investido'
              }
              tone={
                retorno?.payback == null
                  ? 'var(--neg)'
                  : retorno.payback <= PAYBACK_ALVO_MESES
                    ? 'var(--pos-text)'
                    : 'var(--warn-text)'
              }
            />
            {/* P0-4: a legenda estava "lucro anual + investimento" (o operador escreveu
                errado) e a ótica não aparecia. Padrão do produto = DESALAVANCADO. */}
            <Kpi
              label="Retorno anual (desalavancado)"
              valor={pctFrac(retorno?.retorno_anual_desalavancado)}
              sub="lucro anual / investimento total"
              tone={
                retorno?.retorno_anual_desalavancado == null
                  ? undefined
                  : retorno.retorno_anual_desalavancado >= 0
                    ? 'var(--pos-text)'
                    : 'var(--neg)'
              }
            />
            {/* P2-15: este é o indicador OPERACIONAL — não é payback. */}
            <Kpi
              label="1º mês com caixa operacional positivo"
              valor={
                res?.mes_caixa_operacional_positivo == null
                  ? 'não vira'
                  : `mês ${res.mes_caixa_operacional_positivo}`
              }
              sub={`e assim permanece até o mês ${premissas?.horizonte_meses ?? 60}`}
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
                  : 'n/d'
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
      <div className="num" style={{ font: '600 13px/1 var(--f-num)', color: 'var(--tx-soft)' }}>
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
