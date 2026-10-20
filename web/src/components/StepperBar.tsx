import { camadaCor } from '../lib/colors'
import { num } from '../lib/format'
import type { Passo } from '../lib/types'
import { Spinner } from './primitives'

/* ---------------------------------------------------------------------------
   Os passos da recomendacao, na barra inferior do mapa.

   O ultimo passo troca o CTA de "próxima camada" por "Gerar Relatório
   Municipal" — a sintese das camadas vira o PDF (pedido do Felipe).

   O RELATÓRIO EM TODAS AS CAMADAS (pedido do Vinicius, 2026-10-20): o PDF é do
   MUNICÍPIO, não da camada em que o operador está, e obrigar a percorrer o funil
   até o fim para baixá-lo escondia o botão de quem já sabe o que quer. Nas camadas
   antes da última ele entra ao lado do "Próxima camada", sempre na PONTA DIREITA e
   em ciano; na última, o "Próxima camada" sai e só ele fica. Na visão de UF não há
   município, então não há relatório. A regra mora em `botoesDoStepper`, testada.

   Voltar SEMPRE foi possivel (clicar num passo ja percorrido), mas nada dizia
   isso: o CTA era de mao unica e a palavra "voltar" nao aparecia. Dai o botao
   secundario ao lado do CTA e o aria-label/title explicito em cada passo.

   COR: cada passo veste a SUA camada (--l1..--l4, tokens.css). Antes os 4 eram o
   mesmo turquesa, entao a barra nao dava identidade nenhuma a' camada e ainda
   repetia, na mesma cor, o par numero+unidade que o painel ja mostrava — o mesmo
   valor em turquesa em tres lugares. O CTA a' direita segue turquesa: ele e' ACAO,
   nao camada. O numero dentro da bolinha permanece (a cor nao pode ser o unico
   portador da identidade).
   --------------------------------------------------------------------------- */

export interface StepperBarProps {
  passos: Passo[]
  atual: number
  onIr: (n: number) => void
  onGerarRelatorio: () => void
  gerando: boolean
  /** Na visão de UF inteira o último passo recomenda municípios — sem relatório. */
  nivelUf?: boolean
}

/** Quais botões a barra mostra — pura, para ser testada sem montar o componente. */
export function botoesDoStepper({
  atual,
  total,
  nivelUf,
}: {
  atual: number
  total: number
  nivelUf: boolean
}): { navegacao: 'proxima' | 'escolha-municipio' | null; relatorio: boolean } {
  const ultimo = atual >= total
  if (nivelUf) return { navegacao: ultimo ? 'escolha-municipio' : 'proxima', relatorio: false }
  return { navegacao: ultimo ? null : 'proxima', relatorio: true }
}

