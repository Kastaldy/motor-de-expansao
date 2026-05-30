"""
jobs/pipelines/poi_enrichment.py — Enriquecimento de POIs por hexágono

Fontes gratuitas:
  1. OpenStreetMap via Overpass API — academias e fitness
  2. Google Places API (free tier US$3.250/mês) — vitalidade comercial
"""

import json
import time
from pathlib import Path

import h3
import numpy as np
import requests
import structlog
from sklearn.neighbors import BallTree

from motor_expansao.config import settings

log = structlog.get_logger()
OSM_CACHE_DIR = Path("data/osm_cache")
OSM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
OSM_CACHE_VERSION = "v2"

OSM_FITNESS_TAGS = [
    '"leisure"="fitness_centre"',
    '"sport"="fitness"',
    '"sport"="gym"',
    '"amenity"="gym"',
]

OSM_OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

GOOGLE_VITALIDADE_TIPOS = {
    "supermarket":   3.0,
    "gym":           2.0,
    "pharmacy":      2.0,
    "restaurant":    1.5,
    "shopping_mall": 3.5,
}


class POIEnricher:
    def __init__(self):
        self._google_key = settings.GOOGLE_MAPS_API_KEY
        self._cache_academias: list[dict] | None = None

    def _post_overpass(self, query: str, timeout: int, contexto: str) -> requests.Response:
        ultimo_erro = None
        headers = {"User-Agent": "motor-expansao-ultra-academia/1.0"}

        for endpoint in OSM_OVERPASS_ENDPOINTS:
            for tentativa in range(3):
                try:
                    resp = requests.post(
                        endpoint,
                        data={"data": query},
                        timeout=timeout,
                        headers=headers,
                    )
                    resp.raise_for_status()
                    time.sleep(1.1)
                    return resp
                except Exception as e:
                    ultimo_erro = e
                    if tentativa < 2:
                        wait = min(20, 4 * (2 ** tentativa))
                        log.warning(
                            "osm_retry",
                            contexto=contexto,
                            endpoint=endpoint,
                            tentativa=tentativa + 1,
                            aguardando_s=wait,
                            erro=str(e),
                        )
                        time.sleep(wait)
                    else:
                        log.warning(
                            "osm_endpoint_erro",
                            contexto=contexto,
                            endpoint=endpoint,
                            erro=str(e),
                        )

        raise RuntimeError(f"Falha ao consultar Overpass ({contexto}): {ultimo_erro}")

    @staticmethod
    def _normalizar_bbox(lat_min: float, lat_max: float, lng_min: float, lng_max: float) -> tuple[float, float, float, float]:
        return (
            min(lat_min, lat_max),
            max(lat_min, lat_max),
            min(lng_min, lng_max),
            max(lng_min, lng_max),
        )

    @staticmethod
    def _bbox_cache_path(lat_min: float, lat_max: float, lng_min: float, lng_max: float) -> Path:
        chave = f"{lat_min:.4f}_{lat_max:.4f}_{lng_min:.4f}_{lng_max:.4f}"
        chave = chave.replace("-", "m").replace(".", "_")
        return OSM_CACHE_DIR / f"{OSM_CACHE_VERSION}_{chave}.json"

    def buscar_academias_bbox(
        self,
        lat_min: float,
        lat_max: float,
        lng_min: float,
        lng_max: float,
        contexto: str = "bbox",
    ) -> list[dict]:
        lat_min, lat_max, lng_min, lng_max = self._normalizar_bbox(lat_min, lat_max, lng_min, lng_max)
        cache_path = self._bbox_cache_path(lat_min, lat_max, lng_min, lng_max)
        if cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

        filtros = "\n  ".join([
            f"node[{tag}]({lat_min},{lng_min},{lat_max},{lng_max});"
            for tag in OSM_FITNESS_TAGS
        ])
        query = f"[out:json][timeout:40];\n(\n  {filtros}\n);\nout body;\n"
        resp = self._post_overpass(query, timeout=45, contexto=contexto)
        elementos = resp.json().get("elements", [])
        academias = [
            {
                "osm_id": el.get("id"),
                "nome":   el.get("tags", {}).get("name", "Academia sem nome"),
                "lat":    el.get("lat"),
                "lng":    el.get("lon"),
                "tipo":   el.get("tags", {}).get("leisure") or el.get("tags", {}).get("sport"),
                "fonte":  "osm",
            }
            for el in elementos
        ]
        cache_path.write_text(json.dumps(academias, ensure_ascii=False), encoding="utf-8")
        return academias

    def buscar_academias_osm(self, lat: float, lng: float, raio_metros: int = 1500) -> list[dict]:
        filtros = "\n  ".join([
            f"node[{tag}](around:{raio_metros},{lat},{lng});"
            for tag in OSM_FITNESS_TAGS
        ])
        query = f"[out:json][timeout:30];\n(\n  {filtros}\n);\nout body;\n"
        try:
            resp = self._post_overpass(query, timeout=35, contexto="raio")
            elementos = resp.json().get("elements", [])
            return [
                {
                    "osm_id": el.get("id"),
                    "nome":   el.get("tags", {}).get("name", "Academia sem nome"),
                    "lat":    el.get("lat"),
                    "lng":    el.get("lon"),
                    "tipo":   el.get("tags", {}).get("leisure") or el.get("tags", {}).get("sport"),
                    "fonte":  "osm",
                }
                for el in elementos
            ]
        except Exception as e:
            log.warning("osm_erro", erro=str(e))
            return []

    def buscar_academias_hex_osm(self, hex_id: str, raio_metros: int = 1500) -> list[dict]:
        lat, lng = h3.cell_to_latlng(hex_id)
        return self.buscar_academias_osm(lat, lng, raio_metros)

    def carregar_academias_cidade(
        self,
        lat_min: float, lat_max: float,
        lng_min: float, lng_max: float,
    ) -> list[dict]:
        """
        Carrega TODAS as academias dentro de um bounding box em 1 query.
        Usar no início do pipeline para pré-carregar toda a cidade de uma vez.
        Armazena resultado em self._cache_academias para uso por contar_academias_proximas().
        """
        try:
            self._cache_academias = self.buscar_academias_bbox(
                lat_min=lat_min,
                lat_max=lat_max,
                lng_min=lng_min,
                lng_max=lng_max,
                contexto="bbox",
            )
            log.info("academias_cidade_carregadas", total=len(self._cache_academias))
            return self._cache_academias
        except Exception as e:
            self._cache_academias = None
            log.error(
                "osm_bbox_falha_bloqueante",
                lat_min=lat_min,
                lat_max=lat_max,
                lng_min=lng_min,
                lng_max=lng_max,
                erro=str(e),
            )
            raise

    def contar_academias_proximas(self, lat: float, lng: float, raio_metros: int = 1500) -> int:
        """
        Conta academias próximas usando o cache carregado por carregar_academias_cidade().
        Operação local — sem chamada de rede.
        Fallback para query individual se cache não foi carregado.
        """
        cache = getattr(self, '_cache_academias', None)
        if cache is None:
            return len(self.buscar_academias_osm(lat, lng, raio_metros))
        raio_graus = raio_metros / 111_000
        return sum(
            1 for a in cache
            if a["lat"] and a["lng"]
            and abs(a["lat"] - lat) <= raio_graus
            and abs(a["lng"] - lng) <= raio_graus
        )

    def buscar_academias_em_janelas(
        self,
        df_hex,
        lat_step: float = 1.0,
        lng_step: float = 1.0,
        margem: float = 0.03,
        contexto: str = "uf",
    ) -> list[dict]:
        if df_hex.empty:
            return []

        df = df_hex[["lat", "lng"]].copy()
        df["lat_bucket"] = np.floor(df["lat"] / lat_step).astype(int)
        df["lng_bucket"] = np.floor(df["lng"] / lng_step).astype(int)

        academias_por_id: dict[object, dict] = {}
        grupos = df.groupby(["lat_bucket", "lng_bucket"], sort=True)

        for idx, (_, grupo) in enumerate(grupos, start=1):
            lat_min = float(grupo["lat"].min() - margem)
            lat_max = float(grupo["lat"].max() + margem)
            lng_min = float(grupo["lng"].min() - margem)
            lng_max = float(grupo["lng"].max() + margem)
            academias = self.buscar_academias_bbox_adaptativo(
                lat_min=lat_min,
                lat_max=lat_max,
                lng_min=lng_min,
                lng_max=lng_max,
                contexto=f"{contexto}_janela_{idx}",
            )
            for academia in academias:
                osm_id = academia.get("osm_id")
                if osm_id is None:
                    continue
                academias_por_id[osm_id] = academia
            log.info(
                "osm_janela_processada",
                contexto=contexto,
                janela=idx,
                hexagonos=len(grupo),
                academias=len(academias),
                acumulado=len(academias_por_id),
            )

        return list(academias_por_id.values())

    def buscar_academias_bbox_adaptativo(
        self,
        lat_min: float,
        lat_max: float,
        lng_min: float,
        lng_max: float,
        contexto: str,
        profundidade: int = 0,
        max_profundidade: int = 5,
        min_span: float = 0.05,
    ) -> list[dict]:
        try:
            return self.buscar_academias_bbox(
                lat_min=lat_min,
                lat_max=lat_max,
                lng_min=lng_min,
                lng_max=lng_max,
                contexto=contexto,
            )
        except Exception:
            lat_span = abs(lat_max - lat_min)
            lng_span = abs(lng_max - lng_min)
            if profundidade >= max_profundidade or (lat_span <= min_span and lng_span <= min_span):
                raise

            lat_mid = (lat_min + lat_max) / 2
            lng_mid = (lng_min + lng_max) / 2
            log.warning(
                "osm_bbox_split",
                contexto=contexto,
                profundidade=profundidade,
                lat_span=round(lat_span, 4),
                lng_span=round(lng_span, 4),
            )

            sub_bboxes = [
                (lat_min, lat_mid, lng_min, lng_mid),
                (lat_min, lat_mid, lng_mid, lng_max),
                (lat_mid, lat_max, lng_min, lng_mid),
                (lat_mid, lat_max, lng_mid, lng_max),
            ]

            academias_por_id: dict[object, dict] = {}
            for idx, (sub_lat_min, sub_lat_max, sub_lng_min, sub_lng_max) in enumerate(sub_bboxes, start=1):
                academias = self.buscar_academias_bbox_adaptativo(
                    lat_min=sub_lat_min,
                    lat_max=sub_lat_max,
                    lng_min=sub_lng_min,
                    lng_max=sub_lng_max,
                    contexto=f"{contexto}_sub{idx}",
                    profundidade=profundidade + 1,
                    max_profundidade=max_profundidade,
                    min_span=min_span,
                )
                for academia in academias:
                    osm_id = academia.get("osm_id")
                    if osm_id is None:
                        continue
                    academias_por_id[osm_id] = academia

            return list(academias_por_id.values())

    def contar_academias_em_lote(self, df_hex, academias: list[dict], raio_metros: int = 1500, chunk_size: int = 50_000):
        if df_hex.empty:
            return np.array([], dtype=int)
        if not academias:
            return np.zeros(len(df_hex), dtype=int)

        coords_poi = np.array(
            [
                [a["lat"], a["lng"]]
                for a in academias
                if a.get("lat") is not None and a.get("lng") is not None
            ],
            dtype=float,
        )
        if len(coords_poi) == 0:
            return np.zeros(len(df_hex), dtype=int)

        tree = BallTree(np.radians(coords_poi), metric="haversine")
        raio = raio_metros / 6_371_000.0
        contagens = np.zeros(len(df_hex), dtype=int)
        coords_hex = np.radians(df_hex[["lat", "lng"]].to_numpy(dtype=float))

        for inicio in range(0, len(coords_hex), chunk_size):
            fim = min(inicio + chunk_size, len(coords_hex))
            contagens[inicio:fim] = tree.query_radius(
                coords_hex[inicio:fim],
                r=raio,
                count_only=True,
            )

        return contagens

    def buscar_pois_google(self, lat: float, lng: float, raio_metros: int = 1500, tipo: str = "gym") -> list[dict]:
        if not self._google_key:
            return []
        try:
            resp = requests.get(
                "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
                params={"location": f"{lat},{lng}", "radius": raio_metros, "type": tipo, "key": self._google_key},
                timeout=15,
            )
            data = resp.json()
            if data.get("status") not in ("OK", "ZERO_RESULTS"):
                return []
            return [
                {
                    "place_id":     p.get("place_id"),
                    "nome":         p.get("name"),
                    "lat":          p.get("geometry", {}).get("location", {}).get("lat"),
                    "lng":          p.get("geometry", {}).get("location", {}).get("lng"),
                    "tipo":         tipo,
                    "rating":       p.get("rating", 0),
                    "n_avaliacoes": p.get("user_ratings_total", 0),
                    "fonte":        "google_places",
                }
                for p in data.get("results", [])
            ]
        except Exception as e:
            log.warning("google_places_erro", tipo=tipo, erro=str(e))
            return []

    def score_vitalidade_comercial(self, lat: float, lng: float, raio_metros: int = 1500) -> float:
        if not self._google_key:
            return 50.0
        total = 0.0
        for tipo, peso in GOOGLE_VITALIDADE_TIPOS.items():
            n = min(len(self.buscar_pois_google(lat, lng, raio_metros, tipo)), 10)
            total += n * peso
            time.sleep(0.3)
        return round(min((total / 50) * 100, 100), 2)

    def features_para_hex(self, hex_id: str) -> dict:
        lat, lng = h3.cell_to_latlng(hex_id)
        academias = self.buscar_academias_osm(lat, lng)
        vitalidade = self.score_vitalidade_comercial(lat, lng) if self._google_key else 50.0
        return {
            "n_academias_osm":  len(academias),
            "academias_osm":    academias,
            "score_vitalidade": vitalidade,
        }
