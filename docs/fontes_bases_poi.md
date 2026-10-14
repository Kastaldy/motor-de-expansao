# Base única de pontos de interesse (POI): fontes e processamento

> Camada de APOIO para o épico BLK-UNI (Inteligência de Unidade). É read-only sobre o M1 e não alimenta nenhum score oficial.
> Montada em 2026-09-25 por Felipe Silva com o Claude Code. Os dados ficam só na estação de trabalho: `data/raw/`, `data/staging/` e `data/analysis/` estão no `.gitignore`.

## 1. Fontes

| fonte | o que é | link | versão | data do download | tamanho bruto |
|---|---|---|---|---|---|
| Receita Federal: CNPJ, dados abertos | Tabela `Estabelecimentos` 0 a 9, mais as tabelas `Cnaes`, `Municipios` e `Motivos` | Página do compartilhamento: https://arquivos.receitafederal.gov.br/index.php/s/gn672Ad4CF8N6TK · Endereço WebDAV usado no download: `https://arquivos.receitafederal.gov.br/public.php/webdav/Dados/Cadastros/CNPJ/2026-09/`, com usuário `gn672Ad4CF8N6TK` e senha vazia · Portal: https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj | Pasta `2026-09`, publicada em 14/09/2026 | 25/09/2026, entre 21:04 e 21:31 | 5,1 GB (41 arquivos, com o CNEFE) |
| IBGE: CNEFE, Censo 2022 | Cadastro Nacional de Endereços para Fins Estatísticos, com endereços geocodificados e a espécie de cada um | https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/Arquivos_CNEFE/CSV/UF/ · Dicionário: `Dicionario_CNEFE_Censo_2022.xls`, na mesma árvore | Arquivos por UF datados de 20/05/2024 | 25/09/2026, na mesma janela | 3,7 GB (27 zips e o dicionário) |
| OpenStreetMap (extratos da Geofabrik) | Extratos regionais: centro-oeste, nordeste, norte, sudeste e sul | `https://download.geofabrik.de/south-america/brazil/<regiao>-latest.osm.pbf` · Licença ODbL, © contribuidores do OpenStreetMap | Extratos de 23/09/2026 | 24/09/2026 | 2,0 GB |

Todas as fontes são públicas e oficiais. O OSM vem de uma comunidade aberta e exige atribuição (ODbL).

### Onde ficam os arquivos brutos
- Receita: `data/raw/receita_cnpj/2026-09/`
- IBGE: `data/raw/ibge_cnefe_2022/UF/`
- OSM: `data/osm_cache/pbf/`

O download usou `data/raw/baixar_bases_poi.sh`: `curl` sequencial, que retoma do ponto em que parou. O log fica em `data/raw/download_bases_poi.log` e todos os arquivos terminaram com rc=0.

## 2. Processamento

Os scripts ficam em `data/analysis/poi/` e rodam um de cada vez, com o `venv-iso`.

| script | entrada | saída em `data/staging/poi/` |
|---|---|---|
| `01_osm_poi.py <regiao>` | PBF regional | `osm_poi_<regiao>.parquet`: nós e ways com tags de atividade (loja, shopping, escola, saúde, alimentação, transporte, academia...). O way vira o centroide dos seus nós. |
| `01b_osm_relacoes.py <regiao>` | PBF regional | `osm_poi_rel_<regiao>.parquet`: os mesmos POIs quando estão mapeados como **relação** multipolygon (shopping grande, campus). O `01` não os via. São 9.755 POIs, 135 deles de `shop=mall`. |
| `01c_osm_malls_poligono.py` | 5 PBFs | `osm_malls_poligonos.parquet`: **polígono** dos 3.551 `shop=mall` (ways e relações), para saber se uma unidade está dentro de um shopping |
| `02_cnefe.py <UF>` | zip do CNEFE | `cnefe_estab_<UF>.parquet`: endereços NÃO residenciais, das espécies 3 (agropecuário), 4 (ensino), 5 (saúde), 6 (outras finalidades) e 8 (religioso). Também gera dois geocodificadores: `cnefe_cep_numero_<UF>.parquet` (por CEP e número) e `cnefe_cep_<UF>.parquet` (por CEP). |
| `03_cnpj.py <n>` e depois `03_cnpj.py --geocodificar <UF>` | `Estabelecimentos<n>.zip` | `cnpj_ativos_<UF>.parquet`: só os estabelecimentos ATIVOS (situação 02), geocodificados pelo CNEFE. |
| `03b_regeocodificar.py --todas` | `cnpj_ativos_<UF>` + CNEFE | Refaz a geocodificação com as regras da v2 (abaixo), no mesmo arquivo. |
| `04_base_unica.py` | as três saídas acima | `base_poi_unica/uf=XX/parte-0.parquet` e `base_poi_unica/resumo_fonte_categoria_uf.csv` |

### Geocodificação do CNPJ (v2, 2026-09-25)
A Receita não publica coordenada. Cada estabelecimento é casado com o CNEFE. Os níveis vão em `geo_nivel`; a participação é a do país:

| nível | regra | % |
|---|---|---|
| `cnpj_cep_numero` | CEP e número batem com o CNEFE, o número não é vazio e o CEP não é de área | 46,9% |
| `cnpj_cep` | centroide ponderado dos endereços do CEP | 22,2% |
| `cnpj_cep_area` | o CEP tem mais de 2.000 endereços (CEP de cidade ou de bairro inteiro). O mesmo número existe em várias ruas, então nem o casamento com o número localiza. | 23,0% |
| `cnpj_cep5` | o CEP não existe no CNEFE (grande usuário, CEP novo): centroide dos endereços com o mesmo prefixo de 5 dígitos | 6,7% |
| `cnpj_sem_coordenada` | nenhum dos anteriores | 1,1% |

