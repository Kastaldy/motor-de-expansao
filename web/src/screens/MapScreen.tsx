import { latLngToCell } from 'h3-js'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import type { PontoEscolhido } from '../App'
import HexMap, { type SearchPin, type ViewState } from '../components/HexMap'
import MethodologyPanel from '../components/MethodologyPanel'
import NarrativePanel from '../components/NarrativePanel'
import ScoreLegend from '../components/ScoreLegend'
import Select from '../components/Select'
import StepperBar from '../components/StepperBar'
import { Botao } from '../components/primitives'
import { api, ApiError, baixar } from '../lib/api'
import { parseCoordinate } from '../lib/coord'
import { alunos, coord, num } from '../lib/format'
import { chaveContexto, fotoAplicavel, type EstadoMapa } from '../lib/mapa-estado'
import type { Hex, MunicipioItem, MunicipioPayload } from '../lib/types'

/** Filtro global "melhores hexes": faixas M1 permitidas por nível. */
const FAIXA_FILTROS: Record<string, Set<string>> = {
  prioridade: new Set(['Prioridade máxima']),
  alta: new Set(['Prioridade máxima', 'Alta']),
  media: new Set(['Prioridade máxima', 'Alta', 'Média']),
}

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
  /**
   * Foto do mapa guardada pelo App. O `App` renderiza as telas por CONDICIONAL, entao
   * ir para a Viabilidade DESMONTA esta tela e mata todo o `useState` local: passo do
   * funil, hexagono selecionado, pin da busca, cenario multi-hex e a camera do deck.gl.
   * Era isso que fazia o mapa "resetar" na volta pelo breadcrumb "vindo do mapa".
   * A UF e o municipio nunca se perderam — moram no App desde sempre.
   */
  estadoInicial: EstadoMapa
  onEstado: (e: EstadoMapa) => void
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
  estadoInicial,
  onEstado,
}: MapScreenProps) {
  // A foto so' vale se tiver sido tirada NESTA uf/municipio — `fotoAplicavel` faz esse
  // portao (lib/mapa-estado). Sem ele, um pin de Sao Paulo reapareceria depois de um
  // drill-down em Campinas. `useState(() => ...)` roda so' na montagem: e' o unico
  // momento em que a foto e' consumida.
  const [foto] = useState(() => fotoAplicavel(estadoInicial, uf, municipio))

  // Todo estado abaixo NASCE da foto, nao de um valor fixo — e' o que devolve a tela
  // como estava quando o operador volta da Viabilidade.
  const [passoN, setPassoN] = useState(foto.passoN)
  const [metodologiaAberta, setMetodologiaAberta] = useState(false)
  const [selecionado, setSelecionado] = useState<string | null>(foto.selecionado)
  const [gerando, setGerando] = useState(false)
  const [aviso, setAviso] = useState<string | null>(null)

  // Busca por coordenada: solta um pin, marca o hexagono e habilita o estudo pontual.
  const [busca, setBusca] = useState(foto.busca)
  const [pin, setPin] = useState<SearchPin | null>(foto.pin)
  const [buscaErro, setBuscaErro] = useState<string | null>(null)
  const [buscando, setBuscando] = useState(false)

  // Filtro global: mostra só os melhores hexes (por faixa M1).
  const [filtroFaixa, setFiltroFaixa] = useState(foto.filtroFaixa)
  // Cenário multi-hex: seleção de vários hexes para somar.
  const [modoCenario, setModoCenario] = useState(foto.modoCenario)
  const [cenario, setCenario] = useState<string[]>(foto.cenario)
  const [copiado, setCopiado] = useState(false)

  // Camera do deck.gl em REF, nao em state, de proposito: o `onViewStateChange` do
  // deck dispara a cada quadro de um voo (centenas de vezes em 800 ms). Em state, cada
  // quadro re-renderizaria esta tela E o App inteiro (StepperBar, NarrativePanel,
  // MethodologyPanel...). Em ref, gravar e' de graca e a camera segue sempre atual.
  const cameraRef = useRef<ViewState | null>(foto.camera)

  // Estavel de proposito (`[]`): o HexMap tem `onCamera` nas dependencias do efeito que
  // publica a camera. Um callback inline mudaria de identidade a cada render e faria
  // aquele efeito disparar em todo render, nao so' quando a camera muda.
  const publicarCamera = useCallback((v: ViewState) => {
    cameraRef.current = v
  }, [])

  // Trocar de UF/município recomeça a história do passo 1 e limpa a busca/cenário.
  // O guarda por ref e' ESSENCIAL: sem ele o efeito rodaria tambem na MONTAGEM da tela
  // e apagaria na hora o estado que acabou de ser restaurado — o mapa continuaria
  // "resetando" na volta, so' que por outro caminho.
  const contextoAnterior = useRef(chaveContexto(uf, municipio))
  useEffect(() => {
    const contexto = chaveContexto(uf, municipio)
    if (contextoAnterior.current === contexto) return
    contextoAnterior.current = contexto
    setPassoN(1)
    setSelecionado(null)
    setPin(null)
    setBuscaErro(null)
    setBuscando(false)
    setFiltroFaixa('')
    setModoCenario(false)
    setCenario([])
    cameraRef.current = null
  }, [uf, municipio])

  // Espelho SEMPRE atual do estado, mantido num ref. Existe para o cleanup do efeito
  // abaixo poder ler valores frescos: um cleanup enxerga o closure do render em que foi
  // criado, entao ler as variaveis de estado direto ali guardaria uma foto velha.
  const estadoRef = useRef<EstadoMapa>(foto)
  useEffect(() => {
    estadoRef.current = {
      // O contexto viaja COM a foto: e' o que permite descarta-la depois se o operador
      // trocar de UF/municipio antes de voltar ao mapa.
      uf,
      municipio,
      passoN,
      selecionado,
      pin,
      busca,
      filtroFaixa,
      modoCenario,
      cenario,
      camera: cameraRef.current,
    }
  })

  // Publica a foto no App UMA vez, ao desmontar — que e' exatamente quando ela passa a
  // importar (o operador saiu para a Viabilidade). Publicar a cada mudanca faria o App
  // re-renderizar a arvore inteira a cada clique no mapa, sem ganho nenhum.
  // `onEstado` e' o `setEstadoMapa` do `useState` do App, cuja identidade o React
  // garante estavel — o efeito nao remonta e nao publica antes da hora.
  useEffect(() => {
    return () => onEstado(estadoRef.current)
  }, [onEstado])

  const passo = dados?.passos.find((p) => p.n === passoN) ?? dados?.passos[0] ?? null
  const nivelUf = dados?.nivel === 'uf'

  const porId = useMemo(
    () => new Map((dados?.hexes ?? []).map((h) => [h.id, h])),
    [dados],
  )

  // Municípios do dropdown: "Todos" (volta à UF) + lista alfabética.
  const opcoesMunicipio = useMemo(
    () => [
      { value: '', label: 'Todos os municípios' },
      ...[...municipios]
        .sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'))
        .map((m) => ({ value: m.nome, label: m.nome })),
    ],
    [municipios],
  )

  // Filtro global de "melhores hexes" por faixa M1 (aplicado ao mapa).
  const hexesFiltrados = useMemo(() => {
    const hs = dados?.hexes ?? []
    const permitidas = FAIXA_FILTROS[filtroFaixa]
    return permitidas ? hs.filter((h) => h.faixa != null && permitidas.has(h.faixa)) : hs
  }, [dados, filtroFaixa])

  // Agregação do cenário multi-hex (soma no cliente a partir dos hexes servidos).
  const resumoCenario = useMemo(() => {
    const hs = cenario.map((id) => porId.get(id)).filter(Boolean) as Hex[]
    if (!hs.length) return null
    const soma = (f: (h: Hex) => number | null) => hs.reduce((a, h) => a + (f(h) ?? 0), 0)
    const scores = hs.map((h) => h.censo).filter((v): v is number => v != null)
    return {
      n: hs.length,
      residual: soma((h) => h.oferta),
      pop: soma((h) => h.pop),
      conc: soma((h) => h.conc),
      scoreMedio: scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null,
    }
  }, [cenario, porId])

  function copiarCenario() {
    navigator.clipboard?.writeText(cenario.join('\n')).then(() => {
      setCopiado(true)
      setTimeout(() => setCopiado(false), 1500)
    })
  }

  function aplicarPonto(lat: number, lng: number) {
    const hexId = latLngToCell(lat, lng, 7)
    setBuscaErro(null)
    setPin({ lat, lng, hexId })
    setSelecionado(hexId)
  }

  async function buscarCoordenada() {
    const termo = busca.trim()
    if (!termo || buscando) return
    // 1) coordenada / link do Maps (offline, instantâneo)
    const c = parseCoordinate(termo)
    if (c) {
      aplicarPonto(c.lat, c.lng)
      return
    }
    // 2) endereço livre -> geocoding (Nominatim, DEC-010)
    setBuscando(true)
    setBuscaErro(null)
    try {
      const r = await api.geocode(termo)
      if (r.found && r.lat != null && r.lng != null) {
        aplicarPonto(r.lat, r.lng)
      } else {
        setBuscaErro(
          'Não encontrei esse endereço. Tente "lat, lng", um link do Google Maps ou um endereço mais completo.',
        )
        setPin(null)
      }
    } catch {
      setBuscaErro('Busca de endereço indisponível agora. Use "lat, lng" ou um link do Google Maps.')
    } finally {
      setBuscando(false)
    }
  }

  function estudoPontualDoPin() {
    if (!pin) return
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
      mun: null,
      cres_hex_taxa: null,
      cres_hex_classe: null,
    }
    onAnalisarPonto({
      hex,
      rotulo: coord(pin.lat, pin.lng),
      municipio: dados?.municipio ?? '',
      uf: dados?.uf ?? uf,
      // A coordenada BUSCADA viaja junto. `hex` aqui costuma ser o `real` do dataset,
      // cujo lat/lng é o CENTROIDE do hexágono — usá-lo no relatório tirava a foto de
      // satélite e o mapa de quadra de até ~1,5 km do imóvel (e, na orla, jogava o
      // ponto no mar -> "fora do Brasil"). O hexágono continua o mesmo: por construção
      // `latLngToCell(pin.lat, pin.lng, 7) === pin.hexId === hex.id`.
      lat: pin.lat,
      lng: pin.lng,
    })
  }

  async function gerarRelatorioMunicipal() {
    if (!dados || dados.nivel !== 'municipio' || !dados.municipio) return
    setGerando(true)
    setAviso(null)
    try {
      const { blob, filename } = await api.relatorioMunicipal(dados.uf, dados.municipio)
      baixar(blob, filename)
    } catch (e) {
      setAviso(e instanceof ApiError ? e.message : 'Não foi possível gerar o relatório.')
    } finally {
      setGerando(false)
    }
  }

  function analisar(hexId: string) {
    const h = porId.get(hexId)
    if (!h || !dados) return
    const item = dados.passos.flatMap((p) => p.itens).find((i) => i.hex_id === hexId)
    onAnalisarPonto({
      hex: h,
      rotulo: item?.titulo ?? dados.municipio ?? dados.uf,
      municipio: dados.municipio ?? '',
      uf: dados.uf,
    })
  }

  // ---------------- Porta de entrada: escolha de estado ----------------
  if (!uf) {
    return <Landing ufs={ufs} onUf={onUf} />
  }

  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column' }}>
      {/* ---------------- Mapa ao fundo ---------------- */}
      {dados && passo && (
        <HexMap
          hexes={hexesFiltrados}
          passo={passo}
          cresMun={dados.cres_mun}
          centro={dados.centro}
          municipio={dados.municipio ?? undefined}
          uf={dados.uf}
          pins={dados.pins}
          selecionado={modoCenario ? null : selecionado}
          cenario={cenario}
          cameraInicial={foto.camera}
          onCamera={publicarCamera}
          onSelecionar={(h) => {
            setPin(null)
            if (modoCenario) {
              setCenario((cs) =>
                cs.includes(h.id) ? cs.filter((x) => x !== h.id) : [...cs, h.id],
              )
            } else {
              setSelecionado(h.id)
            }
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
          <span className="num" style={{ font: '500 11px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
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
          <span className="num" style={{ font: '500 11px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
            MUNICÍPIO
          </span>
          <Select
            label="Município"
            value={municipio}
            onChange={onMunicipio}
            maxWidth={210}
            options={opcoesMunicipio}
          />
        </label>

        {/* Saida VISIVEL do drill-down. Voltar a' visao do estado ja era possivel,
            mas so' abrindo o seletor e achando "Todos os municipios" no meio da
            lista — caminho que existe e nao se anuncia (relato de Felipe,
            2026-07-31). So' aparece quando ha' municipio selecionado. */}
        {municipio && (
          <Botao
            variante="ghost"
            onClick={() => onMunicipio('')}
            title="Voltar à visão do estado inteiro"
            style={{ padding: '6px 11px', font: '600 11.5px/1 var(--f-ui)', whiteSpace: 'nowrap' }}
          >
            ← Todos os municípios
          </Botao>
        )}

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
            stroke={buscando ? 'var(--ac)' : 'var(--tx-muted)'}
            strokeWidth="1.8"
            strokeLinecap="round"
            aria-hidden
            style={buscando ? { animation: 'pulse 1s ease-in-out infinite' } : undefined}
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
            placeholder={buscando ? 'Buscando endereço…' : 'Buscar endereço, coordenada ou link'}
            aria-label="Buscar por endereço ou coordenada"
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

        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="num" style={{ font: '500 11px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
            MELHORES
          </span>
          <Select
            label="Filtrar pelos melhores hexes"
            value={filtroFaixa}
            onChange={setFiltroFaixa}
            maxWidth={150}
            options={[
              { value: '', label: 'Todos os hexes' },
              { value: 'prioridade', label: 'Prioridade máxima' },
              { value: 'alta', label: 'Alta ou +' },
              { value: 'media', label: 'Média ou +' },
            ]}
          />
        </label>

        {/* Manual do funil. Ao lado do MELHORES e ANTES do `flex:1`: ocupa a folga do
            meio, entao o bloco de metricas segue ancorado na borda direita.

            A quebra do header em duas linhas a 100% de zoom NAO vem daqui — a 1280 px
            logicos (notebook Full HD com escala 150% do Windows, padrao de fabrica)
            todos os paineis da tela quebram, com ou sem este botao. E' aperto geral de
            layout, assunto separado. */}
        <Botao
          variante="ghost"
          onClick={() => setMetodologiaAberta((v) => !v)}
          title="Metodologia — o que cada camada mede e onde corta"
          style={{
            padding: '6px 11px',
            font: '600 11.5px/1 var(--f-ui)',
            whiteSpace: 'nowrap',
            ...(metodologiaAberta
              ? { color: 'var(--ac)', borderColor: 'var(--ac)', background: 'var(--ac-a12)' }
              : {}),
          }}
        >
          Metodologia
        </Botao>

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
            <Metrica rotulo="espaço p/ academias" valor={num(dados.resumo.espaco_academias)} destaque />
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
            {!nivelUf && (
              <div
                style={{
                  pointerEvents: 'auto',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                  maxWidth: 280,
                }}
              >
                <button
                  type="button"
                  onClick={() => {
                    if (modoCenario) setCenario([])
                    setModoCenario((m) => !m)
                    setSelecionado(null)
                  }}
                  style={{
                    alignSelf: 'flex-start',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    background: modoCenario ? 'var(--ac-a16)' : 'var(--surf-panel)',
                    border: `1px solid ${modoCenario ? 'var(--ac-a30)' : 'var(--line-soft)'}`,
                    borderRadius: 'var(--r-md)',
                    padding: '8px 11px',
                    font: '600 12px/1 var(--f-ui)',
                    color: modoCenario ? 'var(--ac-text)' : 'var(--tx-soft)',
                    backdropFilter: 'blur(16px)',
                  }}
                >
                  {modoCenario ? '◆ Comparando hexes' : '◇ Comparar vários hexes'}
                </button>

                {modoCenario && (
                  <div
                    style={{
                      background: 'var(--surf-panel)',
                      border: '1px solid var(--ac-a30)',
                      borderRadius: 'var(--r-md)',
                      padding: '11px 13px',
                      backdropFilter: 'blur(16px)',
                      minWidth: 232,
                    }}
                  >
                    <div style={{ font: '700 12px/1 var(--f-ui)', color: 'var(--tx-max)' }}>
                      Cenário multi-hex · {resumoCenario?.n ?? 0} hex
                    </div>
                    {resumoCenario ? (
                      <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 5 }}>
                        <LinhaC rotulo="Residual somado" valor={`${alunos(resumoCenario.residual)} alunos`} forte />
                        <LinhaC rotulo="População" valor={num(resumoCenario.pop)} />
                        <LinhaC rotulo="Score censo médio" valor={num(resumoCenario.scoreMedio, 1)} />
                        <LinhaC rotulo="Concorrentes 2 km" valor={num(resumoCenario.conc)} />
                      </div>
                    ) : (
                      <p style={{ margin: '8px 0 0', font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)' }}>
                        Clique nos hexágonos do mapa para somar residual, população e score.
                      </p>
                    )}
                    {resumoCenario && (
                      <div style={{ marginTop: 11, display: 'flex', gap: 8 }}>
                        <button
                          type="button"
                          onClick={() => setCenario([])}
                          style={botaoGhost}
                        >
                          Limpar
                        </button>
                        <button type="button" onClick={copiarCenario} style={botaoGhost}>
                          {copiado ? 'Copiado ✓' : 'Copiar IDs'}
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            <ScoreLegend passoN={passo.n} />
          </div>
        )}

        <div style={{ pointerEvents: 'auto', display: 'flex', minHeight: 0 }}>
          {carregando && !dados ? (
            <PainelMensagem>
              {nivelUf || !municipio
                ? `Lendo o território de ${uf}…`
                : `Lendo ${municipio}…`}{' '}
              A primeira leitura de uma UF carrega a partição inteira e pode levar alguns segundos.
            </PainelMensagem>
          ) : erro ? (
            <PainelMensagem>
              {erro}
              <br />
              <br />O backend do piloto responde na porta 8899. Se você abriu o app sem ele, feche e
              use o <code>iniciar-piloto-web.cmd</code>.
            </PainelMensagem>
          ) : dados && passo ? (
            <NarrativePanel
              passo={passo}
              hexes={dados.hexes}
              totalPassos={dados.passos.length}
              selecionado={selecionado}
              onSelecionarHex={setSelecionado}
              onAnalisar={analisar}
              onDrillMunicipio={onMunicipio}
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
            onIr={(n) => setPassoN(Math.min(dados.passos.length, Math.max(1, n)))}
            onGerarRelatorio={gerarRelatorioMunicipal}
            gerando={gerando}
            nivelUf={nivelUf}
          />
        </div>
      )}

      {/* Gaveta da metodologia. Ultima na arvore e com zIndex acima do header para
          cobrir o chrome do mapa; o mapa em si continua visivel a' esquerda. */}
      <MethodologyPanel
        aberto={metodologiaAberta}
        onFechar={() => setMetodologiaAberta(false)}
        passoAtivo={passoN}
        escopo={nivelUf ? 'uf' : 'municipio'}
      />
    </div>
  )
}

/* ---------------- Porta de entrada: hero + seletor de estado ---------------- */

function Landing({ ufs, onUf }: { ufs: string[]; onUf: (uf: string) => void }) {
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'grid',
        placeItems: 'center',
        padding: 24,
        background:
          'radial-gradient(120% 90% at 50% 30%, var(--bg-lift) 0%, var(--bg-base) 72%)',
      }}
    >
      <div style={{ maxWidth: 560, textAlign: 'center' }}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            font: '600 11px/1 var(--f-ui)',
            letterSpacing: '.14em',
            textTransform: 'uppercase',
            color: 'var(--ac-text)',
          }}
        >
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--ac)' }} />
          Inteligência de Expansão · Ultra Academia
        </span>

        <h1
          className="story"
          style={{
            font: '400 44px/1.05 var(--f-story)',
            color: 'var(--tx-max)',
            margin: '18px 0 0',
            letterSpacing: '.005em',
          }}
        >
          Por onde a Ultra deve crescer?
        </h1>

        <p
          style={{
            font: '400 15px/1.6 var(--f-ui)',
            color: 'var(--tx-narrative)',
            margin: '16px auto 0',
            maxWidth: 460,
          }}
        >
          Comece escolhendo um <strong style={{ color: 'var(--tx-strong)' }}>estado</strong>. O mapa
          lê o território inteiro e monta a sequência de camadas — do potencial socioeconômico até os
          municípios com mais espaço para abrir.
        </p>

        <div
          style={{
            marginTop: 30,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 12,
            padding: '14px 16px',
            background: 'var(--surf-panel)',
            border: '1px solid var(--ac-a30)',
            borderRadius: 'var(--r-lg)',
            backdropFilter: 'blur(16px)',
            boxShadow: 'var(--ac-glow)',
          }}
        >
          <span style={{ font: '600 13px/1 var(--f-ui)', color: 'var(--tx-soft)' }}>
            Selecione um estado
          </span>
          {ufs.length ? (
            <Select
              label="Escolha um estado para começar"
              value=""
              onChange={onUf}
              maxWidth={260}
              buscavel
              placeholder="Escolha…"
              options={ufs.map((u) => ({ value: u, label: u }))}
            />
          ) : (
            <span className="num" style={{ font: '500 12px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
              carregando estados…
            </span>
          )}
        </div>

        <p
          style={{
            font: '400 11.5px/1.5 var(--f-ui)',
            color: 'var(--tx-sub)',
            margin: '18px 0 0',
          }}
        >
          27 estados · Censo 2022 (IBGE) + rede Ultra e concorrentes mapeados · camada visual read-only
        </p>
      </div>
    </div>
  )
}

const botaoGhost: React.CSSProperties = {
  flex: 1,
  padding: '7px 10px',
  borderRadius: 8,
  border: '1px solid var(--line-soft)',
  background: 'var(--surf-raised)',
  color: 'var(--tx-soft)',
  font: '600 11.5px/1 var(--f-ui)',
}

/** Linha do resumo do CENARIO multi-hex. O `forte` continua turquesa de proposito:
 *  o cenario e' o unico bloco que pertence ao modo turquesa (botao "◆ Comparando
 *  hexes" + contorno turquesa do hex no mapa). Fora dele o turquesa nao significa
 *  mais "numero importante" — ver --l1..--l4 em tokens.css. */
function LinhaC({ rotulo, valor, forte }: { rotulo: string; valor: string; forte?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14 }}>
      <span style={{ font: '400 11.5px/1 var(--f-ui)', color: 'var(--tx-label)' }}>{rotulo}</span>
      <span
        className="num"
        style={{
          font: `${forte ? 700 : 500} 12px/1 var(--f-num)`,
          color: forte ? 'var(--ac-text)' : 'var(--tx-soft)',
        }}
      >
        {valor}
      </span>
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
        // Largura igual nos três cards (o rótulo "espaço p/ academias" é o mais
        // largo; sem isto ele fica maior que os outros — pedido do Felipe).
        width: 116,
        flexShrink: 0,
        boxSizing: 'border-box',
        padding: '6px 8px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 4,
        // O destaque e' FORMA, nao matiz: fundo neutro + regra vertical. Em turquesa
        // este card usava a mesma familia do numero do funil (numero mono turquesa em
        // caixa turquesa fraca) para grandezas opostas — aqui um TOTAL fixo do
        // territorio, la' o CONTADOR da camada ativa. No passo 2, em que o funil
        // tambem fala de residual, o olho concluia que eram o mesmo numero em dois
        // lugares (relato de Juan, 2026-08-04: "leva o usuario a entender q sao as
        // mesmas coisas").
        //
        // A regra ja' foi `--ultra` (vermelho da marca) e `--info` (azul), e as duas
        // erraram pelo mesmo motivo: TODA matiz deste tema ja' significa outra coisa.
        // Vermelho e' alerta, e este numero e' oportunidade (Juan, 2026-08-05: "deixar
        // um azul para nao levar o usuario a entender q e' algo ruim"). Azul e' a
        // camada 1, e ai' o card passou a parecer parente do Potencial socioeconomico
        // (Juan, 2026-08-05: "o azul leva a entender q o potencial de socio e espaco
        // sao a mesma coisa").
        //
        // Restam violeta (camada 2), ambar (camada 3), turquesa (acao e camada 4) e
        // verde (positivo, e ainda por cima e' o topo da rampa de score do mapa). Nao
        // ha' matiz livre — entao o destaque fica SEM matiz: regra clara e neutra.
        // Ausencia de cor nao afirma parentesco com camada nenhuma, que era o defeito
        // comum das duas tentativas. Quem diz "este e' o numero em destaque" continua
        // sendo o par regra + fundo levantado, e nao o hue.
        background: destaque ? 'var(--surf-pending)' : 'transparent',
        borderLeft: destaque ? '2px solid var(--tx-max)' : undefined,
      }}
    >
      <div
        className="num"
        style={{
          font: '700 18px/1 var(--f-num)',
          // Neutro tambem no destaque: --ultra da' 3,26:1, serve como regra
          // grafica e reprova como cor de texto (mais ainda no rotulo de 8px).
          color: 'var(--tx-max)',
        }}
      >
        {valor}
      </div>
      <div
        style={{
          font: '600 8px/1 var(--f-ui)',
          color: 'var(--tx-label)',
          textTransform: 'uppercase',
          letterSpacing: '.05em',
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
