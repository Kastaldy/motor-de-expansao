# Runbook — deploy de DADO da E3 (renda do hexágono pela malha de setores)

> Plano de correção da renda, E3 (frente c). Fórmula e contrato: `docs/relatorio_pontual_censitario.md`,
> "Renda do hexágono". Este runbook cobre **só o dado**; o código vai pelo deploy por digest de sempre.
> **Deploy é manual do dono, comando a comando, com confirmação explícita** (CLAUDE.md §6).

## O que muda na VPS

| Artefato | Caminho na VPS | Como chega |
|---|---|---|
| Malha do hexágono | `/opt/motor-expansao/data/staging/censo2022_hex_da_malha.parquet` | **scp** da malha regenerada (abaixo). Ganha `renda_domiciliar_2022_malha`, `renda_per_capita_domiciliar_2022_malha` e 2 pesos de auditoria; as 17 colunas existentes saem bit a bit. |
| Enriquecido (derivado) | `/opt/motor-expansao/data/outputs/hexagonos_dashboard_enriquecido/` | **remontado NA VPS** pelo `run_regen_mercado.sh` (DEC-059), do staging da própria VPS + a malha nova. |

**O enriquecido local NÃO sobe.** Ele foi montado do `hexagonos_mercado_mapeado.parquet` local, de
2026-09-11; a VPS regenera a camada de mercado todo domingo. Copiar o enriquecido local por cima do
vivo voltaria a concorrência do piloto à foto de setembro, sem erro nenhum. O regen da VPS lê a malha
do staging (`calcular_colunas_mercado` e `fase1_bi_exports` chamam `sobrepor_renda_da_malha`), então
basta trocar a malha e remontar lá.

## Artefato a subir (estação do Felipe)

Pasta (`$E3` nos passos): `C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\411836a7-8cdf-4529-a5f5-8144d8073500\scratchpad\e3\`

| Arquivo | md5 | O que é |
|---|---|---|
| `antes\censo2022_hex_da_malha.parquet` | `5d344e3c93857a4a0b6388614b8ae74c` | a malha VIVA da VPS (2026-08-31), conferida em 2026-10-21. |
| `malhas\malha_regen_geo_vps.parquet` | `07af732b5d9d50d61461fbf018bcbcf1` | **o que sobe**: regeneração COMPLETA da malha sobre a malha de setores da VPS. |

**Escolha do dono (2026-10-21): regeneração completa (opção c).** Ela foi feita sobre os MESMOS
insumos da VPS, conferidos por md5 em 2026-10-21: as 5.571 partições de `setores_censitarios_2022_geo`,
os dois uplifts e a `pop_total_setor_2022` do `hexagonos_mercado_mapeado` (hash da coluna). Resultado
contra a malha viva: os mesmos 1.293.425 hexágonos, todas as colunas existentes idênticas valor a valor
(score, renda e população inclusive; só `data_agregacao_censo_hex` muda) e as 4 colunas novas da E3
(as duas rendas com valor em 1.194.976 hexágonos). **Nenhum score muda.**

**Não usar a malha de setores do checkout principal da estação.** Nela, a partição
`uf=CE/cod_municipio=2313955` foi regravada em 2026-09-02 (md5 `d554f82b…`) e difere da VPS
(`2b2bb4f3…`, de 2026-08-28, a que gerou a malha viva). Regenerar sobre ela mudava o score de 33
hexágonos e criava 23 novos — era essa a origem das opções (a)/(b)/(c) anteriores, hoje sem objeto.

## Pré-condições (todas obrigatórias; qualquer uma falhando = abortar)

1. **A imagem com o código da E3 já está no ar (web E api).** O regen roda com a imagem da api: com a
   imagem antiga, o enriquecido remontado sai SEM as colunas novas e o efeito some em silêncio (o
   código cai na fórmula municipal por linha). Ordem: código primeiro, dado depois.
2. **Janela fora do cron de domingo** (DEC-059). De segunda a sexta, longe da terça/quinta dos
   monitores, e sem regen rodando: `pgrep -af run_regen_mercado` vazio.
3. **A malha viva e a malha de setores da VPS são as mesmas da regeneração.** Se alguma mudou, o scp
   trocaria `score_malha`/`renda_malha` (e o score do hexágono) sem nada acusar.

   ```bash
   md5sum /opt/motor-expansao/data/staging/censo2022_hex_da_malha.parquet
   # tem de ser 5d344e3c93857a4a0b6388614b8ae74c
   md5sum /opt/motor-expansao/data/outputs/setores_censitarios_2022_geo/uf=CE/cod_municipio=2313955/part-000.parquet
   # tem de ser 2b2bb4f3f921441fef7b7769b1f9c255
   ```

   Divergiu: **abortar** e regenerar a malha de novo sobre a malha de setores da VPS
   (`python -m motor_expansao.pipelines.agregar_censo_hex_da_malha --output <saida.parquet>`, rodando
   numa pasta com `data/` igual à da VPS), conferir contra a malha viva e usar o md5 novo.

## Passos

```bash
# 0) (VPS) carimbo + backup ANTES de tudo. ANOTE o carimbo impresso: o rollback precisa dele.
D=/opt/motor-expansao/data
TS=$(date +%Y%m%d-%H%M%S) && echo "CARIMBO DO DEPLOY E3: $TS" &&
  cp -a "$D/staging/censo2022_hex_da_malha.parquet" "$D/staging/censo2022_hex_da_malha.parquet.bak-e3-$TS" &&
  cp -a "$D/outputs/hexagonos_dashboard_enriquecido" "$D/outputs/hexagonos_dashboard_enriquecido.bak-e3-$TS" &&
  ls -ld "$D/staging/censo2022_hex_da_malha.parquet.bak-e3-$TS" "$D/outputs/hexagonos_dashboard_enriquecido.bak-e3-$TS"
