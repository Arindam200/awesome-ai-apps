import os
import json
import re
import shutil
import tempfile

import streamlit as st
from dotenv import load_dotenv
from llama_index.core import Settings, SimpleDirectoryReader, VectorStoreIndex
from llama_index.embeddings.nebius import NebiusEmbedding
from llama_index.llms.nebius import NebiusLLM
from openai import OpenAI

load_dotenv()

NEBIUS_BASE_URL = "https://api.studio.nebius.com/v1/"
DEFAULT_GEN_MODEL = "Qwen/Qwen3-235B-A22B"
DEFAULT_VERIFIER_MODEL = "meta-llama/Meta-Llama-3.1-70B-Instruct"
DEFAULT_EMBED_MODEL = "BAAI/bge-en-icl"


def get_nebius_client() -> OpenAI:
    api_key = os.getenv("NEBIUS_API_KEY")
    if not api_key:
        raise RuntimeError("NEBIUS_API_KEY is not set")
    return OpenAI(base_url=NEBIUS_BASE_URL, api_key=api_key)


def build_index(documents, embed_model: str, gen_model: str):
    Settings.llm = NebiusLLM(model=gen_model, api_key=os.getenv("NEBIUS_API_KEY"))
    Settings.embed_model = NebiusEmbedding(
        model_name=embed_model, api_key=os.getenv("NEBIUS_API_KEY")
    )
    return VectorStoreIndex.from_documents(documents)


def retrieve_context(index, query: str, top_k: int = 5):
    retriever = index.as_retriever(similarity_top_k=top_k)
    nodes = retriever.retrieve(query)
    sources = []
    for i, node in enumerate(nodes, start=1):
        meta = node.node.metadata or {}
        sources.append(
            {
                "id": i,
                "text": node.node.get_content(),
                "score": float(node.score) if node.score is not None else 0.0,
                "file": meta.get("file_name", "unknown"),
                "page": meta.get("page_label", meta.get("page", "?")),
            }
        )
    return sources


def generate_cited_answer(client: OpenAI, model: str, query: str, sources: list) -> str:
    context_block = "\n\n".join(
        f"[{s['id']}] (file: {s['file']}, page: {s['page']})\n{s['text']}" for s in sources
    )
    system = (
        "You are a careful research assistant. Answer ONLY using the provided sources. "
        "After every factual sentence, add inline citations like [1] or [2,3] referencing the source IDs. "
        "If the sources are insufficient, say so explicitly. Do not invent facts or sources."
    )
    user = f"Question: {query}\n\nSources:\n{context_block}\n\nWrite a concise, cited answer."
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.1,
    )
    raw = resp.choices[0].message.content or ""
    return re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()


def split_claims(answer: str) -> list:
    cleaned = re.sub(r"\s+", " ", answer).strip()
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [p.strip() for p in parts if len(p.strip()) > 5]


def extract_cited_ids(claim: str) -> list:
    ids = []
    for match in re.findall(r"\[([0-9,\s]+)\]", claim):
        for num in match.split(","):
            num = num.strip()
            if num.isdigit():
                ids.append(int(num))
    return sorted(set(ids))


def verify_claim(client: OpenAI, model: str, claim: str, cited_sources: list) -> dict:
    if not cited_sources:
        return {"verdict": "UNSUPPORTED", "confidence": 0.9, "reason": "No citation provided."}
    evidence = "\n\n".join(f"[{s['id']}]: {s['text']}" for s in cited_sources)
    prompt = (
        "You are a strict fact-checker. Decide whether the CLAIM is entailed by the EVIDENCE.\n"
        "Return strict JSON with keys: verdict (SUPPORTED | PARTIAL | UNSUPPORTED | CONTRADICTED), "
        "confidence (0-1 float), reason (<=25 words).\n\n"
        f"CLAIM: {claim}\n\nEVIDENCE:\n{evidence}\n\nJSON:"
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Return ONLY valid JSON, no prose."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
    )
    text = resp.choices[0].message.content or "{}"
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        data = json.loads(match.group(0) if match else text)
    except Exception:
        data = {"verdict": "UNSUPPORTED", "confidence": 0.5, "reason": "Verifier parse error"}
    data["verdict"] = str(data.get("verdict", "UNSUPPORTED")).upper()
    try:
        data["confidence"] = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
    except Exception:
        data["confidence"] = 0.5
    return data


def compute_trust_score(verifications: list) -> float:
    if not verifications:
        return 0.0
    weights = {"SUPPORTED": 1.0, "PARTIAL": 0.5, "UNSUPPORTED": 0.0, "CONTRADICTED": -0.5}
    total = sum(weights.get(v["result"]["verdict"], 0.0) * v["result"]["confidence"] for v in verifications)
    max_total = sum(v["result"]["confidence"] for v in verifications) or 1.0
    score = (total / max_total) * 100
    return max(0.0, min(100.0, score))


