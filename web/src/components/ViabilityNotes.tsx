import { brl, pctFrac, rotuloMes } from '../lib/format'
import type { DreViabilidade, PremissasViabilidade } from '../lib/types'
import { Glass } from './primitives'

/* ---------------------------------------------------------------------------
   Notas metodologicas — o "manual" da tela de Viabilidade.

   Existe porque o rotulo de um card nao cabe a explicacao: "custos variaveis" sao
   quatro linhas somadas, a "despesa financeira" aparece DEPOIS do IR por causa do
   regime tributario, e ha DOIS indicadores que soam como payback. Sem isto o
   operador tem de saber de cor — foi exatamente a duvida que Felipe levantou.

   Percentuais e prazos saem do PAYLOAD, nao escritos a mao: se a premissa mudar
   (folha, reajuste, taxa de desconto, carencia), a nota acompanha em vez de mentir.
   Nenhum numero e calculado aqui — pctFrac/brl sao RENDER (FIN-VIAB-01).
   --------------------------------------------------------------------------- */

interface Nota {
  kpi: string
  como: string
}

interface Secao {
  titulo: string
  notas: Nota[]
}

function montarSecoes(p: PremissasViabilidade): Secao[] {
  const mixAgr = 1 - (p.share_balcao ?? 0)
  const fatorAgr = p.ticket_agregador_fator ?? null
  const mesSteady = p.mes_referencia_steady ?? p.maturacao_meses

  return [
    {
      titulo: 'Receita',
      notas: [
        {
          kpi: 'Ticket cheio do plano',
          como:
            `Mensalidade de balcão que você digita (${brl(p.ticket_cheio, false, 2)}). ` +
            'É o preço de tabela, NÃO o que entra no caixa por aluno.',
        },
        {
          kpi: 'Ticket médio (blended)',
          como:
            `${brl(p.ticket_blended, false, 2)} por aluno total. Mistura o balcão ` +
            `(${pctFrac(p.share_balcao)} da base, paga o cheio) com os agregadores ` +
            `(${pctFrac(mixAgr)} — Gympass, TotalPass e similares, que pagam ` +
            `${brl(p.ticket_agregador, false, 2)}` +
            `${fatorAgr ? `, ou ${pctFrac(fatorAgr)} do cheio` : ''}), e já desconta ` +
            'churn e inadimplência. É este número que sustenta o break-even.',
        },
        {
          kpi: 'Anuidade',
          como:
            p.anuidade_valor > 0
              ? `${brl(p.anuidade_valor, false, 2)} uma vez POR ANO por aluno de ` +
                `${p.anuidade_apenas_balcao ? 'balcão' : 'qualquer canal'} que completa ` +
                `${p.anuidade_mes_inicio} meses de casa. Só ${pctFrac(p.anuidade_elegivel_pct)} ` +
                'chegam lá, e essa fração é derivada do próprio churn — não é um número ' +
                'à parte. Reconhecida pro-rata mensal (dividida por 12) porque os ' +
                'aniversários dos alunos se espalham pelo ano; lançá-la de uma vez ' +
                `criaria um degrau falso no caixa do mês ${p.anuidade_mes_inicio}.`
              : 'Desligada neste cenário.',
        },
        {
          kpi: 'Faturamento',
          como:
            'Receita BRUTA do mês: mensalidades + anuidade + personal. É a base de ' +
            'cálculo da folha, do IR/CSLL e do aluguel-teto.',
        },
      ],
    },
    {
      titulo: 'Custos e impostos',
      notas: [
        {
          kpi: 'Deduções',
          como:
            `${pctFrac(p.deducoes_pct, 2)} da receita bruta: cancelamentos, chargeback e ` +
            'descontos comerciais.',
        },
        {
          kpi: 'Impostos sobre a receita',
          como:
            `${pctFrac(p.impostos_receita_pct, 2)} da receita LÍQUIDA — PIS 0,65% + ` +
            'COFINS 3% + ISS 3%. Ficam acima do EBITDA porque são custo de operar, ' +
            'diferente do IR/CSLL.',
        },
        {
          kpi: 'Custos variáveis',
          como:
            `${pctFrac(p.custo_variavel_pct, 2)} da receita líquida, somando QUATRO ` +
            'linhas: royalties 8% + fundo de marketing (FPP) 2% + manutenção 2% + ' +
            'taxas de cartão 1,05%. Escalam com a receita, então mais alunos não ' +
            'diluem esta linha.',
        },
        {
          kpi: 'Folha',
          como:
            `${pctFrac(p.folha_pct)} do faturamento BRUTO. Acompanha o volume: mais ` +
            'alunos assumidos, mais folha, automático. Substituiu um valor fixo que ' +
            'subestimava unidades de alto faturamento.',
        },
        {
          kpi: 'Outros custos fixos',
          como:
            'Valor absoluto por mês, somando IPTU, água e luz, telefone, limpeza, ' +
            'tecnologia, assessorias e outros. Não varia com o número de alunos.',
        },
        {
          kpi: 'Aluguel',
          como:
            'Input seu, e já contempla IPTU, condomínio e encargos — não somar nada em ' +
            `cima. Reajusta ${pctFrac(p.reajuste_aluguel_aa)} ao ano a partir do mês 13.` +
            (p.carencia_aluguel_meses > 0
              ? ` Carência de ${p.carencia_aluguel_meses} meses contada da ENTREGA da ` +
                'unidade (M-4), não da abertura: a cobrança começa no ' +
                `${rotuloMes(p.mes_inicio_aluguel)}.`
              : ' Sem carência neste cenário.'),
        },
      ],
    },
    {
      titulo: 'Resultado',
      notas: [
        {
          kpi: 'EBITDA e margem',
          como:
            'Faturamento menos deduções, impostos e custos operacionais. A margem é ' +
            'sobre a receita BRUTA. O custo é integral desde o mês 1, então o EBITDA ' +
            'dos primeiros meses é NEGATIVO enquanto a rampa não enche a casa — isso ' +
            'é o comportamento correto, não um defeito do gráfico.',
        },
        {
          kpi: 'IR/CSLL',
          como:
            'Lucro Presumido, serviços: a base é 32% da receita BRUTA e, sobre ela, ' +
            'IRPJ 15% + adicional de 10% no que exceder R$ 20 mil/mês + CSLL 9%. ' +
            'Como a base é a receita, o imposto é devido mesmo num mês de EBITDA ' +
            'negativo, e nenhuma despesa reduz a conta.',
        },
        {
          kpi: 'Despesa financeira — por que vem DEPOIS do IR',
          como:
            'São os juros da parcela do financiamento. No Lucro Presumido o juro NÃO é ' +
            'dedutível: o imposto olha apenas a receita. Colocá-la antes do IR ' +
            'insinuaria um benefício fiscal do financiamento que não existe neste ' +
            'regime, e inflaria o resultado.',
        },
      ],
    },
    {
      titulo: 'Réguas de decisão',
      notas: [
        {
          kpi: 'Break-even operacional',
          como:
            'Alunos TOTAIS (balcão + agregadores, na mesma proporção do mix) para o ' +
            'EBITDA fechar em zero. Está na mesma unidade da demanda que você digita, ' +
            'então dá para comparar direto.',
        },
        {
          kpi: 'Break-even de caixa',
          como:
            'O mesmo, cobrindo também a parcela do financiamento. Entre os dois ' +
            'break-evens a operação dá lucro no papel e ainda queima caixa.',
        },
        {
          kpi: '1º mês com caixa operacional positivo',
          como:
            'O primeiro mês que fecha no azul e permanece assim. NÃO é payback: aqui o ' +
            'investimento ainda não voltou.',
        },
        {
          kpi: 'Payback',
          como:
            'Mês em que o caixa ACUMULADO cruza o zero, contado desde o primeiro ' +
            'desembolso da obra (M-4). Devolve o capital investido — CAPEX mais a taxa ' +
            'de franquia. É o único indicador que se chama payback nesta tela.',
        },
        {
          kpi: 'Aluguel-teto',
          como:
            'Percentual do faturamento bruto, em três faixas: ideal 15%, teto 20% e ' +
            'exceção 30%. O card grande mostra o TETO — o limite que a operação ' +
            'defende. É calculado sobre a demanda que você assumiu, então é circular ' +
            'por natureza: premissa mais otimista, teto mais alto.',
        },
      ],
    },
    {
      titulo: 'Retorno',
      notas: [
        {
          kpi: 'Retorno anual (desalavancado)',
          como:
            'Resultado anual ANTES da parcela do financiamento, dividido pelo ' +
            'investimento total (CAPEX + franquia). É a ótica de comitê: mede o ativo, ' +
            'não a estrutura de capital. A visão equity (depois da parcela, sobre o que ' +
            'foi aportado) aparece separada — as duas nunca se misturam no mesmo número.',
        },
        {
          kpi: 'TIR',
          como:
            'Taxa interna de retorno do fluxo de caixa de M-4 até o mês ' +
            `${p.horizonte_meses}. Ao contrário do payback, considera QUANDO cada real ` +
            'entra.',
        },
        {
          kpi: 'VPL',
          como:
            'Valor presente líquido do mesmo fluxo, descontado a ' +
            `${pctFrac(p.taxa_desconto_aa)} ao ano. Positivo significa criar valor ` +
            'acima do custo de capital. A taxa é premissa editável e ainda pende de ' +
            'validação.',
        },
      ],
    },
    {
      titulo: 'Premissas de tempo e de demanda',
      notas: [
        {
          kpi: `Steady-state (mês ${mesSteady})`,
          como:
            'Todo número "por mês" desta tela se refere a este mês — o primeiro em ' +
            'REGIME PLENO, com a casa madura e a anuidade já em cobrança. Antes dele o ' +
            'resultado é menor, e é por isso que a DRE não usa o mês 1 nem o mês em ' +
            'que a rampa termina.',
        },
        {
          kpi: 'Rampa de maturação',
          como:
            `${p.maturacao_meses} meses para a demanda sair do piso inicial e chegar ao ` +
            'valor assumido. Afeta o caixa e o payback, não a margem de steady-state.',
        },
        {
          kpi: 'Reajuste anual',
          como:
            `Ticket ${pctFrac(p.reajuste_ticket_aa)}, aluguel ` +
            `${pctFrac(p.reajuste_aluguel_aa)} e custos ${pctFrac(p.reajuste_custos_aa)} ` +
            'ao ano, por degrau a partir do mês 13. A parcela do financiamento é ' +
            'nominal e NÃO reajusta.',
        },
        {
          kpi: 'Faixa de alunos (p10 – p50 – p90)',
          como:
            'Sai da curva tamanho→densidade dos comparáveis Ultra: depende SÓ da ' +
            'metragem, nunca da localização. O p50 semeia a demanda; p10 e p90 são o ' +
            'cenário pessimista e o otimista da MESMA metragem.',
        },
        {
          kpi: 'Demanda assumida',
          como:
            'É PREMISSA sua, não previsão. A ferramenta testa o número que você assume; ' +
            'ela não estima quantos alunos o ponto teria. Guardrail permanente do modelo.',
        },
        {
          kpi: `Horizonte de ${p.horizonte_meses} meses`,
          como:
            'Prazo do contrato de franquia. O corte no fim não conta valor residual do ' +
            'equipamento nem CAPEX de renovação — ambos entram como zero por padrão.',
        },
      ],
    },
  ]
}

