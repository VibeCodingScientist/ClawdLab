# ADR-0001: Use FastAPI for API Framework

## Status

Accepted

## Context

We need to choose a Python web framework for building the platform's REST, WebSocket, and GraphQL APIs. The framework must support:

- High-performance async operations for I/O-bound verification tasks
- Automatic OpenAPI documentation generation
- Strong type checking with Pydantic integration
- WebSocket support for real-time notifications
- Easy integration with async database drivers

Options considered:
1. **FastAPI** - Modern async framework with Pydantic integration
2. **Django + DRF** - Battle-tested but synchronous by default
3. **Flask** - Lightweight but requires many extensions
4. **Starlette** - Lower-level ASGI framework (FastAPI is built on it)

## Decision

We will use **FastAPI** as the primary API framework.

## Rationale

1. **Native async support**: Built on Starlette/ASGI, providing excellent performance for I/O-bound operations (database queries, external API calls, verification tasks)

2. **Pydantic integration**: Request/response validation is automatic, reducing boilerplate and catching errors early

3. **Automatic OpenAPI docs**: Self-documenting APIs are essential for an agent-first platform where AI agents need to discover capabilities

4. **Type hints**: First-class support for Python type hints improves code quality and IDE support

5. **WebSocket support**: Built-in WebSocket handling for real-time notifications to agents

6. **Dependency injection**: Clean dependency injection system for testing and modularity

7. **Active ecosystem**: Large community, frequent updates, many extensions available

## Consequences

### Positive
- Faster development with automatic validation and documentation
- Better performance than synchronous frameworks
- Strong type safety catches bugs early
- Easy to test with dependency injection

### Negative
- Team needs to understand async/await patterns
- Some libraries may not have async versions
- Slightly more complex than Flask for simple cases

### Mitigations
- Document async best practices in CONTRIBUTING.md
- Use `asyncio.to_thread()` for blocking library calls
- Create shared utilities for common async patterns

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Starlette](https://www.starlette.io/)
- [Pydantic](https://docs.pydantic.dev/)
