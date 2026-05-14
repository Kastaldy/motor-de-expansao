# Fora da primeira fase

Arquivos separados da raiz em 2026-05-14 porque nao entram no ciclo inicial de
handoff/Streamlit offline/M1. Eles foram preservados para reativacao futura, sem
ficarem misturados com os entrypoints oficiais da fase atual.

## Organizacao

- `m2_m3_imobiliario/`: scrapers, geocoding, qualificacao de imoveis, pipeline diario e score consolidado M2/M3.
- `api_postgis/`: API FastAPI, modelos SQLAlchemy/PostGIS, migracao inicial e compose legado de desenvolvimento.
- `pesquisa/`: pesquisas, tese/plano e notas exploratorias.
- `agentes/`: prompt operacional antigo para agentes.
- `powerbi/`: gerador e teste do dashboard Power BI legado.
- `dados/`: planilhas soltas que nao entram no deploy inicial.
- `tests/`: testes dos modulos arquivados; nao entram na coleta ativa porque `pyproject.toml` coleta apenas `tests/`.

Para reativar qualquer bloco, revisar imports e caminhos antes de voltar arquivos
para a raiz ou para `src/`.
