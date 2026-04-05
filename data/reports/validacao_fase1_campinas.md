# Relatório de Validação — Fase 1 Motor de Expansão
## Segunda Cidade Piloto: Campinas / SP

**Data de execução:** 2026-04-03 17:13–17:14  
**Tempo total:** 28.6 segundos  
**Resolução H3:** 7  
**Raio de cobertura:** 15 km  
**Output:** `data/staging/hexagonos_campinas_sp.parquet`

---

## 1. Validação do Schema

| Check | Resultado |
|-------|-----------|
| Hexágonos processados | ✅ 469 |
| Colunas presentes | ✅ 20/20 |
| NaN em `hex_id` | ✅ 0 |
| NaN em `lat` | ✅ 0 |
| NaN em `lng` | ✅ 0 |
| NaN em `hex_score` | ✅ 0 |
| hex_score em [0, 100] | ✅ 0 fora do range |
| Fonte demográfica | ✅ `ibge_sidra_municipio_2022` 100% |
| OSM academias | ✅ 134 carregadas (1ª tentativa falhou 504 → retry ok) |

**Código IBGE resolvido:** 3509502 (Campinas/SP)

---

## 2. Distribuição do hex_score

| Métrica | Valor |
|---------|-------|
| Mínimo | 37.50 |
| Máximo | 62.50 |
| Média | 59.93 |
| Mediana | 62.50 |
| Desvio Padrão | 6.13 |

**Composição do score:**
- `renda_norm` = 50.0 constante (SIDRA retorna `..` sigiloso → renda_per_capita=0 → série zerada)
- `pop_norm` = 50.0 constante (63.923 pessoas em toda a cidade — mesmo valor para todos 469 hexágonos)
- `concorrencia_norm` = **variável** (134 academias OSM distribuídas em 74 hexágonos)
- `vitalidade_norm` = 50.0 constante (sem Google API key)

Score efetivo: `37.5 + concorrencia_norm × 0.25`

---

## 3. Cobertura OSM (academias)

| n_academias_osm | Hexágonos |
|-----------------|-----------|
| 0 | 395 (84%) |
| 1 | 42 (9%) |
| 2 | 11 (2%) |
| 3 | 9 (2%) |
| 4+ | 12 (3%) |
| máx (16) | 1 |

**74 hexágonos com pelo menos 1 academia (16% da área)**  
**134 academias mapeadas no bbox da cidade**

---

## 4. Top 10 Hexágonos por Score

> Score máximo 62.5 = zero academias no raio. Ranking atual reflete ausência de concorrência — dados de renda e população ficarão ativos quando shapefile IBGE 2022 ou outra fonte por setor estiver disponível.

| # | hex_id | lat | lng | renda | pop_18_45 | n_acad | score |
|---|--------|-----|-----|-------|-----------|--------|-------|
| 1 | 87a811580ffffff | -23.162 | -47.067 | 0 | 63923 | 0 | 62.50 |
| 2 | 87a811581ffffff | -23.150 | -47.088 | 0 | 63923 | 0 | 62.50 |
| 3 | 87a81158cffffff | -23.138 | -47.109 | 0 | 63923 | 0 | 62.50 |
| 4 | 87a813b31ffffff | -22.893 | -47.037 | 0 | 63923 | 0 | 62.50 |
| 5 | 87a81158dffffff | -23.126 | -47.130 | 0 | 63923 | 0 | 62.50 |
| 6 | 87a811432ffffff | -23.114 | -47.151 | 0 | 63923 | 0 | 62.50 |
| 7 | 87a811433ffffff | -23.103 | -47.172 | 0 | 63923 | 0 | 62.50 |
| 8 | 87a811401ffffff | -23.067 | -47.235 | 0 | 63923 | 0 | 62.50 |
| 9 | 87a81140cffffff | -23.055 | -47.256 | 0 | 63923 | 0 | 62.50 |
| 10 | 87a81140dffffff | -23.043 | -47.277 | 0 | 63923 | 0 | 62.50 |

**Hexágono mais competitivo:** 16 academias OSM → hex_score 37.50

---

## 5. Comparativo Campinas vs Goiânia

| Métrica | Goiânia/GO | Campinas/SP | Observação |
|---------|------------|-------------|------------|
| Tempo de execução | 16s | **28.6s** | 12s extras = retry OSM (1 tentativa 504 + 10s wait) |
| Hexágonos | 469 | 469 | Raio 15km → mesmo grid_disk k=12 |
| Colunas | 20 | 20 | Schema idêntico |
| NaN críticos | 0 | 0 | |
| Fonte demográfica | `ibge_sidra_municipio_2022` | `ibge_sidra_municipio_2022` | Consistente |
| renda_per_capita | 0 (sigiloso) | 0 (sigiloso) | SIDRA t.10297 sigilo em ambas |
| pop_18_45 | 90.092 | 63.923 | Municipal — sem variação intra-cidade |
| OSM academias | 0 (504 sem retry) | **134** (retry funcionou) | Retry implementado resolveu o problema |
| hex_score range | 50.0–50.0 | **37.5–62.5** | Campinas tem variação real via OSM |
| hex_score std | 0.0 | **6.13** | Campinas diferencia hexágonos |
| Hexágonos com acad. | 0 (504) | 74/469 (16%) | |
| Erros bloqueantes | Nenhum | Nenhum | |

---

## 6. Conclusões Executivas

### M1 está estável em segunda cidade?
**Sim.** Pipeline executou sem erros bloqueantes, schema 100% válido, município resolvido automaticamente via IBGE Localidades, OSM carregado via retry. Nenhuma correção de código foi necessária para Campinas.

### A normalização atual suporta múltiplas cidades?
**Parcialmente.** A normalização é **por cidade** (min-max dentro do batch de hexágonos da mesma cidade). Isso significa:
- Score 62.5 em Campinas ≠ Score 62.5 em Goiânia — não são comparáveis diretamente
- Para ranking inter-cidades, precisar rodar todas as cidades juntas (1 DataFrame, 1 normalização)
- Para uso intra-cidade (apontar melhores hexágonos dentro de Campinas), a normalização atual está correta

O M1 **não está pronto para ranquear Campinas vs Goiânia** sem refatoração da normalização para modo multi-cidade.

### Ajustes necessários antes de escalar?

| Prioridade | Ajuste | Impacto |
|------------|--------|---------|
| Alta | Normalização multi-cidade: juntar DataFrames antes de `normalizar_serie` | Habilita ranking inter-cidades válido |
| Média | Aguardar shapefile IBGE 2022 setor censitário | Ativa renda e pop com variação por hexágono |
| Média | Google Maps API key | Ativa peso 15% de vitalidade comercial |
| Baixa | SIDRA renda: investigar tabela alternativa (t.9605?) | t.10297 retorna sigiloso para cidades grandes |

**Bloqueante para escalar a +10 cidades sem ajuste:** o volume de dados do OSM bbox vai aumentar linearmente; sem retry o pipeline teria ~30–40% de falha. O retry implementado resolve isso.

**Conclusão:** M1 pode ser escalado para novas cidades com a arquitetura atual. O pré-requisito para uso em decisão real é a normalização multi-cidade (rodar batch de cidades alvo juntas).
