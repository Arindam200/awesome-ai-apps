# Insurance Claims Fine-Tuning (Nebius Token Factory) using Nebius [Agent Skills](https://skills.sh/arindam200/nebius-skills)

End-to-end example: load an insurance chatbot dataset, distill labels with a **70B teacher** in **Data Lab**, **LoRA**-fine-tune an **8B** model on **Nebius Token Factory**, deploy the adapter as a **serverless** custom endpoint, and compare **base vs fine-tuned** answers in the notebook and in a small **Gradio** app.

This repo teaches the **mechanics** of distillation + fine-tuning on domain dialogue. It is not a full claims-production stack (separate triage, document extraction, and adjudication models)—that is a typical next step when you control data and compliance requirements.

## Features

- **Data Lab pipeline** — upload JSONL, run batch inference with a teacher model, export results
- **Teacher distillation** — stronger model (`meta-llama/Llama-3.3-70B-Instruct`) improves training targets before student training
- **LoRA fine-tuning** — efficient adaptation on `meta-llama/Llama-3.1-8B-Instruct` (training API model id)
- **Serverless deployment** — LoRA adapter exposed as a private model name (`POST /v0/models`); pay per token when you call it
- **Before/after evaluation** — same held-out prompts on base 8B vs your adapter; optional Gradio UI for side-by-side chat

## Tech stack

- **Python** 3.10+
- **Jupyter** — tutorial notebook
- **OpenAI-compatible client** — Token Factory inference and fine-tuning APIs
- **`requests`** — Data Lab REST (`/v1/datasets`, `/v1/operations`)
- **`datasets`** — load [Bitext Insurance LLM Chatbot](https://huggingface.co/datasets/bitext/Bitext-insurance-llm-chatbot-training-dataset) from Hugging Face
- **Gradio** — local demo (`app.py`)

## Workflow

### Pipeline 

Seven stages from raw dataset to Gradio comparison — Data Lab upload, 70B teacher batch, JSONL curation, LoRA fine-tune, serverless deploy, and before/after evaluation.

<img width="1734" height="924" alt="image" src="https://github.com/user-attachments/assets/d2e76920-4f32-4417-ab95-b8fe741b61c0" />

### Architecture

How the notebook talks to Token Factory: HuggingFace data flows in, Data Lab REST + OpenAI-compatible fine-tuning APIs do the work, artifacts land locally, and the Gradio app calls both the base and LoRA models.

<img width="1555" height="949" alt="image" src="https://github.com/user-attachments/assets/4f668e09-a754-4256-8fb1-0068eebf9255" />


The middle column summarizes **train vs chat** model ids on the fine-tuning card; see **[Model IDs (important)](#model-ids-important)** for the exact strings and table.

## Demo vs full run

Defaults target roughly **5–7 minutes** for batch inference + LoRA when the queue is light: **`SAMPLE_SIZE = 32`**, **`N_EPOCHS = 1`**, **`POLL_SECONDS = 20`**. Actual time depends on Nebius load.

For a stronger model, open **Step 0** in the notebook and raise **`SAMPLE_SIZE`** (e.g. 3000) and **`N_EPOCHS`** (e.g. 2).

## Model IDs (important)

| Use | Model id |
|-----|----------|
| Fine-tuning `jobs.create` | `meta-llama/Llama-3.1-8B-Instruct` |
| Chat `completions` (base tab) | `meta-llama/Meta-Llama-3.1-8B-Instruct` |

The notebook sets both; `app.py` defaults to the **Meta** chat id for the base model.

## What you do in the dashboard

| Step | Where | Action |
|------|--------|--------|
| 1 | [Token Factory](https://tokenfactory.nebius.com/) → Project settings | Create a **project-scoped API key** |
| 2 | After the notebook deploys your adapter | Copy the printed **`CUSTOM_MODEL_NAME`** into `.env` for the Gradio app |

Everything else (Data Lab upload, batch job, training file upload, fine-tuning, deployment, evaluation) runs in the notebook.

## Project layout

```
fine_tuning/insurance_claims_finetuning/
  README.md
  requirements.txt
  .env.example
  assets/
    pipeline-diagram.png
    architecture-diagram.png
  insurance_claims_finetuning_tutorial.ipynb
  app.py
```

Generated when you run the notebook (gitignored): `insurance_claims_demo_artifacts/`.

## Setup

```bash
cd fine_tuning/insurance_claims_finetuning
python -m venv .venv && source .venv/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: NEBIUS_API_KEY (or paste the key in the notebook)
```

## Run the notebook

Open `insurance_claims_finetuning_tutorial.ipynb` and run cells from top to bottom.

- Loads the Bitext dataset via `datasets` (no manual CSV unless you prefer a local file).
- Samples rows, holds out 10 prompts, runs teacher batch inference, fine-tunes, deploys, compares before/after.

After **Step 7**, copy the printed `CUSTOM_MODEL_NAME` into `.env`.

### Reuse a previous teacher batch (optional)

If you keep `insurance_raw_dataset.jsonl` from a run, you can skip starting a new Data Lab batch by setting `REUSE_OUTPUT_DATASET_ID` or `REUSE_BATCH_FROM_STATE=1` in `.env`. See Step 4 in the notebook.

## Run the Gradio app

```bash
cd fine_tuning/insurance_claims_finetuning
# .env needs NEBIUS_API_KEY and CUSTOM_MODEL_NAME
python app.py
```

Open `http://127.0.0.1:7860`. Tabs: **Base model**, **Fine-tuned**, **Side-by-side**.

## Cleanup

When finished, use the **Cleanup** cell at the end of the notebook to delete the deployed custom model (`DELETE /v0/models/...`), or remove it under **Models → Private** in the console. Serverless adapters do not reserve a GPU while idle; you pay when you send traffic.

## References

- [Fine-tuning overview](https://docs.tokenfactory.nebius.com/fine-tuning/overview)
- [Deploy custom LoRA](https://docs.tokenfactory.nebius.com/fine-tuning/deploy-custom-model)
- [Data Lab](https://docs.tokenfactory.nebius.com/data-lab/overview)
- [Token Factory docs](https://docs.tokenfactory.nebius.com/)

## License

This project follows the repository’s [LICENSE](../../LICENSE).
