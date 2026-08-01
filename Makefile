VENV := .venv

ifeq ($(wildcard $(VENV)/bin/pip),)
ifeq ($(wildcard $(VENV)/Scripts/pip),)
	PY := python3
	PIP := python3 -m pip
	PIP_FLAGS := --user --break-system-packages
else
	PY := $(VENV)/Scripts/python
	PIP := $(VENV)/Scripts/pip
	PIP_FLAGS :=
endif
else
	PY := $(VENV)/bin/python
	PIP := $(VENV)/bin/pip
	PIP_FLAGS :=
endif

.PHONY: build start stop security sanity format lint clean dist-clean

build:
	@rm -rf "$(VENV)" || true
	python3 -m venv $(VENV) 2>/dev/null || python3 -m venv --without-pip $(VENV)
	@if [ ! -f "$(VENV)/bin/pip" ] && [ ! -f "$(VENV)/Scripts/pip" ]; then \
		echo "Bootstrapping pip..."; \
		curl -sS https://bootstrap.pypa.io/get-pip.py -o get-pip.py || wget -q https://bootstrap.pypa.io/get-pip.py -O get-pip.py; \
		$(VENV)/bin/python get-pip.py || $(VENV)/Scripts/python get-pip.py; \
		rm -f get-pip.py; \
	fi
	@if [ -x "$(VENV)/bin/pip" ]; then \
		$(VENV)/bin/pip install --ignore-installed -r requirements.txt; \
	elif [ -f "$(VENV)/Scripts/pip" ] || [ -f "$(VENV)/Scripts/pip.exe" ]; then \
		$(VENV)/Scripts/pip install --ignore-installed -r requirements.txt; \
	else \
		python3 -m pip install -r requirements.txt; \
	fi

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
# Additional verification targets

type-check:
	$(PIP) install $(PIP_FLAGS) mypy
	$(PY) -m mypy app tests

security-extra:
	$(PIP) install $(PIP_FLAGS) bandit safety
	$(PY) -m bandit -r app
	$(PY) -m safety check -r requirements.txt

coverage:
	$(PIP) install $(PIP_FLAGS) pytest-cov
	$(PY) -m pytest --cov=app --cov-report=term-missing

all-check: format lint type-check security security-extra coverage
	@echo "All checks passed."

clean:
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name '*.pyc' -delete 2>/dev/null || true
	@rm -rf .pytest_cache .ruff_cache *.egg-info 2>/dev/null || true
	@echo "Limpieza de artefactos completada."

dist-clean: clean
	@rm -rf $(VENV) data 2>/dev/null || true
	@echo "Limpieza total completada."
