# Contrato — `GET /api/metodologia` (painel de metodologia do Mapa)

> **Status:** [canônico] · **Origem:** PR #185 (2026-08-05), reparado antes do merge ·
> **Implementação:** `montar_metodologia()` em `web/server/app.py` ·
> **Consumidor:** `web/src/components/MethodologyPanel.tsx` ·
> **Contrato travado por:** `tests/contracts/test_metodologia_espelha_o_funil.py`

## O que é

A gaveta "Metodologia" da tela **Mapa** do piloto web. Explica as camadas do funil para **quem lê a
tela**, não para quem escreveu o código: o que cada camada pergunta, com que régua corta, de onde
vem cada número e que limite conhecido ele tem.

**READ-ONLY e puro.** O endpoint não lê Parquet, não toca DataFrame e não calcula nada: só formata
constantes que o próprio funil usa. Nenhum número exibido é recomputado.

## Por que ele é perigoso (e por que tem teste de contrato)

O painel é um **manual publicado na mesma tela que o resultado**. Quando ele diverge do funil, o
usuário não vê um bug — vê uma explicação convincente e errada, e decide com ela. É a classe de
defeito mais cara deste endpoint, e ela **já aconteceu duas vezes**:

1. **Faixas extintas.** O painel nasceu publicando `Quente ≥ 90`, `Alta ≥ 6.000 alunos` e
   `Agora/Próximo/Fila` enquanto o funil, depois do BLK-MAPA-FAIXAS-01, já etiquetava
   Desfavorável…Excelente, Saturado…Livre e as faixas de oportunidade do M1. Os dois lados estavam
   verdes no CI.
2. **Seis afirmações factualmente erradas** sobre calibração, insumos do score, ponderação da oferta
   concorrente, causa do residual zero, origem da população e fonte da oferta Ultra.

Por isso a regra: **as faixas são DERIVADAS, nunca escritas à mão.** `_faixas_potencial()`,
`_faixas_residual()`, `_faixas_competitivas()` e `_faixas_m1()` leem `constants.FAIXAS_MAPA_*`,
`FAIXA_LABELS` e `FAIXA_ORDEM` — as mesmas listas que o `_etiqueta` usa e que a legenda do mapa
desenha. Trocar a régua num lugar troca no outro, ou o teste de contrato quebra.

## Payload

```
{
  "intro":   str,
  "fontes":  [ {"nome": str, "detalhe": str} ],
  "camadas": [ {
      "n":        int,          # 1..N, na ordem do funil
      "titulo":   str,
      "pergunta": str,          # o que a camada responde, em linguagem de quem decide
      "corte":    str,          # a régua que ela aplica, com os números vindos das constantes
      "metricas": [ {
          "nome":     str,
          "coluna":   str,      # nome da coluna no Parquet — rastreabilidade
          "fonte":    str,      # tem que casar com um "nome" de `fontes`
          "resumo":   str,      # o que o número significa
          "regra":    str,      # como é calculado, em português corrido
          "ressalva": str       # OPCIONAL: limite conhecido do número
      } ],
      "faixas":   [ {"etiqueta": str, "condicao": str, "tom": str, "escopo": str} ],
      "nota":     str           # OPCIONAL: ressalva de leitura da camada inteira
  } ],
  "parametros": [ {"nome": str, "valor": str} ]
}
```

### O campo `escopo` das faixas

`""` (vale nos dois), `"municipio"` ou `"uf"`. Existe porque **a mesma camada pode rotular por
bases diferentes conforme a tela**: no mapa de um município a camada 3 é competitiva (Livre /
Adensar / Disputa, do `_etiqueta` ramo `"conc. 2 km"`), e na visão do estado ela mostra a faixa de
demanda do **melhor hexágono** do município (`_melhor_faixa_por_municipio`). O front filtra com
`!f.escopo || f.escopo === escopo` (`MethodologyPanel.tsx`); o teste de contrato usa a mesma regra.

### Acentuação

Todo texto do payload é **texto de usuário** e vai acentuado. As **chaves** (`etiqueta`, `condicao`,
`escopo`, `metricas`, `parametros`) e os **valores de enum** (`escopo: "municipio"` / `"uf"`, `tom:
"green"|"amber"|"gray"|"blue"|"red"`) são identificadores e nunca recebem acento — CLAUDE.md §2.

> **Aviso para reuso em PDF:** o payload usa `≥` (U+2265) e travessão, que estão **fora de
> latin-1**. Em React renderizam normalmente; no gerador de PDF (`fpdf2`, core font Helvetica)
> virariam `"?"` em silêncio. Sanitizar antes de reaproveitar este texto em relatório.

## Defeito conhecido em aberto

**As faixas publicadas incluem faixas inalcançáveis** — o corte de cada camada coincide com o piso
da última faixa da régua, então o chip do ranking é constante (camada 2: corte de 2.000 alunos =
score 80 = piso de "Livre"; 8 municípios de 2.000 a 40.000 alunos saem todos "Livre"). O painel
agrava ao publicá-las como "etiquetas do ranking" no mesmo cartão que declara o corte. Tratado em
**BLK-MAPA-CHIP-01**; a decisão de produto já tomada é trocar o chip pela leitura em unidades.

**Cuidado ao escrever teste para isso:** o contrato atual valida chamando `_etiqueta` diretamente,
com valores que o funil nunca entrega (`n_concorrentes_est` = 2 e 99, quando a base do passo 3 é
`white`, com `n == 0`). Passa verde sobre vocabulário inalcançável. Teste novo deve exercitar as
etiquetas **através de `montar_funil` / `montar_funil_uf`**.

## Ver também

- [arquitetura_app_atual.md](arquitetura_app_atual.md) — arquitetura das 3 superfícies do piloto.
- [modelo_mercado_hexagonos.md](modelo_mercado_hexagonos.md) — de onde vêm residual, oferta
  ponderada por distância e o gate do SAM que o painel descreve.
- `src/motor_expansao/dashboard/constants.py` — `FAIXAS_MAPA_POTENCIAL`, `FAIXAS_MAPA_DEMANDA`,
  `FAIXA_LABELS`, `FAIXA_ORDEM`: a fonte da verdade das faixas.
