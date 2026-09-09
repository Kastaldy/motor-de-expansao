"""Atualizacao TRIMESTRAL da camada de crescimento municipal (BLK-TRAJ-02 / DEC-052).

O que vive aqui e' o lado TESTADO e EMBARCAVEL (viaja na imagem da API) do ciclo de
atualizacao que ate' a DEC-052 era 100% manual e sem cadencia:

    caged.py      baixa os meses NOVOS do Novo CAGED (FTP do PDET) e atualiza o CSV
                  consolidado que a cadeia 01..10 consome — sem meses hardcoded e
                  sem caminho fixo de maquina (armadilhas ja' pagas uma vez).
    atualizar.py  orquestra a cadeia 01..10 de `data/reports/crescimento/` na ordem
                  OBRIGATORIA, em MOTOR_DATA_DIR de rascunho (nunca sobre o staging
                  vivo), valida o resultado e publica por rename atomico.
    validar.py    o portao do artefato: rejeita a assinatura da execucao parcial
                  (15 de 33 colunas), dominio fechado quebrado e cobertura mutilada.
    aviso.py      o texto do chat de atualizacao (bot Telegram "Paulo"), nos dois
                  desfechos — sucesso e falha — sem nunca logar token.

READ-ONLY sobre o M1: nada aqui escreve em `data/outputs/`. Os unicos artefatos
gravados sao `staging/crescimento_municipal.parquet` e `staging/crescimento_hex.parquet`
(camada OPCIONAL do passo 4 do piloto) e o CSV consolidado do CAGED nos INSUMOS.

O agendamento (cron da VPS), o restart do web e a instalacao sao papel do wrapper
`scripts/cron/run_atualizacao_crescimento.sh` — e a aplicacao na VPS e' sempre ato
manual do dono (CLAUDE.md §6). Contratos e runbook: docs/camada_crescimento_municipal.md
e docs/infra_producao.md (secao da atualizacao trimestral).
"""
