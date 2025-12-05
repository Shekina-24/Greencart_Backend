# syntax=docker/dockerfile:1

 FROM python:3.11-slim


FROM python:3.10

WORKDIR /code

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

EXPOSE 50505

ENTRYPOINT ["gunicorn", "-c", "app/gunicorn.conf.py", "app.main:app"]
