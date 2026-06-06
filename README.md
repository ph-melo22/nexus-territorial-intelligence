# NEXUS — Territorial Intelligence Platform

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Azure AI Foundry](https://img.shields.io/badge/Azure_AI_Foundry-Agents-0078D4?logo=microsoft-azure&logoColor=white)](https://ai.azure.com)
[![MCP](https://img.shields.io/badge/MCP-1.9+-6C3483?logo=anthropic&logoColor=white)](https://modelcontextprotocol.io)
[![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-Traced-F5A623?logo=opentelemetry&logoColor=white)](https://opentelemetry.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

> **Microsoft Agents League @ AI Skills Fest 2026** — Submission

NEXUS crosses Brazilian public fiscal, social, and geographic open data to deliver actionable natural-language insights for public sector decision makers — powered by Azure AI Foundry multi-agent orchestration and real government APIs.

---

## Why / How / What

### WHY
Brazilian municipalities manage billions in federal transfers with limited capacity to connect fiscal, social, and territorial data. Decisions are made in silos. NEXUS breaks those silos.

### HOW
A Router Agent (Azure AI Agent Service) receives a natural-language question, decomposes it, and dispatches specialized sub-agents that query real Brazilian government APIs concurrently. The results are cross-referenced and surfaced as a synthesized narrative — in Portuguese or English.

### WHAT
A FastAPI MCP server exposing four tools that span three dimensions of public intelligence: **fiscal** (where the money goes), **territorial** (who lives where and at what cost), and **social** (how people live). Any AI client that speaks MCP or REST can consume it.

---

## Architecture

```
User / AI Client
       │
       ▼
 ┌─────────────────────────────────────────────────┐
 │          FastAPI MCP Server  :8000              │
 │  GET /sse  ·  POST /messages  (MCP/SSE)         │
 │  POST /v1/{buscar_fiscal|territorial|social|    │
 │             cruzar_dados}    (REST)             │
 │  POST /v1/query              (NL entry point)   │
 └──────────────┬──────────────────────────────────┘
                │
                ▼
      ┌─────────────────┐
      │  Router Agent   │  ← Azure AI Agent Service (gpt-4o)
      │  agents/router  │    + function-calling loop
      └────────┬────────┘
               │ dispatches to
   ┌───────────┼───────────┐
   ▼           ▼           ▼
┌──────┐  ┌──────────┐  ┌────────┐
│Fiscal│  │Territorial│  │ Social │
│Agent │  │  Agent    │  │ Agent  │
└──┬───┘  └─────┬─────┘  └───┬────┘
   │             │             │
   ▼             ▼             ▼
transparencia  ibge.py    datasus.py
   .py                    inep.py

Universal key: IBGE 7-digit municipality code
```

---

## Data Sources

| Dimension | Source | API / Endpoint | Auth |
|-----------|--------|---------------|------|
| Fiscal | Portal da Transparência | `api.portaldatransparencia.gov.br/api-de-dados` | Free API key |
| Fiscal | Portal da Transparência | Bolsa Família, Transferências, Convênios | Free API key |
| Territorial | IBGE Localidades | `servicodados.ibge.gov.br/api/v1/localidades` | None |
| Territorial | IBGE SIDRA | Population, PIB per capita | None |
| Social | CNES / Min. Saúde | `apidadosabertos.saude.gov.br/v1/cnes` | None |
| Social | OpenDATASUS | `opendatasus.saude.gov.br/api/3/action` | None |
| Social | INEP / IBGE SIDRA | School enrollments, teachers | None |
| Social | INEP Open Data | IDEB microdata (Excel files) | None |

> **Municipality universal key**: All data is keyed by the 7-digit IBGE municipality code (e.g. `3550308` for São Paulo/SP).

---

## Quick Start

### Prerequisites
- Python 3.12+
- [Portal da Transparência API key](https://portaldatransparencia.gov.br/api-de-dados/cadastrar-email) (free)
- Azure subscription with Azure AI Foundry project (optional — for Router Agent)

### 1. Clone & install

```bash
git clone https://github.com/your-org/nexus-territorial-intelligence.git
cd nexus-territorial-intelligence

python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — minimum required: TRANSPARENCIA_API_KEY
```

### 3. Run

```bash
python main.py
# or
uvicorn main:app --reload
```

Server starts at `http://localhost:8000`.

---

## API Reference

### Health

```
GET /health
```

```json
{"status": "ok", "service": "nexus-mcp", "version": "1.0.0", "mcp_enabled": true}
```

### Natural Language Query

```
POST /v1/query
{"question": "Qual o total de transferências federais para Campinas em 2023?"}
```

### Tool Endpoints

All tools accept JSON bodies; `codigo_ibge` is always required.

```
POST /v1/buscar_fiscal
{"codigo_ibge": "3509502", "ano": 2024}

POST /v1/buscar_territorial
{"codigo_ibge": "3509502"}

POST /v1/buscar_social
{"codigo_ibge": "3509502"}

POST /v1/cruzar_dados
{
  "codigos_ibge": ["3509502", "3550308"],
  "dimensoes": ["fiscal", "territorial", "social"],
  "consulta": "Compare Campinas e São Paulo em investimento social per capita"
}
```

### MCP Transport (SSE)

```
GET  /sse       ← SSE connection (MCP clients)
POST /messages  ← JSON-RPC messages
```

---

## Example Queries

```
"Quanto Manaus recebeu de Bolsa Família em 2024?"
→ buscar_fiscal(3302403)

"Qual a população e o PIB per capita de Curitiba?"
→ buscar_territorial(4106902)

"Quantos hospitais existem em Fortaleza?"
→ buscar_social(2304400)

"Compare os municípios do Nordeste com menor IDH no eixo fiscal e social"
→ cruzar_dados([...], ["fiscal","social"], consulta="...")
```

---

## Project Structure

```
nexus-territorial-intelligence/
├── main.py                  # FastAPI MCP server + REST endpoints
├── config.py                # Pydantic settings (env-driven)
├── requirements.txt
├── .env.example
│
├── agents/
│   ├── __init__.py
│   ├── router.py            # Router Agent (Azure AI Agent Service)
│   ├── fiscal.py            # Fiscal Agent
│   ├── territorial.py       # Territorial Agent
│   └── social.py            # Social Agent (health + education)
│
└── tools/
    ├── __init__.py
    ├── ibge.py              # IBGE Localidades + SIDRA client
    ├── transparencia.py     # Portal da Transparência client
    ├── datasus.py           # DATASUS / Ministério da Saúde client
    └── inep.py              # INEP education data client
```

---

## Observability

NEXUS instruments every agent run and tool call with **OpenTelemetry** spans. Set `OTLP_ENDPOINT` in `.env` to ship traces to Azure Monitor (Application Insights), Jaeger, or any OTLP-compatible backend.

Key span names:
- `agent.fiscal` / `agent.territorial` / `agent.social`
- `ibge.get_perfil_completo`, `transparencia.perfil_fiscal`, etc.
- `mcp.tool.{name}`, `rest.{name}`
- `router.azure_agent_run`

---

## Hackathon Tracks

This submission targets the following **Microsoft Agents League** tracks:

| Track | How NEXUS qualifies |
|-------|---------------------|
| **AI Agent** | Router Agent orchestrates sub-agents using Azure AI Agent Service function-calling |
| **MCP** | FastAPI MCP server with SSE transport exposes 4 tools consumable by any MCP client |
| **GitHub Copilot** | Codebase scaffolded and iterated with GitHub Copilot (agent mode) |
| **Responsible AI** | All data sourced from free Brazilian government open data; no PII; transparent provenance |

---

## Contributing

Pull requests welcome. Please open an issue first to discuss what you would like to change.

---

## License

[MIT](LICENSE)

---

*Built with Azure AI Foundry · FastAPI · Model Context Protocol · OpenTelemetry*
*for the Microsoft Agents League @ AI Skills Fest 2026*
