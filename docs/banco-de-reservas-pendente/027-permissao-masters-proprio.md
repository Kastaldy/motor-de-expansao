# 027 — Capacidade `masters.ver_proprio`: o master vê o próprio painel na tela Masters

> **Rascunho para o `banco-de-reservas`.** O desenho do esquema mora lá (convenções §7), e este
> arquivo existe no motor só porque aquele repositório não estava ao alcance de quem escreveu a
> mudança. O primeiro bloco ```sql abaixo é, byte a byte, o que vai em
> `src/motor_expansao/db/migracoes/027-permissao-masters-proprio.sql` — quem trouxer este documento
> para `banco-de-reservas/sql/` deve conferir com
> `python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql> --conferir` e então
> apagar esta cópia.

## O que a migration cria

Pedido de 19/11/2026 (emenda 2 da DEC-089): os masters franqueados têm login próprio (perfil
`master`, 025, DEC-087), e, ao clicar em "Masters" na barra lateral, cada um abre direto no PRÓPRIO
painel — o crescimento possível no território, o mapa, onde abrir, onde expandir, a meta e o botão
do relatório. Nunca o de outro master.

| Objeto | Para quê |
|---|---|
| `masters.ver_proprio` | Capacidade nova: ver a tela Masters RECORTADA ao próprio painel. |

## Decisões de desenho

- **Uma capacidade nova, e não `rede.ver_propria`.** Aquela é a Visão Executiva recortada (025);
  esta é a tela Masters recortada (escolha do Juan em 19/11/2026: as duas coisas separadas, cada
  uma concedida por si). O gate só a aceita no lugar de `masters.ver` numa allowlist FECHADA das
  rotas de leitura da tela (`acesso.rota_dos_masters_proprios`), e cada rota recorta o master pedido.
- **O recorte é pelo nome.** O master da tela é o do login cujo `nome_usuario` bate com o nome do
  master (o titular da planilha, ou uma das pessoas de um titular composto); sem nome que bata, a
  lista sai VAZIA (falha fechada). Sem tabela nova: o vínculo é o próprio cadastro do usuário.
- **Só o perfil `master`.** Growth e Líderes já têm `masters.ver` (026) e veem todos.

## Migration

```sql
BEGIN;

-- A capacidade nova. Descricao com o mesmo cuidado das outras: ela vira ROTULO DE TELA, e a
-- verificacao mede char_length/octet_length para pegar duplo-encoding (convencoes §5).
INSERT INTO permissoes (chave, descricao_permissao) VALUES
  ('masters.ver_proprio', 'Ver o próprio painel na tela Masters (o master do login)'); -- GET /api/masters/*

-- So' o perfil `master` (decisao de produto de 19/11/2026, emenda 2 da DEC-089). Escrito como
-- consulta, e nao com id literal, pelo mesmo motivo da 012: `id_perfil`/`id_permissao` sao
-- BIGSERIAL e dependem da ordem de insercao. A trigger de auditoria do D19 grava
-- `registrado_por` NULO, como na 015.
INSERT INTO perfil_permissoes (id_perfil, id_permissao)
SELECT p.id_perfil, pe.id_permissao
FROM perfis p
JOIN permissoes pe ON TRUE
WHERE (p.nome_perfil, pe.chave) IN (
  ('master', 'masters.ver_proprio')
);

COMMIT;
```

## Verificação (não vai para a migration)

```sql
-- Só o perfil master tem `masters.ver_proprio`.
SELECT p.nome_perfil, pe.chave
FROM perfil_permissoes pp
JOIN perfis p ON p.id_perfil = pp.id_perfil
JOIN permissoes pe ON pe.id_permissao = pp.id_permissao
WHERE pe.chave = 'masters.ver_proprio'
ORDER BY 1;
```