def verdict_badge(verdict: str) -> str:
    colors = {
        "SUPPORTED": "#16a34a",
        "PARTIAL": "#ca8a04",
        "UNSUPPORTED": "#dc2626",
        "CONTRADICTED": "#7f1d1d",
    }
    color = colors.get(verdict, "#6b7280")
    return f"<span style='background:{color};color:white;padding:2px 8px;border-radius:10px;font-size:12px;'>{verdict}</span>"


def main():
    st.set_page_config(page_title="Trustworthy RAG", layout="wide")
    st.title("Trustworthy RAG")
    st.caption(
        "A RAG pipeline with citation verification and hallucination scoring. Powered by Nebius Token Factory."
    )

    if "index" not in st.session_state:
        st.session_state.index = None
    if "temp_dir" not in st.session_state:
        st.session_state.temp_dir = None
    if "current_pdf" not in st.session_state:
        st.session_state.current_pdf = None

    with st.sidebar:
        st.header("Configuration")
        gen_model = st.selectbox(
            "Answer Model",
            [DEFAULT_GEN_MODEL, "deepseek-ai/DeepSeek-V3", "meta-llama/Meta-Llama-3.1-70B-Instruct"],
            index=0,
        )
        verifier_model = st.selectbox(
            "Verifier Model",
            [DEFAULT_VERIFIER_MODEL, "Qwen/Qwen3-235B-A22B", "deepseek-ai/DeepSeek-V3"],
            index=0,
        )
        top_k = st.slider("Top-K retrieved chunks", 2, 10, 5)
        st.divider()
        st.subheader("Upload PDF")
        uploaded_file = st.file_uploader("Choose a PDF", type="pdf")

        if uploaded_file is not None and uploaded_file != st.session_state.current_pdf:
            if not os.getenv("NEBIUS_API_KEY"):
                st.error("Missing NEBIUS_API_KEY")
                st.stop()
            st.session_state.current_pdf = uploaded_file
            if st.session_state.temp_dir:
                shutil.rmtree(st.session_state.temp_dir, ignore_errors=True)
            st.session_state.temp_dir = tempfile.mkdtemp()
            file_path = os.path.join(st.session_state.temp_dir, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            with st.spinner("Indexing document..."):
                docs = SimpleDirectoryReader(st.session_state.temp_dir).load_data()
                st.session_state.index = build_index(docs, DEFAULT_EMBED_MODEL, gen_model)
            st.success("Document indexed")

    query = st.text_input("Ask a question about your document")
    run = st.button("Run Trustworthy RAG", type="primary", disabled=st.session_state.index is None)

    if run and query:
        client = get_nebius_client()

        with st.spinner("Retrieving relevant context..."):
            sources = retrieve_context(st.session_state.index, query, top_k=top_k)

        with st.spinner("Generating cited answer..."):
            answer = generate_cited_answer(client, gen_model, query, sources)

        st.subheader("Answer")
        st.markdown(answer)

        claims = split_claims(answer)
        verifications = []
        with st.spinner(f"Verifying {len(claims)} claim(s)..."):
            for claim in claims:
                cited_ids = extract_cited_ids(claim)
                cited_sources = [s for s in sources if s["id"] in cited_ids]
                result = verify_claim(client, verifier_model, claim, cited_sources)
                verifications.append({"claim": claim, "cited_ids": cited_ids, "result": result})

        trust_score = compute_trust_score(verifications)
        hallucination_score = 100.0 - trust_score

        col1, col2, col3 = st.columns(3)
        col1.metric("Trust Score", f"{trust_score:.1f}%")
        col2.metric("Hallucination Risk", f"{hallucination_score:.1f}%")
        col3.metric("Claims Checked", len(verifications))

        st.subheader("Claim-by-claim verification")
        for i, v in enumerate(verifications, start=1):
            verdict = v["result"]["verdict"]
            st.markdown(
                f"**{i}.** {verdict_badge(verdict)} &nbsp; "
                f"confidence: `{v['result']['confidence']:.2f}` &nbsp; "
                f"citations: `{v['cited_ids'] or 'none'}`",
                unsafe_allow_html=True,
            )
            st.markdown(f"> {v['claim']}")
            st.caption(f"Reason: {v['result'].get('reason', '')}")
            st.divider()

        with st.expander("Retrieved sources"):
            for s in sources:
                st.markdown(
                    f"**[{s['id']}]** `{s['file']}` — page {s['page']} — score {s['score']:.3f}"
                )
                st.text(s["text"][:600] + ("..." if len(s["text"]) > 600 else ""))


if __name__ == "__main__":
    main()
