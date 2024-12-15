SHELL := /bin/bash

runLocal:
	source .env.local && \
	poetry run uvicorn --reload --workers 4 --host 0.0.0.0 --port 8000 --timeout-keep-alive 600 app.server:app --log-config ./config.local.ini --log-level debug

initialMigration:
	source .env.local && \
	alembic revision --autogenerate -m "Initial migration"
	
applyMigration:
	source .env.local && \
	alembic upgrade head
