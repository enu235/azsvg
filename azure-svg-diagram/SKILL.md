---
name: azure-svg-diagram
description: Generate professional SVG Azure architecture diagrams with real Microsoft Azure icons, including annotated troubleshooting/review diagrams that highlight issues on the topology. Trigger when the user names Azure services (App Service, AKS, SQL, Cosmos, Key Vault, vnet, App Gateway, Front Door, Entra, Functions, private endpoint, etc.) with a visual verb ("draw," "diagram," "sketch," "visualize," "show," "map out," "whip up"). ALSO trigger when the user is troubleshooting or reviewing a customer's Azure environment and wants problems pointed out visually — "highlight what's wrong," "call out misconfigurations," "security/well-architected review," "show the customer the issue." Use for any visual ask, however casual. Output is a self-contained SVG with real icons, numbered dataflow steps, per-resource properties, and severity-coded findings callouts. Do NOT trigger for non-Azure diagrams, code/Terraform/Bicep generation, or conceptual questions with no visual ask.
---

# Azure SVG Diagram

Turn an Azure architecture description (English or YAML) into a clean, self-contained `.svg` file that uses the official Microsoft Azure service icons. The output looks like the diagrams on learn.microsoft.com/azure/architecture — containers, icons, labeled arrows, numbered dataflow steps — and can additionally carry a **review layer**: severity-coded findings that highlight specific resources, connections, or boundaries and explain what's wrong and how to fix it.

All paths below are relative to this skill's directory; run scripts with the `python` on PATH (`python3` on some systems).

## How this works

1. The user describes an architecture (and, in review mode, the problems found in it).
2. Translate that description into a **YAML spec** (schema in `references/spec-format.md`).
3. Run `scripts/render.py` to produce the SVG.
4. Show the user the file path and offer to make adjustments.

The renderer is deterministic — same YAML in, same SVG out — so iteration is fast: tweak the YAML, re-render, repeat.

## First-run setup

The skill needs the official Microsoft Azure icon set. Microsoft does not permit redistributing the raw icon files, so the skill downloads them straight from Microsoft to `~/.cache/azure-icons/` on first use.

Before anything else, check:

```bash
python scripts/bootstrap_icons.py --check
```

- Exit 0 → icons are cached, proceed.
- Exit 1 → run without `--check` to download. It takes 5–20 seconds on a typical connection and writes `~/.cache/azure-icons/index.json` mapping canonical names → SVG paths.

The bootstrap script will refuse to clobber an existing cache; pass `--refresh` to update.

## Running the workflow

Once icons are cached, the standard flow is:

```bash
# 1. Write a spec to a temp file, then render it
python scripts/render.py --in my-arch.yaml --out my-arch.svg
```

For one-shot use, pipe YAML on stdin: `cat spec.yaml | render.py --out out.svg`. Open the result in any browser (hover tooltips work there) or hand it to the user — it's a single self-contained file.

## Two modes: project diagrams and review diagrams

**Project mode** documents a design: containers, icons, edges, optional numbered dataflow. **Review mode** adds `findings` — the troubleshooting layer for "point out what's wrong with this customer's implementation." Decide which mode the user wants up front; the telltale for review mode is any mention of issues, misconfigurations, audits, incidents, or "show them where the problem is."

For review mode, read `references/annotations.md` before drafting — it covers severity choice, finding wording, the properties-as-evidence pattern, and the before/after deliverable. The short version:

- Draw the architecture **as it actually is**, wrong parts included.
- Put incriminating config values in the flagged resource's `properties` so the evidence is visible under the icon.
- Add one finding per issue (`ref` → resource id, edge id, or container id), ordered critical-first.
- The renderer does the rest: severity-colored rings and numbered badges on the topology, recolored edges/containers, and a Findings legend with detail + **Fix:** lines.

## Translating an English description into YAML

Most users will describe the architecture in prose. The job is to extract:

- **Containers** (boundaries): subscription, resource group, virtual network, subnet, region. Nest them — a subnet lives inside a vnet, a vnet inside a resource group, etc. Containers are how the diagram earns the "not just rectangles" feel; without them it's a pile of icons.
- **Resources** (the icons): each one needs a stable `id`, a service `type` (e.g., `app-service`, `sql-database`, `key-vault`), an optional human `label`, optional `meta` strings (free-text badges like "zone-redundant"), optional `properties` (named config facts like `TLS: "1.2"` rendered as small lines), and an optional `description` (becomes a hover tooltip — free detail, use it generously).
- **Edges** (connections): `from` → `to` referencing resource ids, with an optional short `label` ("HTTPS", "private endpoint", "managed identity", "telemetry"). Direction matters — pick the dataflow direction the user means. Add `step: 1..N` along the primary request path to get Microsoft-style numbered circles plus a Dataflow legend.
- **Findings** (review mode only): see above.

