# Worked examples

Each example shows the prose a user might say, the YAML spec it translates to, and a note about how it lays out. Use these as templates when drafting new specs.

## Example 1 — Baseline web app

**User says:** "Draw a baseline App Service architecture: an Application Gateway in front of an App Service, talking to SQL via private endpoint, secrets in Key Vault, monitored by App Insights. Production subscription, one resource group, all in a single vnet."

**Spec:**

```yaml
title: "Baseline App Service architecture"
subtitle: "Private endpoints + zone redundancy"

containers:
  - name: "Production subscription"
    kind: subscription
    containers:
      - name: "rg-web-prod"
        kind: resource-group
        meta: ["West US 2"]
        resources:
          - id: ai
            type: application-insights
            label: "contoso-ai"
        containers:
          - name: "vnet-web · 10.0.0.0/16"
            kind: vnet
            containers:
              - name: "snet-gw · 10.0.1.0/24"
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

**Layout notes:** Each subnet has its own row inside the vnet. The App Insights resource sits at the resource-group level (not inside any subnet) since it's a global PaaS service. Four edges, all originating from `web`, fan out without crossing.

## Example 2 — Hub-and-spoke network

**User says:** "Hub-and-spoke. Hub vnet has Azure Firewall and Bastion. Two spoke vnets: one for web workload (an App Service), one for data (Cosmos DB and a Function App). Peering between hub and both spokes."

**Spec:**

```yaml
title: "Hub-and-spoke network"
subtitle: "Centralized egress via Azure Firewall"

containers:
  - name: "Connectivity subscription"
    kind: subscription
    containers:
      - name: "rg-hub"
        kind: resource-group
        containers:
          - name: "vnet-hub · 10.0.0.0/22"
            kind: vnet
            resources:
              - id: afw
                type: firewall
                label: "hub-afw"
                meta: ["Premium"]
              - id: bas
                type: bastion
                label: "hub-bas"
      - name: "rg-spoke-web"
        kind: resource-group
        containers:
          - name: "vnet-web · 10.1.0.0/16"
            kind: vnet
            resources:
              - id: web
                type: app-service
                label: "contoso-web"
      - name: "rg-spoke-data"
        kind: resource-group
        containers:
          - name: "vnet-data · 10.2.0.0/16"
            kind: vnet
            resources:
              - id: fn
                type: function-app
                label: "data-fn"
              - id: cos
                type: cosmos-db
                label: "contoso-cosmos"

edges:
  - from: afw
    to: web
    label: "peering"
    style: dashed
  - from: afw
    to: fn
    label: "peering"
    style: dashed
  - from: web
    to: fn
    label: "HTTPS"
  - from: fn
    to: cos
    label: "data plane"
```

**Layout notes:** Three sibling resource groups stack vertically. Peering shown as dashed lines because it's a network-layer relationship, not application traffic. Application traffic (HTTPS, data plane) uses solid lines.

## Example 3 — Event-driven processing

**User says:** "Event Grid receives storage blob events, fans out to a Function App which writes results to Cosmos DB and pushes notifications via Service Bus to downstream consumers. Log Analytics collects diagnostics from everything."

**Spec:**

```yaml
title: "Event-driven blob processing"

containers:
  - name: "rg-pipeline"
    kind: resource-group
    resources:
      - id: stor
        type: storage-accounts
        label: "ingest"
        meta: ["blob"]
      - id: eg
        type: event-grid
        label: "events"
      - id: fn
        type: function-app
        label: "process-fn"
        meta: ["Consumption"]
      - id: sb
        type: service-bus
        label: "notify"
      - id: cos
        type: cosmos-db
        label: "results"
        meta: ["Serverless"]
      - id: la
        type: log-analytics
        label: "diag-la"

edges:
  - from: stor
    to: eg
    label: "blob created"
  - from: eg
    to: fn
    label: "trigger"
  - from: fn
    to: cos
    label: "write"
  - from: fn
    to: sb
    label: "notify"
  - from: fn
    to: la
    label: "logs"
    style: dotted
  - from: cos
    to: la
    label: "logs"
    style: dotted
  - from: sb
    to: la
    label: "logs"
    style: dotted
```

**Layout notes:** No nested containers — all six resources sit in one resource group and wrap to multiple rows. Dotted lines for diagnostic flows visually separate them from primary dataflow.
