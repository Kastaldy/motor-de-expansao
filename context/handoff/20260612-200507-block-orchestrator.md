# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-FIX-12 — Logos das concorrentes não aparecem no PDF do Relatório (API/bot; verificar dashboard)**

O PDF da página **Concorrentes** sai sem logos nos pins quando gerado pela API/bot. O dashboard
Streamlit gera o PDF COM logos (correto). Causa raiz confirmada por leitura de código: 3 causas
somadas no caminho da API; dashboard não sofre o bug.

---

## Objetivo
Fazer o PDF do Relatório Pontual Censitário (página Concorrentes) exibir a logo correta por rede
tanto na API/bot quanto no dashboard, adicionando o volume `concorrentes` e a env
`API_COMPETITORS_LOGOS_DIR` ao serviço `api` no compose, e garantindo que o default de
`settings.competitors_logos_dir` não resolva para `site-packages/data/Logos`.

---

## Diagnóstico confirmado (leitura de código real)

### Causa 1 — Volume ausente no serviço `api` (compose)
`docker-compose.prod.yml` serviço `api` monta apenas:
```
/opt/motor-expansao/data/outputs:/app/data/outputs:ro
/opt/motor-expansao/data/ibge:/app/data/ibge:ro
/opt/motor-expansao/data/staging:/app/data/staging:ro
/opt/motor-expansao/data/ultra:/app/data/ultra:ro
```
O diretório `/opt/motor-expansao/concorrentes` (que o serviço `streamlit` monta como
`/app/concorrentes:ro`) **não está montado no serviço `api`**.

### Causa 2 — Env `API_COMPETITORS_LOGOS_DIR` ausente no compose
O serviço `api` define `API_CENSO_GEO_DIR`, `API_IBGE_DIR`, `API_STAGING_DIR`, `API_ULTRA_DIR`,
mas **não define `API_COMPETITORS_LOGOS_DIR`**.

### Causa 3 — Default de `settings.competitors_logos_dir` resolve para path inexistente
`src/motor_expansao/api/settings.py` linha 45:
```python
competitors_logos_dir: Path = _DATA_DIR / "Logos"
```
onde `_DATA_DIR = Path(__file__).resolve().parents[3] / "data"`. Em produção (pacote
não-editável instalado no `site-packages`), `parents[3]` aponta para dentro do `site-packages`
e não para `/app/data`. Resultado: o default é `site-packages/data/Logos`, diretório inexistente.

### Cadeia de falha em `service.py` (`gerar_pdf_ponto`)
```python
logos_dir = (
    settings.competitors_logos_dir
    if Path(settings.competitors_logos_dir).is_dir()
    else None
)
...
render_mapas_censitarios_combinados(..., logos_dir=logos_dir, ...)
```
Com `logos_dir=None`, `render_mapas_censitarios_combinados` pula o `preload_logos` → `_ICON_CACHE`
fica vazio → `_render_pin_tile` cai no fallback de sigla para todas as redes.

### Por que o dashboard funciona (o bug NÃO afeta o Streamlit)
`streamlit_app.py` linha 206:
```python
preload_logos(CONCORRENTES_DIR, ultra_dir=ULTRA_PATH.parent)
```
onde `CONCORRENTES_DIR = Path(__file__).resolve().parent / "concorrentes"`. No container
Streamlit, `/app/concorrentes` é montado via volume. O `preload_logos` roda no boot e popula o
`_ICON_CACHE` global do módulo. A chamada subsequente em `pages.py` (linha 2586) a
`render_mapas_censitarios_combinados` **sem** `logos_dir` ainda usa o `_ICON_CACHE` já populado
(módulo-global, mesmo processo). PDF do dashboard: logos corretos.

A chamada em `pages.py` `render_relatorio_pontual_censitario` (linha 2586) NÃO passa `logos_dir`
a `render_mapas_censitarios_combinados` — depende do `_ICON_CACHE` global já preenchido pelo boot.
Isso é correto para o Streamlit (mesmo processo) mas não seria suficiente para a API (processo
separado, boot diferente). A API faz corretamente: passa `logos_dir` explicitamente em
`service.gerar_pdf_ponto` — porém o dir não existe na imagem/container por falta do volume.

