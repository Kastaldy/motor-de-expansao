import type { ReactNode } from 'react'

import type { CrescimentoMunicipio } from '../lib/oportunidades'
import { alunos, brl, num, pct } from '../lib/format'
import type { Hex } from '../lib/types'
import { BarraMercado, MedidorScore } from './LeiturasVisuais'
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
}: {
  hex: Hex
  /** Crescimento do MUNICÍPIO do hexágono (`MapaResposta.cres_mun`), quando houver. */
  cres?: CrescimentoMunicipio | null
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
        </div>
      </div>

      <Bloco titulo="Quem mora aqui" nota="Censo 2022 (IBGE), no hexágono">
        <Kpi label="População" valor={num(hex.pop)} />
        <Kpi label="Renda per capita" valor={hex.renda == null ? '—' : brl(hex.renda)} />
        <Kpi label="Renda domiciliar" valor={hex.renda_dom == null ? '—' : brl(hex.renda_dom)} />
      </Bloco>
      <MedidorScore rotulo="Score censitário" valor={hex.censo} />

      <Bloco titulo="Quem já disputa o aluno" nota="unidades mapeadas dentro do hexágono">
        <Kpi label="Concorrentes" valor={num(hex.conc)} />
        <Kpi label="Unidades Ultra" valor={num(hex.ultra)} />
      </Bloco>

      <Bloco titulo="Quanto de mercado sobra" nota="capacidade, não meta de abertura">
        <Kpi label="Mercado potencial (SAM)" valor={hex.sam == null ? '—' : alunos(hex.sam)} />
        <Kpi label="Residual disponível" valor={hex.oferta == null ? '—' : alunos(hex.oferta)} />
      </Bloco>
      {/* A mesma leitura visual da ficha do ponto: a barra responde "sobra muito?" sem
          conta de cabeça, e os dois scores viram medidor porque a escala é conhecida. */}
      <div style={{ display: 'grid', gap: 12 }}>
        <BarraMercado sam={hex.sam} residual={hex.oferta} />
        <MedidorScore
          rotulo="Score de residual"
          valor={hex.res}
          nota="satura em 100 acima de 2.500 alunos — uma unidade cheia"
        />
        <MedidorScore rotulo="Score híbrido" valor={hex.hib} />
      </div>

      {/* O crescimento tem DUAS bases e elas não se misturam: a obra nova é DESTE
          hexágono (satélite); o emprego formal é do MUNICÍPIO inteiro (CAGED). Rotular as
          duas como "crescimento do hexágono" afirmaria sobre a área uma medida que é da
          cidade. Some inteiro quando nenhuma das duas existe — bloco sem dado declara o
          motivo, nunca desaparece em silêncio. */}
      {(hex.cres_hex_classe || hex.cres_hex_taxa != null || cres) && (
        <Bloco titulo="Como a região vem indo" nota={hex.mun ? `obra nova aqui · emprego em ${hex.mun}` : undefined}>
          <Kpi
            label="Obra nova (2016→2023)"
            valor={hex.cres_hex_taxa == null ? '—' : pct(hex.cres_hex_taxa)}
            sub={hex.cres_hex_classe ?? undefined}
          />
          {/* O CAGED só é publicado com a mediana da UF ao lado: sem referência estadual
              o número não deve ser mostrado nem classificado (regra do Juan, 2026-08-07).
              Aqui isso vira "—" com o motivo por extenso, em vez de um número solto. */}
          <Kpi
            label="Emprego formal (município)"
            valor={cres?.emp == null || cres?.uf_mediana == null ? '—' : pct(cres.emp)}
            sub={
              cres?.uf_mediana == null
                ? 'sem mediana da UF para comparar'
                : `mediana da UF: ${pct(cres.uf_mediana)}`
            }
          />
        </Bloco>
      )}
    </div>
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
      <div
        style={{
          marginTop: 9,
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: 9,
        }}
      >
        {children}
      </div>
    </section>
  )
}
