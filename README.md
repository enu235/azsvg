# Azure SVG Diagram Skill

This repository contains an AI skill for generating self-contained SVG Azure architecture diagrams with official Microsoft Azure service icons — both **project diagrams** (topology, properties, numbered dataflow steps) and **review diagrams** that highlight issues found during customer troubleshooting (severity-coded rings, numbered finding badges, and a rendered Findings legend with fix recommendations).

The skill source lives in [`azure-svg-diagram/`](azure-svg-diagram/). That folder is the installable skill directory because it contains the required [`SKILL.md`](azure-svg-diagram/SKILL.md), scripts, and references.

## Features

- Official Microsoft Azure service icons (downloaded from Microsoft on first run; never modified, per their terms)
- Nested containers: subscription, resource group, vnet, subnet, region, AZ, on-prem
- Per-resource `properties` (rendered key/value config facts) and `description` (hover tooltips)
- Numbered dataflow steps with a Dataflow legend, matching architecture-center style
- `findings`: severity-coded callouts (critical / warning / info / ok) that highlight resources, edges, or containers, plus a Findings legend with detail and **Fix:** lines — built for customer troubleshooting and well-architected/security reviews
- Deterministic rendering: same YAML spec in, same SVG out

## Install

Copy the skill directory into your skills folder:

```bash
cp -R azure-svg-diagram ~/.claude/skills/
```

On Windows (PowerShell):

```powershell
Copy-Item -Recurse azure-svg-diagram "$env:USERPROFILE\.claude\skills\"
```

## First Run

The renderer uses the official Microsoft Azure icon set. Because the raw icons are not redistributed in this repository, run the bootstrap script once to download them into `~/.cache/azure-icons/`:

```bash
python azure-svg-diagram/scripts/bootstrap_icons.py
```

To verify the cache:

```bash
python azure-svg-diagram/scripts/bootstrap_icons.py --check
```

## Repository Layout

```text
azure-svg-diagram/            Skill source consumed by the AI agent
  SKILL.md                    Entry point + workflow
  scripts/                    bootstrap_icons.py, icon_index.py, render.py
  references/                 spec-format.md, annotations.md, examples.md, icon-catalog.md
azure-svg-diagram-workspace/  Eval runs, benchmark output, and test specs (not installed)
azure-svg-diagram.skill       Packaged skill artifact
```

## Validation

Run Python syntax checks:

```bash
python -m py_compile azure-svg-diagram/scripts/render.py azure-svg-diagram/scripts/icon_index.py azure-svg-diagram/scripts/bootstrap_icons.py
```

Render the bundled examples in `references/examples.md` and open the SVGs in a browser.
