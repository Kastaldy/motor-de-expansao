import { useEffect, useState } from 'react'

import { api, ApiError } from '../../lib/api'
import type { FocoNoMapa } from '../../lib/masters'
import { TOP_INICIAL, focoDoHexagono, recorteDoTop, temMaisQueOTop } from '../../lib/masters'
import { rotuloNoMapa } from '../../lib/top10'
import type { RecomendacaoTop10 } from '../../lib/types'
import { Botao, Eyebrow, Glass, Spinner } from '../primitives'
import Top10Regioes from '../Top10Regioes'

/* ---------------------------------------------------------------------------
   Onde abrir no território do master, pela régua do motor (BLK-MASTERS-04).

   18/11/2026, Juan: "no top 5, mudar para o padrão do motor (que é Mata Virgem e
   Premium), deixar os top 5, só que embaixo a opção de expandir e mostrar o top 20".
   A lista é a recomendação única (DEC-077) — a MESMA do Mapa e de Oportunidades —,
   calculada no servidor sobre os hexágonos do território, com 20 vagas por segmento,
   e desenhada pelo componente único dela (`Top10Regioes`). Aqui só se escolhe
   quantas vagas mostrar e se avisa o mapa da região clicada.
   --------------------------------------------------------------------------- */

export default function RecomendacaoDoTerritorio({
  masterId,
  selecionado,
  onFocar,
}: {
  masterId: string
  /** O hexágono em foco no mapa (realçado na lista). */
  selecionado: string | null
  /** Clique numa região: o mapa aproxima nela e desenha o limite dela. */
  onFocar: (f: FocoNoMapa) => void
}) {
  // `undefined` = carregando; `null` = país sem régua (a recomendação não existe aqui).
  const [bloco, setBloco] = useState<RecomendacaoTop10 | null | undefined>(undefined)
  const [erro, setErro] = useState<string | null>(null)
  const [aberto, setAberto] = useState(false)

  useEffect(() => {
    let vivo = true
    setBloco(undefined)
    setErro(null)
    setAberto(false)
    api
      .masterRecomendacao(masterId)
      .then((r) => vivo && setBloco(r.recomendacao))
      .catch((e: ApiError) => vivo && setErro(e.message))
    return () => {
      vivo = false
    }
  }, [masterId])

  function selecionar(hexId: string) {
    if (!bloco) return
    const v = [...bloco.mata_virgem.vagas, ...bloco.premium.vagas].find((x) => x.hex_id === hexId)
    const regiao = v?.nome_regiao ?? v?.nome_municipio ?? 'Região recomendada'
    const nome = v?.nome_regiao && v.nome_municipio ? `${regiao} (${v.nome_municipio})` : regiao
    // O segmento e o rótulo da vaga (MV1, P1): a cor e o nome do hexágono no mapa.
    const marca = v && !v.vazia ? { segmento: v.segmento, rotulo: rotuloNoMapa(v) } : null
    onFocar(focoDoHexagono(hexId, nome, marca))
  }

  return (
    <Glass style={{ padding: '14px 16px', minWidth: 0 }}>
      <Eyebrow>Onde abrir: Mata Virgem e Premium</Eyebrow>
      <div style={{ font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-sub)', margin: '3px 0 12px' }}>
        a recomendação do motor (a mesma do Mapa e de Oportunidades), dentro do território do master; clique numa
        região para vê-la no mapa
      </div>
      {erro ? (
        <div style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--warn-text)' }}>{erro}</div>
      ) : bloco === undefined ? (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            font: '400 12px/1.5 var(--f-ui)',
            color: 'var(--tx-sub)',
          }}
        >
          <Spinner tamanho={13} />
          Calculando as regiões recomendadas do território…
        </div>
      ) : bloco === null ? (
        <div style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-sub)' }}>
          A recomendação do motor não existe para este país.
        </div>
      ) : (
        <>
          <Top10Regioes
            bloco={recorteDoTop(bloco, aberto ? bloco.regra.vagas_por_segmento : TOP_INICIAL)}
            variante="hero"
            selecionado={selecionado}
            onSelecionar={selecionar}
          />
          {temMaisQueOTop(bloco) && (
            <div style={{ display: 'flex', justifyContent: 'center', marginTop: 12 }}>
              <Botao variante="ghost" onClick={() => setAberto((a) => !a)} style={{ padding: '8px 16px' }}>
                {aberto ? `Mostrar só o top ${TOP_INICIAL}` : `Mostrar o top ${bloco.regra.vagas_por_segmento}`}
              </Botao>
            </div>
          )}
        </>
      )}
    </Glass>
  )
}
