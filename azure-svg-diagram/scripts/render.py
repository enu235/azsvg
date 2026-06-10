#!/usr/bin/env python3
"""Render an Azure architecture spec to a self-contained SVG.

Reads a YAML (preferred) or JSON spec. Produces SVG with inlined official
Microsoft Azure service icons, container boundaries, labeled arrows, numbered
dataflow steps, severity-coded findings callouts (for troubleshooting /
well-architected reviews), per-resource property blocks, hover tooltips, and
a small metadata block. Style mirrors learn.microsoft.com architecture
diagrams.

Usage:
  render.py --in spec.yaml --out out.svg
  cat spec.yaml | render.py --out out.svg

Spec format is documented in references/spec-format.md.
Findings / annotation guidance is in references/annotations.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from icon_index import IconIndex

# XML safety: Python's stdlib xml.etree resolves internal entities, which
# allows billion-laughs DoS even though it doesn't fetch external ones. We
# prefer defusedxml when available, and as defense-in-depth we hard-reject
# any icon containing a DOCTYPE or ENTITY declaration before parsing. The
# Microsoft Azure icon SVGs we care about do not use these.
try:
    import defusedxml.ElementTree as _safe_ET  # type: ignore

    def _parse_xml(path: str) -> ET.Element:
        return _safe_ET.parse(path).getroot()
except ImportError:
    _DTD_OR_ENTITY = re.compile(rb"<!DOCTYPE|<!ENTITY", re.IGNORECASE)

    def _parse_xml(path: str) -> ET.Element:
        raw = Path(path).read_bytes()
        if _DTD_OR_ENTITY.search(raw):
            raise ValueError(
                f"refusing to parse {path}: contains DOCTYPE/ENTITY (install defusedxml for full XXE protection)"
            )
        return ET.fromstring(raw)


SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


# ----------------------------- spec model ----------------------------- #


@dataclass
class Options:
    cell_width: float = 130.0
    cell_height: float = 120.0
    row_wrap: int = 6
    container_padding: float = 24.0
    name_strip_height: float = 28.0
    icon_size: float = 48.0
    icon_top: float = 12.0  # padding from top of cell to top of icon
    background: str = "#ffffff"
    title_font_size: float = 20.0
    subtitle_font_size: float = 13.0
    label_font_size: float = 11.0
    meta_font_size: float = 9.0
    container_label_font_size: float = 11.0
    edge_label_font_size: float = 11.0
    edge_label_collision_offset: float = 16.0  # px to nudge a label when it overlaps another
    max_cell_width: float = 250.0  # cap for auto-grown cells (long properties)
    findings_panel: bool = True    # render the findings legend when findings exist
    dataflow_panel: bool = True    # render the numbered dataflow legend when steps exist
    tooltips: bool = True          # embed <title> hover tooltips (description + properties)


@dataclass
class Finding:
    number: int
    ref: str
    severity: str = "warning"     # critical | warning | info | ok
    title: str = ""
    detail: str = ""
    recommendation: str = ""


@dataclass
class ResourceNode:
    id: str
    type: str
    label: str
    meta: list[str] = field(default_factory=list)
    properties: dict[str, str] = field(default_factory=dict)
    description: str = ""
    icon_path: str | None = None
    display_type: str = ""
    canonical: str | None = None
    findings: list[Finding] = field(default_factory=list)
    # absolute coordinates filled by layout
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0


@dataclass
class ContainerNode:
    name: str
    kind: str = "custom"
    id: str | None = None
    meta: list[str] = field(default_factory=list)
    description: str = ""
    layout: str = "row"  # currently unused; rows always vertical
    children: list[Any] = field(default_factory=list)  # list of ContainerNode | ResourceNode
    findings: list[Finding] = field(default_factory=list)
    # absolute coordinates filled by layout
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0


@dataclass
class Edge:
    from_id: str
    to_id: str
    id: str | None = None
    label: str = ""
    style: str = "solid"
    direction: str = "forward"
    step: int | None = None      # numbered dataflow step (blue circle)
    description: str = ""        # text for the dataflow legend (falls back to label)
    findings: list[Finding] = field(default_factory=list)


@dataclass
class Diagram:
    title: str
    subtitle: str
    description: str
    root: ContainerNode
    edges: list[Edge]
    findings: list[Finding]
    metadata: dict[str, str]
    options: Options


CONTAINER_BORDER = {
    "subscription":      {"stroke": "#37474f", "dash": None,    "width": 1.2},
    "resource-group":    {"stroke": "#5f6368", "dash": None,    "width": 1.0},
    "vnet":              {"stroke": "#2b6cb0", "dash": None,    "width": 1.2},
    "subnet":            {"stroke": "#2b6cb0", "dash": "5,3",   "width": 1.0},
    "region":            {"stroke": "#4b6043", "dash": None,    "width": 1.0},
    "availability-zone": {"stroke": "#4b6043", "dash": "2,3",   "width": 1.0},
    "on-prem":           {"stroke": "#6b3fa0", "dash": None,    "width": 1.0},
    "internet":          {"stroke": "#9aa0a6", "dash": "1,3",   "width": 0.8},
    "custom":            {"stroke": "#9aa0a6", "dash": None,    "width": 1.0},
}

# Severity palette. Halos/badges use `color`; halo fill uses `tint`.
# We never recolor the Microsoft icons themselves (their terms forbid it) —
# severity is expressed by a ring *around* the icon plus a numbered badge.
SEVERITY = {
    "critical": {"color": "#d13438", "tint": "#fdf3f4", "label": "Critical"},
    "warning":  {"color": "#ca5010", "tint": "#fdf6f0", "label": "Warning"},
    "info":     {"color": "#0078d4", "tint": "#f0f6fc", "label": "Info"},
    "ok":       {"color": "#107c10", "tint": "#f1faf1", "label": "OK"},
}
SEVERITY_ORDER = ["critical", "warning", "info", "ok"]

STEP_COLOR = "#0078d4"  # Microsoft-blue dataflow step circles


# ----------------------------- loading ----------------------------- #


def load_spec_text(text: str) -> dict:
    """Parse YAML if PyYAML is present, else JSON. JSON is valid YAML so this
    Just Works for JSON input either way."""
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text)
    except ImportError:
        pass
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise SystemExit(
            "PyYAML is not installed and the input is not valid JSON.\n"
            "Either install PyYAML (`pip install --user pyyaml`) or pass a JSON spec.\n"
            f"JSON parse error: {e}"
        )


def build_diagram(spec: dict, icons: IconIndex) -> Diagram:
    options = Options(**(spec.get("options") or {}))

    # Top level: wrap any top-level resources + containers into a synthetic root.
    root = ContainerNode(name="", kind="internet")  # invisible root
    root.children = parse_children(spec, icons)

    edges = [
        Edge(
            from_id=e["from"],
            to_id=e["to"],
            id=e.get("id"),
            label=e.get("label", ""),
            style=e.get("style", "solid"),
            direction=e.get("direction", "forward"),
            step=e.get("step"),
            description=e.get("description", ""),
        )
        for e in (spec.get("edges") or [])
    ]

    findings: list[Finding] = []
    for i, f in enumerate(spec.get("findings") or [], start=1):
        sev = str(f.get("severity", "warning")).lower()
        if sev not in SEVERITY:
            print(f"WARN: unknown severity {sev!r} on finding {i}; using 'warning'", file=sys.stderr)
            sev = "warning"
        findings.append(
            Finding(
                number=i,
                ref=str(f.get("ref", "")),
                severity=sev,
                title=f.get("title", ""),
                detail=f.get("detail", ""),
                recommendation=f.get("recommendation", ""),
            )
        )

    diagram = Diagram(
        title=spec.get("title", ""),
        subtitle=spec.get("subtitle", ""),
        description=spec.get("description", "") or "",
        root=root,
        edges=edges,
        findings=findings,
        metadata=spec.get("metadata") or {},
        options=options,
    )
    _attach_findings(diagram)
    return diagram


def _attach_findings(d: Diagram) -> None:
    """Resolve each finding's `ref` to a resource id, edge id, or container
    id/name, and attach it so the renderer can draw halos/badges."""
    resources = {r.id: r for r in collect_resources(d.root)}
    edges_by_id = {e.id: e for e in d.edges if e.id}
    containers = list(collect_containers(d.root))
    for f in d.findings:
        if f.ref in resources:
            resources[f.ref].findings.append(f)
            continue
        if f.ref in edges_by_id:
            edges_by_id[f.ref].findings.append(f)
            continue
        hit = next((c for c in containers if c is not d.root and (c.id == f.ref or c.name == f.ref)), None)
        if hit is not None:
            hit.findings.append(f)
            continue
        print(
            f"WARN: finding {f.number} ({f.title!r}) references unknown id {f.ref!r} — "
            "it will appear in the findings panel but nothing is highlighted",
            file=sys.stderr,
        )


def parse_children(node_spec: dict, icons: IconIndex) -> list[Any]:
    children: list[Any] = []
    for r in (node_spec.get("resources") or []):
        children.append(parse_resource(r, icons))
    for c in (node_spec.get("containers") or []):
        children.append(parse_container(c, icons))
    return children


def parse_container(c: dict, icons: IconIndex) -> ContainerNode:
    node = ContainerNode(
        name=c.get("name", ""),
        kind=c.get("kind", "custom"),
        id=c.get("id"),
        meta=list(c.get("meta") or []),
        description=c.get("description", ""),
        layout=c.get("layout", "row"),
    )
    node.children = parse_children(c, icons)
    return node


def parse_resource(r: dict, icons: IconIndex) -> ResourceNode:
    rid = r.get("id")
    rtype = r.get("type", "")
    if not rid:
        raise SystemExit(f"resource is missing id: {r!r}")
    hit = icons.resolve(rtype) if rtype else None
    props = r.get("properties") or {}
    node = ResourceNode(
        id=rid,
        type=rtype,
        label=r.get("label") or (hit.display if hit else rtype or rid),
        meta=list(r.get("meta") or []),
        properties={str(k): str(v) for k, v in props.items()},
        description=r.get("description", ""),
        icon_path=hit.path if hit else None,
        display_type=hit.display if hit else rtype,
        canonical=hit.canonical if hit else None,
    )
    return node


# ----------------------------- text helpers ----------------------------- #


def _est_text_w(s: str, font_size: float) -> float:
    """Approximate rendered width of Segoe UI text."""
    return len(s) * font_size * 0.60


def _wrap_text(text: str, max_chars: int) -> list[str]:
    """Greedy word wrap. Collapses internal whitespace/newlines."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for w in words:
        candidate = f"{current} {w}".strip()
        if len(candidate) <= max_chars or not current:
            current = candidate
        else:
            lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


