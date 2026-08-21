import type { ReactNode } from 'react'

import type { CrescimentoMunicipio } from '../lib/oportunidades'
import { alunos, brl, num, pctVar } from '../lib/format'
import { corTipo, custoOcup, labelTipo } from '../lib/imovel'
import type { Hex, Oportunidade } from '../lib/types'
import { FAIXAS_DEMANDA, FAIXAS_POTENCIAL } from '../lib/faixas'
import IconeTipo from './IconeTipo'
import { BarraMercado, FilaApoio, MedidorScore, NumeroApoio } from './LeiturasVisuais'
import { Chip, Eyebrow, Kpi } from './primitives'

/**
 * A leitura de UM hexagono, para viver dentro da janela flutuante do mapa.
 *
 * POR QUE EXISTE. O dado do hexagono so' aparecia em dois lugares efemeros: o tooltip,
 * que some quando o mouse sai, e a linha do painel de ranking, que mostra UMA metrica (a
 * da camada ativa). Quem escolhe entre dois bairros precisava trocar de camada quatro
 * vezes para juntar populacao, renda, concorrencia e residual do mesmo hexagono. Aqui as
 * quatro leituras ficam paradas na tela, do mesmo jeito que a ficha do ponto colado.
 *
 * SEM VIABILIDADE, de proposito. Metragem e aluguel sao ENTRADA do operador sobre um
 * IMOVEL concreto (DEC-009, motor property-first); um hexagono e' uma area de ~5 km2, e
 * pedir "o aluguel do hexagono" seria inventar um imovel que nao existe. Quem tem o
 * imovel na mao entra pela analise de ponto, que ja' faz essa conta.
 *
 * NADA E' DERIVADO AQUI. Todo numero vem do payload; o que falta aparece como "—" em vez
 * de virar zero — zero e' uma AFIRMACAO ("nao ha' concorrente"), e ausencia nao afirma.
 */
