"""Main Research Orchestration Service."""

from datetime import datetime
from typing import Any

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
from platform.orchestration.claim_router import ClaimRouter, get_claim_router
from platform.orchestration.config import (
    RESEARCH_DOMAINS,
    WORKFLOW_TEMPLATES,
    get_settings,
)
from platform.orchestration.session_manager import SessionManager, get_session_manager
from platform.orchestration.task_scheduler import TaskScheduler, get_task_scheduler
from platform.orchestration.workflow_engine import WorkflowEngine, get_workflow_engine
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class OrchestrationService:
    """
    Main service for research orchestration.

    Coordinates:
    - Research request processing
    - Workflow creation and management
    - Claim routing to verification engines
    - Result aggregation
    - Session management
    """

    def __init__(
        self,
        workflow_engine: WorkflowEngine | None = None,
        claim_router: ClaimRouter | None = None,
        task_scheduler: TaskScheduler | None = None,
        session_manager: SessionManager | None = None,
    ):
        """
        Initialize orchestration service.

        Args:
            workflow_engine: Workflow engine instance
            claim_router: Claim router instance
            task_scheduler: Task scheduler instance
            session_manager: Session manager instance
        """
        self._workflow_engine = workflow_engine or get_workflow_engine()
        self._claim_router = claim_router or get_claim_router()
        self._task_scheduler = task_scheduler or get_task_scheduler()
        self._session_manager = session_manager or get_session_manager()

    async def submit_research_request(
        self,
        request: ResearchRequest,
    ) -> ResearchResponse:
        """
        Submit a research request for processing.

        Args:
            request: Research request

        Returns:
            Initial response with workflow ID
        """
        logger.info(
            "research_request_received",
            request_id=request.request_id,
            request_type=request.request_type,
            num_claims=len(request.claims),
        )

        # Determine workflow template
        template = self._get_template_for_request(request)

        # Create workflow
        workflow = await self._workflow_engine.create_workflow(
            template_name=template,
            name=request.title or f"Research: {request.request_type}",
            description=request.description,
            claims=request.claims,
            context=request.context,
            owner_agent_id=request.requester_agent_id,
            priority=request.priority,
        )

        # If no claims provided, try to extract from description
        if not workflow.claims and request.description:
            extracted = await self._claim_router.extract_claims(
                request.description,
                source=request.request_id,
            )
            workflow.claims.extend(extracted)

        # Start workflow
        await self._workflow_engine.start_workflow(workflow.workflow_id)

        # Create initial response
        response = ResearchResponse(
            request_id=request.request_id,
            workflow_id=workflow.workflow_id,
            status=workflow.status,
            message=f"Research workflow created with {len(workflow.steps)} steps",
            metadata={
                "template": template,
                "num_claims": len(workflow.claims),
            },
        )

        logger.info(
            "research_request_accepted",
            request_id=request.request_id,
            workflow_id=workflow.workflow_id,
        )

        return response

    async def process_claim(
        self,
        claim: Claim,
        workflow_id: str | None = None,
    ) -> ClaimVerificationResult:
        """
        Process a single claim.

        Args:
            claim: Claim to verify
            workflow_id: Optional workflow context

        Returns:
            Verification result
        """
        started_at = datetime.utcnow()

        # Route the claim
        routing = await self._claim_router.route_claim(claim)

        if routing.confidence < settings.min_routing_confidence:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                status=ClaimStatus.ERROR,
                verified=False,
                message=f"Unable to route claim with sufficient confidence ({routing.confidence:.2f})",
                domain=routing.domain,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        # Dispatch to verification engine via Celery
        from celery import current_app

        task_name = f"verify.{routing.domain.replace('_', '')}.claim"

        # Build payload
        payload = {
            "claim_type": claim.claim_type,
            "content": claim.content,
            **claim.metadata,
        }

        try:
            # Send to appropriate queue
            result = current_app.send_task(
                task_name,
                args=[claim.claim_id, payload],
                kwargs={"job_id": workflow_id},
                queue=routing.celery_queue,
            )

            # For async processing, return pending status
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                status=ClaimStatus.VERIFYING,
                verified=False,
                message=f"Claim submitted to {routing.verification_engine}",
                verifier=routing.verification_engine,
                domain=routing.domain,
                confidence=routing.confidence,
                started_at=started_at,
            )

        except Exception as e:
            logger.exception("claim_dispatch_error", claim_id=claim.claim_id)
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                status=ClaimStatus.ERROR,
                verified=False,
                message=f"Failed to dispatch claim: {str(e)}",
                domain=routing.domain,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    async def process_workflow_claims(
        self,
        workflow_id: str,
    ) -> list[ClaimVerificationResult]:
        """
        Process all claims in a workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            List of verification results
        """
        workflow = self._workflow_engine.get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")

        results = []
        for claim in workflow.claims:
            result = await self.process_claim(claim, workflow_id)
            results.append(result)

            # Add to workflow results
            await self._workflow_engine.add_claim_result(workflow_id, result)

        return results

    async def handle_verification_result(
        self,
        workflow_id: str,
        claim_id: str,
        result: dict[str, Any],
    ) -> None:
        """
        Handle a verification result from a verification engine.

        Args:
            workflow_id: Workflow ID
            claim_id: Claim ID
            result: Verification result dict
        """
        # Parse result
        verification_result = ClaimVerificationResult(
            claim_id=claim_id,
            status=ClaimStatus(result.get("status", "error")),
            verified=result.get("verified", False),
            message=result.get("message", ""),
            verifier=result.get("verifier", ""),
            domain=result.get("domain", ""),
            confidence=result.get("confidence", 0.0),
            evidence=result.get("evidence", []),
            details=result.get("details", {}),
            completed_at=datetime.utcnow(),
        )

        # Update workflow
        await self._workflow_engine.add_claim_result(workflow_id, verification_result)

        # Check if all claims are processed
        workflow = self._workflow_engine.get_workflow(workflow_id)
        if workflow:
            pending_claims = [
                c for c in workflow.claims
                if not any(r.claim_id == c.claim_id and r.status != ClaimStatus.VERIFYING for r in workflow.results)
            ]

            if not pending_claims:
                # All claims processed, advance workflow
                await self._workflow_engine.advance_workflow(workflow_id)

        logger.info(
            "verification_result_handled",
            workflow_id=workflow_id,
            claim_id=claim_id,
            verified=verification_result.verified,
        )

    async def get_workflow_status(
        self,
        workflow_id: str,
    ) -> dict[str, Any]:
        """
        Get workflow status.

        Args:
            workflow_id: Workflow ID

        Returns:
            Status dict
        """
        return self._workflow_engine.get_workflow_status(workflow_id)

    async def get_workflow_results(
        self,
        workflow_id: str,
    ) -> ResearchResponse | None:
        """
        Get final workflow results.

        Args:
            workflow_id: Workflow ID

        Returns:
            Research response or None
        """
        workflow = self._workflow_engine.get_workflow(workflow_id)
        if not workflow:
            return None

        # Generate summary
        summary = self._generate_summary(workflow)

        # Calculate confidence
        if workflow.results:
            confidence = sum(r.confidence for r in workflow.results) / len(workflow.results)
        else:
            confidence = 0.0

        return ResearchResponse(
            request_id=workflow.metadata.get("request_id", ""),
            workflow_id=workflow.workflow_id,
            status=workflow.status,
            message=self._get_status_message(workflow),
            results=workflow.results,
            summary=summary,
            confidence=confidence,
            metadata={
                "template": workflow.template,
                "progress_percent": workflow.progress_percent,
                "execution_time_seconds": workflow.execution_time_seconds,
            },
            created_at=workflow.created_at,
            completed_at=workflow.completed_at,
        )

    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a workflow."""
        workflow = await self._workflow_engine.cancel_workflow(workflow_id)
        return workflow.status == WorkflowStatus.CANCELLED

    async def pause_workflow(self, workflow_id: str) -> bool:
        """Pause a workflow."""
        workflow = await self._workflow_engine.pause_workflow(workflow_id)
        return workflow.status == WorkflowStatus.PAUSED

    async def resume_workflow(self, workflow_id: str) -> bool:
        """Resume a paused workflow."""
        workflow = await self._workflow_engine.resume_workflow(workflow_id)
        return workflow.status == WorkflowStatus.RUNNING

    def _get_template_for_request(self, request: ResearchRequest) -> str:
        """Determine workflow template for request."""
        request_type = request.request_type.lower()

        # Direct mapping
        if request_type in WORKFLOW_TEMPLATES:
            return request_type

        # Keyword-based mapping
        type_mapping = {
            "verify": "claim_verification",
            "hypothesis": "hypothesis_verification",
            "literature": "literature_review",
            "reproduce": "experiment_reproduction",
            "multi": "multi_domain_research",
        }

        for keyword, template in type_mapping.items():
            if keyword in request_type:
                return template

        # Default to single claim verification if claims exist
        if request.claims:
            return "claim_verification"

        return "hypothesis_verification"

    def _generate_summary(self, workflow: ResearchWorkflow) -> str:
        """Generate summary of workflow results."""
        if not workflow.results:
            return "No verification results available."

        verified = sum(1 for r in workflow.results if r.verified)
        refuted = sum(1 for r in workflow.results if r.status == ClaimStatus.REFUTED)
        inconclusive = sum(1 for r in workflow.results if r.status == ClaimStatus.INCONCLUSIVE)
        total = len(workflow.results)

        summary_parts = [
            f"Processed {total} claims:",
            f"- {verified} verified",
            f"- {refuted} refuted",
        ]

        if inconclusive:
            summary_parts.append(f"- {inconclusive} inconclusive")

        if workflow.status == WorkflowStatus.COMPLETED:
            if verified == total:
                summary_parts.append("\nAll claims were successfully verified.")
            elif refuted == total:
                summary_parts.append("\nAll claims were refuted.")
            else:
                summary_parts.append("\nResults are mixed.")

        return "\n".join(summary_parts)

    def _get_status_message(self, workflow: ResearchWorkflow) -> str:
        """Get human-readable status message."""
        status_messages = {
            WorkflowStatus.PENDING: "Workflow is pending execution",
            WorkflowStatus.RUNNING: f"Workflow is running ({workflow.progress_percent:.0f}% complete)",
            WorkflowStatus.PAUSED: "Workflow is paused",
            WorkflowStatus.COMPLETED: "Workflow completed successfully",
            WorkflowStatus.FAILED: f"Workflow failed: {workflow.error_message or 'Unknown error'}",
            WorkflowStatus.CANCELLED: "Workflow was cancelled",
            WorkflowStatus.TIMEOUT: "Workflow timed out",
        }
        return status_messages.get(workflow.status, "Unknown status")

    def get_available_templates(self) -> list[dict[str, Any]]:
        """Get available workflow templates."""
        return self._workflow_engine.get_templates()

    def get_available_domains(self) -> list[dict[str, Any]]:
        """Get available research domains."""
        return self._claim_router.get_all_domains()


# Singleton instance
_service_instance: OrchestrationService | None = None


def get_orchestration_service() -> OrchestrationService:
    """Get singleton OrchestrationService instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = OrchestrationService()
    return _service_instance
