import { latLngToCell } from 'h3-js'
import { useEffect, useMemo, useState } from 'react'

import type { PontoEscolhido } from '../App'
import HexMap, { type SearchPin } from '../components/HexMap'
import NarrativePanel from '../components/NarrativePanel'
import ScoreLegend from '../components/ScoreLegend'
import Select from '../components/Select'
import StepperBar from '../components/StepperBar'
import { Aviso, Botao } from '../components/primitives'
import { api, ApiError, baixar } from '../lib/api'
import { parseCoordinate } from '../lib/coord'
import { alunos, coord, num } from '../lib/format'
import type { Hex, MunicipioItem, MunicipioPayload } from '../lib/types'

export interface MapScreenProps {
  ufs: string[]
  uf: string
  onUf: (uf: string) => void
  municipios: MunicipioItem[]
  municipio: string
  onMunicipio: (m: string) => void
  dados: MunicipioPayload | null
  carregando: boolean
  erro: string | null
  onAnalisarPonto: (p: PontoEscolhido) => void
}

export default function MapScreen({
  ufs,
  uf,
  onUf,
  municipios,
  municipio,
  onMunicipio,
  dados,
  carregando,
  erro,
  onAnalisarPonto,
}: MapScreenProps) {
  const [passoN, setPassoN] = useState(1)
  const [selecionado, setSelecionado] = useState<string | null>(null)
  const [gerando, setGerando] = useState(false)
  const [aviso, setAviso] = useState<string | null>(null)

  // Busca por coordenada: solta um pin, marca o hexagono e habilita o estudo pontual.
  const [busca, setBusca] = useState('')
  const [pin, setPin] = useState<SearchPin | null>(null)
  const [buscaErro, setBuscaErro] = useState<string | null>(null)

  // Trocar de municipio recomeça a história do passo 1 e limpa a busca.
  useEffect(() => {
    setPassoN(1)
    setSelecionado(null)
    setPin(null)
    setBuscaErro(null)
  }, [uf, municipio])

  function buscarCoordenada() {
    const c = parseCoordinate(busca)
    if (!c) {
      setBuscaErro('Não reconheci a coordenada. Use "lat, lng" ou um link do Google Maps.')
      setPin(null)
      return
    }
    const hexId = latLngToCell(c.lat, c.lng, 7)
    setBuscaErro(null)
    setPin({ lat: c.lat, lng: c.lng, hexId })
    setSelecionado(hexId)
  }

  function estudoPontualDoPin() {
    if (!pin) return
    // Se o hex buscado está no recorte carregado, usa os dados reais; senão,
    // um hex sintético só com a coordenada (a viabilidade e o Pontual são geo).
    const real = porId.get(pin.hexId)
    const hex: Hex = real ?? {
      id: pin.hexId,
      lat: pin.lat,
      lng: pin.lng,
      m1: null,
      censo: null,
      hib: null,
      res: null,
      oferta: null,
      sam: null,
      pop: null,
      renda: null,
      renda_dom: null,
      faixa: null,
      conc: 0,
      ultra: 0,
    }
    onAnalisarPonto({
      hex,
      rotulo: coord(pin.lat, pin.lng),
      municipio: dados?.municipio ?? '',
      uf: dados?.uf ?? uf,
    })
  }

  const passo = dados?.passos.find((p) => p.n === passoN) ?? dados?.passos[0] ?? null

  const porId = useMemo(
    () => new Map((dados?.hexes ?? []).map((h) => [h.id, h])),
    [dados],
  )

  // Municipios em ordem alfabetica no dropdown (a API os devolve por residual).
  const opcoesMunicipio = useMemo(
    () =>
      [...municipios]
        .sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'))
        .map((m) => ({ value: m.nome, label: m.nome })),
    [municipios],
  )

  async function gerarRelatorioMunicipal() {
    if (!dados) return
    setGerando(true)
    setAviso(null)
    try {
      const { blob, filename } = await api.relatorioMunicipal(dados.uf, dados.municipio)
      baixar(blob, filename)
    } catch (e) {
      setAviso(
        e instanceof ApiError ? e.message : 'Não foi possível gerar o relatório.',
      )
    } finally {
      setGerando(false)
    }
  }

  function analisar(hexId: string) {
    const h = porId.get(hexId)
    if (!h || !dados) return
    const item = dados.passos
      .flatMap((p) => p.itens)
      .find((i) => i.hex_id === hexId)
    onAnalisarPonto({
      hex: h,
      rotulo: item?.titulo ?? dados.municipio,
      municipio: dados.municipio,
      uf: dados.uf,
    })
  }

  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column' }}>
      {/* ---------------- Mapa ao fundo, ocupando tudo ---------------- */}
      {dados && passo && (
        <HexMap
          hexes={dados.hexes}
          passo={passo}
          centro={dados.centro}
          municipio={dados.municipio}
          uf={dados.uf}
          pins={dados.pins}
          selecionado={selecionado}
          onSelecionar={(h) => {
            setSelecionado(h.id)
            setPin(null)
          }}
          searchPin={pin}
        />
      )}

      {/* ---------------- Header ---------------- */}
      <header
        style={{
          position: 'relative',
          zIndex: 10,
          margin: '16px 16px 0',
          padding: '9px 12px',
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
        <h1
          style={{
            font: '600 14px/1 var(--f-ui)',
            letterSpacing: '-.01em',
            color: 'var(--tx-max)',
            margin: 0,
          }}
        >
          Inteligência de Expansão
        </h1>

        <Divisor />

        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span
            className="num"
            style={{ font: '500 11px/1 var(--f-num)', color: 'var(--tx-muted)' }}
          >
            UF
          </span>
          <Select
            label="Unidade federativa"
            value={uf}
            onChange={onUf}
            maxWidth={74}
            options={ufs.map((u) => ({ value: u, label: u }))}
          />
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
          <span
            className="num"
            style={{ font: '500 11px/1 var(--f-num)', color: 'var(--tx-muted)' }}
          >
            MUNICÍPIO
          </span>
          <Select
            label="Município"
            value={municipio}
            onChange={onMunicipio}
            maxWidth={200}
            options={opcoesMunicipio}
          />
        </label>

        <Divisor />

        {/* Lupa de busca por coordenada */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 7,
            background: 'var(--surf-input)',
            border: `1px solid ${buscaErro ? 'rgba(255,90,110,.5)' : 'var(--line)'}`,
            borderRadius: 9,
            padding: '6px 10px',
            minWidth: 210,
          }}
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="var(--tx-muted)"
            strokeWidth="1.8"
            strokeLinecap="round"
            aria-hidden
          >
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            value={busca}
            onChange={(e) => {
              setBusca(e.target.value)
              if (buscaErro) setBuscaErro(null)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') buscarCoordenada()
            }}
            placeholder="Buscar coordenada (lat, lng)"
            aria-label="Buscar por coordenada"
            style={{
              flex: 1,
              minWidth: 0,
              background: 'transparent',
              border: 'none',
              padding: 0,
              font: '500 12.5px/1 var(--f-ui)',
              color: 'var(--tx-strong)',
            }}
          />
          {pin && (
            <button
              type="button"
              aria-label="Limpar busca"
              onClick={() => {
                setPin(null)
                setBusca('')
                setSelecionado(null)
              }}
              style={{ color: 'var(--tx-muted)', font: '500 15px/1 var(--f-ui)', padding: 0 }}
            >
              ×
            </button>
          )}
        </div>

        <div style={{ flex: 1 }} />

        {dados && (
          <div
            style={{
              display: 'flex',
              alignItems: 'stretch',
              background: 'var(--surf-raised)',
              border: '1px solid var(--line-soft)',
              borderRadius: 'var(--r-lg)',
              overflow: 'hidden',
            }}
          >
            <Metrica rotulo="hexágonos" valor={num(dados.n_hex_total)} />
            <MetricaDivisor />
            <Metrica rotulo="residual" valor={alunos(dados.resumo.residual_total)} />
            <MetricaDivisor />
            <Metrica
              rotulo="espaço p/ academias"
              valor={num(dados.resumo.espaco_academias)}
              destaque
            />
          </div>
        )}
      </header>

      {buscaErro && (
        <div
          role="alert"
          style={{
            position: 'relative',
            zIndex: 10,
            margin: '8px 16px 0',
            padding: '8px 12px',
            width: 'fit-content',
            borderRadius: 'var(--r-md)',
            background: 'rgba(255,90,110,.12)',
            border: '1px solid rgba(255,90,110,.3)',
            color: 'var(--neg)',
            font: '500 12px/1.4 var(--f-ui)',
          }}
        >
          {buscaErro}
        </div>
      )}

      {/* ---------------- Corpo: painel + rodapé ---------------- */}
      <div
        style={{
          position: 'relative',
          zIndex: 10,
          flex: 1,
          display: 'flex',
          justifyContent: 'flex-end',
          padding: '14px 16px 0',
          minHeight: 0,
          pointerEvents: 'none',
        }}
      >
        {/* Legenda de score — no canto inferior esquerdo, acima do stepper. */}
        {dados && passo && (
          <div
            style={{
              position: 'absolute',
              left: 16,
              bottom: 10,
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
              pointerEvents: 'none',
            }}
          >
            {pin && (
              <div
                style={{
                  pointerEvents: 'auto',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  background: 'var(--surf-panel)',
                  border: '1px solid var(--ac-a30)',
                  borderRadius: 'var(--r-md)',
                  padding: '9px 11px',
                  backdropFilter: 'blur(16px)',
                  maxWidth: 340,
                }}
              >
                <span style={{ minWidth: 0 }}>
                  <span
                    className="num"
                    style={{ display: 'block', font: '600 12px/1 var(--f-num)', color: 'var(--tx-max)' }}
                  >
                    {coord(pin.lat, pin.lng)}
                  </span>
                  <span
                    className="num"
                    style={{ display: 'block', font: '400 10px/1.2 var(--f-num)', color: 'var(--tx-sub)', marginTop: 3 }}
                  >
                    hex {pin.hexId}
                  </span>
                </span>
                <button
                  type="button"
                  onClick={estudoPontualDoPin}
                  style={{
                    flexShrink: 0,
                    background: 'var(--ac)',
                    color: 'var(--ac-on)',
                    font: '700 12px/1 var(--f-ui)',
                    padding: '9px 12px',
                    borderRadius: 9,
                    boxShadow: 'var(--ac-glow)',
                  }}
                >
                  Estudo pontual →
                </button>
              </div>
            )}
            <ScoreLegend passoN={passo.n} />
          </div>
        )}

        <div style={{ pointerEvents: 'auto', display: 'flex', minHeight: 0 }}>
          {carregando && !dados ? (
            <PainelMensagem>
              Lendo a base de {uf}… A primeira leitura de uma UF carrega a partição
              inteira e pode levar alguns segundos.
            </PainelMensagem>
          ) : erro ? (
            <PainelMensagem>
              {erro}
              <br />
              <br />O backend do piloto responde na porta 8899. Se você abriu o app
              sem ele, feche e use o <code>iniciar-piloto-web.cmd</code>.
            </PainelMensagem>
          ) : dados && passo ? (
            <NarrativePanel
              passo={passo}
              hexes={dados.hexes}
              selecionado={selecionado}
              onSelecionarHex={setSelecionado}
              onAnalisar={analisar}
            />
          ) : null}
        </div>
      </div>

      {/* ---------------- Barra dos 4 passos ---------------- */}
      {dados && passo && (
        <div style={{ position: 'relative', zIndex: 10, padding: '14px 16px 16px' }}>
          {aviso && (
            <div
              role="alert"
              style={{
                marginBottom: 10,
                padding: '10px 14px',
                borderRadius: 'var(--r-md)',
                background: 'rgba(217,164,65,.14)',
                border: '1px solid rgba(217,164,65,.35)',
                color: 'var(--warn-text)',
                font: '500 12.5px/1.4 var(--f-ui)',
                display: 'flex',
                justifyContent: 'space-between',
                gap: 12,
                alignItems: 'center',
              }}
            >
              <span>{aviso}</span>
              <Botao variante="ghost" onClick={() => setAviso(null)} style={{ padding: '6px 10px' }}>
                Fechar
              </Botao>
            </div>
          )}
          <StepperBar
            passos={dados.passos}
            atual={passoN}
            onIr={(n) => setPassoN(Math.min(4, Math.max(1, n)))}
            onGerarRelatorio={gerarRelatorioMunicipal}
            gerando={gerando}
          />
        </div>
      )}

      {!dados && !carregando && !erro && (
        <div style={{ position: 'relative', zIndex: 10, flex: 1 }}>
          <Aviso
            titulo="Escolha um município para começar"
            corpo="O mapa lê os hexágonos da UF selecionada e monta a sequência de quatro camadas até a recomendação."
          />
        </div>
      )}
    </div>
  )
}

