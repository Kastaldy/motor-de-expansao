# Passagem do estudo BLK-UNI (Inteligência de Unidade)

De Felipe para Juan, 13/10/2026. O estudo é **fase de pesquisa**: nada aqui está em produção, e nada vai para a aba de
viabilidade sem DEC.

## Por onde começar

1. `CADERNO_ESTUDO_UNI.md`: a história completa, em linguagem de negócio. O topo tem as mensagens-chave; o fim tem as
   pendências e os próximos passos.
2. `relatorio/README.md` e `relatorio/ROTEIRO.md`: os gráficos da apresentação, cada um com o script que o gera.
3. `tasks/backlog.md`, epic **BLK-UNI**: um bloco por análise, com o escopo e as decisões do Felipe.

## Onde o modelo está (13/10)

- **Modelo de trabalho (v2):** log da metragem, log da renda domiciliar e log da população da área de 10 min de carro,
  mais estúdio (sim/não) e master real (M1 a M7, anonimizada).
- **Erro típico nas 57 unidades** (cada uma prevista por um modelo que não a viu):

  | Faturamento | Balcão | Agregador | Total recombinado |
  |---|---|---|---|
  | 25% | 22% | 30% | 23% |

- Para a diretoria, a precisão é **22% a 27%** (o número muda com uma unidade a mais ou a menos no treino).
- **Única melhoria clara:** previsão em dois tempos (meses 1 a 3 + v2), que só vale depois de abrir.
- **Antes de uma DEC:** rodar com o aluguel e a obra reais das unidades novas e conferir a turma de 2026.

## Mapa das pastas

| Pasta | O que tem | Bloco | No caderno |
|---|---|---|---|
| raiz (`01_` a `06_`) | painel da rede: de-para, fato unidade × mês, atributos, cobertura, pinos corrigidos | UNI-00 | Etapa 1 |
| `uni01/` | exploração de hipóteses, anatomia dos erros, modelo em duas partes | UNI-01 | Etapas 2, 6 e 7 |
| `uni02/` | confirmação do modelo nas 18 novas | UNI-02 | Etapa 8 |
| `uni02r/` | réplica da hipótese do diretor em outras redes | UNI-02 | Etapa 4 |
| `uni03/` | curva de rampa | UNI-03 | Etapa 3 |
| `uni04/` | renda × cancelamento | UNI-04 | Etapa 5 |
| `uni05/` | viabilidade v2 × atual no simulador | UNI-05 | Etapa 9 |
| `alavancas/` | alavancas do operador, estúdio × master, fachada | UNI-05B | Etapas 10 e 12, Fachada |
| `mix/` | fatia de agregador por praça | UNI-05C | Etapa 11 |
| `uni07/` | erro do modelo e faixas de segurança | UNI-07 | Etapa 13 |
| `simulacoes/`, `manaus_volume/` | caso Manaus | UNI-11 | Simulação pontual |
| `termometro/` | Smart Fit vizinha como termômetro | UNI-12 | Termômetro |
| `bateria/` | concorrência, idade, avenida, faculdade | UNI-10 | Bateria |
| `uni09/` | balcão + agregador | UNI-09 | Faturamento em duas partes |
| `exploratoria/`, `previsao_turma_b/` | exploratória de 06/10 e turma B (já lida em 06/10: deixou de ser juiz cego) | UNI-09 | Exploratória |
| `uni13/` a `uni16/` | sem agregador, masters, validação ampliada, melhorias, preço | UNI-13 a UNI-16 | Seções de 06 e 07/10 |
| `ficha_v2/` | ficha técnica do modelo (R², faixas, métodos) | — | Validação ampliada |
| `releitura/` | testes antigos relidos com a medida de efeito | — | Antes de inaugurar |
| `checklist_ponto/` | checklist do ponto (planilhas A e B) | UNI-17 | Antes de inaugurar |
| `precos/`, `idade/` | coletas agregadas da Growth (vendas e idade) | UNI-16 | — |
| `coleta_metragem/` | metragem por satélite e controle de qualidade | UNI-02 | Etapa 8 |
| `previsao_2026/` | previsões congeladas da turma de 2026 | UNI-12 | — |
| `relatorio/` | gráficos da apresentação | — | — |
| `../isocronas/` | motor das áreas de 10 min de carro | UNI-00 | — |
| `../poi/` | base de POIs e o teste de polos de fluxo | — | Etapa 0 |

## Como rodar

- Da raiz do repositório, **um script por vez** (rodar vários juntos travou a máquina em 25/09):

  ```
  PYTHONIOENCODING=utf-8 PYTHONPATH=src .venv/Scripts/python.exe data/analysis/uni/<pasta>/<script>.py [modo]
  ```

