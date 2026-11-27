---
name: insights
description: >-
  Analyze past Antigravity (AGY) conversations over a chosen time window (default 30 days)
  to uncover usage patterns, recurring friction, tool/permission bottlenecks, and concrete
  customization recommendations (rules, skills, hooks, permissions, workflows). Use when
  the user invokes /insights or asks for a usage retrospective, friction analysis, or
  efficiency recommendations based on past chats.
---

# Antigravity Usage Insights (`/insights`)

Generates a grounded, evidence-backed usage & efficiency report by combining deterministic
metrics from local transcripts (`~/.gemini/antigravity-cli/`) with parallel qualitative
facet analysis across sessions.

## Arguments

The user may specify a lookback window (e.g., `/insights 90 days`, `/insights last 3 months`,
`/insights last 2 weeks`, `/insights 20 sessions`). Defaults to **30 days** if unspecified.

## Workflow

### Step 1: Extract Metrics & Session Batches

Run the extractor script into this conversation's scratch directory (so no clutter is left
in the user's workspace):

```bash
python3 /home/lp-lima/.gemini/skills/insights/scripts/extract_sessions.py \
  --days <DAYS> \
  --exclude-cid "$ANTIGRAVITY_CONVERSATION_ID" \
  --out-dir "<CONVERSATION_SCRATCH_DIR>/insights_data"
```

Pass `--limit <N>` instead of (or with) `--days` if the user requested a specific session count.

Verify that `metrics.json` and `batches/batch_*.md` were created, and read `metrics.json`
in full (including `customizations_inventory` so recommendations never duplicate existing
rules, skills, hooks, or allowlisted commands).

### Step 2: Parallel Qualitative Facet Analysis

- If there is **1 batch** (small window): read it directly yourself.
- If there are **2+ batches**: use `run_workflow` to fan out across every `batch_*.md` file
  in parallel using `model="flash"`. Each worker reads its assigned batch file and returns
  a structured JSON summary containing:
  - `project_themes`: primary tasks/projects worked on
  - `what_worked_well`: smooth, high-leverage workflows or custom skills
  - `friction_events`: concrete instances of repeated corrections, wasted turns, tool/MCP
    failures, permission/GPG interruptions, misunderstood intent, or abandoned/killed sessions
    (always citing `conversation_id` and date)
  - `repeated_manual_patterns`: recurring multi-step tasks or prompt instructions that could
    be codified into a rule, skill, hook, or permission allowlist
  - `prompting_and_feature_opportunities`: missed opportunities for `/plan`, `/grill-me`,
    `/goal`, `/compact`, `/model`, subagents, or clearer upfront constraints

### Step 3: Deep-Dive Verification (Optional, High-Signal Only)

For the 2–4 most surprising or highest-friction sessions surfaced in Steps 1–2, spot-check
their actual `transcript.jsonl` (or `settings.json` / `hooks.json` / `GEMINI.md` / `AGENTS.md`)
to verify root causes before making prescriptions.

### Step 4: Write the Insights Artifact

Create a polished, scannable Markdown artifact (`insights_report_<YYYY-MM-DD>.md`) in the
artifact directory (`UserFacing=true, RequestFeedback=false`) with these sections:

1. **Executive Summary & At-a-Glance Metrics** (table + key headline takeaways: sessions,
   active days, turns, models, cache hit rate, tool error rate, top skills/MCPs)
2. **What You Work On & What's Working Well** (top project clusters + high-leverage habits)
3. **Top Friction Points (Evidence-Backed)** (ranked by impact, with counts and clickable
   `[Session Title](conversation://<conversation-id>)` links)
4. **Configuration & Setup Audit** (concrete bugs, redundancies, or dead entries spotted in
   `settings.json`, `hooks.json`, `GEMINI.md` / `AGENTS.md`, skills, or MCPs)
5. **Actionable Recommendations** — grouped by effort/impact with copy-pasteable snippets:
   - **Quick Wins (< 5 min)**: permission allowlist additions, settings/hook cleanups, rule tweaks
   - **New or Refined Skills / Workflows**: recurring manual patterns worth automating
   - **Prompting & AGY Feature Habits**: specific built-in commands/modes to use more (or differently)
6. **Suggested Next Actions** (short numbered menu the user can reply with to apply immediately)

Respond concisely in chat pointing the user to the artifact and highlighting the top 3–5
highest-leverage actions they can ask you to apply next. Do **not** edit their config files
or rules automatically unless they explicitly ask.
