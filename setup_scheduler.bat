@echo off
REM ============================================================
REM  setup_scheduler.bat
REM  Kør denne ÉN gang som administrator for at oprette
REM  den planlagte opgave i Windows Task Scheduler.
REM
REM  TILRET:
REM    PROJECT_DIR  — stien til dit projekt
REM    RUN_TIME     — hvornår den skal køre (HH:MM)
REM    RUN_DAY      — hvilken dag om måneden (fx "15" eller "MON-SUN")
REM ============================================================

set PROJECT_DIR=C:\job_mail_planner
set TASK_NAME=JobMailPlanner
set RUN_TIME=08:00
set BAT_FILE=%PROJECT_DIR%\run.bat

echo Opretter planlagt opgave: %TASK_NAME%
echo Kørselstidspunkt: %RUN_TIME% dagligt
echo Script: %BAT_FILE%
echo.

REM Opret opgaven (kører dagligt kl. 08:00)
schtasks /Create /TN "%TASK_NAME%" /TR "%BAT_FILE%" /SC DAILY /ST %RUN_TIME% /F /RL HIGHEST

if %ERRORLEVEL% == 0 (
    echo.
    echo [OK] Opgaven '%TASK_NAME%' er oprettet.
    echo Du kan se og ændre den i Task Scheduler ^(søg i Start-menuen^).
) else (
    echo.
    echo [FEJL] Opgaven kunne ikke oprettes.
    echo Prøv at højreklikke på denne fil og vælg 'Kør som administrator'.
)

echo.
pause
