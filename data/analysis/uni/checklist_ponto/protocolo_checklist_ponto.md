# BLK-UNI-17 — Checklist do ponto (pré-registro, rascunho)

Versão 1.0, 2026-10-07, revisada antes de qualquer preenchimento. Só análise; nada vai para a aba de viabilidade sem o
Felipe.

## Pergunta (Felipe, 07/10)

Uma avaliação do ponto/imóvel, feita **antes de abrir**, melhora a previsão dos três modelos (faturamento, balcão e
agregador) e do total recombinado?

## Por que um checklist, e não uma nota livre

A nota livre de fachada (1 a 5) saiu **inconclusiva** em 30/09 (`alavancas/resultado_fachada_final.md`):
- com um avaliador independente, a correlação foi de +0,05 (N 23);
- nas 6 unidades de controle, a régua do Juan diferiu da de Felipe/Vini em mais de 1 ponto em 3 delas.

O caderno concluiu: "se voltar, precisa de checklist objetivo". Por isso:
- a avaliação vem de **itens de fato do imóvel**, com definição e limiar;
- a nota livre continua, mas é preenchida depois do checklist e testada à parte (ela acrescenta algo ao checklist?).

**Exposição declarada:**
- 6 dos 8 itens do índice já formavam o "índice dos 6 itens" da fachada.
- Aquele índice foi rodado e visto em 15 unidades (+0,22, inconclusivo; `alavancas/resultado_fachada.md`).
- Este teste é um **reteste**, com definições mais duras e mais unidades.

## Itens (planilha de cada avaliador)

**Imagem**
- Usar a última imagem do Street View **anterior à inauguração** ("Ver mais datas").
- Se não houver, usar a primeira depois dela e marcar `imagem_antes_da_abertura` = não.
- Os itens descrevem o **imóvel**, nunca a loja pronta (letreiro, equipamentos).
- `data_imagem_rua` é texto, no formato aaaa-mm.
- `imovel_conferido`: a imagem mostra o imóvel certo? (algumas coordenadas são aproximadas; a planilha mostra a
  confiança de cada uma).

**Bloco 1 — Visibilidade do imóvel**
1. `frente_visivel_da_via`: da faixa de trânsito mais próxima, ~50 m antes do imóvel no sentido do trânsito, a frente
   aparece sem nada na frente (árvore, marquise, banca, outro prédio)?
   - sim;
   - não, obstruída (conta como **não**);
   - sem imagem utilizável (fica de fora).
2. `fachada_envidracada`: a frente do imóvel no térreo tem vidro ou porta de vidro voltada para a calçada?
   sim / não / sem imagem utilizável.
3. `esquina`: o imóvel fica no encontro de duas ruas que se cruzam? O lote que vai de uma rua até a paralela não é
   esquina. sim / não / sem imagem utilizável.
4. `testada_m`: largura da frente na rua da entrada, em metros (satélite → botão direito → "Medir distância").
   Número inteiro. Dentro de shopping: deixar vazio.

**Bloco 2 — Via e acesso**
5. `tipo_via`, contando as faixas de rolamento num sentido, sem a faixa de estacionamento:
   - avenida (2 ou mais faixas por sentido, ou canteiro central; mão única com 2 ou mais faixas conta);
   - rua (1 faixa por sentido);
   - interna (dentro de shopping, condomínio ou estacionamento).
6. `estacionamento`: próprio do imóvel / compartilhado (shopping, supermercado, centro comercial) / só na rua / sem
   imagem utilizável.
7. `entrada`: térreo pela rua / andar de cima com porta na rua / por dentro de shopping ou galeria.

**Bloco 3 — Entorno imediato** (até 150 m a pé, medidos no Maps)
- Não conta o próprio imóvel, nem o shopping ou o supermercado onde a academia fica.
- Itens:
  8. `supermercado_150m`: sim / não / não sei.
  9. `shopping_150m`: sim / não / não sei.
  10. `terminal_150m`, terminal ou estação de ônibus, metrô ou trem (ponto de ônibus não conta): sim / não / não sei.
  11. `faculdade_150m`: sim / não / não sei.
  12. `quadra_comercial`: na quadra, a maioria dos imóveis no térreo é comércio? sim / não / não sei.
- Só descritivos, fora do índice:
  13. `ponto_onibus_100m`: sim / não / não sei.
  14. `academia_concorrente_150m`, outra marca: sim / não / não sei.

**Bloco 4 — Imóvel**

15. `tipo_imovel`: loja de rua / galpão / centro comercial ou prédio / dentro de shopping / anexo a supermercado.

**Depois do checklist**
- `nota_potencial_1a5`: "o ponto, sozinho (sem pensar em cidade, renda ou concorrência), atrai aluno?", de 1 a 5.
- `sabe_como_vai`: você sabe se esta unidade vai bem ou mal? sim / não. É sensibilidade: a leitura sem essas
  unidades sai ao lado.
- `observacao`.

## Índice do ponto (fixado agora)

- **Item favorável = 1**, um ponto por item:
  - frente visível = sim;
  - fachada envidraçada = sim;
  - esquina = sim;
  - tipo de via = avenida;
  - estacionamento **próprio** (a mesma definição do índice da fachada; "compartilhado" não conta);
  - entrada no térreo pela rua;
  - pelo menos uma âncora a até 150 m;
  - quadra comercial = sim.
