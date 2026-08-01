VENV := .venv

ifeq ($(wildcard $(VENV)/bin/pip),)
	PY := python3
	PIP := python3 -m pip
	PIP_FLAGS := --user --break-system-packages
else
	PY := $(VENV)/bin/python
	PIP := $(VENV)/bin/pip
	PIP_FLAGS :=
endif

.PHONY: build start stop security sanity format lint clean dist-clean

build:
	@if [ ! -x "$(VENV)/bin/pip" ]; then rm -rf "$(VENV)"; fi
	python3 -m venv $(VENV) 2>/dev/null || echo "python3-venv no disponible; se usaran paquetes de usuario."
	@if [ -x "$(VENV)/bin/pip" ]; then $(VENV)/bin/pip install -r requirements.txt; else python3 -m pip install --user --break-system-packages -r requirements.txt; fi

start:
	$(PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000

stop:
	-pkill -f "uvicorn app.main:app"

security:
	$(PIP) install $(PIP_FLAGS) pip-audit
	$(PY) -m pip_audit --disable-pip --no-deps -r requirements.txt

sanity:
	$(PY) -m pytest -q

format:
	$(PIP) install $(PIP_FLAGS) ruff
	$(PY) -m ruff format app tests
	$(PY) -m ruff check --fix app tests

lint:
	$(PIP) install $(PIP_FLAGS) ruff
	$(PY) -m ruff check app tests

clean:
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name '*.pyc' -delete 2>/dev/null || true
	@rm -rf .pytest_cache .ruff_cache *.egg-info 2>/dev/null || true
	@echo "Limpieza de artefactos completada."

dist-clean: clean
	@rm -rf $(VENV) data 2>/dev/null || true
	@echo "Limpieza total completada."
