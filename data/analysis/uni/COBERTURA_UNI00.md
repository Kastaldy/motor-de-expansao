# Painel BLK-UNI-00 — cobertura (critério de aceite)

Scripts `01_depara.py` a `05_cobertura_dicionario.py` em `data/analysis/uni/`. Universo: **98 unidades** da rede comparável (+7 que o motor exclui — studio, administração etc. — só no de-para).

- **Dado pessoal:** nenhuma coluna (checado por nome). Lifetime e TotalPass entram só agregados por unidade. A cópia do cadastro foi reduzida aos campos usados, sem franqueado ou consultor.
- **Reprodutível:** todos os insumos estão em `insumos_vps/`, `insumos_locais/` e `../isocronas/`. Nada é lido do scratchpad da sessão, exceto o `06_teste_poi.py` do teste de POI, que só lê o repositório.

## Fato unidade × mês (`fato_unidade_mes.parquet`)

- 2,275 linhas, 98 unidades, 2022-04 a 2026-09. A Growth começa em 2022-04; o Financeiro fecha até 2026-08.
- **Receita válida** (Financeiro, mês completo, operação cheia): 2,088 unidade-mês, de 95 unidades.
- Receita vazia por regra: {'sem_financeiro_neste_mes': 98, 'financeiro_zero_com_ativos (mes sem lancamento)': 16, 'financeiro_por_alias_declarado (SÃO CARLOS - SP -> SAO CARLOS - CENTRO - SP)': 5}.
- Correção manual: 0 (Guarujá ago/26, informado pelo Felipe).
- Canibalização no tempo: 971 unidade-mês com outra Ultra já aberta na isócrona de carro 10 min.

## Atributos por unidade (`dim_unidade.parquet`): cobertura por bloco

| bloco | unidades com dado (de 98) | coluna-chave |
|---|---|---|
| Tamanho (metragem, vagas) | 54 | `tam_metragem_m2` |
| Cadastro | 92 | `cad_tier_totalpass` |
| Isócronas (pop, renda, oferta) | 97 | `iso_pop__carro_10` |
| Concorrência com alunos reais | 97 | `conc_cap_real__carro_10` |
| Sobreposição com outras Ultras | 97 | `canib_frac_max__carro_10` |
| Crescimento municipal | 97 | `cres_dim_media` |
| Crescimento do hexágono (satélite) | 89 | `cres_hex_taxa` |
| POIs | 95 | `poi_F1` |
| TotalPass: plano da Ultra no feed | 51 | `tp_plano_ultra` |
| TotalPass: concorrência com ≥ 3 preços | 97 | `tp_ord_mediana_c10` |
| Wellhub: plano da Ultra no feed | 59 | `wh_plano_ultra` |
| Wellhub: concorrência com ≥ 3 preços | 96 | `wh_ord_mediana_c10` |
| Lifetime: retenção EB | 88 | `lt_eb_retencao_60d` |
| Lifetime: prob. 90d utilizável | 76 | `lt_prob_cancel_90d_media` |
| Rampa observável | 86 | `rampa_ativos_m1` |
| Patamar (estabilizou) | 63 | `rampa_patamar_ativos` |

## Erros de dado conhecidos (linha mantida, atributo afetado anulado)

- `boa-vista-ba`: coord_baixa
- `lago-sul-df`: isocrona_pe_degenerada (0,16 km2): atributos a pe anulados
- `vicente-pires-rua-8-df`: coord_baixa
- `domingos-ferreira-pe`: coord_baixa
- `boqueirao-sp`: coord_baixa
- Inauguração placeholder 23/08/2021: ['aclimacao-sp', 'mooca-sp', 'plaza-sul-sp', 'vila-mariana-sp']. No fato, `mes_vida` = NaN e `mes_vida_minimo` = meses desde o 1º faturamento (limite inferior); a rampa não é observável.
- Anomalias a conferir (não excluídas): [['brasilandia-sp', 'vale de receita -45% out/25-mai/26 com ativos estaveis'], ['suzano-sp', '-52% de ativos abr-ago/26 (agregadores 2.964 -> 919)'], ['vila-guilherme-sp', 'vale de receita -45% out/25-mai/26 com ativos estaveis']]

## Lacunas por unidade

- Sem nenhum mês de Financeiro: [('nucleo-bandeirante-df', '2026-09-18'), ('freguesia-rj', '2026-09-08'), ('via-brasil-shopping-rj', '2026-09-23')]. Abriram em set/2026 e ainda não têm mês fechado.
- Casadas no Financeiro só por nome, porque o layout novo do Financeiro não traz código: ver `depara_divergencias.md`.
- Sem metragem: 44. A falta NÃO é aleatória: o xlsx cobre as unidades maduras em abr/2026.
- Crescimento: município do hexágono pelo universo completo em 97 unidades e por nome em 0. 14 unidades têm a cidade do cadastro diferente do município do hexágono. Em quase todas é grafia ou região metropolitana (RA do DF, Grande Rio); a exceção é Sagrada Família, com pino em Cuiabá e cadastro em Rondonópolis, marcada como erro.
- Plano da Ultra: TotalPass no feed 51 e no cadastro 62; Wellhub 59 / 69. O casamento aceita até 300 m (o piloto usa 120 m); a distância fica gravada. Em 10 unidades o cadastro de agosto diz TP1+ e o feed de setembro diz TP 2.
- Lifetime: 88 unidades com retenção EB. Uso da prob. 90d: {'absoluto': 48, 'so_ranking': 28, 'nao_usar': 12, 'sem_lifetime': 10}.
- Rampa: 86 observáveis; 63 estabilizaram até hoje (a mediana de 6 meses reproduz o estudo da Growth).

## Fora do painel ou pendente (com motivo)

- **Retenção de 12 meses da coorte de abertura e pré-venda:** colunas `rampa_ret12_*` e `rampa_n_alunos_prevenda` ficam NaN. Precisam de export agregado por unidade do Projeto Lifetime, que é base aluno a aluno.
- **Tipo de imóvel e fachada:** não há fonte para a Ultra (colunas reservadas). O proxy é `poi_em_shopping`.
- **Demografia GeoFusion 1 km do xlsx:** fora, por regra. É uma foto antiga e o Censo 2022 nas isócronas a substitui.
- **Engenharia do Corpo:** fora deste painel, que é da Ultra. Ela é amostra de replicação dos testes (`data/analysis/poi`, `data/analysis/isocronas`).
- **Corte de 'tier alto' nos planos:** não criado, porque é decisão de negócio. As features relativas (`pct_acima_ultra`, `gap_ord`) não dependem de corte.
- **NPS por canal:** não ingerido. A coluna `nps` crua mistura canais.
- **Demanda revelada TotalPass:** só no arquivo `LOCAL_` (procedência a confirmar); a cobertura está em `LOCAL_COBERTURA_demanda_totalpass.md`.

## Cautelas de tempo (não usar como preditor de meses anteriores sem pensar)

- **Lifetime** (2026-04..08), **planos** (set/2026), **concorrência** e **canibalização estática** (hoje), **POI** (CNPJ de set/2026 com estoque < 2025; OSM set/2026) e **cadastro** (ago/2026) são fotos atuais.
- Para a exploração até dez/2025 (UNI-01), o que existe no tempo é o fato mensal: receita, ativos, agregadores, churn e canibalização no tempo.
- Rampa: só em janelas a partir de `rampa_competencia_liberacao`. Os `rampadesc_*` são descrição ou desfecho.