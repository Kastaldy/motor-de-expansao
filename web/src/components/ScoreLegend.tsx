import {
  CRESC_ALTA_HEX,
  CRESC_ESTAVEL_HEX,
  CRESC_PARADO_HEX,
  FAIXA_M1_HEX,
  FAIXA_M1_ORDEM,
} from '../lib/colors'
import {
  alunosDaFaixa,
  bandasDaFaixa,
  faixasDoPasso,
  fundoDoSwatch,
  tituloDaLegenda,
} from '../lib/faixas'

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

export default function ScoreLegend({ passoN }: { passoN: number }) {
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
