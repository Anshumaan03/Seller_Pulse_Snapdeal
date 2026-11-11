# macOS / Linux shortcuts. Windows users: see the PowerShell commands in README.md.
.PHONY: setup run test ui-test

setup:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt

run:
	. .venv/bin/activate && uvicorn backend.app.main:app --port 8000

test:
	. .venv/bin/activate && python -m pytest -q

ui-test:
	python3 backend/tests/ui_smoke.py http://localhost:8000
