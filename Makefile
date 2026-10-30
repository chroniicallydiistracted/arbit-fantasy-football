.PHONY: check help

check:
	python3 scripts/validate_foundation.py

help:
	@echo "check: verify documentation, traceability, configuration, examples and token contrast"
