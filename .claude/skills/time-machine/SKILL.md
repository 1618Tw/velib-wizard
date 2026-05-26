---
name: time-machine
description: Use when the user asks for a project snapshot, status checkpoint, "time machine" entry, or wants to capture where the Vélib Wizard project currently stands. Writes a dated markdown file to time_machine/.
---

# Time Machine

Capture a point-in-time snapshot of the Vélib Wizard project so the user
can scroll back through past states. Each snapshot is one self-contained
markdown file in `time_machine/`.

## When to use
- User says "make a snapshot", "time machine", "checkpoint", "status doc"
- After finishing a chunk of work that meaningfully changed the project
- When closing a long working session

## Output

**Path:** `time_machine/YYYY-MM-DD_HH-MM.md` (local time)
**Get the timestamp:** `date "+%Y-%m-%d_%H-%M"` — never invent or
approximate; always shell out so the file matches wall-clock time.

The `time_machine/` directory is gitignored — snapshots stay local. Do
not commit them.

## What goes in the snapshot

Each snapshot is a single markdown file with these sections, in order:

1. **Project snapshot, one paragraph.** What Vélib Wizard is *right now*
   (stack, what's deployed, what's working).
2. **What changed since the previous snapshot.** Read the latest file in
   `time_machine/` (if any) to find a delta. Reference commits by short
   SHA. If no prior snapshot exists, summarise the recent history with
   `git log --oneline -10` instead.
3. **Current state — numbers.** DB size if recently observed, latest
   model MAE per horizon, anything else quantified during the session.
   Do not invent numbers; if not known, write "not measured this session".
4. **Known issues / open items.** What's broken, latent, or in progress.
   Mark severity (high / medium / low).
5. **Decisions locked in.** Things the user explicitly decided NOT to do
   or committed to a path on, so future sessions don't re-litigate them.
6. **Suggested next moves.** Short ordered list, with rough time
   estimates if possible.

## Gathering inputs

Run these before writing the snapshot:

```bash
git log --oneline -10                       # recent commits
git status                                  # any uncommitted work
git diff --stat HEAD~5..HEAD 2>/dev/null    # rough scope of recent work
ls -t time_machine/ | head -1               # most recent prior snapshot
```

Do not query Supabase or Render from within the skill — if the user
mentions fresh numbers in the session, use them; otherwise omit and
say so.

## Style

- Plain English, no marketing fluff (see [[feedback-communication]]).
- Italian-friendly: explain jargon if it's project-specific.
- Honest about what's not known. "DB size not re-measured this session"
  beats inventing a number.
- Tables for numeric or status data. Bullets for everything else.
- Keep under ~250 lines — this is a snapshot, not a manual.

## Do not
- Do not commit the snapshot to git.
- Do not overwrite an existing snapshot for the same minute — if one
  already exists, increment the minute by one and note it.
- Do not duplicate the content of the previous snapshot wholesale — the
  "what changed" section IS the value.
- Do not include code diffs — reference commit SHAs instead.

## After writing

Tell the user where the file is, in one sentence. No summary of its
contents in chat (the file itself is the artifact).
