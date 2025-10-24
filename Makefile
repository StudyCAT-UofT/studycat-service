PYTHON = python3.10

venv:
	@if [ ! -d ".venv" ]; then \
		echo "Creating virtual environment..."; \
		$(PYTHON) -m venv .venv; \
	fi
	@echo "✅ Virtual environment ready."

install: venv
	@source .venv/bin/activate && pip install -r requirements.txt
	@echo "✅ Dependencies installed."

db-generate: venv install
	@source .venv/bin/activate && prisma generate --schema external/studycat-schema/schema.prisma --generator py
	@echo "✅ Prisma client generated."

submodule-update:
	@git submodule update --init --recursive
	@echo "✅ Submodule updated."

run: venv install db-generate submodule-update
	@source .venv/bin/activate && uvicorn main:app --reload --host 0.0.0.0 --port 8000