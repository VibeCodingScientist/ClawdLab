"""Research Orchestration Layer.

This module provides orchestration for autonomous scientific research:
- Workflow management for multi-step research processes
- Claim routing to appropriate verification engines
- Task scheduling and queue management
- Session management for agent work tracking

The orchestration layer coordinates all verification engines and manages
the flow of research from request to result.
"""

from platform.orchestration.base import (
    Claim,
    ClaimStatus,
    ClaimVerificationResult,
    Priority,
    ResearchRequest,
    ResearchResponse,
    ResearchSession,
    ResearchTask,
    ResearchWorkflow,
    RoutingDecision,
    TaskStatus,
    WorkflowStatus,
    WorkflowStep,
)
from platform.orchestration.claim_router import ClaimRouter, get_claim_router
from platform.orchestration.config import (
    CLAIM_TYPE_DOMAINS,
    RESEARCH_DOMAINS,
    TASK_TYPES,
    WORKFLOW_TEMPLATES,
    get_settings,
)
from platform.orchestration.service import OrchestrationService, get_orchestration_service
from platform.orchestration.session_manager import SessionManager, get_session_manager
from platform.orchestration.task_scheduler import TaskScheduler, get_task_scheduler
from platform.orchestration.workflow_engine import WorkflowEngine, get_workflow_engine

__all__ = [
    # Config
    "get_settings",
    "RESEARCH_DOMAINS",
    "WORKFLOW_TEMPLATES",
    "TASK_TYPES",
    "CLAIM_TYPE_DOMAINS",
    # Enums
    "WorkflowStatus",
    "TaskStatus",
    "ClaimStatus",
    "Priority",
    # Data classes
    "Claim",
    "ClaimVerificationResult",
    "ResearchTask",
    "WorkflowStep",
    "ResearchWorkflow",
    "ResearchSession",
    "RoutingDecision",
    "ResearchRequest",
    "ResearchResponse",
    # Services
    "OrchestrationService",
    "get_orchestration_service",
    "WorkflowEngine",
    "get_workflow_engine",
    "ClaimRouter",
    "get_claim_router",
    "TaskScheduler",
    "get_task_scheduler",
    "SessionManager",
    "get_session_manager",
]
