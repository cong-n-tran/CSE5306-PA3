FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY layered ./layered
COPY .env.example .env
CMD ["sh", "-c", "uvicorn layered.main:app --host 0.0.0.0 --port ${HTTP_PORT:-8101}"]
