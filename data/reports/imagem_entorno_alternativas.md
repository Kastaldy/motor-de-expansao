# Imagem do entorno no Relatório Pontual — alternativas sem provedor novo

> Pesquisa de 2026-07-22, motivada pela pergunta de Vinicius: *"é possível incluir um mapeamento
> geral da zona próxima sem usar API?"* — ou seja, atender à intenção do BLK-RELPON-11 (dar ao
> operador noção do que existe no entorno do ponto) **sem** abrir a DEC-018.
>
> **Conclusão em uma linha: existe caminho sem DEC, mas ele NÃO dissolve a DEC-018 — adia e
> rebaixa.** Detalhe em §4.
>
> READ-ONLY sobre o M1: nada aqui altera score, pesos, artefatos oficiais ou pipeline.

## 1. O que morreu por FÍSICA, não por licença

Um recorte de 250 m impresso em ~460 pt a 150 ppi exige **958 px**, ou seja **~26 cm/pixel na
fonte**. O que existe aberto e com cobertura nacional não chega nem perto:

| Fonte | m/px | px num recorte de 250 m | Serve? |
|---|---|---|---|
| Sentinel-2 (Copernicus) | 10 | **25 px** | Não — é uma mancha de 25 quadrados |
| CBERS-4A WPM multiespectral | 8 | 31 px | Não |
| Landsat 8/9 pancromático | 15 | 17 px | Não |
| **CBERS-4A WPM pancromático** | **2** | **125 px (19,6 ppi)** | Marginal, e é **cinza** |
| Amazonia-1 | 64 | 3,9 px | Não |

**Descartar a família inteira de satélite gratuito, inclusive os brasileiros do INPE.** O CBERS-4A
pancromático, único marginal, ainda soma revisita de 31 dias, nuvens, cobertura por cena e download
com cadastro — custo de engenharia alto para um resultado que não passa no critério de nitidez.

**O recorte de ~100 m do pedido original também está morto:** exige 10 cm/px. Nem o Esri z19 passa
(52 ppi). Só ortofoto municipal. A janela viável é **250–400 m** — e ela é a mesma para satélite e
para mapa de ruas, ou seja, **a largura não é o que se perde** ao trocar um pelo outro.

## 2. Portas que se fecharam na verificação

- **OpenAerialMap:** um bbox cobrindo toda a Grande São Paulo retorna **9 imagens** (um galpão, um
  aeródromo, prédios da USP). E 3 de 5 registros inspecionados estavam sob **CC BY-NC** — uso
  comercial seria violação de licença.
- **Tileserver self-hosted:** citado em `PLANO_APP_WEB.md:36` e no backlog, mas **não existe neste
  repositório** — `docker-compose.prod.yml` tem 5 serviços e zero ocorrência de `tileserver`/`/tiles`.
  E, mesmo existindo na VPS, seria OpenMapTiles: **mesma classe de conteúdo do Voyager, não satélite**.
- **POI comercial via OSM local:** `data/osm_cache/` tem 191 JSONs, 378 KB, 122 vazios, e só contém
  academias. `M1_OSM_ENABLED = False`. Não há camada de comércio em disco. Se o objetivo real for
  conteúdo comercial, o insumo certo é o **CNEFE 2022 do IBGE** (pontos de endereço com espécie
  residencial/comercial, download único, zero dependência em runtime) — bloco próprio, não este.
- **Ortofotos municipais:** qualidade excelente (GeoSampa 10 cm, Rio 15 cm, ES 25 cm, SC 39 cm), mas
  cobrem fração dos municípios, SC é de 2010–2012, e **só o GeoSampa tem licença verificada** (CC0,
  com `Fees: NONE` / `AccessConstraints: NONE` no `GetCapabilities`). Seria uma DEC por provedor.

## 3. Alternativas viáveis

| # | Alternativa | O que entrega | Infra que usa | DEC nova? | Custo |
|---|---|---|---|---|---|
| **A4** | **Operador anexa o print** (página "Imagem do entorno") | **Satélite real** | `_fotos_imovel_page` + `st.file_uploader` — **já existem** | **Não** (com rótulo neutro) | Baixo |
| **A1** | **Mapa de quadra, Voyager z19, ~300 m** | Quadras, footprints, nomes de rua, **números de porta**, hierarquia viária | Provedor **já aprovado** (DEC-004/011) | **Não** | Baixo no render, médio no PDF (churn de `/Count`) |
| A5 | Links "Abrir no Maps" / "Street View" no PDF | Atalho de 1 clique | `build_search_url` (função pura) | Não | Muito baixo |
| A3 | Bloco "Vizinhança competitiva imediata" | Distâncias e contagens de concorrente | Colunas já calculadas | Não | Baixo |
| A6 | Perfil do Bairro enriquecido | Mais números socioeconômicos | Partições do censo | Não | Baixo/médio |
| — | Esri World Imagery z19 | Satélite automático, nacional | Provedor **novo** | **Sim — DEC-018** | — |

