# YAML spec format

The renderer reads a single YAML document. Top-level keys:

| Key | Required | Purpose |
|---|---|---|
| `title` | yes | Diagram title, rendered top-left. |
| `subtitle` | no | Smaller line under the title. |
| `description` | no | Paragraph under the subtitle — context for the reader (what this diagram shows, what was reviewed). Wraps automatically. |
| `containers` | yes (or `resources`) | Top-level grouping boxes. |
| `resources` | yes (or `containers`) | Top-level icons not inside any container. |
| `edges` | no | List of arrows between resources. |
| `findings` | no | Numbered, severity-coded issue callouts. See "Findings" below and `annotations.md`. |
| `options` | no | Layout overrides. |
| `metadata` | no | Free-form k/v pairs rendered in a small footer block. |

You can use `resources` at the top level alongside or instead of `containers`; the renderer treats top-level resources as if they were in an implicit container with no border.

## Container

```yaml
- name: "rg-web-prod"        # required, rendered as the small label at top-left of the box
  kind: resource-group       # optional, drives border style. See "Container kinds" below.
  id: rg-web                 # optional, lets findings reference this container
  containers: [...]          # optional, nested containers
  resources: [...]           # optional, leaf icons
  layout: row                # optional: "row" (default) or "column" — direction children flow
  meta: ["West US 2"]        # optional small caption next to the name
  description: "..."         # optional, shown as a hover tooltip on the container
```

Containers may be arbitrarily nested. The renderer measures children first, then sizes the container to fit, with padding for the name strip at the top.

### Container kinds

The `kind` affects the border style — it doesn't constrain what you can put inside.