Keep the spec tight: prefer fewer, meaningful edges over dense webs. **Concrete rules that matter for readability:**

- **Consolidate fan-in.** If multiple resources all send the same logical signal to one destination (e.g., diagnostics → Log Analytics, telemetry → App Insights), draw **one** edge from the *primary workload* to the destination, labeled something like "diagnostics" or "telemetry." Do **not** draw one edge per source resource — three edges all converging on a single icon look like a hairball and the labels collide.
- **Style by relationship type.** Use `style: dashed` for vnet peering and for network-layer relationships. Use `style: dotted` for diagnostic / log flows. Solid lines (the default) are for application dataflow. The visual distinction reads at a glance.
- **Direction matters.** `forward` (default) is the common case. Use `both` for true bidirectional flows (e.g., replication) and `none` only when the relationship has no direction (rare).
- **Aim for ≤ 2 edges per resource on average.** If a resource needs more, the diagram is probably trying to show too much — split it into two diagrams or push some relationships into `properties` instead.
- **Number only the primary path.** Steps tell one story; leave telemetry, peering, and other secondary flows un-numbered.

When the user is vague about boundaries (e.g., "an app service that talks to a SQL DB"), make a reasonable single-resource-group, single-vnet structure rather than asking. The diagram is editable; correctness can be tweaked.

The full schema with all fields is in `references/spec-format.md`. Read it before drafting a spec; the docs there are short.

## Finding the right icon type

Resource `type` values are canonical kebab-case names like `app-service`, `sql-database`, `function-app`, `key-vault`, `cosmos-db`, `application-insights`, `front-door`, `application-gateway`, `vnet`, `firewall`, `bastion`, `private-endpoint`.

If unsure, query the index:

```bash
python scripts/icon_index.py search "kubernetes"
```

This prints matching canonical names. Pick the closest one. The renderer also accepts unknown types by drawing a labeled placeholder, so a bad type fails loudly in the output rather than silently.

See `references/icon-catalog.md` for the conventions used to map service names to canonical keys, and for common gotchas (e.g., "AKS" vs "kubernetes-services").

## Visual style

The renderer follows the Microsoft architecture style:

- White background.
- Containers: thin gray rectangles with the container name at top-left in a small label. Subnets get a dashed border to distinguish from vnet/resource-group boundaries.
- Resources: 48×48 icon, label centered below in 11px, meta/properties in 9px gray underneath. Cells auto-grow to fit their text.
- Edges: thin gray orthogonal lines with arrowheads; lines exit below a resource's text block and attach at icon edges so they don't strike through labels. Labels in small white pills.
- Dataflow steps: blue numbered circles (matching architecture-center conventions) + a Dataflow legend.
- Findings: severity-colored ring + tinted halo around flagged icons (red/orange/blue/green for critical/warning/info/ok), numbered badges, recolored edges and container borders, and a Findings legend with title, detail, and **Fix:** line.

Microsoft's icon terms forbid cropping, flipping, rotating, or recoloring the icons. The renderer respects that — severity is always expressed by a ring *around* the icon, never by modifying it.

## Examples

See `references/examples.md` for four worked examples (3-tier web app with dataflow, hub-and-spoke network, event-driven processing, and a troubleshooting review with findings) showing prose → YAML → rendered SVG.

## When something looks off

- **Icon shows as a labeled rectangle placeholder** → the `type` didn't match any canonical name. Run `icon_index.py search <keyword>` and update the spec.
- **A finding didn't highlight anything** → its `ref` matched no resource id, edge id, or container id/name (the renderer prints a warning to stderr). Edges need an explicit `id` to be referenced.
- **Containers overlap** → too many resources in one row. Set `options.row_wrap: 4` (or similar) to wrap at N columns, or split into sibling containers.
- **An edge cuts through an unrelated resource** → layout is grid-based with no obstacle avoidance. Reorder the `resources` list so connected things sit near each other, or move the offending resource to a different container/row.
- **Diagram is huge / tiny** → adjust `options.cell_width` and `options.cell_height` (defaults: 130, 120; cells auto-grow beyond these to fit text).
- **Too many property lines making cells tall** → keep ~4 visible lines max; move the rest into `description` (hover tooltip).

## What this skill does NOT do

- Doesn't ingest live Azure subscriptions (that's a separate tool — see `~/dev/infradiagram`).
- Doesn't produce Visio, Draw.io, or PNG output directly. SVG can be opened in any of those, but the renderer only writes SVG.
- Doesn't autoroute connections to avoid every overlap. Layout is grid-based; for complex diagrams expect to nudge the spec a few times.
