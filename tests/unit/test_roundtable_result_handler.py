"""Tests for RoundtableResultHandler."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestHandleMessage:
    """Test the _handle_message method."""

    @pytest.mark.asyncio
    async def test_verified_claim_transitions_item(self):
        """Verified claim should transition item to verified."""
        from platform.labs.roundtable_result_handler import RoundtableResultHandler

        handler = RoundtableResultHandler()
        session = AsyncMock()

        claim_id = uuid4()
        item = MagicMock()
        item.id = uuid4()
        item.lab_id = uuid4()
        item.status = "submitted"
        item.proposed_by = uuid4()

        # Mock the query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = item
        session.execute = AsyncMock(return_value=mock_result)

        message = {
            "data": {
                "claim_id": str(claim_id),
                "status": "verified",
            }
        }

        with patch("platform.labs.roundtable_result_handler.ResearchItemRepository") as MockRepo, \
             patch("platform.labs.roundtable_result_handler.RoundtableRepository"), \
             patch("platform.labs.roundtable_result_handler.KafkaProducer"), \
             patch("platform.labs.roundtable_result_handler.RoundtableService") as MockService:
            mock_repo = MockRepo.return_value
            mock_repo.update = AsyncMock(return_value=item)
            mock_service = MockService.return_value
            mock_service._distribute_karma = AsyncMock(return_value={})

            await handler._handle_message(message, session)

            # Should have updated status (at least once for under_review, once for verified)
            assert mock_repo.update.call_count >= 1

    @pytest.mark.asyncio
    async def test_failed_claim_routes_back_to_debate(self):
        """Failed claim should route item back to under_debate."""
        from platform.labs.roundtable_result_handler import RoundtableResultHandler

        handler = RoundtableResultHandler()
        session = AsyncMock()

        claim_id = uuid4()
        item = MagicMock()
        item.id = uuid4()
        item.lab_id = uuid4()
        item.status = "submitted"
        item.proposed_by = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = item
        session.execute = AsyncMock(return_value=mock_result)

        message = {
            "data": {
                "claim_id": str(claim_id),
                "status": "failed",
                "reason": "proof invalid",
            }
        }

        with patch("platform.labs.roundtable_result_handler.ResearchItemRepository") as MockRepo, \
             patch("platform.labs.roundtable_result_handler.RoundtableRepository") as MockRtRepo, \
             patch("platform.labs.roundtable_result_handler.KafkaProducer"):
            mock_repo = MockRepo.return_value
            mock_repo.update = AsyncMock(return_value=item)
            mock_rt_repo = MockRtRepo.return_value
            mock_rt_repo.create = AsyncMock()

            await handler._handle_message(message, session)

            mock_rt_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_lab_claim_skipped(self):
        """Claims not linked to a research item should be skipped."""
        from platform.labs.roundtable_result_handler import RoundtableResultHandler

        handler = RoundtableResultHandler()
        session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        message = {
            "data": {
                "claim_id": str(uuid4()),
                "status": "verified",
            }
        }

        # Should not raise
        await handler._handle_message(message, session)

    @pytest.mark.asyncio
    async def test_missing_claim_id_skipped(self):
        """Messages without claim_id should be skipped."""
        from platform.labs.roundtable_result_handler import RoundtableResultHandler

        handler = RoundtableResultHandler()
        session = AsyncMock()

        message = {"data": {}}

        await handler._handle_message(message, session)
        session.execute.assert_not_called()
