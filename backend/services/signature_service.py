"""Signature chain service — cryptographic provenance for state transitions."""

import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.logging_config import get_logger
from backend.models import SignatureChain

logger = get_logger(__name__)


async def sign_and_append(
    db: AsyncSession,
    entity_type: str,
    entity_id: UUID,
    action: str,
    agent_id: UUID,
    payload: dict,
    signature: str = "",
) -> SignatureChain:
    """
    Create a SHA-256 hash of the payload, chain it to the previous entry,
    and append to the signature_chain table.

    Args:
        db: Database session
        entity_type: 'task', 'lab', 'forum_post'
        entity_id: UUID of the entity
        action: 'status_change', 'vote', 'result_submitted', etc.
        agent_id: Agent performing the action
        payload: The data being signed (will be JSON-serialized + hashed)
        signature: Optional Ed25519 signature (base64). Empty if not provided.
    """
    # Serialize payload deterministically
    payload_json = json.dumps(payload, sort_keys=True, default=str)
    payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()

    # Get previous hash in chain for this entity
    prev_result = await db.execute(
        select(SignatureChain.payload_hash)
        .where(
            SignatureChain.entity_type == entity_type,
            SignatureChain.entity_id == entity_id,
        )
        .order_by(SignatureChain.created_at.desc())
        .limit(1)
    )
    previous_hash = prev_result.scalar_one_or_none()

    entry = SignatureChain(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        agent_id=agent_id,
        payload_hash=payload_hash,
        signature=signature or payload_hash,  # Use hash as placeholder if no signature
        previous_hash=previous_hash,
        metadata_={
            "payload_preview": payload_json[:200],
        },
    )
    db.add(entry)

    logger.info(
        "signature_appended",
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        agent_id=str(agent_id),
    )

    return entry
