"""Executes model-written CadQuery code in a separate process and exports the part.

Usage: python cad_runner.py <code.py> <params.json> <out_dir>

Writes <out_dir>/result.json plus model.stl and model.step on success.
The generated code is checked against an import allowlist and an AST denylist
before it runs, and the parent starts this process with an empty environment
(no API keys) and a timeout. That's a guardrail for a localhost demo, not a
security sandbox: for anything shared, run this step in a container or a remote
sandbox with no network and a read-only filesystem.
"""

from __future__ import annotations

import ast
import json
import math
import sys
import traceback
from pathlib import Path

ALLOWED_IMPORTS = {"cadquery", "math", "numpy"}
BLOCKED_CALLS = {
    "open", "exec", "eval", "compile", "__import__", "input", "breakpoint",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
}
BLOCKED_ATTRS = {
    # file I/O and process escape hatches reachable through cadquery / numpy
    "exporters", "importers", "system", "popen", "load", "loads", "save", "savez", "savez_compressed",
    "savetxt", "loadtxt", "genfromtxt", "fromfile", "tofile", "memmap", "ctypeslib", "lib",
    "os", "sys", "subprocess", "builtins", "importlib", "f2py", "testing",
}


class GuardError(Exception):
    pass


def check_code(source: str) -> None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_IMPORTS:
                    raise GuardError(f"import of '{alias.name}' is not allowed (only cadquery, math, numpy)")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                raise GuardError(f"import from '{node.module}' is not allowed (only cadquery, math, numpy)")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BLOCKED_CALLS:
            raise GuardError(f"call to '{node.func.id}()' is not allowed")
        elif isinstance(node, ast.Attribute) and (node.attr.startswith("__") or node.attr in BLOCKED_ATTRS):
            raise GuardError(f"attribute '.{node.attr}' is not allowed")
        elif isinstance(node, ast.Name) and node.id.startswith("__"):
            raise GuardError(f"name '{node.id}' is not allowed")


def safe_fillet(wp, radius, selector=None):
    """Fillet edges, returning the input unchanged if OpenCascade can't do it."""
    try:
        target = wp.edges(selector) if selector else wp.edges()
        result = target.fillet(radius)
        if result.val().isValid():
            return result
    except Exception:
        pass
    return wp


def safe_chamfer(wp, length, selector=None):
    """Chamfer edges, returning the input unchanged if OpenCascade can't do it."""
    try:
        target = wp.edges(selector) if selector else wp.edges()
        result = target.chamfer(length)
        if result.val().isValid():
            return result
    except Exception:
        pass
    return wp


def resolve_params(spec: dict, overrides: dict) -> dict:
    values = {}
    for name, cfg in spec.items():
        if not isinstance(cfg, dict) or "value" not in cfg:
            raise ValueError(f"PARAMS['{name}'] must be a dict with at least a 'value' key")
        v = overrides.get(name, cfg["value"])
        lo, hi = cfg.get("min"), cfg.get("max")
        if lo is not None:
            v = max(lo, v)
        if hi is not None:
            v = min(hi, v)
        values[name] = int(round(v)) if cfg.get("type") == "int" else float(v)
    return values


def to_shape(cq, result):
    if isinstance(result, cq.Workplane):
        vals = [v for v in result.vals() if isinstance(v, cq.Shape)]
        if not vals:
            raise ValueError("build() returned a Workplane with no shapes on the stack")
        shape = vals[0] if len(vals) == 1 else cq.Compound.makeCompound(vals)
    elif isinstance(result, cq.Assembly):
        shape = result.toCompound()
    elif isinstance(result, cq.Shape):
        shape = result
    else:
        raise TypeError(f"build() must return a cq.Workplane or cq.Shape, got {type(result).__name__}")
    if not shape.Solids():
        raise ValueError("build() produced no solid volume (it returned only wires, faces or a sketch)")
    return shape


def main() -> None:
    code_path, params_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / "result.json"

    try:
        source = code_path.read_text()
        check_code(source)

        import cadquery as cq

        namespace = {"__name__": "napkin_model", "cq": cq, "math": math,
                     "safe_fillet": safe_fillet, "safe_chamfer": safe_chamfer}
        exec(compile(source, "model.py", "exec"), namespace)

        spec = namespace.get("PARAMS", {})
        build = namespace.get("build")
        if not callable(build):
            raise ValueError("the code must define build(p) that returns the part")
        overrides = json.loads(params_path.read_text()) if params_path.exists() else {}
        values = resolve_params(spec, overrides)

        shape = to_shape(cq, build(values))

        # Sit the part on the print bed: XY-centered, lowest point at z=0.
        bb = shape.BoundingBox()
        shape = shape.translate(cq.Vector(-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))
        bb = shape.BoundingBox()

        cq.exporters.export(shape, str(out_dir / "model.stl"), tolerance=0.05, angularTolerance=0.15)
        cq.exporters.export(shape, str(out_dir / "preview.stl"), tolerance=0.25, angularTolerance=0.4)
        cq.exporters.export(shape, str(out_dir / "model.step"))

        result = {
            "ok": True,
            "size": [round(bb.xlen, 2), round(bb.ylen, 2), round(bb.zlen, 2)],
            "volume_mm3": round(shape.Volume(), 1),
            "solids": len(shape.Solids()),
            "valid": bool(shape.isValid()),
            "params": values,
            "spec": spec,
        }
    except Exception as exc:
        tb = traceback.format_exc(limit=6)
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "traceback": tb[-4000:]}

    result_path.write_text(json.dumps(result, default=str))


if __name__ == "__main__":
    main()
