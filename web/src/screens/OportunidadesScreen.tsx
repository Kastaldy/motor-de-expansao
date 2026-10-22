import { useMemo } from 'react'

import BotaoInicio from '../components/BotaoInicio'
import HeroTop10 from '../components/HeroTop10'
import type { SearchPin } from '../components/HexMap'
import RankingEstados from '../components/RankingEstados'
import Select from '../components/Select'
import { Aviso, Glass, Spinner } from '../components/primitives'
import { camadaCor } from '../lib/colors'
import { alunos, num } from '../lib/format'
import {
  lerCrescimento,
  temCoberturaSatelite,
  type CrescimentoMunicipio,
} from '../lib/oportunidades'
import { leiturasDoRecorte, temTop10 } from '../lib/top10'
import type { MunicipioItem, MunicipioPayload, Passo, RankItem } from '../lib/types'

/**
 * Modo 3 — o Top 10 por hexágono. ENTRA PELO BRASIL, não por um estado.
 *
 * A RESPOSTA É UMA SÓ (recomendação única, DEC-077): o Top 10 do recorte — 5 Mata Virgem
 * + 5 Premium por hexágono —, montado no servidor pela MESMA função que monta o passo 5 do
 * mapa (`HeroTop10` -> `/api/hexagonos`). Estado e município são FILTROS do cabeçalho: sem
 * filtro, o Top 10 do Brasil; com a UF, o do estado; com o município, o do município. Como
 * as réguas são absolutas, um hexágono do Top 10 do Brasil está também no Top 10 da UF e do
 * município dele, no mesmo segmento.
 *
 * O QUE SAIU. A tela tinha DUAS "respostas": o ranking nacional por índice de praça e um
 * "Top 5 cidades/bairros" que CONTAVA em quantas camadas cada nome aparecia, desempatando
 * pela fila do passo 5. Os dois eram outras definições de "onde expandir" — exatamente o que
 * a recomendação única existe para eliminar. Saíram junto com `lib/consolidado.ts`.
 *
 * O QUE FICOU, COMO LEITURA. O ranking de estados ("residual somado por estado") continua
 * sendo o seletor de UF, mas declarado como leitura de tamanho. E as camadas 1 a 4 do
 * recorte aparecem abaixo como "Leituras do recorte — não entram na recomendação": o topo
 * de cada uma, com o número que ordena aquela leitura. A camada 5 não se repete aqui — ela
 * é o hero.
 */
