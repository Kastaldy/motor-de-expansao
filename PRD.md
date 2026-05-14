# PRD - Guia Operacional para Agentes de IA
**Projeto:** Motor de expansao - Ultra Academia
**Ultima atualizacao:** 2026-05-12
**Ciclo ativo:** Commit de handoff, recalculo M1 e preparacao VPS

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

## Contexto do ciclo anterior
- Ciclo de handoff/deploy encerrado em 2026-05-12 (Blocos 1-6 concluidos).
- Repositorio preparado para compartilhamento; dashboard Streamlit empacotado para VPS.
- Validacao final: 16 testes passando, `import streamlit_app ok`, smoke headless ok, `check_artifacts.py` com 4 criticos presentes.
- As mudancas do ciclo foram promovidas para `main` em 2026-05-14; o branch `codex-dashboard-m1-streamlit` permanece apenas como historico do ciclo.
- Artefatos Parquet regenerados em 2026-05-12 com pesos corretos (renda=0.40, pop=0.60); 18/18 testes passando.

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
python -m pytest -q test_streamlit_app.py test_carteira_plano_nacional.py
python -c "import streamlit_app; print('ok')"
```

Deploy VPS:
```bash
python scripts/check_artifacts.py
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
curl -fsS http://127.0.0.1:8501/_stcore/health
```

## Docs de referencia
- `README.md`: quickstart, testes, deploy e mapa de docs.
- `docs/handoff_repositorio.md`: contrato de handoff e checklist para a equipe.
- `docs/artefatos_dados.md`: manifesto de dados e politica de versionamento.
- `docs/deploy_vps_streamlit.md`: runbook Streamlit/Docker para VPS.
- `docs/streamlit_dashboard_m1.md`: governanca e uso do dashboard.
- `docs/modelo_mercado_hexagonos.md`: contrato tecnico da camada de mercado.

## Blocos

### Bloco 1 - Commit e abertura de PR de handoff [x]
**Objetivo:** persistir todas as mudancas do ciclo anterior no git e abrir PR para revisao da equipe.

**Concluido em 2026-05-12.**
- Commit `d4d1ae3` criado com 66 arquivos (16.111 insercoes).
- Branch `codex-dashboard-m1-streamlit` empurrada para `origin` e depois promovida para `main` em 2026-05-14.
- Suite rapida: 16 testes passando localmente.
- PR manual deixou de ser necessario porque a entrega foi consolidada diretamente na `main`.

---

### Bloco 2 - Recalculo M1 com novos pesos (renda=0.40 / pop=0.60) [x]
**Objetivo:** aplicar os pesos aprovados pela diretoria em 2026-04-24 e regenerar os artefatos oficiais.

**Concluido em 2026-05-12.**
- Pesos ja estavam corretos no codigo (`hex_enrichment.py` linhas 46-48); apenas o pipeline precisava ser re-executado.
- `hex_enrichment.py --brasil`: 27 UFs processadas, 1.532.645 hexagonos, max diff pesos = 0.0000.
- `fase1_bi_exports.py`: dashboard 1.532.645 hex, mapa sample 459.794 hex, 27 UFs.
- Suite M1: 18/18 testes passando.
- Todos os campos auditaveis confirmados: 5 em `brasil_estrutural.parquet`, 3 adicionais em `hexagonos_brasil_oportunidades.parquet`.
- `score_oficial_nome = 'score_priorizacao'` e `score_oficial == score_priorizacao` em 100% das linhas.
- `CLAUDE.md` atualizado: aviso de pesos antigos removido.

---

### Bloco 3 - Preparacao e checklist de entrega VPS para a equipe [x]
**Objetivo:** garantir que a equipe consiga replicar o deploy sem intervencao adicional.

**Concluido em 2026-05-12.**
- `check_artifacts.py`: 4 criticos OK (dashboard 47 MB, hibrido 67 MB, carteira 0,4 MB, plano 0,1 MB); staging opcional tambem presente.
- `Dockerfile.streamlit`: HEALTHCHECK configurado (`curl /_stcore/health`, interval 30s, start-period 45s); sem secrets; usuario nao-root.
- `docker-compose.prod.yml`: volume `./data/outputs:/app/data/outputs:ro` correto; HEALTHCHECK redundante configurado; sem credentials no compose.
- `docs/handoff_repositorio.md` atualizado com: (a) tabela de pacote de arquivos externos ao git (4 Parquets + `.env` + staging opcional); (b) secao de rollback com comandos passo a passo e recomendacao de backup.
- `docs/deploy_vps_streamlit.md` revisado — sem lacunas de instrucao identificadas.

## Backlog do proximo ciclo
- Hardening operacional da VPS: HTTPS/proxy reverso, autenticacao ou VPN, monitoramento de uptime.
- Limpeza de artefatos temporarios e permissoes de diretorios de teste pendentes.
- Avaliar se camada de mercado por hexagono avanca para novo bloco analitico apos o PR de handoff ser mesclado.
