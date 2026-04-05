"""
jobs/pipelines/ibge_censo.py — Ingestão de dados do Censo IBGE 2022

Baixa e processa os Agregados por Setores Censitários do Censo 2022.
Fornece renda média, perfil etário e densidade para enriquecer hexágonos H3.

Fontes:
  - Agregados por Setores Censitários: https://downloads.ibge.gov.br/
  - API SIDRA: https://apisidra.ibge.gov.br/
"""

import io
import json
import re
import time
import unicodedata
import zipfile
from pathlib import Path
from functools import lru_cache
from typing import Optional

import h3
import numpy as np
import pandas as pd
import requests
import shapely
import structlog
from shapely.geometry import shape
from shapely.strtree import STRtree

log = structlog.get_logger()

CACHE_DIR = Path("data/ibge")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

IBGE_SETORES_BASE_URL = "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios"
IBGE_MALHA_MUNICIPIOS_URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/estados/{uf}"
    "?intrarregiao=municipio&formato=application/vnd.geo+json&qualidade=maxima"
)
SIDRA_RENDA_MUNICIPIO       = "10297"   # massa rendimento per capita — retorna sigiloso em cidades grandes
SIDRA_RENDA_MEDIO_MUNICIPIO = "10295"   # rendimento MÉDIO domiciliar per capita Censo 2022 — sem sigilo
SIDRA_VAR_RENDA_MEDIO       = "13431"   # var: Valor do rendimento nominal médio mensal domiciliar per capita
SIDRA_POPULACAO_FAIXA       = "9514"
SIDRA_PESOS_IDADE_18_45 = {
    "93086": 0.40,  # 15 a 19 anos -> proxy 18-19
    "93087": 1.00,  # 20 a 24 anos
    "93088": 1.00,  # 25 a 29 anos
    "93089": 1.00,  # 30 a 34 anos
    "93090": 1.00,  # 35 a 39 anos
    "93091": 1.00,  # 40 a 44 anos
    "93092": 0.20,  # 45 a 49 anos -> proxy 45
}


