FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY twophase.proto .
RUN python -m grpc_tools.protoc -I. --python_out=. --pyi_out=. --grpc_python_out=. twophase.proto

COPY services ./services
COPY .env.example .env
