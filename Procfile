web: PYTHONPATH=. WEB_GUNICORN_BIND=0.0.0.0:$PORT bash scripts/start_all.sh
release: PYTHONPATH=. python -c "from components.database.session import _run_alembic_migrations; _run_alembic_migrations()"