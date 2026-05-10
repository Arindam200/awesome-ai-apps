# Customer Support Fine-Tuning with Nebius Data Lab

Step-by-step customer-support fine-tuning tutorial using Nebius Data Lab for dataset processing and teacher-model batch generation before LoRA training.

## Files

- [Notebook](customer_support_datalab_finetuning_tutorial.ipynb)

## Open In Colab

- [Launch notebook](https://colab.research.google.com/github/Arindam200/awesome-ai-apps/blob/main/fine_tuning/customer_support_datalab/customer_support_datalab_finetuning_tutorial.ipynb)

## Workflow

- Generate baseline customer-support interactions
- Upload the raw dataset to Data Lab
- Run batch inference with a stronger teacher model
- Filter and reformat outputs into training data
- Fine-tune a smaller model with LoRA
- Deploy and smoke test the custom model
