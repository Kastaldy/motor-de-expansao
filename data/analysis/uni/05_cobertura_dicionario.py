# -*- coding: utf-8 -*-
"""BLK-UNI-00, passo 5: criterio de aceite — cobertura por fonte, por COLUNA e por unidade + checagem de dado pessoal.

Saidas (sem nada derivado do NAO_ABRA): COBERTURA_UNI00.md, DICIONARIO_UNI00.md, cobertura_por_unidade.csv
Saida SO' LOCAL: LOCAL_COBERTURA_demanda_totalpass.md
"""
import re
from pathlib import Path

import pandas as pd

UNI = Path(__file__).parent
PII = re.compile(r"franqueado|consultor|cod_aluno|employee|cpf|email|telefone|master_franquia|nome_aluno", re.I)

# (padrao regex do nome da coluna, fonte, definicao/escala, significado do NaN) — a primeira regra que casa vence
REGRAS = [
    (r"^unidade_id$", "catalogo Growth (rede_metricas)", "slug canonico da unidade", "-"),
    (r"^competencia$", "fechamento_mensal", "mes 'AAAA-MM'", "-"),
    (r"^faturamento$", "Financeiro (planilha de 2026-09-28, mes fechado) via fechamento_mensal", "R$ do mes; so' onde origem_faturamento='financeiro'", "sem Financeiro no mes, zero com ativos (mes sem lancamento) ou mes corrigido sem componentes"),
    (r"^faturamento_original$", "fechamento_mensal antes das regras do painel", "R$ (auditoria)", "-"),
    (r"^faturamento_growth_auditoria$", "Growth", "R$ da Growth onde NAO ha Financeiro; so' auditoria, nunca variavel", "ha Financeiro"),
    (r"^fin_", "planilha do Financeiro de 2026-09-28 (ler_planilha do motor; ate o ultimo mes fechado)", "componentes do Financeiro em R$: vendas_ux + gympass + totalpass - tem_saude = faturamento", "sem Financeiro / mes corrigido / zero com ativos"),
    (r"^(faturamento_sem_agregador|faturamento_agregador|receita_por_recorrente|pct_agregador_receita)$", "fechamento_mensal (motor)", "derivadas do motor sobre o faturamento (pct em 0-100)", "mesmas regras do faturamento"),
    (r"^flag_receita$", "painel", "por que a receita da linha esta vazia ou marcada", "linha sem ressalva"),
    (r"^correcao_manual$", "painel", "correcao declarada (Guaruja ago/26)", "sem correcao"),
    (r"^origem_faturamento$", "fechamento_mensal", "'financeiro' ou 'ux' (Growth)", "-"),
    (r"^(mes_completo|operacao_mes_cheio)$", "fechamento_mensal", "completude de COLETA (>= 25 dias e fim do mes) / operacao no mes inteiro", "-"),
    (r"^mes_vida$", "fechamento_mensal.meses_operacao", "meses desde a inauguracao (mes 0 = mes da inauguracao)", "inauguracao invalida ou placeholder"),
    (r"^mes_vida_minimo$", "Financeiro", "so' nas 4 unidades de inauguracao placeholder: meses desde o 1o faturamento > 0 (limite INFERIOR da idade)", "unidade com inauguracao valida"),
    (r"^var_ativos_pct$", "painel", "ativos(m)/ativos(m-1) - 1 por merge; so' entre meses completos, mes_vida >= 1 (fracao)", "algum dos 2 meses incompleto"),
    (r"^pct_agregador_ativos$", "painel", "agregadores/ativos (fracao 0-1; definicao do estudo de inauguracao, NAO e' o pct_agregador_alunos do motor)", "ativos = 0"),
    (r"^pct_agregador_receita_fin$", "Financeiro", "(gympass+totalpass)/(vendas_ux+gympass+totalpass): agregador sobre a receita BRUTA, antes do Tem Saude (fracao 0-1)", "sem componente de agregador"),
    (r"^pct_tem_saude_fin$", "Financeiro", "deducao Tem Saude / faturamento (fracao)", "sem Financeiro"),
    (r"^receita_por_ativo_fin$", "Financeiro + Growth", "faturamento do Financeiro / ativos do fim do mes, so' em mes completo e de operacao cheia (R$)", "mes parcial ou sem Financeiro"),
    (r"^(n_ultra_outras_abertas|ativos_ultra_outras)__carro_10$", "poligonos_v2 + ultra_pontos + inauguracao", "outras Ultras dentro da isocrona carro 10 JA inauguradas no mes (contagem / soma de ativos no mes); 0 = nenhuma", "sem isocrona, pino errado, ou vizinha aberta sem ativos no mes"),
    (r"^tem_isocrona_carro_10$", "poligonos_v2", "a unidade tem isocrona de carro 10 min", "-"),
    (r"^(ultima_competencia|ultima_competencia_unidade|serie_encerrada)$", "serie", "ultimo mes com dado; True = parou de reportar antes do fim (vies de sobrevivencia)", "-"),
    (r"^churn_pct$", "fechamento_mensal (DAX oficial)", "cancelados / pagantes do mes anterior (0-100)", "-"),
    (r"^(nps|NPS)$", "Growth", "NPS agregado; mistura canais e usa 999 como sentinela — so' com nps_valido", "-"),
    (r"^cod_", "de-para", "codigo UX da unidade (2 caracteres)", "sem codigo naquela fonte"),
    (r"^flag_erro_dado$", "painel", "erro de dado conhecido; os atributos que ele compromete estao anulados", "sem erro conhecido"),
    (r"^flag_inauguracao_placeholder$", "Growth", "inauguracao = 23/08/2021 (placeholder da matriz de SP)", "-"),
    (r"^inauguracao_origem$", "Growth/DEC-053", "cadastro_growth | placeholder | derivada_serie (DEC-053: 1a data da serie)", "-"),
    (r"^anomalia_conferir$", "memoria do projeto", "anomalia a conferir (nao excluida; regra 4 do epic)", "sem anomalia"),
    (r"^(lat|lng|confianca_coord|origem_coord|pin_cadastro|hex_id_res7)$", "isocronas/ultra_pontos.parquet", "pino usado nas isocronas; hex H3 res-7 do pino", "sem pino"),
    (r"^tam_", "dados_academias.xlsx (Plan1)", "metragem (m2), vagas, vagas por 1.000 m2; VAGAS NAO E' PREDITOR (colinear com m2; so' descritivo)", "unidade fora do xlsx (falta NAO aleatoria: cobre as maduras em abr/2026)"),
    (r"^(tipo_imovel|fachada)$", "sem fonte", "coluna reservada: nao ha levantamento para a Ultra (proxy: poi_em_shopping)", "sempre NaN (pendente)"),
    (r"^cad_", "VPS cadastro_unidades.json (2026-08-06, reduzido)", "preco Gold (R$), tier Wellhub/TotalPass declarado e modalidades; foto", "fora do cadastro"),
    (r"^iso_.*__(carro_5|carro_10|pe_15|circulo_1km)$", "isocronas v2 + Censo 2022 (base_ultra)", "atributo dentro da area: pop, renda_pc (R$ calibrada do setor, sem uplift), domicilios, area_km2, km_rua, densidade, oferta (cadeia 1,0 / independente 0,5) e contagens de academias", "sem isocrona, pino errado; pe_15 da Lago Sul anulada"),
    (r"^iso_", "isocronas v2", "metro (caixa OSM) e distancia do pino ao no' da malha", "sem isocrona"),
    (r"^conc_alunos_por_mil_hab", "academias_pontos + alunos_reais (confianca alta)", "alunos dos concorrentes na isocrona por mil hab; PREMISSA: cadeia sem dado = 1.800 alunos, independente = 400; foto de hoje (anacronico para meses antigos)", "sem isocrona/pop"),
    (r"^conc_", "academias_pontos + alunos_reais (confianca alta)", "cap_real = soma de alunos reais; cap_rede = mediana da rede; n_cadeia_proxy / n_indep = contagens sem dado; foto de hoje", "sem isocrona"),
    (r"^canib_", "base_canibal (isocronas v2)", "maior fracao da isocrona sobreposta por outra Ultra e n de Ultras sobrepostas (foto de hoje; a versao no tempo esta no fato); 0 = nenhuma", "sem isocrona"),
    (r"^cres_hex", "VPS crescimento_hex.parquet", "variacao % da area construida 2016-2023 (satelite) no hex da unidade / classe", "fora das 12 UFs com satelite ou da mascara urbana"),
    (r"^cres_", "VPS crescimento_municipal.parquet", "crescimento do municipio: dim_media (percentis 0-100), renda RAIS 2020-24 nominal, pop 2016-21, empresas por mil, emprego CAGED (trimestral, entra 2026), predios satelite; municipio pelo hex do universo completo (brasil_estrutural) com fallback por nome", "municipio sem a dimensao"),
    (r"^poi_F1", "base_poi_unica (CNPJ set/26, estoque < 2025)", "F1 = log(1+filiais de escritorio/TI/financeiro/juridico/governo/hospital a pe 15) - log(1+pop a pe); _all = todas as empresas; _c10 = carro 10", "sem isocrona a pe"),
    (r"^poi_F2b", "base_poi_unica (CNEFE 2022)", "enderecos nao residenciais do Censo a pe 15, na forma de F2", "sem isocrona a pe"),
    (r"^poi_F2", "base_poi_unica (CNPJ set/26, estoque < 2025)", "F2 = log(1+filiais de varejo/alimentacao/servicos pessoais a pe 15) - log(1+pop a pe)", "sem isocrona a pe"),
    (r"^poi_F3$", "OSM + CNPJ", "1 se ha ancora (shopping, estacao, atacarejo) a pe 15, fora o shopping da propria unidade", "sem isocrona a pe"),
    (r"^poi_F5", "CNPJ 9313 (endereco exato)", "log(1 + academias CNPJ fora do universo mapeado por mil hab, carro 10); pre_inaug = estoque anterior a inauguracao", "sem isocrona"),
    (r"^poi_", "base_poi_unica", "fatos: em_shopping (poligono OSM de shopping a <= 150 m), n de shoppings/estacoes/atacarejos a pe 15, universidades carro 10, fracao da contagem com endereco exato", "sem isocrona"),
    (r"^(tp|wh)_.*_cadastro$", "cadastro", "tier/tem agregador segundo o cadastro (foto 2026-08-06), na mesma regua ordinal do feed", "fora do cadastro / 'NAO POSSUI'"),
    (r"^(tp|wh)_.*_c10$", "planos_totalpass / planos_wellhub (coleta 2026-09-10..15)", "concorrentes na isocrona carro 10 (sem Ultra, sem estudio DEC-056, so' musculacao; Wellhub pelo vocabulario V2): contagem, mediana do ordinal e do preco da ASSINATURA do agregador, % acima/igual/abaixo do tier da Ultra, gap; foto de set/26", "< 3 concorrentes com preco, Ultra sem plano, sem isocrona"),
    (r"^(tp|wh)_", "planos_totalpass / planos_wellhub", "plano da propria Ultra no feed (linha 'Ultra Academia' a <= 300 m do pino), preco da assinatura, ordinal (rank do preco; 0 = TP Free/Digital), distancia ao casamento", "Ultra nao listada no agregador (NAO e' 'plano barato')"),
    (r"^lt_", "Projeto-Lifetime unidade_para_motor (vintage 2026-08-10; EB 2026-04-17..08-11)", "retencao EB 60d (headline), churn 60d e IC, peso do dado proprio, prob. de cancelamento 90d (so' onde o gate permite), meses esperados 12M, LTV 12M, confiabilidade; POSTERIOR a exploracao ate dez/25: desfecho/descritor, nunca preditor de meses anteriores", "unidade fora do Lifetime ou gate de uso"),
    (r"^(cancelados|visitas|convertidos|novos_alunos|vendas|passagens_gympass|passagens_totalpass)$", "Growth (fechamento_mensal)", "cumulativa do mes: ULTIMO valor do mes (nunca o maximo; cancelados cai dentro do mes em 36,7% dos casos)", "sem dado"),
    (r"^(pagantes|alunos_gympass|alunos_totalpass|ativos|agregadores|em_cobranca|inadimplente|treino_ativo|pagantes_m1|saldo_operacional)$", "Growth (fechamento_mensal)", "foto do ultimo dia com dado do mes (contagem de alunos); agregadores = gympass + totalpass; saldo = novos - cancelados", "sem dado"),
    (r"^(conversao_pct|em_cobranca_pct|pct_agregador_alunos)$", "fechamento_mensal (motor)", "percentual 0-100 do motor (pct_agregador_alunos = agregadores/(pagantes+agregadores), NAO a definicao do estudo)", "denominador zero"),
    (r"^(dia_ref|dias_com_dado|unidade_cru|nps_valido|meses_operacao|inauguracao|inauguracao_competencia|pre_inauguracao|ativos_mes_anterior|mes_completo_anterior)$", "fechamento_mensal / painel", "controle: ultimo dia com dado, dias com dado, nome cru, NPS valido, meses de operacao do motor, inauguracao, mes anterior usado na variacao", "-"),
    (r"^(nome|uf|master|excluida_rede|cidade_cadastro|localizacao_xlsx|tem_pino_iso)$", "de-para", "identidade: nome, UF, sigla regional da Growth (agrupador, nao nome de pessoa), excluida pelo motor, cidade do cadastro, linha do xlsx, tem pino de isocrona", "sem par naquela fonte"),
    (r"^rampadesc_", "serie mensal", "descritor de rampa que usa meses POSTERIORES a liberacao (formato pos-patamar, estabilizou ate hoje, tolerancias 3%/10%, estabilizacao do faturamento): so' descricao/desfecho", "rampa nao observavel"),
    (r"^rampa_(ret12|n_alunos_prevenda)", "PENDENTE", "retencao 12m da coorte de abertura / pre-venda: exige export agregado por unidade do Projeto Lifetime", "sempre NaN (pendente)"),
    (r"^rampa_", "serie mensal (Growth + Financeiro), estudo de inauguracao", "variaveis de abertura: ativos/recorrentes/agregadores/faturamento nos meses de vida 1/3/6/12, tempo ate estabilizar (+-5% por 3 meses seguidos: m, m+1, m+2), patamar (media m..m+2), velocidade, pico, churn e conversao ate o mes 12; so' explicam janelas que comecam em rampa_competencia_liberacao ou depois", "rampa nao observavel (inauguracao antes de 2022-04, placeholder ou sem mes 1 completo)"),
]


