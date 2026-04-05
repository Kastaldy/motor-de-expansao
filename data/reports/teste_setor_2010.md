# Teste Paralelo - Setor Censitario IBGE 2010

Execucao real pendente de insumos locais de setor censitario 2010.

- este relatorio nao faz parte do pipeline oficial da Fase 1
- o experimento isolado esta implementado em `jobs/pipelines/teste_setor_censitario_2010.py`
- outputs reais serao gravados apenas em `data/staging/teste_setor_2010/` e `data/outputs/teste_setor_2010/`
- comando base:

```bash
python jobs/pipelines/teste_setor_censitario_2010.py \
  --cidade "Sao Paulo/SP" \
  --cidade "Goiania/GO" \
  --cidade "Campinas/SP" \
  --setores-root "CAMINHO_DOS_INSUMOS_2010"
```
