# API Keys Policy During Sync

Confirmed project policy:

- **MySQL password** → always use local value **`23050929`**
- **All other keys in `application.yml`** → adopt **latest** values via cherry-pick (do not restore main's old values)

## 1. MySQL password (`spring.datasource.password`)

| Source | Value |
|--------|-------|
| latest snapshot | author's password (e.g. `Gyp20051215`) — **ignore** |
| this monorepo (local) | **`23050929`** — **always use** |

After every sync, `ensure-local-db-password.ps1` overwrites only `spring.datasource.password` with `23050929`.

Do **not** backup or restore main's old DB password.

## 2. Ezviz keys (`ezviz.app-key`, `ezviz.app-secret`)

**Policy: adopt latest's values.**

Cherry-pick writes latest's ezviz keys into `application.yml`. Do not revert to main's pre-sync values.

Used for: camera live stream, cloud recording, device status (萤石云 Open API).

## 3. AI keys in backend (`ai.api-key`, `ai.api-url`, `ai.model`)

**Policy: adopt latest's values in `application.yml`.**

Cherry-pick writes latest's `ai.*` section. Do not revert to main's pre-sync values.

Used by: Spring Boot `AnalysisService` → 智谱 GLM Chat Completions.

## 4. Python `ai/.env` (out of scope)

Latest snapshot has **no** `ai/` module. Sync does **not** touch `ai/.env`.

If backend `ai.api-key` and Python `ai/.env` diverge after sync, that is expected unless the user manually aligns them.

## Summary

| Credential | Source after sync |
|------------|-------------------|
| `spring.datasource.password` | **Local: `23050929`** (forced in post-sync) |
| `ezviz.app-key` / `app-secret` | **latest** (from cherry-pick) |
| `ai.api-key` / `api-url` / `model` | **latest** (from cherry-pick) |
| `ai/.env` | unchanged (not in latest) |

## Agent rules

1. Never restore main's ezviz or ai keys after sync.
2. Never skip `ensure-local-db-password.ps1` — MySQL must stay `23050929`.
3. If `application.yml` has merge conflicts during cherry-pick, resolve by taking latest's ezviz/ai values but set `spring.datasource.password` to `23050929` before completing the cherry-pick or in post-sync.
