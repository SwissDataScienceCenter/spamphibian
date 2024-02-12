FROM python:3.9-slim

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONPATH /app

RUN apt-get update && apt-get install -y tini

WORKDIR /app

COPY . /app

RUN pip install --upgrade pip && pip install -r requirements.txt

EXPOSE 5001

ENTRYPOINT ["tini", "--"]
CMD ["python", "flask_service.py"]
