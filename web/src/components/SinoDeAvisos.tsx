import { useCallback, useEffect, useRef, useState } from 'react'

import { api } from '../lib/api'
import {
  INTERVALO_DO_SINO_MS,
  quandoDoAviso,
  rotuloDoContador,
  textoDoAviso,
  type ItemDeAviso,
  type SinoPayload,
} from '../lib/avisos'

/* ---------------------------------------------------------------------------
   O sino da barra lateral (DEC-090): os avisos dos pedidos dos masters.

   19/11/2026, Juan: quando um master pede um estudo, o aviso chega ao time do Growth (a hora,
   quem pediu e de onde); quando pede um imóvel, chega à Priscila. O botão mora no rodapé do
   Dock, com a métrica do cadeado e do tema, e só existe para quem recebe algum aviso (`avisos`
   do `/api/me`). Pergunta a cada minuto se chegou aviso novo, com a aba visível; abrir o painel
   marca tudo o que estava nele como lido, e os que eram novos ficam realçados até fechar.
   --------------------------------------------------------------------------- */

export default function SinoDeAvisos() {
  const [sino, setSino] = useState<SinoPayload | null>(null)
  const [aberto, setAberto] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  // Os que eram novos quando o painel abriu: seguem realçados até fechar.
  const [novosAoAbrir, setNovosAoAbrir] = useState<Set<number>>(() => new Set())
  const caixa = useRef<HTMLDivElement>(null)

  const carregar = useCallback(() => {
    api
      .avisos()
      .then((r) => {
        setSino(r)
        setErro(null)
      })
      .catch(() => setErro('Não foi possível carregar os avisos agora.'))
  }, [])

  useEffect(() => {
    carregar()
    const id = window.setInterval(() => {
      if (document.visibilityState === 'visible') carregar()
    }, INTERVALO_DO_SINO_MS)
    return () => window.clearInterval(id)
  }, [carregar])

  // Fecha com Esc e com clique fora do painel.
  useEffect(() => {
    if (!aberto) return
    const tecla = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setAberto(false)
    }
    const clique = (e: MouseEvent) => {
      if (caixa.current && !caixa.current.contains(e.target as Node)) setAberto(false)
    }
    window.addEventListener('keydown', tecla)
    window.addEventListener('mousedown', clique)
    return () => {
      window.removeEventListener('keydown', tecla)
      window.removeEventListener('mousedown', clique)
    }
  }, [aberto])

  function alternar() {
    if (aberto) {
      setAberto(false)
      return
    }
    setAberto(true)
    if (!sino || sino.nao_lidos === 0 || sino.itens.length === 0) return
    const novos = new Set(sino.itens.filter((i) => !i.lido).map((i) => i.id))
    setNovosAoAbrir(novos)
    const maisNovo = Math.max(...sino.itens.map((i) => i.id))
    // Otimista: o contador zera na hora; se a gravação falhar, a próxima consulta o traz de volta.
    setSino({ ...sino, nao_lidos: 0, itens: sino.itens.map((i) => ({ ...i, lido: true })) })
    api.marcarAvisosLidos(maisNovo).catch(() => undefined)
  }

  const naoLidos = sino?.nao_lidos ?? 0
  const titulo = naoLidos > 0 ? `Avisos: ${naoLidos} novo${naoLidos === 1 ? '' : 's'}` : 'Avisos'

  return (
    <div ref={caixa} style={{ position: 'relative' }}>
      <button
        type="button"
        title={titulo}
        aria-label={titulo}
        aria-expanded={aberto}
        onClick={alternar}
        style={{
          width: 42,
          height: 42,
          flexShrink: 0,
          display: 'grid',
          placeItems: 'center',
          borderRadius: 11,
          border: '1px solid var(--line-soft)',
          background: aberto ? 'var(--surf-chip)' : 'var(--surf-raised)',
          color: 'var(--tx-muted)',
          cursor: 'pointer',
          position: 'relative',
          transition: 'background .15s ease, color .15s ease',
        }}
      >
        <Sino />
        {naoLidos > 0 && (
          <span
            aria-hidden
            style={{
              position: 'absolute',
              top: -5,
              right: -5,
              minWidth: 18,
              height: 18,
              padding: '0 4px',
              borderRadius: 9,
              background: 'var(--mst)',
              color: 'var(--mst-on)',
              font: '700 10.5px/18px var(--f-num)',
              textAlign: 'center',
              boxShadow: '0 0 0 2px var(--surf-chrome)',
            }}
          >
            {rotuloDoContador(naoLidos)}
          </span>
        )}
      </button>

      {aberto && (
        <div
          role="dialog"
          aria-label="Avisos"
          style={{
            position: 'absolute',
            left: 54,
            bottom: 0,
            width: 360,
            maxHeight: 'min(560px, 75vh)',
            display: 'flex',
            flexDirection: 'column',
            background: 'var(--surf-panel)',
            border: '1px solid var(--line-mid)',
            borderRadius: 'var(--r-md)',
            boxShadow: 'var(--sh-pop)',
            backdropFilter: 'blur(16px)',
            zIndex: 60,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              padding: '12px 14px 10px',
              borderBottom: '1px solid var(--line-soft)',
              font: '700 13px/1.3 var(--f-ui)',
              color: 'var(--tx-strong)',
            }}
          >
            Avisos
            <div style={{ font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 2 }}>
              os pedidos dos masters, os mais novos primeiro
            </div>
          </div>
          <div style={{ overflowY: 'auto' }}>
            {erro ? (
              <Vazio>{erro}</Vazio>
            ) : !sino ? (
              <Vazio>Carregando os avisos…</Vazio>
            ) : sino.itens.length === 0 ? (
              <Vazio>Nenhum aviso por enquanto.</Vazio>
            ) : (
              sino.itens.map((item) => <LinhaDoAviso key={item.id} item={item} novo={novosAoAbrir.has(item.id)} />)
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function LinhaDoAviso({ item, novo }: { item: ItemDeAviso; novo: boolean }) {
  const { titulo, linha, destaque } = textoDoAviso(item)
  return (
    <div
      style={{
        padding: '10px 14px',
        borderBottom: '1px solid var(--line-soft)',
        background: novo ? 'color-mix(in srgb, var(--mst) 10%, transparent)' : 'transparent',
        borderLeft: `3px solid ${novo ? 'var(--mst)' : 'transparent'}`,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
        <span style={{ font: '700 12px/1.35 var(--f-ui)', color: 'var(--tx-strong)' }}>{titulo}</span>
        <span style={{ font: '400 10.5px/1 var(--f-num)', color: 'var(--tx-sub)', whiteSpace: 'nowrap' }}>
          {quandoDoAviso(item.quando)}
        </span>
      </div>
      <div style={{ font: '400 12px/1.45 var(--f-ui)', color: 'var(--tx-soft)', marginTop: 3 }}>{linha}</div>
      {destaque && (
        <span
          style={{
            display: 'inline-block',
            marginTop: 5,
            padding: '2px 7px',
            borderRadius: 999,
            font: '700 10px/1.4 var(--f-ui)',
            color: 'var(--mst-text)',
            border: '1px solid var(--mst)',
          }}
        >
          {destaque}
        </span>
      )}
    </div>
  )
}

function Vazio({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ padding: '16px 14px', font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-sub)' }}>{children}</div>
  )
}

/* Sino em `currentColor` e `stroke`, como o cadeado: herda a cor do botão nos dois temas. */
function Sino() {
  return (
    <svg
      width={18}
      height={18}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M6 9.5a6 6 0 0 1 12 0c0 4.2 1.4 6 2.2 7H3.8c.8-1 2.2-2.8 2.2-7Z" />
      <path d="M10 19.5a2.1 2.1 0 0 0 4 0" />
    </svg>
  )
}
