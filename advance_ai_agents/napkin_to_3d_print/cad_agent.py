"""The sketch -> CadQuery -> render -> critique loop.

Kimi writes a parametric CadQuery module, we build it in a subprocess, render
four views, and show Kimi its own render next to the sketch. It either signs off
or sends corrected code. Build errors go back to Kimi with the traceback.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from openai import OpenAI

from kimi import stream_chat
from render import mesh_report, render_views

RUNNER = Path(__file__).parent / "cad_runner.py"
BUILD_TIMEOUT_S = 120

SYSTEM_PROMPT = """You are Napkin, an expert mechanical designer and CadQuery programmer. You turn rough hand-drawn sketches into accurate, 3D-printable parametric CAD.

## Output contract
Write one Python module:

```python
import cadquery as cq
import math  # optional

PARAMS = {
    "width": {"value": 80.0, "min": 40.0, "max": 160.0, "step": 1.0, "unit": "mm", "label": "Width"},
    "holes": {"value": 2, "min": 0, "max": 6, "step": 1, "type": "int", "label": "Hole count"},
}

def build(p):
    # p maps every PARAMS key to its current number
    ...
    return part  # a cq.Workplane holding ONE solid
```

## Rules
- Units are millimetres. Z is up. Model the part in its natural printing orientation, resting on a flat face on the XY plane.
- Expose 3-8 PARAMS a person would actually want to tweak (overall size, wall thickness, angle, hole diameter, counts). Every dimension in build() must derive from p[...] so sliders always produce a valid part. Choose min/max so every combination stays valid (a hole never exceeds its wall, a slot never cuts the part in two).
- Union everything into a single solid. No floating pieces, no zero-thickness faces.
- Printability: walls >= 1.6 mm, a flat stable base, avoid unsupported overhangs steeper than 45 degrees where the design allows.
- Read any dimensions written on the sketch and honour them exactly. Otherwise infer realistic real-world sizes from the object's purpose (a phone stand must hold a ~75 mm wide, ~9 mm thick phone; an M4 screw needs a ~4.4 mm clearance hole).
- Fillets and chamfers fail easily in OpenCascade. Apply them last, keep radii below half the thinnest adjacent wall, and use the helpers `safe_fillet(wp, radius, selector=None)` and `safe_chamfer(wp, length, selector=None)`. They are already in scope (don't import or define them) and return the part unchanged if the operation fails.
- Only import cadquery, math and numpy. No file I/O, no exporters, no print(), no show_object.
- Prefer robust operations: box, cylinder, polyline().close().extrude(), revolve, hole, cutThruAll, union, cut, mirror. Avoid loft and sweep unless the shape needs them.

## Response format
## Interpretation
- **Object:** what it is and what it's for
- **Features:** every feature you see (holes, slots, lips, angles, ribs, cutouts)
- **Dimensions:** the numbers you read or assumed

Then exactly one ```python code block with the complete module."""

CRITIQUE_PROMPT = """Image 1 is the user's sketch. Image 2 is your current CAD model rendered from the front (looking along +Y), the right (looking along -X), the top, and an isometric angle, with the measured size printed above it.

Measured: {size} mm (X x Y x Z), volume {volume} mm³, {solids} solid(s), valid={valid}, watertight={watertight}.
User notes: {notes}

Current code:
```python
{code}
```

Review the model against the sketch like a strict design reviewer:
1. Overall shape and proportions.
2. Every feature in the sketch is present, in the right place, at the right size (holes, slots, cutouts, lips, angles, ribs).
3. Nothing extra that the sketch doesn't show.
4. Printability: flat base, walls >= 1.6 mm, a single solid.

Answer in exactly this format:
VERDICT: PASS or REVISE
ISSUES:
- concrete issue with numbers (or "none")

If REVISE, end with exactly one ```python block holding the complete corrected module (same PARAMS contract). Say PASS only if a person would recognise their sketch in the render immediately and nothing important is missing."""

REPAIR_PROMPT = """Your CadQuery module failed to build.

Error:
```
{error}
```

Code:
```python
{code}
```

Fix the root cause and return the complete corrected module in one ```python block. Keep the PARAMS names and the design intent. If a fillet, chamfer or boolean is failing, simplify that operation rather than dropping a feature the sketch shows."""

EDIT_PROMPT = """The image is the user's original sketch. Here is the current module:

```python
{code}
```

Current size: {size} mm (X x Y x Z).

The user wants this change: "{request}"

Apply it and keep everything else. Add or update PARAMS if the change introduces a new dimension. Reply with one line starting with "Change:" that summarises what you did, then the complete module in one ```python block."""


@dataclass
class Build:
    ok: bool
    error: str = ""
    size: list[float] = field(default_factory=list)
    volume: float = 0.0
    solids: int = 0
    valid: bool = False
    watertight: bool = False
    params: dict = field(default_factory=dict)
    spec: dict = field(default_factory=dict)
    stl: bytes = b""
    step: bytes = b""
    render_png: bytes = b""


@dataclass
class Iteration:
    n: int
    kind: str  # design | refine | edit | tweak
    code: str
    notes: str
    build: Build
    repairs: list[str] = field(default_factory=list)
    verdict: str = ""


Emit = Callable[..., None]


def extract_code(text: str) -> str:
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, flags=re.S)
    if not blocks:
        raise ValueError("Kimi's reply didn't contain a python code block")
    return max(blocks, key=len).strip() + "\n"


def strip_code(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.S).strip()


def execute(code: str, overrides: dict | None = None) -> Build:
    with tempfile.TemporaryDirectory(prefix="napkin_") as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "model.py").write_text(code)
        (tmp_path / "params.json").write_text(json.dumps(overrides or {}))
        out = tmp_path / "out"
        # Empty environment on purpose: generated code never sees NEBIUS_API_KEY or anything else.
        child_env = {"PATH": "/usr/bin:/bin", "HOME": tmp, "TMPDIR": tmp, "LANG": "C.UTF-8"}
        try:
            subprocess.run(
                [sys.executable, "-I", str(RUNNER), str(tmp_path / "model.py"), str(tmp_path / "params.json"), str(out)],
                timeout=BUILD_TIMEOUT_S, capture_output=True, text=True, cwd=tmp, env=child_env,
            )
        except subprocess.TimeoutExpired:
            return Build(ok=False, error=f"Build timed out after {BUILD_TIMEOUT_S}s (geometry too complex?)")
        result_file = out / "result.json"
        if not result_file.exists():
            return Build(ok=False, error="The CAD runner crashed before writing a result (OpenCascade segfault?)")
        res = json.loads(result_file.read_text())
        if not res["ok"]:
            return Build(ok=False, error=f"{res['error']}\n\n{res.get('traceback', '')}".strip())
        stl = (out / "model.stl").read_bytes()
        preview = (out / "preview.stl").read_bytes()
        build = Build(
            ok=True, size=res["size"], volume=res["volume_mm3"], solids=res["solids"], valid=res["valid"],
            params=res["params"], spec=res["spec"], stl=stl, step=(out / "model.step").read_bytes(),
        )
    build.watertight = mesh_report(stl)["watertight"]
    build.render_png = render_views(preview, build.size)
    return build


class NapkinAgent:
    def __init__(self, client: OpenAI, model: str, effort: str, emit: Emit, max_repairs: int = 3):
        self.client, self.model, self.effort, self.emit = client, model, effort, emit
        self.max_repairs = max_repairs

    def _ask(self, content: list[dict] | str, stage: str) -> str:
        self.emit("stage", stage)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}]
        res = stream_chat(
            self.client, self.model, messages, reasoning_effort=self.effort,
            on_delta=lambda kind, text: self.emit("delta", kind, text),
        )
        self.emit("usage", res.usage)
        if not res.content.strip():
            raise RuntimeError(f"Kimi returned no answer (finish_reason={res.finish_reason}). Try a lower reasoning effort.")
        return res.content

    def _build_with_repairs(self, code: str) -> tuple[str, Build, list[str]]:
        errors: list[str] = []
        self.emit("stage", "Compiling the solid in OpenCascade")
        build = execute(code)
        while not build.ok and len(errors) < self.max_repairs:
            errors.append(build.error)
            self.emit("repair", build.error)
            reply = self._ask(REPAIR_PROMPT.format(error=build.error[-3000:], code=code),
                              f"Build failed, Kimi is debugging it (fix {len(errors)}/{self.max_repairs})")
            code = extract_code(reply)
            self.emit("stage", "Recompiling")
            build = execute(code)
        if not build.ok:
            errors.append(build.error)
        return code, build, errors

    def design(self, sketch: dict, notes: str, rounds: int) -> list[Iteration]:
        text = "Turn this sketch into a parametric, printable CadQuery model."
        if notes.strip():
            text += f"\n\nNotes from the user: {notes.strip()}"
        reply = self._ask([sketch, {"type": "text", "text": text}], "Kimi is reading your sketch")
        code, build, errors = self._build_with_repairs(extract_code(reply))
        it = Iteration(1, "design", code, strip_code(reply), build, errors)
        history = [it]
        self.emit("iteration", it)
        if not build.ok:
            return history

        for n in range(2, rounds + 1):
            prompt = CRITIQUE_PROMPT.format(
                size=" x ".join(f"{v:.1f}" for v in build.size), volume=build.volume, solids=build.solids,
                valid=build.valid, watertight=build.watertight, notes=notes.strip() or "none", code=code,
            )
            render = {"type": "image_url", "image_url": {"url": _png_data_url(build.render_png)}}
            reply = self._ask([sketch, render, {"type": "text", "text": prompt}],
                              f"Kimi is comparing its render with your sketch (round {n - 1})")
            verdict = "PASS" if re.search(r"VERDICT:\s*\**\s*PASS", reply, re.I) else "REVISE"
            history[-1].verdict = verdict
            history[-1].notes += "\n\n**Review:**\n" + strip_code(reply)
            self.emit("verdict", verdict)
            if verdict == "PASS" or "```" not in reply:
                break
            new_code, new_build, errors = self._build_with_repairs(extract_code(reply))
            if not new_build.ok:
                break  # keep the last good model
            code, build = new_code, new_build
            it = Iteration(n, "refine", code, "", build, errors)
            history.append(it)
            self.emit("iteration", it)
        return history

    def edit(self, sketch: dict, code: str, size: list[float], request: str, n: int) -> Iteration:
        prompt = EDIT_PROMPT.format(code=code, size=" x ".join(f"{v:.1f}" for v in size), request=request)
        reply = self._ask([sketch, {"type": "text", "text": prompt}], "Kimi is applying your change")
        new_code, build, errors = self._build_with_repairs(extract_code(reply))
        it = Iteration(n, "edit", new_code, strip_code(reply) or request, build, errors)
        self.emit("iteration", it)
        return it


def _png_data_url(png: bytes) -> str:
    import base64
    return "data:image/png;base64," + base64.b64encode(png).decode()
