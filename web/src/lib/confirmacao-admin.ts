/* ---------------------------------------------------------------------------
   A FRASE de cada confirmação da tela de administração de usuários.

   POR QUE ISTO É UM MÓDULO PURO. O projeto testa com Vitest em ambiente `node`,
   sem DOM: não há jsdom, nem testing-library, e os 37 testes de `web/src/` vivem
   todos em `lib/`. O precedente da casa é extrair a lógica do componente para cá
   e testá-la — `select-filter.ts` saiu de `Select.tsx`, `imovel.ts` saiu da tela
   de oportunidades, `crescimento.ts` saiu do NarrativePanel. Aqui vale o mesmo: o
   casulo do pop-up não é testável neste projeto, mas o TEXTO dele é — e o texto é
   a parte que pode mentir.

   E há precedente de montar frase em português para o operador ler: `fraseConsolidada`
   em `consolidado.ts` e `compararComFrase` em `comparacao.ts`.

   O QUE A FRASE PRECISA DIZER. Não "Confirmar alteração?", que treina a pessoa a
   clicar em Sim no automático. Quem, o quê, e o de-para — e a consequência, que é
   o que de fato responde "o que está sendo feito".
   --------------------------------------------------------------------------- */

/**
 * A D22 escrita como ela é: uma ordem **parcial**, não uma escada.
 *
 * `Expansão ⊂ Líderes ⊂ Growth` e `Consultoria ⊂ Líderes`. Repare no que NÃO está
 * aqui: `expansao` e `consultoria` são INCOMPARÁVEIS — nenhum contém o outro.
 *
 * Isto existe porque a saída fácil estaria errada. O payload de `/api/acessos/usuarios`
 * traz `capacidades` (11 / 2 / 13 / 15) e a ordem dele é a hierarquia — mas ele é uma
 * ordem TOTAL. Comparar os números diria que ir de Expansão (11) para Consultoria (2)
 * é um REBAIXAMENTO, quando na verdade é uma troca de área: a pessoa perde a carteira
 * de imóveis e ganha a Visão Executiva, que Expansão não tem. Dizer "vai perder acesso"
 * ali seria mentir na tela que existe para não deixar ninguém errar.
 */
const CONTIDOS_EM: Readonly<Record<string, readonly string[]>> = {
  growth: ['growth', 'lideres', 'expansao', 'consultoria'],
  lideres: ['lideres', 'expansao', 'consultoria'],
  expansao: ['expansao'],
  consultoria: ['consultoria'],
}

/** O perfil que dá poder de administrar gente — o único com atrito extra. */
export const PERFIL_ADMINISTRADOR = 'growth'

export type Relacao = 'igual' | 'sobe' | 'desce' | 'muda-de-area' | 'desconhecida'

/**
 * Como `para` se relaciona com `de`, pela D22.
 *
 * `desconhecida` cobre o perfil que o seed ainda não tem: um quinto perfil criado no
 * banco não pode ser descrito como promoção nem como rebaixamento por chute. Aí a
 * frase fica honesta e diz só o de-para, sem afirmar direção.
 */
export function relacaoEntrePerfis(de: string, para: string): Relacao {
  if (de === para) return 'igual'
  const contemPara = CONTIDOS_EM[para]
  const contemDe = CONTIDOS_EM[de]
  if (!contemPara || !contemDe) return 'desconhecida'
  if (contemPara.includes(de)) return 'sobe'
  if (contemDe.includes(para)) return 'desce'
  return 'muda-de-area'
}

const NOMES: Readonly<Record<string, string>> = {
  consultoria: 'Consultoria',
  expansao: 'Expansão',
  lideres: 'Líderes',
  growth: 'Growth',
}

/**
 * O rótulo de exibição de um perfil.
 *
 * `descricoes` é o mapa `perfil -> descricao_perfil` que vem do banco já acentuado.
 * Ele existe como segunda escolha para o caso do quinto perfil: sem ele, o fallback
 * imprimiria o slug cru (`novo_perfil`), sem acento, num texto de usuário — o que a
 * regra permanente do CLAUDE.md §2 proíbe.
 */
export function rotuloPerfil(perfil: string, descricoes?: Record<string, string>): string {
  return NOMES[perfil] ?? descricoes?.[perfil] ?? perfil
}

export type AcaoAdmin =
  | {
      tipo: 'criar'
      nome: string
      login: string
      email: string
      perfil: string
      capacidades?: number
    }
  | {
      tipo: 'trocar-perfil'
      nome: string
      login: string
      de: string
      para: string
      capacidadesDe?: number
      capacidadesPara?: number
    }
  | { tipo: 'definir-ativo'; nome: string; login: string; perfil: string; ativo: boolean }

export interface Confirmacao {
  /** Tarja curta acima do título. Caixa alta no componente. */
  eyebrow: string
  /** O título GARRAFAL. Uma frase, com quem e o quê. */
  titulo: string
  /** Parágrafos de apoio: a consequência, e o que é ou não reversível. */
  apoio: string[]
  /** O rótulo do botão que confirma. Repete a ação — nunca só "Confirmar". */
  rotuloConfirmar: string
  /** `alta` pinta o botão de perigo; `media` usa o acento normal. */
  gravidade: 'alta' | 'media'
  /**
   * Quando não é nulo, o botão só libera se a pessoa digitar EXATAMENTE este login.
   * Só acontece no caminho que concede poder de administrador.
   */
  loginParaDigitar: string | null
}

