# Arquitetura do NEXUS

**Última atualização:** 2026-06-10

---

## Fluxo principal

```
Usuário digita pergunta em linguagem natural
        │
        ▼
POST /v1/query  {"question": "..."}
        │
        ▼
RouterAgent.run_with_azure_agent(question)
        │
        ├─ Tenta Azure AI Foundry (endpoint + API key)
        │       └─ Se NotFoundError/AuthError → fallback
        ├─ Tenta GitHub Models (ghp_... token)
        │       └─ Se erro → fallback
        └─ _direct_dispatch (sem LLM, só dados brutos)
        │
        ▼ (com LLM ativo)
GPT-4o function-calling loop (até 8 turnos)
        │
        ├─ buscar_municipio(nome, uf?) → resolve para código IBGE 7 dígitos
        ├─ buscar_fiscal(codigo_ibge) → FiscalAgent
        ├─ buscar_territorial(codigo_ibge) → TerritorialAgent
        ├─ buscar_social(codigo_ibge) → SocialAgent
        └─ cruzar_dados([codigos], dimensoes) → paralelo
        │
        ▼
Resposta sintetizada em linguagem natural
```

---

## Estrutura de arquivos

```
nexus-territorial-intelligence/
├── main.py                  # FastAPI app + MCP Server + todos os endpoints
├── config.py                # Pydantic Settings (lê .env)
├── requirements.txt
├── Dockerfile               # python:3.12-slim, USER nexus, CMD com $PORT
├── docker-compose.yml
├── railway.toml             # builder=dockerfile, healthcheck=/health
├── .env                     # NÃO commitado — ver .env.example
├── .env.example
├── .dockerignore
│
├── agents/
│   ├── router.py            # RouterAgent — GPT-4o + function-calling loop
│   ├── fiscal.py            # FiscalAgent — chama tools/transparencia.py
│   ├── territorial.py       # TerritorialAgent — chama tools/ibge.py
│   └── social.py            # SocialAgent — chama tools/datasus.py + inep.py
│
├── tools/
│   ├── ibge.py              # IBGE Localidades v1 + SIDRA v3
│   ├── transparencia.py     # Portal da Transparência API
│   ├── datasus.py           # DATASUS/CNES
│   └── inep.py              # INEP (links para XLSX)
│
├── frontend/
│   └── index.html           # SPA completa (Alpine.js + Tailwind + marked.js)
│
├── tests/
│   └── test_tools.py        # 17 testes de integração
│
└── docs/
    └── context/             # Este diretório — contexto vivo do projeto
```

---

## Decisões técnicas importantes

### Por que OpenAI SDK direto e não azure-ai-projects?
O SDK `azure-ai-projects` v2.2.0 mudou completamente a interface — `AIProjectClient.from_connection_string()` não existe mais. A nova versão só expõe `get_openai_client()`. Optamos por usar `openai.OpenAI(base_url=endpoint+"/openai/v1/", api_key=key)` diretamente, que funciona com ambos Azure AI Foundry e GitHub Models.

### Por que GitHub Models como fallback?
Azure free tier tem quota 0 em todas as regiões para GPT-4o. GitHub Models oferece GPT-4o gratuito via `https://models.inference.ai.azure.com` com a mesma interface OpenAI. Requer apenas um GitHub PAT sem escopos.

### Por que IBGE sem filtro por nome?
A API `servicodados.ibge.gov.br/api/v1/localidades/municipios?nome=X` não filtra — retorna todos os 5.570 municípios independente do parâmetro. A solução foi buscar a lista completa uma vez e filtrar localmente com match exato prioritário.

### Por que código IBGE de 7 dígitos como chave universal?
É o único identificador consistente entre Portal da Transparência, IBGE e DATASUS. Permite cruzar as três dimensões sem ambiguidade.

### Por que MCP + REST juntos?
MCP/SSE (`GET /sse` + `POST /messages`) permite que clientes AI (Claude, Copilot) consumam as ferramentas nativamente via protocolo padrão. REST (`POST /v1/*`) permite integração direta com qualquer sistema sem depender do protocolo MCP.

---

## Stack tecnológico

| Camada | Tecnologia | Versão |
|---|---|---|
| Runtime | Python | 3.12 |
| Framework | FastAPI | 0.115+ |
| Servidor | Uvicorn | 0.32+ |
| LLM | GPT-4o via OpenAI SDK | 1.55+ |
| Protocolo AI | MCP (Model Context Protocol) | 1.9+ |
| HTTP client | httpx | 0.28+ |
| Config | pydantic-settings | 2.7+ |
| Resiliência | tenacity | 9.0+ |
| Observabilidade | OpenTelemetry | 1.29+ |
| Frontend | Alpine.js + Tailwind CSS + marked.js | 3.14 / CDN / 12 |
| Container | Docker | - |
| Deploy | Railway | - |
| CI | GitHub Actions | - |
| Testes | pytest-asyncio | 17 testes |
