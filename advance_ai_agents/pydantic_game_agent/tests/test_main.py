from app.main import app
from app.models import GameReview, GameSpec, GeneratedGame
from app.storage import get_game_html, load_games, save_game
from fastapi.testclient import TestClient
import pytest


def fake_game(prompt: str) -> GeneratedGame:
    return GeneratedGame(
        prompt=prompt,
        spec=GameSpec(
            title="Test Game",
            genre="Arcade",
            visual_style="Clean blocks",
            controls=["Arrow keys"],
            rules=["Catch points"],
            objective="Score points before the timer ends.",
            win_condition="Reach 10 score.",
            lose_condition="Timer reaches zero.",
            entities=["Player", "Point"],
            tone="Bright",
        ),
        html="""<!doctype html><html><head><style>body{font-family:sans-serif}</style></head><body><h1>Test Game</h1><button id="reset">Reset</button><script>document.addEventListener('keydown',()=>{});</script></body></html>""",
        review=GameReview(approved=True),
    )


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_generate_renders_mocked_game(monkeypatch, tmp_path) -> None:
    async def mock_generate_game(prompt: str) -> GeneratedGame:
        return fake_game(prompt)

    monkeypatch.setenv("GENERATED_GAMES_DIR", str(tmp_path))
    monkeypatch.setattr("app.main.generate_game", mock_generate_game)

    client = TestClient(app)
    response = client.post("/generate", data={"prompt": "make a test game"})

    assert response.status_code == 200
    assert "Test Game" in response.text
    assert "Open game" in response.text


def test_generate_renders_friendly_error(monkeypatch) -> None:
    async def mock_generate_game(prompt: str) -> GeneratedGame:
        raise RuntimeError("Missing NEBIUS_API_KEY")

    monkeypatch.setattr("app.main.generate_game", mock_generate_game)

    client = TestClient(app)
    response = client.post("/generate", data={"prompt": "make a test game"})

    assert response.status_code == 400
    assert "Missing NEBIUS_API_KEY" in response.text


def test_generate_rejection_does_not_save_game(monkeypatch, tmp_path) -> None:
    from app.agents import GenerationRejectedError

    async def mock_generate_game(prompt: str) -> GeneratedGame:
        raise GenerationRejectedError("Generated game did not pass review after one repair pass.")

    monkeypatch.setenv("GENERATED_GAMES_DIR", str(tmp_path))
    monkeypatch.setattr("app.main.generate_game", mock_generate_game)

    client = TestClient(app)
    response = client.post("/generate", data={"prompt": "make a broken test game"})

    assert response.status_code == 400
    assert "Reviewer still found issues after repair" in response.text
    assert load_games(root=tmp_path) == []


def test_play_latest_returns_404_before_generation(monkeypatch, tmp_path) -> None:
    import app.main as main

    monkeypatch.setenv("GENERATED_GAMES_DIR", str(tmp_path))
    main.LATEST_GAME = None
    client = TestClient(app)
    response = client.get("/play/latest")

    assert response.status_code == 404
    assert "No generated game yet" in response.text


def test_api_generate_stream_emits_stage_and_complete(monkeypatch, tmp_path) -> None:
    async def mock_generate_game(prompt, on_stage=None) -> GeneratedGame:
        if on_stage is not None:
            await on_stage("designer", "Game Designer Agent", "Designer is working", "Creates a typed game spec.")
            await on_stage("builder", "Game Builder Agent", "Builder is working", "Writes standalone HTML.")
        return fake_game(prompt)

    monkeypatch.setenv("GENERATED_GAMES_DIR", str(tmp_path))
    monkeypatch.setattr("app.main.generate_game", mock_generate_game)

    client = TestClient(app)
    response = client.get("/api/generate-stream", params={"prompt": "make a test game"})

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert '"type": "stage"' in response.text
    assert '"stage": "designer"' in response.text
    assert '"agent_name": "Game Designer Agent"' in response.text
    assert '"stage": "builder"' in response.text
    assert '"detail": "Writes standalone HTML."' in response.text
    assert '"type": "complete"' in response.text
    assert '"saved_game"' in response.text
    assert "Test Game" in response.text


def test_api_generate_stream_marks_rejected_draft_repairable(monkeypatch, tmp_path) -> None:
    import app.main as main
    from app.agents import GenerationRejectedError

    rejected = fake_game("make a rejected game")
    rejected.review = GameReview(approved=False, issues=["missing controls"])

    async def mock_generate_game(prompt, on_stage=None) -> GeneratedGame:
        raise GenerationRejectedError("Generated game did not pass review after one repair pass.", draft=rejected)

    monkeypatch.setenv("GENERATED_GAMES_DIR", str(tmp_path))
    monkeypatch.setattr("app.main.generate_game", mock_generate_game)
    main.LATEST_REJECTED_DRAFT = None

    client = TestClient(app)
    response = client.get("/api/generate-stream", params={"prompt": "make a rejected game"})

    assert response.status_code == 200
    assert '"type": "error"' in response.text
    assert '"repairable": true' in response.text
    assert main.LATEST_REJECTED_DRAFT == rejected
    assert load_games(root=tmp_path) == []


