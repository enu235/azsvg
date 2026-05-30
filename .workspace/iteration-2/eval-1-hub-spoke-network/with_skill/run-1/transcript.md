# Transcript — eval-1 hub-spoke (with_skill, run-1)

## User request

> draw the hub-and-spoke we discussed yesterday so I can put it in tomorrow's design doc. hub vnet (10.0.0.0/22) has azure firewall (premium) and bastion, in rg-net-hub. two spokes — rg-app-prod has an aks cluster (System+User node pools), and rg-data has cosmos db (provisioned) plus a function app on consumption. all peered to hub. egress flows through the firewall. save it to /tmp/hub-spoke.svg.

## Approach

Used the `azure-svg-diagram` skill.

1. Read `SKILL.md`, `references/spec-format.md`, and `references/examples.md` (Example 2 is a hub-and-spoke, used as a template).
2. Checked icon cache — 626 icons already indexed.
3. Resolved canonical icon names via `icon_index.py search`:
   - firewall → `firewalls`
   - bastion → `bastions`
   - AKS → `kubernetes-services`
   - cosmos → `azure-cosmos-db`
   - function app → `function-apps`
4. Drafted `spec.yaml` with three sibling resource groups (`rg-net-hub`, `rg-app-prod`, `rg-data`), each containing a vnet with its resources.
5. Edges:
   - Peering edges (`afw` → `aks`, `afw` → `func`) as `style: dashed` — network-layer relationship, per skill guidance.
   - Egress edges (`aks` → `afw`, `func` → `afw`) as solid lines — application dataflow.
6. Rendered with `scripts/render.py`. PyYAML wasn't available on `/opt/homebrew/bin/python3` (PEP 668-managed 3.14), so used `/usr/local/bin/python3.11` which has PyYAML 6.0.2.

## Outputs

- `/tmp/hub-spoke.svg` (16.7 KB)
- `outputs/diagram.svg` (copy)
- `spec.yaml` (spec)

## Notes / decisions

- Hub vnet CIDR `10.0.0.0/22` rendered in the vnet container label, as requested.
- Spoke vnet CIDRs not specified by user; left them unlabeled rather than inventing addresses.
- AKS "System + User node pools" placed in `meta` since it's an internal cluster detail, not its own icon.
- Cosmos "Provisioned" and Function "Consumption" likewise in `meta`.
- Bastion has no peering/egress edges — it's a management-plane resource, edges would clutter without adding information.
- 4 edges total, well under the "≤ 2 per resource" guidance.
