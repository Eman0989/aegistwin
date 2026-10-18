FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/app

COPY requirements.txt requirements-db.txt ./

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt \
    && python -m pip install -r requirements-db.txt \
    && python -m pip check

COPY app/ ./app/
COPY migrations/ ./migrations/
COPY alembic.ini ./
COPY policies/ ./policies/

RUN mkdir -p /srv/app/data \
    && chown -R 10001:10001 /srv/app

USER 10001:10001

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]