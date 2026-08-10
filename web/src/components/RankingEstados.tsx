import { useEffect, useState } from 'react'

import { Aviso, Chip, Eyebrow, Spinner } from './primitives'
import { api, ApiError } from '../lib/api'
import { alunos, num } from '../lib/format'
import type { EstadoRanking } from '../lib/types'

/**
 * Por qual ESTADO comecar — a pergunta que o piloto nunca respondeu.
 *
 * ELE E' O SELETOR, e nao um enfeite ao lado dele. Antes o operador escolhia a UF num
 * dropdown que nao dizia nada: 27 siglas em ordem alfabetica, e ele que descobrisse
 * qual valia a pena. Aqui a escolha e' a propria resposta — a lista ja vem ordenada
 * por quanto residual cada estado tem ONDE ainda cabe abrir.
 *
 * MESMA CASCATA DO FUNIL, aplicada nacionalmente (potencial >= 70, populacao >= 5.000,
 * white space). Nada de criterio novo: e' a leitura do funil somada por UF, e o
 * numero que ordena e' o residual em ALUNOS, nao um score — score satura em 100 e
 * empataria os estados grandes.
 */
export default function RankingEstados({
  ufSelecionada,
  onEscolher,
}: {
  ufSelecionada: string
  onEscolher: (uf: string) => void
}) {
  const [estados, setEstados] = useState<EstadoRanking[] | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [tudo, setTudo] = useState(false)

  useEffect(() => {
    let vivo = true
    api
      .estados()
      .then((r) => vivo && setEstados(r.estados))
      .catch((e: ApiError) => vivo && setErro(e.message))
    return () => {
      vivo = false
    }
  }, [])

  if (erro) return <Aviso titulo="Não deu para ler o ranking de estados" corpo={erro} />

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
        <Spinner /> Comparando os 27 estados…
      </p>
    )
  }

  const visiveis = tudo ? estados : estados.slice(0, 8)

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <div style={{ display: 'grid', gap: 6 }}>
        <Eyebrow dot>Por onde começar</Eyebrow>
        <span style={{ font: '400 21px/1.25 var(--f-story)', color: 'var(--tx-max)' }}>
          Qual estado tem mais espaço para a Ultra
        </span>
        <p style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
          Ordenado por <strong style={{ color: 'var(--tx-soft)' }}>alunos não atendidos onde
          ainda cabe abrir</strong> — o mesmo funil de sempre (potencial ≥ 70, população ≥ 5.000,
          sem concorrente mapeado), somado por estado. Clique num estado para abrir as camadas
          dele.
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
          {ufSelecionada} é o {estados.find((e) => e.uf === ufSelecionada)?.rank ?? '—'}º do país
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
