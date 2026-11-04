# A cadeia do crescimento mudou de pasta

Desde 01/11/2026, os geradores da camada de crescimento municipal (`01_municipal.py` a `10_periodo.py` e
`_raizes.py`) e o README deles ficam em [`scripts/crescimento/`](../../../scripts/crescimento/README.md).
Esta pasta guardava código de produção dentro de `data/`. Ficou só este aviso, porque comentários do
`docker-compose.prod.yml` e do `web/` ainda apontam para cá.

Quem roda a cadeia na própria máquina: mova o `_eixo_trajetoria.parquet` daqui para `scripts/crescimento/`.
