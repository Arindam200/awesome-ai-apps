from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.agents import DEFAULT_BASE_URL, GenerationRejectedError, generate_game, get_model_name, needs_repair, repair_rejected_game
from app.models import GeneratedGame
from app.storage import StoredGame, get_game_html, load_games, save_game


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Pydantic Game Agent")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

LATEST_GAME: GeneratedGame | None = None
LATEST_GAME_RECORD: StoredGame | None = None
LATEST_REJECTED_DRAFT: GeneratedGame | None = None

EXAMPLES = [
    "Make a one-button game where I jump over blocks.",
    "Make a click game where I pop green circles before time runs out.",
    "Make a tiny paddle game where I bounce one ball for points.",
    "Make a simple dodge game where I avoid falling squares.",
    "Make a reaction game where I click only when the screen turns green.",
]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "examples": EXAMPLES,
            "game": LATEST_GAME,
            "prompt": "",
            "error": None,
            "model": get_model_name(),
            "base_url": DEFAULT_BASE_URL,
            "saved_games": load_games(),
        },
    )


@app.get("/generate")
async def generate_get() -> RedirectResponse:
    return RedirectResponse("/", status_code=303)


@app.post("/generate", response_class=HTMLResponse)
async def generate(request: Request, prompt: str = Form(...)) -> HTMLResponse:
    global LATEST_GAME, LATEST_GAME_RECORD, LATEST_REJECTED_DRAFT

    try:
        LATEST_GAME = await generate_game(prompt)
        LATEST_GAME_RECORD = save_game(LATEST_GAME)
        LATEST_REJECTED_DRAFT = None
        error = None
    except GenerationRejectedError as exc:
        LATEST_REJECTED_DRAFT = exc.draft
        error = friendly_error(exc)
    except Exception as exc:
        error = friendly_error(exc)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "examples": EXAMPLES,
            "game": LATEST_GAME,
            "prompt": prompt,
            "error": error,
            "model": get_model_name(),
            "base_url": DEFAULT_BASE_URL,
            "saved_games": load_games(),
        },
        status_code=200 if error is None else 400,
    )


@app.post("/api/generate")
async def api_generate(prompt: str = Form(...)) -> JSONResponse:
    global LATEST_GAME, LATEST_GAME_RECORD, LATEST_REJECTED_DRAFT

    try:
        LATEST_GAME = await generate_game(prompt)
        LATEST_GAME_RECORD = save_game(LATEST_GAME)
        LATEST_REJECTED_DRAFT = None
    except GenerationRejectedError as exc:
        LATEST_REJECTED_DRAFT = exc.draft
        return JSONResponse({"error": friendly_error(exc), "repairable": exc.draft is not None}, status_code=400)
    except Exception as exc:
        return JSONResponse({"error": friendly_error(exc)}, status_code=400)
    return JSONResponse({"game": LATEST_GAME.model_dump(), "saved_game": LATEST_GAME_RECORD.model_dump()})


