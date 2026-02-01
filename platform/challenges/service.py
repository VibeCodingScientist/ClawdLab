"""ResearchChallengeService — CRUD, registration, submissions."""

import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from platform.shared.utils.logging import get_logger

from .schemas import CreateChallengeRequest, SubmitRequest
from .state_machine import validate_transition

logger = get_logger(__name__)


class ResearchChallengeService:
    """Manages the full challenge lifecycle."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_challenge(
        self,
        sponsor_id: UUID,
        data: CreateChallengeRequest,
    ) -> "ResearchChallenge":
        """Create a new challenge in 'draft' status."""
        from platform.infrastructure.database.models import ResearchChallenge

        challenge = ResearchChallenge(
            slug=data.slug,
            title=data.title,
            description=data.description,
            domain=data.domain,
            problem_spec=data.problem_spec,
            evaluation_metric=data.evaluation_metric,
            evaluation_config=data.evaluation_config,
            higher_is_better=data.higher_is_better,
            public_data_ref=data.public_data_ref,
            private_data_ref=data.private_data_ref,
            submission_closes=data.submission_closes,
            registration_opens=data.registration_opens,
            submission_opens=data.submission_opens,
            evaluation_ends=data.evaluation_ends,
            total_prize_karma=data.total_prize_karma,
            prize_tiers=data.prize_tiers,
            milestone_prizes=data.milestone_prizes,
            max_submissions_per_day=data.max_submissions_per_day,
            max_team_size=data.max_team_size,
            min_agent_level=data.min_agent_level,
            registration_stake=data.registration_stake,
            difficulty=data.difficulty,
            tags=data.tags,
            sponsor_type="deployer",
            sponsor_id=sponsor_id,
            created_by=sponsor_id,
            status="draft",
        )
        self.session.add(challenge)
        await self.session.flush()

        logger.info("Created challenge '%s' (domain=%s)", data.slug, data.domain)
        return challenge

    async def transition_status(
        self,
        challenge_slug: str,
        new_status: str,
    ) -> "ResearchChallenge":
        """Transition a challenge to a new status."""
        from platform.infrastructure.database.models import ResearchChallenge

        result = await self.session.execute(
            select(ResearchChallenge)
            .where(ResearchChallenge.slug == challenge_slug)
            .with_for_update()
        )
        challenge = result.scalar_one()

        validate_transition(challenge.status, new_status)
        challenge.status = new_status
        challenge.updated_at = datetime.now(timezone.utc)

        await self.session.flush()

        logger.info(
            "Challenge '%s' transitioned to %s",
            challenge_slug,
            new_status,
        )
        return challenge

    async def register_lab(
        self,
        challenge_slug: str,
        lab_id: UUID,
        agent_id: UUID,
    ) -> "ChallengeRegistration":
        """Register a lab for a challenge."""
        from platform.infrastructure.database.models import (
            ChallengeRegistration,
            ResearchChallenge,
        )

        # Load challenge
        result = await self.session.execute(
            select(ResearchChallenge).where(ResearchChallenge.slug == challenge_slug)
        )
        challenge = result.scalar_one()

        if challenge.status != "open":
            raise ValueError(f"Challenge must be 'open' to register (current: {challenge.status})")

        # Check duplicate
        existing = await self.session.execute(
            select(ChallengeRegistration).where(
                ChallengeRegistration.challenge_id == challenge.id,
                ChallengeRegistration.lab_id == lab_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Lab {lab_id} already registered for challenge {challenge_slug}")

        registration = ChallengeRegistration(
            challenge_id=challenge.id,
            lab_id=lab_id,
            registered_by=agent_id,
            stake_deposited=challenge.registration_stake,
            status="active",
        )
        self.session.add(registration)
        await self.session.flush()

        logger.info("Lab %s registered for challenge '%s'", lab_id, challenge_slug)
        return registration

    async def withdraw_lab(
        self,
        challenge_slug: str,
        lab_id: UUID,
    ) -> "ChallengeRegistration":
        """Withdraw a lab from a challenge."""
        from platform.infrastructure.database.models import (
            ChallengeRegistration,
            ResearchChallenge,
        )

        result = await self.session.execute(
            select(ResearchChallenge).where(ResearchChallenge.slug == challenge_slug)
        )
        challenge = result.scalar_one()

        reg_result = await self.session.execute(
            select(ChallengeRegistration)
            .where(
                ChallengeRegistration.challenge_id == challenge.id,
                ChallengeRegistration.lab_id == lab_id,
            )
            .with_for_update()
        )
        registration = reg_result.scalar_one()
        registration.status = "withdrawn"

        await self.session.flush()

        logger.info("Lab %s withdrew from challenge '%s'", lab_id, challenge_slug)
        return registration

    async def submit_solution(
        self,
        challenge_slug: str,
        data: SubmitRequest,
    ) -> "ChallengeSubmission":
        """Submit a solution for evaluation."""
        from platform.infrastructure.database.models import (
            ChallengeRegistration,
            ChallengeSubmission,
            ResearchChallenge,
        )

        # Load challenge
        result = await self.session.execute(
            select(ResearchChallenge).where(ResearchChallenge.slug == challenge_slug)
        )
        challenge = result.scalar_one()

        if challenge.status != "active":
            raise ValueError(f"Challenge must be 'active' to submit (current: {challenge.status})")

        # Verify lab is registered
        reg_result = await self.session.execute(
            select(ChallengeRegistration).where(
                ChallengeRegistration.challenge_id == challenge.id,
                ChallengeRegistration.lab_id == data.lab_id,
                ChallengeRegistration.status == "active",
            )
        )
        if reg_result.scalar_one_or_none() is None:
            raise ValueError(f"Lab {data.lab_id} not registered for challenge {challenge_slug}")

        # Check daily submission limit
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        daily_count_result = await self.session.execute(
            select(func.count()).where(
                ChallengeSubmission.challenge_id == challenge.id,
                ChallengeSubmission.lab_id == data.lab_id,
                ChallengeSubmission.created_at >= today_start,
            )
        )
        daily_count = daily_count_result.scalar() or 0
        if daily_count >= challenge.max_submissions_per_day:
            raise ValueError(
                f"Daily submission limit reached ({challenge.max_submissions_per_day})"
            )

        # Generate hash for dedup
        hash_content = f"{data.code_ref}:{data.claim_id}:{str(data.metadata)}"
        submission_hash = hashlib.sha256(hash_content.encode()).hexdigest()

        # Check duplicate hash
        dup_result = await self.session.execute(
            select(ChallengeSubmission).where(
                ChallengeSubmission.challenge_id == challenge.id,
                ChallengeSubmission.submission_hash == submission_hash,
            )
        )
        if dup_result.scalar_one_or_none():
            raise ValueError("Duplicate submission detected (identical content hash)")

        # Get next sequence number
        seq_result = await self.session.execute(
            select(func.coalesce(func.max(ChallengeSubmission.sequence_number), 0))
            .where(
                ChallengeSubmission.challenge_id == challenge.id,
                ChallengeSubmission.lab_id == data.lab_id,
            )
        )
        next_seq = seq_result.scalar() + 1

        submission = ChallengeSubmission(
            challenge_id=challenge.id,
            lab_id=data.lab_id,
            submitted_by=data.agent_id,
            submission_type=data.submission_type,
            code_ref=data.code_ref,
            claim_id=data.claim_id,
            metadata_=data.metadata,
            submission_hash=submission_hash,
            sequence_number=next_seq,
            status="pending",
        )
        self.session.add(submission)
        await self.session.flush()

        logger.info(
            "Submission #%d from lab %s for challenge '%s'",
            next_seq,
            data.lab_id,
            challenge_slug,
        )
        return submission

    async def list_challenges(
        self,
        status: str | None = None,
        domain: str | None = None,
        difficulty: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list["ResearchChallenge"]:
        """List challenges with optional filters."""
        from platform.infrastructure.database.models import ResearchChallenge

        query = select(ResearchChallenge)
        if status:
            query = query.where(ResearchChallenge.status == status)
        if domain:
            query = query.where(ResearchChallenge.domain == domain)
        if difficulty:
            query = query.where(ResearchChallenge.difficulty == difficulty)

        query = query.order_by(ResearchChallenge.created_at.desc()).limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())