export default function FichaHex({
  hex,
  cres,
  onComparar,
  imoveis,
  onVerImovel,
}: {
  hex: Hex
  /** Crescimento do MUNICÍPIO do hexágono (`MapaResposta.cres_mun`), quando houver. */
  cres?: CrescimentoMunicipio | null
  /**
   * Põe ESTE hexágono na comparação e liga o modo cenário. Ausente = o botão não aparece.
   *
   * SEM estado de "já está comparando", e isso é medido, não esquecimento: esta janela só
   * abre com `!modoCenario` (`MapScreen`), e desligar o modo zera a lista. Logo o hexágono
   * nunca está na comparação enquanto a ficha está aberta — um rótulo "tirar da
   * comparação" seria um estado inalcançável prometendo comportamento que não existe.
   */
  onComparar?: () => void
  /**
   * Oportunidades imobiliárias coletadas DENTRO deste hexágono (casadas por `hex_id`,
   * H3 res-7 — a mesma malha do M1). Vazia ou ausente = a seção não aparece: a maioria
   * dos hexágonos não tem imóvel coletado, e um bloco "nenhum" em todos eles seria ruído.
   */
  imoveis?: Oportunidade[]
  /** Abre a janela de DETALHE do imóvel (a mesma que o pin da camada abre no mapa). */
  onVerImovel?: (o: Oportunidade) => void
}) {
  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <div>
        <Eyebrow dot>Hexágono selecionado</Eyebrow>
        <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span
            className="num"
            style={{
              font: '500 11px/1 var(--f-num)',
              color: 'var(--tx-sub)',
              padding: '5px 8px',
              borderRadius: 7,
              background: 'var(--surf-raised)',
              border: '1px solid var(--line-soft)',
            }}
          >
            {hex.id}
          </span>
          {hex.faixa && <Chip tom="blue">{hex.faixa}</Chip>}
          {/* O centroide no Maps: é assim que o operador sai da tela e vai ver a rua.
              O hexágono tem ~5 km², então isto abre no CENTRO dele — não num endereço,
              que o hexágono não tem. O rótulo diz isso para ninguém ler como "o imóvel". */}
          <a
            href={`https://www.google.com/maps/search/?api=1&query=${hex.lat},${hex.lng}`}
            target="_blank"
            rel="noreferrer"
            style={{
              font: '600 11px/1 var(--f-ui)',
              color: 'var(--ac-text)',
              textDecoration: 'underline',
            }}
          >
            Abrir o centro no Google Maps ↗
          </a>
          {/* COMPARAR A PARTIR DAQUI (pedido do Juan, 2026-08-13). A comparação já
              existia, mas só se alcançava entrando no modo cenário ANTES de escolher — ou
              seja, quem já estava lendo uma ficha tinha de sair dela e recomeçar. O botão
              põe este hexágono na lista e liga o modo; o próximo clique no mapa entra como
              o segundo, e a comparação aparece sozinha. */}
          {onComparar && (
            <button
              type="button"
              onClick={onComparar}
              title="Põe este hexágono na comparação — clique em outro no mapa para comparar os dois"
              style={{
                padding: '4px 9px',
                borderRadius: 999,
                border: '1px solid var(--line-soft)',
                background: 'var(--surf-raised)',
                color: 'var(--tx-soft)',
                font: '600 11px/1 var(--f-ui)',
              }}
            >
              + Comparar com outro
            </button>
          )}
        </div>
      </div>

      {/* MESMA HIERARQUIA da ficha do ponto: desenho primeiro, número como apoio. Duas
          fichas que respondem à mesma pergunta não podem ler de jeitos diferentes. */}
      <Bloco titulo="Quem mora aqui" nota="Censo 2022 (IBGE), no hexágono">
        <MedidorScore rotulo="Score censitário" valor={hex.censo} faixas={FAIXAS_POTENCIAL} />
        <FilaApoio>
          <NumeroApoio rotulo="População" valor={num(hex.pop)} />
          <NumeroApoio rotulo="Renda per capita" valor={hex.renda == null ? '—' : brl(hex.renda)} />
          <NumeroApoio
            rotulo="Renda domiciliar"
            valor={hex.renda_dom == null ? '—' : brl(hex.renda_dom)}
          />
        </FilaApoio>
      </Bloco>

      {/* CONTAGEM, e do HEXAGONO. Até 2026-08-13 este bloco lia `hex.conc`/`hex.ultra`,
          que não são nenhuma das duas coisas: `conc` é `oferta_consumida_mercado_estimada
          / 2.500` — capacidade do modelo de 2 km ponderado por distância —, então uma
          concorrente a 1,8 km do centroide entrava aqui sem estar dentro do hexágono, e
          `ultra` vem da camada de performance. O rótulo prometia "unidades mapeadas
          dentro do hexágono" e entregava outra medida. O mesmo defeito de redação já
          tinha sido corrigido no texto do funil ("RAIO, NÃO HEXÁGONO", em `app.py`).
          Agora vem de `conc_hex`/`ultra_hex`, contagem de ponto por célula H3 res-7 sobre
          os MESMOS pontos que viram pin no mapa — ficha e mapa não podem discordar. */}
      <Bloco titulo="Quem já disputa o aluno" nota="unidades mapeadas dentro do hexágono">
        <FilaApoio>
          <NumeroApoio
            rotulo="Concorrentes"
            valor={hex.conc_hex == null ? '—' : num(hex.conc_hex)}
          />
          <NumeroApoio
            rotulo="Unidades Ultra"
            valor={hex.ultra_hex == null ? '—' : num(hex.ultra_hex)}
          />
        </FilaApoio>
      </Bloco>

      <Bloco titulo="Quanto de mercado sobra" nota="capacidade, não meta de abertura">
        <BarraMercado sam={hex.sam} residual={hex.oferta} />
        <MedidorScore
          rotulo="Score de residual"
          valor={hex.res}
          faixas={FAIXAS_DEMANDA}
          nota="satura em 100 acima de 2.500 alunos — uma unidade cheia"
        />
        {/* SEM faixas: o híbrido combina duas escalas (censo e residual) e não tem régua
            nomeada publicada. Colorir por analogia daria a ele um veredito que ninguém
            aprovou. Fica na cor neutra. */}
        <MedidorScore rotulo="Score híbrido" valor={hex.hib} />
        <FilaApoio>
          <NumeroApoio
            rotulo="Mercado potencial (SAM)"
            valor={hex.sam == null ? '—' : alunos(hex.sam)}
          />
          <NumeroApoio
            rotulo="Residual disponível"
            valor={hex.oferta == null ? '—' : alunos(hex.oferta)}
          />
        </FilaApoio>
      </Bloco>

      {/* A OFERTA IMOBILIÁRIA coletada dentro do hexágono. É a ponte entre as duas
          leituras: o residual acima diz quanto mercado sobra, e aqui está o imóvel
          concreto para capturá-lo. Os quatro números são os MESMOS do ranking da aba
          (Aluguel, Custo de ocupação, Projeção de faturamento, Área) — o clique abre
          a janela de detalhe, e dela se vai para a aba já focado no imóvel. */}
      {imoveis != null && imoveis.length > 0 && (
        <Bloco
          titulo="Imóveis disponíveis aqui"
          nota={
            imoveis.length === 1
              ? '1 oportunidade coletada neste hexágono'
              : `${num(imoveis.length)} oportunidades coletadas neste hexágono`
          }
        >
          {imoveis.map((o) => (
            <CartaoImovel key={o.id} op={o} onAbrir={onVerImovel ? () => onVerImovel(o) : undefined} />
          ))}
        </Bloco>
      )}

      {/* O crescimento tem DUAS bases e elas não se misturam: a obra nova é DESTE
          hexágono (satélite); o emprego formal é do MUNICÍPIO inteiro (CAGED). Rotular as
          duas como "crescimento do hexágono" afirmaria sobre a área uma medida que é da
          cidade. Some inteiro quando nenhuma das duas existe — bloco sem dado declara o
          motivo, nunca desaparece em silêncio. */}
      {(hex.cres_hex_classe || hex.cres_hex_taxa != null || cres) && (
        <Bloco titulo="Como a região vem indo" nota={hex.mun ? `obra nova aqui · emprego em ${hex.mun}` : undefined}>
          {/* Sinal EXPLICITO nas duas taxas deste bloco (`pctVar`). São VARIAÇÃO, não
              participação: sem o `+`, "8,8%" não diz se a cidade cresceu ou se aquilo é
              um patamar — e o bloco inteiro existe para responder "como a região vem
              indo". O negativo já vinha; o positivo é que era mudo. */}
          {/* A guarda `== null ? '—'` TEM de ficar: `pctVar` devolve `TEXTO_SEM_DADO`, que
              é "Não disponível" por extenso, e este `Kpi` desenha o valor em 700 24px com
              `nowrap` + `ellipsis` — o texto sairia truncado como "Não dispo…". Perdi a
              guarda ao trocar `pct` por `pctVar`; o travessão curto é a regra deste
              arquivo e a mesma nota que escrevi em `exec/PainelRede`. */}
          <Kpi
            label="Obra nova (2016→2023)"
            valor={hex.cres_hex_taxa == null ? '—' : pctVar(hex.cres_hex_taxa)}
            sub={hex.cres_hex_classe ?? undefined}
          />
          {/* O CAGED só é publicado com a mediana da UF ao lado: sem referência estadual
              o número não deve ser mostrado nem classificado (regra do Juan, 2026-08-07).
              Aqui isso vira "—" com o motivo por extenso, em vez de um número solto. */}
          <Kpi
            label="Emprego formal (município)"
            valor={cres?.emp == null || cres?.uf_mediana == null ? '—' : pctVar(cres.emp)}
            sub={
              cres?.uf_mediana == null
                ? 'sem mediana da UF para comparar'
                : `mediana da UF: ${pctVar(cres.uf_mediana)}`
            }
          />
        </Bloco>
      )}
    </div>
  )
}

