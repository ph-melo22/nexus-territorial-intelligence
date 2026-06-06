"""Integration smoke tests — hit live government APIs.

Run with:
    python -m pytest tests/ -v

Requires internet. No API keys needed (IBGE + CNES only).
"""
import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio

IBGE_CAMPINAS  = "3509502"   # Campinas/SP
IBGE_FORTALEZA = "2304400"   # Fortaleza/CE
IBGE_OIAPOQUE  = "1600501"   # Oiapoque/AP — pequeno município remoto


# ── IBGE ──────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def ibge():
    from tools.ibge import IBGEClient
    client = IBGEClient()
    yield client
    await client.aclose()


async def test_ibge_municipio_campinas(ibge):
    result = await ibge.get_municipio(IBGE_CAMPINAS)
    assert result["nome"] == "Campinas"
    assert result["estado"] == "SP"
    assert result["regiao"] == "SE"


async def test_ibge_municipio_fortaleza(ibge):
    result = await ibge.get_municipio(IBGE_FORTALEZA)
    assert result["nome"] == "Fortaleza"
    assert result["estado"] == "CE"


async def test_ibge_populacao_censo_2022(ibge):
    result = await ibge.get_populacao(IBGE_CAMPINAS)
    pop = result.get("populacao_censo_2022")
    assert pop is not None, "Censo 2022 population should be available"
    assert int(pop) > 1_000_000, f"Campinas pop should be >1M, got {pop}"


async def test_ibge_pib_per_capita(ibge):
    result = await ibge.get_pib(IBGE_CAMPINAS)
    pib = result.get("pib_per_capita_reais")
    assert pib is not None, "PIB per capita should be available"
    # Campinas 2021 ≈ R$ 72.947
    assert 20_000 < float(pib) < 500_000, f"PIB per capita out of range: {pib}"


async def test_ibge_perfil_completo_keys(ibge):
    result = await ibge.get_perfil_completo(IBGE_CAMPINAS)
    assert "municipio" in result
    assert "populacao" in result
    assert "pib" in result
    assert result["codigo_ibge"] == IBGE_CAMPINAS


async def test_ibge_municipio_pequeno(ibge):
    result = await ibge.get_municipio(IBGE_OIAPOQUE)
    assert result.get("nome") == "Oiapoque"
    assert result.get("estado") == "AP"


# ── Portal da Transparência ───────────────────────────────────────────────────

@pytest_asyncio.fixture
async def transparencia():
    from tools.transparencia import TransparenciaClient
    client = TransparenciaClient()
    yield client
    await client.aclose()


async def test_transparencia_perfil_retorna_dict(transparencia):
    result = await transparencia.get_perfil_fiscal(IBGE_CAMPINAS, 2024)
    assert isinstance(result, dict)
    assert "bolsa_familia" in result
    assert "transferencias_federais" in result
    assert "convenios" in result


async def test_transparencia_bolsa_familia_estrutura(transparencia):
    result = await transparencia.get_bolsa_familia(IBGE_CAMPINAS, 2024, 1)
    assert isinstance(result, dict)
    assert "beneficiarios" in result
    assert "mes_ano" in result


# ── DATASUS / CNES ────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def datasus():
    from tools.datasus import DatasusClient
    client = DatasusClient()
    yield client
    await client.aclose()


async def test_cnes_estabelecimentos_retorna_dict(datasus):
    result = await datasus.get_estabelecimentos(IBGE_FORTALEZA)
    assert isinstance(result, dict)
    assert "total_estabelecimentos_amostra" in result
    assert "fonte" in result


async def test_cnes_estabelecimentos_contagem_positiva(datasus):
    result = await datasus.get_estabelecimentos(IBGE_FORTALEZA)
    total = result.get("total_estabelecimentos_amostra")
    assert total is not None and total > 0, f"Esperado >0 estabelecimentos, obteve {total}"


async def test_cnes_perfil_saude_keys(datasus):
    result = await datasus.get_perfil_saude(IBGE_FORTALEZA, "Fortaleza")
    assert "estabelecimentos" in result
    assert "codigo_ibge" in result


# ── INEP ──────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def inep():
    from tools.inep import INEPClient
    client = INEPClient()
    yield client
    await client.aclose()


async def test_inep_ideb_tem_arquivos(inep):
    result = await inep.get_ideb_info(IBGE_CAMPINAS)
    assert "arquivos" in result
    assert len(result["arquivos"]) >= 3


async def test_inep_codigo_ibge_6_digitos(inep):
    result = await inep.get_ideb_info(IBGE_CAMPINAS)
    assert result["codigo_ibge_6"] == IBGE_CAMPINAS[:6]


async def test_inep_perfil_educacao_keys(inep):
    result = await inep.get_perfil_educacao(IBGE_CAMPINAS)
    assert "ideb" in result
    assert "codigo_ibge" in result


# ── Agentes ───────────────────────────────────────────────────────────────────

async def test_agente_territorial():
    from agents.territorial import TerritorialAgent
    agent = TerritorialAgent()
    try:
        result = await agent.run(codigo_ibge=IBGE_CAMPINAS)
        assert result["dimensao"] == "territorial"
        assert result["municipio"]["nome"] == "Campinas"
    finally:
        await agent.aclose()


async def test_agente_fiscal_sem_chave():
    from agents.fiscal import FiscalAgent
    agent = FiscalAgent()
    try:
        result = await agent.run(codigo_ibge=IBGE_CAMPINAS)
        assert result["dimensao"] == "fiscal"
        assert "bolsa_familia" in result
    finally:
        await agent.aclose()


async def test_agente_social():
    from agents.social import SocialAgent
    agent = SocialAgent()
    try:
        result = await agent.run(codigo_ibge=IBGE_FORTALEZA)
        assert result["dimensao"] == "social"
        assert "saude" in result
        assert "educacao" in result
    finally:
        await agent.aclose()
