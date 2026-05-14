# TESE E PLANO EXECUTIVO

Documento operacional para orientar agentes de IA e humanos na evolucao do projeto.
Objetivo: decidir e executar a proxima fase sem contaminar o M1 canonico.
Limite estrategico: preservar o que ja funciona; refatorar o que trava evolucao; validar M1.1 em paralelo.

## 1. Tese central

Nao devemos reiniciar o projeto do zero.
Devemos:
- congelar o M1 como produto canonico e auditavel;
- parar de adicionar complexidade no nucleo atual;
- extrair um nucleo menor e mais claro do M1;
- construir o M1.1 como camada paralela e experimental;
- separar concorrencia e imobiliario como camadas proprias de ingestao;
- promover qualquer nova camada somente apos gates objetivos.

Resumo decisorio: produto correto; codigo saturado; refundacao controlada, nao rewrite total.

## 2. Verdades operacionais

- O contrato canonico do projeto esta em `CLAUDE.md`.
- O M1 oficial fecha com IBGE, Parquet e `score_priorizacao`.
- O M1 atual ja tem validacao executiva suficiente para continuar existindo.
- O M1 atual ainda usa fallback municipal em larga escala; isso limita a granularidade intraurbana.
- O experimento censitario 2010 provou valor analitico, mas nao esta pronto para promocao.
- O M1.1 deve nascer paralelo e nao pode alterar score, dashboard nem artefatos oficiais do M1.
- Concorrencia e imobiliario devem produzir snapshots proprios e alimentar o motor como input, nao como dependencia ao vivo.

## 3. Objetivo deste plano

Entregar, em sequencia:
1. um M1 estabilizado e mais facil de manter;
2. um M1.1 Fase A implementado como prova forte de enriquecimento territorial;
3. uma base objetiva para decidir promocao, pausa ou mudanca de rota.

## 4. Escopo e nao escopo

No escopo agora:
- M1 canonico;
- refatoracao estrutural do nucleo M1;
- M1.1 Fase A: Censo 2022 setores censitarios + agregacao H3-r7;
- testes, contratos e rastreabilidade;
- staging em Parquet e snapshots locais.

Fora do escopo agora:
- alterar `score_priorizacao`;
- incorporar OSM ao fechamento nacional;
- fazer M2 competitivo completo;
- fazer M3 imobiliario completo;
- acoplar scrapers ou APIs ao vivo diretamente no core territorial;
- API de producao;
- ML;
- dashboards executivos com nova metrica antes de aprovacao.

## 5. Regra mestra para agentes

Todo agente deve assumir:
- M1 e sagrado: nao alterar formula, pesos, artefatos ou naming oficial sem aprovacao explicita;
- M1.1 e paralelo: toda coluna nova deve ser claramente experimental;
- nenhuma fonte nova pode ser consultada ao vivo no fechamento nacional;
- tudo novo entra via snapshot em `data/raw/` e staging em Parquet;
- collectors de concorrencia e imobiliario publicam insumos; o core apenas consome insumos versionados;
- toda decisao de promocao exige teste, rastreabilidade e criterio numerico;
- se surgir duvida entre velocidade e auditabilidade, escolher auditabilidade.

## 6. Diagnostico tecnico sintetico

Pontos fortes:
- contrato do M1 esta claro e o fluxo territorial principal e coerente;
- testes canonicos e documentacao de negocio ja sustentam o nucleo atual.

Pontos fracos:
- `hex_enrichment.py` concentra logica demais e mistura fluxo oficial, legado e experimento;
- `jobs/`, `daily_pipeline.py`, API e modelos representam uma historia maior que o repo atual sustenta;
- dependencias, empacotamento e testes ainda misturam trilhas diferentes.

## 7. Decisao arquitetural

Decisao:
- manter o M1 atual funcionando;
- extrair um `m1_core` enxuto;
- criar um `m1_1` separado para enriquecimento territorial;
- separar `collectors` de concorrencia e imobiliario do motor territorial;
- tratar codigo legado fora do M1 como periferia, nao como trilha critica.

Arquitetura alvo:
- `m1_core/base_h3.py`
- `m1_core/ibge_structural.py`
- `m1_core/scoring.py`
- `m1_core/priorizacao.py`
- `m1_core/exports.py`
- `m1_1/censo_2022_setor.py`
- `m1_1/join_h3.py`
- `m1_1/territorial_dataset.py`
- `m1_1/quality_gates.py`
- `collectors/concorrencia/`
- `collectors/imobiliario/`
- `integration/opportunity_inputs.py`
- `integration/opportunity_engine.py`

Observacao: wrappers atuais podem continuar existindo temporariamente; centralizacao desejada = hub canonico de dados e decisao, nao monolito com scraping ao vivo acoplado.

## 8. Ordem de execucao

### Fase 0 - Congelamento e contratos

