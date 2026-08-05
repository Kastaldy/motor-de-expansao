# Spike BLK-MA-10 — a nota do TotalPass existe em alguma superfície legítima?

> Bloco **BLK-MA-10** (Baixa, time-boxed, **zero código de produção**). Medido em 2026-08-05.
> Sucessor da sonda de 2026-07-30/31 (`sonda_rating_agregadores_2026-07-31.md`), que mediu 7 páginas
> de unidade e não encontrou nota.
> Camada **PARALELA e READ-ONLY sobre o M1**. Nenhum dado coletado foi persistido além deste relato.

## 1. Veredito

**ARQUIVAR.** A nota por unidade do TotalPass **não existe** — e o achado importante é *o motivo*:
não se trata de um dado existente porém escondido atrás de proteção técnica. **A funcionalidade de
avaliar academia não existe no produto TotalPass**, nem para o usuário, nem para a academia parceira,
nem no contrato de dados que alimenta o próprio site.

A sonda anterior provou ausência **por amostragem** (7 páginas de unidade). Este spike prova ausência
**no nível do produto**, por vetores que não dependem de amostra.

## 2. As cinco evidências que fecham a questão

**(1) A documentação pública da API não tem o conceito de nota.** O TotalPass mantém um portal de
desenvolvedor aberto e sem autenticação em `dev.totalpass.com`, cujo índice (`/llms.txt`) enumera
**69 páginas / ~65 endpoints** em 3 APIs (parceiro/academia, analytics corporativo em
`hr.totalpass.com`, bookings). **Zero** campo `rating`, `ratingValue`, `reviewCount`, `score`,
`stars`, `nota` ou `avaliação` em qualquer endpoint. Não há sequer endpoint público de catálogo de
academias. Esta é uma fonte independente e *de dentro da própria empresa*.

**(2) O código do site não sabe exibir nota.** O bundle JavaScript completo do app de busca
(`/br/mapa/`) — 20 chunks, ~1,3 MB, cuja leitura o `robots.txt` **autoriza explicitamente**
(`Allow: /*.js`) — tem **zero ocorrência** de qualquer identificador de rating. Não há componente,
estado, tipo nem parser de nota no cliente.

**(3) O backend não serve nota.** O BFF público que alimenta o mapa
(`/api/website/gyms/?locale=br&q=...`, sem autenticação, sem chave) devolve **18 atributos por
unidade** — todos de elegibilidade de plano (`allow_check_in`, `accessible_on_plans`, `closed`…) e
nenhum de reputação. O TotalPass é um **catálogo de elegibilidade**, não um marketplace com
reputação.

**(4) Nenhum dos dois lados do produto conhece a feature.**
- *Usuário:* a Central de Ajuda tem categoria "Academias" com artigos sobre busca, cobertura, planos
  e acesso — e **nenhum** sobre avaliar. Toda ocorrência de "nota" no corpus é **nota fiscal**.
- *Parceiro:* o Portal de Academias tem lista de funções publicada e detalhada (check-in, token,
  financeiro, integração com 13+ ERPs, dashboard) **sem uma única menção** a nota, avaliação ou NPS.
- *Editorial:* o próprio blog do TotalPass **ensina a academia parceira a montar sua própria
  pesquisa de satisfação** em Google Forms / NPS / WhatsApp. Uma plataforma que já tivesse nota por
  unidade não orientaria o parceiro a construir a pesquisa do zero em ferramenta de terceiro.

**(5) O app mobile também não tem — e um cliente pediu.** Os 6 screenshots oficiais da App Store,
**incluindo a tela de mapa com pins e card de unidade** (exatamente onde a nota apareceria), não
mostram estrela, número nem badge. A descrição oficial (v2.87.0, 2026-07-30) não cita avaliação, e o
post de lançamento do app redesenhado lista 6 novidades — nenhuma é nota.

E a prova pelo avesso: em 05/10/2024, na App Store BR, o usuário `binaru` escreveu *"Poderia ter um
sistema de avaliação das academias… seria interessante ter um ranking"*. **É um cliente pagante
pedindo que o recurso seja criado** — evidência positiva de ausência, mais forte que a simples
não-observação. Em 297 resenhas recentes (2026, v2.84–2.87) não há relato de uso da feature.

### O único quase-acerto, verificado a fundo

`GET hr.totalpass.com/api/company_analytic/v1/monthly_gyms_rankings` soa como nota e **não é**: os
campos são `key` (nome da academia), `ranking_position` e `value` (**contagem de check-ins**). É
ranking por **volume**, restrito aos beneficiários de **uma** empresa contratante. Ainda que fosse
acessível, seria inútil como proxy de qualidade e enviesado pelo contrato daquele cliente.

