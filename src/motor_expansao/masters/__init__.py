"""Masters franqueados (camada paralela, READ-ONLY sobre o M1).

O que a Ultra combinou com cada master (território, prazo e meta de aberturas, na config
`data/ultra/masters/territorios.json`) e o que ele tem hoje (inauguradas e assinadas, na planilha
de levantamento `Masters_Ultra_Territorios_e_Unidades.xlsx`). As duas fontes são CONFIDENCIAIS e
ficam fora do git.

* `territorios` e `dados`: lêem a config e a planilha.
* `meta`: a meta de aberturas do ano, trimestre a trimestre.
* `ingestao`: planilha + config -> parquets sem dado pessoal em `data/staging` (DEC-089), o que o
  piloto lê; quem roda é `scripts/ingerir_masters.py`.
* `painel`: o painel de cada master na tela Masters do piloto, com as datas de inauguração da
  base do Growth (que o motor atualiza todo dia).

Nada aqui lê ou grava `score_priorizacao`, pesos ou artefatos oficiais do M1.
"""
