# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Builder (criticidade baixa — sem Planner separado)

## Bloco refinado
**BLK-UI-10 — PoC de repaginação do dashboard: tema denso (baixo) + mapa Leaflet client-side (médio)**

Protótipo opt-in que demonstra dois ganhos do design de SPA estático (ex.: `NAO_ABRA/totalpass_final.html`):
1. **Fase A:** Layout denso de 3 painéis + tema visual coeso (Dark com identidade da Ultra).
2. **Fase B:** Mapa interativo Leaflet client-side via `st.components.v1.html` (dados embutidos, pan/zoom/clique sem round-trip).

Camada de visualização READ-ONLY sobre o M1. Produção (pydeck/abas) intacta e default.

## Objetivo
Entregar um protótipo navegável e testado que demonstre um layout denso coeso com identidade visual Ultra e um mapa client-side fluido, sem reescrever o motor de server-side (que roda o script a cada clique, 1,54 M hexes + malha censitária).

## Escopo permitido

### Fase A (esforço baixo — tema/layout)
- Criar novo arquivo `src/motor_expansao/dashboard/ui_proto.py` com página Streamlit opt-in (aba nova atrás de flag em `session_state`).
- Criar novo arquivo `src/motor_expansao/dashboard/ui_theme.py` com CSS injetado + helpers de tema (paleta, tipografia, componentes).
- Layout 3-painéis: faixa superior (KPIs/filtros) + painel esquerdo (contexto) + mapa (centro) + painel direito (detalhe).
- **Direção visual obrigatória** (decisão já tomada — o agente NÃO reinventa):
  - **Paleta:** Dark carvão-azulado (`--bg:#0b1016`, `--panel:#121a24`, `--line:#1f2c3a`) com turquesa Ultra (`--ultra:#1fd1c4`, acento único) + magenta só-concorrente (`--conc:#ff3d8b`); texto em cinza claro (`--text:#dce6f0`, `--muted:#7d97ad`).
  - **Tipografia:** Display/títulos = **Space Grotesk** (caráter técnico/cartográfico); corpo/UI = **IBM Plex Sans** (engenharia); dados (hex_id, lat/lng, scores) = **IBM Plex Mono** (mono é justificável — o dado é o subject).
  - **Assinatura:** Hexágono H3 como motivo memorável (recorte hexagonal sutil em KPI cards ou marcador hex em legenda); o resto fica quieto e disciplinado.
  - **Qualidade:** Contraste AA, responsivo até telas estreitas, foco de teclado visível, `prefers-reduced-motion` respeitado.
- **Anti-default checklist** (obrigatório responder no relatório do bloco antes de fechar Fase A):
  1. A paleta NÃO é o verde-ácido do totalpass nem cream+serif+terracota nem broadsheet hairline?
  2. O par tipográfico (Space Grotesk + IBM Plex Sans) não é o que eu usaria em qualquer projeto?
  3. Existe UMA assinatura (hexágono) e o resto é contido?
  4. Algum elemento decora sem significar? Se sim, corte.

### Fase B (esforço médio — mapa client-side)
- Mapa **Leaflet** renderizado via `st.components.v1.html` com CDN (sem `pip` novo).
- Recorte JSON **enxuto por UF/cidade** pré-agregado a partir dos parquets existentes (`data/outputs/hexagonos_dashboard_enriquecido/`, `data/staging/hexagonos_mercado_mapeado.parquet`, etc.).
- Pan/zoom/clique fluidos **sem rerun do servidor** (dados embutidos como arrays JS, igual ao totalpass).
- Geração de JSON determinística e reprodutível; armazenamento em `data/outputs/ui_proto/` (ou cache `data/cache/`) — nunca como artefato oficial do M1.
- Geração de **`data/reports/ui_poc_leaflet.md`:** relatório curto comparando peso percebido, responsividade e tempo de resposta vs. pydeck atual num pequeno recorte (ex.: 1 UF, ~100 hexes).