def _resource_text_lines(r: ResourceNode) -> list[str]:
    """The small gray caption lines under a resource label: meta strings
    first, then properties as 'Key: value'."""
    return list(r.meta) + [f"{k}: {v}" for k, v in r.properties.items()]


# ----------------------------- layout ----------------------------- #


def layout_node(node: Any, x0: float, y0: float, opt: Options, is_root: bool = False) -> tuple[float, float]:
    if isinstance(node, ResourceNode):
        node.x = x0
        node.y = y0
        # Cells grow to fit their text: the label plus every meta/property
        # line must be readable without clipping, so height extends with the
        # line count and width extends (up to max_cell_width) with the
        # longest line.
        lines = _resource_text_lines(node)
        text_h = 12 + opt.label_font_size + len(lines) * (opt.meta_font_size + 2) + 8
        needed_h = opt.icon_top + opt.icon_size + text_h
        widest = max(
            [_est_text_w(node.label, opt.label_font_size)]
            + [_est_text_w(ln, opt.meta_font_size) for ln in lines]
        )
        needed_w = widest + 24
        node.w = max(opt.cell_width, min(needed_w, opt.max_cell_width))
        node.h = max(opt.cell_height, needed_h)
        return node.w, node.h

    # ContainerNode
    pad = opt.container_padding
    name_strip = 0.0 if is_root else opt.name_strip_height

    # Group children into rows: a run of consecutive resources flows
    # horizontally with wrapping; each sub-container occupies its own row.
    rows: list[list[Any]] = []
    current_resources: list[ResourceNode] = []
    for child in node.children:
        if isinstance(child, ResourceNode):
            current_resources.append(child)
            if len(current_resources) >= opt.row_wrap:
                rows.append(current_resources)
                current_resources = []
        else:
            if current_resources:
                rows.append(current_resources)
                current_resources = []
            rows.append([child])
    if current_resources:
        rows.append(current_resources)

    inner_x = x0 + pad
    inner_y = y0 + name_strip + (pad if not is_root else 0)
    cursor_y = inner_y
    max_inner_w = 0.0

    for row in rows:
        cursor_x = inner_x
        row_h = 0.0
        for child in row:
            cw, ch = layout_node(child, cursor_x, cursor_y, opt)
            cursor_x += cw
            row_h = max(row_h, ch)
        max_inner_w = max(max_inner_w, cursor_x - inner_x)
        cursor_y += row_h

    cursor_y += pad if not is_root else 0
    width = max_inner_w + 2 * pad if not is_root else max_inner_w
    height = (cursor_y - y0)

    node.x = x0
    node.y = y0
    node.w = width
    node.h = height
    return width, height


