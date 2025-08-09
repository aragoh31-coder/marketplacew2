.PHONY: test lint format
format:
	black .
	isort .
lint:
	flake8
test:
	pytest --maxfail=1 --disable-warnings -q