export function NotasMetodologicas({
  premissas,
  dre,
}: {
  premissas: PremissasViabilidade | null
  dre: DreViabilidade | null
}) {
  if (!premissas) return null

  const mesSteady = premissas.mes_referencia_steady ?? premissas.maturacao_meses
  const secoes = montarSecoes(premissas)

  return (
    <Glass style={{ padding: '19px 21px', minWidth: 0 }}>
      <span
        style={{ display: 'block', font: '600 14px/1 var(--f-ui)', color: 'var(--tx-strong)' }}
      >
        Notas metodológicas
      </span>
      <span
        style={{
          display: 'block',
          font: '400 11px/1.55 var(--f-ui)',
          color: 'var(--tx-muted)',
          marginTop: 6,
        }}
      >
        O que cada indicador desta tela significa e como é calculado. Os percentuais e
        prazos abaixo saem das premissas deste cenário — mudou a premissa, muda a nota.
        {dre?.faturamento != null
          ? ` Cenário lido: faturamento de ${brl(dre.faturamento, true)} no mês ${mesSteady}.`
          : ''}
      </span>

      {secoes.map((s) => (
        <div key={s.titulo} style={{ marginTop: 17 }}>
          <span
            style={{
              display: 'block',
              font: '600 10.5px/1 var(--f-ui)',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'var(--ac)',
              paddingBottom: 7,
              borderBottom: '1px solid var(--line)',
            }}
          >
            {s.titulo}
          </span>
          {s.notas.map((n) => (
            <div
              key={n.kpi}
              style={{
                display: 'grid',
                gridTemplateColumns: 'minmax(140px, 215px) 1fr',
                gap: 14,
                padding: '9px 0',
                borderBottom: '1px solid var(--line-soft)',
                alignItems: 'baseline',
              }}
            >
              <span style={{ font: '600 11.5px/1.45 var(--f-ui)', color: 'var(--tx-strong)' }}>
                {n.kpi}
              </span>
              <span style={{ font: '400 11.5px/1.6 var(--f-ui)', color: 'var(--tx-sub)' }}>
                {n.como}
              </span>
            </div>
          ))}
        </div>
      ))}
    </Glass>
  )
}
