.PHONY: start stop check logs delete restart

start:
	@sudo docker compose up -d --build

stop:
	@sudo docker compose down

check:
	@sudo docker compose ps -a

logs:
	@sudo docker compose logs

delete:
	@read -p "Удалить базу данных? [y/N] " confirm; \
	[ "$$confirm" = "y" ] && sudo docker compose down -v || echo "Отменено"

restart: stop start
