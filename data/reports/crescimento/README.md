# Camada de crescimento municipal — geradores (BLK-TRAJ-01)

Produzem os dois artefatos que o passo 4 do funil do piloto consome:

| Artefato | Chave | Linhas | Consumidor |
|---|---|---|---|
| `data/staging/crescimento_municipal.parquet` | `cod6` (6 dígitos IBGE) | 5.571 | `web/server/app.py::carregar_crescimento` |
| `data/staging/crescimento_hex.parquet` | `hex_id` (H3 res 7) | 41.135 | `web/server/app.py::carregar_crescimento_hex` |

Os dois são **opcionais**: ausentes, os loaders devolvem `None`, o passo 4 exibe a
narrativa de indisponibilidade e o resto do piloto segue igual. Nenhum deles é
gravado no artefato do M1 — a camada é **READ-ONLY** sobre ele.

## Onde os dados moram (variáveis de ambiente)

Os caminhos **não** são mais literais dentro dos scripts: `_raizes.py` resolve as
quatro raízes por variável de ambiente, com default para o layout do autor. Rodar em
outra máquina é definir as variáveis, não editar 10 arquivos — e a falha vem como
"defina `SOCIOECONOMICO_DIR`", não como um `FileNotFoundError` apontando para o disco
de outra pessoa.

| Variável | Serve para | Default |
|---|---|---|
| `MOTOR_DATA_DIR` | lê `outputs/`, **escreve `staging/`** | `data/` deste repo |
| `CRESCIMENTO_TEC_DIR` | os 3 CSVs do projeto Crescimento Regional TEC | `C:\dados\crescimento_tec` |
| `SOCIOECONOMICO_DIR` | `rais/`, `caged/`, `cnpj/`, `pib/` | `C:\dados\socioeconomico` |
| `POC_SATELITE_DIR` | mosaicos `data/uf=XX/hex_google_temporal_YYYY.parquet` | `C:\dados\poc_satelite` |

`MOTOR_DATA_DIR` é a **mesma** variável que `web/server/app.py` usa para achar
`staging/`. Antes o destino era um literal aqui e uma env var lá: podiam divergir sem
ninguém notar, e o piloto leria um artefato velho em silêncio.

Os defaults são placeholders genéricos de propósito: caminho de pasta pessoal (nome de
usuário, conta corporativa de nuvem) não entra em arquivo versionado — uma vez commitado
fica no histórico do git para sempre. Aponte as variáveis para onde os dados estão.

Os intermediários (`_mun_cresc_bruto`, `_cres_extra`, `_dims`) ficam ancorados **na
pasta dos scripts**, não no CWD — rodar de outro diretório antes lia um intermediário
de outra execução, sem avisar.

### O que este repositório NÃO consegue reproduzir sozinho

Ser honesto sobre isto importa mais do que parecer completo:

- Os insumos são dezenas de GB de microdado (RAIS, CAGED, CNPJ) e de mosaicos de
  satélite por UF. **Nada disso está aqui e nada disso pode estar.**
- **`_eixo_trajetoria.parquet` não é gerado por nenhum destes 10 scripts.** Ele é lido
  por `04`, `07` e `08` e vem do projeto irmão `poc_satelite`, em
  `_proposta_camada_motor/prototipo/p2_eixo.py`, que por sua vez depende de
  `p1_base.py`. Colocá-lo nesta pasta é pré-requisito do `04`. Contrato mínimo das
  colunas: `hex_id`, `cod_municipio`, `n_pixels`, `mascara_urbana` (bool),
  `p2016`…`p2023` (fração de presença de edificação, 0–1). Área construída =
  `p{ano} × n_pixels × 400` (pixel de 20 m); `mascara_urbana = p2019 >= 0.005`.
- Logo: reproduzir a camada do zero exige **este repo + `poc_satelite` +
  `Crescimento Regional TEC` + a árvore de microdado**. O que os 10 scripts garantem é
  serem executáveis onde esses dados existirem, e dizerem qual peça falta.

Os dois artefatos são versionados como saída, não como código: estão em
`PILOTO_CRESCIMENTO` (`scripts/check_artifacts.py`), então **a ausência degrada a camada
e não quebra o deploy**.

E é justamente por não quebrar nada que a ausência precisa ser dita em voz alta — o
passo 4 sai vazio e sem cor, sem erro na tela e sem linha no log. Onde conferir:

- **disco local:** `python scripts/check_artifacts.py` (respeita `MOTOR_DATA_DIR`, a
  mesma raiz que `_raizes.py` e o backend usam);
- **ambiente publicado:** `curl -fsS <host>/api/health` → campo `artefatos_faltando`.

Eles não viajam com o código: o `.gitignore` corta `data/staging/*` e o `.dockerignore`
corta `data/` da imagem. Em produção chegam **só** pelo bind mount declarado em
`docker-compose.prod.yml`. Copiar os dois parquets para
`/opt/motor-expansao/data/staging/` é o que acende a camada lá.

## Fontes

Tudo fora do repositório, sob as raízes acima:

- **CAGED** (`caged/caged_municipio_mensal_2020_2026.csv`) — saldo mensal por município, até jun/2026
- **RAIS** (`rais/rais_municipio_{2020..2024}.csv`) — vínculos, massa salarial, remuneração
- **CNPJ / Receita Federal** (`cnpj/agg/*.parquet`, `cnpj/Municipios.zip`) — abertura e fechamento de empresas por ano e setor
- **IBGE** (`pib/populacao_6579_serie.csv`, `pib/pib_municipal_5938_2019_2023.csv`)
- **Crescimento Regional TEC** (`output/*.csv`) — índices municipais já apurados
- **Satélite** (`poc_satelite`) — presença de edificação por hexágono, 2016–2023

