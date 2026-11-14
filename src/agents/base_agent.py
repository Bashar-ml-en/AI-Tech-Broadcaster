"""
Base Agent Interface for AI Tech Broadcaster Multi-Agent Swarm
Defines standard role, state lifecycle, message passing, and execution contracts.
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

logger = logging.getLogger("base_agent")


class AgentState:
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BaseAgent(ABC):
    """Abstract base class for all specialized broadcast agents."""

    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role
        self.state = AgentState.IDLE
        self.last_execution_time: float = 0.0
        self.last_result: Optional[Dict[str, Any]] = None
        self.execution_count: int = 0
        self.error_history: List[str] = []

    @abstractmethod
    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's core responsibility."""
        pass

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrap execution with state transitions, telemetry, and error trapping."""
        self.state = AgentState.RUNNING
        start_time = time.time()
        self.execution_count += 1

        try:
            result = self.run(payload)
            self.state = AgentState.COMPLETED
            self.last_execution_time = time.time() - start_time
            self.last_result = result
            return {
                "agent": self.name,
                "role": self.role,
                "status": "success",
                "latency_sec": round(self.last_execution_time, 3),
                "data": result,
            }
        except Exception as e:
            self.state = AgentState.FAILED
            self.last_execution_time = time.time() - start_time
            err_msg = str(e)
            self.error_history.append(err_msg)
            logger.exception("[%s] Agent execution failed: %s", self.name, err_msg)
            return {
                "agent": self.name,
                "role": self.role,
                "status": "failed",
                "latency_sec": round(self.last_execution_time, 3),
                "error": err_msg,
            }

    def get_status(self) -> Dict[str, Any]:
        """Return agent telemetry and current health status."""
        return {
            "name": self.name,
            "role": self.role,
            "state": self.state,
            "executions": self.execution_count,
            "last_latency_sec": round(self.last_execution_time, 3),
            "errors_count": len(self.error_history),
        }
