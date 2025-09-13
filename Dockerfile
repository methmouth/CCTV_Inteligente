FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git curl wget ffmpeg libsm6 libxext6 libxrender1 \
    libgl1 libgtk-3-dev libopenblas-dev liblapack-dev libboost-all-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --upgrade pip wheel setuptools \
 && pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

COPY . /app
RUN mkdir -p recordings evidencias reports config_history faces

EXPOSE 5000

CMD ["python", "app.py"]