def collect_resources(node: Any) -> Iterable[ResourceNode]:
    if isinstance(node, ResourceNode):
        yield node
    else:
        for c in node.children:
            yield from collect_resources(c)


def collect_containers(node: Any) -> Iterable[ContainerNode]:
    if isinstance(node, ContainerNode):
        yield node
        for c in node.children:
            yield from collect_containers(c)


# ----------------------------- rendering ----------------------------- #


def load_icon_symbol(path: str, symbol_id: str) -> tuple[str, str]:
    """Read an icon SVG, return (viewBox, inner_xml) ready for <symbol>."""
    root = _parse_xml(path)
    vb = root.get("viewBox")
    if not vb:
        w = root.get("width", "18")
        h = root.get("height", "18")
        vb = f"0 0 {w} {h}"
    inner_parts = []
    for child in list(root):
        inner_parts.append(_serialize_no_ns(child))
    return vb, "".join(inner_parts)


def _serialize_no_ns(elem: ET.Element) -> str:
    """Serialize an element stripping the SVG namespace from tag names so it
    can be safely embedded inside another <svg> document."""
    tag = elem.tag
    if tag.startswith("{" + SVG_NS + "}"):
        tag = tag.split("}", 1)[1]
    attrs = "".join(f' {k}="{_xml_escape(v)}"' for k, v in elem.attrib.items() if not k.startswith("{"))
    children_xml = "".join(_serialize_no_ns(c) for c in list(elem))
    text = _xml_escape(elem.text or "")
    tail = _xml_escape(elem.tail or "")
    if children_xml or text:
        return f"<{tag}{attrs}>{text}{children_xml}</{tag}>{tail}"
    return f"<{tag}{attrs}/>{tail}"


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def icon_center(r: ResourceNode, opt: Options) -> tuple[float, float]:
    cx = r.x + r.w / 2
    cy = r.y + opt.icon_top + opt.icon_size / 2
    return cx, cy


def _worst_severity(findings: list[Finding]) -> str:
    return min((f.severity for f in findings), key=SEVERITY_ORDER.index)