## Ordem obrigatória

Rodar **do começo, sempre**, nesta ordem. Rodar parcial produz artefato
silenciosamente errado — sem exceção e sem erro na tela.

```
01_municipal.py     -> _mun_cresc_bruto.parquet          (CAGED + RAIS + CNPJ por município)
02_enriquecer.py    -> _cres_extra.parquet               (série, salário, setor, mediana da UF)
03_artefato.py      -> staging/crescimento_municipal.parquet
04_dimensoes.py     -> _dims.parquet                     (as 5 dimensões + posição nacional)
05_veredito.py      -> soma v_classe/v_frase ao artefato
06_encode_dims.py   -> soma cres_dims
07_series.py        -> soma cres_series
08_populacao_e_hex.py -> corrige População + staging/crescimento_hex.parquet
09_nivel.py         -> converte as séries de ritmo para nível
10_periodo.py       -> ancora a série de emprego e soma o período às dimensões
```

## Os quatro gotchas

Todos custaram tempo real. Estão aqui para não custarem de novo.

**1. `03_artefato.py` recria o arquivo inteiro.** Rodar só ele para "atualizar o
CAGED" apaga `cres_dims`, `cres_series`, `v_frase`, `v_classe` e todas as colunas
`dim_*`/`pos_*`. Não dá erro, não dá 500 — o passo 4 simplesmente perde o veredito
e o Detalhes. Depois do `03` é obrigatório seguir até o `10`.

**2. `08_populacao_e_hex.py` reescreve `cres_dims` sem o período.** Se rodar depois
do `10`, a linha de População perde o campo `período` em silêncio. Por isso o `10`
vem por último.

**3. `09_nivel.py` não é idempotente.** Ele faz `cumsum` sobre a série de empresas;
rodar duas vezes acumula o acumulado e produz uma curva plausível e errada.

**4. `09` e `10` só atualizam Emprego para município presente na RAIS 2022.** Um
município criado depois fica com a série da geração anterior (unidade `vagas` em vez
de `vínculos`). Hoje é um caso: `510183` Boa Esperança do Norte/MT, fora das 12 UFs.

## Os dois campos codificados

Para não inflar o contrato da API com dez colunas, duas viajam como string.

**`cres_dims`** — `nome:valor:unidade:posição:período`, blocos separados por `;`

```
Renda:25.8:%:25:2020→2024;Empresas:110.0:/mil:99:2020–2025;Emprego:8.8:%:59:2022→jun/2026
```

**`cres_series`** — `nome|unidade|ini|fim|v1,v2,…`, blocos separados por `;`

```
Renda|R$|2020|2024|3243,3500,3900,4200,4643;Emprego|vínculos|dez/2022|jun/2026|198454,…
```

O front (`web/src/components/NarrativePanel.tsx`) faz `split` desses separadores.
**Nenhum valor pode conter `:`, `|` ou `;`.** Os separadores `→` e `–` dos períodos
são seguros. Verificado em 26.129 blocos de dims e 26.140 de séries.

O mesmo acoplamento existe nas classes do hexágono, e ele agora tem três pontas:
`08_populacao_e_hex.py` (`CORTES`) grava o identificador **sem acento** no parquet,
`app.py` (`_ROTULO_CLASSE`) traduz para o rótulo acentuado que a API envia, e
`lib/colors.ts` (`crescClasseToColor`) compara esse rótulo para escolher a cor.
Quebrar qualquer elo pinta a camada 4 inteira de cinza — sem erro, sem log.

O identificador é ASCII de propósito (CLAUDE.md §2): era gravado `'Estável'` enquanto
o irmão `cres_tendencia` já saía `'Estavel'`, e os dois apareciam no mesmo balão de
tooltip. `tests/unit/test_paridade_classe_crescimento_web.py` trava as três pontas —
inclusive que o identificador continue sem acento.

## Decisões que os números não explicam sozinhos

**População é 2016→2021, não até 2025.** A série do IBGE tem duas bases: o Censo
2022 revisou as estimativas e o cruzamento 2021→2024 tem dispersão de 0,697 a 1,425,
contra 0,974–1,026 entre anos da mesma base. Comparar 2016 com 2025 mistura
metodologias. Ver `08_populacao_e_hex.py`.

**Renda é nominal.** A mediana nacional de +34% em 2020→2024 carrega inflação. Não
foi deflacionada para não introduzir um índice não auditável aqui; a comparação com
a mediana nacional na barra faz o papel do deflator na leitura relativa.

**Emprego é dez/2022 → jun/2026.** Saldo acumulado do CAGED sobre o estoque de
vínculos da RAIS de 2022. O primeiro ponto da série é esse estoque, para a variação
do gráfico bater exatamente com o percentual da dimensão.

**"Sem obra nova" não é "em queda".** A classe cobre variação de área construída
levemente negativa, que nessa escala é obra encerrada mais ruído de medição — não
demolição. Por isso é cinza, não vermelho.

## Rodar

```bash
cd data/reports/crescimento
for f in 0*.py 10_*.py; do python "$f" || break; done
```

Os caminhos de entrada estão no topo de cada script. Fora do gate de lint por
`pyproject.toml` (`extend-exclude = ["data"]`), como os demais estudos de
reprodutibilidade em `data/reports/`.
