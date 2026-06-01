FROM python:3.12-alpine

RUN apk add --no-cache tini

RUN addgroup -S meds -g 1000 && adduser -S meds -G meds -u 1000

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app
COPY static /app/static
COPY wsgi.py /app/wsgi.py

RUN mkdir -p /app/data && chown -R meds:meds /app

USER meds

ENV DB_PATH=/app/data/medsafety.db

EXPOSE 8004

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["gunicorn", "--workers", "2", "--threads", "4", "--worker-class", "gthread", "--bind", "0.0.0.0:8004", "wsgi:app"]
