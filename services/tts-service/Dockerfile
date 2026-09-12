# services/tts-service/Dockerfile
# Real Piper TTS microservice. Voice models are downloaded into /app/voices
# at deploy time (see README "Downloading Piper voices") and mounted in --
# they are not baked into the image.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 120 --retries 5 -r requirements.txt

COPY main.py .

VOLUME ["/app/voices"]

EXPOSE 5002
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5002"]
