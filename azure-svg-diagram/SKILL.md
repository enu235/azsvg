---
name: azure-svg-diagram
description: Generate professional SVG Azure architecture diagrams using real Microsoft Azure service icons instead of plain rectangles. Trigger when the user names Azure services (App Service, AKS, SQL, Cosmos, Key Vault, vnet, subnet, App Gateway, Front Door, App Insights, Log Analytics, Entra, Azure OpenAI, Function App, private endpoint, etc.) together with a verb suggesting they want to see it ("draw," "diagram," "whiteboard," "sketch," "picture," "visualize," "show," "map out," "whip up"). Use for any visual ask — topology maps, mockups, onboarding docs, stand-up visuals, manager explanations, well-architected reviews, security-posture pictures, design-doc illustrations — including casual or informal phrasings. Output is a self-contained SVG with real Microsoft Azure icons. Do NOT trigger for non-Azure diagrams (React trees, generic flowcharts, sequence diagrams unrelated to Azure), code/CLI/Terraform/Bicep generation, or conceptual questions with no visual ask.
---

# Azure SVG Diagram

Turn an Azure architecture description (English or YAML) into a clean, self-contained `.svg` file that uses the official Microsoft Azure service icons. The output looks like the diagrams on learn.microsoft.com/azure/architecture, not like generic boxes.

## How this works

1. The user describes an architecture.
2. Translate that description into a **YAML spec** (schema in `references/spec-format.md`).
3. Run `scripts/render.py` to produce the SVG.
4. Show the user the file path and offer to make adjustments.

The renderer is deterministic — same YAML in, same SVG out — so iteration is fast: tweak the YAML, re-render, repeat.

## First-run setup

The skill needs the official Microsoft Azure icon set. Microsoft does not permit redistributing the raw icon files, so the skill downloads them straight from learn.microsoft.com to `~/.cache/azure-icons/` on first use.

Before anything else, check:

```bash
python3 /Users/allan/.claude/skills/azure-svg-diagram/scripts/bootstrap_icons.py --check
```

- Exit 0 → icons are cached, proceed.
- Exit 1 → run without `--check` to download. It takes 5–20 seconds on a typical connection and writes `~/.cache/azure-icons/index.json` mapping canonical names → SVG paths.

The bootstrap script will refuse to clobber an existing cache; pass `--refresh` to update.

## Running the workflow

Once icons are cached, the standard flow is:

```bash
# 1. Write a spec
$EDITOR /tmp/my-arch.yaml

# 2. Render it
python3 /Users/allan/.claude/skills/azure-svg-diagram/scripts/render.py \
  --in /tmp/my-arch.yaml \
  --out /tmp/my-arch.svg

# 3. Open it
open /tmp/my-arch.svg
```

For one-shot use, pipe YAML on stdin: `cat spec.yaml | render.py --out out.svg`.

## Translating an English description into YAML

Most users will describe the architecture in prose. The job is to extract:

- **Containers** (boundaries): subscription, resource group, virtual network, subnet, region. Nest them — a subnet lives inside a vnet, a vnet inside a resource group, etc. Containers are how the diagram earns the "not just rectangles" feel; without them it's a pile of icons.
- **Resources** (the icons): each one needs a stable `id`, a service `type` (e.g., `app-service`, `sql-database`, `key-vault`), an optional human `label`, and optional `meta` strings (SKU, tier, "zone-redundant", IP, etc.) that render small under the label.
- **Edges** (connections): `from` → `to` referencing resource ids, with an optional short `label` ("HTTPS", "private endpoint", "managed identity", "telemetry"). Direction matters — pick the dataflow direction the user means.

Keep the spec tight: prefer fewer, meaningful edges over dense webs. **Concrete rules that matter for readability:**

- **Consolidate fan-in.** If multiple resources all send the same logical signal to one destination (e.g., diagnostics → Log Analytics, telemetry → App Insights), draw **one** edge from the *primary workload* to the destination, labeled something like "diagnostics" or "telemetry." Do **not** draw one edge per source resource — three edges all converging on a single icon look like a hairball and the labels collide.
- **Style by relationship type.** Use `style: dashed` for vnet peering and for network-layer relationships. Use `style: dotted` for diagnostic / log flows. Solid lines (the default) are for application dataflow. The visual distinction reads at a glance.
- **Direction matters.** `forward` (default) is the common case. Use `both` for true bidirectional flows (e.g., replication) and `none` only when the relationship has no direction (rare).
- **Aim for ≤ 2 edges per resource on average.** If a resource needs more, the diagram is probably trying to show too much — split it into two diagrams or push some relationships into the `meta` field instead.

When the user is vague about boundaries (e.g., "an app service that talks to a SQL DB"), make a reasonable single-resource-group, single-vnet structure rather than asking. The diagram is editable; correctness can be tweaked.

The full schema with all fields is in `references/spec-format.md`. Read it before drafting a spec; the docs there are short.

## Finding the right icon type

Resource `type` values are canonical kebab-case names like `app-service`, `sql-database`, `function-app`, `key-vault`, `cosmos-db`, `application-insights`, `front-door`, `application-gateway`, `vnet`, `firewall`, `bastion`, `private-endpoint`.

If unsure, query the index:

```bash
python3 /Users/allan/.claude/skills/azure-svg-diagram/scripts/icon_index.py search "kubernetes"
```

This prints matching canonical names. Pick the closest one. The renderer also accepts unknown types by drawing a labeled placeholder, so a bad type fails loudly in the output rather than silently.

See `references/icon-catalog.md` for the conventions used to map service names to canonical keys, and for common gotchas (e.g., "AKS" vs "kubernetes-services").

## Visual style

The renderer follows the Microsoft architecture style:

- White background.
- Containers: thin gray rectangles with the container name at top-left in a small label. Subnets get a dashed border to distinguish from vnet/resource-group boundaries.
- Resources: 48×48 icon, label centered below in 11px, optional metadata in 9px gray underneath.
- Edges: thin gray orthogonal lines with arrowheads; labels in a small white-backed pill where the line bends.

Microsoft's icon terms forbid cropping, flipping, rotating, or recoloring the icons. The renderer respects that — it only translates and uniformly scales them.

## Examples

See `references/examples.md` for three worked examples (3-tier web app, hub-and-spoke network, event-driven processing) showing prose → YAML → rendered SVG.

## When something looks off

- **Icon shows as a labeled rectangle placeholder** → the `type` didn't match any canonical name. Run `icon_index.py search <keyword>` and update the spec.
- **Containers overlap** → too many resources in one row. Set `options.row_wrap: 4` (or similar) to wrap at N columns, or split into sibling containers.
- **Arrows cross the page** → resource ordering matters; group endpoints into the same container or reorder the `resources` list so connected things sit near each other.
- **Diagram is huge / tiny** → adjust `options.cell_width` and `options.cell_height` (defaults: 130, 120).

## What this skill does NOT do

- Doesn't ingest live Azure subscriptions (that's a separate tool — see `~/dev/infradiagram`).
- Doesn't produce Visio, Draw.io, or PNG output directly. SVG can be opened in any of those, but the renderer only writes SVG.
- Doesn't autoroute connections to avoid every overlap. Layout is grid-based; for complex diagrams expect to nudge the spec a few times.
