import { useState } from 'react'

/* ---------------------------------------------------------------------------
   TRILHO + PAINEL "CAMADAS DO MAPA" (Juan, 2026-09-02, sobre desenho do Claude
   Design — arquivo "Barra de Camadas do Mapa", opcao 2a).

   O QUE SUBSTITUIU. As chaves do mapa eram quatro botoes de largura cheia
   empilhados no canto inferior esquerdo (`PilulaRegua`, `PilulaIndependentes`,
   `PilulaImoveis` e o botao solto da comparacao). Num municipio com independentes
   E imoveis coletados isso empilhava quatro faixas de ~34px ENTRE o mapa e a
   legenda — ~136px de territorio coberto exatamente no canto em que o operador
   procura a legenda. Pior: a pilha mudava de altura conforme o recorte, entao a
   legenda subia e descia de lugar sozinha.

   O DESENHO. Um trilho vertical de quatro icones, de altura CONSTANTE — ele nao
   muda quando as condicionais entram ou saem, e e' isso que da' ao canto um ponto
   de referencia fixo. As chaves moram num painel unico que abre a partir do
   primeiro icone. Fechado, o mapa perde so' os 46px do trilho.

   O TRILHO NAO REPETE O PAINEL — ele o ATALHA. `Regua` e `Comparar` sao a mesma
   chave que a linha correspondente do painel, e acendem juntas; o icone e' o
   caminho de um clique para quem ja sabe o que quer, o painel e' o caminho de quem
   esta procurando. Um trilho cujos icones abrissem coisas diferentes das que o
   painel lista seria dois vocabularios no mesmo canto.

   COMECA FECHADO. E' o argumento do proprio desenho ("o mapa so perde os 34px do
   trilho quando o painel esta fechado"): abrir por padrao gastaria ~200px de mapa
   toda vez, inclusive para quem nunca liga camada nenhuma. Quem procura acha pelo
   icone de camadas, que tem `title` e fica aceso enquanto o painel esta aberto.

   FUNDO OPACO, nunca translucido: estes elementos ficam SOBRE o mapa, e com fundo
   translucido a legenda de faixas atravessava o texto. `--surf-mapa` e' preto no
   tema escuro e branco chapado no claro — o que resolve e' a opacidade, nao a cor.
   --------------------------------------------------------------------------- */

/** Uma chave do painel. A identidade visual chega pronta: quem sabe a cor de cada
 *  camada e' quem a desenha no mapa, nao este componente. */
export interface ChaveDeCamada {
  id: string
  titulo: string
  /**
   * A linha de baixo, em mono. Muda com o estado, e e' onde mora a CONTAGEM:
   * apagada diz o que ha' para ver ("318 no recorte"), acesa diz o que esta na
   * tela ("312 · visível"). Sem ela o operador liga a camada sem saber se o
   * recorte tem 3 ou 300 pontos.
   */
  sub: string
  ligado: boolean
  onToggle: () => void
  /** Acento da camada: ponto, filete da linha acesa e trilho do switch. */
  cor: string
  /** O mesmo acento, na versao ja aprovada como COR DE TEXTO nos dois temas. */
  corTexto: string
  /** O acento com alpha, para o fundo da linha acesa sobre o painel opaco. */
  corRealce: string
}

const ICONE: Record<string, React.JSX.Element> = {
  /* Pilha de camadas — abre o painel. */
  camadas: (
    <>
      <path d="M12 3 3 8l9 5 9-5-9-5Z" />
      <path d="m3 13 9 5 9-5" />
    </>
  ),
  /* Regua: seta de duas pontas. */
  regua: (
    <>
      <path d="M4 12h16M8 8l-4 4 4 4M16 8l4 4-4 4" />
    </>
  ),
  /* Dois quadros sobrepostos — comparar. */
  comparar: (
    <>
      <rect x="3" y="3" width="12" height="12" rx="2" />
      <path d="M9 21h10a2 2 0 0 0 2-2V9" />
    </>
  ),
  /* Tres filetes — a legenda de faixas. */
  legenda: (
    <>
      <path d="M4 7h16M4 12h16M4 17h10" />
    </>
  ),
}

