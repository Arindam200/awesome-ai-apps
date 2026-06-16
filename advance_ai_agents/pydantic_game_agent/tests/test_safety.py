from app.safety import is_safe_generated_html, strip_markdown_fences, validate_generated_html


SAFE_GAME = """
<!doctype html>
<html>
<head>
  <title>Star Catch</title>
  <style>
    body { margin: 0; font-family: sans-serif; }
    canvas { display: block; }
  </style>
</head>
<body>
  <h1>Star Catch</h1>
  <p>Objective: move with arrow keys, catch stars, avoid comets. Score 10 to win. Press reset to restart.</p>
  <button id="reset">Reset</button>
  <canvas id="game" width="640" height="360"></canvas>
  <script>
    let score = 0;
    document.addEventListener('keydown', function (event) {
      score += event.key === 'ArrowRight' ? 1 : 0;
    });
    document.querySelector('#reset').addEventListener('click', function () {
      score = 0;
    });
  </script>
</body>
</html>
"""


def test_accepts_safe_standalone_game() -> None:
    assert validate_generated_html(SAFE_GAME) == []
    assert is_safe_generated_html(SAFE_GAME)


def test_rejects_external_script() -> None:
    html = SAFE_GAME.replace("<script>", '<script src="https://example.com/app.js">')
    assert "external script tags are not allowed" in validate_generated_html(html)


def test_rejects_network_calls() -> None:
    html = SAFE_GAME.replace("let score = 0;", "let score = 0; fetch('/api');")
    assert "network calls are not allowed" in validate_generated_html(html)


def test_rejects_navigation() -> None:
    html = SAFE_GAME.replace("let score = 0;", "let score = 0; window.location = 'https://example.com';")
    assert "page navigation is not allowed" in validate_generated_html(html)


def test_rejects_storage() -> None:
    html = SAFE_GAME.replace("let score = 0;", "let score = 0; localStorage.setItem('score', score);")
    assert "browser storage is not allowed" in validate_generated_html(html)


def test_rejects_embeds() -> None:
    html = SAFE_GAME.replace("<canvas", "<iframe></iframe><canvas")
    assert "embedded frames or plugins are not allowed" in validate_generated_html(html)


def test_rejects_incomplete_document() -> None:
    issues = validate_generated_html("<div>No game yet</div>")
    assert "game must be a complete HTML document" in issues
    assert "game should include embedded JavaScript" in issues


def test_rejects_truncated_html_document() -> None:
    html = """
    <!doctype html>
    <html>
    <body>
      <h1>Broken Space Game</h1>
      <script>
        const player = { x: 10
    """
    issues = validate_generated_html(html)

    assert "HTML appears truncated: missing closing script tag" in issues
    assert "HTML appears truncated: missing closing body tag" in issues
    assert "HTML appears truncated: missing closing html tag" in issues


def test_strips_markdown_html_fence() -> None:
    assert strip_markdown_fences("```html\n<p>Hello</p>\n```") == "<p>Hello</p>"
