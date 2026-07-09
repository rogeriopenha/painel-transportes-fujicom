@echo off
REM Agendador Painel Transportes - Braspress
REM Configurar no Windows Task Scheduler:
REM   Gatilho: 06:00, 10:00, 14:00, 18:00, 22:00 (diariamente)
REM   Acao:    python "C:\caminho\completo\Painel Transportes\scheduler.py"

cd /d "%~dp0"
python scheduler.py %*
