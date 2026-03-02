@echo off
echo Starting Jambo Park Development Environment...

REM Check if Redis is running (optional check, or just try to start it)
REM Assuming redis-server is in PATH or standard location. 
REM If using Docker, you might use 'docker-compose up -d redis'
echo Starting Redis...
start "Redis Server" redis-server

REM Wait a moment for Redis to start
timeout /t 3

echo Starting Celery Worker...
REM using gevent pool for Windows compatibility
start "Celery Worker" python -m celery -A config worker --loglevel=info -P gevent

echo Starting Ngrok Tunnel...
start "Ngrok Tunnel" ngrok http --domain=curtis-unmobilized-clarence.ngrok-free.dev 8000

echo Starting Django Server...
python manage.py runserver

pause