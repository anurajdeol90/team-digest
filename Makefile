# Makefile for running digests

.PHONY: digest daily weekly monthly

digest:
	@echo "→ Running: python3 scripts/publish_digests.py --digest $(DIGEST) --date '$(DATE)' --dry-run $(DRY_RUN)"
	python3 scripts/publish_digests.py --digest $(DIGEST) --date "$(DATE)" --dry-run $(DRY_RUN)

daily:
	$(MAKE) digest DIGEST=daily DATE="$(DATE)" DRY_RUN=$(DRY_RUN)

weekly:
	$(MAKE) digest DIGEST=weekly DATE="$(DATE)" DRY_RUN=$(DRY_RUN)

monthly:
	$(MAKE) digest DIGEST=monthly DATE="$(DATE)" DRY_RUN=$(DRY_RUN)
