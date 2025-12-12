"""
Agents 模块

提供：
1. Supervisor Architecture
2. Performance Layer
3. Worker Agents
"""

from src.router.agents.api import register_agent_routes

__all__ = [
    "register_agent_routes",
]

