"""Unit tests for ResearchChallengeService — CRUD, registration, submissions."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_challenge(
    slug: str = "test-challenge",
    status: str = "draft",
    domain: str = "mathematics",
    registration_stake: int = 0,
    max_submissions_per_day: int = 5,
):
    """Return a MagicMock that behaves like a ResearchChallenge row."""
    ch = MagicMock()
    ch.id = uuid4()
    ch.slug = slug
    ch.title = "Test Challenge"
    ch.description = "A test challenge description"
    ch.domain = domain
    ch.status = status
    ch.registration_stake = registration_stake
    ch.max_submissions_per_day = max_submissions_per_day
    ch.created_at = datetime.now(timezone.utc)
    ch.updated_at = datetime.now(timezone.utc)
    return ch


def _make_registration(challenge_id=None, lab_id=None, status="active"):
    """Return a MagicMock that behaves like a ChallengeRegistration row."""
    reg = MagicMock()
    reg.id = uuid4()
    reg.challenge_id = challenge_id or uuid4()
    reg.lab_id = lab_id or uuid4()
    reg.status = status
    reg.stake_deposited = 0
    reg.registered_by = uuid4()
    return reg


def _make_create_request(slug="test-challenge", domain="mathematics"):
    """Build a minimal CreateChallengeRequest-like object."""
    from platform.challenges.schemas import CreateChallengeRequest

    return CreateChallengeRequest(
        slug=slug,
        title="Test Challenge",
        description="A test challenge description",
        domain=domain,
        problem_spec={"task": "classify"},
        evaluation_metric="accuracy",
        evaluation_config={},
        higher_is_better=True,
        submission_closes=datetime(2026, 12, 31, tzinfo=timezone.utc),
        total_prize_karma=1000,
        max_submissions_per_day=5,
        difficulty="medium",
        tags=["test"],
    )


def _make_submit_request(lab_id=None, agent_id=None, code_ref="git://repo/abc123"):
    """Build a minimal SubmitRequest-like object."""
    from platform.challenges.schemas import SubmitRequest

    return SubmitRequest(
        lab_id=lab_id or uuid4(),
        agent_id=agent_id or uuid4(),
        submission_type="code",
        code_ref=code_ref,
        claim_id=None,
        metadata={},
    )


# ---------------------------------------------------------------------------
# 1. Business-rule / pure-logic tests (no async, no DB)
# ---------------------------------------------------------------------------


class TestChallengeServiceRules:
    """Test challenge service business rules without DB."""

    def test_submission_hash_deterministic(self):
        """Same content produces same hash (dedup works)."""
        content1 = "git://repo/commit1:None:{'key': 'val'}"
        content2 = "git://repo/commit1:None:{'key': 'val'}"

        hash1 = hashlib.sha256(content1.encode()).hexdigest()
        hash2 = hashlib.sha256(content2.encode()).hexdigest()

        assert hash1 == hash2
        assert len(hash1) == 64

    def test_different_content_different_hash(self):
        """Different content produces different hash."""
        content1 = "git://repo/commit1:None:{}"
        content2 = "git://repo/commit2:None:{}"

        hash1 = hashlib.sha256(content1.encode()).hexdigest()
        hash2 = hashlib.sha256(content2.encode()).hexdigest()

        assert hash1 != hash2

    def test_challenge_difficulty_values(self):
        """Valid difficulty values for research challenges."""
        valid = {"tutorial", "easy", "medium", "hard", "grandmaster"}
        assert len(valid) == 5

    def test_challenge_status_values(self):
        """Valid status values for research challenges."""
        valid = {"draft", "review", "open", "active", "evaluation", "completed", "cancelled"}
        assert len(valid) == 7

    def test_medal_types(self):
        """Valid medal types."""
        valid = {"gold", "silver", "bronze", "milestone", "participation"}
        assert len(valid) == 5


# ---------------------------------------------------------------------------
# 2. create_challenge
# ---------------------------------------------------------------------------


class TestChallengeServiceCreate:
    """Tests for ResearchChallengeService.create_challenge."""

    @pytest.mark.asyncio
    async def test_create_challenge_initializes_draft_status(self):
        """Newly created challenge must start in 'draft' status."""
        from platform.challenges.service import ResearchChallengeService

        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        service = ResearchChallengeService(session)

        sponsor_id = uuid4()
        data = _make_create_request(slug="my-challenge")

        result = await service.create_challenge(sponsor_id, data)

        # session.add should have been called with the new challenge object
        session.add.assert_called_once()
        created = session.add.call_args[0][0]
        assert created.status == "draft"

        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_challenge_sets_slug_and_domain(self):
        """Challenge must carry the slug and domain from the request."""
        from platform.challenges.service import ResearchChallengeService

        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        service = ResearchChallengeService(session)

        sponsor_id = uuid4()
        data = _make_create_request(slug="genomics-2026", domain="computational_biology")

        result = await service.create_challenge(sponsor_id, data)

        created = session.add.call_args[0][0]
        assert created.slug == "genomics-2026"
        assert created.domain == "computational_biology"


# ---------------------------------------------------------------------------
# 3. list_challenges
# ---------------------------------------------------------------------------


class TestChallengeServiceListChallenges:
    """Tests for ResearchChallengeService.list_challenges."""

    @pytest.mark.asyncio
    async def test_list_challenges_returns_results(self):
        """list_challenges should return whatever the DB yields."""
        from platform.challenges.service import ResearchChallengeService

        challenge_a = _make_challenge(slug="alpha", status="open")
        challenge_b = _make_challenge(slug="beta", status="active")

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [challenge_a, challenge_b]

        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        service = ResearchChallengeService(session)
        results = await service.list_challenges()

        assert len(results) == 2
        assert results[0].slug == "alpha"
        assert results[1].slug == "beta"
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_challenges_filters_by_status(self):
        """Passing status= should still execute and return filtered rows."""
        from platform.challenges.service import ResearchChallengeService

        challenge = _make_challenge(slug="only-open", status="open")

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [challenge]

        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        service = ResearchChallengeService(session)
        results = await service.list_challenges(status="open")

        assert len(results) == 1
        assert results[0].status == "open"
        session.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# 4. register_lab
# ---------------------------------------------------------------------------


class TestChallengeServiceRegistration:
    """Tests for ResearchChallengeService.register_lab."""

    @pytest.mark.asyncio
    async def test_register_lab_creates_registration(self):
        """Successful registration adds a row and flushes."""
        from platform.challenges.service import ResearchChallengeService

        challenge = _make_challenge(status="open", registration_stake=10)
        lab_id = uuid4()
        agent_id = uuid4()

        # First execute: load challenge (scalar_one returns challenge)
        challenge_result = MagicMock()
        challenge_result.scalar_one.return_value = challenge

        # Second execute: duplicate check (scalar_one_or_none returns None)
        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = None

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[challenge_result, dup_result])
        session.add = MagicMock()
        session.flush = AsyncMock()

        service = ResearchChallengeService(session)
        result = await service.register_lab("test-challenge", lab_id, agent_id)

        session.add.assert_called_once()
        registration = session.add.call_args[0][0]
        assert registration.challenge_id == challenge.id
        assert registration.lab_id == lab_id
        assert registration.registered_by == agent_id
        assert registration.stake_deposited == 10
        assert registration.status == "active"
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_register_lab_rejects_duplicate(self):
        """Should raise ValueError when the lab is already registered."""
        from platform.challenges.service import ResearchChallengeService

        challenge = _make_challenge(status="open")
        lab_id = uuid4()
        agent_id = uuid4()

        existing_reg = _make_registration(
            challenge_id=challenge.id,
            lab_id=lab_id,
        )

        # First execute: load challenge
        challenge_result = MagicMock()
        challenge_result.scalar_one.return_value = challenge

        # Second execute: duplicate check finds existing
        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = existing_reg

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[challenge_result, dup_result])

        service = ResearchChallengeService(session)

        with pytest.raises(ValueError, match="already registered"):
            await service.register_lab("test-challenge", lab_id, agent_id)

    @pytest.mark.asyncio
    async def test_register_lab_rejects_non_open_challenge(self):
        """Should raise ValueError when challenge is not in 'open' status."""
        from platform.challenges.service import ResearchChallengeService

        challenge = _make_challenge(status="draft")

        challenge_result = MagicMock()
        challenge_result.scalar_one.return_value = challenge

        session = AsyncMock()
        session.execute = AsyncMock(return_value=challenge_result)

        service = ResearchChallengeService(session)

        with pytest.raises(ValueError, match="must be 'open'"):
            await service.register_lab("test-challenge", uuid4(), uuid4())


# ---------------------------------------------------------------------------
# 5. submit_solution
# ---------------------------------------------------------------------------


class TestChallengeServiceSubmission:
    """Tests for ResearchChallengeService.submit_solution."""

    @pytest.mark.asyncio
    async def test_submit_solution_creates_submission(self):
        """Successful submission adds a row with pending status."""
        from platform.challenges.service import ResearchChallengeService

        challenge = _make_challenge(status="active", max_submissions_per_day=5)
        lab_id = uuid4()
        agent_id = uuid4()
        data = _make_submit_request(lab_id=lab_id, agent_id=agent_id)

        # 1. Load challenge
        challenge_result = MagicMock()
        challenge_result.scalar_one.return_value = challenge

        # 2. Verify registration exists
        reg_result = MagicMock()
        reg_result.scalar_one_or_none.return_value = _make_registration(
            challenge_id=challenge.id, lab_id=lab_id,
        )

        # 3. Daily submission count
        daily_count_result = MagicMock()
        daily_count_result.scalar.return_value = 0

        # 4. Duplicate hash check
        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = None

        # 5. Next sequence number
        seq_result = MagicMock()
        seq_result.scalar.return_value = 2  # next will be 3

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[
            challenge_result,
            reg_result,
            daily_count_result,
            dup_result,
            seq_result,
        ])
        session.add = MagicMock()
        session.flush = AsyncMock()

        service = ResearchChallengeService(session)
        result = await service.submit_solution("test-challenge", data)

        session.add.assert_called_once()
        submission = session.add.call_args[0][0]
        assert submission.challenge_id == challenge.id
        assert submission.lab_id == lab_id
        assert submission.submitted_by == agent_id
        assert submission.status == "pending"
        assert submission.sequence_number == 3
        assert len(submission.submission_hash) == 64
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_submit_solution_rejects_duplicate_hash(self):
        """Should raise ValueError when identical content hash already exists."""
        from platform.challenges.service import ResearchChallengeService

        challenge = _make_challenge(status="active", max_submissions_per_day=5)
        lab_id = uuid4()
        agent_id = uuid4()
        data = _make_submit_request(lab_id=lab_id, agent_id=agent_id, code_ref="git://repo/dup")

        # Pre-compute the expected hash so we can mock a duplicate
        hash_content = f"{data.code_ref}:{data.claim_id}:{str(data.metadata)}"
        expected_hash = hashlib.sha256(hash_content.encode()).hexdigest()

        existing_submission = MagicMock()
        existing_submission.submission_hash = expected_hash

        # 1. Load challenge
        challenge_result = MagicMock()
        challenge_result.scalar_one.return_value = challenge

        # 2. Verify registration exists
        reg_result = MagicMock()
        reg_result.scalar_one_or_none.return_value = _make_registration(
            challenge_id=challenge.id, lab_id=lab_id,
        )

        # 3. Daily submission count (within limit)
        daily_count_result = MagicMock()
        daily_count_result.scalar.return_value = 1

        # 4. Duplicate hash check -- finds existing
        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = existing_submission

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[
            challenge_result,
            reg_result,
            daily_count_result,
            dup_result,
        ])

        service = ResearchChallengeService(session)

        with pytest.raises(ValueError, match="Duplicate submission"):
            await service.submit_solution("test-challenge", data)

    @pytest.mark.asyncio
    async def test_submit_solution_rejects_non_active_challenge(self):
        """Should raise ValueError when challenge is not in 'active' status."""
        from platform.challenges.service import ResearchChallengeService

        challenge = _make_challenge(status="open")
        data = _make_submit_request()

        challenge_result = MagicMock()
        challenge_result.scalar_one.return_value = challenge

        session = AsyncMock()
        session.execute = AsyncMock(return_value=challenge_result)

        service = ResearchChallengeService(session)

        with pytest.raises(ValueError, match="must be 'active'"):
            await service.submit_solution("test-challenge", data)

    @pytest.mark.asyncio
    async def test_submit_solution_rejects_unregistered_lab(self):
        """Should raise ValueError when lab is not registered for the challenge."""
        from platform.challenges.service import ResearchChallengeService

        challenge = _make_challenge(status="active")
        data = _make_submit_request()

        # 1. Load challenge
        challenge_result = MagicMock()
        challenge_result.scalar_one.return_value = challenge

        # 2. Registration check returns None (not registered)
        reg_result = MagicMock()
        reg_result.scalar_one_or_none.return_value = None

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[challenge_result, reg_result])

        service = ResearchChallengeService(session)

        with pytest.raises(ValueError, match="not registered"):
            await service.submit_solution("test-challenge", data)

    @pytest.mark.asyncio
    async def test_submit_solution_rejects_daily_limit_exceeded(self):
        """Should raise ValueError when daily submission limit is reached."""
        from platform.challenges.service import ResearchChallengeService

        challenge = _make_challenge(status="active", max_submissions_per_day=3)
        data = _make_submit_request()

        # 1. Load challenge
        challenge_result = MagicMock()
        challenge_result.scalar_one.return_value = challenge

        # 2. Registration check passes
        reg_result = MagicMock()
        reg_result.scalar_one_or_none.return_value = _make_registration()

        # 3. Daily count at limit
        daily_count_result = MagicMock()
        daily_count_result.scalar.return_value = 3  # equals max

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[
            challenge_result,
            reg_result,
            daily_count_result,
        ])

        service = ResearchChallengeService(session)

        with pytest.raises(ValueError, match="Daily submission limit"):
            await service.submit_solution("test-challenge", data)
