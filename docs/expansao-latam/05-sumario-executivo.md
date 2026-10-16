# Motor de Expansão na América Latina: sumário executivo

**Para:** Diretoria e C-level · **De:** Estratégia e Growth · **Data:** 16/10/2026 · **Status:** recomendação; nada foi decidido nem implementado.

## Recomendação

**Levar o Motor ao México, à Colômbia e ao Peru, nessa ordem, e ao Paraguai só sob demanda, restrito às regiões metropolitanas.** Antes do primeiro país novo, investir **~5 semanas** num "kit de país" que a Argentina mostrou faltar.

- **A plataforma já é multi-país.** A Argentina está no ar desde 03/09/2026 com a mesma arquitetura (um sistema, uma instância por país). O próximo país não exige reescrever o produto.
- **O custo real está em outros dois lugares,** medidos na Argentina:
  - **montar a base de dados de cada país**, ~7 semanas de uma pessoa;
  - **corrigir números errados que não geram erro** nas semanas seguintes, ~4 semanas.
- **O kit de país ataca os dois:**
  - um validador que barra o pacote de dados com número errado antes de ir ao ar;
  - uma biblioteca comum para montar a base de cada país.

## Ordem dos países e por quê

| | Prêmio | Qualidade do dado | Esforço | Risco | Leitura |
|---|---|---|---|---|---|
| **1. México** | O maior: 131 M de habitantes, penetração de 5,6 % | **A melhor**: cadastro oficial com 30 mil academias georreferenciadas; renda medida por município | O maior (~2,7× a Argentina em área servida) | Franquia: a lei exige entregar números de investimento e retorno ao franqueado, o que torna a viabilidade documento com responsabilidade legal | Melhor dado e maior prêmio. O risco legal afeta só o módulo de viabilidade, que fica desligado até termos premissas mexicanas assinadas |
| **2. Colômbia** | 53 M, penetração de 6,9 % | Boa: quarteirão censitário com estrato social; censo de 2018 | Do tamanho da Argentina | Baixo; IVA de 19 % sobre a mensalidade e juro de 12,25 % apertam o payback | O mercado mais ocupado pela Smart Fit (232 unidades). **Pode vir primeiro** se a prioridade for o país novo no ar mais rápido |
| **3. Peru** | 34 M, penetração de 6 %, **o menos ocupado pela Smart Fit** (95 unidades; a Bodytech saiu em 2024) | Média: o censo de 2025 ainda não saiu por quarteirão | Médio | O menor (acordo tributário com o Brasil em vigor) | Entrar em 3º dá tempo para o censo 2025 completo sair |
| **4. Paraguai** | Pequeno: o mercado comporta **3 a 8 unidades Ultra** em 3–5 anos (estimativa) | A mais fraca: sem dado social abaixo do distrito | O menor | Lei local pode alcançar a rescisão de franquia (pede parecer) | O motor completo pode custar mais que a decisão que informa. Recomendamos estudo de mesa antes de uma instância |

## Prazo

- **~6 meses** para os quatro MVPs (mapa de oportunidades com potencial, demanda e concorrência), **com duas pessoas de dados** trabalhando em paralelo. **A segunda pessoa (estagiário) está em contratação**, informado por Felipe em 16/10/2026.
- **~9 a 10 meses com uma pessoa só**, o cenário até a contratação. Conte de 2 a 4 semanas de ambientação do estagiário antes de ele assumir um país (recomendação: Colômbia, sobre o kit já testado no México).
- **Marcos com duas pessoas:**
  - kit de país em ~5 semanas;
  - México MVP na semana ~15;
  - Colômbia na ~16;
  - Paraguai, se aprovado, na ~23;
  - Peru na ~25.
- **Marcos com uma pessoa:** México ~15, Colômbia ~24, Peru ~34, Paraguai ~39.
- **A viabilidade financeira de cada país** (DRE com tributos locais) corre em paralelo e depende de assessoria fiscal local: **3 a 6 semanas por país**.

## O que o Motor promete fora do Brasil, e o que não promete

- **Promete:** triagem. Onde há população, renda e demanda não atendida, e quem já está lá.
- **Não promete:** prever faturamento. Isso foi testado no Brasil e fechado por decisão (DEC-043).
- **Validação:** nenhum dos quatro países tem unidade Ultra para calibrar. Validaremos com:
  - um teste de "falso-veto" contra as unidades da Smart Fit: o motor não pode descartar onde ela já opera;
  - as aberturas dela em pré-venda, registradas como previsão antes de abrirem;
  - um ranking cego feito pelo time local.

## Riscos principais

1. **Uma pessoa de dados** serializa os quatro países: +3 a 4 meses. *Mitigação:* segunda pessoa (estagiário em contratação) mais o kit comum com agentes de IA. O estagiário precisa de 2 a 4 semanas de ambientação e de revisão sênior nos pacotes.
2. **Números errados silenciosos** voltam a cada país (a Argentina ainda tem 5 hoje, que corrigimos primeiro). *Mitigação:* validador obrigatório.
3. **Penetração e capacidade das academias** sem fonte primária (México e Paraguai) mudam a escala da demanda. *Mitigação:* parâmetro declarado, com faixa e teste de sensibilidade.
4. **Concorrência independente pouco visível** sem agregadores (Peru e Paraguai; o OpenStreetMap cobre só ~9 % das academias). *Mitigação:* múltiplas fontes e aviso na tela.
5. **Viabilidade com premissa brasileira usada como documento de franquia no México:** risco legal. *Mitigação:* módulo desligado até as premissas locais serem assinadas.
6. **Servidor:** cabe na mesma máquina em memória e disco, mas a CPU é o limite. *Mitigação:* limites por país e gatilho escrito para uma segunda máquina.
7. **Imóveis:** os portais de aluguel dos três países grandes bloqueiam coleta automática. Essa parte só entra com parceria comercial.

## Decisões que precisam de aprovação

| # | Decisão | Quem |
|---|---|---|
| 1 | **Ordem de entrada e escopo** (México → Colômbia → Peru; Paraguai sob demanda e só metros) — DEC-073/D10 | Felipe / Expansão Internacional |
| 2 | ~~Segunda pessoa de dados~~: **resolvida**, estagiário em contratação (16/10/2026) | — |
| 3 | **Assessoria fiscal local por país** para a viabilidade (DEC-073/D6) | Diretoria / Financeiro |
| 4 | **Validador e contrato de dados** como condição de entrega de todo país (DEC-073/D1) e **biblioteca comum** de montagem de base (DEC-073/D2) | Felipe / Juan |
| 5 | **Renda em moeda local** (não em dólar) nos países novos, por causa da volatilidade cambial (COP −23 % e guarani −17 % em 12 meses) — DEC-073/D5 | Felipe / Financeiro |
| 6 | **Um login só** para todos os países (hoje já são dois cadastros) e infraestrutura gerada automaticamente por país (DEC-073/D7, DEC-073/D8) | Felipe / Vinicius |
| 7 | **Protocolo de liberação** de país sem unidade Ultra (DEC-073/D9) e **correção das réguas** que hoje erram na Argentina (DEC-073/D3, DEC-073/D4) | Felipe |
| 8 | **Parcerias com portais imobiliários** (México, Colômbia, Peru), se o módulo de imóveis for prioridade | Expansão Internacional |

*Detalhe técnico, evidências (com fonte, data e status de verificação) e o que ficou sem verificar: `00-baseline-argentina.md` a `04-roadmap.md` nesta pasta.*
