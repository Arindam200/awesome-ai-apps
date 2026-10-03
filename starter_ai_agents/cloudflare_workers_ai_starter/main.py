import os

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Available Llama models on Cloudflare Workers AI
MODELS = {
    "Llama 3.3 70B (Fast)": "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    "Llama 3.1 8B (Lightweight)": "@cf/meta/llama-3.1-8b-instruct",
    "Llama 3.2 11B Vision": "@cf/meta/llama-3.2-11b-vision-instruct",
}


def get_client(account_id: str, api_token: str) -> OpenAI:
    return OpenAI(
        api_key=api_token,
        base_url=f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
    )


# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cloudflare Workers AI Chat",
    page_icon="☁️",
    layout="centered",
)

st.title("☁️ Cloudflare Workers AI Starter")
st.caption(
    "A minimal chat agent powered by **Llama on Cloudflare Workers AI**. "
    "No GPU required — just a Cloudflare account."
)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔑 Credentials")

    account_id = st.text_input(
        "Cloudflare Account ID",
        value=os.getenv("CLOUDFLARE_ACCOUNT_ID", ""),
        help="dash.cloudflare.com → right sidebar → Account ID",
    )
    api_token = st.text_input(
        "Cloudflare API Token",
        type="password",
        value=os.getenv("CLOUDFLARE_API_TOKEN", ""),
        help="My Profile → API Tokens → Create Token (Workers AI template)",
    )

    st.divider()
    st.header("⚙️ Settings")

    model_label = st.selectbox("Model", list(MODELS.keys()))
    model_id = MODELS[model_label]

    system_prompt = st.text_area(
        "System Prompt",
        value="You are a helpful assistant.",
        height=80,
    )

    if st.button("🗑️ Clear chat"):
        st.session_state.messages = []

# ── Chat state ────────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Input ─────────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Message Llama…"):
    if not account_id or not api_token:
        st.error("Enter your Cloudflare Account ID and API token in the sidebar.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                client = get_client(account_id, api_token)
                response = client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        *st.session_state.messages,
                    ],
                )
                reply = response.choices[0].message.content
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
            except Exception as exc:
                st.error(f"Error: {exc}")