/** Frase de capacidades, quando os dois números vieram do payload. */
function contagem(de?: number, para?: number): string {
  if (de === undefined || para === undefined) return ''
  return ` ${de} → ${para} capacidades.`
}

/**
 * Compara o texto digitado com o login esperado.
 *
 * Comparação LITERAL, sem normalizar caixa nem acento, e sem aparar espaço interno —
 * apenas as bordas, porque colar de outro campo costuma trazer espaço em volta. O
 * ponto do atrito é exigir atenção; aceitar `ANA.TESTE` no lugar de `ana.teste`
 * devolveria parte da facilidade que ele existe para tirar.
 */
export function loginConfere(digitado: string, esperado: string): boolean {
  return digitado.trim() === esperado
}

/**
 * Monta a confirmação de uma ação. Função total: todo caminho devolve frase.
 *
 * O que ela NÃO faz, de propósito: prometer resultado. Ela descreve INTENÇÃO. Quem
 * diz o que aconteceu é o recado da tela, montado da resposta do servidor — que lê o
 * estado anterior com a linha travada e pode devolver `mudou: false`. Se o pop-up
 * dissesse "Expansão → Growth" como fato e o servidor respondesse "já estava assim",
 * quem estaria errado seria o pop-up.
 */
export function montarConfirmacao(
  acao: AcaoAdmin,
  descricoes?: Record<string, string>,
): Confirmacao {
  const rot = (p: string) => rotuloPerfil(p, descricoes)

  if (acao.tipo === 'criar') {
    const ehAdmin = acao.perfil === PERFIL_ADMINISTRADOR
    return {
      eyebrow: ehAdmin ? 'Criar com poder de administrador' : 'Criar usuário',
      titulo: `Criar ${acao.nome} como ${rot(acao.perfil)}`,
      apoio: [
        `Login ${acao.login} · ${acao.email}.`,
        ehAdmin
          ? `${rot(acao.perfil)} administra o acesso das outras pessoas: pode criar, ` +
            'desativar e trocar o perfil de quem já existe.'
          : `Perfil ${rot(acao.perfil)}.` + contagem(undefined, acao.capacidades),
        'A pessoa nasce com a senha inicial compartilhada do piloto e é levada a trocá-la ' +
          'no primeiro acesso.',
        'Esta tela não apaga ninguém: para desfazer, o caminho é desativar. E ela ainda ' +
          'precisa ser cadastrada no Authelia para conseguir entrar.',
      ],
      rotuloConfirmar: `Criar ${acao.nome}`,
      gravidade: ehAdmin ? 'alta' : 'media',
      loginParaDigitar: ehAdmin ? acao.login : null,
    }
  }

  if (acao.tipo === 'trocar-perfil') {
    const rel = relacaoEntrePerfis(acao.de, acao.para)
    const viraAdmin = acao.para === PERFIL_ADMINISTRADOR && rel === 'sobe'
    const nums = contagem(acao.capacidadesDe, acao.capacidadesPara)

    const consequencia =
      rel === 'sobe'
        ? `Continua com tudo o que tem hoje e ganha o que ${rot(acao.para)} abre a mais.${nums}`
        : rel === 'desce'
          ? `Perde o que ${rot(acao.de)} abria e fica só com o de ${rot(acao.para)}.${nums}`
          : rel === 'muda-de-area'
            ? `Troca de área: ${rot(acao.de)} e ${rot(acao.para)} abrem coisas diferentes — ` +
              `não é promoção nem rebaixamento.${nums}`
            : `As duas faixas de acesso são diferentes.${nums}`

    return {
      eyebrow: viraAdmin ? 'Conceder poder de administrador' : 'Mudar o acesso de alguém',
      titulo: `${acao.nome} vai passar de ${rot(acao.de)} para ${rot(acao.para)}`,
      apoio: [
        `Login ${acao.login}.`,
        consequencia,
        viraAdmin
          ? `${rot(acao.para)} pode criar, desativar e trocar o perfil de outras pessoas — ` +
            'menos o dele próprio. Digite o login abaixo para liberar.'
          : 'O acesso muda na hora, e fica registrado com o seu nome, a data e o de-para.',
      ],
      rotuloConfirmar: `Passar ${acao.nome} para ${rot(acao.para)}`,
      gravidade: viraAdmin || rel === 'desce' ? 'alta' : 'media',
      loginParaDigitar: viraAdmin ? acao.login : null,
    }
  }

  // definir-ativo
  if (acao.ativo) {
    return {
      eyebrow: 'Devolver o acesso',
      titulo: `${acao.nome} volta a entrar no piloto`,
      apoio: [
        `Login ${acao.login}. O acesso volta com o perfil ${rot(acao.perfil)}, que é o que ` +
          'está selecionado na linha dela.',
        'Fica registrado com o seu nome e a data.',
      ],
      rotuloConfirmar: `Reativar ${acao.nome}`,
      gravidade: 'media',
      loginParaDigitar: null,
    }
  }
  return {
    eyebrow: 'Tirar o acesso',
    titulo: `${acao.nome} perde o acesso ao piloto agora`,
    apoio: [
      `Login ${acao.login}, perfil ${rot(acao.perfil)}.`,
      'Nada é apagado: a linha e todo o histórico dela ficam, e você reativa aqui mesmo. ' +
        'É o caminho de quem sai da empresa.',
      `Enquanto estiver inativa, o login ${acao.login} volta a ficar livre para outro cadastro.`,
    ],
    rotuloConfirmar: `Desativar ${acao.nome}`,
    gravidade: 'alta',
    loginParaDigitar: null,
  }
}
