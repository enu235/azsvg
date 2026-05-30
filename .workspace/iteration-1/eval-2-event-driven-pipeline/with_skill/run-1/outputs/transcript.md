# Transcript

User described an event-driven blob ingestion pipeline: Storage Account -> Event Grid -> Function App (Consumption) -> Cosmos DB (Serverless) and Service Bus, with all components shipping logs to a single Log Analytics workspace, inside one resource group `rg-pipeline-prod`, no vnet (PaaS only).

I confirmed the Azure icon cache was bootstrapped (626 icons), then searched the icon index for `event grid`, `service bus`, `log analytics`, `storage`, `cosmos`, and `function` to pick canonical names (`event-grid-topics`, `azure-service-bus`, `log-analytics-workspaces`, `storage-accounts`, `azure-cosmos-db`, `function-apps`).

I drafted a spec with a single `rg-pipeline-prod` resource-group container holding all six resources, solid edges for the main dataflow (blob -> event grid -> function -> cosmos / service bus) and dashed `diagnostics` edges fanning into Log Analytics so the telemetry plane reads differently from the runtime plane.

PyYAML wasn't installable on this Python (PEP 668), so I converted the spec to JSON and invoked `render.py` against the JSON. The renderer wrote `/tmp/pipeline.svg` (18 KB) and I copied it to the workspace outputs alongside the YAML spec.
