.PHONY: doctor doctor-db doctor-health doctor-ui

doctor: doctor-db doctor-health doctor-ui
	@echo "Doctor: OK"

doctor-db:
	@python3 api/scripts/db_doctor.py

doctor-health:
	@bash -c '\
		if curl -fsS http://127.0.0.1:8080/api/health >/dev/null 2>&1; then \
			curl -fsS http://127.0.0.1:8080/api/health | (command -v jq >/dev/null && jq || cat); \
		else \
			echo "[INFO] /api/health not available yet; using /api/status"; \
			curl -fsS http://127.0.0.1:8080/api/status | (command -v jq >/dev/null && jq || cat); \
		fi'

doctor-ui:
	@bash -c '\
		if [ -d ui ]; then \
			cd ui; \
			npm run -s lint; \
			npm run -s build; \
		else \
			echo "[SKIP] ui/ directory not found"; \
		fi'

