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
                                   # Limpeza(14000)+Tec(2150)+Assess(2500) = 38.150
                                   # DRE linhas 52-59,69
# FIN-VIAB-01 (2026-07-24): este comentario listava tambem "Outros(2000)", e as SETE
# componentes somavam 40.150 — R$ 2.000 acima do valor da propria constante. As SEIS
# acima fecham EXATAMENTE nos 38.150 que o motor usa, entao o "Outros" era espurio:
# entrou no texto e nunca no numero. A constante NAO mudou (o golden esta preservado);
# so o comentario foi corrigido. Descoberto ao decompor a linha na aba Premissas do
# simulador em XLSX, onde ratear as sete dava "IPTU R$ 1.900,37" — indefensavel linha
# a linha. Se a decomposicao real da unidade for outra, quem muda e a controladoria.

# ---------------------------------------------------------------------------
# Reforma do motor de viabilidade (alinhamento a planilha financeira oficial).
# READ-ONLY sobre o M1 (DEC-008/009): nao toca score_priorizacao/pesos/artefatos.
#
# FIN-VIAB-01 (2026-07-24): este bloco e a FONTE UNICA de premissas do simulador.
# Nenhum coeficiente financeiro pode viver como literal em simulador.py,
# viabilidade_ponto.py, web/server/app.py ou no frontend. Todo parametro daqui
# esta documentado em PREMISSAS_VIABILIDADE.md (default, fonte, quem pode alterar).
# ---------------------------------------------------------------------------
# ORFA / NAO CONSUMIDA — mantida so para nao quebrar import de terceiros.
# NAO LIGAR sem gate humano: trocaria PIS/COFINS/ISS (6,65% da liquida) por 16% da
# bruta = +R$26 mil/mes no caso de referencia. O regime vigente e o de SIM_PIS/
# SIM_COFINS/SIM_ISS, que tem celula rastreavel na planilha (Tributos E38/E40/E42);
# este 0.16 nao tem fonte. Ver PREMISSAS_VIABILIDADE.md secao "Constantes orfas".
SIM_IMPOSTO_FATURAMENTO = 0.16

# Folha: % do FATURAMENTO BRUTO (substitui o custo absoluto SIM_PESSOAL_MES).
# ATIVADA em FIN-VIAB-01 por decisao de Felipe (2026-07-24).
# CONFLITO ABERTO: o BLK-VIAB-11 (tasks/backlog.md) apurou 0,25-0,26 em 6 DREs
# gerenciais reais (folha real R$38k-99k/mes, estavel como % da bruta, CV 0,16).
# 0,17 fica ~no status quo (R$50.128 / R$277.676 = 18,05% no caso de referencia),
# entao a mudanca e de ESTRUTURA, nao de nivel.
# ATENCAO (decisao de Felipe, 2026-07-24): o percentual dimensiona a folha pelo
# faturamento MADURO, e o valor resultante e FIXO desde o mes 1 — a folha NAO escala
# com a rampa. Ver `Premissas.folha_fixa_mes()`. Como consequencia a folha e custo
# FIXO e NAO entra em `fator_receita_para_ebitda`.
# A calibracao do nivel segue pendente de gate da controladoria no BLK-VIAB-11.
SIM_FOLHA_PCT = 0.17
SIM_CUSTO_STUDIO = 6_000.0       # R$/mes de fopag adicional por studio extra
SIM_STUDIOS_DEFAULT = 0          # quantidade de studios (0..3)
# CAPEX/OPEX: Obra (equity, parcelas sem juros) x Equipamentos (financiado). Taxa de
# franquia PARCELADA sem juros junto da obra (ver SIM_PARCELAS_FRANQUIA_DEFAULT).
# DIVERGENCIA DE FONTE: a planilha (simulador_estrutura.json, celula R10) e
# docs/modelo_dimensionamento_expansao.md:276 dizem 140.000. O 160.000 abaixo e o
# valor em producao e o que o comite ja viu; mantido por decisao de Felipe
# (2026-07-24) e agora EXPOSTO no schema da API para o operador poder sobrescrever.
SIM_TAXA_FRANQUIA = 160_000.0
SIM_PARCELAS_OBRA_DEFAULT = 4
# Taxa de franquia PARCELADA sem juros (decisao de Felipe, 2026-07-24). Antes saia
# inteira do caixa no M-4; parcelada, o desembolso acompanha a obra e o payback
# deixa de carregar uma antecipacao que o contrato nao exige.
SIM_PARCELAS_FRANQUIA_DEFAULT = 4
# Aluguel-teto por clusters sobre o faturamento bruto steady (substitui a inversao por margem EBITDA).
# FIN-VIAB-01: passa a ser a UNICA definicao de aluguel-teto do sistema (tela E PDF).
# O canonico exibido no card grande e o SIM_ALUGUEL_TETO_TETO (20%) — o limite que a
# operacao defende. A EXCECAO (30%) e caso de excecao, nao referencia (decisao de
# Felipe, 2026-07-24). As tres faixas seguem impressas no detalhe da tela e do PDF.
SIM_ALUGUEL_TETO_IDEAL = 0.15
SIM_ALUGUEL_TETO_TETO = 0.20
SIM_ALUGUEL_TETO_EXCECAO = 0.30

