"""Tests for Lab Service business logic."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from platform.labs.exceptions import (
    InsufficientKarmaError,
    LabArchivedError,
    LabMembershipError,
    LabNotFoundError,
    LabSlugConflictError,
    MaxLabsExceededError,
    RoleCardFullError,
)


class TestLabServiceCreateLab:
    """Tests for lab creation."""

    @pytest.mark.asyncio
    async def test_create_lab_insufficient_karma(self):
        """Should reject lab creation with insufficient karma."""
        from platform.labs.service import LabService

        session = AsyncMock()
        service = LabService(session)

        # Mock repo methods
        service.lab_repo = MagicMock()
        service.lab_repo.slug_exists = AsyncMock(return_value=False)
        service.lab_repo.count_by_creator = AsyncMock(return_value=0)

        with pytest.raises(InsufficientKarmaError):
            await service.create_lab(
                agent_id=str(uuid4()),
                slug="test-lab",
                name="Test Lab",
                agent_karma=10,  # Below default 50
            )

    @pytest.mark.asyncio
    async def test_create_lab_slug_conflict(self):
        """Should reject duplicate slugs."""
        from platform.labs.service import LabService

        session = AsyncMock()
        service = LabService(session)
        service.lab_repo = MagicMock()
        service.lab_repo.slug_exists = AsyncMock(return_value=True)

        with pytest.raises(LabSlugConflictError):
            await service.create_lab(
                agent_id=str(uuid4()),
                slug="existing-lab",
                name="Existing Lab",
                agent_karma=100,
            )

    @pytest.mark.asyncio
    async def test_create_lab_max_pi_labs(self):
        """Should reject when agent has too many PI labs."""
        from platform.labs.service import LabService

        session = AsyncMock()
        service = LabService(session)
        service.lab_repo = MagicMock()
        service.lab_repo.slug_exists = AsyncMock(return_value=False)
        service.lab_repo.count_by_creator = AsyncMock(return_value=5)  # At max

        with pytest.raises(MaxLabsExceededError):
            await service.create_lab(
                agent_id=str(uuid4()),
                slug="new-lab",
                name="New Lab",
                agent_karma=100,
            )

    @pytest.mark.asyncio
    async def test_create_lab_success(self):
        """Should create lab with default role cards and PI membership."""
        from platform.labs.service import LabService

        session = AsyncMock()
        service = LabService(session)

        agent_id = str(uuid4())
        lab_id = uuid4()

        # Mock lab model
        mock_lab = MagicMock()
        mock_lab.id = lab_id
        mock_lab.slug = "test-lab"
        mock_lab.name = "Test Lab"
        mock_lab.description = None
        mock_lab.governance_type = "democratic"
        mock_lab.domains = ["mathematics"]
        mock_lab.rules = {}
        mock_lab.visibility = "public"
        mock_lab.karma_requirement = 0
        mock_lab.created_by = agent_id
        mock_lab.created_at = MagicMock()
        mock_lab.updated_at = MagicMock()
        mock_lab.archived_at = None
        mock_lab.memberships = []

        # Mock repos
        service.lab_repo = MagicMock()
        service.lab_repo.slug_exists = AsyncMock(return_value=False)
        service.lab_repo.count_by_creator = AsyncMock(return_value=0)
        service.lab_repo.create = AsyncMock(return_value=mock_lab)

        mock_role = MagicMock()
        mock_role.id = uuid4()
        mock_role.archetype = "pi"
        service.role_card_repo = MagicMock()
        service.role_card_repo.create = AsyncMock(return_value=mock_role)

        service.membership_repo = MagicMock()
        service.membership_repo.create = AsyncMock()

        service.workspace_repo = MagicMock()
        service.workspace_repo.upsert = AsyncMock()

        result = await service.create_lab(
            agent_id=agent_id,
            slug="test-lab",
            name="Test Lab",
            domains=["mathematics"],
            agent_karma=100,
        )

        assert result["slug"] == "test-lab"
        assert service.role_card_repo.create.call_count == 9  # 9 archetypes
        service.membership_repo.create.assert_called_once()


class TestLabServiceJoinLab:
    """Tests for joining labs."""

    @pytest.mark.asyncio
    async def test_join_lab_not_found(self):
        """Should raise when lab doesn't exist."""
        from platform.labs.service import LabService

        session = AsyncMock()
        service = LabService(session)
        service.lab_repo = MagicMock()
        service.lab_repo.get_by_slug = AsyncMock(return_value=None)

        with pytest.raises(LabNotFoundError):
            await service.join_lab("nonexistent", str(uuid4()))

    @pytest.mark.asyncio
    async def test_join_archived_lab(self):
        """Should reject joining an archived lab."""
        from platform.labs.service import LabService

        session = AsyncMock()
        service = LabService(session)

        mock_lab = MagicMock()
        mock_lab.archived_at = MagicMock()  # Non-None = archived
        mock_lab.slug = "archived-lab"

        service.lab_repo = MagicMock()
        service.lab_repo.get_by_slug = AsyncMock(return_value=mock_lab)

        with pytest.raises(LabArchivedError):
            await service.join_lab("archived-lab", str(uuid4()))

    @pytest.mark.asyncio
    async def test_join_lab_karma_too_low(self):
        """Should reject when agent karma is below requirement."""
        from platform.labs.service import LabService

        session = AsyncMock()
        service = LabService(session)

        mock_lab = MagicMock()
        mock_lab.archived_at = None
        mock_lab.karma_requirement = 100
        mock_lab.slug = "elite-lab"

        service.lab_repo = MagicMock()
        service.lab_repo.get_by_slug = AsyncMock(return_value=mock_lab)

        with pytest.raises(InsufficientKarmaError):
            await service.join_lab("elite-lab", str(uuid4()), agent_karma=50)

    @pytest.mark.asyncio
    async def test_join_lab_already_member(self):
        """Should reject when already an active member."""
        from platform.labs.service import LabService

        session = AsyncMock()
        service = LabService(session)

        mock_lab = MagicMock()
        mock_lab.archived_at = None
        mock_lab.karma_requirement = 0
        mock_lab.id = uuid4()

        service.lab_repo = MagicMock()
        service.lab_repo.get_by_slug = AsyncMock(return_value=mock_lab)

        mock_membership = MagicMock()
        mock_membership.status = "active"
        service.membership_repo = MagicMock()
        service.membership_repo.get = AsyncMock(return_value=mock_membership)

        with pytest.raises(LabMembershipError, match="Already a member"):
            await service.join_lab("test-lab", str(uuid4()))


class TestLabServiceMembership:
    """Tests for membership operations."""

    @pytest.mark.asyncio
    async def test_leave_lab_pi_cannot_leave(self):
        """PI cannot leave their own lab."""
        from platform.labs.service import LabService

        session = AsyncMock()
        service = LabService(session)

        agent_id = str(uuid4())
        mock_lab = MagicMock()
        mock_lab.created_by = agent_id

        service.lab_repo = MagicMock()
        service.lab_repo.get_by_slug = AsyncMock(return_value=mock_lab)

        with pytest.raises(LabMembershipError, match="PI cannot leave"):
            await service.leave_lab("test-lab", agent_id)
