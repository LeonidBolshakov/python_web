@echo off
set "endpoint=%~1"
if "%endpoint%"=="" set "endpoint=operation"

curl -i -X POST http://localhost:8000/%endpoint% -H "Content-Type: application/json" -d @data.json