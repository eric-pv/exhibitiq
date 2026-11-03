# ExhibitIQ — Claude Code Rules (Competition Edition V2.0)

## Mission
ExhibitIQ is a cloud-only, GitHub-first AI exhibition intelligence competition project for Big x Reality. Read `docs/ExhibitIQ_專案總規範.md` and the assigned Issue before every task. The user is the project owner and sole phase-integration/acceptance authority.

## Mandatory task workflow
1. Identify your role: `ai` (project owner) or `data` (colleague), and current phase/Issue.
2. Inspect the actual repository, schemas, tests and branch state. Never invent existing files, APIs or capabilities.
3. Create a task-specific branch from your OWN development branch:
   - AI: `feature/ai/<issue>-<slug>` from `dev/ai-intelligence`.
   - Data: `feature/data/<issue>-<slug>` from `dev/data-platform`.
4. Implement only the assigned Issue. Run relevant cloud tests, validate schema compatibility, document limitations.
5. Commit, push and **create a visible GitHub Pull Request for EVERY Issue**, with base set to your OWN development branch (not `main`). Include Issue, changed files, tests, schema impact, evidence, limitations.
6. The **owner of the Issue reviews and merges their own PR** into their own development branch. Do not require the project owner to review the colleague's individual PRs. Do not begin the next Issue before the previous one is merged, unless explicitly instructed.
7. **Do not merge `dev/*` into `main` during an active phase.** When BOTH people's phase tasks are complete, the project owner requests a separate phase-integration instruction. Only then use `integration/phase-N` to integrate both development branches, test, and submit an integration PR to `main`. The project owner alone accepts and merges that integration PR.
8. After a phase is integrated, synchronize both development branches with the newly accepted `main` before the next phase. Never discard unmerged work.

## Architecture boundaries
- One GitHub Private Monorepo. All development, execution, testing and crawling in cloud workspaces/GitHub Actions; no local computer compute requirement.
- GitHub stores versioned JSON/JSONL/CSV/manifests, code and reports. GitHub is NOT a transactional database. No PostgreSQL, Supabase, VPS or always-on FastAPI unless explicitly approved.
- `schemas/` is the ONLY shared data contract. Shared schema changes require project owner approval and matching fixture/tests updates.
- `crawler/`, `etl/` and Actions own acquisition, deterministic cleaning, provenance and data packaging.
- `skills/exhibitiq/` owns AI analysis, grounded recommendations and report generation.
- Raw evidence is immutable; inferred analysis must never overwrite sourced facts.
- Use source IDs, timestamps, hashes and completeness statuses. Never invent counts, company facts, citations or confidence.
- Use reusable modules, no duplicate frameworks. Limit Git history growth; do not assume Actions artifacts are permanent.
- No secrets in Git. Never publish private intelligence to public GitHub Pages. Protect workflows from concurrent writes and overly broad token permissions.

## Stop and ask the project owner if
- Task changes architecture, shared schema, storage choice, public/private publishing or module ownership.
- Task requires access to another person's development branch or changes outside allowed paths.
- Source access is blocked or data completeness cannot be established.
- The requested feature depends on unavailable cloud permissions, credentials or execution capabilities.

## Required final task response
- Issue and phase; feature branch and PR URL; **PR base branch**.
- Files changed; behavior implemented; tests and results; sample input/output.
- Schema compatibility; known limitations; manual verification steps.
- Whether the task owner has merged the PR (do not claim a merge without verification).

## Phase integration is a DIFFERENT task
The project owner alone authorizes it after all phase Issues are done. Inspect both dev branches and PR history; integrate in `integration/phase-N`; resolve conflicts, run end-to-end tests, present evidence; do not declare phase accepted or merge `main` without project owner approval.
