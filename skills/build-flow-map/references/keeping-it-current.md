# Keeping BUILD_FLOW.md current

## Cheap and effective: review prompt
Add to the pull request template: "Did this change add or remove a framework, service, env var, route, or deploy step? If yes, update docs/BUILD_FLOW.md."

## Drift check in CI
`scan_stack.py --format json` is stable and diffable. Save a baseline once, then fail CI when new env vars or services appear that the document does not mention.

```yaml
# .github/workflows/build-flow-drift.yml
name: build-flow-drift
on: [pull_request]
jobs:
  drift:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Scan
        run: python3 .claude/skills/build-flow-map/scripts/scan_stack.py . --format json > /tmp/scan.json
      - name: Every env var and service must be mentioned in docs/BUILD_FLOW.md
        run: |
          python3 - <<'EOF'
          import json, sys
          scan = json.load(open('/tmp/scan.json'))
          doc = open('docs/BUILD_FLOW.md').read()
          names = [e['name'] for e in scan['env_vars']] + [s for s in scan['services']]
          missing = [n for n in names if n not in doc]
          if missing:
              print('Not documented in docs/BUILD_FLOW.md:', ', '.join(sorted(set(missing))))
              sys.exit(1)
          EOF
```

Adjust the path to wherever the skill is vendored in your repo.

## Pre-commit (local)
Run the same check in a `pre-commit` hook so drift is caught before the pull request.
