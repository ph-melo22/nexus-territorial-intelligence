"""NEXUS — Demo end-to-end.

Executa três consultas reais contra os agentes e imprime os resultados
formatados em português. Ideal para gravação do vídeo de demo.

Uso:
    python demo.py
    python demo.py --ibge 3550308   # São Paulo
"""
import argparse
import asyncio
import json
import sys
from textwrap import indent

# ─────────────────────────────────────────────────────────────────────────────
# Municípios de exemplo (código IBGE 7 dígitos)
EXEMPLOS = {
    "campinas":  "3509502",
    "fortaleza": "2304400",
    "manaus":    "1302603",
    "recife":    "2611606",
    "curitiba":  "4106902",
    "sao_paulo": "3550308",
    "salvador":  "2927408",
    "belem":     "1501402",
}


def _fmt(data: dict, indent_: int = 2) -> str:
    return indent(json.dumps(data, ensure_ascii=False, indent=2, default=str), " " * indent_)


def _hr(title: str) -> None:
    print(f"\n{'-' * 60}")
    print(f"  {title}")
    print("-" * 60)


async def demo_territorial(ibge_code: str) -> dict:
    from agents.territorial import TerritorialAgent
    agent = TerritorialAgent()
    try:
        return await agent.run(codigo_ibge=ibge_code, consulta="Perfil demográfico e econômico")
    finally:
        await agent.aclose()


async def demo_fiscal(ibge_code: str) -> dict:
    from agents.fiscal import FiscalAgent
    agent = FiscalAgent()
    try:
        return await agent.run(
            codigo_ibge=ibge_code,
            ano=2024,
            consulta="Qual o total de transferências federais e benefícios sociais?",
        )
    finally:
        await agent.aclose()


async def demo_social(ibge_code: str) -> dict:
    from agents.social import SocialAgent
    agent = SocialAgent()
    try:
        return await agent.run(
            codigo_ibge=ibge_code,
            consulta="Quantos estabelecimentos de saúde e qual a situação educacional?",
        )
    finally:
        await agent.aclose()


async def demo_cruzamento(codigos: list[str]) -> dict:
    from agents.fiscal import FiscalAgent
    from agents.territorial import TerritorialAgent

    fiscal = FiscalAgent()
    territorial = TerritorialAgent()
    try:
        results = await asyncio.gather(
            *[territorial.run(codigo_ibge=c, consulta="comparação") for c in codigos],
            *[fiscal.run(codigo_ibge=c, consulta="comparação") for c in codigos],
            return_exceptions=True,
        )
        n = len(codigos)
        return {
            "territorial": {codigos[i]: results[i] for i in range(n)},
            "fiscal": {codigos[i]: results[n + i] for i in range(n)},
        }
    finally:
        await fiscal.aclose()
        await territorial.aclose()