def _edge_anchor(r: ResourceNode, opt: Options, side: str) -> tuple[float, float]:
    """Attachment point on a resource for an edge. Lines never start at the
    icon center: a downward edge exits below the whole text block (so it does
    not strike through the label/properties), an upward edge exits above the
    icon, and horizontal edges attach at the icon's left/right edge. Resources
    with findings get extra clearance for the severity halo."""
    cx, cy = icon_center(r, opt)
    pad = 11.0 if r.findings else 6.0
    if side == "left":
        return (cx - opt.icon_size / 2 - pad, cy)
    if side == "right":
        return (cx + opt.icon_size / 2 + pad, cy)
    if side == "top":
        return (cx, r.y + max(opt.icon_top - pad, 0.0))
    return (cx, r.y + r.h - 4.0)  # bottom: below label + properties


def route_edge(
    p1: tuple[float, float], p2: tuple[float, float], horizontal_first: bool
) -> tuple[str, list[tuple[float, float]]]:
    """Return (svg_path_d, candidate_label_points). L-shape Manhattan routing.

    Candidate points are the midpoints of each leg of the L, ordered longest-leg
    first. For pure horizontal/vertical edges, returns the single midpoint.
    """
    x1, y1 = p1
    x2, y2 = p2
    if abs(x2 - x1) < 0.5 or abs(y2 - y1) < 0.5:
        return (
            f"M{x1:.1f} {y1:.1f} L{x2:.1f} {y2:.1f}",
            [((x1 + x2) / 2, (y1 + y2) / 2)],
        )
    if horizontal_first:
        corner = (x2, y1)
        d = f"M{x1:.1f} {y1:.1f} L{x2:.1f} {y1:.1f} L{x2:.1f} {y2:.1f}"
    else:
        corner = (x1, y2)
        d = f"M{x1:.1f} {y1:.1f} L{x1:.1f} {y2:.1f} L{x2:.1f} {y2:.1f}"
    # Leg midpoints.
    mid1 = ((x1 + corner[0]) / 2, (y1 + corner[1]) / 2)
    mid2 = ((corner[0] + x2) / 2, (corner[1] + y2) / 2)
    # Longer leg gets the label preferentially (more empty space along it).
    len1 = abs(x1 - corner[0]) + abs(y1 - corner[1])
    len2 = abs(corner[0] - x2) + abs(corner[1] - y2)
    candidates = [mid1, mid2] if len1 >= len2 else [mid2, mid1]
    return d, candidates


