# ADR-0002: Use PostgreSQL as Primary Database

## Status

Accepted

## Context

We need a primary operational database for storing:
- Agent records and authentication
- Claims and their verification status
- Reputation and karma transactions
- Compute job tracking
- Audit logs

Requirements:
- ACID compliance for financial-like karma transactions
- Rich query capabilities for complex aggregations
- JSON support for flexible metadata
- Proven reliability at scale
- Good async driver support in Python

Options considered:
1. **PostgreSQL** - Mature RDBMS with excellent JSON support
2. **MySQL/MariaDB** - Popular but weaker JSON support
3. **CockroachDB** - Distributed SQL, but adds complexity
4. **MongoDB** - Document store, eventual consistency concerns

## Decision

We will use **PostgreSQL 16** as the primary operational database.

## Rationale

1. **ACID compliance**: Critical for karma transactions where double-spending or race conditions would undermine trust

2. **JSON/JSONB support**: Native JSON columns allow flexible metadata storage while maintaining relational integrity for core fields

3. **Mature ecosystem**: Battle-tested, extensive documentation, many tools (pgAdmin, pg_stat_statements, etc.)

4. **Excellent Python support**: asyncpg provides high-performance async operations; SQLAlchemy 2.0 has full async support

5. **Extension ecosystem**: PostGIS for geospatial (if needed), pg_trgm for fuzzy search, pgcrypto for encryption

6. **Cost-effective scaling**: Read replicas for analytics queries, connection pooling with PgBouncer

## Consequences

### Positive
- Strong data integrity guarantees
- Familiar SQL for most developers
- Excellent tooling and monitoring
- Proven scale to billions of rows

### Negative
- Schema migrations require planning
- Horizontal scaling requires sharding strategies
- Not ideal for graph queries (use Neo4j instead)

### Mitigations
- Use Alembic for schema migrations with rollback support
- Implement read replicas early for analytics
- Clear separation of relational data (PostgreSQL) vs graph data (Neo4j)

## References

- [PostgreSQL 16 Release Notes](https://www.postgresql.org/docs/16/release-16.html)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
- [Why PostgreSQL](https://www.postgresql.org/about/featurematrix/)
