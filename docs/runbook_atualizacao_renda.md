# Runbook — atualização anual dos fatores de renda (`motor_expansao.renda`)

> Para quem vai trocar o fator que leva a renda do Censo 2022 (julho/2022) até o ano corrente.
> Nada disto roda sozinho: o script só **grava uma versão nova**; virar a versão em uso é PR humano.
> Decisão: a DEC do método entra na E2 da correção de renda (prevista DEC-075 — **conferir o número
> contra a `origin/main` no dia**, ver Passo 5). Código: `src/motor_expansao/renda/`. Deploy:
> `docs/deploy_piloto_web.md` e `docs/deploy_api_bot.md`.

## O que isto atualiza

A renda **exibida** (tooltip do hexágono, ficha, Relatório Pontual, Relatório Municipal, PDFs da API e
do bot) sai de um ponto único, `motor_expansao.renda`:

- **domiciliar** = `V06004 × uplift × F_dom(uf)`;
- **per capita** = `V06004 × uplift × F_pc(uf) ÷ moradores` — com o **fator per capita próprio**,
  **nunca** derivada da domiciliar (dividir a domiciliar por moradores aplicaria duas vezes a queda de
  moradores entre 2022 e o ano-alvo).

`F_dom` e `F_pc` são a única coisa que este runbook troca. A escala do **score**
(`renda_per_capita_setor_2022_calibrada`) tem réguas próprias e **não** passa por aqui.

### Onde moram os fatores

```
src/motor_expansao/renda/fatores/
├── BR/
│   ├── 2026-08_caged_v0.json      # v0: o 1,1641 do CAGED que produção aplicava antes da E0
│   └── VIGENTE                    # uma linha: o nome da versão em uso (sem .json)
└── AR/
    ├── 2026-08_sem_atualizacao_v0.json   # fatores 1,0 (renda já em pesos de maio/2026)
    └── VIGENTE
```

- **Arquivos imutáveis.** Um `<versao>.json` **nunca é editado depois de publicado**. Corrigir é gravar
  uma versão nova. As antigas ficam no repositório — são elas que tornam o rollback possível.
- **`VIGENTE`** aponta a versão em uso. O país é o do perfil da instância (`perfil.json`, DEC-047):
  o diretório é escolhido por **lookup**, nunca por `if pais == ...`.
- Os arquivos viajam **dentro da imagem** (são `.json` e um arquivo sem extensão — o hatch empacota os
  dois; **nunca usar `.csv`**, que o `.gitignore` faz o hatch descartar em silêncio) e sobem por
  digest, com o mesmo controle de mudança do código. **Não** moram no `MOTOR_DATA_DIR` da VPS, de
  propósito: o `perfil.json` montado lá já sofreu drift. O antigo
  `data/staging/fator_temporal_renda.json` não é mais lido e **não se faz mais `scp` dele**.
- O pacote inteiro (`^src/motor_expansao/renda/`) é **CRITICO** no `scripts/loop_guard.py`: trocar o
  `VIGENTE` ou uma linha da fórmula muda a renda de todas as telas de uma vez, então o PR pede a label
  `critica-aprovada`.

## A regra da SIDRA 7531 (regra do Felipe, 2026-10-20) — ler antes de rodar

> **A tabela SIDRA 7531 só CONFERE o NÍVEL de cada ano contra a visita que ela usa naquele ano —
> visita 5 em 2022, visita 1 em 2025. NUNCA se calcula crescimento a partir da 7531. Os fatores vêm
> sempre da MESMA visita, a partir dos microdados.**

Por quê: a 7531 **mistura visitas** — o ano 2022 reproduz a visita 5 da PNAD Contínua anual e o ano
2025 reproduz a visita 1. A visita 1 mede renda cerca de 6% maior que a visita 5 no mesmo ano, então
`7531(2025) ÷ 7531(2022)` carrega um artefato de visita, não crescimento de renda.

Como o código impõe isso:

- o **cálculo** (`renda/pnad.py`) usa só microdados: fator de cada visita = nível do ano-alvo ÷ nível
  do ano-base **na mesma visita**, e o fator final é a **média geométrica das visitas 1 e 5**
  (per capita e domiciliar calculadas separadamente; nacional = Brasil inteiro);
- a **conferência** (`renda/sidra.py`) recebe os níveis já calculados e devolve **só erros** por UF. Se
  algum erro passar de **0,5%**, o script aborta. Nenhum valor da 7531 volta para o fator — e os
  testes `test_felipe_*` de `tests/unit/test_renda_atualizar_fatores.py` falham se o fator passar a
  depender dela (7531 adulterada não muda o fator; o cálculo não importa `sidra`);
- a visita que a 7531 usa em cada ano é **parâmetro declarado** (`visita_sidra`, gravado no arquivo de
  versão). Hoje só 2022 → 5 e 2025 → 1 estão declarados e conferidos. **Ano sem visita declarada
  aborta** — não se infere a visita. Para um ano-alvo novo, descobrir qual visita a 7531 reproduz
  naquele ano e declará-la com `--visita-sidra ANO=VISITA` (a visita errada passa de 18% de erro e o
  script aborta, o que já denuncia a troca).