### Testes
- Smoke tests do render da página Fase A (verificar que o CSS injeta sem erro, nenhuma exceção de Streamlit).
- Teste de geração JSON (determinístico, estrutura esperada, sem PII, sem valores NaN infinitos).
- Teste de fallback quando parquet/UF não existe.
- Suíte verde ao fechar.

### Exposição da página opt-in
- A página PoC fica atrás de um **flag opt-in** — sugestão: env var `SHOW_UI_PROTO=true` OU checkbox `session_state["show_ui_proto"]` na sidebar de `pages.py` (sem alterar o render de produção).
- **NUNCA** substituir o render de produção (`pages.py` intacto byte-a-byte); o caminho pydeck/abas permanece default.

### Recorte JSON — especificação técnica
- **Estrutura esperada** (exemplo de 1 UF, ~100–500 hexes):
  ```json
  {
    "uf": "SP",
    "version": "ui_proto_v1",
    "timestamp": "2026-07-06T12:34:56Z",
    "hexagons": [
      {
        "hex_id": "87a8a...",
        "lat": -23.55,
        "lng": -46.63,
        "score_priorizacao": 78.5,
        "pop_total": 12500,
        "renda_per_capita": 5800,
        "score_oportunidade_residual": 45.0,
        "oferta_efetiva_disponivel": 2100,
        "sam_fitness_potencial": 3500
      },
      ...
    ]
  }
  ```
- **Geração:** passe por `json.dumps(..., separators=(',', ':'), sort_keys=True)` para determinismo.
- **Filtragem:** pode filtrar para pop ≥ 5.000 e score ≥ 20 (OPCIONAL, desde que reprodutível).
- **Sem PII:** nenhuma coluna com `endereco`, `nome_propriedade`, `owner`, etc.

### Dados consumidos (read-only)
- `data/outputs/hexagonos_dashboard_enriquecido/uf=*/` (particionado).
- `data/staging/hexagonos_mercado_mapeado.parquet` (residual fitness).
- `data/staging/brasil_priorizados.parquet` (para context — top-20% por UF).
- Constantes de RESIDUAL_SCORE_BANDS do `constants.py` (paleta de cores do mapa).

## Fora de escopo

- **NÃO tocar** `config.py`, `pipelines/m1/`, `*scoring*`, `components.py`, `pages.py` (caminho de produção).
- **NÃO recalcular** score, ranking, carteira, plano curto prazo, plano de domínio.
- **NÃO adicionar dependência nova** ao `pyproject.toml` (Leaflet/h3-js vêm de CDN no HTML embutido — padrão do totalpass).
- **NÃO persistir PII** (endereços, proprietários, coordenadas individuais).
- **NÃO substituir** o caminho de produção — PoC fica **opt-in atrás de flag**, nunca como default.
- **NÃO tocar** `Dockerfile.streamlit`, compose, Caddy, authelia, `.env`, `secrets/`, CI.
- **NÃO fazer deploy** ao VPS — bloco paralelo ao produto, reviável depois.
- Promover o PoC a default é **decisão humana** num bloco sucessor.

## Arquivos que devem ser lidos

(Todos já lidos pelo Block Orchestrator.)
- `/repo/CLAUDE.md` — contexto completo, especialmente §4 ("Camadas paralelas e estado atual") e §5 ("Ciclos concluidos").
- `/repo/tasks/current_task.md` — tarefa ativa (tiering de modelo, paths, guardrails).
- `/repo/tasks/backlog.md` linhas 1103–1205 — seção BLK-UI-10 completa, contexto, Direção Visual, anti-default checklist.
- `/repo/prompts/block_orchestrator.md` — formato e guardrails.

### Leitura durante implementação (Builder)
- `/repo/src/motor_expansao/dashboard/constants.py` — `RESIDUAL_SCORE_BANDS`, paleta de cores existente, faixa de 10 pontos.
- `/repo/src/motor_expansao/dashboard/pages.py` — estrutura de abas e carregamento de dados (para entender o fluxo, **NÃO alterar**).
- `/repo/src/motor_expansao/dashboard/data.py` — funções de carga de UF, helpers de análise (consumir, não tocar).

