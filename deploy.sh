#!/usr/bin/env bash
set -e
docker-compose build
docker-compose up -d
docker-compose ps
docker-compose logs -f cctv-app