# ---------------------------------------------------------------------------
# FIN-VIAB-01 — premissas que estavam como literal espalhado pelo codigo
# ---------------------------------------------------------------------------
# Inadimplencia: estava HARDCODED duas vezes na assinatura do simulador
# (viabilidade() e gerar_serie_mensal()); alterar uma sem a outra fazia o steady
# divergir da serie mensal. Agora tem dono unico.
SIM_INADIMPLENCIA = 0.02

# Composicao da demanda: a demanda_premissa e SEMPRE alunos TOTAIS; o DRE roda com
# dois tickets. Estava em viabilidade_ponto.SHARE_BALCAO_DEFAULT e DUPLICADO em
# web/server/app.py::_serie_motor.
SIM_SHARE_BALCAO = 0.69

# Ticket do agregador (Gympass/TotalPass e similares) como FRACAO do ticket cheio.
# ANTES: SIM_TICKET_AGREGADOR = R$82 ABSOLUTO, desacoplado do ticket cheio -> quando
# o studio elevava o ticket de 147 para 177, o agregador degradava de 55,8% para
# 46,3% sem ninguem ver. O comentario de viabilidade_ponto.py ja dizia "~60% do
# ticket"; agora e o que o codigo faz.
SIM_TICKET_AGREGADOR_FATOR = 0.60
SIM_TICKET_AGREGADOR = 82        # LEGADO: piso absoluto so p/ chamadas antigas sem ticket

# IR/CSLL — Lucro Presumido, servicos (base presumida 32% da RECEITA BRUTA).
# ANTES: aliquotas efetivas de 8%/2,88% aplicadas sobre a receita LIQUIDA, com o
# adicional de 10% embutido como se TODA a base excedesse o limite. Agora a faixa
# do adicional e explicita.
SIM_BASE_PRESUMIDA_PCT = 0.32    # base de calculo presumida sobre a receita bruta
SIM_IRPJ_ALIQUOTA = 0.15
SIM_IRPJ_ADICIONAL_ALIQUOTA = 0.10
# Limite do adicional: R$60.000/trimestre. Aplicado PRO-RATA MENSAL (=60.000/3) para
# nao criar degrau artificial na serie de caixa; equivalente ao trimestral quando os
# meses do trimestre sao estaveis. Ver PREMISSAS_VIABILIDADE.md.
SIM_IRPJ_ADICIONAL_LIMITE_MES = 20_000.0
SIM_CSLL_ALIQUOTA = 0.09

# Reajuste anual (P1-8). Aplicado a partir do mes 13 (fator degrau por ano cheio).
# A PMT do financiamento e NOMINAL e NAO sofre reajuste.
SIM_REAJUSTE_TICKET_AA = 0.04
SIM_REAJUSTE_ALUGUEL_AA = 0.04
SIM_REAJUSTE_CUSTOS_AA = 0.04

# ---------------------------------------------------------------------------
# Taxa minima do negocio (Ku) — a UNICA taxa configuravel do modelo.
# Decisao de Felipe, 2026-07-25.
# ---------------------------------------------------------------------------
# 25% a.a. NOMINAL. Justificativa registrada: piso implicito da propria decisao de
# financiar (o custo da divida de 1,8% a.m. = 23,87% a.a.) + build-up sobre a Selic
# de 14,25%. Substitui a antiga SIM_TAXA_DESCONTO_AA = 0.12, que era uma taxa de
# referencia generica aplicada a um fluxo DE SOCIO — incoerencia apontada em revisao
# externa: o socio e subordinado ao banco, entao a taxa dele nao pode ser MENOR que a
# do credor.
#
# A taxa do SOCIO (Ke) NAO e configuravel: e DERIVADA, em `simular()`, por
#     Ke = Ku + (Ku - Kd) * D/E
# Isso torna a incoerencia IMPOSSIVEL por construcao — nao existe campo onde alguem
# possa digitar uma taxa de socio abaixo do custo da divida.
#
# E como o Lucro Presumido NAO tem escudo fiscal da divida (o IR/CSLL incide sobre a
# receita bruta e ignora a despesa financeira), WACC = Ku. Nao ha media ponderada a
# fazer: a estrutura de capital nao muda o valor do ativo, so a sua reparticao.
SIM_TAXA_MINIMA_NEGOCIO_AA = 0.25

