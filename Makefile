# Philippine Mall Explorer. `make help` lists targets.
.DEFAULT_GOAL := help
.PHONY: help setup all scrape clean report site dev check lint test integration e2e

help:  ## show this list
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[1m%-12s\033[0m %s\n", $$1, $$2}'

setup:  ## install dependencies and the browser used by end-to-end tests
	uv sync
	uv run playwright install chromium

all: clean report site  ## stages 2 to 4 over the committed snapshot

scrape:  ## stage 1: fetch every chain (slow, hits the network)
	uv run mallscape scrape

clean:  ## stage 2: standardize listings
	uv run mallscape clean

report:  ## stage 3: analysis tables and breakdown.md
	uv run mallscape report

site:  ## stage 4: build the static site
	uv run mallscape website

dev:  ## build and serve on http://localhost:3000
	uv run mallscape website --serve

check: lint test integration  ## everything that runs without a browser
	@echo "check passed"

lint:  ## static analysis
	uv run ruff check .

test:  ## unit tests
	uv run pytest tests/test_unit.py -q

integration:  ## stage handoff tests
	uv run pytest tests/test_integration.py -q

e2e:  ## drive the built site in a browser (needs `make all` first)
	uv run pytest tests/test_e2e.py -q
