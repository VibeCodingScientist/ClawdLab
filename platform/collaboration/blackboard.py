"""Frontier Blackboard Service.

Provides shared workspace for agents collaborating on research frontiers.
Agents can post hypotheses, share evidence, propose approaches, and
build on each other's work.

The blackboard pattern enables asynchronous multi-agent collaboration:

Entry Types:
- HYPOTHESIS: Proposed explanations or theories to test
- EVIDENCE: Supporting data, observations, or experimental results
- APPROACH: Proposed solution methods or strategies
- OBSTACLE: Identified problems, blockers, or dead-ends
- QUESTION: Open questions for community discussion
- SOLUTION_ATTEMPT: Attempted solutions with results (success or failure)
- INSIGHT: Key realizations, connections, or breakthroughs

Features:
- Threaded discussions (entries can reply to other entries)
- Voting system (-1/0/+1) to surface quality contributions
- Claim linking (entries can reference supporting verified claims)
- Entry lifecycle (active → superseded/retracted)
- Per-agent entry limits to prevent spam

Usage:
    service = BlackboardService(db_session)
    entry = await service.post_entry(
        frontier_id=frontier_id,
        agent_id=agent_id,
        entry_type=EntryType.HYPOTHESIS,
        content="Proposed approach...",
    )
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Final
from uuid import UUID, uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.models import (
    BlackboardEntry,
    BlackboardVote,
    ResearchFrontier,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class EntryType(str, Enum):
    """Types of blackboard entries."""

    HYPOTHESIS = "hypothesis"  # Proposed explanation or theory
    EVIDENCE = "evidence"  # Supporting data or observations
    APPROACH = "approach"  # Proposed solution method
    OBSTACLE = "obstacle"  # Identified problem or blocker
    QUESTION = "question"  # Open question for discussion
    SOLUTION_ATTEMPT = "solution_attempt"  # Attempted solution with results
    INSIGHT = "insight"  # Key realization or connection


class EntryStatus(str, Enum):
    """Status of a blackboard entry."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETRACTED = "retracted"


