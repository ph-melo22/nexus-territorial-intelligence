# Roteiro — Vídeo Demo NEXUS (5 minutos)

**Última atualização:** 2026-06-10

> Gravar com OBS, Loom ou qualquer software de captura de tela.
> Mostrar o browser com o frontend aberto em `https://nexus-territorial-intelligence-production.up.railway.app`

---

## Estrutura (5 min)

| Bloco | Tempo | O que fazer |
|---|---|---|
| Abertura + problema | 0:00 – 0:45 | Falar sobre o problema, mostrar a tela inicial |
| Demo 1: consulta simples | 0:45 – 2:00 | Buscar um município, mostrar os 3 agentes |
| Demo 2: pergunta livre | 2:00 – 3:15 | Fazer uma pergunta comparativa via Router Agent |
| Demo 3: comparação | 3:15 – 4:00 | Comparar 2 municípios lado a lado |
| Arquitetura + encerramento | 4:00 – 5:00 | Mostrar aba HUB, GitHub, encerrar |

---

## Roteiro detalhado

### 0:00 – 0:45 | Abertura e Problema

**Falar:**
> "O Brasil tem 5.570 municípios. O governo federal transfere mais de 1 trilhão de reais por ano em programas sociais, convênios e transferências diretas. Os dados são públicos — mas estão espalhados em portais diferentes: Portal da Transparência, IBGE, DATASUS, INEP. Um gestor público que quer tomar uma decisão informada precisa navegar quatro portais, baixar planilhas, cruzar códigos manualmente. O NEXUS resolve isso."

**Mostrar:** Tela inicial do produto. Apontar para o hero.

---

### 0:45 – 2:00 | Demo 1 — Consulta por Município

**Falar:**
> "Com o NEXUS, basta digitar o nome do município."

**Fazer:**
1. No campo "Por Município", digitar `Fortaleza`
2. Selecionar `Fortaleza / Ceará` no autocomplete
3. Clicar em **Consultar →**
4. Mostrar a animação dos 3 agentes rodando em paralelo
5. Quando os cards aparecerem, destacar:
   - **Territorial:** "Aqui vemos a população do Censo 2022 e o PIB per capita direto do IBGE"
   - **Fiscal:** "Aqui o número de beneficiários do Bolsa Família e o valor total transferido, direto do Portal da Transparência"
   - **Social:** "E aqui os estabelecimentos de saúde cadastrados no DATASUS/CNES"

**Falar:**
> "Três agentes especializados consultando APIs reais do governo em paralelo, em segundos."

---

### 2:00 – 3:15 | Demo 2 — Pergunta Livre (Router Agent)

**Falar:**
> "Mas o diferencial do NEXUS está aqui — a pergunta livre. Posso fazer uma pergunta complexa em linguagem natural."

**Fazer:**
1. Clicar na aba **🤖 Pergunta Livre**
2. Clicar no exemplo: *"Compare Fortaleza e Manaus: população, Bolsa Família e estabelecimentos de saúde."*
3. Clicar em **Perguntar →**
4. Mostrar o loading "Router Agent processando…"
5. Quando a resposta aparecer, destacar o **markdown formatado** com os dados comparativos

**Falar:**
> "O Router Agent — usando GPT-4o via Azure AI Foundry — decompõe a pergunta, decide quais dados buscar, chama os agentes certos e sintetiza tudo em uma resposta estruturada. Raciocínio em múltiplos passos, dados reais."

---

### 3:15 – 4:00 | Demo 3 — Comparação

**Fazer:**
1. Clicar na aba **Comparar**
2. Selecionar **Campinas/SP** e **Curitiba/PR**
3. Clicar em **Comparar →**
4. Mostrar a tabela com os 3 blocos (Territorial, Fiscal, Social)
5. Destacar a **análise comparativa automática** no topo (a síntese calculada)

**Falar:**
> "E aqui comparamos dois municípios lado a lado — população, PIB per capita, Bolsa Família, estabelecimentos de saúde — tudo em uma tabela unificada."

---

### 4:00 – 5:00 | Arquitetura e Encerramento

**Fazer:**
1. Clicar na aba **HUB**
2. Mostrar o diagrama de orquestração (Router → 3 agentes → fontes)
3. Mostrar a tabela de fontes de dados
4. Abrir rapidamente o GitHub: `github.com/ph-melo22/nexus-territorial-intelligence`
5. Mostrar o README com o diagrama ASCII

**Falar:**
> "O NEXUS é open source, deployado com Docker no Railway, com MCP Server para integração com qualquer cliente de IA — Claude, Copilot, agentes customizados. Código IBGE de 7 dígitos como chave universal conectando as três dimensões. 5.570 municípios brasileiros acessíveis em linguagem natural."
>
> "Dados públicos que existem. Inteligência que faltava."

---

## Dicas de gravação

- Usar resolução 1920x1080
- Deixar o browser em fullscreen ou maximizado
- Falar devagar e claro — os juízes são internacionais
- Se quiser, pode gravar em inglês (o produto responde em português mas o vídeo pode ser em inglês)
- Subir no YouTube como **Não listado** (link privado) ou **Público**
- Copiar o link e adicionar na submissão do Innovation Studio
