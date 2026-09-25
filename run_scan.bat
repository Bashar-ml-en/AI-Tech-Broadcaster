@echo off
title AI Tech Broadcaster - Trigger Scan
color 0A
echo ==============================================================================
echo   AI TECH BROADCASTER — EXECUTING IMMEDIATE BROADCAST CYCLE
echo ==============================================================================
echo.
.venv\Scripts\python.exe manage.py scan
echo.
pause
