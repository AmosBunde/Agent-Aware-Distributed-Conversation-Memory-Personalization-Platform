FROM python:3.12-slim

WORKDIR /srv

COPY shared/ /srv/shared/
COPY services/embedding/requirements.txt services/embedding/requirements-st.txt /srv/
RUN pip install --no-cache-dir -r requirements.txt -e /srv/shared

# Optional semantic backend (torch is heavy; off by default)
ARG INSTALL_ST=false
RUN if [ "$INSTALL_ST" = "true" ]; then \
      pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
      pip install --no-cache-dir -r requirements-st.txt; \
    fi

COPY services/embedding/app/ /srv/services/embedding/app/
RUN touch /srv/services/__init__.py /srv/services/embedding/__init__.py

EXPOSE 8003
CMD ["uvicorn", "services.embedding.app.main:app", "--host", "0.0.0.0", "--port", "8003"]
