# Feature Specification: Obsidian in Docker with me/raw and me/wiki vaults

**Feature Branch**: `001-obsidian-vaults`

**Created**: 2026-08-01

**Status**: Draft

**Input**: User description: "Create a Docker container running Obsidian. It will be used later to apply an article that builds vaults from raw documents (PDFs, videos, transcriptions, links, etc.). The idea is to have a vault called me/raw and another called me/wiki. Obsidian should expose the wiki vault, and the wiki vault will have markdown generated from the real files. Deploy via Docker Agent."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Obsidian runs in Docker and is reachable from the browser (Priority: P1)

As a user, I want to open Obsidian in my browser so that I can use it from anywhere without installing desktop software.

**Why this priority**: Without a reachable Obsidian UI, nothing else in this feature is usable.

**Independent Test**: Can be fully tested by opening the deploy URL in a browser and confirming the Obsidian interface loads and responds to clicks.

**Acceptance Scenarios**:

1. **Given** the container is deployed, **When** I open the public URL, **Then** the Obsidian window is visible in the browser and interactive.
2. **Given** the container is deployed, **When** I type text in a note, **Then** the text is saved to disk inside the container.

---

### User Story 2 - The me/raw vault exists for raw documents (Priority: P1)

As a user, I want a vault at `me/raw` where raw source documents (PDFs, videos, transcriptions, links, etc.) will live, so that I can drop raw material into it.

**Why this priority**: The raw vault is the input side of the knowledge workflow.

**Independent Test**: Can be tested by checking the `me/raw` folder exists with its `.obsidian` vault metadata and by placing a file in it.

**Acceptance Scenarios**:

1. **Given** the container is running, **When** I inspect `/data/me/raw`, **Then** the directory exists and contains an `.obsidian` config folder.
2. **Given** a file is placed in `/data/me/raw`, **When** I open the vault in Obsidian, **Then** the file is visible in the file explorer.

---

### User Story 3 - The me/wiki vault is exposed with markdown generated from raw files (Priority: P1)

As a user, I want a vault at `me/wiki` that Obsidian exposes, where markdown files generated from the raw documents will live, so that I can browse a wiki of my knowledge.

**Why this priority**: This is the output side of the workflow and the vault the user expects Obsidian to expose.

**Independent Test**: Can be tested by checking the `me/wiki` folder exists with `.obsidian` metadata and is registered in the Obsidian vault list (obsidian.json), and by verifying a generated markdown file appears when placed in the vault.

**Acceptance Scenarios**:

1. **Given** the container is running, **When** I inspect `/data/me/wiki`, **Then** the directory exists and contains an `.obsidian` config folder.
2. **Given** both vaults are registered, **When** Obsidian starts, **Then** the wiki vault is open (or selectable from the vault switcher) and the raw vault is listed.
3. **Given** a markdown file is generated into `/data/me/wiki`, **When** I refresh Obsidian, **Then** the note appears and is editable.

---

### User Story 4 - Vault data persists across container restarts (Priority: P2)

As a user, I want my vaults and settings to survive container recreation, so that I do not lose notes.

**Why this priority**: Persistence protects the actual knowledge work.

**Independent Test**: Can be tested by writing a note, recreating the container (docker-agent stop/rm/run), and confirming the note is still there.

**Acceptance Scenarios**:

1. **Given** a note exists in the wiki vault, **When** the container is recreated, **Then** the note is still present and readable.

---

### Edge Cases

- What happens when the container restarts while Obsidian has unsaved changes? (Obsidian autosaves; vault metadata may need a short grace period before shutdown.)
- How does the system handle a missing `me/` base folder? (Entrypoint creates `me/raw` and `me/wiki` idempotently.)
- What happens when the VNC session disconnects? (The X server and Obsidian keep running; reconnecting shows the same session.)
- How does the system handle the arm64 architecture of the production VPS? (Dockerfile installs the arm64 Obsidian package; CI builds the `arch64` tag.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST run Obsidian inside a Docker container.
- **FR-002**: System MUST expose Obsidian over HTTP(S) via a web VNC client (noVNC) so it works in a browser.
- **FR-003**: System MUST create and persist a vault at `/data/me/raw` for raw documents (PDFs, videos, transcriptions, links, etc.).
- **FR-004**: System MUST create and persist a vault at `/data/me/wiki` for markdown generated from the raw documents.
- **FR-005**: System MUST register both vaults in Obsidian's vault list (obsidian.json) so they appear in the vault switcher.
- **FR-006**: System MUST support the arm64 architecture (production VPS) and build via the CI pipeline into `ghcr.io/legido-ai/obsidian:arch64`.
- **FR-007**: System MUST be deployable through docker-agent with Traefik routing (public URL) and a persistent volume for `/data`.
- **FR-008**: System MUST keep Obsidian and the VNC session alive across client disconnects.

### Key Entities *(include if feature involves data)*

- **Vault `me/raw`**: Directory `/data/me/raw` holding raw source documents; carries `.obsidian` vault metadata.
- **Vault `me/wiki`**: Directory `/data/me/wiki` holding generated markdown notes; carries `.obsidian` vault metadata; the exposed vault.
- **Obsidian workspace state**: `~/.config/obsidian/obsidian.json` mapping vault paths to IDs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The Obsidian UI loads at the public URL in under 30 seconds from container start.
- **SC-002**: Both `me/raw` and `me/wiki` exist with `.obsidian` metadata immediately after first start.
- **SC-003**: A note written in the wiki vault survives a container recreation (persistence volume).
- **SC-004**: The image builds and runs on arm64 (tag `arch64`), matching the production VPS.

## Assumptions

- The user will generate the wiki markdown from raw documents in a later step (from Hermes); this feature only provides the Obsidian container with the vault structure.
- A browser-based Obsidian session (noVNC) is an acceptable way to "expose" the wiki vault; a headless markdown export is out of scope for this iteration.
- Obsidian's Linux arm64 package (`.deb`) is available from the official GitHub releases.
- The deploy domain follows the existing convention (`<container_name>.test.legido.com` via docker-agent + Traefik).
- Data persistence is provided by a docker volume mounted at `/data`.