export default function OportunidadesScreen({
  ufs,
  uf,
  onUf,
  dados,
  carregando,
  erro,
  municipios,
  municipio,
  onMunicipio,
  onInicio,
  onVerNoMapa,
  onVerHexNoMapa,
}: {
  ufs: string[]
  uf: string
  onUf: (uf: string) => void
  municipios: MunicipioItem[]
  municipio: string
  onMunicipio: (m: string) => void
  dados: MunicipioPayload | null
  carregando: boolean
  erro: string | null
  onInicio: () => void
  onVerNoMapa: (municipio: string) => void
  /**
   * Um item do Top 10 leva UF e HEXÁGONO junto: sem a UF o mapa abriria o município certo
   * no estado em que o operador já estava — que pode não ser nenhum —, e sem o pin ele
   * pararia na cidade inteira, deixando o operador reencontrar a olho o hexágono que acabou
   * de escolher.
   */
  onVerHexNoMapa: (uf: string, municipio: string, pin: SearchPin) => void
}) {
  const passos = dados?.passos ?? []
  const cres = dados?.cres_mun ?? null

  const leituras = useMemo(() => leiturasDoRecorte(passos), [passos])

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
          // `position: relative` + `zIndex` sao OBRIGATORIOS, nao enfeite. O
          // `backdropFilter` cria um CONTEXTO DE EMPILHAMENTO, entao o zIndex do popup
          // do Select so' vale DENTRO deste cabecalho — sem elevar o cabecalho inteiro,
          // o conteudo que vem depois no DOM (que tambem tem backdropFilter) pinta por
          // cima e a lista de estados abre ATRAS dos cards. Mesma armadilha ja
          // documentada no ExecutiveScreen.
          position: 'relative',
          zIndex: 30,
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
          Top 10 por hexágono
        </h1>
        {/* Rótulo e placeholder dizem que a UF é FILTRO: a tela já respondeu a pergunta
            antes de o operador tocar aqui. A opção vazia é o que permite desfazer o recorte
            e voltar ao Brasil — sem ela, escolher um estado seria um caminho sem volta. */}
        <Select
          label="Filtrar estado"
          value={uf}
          onChange={onUf}
          maxWidth={150}
          buscavel
          placeholder="Brasil inteiro"
          options={[
            { value: '', label: 'Brasil inteiro' },
            ...ufs.map((u) => ({ value: u, label: u })),
          ]}
        />
        {/* O drill-down para MUNICÍPIO recorta o Top 10 ao município (e, nas leituras
            abaixo, os itens deixam de ser cidades e passam a ser bairros). */}
        {uf && (
          <Select
            label="Município"
            value={municipio}
            onChange={onMunicipio}
            maxWidth={190}
            buscavel
            placeholder="Estado inteiro"
            options={[
              { value: '', label: 'Estado inteiro' },
              ...municipios.map((m) => ({ value: m.nome, label: m.nome })),
            ]}
          />
        )}
      </header>

      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        <div style={{ maxWidth: 1000, margin: '0 auto', display: 'grid', gap: 18 }}>
          {/* A RESPOSTA vem primeiro: o Top 10 do recorte. Tudo o que vem depois — o
              residual por estado e as camadas de leitura — é contexto, não recomendação. */}
          <Glass style={{ padding: 18 }}>
            <HeroTop10 uf={uf} municipio={municipio} onVerNoMapa={onVerHexNoMapa} />
          </Glass>

          {/* O ranking de estados continua sendo o seletor de UF — e filtra o Top 10 acima. */}
          <Glass style={{ padding: 18 }}>
            <RankingEstados ufSelecionada={uf} onEscolher={onUf} />
          </Glass>

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

          {leituras.length > 0 && !carregando && (
            <>
              <div style={{ display: 'grid', gap: 4, marginTop: 2 }}>
                <span style={{ font: '600 12px/1 var(--f-ui)', color: 'var(--tx-soft)' }}>
                  Leituras do recorte — não entram na recomendação
                </span>
                <span style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)' }}>
                  O topo de cada camada de leitura, com o número que ordena aquela leitura.
                </span>
              </div>

              {leituras.map(({ passo, itens }) => (
                <BlocoCamada
                  key={passo.n}
                  passo={passo}
                  itens={itens}
                  cres={cres}
                  nivelMunicipio={Boolean(municipio)}
                  leitura={temTop10(dados)}
                  onVerNoMapa={onVerNoMapa}
                />
              ))}

              {!temCoberturaSatelite(dados?.uf) && (
                <p style={{ font: '400 11px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
                  Neste estado a camada de área construída (satélite) não tem cobertura — ela
                  colore o mapa em 12 UFs. O crescimento acima vem de outra fonte (CAGED) e segue
                  valendo, sempre lido contra a mediana deste estado.
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

/** Uma camada de leitura: o topo dela, com a identidade de cor que o funil já usa. */
function BlocoCamada({
  passo,
  itens,
  cres,
  nivelMunicipio,
  leitura,
  onVerNoMapa,
}: {
  passo: Passo
  itens: RankItem[]
  cres: Record<string, CrescimentoMunicipio> | null
  /** Dentro de um município os itens são BAIRROS, não cidades. */
  nivelMunicipio: boolean
  /** Payload com o Top 10 (bloco `recomendacao`): a camada é LEITURA, e o vazio não é
   *  "ninguém passou". Sem o bloco (instância sem régua), o texto de sempre. */
  leitura: boolean
  onVerNoMapa: (municipio: string) => void
}) {
  const cor = camadaCor(passo.n)

  return (
    <Glass style={{ padding: 18, display: 'grid', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <span
          className="num"
          style={{
            font: '700 10.5px/1 var(--f-num)',
            color: cor.fg,
            background: cor.bg,
            border: `1px solid ${cor.borda}`,
            borderRadius: 6,
            padding: '4px 7px',
          }}
        >
          CAMADA {passo.n}
        </span>
        <span style={{ font: '600 15px/1.2 var(--f-ui)', color: 'var(--tx-max)' }}>
          {passo.titulo}
        </span>
        <span style={{ font: '400 11px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
          top {itens.length} · ordenado por {passo.metrica}
        </span>
      </div>

      {itens.length === 0 ? (
        <p style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-muted)', margin: 0 }}>
          {/* A camada 4 e' MUNICIPAL por natureza: dentro de uma cidade nao ha o que
              ranquear entre bairros, e dizer "nenhum bairro passou" sugeriria que
              todos foram reprovados. */}
          {nivelMunicipio && passo.n === 4
            ? 'O crescimento é medido por município — dentro de uma cidade não há o que comparar entre bairros. Volte ao estado inteiro para ver esta camada.'
            : nivelMunicipio
              ? leitura
                ? 'Nenhum bairro aparece nesta leitura.'
                : 'Nenhum bairro passou nesta camada.'
              : leitura
                ? 'Nenhuma cidade aparece nesta leitura.'
                : 'Nenhuma cidade passou nesta camada.'}
        </p>
      ) : (
        <div style={{ display: 'grid', gap: 4 }}>
          {itens.map((it, i) => {
            const municipio = it.municipio ?? it.titulo ?? ''
            const leitura = lerCrescimento(cres?.[municipio])
            return (
              <button
                key={`${passo.n}-${it.rank}-${municipio}`}
                type="button"
                onClick={() => onVerNoMapa(municipio)}
                title={`Ver ${municipio} no mapa`}
                style={{
                  display: 'flex',
                  alignItems: 'baseline',
                  gap: 10,
                  padding: '7px 8px',
                  borderRadius: 8,
                  border: '1px solid transparent',
                  background: 'transparent',
                  textAlign: 'left',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'var(--surf-raised)'
                  e.currentTarget.style.borderColor = 'var(--line-soft)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent'
                  e.currentTarget.style.borderColor = 'transparent'
                }}
              >
                <span
                  className="num"
                  style={{ font: '600 11px/1 var(--f-num)', color: cor.fg, width: 18 }}
                >
                  {i + 1}º
                </span>
                <span
                  style={{
                    flex: 1,
                    minWidth: 0,
                    font: '500 13px/1.3 var(--f-ui)',
                    color: 'var(--tx-strong)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {it.titulo}
                </span>
                {/* So' na camada de crescimento: nas outras a etiqueta seria ruido,
                    porque o que ordena ali nao e o crescimento. */}
                {passo.n === 4 && leitura.classe !== 'sem-dado' && (
                  <span
                    style={{
                      font: '500 10px/1 var(--f-ui)',
                      color:
                        leitura.classe === 'acima'
                          ? 'var(--pos-text)'
                          : leitura.classe === 'abaixo'
                            ? 'var(--neg)'
                            : 'var(--tx-sub)',
                    }}
                  >
                    {leitura.rotulo}
                  </span>
                )}
                <span
                  className="num"
                  style={{
                    font: '600 13px/1 var(--f-num)',
                    color: 'var(--tx-max)',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {it.label === 'residual' ? alunos(it.valor) : num(it.valor)}
                </span>
                <span
                  style={{
                    font: '400 9.5px/1 var(--f-ui)',
                    color: 'var(--tx-sub)',
                    minWidth: 54,
                  }}
                >
                  {it.label}
                </span>
              </button>
            )
          })}
        </div>
      )}
    </Glass>
  )
}
