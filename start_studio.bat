@echo off
title AI Tech Broadcaster - Executive Management Studio
color 0B
echo ==============================================================================
echo   STARTING AI TECH BROADCASTER — EXECUTIVE MANAGEMENT STUDIO
echo ==============================================================================
echo.
echo Launching local Studio Web Server and opening browser...
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Running uv setup...
    uv venv .venv
    uv pip install -r requirements.txt --python .venv\Scripts\python.exe
)

.venv\Scripts\python.exe manage.py studio --port 8080
pause