function Divisor() {
  return (
    <span
      aria-hidden
      style={{ width: 1, height: 20, background: 'var(--line-mid)', flexShrink: 0 }}
    />
  )
}

function Metrica({
  rotulo,
  valor,
  destaque,
}: {
  rotulo: string
  valor: string
  destaque?: boolean
}) {
  return (
    <div
      style={{
        padding: '6px 15px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 4,
        background: destaque ? 'var(--ac-a08)' : 'transparent',
      }}
    >
      <div
        className="num"
        style={{
          font: '700 18px/1 var(--f-num)',
          color: destaque ? 'var(--ac-text)' : 'var(--tx-max)',
        }}
      >
        {valor}
      </div>
      <div
        style={{
          font: '600 9px/1 var(--f-ui)',
          color: destaque ? 'var(--ac-text)' : 'var(--tx-label)',
          textTransform: 'uppercase',
          letterSpacing: '.06em',
          whiteSpace: 'nowrap',
        }}
      >
        {rotulo}
      </div>
    </div>
  )
}

function MetricaDivisor() {
  return (
    <span
      aria-hidden
      style={{ width: 1, background: 'var(--line-soft)', alignSelf: 'stretch' }}
    />
  )
}

function PainelMensagem({ children }: { children: React.ReactNode }) {
  return (
    <aside
      style={{
        width: 394,
        padding: '22px 20px',
        background: 'var(--surf-panel)',
        border: '1px solid var(--line-soft)',
        borderRadius: 'var(--r-2xl)',
        backdropFilter: 'blur(18px)',
        font: '400 13px/1.6 var(--f-ui)',
        color: 'var(--tx-narrative)',
        alignSelf: 'flex-start',
      }}
    >
      {children}
    </aside>
  )
}
