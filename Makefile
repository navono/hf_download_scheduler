dev:
	uv run -m src.main run

local:
	uv run -m src.main_local

.PHONY: dev local

prefect-reset:
	uv run prefect config set PREFECT_API_URL=""

prefect-deploy:
	uv run prefect deploy src/app.py:process_flow --name process-flow-deployment --pool default-agent-pool

prefect-worker:
	uv run prefect worker start --pool default-agent-pool

prefect-run:
	uv run prefect deployment run 'process-flow/process-flow-deployment'

prefect-create-work-pool:
	uv run prefect work-pool create default-agent-pool --type process

.PHONY: prefect-reset prefect-deploy prefect-worker prefect-run prefect-create-work-pool

# Remote worker setup commands
PREFECT_API_URL ?= http://192.168.8.127:4200/api

remote-worker-setup:
	@echo "Setting up Prefect worker for remote execution..."
	@echo "Make sure Prefect server is accessible at $(PREFECT_API_URL)"
	uv run prefect config set PREFECT_API_URL=$(PREFECT_API_URL)

remote-worker-start:
	uv run prefect worker start --pool default-agent-pool --api $(PREFECT_API_URL)

remote-deploy:
	@echo "Deploying to remote Prefect server at $(PREFECT_API_URL)..."
	uv run prefect deploy src/app.py:process_flow --name process-flow-deployment --pool default-agent-pool --api $(PREFECT_API_URL)

# Utility commands
show-ip:
	@echo "Local IP addresses:"
	@echo "  - 192.168.8.127 (likely LAN IP)"
	@echo "  - 172.18.32.1 (internal)"
	@echo "  - 192.168.56.1 (VirtualBox)"

show-config:
	uv run prefect config view

.PHONY: remote-worker-setup remote-worker-start remote-deploy show-ip show-config