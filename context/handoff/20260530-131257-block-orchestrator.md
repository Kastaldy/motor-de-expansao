# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-OPS-03 — Manifesto de proveniência nos outputs**

Adicionar, como passo final ISOLADO do pipeline de exportação BI do M1, a geração de um
arquivo `data/outputs/_manifest.json` que carrega a proveniência do conjunto de outputs:
vintage IBGE, hash sha256 do `Ultra.csv`, commit do código, timestamp de geração e os
valores dos parâmetros canônicos do score. O dashboard passa a exibir essa proveniência em
modo somente-leitura (rodapé/caption). É um bloco ADITIVO e NÃO-MUTANTE: nenhum valor dentro
de qualquer artefato de scoring do M1 pode mudar. O manifesto fica AO LADO dos artefatos,
nunca DENTRO do conteúdo de scoring.

## Objetivo
Materializar um manifesto de proveniência ao lado dos outputs do M1 (e exibi-lo read-only no
dashboard) sem alterar um único byte dos artefatos oficiais de scoring.

## Escopo permitido
- (1) Gerar `data/outputs/_manifest.json` ao FINAL de `fase1_bi_exports.py`, como passo
  isolado, executado DEPOIS que todos os artefatos M1 já foram escritos em disco. O cálculo
  do manifesto não pode estar acoplado ao cálculo/escrita do score nem dos parquets.
- (2) Expor o manifesto no rodapé/aba do dashboard em modo read-only (ex.: `st.caption` /
  `st.expander` ao final de `main()` em `streamlit_app.py`, ou via um helper render em
  `dashboard/components.py`/`pages.py`). Apenas leitura e exibição — sem recálculo.
- (3) Teste em `tests/unit/test_manifest.py` validando presença do arquivo e schema
  (todos os campos obrigatórios e seus tipos/valores esperados).
- Opcional sugerido pela current_task: extrair a lógica de geração para um módulo novo
  `src/motor_expansao/pipelines/m1/provenance.py` (mantém o passo isolado e testável). O
  Planner decide se cria o módulo ou se a função vive dentro de `fase1_bi_exports.py`.

## Fora de escopo
- Alterar QUALQUER valor dentro dos artefatos M1 (parquets de scoring, CSVs, resumo
  executivo). O manifesto é arquivo separado, nunca uma coluna/campo dentro do conteúdo.
