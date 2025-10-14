.PHONY: digest
digest:
	@set -euo pipefail; \
	echo "Running publish_digests.py..."; \
	DIGEST="$(DIGEST)" DATE="$(DATE)" DRY_RUN="$(DRY_RUN)" \
	python3 scripts/publish_digests.py
