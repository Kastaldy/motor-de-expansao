/* ---------------------------------------------------------------------------
   Perfil BRASILEIRO compilado — o default do cliente.

   GERADO de `data/perfis/BR/perfil.json`. NAO edite a mao: o teste de contrato
   `tests/contracts/test_perfil_front_espelha_o_python.py` compara este arquivo com o
   JSON e falha nomeando o campo divergente.

   Por que existe. `coord.ts`, `entrada-ponto.ts`, `format.ts`, `faixas.ts`, `colors.ts`
   e `mapa-ponto.ts` sao modulos PUROS, testados pelo Vitest SEM servidor. Sem um default
   compilado, os testes deles quebrariam por `undefined` — nao por regua. Este arquivo e o
   que mantem quatro arquivos de teste verdes sem uma linha de mudanca neles.

   Ele NAO e o perfil da instancia: em producao o `main.tsx` resolve o perfil de verdade
   antes de montar a arvore (ver `perfil.ts`). Este e so o ponto de partida.
   --------------------------------------------------------------------------- */

import type { PerfilCliente } from './perfil'

export const PERFIL_BR: PerfilCliente = {
    "pais": "BR",
    "nome": "Brasil",
    "locale": "pt-BR",
    "moeda": {
      "codigo": "BRL",
      "simbolo": "R$"
    },
    "bbox": {
      "lat_min": -34.0,
      "lat_max": 5.5,
      "lng_min": -74.0,
      "lng_max": -28.0
    },
    "vista_padrao": {
      "lat": -14.5,
      "lng": -52.9,
      "zoom": 3.4
    },
    "reguas": {
      "pop_min_acionavel": 5000,
      "capacidade_unidade_alunos": 2500
    }
  }