function BotaoTrilho({
  icone,
  titulo,
  aceso,
  desabilitado = false,
  cor = 'var(--ac-text)',
  onClick,
}: {
  icone: keyof typeof ICONE | string
  titulo: string
  aceso: boolean
  desabilitado?: boolean
  cor?: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={titulo}
      aria-label={titulo}
      aria-pressed={aceso}
      disabled={desabilitado}
      style={{
        width: 34,
        height: 34,
        display: 'grid',
        placeItems: 'center',
        borderRadius: 8,
        border: 'none',
        background: aceso ? 'var(--ac-a16)' : 'transparent',
        color: desabilitado ? 'var(--sinal-off)' : aceso ? cor : 'var(--tx-narrative)',
        opacity: desabilitado ? 0.45 : 1,
        cursor: desabilitado ? 'not-allowed' : 'pointer',
        transition: 'background .15s ease, color .15s ease',
      }}
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        {ICONE[icone]}
      </svg>
    </button>
  )
}

/** Switch de 34x18. Desenhado aqui e nao com um `<input type=checkbox>` porque o
 *  chrome nativo do Chrome/Windows nao segue o tema — o mesmo motivo que ja tirou o
 *  `<select>` nativo do app (ver `components/Select.tsx`). */
function Switch({ ligado, cor }: { ligado: boolean; cor: string }) {
  return (
    <span
      aria-hidden
      style={{
        width: 34,
        height: 18,
        flex: '0 0 auto',
        marginLeft: 'auto',
        display: 'flex',
        alignItems: 'center',
        justifyContent: ligado ? 'flex-end' : 'flex-start',
        padding: 2,
        boxSizing: 'border-box',
        borderRadius: 9,
        background: ligado ? cor : 'var(--sinal-off)',
        transition: 'background .15s ease',
      }}
    >
      <span
        style={{
          width: 14,
          height: 14,
          borderRadius: 7,
          background: '#fff',
          boxShadow: '0 1px 2px rgba(0,0,0,.3)',
        }}
      />
    </span>
  )
}

function Linha({ chave }: { chave: ChaveDeCamada }) {
  const on = chave.ligado
  return (
    <button
      type="button"
      onClick={chave.onToggle}
      aria-pressed={on}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 11,
        width: '100%',
        textAlign: 'left',
        padding: '8px 13px 8px 12px',
        borderRadius: 8,
        border: 'none',
        cursor: 'pointer',
        background: on ? chave.corRealce : 'transparent',
        /* Filete no lado esquerdo em vez de borda inteira: com quatro linhas, quatro
           molduras viravam grade. O filete diz "esta acesa" sem fechar a linha. */
        boxShadow: on ? `inset 2px 0 0 ${chave.cor}` : 'none',
        transition: 'background .15s ease',
      }}
    >
      <span
        aria-hidden
        style={{
          width: 8,
          height: 8,
          borderRadius: 2,
          flex: '0 0 auto',
          background: on ? chave.cor : 'var(--sinal-off)',
        }}
      />
      <span style={{ minWidth: 0 }}>
        <span
          style={{
            display: 'block',
            font: '600 13px/1.25 var(--f-ui)',
            color: 'var(--tx-max)',
          }}
        >
          {chave.titulo}
        </span>
        <span
          className="num"
          style={{
            display: 'block',
            marginTop: 2,
            font: '400 10.5px/1.2 var(--f-num)',
            color: on ? chave.corTexto : 'var(--tx-sub)',
          }}
        >
          {chave.sub}
        </span>
      </span>
      <Switch ligado={on} cor={chave.cor} />
    </button>
  )
}

