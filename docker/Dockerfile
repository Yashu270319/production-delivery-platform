FROM python:3.12-slim AS builder

WORKDIR /build

RUN python -m venv --without-pip /opt/venv

COPY requirements.txt .

RUN python -m pip --python /opt/venv install --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY app/ ./app/

RUN rm -rf \
      /usr/local/lib/python3.12/site-packages/pip \
      /usr/local/lib/python3.12/site-packages/pip-*.dist-info \
      /usr/local/bin/pip \
      /usr/local/bin/pip3 \
      /usr/local/bin/pip3.12 \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

USER 10001:10001

EXPOSE 8000

CMD ["uvicorn", "app.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
