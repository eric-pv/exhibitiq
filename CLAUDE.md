# ExhibitIQ — Claude Code Rules (Competition Edition V2.3)

## Mission
ExhibitIQ is a cloud-only, GitHub-first, **general-purpose** AI exhibition intelligence platform (Big x Reality competition project): users search or add any exhibition, acquire or import its data, normalize it through `schemas/`, run AI analysis, compare exhibitions/years and export reports in the Web Dashboard. It is not built for any particular exhibition; exhibitions and their data sources are chosen through the generic discovery and assessment flow. It has three core modules: Data Platform, AI Intelligence and the Web Dashboard (a required MVP module). The user is the project owner and sole phase-integration/acceptance authority.

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
4. **Every independently verifiable work item gets its own GitHub PR**, base = your OWN dev branch (never `main`). Title format: `【<merger> 合併】[<work-item-id>] <summary>` (see item 6). Include changed files, tests and results, schema impact, evidence (screenshots or preview for any `site/` change) and limitations.
5. **Merge your own PR** into your own dev branch. No review by the other developer is required.
6. **Every PR names its merger (Issue #15).** People: **Eric** = project owner (`ai`, GitHub `magician-eric`); **Albert** = colleague (`data`, GitHub `acyihung-infinityandbeyond`).
   - Base `dev/ai-intelligence` or `main` → title starts with `【Eric 合併】`, first body line `> **合併人：Eric**`, assignee `magician-eric`.
   - Base `dev/data-platform` (including shared-file sync PRs) → title starts with `【Albert 合併】`, first body line `> ⚠️ **合併人：Albert。Eric 請勿合併。**`, assignee `acyihung-infinityandbeyond`.
   - When reporting to the user, the first line states the merger, e.g. `合併人：Albert（請轉給 Albert，Eric 不要按合併）`.
7. The project owner keeps `docs/PROGRESS.md` up to date from merged PRs. Albert reports progress through PR descriptions and does not edit `PROGRESS.md`.
8. **Do not merge `dev/*` into `main` during an active phase.** Only after BOTH developers finish their phase work does the project owner run the phase integration (see below).
9. After a phase is integrated, synchronize both development branches with the newly accepted `main` before the next phase. Never discard unmerged work.
10. Shared rules and contracts reach `dev/data-platform` only through the one-way sync in `module-boundaries.md` §4; the colleague merges the sync PR. Exception: when the project owner explicitly authorizes the colleague to revise shared documents, the change is made on `dev/data-platform` and reaches `dev/ai-intelligence` through a sync PR that only the project owner merges (`module-boundaries.md` §4.6). Such authorization does not change module ownership.

## Architecture boundaries
- **強制規則（V2.3）：ExhibitIQ 嚴禁將任何特定展覽列為預設開發目標、主要資料來源、必要驗收對象或專案負責人必須指定的測試案例。所有展覽資料來源均由通用探索與評估流程決定。特定展覽的取得失敗，不得阻礙通用系統繼續開發。**
  - If one exhibition's data cannot be acquired, record the failure (dataset index, assessment report) and continue with other sources; never mark a phase or the framework as blocked because of one exhibition.
  - Data engineering picks legal public test sources itself based on availability; the project owner does not designate test exhibitions.
  - No exhibition's exhibitor count is ever an acceptance metric. Acceptance measures reusable system capability.
  - Past exhibition-specific research (e.g. earlier source assessments) is kept as historical record only, never as a dependency.
- **No exhibition is hard-coded in core code.** Core code, schemas, analysis logic and Dashboard pages/navigation must not depend on a specific exhibition's name, ID, URL, fields or counts. Exhibition-specific differences live only in exhibition registration data, source configs, source adapters or import mappings. Adding another exhibition must not require changing core code.
- Never assume every exhibition can be fully acquired automatically. Each new exhibition goes through source assessment; automatic, semi-automatic, file import, manual entry, partial success and insufficient data are all valid, explicitly labelled outcomes.
- One GitHub Private Monorepo. All development, execution, testing and crawling in cloud workspaces/GitHub Actions; no local computer compute requirement.
- GitHub stores versioned JSON/JSONL/CSV/manifests, code and reports. GitHub is NOT a transactional database. No PostgreSQL, Supabase, VPS or always-on FastAPI unless explicitly approved.
- `schemas/` is the ONLY shared data contract. Shared schema changes require project owner approval and matching fixture/tests updates.
- `crawler/`, `etl/` and Actions own acquisition, deterministic cleaning, provenance and data packaging.
- `skills/exhibitiq/` owns AI analysis, grounded recommendations and report generation.
- `site/` is the Web Dashboard (static React SPA). A static site cannot run crawlers, write to GitHub, call an LLM or hold credentials: "add exhibition / trigger acquisition / run analysis" are done via GitHub Actions `workflow_dispatch` and Claude Code sessions (spec §4.1); any in-browser one-click backend needs project owner approval. Pages read data only through `site/src/data/`, which consumes schema-validated files; pages never parse raw crawler output. One shared design system and component set; no per-page redesign.
- Every phase must deliver a Dashboard version that works in a browser, extending the same site (no per-phase demo rebuild); documents or passing tests alone do not count as the phase's visible result.
- Generality acceptance (spec §8.1): without changing core code, the system must normalize, analyse and display a different exhibition's data; test with at least two differently structured exhibition datasets (synthetic allowed if labelled; final results need at least one legally obtained real dataset).
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
- **Merger (Eric or Albert) on the first line**; work item ID and phase; feature branch and PR URL; **PR base branch**.
- Files changed; behavior implemented; tests and results; sample input/output; screenshots for `site/` changes.
- Schema compatibility; known limitations; manual verification steps.
- Whether the task owner has merged the PR (do not claim a merge without verification).

## Phase integration is a DIFFERENT task
The project owner alone authorizes it after both developers' phase work in `DEVELOPMENT_PLAN.md` is done. Inspect both dev branches and PR history; integrate in `integration/phase-N`; resolve conflicts, run end-to-end tests including the Dashboard, present evidence and screenshots; do not declare phase accepted or merge `main` without project owner approval.
