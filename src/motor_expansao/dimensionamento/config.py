"""Constantes LOCAIS do modulo de Dimensionamento (BLK-DIM).

NAO mexer no `config.py` raiz do M1. Estes valores sao da camada paralela de
Dimensionamento e Viabilidade e foram aprovados no gate humano (2026-06-13,
decisoes D1-D7 do BLK-DIM-00).
"""

from __future__ import annotations

from pathlib import Path

# --- Growth API -------------------------------------------------------------
GROWTH_API_BASE_URL = "https://services.ultraacademia.com.br/growth_api_ultra"

# Rate limit documentado (doc Growth API v1.0.0 §6): 10 req / 5 min por IP -> HTTP 429.
RATE_LIMIT_REQS = 10
RATE_LIMIT_WINDOW_S = 300
# Em 429 o doc manda aguardar >= 30 s + backoff exponencial.
BACKOFF_MIN_S = 30
# Token expira em 1 h (§5.4) -> relogin em 401.
TOKEN_TTL_S = 3600

# --- Diretorios -------------------------------------------------------------
CACHE_DIR = Path("data/cache/growth_api")
STAGING_DIR = Path("data/staging")

# --- Anti-PII (LGPD §10.3) --------------------------------------------------
# Nenhuma destas colunas pode existir em disco. `assert_sem_pii` levanta antes de
# qualquer `to_parquet`. Comparacao case-insensitive.
PII_COLUNAS_PROIBIDAS = frozenset(
    {
        "nome",
        "cpf",
        "email",
        "celular",
        "data_nascimento",
        "cod_aluno",
        "nome_usuario",
        "usuario",
        "cod_usuario",
        "tel",
        "cel",
        "sexo",
        "situacao",
        "plano",
        "motivo",
        "cargo",
    }
)

# --- Parametros de consolidacao (decisoes D1/D3/D4/D6 do gate humano) -------
# D1: inicio da serie historica (janela mensal ate hoje).
DATA_INICIO_HISTORICO = "2022-04-01"
# D6: mediana dos ultimos N meses maduros para steady-state.
N_MESES_STEADY = 6
# D4: limiar de maturacao em meses (flag_madura = meses_desde_inauguracao >= MESES_MADURA).
MESES_MADURA = 8
# D3: raio do catchment censitario (km). Parametrizavel 1.0-2.0 sem tocar o helper.
RAIO_CATCHMENT_KM = 1.5

# --- Endpoint (decisao D7) --------------------------------------------------
# Ingerir SO `/historico-dash-view` (superset de `/historico-dash`).
ENDPOINT_HISTORICO_VIEW = "/historico-dash-view"
ENDPOINT_HISTORICO = "/historico-dash"
ENDPOINT_LOGIN = "/auth/login"

# ---------------------------------------------------------------------------
# Simulador financeiro — coeficientes do DRE real (BLK-DIM-03R)
# Fonte: data/staging/simulador_estrutura.json (BLK-DIM-00) +
#        custos fixos absolutos extraidos manualmente do Excel (handoff BO BLK-DIM-03R)
# ---------------------------------------------------------------------------

# Ratios % do DRE (ratios_dre do JSON)
SIM_DEVOLUCOES_PCT = 0.005   # DRE F30
SIM_MARKETING_PCT = 0.02     # DRE F63
SIM_MANUTENCAO_PCT = 0.02    # DRE F67
SIM_CARTOES_PCT = 0.0105     # DRE F79
# royalties vem do driver Simulador!N11 (= 0.08); exposto como SIM_ROYALTIES_PCT
SIM_ROYALTIES_PCT = 0.08     # Simulador N11

# Impostos — regime Lucro Presumido (impostos_presumido do JSON)
SIM_PIS = 0.0065             # Tributos E38
SIM_COFINS = 0.03            # Tributos E40
SIM_ISS = 0.03               # Tributos E42
SIM_IR_EFETIVO = 0.08        # Tributos E44 (=32%*25%)
SIM_CSLL_EFETIVO = 0.0288    # Tributos E46 (=32%*9%)

# Drivers de demanda (Simulador — celulas E9..E13)
SIM_ALUNOS_BALCAO_MATURIDADE = 938      # E10
SIM_ALUNOS_AGREGADORES_MATURIDADE = 651  # E11
SIM_ALUNOS_INICIAL = 500                 # E9
SIM_CHURN = 0.06                         # E12
SIM_MATURACAO_MESES = 8                  # E13

# Drivers financeiros (Simulador — celulas J9, N9, N11, R9)
SIM_MENSALIDADE_BALCAO = 137             # J9 cenario 0 (=IF(N12=0,137,...))
SIM_TICKET_AGREGADOR = 82                # aba Simulador linha 11 (~R$82/aluno/mes)
SIM_PERSONAL_MES_RECEITA = 5_000         # DRE linha 24 (receita fixa personal)
SIM_ALUGUEL_MES = 20_000                 # N9
SIM_CAPEX_DEFAULT = 2_340_000            # R9 formula cenario 0 (FC!C11:C16)

# Custos fixos ABSOLUTOS mensais (nao no JSON — extraidos do Excel; DRE linhas 52-59,69 + Fopag 44)
SIM_PESSOAL_MES = 50_128.16     # Fopag total c/ encargos (linha DRE 55)
                                 # LEGADO: nao alimenta mais a folha (ver SIM_FOLHA_PCT abaixo);
                                 # mantido so como default da assinatura de viabilidade()/gerar_serie_mensal().
SIM_OUTROS_FIXOS_MES = 38_150.00  # IPTU(2000)+Agua/Luz(17000)+Tel(500)+
                                   # Limpeza(14000)+Tec(2150)+Assess(2500)+Outros(2000)
                                   # DRE linhas 52-59,69

# ---------------------------------------------------------------------------
# Reforma do motor de viabilidade (alinhamento a planilha financeira oficial).
# READ-ONLY sobre o M1 (DEC-008/009): nao toca score_priorizacao/pesos/artefatos.
# ---------------------------------------------------------------------------
# Impostos: 16% sobre o FATURAMENTO BRUTO substitui a linha PIS/COFINS/ISS (acima do
# EBITDA). IR/CSLL (SIM_IR_EFETIVO/SIM_CSLL_EFETIVO) seguem abaixo do EBITDA, inalterados.
SIM_IMPOSTO_FATURAMENTO = 0.16
# Folha: 17% do faturamento bruto (substitui o custo absoluto SIM_PESSOAL_MES) + custo por studio.
SIM_FOLHA_PCT = 0.17
SIM_CUSTO_STUDIO = 6_000.0       # R$/mes de fopag adicional por studio extra
SIM_STUDIOS_DEFAULT = 0          # quantidade de studios (0..3)
# CAPEX/OPEX: Obra (equity, parcelas sem juros) x Equipamentos (financiado). Taxa de franquia
# paga a vista no M-4 (pre-inauguracao); usada na serie de fluxo de caixa operacional.
SIM_TAXA_FRANQUIA = 160_000.0
SIM_PARCELAS_OBRA_DEFAULT = 4
# Aluguel-teto por clusters sobre o faturamento bruto steady (substitui a inversao por margem EBITDA).
SIM_ALUGUEL_TETO_IDEAL = 0.15
SIM_ALUGUEL_TETO_TETO = 0.20
SIM_ALUGUEL_TETO_EXCECAO = 0.30
