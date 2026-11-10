import { useState } from 'react'

import { baixar } from '../lib/api'
import { alcanceDoPrint, nomeDoArquivoPrint, rotuloDoPrint } from '../lib/print-mapa'
import type { PontoPayload } from '../lib/types'
import { Spinner } from './primitives'

/**
 * "Baixar imagem do mapa": o PRINT LIMPO do ponto, em 16:9 (`lib/print-mapa`).
 *
 * Só o fundo de ruas realçado, o alcance do ponto e o pin — sem hexágono, setor ou número.
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
  const [gerando, setGerando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function gerar() {
    if (gerando) return
    setGerando(true)
    setErro(null)
    let erroComTexto: (new (msg?: string) => Error) | null = null
    try {
      const { gerarPrintDoMapa, ErroPrint } = await import('../lib/print-mapa-render')
      erroComTexto = ErroPrint
      const rotulo = rotuloDoPrint(nome, ficha.local.municipio, ficha.local.uf)
      const imagem = await gerarPrintDoMapa({
        lat: ficha.lat,
        lng: ficha.lng,
        poligonos: alcanceDoPrint(ficha),
        rotulo,
      })
      baixar(imagem, nomeDoArquivoPrint(rotulo, recorte))
    } catch (e) {
      // Só o erro do próprio print tem frase pronta; o resto (do MapLibre, em inglês) não.
      const comTexto = erroComTexto != null && e instanceof erroComTexto
      if (!comTexto) console.error('[print-mapa]', e)
      setErro(comTexto ? (e as Error).message : 'Não foi possível gerar a imagem do mapa. Tente de novo.')
    } finally {
      setGerando(false)
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={gerar}
        disabled={gerando}
        aria-busy={gerando}
        title="Baixa uma imagem 16:9 só com o mapa da região, o alcance e o pin do ponto — sem hexágonos nem dados"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '6px 10px',
          borderRadius: 'var(--r-md)',
          border: '1px solid var(--line-strong)',
          background: 'transparent',
          color: 'var(--ac-text)',
          font: '600 11.5px/1 var(--f-ui)',
          cursor: gerando ? 'progress' : 'pointer',
          opacity: gerando ? 0.7 : 1,
        }}
      >
        {gerando ? (
          <Spinner tamanho={12} />
        ) : (
          <svg width="13" height="13" viewBox="0 0 24 24" aria-hidden fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="5" width="18" height="14" rx="2" />
            <circle cx="12" cy="11" r="2.5" />
            <path d="M12 13.5V16" />
          </svg>
        )}
        {gerando ? 'Gerando imagem…' : 'Baixar imagem do mapa'}
      </button>
      {erro && (
        <span role="alert" style={{ flexBasis: '100%', font: '400 11.5px/1.4 var(--f-ui)', color: 'var(--neg, #e5484d)' }}>
          {erro}
        </span>
      )}
    </>
  )
}
