@echo off
setlocal
rem NovelOS SQLite MCP launcher (Windows / DSH).
rem Prefer project .venv, otherwise fall back to python on PATH.
cd /d "%~dp0.."

set "PYTHON_CMD="
if exist ".venv\Scripts\python.exe" set "PYTHON_CMD=.venv\Scripts\python.exe"
if not defined PYTHON_CMD (
  where python >nul 2>nul
  if errorlevel 1 (
    echo run_sqlite_mcp: python not found on PATH >&2
    exit /b 1
  )
  set "PYTHON_CMD=python"
)

"%PYTHON_CMD%" "mcp\sqlite-mcp\server.py" --db-path "data\novelos-v2.db"
exit /b %errorlevel%
