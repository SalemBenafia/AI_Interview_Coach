# services/stt-service/Dockerfile
# Real faster-whisper STT microservice. CPU image by default (int8); set
# WHISPER_DEVICE=cuda and WHISPER_COMPUTE_TYPE=float16 + install onnxruntime-gpu
# style base image for GPU deployments.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 120 --retries 5 -r requirements.txt

COPY main.py .

# Pre-downloading the model at build time is optional -- by default
# faster-whisper downloads it on first run and caches it in this volume.
VOLUME ["/root/.cache/huggingface"]

EXPOSE 9001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9001"]
