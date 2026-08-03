/**
 * Texto exibido quando um valor nao existe para o recorte (metrica ausente, secao que o
 * motor nao devolveu, campo nao preenchido).
 *
 * Espelha `TEXTO_SEM_DADO` de `src/motor_expansao/dashboard/constants.py` — a tela e o PDF
 * que sai dela NAO podem chamar a mesma coisa por nomes diferentes. Se mudar aqui, mude la.
 *
 * Era a sigla "n/d"; trocada por extenso a pedido de Juan (2026-08-03), porque quem le nao
 * e do time e nao decodificava a sigla.
 *
 * ATENCAO ao usar em readout compacto: a string tem 14 caracteres contra 3 da sigla antiga.
 * Onde o layout foi dimensionado para caber em UMA linha (cards estreitos da aba
 * Viabilidade, sidebar de investimento), confira que nao quebrou.
 */
export const TEXTO_SEM_DADO = 'Não disponível'
