# Annotating diagrams: descriptions, properties, and findings

This guide covers the annotation layer — how to turn a topology picture into a
*review artifact* a customer or stakeholder can act on. Read it when the user is
troubleshooting, doing a well-architected / security review, or asks to "point
out", "highlight", "flag", or "call out" anything in a diagram.

## The two diagram modes

**Project mode** — the diagram documents a design. Use `description` for
context, `properties` for the configuration facts that matter (SKUs, tiers,
TLS versions, redundancy), and `step` numbers on the primary request path so
the Dataflow legend tells the story. No findings.

**Review mode** — the diagram communicates problems. Everything from project
mode, plus `findings` that mark the issues directly on the topology. The output
should read like a consultant's deliverable: the customer sees *where* each
problem lives, *why* it matters, and *what to do about it* — all in one image
they can paste into an email or slide.

## Writing good findings

A finding has four parts. Each has a job:

- **`title`** — the headline a busy executive reads. Name the misconfiguration,
  not the symptom: "SQL firewall allows 0.0.0.0", not "database problem".
  Keep it under ~8 words; it renders bold next to the severity.
- **`detail`** — one or two sentences of evidence and impact. State what is
  configured today and why that's a problem ("Minimum TLS is 1.0, which fails
  the customer's compliance baseline and breaks modern client handshakes").
- **`recommendation`** — the fix, specific enough to act on. Prefer the actual
  portal path, CLI flag, or setting name ("Set minimum TLS to 1.2 under
  Configuration > General settings") over generic advice ("improve security").
- **`severity`** — see below.

### Choosing severity

| Severity | Use when | Examples |
|---|---|---|
| `critical` | Active exposure or outage cause; fix now | Public network access on a data store, secrets in app settings, single instance of a stateful tier, 0.0.0.0 firewall rule |
| `warning` | Real risk or deviation from baseline; fix soon | Missing NSG, HTTP between tiers, no zone redundancy, WAF in detection mode, missing diagnostic settings |
| `info` | Worth knowing; not a risk by itself | Cost observations, deprecated-but-working SKUs, sampling rates, upcoming retirement dates |
| `ok` | Explicitly confirm something is *right* | "Private endpoint correctly enforced", "soft-delete enabled" — useful in reviews so the customer sees what *passed*, not just what failed |

When unsure between two severities, pick the lower one — a review full of
criticals loses the customer's trust; a single critical gets fixed the same day.

### Ordering and quantity

- List findings **critical first** — they're numbered 1..N in spec order, and the
  legend reads as a prioritized punch list.
- **3–7 findings per diagram** is the sweet spot. Past that, split into two
  diagrams (e.g., one network review, one identity review) or fold the minor
  items into a single info finding.
- Anchor each finding to the most specific thing: the resource if it's a
  resource setting, the *edge* if the problem is the connection (plain HTTP,
  missing private link), the *container* if it's a boundary problem (subnet with
  no NSG, resource group with no lock).

### Pairing findings with properties

A finding lands harder when the evidence is visible on the resource itself. If
the finding says "TLS 1.0 still accepted", put `TLS: "1.0"` in that resource's
`properties` — the reader sees the bad value right under the icon the badge
points at. This properties-as-evidence pattern is what makes the diagram
self-explanatory without the prose report.

```yaml
resources:
  - id: web
    type: app-service
    label: "contoso-web"
    properties:
      TLS: "1.0"               # <- the evidence
      Public access: "Enabled" # <- evidence for a second finding
findings:
  - ref: web
    severity: critical
    title: "TLS 1.0 still accepted"
    detail: "Minimum TLS version is 1.0; the customer's baseline requires 1.2."
    recommendation: "Configuration > General settings > Minimum TLS version = 1.2."
```

### Highlighting an edge

The connection itself is often the problem. Give the edge an `id` and reference
it — the whole line turns the severity color, which reads instantly:

```yaml
edges:
  - from: agw
    to: web
    id: agw-web
    label: "HTTP"
findings:
  - ref: agw-web
    severity: warning
    title: "Gateway to backend is plain HTTP"
    recommendation: "Switch the backend setting to HTTPS."
```

### Highlighting a container

Boundary problems (subnet without an NSG, unprotected resource group) reference
the container's `id` or exact `name`. The whole box tints and the badge sits at
its bottom-right corner:

```yaml
containers:
  - name: "snet-app · 10.0.2.0/24"
    kind: subnet
    id: snet-app
findings:
  - ref: snet-app
    severity: warning
    title: "No NSG on the app subnet"
```

## The troubleshooting workflow

When a user describes a customer issue ("their App Gateway returns 502s and
the audit flagged the SQL firewall"):

1. **Draw the architecture as it exists** — including the wrong parts. The
   diagram must reflect the customer's actual deployment, not the ideal one.
   Resist fixing the topology in the picture; the findings do the criticizing.
2. **Put the incriminating values in `properties`** so the evidence is visible.
3. **Add one finding per distinct issue**, anchored to the most specific
   element, ordered by severity.
4. **Fill the `metadata` block** with customer, engineer, and session date —
   the SVG becomes a dated review artifact.
5. Offer a follow-up "target state" diagram: same spec with the findings
   removed and the configuration corrected (TLS 1.2, private endpoints, NSGs
   in place, severity-`ok` confirmations where useful). Before/after pairs are
   the most persuasive deliverable for customers.

## Descriptions and tooltips

`description` on a resource or container becomes a hover tooltip in the SVG
(along with the full property list). Tooltips cost no pixels, so use them for
the detail that would clutter the canvas: what the service does in *this*
architecture, why it's sized the way it is, links to runbooks. The top-level
`description` renders as a visible paragraph under the title — use it to set
the scene in one or two sentences (what was reviewed, when, what the reader
should take away).