## 3. Termos de Uso e conformidade

Os ToS (`totalpass.com/br/terms/`) **não têm cláusula alguma** proibindo scraping, crawler, robô,
mineração ou acesso automatizado. Há restrição de **uso comercial da marca** e de **reprodução de
conteúdo** sem autorização expressa, e a regra de **1 cadastro por pessoa** — esta última relevante
porque inviabiliza, já no contrato, a hipótese de conta dedicada à coleta.

O `robots.txt` é **permissivo**: só desautoriza `/admin/`, `/auth/`, `/login`, `/logout`,
`/br/onboarding/` e 4 slugs de teste. As páginas de unidade e os assets JS são explicitamente
permitidos. Não há `Crawl-delay`.

**Conduta da sonda:** requisições de leitura pública, espaçadas. Nenhum login, nenhuma credencial,
nenhum captcha ou rate-limit tocado, nenhuma tentativa de contornar os `403` encontrados.

## 4. Custo de insistir — as quatro vias, todas fechadas

| Via | Custo | Retorno |
|---|---|---|
| **API oficial** | As chaves não são públicas: a doc manda "contact the Gyms support team". Exige ser **academia credenciada TotalPass** (Ultra virar parceira de rede do grupo SmartFit) ou **cliente corporativo RH**. Contrato comercial. | **Zero nota.** A API de parceiro só expõe a operação do *próprio* estabelecimento, nunca de concorrentes, e não tem campo de rating |
| **Subdomínios fechados** (`api.`, `cms.`) | Exigiria burlar autenticação | **Vetado** pelos guardrails do bloco — parada imediata |
| **App mobile** | Exigiria interceptar tráfego autenticado, com *certificate pinning* provável | **Vetado** pelos guardrails |
| **Scraping das páginas públicas** | Permitido por robots e ToS; custo de engenharia > 0 | **Zero.** 8/8 páginas de unidade sem qualquer sinal de nota |

## 5. Limites declarados (o que NÃO foi verificado)

Honestidade sobre o perímetro, porque nenhum destes muda o veredito:

- **Central de Ajuda (Zendesk):** devolveu `403` ao acesso automatizado. **Respeitado, sem retry e
  sem troca de User-Agent.** O conteúdo foi lido apenas pelo índice público de busca.
- **Google Play:** a ficha é um shell JS; não foi lida sem execução de script.
- **Tráfego interno do app mobile:** não interceptado, por proibição explícita do bloco. Resta a
  hipótese teórica de uma avaliação in-app que nunca aflora na web, na doc da API, nos screenshots
  oficiais nem em 297 resenhas. **Mesmo nessa hipótese, o dado não seria obtível de forma legítima e
  sustentável** — que é exatamente a pergunta do bloco.

## 6. Recomendação

1. **Arquivar o TotalPass como fonte de nota.** Nenhum follow-up técnico. Se a nota do TotalPass
   virar requisito de negócio, o caminho é **comercial** (pedir a fonte ao grupo SmartFit), não
   técnico.
2. **Levar o universo TotalPass ao `BLK-MA-07`** (reputação **externa**, com gate e DEC próprios) —
   é a alternativa que o próprio backlog do MA-10 antecipava. São **15.986 unidades já coletadas**,
   universo maior que o do WellHub, e que sem isso ficam permanentemente sem sinal 2.
3. **Insumo direto para o `D-B` do `BLK-MA-09`:** está confirmado que a régua assimétrica por fonte
   é **permanente**, não transitória. O universo do score fica partido entre WellHub (com `v2`) e
   TotalPass (sem), e essa partição **não se resolve** por engenharia. O D-B precisa decidir sabendo
   que a fragmentação é definitiva — o que reforça a opção **(0)** já listada como preferida no
   backlog (propagar o rating como coluna-fato **sem peso**), que dissolve o problema em vez de
   administrá-lo.

## 7. Fontes

Superfícies consultadas: `dev.totalpass.com/llms.txt` e `/reference/*`; `totalpass.com/robots.txt`,
`/sitemap.xml`, `/br/sitemap.xml`, `/br/mapa/` (+ bundle `/_next/static/chunks/*.js`),
`/api/website/gyms/`, `/br/academias/sp/`, `/br/academias-estudios/`, `/br/academias/{slug}/`,
`/br/terms/`, `/br/blog/*`; `booking.totalpass.com`, `cms.totalpass.com`, `api.totalpass.com`;
`ajuda.totalpass.com.br`; App Store (ficha, feed RSS de resenhas, screenshots oficiais) e Google Play.