### Localização dos assets de logo
- **No repositório local:** `concorrentes/logo_<rede>.png` (gitignored via `concorrentes/` no
  `.gitignore`; não vai na imagem Docker).
- **No VPS:** `/opt/motor-expansao/concorrentes/logo_*.png` — existente no host (o serviço
  `streamlit` já o monta com sucesso).
- **Nome esperado por `COMPETITOR_LOGO_FILES`:** `logo_<rede>.png` com underscore. Há aliases
  legacy presentes no repo — `preload_logos` degrada graciosamente para sigla quando o nome não
  casa.

---

## Escopo permitido
- Adicionar volume `concorrentes` (`:ro`) ao serviço `api` em `docker-compose.prod.yml`, apontando
  `/opt/motor-expansao/concorrentes:/app/concorrentes:ro`.
- Adicionar env `API_COMPETITORS_LOGOS_DIR=/app/concorrentes` ao serviço `api` em
  `docker-compose.prod.yml`.
- Corrigir o default de `settings.competitors_logos_dir` em `src/motor_expansao/api/settings.py`
  para ser mais robusto (ex.: usar `Optional[Path] = None` como sentinel, com guard em
  `service.py`), para que o fallback seja acionado corretamente sem depender apenas de env.
- Atualizar `docs/api_geoespacial_deploy.md` para documentar o volume e a env na seção de deploy.
- Adicionar/adaptar teste de integração confirmando que `logos_dir` válido resulta em
  `_ICON_CACHE` populado e `logos_dir=None` não quebra.

## Fora de escopo
- `score_priorizacao`, `hex_score_estrutural`, pesos, artefatos oficiais do M1 (READ-ONLY
  absoluto — §5 guardrail permanente).
- Método de interseção `setor_censitario_intersecao_area_1p5km` e raio 1.5 km (INTOCADOS).
- Qualquer comando de execução no servidor VPS — operação de deploy (`docker compose up`, `scp`,
  etc.) é **exclusivamente responsabilidade do humano** (§6 GUARDRAIL VPS); o ciclo entrega
  somente o código/config versionável.
- Modificar o comportamento do dashboard Streamlit — ele funciona corretamente.
- Criar novos assets de logo (os PNGs existentes em `concorrentes/` são suficientes).
- Alterar o nome/estrutura do diretório de logos no host.

---

## Arquivos que devem ser lidos
- `docker-compose.prod.yml` — configuração de volumes e envs dos serviços.
- `src/motor_expansao/api/settings.py` — definição de `competitors_logos_dir` e default.
- `src/motor_expansao/api/service.py` — uso de `settings.competitors_logos_dir` em
  `gerar_pdf_ponto` (linhas 273-286).
- `src/motor_expansao/dashboard/competitors.py` — `preload_logos`, `COMPETITOR_LOGO_FILES`,
  `_ICON_CACHE`, `_render_pin_tile`.
- `src/motor_expansao/dashboard/censo_map.py` — assinatura de
  `render_mapas_censitarios_combinados` (parâmetro `logos_dir`, linhas 643-684).
- `streamlit_app.py` — chamada de `preload_logos` no boot (linha 206) e `CONCORRENTES_DIR`
  (linha 187).
- `docs/api_geoespacial_deploy.md` — documentação de envs e volumes.

## Arquivos que podem ser alterados
- `docker-compose.prod.yml` — adicionar volume `concorrentes` e env `API_COMPETITORS_LOGOS_DIR`
  ao serviço `api`.
- `src/motor_expansao/api/settings.py` — corrigir default de `competitors_logos_dir` para
  `Optional[Path] = None` (ou equivalente seguro).
- `src/motor_expansao/api/service.py` — ajustar guard de `logos_dir` se o tipo do campo mudar
  para `Optional[Path]`.
- `docs/api_geoespacial_deploy.md` — incluir volume `concorrentes` e env na seção de volumes de
  deploy.
