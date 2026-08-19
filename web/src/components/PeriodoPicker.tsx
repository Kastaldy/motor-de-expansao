import { useEffect, useId, useState } from 'react'

import {
  ajustarAoLimite,
  dataBr,
  ehData,
  mesmoPeriodo,
  periodoValido,
  rotuloDoPeriodo,
  type LimitePeriodo,
  type Periodo,
} from '../lib/periodo'

/* ---------------------------------------------------------------------------
   Seletor de PERÍODO de análise — substitui o Select de competência (um mês) por
   um intervalo com as duas pontas, inclusivo.

   POR QUE `<input type="date">` NATIVO, e não uma grade de calendário nossa: o
   input abre o calendário do sistema, já é acessível por teclado, entende o
   formato do idioma da máquina, respeita `min`/`max` e não custa uma linha de
   manutenção. O `Select` deste repo é customizado por um motivo MEDIDO (o popup
   do `<select>` nativo sai branco no Chrome/Windows e fica ilegível no tema
   escuro) — o input de data não tem esse defeito: o `<meta name="color-scheme"
   content="dark">` do index.html já entrega o calendário e o ícone em tema
   escuro. Reescrever uma grade de datas à mão seria assumir fuso, semana, teclado
   e leitor de tela sem nenhum ganho.

   POR QUE NÃO HÁ ATALHOS ("Mês atual", "Últimos 90 dias"…): eles existiram e
   saíram a pedido do Felipe (2026-08-10). Eram seis chips numa faixa própria, o
   cabeçalho ficou alto demais e a fileira quebrava linha junto dos filtros. O
   componente cabe agora DENTRO da fila de filtros, ao lado dos selects, e é isso
   que mantém o cabeçalho do tamanho que era.

   TODA a aritmética e todo rótulo vêm de `lib/periodo` (puro, testado). Aqui só
   tem estado de digitação e pintura.
   --------------------------------------------------------------------------- */

const ESTILO_DATA: React.CSSProperties = {
  // O CSS global já veste `input` (fundo, borda, raio, fonte); aqui só o que é
  // específico da barra de controles: largura fixa (senão o `width: 100%` global
  // estica o campo pela linha inteira) e a caixa mais baixa, do tamanho do botão do
  // `Select` ao lado.
  width: 136,
  flex: '0 0 auto',
  padding: '6px 8px',
  borderRadius: 8,
  // Redundante com o `<meta color-scheme>` do documento, e barato: garante o
  // calendário e o ícone do seletor em tema escuro mesmo se este componente for
  // reaproveitado fora do index.html do piloto.
  colorScheme: 'dark',
}

export interface PeriodoPickerProps {
  periodo: Periodo
  /** Primeira e última data com dado na base. Amarra o `min`/`max` dos inputs. */
  limite: LimitePeriodo
  /** Só dispara com período VÁLIDO — a tela nunca recebe intervalo impossível. */
  onChange: (p: Periodo) => void
}

