"""Router Agent — orchestrates fiscal, territorial, and social agents via GPT-4o function calling.

Uses the Azure AI Foundry (Nova Fábrica) endpoint + API key to obtain an
OpenAI-compatible client, then runs a function-calling loop to answer
natural-language questions about Brazilian municipalities.
"""
import asyncio
import json
import logging
import re

import openai
from opentelemetry import trace

from config import settings
from agents.fiscal import FiscalAgent
from agents.territorial import TerritorialAgent
from agents.social import SocialAgent

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

_SYSTEM_PROMPT = """Você é o NEXUS, um analista de IA especializado em dados públicos brasileiros.

Seu papel é responder perguntas de gestores e analistas do setor público cruzando três
dimensões de dados municipais:

• Fiscal     — transferências federais, Bolsa Família, convênios (Portal da Transparência)
• Territorial — demografia, PIB, geografia (IBGE)
• Social     — infraestrutura de saúde, indicadores educacionais (DATASUS + INEP)

Instruções:
1. Identifique o município na pergunta e obtenha seu código IBGE de 7 dígitos antes de consultar.
2. Use apenas as ferramentas disponíveis — nunca invente dados.
3. Combine dados de múltiplas dimensões quando a pergunta exigir.
4. Apresente números com unidades (R$, %, habitantes) e cite a fonte.
5. Destaque disparidades, riscos ou oportunidades baseados nos dados.
6. Responda no mesmo idioma da pergunta (português ou inglês).
7. Seja direto: comece pela resposta, depois os dados de suporte.
"""

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "buscar_municipio",
            "description": "Resolve o nome de um município brasileiro para seu código IBGE de 7 dígitos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string", "description": "Nome do município (ex: Campinas, Fortaleza)"},
                    "uf": {"type": "string", "description": "Sigla do estado, opcional (ex: SP, CE)"},
                },
                "required": ["nome"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_fiscal",
            "description": "Busca dados fiscais de um município: Bolsa Família, transferências federais, convênios.",
            "parameters": {
                "type": "object",
                "properties": {
                    "codigo_ibge": {"type": "string", "description": "Código IBGE de 7 dígitos"},
                    "ano": {"type": "integer", "description": "Ano de referência (padrão: 2024)"},
                    "consulta": {"type": "string", "description": "Pergunta específica"},
                },
                "required": ["codigo_ibge"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_territorial",
            "description": "Busca dados territoriais e demográficos: população (Censo 2022), PIB per capita, perfil geográfico.",
            "parameters": {
                "type": "object",
                "properties": {
                    "codigo_ibge": {"type": "string", "description": "Código IBGE de 7 dígitos"},
                    "consulta": {"type": "string", "description": "Pergunta específica"},
                },
                "required": ["codigo_ibge"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_social",
            "description": "Busca dados sociais: estabelecimentos de saúde (DATASUS/CNES) e indicadores educacionais (INEP).",
            "parameters": {
                "type": "object",
                "properties": {
                    "codigo_ibge": {"type": "string", "description": "Código IBGE de 7 dígitos"},
                    "consulta": {"type": "string", "description": "Pergunta específica"},
                },
                "required": ["codigo_ibge"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cruzar_dados",
            "description": "Cruza dados fiscais, territoriais e sociais de um ou mais municípios para análise comparativa.",
            "parameters": {
                "type": "object",
                "properties": {
                    "codigos_ibge": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de códigos IBGE de 7 dígitos",
                    },
                    "dimensoes": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["fiscal", "territorial", "social"]},
                        "description": "Dimensões a cruzar (padrão: todas)",
                    },
                    "consulta": {"type": "string", "description": "Pergunta ou hipótese a investigar"},
                },
                "required": ["codigos_ibge", "consulta"],
            },
        },
    },
]


class RouterAgent:
    def __init__(self) -> None:
        self._fiscal = FiscalAgent()
        self._territorial = TerritorialAgent()
        self._social = SocialAgent()
        self._openai_client: openai.OpenAI | None = None

    def _get_client(self) -> openai.OpenAI | None:
        if not settings.AZURE_AI_PROJECT_ENDPOINT or not settings.AZURE_AI_API_KEY:
            return None
        if self._openai_client is None:
            base_url = settings.AZURE_AI_PROJECT_ENDPOINT.rstrip("/") + "/openai/v1/"
            self._openai_client = openai.OpenAI(
                base_url=base_url,
                api_key=settings.AZURE_AI_API_KEY,
            )
        return self._openai_client

    async def _execute_tool(self, name: str, arguments: dict) -> str:
        with tracer.start_as_current_span(f"router.tool.{name}") as span:
            span.set_attribute("tool.name", name)
            try:
                if name == "buscar_municipio":
                    result = await self._resolve_municipio(
                        arguments["nome"], arguments.get("uf", "")
                    )
                elif name == "buscar_fiscal":
                    result = await self._fiscal.run(
                        codigo_ibge=arguments["codigo_ibge"],
                        ano=arguments.get("ano", 2024),
                        consulta=arguments.get("consulta", ""),
                    )
                elif name == "buscar_territorial":
                    result = await self._territorial.run(
                        codigo_ibge=arguments["codigo_ibge"],
                        consulta=arguments.get("consulta", ""),
                    )
                elif name == "buscar_social":
                    result = await self._social.run(
                        codigo_ibge=arguments["codigo_ibge"],
                        consulta=arguments.get("consulta", ""),
                    )
                elif name == "cruzar_dados":
                    result = await self._cruzar_dados(
                        codigos_ibge=arguments["codigos_ibge"],
                        dimensoes=arguments.get("dimensoes", ["fiscal", "territorial", "social"]),
                        consulta=arguments.get("consulta", ""),
                    )
                else:
                    result = {"erro": f"Ferramenta desconhecida: {name}"}
                return json.dumps(result, ensure_ascii=False, default=str)
            except Exception as e:
                logger.error(f"Tool {name} error: {e}")
                return json.dumps({"erro": str(e)})

    async def _resolve_municipio(self, nome: str, uf: str = "") -> dict:
        import httpx
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                "https://servicodados.ibge.gov.br/api/v1/localidades/municipios",
                params={"nome": nome},
            )
            r.raise_for_status()
            data = r.json()

        results = []
        for m in data[:5]:
            try:
                uf_sigla = m["microrregiao"]["mesorregiao"]["UF"]["sigla"]
                if uf and uf_sigla.upper() != uf.upper():
                    continue
                results.append({"codigo_ibge": str(m["id"]), "nome": m["nome"], "uf": uf_sigla})
            except (KeyError, TypeError):
                pass

        if not results:
            return {"erro": f"Município '{nome}' não encontrado"}
        return {"municipios": results, "principal": results[0]}

    async def _cruzar_dados(
        self,
        codigos_ibge: list[str],
        dimensoes: list[str],
        consulta: str,
    ) -> dict:
        tasks, labels = [], []
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
            municipios.setdefault(codigo, {})[dim] = (
                res if not isinstance(res, Exception) else {"erro": str(res)}
            )
        return {"consulta": consulta, "municipios": municipios, "dimensoes": dimensoes}

    async def run_with_azure_agent(self, question: str) -> str:
        client = self._get_client()
        if client is None:
            logger.warning("Azure AI não configurado — usando fallback direto.")
            return await self._direct_dispatch(question)

        with tracer.start_as_current_span("router.gpt4o_run") as span:
            span.set_attribute("question_len", len(question))
            messages: list[dict] = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ]

            try:
                for _ in range(8):  # max 8 turns
                    response = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda msgs=messages: client.chat.completions.create(
                            model=settings.AZURE_OPENAI_DEPLOYMENT,
                            messages=msgs,
                            tools=_TOOLS,
                            tool_choice="auto",
                            max_tokens=2048,
                        ),
                    )

                    msg = response.choices[0].message
                    messages.append(msg.model_dump(exclude_unset=False))

                    if not msg.tool_calls:
                        return msg.content or "Não foi possível gerar uma resposta."

                    tool_results = await asyncio.gather(*[
                        self._execute_tool(tc.function.name, json.loads(tc.function.arguments))
                        for tc in msg.tool_calls
                    ])

                    for tc, result in zip(msg.tool_calls, tool_results):
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result,
                        })

                return "Limite de iterações atingido sem resposta final."

            except openai.NotFoundError:
                logger.error("GPT-4o deployment not found — deploy it in Azure AI Foundry first.")
                return await self._direct_dispatch(question)
            except Exception as e:
                logger.error(f"Azure GPT-4o error: {e}")
                return await self._direct_dispatch(question)

    async def _direct_dispatch(self, question: str) -> str:
        """Fallback: tenta resolver município pelo nome e cruza todas as dimensões."""
        with tracer.start_as_current_span("router.direct_dispatch"):
            codes = re.findall(r"\b\d{7}\b", question)

            if not codes:
                words = [w.strip(".,?!") for w in question.split() if len(w) > 3]
                for word in words:
                    try:
                        resolved = await self._resolve_municipio(word)
                        if "principal" in resolved:
                            codes = [resolved["principal"]["codigo_ibge"]]
                            break
                    except Exception:
                        continue

            if not codes:
                return (
                    "Para responder, preciso identificar o município na pergunta. "
                    "Tente mencionar o nome completo (ex: 'Campinas', 'Fortaleza') "
                    "ou o código IBGE de 7 dígitos."
                )

            result = await self._cruzar_dados(
                codigos_ibge=codes[:2],
                dimensoes=["fiscal", "territorial", "social"],
                consulta=question,
            )
            return json.dumps(result, ensure_ascii=False, default=str, indent=2)

    async def aclose(self) -> None:
        await asyncio.gather(
            self._fiscal.aclose(),
            self._territorial.aclose(),
            self._social.aclose(),
        )
