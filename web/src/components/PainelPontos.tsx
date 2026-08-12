import { useMemo, useState } from 'react'

import CampoPonto from './CampoPonto'
import Select from './Select'
import TabelaComparacao from './TabelaComparacao'
import { Botao, Glass } from './primitives'
import type { EntradaClassificada } from '../lib/entrada-ponto'
import {
  MAX_PONTOS,
  compararPontos,
  rotulosDosPontos,
} from '../lib/comparacao-pontos'
import { alunos, num } from '../lib/format'
import type { PontoPayload } from '../lib/types'

/**
 * Os pontos colados: as abas para trocar entre eles, e a comparacao A x B.
 *
 * A COMPARACAO NAO INCLUI VIABILIDADE, de proposito. Por DEC-009 a demanda e' premissa
 * digitada pelo operador, entao dois imoveis com a mesma metragem e o mesmo aluguel
 * produzem DRE, payback e break-even IDENTICOS — duas colunas com os mesmos numeros,
 * que se le como defeito. O que muda entre pontos e' o contexto (quem mora em volta,
 * quanto sobra de mercado, quem ja disputa), e e' isso que a tabela compara. A
 * viabilidade continua embaixo, por ponto.
 */
export default function PainelPontos({
  fichas,
  aberto,
  onAbrir,
  onRemover,
  onResolver,
  onLimpar,
  carregando,
  erro,
}: {
  fichas: PontoPayload[]
  aberto: number
  onAbrir: (i: number) => void
  onRemover: (i: number) => void
  /** Resolve e acrescenta um ponto — o mesmo caminho da caixa de colar da tela. */
  onResolver: (entrada: EntradaClassificada, texto: string) => Promise<void>
  /** Tira os pontos, a janela e a marca do mapa. */
  onLimpar: () => void
  carregando: boolean
  erro: string | null
}) {
  const [a, setA] = useState(0)
  const [b, setB] = useState(1)
  /** O campo de colar aberto aqui dentro, ao lado do botão que o pediu. */
  const [adicionando, setAdicionando] = useState(false)

  /* Rotulos da LISTA, nao de cada ponto isolado: dois enderecos da mesma cidade sem
     bairro resolvido tinham o mesmo nome, e as abas, os seletores e as duas colunas da
     tabela ficavam indistinguiveis. */
  const rotulos = useMemo(() => rotulosDosPontos(fichas), [fichas])

  // Com 3+ pontos o operador escolhe o par; com 2 nao ha o que escolher.
  const iA = Math.min(a, fichas.length - 1)
  const iB = Math.min(b, fichas.length - 1)
  const comparacao = useMemo(
    () =>
      fichas.length >= 2 && iA !== iB
        ? compararPontos(fichas[iA], fichas[iB], rotulos[iA], rotulos[iB])
        : null,
    [fichas, iA, iB, rotulos],
  )

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      {/* ---- Abas dos pontos ---- */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        {fichas.map((f, i) => {
          const ativo = i === aberto
          return (
            <span
              key={`${f.hex_id}-${i}`}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '7px 8px 7px 11px',
                borderRadius: 999,
                background: ativo ? 'var(--ac-a12)' : 'var(--surf-raised)',
                border: `1px solid ${ativo ? 'var(--ac-a25)' : 'var(--line-soft)'}`,
              }}
            >
              <button
                type="button"
                onClick={() => onAbrir(i)}
                style={{
                  background: 'transparent',
                  border: 0,
                  padding: 0,
                  font: `${ativo ? 700 : 500} 12px/1 var(--f-ui)`,
                  color: ativo ? 'var(--ac-text)' : 'var(--tx-soft)',
                }}
              >
                {rotulos[i]}
              </button>
              <span className="num" style={{ font: '500 10px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
                {alunos(f.mercado?.residual)}
              </span>
              {fichas.length > 1 && (
                <button
                  type="button"
                  onClick={() => onRemover(i)}
                  title={`Remover ${rotulos[i]}`}
                  aria-label={`Remover ${rotulos[i]}`}
                  style={{
                    background: 'transparent',
                    border: 0,
                    padding: '0 2px',
                    color: 'var(--tx-rank)',
                    font: '700 12px/1 var(--f-ui)',
                  }}
                >
                  ×
                </button>
              )}
            </span>
          )
        })}

        {fichas.length < MAX_PONTOS ? (
          <Botao variante="ghost" onClick={() => setAdicionando((v) => !v)} aria-expanded={adicionando}>
            {adicionando ? '− Fechar' : '+ Adicionar mais um ponto'}
          </Botao>
        ) : (
          <span style={{ font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>
            {/* Teto declarado: sem isto o botao sumiria sem explicacao. */}
            Máximo de {MAX_PONTOS} pontos — remova um para colar outro.
          </span>
        )}

        {/* Limpeza. Só com ponto na tela — um "Limpar" sobre lista vazia é botão morto. */}
        {fichas.length > 0 && (
          <Botao variante="ghost" onClick={onLimpar} title="Tira os pontos, a janela e a marca do mapa">
            Limpar tudo
          </Botao>
        )}
      </div>

      {/* ---- Campo de colar, AQUI e não no cabeçalho ----
          A versão anterior mandava o cursor para a lupa do topo, e o operador tinha de
          procurar onde o foco caiu — longe do botão que ele acabou de clicar e longe da
          lista que está montando. O campo aparece colado na ação que o pediu, e some
          quando o ponto entra. Não é a caixa fixa que duplicava a lupa: existe só
          enquanto está aberto, a pedido. */}
      {adicionando && (
        <div
          style={{
            padding: 12,
            borderRadius: 'var(--r-lg)',
            border: '1px solid var(--ac-a25)',
            background: 'var(--surf-raised)',
            display: 'grid',
            gap: 8,
          }}
        >
          <CampoPonto
            onResolver={async (entrada, texto) => {
              await onResolver(entrada, texto)
              setAdicionando(false)
            }}
            ocupado={carregando}
            erro={erro}
          />
        </div>
      )}

      {/* ---- Comparação ---- */}
      {fichas.length >= 2 && (
        <Glass style={{ padding: 18, display: 'grid', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ font: '600 15px/1.2 var(--f-ui)', color: 'var(--tx-max)' }}>
              Comparando os pontos
            </span>
            <span style={{ font: '400 11px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
              contexto do entorno — a viabilidade fica por ponto, abaixo
            </span>
          </div>

          {/* Seletores só com 3+: com dois pontos não há par a escolher. */}
          {fichas.length > 2 && (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Select
                label="Primeiro ponto"
                value={String(iA)}
                onChange={(v) => setA(Number(v))}
                maxWidth={170}
                options={rotulos.map((r, i) => ({ value: String(i), label: r }))}
              />
              <Select
                label="Segundo ponto"
                value={String(iB)}
                onChange={(v) => setB(Number(v))}
                maxWidth={170}
                options={rotulos.map((r, i) => ({ value: String(i), label: r }))}
              />
            </div>
          )}

          {comparacao ? (
            <TabelaComparacao
              comparacao={comparacao}
              rotuloA={rotulos[iA]}
              rotuloB={rotulos[iB]}
            />
          ) : (
            <p style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
              Escolha dois pontos diferentes para comparar.
            </p>
          )}

          <p style={{ font: '400 11px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
            Cada leitura sai do raio de {num((fichas[iA]?.raio_km ?? 1) * 1000)} m em torno do
            ponto — a mesma régua do Relatório Pontual.
          </p>
        </Glass>
      )}
    </div>
  )
}
