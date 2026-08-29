import { useEffect, useState } from 'react'

import type { SearchPin } from './HexMap'
import { Aviso, Chip, Eyebrow, Spinner } from './primitives'
import { api, ApiError } from '../lib/api'
import { alunos, num } from '../lib/format'
import { destinoDoHex } from '../lib/oportunidades'
import type { HexagonoNacional, HexagonosPayload } from '../lib/types'

/**
 * Os melhores hexágonos do BRASIL — o Modo 3 sem precisar marcar um estado.
 *
 * O QUE ESTAVA ERRADO. O Modo 3 já lia o país inteiro, mas a leitura era POR ESTADO:
 * `RankingEstados` ordena as 27 UFs por residual SOMADO, o operador escolhia uma, e só
 * então o funil descia a município e, no fim, a hexágono. Quem perguntava "quais são os
 * melhores hexágonos do Brasil?" recebia uma resposta em outra escala — soma por estado
 * é grandeza de TAMANHO, e estado grande cheio de hexágono mediano vence estado pequeno
 * dono do melhor hexágono do país. O hexágono só existia no terceiro degrau, dentro de
 * uma cidade, dentro de um estado que o operador tinha de acertar antes.
 *
 * O QUE ESTA LISTA É. A mesma cascata do funil (potencial, população, residual, sem
 * concorrente) aplicada de uma vez sobre a base inteira, ordenada por alunos não
 * atendidos POR HEXÁGONO. Sem cota por estado e sem filtro de região antes da
 * ordenação — os dois reproduziriam o defeito acima.
 *
 * POR QUE O AVISO DE MEDIÇÃO ESTÁ AQUI E NÃO ESCONDIDO. O backend trata consumo de
 * concorrente AUSENTE como espaço livre. Dentro de uma UF isso é ruído; num ranking
 * nacional as UFs com mapeamento ralo subiriam inteiras, e a tela afirmaria "sem
 * concorrente" onde ninguém mediu. A lista diz quantos dos seus primeiros colocados
 * vêm de dado ausente, em vez de deixar o operador descobrir isso no campo.
 */
