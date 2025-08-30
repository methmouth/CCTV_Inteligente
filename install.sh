#!/usr/bin/env bash
set -e

echo "=== Instalando CCTV_Inteligente ==="
apt-get update -y
apt-get install -y python3 python3-venv python3-pip build-essential ffmpeg git wget curl libsm6 libxrender1 libxext6 libgtk-3-dev libboost-all-dev cmake

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

mkdir -p recordings evidencias reports config_history
echo "✅ Instalación completada"