import io
import os

import streamlit as st
from dotenv import load_dotenv
from pypdf import PdfReader

from crew import run_review

load_dotenv()


SAMPLE_CONTRACT = """MUTUAL NON-DISCLOSURE AGREEMENT

This Agreement is entered into as of January 1, 2026 by and between
Acme Corp. ("Disclosing Party") and Widget Inc. ("Receiving Party").

1. Confidential Information. All business, technical, and financial
information disclosed by either party shall be deemed Confidential
Information.

2. Term. This Agreement shall remain in effect for a period of five (5)
years and shall automatically renew for successive one-year terms
unless either party provides 90 days' written notice.

3. Obligations. The Receiving Party agrees to use Confidential
Information solely for the purpose of evaluating a potential business
relationship.

4. Indemnification. The Receiving Party shall indemnify and hold
harmless the Disclosing Party from any and all claims, losses, and
damages, without limitation, arising from any breach of this Agreement.

5. Limitation of Liability. IN NO EVENT SHALL THE DISCLOSING PARTY BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL DAMAGES.

6. Governing Law. This Agreement shall be governed by the laws of the
State of Delaware, without regard to conflicts of laws.

7. Assignment. The Receiving Party may not assign this Agreement
without prior written consent of the Disclosing Party.
"""


def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def main() -> None:
    st.set_page_config(
        page_title="Paralegal Crew",
        page_icon="⚖️",
        layout="wide",
    )
    st.title("⚖️ Paralegal Crew")
    st.caption(
        "CrewAI multi-agent contract review • clause extraction • risk scoring"
    )

    with st.sidebar:
        st.header("⚙️ Settings")
        model_id = st.selectbox(
            "Nebius model",
            [
                "Qwen/Qwen3-235B-A22B",
                "meta-llama/Llama-3.3-70B-Instruct",
                "deepseek-ai/DeepSeek-V3-0324",
            ],
            index=0,
        )
        party_perspective = st.text_input(
            "Review from the perspective of",
            value="the Receiving Party (our client)",
        )
        if not os.getenv("NEBIUS_API_KEY"):
            st.warning("Set NEBIUS_API_KEY in your .env file.")
        st.markdown("Get a key at [Nebius Token Factory](https://dub.sh/AIStudio).")
        st.markdown("---")
        st.markdown(
            "**The crew**\n\n"
            "1. 🧾 Clause Extractor\n"
            "2. 🛡️ Risk Analyst\n"
            "3. 📝 Senior Paralegal Reviewer"
        )

    tab_upload, tab_paste = st.tabs(["📎 Upload PDF", "📝 Paste Text"])
    contract_text = ""

    with tab_upload:
        uploaded = st.file_uploader(
            "Upload a contract (PDF)", type=["pdf"], key="pdf_upload"
        )
        if uploaded is not None:
            try:
                contract_text = extract_text_from_pdf(uploaded.read())
                st.success(f"Extracted {len(contract_text):,} characters.")
                with st.expander("Preview extracted text"):
                    st.text(contract_text[:3000] + ("..." if len(contract_text) > 3000 else ""))
            except Exception as exc:
                st.error(f"Could not parse PDF: {exc}")

    with tab_paste:
        pasted = st.text_area(
            "Paste contract text",
            value=SAMPLE_CONTRACT,
            height=320,
            key="pasted_contract",
        )
        if pasted.strip() and not contract_text:
            contract_text = pasted

    if st.button("Run Paralegal Crew", type="primary"):
        if not contract_text.strip():
            st.error("Provide a contract via upload or paste first.")
            return
        if not os.getenv("NEBIUS_API_KEY"):
            st.error("NEBIUS_API_KEY is missing.")
            return

        with st.spinner("Crew is reviewing the contract..."):
            memo = run_review(model_id, contract_text, party_perspective)

        st.markdown("### 📋 Contract Review Memo")
        st.markdown(memo)
        st.download_button(
            "Download memo (Markdown)",
            data=memo,
            file_name="contract_review_memo.md",
            mime="text/markdown",
        )


if __name__ == "__main__":
    main()
