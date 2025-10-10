.PHONY: setup install fmt lint test

setup:
	python3.12 -m venv .venv
	. .venv/bin/activate && python -m pip install --upgrade pip
	. .venv/bin/activate && python -m pip install -r requirements.txt
	. .venv/bin/activate && python -m pip install -r requirements-dev.txt

install:
	. .venv/bin/activate && python -m pip install -r requirements.txt

fmt:
	. .venv/bin/activate && black src pages Home.py

lint:
	. .venv/bin/activate && ruff check src pages Home.py

test:
	. .venv/bin/activate && pytest