## A regra de exceção por UF

Uma UF **pode** ganhar fator próprio, no lugar do nacional, quando atende às três condições (parâmetros
no script, nenhuma UF citada no código):

1. **Desvio relevante:** `|fator da UF ÷ fator nacional − 1| > L = 7%` na per capita, medido **em cada
   uma das duas visitas** (1 e 5), sempre contra o nacional da mesma visita;
2. **Consistência:** o desvio tem **o mesmo sinal** nas duas visitas;
3. **Amostra mínima:** **n ≥ 5.000** pessoas com renda **em cada uma das quatro amostras** (ano-base v1,
   ano-base v5, ano-alvo v1, ano-alvo v5).

Fator próprio = média geométrica das duas visitas, per capita e domiciliar separadas.

**A regra só aponta candidatas.** A inclusão é **decisão humana**, registrada no arquivo de versão:
a UF aprovada entra em `excecoes_aprovadas` (com `per_capita`, `domiciliar`, `moradores` e
`evidencia`), e o que a regra apontou fica em `candidatas_regra`. O script **recusa** `--aprovar-uf`
de UF que não seja candidata. Nunca há inclusão automática.

## Passo 1 — quando rodar

- A visita 1 do ano anterior sai em setembro (a de 2025 saiu em 23/09/2026) e a visita 5 cerca de um
  mês depois (16/10/2026). É inferência pelo calendário observado.
- **Esperar as duas visitas.** O fator é a média das duas; rodar só com uma não é opção.
- O verificador mensal do FTP com aviso no chat de ops (molde da DEC-052) **ainda não existe** — até
  ele existir, a checagem é manual no FTP do IBGE (PNAD Contínua anual, visitas 1 e 5).

## Passo 2 — rodar `atualizar_fatores`

No checkout do repositório (o script grava a versão nova em `src/motor_expansao/renda/fatores/<PAIS>/`):

```bash
python -m motor_expansao.renda.atualizar_fatores --pais BR --ano-base 2022 --ano-alvo 2025 \
    --aprovar-uf PE            # repetir as UFs aprovadas na versão vigente (ver o JSON dela)
```

O que ele faz, em ordem:

1. lista o FTP do IBGE e casa as 4 amostras (ano-base/ano-alvo × visitas 1 e 5);
2. baixa ou reusa o cache (`~/.cache/motor_expansao/pnad`, `sha256` no manifesto);
3. calcula os fatores **só dos microdados**, na mesma visita;
4. avalia a regra de exceção e aceita `--aprovar-uf` só para candidata;
5. confere o **nível** de cada ano contra a 7531 na visita declarada (`visita_sidra`); erro > 0,5%
   por UF aborta;
6. grava `<AAAA-MM>_pnad<ano_alvo>_vN.json` e o relatório de mudança `<mesmo nome>.md` ao lado.
   **O `VIGENTE` não é alterado.**

Opções úteis:

| Opção | Para quê |
|---|---|
| `--visita-sidra ANO=VISITA` | declarar a visita da 7531 de um ano novo (repetível); **completa** o mapa padrão (2022 → 5, 2025 → 1), não o substitui |
| `--ponte-ipca` | grava `ponte_ipca` (IPCA acumulado) — **informativo, nunca aplicado** |
| `--offline --cache-dir DIR --sidra-7531-json ARQ` | reproduz sem rede, a partir do cache e de um JSON da 7531 |
| `--saida-dir DIR` | grava fora do pacote (ensaio) |
| `--limiar` / `--n-min` | sensibilidade da regra (padrão 0,07 e 5.000) — mudar o padrão é mudar a regra: DEC nova |

**Censo novo:** o mesmo comando com `--ano-base` novo. A cadeia de base (V06004, uplift, moradores) é
regenerada pelos pipelines do Censo; o fator só leva do ano do Censo ao ano-alvo. O script aborta se
`--ano-base` diferir do `ano_base_renda` da versão vigente.

## Passo 3 — checar o relatório de mudança (`<versao>.md`)

- [ ] conferência com a SIDRA 7531 em até **0,5%** por UF, na visita declarada de cada ano;
- [ ] todos os fatores dentro da faixa **[0,9; 1,8]** (o loader recusa fora dela);
- [ ] coerência interna: `per_capita × moradores ≈ domiciliar` (tolerância 0,5%, nacional e cada exceção);
- [ ] delta contra a versão vigente — **alerta se algum fator variar mais de 10%**;
- [ ] candidatas novas e candidatas que **deixaram** de atender à regra.

## Passo 4 — decidir as exceções

Decidir, UF a UF, quais candidatas entram. Rodar de novo com o `--aprovar-uf` final (a rodada anterior
vira lixo de ensaio: apagar o `.json`/`.md` que não vão para o PR). Registrar quem aprovou no arquivo
de versão (`aprovado_por`) e a DEC em `dec`.

