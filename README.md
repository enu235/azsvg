# Azure SVG Diagram Skill

This repository contains an AI skill for generating self-contained SVG Azure architecture diagrams with official Microsoft Azure service icons.

The skill source lives in [`azure-svg-diagram/`](azure-svg-diagram/). That folder is the installable skill directory because it contains the required [`SKILL.md`](azure-svg-diagram/SKILL.md), scripts, and references.

## Install

Copy the skill directory into your skills folder:

```bash
cp -R azure-svg-diagram ~/.claude/skills/
```

The existing `.skill` zip package is preserved in the repository history as the original working package. The editable source of truth for future development is the folder form in `azure-svg-diagram/`.

## First Run

The renderer uses the official Microsoft Azure icon set. Because the raw icons are not redistributed in this repository, run the bootstrap script once to download them into `~/.cache/azure-icons/`:

```bash
python3 ~/.claude/skills/azure-svg-diagram/scripts/bootstrap_icons.py
```

To verify the cache:

```bash
python3 ~/.claude/skills/azure-svg-diagram/scripts/bootstrap_icons.py --check
```

## Repository Layout

```text
azure-svg-diagram/   Skill source consumed by the AI agent
.workspace/          Preserved eval runs, benchmark output, and iteration notes
azure-svg-diagram.skill  Original working package artifact
```

## Validation

Run the basic skill validator:

```bash
python3 /Users/allan/.codex/skills/.system/skill-creator/scripts/quick_validate.py azure-svg-diagram
```

Run Python syntax checks:

```bash
python3 -m py_compile azure-svg-diagram/scripts/*.py
```