@app.get("/api/generate-stream")
async def api_generate_stream(prompt: str = Query(...)) -> StreamingResponse:
    async def event_stream():
        global LATEST_GAME, LATEST_GAME_RECORD, LATEST_REJECTED_DRAFT

        queue: asyncio.Queue[dict] = asyncio.Queue()

        async def on_stage(stage: str, agent_name: str, message: str, detail: str | None = None) -> None:
            await queue.put(
                {
                    "type": "stage",
                    "stage": stage,
                    "agent_name": agent_name,
                    "message": message,
                    "detail": detail,
                }
            )

        async def runner() -> None:
            global LATEST_GAME, LATEST_GAME_RECORD, LATEST_REJECTED_DRAFT
            try:
                LATEST_GAME = await generate_game(prompt, on_stage=on_stage)
                LATEST_GAME_RECORD = save_game(LATEST_GAME)
                LATEST_REJECTED_DRAFT = None
                await queue.put(
                    {
                        "type": "complete",
                        "game": LATEST_GAME.model_dump(),
                        "saved_game": LATEST_GAME_RECORD.model_dump(),
                    }
                )
            except GenerationRejectedError as exc:
                LATEST_REJECTED_DRAFT = exc.draft
                await queue.put({"type": "error", "error": friendly_error(exc), "repairable": exc.draft is not None})
            except Exception as exc:
                await queue.put({"type": "error", "error": friendly_error(exc), "repairable": False})

        task = asyncio.create_task(runner())
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
                if event["type"] in {"complete", "error"}:
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/repair-stream")
async def api_repair_stream() -> StreamingResponse:
    async def event_stream():
        global LATEST_GAME, LATEST_GAME_RECORD, LATEST_REJECTED_DRAFT

        queue: asyncio.Queue[dict] = asyncio.Queue()

        async def on_stage(stage: str, agent_name: str, message: str, detail: str | None = None) -> None:
            await queue.put(
                {
                    "type": "stage",
                    "stage": stage,
                    "agent_name": agent_name,
                    "message": message,
                    "detail": detail,
                }
            )

        async def runner() -> None:
            global LATEST_GAME, LATEST_GAME_RECORD, LATEST_REJECTED_DRAFT
            draft = LATEST_REJECTED_DRAFT
            if draft is None and LATEST_GAME is not None and needs_repair(LATEST_GAME.review, LATEST_GAME.safety_issues):
                draft = LATEST_GAME

            if draft is None:
                await queue.put({"type": "error", "error": "No rejected draft is available to repair.", "repairable": False})
                return

            try:
                LATEST_GAME = await repair_rejected_game(draft, on_stage=on_stage)
                LATEST_GAME_RECORD = save_game(LATEST_GAME)
                LATEST_REJECTED_DRAFT = None
                await queue.put(
                    {
                        "type": "complete",
                        "game": LATEST_GAME.model_dump(),
                        "saved_game": LATEST_GAME_RECORD.model_dump(),
                    }
                )
            except GenerationRejectedError as exc:
                LATEST_REJECTED_DRAFT = exc.draft
                await queue.put({"type": "error", "error": friendly_error(exc), "repairable": exc.draft is not None})
            except Exception as exc:
                await queue.put({"type": "error", "error": friendly_error(exc), "repairable": False})

        task = asyncio.create_task(runner())
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
                if event["type"] in {"complete", "error"}:
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/play/latest", response_class=HTMLResponse)
async def play_latest():
    if LATEST_GAME is not None:
        return HTMLResponse(LATEST_GAME.html)

    saved_games = load_games()
    if saved_games:
        html = get_game_html(saved_games[0].id)
        if html is not None:
            return HTMLResponse(html)

    if LATEST_GAME is None:
        return PlainTextResponse("No generated game yet. Generate a game first.", status_code=404)


@app.get("/games/{game_id}", response_class=HTMLResponse)
async def play_saved_game(game_id: str):
    html = get_game_html(game_id)
    if html is None:
        return PlainTextResponse("Generated game not found.", status_code=404)
    return HTMLResponse(html)


@app.get("/api/games")
async def api_games() -> JSONResponse:
    return JSONResponse({"games": [record.model_dump() for record in load_games()]})


def friendly_error(exc: Exception) -> str:
    message = str(exc)
    if isinstance(exc, GenerationRejectedError):
        return "Reviewer still found issues after repair. Run Repair Agent again, or try a simpler prompt."
    if "NEBIUS_API_KEY" in message:
        return "Missing NEBIUS_API_KEY. Export it, then restart the app."
    if "401" in message or "Unauthorized" in message:
        return "Nebius rejected the request. Check that NEBIUS_API_KEY is valid."
    if "finish_reason" in message or "content" in message.lower() or "length" in message.lower():
        return "GLM-5.2 did not return final game HTML. Try a shorter prompt or generate again."
    if "404" in message or "model" in message.lower():
        return f"The model request failed. Effective NEBIUS_MODEL is {get_model_name()}."
    return f"Could not generate the game: {message}"
