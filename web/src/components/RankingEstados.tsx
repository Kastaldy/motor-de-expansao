import { useEffect, useState } from 'react'
import { useUfsDaBase } from '../lib/base-contexto'
import { nomeDasUnidades } from '../lib/rodape-base'

import { Aviso, Chip, Eyebrow, Spinner } from './primitives'
import { api, ApiError } from '../lib/api'
import { alunos, num } from '../lib/format'
import type { EstadoRanking, EstadosPayload } from '../lib/types'

/**
 * Residual somado por ESTADO — uma LEITURA de tamanho, e o seletor de UF da tela.
 *
 * ELE E' O SELETOR, e nao um enfeite ao lado dele. Antes o operador escolhia a UF num
 * dropdown que nao dizia nada: 27 siglas em ordem alfabetica. Aqui a lista vem ordenada
 * pela soma dos alunos nao atendidos de cada estado, e clicar num estado FILTRA a tela —
 * inclusive o Top 10 acima.
 *
 * NAO E' RECOMENDACAO (recomendacao unica, DEC-077). A recomendacao e' o Top 10 por
 * hexagono; esta soma e' grandeza de TAMANHO, e estado grande cheio de hexagono mediano
 * vence estado pequeno dono do melhor hexagono do pais — por isso ela se apresenta como
 * leitura. A conta e' a de sempre (`/api/estados`): soma do residual nos hexagonos com
 * score censitario >= `reguas.score_minimo` e populacao >= `reguas.pop_minima`, sem
 * saturacao de concorrencia. O numero que ordena e' o residual em ALUNOS, nao um score —
 * score satura em 100 e empataria os estados grandes.
 */
export default function RankingEstados({
  ufSelecionada,
  onEscolher,
}: {
  ufSelecionada: string
  onEscolher: (uf: string) => void
}) {
  const ufs = useUfsDaBase()
  const [estados, setEstados] = useState<EstadoRanking[] | null>(null)
  const [reguas, setReguas] = useState<EstadosPayload['reguas'] | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [tudo, setTudo] = useState(false)

  useEffect(() => {
    let vivo = true
    api
      .estados()
      .then((r) => {
        if (!vivo) return
        setEstados(r.estados)
        setReguas(r.reguas ?? null)
      })
      .catch((e: ApiError) => vivo && setErro(e.message))
    return () => {
      vivo = false
    }
  }, [])

  if (erro) return <Aviso titulo="Não deu para ler o ranking" corpo={erro} />

  if (!estados) {
    return (
      <p
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          font: '400 13px/1 var(--f-ui)',
          color: 'var(--tx-muted)',
          margin: 0,
        }}
      >
        <Spinner /> Comparando {nomeDasUnidades(ufs)}…
      </p>
    )
  }

  const visiveis = tudo ? estados : estados.slice(0, 8)

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <div style={{ display: 'grid', gap: 6 }}>
        <Eyebrow dot>Leitura por estado</Eyebrow>
        <span style={{ font: '400 21px/1.25 var(--f-story)', color: 'var(--tx-max)' }}>
          Residual somado por estado
        </span>
        <p style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
          Soma dos <strong style={{ color: 'var(--tx-soft)' }}>alunos não atendidos</strong> nos
          hexágonos com{' '}
          {reguas
            ? `score censitário a partir de ${num(reguas.score_minimo)} e população a partir de ${num(reguas.pop_minima)} habitantes`
            : 'potencial e população acima do corte'}
          , sem saturação de concorrência. É uma leitura de tamanho, não uma recomendação — a
          recomendação é o Top 10 acima. Clique num estado para filtrar.
        </p>
      </div>

      <div style={{ display: 'grid', gap: 3 }}>
        {visiveis.map((e) => {
          const ativo = e.uf === ufSelecionada
          return (
            <button
              key={e.uf}
              type="button"
              onClick={() => onEscolher(e.uf)}
              style={{
                display: 'flex',
                alignItems: 'baseline',
                gap: 10,
                padding: '8px 10px',
                borderRadius: 8,
                textAlign: 'left',
                background: ativo ? 'var(--ac-a12)' : 'transparent',
                border: `1px solid ${ativo ? 'var(--ac-a25)' : 'transparent'}`,
              }}
              onMouseEnter={(ev) => {
                if (!ativo) ev.currentTarget.style.background = 'var(--surf-raised)'
              }}
              onMouseLeave={(ev) => {
                if (!ativo) ev.currentTarget.style.background = 'transparent'
              }}
            >
              <span
                className="num"
                style={{
                  font: '600 11px/1 var(--f-num)',
                  color: ativo ? 'var(--ac-text)' : 'var(--tx-rank)',
                  width: 20,
                }}
              >
                {e.rank}º
              </span>
              <span
                style={{
                  font: '700 14px/1 var(--f-ui)',
                  color: ativo ? 'var(--ac-text)' : 'var(--tx-max)',
                  width: 30,
                }}
              >
                {e.uf}
              </span>
              {/* Barra proporcional ao 1º: o numero absoluto nao diz se SP e' o dobro
                  ou dez vezes o segundo, e essa proporcao e' a decisao. */}
              <span
                aria-hidden
                style={{
                  flex: 1,
                  height: 6,
                  minWidth: 40,
                  borderRadius: 3,
                  background: 'var(--surf-raised)',
                  overflow: 'hidden',
                }}
              >
                <span
                  style={{
                    display: 'block',
                    height: '100%',
                    width: `${fracao(e, estados[0])}%`,
                    background: ativo ? 'var(--ac)' : 'var(--l2)',
                  }}
                />
              </span>
              <span
                className="num"
                style={{
                  font: '600 12.5px/1 var(--f-num)',
                  color: 'var(--tx-max)',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {alunos(e.residual_white_space)}
              </span>
              <span
                style={{
                  font: '400 9.5px/1 var(--f-ui)',
                  color: 'var(--tx-sub)',
                  minWidth: 96,
                }}
              >
                alunos · {num(e.municipios_elegiveis)} cidades
              </span>
            </button>
          )
        })}
      </div>

      {estados.length > 8 && (
        <button
          type="button"
          onClick={() => setTudo((v) => !v)}
          style={{
            justifySelf: 'start',
            padding: '6px 10px',
            borderRadius: 8,
            border: '1px solid var(--line-soft)',
            background: 'var(--surf-raised)',
            color: 'var(--tx-soft)',
            font: '600 11px/1 var(--f-ui)',
          }}
        >
          {tudo ? 'Mostrar só o top 8' : `Ver os ${estados.length} estados`}
        </button>
      )}

      {ufSelecionada && (
        <Chip>
          {ufSelecionada} é o {estados.find((e) => e.uf === ufSelecionada)?.rank ?? '—'}º em
          residual somado
        </Chip>
      )}
    </div>
  )
}

/** Proporcao para a barra. Zero e' zero — nao se desenha barra de nada. */
function fracao(e: EstadoRanking, topo: EstadoRanking): number {
  const t = topo.residual_white_space ?? 0
  const v = e.residual_white_space ?? 0
  if (t <= 0) return 0
  return Math.max(1, Math.round((v / t) * 100))
}
