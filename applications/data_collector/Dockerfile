FROM python:3.11-slim

WORKDIR /app

COPY applications/web_app/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /app

ENV PYTHONPATH=/app:$PYTHONPATH

CMD ["python", "-m", "applications.data_collector.worker"]
