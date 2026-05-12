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
- As mudancas do ciclo estao no branch `codex-dashboard-m1-streamlit` e ainda nao foram commitadas nem mescladas em `main`.
- Artefatos Parquet existentes foram gerados com pesos antigos (renda=0.60, pop=0.40); novos pesos (renda=0.40, pop=0.60) aprovados em 2026-04-24 ainda nao foram aplicados.

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

### Bloco 1 - Commit e abertura de PR de handoff [ ]
**Objetivo:** persistir todas as mudancas do ciclo anterior no git e abrir PR para revisao da equipe.

Passos:
1. Rodar `git status --short` e listar arquivos modificados/nao-rastreados.
2. Stagear apenas os arquivos do ciclo — excluir `data/`, caches, outputs pesados e qualquer arquivo que o `.gitignore` ja cobre. Usar `git add <arquivo>` por nome, nunca `git add -A`.
3. Criar commit descritivo resumindo o ciclo de handoff/deploy.
4. Abrir PR de `codex-dashboard-m1-streamlit` -> `main` via `gh pr create` com titulo curto e descricao dos blocos concluidos.
5. Confirmar que o CI do GitHub Actions foi disparado.

Validacao minima:
- `git status --short` sem arquivos esquecidos relevantes.
- PR aberto com link retornado.
- Suite rapida passando localmente antes do push: `python -m pytest -q test_streamlit_app.py test_carteira_plano_nacional.py`.

Observacoes: aguardar aprovacao explicita do usuario antes de executar `git push` e `gh pr create`; mostrar diff e draft da mensagem de PR antes de confirmar.

---

### Bloco 2 - Recalculo M1 com novos pesos (renda=0.40 / pop=0.60) [ ]
**Objetivo:** aplicar os pesos aprovados pela diretoria em 2026-04-24 e regenerar os artefatos oficiais.

**ATENCAO:** este bloco sobrescreve `brasil_estrutural.parquet`, `brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet` e outputs do M1. Executar somente com aprovacao explicita do usuario.

Passos:
1. Ler `config.py` e `hex_enrichment.py` para confirmar os pesos atuais e onde sao aplicados.
2. Atualizar os pesos para `renda=0.40` e `pop=0.60` se ainda estiverem nos valores antigos.
3. Rodar `python hex_enrichment.py --brasil`.
4. Rodar `python fase1_bi_exports.py`.
5. Validar campos auditaveis nos Parquets gerados: `renda_pct_nacional`, `pop_pct_nacional`, `hex_score_estrutural`, `ajuste_executivo`, `score_priorizacao`, `score_oficial`, `score_oficial_nome`, `score_percentil_nacional`.
6. Rodar suite do M1: `python -m pytest test_hex_enrichment_brasil.py test_fase1_bi_exports.py -v`.
7. Confirmar que `score_priorizacao` continua sendo o score oficial e que nenhum artefato paralelo foi alterado.

Validacao minima:
- Suite do M1 passando sem falhas.
- Parquets oficiais regenerados com pesos corretos verificados por inspecao de sample.
- Atualizar `CLAUDE.md` removendo o aviso de pesos antigos se o recalculo for bem-sucedido.

---

### Bloco 3 - Preparacao e checklist de entrega VPS para a equipe [ ]
**Objetivo:** garantir que a equipe consiga replicar o deploy sem intervencao adicional.

Passos:
1. Rodar `python scripts/check_artifacts.py` e confirmar os 4 Parquets criticos presentes em `data/outputs/`.
2. Revisar `docs/deploy_vps_streamlit.md` e `docs/handoff_repositorio.md` — completar qualquer lacuna de instrucao que impeca a equipe de subir o container sem ajuda.
3. Verificar se `Dockerfile.streamlit` e `docker-compose.prod.yml` fazem referencia correta ao volume de `data/outputs/` e se o `HEALTHCHECK` esta configurado.
4. Documentar em `docs/handoff_repositorio.md` o procedimento de rollback (parar container, substituir Parquets, reiniciar).
5. Gerar lista final de arquivos que a equipe deve receber fora do git (os 4 Parquets + `.env` preenchido) e registrar no proprio doc.

Validacao minima:
- `check_artifacts.py` retorna todos os criticos presentes.
- `docs/handoff_repositorio.md` descreve passo a passo suficiente para deploy sem dependencia de quem escreveu.
- Nenhum secret ou dado bruto referenciado dentro do `Dockerfile.streamlit` ou do compose.

## Backlog do proximo ciclo
- Hardening operacional da VPS: HTTPS/proxy reverso, autenticacao ou VPN, monitoramento de uptime.
- Limpeza de artefatos temporarios e permissoes de diretorios de teste pendentes.
- Avaliar se camada de mercado por hexagono avanca para novo bloco analitico apos o PR de handoff ser mesclado.
