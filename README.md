# AI Agent System for Return Processing

This project implements a multi-agent system using the OpenAI Agents SDK to handle customer return requests, resolution, and communication.

## System Overview

The system consists of several specialized agents:
- **Triage Orchestrator**: Classifies incoming messages and routes to appropriate agents
- **Policy Agent**: Validates return eligibility against business rules
- **Resolution Agent**: Executes approved resolutions (refund, replacement, return label)
- **Communication Agent**: Sends customer-facing notifications
- **Escalation Agent**: Handles high-risk or complex cases requiring human intervention
- **Guardrails**: Ensure safety, compliance, and quality (PII scrubbing, sentiment monitoring, refund limits, brand voice)

## Directory Structure

- `/agents`: Contains all agent implementations
- `/tools`: External service integrations (CRM, payment, shipping)
- `/guardrails`: Safety and compliance checks
- `/tests`: Unit and integration tests
- `/infrastructure`: Deployment configurations (Docker, Kubernetes)
- `/docs`: Documentation

## Getting Started

1. Install dependencies: `pip install -r requirements.txt`
2. Configure environment variables (see `.env.example`)
3. Run the system: `python -m agents.triage_orchestrator`

## License

Proprietary - Team Internal
