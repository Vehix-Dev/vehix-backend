#!/bin/sh
set -e

# wait for DB to be ready (simple loop) — requires netcat (nc)
if [ -n "$DATABASE_HOST" ]; then
  echo "Waiting for database at $DATABASE_HOST:$DATABASE_PORT..."
  COUNTER=0
  until nc -z $DATABASE_HOST ${DATABASE_PORT:-5432}; do
    COUNTER=$((COUNTER+1))
    if [ $COUNTER -gt 60 ]; then
      echo "Timed out waiting for database"
      break
    fi
    sleep 1
  done
fi

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput || true

exec "$@"
