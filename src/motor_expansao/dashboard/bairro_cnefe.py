"""Nome de bairro pelo CNEFE 2022, com a malha de setores do IBGE como RESERVA (DEC-076).

FONTE UNICA do nome de bairro do motor. Todas as superficies que nomeiam bairro (ranking e
ficha do hexagono no piloto, bairro do ponto no Relatorio Pontual e na ficha, perfil do
bairro, Relatorio Municipal e API/bot) leem os setores por algum caminho e passam por
`aplicar_bairro_cnefe` ANTES de resolver a localidade. A funcao reescreve `nome_bairro` /
`cod_bairro` do setor quando o CNEFE tem um bairro para ele; o resto da cadeia (a cascata
`nome_bairro -> nome_subdistrito -> nome_distrito` de `relatorio_municipal._localidade_do_setor`,
a dominancia por populacao no hexagono, o setor que contem o ponto) segue IDENTICO.

Por que o CNEFE: o `NM_BAIRRO` da malha 2022 falta em 587 dos 645 municipios de SP e, onde
existe, as vezes e' outra coisa (em Sao Jose dos Campos sao as 35 regioes de planejamento da
prefeitura, "Setor Socioeconomico 14"). O `DSC_LOCALIDADE` do CNEFE da' o bairro em 97,2% dos
setores do pais (BLK-BAIRRO-01, fase 1).

Artefato (derivado, OPCIONAL, gitignored): `<MOTOR_DATA_DIR>/staging/bairro_cnefe_setor/
uf=XX/part-000.parquet`, uma linha por setor com o bairro DOMINANTE (o de mais enderecos).
Sem o artefato, ou sem a UF, `aplicar_bairro_cnefe` devolve o MESMO objeto que recebeu: o
comportamento e' byte a byte o de antes (travado por teste).

Regra de nome, por setor:
- classe BAIRRO  -> o nome do CNEFE, em qualquer participacao (e' o dominante do setor; sem
  corte, ver DEC-076);
- classe RURAL   -> "Zona rural";
- MUNICIPIO / CODIGO / SEM_NOME / VAZIO / setor ausente -> o setor fica como esta (IBGE).

Grafia: o CNEFE vem em MAIUSCULAS e sem acento. Se o nome, normalizado, casar com um bairro/
subdistrito/distrito do IBGE do MESMO municipio, usa a grafia do IBGE (que tem acento). Senao,
Title Case portugues com acento restaurado por um dicionario CONSERVADOR (`_ACENTOS`): so
palavras de grafia acentuada unica; o que nao esta nele fica sem acento.

READ-ONLY sobre o M1: rotulo de exibicao, nao entra em score, carteira nem artefato oficial.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

#: Subdiretorio do artefato dentro de `<MOTOR_DATA_DIR>/staging/`.
SUBDIR_ARTEFATO = "bairro_cnefe_setor"
#: Rotulo de exibicao do setor que o CNEFE classifica como rural.
ROTULO_ZONA_RURAL = "Zona rural"
#: Valores de `fonte_bairro` (identificadores crus, NAO acentuar).
FONTE_CNEFE = "cnefe"
FONTE_IBGE = "ibge"

_CLASSE_BAIRRO = "BAIRRO"
_CLASSE_RURAL = "RURAL"
_COLUNAS_ARTEFATO = ["cod_setor", "bairro_cnefe", "classe"]


def diretorio_bairro_cnefe(censo_geo_dir: Path | str) -> Path:
    """`<MOTOR_DATA_DIR>/staging/bairro_cnefe_setor`, derivado do diretorio da malha geo.

    A malha mora em `<MOTOR_DATA_DIR>/outputs/setores_censitarios_2022_geo` nos tres lugares
    que a leem (piloto, API e o checkout local), e `outputs/` e `staging/` sao irmaos nos
    mounts de producao. Derivar daqui evita um parametro novo em cada chamador.
    """
    return Path(censo_geo_dir).parent.parent / "staging" / SUBDIR_ARTEFATO


def _arquivo_uf(raiz: Path, uf: str) -> Path:
    return raiz / f"uf={str(uf).upper()}" / "part-000.parquet"


def bairro_cnefe_disponivel(censo_geo_dir: Path | str | None, uf: str | None) -> bool:
    """O artefato existe para esta UF? (barato: um `stat`)."""
    if censo_geo_dir is None or not uf:
        return False
    return _arquivo_uf(diretorio_bairro_cnefe(censo_geo_dir), str(uf)).is_file()


@lru_cache(maxsize=8)
def _ler_uf(caminho: str, _mtime_ns: int) -> dict[str, tuple[str, str]]:
    """`cod_setor -> (bairro_cnefe, classe)` de uma UF. Cacheado por (caminho, mtime).

    O `mtime` na chave e' de proposito: um artefato substituido no disco e' relido sem
    restart, e a AUSENCIA nunca entra no cache (quem chama so' chega aqui com o arquivo).
    """
    df = pd.read_parquet(caminho, columns=_COLUNAS_ARTEFATO)
    mapa: dict[str, tuple[str, str]] = {}
    for cod, bruto, classe in zip(df["cod_setor"], df["bairro_cnefe"], df["classe"], strict=True):
        chave = _cod_setor_limpo(cod)
        if not chave:
            continue
        mapa[chave] = ("" if bruto is None or pd.isna(bruto) else str(bruto), str(classe))
    return mapa


def ler_bairro_cnefe_uf(raiz: Path | str, uf: str) -> dict[str, tuple[str, str]] | None:
    """Mapa do artefato de uma UF, ou `None` se ele nao existe (ou nao se le)."""
    arquivo = _arquivo_uf(Path(raiz), uf)
    try:
        mtime = arquivo.stat().st_mtime_ns
    except OSError:
        return None
    try:
        return _ler_uf(str(arquivo), mtime)
    except Exception:  # noqa: BLE001 - artefato ilegivel = ausente: o IBGE segue valendo
        return None


def _cod_setor_limpo(valor: Any) -> str:
    """Codigo do setor so' com digitos (a malha antiga carregava sufixo 'P' em alguns)."""
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    texto = str(valor).strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    return re.sub(r"\D", "", texto)


def normalizar_nome(valor: Any) -> str:
    """Sem acento, MAIUSCULO e espacos colapsados — a regua de comparacao entre as fontes."""
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    sem_acento = unicodedata.normalize("NFKD", str(valor)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento.upper()).strip()


# --- Grafia -----------------------------------------------------------------------------------

#: Conectivos em minusculas no MEIO do nome (no inicio e no fim ficam capitalizados: "Vila E").
_CONECTIVOS = frozenset({"DE", "DA", "DO", "DAS", "DOS", "E", "EM"})

#: Siglas que ficam em maiusculas. So' as que aparecem como nome de conjunto habitacional ou
#: instituicao em bairro; "CEU" NAO entra (e' "Céu" em "Jardim Céu Azul").
_SIGLAS = frozenset({
    "BNH", "CDHU", "COHAB", "CECAP", "IAPI", "INOCOOP", "IPESP", "CTA", "DCTA", "INPE", "DER",
    "SESC", "SESI", "CEASA", "URBIS", "COHAPAR", "CODHAB", "EMHAB", "PROHAB", "CEHAB", "USP",
})

#: Algarismo romano de 1 a 39 ("Vila XV de Novembro", "Jardim São José II").
_ROMANO = re.compile(r"^(?=[IVX]+$)X{0,3}(IX|IV|V?I{0,3})$")

#: Palavra sem acento (chave, MAIUSCULA) -> grafia acentuada (valor). CONSERVADOR: so entra
#: palavra cuja forma acentuada e' a UNICA possivel num nome de lugar. Fica fora o que tem
#: leitura sem acento comum ("SABIA" verbo, "PARA" preposicao, "SE" conjuncao, "FRANCA"
#: cidade x pais, "ESTEVAO"/"ESTEVAM", "HORTENCIA"/"HORTENSIA").
_ACENTOS: dict[str, str] = {
    # nomes de santo e de pessoa
    "SAO": "São", "JOSE": "José", "JOAO": "João", "ANTONIO": "Antônio", "SEBASTIAO": "Sebastião",
    "CRISTOVAO": "Cristóvão", "INES": "Inês", "LUIS": "Luís", "LUCIA": "Lúcia",
    "FATIMA": "Fátima", "NAZARE": "Nazaré", "GLORIA": "Glória", "VITORIA": "Vitória",
    "BARBARA": "Bárbara", "CECILIA": "Cecília", "EMILIA": "Emília", "AMELIA": "Amélia",
    "MARILIA": "Marília", "EFIGENIA": "Efigênia", "MONICA": "Mônica", "VERONICA": "Verônica",
    "ANGELA": "Ângela", "ANGELO": "Ângelo", "VALERIA": "Valéria", "PATRICIA": "Patrícia",
    "MARCIA": "Márcia", "MARCIO": "Márcio", "MARIO": "Mário", "CESAR": "César",
    "CICERO": "Cícero", "ABRAAO": "Abraão", "ADAO": "Adão", "NOE": "Noé", "MOISES": "Moisés",
    "TOME": "Tomé", "FELIX": "Félix", "CANDIDO": "Cândido", "CLAUDIO": "Cláudio",
    "CLAUDIA": "Cláudia", "SERGIO": "Sérgio", "ROGERIO": "Rogério", "HELIO": "Hélio",
    "JULIO": "Júlio", "JULIA": "Júlia", "OTAVIO": "Otávio", "FLAVIO": "Flávio",
    "LAZARO": "Lázaro", "ROMAO": "Romão", "SIMAO": "Simão", "VINICIUS": "Vinícius",
    "ANDRE": "André", "MAGALHAES": "Magalhães", "GUIMARAES": "Guimarães",
    # devocoes e datas
    "CONCEICAO": "Conceição", "ASSUNCAO": "Assunção", "ASCENSAO": "Ascensão",
    "ANUNCIACAO": "Anunciação", "ENCARNACAO": "Encarnação", "RESSURREICAO": "Ressurreição",
    "CONSOLACAO": "Consolação", "GRACA": "Graça", "GRACAS": "Graças", "ROSARIO": "Rosário",
    "CANDELARIA": "Candelária", "BELEM": "Belém", "JERUSALEM": "Jerusalém",
    "BETANIA": "Betânia", "CANAA": "Canaã", "PARAISO": "Paraíso", "CEU": "Céu",
    "INDEPENDENCIA": "Independência", "REPUBLICA": "República", "ABOLICAO": "Abolição",
    "PATRIA": "Pátria", "UNIAO": "União", "ESPERANCA": "Esperança", "IMPERIO": "Império",
    # lugares e gentilicos
    "BRASILIA": "Brasília", "AMERICA": "América", "AMERICAS": "Américas", "AFRICA": "África",
    "ASIA": "Ásia", "MEXICO": "México", "CANADA": "Canadá", "JAPAO": "Japão",
    "ITALIA": "Itália", "SUICA": "Suíça", "BELGICA": "Bélgica", "GRECIA": "Grécia",
    "PARANA": "Paraná", "GOIAS": "Goiás", "PIAUI": "Piauí", "AMAPA": "Amapá",
    "CEARA": "Ceará", "MARANHAO": "Maranhão", "AMAZONIA": "Amazônia", "MARINGA": "Maringá",
    "ATLANTICO": "Atlântico", "PACIFICO": "Pacífico", "PETROPOLIS": "Petrópolis",
    "HELIOPOLIS": "Heliópolis", "TERESOPOLIS": "Teresópolis",
    "FLORIANOPOLIS": "Florianópolis", "ANAPOLIS": "Anápolis",
    "PARAISOPOLIS": "Paraisópolis", "BRASILANDIA": "Brasilândia", "TATUAPE": "Tatuapé",
    "BUTANTA": "Butantã", "JACANA": "Jaçanã", "TREMEMBE": "Tremembé", "GRAJAU": "Grajaú",
    "JARAGUA": "Jaraguá", "SACOMA": "Sacomã", "CARRAO": "Carrão", "LIMAO": "Limão",
    "IRAJA": "Irajá", "INHAUMA": "Inhaúma", "MEIER": "Méier", "GALEAO": "Galeão",
    "GAVEA": "Gávea", "JACARE": "Jacaré", "SAUDE": "Saúde", "BRAS": "Brás",
    # paisagem e equipamento urbano
    "AGUA": "Água", "AGUAS": "Águas", "ACUCAR": "Açúcar", "IPE": "Ipê", "IPES": "Ipês",
    "PAO": "Pão", "SITIO": "Sítio", "SITIOS": "Sítios", "CHACARA": "Chácara",
    "CHACARAS": "Chácaras", "ESTACAO": "Estação", "CORREGO": "Córrego",
    "RIBEIRAO": "Ribeirão", "VARZEA": "Várzea", "CAPAO": "Capão", "SERTAO": "Sertão",
    "SERTAOZINHO": "Sertãozinho", "PORTAO": "Portão", "PRACA": "Praça", "MARE": "Maré",
    "SATELITE": "Satélite", "INDUSTRIAS": "Indústrias", "OPERARIO": "Operário",
    "OPERARIA": "Operária", "UNIVERSITARIO": "Universitário",
    "UNIVERSITARIA": "Universitária", "RODOVIARIA": "Rodoviária", "ESTADIO": "Estádio",
    "HIPICA": "Hípica", "NAUTICO": "Náutico", "OLIMPICO": "Olímpico",
    "PANORAMICO": "Panorâmico", "MANSOES": "Mansões", "COLONIA": "Colônia",
    "ORQUIDEAS": "Orquídeas", "ACACIAS": "Acácias", "MAGNOLIAS": "Magnólias",
    "LIRIOS": "Lírios", "CAMELIAS": "Camélias", "GIRASSOIS": "Girassóis",
    "GARDENIA": "Gardênia", "PASSARO": "Pássaro", "PASSAROS": "Pássaros",
    "HABITACAO": "Habitação", "FUNDACAO": "Fundação", "INTEGRACAO": "Integração",
    "ASSOCIACAO": "Associação", "COOPERACAO": "Cooperação",
    # Medidas na malha de SP (20/10): palavras do CNEFE cuja UNICA grafia no IBGE e' acentuada
    # (nenhuma ocorrencia sem acento), conferidas uma a uma. Ficaram de fora as que o IBGE
    # grafa errado ("Bangú", "Cumbíca", "Jóckey") ou que tem outra leitura ("PARA", "CARA",
    # "POMPEIA", que o Acordo de 1990 tirou o acento).
    "TRES": "Três", "CONDOMINIO": "Condomínio", "BOQUEIRAO": "Boqueirão", "POCO": "Poço",
    "CALIFORNIA": "Califórnia", "NACOES": "Nações", "SONIA": "Sônia",
    "CENTENARIO": "Centenário", "BALNEARIO": "Balneário", "ESTANCIA": "Estância",
    "RINCAO": "Rincão", "MARACANA": "Maracanã", "CAICARA": "Caiçara", "LOURENCO": "Lourenço",
    "CURUCA": "Curuçá", "ALIANCA": "Aliança", "JATOBA": "Jatobá", "REGIAO": "Região",
    "AREA": "Área", "TABOAO": "Taboão", "GUARA": "Guará", "IRIS": "Íris", "ELISEOS": "Elíseos",
    "BONIFACIO": "Bonifácio", "BOTANICO": "Botânico", "GONCALO": "Gonçalo",
    "ESPIRITO": "Espírito", "IRMAOS": "Irmãos", "SUMARE": "Sumaré", "TARUMA": "Tarumã",
    "ITAPUA": "Itapuã", "ACU": "Açu", "GALVAO": "Galvão", "HIGIENOPOLIS": "Higienópolis",
    "JUNIOR": "Júnior", "HUMAITA": "Humaitá", "MARABA": "Marabá", "VIRGINIA": "Virgínia",
    "AVIACAO": "Aviação", "REDENCAO": "Redenção", "CANDIDA": "Cândida", "INGA": "Ingá",
    "JACUI": "Jacuí", "BARAO": "Barão", "SAPE": "Sapê", "FLORIDA": "Flórida",
    "MONTANHAO": "Montanhão", "MAE": "Mãe", "ANGELICA": "Angélica", "MAUA": "Mauá",
    "PARAIBA": "Paraíba", "CERAMICA": "Cerâmica", "JAGUARE": "Jaguaré", "INDAIA": "Indaiá",
    "VALPARAISO": "Valparaíso", "ORATORIO": "Oratório", "JORDAO": "Jordão", "IRMA": "Irmã",
    "CASSIA": "Cássia", "COLEGIO": "Colégio", "PEREQUE": "Perequê", "CIPO": "Cipó",
    "CABUCU": "Cabuçu", "LIBANO": "Líbano", "PICANCO": "Picanço", "ITARARE": "Itararé",
    "GUARUJA": "Guarujá", "CAMBUI": "Cambuí", "GAVIAO": "Gavião", "EMBARE": "Embaré",
    "CAMARAO": "Camarão", "BRACO": "Braço", "NOBREGA": "Nóbrega",
    "ATLANTICA": "Atlântica", "TIETE": "Tietê", "TAMANDARE": "Tamandaré", "MATAO": "Matão",
    "AMERICO": "Américo", "MENDONCA": "Mendonça", "ALVARO": "Álvaro",
    "CAMPANARIO": "Campanário", "BONANCA": "Bonança", "ESPIGAO": "Espigão",
    "CUIABA": "Cuiabá", "EUGENIO": "Eugênio", "SINHA": "Sinhá", "SIMOES": "Simões",
    "PAQUETA": "Paquetá", "ANTARTICA": "Antártica", "OLIMPIA": "Olímpia",
    "REMEDIOS": "Remédios", "CORUMBA": "Corumbá", "PILOES": "Pilões", "GARCAS": "Garças",
    "LINDOIA": "Lindóia", "FLORENCA": "Florença", "OSORIO": "Osório", "LIRIO": "Lírio",
    "VALENCA": "Valença", "JUNDIAI": "Jundiaí", "AUREA": "Áurea", "OASIS": "Oásis",
    "ARMACAO": "Armação", "NAUTICA": "Náutica", "AREIAO": "Areião", "MEDICI": "Médici",
    "METALURGICA": "Metalúrgica", "TUPA": "Tupã", "PROMISSAO": "Promissão",
    "CHAPEU": "Chapéu", "HORTENCIAS": "Hortências", "FERNAO": "Fernão",
    "ROSALIA": "Rosália", "ARAUCARIA": "Araucária", "HISTORICO": "Histórico",
    "RADIO": "Rádio", "EXPANSAO": "Expansão", "ANTONIA": "Antônia", "LUCIO": "Lúcio",
    "JACAREI": "Jacareí", "NUCLEO": "Núcleo", "EUGENIA": "Eugênia",
}


def _capitalizar_parte(parte: str) -> str:
    """Uma parte de palavra (sem hifen/apostrofo) em grafia de nome proprio."""
    if not parte:
        return parte
    if parte in _SIGLAS or _ROMANO.match(parte):
        return parte
    if any(ch.isdigit() for ch in parte):
        return parte  # "1A", "2ª", "15" — fica como o IBGE escreveu
    if len(parte) == 1:
        return parte  # letra de quadra/loteamento: "Vila A", "Jardim B"
    if parte in _ACENTOS:
        return _ACENTOS[parte]
    return parte[0] + parte[1:].lower()


def _formatar_palavra(palavra: str, *, primeira: bool, ultima: bool) -> str:
    if palavra in _CONECTIVOS and not primeira and not ultima:
        return palavra.lower()
    # Hifen, apostrofo e barra separam partes que se capitalizam sozinhas ("D'Oeste").
    partes = re.split(r"([-'/])", palavra)
    return "".join(p if p in {"-", "'", "/"} else _capitalizar_parte(p) for p in partes)


def title_case_portugues(bruto: Any) -> str:
    """Nome cru do CNEFE (MAIUSCULO, sem acento) em grafia de exibicao, com acento por dicionario."""
    palavras = normalizar_nome(bruto).split(" ")
    palavras = [p for p in palavras if p]
    n = len(palavras)
    return " ".join(
        _formatar_palavra(p, primeira=i == 0, ultima=i == n - 1) for i, p in enumerate(palavras)
    )


def formatar_nome_cnefe(bruto: Any, grafias_ibge: dict[str, str] | None = None) -> str:
    """Grafia de exibicao do bairro do CNEFE.

    `grafias_ibge`: `nome normalizado -> grafia do IBGE` do MESMO municipio. Quando o nome casa,
    a grafia do IBGE vence (ela tem acento e a capitalizacao oficial). Senao, Title Case com o
    dicionario de acentos.
    """
    chave = normalizar_nome(bruto)
    if not chave:
        return ""
    if grafias_ibge:
        grafia = grafias_ibge.get(chave)
        if grafia:
            return grafia
    return title_case_portugues(chave)


def _grafias_por_municipio(setores: pd.DataFrame, cods_muni: pd.Series) -> dict[str, dict[str, str]]:
    """`cod_municipio -> {nome normalizado: grafia do IBGE}`, com os niveis bairro/subdistrito/distrito.

    So' grafia que TEM minuscula entra: uma grafia toda em maiusculas nao ensina nada sobre
    acento nem capitalizacao. Varias grafias para o mesmo nome -> a mais frequente, desempate
    pela ordem alfabetica (deterministico, nao depende da ordem das linhas).
    """
    contagem: dict[str, dict[str, dict[str, int]]] = {}
    for col in ("nome_bairro", "nome_subdistrito", "nome_distrito"):
        if col not in setores.columns:
            continue
        for cod, valor in zip(cods_muni, setores[col], strict=True):
            if valor is None:
                continue
            try:
                if pd.isna(valor):
                    continue
            except (TypeError, ValueError):
                continue
            grafia = str(valor).strip()
            if not grafia or grafia.upper() == grafia:
                continue
            chave = normalizar_nome(grafia)
            if not chave:
                continue
            balde = contagem.setdefault(cod, {}).setdefault(chave, {})
            balde[grafia] = balde.get(grafia, 0) + 1
    return {
        cod: {
            chave: sorted(opcoes.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            for chave, opcoes in por_nome.items()
        }
        for cod, por_nome in contagem.items()
    }


def aplicar_bairro_cnefe(
    setores: pd.DataFrame,
    *,
    censo_geo_dir: Path | str | None,
    uf: str | None = None,
) -> pd.DataFrame:
    """Reescreve o bairro dos setores pelo CNEFE 2022; o IBGE fica como reserva. FONTE UNICA.

    Para cada setor que o artefato classifica como BAIRRO (ou RURAL), `nome_bairro` passa a ser
    o nome do CNEFE em grafia de exibicao (ou "Zona rural") e `cod_bairro` uma chave sintetica
    `cnefe:<cod_municipio>:<NOME>` — a mesma para todos os setores daquele bairro no municipio,
    que e' o que o perfil do bairro (`agregar_perfil_bairro_distrito`) usa para juntar a unidade.
    Os valores originais ficam em `nome_bairro_ibge` / `cod_bairro_ibge`, e `fonte_bairro` diz
    de onde veio cada linha (`cnefe`/`ibge`).

    Devolve o MESMO objeto, intocado, quando nao ha o que aplicar: frame vazio, sem
    `cod_setor`, sem `censo_geo_dir`, sem o artefato da(s) UF(s) ou nenhum setor coberto. E'
    essa identidade que garante o "byte a byte" sem o artefato.

    `uf`: a UF quando o frame nao tem a coluna `uf` (a particao lida por
    `ler_particao_setores` com colunas escolhidas nao a traz). Com a coluna, ela manda — o
    frame do ponto de divisa junta municipios de UFs diferentes.
    """
    if setores is None or getattr(setores, "empty", True) or censo_geo_dir is None:
        return setores
    if "cod_setor" not in setores.columns:
        return setores
    raiz = diretorio_bairro_cnefe(censo_geo_dir)
    uf_padrao = str(uf).upper().strip() if uf else ""
    if "uf" in setores.columns:
        ufs = [
            (str(u).upper().strip() if u is not None and not pd.isna(u) else "") or uf_padrao
            for u in setores["uf"]
        ]
    else:
        if not uf_padrao:
            return setores
        ufs = [uf_padrao] * len(setores)
    mapas: dict[str, dict[str, tuple[str, str]]] = {}
    for u in sorted(set(ufs)):
        if not u:
            continue
        mapa = ler_bairro_cnefe_uf(raiz, u)
        if mapa:
            mapas[u] = mapa
    if not mapas:
        return setores

    cods = [_cod_setor_limpo(c) for c in setores["cod_setor"]]
    achados: list[tuple[str, str] | None] = []
    for u, cod in zip(ufs, cods, strict=True):
        entrada = mapas.get(u, {}).get(cod) if cod else None
        if entrada is not None and entrada[1] in (_CLASSE_BAIRRO, _CLASSE_RURAL):
            achados.append(entrada)
        else:
            achados.append(None)
    if not any(a is not None for a in achados):
        return setores

    cods_muni = pd.Series([c[:7] for c in cods], index=setores.index)
    grafias = _grafias_por_municipio(setores, cods_muni)

    nomes: list[Any] = []
    chaves: list[Any] = []
    fontes: list[str] = []
    nome_ibge = setores["nome_bairro"] if "nome_bairro" in setores.columns else None
    cod_ibge = setores["cod_bairro"] if "cod_bairro" in setores.columns else None
    for i, (achado, cod_muni) in enumerate(zip(achados, cods_muni, strict=True)):
        if achado is None:
            nomes.append(nome_ibge.iat[i] if nome_ibge is not None else pd.NA)
            chaves.append(cod_ibge.iat[i] if cod_ibge is not None else pd.NA)
            fontes.append(FONTE_IBGE)
            continue
        bruto, classe = achado
        if classe == _CLASSE_RURAL:
            nome = ROTULO_ZONA_RURAL
        else:
            nome = formatar_nome_cnefe(bruto, grafias.get(cod_muni))
        nomes.append(nome)
        chaves.append(f"cnefe:{cod_muni}:{normalizar_nome(nome)}")
        fontes.append(FONTE_CNEFE)

    out = setores.copy()
    out["nome_bairro_ibge"] = nome_ibge if nome_ibge is not None else pd.NA
    out["cod_bairro_ibge"] = cod_ibge if cod_ibge is not None else pd.NA
    out["nome_bairro"] = pd.Series(nomes, index=setores.index, dtype=object)
    out["cod_bairro"] = pd.Series(chaves, index=setores.index, dtype=object)
    out["fonte_bairro"] = pd.Series(fontes, index=setores.index, dtype=object)
    return out
