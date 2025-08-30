# 🔒 CCTV Inteligente — Dashboard con AI + CRUD + TTS + Reportes

Sistema de **videovigilancia inteligente** para escritorio y servidores.  
Construido con **YOLOv8 + DeepSORT + PyQt5 + SQLite**.  
Incluye dashboard estilo Office, CRUD tipo Excel, alertas con voz (TTS), reporter automático en PDF/CSV y despliegue vía Docker.

---

## 🚀 Características principales

- **🔎 Detección AI**
  - Detector **YOLOv8n** (optimizado para CPU/GPU).
  - **DeepSORT** → tracking estable con IDs únicos.
  - Clasificación de personas (empleados, clientes, proveedores, invitados, desconocidos).
  - Hitbox con **nombre/rol** encima de cada persona detectada.

- **🖥️ Dashboard PyQt5**
  - Barra de herramientas estilo Office.
  - CRUD tipo Excel sobre tabla `persons`.
  - Editor directo de eventos en tabla `events`.
  - Exportación rápida a CSV (`events.csv`).
  - Vista en vivo de cámaras IP / webcam.

- **📂 Base de datos (SQLite)**
  - Tabla `persons`: empleados, clientes, proveedores, invitados.
  - Tabla `events`: histórico de detecciones con timestamp, cámara y persona.
  - Editable desde el dashboard (sin salir de la app).

- **🔔 Text-to-Speech (TTS)**
  - Alertas sonoras en tiempo real cuando se detecta una **persona desconocida**.
  - Ejemplo: *“Alerta: persona desconocida en cámara 2”*.

- **📊 Exportación y reportes**
  - `events.csv` para abrir en Excel/LibreOffice y generar tablas dinámicas.
  - Reportes automáticos cada **8h** en PDF (`reports/report.pdf`).
  - Logs de consola tipo “ventana de depuración”.

- **☁️ Cloud & despliegue**
  - Clips críticos → subida opcional con `rclone` o `S3`.
  - Despliegue vía **Docker + docker-compose**.
  - Servicios **systemd** (`cctv.service` usuario / `cctv_admin.service` root).

---

## 📂 Estructura del proyecto

CCTV_Inteligente/ │── app.py              # Dashboard principal │── db_init.py          # Inicializa la BD con ejemplos │── reporter.py         # Generador de reportes automáticos │── cameras.json        # Configuración de cámaras │── requirements.txt    # Dependencias │── install.sh          # Instalador (Debian/Ubuntu) │── Dockerfile          # Imagen base │── docker-compose.yml  # Orquestación │── Makefile            # Atajos de despliegue │── deploy.sh           # Script: build + up + logs │── stop.sh             # Script: down + limpieza │── restart.sh          # Script: reinicio completo │── .dockerignore       # Ignorar archivos innecesarios │── people.db           # BD SQLite (se genera tras db_init.py) │── recordings/         # Grabaciones locales │── evidencias/         # Clips críticos / alertas │── reports/            # Reportes PDF/CSV │── config_history/     # Versionado de cameras.json

---

## ⚙️ Instalación (Debian 11+)

### 🖥️ Instalación nativa
```bash
git clone <REPO_URL> CCTV_Inteligente
cd CCTV_Inteligente
sudo bash install.sh
python3 db_init.py
python3 app.py

🐳 Instalación con Docker

git clone <REPO_URL> CCTV_Inteligente
cd CCTV_Inteligente
./deploy.sh


---

📸 Ejemplo cameras.json

{
  "1": "0",
  "2": "rtsp://admin:12345@192.168.1.50:554/Streaming/Channels/101"
}

"1": "0" → Webcam local.

"2": "rtsp://..." → Cámara IP con RTSP (modifica usuario/contraseña/IP).



---

🛡️ Seguridad

Servicios systemd incluidos:

cctv.service → corre como usuario limitado cctv.

cctv_admin.service → corre como root (solo administración).


Rotación de grabaciones: borrar archivos viejos automáticamente.

Cifrado opcional: BD y clips pueden almacenarse en volumen cifrado.



---

📊 Futuras mejoras (Roadmap)

Reconocimiento facial con embeddings + match directo en persons.

Dashboard web (Flask + React) para acceso remoto.

Integración directa con almacenamiento en nube (Nextcloud, S3).

Generación de reportes HTML interactivos.



---

👷 Autores

Equipo de Seguridad + TI

methmouth


---

⚡ Uso rápido

Ejecuta el dashboard → cámara en vivo + barra de herramientas.

Administra personal desde Personas (CRUD).

Revisa detecciones desde Eventos (Excel).

Exporta reportes desde Exportar CSV.

Recibe alertas de voz cuando entra un desconocido.



---
