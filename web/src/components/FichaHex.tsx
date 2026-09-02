import type { CrescimentoMunicipio } from '../lib/oportunidades'
import { censoDaBase } from '../lib/rodape-base'
import { alunos, brl, num, pctVar } from '../lib/format'
import { FAIXA_M1_HEX } from '../lib/colors'
import { CAPACIDADE_UNIDADE_ALUNOS, FAIXAS_DEMANDA, FAIXAS_POTENCIAL } from '../lib/faixas'
import { classeAluguelFat, corTipo, custoOcup, labelTipo, pctAluguelFat } from '../lib/imovel'
import { composicaoMercado, faixaDoValor, leituraDeSaturacao } from '../lib/medidor'
import type { Hex, Oportunidade } from '../lib/types'
import IconeTipo from './IconeTipo'
import { CardPainel, LinhaTabela, Ticks, TituloSecao } from './PecasPainel'

/* Cores do design "Paineis do Hexagono" aplicadas por pedido do Felipe (2026-08-21):
   identidade FIXA por score (verde/turquesa/claro — a cor identifica O QUAL score, nao
   o valor dele) e o fundo/borda do card de veredito. Hex direto: tela so-escura, como a
   aba imobiliaria. O veredito por VALOR continua nas notas (nome da faixa publicada). */
const COR_SCORE_CENSO = '#5ee6a8'
const COR_SCORE_RESIDUAL = '#22d3e0'
const COR_SCORE_HIBRIDO = '#eef6f7'
const COR_TICKS_HIBRIDO = '#cfdfe3'
const FUNDO_VEREDITO = 'linear-gradient(120deg, #11282a, #0d1a1e 70%)'
const BORDA_VEREDITO = '#24474a'

/* QUAIS FAIXAS GANHAM O PREFIXO "Prioridade" NO SELO.
   Tabela explicita, e nao uma regra sobre o texto. A lista de faixas e' FECHADA e vive em
   `FAIXA_M1_ORDEM` (`lib/colors.ts`): 'Prioridade máxima', 'Alta', 'Média', 'Baixa',
   'Descartado', 'Inviável'.

   So' as tres do MEIO sao GRAU de prioridade, e so' elas ficam ambiguas sozinhas — era
   "ALTA" solto no topo que se lia como veredito do hexagono inteiro, contra a sobra de
   mercado do rodape. As outras tres nao precisam: 'Prioridade máxima' ja' traz a palavra,
   e 'Descartado'/'Inviável' sao ESTADO, nao grau — "Prioridade Descartado" nao e'
   portugues nem e' o que o M1 diz.

   Perguntar ao texto ("contem 'prioridade'?") acertava por acidente nas duas primeiras e
   errava nas duas ultimas. Pertencer a um conjunto declarado nao depende de sorte, e no
   dia em que o M1 publicar uma faixa nova o silencio aqui e' o comportamento seguro: sai
   sem prefixo, exatamente como a API escreveu. */
const FAIXAS_M1_COM_PREFIXO = new Set(['Alta', 'Média', 'Baixa'])

