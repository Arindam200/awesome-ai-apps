#!/usr/bin/env python3
"""Gradio chat: compare base Llama 3.1 8B vs deployed fine-tuned LoRA on Nebius Token Factory."""

from __future__ import annotations

import os

import gradio as gr
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE_URL = "https://api.tokenfactory.nebius.com/v1/"

# Nebius chat inference registry uses the Meta-prefixed id (same as notebook CHAT_BASE_MODEL).
_DEFAULT_CHAT_BASE = "meta-llama/Meta-Llama-3.1-8B-Instruct"

CLAIMS_SYSTEM_PROMPT = (
    "You are a helpful insurance assistant. "
    "You explain coverage, claims intake, deductibles, and next steps clearly and accurately. "
    "You do not provide legal advice or guarantee claim outcomes. "
    "When policy-specific details are needed, direct the customer to their policy documents or a licensed adjuster. "
    "Be concise, empathetic, and consistent with standard P&C insurance terminology."
)


def chat_base_model() -> str:
    """Base model id for OpenAI-compatible chat on Token Factory (override via CHAT_BASE_MODEL or BASE_MODEL_NAME)."""
    for key in ("CHAT_BASE_MODEL", "BASE_MODEL_NAME"):
        v = os.environ.get(key, "").strip()
        if v:
            return v
    return _DEFAULT_CHAT_BASE


def custom_model_name() -> str:
    """Full deployed LoRA name from notebook Step 7 (CUSTOM_MODEL_NAME)."""
    return os.environ.get("CUSTOM_MODEL_NAME", "").strip()


def get_client() -> OpenAI:
    key = os.environ.get("NEBIUS_API_KEY")
    if not key:
        raise RuntimeError("Set NEBIUS_API_KEY in .env or the environment.")
    return OpenAI(base_url=BASE_URL, api_key=key)


def complete(model: str, message: str, history: list) -> str:
    """Single path for chat completions: system prompt + history + latest user message."""
    client = get_client()
    messages = [{"role": "system", "content": CLAIMS_SYSTEM_PROMPT}]
    for turn in history or []:
        if isinstance(turn, (list, tuple)) and len(turn) >= 2:
            messages.append({"role": "user", "content": str(turn[0])})
            messages.append({"role": "assistant", "content": str(turn[1])})
    messages.append({"role": "user", "content": message})
    resp = client.chat.completions.create(model=model, messages=messages, max_tokens=512)
    return (resp.choices[0].message.content or "").strip()


def respond_base(message: str, history: list) -> tuple[str, list]:
    text = complete(chat_base_model(), message, history)
    history = history or []
    return "", history + [[message, text]]


def respond_custom(message: str, history: list) -> tuple[str, list]:
    custom = custom_model_name()
    if not custom:
        raise RuntimeError(
            "Set CUSTOM_MODEL_NAME in .env to the full deployed model name from the notebook (Step 7)."
        )
    text = complete(custom, message, history)
    history = history or []
    return "", history + [[message, text]]


def compare_side_by_side(message: str) -> tuple[str, str]:
    """Same `complete()` path as the chat tabs: one turn, empty history (no duplicate request code)."""
    custom = custom_model_name()
    if not custom:
        raise RuntimeError("Set CUSTOM_MODEL_NAME in .env (from notebook Step 7).")
    base_id = chat_base_model()
    msg = (message or "").strip()
    if not msg:
        return "", ""
    base_text = complete(base_id, msg, [])
    custom_text = complete(custom, msg, [])
    return base_text, custom_text


def build_ui() -> gr.Blocks:
    base_id = chat_base_model()
    has_custom = bool(custom_model_name())
    intro = (
        "# Insurance chatbot — Nebius Token Factory\n\n"
        f"- **Base model:** `{base_id}` (set `CHAT_BASE_MODEL` or `BASE_MODEL_NAME` in `.env` to override)\n"
    )
    if has_custom:
        intro += f"- **Fine-tuned:** `{custom_model_name()}` (`CUSTOM_MODEL_NAME`)\n\n"
    else:
        intro += (
            "- **Fine-tuned:** not set — add **`CUSTOM_MODEL_NAME`** to `.env` (from notebook Step 7).\n\n"
        )
    intro += "Set **`NEBIUS_API_KEY`** in `.env`. See `.env.example`."

    with gr.Blocks(title="Insurance Claims — Base vs Fine-tuned (Nebius)") as demo:
        gr.Markdown(intro)
        with gr.Accordion("System prompt", open=False):
            gr.Markdown(CLAIMS_SYSTEM_PROMPT)

        with gr.Tabs():
            with gr.Tab("Base model"):
                cb1 = gr.Chatbot(height=400, label="Base 8B")
                msg1 = gr.Textbox(label="Your message", lines=2)
                btn1 = gr.Button("Send")
                sub1 = [msg1, cb1]
                btn1.click(respond_base, sub1, [msg1, cb1])
                msg1.submit(respond_base, sub1, [msg1, cb1])

            with gr.Tab("Fine-tuned (custom)"):
                cb2 = gr.Chatbot(height=400, label="Fine-tuned LoRA")
                msg2 = gr.Textbox(label="Your message", lines=2)
                btn2 = gr.Button("Send")
                sub2 = [msg2, cb2]
                btn2.click(respond_custom, sub2, [msg2, cb2])
                msg2.submit(respond_custom, sub2, [msg2, cb2])

            with gr.Tab("Side-by-side (one shot)"):
                inp = gr.Textbox(label="Your message", lines=3)
                out_base = gr.Textbox(label="Base model", lines=12)
                out_custom = gr.Textbox(label="Fine-tuned model", lines=12)
                btn = gr.Button("Compare")
                btn.click(compare_side_by_side, [inp], [out_base, out_custom])

    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.launch(server_name="127.0.0.1", server_port=7860)
