# YAML spec format

The renderer reads a single YAML document. Top-level keys:

| Key | Required | Purpose |
|---|---|---|
| `title` | yes | Diagram title, rendered top-left. |
| `subtitle` | no | Smaller line under the title. |
| `containers` | yes (or `resources`) | Top-level grouping boxes. |
| `resources` | yes (or `containers`) | Top-level icons not inside any container. |
| `edges` | no | List of arrows between resources. |
| `options` | no | Layout overrides. |
| `metadata` | no | Free-form k/v pairs rendered in a small footer block. |

You can use `resources` at the top level alongside or instead of `containers`; the renderer treats top-level resources as if they were in an implicit container with no border.

## Container

```yaml
- name: "rg-web-prod"        # required, rendered as the small label at top-left of the box
  kind: resource-group       # optional, drives border style. See "Container kinds" below.
  containers: [...]          # optional, nested containers
  resources: [...]           # optional, leaf icons
  layout: row                # optional: "row" (default) or "column" — direction children flow
  meta: ["West US 2"]        # optional small caption next to the name
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
- id: web                    # required, used by edges. Must be unique across the spec.
  type: app-service          # required, canonical icon name
  label: "contoso-web"       # optional, defaults to the type's display name
  meta: ["P2v3", "zone-redundant"]   # optional, list of small caption strings under the label
  position: [col, row]       # optional, manual placement within the parent container
```

`type` is matched against the icon index. Unknown types render a labeled placeholder box. See `icon-catalog.md` for the naming conventions.

`meta` strings are rendered stacked, in 9px gray, under the main label. Useful for SKU, tier, IP range, identity, "private", "public," etc.

## Edge

```yaml
- from: web                  # required, resource id
  to: sql                    # required, resource id
  label: "private endpoint"  # optional, short caption
  style: solid               # optional: "solid" (default) | "dashed" | "dotted"
  direction: forward         # optional: "forward" (default) | "back" | "both" | "none"
```

The renderer routes orthogonally (right-angle Manhattan paths). Labels render in a small pill at the midpoint.

Keep edges semantically meaningful. "App talks to DB" is one edge, not three. Telemetry/logging fan-in usually reads better as a single edge from the workload to App Insights or Log Analytics.

## Options

```yaml
options:
  cell_width: 130            # px allocated per resource cell (default 130)
  cell_height: 120           # px allocated per resource cell (default 120)
  row_wrap: 6                # auto-wrap resources within a container after N (default 6)
  container_padding: 24      # inner padding inside containers (default 24)
  background: "#ffffff"      # page background (default white)
```

Defaults are tuned for Microsoft-style readability. Increase `cell_width` if labels are long enough to clip.

## Metadata footer

```yaml
metadata:
  Owner: "platform-eng"
  Environment: "production"
  Region: "westus2"
  Reviewed: "2026-05-30"
```

Renders as a tidy two-column block bottom-left. Useful for design-doc context.

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

```yaml
title: "Baseline App Service architecture"
subtitle: "Private endpoints + zone redundancy"

containers:
  - name: "Production subscription"
    kind: subscription
    containers:
      - name: "rg-web-prod (West US 2)"
        kind: resource-group
        resources:
          - id: ai
            type: application-insights
            label: "contoso-ai"
        containers:
          - name: "vnet-web · 10.0.0.0/16"
            kind: vnet
            containers:
              - name: "snet-gateway · 10.0.1.0/24"
                kind: subnet
                resources:
                  - id: agw
                    type: application-gateway
                    label: "contoso-agw"
                    meta: ["WAF v2"]
              - name: "snet-app · 10.0.2.0/24"
                kind: subnet
                resources:
                  - id: web
                    type: app-service
                    label: "contoso-web"
                    meta: ["P2v3", "zone-redundant"]
              - name: "snet-data · 10.0.3.0/24"
                kind: subnet
                resources:
                  - id: sql
                    type: sql-database
                    label: "contoso-sql"
                    meta: ["Hyperscale"]
                  - id: kv
                    type: key-vault
                    label: "contoso-kv"

edges:
  - from: agw
    to: web
    label: "private endpoint"
  - from: web
    to: sql
    label: "private endpoint"
  - from: web
    to: kv
    label: "managed identity"
  - from: web
    to: ai
    label: "telemetry"

metadata:
  Owner: "platform-eng"
  Region: "West US 2"
```