def render_svg(d: Diagram) -> str:
    opt = d.options

    # 0. Title block sizing. The optional top-level description renders as a
    # wrapped paragraph under the subtitle and pushes the body down.
    body_x = 24.0
    desc_lines = _wrap_text(d.description, 100) if d.description else []
    body_y = 90.0 + (len(desc_lines) * 15 + 6 if desc_lines else 0)

    # 1. Layout the body (the root container's children).
    body_w, body_h = layout_node(d.root, body_x, body_y, opt, is_root=True)

    # 2. Canvas width: body, title/description, with a sensible minimum.
    canvas_w = max(560.0, body_x + body_w + 24.0)
    if desc_lines:
        canvas_w = max(canvas_w, body_x + max(_est_text_w(ln, 12) for ln in desc_lines) + 24.0)

    # 3. Build symbols for each unique icon used.
    used_icons: dict[str, ResourceNode] = {}
    for r in collect_resources(d.root):
        if r.canonical and r.icon_path and r.canonical not in used_icons:
            used_icons[r.canonical] = r

    symbols_xml: list[str] = []
    for canonical, r in used_icons.items():
        try:
            vb, inner = load_icon_symbol(r.icon_path, f"icon-{canonical}")  # type: ignore[arg-type]
        except (ET.ParseError, OSError, ValueError) as e:
            print(f"WARN: failed to load icon {r.icon_path}: {e}", file=sys.stderr)
            continue
        symbols_xml.append(f'<symbol id="icon-{canonical}" viewBox="{vb}">{inner}</symbol>')

    # 4. Resolve edges. Step badges claim their spot first; labels then pick a
    # position that avoids resource bboxes, step badges, and other labels.
    by_id = {r.id: r for r in collect_resources(d.root)}
    # Labels and badges must avoid resource cells AND container name strips
    # (the title text along each container's top edge).
    resource_bboxes = [
        (r.x + 4, r.y + 4, r.x + r.w - 4, r.y + r.h - 4)
        for r in collect_resources(d.root)
    ]
    for c in collect_containers(d.root):
        if c is not d.root:
            # Pad the strip so wide label pills can't clip the header text.
            resource_bboxes.append((c.x, c.y - 8, c.x + c.w, c.y + opt.name_strip_height + 10))
    edge_paths: list[tuple[str, tuple[float, float] | None, tuple[float, float] | None, Edge]] = []
    # Placed items are (x, y, half_width) so wide pills repel each other by
    # their actual extent, not just a fixed radius.
    placed_label_points: list[tuple[float, float, float]] = []

    def _label_half_w(e: Edge) -> float:
        hw = max(int(6.6 * len(e.label)), 28) / 2 + 6
        if e.step is not None:
            hw += 20  # glued step badge on the left
        if e.findings:
            hw += 20  # finding badge hung on the right
        return hw

    for e in d.edges:
        a = by_id.get(e.from_id)
        b = by_id.get(e.to_id)
        if not a or not b:
            print(f"WARN: edge references unknown id ({e.from_id} -> {e.to_id})", file=sys.stderr)
            continue
        c1 = icon_center(a, opt)
        c2 = icon_center(b, opt)
        dx, dy = c2[0] - c1[0], c2[1] - c1[1]
        horizontal_first = abs(dx) >= abs(dy)
        if horizontal_first:
            p1 = _edge_anchor(a, opt, "right" if dx >= 0 else "left")
            if abs(dy) < 1:
                p2 = _edge_anchor(b, opt, "left" if dx >= 0 else "right")
            else:
                p2 = _edge_anchor(b, opt, "top" if dy > 0 else "bottom")
        else:
            p1 = _edge_anchor(a, opt, "bottom" if dy >= 0 else "top")
            if abs(dx) < 1:
                p2 = _edge_anchor(b, opt, "top" if dy > 0 else "bottom")
            else:
                p2 = _edge_anchor(b, opt, "left" if dx > 0 else "right")
        path_d, candidates = route_edge(p1, p2, horizontal_first)
        # An edge with both a step and a label renders the step badge glued to
        # the label pill, so only a standalone step needs its own position.
        step_pos: tuple[float, float] | None = None
        if e.step is not None and not e.label:
            step_pos = _pick_label_position(
                candidates, resource_bboxes, placed_label_points, opt.edge_label_collision_offset, 9.0
            )
            placed_label_points.append((step_pos[0], step_pos[1], 9.0))
        label_pos: tuple[float, float] | None = None
        if e.label:
            hw = _label_half_w(e)
            label_pos = _pick_label_position(
                candidates, resource_bboxes, placed_label_points, opt.edge_label_collision_offset, hw
            )
            placed_label_points.append((label_pos[0], label_pos[1], hw))
        edge_paths.append((path_d, label_pos, step_pos, e))

    # 5. Pre-render the legend panels (dataflow, findings, metadata) so we can
    # size the canvas before emitting.
    panels_xml: list[str] = []
    panel_y = body_y + body_h + 28
    wrap_chars = max(50, int((canvas_w - body_x * 2 - 30) / 5.8))

    steps = sorted([e for e in d.edges if e.step is not None], key=lambda e: e.step)
    if steps and opt.dataflow_panel:
        xml, panel_y = _render_dataflow_panel(steps, body_x, panel_y, wrap_chars, opt)
        panels_xml.append(xml)

    if d.findings and opt.findings_panel:
        xml, panel_y = _render_findings_panel(d.findings, body_x, panel_y, wrap_chars, opt)
        panels_xml.append(xml)

    if d.metadata:
        xml, panel_y = _render_metadata_panel(d.metadata, body_x, panel_y, opt)
        panels_xml.append(xml)

    canvas_h = panel_y + 24.0

    # 6. Emit SVG.
    parts: list[str] = []
    parts.append(
        f'<svg xmlns="{SVG_NS}" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {canvas_w:.0f} {canvas_h:.0f}" width="{canvas_w:.0f}" height="{canvas_h:.0f}" '
        f'font-family="Segoe UI, -apple-system, Helvetica, Arial, sans-serif">'
    )
    parts.append('<defs>')
    parts.append(
        '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M0 0 L10 5 L0 10 z" fill="#5f6368"/></marker>'
    )
    for sev, style in SEVERITY.items():
        parts.append(
            f'<marker id="arrow-{sev}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0 0 L10 5 L0 10 z" fill="{style["color"]}"/></marker>'
        )
    parts.extend(symbols_xml)
    parts.append('</defs>')

    # Background
    parts.append(f'<rect width="100%" height="100%" fill="{opt.background}"/>')

    # Title + subtitle + description
    if d.title:
        parts.append(
            f'<text x="{body_x:.0f}" y="40" font-size="{opt.title_font_size}" font-weight="600" fill="#202124">'
            f'{_xml_escape(d.title)}</text>'
        )
    if d.subtitle:
        parts.append(
            f'<text x="{body_x:.0f}" y="62" font-size="{opt.subtitle_font_size}" fill="#5f6368">'
            f'{_xml_escape(d.subtitle)}</text>'
        )
    for i, ln in enumerate(desc_lines):
        parts.append(
            f'<text x="{body_x:.0f}" y="{(82 + 15 * i):.0f}" font-size="12" fill="#3c4043">'
            f'{_xml_escape(ln)}</text>'
        )

    # Containers (depth-first so outer ones render under inner ones)
    for c in collect_containers(d.root):
        if c is d.root:
            continue
        parts.append(_render_container(c, opt))

    # Edge LINES go UNDER resources so icons sit on top of the lines.
    # (Endpoints are anchored at icon/cell edges so arrow tips stay visible.)
    for path_d, _label, _step, e in edge_paths:
        parts.append(_render_edge_path(path_d, e, opt))

    # Resources (halo + icon + labels + properties)
    for r in collect_resources(d.root):
        parts.append(_render_resource(r, opt))

    # Edge LABELS, step circles, and finding badges go on TOP so they read cleanly.
    for _path_d, label_pos, step_pos, e in edge_paths:
        if label_pos and e.label:
            parts.append(_render_edge_label(label_pos, e, opt))
        if step_pos is not None and e.step is not None:
            parts.append(_render_step_badge(step_pos, e.step))
        if e.findings:
            if label_pos and e.label:
                # Hang the badge off the pill's right edge.
                text_w = max(int(6.6 * len(e.label)), 28)
                bx, by = label_pos[0] + text_w / 2 + 6 + 13, label_pos[1]
            elif step_pos is not None:
                bx, by = step_pos[0] + 22, step_pos[1]
            else:
                mid = _midpoint_of_path(path_d=_path_d)
                bx, by = mid[0], mid[1] - 14
            for i, f in enumerate(e.findings):
                parts.append(_render_finding_badge(bx + i * 22, by, f))

    # Resource finding badges (drawn after everything so they're never covered)
    for r in collect_resources(d.root):
        if r.findings:
            icon_x = r.x + r.w / 2 + opt.icon_size / 2
            icon_y = r.y + opt.icon_top
            for i, f in enumerate(r.findings):
                parts.append(_render_finding_badge(icon_x + 4 + i * 22, icon_y - 4, f))

    # Container finding badges
    for c in collect_containers(d.root):
        if c is not d.root and c.findings:
            for i, f in enumerate(c.findings):
                parts.append(_render_finding_badge(c.x + c.w - 14 - i * 22, c.y + c.h - 14, f))

    parts.extend(panels_xml)

    parts.append('</svg>')
    return "".join(parts)


