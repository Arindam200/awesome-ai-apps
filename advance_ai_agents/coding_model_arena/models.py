"""Model roster for the arena, sourced from the live Nebius Token Factory catalog.

Grouping and taglines exist purely to help a live audience read the roster at a
glance; the model IDs are what actually get sent to the API.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    id: str
    label: str
    tagline: str
    group: str


CONTESTANTS: list[ModelSpec] = [
    ModelSpec(
        id="moonshotai/Kimi-K2.7-Code",
        label="Kimi K2.7 Code",
        tagline="Coding specialist",
        group="Coding specialists",
    ),
    ModelSpec(
        id="zai-org/GLM-5.2",
        label="GLM-5.2",
        tagline="Coding-strong generalist",
        group="Coding specialists",
    ),
    ModelSpec(
        id="MiniMaxAI/MiniMax-M3",
        label="MiniMax M3",
        tagline="Agentic MoE",
        group="Frontier / OSS",
    ),
    ModelSpec(
        id="openai/gpt-oss-120b",
        label="GPT-OSS 120B",
        tagline="Latest open-weight OSS",
        group="Frontier / OSS",
    ),
    ModelSpec(
        id="Qwen/Qwen3.5-397B-A17B",
        label="Qwen3.5 397B",
        tagline="Flagship generalist",
        group="Frontier / OSS",
    ),
    ModelSpec(
        id="deepseek-ai/DeepSeek-V4-Pro",
        label="DeepSeek V4 Pro",
        tagline="Frontier reasoning",
        group="Frontier / OSS",
    ),
]

# Kept separate from CONTESTANTS so the judge isn't scoring a sibling of itself.
JUDGE_MODELS: list[ModelSpec] = [
    ModelSpec(
        id="Qwen/Qwen3-Next-80B-A3B-Thinking",
        label="Qwen3 Next 80B - Thinking",
        tagline="Fast, careful reasoning",
        group="Judge",
    ),
    ModelSpec(
        id="nvidia/Llama-3_1-Nemotron-Ultra-253B-v1",
        label="Nemotron Ultra 253B",
        tagline="Deep chain-of-thought grading",
        group="Judge",
    ),
    ModelSpec(
        id="Qwen/Qwen3-235B-A22B-Instruct-2507",
        label="Qwen3 235B Instruct",
        tagline="Large flagship generalist judge",
        group="Judge",
    ),
    ModelSpec(
        id="NousResearch/Hermes-4-405B",
        label="Hermes 4 405B",
        tagline="Independent lineage, second opinion",
        group="Judge",
    ),
]

# An instruction-tuned model is more reliable for the strict JSON judge schema
# than a thinking model whose reasoning can consume the response budget.
DEFAULT_JUDGE = "Qwen/Qwen3-235B-A22B-Instruct-2507"

DEFAULT_SELECTION = [
    "moonshotai/Kimi-K2.7-Code",
    "zai-org/GLM-5.2",
    "MiniMaxAI/MiniMax-M3",
    "openai/gpt-oss-120b",
]


def by_id(model_id: str) -> ModelSpec:
    for m in CONTESTANTS:
        if m.id == model_id:
            return m
    return ModelSpec(id=model_id, label=model_id, tagline="", group="Custom")
