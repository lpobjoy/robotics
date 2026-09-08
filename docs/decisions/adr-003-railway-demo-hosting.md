# ADR-003: Railway for a public demo link, alongside (not instead of) docker-compose/k3d

## Status

Accepted

## Context

CLAUDE.md section 4.9 specifies docker-compose for local dev and k3d for
step 13. Neither gives Lewis a URL he can hand someone before or during
an interview without them having Docker and this repo checked out.

Lewis provisioned a Railway project (`Robot-Sim`) for exactly that: a
public demo link, hosted alongside the local docker-compose/k3d setup
described in the brief, not replacing it.

## Decision

Deploy individual services to the existing Railway project as they
become demo-worthy, starting with `eam` (CLAUDE.md section 4.1). Each
service gets its own Dockerfile under `deploy/<service>/Dockerfile` --
the same "one image per component" rule as section 4.9 -- built from the
full repo context, because `uv sync` needs the whole workspace manifest
and lockfile even when only one member's code actually runs.

Build configuration is pinned explicitly via a `railway.json` at the repo
root (`build.builder: DOCKERFILE`, `build.dockerfilePath`), because
Railway's auto-detection (Railpack) inspects the repo, finds a Python
project using uv, but can't infer a start command for a multi-package uv
workspace with no single top-level `app.py`/`main.py` -- it fails with
"No start command detected" rather than guessing wrong.

## Consequences

- `railway up` uploads based on git-tracked files, not just what's on
  disk -- a new Dockerfile or config has to be committed (or at least
  `git add`ed) before it will actually take effect, discovered the hard
  way on the first deploy attempt (it silently fell back to Railpack
  because `railway.json` and `deploy/eam/Dockerfile` were still
  untracked).
- The container has no persistent volume; `EAM_DB_PATH` defaults to a
  container-local SQLite file. A redeploy or restart starts from a fresh,
  reseeded database (`eam/seed.py`). That's a feature for a demo -- every
  viewing starts from the same known state -- not an oversight.
- As later components (router, agent, console, ...) become demo-ready,
  each gets added as its own Railway service in the same project, with
  its own Dockerfile and its own entry describing how it's wired to the
  others (env vars for service-to-service URLs). Not building that
  wiring now -- only `eam` exists to deploy.
- This is a hosted extra for the interview process. It is not part of
  the CLAUDE.md section 9 definition of done, which is explicitly the
  local one-command docker-compose/k3d path.