async def main(ibge_code: str) -> None:
    print("\n" + "=" * 60)
    print("  NEXUS - Plataforma de Inteligencia Territorial")
    print("  Microsoft Agents League @ AI Skills Fest 2026")
    print("=" * 60)

    # ── Demo 1: Perfil Territorial ────────────────────────────────────────────
    _hr("DEMO 1 — Agente Territorial (IBGE)")
    print(f"Consultando município IBGE {ibge_code}…")
    t = await demo_territorial(ibge_code)
    m = t.get("municipio", {})
    p = t.get("populacao", {})
    pib = t.get("pib", {})
    print(f"\n  Município   : {m.get('nome')}/{m.get('estado')}")
    print(f"  Mesorregião : {m.get('mesorregiao')}")
    print(f"  Região      : {m.get('regiao')}")
    print(f"  Pop. 2022   : {int(p['populacao_censo_2022']):,} habitantes".replace(",", ".") if p.get("populacao_censo_2022") else "  Pop. 2022   : indisponível")
    if pib.get("pib_per_capita_reais"):
        print(f"  PIB/capita  : R$ {pib['pib_per_capita_reais']:,.2f} (2021)".replace(",", "X").replace(".", ",").replace("X", "."))
    print(f"\n  Fonte       : {t.get('fonte')}")

    # ── Demo 2: Perfil Fiscal ────────────────────────────────────────────────
    _hr("DEMO 2 — Agente Fiscal (Portal da Transparência)")
    print(f"Consultando dados fiscais de {m.get('nome', ibge_code)}…")
    f = await demo_fiscal(ibge_code)
    bf = f.get("bolsa_familia", {})
    tr = f.get("transferencias_federais", {})
    cv = f.get("convenios", {})
    if bf.get("beneficiarios"):
        print(f"  Bolsa Família (beneficiários) : {bf['beneficiarios']:,}".replace(",", "."))
        if bf.get("valor_total_reais"):
            print(f"  Bolsa Família (valor)        : R$ {float(bf['valor_total_reais']):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    else:
        print("  Bolsa Família : requer TRANSPARENCIA_API_KEY no .env")
    if tr.get("total_transferido_reais") and tr["total_transferido_reais"] > 0:
        print(f"  Transferências federais      : R$ {tr['total_transferido_reais']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    if cv.get("quantidade_convenios") is not None:
        print(f"  Convênios ativos             : {cv.get('quantidade_convenios')}")
    print(f"\n  Fonte       : {f.get('fonte')}")

    # ── Demo 3: Perfil Social ────────────────────────────────────────────────
    _hr("DEMO 3 — Agente Social (DATASUS + INEP)")
    print(f"Consultando saúde e educação de {m.get('nome', ibge_code)}…")
    s = await demo_social(ibge_code)
    est = s.get("saude", {}).get("estabelecimentos", {})
    ideb = s.get("educacao", {}).get("ideb", {})
    if est.get("total_estabelecimentos_amostra") is not None:
        print(f"  Estabelecimentos de saúde (amostra) : {est['total_estabelecimentos_amostra']}")
        print(f"  Com atendimento SUS                 : {est.get('com_atendimento_sus', '?')}")
        print(f"  Com internação hospitalar           : {est.get('com_internacao_hospitalar', '?')}")
        tipos = est.get("por_tipo", {})
        if tipos:
            print("  Por tipo:")
            for tipo, qtd in list(tipos.items())[:5]:
                print(f"    • {tipo}: {qtd}")
    if ideb.get("arquivos"):
        print(f"\n  IDEB disponível em {len(ideb['arquivos'])} arquivos INEP:")
        for arq in ideb["arquivos"][:2]:
            print(f"    • {arq['descricao']}")
    print(f"\n  Fontes      : {', '.join(s.get('fontes', []))}")

    # ── Demo 4: Cruzamento comparativo ───────────────────────────────────────
    _hr("DEMO 4 — Cruzamento: Fortaleza × Recife")
    print("Cruzando dimensões fiscal e territorial…")
    cr = await demo_cruzamento(["2304400", "2611606"])
    for codigo, nome in [("2304400", "Fortaleza/CE"), ("2611606", "Recife/PE")]:
        ter = cr["territorial"].get(codigo, {})
        fis = cr["fiscal"].get(codigo, {})
        pop_raw = ter.get("populacao", {}).get("populacao_censo_2022")
        pib_val = ter.get("pib", {}).get("pib_per_capita_reais")
        print(f"\n  {nome}")
        if pop_raw:
            print(f"    Pop. 2022      : {int(pop_raw):,} hab".replace(",", "."))
        if pib_val:
            print(f"    PIB/capita     : R$ {pib_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        bf_val = fis.get("bolsa_familia", {}).get("beneficiarios")
        if bf_val:
            print(f"    BF beneficiários: {bf_val:,}".replace(",", "."))

    print("\n" + "=" * 60)
    print("  NEXUS demo concluido.")
    print("  Para consultas em linguagem natural: POST /v1/query")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NEXUS demo end-to-end")
    parser.add_argument("--ibge", default="3509502", help="Código IBGE 7 dígitos (padrão: Campinas/SP)")
    parser.add_argument(
        "--municipio",
        choices=list(EXEMPLOS.keys()),
        help="Município pré-definido (substitui --ibge)",
    )
    args = parser.parse_args()
    ibge = EXEMPLOS[args.municipio] if args.municipio else args.ibge
    asyncio.run(main(ibge))
