# Para a Liderança — Camada de Satélite (PoC Visão de Satélite)

**Escopo:** Brasil de mercado — 12 UFs (SP, MG, RJ, ES, PR, SC, RS, BA, PE, CE, GO, DF).
**486.850 hexágonos H3 resolução 7** (~5,16 km² cada), anos 2016 e 2023.
Custo de dados: **zero** (fontes gratuitas com uso comercial).

---

## 1. Documentos — comece por aqui

| Arquivo | O que é |
|---|---|
| **`RELATORIO_CONSOLIDADO_SATELITE.pdf`** | **COMECE AQUI.** Tudo em um só documento: escopo, validação contra o Censo (r=0,86), índices de crescimento por estado e município, aceleração, os datasets e a validação vs. M1. 8 seções, 5 figuras. |
| `VALIDACAO_SATELITE_VS_M1.pdf` | Aprofundamento técnico da validação satélite vs. baseline M1. |
| `*.docx` | Versões editáveis dos dois documentos. |
| `figura_crescimento_uf.png` | Crescimento por estado: pessoas (Censo) × área construída (satélite). |
| `figura_aceleracao.png` | Radar de aceleração — quem está ganhando ritmo agora. |
| `figura_resolucao.png` | Onde o baseline do M1 fica cego dentro do município. |
| `figura_divergencia.png` | Candidatos que a triagem atual descarta. |

**Achado central:** o score do M1 é **constante dentro de cada município** (3.890 de 3.890
municípios) — é um número municipal pintado nos hexágonos. Resultado medido: **68,2% da variação
da densidade construída** e **76,8% da variação do crescimento** acontecem *dentro* dos municípios,
invisíveis à triagem atual. O satélite opera com **125× mais resolução** (486.850 hexágonos vs. 3.892 municípios).

---

## 2. Dados entregues

### `indice_densidade_construida_BR.(parquet|csv)`
Índice de densidade urbana construída por hexágono.

| Coluna | Descrição |
|---|---|
| `hex_id`, `lat`, `lng` | Hexágono H3 res 7 e seu centroide |
| `UF`, `cod_municipio`, `nome_municipio` | Localização |
| `densidade_2016`, `densidade_2023` | Fração construída (0–1) vista pelo satélite |
| `altura_media` | Altura média das edificações (Google 2.5D) |
| `indice_densidade` | **0–100** — percentil nacional de densidade construída |

### `vetor_crescimento_hex_BR.(parquet|csv)`
Vetor de crescimento por hexágono, 2016→2023.

| Coluna | Descrição |
|---|---|
| `crescimento_delta` | Variação absoluta da fração construída |
| `crescimento_pct` | Variação percentual sobre a base de 2016 |
| `magnitude_vetor` | Intensidade do gradiente local de crescimento |
| `direcao_graus` | **Direção do crescimento** (0° = Norte, 90° = Leste) |
| `crescimento_classe` | `expansao_forte` · `expansao` · `estavel` · `retracao` |

### `candidatos_ocultos_BR.csv`
Os **39.873 hexágonos (8,2%)** onde o satélite vê construção alta (top 20%) e o M1 pontua na
metade inferior. É uma fila de triagem pronta para verificação.

---

## 3. Limites honestos

- **Não é validação de resultado de negócio.** Só 4 hexágonos da base M1 têm performance real de
  unidade Ultra registrada — cruzar com performance segue como o teste definitivo, e depende de
  dado que hoje não existe na base. Esta é uma validação *estrutural e de cobertura*.
- **"Todo o Brasil" = Brasil de mercado.** Interior Norte/Nordeste e Amazônia ficaram de fora por
  ausência de mercado, **não** por limite técnico — o pipeline roda em qualquer UF quando preciso.
- **A cegueira do M1 não é uniforme.** Em metrópoles compactas (São Paulo, Rio), o valor único do
  M1 aproxima bem. Ela se concentra nos municípios de **grande área** (urbano + rural) — que são
  exatamente onde está a fronteira de expansão.
- **Aceleração nacional.** A série anual completa 2016–2023 foi processada para as **12 UFs**, então
  a aceleração (crescimento recente vs. inicial) cobre todos os municípios. Ainda assim é um sinal
  físico de construção — direcional para expansão, não gatilho automático de site.

---

## 4. Reprodutibilidade

```
scripts/passo33_entrega_lideranca.py   # gera os 2 datasets + roda a validação
scripts/passo34_docx_validacao.py      # gera o documento e as figuras
```
