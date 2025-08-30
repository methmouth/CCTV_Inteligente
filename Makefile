up: ; docker-compose up -d
down: ; docker-compose down
build: ; docker-compose build
logs: ; docker-compose logs -f cctv-app
logs-reporter: ; docker-compose logs -f cctv-reporter
restart: ; docker-compose restart
ps: ; docker-compose ps
shell: ; docker exec -it cctv_app /bin/bash
report: ; docker exec -it cctv_reporter python reporter.py
clean:
	docker-compose down -v
	docker system prune -f
	docker volume prune -f