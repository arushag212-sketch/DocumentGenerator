.PHONY: test build

test:
	python -m compileall -q server/app
	npm --prefix web run build

build: test