export default function StepperBar({
  passos,
  atual,
  onIr,
  onGerarRelatorio,
  gerando,
  nivelUf = false,
}: StepperBarProps) {
  // Deriva do proprio funil, como as linhas 69/144/168 ja faziam. Era o unico
  // literal do stepper que precisava de edicao manual a cada passo novo.
  // No nível da UF, o último passo guia para escolher um município (não gera PDF).
  const { navegacao, relatorio } = botoesDoStepper({
    atual,
    total: passos.length,
    nivelUf,
  })
  const podeVoltar = atual > 1

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        padding: '0 16px',
        height: 60,
        background: 'var(--surf-bar)',
        border: '1px solid var(--line-soft)',
        borderRadius: 'var(--r-xl)',
        backdropFilter: 'blur(16px)',
      }}
    >
      <ol
        style={{
          display: 'flex',
          alignItems: 'center',
          flex: 1,
          margin: 0,
          padding: 0,
          listStyle: 'none',
          minWidth: 0,
        }}
      >
        {passos.map((p, i) => {
          const feito = p.n < atual
          const ativo = p.n === atual
          const cor = camadaCor(p.n)
          // O passo é clicável nos dois sentidos; o rótulo precisa dizer isso.
          const rotulo = `${
            ativo ? 'Camada atual,' : feito ? 'Voltar para a camada' : 'Avançar para a camada'
          } ${p.n} de ${passos.length}: ${p.titulo} (${num(p.funil_big)} ${p.funil_unit})`
          return (
            <li
              key={p.n}
              style={{ display: 'contents' }}
            >
              <button
                type="button"
                onClick={() => onIr(p.n)}
                aria-current={ativo ? 'step' : undefined}
                aria-label={rotulo}
                title={rotulo}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  flexShrink: 0,
                  padding: '4px 2px',
                  borderRadius: 8,
                }}
              >
                <span
                  aria-hidden
                  className="num"
                  style={{
                    width: 23,
                    height: 23,
                    borderRadius: '50%',
                    display: 'grid',
                    placeItems: 'center',
                    font: '700 11px/1 var(--f-num)',
                    flexShrink: 0,
                    // Passo feito continua cheio (so' que na cor DELE, nao na do
                    // passo atual): o rastro do funil fica legivel de relance.
                    background: ativo || feito ? cor.fg : 'var(--surf-pending)',
                    // Sem opacidade no passo feito: o ✓ e' texto escuro sobre a cor
                    // da camada e rebaixar a bolinha rebaixaria junto o contraste
                    // dele. Quem separa "atual" de "feito" e o anel + o ✓.
                    color: ativo || feito ? 'var(--ac-on)' : 'var(--tx-muted)',
                    border: ativo || feito ? 'none' : '1px solid var(--line-strong)',
                    boxShadow: ativo ? `0 0 0 4px ${cor.borda}` : 'none',
                    transition: 'background .2s ease, box-shadow .2s ease',
                  }}
                >
                  {feito ? '✓' : p.n}
                </span>
                <span style={{ textAlign: 'left', minWidth: 0 }}>
                  <span
                    style={{
                      display: 'block',
                      font: '600 11.5px/1.1 var(--f-ui)',
                      color: ativo || feito ? 'var(--tx-strong)' : 'var(--tx-muted)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {p.titulo}
                  </span>
                  <span
                    className="num"
                    style={{
                      display: 'block',
                      font: '500 9.5px/1.2 var(--f-num)',
                      marginTop: 2,
                      color: ativo ? cor.fg : feito ? 'var(--tx-label)' : 'var(--tx-off)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {num(p.funil_big)} {p.funil_unit}
                  </span>
                </span>
              </button>

              {i < passos.length - 1 && (
                <span
                  aria-hidden
                  style={{
                    flex: 1,
                    height: 2,
                    margin: '0 10px',
                    borderRadius: 1,
                    // Conector percorrido = cor do passo da ESQUERDA (de onde veio).
                    background: feito ? cor.conector : 'var(--line-mid)',
                    transition: 'background .2s ease',
                    minWidth: 12,
                  }}
                />
              )}
            </li>
          )
        })}
      </ol>

      {podeVoltar && (
        <button
          type="button"
          onClick={() => onIr(atual - 1)}
          disabled={gerando}
          aria-label={`Voltar para a camada ${atual - 1} de ${passos.length}`}
          title="Voltar uma camada"
          style={{
            flexShrink: 0,
            background: 'var(--surf-pending)',
            color: 'var(--tx-soft)',
            font: '600 12px/1 var(--f-ui)',
            padding: '10px 13px',
            borderRadius: 10,
            border: '1px solid var(--line-strong)',
            opacity: gerando ? 0.6 : 1,
          }}
        >
          ← Camada anterior
        </button>
      )}

      {navegacao && (
        <button
          type="button"
          onClick={navegacao === 'proxima' ? () => onIr(atual + 1) : undefined}
          disabled={gerando || navegacao === 'escolha-municipio'}
          style={{
            flexShrink: 0,
            background: navegacao === 'proxima' ? 'var(--ac)' : 'var(--surf-pending)',
            color: navegacao === 'proxima' ? 'var(--ac-on)' : 'var(--tx-muted)',
            font: '700 12px/1 var(--f-ui)',
            padding: '10px 15px',
            borderRadius: 10,
            boxShadow: navegacao === 'proxima' ? 'var(--ac-glow)' : 'none',
            border: navegacao === 'proxima' ? 'none' : '1px solid var(--line-strong)',
            opacity: gerando ? 0.6 : 1,
          }}
        >
          {navegacao === 'proxima' ? 'Próxima camada →' : 'Escolha um município ↑'}
        </button>
      )}

      {/* O relatório fica SEMPRE na ponta direita e em CIANO (pedidos do Vinicius,
          2026-10-20: primeiro rosa, depois ciano) — o `--ac`, turquesa do sistema, por
          token e não por hex, para acompanhar o tema claro. */}
      {relatorio && (
        <button
          type="button"
          onClick={onGerarRelatorio}
          disabled={gerando}
          title="Gerar o Relatório Municipal (PDF)"
          style={{
            flexShrink: 0,
            background: 'var(--ac)',
            color: 'var(--ac-on)',
            font: '700 12px/1 var(--f-ui)',
            padding: '10px 15px',
            borderRadius: 10,
            boxShadow: 'var(--ac-glow)',
            border: 'none',
            opacity: gerando ? 0.6 : 1,
            display: 'flex',
            alignItems: 'center',
            gap: 7,
          }}
        >
          {gerando ? (
            <>
              <Spinner />
              Montando o relatório…
            </>
          ) : (
            'Gerar Relatório Municipal ↓'
          )}
        </button>
      )}
    </div>
  )
}
