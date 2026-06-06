"""Fiscal Agent — queries Portal da Transparência and structures fiscal data."""
import logging

from opentelemetry import trace

from tools.transparencia import TransparenciaClient

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class FiscalAgent:
    """Retrieves and structures fiscal/budgetary indicators for a municipality."""

    def __init__(self) -> None:
        self._client = TransparenciaClient()

    async def run(
        self,
        codigo_ibge: str,
        ano: int = 2024,
        consulta: str = "",
    ) -> dict:
        """Return a structured fiscal profile for the municipality.

        Args:
            codigo_ibge: 7-digit IBGE municipality code.
            ano: Reference year.
            consulta: Optional natural-language question for context.

        Returns:
            Dictionary with Bolsa Família, federal transfers, grants, and metadata.
        """
        with tracer.start_as_current_span("agent.fiscal") as span:
            span.set_attribute("agent", "fiscal")
            span.set_attribute("municipio.ibge", codigo_ibge)
            span.set_attribute("ano", ano)
            if consulta:
                span.set_attribute("consulta", consulta[:120])

            logger.info(f"FiscalAgent: querying ibge={codigo_ibge} ano={ano}")
            perfil = await self._client.get_perfil_fiscal(codigo_ibge, ano)
            perfil["dimensao"] = "fiscal"
            perfil["consulta"] = consulta
            return perfil

    async def aclose(self) -> None:
        await self._client.aclose()