- Os testes registrados antes de rodar têm modos, nesta ordem e um por vez: `--seca`, `--ensaio`, `--registrar`,
  `--rodar`.
- **Caminhos desta máquina:** vários scripts gravam no OneDrive do Felipe ou leem de `Downloads`. Ajuste os caminhos antes
  de rodar.
- **h3:** na máquina do Felipe o Windows bloqueia a biblioteca h3, e alguns scripts trazem um substituto vazio no topo.
  Em outra máquina, o h3 normal funciona.

## Dados (fora do git)

O git tem só código, documentos e registros. A pasta `data/analysis/` continua no `.gitignore` (a regra protege os
dados): para versionar um arquivo novo, use `git add -f <arquivo>`, e só para código, documento ou registro. Os dados
ficam fora:

- **Painel** (`fato_unidade_mes`, `dim_unidade`, `depara_unidade`): refeito pelos scripts `01_` a `05_`, a partir de
  `insumos_vps/` (cópias de artefatos da VPS) e `insumos_locais/` (Financeiro, `dados_academias.xlsx` e outros).
- **Growth API** (`precos/`, `idade/`): credenciais no `.env` (`GROWTH_API_USUARIO`, `GROWTH_API_SENHA`).
  - LGPD: só agregados; `cod_aluno`, nome, usuário e data de nascimento são descartados antes de gravar; sem cache.
  - No máximo 10 chamadas a cada 5 min; no erro 429, uma tentativa só, e para.
- **Base Consolidada** (`BASE UNIDADES_CONSOLIDADA.xlsx`): **nada dela sai da máquina do Felipe.** Só scripts locais, nunca
  subagente ou workflow de IA, nunca git, VPS ou OneDrive. Os derivados ficam em `LOCAL_bateria_operador/` (testes do
  operador e das modalidades), que não está no git.
- **`NAO_ABRA/`** (demanda revelada do TotalPass): só local; não abrir.
- **Previsões congeladas** (o juiz de 2027): os CSVs ficam fora do git. Os arquivos `REGISTRO_*.txt` estão no git e
  guardam o SHA de cada uma, que prova que a previsão não mudou depois de congelada.

## Regras de trabalho do estudo

- **Registro antes de rodar:** protocolo → checagem seca (contagens, sem desempenho) → revisão adversarial → ensaio com
  ruído → `REGISTRO_PRE` com SHA → rodada (com marcador e `REGISTRO_POS`) → verificação independente.
- **Teste = tamanho do efeito** com faixa de 90% (erro-padrão robusto HC3) e correção de Holm. A régua antiga ("cair 2
  pontos nas 39 e no teste") quase nunca detectava efeito moderado; hoje os 2 pontos são só o portão para levar à aba:
  o erro tem de cair 2 pontos no faturamento **e** no total.
- **Sempre os três modelos lado a lado** (faturamento, balcão, agregador) e o total recombinado.
- **Erro típico** = mediana de |previsto ÷ real − 1|, com cada unidade prevista por um modelo que não a viu.
- **Quem decide a adoção é o Felipe.** O critério registrado é checagem; o objetivo é prever melhor.
- **Nenhum "não" é definitivo:** variáveis podem voltar com dado novo.
- **Contexto que muda leituras:**
  - desde mar/2025 a rede abre sem agregador;
  - a contagem de alunos de agregador da Growth não é limpa, e a premissa do aluno de agregador fica em 60% do recorrente;
  - o público é de todas as idades (mediana de 37 anos; um terço com 45 ou mais).

## Agenda

| Quando | O quê | Onde |
|---|---|---|
| Quando as planilhas voltarem | checklist do ponto: piloto cronometrado de 5 unidades, concordância (item abaixo de 75% nas 20 sai), registro, rodada e verificação | `checklist_ponto/protocolo_checklist_ponto.md` |
| Quando a turma de 2026 amadurecer (2027) | conferir as previsões congeladas: v2, renda domiciliar, master real, duas partes, termômetro, bateria (inclusive operador e modalidades, que só existem na máquina do Felipe) e UNI-13 a UNI-15. Cada protocolo diz o critério | `previsao_2026/`, `termometro/`, `bateria/`, `uni09/`, `uni13/` a `uni15/` |
| Quando as unidades de 2026 ligarem o Wellhub | registrar o tier e conferir o +21% por nível | `releitura/`, `uni16/protocolo_uni16.md` |
| ~mar/2027 | RJ passando a aceitar Wellhub (set/2026): primeiro caso de "não aceitava → passou a aceitar" | Caderno, Pendências |
| Com o export do Lifetime | retenção da turma de abertura e da pré-venda | backlog, BLK-UNI-PEND-01 |
| Quando quiser | preço dentro da mesma unidade (o dado já está em `precos/vendas_unidade_mes.parquet`) | Caderno, Pendências |