```

```powershell
# 1) (estacao) enviar a malha regenerada para nome TEMPORARIO -- nunca por cima do vivo
$E3 = "C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\411836a7-8cdf-4529-a5f5-8144d8073500\scratchpad\e3"
$ENXERTO = "$E3\malhas\malha_regen_geo_vps.parquet"
(Get-FileHash -Algorithm MD5 $ENXERTO).Hash        # tem de bater com a tabela
scp -i "$env:USERPROFILE\.ssh\id_ultra" $ENXERTO `
    root@2.25.137.241:/opt/motor-expansao/data/staging/censo2022_hex_da_malha.parquet.novo
```

```bash
# 2) (VPS) conferir o que chegou: md5 E as colunas novas no schema
D=/opt/motor-expansao/data
MD5_ENXERTO=07af732b5d9d50d61461fbf018bcbcf1
echo "$MD5_ENXERTO  $D/staging/censo2022_hex_da_malha.parquet.novo" | md5sum -c - &&
  cd /opt/motor-expansao/app &&
  docker compose -f docker-compose.prod.yml exec -T api python -c "
import pyarrow.parquet as pq
n = set(pq.read_schema('/app/data/staging/censo2022_hex_da_malha.parquet.novo').names)
f = {'renda_domiciliar_2022_malha', 'renda_per_capita_domiciliar_2022_malha'} - n
assert not f, f'faltam {f}'
print('schema OK', len(n), 'colunas')
"

# 3) (VPS) SO com o passo 2 OK: trocar a malha por rename atomico
mv "$D/staging/censo2022_hex_da_malha.parquet.novo" "$D/staging/censo2022_hex_da_malha.parquet"

# 4) (VPS) remontar o enriquecido NA VPS: seco primeiro (tem de sair "Validacao OK"), depois de
#    verdade. O regen publica por rename e faz `restart` de web/api/telegram-bot -- nunca
#    `--force-recreate`, que reaplicaria o compose e poderia trocar a versao do piloto junto.
DRY_RUN=1 /opt/motor-expansao-infra/run_regen_mercado.sh
/opt/motor-expansao-infra/run_regen_mercado.sh
```

