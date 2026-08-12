import { useMemo, useState } from 'react'

import { Botao, Spinner } from './primitives'
import { classificarEntrada, type EntradaClassificada } from '../lib/entrada-ponto'

/**
 * Caixa de entrada do modo de ponto: cole o link do Google Maps ou a coordenada.
 *
 * A classificacao e' VIVA (a cada tecla) e vem de `lib/entrada-ponto`, que e' pura e
 * testada. Aqui so' se desenha o resultado dela — o componente nao decide nada sobre
 * formato de link.
 *
 * O aviso aparece ANTES de o operador apertar Analisar. E' o ponto do exercicio: com o
 * link curto do celular, o fluxo antigo so' dizia "nao encontrei esse endereco" depois
 * da ida ao servidor, e mandava o operador procurar erro num link correto.
 */
export default function CampoPonto({
  onResolver,
  ocupado = false,
  erro = null,
}: {
  onResolver: (entrada: EntradaClassificada, texto: string) => void
  ocupado?: boolean
  erro?: string | null
}) {
  const [texto, setTexto] = useState('')
  const entrada = useMemo(() => classificarEntrada(texto), [texto])

  // Vazio nao tem o que analisar; fora do Brasil o servidor recusaria de qualquer
  // forma (a malha municipal do IBGE nao resolve) — barrar aqui poupa a ida e devolve
  // uma mensagem que explica o que houve.
  const podeAnalisar =
    !ocupado && entrada.tipo !== 'vazio' && entrada.tipo !== 'fora-do-brasil'

  function enviar() {
    if (!podeAnalisar) return
    onResolver(entrada, texto.trim())
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <label
        htmlFor="campo-ponto"
        style={{ font: '600 12px/1 var(--f-ui)', color: 'var(--tx-soft)' }}
      >
        Cole o link do Google Maps ou a coordenada
      </label>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <input
          id="campo-ponto"
          type="text"
          value={texto}
          disabled={ocupado}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') enviar()
          }}
          placeholder="https://maps.app.goo.gl/…   ou   -23.5613, -46.6565"
          style={{
            flex: 1,
            minWidth: 240,
            padding: '11px 13px',
            borderRadius: 'var(--r-md)',
            border: '1px solid var(--line-strong)',
            background: 'var(--surf-raised)',
            color: 'var(--tx-max)',
            font: '400 13px/1.2 var(--f-ui)',
          }}
        />
        <Botao onClick={enviar} disabled={!podeAnalisar}>
          {ocupado ? (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <Spinner /> Analisando…
            </span>
          ) : (
            'Analisar'
          )}
        </Botao>
      </div>

      {/* Uma linha de estado por vez, nesta ordem: erro do servidor manda em tudo,
          depois o aviso da classificacao, e por fim a dica neutra. */}
      {erro ? (
        <Nota cor="var(--neg)">{erro}</Nota>
      ) : entrada.aviso ? (
        <Nota cor="var(--tx-narrative)">{entrada.aviso}</Nota>
      ) : (
        <Nota cor="var(--tx-sub)">
          Funciona com o link da barra de endereço do computador, o link curto que o
          celular compartilha, um endereço escrito ou o par de coordenadas.
        </Nota>
      )}
    </div>
  )
}

function Nota({ children, cor }: { children: React.ReactNode; cor: string }) {
  return (
    <p style={{ font: '400 11.5px/1.5 var(--f-ui)', color: cor, margin: 0 }}>{children}</p>
  )
}
