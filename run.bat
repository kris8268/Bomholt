@echo off
REM ============================================================
REM  job_mail_planner — kør denne via Windows Task Scheduler
REM  Ret stien nedenfor til din faktiske installationsmappe
REM ============================================================

set PROJECT_DIR=C:\job_mail_planner

cd /d "%PROJECT_DIR%"

REM Aktiver venv hvis du bruger et (anbefalet)
REM call "%PROJECT_DIR%\venv\Scripts\activate.bat"

echo [%DATE% %TIME%] Starter job_mail_planner pipeline... >> data\out\scheduler.log

python -m src.pipeline.run_all >> data\out\scheduler.log 2>&1

echo [%DATE% %TIME%] Pipeline afsluttet. >> data\out\scheduler.log
