"""Territorial Agent — queries IBGE for demographic and geographic data."""
import logging

from opentelemetry import trace

from tools.ibge import IBGEClient

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class TerritorialAgent:
    """Retrieves and structures territorial/demographic indicators for a municipality."""

    def __init__(self) -> None:
        self._client = IBGEClient()

    async def run(
        self,
        codigo_ibge: str,
        consulta: str = "",
    ) -> dict:
        """Return a structured territorial profile for the municipality.

        Args:
            codigo_ibge: 7-digit IBGE municipality code.
            consulta: Optional natural-language question for context.

        Returns:
            Dictionary with municipality metadata, population, PIB, and related indicators.
        """
        with tracer.start_as_current_span("agent.territorial") as span:
            span.set_attribute("agent", "territorial")
            span.set_attribute("municipio.ibge", codigo_ibge)
            if consulta:
                span.set_attribute("consulta", consulta[:120])

            logger.info(f"TerritorialAgent: querying ibge={codigo_ibge}")
            perfil = await self._client.get_perfil_completo(codigo_ibge)
            perfil["dimensao"] = "territorial"
            perfil["consulta"] = consulta
            return perfil

    async def aclose(self) -> None:
        await self._client.aclose()
