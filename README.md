# onchain-scout

AI-powered crypto risk intelligence for evaluating social profiles, token signals, and scam patterns across on-chain and off-chain data.

## Overview

`onchain-scout` is a FastAPI backend for crypto threat analysis. It combines Twitter/X profile evaluation, deep research, tweet-level scam classification, token risk assessment, IP conflict checks, wallet/payment flows, and generated API SDKs.

## Core Features

- Profile evaluation for cryptocurrency scam signals
- Advanced and basic evaluation modes
- Deep research for contextual project and profile intelligence
- Tweet and retweet analysis with scam type classification
- Batch-based summary generation for large profiles
- Optional IP conflict analysis against project details
- Token risk assessment using DexScreener market data
- Persistent analysis history with PostgreSQL and Alembic
- Generated JavaScript and Python API clients

## Evaluation Modes

- `advanced`: Runs deep research and tool-enabled tweet analysis.
- `basic`: Runs lightweight tweet analysis without deep research.

Example request:

```json
{
  "x_profile": "twitter_username",
  "evaluation_type": "advanced",
  "project_name": "Optional Project Name",
  "project_description": "Optional Project Description",
  "token_risk": true
}
```

## Project Structure

```text
.
├── main.py                         # FastAPI application entrypoint
├── routes/                         # API routers
├── db/                             # SQLAlchemy models and CRUD helpers
├── source/agents/                  # AI agents and token risk engine
├── source/services/                # Evaluation, Twitter, payment, and data services
├── source/utils/                   # Auth, formatting, task, and result utilities
├── alembic/                        # Database migrations
├── twitter_service/                # Async Twitter data service
├── theagentic_rugpool_js_sdk/      # Generated JavaScript client
└── theagentic_rugpool_python_sdk/  # Generated Python client
```

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

API health check:

```bash
curl http://127.0.0.1:8000/health
```

## Notes

This repository is being prepared for a clean public GitHub history. Local secrets, generated caches, database dumps, and runtime outputs should stay out of future commits.
