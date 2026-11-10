import { useEffect, useRef, useState } from 'react'

import { baixar } from '../lib/api'
import {
  MAX_ROTULO_PRINT,
  alcanceDoPrint,
  limparRotuloDigitado,
  nomeDoArquivoPrint,
  rotuloDoPrint,
} from '../lib/print-mapa'
import type { PontoPayload } from '../lib/types'
import { Spinner } from './primitives'

/**
 * "Baixar imagem do mapa": o PRINT LIMPO do ponto, em 16:9 (`lib/print-mapa`).
 *
 * Só o fundo de ruas realçado, o alcance do ponto e o pin — sem hexágono, setor ou número.
 *
 * O NOME DO PIN é do operador (pedido do Vinicius, 10/11/2026): o clique abre, logo abaixo
 * do botão e DENTRO da ficha, um campo já preenchido com o nome sugerido (bairro · cidade/UF)
 * para ele trocar pelo endereço que quiser — ou apagar, e o pin sai sem nome. Dentro da
 * ficha, e não num pop-up flutuante: não cobre o mapa, não é cortado pela rolagem da ficha
 * e, no caso comum, custa só o Enter.
 *
 * O renderizador (MapLibre + canvas) entra por import DINÂMICO: ele só é pedido no clique,
 * e quem nunca baixa a imagem não paga o carregamento dele.
 */
export default function BotaoPrintMapa({
  ficha,
  nome,
  recorte,
}: {
  ficha: PontoPayload
  /**
   * O nome do LUGAR (bairro/hexágono), `null` na área desenhada. Não é o rótulo da aba: ele
   * carrega "(unidade Ultra)" e cai na coordenada, que não cabem numa imagem sem dados.
   */
  nome: string | null
  /** O rótulo do recorte ("raio de 1 km", "10 min de carro"...), só para o nome do arquivo. */
  recorte: string | null
}) {
  const sugerido = rotuloDoPrint(nome, ficha.local.municipio, ficha.local.uf)
  const [aberto, setAberto] = useState(false)
  const [texto, setTexto] = useState(sugerido)
  const [gerando, setGerando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const campo = useRef<HTMLInputElement>(null)

  /* Outro ponto (ou outro alcance com outro nome) volta à sugestão dele: o nome digitado
     para a Paulista não pode ir parar no print de Pinheiros. */
  useEffect(() => {
    setTexto(sugerido)
    setAberto(false)
  }, [sugerido, ficha.lat, ficha.lng])

  useEffect(() => {
    if (aberto) campo.current?.select()
  }, [aberto])

  async function gerar() {
    if (gerando) return
    setGerando(true)
    setErro(null)
    let erroComTexto: (new (msg?: string) => Error) | null = null
    try {
      const { gerarPrintDoMapa, ErroPrint } = await import('../lib/print-mapa-render')
      erroComTexto = ErroPrint
      const rotulo = limparRotuloDigitado(texto)
      const imagem = await gerarPrintDoMapa({
        lat: ficha.lat,
        lng: ficha.lng,
        poligonos: alcanceDoPrint(ficha),
        rotulo,
      })
      // Sem nome no pin, o arquivo segue nomeado pelo lugar sugerido.
      baixar(imagem, nomeDoArquivoPrint(rotulo || sugerido, recorte))
      setAberto(false)
    } catch (e) {
      // Só o erro do próprio print tem frase pronta; o resto (do MapLibre, em inglês) não.
      const comTexto = erroComTexto != null && e instanceof erroComTexto
      if (!comTexto) console.error('[print-mapa]', e)
      setErro(comTexto ? (e as Error).message : 'Não foi possível gerar a imagem do mapa. Tente de novo.')
    } finally {
      setGerando(false)
    }
  }

  const botaoBase = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '6px 10px',
    borderRadius: 'var(--r-md)',
    font: '600 11.5px/1 var(--f-ui)',
  } as const

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setErro(null)
          setAberto((v) => !v)
        }}
        disabled={gerando}
        aria-expanded={aberto}
        aria-controls="print-mapa-nome"
        title="Baixa uma imagem 16:9 só com o mapa da região, o alcance e o pin do ponto — sem hexágonos nem dados"
        style={{
          ...botaoBase,
          border: '1px solid var(--line-strong)',
          background: aberto ? 'var(--surf-panel)' : 'transparent',
          color: 'var(--ac-text)',
          cursor: gerando ? 'progress' : 'pointer',
          opacity: gerando ? 0.7 : 1,
        }}
      >
        <svg width="13" height="13" viewBox="0 0 24 24" aria-hidden fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="5" width="18" height="14" rx="2" />
          <circle cx="12" cy="11" r="2.5" />
          <path d="M12 13.5V16" />
        </svg>
        Baixar imagem do mapa
      </button>

      {aberto && (
        <form
          id="print-mapa-nome"
          onSubmit={(e) => {
            e.preventDefault()
            void gerar()
          }}
          style={{
            flexBasis: '100%',
            display: 'grid',
            gap: 8,
            padding: 12,
            borderRadius: 'var(--r-md)',
            border: '1px solid var(--line-soft)',
            background: 'var(--surf-panel)',
          }}
        >
          <label htmlFor="print-mapa-nome-campo" style={{ font: '600 12px/1.3 var(--f-ui)', color: 'var(--tx-max)' }}>
            Nome que aparece sob o pin
          </label>
          <input
            id="print-mapa-nome-campo"
            ref={campo}
            value={texto}
            maxLength={MAX_ROTULO_PRINT}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') setAberto(false)
            }}
            disabled={gerando}
            placeholder="Ex.: Av. Lúcio Meira, 923 - Várzea, Teresópolis - RJ"
            style={{
              padding: '8px 10px',
              borderRadius: 'var(--r-sm, 6px)',
              border: '1px solid var(--line-strong)',
              background: 'var(--bg-lift)',
              color: 'var(--tx-max)',
              font: '400 13px/1.3 var(--f-ui)',
            }}
          />
          <div style={{ font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>
            Deixe em branco para o pin sair sem nome.
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <button
              type="submit"
              disabled={gerando}
              aria-busy={gerando}
              style={{
                ...botaoBase,
                border: 'none',
                background: 'var(--ac)',
                color: 'var(--ac-on)',
                fontWeight: 700,
                cursor: gerando ? 'progress' : 'pointer',
                opacity: gerando ? 0.75 : 1,
              }}
            >
              {gerando && <Spinner tamanho={12} />}
              {gerando ? 'Gerando imagem…' : 'Baixar'}
            </button>
            <button
              type="button"
              onClick={() => setAberto(false)}
              disabled={gerando}
              style={{ ...botaoBase, border: 'none', background: 'transparent', color: 'var(--tx-soft)', cursor: 'pointer' }}
            >
              Cancelar
            </button>
            {texto !== sugerido && !gerando && (
              <button
                type="button"
                onClick={() => setTexto(sugerido)}
                style={{ ...botaoBase, border: 'none', background: 'transparent', color: 'var(--ac-text)', cursor: 'pointer', textDecoration: 'underline' }}
              >
                Voltar ao nome sugerido
              </button>
            )}
          </div>
        </form>
      )}

      {erro && (
        <span role="alert" style={{ flexBasis: '100%', font: '400 11.5px/1.4 var(--f-ui)', color: 'var(--neg, #e5484d)' }}>
          {erro}
        </span>
      )}
    </>
  )
}