**O que o Voyager z19 NÃO entrega** (testado adversarialmente): **nenhum POI comercial**. O Shopping
Ibirapuera aparece como blob bege rotulado "3103"; a Rua Augusta não tem um nome de loja. Também não
mostra telhado, área construída real, estacionamento/vagas, terreno vago, vegetação nem verticalização.

**Achado contraintuitivo:** **z20 perde os rótulos** (texto rasterizado em px de tile encolhe 2,3× ao
reamostrar). **z19 é o teto útil** — e o `_BASEMAP_ZOOM_BUMP = 1` (`censo_map.py:52`) **faz overshoot
nesta escala**: o mapa de quadra precisaria de bump = 0.

## 4. A DEC-018 não é dissolvida

- **Dissolve para o dashboard**, se a imagem de satélite virar passo manual permanente do operador.
- **NÃO dissolve para o bot Telegram nem para o "gerar em 1 clique"** — ali não há humano para
  anexar nada, e satélite automático continua exigindo Esri ou ortofoto municipal.
- **A1 reduz mas não elimina:** entrega morfologia, não as variáveis físicas do imóvel.

E há uma pergunta que o argumento *"o software não faz requisição"* **não responde**: o PDF final
contém imagem de terceiro e é **distribuído** a proprietário, sócio, comitê. A questão não some —
**troca de dono**, do repositório para a política de uso da empresa. Rótulo neutro na UI ("imagem que
você tenha direito de usar") → sem DEC. UI que **nomeia o Google** → o projeto passa a induzir um
workflow sobre um provedor específico, e isso merece registro.

## 5. Três consertos obrigatórios se A4 for adotada

1. **Trocar cover-crop por letterbox** no slot de entorno. Medido: `_recortar_cover` corta **150 px
   de cada lateral** de um print 16:9. Se a atribuição do provedor estiver ali, **o software a apaga
   sozinho** — converte "operador colou print com crédito" em "PDF distribuído sem crédito".
2. **Bug de rerun** em `_render_relatorio_pdf_imovel` (`pages.py:3704`): os botões de download estão
   dentro do `if gerar:` → baixar o CSV faz o PDF sumir e obriga a regerar tudo, inclusive os tiles.
   O padrão certo já existe no caminho vizinho (`pages.py:3067`, bytes em `session_state`).
3. **Ligar o uploader ao Mapa Territorial** (`pages.py:3522` hoje não passa `fotos=`). Hoje o
   operador precisa passar pelo fluxo de viabilidade (m², aluguel, ticket) só para anexar imagem.

**Achado de ops, independente:** `data/cache` **não é volume montado** no `docker-compose.prod.yml` →
em produção o cache de tiles é **efêmero por container**.

## 6. O que NÃO foi verificado (lacunas declaradas)

- **ToS do ArcGIS Online** para uso programático sem conta — **continua sem resposta**. Nenhuma
  declaração explícita da Esri autorizando ou proibindo. Decisão humana.
- **ToS do Google Maps** para print de tela em relatório de negócio distribuído — não apurável a
  partir do repo; não se sabe se a Ultra tem contrato Workspace/Maps que altere o quadro.
- **Onde o Google desenha o crédito** num print real — a geometria do corte foi medida (150 px de
  cada lado), a posição do crédito não. Checagem manual de 30 s com um print real resolve.
- **Licenças de SIGSC (SC), GEOBASES (ES) e Data.Rio** — nenhum publica termos explícitos.
- **STAC público do INPE** (`data.inpe.br/bdc/stac/v1/`) permite download anônimo dos assets? Não
  verificado (o catálogo clássico exige cadastro).
- **Latência real do fetch z19 no bot Telegram** — não medida.
- **Voyager fora de capital** — testado em 2 pontos (Chapecó/SC e Patos de Minas/MG). Chapecó veio
  visivelmente esparso (4 números de porta, muito bege vazio). Amostra pequena.
