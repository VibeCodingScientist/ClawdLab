"""Integration tests for Lab API endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


class TestLabAPIWorkflow:
    """Integration tests for the complete lab workflow."""

    @pytest.mark.asyncio
    async def test_create_lab_request_validation(self):
        """CreateLabRequest should validate fields."""
        from platform.labs.schemas import CreateLabRequest

        # Valid request
        req = CreateLabRequest(
            slug="my-lab",
            name="My Lab",
            description="A test lab",
            governance_type="democratic",
            domains=["mathematics"],
        )
        assert req.slug == "my-lab"
        assert req.governance_type == "democratic"

    @pytest.mark.asyncio
    async def test_create_lab_invalid_slug(self):
        """Should reject invalid slugs."""
        from pydantic import ValidationError
        from platform.labs.schemas import CreateLabRequest

        with pytest.raises(ValidationError):
            CreateLabRequest(
                slug="INVALID SLUG!!!",
                name="Bad Lab",
            )

    @pytest.mark.asyncio
    async def test_create_lab_invalid_governance(self):
        """Should reject invalid governance type."""
        from pydantic import ValidationError
        from platform.labs.schemas import CreateLabRequest

        with pytest.raises(ValidationError):
            CreateLabRequest(
                slug="my-lab",
                name="My Lab",
                governance_type="anarchy",
            )

    @pytest.mark.asyncio
    async def test_create_lab_invalid_domain(self):
        """Should reject invalid domains."""
        from pydantic import ValidationError
        from platform.labs.schemas import CreateLabRequest

        with pytest.raises(ValidationError):
            CreateLabRequest(
                slug="my-lab",
                name="My Lab",
                domains=["quantum_computing"],
            )

    @pytest.mark.asyncio
    async def test_join_lab_request(self):
        """JoinLabRequest should accept optional archetype."""
        from platform.labs.schemas import JoinLabRequest

        req = JoinLabRequest(preferred_archetype="theorist")
        assert req.preferred_archetype == "theorist"

        req2 = JoinLabRequest()
        assert req2.preferred_archetype is None

    @pytest.mark.asyncio
    async def test_propose_research_item_validation(self):
        """ProposeResearchItemRequest should validate fields."""
        from platform.labs.schemas import ProposeResearchItemRequest

        req = ProposeResearchItemRequest(
            title="Test Research Item",
            description="Testing the research item proposal",
            domain="mathematics",
            claim_type="theorem",
        )
        assert req.domain == "mathematics"

    @pytest.mark.asyncio
    async def test_vote_request_validation(self):
        """VoteRequest should validate vote_value range."""
        from platform.labs.schemas import VoteRequest

        req = VoteRequest(vote_value=1)
        assert req.vote_value == 1

        req = VoteRequest(vote_value=-1)
        assert req.vote_value == -1

        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            VoteRequest(vote_value=2)

    @pytest.mark.asyncio
    async def test_roundtable_entry_type_validation(self):
        """RoundtableContributionRequest should validate entry types."""
        from platform.labs.schemas import RoundtableContributionRequest

        req = RoundtableContributionRequest(
            entry_type="argument",
            content="This is my argument.",
        )
        assert req.entry_type == "argument"

        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RoundtableContributionRequest(
                entry_type="invalid_type",
                content="Bad type.",
            )

    @pytest.mark.asyncio
    async def test_workspace_zone_validation(self):
        """UpdateWorkspaceRequest should validate zones."""
        from platform.labs.schemas import UpdateWorkspaceRequest

        req = UpdateWorkspaceRequest(zone="bench")
        assert req.zone == "bench"

        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            UpdateWorkspaceRequest(zone="invalid_zone")

    @pytest.mark.asyncio
    async def test_exception_to_http(self):
        """LabServiceError should convert to proper HTTP responses."""
        from platform.labs.exceptions import (
            LabNotFoundError,
            LabSlugConflictError,
            InsufficientKarmaError,
            raise_http_exception,
        )
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            raise_http_exception(LabNotFoundError("test"))
        assert exc_info.value.status_code == 404

        with pytest.raises(HTTPException) as exc_info:
            raise_http_exception(LabSlugConflictError("test"))
        assert exc_info.value.status_code == 409

        with pytest.raises(HTTPException) as exc_info:
            raise_http_exception(InsufficientKarmaError(100, 50))
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_role_card_archetype_validation(self):
        """CreateRoleCardRequest should validate archetypes."""
        from platform.labs.schemas import CreateRoleCardRequest

        req = CreateRoleCardRequest(
            archetype="critic",
            pipeline_layer="verification",
        )
        assert req.archetype == "critic"

        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            CreateRoleCardRequest(
                archetype="invalid_role",
                pipeline_layer="verification",
            )

    @pytest.mark.asyncio
    async def test_status_update_validation(self):
        """UpdateResearchItemStatusRequest should validate statuses."""
        from platform.labs.schemas import UpdateResearchItemStatusRequest

        req = UpdateResearchItemStatusRequest(status="approved")
        assert req.status == "approved"

        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            UpdateResearchItemStatusRequest(status="invalid_status")
