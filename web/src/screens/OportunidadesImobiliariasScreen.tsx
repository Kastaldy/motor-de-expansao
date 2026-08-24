import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Map, Marker } from 'react-map-gl/maplibre'

import IconeTipo from '../components/IconeTipo'
import Select from '../components/Select'
import { Aviso, Botao, Eyebrow, Glass, Spinner } from '../components/primitives'
import { api, ApiError, baixar } from '../lib/api'
import { SCORE_BANDS_HEX } from '../lib/colors'
import { brl, brlCurto, num } from '../lib/format'
import {
  ACC,
  ACC_08,
  ACC_10,
  ACC_12,
  ACC_24,
  ACC_30,
  ACC_GLOW,
  ACC_ON,
  ACC_TX,
  COR_TIPO,
  corTipo,
  custoOcup,
  labelFaixa,
  labelTipo,
  rsM2,
} from '../lib/imovel'
import { alternarVisita, lerVisitas } from '../lib/visitas'
import type { Oportunidade } from '../lib/types'

import 'maplibre-gl/dist/maplibre-gl.css'

/**
 * Aba OPORTUNIDADES IMOBILIARIAS — a camada de oferta dentro do piloto.
 *
 * Le o `viaveis.parquet` do coletor (imoveis de locacao ja joinados ao territorio) por
 * `/api/oportunidades`. Camada AGREGADA por `hex_id` (contato do corretor so' no
 * dossie, atras do Authelia).
 *
 * DESENHO: porte fiel do layout que o Claude Design gerou para esta aba
 * ("Oportunidades Imobiliarias (standalone).html"), adaptado aos tokens e fontes do
 * piloto (Instrument Serif / Instrument Sans / IBM Plex Mono) e alimentado por dado
 * REAL. Estrutura: header narrativo -> filtros por dropdown (escalam p/ 27 UFs) +
 * alternador Ranking/Mapa -> coluna esquerda com "3 melhores" (cards) + "restante"
 * (lista compacta) -> coluna direita com ficha (hero + 3 cards de metrica + scatter
 * ao lado do mini-mapa + acoes).
 */

const BASEMAP = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
const MAX_PINS = 160
/* Teto da rota `/api/oportunidades` (cap de 3.000 no servidor). Pedimos o teto porque
   uma UF inteira cabe folgada nele — a maior, SP, tem 1.501 imoveis. So' o recorte
   NACIONAL (4.003) estoura, e ai o hero diz que a lista esta capada. */
const TETO_ITENS = 3000

/* Paleta por tipo, rotulos, custo de ocupacao, R$/m² e o acento MAGENTA vivem em
   `lib/imovel` desde que a camada aparece tambem no Mapa Territorial (pontinhos +
   secao da ficha do hexagono): uma unica fonte para as duas telas. */

/** Agrupamento p/ a composicao e a legenda do scatter (loja funde em comercial). */
const GRUPOS = [
  { chave: 'galpao', rotulo: 'Galpão', cor: COR_TIPO.galpao, tipos: ['galpao'] },
  { chave: 'comercial', rotulo: 'Comercial/Loja', cor: COR_TIPO.comercial, tipos: ['comercial', 'loja'] },
  { chave: 'terreno', rotulo: 'Terreno', cor: COR_TIPO.terreno, tipos: ['terreno'] },
]

/** Rampa de SCORE (residual) — canonica do sistema (RESIDUAL_SCORE_BANDS). */
const corResidual = (v: number | null | undefined): string => {
  if (v == null || Number.isNaN(v)) return 'var(--tx-rank)'
  return SCORE_BANDS_HEX[Math.min(9, Math.max(0, Math.floor(v / 10)))]
}

