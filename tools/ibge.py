"""IBGE API client — localidades, SIDRA (PNAD/Censo), PIB, territory metadata.

All endpoints are public and require no authentication.
Docs: https://servicodados.ibge.gov.br/api/docs
"""
import asyncio
import logging
from typing import Any

import httpx
from opentelemetry import trace
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# SIDRA aggregate / variable references used in this client
_SIDRA = {
    # Table 4714 — Censo 2022: Pessoas residentes (var 93)
    "populacao_censo": ("4714", "2022", "93"),
    # Table 6408 — Estimativas de população (var 2093), annual
    "populacao_estimada": ("6408", "2024", "2093"),
    # Table 5938 — PIB dos Municípios (var 37 = PIB per capita R$)
    "pib_per_capita": ("5938", "2021", "37"),
}


class IBGEClient:
    def __init__(self) -> None:
        self._http = httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT,
            headers={"Accept": "application/json"},
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    # ── Core helpers ──────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def _get(self, url: str, **params) -> Any:
        resp = await self._http.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    async def _sidra(self, table: str, period: str, variable: str, ibge_code: str) -> Any:
        url = (
            f"{settings.IBGE_BASE_URL}/v3/agregados/{table}"
            f"/periodos/{period}/variaveis/{variable}"
        )
        return await self._get(url, localidades=f"N6[{ibge_code}]")

    def _sidra_value(self, data: list, fallback=None) -> Any:
        try:
            return data[0]["resultados"][0]["series"][0]["serie"]
        except (IndexError, KeyError, TypeError):
            return fallback

    # ── Public methods ────────────────────────────────────────────────────────

    async def get_municipio(self, ibge_code: str) -> dict:
        """Basic municipality metadata (name, state, region, area)."""
        with tracer.start_as_current_span("ibge.get_municipio") as span:
            span.set_attribute("ibge.code", ibge_code)
            url = f"{settings.IBGE_BASE_URL}/v1/localidades/municipios/{ibge_code}"
            data = await self._get(url)
            return {
                "id": data.get("id"),
                "nome": data.get("nome"),
                "estado": data.get("microrregiao", {}).get("mesorregiao", {}).get("UF", {}).get("sigla"),
                "estado_nome": data.get("microrregiao", {}).get("mesorregiao", {}).get("UF", {}).get("nome"),
                "regiao": data.get("microrregiao", {}).get("mesorregiao", {}).get("UF", {}).get("regiao", {}).get("sigla"),
                "microrregiao": data.get("microrregiao", {}).get("nome"),
                "mesorregiao": data.get("microrregiao", {}).get("mesorregiao", {}).get("nome"),
            }

    async def get_populacao(self, ibge_code: str) -> dict:
        """Population data: Censo 2022 + latest annual estimate."""
        with tracer.start_as_current_span("ibge.get_populacao"):
            censo_task = self._sidra(*_SIDRA["populacao_censo"], ibge_code)
            estimada_task = self._sidra(*_SIDRA["populacao_estimada"], ibge_code)
            censo, estimada = await asyncio.gather(censo_task, estimada_task, return_exceptions=True)

            censo_val = self._sidra_value(censo) if not isinstance(censo, Exception) else None
            estimada_val = self._sidra_value(estimada) if not isinstance(estimada, Exception) else None

            # extract the most recent year value from SIDRA series dict
            def latest(series_dict):
                if not series_dict or not isinstance(series_dict, dict):
                    return None
                return series_dict.get(max(series_dict.keys()))

            return {
                "populacao_censo_2022": latest(censo_val),
                "populacao_estimada_2024": latest(estimada_val),
            }

    async def get_pib(self, ibge_code: str) -> dict:
        """PIB per capita — last available year (2021).

        SIDRA table 5938 stores values in 'Mil Reais' with 3 implied decimal
        places. Per capita (var 37): raw_value / 1000 → R$ actual per capita.
        """
        with tracer.start_as_current_span("ibge.get_pib"):
            per_capita_data = await self._sidra(*_SIDRA["pib_per_capita"], ibge_code)

            series = self._sidra_value(per_capita_data)
            raw = None
            if series and isinstance(series, dict):
                raw = series.get(max(series.keys()))

            per_capita_reais: float | None = None
            if raw is not None:
                try:
                    per_capita_reais = round(float(raw) / 1000, 2)
                except (ValueError, TypeError):
                    pass

            return {
                "pib_per_capita_reais": per_capita_reais,
                "ano_referencia": "2021",
                "nota_unidade": "Fonte SIDRA tabela 5938 var 37 (Mil Reais ÷ 1000)",
            }

    async def get_municipios_estado(self, uf_sigla: str) -> list[dict]:
        """All municipalities for a state (UF sigla e.g. 'SP')."""
        with tracer.start_as_current_span("ibge.get_municipios_estado"):
            url = f"{settings.IBGE_BASE_URL}/v1/localidades/estados/{uf_sigla}/municipios"
            data = await self._get(url)
            return [{"id": str(m["id"]), "nome": m["nome"]} for m in data]

    async def get_perfil_completo(self, ibge_code: str) -> dict:
        """Fetch all territorial/demographic indicators concurrently."""
        with tracer.start_as_current_span("ibge.get_perfil_completo") as span:
            span.set_attribute("ibge.code", ibge_code)
            municipio, populacao, pib = await asyncio.gather(
                self.get_municipio(ibge_code),
                self.get_populacao(ibge_code),
                self.get_pib(ibge_code),
                return_exceptions=True,
            )
            return {
                "codigo_ibge": ibge_code,
                "municipio": municipio if not isinstance(municipio, Exception) else {"erro": str(municipio)},
                "populacao": populacao if not isinstance(populacao, Exception) else {"erro": str(populacao)},
                "pib": pib if not isinstance(pib, Exception) else {"erro": str(pib)},
                "fonte": "IBGE — Localidades + SIDRA",
                "url_api": "https://servicodados.ibge.gov.br/api/docs",
            }
