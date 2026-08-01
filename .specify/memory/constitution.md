<!--
Sync Impact Report
Version change: 2.0.0 -> 2.1.0
Old version: 2.0.0
New version: 2.1.0
Ratification date: TODO(RATIFICATION_DATE): original adoption date unknown
Last amended: 2026-07-12
Modified principles: none
Added sections:
- Article 10 - Skills (new principle: self-contained directory-based skill format)
Removed sections: none
Templates requiring updates:
- .specify/templates/constitution-template.md - no change needed
- .specify/templates/plan-template.md - ✅ no change needed (Constitution Check is dynamic placeholder)
- .specify/templates/spec-template.md - ✅ no change needed
- .specify/templates/tasks-template.md - ✅ no change needed
- .specify/templates/checklist-template.md - ✅ no change needed
Follow-up TODOs:
- 🔴 Flat .skill.md files in skills/ (telegram-memory.skill.md, telegram-request-normalization.skill.md, telegram-voice-action.skill.md) should be removed or migrated to the directory-only format per Article 10
- ✅ RESOLVED 2026-07-12: Flat .skill.md files deleted from skills/ root. Directory-based skills (skills/telegram-memory/SKILL.md, skills/telegram-request-normalization/SKILL.md, skills/telegram-voice-action/SKILL.md) retain the functionality.
-->

# Constitution

**Version**: 2.1.0 | **Ratified**: TODO(RATIFICATION_DATE): original adoption
date unknown | **Last Amended**: 2026-07-12

This document governs all development on this project. Specifications are the
source of truth. No implementation proceeds without an approved spec. No merge
or acceptance occurs without completing all compliance and checklist
requirements.

## Article 1 — Testing Strategy

- TDD is mandatory. Every feature and every bug fix must include at least one
  new automated test written before or alongside the implementation. No
  exceptions.
- All tests must pass before any feature or fix can be merged or accepted.
- Automated regression and compliance tests live under the `/tests` directory.
  Supporting harness scripts may live at the repo root when those `/tests`
  entrypoints invoke them directly and a stable path is required by the
  toolchain.
- `make test` runs the full test suite and is a hard blocker for acceptance.
- External LLM integration tests should prefer free-of-charge or default-safe
  configurations unless a spec explicitly documents otherwise.

## Article 2 — Runtime & Infrastructure

- Hermes Agent is the multi-purpose agent runtime and project identity.
- Docker Compose is the canonical deployment and runtime model. A
  `docker-compose.yml` is required at the project root.
- Reliance on DinD or similar infrastructure sidecars for isolated execution
  is part of the architecture. No host Docker socket is mounted into the agent
  container.
- The Hermes container must run as a non-root user.
- The repository's `Dockerfile` and `docker-compose.yml` are the only valid
  build and start paths. Standalone `docker run` is not valid for development
  or production.
- A Makefile with at least `run` and `test` targets must exist at the project
  root.
- The README must document at minimum: prerequisites, quickstart, and
  architecture overview.

## Article 3 — Persistence

- All stateful data must use named Docker volumes. Bind mounts are allowed
  only for repo-owned configuration, definitions, skill files, or other
  non-stateful development assets.
- Every named volume must be declared explicitly in `docker-compose.yml`.
- Each volume must have a single, clearly defined purpose.

## Article 4 — Secrets Management

- All secrets (API keys, tokens, private keys) must be supplied through
  environment variables only. No secrets in code, committed config files, or
  container images.
- A `.env.example` file listing every required environment variable with
  placeholder values and documentation must be committed to the repository.
  The actual `.env` file is never committed and must be listed in
  `.gitignore`.
- The runtime or entrypoint must validate that all required environment
  variables are set before starting.
- An automated secret audit (scanning for committed secrets or hard-coded
  credentials) must be included in the test suite or CI-equivalent checks.

## Article 5 — LLM Model Provider Policy

- The project is provider-agnostic. Any LLM provider or model backend may be
  supported by defining it in the relevant configuration, specs, and feature
  documentation. No specific provider is mandated at constitutional level.
- Default configured models must be free-of-charge. No default model may incur
  per-token or per-request billing.
- Paid models may be supported but must require explicit opt-in configuration,
  primarily through dedicated environment variables in the runtime.
- External LLM integration tests should prefer free-of-charge or default-safe
  model configurations unless a spec explicitly documents otherwise.
- Provider-specific environment variable names, switching procedures, and
  backend mechanics belong in specs and feature docs, not in this
  constitution.

## Article 6 — Agent Architecture