def _midpoint_of_path(path_d: str) -> tuple[float, float]:
    nums = [float(v) for v in re.findall(r"-?\d+\.?\d*", path_d)]
    pts = list(zip(nums[0::2], nums[1::2]))
    mid = pts[len(pts) // 2]
    return mid


# ----------------------------- legend panels ----------------------------- #


def _render_dataflow_panel(
    steps: list[Edge], x: float, y: float, wrap_chars: int, opt: Options
) -> tuple[str, float]:
    parts = [
        f'<text x="{x:.0f}" y="{y:.0f}" font-size="13" font-weight="600" fill="#202124">Dataflow</text>'
    ]
    y += 8
    for e in steps:
        text = e.description or e.label or f"{e.from_id} → {e.to_id}"
        lines = _wrap_text(text, wrap_chars)
        y += 18
        parts.append(_render_step_badge((x + 9, y - 4), e.step))
        for j, ln in enumerate(lines):
            if j > 0:
                y += 14
            parts.append(
                f'<text x="{(x + 26):.0f}" y="{y:.0f}" font-size="11" fill="#3c4043">{_xml_escape(ln)}</text>'
            )
    return "".join(parts), y + 24


def _render_findings_panel(
    findings: list[Finding], x: float, y: float, wrap_chars: int, opt: Options
) -> tuple[str, float]:
    parts = [
        f'<text x="{x:.0f}" y="{y:.0f}" font-size="13" font-weight="600" fill="#202124">Findings</text>'
    ]
    y += 10
    tx = x + 26
    for f in findings:
        sev = SEVERITY[f.severity]
        y += 19
        parts.append(_render_finding_badge((x + 9), y - 4, f, in_panel=True))
        head = f.title or f.ref
        parts.append(
            f'<text x="{tx:.0f}" y="{y:.0f}" font-size="11.5">'
            f'<tspan font-weight="600" fill="{sev["color"]}">{_xml_escape(sev["label"])}</tspan>'
            f'<tspan fill="#202124" font-weight="600"> — {_xml_escape(head)}</tspan></text>'
        )
        if f.detail:
            for ln in _wrap_text(f.detail, wrap_chars):
                y += 14
                parts.append(
                    f'<text x="{tx:.0f}" y="{y:.0f}" font-size="10.5" fill="#5f6368">{_xml_escape(ln)}</text>'
                )
        if f.recommendation:
            for j, ln in enumerate(_wrap_text(f.recommendation, wrap_chars - 5)):
                y += 14
                prefix = 'Fix: ' if j == 0 else ''
                parts.append(
                    f'<text x="{tx:.0f}" y="{y:.0f}" font-size="10.5" fill="#3c4043">'
                    f'<tspan font-weight="600">{prefix}</tspan>{_xml_escape(ln)}</text>'
                )
        y += 4
    return "".join(parts), y + 22


def _render_metadata_panel(metadata: dict[str, str], x: float, y: float, opt: Options) -> tuple[str, float]:
    parts = [
        f'<text x="{x:.0f}" y="{y:.0f}" font-size="{opt.subtitle_font_size}" font-weight="600" fill="#5f6368">'
        f'Metadata</text>'
    ]
    for i, (k, v) in enumerate(metadata.items()):
        yy = y + 16 * (i + 1)
        parts.append(
            f'<text x="{x:.0f}" y="{yy:.0f}" font-size="{opt.meta_font_size}" fill="#5f6368">'
            f'<tspan font-weight="600">{_xml_escape(str(k))}:</tspan> {_xml_escape(str(v))}</text>'
        )
    return "".join(parts), y + 16 * len(metadata) + 8


# ----------------------------- badges ----------------------------- #


def _render_step_badge(pos: tuple[float, float] | float, number: int | None) -> str:
    if isinstance(pos, tuple):
        cx, cy = pos
    else:  # pragma: no cover - defensive
        cx, cy = pos, 0
    return (
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="9" fill="{STEP_COLOR}" stroke="#ffffff" stroke-width="1.5"/>'
        f'<text x="{cx:.1f}" y="{(cy + 3.5):.1f}" text-anchor="middle" font-size="10" '
        f'font-weight="600" fill="#ffffff">{number}</text>'
    )


def _render_finding_badge(cx: float, cy: float, f: Finding, in_panel: bool = False) -> str:
    sev = SEVERITY[f.severity]
    return (
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="9" fill="{sev["color"]}" stroke="#ffffff" stroke-width="1.5"/>'
        f'<text x="{cx:.1f}" y="{(cy + 3.5):.1f}" text-anchor="middle" font-size="10" '
        f'font-weight="600" fill="#ffffff">{f.number}</text>'
    )


# ----------------------------- element renderers ----------------------------- #


def _pick_label_position(
    candidates: list[tuple[float, float]],
    resource_bboxes: list[tuple[float, float, float, float]],
    placed: list[tuple[float, float, float]],
    offset: float,
    half_w: float,
) -> tuple[float, float]:
    """Pick a label position that avoids both resource icons and other labels.

    Strategy: try each candidate midpoint; if it falls inside a resource bbox
    or near another label, nudge it perpendicular to the leg until clear.
    Falls back to the first candidate with vertical stacking if nothing fits.
    """
    for cand in candidates:
        adjusted = _nudge_clear(cand, resource_bboxes, placed, offset, half_w)
        if adjusted is not None:
            return adjusted
    # Last resort: stack below first candidate.
    x, y = candidates[0]
    while any(abs(x - px) < half_w + phw and abs(y - py) < offset for (px, py, phw) in placed):
        y += offset
    return (x, y)


def _nudge_clear(
    point: tuple[float, float],
    bboxes: list[tuple[float, float, float, float]],
    placed: list[tuple[float, float, float]],
    offset: float,
    half_w: float,
    max_steps: int = 4,
) -> tuple[float, float] | None:
    """Walk the point in 8 directions in `offset`-sized steps until it's free
    of both resource bboxes and other labels. Returns None if it cannot find
    a clear spot within `max_steps` rings.
    """
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1)]
    for ring in range(max_steps + 1):
        for dx, dy in ([(0, 0)] if ring == 0 else directions):
            x = point[0] + dx * offset * ring
            y = point[1] + dy * offset * ring
            in_bbox = any(x0 <= x <= x1 and y0 <= y <= y1 for (x0, y0, x1, y1) in bboxes)
            # Items repel each other by their combined widths (pills are wide)
            # and a fixed vertical clearance.
            near_label = any(
                abs(x - px) < half_w + phw + 8 and abs(y - py) < offset * 1.2
                for (px, py, phw) in placed
            )
            if not in_bbox and not near_label:
                return (x, y)
    return None