/** Um imóvel da seção "Imóveis disponíveis aqui": ícone do tipo + os 4 números do
 *  ranking da aba, em miniatura. O cartão inteiro é o clique — abre o detalhe. */
function CartaoImovel({ op, onAbrir }: { op: Oportunidade; onAbrir?: () => void }) {
  const tint = corTipo(op.tipo)
  const ocupacao = custoOcup(op)
  return (
    <button
      type="button"
      onClick={onAbrir}
      title="Abrir os detalhes deste imóvel"
      style={{
        width: '100%',
        textAlign: 'left',
        display: 'grid',
        gap: 10,
        padding: 12,
        borderRadius: 'var(--r-lg)',
        cursor: onAbrir ? 'pointer' : 'default',
        background: 'var(--surf-raised)',
        border: '1px solid var(--line-soft)',
      }}
    >
      <span style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0 }}>
        <span
          style={{
            width: 30,
            height: 30,
            borderRadius: 8,
            display: 'grid',
            placeItems: 'center',
            color: tint,
            background: `${tint}1f`,
            flexShrink: 0,
          }}
        >
          <IconeTipo tipo={op.tipo} tamanho={16} />
        </span>
        <span style={{ minWidth: 0 }}>
          <span
            style={{
              display: 'block',
              font: '600 12.5px/1.25 var(--f-ui)',
              color: 'var(--tx-strong)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {op.titulo}
          </span>
          <span
            style={{
              display: 'block',
              font: '400 10.5px/1.3 var(--f-ui)',
              color: 'var(--tx-sub)',
              marginTop: 2,
            }}
          >
            {labelTipo(op.tipo)}
            {op.bairro ? ` · ${op.bairro}` : ''}
          </span>
        </span>
      </span>
      <span style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 14px' }}>
        <MiniNum rotulo="Aluguel" valor={op.aluguel == null ? '—' : brl(op.aluguel)} />
        <MiniNum rotulo="Custo de ocupação" valor={ocupacao > 0 ? brl(ocupacao) : '—'} />
        <MiniNum
          rotulo="Faturamento proj."
          valor={op.fat_proj == null ? '—' : `${brl(op.fat_proj, true)}/mês`}
          verde
        />
        <MiniNum rotulo="Área" valor={op.area == null ? '—' : `${num(op.area)} m²`} />
      </span>
    </button>
  )
}

