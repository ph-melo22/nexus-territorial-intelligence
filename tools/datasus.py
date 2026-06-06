"""DATASUS / Ministério da Saúde open data client.

Sources:
  - API Dados Abertos Saúde (CNES): https://apidadosabertos.saude.gov.br/cnes/estabelecimentos
  - OpenDATASUS CKAN: https://opendatasus.saude.gov.br/api/3/action

Note: The CNES REST API returns up to 20 establishments per request.
For full municipality counts, the DATASUS TABNET or direct file downloads
are required. This client uses the available REST endpoints.
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

# CNES establishment type codes → human-readable labels
_TIPO_UNIDADE: dict[str, str] = {
    "1": "Posto de Saúde",
    "2": "Centro de Saúde/UBS",
    "4": "Policlínica",
    "5": "Hospital Geral",
    "7": "Hospital Especializado",
    "15": "Unidade Mista",
    "20": "Pronto-Socorro Especializado",
    "21": "Hospital-Dia Isolado",
    "22": "Consultório Isolado",
    "32": "Unidade Móvel Terrestre",
    "36": "Clínica/Centro de Especialidade",
    "39": "Unidade de Vigilância em Saúde",
    "61": "Centro de Parto Normal",
    "69": "Centro de Hemoterapia",
    "71": "CAPS (Atenção Psicossocial)",
    "72": "UADT (Diagnose e Terapia)",
    "73": "URAP",
    "76": "Central de Regulação",
    "77": "Clínica de Reabilitação",
    "78": "Unidade de Saúde da Família",
    "79": "Oficina Ortopédica",
    "81": "Laboratório de Saúde Pública",
    "85": "CECCO",
}


class DatasusClient:
    def __init__(self) -> None:
        self._saude = httpx.AsyncClient(
            base_url=settings.SAUDE_BASE_URL,
            timeout=settings.HTTP_TIMEOUT,
            headers={"Accept": "application/json"},
        )
        self._ckan = httpx.AsyncClient(
            base_url=settings.OPENDATASUS_CKAN_URL,
            timeout=settings.HTTP_TIMEOUT,
            headers={"Accept": "application/json"},
        )

    async def aclose(self) -> None:
        await self._saude.aclose()
        await self._ckan.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def _get_saude(self, path: str, **params) -> Any:
        params = {k: v for k, v in params.items() if v is not None}
        resp = await self._saude.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get_ckan(self, action: str, **params) -> Any:
        params = {k: v for k, v in params.items() if v is not None}
        resp = await self._ckan.get(f"/{action}", params=params)
        resp.raise_for_status()
        return resp.json()

    # ── CNES — Estabelecimentos de Saúde ─────────────────────────────────────

    async def get_estabelecimentos(self, ibge_code: str) -> dict:
        """CNES health establishments for a municipality.

        The public API returns up to ~20 records per query (API limitation).
        Paginates across 3 pages to maximise coverage.
        """
        with tracer.start_as_current_span("datasus.get_estabelecimentos") as span:
            span.set_attribute("ibge.code", ibge_code)
            try:
                # Fetch up to 3 pages of 100 to maximise coverage within API limits
                pages = await asyncio.gather(
                    *[
                        self._get_saude(
                            "/cnes/estabelecimentos",
                            codigoMunicipio=ibge_code,
                            limit=100,
                            offset=i * 100,
                        )
                        for i in range(3)
                    ],
                    return_exceptions=True,
                )

                registros: list[dict] = []
                for page in pages:
                    if isinstance(page, Exception):
                        continue
                    batch = page.get("estabelecimentos", []) if isinstance(page, dict) else []
                    registros.extend(batch)

                # Count by type
                tipos: dict[str, int] = {}
                sus_count = 0
                hospitais = 0
                for est in registros:
                    code_tipo = str(est.get("codigo_tipo_unidade", "?"))
                    label = _TIPO_UNIDADE.get(code_tipo, f"Tipo {code_tipo}")
                    tipos[label] = tipos.get(label, 0) + 1
                    sus_val = est.get("estabelecimento_faz_atendimento_ambulatorial_sus", "")
                    if str(sus_val).upper() in ("SIM", "S", "1", "TRUE"):
                        sus_count += 1
                    hosp_val = est.get("estabelecimento_possui_atendimento_hospitalar", 0)
                    if hosp_val and str(hosp_val).upper() not in ("0", "NAO", "N", "FALSE"):
                        hospitais += 1

                return {
                    "total_estabelecimentos_amostra": len(registros),
                    "com_atendimento_sus": sus_count,
                    "com_internacao_hospitalar": hospitais,
                    "por_tipo": tipos,
                    "nota": (
                        "Amostra retornada pela API REST do CNES. "
                        "Para totais completos, consulte cnes.datasus.gov.br."
                    ),
                    "fonte": "CNES — Ministério da Saúde",
                    "url": "https://cnes.datasus.gov.br/",
                }
            except Exception as e:
                logger.warning(f"CNES establishments unavailable: {e}")
                return {
                    "total_estabelecimentos_amostra": None,
                    "erro": str(e),
                    "fonte": "CNES",
                }

    # ── OpenDATASUS CKAN — dataset discovery ──────────────────────────────────

    async def search_datasets(self, municipio_nome: str, rows: int = 5) -> list[dict]:
        """Discover health datasets for a municipality in the OpenDATASUS CKAN catalog."""
        with tracer.start_as_current_span("datasus.search_datasets"):
            try:
                result = await self._get_ckan(
                    "package_search",
                    q=municipio_nome,
                    rows=rows,
                    sort="score desc",
                )
                pkgs = result.get("result", {}).get("results", [])
                return [
                    {
                        "id": p.get("id"),
                        "titulo": p.get("title"),
                        "descricao": (p.get("notes") or "")[:200],
                        "url": f"https://opendatasus.saude.gov.br/dataset/{p.get('name')}",
                    }
                    for p in pkgs
                ]
            except Exception as e:
                logger.warning(f"OpenDATASUS CKAN unavailable: {e}")
                return []

    # ── Composite ─────────────────────────────────────────────────────────────

    async def get_perfil_saude(self, ibge_code: str, municipio_nome: str = "") -> dict:
        """Health infrastructure profile for the municipality."""
        with tracer.start_as_current_span("datasus.get_perfil_saude") as span:
            span.set_attribute("ibge.code", ibge_code)
            estabelecimentos, datasets = await asyncio.gather(
                self.get_estabelecimentos(ibge_code),
                self.search_datasets(municipio_nome or ibge_code),
                return_exceptions=True,
            )
            return {
                "codigo_ibge": ibge_code,
                "estabelecimentos": (
                    estabelecimentos
                    if not isinstance(estabelecimentos, Exception)
                    else {"erro": str(estabelecimentos)}
                ),
                "datasets_disponíveis": (
                    datasets if not isinstance(datasets, Exception) else []
                ),
                "fonte": "DATASUS / Ministério da Saúde",
                "url_cnes": "https://cnes.datasus.gov.br/",
                "url_opendatasus": "https://opendatasus.saude.gov.br/",
            }
