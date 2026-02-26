FROM python:3.11-slim

WORKDIR /app/applications/web_app

COPY applications/web_app/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 5000

ENV PYTHONPATH=/app:$PYTHONPATH

CMD ["gunicorn", "-b", "0.0.0.0:8000", "--chdir", "/app/applications/web_app", "src.app:app"]
