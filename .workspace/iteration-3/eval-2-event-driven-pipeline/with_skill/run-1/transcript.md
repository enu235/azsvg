# Transcript — iter-3 / eval-2 event-driven pipeline / with_skill / run-1

## User request

> i'm sketching out an event-driven pipeline for blob ingestion. storage account fires events to event grid, fans out to a function app (consumption tier), which writes results into cosmos db (serverless) and emits messages on service bus. everything sends logs to one log analytics workspace. one resource group called rg-pipeline-prod, no vnet needed (PaaS only). please give me an svg at /tmp/pipeline.svg.

## Approach

Used the `azure-svg-diagram` skill. Icon cache already bootstrapped (626 icons).

### Translation prose -> structure

- One container: `rg-pipeline-prod` (resource-group kind). No vnet — user explicitly said PaaS only.
- Six resources arranged left-to-right along the dataflow:
  1. Storage account (blob source)
  2. Event Grid (event router)
  3. Function App (Consumption tier)
  4. Cosmos DB (Serverless)
  5. Service Bus (downstream messaging)
  6. Log Analytics workspace (central logging)
- Five edges, all dataflow-forward:
  - storage -> egrid ("blob created")
  - egrid -> func ("event trigger")
  - func -> cosmos ("write results")
  - func -> sbus ("emit message")
  - func -> law ("diagnostics", dotted style)
- Per skill guidance: consolidated all logging fan-in into a single dotted edge from the Function App (the primary workload) to Log Analytics rather than drawing a log edge from every resource. Solid edges are application dataflow; dotted is the diagnostic flow.

### Canonical icon types resolved

| Service | Icon type |
|---|---|
| Storage account | `storage-accounts` |
| Event Grid | `event-grid-topics` |
| Function App | `function-apps` |
| Cosmos DB | `azure-cosmos-db` |
| Service Bus | `azure-service-bus` |
| Log Analytics workspace | `log-analytics-workspaces` |

### Render

```
python3 /Users/allan/.claude/skills/azure-svg-diagram/scripts/render.py \
  --in .../outputs/spec.yaml \
  --out /tmp/pipeline.svg
```

Output: 16,929 bytes. Copied to `outputs/diagram.svg`.

## Files

- `outputs/spec.yaml` — YAML spec
- `outputs/diagram.svg` — rendered SVG (also at `/tmp/pipeline.svg`)
