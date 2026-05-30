# Transcript: Hub-and-Spoke SVG (without skill)

## Task
Draw an Azure hub-and-spoke network topology and save it to `/tmp/hub-spoke.svg`. Constraint: do NOT invoke the `azure-svg-diagram` skill — produce the SVG by my own means.

## Topology to depict
- **Hub VNet** 10.0.0.0/22 in `rg-net-hub`, containing Azure Firewall (Premium) and Azure Bastion.
- **Spoke 1** `rg-app-prod`: AKS cluster with System + User node pools.
- **Spoke 2** `rg-data`: Cosmos DB (provisioned) and a Function App (consumption).
- Both spokes peered to the hub; egress flows through the firewall.

## Approach

Wrote the SVG markup by hand directly (no skill, no Python). Key decisions:

1. **Canvas / layout.** Chose a 1200x820 viewBox with the hub centered at the top and the two spokes side-by-side below — the canonical "hub-and-spoke" visual where peering lines fan out from a single central VNet.
2. **Container hierarchy.** Three nested visual layers:
   - Dashed blue rectangles for **resource groups** (`rg-net-hub`, `rg-app-prod`, `rg-data`).
   - Solid blue rectangles inside each RG for the **VNets**, labeled with name and CIDR.
   - White rounded boxes inside each VNet for the **services** themselves.
3. **Icons.** Because I'm not using the skill's icon library, I built six small inline `<symbol>` glyphs in `<defs>` so each service gets a recognizable mark rather than a bare rectangle:
   - Firewall: orange brick wall with a small red shield on top.
   - Bastion: blue castle/tower silhouette.
   - AKS: blue hexagon with a kubernetes-style spoked wheel inside.
   - Cosmos DB: dark blue globe with cyan latitude/longitude rings.
   - Function App: yellow square with a white lightning bolt.
   - Internet: gray cloud outline.
   These are stylized approximations of the official Azure icons — not pixel-accurate, but they read at a glance and avoid plain rectangles.
4. **AKS node pools.** Inside the AKS service box I added two small sub-boxes labeled "System Node Pool" (CriticalAddonsOnly) and "User Node Pool" (autoscale) so the design doc reader can see both pools explicitly.
5. **Connections.**
   - **Green solid arrows** with double-headed arrows = bidirectional VNet peering between hub and each spoke.
   - **Orange dashed arrows** = egress traffic, drawn from each spoke through the Firewall and out to the Internet cloud. Annotated "Egress via UDR" to signal that user-defined routes force spoke outbound traffic through the firewall.
6. **Legend.** Top-left legend box explains the three line/box styles (peering, egress, RG boundary) so the diagram is self-contained when pasted into the design doc.
7. **Typography.** Segoe UI stack (Microsoft house font), with a clear title and subtitle summarizing the architecture.

## Output
- `/tmp/hub-spoke.svg` (primary deliverable, ~11 KB hand-written SVG)
- Copy at `azure-svg-diagram-workspace/iteration-1/eval-1-hub-spoke-network/without_skill/outputs/diagram.svg`

## Notes / limitations
- Icons are hand-stylized SVG primitives, not the licensed Microsoft Azure icon set. For a polished published doc, the icons could be swapped for the official ones, but visual hierarchy and topology semantics are preserved.
- No private endpoints / NSG / route table objects drawn explicitly — only the UDR egress is annotated. Could be expanded if the design doc needs that level of detail.
