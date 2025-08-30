#!/usr/bin/env bash
set -e
echo "🛑 Deteniendo CCTV_Inteligente..."
docker-compose down
docker system prune -f
docker volume prune -f
echo "✅ Servicios detenidos"