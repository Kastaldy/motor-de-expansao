---
name: registrar-decisao
description: Registra uma nova decisão (DEC) do projeto SEM inchar o CLAUDE.md — cria docs/decisions/DEC-0XX.md com o corpo completo e insere só a linha-índice de 1 linha no §8. Use ao fechar uma decisão de arquitetura, produto, score ou governança que hoje viraria uma "DEC-XXX" no CLAUDE.md §8. Palavras-gatilho: "registrar decisão", "nova DEC", "criar DEC", "/dec".
---

# /registrar-decisao — registra uma DEC sem re-inchar o CLAUDE.md

Guarda a estrutura decidida no ciclo do §8 (PR de 2026-07-19): o **corpo** de cada decisão vive
em `docs/decisions/DEC-0XX.md`; o `CLAUDE.md` §8 guarda só **1 linha-índice** por DEC. Esta skill
executa esse contrato para que o §8 nunca volte a crescer.

## Quando usar
Ao concluir uma decisão que precisa de registro canônico (mudança de rumo, aprovação de arquitetura/
contrato, desvio de guardrail, supersessão de bloco). NÃO use para bookkeeping de ciclo comum (isso é
`tasks/completed.md`).

## Passos

1. **Descobrir o próximo ID.** Liste `docs/decisions/DEC-*.md`, pegue o maior número e some 1.
   Respeite gaps já reservados (ex.: `DEC-015` é reservado — a numeração pulou 014→016). Nunca reutilize
   um número.

2. **Criar o arquivo `docs/decisions/DEC-0XX.md`** (LF; `docs/**/*.md` é `eol=lf` no `.gitattributes`),
   começando com `### DEC-0XX — <título curto>` e seguindo o formato dos vizinhos:
   ```
   ### DEC-0XX — <título>
   - ID: DEC-0XX | Data: <AAAA-MM-DD> | Criticidade: <Baixa|Média|Alta|Crítica|Estratégica> (<por quê>)
   - Status: <APROVADA por <quem> em <data> | PROPOSTA | SUPERSEDED por DEC-YYY>
   - Decisão: <o que muda, em 1-3 frases>
   - Evidência-chave: <dado/arquivo que sustenta; cite file:line ou relatório>
   - Relação com DECs anteriores: <intacta / supersede / emenda — cite os números>
   - Referências: <backlog/handoff/docs relevantes>
   ```
   Emendas futuras a esta DEC entram **neste arquivo** (como `**Emenda <data>:** ...`), NUNCA no índice.
   Não é preciso repetir os **invariantes vigentes** (M1 read-only, merge por criticidade, acentuação,
   CSV/encoding, deploy-manual) — eles estão no callout do §8 e são impostos por `loop_guard.py`.

3. **Inserir 1 linha no índice do `CLAUDE.md` §8** (preserve o EOL do arquivo — CLAUDE.md é CRLF), na
   ordem numérica, na tabela `| DEC | Data | Criticidade | Decisao | Status |`:
   ```
   | [DEC-0XX](docs/decisions/DEC-0XX.md) | <AAAA-MM-DD> | <Criticidade> | <título> | <APROVADA|...> |
   ```
   **NÃO cole o corpo no CLAUDE.md.** Se a nova DEC supersede/emenda outra, atualize o Status da linha da
   DEC afetada (ex.: `SUPERSEDED por DEC-0XX`) — o corpo do detalhe fica no arquivo dela.

4. **Adicionar a linha em `docs/decisions/README.md`** (lista de links, mesma ordem).

5. **Verificar (gate):** rode
   ```
   python -m pytest tests/unit/test_claude_md_size.py -q
   ```
   Os dois testes devem passar: (a) `CLAUDE.md` continua sob o teto de linhas; (b) o conjunto de IDs
   linkados no §8 == conjunto de arquivos em `docs/decisions/` (sem drift). Se o teto estourar, é sinal de
   que algo além do índice cresceu — mova detalhe para `docs/`, não relaxe o teto sem decisão.

## Guardrails
- READ-ONLY sobre o M1: registrar uma DEC não altera `score_priorizacao`/pesos/artefatos (a menos que a
  própria DEC seja uma mudança de M1 aprovada — nesse caso o código do M1 é um PR à parte, Crítico).
- CLAUDE.md está no CODEOWNERS → o PR que mexe no §8 exige review de code owner + label `aprovado-humano`.
- Uma DEC = um arquivo + uma linha. Nunca duas fontes do mesmo corpo.
