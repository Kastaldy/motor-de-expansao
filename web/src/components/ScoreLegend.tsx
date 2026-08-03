import { FAIXA_M1_HEX, FAIXA_M1_ORDEM } from '../lib/colors'
import { alunosDaFaixa, faixasDoPasso, tituloDaLegenda } from '../lib/faixas'

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

/** Um bloco: swatch de cor + nome (+ sublinha opcional com a leitura em alunos). */
function Bloco({ cor, nome, sub }: { cor: string; nome: string; sub?: string }) {
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <span style={{ width: 9, height: 9, borderRadius: 2, background: cor, flexShrink: 0 }} />
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

export default function ScoreLegend({ passoN }: { passoN: number }) {
  const faixas = faixasDoPasso(passoN)

  return (
    <div style={CAIXA}>
      <div style={TITULO}>{tituloDaLegenda(passoN)}</div>

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 9, flexWrap: 'wrap' }}>
        {faixas
          ? faixas.map((f) => (
              <Bloco
                key={f.nome}
                cor={f.cor}
                nome={f.nome}
                // So a camada de demanda traduz a faixa em alunos — na camada 1 o
                // score censitario nao tem unidade fisica para mostrar.
                sub={passoN === 1 ? undefined : alunosDaFaixa(f)}
              />
            ))
          : FAIXA_M1_ORDEM.map((nome) => (
              <Bloco key={nome} cor={FAIXA_M1_HEX[nome]} nome={nome} />
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
          <span style={{ width: 9, height: 9, borderRadius: 2, background: 'rgb(150,150,170)' }} />
          <span style={NOME}>&lt; 5k hab</span>
        </span>
      </div>
    </div>
  )
}
