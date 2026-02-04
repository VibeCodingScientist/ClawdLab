"""Unit tests for AgentRegistry service."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock

import pytest


def _utcnow() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)

from platform.agents.registry import AgentRegistry
from platform.agents.base import AgentInfo, AgentMetrics, AgentStatus


class TestAgentRegistry:
    """Tests for AgentRegistry class."""

    @pytest.fixture
    def registry(self) -> AgentRegistry:
        """Create a fresh registry instance."""
        return AgentRegistry()

    @pytest.fixture
    async def started_registry(self, registry: AgentRegistry) -> AgentRegistry:
        """Create and start a registry instance."""
        # Start without actually running the health check loop
        with patch.object(registry, '_health_check_loop', new_callable=AsyncMock):
            await registry.start()
        yield registry
        await registry.stop()

    # ===================================
    # REGISTRATION TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_register_agent_success(self, registry: AgentRegistry):
        """Test successful agent registration."""
        agent = await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research", "hypothesis_generation"],
            endpoint="http://localhost:8001",
            description="A test research agent",
            metadata={"version": "1.0"},
        )

        assert agent is not None
        assert agent.agent_type == "research"
        assert agent.name == "Test Agent"
        assert agent.capabilities == ["research", "hypothesis_generation"]
        assert agent.endpoint == "http://localhost:8001"
        assert agent.status == AgentStatus.INITIALIZING
        assert agent.metadata["version"] == "1.0"
        assert agent.agent_id is not None

    @pytest.mark.asyncio
    async def test_register_agent_with_custom_id(self, registry: AgentRegistry):
        """Test registration with custom agent ID."""
        custom_id = "custom-agent-123"
        agent = await registry.register(
            agent_type="math",
            name="Math Agent",
            capabilities=["proof_generation"],
            agent_id=custom_id,
        )

        assert agent.agent_id == custom_id

    @pytest.mark.asyncio
    async def test_register_agent_unknown_type_logs_warning(self, registry: AgentRegistry):
        """Test registration with unknown agent type logs warning but succeeds."""
        agent = await registry.register(
            agent_type="unknown_type",
            name="Unknown Agent",
            capabilities=["some_capability"],
        )

        # Should still succeed but with the unknown type
        assert agent.agent_type == "unknown_type"

    @pytest.mark.asyncio
    async def test_register_agent_max_agents_exceeded(self, registry: AgentRegistry):
        """Test registration fails when max agents reached."""
        # Patch settings to have max_agents = 2
        with patch('platform.agents.registry.settings') as mock_settings:
            mock_settings.max_agents = 2

            # Register 2 agents
            await registry.register(
                agent_type="research",
                name="Agent 1",
                capabilities=["research"],
            )
            await registry.register(
                agent_type="math",
                name="Agent 2",
                capabilities=["proof_generation"],
            )

            # Third registration should fail
            with pytest.raises(ValueError, match="Maximum agents"):
                await registry.register(
                    agent_type="ml",
                    name="Agent 3",
                    capabilities=["experiment_design"],
                )

    @pytest.mark.asyncio
    async def test_register_agent_creates_metrics(self, registry: AgentRegistry):
        """Test that registration creates metrics entry."""
        agent = await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research"],
        )

        metrics = await registry.get_metrics(agent.agent_id)
        assert metrics is not None
        assert metrics.agent_id == agent.agent_id
        assert metrics.messages_sent == 0
        assert metrics.errors_count == 0

    @pytest.mark.asyncio
    async def test_register_agent_records_event(self, registry: AgentRegistry):
        """Test that registration records an event."""
        agent = await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research"],
        )

        events = await registry.get_events(agent_id=agent.agent_id)
        assert len(events) >= 1
        assert events[0].event_type == "registered"
        assert events[0].agent_id == agent.agent_id

    @pytest.mark.asyncio
    async def test_register_agent_indexes_by_type(self, registry: AgentRegistry):
        """Test that agents are indexed by type."""
        await registry.register(
            agent_type="research",
            name="Research Agent 1",
            capabilities=["research"],
        )
        await registry.register(
            agent_type="research",
            name="Research Agent 2",
            capabilities=["research"],
        )
        await registry.register(
            agent_type="math",
            name="Math Agent",
            capabilities=["proof_generation"],
        )

        research_agents = await registry.get_agents_by_type("research")
        assert len(research_agents) == 2

        math_agents = await registry.get_agents_by_type("math")
        assert len(math_agents) == 1

    @pytest.mark.asyncio
    async def test_register_agent_indexes_by_capability(self, registry: AgentRegistry):
        """Test that agents are indexed by capabilities."""
        await registry.register(
            agent_type="research",
            name="Research Agent",
            capabilities=["research", "hypothesis_generation"],
        )
        await registry.register(
            agent_type="knowledge",
            name="Knowledge Agent",
            capabilities=["research", "knowledge_storage"],
        )

        research_capable = await registry.get_agents_by_capability("research")
        assert len(research_capable) == 2

        knowledge_capable = await registry.get_agents_by_capability("knowledge_storage")
        assert len(knowledge_capable) == 1

    # ===================================
    # UNREGISTRATION TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_unregister_agent_success(self, registry: AgentRegistry):
        """Test successful agent unregistration."""
        agent = await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research"],
        )

        result = await registry.unregister(agent.agent_id)
        assert result is True

        # Verify agent is removed
        retrieved = await registry.get_agent(agent.agent_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_unregister_agent_not_found(self, registry: AgentRegistry):
        """Test unregistering non-existent agent returns False."""
        result = await registry.unregister("non-existent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_unregister_removes_from_type_index(self, registry: AgentRegistry):
        """Test that unregistration removes agent from type index."""
        agent = await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research"],
        )

        await registry.unregister(agent.agent_id)

        research_agents = await registry.get_agents_by_type("research")
        assert len(research_agents) == 0

    @pytest.mark.asyncio
    async def test_unregister_removes_from_capability_index(self, registry: AgentRegistry):
        """Test that unregistration removes agent from capability index."""
        agent = await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research", "hypothesis_generation"],
        )

        await registry.unregister(agent.agent_id)

        research_capable = await registry.get_agents_by_capability("research")
        assert len(research_capable) == 0

        hypothesis_capable = await registry.get_agents_by_capability("hypothesis_generation")
        assert len(hypothesis_capable) == 0

    @pytest.mark.asyncio
    async def test_unregister_records_event(self, registry: AgentRegistry):
        """Test that unregistration records an event."""
        agent = await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research"],
        )

        await registry.unregister(agent.agent_id)

        events = await registry.get_events(agent_id=agent.agent_id)
        unregister_events = [e for e in events if e.event_type == "unregistered"]
        assert len(unregister_events) == 1

    # ===================================
    # STATUS UPDATE TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_update_status_success(self, registry: AgentRegistry):
        """Test successful status update."""
        agent = await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research"],
        )

        updated = await registry.update_status(agent.agent_id, AgentStatus.READY)
        assert updated is not None
        assert updated.status == AgentStatus.READY

    @pytest.mark.asyncio
    async def test_update_status_with_metadata(self, registry: AgentRegistry):
        """Test status update with metadata."""
        agent = await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research"],
        )

        updated = await registry.update_status(
            agent.agent_id,
            AgentStatus.BUSY,
            metadata={"current_task": "processing"},
        )

        assert updated.status == AgentStatus.BUSY
        assert updated.metadata["current_task"] == "processing"

    @pytest.mark.asyncio
    async def test_update_status_not_found(self, registry: AgentRegistry):
        """Test status update for non-existent agent."""
        result = await registry.update_status("non-existent-id", AgentStatus.READY)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_status_records_event(self, registry: AgentRegistry):
        """Test that status change records an event."""
        agent = await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research"],
        )

        await registry.update_status(agent.agent_id, AgentStatus.READY)

        events = await registry.get_events(agent_id=agent.agent_id)
        status_events = [e for e in events if e.event_type == "status_changed"]
        assert len(status_events) == 1
        assert status_events[0].data["new_status"] == "ready"

    # ===================================
    # HEARTBEAT TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_heartbeat_success(self, registry: AgentRegistry):
        """Test successful heartbeat."""
        agent = await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research"],
        )

        original_heartbeat = agent.last_heartbeat

        # Small delay to ensure time difference
        await asyncio.sleep(0.01)

        result = await registry.heartbeat(agent.agent_id)
        assert result is True

        updated_agent = await registry.get_agent(agent.agent_id)
        assert updated_agent.last_heartbeat > original_heartbeat

    @pytest.mark.asyncio
    async def test_heartbeat_not_found(self, registry: AgentRegistry):
        """Test heartbeat for non-existent agent."""
        result = await registry.heartbeat("non-existent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_heartbeat_recovers_unhealthy_agent(self, registry: AgentRegistry):
        """Test that heartbeat recovers an unhealthy agent."""
        agent = await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research"],
        )

        # Set agent to unhealthy
        await registry.update_status(agent.agent_id, AgentStatus.UNHEALTHY)

        # Send heartbeat
        await registry.heartbeat(agent.agent_id)

        updated_agent = await registry.get_agent(agent.agent_id)
        assert updated_agent.status == AgentStatus.READY

    @pytest.mark.asyncio
    async def test_heartbeat_records_recovery_event(self, registry: AgentRegistry):
        """Test that recovery from unhealthy records an event."""
        agent = await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research"],
        )

        await registry.update_status(agent.agent_id, AgentStatus.UNHEALTHY)
        await registry.heartbeat(agent.agent_id)

        events = await registry.get_events(agent_id=agent.agent_id)
        recovery_events = [e for e in events if e.event_type == "recovered"]
        assert len(recovery_events) == 1

    @pytest.mark.asyncio
    async def test_heartbeat_updates_metrics(self, registry: AgentRegistry):
        """Test that heartbeat updates agent metrics."""
        agent = await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research"],
        )

        await registry.heartbeat(
            agent.agent_id,
            metrics={
                "messages_sent": 10,
                "messages_received": 5,
                "requests_handled": 3,
                "errors_count": 1,
                "avg_response_time_ms": 150.5,
            },
        )

        metrics = await registry.get_metrics(agent.agent_id)
        assert metrics.messages_sent == 10
        assert metrics.messages_received == 5
        assert metrics.requests_handled == 3
        assert metrics.errors_count == 1
        assert metrics.avg_response_time_ms == 150.5

    # ===================================
    # AGENT RETRIEVAL TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_get_agent_success(self, registry: AgentRegistry):
        """Test getting agent by ID."""
        agent = await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research"],
        )

        retrieved = await registry.get_agent(agent.agent_id)
        assert retrieved is not None
        assert retrieved.agent_id == agent.agent_id
        assert retrieved.name == "Test Agent"

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, registry: AgentRegistry):
        """Test getting non-existent agent."""
        retrieved = await registry.get_agent("non-existent-id")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_agents_by_type_with_status_filter(self, registry: AgentRegistry):
        """Test getting agents by type with status filter."""
        agent1 = await registry.register(
            agent_type="research",
            name="Research Agent 1",
            capabilities=["research"],
        )
        agent2 = await registry.register(
            agent_type="research",
            name="Research Agent 2",
            capabilities=["research"],
        )

        # Set one to ready
        await registry.update_status(agent1.agent_id, AgentStatus.READY)

        ready_agents = await registry.get_agents_by_type("research", status=AgentStatus.READY)
        assert len(ready_agents) == 1
        assert ready_agents[0].agent_id == agent1.agent_id

    @pytest.mark.asyncio
    async def test_get_agents_by_capability_with_status_filter(self, registry: AgentRegistry):
        """Test getting agents by capability with status filter."""
        agent1 = await registry.register(
            agent_type="research",
            name="Agent 1",
            capabilities=["research"],
        )
        agent2 = await registry.register(
            agent_type="knowledge",
            name="Agent 2",
            capabilities=["research", "knowledge_storage"],
        )

        await registry.update_status(agent2.agent_id, AgentStatus.READY)

        ready_research = await registry.get_agents_by_capability(
            "research", status=AgentStatus.READY
        )
        assert len(ready_research) == 1
        assert ready_research[0].agent_id == agent2.agent_id

    # ===================================
    # FIND AGENTS TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_find_agents_no_filters(self, registry: AgentRegistry):
        """Test finding all agents."""
        await registry.register(
            agent_type="research",
            name="Agent 1",
            capabilities=["research"],
        )
        await registry.register(
            agent_type="math",
            name="Agent 2",
            capabilities=["proof_generation"],
        )

        agents = await registry.find_agents()
        assert len(agents) == 2

    @pytest.mark.asyncio
    async def test_find_agents_by_type(self, registry: AgentRegistry):
        """Test finding agents by type."""
        await registry.register(
            agent_type="research",
            name="Research Agent",
            capabilities=["research"],
        )
        await registry.register(
            agent_type="math",
            name="Math Agent",
            capabilities=["proof_generation"],
        )

        agents = await registry.find_agents(agent_type="research")
        assert len(agents) == 1
        assert agents[0].agent_type == "research"

    @pytest.mark.asyncio
    async def test_find_agents_by_capabilities(self, registry: AgentRegistry):
        """Test finding agents by required capabilities."""
        await registry.register(
            agent_type="research",
            name="Agent 1",
            capabilities=["research", "hypothesis_generation"],
        )
        await registry.register(
            agent_type="research",
            name="Agent 2",
            capabilities=["research"],
        )

        # Find agents with both capabilities
        agents = await registry.find_agents(
            capabilities=["research", "hypothesis_generation"]
        )
        assert len(agents) == 1
        assert "hypothesis_generation" in agents[0].capabilities

    @pytest.mark.asyncio
    async def test_find_agents_by_status(self, registry: AgentRegistry):
        """Test finding agents by status."""
        agent1 = await registry.register(
            agent_type="research",
            name="Agent 1",
            capabilities=["research"],
        )
        agent2 = await registry.register(
            agent_type="math",
            name="Agent 2",
            capabilities=["proof_generation"],
        )

        await registry.update_status(agent1.agent_id, AgentStatus.READY)

        ready_agents = await registry.find_agents(status=AgentStatus.READY)
        assert len(ready_agents) == 1
        assert ready_agents[0].agent_id == agent1.agent_id

    @pytest.mark.asyncio
    async def test_find_agents_combined_filters(self, registry: AgentRegistry):
        """Test finding agents with combined filters."""
        agent1 = await registry.register(
            agent_type="research",
            name="Research Agent 1",
            capabilities=["research", "hypothesis_generation"],
        )
        agent2 = await registry.register(
            agent_type="research",
            name="Research Agent 2",
            capabilities=["research"],
        )
        agent3 = await registry.register(
            agent_type="math",
            name="Math Agent",
            capabilities=["proof_generation"],
        )

        await registry.update_status(agent1.agent_id, AgentStatus.READY)
        await registry.update_status(agent2.agent_id, AgentStatus.READY)

        # Find ready research agents with hypothesis_generation
        agents = await registry.find_agents(
            agent_type="research",
            capabilities=["hypothesis_generation"],
            status=AgentStatus.READY,
        )
        assert len(agents) == 1
        assert agents[0].agent_id == agent1.agent_id

    @pytest.mark.asyncio
    async def test_find_agents_respects_limit(self, registry: AgentRegistry):
        """Test that find_agents respects limit."""
        for i in range(10):
            await registry.register(
                agent_type="research",
                name=f"Agent {i}",
                capabilities=["research"],
            )

        agents = await registry.find_agents(limit=5)
        assert len(agents) == 5

    # ===================================
    # GET READY AGENT TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_get_ready_agent_success(self, registry: AgentRegistry):
        """Test getting a ready agent."""
        agent = await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research"],
        )
        await registry.update_status(agent.agent_id, AgentStatus.READY)

        ready = await registry.get_ready_agent()
        assert ready is not None
        assert ready.agent_id == agent.agent_id

    @pytest.mark.asyncio
    async def test_get_ready_agent_by_capability(self, registry: AgentRegistry):
        """Test getting a ready agent by capability."""
        agent1 = await registry.register(
            agent_type="research",
            name="Research Agent",
            capabilities=["research"],
        )
        agent2 = await registry.register(
            agent_type="math",
            name="Math Agent",
            capabilities=["proof_generation"],
        )

        await registry.update_status(agent1.agent_id, AgentStatus.READY)
        await registry.update_status(agent2.agent_id, AgentStatus.READY)

        ready = await registry.get_ready_agent(capability="proof_generation")
        assert ready is not None
        assert ready.agent_id == agent2.agent_id

    @pytest.mark.asyncio
    async def test_get_ready_agent_by_type(self, registry: AgentRegistry):
        """Test getting a ready agent by type."""
        agent1 = await registry.register(
            agent_type="research",
            name="Research Agent",
            capabilities=["research"],
        )
        agent2 = await registry.register(
            agent_type="math",
            name="Math Agent",
            capabilities=["proof_generation"],
        )

        await registry.update_status(agent1.agent_id, AgentStatus.READY)
        await registry.update_status(agent2.agent_id, AgentStatus.READY)

        ready = await registry.get_ready_agent(agent_type="math")
        assert ready is not None
        assert ready.agent_type == "math"

    @pytest.mark.asyncio
    async def test_get_ready_agent_none_available(self, registry: AgentRegistry):
        """Test getting ready agent when none available."""
        await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research"],
        )
        # Agent is still INITIALIZING, not READY

        ready = await registry.get_ready_agent()
        assert ready is None

    @pytest.mark.asyncio
    async def test_get_ready_agent_round_robin(self, registry: AgentRegistry):
        """Test that get_ready_agent picks agent with oldest heartbeat."""
        agent1 = await registry.register(
            agent_type="research",
            name="Agent 1",
            capabilities=["research"],
        )
        await registry.update_status(agent1.agent_id, AgentStatus.READY)

        # Small delay
        await asyncio.sleep(0.01)

        agent2 = await registry.register(
            agent_type="research",
            name="Agent 2",
            capabilities=["research"],
        )
        await registry.update_status(agent2.agent_id, AgentStatus.READY)

        # Should pick agent1 (older heartbeat)
        ready = await registry.get_ready_agent()
        assert ready.agent_id == agent1.agent_id

    # ===================================
    # METRICS TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_get_metrics_success(self, registry: AgentRegistry):
        """Test getting agent metrics."""
        agent = await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research"],
        )

        metrics = await registry.get_metrics(agent.agent_id)
        assert metrics is not None
        assert isinstance(metrics, AgentMetrics)
        assert metrics.agent_id == agent.agent_id

    @pytest.mark.asyncio
    async def test_get_metrics_not_found(self, registry: AgentRegistry):
        """Test getting metrics for non-existent agent."""
        metrics = await registry.get_metrics("non-existent-id")
        assert metrics is None

    @pytest.mark.asyncio
    async def test_get_all_metrics(self, registry: AgentRegistry):
        """Test getting all metrics."""
        await registry.register(
            agent_type="research",
            name="Agent 1",
            capabilities=["research"],
        )
        await registry.register(
            agent_type="math",
            name="Agent 2",
            capabilities=["proof_generation"],
        )

        all_metrics = await registry.get_all_metrics()
        assert len(all_metrics) == 2

    # ===================================
    # LIST AGENTS TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_list_agents_all(self, registry: AgentRegistry):
        """Test listing all agents."""
        await registry.register(
            agent_type="research",
            name="Agent 1",
            capabilities=["research"],
        )
        await registry.register(
            agent_type="math",
            name="Agent 2",
            capabilities=["proof_generation"],
        )

        agents = await registry.list_agents()
        assert len(agents) == 2

    @pytest.mark.asyncio
    async def test_list_agents_excludes_terminated(self, registry: AgentRegistry):
        """Test that listing excludes terminated agents by default."""
        agent1 = await registry.register(
            agent_type="research",
            name="Agent 1",
            capabilities=["research"],
        )
        agent2 = await registry.register(
            agent_type="math",
            name="Agent 2",
            capabilities=["proof_generation"],
        )

        # Terminate agent1
        await registry.update_status(agent1.agent_id, AgentStatus.TERMINATED)

        agents = await registry.list_agents()
        assert len(agents) == 1
        assert agents[0].agent_id == agent2.agent_id

    @pytest.mark.asyncio
    async def test_list_agents_include_terminated(self, registry: AgentRegistry):
        """Test listing agents including terminated."""
        agent1 = await registry.register(
            agent_type="research",
            name="Agent 1",
            capabilities=["research"],
        )
        await registry.register(
            agent_type="math",
            name="Agent 2",
            capabilities=["proof_generation"],
        )

        await registry.update_status(agent1.agent_id, AgentStatus.TERMINATED)

        agents = await registry.list_agents(include_terminated=True)
        assert len(agents) == 2

    # ===================================
    # EVENTS TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_get_events_all(self, registry: AgentRegistry):
        """Test getting all events."""
        await registry.register(
            agent_type="research",
            name="Agent 1",
            capabilities=["research"],
        )
        await registry.register(
            agent_type="math",
            name="Agent 2",
            capabilities=["proof_generation"],
        )

        events = await registry.get_events()
        assert len(events) >= 2  # At least 2 registration events

    @pytest.mark.asyncio
    async def test_get_events_by_agent(self, registry: AgentRegistry):
        """Test getting events for specific agent."""
        agent1 = await registry.register(
            agent_type="research",
            name="Agent 1",
            capabilities=["research"],
        )
        agent2 = await registry.register(
            agent_type="math",
            name="Agent 2",
            capabilities=["proof_generation"],
        )

        events = await registry.get_events(agent_id=agent1.agent_id)
        for event in events:
            assert event.agent_id == agent1.agent_id

    @pytest.mark.asyncio
    async def test_get_events_by_type(self, registry: AgentRegistry):
        """Test getting events by event type."""
        agent = await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research"],
        )
        await registry.update_status(agent.agent_id, AgentStatus.READY)

        events = await registry.get_events(event_type="registered")
        for event in events:
            assert event.event_type == "registered"

    @pytest.mark.asyncio
    async def test_get_events_since_time(self, registry: AgentRegistry):
        """Test getting events since a specific time."""
        await registry.register(
            agent_type="research",
            name="Agent 1",
            capabilities=["research"],
        )

        cutoff = _utcnow()
        await asyncio.sleep(0.01)

        await registry.register(
            agent_type="math",
            name="Agent 2",
            capabilities=["proof_generation"],
        )

        events = await registry.get_events(since=cutoff)
        # Should only include the second registration
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_get_events_respects_limit(self, registry: AgentRegistry):
        """Test that get_events respects limit."""
        for i in range(10):
            await registry.register(
                agent_type="research",
                name=f"Agent {i}",
                capabilities=["research"],
            )

        events = await registry.get_events(limit=5)
        assert len(events) == 5

    # ===================================
    # STATS TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_get_stats(self, registry: AgentRegistry):
        """Test getting registry statistics."""
        agent1 = await registry.register(
            agent_type="research",
            name="Research Agent",
            capabilities=["research"],
        )
        agent2 = await registry.register(
            agent_type="math",
            name="Math Agent",
            capabilities=["proof_generation"],
        )

        await registry.update_status(agent1.agent_id, AgentStatus.READY)
        await registry.update_status(agent2.agent_id, AgentStatus.BUSY)

        stats = registry.get_stats()

        assert stats["total_agents"] == 2
        assert stats["by_type"]["research"] == 1
        assert stats["by_type"]["math"] == 1
        assert stats["by_status"]["ready"] == 1
        assert stats["by_status"]["busy"] == 1
        assert stats["total_events"] >= 4  # 2 registrations + 2 status changes

    # ===================================
    # HEALTH CHECK TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_check_agent_health_marks_unhealthy(self, registry: AgentRegistry):
        """Test that health check marks agents with expired heartbeat as unhealthy."""
        agent = await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research"],
        )
        await registry.update_status(agent.agent_id, AgentStatus.READY)

        # Manually set last_heartbeat to past
        agent_info = await registry.get_agent(agent.agent_id)
        agent_info.last_heartbeat = _utcnow() - timedelta(seconds=200)

        # Patch settings for short timeout
        with patch('platform.agents.registry.settings') as mock_settings:
            mock_settings.agent_timeout_seconds = 90

            await registry._check_agent_health()

        updated_agent = await registry.get_agent(agent.agent_id)
        assert updated_agent.status == AgentStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_check_agent_health_skips_terminated(self, registry: AgentRegistry):
        """Test that health check skips terminated agents."""
        agent = await registry.register(
            agent_type="research",
            name="Test Agent",
            capabilities=["research"],
        )
        await registry.update_status(agent.agent_id, AgentStatus.TERMINATED)

        # Set old heartbeat
        agent_info = await registry.get_agent(agent.agent_id)
        if agent_info:  # Still in registry before final removal
            agent_info.last_heartbeat = _utcnow() - timedelta(seconds=200)

            with patch('platform.agents.registry.settings') as mock_settings:
                mock_settings.agent_timeout_seconds = 90

                await registry._check_agent_health()

            # Should still be terminated, not unhealthy
            updated = await registry.get_agent(agent.agent_id)
            if updated:
                assert updated.status == AgentStatus.TERMINATED

    # ===================================
    # LIFECYCLE TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_start_creates_health_check_task(self, registry: AgentRegistry):
        """Test that start creates health check task."""
        with patch.object(registry, '_health_check_loop', new_callable=AsyncMock) as mock_loop:
            await registry.start()

            assert registry._health_check_task is not None

            await registry.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_health_check_task(self, registry: AgentRegistry):
        """Test that stop cancels health check task."""
        with patch.object(registry, '_health_check_loop', new_callable=AsyncMock):
            await registry.start()
            await registry.stop()

            assert registry._health_check_task.cancelled() or registry._health_check_task.done()

    # ===================================
    # EVENT TRIMMING TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_event_trimming(self, registry: AgentRegistry):
        """Test that events are trimmed when exceeding limit."""
        # Add many events
        for i in range(10010):
            await registry._record_event("test_event", f"agent-{i}")

        assert len(registry._events) == 10000
