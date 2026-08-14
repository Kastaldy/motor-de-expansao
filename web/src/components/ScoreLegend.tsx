import {
  CRESC_ALTA_HEX,
  CRESC_ESTAVEL_HEX,
  CRESC_PARADO_HEX,
  FAIXA_M1_HEX,
  FAIXA_M1_ORDEM,
  PRESSAO_FORA_DO_UNIVERSO_FILL,
  PRESSAO_SEM_MEDICAO_FILL,
  type RGBA,
} from '../lib/colors'
import {
  alunosDaFaixa,
  bandasDaFaixa,
  bandasDaFaixaPressao,
  FAIXAS_PRESSAO_MA,
  faixasDoPasso,
  fundoDoSwatch,
  tituloDaLegenda,
} from '../lib/faixas'
import { num } from '../lib/format'
import { rotuloDoRegime } from '../lib/pressao-ma'
import type { PressaoMaMeta } from '../lib/types'

/* Legenda das faixas do mapa (BLK-MAPA-FAIXAS-01).

   Antes era uma barra de gradiente 0->100 sem nome nenhum: dava para ver a cor,
   mas nao para dizer se "62" era bom. Agora cada camada mostra BLOCOS NOMEADOS,
   com vocabulario proprio — o eixo de cada camada e' diferente e o mesmo "alto"
   nao significa a mesma coisa em potencial e em demanda.

   Camadas 1/2/3 usam a rampa de score (`faixasDoPasso`); a 4 lista a faixa de
   oportunidade do M1, que e' categorica e NAO deriva do score que pintava o hex
   antes (ver o comentario em `colors.ts`).

   Continua compacta e `pointerEvents: none` — flutua no canto sem competir com o
   mapa nem capturar clique. */

const CAIXA: React.CSSProperties = {
  background: 'var(--surf-bar)',
  border: '1px solid var(--line-soft)',
  borderRadius: 'var(--r-sm)',
  backdropFilter: 'blur(14px)',
  padding: '7px 9px',
  pointerEvents: 'none',
  width: 'fit-content',
}

const TITULO: React.CSSProperties = {
  font: '500 8.5px/1 var(--f-ui)',
  color: 'var(--tx-label)',
  marginBottom: 5,
  textTransform: 'uppercase',
  letterSpacing: '.06em',
}

const NOME: React.CSSProperties = { font: '400 8.5px/1 var(--f-ui)', color: 'var(--tx-sub)' }
const SUB: React.CSSProperties = { font: '400 7.5px/1 var(--f-num)', color: 'var(--tx-label)' }

/** Um bloco: swatch + nome (+ sublinha opcional com a leitura em alunos).

   `fundo` e' `background` e nao uma cor unica de proposito: nas camadas que vem da
   rampa de score, o swatch mostra as DUAS bandas de 10 pontos que o mapa pinta
   dentro daquela faixa (ver `bandasDaFaixa`). Com uma cor so', metade das cores do
   mapa nao teria bloco correspondente na legenda. */
function Bloco({ fundo, nome, sub }: { fundo: string; nome: string; sub?: string }) {
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <span style={{ width: 14, height: 9, borderRadius: 2, background: fundo, flexShrink: 0 }} />
      <span style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        <span style={NOME}>{nome}</span>
        {sub ? (
          <span className="num" style={SUB}>
            {sub}
          </span>
        ) : null}
      </span>
    </span>
  )
}

/* Camada 4 do funil — a taxa de crescimento da area construida do hexagono
   (BLK-TRAJ-01). Tres estados, nao uma rampa: nao ha nota aqui, ha direcao.
   Sem amarelo de proposito — no meio de uma escala vermelho-verde ele le como
   ALERTA, e "estavel" nao e alerta. Cortes na distribuicao real dos 41.135 hexes
   medidos (p50 = +19,2%, p75 = +30,6%). */
const CLASSES_CRESCIMENTO: [string, string][] = [
  [CRESC_ALTA_HEX, 'em alta (+30%)'],
  [CRESC_ESTAVEL_HEX, 'estável'],
  [CRESC_PARADO_HEX, 'sem obra nova'],
  ['rgba(120,120,140,.45)', 'sem medição'],
]

function LegendaCrescimento() {
  return (
    <div style={CAIXA}>
      <div style={TITULO}>Área construída 2016–2023</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
        {CLASSES_CRESCIMENTO.map(([cor, rotulo]) => (
          <span key={rotulo} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: cor }} />
            <span style={{ font: '400 8.5px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
              {rotulo}
            </span>
          </span>
        ))}
      </div>
    </div>
  )
}

