FROM python:3.12-slim

WORKDIR /srv

COPY shared/ /srv/shared/
COPY services/memory/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -e /srv/shared

COPY services/memory/app/ /srv/services/memory/app/
COPY scripts/migrations/ /srv/scripts/migrations/
RUN touch /srv/services/__init__.py /srv/services/memory/__init__.py

EXPOSE 8001
CMD ["uvicorn", "services.memory.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