**Por que a v1 (72% "exato") estava errada:**
- o número vazio (S/N) casava com o endereço "0" do CNEFE e era rotulado exato;
- em CEP de área, o "exato" era a média de ruas diferentes.

**Para contar numa área a pé**, use ponto só para `cnpj_cep_numero`. Os níveis `cnpj_cep` e `cnpj_cep_area` devem ser **rateados** pela fração dos endereços do CEP (`cnefe_cep_numero_<UF>`, peso `n`) que cai dentro da área; é o que faz `data/analysis/poi/05b_familias_poi.py`. O DF é o caso extremo: 85% em `cnpj_cep`, porque o endereço lá é de quadra.

### Privacidade (regra)
Na leitura do CNPJ são descartados o próprio **CNPJ**, a razão social e o nome fantasia, os telefones, o e-mail e o complemento. MEI e empresário individual identificam pessoas, então esses campos não entram. O que fica: CNAE principal e secundário, matriz ou filial, data de início, CEP, número, bairro, UF e o código de município da Receita.

## 3. A base única

O caminho é `data/staging/poi/base_poi_unica/uf=XX/parte-0.parquet`. São 46.028.012 linhas e cerca de 1 GB, particionadas por UF. A versão atual, de 2026-09-25, já tem a geocodificação v2 e as relações do OSM.

| coluna | conteúdo |
|---|---|
| `fonte` | `osm`, `cnefe` ou `cnpj` |
| `uf`, `h3_r7` | `h3_r7` casa direto com o `hex_id` do motor. A UF de um ponto OSM vem do hex r7 da base H3 Brasil, com o pai r5 como alternativa. |
| `lat`, `lng` | WGS84 |
| `categoria` | Categoria harmonizada. No OSM, pelas regras do `01`. No CNEFE, pela espécie. No CNPJ, pela divisão ou classe CNAE: por exemplo, 9313-1 vira `fitness`, 4771-7 vira `farmacia` e 8531 a 8533 viram `educacao_superior`. |
| `subcategoria` | OSM: `chave=valor`. CNEFE: a espécie. CNPJ: o CNAE principal. |
| `geo_nivel` | `osm`, `cnefe_nv<k>` (nível de precisão do IBGE), `cnpj_cep_numero`, `cnpj_cep`, `cnpj_cep_area`, `cnpj_cep5` ou `cnpj_sem_coordenada` |
| `nome` | Só no OSM, que é nome público do lugar |
| `cnae_principal`, `data_inicio`, `matriz_filial` | Só no CNPJ |
| `multi_estab` | Só no CNEFE: indica se há mais de um estabelecimento no mesmo endereço |
| `id_origem` | OSM: `node/<id>`, `way/<id>` ou `relation/<id>`. CNEFE: o setor censitário. CNPJ: `mun_rf/<código do município na Receita>`. |

Volume por fonte no país:
- **cnpj**: 28,3 milhões de ativos. Os maiores grupos são comércio (6,7 milhões), transporte e logística (2,5 milhões), serviços administrativos (2,4 milhões), indústria, escritório e construção (cerca de 2 milhões cada) e alimentação (1,8 milhão). Há 83.515 CNAEs de academia (9313-1).
- **cnefe**: 16,9 milhões de endereços não residenciais. São 11,7 milhões de estabelecimentos genéricos, 4,1 milhões agropecuários, 580 mil religiosos, 264 mil de ensino e 248 mil de saúde.
- **osm**: 989.105 POIs (979.505 de nós e ways e 9.600 de relações). Os maiores grupos são lazer (193 mil), comércio (189 mil), pontos de ônibus (118 mil), alimentação (77 mil) e escolas (71 mil). Há 7.512 shoppings e 7.841 estações.

### Cautelas de uso
- **Uma empresa com CNPJ ativo não é necessariamente um estabelecimento aberto ao público.** O MEI costuma estar registrado na casa do dono, e muitos CNPJs estão ativos sem operar. Para medir polo de fluxo, dê preferência a filtros por CNAE (varejo, alimentação, saúde, ensino) e ao CNEFE, que foi verificado em campo em 2022.
- **O CNEFE é de 2022; o CNPJ é de set/2026; o OSM, de set/2026.** As três fontes contam a mesma loja por caminhos diferentes. **Não some as três como se fossem contagens independentes.** Use cada fonte como uma variável separada, ou escolha uma por categoria.
- **A cobertura do OSM é desigual:** boa nas capitais e fraca no interior.
- A geocodificação pelo centroide do CEP erra alguns quarteirões. Para análise na escala de isócrona ou hex r7, isso é suficiente. Para contar o que existe a 200 m, não é.

## 4. Como atualizar
1. Baixar a nova pasta mensal da Receita, trocando `2026-09` no script de download. O OSM pode ser atualizado quando quiser. O CNEFE só muda no próximo Censo.
2. Rodar `03_cnpj.py 0` até `03_cnpj.py 9`, depois `03_cnpj.py --geocodificar <UF>` para cada UF, e por fim `04_base_unica.py`. Tudo roda um de cada vez. A etapa do CNEFE (`02`) só precisa ser refeita se o CNEFE mudar.
3. Atualizar as datas deste documento.