Entregas:
- inventario final dos artefatos oficiais;
- testes de regressao por schema e por colunas-chave;
- documentacao curta de "o que nao pode mudar".

Gate de saida:
- M1 congelado como referencia confiavel e executavel sem ambiguidade de score oficial.

### Fase 1 - Refatoracao estrutural do M1

Entregas:
- extracao da logica do M1 para modulos menores;
- separacao clara entre fluxo oficial e codigo legado;
- CLI atual mantida, mas como casca fina;
- limpeza de imports e caminhos quebrados fora do core.

Gate de saida:
- artefatos finais identicos ou semanticamente equivalentes;
- testes canonicos verdes;
- nenhuma alteracao em `score_priorizacao`.

### Fase 2 - M1.1 Fase A

Objetivo:
- produzir `censo_2022_h3_res7.parquet` e `brasil_territorial_enriquecido.parquet`.

Entregas:
- ingestao de setores censitarios 2022;
- spatial join setor x H3-r7;
- colunas de demanda residente e cobertura;
- rastreabilidade por linha;
- relatorio de qualidade nacional.

Colunas minimas:
- `pop_total_setor_2022`
- `pop_18_45_setor_2022`
- `renda_per_capita_setor_2022`
- `domicilios_setor_2022`
- `cobertura_setor_2022_pct`

Gate de saida:
- cobertura e rastreabilidade conforme `docs/m1_1_arquitetura_enriquecimento.md`;
- join final preserva 100% das linhas do M1.

### Fase 3 - Validacao decisoria

Entregas:
- comparacao municipal vs setor 2022;
- amplitude intraurbana por capital;
- correlacao agregada com M1 municipal;
- recomendacao executiva: GO, PILOTO ou NO-GO.

Gate de saida:
- decisao formal registrada em doc.

### Fase 4 - Arquitetura futura de inputs operacionais

Entregas:
- contrato de input para concorrencia;
- contrato de input para imobiliario;
- camada de integracao que consome snapshots normalizados e cruza com M1/M1.1;
- definicao de SLA, retries, deduplicacao e geocodificacao fora do core territorial.

## 9. Regras de promocao do M1.1

Nenhuma camada entra no score executivo se nao cumprir:
- cobertura nacional suficiente;
- refresh previsivel;
- licenca clara;
- reproducao em lote;
- latencia operacional aceitavel;
- rastreabilidade por linha;
- coerencia com H3-r7 e parametros canonicos;
- validacao com performance real de unidades Ultra.

## 10. Backlog priorizado

Prioridade P0:
- congelar contrato M1;
- isolar nucleo do M1;
- remover dependencia mental de OSM no fechamento nacional;
- corrigir infraestrutura minima de testes.

Prioridade P1:
- implementar M1.1 Fase A;
- criar quality gates nacionais;
- gerar parquet enriquecido paralelo.

Prioridade P2:
- definir schema canonico de input de concorrencia;
- definir schema canonico de input imobiliario;
- estudar CNPJ CNAE 9313;
- estudar Grade 2022, CNEFE e Entorno.

Prioridade P3:
- implementar coletores separados e snapshots versionados;
- ligar `opportunity_engine` aos inputs normalizados;
- avaliar CNPJ, MapBiomas, INEP e validacao com dados reais de unidade.

## 11. Instrucao de trabalho para agentes

Ao pegar uma tarefa, o agente deve informar:
- qual fase esta executando;
- qual artefato de entrada usa;
- qual artefato de saida gera;
- qual contrato nao pode quebrar;
- qual teste ou validacao prova conclusao.

Todo PR ou patch deve responder:
- o M1 oficial mudou? se sim, parar;
- o output novo e paralelo? se nao, parar;
- houve snapshot local? se nao, parar;
- ha colunas de rastreabilidade? se nao, parar;
- existe gate objetivo de qualidade? se nao, parar.

## 12. Definicao de pronto

Uma entrega so esta pronta quando:
- codigo roda;
- teste relevante existe ou foi atualizado;
- artefato de saida foi especificado;
- rastreabilidade foi preservada;
- impacto no M1 foi explicitamente negado ou demonstrado.

## 13. Sinais de alerta que justificam pausa

- tentativa de mudar `score_priorizacao` cedo;
- uso de API publica ao vivo como dependencia nacional;
- crescimento de complexidade dentro do arquivo unico atual;
- mistura de experimento com output oficial;
- falta de comparabilidade nacional nas novas features.

## 14. Decisao final deste plano

Continuar no pipeline, sim.
Continuar do jeito atual, nao.
Comecar tudo do zero, nao.

Rota aprovada:
- M1 congelado;
- M1 refatorado por extracao;
- M1.1 paralelo com Fase A primeiro;
- concorrencia e imobiliario como camadas separadas de ingestao;
- promocao apenas apos gates.
