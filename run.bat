@echo off
cd /d "%~dp0"

if exist .venv\Scripts\python.exe goto venv_ok
if exist .venv rmdir /s /q .venv
echo Recreando entorno virtual...
py -3 -m venv .venv

:venv_ok
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt

echo Abriendo http://localhost:8000
uvicorn app.main:app --host 0.0.0.0 --port 8000
