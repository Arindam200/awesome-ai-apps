# Fine-Tuning Examples

This directory now groups each fine-tuning example into its own self-contained folder so the notebooks, docs, and supporting assets stay together.

## Examples

- **[Open-source LLM fine-tuning on Nebius Token Factory](open_source_llms_token_factory/README.md)**
  Colab-first walkthrough for uploading a dataset, starting a LoRA fine-tuning job, monitoring training, and deploying the result.
- **[Customer support fine-tuning with Nebius Data Lab](customer_support_datalab/README.md)**
  Teacher-student workflow for generating support data, curating it in Data Lab, fine-tuning a smaller model, and deploying it.
- **[Customer support standalone Colab walkthrough](customer_support_standalone_colab/README.md)**
  Fully standalone demo notebook for running the customer-support distillation and fine-tuning flow step by step in Colab.
- **[Insurance claims Data Lab + fine-tuning + Gradio demo](insurance_claims_finetuning/README.md)**
  End-to-end example with teacher distillation, LoRA fine-tuning, deployment, and a small comparison app.
- **[Legal tech fine-tuning (self-hosted, Gemma + vLLM)](legal-tech-fine-tuning-nebius-cloud/README.md)**
  Fine-tunes Gemma on UK legislation with LoRA, merges and serves with vLLM, and exposes a FastAPI layer with legal-focused routes.
- **[Legal tech fine-tuning (managed, Token Factory)](legal-tech-fine-tuning-token-factory/README.md)**
  Sanitizes a legal Q&A dataset, launches a hosted LoRA fine-tuning job on Nebius Token Factory, and deploys the checkpoint as a private model.

## Layout

```text
fine_tuning/
  README.md
  open_source_llms_token_factory/
  customer_support_datalab/
  customer_support_standalone_colab/
  insurance_claims_finetuning/
  legal-tech-fine-tuning-nebius-cloud/
  legal-tech-fine-tuning-token-factory/
```
