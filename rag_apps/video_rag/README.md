# Video RAG — Gemini Native Multimodal + Weaviate + Nebius

Ask questions about a video and get answers with **clickable timestamp citations**. The whole pipeline runs on Google's native multimodal embedding model — no transcription service, no frame-level CLIP.

- **Embeddings**: Gemini `gemini-embedding-2-preview` (native multimodal — text + video in one space)
- **Vector DB**: Weaviate v4 (local docker or Weaviate Cloud)
- **LLM**: Nebius Token Factory (Qwen3-235B by default) via OpenAI-compatible API
- **UI**: Streamlit with an embedded video player that seeks to cited timestamps

## Why native multimodal?

Because `gemini-embedding-2-preview` embeds **video clips and text queries into the same vector space**, we don't need AssemblyAI for transcription or a separate image encoder for frames. We just slice the video into clips, embed each clip, and do one `near_vector` search at query time.

## Prerequisites

- Python 3.10+
- `ffmpeg` and `ffprobe` on PATH (`brew install ffmpeg` / `apt install ffmpeg`)
- [Nebius Token Factory](https://tokenfactory.nebius.com/) API key
- [Google AI Studio](https://aistudio.google.com/apikey) API key for Gemini
- Weaviate running locally (docker) or a Weaviate Cloud cluster

### Start Weaviate locally

```bash
docker run -d --name weaviate -p 8080:8080 -p 50051:50051 \
  -e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true \
  -e PERSISTENCE_DATA_PATH=/var/lib/weaviate \
  cr.weaviate.io/semitechnologies/weaviate:1.27.0
```

## Installation

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/rag_apps/video_rag

pip install -r requirements.txt
# or: uv sync

cp .env.example .env
# fill in NEBIUS_API_KEY, GEMINI_API_KEY,
# and optionally WEAVIATE_URL / WEAVIATE_API_KEY
```

## Usage

```bash
streamlit run main.py
```

1. Upload a video (mp4/mov/mkv/webm).
2. Pick a clip length (default 20s) and a Nebius answer model.
3. Click **Ingest video** — ffmpeg splits the video into clips, Gemini embeds each clip, Weaviate stores the vectors.
4. Ask questions. The pipeline embeds the query, searches Weaviate, and Nebius writes an answer with `[mm:ss]` citations.
5. Click any timestamp button to seek the embedded player to that moment.

## Architecture

```
Video ──► ffmpeg split (N-second clips) ──► Gemini gemini-embedding-2-preview (native video) ─┐
                                                                                               │
                                                                 Weaviate (VideoSegment, BYO)  ◄
                                                                                               │
Query ──► Gemini gemini-embedding-2-preview (text) ──► near_vector search ◄────────────────────┤
                                                        │                                      │
                                                        ▼                                      │
                                         Nebius Qwen3-235B (chat completions)                  │
                                                        │                                      │
                                   cited answer with [mm:ss] ◄─────────────────────────────────┘
```

Because text queries and video clips share the same embedding space, the retrieval is a single vector search — no hybrid fusion.

## Project layout

```
video_rag/
├── main.py             # Streamlit UI
├── ingest.py           # ffmpeg clip split + Gemini embed + Weaviate upsert
├── embeddings.py       # google-genai wrapper around gemini-embedding-2-preview
├── weaviate_store.py   # Weaviate v4 client + schema + search
├── rag.py              # retrieve + Nebius chat completion with citations
├── pyproject.toml
├── requirements.txt
└── .env.example
```

## Customization tips

- **Answer model**: swap `Qwen/Qwen3-235B-A22B` in the sidebar for any Nebius-served model.
- **Clip length**: shorter clips (10–15s) give tighter timestamps; longer clips (30–60s) cost fewer embedding calls.
- **Scope to one video**: multiple videos can be ingested; the UI scopes the agent's queries to the most recently ingested `video_id`.

## Troubleshooting

- `GEMINI_API_KEY is not set` → create one at https://aistudio.google.com/apikey.
- `weaviate.exceptions.WeaviateConnectionError` → make sure docker is running and `WEAVIATE_URL=http://localhost:8080`.
- `ffmpeg: command not found` → install ffmpeg and ensure it's on PATH.

## Contributing

Issues and PRs welcome. See the root `CONTRIBUTING.md`.
