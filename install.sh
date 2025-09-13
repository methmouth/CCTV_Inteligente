#!/usr/bin/env bash
set -e
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$PROJECT_DIR/venv"

echo "=== Instalador CCTV_Inteligente ==="
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv python3-pip build-essential cmake git curl ffmpeg \
 libsm6 libxrender1 libxext6 libgl1 libgtk-3-dev libboost-all-dev pkg-config libopenblas-dev

# Crear usuario 'cctv' (opcional)
if ! id -u cctv >/dev/null 2>&1; then
  sudo useradd -m -s /bin/bash cctv
  echo "Usuario 'cctv' creado."
fi

python3 -m venv "$VENV"
source "$VENV/bin/activate"
pip install --upgrade pip setuptools wheel

# Instalar requirements (cuidado: dlib / face_recognition compilan)
pip install -r requirements.txt

# Instala PyTorch CPU (si quieres GPU, cambia esto por la rueda CUDA adecuada)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# rclone (opcional)
if ! command -v rclone >/dev/null 2>&1; then
  curl https://rclone.org/install.sh | sudo bash
fi

# crear carpetas
mkdir -p faces recordings evidencias reports config_history
sudo chown -R cctv:cctv recordings evidencias reports faces || true

echo "✅ Instalación completada."
echo "Inicializa BD: python3 db_init.py"
echo "Para ejecutar en background: sudo systemctl start cctv.service (si configuras service)"