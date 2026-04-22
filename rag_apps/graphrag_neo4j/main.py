import os
import json
import re
from typing import List

import streamlit as st
from dotenv import load_dotenv
from neo4j import GraphDatabase
from openai import OpenAI
import PyPDF2

load_dotenv()

NEBIUS_BASE_URL = "https://api.studio.nebius.com/v1/"
DEFAULT_EXTRACTION_MODEL = "Qwen/Qwen3-235B-A22B"
DEFAULT_ANSWER_MODEL = "Qwen/Qwen3-235B-A22B"


def get_llm_client() -> OpenAI:
    api_key = os.getenv("NEBIUS_API_KEY")
    if not api_key:
        raise RuntimeError("NEBIUS_API_KEY is not set")
    return OpenAI(base_url=NEBIUS_BASE_URL, api_key=api_key)


def get_neo4j_driver():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USERNAME", "neo4j")
    pwd = os.getenv("NEO4J_PASSWORD")
    if not uri or not pwd:
        raise RuntimeError("NEO4J_URI and NEO4J_PASSWORD must be set")
    return GraphDatabase.driver(uri, auth=(user, pwd))


EXTRACTION_PROMPT = """You are an information extraction engine that builds a knowledge graph.
From the text below, extract entities and the relationships between them.

Return STRICT JSON with this schema, nothing else:
{
  "entities": [{"id": "short_snake_case_id", "name": "Canonical Name", "type": "Person|Organization|Location|Product|Concept|Event|Other"}],
  "relationships": [{"source": "source_entity_id", "target": "target_entity_id", "type": "UPPER_SNAKE_CASE_VERB", "description": "short context"}]
}

Rules:
- Reuse the same id for the same real-world entity.
- Keep types to the enum above.
- Relationship type should be a short verb phrase (e.g., WORKS_AT, FOUNDED, LOCATED_IN).
- Only include facts explicitly supported by the text.

Text:
\"\"\"{chunk}\"\"\"
"""


CYPHER_PROMPT = """You translate a user question into a single read-only Cypher query for Neo4j.

Graph schema:
- (:Entity {{id, name, type}})
- (:Entity)-[:REL {{type, description}}]->(:Entity)

Rules:
- Return ONLY the Cypher query. No explanation, no code fences.
- Query must be read-only (MATCH/OPTIONAL MATCH/RETURN only). Never write.
- Match entity names case-insensitively using toLower(e.name) CONTAINS toLower('...').
- Include related entities and relationship types in the RETURN.
- LIMIT 25.

Question: {question}
"""


ANSWER_PROMPT = """Answer the user's question using ONLY the graph context below.
If the context is insufficient, say so honestly.

Graph context (subgraph triples):
{context}

Question: {question}

Answer:"""


def strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def extract_json(text: str) -> dict:
    text = strip_think(text)
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model output")
    return json.loads(match.group(0))


def chunk_text(text: str, size: int = 2500, overlap: int = 200) -> List[str]:
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


def read_pdf(file) -> str:
    reader = PyPDF2.PdfReader(file)
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def extract_graph(client: OpenAI, model: str, chunk: str) -> dict:
    resp = client.chat.completions.create(
        model=model,
        temperature=0.0,
        messages=[
            {"role": "system", "content": "You output strict JSON only."},
            {"role": "user", "content": EXTRACTION_PROMPT.format(chunk=chunk)},
        ],
    )
    return extract_json(resp.choices[0].message.content or "")


def ingest_graph(driver, graph: dict, source: str):
    entities = graph.get("entities", [])
    rels = graph.get("relationships", [])
    with driver.session() as session:
        session.run(
            """
            UNWIND $entities AS e
            MERGE (n:Entity {id: e.id})
            SET n.name = coalesce(e.name, n.name),
                n.type = coalesce(e.type, n.type),
                n.source = $source
            """,
            entities=entities,
            source=source,
        )
        session.run(
            """
            UNWIND $rels AS r
            MATCH (a:Entity {id: r.source})
            MATCH (b:Entity {id: r.target})
            MERGE (a)-[rel:REL {type: r.type}]->(b)
            SET rel.description = r.description, rel.source = $source
            """,
            rels=rels,
            source=source,
        )


def ensure_constraints(driver):
    with driver.session() as session:
        session.run("CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE")


def generate_cypher(client: OpenAI, model: str, question: str) -> str:
    resp = client.chat.completions.create(
        model=model,
        temperature=0.0,
        messages=[
            {"role": "system", "content": "You output a single Cypher query, nothing else."},
            {"role": "user", "content": CYPHER_PROMPT.format(question=question)},
        ],
    )
    cypher = strip_think(resp.choices[0].message.content or "")
    cypher = re.sub(r"^```(?:cypher)?|```$", "", cypher, flags=re.MULTILINE).strip()
    return cypher


def is_safe_read_cypher(cypher: str) -> bool:
    banned = ["CREATE", "MERGE", "DELETE", "SET", "REMOVE", "DROP", "CALL DBMS", "LOAD CSV"]
    upper = cypher.upper()
    return not any(b in upper for b in banned)


def run_cypher(driver, cypher: str) -> list:
    with driver.session() as session:
        result = session.run(cypher)
        return [record.data() for record in result]