- Hermes is a multi-purpose agent platform and runtime. It may support
  multiple agent roles, behaviors, and workflows.
- Specialized agent behaviors, roles, or workflows (such as developer-oriented
  agents or stage-specific subagents) must be defined in dedicated specs or
  agent-specific markdown files, not in this constitution.
- Agent workflows must respect the project's specification lifecycle: no
  implementation without an approved spec, and all compliance gates must be
  satisfied before acceptance.

## Article 7 — Interface

- Telegram is the sole human interface for the Hermes runtime.
- Existing spec-kit approval checkpoints (such as `/approve` gates) are
  defined in the workflow configuration and are not expanded by this article.
- Human-driven stages precede automated stages where the workflow defines
  review gates.

## Article 8 — Hermes Memory Persistence

- Memory writes must be explicit and scoped. Implicit full-conversation dumps,
  transcript mirroring, or blanket session archival are forbidden.
- Persisted long-term memory must be intended for cross-session recall of
  user-level context, preferences, and prior outcomes.
- Short-term or ephemeral context must remain in-process only and MUST NOT be
  persisted as long-term memory by default.
- Persisted memory must survive Hermes container restarts, sidecar restarts,
  and full `docker compose down` / `up` cycles when long-term memory is
  claimed or supported.
- Memory must remain isolated by namespace, user, or conversation scope.
- Memory changes must have compliance tests in `/tests` that verify
  persistence, isolation, and correct behavior under restart.

## Article 9 — Memory Architecture & Compliance

- The long-term memory architecture is vendor-agnostic and backend-agnostic.
  No specific memory product, database, or service is mandated at
  constitutional level.
- Memory backends must provide:
  - Explicit persistence: data is written only on explicit request or
    documented automatic-capture rules.
  - Durability: persisted data survives restarts and redeployments.
  - Namespace isolation: data belonging to one user or scope is not
    visible to another.
  - Testability: memory behavior must be covered by automated tests in
    `/tests`.
- The architecture, retention policy, deletion mechanism, compaction strategy,
  and any backend-specific behavior must be documented in the relevant spec
  when a memory feature is implemented.
- No memory data may be transmitted outside the deployment network unless
  explicitly documented and approved by spec.
- Memory backends must not require secrets, API keys, or external credentials
  for default local operation.

## Article 10 — Skills

- Every skill MUST reside in its own subdirectory under `skills/` named after
  the skill (e.g., `skills/dev/`).
- Each skill directory MUST contain a file named `SKILL.md` that defines the
  skill's behavior, rules, and contracts.
- All files required by the skill (scripts, templates, configuration, data)
  MUST be contained within the skill's own directory tree.
- Cross-references to files outside the skill directory, symbolic links across
  skill boundaries, and symlinks escaping the skill directory are FORBIDDEN.
- Skills MUST be self-contained: every file needed to understand, deploy, or
  test the skill MUST exist within its own directory.
- Flat `.skill.md` files at the `skills/` root level are FORBIDDEN. All skill
  definitions MUST use the directory-based format.

## Compliance Gate

Before an implementation plan may proceed, verify:

- [ ] Every planned feature includes at least one test in `/tests`
- [ ] `make test` runs the full test suite with no failures
- [ ] Runtime model is compatible with Docker Compose conventions
- [ ] No security or secret-management rules are violated
- [ ] Makefile and README minimum requirements are satisfied
- [ ] If memory features are included:
  - Memory behavior is documented by the relevant spec
  - Persistence, durability, and isolation expectations are tested
  - Security and privacy boundaries are respected
- [ ] Skill structure conforms to Article 10: directory-based under `skills/`,
      self-contained, no flat `.skill.md` files, no cross-directory references
- [ ] All constitutional rules are respected

Any exception must be documented in the plan's Complexity Tracking section
with justification.

## Governance

- **Supremacy**: This constitution supersedes any conflicting local
  conventions, tool configurations, or ad-hoc practices.
- **Amendment procedure**: Changes to this constitution MUST follow the
  project's amendment workflow: propose the change, obtain approval through
  the established interface, update this constitution, record the change in
  `CHANGELOG.md`, and update the version and last-amended date.
- **Versioning policy**: Constitution versions follow semantic versioning.
  MAJOR for incompatible removals or redefinitions of principles, MINOR for
  added principles or materially expanded guidance, PATCH for wording
  clarifications or non-semantic refinements.
- **Compliance reviews**: Before planning or merging, maintainers MUST verify
  compliance with this constitution and record verification in the plan's
  Constitution Check section.
