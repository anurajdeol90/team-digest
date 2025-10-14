# Makefile for running digests

# Default DRY_RUN to true unless explicitly set to false by the caller
DRY_RUN ?= true

# Translate DRY_RUN=true|false into the correct CLI flag
ifeq ($(DRY_RUN),false)
DRY_FLAG := --no-dry-run
else
DRY_FLAG := --dry-run
endif

.PHONY: digest daily weekly monthly

digest:
	@echo "→ Running: python3 scripts/publish_digests.py --digest $(DIGEST) $(if $(strip $(DATE)),--date '$(DATE)') $(DRY_FLAG)"
	python3 scripts/publish_digests.py --digest $(DIGEST) $(if $(strip $(DATE)),--date "$(DATE)") $(DRY_FLAG)

daily:
	$(MAKE) digest DIGEST=daily DATE="$(DATE)" DRY_RUN=$(DRY_RUN)

weekly:
	$(MAKE) digest DIGEST=weekly DATE="$(DATE)" DRY_RUN=$(DRY_RUN)

monthly:
	$(MAKE) digest DIGEST=monthly DATE="$(DATE)" DRY_RUN=$(DRY_RUN)
