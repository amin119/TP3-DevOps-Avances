# syntax=docker/dockerfile:1
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
# Le secret optionnel "extraca" permet d'ajouter une CA (proxy / antivirus TLS) au build
RUN --mount=type=secret,id=extraca \
    if [ -s /run/secrets/extraca ]; then \
      cat /etc/ssl/certs/ca-certificates.crt /run/secrets/extraca > /tmp/ca.pem; export PIP_CERT=/tmp/ca.pem; \
    fi; \
    pip install --no-cache-dir -r requirements.txt
COPY main.py .
EXPOSE 8000
# Un seul worker uvicorn (asyncio) : suffisant pour 150 RPS
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
