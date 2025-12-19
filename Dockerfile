FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app/supplychain_test

# system libs: postgres client libs + (optional) pillow runtime libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
  && rm -rf /var/lib/apt/lists/*

COPY requirements-prod.txt /app/requirements-prod.txt
RUN pip install --no-cache-dir -r /app/requirements-prod.txt

COPY . /app

EXPOSE 8000

CMD ["bash", "-lc", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn supplychain_test.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 4 --timeout 60 --access-logfile - --error-logfile - --log-level info --capture-output"]
