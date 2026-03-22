# Регрессия: путь tool_requests от «ответа LLM» (без force_tool_data_access на первом раунде).
# Мокирует GigaChat; реальные ключи не нужны.
# Запуск из корня репозитория: .\scripts\run_llm_tool_initiative_test.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
uv run pytest tests/backend/test_orchestrator_llm_tool_initiative.py -v --tb=short
