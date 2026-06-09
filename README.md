# NEXUS — Plataforma de Inteligência Territorial

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Azure AI Foundry](https://img.shields.io/badge/Azure_AI_Foundry-Agents-0078D4?logo=microsoft-azure&logoColor=white)](https://ai.azure.com)
[![MCP](https://img.shields.io/badge/MCP-1.9+-6C3483?logo=anthropic&logoColor=white)](https://modelcontextprotocol.io)
[![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-Traced-F5A623?logo=opentelemetry&logoColor=white)](https://opentelemetry.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## O Problema

O Brasil tem **5.570 municípios**. O governo federal transfere mais de **R$ 1 trilhão por ano** através de programas como Bolsa Família, convênios, FPM e transferências diretas. Cada município, além disso, carrega um perfil único de saúde pública, educação, demografia e capacidade econômica.

O problema: **nenhum gestor público consegue enxergar tudo isso ao mesmo tempo.**

Os dados existem — e são públicos — mas estão espalhados em silos:

| Silo | Onde está | Barreira |
|------|-----------|----------|
| Fiscal | Portal da Transparência | API técnica, sem linguagem natural |
| Territorial | IBGE Localidades + SIDRA | Múltiplos endpoints, codificação específica |
| Saúde | DATASUS / CNES | API fragmentada, sem consolidação |
| Educação | INEP | Apenas arquivos XLSX, sem API REST |

Um gestor municipal que quer responder **"como estamos em saúde comparado ao Nordeste?"** hoje precisa: navegar quatro portais diferentes, baixar planilhas, cruzar códigos IBGE, e ainda assim não terá uma resposta consolidada.

Decisões de política pública são tomadas **no escuro** — não por falta de dados, mas por falta de acesso inteligente a eles.

---

## A Solução

**NEXUS** é uma plataforma multi-agente de inteligência territorial que transforma dados públicos brasileiros em respostas em linguagem natural para gestores e analistas do setor público.

Uma pergunta como:

> *"Compare Fortaleza e Campinas em transferências federais, infraestrutura de saúde e tamanho populacional"*

...dispara automaticamente três agentes especializados em paralelo, que consultam APIs reais do governo, cruzam os dados e entregam uma análise sintetizada — em segundos.

### Como funciona

```
Gestor / Analista / Sistema
          │
          ▼
   POST /v1/query
   {"question": "..."}
          │
          ▼
  ┌───────────────────┐
  │   Router Agent    │  ← Azure AI Foundry (GPT-4o)
  │   GPT-4o + tools  │    decompõe a pergunta e
  └────────┬──────────┘    decide quais dados buscar
           │ despacha em paralelo
  ┌────────┼────────┐
  ▼        ▼        ▼
Fiscal  Territorial  Social
Agent     Agent      Agent
  │          │          │
  ▼          ▼          ▼
Portal    IBGE       DATASUS
Transpar. SIDRA      + INEP
```

### Três dimensões integradas

| Dimensão | O que entrega | Fonte |
|----------|---------------|-------|
| **Fiscal** | Bolsa Família, transferências federais, convênios, licitações | Portal da Transparência |
| **Territorial** | População (Censo 2022), PIB per capita, perfil geográfico, região | IBGE Localidades + SIDRA |
| **Social** | Estabelecimentos e profissionais de saúde, links IDEB, matrículas | DATASUS/CNES + INEP |

### Por que isso importa

- **5.570 municípios** acessíveis pelo nome ou código IBGE
- **Linguagem natural** — sem necessidade de saber qual API chamar
- **Dados reais** de APIs governamentais ativas, não simulados
- **MCP-nativo** — qualquer cliente AI (Claude, Copilot, agentes customizados) pode consumir via protocolo padrão
- **Tempo real** — dados buscados na hora, não em batch

---

## Arquitetura

```
Usuário / Cliente AI
        │
        ▼
┌──────────────────────────────────────────────────┐
│           FastAPI MCP Server  :8000              │
│  GET /sse  ·  POST /messages      (MCP/SSE)      │
│  POST /v1/{fiscal|territorial|social|cruzar}     │
│  POST /v1/query                   (NL)           │
│  GET  /v1/municipios/buscar       (search)       │
│  GET  /                           (frontend)     │
└──────────────┬───────────────────────────────────┘
               │
               ▼
     ┌─────────────────┐
     │  Router Agent   │  ← Azure AI Agent Service (GPT-4o)
     │  agents/router  │    function-calling loop
     └────────┬────────┘
              │
  ┌───────────┼───────────┐
  ▼           ▼           ▼
┌──────┐ ┌──────────┐ ┌────────┐
│Fiscal│ │Territorial│ │ Social │
│Agent │ │  Agent   │ │ Agent  │
└──┬───┘ └────┬─────┘ └───┬────┘
   │           │            │
   ▼           ▼            ▼
transparencia ibge.py   datasus.py
   .py                  inep.py

Chave universal: código IBGE de 7 dígitos
```

---

## Quick Start

### Pré-requisitos
- Python 3.12+
- [Chave API do Portal da Transparência](https://portaldatransparencia.gov.br/api-de-dados/cadastrar-email) (gratuita)
- Projeto Azure AI Foundry (opcional — necessário para síntese em linguagem natural via GPT-4o)

### 1. Clonar e instalar

```bash
git clone https://github.com/ph-melo22/nexus-territorial-intelligence.git
cd nexus-territorial-intelligence

python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configurar

```bash
cp .env.example .env
# Editar .env — mínimo necessário: TRANSPARENCIA_API_KEY
```

### 3. Rodar

```bash
make dev
# ou
uvicorn main:app --reload
```

Servidor em `http://localhost:8000`. Frontend acessível na raiz.

### Docker

```bash
docker-compose up --build
```

---

## Referência da API

### Health

```
GET /health
→ {"status": "ok", "service": "nexus-mcp", "version": "1.0.0", "mcp_enabled": true}
```

### Consulta em linguagem natural

```
POST /v1/query
{"question": "Quanto Campinas recebeu de Bolsa Família em 2024?"}
```

### Ferramentas individuais

```
POST /v1/buscar_fiscal
{"codigo_ibge": "3509502", "ano": 2024}

POST /v1/buscar_territorial
{"codigo_ibge": "3509502"}

POST /v1/buscar_social
{"codigo_ibge": "3509502"}

POST /v1/cruzar_dados
{
  "codigos_ibge": ["3509502", "2304400"],
  "dimensoes": ["fiscal", "territorial", "social"],
  "consulta": "Compare Campinas e Fortaleza em investimento social per capita"
}
```

### Busca de municípios

```
GET /v1/municipios/buscar?nome=campinas&uf=SP&limit=5
```

### MCP (SSE)

```
GET  /sse       ← conexão SSE para clientes MCP
POST /messages  ← mensagens JSON-RPC
```

---

## Exemplos de uso

```
"Quanto Manaus recebeu de Bolsa Família em 2024?"
→ buscar_fiscal(3302403)

"Qual a população e o PIB per capita de Curitiba?"
→ buscar_territorial(4106902)

"Quantos hospitais existem em Fortaleza?"
→ buscar_social(2304400)

"Compare Campinas e São Paulo em saúde e capacidade fiscal"
→ cruzar_dados(["3509502","3550308"], ["fiscal","social"], consulta="...")
```

---

## Fontes de dados

| Dimensão | Fonte | Endpoint | Auth |
|----------|-------|----------|------|
| Fiscal | Portal da Transparência | `api.portaldatransparencia.gov.br/api-de-dados` | Chave gratuita |
| Territorial | IBGE Localidades | `servicodados.ibge.gov.br/api/v1/localidades` | Nenhuma |
| Territorial | IBGE SIDRA | População Censo 2022, PIB per capita 2021 | Nenhuma |
| Social | CNES / Min. Saúde | `apidadosabertos.saude.gov.br/v1/cnes` | Nenhuma |
| Social | OpenDATASUS | `opendatasus.saude.gov.br/api/3/action` | Nenhuma |
| Social | INEP Dados Abertos | IDEB, Censo Escolar (XLSX) | Nenhuma |

---

## Estrutura do projeto

```
nexus-territorial-intelligence/
├── main.py                  # FastAPI MCP server + endpoints REST
├── config.py                # Configurações via variáveis de ambiente
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
│
├── agents/
│   ├── router.py            # Router Agent (Azure AI Foundry)
│   ├── fiscal.py            # Agente Fiscal
│   ├── territorial.py       # Agente Territorial
│   └── social.py            # Agente Social (saúde + educação)
│
├── tools/
│   ├── ibge.py              # IBGE Localidades + SIDRA
│   ├── transparencia.py     # Portal da Transparência
│   ├── datasus.py           # DATASUS / CNES
│   └── inep.py              # INEP educação
│
├── frontend/
│   └── index.html           # SPA (Alpine.js + Tailwind)
│
└── tests/
    └── test_tools.py        # 17 testes de integração
```

---

## Observabilidade

Cada execução de agente e chamada de ferramenta é instrumentada com **OpenTelemetry**. Configure `OTLP_ENDPOINT` no `.env` para enviar traces ao Azure Monitor (Application Insights) ou qualquer backend OTLP.

Spans principais:
- `agent.fiscal` / `agent.territorial` / `agent.social`
- `ibge.get_perfil_completo`, `transparencia.perfil_fiscal`
- `mcp.tool.{name}`, `rest.{name}`
- `router.azure_agent_run`

---

## Licença

[MIT](LICENSE)

---

*Construído com Azure AI Foundry · FastAPI · Model Context Protocol · OpenTelemetry*
