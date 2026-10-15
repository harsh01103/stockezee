.PHONY: install test cov mutate build run
install:
	pip install -e . pytest pytest-cov build httpx
test:
	pytest -q
cov:
	pytest --cov=stockezee --cov-report=term-missing
mutate:
	python mutation_test.py
build:
	python -m build
run:
	uvicorn stockezee.api:app --reload
