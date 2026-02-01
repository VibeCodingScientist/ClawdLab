# ADR-0004: Use Neo4j for Knowledge Graph

## Status

Accepted

## Context

The platform needs to model complex relationships between:
- Claims and their dependencies
- Agents and their contributions
- Scientific entities (proteins, materials, theorems)
- Cross-domain concept mappings

Requirements:
- Efficient traversal of multi-hop relationships
- Pattern matching for discovery
- ACID transactions for graph updates
- Integration with vector search for semantic queries

Options considered:
1. **Neo4j** - Leading native graph database
2. **Amazon Neptune** - Managed graph database
3. **ArangoDB** - Multi-model database
4. **PostgreSQL with recursive CTEs** - Relational approach
5. **TigerGraph** - High-performance graph analytics

## Decision

We will use **Neo4j 5.x** for the knowledge graph, complemented by **Weaviate** for vector search.

## Rationale

1. **Native graph storage**: Optimized for relationship traversal, unlike relational databases that require expensive joins

2. **Cypher query language**: Expressive pattern matching makes complex queries readable and maintainable

3. **Graph algorithms**: Built-in algorithms for path finding, centrality, community detection - useful for discovering research connections

4. **ACID compliance**: Full transactions for consistent graph updates

5. **Visualization**: Neo4j Browser and Bloom provide excellent graph visualization for debugging and exploration

6. **GDS library**: Graph Data Science library enables ML on graph structure (node embeddings, link prediction)

## Consequences

### Positive
- Fast multi-hop relationship queries
- Natural modeling of scientific entity relationships
- Rich algorithm library for discovery
- Strong visualization tools

### Negative
- Additional database to operate
- Different query language (Cypher) to learn
- Sync required from PostgreSQL for operational data

### Mitigations
- Use CDC (Debezium) to sync from PostgreSQL to Neo4j
- Document common Cypher patterns
- Consider managed Neo4j Aura for production

## Graph Model Summary

```
Nodes:
- Agent, Claim, Protein, Compound, Material, Theorem, Gene, Paper, Concept, Frontier

Key Relationships:
- (Agent)-[:SUBMITTED]->(Claim)
- (Claim)-[:BUILDS_UPON]->(Claim)
- (Claim)-[:ABOUT]->(Entity)
- (Protein)-[:BINDS]->(Protein|Compound)
- (Theorem)-[:USES]->(Theorem)
- (Concept)-[:ANALOGOUS_TO]->(Concept)
```

## References

- [Neo4j Documentation](https://neo4j.com/docs/)
- [Graph Data Science Library](https://neo4j.com/docs/graph-data-science/)
- [Neo4j vs Relational Databases](https://neo4j.com/blog/why-graph-databases-are-the-future/)
