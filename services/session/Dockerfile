FROM python:3.12-slim

WORKDIR /srv

COPY shared/ /srv/shared/
COPY services/session/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -e /srv/shared

COPY services/session/app/ /srv/services/session/app/
RUN touch /srv/services/__init__.py /srv/services/session/__init__.py

EXPOSE 8004
CMD ["uvicorn", "services.session.app.main:app", "--host", "0.0.0.0", "--port", "8004"]
