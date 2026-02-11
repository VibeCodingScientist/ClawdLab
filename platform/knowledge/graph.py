"""Knowledge graph service for relationship management and graph queries."""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from platform.knowledge.base import (
    EntryType,
    GraphEdge,
    GraphNode,
    GraphQueryResult,
    KnowledgeEntry,
    Relationship,
    RelationshipType,
)
from platform.knowledge.config import RELATIONSHIP_TYPES, get_settings
from platform.knowledge.repository import get_knowledge_repository
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class PathResult:
    """Result of a path finding query."""

    source_id: str
    target_id: str
    paths: list[list[str]]
    shortest_path_length: int
    relationship_types: list[str]


@dataclass
class ClusterResult:
    """Result of clustering analysis."""

    cluster_id: str
    entries: list[str]
    central_entry: str
    density: float
    dominant_type: EntryType | None = None


@dataclass
class GraphMetrics:
    """Metrics about the knowledge graph."""

    total_nodes: int
    total_edges: int
    avg_degree: float
    density: float
    connected_components: int
    largest_component_size: int
    node_types: dict[str, int]
    edge_types: dict[str, int]


class KnowledgeGraphService:
    """
    Service for knowledge graph operations.

    Provides graph-based queries, path finding, and relationship analysis
    for the knowledge base.
    """

    def __init__(self):
        """Initialize knowledge graph service."""
        self._repository = get_knowledge_repository()

    async def create_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: RelationshipType,
        strength: float = 1.0,
        evidence: str = "",
        bidirectional: bool = False,
        created_by: str = "",
    ) -> Relationship:
        """
        Create a relationship between entries.

        Args:
            source_id: Source entry ID
            target_id: Target entry ID
            relationship_type: Type of relationship
            strength: Relationship strength (0-1)
            evidence: Supporting evidence
            bidirectional: Create inverse relationship too
            created_by: Creator ID

        Returns:
            Created relationship
        """
        # Verify entries exist
        source = await self._repository.get_entry(source_id)
        target = await self._repository.get_entry(target_id)

        if not source:
            raise ValueError(f"Source entry not found: {source_id}")
        if not target:
            raise ValueError(f"Target entry not found: {target_id}")

        # Create relationship
        relationship = await self._repository.create_relationship(
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
            strength=strength,
            evidence=evidence,
            created_by=created_by,
        )

        # Create inverse if bidirectional
        if bidirectional:
            inverse_type = self._get_inverse_relationship(relationship_type)
            if inverse_type:
                await self._repository.create_relationship(
                    source_id=target_id,
                    target_id=source_id,
                    relationship_type=inverse_type,
                    strength=strength,
                    evidence=evidence,
                    created_by=created_by,
                )

        logger.info(
            "relationship_created",
            source=source_id,
            target=target_id,
            type=relationship_type.value,
        )

        return relationship

    async def get_neighbors(
        self,
        entry_id: str,
        relationship_types: list[RelationshipType] | None = None,
        direction: str = "both",  # "outgoing", "incoming", "both"
        max_depth: int = 1,
    ) -> GraphQueryResult:
        """
        Get neighboring entries in the graph.

        Args:
            entry_id: Entry ID
            relationship_types: Filter by relationship types
            direction: Direction of relationships
            max_depth: Maximum depth to traverse

        Returns:
            Graph query result with nodes and edges
        """
        visited_nodes: set[str] = set()
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        queue: list[tuple[str, int]] = [(entry_id, 0)]

        while queue:
            current_id, depth = queue.pop(0)

            if current_id in visited_nodes or depth > max_depth:
                continue

            visited_nodes.add(current_id)

            # Get entry
            entry = await self._repository.get_entry(current_id)
            if not entry:
                continue

            # Add node
            nodes.append(self._entry_to_node(entry))

            # Get relationships based on direction
            if direction in ("outgoing", "both"):
                outgoing = await self._get_relationships_filtered(
                    current_id, relationship_types, as_source=True
                )
                for rel in outgoing:
                    edges.append(self._relationship_to_edge(rel))
                    if rel.target_id not in visited_nodes and depth < max_depth:
                        queue.append((rel.target_id, depth + 1))

            if direction in ("incoming", "both"):
                incoming = await self._get_relationships_filtered(
                    current_id, relationship_types, as_source=False
                )
                for rel in incoming:
                    edges.append(self._relationship_to_edge(rel))
                    if rel.source_id not in visited_nodes and depth < max_depth:
                        queue.append((rel.source_id, depth + 1))

        return GraphQueryResult(nodes=nodes, edges=edges)

    async def find_paths(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
        relationship_types: list[RelationshipType] | None = None,
    ) -> PathResult:
        """
        Find paths between two entries.

        Args:
            source_id: Source entry ID
            target_id: Target entry ID
            max_depth: Maximum path length
            relationship_types: Filter by relationship types

        Returns:
            Path finding result
        """
        paths: list[list[str]] = []
        relationship_types_found: set[str] = set()

        # BFS to find all paths up to max_depth
        queue: list[tuple[str, list[str]]] = [(source_id, [source_id])]
        visited_in_path: set[str] = set()

        while queue:
            current_id, path = queue.pop(0)

            if current_id == target_id:
                paths.append(path)
                continue

            if len(path) > max_depth:
                continue

            # Get outgoing relationships
            relationships = await self._get_relationships_filtered(
                current_id, relationship_types, as_source=True
            )

            for rel in relationships:
                if rel.target_id not in path:  # Avoid cycles in this path
                    new_path = path + [rel.target_id]
                    queue.append((rel.target_id, new_path))
                    relationship_types_found.add(rel.relationship_type.value)

        shortest = min(len(p) for p in paths) - 1 if paths else -1

        return PathResult(
            source_id=source_id,
            target_id=target_id,
            paths=paths,
            shortest_path_length=shortest,
            relationship_types=list(relationship_types_found),
        )

    async def get_subgraph(
        self,
        entry_ids: list[str],
        include_relationships: bool = True,
    ) -> GraphQueryResult:
        """
        Get subgraph containing specified entries.

        Args:
            entry_ids: Entry IDs to include
            include_relationships: Include relationships between entries

        Returns:
            Graph with specified nodes and their relationships
        """
        nodes = []
        edges = []
        entry_set = set(entry_ids)

        for entry_id in entry_ids:
            entry = await self._repository.get_entry(entry_id)
            if entry:
                nodes.append(self._entry_to_node(entry))

        if include_relationships:
            # Find relationships between these entries
            for entry_id in entry_ids:
                relationships = await self._repository.get_relationships(
                    entry_id, as_source=True
                )
                for rel in relationships:
                    if rel.target_id in entry_set:
                        edges.append(self._relationship_to_edge(rel))

        return GraphQueryResult(nodes=nodes, edges=edges)

    async def find_related(
        self,
        entry_id: str,
        relationship_type: RelationshipType | None = None,
        min_strength: float = 0.0,
        limit: int = 20,
    ) -> list[tuple[KnowledgeEntry, float]]:
        """
        Find entries related to the given entry.

        Args:
            entry_id: Entry ID
            relationship_type: Filter by relationship type
            min_strength: Minimum relationship strength
            limit: Maximum results

        Returns:
            List of (entry, strength) tuples
        """
        results = []

        # Get relationships
        relationships = await self._repository.get_relationships(
            entry_id=entry_id,
            relationship_type=relationship_type,
            as_source=True,
        )

        for rel in relationships:
            if rel.strength >= min_strength:
                entry = await self._repository.get_entry(rel.target_id)
                if entry:
                    results.append((entry, rel.strength))

        # Also check incoming relationships
        incoming = await self._repository.get_relationships(
            entry_id=entry_id,
            relationship_type=relationship_type,
            as_source=False,
        )

        for rel in incoming:
            if rel.strength >= min_strength:
                entry = await self._repository.get_entry(rel.source_id)
                if entry and not any(e.entry_id == entry.entry_id for e, _ in results):
                    results.append((entry, rel.strength))

        # Sort by strength and limit
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    async def get_supporting_entries(
        self,
        entry_id: str,
    ) -> list[KnowledgeEntry]:
        """Get entries that support the given entry."""
        relationships = await self._repository.get_relationships(
            entry_id=entry_id,
            relationship_type=RelationshipType.SUPPORTS,
            as_source=False,
        )

        entries = []
        for rel in relationships:
            entry = await self._repository.get_entry(rel.source_id)
            if entry:
                entries.append(entry)

        return entries

    async def get_refuting_entries(
        self,
        entry_id: str,
    ) -> list[KnowledgeEntry]:
        """Get entries that refute the given entry."""
        relationships = await self._repository.get_relationships(
            entry_id=entry_id,
            relationship_type=RelationshipType.REFUTES,
            as_source=False,
        )

        entries = []
        for rel in relationships:
            entry = await self._repository.get_entry(rel.source_id)
            if entry:
                entries.append(entry)

        return entries

    async def find_clusters(
        self,
        min_size: int = 3,
        relationship_types: list[RelationshipType] | None = None,
    ) -> list[ClusterResult]:
        """
        Find clusters of related entries.

        Args:
            min_size: Minimum cluster size
            relationship_types: Relationship types to consider

        Returns:
            List of cluster results
        """
        # Build adjacency list
        entries = await self._repository.list_entries(limit=10000)
        adjacency: dict[str, set[str]] = defaultdict(set)

        for entry in entries:
            rels = await self._get_relationships_filtered(
                entry.entry_id, relationship_types, as_source=True
            )
            for rel in rels:
                adjacency[entry.entry_id].add(rel.target_id)
                adjacency[rel.target_id].add(entry.entry_id)

        # Find connected components
        visited: set[str] = set()
        clusters: list[ClusterResult] = []
        cluster_id = 0

        for entry_id in adjacency:
            if entry_id in visited:
                continue

            # BFS to find component
            component: list[str] = []
            queue = [entry_id]

            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue

                visited.add(current)
                component.append(current)

                for neighbor in adjacency[current]:
                    if neighbor not in visited:
                        queue.append(neighbor)

            if len(component) >= min_size:
                # Find central entry (highest degree)
                degrees = [(eid, len(adjacency[eid])) for eid in component]
                central = max(degrees, key=lambda x: x[1])[0]

                # Calculate density
                possible_edges = len(component) * (len(component) - 1) / 2
                actual_edges = sum(len(adjacency[eid]) for eid in component) / 2
                density = actual_edges / possible_edges if possible_edges > 0 else 0

                # Determine dominant type
                type_counts: dict[EntryType, int] = defaultdict(int)
                for eid in component:
                    e = await self._repository.get_entry(eid)
                    if e:
                        type_counts[e.entry_type] += 1

                dominant_type = (
                    max(type_counts.items(), key=lambda x: x[1])[0]
                    if type_counts
                    else None
                )

                clusters.append(
                    ClusterResult(
                        cluster_id=f"cluster_{cluster_id}",
                        entries=component,
                        central_entry=central,
                        density=density,
                        dominant_type=dominant_type,
                    )
                )
                cluster_id += 1

        # Sort by size descending
        clusters.sort(key=lambda c: len(c.entries), reverse=True)
        return clusters

    async def get_graph_metrics(self) -> GraphMetrics:
        """
        Get overall metrics about the knowledge graph.

        Returns:
            Graph metrics
        """
        entries = await self._repository.list_entries(limit=100000)
        stats = self._repository.get_stats()

        total_nodes = stats["active_entries"]
        total_edges = stats["total_relationships"]

        # Calculate average degree
        avg_degree = (2 * total_edges / total_nodes) if total_nodes > 0 else 0

        # Calculate density
        possible_edges = total_nodes * (total_nodes - 1)
        density = (2 * total_edges / possible_edges) if possible_edges > 0 else 0

        # Find connected components
        adjacency: dict[str, set[str]] = defaultdict(set)
        for entry in entries:
            rels = await self._repository.get_relationships(entry.entry_id, as_source=True)
            for rel in rels:
                adjacency[entry.entry_id].add(rel.target_id)
                adjacency[rel.target_id].add(entry.entry_id)

        visited: set[str] = set()
        components: list[int] = []

        for entry in entries:
            if entry.entry_id in visited:
                continue

            component_size = 0
            queue = [entry.entry_id]

            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue

                visited.add(current)
                component_size += 1

                for neighbor in adjacency[current]:
                    if neighbor not in visited:
                        queue.append(neighbor)

            if component_size > 0:
                components.append(component_size)

        # Add isolated nodes
        for entry in entries:
            if entry.entry_id not in visited:
                components.append(1)
                visited.add(entry.entry_id)

        # Count edge types
        edge_types: dict[str, int] = defaultdict(int)
        for entry in entries:
            rels = await self._repository.get_relationships(entry.entry_id, as_source=True)
            for rel in rels:
                edge_types[rel.relationship_type.value] += 1

        return GraphMetrics(
            total_nodes=total_nodes,
            total_edges=total_edges,
            avg_degree=avg_degree,
            density=density,
            connected_components=len(components),
            largest_component_size=max(components) if components else 0,
            node_types=stats.get("entries_by_type", {}),
            edge_types=dict(edge_types),
        )

    async def infer_relationships(
        self,
        entry_id: str,
        min_confidence: float = 0.7,
    ) -> list[tuple[str, RelationshipType, float]]:
        """
        Infer potential relationships for an entry.

        Uses existing relationships to suggest new ones.

        Args:
            entry_id: Entry ID
            min_confidence: Minimum confidence threshold

        Returns:
            List of (target_id, relationship_type, confidence) tuples
        """
        inferred: list[tuple[str, RelationshipType, float]] = []
        entry = await self._repository.get_entry(entry_id)
        if not entry:
            return inferred

        # Get existing relationships
        existing = await self._repository.get_relationships(entry_id, as_source=True)
        existing_targets = {rel.target_id for rel in existing}

        # Look for transitive relationships
        for rel in existing:
            target_rels = await self._repository.get_relationships(
                rel.target_id, as_source=True
            )

            for target_rel in target_rels:
                if target_rel.target_id != entry_id and target_rel.target_id not in existing_targets:
                    # Infer relationship through transitivity
                    confidence = rel.strength * target_rel.strength * 0.8
                    if confidence >= min_confidence:
                        inferred.append((
                            target_rel.target_id,
                            target_rel.relationship_type,
                            confidence,
                        ))

        # Deduplicate and sort
        seen = set()
        unique_inferred = []
        for target_id, rel_type, conf in inferred:
            key = (target_id, rel_type)
            if key not in seen:
                seen.add(key)
                unique_inferred.append((target_id, rel_type, conf))

        unique_inferred.sort(key=lambda x: x[2], reverse=True)
        return unique_inferred

    async def _get_relationships_filtered(
        self,
        entry_id: str,
        relationship_types: list[RelationshipType] | None,
        as_source: bool,
    ) -> list[Relationship]:
        """Get relationships with optional type filtering."""
        if relationship_types and len(relationship_types) == 1:
            return await self._repository.get_relationships(
                entry_id=entry_id,
                relationship_type=relationship_types[0],
                as_source=as_source,
            )
        else:
            all_rels = await self._repository.get_relationships(
                entry_id=entry_id,
                as_source=as_source,
            )
            if relationship_types:
                return [r for r in all_rels if r.relationship_type in relationship_types]
            return all_rels

    def _entry_to_node(self, entry: KnowledgeEntry) -> GraphNode:
        """Convert entry to graph node."""
        return GraphNode(
            node_id=entry.entry_id,
            entry_type=entry.entry_type,
            title=entry.title,
            domain=entry.domain,
            properties={
                "verification_status": entry.verification_status.value,
                "confidence_score": entry.confidence_score,
                "tags": entry.tags,
            },
        )

    def _relationship_to_edge(self, rel: Relationship) -> GraphEdge:
        """Convert relationship to graph edge."""
        return GraphEdge(
            source_id=rel.source_id,
            target_id=rel.target_id,
            relationship_type=rel.relationship_type,
            strength=rel.strength,
            properties={
                "evidence": rel.evidence,
                "created_by": rel.created_by,
            },
        )

    def _get_inverse_relationship(
        self,
        rel_type: RelationshipType,
    ) -> RelationshipType | None:
        """Get inverse relationship type."""
        inverses = {
            RelationshipType.SUPPORTS: None,  # No direct inverse
            RelationshipType.REFUTES: None,
            RelationshipType.CITES: None,
            RelationshipType.EXTENDS: None,
            RelationshipType.USES: None,
            RelationshipType.DERIVED_FROM: None,
            RelationshipType.RELATED_TO: RelationshipType.RELATED_TO,
            RelationshipType.PART_OF: None,
            RelationshipType.VERSION_OF: None,
        }
        return inverses.get(rel_type)


# Singleton instance
_graph_service_instance: KnowledgeGraphService | None = None


def get_graph_service() -> KnowledgeGraphService:
    """Get singleton KnowledgeGraphService instance."""
    global _graph_service_instance
    if _graph_service_instance is None:
        _graph_service_instance = KnowledgeGraphService()
    return _graph_service_instance