def _render_container(c: ContainerNode, opt: Options) -> str:
    style = CONTAINER_BORDER.get(c.kind, CONTAINER_BORDER["custom"])
    stroke = style["stroke"]
    width = style["width"]
    fill = "none"
    if c.findings:
        sev = SEVERITY[_worst_severity(c.findings)]
        stroke = sev["color"]
        width = max(width, 1.6)
        fill = sev["tint"]
    dash_attr = f' stroke-dasharray="{style["dash"]}"' if style["dash"] else ''
    rect = (
        f'<rect x="{c.x:.1f}" y="{c.y:.1f}" width="{c.w:.1f}" height="{c.h:.1f}" '
        f'rx="4" ry="4" fill="{fill}" fill-opacity="0.35" stroke="{stroke}" stroke-width="{width}"{dash_attr}/>'
    )
    # Name strip: thin label at top-left, small kind chip on the right
    label_y = c.y + 18
    label_x = c.x + 10
    name_xml = (
        f'<text x="{label_x:.1f}" y="{label_y:.1f}" font-size="{opt.container_label_font_size}" '
        f'font-weight="600" fill="{stroke}">{_xml_escape(c.name)}</text>'
    )
    meta_xml = ""
    if c.meta:
        meta_text = "  ·  ".join(c.meta)
        meta_xml = (
            f'<text x="{label_x:.1f}" y="{(label_y + 13):.1f}" font-size="{opt.meta_font_size}" '
            f'fill="#5f6368">{_xml_escape(meta_text)}</text>'
        )
    kind_chip = ""
    if c.kind not in ("custom", "internet"):
        chip_x = c.x + c.w - 8
        kind_chip = (
            f'<text x="{chip_x:.1f}" y="{label_y:.1f}" text-anchor="end" font-size="{opt.meta_font_size}" '
            f'fill="{stroke}" opacity="0.7">{_xml_escape(c.kind)}</text>'
        )
    tooltip = ""
    if c.description and opt.tooltips:
        return (
            f'<g>{_tooltip(c.name, c.description)}{rect}{name_xml}{meta_xml}{kind_chip}</g>'
        )
    return rect + name_xml + meta_xml + kind_chip + tooltip


def _tooltip(name: str, description: str, extra_lines: list[str] | None = None) -> str:
    lines = [name]
    if description:
        lines.append(description)
    if extra_lines:
        lines.extend(extra_lines)
    return f'<title>{_xml_escape(chr(10).join(lines))}</title>'


