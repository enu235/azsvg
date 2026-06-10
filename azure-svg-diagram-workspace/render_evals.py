#!/usr/bin/env python3
"""Render every eval spec.yaml to diagram.svg using the renderer matching its
config: with_skill -> the updated skill, old_skill -> the snapshot. The render
step is deterministic, so doing it centrally is equivalent to the subagent
running it (subagents lacked shell permission)."""
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).parent
ITER = WS / (sys.argv[1] if len(sys.argv) > 1 else "iteration-1")
RENDERERS = {
    "with_skill": Path(r"C:\Users\almiller\dev\azsvg\azure-svg-diagram\scripts\render.py"),
    "old_skill": WS / "skill-snapshot" / "scripts" / "render.py",
}

for spec in sorted(ITER.glob("eval-*/*/outputs/spec.yaml")):
    config = spec.parent.parent.name
    renderer = RENDERERS.get(config)
    if renderer is None:
        continue
    out = spec.parent / "diagram.svg"
    r = subprocess.run(
        [sys.executable, str(renderer), "--in", str(spec), "--out", str(out)],
        capture_output=True, text=True,
    )
    status = "ok" if r.returncode == 0 and out.exists() else f"FAIL rc={r.returncode}"
    warns = " | ".join(l for l in r.stderr.splitlines() if l.startswith("WARN"))
    print(f"{spec.parent.parent.parent.name}/{config}: {status}{(' ' + warns) if warns else ''}")
