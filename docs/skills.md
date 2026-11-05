# Skill playbook

One section per skill: when to reach for it, what to say, what you get, and what it will not do. The [README](../README.md) has the overview; each skill's own `SKILL.md` is the full instruction set Claude follows.

Every skill can also run on its own: see "Runs on its own" in each `SKILL.md` and [autopilot](autopilot.md).

---

## app-readiness-audit

**Reach for it:** before a launch, after a big feature, when inheriting a project, or when someone asks "is this safe to put online?".

**Say:** *Run a readiness audit on this project.* / *What are we missing before launch?* / *Audit only secrets and database.*

**You get:** A written report: a score per area (13 areas), the evidence (file and line), why it matters in one sentence, and a prioritized fix list (critical, high, medium). Claude can then fix the items you choose.

**It will not:** attack a live system, guarantee safety, or treat "pattern not found" as "missing".

**Pairs with:** `monitor-alerts-builder` (monitoring gap), `api-security-guard` (unsafe API), `zero-trust-review` (loose access).

## monitor-alerts-builder

**Reach for it:** the app has no uptime check, nobody would know if it went down, or the audit flagged monitoring.

**Say:** *Set up monitoring and alerts for this app. We use Slack.* / *Add a health endpoint and an uptime check.* / *Write a runbook for the database alert.*

**You get:** a health endpoint recommendation fitted to your stack, `healthcheck.py` (URL, disk, TLS certificate expiry, backup freshness) with webhook delivery and repeat suppression, Prometheus alert rules if you use Prometheus, a runbook per alert, and a short list of what to monitor first.

**It will not:** sign you up for a monitoring service or install agents; it reuses what you already have.

## api-security-guard

**Reach for it:** building or changing an API, auth, tokens, API keys; before exposing an API publicly; when someone mentions IDOR or BOLA.

**Say:** *List every endpoint and show which ones have no auth.* / *Check this API against the 12 rules.* / *Can user A read user B's order?*

**You get:** the endpoint inventory (method, path, auth seen, version, object ID, public or not), findings per rule with fixes, a drift report against your OpenAPI file, and alert rules for auth failures, 403 spikes and abuse.

**It will not:** send requests to your API. "None seen" for authentication means no auth pattern near the route; custom wrappers need a human look.

## zero-trust-review

**Reach for it:** cloud, Kubernetes, CI/CD, service accounts, secrets handling, remote access, or AI agents that act with credentials.

**Say:** *Do a Zero Trust review of this repo.* / *Review our Terraform and GitHub Actions against Zero Trust.* / *How should we give this AI agent access safely?*

**You get:** a result per principle (evidence, risks, questions for the owner), a prioritized 30/60/90-day plan, AWS alert patterns, and guidance for agent identity and just-in-time access.

**It will not:** change your cloud. Where the repo cannot show evidence it says "ask the owner", not "fail".

## skeletonizer

**Reach for it:** a page flashes blank, shows a spinner for content, or jumps when data arrives.

**Say:** *Add skeleton loading to the dashboard.* / *Find every spinner that should be a skeleton.* / *Make the product list skeleton match the real cards.*

**You get:** skeleton components or overlay styles sized to the real layout, wired to the loading state your code already has (`isLoading`, `loading.tsx`, Suspense, `FutureBuilder`, `redacted`), shared CSS (shimmer, dark mode, reduced motion), a delay against flashes, and a note on how to preview the loading state.

**It will not:** add data fetching, or hide errors: failed and empty states keep their own UI.

## motionsite

**Reach for it:** a landing page, hero section or product page that should feel cinematic: video background, glass cards, animated headline.

**Say:** *Build an animated landing page for a meditation app with a video background.* / *Add a video hero to this page.* / *Make this page feel more alive, but keep it fast.*

**You get:** the page (single HTML file, or components in your stack), placeholder animated background until you have footage, `assets/README.md` for licences, the ffmpeg command to prepare your video, and an audit with every fail fixed.

**It will not:** include someone else's footage or prompts, or hotlink third-party video.

## build-flow-map

**Reach for it:** onboarding, handoff, "how does this project even run?", before a refactor, or when docs are stale.

**Say:** *Document the build flow of this project.* / *Which env vars does this app need?* / *Update BUILD_FLOW.md after my changes.*

**You get:** `docs/BUILD_FLOW.md` with stack, commands, entry points, env var names (never values), services, routes, CI/CD, a diagram, and an "Unverified" section for what the scan could not confirm.

## session-journal

**Reach for it:** end of a work session, handing over to a teammate, or when you want to find out why something was decided.

**Say:** *Save this session to the journal.* / *Where did we leave off?* / *Turn on automatic transcript saving.*

**You get:** `.claude/journal/` entries with goals, decisions and why, files changed, and open items, plus the full masked transcript when autopilot is on.

**It will not:** catch every secret in a transcript. Keep the folder private.