function mediana(xs: (number | null | undefined)[]): number | null {
  const s = xs.filter((x): x is number => x != null && !Number.isNaN(x)).sort((a, b) => a - b)
  if (!s.length) return null
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

/** Faturamento projetado/mes = alunos p50 da curva tamanho->densidade (simulador de
 *  Viabilidade, servido pronto pelo backend em `fat_proj`) x ticket. NAO usa residual. */
const projFatDe = (o: Oportunidade): number | null => o.fat_proj ?? null

type Ordem = 'residual' | 'faturamento' | 'rs_m2' | 'area' | 'aluguel'
const ORDENS: { value: Ordem; label: string }[] = [
  { value: 'residual', label: 'Maior residual' },
  { value: 'faturamento', label: 'Maior faturamento (proj.)' },
  { value: 'rs_m2', label: 'Menor R$/m²' },
  { value: 'area', label: 'Maior área' },
  { value: 'aluguel', label: 'Menor aluguel' },
]

/* ======================= Tela ======================= */
export default function OportunidadesImobiliariasScreen({
  onInicio,
  onVerNoMapa,
  focoInicial = null,
  onFocoAplicado,
}: {
  onInicio: () => void
  onVerNoMapa: (uf: string, municipio: string, ponto?: { lat: number; lng: number; hexId: string }) => void
  /**
   * Imovel que deve abrir JA SELECIONADO — o caminho inverso do "Ver no Mapa
   * Territorial": o botao "Ver na aba de imoveis" da janela do imovel no mapa.
   * Viaja o OBJETO inteiro (nao so o id) de proposito: a rota nacional serve o
   * top-N por residual, e o imovel focado pode estar fora dele.
   */
  focoInicial?: Oportunidade | null
  /** Consome a intencao UMA vez, apos aplicar o foco (molde do `modoPendente` do App). */
  onFocoAplicado?: () => void
}) {
  const [itens, setItens] = useState<Oportunidade[] | null>(null)
  const [total, setTotal] = useState(0)
  /** Quantas existem NO RECORTE pedido (a UF, ou o universo) — o denominador honesto. */
  const [totalRecorte, setTotalRecorte] = useState(0)
  /** UFs do UNIVERSO, vindas do payload. Ver `ufs` abaixo para o porquê. */
  const [ufsUniverso, setUfsUniverso] = useState<string[]>([])
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(true)
  /* O recorte NASCE na UF do imovel focado, e nao e' ajustado depois: assim o primeiro
     fetch ja' sai com `uf=` e o operador nao paga duas viagens (nacional -> UF). */
  const [ufSel, setUfSel] = useState(focoInicial?.uf ?? '')
  const [tipoSel, setTipoSel] = useState('')
  const [ordem, setOrdem] = useState<Ordem>('residual')
  const [busca, setBusca] = useState('')
  const [sel, setSel] = useState<string | null>(null)
  const [vistaEsq, setVistaEsq] = useState<'ranking' | 'mapa'>('ranking')
  const [visitas, setVisitas] = useState<Set<string>>(lerVisitas)
  const [soVisitas, setSoVisitas] = useState(false)

  /* Trilha de acesso (DEC-027): a ABERTURA da aba, uma vez por montagem. A tela
     desmonta ao sair (render condicional do App), entao voltar aqui e' uma abertura
     nova; o `ref` so' impede a contagem dobrada do StrictMode, que remonta o mesmo
     componente em dev. Nao ha UF no estado inicial, exceto quando o operador chega
     focando um imovel — ai o recorte ja' nasce na UF dele (ver o efeito abaixo). */
  const aberturaRegistrada = useRef(false)
  useEffect(() => {
    if (aberturaRegistrada.current) return
    aberturaRegistrada.current = true
    api.eventoImobiliaria('abrir-aba', { uf: focoInicial?.uf ?? null, origem: 'aba' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /* A intencao e' CONSUMIDA na MONTAGEM — nao no sucesso do fetch. Consumir so' no
     `.then` deixava o foco vivo no App quando a rota falhava ou o operador saia antes
     da resposta, e uma abertura futura da aba (pelo Dock, dias depois) aplicava um foco
     fantasma. Mesmo idioma do `modoPendente` do App: a intencao vale para ESTA entrada.
     O objeto fica no ref para o PRIMEIRO fetch usar — os refetches por UF nao podem
     reaplicar o foco, senao trocar de estado sequestraria a selecao de volta. */
  const focoPendente = useRef<Oportunidade | null>(focoInicial)
  useEffect(() => {
    if (focoInicial) onFocoAplicado?.()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /* O recorte e' SERVER-SIDE: trocar de UF refaz o fetch com `uf=`, e o backend filtra
     ANTES de aplicar o cap. Antes disso a tela baixava o top-500 NACIONAL e filtrava
     local — e como o residual satura em 100,0 para 44% do universo, o corte caia dentro
     do empate e tres UFs inteiras (RJ, PR, SC) eram INALCANCAVEIS pela aba, junto com
     87,5% dos imoveis e 185 dos 203 dossies que existem. Pedimos o TETO da rota (3.000)
     porque uma UF inteira cabe folgada nele (a maior, SP, tem 1.501). */
  useEffect(() => {
    let vivo = true
    setCarregando(true)
    setErro(null)
    api
      .oportunidades(ufSel || undefined, TETO_ITENS)
      .then((r) => {
        if (!vivo) return
        /* O foco vindo do mapa pode estar FORA do recorte que a rota serve: o proprio
           objeto viaja na intencao e entra no conjunto — senao "Ver na aba de imoveis"
           abriria a tela com OUTRO imovel selecionado. */
        const foco = focoPendente.current
        const itensComFoco =
          foco && !r.itens.some((i) => i.id === foco.id) ? [...r.itens, foco] : r.itens
        setItens(itensComFoco)
        setTotal(r.total)
        setTotalRecorte(r.total_recorte ?? r.total)
        setUfsUniverso(r.ufs)
        if (foco) {
          setSel(foco.id)
          focoPendente.current = null // consumido: refetch por UF nao reaplica
        } else {
          /* Seleciona o 1o do recorte novo. Automatico: NAO passa por
             `selecionarImovel`, entao nao vira rastro (DEC-037). */
          setSel(r.itens[0]?.id ?? null)
        }
      })
      .catch((e: ApiError) => vivo && setErro(e.message))
      .finally(() => {
        if (vivo) setCarregando(false)
      })
    return () => {
      vivo = false
    }
  }, [ufSel])

  /* O seletor de UF vem do UNIVERSO (payload), nunca dos itens carregados. Derivar dos
     itens tinha duas consequencias: (a) o seletor mostrava so' as UFs que caíram no
     recorte — 3 de 6 —, e (b) escolher uma UF encolhia o proprio seletor a um item,
     tornando impossivel voltar para outra. */
  const ufs = ufsUniverso
  const tipos = useMemo(
    () => Array.from(new Set((itens ?? []).map((o) => o.tipo).filter(Boolean))).sort(),
    [itens],
  )

  const filtrados = useMemo(() => {
    /* SEM filtro por UF aqui: o recorte de estado e' SERVER-SIDE (ver o fetch acima).
       Filtrar de novo aqui seria inocuo hoje e uma armadilha amanha — esconderia o
       imovel focado vindo do mapa se ele fosse de outra UF. */
    let xs = itens ?? []
    if (tipoSel) xs = xs.filter((o) => o.tipo === tipoSel)
    if (soVisitas && visitas.size) xs = xs.filter((o) => visitas.has(o.id))
    if (busca.trim()) {
      const q = busca.trim().toLowerCase()
      xs = xs.filter((o) => `${o.titulo} ${o.bairro ?? ''} ${o.municipio}`.toLowerCase().includes(q))
    }
    const ord = [...xs]
    ord.sort((a, b) => {
      if (ordem === 'residual') return (b.residual ?? -1) - (a.residual ?? -1)
      if (ordem === 'faturamento') return (projFatDe(b) ?? -1) - (projFatDe(a) ?? -1)
      if (ordem === 'area') return (b.area ?? -1) - (a.area ?? -1)
      if (ordem === 'aluguel') return (a.aluguel ?? Infinity) - (b.aluguel ?? Infinity)
      return (rsM2(a) ?? Infinity) - (rsM2(b) ?? Infinity)
    })
    return ord
  }, [itens, tipoSel, busca, ordem, soVisitas, visitas])

  useEffect(() => {
    if (filtrados.length && !filtrados.some((o) => o.id === sel)) setSel(filtrados[0].id)
  }, [filtrados, sel])

  useEffect(() => {
    if (visitas.size === 0) setSoVisitas(false)
  }, [visitas])

  /**
   * Selecao por GESTO do operador (card, linha da lista, pin do mapa ou do mini-mapa).
   * O `setSel` cru fica nos caminhos AUTOMATICOS — foco vindo do mapa, primeiro item
   * do recorte ao carregar e a re-selecao quando o filtro derruba o item atual —, que
   * nao sao gesto e nao podem virar rastro.
   */
  function selecionarImovel(id: string) {
    setSel(id)
    const op = (itens ?? []).find((o) => o.id === id)
    api.eventoImobiliaria('abrir-imovel', {
      imovel: id,
      uf: op?.uf ?? null,
      municipio: op?.municipio ?? null,
      origem: 'aba',
    })
  }

  function aoAlternarVisita(op: Oportunidade) {
    // A acao carimbada e' o estado RESULTANTE do toggle, nao o atual.
    const marcando = !visitas.has(op.id)
    api.eventoImobiliaria(marcando ? 'marcar-visita' : 'desmarcar-visita', {
      imovel: op.id,
      uf: op.uf,
      municipio: op.municipio,
      origem: 'aba',
    })
    setVisitas((prev) => alternarVisita(prev, op.id))
  }

  /**
   * Trilha do RECORTE, sempre no handler do controle — nunca num efeito que observe
   * o estado do filtro: ali entrariam tambem as mudancas automaticas e cada
   * re-render, e a trilha viraria ruido. A BUSCA livre fica de fora de proposito
   * (seria um evento por tecla, e nem com debounce o termo digitado pagaria o
   * volume); o que importa e' o recorte que sobrou, ja' visivel nos outros campos.
   */
  function registrarFiltro(campo: string, valor: string, uf = ufSel) {
    api.eventoImobiliaria('filtrar', { uf: uf || null, origem: 'aba', detalhe: `${campo}=${valor}` })
  }

  const idxSel = filtrados.findIndex((o) => o.id === sel)
  const atual = idxSel >= 0 ? filtrados[idxSel] : null
  const medRsM2 = useMemo(() => mediana(filtrados.map((o) => rsM2(o))), [filtrados])
  const top3 = filtrados.slice(0, 3)
  const resto = filtrados.slice(3)

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header narrativo */}
      <header style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 24, padding: '20px 30px 14px' }}>
        <div style={{ minWidth: 0 }}>
          <Eyebrow dot cor={ACC}>Oferta imobiliária</Eyebrow>
          <h1 className="story" style={{ margin: '8px 0 0', font: '400 40px/1 var(--f-story)', letterSpacing: '-.01em', color: 'var(--tx-max)' }}>
            Oportunidades Imobiliárias
          </h1>
          <p style={{ margin: '9px 0 0', font: '400 13.5px/1.5 var(--f-ui)', color: 'var(--tx-narrative)', maxWidth: 640 }}>
            {itens == null ? (
              'Imóveis de locação coletados e cruzados com o território do M1.'
            ) : (
              <>
                <b className="num" style={{ color: 'var(--tx-strong)' }}>{num(total)}</b> imóveis de locação cruzados com o território do M1.{' '}
                <b className="num" style={{ color: ACC_TX }}>{num(filtrados.length)}</b> sobrevivem ao recorte atual.
                {totalRecorte > TETO_ITENS && (
                  <>
                    {' '}A lista carrega os <b className="num">{num(TETO_ITENS)}</b> primeiros por
                    residual, de <b className="num">{num(totalRecorte)}</b> — escolha um estado para
                    ver o recorte inteiro.
                  </>
                )}
              </>
            )}
          </p>
        </div>
        <button type="button" onClick={onInicio}
          style={{ flexShrink: 0, font: '600 12px/1 var(--f-ui)', color: 'var(--tx-soft)', border: '1px solid var(--line-strong)', borderRadius: 999, padding: '9px 15px', background: 'var(--surf-raised)', cursor: 'pointer' }}>
          ← Início
        </button>
      </header>

      {/* Filtros + alternador de vista */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', padding: '10px 30px', borderTop: '1px solid var(--line-soft)', borderBottom: '1px solid var(--line-soft)' }}>
        <Select label="Estado" value={ufSel} onChange={(v) => { setUfSel(v); registrarFiltro('uf', v || 'todos', v) }} placeholder="Todos os estados" maxWidth={188}
          options={[{ value: '', label: 'Todos os estados' }, ...ufs.map((u) => ({ value: u, label: u }))]} />
        <Select label="Tipo de imóvel" value={tipoSel} onChange={(v) => { setTipoSel(v); registrarFiltro('tipo', v || 'todos') }} placeholder="Todos os tipos" maxWidth={188}
          options={[{ value: '', label: 'Todos os tipos' }, ...tipos.map((t) => ({ value: t, label: labelTipo(t) }))]} />
        <Select label="Ordenar por" value={ordem} onChange={(v) => { setOrdem(v as Ordem); registrarFiltro('ordem', v) }} maxWidth={200} buscavel={false} options={ORDENS} />
        <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar bairro, cidade, título…" aria-label="Buscar oportunidade"
          style={{ flex: 1, minWidth: 170, maxWidth: 340, height: 34, padding: '0 12px', background: 'var(--surf-input)', border: '1px solid var(--line-mid)', borderRadius: 'var(--r-md)', color: 'var(--tx-strong)', font: '500 13px/1 var(--f-ui)' }} />
        {carregando && itens != null && (
          /* Refetch por UF: a lista antiga fica na tela (sem piscar) e o spinner diz que
             o recorte esta trocando. `itens == null` ja' cobre a PRIMEIRA carga abaixo. */
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, color: 'var(--tx-muted)', font: '500 12px/1 var(--f-ui)' }}>
            <Spinner /> trocando o recorte…
          </span>
        )}
        {visitas.size > 0 && (
          <button type="button" onClick={() => { setSoVisitas((v) => !v); registrarFiltro('marcados', soVisitas ? 'off' : 'on') }} aria-pressed={soVisitas}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 12px', borderRadius: 'var(--r-md)', cursor: 'pointer',
              border: `1px solid ${soVisitas ? 'rgba(233,192,122,.5)' : 'var(--line-mid)'}`,
              background: soVisitas ? 'rgba(233,192,122,.14)' : 'var(--surf-input)',
              color: soVisitas ? 'var(--warn-text)' : 'var(--tx-muted)', font: '600 12px/1 var(--f-ui)' }}>
            ★ Marcados <span className="num">{visitas.size}</span>
          </button>
        )}
        <SegVista vista={vistaEsq} onVista={setVistaEsq} />
      </div>

      {/* Corpo — a pagina rola; a coluna esquerda gruda no topo (como no design) */}
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, background: `radial-gradient(1100px 520px at 8% -6%, ${ACC_08}, transparent 55%)` }}>
        {itens == null && !erro && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 32, color: 'var(--tx-muted)' }}><Spinner /> Carregando oportunidades…</div>
        )}
        {erro && <Aviso titulo="Não deu para carregar" corpo={`${erro} — confira o backend na porta 8899 e o data/oportunidades/viaveis.parquet.`} />}
        {itens != null && filtrados.length === 0 && (
          <Aviso titulo="Nada no recorte" corpo="Nenhuma oportunidade bate com os filtros. Amplie o estado, o tipo ou limpe a busca." />
        )}

        {itens != null && filtrados.length > 0 && (vistaEsq === 'mapa' ? (
          /* Vista MAPA: mapa como principal + card lateral menor com o estudo do imovel */
          <div style={{ display: 'flex', gap: 16, padding: '16px 24px', height: '100%', minHeight: 0 }}>
            <div style={{ flex: 1, minWidth: 0, height: '100%' }}>
              <MapaRecorte pontos={filtrados} sel={sel} onSel={selecionarImovel} altura="100%" />
            </div>
            <aside style={{ width: 400, flexShrink: 0, overflowY: 'auto', minHeight: 0, display: 'flex', flexDirection: 'column', gap: 14 }}>
              {atual ? (
                <Ficha op={atual} rank={idxSel + 1} pares={filtrados} medRsM2={medRsM2}
                  visita={visitas.has(atual.id)} onVisita={() => aoAlternarVisita(atual)}
                  onSel={selecionarImovel} onVerNoMapa={onVerNoMapa} lateral />
              ) : (
                <Aviso titulo="Selecione uma oportunidade" corpo="Clique num ponto do mapa para ver o estudo." />
              )}
            </aside>
          </div>
        ) : (
          /* Vista RANKING: ranking a ESQUERDA (os "3 melhores" fixos + "restante do
             recorte" num quadrante com scroll proprio) + relatorio completo a DIREITA,
             fixo (rola so' internamente se transbordar). Rolar a lista nao move a ficha. */
          <div style={{ display: 'flex', gap: 20, padding: '16px 26px', height: '100%', minHeight: 0 }}>
            <aside style={{ width: 400, flexShrink: 0, display: 'flex', flexDirection: 'column', minHeight: 0, gap: 14 }}>
              <div style={{ flexShrink: 0 }}>
                <CabecalhoLista titulo="Os 3 melhores do recorte" nota="RESIDUAL × R$/M²" />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 9, marginTop: 11 }}>
                  {top3.map((o, i) => (
                    <CardTop key={o.id} pos={i + 1} op={o} ativo={o.id === sel} visita={visitas.has(o.id)} onClick={() => selecionarImovel(o.id)} />
                  ))}
                </div>
              </div>
              {resto.length > 0 && (
                <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', borderTop: '1px solid var(--line-soft)', paddingTop: 12 }}>
                  <div style={{ flexShrink: 0 }}>
                    <CabecalhoLista titulo="Restante do recorte" nota={`${num(resto.length)} imóveis`} sub />
                  </div>
                  <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', marginTop: 8, marginRight: -6, paddingRight: 6 }}>
                    {resto.map((o, i) => (
                      <LinhaRest key={o.id} pos={i + 4} op={o} ativo={o.id === sel} visita={visitas.has(o.id)} onClick={() => selecionarImovel(o.id)} />
                    ))}
                  </div>
                </div>
              )}
            </aside>
            <section style={{ flex: 1, minWidth: 0, minHeight: 0, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
              {atual ? (
                <Ficha op={atual} rank={idxSel + 1} pares={filtrados} medRsM2={medRsM2}
                  visita={visitas.has(atual.id)} onVisita={() => aoAlternarVisita(atual)}
                  onSel={selecionarImovel} onVerNoMapa={onVerNoMapa} />
              ) : (
                <Aviso titulo="Selecione uma oportunidade" corpo="Escolha um imóvel no ranking à esquerda para ver o estudo." />
              )}
            </section>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ======================= Alternador de vista ======================= */
function SegVista({ vista, onVista }: { vista: 'ranking' | 'mapa'; onVista: (v: 'ranking' | 'mapa') => void }) {
  const opc: { v: 'ranking' | 'mapa'; r: string }[] = [{ v: 'ranking', r: 'Ranking' }, { v: 'mapa', r: 'Mapa' }]
  return (
    <div style={{ display: 'flex', gap: 4, padding: 4, borderRadius: 'var(--r-md)', background: 'var(--surf-input)', border: '1px solid var(--line-mid)' }}>
      {opc.map((o) => {
        const on = vista === o.v
        return (
          <button key={o.v} type="button" onClick={() => onVista(o.v)}
            style={{ padding: '6px 14px', borderRadius: 7, border: 'none', cursor: 'pointer', font: `${on ? 600 : 500} 12px/1 var(--f-ui)`, color: on ? ACC_TX : 'var(--tx-muted)', background: on ? ACC_12 : 'transparent' }}>
            {o.r}
          </button>
        )
      })}
    </div>
  )
}

function CabecalhoLista({ titulo, nota, sub }: { titulo: string; nota: string; sub?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
      <h2 className="story" style={{ margin: 0, font: `400 ${sub ? 18 : 21}px/1.1 var(--f-story)`, color: sub ? 'var(--tx-soft)' : 'var(--tx-max)' }}>{titulo}</h2>
      <span className="num" style={{ font: '500 10px/1 var(--f-num)', letterSpacing: '.12em', color: 'var(--tx-sub)', whiteSpace: 'nowrap' }}>{nota}</span>
    </div>
  )
}

/* ======================= Card dos 3 melhores ======================= */
function CardTop({ pos, op, ativo, visita, onClick }: { pos: number; op: Oportunidade; ativo: boolean; visita: boolean; onClick: () => void }) {
  const tint = corTipo(op.tipo)
  const r = rsM2(op)
  return (
    <button type="button" onClick={onClick}
      style={{ width: '100%', textAlign: 'left', display: 'grid', gridTemplateColumns: '52px 1fr auto', gap: 14, alignItems: 'center', padding: 14, borderRadius: 'var(--r-xl)', cursor: 'pointer',
        background: 'var(--surf-card)', border: `1px solid ${ativo ? ACC_30 : 'var(--line)'}`, boxShadow: ativo ? ACC_GLOW : 'none' }}>
      <span style={{ width: 52, height: 52, borderRadius: 'var(--r-lg)', display: 'grid', placeItems: 'center', color: tint, background: `${tint}1f` }}>
        <IconeTipo tipo={op.tipo} tamanho={24} />
      </span>
      <span style={{ minWidth: 0 }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 4 }}>
          <span className="num" style={{ font: '600 10px/1 var(--f-num)', color: ACC_TX }}>#{pos}</span>
          <span style={{ width: 7, height: 7, borderRadius: 2, background: tint }} />
          <span style={{ font: '400 10.5px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>{labelTipo(op.tipo)}</span>
          {visita && <span title="Marcado para visita" style={{ color: 'var(--warn-text)', font: '400 11px/1 var(--f-ui)' }}>★</span>}
        </span>
        <span style={{ display: 'block', font: '600 14px/1.2 var(--f-ui)', color: 'var(--tx-strong)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{op.titulo}</span>
        <span className="num" style={{ display: 'block', font: '400 11px/1.3 var(--f-num)', color: 'var(--tx-sub)', marginTop: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {op.bairro ? `${op.bairro} · ` : ''}{op.area != null ? `${num(op.area)} m² · ` : ''}{r != null ? `R$ ${num(r, 0)}/m²` : op.municipio}
        </span>
      </span>
      <span style={{ textAlign: 'right' }}>
        <span className="num" style={{ display: 'block', font: '500 22px/1 var(--f-num)', color: corResidual(op.residual) }}>{op.residual != null ? num(op.residual, 0) : '—'}</span>
        <span className="num" style={{ display: 'block', font: '400 9px/1 var(--f-num)', letterSpacing: '.12em', color: 'var(--tx-rank)', marginTop: 3 }}>RESID.</span>
      </span>
    </button>
  )
}

/* ======================= Linha compacta (restante) ======================= */
function LinhaRest({ pos, op, ativo, visita, onClick }: { pos: number; op: Oportunidade; ativo: boolean; visita: boolean; onClick: () => void }) {
  const tint = corTipo(op.tipo)
  const r = rsM2(op)
  const larg = Math.max(4, Math.min(100, op.residual ?? 0))
  /* Quando a linha VIRA a selecionada sem clique do operador (foco vindo do mapa, ou a
     re-selecao do guard de filtros), ela pode estar fora da area visivel da lista — a
     ficha mostrava um imovel que a lista nao aparentava ter. `block: 'nearest'` nao
     move nada quando a linha ja esta visivel (o caso do clique manual). */
  const ref = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    if (ativo) ref.current?.scrollIntoView({ block: 'nearest' })
  }, [ativo])
  return (
    <button ref={ref} type="button" onClick={onClick}
      style={{ width: '100%', textAlign: 'left', display: 'grid', gridTemplateColumns: '20px 30px 1fr auto', gap: 10, alignItems: 'center', padding: '9px 8px', borderBottom: '1px solid var(--line-soft)', borderLeft: `2px solid ${ativo ? ACC : 'transparent'}`, background: ativo ? ACC_08 : 'transparent', cursor: 'pointer' }}>
      <span className="num" style={{ font: '500 10.5px/1 var(--f-num)', color: 'var(--tx-rank)', textAlign: 'right' }}>{pos}</span>
      <span style={{ width: 30, height: 30, borderRadius: 8, display: 'grid', placeItems: 'center', color: tint, background: `${tint}1c` }}>
        <IconeTipo tipo={op.tipo} tamanho={16} />
      </span>
      <span style={{ minWidth: 0 }}>
        <span style={{ display: 'block', font: '500 13px/1.2 var(--f-ui)', color: 'var(--tx-soft)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {op.titulo}{visita ? ' ' : ''}{visita && <span style={{ color: 'var(--warn-text)' }}>★</span>}
        </span>
        <span className="num" style={{ display: 'block', font: '400 10.5px/1.3 var(--f-num)', color: 'var(--tx-sub)', marginTop: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {op.bairro ? `${op.bairro} · ` : ''}{op.area != null ? `${num(op.area)} m² · ` : ''}{r != null ? `R$ ${num(r, 0)}/m²` : op.municipio}
        </span>
      </span>
      <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ width: 34, height: 4, borderRadius: 2, background: 'var(--surf-pending)', overflow: 'hidden' }}>
          <span style={{ display: 'block', height: '100%', width: `${larg}%`, background: corResidual(op.residual), borderRadius: 2 }} />
        </span>
        <span className="num" style={{ width: 22, textAlign: 'right', font: '500 12px/1 var(--f-num)', color: 'var(--tx-soft)' }}>{op.residual != null ? num(op.residual, 0) : '—'}</span>
      </span>
    </button>
  )
}

/* ======================= Ficha ======================= */
function Ficha({
  op, rank, pares, medRsM2, visita, onVisita, onSel, onVerNoMapa, lateral = false,
}: {
  op: Oportunidade
  rank: number
  pares: Oportunidade[]
  medRsM2: number | null
  visita: boolean
  onVisita: () => void
  onSel: (id: string) => void
  onVerNoMapa: (uf: string, municipio: string, ponto?: { lat: number; lng: number; hexId: string }) => void
  /** true = card lateral compacto da vista de Mapa: hero enxuto, sem o mini-mapa. */
  lateral?: boolean
}) {
  const tint = corTipo(op.tipo)
  const r = rsM2(op)
  const ocupacao = [op.aluguel, op.iptu, op.condominio].reduce<number>((s, v) => s + (v ?? 0), 0)
  const sobra = op.residual_total
  const atendido = op.sam != null && sobra != null ? Math.max(0, op.sam - sobra) : null
  const pctLivre = op.sam != null && op.sam > 0 && sobra != null ? Math.round((Math.min(sobra, op.sam) / op.sam) * 100) : null
  const alunosProj = op.alunos_p50 ?? null
  const projFat = op.fat_proj ?? null

  const [baixando, setBaixando] = useState(false)
  const [erroAcao, setErroAcao] = useState<string | null>(null)

  async function baixarDossie() {
    /* Registra ANTES de escolher o caminho: o gesto e' o mesmo ("quero o documento
       deste imovel"), e `detalhe` diz qual documento o operador recebeu — o dossie
       do coletor ou o Relatorio Pontual do endereco, que e' o fallback. */
    api.eventoImobiliaria('abrir-dossie', {
      imovel: op.id,
      uf: op.uf,
      municipio: op.municipio,
      origem: 'aba',
      detalhe: op.tem_dossie ? 'dossie' : 'relatorio-pontual',
    })
    setBaixando(true)
    setErroAcao(null)
    try {
      if (op.tem_dossie) {
        const { blob, filename } = await api.dossie(op.id)
        baixar(blob, filename)
      } else if (op.lat != null && op.lng != null) {
        const { blob, filename } = await api.relatorioPontual({ lat: op.lat, lng: op.lng, rotulo: `${op.titulo} — ${op.municipio}/${op.uf}` })
        baixar(blob, filename)
      } else {
        setErroAcao('Sem dossiê e sem coordenada para gerar o relatório do ponto.')
      }
    } catch (e) {
      setErroAcao(e instanceof ApiError ? e.message : 'Falha ao gerar o documento.')
    } finally {
      setBaixando(false)
    }
  }

  return (
    <>
      {/* Hero */}
      {lateral ? (
        <Glass style={{ padding: 15, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '46px 1fr auto', gap: 12, alignItems: 'center' }}>
            <span style={{ width: 46, height: 46, borderRadius: 'var(--r-md)', display: 'grid', placeItems: 'center', color: tint, background: `${tint}1f` }}>
              <IconeTipo tipo={op.tipo} tamanho={22} />
            </span>
            <div style={{ minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 2 }}>
                <span className="num" style={{ font: '600 10px/1 var(--f-num)', color: ACC_TX }}>#{rank}</span>
                <span style={{ width: 7, height: 7, borderRadius: 2, background: tint }} />
                <span style={{ font: '400 10.5px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>{labelTipo(op.tipo)}</span>
                {visita && <span title="Marcado para visita" style={{ color: 'var(--warn-text)', font: '400 11px/1 var(--f-ui)' }}>★</span>}
              </div>
              <div className="story" style={{ font: '400 19px/1.12 var(--f-story)', color: 'var(--tx-max)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{op.titulo}</div>
              <div style={{ font: '400 12px/1.35 var(--f-ui)', color: 'var(--tx-narrative)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{op.bairro ? `${op.bairro} · ` : ''}{op.municipio}/{op.uf}</div>
            </div>
            <span className="num" title={`Residual ${op.residual != null ? num(op.residual, 0) : '—'}/100`}
              style={{ width: 36, height: 36, borderRadius: 9, display: 'grid', placeItems: 'center', font: '700 13px/1 var(--f-num)', color: '#fff', background: corResidual(op.residual) }}>
              {op.residual != null ? num(op.residual, 0) : '—'}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            {op.faixa && <FaixaPill faixa={op.faixa} />}
            <span className="num" style={{ font: '400 10.5px/1 var(--f-num)', color: 'var(--tx-sub)' }}>{op.hex_id}{op.first_seen ? ` · desde ${op.first_seen}` : ''}</span>
          </div>
          <p style={{ margin: 0, font: '400 12.5px/1.5 var(--f-ui)', color: 'var(--tx-soft)' }}>{tese(op, sobra, atendido, pctLivre, r, medRsM2)}</p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 16px', paddingTop: 12, borderTop: '1px solid var(--line-soft)' }}>
            <HeroStat label="Área" valor={op.area == null ? '—' : num(op.area)} unidade="m²" />
            <HeroStat label="Aluguel" valor={op.aluguel == null ? '—' : num(op.aluguel)} unidade="R$/mês" />
            <HeroStat label="R$/m²" valor={r == null ? '—' : num(r, 0)} unidade="/mês" />
            <HeroStat label="Projeção fat." valor={projFat == null ? '—' : brlCurto(projFat)} unidade="/mês" cor="var(--pos-text)"
              nota={alunosProj != null ? `${num(alunosProj)} alunos p50/m²` : ''} />
          </div>
        </Glass>
      ) : (
        <article style={{ borderRadius: 'var(--r-2xl)', overflow: 'hidden', background: 'var(--surf-card)', border: '1px solid var(--line)', display: 'flex', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 220px', maxWidth: 300, minHeight: 260, position: 'relative', display: 'grid', placeItems: 'center', background: `radial-gradient(120% 90% at 30% 15%, ${tint}22 0%, transparent 70%)`, color: tint }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
              <IconeTipo tipo={op.tipo} tamanho={62} />
              <div className="num" style={{ font: '500 10px/1 var(--f-num)', letterSpacing: '.16em', color: tint }}>{labelTipo(op.tipo).toUpperCase()}</div>
            </div>
            <div className="num" style={{ position: 'absolute', top: 14, left: 14, padding: '5px 10px', borderRadius: 999, background: 'var(--surf-panel)', border: '1px solid var(--line-soft)', backdropFilter: 'blur(8px)', font: '500 9.5px/1 var(--f-num)', letterSpacing: '.1em', color: ACC_TX }}>
              #{rank} DO RECORTE
            </div>
          </div>
          <div style={{ flex: '3 1 340px', minWidth: 0, padding: '24px 26px 22px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap', marginBottom: 11 }}>
              {op.faixa && <FaixaPill faixa={op.faixa} />}
              {visita && <span className="num" style={{ font: '500 10px/1 var(--f-num)', letterSpacing: '.06em', color: 'var(--warn-text)', padding: '4px 9px', borderRadius: 999, background: 'rgba(233,192,122,.12)', border: '1px solid rgba(233,192,122,.3)' }}>★ MARCADO</span>}
              <span className="num" style={{ font: '400 10.5px/1 var(--f-num)', color: 'var(--tx-sub)' }}>{op.hex_id}{op.first_seen ? ` · listado desde ${op.first_seen}` : ''}</span>
            </div>
            <h2 className="story" style={{ margin: 0, font: '400 32px/1.1 var(--f-story)', letterSpacing: '-.01em', color: 'var(--tx-max)' }}>{op.titulo}</h2>
            <div style={{ margin: '8px 0 16px', font: '400 13px/1.4 var(--f-ui)', color: 'var(--tx-narrative)' }}>
              {op.bairro ? `${op.bairro} · ` : ''}{op.municipio}/{op.uf} · <span style={{ color: 'var(--tx-soft)' }}>{labelTipo(op.tipo)} para locação</span>
            </div>
            <p style={{ margin: '0 0 18px', font: '400 15px/1.6 var(--f-ui)', color: 'var(--tx-soft)', maxWidth: '60ch' }}>{tese(op, sobra, atendido, pctLivre, r, medRsM2)}</p>
            <div style={{ display: 'flex', gap: '22px 48px', flexWrap: 'wrap', paddingTop: 18, borderTop: '1px solid var(--line-soft)' }}>
              <HeroStat label="Área" valor={op.area == null ? '—' : num(op.area)} unidade="m²" nota={labelTipo(op.tipo)} />
              <HeroStat label="Aluguel" valor={op.aluguel == null ? '—' : num(op.aluguel)} unidade="R$/mês" nota={r != null ? `R$ ${num(r, 0)}/m²` : ''} />
              <HeroStat label="Custo de ocupação" valor={ocupacao > 0 ? num(ocupacao) : '—'} unidade="R$/mês" nota="com IPTU e condomínio" />
              <HeroStat label="Projeção de faturamento" valor={projFat == null ? '—' : brl(projFat, true)} unidade="/mês" cor="var(--pos-text)"
                nota={alunosProj != null ? `${num(alunosProj)} alunos (p50/m²) × R$ ${num(op.ticket_proj ?? 0)}` : 'sem base de m² p/ estimar'} />
            </div>
          </div>
        </article>
      )}

      {/* 3 cards de metrica */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14 }}>
        <CardCusto aluguel={op.aluguel} iptu={op.iptu} condominio={op.condominio} total={ocupacao} />
        <CardMercado sobra={sobra} atendido={atendido} sam={op.sam} pctLivre={pctLivre} />
        <CardCenso op={op} />
      </div>

      {/* Scatter (+ mini-mapa quando NAO e' a vista lateral do mapa) */}
      {lateral ? (
        <Glass style={{ padding: 16 }}>
          <TituloCard titulo="Onde este imóvel cai" nota="R$/M² × SOBRA" />
          <p style={{ margin: '4px 0 12px', font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)' }}>Alvo: canto superior esquerdo (barato por m², mercado sobrando).</p>
          <Scatter pontos={pares} sel={op.id} />
        </Glass>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14 }}>
          <Glass style={{ padding: 18 }}>
            <TituloCard titulo="Onde este imóvel cai" nota="R$/M² × SOBRA" />
            <p style={{ margin: '4px 0 12px', font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-sub)' }}>O alvo é o canto superior esquerdo: barato por m², mercado sobrando.</p>
            <Scatter pontos={pares} sel={op.id} />
          </Glass>
          <Glass style={{ padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '18px 18px 10px' }}>
              <TituloCard titulo="Localização" nota={op.hex_id.slice(0, 10).toUpperCase()} />
            </div>
            <div style={{ padding: '0 14px 14px', flex: 1 }}><MiniMapa op={op} pares={pares} onSel={onSel} /></div>
          </Glass>
        </div>
      )}

      {/* Acoes */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'stretch' }}>
        <Botao onClick={() => {
          api.eventoImobiliaria('ver-no-mapa', { imovel: op.id, uf: op.uf, municipio: op.municipio, origem: 'aba' })
          onVerNoMapa(op.uf, op.municipio, op.lat != null && op.lng != null ? { lat: op.lat, lng: op.lng, hexId: op.hex_id } : undefined)
        }} style={{ flex: 1, minWidth: 220, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, background: ACC, color: ACC_ON, boxShadow: ACC_GLOW }}>Ver no Mapa Territorial →</Botao>
        <Botao variante="ghost" onClick={baixarDossie} disabled={baixando} style={{ flex: 1, minWidth: 220, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
          title={op.tem_dossie ? 'Dossiê PDF do coletor (oferta + território)' : 'Sem dossiê pronto — gera o Relatório Pontual do endereço'}>
          {baixando ? <><Spinner /> Gerando…</> : op.tem_dossie ? '↓ Baixar dossiê (PDF)' : '↓ Relatório do ponto (PDF)'}
        </Botao>
        <Botao variante="ghost" onClick={onVisita} style={{ flex: 1, minWidth: 220, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, color: visita ? 'var(--warn-text)' : undefined }}>
          {visita ? '★ Marcado para visita' : '☆ Marcar para visita'}
        </Botao>
      </div>
      {erroAcao && <div style={{ font: '400 11.5px/1.4 var(--f-ui)', color: 'var(--neg)' }}>{erroAcao}</div>}

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 9, font: '400 11.5px/1.55 var(--f-ui)', color: 'var(--tx-sub)', maxWidth: '80ch' }}>
        <span style={{ color: ACC_TX, flexShrink: 0 }}>ⓘ</span>
        <span>Camada agregada por <span className="num">hex_id</span>, sem dado pessoal na tela. O contato do corretor vive no dossiê do coletor, servido sob acesso restrito.</span>
      </div>
    </>
  )
}

function tese(op: Oportunidade, sobra: number | null, atendido: number | null, pctLivre: number | null, r: number | null, med: number | null): ReactNode {
  if (op.residual == null && sobra == null) return 'Sem leitura de residual para este hexágono.'
  const partes: ReactNode[] = []
  if (sobra != null && sobra > 0) {
    partes.push(
      <span key="s">O hexágono ainda comporta <b className="num" style={{ color: ACC_TX }}>{num(sobra)}</b> alunos{atendido != null ? <> além dos <b className="num" style={{ color: 'var(--tx-soft)' }}>{num(atendido)}</b> já atendidos</> : ''}
        {pctLivre != null ? <> — <b style={{ color: 'var(--tx-max)' }}>{pctLivre}% do mercado potencial está livre</b></> : ''}. </span>,
    )
  } else if (sobra != null) {
    partes.push(<span key="s">Hexágono saturado: a oferta instalada já cobre o mercado potencial. </span>)
  }
  if (r != null && med != null) {
    const barato = r <= med
    partes.push(
      <span key="m">E o metro quadrado sai por <b className="num" style={{ color: barato ? 'var(--pos-text)' : 'var(--tx-soft)' }}>R$ {num(r, 0)}</b>, contra <b className="num">R$ {num(med, 0)}</b> de mediana no recorte.</span>,
    )
  }
  return <>{partes}</>
}

/* ======================= Cards de metrica ======================= */
function CardCusto({ aluguel, iptu, condominio, total }: { aluguel: number | null; iptu: number | null; condominio: number | null; total: number }) {
  const linhas = [
    { rotulo: 'Aluguel', v: aluguel, cor: ACC },
    { rotulo: 'IPTU', v: iptu, cor: 'var(--warn-text)' },
    { rotulo: 'Condomínio', v: condominio, cor: 'var(--tx-rank)' },
  ]
  return (
    <Glass style={{ padding: 18 }}>
      <RotuloMono>Custo de ocupação</RotuloMono>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, margin: '12px 0 14px' }}>
        <span style={{ font: '400 12px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>R$</span>
        <span className="num" style={{ font: '500 28px/1 var(--f-num)', color: 'var(--tx-max)' }}>{total > 0 ? num(total) : '—'}</span>
        <span style={{ font: '400 12px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>/mês</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {linhas.map((l) => {
          const pct = total > 0 && l.v != null ? Math.round((l.v / total) * 100) : 0
          return (
            <div key={l.rotulo} style={{ display: 'flex', alignItems: 'center', gap: 10, font: '400 12px/1 var(--f-ui)' }}>
              <span style={{ width: 74, color: 'var(--tx-label)' }}>{l.rotulo}</span>
              <span style={{ flex: 1, height: 6, borderRadius: 3, background: 'var(--surf-pending)', overflow: 'hidden' }}>
                <span style={{ display: 'block', height: '100%', width: `${pct}%`, background: l.cor, borderRadius: 3 }} />
              </span>
              <span className="num" style={{ width: 64, textAlign: 'right', color: 'var(--tx-soft)' }}>{l.v == null ? '—' : num(l.v)}</span>
            </div>
          )
        })}
      </div>
    </Glass>
  )
}

function CardMercado({ sobra, atendido, sam, pctLivre }: { sobra: number | null; atendido: number | null; sam: number | null; pctLivre: number | null }) {
  const temDado = sam != null && sam > 0 && sobra != null && pctLivre != null
  return (
    <Glass style={{ padding: 18, display: 'flex', gap: 16, alignItems: 'center' }}>
      {temDado ? (
        <div style={{ position: 'relative', width: 88, height: 88, flexShrink: 0, borderRadius: '50%', background: `conic-gradient(${ACC} 0 ${pctLivre}%, var(--surf-pending) ${pctLivre}% 100%)` }}>
          <div style={{ position: 'absolute', inset: 10, borderRadius: '50%', background: 'var(--bg-lift)', display: 'grid', placeItems: 'center', textAlign: 'center' }}>
            <div>
              <div className="num" style={{ font: '500 21px/1 var(--f-num)', color: ACC_TX }}>{pctLivre}<span style={{ fontSize: 11 }}>%</span></div>
              <div className="num" style={{ font: '400 8.5px/1 var(--f-num)', letterSpacing: '.1em', color: 'var(--tx-sub)', marginTop: 2 }}>SOBRA</div>
            </div>
          </div>
        </div>
      ) : (
        <div style={{ width: 88, height: 88, flexShrink: 0, borderRadius: '50%', background: 'var(--surf-pending)', display: 'grid', placeItems: 'center', color: 'var(--tx-rank)', font: '400 22px/1 var(--f-num)' }}>—</div>
      )}
      <div style={{ minWidth: 0 }}>
        <RotuloMono>Mercado que sobra</RotuloMono>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, margin: '10px 0 0', font: '400 12.5px/1 var(--f-ui)' }}>
          <LegLinha cor={ACC} rotulo="Sobra" valor={sobra == null ? '—' : num(sobra)} forte />
          <LegLinha cor="var(--tx-rank)" rotulo="Já atendido" valor={atendido == null ? '—' : num(atendido)} />
        </div>
        <div style={{ font: '400 11px/1.3 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 8 }}>{sam == null ? 'SAM indisponível' : `de ${num(sam)} alunos do SAM`}</div>
      </div>
    </Glass>
  )
}

function CardCenso({ op }: { op: Oportunidade }) {
  const cel = [
    { valor: op.pop == null ? '—' : num(op.pop), suf: '', rotulo: 'População' },
    { valor: op.renda_pc == null ? '—' : num(op.renda_pc), suf: ' R$', rotulo: 'Renda per capita' },
    { valor: op.censo_score == null ? '—' : num(op.censo_score, 0), suf: '/100', rotulo: 'Potencial (censo)' },
    { valor: op.n_ultra == null ? '—' : num(op.n_ultra), suf: '', rotulo: 'Unidades Ultra' },
  ]
  return (
    <Glass style={{ padding: 18 }}>
      <RotuloMono>Quem mora aqui <span style={{ color: 'var(--tx-rank)' }}>· Censo 2022</span></RotuloMono>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px 10px', marginTop: 14 }}>
        {cel.map((c) => (
          <div key={c.rotulo}>
            <div className="num" style={{ font: '500 18px/1 var(--f-num)', color: 'var(--tx-max)' }}>{c.valor}<span style={{ fontSize: 11, color: 'var(--tx-sub)' }}>{c.suf}</span></div>
            <div style={{ font: '400 11px/1.2 var(--f-ui)', color: 'var(--tx-label)', marginTop: 4 }}>{c.rotulo}</div>
          </div>
        ))}
      </div>
    </Glass>
  )
}

/* ======================= Scatter (aspecto fixo) ======================= */
function Scatter({ pontos, sel }: { pontos: Oportunidade[]; sel: string }) {
  const W = 360, H = 250, padL = 48, padR = 12, padT = 16, padB = 32
  const dados = pontos
    .map((o) => ({ id: o.id, x: rsM2(o), y: o.residual_total, tipo: o.tipo }))
    .filter((d): d is { id: string; x: number; y: number; tipo: string } => d.x != null && !Number.isNaN(d.x) && d.y != null && !Number.isNaN(d.y))
  if (dados.length < 3) {
    return <div style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-muted)', textAlign: 'center', padding: '18px 0' }}>Poucos pontos com preço e sobra de mercado para comparar neste recorte.</div>
  }
  const xsOrd = dados.map((d) => d.x).sort((a, b) => a - b)
  const ysOrd = dados.map((d) => d.y).sort((a, b) => a - b)
  const xMax = xsOrd[Math.floor(xsOrd.length * 0.95)] ?? xsOrd[xsOrd.length - 1] ?? 1
  const yMax = (ysOrd[Math.floor(ysOrd.length * 0.95)] ?? ysOrd[ysOrd.length - 1] ?? 1) || 1
  const xMed = xsOrd[Math.floor(xsOrd.length / 2)] ?? 0
  const yMed = ysOrd[Math.floor(ysOrd.length / 2)] ?? 0
  const px = (x: number) => padL + (Math.min(x, xMax) / xMax) * (W - padL - padR)
  const py = (y: number) => padT + (1 - Math.min(y, yMax) / yMax) * (H - padT - padB)
  const selD = dados.find((d) => d.id === sel)
  const eixoX = [0, Math.round(xMax / 2), Math.round(xMax)]
  const eixoY = [0, Math.round(yMax / 2), Math.round(yMax)]
  const gruposPresentes = GRUPOS.filter((g) => dados.some((d) => g.tipos.includes(d.tipo)))
  // Declutter: amostra uniforme dos pontos (preserva a forma da nuvem) + sempre o selecionado.
  const LIM_PONTOS = 45
  let plot = dados
  if (dados.length > LIM_PONTOS) {
    const passo = dados.length / LIM_PONTOS
    const amostra: typeof dados = []
    for (let i = 0; i < dados.length; i += passo) amostra.push(dados[Math.floor(i)])
    if (selD && !amostra.some((d) => d.id === selD.id)) amostra.push(selD)
    plot = amostra
  }
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block', height: 'auto', maxHeight: 320 }} preserveAspectRatio="xMidYMid meet">
        {/* zona alvo: barato (x < mediana) e sobra alta (y > mediana) */}
        <rect x={px(0)} y={py(yMax)} width={px(xMed) - px(0)} height={py(yMed) - py(yMax)} fill={ACC} fillOpacity={0.1} />
        <line x1={px(xMed)} y1={py(yMax)} x2={px(xMed)} y2={py(yMed)} stroke={ACC} strokeOpacity={0.4} strokeWidth="1" strokeDasharray="3 3" />
        <line x1={px(0)} y1={py(yMed)} x2={px(xMed)} y2={py(yMed)} stroke={ACC} strokeOpacity={0.4} strokeWidth="1" strokeDasharray="3 3" />
        <text x={px(0) + 6} y={py(yMax) + 12} style={{ font: '400 9px var(--f-num)', letterSpacing: '.08em', fill: ACC_TX }}>ZONA ALVO</text>
        <line x1={padL} y1={padT} x2={padL} y2={H - padB} stroke="var(--line-mid)" strokeWidth="1" />
        <line x1={padL} y1={H - padB} x2={W - padR} y2={H - padB} stroke="var(--line-mid)" strokeWidth="1" />
        {eixoY.map((v, i) => <text key={`y${v}-${i}`} x={padL - 6} y={py(v) + 3} textAnchor="end" style={{ font: '400 9px var(--f-num)', fill: 'var(--tx-sub)' }}>{num(v)}</text>)}
        {eixoX.map((v, i) => <text key={`x${v}-${i}`} x={px(v)} y={H - padB + 13} textAnchor={i === 0 ? 'start' : i === eixoX.length - 1 ? 'end' : 'middle'} style={{ font: '400 9px var(--f-num)', fill: 'var(--tx-sub)' }}>{num(v)}</text>)}
        {plot.map((d) => (d.id === sel ? null : <circle key={d.id} cx={px(d.x)} cy={py(d.y)} r={3.4} fill={corTipo(d.tipo)} opacity={0.55} />))}
        {selD && (<>
          <circle cx={px(selD.x)} cy={py(selD.y)} r={9} fill="none" stroke={ACC} strokeWidth="2" />
          <circle cx={px(selD.x)} cy={py(selD.y)} r={4.5} fill={corTipo(selD.tipo)} stroke="var(--bg-base)" strokeWidth="1.2" />
        </>)}
        <text x={(padL + W - padR) / 2} y={H - 3} textAnchor="middle" style={{ font: '400 9.5px var(--f-ui)', fill: 'var(--tx-sub)' }}>aluguel R$/m² →</text>
        <text x={13} y={(padT + H - padB) / 2} textAnchor="middle" transform={`rotate(-90 13 ${(padT + H - padB) / 2})`} style={{ font: '400 9.5px var(--f-ui)', fill: 'var(--tx-sub)' }}>mercado que sobra (alunos) →</text>
      </svg>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center', marginTop: 8 }}>
        {gruposPresentes.map((g) => (
          <span key={g.chave} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, font: '400 11px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: g.cor }} />{g.rotulo}
          </span>
        ))}
        {plot.length < dados.length && (
          <span className="num" style={{ marginLeft: 'auto', font: '400 10px/1 var(--f-num)', color: 'var(--tx-rank)' }}>amostra de {plot.length} de {num(dados.length)}</span>
        )}
      </div>
    </div>
  )
}

/* ======================= Mini-mapa da ficha (pan/zoom) ======================= */
function MiniMapa({ op, pares, onSel }: { op: Oportunidade; pares: Oportunidade[]; onSel: (id: string) => void }) {
  const [vs, setVs] = useState(() => ({ longitude: op.lng ?? -49, latitude: op.lat ?? -16, zoom: op.lat != null ? 13 : 3.5 }))
  const [zoomArmado, setZoomArmado] = useState(false)
  const [hover, setHover] = useState<string | null>(null)

  useEffect(() => {
    if (op.lat != null && op.lng != null) setVs((v) => ({ ...v, longitude: op.lng as number, latitude: op.lat as number, zoom: Math.max(v.zoom, 13) }))
  }, [op.id, op.lat, op.lng])

  const vizinhos = useMemo(() => pares.filter((p) => p.id !== op.id && p.lat != null && p.lng != null).slice(0, MAX_PINS), [pares, op.id])
  const semCoord = op.lat == null || op.lng == null
  const ajustarZoom = (d: number) => setVs((v) => ({ ...v, zoom: Math.min(18, Math.max(3, v.zoom + d)) }))

  return (
    <div onPointerDown={() => setZoomArmado(true)} onMouseLeave={() => setZoomArmado(false)}
      style={{ position: 'relative', borderRadius: 'var(--r-lg)', overflow: 'hidden', border: '1px solid var(--line)', background: 'var(--bg-lift)', height: 320 }}>
      {semCoord ? (
        <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-muted)', textAlign: 'center', padding: 16 }}>Sem coordenada para este imóvel.</div>
      ) : (
        <>
          <Map longitude={vs.longitude} latitude={vs.latitude} zoom={vs.zoom} onMove={(e) => setVs(e.viewState)}
            mapStyle={BASEMAP} scrollZoom={zoomArmado} dragRotate={false} attributionControl={{ compact: true }} reuseMaps
            style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
            {vizinhos.map((p) => (
              <Marker key={p.id} longitude={p.lng as number} latitude={p.lat as number} anchor="center" onClick={() => onSel(p.id)}>
                <div style={{ position: 'relative', zIndex: hover === p.id ? 10 : 1 }} onMouseEnter={() => setHover(p.id)} onMouseLeave={() => setHover((h) => (h === p.id ? null : h))}>
                  <div style={{ width: 13, height: 13, borderRadius: '50%', background: corTipo(p.tipo), border: '1.5px solid rgba(8,11,16,.75)', boxShadow: hover === p.id ? '0 0 0 3px rgba(255,255,255,.18)' : 'none', opacity: 0.9, cursor: 'pointer' }} />
                  {hover === p.id && <TooltipImovel op={p} />}
                </div>
              </Marker>
            ))}
            <Marker longitude={op.lng as number} latitude={op.lat as number} anchor="center">
              <div style={{ width: 18, height: 18, borderRadius: '50%', background: ACC, border: '2px solid #fff', boxShadow: `0 0 0 5px ${ACC_24}, var(--sh-pop)` }} />
            </Marker>
          </Map>
          <div style={{ position: 'absolute', right: 8, top: 8, display: 'flex', flexDirection: 'column', gap: 4, zIndex: 3 }}>
            <BotaoZoom rotulo="Aproximar" onClick={() => ajustarZoom(1)}>+</BotaoZoom>
            <BotaoZoom rotulo="Afastar" onClick={() => ajustarZoom(-1)}>−</BotaoZoom>
          </div>
          {!zoomArmado && (
            <div style={{ position: 'absolute', left: 8, top: 8, zIndex: 3, font: '500 9.5px/1 var(--f-ui)', color: 'var(--tx-muted)', background: 'var(--surf-panel)', border: '1px solid var(--line-soft)', borderRadius: 6, padding: '4px 7px', backdropFilter: 'blur(8px)', pointerEvents: 'none' }}>
              clique para a roda dar zoom · arraste para mover
            </div>
          )}
        </>
      )}
    </div>
  )
}

/* ======================= Mapa do recorte (coluna esquerda) ======================= */
function MapaRecorte({ pontos, sel, onSel, altura = 620 }: { pontos: Oportunidade[]; sel: string | null; onSel: (id: string) => void; altura?: number | string }) {
  const [hover, setHover] = useState<string | null>(null)
  const comCoord = useMemo(() => pontos.filter((p) => p.lat != null && p.lng != null).slice(0, MAX_PINS), [pontos])
  // Chave do recorte: refaz o enquadramento inicial quando o conjunto muda.
  const chave = `${pontos.length}:${pontos[0]?.id ?? ''}`
  const inicial = useMemo(() => {
    if (!comCoord.length) return { longitude: -49, latitude: -15, zoom: 3.2 }
    const lats = comCoord.map((p) => p.lat as number)
    const lngs = comCoord.map((p) => p.lng as number)
    const minLat = Math.min(...lats), maxLat = Math.max(...lats)
    const minLng = Math.min(...lngs), maxLng = Math.max(...lngs)
    const span = Math.max(maxLat - minLat, maxLng - minLng, 0.01)
    // heuristica simples de zoom pelo alcance em graus (sem fitBounds do maplibre)
    const zoom = span > 8 ? 4 : span > 3 ? 5.5 : span > 1 ? 7 : span > 0.3 ? 9 : span > 0.08 ? 11 : 12.5
    return { longitude: (minLng + maxLng) / 2, latitude: (minLat + maxLat) / 2, zoom }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave])

  if (!comCoord.length) {
    return <Aviso titulo="Sem coordenadas" corpo="Nenhum imóvel do recorte tem coordenada para plotar no mapa." />
  }
  return (
    <div style={{ borderRadius: 'var(--r-lg)', overflow: 'hidden', border: '1px solid var(--line)', background: 'var(--bg-lift)', height: altura, position: 'relative' }}>
      <Map key={chave} initialViewState={inicial} mapStyle={BASEMAP} dragRotate={false} attributionControl={{ compact: true }} reuseMaps
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
        {comCoord.map((p) => {
          const on = p.id === sel
          return (
            <Marker key={p.id} longitude={p.lng as number} latitude={p.lat as number} anchor="center" onClick={() => onSel(p.id)}>
              <div style={{ position: 'relative', zIndex: hover === p.id ? 10 : on ? 5 : 1 }} onMouseEnter={() => setHover(p.id)} onMouseLeave={() => setHover((h) => (h === p.id ? null : h))}>
                <div style={{ width: on ? 18 : 13, height: on ? 18 : 13, borderRadius: '50%', background: corTipo(p.tipo), border: on ? '2px solid #fff' : '1.5px solid rgba(8,11,16,.75)', boxShadow: on ? `0 0 0 5px ${ACC_24}` : hover === p.id ? '0 0 0 3px rgba(255,255,255,.18)' : 'none', opacity: on ? 1 : 0.88, cursor: 'pointer' }} />
                {hover === p.id && <TooltipImovel op={p} />}
              </div>
            </Marker>
          )
        })}
      </Map>
      <div style={{ position: 'absolute', bottom: 10, left: 10, zIndex: 3, display: 'flex', gap: 12, flexWrap: 'wrap', padding: '6px 10px', borderRadius: 8, background: 'var(--surf-panel)', border: '1px solid var(--line-soft)', backdropFilter: 'blur(8px)' }}>
        {GRUPOS.filter((g) => comCoord.some((p) => g.tipos.includes(p.tipo))).map((g) => (
          <span key={g.chave} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, font: '400 10.5px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: g.cor }} />{g.rotulo}
          </span>
        ))}
      </div>
    </div>
  )
}

function BotaoZoom({ children, rotulo, onClick }: { children: ReactNode; rotulo: string; onClick: () => void }) {
  return (
    <button type="button" title={rotulo} aria-label={rotulo} onClick={onClick}
      style={{ width: 26, height: 26, display: 'grid', placeItems: 'center', borderRadius: 'var(--r-sm)', border: '1px solid var(--line-soft)', background: 'var(--surf-panel)', backdropFilter: 'blur(10px)', color: 'var(--tx-soft)', font: '600 15px/1 var(--f-ui)', cursor: 'pointer' }}>{children}</button>
  )
}

/** Tooltip de hover sobre um pin de imovel no mapa — principais numeros do ponto. */
function TooltipImovel({ op }: { op: Oportunidade }) {
  const r = rsM2(op)
  const custo = custoOcup(op)
  const proj = projFatDe(op)
  return (
    <div style={{ position: 'absolute', left: '50%', bottom: 'calc(100% + 9px)', transform: 'translateX(-50%)', width: 196, padding: '10px 12px', borderRadius: 'var(--r-md)', pointerEvents: 'none', zIndex: 30, background: 'var(--surf-panel)', border: '1px solid var(--line-mid)', boxShadow: 'var(--sh-pop)', backdropFilter: 'blur(10px)' }}>
      <div style={{ font: '600 12px/1.25 var(--f-ui)', color: 'var(--tx-strong)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{op.titulo}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, margin: '4px 0 8px' }}>
        <span style={{ width: 7, height: 7, borderRadius: 2, background: corTipo(op.tipo), flexShrink: 0 }} />
        <span style={{ font: '400 10.5px/1.2 var(--f-ui)', color: 'var(--tx-sub)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{labelTipo(op.tipo)} · {op.bairro ?? op.municipio}</span>
      </div>
      <TipLinha rotulo="Área" valor={op.area == null ? '—' : `${num(op.area)} m²`} />
      <TipLinha rotulo="Aluguel" valor={op.aluguel == null ? '—' : `${brl(op.aluguel)}${r != null ? ` · R$ ${num(r, 0)}/m²` : ''}`} />
      <TipLinha rotulo="Custo ocup." valor={custo > 0 ? brl(custo) : '—'} />
      <TipLinha rotulo="Projeção fat." valor={proj == null ? '—' : `${brl(proj, true)}/mês`} cor="var(--pos-text)" />
    </div>
  )
}
function TipLinha({ rotulo, valor, cor }: { rotulo: string; valor: string; cor?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, marginTop: 3 }}>
      <span style={{ font: '400 10.5px/1.4 var(--f-ui)', color: 'var(--tx-label)', flexShrink: 0 }}>{rotulo}</span>
      <span className="num" style={{ font: '500 10.5px/1.4 var(--f-num)', color: cor ?? 'var(--tx-soft)', textAlign: 'right' }}>{valor}</span>
    </div>
  )
}

/* ======================= Auxiliares ======================= */
function HeroStat({ label, valor, unidade, nota, cor }: { label: string; valor: string; unidade?: string; nota?: string; cor?: string }) {
  return (
    <div style={{ minWidth: 0 }}>
      <div className="num" style={{ font: '400 10px/1 var(--f-num)', letterSpacing: '.1em', textTransform: 'uppercase', color: cor ?? 'var(--tx-sub)', marginBottom: 6 }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 5, whiteSpace: 'nowrap' }}>
        <span className="num" style={{ font: '500 24px/1 var(--f-num)', color: cor ?? 'var(--tx-max)', whiteSpace: 'nowrap' }}>{valor}</span>
        {unidade && <span style={{ font: '400 12px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>{unidade}</span>}
      </div>
      {nota && <div style={{ font: '400 10.5px/1.3 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 5 }}>{nota}</div>}
    </div>
  )
}

function RotuloMono({ children }: { children: ReactNode }) {
  return <div className="num" style={{ font: '400 10px/1 var(--f-num)', letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--tx-label)' }}>{children}</div>
}

function TituloCard({ titulo, nota }: { titulo: string; nota?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
      <h3 className="story" style={{ margin: 0, font: '400 19px/1.1 var(--f-story)', color: 'var(--tx-max)' }}>{titulo}</h3>
      {nota && <span className="num" style={{ font: '400 10px/1 var(--f-num)', letterSpacing: '.08em', color: 'var(--tx-rank)', whiteSpace: 'nowrap' }}>{nota}</span>}
    </div>
  )
}

function LegLinha({ cor, rotulo, valor, forte }: { cor: string; rotulo: string; valor: string; forte?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ width: 8, height: 8, borderRadius: 2, background: cor, flexShrink: 0 }} />
      <span style={{ font: '400 12px/1.2 var(--f-ui)', color: 'var(--tx-label)', flex: 1 }}>{rotulo}</span>
      <span className="num" style={{ font: `${forte ? 600 : 500} 12.5px/1.2 var(--f-num)`, color: forte ? 'var(--tx-max)' : 'var(--tx-soft)' }}>{valor}</span>
    </div>
  )
}

function FaixaPill({ faixa }: { faixa: string }) {
  return (
    <span className="num" style={{ font: '500 10px/1 var(--f-num)', letterSpacing: '.06em', textTransform: 'uppercase', padding: '5px 10px', borderRadius: 999, color: ACC_TX, background: ACC_10, border: `1px solid ${ACC_24}` }}>{labelFaixa(faixa)}</span>
  )
}
