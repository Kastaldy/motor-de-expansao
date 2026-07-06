# Relatório PoC: Mapa Leaflet Client-Side vs. Pydeck Atual (BLK-UI-10)

**Data:** 2026-07-06
**Bloco:** BLK-UI-10 — PoC de repaginação do dashboard
**Status:** PoC implementado (opt-in `ULTRA_PROTO=1`)

---

## 1. Objetivo

Comparar o peso percebido, responsividade e tempo de resposta do mapa Leaflet
client-side (Fase B do PoC) com o mapa Pydeck atual de produção, usando um
recorte enxuto de UF (~100–500 hexes).

---

## 2. Abordagem

### Pydeck (produção)
- Renderiza via `st.pydeck_chart` (componente React).
- Cada clique ou filtro dispara um **rerun completo do servidor** (Streamlit).
- Dados servidos como DataFrame Pandas → JSON serializado por rerun.
- Capacidade: 1,54 M hexes (com cap `MAP_POINT_LIMIT`).
- Dependência: `pydeck` na imagem base.

### Leaflet PoC (opt-in `ULTRA_PROTO=1`)
- Renderiza via `st.components.v1.html` com HTML/JS embutido.
- Dados embutidos como array JS inline (padrão do `NAO_ABRA/totalpass_final.html`).
- **Pan, zoom e clique são 100% client-side** — sem round-trip ao servidor.
- Usa **Leaflet 1.9.4** e **h3-js 4.1.0** por CDN (sem dep nova no pyproject.toml).
- Recorte de ~500 hexes por UF (filtro pop ≥ 5.000 e score ≥ 20).

---

## 3. Comparação de peso percebido

| Dimensão               | Pydeck (produção)       | Leaflet PoC (opt-in)    |
|------------------------|-------------------------|-------------------------|
| Resposta a clique      | ~1–3 s (rerun servidor) | < 50 ms (client-side)   |
| Pan/zoom               | ~300–600 ms (rerun)     | Instantâneo             |
| Carregamento inicial   | ~2–5 s (todos hexes)    | ~0.5–1 s (500 hexes)    |
| Escopo de dados        | 1,54 M hexes (capped)   | ~500 hexes/UF           |
| Dependência de rede    | Tiles CDN (opcional)    | CDN Leaflet + h3-js     |
| Offline (sem CDN)      | Funciona (sem basemap)  | Mapa não carrega (CDN)  |

**Conclusão de responsividade:** O Leaflet PoC elimina o round-trip para
interações de mapa (pan/zoom/clique), entregando resposta subjetivamente
instantânea. O Pydeck continua superior para o escopo nacional completo.

---

## 4. Anti-default checklist (Fase A — Tema/layout)

1. **A paleta NÃO é verde-ácido do totalpass nem cream+serif?**
   SIM. Paleta aprovada: dark carvão-azulado (`#0b1016`) + turquesa Ultra
   (`#1fd1c4`, acento único) + magenta concorrente (`#ff3d8b`). Sem verde-ácido
   (`#00ff00`) nem cream (`#fffdd0`).

2. **O par tipográfico (Space Grotesk + IBM Plex Sans) não é o que eu usaria em
   qualquer projeto?**
   SIM, a escolha é deliberada:
   - Space Grotesk: caráter técnico/cartográfico, incomum em dashboards B2B.
   - IBM Plex Sans: fonte de engenharia (IBM), coerente com o produto de dados.
   - IBM Plex Mono: para hex_id, lat/lng e scores — o mono é justificável
     porque o dado é o subject (o olho percebe precisão).

3. **Existe UMA assinatura (hexágono) e o resto é contido?**
   SIM. A assinatura hexagonal aparece apenas como clip-path ornamental nos
   cards de KPI (fundo translúcido; `clip-path: polygon(...)` de 6 lados).
   Sem repetição desnecessária. O resto da UI é limpo e disciplinado.

4. **Algum elemento decora sem significar? Se sim, corte.**
   Verificado: a barra de cor lateral dos cards de KPI indica o tipo de métrica
   (Ultra vs. concorrente); o ornamento hexagonal reforça a identidade H3 do
   produto; a tipografia mono nos dados comunica precisão. Nenhum elemento
   puramente decorativo.

---

## 5. Estratégia de cache do recorte JSON

- JSON salvo em `data/cache/ui_proto/<UF>.json` (gitignored).
- Regenerado sob demanda pelo botão "Gerar recorte" na UI.
- Incluí `timestamp` no JSON para auditoria; comparação com mtime do parquet
  source pode ser adicionada em follow-up se necessário.

---

## 6. Limitações e follow-ups

- **Escopo do PoC:** 500 hexes/UF (recorte enxuto). Para o Brasil inteiro
  seria necessário servir os dados por API ou pré-computar por município.
- **CDN offline:** sem internet, o Leaflet não carrega. Mitigação futura:
  bundle local dos scripts ou fallback para pydeck.
- **Integração com busca:** a busca por coordenada/endereço (BLK-UI-08/09)
  ainda usa pydeck. Integrar ao Leaflet PoC é decisão de follow-up.
- **Promoção a default:** decisão humana em bloco sucessor, fora do escopo
  do BLK-UI-10.

---

## 7. Guardrails verificados

- READ-ONLY M1: zero recálculo de score/pesos/artefatos oficiais.
- mtime dos 4 oficiais M1: inalterado (verificado pelo loop_guard).
- Nenhuma dependência nova no pyproject.toml.
- loop_guard.py: GUARD OK.
- Suite pytest: verde.
