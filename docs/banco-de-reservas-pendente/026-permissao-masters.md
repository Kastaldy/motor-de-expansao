# 026 — Capacidade `masters.ver`: a tela Masters do piloto

> **Rascunho para o `banco-de-reservas`.** O desenho do esquema mora lá (convenções §7), e este
> arquivo existe no motor só porque aquele repositório não estava ao alcance de quem escreveu a
> mudança. O primeiro bloco ```sql abaixo é, byte a byte, o que vai em
> `src/motor_expansao/db/migracoes/026-permissao-masters.sql` — quem trouxer este documento
> para `banco-de-reservas/sql/` deve conferir com
> `python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql> --conferir` e então
> apagar esta cópia.

## O que a migration cria

Pedido de 18/11/2026 (DEC-089): uma tela nova no piloto, **Masters**, com um painel por master
franqueado — as unidades em operação e em inauguração, os contratos assinados por fase e a meta de
aberturas do ano e do contrato. Os dados vêm da planilha de levantamento dos masters, que é
confidencial, por isso a tela tem capacidade PRÓPRIA.

| Objeto | Para quê |
|---|---|
| `masters.ver` | Capacidade nova: ver a tela Masters (`GET /api/masters` e `GET /api/masters/{id}`). |

## Decisões de desenho

- **Uma capacidade nova, e não `rede.ver`.** `rede.ver` é a Visão Executiva e vale também para a
  Consultoria; os contratos e as metas dos masters ficam só com Growth e Líderes (decisão de
  18/11/2026). Reaproveitar `rede.ver` daria a tela a quem não deveria vê-la, e daria ao perfil
  `master` (que tem a aba Executiva por `rede.ver_propria`) um ícone que só responderia 403.
- **Só leitura.** Uma capacidade para a lista e o painel: a tela não escreve nada. A planilha
  chega ao piloto por ingestão (`scripts/ingerir_masters.py`), não por tela.
- **Sem tabela nova.** Os dados da tela não moram no banco: são parquets em `data/staging`, só
  com o que a tela mostra, levados à VPS por cópia, como o faturamento do Financeiro.
- **O perfil `master` fica de fora.** Ver a própria meta pelo piloto é outra decisão (e outra
  capacidade); hoje o master vê só a Visão Executiva recortada (025, DEC-087).

## Migration

```sql
BEGIN;

-- A capacidade nova. Descricao com o mesmo cuidado das outras: ela vira ROTULO DE TELA, e a
-- verificacao mede char_length/octet_length para pegar duplo-encoding (convencoes §5).
INSERT INTO permissoes (chave, descricao_permissao) VALUES
  ('masters.ver', 'Ver a tela Masters: contratos, metas e unidades de cada master'); -- GET /api/masters

-- Growth e lideres (decisao de produto de 18/11/2026, DEC-089). Escrito como consulta, e nao com
-- id literal, pelo mesmo motivo da 012: `id_perfil`/`id_permissao` sao BIGSERIAL e dependem da
-- ordem de insercao. A trigger de auditoria do D19 grava `registrado_por` NULO, como na 015.
INSERT INTO perfil_permissoes (id_perfil, id_permissao)
SELECT p.id_perfil, pe.id_permissao
FROM perfis p
JOIN permissoes pe ON TRUE
WHERE (p.nome_perfil, pe.chave) IN (
  ('growth', 'masters.ver'),
  ('lideres', 'masters.ver')
);

COMMIT;
```

## Verificação (não vai para a migration)

```sql
-- Só growth e lideres têm `masters.ver`.
SELECT p.nome_perfil, pe.chave
FROM perfil_permissoes pp
JOIN perfis p ON p.id_perfil = pp.id_perfil
JOIN permissoes pe ON pe.id_permissao = pp.id_permissao
WHERE pe.chave = 'masters.ver'
ORDER BY 1;
```
