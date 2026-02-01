"""Weaviate client for vector search operations."""

import os
from typing import Any

import weaviate
from weaviate.classes.config import Configure, Property, DataType
from weaviate.classes.query import MetadataQuery, Filter

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)

# Global client instance
_client: weaviate.WeaviateClient | None = None


def get_weaviate_url() -> str:
    """Get Weaviate URL from environment."""
    return os.getenv("WEAVIATE_URL", "http://localhost:8080")


def get_client() -> weaviate.WeaviateClient:
    """Get or create Weaviate client."""
    global _client
    if _client is None:
        _client = weaviate.connect_to_local(
            host=get_weaviate_url().replace("http://", "").split(":")[0],
            port=int(get_weaviate_url().split(":")[-1]),
        )
        logger.info("weaviate_client_created", url=get_weaviate_url())
    return _client


def close_client() -> None:
    """Close Weaviate client."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("weaviate_client_closed")


class WeaviateClient:
    """High-level Weaviate client for vector search operations."""

    def __init__(self):
        self.client = get_client()

    # ===========================================
    # SCHEMA OPERATIONS
    # ===========================================

    def create_collection(
        self,
        name: str,
        description: str,
        properties: list[dict[str, Any]],
        vectorizer: str = "text2vec-transformers",
    ) -> bool:
        """Create a new collection (class) in Weaviate."""
        try:
            # Convert properties to Weaviate format
            weaviate_properties = []
            for prop in properties:
                data_type = DataType.TEXT
                if prop.get("dataType") == ["int"]:
                    data_type = DataType.INT
                elif prop.get("dataType") == ["number"]:
                    data_type = DataType.NUMBER
                elif prop.get("dataType") == ["boolean"]:
                    data_type = DataType.BOOL
                elif prop.get("dataType") == ["date"]:
                    data_type = DataType.DATE
                elif prop.get("dataType") == ["string[]"]:
                    data_type = DataType.TEXT_ARRAY

                weaviate_properties.append(
                    Property(
                        name=prop["name"],
                        data_type=data_type,
                        description=prop.get("description", ""),
                    )
                )

            self.client.collections.create(
                name=name,
                description=description,
                properties=weaviate_properties,
                vectorizer_config=Configure.Vectorizer.text2vec_transformers(),
            )
            logger.info("weaviate_collection_created", name=name)
            return True
        except Exception as e:
            logger.error("weaviate_collection_creation_failed", name=name, error=str(e))
            return False

    def collection_exists(self, name: str) -> bool:
        """Check if collection exists."""
        return self.client.collections.exists(name)

    def delete_collection(self, name: str) -> bool:
        """Delete a collection."""
        try:
            self.client.collections.delete(name)
            logger.info("weaviate_collection_deleted", name=name)
            return True
        except Exception as e:
            logger.error("weaviate_collection_deletion_failed", name=name, error=str(e))
            return False

    # ===========================================
    # OBJECT OPERATIONS
    # ===========================================

    def insert_object(
        self,
        collection_name: str,
        properties: dict[str, Any],
        uuid: str | None = None,
        vector: list[float] | None = None,
    ) -> str | None:
        """Insert an object into a collection."""
        try:
            collection = self.client.collections.get(collection_name)
            result = collection.data.insert(
                properties=properties,
                uuid=uuid,
                vector=vector,
            )
            return str(result)
        except Exception as e:
            logger.error(
                "weaviate_insert_failed",
                collection=collection_name,
                error=str(e),
            )
            return None

    def insert_batch(
        self,
        collection_name: str,
        objects: list[dict[str, Any]],
    ) -> int:
        """Insert multiple objects in batch."""
        try:
            collection = self.client.collections.get(collection_name)
            with collection.batch.dynamic() as batch:
                for obj in objects:
                    batch.add_object(
                        properties=obj.get("properties", obj),
                        uuid=obj.get("uuid"),
                        vector=obj.get("vector"),
                    )
            logger.info(
                "weaviate_batch_insert",
                collection=collection_name,
                count=len(objects),
            )
            return len(objects)
        except Exception as e:
            logger.error(
                "weaviate_batch_insert_failed",
                collection=collection_name,
                error=str(e),
            )
            return 0

    def get_object(
        self,
        collection_name: str,
        uuid: str,
        include_vector: bool = False,
    ) -> dict[str, Any] | None:
        """Get an object by UUID."""
        try:
            collection = self.client.collections.get(collection_name)
            result = collection.query.fetch_object_by_id(
                uuid=uuid,
                include_vector=include_vector,
            )
            if result:
                return {
                    "uuid": str(result.uuid),
                    "properties": result.properties,
                    "vector": result.vector if include_vector else None,
                }
            return None
        except Exception as e:
            logger.error(
                "weaviate_get_failed",
                collection=collection_name,
                uuid=uuid,
                error=str(e),
            )
            return None

    def update_object(
        self,
        collection_name: str,
        uuid: str,
        properties: dict[str, Any],
    ) -> bool:
        """Update an object's properties."""
        try:
            collection = self.client.collections.get(collection_name)
            collection.data.update(
                uuid=uuid,
                properties=properties,
            )
            return True
        except Exception as e:
            logger.error(
                "weaviate_update_failed",
                collection=collection_name,
                uuid=uuid,
                error=str(e),
            )
            return False

    def delete_object(self, collection_name: str, uuid: str) -> bool:
        """Delete an object by UUID."""
        try:
            collection = self.client.collections.get(collection_name)
            collection.data.delete_by_id(uuid)
            return True
        except Exception as e:
            logger.error(
                "weaviate_delete_failed",
                collection=collection_name,
                uuid=uuid,
                error=str(e),
            )
            return False

    # ===========================================
    # SEARCH OPERATIONS
    # ===========================================

    def semantic_search(
        self,
        collection_name: str,
        query: str,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
        return_properties: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Perform semantic (vector) search."""
        try:
            collection = self.client.collections.get(collection_name)

            # Build filter if provided
            weaviate_filter = None
            if filters:
                # Simple filter implementation for common cases
                filter_conditions = []
                for key, value in filters.items():
                    if isinstance(value, str):
                        filter_conditions.append(Filter.by_property(key).equal(value))
                    elif isinstance(value, list):
                        filter_conditions.append(Filter.by_property(key).contains_any(value))
                if filter_conditions:
                    weaviate_filter = filter_conditions[0]
                    for fc in filter_conditions[1:]:
                        weaviate_filter = weaviate_filter & fc

            result = collection.query.near_text(
                query=query,
                limit=limit,
                filters=weaviate_filter,
                return_metadata=MetadataQuery(distance=True, certainty=True),
            )

            return [
                {
                    "uuid": str(obj.uuid),
                    "properties": obj.properties,
                    "distance": obj.metadata.distance if obj.metadata else None,
                    "certainty": obj.metadata.certainty if obj.metadata else None,
                }
                for obj in result.objects
            ]
        except Exception as e:
            logger.error(
                "weaviate_search_failed",
                collection=collection_name,
                error=str(e),
            )
            return []

    def hybrid_search(
        self,
        collection_name: str,
        query: str,
        alpha: float = 0.5,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Perform hybrid search (vector + keyword)."""
        try:
            collection = self.client.collections.get(collection_name)

            result = collection.query.hybrid(
                query=query,
                alpha=alpha,  # 0 = keyword only, 1 = vector only
                limit=limit,
                return_metadata=MetadataQuery(score=True),
            )

            return [
                {
                    "uuid": str(obj.uuid),
                    "properties": obj.properties,
                    "score": obj.metadata.score if obj.metadata else None,
                }
                for obj in result.objects
            ]
        except Exception as e:
            logger.error(
                "weaviate_hybrid_search_failed",
                collection=collection_name,
                error=str(e),
            )
            return []

    def vector_search(
        self,
        collection_name: str,
        vector: list[float],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search by vector directly."""
        try:
            collection = self.client.collections.get(collection_name)

            result = collection.query.near_vector(
                near_vector=vector,
                limit=limit,
                return_metadata=MetadataQuery(distance=True),
            )

            return [
                {
                    "uuid": str(obj.uuid),
                    "properties": obj.properties,
                    "distance": obj.metadata.distance if obj.metadata else None,
                }
                for obj in result.objects
            ]
        except Exception as e:
            logger.error(
                "weaviate_vector_search_failed",
                collection=collection_name,
                error=str(e),
            )
            return []

    # ===========================================
    # AGGREGATION
    # ===========================================

    def count(self, collection_name: str) -> int:
        """Count objects in a collection."""
        try:
            collection = self.client.collections.get(collection_name)
            result = collection.aggregate.over_all(total_count=True)
            return result.total_count
        except Exception as e:
            logger.error(
                "weaviate_count_failed",
                collection=collection_name,
                error=str(e),
            )
            return 0


def health_check() -> bool:
    """Check Weaviate connectivity."""
    try:
        client = get_client()
        return client.is_ready()
    except Exception as e:
        logger.error("weaviate_health_check_failed", error=str(e))
        return False
