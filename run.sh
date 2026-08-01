#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  if python3 -m venv .venv 2>/dev/null; then
    source .venv/bin/activate
  else
    echo "python3-venv no está instalado; usando paquetes de usuario."
    pip3 install -q --user --break-system-packages -r requirements.txt
    echo "Abriendo http://localhost:8000"
    exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
  fi
else
  source .venv/bin/activate
fi

pip install -q -r requirements.txt

echo "Abriendo http://localhost:8000"
uvicorn app.main:app --host 0.0.0.0 --port 8000
