#!/usr/bin/env python3
"""Render an Azure architecture spec to a self-contained SVG.

Reads a YAML (preferred) or JSON spec. Produces SVG with inlined official
Microsoft Azure service icons, container boundaries, labeled arrows, and a
small metadata block. Style mirrors learn.microsoft.com architecture diagrams.

Usage:
  render.py --in spec.yaml --out out.svg
  cat spec.yaml | render.py --out out.svg
  render.py --in spec.json --format json --out out.svg

Spec format is documented in references/spec-format.md.
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


@dataclass
class ResourceNode:
    id: str
    type: str
    label: str
    meta: list[str] = field(default_factory=list)
    icon_path: str | None = None
    display_type: str = ""
    canonical: str | None = None
    # absolute coordinates filled by layout
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0


@dataclass
class ContainerNode:
    name: str
    kind: str = "custom"
    meta: list[str] = field(default_factory=list)
    layout: str = "row"  # currently unused; rows always vertical
    children: list[Any] = field(default_factory=list)  # list of ContainerNode | ResourceNode
    # absolute coordinates filled by layout
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0


@dataclass
class Edge:
    from_id: str
    to_id: str
    label: str = ""
    style: str = "solid"
    direction: str = "forward"


@dataclass
class Diagram:
    title: str
    subtitle: str
    root: ContainerNode
    edges: list[Edge]
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
            label=e.get("label", ""),
            style=e.get("style", "solid"),
            direction=e.get("direction", "forward"),
        )
        for e in (spec.get("edges") or [])
    ]

    return Diagram(
        title=spec.get("title", ""),
        subtitle=spec.get("subtitle", ""),
        root=root,
        edges=edges,
        metadata=spec.get("metadata") or {},
        options=options,
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
        meta=list(c.get("meta") or []),
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
    node = ResourceNode(
        id=rid,
        type=rtype,
        label=r.get("label") or (hit.display if hit else rtype or rid),
        meta=list(r.get("meta") or []),
        icon_path=hit.path if hit else None,
        display_type=hit.display if hit else rtype,
        canonical=hit.canonical if hit else None,
    )
    return node


# ----------------------------- layout ----------------------------- #


def layout_node(node: Any, x0: float, y0: float, opt: Options, is_root: bool = False) -> tuple[float, float]:
    if isinstance(node, ResourceNode):
        node.x = x0
        node.y = y0
        node.w = opt.cell_width
        node.h = opt.cell_height
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
    cx = r.x + opt.cell_width / 2
    cy = r.y + opt.icon_top + opt.icon_size / 2
    return cx, cy


def route_edge(p1: tuple[float, float], p2: tuple[float, float]) -> tuple[str, list[tuple[float, float]]]:
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
    if abs(x2 - x1) >= abs(y2 - y1):
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

    # 1. Layout the body (the root container's children) starting at a fixed offset.
    body_x = 24.0
    body_y = 90.0
    body_w, body_h = layout_node(d.root, body_x, body_y, opt, is_root=True)

    # 2. Compute overall canvas size with room for title and footer.
    canvas_w = max(560.0, body_x + body_w + 24.0)
    footer_h = (24.0 + 18.0 * len(d.metadata)) if d.metadata else 16.0
    canvas_h = body_y + body_h + footer_h + 24.0

    # 3. Build symbols for each unique icon used.
    used_icons: dict[str, ResourceNode] = {}
    for r in collect_resources(d.root):
        if r.canonical and r.icon_path and r.canonical not in used_icons:
            used_icons[r.canonical] = r

    symbols_xml: list[str] = []
    for canonical, r in used_icons.items():
        try:
            vb, inner = load_icon_symbol(r.icon_path, f"icon-{canonical}")  # type: ignore[arg-type]
        except (ET.ParseError, OSError) as e:
            print(f"WARN: failed to load icon {r.icon_path}: {e}", file=sys.stderr)
            continue
        symbols_xml.append(f'<symbol id="icon-{canonical}" viewBox="{vb}">{inner}</symbol>')

    # 4. Resolve edges. For each edge with a label, choose a label position
    # that avoids resource bboxes and other already-placed labels.
    by_id = {r.id: r for r in collect_resources(d.root)}
    resource_bboxes = [
        (r.x + 4, r.y + 4, r.x + opt.cell_width - 4, r.y + opt.cell_height - 4)
        for r in collect_resources(d.root)
    ]
    edge_paths: list[tuple[str, tuple[float, float] | None, Edge]] = []
    placed_label_points: list[tuple[float, float]] = []
    for e in d.edges:
        a = by_id.get(e.from_id)
        b = by_id.get(e.to_id)
        if not a or not b:
            print(f"WARN: edge references unknown id ({e.from_id} -> {e.to_id})", file=sys.stderr)
            continue
        p1 = icon_center(a, opt)
        p2 = icon_center(b, opt)
        p1, p2 = _shrink_endpoints(p1, p2, opt.icon_size / 2)
        path_d, candidates = route_edge(p1, p2)
        label_pos: tuple[float, float] | None = None
        if e.label:
            label_pos = _pick_label_position(
                candidates, resource_bboxes, placed_label_points, opt.edge_label_collision_offset
            )
            placed_label_points.append(label_pos)
        edge_paths.append((path_d, label_pos, e))

    # 5. Emit SVG.
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
    parts.extend(symbols_xml)
    parts.append('</defs>')

    # Background
    parts.append(f'<rect width="100%" height="100%" fill="{opt.background}"/>')

    # Title + subtitle
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

    # Containers (depth-first so outer ones render under inner ones)
    for c in collect_containers(d.root):
        if c is d.root:
            continue
        parts.append(_render_container(c, opt))

    # Edge LINES go UNDER resources so icons sit on top of the lines.
    # (The arrow tips are already pulled to the icon edge by _shrink_endpoints
    # so they remain visible.)
    for path_d, _label, e in edge_paths:
        parts.append(_render_edge_path(path_d, e, opt))

    # Resources (icons + labels)
    for r in collect_resources(d.root):
        parts.append(_render_resource(r, opt))

    # Edge LABELS go on TOP of everything so they read cleanly.
    for _path_d, label_pos, e in edge_paths:
        if label_pos and e.label:
            parts.append(_render_edge_label(label_pos, e, opt))

    # Metadata footer
    if d.metadata:
        fy0 = body_y + body_h + 32
        parts.append(
            f'<text x="{body_x:.0f}" y="{fy0:.0f}" font-size="{opt.subtitle_font_size}" font-weight="600" fill="#5f6368">'
            f'Metadata</text>'
        )
        for i, (k, v) in enumerate(d.metadata.items()):
            y = fy0 + 16 * (i + 1)
            parts.append(
                f'<text x="{body_x:.0f}" y="{y:.0f}" font-size="{opt.meta_font_size}" fill="#5f6368">'
                f'<tspan font-weight="600">{_xml_escape(str(k))}:</tspan> {_xml_escape(str(v))}</text>'
            )

    parts.append('</svg>')
    return "".join(parts)


def _pick_label_position(
    candidates: list[tuple[float, float]],
    resource_bboxes: list[tuple[float, float, float, float]],
    placed: list[tuple[float, float]],
    offset: float,
) -> tuple[float, float]:
    """Pick a label position that avoids both resource icons and other labels.

    Strategy: try each candidate midpoint; if it falls inside a resource bbox
    or near another label, nudge it perpendicular to the leg until clear.
    Falls back to the first candidate with vertical stacking if nothing fits.
    """
    for cand in candidates:
        adjusted = _nudge_clear(cand, resource_bboxes, placed, offset)
        if adjusted is not None:
            return adjusted
    # Last resort: stack below first candidate.
    x, y = candidates[0]
    while any(abs(x - px) < offset and abs(y - py) < offset for (px, py) in placed):
        y += offset
    return (x, y)


def _nudge_clear(
    point: tuple[float, float],
    bboxes: list[tuple[float, float, float, float]],
    placed: list[tuple[float, float]],
    offset: float,
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
            near_label = any(abs(x - px) < offset and abs(y - py) < offset for (px, py) in placed)
            if not in_bbox and not near_label:
                return (x, y)
    return None


def _shrink_endpoints(p1: tuple[float, float], p2: tuple[float, float], r: float) -> tuple[tuple[float, float], tuple[float, float]]:
    """Pull both endpoints toward each other by r in the dominant axis."""
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    if abs(dx) >= abs(dy):
        sx = r if dx >= 0 else -r
        return (x1 + sx, y1), (x2 - sx, y2)
    sy = r if dy >= 0 else -r
    return (x1, y1 + sy), (x2, y2 - sy)


def _render_container(c: ContainerNode, opt: Options) -> str:
    style = CONTAINER_BORDER.get(c.kind, CONTAINER_BORDER["custom"])
    dash_attr = f' stroke-dasharray="{style["dash"]}"' if style["dash"] else ''
    rect = (
        f'<rect x="{c.x:.1f}" y="{c.y:.1f}" width="{c.w:.1f}" height="{c.h:.1f}" '
        f'rx="4" ry="4" fill="none" stroke="{style["stroke"]}" stroke-width="{style["width"]}"{dash_attr}/>'
    )
    # Name strip: thin label at top-left, small kind chip on the right
    label_y = c.y + 18
    label_x = c.x + 10
    name_xml = (
        f'<text x="{label_x:.1f}" y="{label_y:.1f}" font-size="{opt.container_label_font_size}" '
        f'font-weight="600" fill="{style["stroke"]}">{_xml_escape(c.name)}</text>'
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
            f'fill="{style["stroke"]}" opacity="0.7">{_xml_escape(c.kind)}</text>'
        )
    return rect + name_xml + meta_xml + kind_chip


def _render_resource(r: ResourceNode, opt: Options) -> str:
    cx = r.x + opt.cell_width / 2
    icon_x = cx - opt.icon_size / 2
    icon_y = r.y + opt.icon_top
    parts = []
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

    label_y = r.y + opt.icon_top + opt.icon_size + 12
    parts.append(
        f'<text x="{cx:.1f}" y="{label_y:.1f}" text-anchor="middle" '
        f'font-size="{opt.label_font_size}" fill="#202124">{_xml_escape(r.label)}</text>'
    )
    for i, m in enumerate(r.meta):
        y = label_y + 12 + 11 * i
        parts.append(
            f'<text x="{cx:.1f}" y="{y:.1f}" text-anchor="middle" '
            f'font-size="{opt.meta_font_size}" fill="#5f6368">{_xml_escape(m)}</text>'
        )
    return "".join(parts)


def _render_edge_path(path_d: str, e: Edge, opt: Options) -> str:
    dasharray = {"solid": "", "dashed": ' stroke-dasharray="6,4"', "dotted": ' stroke-dasharray="2,3"'}[e.style]
    marker_start = ' marker-start="url(#arrow)"' if e.direction in ("back", "both") else ""
    marker_end = ' marker-end="url(#arrow)"' if e.direction in ("forward", "both") else ""
    return (
        f'<path d="{path_d}" fill="none" stroke="#5f6368" stroke-width="1.2"'
        f'{dasharray}{marker_start}{marker_end}/>'
    )


def _render_edge_label(pos: tuple[float, float], e: Edge, opt: Options) -> str:
    bx, by = pos
    # 6.6px-per-char approximates 11px Segoe UI width.
    text_w = max(int(6.6 * len(e.label)), 28)
    pad_x = 6
    pad_y = 3
    rect_h = opt.edge_label_font_size + 2 * pad_y
    return (
        f'<rect x="{(bx - text_w/2 - pad_x):.1f}" y="{(by - rect_h/2):.1f}" '
        f'width="{(text_w + 2*pad_x):.1f}" height="{rect_h:.1f}" '
        f'rx="3" ry="3" fill="#ffffff" stroke="#dadce0" stroke-width="0.5"/>'
        f'<text x="{bx:.1f}" y="{(by + 4):.1f}" text-anchor="middle" '
        f'font-size="{opt.edge_label_font_size}" fill="#3c4043">{_xml_escape(e.label)}</text>'
    )


# ----------------------------- entrypoint ----------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="in_path", help="input spec path (default: stdin)")
    parser.add_argument("--out", required=True, help="output SVG path (or - for stdout)")
    args = parser.parse_args(argv)

    if args.in_path and args.in_path != "-":
        text = Path(args.in_path).read_text()
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
        Path(args.out).write_text(svg)
        print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
