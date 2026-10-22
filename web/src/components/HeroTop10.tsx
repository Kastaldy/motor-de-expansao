import { useEffect, useState } from 'react'

import type { SearchPin } from './HexMap'
import Top10Regioes from './Top10Regioes'
import { Aviso, Chip, Eyebrow, Spinner } from './primitives'
import { api, ApiError } from '../lib/api'
import { num } from '../lib/format'
import { temTop10, tituloTop10 } from '../lib/top10'
import type { HexagonosResposta } from '../lib/types'

/**
 * O hero de Oportunidades: o Top 10 do recorte (recomendação única, DEC-077).
 *
 * O recorte segue os filtros do cabeçalho — sem filtro, o Brasil; com a UF, o estado; com o
 * município, o município. Quem decide o Top 10 é o servidor (`/api/hexagonos`), com a MESMA
 * função que monta o passo 5 do mapa: o Top 10 do município aqui é o mesmo que o operador
 * vê no mapa daquele município, e o do Brasil cai no Top 10 da própria UF, no mesmo
 * segmento (as réguas são absolutas).
 *
 * Substitui o antigo ranking nacional por índice de praça (com "um por cidade", lista de 50
 * e marca de "sem medição"): nenhum desses conceitos existe na regra nova. Sem o bloco
 * (instância sem régua), a tela diz que a recomendação não está disponível — nunca mostra
 * uma lista calculada por outra regra.
 */
export default function HeroTop10({
  uf,
  municipio,
  onVerNoMapa,
}: {
  /** Filtro OPCIONAL. Vazio = o Brasil inteiro, que é como a tela abre. */
  uf: string
  municipio: string
  onVerNoMapa: (uf: string, municipio: string, pin: SearchPin) => void
}) {
  const [dados, setDados] = useState<HexagonosResposta | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    let vivo = true
    setDados(null)
    setErro(null)
    api
      .hexagonos({ uf, municipio })
      .then((r) => vivo && setDados(r))
      .catch((e: ApiError) => vivo && setErro(e.message))
    return () => {
      vivo = false
    }
  }, [uf, municipio])

  if (erro) return <Aviso titulo="Não deu para calcular o Top 10" corpo={erro} />

  if (!dados) {
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
        <Spinner /> Calculando o Top 10…
      </p>
    )
  }

  if (!temTop10(dados)) {
    return (
      <Aviso
        titulo="Recomendação indisponível nesta instância"
        corpo="Esta instância não tem a régua do Top 10. As leituras por camada, abaixo, continuam valendo."
      />
    )
  }

  const bloco = dados.recomendacao
  /* `cobertura` é contrato da rota; se um servidor a omitisse, o próprio bloco ainda sabe
     quantos hexágonos leu — o chip nunca mostra "Não disponível" no denominador. */
  const hexes = dados.cobertura?.hexes_no_recorte ?? bloco.n_hexes_recorte
  const ufs = dados.cobertura?.ufs_no_recorte ?? 0
  const doBrasil = bloco.recorte.nivel === 'brasil'

  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <div style={{ display: 'grid', gap: 6 }}>
        <Eyebrow dot>Recomendação</Eyebrow>
        <span style={{ font: '400 24px/1.2 var(--f-story)', color: 'var(--tx-max)' }}>
          {tituloTop10(bloco)}
        </span>
      </div>

      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        {/* O denominador do Top 10: ele lê TODOS os hexágonos do recorte com régua própria
            — não é um filtro de camada anterior. */}
        <Chip>
          Sobre {num(hexes)} {hexes === 1 ? 'hexágono' : 'hexágonos'}
          {doBrasil ? ` · ${num(ufs)} ${ufs === 1 ? 'estado' : 'estados'}` : ''}
        </Chip>
      </div>

      <Top10Regioes
        bloco={bloco}
        variante="hero"
        mostrarRegua
        onVerNoMapa={(d) => onVerNoMapa(d.uf, d.municipio, d.pin)}
      />
    </div>
  )
}
