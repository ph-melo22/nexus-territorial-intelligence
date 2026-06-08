.PHONY: run dev test demo docker-up docker-down install lint

# ── Desenvolvimento ────────────────────────────────────────────────────────────
run:
	uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2

dev:
	uvicorn main:app --reload --port 8000 --log-level debug

install:
	pip install -r requirements.txt

# ── Testes ─────────────────────────────────────────────────────────────────────
test:
	python -m pytest tests/ -v

test-fast:
	python -m pytest tests/ -v -k "not agente"

# ── Demo ───────────────────────────────────────────────────────────────────────
demo:
	python demo.py --municipio campinas

demo-fortaleza:
	python demo.py --municipio fortaleza

# ── Docker ─────────────────────────────────────────────────────────────────────
docker-up:
	docker-compose up --build -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f nexus

# ── Utilitários ────────────────────────────────────────────────────────────────
health:
	curl -s http://localhost:8000/health | python -m json.tool

tools:
	curl -s http://localhost:8000/tools | python -m json.tool
