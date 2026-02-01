"""Neo4j client for knowledge graph operations."""

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from neo4j.exceptions import ServiceUnavailable

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)

# Global driver instance
_driver: AsyncDriver | None = None


def get_neo4j_config() -> dict[str, str]:
    """Get Neo4j configuration from environment."""
    return {
        "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        "user": os.getenv("NEO4J_USER", "neo4j"),
        "password": os.getenv("NEO4J_PASSWORD", "neo4j_dev_password"),
    }


async def get_driver() -> AsyncDriver:
    """Get or create Neo4j async driver."""
    global _driver
    if _driver is None:
        config = get_neo4j_config()
        _driver = AsyncGraphDatabase.driver(
            config["uri"],
            auth=(config["user"], config["password"]),
            max_connection_pool_size=50,
            connection_acquisition_timeout=30,
        )
        logger.info("neo4j_driver_created", uri=config["uri"])
    return _driver


async def close_driver() -> None:
    """Close Neo4j driver."""
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None
        logger.info("neo4j_driver_closed")


@asynccontextmanager
async def get_session(database: str = "neo4j") -> AsyncGenerator[AsyncSession, None]:
    """Get Neo4j session context manager."""
    driver = await get_driver()
    session = driver.session(database=database)
    try:
        yield session
    finally:
        await session.close()


class Neo4jClient:
    """High-level Neo4j client for knowledge graph operations."""

    def __init__(self, database: str = "neo4j"):
        self.database = database

    async def execute_read(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a read query and return results."""
        async with get_session(self.database) as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    async def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a write query and return results."""
        async with get_session(self.database) as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    async def execute_single(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Execute query and return single result."""
        results = await self.execute_read(query, parameters)
        return results[0] if results else None

    # ===========================================
    # NODE OPERATIONS
    # ===========================================

    async def create_node(
        self,
        labels: list[str],
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a node with given labels and properties."""
        labels_str = ":".join(labels)
        query = f"""
        CREATE (n:{labels_str} $props)
        RETURN n, id(n) as node_id
        """
        result = await self.execute_single(query, {"props": properties})
        return result

    async def get_node_by_id(
        self,
        node_id: str,
        id_property: str = "id",
    ) -> dict[str, Any] | None:
        """Get node by ID property."""
        query = f"""
        MATCH (n {{{id_property}: $id}})
        RETURN n, labels(n) as labels
        """
        return await self.execute_single(query, {"id": node_id})

    async def update_node(
        self,
        node_id: str,
        properties: dict[str, Any],
        id_property: str = "id",
    ) -> dict[str, Any] | None:
        """Update node properties."""
        query = f"""
        MATCH (n {{{id_property}: $id}})
        SET n += $props
        RETURN n
        """
        return await self.execute_single(query, {"id": node_id, "props": properties})

    async def delete_node(
        self,
        node_id: str,
        id_property: str = "id",
        detach: bool = True,
    ) -> bool:
        """Delete node by ID."""
        detach_str = "DETACH " if detach else ""
        query = f"""
        MATCH (n {{{id_property}: $id}})
        {detach_str}DELETE n
        RETURN count(n) as deleted
        """
        result = await self.execute_single(query, {"id": node_id})
        return result and result.get("deleted", 0) > 0

    # ===========================================
    # RELATIONSHIP OPERATIONS
    # ===========================================

    async def create_relationship(
        self,
        from_id: str,
        to_id: str,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
        id_property: str = "id",
    ) -> dict[str, Any] | None:
        """Create a relationship between two nodes."""
        props_clause = "SET r = $props" if properties else ""
        query = f"""
        MATCH (a {{{id_property}: $from_id}})
        MATCH (b {{{id_property}: $to_id}})
        CREATE (a)-[r:{relationship_type}]->(b)
        {props_clause}
        RETURN r, type(r) as type
        """
        params = {"from_id": from_id, "to_id": to_id}
        if properties:
            params["props"] = properties
        return await self.execute_single(query, params)

    async def get_neighbors(
        self,
        node_id: str,
        relationship_types: list[str] | None = None,
        direction: str = "both",
        depth: int = 1,
        id_property: str = "id",
    ) -> list[dict[str, Any]]:
        """Get neighboring nodes."""
        rel_filter = ""
        if relationship_types:
            rel_filter = ":" + "|".join(relationship_types)

        if direction == "outgoing":
            pattern = f"-[r{rel_filter}*1..{depth}]->"
        elif direction == "incoming":
            pattern = f"<-[r{rel_filter}*1..{depth}]-"
        else:
            pattern = f"-[r{rel_filter}*1..{depth}]-"

        query = f"""
        MATCH (n {{{id_property}: $id}}){pattern}(neighbor)
        RETURN DISTINCT neighbor, labels(neighbor) as labels
        """
        return await self.execute_read(query, {"id": node_id})

    # ===========================================
    # PATH FINDING
    # ===========================================

    async def find_shortest_path(
        self,
        from_id: str,
        to_id: str,
        relationship_types: list[str] | None = None,
        max_hops: int = 5,
        id_property: str = "id",
    ) -> dict[str, Any] | None:
        """Find shortest path between two nodes."""
        rel_filter = ""
        if relationship_types:
            rel_filter = ":" + "|".join(relationship_types)

        query = f"""
        MATCH path = shortestPath(
            (a {{{id_property}: $from_id}})-[{rel_filter}*..{max_hops}]-(b {{{id_property}: $to_id}})
        )
        RETURN path, length(path) as length,
               [n in nodes(path) | n] as nodes,
               [r in relationships(path) | type(r)] as relationships
        """
        return await self.execute_single(query, {"from_id": from_id, "to_id": to_id})

    # ===========================================
    # FULL-TEXT SEARCH
    # ===========================================

    async def fulltext_search(
        self,
        index_name: str,
        search_term: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Perform full-text search on an index."""
        query = """
        CALL db.index.fulltext.queryNodes($index, $term)
        YIELD node, score
        RETURN node, score, labels(node) as labels
        ORDER BY score DESC
        LIMIT $limit
        """
        return await self.execute_read(
            query,
            {"index": index_name, "term": search_term, "limit": limit},
        )

    # ===========================================
    # GRAPH ALGORITHMS
    # ===========================================

    async def get_pagerank(
        self,
        label: str,
        relationship_type: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Calculate PageRank for nodes (requires GDS library)."""
        query = f"""
        CALL gds.pageRank.stream({{
            nodeProjection: '{label}',
            relationshipProjection: '{relationship_type}'
        }})
        YIELD nodeId, score
        RETURN gds.util.asNode(nodeId) as node, score
        ORDER BY score DESC
        LIMIT $limit
        """
        return await self.execute_read(query, {"limit": limit})


async def health_check() -> bool:
    """Check Neo4j connectivity."""
    try:
        driver = await get_driver()
        await driver.verify_connectivity()
        return True
    except ServiceUnavailable as e:
        logger.error("neo4j_health_check_failed", error=str(e))
        return False
