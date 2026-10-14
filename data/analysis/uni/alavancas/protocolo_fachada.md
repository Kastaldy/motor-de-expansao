# Fachada × desempenho (BLK-UNI-05B, passo 4)

Versão 1.0, 2026-09-29. Escrito antes de rodar. A fachada foi avaliada por Felipe e Vini na coleta de metragem
(28–29/09) e **nunca foi comparada com desempenho** até aqui.

## Pergunta

Unidade com fachada melhor fatura **acima do que a praça prevê** (resíduo do modelo M0)?

## Dados

- **Fachada:**
  - nota de 1 a 5 (média dos avaliadores);
  - índice dos 6 itens (letreiro visível, vitrine para a rua, frente para via principal, esquina, estacionamento
    próprio, acesso pelo térreo) = fração de "sim" entre os itens visíveis ("não dá para ver" fica fora).
- **Resíduo fora da amostra do M0** (log do real − log do previsto; positivo = fatura acima do previsto):
  - unidades do treino (maduras de 2025): resíduo LOO;
  - unidades do teste do UNI-02: o erro do teste;
  - outras unidades maduras em 2026, com metragem e isócrona: previsão do M0 treinado nas 39, com o calendário.
- Concordância entre avaliadores: descritiva (poucas unidades avaliadas pelos dois).

## Teste e leitura (fixados antes)

- Para cada X (nota e índice):
  - Spearman com o resíduo, com IC 90% por bootstrap (2.000 reamostras);
  - inclinação por MQO, em % de faturamento por ponto de nota.
- "**Sinal**" se o IC do Spearman exclui zero **com sinal positivo**. "**Contrário**" se exclui com sinal negativo.
  Senão, "**inconclusivo**".
- **Poder:** com N ≈ 15, só se detecta |ρ| acima de ~0,45. "Inconclusivo" aqui não quer dizer "sem efeito".
- A fachada entra também na conferência congelada da turma de 2026 (`previsao_2026/`), onde as notas das 16 unidades
  ficam registradas hoje, antes de haver desempenho maduro.

Arquivos: `alavancas/04_fachada.py` → `resultado_fachada.md`.

## Versão 1.1 (2026-09-29): amostra ampliada, antes de rodar

**Motivo:** das 31 unidades com nota, só 14 estão maduras e têm metragem. Pedido do Felipe: usar o máximo das notas.

**Unidades acrescentadas:**
- **Com 6 a 12 meses de vida** (não maduras), com metragem:
  - o desfecho é o nível maduro **projetado** pela curva de faturamento do UNI-03: faturamento do último mês válido
    (mês de vida 6–12) ÷ mediana da curva naquele mês;
  - o erro da projeção é de ~9% no mês 6;
  - resíduo = log(projetado) − log(previsto pelo M0 com o calendário de 2026).
- **Maduras sem metragem** (shopping):
  - resíduo contra um modelo **sem metragem** (renda e população), treinado nas 39;
  - mais fraco que o M0, então essas unidades só entram na leitura ampliada.

**Regra:** a mesma de antes (Spearman com IC 90% por bootstrap). Reporta-se a amostra principal (14) e a ampliada.
"**Sinal**" na ampliada só vale se o IC excluir zero **e** o Spearman da principal tiver o mesmo sinal.

Arquivos: `alavancas/05_fachada_ampliada.py` → `resultado_fachada_ampliada.md`.

## Versão 1.2 (2026-09-29): confirmação com as notas do Juan (escrita antes de ele preencher)

**Decisão do Felipe:**
- **Botafogo sai só do teste de fachada.** O motivo dado: "fachada ridícula, totalmente fora da curva, o maior
  outlier da rede".
- Nas demais análises ela continua.
- A exclusão é pós-hoc e registrada como decisão do dono. As versões com e sem Botafogo foram reportadas em
  `resultado_fachada_sem_botafogo.md`: sem ela, 13 maduras dão +0,67 [+0,27; +0,91], e a ampliada, +0,49 [+0,15; +0,76].

**Confirmação:** feita nas unidades avaliadas **só pelo Juan**, que ninguém tinha avaliado antes; é a planilha
`coleta_metragem/planilha_fachada_juan.xlsx`.
- **Desfecho:** o mesmo resíduo fora da amostra do M0:
  - treino: LOO;
  - teste do UNI-02: o erro do teste;
  - maduras sem metragem: o modelo sem m²;
  - jovens com 6+ meses: a projeção pela curva.
- **Teste:** Spearman nota × resíduo, IC 90% por bootstrap (2.000), inclinação em % por ponto.
- "**Confirma**" se o IC exclui zero com sinal positivo. Reporta-se também a amostra total (Felipe + Vini + Juan),
  sempre sem Botafogo.
- **Concordância:**
  - 6 unidades já avaliadas por Felipe/Vini estão misturadas sem aviso (gabarito em
    `coleta_metragem/_gabarito_nao_abrir/fachada_juan_calibracao.csv`);
  - se o Juan diferir em mais de 1 ponto em 3 ou mais delas, a régua dele é tratada como diferente, e a leitura
    principal passa a ser o Spearman **dentro** do avaliador.
- Botafogo não está na planilha do Juan.

## Versão 1.3 (2026-09-30): hipótese "loja de rua", escrita antes das notas restantes do Juan

**Pergunta do Felipe:** tirando as unidades extremas, como foi feito com Botafogo, a fachada se sustenta?

**Resposta, medida antes desta versão** com as 14 primeiras notas do Juan (exploratório):
- tirar só as unidades que contrariam (as de nota 2 que faturam acima) daria +0,41. É **escolher a dedo** e não vale
  como evidência;
- regras que não olham a nota:
  - corte simétrico de 10% em cada ponta: +0,16 [−0,20; +0,47];
  - só fora de shopping, sem Botafogo: +0,30 [−0,03; +0,64].

**Para as notas que o Juan ainda vai dar** (~34 unidades que ninguém viu), a leitura principal passa a ser:
- **"loja de rua"** (hipótese levantada pela análise, não pelo Felipe): unidades fora de shopping (`poi_em_shopping`, critério que não olha desempenho), sem Botafogo;
- **"confirma"** se o IC 90% do Spearman nota × resíduo excluir zero com sinal positivo **nas unidades novas ainda não
  avaliadas** (as 11 da leitura parcial ficam de fora dessa conta);
- reportam-se também todas as unidades e a versão com shopping.

Nenhuma outra exclusão por desempenho é permitida.

