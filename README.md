# PIEA — Public Information Exposure Analyzer

A consent-based security assessment tool that aggregates publicly available information about an individual from legitimate data sources, builds a recursive identity graph across platforms, and produces a risk-scored exposure report with actionable remediation recommendations.

## Purpose

- **Self-assessment** — Individuals analyzing their own public information exposure
- **Authorized penetration testing** — Security professionals with documented authorization
- **Security awareness training** — Educational demonstrations of exposure risks

## Features

- Username enumeration across 300+ public platforms
- Recursive cross-platform identity linking (GitHub, Mastodon, Keybase, GitLab, Gravatar, Reddit)
- Email breach exposure analysis via Have I Been Pwned API v3
- Domain intelligence (WHOIS, DNS, email security posture)
- Public search footprint analysis via Google Custom Search API
- Weighted risk scoring with configurable weights
- Interactive web-based report with identity graph visualization
- Mandatory consent gate before any scan
- Full audit logging

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16+ |
| Cache / Queue | Redis 7+, Celery 5.3+ |
| Frontend | React 18+, TypeScript, D3.js, Recharts, Tailwind CSS |
| Infrastructure | Docker, Docker Compose |

## Quick Start

### Prerequisites

- Docker 24+ and Docker Compose v2+
- Python 3.11+ (for local development)

### Run with Docker

```bash
# Clone the repository
git clone https://github.com/AreYouPublic/piea.git
cd piea

# Copy environment template
cp .env.example .env

# Start all services
docker compose up -d

# Run database migrations
docker compose exec fastapi alembic upgrade head

# Verify — health endpoint should respond
curl http://localhost:8000/health
```

### Local Development

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting & type checking
ruff check src/ tests/
mypy src/
```

## Project Structure

```
src/piea/
├── main.py              # FastAPI application entry point
├── config.py            # Settings from environment
├── api/                 # REST API layer (routes, schemas)
├── core/                # Business logic (consent gate, orchestrator)
├── db/                  # Database models and session management
├── modules/             # Data source integrations (HIBP, etc.)
├── scoring/             # Risk scoring engine
├── graph/               # Identity graph models
└── tasks/               # Celery background tasks
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/scans` | Create a new scan (requires consent) |
| `GET` | `/scans/{id}` | Get scan status |
| `GET` | `/reports/{scan_id}` | Get scan report |

## Code Quality

- **Type checking**: mypy strict mode
- **Linting**: ruff (E, W, F, I, B, C4, UP rules)
- **Testing**: pytest with 80% minimum coverage
- **CI**: GitHub Actions runs lint + type check + tests on every PR

## Ethics & Legal

This tool operates under strict ethical guidelines:

- **Consent required** — Every scan requires documented consent before execution
- **Public data only** — No scraping of private or authentication-protected content
- **Platform TOS compliant** — No bypassing of anti-bot protections
- **GDPR/PDPD aligned** — Proper data handling and retention policies

See [LEGAL.md](LEGAL.md) for full terms of use and acceptable use policy.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes with tests
4. Ensure CI passes (`ruff check`, `mypy`, `pytest`)
5. Open a Pull Request

## License

MIT License — see [LICENSE](LICENSE) for details.