## Arquivos que podem ser alterados

- **Criar (novos):**
  - `src/motor_expansao/dashboard/ui_proto.py` — página Streamlit opt-in com layout 3-painéis, Fase A + Fase B.
  - `src/motor_expansao/dashboard/ui_theme.py` — CSS (puro string em `<style>`) + helpers de tema (cores, tipos, componentes de KPI cards).
  - `tests/unit/test_ui_proto.py` — smoke tests do render, geração JSON, fallback.
  - `data/reports/ui_poc_leaflet.md` — relatório de comparação peso/responsividade.

- **Modificar (existentes, APENAS para opt-in da página):**
  - `src/motor_expansao/dashboard/pages.py` — **APENAS** adicionar checkbox ou env check SIMPLES na sidebar para ativar `session_state["show_ui_proto"]`, e passar esse flag ao `main()` ou a uma função de roteamento. Nenhuma alteração no logic de pydeck, abas, componentes.
  - `tasks/current_task.md` — atualizar status ao final (Builder + QA).
  - `tasks/completed.md` — registrar bloco ao fechar.
  - `tasks/backlog.md` — mover linha do BLK-UI-10 para completado.
  - `context/handoff.md` — este arquivo, será sobrescrito ou deixado como referência do próximo ciclo.

- **Não alterar (gitignored, diretos de leitura):**
  - Parquets em `data/staging/`, `data/outputs/`.
  - Relatórios em `data/reports/` (só ler).

## Critérios de aceite

### Fase A (tema/layout)
- [ ] Página Streamlit `ui_proto.py` renderiza sem erro quando `SHOW_UI_PROTO=true` ou `session_state["show_ui_proto"]=True`.
- [ ] Layout 3-painéis (faixa superior + painel esquerdo + mapa/centro + painel direito) é visível e responsivo.
- [ ] **Direção visual aplicada corretamente:**
  - Paleta turquesa Ultra (`#1fd1c4`) como acento único + magenta (`#ff3d8b`) só-concorrente.
  - Tipografia Space Grotesk (display) + IBM Plex Sans (corpo) + IBM Plex Mono (dados).
  - Hexágono H3 como assinatura (recorte sutil em card de KPI OU marcador em legenda).
  - Contraste AA verificado, responsivo, foco de teclado visível, `prefers-reduced-motion` respeitado.
- [ ] **Anti-default checklist respondido no relatório** (4 perguntas explicitamente: paleta ≠ verde-ácido; tipografia deliberada; 1 assinatura + resto contido; sem decoração sem significado).
- [ ] Produção (pydeck/abas) **byte-a-byte preservada**, ainda default.
- [ ] Smoke test verde (render sem exceção).

### Fase B (mapa Leaflet)
- [ ] JSON recorte gerado para ≥1 UF (ex.: SP com ~200–500 hexes), armazenado em `data/outputs/ui_proto/` ou `data/cache/`.
- [ ] Mapa Leaflet carrega a partir do JSON (via `st.components.v1.html`), com pan/zoom/clique sem round-trip (não dispara rerun do Streamlit).
- [ ] Clique num hexágono exibe detalhe (ex.: hex_id, score, pop) em tooltip ou painel lateral do PoC (sem alterar o detalhe de produção).
- [ ] JSON geração é **determinística** (mesmos inputs → mesmo JSON byte-a-byte).
- [ ] Sem PII (nenhuma coluna proibida).
- [ ] Relatório `data/reports/ui_poc_leaflet.md` criado com comparação breve de peso percebido, responsividade e tempo de clique vs. pydeck atual.
- [ ] Teste de fallback: se UF não existe no cache, exibe mensagem clara (sem crashar).
- [ ] Teste verde.

