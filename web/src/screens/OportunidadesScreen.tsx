import { useMemo, useState } from 'react'

import BotaoInicio from '../components/BotaoInicio'
import Select from '../components/Select'
import { Aviso, Chip, Eyebrow, Glass, Spinner } from '../components/primitives'
import { alunos, num } from '../lib/format'
import {
  filtrarPorCrescimento,
  lerCrescimento,
  leituraDoItem,
  ordenarComDesempate,
  temCoberturaSatelite,
  type CrescimentoMunicipio,
} from '../lib/oportunidades'
import type { MunicipioPayload, RankItem } from '../lib/types'

/**
 * Modo 3 — a FILA de melhores oportunidades, em tela propria.
 *
 * POR QUE NAO E' MAIS O MAPA NO PASSO 5. Ate aqui o card 3 abria o `MapScreen` com o
 * funil no ultimo passo. Funcionava, mas a pergunta do modo ("quais sao as melhores?")
 * ficava respondida de lado: o operador via o chrome do funil — camadas, stepper,
 * legenda, filtro de faixa — e a fila era uma lista no painel lateral. Aqui a fila E'
 * a tela, e cada item diz por que esta nela.
 *
 * A ORDEM E O CONTEUDO VEM DO SERVIDOR. Nada e' reordenado por criterio novo: a
 * cascata do passo 5 ja roda em producao (potencial >= 70, populacao >= 5.000,
 * residual >= 2.000, ZERO concorrente mapeado), ordenada por residual em alunos. O
 * unico rearranjo local e' o DESEMPATE por crescimento, e so' entre itens de residual
 * igual — `ordenarComDesempate` existe para isso e tem teste travando que crescimento
 * nunca vira peso.
 */
