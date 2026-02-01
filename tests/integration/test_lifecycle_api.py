"""Integration tests for Agent Lifecycle API endpoints and schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ===========================================
# CHECKPOINT SCHEMA TESTS
# ===========================================


class TestCheckpointSchemas:
    """Test CheckpointSummary and CheckpointDetailResponse schema validation."""

    def test_valid_checkpoint_summary(self):
        from platform.agents.lifecycle_schemas import CheckpointSummary

        cp_id = uuid4()
        now = _utc_now()

        summary = CheckpointSummary(
            id=cp_id,
            sequence_number=5,
            checkpoint_type="auto",
            research_state="experimenting",
            progress_pct=0.72,
            tokens_consumed=15000,
            is_latest=True,
            created_at=now,
        )
        assert summary.id == cp_id
        assert summary.sequence_number == 5
        assert summary.checkpoint_type == "auto"
        assert summary.research_state == "experimenting"
        assert summary.progress_pct == 0.72
        assert summary.tokens_consumed == 15000
        assert summary.is_latest is True
        assert summary.created_at == now

    def test_checkpoint_detail_with_data_dict(self):
        from platform.agents.lifecycle_schemas import CheckpointDetailResponse

        cp_id = uuid4()
        now = _utc_now()
        data = {"hypothesis": "test hypothesis", "findings": [1, 2, 3]}

        detail = CheckpointDetailResponse(
            id=cp_id,
            sequence_number=3,
            checkpoint_type="pre_park",
            research_state="parked",
            progress_pct=0.45,
            tokens_consumed=8000,
            is_latest=False,
            created_at=now,
            checkpoint_data=data,
        )
        assert detail.checkpoint_data == data
        assert detail.checkpoint_data["hypothesis"] == "test hypothesis"
        assert len(detail.checkpoint_data["findings"]) == 3

    def test_checkpoint_summary_serialization(self):
        from platform.agents.lifecycle_schemas import CheckpointSummary

        cp_id = uuid4()
        now = _utc_now()

        summary = CheckpointSummary(
            id=cp_id,
            sequence_number=1,
            checkpoint_type="manual",
            research_state="idle",
            progress_pct=0.0,
            tokens_consumed=0,
            is_latest=True,
            created_at=now,
        )
        data = summary.model_dump()
        assert data["id"] == cp_id
        assert data["sequence_number"] == 1
        assert data["checkpoint_type"] == "manual"
        assert data["research_state"] == "idle"
        assert data["progress_pct"] == 0.0
        assert data["tokens_consumed"] == 0
        assert data["is_latest"] is True


# ===========================================
# SPRINT SCHEMA TESTS
# ===========================================


class TestSprintSchemas:
    """Test SprintResponse, StartSprintRequest, and EndSprintRequest schemas."""

    def test_valid_sprint_response(self):
        from platform.agents.lifecycle_schemas import SprintResponse

        sprint_id = uuid4()
        agent_id = uuid4()
        lab_id = uuid4()
        now = _utc_now()

        sprint = SprintResponse(
            id=sprint_id,
            agent_id=agent_id,
            lab_id=lab_id,
            sprint_number=3,
            goal="Investigate convergence properties of novel optimizer",
            approach="grid search over hyperparameters",
            started_at=now,
            target_end_at=now,
            actual_end_at=None,
            status="active",
            outcome_type=None,
            outcome_summary=None,
            claims_submitted=2,
            findings_recorded=5,
            reviews_completed=1,
            hypotheses_active=3,
            tokens_consumed=42000,
            checkpoints_created=7,
            reviewed=False,
            review_verdict=None,
        )
        assert sprint.id == sprint_id
        assert sprint.agent_id == agent_id
        assert sprint.lab_id == lab_id
        assert sprint.sprint_number == 3
        assert sprint.status == "active"
        assert sprint.actual_end_at is None
        assert sprint.claims_submitted == 2
        assert sprint.reviewed is False
        assert sprint.review_verdict is None

    def test_start_sprint_request_minimal_fields(self):
        from platform.agents.lifecycle_schemas import StartSprintRequest

        req = StartSprintRequest(goal="Prove the Riemann hypothesis")
        assert req.goal == "Prove the Riemann hypothesis"
        assert req.approach is None
        assert req.duration_days is None
        assert req.domain is None

    def test_start_sprint_request_all_fields(self):
        from platform.agents.lifecycle_schemas import StartSprintRequest

        req = StartSprintRequest(
            goal="Benchmark transformer variants",
            approach="systematic ablation study",
            duration_days=14,
            domain="ml_ai",
        )
        assert req.goal == "Benchmark transformer variants"
        assert req.approach == "systematic ablation study"
        assert req.duration_days == 14
        assert req.domain == "ml_ai"

    def test_end_sprint_request(self):
        from platform.agents.lifecycle_schemas import EndSprintRequest

        req = EndSprintRequest(
            outcome_type="success",
            outcome_summary="Convergence proof completed with all lemmas verified.",
        )
        assert req.outcome_type == "success"
        assert req.outcome_summary == "Convergence proof completed with all lemmas verified."


# ===========================================
# HEARTBEAT SCHEMA TESTS
# ===========================================


class TestHeartbeatSchemas:
    """Test HeartbeatRequest, LivenessProbeData, ReadinessProbeData, ProgressProbeData."""

    def test_full_three_probe_heartbeat(self):
        from platform.agents.lifecycle_schemas import (
            HeartbeatRequest,
            LivenessProbeData,
            ProgressProbeData,
            ReadinessProbeData,
        )

        task_id = uuid4()
        blocked_id = uuid4()
        completion_time = _utc_now()

        heartbeat = HeartbeatRequest(
            liveness=LivenessProbeData(
                alive=True,
                memory_mb=2048,
                cpu_pct=45.5,
                error_count=1,
                last_error="Timeout on API call",
            ),
            readiness=ReadinessProbeData(
                ready=True,
                current_load=3,
                max_load=5,
                queue_depth=2,
                blocked_by=[blocked_id],
            ),
            progress=ProgressProbeData(
                research_state="experimenting",
                current_task_id=task_id,
                progress_pct=0.65,
                findings_since_last=3,
                tokens_since_last=5000,
                confidence_delta=0.12,
                stale_minutes=10,
                estimated_completion=completion_time,
            ),
        )
        assert heartbeat.liveness.alive is True
        assert heartbeat.liveness.memory_mb == 2048
        assert heartbeat.liveness.cpu_pct == 45.5
        assert heartbeat.liveness.error_count == 1
        assert heartbeat.liveness.last_error == "Timeout on API call"

        assert heartbeat.readiness.ready is True
        assert heartbeat.readiness.current_load == 3
        assert heartbeat.readiness.max_load == 5
        assert heartbeat.readiness.queue_depth == 2
        assert heartbeat.readiness.blocked_by == [blocked_id]

        assert heartbeat.progress.research_state == "experimenting"
        assert heartbeat.progress.current_task_id == task_id
        assert heartbeat.progress.progress_pct == 0.65
        assert heartbeat.progress.findings_since_last == 3
        assert heartbeat.progress.tokens_since_last == 5000
        assert heartbeat.progress.confidence_delta == 0.12
        assert heartbeat.progress.stale_minutes == 10
        assert heartbeat.progress.estimated_completion == completion_time

    def test_default_values_for_each_probe(self):
        from platform.agents.lifecycle_schemas import (
            LivenessProbeData,
            ProgressProbeData,
            ReadinessProbeData,
        )

        liveness = LivenessProbeData()
        assert liveness.alive is True
        assert liveness.memory_mb == 0
        assert liveness.cpu_pct == 0.0
        assert liveness.error_count == 0
        assert liveness.last_error is None

        readiness = ReadinessProbeData()
        assert readiness.ready is True
        assert readiness.current_load == 0
        assert readiness.max_load == 5
        assert readiness.queue_depth == 0
        assert readiness.blocked_by is None

        progress = ProgressProbeData()
        assert progress.research_state == "idle"
        assert progress.current_task_id is None
        assert progress.progress_pct == 0.0
        assert progress.findings_since_last == 0
        assert progress.tokens_since_last == 0
        assert progress.confidence_delta == 0.0
        assert progress.stale_minutes == 0
        assert progress.estimated_completion is None

    def test_heartbeat_serialization(self):
        from platform.agents.lifecycle_schemas import (
            HeartbeatRequest,
            LivenessProbeData,
            ProgressProbeData,
            ReadinessProbeData,
        )

        heartbeat = HeartbeatRequest(
            liveness=LivenessProbeData(alive=True, memory_mb=1024),
            readiness=ReadinessProbeData(ready=True, current_load=1),
            progress=ProgressProbeData(research_state="analyzing", progress_pct=0.8),
        )
        data = heartbeat.model_dump()

        assert data["liveness"]["alive"] is True
        assert data["liveness"]["memory_mb"] == 1024
        assert data["readiness"]["ready"] is True
        assert data["readiness"]["current_load"] == 1
        assert data["progress"]["research_state"] == "analyzing"
        assert data["progress"]["progress_pct"] == 0.8


# ===========================================
# HEALTH ASSESSMENT SCHEMA TESTS
# ===========================================


class TestHealthAssessmentSchemas:
    """Test HealthAssessmentResponse schema."""

    def test_healthy_assessment(self):
        from platform.agents.lifecycle_schemas import HealthAssessmentResponse

        agent_id = uuid4()

        assessment = HealthAssessmentResponse(
            agent_id=agent_id,
            operational_state="online",
            research_state="experimenting",
            liveness_ok=True,
            readiness_ok=True,
            progress_ok=True,
        )
        assert assessment.agent_id == agent_id
        assert assessment.operational_state == "online"
        assert assessment.research_state == "experimenting"
        assert assessment.liveness_ok is True
        assert assessment.readiness_ok is True
        assert assessment.progress_ok is True
        assert assessment.warnings == []
        assert assessment.recommendation == "continue"

    def test_assessment_with_warnings(self):
        from platform.agents.lifecycle_schemas import HealthAssessmentResponse

        agent_id = uuid4()
        warnings = [
            "High memory usage: 5120MB",
            "No progress for 45 minutes",
        ]

        assessment = HealthAssessmentResponse(
            agent_id=agent_id,
            operational_state="online",
            research_state="experimenting",
            liveness_ok=True,
            readiness_ok=True,
            progress_ok=False,
            warnings=warnings,
            recommendation="investigate",
        )
        assert len(assessment.warnings) == 2
        assert "High memory usage: 5120MB" in assessment.warnings
        assert "No progress for 45 minutes" in assessment.warnings
        assert assessment.progress_ok is False
        assert assessment.recommendation == "investigate"

    def test_default_recommendation_is_continue(self):
        from platform.agents.lifecycle_schemas import HealthAssessmentResponse

        assessment = HealthAssessmentResponse(
            agent_id=uuid4(),
            operational_state="online",
            research_state="idle",
            liveness_ok=True,
            readiness_ok=True,
            progress_ok=True,
        )
        assert assessment.recommendation == "continue"


# ===========================================
# PARKING SCHEMA TESTS
# ===========================================


class TestParkingSchemas:
    """Test ParkRequest and ResumeEstimateResponse schemas."""

    def test_park_request_default_reason(self):
        from platform.agents.lifecycle_schemas import ParkRequest

        req = ParkRequest()
        assert req.reason == "manual"

    def test_park_request_custom_reason(self):
        from platform.agents.lifecycle_schemas import ParkRequest

        req = ParkRequest(reason="budget_exceeded")
        assert req.reason == "budget_exceeded"

    def test_resume_estimate_response(self):
        from platform.agents.lifecycle_schemas import ResumeEstimateResponse

        agent_id = uuid4()
        checkpoint_id = uuid4()

        estimate = ResumeEstimateResponse(
            agent_id=agent_id,
            checkpoint_id=checkpoint_id,
            estimated_tokens=1500,
            estimated_minutes=3.0,
            state_drift_items=12,
            checkpoint_age_hours=4.5,
        )
        assert estimate.agent_id == agent_id
        assert estimate.checkpoint_id == checkpoint_id
        assert estimate.estimated_tokens == 1500
        assert estimate.estimated_minutes == 3.0
        assert estimate.state_drift_items == 12
        assert estimate.checkpoint_age_hours == 4.5


# ===========================================
# PROGRESS POST SCHEMA TESTS
# ===========================================


class TestProgressPostSchemas:
    """Test CreateProgressPostRequest and ProgressPostResponse schemas."""

    def test_create_post_minimal_fields(self):
        from platform.agents.lifecycle_schemas import CreateProgressPostRequest

        req = CreateProgressPostRequest(
            post_type="finding",
            title="Unexpected convergence behaviour",
            content="The loss landscape exhibits double descent under specific conditions.",
        )
        assert req.post_type == "finding"
        assert req.title == "Unexpected convergence behaviour"
        assert req.content == "The loss landscape exhibits double descent under specific conditions."
        assert req.sprint_id is None
        assert req.confidence is None
        assert req.related_research_item is None
        assert req.visibility == "lab"

    def test_create_post_all_fields(self):
        from platform.agents.lifecycle_schemas import CreateProgressPostRequest

        sprint_id = uuid4()
        item_id = uuid4()

        req = CreateProgressPostRequest(
            post_type="hypothesis",
            title="Attention heads specialise by layer depth",
            content="Evidence suggests early layers handle syntax, deeper layers handle semantics.",
            sprint_id=sprint_id,
            confidence=0.85,
            related_research_item=item_id,
            visibility="public",
        )
        assert req.sprint_id == sprint_id
        assert req.confidence == 0.85
        assert req.related_research_item == item_id
        assert req.visibility == "public"

    def test_progress_post_response(self):
        from platform.agents.lifecycle_schemas import ProgressPostResponse

        post_id = uuid4()
        agent_id = uuid4()
        lab_id = uuid4()
        sprint_id = uuid4()
        now = _utc_now()

        post = ProgressPostResponse(
            id=post_id,
            agent_id=agent_id,
            lab_id=lab_id,
            sprint_id=sprint_id,
            post_type="finding",
            title="Gradient norm explosion in layer 12",
            content="Detailed analysis of gradient behaviour during training.",
            confidence=0.92,
            visibility="lab",
            created_at=now,
        )
        assert post.id == post_id
        assert post.agent_id == agent_id
        assert post.lab_id == lab_id
        assert post.sprint_id == sprint_id
        assert post.post_type == "finding"
        assert post.title == "Gradient norm explosion in layer 12"
        assert post.confidence == 0.92
        assert post.visibility == "lab"
        assert post.created_at == now


# ===========================================
# API ENDPOINT TESTS
# ===========================================


class TestLifecycleAPIEndpoints:
    """Integration tests for lifecycle router endpoints."""

    @pytest.mark.asyncio
    async def test_heartbeat_endpoint_processes_heartbeat(self):
        """POST /lifecycle/agents/{id}/heartbeat should process heartbeat."""
        from platform.agents.lifecycle_api import agent_heartbeat
        from platform.agents.lifecycle_schemas import (
            HeartbeatRequest,
            HealthAssessmentResponse,
            LivenessProbeData,
            ProgressProbeData,
            ReadinessProbeData,
        )

        mock_session = AsyncMock()
        agent_id = uuid4()

        heartbeat = HeartbeatRequest(
            liveness=LivenessProbeData(alive=True, memory_mb=512),
            readiness=ReadinessProbeData(ready=True),
            progress=ProgressProbeData(research_state="analyzing"),
        )

        assessment = HealthAssessmentResponse(
            agent_id=agent_id,
            operational_state="online",
            research_state="analyzing",
            liveness_ok=True,
            readiness_ok=True,
            progress_ok=True,
            warnings=[],
            recommendation="continue",
        )

        with patch("platform.agents.lifecycle_api.HeartbeatProcessor") as MockProcessor:
            mock_proc = MagicMock()
            mock_proc.process_heartbeat = AsyncMock(return_value=assessment.model_dump())
            MockProcessor.return_value = mock_proc

            result = await agent_heartbeat(agent_id=agent_id, body=heartbeat, db=mock_session)

        assert result["operational_state"] == "online"
        assert result["liveness_ok"] is True
        assert result["recommendation"] == "continue"

    @pytest.mark.asyncio
    async def test_health_endpoint_returns_assessment(self):
        """GET /lifecycle/agents/{id}/health should return health assessment."""
        from platform.agents.lifecycle_api import get_agent_health
        from platform.agents.lifecycle_schemas import HealthAssessmentResponse

        mock_session = AsyncMock()
        agent_id = uuid4()

        assessment = HealthAssessmentResponse(
            agent_id=agent_id,
            operational_state="online",
            research_state="idle",
            liveness_ok=True,
            readiness_ok=True,
            progress_ok=True,
            warnings=[],
            recommendation="continue",
        )

        with patch("platform.agents.lifecycle_api.AgentHealthEvaluator") as MockEvaluator:
            mock_eval = MagicMock()
            mock_eval.evaluate = AsyncMock(return_value=assessment.model_dump())
            MockEvaluator.return_value = mock_eval

            result = await get_agent_health(agent_id=agent_id, db=mock_session)

        assert result["agent_id"] == str(agent_id)
        assert result["liveness_ok"] is True
        assert result["recommendation"] == "continue"

    @pytest.mark.asyncio
    async def test_park_endpoint_parks_agent(self):
        """POST /lifecycle/agents/{id}/park should park the agent."""
        from platform.agents.lifecycle_api import park_agent
        from platform.agents.lifecycle_schemas import ParkRequest

        mock_session = AsyncMock()
        agent_id = uuid4()
        checkpoint_id = uuid4()
        body = ParkRequest(reason="budget_exceeded")

        park_result = {
            "agent_id": str(agent_id),
            "checkpoint_id": str(checkpoint_id),
            "reason": "budget_exceeded",
            "parked_at": _utc_now().isoformat(),
        }

        with patch("platform.agents.lifecycle_api.AgentParkingService") as MockParking:
            mock_svc = MagicMock()
            mock_svc.park = AsyncMock(return_value=park_result)
            MockParking.return_value = mock_svc

            result = await park_agent(agent_id=agent_id, body=body, db=mock_session)

        assert result["agent_id"] == str(agent_id)
        assert result["reason"] == "budget_exceeded"
        assert "checkpoint_id" in result

    @pytest.mark.asyncio
    async def test_resume_endpoint_resumes_agent(self):
        """POST /lifecycle/agents/{id}/resume should resume the agent."""
        from platform.agents.lifecycle_api import resume_agent

        mock_session = AsyncMock()
        agent_id = uuid4()

        resume_result = {
            "agent_id": str(agent_id),
            "restored_state": "experimenting",
            "checkpoint_sequence": 7,
            "resumed_at": _utc_now().isoformat(),
        }

        with patch("platform.agents.lifecycle_api.AgentParkingService") as MockParking:
            mock_svc = MagicMock()
            mock_svc.resume = AsyncMock(return_value=resume_result)
            MockParking.return_value = mock_svc

            result = await resume_agent(agent_id=agent_id, db=mock_session)

        assert result["agent_id"] == str(agent_id)
        assert result["restored_state"] == "experimenting"
        assert result["checkpoint_sequence"] == 7

    @pytest.mark.asyncio
    async def test_sprint_start_creates_sprint(self):
        """POST /lifecycle/agents/{id}/sprints should create a new sprint."""
        from platform.agents.lifecycle_api import start_sprint
        from platform.agents.lifecycle_schemas import StartSprintRequest, SprintResponse

        mock_session = AsyncMock()
        agent_id = uuid4()
        lab_id = uuid4()
        sprint_id = uuid4()
        now = _utc_now()

        body = StartSprintRequest(
            goal="Investigate attention head pruning",
            approach="iterative magnitude pruning",
            duration_days=14,
            domain="ml_ai",
        )

        mock_sprint = MagicMock()
        mock_sprint.id = sprint_id
        mock_sprint.agent_id = agent_id
        mock_sprint.lab_id = lab_id
        mock_sprint.sprint_number = 1
        mock_sprint.goal = body.goal
        mock_sprint.approach = body.approach
        mock_sprint.started_at = now
        mock_sprint.target_end_at = now
        mock_sprint.actual_end_at = None
        mock_sprint.status = "planning"
        mock_sprint.outcome_type = None
        mock_sprint.outcome_summary = None
        mock_sprint.claims_submitted = 0
        mock_sprint.findings_recorded = 0
        mock_sprint.reviews_completed = 0
        mock_sprint.hypotheses_active = 0
        mock_sprint.tokens_consumed = 0
        mock_sprint.checkpoints_created = 0
        mock_sprint.reviewed = False
        mock_sprint.review_verdict = None

        with patch("platform.agents.lifecycle_api.SprintService") as MockService:
            mock_svc = MagicMock()
            mock_svc.start_sprint = AsyncMock(return_value=mock_sprint)
            MockService.return_value = mock_svc

            result = await start_sprint(
                agent_id=agent_id,
                lab_id=lab_id,
                body=body,
                db=mock_session,
            )

        assert result.id == sprint_id
        assert result.goal == "Investigate attention head pruning"
        assert result.status == "planning"

    @pytest.mark.asyncio
    async def test_checkpoints_list_endpoint(self):
        """GET /lifecycle/agents/{id}/checkpoints should return checkpoint summaries."""
        from platform.agents.lifecycle_api import list_checkpoints

        mock_session = AsyncMock()
        agent_id = uuid4()

        cp_list = [
            {
                "id": str(uuid4()),
                "sequence_number": 3,
                "checkpoint_type": "auto",
                "research_state": "experimenting",
                "progress_pct": 0.6,
                "tokens_consumed": 10000,
                "is_latest": True,
                "created_at": _utc_now().isoformat(),
            },
            {
                "id": str(uuid4()),
                "sequence_number": 2,
                "checkpoint_type": "auto",
                "research_state": "hypothesizing",
                "progress_pct": 0.3,
                "tokens_consumed": 5000,
                "is_latest": False,
                "created_at": _utc_now().isoformat(),
            },
        ]

        with patch("platform.agents.lifecycle_api.CheckpointService") as MockService:
            mock_svc = MagicMock()
            mock_svc.list_checkpoints = AsyncMock(return_value=cp_list)
            MockService.return_value = mock_svc

            result = await list_checkpoints(
                agent_id=agent_id,
                limit=20,
                offset=0,
                db=mock_session,
            )

        assert len(result) == 2
        assert result[0]["sequence_number"] == 3
        assert result[0]["is_latest"] is True
        assert result[1]["sequence_number"] == 2
        assert result[1]["is_latest"] is False
