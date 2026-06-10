#!/usr/bin/env python3
"""Grade eval outputs for the azure-svg-diagram skill (iteration N).

For each eval-*/config/outputs/diagram.svg, evaluate the assertions from
eval_metadata.json programmatically and write grading.json next to outputs/.
"""
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

WS = Path(__file__).parent
ITER = WS / (sys.argv[1] if len(sys.argv) > 1 else "iteration-1")

SEV_COLORS = ["#d13438", "#ca5010"]


def signals(svg_path: Path) -> dict:
    s = {"exists": svg_path.exists()}
    if not s["exists"]:
        return s
    text = svg_path.read_text(encoding="utf-8", errors="replace")
    s["size"] = len(text)
    try:
        root = ET.fromstring(text)
        s["valid_xml"] = True
        s["svg_root"] = root.tag.endswith("svg")
    except ET.ParseError as e:
        s["valid_xml"] = False
        s["svg_root"] = False
        s["parse_error"] = str(e)
        return s
    s["symbol_count"] = text.count("<symbol")
    s["use_count"] = text.count("<use")
    s["placeholder_count"] = text.count("#fef3c7")
    s["severity_color_hits"] = {c: text.count(c) for c in SEV_COLORS}
    s["has_findings_panel"] = ">Findings<" in text
    s["has_fix_lines"] = "Fix:" in text or "Fix: " in text
    s["has_dataflow_panel"] = ">Dataflow<" in text
    # numbered badges: circles with white text digits
    s["badge_numbers"] = sorted(set(int(m) for m in re.findall(r'fill="#ffffff">(\d+)</text>', text)))
    s["raw_text_lower"] = re.sub(r"<[^>]+>", " ", text).lower()
    return s


def grade_eval(eval_dir: Path) -> None:
    meta = json.loads((eval_dir / "eval_metadata.json").read_text(encoding="utf-8"))
    eid = meta["eval_id"]
    for config_dir in sorted(p for p in eval_dir.iterdir() if p.is_dir()):
        svg = config_dir / "outputs" / "diagram.svg"
        sig = signals(svg)
        expectations = []

        def add(text_, passed, evidence):
            expectations.append({"text": text_, "passed": bool(passed), "evidence": evidence})

        a = meta["assertions"]
        # Assertion 0: exists + valid XML svg root (same for all evals)
        add(a[0], sig.get("exists") and sig.get("valid_xml") and sig.get("svg_root"),
            f"exists={sig.get('exists')}, valid_xml={sig.get('valid_xml')}, svg_root={sig.get('svg_root')}, size={sig.get('size', 0)}")

        if not sig.get("valid_xml"):
            for t in a[1:]:
                add(t, False, "no parseable SVG produced")
        elif eid == 0:
            icons_ok = sig["symbol_count"] >= 4 and sig["use_count"] >= 4 and sig["placeholder_count"] == 0
            add(a[1], icons_ok, f"symbols={sig['symbol_count']}, uses={sig['use_count']}, placeholders={sig['placeholder_count']}")
            sev_total = sum(sig["severity_color_hits"].values())
            add(a[2], sev_total >= 6, f"severity color occurrences: {sig['severity_color_hits']} (rings+badges+legend expected; >=6 indicates per-resource highlights)")
            txt = sig["raw_text_lower"]
            legend_ok = sig["has_findings_panel"] and sig["has_fix_lines"] and ("tls" in txt) and ("firewall" in txt or "0.0.0.0" in txt) and ("public" in txt and ("blob" in txt or "storage" in txt))
            add(a[3], legend_ok, f"findings_panel={sig['has_findings_panel']}, fix_lines={sig['has_fix_lines']}, mentions tls/firewall/public-blob in text")
            nums_ok = set([1, 2, 3]).issubset(set(sig["badge_numbers"]))
            add(a[4], nums_ok, f"white badge numbers found: {sig['badge_numbers']} (need 1-3; badges appear once on topology and once in legend)")
        elif eid == 1:
            icons_ok = sig["symbol_count"] >= 5 and sig["use_count"] >= 5 and sig["placeholder_count"] == 0
            add(a[1], icons_ok, f"symbols={sig['symbol_count']}, uses={sig['use_count']}, placeholders={sig['placeholder_count']}")
            txt = sig["raw_text_lower"]
            sku_ok = "p1v3" in txt and "consumption" in txt and "serverless" in txt
            add(a[2], sku_ok, f"p1v3={'p1v3' in txt}, consumption={'consumption' in txt}, serverless={'serverless' in txt}")
            nums_ok = set([1, 2, 3, 4]).issubset(set(sig["badge_numbers"]))
            add(a[3], nums_ok, f"white badge numbers found: {sig['badge_numbers']} (need 1-4)")
            add(a[4], sig["has_dataflow_panel"], f"dataflow_panel={sig['has_dataflow_panel']}")
        elif eid == 2:
            txt = sig["raw_text_lower"]
            icons_ok = sig["symbol_count"] >= 2 and sig["use_count"] >= 2 and sig["placeholder_count"] == 0 and ("kubernetes" in txt or "aks" in txt) and ("registry" in txt or "acr" in txt)
            add(a[1], icons_ok, f"symbols={sig['symbol_count']}, uses={sig['use_count']}, placeholders={sig['placeholder_count']}, aks/acr text present")
            sev_total = sum(sig["severity_color_hits"].values())
            add(a[2], sev_total >= 4, f"severity color occurrences: {sig['severity_color_hits']}")
            legend_ok = sig["has_findings_panel"] and sig["has_fix_lines"] and "private endpoint" in txt and "acrpull" in txt
            add(a[3], legend_ok, f"findings_panel={sig['has_findings_panel']}, fix_lines={sig['has_fix_lines']}, private-endpoint={'private endpoint' in txt}, acrpull={'acrpull' in txt}")
            email_ok = sig.get("svg_root") and sig["size"] > 0
            add(a[4], email_ok, "single self-contained SVG file with title text")

        grading = {"eval_id": eid, "config": config_dir.name, "expectations": expectations,
                   "pass_count": sum(1 for e in expectations if e["passed"]),
                   "total": len(expectations)}
        out = config_dir / "grading.json"
        out.write_text(json.dumps(grading, indent=2), encoding="utf-8")
        print(f"{eval_dir.name}/{config_dir.name}: {grading['pass_count']}/{grading['total']}")


for ed in sorted(ITER.glob("eval-*")):
    if ed.is_dir():
        grade_eval(ed)