- **Índice** = itens favoráveis ÷ itens respondidos. "Sem imagem utilizável" e "não sei" ficam de fora; "obstruída"
  conta como não.
- **Unidade sem índice:** com menos de 75% dos itens retidos respondidos.
  - Ela recebe o índice médio e uma marca "sem índice", nos dois lados da comparação.
  - O resultado informa quantas.

## Avaliadores, cegamento e concordância

- **Avaliador A:** todas as unidades obrigatórias, na ordem sorteada da planilha; as opcionais ficam no fim.
- **Avaliador B:** 20 unidades sorteadas, com pelo menos 4 de shopping ou galeria, sozinho e sem ver a planilha do A.
- **Quem avalia:**
  - de preferência, alguém de fora da operação e do time que escolheu os pontos;
  - nunca quem viu as tabelas de "faturou acima/abaixo do previsto" por unidade;
  - o Felipe escolhe.
- **O que não pode ser aberto:** o cartão da Ultra no Google Maps (nota, avaliações, "horários de pico" e fotos), que é
  pista de movimento. Só a imagem da rua e o satélite.
- **Entrega:** cada avaliador recebe só a própria planilha, por canal separado, sem este protocolo. A instrução não diz
  qual é a hipótese.
- **Concordância**, medida ANTES de ligar o checklist ao desempenho, no item do jeito que entra no índice:
  - item com concordância abaixo de 75% nas 20 sai do índice;
  - a testada sai se a diferença mediana entre A e B passar de 25%;
  - AC1 com faixa é reportado ao lado.
  - A decisão usa só a concordância, nunca o desempenho.
  - Com 20 unidades a régua é imprecisa: um item que concorda 80% de verdade pode cair por azar. Isso fica declarado.

## Teste (a versão 1.1 é congelada com SHA ANTES de ligar o checklist ao desempenho)

**Unidades:**
- as 57 do modelo: 39 maduras de 2025 e 18 maduras de 2026, juntas, com o ajuste de nível de 2026, como no T2 do
  UNI-15;
- `poi_em_shopping` entra como controle nos dois lados.

**Principal — o efeito, em cada modelo:**
- coeficiente do índice no faturamento (v2), no balcão e no agregador, com faixa robusta (HC3) de 90%;
- **"tem efeito"** se a faixa exclui zero com sinal positivo, depois de Holm (k = 3, 5% de um lado).
- **Poder** (simulação própria, 07/10: 57 unidades, erro típico de 22%), conforme a correlação real entre o índice e a
  parte que o modelo erra:

  | Correlação real | Chance de detectar |
  |---|---|
  | 0,2 | 39% |
  | 0,3 | 68% |
  | 0,4 | 90% |

  Com efeito nulo, 4%.

**Portão de adoção** (não é teste; decide se vale levar para a aba):
- o erro de cada unidade prevista sem ela, nas 57, cai ≥ 2 pontos no faturamento **e** no total recombinado.
- **Atenção:** na mesma simulação, a régua antiga dos UNI-14/15 (cair 2 pontos nas 39 e no teste) detecta um efeito
  real de 0,3 a 0,5 em só 1% a 4% das vezes. Por isso ela deixa de ser o teste e vira só portão.

**Leituras (sem veredito):**
- Spearman do índice com o faturamento acima/abaixo do previsto (57 + as 3 maduras da turma B), com faixa de 90%;
- nota livre: sozinha, e se acrescenta algo ao índice;
- cada item, um a um (com 13 itens, algum "acerta" por acaso);
- só lojas de rua;
- sem as unidades marcadas "sei como vai";
- sem Botafogo;
- testada (log).

**Prospectivo (o teste limpo) — só as 5 cegas:**
- belford-roxo-rj, novo-gama-df, paulinia-sp, domingos-ferreira-pe e bonsucesso-rj, conferidas em 2027 com o
  BLK-UNI-12;
- o SHA da planilha preenchida é registrado na entrega;
- as outras 11 da turma de 2026 são avaliadas agora, mas ficam fora de toda análise até 2027: 7 delas já tiveram
  "faturou vs. previsto" publicado por unidade.

## Se passar / se não passar

- **Tem efeito e passa no portão:**
  - o checklist vira formulário na aba de viabilidade;
  - a nota ajusta a previsão pelo efeito medido, com a faixa ao lado;
  - quem propõe o ponto não preenche;
  - é ideia de tela: entra no backlog e só é desenvolvida depois da fase de pesquisa.
- **Tem efeito, mas não passa no portão:** aparece como faixa de cenário, sem mexer no número central.
- **Sem efeito:**
  - fica como registro descritivo do ponto;
  - o ± de demanda da aba continua sendo premissa;
  - as 5 cegas ainda são conferidas em 2027.

## Fluxo

Rascunho → revisão adversarial (feita em 07/10: 15 achados, todos aplicados nesta versão) → piloto cronometrado de 5
unidades → planilhas para o Felipe distribuir → preenchimento → concordância → v1.1 congelada (REGISTRO_PRE) → rodada →
verificação independente.
