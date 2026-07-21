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
import { alunos, brl, coord, num, pct } from '../lib/format'
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

/** Ticket (mensalidade) por nº de studios — tabela da planilha (Simulador!J9). */
const TICKET_POR_STUDIO = [147, 157, 167, 177] as const

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
  // Ticket = mensalidade R$/mês por aluno pagante do balcão. Coerente com studios=0
  // (planilha: 0→147). Mudar Studios reajusta o ticket; pode editar manualmente.
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

  // --- Dados opcionais do imóvel (entram no PDF completo) ------------------
  const [info, setInfo] = useState<InfoImovel>({})
  const [fotos, setFotos] = useState<File[]>([])

  const [res, setRes] = useState<ViabilidadeOut | null>(null)
  const [calculando, setCalculando] = useState(false)
  const [gerandoPdf, setGerandoPdf] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const inputFoto = useRef<HTMLInputElement>(null)

  function montarPayload(demandaUsar: number): ViabilidadeIn {
    const jurosEquip = parseNum(jurosEquipTxt)
    return {
      lat: ponto!.hex.lat,
      lng: ponto!.hex.lng,
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
        lat: ponto.hex.lat,
        lng: ponto.hex.lng,
        rotulo: info.nome || ponto.rotulo,
        infoImovel: info,
        viabilidade: res
          ? {
              demanda_premissa: res.demanda_premissa,
              alunos_breakeven: res.alunos_breakeven,
              // Relatório usa um teto único: o cluster "Teto" (20% do faturamento).
              aluguel_teto: res.aluguel_teto?.teto ?? null,
              margem: res.dre.margem,
              ebitda: res.dre.ebitda,
              faturamento: res.dre.faturamento,
              m2,
              aluguel_pedido: aluguel,
            }
          : undefined,
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

  const margem = res?.dre.margem ?? null
  const be = res?.alunos_breakeven ?? null
  const aprovado = margem !== null && margem > 0 && (be === null || demanda >= be)

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
          {coord(ponto.hex.lat, ponto.hex.lng)}
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
            <Campo label="Ticket médio" sufixo="/mês">
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
          <span
            style={{
              display: 'block',
              font: '400 10px/1.4 var(--f-ui)',
              color: 'var(--tx-sub)',
              marginTop: 6,
            }}
          >
            Ticket = mensalidade por aluno. Studios elevam o ticket (0→147, 1→157, 2→167, 3→177);
            você pode ajustar o ticket manualmente depois.
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
              ) : (
                'Premissa explícita do operador. Split: balcão ~69% + agregadores ~31%.'
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
            base do ROIC e do payback (à vista). Vazio usa o padrão do modelo.
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
          <span style={{ display: 'block', font: '400 10px/1.4 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 8 }}>
            Taxa de franquia R$ 160.000 já entra no investimento. Carência = meses iniciais sem
            aluguel. Prazo/juros do equipamento (alavancagem) entram no 2º passo — hoje é à vista.
          </span>
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
              <ReadoutCapex rotulo="Payback" valor={res.dre.payback == null ? 'não atinge' : `${num(res.dre.payback)} meses`} />
              <ReadoutCapex rotulo="ROIC anual" valor={res.dre.roic == null ? 'n/d' : pct((res.dre.roic ?? 0) * 100)} />
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
            <strong style={{ fontWeight: 600 }}>Números preliminares — em calibração.</strong> A
            Viabilidade ainda está sendo ajustada à planilha financeira oficial (folha, split
            balcão/agregadores e alavancagem do financiamento pendentes). Use como leitura
            direcional, não como número final de comitê.
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
            breakeven={be}
            payback={res?.dre.payback ?? null}
            melhoria={res?.melhoria_payback ?? null}
          />

          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
            <Kpi
              label="Margem EBITDA"
              valor={pct(margem)}
              sub="no cenário assumido"
              tone={
                margem === null
                  ? undefined
                  : margem >= 0
                    ? 'var(--pos-text)'
                    : 'var(--neg)'
              }
            />
            <Kpi
              label="Payback"
              valor={
                res?.dre.payback == null ? 'não atinge' : `${num(res.dre.payback)} meses`
              }
              sub={
                res && (res.carencia_aluguel_meses ?? 0) > 0
                  ? `com ${res.carencia_aluguel_meses}m de carência`
                  : 'até o caixa virar'
              }
              tone={
                res?.dre.payback == null
                  ? 'var(--neg)'
                  : res.dre.payback <= 36
                    ? 'var(--pos-text)'
                    : 'var(--warn-text)'
              }
            />
            <Kpi
              label="ROIC anual"
              valor={res?.dre.roic == null ? 'n/d' : pct((res.dre.roic ?? 0) * 100)}
              sub="lucro anual ÷ investimento"
              tone={
                res?.dre.roic == null
                  ? undefined
                  : res.dre.roic >= 0
                    ? 'var(--pos-text)'
                    : 'var(--neg)'
              }
            />
            <Kpi
              label="Aluguel-teto"
              valor={tetoCls?.label ?? 'n/d'}
              sub={
                teto && teto.ideal != null && teto.teto != null && teto.excecao != null
                  ? `ideal ${brl(teto.ideal, true)} · teto ${brl(teto.teto, true)} · exc ${brl(teto.excecao, true)}`
                  : `pedido ${brl(aluguel, true)}`
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

          <ReguaBreakEven demanda={demanda} breakeven={be} />

          {/* Fluxo de caixa ao lado da rampa; a composição do resultado (agora com
              7 barras) fica embaixo, em largura total, com mais espaço. */}
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
            <div style={{ flex: 1.5, minWidth: 320, display: 'flex' }}>
              <FluxoCaixa
                serie={res?.fcf_serie ?? []}
                payback={res?.dre.payback ?? null}
                carencia={res?.carencia_aluguel_meses ?? 0}
              />
            </div>
            <div style={{ flex: 1, minWidth: 240, display: 'flex' }}>
              <RampaAlunos plateau={demanda} meses={rampaMeses} />
            </div>
          </div>

          <FluxoCaixaOperacional
            serie={res?.fco_serie ?? []}
            mesPositivo={res?.mes_operacao_positiva ?? null}
          />

          <CascataDre
            faturamento={res?.dre.faturamento ?? null}
            deducoes={res?.dre.deducoes ?? null}
            impostos={res?.dre.impostos ?? null}
            custos={res?.dre.custos ?? null}
            ebitda={res?.dre.ebitda ?? null}
            lucroLiquido={res?.dre.lucro_liquido ?? null}
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
