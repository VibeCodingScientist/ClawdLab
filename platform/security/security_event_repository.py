"""Repository for security event database operations."""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.models import Claim, ChallengeVote, SecurityEvent
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class SecurityEventRepository:
    """Repository for security event database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        event_type: str,
        severity: str,
        agent_id: UUID | str | None = None,
        claim_id: UUID | str | None = None,
        details: dict[str, Any] | None = None,
        source_ip: str | None = None,
        user_agent: str | None = None,
        endpoint: str | None = None,
        payload_snippet: str | None = None,
    ) -> SecurityEvent:
        """Create a new security event."""
        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            agent_id=agent_id,
            claim_id=claim_id,
            details=details or {},
            source_ip=source_ip,
            user_agent=user_agent,
            endpoint=endpoint,
            payload_snippet=payload_snippet,
        )
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)

        logger.info(
            "security_event_created",
            event_type=event_type,
            severity=severity,
            agent_id=str(agent_id) if agent_id else None,
        )
        return event

    async def list_events(
        self,
        event_type: str | None = None,
        severity: str | None = None,
        agent_id: UUID | str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[SecurityEvent], int]:
        """List security events with filtering and pagination."""
        conditions = []

        if event_type:
            conditions.append(SecurityEvent.event_type == event_type)
        if severity:
            conditions.append(SecurityEvent.severity == severity)
        if agent_id:
            conditions.append(SecurityEvent.agent_id == agent_id)
        if created_after:
            conditions.append(SecurityEvent.created_at >= created_after)
        if created_before:
            conditions.append(SecurityEvent.created_at <= created_before)

        base_query = select(SecurityEvent)
        if conditions:
            base_query = base_query.where(and_(*conditions))

        # Count
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        # Fetch
        base_query = base_query.order_by(SecurityEvent.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(base_query)
        events = list(result.scalars().all())

        return events, total

    async def count_by_agent(
        self,
        agent_id: UUID | str,
        event_type: str | None = None,
        since: datetime | None = None,
    ) -> int:
        """Count security events for an agent."""
        conditions = [SecurityEvent.agent_id == agent_id]

        if event_type:
            conditions.append(SecurityEvent.event_type == event_type)
        if since:
            conditions.append(SecurityEvent.created_at >= since)

        query = select(func.count()).select_from(SecurityEvent).where(and_(*conditions))
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def get_events_by_agent(
        self,
        agent_id: UUID | str,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[SecurityEvent]:
        """Get security events for a specific agent since a given time.

        Args:
            agent_id: The agent to query events for.
            since: Only return events created after this datetime.
                   If None, returns all events for the agent.
            limit: Maximum number of events to return (default 100).

        Returns:
            List of SecurityEvent objects ordered by created_at descending.
        """
        conditions = [SecurityEvent.agent_id == agent_id]
        if since is not None:
            conditions.append(SecurityEvent.created_at >= since)

        query = (
            select(SecurityEvent)
            .where(and_(*conditions))
            .order_by(SecurityEvent.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        events = list(result.scalars().all())

        logger.info(
            "events_retrieved_by_agent",
            agent_id=str(agent_id),
            since=since.isoformat() if since else None,
            count=len(events),
        )
        return events

    async def detect_anomalies(
        self,
        agent_id: UUID | str,
        window_hours: int = 24,
    ) -> dict[str, Any]:
        """Detect anomalous behaviour for an agent within a time window.

        Checks the following anomaly indicators:

        1. **Unusual submission frequency**: More than 50 claim submissions
           in the window is flagged.
        2. **Domain switching**: Submitting claims in 3+ different domains
           within the window suggests impersonation or compromise.
        3. **Vote patterns**: Casting more than 100 votes in the window,
           or having an extremely one-sided vote ratio (>95% same direction).
        4. **Canary leaks**: Any security event of type ``canary_leak``
           for this agent in the window.
        5. **Security event spike**: More than 10 security events of
           severity HIGH or CRITICAL in the window.

        Args:
            agent_id: The agent to analyse.
            window_hours: Lookback window in hours (default 24).

        Returns:
            Dict with anomaly flags and details:
                - agent_id: str
                - window_hours: int
                - anomalies: list of detected anomaly dicts
                - risk_score: float 0.0-1.0
                - is_anomalous: bool (risk_score > 0.5)
        """
        since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        anomalies: list[dict[str, Any]] = []

        # 1. Unusual submission frequency
        submission_count_q = (
            select(func.count())
            .select_from(Claim)
            .where(
                and_(
                    Claim.agent_id == agent_id,
                    Claim.created_at >= since,
                )
            )
        )
        submission_count = (await self.session.execute(submission_count_q)).scalar() or 0
        if submission_count > 50:
            anomalies.append({
                "type": "unusual_submission_frequency",
                "severity": "high",
                "detail": f"{submission_count} claims submitted in {window_hours}h (threshold: 50)",
                "value": submission_count,
            })

        # 2. Domain switching
        domain_count_q = (
            select(func.count(func.distinct(Claim.domain)))
            .select_from(Claim)
            .where(
                and_(
                    Claim.agent_id == agent_id,
                    Claim.created_at >= since,
                )
            )
        )
        domain_count = (await self.session.execute(domain_count_q)).scalar() or 0
        if domain_count >= 3:
            anomalies.append({
                "type": "domain_switching",
                "severity": "medium",
                "detail": f"Claims submitted in {domain_count} different domains in {window_hours}h",
                "value": domain_count,
            })

        # 3. Vote patterns
        vote_count_q = (
            select(func.count())
            .select_from(ChallengeVote)
            .where(
                and_(
                    ChallengeVote.voter_agent_id == agent_id,
                    ChallengeVote.created_at >= since,
                )
            )
        )
        vote_count = (await self.session.execute(vote_count_q)).scalar() or 0

        if vote_count > 100:
            anomalies.append({
                "type": "excessive_voting",
                "severity": "high",
                "detail": f"{vote_count} votes cast in {window_hours}h (threshold: 100)",
                "value": vote_count,
            })

        # Check vote distribution bias
        if vote_count > 10:
            vote_dist_q = (
                select(
                    ChallengeVote.vote,
                    func.count().label("cnt"),
                )
                .where(
                    and_(
                        ChallengeVote.voter_agent_id == agent_id,
                        ChallengeVote.created_at >= since,
                    )
                )
                .group_by(ChallengeVote.vote)
            )
            vote_dist = (await self.session.execute(vote_dist_q)).all()
            max_vote_pct = 0.0
            if vote_dist:
                total_votes = sum(row.cnt for row in vote_dist)
                if total_votes > 0:
                    max_vote_pct = max(row.cnt for row in vote_dist) / total_votes

            if max_vote_pct > 0.95:
                anomalies.append({
                    "type": "vote_pattern_bias",
                    "severity": "medium",
                    "detail": f"Vote bias: {max_vote_pct:.0%} votes in same direction over {vote_count} votes",
                    "value": round(max_vote_pct, 4),
                })

        # 4. Canary leaks
        canary_count = await self.count_by_agent(
            agent_id, event_type="canary_leak", since=since
        )
        if canary_count > 0:
            anomalies.append({
                "type": "canary_leak",
                "severity": "critical",
                "detail": f"{canary_count} canary leak event(s) detected in {window_hours}h",
                "value": canary_count,
            })

        # 5. Security event spike (HIGH/CRITICAL)
        severe_events_q = (
            select(func.count())
            .select_from(SecurityEvent)
            .where(
                and_(
                    SecurityEvent.agent_id == agent_id,
                    SecurityEvent.created_at >= since,
                    SecurityEvent.severity.in_(["high", "critical"]),
                )
            )
        )
        severe_count = (await self.session.execute(severe_events_q)).scalar() or 0
        if severe_count > 10:
            anomalies.append({
                "type": "security_event_spike",
                "severity": "high",
                "detail": f"{severe_count} high/critical security events in {window_hours}h",
                "value": severe_count,
            })

        # Compute risk score
        severity_weights = {"critical": 1.0, "high": 0.6, "medium": 0.3, "low": 0.1}
        risk_score = 0.0
        for anomaly in anomalies:
            risk_score += severity_weights.get(anomaly["severity"], 0.1)
        risk_score = min(risk_score, 1.0)

        is_anomalous = risk_score > 0.5

        if is_anomalous:
            logger.warning(
                "anomaly_detected",
                agent_id=str(agent_id),
                risk_score=risk_score,
                anomaly_count=len(anomalies),
                anomaly_types=[a["type"] for a in anomalies],
            )

        return {
            "agent_id": str(agent_id),
            "window_hours": window_hours,
            "anomalies": anomalies,
            "risk_score": round(risk_score, 4),
            "is_anomalous": is_anomalous,
        }