- `tests/` — adicionar/adaptar teste para o caminho de `logos_dir` válido vs `None`.

**Não devem ser alterados:**
- `src/motor_expansao/dashboard/competitors.py` — lógica correta; não mexer.
- `src/motor_expansao/dashboard/censo_map.py` — assinatura já aceita `logos_dir: Path | None`.
- `src/motor_expansao/dashboard/pages.py` — dashboard correto; não mexer.
- `streamlit_app.py` — dashboard correto; não mexer.
- Quaisquer artefatos M1 ou scripts de pipeline.

---

## Critérios de aceite
1. `docker-compose.prod.yml`: serviço `api` tem o volume
   `/opt/motor-expansao/concorrentes:/app/concorrentes:ro` e a env
   `API_COMPETITORS_LOGOS_DIR=/app/concorrentes`.
2. `settings.py`: `competitors_logos_dir` tem default que não resolve para `site-packages/`
   (ex.: `Optional[Path] = None` ou path vazio, com guard no `service.py`).
3. Teste automatizado: com `logos_dir` apontando para diretório de fixtures com `logo_smart_fit.png`,
   `preload_logos` popula `_ICON_CACHE["smart_fit"]`; com `logos_dir=None`, `_ICON_CACHE` fica
   sem a chave e nenhuma exceção é lançada.
4. `pytest -q` (suite completa) passa sem regressões.
5. `ruff check` e `mypy` limpos nos arquivos alterados.
6. `docs/api_geoespacial_deploy.md` documenta o volume `concorrentes` e a env
   `API_COMPETITORS_LOGOS_DIR` na seção de volumes de deploy.

---

## Criticidade classificada
**Média** — qualidade do entregável ao cliente (PDF sem logos); não toca M1 nem score; operação
READ-ONLY. A correção de `settings.py` é análoga ao bug de data dirs já resolvido (BLK-API-06,
memória do projeto).

---

## Esteira recomendada
Block Orchestrator → **Planner** → Builder → QA

---

## Riscos identificados
- **Deploy operacional fora do ciclo:** a adição do volume no compose é código versionável (este
  ciclo); a execução no VPS (`docker compose pull && docker compose up -d --no-deps api`) é
  responsabilidade humana pós-merge. Garantir que `/opt/motor-expansao/concorrentes` existe no
  host antes do `up` (o Streamlit já o usa, então existe).
- **Alias de nomes de arquivo:** alguns logos têm nomes com underscores vs sem (ex.:
  `logo_aera_pilates.png` vs `logo_aerapilates.png`). `preload_logos` degrada graciosamente;
  não é bloqueante para o fix principal.
- **`_ICON_CACHE` é módulo-global compartilhado:** em desenvolvimento local onde API e dashboard
  rodam no mesmo processo pode haver interferência. Em produção são containers separados — sem
  risco.
- **Tipo de `competitors_logos_dir`:** ao mudar para `Optional[Path] = None`, verificar todos os
  usos em `service.py` para não introduzir `TypeError`. Preferir guard explícito:
  `if settings.competitors_logos_dir and Path(settings.competitors_logos_dir).is_dir()`.

---

## Guardrails ativos
- **§5 guardrail permanente:** visualizações, análise radial e interações de mapa não podem
  recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo,
  plano de domínio ou artefatos oficiais do M1. Esta fix é exclusivamente de camada visual (logos
  nos pins do PDF).
- **§6 GUARDRAIL VPS ABSOLUTO:** nenhum comando no servidor VPS sem confirmação humana explícita
  por comando individual. O ciclo entrega somente código/config versionável; operações no VPS
  são orientação para o humano, não ação do agente.
- **§2 regra canônica:** assets de branding (`concorrentes/logo_*.png`) são gitignored e nunca
  versionados — o ciclo apenas configura onde o container os encontra em runtime via volume.
- **M1 READ-ONLY:** `src/motor_expansao/pipelines/` e artefatos em `data/staging/` e
  `data/outputs/` permanecem intocados.
