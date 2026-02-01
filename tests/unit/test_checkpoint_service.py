"""Unit tests for checkpoint serialization roundtrip."""

import pytest

from platform.agents.checkpoint import (
    AgentCheckpointData,
    DecisionEntry,
    FindingSnapshot,
    HypothesisState,
    TaskSnapshot,
)


class TestCheckpointSerialization:
    def test_empty_checkpoint_roundtrip(self):
        data = AgentCheckpointData(agent_id="test-agent-1")
        serialized = data.to_dict()
        restored = AgentCheckpointData.from_dict(serialized)

        assert restored.agent_id == "test-agent-1"
        assert restored.research_state == "idle"
        assert restored.hypothesis_stack == []
        assert restored.findings == []

    def test_full_checkpoint_roundtrip(self):
        data = AgentCheckpointData(
            agent_id="test-agent-2",
            lab_id="lab-123",
            sequence_number=5,
            current_task=TaskSnapshot(
                task_id="task-1",
                task_type="research_item",
                source_id="src-1",
                description="Investigate protein folding",
                started_at="2026-01-01T00:00:00Z",
                approach="ML-guided molecular dynamics",
            ),
            hypothesis_stack=[
                HypothesisState(
                    hypothesis_id="h1",
                    statement="Alpha helices form first",
                    confidence=0.75,
                    evidence_for=["sim-1", "sim-2"],
                    evidence_against=["paper-3"],
                    status="active",
                ),
            ],
            findings=[
                FindingSnapshot(
                    finding_id="f1",
                    description="Found novel intermediate state",
                    evidence_type="computational",
                    confidence=0.82,
                    publishable=True,
                ),
            ],
            decision_log=[
                DecisionEntry(
                    timestamp="2026-01-02T10:00:00Z",
                    decision="Switch to explicit solvent",
                    reasoning="Implicit solvent underestimates entropy",
                    alternatives_considered=["keep implicit", "hybrid model"],
                ),
            ],
            core_memory={"persona": "experimentalist", "focus": "protein folding"},
            working_memory="Currently analyzing trajectory data from run 47...",
            archival_refs=["vec-001", "vec-002"],
            pending_compute_jobs=["job-1"],
            sprint_id="sprint-42",
            sprint_progress_pct=0.65,
            tokens_consumed=150000,
            compute_seconds_used=3600.5,
            research_state="analyzing",
            resume_action="continue_analysis",
            resume_context={"trajectory_id": "traj-47"},
        )

        serialized = data.to_dict()
        assert isinstance(serialized, dict)
        assert serialized["agent_id"] == "test-agent-2"
        assert serialized["research_state"] == "analyzing"
        assert serialized["current_task"]["task_type"] == "research_item"
        assert len(serialized["hypothesis_stack"]) == 1

        restored = AgentCheckpointData.from_dict(serialized)
        assert restored.agent_id == "test-agent-2"
        assert restored.current_task.task_type == "research_item"
        assert restored.hypothesis_stack[0].confidence == 0.75
        assert restored.findings[0].publishable is True
        assert restored.decision_log[0].decision == "Switch to explicit solvent"
        assert restored.sprint_progress_pct == 0.65
        assert restored.resume_context == {"trajectory_id": "traj-47"}

    def test_checkpoint_without_nested_objects(self):
        data = AgentCheckpointData(
            agent_id="agent-3",
            research_state="scouting",
            working_memory="Scanning recent papers...",
        )
        serialized = data.to_dict()
        restored = AgentCheckpointData.from_dict(serialized)

        assert restored.current_task is None
        assert restored.hypothesis_stack == []
        assert restored.working_memory == "Scanning recent papers..."
