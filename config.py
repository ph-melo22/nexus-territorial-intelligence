from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Azure AI Foundry (Nova Fábrica — endpoint + key)
    AZURE_AI_PROJECT_ENDPOINT: str = ""
    AZURE_AI_API_KEY: str = ""
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4o"

    # GitHub Models fallback (free, same OpenAI API format)
    GITHUB_TOKEN: str = ""
    GITHUB_MODEL: str = "gpt-4o"

    # Legacy — kept for backwards compat, unused when endpoint is set
    AZURE_AI_PROJECT_CONNECTION_STRING: str = ""

    # Portal da Transparência
    # Free key: https://portaldatransparencia.gov.br/api-de-dados/cadastrar-email
    TRANSPARENCIA_API_KEY: str = ""
    TRANSPARENCIA_BASE_URL: str = "https://api.portaldatransparencia.gov.br/api-de-dados"

    # IBGE (no auth required)
    IBGE_BASE_URL: str = "https://servicodados.ibge.gov.br/api"

    # Ministério da Saúde open data (DATASUS)
    SAUDE_BASE_URL: str = "https://apidadosabertos.saude.gov.br"
    OPENDATASUS_CKAN_URL: str = "https://opendatasus.saude.gov.br/api/3/action"

    # OpenTelemetry
    OTLP_ENDPOINT: str = ""
    OTEL_SERVICE_NAME: str = "nexus-mcp"

    # HTTP client
    HTTP_TIMEOUT: float = 30.0
    HTTP_MAX_RETRIES: int = 3


settings = Settings()