def descrever(c):
    for pad, fonte, defi, nan in REGRAS:
        if re.search(pad, c):
            return fonte, defi, nan
    return "fechamento_mensal (motor) / de-para", "ver rede_metricas.py", "-"


def main():
    D = pd.read_parquet(UNI / "dim_unidade.parquet")
    F = pd.read_parquet(UNI / "fato_unidade_mes.parquet")
    L = pd.read_parquet(UNI / "LOCAL_demanda_totalpass_por_unidade.parquet")
    for df, nome in ((D, "dim"), (F, "fato"), (L, "local")):
        ruins = [c for c in df.columns if PII.search(c)]
        assert not ruins, f"coluna com cara de dado pessoal em {nome}: {ruins}"
    N = D[~D.excluida_rede].reset_index(drop=True)
    fin_units = set(F.loc[F.origem_faturamento.eq("financeiro") & F.faturamento.notna(), "unidade_id"])
    sem_fin = N.loc[~N.unidade_id.isin(fin_units), ["unidade_id", "inauguracao"]]
    md = ["# Painel BLK-UNI-00 — cobertura (critério de aceite)\n",
          f"Scripts `01_depara.py` a `05_cobertura_dicionario.py` em `data/analysis/uni/`. Universo: **{len(N)} unidades** da rede comparável "
          f"(+{int(D.excluida_rede.sum())} que o motor exclui — studio, administração etc. — só no de-para).\n",
          "- **Dado pessoal:** nenhuma coluna (checado por nome). Lifetime e TotalPass entram só agregados por unidade. A cópia do cadastro foi reduzida aos campos usados, sem franqueado ou consultor.",
          "- **Reprodutível:** todos os insumos estão em `insumos_vps/`, `insumos_locais/` e `../isocronas/`. Nada é lido do scratchpad da sessão, exceto o `06_teste_poi.py` do teste de POI, que só lê o repositório.\n",
          "## Fato unidade × mês (`fato_unidade_mes.parquet`)\n",
          f"- {len(F):,} linhas, {F.unidade_id.nunique()} unidades, {F.competencia.min()} a {F.competencia.max()}. A Growth começa em 2022-04; o Financeiro fecha até 2026-08.",
          f"- **Receita válida** (Financeiro, mês completo, operação cheia): {int((F.mes_completo & F.operacao_mes_cheio & F.origem_faturamento.eq('financeiro') & F.faturamento.notna()).sum()):,} unidade-mês, de {len(fin_units)} unidades.",
          f"- Receita vazia por regra: {F.flag_receita.value_counts().to_dict()}.",
          f"- Correção manual: {F.correcao_manual.notna().sum()} (Guarujá ago/26, informado pelo Felipe).",
          f"- Canibalização no tempo: {int((F.n_ultra_outras_abertas__carro_10 > 0).sum()):,} unidade-mês com outra Ultra já aberta na isócrona de carro 10 min.\n",
          "## Atributos por unidade (`dim_unidade.parquet`): cobertura por bloco\n",
          "| bloco | unidades com dado (de %d) | coluna-chave |" % len(N), "|---|---|---|"]
    chaves = [("Tamanho (metragem, vagas)", "tam_metragem_m2"), ("Cadastro", "cad_tier_totalpass"), ("Isócronas (pop, renda, oferta)", "iso_pop__carro_10"),
              ("Concorrência com alunos reais", "conc_cap_real__carro_10"), ("Sobreposição com outras Ultras", "canib_frac_max__carro_10"),
              ("Crescimento municipal", "cres_dim_media"), ("Crescimento do hexágono (satélite)", "cres_hex_taxa"), ("POIs", "poi_F1"),
              ("TotalPass: plano da Ultra no feed", "tp_plano_ultra"), ("TotalPass: concorrência com ≥ 3 preços", "tp_ord_mediana_c10"),
              ("Wellhub: plano da Ultra no feed", "wh_plano_ultra"), ("Wellhub: concorrência com ≥ 3 preços", "wh_ord_mediana_c10"),
              ("Lifetime: retenção EB", "lt_eb_retencao_60d"), ("Lifetime: prob. 90d utilizável", "lt_prob_cancel_90d_media"),
              ("Rampa observável", "rampa_ativos_m1"), ("Patamar (estabilizou)", "rampa_patamar_ativos")]
    cob = pd.DataFrame({"unidade_id": N.unidade_id})
    for nome, col in chaves:
        md.append(f"| {nome} | {int(N[col].notna().sum())} | `{col}` |")
        cob[col] = N[col].notna().to_numpy()
    cob["financeiro_valido"] = N.unidade_id.isin(fin_units).to_numpy()
    fl = N[N.flag_erro_dado.notna()][["unidade_id", "flag_erro_dado"]]
    md += ["\n## Erros de dado conhecidos (linha mantida, atributo afetado anulado)\n"] + [f"- `{r.unidade_id}`: {r.flag_erro_dado}" for r in fl.itertuples()]
    md.append(f"- Inauguração placeholder 23/08/2021: {N.loc[N.flag_inauguracao_placeholder, 'unidade_id'].tolist()}. No fato, `mes_vida` = NaN e `mes_vida_minimo` = meses desde o 1º faturamento (limite inferior); a rampa não é observável.")
    md.append(f"- Anomalias a conferir (não excluídas): {N.loc[N.anomalia_conferir.notna(), ['unidade_id', 'anomalia_conferir']].values.tolist()}")
    md += ["\n## Lacunas por unidade\n",
           f"- Sem nenhum mês de Financeiro: {[(r.unidade_id, str(r.inauguracao)[:10]) for r in sem_fin.itertuples()]}. Abriram em set/2026 e ainda não têm mês fechado.",
           "- Casadas no Financeiro só por nome, porque o layout novo do Financeiro não traz código: ver `depara_divergencias.md`.",
           f"- Sem metragem: {int(N.tam_metragem_m2.isna().sum())}. A falta NÃO é aleatória: o xlsx cobre as unidades maduras em abr/2026.",
           f"- Crescimento: município do hexágono pelo universo completo em {int((N.cres_municipio_origem == 'hex_estrutural').sum())} unidades e por nome em {int((N.cres_municipio_origem == 'nome_cadastro').sum())}. "
           f"{int(N.cres_municipio_diverge_cadastro.sum())} unidades têm a cidade do cadastro diferente do município do hexágono. Em quase todas é grafia ou região metropolitana (RA do DF, Grande Rio); a exceção é Sagrada Família, com pino em Cuiabá e cadastro em Rondonópolis, marcada como erro.",
           f"- Plano da Ultra: TotalPass no feed {int(N.tp_plano_ultra.notna().sum())} e no cadastro {int(N.tp_tem_agregador_cadastro.eq(True).sum())}; Wellhub {int(N.wh_plano_ultra.notna().sum())} / {int(N.wh_tem_agregador_cadastro.eq(True).sum())}. "
           f"O casamento aceita até 300 m (o piloto usa 120 m); a distância fica gravada. Em 10 unidades o cadastro de agosto diz TP1+ e o feed de setembro diz TP 2.",
           f"- Lifetime: {int(N.lt_eb_retencao_60d.notna().sum())} unidades com retenção EB. Uso da prob. 90d: {N.lt_prob_90d_uso.value_counts().to_dict()}.",
           f"- Rampa: {int(N.rampa_observavel.fillna(False).sum())} observáveis; {int(N.rampadesc_estabilizou_ate_hoje.fillna(False).sum())} estabilizaram até hoje (a mediana de 6 meses reproduz o estudo da Growth).",
           "\n## Fora do painel ou pendente (com motivo)\n",
           "- **Retenção de 12 meses da coorte de abertura e pré-venda:** colunas `rampa_ret12_*` e `rampa_n_alunos_prevenda` ficam NaN. Precisam de export agregado por unidade do Projeto Lifetime, que é base aluno a aluno.",
           "- **Tipo de imóvel e fachada:** não há fonte para a Ultra (colunas reservadas). O proxy é `poi_em_shopping`.",
           "- **Demografia GeoFusion 1 km do xlsx:** fora, por regra. É uma foto antiga e o Censo 2022 nas isócronas a substitui.",
           "- **Engenharia do Corpo:** fora deste painel, que é da Ultra. Ela é amostra de replicação dos testes (`data/analysis/poi`, `data/analysis/isocronas`).",
           "- **Corte de 'tier alto' nos planos:** não criado, porque é decisão de negócio. As features relativas (`pct_acima_ultra`, `gap_ord`) não dependem de corte.",
           "- **NPS por canal:** não ingerido. A coluna `nps` crua mistura canais.",
           "- **Demanda revelada TotalPass:** só no arquivo `LOCAL_` (procedência a confirmar); a cobertura está em `LOCAL_COBERTURA_demanda_totalpass.md`.",
           "\n## Cautelas de tempo (não usar como preditor de meses anteriores sem pensar)\n",
           "- **Lifetime** (2026-04..08), **planos** (set/2026), **concorrência** e **canibalização estática** (hoje), **POI** (CNPJ de set/2026 com estoque < 2025; OSM set/2026) e **cadastro** (ago/2026) são fotos atuais.",
           "- Para a exploração até dez/2025 (UNI-01), o que existe no tempo é o fato mensal: receita, ativos, agregadores, churn e canibalização no tempo.",
           "- Rampa: só em janelas a partir de `rampa_competencia_liberacao`. Os `rampadesc_*` são descrição ou desfecho."]
    cob.to_csv(UNI / "cobertura_por_unidade.csv", sep=";", encoding="utf-8-sig", index=False)
    (UNI / "COBERTURA_UNI00.md").write_text("\n".join(md), encoding="utf-8")
    # dicionario: uma linha por coluna
    dic = ["# Dicionário do painel BLK-UNI-00\n", "Uma linha por coluna. Cobertura = linhas com valor (fato) ou unidades com valor (dim; de %d da rede)." % len(N), ""]
    for nome, df, base in (("fato_unidade_mes", F, len(F)), ("dim_unidade", N, len(N))):
        dic += [f"## {nome}\n", "| coluna | tipo | cobertura | fonte | definição / escala | NaN significa |", "|---|---|---|---|---|---|"]
        for c in df.columns:
            fonte, defi, nan = descrever(c)
            dic.append(f"| `{c}` | {df[c].dtype} | {int(df[c].notna().sum())}/{base} | {fonte} | {defi} | {nan} |")
        dic.append("")
    (UNI / "DICIONARIO_UNI00.md").write_text("\n".join(dic), encoding="utf-8")
    lo = ["# SÓ LOCAL — demanda revelada TotalPass por unidade (NAO_ABRA; procedência a confirmar; nunca sai da máquina)\n",
          f"- Unidades com células de demanda na isócrona de carro 10 min: {int((L.tpd_celulas_c10 > 0).sum())} de {len(L)}. A fonte é metropolitana (SP ~66%); isócrona sem célula = não coberta (NaN).",
          f"- Colunas: {', '.join('`' + c + '`' for c in L.columns)}", "- A isócrona a pé ficou fora: células de ~1 km deixam a área a pé quase sempre vazia."]
    (UNI / "LOCAL_COBERTURA_demanda_totalpass.md").write_text("\n".join(lo), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
