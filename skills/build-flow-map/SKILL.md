---
name: build-flow-map
description: Map how an application is built and connected - languages, frameworks, entry points, build/run/test/deploy commands, environment variables, databases and external services, API routes, and CI/CD - and write it to docs/BUILD_FLOW.md with a diagram so any developer can onboard fast. Use when asked to document the build flow, track the code workflow, explain what frameworks the project uses, or onboard a new developer. Use proactively after structural changes (new framework, service, environment variable, route group) and when docs/BUILD_FLOW.md is missing or stale.
---

# Build Flow Map

Produces and maintains one document, `docs/BUILD_FLOW.md`, that answers a new developer's first questions: *What is this made of? How do I run, test and ship it? What does it talk to? Where does a request go?*

**Runs on its own:** after structural changes Claude updates `docs/BUILD_FLOW.md`, and offers to create it when it is missing.

## Procedure

1. **Scan for facts** (fast, no guessing):
   ```bash
   python3 <skill-dir>/scripts/scan_stack.py <project-root> --format markdown > /tmp/stack-scan.md
   ```
   The script reads manifests, lockfile names, Dockerfiles, CI workflows, `.env.example`, and source files to list: languages, frameworks, scripts/commands, environment variables (names only, never values), databases and services, HTTP routes, and a rough internal module graph.
2. **Verify and fill gaps by reading the code.** The scan is heuristic. Open the entry points it found and confirm: how a request flows, where auth happens, what talks to the database, what runs in the background. Anything you cannot confirm goes under "Unverified" rather than being stated as fact.
3. **Write `docs/BUILD_FLOW.md`** using `references/build-flow-template.md`. Keep it to what a developer needs; link to files instead of pasting code.
4. **Draw the connections.** Include one Mermaid diagram of the runtime flow (browser/client, app, database, third parties, workers) and, for larger projects, one of the build/deploy pipeline. For prettier diagrams, hand the facts to a diagram skill if one is installed.
5. **Keep it current ("tracking").** Add a short "How to update this file" note at the bottom with the scan command. When you later add a framework, service, env var, route, or CI step, update the matching section in the same change. If the user wants it automatic, offer a CI step or pre-commit hook that runs the scan and fails when the file's "Last scanned" facts drift (see `references/keeping-it-current.md`).

## What good output looks like

- A newcomer can clone the repo and run it using only this file.
- Every command shown was found in a manifest, Makefile, or CI file (cite which).
- Environment variables are listed by **name**, with purpose and whether required. Never real values.
- Connections are explicit: "API route `POST /api/orders` -> `orders` service -> Postgres table `orders` -> Stripe webhook".
- Unknowns are labelled, not invented.

## Rules

- Read-only on source code. The only file you create or change is the document (and optional CI snippet if asked).
- Do not print secrets. If `.env` (not `.env.example`) contains real values, use names only.
- Do not claim a framework is used because it appears in a comment or a lockfile of a dependency; confirm it is a direct dependency or imported.
