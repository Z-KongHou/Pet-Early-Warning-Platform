---
name: yingshi-latest-sync
description: Sync yingshi monorepo frontend/backend from the fixed latest/yingshi/ snapshot, compare diffs, cherry-pick new commits, run SQL migrations, enforce local MySQL password 23050929, and auto-run pnpm install. Use whenever the user mentions latest/, syncing upstream yingshi code, merging Pet-Early-Warning-Platform updates, comparing main vs latest frontend/backend, cherry-picking from latest/yingshi, database migration for yingshi, or updating the yingshi project from a downloaded snapshot — even if they only say "更新代码" or "同步 latest". This skill lives in .cursor/skills/ for the yingshi project.
compatibility: Requires git, MySQL 8 client (Windows), pnpm, PowerShell. Snapshot path fixed at latest/yingshi/ under repo root.
---

# Yingshi Latest Sync

Workflow for keeping the **main monorepo** (`backend/`, `frontend/`, `docs/`) aligned with **`latest/yingshi/`**, while preserving monorepo-only modules (`ai/`, `ai-old/`).

Read `references/project-conventions.md` and `references/api-keys-policy.md` before changing config.

Skill path: `.cursor/skills/yingshi-latest-sync/`

## When to use

| User intent | Action |
|-------------|--------|
| Compare latest vs main | Phase 1 |
| Sync new commits from latest | Phase 2 (+ auto Phase 3) |
| Apply schema changes | Phase 3 (part of post-sync) |
| Fix backend DB connection | Phase 3 (part of post-sync) |

Do **not** sync `ai/` from latest.

## Phase 1 — Compare

```powershell
powershell -NoProfile -File ".cursor/skills/yingshi-latest-sync/scripts/compare-latest.ps1" -RepoRoot "<repo-root>"
```

Summarize: file counts, files only in latest, tree/commit delta, key areas (`CameraController`, `cameras/page.tsx`, `application.yml`).

Snapshot path is **fixed** at `<repo>/latest/yingshi/`. If missing, tell user to place snapshot there.

## Phase 2 — Sync

```powershell
powershell -NoProfile -File ".cursor/skills/yingshi-latest-sync/scripts/sync-from-latest.ps1" -RepoRoot "<repo-root>"
```

Behavior:
1. Cherry-picks only when tree differs from `latest/yingshi`
2. Skips cherry-pick when already identical
3. **Always runs post-sync** (unless `-DryRun` or `-SkipPostSync`)

Dry run: add `-DryRun` (shows pending commits, skips cherry-pick and post-sync).

**On conflict:** resolve, then `git cherry-pick --continue`. Abort: `git cherry-pick --abort`.

Do **not** commit unless user asks.

## Phase 3 — Post-sync (automatic)

Runs via `scripts/post-sync.ps1` after every sync:

1. `ensure-local-db-password.ps1` → `spring.datasource.password = 23050929`
2. `run-migrations.ps1` → all `backend/sql/migrations/*.sql`
3. `pnpm install` in `frontend/`

Manual run:

```powershell
powershell -NoProfile -File ".cursor/skills/yingshi-latest-sync/scripts/post-sync.ps1" -RepoRoot "<repo-root>"
```

### Adding a new migration

1. Update `backend/sql/init.sql`
2. Add idempotent `backend/sql/migrations/NNN_<name>.sql`
3. Update `docs/database-schema.md`

## API keys after sync

**Fixed policy:**
- MySQL `spring.datasource.password` → **`23050929`** (forced in post-sync)
- Ezviz + backend `ai.*` in `application.yml` → **latest's values** (from cherry-pick; never restore main's old keys)
- `ai/.env` → not touched (latest has no `ai/` module)

On cherry-pick conflicts in `application.yml`, take latest for ezviz/ai; DB password set to `23050929` in post-sync.

See `references/api-keys-policy.md`.

## Post-sync checklist

Report to user:

```
- [ ] Cherry-pick completed (or tree already matched)
- [ ] spring.datasource.password = 23050929
- [ ] SQL migrations executed
- [ ] pnpm install completed
- [ ] backend/video/*.mp4 included if synced
- [ ] backend: mvn spring-boot:run
- [ ] frontend: pnpm dev
```

## Output format

```markdown
## Sync report

### Commits applied
(SHAs or "already up to date")

### Schema
(migration results)

### Config
(MySQL password → 23050929; ezviz + ai.* from latest)

### Frontend
(pnpm install result)

### Manual follow-ups
(ffmpeg, ezviz key check, known issues from commit messages)
```

## Edge cases

| Situation | Handling |
|-----------|----------|
| Main has `ai/`, latest does not | Keep main; never delete |
| `backend/video/*.mp4` in latest | Sync as-is (do not exclude) |
| Cherry-pick brings wrong DB password | post-sync fixes to 23050929 |
| Cherry-pick overwrites ezviz/ai keys | **Expected** — keep latest's values |
| `application.yml` merge conflict | latest wins for ezviz/ai; DB password → 23050929 |
| No shared git history | Manual copy `backend/` + `frontend/` only; ask user |
| User asks to commit | Follow user git rules |

## Bundled scripts

| Script | Purpose |
|--------|---------|
| `compare-latest.ps1` | Diff summary |
| `sync-from-latest.ps1` | Cherry-pick + trigger post-sync |
| `post-sync.ps1` | DB password + migrations + pnpm install |
| `run-migrations.ps1` | SQL migrations |
| `ensure-local-db-password.ps1` | Force password 23050929 |
