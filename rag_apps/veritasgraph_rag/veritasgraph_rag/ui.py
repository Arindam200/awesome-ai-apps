"""Gradio chat + graph explorer UI."""

from __future__ import annotations

import gradio as gr

from .retriever import answer


def _ask(question: str, k: int, hops: int) -> tuple[str, str, str]:
    if not question.strip():
        return "Ask a question about your indexed documents.", "", ""
    result = answer(question, k=int(k), hops=int(hops))
    citations = "\n".join(f"- {c}" for c in result.citations) or "_(none)_"
    nodes = ", ".join(result.subgraph_nodes) or "_(none)_"
    return result.text, citations, nodes


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="VeritasGraph") as demo:
        gr.Markdown("# 🌳🔗 VeritasGraph\nGraph + tree retrieval with verifiable citations.")
        with gr.Row():
            with gr.Column(scale=3):
                question = gr.Textbox(label="Question", lines=2,
                                      placeholder="e.g. How does the procurement policy "
                                                  "treat split purchase orders?")
                with gr.Row():
                    k = gr.Slider(1, 20, value=6, step=1, label="Seed entities (k)")
                    hops = gr.Slider(0, 3, value=1, step=1, label="Graph hops")
                ask_btn = gr.Button("Ask", variant="primary")
            with gr.Column(scale=4):
                ans = gr.Markdown(label="Answer")
                cites = gr.Markdown(label="Citations")
                subgraph = gr.Markdown(label="Subgraph nodes")
        ask_btn.click(_ask, inputs=[question, k, hops], outputs=[ans, cites, subgraph])
    return demo


def main() -> None:
    build_ui().launch(server_name="0.0.0.0", server_port=7860)


if __name__ == "__main__":
    main()
