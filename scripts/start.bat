@echo off
cd /d "%~dp0\.."
docker compose up --build -d
echo App running at http://localhost:8000
