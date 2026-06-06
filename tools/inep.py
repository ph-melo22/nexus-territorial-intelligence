"""INEP education data client.

INEP does not expose a public REST API. Open data is published as downloadable
microdata files (XLSX/ZIP). This client:
  1. Provides structured metadata with direct links to IDEB and Censo Escolar files.
  2. Fetches IBGE SIDRA — Pesquisa Nacional de Saúde do Escolar (PNSE) where available.
  3. Enables the Router Agent to guide users toward official download sources with the
     correct municipality filter (CO_MUNICIPIO = 6-digit IBGE code).

References:
  https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos
  https://inepdata.inep.gov.br/
"""
import logging
from typing import Any

import httpx
from opentelemetry import trace
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# IBGE SIDRA — Pesquisa Nacional de Saúde do Escolar (table AA / PNSE)
# This is the only municipal-level education table available via SIDRA API.
_SIDRA_PNSE_BASE = f"{settings.IBGE_BASE_URL}/v3/agregados/AA"


class INEPClient:
    def __init__(self) -> None:
        self._ibge = httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT,
            headers={"Accept": "application/json"},
        )

    async def aclose(self) -> None:
        await self._ibge.aclose()

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def _get(self, url: str, **params) -> Any:
        params = {k: v for k, v in params.items() if v is not None}
        resp = await self._ibge.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    # ── IDEB metadata ─────────────────────────────────────────────────────────

    async def get_ideb_info(self, ibge_code: str) -> dict:
        """Returns IDEB metadata and direct download links for the municipality."""
        with tracer.start_as_current_span("inep.get_ideb_info"):
            ibge_6 = ibge_code[:6]
            return {
                "codigo_ibge_7": ibge_code,
                "codigo_ibge_6": ibge_6,
                "filtro_planilha": f"Filtrar coluna CO_MUNICIPIO = {ibge_6}",
                "arquivos": [
                    {
                        "descricao": "IDEB — Anos Iniciais do Ensino Fundamental (2023)",
                        "url": (
                            "https://download.inep.gov.br/educacao_basica/portal_ideb"
                            "/planilhas_para_download/2023"
                            "/divulgacao_anos_iniciais_municipios_2023.xlsx"
                        ),
                    },
                    {
                        "descricao": "IDEB — Anos Finais do Ensino Fundamental (2023)",
                        "url": (
                            "https://download.inep.gov.br/educacao_basica/portal_ideb"
                            "/planilhas_para_download/2023"
                            "/divulgacao_anos_finais_municipios_2023.xlsx"
                        ),
                    },
                    {
                        "descricao": "IDEB — Ensino Médio (2023)",
                        "url": (
                            "https://download.inep.gov.br/educacao_basica/portal_ideb"
                            "/planilhas_para_download/2023"
                            "/divulgacao_ensino_medio_municipios_2023.xlsx"
                        ),
                    },
                    {
                        "descricao": "Microdados Censo Escolar 2023",
                        "url": (
                            "https://www.gov.br/inep/pt-br/acesso-a-informacao"
                            "/dados-abertos/microdados/censo-escolar"
                        ),
                    },
                ],
                "nota": (
                    "O INEP não oferece API REST. Dados disponíveis como arquivos XLSX/ZIP. "
                    "Para consultar este município, filtre as planilhas pela coluna CO_MUNICIPIO."
                ),
                "fonte": "INEP — Dados Abertos",
                "url_portal": "https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos",
            }

    # ── PNSE via IBGE SIDRA ───────────────────────────────────────────────────

    async def get_pnse_variables(self) -> list[dict]:
        """List available variables in SIDRA's PNSE aggregate (table AA)."""
        with tracer.start_as_current_span("inep.get_pnse_variables"):
            try:
                data = await self._get(f"{_SIDRA_PNSE_BASE}/variaveis")
                return [
                    {"id": v.get("id"), "nome": v.get("nome"), "unidade": v.get("unidade")}
                    for v in (data if isinstance(data, list) else [])
                ][:10]
            except Exception as e:
                logger.warning(f"PNSE variables unavailable: {e}")
                return []

    # ── Composite ─────────────────────────────────────────────────────────────

    async def get_perfil_educacao(self, ibge_code: str) -> dict:
        """Full education profile for the municipality."""
        with tracer.start_as_current_span("inep.get_perfil_educacao") as span:
            span.set_attribute("ibge.code", ibge_code)
            import asyncio
            ideb_info, pnse_vars = await asyncio.gather(
                self.get_ideb_info(ibge_code),
                self.get_pnse_variables(),
                return_exceptions=True,
            )
            return {
                "codigo_ibge": ibge_code,
                "ideb": (
                    ideb_info
                    if not isinstance(ideb_info, Exception)
                    else {"erro": str(ideb_info)}
                ),
                "pnse_variaveis_disponiveis": (
                    pnse_vars if not isinstance(pnse_vars, Exception) else []
                ),
                "fonte": "INEP — Dados Abertos / IBGE SIDRA (PNSE)",
                "url_inep": "https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos",
            }
