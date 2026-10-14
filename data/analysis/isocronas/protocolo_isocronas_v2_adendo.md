# Adendo ao protocolo — versão 2 do pipeline (2026-09-24, escrito ANTES de rodar a v2)

> O protocolo original (`protocolo_isocronas.md`) segue valendo. Este adendo registra as correções que a verificação da v1 impôs e os testes novos, com critério escrito antes de ver qualquer número da v2. Resultados da v1 ficam preservados (`isocronas/`, `atributos/`, `testes/`); a v2 grava em `*_v2/`.

## Correções de pipeline (achados verificados da v1)

1. **Malha a pé partida (D1):** o snap exigia nó no MAIOR componente conexo; sem trunk/motorway, Niterói/São Gonçalo, Guarujá/Bertioga e Águas Lindas caíam fora. v2: componente com ≥ 1.000 nós.
2. **Caixa curta (D2):** a margem de 12 km truncava carro 15 min em 57–69% das academias/controles, e a distância à borda sozinha separava academia de controle (AUC 0,64). v2: academias, controles e hexágonos só a ≥ 6 km da borda da caixa; Ultra sempre (estão a ≥ 12 km). Cada isócrona carrega `truncada` (raio máximo ≥ distância à borda − 500 m).
3. **Auto-contagem (L1-A5):** a academia contava a si mesma na oferta do próprio polígono. v2: excluída (< 2 m do alvo).
4. **Universo de oferta (verificadores L3):** `academias_pontos` incluía os estúdios boutique da DEC-056 e a própria Ultra listada no agregador como independente. v2: fora, pelas regras do repo (`REDES_ESTUDIO_BOUTIQUE`; regex `\bultra\s+academia\b`).
5. **Snap de hexágono (L3-A7):** centroide de hexágono res-7 a > 250 m de rua ficava sem isócrona. v2: 700 m para hexágonos.
6. **Samambaia (verificador E8-1):** o join de metragem perdia samambaia-df. v2: corrigido.
7. **Custo:** polígonos > 40 km² (carro 10/15 min) usam o ponto representativo do setor em vez da fração de área. Declarado; não afeta carro 5, a pé 10/15, círculos nem hexágono.

## Testes

- **T1–T5**: mesmas especificações e critérios do protocolo original, sobre a base v2. No T2, a especificação pré-registrada (carro 5, carro 15, a pé 15) roda só em pontos com carro 15 NÃO truncado; roda também sem carro 15 em todos os pontos (sensibilidade).
- **T4 na cascata real (novo recorte, mesmo critério descritivo):** além dos hexágonos do recorte, reportar a troca de rótulo só entre os que passam a cascata do funil sem a camada 3 (`score_setor_2022_calibrado` ≥ 30, população do hexágono ≥ 5.000, `oferta_efetiva_disponivel` ≥ 2.000).
- **T6 — forma da rede x tamanho do catchment (novo, pré-registrado):** a pergunta do dono é se adaptar a geografia por unidade traz informação. A isócrona difere do círculo de 1 km em TAMANHO e em FORMA; um círculo de ÁREA EQUIVALENTE (raio = √(área/π)) isola o tamanho.
  - T6a (preferência revelada): AUC OOF de B + atributos das isócronas (carro 5, a pé 15) contra B + os mesmos atributos nos círculos de área equivalente (mesmas colunas, mesmo modelo, GroupKFold por metro). **Critério: a forma da rede acrescenta informação de localização se AUC(isócrona) − AUC(círculo equivalente) ≥ +0,01 com IC95 (bootstrap por metro, 2.000) excluindo zero.**
  - T6b (leitura de oferta e população nas Ultra e nos hexágonos): rho de Spearman entre isócrona e círculo equivalente para pop, renda e oferta ponderada; fração de unidades cujo rank de oferta muda > 10 posições. **Critério descritivo:** se rho ≥ 0,90 em pop e oferta, a forma não muda a leitura do motor, só o tamanho.
  - T6c (previsão, E8): R² OOF do modelo I com as colunas da isócrona contra o mesmo modelo com as colunas do círculo equivalente. Só descritivo (T3 já é NO-GO).
- **T7 — calibração de velocidade (descritivo):** tempo de carro no nosso grafo contra o tempo do OSRM público (perfil car, sem trânsito) para ~40 pares origem Ultra → academia a 1–6 km. Reporta a razão mediana e o IQR. Não altera as isócronas da v2; serve para rotular o que "5 min" significa.

## O que continua fora

Nada aqui altera M1, score, pesos, o raio do Relatório Pontual (DEC-021), o gate do funil (DEC-041) ou artefatos oficiais. Camada paralela READ-ONLY.
