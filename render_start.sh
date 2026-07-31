#!/usr/bin/env bash
set -e

echo "Starting Austria Express..."
echo "Running database initialization..."
flask --app run.py init-db

echo "Starting Gunicorn..."
exec gunicorn run:app --access-logfile - --error-logfile -
