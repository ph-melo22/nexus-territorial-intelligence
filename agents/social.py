"""Social Agent — queries DATASUS (health) and INEP (education) data."""
import asyncio
import logging

from opentelemetry import trace

from tools.datasus import DatasusClient
from tools.inep import INEPClient
from tools.ibge import IBGEClient

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class SocialAgent:
    """Retrieves and structures social indicators (health + education) for a municipality."""

    def __init__(self) -> None:
        self._datasus = DatasusClient()
        self._inep = INEPClient()
        self._ibge = IBGEClient()

    async def run(
        self,
        codigo_ibge: str,
        consulta: str = "",
    ) -> dict:
        """Return a structured social profile for the municipality.

        Args:
            codigo_ibge: 7-digit IBGE municipality code.
            consulta: Optional natural-language question for context.

        Returns:
            Dictionary with health infrastructure, education metrics, and metadata.
        """
        with tracer.start_as_current_span("agent.social") as span:
            span.set_attribute("agent", "social")
            span.set_attribute("municipio.ibge", codigo_ibge)
            if consulta:
                span.set_attribute("consulta", consulta[:120])

            logger.info(f"SocialAgent: querying ibge={codigo_ibge}")

            # Resolve municipality name for DATASUS dataset search
            try:
                municipio_info = await self._ibge.get_municipio(codigo_ibge)
                nome = municipio_info.get("nome", "")
            except Exception:
                nome = ""

            saude, educacao = await asyncio.gather(
                self._datasus.get_perfil_saude(codigo_ibge, nome),
                self._inep.get_perfil_educacao(codigo_ibge),
                return_exceptions=True,
            )

            return {
                "codigo_ibge": codigo_ibge,
                "municipio": nome,
                "saude": saude if not isinstance(saude, Exception) else {"erro": str(saude)},
                "educacao": educacao if not isinstance(educacao, Exception) else {"erro": str(educacao)},
                "dimensao": "social",
                "consulta": consulta,
                "fontes": ["DATASUS/CNES", "INEP/Censo Escolar", "IBGE SIDRA"],
            }

    async def aclose(self) -> None:
        await self._datasus.aclose()
        await self._inep.aclose()
        await self._ibge.aclose()
