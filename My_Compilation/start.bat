@echo off
title PROJECT ARJUNA - Integration Test Server (Member 1 + 3)
cd /d "%~dp0"
echo ==========================================================================
echo   PROJECT ARJUNA (SIH 26170): INTEGRATION TEST SERVER (MEMBER 1 + MEMBER 3)
echo ==========================================================================
python run_integration.py
pause