- Recalcular `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo,
  plano de domínio ou qualquer artefato oficial.
- Mudar pesos, parâmetros canônicos ou regras de negócio — o manifesto apenas LÊ e
  REGISTRA os valores atuais; não os define nem os altera.
- Adicionar dependência de API ao vivo no dashboard de produção.
- Tocar em outras camadas/blocos. Um bloco por vez.

## Arquivos que devem ser lidos
- `src/motor_expansao/pipelines/m1/fase1_bi_exports.py` — ponto de inserção do passo final
  isolado: a geração do manifesto deve ocorrer em `main()` DEPOIS de
  `generate_fase1_bi_artifacts()` (que chama `write_outputs`, escrevendo
  `DASHBOARD_PATH`, `TOP_OPORTUNIDADES_PATH`, `RESUMO_UF_PATH`, `MAPA_SAMPLE_PATH`,
  `RESUMO_EXECUTIVO_PATH`) e, idealmente, após o bloco do enriquecido particionado. Reusar a
  constante de diretório de saída: o manifesto vai em `Path("data/outputs/_manifest.json")`,
  irmão de `DASHBOARD_PATH = data/outputs/hexagonos_brasil_dashboard.parquet`. `ESTRUTURAL_PATH`
  aponta para `data/staging/brasil_estrutural.parquet` (artefato a proteger por hash, junto
  com `brasil_priorizados.parquet` e `hexagonos_brasil_oportunidades.parquet`).
- `src/motor_expansao/config.py` — FONTE CANÔNICA dos parâmetros (via objeto `settings`):
  `H3_RESOLUTION` (=7), `DIST_MIN_ULTRA_KM` (=1.0), `RENDA_MIN` (=4500.0). Pesos do score NÃO
  estão aqui.
- `src/motor_expansao/core/constants.py` — re-exporta os settings como aliases estáveis e,
  IMPORTANTE, define `PESOS_HEX_SCORE_ESTRUTURAL = {"renda_per_capita": 0.40,
  "populacao_proxy": 0.60}` — esta é a fonte canônica dos pesos `{renda:0.40, pop:0.60}` que
  o manifesto deve registrar. Preferir ler daqui (mapear renda←renda_per_capita,
  pop←populacao_proxy) a hardcodear 0.40/0.60.
- `streamlit_app.py` — entrada do dashboard. `main()` termina por volta da linha 556 (após o
  bloco `if active_tab == ...`). Ponto de inserção do rodapé read-only é o final de `main()`.
  `ULTRA_PATH = Path(__file__).resolve().parent / "data" / "ultra" / "Ultra.csv"` (linha 185)
  é a referência canônica em código ao caminho do `Ultra.csv` para o sha256.
- (vintage IBGE) A constante de vintage é a string `"censo_2022"`, usada como
  `data_referencia_ibge` em `hex_enrichment.py` (linhas 109, 605) e default em
  `fase1_bi_exports.py` (`data_referencia_ibge`, default `"censo_2022"`, linha ~297-301). O
  manifesto deve registrar `ibge_vintage = "censo_2022"` (Planner decide se lê do dataframe
  `data_referencia_ibge` ou de uma constante; recomendado: constante/derivar do dataset, não
  inventar novo valor).

## Arquivos que podem ser alterados
- `src/motor_expansao/pipelines/m1/fase1_bi_exports.py`
- `src/motor_expansao/pipelines/m1/provenance.py` (NOVO, opcional — a critério do Planner)
- `data/outputs/_manifest.json` (GERADO pelo pipeline; não é editado à mão)
- Componente de rodapé no dashboard: `streamlit_app.py` e/ou
  `src/motor_expansao/dashboard/components.py` / `pages.py` (helper de render read-only)
- `tests/unit/test_manifest.py` (NOVO)
- Arquivos de processo do ciclo: `tasks/current_task.md`, `tasks/backlog.md`,
  `tasks/completed.md`, `context/handoff.md`, `context/handoff/` (commit por path).

## Critérios de aceite
- `data/outputs/_manifest.json` é gerado ao final do pipeline e contém, no mínimo:
  - `ibge_vintage` (= `"censo_2022"`)
  - `ultra_csv_sha256` (sha256 do conteúdo de `data/ultra/Ultra.csv`; comportamento definido
    e testável quando o arquivo está ausente — ex.: `null` ou marcador explícito)
  - `code_commit` (hash do commit corrente; comportamento definido quando git indisponível)
  - `generated_at` (timestamp ISO da geração)
  - `h3_resolution` (= 7, de `settings.H3_RESOLUTION`)
  - `pesos` = `{"renda": 0.40, "pop": 0.60}` (de `PESOS_HEX_SCORE_ESTRUTURAL`)
  - `dist_min_ultra_km` (= 1.0, de `settings.DIST_MIN_ULTRA_KM`)
  - `renda_min` (= 4500.0, de `settings.RENDA_MIN`)
- O dashboard exibe a proveniência (read-only) em algum ponto visível (rodapé/aba/expander).
- `pytest -q tests/unit/test_manifest.py` passa (presença do arquivo + schema/valores).
- PROVA DE NÃO-MUTAÇÃO: sha256 dos parquets M1 `brasil_priorizados.parquet`,
  `brasil_estrutural.parquet` e `hexagonos_*_dashboard.parquet` IDÊNTICO antes e depois de
  rodar o pipeline com a feature. Qualquer hash diferente → REPROVAR.
- Suíte completa permanece verde (baseline atual: `532 passed, 1 skipped`).

## Criticidade classificada
crítica

> ALERTA EXPLÍCITO (override do orquestrador): embora o backlog marque "Alta", este bloco
> menciona os PESOS DO SCORE (`{renda:0.40, pop:0.60}`) e toca o pipeline que gera os
> ARTEFATOS OFICIAIS DO M1 (`fase1_bi_exports.py`). Pela regra inviolável do CLAUDE.md /
> run-cycle, isso obriga classificação **CRÍTICA**, não Alta. A esteira exige APROVAÇÃO
> HUMANA após o Planner. O manifesto apenas LÊ os pesos canônicos para registrá-los; não pode
> redefini-los nem alterar qualquer score.

## Esteira recomendada
Block Orchestrator → Planner → [aprovação humana] → Builder → QA

## Riscos identificados
- Acoplamento indevido: se a geração do manifesto for misturada ao cálculo/escrita do score,
  vira risco médio. Mitigação: passo FINAL isolado, executado só depois que todos os
  artefatos já estão em disco (idealmente em função/módulo próprio).
- Mutação acidental de artefato: qualquer reescrita dos parquets M1 dentro do novo passo é
  reprovação. Mitigação: o passo só LÊ (para sha256/parâmetros) e ESCREVE o JSON novo.
- Hardcode de pesos: duplicar `0.40/0.60` em vez de ler `PESOS_HEX_SCORE_ESTRUTURAL` cria
  fonte divergente. Mitigação: ler da constante canônica e mapear chaves para `renda`/`pop`.
- Não-determinismo do `generated_at` e do `code_commit` quebrando testes. Mitigação: o teste
  deve validar presença/tipo/formato, não valores literais voláteis; campos voláteis
  isolados do schema fixo.
- `Ultra.csv` é gitignored / pode estar ausente em CI. Mitigação: definir e testar o
  comportamento de `ultra_csv_sha256` quando o arquivo não existe.
- Encoding/escrita do JSON em Windows (CRLF/UTF-8): garantir `utf-8` e novo arquivo sem
  poluir os contratos CSV existentes (`sep=";"`, `utf-8-sig` é só para os CSVs do projeto, não
  para o JSON).

## Guardrails ativos
- (CLAUDE.md §3/§5) Guardrail permanente: visualizações, análise radial e interações de mapa
  NÃO podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira,
  plano curto prazo, plano de domínio ou artefatos oficiais do M1 sem aprovação explícita.
- (CLAUDE.md §1) Nenhuma trilha paralela pode alterar o M1 sem aprovação explícita.
- (CLAUDE.md §2) Tratar `config.py`, `CLAUDE.md` e `PRD.md` como fontes canônicas de
  parâmetros e guardrails; ler o repositório real antes de editar.
- (CLAUDE.md §2) Toda mudança relevante entra com teste; nenhum PR sobe com CI quebrado.
- NÃO-MUTAÇÃO POR HASH (guardrail específico do bloco): QA deve verificar que os Parquets M1
  (`brasil_priorizados`, `brasil_estrutural`, `hexagonos_*_dashboard`) têm sha256 IDÊNTICO
  antes e depois. Se algum hash mudar → REPROVAR. Só foi ADICIONADO um manifesto.
- MANIFESTO AO LADO, NUNCA DENTRO: o `_manifest.json` é arquivo separado em
  `data/outputs/`; jamais um campo/coluna dentro do conteúdo de scoring de qualquer artefato.
- Commit por path (current_task): NUNCA `git add -A`; nunca arrastar `PRD.md` ou edições não
  relacionadas. Branch isolado `ciclo/BLK-OPS-03`.
- Este ciclo NÃO altera a orquestração → dry-run 6.c NÃO dispara.
