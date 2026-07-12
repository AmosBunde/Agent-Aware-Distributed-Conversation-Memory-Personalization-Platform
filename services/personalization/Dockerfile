FROM python:3.12-slim

WORKDIR /srv

COPY shared/ /srv/shared/
COPY services/personalization/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -e /srv/shared

COPY services/personalization/app/ /srv/services/personalization/app/
RUN touch /srv/services/__init__.py /srv/services/personalization/__init__.py

EXPOSE 8002
CMD ["uvicorn", "services.personalization.app.main:app", "--host", "0.0.0.0", "--port", "8002"]
