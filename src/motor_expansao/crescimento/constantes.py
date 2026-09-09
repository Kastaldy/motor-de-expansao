"""Constantes da cadencia trimestral — fonte UNICA dos numeros que o shell repete.

A armadilha que este arquivo mata: a mesma grandeza escrita em dois lugares nao da'
erro, ela DESENCONTRA (cambio duplicado no motor argentino, `H3_RES` em 8 arquivos).
O shell (`scripts/healthcheck_vps.sh`, `scripts/cron/run_atualizacao_crescimento.sh`)
nao importa Python, entao repete estes valores por texto — e
`tests/unit/test_crescimento_atualizacao.py` compara os dois lados e reprova o PR
que mudar um sem o outro.
"""

#: Limiar do monitor de idade (dias). Um trimestre (~92) + folga de retentativa.
#: Paridade: default de MONITOR_CRESCIMENTO_MAX_DIAS em scripts/healthcheck_vps.sh.
LIMIAR_IDADE_DIAS = 100

#: Meses da rodada trimestral (crontab `0 3 5 2,5,8,11 *`): dia 5 de fev/mai/ago/nov,
#: quando o trimestre-calendario anterior ja' esta' inteiro no FTP do PDET (lag ~40d).
#: Paridade: linha de crontab documentada em scripts/cron/run_atualizacao_crescimento.sh.
MESES_CRON = (2, 5, 8, 11)
