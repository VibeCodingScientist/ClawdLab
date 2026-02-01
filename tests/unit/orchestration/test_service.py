"""Unit tests for OrchestrationService."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from platform.orchestration.service import OrchestrationService
from platform.orchestration.base import (
    Claim,
    ClaimStatus,
    ClaimVerificationResult,
    Priority,
    ResearchRequest,
    ResearchResponse,
    ResearchWorkflow,
    WorkflowStatus,
)


class TestOrchestrationService:
    """Tests for OrchestrationService class."""

    @pytest.fixture
    def mock_workflow_engine(self) -> AsyncMock:
        """Create mock workflow engine."""
        mock = AsyncMock()

        # Create a mock workflow
        workflow = ResearchWorkflow(
            workflow_id="workflow-123",
            name="Test Workflow",
            status=WorkflowStatus.PENDING,
            template="claim_verification",
            steps=[
                MagicMock(step_id="step-1", name="Verify Claims"),
                MagicMock(step_id="step-2", name="Aggregate Results"),
            ],
            claims=[],
            results=[],
            metadata={},
            progress_percent=0.0,
            execution_time_seconds=0.0,
        )

        mock.create_workflow.return_value = workflow
        mock.start_workflow.return_value = workflow
        mock.get_workflow.return_value = workflow
        mock.get_workflow_status.return_value = {
            "workflow_id": "workflow-123",
            "status": "pending",
            "progress": 0.0,
        }
        mock.advance_workflow.return_value = workflow
        mock.add_claim_result.return_value = None
        mock.cancel_workflow.return_value = ResearchWorkflow(
            workflow_id="workflow-123", status=WorkflowStatus.CANCELLED
        )
        mock.pause_workflow.return_value = ResearchWorkflow(
            workflow_id="workflow-123", status=WorkflowStatus.PAUSED
        )
        mock.resume_workflow.return_value = ResearchWorkflow(
            workflow_id="workflow-123", status=WorkflowStatus.RUNNING
        )
        mock.get_templates.return_value = [
            {"name": "claim_verification", "steps": 3},
            {"name": "hypothesis_verification", "steps": 5},
        ]
        return mock

    @pytest.fixture
    def mock_claim_router(self) -> AsyncMock:
        """Create mock claim router."""
        mock = AsyncMock()
        mock.route_claim.return_value = MagicMock(
            domain="ml_ai",
            verification_engine="ml_verifier",
            celery_queue="verification.ml",
            confidence=0.95,
        )
        mock.extract_claims.return_value = [
            Claim(claim_id="claim-1", content="Test claim 1", claim_type="empirical"),
        ]
        mock.get_all_domains.return_value = [
            {"name": "ml_ai", "description": "ML/AI domain"},
            {"name": "mathematics", "description": "Mathematics domain"},
        ]
        return mock

    @pytest.fixture
    def mock_task_scheduler(self) -> AsyncMock:
        """Create mock task scheduler."""
        return AsyncMock()

    @pytest.fixture
    def mock_session_manager(self) -> AsyncMock:
        """Create mock session manager."""
        return AsyncMock()

    @pytest.fixture
    def service(
        self,
        mock_workflow_engine,
        mock_claim_router,
        mock_task_scheduler,
        mock_session_manager,
    ) -> OrchestrationService:
        """Create service with mocked dependencies."""
        return OrchestrationService(
            workflow_engine=mock_workflow_engine,
            claim_router=mock_claim_router,
            task_scheduler=mock_task_scheduler,
            session_manager=mock_session_manager,
        )

    # ===================================
    # RESEARCH REQUEST TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_submit_research_request(
        self,
        service: OrchestrationService,
        mock_workflow_engine: AsyncMock,
    ):
        """Test submitting a research request."""
        request = ResearchRequest(
            request_id="req-123",
            request_type="claim_verification",
            title="Test Research",
            description="Testing claims",
            claims=[
                Claim(claim_id="claim-1", content="Test claim", claim_type="empirical"),
            ],
            requester_agent_id="agent-1",
            priority=Priority.HIGH,
        )

        response = await service.submit_research_request(request)

        assert response is not None
        assert response.request_id == "req-123"
        assert response.workflow_id == "workflow-123"
        mock_workflow_engine.create_workflow.assert_called_once()
        mock_workflow_engine.start_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_research_request_extracts_claims(
        self,
        service: OrchestrationService,
        mock_workflow_engine: AsyncMock,
        mock_claim_router: AsyncMock,
    ):
        """Test that claims are extracted from description if not provided."""
        # Make workflow have no claims initially
        mock_workflow_engine.create_workflow.return_value = ResearchWorkflow(
            workflow_id="workflow-123",
            name="Test Workflow",
            status=WorkflowStatus.PENDING,
            template="claim_verification",
            claims=[],  # No claims
        )

        request = ResearchRequest(
            request_id="req-123",
            request_type="claim_verification",
            title="Test Research",
            description="This is a testable claim about ML performance",
            claims=[],  # No claims provided
            requester_agent_id="agent-1",
        )

        await service.submit_research_request(request)

        mock_claim_router.extract_claims.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_research_request_determines_template(
        self,
        service: OrchestrationService,
    ):
        """Test workflow template determination."""
        # Test verify request type
        request = ResearchRequest(
            request_id="req-1",
            request_type="verify_claims",
            claims=[Claim(claim_id="c1", content="Test")],
        )
        template = service._get_template_for_request(request)
        assert template == "claim_verification"

        # Test hypothesis request type
        request = ResearchRequest(
            request_id="req-2",
            request_type="hypothesis_testing",
        )
        template = service._get_template_for_request(request)
        assert template == "hypothesis_verification"

        # Test literature request type
        request = ResearchRequest(
            request_id="req-3",
            request_type="literature_review",
        )
        template = service._get_template_for_request(request)
        assert template == "literature_review"

    # ===================================
    # CLAIM PROCESSING TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_process_claim_success(
        self,
        service: OrchestrationService,
        mock_claim_router: AsyncMock,
    ):
        """Test processing a single claim successfully."""
        claim = Claim(
            claim_id="claim-123",
            content="Test claim content",
            claim_type="empirical",
        )

        # Mock Celery
        with patch("platform.orchestration.service.current_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id="task-123")

            result = await service.process_claim(claim, workflow_id="workflow-123")

            assert result is not None
            assert result.claim_id == "claim-123"
            assert result.status == ClaimStatus.VERIFYING
            mock_claim_router.route_claim.assert_called_once_with(claim)

    @pytest.mark.asyncio
    async def test_process_claim_low_routing_confidence(
        self,
        service: OrchestrationService,
        mock_claim_router: AsyncMock,
    ):
        """Test claim processing with low routing confidence."""
        mock_claim_router.route_claim.return_value = MagicMock(
            domain="unknown",
            confidence=0.3,  # Below threshold
        )

        # Set minimum confidence threshold
        with patch("platform.orchestration.service.settings") as mock_settings:
            mock_settings.min_routing_confidence = 0.5

            claim = Claim(claim_id="claim-123", content="Unclear claim")

            result = await service.process_claim(claim)

            assert result.status == ClaimStatus.ERROR
            assert "confidence" in result.message.lower()

    @pytest.mark.asyncio
    async def test_process_claim_dispatch_error(
        self,
        service: OrchestrationService,
        mock_claim_router: AsyncMock,
    ):
        """Test claim processing with dispatch error."""
        claim = Claim(claim_id="claim-123", content="Test claim")

        with patch("platform.orchestration.service.current_app") as mock_celery:
            mock_celery.send_task.side_effect = Exception("Celery error")

            result = await service.process_claim(claim)

            assert result.status == ClaimStatus.ERROR
            assert "dispatch" in result.message.lower()

    @pytest.mark.asyncio
    async def test_process_workflow_claims(
        self,
        service: OrchestrationService,
        mock_workflow_engine: AsyncMock,
    ):
        """Test processing all claims in a workflow."""
        # Setup workflow with claims
        workflow = ResearchWorkflow(
            workflow_id="workflow-123",
            claims=[
                Claim(claim_id="claim-1", content="Claim 1"),
                Claim(claim_id="claim-2", content="Claim 2"),
            ],
        )
        mock_workflow_engine.get_workflow.return_value = workflow

        with patch("platform.orchestration.service.current_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id="task-123")

            results = await service.process_workflow_claims("workflow-123")

            assert len(results) == 2
            assert mock_workflow_engine.add_claim_result.call_count == 2

    @pytest.mark.asyncio
    async def test_process_workflow_claims_not_found(
        self,
        service: OrchestrationService,
        mock_workflow_engine: AsyncMock,
    ):
        """Test processing claims for non-existent workflow."""
        mock_workflow_engine.get_workflow.return_value = None

        with pytest.raises(ValueError, match="Workflow not found"):
            await service.process_workflow_claims("non-existent")

    # ===================================
    # VERIFICATION RESULT HANDLING TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_handle_verification_result(
        self,
        service: OrchestrationService,
        mock_workflow_engine: AsyncMock,
    ):
        """Test handling a verification result."""
        # Setup workflow with one claim and one pending result
        workflow = ResearchWorkflow(
            workflow_id="workflow-123",
            claims=[Claim(claim_id="claim-1", content="Test claim")],
            results=[],
        )
        mock_workflow_engine.get_workflow.return_value = workflow

        result_data = {
            "status": "verified",
            "verified": True,
            "message": "Claim verified",
            "verifier": "ml_verifier",
            "domain": "ml_ai",
            "confidence": 0.95,
            "evidence": ["evidence-1"],
        }

        await service.handle_verification_result(
            workflow_id="workflow-123",
            claim_id="claim-1",
            result=result_data,
        )

        mock_workflow_engine.add_claim_result.assert_called_once()
        # Should advance workflow since all claims are processed
        mock_workflow_engine.advance_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_verification_result_pending_claims(
        self,
        service: OrchestrationService,
        mock_workflow_engine: AsyncMock,
    ):
        """Test that workflow doesn't advance with pending claims."""
        # Setup workflow with multiple claims
        workflow = ResearchWorkflow(
            workflow_id="workflow-123",
            claims=[
                Claim(claim_id="claim-1", content="Claim 1"),
                Claim(claim_id="claim-2", content="Claim 2"),  # Still pending
            ],
            results=[],
        )
        mock_workflow_engine.get_workflow.return_value = workflow

        result_data = {"status": "verified", "verified": True}

        await service.handle_verification_result(
            workflow_id="workflow-123",
            claim_id="claim-1",
            result=result_data,
        )

        # Should not advance with pending claims
        mock_workflow_engine.advance_workflow.assert_not_called()

    # ===================================
    # WORKFLOW STATUS TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_get_workflow_status(
        self,
        service: OrchestrationService,
        mock_workflow_engine: AsyncMock,
    ):
        """Test getting workflow status."""
        status = await service.get_workflow_status("workflow-123")

        assert status is not None
        assert status["workflow_id"] == "workflow-123"
        mock_workflow_engine.get_workflow_status.assert_called_once_with("workflow-123")

    @pytest.mark.asyncio
    async def test_get_workflow_results(
        self,
        service: OrchestrationService,
        mock_workflow_engine: AsyncMock,
    ):
        """Test getting workflow results."""
        # Setup completed workflow
        workflow = ResearchWorkflow(
            workflow_id="workflow-123",
            name="Test Workflow",
            status=WorkflowStatus.COMPLETED,
            template="claim_verification",
            claims=[Claim(claim_id="claim-1", content="Test")],
            results=[
                ClaimVerificationResult(
                    claim_id="claim-1",
                    status=ClaimStatus.VERIFIED,
                    verified=True,
                    confidence=0.95,
                )
            ],
            progress_percent=100.0,
            execution_time_seconds=30.0,
            metadata={"request_id": "req-123"},
        )
        mock_workflow_engine.get_workflow.return_value = workflow

        response = await service.get_workflow_results("workflow-123")

        assert response is not None
        assert response.workflow_id == "workflow-123"
        assert response.status == WorkflowStatus.COMPLETED
        assert len(response.results) == 1
        assert response.confidence == 0.95

    @pytest.mark.asyncio
    async def test_get_workflow_results_not_found(
        self,
        service: OrchestrationService,
        mock_workflow_engine: AsyncMock,
    ):
        """Test getting results for non-existent workflow."""
        mock_workflow_engine.get_workflow.return_value = None

        response = await service.get_workflow_results("non-existent")

        assert response is None

    # ===================================
    # WORKFLOW CONTROL TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_cancel_workflow(
        self,
        service: OrchestrationService,
        mock_workflow_engine: AsyncMock,
    ):
        """Test cancelling a workflow."""
        result = await service.cancel_workflow("workflow-123")

        assert result is True
        mock_workflow_engine.cancel_workflow.assert_called_once_with("workflow-123")

    @pytest.mark.asyncio
    async def test_pause_workflow(
        self,
        service: OrchestrationService,
        mock_workflow_engine: AsyncMock,
    ):
        """Test pausing a workflow."""
        result = await service.pause_workflow("workflow-123")

        assert result is True
        mock_workflow_engine.pause_workflow.assert_called_once_with("workflow-123")

    @pytest.mark.asyncio
    async def test_resume_workflow(
        self,
        service: OrchestrationService,
        mock_workflow_engine: AsyncMock,
    ):
        """Test resuming a workflow."""
        result = await service.resume_workflow("workflow-123")

        assert result is True
        mock_workflow_engine.resume_workflow.assert_called_once_with("workflow-123")

    # ===================================
    # SUMMARY GENERATION TESTS
    # ===================================

    def test_generate_summary_all_verified(self, service: OrchestrationService):
        """Test summary generation when all claims verified."""
        workflow = ResearchWorkflow(
            workflow_id="workflow-123",
            status=WorkflowStatus.COMPLETED,
            results=[
                ClaimVerificationResult(
                    claim_id="c1", status=ClaimStatus.VERIFIED, verified=True
                ),
                ClaimVerificationResult(
                    claim_id="c2", status=ClaimStatus.VERIFIED, verified=True
                ),
            ],
        )

        summary = service._generate_summary(workflow)

        assert "2 verified" in summary
        assert "successfully verified" in summary.lower()

    def test_generate_summary_mixed_results(self, service: OrchestrationService):
        """Test summary generation with mixed results."""
        workflow = ResearchWorkflow(
            workflow_id="workflow-123",
            status=WorkflowStatus.COMPLETED,
            results=[
                ClaimVerificationResult(
                    claim_id="c1", status=ClaimStatus.VERIFIED, verified=True
                ),
                ClaimVerificationResult(
                    claim_id="c2", status=ClaimStatus.REFUTED, verified=False
                ),
                ClaimVerificationResult(
                    claim_id="c3", status=ClaimStatus.INCONCLUSIVE, verified=False
                ),
            ],
        )

        summary = service._generate_summary(workflow)

        assert "1 verified" in summary
        assert "1 refuted" in summary
        assert "1 inconclusive" in summary
        assert "mixed" in summary.lower()

    def test_generate_summary_no_results(self, service: OrchestrationService):
        """Test summary generation with no results."""
        workflow = ResearchWorkflow(
            workflow_id="workflow-123",
            status=WorkflowStatus.RUNNING,
            results=[],
        )

        summary = service._generate_summary(workflow)

        assert "no verification results" in summary.lower()

    # ===================================
    # STATUS MESSAGE TESTS
    # ===================================

    def test_get_status_message(self, service: OrchestrationService):
        """Test status message generation."""
        workflow = ResearchWorkflow(
            workflow_id="workflow-123",
            status=WorkflowStatus.RUNNING,
            progress_percent=50.0,
        )

        message = service._get_status_message(workflow)

        assert "running" in message.lower()
        assert "50%" in message

    def test_get_status_message_failed(self, service: OrchestrationService):
        """Test status message for failed workflow."""
        workflow = ResearchWorkflow(
            workflow_id="workflow-123",
            status=WorkflowStatus.FAILED,
            error_message="Network timeout",
        )

        message = service._get_status_message(workflow)

        assert "failed" in message.lower()
        assert "Network timeout" in message

    # ===================================
    # UTILITY TESTS
    # ===================================

    def test_get_available_templates(
        self,
        service: OrchestrationService,
        mock_workflow_engine: AsyncMock,
    ):
        """Test getting available workflow templates."""
        templates = service.get_available_templates()

        assert len(templates) == 2
        mock_workflow_engine.get_templates.assert_called_once()

    def test_get_available_domains(
        self,
        service: OrchestrationService,
        mock_claim_router: AsyncMock,
    ):
        """Test getting available research domains."""
        domains = service.get_available_domains()

        assert len(domains) == 2
        mock_claim_router.get_all_domains.assert_called_once()
