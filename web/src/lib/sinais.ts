/* ---------------------------------------------------------------------------
   Camada de LABEL dos sinais do score de M&A (BLK-MA-15, revisao de 2026-08-14)

   `sinais_disponiveis` chega do backend como `"s1,s6"` — valor BRUTO de enum,
   produzido pelo pipeline e comparado por igualdade la dentro. Exibi-lo cru nao e'
   neutro: ele ocupa a linha do tooltip que deveria dizer ao operador SOB QUAL
   REGUA aquele numero foi composto, e nao diz nada a quem nao leu o contrato.

   Regra do CLAUDE.md §2: nunca acentuar identificadores; para exibir acentuado,
   usar uma camada de LABEL `{valor_bruto: "Texto Acentuado"}`. E' o que este
   modulo e'. O valor bruto segue intocado no payload, no parquet e no score.

   AS DESCRICOES SAO DO CONTRATO, NAO INVENTADAS. Cada `explica` traduz a coluna
   "direcao" do §8.1 de `docs/vulnerabilidade_ma_contrato.md` para linguagem de
   tela — e mantem a DIRECAO, que e' o que o operador precisa para ler o numero
   (todo sinal e' crescente na vulnerabilidade: `↑ = ↑ vuln`).

   O QUE ELAS NAO DIZEM: "vulnerabilidade", "alvo" ou "aquisicao". Enquanto S3/S4
   estiverem imaturos, afirmar fragilidade da academia e' vender o sinal 6 com o
   rotulo do 3 (DEC-028). As frases descrevem o que foi MEDIDO, nao o veredito.
   --------------------------------------------------------------------------- */

export interface SinalInfo {
  /** Nome curto, para a linha do tooltip. */
  rotulo: string
  /** O que o sinal mede, em uma frase — com a direcao embutida. */
  explica: string
}

/** Mapa dos sinais do contrato (`SINAIS_ORDEM` em `contrato.py`). */
export const SINAIS: Record<string, SinalInfo> = {
  s1: {
    rotulo: 'Presença em agregador',
    explica: 'em quantos apps ela aparece — quanto menos, mais exposta',
  },
  // Nunca chega à tela hoje (`SINAIS_INATIVOS`), mas o mapa é do CONTRATO, não do
  // que está ativo: reativar o s2 não pode fazer o rótulo sumir em silêncio.
  s2: {
    rotulo: 'Nota no agregador',
    explica: 'nota mais baixa entre os alunos do app',
  },
  s3: {
    rotulo: 'Sumiu do agregador',
    explica: 'deixou de aparecer entre uma coleta e outra',
  },
  s4: {
    rotulo: 'Cadastro parado',
    explica: 'semanas sem nenhuma mudança no cadastro',
  },
  s6: {
    rotulo: 'Concorrentes por perto',
    explica: 'concorrência num raio de 2 km, mais pesada quanto mais próxima',
  },
}

/**
 * `"s1,s6"` -> a lista de sinais, na ordem em que o backend os enviou.
 *
 * Token desconhecido vira uma entrada com o codigo cru no rotulo, em vez de ser
 * descartado: um sinal novo no backend (o s5, por exemplo) apareceria como `s5` —
 * feio, mas visivel. Descarta-lo faria a declaracao de regime mentir por omissao,
 * que e' exatamente o que esta linha existe para evitar.
 */
export function sinaisDoRegime(bruto: string | null | undefined): SinalInfo[] {
  if (!bruto) return []
  return bruto
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)
    .map((t) => SINAIS[t] ?? { rotulo: t, explica: 'sinal não catalogado nesta versão da tela' })
}