def entity_fallback_search(driver, question: str) -> list:
    terms = [t for t in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", question) if t.lower() not in {"what", "who", "where", "when", "which", "how", "the", "and", "for", "with", "does", "did", "are", "was"}]
    if not terms:
        return []
    cypher = """
    UNWIND $terms AS t
    MATCH (a:Entity)
    WHERE toLower(a.name) CONTAINS toLower(t)
    OPTIONAL MATCH (a)-[r:REL]-(b:Entity)
    RETURN a.name AS source, a.type AS source_type,
           r.type AS relation, r.description AS description,
           b.name AS target, b.type AS target_type
    LIMIT 50
    """
    with driver.session() as session:
        result = session.run(cypher, terms=terms)
        return [record.data() for record in result]


def format_context(rows: list) -> str:
    if not rows:
        return "(no matching subgraph found)"
    lines = []
    for r in rows:
        lines.append(json.dumps(r, default=str))
    return "\n".join(lines)


def answer_question(client: OpenAI, model: str, question: str, context: str) -> str:
    resp = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": "You are a careful assistant that grounds answers in the provided graph context."},
            {"role": "user", "content": ANSWER_PROMPT.format(context=context, question=question)},
        ],
    )
    return strip_think(resp.choices[0].message.content or "")


def main():
    st.set_page_config(page_title="GraphRAG • Neo4j + Nebius", layout="wide")
    st.title("GraphRAG with Neo4j and Nebius Token Factory")
    st.caption("Extract entities & relationships → store in Neo4j → retrieve via Cypher → answer.")

    with st.sidebar:
        st.subheader("Models")
        extraction_model = st.selectbox(
            "Extraction model",
            ["Qwen/Qwen3-235B-A22B", "deepseek-ai/DeepSeek-V3", "meta-llama/Meta-Llama-3.1-70B-Instruct"],
            index=0,
        )
        answer_model = st.selectbox(
            "Answer model",
            ["Qwen/Qwen3-235B-A22B", "deepseek-ai/DeepSeek-V3", "meta-llama/Meta-Llama-3.1-70B-Instruct"],
            index=0,
        )
        st.divider()
        st.subheader("Connection")
        st.code(
            f"NEO4J_URI: {'set' if os.getenv('NEO4J_URI') else 'missing'}\n"
            f"NEBIUS_API_KEY: {'set' if os.getenv('NEBIUS_API_KEY') else 'missing'}"
        )
        if st.button("Reset graph (DANGER)"):
            try:
                driver = get_neo4j_driver()
                with driver.session() as s:
                    s.run("MATCH (n) DETACH DELETE n")
                st.success("Graph cleared.")
            except Exception as e:
                st.error(str(e))

    tab_ingest, tab_query = st.tabs(["1. Ingest", "2. Query"])

    with tab_ingest:
        st.write("Upload a PDF or paste text. Entities and relationships will be extracted and written to Neo4j.")
        uploaded = st.file_uploader("PDF file", type="pdf")
        text_input = st.text_area("Or paste text", height=200)

        if st.button("Build knowledge graph", type="primary"):
            try:
                client = get_llm_client()
                driver = get_neo4j_driver()
                ensure_constraints(driver)

                if uploaded is not None:
                    raw = read_pdf(uploaded)
                    source = uploaded.name
                else:
                    raw = text_input
                    source = "pasted_text"

                if not raw.strip():
                    st.warning("Please provide some input.")
                    st.stop()

                chunks = chunk_text(raw)
                progress = st.progress(0.0, text="Extracting graph...")
                total_entities, total_rels = 0, 0

                for i, ch in enumerate(chunks):
                    graph = extract_graph(client, extraction_model, ch)
                    ingest_graph(driver, graph, source)
                    total_entities += len(graph.get("entities", []))
                    total_rels += len(graph.get("relationships", []))
                    progress.progress((i + 1) / len(chunks), text=f"Chunk {i+1}/{len(chunks)}")

                st.success(f"Ingested {total_entities} entities and {total_rels} relationships from {len(chunks)} chunk(s).")
            except Exception as e:
                st.error(f"Error: {e}")

    with tab_query:
        st.write("Ask a question. The app turns it into Cypher, runs it against Neo4j, and uses the subgraph as context.")
        question = st.text_input("Your question")
        use_llm_cypher = st.checkbox("Use LLM-generated Cypher (else entity-keyword search)", value=True)

        if st.button("Ask", type="primary") and question:
            try:
                client = get_llm_client()
                driver = get_neo4j_driver()

                rows = []
                cypher = None
                if use_llm_cypher:
                    cypher = generate_cypher(client, answer_model, question)
                    if not is_safe_read_cypher(cypher):
                        st.warning("Generated Cypher was not read-only; falling back to keyword search.")
                        rows = entity_fallback_search(driver, question)
                    else:
                        try:
                            rows = run_cypher(driver, cypher)
                        except Exception as e:
                            st.warning(f"Cypher failed ({e}); falling back to keyword search.")
                            rows = entity_fallback_search(driver, question)
                else:
                    rows = entity_fallback_search(driver, question)

                context = format_context(rows)
                with st.expander("Retrieved subgraph"):
                    if cypher:
                        st.code(cypher, language="cypher")
                    st.json(rows)

                answer = answer_question(client, answer_model, question, context)
                st.markdown("### Answer")
                st.markdown(answer)
            except Exception as e:
                st.error(f"Error: {e}")


if __name__ == "__main__":
    main()
