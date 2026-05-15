# PRD - Guia Operacional para Agentes de IA
**Projeto:** Motor de expansao - Ultra Academia
**Ultima atualizacao:** 2026-05-15
**Ciclo ativo:** Handoff, refatoracao segura e preparacao VPS fechados

## Instrucoes obrigatorias
1. Ler `CLAUDE.md` antes de qualquer acao.
2. Tratar `CLAUDE.md`, `config.py` e este PRD como fontes de verdade operacional.
3. Executar apenas o proximo bloco cujo cabecalho esteja com `[ ]`.
4. Antes de editar, ler os arquivos reais envolvidos e rodar `git status --short`.
5. Nao reverter nem sobrescrever mudancas existentes sem aprovacao explicita.
6. Atualizar `CLAUDE.md` e `PRD.md` se mudar regra, target, semantica de coluna, fluxo ou decisao relevante.
7. Se houver ambiguidade entre codigo e documentacao, corrigir primeiro a documentacao e depois o codigo.
8. Nao encerrar bloco sem editar arquivo, registrar observacoes e rodar validacao minima.
9. Tentar manter `CLAUDE.md` e `PRD.md` com no maximo `200` linhas.
10. Quando um ciclo fechar, consolidar o historico em `Estado atual` e substituir blocos antigos pelo backlog ativo.

## Estado atual
- Ciclo de handoff/deploy e refatoracao segura concluido em 2026-05-14.
- Repositorio preparado para equipe: Streamlit offline, Docker de producao e docs de VPS mantidos.
- M1 oficial recalculado em 2026-05-15 para refletir `populacao_proxy = pop_total`; pesos `renda=0.40` e `pop=0.60` seguem inalterados.
- Camada censitaria completa (todos os 3 parquets: core GO/RJ/SP, piloto expandido DF/MG/RS e nacional 21 UFs) regenerada em 2026-05-15 com `v0001` corrigido; toda a cadeia rematerializada: hibrido (780 hexes elegiveis), carteira (4.892 hexes, 1.103 municipios) e plano (267 hexes, 100 municipios).
- Branch historico `codex-dashboard-m1-streamlit` permanece apenas como historico; mudancas anteriores foram promovidas para `main` em 2026-05-14.
- Estrutura nova: pacote interno em `src/motor_expansao/` com `dashboard`, `core`, `data` e `pipelines/m1`.
- Entrypoints legados preservados na raiz: `streamlit_app.py`, `base_h3_brasil.py`, `hex_enrichment.py`, `fase1_bi_exports.py`.
- Arquivos fora do deploy inicial foram concentrados em `fora_primeira_fase/`: API/PostGIS, M2/M3, pesquisas, Power BI e testes associados.
- Testes reorganizados em `tests/unit/`, `tests/integration/` e `tests/contracts/`; coleta oficial em `pyproject.toml`.
- Diretorios temporarios antigos em `fixtures/` seguem com alguns avisos de permissao no `git status`; nao foram removidos sem aprovacao.

## Artefatos minimos do dashboard
Manter em `data/outputs/` no ambiente da equipe ou montados como volume na VPS:

| arquivo | uso |
| --- | --- |
| `hexagonos_brasil_dashboard.parquet` | base oficial M1, KPIs, ranking e mapa executivo |
| `oportunidades_expansao_hibrido.parquet` | enriquecimento hibrido/censitario e filtros combinados |
| `carteira_expansao_acionavel.parquet` | aba de carteira operacional |
| `plano_expansao_curto_prazo.parquet` | aba de plano curto prazo |

Validar com:

```bash
python scripts/check_artifacts.py
```

## Comandos de referencia

Setup local:
```bash
python -m pip install -e ".[dev]"
copy .env.example .env
python -m streamlit run streamlit_app.py
```

Suite rapida:
```bash
python -m pytest -q tests/integration/test_streamlit_app.py tests/integration/test_carteira_plano_nacional.py
python -c "import streamlit_app; print('ok')"
```

Suite M1:
```bash
python -m pytest -q tests/integration/test_base_h3_brasil.py tests/integration/test_hex_enrichment_brasil.py tests/integration/test_fase1_bi_exports.py tests/contracts/test_fontes_gratuitas.py
```

Suite completa:
```bash
python -m pytest -q
```

Deploy VPS:
```bash
python scripts/check_artifacts.py
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
curl -fsS http://127.0.0.1:8501/_stcore/health
```

