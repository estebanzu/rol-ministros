#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  if python3 -m venv .venv 2>/dev/null; then
    source .venv/bin/activate
  else
    echo "python3-venv no está disponible; creando venv sin pip..."
    python3 -m venv --without-pip .venv
    source .venv/bin/activate
    if [ ! -f .venv/bin/pip ]; then
      echo "Bootstrapping pip..."
      curl -sS https://bootstrap.pypa.io/get-pip.py -o get-pip.py || wget -q https://bootstrap.pypa.io/get-pip.py -O get-pip.py
      python get-pip.py
      rm -f get-pip.py
    fi
  fi
else
  source .venv/bin/activate
fi

pip install -q -r requirements.txt

echo "Abriendo http://localhost:8000"
uvicorn app.main:app --host 0.0.0.0 --port 8000
