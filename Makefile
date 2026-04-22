.PHONY: help bundle-dashboard wheel docker-build docker-run dev-server dev-dashboard test clean

help:  ## Show this help.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

bundle-dashboard:  ## Build the Next.js dashboard and drop it into the Python package.
	./scripts/build-bundled.sh

wheel: bundle-dashboard  ## Build the Python wheel with the dashboard bundled in.
	cd packages/python && rm -rf dist/ build/ && python -m build --wheel

docker-build:  ## Build the local Docker image (awaithumans:local).
	docker build -t awaithumans:local .

docker-run: docker-build  ## Run the local image on :3001.
	docker run --rm -p 3001:3001 --name awaithumans awaithumans:local

dev-server:  ## Run the Python API server from source (no dashboard mount).
	cd packages/python && uvicorn awaithumans.server.app:create_app --factory --reload --port 3001

dev-dashboard:  ## Run the Next.js dashboard dev server.
	cd packages/dashboard && npm run dev

test:  ## Run all test suites.
	cd packages/python && python -m pytest tests/
	cd packages/typescript-sdk && npx vitest run
	cd packages/dashboard && npx tsc --noEmit

clean:  ## Remove all build artifacts.
	rm -rf packages/dashboard/dist packages/dashboard/.next
	rm -rf packages/python/dist packages/python/build
	rm -rf packages/python/awaithumans/dashboard_dist
	rm -rf packages/typescript-sdk/dist
