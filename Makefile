.PHONY: test run docker-build demo install

install:
	pip install -e ".[dev]"

test:
	pytest

run:
	uvicorn the_harness.webui:app --host 0.0.0.0 --port 8000

docker-build:
	docker build -t the-harness .

docker-run:
	docker run -p 8000:8000 the-harness

demo:
	python demo.py