class IBGECenso:
    # UFs onde o download do shapefile já falhou nesta sessão — evita retry por hexágono
    _uf_download_falhou: set = set()

    def __init__(self):
        self._gdf_setores = None
        self._df_municipios = None
        self._municipio_padrao: Optional[str] = None
        self._uf_padrao: Optional[str] = None

    def baixar_setores_uf(self, uf: str) -> Path:
        uf = uf.upper()
        if uf in IBGECenso._uf_download_falhou:
            return CACHE_DIR / uf  # já falhou antes, não tenta de novo

        cache_path = CACHE_DIR / uf
        shp_path = cache_path / f"setores_{uf}.shp"
        if shp_path.exists():
            log.info("ibge_setores_cache_hit", uf=uf)
            return cache_path

        cache_path.mkdir(parents=True, exist_ok=True)
        log.info("ibge_setores_download_iniciado", uf=uf)

        # Tenta múltiplos padrões de URL do FTP IBGE
        urls_candidatas = [
            f"{IBGE_SETORES_BASE_URL}/Shapefile/{uf}_Malha_Preliminar_2022.zip",
            f"{IBGE_SETORES_BASE_URL}/{uf}_Malha_Preliminar_2022.zip",
            f"https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022/setores/{uf}_Malha_Preliminar_2022.zip",
        ]
        baixou = False
        for url in urls_candidatas:
            try:
                resp = requests.get(url, timeout=120, stream=True)
                resp.raise_for_status()
                z = zipfile.ZipFile(io.BytesIO(resp.content))
                z.extractall(cache_path)
                log.info("ibge_setores_download_ok", uf=uf, url=url)
                baixou = True
                break
            except Exception:
                continue

        if not baixou:
            log.warning("ibge_setores_indisponivel", uf=uf,
                        msg="Shapefile nao encontrado — usando SIDRA municipio como fallback")
            IBGECenso._uf_download_falhou.add(uf)

        return cache_path

    def carregar_setores(self, uf: str):
        try:
            import geopandas as gpd
        except ImportError:
            log.warning("geopandas_nao_instalado", msg="pip install geopandas")
            return None
        cache_path = self.baixar_setores_uf(uf)
        shp_files = list(cache_path.glob("*.shp"))
        if not shp_files:
            return None
        gdf = gpd.read_file(shp_files[0])
        gdf = gdf.to_crs(epsg=4326)
        log.info("ibge_setores_carregados", uf=uf, total=len(gdf))
        return gdf

    def set_municipio_padrao(self, cod_municipio: str, uf: str) -> None:
        """
        Define município padrão para evitar reverse geocoding por hexágono.
        Usar quando o pipeline já sabe qual cidade está processando.
        Elimina N chamadas Nominatim → 1 chamada única no início.
        """
        self._municipio_padrao = cod_municipio
        self._uf_padrao = uf
        log.info("municipio_padrao_definido", cod=cod_municipio, uf=uf)

    def resolver_municipio(self, cidade: str, uf: str) -> Optional[str]:
        """
        Resolve o código IBGE de um município pelo nome + UF.
        Usar no início do pipeline para chamar set_municipio_padrao().
        Consulta a API IBGE de localidades — sem Nominatim.
        """
        cod = self._buscar_cod_ibge_por_nome(cidade, uf)
        if cod:
            self.set_municipio_padrao(cod, uf)
            log.info("municipio_resolvido", cidade=cidade, uf=uf, cod=cod)
        else:
            log.warning("municipio_nao_resolvido", cidade=cidade, uf=uf)
        return cod

    def features_para_coordenada(self, lat: float, lng: float, uf: str = "") -> dict:
        if self._gdf_setores is None and uf:
            self._gdf_setores = self.carregar_setores(uf)
        if self._gdf_setores is not None:
            try:
                from shapely.geometry import Point
                ponto = Point(lng, lat)
                setor = self._gdf_setores[self._gdf_setores.geometry.contains(ponto)]
                if not setor.empty:
                    row = setor.iloc[0]
                    return {
                        "cod_setor":        str(row.get("CD_SETOR", "")),
                        "pop_total":        float(row.get("V002", 0) or 0),
                        "n_domicilios":     float(row.get("V001", 0) or 0),
                        "area_km2":         float(row.get("AREA_KM2", 0.1) or 0.1),
                        "densidade_dom":    float(row.get("V001", 0) or 0) / max(float(row.get("AREA_KM2", 0.1) or 0.1), 0.01),
                        "renda_per_capita": float(row.get("V6531", 0) or 0),
                        "pop_18_45":        float(row.get("V18_45", 0) or 0),
                        "fonte":            "ibge_setor_2022",
                    }
            except Exception as e:
                log.warning("setor_lookup_erro", erro=str(e))
        return self._features_municipio_sidra(lat, lng)

    def features_para_hex(self, hex_id: str, uf: str = "") -> dict:
        lat, lng = h3.cell_to_latlng(hex_id)
        return self.features_para_coordenada(lat, lng, uf)

    def _features_municipio_sidra(self, lat: float, lng: float) -> dict:
        cod = getattr(self, '_municipio_padrao', None) or self._geocodigo_municipio(lat, lng)
        if not cod or cod == "__nenhum__":
            return self._features_padrao()
        return self._sidra_renda_populacao(cod)

    @lru_cache(maxsize=1000)
    def _sidra_renda_populacao(self, cod_municipio: str) -> dict:
        resultado = self._features_padrao()

        # Fonte primária: t.10295 v.13431 — rendimento médio domiciliar per capita Censo 2022
        # Não retorna sigiloso (..) para municípios grandes — ao contrário de t.10297
        renda_ok = False
        try:
            url = (
                f"https://apisidra.ibge.gov.br/values/t/{SIDRA_RENDA_MEDIO_MUNICIPIO}"
                f"/n6/{cod_municipio}/v/{SIDRA_VAR_RENDA_MEDIO}/p/last"
            )
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                dados = resp.json()
                if len(dados) >= 2:
                    valor = str(dados[1].get("V", "")).strip().replace(",", ".")
                    sem_dado = valor in ("...", "..", "-", "", "X", "x")
                    if not sem_dado:
                        resultado["renda_per_capita"] = float(valor)
                        resultado["fonte_renda"] = "ibge_censo2022_t10295"
                        renda_ok = True
        except Exception as e:
            log.warning("sidra_renda_medio_erro", cod=cod_municipio, erro=str(e))

        # Fallback: t.10297 — massa rendimento per capita (pode retornar sigiloso)
        if not renda_ok:
            try:
                url = f"https://apisidra.ibge.gov.br/values/t/{SIDRA_RENDA_MUNICIPIO}/n6/{cod_municipio}/v/allxp/p/last"
                resp = requests.get(url, timeout=30)
                if resp.status_code == 200:
                    dados = resp.json()
                    if len(dados) >= 2:
                        valor = str(dados[1].get("V", "0")).strip().replace(",", ".")
                        sem_dado = valor in ("...", "..", "-", "", "X", "x")
                        resultado["renda_per_capita"] = float(valor) if not sem_dado else 0
                        resultado["fonte_renda"] = "ibge_censo2022_t10297_fallback"
            except Exception as e:
                log.warning("sidra_renda_erro", cod=cod_municipio, erro=str(e))

        time.sleep(0.5)
        try:
            url = (
                f"https://apisidra.ibge.gov.br/values/t/{SIDRA_POPULACAO_FAIXA}"
                f"/n6/{cod_municipio}/v/93/p/last/c287/{','.join(SIDRA_PESOS_IDADE_18_45)}"
            )
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                dados = resp.json()
                pop = 0.0
                for d in dados[1:]:
                    valor = str(d.get("V", "")).strip()
                    if valor in ["...", "..", "-", "", "X", "x"]:
                        continue
                    codigo_idade = str(d.get("D4C", "")).strip()
                    peso = SIDRA_PESOS_IDADE_18_45.get(codigo_idade, 1.0)
                    pop += float(valor.replace(",", ".")) * peso
                resultado["pop_18_45"] = pop
        except Exception as e:
            log.warning("sidra_pop_erro", cod=cod_municipio, erro=str(e))
        fonte_renda = resultado.pop("fonte_renda", "ibge_censo2022_sem_renda")
        resultado["fonte"] = f"ibge_sidra_municipio_2022+{fonte_renda}"
        resultado["cod_municipio"] = cod_municipio
        return resultado

    @lru_cache(maxsize=500)
    def _geocodigo_municipio(self, lat: float, lng: float) -> Optional[str]:
        try:
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {"lat": lat, "lon": lng, "format": "json", "zoom": 10, "addressdetails": 1}
            headers = {"User-Agent": "motor-expansao-ultra/1.0"}
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            time.sleep(1.1)
            if resp.status_code == 200:
                data = resp.json()
                cidade = data.get("address", {}).get("city") or data.get("address", {}).get("town")
                uf = data.get("address", {}).get("state_code", "")
                if cidade:
                    return self._buscar_cod_ibge_por_nome(cidade, uf)
        except Exception as e:
            log.warning("geocodigo_erro", erro=str(e))
        return None

    @lru_cache(maxsize=500)
    def _buscar_cod_ibge_por_nome(self, cidade: str, uf: str) -> Optional[str]:
        def normalizar(s: str) -> str:
            """Remove acentos e converte para minúsculas para comparação."""
            return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()

        cidade_norm = normalizar(cidade)
        uf_norm = uf.lower()
        try:
            resp = requests.get(
                "https://servicodados.ibge.gov.br/api/v1/localidades/municipios",
                timeout=15,
            )
            if resp.status_code == 200:
                for m in resp.json():
                    try:
                        nome_ibge = normalizar(m["nome"])
                        uf_ibge   = m["microrregiao"]["mesorregiao"]["UF"]["sigla"].lower()
                        if nome_ibge == cidade_norm and uf_ibge == uf_norm:
                            return str(m["id"])
                    except (TypeError, KeyError):
                        continue
        except Exception:
            pass
        return None

    def baixar_renda_todos_municipios(self) -> pd.DataFrame:
        cache_file = CACHE_DIR / "renda_municipios_2022.parquet"
        if cache_file.exists():
            log.info("renda_cache_hit")
            return pd.read_parquet(cache_file)
        log.info("baixando_renda_todos_municipios")
        try:
            url = f"https://apisidra.ibge.gov.br/values/t/{SIDRA_RENDA_MUNICIPIO}/n6/all/v/allxp/p/last"
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            raw = resp.json()
            df = pd.DataFrame(raw[1:])
            df.columns = [str(c) for c in df.columns]
            valor_col = [c for c in df.columns if "alor" in c or c == "V"]
            cod_col   = [c for c in df.columns if "digo" in c or "6" in c]
            if valor_col and cod_col:
                df = df.rename(columns={valor_col[0]: "renda_per_capita", cod_col[0]: "cod_municipio"})
                df["renda_per_capita"] = pd.to_numeric(
                    df["renda_per_capita"].replace({"...": None, "-": None, "": None}), errors="coerce"
                )
                df = df[["cod_municipio", "renda_per_capita"]].dropna()
                df.to_parquet(cache_file, index=False)
                log.info("renda_municipios_ok", total=len(df))
                return df
        except Exception as e:
            log.error("renda_municipios_erro", erro=str(e))
        return pd.DataFrame()

    def carregar_demografia_municipios(self, refresh: bool = False) -> pd.DataFrame:
        cache_file = CACHE_DIR / "demografia_municipios_2022.parquet"
        if cache_file.exists() and not refresh:
            log.info("demografia_municipios_cache_hit", path=str(cache_file))
            return pd.read_parquet(cache_file)

        log.info("demografia_municipios_download_iniciado")
        df_renda = self._baixar_renda_municipios_sidra()
        df_pop = self._baixar_populacao_18_45_municipios_sidra()

        if df_renda.empty:
            raise RuntimeError("SIDRA renda municipal nao retornou dados para a carga nacional.")
        if df_pop.empty:
            raise RuntimeError("SIDRA populacao 18-45 municipal nao retornou dados para a carga nacional.")

        df = df_renda.merge(df_pop, on="cod_municipio", how="outer")
        if "pop_total" not in df.columns:
            df["pop_total"] = 0.0
        if "n_domicilios" not in df.columns:
            df["n_domicilios"] = 0.0
        if "densidade_dom" not in df.columns:
            df["densidade_dom"] = 0.0
        df["renda_per_capita"] = pd.to_numeric(df["renda_per_capita"], errors="coerce").fillna(0.0)
        df["pop_18_45"] = pd.to_numeric(df["pop_18_45"], errors="coerce").fillna(0.0)
        df["pop_total"] = pd.to_numeric(df["pop_total"], errors="coerce").fillna(0.0)
        df["n_domicilios"] = pd.to_numeric(df["n_domicilios"], errors="coerce").fillna(0.0)
        df["densidade_dom"] = pd.to_numeric(df["densidade_dom"], errors="coerce").fillna(0.0)
        df["fonte_renda"] = df["fonte_renda"].fillna("ibge_censo2022_sem_renda")
        df["fonte_populacao"] = df["fonte_populacao"].fillna("ibge_censo2022_sem_populacao")
        df["fonte_demografica"] = (
            "ibge_sidra_municipio_2022+"
            + df["fonte_renda"].astype(str)
            + "+"
            + df["fonte_populacao"].astype(str)
        )
        df = df[
            [
                "cod_municipio",
                "renda_per_capita",
                "pop_total",
                "pop_18_45",
                "n_domicilios",
                "densidade_dom",
                "fonte_demografica",
            ]
        ].drop_duplicates(subset=["cod_municipio"])
        df.to_parquet(cache_file, index=False)
        log.info("demografia_municipios_download_ok", total=len(df), path=str(cache_file))
        return df

    def baixar_malha_municipios_uf(self, uf: str, refresh: bool = False) -> Path:
        uf = uf.upper()
        cache_path = CACHE_DIR / f"municipios_{uf}.geojson"
        if cache_path.exists() and not refresh:
            return cache_path

        resp = requests.get(IBGE_MALHA_MUNICIPIOS_URL.format(uf=uf), timeout=120)
        resp.raise_for_status()
        payload = resp.json()
        cache_path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        log.info("malha_municipios_uf_ok", uf=uf, path=str(cache_path))
        return cache_path

    def carregar_malha_municipios_uf(self, uf: str, refresh: bool = False) -> pd.DataFrame:
        cache_path = self.baixar_malha_municipios_uf(uf=uf, refresh=refresh)
        payload = json.loads(cache_path.read_text(encoding="utf-8"))

        registros = []
        for feature in payload.get("features", []):
            properties = feature.get("properties", {})
            cod_municipio = self._extrair_codigo_municipio_feature(properties)
            nome_municipio = properties.get("nome") or properties.get("NM_MUN") or properties.get("name") or ""
            if not cod_municipio:
                continue
            registros.append(
                {
                    "cod_municipio": cod_municipio,
                    "nome_municipio": nome_municipio,
                    "geometry": shape(feature["geometry"]),
                }
            )

        if not registros:
            raise RuntimeError(f"Malha municipal da UF {uf} veio vazia ou sem codigos IBGE.")

        df = pd.DataFrame(registros).drop_duplicates(subset=["cod_municipio"]).reset_index(drop=True)
        log.info("malha_municipios_uf_carregada", uf=uf, municipios=len(df))
        return df

    def enriquecer_dataframe_hexagonos(
        self,
        df_hex: pd.DataFrame,
        uf: str,
        refresh_malha: bool = False,
        refresh_demografia: bool = False,
    ) -> pd.DataFrame:
        if df_hex.empty:
            return df_hex.copy()

        df_municipios = self.carregar_malha_municipios_uf(uf=uf, refresh=refresh_malha)
        df_demografia = self.carregar_demografia_municipios(refresh=refresh_demografia)

        tree = STRtree(df_municipios["geometry"].tolist())
        pontos = shapely.points(df_hex["lng"].to_numpy(), df_hex["lat"].to_numpy())
        pares = tree.query(pontos, predicate="within")
        codigos = np.full(len(df_hex), None, dtype=object)

        if pares.size:
            codigos[pares[0]] = df_municipios["cod_municipio"].to_numpy()[pares[1]]

        df = df_hex.copy()
        df["cod_municipio"] = codigos

        faltantes = pd.isna(df["cod_municipio"]).to_numpy()
        if faltantes.any():
            pares_intersects = tree.query(pontos[faltantes], predicate="intersects")
            if pares_intersects.size:
                idx_hex = np.where(faltantes)[0][pares_intersects[0]]
                codigos[idx_hex] = df_municipios["cod_municipio"].to_numpy()[pares_intersects[1]]
                df["cod_municipio"] = codigos

        faltantes_total = int(pd.isna(df["cod_municipio"]).sum())
        if faltantes_total:
            idx_faltantes = np.where(pd.isna(df["cod_municipio"]).to_numpy())[0]
            codigos_municipio = df_municipios["cod_municipio"].to_numpy()
            for idx_hex in idx_faltantes:
                idx_municipio = tree.nearest(pontos[idx_hex])
                if idx_municipio is None:
                    continue
                codigos[idx_hex] = codigos_municipio[int(idx_municipio)]
            df["cod_municipio"] = codigos

        faltantes_total = int(pd.isna(df["cod_municipio"]).sum())
        if faltantes_total:
            raise RuntimeError(f"{uf}: {faltantes_total} hexagonos sem municipio apos join espacial do IBGE.")

        df = df.merge(
            df_municipios[["cod_municipio", "nome_municipio"]],
            on="cod_municipio",
            how="left",
        )
        df = df.merge(df_demografia, on="cod_municipio", how="left")
        df["renda_per_capita"] = pd.to_numeric(df["renda_per_capita"], errors="coerce").fillna(0.0)
        df["pop_total"] = pd.to_numeric(df["pop_total"], errors="coerce").fillna(0.0)
        df["pop_18_45"] = pd.to_numeric(df["pop_18_45"], errors="coerce").fillna(0.0)
        df["n_domicilios"] = pd.to_numeric(df["n_domicilios"], errors="coerce").fillna(0.0)
        df["densidade_dom"] = pd.to_numeric(df["densidade_dom"], errors="coerce").fillna(0.0)
        df["nome_municipio"] = df["nome_municipio"].fillna("")
        df["fonte_demografica"] = df["fonte_demografica"].fillna("fallback_padrao")
        return df

    @staticmethod
    def _extrair_codigo_municipio_feature(properties: dict) -> Optional[str]:
        candidatos = [
            properties.get("codarea"),
            properties.get("id"),
            properties.get("CD_MUN"),
            properties.get("CD_MUN7"),
            properties.get("code"),
        ]
        for valor in candidatos:
            codigo = IBGECenso._normalizar_codigo_municipio(valor)
            if codigo:
                return codigo
        return None

    @staticmethod
    def _normalizar_codigo_municipio(valor: object) -> Optional[str]:
        if valor is None:
            return None
        texto = re.sub(r"\D", "", str(valor))
        if len(texto) == 7:
            return texto
        return None

    @staticmethod
    def _detectar_coluna_codigo_municipio(df: pd.DataFrame) -> str:
        melhor_coluna = None
        maior_cardinalidade = -1
        for coluna in df.columns:
            serie = df[coluna].astype(str).str.strip()
            proporcao_codigo = serie.str.fullmatch(r"\d{7}").fillna(False).mean()
            cardinalidade = serie.nunique()
            if proporcao_codigo >= 0.90 and cardinalidade > maior_cardinalidade:
                melhor_coluna = coluna
                maior_cardinalidade = cardinalidade
        if melhor_coluna:
            return melhor_coluna
        raise ValueError("Nao foi possivel detectar a coluna de codigo de municipio na resposta SIDRA.")

    @staticmethod
    def _parse_sidra_dataframe(payload: list[dict]) -> pd.DataFrame:
        if not payload or len(payload) < 2:
            return pd.DataFrame()
        return pd.DataFrame(payload[1:])

    def _baixar_renda_municipios_sidra(self) -> pd.DataFrame:
        url = (
            f"https://apisidra.ibge.gov.br/values/t/{SIDRA_RENDA_MEDIO_MUNICIPIO}"
            f"/n6/all/v/{SIDRA_VAR_RENDA_MEDIO}/p/last"
        )
        resp = requests.get(url, timeout=180)
        resp.raise_for_status()
        df = self._parse_sidra_dataframe(resp.json())
        if df.empty:
            return df

        codigo_col = self._detectar_coluna_codigo_municipio(df)
        resultado = pd.DataFrame(
            {
                "cod_municipio": df[codigo_col].astype(str).str.extract(r"(\d{7})")[0],
                "renda_per_capita": pd.to_numeric(
                    df["V"].astype(str).str.replace(",", ".", regex=False),
                    errors="coerce",
                ).fillna(0.0),
                "fonte_renda": "ibge_censo2022_t10295",
            }
        )
        return resultado.dropna(subset=["cod_municipio"]).drop_duplicates(subset=["cod_municipio"])

    def _baixar_populacao_18_45_municipios_sidra(self) -> pd.DataFrame:
        url = (
            f"https://apisidra.ibge.gov.br/values/t/{SIDRA_POPULACAO_FAIXA}"
            f"/n6/all/v/93/p/last/c287/{','.join(SIDRA_PESOS_IDADE_18_45)}"
        )
        resp = requests.get(url, timeout=180)
        resp.raise_for_status()
        df = self._parse_sidra_dataframe(resp.json())
        if df.empty:
            return df

        codigo_col = self._detectar_coluna_codigo_municipio(df)
        df["cod_municipio"] = df[codigo_col].astype(str).str.extract(r"(\d{7})")[0]
        df["peso_idade"] = df["D4C"].astype(str).map(SIDRA_PESOS_IDADE_18_45).fillna(1.0)
        df["valor"] = pd.to_numeric(
            df["V"].astype(str).str.replace(",", ".", regex=False),
            errors="coerce",
        ).fillna(0.0)
        df["valor_ponderado"] = df["valor"] * df["peso_idade"]
        resultado = (
            df.groupby("cod_municipio", as_index=False)["valor_ponderado"]
            .sum()
            .rename(columns={"valor_ponderado": "pop_18_45"})
        )
        resultado["fonte_populacao"] = "ibge_censo2022_t9514_18_45_proxy"
        return resultado

    @staticmethod
    def _features_padrao() -> dict:
        return {
            "renda_per_capita": 0.0,
            "pop_total":        0.0,
            "pop_18_45":        0.0,
            "n_domicilios":     0.0,
            "densidade_dom":    0.0,
            "area_km2":         0.0,
            "fonte":            "fallback_padrao",
        }