function MiniNum({ rotulo, valor, verde }: { rotulo: string; valor: string; verde?: boolean }) {
  return (
    <span style={{ minWidth: 0 }}>
      <span style={{ display: 'block', font: '400 9.5px/1.2 var(--f-ui)', color: 'var(--tx-label)' }}>
        {rotulo}
      </span>
      <span
        className="num"
        style={{
          display: 'block',
          font: '600 12px/1.3 var(--f-num)',
          color: verde ? 'var(--pos-text)' : 'var(--tx-strong)',
          marginTop: 2,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {valor}
      </span>
    </span>
  )
}

/** Uma seção de KPIs. Grade de 2 colunas — a mesma da ficha do ponto. */
function Bloco({
  titulo,
  nota,
  children,
}: {
  titulo: string
  nota?: string
  children: ReactNode
}) {
  return (
    <section>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
        <h3 style={{ margin: 0, font: '600 13px/1.2 var(--f-ui)', color: 'var(--tx-max)' }}>
          {titulo}
        </h3>
        {nota && (
          <span style={{ font: '400 11px/1.3 var(--f-ui)', color: 'var(--tx-sub)' }}>{nota}</span>
        )}
      </div>
      <div style={{ marginTop: 10, display: 'grid', gap: 12 }}>{children}</div>
    </section>
  )
}
