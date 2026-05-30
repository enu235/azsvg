# Transcript — eval-2-event-driven-pipeline (with_skill, run-1)

## User request

> i'm sketching out an event-driven pipeline for blob ingestion. storage account fires events to event grid, fans out to a function app (consumption tier), which writes results into cosmos db (serverless) and emits messages on service bus. everything sends logs to one log analytics workspace. one resource group called rg-pipeline-prod, no vnet needed (PaaS only). please give me an svg at /tmp/pipeline.svg.

## Approach

Used the `azure-svg-diagram` skill at `/Users/allan/.claude/skills/azure-svg-diagram`.

1. Read `SKILL.md` and the relevant `references/` docs (`spec-format.md`, `examples.md` — Example 3 is the exact analogous pattern).
2. Confirmed icon cache: `bootstrap_icons.py --check` → 626 icons indexed.
3. Drafted the YAML spec (see `spec.yaml`) modeling the user's pipeline as a single flat `rg-pipeline-prod` resource group (no vnet, per the user's "PaaS only" note). Six resources: storage account, event grid, function app, cosmos db, service bus, log analytics.
4. Applied the skill's readability rules:
   - **Consolidated fan-in for diagnostics.** The user said "everything sends logs to one log analytics workspace," but per `SKILL.md`'s explicit guidance ("draw one edge from the primary workload to the destination, labeled something like 'diagnostics'"), drew a single dotted edge `fn → la` labeled "diagnostics" rather than three converging dotted edges from stor, cos, and sb. The metadata caption on the Log Analytics icon ("Diagnostics sink") preserves the "everything logs here" semantics.
   - **Style by relationship type.** Solid lines for application dataflow (`stor → eg`, `eg → fn`, `fn → cos`, `fn → sb`). Dotted for the diagnostics flow.
   - **Direction.** All edges left as default `forward`, which matches the unidirectional event-driven flow.
5. Installed PyYAML (missing on system Python) via `uv pip install --system --break-system-packages pyyaml`, then ran the renderer:
   ```
   python3 /Users/allan/.claude/skills/azure-svg-diagram/scripts/render.py \
     --in .../spec.yaml --out /tmp/pipeline.svg
   ```
6. Copied output to the workspace outputs directory as `diagram.svg`.

## Outputs

- `/tmp/pipeline.svg` — primary deliverable to the user
- `outputs/diagram.svg` — workspace copy (identical bytes)
- `outputs/spec.yaml` — source spec
- `outputs/transcript.md` — this file

## Notes / deviations from a naive read of the request

The literal "everything sends logs to one log analytics workspace" would have been 5 dotted edges (storage, event grid, function, cosmos, service bus → log analytics). The skill docs explicitly call this out as a hairball anti-pattern. Chose the consolidated single-edge representation and conveyed the "everything sinks here" semantics via the resource `meta` caption instead. If the user wants the explicit 5-edge fan-in, the spec change is mechanical.