# Linha do tempo: M-4..M-1 = pre-abertura (obra), M1..M60 = operacao.
SIM_MESES_PRE_ABERTURA = 4
SIM_HORIZONTE_MESES = 60

# Carencia de aluguel: meses iniciais sem pagar aluguel, contados A PARTIR DE M-4
# (entrega da unidade / inicio das obras), nao da abertura.
SIM_CARENCIA_ALUGUEL_MESES = 0

# Custo pre-operacional (contratacao, treinamento, pre-venda nos meses de obra).
# Default ZERO — existe para tornar EXPLICITO que hoje o modelo assume ausencia total.
SIM_CUSTO_PRE_OPERACIONAL_MES = 0.0

# Fim do horizonte (P2-16). Defaults ZERO; existem para tornar explicito que o corte
# em 60 meses ignora tanto o valor residual quanto o CAPEX de renovacao.
SIM_VALOR_RESIDUAL_MES_60 = 0.0
SIM_CAPEX_RENOVACAO = 0.0

# Criterio de viabilidade (estavam como literais em simulador.py::flag_viavel).
# MARGEM MINIMA 30% por decisao de Felipe (2026-07-25); era 0.10. A regua antiga
# aprovava cenario de margem 12% que ninguem levaria a comite.
SIM_MARGEM_VIAVEL_MIN = 0.30
# Payback em meses de OPERACAO (M1..M60), NAO meses decorridos desde a entrega do
# imovel (M-4). No caso de referencia: 31 meses de operacao = 35 meses desde o 1o
# desembolso. A base de contagem esta travada em teste.
SIM_PAYBACK_VIAVEL_MAX = 36

# ---------------------------------------------------------------------------
# Anuidade / taxa de manutencao (Simulador J10 + J12)
# ---------------------------------------------------------------------------
# Linha de receita que existe na planilha (drivers.manutencao_anuidade, J10) e nunca
# tinha sido implementada no motor.
#
# LIGADA por decisao explicita de Felipe (2026-07-24), com a periodicidade confirmada
# por ele: R$99 UMA VEZ POR ANO (nao por mes) por aluno de BALCAO que completa 12
# meses de casa. O gate de QA deste mesmo ciclo a havia desligado por nao conseguir
# verificar a aprovacao — a aprovacao existe, e as 4 condicoes que o QA exigiu para
# religar foram cumpridas no mesmo commit:
#   (a) a anuidade e EXPOSTA no `viabilidade_payload_v1` (premissas.anuidade_* e
#       dre.receita_anuidade) — o operador ve a linha, nao um faturamento maior sem causa;
#   (b) os numeros do caso golden foram re-medidos em tests/contracts/;
#   (c) PREMISSAS_VIABILIDADE.md, STATUS_ORQUESTRACAO.md e a nota de impacto atualizados;
#   (d) o mes de referencia do steady-state passa a ser max(maturacao, inicio da
#       anuidade) = 12, e o PDF le esse mes do bloco `dre` do payload (nao o recalcula),
#       que era a causa do waterfall divergir do card ao lado no mesmo slide.
SIM_ANUIDADE_VALOR = 99.0
# Mes de operacao a partir do qual a cobranca existe (Simulador J12).
SIM_ANUIDADE_MES_INICIO = 12
# So o BALCAO paga: aluno de agregador (Gympass/TotalPass) nao paga anuidade da
# academia — o agregador remunera por acesso.
SIM_ANUIDADE_APENAS_BALCAO = True
# Fracao dos alunos que chega aos 12 meses. None = DERIVA do churn ((1-churn)^12),
# entao mexer no churn ajusta a elegibilidade sozinho, sem numero magico paralelo.
# Com churn 0,06 -> 0,94^12 = 47,6%. Pedido explicito de Felipe: "nem todos os
# alunos chegam a 12 meses".
SIM_ANUIDADE_ELEGIVEL_PCT: float | None = None
# Reconhecimento PRO-RATA MENSAL (valor/12) a partir do mes de inicio, em vez de um
# lancamento unico no mes 12: os aniversarios dos alunos se distribuem ao longo do
# ano, entao o lancamento unico criaria um degrau artificial no caixa.
SIM_ANUIDADE_PRO_RATA = True