export default function RankingHexagonosBrasil({
  uf,
  municipio,
  onVerNoMapa,
}: {
  /** Filtro OPCIONAL. Vazio = o Brasil inteiro, que é como a tela abre. */
  uf: string
  municipio: string
  onVerNoMapa: (uf: string, municipio: string, pin: SearchPin) => void
}) {
  const [dados, setDados] = useState<HexagonosPayload | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [porMunicipio, setPorMunicipio] = useState(false)
  const [verTudo, setVerTudo] = useState(false)

  useEffect(() => {
    let vivo = true
    setDados(null)
    setErro(null)
    api
      .hexagonos({ uf, municipio, porMunicipio, limite: TETO_PEDIDO })
      .then((r) => vivo && setDados(r))
      .catch((e: ApiError) => vivo && setErro(e.message))
    return () => {
      vivo = false
    }
  }, [uf, municipio, porMunicipio])

  if (erro) return <Aviso titulo="Não deu para ler o ranking nacional" corpo={erro} />

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
        <Spinner /> Varrendo os hexágonos do Brasil…
      </p>
    )
  }

  const { itens, cobertura } = dados
  const visiveis = verTudo ? itens : itens.slice(0, TOP_VISIVEL)
  const recorte = municipio || uf

  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <div style={{ display: 'grid', gap: 6 }}>
        <Eyebrow dot>A resposta</Eyebrow>
        <span style={{ font: '400 24px/1.2 var(--f-story)', color: 'var(--tx-max)' }}>
          {recorte
            ? `Melhores hexágonos de ${recorte}`
            : `Os ${Math.min(TOP_VISIVEL, itens.length)} melhores hexágonos do Brasil`}
        </span>
        <p style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
          Ordenados por <strong style={{ color: 'var(--tx-soft)' }}>alunos não atendidos no
          próprio hexágono</strong>
          {/* Com filtro a frase "sobre a base inteira" passaria a ser falsa. O que
              importa dizer no recorte é OUTRA coisa: que ele é um corte da lista
              nacional, feito depois da ordenação — e não um ranking próprio daquele
              estado, que é justamente a leitura que esta tela deixou de fazer. */}
          {recorte ? (
            <>
              {' '}
              — este é o recorte de <strong style={{ color: 'var(--tx-soft)' }}>{recorte}</strong>{' '}
              dentro do ranking nacional, não um ranking à parte.
            </>
          ) : (
            <>, sobre a base inteira — não por estado.</>
          )}{' '}
          {/* Os números saem do payload, nunca escritos à mão: este texto já mentiu uma
              vez, prometendo "nenhum concorrente" depois que a DEC-041 passou a admitir
              até `conc_max`. */}
          A cascata é a mesma do funil: potencial acima de {num(dados.reguas.score_minimo)},
          população acima de {num(dados.reguas.pop_minima)} e até{' '}
          {num(dados.reguas.conc_max)} concorrentes estimados a 2 km — praça disputada não é
          praça descartada. A ordem sai do índice de praça, que pondera perfil
          socioeconômico e demanda não atendida.
        </p>
      </div>

      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        {/* Com "um por cidade" ligado, `hexes_no_recorte` deixa de contar hexágonos e
            passa a contar CIDADES — dizer "14 de 125 acionáveis" ali afirmaria que só
            14 hexágonos passam na cascata, quando 125 passam e 14 é o número de cidades
            distintas entre eles. Duas grandezas no mesmo "N de M" é exatamente o tipo de
            comparação torta que esta tela existe para desfazer. */}
        <Chip>
          {porMunicipio
            ? `${num(cobertura.hexes_no_recorte)} cidades · ${num(cobertura.hexes_acionaveis_brasil)} hexágonos acionáveis`
            : `${num(cobertura.hexes_no_recorte)} de ${num(cobertura.hexes_acionaveis_brasil)} acionáveis`}
        </Chip>
        <Chip>
          {num(cobertura.ufs_no_recorte)}{' '}
          {cobertura.ufs_no_recorte === 1 ? 'estado na lista' : 'estados na lista'}
        </Chip>
        {/* A convenção "um por cidade" já existe no ranking do funil (`_rank_items`).
            Aqui ela é OPCIONAL e sai desligada: o pedido foi hexágono, não cidade —
            mas sem a opção o topo de uma região metropolitana vira uma sequência de
            hexágonos vizinhos, tecnicamente certos e inúteis como lista de decisão. */}
        <button
          type="button"
          onClick={() => setPorMunicipio((v) => !v)}
          style={{
            padding: '5px 10px',
            borderRadius: 8,
            border: `1px solid ${porMunicipio ? 'var(--ac-a25)' : 'var(--line-soft)'}`,
            background: porMunicipio ? 'var(--ac-a12)' : 'var(--surf-raised)',
            color: porMunicipio ? 'var(--ac-chip)' : 'var(--tx-soft)',
            font: '600 11px/1 var(--f-ui)',
          }}
        >
          {porMunicipio ? '✓ Um por cidade' : 'Um por cidade'}
        </button>
      </div>

      {/* Nota de RODAPÉ da lista, não manchete.
          Usar o `Aviso` aqui foi um erro de peso visual: ele renderiza centralizado e
          em fonte de narrativa, e a ressalva ficava maior que a resposta que ela
          ressalva — visto na prévia de 28/08/2026. A informação importa e continua
          inteira; o que muda é a hierarquia. */}
      {cobertura.topo_sem_medicao > 0 && (
        <p
          style={{
            display: 'flex',
            gap: 8,
            alignItems: 'baseline',
            font: '400 11.5px/1.5 var(--f-ui)',
            color: 'var(--tx-sub)',
            margin: 0,
            padding: '8px 10px',
            borderRadius: 'var(--r-md)',
            border: '1px dashed var(--line-strong)',
          }}
        >
          <strong style={{ color: 'var(--tx-soft)', whiteSpace: 'nowrap' }}>
            {num(cobertura.topo_sem_medicao)} sem medição
          </strong>
          <span>
            Nesses hexágonos o consumo de concorrentes está <strong>ausente na base</strong>, não
            foi medido como zero — e a leitura os trata como espaço livre, o que num ranking
            nacional favorece as regiões menos mapeadas. Seguem na lista, marcados, para
            conferência em campo antes de virar decisão.
          </span>
        </p>
      )}

      {itens.length === 0 ? (
        <Aviso
          titulo="Nenhum hexágono passa na cascata neste recorte"
          corpo="Sem área de alto potencial, povoada e livre de concorrente aqui. Tire o filtro de estado ou município para ver o país inteiro."
        />
      ) : (
        <div style={{ display: 'grid', gap: 8 }}>
          {visiveis.map((h) => (
            <LinhaHexagono key={h.hex_id} hex={h} onVerNoMapa={onVerNoMapa} />
          ))}
          {itens.length > TOP_VISIVEL && (
            <button
              type="button"
              onClick={() => setVerTudo((v) => !v)}
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
              {verTudo ? `Mostrar só o top ${TOP_VISIVEL}` : `Ver os ${itens.length} da lista`}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

/** Quantos hexágonos a tela pede ao servidor. Teto de payload, não régua de negócio. */
const TETO_PEDIDO = 50
/** Quantos aparecem antes de "ver todos" — o que cabe numa decisão. */
const TOP_VISIVEL = 10

function LinhaHexagono({
  hex,
  onVerNoMapa,
}: {
  hex: HexagonoNacional
  onVerNoMapa: (uf: string, municipio: string, pin: SearchPin) => void
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        flexWrap: 'wrap',
        padding: '10px 12px',
        borderRadius: 'var(--r-md)',
        background: 'var(--surf-raised)',
        border: '1px solid var(--line-soft)',
      }}
    >
      <span
        className="num"
        style={{ font: '700 14px/1 var(--f-num)', color: 'var(--ac-text)', width: 30 }}
      >
        {hex.rank}º
      </span>
      <span style={{ flex: 1, minWidth: 140, display: 'grid', gap: 2 }}>
        <span style={{ font: '600 15px/1.2 var(--f-ui)', color: 'var(--tx-max)' }}>
          {hex.municipio ?? 'Município não identificado'}
          <span style={{ color: 'var(--tx-sub)', font: '500 12px/1 var(--f-ui)' }}>
            {' '}
            · {hex.uf ?? '—'}
          </span>
        </span>
        <span className="num" style={{ font: '400 10px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
          hex {hex.hex_id.slice(0, 9)}…
        </span>
      </span>

      {hex.tag && (
        <span
          style={{
            font: '600 10px/1 var(--f-ui)',
            padding: '4px 7px',
            borderRadius: 6,
            color: hex.tag_cor ?? 'var(--tx-soft)',
            border: `1px solid ${hex.tag_cor ?? 'var(--line-soft)'}`,
          }}
        >
          {hex.tag}
        </span>
      )}
      {/* A marca fica no ITEM, e não só no resumo: quem rola a lista tem de ver qual
          linha específica está apoiada em dado ausente. */}
      {!hex.consumo_medido && (
        <span
          title="Consumo de concorrente ausente na base — tratado como espaço livre"
          style={{
            font: '600 10px/1 var(--f-ui)',
            padding: '4px 7px',
            borderRadius: 6,
            color: 'var(--tx-sub)',
            border: '1px dashed var(--line-strong)',
          }}
        >
          sem medição
        </span>
      )}

      <span style={{ display: 'grid', justifyItems: 'end', minWidth: 78 }}>
        <span
          className="num"
          style={{
            font: '600 14px/1 var(--f-num)',
            color: 'var(--tx-max)',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {alunos(hex.residual)}
        </span>
        <span style={{ font: '400 9.5px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>residual</span>
      </span>

      {/* Leva ao HEXÁGONO, não à cidade dele: o pin faz a câmera voar até a coordenada,
          desenha o contorno de seleção e abre a ficha — as três leituras que o mapa já
          sabe amarrar. Levar só ao município deixava o operador reencontrar a olho,
          numa cidade inteira, o hexágono que ele acabara de escolher na lista. */}
      <button
        type="button"
        onClick={() => {
          const destino = destinoDoHex(hex)
          if (destino) onVerNoMapa(destino.uf, destino.municipio, destino.pin)
        }}
        disabled={destinoDoHex(hex) === null}
        style={{
          padding: '6px 10px',
          borderRadius: 8,
          border: '1px solid var(--ac-a25)',
          background: 'var(--ac-a12)',
          color: 'var(--ac-chip)',
          font: '600 11px/1 var(--f-ui)',
          opacity: destinoDoHex(hex) ? 1 : 0.4,
        }}
      >
        Ver no mapa →
      </button>
    </div>
  )
}
