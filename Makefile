.PHONY: format lint
format:
	black .
	isort .

lint:
	flake8
