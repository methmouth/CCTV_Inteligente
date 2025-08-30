FROM python:3.11-slim

# Evitar prompts interactivos
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    build-essential cmake \
    libsm6 libxrender1 libxext6 \
    ffmpeg git wget curl \
    libopenblas-dev liblapack-dev \
    libgtk2.0-dev pkg-config \
    libboost-all-dev \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip wheel setuptools \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Copiar todo el código del repo
COPY . .

# Crear carpetas de datos
RUN mkdir -p recordings evidencias reports config_history faces

# Exponer Flask API en el puerto 5000
EXPOSE 5000

# Comando por defecto: ejecutar app
CMD ["python", "app.py"]