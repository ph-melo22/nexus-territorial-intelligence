"""Router Agent — Azure AI Agent Service orchestrator.

Uses azure-ai-projects to create an Azure AI Agent that receives natural-language
questions, plans which NEXUS tools to invoke, and returns a synthesized answer.

The four NEXUS tools are registered as Azure AI FunctionTool definitions that
call back to the running FastAPI endpoints, so the agent can invoke them
autonomously via the Azure AI Agent runtime's function-calling loop.
"""
import asyncio
import json
import logging
from typing import AsyncIterator

from opentelemetry import trace

from config import settings
from agents.fiscal import FiscalAgent
from agents.territorial import TerritorialAgent
from agents.social import SocialAgent

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

_SYSTEM_PROMPT = """You are NEXUS, an AI analyst specialising in Brazilian public sector data.

Your role is to answer questions from government decision-makers by crossing three
dimensions of municipal data:

• Fiscal     — federal transfers, Bolsa Família, procurement (Portal da Transparência)
• Territorial — demographics, PIB, geography (IBGE)
• Social     — health infrastructure, education metrics (DATASUS + INEP)

Guidelines:
1. Always identify the municipality and obtain its 7-digit IBGE code before querying.
2. Use only the tools available; never invent data.
3. Combine data from multiple dimensions when the question spans them.
4. Present numbers with units (R$, %, inhabitants, etc.) and cite the source.
5. Highlight disparities, risks, or opportunities grounded in the data.
6. Reply in the same language as the question (Portuguese or English).
7. Be concise: lead with the direct answer, then supporting evidence.
"""


