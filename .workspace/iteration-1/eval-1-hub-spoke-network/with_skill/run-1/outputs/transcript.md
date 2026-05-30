# Transcript

User asked for a hub-and-spoke diagram with a hub vnet (10.0.0.0/22) containing Azure Firewall Premium and Bastion in `rg-net-hub`, plus two spokes: `rg-app-prod` with an AKS cluster (System + User node pools), and `rg-data` with a provisioned Cosmos DB and a Consumption-plan Function App, all peered to the hub with egress through the firewall.

I confirmed the azure-icon cache (626 icons indexed), then translated the request into a spec with three resource-group containers, each wrapping its own vnet boundary, and used canonical icon types `firewall`, `bastion`, `kubernetes-services`, `cosmos-db`, and `function-app`. SKU/tier details (Premium, Provisioned, Consumption, System + User pools) live in resource `meta` fields, and three edges from each spoke workload to the firewall convey "peered + egress" without cluttering the diagram with per-peering arrows.

Since PyYAML wasn't installed in the runtime, I rendered from a JSON copy of the spec via `scripts/render.py`. Output written to `/tmp/hub-spoke.svg` (16 KB) and copied to the workspace alongside both spec formats.
