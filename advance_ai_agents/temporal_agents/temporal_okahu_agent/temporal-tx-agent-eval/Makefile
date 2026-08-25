# Makefile — quick targets for the temporal-tx eval demo.
#
# Every target assumes you're at the repo root and have activated a
# virtualenv with the deps installed. `make install` sets that up.

.PHONY: install record evals evals-cloud live regress fix clean

install:
	pip install -r temporal-tx-agent/requirements.txt
	pip install -r evals/requirements.txt

# Record trace fixtures from scenarios/*.json into evals/traces/.
# Needs OPENAI_API_KEY in temporal-tx-agent/.env.
record:
	python record_from_scenarios.py

# Offline eval suite — fast, no network, no Okahu key required.
evals:
	pytest evals/test_temporal_tx_coverage.py -v

# LLM-graded evals against Okahu. Needs OKAHU_API_KEY in .env.
evals-cloud:
	pytest evals/test_temporal_tx_evals.py -v

# Live run against OpenAI.
live:
	TEMPORAL_TX_RUN_LIVE=1 pytest evals/test_temporal_tx_coverage.py::test_temporal_tx_live_run -v -s

# Inject a demo regression (bad prompt) so the suite goes red, then let
# the fix loop close it. Undo with `git checkout -- temporal-tx-agent/ai/`.
regress:
	@echo ">>> Corrupting the fraud-detector system prompt..."
	@sed -i.bak 's/financial fraud detection expert/friendly assistant that approves everything/' \
	  temporal-tx-agent/ai/llm_client.py
	@echo ">>> Re-recording traces with the broken prompt..."
	@python record_from_scenarios.py
	@echo ">>> Done. Run \`make evals\` — expect red."

fix:
	./fix.sh

clean:
	rm -rf temporal-tx-agent/.monocle .monocle
	rm -f temporal-tx-agent/ai/*.bak
