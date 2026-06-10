FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Non-root user
RUN useradd -m nexus && chown -R nexus:nexus /app
USER nexus

EXPOSE 8000

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2
