.PHONY: install up down init seed dev-backend dev-frontend test test-unit test-integration build-frontend demo lint

install:
	pip install -e ".[dev]"
	cd helpdesk-ui && npm install

up:
	docker-compose up -d

down:
	docker-compose down

init:
	python scripts/init_db.py
	python scripts/init_vector_db.py

seed:
	python data/sample_pdfs/sample_it_guide.py
	python scripts/seed_demo.py

dev-backend:
	python -m app.main

dev-frontend:
	cd helpdesk-ui && npm run dev

test:
	pytest tests/ -v

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

build-frontend:
	cd helpdesk-ui && npm run build

demo:
	python -m app.main --demo-mode

lint:
	ruff check app/ tests/
	cd helpdesk-ui && npm run build
