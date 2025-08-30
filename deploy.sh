#!/usr/bin/env bash
set -e
echo "🚀 Desplegando CCTV_Inteligente..."
docker-compose build
docker-compose up -d
docker-compose ps
docker-compose logs -f cctv-app