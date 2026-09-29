---
name: repo-health
description: One-shot health report for the Hive custom component repo - workflow states and latest results, open bot/dependency PRs, stale-labelled items, pending release, branch protection and required secrets. Use when the user asks for status, "is everything OK", a maintenance check, or what needs attention.
---

# Repo health

This is read-only. Gather everything first, then report. Don't change settings, rerun workflows, or merge anything unless the user asks.

```bash
R=Pyhass/Hive-Custom-Component
gh workflow list --all -R $R                                  # any "disabled_inactivity"?
for w in ci.yml compat.yml pyhive_bump.yml stale.yml release.yml; do
  echo "== $w"; gh run list -R $R -w $w -L 3 --json conclusion,createdAt,headBranch,event -q '.[] | "\(.createdAt) \(.event) \(.headBranch) \(.conclusion)"'
done
gh pr list -R $R --state open --json number,title,author,labels,statusCheckRollup,createdAt
gh issue list -R $R --label no-issue-activity
gh pr list -R $R --label no-pr-activity
gh release list -R $R -L 5
git fetch -q origin && git log $(gh release list -R $R -L1 --exclude-pre-releases --json tagName -q '.[0].tagName')..origin/master --oneline
gh api repos/$R/branches/master/protection 2>&1 | jq '{checks: .required_status_checks.contexts, code_owners: .required_pull_request_reviews.require_code_owner_reviews}'
gh secret list -R $R                                          # expect BOT_TOKEN
```
(The protection and secrets calls need admin access. If they fail, say so rather than guessing.)

Compare what you find with MAINTAINING.md:
- **Workflows:** all active, with no `disabled_inactivity`. The latest CI run on master and the latest Compatibility run should both be green. The last Compatibility run should be under ~26 hours old.
- **Bot PRs:** Dependabot and pyhive bump PRs with no checks at all mean `BOT_TOKEN` is missing (for pyhive ones). PRs failing checks need attention. Anything older than about 2 weeks is going stale.
- **Unreleased commits on master:** suggest a release if there are user-facing changes.
- **Branch protection:** the required checks should be `HACS validation`, `Hassfest`, `Lint` and `Tests`, with code owner review on.
- **Secrets:** `BOT_TOKEN` should be present.
- **Pinned HA:** compare the HA version in the `requirements_test.txt` comment with the latest stable on PyPI (`curl -fsS https://pypi.org/pypi/homeassistant/json | jq -r .info.version`). A gap of more than one minor release means the Dependabot PR is stuck.

Report as a short table with ✅ / ⚠️ / ❌ and one line each. Then list the actions in priority order, each with the skill to use (`/triage-compat`, `/bump-pyhive`, `/release`) or the settings page to change.
