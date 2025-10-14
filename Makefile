SHELL := bash
.ONESHELL:

.PHONY: digest daily weekly monthly

digest:
	@echo "→ Running: python3 scripts/publish_digests.py --digest $(DIGEST) $(if $(DATE),--date '$(DATE)') $(if $(filter true,$(DRY_RUN)),--dry-run) $(if $(TZ),--tz '$(TZ)')"
	python3 scripts/publish_digests.py \
		--digest $(DIGEST) \
		$(if $(DATE),--date '$(DATE)') \
		$(if $(filter true,$(DRY_RUN)),--dry-run) \
		$(if $(TZ),--tz '$(TZ)')

daily:
	$(MAKE) digest DIGEST=daily DATE="$(DATE)" DRY_RUN=$(DRY_RUN) TZ="$(TZ)"

weekly:
	$(MAKE) digest DIGEST=weekly DATE="$(DATE)" DRY_RUN=$(DRY_RUN) TZ="$(TZ)"

monthly:
	$(MAKE) digest DIGEST=monthly DATE="$(DATE)" DRY_RUN=$(DRY_RUN) TZ="$(TZ)"
