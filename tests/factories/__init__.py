"""Test data factories for the Autonomous Scientific Research Platform.

This module provides factory classes for generating test data.
Factories use the Factory Boy pattern for consistent test data generation.
"""

from tests.factories.user_factory import UserFactory
from tests.factories.agent_factory import AgentFactory
from tests.factories.experiment_factory import ExperimentFactory, ExperimentPlanFactory
from tests.factories.claim_factory import ClaimFactory, VerificationResultFactory

__all__ = [
    "UserFactory",
    "AgentFactory",
    "ExperimentFactory",
    "ExperimentPlanFactory",
    "ClaimFactory",
    "VerificationResultFactory",
]
