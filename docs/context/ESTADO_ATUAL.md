# Estado Atual do Projeto

**Última atualização:** 2026-06-10

---

## ✅ O que está feito e funcionando

### Backend
- FastAPI MCP Server com SSE transport
- 4 endpoints REST: `/v1/buscar_fiscal`, `/v1/buscar_territorial`, `/v1/buscar_social`, `/v1/cruzar_dados`
- Endpoint de linguagem natural: `POST /v1/query`
- Endpoint de busca de municípios: `GET /v1/municipios/buscar`
- Health check: `GET /health`
- Swagger automático: `GET /docs`

### Agentes
- **Router Agent** — recebe pergunta em linguagem natural, orquestra os demais via GPT-4o function-calling (loop de até 8 turnos)
- **Fiscal Agent** — Bolsa Família, transferências federais, convênios (Portal da Transparência)
- **Territorial Agent** — população Censo 2022, PIB per capita, perfil geográfico (IBGE)
- **Social Agent** — estabelecimentos de saúde CNES, links IDEB/INEP (DATASUS)

### LLM
- **Prioridade 1:** Azure AI Foundry (endpoint configurado, sem quota disponível no momento)
- **Prioridade 2 (ativo):** GitHub Models — GPT-4o via `https://models.inference.ai.azure.com`
- Fallback final: `_direct_dispatch` (sem LLM, só dados brutos)

### Correções importantes já feitas
- IBGE `_resolve_municipio`: busca lista completa e filtra localmente (API não suporta `?nome=`)
- Endpoint Bolsa Família: `novo-bolsa-familia-por-municipio` com parâmetro `mesAno`
- HTTP 400 tratado graciosamente no Portal da Transparência
- Cascade Azure → GitHub Models → direct dispatch sem quebrar

### Frontend (Alpine.js + Tailwind CSS)
- 4 abas: Consultar, Comparar, HUB, Sobre
- Modo "Por Município" + modo "Pergunta Livre" (Router Agent)
- Busca de municípios com autocomplete (API interna)
- Visualização de agentes em ação com animação
- Comparação lado a lado de 2 municípios
- **Markdown rendering** nas respostas do GPT-4o (marked.js)
- Timeouts em todas as chamadas (45s por agente, 90s query livre)
- Branding: Azure AI Foundry (corrigido — era "Azure AI Agent Service")

### Infraestrutura
- Docker + docker-compose
- `.dockerignore` protege `.env`
- `railway.toml` com health check
- CI via GitHub Actions (`.github/workflows/`)
- 17 testes de integração com pytest-asyncio
- OpenTelemetry tracing em todos os spans
- LICENSE MIT

### Deploy
- **Railway:** https://nexus-territorial-intelligence-production.up.railway.app ✅ ONLINE
- **GitHub:** https://github.com/ph-melo22/nexus-territorial-intelligence ✅ PÚBLICO

---

## ❌ O que falta

| Item | Prioridade | Responsável |
|---|---|---|
| Vídeo demo 5 min no YouTube | **CRÍTICO** | Pedro (gravar) |
| Adicionar link do vídeo na submissão Innovation Studio | Bloqueado pelo vídeo | Pedro |
| Postar no Discord do hackathon (10% do score = votos) | Alta | Pedro |
| Azure Container Apps deploy (opcional — mais impressiona juízes MS) | Média | Ambos |
| Quota Azure GPT-4o (opcional — hoje usa GitHub Models) | Média | Pedro (upgrade conta) |

---

## ⚠️ Alertas

- A `AZURE_AI_API_KEY` que estava no `.env` foi exposta no chat. **Regenerar no portal Azure antes do deploy final.**
- `GITHUB_TOKEN` exposto no chat. Expira em 90 dias (setembro 2026). Regenerar se necessário.
- O projeto usa GitHub Models como LLM principal (Azure sem quota). Os juízes podem não notar, mas tecnicamente não é Azure AI nativo.
- `OTLP_ENDPOINT` deve ficar vazio no Railway (não tem coletor configurado).

---

## 📊 Dados que funcionam vs. não funcionam

| Fonte | Status | Observação |
|---|---|---|
| IBGE Localidades | ✅ | Busca local na lista completa |
| IBGE SIDRA (população, PIB) | ✅ | Censo 2022 + PIB 2021 |
| Portal da Transparência — Bolsa Família | ✅ | `novo-bolsa-familia-por-municipio` |
| Portal da Transparência — Transferências | ⚠️ 403 | Endpoint requer tier pago |
| Portal da Transparência — Convênios | ⚠️ 400 | Parâmetros não documentados |
| DATASUS/CNES | ✅ parcial | Amostra de 100 estabelecimentos |
| INEP | ✅ | Links para arquivos XLSX |
