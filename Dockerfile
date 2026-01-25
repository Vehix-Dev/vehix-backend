FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# install system deps
RUN apt-get update && apt-get install -y build-essential libpq-dev gcc curl && rm -rf /var/lib/apt/lists/*

# copy and install python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install --no-cache-dir -r /app/requirements.txt

# copy project
COPY . /app

RUN chmod +x /app/entrypoint.sh || true
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