export default function BarraCamadas({
  chaves,
  regua,
  comparar,
  legendaVisivel,
  onLegenda,
  aviso,
}: {
  /** Todas as chaves do painel, na ordem fixa do desenho. */
  chaves: ChaveDeCamada[]
  /** Atalho do trilho para a regua — a MESMA chave da linha correspondente. */
  regua: { ligado: boolean; onToggle: () => void }
  /** Idem para a comparacao. `null` = fora do drill-down, entao o icone fica inerte. */
  comparar: { ligado: boolean; onToggle: () => void } | null
  legendaVisivel: boolean
  onLegenda: () => void
  /**
   * Linha de estado no pe do painel (hoje: a espera do raio de 1 km).
   *
   * No PAINEL e nao solta no mapa: o raio e' o que a camada 3 desenha, entao a
   * espera dele pertence ao lugar em que se fala de camada. Ausente = sem aviso.
   */
  aviso?: string | null
}) {
  const [aberto, setAberto] = useState(false)
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, pointerEvents: 'auto' }}>
      {/* TRILHO — altura constante, quatro icones, sempre os mesmos quatro. */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          padding: 6,
          borderRadius: 10,
          background: 'var(--surf-mapa)',
          border: '1px solid var(--linha-mapa)',
          flexShrink: 0,
        }}
      >
        <BotaoTrilho
          icone="camadas"
          titulo={aberto ? 'Fechar as camadas do mapa' : 'Camadas do mapa'}
          aceso={aberto}
          onClick={() => setAberto((v) => !v)}
        />
        <BotaoTrilho
          icone="regua"
          titulo={
            regua.ligado
              ? 'Régua ligada — clique na origem e no destino'
              : 'Medir a distância entre dois pontos do mapa'
          }
          aceso={regua.ligado}
          onClick={regua.onToggle}
        />
        <BotaoTrilho
          icone="comparar"
          titulo={
            comparar
              ? comparar.ligado
                ? 'Comparando hexágonos — clique para somar mais'
                : 'Somar vários hexágonos num cenário'
              : 'Comparar hexágonos só dentro de um município'
          }
          aceso={comparar?.ligado ?? false}
          desabilitado={!comparar}
          onClick={() => comparar?.onToggle()}
        />
        <BotaoTrilho
          icone="legenda"
          titulo={legendaVisivel ? 'Esconder a legenda' : 'Mostrar a legenda'}
          aceso={legendaVisivel}
          onClick={onLegenda}
        />
      </div>

      {/* PAINEL — some por inteiro quando fechado; o trilho e' que fica. */}
      {aberto && (
        <div
          role="group"
          aria-label="Camadas do mapa"
          style={{
            width: 330,
            flexShrink: 0,
            background: 'var(--surf-mapa)',
            border: '1px solid var(--linha-mapa)',
            borderRadius: 12,
            padding: '11px 8px 9px',
            /* `--sh-pop` e' o token do BALAO que flutua sobre o conteudo, e nao um
               preto cravado: no tema claro ele troca o preto por azul-tinta com menos
               alfa (ver tokens.css). Uma sombra preta chapada sobre o Positron seria a
               unica mancha escura da tela. */
            boxShadow: 'var(--sh-pop)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0 6px 8px 12px',
            }}
          >
            <span
              className="num"
              style={{
                font: '500 10.5px/1 var(--f-num)',
                letterSpacing: '.12em',
                textTransform: 'uppercase',
                color: 'var(--tx-muted)',
              }}
            >
              Camadas do mapa
            </span>
            <button
              type="button"
              onClick={() => setAberto(false)}
              title="Fechar"
              aria-label="Fechar as camadas do mapa"
              style={{
                width: 20,
                height: 20,
                display: 'grid',
                placeItems: 'center',
                borderRadius: 5,
                font: '400 15px/1 var(--f-ui)',
                color: 'var(--tx-muted)',
              }}
            >
              ×
            </button>
          </div>

          {chaves.map((c) => (
            <Linha key={c.id} chave={c} />
          ))}

          {aviso && (
            <div
              className="num"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 7,
                margin: '6px 0 0',
                padding: '7px 12px 2px',
                borderTop: '1px solid var(--line-soft)',
                font: '400 10.5px/1.3 var(--f-num)',
                color: 'var(--tx-sub)',
              }}
            >
              <span
                aria-hidden
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  flexShrink: 0,
                  background: 'var(--carga)',
                  animation: 'pulse 1s ease-in-out infinite',
                }}
              />
              {aviso}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
