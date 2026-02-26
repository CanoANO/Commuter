web: PYTHONPATH=. gunicorn -b 0.0.0.0:$PORT --chdir applications/web_app src.app:app
collector: PYTHONPATH=. python -m applications.data_collector.worker
analyzer: PYTHONPATH=. python -m applications.data_analyzer.worker
release: PYTHONPATH=. python -c "from components.database.session import _run_alembic_migrations; _run_alembic_migrations()"