### Guardrails de produção
- [ ] **READ-ONLY M1:** mtime dos 4 artefatos oficiais (brasil_estrutural, brasil_priorizados, hexagonos_brasil_oportunidades, hexagonos_brasil_dashboard) **inalterado**.
- [ ] **Zero recálculo** de score, pesos, carteira, plano.
- [ ] **Nenhuma dependência nova** em `pyproject.toml` (Leaflet/h3-js por CDN).
- [ ] **`loop_guard.py` verde:** zero acusação de toque em `config.py`, `pipelines/m1/`, `*scoring*`, artefatos M1, `deploy/`, `Dockerfile.{streamlit,api}`, `compose/`, `Caddy/`, `authelia/`, `.env`, `secrets/`, CI.
- [ ] **Suíte verde** (ruff+mypy limpos, pytest full verde).
- [ ] **Commit por path** (não git add -A): paths do `tasks/current_task.md` §4 (Paths do ciclo).

## Criticidade classificada
**Baixa** (visualização/PoC, READ-ONLY M1, não substitui produção, sem dependência nova, loop-safe).

## Esteira recomendada
1. **Block Orchestrator** (concluído — este handoff).
2. **Builder** (Fase A + Fase B, teste e relatório).
3. **QA** (suite full, ruff+mypy, smoke, guardrail M1, loop_guard.py).

Sem Planner separado (criticidade baixa). Gate humano é o loop_guard automático para loop-safe.

## Riscos identificados

1. **Leque tipográfico (Space Grotesk + IBM Plex Sans):** ambas são Google Fonts CDN, sem fallback system-font. **Mitigação:** importar via `@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap')` no CSS injetado; fallback gracioso (se não carregar, o browser usa sans-serif default do SO — não quebra o layout).

2. **Recorte JSON em cache local (`data/cache/`):** se voltar a rodar o código, o cache pode ficar desatualizado se os parquets forem recompostos. **Mitigação:** adicionar `timestamp` no JSON e comparar com mtime do parquet source; regenerar se defasado. Documentar a estratégia em `data/reports/ui_poc_leaflet.md`.

3. **Opt-in via `session_state` vs. env var:** se o Builder escolher `session_state`, o checkbox pode ficar "cola" na sidebar de Produção (efeito colateral visual). **Mitigação:** envolver o checkbox em `if st.secrets.get("ENABLE_EXPERIMENTAL_UI", False)` ou em um expander `"Experimental"` discreto.

4. **Integridade de dados no JSON:** se o recorte derivado perder hexes por erro de join, o mapa vai renderizar vazio e o usuário não verá feedback. **Mitigação:** adicionar log de "N hexes gerados para UF=XX" e comparação com contagem esperada; teste de fuzzy-match com brazionr hexes totais.

5. **Leaflet CDN indisponível:** se o CDN cair, o mapa não renderiza. **Mitigação:** fallback gracioso — se `st.components.v1.html` receber um objeto vazio, exibir botão "Tentar novamente" + mensagem "Mapa client-side indisponível; usando pydeck". Documentar em code.

6. **Conflito de CSS com Streamlit:** injetar CSS global pode coletar com temas/classes internas do Streamlit. **Mitigação:** prefixar todas as classes com `.ui-proto-` e usar seletores específicos (não `*` ou `body`); testar em light mode e dark mode.

## Guardrails ativos

(Do CLAUDE.md §2, §5, §6.1)

- **§2:** Não criar dependência de API ao vivo no dashboard de produção. (Mitigado: CDN é cache+fallback gracioso; Leaflet só carrega no PoC opt-in.)
- **§5:** Visualizações, análise radial e interações de mapa **não podem recalcular** nem alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano domínio ou artefatos oficiais do M1 sem aprovação explícita. (Garantido: zero escrita em artefatos, zero recálculo.)
- **§6.1 (loop-safe):** READ-ONLY M1, sem VPS/deploy/segredos, sem PII, consome `data/staging/outputs` sem ingestão ao vivo. (Satisfeito.)

Precedente direto: **DEC-004** (tiles online no Relatório Pontual Censitario, com cache+fallback gracioso; desvio cosmético restrito a um caminho). Este bloco segue o mesmo padrão de justificativa.

---

**Handoff pronto para Builder.**

Data: 2026-07-06 18:45:23 UTC
