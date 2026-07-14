from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).parents[1] / "app.py"


def test_initial_app_view_renders_without_provider_calls():
    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)

    assert not app.exception
    assert app.title[0].value == "FunASR + Nebius Voice Note Analyst"
    assert any(button.label == "Transcribe" for button in app.button)
    assert any(button.label == "Generate brief" for button in app.button)
    assert app.text_input[0].label == "Nebius API key (optional)"


def test_environment_api_key_is_not_written_into_password_widget(monkeypatch):
    secret = "environment-nebius-secret"
    monkeypatch.setenv("NEBIUS_API_KEY", secret)

    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)

    assert not app.exception
    assert app.text_input[0].value == ""
    assert secret not in str(app)
