import { alunos, brl, pctFrac, rotuloMes } from '../lib/format'
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

function montarSecoes(p: PremissasViabilidade, demandaPremissa: number | null): Secao[] {
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
            'cálculo do IR/CSLL e do aluguel-teto. A folha NÃO sai do faturamento do ' +
            'mês: ela é dimensionada uma vez pelo faturamento MADURO e fica fixa (ver ' +
            'Custos e impostos).',
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
            'taxas de cartão 1,05%. São os ÚNICOS custos que escalam com a receita — ' +
            'a folha NÃO está aqui, ela é custo fixo (ver a linha abaixo). Por serem ' +
            'percentuais, mais alunos não diluem esta linha.',
        },
        {
          kpi: 'Folha (fixa desde o mês 1)',
          como:
            `${brl(p.folha_fixa_mes, false, 2)} por mês, FIXOS desde o mês 1. O valor é ` +
            `dimensionado uma vez — ${pctFrac(p.folha_pct)} do faturamento MADURO ` +
            `(${brl(p.folha_base_faturamento_maduro, true)}, a casa cheia) — e é pago ` +
            'integralmente já no primeiro mês, porque a equipe é contratada ANTES dos ' +
            'alunos chegarem. Não acompanha a rampa: no mês 1, com a casa vazia, a ' +
            'folha é a mesma do mês de regime pleno (só o reajuste anual a move). É ' +
            'por isso que ela conta como custo FIXO, e não como percentual da receita ' +
            'do mês.',
        },
        {
          kpi: 'Outros custos fixos',
          como:
            'Valor absoluto por mês, somando IPTU, água e luz, telefone, limpeza, ' +
            'tecnologia e assessorias. Não varia com o número de alunos. Somado à ' +
            `folha (${brl(p.folha_fixa_mes, true)}) forma o custo fixo que o aluguel ` +
            'ainda vai engrossar.',
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
            'sobre a receita BRUTA. O custo é integral desde o mês 1 — e a folha ' +
            `(${brl(p.folha_fixa_mes, true)}/mês) entra CHEIA já no mês 1, sem ` +
            'acompanhar a rampa — então o EBITDA dos primeiros meses é bem NEGATIVO ' +
            'enquanto a casa não enche. A alavancagem operacional é alta: quase todo ' +
            'o custo é fixo e cada aluno novo cai direto no resultado. Isso é o ' +
            'comportamento correto, não um defeito do gráfico.',
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
            'então dá para comparar direto. A pergunta que ele responde: “montei a casa ' +
            `para ${demandaPremissa != null ? `${alunos(demandaPremissa)} alunos` : 'a demanda assumida'}` +
            `, com a folha de ${brl(p.folha_fixa_mes, true)}/mês já contratada — com ` +
            'quantos eu empato?”. ' +
            'Como a folha é fixa e não encolhe se o volume não vier, este número é ' +
            'mais alto (e mais honesto) que o de um modelo com folha percentual.',
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
            'de franquia, esta última PARCELADA sem juros junto da obra (o nº de ' +
            'parcelas está no bloco de investimento), não mais à vista no M-4. É o ' +
            'único indicador que se chama payback nesta tela.',
        },
        {
          kpi: 'Régua de aprovação',
          como:
            'O veredito exige DUAS coisas ao mesmo tempo: margem EBITDA de pelo menos ' +
            '30% e payback dentro de 36 meses de operação. Passar só no payback deixou ' +
            'de bastar — a régua de margem subiu de 10% para 30% em 2026-07-25.',
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
          kpi: 'Duas óticas, nunca no mesmo número',
          como:
            'Todo indicador de retorno aparece em PAR. O "do negócio" mede o ATIVO: ' +
            'nenhum financiamento no fluxo e o CAPEX inteiro saindo do caixa. O "do ' +
            'sócio" mede a ESTRUTURA DE CAPITAL: a parcela do financiamento sai e só o ' +
            'aporte de obra e franquia entra. Misturar numerador de um com denominador ' +
            'do outro faz o modelo se beneficiar do financiamento duas vezes.',
        },
        {
          kpi: 'Taxa mínima do negócio',
          como:
            `${pctFrac(p.taxa_minima_negocio_aa)} ao ano, nominal. É a única taxa ` +
            'editável do modelo, e o piso vem da própria decisão de financiar: se o ' +
            'banco cobra menos que isso, tomar emprestado cria valor; se cobra mais, ' +
            'destrói. Como o Lucro Presumido não tem escudo fiscal da dívida, esta é ' +
            'também a taxa do ativo — não há média ponderada a fazer.',
        },
        {
          kpi: 'Taxa mínima do sócio',
          como:
            'NÃO é um campo: é derivada da taxa do negócio, do custo da dívida e da ' +
            'alavancagem. O sócio é subordinado ao banco — recebe o resíduo, e o ' +
            'equipamento é garantia do credor — então a taxa dele tem de ser maior que ' +
            'a do credor. Sendo derivada, é impossível alguém digitar uma taxa de sócio ' +
            'abaixo do custo da dívida, que era o furo do modelo anterior.',
        },
        {
          kpi: 'TIR e VPL',
          como:
            'Taxa interna de retorno e valor presente do fluxo de M-4 até o mês ' +
            `${p.horizonte_meses}. Ao contrário do payback, consideram QUANDO cada real ` +
            'entra. Cada um sai duas vezes, na ótica do negócio e na do sócio, cada uma ' +
            'descontada pela SUA taxa. A diferença entre as duas é a alavancagem: sem ' +
            'escudo fiscal no Presumido, ela cria valor apenas por ARBITRAGEM — tomar ' +
            'dinheiro mais barato do que o ativo rende.',
        },
        {
          kpi: 'Cheque total',
          como:
            'O pior ponto do caixa acumulado, e não o aporte contratado. É o dinheiro ' +
            'que o investidor precisa ter DISPONÍVEL, porque a obra e os primeiros ' +
            'meses de operação queimam caixa antes da casa encher. Decide se o negócio ' +
            'é financiável, o que é uma pergunta diferente de ser bom.',
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
  demanda = null,
}: {
  premissas: PremissasViabilidade | null
  dre: DreViabilidade | null
  /** `demanda_premissa` do payload — entra SÓ como rótulo na nota do break-even
   *  (é ela que dimensiona a folha fixa). Nenhuma conta é feita aqui. */
  demanda?: number | null
}) {
  if (!premissas) return null

  const mesSteady = premissas.mes_referencia_steady ?? premissas.maturacao_meses
  const secoes = montarSecoes(premissas, demanda)

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