Recalculo analitico M1, fora do deploy Streamlit inicial:
```bash
python base_h3_brasil.py
python hex_enrichment.py --brasil
python fase1_bi_exports.py
```

## Docs de referencia
- `README.md`: quickstart, testes, deploy e mapa de docs.
- `docs/handoff_repositorio.md`: contrato de handoff e checklist para a equipe.
- `docs/artefatos_dados.md`: manifesto de dados e politica de versionamento.
- `docs/deploy_vps_streamlit.md`: runbook Streamlit/Docker para VPS.
- `docs/streamlit_dashboard_m1.md`: governanca e uso do dashboard.
- `docs/modelo_mercado_hexagonos.md`: contrato tecnico da camada de mercado.

## Blocos concluidos

### Ciclo anterior - Handoff, refatoracao segura e preparacao VPS [x]
**Concluido:** 2026-05-14
- Blocos 1 a 6 fechados: diagnostico, higiene segura, pacote interno, extracao do dashboard, isolamento do M1, pipelines/testes e handoff.
- Validacao final registrada: `scripts/check_artifacts.py`, suite completa com `215 passed, 4 warnings` e import smoke dos entrypoints.
- Historico operacional consolidado em `Estado atual`; detalhes tecnicos permanecem no git e nos docs de referencia.

## Blocos pendentes

Nenhum bloco pendente no momento.

### Bloco 8 - Regenerar camada censitaria nacional com v0001 corrigido [x]
**Concluido:** 2026-05-15

**Observacoes:**
- `nacional_completo.parquet` (21 UFs) regenerado com `v0001`; cobertura 84-100% dos totais IBGE 2022 por UF (era ~44% com v0002).
- 9/21 UFs com gates aprovados (qualidade A/B); 11 UFs com qualidade C filtradas automaticamente pelo hibrido.
- Cadeia completa reencadeada: `fase_a_nacional` -> `modelo_hibrido` -> Bloco 3 -> Bloco 4 -> `gerar_carteira` -> `gerar_plano`.
- Hexes elegiveis no hibrido: 618 (eram 477 apenas com piloto v0001, eram 185 com v0002 total).
- Carteira: 5.035 hexes, 1.103 municipios, 27 UFs; granular censitario em 122 municipios.
- Plano curto prazo: 265 hexes, 93 municipios, 27 UFs; 20 Estrategicos, 30 Alta, 215 Taticos.
- Suite: 33/33 passed (test_pop_censo_v0001, test_modelo_hibrido_expansao, test_modelo_mercado_hexagonos).

### Bloco 7 - Auditoria de populacao censitaria por hex [x]
**Concluido:** 2026-05-15

**Observacoes:**
- Root cause confirmado: `v0002` (Total de Domicilios) era usado no lugar de `v0001` (Total de pessoas); undercount sistematico de ~2.3x em `pop_total_setor_2022` em todas as UFs piloto.
- Fix em `fase_a_censo2022_setores.py`: `POP_V002_CANDIDATES` agora prioriza `v0001`; `ler_basico_nacional_uf` le `v0001` para populacao total e `v0007` para domicilios.
- `spatial_join_area_weighted` confirmado correto: `gpd.overlay + groupby.agg("sum")` soma todos os setores intersectantes; nao havia bug de agregacao.
- Cobertura apos correcao: SP 98.6%, GO 97.5%, RJ 87.6% dos totais IBGE 2022.
- Hexes elegiveis no hibrido: 477 (eram 185) — piloto GO/SP/RJ/MG/DF/RS.
- Teste de regressao adicionado: `tests/unit/test_pop_censo_v0001.py` (6 casos); 6/6 passing.

### Ciclo dashboard M1 — Blocos 1 a 6 [x]
**Concluido:** 2026-05-14
- Regua 5k, busca por coordenada, visuais pop-cut, pins Ultra, documentacao e concorrentes/logos; detalhes em `CLAUDE.md` secao 5 e git log.

## Backlog posterior
- Hardening operacional da VPS: HTTPS/proxy reverso, autenticacao ou VPN, monitoramento de uptime.
- Limpeza assistida dos diretorios temporarios antigos com permissao negada em `fixtures/`.
- Avaliar regeneracao nacional da camada de mercado apos estabilizar a regua de `5.000` habitantes.
