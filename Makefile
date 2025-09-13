up: ; docker-compose up -d
down: ; docker-compose down
build: ; docker-compose build
rebuild: ; docker-compose build --no-cache
logs: ; docker-compose logs -f cctv-app
ps: ; docker-compose ps
shell: ; docker exec -it cctv_app /bin/bash
report: ; docker exec -it cctv_reporter python reporter.py once
clean:
	docker-compose down -v
	docker system prune -f