/* Overlay de PRESSAO COMPETITIVA sobre as independentes (BLK-MA-13 / DEC-028).

   Esta legenda carrega TRES obrigacoes que as outras nao tem, e nenhuma e' cosmetica:

   1. Declarar o REGIME de sinais. Reguas de regimes diferentes nao sao comparaveis entre si
      (emenda BLK-MA-04-FU1), e hoje o regime e' um so — mas quem le a tela precisa saber
      qual, senao a comparacao entre dois hexagonos vira um ato de fe.
   2. Declarar a COBERTURA. So ~40% dos hexagonos com academia independente tem pressao > 0;
      onde falta coleta a pressao sai `0`, a leitura mais OTIMISTA da regua (risco 2 da
      DEC-027). Sem o par "N de M", verde le como "medi e nao ha concorrencia".
   3. Separar SEM MEDICAO de SEM PRESSAO. Sao dois blocos proprios, com as cores que o mapa
      de fato usa — pinta-los como a faixa 0-20 apagaria a diferenca entre ausencia de dado e
      ausencia de concorrente.

   O que ela NAO diz: "vulnerabilidade", "alvo" ou "aquisicao". Ver o cabecalho de faixas.ts. */
/** `[r,g,b,a]` do deck.gl -> `rgba()` do CSS. O alpha do deck é 0-255; o do CSS, 0-1. */
function rgba([r, g, b, a]: RGBA): string {
  return `rgba(${r},${g},${b},${(a / 255).toFixed(3)})`
}

function LegendaPressao({ meta }: { meta: PressaoMaMeta }) {
  const cobertura =
    meta.n_hexes != null && meta.n_com_pressao != null
      ? `${num(meta.n_com_pressao)} de ${num(meta.n_hexes)} hexágonos com pressão medida`
      : null
  // Rótulo de exibição do regime DOMINANTE (o que cobre mais hexágonos do recorte). O valor
  // bruto (`s1,s6`) é enum do pipeline — ver `lib/pressao-ma.ts`.
  const regime = meta.regimes?.length ? `medido por ${rotuloDoRegime(meta.regimes[0])}` : null

  return (
    <div style={CAIXA}>
      <div style={TITULO}>Pressão competitiva (raio de 2 km)</div>

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 9, flexWrap: 'wrap' }}>
        {FAIXAS_PRESSAO_MA.map((f) => (
          <Bloco
            key={f.nome}
            fundo={fundoDoSwatch(bandasDaFaixaPressao(f))}
            nome={f.nome}
            sub={`${f.de}–${f.ate}`}
          />
        ))}

        <span
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 9,
            paddingLeft: 7,
            borderLeft: '1px solid var(--line-mid)',
          }}
        >
          {/* Derivadas das MESMAS constantes que o mapa usa. Escrever o `rgba()` à mão aqui
              faria a legenda descrever uma cor que o mapa deixaria de pintar no dia em que
              alguém ajustasse o alpha — o defeito de "duas réguas na mesma tela", só que
              entre dois arquivos do mesmo lado. */}
          <Bloco fundo={rgba(PRESSAO_SEM_MEDICAO_FILL)} nome="sem medição" />
          <Bloco fundo={rgba(PRESSAO_FORA_DO_UNIVERSO_FILL)} nome="sem academia independente" />
        </span>
      </div>

      {(cobertura || regime) && (
        <div
          className="num"
          style={{
            font: '400 7.5px/1.3 var(--f-num)',
            color: 'var(--tx-label)',
            marginTop: 6,
            maxWidth: 420,
          }}
        >
          {[cobertura, regime].filter(Boolean).join(' · ')}
        </div>
      )}
    </div>
  )
}

export default function ScoreLegend({
  passoN,
  pressao,
}: {
  passoN: number
  /** Preenchido = o overlay está ligado e é ELE que a cor está medindo. */
  pressao?: PressaoMaMeta | null
}) {
  // O overlay vence o passo: quando ligado, a cor do mapa não é mais a da camada do funil, e
  // manter a legenda antiga explicaria uma régua que a tela deixou de usar.
  if (pressao) return <LegendaPressao meta={pressao} />
  // O passo 4 tem escala propria e categorica; os demais seguem pela rampa.
  if (passoN === 4) return <LegendaCrescimento />
  const faixas = faixasDoPasso(passoN)

  return (
    <div style={CAIXA}>
      <div style={TITULO}>{tituloDaLegenda(passoN)}</div>

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 9, flexWrap: 'wrap' }}>
        {faixas
          ? faixas.map((f) => (
              <Bloco
                key={f.nome}
                fundo={fundoDoSwatch(bandasDaFaixa(f))}
                nome={f.nome}
                // So a camada de demanda traduz a faixa em alunos — na camada 1 o
                // score censitario nao tem unidade fisica para mostrar.
                sub={passoN === 1 ? undefined : alunosDaFaixa(f)}
              />
            ))
          : // Camada 5: a faixa do M1 e' CATEGORICA e o mapa pinta a cor cheia
            // (`faixaM1ToColor`), entao aqui o swatch e' cor unica mesmo.
            FAIXA_M1_ORDEM.map((nome) => (
              <Bloco key={nome} fundo={FAIXA_M1_HEX[nome]} nome={nome} />
            ))}

        {/* Corte operacional do dashboard (POP_MIN_ACIONAVEL): vale em toda camada. */}
        <span
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            paddingLeft: 7,
            borderLeft: '1px solid var(--line-mid)',
          }}
        >
          <span style={{ width: 14, height: 9, borderRadius: 2, background: 'rgb(150,150,170)' }} />
          <span style={NOME}>&lt; 5k hab</span>
        </span>
      </div>
    </div>
  )
}
