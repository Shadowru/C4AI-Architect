FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей для компиляции
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

ENTRYPOINT ["python", "src/orchestrator.py"]