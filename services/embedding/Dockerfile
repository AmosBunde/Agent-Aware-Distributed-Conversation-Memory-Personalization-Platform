FROM python:3.12-slim

WORKDIR /srv

COPY shared/ /srv/shared/
COPY services/embedding/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -e /srv/shared

COPY services/embedding/app/ /srv/services/embedding/app/
RUN touch /srv/services/__init__.py /srv/services/embedding/__init__.py

EXPOSE 8003
CMD ["uvicorn", "services.embedding.app.main:app", "--host", "0.0.0.0", "--port", "8003"]