| Kind | Border | Use for |
|---|---|---|
| `subscription` | solid 1px dark gray | Top-level subscription / tenant boundary |
| `resource-group` | solid 1px medium gray | Resource group |
| `vnet` | solid 1px blue (#2b6cb0) | Virtual network |
| `subnet` | dashed 1px blue (#2b6cb0) | Subnet |
| `region` | solid 1px green-gray | Azure region |
| `availability-zone` | dotted 1px green-gray | AZ |
| `on-prem` | solid 1px purple | On-premises / customer datacenter |
| `internet` | none, just label | Public internet cloud |
| `custom` | solid 1px gray | Anything else |

Default if omitted: `custom`.

## Resource

```yaml
- id: web                    # required, used by edges and findings. Unique across the spec.
  type: app-service          # required, canonical icon name
  label: "contoso-web"       # optional, defaults to the type's display name
  meta: ["zone-redundant"]   # optional, list of small caption strings under the label
  properties:                # optional, key/value config facts rendered as "Key: value"
    SKU: "P2v3"              #   lines under the label (after any meta lines)
    TLS: "1.2"
    Identity: "system-assigned"
  description: "Customer-facing API, .NET 8."   # optional, hover tooltip text
```

`type` is matched against the icon index. Unknown types render a labeled placeholder box. See `icon-catalog.md` for the naming conventions.

**`meta` vs `properties`:** both render as small 9px gray lines under the label. `meta` is for free-text badges ("zone-redundant", "private"); `properties` is for named configuration facts ("TLS: 1.2", "SKU: P2v3"). Use `properties` when the *name* of the setting matters — especially in troubleshooting diagrams where a finding references a specific configuration value shown on the resource. The cell grows to fit however many lines you add, but past ~4 lines the diagram gets tall; move long detail into `description` (tooltip) instead.

**Tooltips:** when a resource has a `description` or `properties`, the SVG embeds a `<title>` element — hovering the resource in a browser shows the description and full property list. This is free detail that doesn't cost any pixels, so be generous with `description`.

## Edge

```yaml
- from: web                  # required, resource id
  to: sql                    # required, resource id
  id: web-sql                # optional, lets findings reference this edge
  label: "private endpoint"  # optional, short caption
  style: solid               # optional: "solid" (default) | "dashed" | "dotted"
  direction: forward         # optional: "forward" (default) | "back" | "both" | "none"
  step: 2                    # optional, numbered dataflow step (blue circle on the edge)
  description: "API reads/writes order data."   # optional, text for the Dataflow legend
```

The renderer routes orthogonally (right-angle Manhattan paths). Lines exit *below* a resource's text block when heading down and attach at the icon's edge otherwise, so they don't strike through labels. Labels render in a small pill near the line's midpoint.

Keep edges semantically meaningful. "App talks to DB" is one edge, not three. Telemetry/logging fan-in usually reads better as a single edge from the workload to App Insights or Log Analytics.

### Numbered dataflow steps

Give edges a `step` number to tell the story of a request the way Microsoft's architecture-center diagrams do: a blue numbered circle renders on the edge, and a **Dataflow** legend below the diagram lists each step using the edge's `description` (falling back to `label`, then `from → to`). Number the primary request path 1..N in order; leave secondary flows (telemetry, peering) un-numbered so the story stays clean.

## Findings

Findings are the troubleshooting layer: numbered, severity-coded callouts that highlight a resource, an edge, or a container, plus a **Findings** legend that explains each one.

```yaml
findings:
  - ref: web                 # required: a resource id, edge id, or container id/name
    severity: critical       # critical | warning | info | ok   (default: warning)
    title: "TLS 1.0 still accepted"          # short headline, bold in the legend
    detail: "Minimum TLS version is 1.0, which fails the compliance baseline."
    recommendation: "Set minimum TLS to 1.2 under Configuration > General settings."
```

What renders:

- **Resource ref** → a severity-colored ring + tinted halo around the icon, and a numbered badge at the icon's top-right. (Icons themselves are never recolored — Microsoft's terms forbid modifying them; the ring carries the color.)
- **Edge ref** → the line, arrowhead, and label pill turn the severity color and the numbered badge sits near the label. The edge needs an `id` to be referenced.
- **Container ref** → the border turns the severity color with a light tint fill, badge at bottom-right. Reference by the container's `id` (preferred) or exact `name`.
- **Findings legend** → numbered list below the diagram: colored badge, severity word, title, wrapped detail, and a bold **Fix:** line with the recommendation.

Findings are numbered 1..N in spec order — order them by severity (critical first) so the legend reads like a prioritized punch list. A `ref` that matches nothing prints a warning to stderr and still appears in the legend.

Severity colors: critical = red `#d13438`, warning = orange `#ca5010`, info = blue `#0078d4`, ok = green `#107c10`. Use `ok` to call out things that are configured *correctly* when that's worth saying ("private endpoint correctly enforced here").

Full guidance on writing good findings (severity choice, wording, how many per diagram) is in `annotations.md`.

## Options

```yaml
options:
  cell_width: 130            # min px per resource cell (default 130; cells auto-grow to fit text)
  cell_height: 120           # min px per resource cell (default 120; auto-grows with property lines)
  max_cell_width: 250        # cap for auto-grown cells (default 250)
  row_wrap: 6                # auto-wrap resources within a container after N (default 6)
  container_padding: 24      # inner padding inside containers (default 24)
  background: "#ffffff"      # page background (default white)
  findings_panel: true       # set false to highlight without the legend (default true)
  dataflow_panel: true       # set false to hide the numbered step legend (default true)
  tooltips: true             # set false to omit hover <title> tooltips (default true)
```

Defaults are tuned for Microsoft-style readability. Cells size themselves to their content, so you rarely need to touch these.

## Metadata footer

```yaml
metadata:
  Customer: "Contoso"
  Engineer: "Allan Miller"
  Session: "2026-06-09"
  Environment: "production"
```

Renders as a tidy block at the bottom. For troubleshooting sessions, record the customer, date, and who did the review — the SVG becomes a self-documenting artifact.

## Minimal valid spec

```yaml
title: "Hello"
resources:
  - id: app
    type: app-service
    label: "my-app"
```

Renders a single App Service icon centered on a white page with the title.

## Full reference example

See `examples.md` — Example 1 covers a healthy architecture with properties and dataflow steps; Example 4 is a complete troubleshooting review with findings at every severity.
