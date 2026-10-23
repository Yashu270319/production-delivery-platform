.PHONY: test validate-deployment

test:
	python -m pytest -q

validate-deployment:
	./scripts/validate-deployment.sh $(or $(BASE_URL),http://127.0.0.1:8001) $(or $(EXPECTED_VERSION),1.0.1)
