#!/usr/bin/env python3
"""Programmatic grader for the azure-svg-diagram eval workspace.

Walks every iteration/eval-*/(with_skill|without_skill|old_skill)/outputs/
directory, opens diagram.svg, and applies a set of assertions keyed on the
eval_name in eval_metadata.json.

Writes grading.json next to outputs/ with fields {text, passed, evidence}
per the viewer's schema.

Usage:
  grade.py <workspace-root>             # grades every iteration
  grade.py <workspace-root>/iteration-1 # grades just one iteration
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SVG_NS = "{http://www.w3.org/2000/svg}"

# Defense-in-depth XML parsing: prefer defusedxml; otherwise reject DTDs.
try:
    import defusedxml.ElementTree as _safe_ET  # type: ignore

    def _parse_path(path: Path):
        return _safe_ET.parse(str(path)).getroot()
except ImportError:
    _DTD_OR_ENTITY = re.compile(rb"<!DOCTYPE|<!ENTITY", re.IGNORECASE)

    def _parse_path(path: Path):
        raw = path.read_bytes()
        if _DTD_OR_ENTITY.search(raw):
            raise ET.ParseError(f"refusing to parse {path}: contains DOCTYPE/ENTITY")
        return ET.fromstring(raw)


def load_svg(path: Path):
    if not path.exists():
        return None, f"missing: {path}"
    try:
        return _parse_path(path), None
    except ET.ParseError as e:
        return None, f"parse error: {e}"
    except ValueError as e:
        return None, str(e)


def has_icon(root, canonical: str) -> tuple[bool, str]:
    """Check whether the SVG uses an official MS icon for `canonical`.

    Heuristic: looks for a <symbol id="icon-X"> definition that contains
    enough child elements to plausibly be an inlined Microsoft icon, OR a
    <use href="#icon-X"> referencing one. Strings near the canonical name
    in <text> also count partially.
    """
    # Symbol with the exact id
    sym = root.find(f".//{SVG_NS}symbol[@id='icon-{canonical}']")
    if sym is not None:
        # Inlined MS icons contain real SVG primitives, not just rects.
        kids = list(sym.iter())
        has_visual = any(
            k.tag in (SVG_NS + "path", SVG_NS + "circle", SVG_NS + "polygon", SVG_NS + "polyline", SVG_NS + "ellipse")
            for k in kids
        )
        if has_visual and len(kids) >= 3:
            return True, f"symbol icon-{canonical} with {len(kids)} elements"
    # <use> referencing it
    for use in root.iter(SVG_NS + "use"):
        href = use.get("href") or use.get("{http://www.w3.org/1999/xlink}href") or ""
        if href.endswith(f"icon-{canonical}"):
            return True, f"use {href}"
    return False, f"no symbol or use for icon-{canonical}"


def count_container_rects(root) -> int:
    """Count rects that look like container boundaries (fill=none, stroke set)."""
    n = 0
    for rect in root.iter(SVG_NS + "rect"):
        fill = (rect.get("fill") or "").lower()
        stroke = (rect.get("stroke") or "").lower()
        if fill == "none" and stroke and stroke != "none":
            n += 1
    return n


def count_dashed_paths(root) -> int:
    n = 0
    for p in root.iter(SVG_NS + "path"):
        if p.get("stroke-dasharray"):
            n += 1
    return n


def count_directional_edges(root) -> int:
    n = 0
    for p in root.iter(SVG_NS + "path"):
        if (p.get("marker-end") or "").strip():
            n += 1
    return n


def has_text_containing(root, needle: str) -> bool:
    needle_l = needle.lower()
    for t in root.iter(SVG_NS + "text"):
        full = "".join(t.itertext()).lower()
        if needle_l in full:
            return True
    return False


def grade_assertion(text: str, root, svg_path: Path) -> tuple[bool, str]:
    """Map an assertion's text to a programmatic check.

    Returns (passed, evidence). Text patterns are matched fuzzily so this
    grader stays small without coupling to wording too tightly.
    """
    if root is None:
        return False, "SVG not loaded"

    size = svg_path.stat().st_size if svg_path.exists() else 0
    t = text.lower()

    # Size assertions
    if "more than" in t and ("kb" in t or "k bytes" in t):
        m = re.search(r"more than\s+(\d+)\s*kb", t)
        if m:
            threshold = int(m.group(1)) * 1024
            ok = size > threshold
            return ok, f"file size {size} bytes (threshold {threshold})"

    # Valid XML assertion
    if "parses as valid xml" in t or "valid xml" in t:
        return True, "ET parsed root successfully"

    # No vnet / paas-only -- must come BEFORE generic container rule
    if "no vnet" in t or "paas only" in t:
        rects = count_container_rects(root)
        ok = 1 <= rects <= 3
        return ok, f"{rects} container rects (want 1-3, since PaaS only)"

    # Container boundary assertions
    if (
        "container boundar" in t
        or ("resource group" in t and "boundar" in t)
        or ("nested" in t and "rect" in t)
        or "three distinct" in t
    ):
        rects = count_container_rects(root)
        m = re.search(r"\b(\d+|three|four|two)\b", t)
        wanted_map = {"two": 2, "three": 3, "four": 4}
        wanted = int(m.group(1)) if (m and m.group(1).isdigit()) else wanted_map.get(m.group(1) if m else "", 2)
        return rects >= wanted, f"{rects} container-style rects (wanted >= {wanted})"

    # Dashed edge / peering
    if "dashed" in t or "peering" in t:
        n = count_dashed_paths(root)
        return n >= 1, f"{n} dashed paths"

    # Directional edges with arrowheads
    if "directional edges" in t or ("arrowhead" in t):
        n = count_directional_edges(root)
        m = re.search(r"at least (\d+)", t)
        wanted = int(m.group(1)) if m else 1
        return n >= wanted, f"{n} edges with marker-end (wanted >= {wanted})"

    # Labeled edge mentioning a phrase
    if "private endpoint" in t and "label" in t:
        ok = has_text_containing(root, "private endpoint")
        return ok, f"'private endpoint' text found: {ok}"

    # Icon assertions: detect by name fragments
    icon_aliases = {
        "app service": ["app-services", "app-service"],
        "sql": ["sql-database"],
        "key vault": ["key-vaults"],
        "application insights": ["application-insights"],
        "firewall": ["firewalls"],
        "bastion": ["bastions"],
        "kubernetes": ["kubernetes-services"],
        "aks": ["kubernetes-services"],
        "cosmos": ["azure-cosmos-db"],
        "function app": ["function-apps"],
        "storage": ["storage-accounts"],
        "event grid": ["event-grid-domains", "event-grid-topics", "event-grid-subscriptions"],
        "service bus": ["azure-service-bus"],
        "log analytics": ["log-analytics-workspaces"],
    }

    if "official microsoft" in t and "icon" in t:
        for needle, canonicals in icon_aliases.items():
            if needle in t:
                for c in canonicals:
                    ok, ev = has_icon(root, c)
                    if ok:
                        return True, ev
                return False, f"no icon for {needle} (tried {canonicals})"
        # Generic "uses an official icon"
        any_symbol = root.find(f".//{SVG_NS}symbol[@id]")
        ok = any_symbol is not None
        return ok, "has at least one icon symbol" if ok else "no <symbol> defined"

    return False, f"no rule matched assertion text: {text!r}"


def grade_run(run_dir: Path, eval_meta: dict) -> dict:
    svg_path = run_dir / "outputs" / "diagram.svg"
    root, err = load_svg(svg_path)
    expectations = []
    for a in eval_meta.get("assertions", []):
        text = a["text"]
        if root is None:
            expectations.append({"text": text, "passed": False, "evidence": err})
            continue
        passed, evidence = grade_assertion(text, root, svg_path)
        expectations.append({"text": text, "passed": passed, "evidence": evidence})
    passed = sum(1 for e in expectations if e["passed"])
    total = len(expectations)
    pass_rate = (passed / total) if total else 0.0
    return {
        "expectations": expectations,
        "summary": {
            "passed": passed,
            "failed": total - passed,
            "total": total,
            "pass_rate": round(pass_rate, 4),
        },
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: grade.py <iteration-dir-or-workspace-root>", file=sys.stderr)
        return 2
    root = Path(sys.argv[1]).resolve()
    # If pointed at workspace root, iterate over iteration-* dirs; else just that one.
    iterations = (
        sorted(root.glob("iteration-*"))
        if not root.name.startswith("iteration-")
        else [root]
    )
    if not iterations:
        iterations = [root]

    for it in iterations:
        for eval_dir in sorted(it.glob("eval-*")):
            meta_path = eval_dir / "eval_metadata.json"
            if not meta_path.exists():
                print(f"skip {eval_dir}: no eval_metadata.json", file=sys.stderr)
                continue
            meta = json.loads(meta_path.read_text())
            for mode in ("with_skill", "without_skill", "old_skill"):
                mode_dir = eval_dir / mode
                if not mode_dir.exists():
                    continue
                # Each mode may have multiple run-* subdirs OR a flat layout.
                run_dirs = sorted(mode_dir.glob("run-*")) or [mode_dir]
                for run_dir in run_dirs:
                    if not (run_dir / "outputs").exists() and not (mode_dir / "outputs").exists():
                        continue
                    # Outputs may live one level up if flat layout
                    effective = run_dir if (run_dir / "outputs").exists() else mode_dir
                    grading = grade_run(effective, meta)
                    out = run_dir / "grading.json"
                    out.write_text(json.dumps(grading, indent=2))
                    s = grading["summary"]
                    print(f"{eval_dir.name}/{mode}/{run_dir.name}: {s['passed']}/{s['total']} passed -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
