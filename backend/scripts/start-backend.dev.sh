#!/bin/bash
alembic upgrade head
poetry run uvicorn --workers 4 --host 0.0.0.0 --port 8000 --timeout-keep-alive 600 app.server:app --log-config ./config.ini --log-level debug