FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Hosted platforms mount a persistent disk here (see render.yaml)
ENV ARDHI_DATA_DIR=/data
RUN mkdir -p /data

EXPOSE 8000
# $PORT is injected by most PaaS providers; default to 8000 locally
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