export default function OportunidadesScreen({
  ufs,
  uf,
  onUf,
  dados,
  carregando,
  erro,
  onInicio,
  onVerNoMapa,
}: {
  ufs: string[]
  uf: string
  onUf: (uf: string) => void
  dados: MunicipioPayload | null
  carregando: boolean
  erro: string | null
  onInicio: () => void
  /** Leva o operador ao mapa, no municipio escolhido. */
  onVerNoMapa: (municipio: string) => void
}) {
  const [soCrescendo, setSoCrescendo] = useState(false)

  const passo = dados?.passos?.find((p) => p.n === 5) ?? null
  const cres = dados?.cres_mun ?? null

  const itens = useMemo(() => {
    if (!passo) return []
    return filtrarPorCrescimento(ordenarComDesempate(passo.itens, cres), cres, soCrescendo)
  }, [passo, cres, soCrescendo])

  const escondidos = passo ? passo.itens.length - itens.length : 0

  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column' }}>
      <header
        style={{
          flexShrink: 0,
          margin: '16px 16px 0',
          padding: '9px 12px',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          flexWrap: 'wrap',
          background: 'var(--surf-chrome)',
          border: '1px solid var(--line-soft)',
          borderRadius: 'var(--r-xl)',
          backdropFilter: 'blur(14px)',
        }}
      >
        <BotaoInicio onInicio={onInicio} />
        <h1
          style={{
            font: '600 14px/1 var(--f-ui)',
            letterSpacing: '-.01em',
            color: 'var(--tx-max)',
            margin: 0,
          }}
        >
          Melhores oportunidades
        </h1>
        <Select
          label="Estado"
          value={uf}
          onChange={onUf}
          maxWidth={130}
          buscavel
          placeholder="Estado…"
          options={ufs.map((u) => ({ value: u, label: u }))}
        />
        {passo && <Chip>{passo.itens.length} na fila</Chip>}
      </header>

      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        <div style={{ maxWidth: 980, margin: '0 auto', display: 'grid', gap: 16 }}>
          {!uf && (
            <Aviso
              titulo="Escolha um estado"
              corpo="A fila é montada por estado: o motor lê a partição inteira da UF e devolve os hexágonos com mais alunos não atendidos onde a rede ainda tem espaço."
            />
          )}

          {carregando && (
            <p
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                font: '400 13px/1 var(--f-ui)',
                color: 'var(--tx-muted)',
              }}
            >
              <Spinner /> Lendo a partição do estado…
            </p>
          )}

          {erro && <Aviso titulo="Não deu para carregar" corpo={erro} />}

          {passo && !carregando && (
            <>
              {/* ---- Por que ESTES são os melhores ---- */}
              <Glass style={{ padding: 18, display: 'grid', gap: 10 }}>
                <Eyebrow dot>Como esta fila é montada</Eyebrow>
                <p
                  style={{
                    font: '400 14px/1.55 var(--f-story)',
                    color: 'var(--tx-strong)',
                    margin: 0,
                  }}
                >
                  {passo.narrativa}
                </p>
                {/* O funil em UMA linha: de onde partiu e o que sobrou. É a resposta a
                    "por que só estes?" sem o operador ter de percorrer 5 camadas. */}
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                  <Chip>{passo.funil_from}</Chip>
                  <span aria-hidden style={{ color: 'var(--tx-rank)' }}>→</span>
                  <Chip>
                    {num(passo.funil_big)} {passo.funil_unit}
                  </Chip>
                </div>
                <p style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
                  Ordenada por <strong style={{ color: 'var(--tx-soft)' }}>alunos não
                  atendidos</strong>, não por score: o score de residual satura em 100 acima de
                  2.500 alunos e empataria todo o topo da fila. Empates são desfeitos pelo
                  crescimento da cidade — que nunca reordena quem tem mais residual.
                </p>
              </Glass>

              {/* ---- Filtro ---- */}
              {passo.itens.length > 0 && (
                <div style={{ display: 'grid', gap: 6 }}>
                  <label
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      font: '500 12px/1.3 var(--f-ui)',
                      color: 'var(--tx-soft)',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={soCrescendo}
                      onChange={(e) => setSoCrescendo(e.target.checked)}
                    />
                    Só cidades crescendo acima da mediana do estado
                  </label>
                  {soCrescendo && escondidos > 0 && (
                    <span style={{ font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>
                      {escondidos} {escondidos === 1 ? 'item escondido' : 'itens escondidos'} pelo
                      filtro — a ordem não muda, só a visibilidade.
                    </span>
                  )}
                </div>
              )}

              {/* ---- A fila ---- */}
              {itens.length === 0 ? (
                <Aviso
                  titulo={soCrescendo ? 'Nenhuma cidade passou no filtro' : 'Fila vazia neste estado'}
                  corpo={
                    soCrescendo
                      ? 'Desligue o filtro de crescimento para ver a fila completa.'
                      : 'Nenhum hexágono passou na cascata. Município saturado sai com fila vazia de propósito: a camada só aceita área sem concorrente mapeado.'
                  }
                />
              ) : (
                <div style={{ display: 'grid', gap: 10 }}>
                  {itens.map((it) => (
                    <Cartao
                      key={`${it.rank}-${it.hex_id}`}
                      item={it}
                      cres={cres?.[it.municipio ?? it.titulo ?? '']}
                      onVerNoMapa={onVerNoMapa}
                    />
                  ))}
                </div>
              )}

              {!temCoberturaSatelite(dados?.uf) && (
                <p style={{ font: '400 11px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
                  Neste estado a camada de área construída (satélite) não tem cobertura — ela
                  colore o mapa em 12 UFs. Os números de emprego acima são de outra fonte
                  (CAGED) e seguem valendo, sempre lidos contra a mediana deste estado.
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

/** Um item da fila: o número que ordena, a leitura, e o caminho para o mapa. */
function Cartao({
  item,
  cres,
  onVerNoMapa,
}: {
  item: RankItem
  cres?: CrescimentoMunicipio
  onVerNoMapa: (municipio: string) => void
}) {
  const leitura = lerCrescimento(cres)
  const municipio = item.municipio ?? item.titulo ?? ''

  const corCres =
    leitura.classe === 'acima'
      ? 'var(--pos-text)'
      : leitura.classe === 'abaixo'
        ? 'var(--neg)'
        : 'var(--tx-sub)'

  return (
    <Glass style={{ padding: 16, display: 'grid', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <span
          className="num"
          style={{ font: '700 13px/1 var(--f-num)', color: 'var(--ac-text)', width: 26 }}
        >
          {item.rank}º
        </span>
        <span
          style={{
            flex: 1,
            minWidth: 0,
            font: '600 17px/1.2 var(--f-ui)',
            color: 'var(--tx-max)',
            letterSpacing: '-.01em',
          }}
        >
          {item.titulo}
        </span>
        {item.tag && <Chip cor={item.tag_cor} tom={item.tom}>{item.tag}</Chip>}
        <span className="num" style={{ font: '700 17px/1 var(--f-num)', color: 'var(--tx-max)' }}>
          {alunos(item.valor)}
        </span>
        <span style={{ font: '400 10px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
          alunos de residual
        </span>
      </div>

      {/* A leitura POR REGRA: diz o que o item já garante por estar na fila. */}
      <p style={{ font: '400 12px/1.55 var(--f-ui)', color: 'var(--tx-narrative)', margin: 0 }}>
        {leituraDoItem(item, cres)}
      </p>

      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5,
            font: '500 10.5px/1.3 var(--f-ui)',
            color: corCres,
          }}
        >
          <span aria-hidden style={{ width: 5, height: 5, borderRadius: '50%', background: corCres }} />
          {leitura.rotulo}
          {leitura.delta != null && (leitura.classe === 'acima' || leitura.classe === 'abaixo') && (
            <span className="num" style={{ font: '500 10px/1 var(--f-num)', opacity: 0.85 }}>
              ({leitura.delta > 0 ? '+' : ''}
              {leitura.delta.toFixed(1).replace('.', ',')} p.p.)
            </span>
          )}
        </span>
        <div style={{ flex: 1 }} />
        <button
          type="button"
          onClick={() => onVerNoMapa(municipio)}
          style={{
            padding: '7px 11px',
            borderRadius: 8,
            border: '1px solid var(--ac-a25)',
            background: 'var(--ac-a12)',
            color: 'var(--ac-chip)',
            font: '600 11.5px/1 var(--f-ui)',
          }}
        >
          Ver no mapa →
        </button>
      </div>
    </Glass>
  )
}
