# Contributing Guide

> Read this before writing a single line of code.

---

## Branch Rules

| Branch | Purpose | Who pushes |
|--------|---------|-----------|
| `main` | Protected. Production-ready only. | Lead only (via PR) |
| `develop` | Integration. All features merge here first. | Lead merges PRs |
| `feature/triage-orchestrator` | Lead | Lead |
| `feature/session-management` | Lead | Lead |
| `feature/policy-agent` | Member 2 | Member 2 |
| `feature/resolution-agent` | Member 3 | Member 3 |
| `feature/communication-escalation` | Member 4 | Member 4 |
| `feature/infra-observability` | Member 5 | Member 5 |

**Never push directly to `main` or `develop`.**

---

## Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <short description>

Types:
  feat:   a new feature or agent implementation
  fix:    a bug fix
  chore:  setup, config, dependency changes
  test:   adding or updating tests
  docs:   documentation only changes
  refactor: code change that neither fixes a bug nor adds a feature
```

Examples:
```
feat: implement policy_agent return eligibility check
fix: handle missing customer_id in get_customer_profile
test: add 10 unit tests for policy_agent
docs: update tool_interface_spec with error contract
chore: add refund_cap guardrail scaffold
```

---

## Pull Request Checklist

Before opening a PR, confirm all of these:

- [ ] My branch is up to date with `develop` (`git pull origin develop`)
- [ ] All tests pass locally (`pytest tests/ -v`)
- [ ] No secrets or API keys committed (check with `git diff --staged`)
- [ ] PR title references the GitHub Issue number (e.g. `feat: #12 implement policy_agent`)
- [ ] PR description explains: what changed, how to test it, known risks
- [ ] I have NOT changed any function signatures in `tools/` without Lead approval
- [ ] I have NOT changed the model name in my agent without Lead approval

---

## Getting Unblocked

If you are blocked for more than **4 hours**, message the Lead directly.  
Do not wait for the next standup. Delays on your branch block other members.

---

## Environment Setup

```bash
git clone <repo-url>
cd agent-nemo-customer-support
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Fill in your keys in .env — ask Lead if unsure which keys you need
```

---

## Running Tests

```bash
# All tests
pytest tests/ -v

# Your specific file only
pytest tests/test_policy_agent.py -v       # Member 2
pytest tests/test_tools.py -v              # Member 3
pytest tests/test_comm_escalation.py -v   # Member 4

# With coverage report
pytest tests/ --cov=. --cov-report=term-missing
```
