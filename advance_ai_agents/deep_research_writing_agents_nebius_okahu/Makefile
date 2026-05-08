ifeq (,$(wildcard .env))
$(error .env file is missing. Please create one based on .env.example. Run: "cp .env.example .env" and fill in the missing values.)
endif

include .env
export

export UV_PROJECT_ENVIRONMENT=.venv
export PYTHONPATH = ./src/

# --- Default Values ---

QA_FOLDERS := src/ scripts/
TEST_SLUG := im-currently-designing-a-second-brain-ai-agent
DATASET_DIR := datasets/linkedin_paul_iusztin

# --- QA ---

format-fix: # Auto-format Python code using ruff formatter.
	uv run ruff format $(QA_FOLDERS)

lint-fix: # Auto-fix linting issues using ruff linter.
	uv run ruff check --fix $(QA_FOLDERS)

format-check: # Check code formatting without making changes using ruff formatter.
	uv run ruff format --check $(QA_FOLDERS)

lint-check: # Check code for linting issues without fixing them using ruff linter.
	uv run ruff check $(QA_FOLDERS)

# --- Run ---

run-research-server: # Run the Deep Research MCP server (stdio transport).
	uv run fastmcp run src/research/server.py

run-writing-server: # Run the LinkedIn Writer MCP server (stdio transport).
	uv run fastmcp run src/writing/server.py

run-ui: # Run the Streamlit chat UI orchestrating both MCP servers.
	uv run streamlit run streamlit_app.py

test-research-workflow: # Test the research workflow using the dataset seed.
	@mkdir -p test_logic
	@cp $(DATASET_DIR)/$(TEST_SLUG)_seed.md test_logic/seed.md
	uv run python scripts/test_research_workflow.py --working-dir test_logic --iterations 2

test-writing-workflow: # Test the writing workflow using the dataset guideline and research.
	@mkdir -p test_logic
	@cp $(DATASET_DIR)/$(TEST_SLUG)_guideline.md test_logic/guideline.md
	@test -f test_logic/research.md || cp $(DATASET_DIR)/$(TEST_SLUG)_research.md test_logic/research.md
	uv run python scripts/test_writing_workflow.py --working-dir test_logic

test-end-to-end: # Test research + writing end-to-end using the dataset sample.
	make test-research-workflow
	make test-writing-workflow

# --- Dataset ---

run-dataset-writing: # Run the full research + writing workflow on all dataset posts (output to test_all/).
	uv run python scripts/run_dataset_writing.py --output-dir test_all --run-research

run-dataset-writing-no-image: # Run the full research + writing workflow on all dataset posts without images.
	uv run python scripts/run_dataset_writing.py --output-dir test_all --run-research --skip-image

# --- Evaluation ---

eval-dev: # Run LLM judge on dev split (alignment check).
	uv run python scripts/run_evaluation.py --split dev_evaluator

eval-test: # Run LLM judge on test split (final evaluation).
	uv run python scripts/run_evaluation.py --split test_evaluator

eval-online: # Run online evaluation: generate posts on the fly + judge them.
	uv run python scripts/run_online_evaluation.py --split online_test