export default function PeriodoPicker({ periodo, limite, onChange }: PeriodoPickerProps) {
  const idMensagem = useId()

  // O rascunho é o estado de DIGITAÇÃO; `periodo` (do pai) é a verdade. Os dois são
  // separados porque o caminho até um período válido passa por estados inválidos: ao
  // trocar o início para depois do fim, o campo tem de mostrar o que foi digitado
  // enquanto a mensagem explica por que nada subiu. Mesma divisão do `CampoNumero`.
  const [rascunho, setRascunho] = useState<Periodo>(periodo)

  useEffect(() => {
    setRascunho(periodo)
  }, [periodo.inicio, periodo.fim])

  const validacao = periodoValido(rascunho, limite)

  /** Sobe para o pai SÓ o que é válido; o inválido fica na tela com a explicação. */
  function propor(p: Periodo) {
    setRascunho(p)
    if (periodoValido(p, limite).ok) onChange(p)
  }

  // Saída de emergência para quem digitou fora da cobertura: em vez de só recusar,
  // oferece o período mais próximo que a base consegue responder. Não aparece quando
  // o problema é outro (datas invertidas, campo pela metade) — grampear não resolve
  // esses, e um botão que não conserta nada é pior que botão nenhum.
  const sugestao = ajustarAoLimite(rascunho, limite)
  const podeAjustar =
    !validacao.ok && !mesmoPeriodo(sugestao, rascunho) && periodoValido(sugestao, limite).ok

  const cobertura = `A base cobre de ${dataBr(limite.min)} a ${dataBr(limite.max)}.`

  // Qual campo pintar de vermelho. Campo em branco acusa SÓ ele; erro de ordem ou de
  // cobertura é do par (não dá para dizer qual das duas datas o operador quis mudar),
  // e aí os dois ficam marcados. Pintar o campo preenchido de vermelho porque o OUTRO
  // está vazio manda a pessoa conferir a data certa.
  const faltaInicio = !ehData(rascunho.inicio)
  const faltaFim = !ehData(rascunho.fim)
  const algumEmBranco = faltaInicio || faltaFim
  const erroNoInicio = !validacao.ok && (algumEmBranco ? faltaInicio : true)
  const erroNoFim = !validacao.ok && (algumEmBranco ? faltaFim : true)

  return (
    <div
      role="group"
      aria-label="Período de análise"
      style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}
    >
      <input
        type="date"
        className="num"
        aria-label="Data inicial do período"
        aria-invalid={erroNoInicio}
        aria-describedby={idMensagem}
        value={rascunho.inicio}
        min={limite.min}
        max={limite.max}
        title={cobertura}
        onChange={(e) => propor({ ...rascunho, inicio: e.target.value })}
        style={{
          ...ESTILO_DATA,
          // A borda vermelha marca o campo, mas nunca é o único portador do erro:
          // a mensagem ao lado diz o que houve, e é ela que o leitor de tela
          // anuncia (`aria-describedby`).
          border: erroNoInicio ? '1px solid var(--neg)' : undefined,
        }}
      />
      <span aria-hidden style={{ font: '500 11px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
        até
      </span>
      <input
        type="date"
        className="num"
        aria-label="Data final do período"
        aria-invalid={erroNoFim}
        aria-describedby={idMensagem}
        value={rascunho.fim}
        min={limite.min}
        max={limite.max}
        title={cobertura}
        onChange={(e) => propor({ ...rascunho, fim: e.target.value })}
        style={{
          ...ESTILO_DATA,
          border: erroNoFim ? '1px solid var(--neg)' : undefined,
        }}
      />

      {/* O nó existe SEMPRE, mesmo vazio: `aria-describedby` aponta para ele, e um id
          que aparece e some deixa o leitor de tela sem referência no meio da digitação.
          Com período válido ele não ocupa espaço — o rótulo do intervalo e a contagem
          de dias já estão na legenda do cabeçalho, e repeti-los aqui empurraria os
          filtros para a linha seguinte, que é justamente o que este componente evita. */}
      <span
        id={idMensagem}
        // `polite`: a mensagem muda a cada tecla do campo de data; interromper o
        // leitor de tela a cada dígito seria pior que não anunciar.
        aria-live="polite"
        style={{
          display: validacao.ok ? 'none' : 'inline-flex',
          alignItems: 'center',
          gap: 7,
          font: '500 11px/1.3 var(--f-ui)',
          color: 'var(--neg)',
          maxWidth: 320,
        }}
      >
        {!validacao.ok && (
          <>
            <span>{validacao.erro}</span>
            {podeAjustar && (
              <button
                type="button"
                onClick={() => propor(sugestao)}
                title={`Usar ${rotuloDoPeriodo(sugestao)}`}
                style={{
                  padding: '3px 8px',
                  borderRadius: 'var(--r-sm)',
                  border: '1px solid var(--line-strong)',
                  background: 'transparent',
                  color: 'var(--tx-soft)',
                  font: '600 11px/1 var(--f-ui)',
                  whiteSpace: 'nowrap',
                }}
              >
                Ajustar à base
              </button>
            )}
          </>
        )}
      </span>
    </div>
  )
}