def test_api_repair_stream_repairs_latest_rejected_draft(monkeypatch, tmp_path) -> None:
    import app.main as main

    rejected = fake_game("make a rejected game")
    rejected.review = GameReview(approved=False, issues=["missing controls"])

    async def mock_repair_rejected_game(draft, on_stage=None) -> GeneratedGame:
        if on_stage is not None:
            await on_stage("repair", "Repair Agent", "Repairing draft", "Uses reviewer issues.")
        return fake_game(draft.prompt)

    monkeypatch.setenv("GENERATED_GAMES_DIR", str(tmp_path))
    monkeypatch.setattr("app.main.repair_rejected_game", mock_repair_rejected_game)
    main.LATEST_REJECTED_DRAFT = rejected

    client = TestClient(app)
    response = client.get("/api/repair-stream")

    assert response.status_code == 200
    assert '"type": "stage"' in response.text
    assert '"agent_name": "Repair Agent"' in response.text
    assert '"type": "complete"' in response.text
    assert '"saved_game"' in response.text
    assert main.LATEST_REJECTED_DRAFT is None
    assert load_games(root=tmp_path)[0].title == "Test Game"


def test_api_repair_stream_repairs_latest_game_with_review_issues(monkeypatch, tmp_path) -> None:
    import app.main as main

    needs_care = fake_game("make a flawed game")
    needs_care.review = GameReview(approved=True, issues=["overlay flashes for one frame"])

    async def mock_repair_rejected_game(draft, on_stage=None) -> GeneratedGame:
        assert draft.review.issues == ["overlay flashes for one frame"]
        return fake_game(draft.prompt)

    monkeypatch.setenv("GENERATED_GAMES_DIR", str(tmp_path))
    monkeypatch.setattr("app.main.repair_rejected_game", mock_repair_rejected_game)
    main.LATEST_REJECTED_DRAFT = None
    main.LATEST_GAME = needs_care

    client = TestClient(app)
    response = client.get("/api/repair-stream")

    assert response.status_code == 200
    assert '"type": "complete"' in response.text
    assert load_games(root=tmp_path)[0].title == "Test Game"


def test_api_repair_stream_without_draft_returns_error(monkeypatch, tmp_path) -> None:
    import app.main as main

    monkeypatch.setenv("GENERATED_GAMES_DIR", str(tmp_path))
    main.LATEST_REJECTED_DRAFT = None
    main.LATEST_GAME = None

    client = TestClient(app)
    response = client.get("/api/repair-stream")

    assert response.status_code == 200
    assert '"type": "error"' in response.text
    assert "No rejected draft is available to repair" in response.text


def test_root_renders_agent_run_ui_without_agent_output_card() -> None:
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "Generated Games" in response.text
    assert "Game Reviewer Agent" in response.text
    assert "Open any saved game in a new tab" in response.text
    assert "Multi-agent workflow" not in response.text
    assert "Agent output" not in response.text
    assert "Pydantic Game Agent" in response.text
    assert "Run repair agent" in response.text
    assert "data-repair-button" in response.text
    assert "Make a one-button game where I jump over blocks." in response.text
    assert "Make a reaction game where I click only when the screen turns green." in response.text
    assert "cozy cafe" not in response.text
    assert "neon maze" not in response.text


def test_root_keeps_run_console_available_after_latest_game() -> None:
    import app.main as main

    main.LATEST_GAME = fake_game("make a test game")

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert 'id="empty-preview"' in response.text
    assert 'id="preview-run"' in response.text
    assert 'id="game-frame"' in response.text
    assert "Test Game" in response.text


def test_play_latest_serves_generated_html(monkeypatch, tmp_path) -> None:
    import app.main as main

    monkeypatch.setenv("GENERATED_GAMES_DIR", str(tmp_path))
    main.LATEST_GAME = fake_game("make a test game")

    client = TestClient(app)
    response = client.get("/play/latest")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<h1>Test Game</h1>" in response.text


def test_invalid_nebius_model_env_falls_back_to_glm(monkeypatch) -> None:
    from app.agents import get_model_name

    monkeypatch.setenv("NEBIUS_MODEL", "nemotron super")

    assert get_model_name() == "zai-org/GLM-5.2"


def test_save_and_load_generated_game(tmp_path) -> None:
    record = save_game(fake_game("make a test game"), root=tmp_path)

    records = load_games(root=tmp_path)

    assert records[0].id == record.id
    assert records[0].title == "Test Game"
    assert get_game_html(record.id, root=tmp_path).startswith("<!doctype html>")


def test_save_rejects_unapproved_game(tmp_path) -> None:
    game = fake_game("make a broken game")
    game.review = GameReview(approved=False, issues=["broken"])

    with pytest.raises(ValueError, match="Only approved"):
        save_game(game, root=tmp_path)

    assert load_games(root=tmp_path) == []


def test_save_rejects_approved_game_with_review_issues(tmp_path) -> None:
    game = fake_game("make a needs care game")
    game.review = GameReview(approved=True, issues=["has a visual bug"])

    with pytest.raises(ValueError, match="Only approved"):
        save_game(game, root=tmp_path)

    assert load_games(root=tmp_path) == []


def test_saved_game_route_and_api(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("GENERATED_GAMES_DIR", str(tmp_path))
    record = save_game(fake_game("make a test game"), root=tmp_path)

    client = TestClient(app)
    game_response = client.get(f"/games/{record.id}")
    api_response = client.get("/api/games")

    assert game_response.status_code == 200
    assert "<h1>Test Game</h1>" in game_response.text
    assert api_response.status_code == 200
    assert api_response.json()["games"][0]["id"] == record.id


def test_unknown_saved_game_returns_404(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("GENERATED_GAMES_DIR", str(tmp_path))

    client = TestClient(app)
    response = client.get("/games/not-found")

    assert response.status_code == 404
    assert "Generated game not found" in response.text
