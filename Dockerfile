FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

VOLUME ["/app/data"]

EXPOSE 8000

ENV SPOOLIFY_DATA_DIR=data \
    SPOOLIFY_API_HOST=0.0.0.0 \
    SPOOLIFY_API_PORT=8000 \
    SPOOLIFY_LOG_LEVEL=INFO

CMD ["python", "entrypoint.py", "serve"]
