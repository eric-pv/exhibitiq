# ExhibitIQ — Claude Code Rules (Competition Edition V2.1)

## Mission
ExhibitIQ is a cloud-only, GitHub-first AI exhibition intelligence competition project for Big x Reality. It has three modules: Data Platform, AI Intelligence and the Web Dashboard (a required MVP module). The user is the project owner and sole phase-integration/acceptance authority.

## Before every task
1. Read `docs/ExhibitIQ_專案總規範.md`, `docs/DEVELOPMENT_PLAN.md`, `docs/PROGRESS.md` and `docs/architecture/module-boundaries.md`.
2. Identify your role — `ai` (project owner: AI + Web Dashboard) or `data` (colleague: data platform + GitHub Actions) — the current phase, and the work item ID from `DEVELOPMENT_PLAN.md`.
3. Understand the whole system, including the other developer's modules and the contracts between them. You may read anything; you may modify only paths your role owns (`module-boundaries.md` §2).
4. Inspect the actual repository, schemas, tests and branch state. Never invent existing files, APIs, data or capabilities.

## Task workflow
1. **No GitHub Issue is needed for normal work.** Work directly from `DEVELOPMENT_PLAN.md`. Use Issues only for bugs, major requirement changes, cross-person coordination, or problems that need tracking.
2. Branch from your OWN development branch:
   - AI: `feature/ai/<work-item-id>-<slug>` from `dev/ai-intelligence` (e.g. `feature/ai/w1-01-frontend-scaffold`).
   - Data: `feature/data/<work-item-id>-<slug>` from `dev/data-platform`.
3. Implement only that work item. Run the relevant cloud tests, validate schema compatibility, document limitations.
4. **Every independently verifiable work item gets its own GitHub PR**, base = your OWN dev branch (never `main`). Title starts with `[<work-item-id>]`. Include changed files, tests and results, schema impact, evidence (screenshots or preview for any `site/` change) and limitations.
5. **Merge your own PR** into your own dev branch. No review by the other developer is required.
6. The project owner keeps `docs/PROGRESS.md` up to date from merged PRs. The colleague reports progress through her PR descriptions and does not edit `PROGRESS.md`.
7. **Do not merge `dev/*` into `main` during an active phase.** Only after BOTH developers finish their phase work does the project owner run the phase integration (see below).
8. After a phase is integrated, synchronize both development branches with the newly accepted `main` before the next phase. Never discard unmerged work.
9. Shared rules and contracts reach `dev/data-platform` only through the one-way sync in `module-boundaries.md` §4; the colleague merges the sync PR.

## Architecture boundaries
- One GitHub Private Monorepo. All development, execution, testing and crawling in cloud workspaces/GitHub Actions; no local computer compute requirement.
- GitHub stores versioned JSON/JSONL/CSV/manifests, code and reports. GitHub is NOT a transactional database. No PostgreSQL, Supabase, VPS or always-on FastAPI unless explicitly approved.
- `schemas/` is the ONLY shared data contract. Shared schema changes require project owner approval and matching fixture/tests updates.
- `crawler/`, `etl/` and Actions own acquisition, deterministic cleaning, provenance and data packaging.
- `skills/exhibitiq/` owns AI analysis, grounded recommendations and report generation.
- `site/` is the Web Dashboard (static React SPA). Pages read data only through `site/src/data/`, which consumes schema-validated files; pages never parse raw crawler output. One shared design system and component set; no per-page redesign.
- Every phase must deliver a Dashboard version that works in a browser; documents or passing tests alone do not count as the phase's visible result.
- Raw evidence is immutable; inferred analysis must never overwrite sourced facts, and the Dashboard must never display AI inference as verified fact.
- Use source IDs, timestamps, hashes and completeness statuses. Never invent counts, company facts, citations, scores or confidence.
- Use reusable modules, no duplicate frameworks. Limit Git history growth; do not assume Actions artifacts are permanent.
- No secrets in Git or in the frontend. Never publish private intelligence to public GitHub Pages. Protect workflows from concurrent writes and overly broad token permissions.

## Stop and ask the project owner if
- Task changes architecture, shared schema, storage choice, public/private publishing or module ownership.
- Task requires access to another person's development branch or changes outside your role's paths.
- Source access is blocked or data completeness cannot be established.
- The requested feature depends on unavailable cloud permissions, credentials or execution capabilities.

## Required final task response
- Work item ID and phase; feature branch and PR URL; **PR base branch**.
- Files changed; behavior implemented; tests and results; sample input/output; screenshots for `site/` changes.
- Schema compatibility; known limitations; manual verification steps.
- Whether the task owner has merged the PR (do not claim a merge without verification).

## Phase integration is a DIFFERENT task
The project owner alone authorizes it after both developers' phase work in `DEVELOPMENT_PLAN.md` is done. Inspect both dev branches and PR history; integrate in `integration/phase-N`; resolve conflicts, run end-to-end tests including the Dashboard, present evidence and screenshots; do not declare phase accepted or merge `main` without project owner approval.
