.PHONY: release-gate test validate

release-gate:
	python3 scripts/release_gate.py

test:
	PYTHONPATH=src:. python3 -m unittest discover -s tests -p 'test_*.py'

validate:
	python3 scripts/validate_repository.py --json reports/validation.json
