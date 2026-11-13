"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "./Icon";

type Point = [number, number];

// A plain pen on white paper. Strokes are kept so undo can redraw them.
export function SketchPad({ busy, onDone }: { busy: boolean; onDone: (file: File) => void }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [strokes, setStrokes] = useState<Point[][]>([]);
  const current = useRef<Point[] | null>(null);

  useEffect(() => {
    const c = canvas.current!;
    c.width = 1600;
    c.height = 1200;
    redraw(strokes);
  }, []);

  function ctx() {
    const g = canvas.current!.getContext("2d")!;
    g.lineCap = "round";
    g.lineJoin = "round";
    g.lineWidth = 5;
    g.strokeStyle = "#111827";
    return g;
  }

  function redraw(all: Point[][]) {
    const g = ctx();
    g.fillStyle = "#ffffff";
    g.fillRect(0, 0, 1600, 1200);
    for (const s of all) drawStroke(g, s);
  }

  function drawStroke(g: CanvasRenderingContext2D, s: Point[]) {
    if (!s.length) return;
    g.beginPath();
    g.moveTo(s[0][0], s[0][1]);
    for (const p of s.slice(1)) g.lineTo(p[0], p[1]);
    if (s.length === 1) g.lineTo(s[0][0] + 0.1, s[0][1]);
    g.stroke();
  }

  function at(e: React.PointerEvent): Point {
    const r = canvas.current!.getBoundingClientRect();
    return [((e.clientX - r.left) / r.width) * 1600, ((e.clientY - r.top) / r.height) * 1200];
  }

  return (
    <div className="pad-wrap">
      <canvas
        ref={canvas}
        className="pad"
        aria-label="Drawing area"
        onPointerDown={(e) => {
          canvas.current!.setPointerCapture(e.pointerId);
          current.current = [at(e)];
        }}
        onPointerMove={(e) => {
          if (!current.current) return;
          const p = at(e);
          const g = ctx();
          const last = current.current.at(-1)!;
          g.beginPath();
          g.moveTo(last[0], last[1]);
          g.lineTo(p[0], p[1]);
          g.stroke();
          current.current.push(p);
        }}
        onPointerUp={() => {
          if (current.current) setStrokes((s) => [...s, current.current!]);
          current.current = null;
        }}
      />
      <div className="toolbar">
        <button
          className="btn"
          disabled={!strokes.length}
          onClick={() => {
            const next = strokes.slice(0, -1);
            setStrokes(next);
            redraw(next);
          }}
        >
          <Icon name="undo" /> Undo
        </button>
        <button
          className="btn"
          disabled={!strokes.length}
          onClick={() => {
            setStrokes([]);
            redraw([]);
          }}
        >
          <Icon name="trash" /> Clear
        </button>
        <span className="faint small" style={{ flex: 1 }}>Draw symbols the way you would on paper. Write values next to parts.</span>
        <button
          className="btn btn-primary"
          disabled={busy || strokes.length < 3}
          onClick={() => canvas.current!.toBlob((b) => b && onDone(new File([b], "drawing.png", { type: "image/png" })), "image/png")}
        >
          <Icon name="play" /> {busy ? "Starting" : "Run it"}
        </button>
      </div>
    </div>
  );
}
