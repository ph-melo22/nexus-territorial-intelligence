"""NEXUS — Multi-Agent Territorial Intelligence Platform.

FastAPI application that acts as an MCP server exposing four intelligence tools
for Brazilian public sector data. Also serves REST endpoints consumed directly
by Azure AI Agent Service function-calling.

MCP transport:  SSE at GET /sse  +  POST /messages
REST endpoints: POST /v1/buscar_fiscal | buscar_territorial | buscar_social | cruzar_dados
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse as _JSONResponse


class JSONResponse(_JSONResponse):
    """JSONResponse that preserves UTF-8 characters (no ASCII escaping)."""
    def render(self, content) -> bytes:
        return json.dumps(content, ensure_ascii=False, default=str).encode("utf-8")
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from config import settings
from agents.fiscal import FiscalAgent
from agents.territorial import TerritorialAgent
from agents.social import SocialAgent

# ── OpenTelemetry ─────────────────────────────────────────────────────────────

def _setup_telemetry() -> None:
    provider = TracerProvider()
    if settings.OTLP_ENDPOINT:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.OTLP_ENDPOINT))
            )
        except ImportError:
            logging.warning("OTLP exporter not installed; traces will go to console.")
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)


_setup_telemetry()
tracer = trace.get_tracer(__name__)
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)

# ── Shared agent instances (created once, reused) ─────────────────────────────

fiscal_agent = FiscalAgent()
territorial_agent = TerritorialAgent()
social_agent = SocialAgent()


async def _cruzar_dados(
    codigos_ibge: list[str],
    dimensoes: list[str],
    consulta: str,
) -> dict:
    """Gather all requested dimensions concurrently, then assemble the report."""
    with tracer.start_as_current_span("nexus.cruzar_dados") as span:
        span.set_attribute("municipios", ",".join(codigos_ibge))
        span.set_attribute("dimensoes", ",".join(dimensoes))

        tasks: list[Any] = []
        labels: list[tuple[str, str]] = []

        for codigo in codigos_ibge:
            if "fiscal" in dimensoes:
                tasks.append(fiscal_agent.run(codigo_ibge=codigo, consulta=consulta))
                labels.append((codigo, "fiscal"))
            if "territorial" in dimensoes:
                tasks.append(territorial_agent.run(codigo_ibge=codigo, consulta=consulta))
                labels.append((codigo, "territorial"))
            if "social" in dimensoes:
                tasks.append(social_agent.run(codigo_ibge=codigo, consulta=consulta))
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


# ── MCP Server ────────────────────────────────────────────────────────────────

try:
    from mcp.server import Server
    from mcp.server.sse import SseServerTransport
    from mcp import types as mcp_types

    mcp_server = Server("nexus-mcp")

    @mcp_server.list_tools()
    async def _list_tools() -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(
                name="buscar_fiscal",
                description=(
                    "Busca dados fiscais e orçamentários de um município brasileiro. "
                    "Retorna transferências federais, Bolsa Família, convênios e licitações "
                    "a partir do Portal da Transparência."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "codigo_ibge": {
                            "type": "string",
                            "description": "Código IBGE de 7 dígitos do município",
                        },
                        "ano": {
                            "type": "integer",
                            "description": "Ano de referência (padrão: 2024)",
                        },
                        "consulta": {
                            "type": "string",
                            "description": "Pergunta específica em linguagem natural",
                        },
                    },
                    "required": ["codigo_ibge"],
                },
            ),
            mcp_types.Tool(
                name="buscar_territorial",
                description=(
                    "Busca dados territoriais, demográficos e socioeconômicos de um município "
                    "brasileiro via IBGE. Retorna população, PIB, perfil geográfico e região."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "codigo_ibge": {
                            "type": "string",
                            "description": "Código IBGE de 7 dígitos do município",
                        },
                        "consulta": {
                            "type": "string",
                            "description": "Pergunta específica em linguagem natural",
                        },
                    },
                    "required": ["codigo_ibge"],
                },
            ),
            mcp_types.Tool(
                name="buscar_social",
                description=(
                    "Busca dados sociais de saúde e educação de um município brasileiro. "
                    "Retorna estabelecimentos e profissionais de saúde (DATASUS/CNES) e "
                    "indicadores educacionais (INEP/Censo Escolar)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "codigo_ibge": {
                            "type": "string",
                            "description": "Código IBGE de 7 dígitos do município",
                        },
                        "consulta": {
                            "type": "string",
                            "description": "Pergunta específica em linguagem natural",
                        },
                    },
                    "required": ["codigo_ibge"],
                },
            ),
            mcp_types.Tool(
                name="cruzar_dados",
                description=(
                    "Cruza dados fiscais, territoriais e sociais de um ou mais municípios. "
                    "Produz análise multi-dimensional para comparação e identificação de correlações."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "codigos_ibge": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Lista de códigos IBGE de 7 dígitos",
                        },
                        "dimensoes": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["fiscal", "territorial", "social"],
                            },
                            "description": "Dimensões a cruzar (padrão: todas)",
                        },
                        "consulta": {
                            "type": "string",
                            "description": "Pergunta ou hipótese a investigar",
                        },
                    },
                    "required": ["codigos_ibge", "consulta"],
                },
            ),
        ]

    @mcp_server.call_tool()
    async def _call_tool(
        name: str, arguments: dict
    ) -> list[mcp_types.TextContent]:
        with tracer.start_as_current_span(f"mcp.tool.{name}") as span:
            span.set_attribute("tool.name", name)
            try:
                result = await _dispatch_tool(name, arguments)
                text = json.dumps(result, ensure_ascii=False, default=str)
                return [mcp_types.TextContent(type="text", text=text)]
            except Exception as e:
                span.record_exception(e)
                logger.error(f"MCP tool {name} error: {e}")
                return [mcp_types.TextContent(type="text", text=f'{{"erro": "{e}"}}')]

    _mcp_available = True
    sse_transport = SseServerTransport("/messages")

except ImportError:
    logger.warning("mcp package not installed — MCP/SSE endpoints will be unavailable.")
    _mcp_available = False
    mcp_server = None  # type: ignore
    sse_transport = None  # type: ignore


async def _dispatch_tool(name: str, arguments: dict) -> Any:
    """Central dispatch shared by MCP and REST handlers."""
    if name == "buscar_fiscal":
        return await fiscal_agent.run(
            codigo_ibge=arguments["codigo_ibge"],
            ano=arguments.get("ano", 2024),
            consulta=arguments.get("consulta", ""),
        )
    if name == "buscar_territorial":
        return await territorial_agent.run(
            codigo_ibge=arguments["codigo_ibge"],
            consulta=arguments.get("consulta", ""),
        )
    if name == "buscar_social":
        return await social_agent.run(
            codigo_ibge=arguments["codigo_ibge"],
            consulta=arguments.get("consulta", ""),
        )
    if name == "cruzar_dados":
        return await _cruzar_dados(
            codigos_ibge=arguments["codigos_ibge"],
            dimensoes=arguments.get("dimensoes", ["fiscal", "territorial", "social"]),
            consulta=arguments.get("consulta", ""),
        )
    raise ValueError(f"Unknown tool: {name}")


# ── FastAPI app ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        f"NEXUS MCP Server starting — host={settings.HOST} port={settings.PORT} "
        f"mcp={'enabled' if _mcp_available else 'disabled (install mcp package)'}"
    )
    yield
    logger.info("NEXUS MCP Server shutting down")
    await asyncio.gather(
        fiscal_agent.aclose(),
        territorial_agent.aclose(),
        social_agent.aclose(),
        return_exceptions=True,
    )


app = FastAPI(
    title="NEXUS — Territorial Intelligence Platform",
    description=(
        "Multi-agent platform that crosses Brazilian public fiscal, social and geographic "
        "open data to deliver actionable natural-language insights for public sector decision makers."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FastAPIInstrumentor.instrument_app(app)

# ── MCP SSE routes (only when mcp package available) ─────────────────────────

if _mcp_available:
    @app.get("/sse", include_in_schema=False)
    async def mcp_sse(request: Request) -> None:
        async with sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp_server.run(
                streams[0],
                streams[1],
                mcp_server.create_initialization_options(),
            )

    @app.post("/messages", include_in_schema=False)
    async def mcp_messages(request: Request) -> None:
        await sse_transport.handle_post_message(
            request.scope, request.receive, request._send
        )

# ── Health / discovery ────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {
        "status": "ok",
        "service": "nexus-mcp",
        "version": "1.0.0",
        "mcp_enabled": _mcp_available,
    }


@app.get("/tools", tags=["meta"])
async def list_tools_endpoint() -> dict:
    """Enumerate available tools (convenience; does not use MCP transport)."""
    tools = [
        {"name": "buscar_fiscal", "dimensao": "fiscal"},
        {"name": "buscar_territorial", "dimensao": "territorial"},
        {"name": "buscar_social", "dimensao": "social"},
        {"name": "cruzar_dados", "dimensao": "all"},
    ]
    return {"tools": tools, "count": len(tools)}


# ── REST tool endpoints (Azure AI Agent Service function-calling) ─────────────

@app.post("/v1/buscar_fiscal", tags=["tools"])
async def buscar_fiscal(request: Request) -> JSONResponse:
    """Fiscal data: Bolsa Família, federal transfers, grants."""
    body = await request.json()
    with tracer.start_as_current_span("rest.buscar_fiscal"):
        result = await fiscal_agent.run(
            codigo_ibge=body["codigo_ibge"],
            ano=body.get("ano", 2024),
            consulta=body.get("consulta", ""),
        )
        return JSONResponse(result)


@app.post("/v1/buscar_territorial", tags=["tools"])
async def buscar_territorial(request: Request) -> JSONResponse:
    """Territorial data: population, PIB, geography (IBGE)."""
    body = await request.json()
    with tracer.start_as_current_span("rest.buscar_territorial"):
        result = await territorial_agent.run(
            codigo_ibge=body["codigo_ibge"],
            consulta=body.get("consulta", ""),
        )
        return JSONResponse(result)


@app.post("/v1/buscar_social", tags=["tools"])
async def buscar_social(request: Request) -> JSONResponse:
    """Social data: health infrastructure (DATASUS/CNES) + education (INEP)."""
    body = await request.json()
    with tracer.start_as_current_span("rest.buscar_social"):
        result = await social_agent.run(
            codigo_ibge=body["codigo_ibge"],
            consulta=body.get("consulta", ""),
        )
        return JSONResponse(result)


@app.post("/v1/cruzar_dados", tags=["tools"])
async def cruzar_dados(request: Request) -> JSONResponse:
    """Cross-reference fiscal + territorial + social data for one or more municipalities."""
    body = await request.json()
    with tracer.start_as_current_span("rest.cruzar_dados"):
        result = await _cruzar_dados(
            codigos_ibge=body["codigos_ibge"],
            dimensoes=body.get("dimensoes", ["fiscal", "territorial", "social"]),
            consulta=body.get("consulta", ""),
        )
        return JSONResponse(result)


# ── Query endpoint (natural language → router agent) ─────────────────────────

@app.post("/v1/query", tags=["query"])
async def query(request: Request) -> JSONResponse:
    """Natural-language query endpoint. Routes through the Router Agent."""
    body = await request.json()
    question: str = body.get("question", "")
    if not question:
        return JSONResponse({"erro": "Field 'question' is required."}, status_code=422)

    from agents.router import RouterAgent
    router = RouterAgent()
    try:
        with tracer.start_as_current_span("rest.query"):
            result = await router.run_with_azure_agent(question)
        return JSONResponse({
            "question": question,
            "answer": result.get("answer", ""),
            "steps": result.get("steps", []),
            "model": result.get("model", ""),
        })
    finally:
        await router.aclose()


# ── Municipality search (cached) ─────────────────────────────────────────────

_municipios_cache: list[dict] | None = None


async def _get_all_municipios() -> list[dict]:
    global _municipios_cache
    if _municipios_cache is None:
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=20) as c:
            r = await c.get("https://servicodados.ibge.gov.br/api/v1/localidades/municipios")
            r.raise_for_status()
            data = r.json()
        result = []
        for m in data:
            try:
                uf = m["microrregiao"]["mesorregiao"]["UF"]
                result.append({
                    "id": str(m["id"]),
                    "nome": m["nome"],
                    "estado": uf["sigla"],
                    "estado_nome": uf["nome"],
                    "regiao": uf["regiao"]["sigla"],
                })
            except (TypeError, KeyError):
                result.append({
                    "id": str(m["id"]),
                    "nome": m["nome"],
                    "estado": "?",
                    "estado_nome": "?",
                    "regiao": "?",
                })
        _municipios_cache = result
        logger.info(f"Municipality cache loaded: {len(_municipios_cache)} municipalities")
    return _municipios_cache


@app.get("/v1/municipios/buscar", tags=["municipios"])
async def buscar_municipios(
    nome: str = Query(default="", description="Nome (ou parte) do município"),
    uf: str = Query(default="", description="Sigla do estado (ex: SP)"),
    limit: int = Query(default=10, le=50),
) -> JSONResponse:
    """Search municipalities by name and/or UF (cached from IBGE)."""
    todos = await _get_all_municipios()
    filtered = todos
    if nome:
        q = nome.lower()
        filtered = [m for m in filtered if q in m["nome"].lower()]
    if uf:
        filtered = [m for m in filtered if m["estado"].upper() == uf.upper()]
    return JSONResponse({"municipios": filtered[:limit], "total": len(filtered)})


# ── Frontend ──────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def serve_frontend() -> FileResponse:
    return FileResponse("frontend/index.html", media_type="text/html")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
