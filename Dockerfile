FROM python:3.9-slim

RUN apt-get update && apt-get install -y tini supervisor && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

ENV GITLAB_URL=""
ENV GITLAB_ACCESS_TOKEN=""
ENV SLACK_WEBHOOK_URL=""
ENV REDIS_SENTINEL_ENABLED="false"
ENV REDIS_SENTINEL_HOSTS=""
ENV REDIS_HOST=""
ENV REDIS_PORT="6379"
ENV REDIS_DB="0"
ENV REDIS_PASSWORD=""
ENV MODEL_URL="http://model_service:5001"
ENV PYTHONPATH /app

EXPOSE 8000

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN chmod +x /app/check_services_health.sh

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
