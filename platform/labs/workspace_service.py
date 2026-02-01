"""Workspace presence service for lab event-to-zone mapping.

Routes lab events to workspace zones for the visual workspace,
updating agent positions and statuses in real-time.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from platform.labs.repository import WorkspaceRepository
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class WorkspaceService:
    """Maps lab events to workspace zone updates.

    Each event type corresponds to a zone and action that determines
    where an agent appears in the visual workspace.
    """

    ZONE_MAPPINGS: Final[dict[str, tuple[str, str]]] = {
        "member.joined":               ("ideation", "entering"),
        "entry.created":               ("roundtable", "contributing"),
        "roundtable.vote_cast":        ("roundtable", "voting"),
        "roundtable.vote_called":      ("roundtable", "moderating"),
        "roundtable.proposal_approved": ("whiteboard", "celebrating"),
        "roundtable.proposal_rejected": ("roundtable", "deliberating"),
        "roundtable.work_assigned":    ("bench", "working"),
        "roundtable.result_submitted": ("presentation", "presenting"),
        "roundtable.result_verified":  ("whiteboard", "celebrating"),
        "roundtable.result_failed":    ("roundtable", "reviewing"),
        "item.proposed":               ("ideation", "proposing"),
    }

    # Zone positions (default center coordinates for each zone)
    ZONE_POSITIONS: Final[dict[str, tuple[float, float]]] = {
        "ideation":     (100.0, 100.0),
        "library":      (300.0, 100.0),
        "bench":        (500.0, 100.0),
        "roundtable":   (100.0, 300.0),
        "whiteboard":   (300.0, 300.0),
        "presentation": (500.0, 300.0),
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.workspace_repo = WorkspaceRepository(session)

    async def handle_event(
        self,
        event_type: str,
        data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Process a lab event and update workspace state.

        Args:
            event_type: The event type string (e.g. "entry.created").
            data: Event payload containing lab_id, agent_id, etc.

        Returns:
            Updated workspace state dict, or None if event is unmapped.
        """
        mapping = self.ZONE_MAPPINGS.get(event_type)
        if not mapping:
            logger.debug("workspace_unmapped_event", event_type=event_type)
            return None

        zone, action = mapping
        lab_id = data.get("lab_id")
        agent_id = data.get("agent_id") or data.get("proposed_by") or data.get("assigned_to")

        if not lab_id or not agent_id:
            logger.debug(
                "workspace_missing_ids",
                event_type=event_type,
                lab_id=lab_id,
                agent_id=agent_id,
            )
            return None

        position = self.ZONE_POSITIONS.get(zone, (0.0, 0.0))

        await self.workspace_repo.upsert(
            lab_id=lab_id,
            agent_id=agent_id,
            zone=zone,
            position_x=position[0],
            position_y=position[1],
            status=action,
        )

        state = {
            "lab_id": str(lab_id),
            "agent_id": str(agent_id),
            "zone": zone,
            "position_x": position[0],
            "position_y": position[1],
            "status": action,
            "action": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            "workspace_state_updated",
            lab_id=str(lab_id),
            agent_id=str(agent_id),
            zone=zone,
            action=action,
        )

        return state

    async def get_lab_workspace(self, lab_id: str | UUID) -> list[dict[str, Any]]:
        """Get current workspace state for all agents in a lab.

        Returns:
            List of workspace state dicts for each agent.
        """
        states = await self.workspace_repo.get_by_lab(lab_id)
        return [
            {
                "agent_id": str(s.agent_id),
                "zone": s.zone,
                "position_x": float(s.position_x),
                "position_y": float(s.position_y),
                "status": s.status,
                "last_action_at": s.last_action_at.isoformat() if s.last_action_at else None,
            }
            for s in states
        ]


__all__ = ["WorkspaceService"]
