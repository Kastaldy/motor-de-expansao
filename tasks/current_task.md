# Current Task

## Bloco atual

ID: BLK-20260527-01
Nome: Deploy Hostinger KVM4 + Caddy + Authelia
Status: aprovado — pronto para fechamento do ciclo
Tipo: operação / infraestrutura
Criticidade: estratégica
Esteira: Block Orchestrator → Planner → [aprovação humana] → Builder → QA → Builder (correção) → QA
Skill atual: QA re-run (concluído — APROVADO)
Próxima Skill: Fechamento do ciclo

## Objetivo

Implementar os arquivos de infraestrutura para deploy do dashboard Streamlit Motor de Expansão
na Hostinger KVM4, com autenticação Authelia (tela de login com formulário, 2FA opcional,
100% self-hosted) via Caddy reverse proxy com TLS automático.

## O que foi implementado (Builder)

- `.dockerignore` reescrito
- `docker-compose.prod.yml` reescrito (streamlit + caddy + authelia)
- `Caddyfile` criado (template com placeholder)
- `authelia/configuration.yml` criado
- `authelia/users_database.yml` criado (template com placeholders)
- `.env.example` atualizado com segredos Authelia
- `.gitignore` atualizado com entradas de deploy
- `docs/deploy_plan.md` criado

## Validações (Builder)

- pytest tests/integration/test_streamlit_app.py: 147 passed
- import streamlit_app: ok

## Pendências antes do deploy (ações do usuário)

1. Contratar Hostinger KVM4 e anotar IP + domínio
2. Criar registros DNS A para dashboard.* e auth.*
3. Substituir SEU_DOMINIO.COM.BR em Caddyfile e authelia/configuration.yml
4. Gerar hashes reais dos usuários e preencher authelia/users_database.yml
5. Copiar .env.example para .env e preencher segredos Authelia
6. Transferir data/outputs/ e data/ultra/ via rsync para o servidor

## Resultado QA #1 (2026-05-27)

REPROVADO. Bloqueadores identificados: server.host/port deprecado, /api/verify deprecado, imagem latest sem pin, depends_on ausente no caddy. Problema médio: authelia/configuration.yml fora do .gitignore, inconsistência root@ no deploy_plan.md.

## Resultado QA #2 — Re-run (2026-05-27)

APROVADO. Todos os 5 bloqueadores corrigidos com exatidão. Ambos os problemas médios corrigidos. Nenhum arquivo Python alterado. Nenhum artefato M1 tocado. 147 testes passam (referência Builder). Ver context/handoff.md para detalhes completos.

## Próxima ação

Fechamento do ciclo BLK-20260527-01.
