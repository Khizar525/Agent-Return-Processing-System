---
id: 0002
title: Localhost link not working
stage: debugging
date: 2026-06-03
surface: codex
model: GPT-5
feature: 002-policy-agent
branch: feature/policy-agent
user: developer
command: "why its local host link is'nt working"
labels: [debugging, localhost, fastapi]
links:
  spec: specs/002-policy-agent/spec.md
  ticket: null
  adr: docs/ADR-001.md
  pr: null
files:
  - main.py
  - server_err.log
  - server_out.log
tests:
  - Invoke-WebRequest http://127.0.0.1:8000/health
---

## Prompt

this project is ok but why its local host link is'nt working

## Response snapshot

Investigated the FastAPI startup path, previous server logs, and current port state. Found that no process was listening on port 8000 during the check.

## Outcome

- Impact: Identified likely cause as dev server not currently running.
- Tests: Local health request failed because the server was unavailable.
- Files: Added this prompt history record.
- Next prompts: Start the server and confirm the correct URL.
- Reflection: Existing logs showed a prior successful run, so current failure is runtime state rather than an obvious code failure.

## Evaluation notes (flywheel)

- Failure modes observed: Server process not running on port 8000.
- Graders run and results (PASS/FAIL): Manual localhost health check failed before server start.
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): Start uvicorn and retry /health.
