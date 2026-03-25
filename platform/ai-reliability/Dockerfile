FROM python:3.12-slim

RUN groupadd --gid 10001 ai-reliability \
    && useradd --uid 10001 --gid 10001 --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin ai-reliability \
    && mkdir -p /app /tmp \
    && chown -R 10001:10001 /app /tmp

WORKDIR /app

COPY app/engine.py /app/engine.py
COPY app/server.py /app/server.py
COPY app/tracing.py /app/tracing.py

ENV PORT=8080
ENV PYTHONDONTWRITEBYTECODE=1

USER 10001:10001

EXPOSE 8080

CMD ["python", "/app/server.py"]
