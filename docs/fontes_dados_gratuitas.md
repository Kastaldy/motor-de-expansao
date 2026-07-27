# Fontes de Dados Gratuitas do M1

Referência do pipeline territorial nacional da Fase 1.

Este documento descreve apenas o que está ativo no fechamento oficial do M1. A fonte oficial do projeto continua sendo `CLAUDE.md`.

## Resumo executivo

No MVP nacional atual:

- IBGE é a base oficial do enriquecimento estrutural.
- `hex_score_estrutural` é a base estrutural oficial.
- `score_priorizacao` é o score oficial do M1.
- setor censitário continua desejável, mas não é pré-requisito operacional.
- fallback municipal do IBGE é explícito, auditável e aceito como contrato atual.
- OSM não participa do fechamento executivo nacional.

## 1. IBGE

### Fontes ativas

- Malha oficial do Brasil por UF:
  `https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&intrarregiao=UF&qualidade=maxima`
- Malha oficial do Brasil:
  `https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&qualidade=maxima`
- Malha municipal por UF:
  `https://servicodados.ibge.gov.br/api/v3/malhas/estados/{uf}?intrarregiao=municipio&formato=application/vnd.geo+json&qualidade=maxima`
- SIDRA renda municipal:
  tabela `10295`, variável `13431`
- SIDRA população municipal total (alterado 2026-05-15; trava 18-45 removida):
  tabela `4709`, variável `93`, período `last`/`2022`

### Fallback oficial atual

Quando setor censitário não estiver disponível:

1. o hexágono recebe `cod_municipio` via malha municipal oficial do IBGE
2. renda e população vêm do SIDRA municipal
3. o dataset registra:
   - `nivel_geografico_ibge=municipio`
   - `fallback_setor_censitario=true`
   - `motivo_fallback_setor`
   - `fonte_renda`
   - `fonte_populacao`
   - `fonte_geometria_ibge=ibge_malha_municipal_2022`
   - `metodo_atribuicao_municipio`

### Cache local

- `data/raw/ibge/malha_uf_brasil.geojson`
- `data/raw/ibge/malha_brasil.geojson`
- `data/ibge/municipios_{UF}.geojson`
- `data/ibge/demografia_municipios_2022.parquet`

## 2. OSM

OSM permanece suportado tecnicamente para fluxos locais, validações pontuais e retomada futura da camada competitiva.

No entanto, para o MVP nacional atual:

- `M1_OSM_ENABLED=false`
- `osm_status=nao_aplicado_mvp_nacional` nos outputs oficiais
- nenhum ranking executivo depende de `n_academias_osm`, `score_concorrencia` ou `hex_score_final`

## 3. Google Places

Google Places continua opcional e fora do fechamento nacional oficial do M1.

Sem chave:

- `score_vitalidade` pode permanecer neutro em fluxos locais
- isso não afeta o pipeline oficial nacional, que fecha com `hex_score_estrutural` como base e `score_priorizacao` como score oficial

## 4. Score oficial

```python
renda_pct_nacional = percentil_nacional(renda_per_capita)
pop_pct_nacional = percentil_nacional(populacao_proxy)

hex_score_estrutural = 100 * (
    0.40 * renda_pct_nacional +
    0.60 * pop_pct_nacional
)

score_priorizacao = clip(hex_score_estrutural + ajuste_executivo, 0, 100)
```

Regras:

- normalização nacional por percentil
- `hex_score_estrutural` fica separado do `ajuste_executivo`
- `pop_total` é a fonte canônica de população (trava 18-45 removida em 2026-05-15; `populacao_proxy` = `pop_total`)

> **Pesos canônicos: `renda=0.40`, `pop=0.60`.** Fonte de verdade:
> `PESOS_HEX_SCORE_ESTRUTURAL` em `src/motor_expansao/core/constants.py`, espelhada no
> `CLAUDE.md` §3 e ratificada pela **DEC-001** (2026-05-31: backtest BLK-SCORE-02 deu Spearman
> rho ~= -0.004 com IC95% cruzando zero -> pesos mantidos INALTERADOS).
> **Correção de 2026-07-27:** este bloco dizia `0.60*renda + 0.40*pop` — os pesos foram invertidos
> no código em `ef325d8` (2026-05-12, aprovação de diretoria 2026-04-24) e das três cópias da
> fórmula só duas (`CLAUDE.md` e `README.md`) foram atualizadas na época. **Não confundir** com
> `score_dominio_hibrido` / `score_setor_2022_calibrado`, onde `0.60/0.40` É legítimo — é essa
> coincidência que fez o erro passar despercebido por ~2 meses.

## 5. Saídas oficiais

- `data/staging/brasil_estrutural.parquet`
- `data/staging/brasil_priorizados.parquet`
- `data/staging/hexagonos_brasil_oportunidades.parquet`
- `data/outputs/hexagonos_brasil_dashboard.parquet`
- `data/outputs/top_oportunidades_resumo.csv`
- `data/outputs/resumo_por_uf.csv`

## 6. Colunas de auditoria esperadas

- `fonte_demografica`
- `fonte_renda`
- `fonte_populacao`
- `nivel_geografico_ibge`
- `fallback_setor_censitario`
- `motivo_fallback_setor`
- `fonte_geometria_ibge`
- `metodo_atribuicao_municipio`
- `data_referencia_ibge`
- `score_oficial`
- `score_oficial_nome`
- `osm_status`

## 7. Decisão registrada

O MVP nacional da Fase 1 fecha com pipeline estrutural reproduzível e auditável em cima do IBGE. OSM e demais fontes complementares ficam preservados como capacidade futura, mas não como dependência obrigatória do fechamento nacional.
