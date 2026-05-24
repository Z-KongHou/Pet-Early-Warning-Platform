# Yingshi Project Conventions

## Repository layout

```
yingshi/                    # main monorepo (git root)
├── backend/                # Spring Boot 2.7, port 8081
├── frontend/               # Next.js 16, port 3000
├── ai/                     # Python FastAPI (monorepo only, NOT in latest snapshot)
├── ai-old/                 # legacy AI (monorepo only)
├── docs/
├── .cursor/skills/         # project skills (this skill lives here)
└── latest/
    └── yingshi/            # upstream snapshot (separate .git repo) — FIXED PATH
        ├── backend/
        ├── frontend/
        └── docs/
```

**Snapshot path is fixed:** `<repo>/latest/yingshi/` — do not ask for alternate paths.

## Local MySQL (fixed)

| Setting | Value |
|---------|-------|
| Host | `localhost` |
| Port | `3306` |
| Database | `yingshi_database` |
| User | `root` |
| Password | **`23050929`** |

Apply to:
- `backend/src/main/resources/application.yml` → `spring.datasource.password` only
- `backend/sql/migrations/*.ps1` default `-Password`
- Any migration runner invoked by this skill

Never commit alternate local passwords from upstream snapshots (e.g. `Gyp20051215`).

## Git workflow

- Compare: main repo vs `latest/yingshi` (tree diff + file lists)
- Sync: cherry-pick when tree differs; skip when tree identical
- Post-sync: always run `post-sync.ps1` (DB password, migrations, `pnpm install`)
- Commit: only when user explicitly requests
- Push: only when user explicitly requests

## Modules excluded from sync

| Path | Reason |
|------|--------|
| `ai/` | Exists only in monorepo |
| `ai-old/` | Exists only in monorepo |
| `latest/` | Snapshot container |

## Video files

Include `backend/video/*.mp4` when syncing from latest — do **not** exclude or strip them.

## Frontend after sync

Always run (via `post-sync.ps1`):

```bash
cd frontend && pnpm install
```

Common deps from camera features: `ezuikit-js`, `hls.js`.

## Backend after sync

- `@EnableScheduling` required for recording/status jobs
- Recording needs **FFmpeg** on PATH
- API keys: MySQL local `23050929`; ezviz + backend `ai.*` from latest — see `references/api-keys-policy.md`

## Migration file conventions

- Location: `backend/sql/migrations/`
- Naming: `NNN_<snake_case_description>.sql`
- Must be idempotent (stored procedure + `INFORMATION_SCHEMA` pattern)
- Always update `backend/sql/init.sql` for new installs
- Always update `docs/database-schema.md`
- Run via `mysql -e "source ..."` (not pipe) for `DELIMITER` support

## Known upstream issues (as of 2026-05-23 sync)

- Videos under 5 minutes may not save correctly
- H264 encoding issues may affect some cameras
