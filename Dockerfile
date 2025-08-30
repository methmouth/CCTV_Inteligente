FROM python:3.10-slim
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 TZ=UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git curl wget ffmpeg libsm6 libxext6 libxrender1 libgl1 libgtk-3-dev libboost-all-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt
RUN curl https://rclone.org/install.sh | bash

COPY . /app/
RUN mkdir -p recordings evidencias reports config_history

EXPOSE 5000
CMD ["python","app.py"]