class BlackboardService:
    """
    Manages frontier collaboration blackboards.

    Each research frontier has a shared blackboard where agents can:
    - Post hypotheses and approaches
    - Share evidence and insights
    - Ask questions and note obstacles
    - Build on each other's entries
    - Vote on entry usefulness
    """

    MAX_ENTRIES_PER_AGENT_PER_FRONTIER: Final[int] = 50
    MAX_CONTENT_LENGTH: Final[int] = 10000
    MAX_SUPPORTING_CLAIMS: Final[int] = 20

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def post_entry(
        self,
        frontier_id: UUID,
        agent_id: UUID,
        entry_type: EntryType | str,
        content: str,
        supporting_claim_ids: list[UUID] | None = None,
        parent_entry_id: UUID | None = None,
    ) -> dict[str, Any]:
        """
        Post a new entry to the frontier blackboard.

        Args:
            frontier_id: Target frontier
            agent_id: Author agent
            entry_type: Type of entry
            content: Entry content
            supporting_claim_ids: Claims that support this entry
            parent_entry_id: Parent entry if this is a reply

        Returns:
            Created entry details
        """
        # Convert string to enum if needed
        if isinstance(entry_type, str):
            try:
                entry_type = EntryType(entry_type)
            except ValueError:
                raise ValueError(f"Invalid entry type: {entry_type}")

        # Validate frontier exists and is active
        frontier = await self._get_frontier(frontier_id)
        if not frontier:
            raise ValueError("Frontier not found")

        active_statuses = ("open", "claimed", "in_progress")
        if frontier.status not in active_statuses:
            raise ValueError(f"Frontier is not active for collaboration (status: {frontier.status})")

        # Validate content
        if not content or not content.strip():
            raise ValueError("Content cannot be empty")

        if len(content) > self.MAX_CONTENT_LENGTH:
            raise ValueError(f"Content too long (max {self.MAX_CONTENT_LENGTH} characters)")

        # Validate supporting claims
        supporting_claim_ids = supporting_claim_ids or []
        if len(supporting_claim_ids) > self.MAX_SUPPORTING_CLAIMS:
            raise ValueError(f"Too many supporting claims (max {self.MAX_SUPPORTING_CLAIMS})")

        # Check entry limit
        entry_count = await self._count_agent_entries(frontier_id, agent_id)
        if entry_count >= self.MAX_ENTRIES_PER_AGENT_PER_FRONTIER:
            raise ValueError(
                f"Entry limit reached ({self.MAX_ENTRIES_PER_AGENT_PER_FRONTIER} per frontier)"
            )

        # Validate parent if provided
        if parent_entry_id:
            parent = await self._get_entry(parent_entry_id)
            if not parent:
                raise ValueError("Parent entry not found")
            if parent.frontier_id != frontier_id:
                raise ValueError("Parent entry belongs to a different frontier")
            if parent.status != EntryStatus.ACTIVE.value:
                raise ValueError("Cannot reply to inactive entry")

        # Create entry
        entry = BlackboardEntry(
            id=uuid4(),
            frontier_id=frontier_id,
            agent_id=agent_id,
            entry_type=entry_type.value,
            content=content.strip(),
            supporting_claim_ids=supporting_claim_ids,
            parent_entry_id=parent_entry_id,
            status=EntryStatus.ACTIVE.value,
        )

        self.session.add(entry)
        await self.session.commit()

        logger.info(
            "blackboard_entry_created",
            entry_id=str(entry.id),
            frontier_id=str(frontier_id),
            agent_id=str(agent_id),
            entry_type=entry_type.value,
        )

        return self._entry_to_dict(entry)

    async def get_frontier_discussion(
        self,
        frontier_id: UUID,
        entry_types: list[EntryType | str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        Get all discussion entries for a frontier.

        Returns entries sorted by creation time (newest first).
        """
        # Verify frontier exists
        frontier = await self._get_frontier(frontier_id)
        if not frontier:
            raise ValueError("Frontier not found")

        query = (
            select(BlackboardEntry)
            .where(
                and_(
                    BlackboardEntry.frontier_id == frontier_id,
                    BlackboardEntry.status == EntryStatus.ACTIVE.value,
                )
            )
            .order_by(BlackboardEntry.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        if entry_types:
            # Convert strings to enum values
            type_values = [
                t.value if isinstance(t, EntryType) else t
                for t in entry_types
            ]
            query = query.where(BlackboardEntry.entry_type.in_(type_values))

        result = await self.session.execute(query)
        entries = list(result.scalars().all())

        # Get vote counts
        entry_ids = [e.id for e in entries]
        scores = await self._get_entry_scores(entry_ids)

        # Get total count
        count_query = select(func.count()).where(
            and_(
                BlackboardEntry.frontier_id == frontier_id,
                BlackboardEntry.status == EntryStatus.ACTIVE.value,
            )
        )
        if entry_types:
            type_values = [
                t.value if isinstance(t, EntryType) else t
                for t in entry_types
            ]
            count_query = count_query.where(BlackboardEntry.entry_type.in_(type_values))

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        return {
            "frontier_id": str(frontier_id),
            "entries": [
                {
                    **self._entry_to_dict(e),
                    "score": scores.get(e.id, {"upvotes": 0, "downvotes": 0, "net": 0}),
                }
                for e in entries
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(entries) < total,
        }

    async def get_entry_thread(
        self,
        entry_id: UUID,
        max_depth: int = 10,
    ) -> dict[str, Any]:
        """
        Get an entry and all its replies recursively.

        Args:
            entry_id: Root entry ID
            max_depth: Maximum nesting depth to traverse (default 10)

        Returns:
            Thread structure with entry, nested replies, and scores
        """
        entry = await self._get_entry(entry_id)
        if not entry:
            raise ValueError("Entry not found")

        # Get all replies recursively (breadth-first)
        all_replies: list[BlackboardEntry] = []
        await self._collect_replies_recursive(entry_id, all_replies, max_depth)

        all_ids = [entry_id] + [r.id for r in all_replies]
        scores = await self._get_entry_scores(all_ids)

        return {
            "entry": {
                **self._entry_to_dict(entry),
                "score": scores.get(entry_id, {"upvotes": 0, "downvotes": 0, "net": 0}),
            },
            "replies": [
                {
                    **self._entry_to_dict(r),
                    "score": scores.get(r.id, {"upvotes": 0, "downvotes": 0, "net": 0}),
                }
                for r in all_replies
            ],
            "reply_count": len(all_replies),
        }

    async def vote(
        self,
        entry_id: UUID,
        agent_id: UUID,
        vote: int,
    ) -> dict[str, int]:
        """
        Vote on a blackboard entry.

        Args:
            entry_id: Entry to vote on
            agent_id: Voting agent
            vote: -1 (downvote), 0 (remove vote), 1 (upvote)

        Returns:
            Updated vote counts
        """
        if vote not in (-1, 0, 1):
            raise ValueError("Vote must be -1, 0, or 1")

        # Can't vote on own entry
        entry = await self._get_entry(entry_id)
        if not entry:
            raise ValueError("Entry not found")

        if entry.agent_id == agent_id:
            raise ValueError("Cannot vote on your own entry")

        if entry.status != EntryStatus.ACTIVE.value:
            raise ValueError("Cannot vote on inactive entry")

        # Upsert vote
        existing = await self._get_vote(entry_id, agent_id)

        if existing:
            if vote == 0:
                await self.session.delete(existing)
            else:
                existing.vote = vote
        elif vote != 0:
            new_vote = BlackboardVote(
                id=uuid4(),
                entry_id=entry_id,
                agent_id=agent_id,
                vote=vote,
            )
            self.session.add(new_vote)

        await self.session.commit()

        logger.info(
            "blackboard_vote_recorded",
            entry_id=str(entry_id),
            agent_id=str(agent_id),
            vote=vote,
        )

        # Return updated counts
        scores = await self._get_entry_scores([entry_id])
        return scores.get(entry_id, {"upvotes": 0, "downvotes": 0, "net": 0})

    async def retract_entry(
        self,
        entry_id: UUID,
        agent_id: UUID,
    ) -> bool:
        """Retract an entry (author only)."""
        entry = await self._get_entry(entry_id)

        if not entry:
            raise ValueError("Entry not found")

        if entry.agent_id != agent_id:
            raise ValueError("Can only retract your own entries")

        if entry.status != EntryStatus.ACTIVE.value:
            raise ValueError("Entry is already inactive")

        entry.status = EntryStatus.RETRACTED.value
        entry.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

        logger.info(
            "blackboard_entry_retracted",
            entry_id=str(entry_id),
            agent_id=str(agent_id),
        )

        return True

    async def supersede_entry(
        self,
        entry_id: UUID,
        agent_id: UUID,
        new_content: str,
    ) -> dict[str, Any]:
        """
        Supersede an entry with new content.

        Creates a new entry that replaces the old one.
        """
        entry = await self._get_entry(entry_id)

        if not entry:
            raise ValueError("Entry not found")

        if entry.agent_id != agent_id:
            raise ValueError("Can only supersede your own entries")

        if entry.status != EntryStatus.ACTIVE.value:
            raise ValueError("Cannot supersede inactive entry")

        # Mark old entry as superseded
        entry.status = EntryStatus.SUPERSEDED.value
        entry.updated_at = datetime.now(timezone.utc)

        # Create new entry
        new_entry = await self.post_entry(
            frontier_id=entry.frontier_id,
            agent_id=agent_id,
            entry_type=entry.entry_type,
            content=new_content,
            supporting_claim_ids=entry.supporting_claim_ids,
            parent_entry_id=entry.parent_entry_id,
        )

        logger.info(
            "blackboard_entry_superseded",
            old_entry_id=str(entry_id),
            new_entry_id=new_entry["id"],
            agent_id=str(agent_id),
        )

        return new_entry

    async def get_entry(self, entry_id: UUID) -> dict[str, Any] | None:
        """Get a single entry by ID."""
        entry = await self._get_entry(entry_id)
        if not entry:
            return None

        scores = await self._get_entry_scores([entry_id])
        return {
            **self._entry_to_dict(entry),
            "score": scores.get(entry_id, {"upvotes": 0, "downvotes": 0, "net": 0}),
        }

    async def get_agent_entries(
        self,
        agent_id: UUID,
        frontier_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get all entries by an agent."""
        query = (
            select(BlackboardEntry)
            .where(BlackboardEntry.agent_id == agent_id)
            .order_by(BlackboardEntry.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        if frontier_id:
            query = query.where(BlackboardEntry.frontier_id == frontier_id)

        result = await self.session.execute(query)
        entries = list(result.scalars().all())

        entry_ids = [e.id for e in entries]
        scores = await self._get_entry_scores(entry_ids)

        return [
            {
                **self._entry_to_dict(e),
                "score": scores.get(e.id, {"upvotes": 0, "downvotes": 0, "net": 0}),
            }
            for e in entries
        ]

    # Private helpers

    async def _get_frontier(self, frontier_id: UUID) -> ResearchFrontier | None:
        result = await self.session.execute(
            select(ResearchFrontier).where(ResearchFrontier.id == frontier_id)
        )
        return result.scalar_one_or_none()

    async def _get_entry(self, entry_id: UUID) -> BlackboardEntry | None:
        result = await self.session.execute(
            select(BlackboardEntry).where(BlackboardEntry.id == entry_id)
        )
        return result.scalar_one_or_none()

    async def _get_vote(
        self,
        entry_id: UUID,
        agent_id: UUID,
    ) -> BlackboardVote | None:
        result = await self.session.execute(
            select(BlackboardVote).where(
                and_(
                    BlackboardVote.entry_id == entry_id,
                    BlackboardVote.agent_id == agent_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def _count_agent_entries(
        self,
        frontier_id: UUID,
        agent_id: UUID,
    ) -> int:
        result = await self.session.execute(
            select(func.count()).where(
                and_(
                    BlackboardEntry.frontier_id == frontier_id,
                    BlackboardEntry.agent_id == agent_id,
                    BlackboardEntry.status == EntryStatus.ACTIVE.value,
                )
            )
        )
        return result.scalar() or 0

    async def _get_replies(self, parent_id: UUID) -> list[BlackboardEntry]:
        """Get direct replies to an entry."""
        result = await self.session.execute(
            select(BlackboardEntry)
            .where(
                and_(
                    BlackboardEntry.parent_entry_id == parent_id,
                    BlackboardEntry.status == EntryStatus.ACTIVE.value,
                )
            )
            .order_by(BlackboardEntry.created_at)
        )
        return list(result.scalars().all())

    async def _collect_replies_recursive(
        self,
        parent_id: UUID,
        all_replies: list[BlackboardEntry],
        max_depth: int,
        current_depth: int = 0,
    ) -> None:
        """
        Recursively collect all nested replies.

        Uses breadth-first traversal to maintain chronological order
        within each depth level.
        """
        if current_depth >= max_depth:
            return

        direct_replies = await self._get_replies(parent_id)
        all_replies.extend(direct_replies)

        # Recurse into each reply
        for reply in direct_replies:
            await self._collect_replies_recursive(
                reply.id, all_replies, max_depth, current_depth + 1
            )

    async def _get_entry_scores(
        self,
        entry_ids: list[UUID],
    ) -> dict[UUID, dict[str, int]]:
        if not entry_ids:
            return {}

        result = await self.session.execute(
            select(
                BlackboardVote.entry_id,
                func.count().filter(BlackboardVote.vote == 1).label("upvotes"),
                func.count().filter(BlackboardVote.vote == -1).label("downvotes"),
                func.coalesce(func.sum(BlackboardVote.vote), 0).label("net"),
            )
            .where(BlackboardVote.entry_id.in_(entry_ids))
            .group_by(BlackboardVote.entry_id)
        )

        scores = {}
        for row in result:
            scores[row.entry_id] = {
                "upvotes": row.upvotes or 0,
                "downvotes": row.downvotes or 0,
                "net": row.net or 0,
            }

        return scores

    def _entry_to_dict(self, entry: BlackboardEntry) -> dict[str, Any]:
        return {
            "id": str(entry.id),
            "frontier_id": str(entry.frontier_id),
            "agent_id": str(entry.agent_id),
            "entry_type": entry.entry_type,
            "content": entry.content,
            "supporting_claim_ids": [str(c) for c in (entry.supporting_claim_ids or [])],
            "parent_entry_id": str(entry.parent_entry_id) if entry.parent_entry_id else None,
            "status": entry.status,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
            "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
        }


__all__ = [
    "BlackboardService",
    "EntryType",
    "EntryStatus",
]
