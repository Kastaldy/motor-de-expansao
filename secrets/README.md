# secrets/ — Cofre encriptado de segredos do projeto

## Proposito

Este diretorio guarda **somente** as versoes encriptadas (SOPS+age) dos segredos
que vivem em producao no VPS (`/opt/motor-expansao/app/`). Valores reais em
texto puro **NUNCA** ficam aqui — eles existem apenas:

1. Em memoria durante uma sessao `sops <arquivo>` (editor abre desencriptado);
2. Em disco no VPS apos `sops -d` no momento do deploy;
3. No cofre offline (gestor de senhas / pen drive criptografado) do operador.

Qualquer arquivo `.dec`, `.plain.*` ou similar e tratado como vazamento e ja
esta no `.gitignore`.

## Convencao de nomes

| Sufixo            | Tipo SOPS                            | Uso                                |
| ----------------- | ------------------------------------ | ---------------------------------- |
| `*.enc.yaml`      | YAML (criptografa apenas valores)    | Authelia configuration/users       |
| `*.enc.env`       | dotenv (`encrypted_regex: ^.*$`)     | `.env` com `AUTHELIA_*` etc.       |
| `*.enc.txt`       | texto simples                        | (sem uso hoje)                     |
| `*.enc`           | binario opaco                        | `authelia/db.sqlite3`, `Caddyfile` |
| `*.dec`           | **plaintext temporario** (gitignored)| Saida de `sops -d`                 |
| `*.plain.*`       | **plaintext temporario** (gitignored)| Defensivo                          |

## Inventario esperado (apos primeiro setup)

| Arquivo neste diretorio                         | Origem no VPS                                |
| ----------------------------------------------- | -------------------------------------------- |
| `secrets/env.enc.env`                           | `/opt/motor-expansao/app/.env` (dotenv)      |
| `secrets/Caddyfile.enc`                         | `/opt/motor-expansao/app/Caddyfile`          |
| `secrets/authelia.configuration.enc.yaml`       | `authelia/configuration.yml`                 |
| `secrets/authelia.users_database.enc.yaml`      | `authelia/users_database.yml`                |
| `secrets/authelia.db.sqlite3.enc`               | `authelia/db.sqlite3` (binario)              |

> **Os tres `secrets/authelia.*` sao backup de um servico aposentado em 16/11/2026** (Estagio 3
> da DEC-081): nenhum container le mais `authelia/`. Ficam ate a pasta `authelia/` e as variaveis
> `AUTHELIA_*` sairem tambem da VPS; o `env.enc.env` e o `Caddyfile.enc` vigentes (27/10/2026) sao
> de antes do Estagio 3 e precisam ser recifrados (BLK-BANCO-04; `docs/backup_restore.md`, aviso
> do topo).

> O sufixo `.enc.env` (em vez de apenas `.enc`) e necessario para que a regra
> dotenv do `.sops.yaml` case e encripte cada KEY=VALUE em vez de tratar o
> arquivo como blob binario opaco.

Antes do primeiro setup, esses arquivos nao existem — apenas este README e o
`.sops.yaml` na raiz. A geracao inicial e responsabilidade do operador, conforme
runbook.

## Editar um segredo

```bash
sops secrets/env.enc.env
# abre o editor padrao com conteudo desencriptado em MEMORIA
# salvar e sair re-encripta automaticamente
```

Nunca edite arquivos `secrets/*.enc*` direto com `nano`/`vim` — voce vai
quebrar o envelope SOPS. Use sempre `sops <arquivo>`.

## Referencia

Runbook completo de backup, restore e regeneracao: [`docs/backup_restore.md`](../docs/backup_restore.md).

Regras de criptografia (recipient public key age): [`../.sops.yaml`](../.sops.yaml).
