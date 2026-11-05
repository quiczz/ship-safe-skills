# Zero Trust for AI agents and automation (principles 11 and 12)

An AI coding agent or autonomous workflow is a non-human identity that follows instructions found in text it reads. Treat it like a new contractor with a laptop: useful, fast, and able to be tricked.

| Control | What to do |
|---------|-----------|
| Own identity | Give each agent or workflow its own account or token. Never reuse a person's login or a shared admin key. The audit log must show which agent did what. |
| Least privilege | Read-only by default. Grant write access per task and per repository or resource. Prefer deny-by-default tool lists and file/folder scopes. |
| Short-lived credentials | Issue tokens that expire in minutes or hours (OIDC federation, vault leases). No long-lived keys in agent environments or prompts. |
| Just-in-time approval | Require a human approval step for destructive or irreversible actions (delete, deploy to production, send money or mail, change permissions). |
| Isolation (assume breach) | Run agents in a sandbox or disposable container with no access to production secrets, no broad network egress, and a throwaway workspace. A prompt injection should have a small blast radius. |
| Network and egress | Allow-list the domains an agent can reach. Block cloud metadata endpoints from agent workloads. |
| Untrusted input | Treat web pages, issues, emails, documents and tool outputs as data, not instructions. Do not let an agent forward secrets or run commands because retrieved text said so. |
| Secrets hygiene | Keep secrets out of prompts, transcripts and logs. Mask them in saved transcripts; rotate any that appeared in one. |
| Logging | Log every tool call with agent identity, arguments (secrets masked), result status and time, to a store the agent cannot edit. |
| Monitoring | Alert on an agent acting outside its pattern: new resource types, unusual hours, bulk reads, permission changes, repeated denied actions, new outbound domains. |
| Kill switch | Be able to revoke one agent's credentials in one step, and a runbook that says how. |

Quick check for any agent deployment: *Which identity does it use? What can that identity do if the agent is tricked? How would I notice, and how fast can I turn it off?*
