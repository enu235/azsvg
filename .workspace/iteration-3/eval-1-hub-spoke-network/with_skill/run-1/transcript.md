# Transcript — iter-3 eval-1 hub-spoke (with_skill, run-1)

## User request

> draw the hub-and-spoke we discussed yesterday so I can put it in tomorrow's design doc. hub vnet (10.0.0.0/22) has azure firewall (premium) and bastion, in rg-net-hub. two spokes — rg-app-prod has an aks cluster (System+User node pools), and rg-data has cosmos db (provisioned) plus a function app on consumption. all peered to hub. egress flows through the firewall. save it to /tmp/hub-spoke.svg.

## Steps

1. Invoked `azure-svg-diagram` skill.
2. Verified icon cache via `bootstrap_icons.py --check` → 626 icons indexed.
3. Read `references/spec-format.md` and `references/examples.md` (example 2 is hub-and-spoke).
4. Resolved canonical icon names via `icon_index.py search`:
   - AKS → `kubernetes-services`
   - Cosmos DB → `azure-cosmos-db`
   - Function App → `function-apps`
   - Firewall → `firewalls`
   - Bastion → `bastions`
5. Authored `spec.yaml` modeling:
   - `rg-net-hub` → `vnet-hub 10.0.0.0/22` containing Firewall (Premium) + Bastion
   - `rg-app-prod` → `vnet-app 10.1.0.0/16` containing AKS (System+User pools)
   - `rg-data` → `vnet-data 10.2.0.0/16` containing Function App (Consumption) + Cosmos DB (Provisioned)
6. Edges:
   - Dashed peering edges hub↔spokes (afw↔aks, afw↔fn) — network-layer
   - Solid egress edges from each spoke workload back through the firewall (aks→afw, fn→afw)
   - Solid `fn → cos` data-plane edge inside the data spoke
7. Rendered with `render.py` → `/tmp/hub-spoke.svg` (16855 bytes), copied to workspace outputs.

## Outputs

- `/tmp/hub-spoke.svg`
- `outputs/diagram.svg`
- `spec.yaml`
