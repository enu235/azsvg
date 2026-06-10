# Worked examples

Each example shows the prose a user might say, the YAML spec it translates to, and a note about how it lays out. Use these as templates when drafting new specs. Examples 1–3 are project-mode diagrams; Example 4 is a review-mode (troubleshooting) diagram — see `annotations.md` for the difference.

## Example 1 — Baseline web app with dataflow

**User says:** "Draw a baseline App Service architecture: an Application Gateway in front of an App Service, talking to SQL via private endpoint, secrets in Key Vault, monitored by App Insights. Production subscription, one resource group, all in a single vnet. Show the request flow."

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
            description: "Telemetry sink for the web tier."
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
                    properties:
                      SKU: "WAF v2"
                      Mode: "Prevention"
              - name: "snet-app · 10.0.2.0/24"
                kind: subnet
                resources:
                  - id: web
                    type: app-service
                    label: "contoso-web"
                    description: "Customer-facing API, .NET 8."
                    properties:
                      SKU: "P2v3"
                      Zones: "redundant"
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
    step: 1
    label: "HTTPS"
    description: "Application Gateway terminates TLS and forwards to the App Service backend."
  - from: web
    to: sql
    step: 2
    label: "private endpoint"
    description: "API reads/writes order data over a private endpoint in snet-data."
  - from: web
    to: kv
    step: 3
    label: "managed identity"
    description: "Secrets fetched at startup via managed identity."
  - from: web
    to: ai
    label: "telemetry"
    style: dotted

metadata:
  Owner: "platform-eng"
  Region: "West US 2"
```

**Layout notes:** Each subnet gets its own row inside the vnet. App Insights sits at the resource-group level (it's a global PaaS service). Steps 1–3 number the request path and produce a Dataflow legend; the telemetry edge is deliberately un-numbered and dotted so the story stays clean. Properties render under each label; descriptions become hover tooltips.

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
    step: 1
    label: "blob created"
  - from: eg
    to: fn
    step: 2
    label: "trigger"
  - from: fn
    to: cos
    step: 3
    label: "write"
  - from: fn
    to: sb
    step: 4
    label: "notify"
  - from: fn
    to: la
    label: "logs"
    style: dotted
```

**Layout notes:** No nested containers — all six resources sit in one resource group and wrap to multiple rows. One dotted diagnostics edge from the primary workload stands in for "everything logs to LA" (per the fan-in rule); the numbered steps narrate the pipeline.

## Example 4 — Troubleshooting review with findings

**User says:** "I'm troubleshooting a customer's web workload. Their App Service still accepts TLS 1.0, the SQL firewall has a 0.0.0.0 rule, the App Gateway talks plain HTTP to the backend, and the app subnet has no NSG. Draw their architecture and call out the issues so I can walk them through it."

**Spec (abridged — the pattern is what matters):**

```yaml
title: "Contoso web workload — security review"
subtitle: "Findings from the 2026-06-09 troubleshooting session"
description: >
  Customer reported intermittent 502s and a failed security audit. This review
  highlights three configuration issues and one informational note.

containers:
  - name: "rg-web-prod"
    kind: resource-group
    containers:
      - name: "vnet-web · 10.0.0.0/16"
        kind: vnet
        containers:
          - name: "snet-app · 10.0.2.0/24"
            kind: subnet
            id: snet-app                  # <- so a finding can reference the subnet
            resources:
              - id: web
                type: app-service
                label: "contoso-web"
                properties:
                  TLS: "1.0"              # <- visible evidence for finding 1
                  Public access: "Enabled"
          - name: "snet-data · 10.0.3.0/24"
            kind: subnet
            resources:
              - id: sql
                type: sql-database
                label: "contoso-sql"
                properties:
                  Firewall: "0.0.0.0 allowed"   # <- evidence for finding 2

edges:
  - from: agw
    to: web
    id: agw-web                           # <- so a finding can reference the edge
    step: 1
    label: "HTTP"

findings:                                 # ordered by severity, numbered 1..N
  - ref: web
    severity: critical
    title: "TLS 1.0 still accepted"
    detail: "Minimum TLS version is 1.0, which fails the compliance baseline."
    recommendation: "Set minimum TLS to 1.2 under Configuration > General settings."
  - ref: sql
    severity: critical
    title: "SQL firewall allows 0.0.0.0"
    detail: "The open start-IP rule exposes the server to any Azure tenant."
    recommendation: "Remove the rule; use a private endpoint in snet-data."
  - ref: agw-web
    severity: warning
    title: "Gateway to backend is plain HTTP"
    recommendation: "Switch the backend setting to HTTPS."
  - ref: snet-app
    severity: warning
    title: "No NSG on the app subnet"
    recommendation: "Attach an NSG allowing only AppGw ingress on 443."

metadata:
  Customer: "Contoso"
  Engineer: "Allan Miller"
  Session: "2026-06-09"
```

**What renders:** red rings + numbered badges on `web` and `sql`, the `agw→web` line turns orange, the subnet border turns orange with a tinted fill, and a Findings legend below the diagram lists all four issues with severity, detail, and a bold **Fix:** line. The bad config values sit right under the flagged icons because they're in `properties`. Offer the customer a matching "target state" diagram afterward (findings removed, values corrected).
