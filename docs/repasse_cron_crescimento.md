# Repasse — ligar a atualização trimestral da camada de crescimento (DEC-052)

> Para o dono executar na VPS, comando a comando, sem precisar abrir o repositório.
> Nada disto roda sozinho: o PR só entrega o código; cada passo abaixo é seu.
> Decisão: `docs/decisions/DEC-052.md` · detalhe de infra: `docs/infra_producao.md`.

## O que isto liga

Um cron **trimestral** (dia 5 de fev/mai/ago/nov, 00:00 BRT) que atualiza a camada
"Como as cidades estão indo" (passo 4 do piloto): baixa os meses novos do CAGED,
reroda a cadeia de geração completa em área de rascunho, valida, publica por rename
atômico, reinicia o web e avisa no chat de ops do Telegram — sucesso ou falha. Falhou
qualquer etapa: o staging fica intacto e a tela não muda.

O trimestre atualiza o **Emprego** (CAGED é mensal). Renda, população e empresas são
fontes anuais e os prédios (satélite) são 2016-2023 — o aviso do bot repete isso a
cada rodada.

## Passo 0 — o que precisa existir antes (uma vez)

**a) Imagem nova da api/bot** (tem o módulo do job + py7zr). Deploy manual por digest,
como sempre. O wrapper recusa imagem antiga com mensagem clara.

**b) Insumos em `/opt/motor-expansao/data/insumos_crescimento/`.** A árvore esperada:

```
insumos_crescimento/
├── socioeconomico/
│   ├── caged/caged_municipio_mensal_consolidado.csv   # copie o _2020_2026.csv atual com este nome
│   ├── rais/rais_municipio_{2020..2024}.csv
│   ├── cnpj/agg/municipio_ano_dinamismo.parquet
│   ├── cnpj/agg/municipio_ano_setor_dinamismo.parquet
│   ├── cnpj/Municipios.zip
│   └── pib/populacao_6579_serie.csv
├── crescimento_tec/{indices_crescimento_municipal.csv, crescimento_municipio.csv, indices_desenvolvimento_municipal.csv}
├── poc_satelite/data/uf=XX/hex_google_temporal_{2016,2023}.parquet   # 12 UFs: BA CE DF ES GO MG PE PR RJ RS SC SP
└── eixo/_eixo_trajetoria.parquet
```

É ~200 MB de AGREGADOS (o microdado gigante fica de fora, como sempre). **Tudo está na
estação do Juan** (foi ele quem gerou a camada em agosto):

| Peça | Onde está na estação | Tamanho |
|---|---|---|
| `socioeconomico/` | `C:\dados\socioeconomico` (só os agregados da árvore acima) | ~90 MB |
| `crescimento_tec/` | `Área de Trabalho\Crescimento Regional TEC\output\` (os 3 CSVs) | 26 MB |
| `poc_satelite/data/uf=XX/` | `Área de Trabalho\Google Engine\poc_satelite\data\uf=XX\` | 81 MB |
| `eixo/_eixo_trajetoria.parquet` | **regenerar** (a cópia de agosto não ficou no disco): em `Google Engine\poc_satelite\_proposta_camada_motor\prototipo\`, rodar `python p1_base.py && python p2_eixo.py` — o arquivo sai no diretório corrente | pequeno |

O envio é `scp -i ~/.ssh/id_ultra` da estação para a VPS.

## Passo 1 — instalar o wrapper

```bash
install -d -m 0755 /opt/motor-expansao-infra
cp /opt/motor-expansao/app/scripts/cron/run_atualizacao_crescimento.sh /opt/motor-expansao-infra/
chmod +x /opt/motor-expansao-infra/run_atualizacao_crescimento.sh
```

(Antes do `cp`: `cd /opt/motor-expansao/app && git pull` para o checkout ter o script.)

## Passo 2 — modo seco (OBRIGATÓRIO antes de agendar)

```bash
DRY_RUN=1 /opt/motor-expansao-infra/run_atualizacao_crescimento.sh
```

Confira na saída: o job termina `OK`, a validação diz `artefatos integros`, e o texto
do aviso aparece no stdout (nada é publicado, nada reinicia, nada vai ao Telegram).
Se faltar insumo, a mensagem diz exatamente qual diretório está ausente.

## Passo 3 — primeira rodada real

```bash
/opt/motor-expansao-infra/run_atualizacao_crescimento.sh
```

Validação pós-rodada (a mesma do runbook da camada — `/api/health` NÃO serve para isso):

```bash
docker exec -i motor_expansao_web python - <<'PY'
import json, urllib.request
js = json.load(urllib.request.urlopen("http://127.0.0.1:8899/api/uf/SP", timeout=300))
p4 = [x for x in js["passos"] if x["n"] == 4][0]
print("funil_big", p4["funil_big"], "| cres_mun", len(js.get("cres_mun") or {}),
      "| hexes com cor", sum(1 for h in js["hexes"] if h.get("cres_hex_classe")))
PY
```

Esperado: `funil_big` e `cres_mun` com números (não vazios) e `hexes com cor > 1000`.
E o aviso de sucesso deve ter chegado no chat de ops.

## Passo 4 — agendar (cron + monitor)

```bash
( crontab -l 2>/dev/null
  echo '0 3 5 2,5,8,11 * /opt/motor-expansao-infra/run_atualizacao_crescimento.sh'
  echo '0 12 * * 4 /opt/motor-monitoring/healthcheck_vps.sh crescimento'
) | crontab -
```

(O healthcheck novo vem no mesmo `git pull`: recopie
`/opt/motor-expansao/app/scripts/healthcheck_vps.sh` para `/opt/motor-monitoring/`.)

## Rollback

Reverter a automação = remover as duas linhas do crontab. Reverter uma PUBLICAÇÃO
ruim = o rollback do runbook da camada (`docs/camada_crescimento_municipal.md` §7):
mover os dois parquets para fora do staging e reiniciar o web — o passo 4 degrada
para "indisponível", sem 500.

## Onde olhar quando algo falhar

- Log da rodada: `/var/log/motor-snapshots/atualizacao_crescimento_latest.log`
- O aviso de falha no chat diz a ETAPA (job / prova de legibilidade / restart)
- Alarme de idade: transição OK→FAIL no chat quando o artefato passar de 100 dias
