FROM python:3.12-slim

WORKDIR /app

COPY app/engine.py /app/engine.py
COPY app/server.py /app/server.py
COPY app/tracing.py /app/tracing.py

ENV PORT=8080
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

CMD ["python", "/app/server.py"]