class RouterAgent:
    """High-level orchestrator that delegates to fiscal, territorial, and social agents."""

    def __init__(self) -> None:
        self._fiscal = FiscalAgent()
        self._territorial = TerritorialAgent()
        self._social = SocialAgent()
        self._azure_agent_id: str | None = None

    # ── Azure AI Agent Service integration ────────────────────────────────────

    def _build_tool_definitions(self) -> list[dict]:
        """Return OpenAI-compatible function definitions for the four NEXUS tools."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "buscar_fiscal",
                    "description": (
                        "Search fiscal/budgetary data for a Brazilian municipality: "
                        "Bolsa Família beneficiaries, federal transfers, grants."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "codigo_ibge": {"type": "string", "description": "7-digit IBGE municipality code"},
                            "ano": {"type": "integer", "description": "Reference year (default 2024)"},
                            "consulta": {"type": "string", "description": "Specific sub-question"},
                        },
                        "required": ["codigo_ibge"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "buscar_territorial",
                    "description": (
                        "Search territorial/demographic data for a Brazilian municipality: "
                        "population, area, PIB, geographic profile."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "codigo_ibge": {"type": "string", "description": "7-digit IBGE municipality code"},
                            "consulta": {"type": "string", "description": "Specific sub-question"},
                        },
                        "required": ["codigo_ibge"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "buscar_social",
                    "description": (
                        "Search social data for a Brazilian municipality: "
                        "health establishments, professionals (DATASUS/CNES), "
                        "school enrollments and teachers (INEP/Censo Escolar)."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "codigo_ibge": {"type": "string", "description": "7-digit IBGE municipality code"},
                            "consulta": {"type": "string", "description": "Specific sub-question"},
                        },
                        "required": ["codigo_ibge"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "cruzar_dados",
                    "description": (
                        "Cross-reference fiscal, territorial, and social data for one or more "
                        "Brazilian municipalities. Returns a comparative multi-dimensional analysis."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "codigos_ibge": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of 7-digit IBGE codes",
                            },
                            "dimensoes": {
                                "type": "array",
                                "items": {"type": "string", "enum": ["fiscal", "territorial", "social"]},
                                "description": "Dimensions to cross (default: all three)",
                            },
                            "consulta": {"type": "string", "description": "Question or hypothesis to investigate"},
                        },
                        "required": ["codigos_ibge", "consulta"],
                    },
                },
            },
        ]

    async def _execute_tool_call(self, name: str, arguments: dict) -> str:
        """Execute a tool call dispatched by the Azure AI Agent."""
        with tracer.start_as_current_span(f"router.tool_call.{name}") as span:
            span.set_attribute("tool.name", name)
            try:
                if name == "buscar_fiscal":
                    result = await self._fiscal.run(**arguments)
                elif name == "buscar_territorial":
                    result = await self._territorial.run(**arguments)
                elif name == "buscar_social":
                    result = await self._social.run(**arguments)
                elif name == "cruzar_dados":
                    result = await self._cruzar_dados(**arguments)
                else:
                    result = {"erro": f"Unknown tool: {name}"}
                return json.dumps(result, ensure_ascii=False, default=str)
            except Exception as e:
                logger.error(f"Tool call {name} failed: {e}")
                return json.dumps({"erro": str(e)})

    async def _cruzar_dados(
        self,
        codigos_ibge: list[str],
        dimensoes: list[str] | None = None,
        consulta: str = "",
    ) -> dict:
        if dimensoes is None:
            dimensoes = ["fiscal", "territorial", "social"]

        tasks = []
        labels = []
        for codigo in codigos_ibge:
            if "fiscal" in dimensoes:
                tasks.append(self._fiscal.run(codigo_ibge=codigo, consulta=consulta))
                labels.append((codigo, "fiscal"))
            if "territorial" in dimensoes:
                tasks.append(self._territorial.run(codigo_ibge=codigo, consulta=consulta))
                labels.append((codigo, "territorial"))
            if "social" in dimensoes:
                tasks.append(self._social.run(codigo_ibge=codigo, consulta=consulta))
                labels.append((codigo, "social"))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        municipios: dict[str, dict] = {}
        for (codigo, dim), res in zip(labels, results):
            if codigo not in municipios:
                municipios[codigo] = {}
            municipios[codigo][dim] = (
                res if not isinstance(res, Exception) else {"erro": str(res)}
            )

        return {
            "consulta": consulta,
            "municipios": municipios,
            "dimensoes_analisadas": dimensoes,
        }

    # ── Azure AI Agent run loop ────────────────────────────────────────────────

    async def run_with_azure_agent(self, question: str) -> str:
        """Run the question through the Azure AI Agent Service (requires valid config)."""
        if not settings.AZURE_AI_PROJECT_CONNECTION_STRING:
            logger.warning("Azure AI Project not configured; falling back to direct dispatch.")
            return await self._direct_dispatch(question)

        try:
            from azure.ai.projects import AIProjectClient
            from azure.ai.projects.models import FunctionTool, ToolSet
            from azure.identity import DefaultAzureCredential

            client = AIProjectClient.from_connection_string(
                credential=DefaultAzureCredential(),
                conn_str=settings.AZURE_AI_PROJECT_CONNECTION_STRING,
            )

            # Define tools using the SDK's FunctionTool wrapper
            functions = FunctionTool(functions={
                self.buscar_fiscal_fn,
                self.buscar_territorial_fn,
                self.buscar_social_fn,
                self.cruzar_dados_fn,
            })
            toolset = ToolSet()
            toolset.add(functions)

            with tracer.start_as_current_span("router.azure_agent_run") as span:
                agent = client.agents.create_agent(
                    model=settings.AZURE_OPENAI_DEPLOYMENT,
                    name="nexus-router",
                    instructions=_SYSTEM_PROMPT,
                    toolset=toolset,
                )
                span.set_attribute("azure.agent_id", agent.id)

                thread = client.agents.create_thread()
                client.agents.create_message(
                    thread_id=thread.id,
                    role="user",
                    content=question,
                )

                run = client.agents.create_and_process_run(
                    thread_id=thread.id,
                    agent_id=agent.id,
                    toolset=toolset,
                )

                messages = client.agents.list_messages(thread_id=thread.id)
                for msg in messages:
                    if msg.role == "assistant":
                        return msg.content[0].text.value if msg.content else ""

                return "Não foi possível gerar uma resposta."

        except ImportError:
            logger.warning("azure-ai-projects not installed; falling back to direct dispatch.")
            return await self._direct_dispatch(question)
        except Exception as e:
            logger.error(f"Azure Agent run failed: {e}")
            return await self._direct_dispatch(question)

    async def _direct_dispatch(self, question: str) -> str:
        """Minimal fallback: extract IBGE code from question and cross all dimensions."""
        with tracer.start_as_current_span("router.direct_dispatch"):
            logger.info(f"Direct dispatch for: {question[:80]}")
            # Heuristic: look for 7-digit number in the question
            import re
            codes = re.findall(r"\b\d{7}\b", question)
            if not codes:
                return (
                    "Para responder, preciso do código IBGE de 7 dígitos do município. "
                    "Exemplo: 3550308 (São Paulo/SP)."
                )
            result = await self._cruzar_dados(
                codigos_ibge=codes,
                dimensoes=["fiscal", "territorial", "social"],
                consulta=question,
            )
            return json.dumps(result, ensure_ascii=False, default=str, indent=2)

    # ── Syncable tool functions (used by Azure AI FunctionTool) ───────────────

    def buscar_fiscal_fn(self, codigo_ibge: str, ano: int = 2024, consulta: str = "") -> str:
        """Search fiscal data for a municipality (Bolsa Família, transfers, grants)."""
        return asyncio.run(
            self._fiscal.run(codigo_ibge=codigo_ibge, ano=ano, consulta=consulta)
        )

    def buscar_territorial_fn(self, codigo_ibge: str, consulta: str = "") -> str:
        """Search territorial/demographic data for a municipality."""
        return asyncio.run(
            self._territorial.run(codigo_ibge=codigo_ibge, consulta=consulta)
        )

    def buscar_social_fn(self, codigo_ibge: str, consulta: str = "") -> str:
        """Search social data (health + education) for a municipality."""
        return asyncio.run(
            self._social.run(codigo_ibge=codigo_ibge, consulta=consulta)
        )

    def cruzar_dados_fn(
        self,
        codigos_ibge: list[str],
        consulta: str,
        dimensoes: list[str] | None = None,
    ) -> str:
        """Cross-reference data across dimensions for one or more municipalities."""
        return asyncio.run(
            self._cruzar_dados(
                codigos_ibge=codigos_ibge,
                dimensoes=dimensoes,
                consulta=consulta,
            )
        )

    async def aclose(self) -> None:
        await asyncio.gather(
            self._fiscal.aclose(),
            self._territorial.aclose(),
            self._social.aclose(),
        )
