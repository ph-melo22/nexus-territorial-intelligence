"""Portal da Transparência API client — transfers, Bolsa Família, procurement.

Endpoints: https://api.portaldatransparencia.gov.br/api-de-dados
Free API key: https://portaldatransparencia.gov.br/api-de-dados/cadastrar-email
"""
import asyncio
import logging
from datetime import date
from typing import Any

import httpx
from opentelemetry import trace
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class TransparenciaClient:
    def __init__(self) -> None:
        headers = {"Accept": "application/json"}
        if settings.TRANSPARENCIA_API_KEY:
            headers["chave-api-dados"] = settings.TRANSPARENCIA_API_KEY
        self._http = httpx.AsyncClient(
            base_url=settings.TRANSPARENCIA_BASE_URL,
            timeout=settings.HTTP_TIMEOUT,
            headers=headers,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def _get(self, path: str, **params) -> Any:
        params = {k: v for k, v in params.items() if v is not None}
        resp = await self._http.get(path, params=params)
        if resp.status_code in (400, 401, 403):
            logger.warning(f"Portal da Transparência: HTTP {resp.status_code} on {path}")
            return []
        resp.raise_for_status()
        return resp.json()

    # ── Bolsa Família ─────────────────────────────────────────────────────────

    async def get_bolsa_familia(
        self, ibge_code: str, ano: int = 2024, mes: int = 1
    ) -> dict:
        """Bolsa Família beneficiaries and total value for a municipality."""
        with tracer.start_as_current_span("transparencia.bolsa_familia") as span:
            span.set_attribute("ibge.code", ibge_code)
            mes_ano = f"{ano}{mes:02d}"
            data = await self._get(
                "/novo-bolsa-familia-por-municipio",
                mesAno=mes_ano,
                codigoIbge=ibge_code,
                pagina=1,
            )
            if not data:
                return {"beneficiarios": None, "valor_total_reais": None, "mes_ano": mes_ano}

            # API returns a list; we want the first (and usually only) entry
            entry = data[0] if isinstance(data, list) else data
            return {
                "beneficiarios": entry.get("quantidadeBeneficiados"),
                "valor_total_reais": entry.get("valor"),
                "mes_ano": mes_ano,
                "municipio": entry.get("municipio", {}).get("nomeIBGE"),
                "fonte": "Portal da Transparência — Bolsa Família",
            }

    # ── Transferências Constitucionais ────────────────────────────────────────

    async def get_transferencias(self, ibge_code: str, ano: int = 2024) -> dict:
        """FPM, SUS, FUNDEB and other federal transfers to the municipality."""
        with tracer.start_as_current_span("transparencia.transferencias") as span:
            span.set_attribute("ibge.code", ibge_code)
            # Endpoint paginated — grab first two pages for overview
            pages = await asyncio.gather(
                self._get(
                    "/transferencias/municipios",
                    codigoMunicipio=ibge_code,
                    ano=ano,
                    pagina=1,
                ),
                self._get(
                    "/transferencias/municipios",
                    codigoMunicipio=ibge_code,
                    ano=ano,
                    pagina=2,
                ),
                return_exceptions=True,
            )

            registros = []
            for page in pages:
                if isinstance(page, list):
                    registros.extend(page)

            total = sum(r.get("valor", 0) or 0 for r in registros)
            tipos = list({r.get("tipoTransferencia", {}).get("nome", "") for r in registros if r.get("tipoTransferencia")})

            return {
                "total_transferido_reais": total,
                "quantidade_registros": len(registros),
                "tipos_transferencia": tipos,
                "ano": ano,
                "fonte": "Portal da Transparência — Transferências",
            }

    # ── Contratos / Convênios ─────────────────────────────────────────────────

    async def get_convenios(self, ibge_code: str, ano: int = 2024) -> dict:
        """Federal grants (convênios/transferências especiais) for the municipality."""
        with tracer.start_as_current_span("transparencia.convenios") as span:
            span.set_attribute("ibge.code", ibge_code)
            data = await self._get(
                "/convenios",
                codigoMunicipioProponente=ibge_code,
                dataInicioVigencia=f"{ano}-01-01",
                dataFimVigencia=f"{ano}-12-31",
                pagina=1,
            )
            registros = data if isinstance(data, list) else []
            total_valor = sum(r.get("valorGlobal", 0) or 0 for r in registros)

            return {
                "quantidade_convenios": len(registros),
                "valor_total_reais": total_valor,
                "ano": ano,
                "convenios": [
                    {
                        "numero": r.get("numero"),
                        "objeto": r.get("objeto"),
                        "valor": r.get("valorGlobal"),
                        "orgao_concedente": r.get("orgaoConcedente", {}).get("nome"),
                        "situacao": r.get("situacao"),
                    }
                    for r in registros[:10]  # top 10 for context
                ],
                "fonte": "Portal da Transparência — Convênios",
            }

    # ── Licitações ────────────────────────────────────────────────────────────

    async def get_licitacoes(self, ibge_code: str, ano: int = 2024) -> dict:
        """Public procurement notices linked to the municipality."""
        with tracer.start_as_current_span("transparencia.licitacoes") as span:
            span.set_attribute("ibge.code", ibge_code)
            data = await self._get(
                "/licitacoes",
                codigoMunicipio=ibge_code,
                dataInicio=f"{ano}-01-01",
                dataFim=f"{ano}-12-31",
                pagina=1,
            )
            registros = data if isinstance(data, list) else []
            return {
                "quantidade_licitacoes": len(registros),
                "ano": ano,
                "fonte": "Portal da Transparência — Licitações",
            }

    # ── Emendas Parlamentares ─────────────────────────────────────────────────

    async def get_emendas(self, ibge_code: str, ano: int = 2024) -> dict:
        """Parliamentary amendments (emendas) directed to the municipality."""
        with tracer.start_as_current_span("transparencia.emendas") as span:
            span.set_attribute("ibge.code", ibge_code)
            data = await self._get(
                "/emendas",
                codigoMunicipio=ibge_code,
                ano=ano,
                pagina=1,
            )
            registros = data if isinstance(data, list) else []
            valor_pago = sum(
                float(str(r.get("valorPago", "0") or "0").replace(",", "."))
                for r in registros
            )
            valor_empenhado = sum(
                float(str(r.get("valorEmpenhado", "0") or "0").replace(",", "."))
                for r in registros
            )
            return {
                "quantidade_emendas": len(registros),
                "valor_pago_reais": round(valor_pago, 2),
                "valor_empenhado_reais": round(valor_empenhado, 2),
                "ano": ano,
                "emendas": [
                    {
                        "autor": r.get("nomeAutor"),
                        "tipo": r.get("tipoEmenda"),
                        "funcao": r.get("funcao"),
                        "valor_pago": r.get("valorPago"),
                    }
                    for r in registros[:5]
                ],
                "fonte": "Portal da Transparência — Emendas Parlamentares",
            }

    # ── Composite ─────────────────────────────────────────────────────────────

    async def get_perfil_fiscal(self, ibge_code: str, ano: int = 2024) -> dict:
        """All fiscal indicators fetched concurrently."""
        with tracer.start_as_current_span("transparencia.perfil_fiscal") as span:
            span.set_attribute("ibge.code", ibge_code)
            mes = 12 if ano < date.today().year else date.today().month - 1 or 1
            bf, transferencias, convenios, emendas = await asyncio.gather(
                self.get_bolsa_familia(ibge_code, ano, mes),
                self.get_transferencias(ibge_code, ano),
                self.get_convenios(ibge_code, ano),
                self.get_emendas(ibge_code, ano),
                return_exceptions=True,
            )
            return {
                "codigo_ibge": ibge_code,
                "ano": ano,
                "bolsa_familia": bf if not isinstance(bf, Exception) else {"erro": str(bf)},
                "transferencias_federais": transferencias if not isinstance(transferencias, Exception) else {"aviso": "Endpoint requer acesso premium na API da Transparência", "total_transferido_reais": 0},
                "convenios": convenios if not isinstance(convenios, Exception) else {"aviso": "Parâmetros não suportados neste tier da API", "quantidade_convenios": 0},
                "emendas_parlamentares": emendas if not isinstance(emendas, Exception) else {"erro": str(emendas)},
                "fonte": "Portal da Transparência",
                "url_api": "https://api.portaldatransparencia.gov.br/api-de-dados",
            }
