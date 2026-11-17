@echo off
chcp 65001 > nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

:: Muda para o diretorio onde este arquivo .bat esta localizado
cd /d "%~dp0"

echo ================================================== >> monitor.log
echo Execucao em: %date% %time% >> monitor.log

:: Detecta se existe ambiente virtual (venv ou .venv) ou usa o python do sistema
if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" main.py >> monitor.log 2>&1
) else if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" main.py >> monitor.log 2>&1
) else (
    python main.py >> monitor.log 2>&1
)