/**
 * A leitura de UM hexagono, para viver dentro da janela flutuante do mapa.
 *
 * POR QUE EXISTE. O dado do hexagono so' aparecia em dois lugares efemeros: o tooltip,
 * que some quando o mouse sai, e a linha do painel de ranking, que mostra UMA metrica (a
 * da camada ativa). Quem escolhe entre dois bairros precisava trocar de camada quatro
 * vezes para juntar populacao, renda, concorrencia e residual do mesmo hexagono. Aqui as
 * quatro leituras ficam paradas na tela, do mesmo jeito que a ficha do ponto colado.
 *
 * DESENHO: porte do painel esquerdo do design "Paineis do Hexagono" (Claude Design,
 * 2026-08-21), adaptado aos tokens/fontes do piloto — veredito narrativo no topo, tres
 * scores com regua de tracinhos, censo em tabela, mercado por situacao e os imoveis
 * coletados. As pecas de forma vivem em `PecasPainel`.
 *
 * SEM VIABILIDADE, de proposito. Metragem e aluguel sao ENTRADA do operador sobre um
 * IMOVEL concreto (DEC-009, motor property-first); um hexagono e' uma area de ~5 km2, e
 * pedir "o aluguel do hexagono" seria inventar um imovel que nao existe. Quem tem o
 * imovel na mao entra pela analise de ponto, que ja' faz essa conta.
 *
 * NUMEROS: todo valor vem do payload; o que falta aparece como "—" em vez de virar
 * zero — zero e' uma AFIRMACAO ("nao ha' concorrente"), e ausencia nao afirma. As unicas
 * contas locais sao aritmetica de EXIBICAO sobre numeros ja servidos (atendido = SAM −
 * residual via `composicaoMercado`, % da capacidade de 2.500), as mesmas da BarraMercado
 * e da aba imobiliaria. Cor so' de regua publicada (faixas do mapa; clusters 15/20/30 do
 * modelo de viabilidade nos imoveis) — nada colorido por limiar de olho.
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
  const corFaixaM1 = hex.faixa ? (FAIXA_M1_HEX[hex.faixa] ?? null) : null
  const fxCenso = faixaDoValor(hex.censo, FAIXAS_POTENCIAL)
  const fxResidual = faixaDoValor(hex.res, FAIXAS_DEMANDA)
  const mercado = composicaoMercado(hex.sam, hex.oferta)
  const saturacao = leituraDeSaturacao(hex.sam, hex.oferta)
  const ocupacaoAbertura =
    hex.oferta == null
      ? null
      : Math.min(100, Math.round((100 * Math.max(0, hex.oferta)) / CAPACIDADE_UNIDADE_ALUNOS))

  /* AS DUAS LEITURAS QUE PARECIAM SE CONTRADIZER (Juan, 2026-08-26: "em cima fala que é
     alta prioridade e embaixo fala que não tem mercado disponível").

     Elas medem coisas diferentes, e a ficha nunca dizia isso:

       faixa M1 (topo)   percentil de `score_priorizacao` = 0,40·renda + 0,60·população.
                         É PERFIL do lugar. A concorrência NÃO entra na conta.
       sobra (rodapé)    SAM − oferta instalada. É MERCADO ainda não atendido, e é
                         justamente a concorrência que o consome.

     Um bairro rico e denso cheio de academias marca "Alta" em cima e "não sobra mercado"
     embaixo — as duas frases estão certas ao mesmo tempo. Sem dizer de onde cada uma vem,
     a janela parecia com defeito, e uma leitura assim não sustenta decisão de abertura.

     A correção é de LINGUAGEM, não de número: nada aqui recalcula, reordena ou esconde
     nada. A faixa passa a se declarar (a nota sob o selo) e, quando as duas leituras
     apontam para lados opostos, a ficha explica o porquê em vez de deixar o leitor
     resolver sozinho. */
  const FAIXAS_M1_DE_ENTRAR = new Set(['Prioridade máxima', 'Alta'])
  const perfilBomMercadoTomado =
    saturacao?.tom === 'saturado' && hex.faixa != null && FAIXAS_M1_DE_ENTRAR.has(hex.faixa)

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      {/* ---- Veredito: a frase que resume, com a faixa M1 e os numeros-chave ---- */}
      <CardPainel style={{ background: FUNDO_VEREDITO, border: `1px solid ${BORDA_VEREDITO}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 9 }}>
          {/* Texto NEUTRO + swatch na cor da faixa — não a cor como texto: 'Inviável' é
              #2E3040 e como texto sobre o card escuro dava ~1,4:1, ilegível. */}
          {hex.faixa && (
            <span
              className="num"
              /* O selo diz o NOME da régua junto com o valor. Sozinho, "ALTA" era lido
                 como veredito do hexágono inteiro — e logo abaixo, na mesma janela, a
                 sobra de mercado dizia o contrário. */
              title="Faixa de prioridade do M1: percentil de renda e população. Não considera a concorrência instalada — isso é o bloco 'Quanto de mercado sobra'."
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '4px 9px',
                borderRadius: 999,
                background: corFaixaM1 ? `${corFaixaM1}26` : 'var(--surf-pending)',
                border: '1px solid var(--line-soft)',
                color: 'var(--tx-strong)',
                font: '500 9px/1 var(--f-num)',
                letterSpacing: '.12em',
                textTransform: 'uppercase',
                whiteSpace: 'nowrap',
              }}
            >
              <span
                aria-hidden
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: 2,
                  background: corFaixaM1 ?? 'var(--tx-sub)',
                  flexShrink: 0,
                }}
              />
              {/* "PRIORIDADE ALTA", não "ALTA" — só nas faixas que são grau de prioridade
                  (ver `FAIXAS_M1_COM_PREFIXO`). As demais saem como a API as escreveu. */}
              {FAIXAS_M1_COM_PREFIXO.has(hex.faixa) ? `Prioridade ${hex.faixa}` : hex.faixa}
            </span>
          )}
          {hex.hib != null && (
            <span
              className="num"
              style={{ font: '400 9.5px/1 var(--f-num)', letterSpacing: '.1em', color: 'var(--tx-sub)' }}
            >
              HÍBRIDO {num(hex.hib, 1)}
            </span>
          )}
        </div>

        {/* De onde vem a faixa. Uma linha, sempre visível — o `title` do selo não serve
            sozinho: não aparece no toque, e era exatamente esta informação que faltava
            para as duas leituras da janela pararem de parecer contraditórias. */}
        {hex.faixa && (
          <p
            style={{
              margin: '0 0 9px',
              font: '400 10.5px/1.45 var(--f-ui)',
              color: 'var(--tx-sub)',
            }}
          >
            Faixa do M1 — perfil de renda e população do hexágono. A concorrência instalada
            entra em “Quanto de mercado sobra”, abaixo.
          </p>
        )}
        <p style={{ margin: 0, font: '400 14.5px/1.5 var(--f-ui)', color: 'var(--tx-strong)' }}>
          <FraseVeredito hex={hex} />
        </p>
        <div style={{ display: 'flex', gap: 8, marginTop: 13, flexWrap: 'wrap' }}>
          {hex.censo != null && (
            <ChipNumero valor={num(hex.censo, 1)} rotulo="censo" tom={fxCenso?.cor} />
          )}
          {hex.oferta != null && (
            <ChipNumero valor={alunos(hex.oferta)} rotulo="alunos livres" tom="var(--ac-text)" />
          )}
          {/* "no hexágono" por extenso: os chips contam PONTOS dentro da célula, e sem a
              base declarada leem-se como o modelo de raio de 2 km — a confusão
              RAIO×HEXÁGONO que este arquivo já corrigiu uma vez (2026-08-13). O ZERO
              aparece: contagem 0 é afirmação ("não há unidade aqui"), só null some. */}
          {hex.conc_hex != null && (
            <ChipNumero valor={num(hex.conc_hex)} rotulo="concorrentes no hexágono" />
          )}
          {hex.ultra_hex != null && (
            <ChipNumero valor={num(hex.ultra_hex)} rotulo="Ultra no hexágono" />
          )}
        </div>

        {/* Identidade e ações — o id inteiro (copiável), a saída para a rua e a
            comparação. O rótulo do Maps diz "o centro" de propósito: o hexágono tem
            ~5 km² e isto abre o CENTRO dele, não um endereço, que ele não tem. */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            flexWrap: 'wrap',
            marginTop: 13,
            paddingTop: 11,
            borderTop: '1px solid var(--line-soft)',
          }}
        >
          <span
            className="num"
            style={{
              font: '500 10px/1 var(--f-num)',
              color: 'var(--tx-sub)',
              padding: '5px 8px',
              borderRadius: 6,
              background: 'var(--surf-raised)',
              border: '1px solid var(--line-soft)',
            }}
          >
            {hex.id}
          </span>
          <a
            href={`https://www.google.com/maps/search/?api=1&query=${hex.lat},${hex.lng}`}
            target="_blank"
            rel="noreferrer"
            style={{ font: '600 11px/1 var(--f-ui)', color: 'var(--ac-text)', textDecoration: 'underline' }}
          >
            Abrir o centro no Google Maps ↗
          </a>
          {/* COMPARAR A PARTIR DAQUI (pedido do Juan, 2026-08-13): põe este hexágono na
              lista e liga o modo; o próximo clique no mapa entra como o segundo. */}
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
                cursor: 'pointer',
              }}
            >
              + Comparar com outro
            </button>
          )}
        </div>
      </CardPainel>

      {/* ---- Os três scores, com a régua de tracinhos do design ----
          As CORES são as do design (identidade fixa por score — pedido do Felipe); o
          veredito por VALOR fica na nota, pelo nome da faixa publicada da camada. */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 9 }}>
        <CardScore
          rotulo="CENSO"
          valor={hex.censo}
          cor={COR_SCORE_CENSO}
          nota={fxCenso ? `${fxCenso.nome} na régua do potencial` : 'sem leitura do censo'}
        />
        <CardScore
          rotulo="RESIDUAL"
          valor={hex.res}
          cor={COR_SCORE_RESIDUAL}
          nota={fxResidual ? `${fxResidual.nome} — satura em ${num(CAPACIDADE_UNIDADE_ALUNOS)} alunos` : 'sem leitura de residual'}
        />
        <CardScore
          rotulo="HÍBRIDO"
          valor={hex.hib}
          cor={COR_SCORE_HIBRIDO}
          corTicks={COR_TICKS_HIBRIDO}
          nota="média ponderada de censo e residual"
        />
      </div>

      {/* ---- Quem mora aqui ---- */}
      <section>
        <TituloSecao titulo="Quem mora aqui" nota={censoDaBase() ?? undefined} />
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            borderRadius: 12,
            overflow: 'hidden',
            border: '1px solid var(--line-soft)',
          }}
        >
          <CelulaCenso valor={hex.pop == null ? '—' : num(hex.pop)} rotulo="População" />
          <CelulaCenso valor={hex.renda == null ? '—' : brl(hex.renda)} rotulo="Renda per capita" />
          <CelulaCenso
            valor={hex.renda_dom == null ? '—' : brl(hex.renda_dom)}
            rotulo="Renda domiciliar"
            ultima
          />
        </div>
      </section>

      {/* ---- Quanto de mercado sobra (compacto — pedido do Felipe, 2026-08-21) ---- */}
      <CardPainel style={{ padding: '13px 14px' }}>
        <TituloSecao titulo="Quanto de mercado sobra" nota="capacidade, não meta" gap={10} />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 11 }}>
          <BigAlunos
            valor={hex.oferta}
            cor="var(--ac-text)"
            rotulo={
              mercado
                ? `Não atendidos · ${Math.round(mercado.fracaoDisponivel * 100)}% do mercado`
                : 'Não atendidos'
            }
          />
          {/* "pela oferta instalada (raio de 2 km)" SEMPRE: o número vem do modelo de
              raio ponderado por distância (SAM − residual, inclui a Ultra própria) —
              creditá-lo ao `conc_hex` fundia as duas bases que o repo manda separar
              ("RAIO, NÃO HEXÁGONO"); a contagem do hexágono vive nos chips acima. */}
          <BigAlunos
            valor={mercado ? mercado.atendido : null}
            cor="var(--tx-soft)"
            rotulo="Já atendidos pela oferta instalada (raio de 2 km)"
          />
        </div>
        <div
          style={{
            borderRadius: 12,
            background: 'var(--surf-raised)',
            border: '1px solid var(--line-soft)',
            padding: '2px 0',
          }}
        >
          <LinhaTabela rotulo="Mercado total (SAM)" valor={hex.sam == null ? '—' : `${alunos(hex.sam)} alunos`} />
          <LinhaTabela rotulo="Capacidade de uma unidade" valor={`${num(CAPACIDADE_UNIDADE_ALUNOS)} alunos`} />
          {/* "Sobra vs capacidade", e NÃO "ocupação na abertura": o dado só diz quantos
              alunos não são atendidos — prometer ocupação no dia 1 assumiria captura de
              100% do residual, premissa que nenhuma régua publicada sustenta (a rampa de
              abertura é do simulador de viabilidade). */}
          <LinhaTabela
            rotulo="Sobra vs capacidade de uma unidade"
            valor={ocupacaoAbertura == null ? '—' : `${ocupacaoAbertura}%`}
            tom={fxResidual?.cor}
          />
        </div>
        {/* DÁ PARA ENTRAR? A frase vem de `leituraDeSaturacao`, regra de bolso publicada
            (o corte é a capacidade de UMA unidade). NÃO é veredito de viabilidade — isso
            é do simulador, sobre um imóvel concreto. */}
        {saturacao && (
          <p
            style={{
              margin: '10px 0 0',
              font: '400 11px/1.5 var(--f-ui)',
              color: saturacao.tom === 'saturado' ? 'var(--tx-soft)' : 'var(--tx-narrative)',
            }}
          >
            {saturacao.frase}
          </p>
        )}
        {/* A RECONCILIAÇÃO, só quando as duas leituras apontam para lados opostos. Não é
            um terceiro veredito: é a frase que diz por que as outras duas convivem. */}
        {perfilBomMercadoTomado && (
          <p
            style={{
              margin: '8px 0 0',
              padding: '8px 10px',
              borderRadius: 9,
              background: 'var(--surf-raised)',
              border: '1px solid var(--line-soft)',
              font: '400 11px/1.5 var(--f-ui)',
              color: 'var(--tx-sub)',
            }}
          >
            Não contradiz a faixa <b>{hex.faixa?.toLowerCase()}</b> do topo: ela mede o{' '}
            <b>perfil</b> do lugar (renda e população), e esta leitura mede o{' '}
            <b>mercado que sobra</b> depois da oferta já instalada. Aqui o perfil é dos
            bons e o mercado já está tomado — o ponto é bom, a praça é disputada.
          </p>
        )}
      </CardPainel>

      {/* ---- Como a região vem indo (obra nova é DESTE hex; emprego é do MUNICÍPIO —
              as duas bases não se misturam, e o bloco some inteiro sem nenhuma) ---- */}
      {(hex.cres_hex_classe || hex.cres_hex_taxa != null || cres) && (
        <CardPainel>
          <TituloSecao
            titulo="Como a região vem indo"
            nota={hex.mun ? `obra aqui · emprego em ${hex.mun}` : undefined}
          />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 14px' }}>
            {/* A guarda `== null ? '—'` TEM de ficar: `pctVar(null)` devolve "Não
                disponível" por extenso e estouraria o número mono. */}
            <MiniLeitura
              valor={hex.cres_hex_taxa == null ? '—' : pctVar(hex.cres_hex_taxa)}
              rotulo="Obra nova (2016→2023)"
              nota={hex.cres_hex_classe ?? undefined}
            />
            {/* O CAGED só aparece com a mediana da UF ao lado (regra do Juan, 2026-08-07). */}
            <MiniLeitura
              valor={cres?.emp == null || cres?.uf_mediana == null ? '—' : pctVar(cres.emp)}
              rotulo="Emprego formal (município)"
              nota={
                cres?.uf_mediana == null
                  ? 'sem mediana da UF para comparar'
                  : `mediana da UF: ${pctVar(cres.uf_mediana)}`
              }
            />
          </div>
        </CardPainel>
      )}

      {/* ---- Imóveis disponíveis aqui ---- */}
      {imoveis != null && imoveis.length > 0 && (
        <section>
          <TituloSecao
            titulo="Imóveis disponíveis aqui"
            nota={imoveis.length === 1 ? '1 coletado' : `${num(imoveis.length)} coletados`}
          />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {imoveis.map((o) => (
              <CartaoImovel key={o.id} op={o} onAbrir={onVerImovel ? () => onVerImovel(o) : undefined} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

/** A frase do veredito, montada só com o que o payload afirma. */
function FraseVeredito({ hex }: { hex: Hex }) {
  if (hex.sam == null && hex.oferta == null) {
    return <>Sem leitura de mercado para este hexágono.</>
  }
  return (
    <>
      {hex.sam != null && (
        <>
          Mercado de <b className="num">{alunos(hex.sam)}</b> alunos
        </>
      )}
      {hex.oferta != null && (
        <>
          {hex.sam != null ? ', com ' : 'Sobram '}
          <b className="num" style={{ color: 'var(--ac-text)' }}>
            {alunos(hex.oferta)}
          </b>{' '}
          ainda não atendidos
        </>
      )}
      {hex.conc_hex != null && hex.conc_hex > 0 && (
        <>
          {' '}
          e <b className="num">{num(hex.conc_hex)}</b> concorrente
          {hex.conc_hex === 1 ? '' : 's'} instalado{hex.conc_hex === 1 ? '' : 's'}
        </>
      )}
      .
    </>
  )
}

/** Chip de número-chave do veredito (valor mono + rótulo). */
function ChipNumero({ valor, rotulo, tom }: { valor: string; rotulo: string; tom?: string }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'baseline',
        gap: 6,
        padding: '7px 11px',
        borderRadius: 9,
        background: 'var(--surf-raised)',
        border: '1px solid var(--line-soft)',
      }}
    >
      <span className="num" style={{ font: '500 13px/1 var(--f-num)', color: tom ?? 'var(--tx-max)' }}>
        {valor}
      </span>
      <span style={{ font: '400 10.5px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>{rotulo}</span>
    </span>
  )
}

/** Card de score com a régua de tracinhos. A cor vem da faixa publicada da camada. */
function CardScore({
  rotulo,
  valor,
  cor,
  corTicks,
  nota,
}: {
  rotulo: string
  valor: number | null
  cor: string
  corTicks?: string
  nota: string
}) {
  return (
    <div
      style={{
        padding: '12px 12px 11px',
        borderRadius: 13,
        background: 'var(--surf-raised)',
        border: '1px solid var(--line-soft)',
      }}
    >
      <div
        className="num"
        style={{ font: '400 9px/1 var(--f-num)', letterSpacing: '.1em', color: 'var(--tx-sub)', marginBottom: 9 }}
      >
        {rotulo}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 3 }}>
        <span
          className="num"
          style={{ font: '500 22px/1 var(--f-num)', color: valor == null ? 'var(--tx-sub)' : cor }}
        >
          {valor == null ? '—' : num(valor, 1)}
        </span>
        <span className="num" style={{ font: '400 10px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
          /100
        </span>
      </div>
      <div style={{ margin: '10px 0 8px' }}>
        <Ticks score={valor} cor={corTicks ?? cor} />
      </div>
      <div style={{ font: '400 10.5px/1.35 var(--f-ui)', color: 'var(--tx-sub)' }}>{nota}</div>
    </div>
  )
}

function CelulaCenso({ valor, rotulo, ultima }: { valor: string; rotulo: string; ultima?: boolean }) {
  return (
    <div
      style={{
        padding: '13px 14px',
        background: 'var(--surf-raised)',
        borderRight: ultima ? undefined : '1px solid var(--line-soft)',
      }}
    >
      <div className="num" style={{ font: '500 16px/1 var(--f-num)', color: 'var(--tx-max)' }}>{valor}</div>
      <div style={{ font: '400 10.5px/1.25 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 5 }}>
        {rotulo}
      </div>
    </div>
  )
}

/** Número de alunos com a situação por extenso embaixo (19px: o card é apoio, não herói). */
function BigAlunos({ valor, cor, rotulo }: { valor: number | null; cor: string; rotulo: string }) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 5 }}>
        <span
          className="num"
          style={{ font: '500 19px/1 var(--f-num)', color: valor == null ? 'var(--tx-sub)' : cor }}
        >
          {valor == null ? '—' : alunos(valor)}
        </span>
        <span style={{ font: '400 10.5px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>alunos</span>
      </div>
      <div style={{ font: '400 10.5px/1.35 var(--f-ui)', color: 'var(--tx-narrative)', marginTop: 4 }}>
        {rotulo}
      </div>
    </div>
  )
}

function MiniLeitura({ valor, rotulo, nota }: { valor: string; rotulo: string; nota?: string }) {
  return (
    <div>
      <div className="num" style={{ font: '500 15px/1 var(--f-num)', color: 'var(--tx-max)' }}>{valor}</div>
      <div style={{ font: '400 10.5px/1.3 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 4 }}>
        {rotulo}
      </div>
      {nota && (
        <div style={{ font: '400 10px/1.3 var(--f-ui)', color: 'var(--tx-label)', marginTop: 2 }}>
          {nota}
        </div>
      )}
    </div>
  )
}

/** Um imóvel da seção, com presença (pedido do Felipe, 2026-08-21): ícone maior, tipo e
 *  bairro no subtítulo, os 4 números do ranking da aba em grade e a razão ALUGUEL/FAT
 *  à direita — colorida pela régua 15/20/30 do modelo de viabilidade (a única publicada
 *  que compara custo com retorno). O cartão inteiro é o clique. */
function CartaoImovel({ op, onAbrir }: { op: Oportunidade; onAbrir?: () => void }) {
  const tint = corTipo(op.tipo)
  const pct = pctAluguelFat(op)
  const cls = classeAluguelFat(pct)
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
        gridTemplateColumns: '44px 1fr auto',
        gap: 13,
        alignItems: 'start',
        padding: 14,
        borderRadius: 14,
        background: 'var(--surf-raised)',
        border: '1px solid var(--line-soft)',
        cursor: onAbrir ? 'pointer' : 'default',
      }}
    >
      <span
        style={{
          width: 44,
          height: 44,
          borderRadius: 12,
          background: `${tint}1f`,
          display: 'grid',
          placeItems: 'center',
          color: tint,
        }}
      >
        <IconeTipo tipo={op.tipo} tamanho={22} />
      </span>
      <span style={{ minWidth: 0 }}>
        <span
          style={{
            display: 'block',
            font: '600 13.5px/1.3 var(--f-ui)',
            color: 'var(--tx-max)',
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
        <span
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '7px 16px',
            marginTop: 9,
          }}
        >
          <MiniNum rotulo="Aluguel" valor={op.aluguel == null ? '—' : brl(op.aluguel)} />
          <MiniNum rotulo="Custo de ocupação" valor={ocupacao > 0 ? brl(ocupacao) : '—'} />
          <MiniNum
            rotulo="Faturamento proj."
            valor={op.fat_proj == null ? '—' : `${brl(op.fat_proj, true)}/mês`}
            verde
          />
          <MiniNum rotulo="Área" valor={op.area == null ? '—' : `${num(op.area)} m²`} />
        </span>
      </span>
      <span style={{ textAlign: 'right', paddingTop: 2 }}>
        <span
          className="num"
          style={{ display: 'block', font: '500 14px/1 var(--f-num)', color: cls?.tom ?? 'var(--tx-sub)' }}
        >
          {pct == null ? '—' : `${num(pct, 1)}%`}
        </span>
        <span
          className="num"
          style={{
            display: 'block',
            font: '400 8.5px/1 var(--f-num)',
            letterSpacing: '.08em',
            color: 'var(--tx-sub)',
            marginTop: 3,
          }}
        >
          ALUGUEL/FAT
        </span>
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
          font: '600 12.5px/1.3 var(--f-num)',
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
