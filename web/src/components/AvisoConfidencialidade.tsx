import { Botao, Modal } from './primitives'

/* ---------------------------------------------------------------------------
   Aviso de confidencialidade — pop-up bloqueante de entrada (pedido do Felipe,
   2026-08-19, junto da marca d'água "ARQUIVO CONFIDENCIAL" dos PDFs).

   Aparece SEMPRE que o piloto carrega (estado local do App, sem persistência de
   propósito: cada entrada exige um novo OK) e trava o uso até o clique — não há
   fechar pelo backdrop nem por Esc, e é por isso que ele não passa `onFundo` ao
   `Modal`. O texto é fixo de produto: deixa explícita a responsabilidade do usuário
   sobre os dados e sobre cada relatório exportado, que carrega registro (trilha
   DEC-027) e marca d'água de quem o exportou.

   A casca (véu, cartão, tipografia) vive no `Modal` de `primitives.tsx`; aqui só
   moram o texto, a largura e o z-index — 100, ABAIXO do aviso de sessão.
   --------------------------------------------------------------------------- */

export const TITULO_CONFIDENCIALIDADE = 'Aviso de confidencialidade'

export const PARAGRAFOS_CONFIDENCIALIDADE: readonly string[] = [
  'Todos os dados disponíveis neste sistema são confidenciais e de uso restrito ' +
    'da Ultra Academia. O vazamento dessas informações pode acarretar consequências ' +
    'severas para o responsável.',
  'Todos os relatórios exportados carregam registro e marca d’água de quem os ' +
    'exportou, e a responsabilidade sobre cada relatório é exclusivamente do usuário ' +
    'que o gerou.',
  'Ao clicar em OK, você declara estar ciente dessas condições.',
]

export default function AvisoConfidencialidade({ onConfirmar }: { onConfirmar: () => void }) {
  return (
    <Modal
      titulo={TITULO_CONFIDENCIALIDADE}
      emoji="🔒"
      largura={560}
      zIndex={100}
      paragrafos={PARAGRAFOS_CONFIDENCIALIDADE}
      acoes={<Botao onClick={onConfirmar}>OK, estou ciente</Botao>}
    />
  )
}
