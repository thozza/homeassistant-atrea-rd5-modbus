.PHONY: ci lint test

# Run the full CI pipeline locally using act (https://github.com/nektos/act).
# Only the lint-and-test job is run by default — hacs and hassfest jobs require
# specific Docker images that act cannot pull in all environments.
# Usage:
#   make ci            # run lint-and-test job
#   make ci JOB=hacs   # run a specific job by name
JOB ?= lint-and-test
ci:
	act -s GITHUB_TOKEN="$(gh auth token)" --job $(JOB)

# Shortcuts for running checks directly without act or Docker.
lint:
	ruff check custom_components/
	ruff format --check custom_components/

test:
	pytest tests/ -v
