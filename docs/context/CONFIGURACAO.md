# Configuração do NEXUS

**Última atualização:** 2026-06-10

> ⚠️ Este arquivo NÃO contém secrets. Para os valores reais, ver o `.env` local ou as variáveis do Railway.

---

## Variáveis de ambiente (sem valores sensíveis)

| Variável | Descrição | Onde configurar |
|---|---|---|
| `AZURE_AI_PROJECT_ENDPOINT` | Endpoint do projeto Azure AI Foundry | Railway + .env |
| `AZURE_AI_API_KEY` | Chave de API do Azure AI Foundry | Railway + .env |
| `AZURE_OPENAI_DEPLOYMENT` | Nome do deployment GPT-4o no Azure | `gpt-4o` |
| `GITHUB_TOKEN` | PAT do GitHub para GitHub Models (fallback LLM) | Railway + .env |
| `GITHUB_MODEL` | Modelo a usar no GitHub Models | `gpt-4o` |
| `TRANSPARENCIA_API_KEY` | Chave da API do Portal da Transparência | Railway + .env |
| `PORT` | Porta do servidor | `8000` (Railway) |
| `LOG_LEVEL` | Nível de log | `INFO` |
| `DEBUG` | Modo debug | `false` |
| `OTLP_ENDPOINT` | Endpoint OpenTelemetry (opcional) | vazio |
| `OTEL_SERVICE_NAME` | Nome do serviço no trace | `nexus-mcp` |

---

## Serviços externos

| Serviço | URL | Auth | Status |
|---|---|---|---|
| Azure AI Foundry | `nexus-intelligence-resource.services.ai.azure.com` | API Key | Configurado, sem quota |
| GitHub Models | `models.inference.ai.azure.com` | GitHub PAT | **Ativo** (LLM principal) |
| Portal da Transparência | `api.portaldatransparencia.gov.br/api-de-dados` | API Key | Ativo (Bolsa Família ✅, transferências ⚠️) |
| IBGE Localidades | `servicodados.ibge.gov.br/api/v1` | Nenhuma | ✅ Ativo |
| IBGE SIDRA | `servicodados.ibge.gov.br/api/v3` | Nenhuma | ✅ Ativo |
| DATASUS/CNES | `apidadosabertos.saude.gov.br/v1/cnes` | Nenhuma | ✅ Parcial |
| INEP Open Data | `download.inep.gov.br` | Nenhuma | ✅ Links XLSX |

---

## URLs do projeto

| Ambiente | URL |
|---|---|
| **Produção (Railway)** | https://nexus-territorial-intelligence-production.up.railway.app |
| Swagger/Docs | https://nexus-territorial-intelligence-production.up.railway.app/docs |
| Health | https://nexus-territorial-intelligence-production.up.railway.app/health |
| GitHub | https://github.com/ph-melo22/nexus-territorial-intelligence |

---

## Contas e identificadores

| Plataforma | Identificador |
|---|---|
| GitHub | `ph-melo22` |
| Microsoft Learn | `pedrohenriquemelodossantos-2263` |
| Railway | Projeto `selfless-playfulness` / serviço `nexus-territorial-intelligence` |
| Azure | Projeto `nexus-intelligence` / Resource `nexus-intelligence-resource` |
| Innovation Studio | Conta registrada — projeto criado no Agents League Hackathon |

---

## Segredos que precisam ser rotacionados

- `AZURE_AI_API_KEY` — foi exposta no histórico de chat. **Regenerar no portal Azure.**
- `GITHUB_TOKEN` — foi exposta no histórico de chat. Expira ~setembro 2026. Regenerar se necessário.
