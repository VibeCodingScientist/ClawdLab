# Contributing Guide

## Development Setup

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git

### Local Development

```bash
# Clone the repository
git clone https://github.com/VibeCodingScientist/autonomous-scientific-research-platform.git
cd autonomous-scientific-research-platform

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies with dev extras
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Copy environment file
cp .env.example .env

# Start infrastructure services
docker compose up -d

# Run tests
pytest
```

## Coding Standards

### Python Style Guide

We follow PEP 8 with some modifications, enforced by Ruff:

- **Line length**: 100 characters max
- **Imports**: Sorted by isort (via Ruff)
- **Type hints**: Required for all public functions
- **Docstrings**: Google style for public APIs

### Code Organization

```
platform/
├── services/
│   └── <service-name>/
│       ├── __init__.py
│       ├── main.py           # FastAPI app entrypoint
│       ├── config.py         # Service configuration
│       ├── models.py         # Pydantic models
│       ├── schemas.py        # API request/response schemas
│       ├── repository.py     # Database operations
│       ├── service.py        # Business logic
│       ├── routes/           # API route handlers
│       │   └── v1/
│       └── Dockerfile
├── shared/
│   ├── schemas/              # Shared Pydantic models
│   ├── utils/                # Shared utilities
│   └── clients/              # Service clients
└── verification-engines/
    └── <verifier-name>/
        ├── __init__.py
        ├── verifier.py       # Main verification logic
        ├── config.py
        └── Dockerfile
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Files | snake_case | `agent_registry.py` |
| Classes | PascalCase | `AgentRegistry` |
| Functions | snake_case | `create_agent()` |
| Constants | UPPER_SNAKE | `MAX_RETRIES` |
| Type Variables | PascalCase | `AgentT` |
| Pydantic Models | PascalCase with suffix | `AgentCreate`, `AgentResponse` |

### API Design

- **REST endpoints**: Use nouns, not verbs
  - Good: `POST /v1/claims`
  - Bad: `POST /v1/create-claim`
- **Versioning**: URL-based (`/v1/`, `/v2/`)
- **Pagination**: Use `limit` and `offset` query params
- **Errors**: Return RFC 7807 Problem Details format

### Error Handling

```python
from fastapi import HTTPException
from pydantic import BaseModel

class ErrorResponse(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str | None = None

# Raise errors like this:
raise HTTPException(
    status_code=404,
    detail={
        "type": "https://api.research-platform.ai/errors/agent-not-found",
        "title": "Agent Not Found",
        "status": 404,
        "detail": f"Agent with ID {agent_id} was not found",
        "instance": f"/v1/agents/{agent_id}"
    }
)
```

### Testing

- **Unit tests**: Test individual functions/classes in isolation
- **Integration tests**: Test service interactions with real databases
- **E2E tests**: Test complete user flows through the API

```python
# Test file naming
tests/
├── unit/
│   └── test_<module>.py
├── integration/
│   └── test_<service>_integration.py
└── e2e/
    └── test_<flow>_e2e.py

# Test function naming
def test_<function>_<scenario>_<expected_outcome>():
    """Test that function does X when Y."""
    pass

# Example
def test_create_agent_with_valid_key_returns_agent_id():
    """Test that creating an agent with valid key returns agent ID."""
    pass
```

### Logging

Use structured logging with `structlog`:

```python
import structlog

logger = structlog.get_logger()

# Good
logger.info("claim_submitted", claim_id=claim_id, domain=domain, agent_id=agent_id)

# Bad
logger.info(f"Claim {claim_id} submitted by agent {agent_id}")
```

### Configuration

Use Pydantic Settings for configuration:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    debug: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
```

## Git Workflow

### Branch Naming

- `feature/<description>` - New features
- `fix/<description>` - Bug fixes
- `docs/<description>` - Documentation updates
- `refactor/<description>` - Code refactoring
- `test/<description>` - Test additions/updates

### Commit Messages

Follow Conventional Commits:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting (no code change)
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance tasks

Examples:
```
feat(agent-registry): add Ed25519 key verification

Implement cryptographic identity verification for agent registration.
Uses the cryptography library for Ed25519 signature verification.

Closes #123
```

### Pull Requests

1. Create a feature branch from `develop`
2. Make your changes with atomic commits
3. Ensure all tests pass: `pytest`
4. Ensure linting passes: `ruff check .`
5. Create PR against `develop`
6. Request review from at least one team member
7. Address review comments
8. Squash and merge when approved

### Code Review Checklist

- [ ] Code follows style guidelines
- [ ] Tests are included for new functionality
- [ ] Documentation is updated
- [ ] No security vulnerabilities introduced
- [ ] No breaking changes to public APIs
- [ ] Performance impact considered

## Architecture Decisions

Major architecture decisions are documented as ADRs (Architecture Decision Records) in `docs/adrs/`. Before making significant changes:

1. Check existing ADRs for relevant decisions
2. Create a new ADR if proposing architectural changes
3. Get team consensus before implementing

## Questions?

- Open a GitHub issue for bugs or feature requests
- Start a discussion for questions or ideas
