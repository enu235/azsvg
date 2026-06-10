# Iteration 1 — analyst notes

## Headline
With-skill (updated): **100% pass rate (15/15 assertions)** across all three evals.
Old-skill baseline: **47% (7/15)**. The new skill was also ~2.5× faster
(115.7s vs 293.7s mean) and used ~17k fewer tokens per run — the old-skill agents
burned time and tokens improvising annotation conventions ("[!] FINDING" text in
meta lines, findings stuffed into the metadata footer) that the new skill provides
natively.

## Per-assertion patterns
- "SVG exists and is valid XML" passed in all 6 runs — non-discriminating, but a
  necessary regression floor.
- Every findings-related assertion (severity highlights, findings legend with fixes,
  numbered badges) failed on old_skill and passed on with_skill — these carry the
  delta and directly measure the new capability the user asked for.
- Eval-1 old_skill partially passed (3/5): SKUs via meta and improvised "1. HTTPS"
  edge labels worked, but no step circles and no Dataflow legend.

## Process caveats
- Subagents lacked shell permission in this environment, so they authored spec.yaml
  and the deterministic render step ran centrally (render_evals.py) with the renderer
  matching each config. Same treatment for both configs, so the comparison is fair —
  but timing/token numbers measure spec-authoring only, not render execution.
- One with-skill run (eval-2) died on a transient API socket error and was relaunched;
  its retry knew it could not run the renderer, which kept its token count low.
- Old-skill SKILL.md contains macOS-specific paths; baseline agents were told the
  actual snapshot path, which removed that handicap from the comparison.

## Visual review (manual, from PNG screenshots)
- with_skill eval-0/2: severity rings + badges sit exactly on the flagged resources,
  edge finding (plain-HTTP / failing image pull) recolors the whole line — reads
  instantly. Findings legends give portal-path or az-CLI fixes.
- Remaining cosmetic limit (both configs): a long vertical edge can pass through an
  unrelated resource's cell (no obstacle-avoidance routing). White text halos keep
  labels legible; documented in SKILL.md "When something looks off".
