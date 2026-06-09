FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    FLASK_USE_RELOADER=0 \
    PORT=5005

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 300 --prefer-binary -r requirements.txt

COPY . .

EXPOSE 5005

CMD ["sh", "-c", "python scripts/setup_database.py && python app.py"]