def _render_resource(r: ResourceNode, opt: Options) -> str:
    cx = r.x + r.w / 2
    icon_x = cx - opt.icon_size / 2
    icon_y = r.y + opt.icon_top
    parts = []

    # Severity halo: a tinted ring AROUND the icon (icons themselves are never
    # recolored — Microsoft's terms forbid modifying them).
    if r.findings:
        sev = SEVERITY[_worst_severity(r.findings)]
        parts.append(
            f'<rect x="{(icon_x - 8):.1f}" y="{(icon_y - 8):.1f}" '
            f'width="{(opt.icon_size + 16):.1f}" height="{(opt.icon_size + 16):.1f}" '
            f'rx="10" ry="10" fill="{sev["tint"]}" stroke="{sev["color"]}" stroke-width="1.8"/>'
        )

    if r.canonical and r.icon_path:
        parts.append(
            f'<use href="#icon-{r.canonical}" x="{icon_x:.1f}" y="{icon_y:.1f}" '
            f'width="{opt.icon_size:.1f}" height="{opt.icon_size:.1f}"/>'
        )
    else:
        # Placeholder for unknown type: rounded rect with the requested type name
        parts.append(
            f'<rect x="{icon_x:.1f}" y="{icon_y:.1f}" width="{opt.icon_size:.1f}" height="{opt.icon_size:.1f}" '
            f'rx="4" ry="4" fill="#fef3c7" stroke="#d97706" stroke-width="1"/>'
            f'<text x="{cx:.1f}" y="{(icon_y + opt.icon_size/2 + 4):.1f}" text-anchor="middle" '
            f'font-size="9" fill="#92400e">?{_xml_escape(r.type or "")}</text>'
        )

    # White halo behind text (paint-order) keeps labels readable when an
    # edge line happens to run underneath them.
    halo = 'paint-order="stroke" stroke="#ffffff" stroke-width="3" stroke-linejoin="round"'
    label_y = r.y + opt.icon_top + opt.icon_size + 12
    parts.append(
        f'<text x="{cx:.1f}" y="{label_y:.1f}" text-anchor="middle" {halo} '
        f'font-size="{opt.label_font_size}" fill="#202124">{_xml_escape(r.label)}</text>'
    )
    line_h = opt.meta_font_size + 2
    for i, m in enumerate(_resource_text_lines(r)):
        y = label_y + 12 + line_h * i
        parts.append(
            f'<text x="{cx:.1f}" y="{y:.1f}" text-anchor="middle" {halo} '
            f'font-size="{opt.meta_font_size}" fill="#5f6368">{_xml_escape(m)}</text>'
        )

    body = "".join(parts)
    if opt.tooltips and (r.description or r.properties):
        extra = [f"{k}: {v}" for k, v in r.properties.items()]
        tip = _tooltip(f"{r.label} ({r.display_type})", r.description, extra)
        return f"<g>{tip}{body}</g>"
    return body


def _render_edge_path(path_d: str, e: Edge, opt: Options) -> str:
    dasharray = {"solid": "", "dashed": ' stroke-dasharray="6,4"', "dotted": ' stroke-dasharray="2,3"'}[e.style]
    stroke = "#5f6368"
    stroke_w = 1.2
    marker_name = "arrow"
    if e.findings:
        sev_key = _worst_severity(e.findings)
        stroke = SEVERITY[sev_key]["color"]
        stroke_w = 1.8
        marker_name = f"arrow-{sev_key}"
    marker_start = f' marker-start="url(#{marker_name})"' if e.direction in ("back", "both") else ""
    marker_end = f' marker-end="url(#{marker_name})"' if e.direction in ("forward", "both") else ""
    return (
        f'<path d="{path_d}" fill="none" stroke="{stroke}" stroke-width="{stroke_w}"'
        f'{dasharray}{marker_start}{marker_end}/>'
    )


def _render_edge_label(pos: tuple[float, float], e: Edge, opt: Options) -> str:
    bx, by = pos
    # 6.6px-per-char approximates 11px Segoe UI width.
    text_w = max(int(6.6 * len(e.label)), 28)
    pad_x = 6
    pad_y = 3
    rect_h = opt.edge_label_font_size + 2 * pad_y
    stroke = "#dadce0"
    text_fill = "#3c4043"
    if e.findings:
        sev = SEVERITY[_worst_severity(e.findings)]
        stroke = sev["color"]
        text_fill = sev["color"]
    step_xml = ""
    if e.step is not None:
        step_xml = _render_step_badge((bx - text_w / 2 - pad_x - 11, by), e.step)
    return (
        f'<rect x="{(bx - text_w/2 - pad_x):.1f}" y="{(by - rect_h/2):.1f}" '
        f'width="{(text_w + 2*pad_x):.1f}" height="{rect_h:.1f}" '
        f'rx="3" ry="3" fill="#ffffff" stroke="{stroke}" stroke-width="0.8"/>'
        f'<text x="{bx:.1f}" y="{(by + 4):.1f}" text-anchor="middle" '
        f'font-size="{opt.edge_label_font_size}" fill="{text_fill}">{_xml_escape(e.label)}</text>'
        f'{step_xml}'
    )


# ----------------------------- entrypoint ----------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="in_path", help="input spec path (default: stdin)")
    parser.add_argument("--out", required=True, help="output SVG path (or - for stdout)")
    args = parser.parse_args(argv)

    if args.in_path and args.in_path != "-":
        text = Path(args.in_path).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    spec = load_spec_text(text)
    if not isinstance(spec, dict):
        raise SystemExit("spec root must be a mapping with at least a 'title' key")

    icons = IconIndex()
    diagram = build_diagram(spec, icons)
    svg = render_svg(diagram)

    if args.out == "-":
        sys.stdout.write(svg)
    else:
        Path(args.out).write_text(svg, encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
