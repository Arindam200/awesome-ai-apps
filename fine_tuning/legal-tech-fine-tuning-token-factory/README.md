# Legal Tech Fine-Tuning on Nebius Token Factory

> Sanitize a legal Q&A dataset, launch a hosted LoRA fine-tuning job on Nebius Token Factory, and deploy the resulting checkpoint as a private custom model — all via the managed API, no GPU provisioning required.

Unlike [`legal-tech-fine-tuning-nebius-cloud`](../legal-tech-fine-tuning-nebius-cloud) (which self-hosts training and serving with TRL + vLLM on your own GPU), this project uses Nebius Token Factory's **managed fine-tuning API**: upload a dataset, kick off a job, poll it to completion, and deploy the checkpoint as a private model you can call like any other Token Factory model.

## 🚀 Features

- **Dataset sanitization**: repairs and normalizes a raw chat-style JSONL dataset (role aliasing, dropping malformed records) before upload
- **Managed LoRA fine-tuning**: launches and polls a fine-tuning job on Nebius Token Factory via the OpenAI-compatible SDK
- **State tracking**: persists job IDs, checkpoints, and dataset paths to `artifacts/legal_finetune_state.json` so steps can be run independently
- **Private model deployment**: promotes the latest fine-tuning checkpoint to a deployable private custom model and runs a smoke test against it
- **Notebook walkthrough**: `legal.ipynb` for an interactive, step-by-step version of the same flow

## 🛠️ Tech Stack

- **Python**: Core programming language
- **[Nebius Token Factory](https://tokenfactory.nebius.com/)**: Hosted fine-tuning, checkpoints, and private model deployment
- **OpenAI Python SDK**: Used against Token Factory's OpenAI-compatible API for file uploads, fine-tuning jobs, and chat completions
- **`requests`**: For the custom-model deployment endpoints not covered by the OpenAI SDK

## Workflow

```
legislation_qa_clean.jsonl
        │  sanitize (role aliasing, drop malformed records)
        ▼
artifacts/legislation_qa_clean.nebius.jsonl
        │  upload + create fine-tuning job (LoRA)
        ▼
Nebius Token Factory fine-tuning job  ──►  checkpoints
        │  latest checkpoint
        ▼
Private custom model (deploy_private_legal_model.py)
        │  smoke test chat completion
        ▼
Ready to call like any other Token Factory model
```

State from each stage is saved to `artifacts/legal_finetune_state.json`, so `deploy_private_legal_model.py` can pick up the job ID and base model from a previous `launch_legal_finetune.py` run automatically.

## 📦 Getting Started

### Prerequisites

- Python 3.10+
- A [Nebius Token Factory](https://tokenfactory.nebius.com/) API key with fine-tuning access

### Environment Variables

```env
NEBIUS_API_KEY="your_nebius_api_key"
```

### Installation

```bash
git clone https://github.com/Arindam200/awesome-llm-apps.git
cd awesome-llm-apps/fine_tuning/legal-tech-fine-tuning-token-factory
pip install openai requests
```

## ⚙️ Usage

### 1. Sanitize the dataset and launch a fine-tuning job

```bash
export NEBIUS_API_KEY="your_nebius_api_key"
python launch_legal_finetune.py --dataset legislation_qa_clean.jsonl --wait
```

- Drop `--wait` to launch the job and return immediately (poll it later with your own script, or rerun with `--wait`).
- Useful flags: `--model` (base model, default `meta-llama/Llama-3.1-8B-Instruct`), `--epochs`, `--learning-rate`, `--lora-r`, `--lora-alpha`, `--lora-dropout`, `--suffix`.

This writes the sanitized dataset to `artifacts/legislation_qa_clean.nebius.jsonl` and job state to `artifacts/legal_finetune_state.json`.

### 2. Deploy the fine-tuned checkpoint as a private model

```bash
python deploy_private_legal_model.py --name legislation-qa-private
```

Reads the job ID and base model from `artifacts/legal_finetune_state.json` (or pass `--job-id` / `--base-model` explicitly), grabs the latest checkpoint, deploys it as a private custom model, waits for it to become active, and runs a one-line smoke test chat completion. Pass `--skip-smoke-test` to skip that last step.

### 3. Or follow along interactively

Open `legal.ipynb` for the same flow broken into notebook cells.

## 📂 Project Structure

```
legal-tech-fine-tuning-token-factory/
├── launch_legal_finetune.py       # Sanitize dataset, upload, launch/poll fine-tuning job
├── deploy_private_legal_model.py  # Deploy latest checkpoint as a private custom model + smoke test
├── legal.ipynb                    # Interactive notebook walkthrough
├── legislation_qa_clean.jsonl     # Example raw training dataset
└── artifacts/                     # Generated: sanitized dataset + job/deployment state (gitignored)
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. See the [CONTRIBUTING.md](https://github.com/Arindam200/awesome-llm-apps/blob/main/CONTRIBUTING.md) for more details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/Arindam200/awesome-llm-apps/blob/main/LICENSE) file for details.