## Passo 5 — PR

- [ ] o novo `<versao>.json` + `<versao>.md` (relatório; o hash dele está em `relatorio.sha256`);
- [ ] `VIGENTE` com o nome da versão nova;
- [ ] **emenda da DEC do método** (prevista DEC-075) — ou **DEC nova**, se mudar a regra ou o método;
- [ ] **conferir o número da DEC contra a `origin/main`** antes de registrar (numerar pelo diretório
      local colide entre branches):
      ```bash
      git fetch origin && git ls-tree --name-only origin/main docs/decisions/ | sort | tail -3
      ```
- [ ] o PR é CRITICO no guard (`^src/motor_expansao/renda/`): pede `critica-aprovada`.

## Passo 6 — deploy e conferência

- Deploy **manual, por digest**, das duas imagens (web e api/bot) — os fatores vão dentro delas; não há
  `scp` de fator. Cada comando na VPS com confirmação explícita (CLAUDE.md §6).
- **Erro na subida:** com `MOTOR_DATA_DIR` setado, a checagem de subida (`validar_na_subida`) carrega os
  fatores e **recusa subir** se o arquivo estiver ausente ou inconsistente (`FatoresRendaInvalidos`) ou
  se faltar um `artefatos_obrigatorios` da versão / o carimbo `k` estiver ilegível
  (`InsumoRendaInvalido`). Container que não sobe depois do deploy: ler o log — a mensagem nomeia o
  arquivo e o problema. Não existe mais o fallback silencioso de antes (F = 1,0, uplift 1,632,
  k 1,0239).
- **Conferir o `/api/health`** no container: a versão de fatores exibida tem de ser a **nova** e
  `fixada_por_env` tem de ser `false`.
  ```bash
  docker compose -f docker-compose.prod.yml exec web curl -fsS http://127.0.0.1:8899/api/health
  ```
- Conferir uma renda conhecida na tela e no PDF contra o relatório de mudança (o delta da UF).

## Rollback

**Normal — PR de `VIGENTE`.** Um PR que devolve o `VIGENTE` à versão anterior (que continua no
repositório) e deploy por digest. Nenhum arquivo de versão é apagado nem editado.

**Emergência, sem rebuild — `MOTOR_FATORES_RENDA_VERSAO`.** A variável de ambiente fixa uma versão
**que já existe na imagem** e prevalece sobre o `VIGENTE`:

```bash
# 1) no .env da VPS (lido pelo compose para interpolar ${MOTOR_FATORES_RENDA_VERSAO:-})
MOTOR_FATORES_RENDA_VERSAO=2026-08_caged_v0
# 2) RECRIAR o container (restart NÃO relê o environment do compose)
docker compose -f docker-compose.prod.yml up -d web api
#    instância AR: docker compose -f docker-compose.ar.yml up -d web_ar
```

- **A variável só chega ao container porque o compose a lista** no `environment` de `api`, `web`
  (`docker-compose.prod.yml`) e `web_ar` (`docker-compose.ar.yml`). Esses arquivos **não têm
  `env_file`**: uma variável que só está no `.env` e não aparece no compose não tem efeito
  nenhum, e a falha é muda (travado por teste em `tests/unit/test_renda_proveniencia.py`).
- O `bot` não entra: ele não usa a renda (DEC-049).
- **`up -d`, não `restart`**: o `restart` reaproveita o container com o environment antigo. O
  `up -d` recria e, de quebra, zera o cache do loader (`carregar_fatores` é `lru_cache`).
- **Nunca é silencioso:** o log registra `WARNING` "ROLLBACK/fixação de versão ativo ..." e o
  `/api/health` mostra a versão fixada com `fixada_por_env: true`.
- Versão inexistente no diretório do país = **erro na subida** (não cai no `VIGENTE`).
- É ponte, não estado: abrir em seguida o PR de `VIGENTE` e, depois do deploy dele, **remover a
  variável** do `.env` e recriar os containers (`up -d`).

## Onde olhar quando algo falhar

| Sintoma | Onde |
|---|---|
| Script aborta na conferência SIDRA | visita declarada errada para o ano (`--visita-sidra`) ou microdado trocado; o relatório mostra o erro por UF |
| `--aprovar-uf` recusado | a UF não é candidata pela regra nesta rodada — a decisão humana só escolhe entre candidatas |
| Container não sobe após deploy | log de subida: `FatoresRendaInvalidos` (arquivo de fatores) ou `InsumoRendaInvalido` (parquet de uplift / carimbo `k` no staging) |
| `/api/health` mostra versão antiga | imagem velha (conferir o digest) ou `MOTOR_FATORES_RENDA_VERSAO` esquecida no `.env` |
| Renda mudou e ninguém trocou o `VIGENTE` | não deveria acontecer: só `VIGENTE`/env mudam a versão — conferir o `/api/health` e o log |