```bash
# 5) (VPS) conferir: as colunas chegaram ao enriquecido e o SCORE nao se mexeu
#    (score_setor_2022_calibrado e score_priorizacao identicos ao backup do passo 0).
#    Noutra sessao: TS=<carimbo anotado no passo 0> antes.
: "${TS:?defina TS com o carimbo do passo 0}" &&
cd /opt/motor-expansao/app &&
docker compose -f docker-compose.prod.yml exec -T api python - "$TS" <<'PY'
import hashlib, sys
import pandas as pd, pyarrow.dataset as ds
ts = sys.argv[1]
def col(caminho, c):
    t = ds.dataset(caminho, partitioning="hive").to_table(columns=["hex_id", c]).to_pandas()
    s = t.drop_duplicates("hex_id").set_index("hex_id")[c].sort_index()
    return hashlib.sha256(pd.util.hash_pandas_object(s, index=True).to_numpy().tobytes()).hexdigest()
novo = "/app/data/outputs/hexagonos_dashboard_enriquecido"
velho = f"/app/data/outputs/hexagonos_dashboard_enriquecido.bak-e3-{ts}"
nomes = set(ds.dataset(novo, partitioning="hive").schema.names)
assert {"renda_domiciliar_2022_malha", "renda_per_capita_domiciliar_2022_malha"} <= nomes, "colunas E3 ausentes"
for c in ("score_setor_2022_calibrado", "score_priorizacao"):
    a, b = col(velho, c), col(novo, c)
    print(c, "IDENTICO" if a == b else "DIFERENTE")
    assert a == b, c
PY
```

## Conferência depois do deploy

- O hexágono `87a810073ffffff` (São Paulo) é o exemplo do plano: renda domiciliar 2022 da malha
  ≈ R$ 4.749,6 e per capita 2022 ≈ R$ 1.766,2; na tela, cada uma vezes o fator da versão vigente
  (dom × F_dom, pc × F_pc).
- Um hexágono com renda municipal (SIDRA) **não** muda.
- O PDF municipal e o tooltip mostram o mesmo número para o mesmo hexágono.

## Rollback

Repor a malha do passo 0 e devolver o enriquecido. Não precisa de rebuild: sem as colunas, o código
volta sozinho, por linha, à fórmula de antes da E3. **Nada é apagado**: o vivo é renomeado. Roda
num subshell, para o `exit` de uma checagem não derrubar a sessão ssh.

```bash
TS=<carimbo anotado no passo 0>          # sem ele: ls -d /opt/motor-expansao/data/outputs/*.bak-e3-*
(
  set -euo pipefail
  : "${TS:?carimbo vazio -- abortando}"
  D=/opt/motor-expansao/data
  MALHA_BAK="$D/staging/censo2022_hex_da_malha.parquet.bak-e3-$TS"
  ENR_BAK="$D/outputs/hexagonos_dashboard_enriquecido.bak-e3-$TS"
  [ -f "$MALHA_BAK" ] || { echo "backup da malha ausente: $MALHA_BAK"; exit 1; }
  [ -d "$ENR_BAK" ]   || { echo "backup do enriquecido ausente: $ENR_BAK"; exit 1; }
  # malha: copia para nome temporario e troca por rename atomico
  cp -a "$MALHA_BAK" "$D/staging/censo2022_hex_da_malha.parquet.rollback"
  mv "$D/staging/censo2022_hex_da_malha.parquet.rollback" "$D/staging/censo2022_hex_da_malha.parquet"
  # enriquecido: o vivo vai para .rollback-*, o backup volta por copia (o .bak fica intacto)
  mv "$D/outputs/hexagonos_dashboard_enriquecido" "$D/outputs/hexagonos_dashboard_enriquecido.rollback-$TS"
  cp -a "$ENR_BAK" "$D/outputs/hexagonos_dashboard_enriquecido"
  cd /opt/motor-expansao/app
  docker compose -f docker-compose.prod.yml restart web api telegram-bot
)
```

Se um domingo passou entre o deploy e o rollback, o backup do enriquecido tem a concorrência de
antes daquele domingo. Nesse caso, repor **só a malha** (as duas linhas da malha acima, com as
mesmas checagens) e rodar o `run_regen_mercado.sh` à mão: ele remonta o enriquecido, já sem as
colunas, a partir da concorrência do domingo.
