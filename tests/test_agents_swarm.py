"""
Unit tests for Multi-Agent Swarm Interfaces & Coordinator
"""

from src.agents import (
    BaseAgent,
    AgentState,
    SwarmCoordinator,
    IngestionAgent,
    EditorialAgent,
    QualityAuditorAgent,
    DistributionAgent,
)


class DummyAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="DummyAgent", role="Test Role")

    def run(self, payload):
        val = payload.get("input", 0)
        if val < 0:
            raise ValueError("Negative value not allowed")
        return {"output": val * 2}


def test_base_agent_lifecycle_success():
    agent = DummyAgent()
    assert agent.state == AgentState.IDLE
    res = agent.execute({"input": 21})
    assert res["status"] == "success"
    assert res["data"]["output"] == 42
    assert agent.state == AgentState.COMPLETED
    assert agent.execution_count == 1
    assert agent.last_execution_time >= 0.0


def test_base_agent_lifecycle_failure():
    agent = DummyAgent()
    res = agent.execute({"input": -5})
    assert res["status"] == "failed"
    assert "Negative value" in res["error"]
    assert agent.state == AgentState.FAILED
    assert len(agent.error_history) == 1


def test_swarm_coordinator_initialization():
    coordinator = SwarmCoordinator()
    status = coordinator.get_swarm_status()
    assert "ingestion" in status
    assert "editorial" in status
    assert "quality" in status
    assert "distribution" in status
    assert status["ingestion"]["state"] == AgentState.IDLE
    assert status["editorial"]["name"] == "EditorialAgent"
