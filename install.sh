#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"

echo "=== 🚀 Instalador CCTV_Inteligente (Debian/Ubuntu 11+) ==="
apt-get update -y
apt-get install -y \
  python3 python3-venv python3-pip \
  build-essential cmake \
  libsm6 libxrender1 libxext6 \
  ffmpeg git wget curl \
  libopenblas-dev liblapack-dev \
  libgtk2.0-dev pkg-config \
  libboost-all-dev

# Crear usuario no root
if ! id -u cctv >/dev/null 2>&1; then
  useradd -m -s /bin/bash cctv
  echo "✅ Usuario 'cctv' creado."
fi

# Crear virtualenv
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip wheel setuptools

# Instalar dependencias Python
pip install -r "$PROJECT_DIR/requirements.txt"

# Instalar PyTorch (CPU por defecto, GPU opcional)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Descargar e instalar rclone
if ! command -v rclone &> /dev/null; then
  echo "⬇️ Instalando rclone..."
  curl https://rclone.org/install.sh | bash
fi

# Crear carpetas
mkdir -p "$PROJECT_DIR/recordings" \
         "$PROJECT_DIR/evidencias" \
         "$PROJECT_DIR/reports" \
         "$PROJECT_DIR/config_history" \
         "$PROJECT_DIR/faces"
chown -R cctv:cctv "$PROJECT_DIR/recordings" "$PROJECT_DIR/evidencias" "$PROJECT_DIR/reports"

# Crear systemd unit (usuario cctv)
SERVICE_USER_FILE="/etc/systemd/system/cctv.service"
cat > "$SERVICE_USER_FILE" <<EOF
[Unit]
Description=CCTV Inteligente (user cctv)
After=network.target

[Service]
Type=simple
User=cctv
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/python $PROJECT_DIR/app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Crear systemd unit (root admin)
SERVICE_ADMIN_FILE="/etc/systemd/system/cctv_admin.service"
cat > "$SERVICE_ADMIN_FILE" <<EOF
[Unit]
Description=CCTV Inteligente (admin root)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/python $PROJECT_DIR/app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Recargar systemd y habilitar servicios
systemctl daemon-reload
systemctl enable cctv.service
systemctl enable cctv_admin.service

echo "✅ Instalación completada."
echo "- Inicia BD:   python3 db_init.py"
echo "- Arranca app: sudo systemctl start cctv.service"