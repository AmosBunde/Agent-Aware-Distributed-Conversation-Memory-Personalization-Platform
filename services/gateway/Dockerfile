FROM python:3.12-slim

WORKDIR /srv

COPY shared/ /srv/shared/
COPY services/gateway/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -e /srv/shared

COPY services/gateway/app/ /srv/services/gateway/app/
RUN touch /srv/services/__init__.py /srv/services/gateway/__init__.py

EXPOSE 8000
CMD ["uvicorn", "services.gateway.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
